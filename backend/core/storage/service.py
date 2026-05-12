"""
统一存储服务: 封装 Layer 0-5 的所有读写操作。
Agent 不直接操作数据库，全部通过 StorageService。
"""

import json
import uuid
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from config import DATABASE_URL

_IS_SQLITE = DATABASE_URL.startswith("sqlite")


def _now_expr() -> str:
    return "datetime('now')" if _IS_SQLITE else "NOW()"


def _in_placeholder(param_name: str, values: list) -> tuple[str, dict]:
    names = []
    params = {}
    for i, v in enumerate(values):
        k = f"{param_name}_{i}"
        names.append(f":{k}")
        params[k] = v
    return ", ".join(names), params


class StorageService:
    """统一存储服务"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_layer0(self, project_id: str) -> dict:
        result = await self.db.execute(
            text("SELECT * FROM project_configs WHERE project_id = :project_id"),
            {"project_id": project_id},
        )
        row = result.fetchone()
        if not row:
            return {}
        cols = result.keys()
        d = dict(zip(cols, row))
        out = {}
        skip = {"id", "project_id", "created_at", "updated_at"}
        for k, v in d.items():
            if k in skip:
                continue
            out[k] = {"value": v, "locked": False}
        return out

    async def get_layer0_subset(self, project_id: str,
                                 keys: list[str]) -> dict:
        result = await self.db.execute(
            text("SELECT * FROM project_configs WHERE project_id = :project_id"),
            {"project_id": project_id},
        )
        row = result.fetchone()
        if not row:
            return {}
        cols = result.keys()
        d = dict(zip(cols, row))
        out = {}
        for k in keys:
            if k in d:
                out[k] = d[k]
        return out

    async def update_layer0(self, project_id: str, key: str, value: str):
        set_clause = f"{key} = :value, updated_at = {_now_expr()}"
        await self.db.execute(
            text(
                f"UPDATE project_configs SET {set_clause} WHERE project_id = :project_id"
            ),
            {"project_id": project_id, "value": value},
        )
        await self.db.commit()

    async def lock_layer0(self, project_id: str, key: str):
        pass

    async def get_character_states(self, project_id: str,
                                    character_ids: list[str] | None = None) -> list[dict]:
        if character_ids:
            placeholders, params = _in_placeholder("cid", character_ids)
            params["project_id"] = project_id
            result = await self.db.execute(
                text(f"SELECT * FROM characters WHERE project_id = :project_id AND id IN ({placeholders})"),
                params,
            )
        else:
            result = await self.db.execute(
                text("SELECT * FROM characters WHERE project_id = :project_id"),
                {"project_id": project_id},
            )
        rows = result.fetchall()
        cols = result.keys()
        return [dict(zip(cols, row)) for row in rows]

    async def get_foreshadow_states(self, project_id: str,
                                     statuses: list[str] | None = None) -> list[dict]:
        if statuses:
            placeholders, params = _in_placeholder("st", statuses)
            params["project_id"] = project_id
            result = await self.db.execute(
                text(f"SELECT * FROM foreshadows WHERE project_id = :project_id AND current_status IN ({placeholders})"),
                params,
            )
        else:
            result = await self.db.execute(
                text("SELECT * FROM foreshadows WHERE project_id = :project_id"),
                {"project_id": project_id},
            )
        rows = result.fetchall()
        cols = result.keys()
        return [dict(zip(cols, row)) for row in rows]

    async def get_foreshadow(self, project_id: str, foreshadow_id: str) -> Optional[dict]:
        result = await self.db.execute(
            text("SELECT * FROM foreshadows WHERE id = :fs_id AND project_id = :project_id"),
            {"fs_id": foreshadow_id, "project_id": project_id},
        )
        row = result.fetchone()
        if not row:
            return None
        cols = result.keys()
        return dict(zip(cols, row))

    async def get_foreshadows(self, project_id: str) -> list[dict]:
        return await self.get_foreshadow_states(project_id)

    async def get_relation(self, project_id: str, char_a: str, char_b: str) -> Optional[dict]:
        result = await self.db.execute(
            text(
                "SELECT * FROM character_relations WHERE project_id = :project_id "
                "AND ((char_a_id = :a AND char_b_id = :b) OR (char_a_id = :b AND char_b_id = :a))"
            ),
            {"project_id": project_id, "a": char_a, "b": char_b},
        )
        row = result.fetchone()
        if not row:
            return None
        cols = result.keys()
        return dict(zip(cols, row))

    async def get_relations(self, project_id: str) -> list[dict]:
        result = await self.db.execute(
            text("SELECT * FROM character_relations WHERE project_id = :project_id"),
            {"project_id": project_id},
        )
        rows = result.fetchall()
        cols = result.keys()
        return [dict(zip(cols, row)) for row in rows]

    async def update_character_state(self, character_id: str, updates: dict):
        _ALLOWED_CHAR_COLS = {
            "location", "emotional_state", "physical_state", "current_goal",
            "known_info", "status", "role_type", "background", "core_goal",
            "core_fear", "surface_image", "true_self", "language_style",
            "catchphrase", "dark_secret", "arc_description",
        }
        safe_updates = {k: v for k, v in updates.items() if k in _ALLOWED_CHAR_COLS}
        if not safe_updates:
            return
        serialized = {}
        for k, v in safe_updates.items():
            serialized[k] = json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v
        set_clauses = [f"{key} = :{key}" for key in serialized]
        params = {"character_id": character_id, **serialized}
        await self.db.execute(
            text(f"UPDATE characters SET {', '.join(set_clauses)} WHERE id = :character_id"),
            params,
        )
        await self.db.commit()

    async def update_foreshadow_state(self, foreshadow_id: str, updates: dict):
        _ALLOWED_FS_COLS = {
            "current_status", "reinforce_count", "reinforce_scenes",
            "plant_scene_id", "reveal_scene_id", "health", "wow_plans",
            "wow_selected", "foreshadow_tier", "worldview_refs",
            "character_refs", "foreshadow_links", "reclaim_status",
            "plant_location", "reinforce_locations", "reveal_location",
        }
        safe_updates = {k: v for k, v in updates.items() if k in _ALLOWED_FS_COLS}
        if not safe_updates:
            return
        serialized = {}
        for k, v in safe_updates.items():
            serialized[k] = json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v
        set_clauses = [f"{key} = :{key}" for key in serialized]
        params = {"foreshadow_id": foreshadow_id, **serialized}
        await self.db.execute(
            text(f"UPDATE foreshadows SET {', '.join(set_clauses)} WHERE id = :foreshadow_id"),
            params,
        )
        await self.db.commit()

    async def update_relation(self, project_id: str, char_a: str, char_b: str,
                               updates: dict):
        _ALLOWED_REL_COLS = {
            "trust", "favor", "value", "last_interaction",
            "info_known_a_about_b", "info_known_b_about_a",
            "info_asymmetry", "is_hidden", "arc_direction", "arc_milestones",
        }
        safe_updates = {k: v for k, v in updates.items() if k in _ALLOWED_REL_COLS}
        if not safe_updates:
            return
        serialized = {}
        for k, v in safe_updates.items():
            serialized[k] = json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v
        set_clauses = [f"{key} = :{key}" for key in serialized]
        params = {
            "project_id": project_id,
            "char_a": char_a,
            "char_b": char_b,
            **serialized,
        }
        now = _now_expr()
        await self.db.execute(
            text(
                f"""UPDATE character_relations
                    SET {', '.join(set_clauses)}, updated_at = {now}
                    WHERE project_id = :project_id AND char_a_id = :char_a AND char_b_id = :char_b"""
            ),
            params,
        )
        await self.db.commit()

    async def get_scene(self, project_id: str, scene_id: str) -> Optional[dict]:
        result = await self.db.execute(
            text("SELECT * FROM scenes WHERE project_id = :project_id AND id = :scene_id"),
            {"project_id": project_id, "scene_id": scene_id},
        )
        row = result.fetchone()
        if row:
            return dict(zip(result.keys(), row))

    async def create_relations_bulk(self, project_id: str, relations: list[dict]):
        now = _now_expr()
        characters = await self.get_character_states(project_id)
        character_lookup: dict[str, str] = {}
        character_lookup_lower: dict[str, str] = {}
        character_names: list[str] = []
        for character in characters:
            character_id = str(character.get("id", ""))
            name = str(character.get("name", "")).strip()
            char_code = str(character.get("char_code", "")).strip()
            for key in (character_id, name, char_code):
                if key:
                    character_lookup[key] = character_id
            for key in (character_id, name, char_code):
                if key:
                    character_lookup_lower[key.lower()] = character_id
            if name:
                character_names.append(name)

        async def _resolve_or_create_char(raw):
            if raw is None:
                return None
            key = str(raw).strip()
            if not key:
                return None
            # 1. 精确匹配
            if key in character_lookup:
                return character_lookup[key]
            lower_key = key.lower()
            if lower_key in character_lookup_lower:
                return character_lookup_lower[lower_key]
            # 2. 子串匹配：查找包含key的角色名
            for k, cid in character_lookup.items():
                if k and lower_key in k.lower():
                    return cid
            # 3. 反向子串匹配：key是否包含某个角色名（处理带空格或额外文本的情况）
            for k, cid in character_lookup_lower.items():
                if k and k in lower_key:
                    return cid
            # 4. 空格规范化匹配：移除空格后比较
            normalized_key = key.replace(" ", "").replace("\u3000", "").lower()
            if normalized_key:
                for k, cid in character_lookup.items():
                    normalized_k = k.replace(" ", "").replace("\u3000", "").lower()
                    if normalized_key == normalized_k:
                        return cid
            # 自动创建缺失的角色占位记录
            new_id = str(uuid.uuid4())
            new_code = f"C{len(character_names) + 1:03d}"
            await self.db.execute(
                text(
                    f"INSERT INTO characters (id, project_id, char_code, name, role_type, "
                    f"background, core_goal, core_fear, surface_image, true_self, "
                    f"language_style, catchphrase, arc_description, behavior_inevitable, "
                    f"behavior_never, behavior_conditional, status, created_at) "
                    f"VALUES (:id, :pid, :code, :name, 'unknown', '', '', '', '', '', "
                    f"'', '', '[]', '[]', '[]', 'auto_created', {now})"
                ),
                {"id": new_id, "pid": project_id, "code": new_code, "name": key},
            )
            character_lookup[key] = new_id
            character_lookup_lower[lower_key] = new_id
            character_names.append(key)
            return new_id

        for idx, rel in enumerate(relations):
            raw_char_a = (
                rel.get("char_a_id")
                or rel.get("char_a_name")
                or rel.get("char_a")
                or rel.get("a")
            )
            raw_char_b = (
                rel.get("char_b_id")
                or rel.get("char_b_name")
                or rel.get("char_b")
                or rel.get("b")
            )
            char_a_id = await _resolve_or_create_char(raw_char_a)
            char_b_id = await _resolve_or_create_char(raw_char_b)
            if not char_a_id or not char_b_id:
                raise ValueError(
                    f"关系网络存在无法解析的角色: {raw_char_a} -> {raw_char_b}"
                )

            rel_id = str(uuid.uuid4())
            await self.db.execute(
                text(
                    f"INSERT INTO character_relations (id, project_id, char_a_id, char_b_id, "
                    f"relation_type, trust, favor, info_known_a_about_b, info_known_b_about_a, "
                    f"info_asymmetry, is_hidden, arc_direction, arc_milestones, updated_at) "
                    f"VALUES (:id, :pid, :char_a_id, :char_b_id, :rtype, :trust, :favor, :info_a, :info_b, "
                    f"'{{}}', 0, 'stable', '[]', {now})"
                ),
                {
                    "id": rel_id, "pid": project_id,
                    "char_a_id": char_a_id,
                    "char_b_id": char_b_id,
                    "rtype": rel.get("relation_type", ""),
                    "trust": rel.get("trust", 50),
                    "favor": rel.get("favor", 50),
                    "info_a": json.dumps(rel.get("info_known_a_about_b", []), ensure_ascii=False),
                    "info_b": json.dumps(rel.get("info_known_b_about_a", []), ensure_ascii=False),
                },
            )
        await self.db.commit()

    async def get_scene_dependency_graph(self, project_id: str) -> dict:
        scenes = await self.db.execute(
            text("SELECT id, scene_code, chapter_id, characters_involved, foreshadow_ops, choices FROM scenes WHERE project_id = :pid ORDER BY scene_code"),
            {"pid": project_id},
        )
        rows = scenes.fetchall()

        graph = {"nodes": [], "edges": []}
        char_scene_map: dict[str, list[str]] = {}
        fs_scene_map: dict[str, list[str]] = {}

        for row in rows:
            sid, code, ch_id, chars_inv, fs_ops, choices = row
            graph["nodes"].append({"id": str(sid), "scene_code": code, "chapter_id": str(ch_id) if ch_id else None})

            if chars_inv:
                try:
                    chars_list = json.loads(chars_inv) if isinstance(chars_inv, str) else chars_inv
                    for c in (chars_list if isinstance(chars_list, list) else []):
                        c_name = str(c) if isinstance(c, str) else (c.get("name", str(c)) if isinstance(c, dict) else str(c))
                        if c_name not in char_scene_map:
                            char_scene_map[c_name] = []
                        char_scene_map[c_name].append(str(sid))
                except (json.JSONDecodeError, TypeError):
                    pass

            if fs_ops:
                try:
                    fs_list = json.loads(fs_ops) if isinstance(fs_ops, str) else fs_ops
                    for f in (fs_list if isinstance(fs_list, list) else []):
                        fs_id = f.get("fs_id", f.get("fs_name", "")) if isinstance(f, dict) else str(f)
                        if fs_id not in fs_scene_map:
                            fs_scene_map[fs_id] = []
                        fs_scene_map[fs_id].append(str(sid))
                except (json.JSONDecodeError, TypeError):
                    pass

        for c_name, sids in char_scene_map.items():
            for i in range(len(sids) - 1):
                graph["edges"].append({"from": sids[i], "to": sids[i + 1], "type": "character", "label": c_name})

        for fs_id, sids in fs_scene_map.items():
            for i in range(len(sids) - 1):
                graph["edges"].append({"from": sids[i], "to": sids[i + 1], "type": "foreshadow", "label": fs_id})

        return graph

    async def get_affected_scenes(self, project_id: str, entity_type: str, entity_id: str) -> list[str]:
        graph = await self.get_scene_dependency_graph(project_id)
        affected = set()
        for edge in graph["edges"]:
            if edge.get("type") == entity_type and edge.get("label") == entity_id:
                affected.add(edge["from"])
                affected.add(edge["to"])
        return list(affected)

    async def get_prev_scenes(self, scene_id: str, count: int = 2) -> list[dict]:
        scene_result = await self.db.execute(
            text("SELECT chapter_id, scene_code FROM scenes WHERE id = :scene_id"),
            {"scene_id": scene_id},
        )
        scene = scene_result.fetchone()
        if not scene:
            return []
        chapter_id, scene_code = scene

        result = await self.db.execute(
            text(
                """
                SELECT * FROM scenes
                WHERE chapter_id = :chapter_id AND scene_code < :scene_code
                ORDER BY scene_code DESC
                LIMIT :count
                """
            ),
            {"chapter_id": chapter_id, "scene_code": scene_code, "count": count},
        )
        rows = result.fetchall()
        cols = result.keys()
        return [dict(zip(cols, row)) for row in rows]

    async def save_scene_draft(self, scene_id: str, content: dict):
        now = _now_expr()
        await self.db.execute(
            text(
                f"""
                UPDATE scenes SET
                    narration = :narration, dialogue = :dialogue, actions = :actions,
                    foreshadow_ops = :foreshadow_ops, choices = :choices, causal_chain = :causal_chain,
                    status = 'draft', updated_at = {now}
                WHERE id = :scene_id
                """
            ),
            {
                "scene_id": scene_id,
                "narration": content.get("narration"),
                "dialogue": json.dumps(content.get("dialogue", []), ensure_ascii=False),
                "actions": json.dumps(content.get("actions", []), ensure_ascii=False),
                "foreshadow_ops": json.dumps(content.get("foreshadow_ops", []), ensure_ascii=False),
                "choices": json.dumps(content.get("choices", []), ensure_ascii=False),
                "causal_chain": json.dumps(content.get("causal_chain", {}), ensure_ascii=False),
            },
        )
        await self.db.commit()

    async def get_chapter_outlines(self, project_id: str) -> list[dict]:
        result = await self.db.execute(
            text("SELECT * FROM chapters WHERE project_id = :project_id ORDER BY chapter_number"),
            {"project_id": project_id},
        )
        rows = result.fetchall()
        cols = result.keys()
        return [dict(zip(cols, row)) for row in rows]

    async def get_chapter_context(self, project_id: str, chapter_id: str) -> dict:
        ch_result = await self.db.execute(
            text("SELECT * FROM chapters WHERE id = :chapter_id"),
            {"chapter_id": chapter_id},
        )
        chapter_row = ch_result.fetchone()
        chapter = dict(zip(ch_result.keys(), chapter_row)) if chapter_row else None

        sc_result = await self.db.execute(
            text("SELECT * FROM scenes WHERE chapter_id = :chapter_id ORDER BY scene_code"),
            {"chapter_id": chapter_id},
        )
        sc_rows = sc_result.fetchall()
        sc_cols = sc_result.keys()
        scenes = [dict(zip(sc_cols, row)) for row in sc_rows]

        return {"chapter": chapter, "scenes": scenes}

    async def get_scene_summaries(self, project_id: str,
                                   scene_ids: list[str] | None = None) -> list[dict]:
        if scene_ids:
            placeholders, params = _in_placeholder("sid", scene_ids)
            params["project_id"] = project_id
            result = await self.db.execute(
                text(
                    f"SELECT id, scene_code, narration FROM scenes WHERE project_id = :project_id AND id IN ({placeholders})"
                ),
                params,
            )
        else:
            result = await self.db.execute(
                text("SELECT id, scene_code, narration FROM scenes WHERE project_id = :project_id"),
                {"project_id": project_id},
            )
        rows = result.fetchall()
        cols = result.keys()
        return [dict(zip(cols, row)) for row in rows]

    async def get_elements(self, project_id: str,
                           element_type: str | None = None) -> list[dict]:
        if element_type:
            result = await self.db.execute(
                text(
                    "SELECT * FROM elements WHERE project_id = :project_id AND element_type = :element_type"
                ),
                {"project_id": project_id, "element_type": element_type},
            )
        else:
            result = await self.db.execute(
                text("SELECT * FROM elements WHERE project_id = :project_id"),
                {"project_id": project_id},
            )
        rows = result.fetchall()
        cols = result.keys()
        return [dict(zip(cols, row)) for row in rows]

    async def register_element(self, project_id: str, element: dict):
        existing = await self.db.execute(
            text(
                "SELECT id FROM elements WHERE project_id = :project_id AND element_code = :element_code"
            ),
            {"project_id": project_id, "element_code": element["code"]},
        )
        if existing.fetchone():
            return
        await self.db.execute(
            text(
                """
                INSERT INTO elements (id, project_id, element_type, element_code, name, description)
                VALUES (:id, :project_id, :element_type, :element_code, :name, :description)
                """
            ),
            {
                "id": str(uuid.uuid4()),
                "project_id": project_id,
                "element_type": element["type"],
                "element_code": element["code"],
                "name": element["name"],
                "description": element.get("description"),
            },
        )
        await self.db.commit()

    async def get_project_config(self, project_id: str) -> Optional[dict]:
        result = await self.db.execute(
            text("SELECT * FROM project_configs WHERE project_id = :project_id"),
            {"project_id": project_id},
        )
        row = result.fetchone()
        if row:
            return dict(zip(result.keys(), row))
        return None

    async def get_project_word_count(self, project_id: str) -> int:
        result = await self.db.execute(
            text(
                "SELECT COALESCE(SUM(LENGTH(COALESCE(narration, ''))), 0) FROM scenes WHERE project_id = :project_id"
            ),
            {"project_id": project_id},
        )
        row = result.fetchone()
        return row[0] if row else 0

    async def get_all_scenes_ordered(self, project_id: str) -> list[dict]:
        result = await self.db.execute(
            text(
                "SELECT * FROM scenes WHERE project_id = :project_id ORDER BY scene_code"
            ),
            {"project_id": project_id},
        )
        rows = result.fetchall()
        cols = result.keys()
        return [dict(zip(cols, row)) for row in rows]

    async def get_scenes_by_chapter(self, project_id: str, chapter_id: str) -> list[dict]:
        result = await self.db.execute(
            text(
                "SELECT * FROM scenes WHERE project_id = :project_id AND chapter_id = :chapter_id ORDER BY scene_code"
            ),
            {"project_id": project_id, "chapter_id": chapter_id},
        )
        rows = result.fetchall()
        cols = result.keys()
        return [dict(zip(cols, row)) for row in rows]

    async def get_foreshadow_groups(self, project_id: str) -> dict:
        result = await self.db.execute(
            text(
                "SELECT current_status, COUNT(*) as cnt FROM foreshadows WHERE project_id = :project_id GROUP BY current_status"
            ),
            {"project_id": project_id},
        )
        rows = result.fetchall()
        return {row[0]: row[1] for row in rows}

    async def get_foreshadow_relations(self, project_id: str) -> list[dict]:
        result = await self.db.execute(
            text("SELECT * FROM foreshadow_relations WHERE project_id = :project_id"),
            {"project_id": project_id},
        )
        rows = result.fetchall()
        cols = result.keys()
        return [dict(zip(cols, row)) for row in rows]

    async def get_scenes_by_character(self, project_id: str, character_id: str) -> list[dict]:
        result = await self.db.execute(
            text(
                "SELECT * FROM scenes WHERE project_id = :project_id ORDER BY scene_code"
            ),
            {"project_id": project_id},
        )
        rows = result.fetchall()
        cols = result.keys()
        matched = []
        for row in rows:
            d = dict(zip(cols, row))
            chars = d.get("characters_involved")
            if chars:
                if isinstance(chars, str):
                    try:
                        chars = json.loads(chars)
                    except (json.JSONDecodeError, TypeError):
                        chars = []
                if isinstance(chars, list) and character_id in [str(c) for c in chars]:
                    matched.append(d)
        return matched

    async def get_scenes_by_foreshadow(self, project_id: str, foreshadow_id: str) -> list[dict]:
        result = await self.db.execute(
            text(
                "SELECT * FROM scenes WHERE project_id = :project_id ORDER BY scene_code"
            ),
            {"project_id": project_id},
        )
        rows = result.fetchall()
        cols = result.keys()
        matched = []
        for row in rows:
            d = dict(zip(cols, row))
            fs_ops = d.get("foreshadow_ops")
            if fs_ops:
                if isinstance(fs_ops, str):
                    try:
                        fs_ops = json.loads(fs_ops)
                    except (json.JSONDecodeError, TypeError):
                        fs_ops = []
                if isinstance(fs_ops, list):
                    for op in fs_ops:
                        if isinstance(op, dict) and str(op.get("fs_id", "")) == str(foreshadow_id):
                            matched.append(d)
                            break
        return matched

    async def search_scenes_by_keyword(self, project_id: str, keyword: str) -> list[dict]:
        result = await self.db.execute(
            text(
                "SELECT * FROM scenes WHERE project_id = :project_id AND narration LIKE :kw ORDER BY scene_code"
            ),
            {"project_id": project_id, "kw": f"%{keyword}%"},
        )
        rows = result.fetchall()
        cols = result.keys()
        return [dict(zip(cols, row)) for row in rows]

    async def get_scenes_by_emotion_range(self, project_id: str, min_emotion: int, max_emotion: int) -> list[dict]:
        result = await self.db.execute(
            text(
                "SELECT * FROM scenes WHERE project_id = :project_id AND emotion_level >= :min_e AND emotion_level <= :max_e ORDER BY scene_code"
            ),
            {"project_id": project_id, "min_e": min_emotion, "max_e": max_emotion},
        )
        rows = result.fetchall()
        cols = result.keys()
        return [dict(zip(cols, row)) for row in rows]

    async def get_audit_history(self, project_id: str, limit: int = 20) -> list[dict]:
        result = await self.db.execute(
            text(
                "SELECT * FROM audit_records WHERE project_id = :project_id ORDER BY created_at DESC LIMIT :limit"
            ),
            {"project_id": project_id, "limit": limit},
        )
        rows = result.fetchall()
        cols = result.keys()
        return [dict(zip(cols, row)) for row in rows]

    async def get_rejection_count(self, scene_id: str) -> int:
        result = await self.db.execute(
            text(
                "SELECT COUNT(*) FROM audit_records WHERE scene_id = :scene_id AND overall_result = 'rejected'"
            ),
            {"scene_id": scene_id},
        )
        row = result.fetchone()
        return row[0] if row else 0

    async def update_scene_status(self, scene_id: str, status: str):
        now = _now_expr()
        await self.db.execute(
            text(f"UPDATE scenes SET status = :status, updated_at = {now} WHERE id = :scene_id"),
            {"scene_id": scene_id, "status": status},
        )
        await self.db.commit()

    async def update_foreshadow_health(self, project_id: str):
        chapters = await self.get_chapter_outlines(project_id)
        total_chapters = len(chapters) if chapters else 1

        result = await self.db.execute(
            text("SELECT id, current_status, reinforce_count, plant_scene_id, reveal_scene_id, fs_type, name FROM foreshadows WHERE project_id = :project_id"),
            {"project_id": project_id},
        )
        rows = result.fetchall()
        for row in rows:
            fs_id, status, reinforce_count, plant_scene, reveal_scene, fs_type, name = row
            health = "normal"
            issues = []

            if status in ("planted", "reinforced") and (reinforce_count or 0) == 0:
                health = "warning"
                issues.append("已埋设但从未强化")

            if not plant_scene and status != "design":
                health = "warning"
                issues.append("已激活但无埋设场景")

            if not reveal_scene and status in ("planted", "reinforced"):
                health = "danger"
                issues.append("无回收场景规划")

            if fs_type == "global" and total_chapters > 0:
                if plant_scene:
                    try:
                        plant_ch = str(plant_scene).split("_")[1] if "_" in str(plant_scene) else ""
                        if plant_ch and int(plant_ch) > total_chapters * 0.3:
                            if health == "normal":
                                health = "warning"
                            issues.append(f"全局级伏笔在第{plant_ch}章才埋设（建议前30%）")
                    except (ValueError, IndexError):
                        pass

            if status in ("planted", "reinforced") and (reinforce_count or 0) < 3:
                if health == "normal" and total_chapters > 5:
                    health = "warning"
                    issues.append(f"强化次数不足（当前{reinforce_count or 0}次，建议3-5次）")

            await self.db.execute(
                text("UPDATE foreshadows SET health = :health WHERE id = :fs_id"),
                {"health": health, "fs_id": fs_id},
            )
        await self.db.commit()

    async def bulk_update_character_states(self, updates: list[dict]):
        for upd in updates:
            char_id = upd.pop("id", None)
            if char_id and upd:
                set_clauses = [f"{key} = :{key}" for key in upd]
                params = {"character_id": str(char_id), **upd}
                await self.db.execute(
                    text(f"UPDATE characters SET {', '.join(set_clauses)} WHERE id = :character_id"),
                    params,
                )
        await self.db.commit()

    async def get_project_stats(self, project_id: str) -> dict:
        wc = await self.get_project_word_count(project_id)
        sc = await self.db.execute(
            text("SELECT COUNT(*) FROM scenes WHERE project_id = :pid"),
            {"pid": project_id},
        )
        scene_count = sc.scalar_one() or 0
        cc = await self.db.execute(
            text("SELECT COUNT(*) FROM characters WHERE project_id = :pid"),
            {"pid": project_id},
        )
        char_count = cc.scalar_one() or 0
        fc = await self.db.execute(
            text("SELECT COUNT(*) FROM foreshadows WHERE project_id = :pid"),
            {"pid": project_id},
        )
        fs_count = fc.scalar_one() or 0
        return {
            "word_count": wc,
            "scene_count": scene_count,
            "character_count": char_count,
            "foreshadow_count": fs_count,
        }

    async def get_choices(self, project_id: str) -> list[dict]:
        result = await self.db.execute(
            text("SELECT id, choices FROM scenes WHERE project_id = :project_id ORDER BY scene_code"),
            {"project_id": project_id},
        )
        rows = result.fetchall()
        all_choices = []
        for row in rows:
            scene_id, choices_data = row
            if choices_data:
                if isinstance(choices_data, str):
                    try:
                        choices_data = json.loads(choices_data)
                    except (json.JSONDecodeError, TypeError):
                        choices_data = []
                if isinstance(choices_data, list):
                    for ch in choices_data:
                        if isinstance(ch, dict):
                            ch["scene_id"] = str(scene_id)
                            all_choices.append(ch)
        return all_choices

    async def get_world_config(self, project_id: str) -> dict:
        result = await self.db.execute(
            text("SELECT custom_checker_rules FROM project_configs WHERE project_id = :project_id"),
            {"project_id": project_id},
        )
        row = result.fetchone()
        if not row or not row[0]:
            return {}
        try:
            rules = json.loads(row[0]) if isinstance(row[0], str) else dict(row[0])
        except (json.JSONDecodeError, TypeError):
            return {}
        return (rules or {}).get("world_settings", {})

    async def save_world_config(self, project_id: str, world_settings: dict):
        existing = await self.db.execute(
            text("SELECT custom_checker_rules FROM project_configs WHERE project_id = :pid"),
            {"pid": project_id},
        )
        row = existing.fetchone()
        rules = {}
        if row and row[0]:
            try:
                rules = json.loads(row[0]) if isinstance(row[0], str) else dict(row[0])
            except (json.JSONDecodeError, TypeError):
                rules = {}
        if not isinstance(rules, dict):
            rules = {}
        rules["world_settings"] = world_settings
        result = await self.db.execute(
            text("UPDATE project_configs SET custom_checker_rules = :rules, updated_at = " + _now_expr() + " WHERE project_id = :pid"),
            {"pid": project_id, "rules": json.dumps(rules, ensure_ascii=False)},
        )
        if result.rowcount == 0:
            await self.db.execute(
                text(
                    "INSERT INTO project_configs (id, project_id, custom_checker_rules, "
                    "genre, core_contradiction, style, chapter_count, target_word_count, "
                    "plot_complexity, world_building_depth, character_depth_target, work_mode, "
                    "created_at, updated_at) "
                    f"VALUES (:id, :pid, :rules, '', '', '', 10, 50000, 5, 5, 5, 'standard', "
                    f"{_now_expr()}, {_now_expr()})"
                ),
                {"id": str(uuid.uuid4()), "pid": project_id, "rules": json.dumps(rules, ensure_ascii=False)},
            )
        await self.db.commit()

    async def clear_world_config(self, project_id: str):
        pass

    async def clear_characters(self, project_id: str):
        await self.db.execute(
            text("DELETE FROM character_relations WHERE project_id = :pid"),
            {"pid": project_id},
        )
        await self.db.execute(
            text("DELETE FROM characters WHERE project_id = :pid"),
            {"pid": project_id},
        )
        await self.db.commit()

    async def clear_relations(self, project_id: str):
        await self.db.execute(
            text("DELETE FROM character_relations WHERE project_id = :pid"),
            {"pid": project_id},
        )
        await self.db.commit()

    async def clear_foreshadows(self, project_id: str):
        await self.db.execute(
            text("DELETE FROM foreshadows WHERE project_id = :pid"),
            {"pid": project_id},
        )
        await self.db.commit()

    async def clear_chapters(self, project_id: str):
        await self.db.execute(
            text("DELETE FROM chapters WHERE project_id = :pid"),
            {"pid": project_id},
        )
        await self.db.commit()

    async def create_characters_bulk(self, project_id: str, characters: list[dict]):
        now = _now_expr()
        for idx, c in enumerate(characters):
            char_id = str(uuid.uuid4())
            char_code = f"C{idx + 1:03d}"
            await self.db.execute(
                text(
                    f"INSERT INTO characters (id, project_id, char_code, name, role_type, background, "
                    f"core_goal, core_fear, surface_image, true_self, language_style, catchphrase, "
                    f"arc_description, behavior_inevitable, behavior_never, behavior_conditional, "
                    f"status, created_at) VALUES "
                    f"(:id, :pid, :code, :name, :role_type, :background, :core_goal, :core_fear, "
                    f":surface_image, :true_self, :language_style, :catchphrase, :arc_description, "
                    f":b_inevitable, :b_never, :b_conditional, 'active', {now})"
                ),
                {
                    "id": char_id, "pid": project_id, "code": char_code,
                    "name": c.get("name", c.get("名称", f"角色{idx + 1}")),
                    "role_type": c.get("role_type", c.get("角色类型", c.get("type", ""))),
                    "background": c.get("background", c.get("背景故事", c.get("背景", ""))),
                    "core_goal": c.get("core_goal", c.get("核心动机", c.get("动机", ""))),
                    "core_fear": c.get("core_fear", c.get("核心恐惧", c.get("恐惧", ""))),
                    "surface_image": c.get("surface_image", c.get("表面形象", "")),
                    "true_self": c.get("true_self", c.get("真实面目", "")),
                    "language_style": c.get("language_style", c.get("语言风格", "")),
                    "catchphrase": c.get("catchphrase", c.get("口头禅", "")),
                    "arc_description": c.get("arc_description", c.get("角色弧描述", "")),
                    "b_inevitable": json.dumps(c.get("behavior_inevitable", c.get("必然行为", [])), ensure_ascii=False),
                    "b_never": json.dumps(c.get("behavior_never", c.get("绝对不会行为", [])), ensure_ascii=False),
                    "b_conditional": json.dumps(c.get("behavior_conditional", c.get("需要铺垫才能行为", [])), ensure_ascii=False),
                },
            )
        await self.db.commit()

    async def create_foreshadows_bulk(self, project_id: str, foreshadows: list[dict]):
        now = _now_expr()
        for idx, fs in enumerate(foreshadows):
            fs_id = str(uuid.uuid4())
            fs_code = f"FS{idx + 1:03d}"
            name = fs.get("name", fs.get("名称", f"伏笔{idx + 1}"))
            await self.db.execute(
                text(
                    f"INSERT INTO foreshadows (id, project_id, fs_code, name, fs_type, surface_layer, "
                    f"deep_layer, truth_layer, plant_scene_id, reinforce_scenes, reveal_scene_id, "
                    f"wow_factor, player_reaction, depends_on, enables, current_status, reinforce_count, "
                    f"health, wow_plans, wow_selected, foreshadow_tier, worldview_refs, character_refs, "
                    f"foreshadow_links, plant_location, reinforce_locations, reveal_location, reclaim_status, "
                    f"created_at) VALUES "
                    f"(:id, :pid, :code, :name, :fs_type, :surface, :deep, :truth, :plant, :reinforce, "
                    f":reveal, :wow_factor, :player_reaction, :depends, :enables, 'design', 0, "
                    f"'normal', '[]', NULL, :tier, '[]', '[]', '[]', :plant_loc, '[]', :reveal_loc, 'unplanted', "
                    f"{now})"
                ),
                {
                    "id": fs_id, "pid": project_id, "code": fs_code,
                    "name": name,
                    "fs_type": fs.get("fs_type", fs.get("type", "剧情")),
                    "surface": fs.get("surface_layer", fs.get("表层", "")),
                    "deep": fs.get("deep_layer", fs.get("深层", "")),
                    "truth": fs.get("truth_layer", fs.get("真相层", "")),
                    "plant": fs.get("plant_scene_id", None),
                    "reinforce": json.dumps(fs.get("reinforce_scenes", []), ensure_ascii=False),
                    "reveal": fs.get("reveal_scene_id", None),
                    "wow_factor": fs.get("wow_factor", None),
                    "player_reaction": fs.get("player_reaction", None),
                    "depends": json.dumps(fs.get("depends_on", []), ensure_ascii=False),
                    "enables": json.dumps(fs.get("enables", []), ensure_ascii=False),
                    "tier": fs.get("foreshadow_tier", "chapter"),
                    "plant_loc": fs.get("plant_location"),
                    "reveal_loc": fs.get("reveal_location"),
                },
            )
        await self.db.commit()

    async def create_chapters_bulk(self, project_id: str, chapters: list[dict]):
        now = _now_expr()
        for idx, ch in enumerate(chapters):
            ch_id = str(uuid.uuid4())
            await self.db.execute(
                text(
                    f"INSERT INTO chapters (id, project_id, chapter_number, title, summary, "
                    f"outline, core_conflict, emotion_target, key_turning_points, foreshadow_tasks, "
                    f"branch_structure, anchor_scenes, status, created_at) VALUES "
                    f"(:id, :pid, :num, :title, :summary, :outline, :conflict, :emotion, "
                    f":turning, :fs_tasks, :branch, :anchor, 'draft', {now})"
                ),
                {
                    "id": ch_id, "pid": project_id,
                    "num": ch.get("chapter_number", ch.get("chapterNumber", ch.get("章编号", idx + 1))),
                    "title": ch.get("title", ch.get("标题", f"第{idx + 1}章")),
                    "summary": ch.get("summary", ch.get("摘要", ch.get("summary_content", ch.get("概述", "")))),
                    "outline": ch.get("outline", ch.get("大纲", ch.get("outline_content", ""))),
                    "conflict": ch.get("core_conflict", ch.get("核心冲突", ch.get("conflict", ""))),
                    "emotion": ch.get("emotion_target", ch.get("情感目标", 5)),
                    "turning": json.dumps(ch.get("key_turning_points", ch.get("keyTurningPoints", ch.get("关键转折", []))), ensure_ascii=False),
                    "fs_tasks": json.dumps(ch.get("foreshadow_tasks", ch.get("foreshadowTasks", ch.get("伏笔任务", []))), ensure_ascii=False),
                    "branch": ch.get("branch_structure", ch.get("branchStructure", ch.get("分支结构", ""))),
                    "anchor": json.dumps(ch.get("anchor_scenes", ch.get("anchorScenes", ch.get("锚点场景", []))), ensure_ascii=False),
                },
            )
        await self.db.commit()

    async def get_chapter(self, project_id: str, chapter_id: str) -> Optional[dict]:
        result = await self.db.execute(
            text("SELECT * FROM chapters WHERE id = :chapter_id AND project_id = :project_id"),
            {"chapter_id": chapter_id, "project_id": project_id},
        )
        row = result.fetchone()
        if not row:
            return None
        return dict(zip(result.keys(), row))

    async def get_scenes_by_project(self, project_id: str) -> list[dict]:
        result = await self.db.execute(
            text("SELECT * FROM scenes WHERE project_id = :project_id ORDER BY scene_code"),
            {"project_id": project_id},
        )
        rows = result.fetchall()
        cols = result.keys()
        return [dict(zip(cols, row)) for row in rows]

    async def create_scene(self, scene_data: dict):
        now = _now_expr()
        await self.db.execute(
            text(
                f"""
                INSERT INTO scenes (
                    id, project_id, chapter_id, scene_code, scene_type, location, weather,
                    emotion_level, narration, dialogue, actions, choices, foreshadow_ops,
                    causal_chain, characters_involved, status, version, created_at, updated_at
                ) VALUES (
                    :id, :project_id, :chapter_id, :scene_code, :scene_type, :location, :weather,
                    :emotion_level, :narration, :dialogue, :actions, :choices, :foreshadow_ops,
                    :causal_chain, :characters_involved, :status, :version, {now}, {now}
                )
                """
            ),
            {
                "id": scene_data.get("id", str(uuid.uuid4())),
                "project_id": scene_data["project_id"],
                "chapter_id": scene_data.get("chapter_id"),
                "scene_code": scene_data.get("scene_code", ""),
                "scene_type": scene_data.get("scene_type", "dialogue"),
                "location": scene_data.get("location", ""),
                "weather": scene_data.get("weather", ""),
                "emotion_level": scene_data.get("emotion_level", 5),
                "narration": scene_data.get("narration", ""),
                "dialogue": scene_data.get("dialogue", "[]"),
                "actions": scene_data.get("actions", "[]"),
                "choices": scene_data.get("choices", "[]"),
                "foreshadow_ops": scene_data.get("foreshadow_ops", "[]"),
                "causal_chain": scene_data.get("causal_chain", "{}"),
                "characters_involved": scene_data.get("characters_involved", "[]"),
                "status": scene_data.get("status", "pending"),
                "version": scene_data.get("version", 1),
            },
        )
        await self.db.commit()

    async def update_scene(self, project_id: str, scene_id: str, updates: dict):
        now = _now_expr()
        set_clauses = []
        params = {"project_id": project_id, "scene_id": scene_id}
        for key, val in updates.items():
            set_clauses.append(f"{key} = :{key}")
            params[key] = val
        if set_clauses:
            await self.db.execute(
                text(
                    f"UPDATE scenes SET {', '.join(set_clauses)}, updated_at = {now} "
                    f"WHERE project_id = :project_id AND id = :scene_id"
                ),
                params,
            )
            await self.db.commit()

    async def update_project_status(self, project_id: str, updates: dict):
        now = _now_expr()
        set_clauses = []
        params = {"project_id": project_id}
        for key, val in updates.items():
            set_clauses.append(f"{key} = :{key}")
            params[key] = val
        if set_clauses:
            await self.db.execute(
                text(
                    f"UPDATE project_configs SET {', '.join(set_clauses)}, updated_at = {now} "
                    f"WHERE project_id = :project_id"
                ),
                params,
            )
            await self.db.commit()
