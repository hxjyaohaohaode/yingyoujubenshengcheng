"""
分层迭代精炼协调器 (Revision Orchestrator)
- Dramaturge三阶段精炼：全局审查 → 场景级审查 → 层次协调修订
- 向后兼容：run_global_review / refine_scene 独立函数
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
    rhythm_issues: list[dict] = field(default_factory=list)
    unresolved_foreshadows: list[dict] = field(default_factory=list)
    character_arc_issues: list[dict] = field(default_factory=list)
    theme_deviation_issues: list[dict] = field(default_factory=list)
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


@dataclass
class SceneDefect:
    defect_type: str
    location: str
    description: str
    suggestion: str
    priority: str


@dataclass
class SceneReviewReport:
    scene_id: str
    defects: list[SceneDefect] = field(default_factory=list)


@dataclass
class RevisionAction:
    granularity: str
    target: str
    description: str
    before: str = ""
    after: str = ""


@dataclass
class DramaturgeReport:
    project_id: str
    global_review: GlobalReviewReport
    scene_reviews: list[SceneReviewReport] = field(default_factory=list)
    revisions: list[RevisionAction] = field(default_factory=list)
    final_status: str = ""
    iterations: int = 0


class DramaturgeRefiner:
    def __init__(self, db: AsyncSession, project_id: str):
        self.db = db
        self.project_id = project_id
        self._narrative_context: str = ""

    async def _ensure_context(self) -> str:
        if not self._narrative_context:
            self._narrative_context = await build_narrative_context(self.db, self.project_id)
        return self._narrative_context

    async def global_review(self) -> GlobalReviewReport:
        gateway = get_gateway()
        if not gateway:
            return GlobalReviewReport(project_id=self.project_id, summary="LLM网关不可用")

        narrative_context = await self._ensure_context()

        system_prompt = """你是资深剧本审查专家。基于给定的叙事状态，从以下4个维度分析剧本：

1. 节奏问题(rhythm)：是否存在连续高潮导致读者疲劳、或连续低谷导致读者失去兴趣、信息密度是否适当、节奏是否有拖沓或跳跃
2. 未闭合伏笔(foreshadow)：哪些伏笔已完成、哪些悬而未决、哪些被遗忘、伏笔回收时机是否合理
3. 角色弧线断裂(character_arc)：每个主要角色的成长轨迹是否完整，有无突兀的性格转变或动机缺失
4. 主题偏离(theme_deviation)：情节走向是否偏离核心主题，有无冗余或不服务于主题的段落，情感基调是否与主题调性匹配

返回JSON格式：
{
    "rhythm_issues": [{"severity": "high/medium/low", "description": "...", "location": "第X章第Y场景", "suggestion": "..."}],
    "unresolved_foreshadows": [{"severity": "high/medium/low", "description": "...", "location": "...", "suggestion": "..."}],
    "character_arc_issues": [{"severity": "high/medium/low", "description": "...", "location": "...", "suggestion": "..."}],
    "theme_deviation_issues": [{"severity": "high/medium/low", "description": "...", "location": "...", "suggestion": "..."}],
    "overall_score": 75,
    "summary": "总体评价..."
}"""

        try:
            response = await gateway.invoke(
                intent="analyze.global_review",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"叙事状态：\n{narrative_context}\n\n请进行全面审查并返回JSON。项目ID: {self.project_id}"}
                ],
                cost_profile="economy",
                temperature=0.2,
                max_tokens=3000,
            )
            content = response.content if hasattr(response, 'content') else str(response)
            data = _parse_json(content)

            return GlobalReviewReport(
                project_id=self.project_id,
                rhythm_issues=data.get("rhythm_issues", []),
                unresolved_foreshadows=data.get("unresolved_foreshadows", []),
                character_arc_issues=data.get("character_arc_issues", []),
                theme_deviation_issues=data.get("theme_deviation_issues", []),
                overall_score=data.get("overall_score", 0.0),
                summary=data.get("summary", "审查完成"),
            )
        except Exception as e:
            return GlobalReviewReport(project_id=self.project_id, summary=f"全局审查异常: {str(e)}")

    async def scene_review(self, scenes: list[dict]) -> list[SceneReviewReport]:
        gateway = get_gateway()
        if not gateway:
            return [SceneReviewReport(scene_id=s.get("scene_id", "")) for s in scenes]

        narrative_context = await self._ensure_context()
        reports: list[SceneReviewReport] = []

        for scene in scenes:
            scene_id = scene.get("scene_id", "")
            scene_content = scene.get("content", "")

            system_prompt = """你是专业的场景级叙事审查专家。基于给定的叙事上下文和场景内容，定位以下6类具体缺陷：

