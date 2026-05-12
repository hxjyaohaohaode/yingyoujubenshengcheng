import sys
import unittest
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
backend_path = str(BACKEND_DIR)
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

from models.project import Project
from models.project_config import ProjectConfig
from services.project_runtime import ProjectRuntimeView


class ProjectRuntimeViewTestCase(unittest.TestCase):
    def test_runtime_view_prefers_project_config_fields(self):
        project = Project(name="长篇项目", description="desc", status="writing")
        config = ProjectConfig(
            genre="悬疑",
            style="冷峻",
            writing_style="克制",
            target_word_count=1500000,
            core_contradiction="真相与谎言",
            theme="代价",
        )

        runtime = ProjectRuntimeView(project=project, config=config)

        self.assertEqual(runtime.name, "长篇项目")
        self.assertEqual(runtime.genre, "悬疑")
        self.assertEqual(runtime.style, "冷峻")
        self.assertEqual(runtime.target_word_count, 1500000)
        self.assertEqual(runtime.current_phase, "writing")
        self.assertEqual(runtime.core_truth, "真相与谎言")

    def test_runtime_view_falls_back_to_safe_defaults(self):
        project = Project(name="短篇项目", status=None)
        runtime = ProjectRuntimeView(project=project, config=None)

        self.assertEqual(runtime.genre, "")
        self.assertEqual(runtime.style, "")
        self.assertEqual(runtime.target_word_count, 50000)
        self.assertEqual(runtime.current_phase, "draft")
        self.assertEqual(runtime.core_truth, "")


if __name__ == "__main__":
    unittest.main()
