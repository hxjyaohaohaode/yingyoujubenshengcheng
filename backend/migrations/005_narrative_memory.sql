CREATE TABLE IF NOT EXISTS narrative_memory (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    memory_type TEXT NOT NULL,
    category TEXT NOT NULL,
    entity_id TEXT,
    content TEXT NOT NULL,
    scene_anchor TEXT,
    chapter_anchor TEXT,
    priority INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS word_budget (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    chapter_id TEXT REFERENCES chapters(id) ON DELETE CASCADE,
    scene_id TEXT REFERENCES scenes(id) ON DELETE CASCADE,
    target_words INTEGER NOT NULL,
    actual_words INTEGER DEFAULT 0,
    tolerance_pct REAL DEFAULT 20.0
);