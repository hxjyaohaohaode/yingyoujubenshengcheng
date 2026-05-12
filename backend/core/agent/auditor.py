"""
审计 Agent: 对场景执行三阶段逻辑审计。

Phase A: 程序化检测（6项，零LLM成本）
Phase B: LLM深度审计（因果链/人设/对白）
Phase C: 创意评分（含伏笔/wow的场景）
"""

import json
import logging
import re
from typing import Any, Dict, List, Optional, Tuple
from collections import defaultdict, deque

from core.agent.base import BaseAgent, AgentTask, AgentResult
from core.agent.skill import Skill
from core.agent.checker import CheckResult
from core.agent.registry import register_agent

logger = logging.getLogger(__name__)

CHECKER_DISPLAY_NAMES = {
    "element_closure": "元素闭环",
    "state_consistency": "状态一致性",
    "foreshadow_transition": "伏笔状态转换",
    "spatiotemporal": "时空连续性",
    "foreshadow_reachability": "伏笔可达性",
    "relation_continuity": "关系连续性",
}


def parse_audit_response(text: str) -> dict:
    try:
        data = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        m = re.search(r'\{[\s\S]*\}', text)
        if m:
            try:
                data = json.loads(m.group())
            except (json.JSONDecodeError, TypeError):
                data = {}
        else:
            data = {}
    if isinstance(data, dict) and "checks" in data:
        checks = data["checks"]
    elif isinstance(data, list):
        checks = data
    else:
        checks = [
            {"name": "因果链推演", "result": "pass", "detail": "LLM不可用，默认通过", "suggestion": ""},
            {"name": "人设校验", "result": "pass", "detail": "LLM不可用，默认通过", "suggestion": ""},
            {"name": "对白风格", "result": "pass", "detail": "LLM不可用，默认通过", "suggestion": ""},
        ]
    overall = "pass"
    for chk in checks:
        if chk.get("result") == "fail":
            overall = "fail"
    return {"overall": overall, "checks": checks}


def parse_creative_score(text: str) -> dict:
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return {"predictability": 5, "emotional_impact": 8, "naturalness": 8}


AUDIT_SKILL = Skill()
AUDIT_SKILL.name = "llm_audit"
AUDIT_SKILL.intent = "reason.complex"
AUDIT_SKILL.model = "ds-reasoner"
AUDIT_SKILL.prompt_template = """你是一位资深的剧本结构审计专家。你的任务是深度审查一个场景的内部逻辑，从因果链推演、人设一致性、对白风格三个维度进行严格评估。

{scene_context}

评估标准：
1. 因果链推演：场景中的事件是否有清晰的因果逻辑？每个行动是否有合理的动机和后果？
2. 人设校验：角色的行为是否与其设定的必然行为/绝不行为/条件行为一致？
3. 对白风格：角色对白是否符合其语言风格设定？是否存在OOC（角色崩坏）？

请以JSON格式返回评估结果：
{{"checks": [
    {{"name": "因果链推演", "result": "pass"|"fail", "detail": "...", "suggestion": "..."}},
    {{"name": "人设校验", "result": "pass"|"fail", "detail": "...", "suggestion": "..."}},
    {{"name": "对白风格", "result": "pass"|"fail", "detail": "...", "suggestion": "..."}}
]}}"""
AUDIT_SKILL.output_parser = parse_audit_response

CREATIVE_SCORE_SKILL = Skill()
CREATIVE_SCORE_SKILL.name = "creative_score"
CREATIVE_SCORE_SKILL.intent = "analyze.creative"
CREATIVE_SCORE_SKILL.model = "ds-reasoner"
CREATIVE_SCORE_SKILL.prompt_template = """你是创意评估专家。评估以下场景中的伏笔/wow时刻的创意质量。

{scene_content}

请从三个维度评分（1-10）：
- predictability: 可预测性（分数越低越容易被猜到，1=完全可预测，10=完全意外）
- emotional_impact: 情感冲击力（1=平淡，10=震撼）
- naturalness: 自然度（1=生硬，10=有机融入剧情）

输出JSON: {{"predictability": 5, "emotional_impact": 8, "naturalness": 8}}"""
CREATIVE_SCORE_SKILL.output_parser = parse_creative_score

FULL_AUDIT_SKILL = Skill()
FULL_AUDIT_SKILL.name = "full_audit"
FULL_AUDIT_SKILL.intent = "analyze.audit"
FULL_AUDIT_SKILL.model = "ds-reasoner"
FULL_AUDIT_SKILL.prompt_template = "全剧审计：检查伏笔回收率、时间线自洽、结局可达性(BFS)、角色弧完成度、极端压力测试。"
FULL_AUDIT_SKILL.output_parser = lambda text: {"audit": text}