1. 角色不一致(character_inconsistency)：角色行为、性格、说话风格与既定设定矛盾
2. 时间线矛盾(timeline_contradiction)：事件时间顺序、因果链、时间跨度存在矛盾
3. 伏笔遗漏(foreshadow_omission)：本应推进或揭示的活跃伏笔被忽略
4. 世界观违反(worldbuilding_violation)：场景描述违反已建立的世界观规则
5. 情感断裂(emotional_break)：情感基调或角色情绪状态出现不自然跳跃
6. 对白失真(dialogue_distortion)：角色对白风格与既定说话方式不符

返回JSON格式：
{
    "defects": [
        {
            "defect_type": "character_inconsistency/timeline_contradiction/foreshadow_omission/worldbuilding_violation/emotional_break/dialogue_distortion",
            "location": "第X段/第Y句",
            "description": "具体问题描述",
            "suggestion": "修改建议",
            "priority": "high/medium/low"
        }
    ]
}"""

            try:
                response = await gateway.invoke(
                    intent="analyze.scene_review",
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": f"叙事上下文：\n{narrative_context}\n\n场景ID: {scene_id}\n场景内容：\n{scene_content[:5000]}\n\n请进行场景级审查并返回JSON。"}
                    ],
                    cost_profile="standard",
                    temperature=0.2,
                    max_tokens=3000,
                )
                content = response.content if hasattr(response, 'content') else str(response)
                data = _parse_json(content)

                defects = [
                    SceneDefect(
                        defect_type=d.get("defect_type", ""),
                        location=d.get("location", ""),
                        description=d.get("description", ""),
                        suggestion=d.get("suggestion", ""),
                        priority=d.get("priority", "medium"),
                    )
                    for d in data.get("defects", [])
                ]
                reports.append(SceneReviewReport(scene_id=scene_id, defects=defects))
            except Exception:
                reports.append(SceneReviewReport(scene_id=scene_id))

        return reports

    async def coordinated_revision(
        self,
        scenes: list[dict],
        global_report: GlobalReviewReport,
        scene_reports: list[SceneReviewReport],
        max_iterations: int = 3,
    ) -> tuple[list[dict], list[RevisionAction], bool, int]:
        gateway = get_gateway()
        if not gateway:
            return scenes, [], False, 0

        current_scenes = [dict(s) for s in scenes]
        all_revisions: list[RevisionAction] = []
        all_passed = False
        iterations = 0
        current_scene_reports = list(scene_reports)

        for iteration in range(max_iterations):
            iterations = iteration + 1
            revision_prompt = self._build_revision_prompt(current_scenes, global_report, current_scene_reports)

            try:
                response = await gateway.invoke(
                    intent="rewrite.coordinated_revision",
                    messages=[
                        {"role": "system", "content": "你是剧本修订专家。你需要协调多粒度修改：全局结构调整（如插入过渡场景）、场景级修改（如补充伏笔操作）、句子级修改（如修正角色语气）。仅修复指出的具体问题，保持未提及的内容不变。返回JSON格式。"},
                        {"role": "user", "content": revision_prompt}
                    ],
                    cost_profile="standard",
                    temperature=0.3,
                    max_tokens=5000,
                )
                content = response.content if hasattr(response, 'content') else str(response)
                revision_data = _parse_json(content)
            except Exception:
                break

            if not revision_data:
                break

            actions = revision_data.get("actions", [])
            for action in actions:
                granularity = action.get("granularity", "sentence")
                target = action.get("target", "")
                description = action.get("description", "")
                before = action.get("before", "")
                after = action.get("after", "")

                all_revisions.append(RevisionAction(
                    granularity=granularity,
                    target=target,
                    description=description,
                    before=before,
                    after=after,
                ))

                if target and after:
                    for scene in current_scenes:
                        if scene.get("scene_id") == target:
                            scene["content"] = after
                            break

            coherence_passed = True
            for scene in current_scenes:
                scene_id = scene.get("scene_id", "")
                scene_content = scene.get("content", "")
                if not scene_content:
                    continue
                narrative_context = await self._ensure_context()
                report = await run_full_coherence_check(
                    self.db, self.project_id, scene_id, scene_content, narrative_context
                )
                if not report.all_passed:
                    coherence_passed = False
                    current_scene_reports = self._update_scene_reports_from_coherence(
                        scene_id, report, current_scene_reports
                    )

            if coherence_passed:
                all_passed = True
                break

        return current_scenes, all_revisions, all_passed, iterations

    def _build_revision_prompt(
        self,
        scenes: list[dict],
        global_report: GlobalReviewReport,
        scene_reports: list[SceneReviewReport],
    ) -> str:
        issues_parts: list[str] = []

        for issue in global_report.rhythm_issues:
            issues_parts.append(
                f"[节奏问题/{issue.get('severity', 'medium')}] "
                f"{issue.get('location', '')}: {issue.get('description', '')} "
                f"→ 建议: {issue.get('suggestion', '')}"
            )

        for issue in global_report.unresolved_foreshadows:
            issues_parts.append(
                f"[未闭合伏笔/{issue.get('severity', 'medium')}] "
                f"{issue.get('location', '')}: {issue.get('description', '')} "
                f"→ 建议: {issue.get('suggestion', '')}"
            )

        for issue in global_report.character_arc_issues:
            issues_parts.append(
                f"[角色弧线断裂/{issue.get('severity', 'medium')}] "
                f"{issue.get('location', '')}: {issue.get('description', '')} "
                f"→ 建议: {issue.get('suggestion', '')}"
            )

        for issue in global_report.theme_deviation_issues:
            issues_parts.append(
                f"[主题偏离/{issue.get('severity', 'medium')}] "
                f"{issue.get('location', '')}: {issue.get('description', '')} "
                f"→ 建议: {issue.get('suggestion', '')}"
            )

        for sr in scene_reports:
            for defect in sr.defects:
                issues_parts.append(
                    f"[{defect.defect_type}/{defect.priority}] "
                    f"{sr.scene_id} {defect.location}: {defect.description} "
                    f"→ 建议: {defect.suggestion}"
                )

        scenes_text = "\n\n".join(
            f"场景ID: {s.get('scene_id', '')}\n内容:\n{s.get('content', '')[:3000]}"
            for s in scenes
        )

        return (
            f"以下是需要修复的问题清单：\n\n"
            f"{chr(10).join(issues_parts)}\n\n"
            f"当前场景内容：\n\n{scenes_text}\n\n"
            f"请针对以上问题，协调多粒度修改，返回JSON格式：\n"
            f'{{"actions": [{{"granularity": "global/scene/sentence", "target": "场景ID", '
            f'"description": "修改描述", "before": "修改前的关键片段", '
            f'"after": "修改后的完整场景内容"}}]}}'
        )

    def _update_scene_reports_from_coherence(
        self,
        scene_id: str,
        report: CoherenceReport,
        scene_reports: list[SceneReviewReport],
    ) -> list[SceneReviewReport]:
        type_mapping: dict[str, str] = {
            "角色一致性": "character_inconsistency",
            "时间线一致性": "timeline_contradiction",
            "伏笔一致性": "foreshadow_omission",
            "世界观一致性": "worldbuilding_violation",
            "主题一致性": "emotional_break",
        }

        new_defects: list[SceneDefect] = []
        for check in report.checks:
            if not check.passed:
                defect_type = type_mapping.get(check.layer, "emotional_break")
                for idx, issue in enumerate(check.issues):
                    new_defects.append(SceneDefect(
                        defect_type=defect_type,
                        location=scene_id,
                        description=issue,
                        suggestion=check.suggestions[idx] if idx < len(check.suggestions) else "",
                        priority="high" if check.score < 50 else "medium",
                    ))

        updated = list(scene_reports)
        found = False
        for sr in updated:
            if sr.scene_id == scene_id:
                sr.defects = new_defects
                found = True
                break
        if not found:
            updated.append(SceneReviewReport(scene_id=scene_id, defects=new_defects))

        return updated

    async def run_dramaturge_refinement(self, scenes: list[dict]) -> DramaturgeReport:
        global_report = await self.global_review()

        scene_reports = await self.scene_review(scenes)

        revised_scenes, revisions, all_passed, iterations = await self.coordinated_revision(
            scenes, global_report, scene_reports
        )

        final_status = "passed" if all_passed else "needs_manual_review"

        return DramaturgeReport(
            project_id=self.project_id,
            global_review=global_report,
            scene_reviews=scene_reports,
            revisions=revisions,
            final_status=final_status,
            iterations=iterations,
        )


async def run_global_review(db: AsyncSession, project_id: str) -> GlobalReviewReport:
    refiner = DramaturgeRefiner(db, project_id)
    return await refiner.global_review()


async def refine_scene(
    db: AsyncSession,
    project_id: str,
    scene_id: str,
    scene_content: str,
    max_iterations: int = 3,
) -> RefineResult:
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
