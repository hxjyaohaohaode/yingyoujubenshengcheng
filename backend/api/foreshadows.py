import uuid
from fastapi import APIRouter, Depends, HTTPException, Query, Body
from sqlalchemy import select, func, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from database import get_db
from models.foreshadow import Foreshadow, ForeshadowRelation
from models.scene import Scene
from schemas.foreshadow import (
    ForeshadowCreate, ForeshadowUpdate, ForeshadowResponse,
    ForeshadowRelationCreate, ForeshadowRelationResponse,
)

router = APIRouter()

STATUS_ALIASES = {
    "plant": "planted",
    "activate": "active",
    "reveal": "revealed",
}


def _normalize_fs_status(status: str | None) -> str | None:
    if status is None:
        return None
    return STATUS_ALIASES.get(status, status)


def _legacy_status_variants(status: str | None) -> tuple[str, ...]:
    normalized = _normalize_fs_status(status)
    if normalized == "planted":
        return ("planted", "plant")
    if normalized == "revealed":
        return ("revealed", "reveal")
    if normalized is None:
        return tuple()
    return (normalized,)


@router.post("/projects/{project_id}/foreshadows", response_model=ForeshadowResponse, status_code=201)
async def create_foreshadow(
    project_id: uuid.UUID,
    data: ForeshadowCreate,
    db: AsyncSession = Depends(get_db),
):
    payload = data.model_dump(exclude_none=True)
    payload["current_status"] = _normalize_fs_status(payload.get("current_status")) or "design"
    foreshadow = Foreshadow(
        id=uuid.uuid4(),
        project_id=project_id,
        **payload,
    )
    db.add(foreshadow)
    await db.commit()
    await db.refresh(foreshadow)
    try:
        from websocket.manager import ws_manager
        await ws_manager.send_foreshadow_created(str(project_id), str(foreshadow.id))
    except Exception:
        pass
    return foreshadow


@router.get("/projects/{project_id}/foreshadows", response_model=list[ForeshadowResponse])
async def list_foreshadows(
    project_id: uuid.UUID,
    fs_type: str = Query(None),
    current_status: str = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    query = select(Foreshadow).where(Foreshadow.project_id == project_id)
    if fs_type:
        query = query.where(Foreshadow.fs_type == fs_type)
    if current_status:
        status_variants = _legacy_status_variants(current_status)
        if len(status_variants) == 1:
            query = query.where(Foreshadow.current_status == status_variants[0])
        else:
            query = query.where(Foreshadow.current_status.in_(status_variants))
    query = query.order_by(Foreshadow.fs_code).limit(limit).offset(offset)
    result = await db.execute(query)
    foreshadows = result.scalars().all()
    for foreshadow in foreshadows:
        foreshadow.current_status = _normalize_fs_status(foreshadow.current_status) or "design"
    return foreshadows


@router.get("/projects/{project_id}/foreshadows/relations", response_model=list[ForeshadowRelationResponse])
async def list_fs_relations(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ForeshadowRelation)
        .where(ForeshadowRelation.project_id == project_id)
        .options(
            selectinload(ForeshadowRelation.from_fs),
            selectinload(ForeshadowRelation.to_fs),
        )
    )
    return result.scalars().all()


@router.post("/projects/{project_id}/foreshadows/relations", response_model=ForeshadowRelationResponse, status_code=201)
async def create_fs_relation(
    project_id: uuid.UUID,
    data: ForeshadowRelationCreate,
    db: AsyncSession = Depends(get_db),
):
    relation = ForeshadowRelation(
        id=uuid.uuid4(),
        project_id=project_id,
        **data.model_dump(exclude_none=True),
    )
    db.add(relation)
    await db.commit()
    await db.refresh(relation)
    return relation


@router.delete("/projects/{project_id}/foreshadows/relations/{relation_id}", status_code=204)
async def delete_fs_relation(
    project_id: uuid.UUID,
    relation_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ForeshadowRelation).where(
            ForeshadowRelation.id == relation_id,
            ForeshadowRelation.project_id == project_id,
        )
    )
    relation = result.scalar_one_or_none()
    if not relation:
        raise HTTPException(status_code=404, detail="关联不存在")
    await db.delete(relation)
    await db.commit()


