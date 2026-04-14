-- V29: 增强世界管理标签系统
-- 添加多维度标签支持：内容风格、主角类型、角色人设、战斗能力

-- 添加新标签字段（JSONB数组支持多选）
ALTER TABLE worlds ADD COLUMN IF NOT EXISTS content_styles JSONB DEFAULT '[]';
ALTER TABLE worlds ADD COLUMN IF NOT EXISTS protagonist_types JSONB DEFAULT '[]';
ALTER TABLE worlds ADD COLUMN IF NOT EXISTS character_archetypes JSONB DEFAULT '[]';
ALTER TABLE worlds ADD COLUMN IF NOT EXISTS power_types JSONB DEFAULT '[]';

-- 为新字段创建索引
CREATE INDEX IF NOT EXISTS idx_worlds_content_styles ON worlds USING GIN(content_styles);
CREATE INDEX IF NOT EXISTS idx_worlds_protagonist_types ON worlds USING GIN(protagonist_types);
CREATE INDEX IF NOT EXISTS idx_worlds_character_archetypes ON worlds USING GIN(character_archetypes);
CREATE INDEX IF NOT EXISTS idx_worlds_power_types ON worlds USING GIN(power_types);

-- 注释
COMMENT ON COLUMN worlds.content_styles IS '内容风格标签数组，如：沙雕搞笑、治愈救赎等';
COMMENT ON COLUMN worlds.protagonist_types IS '主角类型标签数组，如：大男主、大女主';
COMMENT ON COLUMN worlds.character_archetypes IS '角色人设模板标签数组，如：霸总、腹黑、疯批美人等';
COMMENT ON COLUMN worlds.power_types IS '战斗能力标签数组，如：异能、魔法、修炼等';
