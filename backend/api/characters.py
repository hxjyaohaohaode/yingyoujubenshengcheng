import uuid
from datetime import datetime, UTC
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from database import get_db
from models.character import Character, CharacterRelation
from schemas.character import (
    CharacterCreate, CharacterUpdate, CharacterResponse,
    RelationCreate, RelationUpdate, RelationResponse,
)

router = APIRouter()


@router.post("/projects/{project_id}/characters", response_model=CharacterResponse, status_code=201)
async def create_character(
    project_id: uuid.UUID,
    data: CharacterCreate,
    db: AsyncSession = Depends(get_db),
):
    character = Character(
        id=uuid.uuid4(),
        project_id=project_id,
        **data.model_dump(exclude_none=True),
    )
    db.add(character)
    await db.commit()
    await db.refresh(character)
    try:
        from websocket.manager import ws_manager
        await ws_manager.send_character_created(str(project_id), str(character.id))
    except Exception:
        pass
    return character


@router.get("/projects/{project_id}/characters", response_model=list[CharacterResponse])
async def list_characters(
    project_id: uuid.UUID,
    role_type: str = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    query = select(Character).where(Character.project_id == project_id)
    if role_type:
        query = query.where(Character.role_type == role_type)
    query = query.order_by(Character.char_code).limit(limit).offset(offset)
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/projects/{project_id}/characters/{character_id}", response_model=CharacterResponse)
async def get_character(
    project_id: uuid.UUID,
    character_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Character).where(Character.id == character_id, Character.project_id == project_id)
    )
    character = result.scalar_one_or_none()
    if not character:
        raise HTTPException(status_code=404, detail="角色不存在")
    return character


@router.put("/projects/{project_id}/characters/{character_id}", response_model=CharacterResponse)
async def update_character(
    project_id: uuid.UUID,
    character_id: uuid.UUID,
    data: CharacterUpdate,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Character).where(Character.id == character_id, Character.project_id == project_id)
    )
    character = result.scalar_one_or_none()
    if not character:
        raise HTTPException(status_code=404, detail="角色不存在")

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(character, key, value)

    await db.commit()
    await db.refresh(character)
    try:
        from websocket.manager import ws_manager
        await ws_manager.send_character_updated(str(project_id), str(character.id))
    except Exception:
        pass
    return character


@router.delete("/projects/{project_id}/characters/{character_id}", status_code=204)
async def delete_character(
    project_id: uuid.UUID,
    character_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Character).where(Character.id == character_id, Character.project_id == project_id)
    )
    character = result.scalar_one_or_none()
    if not character:
        raise HTTPException(status_code=404, detail="角色不存在")

    # 先删除关联的关系记录，避免外键约束冲突
    await db.execute(
        delete(CharacterRelation).where(
            CharacterRelation.project_id == project_id,
            (CharacterRelation.char_a_id == character_id) | (CharacterRelation.char_b_id == character_id),
        )
    )

    await db.delete(character)
    await db.commit()
    try:
        from websocket.manager import ws_manager
        await ws_manager.send_character_deleted(str(project_id), str(character_id))
    except Exception:
        pass


@router.get("/projects/{project_id}/relations", response_model=list[RelationResponse])
async def list_relations(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(CharacterRelation)
        .where(CharacterRelation.project_id == project_id)
        .options(
            selectinload(CharacterRelation.char_a),
            selectinload(CharacterRelation.char_b),
        )
    )
    return result.scalars().all()


@router.post("/projects/{project_id}/relations", response_model=RelationResponse, status_code=201)
async def create_relation(
    project_id: uuid.UUID,
    data: RelationCreate,
    db: AsyncSession = Depends(get_db),
):
    relation = CharacterRelation(
        id=uuid.uuid4(),
        project_id=project_id,
        **data.model_dump(exclude_none=True),
    )
    db.add(relation)
    await db.commit()
    await db.refresh(relation)
    return relation


@router.put("/projects/{project_id}/relations/{relation_id}", response_model=RelationResponse)
async def update_relation(
    project_id: uuid.UUID,
    relation_id: uuid.UUID,
    data: RelationUpdate,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(CharacterRelation).where(
            CharacterRelation.id == relation_id,
            CharacterRelation.project_id == project_id,
        ).options(
            selectinload(CharacterRelation.char_a),
            selectinload(CharacterRelation.char_b),
        )
    )
    relation = result.scalar_one_or_none()
    if not relation:
        raise HTTPException(status_code=404, detail="关系不存在")

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(relation, key, value)
    relation.updated_at = datetime.now(UTC)

    await db.commit()
    await db.refresh(relation)
    return relation


@router.delete("/projects/{project_id}/relations/{relation_id}", status_code=204)
async def delete_relation(
    project_id: uuid.UUID,
    relation_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(CharacterRelation).where(
            CharacterRelation.id == relation_id,
            CharacterRelation.project_id == project_id,
        )
    )
    relation = result.scalar_one_or_none()
    if not relation:
        raise HTTPException(status_code=404, detail="关系不存在")
    await db.delete(relation)
    await db.commit()
