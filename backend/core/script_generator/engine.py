"""
完整剧本生成引擎

负责将大纲转化为完整的、可读的剧本文本。
核心能力:
- 场景框架规划: 根据章节大纲和目标字数自动规划场景列表
- 批量场景写作: 按顺序生成每个场景的 narration + dialogue + actions
- 因果链维护: 确保场景间逻辑连续，传递完整上下文
- 伏笔调度: 按规划在正确场景埋设/回收伏笔
- 角色状态追踪: 每个场景生成后更新角色状态
"""

import json
import logging
import re
import uuid
from datetime import datetime, UTC
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from core.gateway.client import get_gateway
from core.storage.service import StorageService
from core.rag.retriever import RAGRetriever

logger = logging.getLogger(__name__)


def _safe_parse_json_list(value) -> list:
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            if isinstance(parsed, list):
                return parsed
        except (json.JSONDecodeError, TypeError):
            pass
    return []


def _safe_extract_dialogue_text(dialogue) -> str:
    dlg_list = _safe_parse_json_list(dialogue)
    if dlg_list:
        return "\n".join(
            f"{d.get('char', '?')}: {d.get('text', '')}" for d in dlg_list if isinstance(d, dict)
        )
    return str(dialogue) if dialogue else ""


def _safe_extract_actions_text(actions) -> str:
    act_list = _safe_parse_json_list(actions)
    if act_list:
        return "\n".join(str(a) for a in act_list)
    return str(actions) if actions else ""

SCENE_TYPE_WRITING_GUIDE = {
    "opening": {
        "narration_guide": "以环境描写开场，营造氛围，通过细节暗示即将到来的冲突。至少包含两种感官描写（光/声/味/触/温）。",
        "dialogue_guide": "对话要自然引入角色关系和本章核心矛盾，每句对白必须有潜文本。",
        "min_words": 1500,
        "max_words": 4000,
    },
    "dialogue": {
        "narration_guide": "通过角色动作和微表情推进对话节奏，环境描写服务于情感渲染。禁止超过三句连续静态描写。",
        "dialogue_guide": "对白是核心，每句对白必须有'字面意思'与'真实意图'的落差。不同角色说话方式必须有区分度（句式、用词、语速）。",
        "min_words": 1500,
        "max_words": 4000,
    },
    "conflict": {
        "narration_guide": "冲突场景需要动态叙述，用短句制造紧张感。描写角色身体反应（手抖、瞳孔收缩、呼吸急促）而非直接写情绪。",
        "dialogue_guide": "对白要尖锐、有攻击性，但每句话背后都有更深层的恐惧或渴望。避免直白争吵，用暗示和反讽。",
        "min_words": 2000,
        "max_words": 5000,
    },
    "climax": {
        "narration_guide": "高潮场景需要最密集的感官描写和最强烈的节奏变化。长短句交替，关键时刻用极短句制造冲击。必须包含至少一个'画面定格'时刻。",
        "dialogue_guide": "对白要达到情感爆发点，但最强烈的情感用沉默表达。关键台词必须可以成为全剧金句。",
        "min_words": 2500,
        "max_words": 6000,
    },
    "closing": {
        "narration_guide": "收尾场景要留下余韵，用一个意味深长的画面或动作结束。章末必须有'钩子'——让读者无法停止阅读的悬念。",
        "dialogue_guide": "对白要克制，言外之意大于字面意思。最后一句台词要暗示下一章的走向。",
        "min_words": 1500,
        "max_words": 4000,
    },
    "transition": {
        "narration_guide": "过渡场景要简洁推进但保留画面感，用环境变化暗示时间流逝或局势转变。",
        "dialogue_guide": "对话简短，主要功能是传递信息或铺垫后续冲突。",
        "min_words": 800,
        "max_words": 2500,
    },
    "revelation": {
        "narration_guide": "揭露场景需要制造'恍然大悟'的感觉，之前的伏笔在此刻全部串联。描写角色认知崩塌的瞬间——不是直接写'震惊'，而是写手指松开、瞳孔放大。",
        "dialogue_guide": "关键信息通过对话逐步释放，每句话都是一块拼图。揭露者的话语要有'终于说出真相'的沉重感。",
        "min_words": 2000,
        "max_words": 5000,
    },
}


