import json
import logging
import asyncio
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from core.gateway.client import get_gateway
from core.search.web_search import WebSearchService
from core.search.brave_search import get_brave_search
from core.context.intent_analyzer import IntentAnalyzer

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/projects", tags=["search"])


class SearchRequest(BaseModel):
    user_query: str


@router.post("/{project_id}/search")
async def trigger_search(project_id: str, body: SearchRequest, db: AsyncSession = Depends(get_db)):
    user_query = body.user_query
    if not user_query:
        raise HTTPException(status_code=400, detail="缺少搜索查询")

    gateway = get_gateway()

    try:
        analyzer = IntentAnalyzer(gateway)
        intent = await analyzer.analyze(user_query)
    except Exception as e:
        logger.warning("意图分析失败，使用简单模式: %s", str(e)[:200])
        from core.context.intent_models import EntityInfo, IntentResult
        intent = IntentResult(
            entities=[EntityInfo(name=user_query, type="concept", importance=0.8)],
            key_events=[], era="", world_elements=[],
            confidence=0.5, need_search=True,
        )

    try:
        search = WebSearchService(db, gateway)
        cards = await search.batch_search(intent.entities, user_query)
        await search.close()
    except Exception as e:
        logger.warning("搜索执行失败: %s", str(e)[:200])
        cards = []

    result = {
        "status": "ok",
        "intent": intent.to_dict() if hasattr(intent, 'to_dict') else {},
        "knowledge_cards": [
            {
                "entity_name": c.entity_name,
                "entity_type": c.entity_type,
                "summary": c.summary,
                "key_facts": c.key_facts[:5] if c.key_facts else [],
                "sources": c.sources[:3] if c.sources else [],
            }
            for c in cards
        ],
    }
    return result


@router.post("/{project_id}/search/stream")
async def search_stream(project_id: str, body: SearchRequest, request: Request):
    user_query = body.user_query.strip()
    if not user_query:
        raise HTTPException(status_code=400, detail="缺少搜索查询")

    brave = get_brave_search()
    gateway = get_gateway()

    async def event_generator():
        disconnected = False
        try:
            async for sse_data in brave.stream_search(user_query, gateway):
                if disconnected:
                    break
                if await request.is_disconnected():
                    disconnected = True
                    break
                yield sse_data.encode("utf-8") if isinstance(sse_data, str) else sse_data
                await asyncio.sleep(0)
        except asyncio.CancelledError:
            logger.info("SSE连接被取消: project_id=%s", project_id)
        except Exception as e:
            logger.error("SSE流式搜索异常: %s", str(e)[:200])
            yield f"data: {json.dumps({'phase': 'error', 'text': f'搜索出错: {str(e)[:200]}'}, ensure_ascii=False)}\n\n".encode("utf-8")
            yield "data: [DONE]\n\n".encode("utf-8")

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "Access-Control-Allow-Origin": "*",
        },
    )


@router.post("/{project_id}/search/quick")
async def search_quick(project_id: str, body: SearchRequest):
    user_query = body.user_query.strip()
    if not user_query:
        raise HTTPException(status_code=400, detail="缺少搜索查询")

    brave = get_brave_search()
    gateway = get_gateway()

    try:
        result = await brave.search_and_summarize(user_query, gateway)
        return {"status": "ok", **result}
    except Exception as e:
        logger.error("快速搜索失败: %s", str(e)[:200])
        return {"status": "error", "message": str(e)[:200], "query": user_query, "sources": []}


@router.get("/{project_id}/search/status")
async def search_status(project_id: str, db: AsyncSession = Depends(get_db)):
    try:
        from sqlalchemy import text
        result = await db.execute(
            text("SELECT COUNT(*), MAX(searched_at) FROM search_cache WHERE entity_name != ''"),
        )
        row = result.fetchone()
        return {
            "cached_count": row[0] if row else 0,
            "last_search": row[1] if row and row[1] else None,
        }
    except Exception:
        return {"cached_count": 0, "last_search": None}