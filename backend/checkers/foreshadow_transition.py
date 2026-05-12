"""
伏笔状态转换验证器 - 验证伏笔操作的状态转换是否合法。
"""

from typing import Any, Dict, List

LEGAL_TRANSITIONS: Dict[str, List[str]] = {
    "design": ["plant"],
    "plant": ["reinforce", "reveal"],
    "reinforce": ["reinforce", "reveal"],
    "reveal": ["verify"],
}


def check_foreshadow_transition(
    foreshadow_ops: List[Dict[str, Any]],
    current_states: Dict[str, str]
) -> dict:
    """
    验证伏笔操作的状态转换是否合法。

    Args:
        foreshadow_ops: 伏笔操作列表，每个元素为 {fs_id, op}，
                        op 取值为 plant|reinforce|reveal。
        current_states: 当前伏笔状态，key为fs_id，value为当前状态。
                        允许为 "design" 作为初始状态。

    Returns:
        {"pass": bool, "illegal_ops": list[dict]}
    """
    illegal_ops: List[Dict[str, Any]] = []

    for op_item in foreshadow_ops:
        fs_id = op_item.get("fs_id")
        op = op_item.get("op")

        if fs_id is None or op is None:
            illegal_ops.append({
                "fs_id": fs_id,
                "op": op,
                "reason": "缺少 fs_id 或 op 字段",
            })
            continue

        if op not in {"plant", "reinforce", "reveal"}:
            illegal_ops.append({
                "fs_id": fs_id,
                "op": op,
                "reason": f"未知操作类型: {op}",
            })
            continue

        current_status = current_states.get(fs_id, "design")

        if current_status not in LEGAL_TRANSITIONS:
            illegal_ops.append({
                "fs_id": fs_id,
                "op": op,
                "current_status": current_status,
                "reason": f"当前状态 {current_status} 未定义合法转换",
            })
            continue

        allowed_next = LEGAL_TRANSITIONS[current_status]

        if op not in allowed_next:
            illegal_ops.append({
                "fs_id": fs_id,
                "op": op,
                "current_status": current_status,
                "reason": (
                    f"非法转换: {current_status} -> {op}，"
                    f"仅允许 -> {allowed_next}"
                ),
            })

    return {
        "pass": len(illegal_ops) == 0,
        "illegal_ops": illegal_ops,
    }
