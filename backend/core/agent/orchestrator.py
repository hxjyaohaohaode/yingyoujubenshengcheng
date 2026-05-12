import json
import logging
from collections import defaultdict

from core.agent.base import BaseAgent, AgentTask, AgentResult, layer0_value
from core.agent.skill import Skill
from core.agent.registry import register_agent

logger = logging.getLogger(__name__)

MAX_CONSECUTIVE_REJECTIONS = 3

PRIORITY_RULES = {
    "anchor_scene": 10,
    "foreshadow_task": 8,
    "emotion_curve_adjust": 7,
    "character_scene": 5,
    "transition_scene": 3,
    "filler_scene": 1,
}

RHYTHM_RULES = {
    "high_consecutive_limit": 2,
    "high_threshold": 8,
    "low_consecutive_limit": 3,
    "low_threshold": 4,
    "buffer_emotion": 5,
    "detonation_emotion": 9,
}


def parse_plan(text: str) -> dict:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"plan": text}


def parse_progress(text: str) -> dict:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"analysis": text}


PLAN_PROJECT_SKILL = Skill()
PLAN_PROJECT_SKILL.name = "plan_project"
PLAN_PROJECT_SKILL.intent = "manage.orchestrate"
PLAN_PROJECT_SKILL.model = "ds-reasoner"
PLAN_PROJECT_SKILL.prompt_template = """你是项目管理专家，负责将互动叙事项目分解为可执行的任务列表。

## 项目信息

{project_info}

## 任务

制定项目执行计划:
1. 各阶段划分与预估工作量
2. 任务依赖关系
3. 关键里程碑
4. 风险点与应对策略

输出JSON格式的执行计划。"""
PLAN_PROJECT_SKILL.output_parser = parse_plan

ANALYZE_PROGRESS_SKILL = Skill()
ANALYZE_PROGRESS_SKILL.name = "analyze_progress"
ANALYZE_PROGRESS_SKILL.intent = "manage.context"
ANALYZE_PROGRESS_SKILL.model = "ds-reasoner"
ANALYZE_PROGRESS_SKILL.prompt_template = """分析项目当前执行状态。

{progress_data}

输出:
1. 当前阶段完成度
2. 阻塞项（如有）
3. 下一步最优行动
4. 整体进度预估

输出JSON格式分析报告。"""
ANALYZE_PROGRESS_SKILL.output_parser = parse_progress

RESOLVE_CONFLICT_SKILL = Skill()
RESOLVE_CONFLICT_SKILL.name = "resolve_conflict"
RESOLVE_CONFLICT_SKILL.intent = "reason.logic"
RESOLVE_CONFLICT_SKILL.model = "ds-reasoner"
RESOLVE_CONFLICT_SKILL.prompt_template = """仲裁以下设定冲突:

{conflict_description}

分析冲突根源，给出仲裁方案（保留谁、修改谁、理由）。

输出JSON: {{"decision": "保留/修改/合并", "reason": "仲裁理由", "action": "具体操作"}}"""
RESOLVE_CONFLICT_SKILL.output_parser = lambda text: json.loads(text) if text and text.strip().startswith("{") else {"decision": text or ""}

PRIORITY_SCHEDULER_SKILL = Skill()
PRIORITY_SCHEDULER_SKILL.name = "priority_scheduler"
PRIORITY_SCHEDULER_SKILL.intent = "planning"
PRIORITY_SCHEDULER_SKILL.model = "ds-reasoner"
PRIORITY_SCHEDULER_SKILL.prompt_template = "根据锚点场景优先级、伏笔任务紧急度和情感曲线，调度当前任务队列。"
PRIORITY_SCHEDULER_SKILL.output_parser = lambda text: {"schedule": text}

RHYTHM_MONITOR_SKILL = Skill()
RHYTHM_MONITOR_SKILL.name = "rhythm_monitor"
RHYTHM_MONITOR_SKILL.intent = "planning"
RHYTHM_MONITOR_SKILL.model = "ds-reasoner"
RHYTHM_MONITOR_SKILL.prompt_template = "监控剧情节奏：连续2个≥8分场景→插入缓冲；连续3个≤4分场景→安排引爆点。"
RHYTHM_MONITOR_SKILL.output_parser = lambda text: {"rhythm": text}

CONFLICT_ARBITER_SKILL = Skill()
CONFLICT_ARBITER_SKILL.name = "conflict_arbiter"
CONFLICT_ARBITER_SKILL.intent = "reason.logic"
CONFLICT_ARBITER_SKILL.model = "ds-reasoner"
CONFLICT_ARBITER_SKILL.prompt_template = "检测Agent间冲突：连续3次封驳→标记需人类介入。"
CONFLICT_ARBITER_SKILL.output_parser = lambda text: {"arbitration": text}


