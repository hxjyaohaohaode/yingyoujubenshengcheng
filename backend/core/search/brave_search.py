import os
import re
import json
import time
import asyncio
import logging
from typing import AsyncGenerator, Optional
from dataclasses import dataclass, field

import httpx

logger = logging.getLogger(__name__)

BRAVE_API_KEY = os.getenv("BRAVE_API_KEY", "")
SERPAPI_KEY = os.getenv("SERPAPI_KEY", "")
BING_API_KEY = os.getenv("BING_API_KEY", "")

FAST_LLM_API_KEY = os.getenv("FAST_LLM_API_KEY", os.getenv("DEEPSEEK_API_KEY", ""))
FAST_LLM_BASE_URL = os.getenv("FAST_LLM_BASE_URL", "https://api.deepseek.com/v1")
FAST_LLM_MODEL = os.getenv("FAST_LLM_MODEL", "deepseek-chat")

SEARCH_TIMEOUT = 3.0
SCRAPE_TIMEOUT = 1.5
MAX_SCRAPE_RESULTS = 3
SCRAPE_MAX_CHARS = 3000


@dataclass
class WebSearchResult:
    title: str
    url: str
    snippet: str
    source: str = "brave"
    full_text: str = ""


@dataclass
class SearchStreamEvent:
    phase: str = ""
    data: dict = field(default_factory=dict)


