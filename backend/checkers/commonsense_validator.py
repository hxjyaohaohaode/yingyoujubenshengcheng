import logging
import re
from collections import defaultdict

logger = logging.getLogger(__name__)

COMMONSENSE_RULES = [
    {
        "id": "time_human",
        "pattern": r"(\d+)(点|时|:)\s*(出发|到达|完成|开始).*?(\d+)(点|时|:)",
        "check": lambda m: abs(int(m.group(1)) - int(m.group(4))) <= 24,
        "description": "时间跨度检查",
    },
    {
        "id": "wound_recovery",
        "pattern": r"(受伤|骨折|中箭|刀伤|枪伤)[^。]{0,50}(恢复|痊愈|康复|好了|没事了)",
        "check": lambda m: False,
        "description": "重伤后短时间恢复",
        "always_flag": True,
    },
    {
        "id": "death_return",
        "pattern": r"(死亡|去世|牺牲|阵亡|死了)[^。]{0,100}(复活|回来|出现|回来了|没死|还活着)",
        "check": lambda m: False,
        "description": "死亡后无解释复活",
        "always_flag": True,
    },
    {
        "id": "pregnancy_timeline",
        "pattern": r"(怀孕|有孕|怀了|有喜)[^。]{0,50}(第二天|第二天早上|次日|几天后)[^。]{0,30}(生了|分娩|生产|出生|诞下)",
        "check": lambda m: False,
        "description": "怀孕时间线异常",
        "always_flag": True,
    },
    {
        "id": "distance_travel",
        "pattern": r"(千里|万里|数千[里公里]|万里之遥)[^。]{0,30}(片刻|须臾|转眼|瞬间|一眨眼|立即|马上|很快)",
        "check": lambda m: False,
        "description": "超远距离瞬间到达",
        "always_flag": True,
    },
    {
        "id": "memory_gap",
        "pattern": r"(失忆|忘了|不记得|记不起)[^。]{0,50}(却记得|偏偏记得|唯独记得|清楚记得|记得很清楚)",
        "check": lambda m: False,
        "description": "选择性失忆矛盾",
        "always_flag": True,
    },
    {
        "id": "age_contradiction",
        "pattern": r"(\d+)\s*岁[^。]{0,100}(\d+)\s*岁",
        "check": lambda m: int(m.group(1)) == int(m.group(2)),
        "description": "同一场景年龄矛盾",
    },
    {
        "id": "weather_contradiction",
        "pattern": r"(晴天|太阳|阳光|烈日|大太阳)[^。]{0,50}(下雨|暴雨|倾盆大雨|淋湿)",
        "check": lambda m: False,
        "description": "晴雨矛盾",
        "always_flag": True,
    },
    {
        "id": "money_unrealistic",
        "pattern": r"(一两|一文|几个铜板|几文钱)[^。]{0,30}(买了|买下|买了)了[^。]{0,20}(宅子|庄园|府邸|酒楼|客栈)",
        "check": lambda m: False,
        "description": "极度不合理的价格",
        "always_flag": True,
    },
]

ROLE_BEHAVIOR_RULES = {
    "医生": {
        "must_know": ["伤势", "病情", "药", "治疗", "诊断"],
        "must_not": ["杀人", "下毒", "故意伤害"],
    },
    "教师": {
        "must_know": ["教书", "学生", "知识", "道理"],
        "must_not": ["文盲行为", "不学无术"],
    },
    "军人": {
        "must_know": ["纪律", "命令", "服从", "战斗"],
        "must_not": ["临阵脱逃", "贪生怕死"],
    },
}


def check_commonsense(
    scenes: list[dict],
    characters: list[dict],
) -> dict:
    violations = []
    role_violations = []

    for i, scene in enumerate(scenes):
        narration = scene.get("narration", "") or ""
        scene_code = scene.get("scene_code", f"S-{i}")

        for rule in COMMONSENSE_RULES:
            for match in re.finditer(rule["pattern"], narration):
                violation = False
                if rule.get("always_flag"):
                    violation = True
                elif rule.get("check"):
                    try:
                        violation = rule["check"](match)
                    except Exception:
                        continue

                if violation:
                    violations.append({
                        "rule": rule["id"],
                        "description": rule["description"],
                        "scene": scene_code,
                        "snippet": narration[max(0, match.start() - 20):match.end() + 20],
                    })

    for char in characters:
        role_type = char.get("role_type", "")
        if role_type in ROLE_BEHAVIOR_RULES:
            rules = ROLE_BEHAVIOR_RULES[role_type]
            char_name = char.get("name", "?")

            for scene in scenes:
                narration = scene.get("narration", "") or ""
                scene_code = scene.get("scene_code", "?")

                for must_not in rules["must_not"]:
                    if must_not in narration and char_name in narration:
                        role_violations.append(
                            f"[{char_name}·{role_type}] {scene_code}: 出现不匹配行为'{must_not}'"
                        )

    total_violations = len(violations) + len(role_violations)
    pass_check = total_violations <= max(len(scenes) * 0.05, 2)

    return {
        "pass": pass_check,
        "commonsense_violations": violations,
        "role_behavior_violations": role_violations,
        "total_violations": total_violations,
        "suggestion": (
            "常识合规检查通过" if pass_check
            else f"发现{total_violations}处常识/角色行为问题，建议逐一核实"
        ),
    }
