"""
创作 Agent: 场景撰写、对白生成、分支设计。

Skills:
  - scene_writer: 场景撰写（write.prose）
  - dialogue_writer: 对白生成（write.dialogue）
  - branch_designer: 分支设计（write.creative）
  - world_builder: 世界观构建（write.creative）
  - character_designer: 角色设计（write.creative）
  - outline_writer: 大纲撰写（write.outline）
"""

import json
from typing import Any, TypedDict
from collections.abc import Callable

from core.agent.base import BaseAgent, AgentTask, AgentResult, layer0_value
from core.agent.skill import Skill
from core.agent.registry import register_agent
from core.agent.prompts import SCENE_GEN_UPGRADED_STANDARDS


class _ThinkingModeRule(TypedDict):
    max_tokens: int
    temperature: float
    conditions: Callable[[dict], bool]


def parse_scene_draft(text: str) -> dict:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"narration": text, "dialogue": [], "actions": [], "foreshadow_ops": [], "choices": []}


def parse_dialogue(text: str) -> dict:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"dialogue": text}


def parse_outline(text: str) -> dict:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    import re
    m = re.search(r'```json\s*([\s\S]*?)\s*```', text)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            pass
    m = re.search(r'\[[\s\S]*\]', text)
    if m:
        try:
            result = json.loads(m.group(0))
            if isinstance(result, list):
                return {"chapters": result}
        except json.JSONDecodeError:
            pass
    m = re.search(r'\{[\s\S]*\}', text)
    if m:
        try:
            result = json.loads(m.group(0))
            if isinstance(result, dict):
                return result
        except json.JSONDecodeError:
            pass
    return {"outline": text}


SCENE_WRITER_SKILL = Skill()
SCENE_WRITER_SKILL.name = "scene_writer"
SCENE_WRITER_SKILL.intent = "write.prose"
SCENE_WRITER_SKILL.model = "ds-reasoner"

_CHINESE_WRITING_STANDARDS = """
【中文创意写作铁律】
1. **画面感三要素**：每个场景描述必须包含至少两种感官（光/味/声/触/温）
2. **动态叙述**：用动作推进剧情，禁止超过三句连续静态描写
3. **对白潜文本**：每句对白必须有"字面意思"与"真实意图"的落差（角色永远口是心非）
4. **节奏控制**：短句（<15字）制造紧张，长句（>30字）营造沉浸
5. **具象化**：抽象概念必须用具体物象承载（不写"悲伤"，写"手指抠进掌心"）
6. **叙事视角一致**：严格遵循指定的POV视角，不跳视角
7. **信息释放**：采用"冰山原则"，只写水面以上，水下留给读者/玩家推断
8. **中国网文黄金律**：每300字必须有新的信息增量（新动作/新对话/新发现）
"""

_INTERACTIVE_GAME_WRITING = """
【互动影游剧本特殊要求】
1. **代入感**：主角的行动必须有明确的选择空间（即使不写出来，也要让读者感受到"此处可分支"）
2. **道德灰度**：每个重大抉择必须有好/坏两面的后果，不能有完美答案
3. **NPC深度**：配角不能只是工具人，每个NPC有自己的小算盘
4. **信息不对等**：不同角色掌握不同信息片段，玩家需要通过探索拼凑真相
5. **情感锚点**：每3-5个场景必须有一个情感重场（角色关系发生质的改变）
6. **分支预埋**：重要对白末尾暗示另一种可能（"如果你当时选了..."的既视感）
7. **环境叙事**：场景本身应当传达故事信息（用场景说故事，不只用字说故事）
"""

SCENE_WRITER_SKILL.prompt_template = """你是专业剧本编剧。

## 世界观
{world_setting}

## 本章大纲
{chapter_outline}

## 本章角色
{chapter_characters}

## 伏笔任务
{foreshadow_tasks}

## 情感目标
{emotion_target}

## 目标字数
{target_word_count}字

{previous_scene_context}

{scene_position_info}

请撰写本场景的完整剧本内容。

【叙事连续性 — 强制约束】
1. **前序衔接**：本场景的开头必须自然承接前序场景的结尾——情绪、动作、对话、场景转换都必须连贯。
2. **场景完整性**：每个场景必须包含完整的叙事弧（引入→发展→转折→收尾），不能只写片段。
3. **角色一致性**：角色的语言风格、行为模式必须与角色设定完全一致。
4. **伏笔执行**：必须执行指定的伏笔任务（埋设/强化/回收），且执行方式必须自然融入剧情。

输出JSON格式:
{{
  "narration": "场景叙述文本（完整的场景描写，包含环境、动作、心理活动，200-800字）",
  "dialogue": [
    {{"speaker": "角色名", "line": "台词内容", "subtext": "潜台词（可选）", "emotion": "情绪标签"}},
    ...
  ],
  "actions": ["关键动作描述1", "关键动作描述2"],
  "foreshadow_ops": [
    {{"foreshadow_id": "伏笔ID", "op": "plant|reinforce|reveal", "method": "执行方式描述"}}
  ],
  "emotion_value": 0.0,
  "wow_moment": {{"type": "reversal|revelation|sacrifice|triumph|betrayal", "description": "哇塞时刻描述"}}或null,
  "scene_transition": "场景转换描述（如何过渡到下一场景）"
}}"""
SCENE_WRITER_SKILL.output_parser = parse_scene_draft

DIALOGUE_WRITER_SKILL = Skill()
DIALOGUE_WRITER_SKILL.name = "dialogue_writer"
DIALOGUE_WRITER_SKILL.intent = "write.dialogue"
DIALOGUE_WRITER_SKILL.model = "ds-reasoner"
DIALOGUE_WRITER_SKILL.prompt_template = """你是对白编剧专家。

## 角色设定
{character_info}

## 当前情感状态
{emotion_state}

## 对话对象关系
{relation_info}

## 场景目标
{scene_goal}

## 要求
- 对白要符合角色语言风格和口头禅
- 要有潜台词，不能直白
- 不同角色的说话方式要有区分度

请输出对白 JSON 数组:
[{{"char": "角色名", "text": "台词", "subtext": "潜台词"}}]"""
DIALOGUE_WRITER_SKILL.output_parser = parse_dialogue

BRANCH_DESIGNER_SKILL = Skill()
BRANCH_DESIGNER_SKILL.name = "branch_designer"
BRANCH_DESIGNER_SKILL.intent = "write.creative"
BRANCH_DESIGNER_SKILL.model = "ds-reasoner"
BRANCH_DESIGNER_SKILL.prompt_template = """你是互动叙事设计专家。

## 当前场景
{scene_summary}

## 角色状态
{character_states}

## 伏笔要求
{foreshadow_tasks}

## 分支约束
- 分支深度上限: {max_branch_depth}层
- 每选择最少: {min_branches}个分支
- 每选择最多: {max_branches}个分支
- 目标结局数: {target_ending_count}个

## 要求
设计 2-3 个选择分支:
- 不是对/错的选择，而是不同代价
- 影响延迟显现
- 不同选择揭示不同真相
- 设计 1 个隐藏选项（需要特定前置条件）
- 避免过度分叉导致分支爆炸，确保每个分支都有叙事价值

请输出选择节点 JSON 数组:
[{{"id": "A", "text": "选项文本", "consequence": "直接后果", "next_scene": "下一场景编号", "hidden": false, "prerequisites": []}}]"""
BRANCH_DESIGNER_SKILL.output_parser = lambda text: {"choices": parse_scene_draft(text).get("choices", [])}

