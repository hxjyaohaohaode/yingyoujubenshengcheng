-- ============================================================
-- 第二回合: 补充 pipeline_state 表（状态机必需）
-- 兼容 PostgreSQL 和 SQLite
-- ============================================================

CREATE TABLE IF NOT EXISTS pipeline_state (
    project_id VARCHAR(36) PRIMARY KEY,
    template_name VARCHAR(100) NOT NULL DEFAULT '',
    current_phase_index INTEGER NOT NULL DEFAULT 0,
    current_step_index INTEGER NOT NULL DEFAULT 0,
    status VARCHAR(20) NOT NULL DEFAULT 'not_started',
    result_data TEXT DEFAULT '{}',
    error_message TEXT DEFAULT '',
    task_results TEXT DEFAULT '[]',
    config TEXT DEFAULT '{}',
    run_id VARCHAR(36),
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
