import csv
import io
import json
import uuid
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Body
from fastapi.responses import JSONResponse, PlainTextResponse, StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from database import get_db
from models.project import Project
from models.scene import Scene
from models.character import Character, CharacterRelation
from models.foreshadow import Foreshadow, ForeshadowRelation
from models.chapter import Chapter, ChapterSection
from models.choice import ChoiceDesign
from models.audit import AuditRecord
from services.project_runtime import load_project_runtime

logger = logging.getLogger(__name__)

router = APIRouter()


def _build_chapter_map(chapters):
    return {str(ch.id): ch for ch in chapters}


def _format_emotion_bar(level: int, max_len: int = 10) -> str:
    filled = int(level / 10 * max_len)
    return "█" * filled + "░" * (max_len - filled) + f" [{level}/10]"


def _format_dialogue(dialogue: list) -> str:
    if not dialogue:
        return ""
    lines = []
    for d in dialogue:
        if isinstance(d, dict):
            name = d.get("character_name", "???")
            text = d.get("text", "")
            lines.append(f"**{name}**: {text}")
        else:
            lines.append(str(d))
    return "\n\n".join(lines)


def _format_actions(actions: list) -> str:
    if not actions:
        return ""
    return "\n".join(f"- {a}" for a in actions)


def _format_choices(choices: list) -> str:
    if not choices:
        return ""
    lines = ["**玩家选择:**"]
    for i, c in enumerate(choices, 1):
        if isinstance(c, dict):
            text = c.get("text", c.get("description", str(c)))
            lines.append(f"  {i}. {text}")
        else:
            lines.append(f"  {i}. {c}")
    return "\n".join(lines)


def _safe_json_parse(raw):
    if raw is None:
        return None
    if isinstance(raw, (list, dict)):
        return raw
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return None
    return None


def format_to_markdown(project_data: dict, chapters: list, scenes: list, characters: list) -> str:
    lines = []
    lines.append(f"# {project_data.get('title', '剧本')}")
    lines.append("")
    for ch in sorted(chapters, key=lambda x: x.get('chapter_index', 0)):
        lines.append(f"## 第{ch.get('chapter_index', 0)+1}章 {ch.get('title', '')}")
        lines.append("")
        ch_scenes = [s for s in scenes if s.get('chapter_id') == str(ch.get('id', ''))]
        for sc in sorted(ch_scenes, key=lambda x: x.get('scene_index', 0)):
            content = sc.get('content', {})
            if isinstance(content, str):
                try:
                    content = json.loads(content)
                except Exception:
                    content = {'narration': content}
            narration = content.get('narration', '')
            if narration:
                for para in narration.split('\n'):
                    if para.strip():
                        lines.append(para.strip())
                        lines.append("")
            dialogue = content.get('dialogue', [])
            if isinstance(dialogue, list):
                for d in dialogue:
                    speaker = d.get('speaker', d.get('char', ''))
                    line_text = d.get('line', d.get('text', ''))
                    subtext = d.get('subtext', '')
                    if speaker and line_text:
                        lines.append(f"> **{speaker}**：{line_text}")
                        if subtext:
                            lines.append(f"> *（潜台词：{subtext}）*")
                        lines.append("")
            choices = content.get('choices', [])
            if isinstance(choices, list) and choices:
                lines.append("**互动选择：**")
                for i, c in enumerate(choices, 1):
                    text = c.get('text', c.get('label', ''))
                    lines.append(f"{i}. {text}")
                lines.append("")
    return '\n'.join(lines)


