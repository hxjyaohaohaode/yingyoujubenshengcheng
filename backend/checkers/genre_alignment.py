import logging
import re
from collections import defaultdict

logger = logging.getLogger(__name__)

GENRE_PROFILES = {
    "悬疑": {
        "must_elements": ["线索", "误导", "真相", "嫌疑人", "推理"],
        "should_elements": ["反转", "不在场证明", "红鲱鱼", "时间线"],
        "forbidden_elements": ["无条件和解", "无缘无故的坦白"],
        "tone_keywords": ["紧张", "压迫", "阴暗", "不安", "怀疑"],
        "pacing": "快节奏，每3-5个场景应有新线索",
        "ending_expectation": "真相揭示应在最后20%篇幅内完成",
    },
    "爱情": {
        "must_elements": ["相遇", "误解", "分离", "选择", "告白"],
        "should_elements": ["竞争者", "成长", "牺牲", "浪漫瞬间"],
        "forbidden_elements": ["无感情基础的婚姻", "单方面牺牲无回应"],
        "tone_keywords": ["心动", "温暖", "纠结", "甜蜜", "感伤"],
        "pacing": "中速，感情线应为主轴占比≥60%",
        "ending_expectation": "情感关系应有明确结局",
    },
    "武侠": {
        "must_elements": ["武功", "江湖", "门派", "侠义", "恩怨"],
        "should_elements": ["江湖", "复仇", "成长", "秘籍", "比试"],
        "forbidden_elements": ["纯科技解决", "现代化思维过度"],
        "tone_keywords": ["豪迈", "苍凉", "热血", "洒脱", "悲壮"],
        "pacing": "高低起伏，动作场景占比≥30%",
        "ending_expectation": "武功与心性双线成长应有收束",
    },
    "科幻": {
        "must_elements": ["科技", "未来", "设定", "伦理", "探索"],
        "should_elements": ["AI", "太空", "时间", "进化", "外星"],
        "forbidden_elements": ["违反自身设定的魔法", "无代价的黑科技"],
        "tone_keywords": ["理性", "宏大", "未知", "思辨", "冷峻"],
        "pacing": "前期设定铺垫30%，中期冲突50%，后期思辨20%",
        "ending_expectation": "科技设定应自洽闭环",
    },
    "奇幻": {
        "must_elements": ["魔法/异能", "世界构建", "种族", "冒险", "命运"],
        "should_elements": ["预言", "神器", "龙/神秘生物", "王国", "远征"],
        "forbidden_elements": ["无代价的魔法", "突兀的现代科技"],
        "tone_keywords": ["神秘", "宏大", "史诗", "惊奇", "敬畏"],
        "pacing": "逐步展开世界观，探索感贯穿始终",
        "ending_expectation": "世界命运应有交代",
    },
    "恐怖": {
        "must_elements": ["恐惧", "未知", "威胁", "孤立", "生存"],
        "should_elements": ["超自然", "心理恐惧", "封闭空间", "追逐"],
        "forbidden_elements": ["无代价的逃脱", "过度喜剧化解"],
        "tone_keywords": ["恐惧", "压抑", "绝望", "紧张", "阴森"],
        "pacing": "紧张感持续递增，每5-8场景一个恐怖爆发点",
        "ending_expectation": "恐惧源应有明确结局",
    },
    "历史": {
        "must_elements": ["时代背景", "真实事件", "社会结构", "人物命运"],
        "should_elements": ["权谋", "战争", "文化", "阶级", "变革"],
        "forbidden_elements": ["严重时代错位", "现代价值观强行植入"],
        "tone_keywords": ["厚重", "沧桑", "权谋", "悲壮", "命运"],
        "pacing": "节奏沉稳，历史进程驱动为主",
        "ending_expectation": "个人命运融入历史洪流",
    },
    "玄幻": {
        "must_elements": ["修炼体系", "境界突破", "奇遇", "宗门", "天才"],
        "should_elements": ["炼丹", "秘境", "试炼", "传承", "天骄"],
        "forbidden_elements": ["无代价变强", "机械化修炼"],
        "tone_keywords": ["热血", "逆袭", "霸气", "爽快", "宏大"],
        "pacing": "升级节奏明确，每10-15章一个大境界",
        "ending_expectation": "主角应有明确的实力巅峰",
    },
    "仙侠": {
        "must_elements": ["修真", "飞升", "道心", "法宝", "天道"],
        "should_elements": ["劫难", "机缘", "轮回", "斩妖除魔", "问道"],
        "forbidden_elements": ["无修行代价", "神通无限"],
        "tone_keywords": ["超脱", "逍遥", "执着", "因果", "天命"],
        "pacing": "前期修行30%，中期历练50%，后期证道20%",
        "ending_expectation": "道心圆满或超脱",
    },
    "推理": {
        "must_elements": ["案件", "证据", "推理", "动机", "真凶"],
        "should_elements": ["密室", "不在场证明", "误导", "侦探", "助手"],
        "forbidden_elements": ["无铺垫的凶手", "超自然破案（除非设定）"],
        "tone_keywords": ["冷静", "严密", "悬疑", "意外", "满足"],
        "pacing": "线索逐步释放，最终章集中推理",
        "ending_expectation": "真相揭示应有完整推理链",
    },
}


def check_genre_alignment(
    scenes: list[dict],
    genre: str = "",
    core_contradiction: str = "",
) -> dict:
    if not genre or genre not in GENRE_PROFILES:
        return {
            "pass": True,
            "genre": genre or "未设定",
            "detail": "体裁未设定或不在预设列表中，跳过检测",
            "must_element_coverage": 0,
            "tone_alignment": 0,
            "suggestion": "建议在创建项目时选择体裁以获得体裁对齐检测",
        }

    profile = GENRE_PROFILES[genre]
    all_text = " ".join(
        [s.get("narration", "") or "" for s in scenes]
    )

    must_hits = []
    must_misses = []
    for elem in profile["must_elements"]:
        if elem in all_text:
            must_hits.append(elem)
        else:
            must_misses.append(elem)

    should_hits = []
    for elem in profile["should_elements"]:
        if elem in all_text:
            should_hits.append(elem)

    tone_matches = 0
    for kw in profile["tone_keywords"]:
        if kw in all_text:
            tone_matches += 1

    forbidden_hits = []
    for elem in profile["forbidden_elements"]:
        if elem in all_text:
            forbidden_hits.append(elem)

    must_coverage = round(len(must_hits) / max(len(profile["must_elements"]), 1) * 100, 1)
    tone_alignment = round(tone_matches / max(len(profile["tone_keywords"]), 1) * 100, 1)

    total_scenes = len(scenes)
    pass_check = (
        must_coverage >= 60
        and tone_alignment >= 30
        and len(forbidden_hits) <= 1
        and total_scenes > 0
    )

    return {
        "pass": pass_check,
        "genre": genre,
        "must_hits": must_hits,
        "must_misses": must_misses,
        "must_element_coverage": must_coverage,
        "should_hits": should_hits,
        "tone_alignment": tone_alignment,
        "forbidden_hits": forbidden_hits,
        "pacing_guideline": profile["pacing"],
        "ending_guideline": profile["ending_expectation"],
        "suggestion": (
            f"体裁《{genre}》对齐良好（必须元素覆盖{must_coverage}%）" if pass_check
            else f"体裁《{genre}》对齐不足：缺少{must_misses}，存在禁忌元素{forbidden_hits}"
        ),
    }
