import json
import logging
from typing import Optional

from core.agent.base import BaseAgent, AgentTask, AgentResult
from core.agent.skill import Skill
from core.agent.registry import register_agent
from core.agent.git_doc_manager import GitDocumentManager

logger = logging.getLogger(__name__)

MAX_CONTEXT_CHARS = 100000

RAG_RETRIEVER_SKILL = Skill()
RAG_RETRIEVER_SKILL.name = "rag_retriever"
RAG_RETRIEVER_SKILL.intent = "search"
RAG_RETRIEVER_SKILL.prompt_template = "从RAG知识库中检索相关上下文片段。"
RAG_RETRIEVER_SKILL.output_parser = lambda text: {"retrieved": text}

CONTEXT_BUILDER_SKILL = Skill()
CONTEXT_BUILDER_SKILL.name = "context_builder"
CONTEXT_BUILDER_SKILL.intent = "planning"
CONTEXT_BUILDER_SKILL.prompt_template = "为创作Agent构建完整的上下文包。"
CONTEXT_BUILDER_SKILL.output_parser = lambda text: {"context": text}

INDEX_QUERY_SKILL = Skill()
INDEX_QUERY_SKILL.name = "index_query"
INDEX_QUERY_SKILL.intent = "search"
INDEX_QUERY_SKILL.prompt_template = "按角色/伏笔/关键词/情感强度查询场景。"
INDEX_QUERY_SKILL.output_parser = lambda text: {"results": text}

DOC_MANAGER_SKILL = Skill()
DOC_MANAGER_SKILL.name = "doc_manager"
DOC_MANAGER_SKILL.intent = "planning"
DOC_MANAGER_SKILL.prompt_template = "Git版本控制的场景文档管理。"
DOC_MANAGER_SKILL.output_parser = lambda text: {"doc": text}


