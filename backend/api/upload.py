import uuid
import logging
from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from core.upload.file_handler import FileUploadHandler
from core.context.context_manager import ContextManager
from core.gateway.client import get_gateway
from core.rag.retriever import RAGRetriever
from core.search.web_search import WebSearchService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/projects", tags=["upload"])


@router.post("/{project_id}/upload")
async def upload_reference_file(
    project_id: str,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    handler = FileUploadHandler()

    if not file.filename:
        raise HTTPException(status_code=400, detail="文件名不能为空")

    content = await file.read()
    valid, error_msg = handler.validate_file(file.filename, len(content))
    if not valid:
        raise HTTPException(status_code=400, detail=error_msg)

    try:
        doc = await handler.parse_file(content, file.filename)
    except ImportError as e:
        raise HTTPException(status_code=500, detail=f"文件解析依赖缺失: {str(e)}")
    except Exception as e:
        logger.error("文件解析失败: %s", str(e)[:200])
        raise HTTPException(status_code=500, detail=f"文件解析失败: {str(e)[:200]}")

    doc_id = str(uuid.uuid4())

    gateway = get_gateway()
    rag = RAGRetriever(db)
    search = WebSearchService(db, gateway)
    ctx_mgr = ContextManager(db, gateway, rag, search)

    try:
        await ctx_mgr.index_uploaded_document(project_id, doc_id, doc.text, file.filename)
    except Exception as e:
        logger.warning("上传文档RAG索引失败: %s", str(e)[:200])

    try:
        from sqlalchemy import text
        await db.execute(
            text(
                """INSERT INTO project_files
                (id, project_id, filename, file_type, file_size, page_count, text_preview, created_at)
                VALUES (:id, :project_id, :filename, :file_type, :file_size, :page_count, :text_preview, datetime('now'))"""
            ),
            {
                "id": doc_id,
                "project_id": project_id,
                "filename": file.filename,
                "file_type": doc.file_type,
                "file_size": len(content),
                "page_count": doc.page_count,
                "text_preview": doc.text[:200] + "..." if len(doc.text) > 200 else doc.text,
            },
        )
        await db.commit()
    except Exception as e:
        logger.warning("上传记录持久化失败: %s", str(e)[:200])

    return {
        "status": "ok",
        "file_id": doc_id,
        "filename": file.filename,
        "file_type": doc.file_type,
        "size": len(content),
        "pages": doc.page_count,
        "preview": doc.text[:200],
    }


@router.get("/{project_id}/uploads")
async def list_uploads(project_id: str, db: AsyncSession = Depends(get_db)):
    try:
        from sqlalchemy import text
        result = await db.execute(
            text(
                "SELECT id, filename, file_type, file_size, page_count, text_preview, created_at "
                "FROM project_files WHERE project_id = :pid ORDER BY created_at DESC"
            ),
            {"pid": project_id},
        )
        files = []
        for row in result.fetchall():
            files.append({
                "id": row[0],
                "filename": row[1],
                "file_type": row[2],
                "file_size": row[3],
                "page_count": row[4],
                "text_preview": row[5],
                "created_at": str(row[6]) if row[6] else "",
            })
        return {"files": files}
    except Exception as e:
        logger.warning("获取上传列表失败: %s", str(e)[:200])
        return {"files": []}


@router.delete("/{project_id}/uploads/{file_id}")
async def delete_upload(project_id: str, file_id: str, db: AsyncSession = Depends(get_db)):
    try:
        from sqlalchemy import text
        await db.execute(
            text("DELETE FROM project_files WHERE id = :fid AND project_id = :pid"),
            {"fid": file_id, "pid": project_id},
        )
        await db.execute(
            text("DELETE FROM embeddings WHERE content_id = :cid AND content_type = 'user_upload'"),
            {"cid": file_id},
        )
        await db.commit()
        return {"status": "deleted"}
    except Exception as e:
        logger.warning("删除上传文件失败: %s", str(e)[:200])
        raise HTTPException(status_code=500, detail=f"删除失败: {str(e)[:200]}")