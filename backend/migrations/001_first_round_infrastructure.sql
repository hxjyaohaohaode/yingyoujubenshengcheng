-- ============================================================
-- 第一轮重构: 基础设施层 — 数据库迁移
-- 执行方式: psql -U postgres -d script_engine -f this_file.sql
-- ============================================================

-- 启用 pgvector 扩展
CREATE EXTENSION IF NOT EXISTS vector;

-- ============================================================
-- 1. token_usage 表: 记录模型调用的 token 用量和费用
-- ============================================================
CREATE TABLE IF NOT EXISTS token_usage (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    agent_name VARCHAR(50) NOT NULL,
    intent VARCHAR(50) NOT NULL,
    model VARCHAR(50) NOT NULL,
    input_tokens INTEGER NOT NULL,
    output_tokens INTEGER NOT NULL,
    cost NUMERIC(10, 6) NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_token_usage_project ON token_usage(project_id, created_at);
CREATE INDEX IF NOT EXISTS idx_token_usage_agent ON token_usage(project_id, agent_name);

-- ============================================================
-- 2. embeddings 表: pgvector 向量存储
-- ============================================================
CREATE TABLE IF NOT EXISTS embeddings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    content_type VARCHAR(20) NOT NULL,
    content_id UUID NOT NULL,
    chunk_text TEXT NOT NULL,
    embedding vector(1536),
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_embeddings_project ON embeddings(project_id, content_type);
CREATE INDEX IF NOT EXISTS idx_embeddings_vector ON embeddings
    USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
