-- V11 Agent Memory System
-- Agent 记忆和状态持久化

-- Agent 记忆表
CREATE TABLE IF NOT EXISTS agent_memories (
    id VARCHAR(50) PRIMARY KEY,
    project_id UUID NOT NULL,
    agent_type VARCHAR(50) NOT NULL,
    agent_id VARCHAR(50),  -- 用于区分同类型多实例

    -- 记忆存储 (JSONB)
    memories JSONB DEFAULT '[]'::jsonb,
    knowledge JSONB DEFAULT '{}'::jsonb,
    working_memory JSONB DEFAULT '{}'::jsonb,

    -- 统计
    total_memories INTEGER DEFAULT 0,
    last_execution TIMESTAMP,
    execution_count INTEGER DEFAULT 0,

    -- 时间戳
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- 约束
    CONSTRAINT fk_project FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
    CONSTRAINT unique_agent_in_project UNIQUE (project_id, agent_type, agent_id)
);

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_agent_memories_project ON agent_memories(project_id);
CREATE INDEX IF NOT EXISTS idx_agent_memories_type ON agent_memories(agent_type);
CREATE INDEX IF NOT EXISTS idx_agent_memories_project_type ON agent_memories(project_id, agent_type);

-- 记忆条目搜索视图（用于向量搜索）
CREATE OR REPLACE VIEW agent_memory_entries AS
SELECT
    am.id as memory_id,
    am.project_id,
    am.agent_type,
    am.agent_id,
    mem.entry_id,
    mem.type,
    mem.importance,
    mem.content,
    mem.summary,
    mem.tags,
    mem.timestamp,
    mem.context,
    mem.related_chapter,
    mem.related_characters
FROM agent_memories am,
LATERAL jsonb_to_recordset(am.memories) AS mem(
    entry_id TEXT,
    type TEXT,
    importance TEXT,
    content TEXT,
    summary TEXT,
    tags TEXT[],
    timestamp TIMESTAMP,
    context JSONB,
    related_chapter INTEGER,
    related_characters TEXT[]
);

-- Agent 执行日志表（记录每次执行）
CREATE TABLE IF NOT EXISTS agent_execution_logs (
    id SERIAL PRIMARY KEY,
    memory_id VARCHAR(50) NOT NULL,
    project_id UUID NOT NULL,
    agent_type VARCHAR(50) NOT NULL,

    -- 执行信息
    execution_type VARCHAR(50),  -- 如 'workflow_node', 'user_intervention'
    node_id VARCHAR(100),
    workflow_execution_id VARCHAR(100),

    -- 输入输出
    input_summary TEXT,
    output_summary TEXT,

    -- 决策记录
    decisions JSONB DEFAULT '[]'::jsonb,
    observations JSONB DEFAULT '[]'::jsonb,

    -- 性能
    duration_ms INTEGER,
    tokens_used INTEGER,

    -- 状态
    success BOOLEAN DEFAULT true,
    error_message TEXT,

    -- 时间
    started_at TIMESTAMP,
    completed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_agent_memory FOREIGN KEY (memory_id) REFERENCES agent_memories(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_execution_logs_memory ON agent_execution_logs(memory_id);
CREATE INDEX IF NOT EXISTS idx_execution_logs_project ON agent_execution_logs(project_id);
CREATE INDEX IF NOT EXISTS idx_execution_logs_time ON agent_execution_logs(completed_at DESC);

-- 注释
COMMENT ON TABLE agent_memories IS 'Agent 持久化记忆存储';
COMMENT ON TABLE agent_execution_logs IS 'Agent 执行日志，记录每次执行的详细信息和决策';
COMMENT ON COLUMN agent_memories.memories IS '记忆条目列表 (JSONB array of MemoryEntry)';
COMMENT ON COLUMN agent_memories.knowledge IS '结构化知识库';
COMMENT ON COLUMN agent_memories.working_memory IS '短期工作记忆';
