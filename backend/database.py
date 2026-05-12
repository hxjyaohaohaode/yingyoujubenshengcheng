from contextlib import asynccontextmanager, contextmanager
from typing import AsyncGenerator

from sqlalchemy import func, text
from sqlalchemy import select as sa_select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

from config import DATABASE_URL, DATABASE_URL_SYNC, APP_ENV

_IS_SQLITE = DATABASE_URL.startswith("sqlite")

if _IS_SQLITE:
    engine = create_async_engine(
        DATABASE_URL,
        echo=False,
        connect_args={"check_same_thread": False},
        pool_pre_ping=True,
    )
else:
    _pool_size = 10 if APP_ENV == "development" else 20
    _max_overflow = 20 if APP_ENV == "development" else 10
    engine = create_async_engine(
        DATABASE_URL,
        echo=False,
        pool_size=_pool_size,
        max_overflow=_max_overflow,
        pool_pre_ping=True,
        pool_recycle=3600,
    )

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        try:
            yield session
        finally:
            await session.close()


from sqlalchemy import create_engine as create_sync_engine
from sqlalchemy.orm import Session, sessionmaker as sync_sessionmaker

_IS_SQLITE_SYNC = DATABASE_URL_SYNC.startswith("sqlite")

if _IS_SQLITE_SYNC:
    _sync_engine = create_sync_engine(
        DATABASE_URL_SYNC,
        connect_args={"check_same_thread": False},
        pool_pre_ping=True,
    )
else:
    _sync_engine = create_sync_engine(
        DATABASE_URL_SYNC,
        pool_pre_ping=True,
        pool_recycle=3600,
    )
SyncSessionLocal = sync_sessionmaker(bind=_sync_engine)


@contextmanager
def get_db_sync():
    session = SyncSessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


async def check_db_health() -> bool:
    try:
        async with async_session_factory() as session:
            await session.execute(text("SELECT 1"))
            return True
    except Exception:
        return False


async def bulk_create(db: AsyncSession, instances: list) -> None:
    db.add_all(instances)
    await db.commit()


async def paginate(query, db: AsyncSession, limit: int, offset: int) -> tuple[list, int]:
    count_query = sa_select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar_one()
    items = (await db.execute(query.limit(limit).offset(offset))).scalars().all()
    return items, total


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db():
    await engine.dispose()
    _sync_engine.dispose()
