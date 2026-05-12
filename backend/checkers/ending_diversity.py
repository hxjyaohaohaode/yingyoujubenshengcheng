import logging
import re
from collections import defaultdict

logger = logging.getLogger(__name__)

ENDING_PATTERNS = {
    "happy": [r"幸福.*生活|从此.*幸福|皆大欢喜|团圆|美满"],
    "bittersweet": [r"虽然.*但是|遗憾|可惜|如果|若是当初|留下一丝"],
    "tragic": [r"悲剧|陨落|逝去|永别|无法挽回|一切.*结束|化为.*灰烬"],
    "open_ended": [r"未来.*如何|无人.*知晓|留给.*想象|未完.*待续|故事.*仍在"],
    "twist_ending": [r"原来.*真相|一切都是|最后的.*反转|最大的.*秘密|所有.*都是.*骗局"],
    "heroic_sacrifice": [r"牺牲.*自己|舍身|与.*同归于尽|用.*生命|以死"],
    "redemption": [r"赎罪|改过|回头|放下屠刀|幡然.*醒悟|重新.*做人"],
    "cyclical": [r"一切都.*回到|原点|轮回|循环|又.*重新.*开始|仿佛是.*开始"],
}


def check_ending_diversity(
    scenes: list[dict],
    endings: list[dict] | None = None,
) -> dict:
    last_n_scenes = min(5, max(3, len(scenes)))
    ending_scenes = scenes[-last_n_scenes:] if scenes else []

    ending_type_hits = defaultdict(list)
    all_ending_text = " ".join([
        s.get("narration", "") or "" for s in ending_scenes
    ])

    for ending_type, patterns in ENDING_PATTERNS.items():
        for pattern in patterns:
            matches = re.finditer(pattern, all_ending_text)
            for match in matches:
                snippet = all_ending_text[
                    max(0, match.start() - 15):match.end() + 15
                ]
                ending_type_hits[ending_type].append(snippet)

    detected_types = list(ending_type_hits.keys())
    type_count = len(detected_types)

    endings_data = endings or []

    valid_endings = 0
    accessible_endings = 0
    ending_labels = []

    for ending in endings_data:
        if not isinstance(ending, dict):
            continue
        valid_endings += 1
        if ending.get("reachable", True):
            accessible_endings += 1
        ending_labels.append(ending.get("label", ending.get("name", "")))

    unique_labels = len(set(ending_labels)) if ending_labels else 0

    pass_check = type_count >= 2

    issues = []
    if type_count < 1:
        issues.append("未检测到明显的结局模式")
    if valid_endings > 0 and accessible_endings < valid_endings:
        issues.append(f"{valid_endings - accessible_endings}个结局不可达")
    if unique_labels > 0 and unique_labels < 2:
        issues.append("结局缺乏多样性（只有一个独特标签）")

    return {
        "pass": pass_check,
        "detected_ending_types": detected_types,
        "type_count": type_count,
        "ending_type_details": {
            t: snippets[:3] for t, snippets in ending_type_hits.items()
        },
        "ending_count": valid_endings,
        "accessible_endings": accessible_endings,
        "unique_labels": unique_labels,
        "issues": issues,
        "suggestion": (
            f"结局多样性良好（检测到{type_count}种类型）" if pass_check
            else "结局缺乏多样性，建议增加不同类型的结局变体"
        ),
    }
