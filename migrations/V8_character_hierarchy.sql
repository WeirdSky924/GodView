-- V8 Character Hierarchy Migration
-- Adds character importance tier system

-- Add importance tier columns to characters table
ALTER TABLE characters ADD COLUMN IF NOT EXISTS importance_tier VARCHAR(50) DEFAULT 'npc';
ALTER TABLE characters ADD COLUMN IF NOT EXISTS narrative_weight VARCHAR(30) DEFAULT 'minimal';
ALTER TABLE characters ADD COLUMN IF NOT EXISTS story_arc_role VARCHAR(30) DEFAULT 'neutral';
ALTER TABLE characters ADD COLUMN IF NOT EXISTS plot_priority INTEGER DEFAULT 0;

-- Add debut/exit control columns
ALTER TABLE characters ADD COLUMN IF NOT EXISTS debut_chapter INTEGER;
ALTER TABLE characters ADD COLUMN IF NOT EXISTS exit_chapter INTEGER;
ALTER TABLE characters ADD COLUMN IF NOT EXISTS active_arc VARCHAR(100);

-- Add key relationships column
ALTER TABLE characters ADD COLUMN IF NOT EXISTS key_relationships JSONB DEFAULT '{}';

-- Add statistics columns
ALTER TABLE characters ADD COLUMN IF NOT EXISTS total_scenes INTEGER DEFAULT 0;
ALTER TABLE characters ADD COLUMN IF NOT EXISTS dialogue_count INTEGER DEFAULT 0;
ALTER TABLE characters ADD COLUMN IF NOT EXISTS major_events JSONB DEFAULT '[]';

-- Create index on importance_tier for faster filtering
CREATE INDEX IF NOT EXISTS idx_characters_importance_tier ON characters(importance_tier);
CREATE INDEX IF NOT EXISTS idx_characters_plot_priority ON characters(plot_priority);

-- Update existing characters based on their role (迁移旧数据)
UPDATE characters SET
    importance_tier = CASE
        WHEN role = 'main' THEN 'protagonist'
        WHEN role = 'antagonist' THEN 'archenemy'
        WHEN role = 'supporting' THEN 'recurring'
        ELSE 'npc'
    END,
    narrative_weight = CASE
        WHEN role = 'main' THEN 'full_focus'
        WHEN role = 'antagonist' THEN 'major_focus'
        WHEN role = 'supporting' THEN 'minimal'
        ELSE 'background'
    END,
    plot_priority = CASE
        WHEN role = 'main' THEN 10
        WHEN role = 'antagonist' THEN 8
        WHEN role = 'supporting' THEN 2
        ELSE 0
    END
WHERE importance_tier = 'npc' OR importance_tier IS NULL OR importance_tier = '';

-- 确保 role 字段与 importance_tier 同步
UPDATE characters SET role = 'main'
WHERE importance_tier IN ('protagonist', 'co_protagonist', 'deuteragonist');

UPDATE characters SET role = 'antagonist'
WHERE importance_tier IN ('archenemy', 'major_antagonist', 'arc_antagonist');

UPDATE characters SET role = 'npc'
WHERE importance_tier IN ('npc', 'background', 'cameo', 'minion');

UPDATE characters SET role = 'supporting'
WHERE role IS NULL OR role = '';
