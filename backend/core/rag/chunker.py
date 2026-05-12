"""
文本分块器: 将不同类型的文本按最优策略切分为 chunks。
"""

from dataclasses import dataclass
from typing import Literal


@dataclass
class Chunk:
    text: str
    metadata: dict
    chunk_type: str


class TextChunker:
    """文本分块器，支持多种策略"""

    def chunk(self, text: str, content_type: str,
              metadata: dict | None = None) -> list[Chunk]:
        metadata = metadata or {}
        strategy = {
            "scene": self._chunk_scene,
            "character": self._chunk_character,
            "foreshadow": self._chunk_foreshadow,
            "world": self._chunk_world,
        }.get(content_type, self._chunk_generic)

        return strategy(text, metadata)

    def _chunk_scene(self, text: str, metadata: dict) -> list[Chunk]:
        chunks = []

        paragraphs = text.split("\n\n")
        current_chunk = ""
        current_type = "narration"

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue

            if para.startswith("对白") or para.startswith("dialogue"):
                chunk_type = "dialogue"
            elif para.startswith("伏笔") or para.startswith("foreshadow"):
                chunk_type = "foreshadow"
            elif para.startswith("选择") or para.startswith("choice"):
                chunk_type = "choice"
            elif para.startswith("因果") or para.startswith("causal"):
                chunk_type = "causal"
            else:
                chunk_type = "narration"

            if chunk_type != current_type and current_chunk:
                chunks.append(Chunk(
                    text=current_chunk.strip(),
                    metadata={**metadata, "chunk_type": current_type},
                    chunk_type=current_type,
                ))
                current_chunk = ""

            current_chunk += para + "\n\n"
            current_type = chunk_type

            if len(current_chunk) > 500:
                chunks.append(Chunk(
                    text=current_chunk.strip(),
                    metadata={**metadata, "chunk_type": current_type},
                    chunk_type=current_type,
                ))
                current_chunk = ""

        if current_chunk.strip():
            chunks.append(Chunk(
                text=current_chunk.strip(),
                metadata={**metadata, "chunk_type": current_type},
                chunk_type=current_type,
            ))

        return chunks

    def _chunk_character(self, text: str, metadata: dict) -> list[Chunk]:
        fields = ["背景", "动机", "恐惧", "表面形象", "真实面目",
                   "语言风格", "口头禅", "必然行为", "绝对不会", "需要铺垫"]
        chunks = []
        current_field = "basic"
        current_text = ""

        for line in text.split("\n"):
            matched = False
            for field in fields:
                if field in line:
                    if current_text.strip():
                        chunks.append(Chunk(
                            text=current_text.strip(),
                            metadata={**metadata, "field": current_field},
                            chunk_type="field",
                        ))
                    current_field = field
                    current_text = line + "\n"
                    matched = True
                    break
            if not matched:
                current_text += line + "\n"

        if current_text.strip():
            chunks.append(Chunk(
                text=current_text.strip(),
                metadata={**metadata, "field": current_field},
                chunk_type="field",
            ))
        return chunks

    def _chunk_foreshadow(self, text: str, metadata: dict) -> list[Chunk]:
        layers = ["表面层", "深层", "真相层", "埋设", "强化", "揭露"]
        chunks = []
        current_layer = "overview"
        current_text = ""

        for line in text.split("\n"):
            matched = False
            for layer in layers:
                if layer in line:
                    if current_text.strip():
                        chunks.append(Chunk(
                            text=current_text.strip(),
                            metadata={**metadata, "layer": current_layer},
                            chunk_type="foreshadow",
                        ))
                    current_layer = layer
                    current_text = line + "\n"
                    matched = True
                    break
            if not matched:
                current_text += line + "\n"

        if current_text.strip():
            chunks.append(Chunk(
                text=current_text.strip(),
                metadata={**metadata, "layer": current_layer},
                chunk_type="foreshadow",
            ))
        return chunks

    def _chunk_world(self, text: str, metadata: dict) -> list[Chunk]:
        return self._sliding_window(text, metadata, window=500, overlap=100)

    def _chunk_generic(self, text: str, metadata: dict) -> list[Chunk]:
        return self._sliding_window(text, metadata, window=500, overlap=100)

    def _sliding_window(self, text: str, metadata: dict,
                        window: int = 500, overlap: int = 100) -> list[Chunk]:
        chunks = []
        start = 0
        while start < len(text):
            end = start + window
            chunk_text = text[start:end]
            chunks.append(Chunk(
                text=chunk_text,
                metadata={**metadata, "position": start},
                chunk_type="generic",
            ))
            start = end - overlap
        return chunks
