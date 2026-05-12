import uuid
import logging
from datetime import datetime, UTC
from fastapi import APIRouter, Depends, HTTPException, Query, Body
from sqlalchemy import select, func, delete, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.orm.attributes import flag_modified
from sqlalchemy.exc import OperationalError

from database import get_db
from models.project import Project
from models.scene import Scene
from models.foreshadow import Foreshadow
from models.character import Character
from models.audit import AuditRecord
from models.chapter import Chapter
from models.emotion_curve import EmotionCurve
from models.project_config import ProjectConfig
from schemas.project import (
    ProjectCreate, ProjectUpdate, ProjectResponse,
    ProjectConfigSchema, ProjectListResponse,
)
from core.script_generator.config_recommender import ConfigRecommender

logger = logging.getLogger(__name__)
router = APIRouter()

WORLD_CONFIG_META = {
    "core_contradiction": {"label": "核心矛盾", "desc": "世界运行的终极矛盾，驱动所有剧情发展的核心动力"},
    "social_structure": {"label": "社会结构", "desc": "权力分布、阶层划分、组织关系"},
    "tech_magic": {"label": "科技/魔法体系", "desc": "能力上限、代价、规则、稀有度"},
    "geography": {"label": "地理环境", "desc": "世界地图、重要地标、气候特征"},
    "history": {"label": "历史背景", "desc": "重大历史事件、传说、被掩盖的真相"},
    "culture": {"label": "文化习俗", "desc": "信仰、节日、禁忌、性别观、道德观"},
    "constraints": {"label": "约束条件", "desc": "人物行为在剧情中的硬性限制"},
    "impossible": {"label": "不可能事项", "desc": "这个世界绝对不可能发生的事"},
}

WORLD_SETTINGS_BUCKET = "world_settings"
WORLD_LOCKS_BUCKET = "world_config_locks"


def _ensure_custom_rule_buckets(config: ProjectConfig) -> dict:
    payload = dict(config.custom_checker_rules or {})
    if not isinstance(payload.get(WORLD_SETTINGS_BUCKET), dict):
        payload[WORLD_SETTINGS_BUCKET] = {}
    if not isinstance(payload.get(WORLD_LOCKS_BUCKET), dict):
        payload[WORLD_LOCKS_BUCKET] = {}
    return payload


def _get_world_config_value(config: ProjectConfig, key: str):
    if hasattr(config, key):
        return getattr(config, key)
    payload = _ensure_custom_rule_buckets(config)
    return payload[WORLD_SETTINGS_BUCKET].get(key, "")


def _set_world_config_value(config: ProjectConfig, key: str, value):
    if hasattr(config, key):
        setattr(config, key, value)
        return
    payload = _ensure_custom_rule_buckets(config)
    payload[WORLD_SETTINGS_BUCKET][key] = value
    config.custom_checker_rules = payload


def _set_world_config_lock(config: ProjectConfig, key: str, is_locked: bool):
    payload = _ensure_custom_rule_buckets(config)
    if is_locked:
        payload[WORLD_LOCKS_BUCKET][key] = {
            "is_locked": True,
            "locked_at": datetime.now(UTC).isoformat(),
        }
    else:
        payload[WORLD_LOCKS_BUCKET].pop(key, None)
    config.custom_checker_rules = payload


def _serialize_world_config_items(project_id: str, config: ProjectConfig) -> list[dict]:
    payload = _ensure_custom_rule_buckets(config)
    locks = payload[WORLD_LOCKS_BUCKET]
    items = []
    for key, meta in WORLD_CONFIG_META.items():
        lock_state = locks.get(key, {}) if isinstance(locks, dict) else {}
        value = _get_world_config_value(config, key)
        items.append({
            "id": f"{project_id}:{key}",
            "config_key": key,
            "config_value": "" if value is None else str(value),
            "label": meta["label"],
            "desc": meta["desc"],
            "is_locked": bool(lock_state.get("is_locked", False)),
            "locked_at": lock_state.get("locked_at"),
        })
    return items


