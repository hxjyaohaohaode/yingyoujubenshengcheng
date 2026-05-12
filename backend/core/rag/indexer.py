"""
RAG 索引器: 在内容定稿后自动建立向量索引。
"""

import json

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from .chunker import TextChunker
from .embedder import Embedder


class RAGIndexer:
    """RAG 索引器"""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.chunker = TextChunker()
        self.embedder = Embedder()

    async def index_content(
        self,
        project_id: str,
        content_type: str,
        content_id: str,
        text: str,
        metadata: dict | None = None,
    ):
        metadata = metadata or {}

        chunks = self.chunker.chunk(text, content_type, metadata)

        if not chunks:
            return

        texts = [c.text for c in chunks]
        embeddings = await self.embedder.embed_batch(texts)

        await self.db.execute(
            text("DELETE FROM embeddings WHERE project_id = :project_id AND content_id = :content_id"),
            {"project_id": project_id, "content_id": content_id},
        )

        for chunk, embedding in zip(chunks, embeddings):
            await self.db.execute(
                text(
                    """
                    INSERT INTO embeddings
                    (project_id, content_type, content_id, chunk_text, embedding, metadata)
                    VALUES (:project_id, :content_type, :content_id, :chunk_text, :embedding, :metadata)
                    """
                ),
                {
                    "project_id": project_id,
                    "content_type": content_type,
                    "content_id": content_id,
                    "chunk_text": chunk.text,
                    "embedding": embedding,
                    "metadata": json.dumps({**chunk.metadata, "chunk_type": chunk.chunk_type}),
                },
            )

        await self.db.commit()

    async def reindex_project(self, project_id: str):
        await self.db.execute(
            text("DELETE FROM embeddings WHERE project_id = :project_id"),
            {"project_id": project_id},
        )

        scene_result = await self.db.execute(
            text(
                "SELECT id, scene_code, narration, dialogue FROM scenes WHERE project_id = :project_id"
            ),
            {"project_id": project_id},
        )
        scenes = scene_result.fetchall()
        for scene in scenes:
            scene_id, scene_code, narration, dialogue = scene
            text_content = f"场景 {scene_code}\n{narration or ''}"
            if dialogue:
                dialogues = json.loads(dialogue) if isinstance(dialogue, str) else dialogue
                for d in dialogues:
                    text_content += f"\n{d.get('char', '')}: {d.get('text', '')}"
            await self.index_content(
                project_id, "scene", str(scene_id), text_content,
                {"scene_code": scene_code}
            )

        char_result = await self.db.execute(
            text(
                "SELECT id, name, background, core_goal, language_style FROM characters WHERE project_id = :project_id"
            ),
            {"project_id": project_id},
        )
        characters = char_result.fetchall()
        for char in characters:
            char_id, name, background, core_goal, language_style = char
            text_content = f"角色: {name}\n背景: {background or ''}\n目标: {core_goal or ''}\n语言风格: {language_style or ''}"
            await self.index_content(
                project_id, "character", str(char_id), text_content,
                {"name": name}
            )

        fs_result = await self.db.execute(
            text(
                "SELECT id, fs_code, name, surface_layer, deep_layer, truth_layer FROM foreshadows WHERE project_id = :project_id"
            ),
            {"project_id": project_id},
        )
        foreshadows = fs_result.fetchall()
        for fs in foreshadows:
            fs_id, fs_code, name, surface_layer, deep_layer, truth_layer = fs
            text_content = f"伏笔 {fs_code}: {name}\n表面: {surface_layer or ''}\n深层: {deep_layer or ''}\n真相: {truth_layer or ''}"
            await self.index_content(
                project_id, "foreshadow", str(fs_id), text_content,
                {"fs_code": fs_code, "name": name}
            )