@register_agent
class MaterialAgent(BaseAgent):
    name = "material"
    description = "场景上下文包构建、素材管理、文档查询、多层级信息整合、Git版本控制"
    skills = {
        "rag_retriever": RAG_RETRIEVER_SKILL,
        "context_builder": CONTEXT_BUILDER_SKILL,
        "index_query": INDEX_QUERY_SKILL,
        "doc_manager": DOC_MANAGER_SKILL,
    }

    async def execute(self, task: AgentTask) -> AgentResult:
        self._validate(task)

        project_id = task.project_id
        scene_id = task.payload.get("scene_id")
        context_type = task.payload.get("context_type", "full")
        rag_query = task.payload.get("rag_query", f"场景 {scene_id or '全景'} 上下文需求")

        try:
            if context_type == "index_query":
                return await self._handle_index_query(project_id, task.payload)

            if context_type == "doc_write":
                return await self._handle_doc_write(project_id, task.payload)

            if context_type == "doc_read":
                return await self._handle_doc_read(project_id, task.payload)

            if not scene_id:
                scene_plan = await self._plan_next_scene(project_id, task.payload)
                if scene_plan.get("status") == "all_done":
                    return AgentResult(
                        status="completed",
                        data=scene_plan,
                    )
                if scene_plan.get("status") == "no_chapters":
                    return AgentResult(
                        status="completed",
                        data=scene_plan,
                    )
                return AgentResult(
                    status="completed",
                    data=scene_plan,
                )

            context_pack = await self._build_context_pack(
                project_id, scene_id, context_type, rag_query
            )

            return AgentResult(
                status="completed",
                data=context_pack,
            )
        except Exception as e:
            logger.error("MaterialAgent failed for scene %s: %s", scene_id, str(e))
            return AgentResult(
                status="failed",
                data={"error": str(e)},
                issues=[str(e)],
            )

    def _validate(self, task: AgentTask):
        if not task.project_id:
            raise ValueError("project_id is required")

    async def _build_context(self, task: AgentTask) -> dict:
        return {}

    def _select_skill(self, task_type: str) -> Skill:
        return self.skills[task_type]

    async def _handle_index_query(self, project_id: str, payload: dict) -> AgentResult:
        query_type = payload.get("query_type", "keyword")
        results = []

        if query_type == "character":
            character_id = payload.get("character_id", "")
            if character_id:
                results = await self.storage.get_scenes_by_character(project_id, character_id)
        elif query_type == "foreshadow":
            foreshadow_id = payload.get("foreshadow_id", "")
            if foreshadow_id:
                results = await self.storage.get_scenes_by_foreshadow(project_id, foreshadow_id)
        elif query_type == "keyword":
            keyword = payload.get("keyword", "")
            if keyword:
                results = await self.storage.search_scenes_by_keyword(project_id, keyword)
        elif query_type == "emotion_range":
            min_e = payload.get("min_emotion", 0)
            max_e = payload.get("max_emotion", 10)
            results = await self.storage.get_scenes_by_emotion_range(project_id, min_e, max_e)

        return AgentResult(
            status="completed",
            data={"query_type": query_type, "results": results, "count": len(results)},
        )

    async def _handle_doc_write(self, project_id: str, payload: dict) -> AgentResult:
        scene_id = payload.get("scene_id", "")
        content = payload.get("content", {})
        if not scene_id:
            return AgentResult(status="failed", data={"error": "scene_id required"}, issues=["scene_id required"])

        doc_mgr = GitDocumentManager(project_id)
        commit_hash = doc_mgr.write_scene(scene_id, content)

        return AgentResult(
            status="completed",
            data={"scene_id": scene_id, "commit_hash": commit_hash, "action": "written"},
        )

    async def _handle_doc_read(self, project_id: str, payload: dict) -> AgentResult:
        scene_id = payload.get("scene_id", "")
        if not scene_id:
            return AgentResult(status="failed", data={"error": "scene_id required"}, issues=["scene_id required"])

        doc_mgr = GitDocumentManager(project_id)
        content = doc_mgr.get_scene(scene_id)

        return AgentResult(
            status="completed",
            data={"scene_id": scene_id, "content": content, "found": content is not None},
        )

    async def _plan_next_scene(self, project_id: str, payload: dict) -> dict:
        """智能规划下一个待写场景，返回场景元数据和上下文包。"""
        chapters = payload.get("chapters", [])
        if not chapters:
            chapters = await self.storage.get_chapter_outlines(project_id)

        if not chapters:
            return {"status": "no_chapters", "message": "尚无章节大纲，无法规划场景"}

        scenes_per_chapter_max = payload.get("scenes_per_chapter_max", 6)
        scenes_per_chapter_min = payload.get("scenes_per_chapter_min", 3)

        target_chapter = None
        target_scene_num = 1
        target_chapter_idx = 0
        prev_scenes_text = ""

        for ch_idx, ch in enumerate(chapters):
            ch_id = str(ch.get("id", ""))
            existing_scenes = await self.storage.get_scenes_by_chapter(project_id, ch_id)
            if len(existing_scenes) < scenes_per_chapter_max:
                target_chapter = ch
                target_scene_num = len(existing_scenes) + 1
                target_chapter_idx = ch_idx
                if existing_scenes:
                    prev_lines = []
                    for es in existing_scenes[-3:]:
                        snippet = (es.get("narration", "") or "")[:500]
                        prev_lines.append(f"[{es.get('scene_code', '?')}] {snippet}")
                    prev_scenes_text = "\n".join(prev_lines)
                break

        if not target_chapter:
            return {"status": "all_done", "message": "所有章节的场景数已达到上限"}

        ch_num = target_chapter.get("chapter_number", target_chapter_idx + 1)
        scene_code = f"CH{int(ch_num):03d}_S{target_scene_num:03d}"

        sections = []
        total_chars = 0

        p1_content, p1_chars = await self._build_layer0(project_id)
        sections.append({"name": "Layer 0 - 世界观设定", "content": p1_content, "priority": 1})
        total_chars += p1_chars

        if prev_scenes_text:
            sections.append({"name": "前序场景摘要", "content": prev_scenes_text, "priority": 2})
            total_chars += len(prev_scenes_text)

        p3_content, p3_chars = await self._build_character_states(project_id)
        sections.append({"name": "角色档案", "content": p3_content, "priority": 3})
        total_chars += p3_chars

        ch_id = str(target_chapter.get("id", ""))
        if ch_id:
            p4_content, p4_chars = await self._build_chapter_context(ch_id)
            sections.append({"name": "章节上下文", "content": p4_content, "priority": 4})
            total_chars += p4_chars

        p6_content, p6_chars = await self._build_master_plan(project_id)
        sections.append({"name": "大纲总览", "content": p6_content, "priority": 5})
        total_chars += p6_chars

        rag_query = f"{target_chapter.get('title', '')} {target_chapter.get('summary', '')} 场景{target_scene_num}"
        rag_results = await self.rag.retrieve(project_id, rag_query, top_k=3)
        if rag_results:
            rag_content = "\n---\n".join(r.text for r in rag_results)
            sections.append({"name": "RAG 参考素材", "content": rag_content, "priority": 6})

        sections = self._trim_context(sections, MAX_CONTEXT_CHARS)

        return {
            "status": "planned",
            "scene_code": scene_code,
            "scene_num": target_scene_num,
            "chapter_id": ch_id,
            "chapter_number": ch_num,
            "chapter_title": target_chapter.get("title", ""),
            "chapter_summary": target_chapter.get("summary", ""),
            "emotion_target": target_chapter.get("emotion_target", 5),
            "chapter_core_conflict": target_chapter.get("core_conflict", ""),
            "sections": sections,
            "total_chars": sum(s.get("char_count", len(s["content"])) for s in sections),
            "current_chapter_index": target_chapter_idx,
            "scenes_in_chapter_so_far": target_scene_num - 1,
        }

    async def _build_context_pack(
        self, project_id: str, scene_id: str, context_type: str, rag_query: str = ""
    ) -> dict:
        sections = []
        total_chars = 0

        p1_content, p1_chars = await self._build_layer0(project_id)
        sections.append({"name": "Layer 0 - 不变量", "content": p1_content, "priority": 1})
        total_chars += p1_chars

        if scene_id:
            scene = await self.storage.get_scene(project_id, scene_id)
            if scene:
                chapter_id = scene.get("chapter_id")
                scene_code = scene.get("scene_code")

                p2_content, p2_chars = await self._build_prev_scenes(project_id, scene_id, scene_code)
                sections.append({"name": "Layer 2 - 前序场景", "content": p2_content, "priority": 2})
                total_chars += p2_chars

                p3_content, p3_chars = await self._build_character_states(project_id)
                sections.append({"name": "Layer 1 - 角色状态", "content": p3_content, "priority": 3})
                total_chars += p3_chars

                if chapter_id:
                    p4_content, p4_chars = await self._build_chapter_context(chapter_id)
                    sections.append({"name": "Layer 4 - 章节上下文", "content": p4_content, "priority": 4})
                    total_chars += p4_chars

                p5_content, p5_chars = await self._build_scene_summaries(project_id, chapter_id, scene_code)
                sections.append({"name": "Layer 5 - 场景摘要", "content": p5_content, "priority": 5})
                total_chars += p5_chars

                p6_content, p6_chars = await self._build_master_plan(project_id)
                sections.append({"name": "Layer 3 - 大纲总览", "content": p6_content, "priority": 6})
                total_chars += p6_chars

        rag_results = await self.rag.retrieve(project_id, rag_query, top_k=5)
        if rag_results:
            rag_content = "\n---\n".join(r.text for r in rag_results)
            sections.append({"name": "RAG 语义召回", "content": rag_content, "priority": 7})

        sections = self._trim_context(sections, MAX_CONTEXT_CHARS)

        return {
            "scene_id": scene_id,
            "project_id": project_id,
            "sections": sections,
            "total_chars": sum(s.get("char_count", len(s["content"])) for s in sections),
        }

    def _trim_context(self, sections: list, max_chars: int) -> list:
        p1_p2 = [s for s in sections if s["priority"] <= 2]
        p3_plus = [s for s in sections if s["priority"] > 2]

        fixed_chars = sum(len(s["content"]) for s in p1_p2)
        remaining = max_chars - fixed_chars

        if remaining <= 0:
            return p1_p2

        for section in p3_plus:
            section["char_count"] = len(section["content"])

        p3_plus.sort(key=lambda s: s["priority"])

        result = list(p1_p2)
        used = 0
        for section in p3_plus:
            chars = section["char_count"]
            if used + chars <= remaining:
                result.append(section)
                used += chars
            else:
                available = remaining - used
                if available > 200:
                    section["content"] = section["content"][:available] + "\n...[裁剪]"
                    section["char_count"] = available
                    result.append(section)
                break

        return result

    async def _build_layer0(self, project_id: str) -> tuple[str, int]:
        layer0 = await self.storage.get_layer0(project_id)
        lines = []
        for key, val in layer0.items():
            v = val.get("value", val) if isinstance(val, dict) else val
            lines.append(f"【{key}】\n{v}")
        content = "\n\n".join(lines)
        return content, len(content)

    async def _build_prev_scenes(self, project_id, scene_id, scene_code) -> tuple[str, int]:
        prev = await self.storage.get_prev_scenes(scene_id, count=5)
        lines = []
        for s in prev:
            narration = s.get('narration', '')
            if narration and len(narration) > 8000:
                narration = narration[:20000] + "...[截断]"

            dialogue = s.get('dialogue', [])
            if isinstance(dialogue, list):
                dialogue_text = "\n".join(
                    f"  {d.get('char', '?')}: {d.get('text', '')}" for d in dialogue if isinstance(d, dict)
                )
            elif dialogue:
                dialogue_text = str(dialogue)[:10000]
            else:
                dialogue_text = ""

            actions = s.get('actions', [])
            if isinstance(actions, list):
                actions_text = "\n".join(f"  {a}" for a in actions)
            elif actions:
                actions_text = str(actions)[:10000]
            else:
                actions_text = ""

            scene_text = f"场景 {s.get('scene_code', '?')}:\n"
            if narration:
                scene_text += f"【旁白】{narration}\n"
            if dialogue_text:
                scene_text += f"【对白】\n{dialogue_text}\n"
            if actions_text:
                scene_text += f"【动作】\n{actions_text}\n"

            lines.append(scene_text)
        content = "\n---\n".join(lines) or "(无前序场景)"
        return content, len(content)

    async def _build_character_states(self, project_id) -> tuple[str, int]:
        chars = await self.storage.get_character_states(project_id)
        lines = []
        for c in (chars or []):
            parts = [f"{c.get('name', '?')} [{c.get('role_type', '未设定')}]"]
            if c.get("core_goal"):
                parts.append(f"动机={c['core_goal']}")
            if c.get("core_fear"):
                parts.append(f"恐惧={c['core_fear']}")
            if c.get("language_style"):
                parts.append(f"风格={c['language_style']}")
            if c.get("catchphrase"):
                parts.append(f"口头禅={c['catchphrase']}")
            if c.get("behavior_inevitable"):
                parts.append(f"必做={c['behavior_inevitable']}")
            if c.get("behavior_never"):
                parts.append(f"绝不做={c['behavior_never']}")
            if c.get("surface_image"):
                parts.append(f"表面={c['surface_image']}")
            if c.get("true_self"):
                parts.append(f"真实={c['true_self']}")
            if c.get("dark_secret"):
                parts.append(f"秘密={c['dark_secret']}")
            if c.get("arc_description"):
                parts.append(f"弧线={c['arc_description']}")
            lines.append(" | ".join(parts))
        content = "\n".join(lines) or "(无角色数据)"
        return content, len(content)

    async def _build_chapter_context(self, chapter_id) -> tuple[str, int]:
        ctx = await self.storage.get_chapter_context("", chapter_id)
        if ctx and ctx.get("chapter"):
            ch = ctx["chapter"]
            content = f"第{ch.get('chapter_number', '?')}章: {ch.get('title', '')}\n摘要: {ch.get('summary', '')}\n情感目标: {ch.get('emotion_target', 5)}/10"
        else:
            content = f"章节ID: {chapter_id}"
        return content, len(content)

    async def _build_scene_summaries(self, project_id, chapter_id, scene_code) -> tuple[str, int]:
        summaries = await self.storage.get_scene_summaries(project_id)
        lines = []
        for s in (summaries or []):
            narration = s.get("narration", "")
            if narration:
                preview = narration[:2000] + ("..." if len(narration) > 2000 else "")
                lines.append(f"{s.get('scene_code', '?')}: {preview}")
        content = "\n".join(lines) or "(无场景摘要)"
        return content, len(content)

    async def _build_master_plan(self, project_id) -> tuple[str, int]:
        chapters = await self.storage.get_chapter_outlines(project_id)
        lines = []
        for ch in (chapters or []):
            lines.append(f"第{ch.get('chapter_number', '?')}章: {ch.get('title', '')} —— {ch.get('summary', '')}")
        content = "\n".join(lines) or "(无大纲数据)"
        return content, len(content)
