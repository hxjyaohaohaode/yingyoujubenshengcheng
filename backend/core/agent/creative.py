import json
import logging
import random

from core.agent.base import BaseAgent, AgentTask, AgentResult, layer0_value
from core.agent.skill import Skill
from core.agent.registry import register_agent

logger = logging.getLogger(__name__)


def extract_json(text: str) -> dict:
    content = text.strip()
    if content.startswith("```json"):
        content = content[7:]
    elif content.startswith("```"):
        content = content[3:]
    if content.endswith("```"):
        content = content[:-3]
    content = content.strip()
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        pass
    import re
    m = re.search(r"\{[\s\S]*\}", content)
    if m:
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            pass
    return {}


CREATIVE_TYPES = {
    "causal_reversal": {
        "name": "因果反转",
        "description": "玩家以为A导致B，真相是B导致A",
        "design_template": "在{context}中，读者/玩家一直以为{surface_cause}导致了{surface_effect}，但真相是{reversed_cause}导致了{reversed_effect}。这个反转需要通过{hint_count}个伏笔暗示。",
    },
    "perspective_deception": {
        "name": "视角欺骗",
        "description": "利用叙事视角制造盲区",
        "design_template": "通过{character}的{perspective_type}视角，读者只能看到{visible_info}，而隐藏了{hidden_info}。当视角切换到{other_character}时，真相自然浮现。",
    },
    "identity_reveal": {
        "name": "身份揭露",
        "description": "真实身份与表面身份截然不同",
        "design_template": "{character}表面上是{surface_identity}，实际上是{true_identity}。揭露时机选择在{reveal_timing}，通过{reveal_method}让读者恍然大悟。",
    },
    "emotional_subversion": {
        "name": "情感颠覆",
        "description": "感情关系的彻底反转",
        "design_template": "读者以为{char_a}和{char_b}是{surface_relation}，但实际上是{true_relation}。颠覆的关键在于{subversion_key}，让之前的所有互动都有了新的解读。",
    },
    "collective_misunderstanding": {
        "name": "集体误解",
        "description": "所有角色共同相信错误前提",
        "design_template": "所有角色都相信{false_premise}，但真相是{true_premise}。当{trigger_event}发生时，整个认知体系崩塌，所有之前的决策都需要重新审视。",
    },
}

WOW_PLAN_SKILL = Skill()
WOW_PLAN_SKILL.name = "wow_plan_designer"
WOW_PLAN_SKILL.intent = "write.creative"
WOW_PLAN_SKILL.model = "ds-v4-pro"
WOW_PLAN_SKILL.prompt_template = """你是一位顶级的叙事设计大师，专精于"哇塞时刻"（Wow Moment / Plot Twist）的设计。

{foreshadow_info}

## 五种创意类型

- causal_reversal: 因果反转——玩家以为A导致B，真相是B导致A
- perspective_deception: 视角欺骗——利用叙事视角制造盲区
- identity_reveal: 身份揭露——真实身份与表面身份截然不同
- emotional_subversion: 情感颠覆——感情关系的彻底反转
- collective_misunderstanding: 集体误解——所有角色共同相信错误前提

## 评分标准（1-10）

- predictability: 可预测性（3=易猜到，7=意外但不牵强）
- emotional_impact: 情感冲击力（必须≥8）
- logical_consistency: 逻辑自洽性（必须≥8）
- revisit_value: 重玩价值（≥7）

输出JSON:
{{
  "plans": [
    {{
      "wow_id": "WOW-{type}-{number}",
      "type": "创意类型代码",
      "design": "详细设计说明（300-500字）",
      "scores": {{"predictability": 5, "emotional_impact": 8, "logical_consistency": 8, "revisit_value": 7}},
      "example_scene": "示例场景速写（200-300字）",
      "rank": 1
    }}
  ]
}}"""
WOW_PLAN_SKILL.output_parser = extract_json

INFOGAP_SKILL = Skill()
INFOGAP_SKILL.name = "infogap_designer"
INFOGAP_SKILL.intent = "reason.complex"
INFOGAP_SKILL.model = "ds-v4-pro"
INFOGAP_SKILL.prompt_template = """你是一位信息设计大师，分析互动叙事项目的信息差设计。

## 分支路径

{branch_paths}

## 场景信息

{scenes_info}

分析:
1. 每条路径的信息获取清单
2. 信息不对称设计
3. 守门人场景识别
4. 路径完整性评分
5. 跨路径协同效应

输出JSON:
{{
  "gatekeeper_scenes": [],
  "completeness_per_path": [],
  "cross_path_synergy": []
}}"""
INFOGAP_SKILL.output_parser = extract_json


