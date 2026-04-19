-- V26: 记忆系统增强
-- 语义检索、上下文感知选择、使用追踪、衰减机制

-- ==================== 确保 pgvector 扩展可用 ====================
-- 如果 pgvector 不可用，将使用 JSONB 作为回退

-- ==================== 记忆嵌入表 ====================

-- 为记忆条目存储向量嵌入（支持语义检索）
CREATE TABLE IF NOT EXISTS memory_embeddings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    memory_id VARCHAR(100) NOT NULL,
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    agent_type VARCHAR(100) NOT NULL,
    agent_id VARCHAR(100),

    -- 记忆内容（便于重建嵌入）
    content TEXT NOT NULL,
    content_hash VARCHAR(64),

    -- 向量嵌入（使用 pgvector 扩展，如果不可用则为 JSONB）
    embedding JSONB DEFAULT NULL,

    -- 元数据
    memory_type VARCHAR(50),
    importance VARCHAR(50),
    tags JSONB DEFAULT '[]',

    -- 使用追踪
    access_count INT DEFAULT 0,
    last_accessed_at TIMESTAMPTZ,
    last_used_in_chapter INT,
    last_used_context VARCHAR(200),

    -- 衰减因子
    decay_factor FLOAT DEFAULT 1.0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE NULLS NOT DISTINCT (memory_id, project_id, agent_type, agent_id)
);

CREATE INDEX IF NOT EXISTS idx_memory_embeddings_project ON memory_embeddings(project_id);
CREATE INDEX IF NOT EXISTS idx_memory_embeddings_agent ON memory_embeddings(agent_type);
CREATE INDEX IF NOT EXISTS idx_memory_embeddings_project_agent_instance ON memory_embeddings(project_id, agent_type, agent_id);
CREATE INDEX IF NOT EXISTS idx_memory_embeddings_type ON memory_embeddings(memory_type);
CREATE INDEX IF NOT EXISTS idx_memory_embeddings_content_hash ON memory_embeddings(content_hash);

-- ==================== 记忆使用日志表 ====================

CREATE TABLE IF NOT EXISTS memory_usage_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    memory_id VARCHAR(100) NOT NULL,
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    agent_type VARCHAR(100) NOT NULL,
    agent_id VARCHAR(100),

    -- 使用场景
    usage_context VARCHAR(200),
    chapter_number INT,
    workflow_execution_id VARCHAR(100),
    workflow_node_id VARCHAR(100),

    -- 相关性评分
    relevance_score FLOAT,

    -- 使用效果
    was_helpful BOOLEAN,

    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_memory_usage_memory ON memory_usage_logs(memory_id);
CREATE INDEX IF NOT EXISTS idx_memory_usage_project ON memory_usage_logs(project_id);
CREATE INDEX IF NOT EXISTS idx_memory_usage_project_agent_instance ON memory_usage_logs(project_id, agent_type, agent_id);
CREATE INDEX IF NOT EXISTS idx_memory_usage_context ON memory_usage_logs(usage_context);
CREATE INDEX IF NOT EXISTS idx_memory_usage_created ON memory_usage_logs(created_at);

-- ==================== 上下文感知记忆配置表 ====================

