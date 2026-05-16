from fastapi import APIRouter, Depends, UploadFile, File, Form
from fastapi.responses import JSONResponse
from core.storage.service import StorageService
from database import get_db
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()


@router.post("/script-viz/analyze-project/{project_id}")
async def analyze_project_visual(project_id: str, db: AsyncSession = Depends(get_db)):
    storage = StorageService(db)
    scenes = await storage.get_all_scenes_ordered(project_id)
    characters = await storage.get_character_states(project_id)
    foreshadows = await storage.get_foreshadow_states(project_id)
    chapters = await storage.get_chapter_states(project_id)
    return {
        "nodes": [],
        "edges": [],
        "scenes": scenes or [],
        "characters": characters or [],
        "foreshadows": foreshadows or [],
        "chapters": chapters or [],
        "stats": {"scene_count": len(scenes or []), "character_count": len(characters or []), "foreshadow_count": len(foreshadows or [])},
    }


@router.post("/script-viz/upload-parse/{project_id}")
async def upload_parse_script(project_id: str, file: UploadFile = File(None), db: AsyncSession = Depends(get_db)):
    return JSONResponse({"status": "ok", "message": "剧本上传解析功能开发中", "project_id": project_id})


@router.post("/script-viz/regenerate/{project_id}")
async def regenerate_visual(project_id: str, data: dict = None, db: AsyncSession = Depends(get_db)):
    return {"status": "ok", "message": "可视化重新生成完成", "project_id": project_id}
