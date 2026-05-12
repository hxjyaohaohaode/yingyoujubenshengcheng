"""
流程状态机: 管理流水线执行的完整生命周期。

状态枚举: PipelineStatus (not_started/running/waiting_human/completed/failed)
步状态: StepStatus (pending/running/completed/failed/skipped)
"""

import json
import logging
from datetime import datetime, UTC
from enum import Enum
from dataclasses import dataclass, field
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from config import DATABASE_URL

_IS_SQLITE = DATABASE_URL.startswith("sqlite")

logger = logging.getLogger(__name__)


def _coerce_json_container(value, expected_type, default):
    if isinstance(value, expected_type):
        return value
    if value in (None, ""):
        return default
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            logger.warning("Failed to decode pipeline JSON payload")
            return default
        return parsed if isinstance(parsed, expected_type) else default
    return default


class PipelineStatus(Enum):
    NOT_STARTED = "not_started"
    RUNNING = "running"
    WAITING_HUMAN = "waiting_human"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class StepStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class PipelineState:
    project_id: str
    template_name: str = ""
    current_phase_index: int = 0
    current_step_index: int = 0
    status: PipelineStatus = PipelineStatus.NOT_STARTED
    result_data: dict = field(default_factory=dict)
    error_message: str = ""
    task_results: list = field(default_factory=list)
    config: dict = field(default_factory=dict)
    run_id: Optional[str] = None


