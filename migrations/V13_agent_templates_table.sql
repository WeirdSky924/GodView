-- V13: 创建 agent_templates 表
-- Agent 模板持久化存储

-- ==================== 创建 agent_templates 表 ====================
CREATE TABLE IF NOT EXISTS agent_templates (
    id VARCHAR(100) PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    description TEXT,

    -- 类型定义
    agent_type VARCHAR(50) NOT NULL,
    tags JSONB DEFAULT '[]',

    -- Prompt 配置
    prompt_slots JSONB DEFAULT '[]',
    default_prompt_order JSONB DEFAULT '[]',

    -- Skill 配置
    skill_slots JSONB DEFAULT '[]',
    default_skill_order JSONB DEFAULT '[]',

    -- 模型配置
    default_model VARCHAR(100),
    default_temperature DECIMAL(3, 2) DEFAULT 0.70,
    default_max_tokens INTEGER,

    -- 元数据
    is_system BOOLEAN DEFAULT FALSE,
    is_optional BOOLEAN DEFAULT FALSE,
    is_enabled BOOLEAN DEFAULT TRUE,
    version VARCHAR(20) DEFAULT '1.0.0',

    -- 时间戳
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 索引
CREATE INDEX IF NOT EXISTS idx_agent_templates_agent_type ON agent_templates(agent_type);
CREATE INDEX IF NOT EXISTS idx_agent_templates_is_system ON agent_templates(is_system);
CREATE INDEX IF NOT EXISTS idx_agent_templates_tags ON agent_templates USING GIN(tags);

-- 注释
COMMENT ON TABLE agent_templates IS 'Agent 模板表，定义不同类型的 Agent 配置';
COMMENT ON COLUMN agent_templates.agent_type IS 'Agent 类型: character, setting, summarizer, master_plotter, hook_manager, writer, evaluator, proc_gen, scene_coordinator, event_generator, world_map_manager, dungeon_generator';
COMMENT ON COLUMN agent_templates.prompt_slots IS 'Prompt 插槽列表，JSON 格式';
COMMENT ON COLUMN agent_templates.skill_slots IS 'Skill 插槽列表，JSON 格式';
COMMENT ON COLUMN agent_templates.is_system IS '是否系统内置模板（不可删除）';
COMMENT ON COLUMN agent_templates.is_optional IS '是否为可选 Agent（可禁用）';
COMMENT ON COLUMN agent_templates.is_enabled IS '是否启用（仅对可选 Agent 有效）';

-- 更新触发器
CREATE OR REPLACE FUNCTION update_agent_templates_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS agent_templates_updated_at ON agent_templates;
CREATE TRIGGER agent_templates_updated_at
    BEFORE UPDATE ON agent_templates
    FOR EACH ROW
    EXECUTE FUNCTION update_agent_templates_updated_at();
