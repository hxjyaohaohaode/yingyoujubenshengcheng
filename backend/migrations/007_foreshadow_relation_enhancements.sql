-- ============================================================
-- 第七轮: 伏笔与角色关系增强 -- 数据库迁移
-- 为 chapters, character_relations, foreshadows 表添加新字段
-- ============================================================

-- chapters 表: 添加 focus_characters 和 worldview_refs
ALTER TABLE chapters ADD COLUMN IF NOT EXISTS focus_characters TEXT NOT NULL DEFAULT '[]';
ALTER TABLE chapters ADD COLUMN IF NOT EXISTS worldview_refs TEXT NOT NULL DEFAULT '[]';

-- character_relations 表: 添加信息不对称与角色弧字段
ALTER TABLE character_relations ADD COLUMN IF NOT EXISTS info_asymmetry TEXT NOT NULL DEFAULT '{}';
ALTER TABLE character_relations ADD COLUMN IF NOT EXISTS is_hidden BOOLEAN NOT NULL DEFAULT 0;
ALTER TABLE character_relations ADD COLUMN IF NOT EXISTS arc_direction VARCHAR(20) NOT NULL DEFAULT 'stable';
ALTER TABLE character_relations ADD COLUMN IF NOT EXISTS trigger_condition TEXT;
ALTER TABLE character_relations ADD COLUMN IF NOT EXISTS arc_milestones TEXT NOT NULL DEFAULT '[]';

-- foreshadows 表: 添加伏笔层级、世界观引用、位置信息等字段
ALTER TABLE foreshadows ADD COLUMN IF NOT EXISTS foreshadow_tier VARCHAR(20) DEFAULT 'chapter';
ALTER TABLE foreshadows ADD COLUMN IF NOT EXISTS worldview_refs TEXT NOT NULL DEFAULT '[]';
ALTER TABLE foreshadows ADD COLUMN IF NOT EXISTS character_refs TEXT NOT NULL DEFAULT '[]';
ALTER TABLE foreshadows ADD COLUMN IF NOT EXISTS foreshadow_links TEXT NOT NULL DEFAULT '[]';
ALTER TABLE foreshadows ADD COLUMN IF NOT EXISTS plant_location VARCHAR(100);
ALTER TABLE foreshadows ADD COLUMN IF NOT EXISTS reinforce_locations TEXT NOT NULL DEFAULT '[]';
ALTER TABLE foreshadows ADD COLUMN IF NOT EXISTS reveal_location VARCHAR(100);
ALTER TABLE foreshadows ADD COLUMN IF NOT EXISTS reclaim_status VARCHAR(20) DEFAULT 'unplanted';
