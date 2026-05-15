"""
Agent 基类: 所有 Agent 的统一接口。

每个 Agent 必须:
  1. 声明 name（唯一标识）和 description（人类可读描述）
  2. 实现 skills 字典（skill_name -> Skill 实例）
  3. 实现 _validate, _build_context, _select_skill 方法
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional
import logging

from core.gateway.client import ModelGateway, ModelResponse
from core.rag.retriever import RAGRetriever
from core.storage.service import StorageService
from core.agent.skill import Skill

logger = logging.getLogger(__name__)


def layer0_value(layer0: dict, key: str, default: str = "") -> str:
    val = layer0.get(key, {})
    if isinstance(val, dict):
        return str(val.get("value", default))
    return str(val) if val is not None else default


@dataclass
class AgentTask:
    task_id: str
    agent_name: str
    task_type: str
    project_id: str
    payload: dict
    cost_profile: str = "balanced"


@dataclass
class AgentResult:
    status: str
    data: dict
    token_usage: Optional[dict] = None
    issues: list = field(default_factory=list)


class BaseAgent(ABC):
    """Agent 基类"""

    name: str
    description: str
    skills: dict[str, Skill]
    checkers: list = []

    def __init__(self, gateway: ModelGateway, rag: RAGRetriever,
                 storage: StorageService):
        self.gateway = gateway
        self.rag = rag
        self.storage = storage

    async def execute(self, task: AgentTask) -> AgentResult:
        self._validate(task)

        try:
            context = await self._build_context(task)
        except Exception as e:
            logger.error("Agent %s _build_context failed: %s", self.name, str(e)[:200])
            context = {}

        skill = self._select_skill(task.task_type)

        result_data = await skill.execute(
            context=context,
            requirements=task.payload,
            gateway=self.gateway,
            cost_profile=task.cost_profile,
        )

        await self._post_process(task, result_data)

        return AgentResult(
            status="completed",
            data=result_data,
        )

    def build_prompt(self, task: AgentTask) -> str:
        self._validate(task)
        skill = self._select_skill(task.task_type)
        context = {}
        try:
            import asyncio
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    context = loop.run_in_executor(pool, lambda: asyncio.run(self._build_context(task)))
                    context = {}
            else:
                context = asyncio.run(self._build_context(task))
        except Exception:
            context = {}
        return skill.render_prompt(context, task.payload)

    async def execute_with_prompt(self, task: AgentTask, enriched_prompt: str) -> AgentResult:
        self._validate(task)
        skill = self._select_skill(task.task_type)

        result_data = await skill.execute_with_custom_prompt(
            custom_prompt=enriched_prompt,
            requirements=task.payload,
            gateway=self.gateway,
            cost_profile=task.cost_profile,
        )

        await self._post_process(task, result_data)

        return AgentResult(
            status="completed",
            data=result_data,
        )

    @abstractmethod
    def _validate(self, task: AgentTask):
        ...

    @abstractmethod
    async def _build_context(self, task: AgentTask) -> dict:
        ...

    @abstractmethod
    def _select_skill(self, task_type: str) -> Skill:
        ...

    async def _post_process(self, task: AgentTask, result: dict):
        pass