async def _safe_execute(db: AsyncSession, statement, params: dict | None = None) -> None:
    try:
        if params is None:
            await db.execute(statement)
        else:
            await db.execute(statement, params)
    except OperationalError as exc:
        if "no such table" not in str(exc).lower():
            raise


def _project_to_response(project: Project) -> ProjectResponse:
    config_data = None
    if project.config:
        cfg = project.config
        config_data = ProjectConfigSchema(
            target_word_count=cfg.target_word_count or 50000,
            genre=cfg.genre or "",
            sub_genre=cfg.sub_genre or "",
            core_contradiction=cfg.core_contradiction or "",
            theme=cfg.theme or "",
            tone=cfg.tone or "neutral",
            chapter_count=cfg.chapter_count or 10,
            min_words_per_chapter=cfg.min_words_per_chapter or 2000,
            max_words_per_chapter=cfg.max_words_per_chapter or 8000,
            scenes_per_chapter_min=cfg.scenes_per_chapter_min or 2,
            scenes_per_chapter_max=cfg.scenes_per_chapter_max or 6,
            target_ending_count=cfg.target_ending_count or 3,
            max_branch_depth=cfg.max_branch_depth or 3,
            min_branches_per_choice=cfg.min_branches_per_choice or 2,
            max_branches_per_choice=cfg.max_branches_per_choice or 4,
            wow_moment_density=cfg.wow_moment_density or 2.5,
            min_dialogue_ratio=cfg.min_dialogue_ratio or 0.20,
            max_narration_ratio=cfg.max_narration_ratio or 0.50,
            narrative_pov=cfg.narrative_pov or "third_person",
            writing_style=cfg.writing_style or "",
            language_complexity=cfg.language_complexity or "medium",
            world_building_depth=cfg.world_building_depth or 5,
            character_depth_target=cfg.character_depth_target or 5,
            plot_complexity=cfg.plot_complexity or 5,
            commercial_fit=cfg.commercial_fit or "",
            target_audience=cfg.target_audience or "",
            age_rating=cfg.age_rating or "general",
            enable_constraint_checking=cfg.enable_constraint_checking if cfg.enable_constraint_checking is not None else True,
            enable_water_detection=cfg.enable_water_detection if cfg.enable_water_detection is not None else True,
            enable_genre_alignment=cfg.enable_genre_alignment if cfg.enable_genre_alignment is not None else True,
            enable_voice_consistency=cfg.enable_voice_consistency if cfg.enable_voice_consistency is not None else True,
            enable_conflict_tracking=cfg.enable_conflict_tracking if cfg.enable_conflict_tracking is not None else True,
            enable_satisfaction_tracking=cfg.enable_satisfaction_tracking if cfg.enable_satisfaction_tracking is not None else True,
            custom_evaluation_weights=cfg.custom_evaluation_weights,
            custom_checker_rules=cfg.custom_checker_rules,
            creator_prompt_template=cfg.creator_prompt_template or "",
            auditor_prompt_template=cfg.auditor_prompt_template or "",
            language=cfg.language or "zh-CN",
            work_mode=cfg.work_mode or "standard",
            player_count=cfg.player_count or "single",
            style=cfg.style or "",
        )

    return ProjectResponse(
        id=project.id,
        name=project.name,
        description=project.description or "",
        status=project.status or "draft",
        template_id=project.template_id,
        config=config_data,
        created_at=project.created_at or datetime.now(UTC),
        updated_at=project.updated_at or datetime.now(UTC),
    )


