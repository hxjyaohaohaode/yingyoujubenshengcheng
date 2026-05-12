import json
import logging
import os
import subprocess
from typing import Optional

from config import GIT_REPO_PATH

logger = logging.getLogger(__name__)


class GitDocumentManager:
    def __init__(self, project_id: str):
        self.project_id = project_id
        self.repo_path = os.path.join(GIT_REPO_PATH, project_id)
        self.scripts_dir = os.path.join(self.repo_path, "scripts")

    def _ensure_repo(self):
        os.makedirs(self.scripts_dir, exist_ok=True)
        if not os.path.exists(os.path.join(self.repo_path, ".git")):
            try:
                subprocess.run(
                    ["git", "init"], cwd=self.repo_path,
                    capture_output=True, timeout=10, check=True,
                )
                subprocess.run(
                    ["git", "config", "user.email", "script-engine@local"],
                    cwd=self.repo_path, capture_output=True, timeout=5,
                )
                subprocess.run(
                    ["git", "config", "user.name", "Script Engine"],
                    cwd=self.repo_path, capture_output=True, timeout=5,
                )
            except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError) as e:
                logger.warning("Git init failed: %s", e)

    def write_scene(self, scene_id: str, content: dict) -> str:
        self._ensure_repo()
        filepath = os.path.join(self.scripts_dir, f"{scene_id}.yaml")
        try:
            import yaml
            yaml_content = yaml.dump(content, allow_unicode=True, default_flow_style=False)
        except ImportError:
            yaml_content = json.dumps(content, ensure_ascii=False, indent=2)

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(yaml_content)

        commit_hash = self._git_commit(f"场景定稿: {scene_id}", [filepath])
        return commit_hash

    def _git_commit(self, message: str, filepaths: list[str]) -> str:
        try:
            for fp in filepaths:
                subprocess.run(
                    ["git", "add", os.path.relpath(fp, self.repo_path)],
                    cwd=self.repo_path, capture_output=True, timeout=10,
                )
            result = subprocess.run(
                ["git", "commit", "-m", message],
                cwd=self.repo_path, capture_output=True, timeout=15,
            )
            if result.returncode == 0:
                hash_result = subprocess.run(
                    ["git", "rev-parse", "HEAD"],
                    cwd=self.repo_path, capture_output=True, timeout=5,
                )
                return hash_result.stdout.decode().strip()[:12]
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError) as e:
            logger.warning("Git commit failed: %s", e)
        return ""

    def get_scene(self, scene_id: str) -> Optional[dict]:
        filepath = os.path.join(self.scripts_dir, f"{scene_id}.yaml")
        if not os.path.exists(filepath):
            return None
        with open(filepath, "r", encoding="utf-8") as f:
            raw = f.read()
        try:
            import yaml
            return yaml.safe_load(raw)
        except ImportError:
            return json.loads(raw)

    def get_commit_log(self, limit: int = 20) -> list[dict]:
        try:
            result = subprocess.run(
                ["git", "log", f"-{limit}", "--pretty=format:%h|%s|%ai"],
                cwd=self.repo_path, capture_output=True, timeout=10,
            )
            if result.returncode != 0:
                return []
            lines = result.stdout.decode().strip().split("\n")
            entries = []
            for line in lines:
                parts = line.split("|", 2)
                if len(parts) == 3:
                    entries.append({
                        "hash": parts[0],
                        "message": parts[1],
                        "date": parts[2],
                    })
            return entries
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return []
