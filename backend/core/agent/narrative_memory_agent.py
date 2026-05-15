"""
叙事记忆Agent - 场景生成后自动提取关键信息更新全局叙事记忆
"""
from core.agent.base import BaseAgent, AgentTask, AgentResult
from core.agent.skill import Skill
from core.agent.registry import register_agent
from core.narrative.memory_extractor import extract_and_update_memory
from core.narrative.memory_loader import build_narrative_context
from core.narrative.memory_store import get_all_memories_for_context


EXTRACT_MEMORY_SKILL = Skill()
EXTRACT_MEMORY_SKILL.name = "extract_memory"
EXTRACT_MEMORY_SKILL.intent = "planning"
EXTRACT_MEMORY_SKILL.prompt_template = "从场景内容提取角色变化/伏笔推进/新事件/关系变化/世界观揭示"
EXTRACT_MEMORY_SKILL.output_parser = lambda text: {"memory": text}

LOAD_CONTEXT_SKILL = Skill()
LOAD_CONTEXT_SKILL.name = "load_context"
LOAD_CONTEXT_SKILL.intent = "planning"
LOAD_CONTEXT_SKILL.prompt_template = "加载全局叙事记忆上下文"
LOAD_CONTEXT_SKILL.output_parser = lambda text: {"context": text}


@register_agent
class NarrativeMemoryAgent(BaseAgent):
    name = "narrative_memory"
    label = "叙事记忆Agent"
    description = "场景生成后自动提取角色变化/伏笔推进/新事件/关系变化/世界观揭示，更新全局叙事记忆"

    skills = {
        "extract_memory": EXTRACT_MEMORY_SKILL,
        "load_context": LOAD_CONTEXT_SKILL,
    }

    def _validate(self, task: AgentTask):
        if not task.project_id:
            raise ValueError("project_id is required")

    async def _build_context(self, task: AgentTask) -> dict:
        return {"project_id": task.project_id}

    def _select_skill(self, task_type: str) -> Skill:
        return self.skills.get(task_type, EXTRACT_MEMORY_SKILL)

    async def execute(self, task: AgentTask) -> AgentResult:
        self._validate(task)

        db = None
        if hasattr(self.storage, 'db'):
            db = self.storage.db

        if db is None:
            return AgentResult(
                status="failed",
                data={"error": "数据库会话不可用"},
                issues=["无法获取数据库会话"],
            )

        project_id = task.project_id
        scene_id = task.payload.get("scene_id", "")
        chapter_id = task.payload.get("chapter_id", "")
        scene_content = task.payload.get("scene_content", "")

        context = await build_narrative_context(db, project_id)
        result = await extract_and_update_memory(
            db=db,
            project_id=project_id,
            scene_id=scene_id,
            chapter_id=chapter_id,
            scene_content=scene_content,
            current_narrative_context=context,
        )

        return AgentResult(
            status="completed",
            data={
                "project_id": project_id,
                "updated": result.get("updated", {}),
                "summary": result.get("summary", ""),
            },
        )