class ScriptGenerationEngine:

    def __init__(self, db: AsyncSession):
        self.db = db
        self.gateway = get_gateway()
        self.storage = StorageService(db)
        self.rag = RAGRetriever(db)

    async def generate_full_script(self, project_id: str) -> dict:
        logger.info("开始为项目 %s 生成完整剧本", project_id)

        project_data = await self._load_project_data(project_id)
        if not project_data["chapters"]:
            raise ValueError("项目没有章节大纲，无法生成剧本。请先执行大纲生成步骤。")

        scene_plan = await self._plan_scenes(project_id, project_data)

        generated_scenes = []
        character_state_tracker = {}

        for c in project_data["characters"]:
            c_name = c.get("name", "")
            character_state_tracker[c_name] = {
                "current_goal": c.get("core_goal", ""),
                "current_fear": c.get("core_fear", ""),
                "emotional_state": "初始状态",
                "known_secrets": [],
                "relationships_changed": [],
            }

        prev_chapter_ending = ""

        for chapter in project_data["chapters"]:
            chapter_scenes = await self._generate_chapter_scenes(
                project_id, chapter, scene_plan, project_data,
                character_state_tracker, prev_chapter_ending
            )
            generated_scenes.extend(chapter_scenes)

            if chapter_scenes:
                last_scene = chapter_scenes[-1]
                if isinstance(last_scene, dict) and not last_scene.get("error"):
                    narration = last_scene.get("narration", "")
                    dialogue_text = _safe_extract_dialogue_text(last_scene.get("dialogue", ""))
                    prev_chapter_ending = f"{narration[-2000:]}\n{dialogue_text[-1000:]}"

        total_words = sum(s.get("word_count", 0) for s in generated_scenes if isinstance(s, dict) and not s.get("error"))
        await self.storage.update_project_status(project_id, {
            "total_written_words": total_words,
            "current_phase": "completed",
        })

        return {
            "status": "completed",
            "project_id": project_id,
            "total_chapters": len(project_data["chapters"]),
            "total_scenes": len(generated_scenes),
            "total_words": total_words,
            "scenes": generated_scenes,
        }

    async def _load_project_data(self, project_id: str) -> dict:
        world_config = await self.storage.get_world_config(project_id) or {}
        characters = await self.storage.get_character_states(project_id) or []
        foreshadows = await self.storage.get_foreshadows(project_id) or []
        chapters = await self.storage.get_chapter_outlines(project_id) or []
        relations = await self.storage.get_relations(project_id) or {}

        config = await self.storage.get_project_config(project_id) or {}

        return {
            "world_config": world_config,
            "characters": characters,
            "foreshadows": foreshadows,
            "chapters": chapters,
            "relations": relations,
            "config": config,
            "genre": config.get("genre", "互动叙事"),
            "style": config.get("style", config.get("writing_style", "现代白话")),
            "core_contradiction": config.get("core_contradiction", ""),
            "target_word_count": config.get("target_word_count", 50000),
        }

    async def _plan_scenes(self, project_id: str, project_data: dict) -> list:
        existing_scenes = await self.storage.get_scenes_by_project(project_id)
        if existing_scenes:
            logger.info("项目已有 %d 个场景，使用现有场景框架", len(existing_scenes))
            return existing_scenes

        logger.info("项目没有场景记录，根据大纲自动生成场景框架")
        planned_scenes = []

        target_word_count = project_data.get("target_word_count", 50000)
        chapter_count = len(project_data["chapters"])
        words_per_chapter = target_word_count / max(chapter_count, 1)

        for chapter in project_data["chapters"]:
            ch_num = chapter.get("chapter_number", 1)
            ch_id = chapter.get("id")
            summary = chapter.get("summary", "")
            outline = chapter.get("outline", "")
            core_conflict = chapter.get("core_conflict", "")

            scene_count = self._estimate_scene_count(summary, outline, words_per_chapter)

            for i in range(1, scene_count + 1):
                scene_code = f"CH{ch_num:02d}-SC{i:02d}"
                scene_type = self._determine_scene_type(i, scene_count, summary, outline)
                location = self._extract_location_from_outline(outline, i)
                emotion_target = self._calculate_emotion_target(chapter, i, scene_count)

                scene_data = {
                    "id": str(uuid.uuid4()),
                    "project_id": project_id,
                    "chapter_id": ch_id,
                    "scene_code": scene_code,
                    "scene_type": scene_type,
                    "location": location,
                    "weather": "",
                    "emotion_level": emotion_target,
                    "summary": f"第{ch_num}章第{i}场: {scene_type}",
                    "narration": "",
                    "dialogue": "",
                    "actions": "",
                    "choices": "",
                    "foreshadow_ops": "[]",
                    "causal_chain": "",
                    "characters_involved": "[]",
                    "status": "pending",
                    "version": 1,
                    "created_at": datetime.now(UTC).isoformat(),
                    "updated_at": datetime.now(UTC).isoformat(),
                }

                await self.storage.create_scene(scene_data)
                planned_scenes.append(scene_data)

        logger.info("自动规划了 %d 个场景", len(planned_scenes))
        return planned_scenes

    MAX_SCENE_WORDS = 3000
    MAX_SCENES_PER_CHAPTER = 50
    MIN_SCENES_PER_CHAPTER = 3
    SCENE_RETRY_MAX = 2

    def _estimate_scene_count(self, summary: str, outline: str, words_per_chapter: float = 5000) -> int:
        text = f"{summary} {outline}"

        if words_per_chapter <= 0:
            return self.MIN_SCENES_PER_CHAPTER

        base_scenes = max(self.MIN_SCENES_PER_CHAPTER, int(words_per_chapter / self.MAX_SCENE_WORDS))

        if "高潮" in text or "决战" in text or "真相" in text or "揭露" in text:
            base_scenes = max(base_scenes, 5)
        if "转折" in text or "反转" in text:
            base_scenes = max(base_scenes, 5)
        if len(text) > 500:
            base_scenes = max(base_scenes, 4)

        return min(base_scenes, self.MAX_SCENES_PER_CHAPTER)

    def _determine_scene_type(self, scene_index: int, total_scenes: int, chapter_summary: str, outline: str = "") -> str:
        text = f"{chapter_summary} {outline}"

        if scene_index == 1:
            return "opening"
        if scene_index == total_scenes:
            if "高潮" in text or "决战" in text:
                return "climax"
            if "真相" in text or "揭露" in text or "揭秘" in text:
                return "revelation"
            return "closing"
        if "冲突" in text or "对抗" in text or "对峙" in text:
            return "conflict"
        if "真相" in text or "揭露" in text:
            return "revelation"
        if "过渡" in text or "日常" in text:
            return "transition"
        return "dialogue"

    def _extract_location_from_outline(self, outline: str, scene_index: int) -> str:
        location_keywords = {
            "宫": "宫殿", "殿": "大殿", "酒": "酒馆", "馆": "客栈",
            "街": "街道", "巷": "小巷", "林": "森林", "山": "山崖",
            "河": "河岸", "海": "海边", "城": "城门", "塔": "高塔",
            "牢": "地牢", "密": "密室", "书": "书房", "院": "庭院",
            "战": "战场", "营": "军营", "庙": "古庙", "寺": "寺庙",
        }
        for keyword, location in location_keywords.items():
            if keyword in outline:
                return location

        locations = ["主城广场", "密室", "酒馆", "森林", "宫殿", "战场", "书房", "街道", "庭院", "高塔"]
        return locations[scene_index % len(locations)]

    def _calculate_emotion_target(self, chapter: dict, scene_index: int, total_scenes: int) -> int:
        ch_emotion = chapter.get("emotion_target", 5)
        if isinstance(ch_emotion, str):
            try:
                ch_emotion = int(ch_emotion)
            except (ValueError, TypeError):
                ch_emotion = 5

        if total_scenes <= 1:
            return ch_emotion

        progress = (scene_index - 1) / (total_scenes - 1)

        if progress <= 0.3:
            return max(1, ch_emotion - 2)
        elif progress <= 0.7:
            return ch_emotion
        else:
            return min(10, ch_emotion + 2)

    async def _generate_chapter_scenes(
        self,
        project_id: str,
        chapter: dict,
        scene_plan: list,
        project_data: dict,
        character_state_tracker: dict,
        prev_chapter_ending: str,
    ) -> list:
        ch_id = chapter.get("id")
        ch_num = chapter.get("chapter_number", 1)
        ch_scenes = [s for s in scene_plan if str(s.get("chapter_id")) == str(ch_id)]

        if not ch_scenes:
            logger.warning("第%d章没有场景记录", ch_num)
            return []

        logger.info("开始生成第%d章的 %d 个场景", ch_num, len(ch_scenes))

        generated = []
        prev_scene_full_content = prev_chapter_ending

        for idx, scene in enumerate(ch_scenes):
            scene_id = scene.get("id")
            logger.info("生成场景 %s", scene.get("scene_code"))

            try:
                scene_content = await self._generate_single_scene(
                    project_id=project_id,
                    scene=scene,
                    chapter=chapter,
                    project_data=project_data,
                    prev_scene_content=prev_scene_full_content,
                    scene_index=idx,
                    total_scenes_in_chapter=len(ch_scenes),
                    character_state_tracker=character_state_tracker,
                )

                await self.storage.update_scene(project_id, scene_id, {
                    "narration": scene_content.get("narration", ""),
                    "dialogue": json.dumps(scene_content.get("dialogue", []), ensure_ascii=False) if isinstance(scene_content.get("dialogue"), list) else scene_content.get("dialogue", ""),
                    "actions": json.dumps(scene_content.get("actions", []), ensure_ascii=False) if isinstance(scene_content.get("actions"), list) else scene_content.get("actions", ""),
                    "choices": json.dumps(scene_content.get("choices", []), ensure_ascii=False) if isinstance(scene_content.get("choices"), list) else scene_content.get("choices", ""),
                    "characters_involved": json.dumps(scene_content.get("characters_involved", []), ensure_ascii=False),
                    "foreshadow_ops": json.dumps(scene_content.get("foreshadow_ops", []), ensure_ascii=False),
                    "causal_chain": scene_content.get("causal_chain", ""),
                    "status": "completed",
                    "word_count": scene_content.get("word_count", 0),
                })

                self._update_character_tracker(character_state_tracker, scene_content)

                narration = scene_content.get("narration", "")
                dialogue_text = _safe_extract_dialogue_text(scene_content.get("dialogue", ""))
                actions_text = _safe_extract_actions_text(scene_content.get("actions", ""))

                prev_scene_full_content = f"【旁白】\n{narration[-3000:]}\n【对白】\n{dialogue_text[-2000:]}\n【动作】\n{actions_text[-1000:]}"

                generated.append(scene_content)

            except Exception as e:
                logger.error("场景 %s 生成失败: %s", scene.get("scene_code"), str(e))
                generated.append({
                    "scene_code": scene.get("scene_code"),
                    "error": str(e),
                    "status": "failed",
                })

        return generated

    def _update_character_tracker(self, tracker: dict, scene_content: dict):
        characters_involved = scene_content.get("characters_involved", [])
        if not isinstance(characters_involved, list):
            return

        narration = scene_content.get("narration", "")
        dialogue = scene_content.get("dialogue", [])

        for char_name in characters_involved:
            if isinstance(char_name, dict):
                char_name = char_name.get("name", char_name.get("id", ""))
            if not isinstance(char_name, str):
                continue
            if char_name not in tracker:
                tracker[char_name] = {
                    "current_goal": "",
                    "current_fear": "",
                    "emotional_state": "初始状态",
                    "known_secrets": [],
                    "relationships_changed": [],
                }

            char_dialogues = []
            if isinstance(dialogue, list):
                for d in dialogue:
                    if isinstance(d, dict) and d.get("char") == char_name:
                        char_dialogues.append(d.get("text", ""))

            if char_dialogues:
                tracker[char_name]["last_dialogues"] = char_dialogues[-3:]

    async def _generate_single_scene(
        self,
        project_id: str,
        scene: dict,
        chapter: dict,
        project_data: dict,
        prev_scene_content: str,
        scene_index: int,
        total_scenes_in_chapter: int,
        character_state_tracker: dict | None = None,
    ) -> dict:
        scene_type = scene.get("scene_type", "dialogue")
        writing_guide = SCENE_TYPE_WRITING_GUIDE.get(scene_type, SCENE_TYPE_WRITING_GUIDE["dialogue"])
        min_required_words = writing_guide["min_words"]

        target_word_count = project_data.get("target_word_count", 50000)
        chapter_count = len(project_data.get("chapters", []))
        words_per_chapter = target_word_count / max(chapter_count, 1)
        scenes_per_chapter = max(self.MIN_SCENES_PER_CHAPTER, int(words_per_chapter / self.MAX_SCENE_WORDS))
        target_scene_words = min(self.MAX_SCENE_WORDS, max(1500, int(words_per_chapter / scenes_per_chapter)))

        min_required_words = max(min_required_words, int(target_scene_words * 0.6))

        best_result = None
        best_word_count = 0

        rag_chunks = await self._retrieve_rag_context(
            project_id, scene, chapter, project_data
        )

        for attempt in range(self.SCENE_RETRY_MAX + 1):
            prompt = self._build_scene_prompt(
                scene=scene,
                chapter=chapter,
                project_data=project_data,
                prev_scene_content=prev_scene_content,
                scene_index=scene_index,
                total_scenes=total_scenes_in_chapter,
                character_state_tracker=character_state_tracker or {},
                target_scene_words=target_scene_words,
                rag_chunks=rag_chunks,
            )

            emotion_level = scene.get("emotion_level", 5)

            if scene_type in ("climax", "revelation") or emotion_level >= 8:
                cost_profile = "quality"
                max_tokens = 16000
                temperature = 0.85
            elif scene_type in ("conflict", "closing") or emotion_level >= 6:
                cost_profile = "balanced"
                max_tokens = 12000
                temperature = 0.8
            elif scene_type == "transition":
                cost_profile = "balanced"
                max_tokens = 8000
                temperature = 0.75
            else:
                cost_profile = "balanced"
                max_tokens = 12000
                temperature = 0.8

            if attempt > 0:
                temperature = min(temperature + 0.1, 1.0)
                max_tokens = min(max_tokens + 4000, 64000)

            try:
                response = await self.gateway.invoke(
                    intent="write.prose",
                    messages=[
                        {"role": "system", "content": self._build_system_prompt(project_data, scene_type)},
                        {"role": "user", "content": prompt},
                    ],
                    cost_profile=cost_profile,
                    max_tokens=max_tokens,
                    temperature=temperature,
                )

                content = response.content
                parsed = self._parse_scene_output(content)

                narration = parsed.get("narration", "")
                dialogue = parsed.get("dialogue", "")
                actions = parsed.get("actions", "")

                dlg_list = _safe_parse_json_list(dialogue)
                dialogue_word_count = sum(len(d.get("text", "")) for d in dlg_list if isinstance(d, dict)) if dlg_list else len(str(dialogue))

                act_list = _safe_parse_json_list(actions)
                actions_word_count = sum(len(str(a)) for a in act_list) if act_list else len(str(actions))

                word_count = len(narration) + dialogue_word_count + actions_word_count
                parsed["word_count"] = word_count
                parsed["scene_code"] = scene.get("scene_code")
                parsed["scene_id"] = scene.get("id")

                if word_count >= min_required_words:
                    return parsed

                if word_count > best_word_count:
                    best_result = parsed
                    best_word_count = word_count

                logger.warning(
                    "场景 %s 第%d次生成字数不足: %d < %d，将重试",
                    scene.get("scene_code"), attempt + 1, word_count, min_required_words
                )

            except Exception as e:
                logger.error("场景 %s 第%d次生成异常: %s", scene.get("scene_code"), attempt + 1, str(e))
                if attempt == self.SCENE_RETRY_MAX:
                    if best_result:
                        return best_result
                    raise

        if best_result:
            logger.warning("场景 %s 重试后仍不足字数，使用最佳结果: %d字", scene.get("scene_code"), best_word_count)
            return best_result

        raise RuntimeError(f"场景 {scene.get('scene_code')} 生成完全失败")

    async def _retrieve_rag_context(self, project_id: str, scene: dict, chapter: dict, project_data: dict) -> list:
        query_parts = []
        scene_type = scene.get("scene_type", "")
        scene_code = scene.get("scene_code", "")
        emotion = scene.get("emotion_level", 5)
        location = scene.get("location", "")
        chapter_title = chapter.get("title", "")
        chapter_summary = chapter.get("summary", "")

        query_parts.append(f"场景{scene_code}")
        if scene_type:
            query_parts.append(f"类型{scene_type}")
        if location:
            query_parts.append(f"地点{location}")
        if chapter_title:
            query_parts.append(f"章节{chapter_title}")
        if chapter_summary:
            query_parts.append(chapter_summary[:200])
        query_parts.append(project_data.get("core_contradiction", ""))
        query_parts.append(f"情感{emotion}")

        query = "，".join(filter(None, query_parts))

        target_word_count = project_data.get("target_word_count", 50000)
        top_k = self._get_rag_top_k(target_word_count)

        try:
            results = await self.rag.retrieve(
                project_id=project_id, query=query, top_k=top_k
            )
            if results:
                logger.info("RAG检索成功: 项目%s 场景%s → %d条结果 (top_k=%d, 剧本规模=%s)",
                             project_id[:8], scene_code, len(results), top_k,
                             self._get_script_scale(target_word_count))
            return results
        except Exception as e:
            logger.warning("RAG检索失败: %s", e)
            return []

    @staticmethod
    def _get_script_scale(target_word_count: int) -> str:
        if target_word_count <= 20000:
            return "短篇"
        elif target_word_count <= 80000:
            return "中篇"
        else:
            return "长篇"

    @staticmethod
    def _get_rag_top_k(target_word_count: int) -> int:
        if target_word_count <= 20000:
            return 6
        elif target_word_count <= 50000:
            return 10
        elif target_word_count <= 80000:
            return 15
        else:
            return 20

    def _build_system_prompt(self, project_data: dict, scene_type: str) -> str:
        genre = project_data.get("genre", "互动叙事")
        style = project_data.get("style", "现代白话")

        return f"""你是一位{genre}题材的{style}风格专业编剧，专精互动影游剧本创作。你的作品以画面感强、对白有深度、角色立体著称。

【生死线——你必须严格遵守，否则作品报废】
1. **narration必须是完整的小说式文学描写**，像出版小说一样有画面感、有节奏、有情感。绝对不能是：大纲、摘要、要点罗列、设定说明、剧情简介、分镜说明。
2. **dialogue必须是角色实际说出口的完整台词**，不是"他说了关于XX的事"这种描述。每句台词都要有潜文本。
3. **你必须真正"写"场景，不是"描述"场景**——读者应该能直接阅读你的输出并沉浸其中。

【中文创意写作铁律】
1. 画面感三要素：每个场景描述必须包含至少两种感官（光/味/声/触/温）
2. 动态叙述：用动作推进剧情，禁止超过三句连续静态描写
3. 对白潜文本：每句对白必须有"字面意思"与"真实意图"的落差（角色永远口是心非）
4. 节奏控制：短句（<15字）制造紧张，长句（>30字）营造沉浸
5. 具象化：抽象概念必须用具体物象承载（不写"悲伤"，写"手指抠进掌心"）
6. 叙事视角一致：严格遵循指定的POV视角，不跳视角
7. 信息释放：采用"冰山原则"，只写水面以上，水下留给读者/玩家推断
8. 中国网文黄金律：每300字必须有新的信息增量（新动作/新对话/新发现）

【互动影游剧本特殊要求】
1. 代入感：主角的行动必须有明确的选择空间
2. 道德灰度：每个重大抉择必须有好/坏两面的后果
3. NPC深度：配角不能只是工具人，每个NPC有自己的小算盘
4. 信息不对等：不同角色掌握不同信息片段
5. 情感锚点：每3-5个场景必须有一个情感重场
6. 分支预埋：重要对白末尾暗示另一种可能
7. 环境叙事：场景本身应当传达故事信息

【正确vs错误的例子】
❌ 错误（设定式）："场景发生在酒馆，主角和反派对峙，主角试图说服反派投降。"
✅ 正确（文学式）："酒馆的灯笼在穿堂风里摇晃，把两人的影子撕成碎片。主角的手指扣在腰间的剑柄上，指节发白。'你来了。'他说，声音比想象中稳。"

❌ 错误（摘要式）："角色A表达了他对角色B的愤怒，因为B背叛了他。"
✅ 正确（台词式）："{{'char': '角色A', 'text': '这杯酒我敬你——敬你当年在雪地里给我那块干粮。', 'subtext': '我记得你的恩情，但你也欠我一条命'}}"

【输出格式要求】
你必须输出严格的JSON格式，不要包含任何markdown标记或额外文字。JSON结构如下：
{{
    "narration": "完整的场景叙述文字（环境描写+角色动作+心理刻画+氛围营造，必须是完整的文学性文字，不是提纲或摘要）",
    "dialogue": [{{"char": "角色名", "text": "完整台词", "subtext": "潜台词/真实意图"}}],
    "actions": ["关键动作描写1", "关键动作描写2"],
    "choices": [{{"id": "A", "text": "选项文本", "consequence": "直接后果"}}],
    "characters_involved": ["参与本场景的角色名列表"],
    "foreshadow_ops": [{{"op": "plant/reinforce/reveal", "fs_name": "伏笔名称", "description": "具体操作描述"}}],
    "causal_chain": "本场景在整体剧情中的因果位置说明"
}}"""

    def _build_scene_prompt(
        self,
        scene: dict,
        chapter: dict,
        project_data: dict,
        prev_scene_content: str,
        scene_index: int,
        total_scenes: int,
        character_state_tracker: dict | None = None,
        target_scene_words: int = 2000,
        rag_chunks: list | None = None,
    ) -> str:
        world = project_data["world_config"]
        chars = project_data["characters"]
        foreshadows = project_data["foreshadows"]
        relations = project_data.get("relations", {})
        tracker = character_state_tracker or {}

        world_summary = ""
        world_labels = {
            "social_structure": "社会结构",
            "tech_magic": "科技/魔法体系",
            "geography": "地理环境",
            "history": "历史背景",
            "culture": "文化习俗",
            "constraints": "约束条件",
            "impossible": "不可能事项",
        }
        for key, label in world_labels.items():
            val = world.get(key, "")
            if val:
                world_summary += f"【{label}】{val}\n"

        char_summary = ""
        for c in chars:
            name = c.get("name", "?")
            role = c.get("role_type", "?")
            goal = c.get("core_goal", "?")
            fear = c.get("core_fear", "?")
            lang_style = c.get("language_style", "")
            catchphrase = c.get("catchphrase", "")
            surface = c.get("surface_image", "")
            true_self = c.get("true_self", "")

            char_summary += f"- {name} ({role}):\n"
            char_summary += f"  动机: {goal}\n"
            char_summary += f"  恐惧: {fear}\n"
            if lang_style:
                char_summary += f"  语言风格: {lang_style}\n"
            if catchphrase:
                char_summary += f"  口头禅: {catchphrase}\n"
            if surface:
                char_summary += f"  表面形象: {surface}\n"
            if true_self:
                char_summary += f"  真实自我: {true_self}\n"

            if name in tracker:
                state = tracker[name]
                if state.get("emotional_state"):
                    char_summary += f"  当前情感状态: {state['emotional_state']}\n"
                if state.get("last_dialogues"):
                    char_summary += f"  近期台词: {'; '.join(state['last_dialogues'][-2:])}\n"
            char_summary += "\n"

        fs_summary = ""
        for f in foreshadows:
            fs_name = f.get("name", "?")
            fs_status = f.get("current_status", "design")
            surface = f.get("surface_layer", "")
            deep = f.get("deep_layer", "")
            truth = f.get("truth_layer", "")
            fs_summary += f"- [{fs_status}] {fs_name}:\n"
            fs_summary += f"  表层: {surface}\n"
            if deep:
                fs_summary += f"  深层: {deep}\n"
            if truth:
                fs_summary += f"  真相: {truth}\n"

        relation_summary = ""
        if isinstance(relations, list):
            for rel in relations:
                a = rel.get("char_a_name", "?")
                b = rel.get("char_b_name", "?")
                rtype = rel.get("relation_type", "?")
                trust = rel.get("trust", 50)
                favor = rel.get("favor", 50)
                surface_desc = rel.get("surface_description", "")
                deep_desc = rel.get("deep_description", "")
                relation_summary += f"- {a} ↔ {b} ({rtype}, 信任:{trust}, 好感:{favor})\n"
                if surface_desc:
                    relation_summary += f"  表面: {surface_desc}\n"
                if deep_desc:
                    relation_summary += f"  深层: {deep_desc}\n"
        elif isinstance(relations, dict):
            for key, val in relations.items():
                relation_summary += f"- {key}: {str(val)}\n"

        scene_type = scene.get("scene_type", "dialogue")
        writing_guide = SCENE_TYPE_WRITING_GUIDE.get(scene_type, SCENE_TYPE_WRITING_GUIDE["dialogue"])

        target_word_count = project_data.get("target_word_count", 50000)
        chapter_count = len(project_data.get("chapters", []))
        words_per_chapter = target_word_count / max(chapter_count, 1)

        position_desc = ""
        if scene_index == 0:
            position_desc = "这是本章的开场场景，需要引入本章主题，建立场景氛围，让读者迅速进入状态。"
        elif scene_index == total_scenes - 1:
            position_desc = "这是本章的收尾场景，必须推进剧情或留下强烈悬念。章末必须有'钩子'——让读者无法停止阅读。"
        else:
            progress = scene_index / max(total_scenes - 1, 1)
            if progress < 0.4:
                position_desc = "这是本章前段场景，需要铺垫冲突、建立角色关系张力。"
            elif progress < 0.7:
                position_desc = "这是本章中段场景，需要推进冲突发展、加深角色矛盾。"
            else:
                position_desc = "这是本章后段场景，需要将冲突推向高潮或准备转折。"

        min_words = writing_guide["min_words"]
        max_words = writing_guide["max_words"]

        if target_scene_words > 0:
            min_words = max(min_words, int(target_scene_words * 0.7))
            max_words = max(max_words, int(target_scene_words * 1.3))

        max_words = min(max_words, 5000)

        rag_context = ""
        if rag_chunks:
            rag_parts = []
            for chunk in rag_chunks:
                if hasattr(chunk, "content_type"):
                    ctype = chunk.content_type
                    text = chunk.text
                else:
                    ctype = chunk.get("content_type", "") if isinstance(chunk, dict) else ""
                    text = chunk.get("text", "") if isinstance(chunk, dict) else str(chunk)
                label = {"scene": "已生成场景参考", "character": "角色信息参考", "foreshadow": "伏笔信息参考"}.get(ctype, ctype)
                rag_parts.append(f"【{label}】\n{text[:800]}")
            rag_context = "\n\n".join(rag_parts) if rag_parts else ""

        rag_section = ""
        if rag_context:
            rag_section = f"""━━━━━━━━━━━━━━━━━━━━━━
🔍 RAG 检索到的相关上下文（已生成的场景/角色/伏笔）
━━━━━━━━━━━━━━━━━━━━━━
{rag_context}
"""

        prompt = f"""请为以下场景创作完整的、文学性的剧本内容。

━━━━━━━━━━━━━━━━━━━━━━
📖 项目信息
━━━━━━━━━━━━━━━━━━━━━━
题材: {project_data['genre']}
风格: {project_data['style']}
核心矛盾: {project_data['core_contradiction']}
目标总字数: {target_word_count}字

━━━━━━━━━━━━━━━━━━━━━━
🌍 世界观设定
━━━━━━━━━━━━━━━━━━━━━━
{world_summary or '(无详细世界观)'}

━━━━━━━━━━━━━━━━━━━━━━
👥 角色详细档案
━━━━━━━━━━━━━━━━━━━━━━
{char_summary or '(无角色信息)'}

━━━━━━━━━━━━━━━━━━━━━━
🔗 角色关系网络
━━━━━━━━━━━━━━━━━━━━━━
{relation_summary or '(无关系信息)'}

━━━━━━━━━━━━━━━━━━━━━━
🔮 伏笔信息
━━━━━━━━━━━━━━━━━━━━━━
{fs_summary or '(无伏笔信息)'}

━━━━━━━━━━━━━━━━━━━━━━
📋 当前章节
━━━━━━━━━━━━━━━━━━━━━━
第{chapter.get('chapter_number', '?')}章: {chapter.get('title', '')}
章节摘要: {chapter.get('summary', '')}
章节核心冲突: {chapter.get('core_conflict', '')}
情感目标: {chapter.get('emotion_target', 5)}/10

━━━━━━━━━━━━━━━━━━━━━━
🎬 当前场景
━━━━━━━━━━━━━━━━━━━━━━
场景编号: {scene.get('scene_code')}
场景类型: {scene_type}
地点: {scene.get('location', '未指定')}
情感强度: {scene.get('emotion_level', 5)}/10
{position_desc}

【场景类型写作指南】
旁白要求: {writing_guide['narration_guide']}
对白要求: {writing_guide['dialogue_guide']}

━━━━━━━━━━━━━━━━━━━━━━
📝 前序场景内容（请严格保持叙事连续性）
━━━━━━━━━━━━━━━━━━━━━━
{prev_scene_content or '(本章第一个场景，请参考上一章结尾自然过渡)'}

{rag_section}━━━━━━━━━━━━━━━━━━━━━━
✍️ 写作要求
━━━━━━━━━━━━━━━━━━━━━━

【字数硬性要求】本场景总字数（旁白+对白+动作）必须在 {min_words}-{max_words} 字之间！

【绝对禁止——出现以下情况作品直接报废】
- ❌ narration写成"场景概述"、"剧情提要"、"分镜说明"或"设定描述"
- ❌ dialogue写成"角色讨论了XX问题"或"两人发生了争执"这种间接叙述
- ❌ 用 bullet points 或编号列表代替文学描写
- ❌ 输出类似"本场景主要讲述..."、"在这一幕中..."的元描述

【内容要求】
1. **narration必须是可直接阅读的小说正文**——读者不需要任何补充说明就能沉浸其中。写环境、写动作、写心理、写氛围，像金庸、古龙、刘慈欣那样写。
2. **dialogue必须是角色实际说出的完整台词**——每句都要有潜台词，不同角色说话方式必须有明显区分度（用词、句式、语速、口头禅）。
3. 场景之间必须严格保持因果连续性——角色位置、情感状态、已知信息必须与前序场景自然衔接
4. 内容必须严格符合世界观设定和角色性格
5. 每个角色在本场景的行为必须与其动机、恐惧、语言风格一致
6. 至少包含两种感官描写（光/声/味/触/温）
7. 禁止过度排比、无意义景物描写、重复心理活动
8. 每个描写必须服务于剧情推进或角色塑造
9. 对话必须有潜台词，角色之间要有信息差
10. 场景结尾必须暗示后续发展的可能性

【自检清单——输出前请确认】
□ narration读起来像小说正文，不是摘要
□ dialogue是角色直接说出的台词，不是描述
□ 如果我把narration和dialogue连起来读，是一个完整的、有画面感的场景
□ 总字数达到了{min_words}字以上

请直接输出JSON，不要输出任何其他内容。"""

        return prompt

    def _parse_scene_output(self, content: str) -> dict:
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            pass

        json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', content, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except json.JSONDecodeError:
                pass

        json_match = re.search(r'(\{[\s\S]*\})', content)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except json.JSONDecodeError:
                pass

        logger.warning("无法解析场景输出为JSON，将内容作为 narration")
        return {
            "narration": content,
            "dialogue": [],
            "actions": [],
            "choices": [],
            "characters_involved": [],
            "foreshadow_ops": [],
            "causal_chain": "",
        }
