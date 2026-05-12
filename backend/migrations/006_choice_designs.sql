CREATE TABLE IF NOT EXISTS choice_designs (
    id VARCHAR(36) PRIMARY KEY,
    project_id VARCHAR(36) NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    section_id VARCHAR(36) NOT NULL REFERENCES chapter_sections(id) ON DELETE CASCADE,
    choice_number INTEGER NOT NULL,
    text TEXT NOT NULL,
    consequence_direct TEXT,
    consequence_indirect TEXT,
    consequence_long_term TEXT,
    character_impact TEXT NOT NULL DEFAULT '[]',
    is_hidden BOOLEAN NOT NULL DEFAULT 0,
    hidden_condition TEXT,
    moral_alignment VARCHAR(20) NOT NULL DEFAULT 'gray',
    branch_target VARCHAR(200),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_choice_designs_project_id ON choice_designs(project_id);
CREATE INDEX IF NOT EXISTS ix_choice_designs_section_id ON choice_designs(section_id);
