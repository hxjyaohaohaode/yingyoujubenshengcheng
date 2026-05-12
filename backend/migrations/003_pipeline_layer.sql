-- ============================================================
-- 第三轮重构: 编排层 — 数据库迁移（补充索引）
-- pipeline_state 表已在 002 迁移中创建，此处仅添加索引
-- ============================================================

CREATE INDEX IF NOT EXISTS idx_pipeline_state_status ON pipeline_state(status);
