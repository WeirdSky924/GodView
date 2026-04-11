-- V10: Agent Skill 系统
-- 将 Agent 的技能从硬编码改为数据库持久化存储

-- ==================== Skills 表 ====================
CREATE TABLE IF NOT EXISTS skills (
    id VARCHAR(100) PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    description TEXT DEFAULT '',

    -- 类型和分类
    skill_type VARCHAR(50) NOT NULL,  -- prompt, function, workflow, knowledge
    category VARCHAR(50) DEFAULT 'general',
    tags JSONB DEFAULT '[]',

    -- 适用范围
    applicable_agent_types JSONB DEFAULT '[]',  -- 空数组表示所有 Agent 都可用

    -- 内容定义
    prompt_template TEXT,  -- 直接内嵌的 Prompt 模板
    prompt_template_id VARCHAR(100),  -- 关联的 PromptTemplate ID
    function_code TEXT,  -- Function 类型的 Python 代码
    workflow_steps JSONB,  -- Workflow 类型的步骤
    knowledge_content TEXT,  -- Knowledge 类型的内容

    -- 参数和输出
    parameters JSONB DEFAULT '[]',  -- 输入参数列表
    output_spec JSONB DEFAULT '[]',  -- 输出字段规范

    -- 执行配置
    temperature FLOAT DEFAULT 0.7,
    max_tokens INTEGER,
    timeout INTEGER DEFAULT 60,
    retry_count INTEGER DEFAULT 0,

    -- 优先级和状态
    priority INTEGER DEFAULT 50,
    status VARCHAR(50) DEFAULT 'active',
    is_system BOOLEAN DEFAULT FALSE,
    is_enabled BOOLEAN DEFAULT TRUE,
    is_composable BOOLEAN DEFAULT TRUE,

    -- 创建来源
    creator_project_id UUID,
    creator_agent_id VARCHAR(100),
    creator_user_id VARCHAR(100),

    -- 元数据
    version VARCHAR(20) DEFAULT '1.0.0',
    author VARCHAR(100) DEFAULT 'system',
    examples JSONB DEFAULT '[]',

    -- 使用统计
    usage_count INTEGER DEFAULT 0,
    last_used_at TIMESTAMP WITH TIME ZONE,

    -- 时间戳
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_skills_type ON skills(skill_type);
CREATE INDEX idx_skills_category ON skills(category);
CREATE INDEX idx_skills_status ON skills(status);
CREATE INDEX idx_skills_system ON skills(is_system);
CREATE INDEX idx_skills_applicable ON skills USING GIN(applicable_agent_types);
CREATE INDEX idx_skills_tags ON skills USING GIN(tags);

-- ==================== Skill Assignments 表 ====================
-- Skill 到 Agent 模板的分配关系
CREATE TABLE IF NOT EXISTS skill_assignments (
    id VARCHAR(100) PRIMARY KEY,
    skill_id VARCHAR(100) NOT NULL REFERENCES skills(id) ON DELETE CASCADE,
    agent_type VARCHAR(50) NOT NULL,

    -- 分配配置
    slot_name VARCHAR(100) DEFAULT '',
    custom_parameters JSONB,
    variable_overrides JSONB DEFAULT '{}',
    priority INTEGER DEFAULT 50,

    -- 执行条件
    execution_condition TEXT,
    is_enabled BOOLEAN DEFAULT TRUE,
    is_required BOOLEAN DEFAULT FALSE,

    -- 分配信息
    assigned_by VARCHAR(50) DEFAULT 'user',
    assigned_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,

    UNIQUE(skill_id, agent_type, slot_name)
);

CREATE INDEX idx_skill_assignments_skill ON skill_assignments(skill_id);
CREATE INDEX idx_skill_assignments_agent ON skill_assignments(agent_type);
CREATE INDEX idx_skill_assignments_enabled ON skill_assignments(is_enabled);

-- ==================== Skill Execution Logs 表 ====================
CREATE TABLE IF NOT EXISTS skill_execution_logs (
    id VARCHAR(100) PRIMARY KEY,
    skill_id VARCHAR(100) NOT NULL REFERENCES skills(id) ON DELETE SET NULL,
    project_id UUID REFERENCES projects(id) ON DELETE SET NULL,
    agent_id VARCHAR(100),

    -- 执行数据
    input_params JSONB DEFAULT '{}',
    output_result TEXT,
    success BOOLEAN DEFAULT TRUE,
    error_message TEXT,
    execution_time_ms INTEGER,
    token_usage JSONB,

    -- 时间戳
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_skill_logs_skill ON skill_execution_logs(skill_id);
CREATE INDEX idx_skill_logs_project ON skill_execution_logs(project_id);
CREATE INDEX idx_skill_logs_created ON skill_execution_logs(created_at DESC);

-- ==================== 更新 Agent Templates 表 ====================
-- 添加 skill_slots 字段
ALTER TABLE agent_templates ADD COLUMN IF NOT EXISTS skill_slots JSONB DEFAULT '[]';

-- ==================== 触发器：更新时间戳 ====================
CREATE OR REPLACE FUNCTION update_skills_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER skills_updated_at
    BEFORE UPDATE ON skills
    FOR EACH ROW
    EXECUTE FUNCTION update_skills_updated_at();

-- ==================== 注释 ====================
COMMENT ON TABLE skills IS 'Agent 技能定义表';
COMMENT ON TABLE skill_assignments IS 'Skill 到 Agent 模板的分配关系';
COMMENT ON TABLE skill_execution_logs IS 'Skill 执行日志';
