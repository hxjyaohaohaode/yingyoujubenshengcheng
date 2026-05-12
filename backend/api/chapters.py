import uuid
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from database import get_db
from models.chapter import Chapter, ChapterSection
from models.choice import ChoiceDesign
from schemas.chapter import ChapterCreate, ChapterUpdate, ChapterResponse
from schemas.chapter import SectionCreate, SectionUpdate, SectionResponse
from schemas.choice import ChoiceDesignCreate, ChoiceDesignUpdate, ChoiceDesignResponse

router = APIRouter()


@router.post("/projects/{project_id}/chapters", response_model=ChapterResponse, status_code=201)
async def create_chapter(
    project_id: uuid.UUID,
    data: ChapterCreate,
    db: AsyncSession = Depends(get_db),
):
    chapter = Chapter(
        id=uuid.uuid4(),
        project_id=project_id,
        **data.model_dump(exclude_none=True),
    )
    db.add(chapter)
    await db.commit()
    await db.refresh(chapter)
    try:
        from websocket.manager import ws_manager
        await ws_manager.send_chapter_created(str(project_id), str(chapter.id))
    except Exception:
        pass
    return chapter


@router.get("/projects/{project_id}/chapters", response_model=list[ChapterResponse])
async def list_chapters(
    project_id: uuid.UUID,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Chapter)
        .where(Chapter.project_id == project_id)
        .options(selectinload(Chapter.scenes), selectinload(Chapter.sections))
        .order_by(Chapter.chapter_number)
        .limit(limit).offset(offset)
    )
    return result.scalars().all()


@router.get("/projects/{project_id}/chapters/{chapter_id}", response_model=ChapterResponse)
async def get_chapter(
    project_id: uuid.UUID,
    chapter_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Chapter)
        .where(Chapter.id == chapter_id, Chapter.project_id == project_id)
        .options(selectinload(Chapter.scenes), selectinload(Chapter.sections))
    )
    chapter = result.scalar_one_or_none()
    if not chapter:
        raise HTTPException(status_code=404, detail="章节不存在")
    return chapter


@router.put("/projects/{project_id}/chapters/{chapter_id}", response_model=ChapterResponse)
async def update_chapter(
    project_id: uuid.UUID,
    chapter_id: uuid.UUID,
    data: ChapterUpdate,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Chapter).where(Chapter.id == chapter_id, Chapter.project_id == project_id)
    )
    chapter = result.scalar_one_or_none()
    if not chapter:
        raise HTTPException(status_code=404, detail="章节不存在")

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(chapter, key, value)

    await db.commit()
    await db.refresh(chapter)
    try:
        from websocket.manager import ws_manager
        await ws_manager.send_chapter_updated(str(project_id), str(chapter.id))
    except Exception:
        pass
    return chapter


@router.delete("/projects/{project_id}/chapters/{chapter_id}", status_code=204)
async def delete_chapter(
    project_id: uuid.UUID,
    chapter_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Chapter).where(Chapter.id == chapter_id, Chapter.project_id == project_id)
    )
    chapter = result.scalar_one_or_none()
    if not chapter:
        raise HTTPException(status_code=404, detail="章节不存在")
    await db.delete(chapter)
    await db.commit()
    try:
        from websocket.manager import ws_manager
        await ws_manager.send_chapter_deleted(str(project_id), str(chapter_id))
    except Exception:
        pass


# ========== Section CRUD ==========


@router.get(
    "/projects/{project_id}/chapters/{chapter_id}/sections",
    response_model=list[SectionResponse],
)
async def list_sections(
    project_id: uuid.UUID,
    chapter_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ChapterSection)
        .where(
            ChapterSection.project_id == project_id,
            ChapterSection.chapter_id == chapter_id,
        )
        .order_by(ChapterSection.section_number)
    )
    return result.scalars().all()


@router.post(
    "/projects/{project_id}/chapters/{chapter_id}/sections",
    response_model=SectionResponse,
    status_code=201,
)
async def create_section(
    project_id: uuid.UUID,
    chapter_id: uuid.UUID,
    data: SectionCreate,
    db: AsyncSession = Depends(get_db),
):
    chapter_result = await db.execute(
        select(Chapter).where(Chapter.id == chapter_id, Chapter.project_id == project_id)
    )
    if not chapter_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="章节不存在")

    section = ChapterSection(
        id=uuid.uuid4(),
        project_id=project_id,
        chapter_id=chapter_id,
        **data.model_dump(exclude_none=True),
    )
    db.add(section)
    await db.commit()
    await db.refresh(section)
    return section


@router.get(
    "/projects/{project_id}/chapters/{chapter_id}/sections/{section_id}",
    response_model=SectionResponse,
)
async def get_section(
    project_id: uuid.UUID,
    chapter_id: uuid.UUID,
    section_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ChapterSection).where(
            ChapterSection.id == section_id,
            ChapterSection.project_id == project_id,
            ChapterSection.chapter_id == chapter_id,
        )
    )
    section = result.scalar_one_or_none()
    if not section:
        raise HTTPException(status_code=404, detail="节不存在")
    return section