CREATE TABLE IF NOT EXISTS memory_context_configs (
    id VARCHAR(100) PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    description TEXT,

    -- 适用场景
    task_types JSONB DEFAULT '[]',
    agent_types JSONB DEFAULT '[]',

    -- 记忆选择策略
    selection_strategy VARCHAR(50) DEFAULT 'hybrid',
    max_memories INT DEFAULT 10,

    -- 类型权重
    type_weights JSONB DEFAULT '{"decision": 2.0, "observation": 1.0, "fact": 1.5}',

    -- 时间衰减
    time_decay_days INT DEFAULT 30,
    time_decay_factor FLOAT DEFAULT 0.5,

    -- 必需/排除标签
    required_tags JSONB DEFAULT '[]',
    excluded_tags JSONB DEFAULT '[]',

    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 插入默认配置
INSERT INTO memory_context_configs (id, name, description, task_types, agent_types, selection_strategy, type_weights, max_memories)
VALUES
('config_outline_generation', '大纲生成记忆配置', '生成章节大纲时加载相关记忆',
 '["outline_generation", "plot_planning"]'::jsonb,
 '["plot_outline", "master_plotter"]'::jsonb,
 'hybrid',
 '{"decision": 2.0, "observation": 1.0, "fact": 1.5, "learning": 1.5}'::jsonb,
 15),
('config_writing', '写作记忆配置', '章节写作时加载相关记忆',
 '["chapter_writing", "scene_writing"]'::jsonb,
 '["writer"]'::jsonb,
 'relevant',
 '{"decision": 1.5, "observation": 1.0, "feedback": 2.0}'::jsonb,
 10),
('config_evaluation', '评估记忆配置', '内容评估时加载相关记忆',
 '["evaluation", "quality_check"]'::jsonb,
 '["evaluator"]'::jsonb,
 'important',
 '{"decision": 2.0, "feedback": 2.0, "learning": 1.5}'::jsonb,
 8),
('config_dialogue', '对话生成记忆配置', '生成角色对话时加载相关记忆',
 '["dialogue_generation", "character_interaction"]'::jsonb,
 '["character", "scene_coordinator"]'::jsonb,
 'relevant',
 '{"observation": 2.0, "fact": 1.5, "decision": 1.0}'::jsonb,
 12)
ON CONFLICT (id) DO NOTHING;

-- ==================== 记忆衰减规则表 ====================

CREATE TABLE IF NOT EXISTS memory_decay_rules (
    id VARCHAR(100) PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    description TEXT,

    -- 适用条件
    memory_type VARCHAR(50),
    importance VARCHAR(50),

    -- 衰减参数
    initial_weight FLOAT DEFAULT 1.0,
    decay_rate FLOAT DEFAULT 0.1,
    min_weight FLOAT DEFAULT 0.1,

    -- 影响因素
    access_boost FLOAT DEFAULT 0.1,
    max_decay_days INT DEFAULT 90,

    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

INSERT INTO memory_decay_rules (id, name, description, memory_type, importance, decay_rate, min_weight)
VALUES
('decay_ephemeral', '短期记忆衰减', 'EPHEMERAL 类型记忆快速衰减',
 'ephemeral', NULL, 0.3, 0.05),
('decay_low_importance', '低重要性记忆衰减', 'LOW 重要性记忆中等衰减',
 NULL, 'low', 0.1, 0.2),
('decay_observation', '观察记忆衰减', 'OBSERVATION 类型记忆会逐渐衰减',
 'observation', NULL, 0.05, 0.3),
('preserve_critical', '关键记忆保护', 'CRITICAL 重要性记忆不衰减',
 NULL, 'critical', 0.0, 1.0),
('preserve_decision', '决策记忆保护', 'DECISION 类型记忆慢衰减',
 'decision', NULL, 0.02, 0.5)
ON CONFLICT (id) DO NOTHING;

-- ==================== 扩展 agent_memories 表 ====================

ALTER TABLE agent_memories ADD COLUMN IF NOT EXISTS total_accesses INT DEFAULT 0;
ALTER TABLE agent_memories ADD COLUMN IF NOT EXISTS last_memory_decay_at TIMESTAMPTZ;

-- ==================== 添加 agent_id 到增强记忆表 ====================

ALTER TABLE memory_embeddings ADD COLUMN IF NOT EXISTS agent_id VARCHAR(100);
ALTER TABLE memory_usage_logs ADD COLUMN IF NOT EXISTS agent_id VARCHAR(100);

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'memory_embeddings_memory_id_project_id_agent_type_key'
    ) THEN
        ALTER TABLE memory_embeddings
        DROP CONSTRAINT memory_embeddings_memory_id_project_id_agent_type_key;
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'memory_embeddings_scope_unique'
    ) THEN
        ALTER TABLE memory_embeddings
        ADD CONSTRAINT memory_embeddings_scope_unique
        UNIQUE NULLS NOT DISTINCT (memory_id, project_id, agent_type, agent_id);
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_memory_embeddings_project_agent_instance ON memory_embeddings(project_id, agent_type, agent_id);
CREATE INDEX IF NOT EXISTS idx_memory_usage_project_agent_instance ON memory_usage_logs(project_id, agent_type, agent_id);

-- ==================== 添加嵌入向量列（如果 pgvector 可用）====================
-- 注意：这个操作需要在 Python 迁移脚本中根据 pgvector 是否可用来决定是否执行
-- 如果 pgvector 可用，会创建 vector(1536) 类型的列并添加向量索引
