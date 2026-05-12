"""
状态一致性检查器 - 检查场景草稿与Layer 1状态之间的一致性。
"""

from typing import Any, Dict, List


def check_state_consistency(
    scene_roles: List[Dict[str, Any]],
    layer1_state: Dict[str, Dict[str, Any]]
) -> dict:
    """
    检查场景角色状态与Layer 1全局状态的一致性。

    Args:
        scene_roles: 场景中的角色列表，每个角色为dict，包含:
                     id, location, emotion_level, known_info_keys。
        layer1_state: Layer 1全局状态，key为role_id，value为角色当前状态dict，
                      包含 location, emotion_level, known_info（集合或列表）。

    Returns:
        {"pass": bool, "failures": list[str]}
    """
    failures: List[str] = []

    for role in scene_roles:
        role_id = role.get("id")
        if role_id is None:
            failures.append("角色缺少id字段")
            continue

        if role_id not in layer1_state:
            failures.append(f"角色 {role_id} 在Layer 1状态中不存在")
            continue

        state = layer1_state[role_id]

        role_location = role.get("location")
        state_location = state.get("location")
        if (
            role_location is not None
            and state_location is not None
            and role_location != state_location
        ):
            if not role.get("_travel_marker", False):
                failures.append(
                    f"角色 {role_id} 位置不一致: "
                    f"场景中={role_location}, Layer 1={state_location}，"
                    f"且场景中无旅行标记"
                )

        role_emotion = role.get("emotion_level")
        state_emotion = state.get("emotion_level")
        if (
            role_emotion is not None
            and state_emotion is not None
            and abs(role_emotion - state_emotion) > 3
        ):
            if not role.get("_emotional_trigger", False):
                failures.append(
                    f"角色 {role_id} 情绪跃变过大: "
                    f"场景中={role_emotion}, Layer 1={state_emotion}, "
                    f"差值={abs(role_emotion - state_emotion)}，"
                    f"且场景中无情绪触发标记"
                )

        role_known = set(role.get("known_info_keys") or [])
        state_known = set(state.get("known_info") or [])

        invalid_info = role_known - state_known
        if invalid_info:
            failures.append(
                f"角色 {role_id} 引用了未确认已知的信息: "
                f"{sorted(invalid_info)}"
            )

    return {
        "pass": len(failures) == 0,
        "failures": failures,
    }
