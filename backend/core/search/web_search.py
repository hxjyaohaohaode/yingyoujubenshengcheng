import json
import time
import asyncio
import logging
import hashlib
from datetime import datetime, UTC
from typing import Optional

import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from core.context.intent_models import EntityInfo
from .search_models import SearchResult, KnowledgeCard

logger = logging.getLogger(__name__)

WEB_SEARCH_ENABLED = True
WEB_SEARCH_MAX_RESULTS = 5
WEB_SEARCH_TIMEOUT = 30
WEB_SEARCH_CACHE_TTL = 86400
RELEVANCE_THRESHOLD = 0.3


class WebSearchService:
    def __init__(self, db: AsyncSession, gateway=None):
        self.db = db
        self.gateway = gateway
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(connect=15.0, read=WEB_SEARCH_TIMEOUT, write=15.0, pool=15.0),
            limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
        )

    async def search_entity(self, entity_name: str, context: str = "", force: bool = False) -> list[SearchResult]:
        if not WEB_SEARCH_ENABLED:
            return []

        cache_key = hashlib.md5(f"{entity_name}:{context}".encode()).hexdigest()
        if not force:
            cached = await self._get_from_cache(cache_key)
            if cached:
                logger.info("搜索缓存命中: %s", entity_name)
                return cached

        results = []
        for attempt in range(3):
            try:
                results = await self._do_search(entity_name, context)
                break
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 429 and attempt < 2:
                    await asyncio.sleep(2 ** attempt)
                    continue
                break
            except (httpx.TimeoutException, httpx.ConnectError) as e:
                if attempt < 2:
                    await asyncio.sleep(2 ** attempt)
                    continue
                break

        filtered = [r for r in results if r.relevance_score >= RELEVANCE_THRESHOLD][:WEB_SEARCH_MAX_RESULTS]
        for r in filtered:
            r.searched_at = datetime.now(UTC).isoformat()
        if filtered:
            await self._save_to_cache(cache_key, filtered)

        if not filtered and self.gateway:
            llm_card = await self._llm_fallback_knowledge(entity_name, context)
            if llm_card:
                filtered.append(SearchResult(
                    entity_name=entity_name, title=f"{entity_name} - AI知识补充",
                    snippet=llm_card.summary, url="", source="llm_internal",
                    relevance_score=0.8,
                ))

        return filtered

    async def batch_search(self, entities: list[EntityInfo], context: str = "") -> list[KnowledgeCard]:
        cards = []
        seen = set()
        for entity in entities:
            if entity.name in seen:
                continue
            seen.add(entity.name)
            results = await self.search_entity(entity.name, context)
            if results:
                summary = results[0].snippet[:300] if results[0].snippet else ""
                cards.append(KnowledgeCard(
                    entity_name=entity.name, entity_type=entity.type, summary=summary,
                    key_facts=[r.snippet[:150] for r in results[:5] if r.snippet],
                    sources=[r.url for r in results if r.url],
                    raw_text="\n".join(r.snippet for r in results if r.snippet),
                ))
            else:
                cards.append(KnowledgeCard(entity_name=entity.name, entity_type=entity.type, summary="(LLM内部知识)"))
        return cards

    async def _do_search(self, entity_name: str, context: str) -> list[SearchResult]:
        query = f"{entity_name} {context}" if context else entity_name
        search_url = f"https://html.duckduckgo.com/html/?q={query}"
        try:
            resp = await self._client.get(search_url, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "text/html,application/xhtml+xml",
            }, follow_redirects=True)
            resp.raise_for_status()
            return self._parse_ddg_results(resp.text, entity_name)
        except Exception:
            if self.gateway:
                return await self._llm_search_simulation(entity_name, context)
            return []

    def _parse_ddg_results(self, html: str, entity_name: str) -> list[SearchResult]:
        import re
        results = []
        link_pattern = re.compile(r'<a[^>]*class="result__a"[^>]*href="([^"]*)"[^>]*>(.*?)</a>', re.DOTALL)
        snippet_pattern = re.compile(r'<a[^>]*class="result__snippet"[^>]*>(.*?)</a>', re.DOTALL)
        link_matches = link_pattern.findall(html)
        snippet_matches = snippet_pattern.findall(html)
        for i, (url, title) in enumerate(link_matches[:WEB_SEARCH_MAX_RESULTS]):
            title_clean = re.sub(r'<[^>]+>', '', title).strip()
            snippet = re.sub(r'<[^>]+>', '', snippet_matches[i]).strip() if i < len(snippet_matches) else ""
            if title_clean:
                results.append(SearchResult(
                    entity_name=entity_name, title=title_clean, snippet=snippet[:500],
                    url=url if url.startswith("http") else "", source="duckduckgo",
                    relevance_score=0.8 if entity_name.lower() in (title_clean + snippet).lower() else 0.4,
                ))
        return results

    async def _llm_search_simulation(self, entity_name: str, context: str) -> list[SearchResult]:
        prompt = f'请提供关于"{entity_name}"的百科式简要介绍（3-5句话）。上下文：{context}'
        try:
            response = await self.gateway.invoke(
                intent="write.creative", messages=[{"role": "user", "content": prompt}],
                cost_profile="economy", temperature=0.3, max_tokens=600, use_cache=False,
            )
            return [SearchResult(entity_name=entity_name, title=f"{entity_name} - AI知识", snippet=response.content.strip()[:500],
                                 url="", source="llm_simulated", relevance_score=0.9)]
        except Exception:
            return []

    async def _llm_fallback_knowledge(self, entity_name: str, context: str) -> Optional[KnowledgeCard]:
        try:
            response = await self.gateway.invoke(
                intent="write.creative",
                messages=[{"role": "user", "content": f'请提供"{entity_name}"的简要百科知识。'}],
                cost_profile="economy",
                temperature=0.3,
                max_tokens=400,
                use_cache=False,
            )
            text = response.content.strip()
            return KnowledgeCard(entity_name=entity_name, entity_type="unknown", summary=text[:300], sources=["LLM内部知识"])
        except Exception:
            return None

    async def _get_from_cache(self, cache_key: str) -> Optional[list[SearchResult]]:
        try:
            result = await self.db.execute(
                text("SELECT result_json FROM search_cache WHERE cache_key = :key "
                     "AND datetime(searched_at, '+' || ttl || ' seconds') > datetime('now')"),
                {"key": cache_key},
            )
            row = result.fetchone()
            if row:
                data = json.loads(row[0])
                return [SearchResult(**r) for r in data]
        except Exception:
            pass
        return None

    async def _save_to_cache(self, cache_key: str, results: list[SearchResult]):
        try:
            data = json.dumps([
                {"entity_name": r.entity_name, "title": r.title, "snippet": r.snippet,
                 "url": r.url, "source": r.source, "relevance_score": r.relevance_score,
                 "saved": True, "searched_at": r.searched_at}
                for r in results
            ], ensure_ascii=False)
            await self.db.execute(
                text("INSERT OR REPLACE INTO search_cache(cache_key, entity_name, result_json, searched_at, ttl) "
                     "VALUES(:key, :name, :json, datetime('now'), :ttl)"),
                {"key": cache_key, "name": results[0].entity_name if results else "", "json": data, "ttl": WEB_SEARCH_CACHE_TTL},
            )
            await self.db.commit()
        except Exception:
            pass

    async def close(self):
        await self._client.aclose()