import uuid
import logging
from datetime import datetime, UTC
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from database import get_db
from models.scene import Scene, SceneVersion
from models.audit import AuditRecord
from schemas.scene import SceneCreate, SceneUpdate, SceneResponse, SceneVersionResponse

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/projects/{project_id}/scenes", response_model=SceneResponse, status_code=201)
async def create_scene(
    project_id: uuid.UUID,
    data: SceneCreate,
    db: AsyncSession = Depends(get_db),
):
    dump = data.model_dump(exclude_none=True)
    scene = Scene(
        id=uuid.uuid4(),
        project_id=project_id,
        **dump,
    )
    db.add(scene)
    await db.commit()
    await db.refresh(scene)
    try:
        from websocket.manager import ws_manager
        await ws_manager.send_scene_created(str(project_id), str(scene.id))
    except Exception:
        pass
    return scene


@router.get("/projects/{project_id}/scenes", response_model=list[SceneResponse])
async def list_scenes(
    project_id: uuid.UUID,
    chapter_id: uuid.UUID = Query(None),
    status: str = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    query = select(Scene).where(Scene.project_id == project_id)
    if chapter_id:
        query = query.where(Scene.chapter_id == chapter_id)
    if status:
        statuses = [s.strip() for s in status.split(",") if s.strip()]
        if len(statuses) == 1:
            query = query.where(Scene.status == statuses[0])
        elif statuses:
            query = query.where(Scene.status.in_(statuses))
    query = query.options(
        selectinload(Scene.chapter),
        selectinload(Scene.versions),
    ).order_by(Scene.scene_code).limit(limit).offset(offset)
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/projects/{project_id}/scenes/{scene_id}", response_model=SceneResponse)
async def get_scene(
    project_id: uuid.UUID,
    scene_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Scene)
        .where(Scene.id == scene_id, Scene.project_id == project_id)
        .options(
            selectinload(Scene.chapter),
            selectinload(Scene.versions),
        )
    )
    scene = result.scalar_one_or_none()
    if not scene:
        raise HTTPException(status_code=404, detail="场景不存在")
    return scene


@router.put("/projects/{project_id}/scenes/{scene_id}", response_model=SceneResponse)
async def update_scene(
    project_id: uuid.UUID,
    scene_id: uuid.UUID,
    data: SceneUpdate,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Scene).where(Scene.id == scene_id, Scene.project_id == project_id)
    )
    scene = result.scalar_one_or_none()
    if not scene:
        raise HTTPException(status_code=404, detail="场景不存在")

    version_snapshot = SceneVersion(
        id=uuid.uuid4(),
        scene_id=scene.id,
        version=scene.version,
        content={
            "narration": scene.narration,
            "dialogue": scene.dialogue,
            "actions": scene.actions,
            "foreshadow_ops": scene.foreshadow_ops,
            "choices": scene.choices,
            "causal_chain": scene.causal_chain,
            "emotion_level": scene.emotion_level,
            "location": scene.location,
            "weather": scene.weather,
            "characters_involved": scene.characters_involved,
        },
        change_reason="编辑前自动快照",
    )
    db.add(version_snapshot)

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(scene, key, value)

    scene.version = (scene.version or 0) + 1

    await db.commit()
    await db.refresh(scene)
    try:
        from websocket.manager import ws_manager
        await ws_manager.send_scene_updated(str(project_id), str(scene.id))
    except Exception:
        pass
    return scene


@router.delete("/projects/{project_id}/scenes/{scene_id}", status_code=204)
async def delete_scene(
    project_id: uuid.UUID,
    scene_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Scene).where(Scene.id == scene_id, Scene.project_id == project_id)
    )
    scene = result.scalar_one_or_none()
    if not scene:
        raise HTTPException(status_code=404, detail="场景不存在")
    await db.delete(scene)
    await db.commit()
    try:
        from websocket.manager import ws_manager
        await ws_manager.send_scene_deleted(str(project_id), str(scene_id))
    except Exception:
        pass


@router.get("/projects/{project_id}/scenes/{scene_id}/versions", response_model=list[SceneVersionResponse])
async def list_scene_versions(
    project_id: uuid.UUID,
    scene_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(SceneVersion)
        .where(SceneVersion.scene_id == scene_id)
        .order_by(SceneVersion.version.desc())
    )
    return result.scalars().all()


