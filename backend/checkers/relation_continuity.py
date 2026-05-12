"""
关系值连续性检查器 - 检查角色间信任值变化的合理性。
"""

from typing import Any, Dict, List, Tuple

MAX_TRUST_DELTA = 30
TRUST_MIN = 0
TRUST_MAX = 100


def _make_key(a_id: str, b_id: str) -> Tuple[str, str]:
    """生成规范化的关系键（字典序）。"""
    return (a_id, b_id) if a_id < b_id else (b_id, a_id)


def check_relation_continuity(
    interactions: List[Dict[str, Any]],
    current_relations: Dict[Tuple[str, str], float]
) -> dict:
    """
    检查角色间互动对信任值的影响是否合理。

    Args:
        interactions: 互动列表，每个元素为 {char_a_id, char_b_id, trust_delta}，
                      可选 major_event 布尔字段。
        current_relations: 当前关系信任值，key为 (a_id, b_id) 元组，
                           value为信任值（0-100）。

    Returns:
        {"pass": bool, "violations": list[str]}
    """
    violations: List[str] = []
    projected: Dict[Tuple[str, str], float] = dict(current_relations)

    for idx, interaction in enumerate(interactions):
        a_id = interaction.get("char_a_id")
        b_id = interaction.get("char_b_id")
        trust_delta = interaction.get("trust_delta")
        is_major = interaction.get("major_event", False)

        if a_id is None or b_id is None:
            violations.append(f"互动 #{idx}: 缺少 char_a_id 或 char_b_id")
            continue

        if trust_delta is None:
            violations.append(f"互动 #{idx}: 缺少 trust_delta")
            continue

        if not is_major and abs(trust_delta) > MAX_TRUST_DELTA:
            violations.append(
                f"互动 #{idx} ({a_id} ↔ {b_id}): "
                f"信任变化 trust_delta={trust_delta}，超出最大允许值 "
                f"±{MAX_TRUST_DELTA}，且未标记为 major_event"
            )

        key = _make_key(a_id, b_id)
        current = projected.get(key, 50.0)
        new_value = current + trust_delta

        if new_value < TRUST_MIN or new_value > TRUST_MAX:
            violations.append(
                f"互动 #{idx} ({a_id} ↔ {b_id}): "
                f"信任值将从 {current} 变为 {new_value}，"
                f"超出允许范围 [{TRUST_MIN}, {TRUST_MAX}]"
            )
        else:
            projected[key] = new_value

    return {
        "pass": len(violations) == 0,
        "violations": violations,
    }
