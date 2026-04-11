-- V8 Agent协作可视化工作台 - 数据库迁移脚本
-- 执行方式: 在PostgreSQL中执行此脚本

-- ==================== 工作流定义表 ====================

CREATE TABLE IF NOT EXISTS workflow_definitions (
    id VARCHAR(50) PRIMARY KEY,
    project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
    name VARCHAR(200) NOT NULL,
    description TEXT,
    nodes JSONB NOT NULL DEFAULT '[]',
    edges JSONB NOT NULL DEFAULT '[]',
    variables JSONB DEFAULT '{}',
    is_template BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE workflow_definitions IS '工作流定义表';
COMMENT ON COLUMN workflow_definitions.nodes IS '节点列表（JSON数组）';
COMMENT ON COLUMN workflow_definitions.edges IS '边列表（JSON数组）';
COMMENT ON COLUMN workflow_definitions.variables IS '工作流变量';
COMMENT ON COLUMN workflow_definitions.is_template IS '是否为模板';

-- ==================== 工作流执行记录表 ====================

CREATE TABLE IF NOT EXISTS workflow_executions (
    id VARCHAR(50) PRIMARY KEY,
    workflow_id VARCHAR(50) REFERENCES workflow_definitions(id) ON DELETE CASCADE,
    project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    current_node VARCHAR(50),
    node_states JSONB DEFAULT '{}',
    context JSONB DEFAULT '{}',
    intervention_ids JSONB DEFAULT '[]',
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    total_duration_ms INTEGER,
    error TEXT,

    CONSTRAINT chk_status CHECK (status IN ('pending', 'running', 'paused', 'completed', 'failed', 'cancelled'))
);

COMMENT ON TABLE workflow_executions IS '工作流执行记录表';
COMMENT ON COLUMN workflow_executions.status IS '执行状态: pending/running/paused/completed/failed/cancelled';
COMMENT ON COLUMN workflow_executions.node_states IS '节点状态映射（JSON对象）';
COMMENT ON COLUMN workflow_executions.context IS '工作流上下文';
COMMENT ON COLUMN workflow_executions.intervention_ids IS '干预日志ID列表';

-- ==================== 干预日志表 ====================

CREATE TABLE IF NOT EXISTS intervention_logs (
    id VARCHAR(50) PRIMARY KEY,
    project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
    workflow_execution_id VARCHAR(50) REFERENCES workflow_executions(id) ON DELETE CASCADE,
    node_id VARCHAR(50),
    agent_type VARCHAR(50) NOT NULL,
    agent_name VARCHAR(100) NOT NULL,
    intervention_type VARCHAR(20) DEFAULT 'guidance',
    user_message TEXT NOT NULL,
    agent_response TEXT,
    context_snapshot JSONB DEFAULT '{}',
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    response_time_ms INTEGER,

    CONSTRAINT chk_intervention_type CHECK (intervention_type IN ('guidance', 'correction', 'direction', 'override'))
);

COMMENT ON TABLE intervention_logs IS '干预日志表';
COMMENT ON COLUMN intervention_logs.intervention_type IS '干预类型: guidance/correction/direction/override';
COMMENT ON COLUMN intervention_logs.context_snapshot IS '干预时的上下文快照';

-- ==================== 索引 ====================

-- 工作流定义索引
CREATE INDEX IF NOT EXISTS idx_workflow_project ON workflow_definitions(project_id);
CREATE INDEX IF NOT EXISTS idx_workflow_template ON workflow_definitions(is_template);
CREATE INDEX IF NOT EXISTS idx_workflow_name ON workflow_definitions(name);

-- 工作流执行索引
CREATE INDEX IF NOT EXISTS idx_execution_workflow ON workflow_executions(workflow_id);
CREATE INDEX IF NOT EXISTS idx_execution_project ON workflow_executions(project_id);
CREATE INDEX IF NOT EXISTS idx_execution_status ON workflow_executions(status);
CREATE INDEX IF NOT EXISTS idx_execution_started ON workflow_executions(started_at DESC);

-- 干预日志索引
CREATE INDEX IF NOT EXISTS idx_intervention_project ON intervention_logs(project_id);
CREATE INDEX IF NOT EXISTS idx_intervention_execution ON intervention_logs(workflow_execution_id);
CREATE INDEX IF NOT EXISTS idx_intervention_agent ON intervention_logs(agent_type);
CREATE INDEX IF NOT EXISTS idx_intervention_type ON intervention_logs(intervention_type);
CREATE INDEX IF NOT EXISTS idx_intervention_time ON intervention_logs(timestamp DESC);

-- ==================== 全文搜索索引 ====================

-- 为干预消息创建全文搜索索引（PostgreSQL）
CREATE INDEX IF NOT EXISTS idx_intervention_message_fts ON intervention_logs
USING gin(to_tsvector('simple', user_message));

-- ==================== 触发器：自动更新 updated_at ====================

CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_workflow_definitions_updated_at
    BEFORE UPDATE ON workflow_definitions
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ==================== 初始模板数据 ====================

-- 插入默认小说创作工作流模板
INSERT INTO workflow_definitions (id, project_id, name, description, nodes, edges, variables, is_template)
VALUES (
    'template_novel_workflow',
    '00000000-0000-0000-0000-000000000000',
    '小说创作标准流程',
    '完整的小说章节生成流程，包含设定准备、剧情规划、角色互动和内容输出四个阶段',
    '[
        {"id": "start", "node_type": "start", "label": "开始", "position": {"x": 400, "y": 0}},
        {"id": "parallel_prep", "node_type": "parallel", "label": "并行准备", "position": {"x": 400, "y": 80}},
        {"id": "setting", "node_type": "agent", "agent_type": "setting", "label": "设定Agent", "description": "确认世界观设定", "position": {"x": 200, "y": 160}},
        {"id": "events", "node_type": "agent", "agent_type": "event_generator", "label": "事件生成", "description": "生成初始事件池", "position": {"x": 400, "y": 160}},
        {"id": "map", "node_type": "agent", "agent_type": "world_map_manager", "label": "地图管理", "description": "确认地点信息", "position": {"x": 600, "y": 160}},
        {"id": "plotter", "node_type": "agent", "agent_type": "master_plotter", "label": "总编剧", "description": "规划章节大纲", "position": {"x": 400, "y": 240}},
        {"id": "hooks", "node_type": "agent", "agent_type": "hook_manager", "label": "伏笔管理", "description": "规划伏笔", "position": {"x": 400, "y": 320}},
        {"id": "character", "node_type": "agent", "agent_type": "character", "label": "角色演绎", "description": "角色对话生成", "position": {"x": 400, "y": 400}},
        {"id": "summarizer", "node_type": "agent", "agent_type": "summarizer", "label": "摘要提取", "description": "对话摘要", "position": {"x": 400, "y": 480}},
        {"id": "condition_chapter", "node_type": "condition", "label": "章节结束?", "position": {"x": 400, "y": 560}},
        {"id": "writer", "node_type": "agent", "agent_type": "writer", "label": "作家", "description": "章节写作", "position": {"x": 400, "y": 640}},
        {"id": "evaluator", "node_type": "agent", "agent_type": "evaluator", "label": "评估", "description": "质量评估", "position": {"x": 400, "y": 720}},
        {"id": "condition_quality", "node_type": "condition", "label": "质量达标?", "position": {"x": 400, "y": 800}},
        {"id": "end", "node_type": "end", "label": "结束", "position": {"x": 400, "y": 880}}
    ]'::jsonb,
    '[
        {"source": "start", "target": "parallel_prep"},
        {"source": "parallel_prep", "target": "setting"},
        {"source": "parallel_prep", "target": "events"},
        {"source": "parallel_prep", "target": "map"},
        {"source": "setting", "target": "plotter"},
        {"source": "events", "target": "plotter"},
        {"source": "map", "target": "plotter"},
        {"source": "plotter", "target": "hooks"},
        {"source": "hooks", "target": "character"},
        {"source": "character", "target": "summarizer"},
        {"source": "summarizer", "target": "condition_chapter"},
        {"source": "condition_chapter", "target": "writer", "condition": {"field": "chapter_end", "value": true}, "label": "是"},
        {"source": "condition_chapter", "target": "character", "condition": {"field": "chapter_end", "value": false}, "label": "否"},
        {"source": "writer", "target": "evaluator"},
        {"source": "evaluator", "target": "condition_quality"},
        {"source": "condition_quality", "target": "end", "condition": {"field": "quality_passed", "value": true}, "label": "是"},
        {"source": "condition_quality", "target": "writer", "condition": {"field": "quality_passed", "value": false}, "label": "否"}
    ]'::jsonb,
    '{"chapter_count": 3, "words_per_chapter": 2000}'::jsonb,
    true
) ON CONFLICT (id) DO NOTHING;

-- 插入快速对话工作流模板
INSERT INTO workflow_definitions (id, project_id, name, description, nodes, edges, variables, is_template)
VALUES (
    'template_dialogue_workflow',
    '00000000-0000-0000-0000-000000000000',
    '快速对话流程',
    '简化的角色对话生成流程，适用于快速测试',
    '[
        {"id": "start", "node_type": "start", "label": "开始", "position": {"x": 200, "y": 0}},
        {"id": "character", "node_type": "agent", "agent_type": "character", "label": "角色对话", "position": {"x": 200, "y": 100}},
        {"id": "end", "node_type": "end", "label": "结束", "position": {"x": 200, "y": 200}}
    ]'::jsonb,
    '[
        {"source": "start", "target": "character"},
        {"source": "character", "target": "end"}
    ]'::jsonb,
    '{}'::jsonb,
    true
) ON CONFLICT (id) DO NOTHING;

-- ==================== 完成提示 ====================

DO $$
BEGIN
    RAISE NOTICE 'V8 数据库迁移完成';
    RAISE NOTICE '已创建表: workflow_definitions, workflow_executions, intervention_logs';
    RAISE NOTICE '已插入 2 个预设工作流模板';
END $$;
