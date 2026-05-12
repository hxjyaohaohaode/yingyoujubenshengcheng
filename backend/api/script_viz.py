import json
import uuid
import logging
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/script-viz")


class ScriptAnalysisResult(BaseModel):
    project_id: str
    characters: list[dict]
    relations: list[dict]
    scenes: list[dict]
    foreshadows: list[dict]
    events: list[dict]
    scene_links: list[dict]
    foreshadow_links: list[dict]


class RegenerateRequest(BaseModel):
    edits: list[dict]
    target_type: str


class RegenerateResponse(BaseModel):
    new_project_id: str
    old_project_id: str
    changes_summary: str
    updated_content: dict


async def _parse_with_ai(intent: str, system_prompt: str, user_prompt: str, temperature: float = 0.5, max_tokens: int = 4096) -> str:
    from core.gateway.client import get_gateway

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
    try:
        gateway = get_gateway()
        result = await gateway.invoke(
            intent=intent,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            cost_profile="balanced",
        )
        return result.content
    except Exception as e:
        logger.error("AI parse failed: %s", str(e))
        raise HTTPException(status_code=502, detail=f"AI 解析服务不可用: {str(e)}")


async def _extract_json(text: str) -> dict | list:
    import re
    match = re.search(r'\{[\s\S]*\}', text)
    if match:
        return json.loads(match.group(0))
    match = re.search(r'\[[\s\S]*\]', text)
    if match:
        return json.loads(match.group(0))
    return {}


@router.post("/analyze-project/{project_id}", response_model=ScriptAnalysisResult)
async def analyze_project(project_id: str, db: AsyncSession = Depends(get_db)):
    from models.project import Project
    from models.character import Character
    from models.scene import Scene
    from models.foreshadow import Foreshadow
    from models.foreshadow import ForeshadowRelation
    from models.chapter import Chapter as ChapterModel
    from models.project_config import ProjectConfig

    project_result = await db.execute(select(Project).where(Project.id == project_id))
    project = project_result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    chars_result = await db.execute(select(Character).where(Character.project_id == project_id))
    chars = chars_result.scalars().all()

    scenes_result = await db.execute(select(Scene).where(Scene.project_id == project_id).order_by(Scene.scene_code))
    scenes = scenes_result.scalars().all()

    fs_result = await db.execute(select(Foreshadow).where(Foreshadow.project_id == project_id))
    foreshadows = fs_result.scalars().all()

    fs_rel_result = await db.execute(
        select(ForeshadowRelation).where(ForeshadowRelation.project_id == project_id)
    )
    fs_relations = fs_rel_result.scalars().all()

    chapters_result = await db.execute(
        select(ChapterModel).where(ChapterModel.project_id == project_id).order_by(ChapterModel.chapter_number)
    )
    chapters = chapters_result.scalars().all()

    characters = []
    for c in chars:
        ch = {
            "id": str(c.id), "name": c.name, "role_type": c.role_type,
            "core_goal": c.core_goal, "core_fear": c.core_fear,
            "background": (c.background or ""),
            "surface_image": c.surface_image, "true_self": c.true_self,
            "arc_description": c.arc_description, "status": c.status,
        }
        characters.append(ch)

    relations = []
    char_map = {str(c.id): c.name for c in chars}
    from models.character import CharacterRelation
    try:
        rel_result = await db.execute(
            select(CharacterRelation).where(CharacterRelation.project_id == project_id)
        )
        db_relations = rel_result.scalars().all()
        for r in db_relations:
            relations.append({
                "id": str(r.id), "char_a_id": str(r.char_a_id),
                "char_b_id": str(r.char_b_id), "relation_type": r.relation_type,
                "trust": r.trust, "favor": r.favor,
                "info_asymmetry": r.info_asymmetry if r.info_asymmetry else {},
                "is_hidden": r.is_hidden if r.is_hidden else False,
                "arc_direction": r.arc_direction or "stable",
                "trigger_condition": r.trigger_condition or "",
                "arc_milestones": r.arc_milestones if r.arc_milestones else [],
            })
    except Exception:
        pass

    scene_list = []
    for s in scenes:
        scene_list.append({
            "id": str(s.id), "scene_code": s.scene_code,
            "scene_type": s.scene_type, "location": s.location,
            "emotion_level": s.emotion_level, "status": s.status,
            "narration_preview": (s.narration or ""),
            "characters_involved": s.characters_involved or [],
            "is_wow_moment": s.is_wow_moment,
            "wow_type": s.wow_type,
            "chapter_id": str(s.chapter_id) if s.chapter_id else None,
        })

    fs_list = []
    for f in foreshadows:
        fs_list.append({
            "id": str(f.id), "fs_code": f.fs_code, "name": f.name,
            "fs_type": f.fs_type, "surface_layer": f.surface_layer,
            "deep_layer": f.deep_layer, "truth_layer": f.truth_layer,
            "health": f.health, "current_status": f.current_status,
            "reinforce_count": f.reinforce_count,
            "plant_scene_id": str(f.plant_scene_id) if f.plant_scene_id else None,
            "reveal_scene_id": str(f.reveal_scene_id) if f.reveal_scene_id else None,
            "depends_on": f.depends_on if isinstance(f.depends_on, list) else [],
            "enables": f.enables if isinstance(f.enables, list) else [],
        })

    events = []
    for s in scenes:
        if s.is_wow_moment:
            events.append({
                "id": str(s.id) + "_wow",
                "name": f"哇塞: {s.wow_type or '重要转折'}",
                "scene_id": str(s.id),
                "type": s.wow_type or "plot_twist",
                "emotion_impact": s.emotion_level,
                "chapter_number": None,
            })

    scene_links = []
    for i in range(len(scene_list) - 1):
        s1 = scene_list[i]
        s2 = scene_list[i + 1]
        causality = 5
        if s1.get("chapter_id") and s2.get("chapter_id") and s1["chapter_id"] == s2["chapter_id"]:
            causality = 7
        scene_links.append({
            "source": s1["id"], "target": s2["id"],
            "strength": causality, "type": "sequential",
        })

    for s in scene_list:
        if s.get("characters_involved"):
            for cid in s["characters_involved"]:
                cid_str = str(cid) if not isinstance(cid, str) else cid
                if cid_str in char_map:
                    scene_links.append({
                        "source": cid_str, "target": s["id"],
                        "strength": 3, "type": "appears_in",
                    })

    foreshadow_links = []
    for r in fs_relations:
        foreshadow_links.append({
            "id": str(r.id),
            "source": str(r.from_fs_id), "target": str(r.to_fs_id),
            "strength": 5, "type": r.relation_type or "related",
        })

    for f in fs_list:
        if f.get("plant_scene_id"):
            foreshadow_links.append({
                "source": f["id"], "target": f["plant_scene_id"],
                "strength": 6, "type": "planted_in",
            })
        if f.get("reveal_scene_id"):
            foreshadow_links.append({
                "source": f["id"], "target": f["reveal_scene_id"],
                "strength": 8, "type": "revealed_in",
            })

    return ScriptAnalysisResult(
        project_id=str(project_id),
        characters=characters,
        relations=relations,
        scenes=scene_list,
        foreshadows=fs_list,
        events=events,
        scene_links=scene_links,
        foreshadow_links=foreshadow_links,
    )


