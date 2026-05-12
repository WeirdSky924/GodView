-- GodView V7 Prompt 管理系统数据库表结构
-- 执行此脚本创建 Prompt 管理相关的表结构

-- ==================== Part 1: 创建 prompt_templates 表 ====================

-- 1. 创建 prompt_templates 表
CREATE TABLE IF NOT EXISTS prompt_templates (
    id VARCHAR(100) PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    description TEXT,

    -- 分类
    category VARCHAR(50) NOT NULL,
    tags JSONB DEFAULT '[]',

    -- 内容
    content TEXT NOT NULL,
    variables JSONB DEFAULT '[]',
    default_values JSONB DEFAULT '{}',

    -- 优先级
    priority INTEGER DEFAULT 50,

    -- 元数据
    is_system BOOLEAN DEFAULT FALSE,
    version INTEGER DEFAULT 1,

    -- 时间戳
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    -- 索引
    CONSTRAINT valid_priority CHECK (priority >= 0 AND priority <= 100)
);

COMMENT ON TABLE prompt_templates IS 'Prompt 模板表，存储可复用的 prompt 片段';
COMMENT ON COLUMN prompt_templates.id IS 'Prompt ID';
COMMENT ON COLUMN prompt_templates.category IS 'Prompt 分类: base, role, function, value, output, constraint';

-- ==================== Part 2: 创建 agent_templates 表 ====================

-- 2. 创建 agent_templates 表
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

    -- 模型配置
    default_model VARCHAR(100) DEFAULT 'gpt-4o-mini',
    default_temperature DECIMAL(3, 2) DEFAULT 0.70,
    default_max_tokens INTEGER,

    -- 元数据
    is_system BOOLEAN DEFAULT FALSE,
    version VARCHAR(20) DEFAULT '1.0.0',

    -- 时间戳
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

COMMENT ON TABLE agent_templates IS 'Agent 模板表，定义不同类型的 Agent 应包含哪些 Prompt 片段';
COMMENT ON COLUMN agent_templates.agent_type IS 'Agent 类型: character, setting, summarizer, master_plotter, hook_manager, writer, evaluator, proc_gen';

-- ==================== Part 3: 创建 agent_configs 表 ====================

-- 3. 创建 agent_configs 表
CREATE TABLE IF NOT EXISTS agent_configs (
    id VARCHAR(100) PRIMARY KEY,
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    agent_type VARCHAR(50) NOT NULL,
    scenario VARCHAR(100) DEFAULT 'default',

    -- 基础信息
    name VARCHAR(200) NOT NULL,
    description TEXT,

    -- 模板关联
    template_id VARCHAR(100) REFERENCES agent_templates(id) ON DELETE SET NULL,
    is_custom BOOLEAN DEFAULT FALSE,

    -- Prompt 配置
    slot_overrides JSONB DEFAULT '[]',
    custom_prompt_order JSONB DEFAULT NULL,

    -- 模型配置
    model_config JSONB DEFAULT '{"model_name": "gpt-4o-mini", "temperature": 0.7}',

    -- 元数据
    is_active BOOLEAN DEFAULT TRUE,
    version VARCHAR(20) DEFAULT '1.0.0',

    -- 使用统计
    usage_count INTEGER DEFAULT 0,
    last_used_at TIMESTAMP WITH TIME ZONE,

    -- 时间戳
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    -- 唯一约束
    UNIQUE(project_id, agent_type, name)
);

COMMENT ON TABLE agent_configs IS 'Agent 配置表，项目级别的 Agent 配置，基于模板但可自定义';
COMMENT ON COLUMN agent_configs.agent_type IS 'Agent 类型，与 agent_templates.agent_type 对应';

-- ==================== Part 4: 修改 skills 表 ====================

-- 4. 为 skills 表添加 prompt_template_id 字段
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'skills' AND column_name = 'prompt_template_id'
    ) THEN
        ALTER TABLE skills ADD COLUMN prompt_template_id VARCHAR(100) REFERENCES prompt_templates(id) ON DELETE SET NULL;
    END IF;
END $$;

-- 5. 更新 skills 表注释
COMMENT ON COLUMN skills.prompt_template_id IS '关联的 PromptTemplate ID，用于 prompt 类型的 skill';

-- ==================== Part 5: 创建写作规则相关表 ====================

