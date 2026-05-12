-- ============================================================
-- 第五轮: 章节分段表
-- 注意: JSON 字段使用 TEXT 类型以兼容 SQLite。
-- PostgreSQL 环境下，建议使用 JSONB 类型替代 TEXT。
-- 生产环境推荐通过 init_db() (SQLAlchemy create_all) 建表，
-- 会自动使用 JSONB。
-- ============================================================

CREATE TABLE IF NOT EXISTS chapter_sections (
    id VARCHAR(36) PRIMARY KEY,
    project_id VARCHAR(36) NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    chapter_id VARCHAR(36) NOT NULL REFERENCES chapters(id) ON DELETE CASCADE,
    section_number INTEGER NOT NULL,
    title VARCHAR(200),
    word_target INTEGER NOT NULL DEFAULT 1000,
    emotion_target INTEGER NOT NULL DEFAULT 5,
    scene_ids TEXT NOT NULL DEFAULT '[]',
    choices TEXT,
    foreshadow_tasks TEXT NOT NULL DEFAULT '[]',
    focus_characters TEXT NOT NULL DEFAULT '[]',
    branch_type VARCHAR(50) NOT NULL DEFAULT 'exploration',
    summary TEXT,
    status VARCHAR(20) NOT NULL DEFAULT 'draft',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_chapter_sections_project_id ON chapter_sections(project_id);
CREATE INDEX IF NOT EXISTS ix_chapter_sections_chapter_id ON chapter_sections(chapter_id);
