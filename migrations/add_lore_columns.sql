-- 添加 lore_entries 缺失的列

-- 添加 priority 列（如果不存在）
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'lore_entries' AND column_name = 'priority') THEN
        ALTER TABLE lore_entries ADD COLUMN priority VARCHAR(20) DEFAULT 'standard';
    END IF;
END $$;

-- 添加 summary 列
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'lore_entries' AND column_name = 'summary') THEN
        ALTER TABLE lore_entries ADD COLUMN summary TEXT DEFAULT '';
    END IF;
END $$;

-- 添加 keywords 列（jsonb）
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'lore_entries' AND column_name = 'keywords') THEN
        ALTER TABLE lore_entries ADD COLUMN keywords JSONB DEFAULT '[]';
    END IF;
END $$;

-- 添加 constraints 列（jsonb）
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'lore_entries' AND column_name = 'constraints') THEN
        ALTER TABLE lore_entries ADD COLUMN constraints JSONB DEFAULT '[]';
    END IF;
END $$;

-- 添加 related_characters 列（jsonb）
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'lore_entries' AND column_name = 'related_characters') THEN
        ALTER TABLE lore_entries ADD COLUMN related_characters JSONB DEFAULT '[]';
    END IF;
END $$;

-- 添加 related_locations 列（jsonb）
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'lore_entries' AND column_name = 'related_locations') THEN
        ALTER TABLE lore_entries ADD COLUMN related_locations JSONB DEFAULT '[]';
    END IF;
END $$;

-- 添加 related_items 列（jsonb）
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'lore_entries' AND column_name = 'related_items') THEN
        ALTER TABLE lore_entries ADD COLUMN related_items JSONB DEFAULT '[]';
    END IF;
END $$;

-- 添加 forbidden_actions 列（jsonb）
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'lore_entries' AND column_name = 'forbidden_actions') THEN
        ALTER TABLE lore_entries ADD COLUMN forbidden_actions JSONB DEFAULT '[]';
    END IF;
END $$;

-- 添加 source 列
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'lore_entries' AND column_name = 'source') THEN
        ALTER TABLE lore_entries ADD COLUMN source TEXT DEFAULT '';
    END IF;
END $$;

-- 将 tags 从 text[] 转为 jsonb（如果还是 text[]）
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'lore_entries'
        AND column_name = 'tags'
        AND data_type = 'ARRAY'
    ) THEN
        ALTER TABLE lore_entries ALTER COLUMN tags TYPE JSONB USING to_jsonb(tags);
    END IF;
END $$;
