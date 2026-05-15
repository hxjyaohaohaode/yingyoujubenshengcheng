import logging
from typing import Optional, TYPE_CHECKING

from sqlalchemy.ext.asyncio import AsyncSession

from core.gateway.client import ModelGateway
from core.rag.retriever import RAGRetriever
from core.search.search_models import KnowledgeCard
from .intent_models import IntentResult

if TYPE_CHECKING:
    from core.search.web_search import WebSearchService

logger = logging.getLogger(__name__)

AGENT_KNOWLEDGE_MAP = {
    "world_builder": ["world_elements", "era", "key_events", "entities"],
    "character_designer": ["entities", "key_events", "era"],
    "relation_network_designer": ["entities"],
    "foreshadow_designer": ["key_events", "entities", "world_elements"],
    "foreshadow_reaction": ["entities"],
    "wow_plan_designer": ["key_events", "entities"],
    "chapter_outliner": ["key_events", "entities", "world_elements"],
    "scene_writer": ["entities", "key_events", "world_elements", "era"],
    "rag_retriever": ["entities", "key_events"],
    "choice_designer": ["entities", "key_events"],
}


class ContextManager:
    def __init__(self, db: AsyncSession, gateway: ModelGateway,
                 rag: RAGRetriever, search: 'WebSearchService'):
        self.db = db
        self.gateway = gateway
        self.rag = rag
        self.search = search

    async def enrich_prompt(self, agent_name: str, base_prompt: str,
                            project_id: str, intent: Optional[IntentResult] = None,
                            search_cards: Optional[list[KnowledgeCard]] = None,
                            upload_chunks: Optional[list[str]] = None) -> str:
        knowledge_text = await self._build_knowledge_context(
            agent_name, project_id, intent, search_cards, upload_chunks
        )

        if not knowledge_text:
            return base_prompt

        if not base_prompt:
            return knowledge_text

        enriched = (
            "========== 参考知识上下文 ==========\n"
            "【重要指令】以下提供的参考信息必须作为你生成内容的基础依据，"
            "确保生成的内容与这些参考信息保持高度一致。\n\n"
            f"{knowledge_text}\n"
            "========================================\n\n"
            f"{base_prompt}"
        )
        return enriched

    async def _build_knowledge_context(self, agent_name: str, project_id: str,
                                        intent: Optional[IntentResult],
                                        search_cards: Optional[list[KnowledgeCard]],
                                        upload_chunks: Optional[list[str]]) -> str:
        parts = []

        if intent:
            intent_text = self._format_intent(intent)
            if intent_text:
                parts.append(f"### 意图分析结果\n{intent_text}")

        if search_cards:
            filtered = self._filter_for_agent(search_cards, agent_name)
            if filtered:
                cards_text = "\n\n".join(c.to_prompt_text() for c in filtered[:5])
                parts.append(f"### 联网搜索知识\n{cards_text}")

        if upload_chunks:
            upload_text = "\n\n".join(f"- {chunk[:500]}" for chunk in upload_chunks[:5] if chunk)
            if upload_text:
                parts.append(f"### 用户上传参考资料\n{upload_text}")

        return "\n\n".join(parts)

    def _format_intent(self, intent: IntentResult) -> str:
        lines = []
        if intent.genre:
            lines.append(f"**题材**: {intent.genre}")
        if intent.style:
            lines.append(f"**风格**: {intent.style}")
        if intent.era:
            lines.append(f"**时代背景**: {intent.era}")
        if intent.entities:
            entity_list = ", ".join(f"{e.name}({e.type})" for e in intent.entities[:10])
            lines.append(f"**关键实体**: {entity_list}")
        if intent.key_events:
            lines.append(f"**关键事件**: {', '.join(intent.key_events[:10])}")
        if intent.world_elements:
            lines.append(f"**世界观要素**: {', '.join(intent.world_elements[:10])}")
        return "\n".join(lines)

    def _filter_for_agent(self, cards: list[KnowledgeCard], agent_name: str) -> list[KnowledgeCard]:
        relevant_types = AGENT_KNOWLEDGE_MAP.get(agent_name, ["entities"])
        filtered = []
        for card in cards:
            if card.entity_type in relevant_types or "entities" in relevant_types:
                filtered.append(card)
            elif any(rt in card.entity_type for rt in relevant_types):
                filtered.append(card)
        return filtered

    async def get_upload_chunks(self, project_id: str) -> list[str]:
        try:
            from sqlalchemy import text
            result = await self.db.execute(
                text(
                    "SELECT chunk_text FROM embeddings WHERE project_id = :pid "
                    "AND content_type = 'user_upload' ORDER BY metadata LIMIT 10"
                ),
                {"pid": project_id},
            )
            return [row[0] for row in result.fetchall() if row[0]]
        except Exception as e:
            logger.warning("获取上传资料片段失败: %s", str(e)[:200])
            return []

    async def index_uploaded_document(self, project_id: str, doc_id: str,
                                       text: str, filename: str):
        from core.rag.indexer import RAGIndexer

        indexer = RAGIndexer(self.db)
        try:
            await indexer.index_content(
                project_id=project_id,
                content_type="user_upload",
                content_id=doc_id,
                text=text,
                metadata={"filename": filename},
            )
            logger.info("上传文档已索引: %s", filename)
        except Exception as e:
            logger.error("上传文档索引失败: %s - %s", filename, str(e)[:200])
            raise