from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from models.project import Project
from models.project_config import ProjectConfig, StoryPlan


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


async def get_story_plan(db: AsyncSession, project_id: str) -> StoryPlan | None:
    result = await db.execute(
        select(ProjectConfig).where(ProjectConfig.project_id == project_id)
    )
    config = result.scalar_one_or_none()
    if not config:
        return None
    return StoryPlan.from_dict(config.story_plan)


async def save_story_plan(db: AsyncSession, project_id: str, plan: StoryPlan) -> StoryPlan:
    result = await db.execute(
        select(ProjectConfig).where(ProjectConfig.project_id == project_id)
    )
    config = result.scalar_one_or_none()
    if not config:
        return None
    config.story_plan = plan.to_dict()
    flag_modified(config, "story_plan")
    await db.commit()
    return plan


async def update_story_plan(db: AsyncSession, project_id: str, plan: StoryPlan) -> StoryPlan:
    result = await db.execute(
        select(ProjectConfig).where(ProjectConfig.project_id == project_id)
    )
    config = result.scalar_one_or_none()
    if not config:
        return None
    existing = StoryPlan.from_dict(config.story_plan)
    updated = StoryPlan(
        core_logline=plan.core_logline if plan.core_logline else existing.core_logline,
        theme_statement=plan.theme_statement if plan.theme_statement else existing.theme_statement,
        character_arcs=plan.character_arcs if plan.character_arcs else existing.character_arcs,
        plot_nodes=plan.plot_nodes if plan.plot_nodes else existing.plot_nodes,
        foreshadow_routes=plan.foreshadow_routes if plan.foreshadow_routes else existing.foreshadow_routes,
        emotion_curve_plan=plan.emotion_curve_plan if plan.emotion_curve_plan else existing.emotion_curve_plan,
        choice_philosophy=plan.choice_philosophy if plan.choice_philosophy else existing.choice_philosophy,
    )
    config.story_plan = updated.to_dict()
    flag_modified(config, "story_plan")
    await db.commit()
    return updated