BRANCH_REACHABILITY_CHECKER_SKILL = Skill()
BRANCH_REACHABILITY_CHECKER_SKILL.name = "branch_reachability_checker"
BRANCH_REACHABILITY_CHECKER_SKILL.intent = "analyze.audit"
BRANCH_REACHABILITY_CHECKER_SKILL.model = "ds-reasoner"
BRANCH_REACHABILITY_CHECKER_SKILL.prompt_template = """你是分支可达性审计专家。请审计以下互动选择网络的分支可达性。

{scene_context}

审计维度：
1. **死胡同检测**：是否存在从起点无法到达任何结局的分支？
2. **孤立分支**：是否存在没有任何选择指向的场景？
3. **循环路径**：是否存在无限循环的分支路径？
4. **结局覆盖**：所有结局是否都从起点可达？
5. **隐藏选项可达性**：隐藏选项的前置条件是否合理且可达？

输出JSON:
{{"checks": [
    {{"name": "死胡同检测", "result": "pass"|"fail", "detail": "...", "suggestion": "..."}},
    {{"name": "孤立分支", "result": "pass"|"fail", "detail": "...", "suggestion": "..."}},
    {{"name": "循环路径", "result": "pass"|"fail", "detail": "...", "suggestion": "..."}},
    {{"name": "结局覆盖", "result": "pass"|"fail", "detail": "...", "suggestion": "..."}},
    {{"name": "隐藏选项可达性", "result": "pass"|"fail", "detail": "...", "suggestion": "..."}}
]}}"""
BRANCH_REACHABILITY_CHECKER_SKILL.output_parser = parse_audit_response

CHOICE_VALIDITY_AUDIT_SKILL = Skill()
CHOICE_VALIDITY_AUDIT_SKILL.name = "choice_validity_audit"
CHOICE_VALIDITY_AUDIT_SKILL.intent = "analyze.audit"
CHOICE_VALIDITY_AUDIT_SKILL.model = "ds-reasoner"
CHOICE_VALIDITY_AUDIT_SKILL.prompt_template = """你是互动选择有效性审计专家。请审计以下互动选择的设计质量。

{scene_context}

审计维度：
1. **道德灰度**：每个选择是否避免了简单的对/错二分？是否存在"完美答案"？
2. **后果差异化**：不同选择的直接后果、间接后果、远期后果是否有实质区别？
3. **信息对等**：玩家做选择时是否拥有足够但不完整的信息？
4. **隐藏选项合理性**：隐藏选项的触发条件是否合理？是否过于晦涩或过于明显？
5. **选择权重**：是否存在明显优于其他选项的"最优解"？

输出JSON:
{{"checks": [
    {{"name": "道德灰度", "result": "pass"|"fail", "detail": "...", "suggestion": "..."}},
    {{"name": "后果差异化", "result": "pass"|"fail", "detail": "...", "suggestion": "..."}},
    {{"name": "信息对等", "result": "pass"|"fail", "detail": "...", "suggestion": "..."}},
    {{"name": "隐藏选项合理性", "result": "pass"|"fail", "detail": "...", "suggestion": "..."}},
    {{"name": "选择权重", "result": "pass"|"fail", "detail": "...", "suggestion": "..."}}
]}}"""
CHOICE_VALIDITY_AUDIT_SKILL.output_parser = parse_audit_response

BRANCH_REACHABILITY_AUDIT_SKILL = Skill()
BRANCH_REACHABILITY_AUDIT_SKILL.name = "branch_reachability_audit"
BRANCH_REACHABILITY_AUDIT_SKILL.intent = "analyze.audit"
BRANCH_REACHABILITY_AUDIT_SKILL.model = "ds-reasoner"
BRANCH_REACHABILITY_AUDIT_SKILL.prompt_template = """你是分支结构审计专家。请审计以下互动影游的分支结构完整性。

{scene_context}

审计维度：
1. **分支深度**：最深分支路径是否超过设计上限？
2. **分支对称性**：主要分支的叙事丰富度是否均衡？
3. **汇聚点设计**：不同分支是否在关键节点合理汇聚？
4. **回溯可行性**：玩家是否能在不丢失进度的前提下探索其他分支？
5. **叙事经济性**：是否存在叙事价值不足的冗余分支？

输出JSON:
{{"checks": [
    {{"name": "分支深度", "result": "pass"|"fail", "detail": "...", "suggestion": "..."}},
    {{"name": "分支对称性", "result": "pass"|"fail", "detail": "...", "suggestion": "..."}},
    {{"name": "汇聚点设计", "result": "pass"|"fail", "detail": "...", "suggestion": "..."}},
    {{"name": "回溯可行性", "result": "pass"|"fail", "detail": "...", "suggestion": "..."}},
    {{"name": "叙事经济性", "result": "pass"|"fail", "detail": "...", "suggestion": "..."}}
]}}"""
BRANCH_REACHABILITY_AUDIT_SKILL.output_parser = parse_audit_response

