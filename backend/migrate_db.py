import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "script_engine.db")
print(f"Database: {DB_PATH}")

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

cursor.execute("PRAGMA table_info(characters)")
existing_cols = {row[1] for row in cursor.fetchall()}
print(f"Existing columns: {existing_cols}")

required_cols = {
    "dark_secret": "TEXT",
    "arc_description": "TEXT",
    "behavior_inevitable": "TEXT DEFAULT '[]'",
    "behavior_never": "TEXT DEFAULT '[]'",
    "behavior_conditional": "TEXT DEFAULT '[]'",
}

for col_name, col_type in required_cols.items():
    if col_name not in existing_cols:
        sql = f"ALTER TABLE characters ADD COLUMN {col_name} {col_type}"
        print(f"  Adding: {sql}")
        cursor.execute(sql)
    else:
        print(f"  Already exists: {col_name}")

cursor.execute("PRAGMA table_info(chapters)")
existing_chapter_cols = {row[1] for row in cursor.fetchall()}
print(f"\nChapter columns: {existing_chapter_cols}")

required_chapter_cols = {
    "core_conflict": "TEXT",
    "foreshadow_tasks": "TEXT DEFAULT '[]'",
    "key_turning_points": "TEXT DEFAULT '[]'",
    "branch_structure": "TEXT",
}

for col_name, col_type in required_chapter_cols.items():
    if col_name not in existing_chapter_cols:
        sql = f"ALTER TABLE chapters ADD COLUMN {col_name} {col_type}"
        print(f"  Adding: {sql}")
        cursor.execute(sql)
    else:
        print(f"  Already exists: {col_name}")

cursor.execute("PRAGMA table_info(scenes)")
existing_scene_cols = {row[1] for row in cursor.fetchall()}
print(f"\nScene columns: {existing_scene_cols}")

required_scene_cols = {
    "foreshadow_ops": "TEXT DEFAULT '[]'",
    "causal_chain": "TEXT DEFAULT '{}'",
    "choices": "TEXT DEFAULT '[]'",
    "suggestions": "TEXT DEFAULT '[]'",
    "emotion_level": "INTEGER DEFAULT 5",
}

for col_name, col_type in required_scene_cols.items():
    if col_name not in existing_scene_cols:
        sql = f"ALTER TABLE scenes ADD COLUMN {col_name} {col_type}"
        print(f"  Adding: {sql}")
        cursor.execute(sql)
    else:
        print(f"  Already exists: {col_name}")

conn.commit()
conn.close()
print("\nMigration complete!")
