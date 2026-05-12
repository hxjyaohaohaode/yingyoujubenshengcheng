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

from core.gateway.client import ModelGateway
from core.rag.retriever import RAGRetriever
from core.rag.indexer import RAGIndexer
from core.storage.service import StorageService
from core.agent.base import AgentTask
from core.agent.registry import get_agent
from .template import PipelineTemplate, Step, Phase
from .state_machine import PipelineStateMachine, PipelineStatus

from config import DATABASE_URL

_IS_SQLITE = DATABASE_URL.startswith("sqlite")

logger = logging.getLogger(__name__)

AUTO_RUN_GLOBAL_TIMEOUT = 12 * 3600
AUTO_RUN_STEP_TIMEOUT = 600
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
                    # 找到场景写作步骤的索引，直接跳到该步骤而不是从头开始
                    scene_writer_idx = None
                    for idx, s in enumerate(phase.steps):
                        if s.skill in ("scene_writer", "component_writer", "chapter_writer", "novel_writer"):
                            scene_writer_idx = idx
                            break
                    next_step = scene_writer_idx if scene_writer_idx is not None else 0
                    await self.state_machine.set_step(project_id, state.current_phase_index, next_step)
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
                scene_count = len(scenes)
                total_scenes_needed += scenes_per_chapter_max
                total_scenes_written += scene_count

                if scene_count < scenes_per_chapter_min:
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
                        continue
                    else:
                        logger.warning("场景审计失败已达最大重试次数(%d)", MAX_AUDIT_RETRIES)
                        return result

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
            if hasattr(audit_result, 'data') and isinstance(audit_result.data, dict):
                data = audit_result.data
            elif isinstance(audit_result, dict):
                data = audit_result

            checker_results = data.get("phase_a", {})
            llm_results = data.get("phase_b")
            creative_scores = data.get("phase_c")
            issues = data.get("issues", [])
            suggestions = data.get("suggestions", [])

            if hasattr(audit_result, 'issues') and audit_result.issues:
                issues = audit_result.issues

            audit_id = str(_uuid.uuid4())
            now_expr = "datetime('now')" if _IS_SQLITE else "NOW()"

            await self.db.execute(
                __import__("sqlalchemy").text(
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

                    if consecutive_failures < MAX_CONSECUTIVE_FAILURES:
                        wait_seconds = min(30, 5 * consecutive_failures)
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
        "character_designer": "world_builder",
        "relation_network_designer": "character_designer",
        "foreshadow_designer": "world_builder",
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
        "character_designer": ["world_builder"],
        "relation_network_designer": ["character_designer"],
        "foreshadow_designer": ["world_builder", "character_designer"],
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
            if flag_key == "layer0_world_builder_built":
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

            if not state.result_data.get(flag_key):
                missing.append(dep_skill)

        if missing:
            return False, f"步骤 '{skill}' 依赖的前置步骤尚未完成: {', '.join(missing)}。请先执行前置生成步骤。"
        return True, ""

    async def _execute_step(self, project_id: str, template: PipelineTemplate,
                             phase: Phase, step: Step, state) -> dict:
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
            logger.error("Step execution failed: %s.%s - %s", step.agent, step.skill, str(e))
            logger.error(traceback.format_exc())
            return {
                "status": "failed",
                "error": str(e),
                "step": {"agent": step.agent, "skill": step.skill},
            }

    async def _persist_result(self, project_id: str, skill: str, data: dict, state):
        try:
            if skill == "world_builder":
                pre_parsed = data.get("world_parsed")
                text = data.get("world_setting", "")
                parsed = pre_parsed if isinstance(pre_parsed, dict) else self._extract_json(text)
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
                parsed = self._extract_json(text)
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
                    logger.warning("character_designer 未生成有效角色数据")
                    raise RuntimeError("character_designer 未生成有效角色数据，无法继续流水线")

            elif skill == "foreshadow_designer":
                text = data.get("foreshadows", data.get("foreshadow_designs", ""))
                parsed = self._extract_json(text)
                fs_list = None
                if isinstance(parsed, list):
                    fs_list = parsed
                elif isinstance(parsed, dict):
                    fs_list = parsed.get("foreshadows", parsed.get("伏笔", []))
                if isinstance(fs_list, list) and len(fs_list) > 0:
                    await self.storage.clear_foreshadows(project_id)
                    await self.storage.create_foreshadows_bulk(project_id, fs_list)
                    await self.state_machine.update_result_data(project_id, "foreshadows", fs_list)
                    await self.state_machine.update_result_data(project_id, "layer0_foreshadows_built", True)
                    for fs in fs_list:
                        await self._notify_data_changed(project_id, "foreshadow_created",
                                                         {"entity_id": fs.get("name", "")})
                else:
                    logger.warning("foreshadow_designer 未生成有效伏笔数据")
                    raise RuntimeError("foreshadow_designer 未生成有效伏笔数据，无法继续流水线")

            elif skill in ("outline_writer", "chapter_outliner"):
                text = data.get("outline", data.get("chapters", data.get("outlines", "")))
                parsed = self._extract_json(text)
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
                parsed = self._extract_json(text)
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
                        repaired = self._repair_truncated_json(raw_text)
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
                reaction_data = data.get("reactions", data.get("chemical_reactions", ""))
                if reaction_data:
                    await self.state_machine.update_result_data(project_id, "foreshadow_reactions", reaction_data)
                await self.state_machine.update_result_data(project_id, "layer0_foreshadow_reaction_built", True)
                await self._notify_data_changed(project_id, "foreshadow_updated", {})

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
                    __import__("sqlalchemy").text(
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
                        __import__("sqlalchemy").text(
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
                                __import__("sqlalchemy").text(
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
                choices_data = self._extract_json(choices_data)
            if not isinstance(choices_data, list) or not choices_data:
                logger.warning("choice_designer 未生成有效选择数据")
                raise RuntimeError("choice_designer 未生成有效选择数据，无法继续流水线")

            sections_in_db = {}
            sec_result = await self.db.execute(
                __import__("sqlalchemy").text(
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
                    __import__("sqlalchemy").text(
                        "SELECT id FROM choice_designs WHERE section_id = :sid AND choice_number = :cnum"
                    ),
                    {"sid": section_id, "cnum": choice.get("choice_number", 1)},
                )
                if existing_choice.fetchone():
                    continue

                choice_id = str(uuid_mod.uuid4())
                char_impact = choice.get("character_impact", [])
                await self.db.execute(
                    __import__("sqlalchemy").text(
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

                    if emotion_level:
                        await self.db.execute(
                            __import__("sqlalchemy").text(
                                "UPDATE scenes SET emotion_level = :el WHERE id = :sid"
                            ),
                            {"el": emotion_level, "sid": scene_id},
                        )
                        await self.db.commit()

                    if characters_involved:
                        await self.db.execute(
                            __import__("sqlalchemy").text(
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
                __import__("sqlalchemy").text(
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
        except Exception:
            pass

    def _extract_json(self, text) -> dict | list | None:
        if not text or not isinstance(text, str):
            return text if isinstance(text, (dict, list)) else None
        text = text.strip()
        if text.startswith("```json"):
            text = text[7:]
        elif text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
        try:
            start = text.find("{")
            if start == -1:
                start = text.find("[")
            if start >= 0:
                end = text.rfind("}") + 1
                if text[start] == "[":
                    end = text.rfind("]") + 1
                if end > start:
                    return json.loads(text[start:end])
        except json.JSONDecodeError:
            pass
        repaired = self._repair_truncated_json(text)
        if repaired is not None:
            return repaired
        return None

    def _repair_truncated_json(self, text: str) -> dict | list | None:
        if not text:
            return None
        start_obj = text.find("{")
        start_arr = text.find("[")
        if start_obj == -1 and start_arr == -1:
            return None
        is_array = False
        start = -1
        if start_obj == -1:
            start = start_arr
            is_array = True
        elif start_arr == -1:
            start = start_obj
        elif start_arr < start_obj:
            start = start_arr
            is_array = True
        else:
            start = start_obj
        fragment = text[start:]
        if is_array:
            last_complete_obj_end = -1
            depth = 0
            for i, ch in enumerate(fragment):
                if ch == "{":
                    depth += 1
                elif ch == "}":
                    depth -= 1
                    if depth == 0:
                        last_complete_obj_end = i
            if last_complete_obj_end > 0:
                candidate = fragment[:last_complete_obj_end + 1] + "]"
                try:
                    return json.loads(candidate)
                except json.JSONDecodeError:
                    pass
            open_braces = 0
            open_brackets = 0
            in_string = False
            escape_next = False
            for ch in fragment:
                if escape_next:
                    escape_next = False
                    continue
                if ch == "\\":
                    escape_next = True
                    continue
                if ch == '"' and not escape_next:
                    in_string = not in_string
                    continue
                if in_string:
                    continue
                if ch == "{":
                    open_braces += 1
                elif ch == "}":
                    open_braces -= 1
                elif ch == "[":
                    open_brackets += 1
                elif ch == "]":
                    open_brackets -= 1
            closing = ""
            if in_string:
                closing += '"'
            closing += "}" * max(0, open_braces) + "]" * max(0, open_brackets)
            candidate = fragment + closing
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                pass
        else:
            open_braces = 0
            open_brackets = 0
            in_string = False
            escape_next = False
            last_complete_key_pos = -1
            for i, ch in enumerate(fragment):
                if escape_next:
                    escape_next = False
                    continue
                if ch == "\\":
                    escape_next = True
                    continue
                if ch == '"' and not escape_next:
                    in_string = not in_string
                    continue
                if in_string:
                    continue
                if ch == "{":
                    open_braces += 1
                elif ch == "}":
                    open_braces -= 1
                    if open_braces == 0:
                        last_complete_key_pos = i
                elif ch == "[":
                    open_brackets += 1
                elif ch == "]":
                    open_brackets -= 1
            if last_complete_key_pos > 0:
                candidate = fragment[:last_complete_key_pos + 1]
                try:
                    return json.loads(candidate)
                except json.JSONDecodeError:
                    pass
            closing = ""
            if in_string:
                closing += '"'
            closing += "]" * max(0, open_brackets) + "}" * max(0, open_braces)
            candidate = fragment + closing
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                pass
        return None

    def _build_payload(self, project_id: str, step: Step, state) -> dict:
        payload = {}

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

        return payload
