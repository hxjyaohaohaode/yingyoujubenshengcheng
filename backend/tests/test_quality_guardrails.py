import json
import sys
import types
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

BACKEND_DIR = Path(__file__).resolve().parents[1]
backend_path = str(BACKEND_DIR)
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

from api.ai import _call_and_parse_json
from core.pipeline.executor import PipelineExecutor
from core.pipeline.state_machine import PipelineStatus
from core.pipeline.template import Phase, PipelineTemplate, Step
from tasks.scene_audit import _run_single_checker


class AIStrictJsonParseTestCase(unittest.IsolatedAsyncioTestCase):
    async def test_call_and_parse_json_raises_when_salvage_disabled(self):
        with patch("api.ai._call_agent", new=AsyncMock(return_value="not-json")):
            with self.assertRaises(json.JSONDecodeError):
                await _call_and_parse_json(
                    "write.prose",
                    "system",
                    "user",
                    allow_salvage=False,
                )


class SceneAuditGuardrailTestCase(unittest.TestCase):
    def test_missing_checker_fails_closed(self):
        fake_module = types.SimpleNamespace()

        with patch("builtins.__import__", return_value=fake_module):
            result = _run_single_checker("spatiotemporal", {})

        self.assertFalse(result["pass"])
        self.assertIn("无法完成质量校验", result["detail"])


class PipelineExecutorGuardrailTestCase(unittest.IsolatedAsyncioTestCase):
    async def test_advance_marks_pipeline_failed_without_advancing_step(self):
        executor = PipelineExecutor(db=None, gateway=None, rag=None, storage=None)
        executor._notify_progress = AsyncMock()
        executor._notify_agent_status = AsyncMock()
        executor._execute_step = AsyncMock(return_value={
            "status": "failed",
            "error": "agent boom",
        })

        state = SimpleNamespace(
            template_name="demo",
            status=PipelineStatus.RUNNING,
            current_phase_index=0,
            current_step_index=0,
            result_data={},
            error_message="",
        )

        executor.state_machine = SimpleNamespace(
            get_state=AsyncMock(return_value=state),
            append_result=AsyncMock(),
            advance_step=AsyncMock(),
            mark_failed=AsyncMock(),
            transition=AsyncMock(),
            advance_phase=AsyncMock(),
        )

        template = PipelineTemplate(
            name="demo",
            description="demo",
            phases=[
                Phase(
                    name="phase-1",
                    steps=[Step(agent="creator", skill="scene_writer")],
                )
            ],
        )

        with patch("core.pipeline.template_loader.get_template", return_value=template):
            result = await executor.advance("project-1")

        self.assertEqual(result["status"], "failed")
        executor.state_machine.mark_failed.assert_awaited_once_with("project-1", "agent boom")
        executor.state_machine.advance_step.assert_not_awaited()
        executor.state_machine.append_result.assert_awaited_once()

    async def test_advance_returns_cancelled_when_state_already_cancelled(self):
        executor = PipelineExecutor(db=None, gateway=None, rag=None, storage=None)
        executor.state_machine = SimpleNamespace(
            get_state=AsyncMock(return_value=SimpleNamespace(
                template_name="demo",
                status=PipelineStatus.CANCELLED,
                current_phase_index=0,
                current_step_index=0,
                result_data={},
                error_message="用户取消",
            ))
        )

        result = await executor.advance("project-1")

        self.assertEqual(result["status"], "cancelled")
        self.assertEqual(result["message"], "用户取消")

    async def test_auto_audit_scene_fails_closed_on_exception(self):
        executor = PipelineExecutor(db=None, gateway=None, rag=None, storage=None)

        with patch("core.pipeline.executor.get_agent", side_effect=RuntimeError("audit boom")):
            result = await executor._auto_audit_scene(
                "project-1",
                {"scene_id": "scene-1"},
                SimpleNamespace(result_data={}),
            )

        self.assertEqual(result["overall"], "fail")
        self.assertIn("自动审计执行失败", result["issues"][0])


if __name__ == "__main__":
    unittest.main()