@router.put(
    "/projects/{project_id}/chapters/{chapter_id}/sections/{section_id}",
    response_model=SectionResponse,
)
async def update_section(
    project_id: uuid.UUID,
    chapter_id: uuid.UUID,
    section_id: uuid.UUID,
    data: SectionUpdate,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ChapterSection).where(
            ChapterSection.id == section_id,
            ChapterSection.project_id == project_id,
            ChapterSection.chapter_id == chapter_id,
        )
    )
    section = result.scalar_one_or_none()
    if not section:
        raise HTTPException(status_code=404, detail="节不存在")

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(section, key, value)

    await db.commit()
    await db.refresh(section)
    return section


@router.delete(
    "/projects/{project_id}/chapters/{chapter_id}/sections/{section_id}",
    status_code=204,
)
async def delete_section(
    project_id: uuid.UUID,
    chapter_id: uuid.UUID,
    section_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ChapterSection).where(
            ChapterSection.id == section_id,
            ChapterSection.project_id == project_id,
            ChapterSection.chapter_id == chapter_id,
        )
    )
    section = result.scalar_one_or_none()
    if not section:
        raise HTTPException(status_code=404, detail="节不存在")
    await db.delete(section)
    await db.commit()


# ========== ChoiceDesign CRUD ==========


@router.get(
    "/projects/{project_id}/chapters/{chapter_id}/sections/{section_id}/choices",
    response_model=list[ChoiceDesignResponse],
)
async def list_choices(
    project_id: uuid.UUID,
    chapter_id: uuid.UUID,
    section_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ChoiceDesign).where(
            ChoiceDesign.project_id == project_id,
            ChoiceDesign.section_id == section_id,
        ).order_by(ChoiceDesign.choice_number)
    )
    return result.scalars().all()


@router.post(
    "/projects/{project_id}/chapters/{chapter_id}/sections/{section_id}/choices",
    response_model=ChoiceDesignResponse,
    status_code=201,
)
async def create_choice(
    project_id: uuid.UUID,
    chapter_id: uuid.UUID,
    section_id: uuid.UUID,
    data: ChoiceDesignCreate,
    db: AsyncSession = Depends(get_db),
):
    section_result = await db.execute(
        select(ChapterSection).where(
            ChapterSection.id == section_id,
            ChapterSection.project_id == project_id,
            ChapterSection.chapter_id == chapter_id,
        )
    )
    if not section_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="节不存在")

    choice = ChoiceDesign(
        id=uuid.uuid4(),
        project_id=project_id,
        section_id=section_id,
        **data.model_dump(exclude_none=True),
    )
    db.add(choice)
    await db.commit()
    await db.refresh(choice)
    return choice


@router.get(
    "/projects/{project_id}/chapters/{chapter_id}/sections/{section_id}/choices/{choice_id}",
    response_model=ChoiceDesignResponse,
)
async def get_choice(
    project_id: uuid.UUID,
    chapter_id: uuid.UUID,
    section_id: uuid.UUID,
    choice_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ChoiceDesign).where(
            ChoiceDesign.id == choice_id,
            ChoiceDesign.project_id == project_id,
            ChoiceDesign.section_id == section_id,
        )
    )
    choice = result.scalar_one_or_none()
    if not choice:
        raise HTTPException(status_code=404, detail="选项不存在")
    return choice


@router.put(
    "/projects/{project_id}/chapters/{chapter_id}/sections/{section_id}/choices/{choice_id}",
    response_model=ChoiceDesignResponse,
)
async def update_choice(
    project_id: uuid.UUID,
    chapter_id: uuid.UUID,
    section_id: uuid.UUID,
    choice_id: uuid.UUID,
    data: ChoiceDesignUpdate,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ChoiceDesign).where(
            ChoiceDesign.id == choice_id,
            ChoiceDesign.project_id == project_id,
            ChoiceDesign.section_id == section_id,
        )
    )
    choice = result.scalar_one_or_none()
    if not choice:
        raise HTTPException(status_code=404, detail="选项不存在")

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(choice, key, value)

    await db.commit()
    await db.refresh(choice)
    return choice


@router.delete(
    "/projects/{project_id}/chapters/{chapter_id}/sections/{section_id}/choices/{choice_id}",
    status_code=204,
)
async def delete_choice(
    project_id: uuid.UUID,
    chapter_id: uuid.UUID,
    section_id: uuid.UUID,
    choice_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ChoiceDesign).where(
            ChoiceDesign.id == choice_id,
            ChoiceDesign.project_id == project_id,
            ChoiceDesign.section_id == section_id,
        )
    )
    choice = result.scalar_one_or_none()
    if not choice:
        raise HTTPException(status_code=404, detail="选项不存在")
    await db.delete(choice)
    await db.commit()
