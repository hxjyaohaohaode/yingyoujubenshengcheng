import logging
import re
from collections import defaultdict

logger = logging.getLogger(__name__)

CONFLICT_PATTERNS = {
    "escalation": [
        (r"冲突.*升级|矛盾.*加剧|局势.*恶化|危机.*加深", "冲突升级"),
        (r"更(大|严重|危险|紧急)的", "程度加深"),
        (r"不仅.*而且|不但.*反而|更加", "复合冲突"),
    ],
    "twist": [
        (r"反转|逆转|出乎意料|没想到|竟然|居然|原来是", "情节反转"),
        (r"真相.*(是|为|在于)|原来如此", "真相揭示"),
        (r"这一切.*(都是|其实是)", "认知颠覆"),
    ],
    "pause": [
        (r"暂时.*(平静|安宁|休息)|喘息|片刻的", "冲突暂缓"),
    ],
    "resolution": [
        (r"终于.*(解决|结束|了结)|尘埃落定|水落石出", "冲突解决"),
    ],
    "dropped": [],
}

CONFLICT_TRACKING_KEYWORDS = [
    "矛盾", "冲突", "恩怨", "仇恨", "对立", "争夺", "竞争",
    "复仇", "对抗", "斗争", "较量", "角逐", "博弈", "暗斗",
]


def check_conflict_evolution(
    scenes: list[dict],
    core_contradiction: str = "",
) -> dict:
    conflict_events = []
    conflict_references = defaultdict(int)
    total_conflict_mentions = 0
    chapter_mentions = defaultdict(int)

    for i, scene in enumerate(scenes):
        narration = scene.get("narration", "") or ""
        scene_code = scene.get("scene_code", f"S-{i}")
        chapter_id = scene.get("chapter_id", "unknown")

        scene_events = []
        for category, patterns in CONFLICT_PATTERNS.items():
            if category == "dropped":
                continue
            for pattern, label in patterns:
                matches = re.findall(pattern, narration)
                for _ in matches:
                    scene_events.append({"category": category, "label": label, "scene": scene_code})

        for kw in CONFLICT_TRACKING_KEYWORDS:
            mentions = narration.count(kw)
            total_conflict_mentions += mentions
            chapter_mentions[chapter_id] += mentions
            conflict_references[scene_code] += mentions

        if scene_events:
            conflict_events.append({
                "scene": scene_code,
                "events": scene_events,
            })

    if not scenes:
        return {
            "pass": True,
            "total_conflict_mentions": 0,
            "evolution_events": [],
            "dropped_warning": False,
            "flat_warning": False,
            "escalation_count": 0,
            "twist_count": 0,
            "resolution_count": 0,
            "suggestion": "暂无场景数据",
        }

    escalation_count = sum(
        1 for e in conflict_events for ev in e["events"] if ev["category"] == "escalation"
    )
    twist_count = sum(
        1 for e in conflict_events for ev in e["events"] if ev["category"] == "twist"
    )
    resolution_count = sum(
        1 for e in conflict_events for ev in e["events"] if ev["category"] == "resolution"
    )

    chapter_keys = list(chapter_mentions.keys())
    consecutive_empty = 0
    dropped_warning = False
    flat_warning = False

    for ch_key in chapter_keys:
        if chapter_mentions[ch_key] == 0:
            consecutive_empty += 1
        else:
            consecutive_empty = 0

        if consecutive_empty >= 3:
            dropped_warning = True
            break

    if len(scenes) > 10 and total_conflict_mentions < len(scenes) * 0.5:
        dropped_warning = True

    if len(scenes) > 5 and escalation_count == 0 and twist_count == 0 and total_conflict_mentions > 0:
        flat_warning = True

    evolution_score = 0
    evolution_score += escalation_count * 2
    evolution_score += twist_count * 3
    evolution_score += resolution_count * 1

    evolution_active = escalation_count > 0 or twist_count > 0
    pass_check = (
        not dropped_warning
        and not flat_warning
        and evolution_active
        and total_conflict_mentions >= len(scenes) * 0.3
    )

    return {
        "pass": pass_check,
        "total_conflict_mentions": total_conflict_mentions,
        "conflict_density": round(total_conflict_mentions / max(len(scenes), 1), 2),
        "evolution_events": conflict_events[-10:],
        "dropped_warning": dropped_warning,
        "flat_warning": flat_warning,
        "escalation_count": escalation_count,
        "twist_count": twist_count,
        "resolution_count": resolution_count,
        "evolution_score": evolution_score,
        "suggestion": (
            "冲突演进良好" if pass_check
            else (
                "冲突疑似被遗忘，多章未提及核心冲突" if dropped_warning
                else "冲突缺乏升级/转折，节奏平缓" if flat_warning
                else "冲突密度偏低，建议加强矛盾刻画"
            )
        ),
    }