-- 10. 创建 writing_rules 表
CREATE TABLE IF NOT EXISTS writing_rules (
    id VARCHAR(100) PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    description TEXT,

    -- 分类
    category VARCHAR(50) NOT NULL,
    severity VARCHAR(20) DEFAULT 'recommended',
    tags JSONB DEFAULT '[]',

    -- 内容
    content TEXT NOT NULL,
    examples JSONB DEFAULT '[]',
    counter_examples JSONB DEFAULT NULL,
    conditions JSONB DEFAULT '[]',
    exceptions JSONB DEFAULT NULL,

    -- 元数据
    is_system BOOLEAN DEFAULT FALSE,
    version VARCHAR(20) DEFAULT '1.0.0',
    author VARCHAR(200),
    source VARCHAR(500),

    -- 使用统计
    usage_count INTEGER DEFAULT 0,
    last_used_at TIMESTAMP WITH TIME ZONE,

    -- 时间戳
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

COMMENT ON TABLE writing_rules IS '写作规则表，存储具体的写作风格规则';
COMMENT ON COLUMN writing_rules.category IS '规则分类: dialogue, structure, style, grammar, format, character, plot, pacing';
COMMENT ON COLUMN writing_rules.severity IS '规则严重程度: required, strong, recommended, optional, info';

-- 11. 创建 writing_rule_sets 表
CREATE TABLE IF NOT EXISTS writing_rule_sets (
    id VARCHAR(100) PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    description TEXT,

    -- 规则组成
    rule_ids JSONB DEFAULT '[]',
    rule_overrides JSONB DEFAULT '{}',

    -- 分类
    category VARCHAR(50) NOT NULL,
    tags JSONB DEFAULT '[]',
    target_genres JSONB DEFAULT '[]',

    -- 元数据
    is_system BOOLEAN DEFAULT FALSE,
    version VARCHAR(20) DEFAULT '1.0.0',
    author VARCHAR(200),

    -- 使用统计
    usage_count INTEGER DEFAULT 0,
    last_used_at TIMESTAMP WITH TIME ZONE,

    -- 时间戳
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

COMMENT ON TABLE writing_rule_sets IS '写作规则集表，将相关规则组合成集合';
COMMENT ON COLUMN writing_rule_sets.category IS '规则集主要分类';

-- 12. 创建 project_writing_configs 表
CREATE TABLE IF NOT EXISTS project_writing_configs (
    id VARCHAR(100) PRIMARY KEY,
    project_id UUID NOT NULL UNIQUE REFERENCES projects(id) ON DELETE CASCADE,

    -- 规则配置
    enabled_rule_ids JSONB DEFAULT '[]',
    enabled_rule_set_ids JSONB DEFAULT '[]',
    rule_overrides JSONB DEFAULT '{}',

    -- 优先级配置
    rule_priorities JSONB DEFAULT '{}',
    default_severity VARCHAR(20) DEFAULT 'recommended',

    -- 应用范围
    apply_to_chapters BOOLEAN DEFAULT TRUE,
    apply_to_characters BOOLEAN DEFAULT TRUE,
    apply_to_descriptions BOOLEAN DEFAULT TRUE,
    apply_to_narration BOOLEAN DEFAULT TRUE,

    -- 元数据
    is_active BOOLEAN DEFAULT TRUE,
    version VARCHAR(20) DEFAULT '1.0.0',

    -- 时间戳
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

COMMENT ON TABLE project_writing_configs IS '项目写作配置表，存储项目的写作规则配置';
COMMENT ON COLUMN project_writing_configs.default_severity IS '默认严重程度: required, strong, recommended, optional, info';

-- ==================== Part 6: 创建索引 ====================

-- 13. 创建 writing_rules 表索引
CREATE INDEX IF NOT EXISTS idx_writing_rules_category ON writing_rules(category);
CREATE INDEX IF NOT EXISTS idx_writing_rules_severity ON writing_rules(severity);
CREATE INDEX IF NOT EXISTS idx_writing_rules_is_system ON writing_rules(is_system);
CREATE INDEX IF NOT EXISTS idx_writing_rules_tags ON writing_rules USING GIN(tags);

-- 14. 创建 writing_rule_sets 表索引
CREATE INDEX IF NOT EXISTS idx_writing_rule_sets_category ON writing_rule_sets(category);
CREATE INDEX IF NOT EXISTS idx_writing_rule_sets_is_system ON writing_rule_sets(is_system);
CREATE INDEX IF NOT EXISTS idx_writing_rule_sets_tags ON writing_rule_sets USING GIN(tags);
CREATE INDEX IF NOT EXISTS idx_writing_rule_sets_target_genres ON writing_rule_sets USING GIN(target_genres);

-- 15. 创建 project_writing_configs 表索引
CREATE INDEX IF NOT EXISTS idx_project_writing_configs_project_id ON project_writing_configs(project_id);
CREATE INDEX IF NOT EXISTS idx_project_writing_configs_is_active ON project_writing_configs(is_active);

-- 16. 创建 prompt_templates 表索引
CREATE INDEX IF NOT EXISTS idx_prompt_templates_category ON prompt_templates(category);
CREATE INDEX IF NOT EXISTS idx_prompt_templates_tags ON prompt_templates USING GIN(tags);
CREATE INDEX IF NOT EXISTS idx_prompt_templates_is_system ON prompt_templates(is_system);
CREATE INDEX IF NOT EXISTS idx_prompt_templates_created_at ON prompt_templates(created_at);

-- 17. 创建 agent_templates 表索引
CREATE INDEX IF NOT EXISTS idx_agent_templates_agent_type ON agent_templates(agent_type);
CREATE INDEX IF NOT EXISTS idx_agent_templates_is_system ON agent_templates(is_system);
CREATE INDEX IF NOT EXISTS idx_agent_templates_tags ON agent_templates USING GIN(tags);

-- 18. 创建 agent_configs 表索引
CREATE INDEX IF NOT EXISTS idx_agent_configs_project_id ON agent_configs(project_id);
CREATE INDEX IF NOT EXISTS idx_agent_configs_agent_type ON agent_configs(agent_type);
CREATE INDEX IF NOT EXISTS idx_agent_configs_template_id ON agent_configs(template_id);
CREATE INDEX IF NOT EXISTS idx_agent_configs_is_active ON agent_configs(is_active);
CREATE INDEX IF NOT EXISTS idx_agent_configs_created_at ON agent_configs(created_at);

-- 19. 创建 skills 表索引
CREATE INDEX IF NOT EXISTS idx_skills_prompt_template_id ON skills(prompt_template_id);

-- ==================== 完成提示 ====================
DO $$
BEGIN
    RAISE NOTICE 'GodView V7 Prompt 管理系统数据库表结构创建完成！';
    RAISE NOTICE '已创建表: prompt_templates, agent_templates, agent_configs, writing_rules, writing_rule_sets, project_writing_configs';
    RAISE NOTICE '已更新表: skills (添加 prompt_template_id 字段)';
    RAISE NOTICE '已创建相关索引';
END $$;