class PipelineStateMachine:
    """流水线状态机 — 持久化到 pipeline_state 表"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def init(self, project_id: str, template_name: str,
                   config: dict | None = None) -> PipelineState:
        state = PipelineState(
            project_id=project_id,
            template_name=template_name,
            status=PipelineStatus.NOT_STARTED,
            config=config or {},
        )
        await self._save(state)
        return state

    async def get_state(self, project_id: str) -> Optional[PipelineState]:
        result = await self.db.execute(
            text("SELECT * FROM pipeline_state WHERE project_id = :pid"),
            {"pid": project_id},
        )
        row = result.fetchone()
        if not row:
            return None
        cols = result.keys()
        data = dict(zip(cols, row))

        return PipelineState(
            project_id=data["project_id"],
            template_name=data.get("template_name", ""),
            current_phase_index=data.get("current_phase_index", 0),
            current_step_index=data.get("current_step_index", 0),
            status=PipelineStatus(data.get("status", "not_started")),
            result_data=_coerce_json_container(data.get("result_data"), dict, {}),
            error_message=data.get("error_message", ""),
            task_results=_coerce_json_container(data.get("task_results"), list, []),
            config=_coerce_json_container(data.get("config"), dict, {}),
            run_id=data.get("run_id"),
        )

    async def transition(self, project_id: str,
                         target_status: PipelineStatus):
        state = await self.get_state(project_id)
        if not state:
            raise ValueError(f"Pipeline state not found for {project_id}")
        state.status = target_status
        await self._save(state)

    async def advance_step(self, project_id: str):
        state = await self.get_state(project_id)
        if not state:
            raise ValueError(f"Pipeline state not found for {project_id}")
        state.current_step_index += 1
        await self._save(state)

    async def advance_phase(self, project_id: str):
        state = await self.get_state(project_id)
        if not state:
            raise ValueError(f"Pipeline state not found for {project_id}")
        state.current_phase_index += 1
        state.current_step_index = 0
        await self._save(state)

    async def set_step(self, project_id: str, phase: int, step: int):
        state = await self.get_state(project_id)
        if not state:
            raise ValueError(f"Pipeline state not found for {project_id}")
        state.current_phase_index = phase
        state.current_step_index = step
        await self._save(state)

    async def mark_failed(self, project_id: str, error: str):
        state = await self.get_state(project_id)
        if not state:
            raise ValueError(f"Pipeline state not found for {project_id}")
        state.status = PipelineStatus.FAILED
        state.error_message = error
        await self._save(state)

    async def cancel(self, project_id: str, reason: str = ""):
        state = await self.get_state(project_id)
        if not state:
            raise ValueError(f"Pipeline state not found for {project_id}")
        state.status = PipelineStatus.CANCELLED
        state.error_message = reason or "流水线已取消"
        await self._save(state)

    async def approve(self, project_id: str):
        state = await self.get_state(project_id)
        if not state:
            raise ValueError(f"Pipeline state not found for {project_id}")
        state.status = PipelineStatus.RUNNING
        state.error_message = ""
        await self._save(state)

    async def reject(self, project_id: str, reason: str = "", task_key: str | None = None):
        state = await self.get_state(project_id)
        if not state:
            raise ValueError(f"Pipeline state not found for {project_id}")
        state.error_message = reason or "人工审核驳回"
        state.status = PipelineStatus.WAITING_HUMAN
        if task_key:
            results = list(state.task_results)
            for i, tr in enumerate(results):
                if tr.get("key") == task_key:
                    results[i] = {
                        **tr,
                        "status": "rejected",
                        "rejected_at": datetime.now(UTC).isoformat(),
                        "rejection_reason": reason or "人工审核驳回",
                    }
                    break
            state.task_results = results
        result_data = dict(state.result_data)
        result_data["last_rejection_reason"] = reason or "人工审核驳回"
        state.result_data = result_data
        await self._save(state)

    async def handle_rejection(self, project_id: str, task_key: str, reason: str = ""):
        await self.reject(project_id, reason=reason, task_key=task_key)

    async def append_result(self, project_id: str, result: dict):
        state = await self.get_state(project_id)
        if not state:
            raise ValueError(f"Pipeline state not found for {project_id}")
        results = list(state.task_results)
        results.append(result)
        state.task_results = results
        await self._save(state)

    async def update_result_data(self, project_id: str, key: str, value):
        state = await self.get_state(project_id)
        if not state:
            raise ValueError(f"Pipeline state not found for {project_id}")
        rd = dict(state.result_data)
        rd[key] = value
        state.result_data = rd
        await self._save(state)

    async def reset(self, project_id: str):
        state = await self.get_state(project_id)
        if state:
            state.status = PipelineStatus.NOT_STARTED
            state.current_phase_index = 0
            state.current_step_index = 0
            state.error_message = ""
            state.result_data = {}
            state.task_results = []
            state.run_id = None
            await self._save(state)

    async def retry(self, project_id: str):
        """从失败步骤重新开始，保留已完成的结果数据和历史记录"""
        state = await self.get_state(project_id)
        if not state:
            raise ValueError(f"Pipeline state not found for {project_id}")
        if state.status != PipelineStatus.FAILED:
            raise ValueError("只能重试处于失败状态的流水线")
        state.status = PipelineStatus.RUNNING
        state.error_message = ""
        # 将当前失败的步骤标记为 retrying，保留之前的 task_results
        results = list(state.task_results)
        current_key = f"{state.current_phase_index}-{state.current_step_index}"
        for i, tr in enumerate(results):
            if tr.get("key") == current_key and tr.get("status") == "failed":
                results[i] = {**tr, "status": "retrying", "retried_at": datetime.now(UTC).isoformat()}
                break
        state.task_results = results
        await self._save(state)
        return state

    async def rollback_to_step(self, project_id: str, phase_idx: int, step_idx: int):
        state = await self.get_state(project_id)
        if not state:
            raise ValueError(f"Pipeline state not found for {project_id}")
        state.current_phase_index = max(0, phase_idx)
        state.current_step_index = max(0, step_idx)
        state.status = PipelineStatus.RUNNING
        state.error_message = ""

        rolled_back_key = f"{phase_idx}-{step_idx}"
        results = list(state.task_results)
        new_results = []
        for tr in results:
            tr_key = tr.get("key", "")
            tr_phase = int(tr_key.split("-")[0]) if "-" in tr_key else -1
            tr_step = int(tr_key.split("-")[1]) if "-" in tr_key and len(tr_key.split("-")) > 1 else -1
            if tr_phase < phase_idx or (tr_phase == phase_idx and tr_step < step_idx):
                new_results.append(tr)
        new_results.append({
            "key": rolled_back_key,
            "phase": "",
            "agent": "系统",
            "skill": "rollback",
            "status": "retrying",
            "retried_at": datetime.now(UTC).isoformat(),
            "rollback_reason": f"回退到阶段{phase_idx}步骤{step_idx}，后续步骤结果已清除",
        })
        state.task_results = new_results

        artifact_keys_to_clear = []
        for key in list(state.result_data.keys()):
            if key.startswith("layer") and key.endswith("_built"):
                layer_name = key.split("_", 1)[1] if "_" in key else ""
                dep_phase = self._estimate_dep_phase(layer_name)
                if dep_phase is not None and dep_phase >= phase_idx:
                    artifact_keys_to_clear.append(key)

        for key in artifact_keys_to_clear:
            state.result_data.pop(key, None)

        await self._save(state)
        return state

    def _estimate_dep_phase(self, layer_name: str) -> int | None:
        phase_map = {
            "world_built": 0, "characters_built": 0, "foreshadows_built": 0, "relations_built": 0,
            "outline_built": 1, "scenes_built": 2, "choices_built": 2,
            "choice_audit_built": 3, "branch_audit_built": 3,
            "consequence_audit_built": 3, "foreshadow_audit_built": 3,
            "branch_checked": 3,
        }
        return phase_map.get(layer_name)

    async def _save(self, state: PipelineState):
        params = {
            "pid": state.project_id,
            "tpl": state.template_name,
            "cpi": state.current_phase_index,
            "csi": state.current_step_index,
            "st": state.status.value,
            "rd": json.dumps(state.result_data, ensure_ascii=False) if isinstance(state.result_data, dict) else "{}",
            "em": state.error_message,
            "tr": json.dumps(state.task_results, ensure_ascii=False) if isinstance(state.task_results, list) else "[]",
            "cfg": json.dumps(state.config, ensure_ascii=False) if isinstance(state.config, dict) else "{}",
            "rid": state.run_id,
            "now": datetime.now(UTC).isoformat(),
        }
        if _IS_SQLITE:
            existing = await self.db.execute(
                text("SELECT project_id FROM pipeline_state WHERE project_id = :pid"),
                {"pid": state.project_id},
            )
            if existing.fetchone():
                await self.db.execute(
                    text(
                        """
                        UPDATE pipeline_state SET
                            template_name = :tpl, current_phase_index = :cpi,
                            current_step_index = :csi, status = :st,
                            result_data = :rd, error_message = :em,
                            task_results = :tr, config = :cfg,
                            run_id = :rid, updated_at = :now
                        WHERE project_id = :pid
                        """
                    ),
                    params,
                )
            else:
                await self.db.execute(
                    text(
                        """
                        INSERT INTO pipeline_state
                            (project_id, template_name, current_phase_index, current_step_index,
                             status, result_data, error_message, task_results, config, run_id, updated_at)
                        VALUES
                            (:pid, :tpl, :cpi, :csi, :st, :rd, :em, :tr, :cfg, :rid, :now)
                        """
                    ),
                    params,
                )
        else:
            await self.db.execute(
                text(
                    """
                    INSERT INTO pipeline_state
                        (project_id, template_name, current_phase_index, current_step_index,
                         status, result_data, error_message, task_results, config, run_id, updated_at)
                    VALUES
                        (:pid, :tpl, :cpi, :csi, :st, :rd, :em, :tr, :cfg, :rid, :now)
                    ON CONFLICT (project_id) DO UPDATE SET
                        template_name = EXCLUDED.template_name,
                        current_phase_index = EXCLUDED.current_phase_index,
                        current_step_index = EXCLUDED.current_step_index,
                        status = EXCLUDED.status,
                        result_data = EXCLUDED.result_data,
                        error_message = EXCLUDED.error_message,
                        task_results = EXCLUDED.task_results,
                        config = EXCLUDED.config,
                        run_id = EXCLUDED.run_id,
                        updated_at = EXCLUDED.updated_at
                    """
                ),
                params,
            )
        await self.db.commit()