def _build_foreshadow_arcs(foreshadows, characters, scenes, world_config):
    arcs = []
    char_map = {str(c.id): c for c in characters}
    scene_map = {str(s.id): s for s in scenes}

    for f in foreshadows:
        arc = {
            "foreshadow_id": str(f.id),
            "fs_code": f.fs_code,
            "name": f.name,
            "fs_type": f.fs_type,
            "current_status": f.current_status,
            "worldview_refs": _safe_json_parse(f.worldview_refs) or [],
            "character_refs": _safe_json_parse(f.character_refs) or [],
            "worldview_details": [],
            "character_details": [],
            "plant_scene": None,
            "reveal_scene": None,
            "scene_path": [],
        }

        for wref in arc["worldview_refs"]:
            if isinstance(wref, str):
                detail = world_config.get(wref, wref)
                arc["worldview_details"].append({"key": wref, "value": detail})
            elif isinstance(wref, dict):
                arc["worldview_details"].append(wref)

        for cref in arc["character_refs"]:
            if isinstance(cref, str):
                ch = char_map.get(cref)
                arc["character_details"].append({
                    "id": cref,
                    "name": ch.name if ch else cref,
                    "role_type": ch.role_type if ch else None,
                })
            elif isinstance(cref, dict):
                arc["character_details"].append(cref)

        if f.plant_scene_id:
            ps = scene_map.get(str(f.plant_scene_id))
            arc["plant_scene"] = {
                "id": str(f.plant_scene_id),
                "scene_code": ps.scene_code if ps else None,
                "location": ps.location if ps else None,
            }
            arc["scene_path"].append({"role": "plant", "scene_code": ps.scene_code if ps else str(f.plant_scene_id)})

        reinforce_scenes = _safe_json_parse(f.reinforce_scenes) or []
        for rsid in reinforce_scenes:
            rsid_str = str(rsid) if not isinstance(rsid, str) else rsid
            rs = scene_map.get(rsid_str)
            arc["scene_path"].append({"role": "reinforce", "scene_code": rs.scene_code if rs else rsid_str})

        if f.reveal_scene_id:
            rv = scene_map.get(str(f.reveal_scene_id))
            arc["reveal_scene"] = {
                "id": str(f.reveal_scene_id),
                "scene_code": rv.scene_code if rv else None,
                "location": rv.location if rv else None,
            }
            arc["scene_path"].append({"role": "reveal", "scene_code": rv.scene_code if rv else str(f.reveal_scene_id)})

        arcs.append(arc)
    return arcs


@router.post("/projects/{project_id}/export")
async def export_project(
    project_id: uuid.UUID,
    format: str = Body("json"),
    chapter_ids: Optional[list[str]] = Body(None),
    include_audit: bool = Body(False),
    db: AsyncSession = Depends(get_db),
):
    runtime = await load_project_runtime(db, project_id)
    project = runtime.project
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    scenes_query = select(Scene).where(Scene.project_id == project_id)
    if chapter_ids:
        scenes_query = scenes_query.where(Scene.chapter_id.in_([uuid.UUID(cid) for cid in chapter_ids]))
    scenes_query = scenes_query.options(
        selectinload(Scene.chapter),
        selectinload(Scene.versions),
    ).order_by(Scene.scene_code)

    scenes_result = await db.execute(scenes_query)
    scenes = scenes_result.scalars().all()

    chars_result = await db.execute(
        select(Character).where(Character.project_id == project_id).order_by(Character.char_code)
    )
    characters = chars_result.scalars().all()

    rel_result = await db.execute(
        select(CharacterRelation)
        .where(CharacterRelation.project_id == project_id)
        .options(selectinload(CharacterRelation.char_a), selectinload(CharacterRelation.char_b))
    )
    relations = rel_result.scalars().all()

    fs_result = await db.execute(
        select(Foreshadow).where(Foreshadow.project_id == project_id).order_by(Foreshadow.fs_code)
    )
    foreshadows = fs_result.scalars().all()

    fs_rel_result = await db.execute(
        select(ForeshadowRelation)
        .where(ForeshadowRelation.project_id == project_id)
        .options(selectinload(ForeshadowRelation.from_fs), selectinload(ForeshadowRelation.to_fs))
    )
    foreshadow_relations = fs_rel_result.scalars().all()

    chapters_result = await db.execute(
        select(Chapter).where(Chapter.project_id == project_id).order_by(Chapter.chapter_number)
    )
    chapters = chapters_result.scalars().all()

    sections_result = await db.execute(
        select(ChapterSection)
        .where(ChapterSection.project_id == project_id)
        .order_by(ChapterSection.chapter_id, ChapterSection.section_number)
    )
    sections = sections_result.scalars().all()

    choices_result = await db.execute(
        select(ChoiceDesign).where(ChoiceDesign.project_id == project_id).order_by(ChoiceDesign.section_id, ChoiceDesign.choice_number)
    )
    choice_designs = choices_result.scalars().all()

    chapter_map = _build_chapter_map(chapters)

    audit_data = None
    if include_audit:
        audit_result = await db.execute(
            select(AuditRecord)
            .where(AuditRecord.project_id == project_id)
            .order_by(AuditRecord.created_at.desc())
        )
        audit_data = []
        for rec in audit_result.scalars().all():
            audit_data.append({
                "id": str(rec.id),
                "scene_id": str(rec.scene_id) if rec.scene_id else None,
                "audit_type": rec.audit_type,
                "overall_result": rec.overall_result,
                "issues": rec.issues,
                "suggestions": rec.suggestions,
                "created_at": rec.created_at.isoformat() if rec.created_at else None,
            })

    if format == "json":
        return await _export_json_streaming(project, runtime, chapters, sections, choice_designs, scenes, characters, foreshadows, foreshadow_relations, relations, audit_data, chapter_map)

    if format in ("markdown", "txt"):
        return await _export_readable_streaming(project, runtime, chapters, scenes, characters, format)

    if format == "excel":
        return _export_csv(scenes, characters, foreshadows, chapter_map)

    raise HTTPException(status_code=400, detail=f"不支持的导出格式: {format}，支持: json, markdown, text, excel")