@router.post("/projects", response_model=ProjectResponse, status_code=201)
async def create_project(data: ProjectCreate, db: AsyncSession = Depends(get_db)):
    config_data = data.config or ProjectConfigSchema()

    project = Project(
        id=str(uuid.uuid4()),
        name=data.name,
        description=data.description or "",
        status="draft",
        template_id=data.template_id or "interactive_drama",
    )
    db.add(project)
    await db.flush()

    project_config = ProjectConfig(
        project_id=project.id,
        target_word_count=config_data.target_word_count,
        genre=config_data.genre,
        sub_genre=config_data.sub_genre,
        core_contradiction=config_data.core_contradiction,
        theme=config_data.theme,
        tone=config_data.tone,
        chapter_count=config_data.chapter_count,
        min_words_per_chapter=config_data.min_words_per_chapter,
        max_words_per_chapter=config_data.max_words_per_chapter,
        scenes_per_chapter_min=config_data.scenes_per_chapter_min,
        scenes_per_chapter_max=config_data.scenes_per_chapter_max,
        target_ending_count=config_data.target_ending_count,
        max_branch_depth=config_data.max_branch_depth,
        min_branches_per_choice=config_data.min_branches_per_choice,
        max_branches_per_choice=config_data.max_branches_per_choice,
        wow_moment_density=config_data.wow_moment_density,
        min_dialogue_ratio=config_data.min_dialogue_ratio,
        max_narration_ratio=config_data.max_narration_ratio,
        narrative_pov=config_data.narrative_pov,
        writing_style=config_data.writing_style,
        language_complexity=config_data.language_complexity,
        world_building_depth=config_data.world_building_depth,
        character_depth_target=config_data.character_depth_target,
        plot_complexity=config_data.plot_complexity,
        commercial_fit=config_data.commercial_fit,
        target_audience=config_data.target_audience,
        age_rating=config_data.age_rating,
        enable_constraint_checking=config_data.enable_constraint_checking,
        enable_water_detection=config_data.enable_water_detection,
        enable_genre_alignment=config_data.enable_genre_alignment,
        enable_voice_consistency=config_data.enable_voice_consistency,
        enable_conflict_tracking=config_data.enable_conflict_tracking,
        enable_satisfaction_tracking=config_data.enable_satisfaction_tracking,
        custom_evaluation_weights=config_data.custom_evaluation_weights,
        custom_checker_rules=config_data.custom_checker_rules,
        creator_prompt_template=config_data.creator_prompt_template,
        auditor_prompt_template=config_data.auditor_prompt_template,
        language=config_data.language,
        work_mode=config_data.work_mode,
        player_count=config_data.player_count,
        style=config_data.style,
    )
    db.add(project_config)
    await db.commit()

    project_result = await db.execute(
        select(Project)
        .options(selectinload(Project.config))
        .where(Project.id == project.id)
    )
    project = project_result.scalar_one()

    try:
        from core.pipeline.state_machine import PipelineStateMachine
        sm = PipelineStateMachine(db)
        template = data.template_id or "interactive_drama"
        await sm.init(project.id, template, {})
    except Exception as e:
        logger.warning("Pipeline init skipped: %s", e)

    return _project_to_response(project)


