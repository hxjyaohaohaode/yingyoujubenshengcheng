from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
import logging

logger = logging.getLogger(__name__)

INIT_SQL = """
CREATE TABLE IF NOT EXISTS search_cache (
    cache_key TEXT PRIMARY KEY,
    entity_name TEXT NOT NULL DEFAULT '',
    result_json TEXT NOT NULL DEFAULT '[]',
    searched_at TEXT NOT NULL DEFAULT '',
    ttl INTEGER NOT NULL DEFAULT 86400
)
"""


async def init_search_cache(db: AsyncSession):
    try:
        await db.execute(text(INIT_SQL))
        await db.commit()
        logger.info("搜索缓存表初始化完成")
    except Exception as e:
        logger.error("搜索缓存表初始化失败: %s", str(e))