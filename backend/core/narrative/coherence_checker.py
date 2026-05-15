"""
5层逻辑锁定协议 —— 连贯性检查器。

对场景草稿执行5层独立检查，每层由LLM驱动，评估场景内容与叙事上下文的一致性。
全部使用 async + AsyncSession 模式。
"""

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from core.gateway.client import get_gateway

logger = logging.getLogger(__name__)

COHERENCE_INTENT = "analyze.coherence"


@dataclass
class CheckResult:
    layer: str
    passed: bool
    issues: list[str] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)
    score: float = 0.0


@dataclass
class CoherenceReport:
    project_id: str
    scene_id: str
    checks: list[CheckResult] = field(default_factory=list)
    all_passed: bool = False
    total_score: float = 0.0


def _parse_llm_json(raw: str) -> dict:
    json_str = raw.strip()
    m = re.search(r"```(?:json)?\s*([\s\S]*?)```", json_str)
    if m:
        json_str = m.group(1).strip()
    return json.loads(json_str)


async def _call_llm(system_prompt: str, user_prompt: str) -> dict:
    gateway = get_gateway()
    try:
        response = await gateway.invoke(
            intent=COHERENCE_INTENT,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            cost_profile="economy",
            temperature=0.2,
            use_cache=False,
        )
        return _parse_llm_json(response.content)
    except Exception as e:
        logger.error("连贯性检查LLM调用失败: %s", str(e)[:200])
        return {"passed": False, "issues": [f"LLM调用异常: {str(e)[:200]}"], "suggestions": [], "score": 0}


async def check_character_consistency(
    db: AsyncSession,
    project_id: str,
    scene_content: str,
    narrative_context: str,
) -> CheckResult:
    system_prompt = """你是专业的叙事一致性审查员，专精角色连贯性分析。

你的任务是比对【场景内容】中出现的角色与【叙事上下文】中记录的角色状态，检查是否存在矛盾。

【检查维度】
1. **姓名正确性**：场景中角色的姓名、称谓是否与上下文一致，有没有拼写错误或错误指代
2. **性格一致性**：角色的行为、反应、决策模式是否与其既定性格特征匹配，有无突兀的性格突变
3. **说话风格一致性**：角色的台词是否保持其标志性的语言风格（句式长短、用词范围、口头禅、语气），有无风格断裂
4. **物理状态连贯性**：角色的位置、身体状况、情绪状态是否与前序场景自然衔接，有无跳跃式变化

【评分标准】
- 90-100：完全一致，无明显矛盾
- 70-89：基本一致，有1-2处轻微偏差
- 50-69：存在3-4处中等矛盾
- 30-49：存在5处以上明显矛盾
- 0-29：角色严重失真，几乎换了个人

【输出格式】
严格JSON，不要代码块包裹：
{"passed": true/false, "issues": ["具体问题描述"], "suggestions": ["改进建议"], "score": 0-100}"""

    user_prompt = f"""请检查以下场景的角色一致性：

========== 叙事上下文（包含角色状态、前序事件、关系网络等） ==========
{narrative_context}

========== 场景内容（待检查的场景草稿） ==========
{scene_content}

请逐项检查并返回JSON结果。"""

    data = await _call_llm(system_prompt, user_prompt)
    return CheckResult(
        layer="角色一致性",
        passed=data.get("passed", False),
        issues=data.get("issues", []),
        suggestions=data.get("suggestions", []),
        score=float(data.get("score", 0)),
    )