GENRE_DIMENSION_MAP = {
    "科幻": {
        "required": ["core_contradiction", "social_structure", "tech_system", "constraints", "impossible"],
        "optional": ["geography", "history", "culture"],
        "dimension_labels": {
            "core_contradiction": "核心矛盾",
            "social_structure": "社会结构",
            "tech_system": "科技体系",
            "geography": "地理环境",
            "history": "历史背景",
            "culture": "文化习俗",
            "constraints": "约束条件",
            "impossible": "不可能事项",
        },
        "dimension_desc": {
            "core_contradiction": "世界运行的终极矛盾，驱动所有剧情发展的核心动力",
            "social_structure": "政治体系、阶层划分、权力流动、资源分配",
            "tech_system": "科技规则、边界、代价与限制、技术等级体系",
            "geography": "地缘格局、气候特征、资源分布、太空/行星/空间站布局",
            "history": "关键历史事件、文明传承、未解之谜",
            "culture": "价值观体系、禁忌、仪式、节日",
            "constraints": "物理法则、社会规则、不可逾越的边界",
            "impossible": "绝对禁忌、打破后不可逆的底线",
        },
    },
    "武侠": {
        "required": ["core_contradiction", "social_structure", "martial_system", "geography", "constraints", "impossible"],
        "optional": ["history", "culture"],
        "dimension_labels": {
            "core_contradiction": "核心矛盾",
            "social_structure": "江湖格局",
            "martial_system": "武功体系",
            "geography": "地理环境",
            "history": "历史背景",
            "culture": "文化习俗",
            "constraints": "约束条件",
            "impossible": "不可能事项",
        },
        "dimension_desc": {
            "core_contradiction": "世界运行的终极矛盾，驱动所有剧情发展的核心动力",
            "social_structure": "门派势力、江湖规矩、正邪之分、权力格局",
            "martial_system": "武功境界、功法体系、内力规则、突破条件与代价",
            "geography": "江湖地图、名山大川、秘境分布、门派据点",
            "history": "江湖往事、百年恩怨、失传秘籍、未解之谜",
            "culture": "江湖规矩、侠义精神、禁忌、仪式",
            "constraints": "武学限制、天道规则、不可逾越的边界",
            "impossible": "绝对禁忌、打破后不可逆的底线",
        },
    },
    "仙侠": {
        "required": ["core_contradiction", "social_structure", "cultivation_system", "geography", "constraints", "impossible"],
        "optional": ["history", "culture"],
        "dimension_labels": {
            "core_contradiction": "核心矛盾",
            "social_structure": "修仙界格局",
            "cultivation_system": "修炼体系",
            "geography": "地理环境",
            "history": "历史背景",
            "culture": "文化习俗",
            "constraints": "约束条件",
            "impossible": "不可能事项",
        },
        "dimension_desc": {
            "core_contradiction": "世界运行的终极矛盾，驱动所有剧情发展的核心动力",
            "social_structure": "宗门势力、修仙等级、仙凡之别、天庭/魔域格局",
            "cultivation_system": "修炼境界、功法体系、天劫规则、飞升条件与代价",
            "geography": "修仙界地图、洞天福地、秘境分布、宗门据点",
            "history": "上古大战、仙人传承、失传功法、未解之谜",
            "culture": "修仙规矩、道心要求、禁忌、仪式",
            "constraints": "天道法则、因果报应、不可逾越的边界",
            "impossible": "绝对禁忌、打破后不可逆的底线",
        },
    },
    "都市": {
        "required": ["core_contradiction", "social_structure", "constraints", "impossible"],
        "optional": ["geography", "history", "culture"],
        "dimension_labels": {
            "core_contradiction": "核心矛盾",
            "social_structure": "社会结构",
            "geography": "城市地图",
            "history": "历史背景",
            "culture": "文化习俗",
            "constraints": "约束条件",
            "impossible": "不可能事项",
        },
        "dimension_desc": {
            "core_contradiction": "世界运行的终极矛盾，驱动所有剧情发展的核心动力",
            "social_structure": "阶层划分、权力流动、经济体系、利益集团",
            "geography": "城市布局、关键地点、势力范围划分",
            "history": "关键历史事件、未解之谜、旧账",
            "culture": "价值观体系、社会潜规则、禁忌",
            "constraints": "法律边界、社会规则、不可逾越的底线",
            "impossible": "绝对禁忌、打破后不可逆的底线",
        },
    },
    "悬疑": {
        "required": ["core_contradiction", "social_structure", "info_structure", "constraints", "impossible"],
        "optional": ["geography", "history"],
        "dimension_labels": {
            "core_contradiction": "核心矛盾",
            "social_structure": "社会结构",
            "info_structure": "信息结构",
            "geography": "地理环境",
            "history": "历史背景",
            "constraints": "约束条件",
            "impossible": "不可能事项",
        },
        "dimension_desc": {
            "core_contradiction": "世界运行的终极矛盾，驱动所有剧情发展的核心动力",
            "social_structure": "权力结构、利益集团、势力关系",
            "info_structure": "信息分布、知情者层级、信息封锁机制、真相揭露路径",
            "geography": "关键地点、犯罪现场、秘密空间",
            "history": "关键历史事件、旧案、未解之谜",
            "constraints": "物理法则、社会规则、不可逾越的边界",
            "impossible": "绝对禁忌、打破后不可逆的底线",
        },
    },
}

DEFAULT_GENRE_DIMENSIONS = {
    "required": ["core_contradiction", "social_structure", "tech_magic", "constraints", "impossible"],
    "optional": ["geography", "history", "culture"],
    "dimension_labels": {
        "core_contradiction": "核心矛盾",
        "social_structure": "社会结构",
        "tech_magic": "科技/魔法体系",
        "geography": "地理环境",
        "history": "历史背景",
        "culture": "文化习俗",
        "constraints": "约束条件",
        "impossible": "不可能事项",
    },
    "dimension_desc": {
        "core_contradiction": "世界运行的终极矛盾，驱动所有剧情发展的核心动力",
        "social_structure": "政治体系、阶层划分、权力流动",
        "tech_magic": "科技/魔法体系（规则、边界、代价与限制）",
        "geography": "地缘格局、气候特征、资源分布",
        "history": "关键历史事件、文化传承、未解之谜",
        "culture": "价值观体系、禁忌、仪式、节日",
        "constraints": "物理法则、社会规则、不可逾越的边界",
        "impossible": "绝对禁忌、打破后不可逆的底线",
    },
}

WORLD_BUILDER_SKILL = Skill()
WORLD_BUILDER_SKILL.name = "world_builder"
WORLD_BUILDER_SKILL.intent = "write.creative"
WORLD_BUILDER_SKILL.model = "ds-reasoner"
WORLD_BUILDER_SKILL.prompt_template = """你是世界观构建专家。

## 用户需求
{user_requirements}

## 题材: {genre}
## 风格: {style}
## 核心矛盾: {core_contradiction}
## 目标总字数: {target_word_count}字
## 世界观深度目标: {world_depth}/10

{genre_dimension_instructions}

输出 JSON 格式，必须使用以下英文键名（每个值是详细的中文描述，200-500字）:
{genre_dimension_json_template}

构建深度应与目标字数匹配：10万字以内注重核心规则清晰，50万字以上需要多层次的隐藏设定。每个维度的描述必须具体、有画面感，禁止泛泛而谈。**必须且只能生成上述列出的维度，不要生成未列出的维度。**"""


def _parse_world_setting(text: str) -> dict:
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return {"world_setting": text, "world_parsed": parsed}
    except json.JSONDecodeError:
        pass
    return {"world_setting": text}


WORLD_BUILDER_SKILL.output_parser = _parse_world_setting

