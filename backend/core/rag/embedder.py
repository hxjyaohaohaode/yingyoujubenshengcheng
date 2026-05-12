"""
Embedding 调用封装。
"""

import os
import httpx


class Embedder:
    """DeepSeek Embedding 调用"""

    def __init__(self):
        self.base_url = "https://api.deepseek.com/v1"
        self.api_key = os.getenv("DEEPSEEK_API_KEY")
        self.dimension = 1536

    async def embed(self, text: str) -> list[float]:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                f"{self.base_url}/embeddings",
                json={"input": text, "model": "deepseek-embedding"},
                headers={"Authorization": f"Bearer {self.api_key}"},
            )
            resp.raise_for_status()
            return resp.json()["data"][0]["embedding"]

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                f"{self.base_url}/embeddings",
                json={"input": texts, "model": "deepseek-embedding"},
                headers={"Authorization": f"Bearer {self.api_key}"},
            )
            resp.raise_for_status()
            data = sorted(resp.json()["data"], key=lambda x: x["index"])
            return [item["embedding"] for item in data]
