"""
流水线执行器: 模板驱动的 Agent 集群协调器。
支持单步推进(auto=False)和自动运行(auto=True)两种模式，
每步执行时通过WebSocket向前端广播实时进度。
支持repeat_until循环、场景批量调度、审计失败自动重试、超时保护。
"""

import json
import asyncio
import logging
import uuid as uuid_mod
from datetime import UTC, datetime
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from utils.json_parser import parse_llm_json
from sqlalchemy import text as sa_text

from core.gateway.client import ModelGateway
from core.rag.retriever import RAGRetriever
from core.rag.indexer import RAGIndexer
from core.storage.service import StorageService
from core.agent.base import AgentTask
from core.agent.registry import get_agent
from .template import PipelineTemplate, Step, Phase
from .state_machine import PipelineStateMachine, PipelineStatus

from core.narrative.memory_loader import build_narrative_context
from core.narrative.memory_extractor import extract_and_update_memory
from core.narrative.coherence_checker import run_full_coherence_check
from core.narrative.revision_orchestrator import DramaturgeRefiner, DramaturgeReport
from config import DATABASE_URL

_IS_SQLITE = DATABASE_URL.startswith("sqlite")

logger = logging.getLogger(__name__)

AUTO_RUN_GLOBAL_TIMEOUT = 12 * 3600
AUTO_RUN_STEP_TIMEOUT = 900
MAX_AUDIT_RETRIES = 3