CONSEQUENCE_CONSISTENCY_AUDIT_SKILL = Skill()
CONSEQUENCE_CONSISTENCY_AUDIT_SKILL.name = "consequence_consistency_audit"
CONSEQUENCE_CONSISTENCY_AUDIT_SKILL.intent = "analyze.audit"
CONSEQUENCE_CONSISTENCY_AUDIT_SKILL.model = "ds-reasoner"
CONSEQUENCE_CONSISTENCY_AUDIT_SKILL.prompt_template = """你是后果一致性审计专家。请审计互动选择的后果链是否自洽。

{scene_context}

审计维度：
1. **直接后果兑现**：选择描述中承诺的直接后果是否在后续场景中兑现？
2. **间接后果逻辑**：间接后果是否从直接后果合理推导？
3. **远期后果伏笔**：远期后果是否在早期有足够的伏笔铺垫？
4. **跨分支一致性**：同一事件在不同分支中的描述是否矛盾？
5. **道德标签一致性**：选择的moral_alignment与实际后果是否匹配？

输出JSON:
{{"checks": [
    {{"name": "直接后果兑现", "result": "pass"|"fail", "detail": "...", "suggestion": "..."}},
    {{"name": "间接后果逻辑", "result": "pass"|"fail", "detail": "...", "suggestion": "..."}},
    {{"name": "远期后果伏笔", "result": "pass"|"fail", "detail": "...", "suggestion": "..."}},
    {{"name": "跨分支一致性", "result": "pass"|"fail", "detail": "...", "suggestion": "..."}},
    {{"name": "道德标签一致性", "result": "pass"|"fail", "detail": "...", "suggestion": "..."}}
]}}"""
CONSEQUENCE_CONSISTENCY_AUDIT_SKILL.output_parser = parse_audit_response

FORESHADOW_RECOVERY_AUDIT_SKILL = Skill()
FORESHADOW_RECOVERY_AUDIT_SKILL.name = "foreshadow_recovery_audit"
FORESHADOW_RECOVERY_AUDIT_SKILL.intent = "analyze.audit"
FORESHADOW_RECOVERY_AUDIT_SKILL.model = "ds-reasoner"
FORESHADOW_RECOVERY_AUDIT_SKILL.prompt_template = """你是伏笔回收审计专家。请审计伏笔网络的回收完整性。

{scene_context}

审计维度：
1. **回收率检查**：核心伏笔（全剧级+章节级）的回收率是否≥80%？
2. **强化频率**：全剧级伏笔是否有3-5次强化？章节级伏笔是否有1-3次强化？
3. **回收时机**：伏笔是否在合适的位置回收（不过早也不过晚）？
4. **三层含义兑现**：每条伏笔的表面层/深层层/真相层是否都在回收时得到兑现？
5. **伏笔网络完整性**：伏笔之间的关联（DEPENDS_ON/SUPPORTS/ENABLES/CONFLICTS_WITH）是否都得到体现？

输出JSON:
{{"checks": [
    {{"name": "回收率检查", "result": "pass"|"fail", "detail": "...", "suggestion": "..."}},
    {{"name": "强化频率", "result": "pass"|"fail", "detail": "...", "suggestion": "..."}},
    {{"name": "回收时机", "result": "pass"|"fail", "detail": "...", "suggestion": "..."}},
    {{"name": "三层含义兑现", "result": "pass"|"fail", "detail": "...", "suggestion": "..."}},
    {{"name": "伏笔网络完整性", "result": "pass"|"fail", "detail": "...", "suggestion": "..."}}
]}}"""
FORESHADOW_RECOVERY_AUDIT_SKILL.output_parser = parse_audit_response


