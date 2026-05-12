"""
Checker 基类: 程序化检测器，零 LLM 成本。
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class CheckResult:
    name: str
    passed: bool
    detail: str = ""
    suggestion: str = ""


class BaseChecker(ABC):
    """程序化检测器基类"""

    name: str

    @abstractmethod
    def check(self, scene_data: dict, context: dict) -> CheckResult:
        ...
