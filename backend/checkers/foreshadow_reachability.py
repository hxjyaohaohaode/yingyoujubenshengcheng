"""
伏笔可达性检查器 - 使用BFS验证伏笔从埋设场景到揭示场景之间是否存在路径。
"""

from collections import deque
from typing import Any, Dict, List


def check_foreshadow_reachability(
    foreshadows: List[Dict[str, Any]],
    scene_graph: Dict[str, List[str]]
) -> dict:
    """
    BFS检查每个伏笔从plant_scene到reveal_scene是否存在路径。

    Args:
        foreshadows: 伏笔列表，每个元素为 {id, plant_scene_id, reveal_scene_id}。
        scene_graph: 场景图，邻接表格式: scene_id -> [reachable_scene_ids]。

    Returns:
        {"pass": bool, "broken_foreshadows": list[str]}
    """
    broken_foreshadows: List[str] = []

    for fs in foreshadows:
        fs_id = fs.get("id")
        plant = fs.get("plant_scene_id")
        reveal = fs.get("reveal_scene_id")

        if fs_id is None or plant is None or reveal is None:
            if fs_id is not None:
                broken_foreshadows.append(fs_id)
            continue

        if plant not in scene_graph or reveal not in scene_graph:
            broken_foreshadows.append(fs_id)
            continue

        if plant == reveal:
            continue

        visited: set = {plant}
        queue: deque = deque([plant])
        reachable = False

        while queue:
            current = queue.popleft()
            if current == reveal:
                reachable = True
                break
            for neighbor in scene_graph.get(current, []):
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append(neighbor)

        if not reachable:
            broken_foreshadows.append(fs_id)

    return {
        "pass": len(broken_foreshadows) == 0,
        "broken_foreshadows": broken_foreshadows,
    }
