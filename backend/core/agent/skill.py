"""
Skill 基类: Agent 内部的最小能力单元。

一个 Skill = 一段 prompt 模板 + 一个模型意图 + 一个输出解析器。
缺失关键变量时抛出异常而非静默填空。
"""

import re
import logging
from typing import Callable, Optional, Set
from core.gateway.client import ModelGateway

logger = logging.getLogger(__name__)

CRITICAL_VARIABLES: Set[str] = {
    "world_settings", "character_states", "scene_code",
    "project_id", "user_requirements", "genre", "style",
    "story_context", "scene_context", "characters",
    "core_contradiction", "target_word_count",
}


class Skill:
    """Skill 基类"""

    name: str
    intent: str
    prompt_template: str
    output_parser: Callable[[str], dict]
    model: Optional[str] = None

    async def execute(
        self,
        context: dict,
        requirements: dict,
        gateway: ModelGateway,
        cost_profile: str = "balanced",
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> dict:
        prompt = self._render(context, requirements)

        invoke_kwargs = {
            "intent": self.intent,
            "messages": [{"role": "user", "content": prompt}],
            "cost_profile": cost_profile,
        }
        if self.model is not None:
            invoke_kwargs["model_override"] = self.model
        if max_tokens is not None:
            invoke_kwargs["max_tokens"] = max_tokens  # type: ignore
        if temperature is not None:
            invoke_kwargs["temperature"] = temperature  # type: ignore

        response = await gateway.invoke(**invoke_kwargs)

        return self.output_parser(response.content)

    def _render(self, context: dict, requirements: dict) -> str:
        variables = {**context, **requirements}
        try:
            return self.prompt_template.format(**variables)
        except KeyError:
            missing = set(re.findall(r'\{(\w+)\}', self.prompt_template))
            missing_vars = missing - set(variables.keys())
            critical_missing = missing_vars & CRITICAL_VARIABLES

            if critical_missing:
                logger.warning(
                    "Skill '%s' 缺失关键变量: %s，将用空字符串填充但可能影响生成质量",
                    self.name, critical_missing,
                )

            safe_vars = {k: variables.get(k, "") for k in missing}
            return self.prompt_template.format(**safe_vars)
