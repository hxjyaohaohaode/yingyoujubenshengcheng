import json
import logging
from collections import defaultdict
from typing import Any

from core.agent.base import BaseAgent, AgentTask, AgentResult
from core.agent.registry import register_agent
from core.agent.skill import Skill

logger = logging.getLogger(__name__)

VALID_FS_TRANSITIONS = {
    "design": {"plant"},
    "planted": {"reinforce", "reveal"},
    "reinforced": {"reinforce", "reveal"},
    "revealed": set(),
    "active": {"reinforce", "reveal"},
}

_FS_OP_TO_STATUS = {
    "plant": "planted",
    "reinforce": "reinforced",
    "reveal": "revealed",
}

INTERACTION_TYPE_IMPACT = {
    "cooperation": 15,
    "conflict": -10,
    "betrayal": -30,
    "reconciliation": 20,
    "sacrifice": 25,
    "teaching": 10,
    "competition": -5,
    "romance": 30,
    "family": 20,
    "rivalry": -15,
    "secret_cooperation": 20,
    "hidden_betrayal": -40,
    "blackmail": -35,
    "debt_collection": -20,
    "information_trade": 5,
    "surrogate_reveal": -25,
    "former_bond_trigger": -15,
}

RELATION_RANGE = (-100, 100)

DETONATION_THRESHOLD = -60

STATE_UPDATER_SKILL = Skill()
STATE_UPDATER_SKILL.name = "state_updater"
STATE_UPDATER_SKILL.intent = "reason.logic"
STATE_UPDATER_SKILL.prompt_template = """你是角色状态分析专家。请分析以下场景内容，提取每个参与角色的状态变化。

## 角色当前状态
{character_states}

## 场景内容
场景编号: {scene_code}
旁白: {narration}
对白: {dialogue_text}
动作: {actions_text}

## 分析要求
对每个参与角色，分析以下变化:
1. 情感状态变化（从什么状态到什么状态）
2. 新获得的信息/秘密
3. 关系变化（与谁的关系如何改变）
4. 物理状态变化（受伤/获得物品等）
5. 动机/目标变化

输出JSON格式:
{{
  "character_updates": [
    {{
      "character_name": "角色名",
      "emotional_state_change": "情感变化描述",
      "new_known_secrets": ["新知道的秘密"],
      "relationship_changes": [{{"target": "另一角色", "change": "关系变化描述"}}],
      "physical_state_change": "物理状态变化",
      "motivation_change": "动机变化（如有）"
    }}
  ]
}}"""
STATE_UPDATER_SKILL.output_parser = lambda text: {"update": text}

FORESHADOW_TRACKER_SKILL = Skill()
FORESHADOW_TRACKER_SKILL.name = "foreshadow_tracker"
FORESHADOW_TRACKER_SKILL.intent = "planning"
FORESHADOW_TRACKER_SKILL.prompt_template = "伏笔健康度检测：超过5章未强化→警告，超过8章→危险。"
FORESHADOW_TRACKER_SKILL.output_parser = lambda text: {"tracker": text}

RELATION_MANAGER_SKILL = Skill()
RELATION_MANAGER_SKILL.name = "relation_manager"
RELATION_MANAGER_SKILL.intent = "planning"
RELATION_MANAGER_SKILL.prompt_template = "关系值管理：互动类型→关系值映射，引爆点检测。"
RELATION_MANAGER_SKILL.output_parser = lambda text: {"relation": text}

CONSISTENCY_CHECKER_SKILL = Skill()
CONSISTENCY_CHECKER_SKILL.name = "consistency_checker"
CONSISTENCY_CHECKER_SKILL.intent = "planning"
CONSISTENCY_CHECKER_SKILL.prompt_template = "状态自洽检查：角色行为与设定冲突检测。"
CONSISTENCY_CHECKER_SKILL.output_parser = lambda text: {"consistency": text}


