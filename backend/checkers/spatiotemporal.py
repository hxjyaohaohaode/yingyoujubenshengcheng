"""
时空连续性检查器 - 检查场景之间的时空连续性。
"""

from datetime import datetime, timedelta
from typing import Dict, List

DEFAULT_TRAVEL_TIME_MINUTES = 30

TRAVEL_TIME: Dict[str, Dict[str, int]] = {
    "长安城": {"洛阳城": 120, "蜀山": 240, "东海": 360, "西域": 480},
    "洛阳城": {"长安城": 120, "蜀山": 180, "东海": 300, "西域": 360},
    "蜀山": {"长安城": 240, "洛阳城": 180, "东海": 480, "西域": 600},
    "东海": {"长安城": 360, "洛阳城": 300, "蜀山": 480, "西域": 720},
    "西域": {"长安城": 480, "洛阳城": 360, "蜀山": 600, "东海": 720},
    "天宫": {"长安城": 60, "洛阳城": 60, "蜀山": 90, "东海": 120, "西域": 180},
}


def _parse_time(time_str: str) -> datetime:
    """解析时间字符串，支持 HH:MM 和 YYYY-MM-DD HH:MM 格式。"""
    time_str = time_str.strip()
    try:
        return datetime.strptime(time_str, "%Y-%m-%d %H:%M")
    except ValueError:
        pass
    try:
        return datetime.strptime(time_str, "%H:%M")
    except ValueError:
        raise ValueError(f"无法解析时间字符串: {time_str}")


def check_spatiotemporal(
    prev_scene_end_time: str,
    prev_scene_location: str,
    new_scene_start_time: str,
    new_scene_location: str,
) -> dict:
    """
    检查场景切换时的时空连续性。

    Args:
        prev_scene_end_time: 上一个场景的结束时间。
        prev_scene_location: 上一个场景的地点名称。
        new_scene_start_time: 新场景的开始时间。
        new_scene_location: 新场景的地点名称。

    Returns:
        {"pass": bool, "issues": list[str]}
    """
    issues: List[str] = []

    try:
        prev_time = _parse_time(prev_scene_end_time)
    except ValueError as e:
        return {"pass": False, "issues": [f"上一个场景时间解析失败: {e}"]}

    try:
        new_time = _parse_time(new_scene_start_time)
    except ValueError as e:
        return {"pass": False, "issues": [f"新场景时间解析失败: {e}"]}

    if new_time < prev_time:
        issues.append(
            f"时间倒退: 从 {prev_scene_end_time} 回到 {new_scene_start_time}"
        )
        return {"pass": False, "issues": issues}

    time_diff = new_time - prev_time
    time_diff_minutes = time_diff.total_seconds() / 60

    if prev_scene_location != new_scene_location:
        min_travel = (
            TRAVEL_TIME.get(prev_scene_location, {}).get(new_scene_location)
            or TRAVEL_TIME.get(new_scene_location, {}).get(prev_scene_location)
            or DEFAULT_TRAVEL_TIME_MINUTES
        )

        if time_diff_minutes < min_travel:
            issues.append(
                f"地点从 {prev_scene_location} 切换到 {new_scene_location}，"
                f"最小旅行时间需 {min_travel} 分钟，实际仅 {time_diff_minutes:.0f} 分钟"
            )

    return {
        "pass": len(issues) == 0,
        "issues": issues,
    }