@router.post("/upload-parse/{project_id}")
async def upload_and_parse_script(
    project_id: uuid.UUID,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    content_bytes = await file.read()
    try:
        script_text = content_bytes.decode("utf-8")
    except UnicodeDecodeError:
        try:
            script_text = content_bytes.decode("gbk")
        except Exception:
            raise HTTPException(status_code=400, detail="无法识别文件编码，请使用 UTF-8 或 GBK 编码")

    if len(script_text) > 500000:
        script_text = script_text[:500000]

    system_prompt = """你是专业的剧本分析师。你的任务是从给定的剧本文本中提取结构化信息。
你必须以严格的JSON格式返回分析结果，不要输出任何其他内容。"""

    user_prompt = f"""请分析以下剧本文本，提取所有结构化元素：

{script_text[:50000]}

请以JSON格式返回，包含以下字段：
{{
  "characters": [{{"name": "角色名", "role_type": "protagonist/antagonist/love_interest/mentor/supporting", "core_goal": "核心动机", "core_fear": "核心恐惧", "background": "背景摘要"}}],
  "relations": [{{"char_a": "角色A名", "char_b": "角色B名", "relation_type": "friend/enemy/lover/family/rival", "trust": 0-100, "favor": 0-100}}],
  "scenes": [{{"scene_code": "场景编号", "title": "场景名", "scene_type": "action/dialogue/exploration", "summary": "场景摘要100字", "emotion_level": 0-10, "characters": ["出现的角色名"]}}],
  "foreshadows": [{{"fs_code": "伏笔编号", "name": "伏笔名", "fs_type": "identity_reveal/secret/clue/relationship", "summary": "伏笔摘要", "plant_in_scene": "植入场景编号", "reveal_in_scene": "回收场景编号"}}],
  "key_events": [{{"name": "事件名", "type": "plot_twist/climax/setback", "scene": "关联场景编号"}}]
}}

如果某个元素不存在，返回空数组。"""

    try:
        content = await _parse_with_ai("write.creative", system_prompt, user_prompt, temperature=0.5, max_tokens=4000)
        parsed = await _extract_json(content)
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Upload parse failed: %s", str(e))
        return {"status": "error", "message": f"AI 解析失败: {str(e)}", "raw": script_text[:500]}

    return {"status": "ok", "parsed": parsed, "filename": file.filename}


@router.post("/regenerate/{project_id}", response_model=RegenerateResponse)
async def regenerate_script(
    project_id: uuid.UUID,
    request: RegenerateRequest,
    db: AsyncSession = Depends(get_db),
):
    from models.project import Project
    from models.character import Character
    from models.scene import Scene
    from models.foreshadow import Foreshadow

    project_result = await db.execute(select(Project).where(Project.id == project_id))
    project = project_result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    chars_result = await db.execute(select(Character).where(Character.project_id == project_id))
    chars = chars_result.scalars().all()
    char_map = {str(c.id): c for c in chars}

    scenes_result = await db.execute(select(Scene).where(Scene.project_id == project_id))
    scenes = scenes_result.scalars().all()
    scene_map = {str(s.id): s for s in scenes}

    fs_result = await db.execute(select(Foreshadow).where(Foreshadow.project_id == project_id))
    foreshadows = fs_result.scalars().all()
    fs_map = {str(f.id): f for f in foreshadows}

    edit_context_parts = []
    for edit in request.edits:
        if edit.get("target_type") == "character":
            c = char_map.get(edit.get("target_id", ""))
            if c:
                edit_context_parts.append(
                    f"编辑角色: {c.name}\n修改: {json.dumps(edit.get('changes', {}), ensure_ascii=False)}\n"
                    f"用户指令: {edit.get('instruction', '')}"
                )
        elif edit.get("target_type") == "scene":
            s = scene_map.get(edit.get("target_id", ""))
            if s:
                edit_context_parts.append(
                    f"编辑场景: {s.scene_code}\n修改: {json.dumps(edit.get('changes', {}), ensure_ascii=False)}\n"
                    f"用户指令: {edit.get('instruction', '')}"
                )
        elif edit.get("target_type") == "foreshadow":
            f = fs_map.get(edit.get("target_id", ""))
            if f:
                edit_context_parts.append(
                    f"编辑伏笔: {f.name}\n修改: {json.dumps(edit.get('changes', {}), ensure_ascii=False)}\n"
                    f"用户指令: {edit.get('instruction', '')}"
                )
        elif edit.get("target_type") == "new_scene":
            edit_context_parts.append(
                f"新增场景: {json.dumps(edit.get('changes', {}), ensure_ascii=False)}"
            )
        elif edit.get("target_type") == "new_foreshadow":
            edit_context_parts.append(
                f"新增伏笔: {json.dumps(edit.get('changes', {}), ensure_ascii=False)}"
            )

    edit_context = "\n---\n".join(edit_context_parts) if edit_context_parts else "无具体编辑"

    system_prompt = """你是顶尖的互动影游剧本升级专家。用户对剧本进行了编辑修改，
你需要根据这些修改方向，生成优化后的剧本内容。返回严格的JSON格式。"""

    user_prompt = f"""用户对剧本「{project.name}」进行了以下编辑修改：

{edit_context}

请基于这些修改方向，生成优化版本的剧本内容。
需要包含以下升级内容：

1. 受影响的角色设定更新（如果有角色编辑）
2. 受影响的场景内容更新（如果有场景编辑）
3. 新增场景/伏笔的详细创作（如果有新增）
4. 全局连贯性调整建议

以JSON格式返回：
{{
  "changes_summary": "一句话总结本次升级",
  "updated_characters": [{{"name": "角色名", "updates": {{"field": "新值"}}}}],
  "updated_scenes": [{{"scene_code": "场景编号", "new_content": "更新后的内容"}}],
  "new_elements": [{{"type": "scene/foreshadow", "data": {{"title": "名称", "content": "内容"}}}}],
  "global_suggestions": ["建议1", "建议2"]
}}"""

    try:
        content = await _parse_with_ai("write.creative", system_prompt, user_prompt, temperature=0.75, max_tokens=4000)
        result = await _extract_json(content)
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Regenerate failed: %s", str(e))
        result = {"changes_summary": "AI 升级服务暂不可用", "updated_characters": [], "updated_scenes": [], "new_elements": [], "global_suggestions": []}

    if not isinstance(result, dict):
        result = {"changes_summary": str(result), "updated_characters": [], "updated_scenes": [], "new_elements": [], "global_suggestions": []}

    return RegenerateResponse(
        new_project_id=str(project_id) + "_v2",
        old_project_id=str(project_id),
        changes_summary=result.get("changes_summary", "剧本已根据用户编辑方向完成优化升级"),
        updated_content={
            "updated_characters": result.get("updated_characters", []),
            "updated_scenes": result.get("updated_scenes", []),
            "new_elements": result.get("new_elements", []),
            "global_suggestions": result.get("global_suggestions", []),
        },
    )
