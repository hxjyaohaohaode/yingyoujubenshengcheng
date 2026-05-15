import uuid
import logging
from sqlalchemy import select, delete, update, desc, and_
from sqlalchemy.ext.asyncio import AsyncSession
from core.narrative.models import NarrativeMemory

logger = logging.getLogger(__name__)

SHORT_TERM_MAX = 5


async def store_short_term_memory(
    db: AsyncSession,
    project_id: str,
    scene_id: str | None,
    chapter_id: str | None,
    category: str,
    entity_id: str | None,
    content: str,
) -> NarrativeMemory:
    memory = NarrativeMemory(
        id=uuid.uuid4(),
        project_id=uuid.UUID(project_id),
        memory_type="short_term",
        category=category,
        entity_id=entity_id,
        content=content,
        scene_anchor=scene_id,
        chapter_anchor=chapter_id,
    )
    db.add(memory)
    await db.flush()

    stmt = (
        select(NarrativeMemory.id)
        .where(
            NarrativeMemory.project_id == uuid.UUID(project_id),
            NarrativeMemory.memory_type == "short_term",
        )
        .order_by(desc(NarrativeMemory.created_at))
        .offset(SHORT_TERM_MAX)
    )
    result = await db.execute(stmt)
    old_ids = result.scalars().all()
    if old_ids:
        del_stmt = delete(NarrativeMemory).where(NarrativeMemory.id.in_(old_ids))
        await db.execute(del_stmt)

    await db.commit()
    await db.refresh(memory)
    return memory


async def store_long_term_memory(
    db: AsyncSession,
    project_id: str,
    category: str,
    entity_id: str | None,
    content: str,
) -> NarrativeMemory:
    conditions = [
        NarrativeMemory.project_id == uuid.UUID(project_id),
        NarrativeMemory.memory_type == "long_term",
        NarrativeMemory.category == category,
    ]
    if entity_id is not None:
        conditions.append(NarrativeMemory.entity_id == entity_id)
    else:
        conditions.append(NarrativeMemory.entity_id.is_(None))

    stmt = select(NarrativeMemory).where(and_(*conditions))
    result = await db.execute(stmt)
    existing = result.scalars().first()

    if existing:
        existing.content = content
        await db.commit()
        await db.refresh(existing)
        return existing

    memory = NarrativeMemory(
        id=uuid.uuid4(),
        project_id=uuid.UUID(project_id),
        memory_type="long_term",
        category=category,
        entity_id=entity_id,
        content=content,
    )
    db.add(memory)
    await db.commit()
    await db.refresh(memory)
    return memory


async def get_short_term_memories(
    db: AsyncSession,
    project_id: str,
    limit: int = 5,
) -> list[NarrativeMemory]:
    stmt = (
        select(NarrativeMemory)
        .where(
            NarrativeMemory.project_id == uuid.UUID(project_id),
            NarrativeMemory.memory_type == "short_term",
        )
        .order_by(desc(NarrativeMemory.created_at))
        .limit(limit)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_long_term_memories(
    db: AsyncSession,
    project_id: str,
    category: str | None = None,
) -> list[NarrativeMemory]:
    conditions = [
        NarrativeMemory.project_id == uuid.UUID(project_id),
        NarrativeMemory.memory_type == "long_term",
    ]
    if category:
        conditions.append(NarrativeMemory.category == category)

    stmt = (
        select(NarrativeMemory)
        .where(and_(*conditions))
        .order_by(NarrativeMemory.priority.desc(), NarrativeMemory.updated_at.desc())
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_all_memories_for_context(
    db: AsyncSession,
    project_id: str,
) -> list[NarrativeMemory]:
    short_term = await get_short_term_memories(db, project_id)
    long_term = await get_long_term_memories(db, project_id)
    return short_term + long_term