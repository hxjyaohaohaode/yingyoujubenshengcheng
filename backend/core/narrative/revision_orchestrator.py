"""
分层迭代精炼协调器 (Revision Orchestrator)
- Global Review：分析整体故事线/节奏/伏笔闭合/角色弧线
- Scene Refine：单场景5层校验 + 局部修复（最多3轮迭代）
"""
import json
from dataclasses import dataclass, field
from sqlalchemy.ext.asyncio import AsyncSession
from core.narrative.coherence_checker import (
    run_full_coherence_check,
    CoherenceReport,
    CheckResult,
)
from core.narrative.memory_loader import build_narrative_context
from core.gateway.client import get_gateway


@dataclass
class GlobalReviewReport:
    project_id: str
    structure_issues: list[dict] = field(default_factory=list)
    rhythm_issues: list[dict] = field(default_factory=list)
    unresolved_foreshadows: list[dict] = field(default_factory=list)
    character_arc_issues: list[dict] = field(default_factory=list)
    overall_score: float = 0.0
    summary: str = ""


@dataclass
class RefineResult:
    scene_id: str
    original_content: str
    refined_content: str = ""
    checks_before: list[CheckResult] = field(default_factory=list)
    checks_after: list[CheckResult] = field(default_factory=list)
    iterations: int = 0
    all_passed: bool = False
    changes_summary: str = ""


async def run_global_review(db: AsyncSession, project_id: str) -> GlobalReviewReport:
    """
    全局审查：加载全部叙事记忆 → LLM分析整体结构/节奏/伏笔闭合/角色弧线
    """
    gateway = get_gateway()
    if not gateway:
        return GlobalReviewReport(project_id=project_id, summary="LLM网关不可用")

    narrative_context = await build_narrative_context(db, project_id)

    system_prompt = """你是资深剧本审查专家。基于给定的叙事状态，从以下4个维度分析剧本：

1. 结构均衡性(structure)：章节节奏是否合理、高潮低谷分布是否恰当
2. 节奏控制(rhythm)：信息密度是否适当、是否有拖沓或跳跃
3. 伏笔闭合(foreshadow)：哪些伏笔已完成、哪些悬而未决、哪些被遗忘
4. 角色弧线(character_arc)：每个主要角色的成长轨迹是否完整

返回JSON格式：
{
    "structure_issues": [{"severity": "high/medium/low", "description": "...", "location": "第X章", "suggestion": "..."}],
    "rhythm_issues": [{"severity": "high/medium/low", "description": "...", "location": "...", "suggestion": "..."}],
    "unresolved_foreshadows": [{"foreshadow_id": "...", "description": "...", "status": "unresolved/forgotten", "suggestion": "..."}],
    "character_arc_issues": [{"character": "...", "description": "...", "severity": "high/medium/low", "suggestion": "..."}],
    "overall_score": 75,
    "summary": "总体评价..."
}"""

    try:
        response = await gateway.invoke(
            intent="analyze.global_review",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"叙事状态：\n{narrative_context}\n\n请进行全面审查并返回JSON。项目ID: {project_id}"}
            ],
            cost_profile="economy",
            temperature=0.2,
            max_tokens=3000,
        )
        content = response.content if hasattr(response, 'content') else str(response)
        data = _parse_json(content)

        return GlobalReviewReport(
            project_id=project_id,
            structure_issues=data.get("structure_issues", []),
            rhythm_issues=data.get("rhythm_issues", []),
            unresolved_foreshadows=data.get("unresolved_foreshadows", []),
            character_arc_issues=data.get("character_arc_issues", []),
            overall_score=data.get("overall_score", 0.0),
            summary=data.get("summary", "审查完成"),
        )
    except Exception as e:
        return GlobalReviewReport(project_id=project_id, summary=f"全局审查异常: {str(e)}")


async def refine_scene(
    db: AsyncSession,
    project_id: str,
    scene_id: str,
    scene_content: str,
    max_iterations: int = 3,
) -> RefineResult:
    """
    单场景精炼迭代：
    1. 执行5层逻辑校验
    2. 针对不通过维度调用LLM进行局部修复
    3. 修复后重新校验
    4. 最多迭代max_iterations轮
    """
    result = RefineResult(scene_id=scene_id, original_content=scene_content)
    current_content = scene_content
    gateway = get_gateway()

    if not gateway:
        return result

    for iteration in range(max_iterations):
        narrative_context = await build_narrative_context(db, project_id)

        report = await run_full_coherence_check(
            db, project_id, scene_id, current_content, narrative_context
        )

        if iteration == 0:
            result.checks_before = report.checks

        if report.all_passed:
            result.refined_content = current_content
            result.checks_after = report.checks
            result.iterations = iteration + 1
            result.all_passed = True
            result.changes_summary = f"第{iteration+1}轮通过所有5层校验"
            return result

        failed_checks = [c for c in report.checks if not c.passed]
        issues_text = "\n".join(
            f"- [{c.layer}] 分数={c.score:.0f} 问题: {'; '.join(c.issues)} 建议: {'; '.join(c.suggestions)}"
            for c in failed_checks
        )

        fix_prompt = f"""当前场景内容存在以下问题，请**仅修复这些问题**，保持其余内容完全不变：

{issues_text}

原场景内容：
{current_content[:5000]}

修复后的场景内容："""

        try:
            response = await gateway.invoke(
                intent="rewrite.refine_scene",
                messages=[
                    {"role": "system", "content": "你是剧本精炼专家。仅修复用户指出的具体问题，保持未提及的其他内容完全不变。不要添加新情节或删除已有内容（除非修复需要）。"},
                    {"role": "user", "content": fix_prompt}
                ],
                cost_profile="standard",
                temperature=0.3,
                max_tokens=4000,
            )
            current_content = response.content if hasattr(response, 'content') else str(response)
        except Exception as e:
            result.changes_summary = f"第{iteration+1}轮精炼异常: {str(e)}"
            break

    narrative_context = await build_narrative_context(db, project_id)
    final_report = await run_full_coherence_check(
        db, project_id, scene_id, current_content, narrative_context
    )
    result.refined_content = current_content
    result.checks_after = final_report.checks
    result.iterations = max_iterations
    result.all_passed = final_report.all_passed
    result.changes_summary = f"完成{max_iterations}轮迭代精炼，{'全部通过' if final_report.all_passed else '仍有未通过项'}"

    return result


def _parse_json(text: str) -> dict:
    """从LLM响应中解析JSON"""
    text = text.strip()
    if text.startswith("```json"):
        text = text[7:]
    elif text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        import re
        match = re.search(r'\{[\s\S]*\}', text)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
        return {}