import logging
import re
from collections import defaultdict

logger = logging.getLogger(__name__)

WOW_MOMENT_INDICATORS = [
    (r"反转|逆转|出乎意料|没想到|竟然|居然是|原来是", "情节反转", 3),
    (r"真相.*(揭示|大白|浮出)|原来如此|原来.*是", "真相揭示", 3),
    (r"牺牲|舍身|赴死|诀别|永别", "牺牲高潮", 2),
    (r"重逢|久别.*重逢|终于.*见到", "重逢爽点", 2),
    (r"突破|晋级|觉醒|开悟|突破瓶颈", "实力突破", 2),
    (r"告白|表白|倾心|动情|说出.*心意", "情感高潮", 2),
    (r"绝地.*(反击|反杀|翻盘)|逆风翻盘", "逆袭爽点", 3),
    (r"身份.*(揭晓|暴露|公开)|原来.*身份", "身份揭晓", 3),
    (r"复仇.*成功|大仇.*得报|了结恩怨", "复仇爽点", 2),
    (r"获得.*(宝物|秘籍|传承|认可)", "获得奖励", 1),
]

CHAPTER_HOOK_PATTERNS = [
    (r"(突然|这时|正在此时|忽然间|猛地)", "突发事件钩子"),
    (r"(不好|糟糕|危险|小心|快跑)", "危机预警钩子"),
    (r"(到底.*什么|究竟|怎么会|难道说)", "悬念钩子"),
    (r"(于是.*出发|决定.*前往|踏上.*旅程)", "启程钩子"),
]


def check_satisfaction_density(
    scenes: list[dict],
    target_beats_per_chapter: float = 2.5,
) -> dict:
    chapter_scores = defaultdict(lambda: {
        "total_score": 0,
        "scenes": 0,
        "events": [],
         "hooks": [],
    })

    total_wow_score = 0
    wow_events = []
    hook_events = []

    for i, scene in enumerate(scenes):
        narration = scene.get("narration", "") or ""
        scene_code = scene.get("scene_code", f"S-{i}")
        chapter_id = scene.get("chapter_id", "unknown")

        for pattern, event_type, score in WOW_MOMENT_INDICATORS:
            matches = re.findall(pattern, narration)
            if matches:
                total_wow_score += score * len(matches)
                wow_events.append({
                    "scene": scene_code,
                    "type": event_type,
                    "score": score * len(matches),
                })
                chapter_scores[chapter_id]["total_score"] += score * len(matches)
                chapter_scores[chapter_id]["events"].append(event_type)

        if scene.get("is_wow_moment"):
            wow_type = scene.get("wow_type", "设计哇塞时刻")
            total_wow_score += 4
            wow_events.append({
                "scene": scene_code,
                "type": f"[设计] {wow_type}",
                "score": 4,
            })
            chapter_scores[chapter_id]["total_score"] += 4
            chapter_scores[chapter_id]["events"].append(wow_type)

        for pattern, hook_type in CHAPTER_HOOK_PATTERNS:
            if re.search(pattern, narration):
                hook_events.append({
                    "scene": scene_code,
                    "type": hook_type,
                })
                chapter_scores[chapter_id]["hooks"].append(hook_type)

        chapter_scores[chapter_id]["scenes"] += 1

    num_chapters = len(chapter_scores)
    if num_chapters == 0:
        num_chapters = 1

    avg_wow_per_chapter = round(total_wow_score / num_chapters, 2)
    chapter_details = {}
    weak_chapters = []

    for ch_id, data in chapter_scores.items():
        ch_score = data["total_score"]
        ch_label = str(ch_id)[:8]
        chapter_details[ch_label] = {
            "score": ch_score,
            "events": data["events"][:5],
            "hooks": data["hooks"][:3],
            "scenes": data["scenes"],
        }
        if ch_score < target_beats_per_chapter:
            weak_chapters.append(f"章节{ch_label}(爽点分{ch_score})")

    pass_check = avg_wow_per_chapter >= target_beats_per_chapter

    return {
        "pass": pass_check,
        "total_wow_score": total_wow_score,
        "avg_wow_per_chapter": avg_wow_per_chapter,
        "target_beats_per_chapter": target_beats_per_chapter,
        "wow_events": wow_events[-20:],
        "hook_events": hook_events[-20:],
        "chapter_details": chapter_details,
        "weak_chapters": weak_chapters,
        "suggestion": (
            f"爽点密度良好（每章{avg_wow_per_chapter}分）" if pass_check
            else f"爽点密度不足（每章{avg_wow_per_chapter}分，目标≥{target_beats_per_chapter}），{len(weak_chapters)}个章节偏弱"
        ),
    }
