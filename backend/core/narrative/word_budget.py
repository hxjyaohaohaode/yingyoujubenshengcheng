"""
字数分配与控制引擎
- 自动分配：总字数 → 每章 → 每场景
- 生成后统计实际字数
- 超出区间自动触发LLM压缩/扩展
"""
import re
from dataclasses import dataclass
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from core.narrative.models import WordBudget


@dataclass
class BudgetAllocation:
    chapter_id: str
    chapter_name: str
    target_words: int
    actual_words: int = 0
    scene_budgets: list[dict] = None

    def __post_init__(self):
        if self.scene_budgets is None:
            self.scene_budgets = []


def count_chinese_words(text: str) -> int:
    chinese_chars = re.findall(r'[\u4e00-\u9fff\u3000-\u303f\uff00-\uffef]', text)
    return len(chinese_chars)


def allocate_chapter_budget(total_words: int, chapter_count: int, chapter_weights: Optional[list[float]] = None) -> list[int]:
    if chapter_weights:
        total_weight = sum(chapter_weights)
        return [int(total_words * w / total_weight) for w in chapter_weights]
    return [int(total_words / chapter_count) for _ in range(chapter_count)]


def allocate_scene_budget(chapter_words: int, scene_count: int) -> list[int]:
    return [int(chapter_words / scene_count) for _ in range(scene_count)]


def is_within_budget(actual_words: int, target_words: int, tolerance_pct: float = 20.0) -> bool:
    lower = target_words * (1 - tolerance_pct / 100)
    upper = target_words * (1 + tolerance_pct / 100)
    return lower <= actual_words <= upper


def get_compression_instruction(actual_words: int, target_words: int) -> str:
    target = int(target_words)
    ratio = actual_words / target_words if target_words > 0 else 1
    if 0.8 <= ratio <= 1.2:
        return ""
    if ratio > 1.2:
        return f"当前字数{actual_words}字超出目标{target}字。请精简内容，删除冗余描述和重复对话，压缩至约{target}字，同时保留核心情节和关键对话。"
    else:
        return f"当前字数{actual_words}字不足目标{target}字。请丰富场景描述、角色心理刻画和环境细节，扩展至约{target}字，但不要添加新情节。"


async def save_budget(db: AsyncSession, project_id: str, chapter_id: str, scene_id: Optional[str],
                      target_words: int, tolerance_pct: float = 20.0) -> WordBudget:
    budget = WordBudget(
        project_id=project_id,
        chapter_id=chapter_id,
        scene_id=scene_id,
        target_words=target_words,
        tolerance_pct=tolerance_pct,
    )
    db.add(budget)
    await db.commit()
    return budget


async def update_actual_words(db: AsyncSession, scene_id: str, actual_words: int):
    result = await db.execute(select(WordBudget).where(WordBudget.scene_id == scene_id))
    budget = result.scalar_one_or_none()
    if budget:
        budget.actual_words = actual_words
        await db.commit()


async def get_project_budgets(db: AsyncSession, project_id: str) -> list[WordBudget]:
    result = await db.execute(select(WordBudget).where(WordBudget.project_id == project_id))
    return list(result.scalars().all())