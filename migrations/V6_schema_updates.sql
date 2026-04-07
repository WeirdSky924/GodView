-- GodView V6 数据库表结构更新
-- 执行此脚本更新现有数据库结构

-- ==================== Part 5.1: 表结构更新 ====================

-- 1. 为 projects 表添加 Token 统计字段
ALTER TABLE projects
ADD COLUMN IF NOT EXISTS total_tokens BIGINT DEFAULT 0,
ADD COLUMN IF NOT EXISTS total_cost DECIMAL(10, 6) DEFAULT 0;

-- 2. 为 worlds 表添加 project_id 外键
ALTER TABLE worlds
ADD COLUMN IF NOT EXISTS project_id UUID REFERENCES projects(id) ON DELETE SET NULL;

-- 3. 为 characters 表添加 project_id 外键（如果不存在）
ALTER TABLE characters
ADD COLUMN IF NOT EXISTS project_id UUID REFERENCES projects(id) ON DELETE SET NULL;

-- 4. 为 chapters 表添加 project_id 外键
ALTER TABLE chapters
ADD COLUMN IF NOT EXISTS project_id UUID REFERENCES projects(id) ON DELETE SET NULL;

-- 5. 为 hooks 表添加 project_id 外键
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'hooks' AND column_name = 'project_id'
    ) THEN
        ALTER TABLE hooks ADD COLUMN project_id UUID REFERENCES projects(id) ON DELETE SET NULL;
    END IF;
END $$;

-- ==================== Part 5.2: 新建表 ====================

-- 6. 创建 token_usage 表
CREATE TABLE IF NOT EXISTS token_usage (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    input_tokens INTEGER NOT NULL DEFAULT 0,
    output_tokens INTEGER NOT NULL DEFAULT 0,
    total_tokens INTEGER NOT NULL DEFAULT 0,
    provider VARCHAR(100) NOT NULL,
    model VARCHAR(200) NOT NULL,
    category VARCHAR(50) NOT NULL,
    agent_name VARCHAR(100),
    session_id UUID,
    chapter_id UUID,
    character_id UUID,
    estimated_cost DECIMAL(10, 6) DEFAULT 0,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 7. 创建 interventions 表（如果不存在）
CREATE TABLE IF NOT EXISTS interventions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    chapter_id UUID REFERENCES chapters(id) ON DELETE CASCADE,
    type VARCHAR(50) NOT NULL,
    description TEXT NOT NULL,
    severity VARCHAR(20) DEFAULT 'info',
    resolved BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    resolved_at TIMESTAMP WITH TIME ZONE
);

-- 8. 创建 snapshots 表（如果不存在）
CREATE TABLE IF NOT EXISTS snapshots (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    name VARCHAR(200) NOT NULL,
    description TEXT,
    snapshot_type VARCHAR(50) NOT NULL,
    data JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_by VARCHAR(100)
);

-- 9. 创建 skills 表
CREATE TABLE IF NOT EXISTS skills (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(200) NOT NULL UNIQUE,
    description TEXT NOT NULL,
    skill_type VARCHAR(50) NOT NULL,
    prompt_template TEXT,
    function_code TEXT,
    workflow_steps JSONB DEFAULT '[]',
    knowledge_content TEXT,
    parameters JSONB DEFAULT '[]',
    tags JSONB DEFAULT '[]',
    version VARCHAR(20) DEFAULT '1.0.0',
    status VARCHAR(20) DEFAULT 'draft',
    creator_project_id UUID REFERENCES projects(id) ON DELETE SET NULL,
    creator_agent_id VARCHAR(100),
    creator_user_id VARCHAR(100),
    usage_count INTEGER DEFAULT 0,
    last_used_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 10. 创建 skill_assignments 表
CREATE TABLE IF NOT EXISTS skill_assignments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    skill_id UUID NOT NULL REFERENCES skills(id) ON DELETE CASCADE,
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    agent_id VARCHAR(100) NOT NULL,
    custom_parameters JSONB DEFAULT '{}',
    priority INTEGER DEFAULT 0,
    assigned_by VARCHAR(100),
    assigned_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(skill_id, project_id, agent_id)
);

-- 11. 创建 skill_execution_logs 表
CREATE TABLE IF NOT EXISTS skill_execution_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    skill_id UUID NOT NULL REFERENCES skills(id) ON DELETE CASCADE,
    project_id UUID REFERENCES projects(id) ON DELETE SET NULL,
    agent_id VARCHAR(100),
    input_params JSONB DEFAULT '{}',
    output_result TEXT,
    success BOOLEAN NOT NULL DEFAULT TRUE,
    error_message TEXT,
    execution_time_ms INTEGER,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 12. 创建 lore_entries 表（设定库）
CREATE TABLE IF NOT EXISTS lore_entries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    category VARCHAR(50) NOT NULL,
    priority VARCHAR(20) DEFAULT 'standard',
    title VARCHAR(200) NOT NULL,
    content TEXT NOT NULL,
    keywords JSONB DEFAULT '[]',
    constraints JSONB DEFAULT '[]',
    references_ids JSONB DEFAULT '[]',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_by VARCHAR(100)
);

-- 13. 创建 setting_agent_sessions 表
CREATE TABLE IF NOT EXISTS setting_agent_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL UNIQUE REFERENCES projects(id) ON DELETE CASCADE,
    mode VARCHAR(50) DEFAULT 'management',
    conversation_history JSONB DEFAULT '[]',
    current_request JSONB,
    pending_conflicts JSONB DEFAULT '[]',
    knowledge_index JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ==================== Part 5.3: 索引创建 ====================

-- 14. 创建索引
CREATE INDEX IF NOT EXISTS idx_characters_project_id ON characters(project_id);
CREATE INDEX IF NOT EXISTS idx_worlds_project_id ON worlds(project_id);
CREATE INDEX IF NOT EXISTS idx_chapters_project_id ON chapters(project_id);
CREATE INDEX IF NOT EXISTS idx_hooks_project_id ON hooks(project_id);
CREATE INDEX IF NOT EXISTS idx_token_usage_project_id ON token_usage(project_id);
CREATE INDEX IF NOT EXISTS idx_token_usage_category ON token_usage(category);
CREATE INDEX IF NOT EXISTS idx_token_usage_created_at ON token_usage(created_at);
CREATE INDEX IF NOT EXISTS idx_token_usage_model ON token_usage(model);
CREATE INDEX IF NOT EXISTS idx_interventions_project_id ON interventions(project_id);
CREATE INDEX IF NOT EXISTS idx_snapshots_project_id ON snapshots(project_id);
CREATE INDEX IF NOT EXISTS idx_skills_type ON skills(skill_type);
CREATE INDEX IF NOT EXISTS idx_skills_status ON skills(status);
CREATE INDEX IF NOT EXISTS idx_skill_assignments_project_agent ON skill_assignments(project_id, agent_id);
CREATE INDEX IF NOT EXISTS idx_lore_entries_project_category ON lore_entries(project_id, category);

-- ==================== 完成提示 ====================
DO $$
BEGIN
    RAISE NOTICE 'GodView V6 数据库表结构更新完成！';
END $$;