class PipelineExecutor:
    """流水线执行器 — 模板驱动"""

    _cancelled_projects: set[str] = set()
    _running_locks_global: dict[str, asyncio.Lock] = {}

    def __init__(self, db: AsyncSession, gateway: ModelGateway,
                 rag: RAGRetriever, storage: StorageService,
                 target_phases: list[str] | None = None):
        self.db = db
        self.gateway = gateway
        self.rag = rag
        self.storage = storage
        self.state_machine = PipelineStateMachine(db)
        self.target_phases = target_phases or []

    def _get_lock(self, project_id: str) -> asyncio.Lock:
        if project_id not in self._running_locks_global:
            self._running_locks_global[project_id] = asyncio.Lock()
        return self._running_locks_global[project_id]

    def _ws(self):
        from websocket.manager import ws_manager
        return ws_manager

    async def _notify_progress(self, project_id: str, phase_name: str,
                                step_idx: int, total_steps: int,
                                agent_name: str, skill: str, status: str,
                                message: str = "", progress_pct: int = 0,
                                phase_index: int | None = None):
        try:
            state = None
            if phase_index is None:
                try:
                    state = await self.state_machine.get_state(project_id)
                    phase_index = state.current_phase_index if state else 0
                except Exception:
                    phase_index = 0
            await self._ws().broadcast_to_project(project_id, {
                "type": "pipeline_progress",
                "phase": phase_name,
                "phase_index": phase_index,
                "step_index": step_idx,
                "total_steps": total_steps,
                "agent": agent_name,
                "skill": skill,
                "status": status,
                "message": message,
                "progress": progress_pct,
                "timestamp": datetime.now(UTC).isoformat(),
            })
        except Exception:
            pass

    async def _notify_agent_status(self, project_id: str, agent_name: str,
                                    status: str, current_task: str = ""):
        try:
            await self._ws().send_agent_update(project_id, agent_name, status, current_task)
        except Exception:
            pass

    async def _notify_task_progress(self, project_id: str, task_id: str,
                                     progress: int, status: str, message: str = ""):
        try:
            await self._ws().broadcast_to_project(project_id, {
                "type": "task_progress",
                "task_id": task_id,
                "progress": progress,
                "status": status,
                "message": message,
                "timestamp": datetime.now(UTC).isoformat(),
            })
        except Exception:
            pass

    async def cancel(self, project_id: str, reason: str = "流水线已被用户取消"):
        self._cancelled_projects.add(project_id)
        await self.state_machine.cancel(project_id, reason)

    def _is_cancelled(self, project_id: str) -> bool:
        return project_id in self._cancelled_projects

    async def advance(self, project_id: str) -> dict:
        lock = self._get_lock(project_id)
        if lock.locked():
            return {"status": "error", "message": "流水线正在执行中，请勿重复操作"}

        async with lock:
            return await self._advance_inner(project_id)

    async def _advance_inner(self, project_id: str) -> dict:
        state = await self.state_machine.get_state(project_id)
        if not state:
            return {"status": "error", "message": "Pipeline未初始化"}

        if state.status == PipelineStatus.COMPLETED:
            return {"status": "completed", "message": "流程已完成"}

        if state.status == PipelineStatus.WAITING_HUMAN:
            return {"status": "waiting_human", "message": "等待人工审核"}

        if state.status == PipelineStatus.FAILED:
            return {"status": "failed", "message": state.error_message}

        if state.status == PipelineStatus.CANCELLED:
            return {"status": "cancelled", "message": state.error_message or "流水线已取消"}

        from .template_loader import get_template
        template = get_template(state.template_name)

        if state.current_phase_index >= len(template.phases):
            await self.state_machine.transition(project_id, PipelineStatus.COMPLETED)
            await self._notify_progress(project_id, "完成", 0, 0, "系统", "", "completed", "全部阶段完成", 100)
            return {"status": "completed", "message": "全部阶段完成"}

        phase = template.phases[state.current_phase_index]

        # 如果设置了 target_phases，跳过不在目标列表中的阶段
        if self.target_phases and phase.name not in self.target_phases:
            logger.info("阶段 '%s' 不在 target_phases %s 中，跳过", phase.name, self.target_phases)
            await self.state_machine.advance_phase(project_id)
            await self._notify_progress(
                project_id, phase.name, 0, 0,
                "系统", "", "skipped",
                f"跳过阶段 '{phase.name}'（不在目标阶段列表中）",
                self._calc_progress(template, state),
            )
            return await self._start_next_phase(project_id, template)

        if state.current_step_index >= len(phase.steps):
            if phase.repeat_until:
                should_repeat = await self._check_repeat_condition(
                    project_id, phase.repeat_until, state
                )
                if should_repeat:
                    next_step = 0
                    await self.state_machine.set_step(project_id, state.current_phase_index, next_step)
                    current_iter = state.result_data.get("scene_iteration_count", 0) + 1
                    await self.state_machine.update_result_data(project_id, "scene_iteration_count", current_iter)
                    try:
                        chapters = await self.storage.get_chapter_outlines(project_id)
                        cfg = await self.storage.get_project_config(project_id) or {}
                        scenes_per_chapter_min = cfg.get("scenes_per_chapter_min", 3)
                        next_ch_idx = 0
                        for ch_idx, ch in enumerate(chapters):
                            ch_id = str(ch.get("id", ""))
                            ch_scenes = await self.storage.get_scenes_by_chapter(project_id, ch_id)
                            has_unfinalized = any(s.get("status") != "finalized" for s in ch_scenes)
                            if has_unfinalized or len(ch_scenes) < scenes_per_chapter_min:
                                next_ch_idx = ch_idx
                                break
                        await self.state_machine.update_result_data(project_id, "current_chapter_index", next_ch_idx)
                    except Exception as e:
                        logger.warning("更新current_chapter_index失败: %s", e)
                    await self._notify_progress(
                        project_id, phase.name, next_step, len(phase.steps),
                        "系统", "", "running",
                        f"阶段 '{phase.name}' 循环继续（{phase.repeat_until}）",
                        self._calc_progress(template, state),
                    )
                    return {"status": "ok", "message": f"循环继续: {phase.repeat_until}"}

            if phase.human_gate:
                await self.state_machine.transition(project_id, PipelineStatus.WAITING_HUMAN)
                return {
                    "status": "waiting_human",
                    "phase": phase.name,
                    "message": f"阶段 '{phase.name}' 完成，等待审核",
                }
            else:
                await self._reindex_all_content(project_id)
                await self.state_machine.advance_phase(project_id)
                return await self._start_next_phase(project_id, template)

        step = phase.steps[state.current_step_index]
        total_steps = len(phase.steps)

        step_flag = f"layer{state.current_phase_index}_{step.skill}_built"
        if state.result_data.get(step_flag) and not getattr(self, 'force_regenerate', False):
            logger.info("跳过已完成步骤: %s.%s (flag=%s)", phase.name, step.skill, step_flag)
            await self.state_machine.advance_step(project_id)
            await self._notify_progress(
                project_id, phase.name, state.current_step_index + 1, total_steps,
                step.agent, step.skill, "skipped",
                f"跳过已完成: {step.skill}",
                self._calc_progress(template, state),
            )
            return {"status": "ok", "message": f"跳过已完成步骤: {step.skill}"}

        if step.skill == "scene_writer":
            scene_plan = state.result_data.get("next_step", {})
            if scene_plan.get("status") == "all_done":
                logger.info("rag_retriever 检测到所有场景已完成，跳过 scene_writer")
                await self.state_machine.advance_step(project_id)
                await self._notify_progress(
                    project_id, phase.name, state.current_step_index + 1, total_steps,
                    step.agent, step.skill, "skipped",
                    "所有场景已生成完毕，跳过场景写作",
                    self._calc_progress(template, state),
                )
                return {"status": "ok", "message": "所有场景已生成完毕，跳过场景写作"}
            if scene_plan.get("status") == "no_chapters":
                logger.info("rag_retriever 检测到无章节大纲，跳过 scene_writer")
                await self.state_machine.mark_failed(project_id, "缺少章节大纲，无法生成场景")
                await self._notify_progress(
                    project_id, phase.name, state.current_step_index, total_steps,
                    step.agent, step.skill, "failed",
                    "无章节大纲，场景写作阶段终止",
                    self._calc_progress(template, state),
                )
                return {"status": "failed", "message": "缺少章节大纲，无法生成场景"}

        await self._notify_progress(project_id, phase.name,
                                     state.current_step_index, total_steps,
                                     step.agent, step.skill, "running",
                                     f"正在执行: {phase.name} → {step.skill}",
                                     self._calc_progress(template, state))

        await self._notify_agent_status(project_id, step.agent, "busy",
                                         f"{phase.name}: {step.skill}")

        result = await self._execute_step_with_retry(project_id, template, phase, step, state)

        state = await self.state_machine.get_state(project_id) or state

        await self.state_machine.append_result(project_id, {
            "key": f"{state.current_phase_index}-{state.current_step_index}",
            "phase": phase.name,
            "agent": step.agent,
            "skill": step.skill,
            "status": result.get("status", "unknown"),
            "completed_at": datetime.now(UTC).isoformat(),
        })

        if result.get("status") not in ("completed", "pass"):
            error_message = result.get("error") or f"步骤执行失败: {step.agent}.{step.skill}"
            await self.state_machine.mark_failed(project_id, error_message)
            await self._notify_progress(project_id, phase.name,
                                         state.current_step_index, total_steps,
                                         step.agent, step.skill, "failed",
                                         f"失败: {step.skill}",
                                         self._calc_progress(template, state))
            await self._notify_agent_status(project_id, step.agent, "idle")
            return {
                "status": "failed",
                "phase": phase.name,
                "message": error_message,
                "step_failed": {"agent": step.agent, "skill": step.skill},
                "result": result,
            }

        await self.state_machine.advance_step(project_id)

        await self._notify_progress(project_id, phase.name,
                                     state.current_step_index + 1, total_steps,
                                     step.agent, step.skill, "completed",
                                     f"完成: {step.skill}",
                                     self._calc_progress(template, state))

        await self._notify_agent_status(project_id, step.agent, "idle")

        return {
            "status": "ok",
            "phase": phase.name,
            "step_completed": {"agent": step.agent, "skill": step.skill},
            "result": result,
            "next_step": (
                state.current_step_index + 1
                if state.current_step_index + 1 < len(phase.steps)
                else None
            ),
        }

    async def _check_repeat_condition(self, project_id: str,
                                       condition: str, state) -> bool:
        if condition == "all_scenes_done":
            return await self._check_all_scenes_done(project_id, state)
        if condition == "all_chapters_done":
            return await self._check_all_chapters_done(project_id, state)
        return False

    async def _check_all_scenes_done(self, project_id: str, state) -> bool:
        """
        检查是否所有场景都已生成完毕。
        返回 True = 还有场景需要生成（继续循环）
        返回 False = 所有场景已完成（停止循环）
        """
        try:
            max_scene_iterations = state.result_data.get("max_scene_iterations", 30)
            current_iteration = state.result_data.get("scene_iteration_count", 0)
            if current_iteration >= max_scene_iterations:
                return False

            target_word_count = state.result_data.get("target_word_count", 50000)
            target_chapter_count = state.result_data.get("chapter_count", 10)
            chapters = await self.storage.get_chapter_outlines(project_id)
            if not chapters:
                logger.info("尚无章节大纲，跳过场景生成循环")
                return False

            cfg = await self.storage.get_project_config(project_id) or {}
            scenes_per_chapter_min = cfg.get("scenes_per_chapter_min", 3)
            scenes_per_chapter_max = cfg.get("scenes_per_chapter_max", 6)

            total_scenes_needed = 0
            total_scenes_written = 0
            total_written_words = 0
            chapters_with_insufficient_scenes = 0

            for ch in chapters:
                ch_id = str(ch.get("id", ""))
                scenes = await self.storage.get_scenes_by_chapter(project_id, ch_id)
                draft_scenes = [s for s in scenes if s.get("status") != "finalized"]
                finalized_scenes = [s for s in scenes if s.get("status") == "finalized"]
                scene_count = len(scenes)
                total_scenes_needed += scenes_per_chapter_max
                total_scenes_written += scene_count

                if len(finalized_scenes) < scenes_per_chapter_min:
                    chapters_with_insufficient_scenes += 1

                for sc in scenes:
                    narration_len = len(sc.get("narration", ""))

                    dialogue = sc.get("dialogue", "")
                    if isinstance(dialogue, list):
                        dialogue_len = sum(len(d.get("text", "")) for d in dialogue if isinstance(d, dict))
                    elif isinstance(dialogue, str):
                        try:
                            dlg_list = json.loads(dialogue)
                            dialogue_len = sum(len(d.get("text", "")) for d in dlg_list if isinstance(d, dict))
                        except (json.JSONDecodeError, TypeError):
                            dialogue_len = len(dialogue)
                    else:
                        dialogue_len = 0

                    actions = sc.get("actions", "")
                    if isinstance(actions, list):
                        actions_len = sum(len(str(a)) for a in actions)
                    elif isinstance(actions, str):
                        try:
                            act_list = json.loads(actions)
                            actions_len = sum(len(str(a)) for a in act_list)
                        except (json.JSONDecodeError, TypeError):
                            actions_len = len(actions)
                    else:
                        actions_len = 0

                    total_written_words += narration_len + dialogue_len + actions_len

            logger.info(
                "场景完成检查: 章节=%d, 已写场景=%d, 需要场景=%d, 不足章节=%d, 已写字数=%d, 目标=%d",
                len(chapters), total_scenes_written, total_scenes_needed,
                chapters_with_insufficient_scenes, total_written_words, target_word_count
            )

            # 如果还有章节没有达到最小场景数，继续生成
            if chapters_with_insufficient_scenes > 0:
                return True

            # 如果总字数未达到目标的80%，继续生成
            if total_written_words < target_word_count * 0.8:
                return True

            # 如果还有章节没有场景，继续生成
            if total_scenes_written < len(chapters) * scenes_per_chapter_min:
                return True

            return False
        except Exception as e:
            logger.warning("检查场景完成状态失败: %s", e)
            return True

    async def _check_all_chapters_done(self, project_id: str, state) -> bool:
        try:
            chapters = await self.storage.get_chapter_outlines(project_id)
            if not chapters:
                return True

            target_chapter_count = state.result_data.get("chapter_count", 10)
            if len(chapters) < target_chapter_count:
                return True

            for ch in chapters:
                if ch.get("status") in ("draft", None, ""):
                    return True
            return False
        except Exception as e:
            logger.warning("检查章节完成状态失败: %s", e)
            return True

    async def _execute_step_with_retry(self, project_id: str,
                                         template: PipelineTemplate,
                                         phase: Phase, step: Step,
                                         state) -> dict:
        last_result = None
        for attempt in range(MAX_AUDIT_RETRIES + 1):
            try:
                result = await asyncio.wait_for(
                    self._execute_step(project_id, template, phase, step, state),
                    timeout=step.timeout if step.timeout and step.timeout > 0 else AUTO_RUN_STEP_TIMEOUT,
                )
            except asyncio.TimeoutError:
                return {
                    "status": "failed",
                    "error": f"步骤超时 ({step.timeout or AUTO_RUN_STEP_TIMEOUT}s): {step.agent}.{step.skill}",
                }

            last_result = result

            if result.get("status") not in ("completed", "pass"):
                return result

            if step.skill in ("scene_writer", "component_writer", "chapter_writer", "novel_writer") and result.get("data"):
                audit_result = await self._auto_audit_scene(
                    project_id, result["data"], state
                )
                if audit_result.get("overall") == "fail":
                    if attempt < MAX_AUDIT_RETRIES:
                        issues = audit_result.get("issues", [])
                        fix_instructions = "; ".join(issues[:3])
                        logger.info("场景审计失败(第%d次)，自动重试: %s", attempt + 1, fix_instructions)
                        await self._notify_progress(
                            project_id, phase.name,
                            state.current_step_index if state else 0, len(phase.steps),
                            step.agent, step.skill, "retrying",
                            f"审计未通过，自动重试({attempt + 1}/{MAX_AUDIT_RETRIES}): {fix_instructions[:100]}",
                            self._calc_progress(template, state),
                        )
                        state = await self.state_machine.get_state(project_id)
                        if state and state.result_data:
                            prev_data = state.result_data
                        else:
                            prev_data = {}
                        prev_data["audit_fix_instructions"] = fix_instructions
                        await self.state_machine.update_result_data(
                            project_id, "audit_fix_instructions", fix_instructions
                        )
                        prev_data["revision_mode"] = True
                        prev_data["existing_scene_content"] = result.get("data", {})
                        await self.state_machine.update_result_data(
                            project_id, "revision_mode", True
                        )
                        await self.state_machine.update_result_data(
                            project_id, "existing_scene_content", result.get("data", {})
                        )
                        continue
                    else:
                        logger.warning("场景审计失败已达最大重试次数(%d)", MAX_AUDIT_RETRIES)
                        return result

            if step.skill in ("scene_writer", "component_writer", "chapter_writer", "novel_writer") and result.get("data"):
                scene_id = result["data"].get("scene_id", "")
                if scene_id:
                    try:
                        await self.db.execute(
                            sa_text("UPDATE scenes SET status = 'finalized' WHERE id = :sid"),
                            {"sid": scene_id},
                        )
                        await self.db.commit()
                        await self._notify_data_changed(project_id, "scene_finalized",
                                                         {"entity_id": scene_id})
                    except Exception as e:
                        logger.warning("标记场景finalized失败: %s", e)

            await self.state_machine.update_result_data(project_id, "revision_mode", False)
            await self.state_machine.update_result_data(project_id, "existing_scene_content", {})
            await self.state_machine.update_result_data(project_id, "audit_fix_instructions", "")

            return result

        return last_result or {"status": "failed", "error": "重试次数耗尽"}

    async def _auto_audit_scene(self, project_id: str, scene_data: dict,
                                 state) -> dict:
        try:
            from core.agent.auditor import AuditorAgent
            auditor = get_agent("auditor", self.gateway, self.rag, self.storage)
            scene_id = scene_data.get("scene_id", "")
            if not scene_id:
                return {"overall": "pass", "issues": []}

            audit_task = AgentTask(
                task_id=f"{project_id}_auto_audit_{scene_id}",
                agent_name="auditor",
                task_type="llm_audit",
                project_id=project_id,
                payload={
                    "scene_id": scene_id,
                    "audit_type": "scene",
                },
                cost_profile="economy",
            )
            audit_result = await auditor.execute(audit_task)

            await self._persist_audit_record(
                project_id, scene_id, "auto_scene", audit_result
            )

            if audit_result.status == "fail":
                return {
                    "overall": "fail",
                    "issues": audit_result.issues or ["审计未通过"],
                }

            _scene_content_str = ""
            try:
                _narrative_ctx = await build_narrative_context(self.db, project_id)
                _scp = []
                _narr = scene_data.get("narration", "")
                if _narr:
                    _scp.append(_narr)
                _dlg = scene_data.get("dialogue", [])
                if isinstance(_dlg, list):
                    _scp.extend(f"{d.get('char', '?')}: {d.get('text', '')}" for d in _dlg if isinstance(d, dict))
                elif _dlg:
                    _scp.append(str(_dlg))
                _acts = scene_data.get("actions", [])
                if isinstance(_acts, list):
                    _scp.extend(str(a) for a in _acts)
                elif _acts:
                    _scp.append(str(_acts))
                _scene_content_str = "\n".join(_scp)

                _coherence_report = await run_full_coherence_check(
                    self.db, project_id, scene_id, _scene_content_str, _narrative_ctx
                )

                if not _coherence_report.all_passed:
                    _all_issues = []
                    _all_suggestions = []
                    for _chk in _coherence_report.checks:
                        if not _chk.passed:
                            _all_issues.extend(_chk.issues)
                            _all_suggestions.extend(_chk.suggestions)
                    return {
                        "overall": "fail",
                        "issues": _all_issues or ["5层逻辑校验未通过"],
                        "suggestions": _all_suggestions,
                    }
            except Exception as _ce:
                logger.warning("5层逻辑校验执行失败: %s", _ce)

            try:
                _refiner = DramaturgeRefiner(self.db, project_id)
                _drama_scenes = [{"scene_id": scene_id, "content": _scene_content_str}]
                _drama_report: DramaturgeReport = await _refiner.run_dramaturge_refinement(_drama_scenes)

                _drama_data = {
                    "global_review_score": _drama_report.global_review.overall_score,
                    "global_review_summary": _drama_report.global_review.summary,
                    "scene_defect_count": sum(len(sr.defects) for sr in _drama_report.scene_reviews),
                    "revision_count": len(_drama_report.revisions),
                    "final_status": _drama_report.final_status,
                    "iterations": _drama_report.iterations,
                }

                await self._persist_dramaturge_record(project_id, scene_id, _drama_report, _drama_data)

                if _drama_report.final_status == "needs_manual_review":
                    _drama_issues = []
                    for sr in _drama_report.scene_reviews:
                        for defect in sr.defects:
                            _drama_issues.append(f"[{defect.defect_type}] {defect.description}")
                    if _drama_issues:
                        return {
                            "overall": "fail",
                            "issues": _drama_issues[:5],
                            "suggestions": [d.suggestion for sr in _drama_report.scene_reviews for d in sr.defects if d.suggestion][:5],
                        }
            except Exception as _de:
                logger.warning("Dramaturge精炼执行失败（非致命）: %s", _de)

            return {"overall": "pass", "issues": []}
        except Exception as e:
            logger.error("自动审计失败，按失败处理: %s", e)
            return {"overall": "fail", "issues": [f"自动审计执行失败: {str(e)[:200]}"]}

    async def _persist_audit_record(self, project_id: str, scene_id: str,
                                     audit_type: str, audit_result):
        try:
            import uuid as _uuid
            from datetime import UTC, datetime as _dt

            overall = "pass"
            if hasattr(audit_result, 'status'):
                overall = "pass" if audit_result.status in ("completed", "pass") else "fail"
            elif isinstance(audit_result, dict):
                overall = audit_result.get("overall", "pass")

            data = {}
            if hasattr(audit_result, 'data') and isinstance(getattr(audit_result, 'data', None), dict):
                data = getattr(audit_result, 'data', {})
            elif isinstance(audit_result, dict):
                data = audit_result

            checker_results = data.get("phase_a", {})
            llm_results = data.get("phase_b")
            creative_scores = data.get("phase_c")
            issues = data.get("issues", [])
            suggestions = data.get("suggestions", [])

            if hasattr(audit_result, 'issues') and getattr(audit_result, 'issues', None):
                issues = getattr(audit_result, 'issues', [])

            audit_id = str(_uuid.uuid4())
            now_expr = "datetime('now')" if _IS_SQLITE else "NOW()"

            await self.db.execute(
                sa_text(
                    f"""INSERT INTO audit_records
                    (id, project_id, scene_id, audit_type, checker_results,
                     llm_results, creative_scores, overall_result, issues, suggestions, created_at)
                    VALUES (:id, :pid, :sid, :atype, :checker,
                            :llm, :creative, :overall, :issues, :suggestions, {now_expr})"""
                ),
                {
                    "id": audit_id,
                    "pid": project_id,
                    "sid": scene_id,
                    "atype": audit_type,
                    "checker": json.dumps(checker_results, ensure_ascii=False) if isinstance(checker_results, dict) else "{}",
                    "llm": json.dumps(llm_results, ensure_ascii=False) if llm_results else None,
                    "creative": json.dumps(creative_scores, ensure_ascii=False) if creative_scores else None,
                    "overall": overall,
                    "issues": json.dumps(issues, ensure_ascii=False) if isinstance(issues, list) else "[]",
                    "suggestions": json.dumps(suggestions, ensure_ascii=False) if isinstance(suggestions, list) else "[]",
                },
            )
            await self.db.commit()
            logger.info("Audit record persisted: scene=%s, overall=%s", scene_id, overall)
        except Exception as e:
            logger.warning("持久化审计记录失败: %s", str(e))

    async def _persist_dramaturge_record(self, project_id: str, scene_id: str,
                                          report: DramaturgeReport, summary_data: dict):
        try:
            import uuid as _uuid
            from datetime import UTC, datetime as _dt

            audit_id = str(_uuid.uuid4())
            now_expr = "datetime('now')" if _IS_SQLITE else "NOW()"

            rhythm_issues = [{"severity": i.get("severity", ""), "description": i.get("description", "")} for i in report.global_review.rhythm_issues]
            char_arc_issues = [{"severity": i.get("severity", ""), "description": i.get("description", "")} for i in report.global_review.character_arc_issues]
            scene_defects = [{"type": d.defect_type, "priority": d.priority, "description": d.description} for sr in report.scene_reviews for d in sr.defects]
            revisions = [{"granularity": r.granularity, "target": r.target, "description": r.description} for r in report.revisions]

            await self.db.execute(
                sa_text(
                    f"""INSERT INTO audit_records
                    (id, project_id, scene_id, audit_type, checker_results,
                     llm_results, creative_scores, overall_result, issues, suggestions, created_at)
                    VALUES (:id, :pid, :sid, :atype, :checker,
                            :llm, :creative, :overall, :issues, :suggestions, {now_expr})"""
                ),
                {
                    "id": audit_id,
                    "pid": project_id,
                    "sid": scene_id,
                    "atype": "dramaturge_refinement",
                    "checker": json.dumps({"rhythm_issues": rhythm_issues, "character_arc_issues": char_arc_issues}, ensure_ascii=False),
                    "llm": json.dumps(scene_defects, ensure_ascii=False),
                    "creative": json.dumps(revisions, ensure_ascii=False),
                    "overall": "pass" if report.final_status == "passed" else "fail",
                    "issues": json.dumps([d.description for sr in report.scene_reviews for d in sr.defects], ensure_ascii=False),
                    "suggestions": json.dumps([d.suggestion for sr in report.scene_reviews for d in sr.defects if d.suggestion], ensure_ascii=False),
                },
            )
            await self.db.commit()
            logger.info("Dramaturge record persisted: scene=%s, status=%s", scene_id, report.final_status)
        except Exception as e:
            logger.warning("持久化Dramaturge记录失败: %s", str(e))

    async def _db_keepalive(self):
        try:
            await self.db.execute(sa_text("SELECT 1"))
        except Exception as e:
            logger.warning("数据库保活检测失败: %s", e)

    async def auto_run(self, project_id: str, force_regenerate: bool = False) -> dict:
        self._cancelled_projects.discard(project_id)
        self.force_regenerate = force_regenerate

        state = await self.state_machine.get_state(project_id)
        template_name = state.template_name if state else ""
        phases_info = []
        if template_name:
            try:
                from .template_loader import get_template as _get_tpl
                tpl = _get_tpl(template_name)
                phases_info = [{"name": p.name, "steps": len(p.steps), "human_gate": p.human_gate} for p in tpl.phases]
            except Exception:
                pass

        await self._notify_progress(
            project_id, "启动", 0, 0, "系统", "", "running",
            "流水线自动运行开始", 0,
        )

        try:
            await self._ws().broadcast_to_project(project_id, {
                "type": "pipeline_progress",
                "phase": "启动",
                "phase_index": 0,
                "step_index": 0,
                "total_steps": 0,
                "agent": "系统",
                "skill": "",
                "status": "running",
                "message": "流水线自动运行开始",
                "progress": 0,
                "phases": phases_info,
                "total_phases": len(phases_info),
                "timestamp": datetime.now(UTC).isoformat(),
            })
        except Exception:
            pass

        start_time = asyncio.get_event_loop().time()
        consecutive_failures = 0
        MAX_CONSECUTIVE_FAILURES = 3

        try:
            while True:
                elapsed = asyncio.get_event_loop().time() - start_time
                if elapsed > AUTO_RUN_GLOBAL_TIMEOUT:
                    msg = f"流水线全局超时 ({AUTO_RUN_GLOBAL_TIMEOUT}s)"
                    await self.state_machine.mark_failed(project_id, msg)
                    await self._notify_progress(project_id, "超时", 0, 0, "系统", "", "failed", msg, 0)
                    return {"status": "failed", "message": msg}

                if self._is_cancelled(project_id):
                    await self.state_machine.cancel(project_id, "流水线已被取消")
                    await self._notify_progress(project_id, "取消", 0, 0, "系统", "", "cancelled", "流水线已被取消", 0)
                    return {"status": "cancelled", "message": "流水线已被取消"}

                result = await self.advance(project_id)
                status = result.get("status")
                logger.info(
                    "auto_run advance 返回: status=%s, phase=%s, message=%s",
                    status, result.get("phase", ""), result.get("message", "")[:100],
                )

                if status == "completed":
                    await self._notify_progress(project_id, "完成", 0, 0, "系统", "", "completed", "流水线全部完成!", 100)
                    return result

                if status == "ok":
                    consecutive_failures = 0
                    await self._db_keepalive()
                    await asyncio.sleep(0.3)
                    continue

                if status == "waiting_human":
                    await self._notify_progress(project_id, "自动审核", 0, 0, "系统", "", "running", "全自动模式：自动通过审核门，继续生成...", 50)
                    await self.state_machine.approve(project_id)
                    await self.state_machine.advance_phase(project_id)
                    cur_state = await self.state_machine.get_state(project_id)
                    if cur_state:
                        from .template_loader import get_template as _get_tpl
                        if cur_state.current_phase_index >= len(_get_tpl(cur_state.template_name).phases):
                            await self.state_machine.transition(project_id, PipelineStatus.COMPLETED)
                            await self._notify_progress(project_id, "完成", 0, 0, "系统", "", "completed", "流水线全部完成!", 100)
                            return {"status": "completed", "message": "全部阶段完成"}
                    continue

                if status in ("failed", "error"):
                    consecutive_failures += 1
                    step_info = result.get("step_failed", {})
                    step_name = f"{step_info.get('agent', '?')}.{step_info.get('skill', '?')}"
                    error_msg = result.get("message", "未知错误")
                    dep_error = result.get("result", {}).get("dependency_error", False)
                    is_retryable = result.get("result", {}).get("retryable", False)

                    if dep_error:
                        rollback_target = await self._find_missing_dep_rollback_target(project_id, error_msg)
                        if rollback_target:
                            target_phase, target_step, target_skill = rollback_target
                            logger.info(
                                "依赖缺失检测: 当前步骤 '%s' 因缺少 '%s' 失败，自动回退到阶段%d步骤%d重做 '%s'",
                                step_info.get('skill', '?'), target_skill, target_phase, target_step, target_skill
                            )
                            await self._notify_progress(
                                project_id, "回退修复", 0, 0, step_info.get('agent', ''), step_info.get('skill', ''),
                                "retrying",
                                f"检测到前置步骤 '{target_skill}' 数据缺失，自动回退修复...",
                                0
                            )
                            await self.state_machine.rollback_to_step(project_id, target_phase, target_step)
                            consecutive_failures = 0
                            continue

                    if is_retryable:
                        retry_wait = min(60, 10 * consecutive_failures)
                        logger.warning(
                            "步骤 %s 网络错误(可重试)，%ds后自动重试: %s",
                            step_name, retry_wait, error_msg[:200]
                        )
                        await self._notify_progress(
                            project_id, "网络重试", 0, 0, step_info.get('agent', ''), step_info.get('skill', ''),
                            "retrying",
                            f"网络断连，{retry_wait}s后自动重试: {error_msg[:100]}",
                            0
                        )
                        retry_ok = await self._retry_from_failure(project_id)
                        if retry_ok:
                            await asyncio.sleep(retry_wait)
                            consecutive_failures = 0
                            continue
                        else:
                            logger.error("重试状态恢复失败，放弃重试")
                            return result

                    if consecutive_failures < MAX_CONSECUTIVE_FAILURES:
                        wait_seconds = min(30, 5 * consecutive_failures)

                        if step_info.get("skill") in ("scene_writer",) and consecutive_failures >= 2:
                            logger.warning("scene_writer连续失败%d次，跳过当前场景继续", consecutive_failures)
                            await self.state_machine.advance_step(project_id)
                            await self._notify_progress(
                                project_id, "跳过", 0, 0, step_info.get('agent', ''), step_info.get('skill', ''),
                                "skipped",
                                f"场景连续失败，已跳过并继续",
                                0
                            )
                            consecutive_failures = 0
                            continue

                        logger.warning(
                            "步骤 %s 失败(第%d次)，%ds后自动重试: %s",
                            step_name, consecutive_failures, wait_seconds, error_msg[:200]
                        )
                        await self._notify_progress(
                            project_id, "重试", 0, 0, step_info.get('agent', ''), step_info.get('skill', ''),
                            "retrying",
                            f"步骤失败，{wait_seconds}s后自动重试({consecutive_failures}/{MAX_CONSECUTIVE_FAILURES}): {error_msg[:100]}",
                            0
                        )
                        await asyncio.sleep(wait_seconds)

                        retry_ok = await self._retry_from_failure(project_id)
                        if retry_ok:
                            continue
                        else:
                            logger.error("重试状态恢复失败，放弃重试")
                            return result
                    else:
                        logger.error(
                            "步骤 %s 连续失败%d次，停止自动重试: %s",
                            step_name, MAX_CONSECUTIVE_FAILURES, error_msg[:200]
                        )
                        await self._notify_progress(
                            project_id, "失败", 0, 0, step_info.get('agent', ''), step_info.get('skill', ''),
                            "failed",
                            f"连续失败{MAX_CONSECUTIVE_FAILURES}次，已停止。可在前端点击「从失败处继续」恢复。",
                            0
                        )
                        return result

        except Exception as e:
            logger.error("流水线自动运行失败: %s", e)
            await self.state_machine.mark_failed(project_id, str(e)[:500])
            await self._notify_progress(project_id, "错误", 0, 0, "系统", "", "failed", str(e)[:200], 0)
            return {"status": "failed", "message": str(e)}
        finally:
            self._cancelled_projects.discard(project_id)
            self._running_locks_global.pop(project_id, None)

    async def _retry_from_failure(self, project_id: str) -> bool:
        """从失败状态恢复，保留已完成的步骤结果，重新执行失败步骤"""
        try:
            state = await self.state_machine.get_state(project_id)
            if not state or state.status != PipelineStatus.FAILED:
                return False

            state.status = PipelineStatus.RUNNING
            state.error_message = ""

            results = list(state.task_results)
            current_key = f"{state.current_phase_index}-{state.current_step_index}"
            for i, tr in enumerate(results):
                if tr.get("key") == current_key and tr.get("status") == "failed":
                    results[i] = {**tr, "status": "retrying", "retried_at": datetime.now(UTC).isoformat()}
                    break
            state.task_results = results
            await self.state_machine._save(state)
            return True
        except Exception as e:
            logger.error("重试状态恢复失败: %s", e)
            return False

    SKILL_TO_DEP_BLOCKER = {
        "world_builder": "story_planner",
        "character_designer": "world_builder",
        "relation_network_designer": "character_designer",
        "foreshadow_designer": "world_builder",
        "foreshadow_reaction": "foreshadow_designer",
        "wow_plan_designer": "foreshadow_designer",
        "chapter_outliner": "world_builder",
        "outline_writer": "world_builder",
        "scene_writer": "world_builder",
        "component_writer": "world_builder",
        "chapter_writer": "world_builder",
        "novel_writer": "world_builder",
        "choice_designer": "chapter_outliner",
        "branch_reachability_checker": "choice_designer",
        "choice_validity_audit": "choice_designer",
        "branch_reachability_audit": "choice_designer",
        "consequence_consistency_audit": "choice_designer",
        "foreshadow_recovery_audit": "foreshadow_designer",
    }

    async def _find_missing_dep_rollback_target(self, project_id: str, error_msg: str) -> tuple[int, int, str] | None:
        """解析依赖缺失错误消息，在流水线模板中查找缺失依赖步骤的准确位置"""
        try:
            state = await self.state_machine.get_state(project_id)
            if not state:
                return None

            from .template_loader import get_template as _get_tpl
            template = _get_tpl(state.template_name)
            current_skill = None
            if state.current_phase_index < len(template.phases):
                phase = template.phases[state.current_phase_index]
                if state.current_step_index < len(phase.steps):
                    current_skill = phase.steps[state.current_step_index].skill

            target_skill = None
            if current_skill:
                target_skill = self.SKILL_TO_DEP_BLOCKER.get(current_skill)

            if not target_skill:
                import re
                match = re.search(r"'(world_builder|character_designer|chapter_outliner|outline_writer|foreshadow_designer|relation_network_designer|choice_designer)'", error_msg)
                if match:
                    target_skill = match.group(1)

            if not target_skill:
                return None

            for p_idx, ph in enumerate(template.phases):
                if p_idx > state.current_phase_index:
                    break
                start_s = 0 if p_idx < state.current_phase_index else 0
                for s_idx in range(start_s, len(ph.steps)):
                    st = ph.steps[s_idx]
                    if st.skill == target_skill:
                        if p_idx == state.current_phase_index and s_idx >= state.current_step_index:
                            continue
                        return (p_idx, s_idx, target_skill)

            for p_idx, ph in enumerate(template.phases):
                for s_idx, st in enumerate(ph.steps):
                    if st.skill == target_skill:
                        return (p_idx, s_idx, target_skill)

            return None
        except Exception as e:
            logger.error("查找依赖回退目标失败: %s", e)
            return None

    async def approve(self, project_id: str) -> dict:
        """批准当前阶段的人工审核门"""
        try:
            state = await self.state_machine.get_state(project_id)
            if not state:
                return {"status": "error", "message": "Pipeline未初始化"}
            if state.status != PipelineStatus.WAITING_HUMAN:
                return {"status": "error", "message": f"当前状态不是待审核: {state.status.value}"}
            await self.state_machine.approve(project_id)
            return {"status": "approved"}
        except Exception as e:
            logger.error("批准审核门失败: %s", e)
            return {"status": "error", "message": str(e)}

    def _calc_progress(self, template: PipelineTemplate, state) -> int:
        total_phases = len(template.phases)
        if total_phases == 0:
            return 0
        phase_progress = state.current_phase_index / total_phases * 80
        phase = template.phases[state.current_phase_index] if state.current_phase_index < total_phases else None
        if phase and phase.steps:
            step_progress = (state.current_step_index / len(phase.steps)) * (80 / total_phases)
        else:
            step_progress = 0
        return min(99, int(phase_progress + step_progress))

    async def _start_next_phase(self, project_id, template, _state=None):
        try:
            next_state = await self.state_machine.get_state(project_id)
        except Exception:
            return {"status": "ok", "message": "进入下一阶段"}

        if not next_state:
            return {"status": "ok", "message": "进入下一阶段"}

        next_phase_idx = next_state.current_phase_index

        if next_phase_idx < len(template.phases):
            phase = template.phases[next_phase_idx]
            return {
                "status": "ok",
                "message": f"进入阶段: {phase.name}",
                "phase": phase.name,
            }
        return {"status": "completed", "message": "完成"}

    STEP_DEPENDENCIES = {
        "world_builder": ["story_planner"],
        "character_designer": ["world_builder"],
        "relation_network_designer": ["character_designer"],
        "foreshadow_designer": ["world_builder", "character_designer"],
        "foreshadow_reaction": ["foreshadow_designer"],
        "wow_plan_designer": ["foreshadow_designer", "foreshadow_reaction"],
        "chapter_outliner": ["world_builder", "character_designer", "foreshadow_designer"],
        "scene_writer": ["world_builder", "character_designer", "chapter_outliner"],
        "choice_designer": ["chapter_outliner", "scene_writer"],
        "branch_reachability_checker": ["choice_designer"],
        "choice_validity_audit": ["choice_designer"],
        "branch_reachability_audit": ["choice_designer"],
        "consequence_consistency_audit": ["choice_designer"],
        "foreshadow_recovery_audit": ["foreshadow_designer"],
    }

    async def _check_step_dependencies(self, project_id: str, skill: str, state) -> tuple[bool, str]:
        deps = self.STEP_DEPENDENCIES.get(skill, [])
        if not deps:
            return True, ""

        missing = []
        for dep_skill in deps:
            flag_key = f"layer0_{dep_skill}_built"
            if flag_key == "layer0_story_planner_built":
                flag_key = "layer0_story_plan_built"
            elif flag_key == "layer0_world_builder_built":
                flag_key = "layer0_world_built"
            elif flag_key == "layer0_character_designer_built":
                flag_key = "layer0_characters_built"
            elif flag_key == "layer0_foreshadow_designer_built":
                flag_key = "layer0_foreshadows_built"
            elif flag_key == "layer0_chapter_outliner_built":
                flag_key = "layer3_outline_built"
            elif flag_key == "layer0_relation_network_designer_built":
                flag_key = "layer0_relations_built"
            elif flag_key == "layer0_scene_writer_built":
                flag_key = "layer2_scenes_built"
            elif flag_key == "layer0_choice_designer_built":
                flag_key = "layer4_choices_built"
            elif flag_key == "layer0_branch_reachability_checker_built":
                flag_key = "layer4_branch_checked"
            elif flag_key == "layer0_choice_validity_audit_built":
                flag_key = "layer5_choice_audit_built"
            elif flag_key == "layer0_branch_reachability_audit_built":
                flag_key = "layer5_branch_audit_built"
            elif flag_key == "layer0_consequence_consistency_audit_built":
                flag_key = "layer5_consequence_audit_built"
            elif flag_key == "layer0_foreshadow_recovery_audit_built":
                flag_key = "layer5_foreshadow_audit_built"

            found = state.result_data.get(flag_key)
            if not found:
                for k in state.result_data:
                    if k.endswith(f"_{dep_skill}_built") and state.result_data.get(k):
                        found = True
                        break
            if not found:
                missing.append(dep_skill)

        if missing:
            return False, f"步骤 '{skill}' 依赖的前置步骤尚未完成: {', '.join(missing)}。请先执行前置生成步骤。"
        return True, ""

    async def _execute_step(self, project_id: str, template: PipelineTemplate,
                             phase: Phase, step: Step, state) -> dict:
        max_step_retries = 3
        retry_delay_base = 5
        for attempt in range(max_step_retries):
            try:
                dep_ok, dep_msg = await self._check_step_dependencies(project_id, step.skill, state)
                if not dep_ok:
                    logger.error("依赖检查失败: %s", dep_msg)
                    return {
                        "status": "failed",
                        "error": dep_msg,
                        "step": {"agent": step.agent, "skill": step.skill},
                        "dependency_error": True,
                    }

                agent = get_agent(step.agent, self.gateway, self.rag, self.storage)

                payload = self._build_payload(project_id, step, state)

                if step.skill == "scene_writer":
                    try:
                        _narrative_ctx = await build_narrative_context(self.db, project_id)
                        if _narrative_ctx:
                            payload["narrative_context"] = _narrative_ctx
                    except Exception as _ne:
                        logger.warning("加载叙事记忆失败: %s", _ne)

                task = AgentTask(
                    task_id=f"{project_id}_{phase.name}_{step.skill}_{state.current_step_index}",
                    agent_name=step.agent,
                    task_type=step.skill,
                    project_id=project_id,
                    payload=payload,
                    cost_profile=step.cost_profile,
                )

                result = await agent.execute(task)

                if result.status in ("completed", "pass") and step.output_to:
                    await self.state_machine.update_result_data(
                        project_id, step.output_to, result.data
                    )
                    await self._persist_result(project_id, step.skill, result.data, state)

                return {
                    "status": result.status,
                    "data": result.data,
                    "issues": result.issues,
                }

            except Exception as e:
                import traceback
                error_str = str(e)
                is_network_error = any(kw in error_str.lower() for kw in [
                    "timeout", "connection", "connect", "timed out",
                    "connectionreset", "brokenpipe", "network",
                    "all models failed", "read error",
                ])

                if is_network_error and attempt < max_step_retries - 1:
                    delay = retry_delay_base * (2 ** attempt)
                    logger.warning(
                        "步骤 %s.%s 网络错误(第%d次重试)，%ds后重试: %s",
                        step.agent, step.skill, attempt + 1, delay, error_str[:200]
                    )
                    await self._notify_progress(
                        project_id, phase.name,
                        state.current_step_index if state else 0, len(phase.steps),
                        step.agent, step.skill, "retrying",
                        f"网络断连，{delay}s后自动重试({attempt + 1}/{max_step_retries})",
                        self._calc_progress(template, state) if state else 0,
                    )
                    await asyncio.sleep(delay)
                    continue

                logger.error("Step execution failed: %s.%s - %s", step.agent, step.skill, str(e))
                logger.error(traceback.format_exc())

                if step.skill in ("scene_writer", "component_writer", "chapter_writer"):
                    try:
                        logger.info("尝试fallback模式生成: %s.%s", step.agent, step.skill)
                        fallback_result = await self._execute_step_fallback(
                            project_id, template, phase, step, state
                        )
                        if fallback_result:
                            logger.info("fallback模式成功: %s.%s", step.agent, step.skill)
                            return fallback_result
                    except Exception as fb_err:
                        logger.error("fallback模式也失败: %s", str(fb_err)[:200])

                return {
                    "status": "failed",
                    "error": str(e),
                    "step": {"agent": step.agent, "skill": step.skill},
                    "retryable": is_network_error,
                }

        return {"status": "failed", "error": "unexpected code path"}

    async def _persist_result(self, project_id: str, skill: str, data: dict, state):
        try:
            if skill == "story_planner":
                sp_raw = data.get("story_plan", data.get("plan", ""))
                sp_parsed = None
                if isinstance(sp_raw, dict) and sp_raw:
                    sp_parsed = sp_raw
                elif isinstance(sp_raw, str) and len(sp_raw) > 10:
                    sp_parsed = parse_llm_json(sp_raw)
                if not sp_parsed and isinstance(data, dict) and "core_logline" in data:
                    sp_parsed = data
                if not sp_parsed:
                    for v in data.values():
                        if isinstance(v, dict) and "core_logline" in v:
                            sp_parsed = v
                            break
                if sp_parsed and isinstance(sp_parsed, dict):
                    from models.project_config import StoryPlan
                    from services.project_runtime import save_story_plan
                    plan = StoryPlan.from_dict(sp_parsed)
                    await save_story_plan(self.db, project_id, plan)
                    await self.state_machine.update_result_data(project_id, "story_plan", sp_parsed)
                    await self.state_machine.update_result_data(project_id, "layer0_story_plan_built", True)
                    rec_ch = sp_parsed.get("recommended_chapter_count", 0)
                    if isinstance(rec_ch, int) and rec_ch > 0:
                        await self.state_machine.update_result_data(project_id, "chapter_count", rec_ch)
                        twc = state.result_data.get("target_word_count", 50000)
                        wpc_min = max(1500, twc // rec_ch - 1000)
                        wpc_max = max(3000, twc // rec_ch + 2000)
                        await self.state_machine.update_result_data(project_id, "min_words_per_chapter", wpc_min)
                        await self.state_machine.update_result_data(project_id, "max_words_per_chapter", wpc_max)
                    await self._notify_data_changed(project_id, "story_plan_created", {
                        "core_logline": sp_parsed.get("core_logline", ""),
                        "theme_statement": sp_parsed.get("theme_statement", ""),
                    })
                else:
                    logger.warning("story_planner 未生成有效Story Plan数据")
                    await self.state_machine.update_result_data(project_id, "story_plan", {})
                    await self.state_machine.update_result_data(project_id, "layer0_story_plan_built", True)

            elif skill == "world_builder":
                pre_parsed = data.get("world_parsed")
                text = data.get("world_setting", "")
                parsed = pre_parsed if isinstance(pre_parsed, dict) else parse_llm_json(text)
                if parsed and isinstance(parsed, dict):
                    cc_value = parsed.pop("core_contradiction", None)
                    await self.storage.clear_world_config(project_id)
                    await self.storage.save_world_config(project_id, parsed if isinstance(parsed, dict) else {})
                    await self.state_machine.update_result_data(project_id, "world_settings", parsed)
                    await self.state_machine.update_result_data(project_id, "layer0_world_built", True)
                    if cc_value and isinstance(cc_value, str) and cc_value.strip():
                        await self.storage.update_layer0(project_id, "core_contradiction", cc_value.strip())
                        await self.state_machine.update_result_data(project_id, "core_contradiction", cc_value.strip())
                    await self._notify_data_changed(project_id, "world_config_updated", {"has_data": True})
                    for ws_key in ("social_structure", "tech_magic", "geography", "history", "culture", "constraints", "impossible"):
                        ws_val = parsed.get(ws_key) if isinstance(parsed, dict) else None
                        if ws_val and isinstance(ws_val, str) and ws_val.strip():
                            await self._notify_data_changed(project_id, "world_config_updated", {"config_key": ws_key})
                else:
                    logger.warning("world_builder JSON解析失败，尝试直接存储原始文本")
                    if text and len(text) > 50:
                        raw_data = {"raw_world_setting": text}
                        await self.storage.clear_world_config(project_id)
                        await self.storage.save_world_config(project_id, raw_data)
                        await self.state_machine.update_result_data(project_id, "world_settings", raw_data)
                        await self.state_machine.update_result_data(project_id, "layer0_world_built", True)
                        await self._notify_data_changed(project_id, "world_config_updated", {"has_data": True})
                    else:
                        logger.error("world_builder 未生成有效世界观数据，且原始文本过短")
                        raise RuntimeError("world_builder 未生成有效世界观数据")

            elif skill == "character_designer":
                text = data.get("characters", "")
                parsed = parse_llm_json(text)
                chars = None
                if isinstance(parsed, list):
                    chars = parsed
                elif isinstance(parsed, dict):
                    chars = parsed.get("characters", parsed.get("角色", []))
                if isinstance(chars, list) and len(chars) > 0:
                    await self.storage.clear_characters(project_id)
                    await self.storage.create_characters_bulk(project_id, chars)
                    await self.state_machine.update_result_data(project_id, "characters", chars)
                    await self.state_machine.update_result_data(project_id, "layer0_characters_built", True)
                    for c in chars:
                        await self._notify_data_changed(project_id, "character_created",
                                                         {"entity_id": c.get("name", "")})
                else:
                    logger.warning("character_designer JSON解析失败，尝试从原始文本提取角色")
                    raw_text = str(text) if text else ""
                    if len(raw_text) > 100:
                        extracted = self._extract_characters_from_text(raw_text)
                        if extracted and len(extracted) > 0:
                            await self.storage.clear_characters(project_id)
                            await self.storage.create_characters_bulk(project_id, extracted)
                            await self.state_machine.update_result_data(project_id, "characters", extracted)
                            await self.state_machine.update_result_data(project_id, "layer0_characters_built", True)
                            for c in extracted:
                                await self._notify_data_changed(project_id, "character_created",
                                                                 {"entity_id": c.get("name", "")})
                        else:
                            logger.warning("character_designer 文本提取也失败，使用最小角色数据")
                            fallback_chars = [{"name": "主角", "role_type": "protagonist", "core_goal": "待补充", "core_fear": "待补充"}]
                            await self.storage.clear_characters(project_id)
                            await self.storage.create_characters_bulk(project_id, fallback_chars)
                            await self.state_machine.update_result_data(project_id, "characters", fallback_chars)
                            await self.state_machine.update_result_data(project_id, "layer0_characters_built", True)
                    else:
                        raise RuntimeError("character_designer 未生成有效角色数据，无法继续流水线")

            elif skill == "foreshadow_designer":
                fs_raw = data.get("foreshadows", data.get("foreshadow_designs", ""))
                fs_list = None
                if isinstance(fs_raw, list) and len(fs_raw) > 0:
                    fs_list = fs_raw
                elif isinstance(fs_raw, dict):
                    fs_list = fs_raw.get("foreshadows", fs_raw.get("伏笔", []))
                elif isinstance(fs_raw, str) and len(fs_raw) > 10:
                    parsed = parse_llm_json(fs_raw)
                    if isinstance(parsed, list):
                        fs_list = parsed
                    elif isinstance(parsed, dict):
                        fs_list = parsed.get("foreshadows", parsed.get("伏笔", []))

                if not fs_list:
                    for key in ("foreshadows", "foreshadow_designs"):
                        val = data.get(key)
                        if isinstance(val, list) and len(val) > 0:
                            fs_list = val
                            break
                        elif isinstance(val, dict):
                            inner = val.get("foreshadows", val.get("伏笔", []))
                            if isinstance(inner, list) and len(inner) > 0:
                                fs_list = inner
                                break

                if not fs_list:
                    raw_text = ""
                    for v in data.values():
                        if isinstance(v, str) and len(v) > 100:
                            raw_text = v
                            break
                    if raw_text:
                        extracted = self._extract_foreshadows_from_text(raw_text)
                        if extracted:
                            fs_list = extracted

                if isinstance(fs_list, list) and len(fs_list) > 0:
                    await self.storage.clear_foreshadows(project_id)
                    await self.storage.create_foreshadows_bulk(project_id, fs_list)
                    await self.state_machine.update_result_data(project_id, "foreshadows", fs_list)
                    await self.state_machine.update_result_data(project_id, "layer0_foreshadows_built", True)
                    for fs in fs_list:
                        await self._notify_data_changed(project_id, "foreshadow_created",
                                                         {"entity_id": fs.get("name", "")})
                    links_data = data.get("links", [])
                    if not links_data:
                        for v in data.values():
                            if isinstance(v, dict) and isinstance(v.get("links"), list):
                                links_data = v["links"]
                                break
                    if links_data:
                        for link in links_data:
                            source_id = link.get("source_id", "")
                            target_id = link.get("target_id", "")
                            link_type = link.get("link_type", "SUPPORTS")
                            strength = link.get("strength", 0.5)
                            description = link.get("description", "")
                            if source_id and target_id:
                                try:
                                    link_id = str(uuid_mod.uuid4())
                                    now_expr = "datetime('now')" if _IS_SQLITE else "NOW()"
                                    await self.db.execute(sa_text(
                                        f"INSERT INTO foreshadow_links (id, project_id, source_id, target_id, link_type, strength, description, created_at, updated_at) "
                                        f"VALUES (:id, :pid, :sid, :tid, :lt, :st, :desc, {now_expr}, {now_expr})"
                                    ), {"id": link_id, "pid": project_id, "sid": source_id, "tid": target_id, "lt": link_type, "st": strength, "desc": description})
                                except Exception:
                                    pass
                        try:
                            await self.db.commit()
                        except Exception:
                            pass
                else:
                    logger.warning("foreshadow_designer 未生成有效伏笔数据，使用空伏笔列表继续流水线")
                    await self.state_machine.update_result_data(project_id, "foreshadows", [])
                    await self.state_machine.update_result_data(project_id, "layer0_foreshadows_built", True)

            elif skill in ("outline_writer", "chapter_outliner"):
                text = data.get("outline", data.get("chapters", data.get("outlines", "")))
                parsed = parse_llm_json(text)
                ch_list = None
                if isinstance(parsed, list):
                    ch_list = parsed
                elif isinstance(parsed, dict):
                    ch_list = parsed.get("chapters", parsed.get("outline", parsed.get("章节", [])))
                    if not isinstance(ch_list, list):
                        ch_list = None
                if isinstance(ch_list, list) and len(ch_list) > 0:
                    await self.storage.clear_chapters(project_id)
                    await self.storage.create_chapters_bulk(project_id, ch_list)
                    await self.state_machine.update_result_data(project_id, "chapters", ch_list)
                    await self.state_machine.update_result_data(project_id, "layer3_outline_built", True)
                    await self.state_machine.update_result_data(project_id, f"layer{state.current_phase_index}_{skill}_built", True)
                    for ch in ch_list:
                        await self._notify_data_changed(project_id, "chapter_created",
                                                         {"entity_id": ch.get("title", ch.get("标题", ""))})
                    await self._persist_chapter_sections(project_id, ch_list)
                    await self._populate_emotion_curves(project_id)
                else:
                    logger.warning("chapter_outliner 未生成有效章节数据，尝试从原始文本提取")
                    raw_text = str(text) if text else ""
                    if len(raw_text) > 100:
                        extracted = self._extract_chapters_from_text(raw_text)
                        if extracted and len(extracted) > 0:
                            await self.storage.clear_chapters(project_id)
                            await self.storage.create_chapters_bulk(project_id, extracted)
                            await self.state_machine.update_result_data(project_id, "chapters", extracted)
                            await self.state_machine.update_result_data(project_id, "layer3_outline_built", True)
                            await self.state_machine.update_result_data(project_id, f"layer{state.current_phase_index}_{skill}_built", True)
                            for ch in extracted:
                                await self._notify_data_changed(project_id, "chapter_created",
                                                                 {"entity_id": ch.get("title", ch.get("标题", ""))})
                            await self._persist_chapter_sections(project_id, extracted)
                        else:
                            logger.error("chapter_outliner 无法从原始文本提取章节数据")
                            raise RuntimeError("chapter_outliner 未生成有效章节数据，无法继续流水线")
                    else:
                        logger.error("chapter_outliner 原始文本过短: %s", raw_text[:200])
                        raise RuntimeError("chapter_outliner 未生成有效章节数据，无法继续流水线")

            elif skill in ("scene_writer", "component_writer", "chapter_writer", "novel_writer"):
                await self._persist_scene_result(project_id, data, state)

            elif skill == "relation_network_designer":
                text = data.get("relations", "")
                parsed = parse_llm_json(text)
                rel_list = None
                if isinstance(parsed, list):
                    rel_list = parsed
                elif isinstance(parsed, dict):
                    rel_list = parsed.get("relations", parsed.get("关系", []))
                    if not isinstance(rel_list, list):
                        rel_list = None
                if isinstance(rel_list, list) and len(rel_list) > 0:
                    await self.storage.clear_relations(project_id)
                    await self.storage.create_relations_bulk(project_id, rel_list)
                    await self.state_machine.update_result_data(project_id, "relations", rel_list)
                    await self.state_machine.update_result_data(project_id, "layer0_relations_built", True)
                    await self.state_machine.update_result_data(project_id, "layer0_relation_network_designer_built", True)
                    for rel in rel_list:
                        if isinstance(rel, dict):
                            a_name = rel.get("char_a_name", rel.get("char_a", ""))
                            b_name = rel.get("char_b_name", rel.get("char_b", ""))
                            await self._notify_data_changed(project_id, "relation_created",
                                                             {"entity_id": f"{a_name}-{b_name}"})
                else:
                    logger.warning("relation_network_designer 未生成有效关系数据，尝试直接从原始文本提取")
                    raw_text = str(text) if text else ""
                    if len(raw_text) > 50:
                        repaired = parse_llm_json(raw_text)
                        if repaired is not None:
                            if isinstance(repaired, list):
                                rel_list = repaired
                            elif isinstance(repaired, dict):
                                rel_list = repaired.get("relations", repaired.get("关系", []))
                            if isinstance(rel_list, list) and len(rel_list) > 0:
                                await self.storage.clear_relations(project_id)
                                await self.storage.create_relations_bulk(project_id, rel_list)
                                await self.state_machine.update_result_data(project_id, "relations", rel_list)
                                await self.state_machine.update_result_data(project_id, "layer0_relations_built", True)
                                await self.state_machine.update_result_data(project_id, "layer0_relation_network_designer_built", True)
                                logger.info("relation_network_designer 通过截断恢复成功保存 %d 条关系", len(rel_list))
                            else:
                                logger.error("relation_network_designer 截断恢复后仍无有效关系数据")
                                raise RuntimeError("relation_network_designer 未生成有效关系数据，无法继续流水线")
                        else:
                            logger.error("relation_network_designer 无法修复截断JSON")
                            raise RuntimeError("relation_network_designer 未生成有效关系数据，无法继续流水线")
                    else:
                        logger.error("relation_network_designer 原始文本过短: %s", raw_text[:200])
                        raise RuntimeError("relation_network_designer 未生成有效关系数据，无法继续流水线")

            elif skill == "choice_designer":
                await self._persist_choice_designer_result(project_id, data, state)

            elif skill == "branch_reachability_checker":
                await self.state_machine.update_result_data(project_id, "branch_check_result", data)
                await self.state_machine.update_result_data(project_id, "layer4_branch_checked", True)
                await self._notify_data_changed(project_id, "branch_check_completed", {})

            elif skill == "choice_validity_audit":
                await self.state_machine.update_result_data(project_id, "choice_validity_result", data)
                await self.state_machine.update_result_data(project_id, "layer5_choice_audit_built", True)
                await self._notify_data_changed(project_id, "choice_validity_audit_completed", {})

            elif skill == "branch_reachability_audit":
                await self.state_machine.update_result_data(project_id, "branch_reachability_result", data)
                await self.state_machine.update_result_data(project_id, "layer5_branch_audit_built", True)
                await self._notify_data_changed(project_id, "branch_reachability_audit_completed", {})

            elif skill == "consequence_consistency_audit":
                await self.state_machine.update_result_data(project_id, "consequence_consistency_result", data)
                await self.state_machine.update_result_data(project_id, "layer5_consequence_audit_built", True)
                await self._notify_data_changed(project_id, "consequence_consistency_audit_completed", {})

            elif skill == "foreshadow_recovery_audit":
                await self.state_machine.update_result_data(project_id, "foreshadow_recovery_result", data)
                await self.state_machine.update_result_data(project_id, "layer5_foreshadow_audit_built", True)
                await self._notify_data_changed(project_id, "foreshadow_recovery_audit_completed", {})

            elif skill == "foreshadow_reaction":
                reactions = data.get("reactions", data.get("chemical_reactions", data.get("reaction_pairs", [])))
                if isinstance(reactions, list) and len(reactions) > 0:
                    await self.state_machine.update_result_data(project_id, "foreshadow_reactions", reactions)
                reaction_analysis = data.get("reaction_analysis", "")
                if reaction_analysis:
                    await self.state_machine.update_result_data(project_id, "reaction_analysis", reaction_analysis)
                network_strength = data.get("network_strength", data.get("overall_strength", None))
                if network_strength is not None:
                    await self.state_machine.update_result_data(project_id, "network_strength", network_strength)
                await self.state_machine.update_result_data(project_id, "layer0_foreshadow_reaction_built", True)
                await self._notify_data_changed(project_id, "foreshadow_updated", {})

            elif skill == "wow_plan_designer":
                wows = data.get("wows", [])
                if wows:
                    await self.state_machine.update_result_data(project_id, "wow_plans", wows)
                    try:
                        existing_fs = await self.storage.get_foreshadows(project_id)
                        for fs in existing_fs:
                            await self.storage.update_foreshadow(project_id, fs["id"], {
                                "wow_plans": wows,
                            })
                    except Exception:
                        pass
                await self.state_machine.update_result_data(project_id, "layer0_wow_plan_built", True)
                await self._notify_data_changed(project_id, "wow_plans_created", {"count": len(wows)})
                await self._populate_emotion_curves(project_id)

            elif skill == "rag_retriever":
                next_step = data.get("next_step", data)
                await self.state_machine.update_result_data(project_id, "next_step", next_step)
                await self.state_machine.update_result_data(project_id, "layer2_rag_built", True)

            elif skill == "llm_audit":
                await self.state_machine.update_result_data(project_id, "last_audit_result", data)
                audit_key = f"layer{state.current_phase_index}_audit_built"
                await self.state_machine.update_result_data(project_id, audit_key, True)
                await self._notify_data_changed(project_id, "audit_completed", {
                    "overall": data.get("overall", "unknown"),
                    "issues_count": len(data.get("issues", [])),
                })

            elif skill == "state_updater":
                await self.state_machine.update_result_data(project_id, "state_update", data)
                await self.state_machine.update_result_data(project_id, "layer1_state_built", True)
                await self._notify_data_changed(project_id, "state_updated", {
                    "character_updates": data.get("character_updates", {}),
                    "foreshadow_updates": data.get("foreshadow_updates", {}),
                    "relation_updates": data.get("relation_updates", {}),
                })

            skip_flag = f"layer{state.current_phase_index}_{skill}_built"
            if not state.result_data.get(skip_flag):
                await self.state_machine.update_result_data(project_id, skip_flag, True)

        except Exception as e:
            logger.error("持久化 %s 结果失败: %s", skill, str(e))
            raise RuntimeError(f"持久化 {skill} 结果失败: {str(e)[:200]}") from e

    def _extract_chapters_from_text(self, text: str) -> list[dict] | None:
        import re
        chapters = []
        chapter_pattern = re.compile(
            r'(?:第[一二三四五六七八九十百千\d]+章|Chapter\s*\d+|chapter\s*\d+)[\s：:]*([^\n]+)',
            re.IGNORECASE
        )
        matches = list(chapter_pattern.finditer(text))
        if not matches:
            heading_pattern = re.compile(r'^#{1,3}\s+(.+)$', re.MULTILINE)
            matches = list(heading_pattern.finditer(text))
        if not matches:
            return None
        for i, match in enumerate(matches):
            title = match.group(1).strip() if match.lastindex else f"第{i+1}章"
            start = match.end()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            content = text[start:end].strip()
            summary = content[:500] if content else ""
            chapters.append({
                "chapter_number": i + 1,
                "title": title,
                "summary": summary,
                "emotion_target": 5,
                "key_turning_point": "",
                "estimated_word_count": 3000,
            })
        return chapters if chapters else None

    def _extract_characters_from_text(self, text: str) -> list[dict] | None:
        import re
        characters = []
        name_pattern = re.compile(r'(?:姓名|名字|角色名)[：:]\s*([^\n]+)')
        role_pattern = re.compile(r'(?:角色定位|类型|身份)[：:]\s*([^\n]+)')
        goal_pattern = re.compile(r'(?:核心目标|动机|目标)[：:]\s*([^\n]+)')
        blocks = re.split(r'\n\s*\n', text)
        for block in blocks:
            name_match = name_pattern.search(block)
            if not name_match:
                continue
            name = name_match.group(1).strip()
            if len(name) > 20:
                continue
            role_match = role_pattern.search(block)
            goal_match = goal_pattern.search(block)
            characters.append({
                "name": name,
                "role_type": role_match.group(1).strip() if role_match else "supporting",
                "core_goal": goal_match.group(1).strip() if goal_match else "",
                "core_fear": "",
                "language_style": "",
            })
        return characters if characters else None

    def _extract_foreshadows_from_text(self, text: str) -> list[dict] | None:
        import re
        fs_list = []
        name_pattern = re.compile(r'(?:伏笔|线索)[：:]\s*([^\n]+)')
        plant_pattern = re.compile(r'(?:埋设位置|埋设)[：:]\s*([^\n]+)')
        reveal_pattern = re.compile(r'(?:回收)[：:]\s*([^\n]+)')
        blocks = re.split(r'\n\s*\n', text)
        for i, block in enumerate(blocks):
            name_match = name_pattern.search(block)
            if not name_match:
                continue
            name = name_match.group(1).strip()
            if len(name) > 30:
                continue
            plant_match = plant_pattern.search(block)
            reveal_match = reveal_pattern.search(block)
            fs_list.append({
                "name": name,
                "description": block[:200].strip(),
                "plant_chapter": plant_match.group(1).strip() if plant_match else 1,
                "reveal_chapter": reveal_match.group(1).strip() if reveal_match else "",
                "status": "planted",
            })
        return fs_list if fs_list else None

    async def _populate_emotion_curves(self, project_id: str):
        try:
            chapters = await self.storage.get_chapter_outlines(project_id)
            if not chapters:
                return
            await self.storage.clear_emotion_curves(project_id)

            wow_density = 2.0
            try:
                st = await self.state_machine.get_state(project_id)
                if st and st.result_data:
                    wow_density = st.result_data.get("wow_moment_density", 2.0)
            except Exception:
                pass

            wow_types = ["reversal", "revelation", "sacrifice", "triumph", "betrayal"]
            for ch_idx, chapter in enumerate(chapters):
                ch_num = chapter.get("chapter_number", 0)
                ch_title = chapter.get("title", "")
                emotion_val = chapter.get("emotion_target", 5)
                curve_data = {
                    "chapter_number": ch_num,
                    "section_number": 0,
                    "emotion_value": emotion_val,
                    "chapter_label": ch_title,
                    "event_description": chapter.get("core_conflict", chapter.get("summary", "")),
                    "conflict_level": 5,
                    "scene_count": 1,
                }
                if wow_density and wow_density > 0:
                    num_wow = max(1, round(wow_density))
                    wow_type = wow_types[ch_idx % len(wow_types)]
                    curve_data["wow_moment"] = {
                        "type": wow_type,
                        "description": f"第{ch_idx+1}章爽点",
                        "intensity": min(1.0, 0.5 + wow_density * 0.15),
                    }
                await self.storage.create_emotion_curve(project_id, curve_data)
            await self._notify_data_changed(project_id, "emotion_curve_created", {"chapters_processed": len(chapters)})
            logger.info("情感曲线自动填充完成: 项目=%s, 章节数=%d", project_id, len(chapters))
        except Exception as e:
            logger.warning("情感曲线填充失败（非致命）: %s", str(e))

    async def _persist_chapter_sections(self, project_id: str, chapters: list[dict]):
        try:
            chapters_in_db = await self.storage.get_chapter_outlines(project_id)
            ch_id_map = {}
            for ch in chapters_in_db:
                ch_id_map[str(ch.get("chapter_number", ""))] = str(ch.get("id", ""))

            for ch_data in chapters:
                ch_number = ch_data.get("chapter_number", ch_data.get("chapterNumber"))
                if ch_number is None:
                    continue
                chapter_id = ch_id_map.get(str(ch_number))
                if not chapter_id:
                    continue

                sections_data = ch_data.get("sections", [])
                if not isinstance(sections_data, list) or not sections_data:
                    continue

                existing_result = await self.db.execute(
                    sa_text(
                        "SELECT section_number FROM chapter_sections WHERE chapter_id = :chid"
                    ),
                    {"chid": chapter_id},
                )
                existing_numbers = {row[0] for row in existing_result.fetchall()}

                for sec in sections_data:
                    if not isinstance(sec, dict):
                        continue
                    sec_num = sec.get("section_number", sec.get("sectionNumber", 0))
                    if sec_num in existing_numbers:
                        continue

                    sec_id = str(uuid_mod.uuid4())
                    choices_data = sec.get("choices", [])
                    await self.db.execute(
                        sa_text(
                            """INSERT INTO chapter_sections
                            (id, project_id, chapter_id, section_number, title, word_target,
                             emotion_target, scene_ids, choices, foreshadow_tasks,
                             focus_characters, branch_type, summary, status, created_at, updated_at)
                            VALUES (:id, :pid, :chid, :snum, :title, :wt, :et, :sids, :choices,
                                    :ftasks, :fchars, :btype, :summary, 'draft', {_now}, {_now})"""
                            .replace("{_now}", "datetime('now')" if _IS_SQLITE else "NOW()")
                        ),
                        {
                            "id": sec_id,
                            "pid": project_id,
                            "chid": chapter_id,
                            "snum": sec_num,
                            "title": sec.get("title", sec.get("标题", "")),
                            "wt": sec.get("word_target", sec.get("目标字数", 1000)),
                            "et": sec.get("emotion_target", sec.get("情感目标", 5)),
                            "sids": json.dumps(sec.get("scene_ids", []), ensure_ascii=False),
                            "choices": json.dumps(choices_data, ensure_ascii=False) if choices_data else None,
                            "ftasks": json.dumps(sec.get("foreshadow_tasks", []), ensure_ascii=False),
                            "fchars": json.dumps(sec.get("focus_characters", []), ensure_ascii=False),
                            "btype": sec.get("branch_type", sec.get("分支类型", "exploration")),
                            "summary": sec.get("summary", sec.get("摘要", "")),
                        },
                    )

                    if isinstance(choices_data, list):
                        for ci, ch_item in enumerate(choices_data):
                            if not isinstance(ch_item, dict):
                                continue
                            choice_id = str(uuid_mod.uuid4())
                            char_impact = ch_item.get("character_impact", [])
                            await self.db.execute(
                                sa_text(
                                    """INSERT INTO choice_designs
                                    (id, project_id, section_id, choice_number, text,
                                     consequence_direct, consequence_indirect, consequence_long_term,
                                     character_impact, is_hidden, hidden_condition,
                                     moral_alignment, branch_target, created_at, updated_at)
                                    VALUES (:id, :pid, :sid, :cnum, :text,
                                            :cd, :ci, :clt,
                                            :charimp, :hidden, :hcond,
                                            :moral, :btarget, {_now}, {_now})"""
                                    .replace("{_now}", "datetime('now')" if _IS_SQLITE else "NOW()")
                                ),
                                {
                                    "id": choice_id,
                                    "pid": project_id,
                                    "sid": sec_id,
                                    "cnum": ci + 1,
                                    "text": ch_item.get("text", ""),
                                    "cd": ch_item.get("consequence_direct", ""),
                                    "ci": ch_item.get("consequence_indirect", ""),
                                    "clt": ch_item.get("consequence_long_term", ""),
                                    "charimp": json.dumps(char_impact, ensure_ascii=False),
                                    "hidden": 1 if ch_item.get("is_hidden", False) else 0,
                                    "hcond": ch_item.get("hidden_condition", ""),
                                    "moral": ch_item.get("moral_alignment", "gray"),
                                    "btarget": ch_item.get("branch_target", ""),
                                },
                            )

                await self.db.commit()
                await self._notify_data_changed(project_id, "chapter_sections_created",
                                                 {"chapter_id": chapter_id})

            logger.info("章节节结构持久化完成: 项目=%s, 处理章节数=%d", project_id, len(chapters))
        except Exception as e:
            logger.error("持久化章节节结构失败: %s", str(e))

    async def _persist_choice_designer_result(self, project_id: str, data: dict, state):
        try:
            choices_data = data.get("choices", data.get("choice_designs", []))
            if isinstance(choices_data, str):
                choices_data = parse_llm_json(choices_data)
            if not isinstance(choices_data, list) or not choices_data:
                logger.warning("choice_designer 未生成有效选择数据")
                raise RuntimeError("choice_designer 未生成有效选择数据，无法继续流水线")

            sections_in_db = {}
            sec_result = await self.db.execute(
                sa_text(
                    "SELECT id, chapter_id, section_number FROM chapter_sections WHERE project_id = :pid"
                ),
                {"pid": project_id},
            )
            for row in sec_result.fetchall():
                sections_in_db[str(row[2])] = str(row[0])

            created_count = 0
            for choice in choices_data:
                if not isinstance(choice, dict):
                    continue

                section_ref = choice.get("section_id", choice.get("section_number", ""))
                section_id = None
                if section_ref in sections_in_db:
                    section_id = sections_in_db[section_ref]
                else:
                    for sid in sections_in_db.values():
                        section_id = sid
                        break

                if not section_id:
                    logger.warning("choice_designer: 未找到对应节，跳过选择 %s", choice.get("text", "")[:50])
                    continue

                existing_choice = await self.db.execute(
                    sa_text(
                        "SELECT id FROM choice_designs WHERE section_id = :sid AND choice_number = :cnum"
                    ),
                    {"sid": section_id, "cnum": choice.get("choice_number", 1)},
                )
                if existing_choice.fetchone():
                    continue

                choice_id = str(uuid_mod.uuid4())
                char_impact = choice.get("character_impact", [])
                await self.db.execute(
                    sa_text(
                        """INSERT INTO choice_designs
                        (id, project_id, section_id, choice_number, text,
                         consequence_direct, consequence_indirect, consequence_long_term,
                         character_impact, is_hidden, hidden_condition,
                         moral_alignment, branch_target, created_at, updated_at)
                        VALUES (:id, :pid, :sid, :cnum, :text,
                                :cd, :ci, :clt,
                                :charimp, :hidden, :hcond,
                                :moral, :btarget, {_now}, {_now})"""
                        .replace("{_now}", "datetime('now')" if _IS_SQLITE else "NOW()")
                    ),
                    {
                        "id": choice_id,
                        "pid": project_id,
                        "sid": section_id,
                        "cnum": choice.get("choice_number", 1),
                        "text": choice.get("text", ""),
                        "cd": choice.get("consequence_direct", ""),
                        "ci": choice.get("consequence_indirect", ""),
                        "clt": choice.get("consequence_long_term", ""),
                        "charimp": json.dumps(char_impact, ensure_ascii=False),
                        "hidden": 1 if choice.get("is_hidden", False) else 0,
                        "hcond": choice.get("hidden_condition", ""),
                        "moral": choice.get("moral_alignment", "gray"),
                        "btarget": choice.get("branch_target", ""),
                    },
                )
                created_count += 1

            await self.db.commit()
            await self.state_machine.update_result_data(project_id, "choice_designs", choices_data)
            await self.state_machine.update_result_data(project_id, "layer4_choices_built", True)
            await self._notify_data_changed(project_id, "choice_designs_created",
                                             {"count": created_count})
            logger.info("互动选择持久化完成: 项目=%s, 创建选择数=%d", project_id, created_count)
        except Exception as e:
            logger.error("持久化互动选择结果失败: %s", str(e))
            await self.state_machine.update_result_data(project_id, "layer4_choices_built", True)

    async def _persist_scene_result(self, project_id: str, data: dict, state):
        scene_id = data.get("scene_id")
        scene_plan = state.result_data.get("next_step", {}) if state else {}
        planned_chapter_id = scene_plan.get("chapter_id", "")
        planned_scene_code = scene_plan.get("scene_code", "")
        planned_chapter_number = scene_plan.get("chapter_number")
        planned_scene_num = scene_plan.get("scene_num")

        if not scene_id:
            chapters = await self.storage.get_chapter_outlines(project_id)
            if chapters:
                pending_scene = await self._get_next_pending_scene(project_id, chapters)
                if pending_scene:
                    scene_id = str(pending_scene.get("id", ""))

        narration = data.get("narration", "")
        dialogue = data.get("dialogue", [])
        actions = data.get("actions", [])
        foreshadow_ops = data.get("foreshadow_ops", [])
        choices = data.get("choices", [])
        causal_chain = data.get("causal_chain", {})
        emotion_level = data.get("emotion_level", 5)
        characters_involved = data.get("characters_involved", [])

        if isinstance(dialogue, list):
            dialogue_word_count = sum(len(d.get("text", "")) for d in dialogue if isinstance(d, dict))
        else:
            dialogue_word_count = 0

        if isinstance(actions, list):
            actions_word_count = sum(len(str(a)) for a in actions)
        else:
            actions_word_count = 0

        word_count = len(narration) + dialogue_word_count + actions_word_count

        if scene_id:
            try:
                existing = await self.storage.get_scene(project_id, scene_id)
                if existing:
                    existing_scene_code = existing.get("scene_code", scene_id)
                    content = {
                        "narration": narration,
                        "dialogue": dialogue,
                        "actions": actions,
                        "foreshadow_ops": foreshadow_ops,
                        "choices": choices,
                        "causal_chain": causal_chain,
                    }
                    await self.storage.save_scene_draft(scene_id, content)

                    audit_passed = state.result_data.get("last_audit_result", {}).get("overall") == "pass" if state else False
                    if audit_passed:
                        await self.db.execute(
                            sa_text("UPDATE scenes SET status = 'finalized' WHERE id = :sid"),
                            {"sid": scene_id},
                        )
                        await self.db.commit()

                    if emotion_level:
                        await self.db.execute(
                            sa_text(
                                "UPDATE scenes SET emotion_level = :el WHERE id = :sid"
                            ),
                            {"el": emotion_level, "sid": scene_id},
                        )
                        await self.db.commit()

                    if characters_involved:
                        await self.db.execute(
                            sa_text(
                                "UPDATE scenes SET characters_involved = :ci WHERE id = :sid"
                            ),
                            {"ci": json.dumps(characters_involved, ensure_ascii=False), "sid": scene_id},
                        )
                        await self.db.commit()

                    await self._track_word_count(project_id, state, scene_id, word_count)
                    await self._notify_data_changed(project_id, "scene_updated",
                                                     {"entity_id": scene_id})
                    await self._index_scene_to_rag(project_id, scene_id, existing_scene_code, narration, dialogue, actions, characters_involved)
                    await self._sync_foreshadow_states(project_id, scene_id, foreshadow_ops)
                    try:
                        _scp = [narration]
                        if isinstance(dialogue, list):
                            _scp.extend(f"{d.get('char', '?')}: {d.get('text', '')}" for d in dialogue if isinstance(d, dict))
                        elif dialogue:
                            _scp.append(str(dialogue))
                        if isinstance(actions, list):
                            _scp.extend(str(a) for a in actions)
                        elif actions:
                            _scp.append(str(actions))
                        await extract_and_update_memory(self.db, project_id, scene_id, str(existing.get("chapter_id") or planned_chapter_id), "\n".join(_scp))
                    except Exception as _me:
                        logger.warning("叙事记忆提取失败: %s", _me)
                    return
            except Exception as e:
                logger.warning("更新已有场景失败: %s, 尝试创建新场景", e)

        try:
            chapters = await self.storage.get_chapter_outlines(project_id)
            if not chapters:
                logger.warning("无章节大纲，无法创建场景")
                return

            cfg = await self.storage.get_project_config(project_id) or {}
            scenes_per_chapter_max = cfg.get("scenes_per_chapter_max", 6)

            if planned_chapter_id and planned_scene_code:
                chapter_id = planned_chapter_id
                scene_code = planned_scene_code
                chapter = next((ch for ch in chapters if str(ch.get("id", "")) == planned_chapter_id), None)
                if chapter:
                    ch_num = chapter.get("chapter_number", planned_chapter_number if planned_chapter_number else 0)
                else:
                    ch_num = planned_chapter_number if planned_chapter_number else 0
                existing_scenes = await self.storage.get_scenes_by_chapter(project_id, chapter_id)
                scene_num = len(existing_scenes) + 1
                await self.state_machine.update_result_data(
                    project_id, "current_chapter_index", scene_plan.get("current_chapter_index", 0)
                )
            else:
                current_ch_idx = state.result_data.get("current_chapter_index", 0)

                while current_ch_idx < len(chapters):
                    ch = chapters[current_ch_idx]
                    ch_id = str(ch.get("id", ""))
                    existing = await self.storage.get_scenes_by_chapter(project_id, ch_id)
                    if len(existing) < scenes_per_chapter_max:
                        break
                    current_ch_idx += 1

                if current_ch_idx >= len(chapters):
                    current_ch_idx = len(chapters) - 1

                chapter = chapters[current_ch_idx]
                chapter_id = str(chapter.get("id", ""))

                await self.state_machine.update_result_data(
                    project_id, "current_chapter_index", current_ch_idx
                )

                existing_scenes = await self.storage.get_scenes_by_chapter(project_id, chapter_id)
                scene_num = len(existing_scenes) + 1
                ch_num = chapter.get("chapter_number", current_ch_idx + 1)
                scene_code = f"CH{ch_num:03d}_S{scene_num:03d}"

            scene_type = data.get("scene_type", "dialogue")
            location = data.get("location", "")
            weather = data.get("weather", "")

            new_scene_id = str(uuid_mod.uuid4())
            await self.db.execute(
                sa_text(
                    """
                    INSERT INTO scenes (id, project_id, chapter_id, scene_code, scene_type,
                        location, weather, narration, dialogue, actions, foreshadow_ops,
                        choices, causal_chain, emotion_level, characters_involved, status)
                    VALUES (:id, :pid, :chid, :scode, :stype, :loc, :weather,
                        :narr, :dlg, :acts, :fsops, :choices, :causal, :emolvl, :charinv, 'draft')
                    """
                ),
                {
                    "id": new_scene_id,
                    "pid": project_id,
                    "chid": chapter_id,
                    "scode": scene_code,
                    "stype": scene_type,
                    "loc": location,
                    "weather": weather,
                    "narr": narration,
                    "dlg": json.dumps(dialogue, ensure_ascii=False) if isinstance(dialogue, list) else str(dialogue),
                    "acts": json.dumps(actions, ensure_ascii=False) if isinstance(actions, list) else str(actions),
                    "fsops": json.dumps(foreshadow_ops, ensure_ascii=False) if isinstance(foreshadow_ops, list) else str(foreshadow_ops),
                    "choices": json.dumps(choices, ensure_ascii=False) if isinstance(choices, list) else str(choices),
                    "causal": json.dumps(causal_chain, ensure_ascii=False) if isinstance(causal_chain, dict) else str(causal_chain),
                    "emolvl": emotion_level,
                    "charinv": json.dumps(characters_involved, ensure_ascii=False) if isinstance(characters_involved, list) else str(characters_involved),
                },
            )
            await self.db.commit()

            data["scene_id"] = new_scene_id
            await self._track_word_count(project_id, state, new_scene_id, word_count)
            await self._notify_data_changed(project_id, "scene_created",
                                             {"entity_id": new_scene_id})
            await self._index_scene_to_rag(project_id, new_scene_id, scene_code, narration, dialogue, actions, characters_involved)
            await self._sync_foreshadow_states(project_id, new_scene_id, foreshadow_ops)
            try:
                _scp = [narration]
                if isinstance(dialogue, list):
                    _scp.extend(f"{d.get('char', '?')}: {d.get('text', '')}" for d in dialogue if isinstance(d, dict))
                elif dialogue:
                    _scp.append(str(dialogue))
                if isinstance(actions, list):
                    _scp.extend(str(a) for a in actions)
                elif actions:
                    _scp.append(str(actions))
                await extract_and_update_memory(self.db, project_id, new_scene_id, chapter_id, "\n".join(_scp))
            except Exception as _me:
                logger.warning("叙事记忆提取失败: %s", _me)
        except Exception as e:
            logger.warning("创建新场景失败: %s", e)

    async def _index_scene_to_rag(self, project_id: str, scene_id: str, scene_code: str,
                                   narration: str, dialogue, actions, characters_involved):
        try:
            dialogue_text = ""
            if isinstance(dialogue, list):
                dialogue_text = "\n".join(
                    f"{d.get('char', '?')}: {d.get('text', '')}" for d in dialogue if isinstance(d, dict)
                )
            elif dialogue:
                dialogue_text = str(dialogue)

            actions_text = ""
            if isinstance(actions, list):
                actions_text = "\n".join(str(a) for a in actions)
            elif actions:
                actions_text = str(actions)

            chars_text = ", ".join(characters_involved) if isinstance(characters_involved, list) else ""

            full_text = f"场景 {scene_code}\n{chars_text}\n{narration}\n{dialogue_text}\n{actions_text}"
            indexer = RAGIndexer(self.db)
            await indexer.index_content(
                project_id=project_id,
                content_type="scene",
                content_id=scene_id,
                text=full_text,
                metadata={"scene_code": scene_code},
            )
        except Exception as e:
            logger.warning("RAG索引场景 %s 失败: %s", scene_code, e)

    async def _sync_foreshadow_states(self, project_id: str, scene_id: str, foreshadow_ops):
        if not foreshadow_ops:
            return
        if isinstance(foreshadow_ops, str):
            try:
                foreshadow_ops = json.loads(foreshadow_ops)
            except (json.JSONDecodeError, TypeError):
                return
        if not isinstance(foreshadow_ops, list) or not foreshadow_ops:
            return
        try:
            from core.agent.state_manager import VALID_FS_TRANSITIONS, _FS_OP_TO_STATUS
            for op in foreshadow_ops:
                if not isinstance(op, dict):
                    continue
                fs_id = op.get("fs_id") or op.get("fs_code")
                operation = op.get("op", op.get("operation", ""))
                if not fs_id or operation not in ("plant", "reinforce", "reveal"):
                    continue
                current = await self.storage.get_foreshadow(project_id, str(fs_id))
                if not current:
                    all_fs = await self.storage.get_foreshadows(project_id)
                    for f in all_fs:
                        if f.get("fs_code") == str(fs_id):
                            current = f
                            break
                current_status = current.get("current_status", "design") if current else "design"
                if operation not in VALID_FS_TRANSITIONS.get(current_status, set()):
                    logger.warning("伏笔 %s 非法状态转换: %s → %s", fs_id, current_status, operation)
                    continue
                new_status = _FS_OP_TO_STATUS.get(operation, operation)
                update_data: dict[str, object] = {"current_status": new_status}
                if operation == "reinforce" and current:
                    old_count = current.get("reinforce_count", 0) or 0
                    update_data["reinforce_count"] = int(old_count if isinstance(old_count, (int, float, str)) else 0) + 1
                    reinforce_scenes = list(current.get("reinforce_scenes", []) or [])
                    if scene_id and scene_id not in reinforce_scenes:
                        reinforce_scenes.append(scene_id)
                    update_data["reinforce_scenes"] = json.dumps(reinforce_scenes, ensure_ascii=False)
                elif operation == "plant":
                    if scene_id:
                        update_data["plant_scene_id"] = scene_id
                elif operation == "reveal":
                    if scene_id:
                        update_data["reveal_scene_id"] = scene_id
                await self.storage.update_foreshadow_state(str(fs_id), update_data)
                logger.info("伏笔状态同步: %s %s → %s", fs_id, current_status, new_status)
        except Exception as e:
            logger.warning("伏笔状态同步失败: %s", str(e))

    async def _reindex_all_content(self, project_id: str):
        try:
            indexer = RAGIndexer(self.db)
            await indexer.reindex_project(project_id)
            logger.info("项目 %s 全量RAG重索引完成", project_id)
        except Exception as e:
            logger.warning("项目 %s RAG重索引失败: %s", project_id, e)

    async def _track_word_count(self, project_id: str, state, scene_id: str, count: int):
        total_words = state.result_data.get("total_written_words", 0) + count
        await self.state_machine.update_result_data(
            project_id, "total_written_words", total_words
        )
        target = state.result_data.get("target_word_count", 50000)
        pct = (total_words / target * 100) if target > 0 else 0
        logger.info("字数追踪: 场景%s +%d字 → 累计%d/%d字 (%.1f%%)",
                     scene_id[:8], count, total_words, target, pct)

    async def _get_next_pending_scene(self, project_id: str,
                                       chapters: list) -> Optional[dict]:
        for ch in chapters:
            ch_id = str(ch.get("id", ""))
            scenes = await self.storage.get_scenes_by_chapter(project_id, ch_id)
            for sc in scenes:
                if sc.get("status") in ("draft", None, ""):
                    return sc
        return None

    async def _notify_data_changed(self, project_id: str, event_type: str, data: dict):
        try:
            await self._ws().broadcast_to_project(project_id, {
                "type": event_type,
                **data,
                "timestamp": datetime.now(UTC).isoformat(),
            })
            if event_type in ("character_created", "character_updated", "character_deleted",
                              "world_config_updated",
                              "scene_created", "scene_updated", "scene_deleted", "scene_finalized",
                              "chapter_created", "chapter_updated", "chapter_deleted",
                              "foreshadow_created", "foreshadow_updated", "foreshadow_deleted",
                              "relation_created", "relation_updated", "relation_deleted",
                              "choice_designs_created"):
                await self._ws().broadcast_to_project(project_id, {
                    "type": "data_sync_required",
                    "event_type": event_type,
                    "timestamp": datetime.now(UTC).isoformat(),
                })
        except Exception:
            pass

    def _build_payload(self, project_id: str, step: Step, state) -> dict:
        payload = {}

        intent_data = state.result_data.get("intent_analysis") or state.result_data.get("layer0", {}).get("intent_analysis")
        search_data = state.result_data.get("search_results") or state.result_data.get("layer0", {}).get("search_results")
        if intent_data:
            payload["intent_analysis"] = intent_data
        if search_data:
            payload["search_results"] = search_data

        payload["project_id"] = project_id

        for source in step.input_from:
            if source == "user_input":
                payload["project_id"] = project_id
                payload["user_requirements"] = state.result_data.get("user_requirements", "")
                payload["genre"] = state.result_data.get("genre", "")
                payload["style"] = state.result_data.get("style", "")
                payload["core_contradiction"] = state.result_data.get("core_contradiction", "")
                payload["target_word_count"] = state.result_data.get("target_word_count", 50000)
                payload["chapter_count"] = state.result_data.get("chapter_count", 10)
                payload["world_depth"] = state.result_data.get("world_building_depth", 5)
                payload["character_depth"] = state.result_data.get("character_depth_target", 5)
                payload["character_count"] = state.result_data.get("character_dynamic_count", state.result_data.get("character_count", 15))
                payload["plot_complexity"] = state.result_data.get("plot_complexity", 5)
                payload["min_words_per_chapter"] = state.result_data.get("min_words_per_chapter", 2000)
                payload["max_words_per_chapter"] = state.result_data.get("max_words_per_chapter", 8000)
                payload["core_truth"] = state.result_data.get("core_truth", "")
                payload["theme"] = state.result_data.get("theme", "")
                payload["tone"] = state.result_data.get("tone", "neutral")
                payload["scenes_per_chapter_min"] = state.result_data.get("scenes_per_chapter_min", 3)
                payload["scenes_per_chapter_max"] = state.result_data.get("scenes_per_chapter_max", 6)
                payload["total_written_words"] = state.result_data.get("total_written_words", 0)
            elif source == "layer0":
                layer0_data = state.result_data.get("layer0", {})
                payload["layer0"] = layer0_data
                payload["world_settings"] = state.result_data.get("world_settings", {})
                payload["characters"] = state.result_data.get("characters", [])
                payload["relations"] = state.result_data.get("relations", [])
                payload["foreshadows"] = state.result_data.get("foreshadows", [])
                payload["character_count"] = state.result_data.get("character_dynamic_count", state.result_data.get("character_count", 15))
                payload["target_word_count"] = state.result_data.get("target_word_count", 50000)
                payload["chapter_count"] = state.result_data.get("chapter_count", 10)
                payload["genre"] = state.result_data.get("genre", "")
                payload["style"] = state.result_data.get("style", "")
                payload["core_contradiction"] = state.result_data.get("core_contradiction", "")
                payload["world_depth"] = state.result_data.get("world_building_depth", 5)
                payload["character_depth"] = state.result_data.get("character_depth_target", 5)
                payload["plot_complexity"] = state.result_data.get("plot_complexity", 5)
                payload["core_truth"] = state.result_data.get("core_truth", "")
                payload["theme"] = state.result_data.get("theme", "")
                payload["tone"] = state.result_data.get("tone", "neutral")
                payload["scenes_per_chapter_min"] = state.result_data.get("scenes_per_chapter_min", 3)
                payload["scenes_per_chapter_max"] = state.result_data.get("scenes_per_chapter_max", 6)
            elif source == "layer1":
                payload["layer1"] = state.result_data.get("layer1", {})
                payload["character_states"] = state.result_data.get("characters", [])
            elif source == "layer2":
                payload["layer2"] = state.result_data.get("layer2", {})
            elif source == "layer3":
                payload["layer3"] = state.result_data.get("layer3", {})
                payload["chapters"] = state.result_data.get("chapters", [])
            elif source == "layer4":
                payload["layer4"] = state.result_data.get("layer4", {})
                payload["choice_designs"] = state.result_data.get("choice_designs", [])
                payload["branch_check_result"] = state.result_data.get("branch_check_result", {})
            elif source == "layer5":
                payload["layer5"] = state.result_data.get("layer5", {})
                payload["choice_validity_result"] = state.result_data.get("choice_validity_result", {})
                payload["branch_reachability_result"] = state.result_data.get("branch_reachability_result", {})
                payload["consequence_consistency_result"] = state.result_data.get("consequence_consistency_result", {})
                payload["foreshadow_recovery_result"] = state.result_data.get("foreshadow_recovery_result", {})
            elif source == "next_step":
                payload["previous_result"] = state.result_data.get("next_step", {})
                payload["project_id"] = project_id
                payload["target_word_count"] = state.result_data.get("target_word_count", 50000)
                payload["chapter_count"] = state.result_data.get("chapter_count", 10)
                payload["total_written_words"] = state.result_data.get("total_written_words", 0)
                payload["current_chapter_index"] = state.result_data.get("current_chapter_index", 0)
                payload["scenes_per_chapter_min"] = state.result_data.get("scenes_per_chapter_min", 3)
                payload["scenes_per_chapter_max"] = state.result_data.get("scenes_per_chapter_max", 6)
                payload["world_settings"] = state.result_data.get("world_settings", {})
                payload["characters"] = state.result_data.get("characters", [])
                payload["foreshadows"] = state.result_data.get("foreshadows", [])
                payload["chapters"] = state.result_data.get("chapters", [])
                payload["genre"] = state.result_data.get("genre", "")
                payload["style"] = state.result_data.get("style", "")
                payload["core_contradiction"] = state.result_data.get("core_contradiction", "")
                payload["theme"] = state.result_data.get("theme", "")
                payload["tone"] = state.result_data.get("tone", "neutral")
                payload["world_depth"] = state.result_data.get("world_building_depth", 5)
                payload["character_depth"] = state.result_data.get("character_depth_target", 5)
                payload["plot_complexity"] = state.result_data.get("plot_complexity", 5)
            else:
                if source in state.result_data:
                    payload[source] = state.result_data[source]

        payload["project_id"] = project_id
        payload["audit_fix_instructions"] = state.result_data.get("audit_fix_instructions", "")
        payload["revision_mode"] = state.result_data.get("revision_mode", False)
        payload["existing_scene_content"] = state.result_data.get("existing_scene_content", {})

        if step.skill in ("choice_designer", "branch_designer", "interaction_designer"):
            for _k in ("target_ending_count", "max_branch_depth"):
                if _k not in payload and _k in (state.result_data or {}):
                    payload[_k] = state.result_data[_k]

        if step.skill in ("emotion_curve_designer", "chapter_outliner"):
            for _k in ("wow_moment_density", "chapter_count"):
                if _k not in payload and _k in (state.result_data or {}):
                    payload[_k] = state.result_data[_k]

        story_plan_data = state.result_data.get("story_plan", {})
        if story_plan_data and step.skill != "story_planner":
            payload["story_plan_context"] = {
                "core_logline": story_plan_data.get("core_logline", ""),
                "theme_statement": story_plan_data.get("theme_statement", ""),
                "character_arcs": story_plan_data.get("character_arcs", []),
                "plot_nodes": story_plan_data.get("plot_nodes", []),
                "foreshadow_routes": story_plan_data.get("foreshadow_routes", []),
                "emotion_curve_plan": story_plan_data.get("emotion_curve_plan", []),
                "choice_philosophy": story_plan_data.get("choice_philosophy", ""),
            }

        return payload

    async def _execute_step_fallback(self, project_id: str, template: PipelineTemplate,
                                      phase: Phase, step: Step, state) -> dict | None:
        try:
            agent = get_agent(step.agent, self.gateway, self.rag, self.storage)
            payload = self._build_payload(project_id, step, state)
            payload["fallback_mode"] = True
            payload["force_prose_format"] = True

            task = AgentTask(
                task_id=f"{project_id}_{phase.name}_{step.skill}_fallback_{state.current_step_index}",
                agent_name=step.agent,
                task_type=step.skill,
                project_id=project_id,
                payload=payload,
                cost_profile="economy",
            )

            result = await agent.execute(task)

            if result.status in ("completed", "pass"):
                if step.output_to:
                    await self.state_machine.update_result_data(
                        project_id, step.output_to, result.data
                    )
                    await self._persist_result(project_id, step.skill, result.data, state)

                data = result.data if isinstance(result.data, dict) else {}
                data["_fallback_generated"] = True
                data["_quality"] = "draft"

                return {
                    "status": result.status,
                    "data": data,
                    "issues": result.issues or ["fallback模式生成"],
                }

            return None
        except Exception as e:
            logger.warning("fallback模式执行失败: %s", str(e)[:200])
            return None
