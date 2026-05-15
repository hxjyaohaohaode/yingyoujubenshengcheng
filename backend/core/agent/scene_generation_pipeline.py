"""
统一场景生成流水线 — 串联叙事记忆→规划→写作→精炼→记忆更新

流水线: NarrativeContextAgent → ScenePlannerAgent → SceneWriterAgent → SceneRefinerAgent → NarrativeMemoryAgent
"""
import json
import logging
from dataclasses import dataclass, field
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from core.gateway.client import get_gateway
from core.narrative.memory_loader import build_narrative_context
from core.narrative.coherence_checker import run_full_coherence_check, CoherenceReport
from core.narrative.revision_orchestrator import refine_scene
from core.narrative.memory_extractor import extract_and_update_memory
from core.narrative.word_budget import count_chinese_words, update_actual_words, is_within_budget

logger = logging.getLogger(__name__)

MAX_REFINE_ITERATIONS = 3


@dataclass
class SceneGenerationResult:
    scene_id: str
    narration: str = ""
    dialogue: list = field(default_factory=list)
    actions: list = field(default_factory=list)
    foreshadow_ops: list = field(default_factory=list)
    choices: list = field(default_factory=list)
    causal_chain: dict = field(default_factory=dict)
    emotion_level: int = 5
    word_count: int = 0
    target_words: int = 0
    within_budget: bool = False
    coherence_report: Optional[CoherenceReport] = None
    refine_iterations: int = 0
    memory_updated: dict = field(default_factory=dict)
    status: str = "completed"


