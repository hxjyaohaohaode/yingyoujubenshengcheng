"""
编排模板: 定义各种应用场景的流水线编排。
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Step:
    agent: str
    skill: str
    input_from: list[str] = field(default_factory=list)
    output_to: str = "next_step"
    condition: Optional[str] = None
    cost_profile: str = "balanced"
    timeout: int = 600
    retry_count: int = 2


@dataclass
class Phase:
    name: str
    steps: list[Step] = field(default_factory=list)
    human_gate: bool = False
    max_parallel: int = 1
    repeat_until: Optional[str] = None


@dataclass
class PipelineTemplate:
    name: str
    description: str
    phases: list[Phase] = field(default_factory=list)
    scale_config: dict = field(default_factory=dict)