GENRE_NAMING_STYLES = {
    "仙侠": "角色名必须为2-4字古风名（如：云无涯、苏暮晚、萧逸尘、柳清漪），禁止使用现代名或西方名",
    "武侠": "角色名必须为2-4字江湖风格名（如：沈惊鸿、叶孤城、陆小凤、花满楼），禁止使用现代名",
    "科幻": "角色名可以是中英文混合或未来感名（如：林远舟、Nova·陈、K-7号、赵星河），体现未来感",
    "都市": "角色名必须为常见中文姓名（如：陈默、林晓、赵远山、苏晴），贴近现实",
    "悬疑": "角色名必须为常见中文姓名，但可以有代号或化名（如：方远/代号：影子、李明月），体现神秘感",
    "历史": "角色名必须符合历史背景（如：萧瑾、慕容婉儿），禁止使用现代名",
}

CHARACTER_DESIGNER_SKILL = Skill()
CHARACTER_DESIGNER_SKILL.name = "character_designer"
CHARACTER_DESIGNER_SKILL.intent = "write.creative"
CHARACTER_DESIGNER_SKILL.model = "ds-reasoner"
CHARACTER_DESIGNER_SKILL.prompt_template = """你是角色设计专家。

## 世界观
{world_setting}

## 核心矛盾
{core_contradiction}

## 题材: {genre}
## 角色命名风格约束: {naming_style_constraint}
## 需要角色数量: {character_count}
## 角色深度目标: {character_depth}/10
## 目标总字数: {target_word_count}字

请设计{character_count}个角色，形成完整角色阵容，覆盖主角、反派、挚爱、导师、暗线角色等类型。

【题材深度绑定 — 强制约束，必须遵守】
1. **命名约束**：{naming_style_constraint}。违反此约束的角色直接作废。
2. **核心动机绑定**：每个角色的core_goal必须直接回应世界观核心矛盾——角色要么在维护这个矛盾的现状，要么在试图打破它，要么在矛盾中求生。绝不能出现与核心矛盾无关的动机。
3. **暗秘密绑定**：每个角色的dark_secret必须与世界观的深层设定有关——秘密的揭露必须能引发对世界观的重新认知。
4. **行为约束绑定**：每个角色的behavior_never必须与世界观的约束条件/不可能事项一致。

每个角色必须包含:
- 名称（{naming_style_constraint}）、角色类型(protagonist/antagonist/love_interest/mentor/rival/wildcard/sidekick/foil)
- 背景故事（200-350字，必须包含具体创伤事件和人生转折，且必须发生在本世界观内）
- 核心动机、核心恐惧（两者必须形成内在矛盾，且核心动机必须直接回应世界观核心矛盾）
- 表面形象 vs 真实面目（必须形成反差）
- 语言风格、口头禅、说话习惯（必须符合{genre}题材风格）
- 角色弧描述（起点→关键转折→潜在终局，100-200字）
- 必然行为、绝对不会行为（绝对不会行为必须与世界观约束条件一致）、需要铺垫才能行为
- 情感弱点、隐藏创伤、不为人知的秘密（秘密必须与世界观的深层设定有关）
- 与其他角色的关系线索（每个角色至少与3个其他角色有关系）

角色之间必须形成:
- 至少3组三角关系
- 至少2组隐藏关系（表面无关，实际有深层联系）
- 利益阵营的对立和交叉
- 信息差（不同角色掌握不同信息片段）

输出JSON数组格式，每个角色包含所有上述字段。
角色设计深度应与目标字数匹配：10万字以内角色关系简洁清晰，50万字以上需要复杂的角色网络和内心层次。"""
CHARACTER_DESIGNER_SKILL.output_parser = lambda text: {"characters": text}

RELATION_NETWORK_DESIGNER_SKILL = Skill()
RELATION_NETWORK_DESIGNER_SKILL.name = "relation_network_designer"
RELATION_NETWORK_DESIGNER_SKILL.intent = "write.creative"
RELATION_NETWORK_DESIGNER_SKILL.model = "ds-reasoner"
RELATION_NETWORK_DESIGNER_SKILL.prompt_template = """你是人物关系网络设计专家。

## 世界观
{world_setting}

## 核心矛盾
{core_contradiction}

## 已有角色
{characters}

请为以上角色设计完整的关系网络，要求:

1. **密度**：每个角色至少与3个其他角色有直接关系
2. **三角关系**：至少3组三角关系（A→B→C→A闭环）
3. **暗线关系**：至少2组隐藏关系（秘密盟友/隐藏仇敌/要挟者等）
4. **信息差**：每条关系包含信息不对称
5. **关系弧线**：每条关系有初始状态→关键事件→可能走向
6. **引爆点**：至少3条关系的信任度或好感度≤20
7. **权力结构**：明确的权力流动（谁操控谁、谁依赖谁）
8. **互锁效应**：改变任何一条关系都会影响其他关系

关系类型包括:
- 基础: family/lover/friend/enemy/mentor_student/colleague/rival/stranger/admirer/betrayer/protector/manipulator
- 高级: secret_ally(秘密盟友)/hidden_enemy(隐藏仇敌)/debtor(债务人)/blackmailer(要挟者)/surrogate(替身)/former_bond(昔日羁绊)/information_broker(信息掮客)

输出JSON数组格式:
[
  {{
    "char_a_name": "角色A名称",
    "char_b_name": "角色B名称",
    "relation_type": "关系类型",
    "trust": 0-100,
    "favor": 0-100,
    "surface_description": "表面关系描述(50-100字)",
    "deep_description": "深层关系描述(50-100字)",
    "info_known_a_about_b": ["A知道关于B的信息"],
    "info_known_b_about_a": ["B知道关于A的信息"],
    "relation_arc": "关系弧线(初始→关键事件→可能走向)",
    "detonator": "引爆条件"
  }}
]"""
RELATION_NETWORK_DESIGNER_SKILL.output_parser = lambda text: {"relations": text}

OUTLINE_WRITER_SKILL = Skill()
OUTLINE_WRITER_SKILL.name = "outline_writer"
OUTLINE_WRITER_SKILL.intent = "write.outline"
OUTLINE_WRITER_SKILL.model = "ds-reasoner"
OUTLINE_WRITER_SKILL.prompt_template = """你是剧本大纲专家。

## 世界观
{world_setting}

## 角色设定
{characters}

## 伏笔网络
{foreshadow_map}

## 目标章节数: {chapter_count}章
## 目标总字数: {target_word_count}字
## 每章字数范围: {min_words_per_chapter}-{max_words_per_chapter}字
## 情节复杂度目标: {plot_complexity}/10

请撰写章节大纲，每章包含:
- 章节标题（吸引眼球）
- 一句话核心事件
- 详细大纲（300-500字，描述关键场景和转折）
- 情感目标(0-10)
- 关键转折点
- 伏笔任务（plant/reinforce/reveal）
- 分支结构描述
- 预估字数
- **章节细分(sections)**：每章必须拆分为3-5节，每节包含:
  - 节标题（描述该节核心情节）
  - 节简述（50-100字描述该节发生的核心事件）
  - 情感值(0-10)
  - 是否包含哇塞时刻(wow_moment=true/false)

大纲策略应与目标总字数匹配：
- 1万-5万字：紧密叙事，每章必须有实质性推进
- 5万-20万字：中等节奏，注意中期疲劳点的预防
- 20万-150万字：长线布局，前30%建立世界观和角色关系网，中间50%逐步升级冲突，最后20%收束多线。输出JSON格式，每个chapter必须包含sections数组。"""
OUTLINE_WRITER_SKILL.output_parser = parse_outline


