-- V30: align agent memory scope with agent_id-aware enhanced memory tables

-- 1. agent_memories 唯一约束改为 NULLS NOT DISTINCT，确保 agent_id 为 NULL 时也按同一实例处理
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'unique_agent_in_project'
          AND conrelid = 'agent_memories'::regclass
    ) THEN
        ALTER TABLE agent_memories
        DROP CONSTRAINT unique_agent_in_project;
    END IF;
END $$;

ALTER TABLE agent_memories
ADD CONSTRAINT unique_agent_in_project
UNIQUE NULLS NOT DISTINCT (project_id, agent_type, agent_id);

CREATE INDEX IF NOT EXISTS idx_agent_memories_project_type ON agent_memories(project_id, agent_type);

-- 2. 为增强记忆表补齐 agent_id 列
ALTER TABLE memory_embeddings ADD COLUMN IF NOT EXISTS agent_id VARCHAR(100);
ALTER TABLE memory_usage_logs ADD COLUMN IF NOT EXISTS agent_id VARCHAR(100);

-- 3. 若历史 setting 记忆未写 agent_id，则回填默认实例名，避免与新逻辑断裂
UPDATE memory_embeddings
SET agent_id = 'setting_agent'
WHERE agent_type = 'setting'
  AND agent_id IS NULL;

UPDATE memory_usage_logs
SET agent_id = 'setting_agent'
WHERE agent_type = 'setting'
  AND agent_id IS NULL;

-- 4. 调整 memory_embeddings 唯一约束到实例粒度
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'memory_embeddings_memory_id_project_id_agent_type_key'
          AND conrelid = 'memory_embeddings'::regclass
    ) THEN
        ALTER TABLE memory_embeddings
        DROP CONSTRAINT memory_embeddings_memory_id_project_id_agent_type_key;
    END IF;

    IF EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'memory_embeddings_scope_unique'
          AND conrelid = 'memory_embeddings'::regclass
    ) THEN
        ALTER TABLE memory_embeddings
        DROP CONSTRAINT memory_embeddings_scope_unique;
    END IF;
END $$;

ALTER TABLE memory_embeddings
ADD CONSTRAINT memory_embeddings_scope_unique
UNIQUE NULLS NOT DISTINCT (memory_id, project_id, agent_type, agent_id);

CREATE INDEX IF NOT EXISTS idx_memory_embeddings_project_agent_instance
ON memory_embeddings(project_id, agent_type, agent_id);

CREATE INDEX IF NOT EXISTS idx_memory_usage_project_agent_instance
ON memory_usage_logs(project_id, agent_type, agent_id);