async def check_timeline_consistency(
    db: AsyncSession,
    project_id: str,
    scene_content: str,
    narrative_context: str,
) -> CheckResult:
    system_prompt = """你是专业的叙事一致性审查员，专精时间线连贯性分析。

你的任务是检查【场景内容】中描述的事件与【叙事上下文】中的时间线是否自洽。

【检查维度】
1. **时间顺序正确性**：场景中描述的事件先后顺序是否与前序事件形成合理的因果链，有无时间倒错（后发生的事表现为先发生）
2. **因果链闭合性**：本场景发生的事件是否由前序事件的"未解决张力"自然催生，有无凭空出现的突兀事件
3. **时间跨度合理性**：场景之间的时间间隔与实际发生的事件量是否匹配（不能"一天之内发生了需要一周才能完成的事"）
4. **节奏连贯性**：叙事节奏是否与篇章结构匹配，有无突然加速或拖沓

【评分标准】
- 90-100：时间线完全自洽，因果链清晰闭合
- 70-89：有轻微时间描述偏差，不影响整体理解
- 50-69：存在中等时间矛盾，可能引起读者困惑
- 30-49：明显的时间跳跃或因果关系缺失
- 0-29：时间线严重混乱，事件先后无法成立

【输出格式】
严格JSON，不要代码块包裹：
{"passed": true/false, "issues": ["具体问题描述"], "suggestions": ["改进建议"], "score": 0-100}"""

    user_prompt = f"""请检查以下场景的时间线一致性：

========== 叙事上下文（包含前序事件链、时间标注、因果链条等） ==========
{narrative_context}

========== 场景内容（待检查的场景草稿） ==========
{scene_content}

请逐项检查事件时间顺序、因果链闭合性、时间跨度合理性，返回JSON结果。"""

    data = await _call_llm(system_prompt, user_prompt)
    return CheckResult(
        layer="时间线一致性",
        passed=data.get("passed", False),
        issues=data.get("issues", []),
        suggestions=data.get("suggestions", []),
        score=float(data.get("score", 0)),
    )


async def check_foreshadow_consistency(
    db: AsyncSession,
    project_id: str,
    scene_content: str,
    narrative_context: str,
) -> CheckResult:
    system_prompt = """你是专业的叙事一致性审查员，专精伏笔系统连贯性分析。

你的任务是检查【场景内容】是否与【叙事上下文】中的活跃伏笔系统保持一致。

【检查维度】
1. **伏笔推进**：场景是否对活跃伏笔进行了合理的推进（埋设新线索/强化已有暗示/回收伏笔真相），有无停滞
2. **伏笔揭示**：场景中是否有对之前暗示的伏笔进行了揭示，揭示时机是否合理（不能过早暴露导致失去悬念，也不能过晚导致被遗忘）
3. **伏笔忽略**：上下文中标记为"待处理"的活跃伏笔是否被场景忽略，若忽略需标记原因（该伏笔不属于本场景责任范围/场景类型不适合/需要前序铺垫等）
4. **伏笔冲突**：场景中新埋设的伏笔是否与已有伏笔之间存在逻辑矛盾

【评分标准】
- 90-100：活跃伏笔得到合理推进，无忽略或矛盾
- 70-89：大部分伏笔处理得当，有1个轻微忽略
- 50-69：存在伏笔推进不足或2-3个忽略
- 30-49：多个伏笔被忽略或存在明显矛盾
- 0-29：伏笔系统严重混乱，与上下文完全脱节

【输出格式】
严格JSON，不要代码块包裹：
{"passed": true/false, "issues": ["具体问题描述"], "suggestions": ["改进建议"], "score": 0-100}"""

    user_prompt = f"""请检查以下场景的伏笔一致性：

========== 叙事上下文（包含活跃伏笔清单、伏笔状态、待处理伏笔任务等） ==========
{narrative_context}

========== 场景内容（待检查的场景草稿） ==========
{scene_content}

请逐项检查伏笔推进、揭示、忽略、冲突情况，返回JSON结果。"""

    data = await _call_llm(system_prompt, user_prompt)
    return CheckResult(
        layer="伏笔一致性",
        passed=data.get("passed", False),
        issues=data.get("issues", []),
        suggestions=data.get("suggestions", []),
        score=float(data.get("score", 0)),
    )