@router.get("/projects/{project_id}/foreshadows-graph")
async def get_foreshadows_graph(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    fs_result = await db.execute(
        select(Foreshadow).where(Foreshadow.project_id == project_id)
    )
    foreshadows = fs_result.scalars().all()

    rel_result = await db.execute(
        select(ForeshadowRelation).where(ForeshadowRelation.project_id == project_id)
    )
    relations = rel_result.scalars().all()

    nodes = []
    for fs in foreshadows:
        normalized_status = _normalize_fs_status(fs.current_status) or "design"
        nodes.append({
            "id": str(fs.id),
            "name": fs.name,
            "fs_code": fs.fs_code,
            "fs_type": fs.fs_type,
            "current_status": normalized_status,
            "health": fs.health,
            "reinforce_count": fs.reinforce_count,
            "surface_layer": fs.surface_layer,
            "deep_layer": fs.deep_layer,
        })

    edges = []
    for rel in relations:
        edges.append({
            "id": str(rel.id),
            "source": str(rel.from_fs_id),
            "target": str(rel.to_fs_id),
            "relation_type": rel.relation_type,
        })

    return {"nodes": nodes, "edges": edges}


@router.get("/projects/{project_id}/foreshadow-health")
async def get_foreshadow_health(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    fs_result = await db.execute(
        select(Foreshadow).where(Foreshadow.project_id == project_id)
    )
    foreshadows = fs_result.scalars().all()

    total = len(foreshadows)
    if total == 0:
        return {"project_id": str(project_id), "overall_health": "unknown", "details": [], "stats": {}}

    health_counts = {"normal": 0, "warning": 0, "danger": 0}
    status_counts = {}
    details = []

    for fs in foreshadows:
        health = fs.health or "normal"
        health_counts[health] = health_counts.get(health, 0) + 1

        status = _normalize_fs_status(fs.current_status) or "design"
        status_counts[status] = status_counts.get(status, 0) + 1

        issues = []
        if status in ("planted", "reinforced") and (fs.reinforce_count or 0) == 0:
            issues.append("已埋设但从未强化")
        if status in ("planted", "reinforced") and not fs.reveal_scene_id:
            issues.append("尚未安排回收场景")

        details.append({
            "id": str(fs.id),
            "name": fs.name,
            "fs_code": fs.fs_code,
            "health": health,
            "current_status": status,
            "reinforce_count": fs.reinforce_count or 0,
            "issues": issues,
        })

    if health_counts.get("danger", 0) > total * 0.3:
        overall = "danger"
    elif health_counts.get("warning", 0) > total * 0.4:
        overall = "warning"
    else:
        overall = "normal"

    return {
        "project_id": str(project_id),
        "overall_health": overall,
        "details": details,
        "stats": {
            "total": total,
            "health_counts": health_counts,
            "status_counts": status_counts,
        },
    }


@router.post("/projects/{project_id}/foreshadow-chemical-reaction")
async def analyze_foreshadow_chemical_reaction(
    project_id: uuid.UUID,
    payload: dict = Body(default=None),
    db: AsyncSession = Depends(get_db),
):
    foreshadow_ids = payload.get("foreshadow_ids", []) if payload else []
    fs_result = await db.execute(
        select(Foreshadow).where(Foreshadow.project_id == project_id)
    )
    foreshadows = fs_result.scalars().all()

    if foreshadow_ids:
        foreshadows = [f for f in foreshadows if str(f.id) in foreshadow_ids]

    if len(foreshadows) < 2:
        return {"project_id": str(project_id), "reactions": [], "message": "至少需要2个伏笔才能分析化学反应"}

    reactions = []
    for i, fs_a in enumerate(foreshadows):
        for fs_b in foreshadows[i + 1:]:
            synergy_score = 0
            reaction_type = "neutral"
            description = ""

            status_a = _normalize_fs_status(fs_a.current_status) or "design"
            status_b = _normalize_fs_status(fs_b.current_status) or "design"

            if status_a == "planted" and status_b == "planted":
                synergy_score = 7
                reaction_type = "parallel_reinforce"
                description = f"「{fs_a.name}」和「{fs_b.name}」可以同时强化，形成叙事共振"

            elif status_a in ("planted", "reinforced") and status_b == "revealed":
                synergy_score = 9
                reaction_type = "cascade_reveal"
                description = f"「{fs_b.name}」的揭示可以触发「{fs_a.name}」的新解读"

            elif fs_a.fs_type == "suspense" and fs_b.fs_type == "suspense":
                synergy_score = 6
                reaction_type = "tension_stack"
                description = f"两个悬念伏笔叠加，紧张感倍增"

            elif fs_a.fs_type == "emotional" and fs_b.fs_type == "emotional":
                synergy_score = 8
                reaction_type = "emotional_resonance"
                description = f"「{fs_a.name}」和「{fs_b.name}」的情感冲击可以互相放大"

            elif status_a == "revealed" and status_b == "revealed":
                synergy_score = 5
                reaction_type = "retroactive_link"
                description = f"两个已揭示的伏笔可以建立回溯性关联"

            else:
                synergy_score = 4
                reaction_type = "potential_synergy"
                description = f"「{fs_a.name}」和「{fs_b.name}」存在潜在的叙事协同"

            if synergy_score >= 5:
                reactions.append({
                    "foreshadow_a": {"id": str(fs_a.id), "name": fs_a.name, "status": status_a},
                    "foreshadow_b": {"id": str(fs_b.id), "name": fs_b.name, "status": status_b},
                    "synergy_score": synergy_score,
                    "reaction_type": reaction_type,
                    "description": description,
                })

    reactions.sort(key=lambda r: r["synergy_score"], reverse=True)

    return {
        "project_id": str(project_id),
        "reactions": reactions,
        "total_pairs": len(reactions),
        "high_synergy_count": sum(1 for r in reactions if r["synergy_score"] >= 7),
    }


@router.get("/projects/{project_id}/foreshadows/{foreshadow_id}", response_model=ForeshadowResponse)
async def get_foreshadow(
    project_id: uuid.UUID,
    foreshadow_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Foreshadow).where(Foreshadow.id == foreshadow_id, Foreshadow.project_id == project_id)
    )
    foreshadow = result.scalar_one_or_none()
    if not foreshadow:
        raise HTTPException(status_code=404, detail="伏笔不存在")
    return foreshadow


@router.put("/projects/{project_id}/foreshadows/{foreshadow_id}", response_model=ForeshadowResponse)
async def update_foreshadow(
    project_id: uuid.UUID,
    foreshadow_id: uuid.UUID,
    data: ForeshadowUpdate,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Foreshadow).where(Foreshadow.id == foreshadow_id, Foreshadow.project_id == project_id)
    )
    foreshadow = result.scalar_one_or_none()
    if not foreshadow:
        raise HTTPException(status_code=404, detail="伏笔不存在")

    update_data = data.model_dump(exclude_unset=True)
    if "current_status" in update_data:
        update_data["current_status"] = _normalize_fs_status(update_data["current_status"])
    for key, value in update_data.items():
        setattr(foreshadow, key, value)

    await db.commit()
    await db.refresh(foreshadow)
    foreshadow.current_status = _normalize_fs_status(foreshadow.current_status) or "design"
    try:
        from websocket.manager import ws_manager
        await ws_manager.send_foreshadow_updated(str(project_id), str(foreshadow.id))
    except Exception:
        pass
    return foreshadow


@router.delete("/projects/{project_id}/foreshadows/{foreshadow_id}", status_code=204)
async def delete_foreshadow(
    project_id: uuid.UUID,
    foreshadow_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Foreshadow).where(Foreshadow.id == foreshadow_id, Foreshadow.project_id == project_id)
    )
    foreshadow = result.scalar_one_or_none()
    if not foreshadow:
        raise HTTPException(status_code=404, detail="线索不存在")
    await db.delete(foreshadow)
    await db.commit()
    try:
        from websocket.manager import ws_manager
        await ws_manager.send_foreshadow_deleted(str(project_id), str(foreshadow_id))
    except Exception:
        pass