@register_agent
class CreatorAgent(BaseAgent):
    name = "creator"
    description = "场景创作、对白生成、分支设计、世界观构建、角色设计、关系网络设计、大纲撰写、思考模式自动选择"
    skills = {
        "scene_writer": SCENE_WRITER_SKILL,
        "dialogue_writer": DIALOGUE_WRITER_SKILL,
        "branch_designer": BRANCH_DESIGNER_SKILL,
        "choice_designer": BRANCH_DESIGNER_SKILL,
        "world_builder": WORLD_BUILDER_SKILL,
        "character_designer": CHARACTER_DESIGNER_SKILL,
        "relation_network_designer": RELATION_NETWORK_DESIGNER_SKILL,
        "outline_writer": OUTLINE_WRITER_SKILL,
        "chapter_outliner": OUTLINE_WRITER_SKILL,
    }

    THINKING_MODE_RULES: dict[str, _ThinkingModeRule] = {
        "quick": {
            "max_tokens": 16384,
            "temperature": 0.7,
            "conditions": lambda p: p.get("scene_type") in ("transition", "filler") or p.get("emotion_target", 5) <= 3,
        },
        "balanced": {
            "max_tokens": 32768,
            "temperature": 0.8,
            "conditions": lambda p: p.get("scene_type") in ("dialogue", "confrontation", "revelation") or 4 <= p.get("emotion_target", 5) <= 7,
        },
        "quality": {
            "max_tokens": 64000,
            "temperature": 0.9,
            "conditions": lambda p: p.get("scene_type") in ("climax", "twist", "wow_moment") or p.get("emotion_target", 5) >= 8 or p.get("is_wow_moment", False),
        },
    }

    THINKING_TO_COST_MAP = {"quick": "economy", "balanced": "balanced", "quality": "quality"}

    def _auto_select_thinking_mode(self, payload: dict) -> str:
        for mode in ("quality", "balanced", "quick"):
            if self.THINKING_MODE_RULES[mode]["conditions"](payload):
                return mode
        return "balanced"

    def _resolve_cost_profile(self, thinking_mode: str) -> str:
        return self.THINKING_TO_COST_MAP.get(thinking_mode, "balanced")

    def _resolve_max_tokens(self, task_type: str, payload: dict) -> int | None:
        if task_type == "scene_writer":
            scene_type = payload.get("scene_type", "dialogue")
            emotion = payload.get("emotion_level", 5)
            target_word_count = payload.get("target_word_count", 50000)
            # 根据目标总字数调整场景生成长度
            scale_factor = min(2.0, max(1.0, target_word_count / 50000))
            if scene_type in ("climax", "revelation") or emotion >= 8:
                return int(16000 * scale_factor)
            elif scene_type in ("conflict", "closing") or emotion >= 6:
                return int(12000 * scale_factor)
            elif scene_type == "transition":
                return int(8000 * scale_factor)
            return int(12000 * scale_factor)
        if task_type == "dialogue_writer":
            return 8000
        if task_type == "outline_writer" or task_type == "chapter_outliner":
            target_word_count = payload.get("target_word_count", 50000)
            scale_factor = min(2.0, max(1.0, target_word_count / 50000))
            return int(16000 * scale_factor)
        if task_type in ("world_builder", "character_designer"):
            target_word_count = payload.get("target_word_count", 50000)
            scale_factor = min(2.0, max(1.0, target_word_count / 50000))
            return int(12000 * scale_factor)
        if task_type == "relation_network_designer":
            target_word_count = payload.get("target_word_count", 50000)
            character_count = payload.get("character_count", 8)
            scale_factor = min(3.0, max(1.5, character_count / 8))
            return int(32768 * scale_factor)
        return None

    def _resolve_temperature(self, task_type: str, payload: dict) -> float | None:
        if task_type == "scene_writer":
            scene_type = payload.get("scene_type", "dialogue")
            if scene_type in ("climax", "revelation"):
                return 0.85
            if scene_type == "transition":
                return 0.75
            return 0.8
        if task_type == "outline_writer" or task_type == "chapter_outliner":
            return 0.7
        return None

    def _validate(self, task: AgentTask):
        if not task.project_id:
            raise ValueError("project_id is required")
        if task.task_type not in self.skills:
            raise ValueError(f"Unknown task_type: {task.task_type}. Available: {list(self.skills.keys())}")

    async def execute(self, task: AgentTask) -> AgentResult:
        self._validate(task)

        project_id = task.project_id
        payload = task.payload

        thinking_mode = payload.get("thinking_mode") or self._auto_select_thinking_mode(payload)
        cost_profile = self._resolve_cost_profile(thinking_mode)

        context = await self._build_context(task)
        skill = self._select_skill(task.task_type)

        if payload.get("fallback_mode") and task.task_type == "scene_writer":
            import copy
            skill = copy.deepcopy(skill)
            skill.prompt_template = """你是互动影游场景编剧。由于格式问题，本次使用简化模式。

{_chinese_writing_standards}

请直接输出纯文本格式的场景内容，包含：
1. 叙述段落（完整的小说式描写，包含画面感和感官描写）
2. 对话段落（角色名：台词）
3. 场景结尾的选择支（选项A/B/C及简述后果）

不要输出JSON，不要输出代码块，直接写正文。

## 世界观设定
{world_settings}

## 角色档案
{character_states}

## 前序场景
{previous_scene}

## 本场景任务
- 场景编号: {scene_code}
- 场景类型: {scene_type}
- 情感目标: {emotion_target}/10
- 地点: {location}

请直接写出完整的场景正文（叙述+对话+选择支），至少800字。"""
            skill.output_parser = lambda text: {"narration": text, "dialogue": [], "choices": [], "fallback_generated": True}

        result = await skill.execute(
            context=context,
            requirements=payload,
            gateway=self.gateway,
            cost_profile=cost_profile,
            max_tokens=self._resolve_max_tokens(task.task_type, payload),
            temperature=self._resolve_temperature(task.task_type, payload),
        )

        if task.task_type == "scene_writer" and isinstance(result, dict):
            result["thinking_mode"] = thinking_mode

        if task.task_type == "dialogue_writer" and isinstance(result, dict):
            result = await self._post_process_dialogue(result, project_id, payload)

        if task.task_type == "branch_designer" and isinstance(result, dict):
            result = await self._post_process_branches(result, project_id, payload)

        return AgentResult(
            status="completed",
            data=result,
        )

    async def _post_process_dialogue(self, result: dict, project_id: str, payload: dict) -> dict:
        characters = await self.storage.get_character_states(project_id) or []
        char_map = {c.get("name", ""): c for c in characters}

        dialogue_list = result.get("dialogue", [])
        if isinstance(dialogue_list, str):
            try:
                dialogue_list = json.loads(dialogue_list)
            except (json.JSONDecodeError, TypeError):
                dialogue_list = [{"char": "未知", "text": dialogue_list}]

        validated = []
        for line in (dialogue_list if isinstance(dialogue_list, list) else []):
            if not isinstance(line, dict):
                continue
            char_name = line.get("char", line.get("speaker", ""))
            char = char_map.get(char_name)
            if char and char.get("catchphrase"):
                text = line.get("text", "")
                if len(text) > 50 and char["catchphrase"] not in text:
                    text = text.rstrip("。！？…") + "，" + char["catchphrase"] + text[-1] if text else char["catchphrase"]
                    line["text"] = text
            validated.append({
                "char": char_name,
                "text": line.get("text", ""),
                "subtext": line.get("subtext", ""),
            })

        result["dialogue"] = validated
        return result

    async def _post_process_branches(self, result: dict, project_id: str, payload: dict) -> dict:
        choices = result.get("choices", [])

        max_branches = payload.get("max_branches", 3)
        if len(choices) > max_branches:
            choices = choices[:max_branches]

        for i, choice in enumerate(choices):
            if not choice.get("id"):
                choice["id"] = chr(65 + i)
            if "hidden" not in choice:
                choice["hidden"] = False
            if "prerequisites" not in choice:
                choice["prerequisites"] = []

        if len(choices) >= 2 and not any(c.get("hidden") for c in choices):
            choices[-1]["hidden"] = True
            choices[-1]["prerequisites"] = choices[-1].get("prerequisites", ["特定前置条件"])

        result["choices"] = choices
        return result

    async def _build_context(self, task: AgentTask) -> dict:
        project_id = task.project_id
        payload = task.payload

        layer0 = await self.storage.get_layer0(project_id)
        world_config = await self.storage.get_world_config(project_id) or {}
        project_config = await self.storage.get_project_config(project_id) or {}

        rag_query = self._build_rag_query(task)
        rag_results = await self.rag.retrieve(
            project_id, rag_query, top_k=10
        ) or []

        context: dict[str, Any] = {
            "layer0": self._format_layer0(layer0),
            "world_settings": self._format_world_settings(layer0, world_config),
            "rag_context": "\n---\n".join(r.text for r in rag_results),
            "chapter_info": "",
            "project_brief": self._build_project_brief(project_config),
            "sub_genre": project_config.get("sub_genre", ""),
            "theme": project_config.get("theme", ""),
            "core_contradiction": project_config.get("core_contradiction", ""),
            "narrative_pov": project_config.get("narrative_pov", "third_person"),
            "_chinese_writing_standards": _CHINESE_WRITING_STANDARDS,
            "_interactive_game_writing": _INTERACTIVE_GAME_WRITING,
            "_scene_gen_standards": SCENE_GEN_UPGRADED_STANDARDS,
        }

        if task.task_type == "world_builder":
            context["user_requirements"] = payload.get("user_requirements", "")
            context["genre"] = payload.get("genre", layer0_value(layer0, "genre"))
            context["style"] = payload.get("style", layer0_value(layer0, "style"))
            context["sub_genre"] = payload.get("sub_genre", project_config.get("sub_genre", ""))
            context["theme"] = payload.get("theme", project_config.get("theme", ""))
            context["core_contradiction"] = payload.get("core_contradiction", layer0_value(layer0, "core_contradiction") or project_config.get("core_contradiction", ""))
            context["narrative_pov"] = payload.get("narrative_pov", project_config.get("narrative_pov", "third_person"))
            context["target_word_count"] = payload.get("target_word_count", 50000)
            context["world_depth"] = payload.get("world_depth", 5)
            genre_name = payload.get("genre", layer0_value(layer0, "genre") or "")
            genre_config = GENRE_DIMENSION_MAP.get(genre_name, DEFAULT_GENRE_DIMENSIONS)
            all_dims = genre_config["required"] + [d for d in genre_config["optional"] if d in (payload.get("include_dimensions", []) or genre_config["optional"])]
            dim_instructions_lines = []
            for d in all_dims:
                label = genre_config["dimension_labels"].get(d, d)
                desc = genre_config["dimension_desc"].get(d, "")
                idx = genre_config["required"].index(d) if d in genre_config["required"] else len(genre_config["required"]) + genre_config["optional"].index(d) if d in genre_config["optional"] else 0
                dim_instructions_lines.append(f"{idx}. {label}（{desc}）")
            context["genre_dimension_instructions"] = "请构建世界观，包含以下维度:\n" + "\n".join(dim_instructions_lines)
            dim_json_lines = []
            for d in all_dims:
                label = genre_config["dimension_labels"].get(d, d)
                dim_json_lines.append(f'  "{d}": "{label}的详细描述"')
            context["genre_dimension_json_template"] = "{{\n" + ",\n".join(dim_json_lines) + "\n}}"

        elif task.task_type == "character_designer":
            world_setting_text = self._format_world_settings(layer0, world_config)
            if not world_setting_text or world_setting_text == "世界观尚未详细设定":
                world_setting_text = str(payload.get("world_settings") or payload.get("world_setting") or "")
            context["world_setting"] = world_setting_text
            context["core_contradiction"] = payload.get("core_contradiction", layer0_value(layer0, "core_contradiction"))
            context["character_count"] = payload.get("character_count", 8)
            context["character_depth"] = payload.get("character_depth", 5)
            context["target_word_count"] = payload.get("target_word_count", 50000)
            genre_name = payload.get("genre", layer0_value(layer0, "genre") or "")
            context["naming_style_constraint"] = GENRE_NAMING_STYLES.get(genre_name, "角色名应为2-4字中文姓名，符合题材风格")
            context["genre"] = genre_name
            context["sub_genre"] = payload.get("sub_genre", project_config.get("sub_genre", ""))
            context["theme"] = payload.get("theme", project_config.get("theme", ""))
            context["narrative_pov"] = payload.get("narrative_pov", project_config.get("narrative_pov", "third_person"))

        elif task.task_type == "relation_network_designer":
            world_setting_text = self._format_world_settings(layer0, world_config)
            if not world_setting_text or world_setting_text == "世界观尚未详细设定":
                world_setting_text = str(payload.get("world_settings") or payload.get("world_setting") or "")
            context["world_setting"] = world_setting_text
            context["core_contradiction"] = payload.get("core_contradiction", layer0_value(layer0, "core_contradiction"))
            chars = await self.storage.get_character_states(project_id)
            if not chars:
                chars = payload.get("characters", [])
            context["characters"] = json.dumps(chars, ensure_ascii=False) if isinstance(chars, list) else str(chars)
            context["genre"] = payload.get("genre", layer0_value(layer0, "genre"))
            context["sub_genre"] = payload.get("sub_genre", project_config.get("sub_genre", ""))
            context["theme"] = payload.get("theme", project_config.get("theme", ""))
            context["narrative_pov"] = payload.get("narrative_pov", project_config.get("narrative_pov", "third_person"))

        elif task.task_type in ("outline_writer", "chapter_outliner"):
            world_setting_text = self._format_world_settings(layer0, world_config)
            if not world_setting_text or world_setting_text == "世界观尚未详细设定":
                world_setting_text = str(payload.get("world_settings") or payload.get("world_setting") or "")
            context["world_setting"] = world_setting_text
            chars = await self.storage.get_character_states(project_id)
            if not chars:
                chars = payload.get("characters", [])
            context["characters"] = self._format_characters(chars)
            fs_list = await self.storage.get_foreshadows(project_id)
            if not fs_list:
                fs_list = payload.get("foreshadows", [])
            context["foreshadow_map"] = self._format_foreshadows(fs_list)
            context["chapter_count"] = payload.get("chapter_count", 10)
            context["target_word_count"] = payload.get("target_word_count", 50000)
            context["min_words_per_chapter"] = payload.get("min_words_per_chapter", 2000)
            context["max_words_per_chapter"] = payload.get("max_words_per_chapter", 8000)
            context["plot_complexity"] = payload.get("plot_complexity", 5)
            context["genre"] = payload.get("genre", layer0_value(layer0, "genre"))
            context["sub_genre"] = payload.get("sub_genre", project_config.get("sub_genre", ""))
            context["theme"] = payload.get("theme", project_config.get("theme", ""))
            context["core_contradiction"] = payload.get("core_contradiction", project_config.get("core_contradiction", ""))
            context["narrative_pov"] = payload.get("narrative_pov", project_config.get("narrative_pov", "third_person"))

        elif task.task_type in ("scene_writer",):
            if payload.get("fallback_mode") or payload.get("force_prose_format"):
                context["force_prose_format"] = True
                context["fallback_mode"] = True

            scene_id = payload.get("scene_id")
            if scene_id:
                prev_scenes = await self.storage.get_prev_scenes(scene_id, count=2)
                context["previous_scene"] = self._format_scenes(prev_scenes)

                scene = await self.storage.get_scene(project_id, scene_id)
                if scene:
                    context["scene_code"] = scene.get("scene_code", "")
                    context["genre"] = payload.get("genre", layer0_value(layer0, "genre"))
                    context["style"] = payload.get("style", layer0_value(layer0, "style") or project_config.get("style", project_config.get("writing_style", "")))
                    context["sub_genre"] = payload.get("sub_genre", project_config.get("sub_genre", ""))
                    context["theme"] = payload.get("theme", project_config.get("theme", ""))
                    context["core_contradiction"] = payload.get("core_contradiction", project_config.get("core_contradiction", ""))
                    context["narrative_pov"] = payload.get("narrative_pov", project_config.get("narrative_pov", "third_person"))
                    context["scene_type"] = scene.get("scene_type", "dialogue")
                    context["location"] = scene.get("location", "未指定")
                    context["weather"] = scene.get("weather", "未指定")
                    context["emotion_target"] = scene.get("emotion_level", 5)
                    context["word_constraints"] = self._build_word_constraints(payload, scene)
                    context["wow_requirements"] = self._build_wow_requirements(payload, scene)
                    context["foreshadow_tasks"] = self._format_foreshadow_tasks(scene)

                    chapter_id = scene.get("chapter_id")
                    if chapter_id:
                        chapter = await self.storage.get_chapter(project_id, chapter_id)
                        if chapter:
                            context["chapter_info"] = (
                                f"第{chapter.get('chapter_number', '?')}章「{chapter.get('title', '')}」\n"
                                f"情感目标: {chapter.get('emotion_target', '未设定')}/10\n"
                                f"核心事件: {chapter.get('core_conflict', '未设定')}"
                            )
            else:
                # 没有 scene_id 时，从章节大纲中选择下一个待写场景
                chapters = await self.storage.get_chapter_outlines(project_id)
                if not chapters:
                    chapters = payload.get("chapters", [])
                
                current_ch_idx = payload.get("current_chapter_index", 0)
                scenes_per_chapter_max = payload.get("scenes_per_chapter_max", 6)
                scenes_per_chapter_min = payload.get("scenes_per_chapter_min", 3)
                
                selected_chapter = None
                scene_num = 1
                
                for ch_idx, ch in enumerate(chapters):
                    ch_id = str(ch.get("id", ""))
                    existing_scenes = await self.storage.get_scenes_by_chapter(project_id, ch_id)
                    if len(existing_scenes) < scenes_per_chapter_max:
                        selected_chapter = ch
                        scene_num = len(existing_scenes) + 1
                        current_ch_idx = ch_idx
                        # 获取前序场景
                        if existing_scenes:
                            context["previous_scene"] = self._format_scenes(existing_scenes[-2:])
                        break
                
                if selected_chapter:
                    ch_num = selected_chapter.get("chapter_number", current_ch_idx + 1)
                    context["scene_code"] = f"CH{ch_num:03d}_S{scene_num:03d}"
                    context["genre"] = payload.get("genre", layer0_value(layer0, "genre"))
                    context["style"] = payload.get("style", layer0_value(layer0, "style") or project_config.get("style", project_config.get("writing_style", "")))
                    context["sub_genre"] = payload.get("sub_genre", project_config.get("sub_genre", ""))
                    context["theme"] = payload.get("theme", project_config.get("theme", ""))
                    context["core_contradiction"] = payload.get("core_contradiction", project_config.get("core_contradiction", ""))
                    context["narrative_pov"] = payload.get("narrative_pov", project_config.get("narrative_pov", "third_person"))
                    context["scene_type"] = "dialogue"
                    context["location"] = "根据章节大纲自由设定"
                    context["weather"] = "根据场景氛围自由设定"
                    context["emotion_target"] = selected_chapter.get("emotion_target", 5)
                    context["word_constraints"] = self._build_word_constraints(payload, {"scene_type": "dialogue", "emotion_level": selected_chapter.get("emotion_target", 5)})
                    context["wow_requirements"] = ""
                    context["foreshadow_tasks"] = self._format_foreshadow_tasks(selected_chapter)
                    context["chapter_info"] = (
                        f"第{selected_chapter.get('chapter_number', '?')}章「{selected_chapter.get('title', '')}」\n"
                        f"情感目标: {selected_chapter.get('emotion_target', '未设定')}/10\n"
                        f"核心事件: {selected_chapter.get('core_conflict', '未设定')}\n"
                        f"大纲摘要: {selected_chapter.get('summary', '未设定')}\n"
                        f"本场景为该章第{scene_num}个场景"
                    )

            char_ids = payload.get("character_ids", [])
            chars = await self.storage.get_character_states(project_id, char_ids)
            if not chars:
                chars = payload.get("characters", [])
            context["character_states"] = self._format_characters(chars)
            # 确保关键字段始终存在
            if not context.get("genre"):
                context["genre"] = payload.get("genre", "互动影游")
            if not context.get("style"):
                context["style"] = payload.get("style", "写实")

            context["world_setting"] = context.get("world_settings", "")
            context["chapter_outline"] = context.get("chapter_info", "")
            context["chapter_characters"] = context.get("character_states", "")
            context["target_word_count"] = payload.get("target_word_count", project_config.get("target_word_count", 3000))

            prev_scene_text = context.get("previous_scene", "")
            if prev_scene_text and prev_scene_text.strip():
                context["previous_scene_context"] = f"## 前序场景全文（必须衔接）\n{prev_scene_text}"
            else:
                context["previous_scene_context"] = "## 前序场景\n（这是第一个场景，需要以引人入胜的方式开场）"

            ch_id_for_count = payload.get("chapter_id", "")
            if ch_id_for_count:
                existing = await self.storage.get_scenes_by_chapter(project_id, ch_id_for_count)
                context["current_scene_index"] = len(existing) if existing else 0
            else:
                context["current_scene_index"] = 0

            foreshadow_tasks = []
            try:
                ch_idx_fs = payload.get("current_chapter_index", 0)
                all_fs = await self.storage.get_foreshadow_states(project_id)
                for fs in all_fs:
                    fs_status = fs.get("current_status", "design")
                    fs_cat = fs.get("foreshadow_category", "chapter")
                    plant_ch = fs.get("plant_chapter", "")
                    reinforce_ch = fs.get("reinforce_chapter", "")
                    reveal_ch = fs.get("reveal_chapter", "")
                    if fs_status == "design" and (not plant_ch or str(ch_idx_fs + 1) in str(plant_ch)):
                        foreshadow_tasks.append(f"🌱 埋设：{fs.get('description', '')[:80]}（{fs_cat}级伏笔）")
                    elif fs_status == "planted" and (not reinforce_ch or str(ch_idx_fs + 1) in str(reinforce_ch)):
                        foreshadow_tasks.append(f"🔄 强化：{fs.get('description', '')[:80]}（{fs_cat}级伏笔）")
                    elif fs_status == "reinforced" and (not reveal_ch or str(ch_idx_fs + 1) in str(reveal_ch)):
                        foreshadow_tasks.append(f"✨ 回收：{fs.get('description', '')[:80]}（{fs_cat}级伏笔）")
            except Exception:
                pass
            if foreshadow_tasks:
                context["foreshadow_tasks"] = "## 本场景必须执行的伏笔任务\n" + "\n".join(f"- {t}" for t in foreshadow_tasks)
            else:
                context["foreshadow_tasks"] = "## 伏笔任务\n（本场景无强制伏笔任务，但可自然埋设新伏笔）"

            ch_idx = payload.get("current_chapter_index", 0)
            sc_idx = context.get("current_scene_index", payload.get("current_scene_index", 0))
            total_ch = payload.get("chapter_count", 10)
            total_sc_in_ch = payload.get("scenes_in_chapter", 3)
            if sc_idx == 0 and ch_idx == 0:
                context["scene_position_info"] = "【重要】这是全剧的第一个场景，必须以引人入胜的开场开始——建立世界观氛围、引出核心矛盾、让读者产生强烈好奇心。禁止从剧情中间开始。"
            elif sc_idx == 0:
                context["scene_position_info"] = f"【重要】这是第{ch_idx+1}章的第一个场景，需要自然承接上一章的结尾，同时开启本章新的叙事弧。"
            elif sc_idx >= total_sc_in_ch - 1:
                context["scene_position_info"] = f"【重要】这是第{ch_idx+1}章的最后一个场景，需要为本章收尾，同时为下一章埋下悬念。"
            else:
                context["scene_position_info"] = f"这是第{ch_idx+1}章的第{sc_idx+1}个场景（共{total_sc_in_ch}个），需要推进剧情发展。"

        elif task.task_type in ("choice_designer", "branch_designer"):
            chars = await self.storage.get_character_states(project_id)
            if not chars:
                chars = payload.get("characters", [])
            context["character_states"] = self._format_characters(chars)
            fs_list = await self.storage.get_foreshadows(project_id)
            if not fs_list:
                fs_list = payload.get("foreshadows", [])
            context["foreshadow_tasks"] = self._format_foreshadows(fs_list)
            context["max_branch_depth"] = payload.get("max_branch_depth", 3)
            context["min_branches"] = payload.get("min_branches", 2)
            context["max_branches"] = payload.get("max_branches", 3)
            context["target_ending_count"] = payload.get("target_ending_count", 3)
            scenes = await self.storage.get_all_scenes_ordered(project_id)
            if not scenes:
                scenes = payload.get("scenes", [])
            scene_summaries = []
            for s in scenes[:10]:
                scene_summaries.append(f"- {s.get('scene_code', '?')}: {s.get('narration', '')[:200]}")
            context["scene_summary"] = "\n".join(scene_summaries) if scene_summaries else "暂无已生成场景"

        return context

    def _select_skill(self, task_type: str) -> Skill:
        return self.skills[task_type]

    def _build_rag_query(self, task: AgentTask) -> str:
        parts = []
        if task.task_type == "scene_writer":
            parts.append(f"场景 {task.payload.get('scene_id', '')}")
            parts.append(f"类型 {task.payload.get('scene_type', '')}")
            parts.append(f"情感 {task.payload.get('emotion_target', 5)}/10")
        elif task.task_type == "world_builder":
            parts.append(task.payload.get("core_contradiction", ""))
        return "，".join(filter(None, parts)) or task.project_id

    def _format_layer0(self, layer0: dict) -> str:
        if not layer0:
            return ""
        parts = []
        for key, val in layer0.items():
            parts.append(f"【{key}】\n{val.get('value', val) if isinstance(val, dict) else val}")
        return "\n\n".join(parts)

    def _format_scenes(self, scenes: list) -> str:
        parts = []
        for s in scenes:
            scene_code = s.get('scene_code', '?')
            narration = s.get('narration', '')
            dialogue = s.get('dialogue', [])
            if isinstance(dialogue, list):
                dialogue_text = "\n".join(
                    f"  {d.get('char', '?')}: {d.get('text', '')}" for d in dialogue if isinstance(d, dict)
                )
            elif dialogue:
                dialogue_text = str(dialogue)
            else:
                dialogue_text = ""
            actions = s.get('actions', [])
            if isinstance(actions, list):
                actions_text = "\n".join(f"  {a}" for a in actions)
            elif actions:
                actions_text = str(actions)
            else:
                actions_text = ""

            fs_ops = s.get('foreshadow_ops', [])
            if isinstance(fs_ops, str):
                try:
                    fs_ops = json.loads(fs_ops)
                except (json.JSONDecodeError, TypeError):
                    fs_ops = []
            if isinstance(fs_ops, list) and fs_ops:
                fs_lines = []
                for op in fs_ops:
                    if isinstance(op, dict):
                        fs_line = f"  [{op.get('op', '?')}] {op.get('fs_id', '?')}: {op.get('content', '')}"
                        if op.get('worldview_ref'):
                            fs_line += f" | 世界观: {op['worldview_ref']}"
                        if op.get('text_implementation'):
                            fs_line += f" | 实现: {op['text_implementation']}"
                        fs_lines.append(fs_line)
                fs_text = "\n".join(fs_lines)
            else:
                fs_text = ""

            choices = s.get('choices', [])
            if isinstance(choices, str):
                try:
                    choices = json.loads(choices)
                except (json.JSONDecodeError, TypeError):
                    choices = []
            if isinstance(choices, list) and choices:
                ch_lines = []
                for c in choices:
                    if isinstance(c, dict):
                        ch_line = f"  [{c.get('id', '?')}] {c.get('text', '')}"
                        if c.get('consequence_direct'):
                            ch_line += f" → 直接: {c['consequence_direct']}"
                        elif c.get('consequence'):
                            ch_line += f" → 后果: {c['consequence']}"
                        if c.get('consequence_indirect'):
                            ch_line += f" | 间接: {c['consequence_indirect']}"
                        if c.get('consequence_long_term'):
                            ch_line += f" | 远期: {c['consequence_long_term']}"
                        if c.get('moral_alignment'):
                            ch_line += f" | 道德: {c['moral_alignment']}"
                        ch_lines.append(ch_line)
                choices_text = "\n".join(ch_lines)
            else:
                choices_text = ""

            causal = s.get('causal_chain', {})
            if isinstance(causal, str):
                try:
                    causal = json.loads(causal)
                except (json.JSONDecodeError, TypeError):
                    causal = {}
            if isinstance(causal, dict) and causal:
                causal_lines = []
                pre = causal.get('preconditions', [])
                if isinstance(pre, list) and pre:
                    causal_lines.append(f"  前置: {'; '.join(str(p) for p in pre)}")
                if causal.get('catalyst'):
                    causal_lines.append(f"  催化: {causal['catalyst']}")
                if causal.get('direct_result'):
                    causal_lines.append(f"  直接: {causal['direct_result']}")
                if causal.get('indirect_result'):
                    causal_lines.append(f"  间接: {causal['indirect_result']}")
                if causal.get('far_result'):
                    causal_lines.append(f"  远期: {causal['far_result']}")
                causal_text = "\n".join(causal_lines)
            else:
                causal_text = ""

            scene_parts = [
                f"场景 {scene_code}:",
                f"【旁白】{narration}",
            ]
            if dialogue_text:
                scene_parts.append(f"【对白】\n{dialogue_text}")
            if actions_text:
                scene_parts.append(f"【动作】\n{actions_text}")
            if fs_text:
                scene_parts.append(f"【伏笔操作】\n{fs_text}")
            if choices_text:
                scene_parts.append(f"【互动选择】\n{choices_text}")
            if causal_text:
                scene_parts.append(f"【因果链】\n{causal_text}")

            parts.append("\n".join(scene_parts))
        return "\n---\n".join(parts)

    def _format_characters(self, chars: list) -> str:
        parts = []
        for c in chars:
            name = c.get('name', '?')
            role = c.get('role_type', '?')
            lines = [f"{name} ({role}):"]
            if c.get('background'):
                lines.append(f"  背景: {c['background']}")
            if c.get('core_goal'):
                lines.append(f"  动机: {c['core_goal']}")
            if c.get('core_fear'):
                lines.append(f"  恐惧: {c['core_fear']}")
            if c.get('language_style'):
                lines.append(f"  语言风格: {c['language_style']}")
            if c.get('catchphrase'):
                lines.append(f"  口头禅: {c['catchphrase']}")
            if c.get('surface_image'):
                lines.append(f"  表面形象: {c['surface_image']}")
            if c.get('true_self'):
                lines.append(f"  真实自我: {c['true_self']}")
            if c.get('dark_secret'):
                lines.append(f"  暗秘密: {c['dark_secret']}")
            if c.get('behavior_inevitable'):
                lines.append(f"  必然行为: {c['behavior_inevitable']}")
            if c.get('behavior_never'):
                lines.append(f"  绝不做: {c['behavior_never']}")
            parts.append("\n".join(lines))
        return "\n\n".join(parts)

    def _format_world_settings(self, layer0: dict, world_config: dict) -> str:
        parts = []
        core_keys = ["core_contradiction", "genre", "theme", "tone", "writing_style", "narrative_pov"]
        if layer0:
            for key in core_keys:
                val = layer0.get(key, {})
                if isinstance(val, dict):
                    val = val.get("value", "")
                if val and isinstance(val, str) and val.strip():
                    parts.append(f"【{key}】{val}")

        # 优先使用 world_config（LLM生成的完整世界观）
        if world_config and isinstance(world_config, dict):
            settings_labels = {
                "social_structure": "社会结构", "tech_magic": "科技/魔法体系",
                "geography": "地理环境", "history": "历史背景",
                "culture": "文化习俗", "constraints": "约束条件",
                "impossible": "不可能事项",
            }
            for key, label in settings_labels.items():
                val = world_config.get(key, "")
                if val and isinstance(val, str) and val.strip():
                    parts.append(f"【{label}】{val}")
            # 如果 world_config 有 world_setting 字段，直接使用
            ws = world_config.get("world_setting", "")
            if ws and isinstance(ws, str) and ws.strip() and len(ws) > 50:
                return ws
            # 如果有 social_structure 等字段，构建完整世界观
            if any(world_config.get(k) for k in settings_labels.keys()):
                return "\n\n".join(parts)

        return "\n\n".join(parts) if parts else "世界观尚未详细设定"

    def _build_project_brief(self, project_config: dict) -> str:
        if not project_config:
            return "暂无项目级约束，请严格围绕当前场景任务、检索资料和既有设定写作。"

        fields = [
            ("体裁", project_config.get("genre", "")),
            ("子类型", project_config.get("sub_genre", "")),
            ("主题", project_config.get("theme", "")),
            ("核心矛盾", project_config.get("core_contradiction", "")),
            ("基调", project_config.get("tone", "")),
            ("叙事视角", project_config.get("narrative_pov", "")),
            ("风格", project_config.get("style", project_config.get("writing_style", ""))),
            ("目标受众", project_config.get("target_audience", "")),
        ]
        parts = [f"- {label}: {value}" for label, value in fields if isinstance(value, str) and value.strip()]
        return "\n".join(parts) if parts else "暂无项目级约束，请严格围绕当前场景任务、检索资料和既有设定写作。"

    MAX_SCENE_WORDS = 3000
    MAX_SCENES_PER_CHAPTER = 50
    MIN_SCENES_PER_CHAPTER = 3

    def _build_word_constraints(self, payload: dict, scene: dict) -> str:
        scene_type = scene.get("scene_type", "dialogue")
        emotion = scene.get("emotion_level", 5)
        target_word_count = payload.get("target_word_count", 50000)
        chapter_count = payload.get("chapter_count", 10)

        if target_word_count > 0 and chapter_count > 0:
            words_per_chapter = target_word_count / chapter_count
            scenes_per_chapter = max(self.MIN_SCENES_PER_CHAPTER, min(self.MAX_SCENES_PER_CHAPTER, int(words_per_chapter / self.MAX_SCENE_WORDS)))
            target_scene_words = min(self.MAX_SCENE_WORDS, max(1500, int(words_per_chapter / scenes_per_chapter)))
        else:
            target_scene_words = 1500

        if scene_type in ("climax", "cutscene", "revelation") or emotion >= 8:
            min_w = max(2000, int(target_scene_words * 1.2))
            max_w = min(5000, int(target_scene_words * 1.8))
            return f"【字数硬性要求】本场景总字数（旁白+对白+动作）必须在 {min_w}-{max_w} 字之间！这是高潮/揭露场景，必须包含充分的环境描写、角色心理活动和多层次对白，确保场景冲击力和细节丰富度"
        elif scene_type in ("conflict", "closing"):
            min_w = max(1500, int(target_scene_words * 1.0))
            max_w = min(4500, int(target_scene_words * 1.5))
            return f"【字数硬性要求】本场景总字数（旁白+对白+动作）必须在 {min_w}-{max_w} 字之间！冲突/收尾场景需要充分的动作描写和情感张力"
        elif scene_type in ("transition", "filler"):
            min_w = max(800, int(target_scene_words * 0.5))
            max_w = min(2500, int(target_scene_words * 0.9))
            return f"【字数硬性要求】本场景总字数（旁白+对白+动作）必须在 {min_w}-{max_w} 字之间，简洁推进但保留画面感"

        min_w = max(1200, int(target_scene_words * 0.7))
        max_w = min(4000, int(target_scene_words * 1.3))
        return f"【字数硬性要求】本场景总字数（旁白+对白+动作）必须在 {min_w}-{max_w} 字之间"

    def _build_wow_requirements(self, payload: dict, scene: dict) -> str:
        if scene.get("is_wow_moment"):
            wow_type = scene.get("wow_type", "")
            wow_spec = scene.get("wow_spec", "")
            return f"【哇塞时刻要求】类型: {wow_type or '未指定'}\n设计说明: {wow_spec or '需要在此场景中制造一个让读者意想不到的转折或揭露'}\n要求: 反转必须自然、有铺垫、情感冲击力≥8/10"
        return ""

    def _format_foreshadow_tasks(self, scene: dict) -> str:
        fs_ops = scene.get("foreshadow_ops", [])
        if isinstance(fs_ops, str):
            try:
                fs_ops = json.loads(fs_ops)
            except (json.JSONDecodeError, TypeError):
                fs_ops = []
        if not fs_ops:
            fs_tasks = scene.get("foreshadow_tasks", [])
            if isinstance(fs_tasks, str):
                try:
                    fs_tasks = json.loads(fs_tasks)
                except (json.JSONDecodeError, TypeError):
                    fs_tasks = []
            if fs_tasks:
                fs_ops = fs_tasks
        if not fs_ops:
            return "无"
        lines = []
        for op in fs_ops:
            if isinstance(op, dict):
                op_type = op.get('op_type', op.get('op', 'plant'))
                fs_name = op.get('fs_name', op.get('fs_id', op.get('foreshadow_name', '未命名伏笔')))
                desc = op.get('description', op.get('content', ''))
                line = f"- [{op_type}] {fs_name}: {desc}"
                if op.get('worldview_ref'):
                    line += f" | 关联世界观: {op['worldview_ref']}"
                if op.get('text_implementation'):
                    line += f" | 实现方式: {op['text_implementation']}"
                lines.append(line)
            elif isinstance(op, str):
                lines.append(f"- {op}")
        return "\n".join(lines) if lines else "无"

    def _format_foreshadows(self, fs_list: list) -> str:
        if not fs_list:
            return "暂无伏笔设计"
        parts = []
        for fs in fs_list:
            parts.append(
                f"【{fs.get('name', '未命名')}】({fs.get('fs_type', '未知类型')}):\n"
                f"  表层: {fs.get('surface_layer', '')}\n"
                f"  深层: {fs.get('deep_layer', '')}\n"
                f"  真相: {fs.get('truth_layer', '')}"
            )
        return "\n\n".join(parts)
