import json
import logging
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from core.gateway.client import get_gateway
from core.rag.retriever import RAGRetriever
from core.search.web_search import WebSearchService
from core.context.context_manager import ContextManager

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/projects", tags=["knowledge"])


@router.get("/{project_id}/knowledge")
async def get_project_knowledge(project_id: str, db: AsyncSession = Depends(get_db)):
    gateway = get_gateway()
    rag = RAGRetriever(db)
    search = WebSearchService(db, gateway)
    ctx_mgr = ContextManager(db, gateway, rag, search)

    try:
        from sqlalchemy import text
        file_result = await db.execute(
            text("SELECT id, filename, file_type, file_size, page_count, created_at "
                 "FROM project_files WHERE project_id = :pid ORDER BY created_at DESC"),
            {"pid": project_id},
        )
        uploads = []
        for row in file_result.fetchall():
            uploads.append({
                "id": row[0],
                "filename": row[1],
                "file_type": row[2],
                "file_size": row[3],
                "page_count": row[4],
                "created_at": str(row[5]) if row[5] else "",
            })
    except Exception:
        uploads = []

    try:
        cache_result = await db.execute(
            text("SELECT entity_name, result_json, searched_at FROM search_cache "
                 "WHERE searched_at != '' ORDER BY searched_at DESC LIMIT 20"),
        )
        searches = []
        for row in cache_result.fetchall():
            results = json.loads(row[1]) if isinstance(row[1], str) else row[1]
            searches.append({
                "entity_name": row[0],
                "results": results[:3] if isinstance(results, list) else [],
                "searched_at": str(row[2]) if row[2] else "",
            })
    except Exception:
        searches = []

    upload_chunks = []
    try:
        upload_chunks = await ctx_mgr.get_upload_chunks(project_id)
    except Exception:
        pass

    return {
        "uploads": uploads,
        "searches": searches,
        "upload_preview": upload_chunks[:3] if upload_chunks else [],
    }