@register_agent
class StateManagerAgent(BaseAgent):
    name = "state_manager"
    description = "角色状态更新、伏笔追踪(健康度检测)、关系值管理(引爆点检测)、信息点同步、情感曲线维护、自洽检查"
    skills = {
        "state_updater": STATE_UPDATER_SKILL,
        "foreshadow_tracker": FORESHADOW_TRACKER_SKILL,
        "relation_manager": RELATION_MANAGER_SKILL,
        "consistency_checker": CONSISTENCY_CHECKER_SKILL,
    }

    async def execute(self, task: AgentTask) -> AgentResult:
        self._validate(task)

        project_id = task.project_id
        scene_id = task.payload.get("scene_id")
        operation = task.payload.get("operation", "update_from_scene")

        try:
            if operation == "track_foreshadow_health":
                return await self._track_foreshadow_health(project_id)

            if operation == "check_detonation":
                return await self._check_detonation_points(project_id)

            if operation == "consistency_check":
                return await self._consistency_check(project_id, scene_id)

            if operation == "update_relation_value":
                return await self._update_relation_value(project_id, task.payload)

            if not scene_id:
                # 没有scene_id时，从payload中获取场景数据直接更新
                scene_data = task.payload.get("previous_result", {})
                if scene_data and isinstance(scene_data, dict):
                    char_updates = await self._update_characters_from_scene(scene_data, project_id, task)
                    fs_updates = await self._update_foreshadows_from_scene(scene_data, project_id)
                    rel_updates = await self._update_relations_from_scene(scene_data, project_id)

                    health_warnings = await self._compute_foreshadow_health(project_id)
                    detonation_warnings = await self._detect_detonation_points(project_id)

                    return AgentResult(
                        status="completed",
                        data={
                            "scene_id": None,
                            "character_updates": char_updates,
                            "foreshadow_updates": fs_updates,
                            "relation_updates": rel_updates,
                            "foreshadow_health_warnings": health_warnings,
                            "detonation_warnings": detonation_warnings,
                        },
                    )
                # 没有scene_id也没有场景数据，直接返回成功
                return AgentResult(
                    status="completed",
                    data={"scene_id": None, "message": "无场景数据，跳过状态更新"},
                )

            scene = await self.storage.get_scene(project_id, scene_id)
            if not scene:
                raise ValueError(f"场景 {scene_id} 不存在")

            char_updates = await self._update_characters_from_scene(scene, project_id, task)
            fs_updates = await self._update_foreshadows_from_scene(scene, project_id)
            rel_updates = await self._update_relations_from_scene(scene, project_id)

            health_warnings = await self._compute_foreshadow_health(project_id)
            detonation_warnings = await self._detect_detonation_points(project_id)

            return AgentResult(
                status="completed",
                data={
                    "scene_id": scene_id,
                    "character_updates": char_updates,
                    "foreshadow_updates": fs_updates,
                    "relation_updates": rel_updates,
                    "foreshadow_health_warnings": health_warnings,
                    "detonation_warnings": detonation_warnings,
                },
            )
        except Exception as e:
            logger.error("StateManager failed for scene %s: %s", scene_id, str(e))
            return AgentResult(
                status="failed",
                data={"scene_id": scene_id, "error": str(e)},
                issues=[str(e)],
            )

    def _validate(self, task: AgentTask):
        if not task.project_id:
            raise ValueError("project_id is required")

    async def _build_context(self, task: AgentTask) -> dict:
        return {}

    def _select_skill(self, task_type: str) -> Skill:
        return self.skills[task_type]

    async def _update_characters_from_scene(self, scene: dict, project_id: str, task: AgentTask | None = None) -> dict:
        characters_involved = scene.get("characters_involved", [])
        if isinstance(characters_involved, str):
            try:
                characters_involved = json.loads(characters_involved)
            except (json.JSONDecodeError, TypeError):
                characters_involved = []
        if not characters_involved:
            return {"updated": 0}

        char_names = []
        for item in characters_involved:
            if isinstance(item, str):
                char_names.append(item)
            elif isinstance(item, dict):
                char_names.append(item.get("name", item.get("id", "")))

        if not char_names:
            return {"updated": 0}

        updates = {}

        narration = scene.get("narration", "")
        dialogue = scene.get("dialogue", [])
        actions = scene.get("actions", [])

        if isinstance(dialogue, list):
            dialogue_text = "\n".join(
                f"{d.get('char', '?')}: {d.get('text', '')}" for d in dialogue if isinstance(d, dict)
            )
        else:
            dialogue_text = str(dialogue) if dialogue else ""

        if isinstance(actions, list):
            actions_text = "\n".join(str(a) for a in actions)
        else:
            actions_text = str(actions) if actions else ""

        if task and self.gateway and narration:
            try:
                characters = await self.storage.get_character_states(project_id) or []
                char_states_text = ""
                for c in characters:
                    c_name = c.get("name", "")
                    if c_name in char_names:
                        char_states_text += (
                            f"- {c_name} ({c.get('role_type', '?')}): "
                            f"动机={c.get('core_goal', '')}, 恐惧={c.get('core_fear', '')}, "
                            f"语言风格={c.get('language_style', '')}\n"
                        )

                from core.agent.skill import Skill
                llm_result = await self.gateway.invoke(
                    intent="reason.logic",
                    messages=[
                        {"role": "system", "content": "你是角色状态分析专家，请分析场景中每个角色的状态变化，输出严格的JSON格式。"},
                        {"role": "user", "content": f"""请分析以下场景中角色的状态变化。

## 角色当前状态
{char_states_text or '无角色状态信息'}

## 场景内容
场景编号: {scene.get('scene_code', '?')}
旁白: {narration[:10000]}
对白: {dialogue_text[:8000]}
动作: {actions_text[:5000]}

请输出JSON:
{{
  "character_updates": [
    {{
      "character_name": "角色名",
      "emotional_state_change": "情感变化描述",
      "new_known_secrets": ["新知道的秘密"],
      "relationship_changes": [{{"target": "另一角色", "change": "关系变化描述"}}],
      "physical_state_change": "物理状态变化",
      "motivation_change": "动机变化"
    }}
  ]
}}"""},
                    ],
                    cost_profile="economy",
                    max_tokens=4096,
                    temperature=0.3,
                )

                llm_parsed = self._extract_json_from_text(llm_result.content)
                if llm_parsed and isinstance(llm_parsed, dict):
                    char_updates_list = llm_parsed.get("character_updates", [])
                    for cu in char_updates_list:
                        if not isinstance(cu, dict):
                            continue
                        cu_name = cu.get("character_name", "")
                        if not cu_name:
                            continue

                        status_change = {}
                        if cu.get("emotional_state_change"):
                            status_change["emotional_state"] = cu["emotional_state_change"]
                        if cu.get("physical_state_change"):
                            status_change["physical_state"] = cu["physical_state_change"]
                        if cu.get("motivation_change"):
                            status_change["current_goal"] = cu["motivation_change"]
                        if cu.get("new_known_secrets"):
                            status_change["new_known_secrets"] = cu["new_known_secrets"]

                        if status_change:
                            try:
                                characters_db = await self.storage.get_character_states(project_id) or []
                                for c in characters_db:
                                    if c.get("name") == cu_name:
                                        await self.storage.update_character_state(str(c.get("id")), status_change)
                                        updates[cu_name] = status_change
                                        break
                            except Exception as e:
                                logger.warning("LLM分析后更新角色 %s 状态失败: %s", cu_name, str(e))

            except Exception as e:
                logger.warning("LLM角色状态分析失败，回退到简单更新: %s", str(e))

        if not updates:
            for item in characters_involved:
                char_id = item if isinstance(item, str) else item.get("id") or item.get("character_id")
                if not char_id:
                    continue

                scene_updates = item if isinstance(item, dict) else {}
                status_change = scene_updates.get("status_change", {})
                if status_change:
                    try:
                        await self.storage.update_character_state(str(char_id), status_change)
                        updates[str(char_id)] = status_change
                    except Exception as e:
                        logger.warning("更新角色 %s 状态失败: %s", char_id, str(e))

        return {"updated": len(updates), "details": updates}

    def _extract_json_from_text(self, text: str) -> dict | None:
        if not text:
            return None
        text = text.strip()
        if text.startswith("```json"):
            text = text[7:]
        elif text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
        import re
        m = re.search(r'\{[\s\S]*\}', text)
        if m:
            try:
                return json.loads(m.group(0))
            except json.JSONDecodeError:
                pass
        start = text.find("{")
        if start >= 0:
            fragment = text[start:]
            open_braces = 0
            open_brackets = 0
            in_string = False
            escape_next = False
            for ch in fragment:
                if escape_next:
                    escape_next = False
                    continue
                if ch == "\\":
                    escape_next = True
                    continue
                if ch == '"' and not escape_next:
                    in_string = not in_string
                    continue
                if in_string:
                    continue
                if ch == "{":
                    open_braces += 1
                elif ch == "}":
                    open_braces -= 1
                elif ch == "[":
                    open_brackets += 1
                elif ch == "]":
                    open_brackets -= 1
            closing = ""
            if in_string:
                closing += '"'
            closing += "]" * max(0, open_brackets) + "}" * max(0, open_braces)
            candidate = fragment + closing
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                pass
            last_complete = -1
            depth = 0
            for i, ch in enumerate(fragment):
                if ch == "{":
                    depth += 1
                elif ch == "}":
                    depth -= 1
                    if depth == 0:
                        last_complete = i
            if last_complete > 0:
                try:
                    return json.loads(fragment[:last_complete + 1])
                except json.JSONDecodeError:
                    pass
        return None

    async def _update_foreshadows_from_scene(self, scene: dict, project_id: str) -> dict:
        foreshadow_ops = scene.get("foreshadow_ops", [])
        if isinstance(foreshadow_ops, str):
            foreshadow_ops = json.loads(foreshadow_ops)
        if not foreshadow_ops:
            return {"updated": 0}

        updates = {}
        scene_id = scene.get("id") or scene.get("scene_id", "")
        for op in foreshadow_ops:
            fs_id = op.get("fs_id") or op.get("fs_code")
            operation = op.get("op", op.get("operation", ""))
            if not fs_id or operation not in ("plant", "reinforce", "reveal"):
                continue

            current = await self.storage.get_foreshadow(project_id, str(fs_id))
            if not current:
                try:
                    all_fs = await self.storage.get_foreshadows(project_id)
                    for f in all_fs:
                        if f.get("fs_code") == str(fs_id):
                            current = f
                            break
                except Exception:
                    pass
            current_status = current.get("current_status", "design") if current else "design"

            if operation not in VALID_FS_TRANSITIONS.get(current_status, set()):
                logger.warning("伏笔 %s 非法状态转换: %s → %s", fs_id, current_status, operation)
                continue

            new_status = _FS_OP_TO_STATUS.get(operation, operation)
            update_data: dict[str, object] = {"current_status": new_status}
            if operation == "reinforce" and current:
                old_count = current.get("reinforce_count", 0) or 0
                update_data["reinforce_count"] = int(old_count if isinstance(old_count, (int, float, str)) else 0) + 1
                reinforce_scenes = list(current.get("reinforce_scenes", []) or [])
                if scene_id and scene_id not in reinforce_scenes:
                    reinforce_scenes.append(scene_id)
                update_data["reinforce_scenes"] = json.dumps(reinforce_scenes, ensure_ascii=False)
            elif operation == "plant":
                if scene_id:
                    update_data["plant_scene_id"] = scene_id
            elif operation == "reveal":
                if scene_id:
                    update_data["reveal_scene_id"] = scene_id

            try:
                await self.storage.update_foreshadow_state(str(fs_id), update_data)
                updates[str(fs_id)] = operation
            except Exception as e:
                logger.warning("更新伏笔 %s 状态失败: %s", fs_id, str(e))

        return {"updated": len(updates), "details": updates}

    async def _update_relations_from_scene(self, scene: dict, project_id: str) -> dict:
        characters_involved = scene.get("characters_involved", [])
        if isinstance(characters_involved, str):
            characters_involved = json.loads(characters_involved)
        if len(characters_involved) < 2:
            return {"updated": 0}

        interaction_type = scene.get("interaction_type", "cooperation")

        updates = {}
        for i, item_a in enumerate(characters_involved):
            id_a = item_a if isinstance(item_a, str) else item_a.get("id") or item_a.get("character_id")
            if not id_a:
                continue
            for j, item_b in enumerate(characters_involved):
                if i >= j:
                    continue
                id_b = item_b if isinstance(item_b, str) else item_b.get("id") or item_b.get("character_id")
                if not id_b:
                    continue
                try:
                    impact = INTERACTION_TYPE_IMPACT.get(interaction_type, 5)
                    await self._apply_relation_change(project_id, str(id_a), str(id_b), impact, interaction_type)
                    updates[f"{id_a}-{id_b}"] = {"type": interaction_type, "impact": impact}
                except Exception as e:
                    logger.warning("更新关系 %s-%s 失败: %s", id_a, id_b, str(e))

        return {"updated": len(updates), "details": updates}

    async def _apply_relation_change(self, project_id: str, char_a: str, char_b: str, impact: int, interaction_type: str):
        current = await self.storage.get_relation(project_id, char_a, char_b)
        if current:
            old_value = current.get("value", 0)
            new_value = max(RELATION_RANGE[0], min(RELATION_RANGE[1], old_value + impact))
            await self.storage.update_relation(project_id, char_a, char_b, {
                "value": new_value,
                "last_interaction": interaction_type,
            })
        else:
            await self.storage.update_relation(project_id, char_a, char_b, {
                "value": impact,
                "last_interaction": interaction_type,
            })

    async def _track_foreshadow_health(self, project_id: str) -> AgentResult:
        warnings = await self._compute_foreshadow_health(project_id)
        await self.storage.update_foreshadow_health(project_id)
        return AgentResult(
            status="completed",
            data={"project_id": project_id, "warnings": warnings},
        )

    async def _compute_foreshadow_health(self, project_id: str) -> list[dict]:
        foreshadows = await self.storage.get_foreshadows(project_id)
        if not foreshadows:
            return []

        scenes = await self.storage.get_scene_summaries(project_id)
        scene_codes = {s.get("id"): s.get("scene_code", "") for s in (scenes or [])}

        warnings = []
        for fs in foreshadows:
            fs_id = fs.get("id", "")
            status = fs.get("current_status", "design")
            reinforce_count = fs.get("reinforce_count", 0) or 0
            plant_scene = fs.get("plant_scene_id", "")
            reveal_scene = fs.get("reveal_scene_id", "")

            if status in ("planted", "reinforced") and reinforce_count == 0:
                warnings.append({
                    "foreshadow_id": fs_id,
                    "type": "no_reinforce",
                    "severity": "warning",
                    "message": f"伏笔 {fs.get('name', fs_id)} 已埋设但从未被强化",
                })

            if not reveal_scene and status in ("planted", "reinforced"):
                plant_code = scene_codes.get(plant_scene, "")
                current_max = max((s.get("scene_code", "") for s in (scenes or [])), default="")
                if plant_code and current_max:
                    try:
                        gap = int(current_max.split(".")[1] if "." in current_max else 0) - int(plant_code.split(".")[1] if "." in plant_code else 0)
                        if gap > 8:
                            warnings.append({
                                "foreshadow_id": fs_id,
                                "type": "overdue",
                                "severity": "danger",
                                "message": f"伏笔 {fs.get('name', fs_id)} 已超过8个场景未回收",
                            })
                        elif gap > 5:
                            warnings.append({
                                "foreshadow_id": fs_id,
                                "type": "aging",
                                "severity": "warning",
                                "message": f"伏笔 {fs.get('name', fs_id)} 已超过5个场景未强化",
                            })
                    except (ValueError, IndexError):
                        pass

        return warnings

    async def _check_detonation_points(self, project_id: str) -> AgentResult:
        detonations = await self._detect_detonation_points(project_id)
        return AgentResult(
            status="completed",
            data={"project_id": project_id, "detonation_points": detonations},
        )

    async def _detect_detonation_points(self, project_id: str) -> list[dict]:
        relations = await self.storage.get_relations(project_id)
        if not relations:
            return []

        detonations = []
        for rel in relations:
            value = rel.get("value", 0)
            if value <= DETONATION_THRESHOLD:
                detonations.append({
                    "character_a": rel.get("character_a_id", ""),
                    "character_b": rel.get("character_b_id", ""),
                    "value": value,
                    "threshold": DETONATION_THRESHOLD,
                    "message": f"关系值 {value} 已达引爆点 (≤{DETONATION_THRESHOLD})，建议安排冲突爆发场景",
                })
            elif value <= DETONATION_THRESHOLD + 20:
                detonations.append({
                    "character_a": rel.get("character_a_id", ""),
                    "character_b": rel.get("character_b_id", ""),
                    "value": value,
                    "threshold": DETONATION_THRESHOLD,
                    "message": f"关系值 {value} 接近引爆点，注意节奏控制",
                    "severity": "approaching",
                })

        return detonations

    async def _update_relation_value(self, project_id: str, payload: dict) -> AgentResult:
        char_a = payload.get("character_a_id", "")
        char_b = payload.get("character_b_id", "")
        interaction_type = payload.get("interaction_type", "cooperation")
        if not char_a or not char_b:
            return AgentResult(status="failed", data={"error": "character_a_id and character_b_id required"}, issues=["Missing character IDs"])

        impact = INTERACTION_TYPE_IMPACT.get(interaction_type, 5)
        await self._apply_relation_change(project_id, char_a, char_b, impact, interaction_type)

        detonation_check = await self._detect_detonation_points(project_id)

        return AgentResult(
            status="completed",
            data={
                "character_a": char_a,
                "character_b": char_b,
                "interaction_type": interaction_type,
                "impact": impact,
                "detonation_warnings": detonation_check,
            },
        )

    async def _consistency_check(self, project_id: str, scene_id: str | None = None) -> AgentResult:
        issues = []

        characters = await self.storage.get_character_states(project_id)
        char_map = {}
        for c in (characters or []):
            cid = c.get("id", "")
            char_map[str(cid)] = c

        if scene_id:
            scene = await self.storage.get_scene(project_id, scene_id)
            if scene:
                chars_involved = scene.get("characters_involved", [])
                if isinstance(chars_involved, str):
                    chars_involved = json.loads(chars_involved)

                for item in (chars_involved or []):
                    char_id = str(item if isinstance(item, str) else item.get("id", ""))
                    if not char_id:
                        continue
                    char = char_map.get(char_id)
                    if not char:
                        issues.append({
                            "type": "missing_character",
                            "severity": "error",
                            "message": f"场景引用了不存在的角色 {char_id}",
                        })
                        continue

                    narration = scene.get("narration", "")
                    behavior_never = char.get("behavior_never", "")
                    if behavior_never and narration:
                        if isinstance(behavior_never, list):
                            never_items = [str(n).strip() for n in behavior_never if str(n).strip()]
                        else:
                            never_items = [n.strip() for n in str(behavior_never).split(",") if n.strip()]
                        for never_action in never_items:
                            if never_action in narration:
                                issues.append({
                                    "type": "behavior_violation",
                                    "severity": "warning",
                                    "character_id": char_id,
                                    "character_name": char.get("name", ""),
                                    "message": f"角色 {char.get('name', '')} 做了设定中「绝不做」的行为: {never_action}",
                                })

        foreshadows = await self.storage.get_foreshadows(project_id)
        for fs in (foreshadows or []):
            status = fs.get("current_status", "design")
            if status == "reveal" and not fs.get("reveal_scene_id"):
                issues.append({
                    "type": "foreshadow_inconsistency",
                    "severity": "error",
                    "foreshadow_id": fs.get("id", ""),
                    "message": f"伏笔 {fs.get('name', '')} 状态为已揭示但缺少揭示场景",
                })

        return AgentResult(
            status="completed",
            data={"project_id": project_id, "scene_id": scene_id, "issues": issues, "issue_count": len(issues)},
        )
