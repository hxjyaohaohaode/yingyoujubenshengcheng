import sys
import unittest
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
backend_path = str(BACKEND_DIR)
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

import tasks


class FakeRedis:
    def __init__(self):
        self.storage = {}

    def setex(self, key, ttl, value):
        self.storage[key] = value

    def get(self, key):
        return self.storage.get(key)


class TaskProgressStoreTestCase(unittest.TestCase):
    def setUp(self):
        self.original_store = tasks._progress_store
        self.original_failed = tasks._progress_store_failed
        self.original_progress = dict(tasks.TASK_PROGRESS)
        tasks._progress_store = FakeRedis()
        tasks._progress_store_failed = False
        tasks.TASK_PROGRESS.clear()

    def tearDown(self):
        tasks._progress_store = self.original_store
        tasks._progress_store_failed = self.original_failed
        tasks.TASK_PROGRESS.clear()
        tasks.TASK_PROGRESS.update(self.original_progress)

    def test_get_progress_reads_back_from_persistent_store(self):
        tasks.update_progress("task-1", 42, "running", "处理中", agent_name="审计Agent", task_name="全剧审计")
        tasks.TASK_PROGRESS.clear()

        progress = tasks.get_progress("task-1")

        self.assertEqual(progress["progress"], 42)
        self.assertEqual(progress["status"], "running")
        self.assertEqual(progress["agent_name"], "审计Agent")
        self.assertEqual(progress["task_name"], "全剧审计")

    def test_get_progress_returns_default_when_missing(self):
        progress = tasks.get_progress("missing-task")

        self.assertEqual(progress["status"], "unknown")
        self.assertEqual(progress["progress"], 0)


if __name__ == "__main__":
    unittest.main()