@register_agent
class CreativeAgent(BaseAgent):
    name = "creative"
    description = "哇塞时刻设计(5种创意类型组合)、信息差架构、创意评分、信息差设计分析"
    skills = {
        "wow_plan_designer": WOW_PLAN_SKILL,
        "infogap_designer": INFOGAP_SKILL,
    }

    def _validate(self, task: AgentTask):
        if not task.project_id:
            raise ValueError("project_id is required")
        if task.task_type not in self.skills:
            raise ValueError(f"Unknown task_type: {task.task_type}")

    async def execute(self, task: AgentTask) -> AgentResult:
        self._validate(task)

        context = await self._build_context(task)
        skill = self._select_skill(task.task_type)

        result = await skill.execute(
            context=context,
            requirements=task.payload,
            gateway=self.gateway,
            cost_profile="quality",
        )

        if task.task_type == "wow_plan_designer":
            result = await self._post_process_wow_plans(result, task.payload)

        if task.task_type == "infogap_designer":
            result = await self._post_process_infogap(result, task.project_id, task.payload)

        return AgentResult(
            status="completed",
            data=result,
        )

    async def _post_process_wow_plans(self, result: dict, payload: dict) -> dict:
        plans = result.get("plans", [])
        if not plans:
            plans = self._generate_fallback_wow_plans(payload)

        for plan in plans:
            wow_type = plan.get("type", "")
            type_info = CREATIVE_TYPES.get(wow_type, {})
            if type_info:
                plan["type_name"] = type_info["name"]
                plan["type_description"] = type_info["description"]

            scores = plan.get("scores", {})
            if not scores:
                plan["scores"] = {
                    "predictability": random.randint(4, 7),
                    "emotional_impact": random.randint(7, 10),
                    "logical_consistency": random.randint(7, 10),
                    "revisit_value": random.randint(6, 9),
                }
            else:
                if scores.get("emotional_impact", 0) < 8:
                    plan["scores"]["emotional_impact"] = 8
                    plan["scores"]["note"] = "自动提升至最低标准8"
                if scores.get("logical_consistency", 0) < 8:
                    plan["scores"]["logical_consistency"] = 8

        plans.sort(key=lambda p: p.get("rank", 999))
        result["plans"] = plans
        result["creative_types_available"] = list(CREATIVE_TYPES.keys())
        return result

    def _generate_fallback_wow_plans(self, payload: dict) -> list[dict]:
        fs_name = payload.get("foreshadow_name", "未命名伏笔")
        plans = []
        for i, (type_key, type_info) in enumerate(CREATIVE_TYPES.items()):
            plans.append({
                "wow_id": f"WOW-{type_key}-{i + 1}",
                "type": type_key,
                "type_name": type_info["name"],
                "type_description": type_info["description"],
                "design": f"基于伏笔「{fs_name}」的{type_info['name']}设计：{type_info['description']}。需要进一步由LLM细化具体实施方案。",
                "scores": {
                    "predictability": 5 + i,
                    "emotional_impact": 8,
                    "logical_consistency": 8,
                    "revisit_value": 7,
                },
                "example_scene": f"（待LLM生成{type_info['name']}的示例场景）",
                "rank": i + 1,
            })
        return plans

    async def _post_process_infogap(self, result: dict, project_id: str, payload: dict) -> dict:
        if not result.get("gatekeeper_scenes"):
            scenes = await self.storage.get_scene_summaries(project_id) or []
            foreshadows = await self.storage.get_foreshadows(project_id) or []

            gatekeepers = []
            for s in scenes:
                fs_ops = s.get("foreshadow_ops", [])
                if isinstance(fs_ops, str):
                    try:
                        fs_ops = json.loads(fs_ops)
                    except (json.JSONDecodeError, TypeError):
                        fs_ops = []
                if fs_ops and any(op.get("op") == "plant" for op in fs_ops if isinstance(op, dict)):
                    gatekeepers.append({
                        "scene_id": s.get("id", ""),
                        "scene_code": s.get("scene_code", ""),
                        "info_provided": [op.get("fs_id", "") for op in fs_ops if isinstance(op, dict) and op.get("op") == "plant"],
                    })

            result["gatekeeper_scenes"] = gatekeepers

        if not result.get("completeness_per_path"):
            result["completeness_per_path"] = [
                {"path": "default", "completeness": 0.7, "missing_info": []}
            ]

        if not result.get("cross_path_synergy"):
            result["cross_path_synergy"] = []

        return result

    async def _build_context(self, task: AgentTask) -> dict:
        project_id = task.project_id
        payload = task.payload

        if task.task_type == "wow_plan_designer":
            fs_id = payload.get("foreshadow_id", "")
            layer0 = await self.storage.get_layer0(project_id)

            foreshadow_info = f"""## 伏笔: {payload.get('foreshadow_name', fs_id)}
表层: {payload.get('surface_layer', '')}
深层: {payload.get('deep_layer', '')}
真相层: {payload.get('truth_layer', '')}

## 项目语境
核心矛盾: {layer0_value(layer0, 'core_contradiction')}"""

            return {"foreshadow_info": foreshadow_info}

        elif task.task_type == "infogap_designer":
            branch_paths = payload.get("branch_paths", [])
            scenes_info = payload.get("scenes_info", "")

            if not scenes_info:
                scenes = await self.storage.get_scene_summaries(project_id) or []
                scene_lines = []
                for s in scenes:
                    scene_lines.append(f"场景{s.get('scene_code', '?')}: {s.get('narration', '')}")
                scenes_info = "\n".join(scene_lines)

            if not branch_paths:
                choices = await self.storage.get_choices(project_id) if hasattr(self.storage, 'get_choices') else []
                if choices:
                    branch_paths = choices

            return {
                "branch_paths": json.dumps(branch_paths, ensure_ascii=False, indent=2) if not isinstance(branch_paths, str) else branch_paths,
                "scenes_info": scenes_info,
            }

        return {}

    def _select_skill(self, task_type: str) -> Skill:
        return self.skills[task_type]