@register_agent
class OrchestratorAgent(BaseAgent):
    name = "orchestrator"
    description = "项目生命周期管理、优先级调度(锚点优先/伏笔优先/情感曲线判断)、节奏监控(连续高→缓冲/连续低→引爆)、冲突仲裁(连续3次封驳→人类介入)"
    skills = {
        "plan_project": PLAN_PROJECT_SKILL,
        "analyze_progress": ANALYZE_PROGRESS_SKILL,
        "resolve_conflict": RESOLVE_CONFLICT_SKILL,
        "priority_scheduler": PRIORITY_SCHEDULER_SKILL,
        "rhythm_monitor": RHYTHM_MONITOR_SKILL,
        "conflict_arbiter": CONFLICT_ARBITER_SKILL,
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._rejection_tracker = defaultdict(int)

    def _validate(self, task: AgentTask):
        if not task.project_id:
            raise ValueError("project_id is required")

    async def execute(self, task: AgentTask) -> AgentResult:
        self._validate(task)

        operation = task.payload.get("operation", task.task_type)

        if operation == "priority_schedule":
            return await self._priority_schedule(task.project_id, task.payload)

        if operation == "rhythm_check":
            return await self._rhythm_check(task.project_id, task.payload)

        if operation == "record_rejection":
            return await self._record_rejection(task.project_id, task.payload)

        if operation == "check_escalation":
            return await self._check_escalation(task.project_id, task.payload)

        context = await self._build_context(task)
        skill = self._select_skill(task.task_type)
        result = await skill.execute(
            context=context,
            requirements=task.payload,
            gateway=self.gateway,
            cost_profile="balanced",
        )

        return AgentResult(
            status="completed",
            data=result,
        )

    async def _priority_schedule(self, project_id: str, payload: dict) -> AgentResult:
        pending_tasks = payload.get("pending_tasks", [])

        if not pending_tasks:
            scenes = await self.storage.get_scene_summaries(project_id) or []
            foreshadows = await self.storage.get_foreshadows(project_id) or []

            pending_tasks = []
            for s in scenes:
                if s.get("status") in ("draft", None):
                    task_item = {
                        "type": "scene_generation",
                        "scene_id": s.get("id", ""),
                        "scene_code": s.get("scene_code", ""),
                        "emotion_level": s.get("emotion_level", 5),
                        "foreshadow_ops": s.get("foreshadow_ops", []),
                        "is_anchor": s.get("is_anchor", False),
                    }
                    pending_tasks.append(task_item)

            for fs in foreshadows:
                if fs.get("current_status") in ("design", "planted"):
                    pending_tasks.append({
                        "type": "foreshadow_task",
                        "foreshadow_id": fs.get("id", ""),
                        "foreshadow_name": fs.get("name", ""),
                        "current_status": fs.get("current_status", "design"),
                    })

        for task_item in pending_tasks:
            task_item["priority_score"] = self._compute_priority(task_item)

        pending_tasks.sort(key=lambda t: t.get("priority_score", 0), reverse=True)

        return AgentResult(
            status="completed",
            data={
                "project_id": project_id,
                "scheduled_tasks": pending_tasks,
                "total_pending": len(pending_tasks),
            },
        )

    def _compute_priority(self, task_item: dict) -> int:
        score = 0
        task_type = task_item.get("type", "")

        if task_item.get("is_anchor"):
            score += PRIORITY_RULES["anchor_scene"]

        if task_type == "foreshadow_task":
            score += PRIORITY_RULES["foreshadow_task"]
            if task_item.get("current_status") == "planted":
                score += 3

        if task_type == "scene_generation":
            fs_ops = task_item.get("foreshadow_ops", [])
            if isinstance(fs_ops, str):
                try:
                    fs_ops = json.loads(fs_ops)
                except (json.JSONDecodeError, TypeError):
                    fs_ops = []
            if fs_ops:
                score += PRIORITY_RULES["foreshadow_task"]

            emotion = task_item.get("emotion_level", 5)
            if emotion >= 8:
                score += PRIORITY_RULES["emotion_curve_adjust"]
            elif emotion <= 3:
                score += PRIORITY_RULES["transition_scene"]

        score += PRIORITY_RULES.get(task_type, 2)

        return score

    async def _rhythm_check(self, project_id: str, payload: dict) -> AgentResult:
        scenes = await self.storage.get_scene_summaries(project_id) or []
        if not scenes:
            return AgentResult(status="completed", data={"project_id": project_id, "rhythm_status": "no_data", "recommendations": []})

        sorted_scenes = sorted(scenes, key=lambda s: s.get("scene_code", ""))

        emotion_values = []
        for s in sorted_scenes:
            el = s.get("emotion_level")
            if el is not None:
                try:
                    emotion_values.append(int(el))
                except (ValueError, TypeError):
                    emotion_values.append(5)

        if not emotion_values:
            return AgentResult(status="completed", data={"project_id": project_id, "rhythm_status": "no_emotion_data", "recommendations": []})

        recommendations = []
        rhythm_status = "healthy"

        consecutive_high = 0
        for i, e in enumerate(emotion_values):
            if e >= RHYTHM_RULES["high_threshold"]:
                consecutive_high += 1
                if consecutive_high >= RHYTHM_RULES["high_consecutive_limit"]:
                    recommendations.append({
                        "type": "buffer_needed",
                        "after_scene": sorted_scenes[i].get("scene_code", ""),
                        "message": f"连续{consecutive_high}个高紧张场景(≥{RHYTHM_RULES['high_threshold']})，需要插入缓冲场景(情感值≈{RHYTHM_RULES['buffer_emotion']})",
                        "suggested_emotion": RHYTHM_RULES["buffer_emotion"],
                    })
                    rhythm_status = "tension_overload"
            else:
                consecutive_high = 0

        consecutive_low = 0
        for i, e in enumerate(emotion_values):
            if e <= RHYTHM_RULES["low_threshold"]:
                consecutive_low += 1
                if consecutive_low >= RHYTHM_RULES["low_consecutive_limit"]:
                    recommendations.append({
                        "type": "detonation_needed",
                        "after_scene": sorted_scenes[i].get("scene_code", ""),
                        "message": f"连续{consecutive_low}个低情感场景(≤{RHYTHM_RULES['low_threshold']})，需要安排引爆点(情感值≥{RHYTHM_RULES['detonation_emotion']})",
                        "suggested_emotion": RHYTHM_RULES["detonation_emotion"],
                    })
                    rhythm_status = "pacing_slow"
            else:
                consecutive_low = 0

        avg_emotion = sum(emotion_values) / len(emotion_values) if emotion_values else 5
        emotion_range = max(emotion_values) - min(emotion_values) if emotion_values else 0

        return AgentResult(
            status="completed",
            data={
                "project_id": project_id,
                "rhythm_status": rhythm_status,
                "recommendations": recommendations,
                "stats": {
                    "avg_emotion": round(avg_emotion, 1),
                    "emotion_range": emotion_range,
                    "scene_count": len(emotion_values),
                    "high_count": sum(1 for e in emotion_values if e >= 8),
                    "low_count": sum(1 for e in emotion_values if e <= 3),
                },
            },
        )

    async def _record_rejection(self, project_id: str, payload: dict) -> AgentResult:
        scene_id = payload.get("scene_id", "")
        if not scene_id:
            return AgentResult(status="failed", data={"error": "scene_id required"}, issues=["scene_id required"])

        key = f"{project_id}:{scene_id}"
        self._rejection_tracker[key] += 1
        count = self._rejection_tracker[key]

        needs_escalation = count >= MAX_CONSECUTIVE_REJECTIONS

        return AgentResult(
            status="completed",
            data={
                "scene_id": scene_id,
                "rejection_count": count,
                "max_allowed": MAX_CONSECUTIVE_REJECTIONS,
                "needs_human_intervention": needs_escalation,
                "message": f"场景 {scene_id} 已被驳回 {count} 次" + (f"，达到{MAX_CONSECUTIVE_REJECTIONS}次阈值，需要人类介入" if needs_escalation else ""),
            },
        )

    async def _check_escalation(self, project_id: str, payload: dict) -> AgentResult:
        escalation_items = []
        for key, count in self._rejection_tracker.items():
            if key.startswith(f"{project_id}:") and count >= MAX_CONSECUTIVE_REJECTIONS:
                scene_id = key.split(":", 1)[1]
                escalation_items.append({
                    "scene_id": scene_id,
                    "rejection_count": count,
                    "action": "human_intervention_required",
                    "message": f"场景 {scene_id} 已被连续驳回 {count} 次，需要人类介入决策",
                })

        return AgentResult(
            status="completed",
            data={
                "project_id": project_id,
                "escalation_items": escalation_items,
                "needs_attention": len(escalation_items) > 0,
            },
        )

    async def _build_context(self, task: AgentTask) -> dict:
        project_id = task.project_id
        payload = task.payload

        if task.task_type == "plan_project":
            layer0 = await self.storage.get_layer0(project_id)
            project_info = f"""## 项目设定
目标字数: {payload.get('target_word_count', '未设定')}
工作模式: {payload.get('work_mode', 'standard')}
核心矛盾: {layer0_value(layer0, 'core_contradiction', '未设定')}
题材: {layer0_value(layer0, 'genre', '未设定')}
风格: {layer0_value(layer0, 'style', '未设定')}"""
            return {"project_info": project_info}

        elif task.task_type == "analyze_progress":
            chapters = await self.storage.get_chapter_outlines(project_id)
            chapter_data = []
            for ch in (chapters or []):
                ctx = await self.storage.get_chapter_context(project_id, ch.get("id", ""))
                finished = sum(1 for s in ctx.get("scenes", []) if s.get("status") in ("final", "approved"))
                total = len(ctx.get("scenes", []))
                chapter_data.append({
                    "chapter": ch.get("chapter_number"),
                    "title": ch.get("title"),
                    "progress": f"{finished}/{total}" if total else "0/0",
                    "status": ch.get("status", "draft"),
                })
            progress_data = json.dumps({"chapters": chapter_data}, ensure_ascii=False, indent=2)
            return {"progress_data": progress_data}

        elif task.task_type == "resolve_conflict":
            return {"conflict_description": payload.get("conflict", "未描述") + "\n\n涉及元素: " + json.dumps(payload.get("elements", []), ensure_ascii=False)}

        return {}

    def _select_skill(self, task_type: str) -> Skill:
        return self.skills[task_type]
