"""
初始化数据库：创建所有表和索引
使用方法: python scripts/init_db.py [--drop] [--seed]
"""
import asyncio
import sys
import os
import argparse

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from sqlalchemy import text  # type: ignore
from backend.database import engine, Base


MODELS = [
    "models.project",
    "models.character",
    "models.foreshadow",
    "models.chapter",
    "models.scene",
    "models.element",
    "models.audit",
    "models.agent_task",
    "models.emotion_curve",
    "models.project_config",
]

for model in MODELS:
    __import__(model)


INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_characters_project ON characters(project_id)",
    "CREATE INDEX IF NOT EXISTS idx_foreshadows_project ON foreshadows(project_id)",
    "CREATE INDEX IF NOT EXISTS idx_foreshadows_status ON foreshadows(current_status)",
    "CREATE INDEX IF NOT EXISTS idx_chapters_project ON chapters(project_id)",
    "CREATE INDEX IF NOT EXISTS idx_chapters_number ON chapters(project_id, chapter_number)",
    "CREATE INDEX IF NOT EXISTS idx_scenes_project ON scenes(project_id)",
    "CREATE INDEX IF NOT EXISTS idx_scenes_chapter ON scenes(chapter_id)",
    "CREATE INDEX IF NOT EXISTS idx_scenes_status ON scenes(status)",
    "CREATE INDEX IF NOT EXISTS idx_scenes_code ON scenes(project_id, scene_code)",
    "CREATE INDEX IF NOT EXISTS idx_elements_project ON elements(project_id)",
    "CREATE INDEX IF NOT EXISTS idx_elements_type ON elements(project_id, element_type)",
    "CREATE INDEX IF NOT EXISTS idx_agent_tasks_status ON agent_tasks(status)",
    "CREATE INDEX IF NOT EXISTS idx_agent_tasks_project ON agent_tasks(project_id, task_type)",
    "CREATE INDEX IF NOT EXISTS idx_audit_records_scene ON audit_records(scene_id)",
    "CREATE INDEX IF NOT EXISTS idx_foreshadow_relations_from ON foreshadow_relations(from_fs_id)",
    "CREATE INDEX IF NOT EXISTS idx_foreshadow_relations_to ON foreshadow_relations(to_fs_id)",
    "CREATE UNIQUE INDEX IF NOT EXISTS uq_character_relations ON character_relations(project_id, char_a_id, char_b_id)",
    "CREATE UNIQUE INDEX IF NOT EXISTS uq_project_config ON project_config(project_id, config_key)",
]

MIGRATIONS = [
    "ALTER TABLE character_relations ADD COLUMN IF NOT EXISTS info_asymmetry JSON DEFAULT '{{}}'",
    "ALTER TABLE character_relations ADD COLUMN IF NOT EXISTS is_hidden BOOLEAN DEFAULT FALSE",
    "ALTER TABLE character_relations ADD COLUMN IF NOT EXISTS arc_direction VARCHAR(20) DEFAULT 'stable'",
    "ALTER TABLE character_relations ADD COLUMN IF NOT EXISTS trigger_condition TEXT",
    "ALTER TABLE character_relations ADD COLUMN IF NOT EXISTS arc_milestones JSON DEFAULT '[]'",
]


async def create_tables():
    print("创建数据库表...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("所有表创建完成！")


async def drop_tables():
    print("删除所有数据库表...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    print("所有表已删除！")


async def create_indexes():
    print("创建索引...")
    async with engine.begin() as conn:
        for idx_sql in INDEXES:
            try:
                await conn.execute(text(idx_sql))
            except Exception as e:
                print(f"  警告: {e}")
    print("所有索引创建完成！")


async def run_migrations():
    print("运行数据库迁移...")
    async with engine.begin() as conn:
        for mig_sql in MIGRATIONS:
            try:
                await conn.execute(text(mig_sql))
            except Exception as e:
                print(f"  警告: {e}")
    print("数据库迁移完成！")


async def run_seed():
    print("种子数据功能已移除，请通过前端界面创建项目数据")


async def main(drop=False, seed=False):
    try:
        if drop:
            await drop_tables()
        await create_tables()
        await run_migrations()
        await create_indexes()
        if seed:
            await run_seed()
        print("\n数据库初始化成功！")
    except Exception as e:
        error_msg = str(e)
        if "Can\'t connect" in error_msg or "Connection refused" in error_msg or "could not connect" in error_msg.lower():
            print(f"\n数据库连接失败: 请检查 DATABASE_URL 环境变量和数据库服务是否运行")
            print(f"  当前 DATABASE_URL: {os.getenv('DATABASE_URL', '未设置')}")
        elif "No module named" in error_msg:
            print(f"\n缺少依赖: {e}\n请运行: pip install -r requirements.txt")
        else:
            print(f"\n数据库初始化失败: {e}")
        sys.exit(1)
    finally:
        await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="初始化数据库")
    parser.add_argument("--drop", action="store_true", help="先删除所有表再创建")
    parser.add_argument("--seed", action="store_true", help="初始化后运行种子数据")
    args = parser.parse_args()
    asyncio.run(main(drop=args.drop, seed=args.seed))