@router.get("/projects/{project_id}/scenes/{scene_id}/versions/{version}", response_model=SceneVersionResponse)
async def get_scene_version(
    project_id: uuid.UUID,
    scene_id: uuid.UUID,
    version: int,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(SceneVersion).where(
            SceneVersion.scene_id == scene_id,
            SceneVersion.version == version,
        )
    )
    ver = result.scalar_one_or_none()
    if not ver:
        raise HTTPException(status_code=404, detail="版本不存在")
    return ver


@router.post("/projects/{project_id}/scenes/{scene_id}/finalize")
async def finalize_scene(project_id: uuid.UUID, scene_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Scene)
        .where(Scene.id == scene_id, Scene.project_id == project_id)
        .options(
            selectinload(Scene.chapter),
            selectinload(Scene.versions),
        )
    )
    scene = result.scalar_one_or_none()
    if not scene:
        raise HTTPException(status_code=404, detail="场景不存在")

    valid_statuses = {"approved", "passed"}
    if scene.status not in valid_statuses:
        raise HTTPException(status_code=400, detail="只有已审核通过的场景才能定稿（当前状态: " + scene.status + "）")

    version_snapshot = SceneVersion(
        id=uuid.uuid4(),
        scene_id=scene.id,
        version=scene.version,
        content={
            "narration": scene.narration,
            "dialogue": scene.dialogue,
            "actions": scene.actions,
            "foreshadow_ops": scene.foreshadow_ops,
            "choices": scene.choices,
            "causal_chain": scene.causal_chain,
            "emotion_level": scene.emotion_level,
            "location": scene.location,
            "weather": scene.weather,
            "time_start": scene.time_start,
            "time_end": scene.time_end,
            "characters_involved": scene.characters_involved,
        },
        audit_report=scene.audit_reports,
        change_reason="场景定稿",
    )
    db.add(version_snapshot)
    commit_hash = ""

    try:
        from core.agent.state_manager import StateManagerAgent
        from core.agent.base import AgentTask

        state_agent = StateManagerAgent()
        state_task = AgentTask(
            task_type="state_updater",
            project_id=str(project_id),
            payload={
                "scene_id": str(scene_id),
                "operation": "update_from_scene",
            },
        )
        state_result = await state_agent.execute(state_task)
        if state_result.status not in ("completed", "pass"):
            raise RuntimeError(f"StateManager 更新失败: {state_result.status}")
        logger.info("StateManager 执行完成: status=%s, data_keys=%s", state_result.status, list(state_result.data.keys()) if state_result.data else [])
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Layer1 状态更新失败，场景未定稿: {str(e)[:200]}") from e

    try:
        from core.agent.material import MaterialAgent
        from core.agent.base import AgentTask

        material_agent = MaterialAgent()
        material_task = AgentTask(
            task_type="doc_manager",
            project_id=str(project_id),
            payload={
                "context_type": "doc_write",
                "scene_id": str(scene_id),
                "content": {
                    "narration": scene.narration,
                    "dialogue": scene.dialogue,
                    "actions": scene.actions,
                    "foreshadow_ops": scene.foreshadow_ops,
                    "choices": scene.choices,
                    "causal_chain": scene.causal_chain,
                    "emotion_level": scene.emotion_level,
                    "location": scene.location,
                    "characters_involved": scene.characters_involved,
                },
            },
        )
        material_result = await material_agent.execute(material_task)
        if material_result.status not in ("completed", "pass"):
            raise RuntimeError(f"MaterialAgent 执行失败: {material_result.status}")
        commit_hash = material_result.data.get("commit_hash", "") if material_result.data else ""
        logger.info("MaterialAgent 执行完成: commit_hash=%s", commit_hash)
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"文档/Git 持久化失败，场景未定稿: {str(e)[:200]}") from e

    old_version = scene.version
    new_version = old_version + 1
    scene.status = "final"
    scene.version = new_version
    if commit_hash:
        scene.git_commit_hash = commit_hash

    scene.updated_at = datetime.now(UTC)

    audit_record = AuditRecord(
        id=uuid.uuid4(),
        project_id=project_id,
        scene_id=scene.id,
        audit_type="finalize",
        checker_results={"version": new_version, "previous_version": old_version},
        overall_result="finalized",
    )
    db.add(audit_record)

    await db.commit()
    await db.refresh(scene)

    try:
        from websocket.manager import ws_manager
        await ws_manager.send_scene_finalized(str(project_id), str(scene.id))
    except Exception:
        pass

    return {
        "id": str(scene.id),
        "scene_code": scene.scene_code,
        "status": scene.status,
        "version": scene.version,
        "git_commit_hash": scene.git_commit_hash,
        "updated_at": scene.updated_at.isoformat() if scene.updated_at else None,
        "message": "场景已成功定稿",
    }