def _extract_text_from_html(html: str) -> str:
    text = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<nav[^>]*>.*?</nav>', '', text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<header[^>]*>.*?</header>', '', text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<footer[^>]*>.*?</footer>', '', text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<[^>]+>', ' ', text)
    text = re.sub(r'&nbsp;', ' ', text)
    text = re.sub(r'&amp;', '&', text)
    text = re.sub(r'&lt;', '<', text)
    text = re.sub(r'&gt;', '>', text)
    text = re.sub(r'&quot;', '"', text)
    text = re.sub(r'&#\d+;', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    sentences = re.split(r'(?<=[。！？.!?\n])\s*', text)
    meaningful = [s.strip() for s in sentences if len(s.strip()) > 20]
    return ' '.join(meaningful)


class BraveSearchService:

    def __init__(self):
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(connect=5.0, read=10.0, write=5.0, pool=5.0),
                limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
            )
        return self._client

    async def close(self):
        if self._client:
            await self._client.aclose()
            self._client = None

    async def search_web(self, query: str) -> list[WebSearchResult]:
        results: list[WebSearchResult] = []

        tasks = []
        if BRAVE_API_KEY:
            tasks.append(self._search_brave(query))
        if SERPAPI_KEY:
            tasks.append(self._search_serpapi(query))
        if BING_API_KEY:
            tasks.append(self._search_bing(query))

        if not tasks:
            logger.warning("无搜索引擎API Key配置，使用DuckDuckGo备用搜索")
            tasks.append(self._search_duckduckgo(query))

        gathered = await asyncio.gather(*tasks, return_exceptions=True)
        for r in gathered:
            if isinstance(r, list):
                results.extend(r)
            elif isinstance(r, Exception):
                logger.warning("搜索源失败: %s", str(r)[:100])

        seen = set()
        deduped = []
        for r in results:
            if r.url and r.url in seen:
                continue
            if r.url:
                seen.add(r.url)
            deduped.append(r)

        deduped.sort(key=lambda x: len(x.snippet), reverse=True)
        return deduped[:5]

    async def _search_brave(self, query: str) -> list[WebSearchResult]:
        client = await self._get_client()
        try:
            resp = await client.get(
                "https://api.search.brave.com/res/v1/web/search",
                params={"q": query, "count": 5, "search_lang": "zh"},
                headers={
                    "Accept": "application/json",
                    "Accept-Encoding": "gzip",
                    "X-Subscription-Token": BRAVE_API_KEY,
                },
                timeout=SEARCH_TIMEOUT,
            )
            resp.raise_for_status()
            data = resp.json()
            results = []
            for item in (data.get("web", {}).get("results", []) or [])[:5]:
                results.append(WebSearchResult(
                    title=item.get("title", ""),
                    url=item.get("url", ""),
                    snippet=item.get("description", "")[:500],
                    source="brave",
                ))
            return results
        except Exception as e:
            logger.warning("Brave Search失败: %s", str(e)[:100])
            return []

    async def _search_serpapi(self, query: str) -> list[WebSearchResult]:
        client = await self._get_client()
        try:
            resp = await client.get(
                "https://serpapi.com/search",
                params={"q": query, "api_key": SERPAPI_KEY, "num": 5, "hl": "zh-CN"},
                timeout=SEARCH_TIMEOUT,
            )
            resp.raise_for_status()
            data = resp.json()
            results = []
            for item in (data.get("organic_results", []) or [])[:5]:
                results.append(WebSearchResult(
                    title=item.get("title", ""),
                    url=item.get("link", ""),
                    snippet=item.get("snippet", "")[:500],
                    source="serpapi",
                ))
            return results
        except Exception as e:
            logger.warning("SerpAPI搜索失败: %s", str(e)[:100])
            return []

    async def _search_bing(self, query: str) -> list[WebSearchResult]:
        client = await self._get_client()
        try:
            resp = await client.get(
                "https://api.bing.microsoft.com/v7.0/search",
                params={"q": query, "count": 5, "mkt": "zh-CN"},
                headers={"Ocp-Apim-Subscription-Key": BING_API_KEY},
                timeout=SEARCH_TIMEOUT,
            )
            resp.raise_for_status()
            data = resp.json()
            results = []
            for item in (data.get("webPages", {}).get("value", []) or [])[:5]:
                results.append(WebSearchResult(
                    title=item.get("name", ""),
                    url=item.get("url", ""),
                    snippet=item.get("snippet", "")[:500],
                    source="bing",
                ))
            return results
        except Exception as e:
            logger.warning("Bing搜索失败: %s", str(e)[:100])
            return []

    async def _search_duckduckgo(self, query: str) -> list[WebSearchResult]:
        client = await self._get_client()
        try:
            resp = await client.get(
                "https://html.duckduckgo.com/html/",
                params={"q": query},
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
                timeout=SEARCH_TIMEOUT,
                follow_redirects=True,
            )
            resp.raise_for_status()
            html = resp.text
            link_pattern = re.compile(r'<a[^>]*class="result__a"[^>]*href="([^"]*)"[^>]*>(.*?)</a>', re.DOTALL)
            snippet_pattern = re.compile(r'<a[^>]*class="result__snippet"[^>]*>(.*?)</a>', re.DOTALL)
            links = link_pattern.findall(html)
            snippets = snippet_pattern.findall(html)
            results = []
            for i, (url, title) in enumerate(links[:5]):
                title_clean = re.sub(r'<[^>]+>', '', title).strip()
                snippet = re.sub(r'<[^>]+>', '', snippets[i]).strip() if i < len(snippets) else ""
                if title_clean:
                    results.append(WebSearchResult(
                        title=title_clean,
                        url=url if url.startswith("http") else "",
                        snippet=snippet[:500],
                        source="duckduckgo",
                    ))
            return results
        except Exception as e:
            logger.warning("DuckDuckGo搜索失败: %s", str(e)[:100])
            return []

    async def scrape_urls(self, results: list[WebSearchResult]) -> list[WebSearchResult]:
        if not results:
            return results

        urls_to_scrape = [r for r in results[:MAX_SCRAPE_RESULTS] if r.url]
        if not urls_to_scrape:
            return results

        client = await self._get_client()
        scrape_tasks = []
        for r in urls_to_scrape:
            scrape_tasks.append(self._scrape_one(client, r))

        scraped = await asyncio.gather(*scrape_tasks, return_exceptions=True)
        for i, s in enumerate(scraped):
            if isinstance(s, Exception):
                logger.warning("抓取 %s 失败: %s", urls_to_scrape[i].url, str(s)[:80])
        return results

    async def _scrape_one(self, client: httpx.AsyncClient, result: WebSearchResult):
        try:
            resp = await client.get(
                result.url,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    "Accept": "text/html,application/xhtml+xml",
                },
                timeout=SCRAPE_TIMEOUT,
                follow_redirects=True,
            )
            if resp.status_code >= 400:
                return
            content_type = resp.headers.get("content-type", "")
            if "text/html" not in content_type:
                return
            text = _extract_text_from_html(resp.text)
            if len(text) > 100:
                result.full_text = text[:SCRAPE_MAX_CHARS]
        except (httpx.TimeoutException, httpx.ConnectError, httpx.ReadError):
            pass
        except Exception as e:
            logger.debug("抓取异常 %s: %s", result.url, str(e)[:80])

    async def stream_search(
        self,
        query: str,
        gateway=None,
    ) -> AsyncGenerator[str, None]:
        t0 = time.time()

        yield f"data: {json.dumps({'phase': 'searching', 'text': '🔎 AI正在搜集信息...'}, ensure_ascii=False)}\n\n"

        results = await self.search_web(query)
        t1 = time.time()
        logger.info("搜索完成: %d条结果, 耗时%.2fs", len(results), t1 - t0)

        if not results:
            yield f"data: {json.dumps({'phase': 'error', 'text': '未找到相关搜索结果，请尝试其他关键词'}, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"
            return

        yield f"data: {json.dumps({'phase': 'searching', 'text': f'🔎 已找到 {len(results)} 条结果，正在抓取网页内容...'}, ensure_ascii=False)}\n\n"

        await self.scrape_urls(results)
        t2 = time.time()
        logger.info("抓取完成, 耗时%.2fs", t2 - t1)

        yield f"data: {json.dumps({'phase': 'organizing', 'text': '📝 AI正在整理信息...'}, ensure_ascii=False)}\n\n"

        sources_block = "\n".join(
            f"- [{r.title}]({r.url})" for r in results if r.url
        )
        scraped_text = "\n\n---\n\n".join(
            f"来源: {r.title}\n{r.full_text}" for r in results if r.full_text
        )
        snippets_text = "\n".join(
            f"- {r.title}: {r.snippet}" for r in results if r.snippet
        )

        yield f"data: {json.dumps({'phase': 'sources', 'sources': [{'title': r.title, 'url': r.url, 'snippet': r.snippet, 'source': r.source} for r in results]}, ensure_ascii=False)}\n\n"

        combined = (
            f"搜索查询: {query}\n\n"
            f"搜索结果摘要:\n{snippets_text}\n\n"
            f"网页详细内容:\n{scraped_text[:4000]}" if scraped_text else snippets_text
        )

        summary_prompt = f"""你是一个专业的研究助手。请根据以下搜索结果，为用户整理一份清晰、全面、权威的信息摘要。

要求：
1. 按逻辑组织信息，分点列出关键事实
2. 优先使用权威来源的信息
3. 如果信息有矛盾，请标注
4. 最后列出所有来源

{combined}

请用中文回答。"""

        if gateway:
            yield f"data: {json.dumps({'phase': 'streaming_start'}, ensure_ascii=False)}\n\n"

            try:
                accumulated = ""
                async for chunk in self._stream_llm(gateway, summary_prompt):
                    accumulated += chunk
                    yield f"data: {json.dumps({'phase': 'streaming', 'text': chunk}, ensure_ascii=False)}\n\n"

                t3 = time.time()
                logger.info("LLM摘要完成, 总耗时%.2fs, 输出%d字", t3 - t0, len(accumulated))

                yield f"data: {json.dumps({'phase': 'complete', 'total_time': round(t3 - t0, 2)}, ensure_ascii=False)}\n\n"
            except Exception as e:
                logger.warning("LLM摘要失败，使用snippets: %s", str(e)[:100])
                yield f"data: {json.dumps({'phase': 'streaming', 'text': f'\n\n（AI摘要暂时不可用，以下是搜索结果摘要：）\n\n{snippets_text}'}, ensure_ascii=False)}\n\n"
                yield f"data: {json.dumps({'phase': 'complete'}, ensure_ascii=False)}\n\n"
        else:
            text = f"\n\n## 搜索结果摘要\n\n{snippets_text}"
            yield f"data: {json.dumps({'phase': 'streaming', 'text': text}, ensure_ascii=False)}\n\n"
            yield f"data: {json.dumps({'phase': 'complete'}, ensure_ascii=False)}\n\n"

        yield "data: [DONE]\n\n"

    async def _stream_llm(self, gateway, prompt: str) -> AsyncGenerator[str, None]:
        api_key = FAST_LLM_API_KEY
        base_url = FAST_LLM_BASE_URL
        model = FAST_LLM_MODEL

        if not api_key:
            api_key = os.getenv("DEEPSEEK_API_KEY", "")

        messages = [
            {"role": "system", "content": "你是一个专业的研究助手，擅长整理和摘要信息。请简洁、准确、有条理地回答。"},
            {"role": "user", "content": prompt},
        ]

        client = await self._get_client()
        async with client.stream(
            "POST",
            f"{base_url}/chat/completions",
            json={
                "model": model,
                "messages": messages,
                "temperature": 0.3,
                "max_tokens": 2048,
                "stream": True,
            },
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=httpx.Timeout(connect=10.0, read=30.0, write=10.0, pool=10.0),
        ) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if line.startswith("data: "):
                    data_str = line[6:]
                    if data_str == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data_str)
                        delta = chunk.get("choices", [{}])[0].get("delta", {})
                        content = delta.get("content", "")
                        if content:
                            yield content
                    except json.JSONDecodeError:
                        continue

    async def search_and_summarize(self, query: str, gateway=None) -> dict:
        results = await self.search_web(query)
        await self.scrape_urls(results)

        scraped_text = "\n\n---\n\n".join(
            f"来源: {r.title}\n{r.full_text}" for r in results if r.full_text
        )
        snippets_text = "\n".join(
            f"- {r.title}: {r.snippet}" for r in results if r.snippet
        )

        summary = snippets_text
        if gateway and (scraped_text or snippets_text):
            combined = f"搜索查询: {query}\n\n搜索结果摘要:\n{snippets_text}\n\n网页详细内容:\n{scraped_text[:4000]}" if scraped_text else snippets_text
            try:
                response = await gateway.invoke(
                    intent="analyze.research",
                    messages=[
                        {"role": "system", "content": "你是一个专业的研究助手。请简洁准确地整理搜索结果。"},
                        {"role": "user", "content": combined},
                    ],
                    cost_profile="economy",
                    temperature=0.3,
                    max_tokens=2048,
                    use_cache=False,
                )
                summary = response.content.strip()
            except Exception as e:
                logger.warning("摘要LLM调用失败: %s", str(e)[:100])

        return {
            "query": query,
            "summary": summary,
            "sources": [{"title": r.title, "url": r.url, "snippet": r.snippet, "source": r.source} for r in results],
        }


_global_brave_service: Optional[BraveSearchService] = None


def get_brave_search() -> BraveSearchService:
    global _global_brave_service
    if _global_brave_service is None:
        _global_brave_service = BraveSearchService()
    return _global_brave_service