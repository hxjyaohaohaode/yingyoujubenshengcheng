import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

BACKEND_DIR = Path(__file__).resolve().parents[1]
backend_path = str(BACKEND_DIR)
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

from models.project import Project  # noqa: F401
from models.project_config import ProjectConfig  # noqa: F401
from services import task_dispatcher


class TaskDispatcherTestCase(unittest.IsolatedAsyncioTestCase):
    async def test_enqueue_task_creates_queued_record(self):
        db = AsyncMock()
        db.add = MagicMock()
        fake_callable = MagicMock()

        with patch.object(task_dispatcher, "_get_task_callable", return_value=fake_callable), \
             patch("services.task_dispatcher.uuid.uuid4", return_value="task-123"), \
             patch("tasks.update_progress") as update_progress, \
             patch("tasks.push_progress_via_ws") as push_ws:
            result = await task_dispatcher.enqueue_task(
                db,
                project_id="project-1",
                task_type="scene_generation",
                payload={"scene_id": "scene-1"},
                task_kwargs={"project_id": "project-1", "scene_id": "scene-1", "requirements": {}},
            )

        self.assertEqual(result["task_id"], "task-123")
        self.assertEqual(result["status"], "queued")
        db.add.assert_called_once()
        db.commit.assert_awaited_once()
        fake_callable.apply_async.assert_called_once_with(
            task_id="task-123",
            kwargs={"project_id": "project-1", "scene_id": "scene-1", "requirements": {}, "task_id": "task-123"},
        )
        update_progress.assert_called_once()
        push_ws.assert_called_once()

    async def test_enqueue_task_marks_record_failed_when_dispatch_fails(self):
        db = AsyncMock()
        db.add = MagicMock()
        fake_callable = MagicMock()
        fake_callable.apply_async.side_effect = RuntimeError("broker down")

        with patch.object(task_dispatcher, "_get_task_callable", return_value=fake_callable), \
             patch("services.task_dispatcher.uuid.uuid4", return_value="task-789"):
            with self.assertRaises(task_dispatcher.HTTPException) as ctx:
                await task_dispatcher.enqueue_task(
                    db,
                    project_id="project-1",
                    task_type="scene_generation",
                    payload={"scene_id": "scene-1"},
                    task_kwargs={"project_id": "project-1", "scene_id": "scene-1", "requirements": {}},
                )

        self.assertEqual(ctx.exception.status_code, 503)
        task_record = db.add.call_args.args[0]
        self.assertEqual(task_record.id, "task-789")
        self.assertEqual(task_record.status, "failed")
        self.assertIn("任务派发失败", task_record.error_message)
        self.assertEqual(db.commit.await_count, 2)

    async def test_cancel_task_marks_record_cancelled(self):
        db = AsyncMock()
        task = SimpleNamespace(
            id="task-456",
            project_id="project-1",
            assigned_to="创作Agent",
            task_type="scene_generation",
            status="running",
            error_message=None,
            completed_at=None,
        )
        execute_result = MagicMock()
        execute_result.scalar_one_or_none.return_value = task
        db.execute.return_value = execute_result

        with patch("tasks.celery_app.control.revoke") as revoke, \
             patch("tasks.update_progress") as update_progress, \
             patch("tasks.push_progress_via_ws") as push_ws:
            result = await task_dispatcher.cancel_task(db, "task-456")

        self.assertEqual(result["status"], "ok")
        self.assertEqual(task.status, "cancelled")
        revoke.assert_called_once_with("task-456", terminate=True)
        db.commit.assert_awaited_once()
        update_progress.assert_called_once()
        push_ws.assert_called_once()


if __name__ == "__main__":
    unittest.main()
