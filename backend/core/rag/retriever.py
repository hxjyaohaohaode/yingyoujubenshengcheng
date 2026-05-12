"""
RAG 检索器: 根据查询语义检索最相关的上下文片段。

SQLite 模式下使用改进的中文分词关键词匹配作为降级方案，
PostgreSQL + pgvector 模式下使用向量相似度检索。
"""

import json
import re
import logging
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from config import DATABASE_URL

logger = logging.getLogger(__name__)

_IS_SQLITE = DATABASE_URL.startswith("sqlite")

_CN_STOPWORDS = frozenset({
    "的", "了", "在", "是", "我", "有", "和", "就", "不", "人", "都", "一",
    "一个", "上", "也", "很", "到", "说", "要", "去", "你", "会", "着", "没有",
    "看", "好", "自己", "这", "他", "她", "它", "们", "那", "被", "从", "把",
    "让", "对", "又", "与", "而", "但", "却", "如果", "因为", "所以", "虽然",
    "可以", "这个", "那个", "什么", "怎么", "如何", "为什么", "哪", "哪里",
})


def _tokenize_chinese(query: str) -> list[str]:
    tokens = []
    query = re.sub(r'[，。！？、；：\u201c\u201d\u2018\u2019\uff08\uff09\u3010\u3011\u300a\u300b\s\d]+', ' ', query)
    parts = query.split()
    for part in parts:
        if not part:
            continue
        if re.match(r'^[a-zA-Z]+$', part):
            if len(part) >= 2:
                tokens.append(part.lower())
        else:
            for i in range(len(part)):
                for length in range(2, min(5, len(part) - i + 1)):
                    sub = part[i:i + length]
                    if sub not in _CN_STOPWORDS:
                        tokens.append(sub)
            if len(part) == 1 and part not in _CN_STOPWORDS:
                tokens.append(part)
    return tokens


def _in_placeholder(param_name: str, values: list) -> tuple[str, dict]:
    names = []
    params = {}
    for i, v in enumerate(values):
        k = f"{param_name}_{i}"
        names.append(f":{k}")
        params[k] = v
    return ", ".join(names), params


@dataclass
class RetrievedChunk:
    text: str
    content_type: str
    content_id: str
    score: float
    metadata: dict


