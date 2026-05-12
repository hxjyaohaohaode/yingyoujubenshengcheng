import logging
import re
from collections import defaultdict

logger = logging.getLogger(__name__)

PLOT_DRIVER_KEYWORDS = [
    "发现", "揭示", "决定", "出发", "到达", "对抗", "战斗", "逃跑",
    "追捕", "谈判", "交易", "背叛", "联盟", "分离", "重逢",
    "突破", "封锁", "潜入", "逃脱", "拯救", "牺牲", "选择",
    "拒绝", "接受", "质问", "承认", "坦白", "隐瞒", "策划",
    "实施", "破坏", "摧毁", "建立", "废除", "宣布", "命令",
]

STATIC_KEYWORDS = [
    "看着", "望着", "望着窗外", "坐着", "躺着", "等待", "沉默",
    "沉思", "叹气", "叹息", "喝酒", "喝茶", "漫步", "散步",
    "回忆", "回想", "想起", "记得", "想起过去",
]

REDUNDANT_PATTERNS = [
    (r"他(再次|又一次|不禁)想起", "重复回忆"),
    (r"正如(之前|此前|前面)所(说|提到|描述)的", "前文复述"),
    (r"(不由得|不禁|忍不住)(又|再次)想起", "重复心理活动"),
    (r"她(依然|仍然|还是)(那么|那样)的", "重复外貌描写"),
]

WATER_CONTENT_PATTERNS = [
    (r"(风|雨|雪|雾|云|星|月|日|天)[^，。]{0,10}(很|非常|极其|格外)", "冗余环境描写"),
    (r"([^，。]{0,5})、(?!还有)([^，。]{0,5})、(?!还有)([^，。]{0,5})、", "过度排比堆砌"),
    (r"(仿佛|似乎|好像|如同)[^，。]{0,30}(一般|似的|一样)", "频繁比喻"),
]


def check_narrative_efficiency(
    scenes: list[dict],
    target_word_count: int = 0,
    min_beats_per_1000: float = 3.0,
    max_static_ratio: float = 0.30,
) -> dict:
    total_words = 0
    driver_beats = 0
    static_beats = 0
    redundant_beats = 0
    water_flags = []
    per_scene_stats = []
    total_dialogue_words = 0

    for i, scene in enumerate(scenes):
        narration = scene.get("narration", "") or ""
        dialogue = scene.get("dialogue", []) or []
        scene_code = scene.get("scene_code", f"S-{i}")

        scene_words = len(narration)
        total_words += scene_words

        dialogue_word_count = 0
        if isinstance(dialogue, list):
            for d in dialogue:
                if isinstance(d, dict):
                    dialogue_word_count += len(d.get("text", ""))
        total_dialogue_words += dialogue_word_count

        driver_count = 0
        static_count = 0
        redundant_count = 0

        for kw in PLOT_DRIVER_KEYWORDS:
            driver_count += narration.count(kw)

        for kw in STATIC_KEYWORDS:
            static_count += narration.count(kw)

        for pattern, _ in REDUNDANT_PATTERNS:
            redundant_count += len(re.findall(pattern, narration))

        for pattern, desc in WATER_CONTENT_PATTERNS:
            matches = re.findall(pattern, narration)
            if matches:
                water_flags.append(f"[{scene_code}] {desc}: 发现{len(matches)}处")

        if scene_words > 0 and static_count > driver_count:
            water_flags.append(
                f"[{scene_code}] 静态描写({static_count})多于驱动({driver_count})，节奏偏慢"
            )

        if scene_words > 2000 and driver_count < 3:
            water_flags.append(
                f"[{scene_code}] 长场景({scene_words}字)但驱动事件仅{driver_count}个，疑似水文"
            )

        driver_beats += driver_count
        static_beats += static_count
        redundant_beats += redundant_count

        per_scene_stats.append({
            "scene": scene_code,
            "words": scene_words,
            "driver_beats": driver_count,
            "static_beats": static_count,
            "redundant_beats": redundant_count,
            "efficiency": round(driver_count / max(scene_words, 1) * 1000, 2),
        })

    beats_per_1000 = round(driver_beats / max(total_words, 1) * 1000, 2)
    static_ratio = round(static_beats / max(driver_beats + static_beats, 1), 2)
    dialogue_ratio = round(total_dialogue_words / max(total_words, 1), 2)

    low_efficiency_scenes = [s["scene"] for s in per_scene_stats if s["efficiency"] < 2.0]
    high_static_scenes = [
        s["scene"] for s in per_scene_stats
        if s["static_beats"] > s["driver_beats"] and s["words"] > 500
    ]

    beats_pass = beats_per_1000 >= min_beats_per_1000
    static_pass = static_ratio <= max_static_ratio
    pass_check = beats_pass and static_pass and len(water_flags) <= max(len(scenes) * 0.15, 3)

    return {
        "pass": pass_check,
        "total_words": total_words,
        "dialogue_ratio": dialogue_ratio,
        "driver_beats": driver_beats,
        "static_beats": static_beats,
        "redundant_beats": redundant_beats,
        "beats_per_1000": beats_per_1000,
        "min_beats_target": min_beats_per_1000,
        "static_ratio": static_ratio,
        "max_static_target": max_static_ratio,
        "water_flags": water_flags,
        "low_efficiency_scenes": low_efficiency_scenes,
        "high_static_scenes": high_static_scenes,
        "per_scene_stats": per_scene_stats,
        "suggestion": (
            f"叙事效率良好（{beats_per_1000}节拍/千字）" if pass_check
            else f"叙事效率偏低（{beats_per_1000}节拍/千字），静态占比{static_ratio*100:.0f}%，建议精简{len(water_flags)}处水文"
        ),
    }
