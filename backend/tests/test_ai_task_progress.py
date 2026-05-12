import sys
import unittest
from unittest.mock import patch
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
backend_path = str(BACKEND_DIR)
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

import tasks
from api.ai import get_task_progress


class AITaskProgressEndpointTestCase(unittest.IsolatedAsyncioTestCase):
    async def test_returns_persisted_progress_fields(self):
        payload = {
            "task_id": "task-123",
            "status": "running",
            "progress": 66,
            "message": "处理中",
            "agent_name": "审计Agent",
            "task_name": "全项目审计",
        }

        with patch.object(tasks, "get_progress", return_value=payload):
            result = await get_task_progress("task-123")

        self.assertEqual(result["task_id"], "task-123")
        self.assertEqual(result["status"], "running")
        self.assertEqual(result["progress"], 66)
        self.assertEqual(result["estimated_time"], "预计 3 秒")

    async def test_returns_unknown_when_progress_lookup_fails(self):
        with patch.object(tasks, "get_progress", side_effect=RuntimeError("boom")):
            result = await get_task_progress("task-404")

        self.assertEqual(result["task_id"], "task-404")
        self.assertEqual(result["status"], "unknown")
        self.assertEqual(result["progress"], 0)
        self.assertEqual(result["estimated_time"], "任务未找到")


if __name__ == "__main__":
    unittest.main()