@router.get("/projects", response_model=ProjectListResponse)
async def list_projects(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    count_result = await db.execute(select(func.count(Project.id)))
    total = count_result.scalar_one()

    result = await db.execute(
        select(Project)
        .options(selectinload(Project.config))
        .order_by(Project.updated_at.desc())
        .limit(limit).offset(offset)
    )
    projects = result.scalars().all()

    return ProjectListResponse(
        projects=[_project_to_response(p) for p in projects],
        total=total,
    )


@router.get("/projects/{project_id}", response_model=ProjectResponse)
async def get_project(project_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Project)
        .options(selectinload(Project.config))
        .where(Project.id == project_id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    return _project_to_response(project)


@router.put("/projects/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: str,
    data: ProjectUpdate,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    if data.name is not None:
        project.name = data.name
    if data.description is not None:
        project.description = data.description
    if data.status is not None:
        project.status = data.status
    project.updated_at = datetime.now(UTC)
    await db.flush()

    if data.config is not None:
        cfg = data.config
        config_result = await db.execute(
            select(ProjectConfig).where(ProjectConfig.project_id == project_id)
        )
        existing_config = config_result.scalar_one_or_none()

        if existing_config:
            for field_name in ProjectConfigSchema.model_fields:
                value = getattr(cfg, field_name, None)
                if value is not None:
                    setattr(existing_config, field_name, value)
            existing_config.updated_at = datetime.now(UTC)
        else:
            new_config = ProjectConfig(
                project_id=project_id,
                target_word_count=cfg.target_word_count,
                genre=cfg.genre,
                sub_genre=cfg.sub_genre,
                core_contradiction=cfg.core_contradiction,
                theme=cfg.theme,
                tone=cfg.tone,
                chapter_count=cfg.chapter_count,
                min_words_per_chapter=cfg.min_words_per_chapter,
                max_words_per_chapter=cfg.max_words_per_chapter,
                scenes_per_chapter_min=cfg.scenes_per_chapter_min,
                scenes_per_chapter_max=cfg.scenes_per_chapter_max,
                target_ending_count=cfg.target_ending_count,
                max_branch_depth=cfg.max_branch_depth,
                min_branches_per_choice=cfg.min_branches_per_choice,
                max_branches_per_choice=cfg.max_branches_per_choice,
                wow_moment_density=cfg.wow_moment_density,
                min_dialogue_ratio=cfg.min_dialogue_ratio,
                max_narration_ratio=cfg.max_narration_ratio,
                narrative_pov=cfg.narrative_pov,
                writing_style=cfg.writing_style,
                language_complexity=cfg.language_complexity,
                world_building_depth=cfg.world_building_depth,
                character_depth_target=cfg.character_depth_target,
                plot_complexity=cfg.plot_complexity,
                commercial_fit=cfg.commercial_fit,
                target_audience=cfg.target_audience,
                age_rating=cfg.age_rating,
                enable_constraint_checking=cfg.enable_constraint_checking,
                enable_water_detection=cfg.enable_water_detection,
                enable_genre_alignment=cfg.enable_genre_alignment,
                enable_voice_consistency=cfg.enable_voice_consistency,
                enable_conflict_tracking=cfg.enable_conflict_tracking,
                enable_satisfaction_tracking=cfg.enable_satisfaction_tracking,
                custom_evaluation_weights=cfg.custom_evaluation_weights,
                custom_checker_rules=cfg.custom_checker_rules,
                creator_prompt_template=cfg.creator_prompt_template,
                auditor_prompt_template=cfg.auditor_prompt_template,
                language=cfg.language,
                work_mode=cfg.work_mode,
                player_count=cfg.player_count,
                style=cfg.style,
            )
            db.add(new_config)

    await db.commit()

    project_result = await db.execute(
        select(Project)
        .options(selectinload(Project.config))
        .where(Project.id == project_id)
    )
    project = project_result.scalar_one()

    return _project_to_response(project)


@router.delete("/projects/{project_id}", status_code=204)
async def delete_project(project_id: str, db: AsyncSession = Depends(get_db)):
    from models.project_config import ProjectConfig
    from models.scene import Scene, SceneVersion
    from models.foreshadow import Foreshadow, ForeshadowRelation
    from models.chapter import Chapter
    from models.character import Character, CharacterRelation
    from models.audit import AuditRecord
    from models.emotion_curve import EmotionCurve
    from models.element import Element, InfoPoint
    from models.agent_task import AgentTask

    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    scene_ids_result = await db.execute(
        select(Scene.id).where(Scene.project_id == project_id)
    )
    scene_ids = [row[0] for row in scene_ids_result.all()]

    chapter_ids_result = await db.execute(
        select(Chapter.id).where(Chapter.project_id == project_id)
    )
    chapter_ids = [row[0] for row in chapter_ids_result.all()]

    char_ids_result = await db.execute(
        select(Character.id).where(Character.project_id == project_id)
    )
    char_ids = [row[0] for row in char_ids_result.all()]

    fs_ids_result = await db.execute(
        select(Foreshadow.id).where(Foreshadow.project_id == project_id)
    )
    fs_ids = [row[0] for row in fs_ids_result.all()]

    if scene_ids:
        await _safe_execute(db, delete(SceneVersion).where(SceneVersion.scene_id.in_(scene_ids)))
        await _safe_execute(db, delete(AuditRecord).where(AuditRecord.scene_id.in_(scene_ids)))

    if chapter_ids:
        await _safe_execute(db, delete(EmotionCurve).where(EmotionCurve.chapter_id.in_(chapter_ids)))

    if scene_ids:
        await _safe_execute(db, delete(EmotionCurve).where(EmotionCurve.scene_id.in_(scene_ids)))

    if char_ids:
        await _safe_execute(db, delete(CharacterRelation).where(
            CharacterRelation.char_a_id.in_(char_ids) | CharacterRelation.char_b_id.in_(char_ids)
        ))

    if fs_ids:
        await _safe_execute(db, delete(ForeshadowRelation).where(
            ForeshadowRelation.from_fs_id.in_(fs_ids) | ForeshadowRelation.to_fs_id.in_(fs_ids)
        ))

    await _safe_execute(db, delete(EmotionCurve).where(EmotionCurve.project_id == project_id))
    await _safe_execute(db, delete(AuditRecord).where(AuditRecord.project_id == project_id))
    await _safe_execute(db, delete(AgentTask).where(AgentTask.project_id == project_id))
    await _safe_execute(db, delete(InfoPoint).where(InfoPoint.project_id == project_id))
    await _safe_execute(db, delete(Element).where(Element.project_id == project_id))
    await _safe_execute(db, delete(Scene).where(Scene.project_id == project_id))
    await _safe_execute(db, delete(Chapter).where(Chapter.project_id == project_id))
    await _safe_execute(db, delete(Character).where(Character.project_id == project_id))
    await _safe_execute(db, delete(Foreshadow).where(Foreshadow.project_id == project_id))
    await _safe_execute(db, delete(ProjectConfig).where(ProjectConfig.project_id == project_id))
    await _safe_execute(db, text("DELETE FROM pipeline_state WHERE project_id = :project_id"), {"project_id": project_id})
    await _safe_execute(db, delete(Project).where(Project.id == project_id))
    await db.commit()


@router.get("/projects/{project_id}/config")
async def get_project_config(project_id: str, db: AsyncSession = Depends(get_db)):
    from models.project_config import ProjectConfig

    result = await db.execute(
        select(ProjectConfig).where(ProjectConfig.project_id == project_id)
    )
    config = result.scalar_one_or_none()
    if not config:
        return {"configs": []}
    return {"configs": _serialize_world_config_items(project_id, config)}


@router.put("/projects/{project_id}/config/{key}")
async def update_project_config_key(
    project_id: str, key: str,
    data: dict = Body(default=None),
    db: AsyncSession = Depends(get_db),
):
    from models.project_config import ProjectConfig

    result = await db.execute(
        select(ProjectConfig).where(ProjectConfig.project_id == project_id)
    )
    config = result.scalar_one_or_none()
    if not config:
        raise HTTPException(status_code=404, detail="项目配置不存在")
    if key not in WORLD_CONFIG_META and not hasattr(config, key):
        raise HTTPException(status_code=400, detail=f"无效的配置项: {key}")

    payload = data or {}
    has_value = "config_value" in payload
    has_lock = "is_locked" in payload

    if not has_value and not has_lock:
        raise HTTPException(status_code=400, detail="缺少可更新字段")

    rules_payload = _ensure_custom_rule_buckets(config)

    if has_value:
        if hasattr(config, key):
            setattr(config, key, payload.get("config_value", ""))
        else:
            rules_payload[WORLD_SETTINGS_BUCKET][key] = payload.get("config_value", "")

    if has_lock:
        if bool(payload.get("is_locked")):
            rules_payload[WORLD_LOCKS_BUCKET][key] = {
                "is_locked": True,
                "locked_at": datetime.now(UTC).isoformat(),
            }
        else:
            rules_payload[WORLD_LOCKS_BUCKET].pop(key, None)

    if not hasattr(config, key) or has_lock:
        config.custom_checker_rules = rules_payload
        flag_modified(config, "custom_checker_rules")

    config.updated_at = datetime.now(UTC)
    await db.commit()

    current_value = _get_world_config_value(config, key)
    lock_payload = _ensure_custom_rule_buckets(config)[WORLD_LOCKS_BUCKET].get(key, {})
    return {
        "status": "ok",
        "key": key,
        "value": "" if current_value is None else str(current_value),
        "is_locked": bool(lock_payload.get("is_locked", False)),
        "locked_at": lock_payload.get("locked_at"),
    }


@router.post("/projects/{project_id}/reset")
async def reset_project(project_id: str, db: AsyncSession = Depends(get_db)):
    from models.scene import Scene
    from models.foreshadow import Foreshadow
    from models.chapter import Chapter

    scene_result = await db.execute(
        select(Scene).where(Scene.project_id == project_id)
    )
    for scene in scene_result.scalars().all():
        await db.delete(scene)

    fs_result = await db.execute(
        select(Foreshadow).where(Foreshadow.project_id == project_id)
    )
    for fs in fs_result.scalars().all():
        await db.delete(fs)

    ch_result = await db.execute(
        select(Chapter).where(Chapter.project_id == project_id)
    )
    for ch in ch_result.scalars().all():
        await db.delete(ch)

    project_result = await db.execute(
        select(Project).where(Project.id == project_id)
    )
    project = project_result.scalar_one_or_none()
    if project:
        project.status = "draft"

    await db.commit()
    return {"status": "ok", "message": "项目已重置"}


@router.post("/projects/recommend-config")
async def recommend_config(
    data: dict = Body(default=None),
):
    """
    根据目标字数和体裁推荐项目配置参数
    """
    payload = data or {}
    target_word_count = payload.get("target_word_count", 50000)
    genre = payload.get("genre", "")
    work_mode = payload.get("work_mode", "standard")
    player_count = payload.get("player_count", "single")

    recommendation = ConfigRecommender.recommend(
        target_word_count=target_word_count,
        genre=genre,
        work_mode=work_mode,
        player_count=player_count,
    )

    return {
        "target_word_count": target_word_count,
        "scale_tier": ConfigRecommender.get_scale_tier(target_word_count / 10000),
        "recommendation": {
            "chapter_count": recommendation.chapter_count,
            "min_words_per_chapter": recommendation.min_words_per_chapter,
            "max_words_per_chapter": recommendation.max_words_per_chapter,
            "scenes_per_chapter_min": recommendation.scenes_per_chapter_min,
            "scenes_per_chapter_max": recommendation.scenes_per_chapter_max,
            "target_ending_count": recommendation.target_ending_count,
            "max_branch_depth": recommendation.max_branch_depth,
            "min_branches_per_choice": recommendation.min_branches_per_choice,
            "max_branches_per_choice": recommendation.max_branches_per_choice,
            "wow_moment_density": recommendation.wow_moment_density,
            "world_building_depth": recommendation.world_building_depth,
            "character_depth_target": recommendation.character_depth_target,
            "plot_complexity": recommendation.plot_complexity,
            "min_dialogue_ratio": recommendation.min_dialogue_ratio,
            "max_narration_ratio": recommendation.max_narration_ratio,
        },
        "estimates": {
            "total_scenes": recommendation.estimated_total_scenes,
            "wow_moments": recommendation.estimated_wow_moments,
            "branch_nodes": recommendation.estimated_branch_nodes,
        },
        "genre_notes": recommendation.genre_notes,
        "reasoning": recommendation.reasoning,
    }


@router.post("/projects/validate-config")
async def validate_config(
    data: dict = Body(default=None),
):
    """
    验证项目配置参数是否合理
    """
    payload = data or {}
    target_word_count = payload.get("target_word_count", 50000)
    chapter_count = payload.get("chapter_count", 10)
    min_words_per_chapter = payload.get("min_words_per_chapter", 2000)
    max_words_per_chapter = payload.get("max_words_per_chapter", 8000)
    target_ending_count = payload.get("target_ending_count", 3)
    max_branch_depth = payload.get("max_branch_depth", 3)

    is_valid, message, suggestions = ConfigRecommender.validate_and_adjust(
        target_word_count=target_word_count,
        chapter_count=chapter_count,
        min_words_per_chapter=min_words_per_chapter,
        max_words_per_chapter=max_words_per_chapter,
        target_ending_count=target_ending_count,
        max_branch_depth=max_branch_depth,
    )

    return {
        "is_valid": is_valid,
        "message": message,
        "suggestions": suggestions,
    }


PHASE_NAMES = [
    "世界观构建",
    "角色创建",
    "章节规划",
    "场景创作",
    "审核与修订",
    "伏笔管理",
    "导出发布",
]


@router.get("/projects/{project_id}/dashboard")
async def get_dashboard(project_id: str, db: AsyncSession = Depends(get_db)):
    project_result = await db.execute(select(Project).where(Project.id == project_id))
    project = project_result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    config_result = await db.execute(
        select(ProjectConfig).where(ProjectConfig.project_id == project_id)
    )
    config = config_result.scalar_one_or_none()

    total_word_count_result = await db.execute(
        select(func.sum(func.length(func.coalesce(Scene.narration, "")))).where(Scene.project_id == project_id)
    )
    total_word_count = total_word_count_result.scalar_one() or 0

    scene_count_result = await db.execute(
        select(func.count(Scene.id)).where(Scene.project_id == project_id)
    )
    scene_count = scene_count_result.scalar_one() or 0

    status_counts_result = await db.execute(
        select(Scene.status, func.count(Scene.id))
        .where(Scene.project_id == project_id)
        .group_by(Scene.status)
    )
    status_counts = dict(status_counts_result.all())

    foreshadow_count_result = await db.execute(
        select(func.count(Foreshadow.id)).where(Foreshadow.project_id == project_id)
    )
    foreshadow_count = foreshadow_count_result.scalar_one() or 0

    character_count_result = await db.execute(
        select(func.count(Character.id)).where(Character.project_id == project_id)
    )
    character_count = character_count_result.scalar_one() or 0

    choice_count = 0
    scenes_for_choices = await db.execute(
        select(Scene.choices).where(Scene.project_id == project_id)
    )
    for (choices,) in scenes_for_choices.all():
        if choices and isinstance(choices, list):
            choice_count += len(choices)

    chapter_count_result = await db.execute(
        select(func.count(Chapter.id)).where(Chapter.project_id == project_id)
    )
    chapter_count = chapter_count_result.scalar_one() or 0

    target_word_count = config.target_word_count if config else 50000
    word_progress = round(total_word_count / max(target_word_count, 1) * 100, 1) if target_word_count else 0

    recent_activity = []
    audit_result = await db.execute(
        select(AuditRecord)
        .where(AuditRecord.project_id == project_id)
        .order_by(AuditRecord.created_at.desc())
        .limit(10)
    )
    for record in audit_result.scalars().all():
        recent_activity.append({
            "type": record.audit_type,
            "description": f"审核结果: {record.overall_result or '无'}",
            "timestamp": record.created_at.isoformat() if record.created_at else "",
        })

    emotion_preview = []
    chapters_result = await db.execute(
        select(Chapter).where(Chapter.project_id == project_id).order_by(Chapter.chapter_number)
    )
    chapters_list = chapters_result.scalars().all()
    for ch in chapters_list:
        avg_emotion_result = await db.execute(
            select(func.avg(func.coalesce(EmotionCurve.actual_emotion, EmotionCurve.target_emotion)))
            .where(EmotionCurve.chapter_id == ch.id)
        )
        avg_emotion = avg_emotion_result.scalar_one()
        if avg_emotion is not None:
            emotion_value = float(avg_emotion)
        elif ch.emotion_target is not None:
            emotion_value = float(ch.emotion_target)
        else:
            emotion_value = 0.0
        emotion_preview.append({
            "chapter": ch.title or f"第{ch.chapter_number}章",
            "emotion": emotion_value,
        })

    fs_health_result = await db.execute(
        select(Foreshadow.health, func.count(Foreshadow.id))
        .where(Foreshadow.project_id == project_id)
        .group_by(Foreshadow.health)
    )
    fs_health_counts = dict(fs_health_result.all())
    foreshadows_normal = fs_health_counts.get("normal", 0)
    foreshadows_warning = fs_health_counts.get("warning", 0)
    foreshadows_danger = fs_health_counts.get("danger", 0)

    phase_progress = await _compute_phase_progress(
        db, project_id, chapter_count, scene_count,
        status_counts, foreshadow_count, character_count,
    )

    return {
        "project": {
            "id": str(project.id),
            "name": project.name,
            "description": project.description,
            "status": project.status,
            "genre": config.genre if config else "",
            "style": config.writing_style if config else "",
            "target_word_count": target_word_count,
            "current_word_count": total_word_count,
            "word_progress": word_progress,
            "chapter_count": chapter_count,
            "template_id": project.template_id,
            "current_phase": phase_progress["current_phase"],
        },
        "stats": {
            "total_word_count": total_word_count,
            "target_word_count": target_word_count,
            "word_progress": word_progress,
            "scene_count": scene_count,
            "scenes_draft": status_counts.get("draft", 0),
            "scenes_auditing": status_counts.get("auditing", 0),
            "scenes_approved": status_counts.get("approved", 0) + status_counts.get("passed", 0),
            "scenes_final": status_counts.get("final", 0),
            "foreshadow_count": foreshadow_count,
            "foreshadows_normal": foreshadows_normal,
            "foreshadows_warning": foreshadows_warning,
            "foreshadows_danger": foreshadows_danger,
            "character_count": character_count,
            "choice_count": choice_count,
            "chapter_count": chapter_count,
        },
        "config": {
            "genre": config.genre if config else "",
            "core_contradiction": config.core_contradiction if config else "",
            "theme": config.theme if config else "",
            "tone": config.tone if config else "neutral",
            "chapter_count": config.chapter_count if config else 10,
            "target_ending_count": config.target_ending_count if config else 3,
            "wow_moment_density": config.wow_moment_density if config else 2.5,
            "world_building_depth": config.world_building_depth if config else 5,
            "character_depth_target": config.character_depth_target if config else 5,
            "plot_complexity": config.plot_complexity if config else 5,
        },
        "phase_progress": phase_progress,
        "recent_activity": recent_activity,
        "emotion_curve_preview": emotion_preview,
    }


async def _compute_phase_progress(
    db: AsyncSession, project_id: str,
    chapter_count: int, scene_count: int,
    status_counts: dict, foreshadow_count: int, character_count: int,
) -> dict:
    from models.project_config import ProjectConfig as PC

    config_result = await db.execute(select(PC).where(PC.project_id == project_id))
    config = config_result.scalar_one_or_none()

    target_chapters = config.chapter_count if config else 10
    target_word_count = config.target_word_count if config else 50000

    word_count_result = await db.execute(
        select(func.sum(func.length(func.coalesce(Scene.narration, "")))).where(Scene.project_id == project_id)
    )
    total_words = word_count_result.scalar_one() or 0

    scenes_final = status_counts.get("final", 0) + status_counts.get("approved", 0)
    scenes_total = max(scene_count, 1)

    phases = [
        {"phase": 0, "name": "世界观构建", "percent": min(100, round(character_count * 5, 1)) if character_count > 0 else 0},
        {"phase": 1, "name": "角色创建", "percent": min(100, round(character_count / max(1, 8) * 100, 1))},
        {"phase": 2, "name": "章节规划", "percent": min(100, round(chapter_count / max(1, target_chapters) * 100, 1))},
        {"phase": 3, "name": "场景创作", "percent": min(100, round(scenes_final / scenes_total * 100, 1))},
        {"phase": 4, "name": "审核与修订", "percent": min(100, round(status_counts.get("final", 0) / scenes_total * 100, 1))},
        {"phase": 5, "name": "伏笔管理", "percent": min(100, round(foreshadow_count / max(1, 30) * 100, 1)) if foreshadow_count > 0 else 0},
        {"phase": 6, "name": "导出发布", "percent": min(100, round(total_words / max(1, target_word_count) * 100, 1))},
    ]

    current_phase = 0
    for i, p in enumerate(phases):
        if p["percent"] < 100:
            current_phase = i
            break
        current_phase = i

    return {
        "current_phase": current_phase,
        "phases": phases,
    }