async def _export_json_streaming(project, runtime, chapters, sections, choice_designs, scenes, characters, foreshadows, foreshadow_relations, relations, audit_data, chapter_map):
    async def generate():
        world_config = runtime.config.custom_checker_rules.get("world_settings", {}) if runtime.config and runtime.config.custom_checker_rules else {}

        section_map_by_chapter = {}
        for sec in sections:
            cid = str(sec.chapter_id)
            section_map_by_chapter.setdefault(cid, []).append(sec)

        choice_map_by_section = {}
        for cd in choice_designs:
            sid = str(cd.section_id)
            choice_map_by_section.setdefault(sid, []).append(cd)

        scene_map = {str(s.id): s for s in scenes}
        char_map = {str(c.id): c for c in characters}

        all_choices = []
        all_branches = []
        all_consequences = []
        all_foreshadow_ops = []
        all_character_state_changes = []
        all_causal_chains = []

        for ch in chapters:
            ch_sections = section_map_by_chapter.get(str(ch.id), [])
            for sec in ch_sections:
                sec_choices = choice_map_by_section.get(str(sec.id), [])
                for cd in sec_choices:
                    choice_entry = {
                        "id": str(cd.id),
                        "section_id": str(cd.section_id),
                        "choice_number": cd.choice_number,
                        "text": cd.text,
                        "consequence_chain": {
                            "direct": cd.consequence_direct,
                            "indirect": cd.consequence_indirect,
                            "long_term": cd.consequence_long_term,
                        },
                        "moral_alignment": cd.moral_alignment,
                        "is_hidden": cd.is_hidden,
                        "hidden_condition": cd.hidden_condition if cd.is_hidden else None,
                        "branch_target": cd.branch_target,
                        "character_impact": _safe_json_parse(cd.character_impact) or [],
                    }
                    all_choices.append(choice_entry)

                    if cd.branch_target:
                        all_branches.append({
                            "source_section_id": str(cd.section_id),
                            "choice_id": str(cd.id),
                            "choice_text": cd.text,
                            "branch_target": cd.branch_target,
                        })

                    if cd.consequence_direct or cd.consequence_indirect or cd.consequence_long_term:
                        all_consequences.append({
                            "choice_id": str(cd.id),
                            "choice_text": cd.text,
                            "direct": cd.consequence_direct,
                            "indirect": cd.consequence_indirect,
                            "long_term": cd.consequence_long_term,
                        })

                    if cd.character_impact:
                        impacts = _safe_json_parse(cd.character_impact) or []
                        for imp in impacts:
                            char_id = imp.get("character_id", imp.get("char_id", "")) if isinstance(imp, dict) else ""
                            char_name = ""
                            if char_id:
                                ch_obj = char_map.get(str(char_id))
                                char_name = ch_obj.name if ch_obj else char_id
                            all_character_state_changes.append({
                                "choice_id": str(cd.id),
                                "choice_text": cd.text,
                                "character_id": str(char_id),
                                "character_name": char_name,
                                "impact": imp,
                            })

        for s in scenes:
            fs_ops = _safe_json_parse(s.foreshadow_ops) or []
            for op in fs_ops:
                if isinstance(op, dict):
                    fs_id = op.get("fs_id", op.get("foreshadow_id", ""))
                    fs_obj = None
                    for f in foreshadows:
                        if str(f.id) == fs_id:
                            fs_obj = f
                            break
                    all_foreshadow_ops.append({
                        "scene_id": str(s.id),
                        "scene_code": s.scene_code,
                        "op_type": op.get("op_type", op.get("op", "plant")),
                        "foreshadow_id": fs_id,
                        "foreshadow_name": fs_obj.name if fs_obj else op.get("fs_name", ""),
                        "foreshadow_code": fs_obj.fs_code if fs_obj else op.get("fs_code", ""),
                        "description": op.get("description", op.get("content", "")),
                        "worldview_refs": _safe_json_parse(fs_obj.worldview_refs) if fs_obj else [],
                        "character_refs": _safe_json_parse(fs_obj.character_refs) if fs_obj else [],
                    })

            causal = _safe_json_parse(s.causal_chain)
            if causal and isinstance(causal, dict):
                has_content = any(causal.get(k) for k in ("precondition", "catalyst", "direct_result", "indirect_result", "long_term_result"))
                if has_content:
                    all_causal_chains.append({
                        "scene_id": str(s.id),
                        "scene_code": s.scene_code,
                        **causal,
                    })

        foreshadow_arcs = _build_foreshadow_arcs(foreshadows, characters, scenes, world_config)

        data = {
            "project": {
                "id": str(project.id),
                "name": project.name,
                "description": project.description,
                "genre": runtime.genre,
                "style": runtime.style,
                "target_word_count": runtime.target_word_count,
                "status": project.status,
                "current_phase": runtime.current_phase,
            },
            "world_settings": world_config,
            "characters": [
                {
                    "id": str(c.id),
                    "char_code": c.char_code,
                    "name": c.name,
                    "role_type": c.role_type,
                    "core_goal": c.core_goal,
                    "core_fear": c.core_fear,
                    "background": c.background,
                    "surface_image": c.surface_image,
                    "true_self": c.true_self,
                    "language_style": c.language_style,
                    "catchphrase": c.catchphrase,
                    "arc_description": c.arc_description,
                    "dark_secret": c.dark_secret,
                    "behavior_inevitable": _safe_json_parse(c.behavior_inevitable) or [],
                    "behavior_never": _safe_json_parse(c.behavior_never) or [],
                    "behavior_conditional": _safe_json_parse(c.behavior_conditional) or [],
                }
                for c in characters
            ],
            "relations": [
                {
                    "id": str(r.id),
                    "char_a": r.char_a.name if r.char_a else None,
                    "char_b": r.char_b.name if r.char_b else None,
                    "relation_type": r.relation_type,
                    "trust": r.trust,
                    "favor": r.favor,
                    "is_hidden": r.is_hidden,
                    "arc_direction": r.arc_direction,
                }
                for r in relations
            ],
            "foreshadows": [
                {
                    "id": str(f.id),
                    "fs_code": f.fs_code,
                    "name": f.name,
                    "fs_type": f.fs_type,
                    "foreshadow_tier": f.foreshadow_tier,
                    "current_status": f.current_status,
                    "health": f.health,
                    "surface_layer": f.surface_layer,
                    "deep_layer": f.deep_layer,
                    "truth_layer": f.truth_layer,
                    "plant_scene_id": str(f.plant_scene_id) if f.plant_scene_id else None,
                    "reinforce_scenes": _safe_json_parse(f.reinforce_scenes) or [],
                    "reveal_scene_id": str(f.reveal_scene_id) if f.reveal_scene_id else None,
                    "worldview_refs": _safe_json_parse(f.worldview_refs) or [],
                    "character_refs": _safe_json_parse(f.character_refs) or [],
                    "foreshadow_links": _safe_json_parse(f.foreshadow_links) or [],
                    "depends_on": _safe_json_parse(f.depends_on) or [],
                    "enables": _safe_json_parse(f.enables) or [],
                    "wow_factor": f.wow_factor,
                    "player_reaction": f.player_reaction,
                }
                for f in foreshadows
            ],
            "foreshadow_relations": [
                {
                    "id": str(fr.id),
                    "from_fs_id": str(fr.from_fs_id),
                    "from_fs_name": fr.from_fs.name if fr.from_fs else None,
                    "to_fs_id": str(fr.to_fs_id),
                    "to_fs_name": fr.to_fs.name if fr.to_fs else None,
                    "relation_type": fr.relation_type,
                }
                for fr in foreshadow_relations
            ],
            "foreshadow_arcs": foreshadow_arcs,
            "chapters": [
                {
                    "id": str(ch.id),
                    "chapter_number": ch.chapter_number,
                    "title": ch.title,
                    "summary": ch.summary,
                    "outline": ch.outline,
                    "core_conflict": ch.core_conflict,
                    "emotion_target": ch.emotion_target,
                    "key_turning_points": _safe_json_parse(ch.key_turning_points) or [],
                    "foreshadow_tasks": _safe_json_parse(ch.foreshadow_tasks) or [],
                    "branch_structure": ch.branch_structure,
                    "anchor_scenes": _safe_json_parse(ch.anchor_scenes) or [],
                    "focus_characters": _safe_json_parse(ch.focus_characters) or [],
                    "worldview_refs": _safe_json_parse(ch.worldview_refs) or [],
                    "status": ch.status,
                    "sections": [
                        {
                            "id": str(sec.id),
                            "section_number": sec.section_number,
                            "title": sec.title,
                            "word_target": sec.word_target,
                            "emotion_target": sec.emotion_target,
                            "scene_ids": _safe_json_parse(sec.scene_ids) or [],
                            "branch_type": sec.branch_type,
                            "foreshadow_tasks": _safe_json_parse(sec.foreshadow_tasks) or [],
                            "focus_characters": _safe_json_parse(sec.focus_characters) or [],
                            "summary": sec.summary,
                            "status": sec.status,
                            "choices": [
                                {
                                    "id": str(cd.id),
                                    "choice_number": cd.choice_number,
                                    "text": cd.text,
                                    "consequence_chain": {
                                        "direct": cd.consequence_direct,
                                        "indirect": cd.consequence_indirect,
                                        "long_term": cd.consequence_long_term,
                                    },
                                    "moral_alignment": cd.moral_alignment,
                                    "is_hidden": cd.is_hidden,
                                    "hidden_condition": cd.hidden_condition if cd.is_hidden else None,
                                    "branch_target": cd.branch_target,
                                    "character_impact": _safe_json_parse(cd.character_impact) or [],
                                }
                                for cd in choice_map_by_section.get(str(sec.id), [])
                            ],
                        }
                        for sec in section_map_by_chapter.get(str(ch.id), [])
                    ],
                    "scenes": [
                        {
                            "id": str(s.id),
                            "scene_code": s.scene_code,
                            "scene_type": s.scene_type,
                            "location": s.location,
                            "weather": s.weather,
                            "emotion_level": s.emotion_level,
                            "narration": s.narration,
                            "dialogue": s.dialogue,
                            "actions": s.actions,
                            "choices": s.choices,
                            "foreshadow_ops": s.foreshadow_ops,
                            "causal_chain": s.causal_chain,
                            "is_wow_moment": s.is_wow_moment,
                            "wow_type": s.wow_type,
                            "wow_spec": s.wow_spec,
                            "characters_involved": s.characters_involved,
                            "status": s.status,
                        }
                        for s in scenes if str(s.chapter_id) == str(ch.id)
                    ],
                }
                for ch in chapters
            ],
            "interactive_data": {
                "choices": all_choices,
                "branches": all_branches,
                "consequences": all_consequences,
                "foreshadow_ops": all_foreshadow_ops,
                "character_state_changes": all_character_state_changes,
                "causal_chains": all_causal_chains,
            },
        }
        if audit_data is not None:
            data["audit_records"] = audit_data

        yield json.dumps(data, ensure_ascii=False, indent=2)

    return StreamingResponse(generate(), media_type="application/json")


