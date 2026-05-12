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

from core.gateway.client import ModelGateway, ModelResponse
from core.rag.retriever import RAGRetriever
from core.storage.service import StorageService
from core.agent.skill import Skill


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

        context = await self._build_context(task)

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