async def check_worldbuilding_consistency(
    db: AsyncSession,
    project_id: str,
    scene_content: str,
    narrative_context: str,
) -> CheckResult:
    system_prompt = """你是专业的叙事一致性审查员，专精世界观自洽性分析。

你的任务是检查【场景内容】中的空间、规则、设定描述是否与【叙事上下文】中的世界观保持自洽。

【检查维度】
1. **空间位置自洽**：场景中描述的地理位置、建筑布局、空间关系是否与世界观设定一致，有无地点跳跃或空间矛盾
2. **世界观规则遵守**：场景中描述的技术水平、魔法体系、社会规则、物理法则等是否遵守了世界观中的约束条件和不可能事项
3. **文化细节一致**：场景中的社会习俗、礼仪规范、服饰饮食、语言习惯等文化细节是否与世界观设定匹配
4. **环境描述自洽**：场景中的天气、光照、季节等自然环境描述是否与上下文保持连续

【评分标准】
- 90-100：世界观完全自洽，细节严谨
- 70-89：基本自洽，有1-2处轻微细节偏差
- 50-69：存在中等世界观矛盾
- 30-49：明显违反世界观规则设定
- 0-29：世界观严重崩塌，规则被无视

【输出格式】
严格JSON，不要代码块包裹：
{"passed": true/false, "issues": ["具体问题描述"], "suggestions": ["改进建议"], "score": 0-100}"""

    user_prompt = f"""请检查以下场景的世界观一致性：

========== 叙事上下文（包含世界观设定、空间布局、规则约束、文化背景等） ==========
{narrative_context}

========== 场景内容（待检查的场景草稿） ==========
{scene_content}

请逐项检查空间位置、世界观规则、文化细节、环境描述的自洽性，返回JSON结果。"""

    data = await _call_llm(system_prompt, user_prompt)
    return CheckResult(
        layer="世界观一致性",
        passed=data.get("passed", False),
        issues=data.get("issues", []),
        suggestions=data.get("suggestions", []),
        score=float(data.get("score", 0)),
    )


async def check_theme_consistency(
    db: AsyncSession,
    project_id: str,
    scene_content: str,
    narrative_context: str,
) -> CheckResult:
    system_prompt = """你是专业的叙事一致性审查员，专精主题连贯性分析。

你的任务是检查【场景内容】的情节走向是否与【叙事上下文】中确立的故事主题保持一致。

【检查维度】
1. **主题偏离度**：场景中的核心冲突和角色行为是否服务于故事主题，有无偏离主题的冗余情节
2. **主题深化**：场景是否在推进剧情的同时深化了主题内涵（如：让读者对主题有新的理解层次），还是仅仅在表面重复主题口号
3. **情感基调一致**：场景的情感色彩和叙事基调是否与主题调性匹配（暗黑主题不应出现轻浮搞笑；温暖主题不应出现无谓残酷）
4. **道德/哲思一致**：场景中角色的道德抉择和价值判断是否与故事的主题立场保持一致，有无突兀的价值观转向

【评分标准】
- 90-100：完全贴合主题，且有深化
- 70-89：基本贴合主题，轻微冗余但不影响
- 50-69：存在偏离主题的段落
- 30-49：明显偏离主题，情节走向有问题
- 0-29：完全背离主题，建议重写

【输出格式】
严格JSON，不要代码块包裹：
{"passed": true/false, "issues": ["具体问题描述"], "suggestions": ["改进建议"], "score": 0-100}"""

    user_prompt = f"""请检查以下场景的主题一致性：

========== 叙事上下文（包含故事主题、核心矛盾、情感基调、道德立场等） ==========
{narrative_context}

========== 场景内容（待检查的场景草稿） ==========
{scene_content}

请逐项检查主题偏离度、主题深化、情感基调一致、道德哲思一致，返回JSON结果。"""

    data = await _call_llm(system_prompt, user_prompt)
    return CheckResult(
        layer="主题一致性",
        passed=data.get("passed", False),
        issues=data.get("issues", []),
        suggestions=data.get("suggestions", []),
        score=float(data.get("score", 0)),
    )


async def run_full_coherence_check(
    db: AsyncSession,
    project_id: str,
    scene_id: str,
    scene_content: str,
    narrative_context: str,
) -> CoherenceReport:
    checks = [
        await check_character_consistency(db, project_id, scene_content, narrative_context),
        await check_timeline_consistency(db, project_id, scene_content, narrative_context),
        await check_foreshadow_consistency(db, project_id, scene_content, narrative_context),
        await check_worldbuilding_consistency(db, project_id, scene_content, narrative_context),
        await check_theme_consistency(db, project_id, scene_content, narrative_context),
    ]
    all_passed = all(c.passed for c in checks)
    avg_score = sum(c.score for c in checks) / len(checks)
    return CoherenceReport(
        project_id=project_id,
        scene_id=scene_id,
        checks=checks,
        all_passed=all_passed,
        total_score=round(avg_score, 1),
    )