async def _export_readable_streaming(project, runtime, chapters, scenes, characters, export_format):
    async def generate():
        project_data = {
            "title": project.name,
            "description": project.description,
        }
        chapters_data = []
        for ch in chapters:
            ch_dict = {
                "id": str(ch.id),
                "chapter_index": getattr(ch, 'chapter_number', 0) or 0,
                "title": ch.title,
            }
            chapters_data.append(ch_dict)

        scenes_data = []
        for s in scenes:
            sc_dict = {
                "id": str(s.id),
                "chapter_id": str(s.chapter_id) if s.chapter_id else "",
                "scene_index": s.scene_code if hasattr(s, 'scene_code') else 0,
                "content": {
                    "narration": s.narration or "",
                    "dialogue": s.dialogue or [],
                    "choices": s.choices or [],
                },
            }
            scenes_data.append(sc_dict)

        characters_data = []
        for c in characters:
            characters_data.append({
                "id": str(c.id),
                "name": c.name,
            })

        markdown_content = format_to_markdown(project_data, chapters_data, scenes_data, characters_data)
        yield markdown_content

    media_type = "text/markdown" if export_format == "markdown" else "text/plain"
    return StreamingResponse(generate(), media_type=media_type)


def _export_csv(scenes, characters, foreshadows, chapter_map):
    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow(["=== 场景列表 ==="])
    writer.writerow(["scene_code", "chapter", "type", "location", "emotion", "word_count", "status"])
    for s in scenes:
        chapter_title = ""
        if s.chapter_id:
            ch = chapter_map.get(str(s.chapter_id))
            if ch:
                chapter_title = ch.title or f"第{ch.chapter_number}章"
        word_count = len(s.narration) if s.narration else 0
        writer.writerow([
            s.scene_code,
            chapter_title,
            s.scene_type or "",
            s.location or "",
            s.emotion_level or 5,
            word_count,
            s.status,
        ])

    writer.writerow([])
    writer.writerow(["=== 角色列表 ==="])
    writer.writerow(["name", "role_type", "core_goal", "core_fear"])
    for c in characters:
        writer.writerow([
            c.name,
            c.role_type or "",
            c.core_goal or "",
            c.core_fear or "",
        ])

    writer.writerow([])
    writer.writerow(["=== 伏笔列表 ==="])
    writer.writerow(["fs_code", "name", "type", "current_status", "health"])
    for f in foreshadows:
        writer.writerow([
            f.fs_code,
            f.name,
            f.fs_type,
            f.current_status or "",
            f.health or "normal",
        ])

    return PlainTextResponse(content=output.getvalue(), media_type="text/csv")
