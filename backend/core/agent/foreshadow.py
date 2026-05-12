"""
伏笔 Agent: 从核心真相反推的三层伏笔体系设计。

Skills:
  - foreshadow_designer: 三层伏笔网络设计（write.outline）
  - foreshadow_reaction: 伏笔化学反应分析（reason.complex）
"""

import json
import logging

from core.agent.base import BaseAgent, AgentTask, AgentResult, layer0_value
from core.agent.skill import Skill
from core.agent.registry import register_agent
from services.llm_prompts import build_foreshadow_design_prompt

logger = logging.getLogger(__name__)


def parse_foreshadow_design(text: str) -> dict:
    content = text.strip()
    json_start = content.find("{")
    json_end = content.rfind("}")
    if json_start != -1 and json_end != -1:
        content = content[json_start:json_end + 1]
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        content = content.replace("'", '"').replace("None", "null").replace("True", "true").replace("False", "false")
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            logger.warning("Foreshadow JSON解析失败")
            return {"foreshadows": [], "relations": [], "design_philosophy": "", "revelation_path": [], "stats": {}}


FORESHADOW_DESIGN_SKILL = Skill()
FORESHADOW_DESIGN_SKILL.name = "foreshadow_designer"
FORESHADOW_DESIGN_SKILL.intent = "write.outline"
FORESHADOW_DESIGN_SKILL.model = "ds-v4-pro"
FORESHADOW_DESIGN_SKILL.prompt_template = "{rendered_prompt}"
FORESHADOW_DESIGN_SKILL.output_parser = parse_foreshadow_design

FORESHADOW_REACTION_SKILL = Skill()
FORESHADOW_REACTION_SKILL.name = "foreshadow_reaction"
FORESHADOW_REACTION_SKILL.intent = "reason.complex"
FORESHADOW_REACTION_SKILL.model = "ds-v4-pro"
FORESHADOW_REACTION_SKILL.prompt_template = """分析以下伏笔之间的化学反应——即两个伏笔交织在一起时产生的1+1>2效果。

{foreshadow_data}

请分析:
1. 每条伏笔独立时的功能
2. 伏笔对之间的化学反应
3. 交叉强化形成的冗余与张力
4. 整体伏笔网络的强度评估（1-10）
5. 三层含义之间的递进关系是否合理
6. 伏笔与世界观/角色的关联是否充分

输出JSON格式的分析报告。"""
FORESHADOW_REACTION_SKILL.output_parser = lambda text: {"reaction_analysis": text}


@register_agent
class ForeshadowAgent(BaseAgent):
    name = "foreshadow"
    description = "从核心真相反推的三层伏笔体系设计、伏笔依赖关系管理、伏笔化学反应分析"
    skills = {
        "foreshadow_designer": FORESHADOW_DESIGN_SKILL,
        "foreshadow_reaction": FORESHADOW_REACTION_SKILL,
    }

    def _validate(self, task: AgentTask):
        if not task.project_id:
            raise ValueError("project_id is required")
        if task.task_type not in self.skills:
            raise ValueError(f"Unknown task_type: {task.task_type}")

    async def _build_context(self, task: AgentTask) -> dict:
        project_id = task.project_id
        payload = task.payload

        layer0 = await self.storage.get_layer0(project_id)
        world_config = await self.storage.get_world_config(project_id) or {}
        chars = await self.storage.get_character_states(project_id)
        chapters = await self.storage.get_chapter_outlines(project_id)

        if not chars:
            chars = payload.get("characters", [])
        if not chapters:
            chapters = payload.get("chapters", [])

        core_truth = layer0_value(layer0, "core_truth") or payload.get("core_truth", "")
        core_contradiction = layer0_value(layer0, "core_contradiction") or payload.get("core_contradiction", "")
        chapter_count = len(chapters) if chapters else payload.get("chapter_count", 20)

        world_settings = {}
        for key in ["core_contradiction", "social_structure", "tech_magic", "geography", "history", "culture", "constraints", "impossible"]:
            val = world_config.get(key, "")
            if val and isinstance(val, str) and val.strip():
                world_settings[key] = val

        if not world_settings:
            world_fallback = payload.get("world_settings", "")
            if world_fallback:
                world_settings["core_contradiction"] = world_fallback

        characters = []
        for c in chars or []:
            char_info = {
                "name": c.get("name", "?"),
                "role_type": c.get("role_type", "未设定"),
            }
            if c.get("core_goal"):
                char_info["core_goal"] = c["core_goal"]
            if c.get("core_fear"):
                char_info["core_fear"] = c["core_fear"]
            if c.get("surface_image"):
                char_info["surface_image"] = c["surface_image"]
            if c.get("true_self"):
                char_info["true_self"] = c["true_self"]
            if c.get("dark_secret"):
                char_info["dark_secret"] = c["dark_secret"]
            characters.append(char_info)

        chapter_outlines = []
        for ch in chapters or []:
            ch_info = {
                "chapter_number": ch.get("chapter_number", ch.get("number", "?")),
                "title": ch.get("title", ""),
            }
            summary = ch.get("summary", ch.get("outline", ch.get("core_conflict", "")))
            if summary:
                ch_info["summary"] = summary
            chapter_outlines.append(ch_info)

        system_prompt, user_prompt = build_foreshadow_design_prompt(
            core_truth=core_truth,
            core_contradiction=core_contradiction,
            world_settings=world_settings,
            characters=characters,
            chapter_outlines=chapter_outlines,
            chapter_count=chapter_count,
        )

        rendered_prompt = f"{system_prompt}\n\n{user_prompt}"

        return {"rendered_prompt": rendered_prompt}

    def _select_skill(self, task_type: str) -> Skill:
        return self.skills[task_type]

    async def _post_process(self, task: AgentTask, result: dict):
        if not isinstance(result, dict):
            return

        foreshadows = result.get("foreshadows", [])
        if not foreshadows:
            return

        stats = result.get("stats", {})
        global_count = stats.get("global_count", 0)
        chapter_count = stats.get("chapter_count", 0)
        scene_count = stats.get("scene_count", 0)
        total = global_count + chapter_count + scene_count

        if total == 0:
            for fs in foreshadows:
                tier = fs.get("foreshadow_tier", "chapter")
                if tier == "global":
                    global_count += 1
                elif tier == "chapter":
                    chapter_count += 1
                else:
                    scene_count += 1
            total = global_count + chapter_count + scene_count
            stats = {
                "global_count": global_count,
                "chapter_count": chapter_count,
                "scene_count": scene_count,
                "total_count": total,
            }
            result["stats"] = stats

        core_total = global_count + chapter_count
        if core_total > 0:
            reclaimed = 0
            for fs in foreshadows:
                tier = fs.get("foreshadow_tier", "chapter")
                if tier in ("global", "chapter"):
                    if fs.get("reveal_location") and fs.get("plant_location"):
                        reclaimed += 1
            reclaim_rate = round(reclaimed / core_total * 100, 1)
            stats["reclaim_rate"] = f"{reclaim_rate}%"
            result["stats"] = stats

        if global_count < 5:
            result.setdefault("issues", []).append(
                f"全剧级伏笔数量不足：当前{global_count}条，建议5-8条"
            )
        if chapter_count < 20:
            result.setdefault("issues", []).append(
                f"章节级伏笔数量不足：当前{chapter_count}条，建议20-30条"
            )