class SceneGenerationPipeline:
    """统一场景生成流水线 — 协调6步生成+精炼+记忆更新流程"""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.gateway = get_gateway()

    async def generate(
        self,
        project_id: str,
        scene_id: str,
        chapter_id: str,
        context: dict,
        user_requirements: str = "",
        target_words: int = 3000,
    ) -> SceneGenerationResult:
        """
        执行完整的场景生成流水线。

        参数:
            project_id: 项目ID
            scene_id: 场景ID
            chapter_id: 章节ID
            context: 场景上下文（包含角色/世界观/前序场景/章节信息/伏笔任务等）
            user_requirements: 用户额外需求
            target_words: 目标字数
        """
        result = SceneGenerationResult(
            scene_id=scene_id,
            target_words=target_words,
        )

        try:
            # Step 1: 加载全局叙事记忆
            logger.info("[Pipeline] Step 1/6: 加载叙事记忆...")
            narrative_context = await build_narrative_context(self.db, project_id)

            # Step 2: 构建场景规划（将叙事记忆注入到生成上下文）
            logger.info("[Pipeline] Step 2/6: 构建场景规划上下文...")
            enriched_context = self._enrich_context(context, narrative_context, user_requirements, target_words)

            # Step 3: 生成场景内容
            logger.info("[Pipeline] Step 3/6: AI生成场景内容...")
            scene_content = await self._generate_scene_content(
                project_id, scene_id, chapter_id, enriched_context, target_words
            )
            if not scene_content:
                result.status = "failed"
                return result

            narration = scene_content.get("narration", "")
            result.narration = narration
            result.dialogue = scene_content.get("dialogue", [])
            result.actions = scene_content.get("actions", [])
            result.foreshadow_ops = scene_content.get("foreshadow_ops", [])
            result.choices = scene_content.get("choices", [])
            result.causal_chain = scene_content.get("causal_chain", {})
            result.emotion_level = scene_content.get("emotion_level", 5)

            # Step 4: 5层连贯性检查
            logger.info("[Pipeline] Step 4/6: 执行5层连贯性检查...")
            report = await run_full_coherence_check(
                db=self.db,
                project_id=project_id,
                scene_id=scene_id,
                scene_content=narration,
                narrative_context=narrative_context,
            )
            result.coherence_report = report

            # Step 5: 迭代精炼（如需要）
            if not report.all_passed:
                logger.info("[Pipeline] Step 5/6: 执行迭代精炼（未通过层数: %d）...",
                            sum(1 for c in report.checks if not c.passed))
                refine_result = await refine_scene(
                    db=self.db,
                    project_id=project_id,
                    scene_id=scene_id,
                    scene_content=narration,
                    max_iterations=MAX_REFINE_ITERATIONS,
                )
                result.refine_iterations = refine_result.iterations
                if refine_result.refined_content:
                    result.narration = refine_result.refined_content
                    result.coherence_report = CoherenceReport(
                        project_id=project_id,
                        scene_id=scene_id,
                        checks=refine_result.checks_after,
                        all_passed=refine_result.all_passed,
                        total_score=sum(c.score for c in refine_result.checks_after) / max(len(refine_result.checks_after), 1),
                    )
            else:
                logger.info("[Pipeline] Step 5/6: 5层检查全部通过，跳过精炼")

            # Step 6: 提取并更新叙事记忆
            logger.info("[Pipeline] Step 6/6: 提取场景关键信息并更新叙事记忆...")
            final_content = result.narration
            memory_result = await extract_and_update_memory(
                db=self.db,
                project_id=project_id,
                scene_id=scene_id,
                chapter_id=chapter_id,
                scene_content=final_content,
                current_narrative_context=narrative_context,
            )
            result.memory_updated = memory_result

            # 字数统计
            result.word_count = count_chinese_words(final_content)
            result.within_budget = is_within_budget(result.word_count, target_words)
            if not result.within_budget and self.gateway:
                logger.info("[Pipeline] 字数(%d)超出范围(目标%d)，尝试压缩/扩展...",
                            result.word_count, target_words)
                adjusted = await self._adjust_word_count(
                    final_content, target_words, result.word_count
                )
                if adjusted:
                    result.narration = adjusted
                    result.word_count = count_chinese_words(adjusted)
                    result.within_budget = is_within_budget(result.word_count, target_words)

            # 更新字数预算
            try:
                await update_actual_words(self.db, scene_id, result.word_count)
            except Exception as e:
                logger.warning("字数预算更新失败: %s", e)

            result.status = "completed"
            logger.info("[Pipeline] 场景生成完成: 字数=%d, 5层通过=%s, 精炼轮数=%d",
                        result.word_count, result.coherence_report.all_passed if result.coherence_report else False,
                        result.refine_iterations)

        except Exception as e:
            logger.error("[Pipeline] 场景生成失败: %s", e, exc_info=True)
            result.status = "failed"

        return result

    def _enrich_context(
        self,
        context: dict,
        narrative_context: str,
        user_requirements: str,
        target_words: int,
    ) -> dict:
        """将叙事记忆注入到生成上下文中"""
        enriched = dict(context)

        if narrative_context:
            enriched["narrative_context"] = narrative_context
            enriched["_narrative_context"] = narrative_context

        if user_requirements:
            enriched["user_requirements"] = user_requirements

        word_instruction = f"目标字数：{target_words}字（允许±20%浮动，即{int(target_words * 0.8)}-{int(target_words * 1.2)}字）"
        enriched["_word_constraint"] = word_instruction
        enriched["is_pipeline_mode"] = True

        return enriched

    async def _generate_scene_content(
        self,
        project_id: str,
        scene_id: str,
        chapter_id: str,
        context: dict,
        target_words: int,
    ) -> Optional[dict]:
        """调用LLM生成场景内容"""
        if not self.gateway:
            logger.error("[Pipeline] Gateway不可用，无法生成场景")
            return None

        narrative_context = context.get("_narrative_context", "")

        prompt = self._build_scene_prompt(context, narrative_context, target_words)

        try:
            response = await self.gateway.invoke(
                intent="write.prose",
                messages=[{"role": "user", "content": prompt}],
                cost_profile="quality",
                max_tokens=64000,
                temperature=0.7,
                use_cache=False,
            )

            content = response.content
            return self._parse_scene_response(content)

        except Exception as e:
            logger.error("[Pipeline] LLM调用失败: %s", e)
            return None

    def _build_scene_prompt(
        self,
        context: dict,
        narrative_context: str,
        target_words: int,
    ) -> str:
        """构建注入叙事记忆的增强Prompt"""

        word_min = int(target_words * 0.8)
        word_max = int(target_words * 1.2)

        genre = context.get("genre", "奇幻")
        style = context.get("style", "叙事")
        sub_genre = context.get("sub_genre", context.get("project_type", ""))
        theme = context.get("theme", "")
        core_contradiction = context.get("core_contradiction", "")
        narrative_pov = context.get("narrative_pov", "第三人称")
        world_settings = context.get("world_settings", "")
        character_states = context.get("character_states", "")
        previous_scene = context.get("previous_scene", "")
        chapter_info = context.get("chapter_info", "")
        scene_code = context.get("scene_code", "")
        scene_type = context.get("scene_type", "transition")
        emotion_target = context.get("emotion_target", 5)
        location = context.get("location", "")
        weather = context.get("weather", "")
        foreshadow_tasks = context.get("foreshadow_tasks", "无特殊伏笔任务")
        rag_context = context.get("rag_context", "")
        user_requirements = context.get("user_requirements", "")
        style_guide = context.get("style_guide", "")
        project_brief = context.get("project_brief", "")

        parts = []

        parts.append(f"你是一位{genre}题材的{style}风格专业编剧，专精互动影游剧本创作。")

        # 风格指南
        if style_guide:
            parts.append(f"\n【写作风格要求】\n{style_guide}")

        # 叙事记忆（核心新增）
        if narrative_context:
            parts.append(f"\n{narrative_context}")

        parts.append(f"""
【项目核心约束】
{project_brief or f'题材: {genre}, 风格: {style}, 子类型: {sub_genre}'}

【创作锚点】
- 主题: {theme}
- 核心矛盾: {core_contradiction}
- 叙事视角: {narrative_pov}

【世界观设定】
{world_settings or '参见项目设定'}

【角色详细档案】
{character_states or '参见项目设定'}

【前序场景全文】
{previous_scene or '（无前序场景，这是第一个场景）'}

【章节上下文】
{chapter_info or '参见章节大纲'}

【本场景任务】
- 场景编号: {scene_code}
- 场景类型: {scene_type}
- 情感目标: {emotion_target}/10
- 地点: {location}
- 天气: {weather}
- 伏笔任务: {foreshadow_tasks}

【字数要求】
目标字数: {target_words}字（必须在{word_min}-{word_max}字之间）
当前已生成字数: 0字，需要生成约{target_words}字的完整场景。

【参考素材】
{rag_context or '无额外参考素材'}

{"【用户额外需求】" + chr(10) + user_requirements if user_requirements else ""}

【输出要求】
请输出 JSON 格式:
{{
  "narration": "完整的小说式场景叙述正文（{word_min}-{word_max}字）",
  "dialogue": [
    {{"char": "角色名", "text": "台词", "subtext": "潜台词"}}
  ],
  "actions": ["关键动作"],
  "foreshadow_ops": [
    {{"fs_id": "伏笔ID", "op": "plant/reinforce/reveal", "content": "内容", "text_implementation": "实现方式"}}
  ],
  "choices": [
    {{"id": "A", "text": "选项", "consequence_direct": "直接后果", "consequence_indirect": "间接后果", "consequence_long_term": "远期后果", "moral_alignment": "good/neutral/evil/gray"}}
  ],
  "causal_chain": {{
    "preconditions": ["前置条件"],
    "catalyst": "催化剂",
    "direct_result": "直接结果",
    "indirect_result": "间接结果",
    "far_result": "远期结果"
  }},
  "emotion_level": 1-10
}}

【绝对禁止】
- narration写成摘要或大纲
- 对白写成间接叙述
- 忽略叙事记忆中记录的角色当前状态、活跃伏笔、最近事件
- 违反世界观规则
- 字数严重偏离目标
""")
        return "\n".join(parts)

    def _parse_scene_response(self, content: str) -> Optional[dict]:
        """解析LLM返回的JSON场景内容"""
        if not content:
            return None

        text = content.strip()

        if text.startswith("```"):
            lines = text.split("\n")
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            text = "\n".join(lines)

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        import re
        match = re.search(r'\{[^{}]*"narration"[^{}]*\}', text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass

        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group())
                if "narration" in data:
                    return data
            except json.JSONDecodeError:
                pass

        return {"narration": text, "dialogue": [], "actions": [], "foreshadow_ops": [],
                "choices": [], "causal_chain": {}, "emotion_level": 5}

    async def _adjust_word_count(
        self, content: str, target_words: int, actual_words: int
    ) -> Optional[str]:
        """调整字数到目标范围"""
        if not self.gateway:
            return None

        if actual_words < target_words * 0.8:
            prompt = f"""以下场景内容字数不足（目标{target_words}字，实际{actual_words}字）。
请在保持原有情节、角色、伏笔不变的前提下，扩展内容使其达到{target_words}字左右。
可以增加环境描写、角色心理活动、对白的潜台词、动作细节。

【原文】
{content}

请直接输出扩展后的完整场景内容："""
        elif actual_words > target_words * 1.2:
            prompt = f"""以下场景内容字数过多（目标{target_words}字，实际{actual_words}字）。
请在保持核心情节、角色互动、伏笔操作不变的前提下，精简内容使其压缩到{target_words}字左右。
删除冗余描写、合并相似对白、精简次要动作。

【原文】
{content}

请直接输出精简后的完整场景内容："""
        else:
            return None

        try:
            response = await self.gateway.invoke(
                intent="write.prose",
                messages=[{"role": "user", "content": prompt}],
                cost_profile="balanced",
                max_tokens=64000,
                temperature=0.3,
                use_cache=False,
            )
            return response.content.strip()
        except Exception as e:
            logger.error("[Pipeline] 字数调整失败: %s", e)
            return None