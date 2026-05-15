import logging
from collections import defaultdict
from sqlalchemy.ext.asyncio import AsyncSession
from core.narrative.memory_store import get_all_memories_for_context

logger = logging.getLogger(__name__)

CATEGORY_LABELS: dict[str, str] = {
    "characters": "角色当前状态",
    "active_foreshadows": "活跃伏笔",
    "recent_events": "最近事件",
    "relationships": "角色关系动态",
    "worldbuilding": "世界观规则",
    "themes": "主题约束",
}

SECTION_ORDER = [
    "角色当前状态",
    "活跃伏笔",
    "最近事件",
    "角色关系动态",
    "世界观规则",
    "主题约束",
]


async def build_narrative_context(db: AsyncSession, project_id: str) -> str:
    memories = await get_all_memories_for_context(db, project_id)

    grouped: dict[str, list[str]] = defaultdict(list)
    for m in memories:
        label = CATEGORY_LABELS.get(m.category, m.category)
        grouped[label].append(m.content)

    if not grouped:
        return ""

    parts = ["【当前叙事状态 —— 生成前必须阅读】", ""]

    for label in SECTION_ORDER:
        items = grouped.get(label)
        if not items:
            continue
        parts.append(f"## {label}")
        for item in items:
            parts.append(f"{item}")
        parts.append("")

    parts.append("---")
    parts.append("在生成新内容时，必须基于以上叙事状态，确保：")
    parts.append("1. 角色行为、性格、说话风格与当前状态一致")
    parts.append("2. 所有活跃伏笔必须有所推进或揭示")
    parts.append("3. 事件因果链必须连续，不可跳时间线")
    parts.append("4. 不违反已建立的世界观规则")
    parts.append("5. 情节走向不偏离主题约束")

    return "\n".join(parts)