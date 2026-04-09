-- 统一角色词汇字段类型为 JSONB
-- 将 forbidden_words 从 text[] 转换为 jsonb

-- 临时添加新列
ALTER TABLE characters ADD COLUMN IF NOT EXISTS forbidden_words_new JSONB DEFAULT '[]';

-- 迁移数据：将 text[] 转换为 jsonb 数组
UPDATE characters
SET forbidden_words_new = COALESCE(
    (SELECT jsonb_agg(elem) FROM unnest(forbidden_words) AS elem),
    '[]'::jsonb
)
WHERE forbidden_words IS NOT NULL AND forbidden_words_new IS NULL;

-- 删除旧列
ALTER TABLE characters DROP COLUMN IF EXISTS forbidden_words;

-- 重命名新列
ALTER TABLE characters RENAME COLUMN forbidden_words_new TO forbidden_words;

-- 完成
SELECT 'forbidden_words migration to JSONB completed!' AS status;
