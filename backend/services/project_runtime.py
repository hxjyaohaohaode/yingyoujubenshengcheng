from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.project import Project
from models.project_config import ProjectConfig


@dataclass(frozen=True)
class ProjectRuntimeView:
    project: Project | None
    config: ProjectConfig | None

    @property
    def name(self) -> str:
        return self.project.name if self.project and self.project.name else "未命名"

    @property
    def description(self) -> str:
        return self.project.description if self.project and self.project.description else ""

    @property
    def genre(self) -> str:
        return self.config.genre if self.config and self.config.genre else ""

    @property
    def style(self) -> str:
        if not self.config:
            return ""
        return self.config.style or self.config.writing_style or ""

    @property
    def target_word_count(self) -> int:
        if not self.config or self.config.target_word_count is None:
            return 50000
        return int(self.config.target_word_count)

    @property
    def current_phase(self) -> str:
        if not self.project or not self.project.status:
            return "draft"
        return self.project.status

    @property
    def core_truth(self) -> str:
        if not self.config:
            return ""
        return self.config.core_contradiction or self.config.theme or ""


async def load_project_runtime(db: AsyncSession, project_id) -> ProjectRuntimeView:
    project_id_str = str(project_id)
    project_result = await db.execute(select(Project).where(Project.id == project_id_str))
    project = project_result.scalar_one_or_none()

    config_result = await db.execute(select(ProjectConfig).where(ProjectConfig.project_id == project_id_str))
    config = config_result.scalar_one_or_none()

    return ProjectRuntimeView(project=project, config=config)
