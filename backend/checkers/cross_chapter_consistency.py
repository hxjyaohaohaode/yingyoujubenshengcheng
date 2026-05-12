import logging
import re
from collections import defaultdict

logger = logging.getLogger(__name__)


def check_cross_chapter_consistency(
    scenes: list[dict],
    characters: list[dict],
    foreshadows: list[dict],
    timeline_threshold: int = 3,
) -> dict:
    findings = []
    cross_chapter_issues = []

    char_state_tracker = {}
    for char in characters:
        char_state_tracker[char.get("id", "")] = {
            "name": char.get("name", "?"),
            "last_location": None,
            "last_emotion": None,
            "last_known_info": set(),
            "last_scene": None,
        }

    fact_registry = {}
    fact_patterns = [
        (r"受伤|骨折|中箭|中毒|昏迷|重伤", "身体健康状态"),
        (r"死亡|去世|牺牲|阵亡|离世", "角色存活状态"),
        (r"怀孕|生子|分娩|临盆", "生育状态"),
        (r"失忆|遗忘|记忆消失", "记忆状态"),
        (r"被囚|关押|监禁|软禁", "自由状态"),
        (r"失去.*能力|功力尽失|武功被废", "能力状态"),
        (r"获得.*能力|觉醒|突破|领悟", "能力获取"),
    ]

    for i, scene in enumerate(scenes):
        scene_narration = scene.get("narration", "")
        scene_code = scene.get("scene_code", f"S-{i}")
        scene_chars = scene.get("characters_involved", []) or []

        for char_id in scene_chars:
            cid = str(char_id) if not isinstance(char_id, str) else char_id
            tracker = char_state_tracker.get(cid)
            if tracker is None:
                continue

            current_location = scene.get("location", "")
            current_emotion = scene.get("emotion_level", 5)

            if tracker["last_location"] is not None:
                if current_location != tracker["last_location"]:
                    findings.append({
                        "type": "location_change",
                        "character": tracker["name"],
                        "from_scene": tracker["last_scene"],
                        "to_scene": scene_code,
                        "from_location": tracker["last_location"],
                        "to_location": current_location,
                    })

            if tracker["last_emotion"] is not None:
                emotion_delta = abs(current_emotion - tracker["last_emotion"])
                if emotion_delta > timeline_threshold:
                    cross_chapter_issues.append(
                        f"[{tracker['name']}] {tracker['last_scene']}→{scene_code} 情绪突变({tracker['last_emotion']}→{current_emotion}，跨度{emotion_delta})"
                    )

            tracker["last_location"] = current_location
            tracker["last_emotion"] = current_emotion
            tracker["last_scene"] = scene_code

        for pattern, fact_type in fact_patterns:
            matches = re.findall(pattern, scene_narration)
            if matches:
                for _ in matches:
                    fact_key = f"{fact_type}:{scene_code}"
                    if fact_key not in fact_registry:
                        fact_registry[fact_key] = {
                            "type": fact_type,
                            "established_in": scene_code,
                            "contradictions": [],
                        }

    for i, scene in enumerate(scenes):
        scene_narration = scene.get("narration", "")
        scene_code = scene.get("scene_code", f"S-{i}")

        if "恢复" in scene_narration or "痊愈" in scene_narration or "康复" in scene_narration:
            for fact_key, fact in fact_registry.items():
                if fact["type"] == "身体健康状态" and fact["established_in"] != scene_code:
                    fact["contradictions"].append({
                        "scene": scene_code,
                        "detail": f"前文{fact['established_in']}中受伤/中毒，{scene_code}突然恢复",
                    })

        if re.search(r"复活|死而复生|复活了", scene_narration):
            for fact_key, fact in fact_registry.items():
                if fact["type"] == "角色存活状态" and fact["established_in"] != scene_code:
                    fact["contradictions"].append({
                        "scene": scene_code,
                        "detail": f"前文{fact['established_in']}中死亡，{scene_code}复活未合理解释",
                    })

    fact_conflicts = []
    for fact_key, fact in fact_registry.items():
        for contradiction in fact["contradictions"]:
            fact_conflicts.append(
                f"[{fact['type']}] {fact['established_in']}→{contradiction['scene']}: {contradiction['detail']}"
            )

    active_foreshadows = [fs for fs in foreshadows if fs.get("current_status") not in ("reveal", "verify")]
    long_pending = [
        f"FS-{fs.get('fs_code', '?')}: {fs.get('name', '?')} (状态: {fs.get('current_status', '?')})"
        for fs in active_foreshadows if (fs.get("reinforce_count", 0) or 0) == 0
    ]

    total_issues = len(cross_chapter_issues) + len(fact_conflicts) + len(long_pending)
    pass_check = total_issues == 0

    return {
        "pass": pass_check,
        "cross_chapter_issues": cross_chapter_issues,
        "fact_conflicts": fact_conflicts,
        "long_pending_foreshadows": long_pending,
        "location_changes": len(findings),
        "total_issues": total_issues,
        "suggestion": (
            "跨章一致性良好" if pass_check
            else f"发现{total_issues}处跨章一致性问题，建议逐一核查"
        ),
    }