class RAGRetriever:
    """RAG 检索器"""

    def __init__(self, db: AsyncSession):
        self.db = db
        if not _IS_SQLITE:
            try:
                from .embedder import Embedder
                self.embedder = Embedder()
            except Exception:
                self.embedder = None  # type: ignore
        else:
            self.embedder = None  # type: ignore

    async def retrieve(
        self,
        project_id: str,
        query: str,
        content_types: list[str] | None = None,
        top_k: int = 5,
    ) -> list[RetrievedChunk]:
        if _IS_SQLITE:
            return await self._retrieve_sqlite(project_id, query, content_types, top_k)
        return await self._retrieve_pgvector(project_id, query, content_types, top_k)

    async def _retrieve_sqlite(
        self,
        project_id: str,
        query: str,
        content_types: list[str] | None = None,
        top_k: int = 5,
    ) -> list[RetrievedChunk]:
        results = []
        keywords = _tokenize_chinese(query)
        if not keywords:
            keywords = query.replace("，", " ").replace("、", " ").split()

        if not content_types or "scene" in content_types:
            scene_params = {"project_id": project_id, "top_k": top_k * 3}
            if keywords:
                like_parts = " OR ".join([f"narration LIKE :kw_{i}" for i in range(len(keywords))])
                kw_params = {f"kw_{i}": f"%{kw}%" for i, kw in enumerate(keywords)}
                scene_params.update(kw_params)
            else:
                like_parts = "1=1"

            try:
                result = await self.db.execute(
                    text(
                        f"SELECT id, narration, scene_code, scene_type, emotion_level FROM scenes "
                        f"WHERE project_id = :project_id AND ({like_parts}) "
                        f"ORDER BY scene_code LIMIT :top_k"
                    ),
                    scene_params,
                )
            except Exception:
                result = await self.db.execute(
                    text(
                        "SELECT id, narration, scene_code, scene_type, emotion_level FROM scenes "
                        "WHERE project_id = :project_id "
                        "ORDER BY scene_code LIMIT :top_k"
                    ),
                    {"project_id": project_id, "top_k": top_k},
                )

            for row in result.fetchall():
                narration = row[1] or ""
                scene_code = row[2] or ""
                scene_type = row[3] or ""
                score = 0.0
                for kw in keywords:
                    if kw in narration:
                        score += 0.3
                    if kw in scene_code or kw in scene_type:
                        score += 0.2
                if score == 0 and keywords:
                    continue
                if not keywords:
                    score = 0.1
                results.append(RetrievedChunk(
                    text=narration,
                    content_type="scene",
                    content_id=str(row[0]),
                    score=score,
                    metadata={"scene_code": scene_code, "scene_type": scene_type},
                ))

        if not content_types or "character" in content_types:
            try:
                char_result = await self.db.execute(
                    text("SELECT id, name, description, background, core_goal FROM characters WHERE project_id = :project_id"),
                    {"project_id": project_id},
                )
            except Exception:
                try:
                    char_result = await self.db.execute(
                        text("SELECT id, name, description FROM characters WHERE project_id = :project_id"),
                        {"project_id": project_id},
                    )
                except Exception:
                    char_result = None

            if char_result:
                for row in char_result.fetchall():
                    desc = row[2] if len(row) > 2 else ""
                    name = row[1] or ""
                    background = row[3] if len(row) > 3 else ""
                    core_goal = row[4] if len(row) > 4 else ""
                    full_text = f"{name} {desc} {background} {core_goal}"
                    score = 0.0
                    for kw in keywords:
                        if kw in full_text:
                            score += 0.3
                    if score > 0 or not keywords:
                        results.append(RetrievedChunk(
                            text=f"{name}: {desc}",
                            content_type="character",
                            content_id=str(row[0]),
                            score=max(score, 0.1) if not keywords else score,
                            metadata={"name": name},
                        ))

        if not content_types or "foreshadow" in content_types:
            try:
                fs_result = await self.db.execute(
                    text("SELECT id, name, description, status FROM foreshadows WHERE project_id = :project_id"),
                    {"project_id": project_id},
                )
            except Exception:
                try:
                    fs_result = await self.db.execute(
                        text("SELECT id, name FROM foreshadows WHERE project_id = :project_id"),
                        {"project_id": project_id},
                    )
                except Exception:
                    fs_result = None

            if fs_result:
                for row in fs_result.fetchall():
                    desc = row[2] if len(row) > 2 else ""
                    name = row[1] or ""
                    status = row[3] if len(row) > 3 else ""
                    full_text = f"{name} {desc} {status}"
                    score = 0.0
                    for kw in keywords:
                        if kw in full_text:
                            score += 0.3
                    if score > 0 or not keywords:
                        results.append(RetrievedChunk(
                            text=f"{name}: {desc}",
                            content_type="foreshadow",
                            content_id=str(row[0]),
                            score=max(score, 0.1) if not keywords else score,
                            metadata={"name": name},
                        ))

        if not content_types or "world" in content_types:
            try:
                world_result = await self.db.execute(
                    text("SELECT key, value FROM world_config WHERE project_id = :project_id"),
                    {"project_id": project_id},
                )
                for row in world_result.fetchall():
                    key = row[0] or ""
                    val = row[1] or ""
                    if isinstance(val, str) and len(val) > 10:
                        score = 0.0
                        for kw in keywords:
                            if kw in val or kw in key:
                                score += 0.3
                        if score > 0 or not keywords:
                            results.append(RetrievedChunk(
                                text=f"【{key}】{val}",
                                content_type="world",
                                content_id=key,
                                score=max(score, 0.1) if not keywords else score,
                                metadata={"key": key},
                            ))
            except Exception:
                pass

        results.sort(key=lambda x: -x.score)
        return results[:top_k]

    async def _retrieve_pgvector(
        self,
        project_id: str,
        query: str,
        content_types: list[str] | None = None,
        top_k: int = 5,
    ) -> list[RetrievedChunk]:
        if not self.embedder:
            return await self._retrieve_sqlite(project_id, query, content_types, top_k)

        query_embedding = await self.embedder.embed(query)
        embedding_str = str(query_embedding)

        params = {"project_id": project_id, "embedding": embedding_str, "top_k": top_k}

        type_filter = ""
        if content_types:
            placeholders, type_params = _in_placeholder("ct", content_types)
            type_filter = f"AND content_type IN ({placeholders})"
            params.update(type_params)

        try:
            result = await self.db.execute(
                text(
                    f"""
                    SELECT
                        content_type, content_id, chunk_text, metadata,
                        1 - (embedding <=> :embedding) as score
                    FROM embeddings
                    WHERE project_id = :project_id {type_filter}
                    ORDER BY embedding <=> :embedding
                    LIMIT :top_k
                    """
                ),
                params,
            )
            rows = result.fetchall()

            return [
                RetrievedChunk(
                    text=row[2],
                    content_type=row[0],
                    content_id=row[1],
                    score=float(row[4]),
                    metadata=row[3] if isinstance(row[3], dict) else json.loads(row[3] or "{}"),
                )
                for row in rows
            ]
        except Exception:
            return await self._retrieve_sqlite(project_id, query, content_types, top_k)

    async def retrieve_for_scene(
        self,
        project_id: str,
        scene_id: str,
        requirements: dict,
    ) -> list[RetrievedChunk]:
        query_parts = [f"场景 {scene_id}"]
        if requirements.get("scene_type"):
            query_parts.append(f"类型: {requirements['scene_type']}")
        if requirements.get("emotion_target"):
            query_parts.append(f"情感强度: {requirements['emotion_target']}/10")
        for fs_task in requirements.get("foreshadow_tasks", []):
            query_parts.append(f"伏笔 {fs_task.get('fs_id', '')} {fs_task.get('op', '')}")
        if requirements.get("is_wow_moment"):
            query_parts.append(f"哇塞时刻 {requirements.get('wow_type', '')}")

        query = "，".join(query_parts)

        results = []

        scene_chunks = await self._search_by_type(
            project_id, query, "scene", top_k=3
        )
        results.extend(scene_chunks)

        char_ids = requirements.get("character_ids", [])
        if char_ids:
            char_chunks = await self._search_by_ids(
                project_id, query, "character", char_ids, top_k=5
            )
            results.extend(char_chunks)
        else:
            char_chunks = await self._search_by_type(
                project_id, query, "character", top_k=5
            )
            results.extend(char_chunks)

        fs_chunks = await self._search_by_type(
            project_id, query, "foreshadow", top_k=3
        )
        results.extend(fs_chunks)

        world_chunks = await self._search_by_type(
            project_id, query, "world", top_k=2
        )
        results.extend(world_chunks)

        seen = {}
        for chunk in results:
            key = chunk.content_id
            if key not in seen or chunk.score > seen[key].score:
                seen[key] = chunk

        return sorted(seen.values(), key=lambda x: -x.score)

    async def _search_by_type(
        self, project_id, query, content_type, top_k
    ) -> list[RetrievedChunk]:
        if _IS_SQLITE:
            return await self._retrieve_sqlite(project_id, query, [content_type], top_k)

        if not self.embedder:
            return await self._retrieve_sqlite(project_id, query, [content_type], top_k)

        query_embedding = await self.embedder.embed(query)
        embedding_str = str(query_embedding)
        try:
            result = await self.db.execute(
                text(
                    """
                    SELECT content_id, chunk_text, metadata,
                           1 - (embedding <=> :embedding) as score
                    FROM embeddings
                    WHERE project_id = :project_id AND content_type = :content_type
                    ORDER BY embedding <=> :embedding
                    LIMIT :top_k
                    """
                ),
                {
                    "project_id": project_id,
                    "content_type": content_type,
                    "embedding": embedding_str,
                    "top_k": top_k,
                },
            )
            rows = result.fetchall()

            return [
                RetrievedChunk(
                    text=row[1],
                    content_type=content_type,
                    content_id=row[0],
                    score=float(row[3]),
                    metadata=row[2] if isinstance(row[2], dict) else json.loads(row[2] or "{}"),
                )
                for row in rows
            ]
        except Exception:
            return await self._retrieve_sqlite(project_id, query, [content_type], top_k)

    async def _search_by_ids(
        self, project_id, query, content_type, ids, top_k
    ) -> list[RetrievedChunk]:
        if _IS_SQLITE:
            return await self._retrieve_sqlite(project_id, query, [content_type], top_k)

        if not self.embedder:
            return await self._retrieve_sqlite(project_id, query, [content_type], top_k)

        query_embedding = await self.embedder.embed(query)
        embedding_str = str(query_embedding)
        placeholders, id_params = _in_placeholder("sid", [str(i) for i in ids])
        try:
            result = await self.db.execute(
                text(
                    f"""
                    SELECT content_id, chunk_text, metadata,
                           1 - (embedding <=> :embedding) as score
                    FROM embeddings
                    WHERE project_id = :project_id AND content_type = :content_type AND content_id IN ({placeholders})
                    ORDER BY embedding <=> :embedding
                    LIMIT :top_k
                    """
                ),
                {
                    "project_id": project_id,
                    "content_type": content_type,
                    "embedding": embedding_str,
                    "top_k": top_k,
                    **id_params,
                },
            )
            rows = result.fetchall()

            return [
                RetrievedChunk(
                    text=row[1],
                    content_type=content_type,
                    content_id=row[0],
                    score=float(row[3]),
                    metadata=row[2] if isinstance(row[2], dict) else json.loads(row[2] or "{}"),
                )
                for row in rows
            ]
        except Exception:
            return await self._retrieve_sqlite(project_id, query, [content_type], top_k)