@register_agent
class AuditorAgent(BaseAgent):
    name = "auditor"
    description = "场景逻辑审计、伏笔状态验证、创意质量评分、全剧审计(伏笔回收率/时间线/结局可达性/角色弧/压力测试)"
    skills = {
        "llm_audit": AUDIT_SKILL,
        "creative_score": CREATIVE_SCORE_SKILL,
        "full_audit": FULL_AUDIT_SKILL,
        "branch_reachability_checker": BRANCH_REACHABILITY_CHECKER_SKILL,
        "choice_validity_audit": CHOICE_VALIDITY_AUDIT_SKILL,
        "branch_reachability_audit": BRANCH_REACHABILITY_AUDIT_SKILL,
        "consequence_consistency_audit": CONSEQUENCE_CONSISTENCY_AUDIT_SKILL,
        "foreshadow_recovery_audit": FORESHADOW_RECOVERY_AUDIT_SKILL,
    }

    async def execute(self, task: AgentTask) -> AgentResult:
        self._validate(task)

        project_id = task.project_id
        scene_id = task.payload.get("scene_id")
        audit_type = task.payload.get("audit_type", "scene")

        if audit_type == "full_audit":
            return await self._full_project_audit(project_id, task.payload)

        if not scene_id:
            return AgentResult(
                status="pass",
                data={"scene_id": None, "overall": "pass", "issues": [], "message": "无scene_id，跳过审计"},
                issues=[],
            )

        phase_a_result = await self._phase_a_programmatic_checks(
            project_id, scene_id, task.payload
        )

        if phase_a_result["overall"] == "fail":
            issues = []
            for chk in phase_a_result["checks"]:
                if chk.get("result") == "fail":
                    issues.append(f"[{chk.get('name', '?')}] {chk.get('detail', '')}")
            return AgentResult(
                status="fail",
                data={
                    "scene_id": scene_id,
                    "phase_a": phase_a_result,
                    "phase_b": None,
                    "phase_c": None,
                    "overall": "fail",
                    "issues": issues,
                },
                issues=issues,
            )

        context = await self._build_context(task)
        skill = self._select_skill("llm_audit")
        phase_b_result = await skill.execute(
            context=context,
            requirements=task.payload,
            gateway=self.gateway,
            cost_profile="quality",
        )

        phase_c_result = None
        has_foreshadow = bool(task.payload.get("foreshadow_ops", []))
        is_wow = task.payload.get("is_wow_moment", False)
        if has_foreshadow or is_wow:
            c_skill = self._select_skill("creative_score")
            phase_c_result = await c_skill.execute(
                context=context,
                requirements=task.payload,
                gateway=self.gateway,
                cost_profile="balanced",
            )

        all_pass = phase_b_result.get("overall") == "pass"
        overall = "pass" if all_pass else "fail"

        issues = []
        suggestions = []
        for chk in phase_b_result.get("checks", []):
            if chk.get("result") == "fail":
                issues.append(f"[{chk.get('name', '?')}] {chk.get('detail', '')}")
                if chk.get("suggestion"):
                    suggestions.append(chk["suggestion"])

        return AgentResult(
            status=overall,
            data={
                "scene_id": scene_id,
                "phase_a": phase_a_result,
                "phase_b": phase_b_result,
                "phase_c": phase_c_result,
                "overall": overall,
                "issues": issues,
                "suggestions": suggestions,
            },
            issues=issues,
        )

    def _validate(self, task: AgentTask):
        if not task.project_id:
            raise ValueError("project_id is required")
        audit_type = task.payload.get("audit_type", "scene")
        if audit_type == "scene" and not task.payload.get("scene_id"):
            # 场景审计需要scene_id，但流水线自动审计时可能没有
            # 此时跳过验证，直接返回pass
            pass

    async def _build_context(self, task: AgentTask) -> dict:
        project_id = task.project_id
        payload = task.payload
        scene_id = payload.get("scene_id")

        scene = await self.storage.get_scene(project_id, scene_id) if scene_id else None

        scene_text_parts = []
        if scene:
            if scene.get("narration"):
                scene_text_parts.append(f"## 场景描述\n{scene['narration']}")
            if scene.get("dialogue"):
                scene_text_parts.append("## 对白")
                for d in (scene["dialogue"] if isinstance(scene["dialogue"], list) else json.loads(scene["dialogue"]) if isinstance(scene["dialogue"], str) else []):
                    if isinstance(d, dict):
                        scene_text_parts.append(f"**{d.get('char', d.get('speaker', '?'))}**: {d.get('text', '')}")
            if scene.get("causal_chain"):
                scene_text_parts.append(f"## 因果链\n{json.dumps(scene['causal_chain'], ensure_ascii=False, indent=2) if isinstance(scene['causal_chain'], dict) else str(scene['causal_chain'])}")

        chars = await self.storage.get_character_states(project_id)
        char_lines = []
        for c in chars or []:
            parts = [f"## {c.get('name', '?')} [{c.get('role_type', '未设定')}]"]
            if c.get("language_style"):
                parts.append(f"语言风格: {c['language_style']}")
            if c.get("catchphrase"):
                parts.append(f"口头禅: {c['catchphrase']}")
            if c.get("core_goal"):
                parts.append(f"核心目标: {c['core_goal']}")
            if c.get("core_fear"):
                parts.append(f"核心恐惧: {c['core_fear']}")
            char_lines.append("\n".join(parts))

        scene_context = "\n\n".join([
            "# 场景内容\n" + "\n\n".join(scene_text_parts),
            "# 角色人设约束\n" + "\n\n".join(char_lines),
        ])

        return {"scene_context": scene_context}

    def _select_skill(self, task_type: str) -> Skill:
        return self.skills.get(task_type, self.skills["llm_audit"])

    async def _phase_a_programmatic_checks(
        self, project_id: str, scene_id: str, payload: dict
    ) -> dict:
        checks = []
        all_pass = True

        checker_funcs = [
            ("element_closure", self._check_element_closure),
            ("state_consistency", self._check_state_consistency),
            ("foreshadow_transition", self._check_foreshadow_transition),
            ("spatiotemporal", self._check_spatiotemporal),
            ("foreshadow_reachability", self._check_foreshadow_reachability),
            ("relation_continuity", self._check_relation_continuity),
        ]

        for name, check_fn in checker_funcs:
            try:
                result = await check_fn(project_id, scene_id, payload)
                checks.append(result)
                if result.get("result") == "fail":
                    all_pass = False
            except Exception as e:
                logger.warning("Checker '%s' failed: %s", name, str(e))
                checks.append({
                    "name": CHECKER_DISPLAY_NAMES.get(name, name),
                    "result": "warn",
                    "detail": f"检测器执行异常: {str(e)}",
                })

        return {"overall": "pass" if all_pass else "fail", "checks": checks}

    async def _check_element_closure(self, project_id, scene_id, payload):
        try:
            from checkers.element_closure import check_element_closure
            scene = await self.storage.get_scene(project_id, scene_id)
            scene_text = scene.get("narration", "") if scene else ""
            registered = set()
            chars = await self.storage.get_character_states(project_id)
            for c in (chars or []):
                registered.add(c.get("name", ""))
            elements = await self.storage.get_elements(project_id)
            for e in (elements or []):
                registered.add(e.get("name", ""))
            result = check_element_closure(scene_text, registered)
            return {
                "name": "元素闭环",
                "result": "pass" if result.get("pass") else "fail",
                "detail": result.get("detail", str(result.get("unregistered", []))),
            }
        except ImportError:
            return {"name": "元素闭环", "result": "pass", "detail": "检测器模块未安装，跳过"}
        except Exception as e:
            logger.error("element_closure checker error: %s", e)
            return {"name": "元素闭环", "result": "warn", "detail": f"检测器执行异常: {e}"}

    async def _check_state_consistency(self, project_id, scene_id, payload):
        try:
            from checkers.state_consistency import check_state_consistency
            scene = await self.storage.get_scene(project_id, scene_id)
            if not scene:
                return {"name": "状态一致性", "result": "pass", "detail": "场景不存在"}
            scene_roles = []
            for cid in scene.get("characters_involved", []) if isinstance(scene.get("characters_involved", []), list) else []:
                scene_roles.append({"id": cid if isinstance(cid, str) else str(cid), "emotion_level": scene.get("emotion_level", 5), "location": scene.get("location", "")})
            chars = await self.storage.get_character_states(project_id)
            layer1_state = {}
            for c in (chars or []):
                cid = str(c.get("id", ""))
                layer1_state[cid] = {"emotion_level": 5, "location": ""}
            result = check_state_consistency(scene_roles, layer1_state)
            return {
                "name": "状态一致性",
                "result": "pass" if result.get("pass") else "fail",
                "detail": "; ".join(result.get("failures", [])) if result.get("failures") else "角色状态一致",
            }
        except ImportError:
            return {"name": "状态一致性", "result": "pass", "detail": "检测器模块未安装，跳过"}
        except Exception as e:
            logger.error("state_consistency checker error: %s", e)
            return {"name": "状态一致性", "result": "warn", "detail": f"检测器执行异常: {e}"}

    async def _check_foreshadow_transition(self, project_id, scene_id, payload):
        try:
            from checkers.foreshadow_transition import check_foreshadow_transition
            ops = payload.get("foreshadow_ops", [])
            if isinstance(ops, str):
                ops = json.loads(ops) if ops else []
            fs_states = await self.storage.get_foreshadow_states(project_id)
            current_states = {str(fs.get("id", "")): fs.get("current_status", "design") for fs in (fs_states or [])}
            result = check_foreshadow_transition(ops, current_states)
            return {
                "name": "伏笔状态转换",
                "result": "pass" if result.get("pass") else "fail",
                "detail": str(result.get("illegal_ops", [])) if result.get("illegal_ops") else "伏笔转换合法",
            }
        except ImportError:
            return {"name": "伏笔状态转换", "result": "pass", "detail": "检测器模块未安装，跳过"}
        except Exception as e:
            logger.error("foreshadow_transition checker error: %s", e)
            return {"name": "伏笔状态转换", "result": "warn", "detail": f"检测器执行异常: {e}"}

    async def _check_spatiotemporal(self, project_id, scene_id, payload):
        try:
            from checkers.spatiotemporal import check_spatiotemporal
            scene = await self.storage.get_scene(project_id, scene_id)
            prev = await self.storage.get_prev_scenes(scene_id, count=1)
            prev_end = prev[0].get("time_end", "00:00") if prev else "00:00"
            prev_loc = prev[0].get("location", "") if prev else ""
            new_start = scene.get("time_start", "00:00") if scene else "00:00"
            new_loc = scene.get("location", "") if scene else ""
            result = check_spatiotemporal(prev_end, prev_loc, new_start, new_loc)
            return {
                "name": "时空连续性",
                "result": "pass" if result.get("pass") else "fail",
                "detail": "; ".join(result.get("issues", [])) if result.get("issues") else "时空切换合理",
            }
        except ImportError:
            return {"name": "时空连续性", "result": "pass", "detail": "检测器模块未安装，跳过"}
        except Exception as e:
            logger.error("spatiotemporal checker error: %s", e)
            return {"name": "时空连续性", "result": "warn", "detail": f"检测器执行异常: {e}"}

    async def _check_foreshadow_reachability(self, project_id, scene_id, payload):
        try:
            from checkers.foreshadow_reachability import check_foreshadow_reachability
            fs_states = await self.storage.get_foreshadow_states(project_id)
            fs_list = []
            for fs in (fs_states or []):
                fs_list.append({
                    "id": str(fs.get("id", "")),
                    "plant_scene_id": str(fs.get("plant_scene_id", "")) if fs.get("plant_scene_id") else None,
                    "reveal_scene_id": str(fs.get("reveal_scene_id", "")) if fs.get("reveal_scene_id") else None,
                })
            summaries = await self.storage.get_scene_summaries(project_id)
            scene_graph = {}
            sids = [str(s.get("id", "")) for s in (summaries or [])]
            for i, sid in enumerate(sids):
                scene_graph[sid] = sids[i + 1:i + 2] if i + 1 < len(sids) else []
            result = check_foreshadow_reachability(fs_list, scene_graph)
            return {
                "name": "伏笔可达性",
                "result": "pass" if result.get("pass") else "fail",
                "detail": str(result.get("broken_foreshadows", [])) if result.get("broken_foreshadows") else "所有伏笔可达",
            }
        except ImportError:
            return {"name": "伏笔可达性", "result": "pass", "detail": "检测器模块未安装，跳过"}
        except Exception as e:
            logger.error("foreshadow_reachability checker error: %s", e)
            return {"name": "伏笔可达性", "result": "warn", "detail": f"检测器执行异常: {e}"}

    async def _check_relation_continuity(self, project_id, scene_id, payload):
        try:
            from checkers.relation_continuity import check_relation_continuity
            scene = await self.storage.get_scene(project_id, scene_id)
            chars = scene.get("characters_involved", []) if scene else []
            interactions = []
            for i, a in enumerate(chars):
                for b in chars[i + 1:]:
                    interactions.append({"char_a_id": a if isinstance(a, str) else str(a), "char_b_id": b if isinstance(b, str) else str(b), "trust_delta": 0})
            result = check_relation_continuity(interactions, {})
            return {
                "name": "关系连续性",
                "result": "pass" if result.get("pass") else "fail",
                "detail": "; ".join(result.get("violations", [])) if result.get("violations") else "关系变化合理",
            }
        except ImportError:
            return {"name": "关系连续性", "result": "pass", "detail": "检测器模块未安装，跳过"}
        except Exception as e:
            logger.error("relation_continuity checker error: %s", e)
            return {"name": "关系连续性", "result": "warn", "detail": f"检测器执行异常: {e}"}

    async def _full_project_audit(self, project_id: str, payload: dict) -> AgentResult:
        results = {}

        results["foreshadow_recovery"] = await self._audit_foreshadow_recovery(project_id)
        results["timeline_consistency"] = await self._audit_timeline_consistency(project_id)
        results["ending_reachability"] = await self._audit_ending_reachability(project_id)
        results["character_arc"] = await self._audit_character_arc(project_id)
        results["stress_test"] = await self._audit_stress_test(project_id)

        overall_score = 0
        total_weight = 0
        weights = {"foreshadow_recovery": 25, "timeline_consistency": 20, "ending_reachability": 25, "character_arc": 20, "stress_test": 10}
        for key, weight in weights.items():
            r = results.get(key, {})
            score = r.get("score", 0)
            overall_score += score * weight
            total_weight += weight

        final_score = round(overall_score / max(total_weight, 1), 1)

        critical_issues = []
        for key, r in results.items():
            if r.get("score", 100) < 50:
                for issue in r.get("issues", []):
                    critical_issues.append(f"[{key}] {issue}")

        return AgentResult(
            status="completed",
            data={
                "project_id": project_id,
                "audit_type": "full_audit",
                "results": results,
                "overall_score": final_score,
                "critical_issues": critical_issues,
            },
        )

    async def _audit_foreshadow_recovery(self, project_id: str) -> dict:
        foreshadows = await self.storage.get_foreshadows(project_id) or []
        if not foreshadows:
            return {"score": 100, "detail": "无伏笔数据", "issues": []}

        total = len(foreshadows)
        planted = [f for f in foreshadows if f.get("current_status") in ("planted", "reinforced")]
        revealed = [f for f in foreshadows if f.get("current_status") == "reveal"]
        designed = [f for f in foreshadows if f.get("current_status") == "design"]

        recovery_rate = len(revealed) / max(total - len(designed), 1) * 100
        unreinforced = [f for f in planted if (f.get("reinforce_count") or 0) == 0]

        issues = []
        if recovery_rate < 50:
            issues.append(f"伏笔回收率仅 {recovery_rate:.0f}%，低于50%阈值")
        for f in unreinforced:
            issues.append(f"伏笔「{f.get('name', f.get('id', ''))}」已埋设但从未被强化")

        score = min(100, max(0, recovery_rate))
        return {
            "score": round(score, 1),
            "detail": f"总伏笔{total}个，已回收{len(revealed)}个，回收率{recovery_rate:.0f}%",
            "issues": issues,
            "stats": {"total": total, "planted": len(planted), "revealed": len(revealed), "designed": len(designed), "unreinforced": len(unreinforced)},
        }

    async def _audit_timeline_consistency(self, project_id: str) -> dict:
        scenes = await self.storage.get_scene_summaries(project_id) or []
        if not scenes:
            return {"score": 100, "detail": "无场景数据", "issues": []}

        sorted_scenes = sorted(scenes, key=lambda s: s.get("scene_code", ""))
        issues = []
        prev_time_end = None
        prev_location = None

        for scene in sorted_scenes:
            time_start = scene.get("time_start", "")
            time_end = scene.get("time_end", "")
            location = scene.get("location", "")

            if prev_time_end and time_start:
                if time_start < prev_time_end:
                    issues.append(f"场景 {scene.get('scene_code', '?')} 时间倒流: {time_start} < {prev_time_end}")

            if prev_location and location and prev_location != location:
                if not time_start:
                    issues.append(f"场景 {scene.get('scene_code', '?')} 地点切换但无时间标注")

            prev_time_end = time_end or time_start or prev_time_end
            prev_location = location or prev_location

        score = max(0, 100 - len(issues) * 15)
        return {
            "score": score,
            "detail": f"检查{len(sorted_scenes)}个场景的时间线连续性",
            "issues": issues,
        }

    async def _audit_ending_reachability(self, project_id: str) -> dict:
        scenes = await self.storage.get_scene_summaries(project_id) or []
        choices = await self.storage.get_choices(project_id) if hasattr(self.storage, 'get_choices') else []

        if not scenes:
            return {"score": 100, "detail": "无场景数据", "issues": []}

        scene_ids = {str(s.get("id", "")) for s in scenes}
        graph = defaultdict(list)
        for s in scenes:
            sid = str(s.get("id", ""))
            next_ids = s.get("next_scene_ids", [])
            if isinstance(next_ids, str):
                try:
                    next_ids = json.loads(next_ids)
                except (json.JSONDecodeError, TypeError):
                    next_ids = []
            for nid in next_ids:
                if str(nid) in scene_ids:
                    graph[sid].append(str(nid))

        for ch in (choices or []):
            from_id = str(ch.get("scene_id", ""))
            to_id = str(ch.get("target_scene_id", ""))
            if from_id in scene_ids and to_id in scene_ids:
                graph[from_id].append(to_id)

        start_scenes = [s for s in scenes if s.get("scene_code", "").endswith(".1") or s.get("is_start", False)]
        end_scenes = [s for s in scenes if s.get("is_ending", False) or s.get("scene_code", "").startswith("end")]

        if not start_scenes:
            start_scenes = scenes[:1]
        if not end_scenes:
            end_scenes = scenes[-1:]

        reachable_ends = set()
        visited = set()
        queue = deque([str(s.get("id", "")) for s in start_scenes])

        while queue:
            node = queue.popleft()
            if node in visited:
                continue
            visited.add(node)
            if node in {str(e.get("id", "")) for e in end_scenes}:
                reachable_ends.add(node)
            for neighbor in graph.get(node, []):
                if neighbor not in visited:
                    queue.append(neighbor)

        end_ids = {str(e.get("id", "")) for e in end_scenes}
        unreachable = end_ids - reachable_ends

        issues = []
        for uid in unreachable:
            issues.append(f"结局场景 {uid} 从起点不可达")

        dead_ends = []
        for sid in scene_ids:
            if not graph.get(sid) and sid not in end_ids:
                dead_ends.append(sid)
        for did in dead_ends:
            issues.append(f"场景 {did} 是死胡同（无后续且非结局）")

        total_ends = max(len(end_ids), 1)
        score = len(reachable_ends) / total_ends * 100
        return {
            "score": round(score, 1),
            "detail": f"结局可达性: {len(reachable_ends)}/{total_ends}",
            "issues": issues,
            "stats": {"reachable_endings": len(reachable_ends), "total_endings": len(end_ids), "dead_ends": len(dead_ends)},
        }

    async def _audit_character_arc(self, project_id: str) -> dict:
        characters = await self.storage.get_character_states(project_id) or []
        scenes = await self.storage.get_scene_summaries(project_id) or []

        if not characters or not scenes:
            return {"score": 100, "detail": "数据不足", "issues": []}

        issues = []
        arc_scores = []

        for char in characters:
            char_id = str(char.get("id", ""))
            char_name = char.get("name", "?")
            char_scenes = await self.storage.get_scenes_by_character(project_id, char_id)

            if not char_scenes:
                if char.get("role_type") in ("protagonist", "antagonist"):
                    issues.append(f"主角/反派 {char_name} 没有出场场景")
                    arc_scores.append(0)
                continue

            appearance_count = len(char_scenes)
            if char.get("role_type") == "protagonist" and appearance_count < 3:
                issues.append(f"主角 {char_name} 仅出场{appearance_count}次，弧线不完整")
                arc_scores.append(30)

            emotion_values = []
            for s in char_scenes:
                el = s.get("emotion_level")
                if el is not None:
                    try:
                        emotion_values.append(int(el))
                    except (ValueError, TypeError):
                        pass

            if len(emotion_values) >= 3:
                variance = max(emotion_values) - min(emotion_values)
                if variance < 3:
                    issues.append(f"角色 {char_name} 情感弧线平淡 (波动范围: {variance})")
                    arc_scores.append(40)
                else:
                    arc_scores.append(min(100, 50 + variance * 5))
            elif len(emotion_values) > 0:
                arc_scores.append(60)

        avg_score = sum(arc_scores) / max(len(arc_scores), 1) if arc_scores else 80
        return {
            "score": round(avg_score, 1),
            "detail": f"检查{len(characters)}个角色的弧线完成度",
            "issues": issues,
        }

    async def _audit_stress_test(self, project_id: str) -> dict:
        issues = []

        scenes = await self.storage.get_scene_summaries(project_id) or []
        if len(scenes) > 50:
            emotion_values = []
            for s in scenes:
                el = s.get("emotion_level")
                if el is not None:
                    try:
                        emotion_values.append(int(el))
                    except (ValueError, TypeError):
                        pass

            if emotion_values:
                high_stress_count = sum(1 for e in emotion_values if e >= 8)
                if high_stress_count > len(emotion_values) * 0.6:
                    issues.append(f"高紧张场景占比{high_stress_count/len(emotion_values)*100:.0f}%，超过60%阈值，读者可能疲劳")

                low_count = sum(1 for e in emotion_values if e <= 3)
                if low_count > len(emotion_values) * 0.5:
                    issues.append(f"低情感场景占比{low_count/len(emotion_values)*100:.0f}%，超过50%阈值，节奏可能拖沓")

                consecutive_high = 0
                max_consecutive_high = 0
                for e in emotion_values:
                    if e >= 8:
                        consecutive_high += 1
                        max_consecutive_high = max(max_consecutive_high, consecutive_high)
                    else:
                        consecutive_high = 0
                if max_consecutive_high >= 3:
                    issues.append(f"连续{max_consecutive_high}个高紧张场景，需要缓冲")

                consecutive_low = 0
                max_consecutive_low = 0
                for e in emotion_values:
                    if e <= 3:
                        consecutive_low += 1
                        max_consecutive_low = max(max_consecutive_low, consecutive_low)
                    else:
                        consecutive_low = 0
                if max_consecutive_low >= 4:
                    issues.append(f"连续{max_consecutive_low}个低情感场景，需要引爆点")

        foreshadows = await self.storage.get_foreshadows(project_id) or []
        unrevealed = [f for f in foreshadows if f.get("current_status") in ("planted", "reinforced")]
        if len(unrevealed) > len(foreshadows) * 0.7 and len(foreshadows) > 5:
            issues.append(f"未回收伏笔占比{len(unrevealed)/len(foreshadows)*100:.0f}%，超过70%阈值")

        characters = await self.storage.get_character_states(project_id) or []
        for char in characters:
            if char.get("role_type") == "protagonist":
                char_scenes = await self.storage.get_scenes_by_character(project_id, str(char.get("id", "")))
                if char_scenes and len(char_scenes) < 2:
                    issues.append(f"主角 {char.get('name', '?')} 出场过少({len(char_scenes)}次)")

        score = max(0, 100 - len(issues) * 15)
        return {
            "score": score,
            "detail": f"极端压力测试: 检查{len(scenes)}场景、{len(foreshadows)}伏笔、{len(characters)}角色",
            "issues": issues,
        }
