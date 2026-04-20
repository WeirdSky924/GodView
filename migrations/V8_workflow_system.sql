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
    NULL,
    '小说创作标准流程',
    '完整的小说章节生成流程，包含设定准备、剧情规划、角色互动和内容输出四个阶段',
    '[
        {"id": "start", "node_type": "start", "label": "开始", "position": {"x": 400, "y": 0}},
        {"id": "parallel_prep", "node_type": "parallel", "label": "并行执行", "position": {"x": 400, "y": 80}},
        {"id": "setting", "node_type": "agent", "agent_type": "setting", "label": "设定 Agent", "description": "确认世界观设定", "position": {"x": 200, "y": 160}},
        {"id": "events", "node_type": "agent", "agent_type": "event_generator", "label": "事件 Agent", "description": "生成初始事件池", "position": {"x": 400, "y": 160}},
        {"id": "map", "node_type": "agent", "agent_type": "world_map_manager", "label": "地图 Agent", "description": "确认地点信息", "position": {"x": 600, "y": 160}},
        {"id": "plotter", "node_type": "agent", "agent_type": "master_plotter", "label": "总编剧 Agent", "description": "规划章节大纲", "position": {"x": 400, "y": 240}},
        {"id": "hooks", "node_type": "agent", "agent_type": "hook_manager", "label": "伏笔 Agent", "description": "规划伏笔", "position": {"x": 400, "y": 320}},
        {"id": "character", "node_type": "agent", "agent_type": "character", "label": "角色 Agent", "description": "角色对话生成", "position": {"x": 400, "y": 400}},
        {"id": "summarizer", "node_type": "agent", "agent_type": "summarizer", "label": "摘要 Agent", "description": "对话摘要", "position": {"x": 400, "y": 480}},
        {"id": "condition_chapter", "node_type": "condition", "label": "条件分支", "position": {"x": 400, "y": 560}},
        {"id": "writer", "node_type": "agent", "agent_type": "writer", "label": "作家 Agent", "description": "章节写作", "position": {"x": 400, "y": 640}},
        {"id": "evaluator", "node_type": "agent", "agent_type": "evaluator", "label": "评估 Agent", "description": "质量评估", "position": {"x": 400, "y": 720}},
        {"id": "condition_quality", "node_type": "condition", "label": "条件分支", "position": {"x": 400, "y": 800}},
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
    NULL,
    '快速对话流程',
    '简化的角色对话生成流程，适用于快速测试',
    '[
        {"id": "start", "node_type": "start", "label": "开始", "position": {"x": 200, "y": 0}},
        {"id": "character", "node_type": "agent", "agent_type": "character", "label": "角色 Agent", "position": {"x": 200, "y": 100}},
        {"id": "end", "node_type": "end", "label": "结束", "position": {"x": 200, "y": 200}}
    ]'::jsonb,
    '[
        {"source": "start", "target": "character"},
        {"source": "character", "target": "end"}
    ]'::jsonb,
    '{}'::jsonb,
    true
) ON CONFLICT (id) DO NOTHING;

-- 插入全内置节点标准工作流模板
INSERT INTO workflow_definitions (id, project_id, name, description, nodes, edges, variables, is_template)
VALUES (
    'template_all_builtin_workflow',
    NULL,
    '全内置节点标准流程',
    '包含全部内置系统节点的标准创作工作流，突出章节大纲驱动、并行执行和逐节点输入输出观察。',
    $$[
        {
            "id": "start",
            "node_type": "start",
            "label": "开始",
            "description": "加载项目基础上下文",
            "config": {},
            "position": {"x": 520, "y": 20},
            "outputs": [
                {"name": "project_info", "target": "context", "key": "project_info", "save_to_db": false},
                {"name": "world_info", "target": "context", "key": "world_info", "save_to_db": false},
                {"name": "characters", "target": "context", "key": "characters", "save_to_db": false},
                {"name": "lore_entries", "target": "context", "key": "lore_entries", "save_to_db": false},
                {"name": "existing_hooks", "target": "context", "key": "existing_hooks", "save_to_db": false},
                {"name": "events", "target": "context", "key": "events", "save_to_db": false},
                {"name": "locations", "target": "context", "key": "locations", "save_to_db": false},
                {"name": "previous_chapters", "target": "context", "key": "previous_chapters", "save_to_db": false}
            ]
        },
        {
            "id": "plot_outline",
            "node_type": "agent",
            "agent_type": "plot_outline",
            "label": "章节大纲 Agent",
            "description": "先产出当前章节目标与章节大纲",
            "config": {},
            "position": {"x": 520, "y": 120},
            "inputs": [
                {"name": "chapter_num", "source": "context", "key": "chapter_num", "required": true, "default": 1},
                {"name": "project_info", "source": "context", "key": "project_info", "required": false},
                {"name": "world_info", "source": "context", "key": "world_info", "required": false},
                {"name": "lore_entries", "source": "context", "key": "lore_entries", "required": false},
                {"name": "characters", "source": "context", "key": "characters", "required": false},
                {"name": "existing_hooks", "source": "context", "key": "existing_hooks", "required": false},
                {"name": "previous_chapters", "source": "context", "key": "previous_chapters", "required": false}
            ],
            "outputs": [
                {"name": "chapter_number", "target": "context", "key": "chapter_number", "save_to_db": false},
                {"name": "chapter_title", "target": "context", "key": "chapter_title", "save_to_db": false},
                {"name": "chapter_outline", "target": "context", "key": "chapter_outline", "save_to_db": false},
                {"name": "chapter_summary", "target": "context", "key": "chapter_summary", "save_to_db": false},
                {"name": "scene_directions", "target": "context", "key": "scene_directions", "save_to_db": false},
                {"name": "chapter_goals", "target": "context", "key": "chapter_goals", "save_to_db": false}
            ]
        },
        {
            "id": "parallel_prep",
            "node_type": "parallel",
            "label": "并行执行",
            "description": "围绕章节大纲并行执行设定、事件、地图与探索素材",
            "config": {},
            "position": {"x": 520, "y": 220}
        },
        {
            "id": "setting",
            "node_type": "agent",
            "agent_type": "setting",
            "label": "设定 Agent",
            "description": "根据本章目标补充设定约束",
            "config": {"task": "chapter_setting_alignment"},
            "position": {"x": 80, "y": 340},
            "inputs": [
                {"name": "chapter_outline", "source": "upstream", "upstream_node": "plot_outline", "upstream_field": "chapter_outline", "required": false},
                {"name": "chapter_goals", "source": "upstream", "upstream_node": "plot_outline", "upstream_field": "chapter_goals", "required": false},
                {"name": "lore_entries", "source": "context", "key": "lore_entries", "required": false},
                {"name": "world_info", "source": "context", "key": "world_info", "required": false}
            ],
            "outputs": [
                {"name": "lore_entries", "target": "context", "key": "lore_entries", "save_to_db": false},
                {"name": "setting_updates", "target": "context", "key": "setting_updates", "save_to_db": false}
            ]
        },
        {
            "id": "event_generator",
            "node_type": "agent",
            "agent_type": "event_generator",
            "label": "事件 Agent",
            "description": "根据章节大纲生成事件候选",
            "config": {},
            "position": {"x": 280, "y": 340},
            "inputs": [
                {"name": "chapter_outline", "source": "upstream", "upstream_node": "plot_outline", "upstream_field": "chapter_outline", "required": false},
                {"name": "chapter_goals", "source": "upstream", "upstream_node": "plot_outline", "upstream_field": "chapter_goals", "required": false},
                {"name": "events", "source": "context", "key": "events", "required": false}
            ],
            "outputs": [
                {"name": "events", "target": "context", "key": "events", "save_to_db": false},
                {"name": "event_candidates", "target": "context", "key": "event_candidates", "save_to_db": false}
            ]
        },
        {
            "id": "world_map_manager",
            "node_type": "agent",
            "agent_type": "world_map_manager",
            "label": "地图 Agent",
            "description": "基于场景方向准备地图与地点信息",
            "config": {},
            "position": {"x": 480, "y": 340},
            "inputs": [
                {"name": "scene_directions", "source": "upstream", "upstream_node": "plot_outline", "upstream_field": "scene_directions", "required": false},
                {"name": "chapter_outline", "source": "upstream", "upstream_node": "plot_outline", "upstream_field": "chapter_outline", "required": false},
                {"name": "world_info", "source": "context", "key": "world_info", "required": false},
                {"name": "locations", "source": "context", "key": "locations", "required": false}
            ],
            "outputs": [
                {"name": "locations", "target": "context", "key": "locations", "save_to_db": false},
                {"name": "world_map_plan", "target": "context", "key": "world_map_plan", "save_to_db": false}
            ]
        },
        {
            "id": "proc_gen",
            "node_type": "agent",
            "agent_type": "proc_gen",
            "label": "过程生成 Agent",
            "description": "扩展探索区域和环境细节",
            "config": {},
            "position": {"x": 680, "y": 340},
            "inputs": [
                {"name": "scene_directions", "source": "upstream", "upstream_node": "plot_outline", "upstream_field": "scene_directions", "required": false},
                {"name": "chapter_goals", "source": "upstream", "upstream_node": "plot_outline", "upstream_field": "chapter_goals", "required": false},
                {"name": "world_info", "source": "context", "key": "world_info", "required": false}
            ],
            "outputs": [
                {"name": "regions", "target": "context", "key": "regions", "save_to_db": false},
                {"name": "procgen_result", "target": "context", "key": "procgen_result", "save_to_db": false}
            ]
        },
        {
            "id": "dungeon_generator",
            "node_type": "agent",
            "agent_type": "dungeon_generator",
            "label": "副本生成 Agent",
            "description": "如章节涉及探索/副本则生成可用结构",
            "config": {},
            "position": {"x": 880, "y": 340},
            "inputs": [
                {"name": "scene_directions", "source": "upstream", "upstream_node": "plot_outline", "upstream_field": "scene_directions", "required": false},
                {"name": "chapter_outline", "source": "upstream", "upstream_node": "plot_outline", "upstream_field": "chapter_outline", "required": false}
            ],
            "outputs": [
                {"name": "dungeon_plan", "target": "context", "key": "dungeon_plan", "save_to_db": false}
            ]
        },
        {
            "id": "group_discussion",
            "node_type": "group_discussion",
            "label": "集体讨论",
            "description": "汇总并行结果，形成统一创作方向",
            "config": {"leader_agent": "master_plotter"},
            "position": {"x": 520, "y": 500},
            "inputs": [
                {"name": "chapter_title", "source": "upstream", "upstream_node": "plot_outline", "upstream_field": "chapter_title", "required": false},
                {"name": "chapter_outline", "source": "upstream", "upstream_node": "plot_outline", "upstream_field": "chapter_outline", "required": false},
                {"name": "chapter_goals", "source": "upstream", "upstream_node": "plot_outline", "upstream_field": "chapter_goals", "required": false},
                {"name": "events", "source": "upstream", "upstream_node": "event_generator", "upstream_field": "events", "required": false},
                {"name": "lore_entries", "source": "upstream", "upstream_node": "setting", "upstream_field": "lore_entries", "required": false},
                {"name": "locations", "source": "upstream", "upstream_node": "world_map_manager", "upstream_field": "locations", "required": false},
                {"name": "regions", "source": "upstream", "upstream_node": "proc_gen", "upstream_field": "regions", "required": false},
                {"name": "dungeon_plan", "source": "upstream", "upstream_node": "dungeon_generator", "upstream_field": "dungeon_plan", "required": false}
            ],
            "outputs": [
                {"name": "group_discussion", "target": "context", "key": "group_discussion", "save_to_db": false},
                {"name": "last_discussion_summary", "target": "context", "key": "last_discussion_summary", "save_to_db": false}
            ]
        },
        {
            "id": "hook_manager",
            "node_type": "agent",
            "agent_type": "hook_manager",
            "label": "伏笔 Agent",
            "description": "根据章节大纲和讨论结果规划伏笔",
            "config": {},
            "position": {"x": 520, "y": 620},
            "inputs": [
                {"name": "chapter_outline", "source": "upstream", "upstream_node": "plot_outline", "upstream_field": "chapter_outline", "required": false},
                {"name": "chapter_goals", "source": "upstream", "upstream_node": "plot_outline", "upstream_field": "chapter_goals", "required": false},
                {"name": "existing_hooks", "source": "context", "key": "existing_hooks", "required": false},
                {"name": "last_discussion_summary", "source": "context", "key": "last_discussion_summary", "required": false}
            ],
            "outputs": [
                {"name": "hooks", "target": "context", "key": "hooks", "save_to_db": false},
                {"name": "existing_hooks", "target": "context", "key": "existing_hooks", "save_to_db": false}
            ]
        },
        {
            "id": "scene_performance",
            "node_type": "scene_performance",
            "label": "场景演绎",
            "description": "根据场景指令组织多角色演绎",
            "config": {"scene_mode": "interactive"},
            "position": {"x": 520, "y": 740},
            "inputs": [
                {"name": "scene_directions", "source": "upstream", "upstream_node": "plot_outline", "upstream_field": "scene_directions", "required": false},
                {"name": "chapter_outline", "source": "upstream", "upstream_node": "plot_outline", "upstream_field": "chapter_outline", "required": false},
                {"name": "characters", "source": "context", "key": "characters", "required": false}
            ],
            "outputs": [
                {"name": "performance_result", "target": "context", "key": "performance_result", "save_to_db": false},
                {"name": "dialogues", "target": "context", "key": "dialogues", "save_to_db": false}
            ]
        },
        {
            "id": "summarizer",
            "node_type": "agent",
            "agent_type": "summarizer",
            "label": "摘要 Agent",
            "description": "压缩上游结果为写作可用摘要",
            "config": {},
            "position": {"x": 520, "y": 860},
            "inputs": [
                {"name": "chapter_summary", "source": "upstream", "upstream_node": "plot_outline", "upstream_field": "chapter_summary", "required": false},
                {"name": "last_discussion_summary", "source": "context", "key": "last_discussion_summary", "required": false},
                {"name": "performance_result", "source": "context", "key": "performance_result", "required": false},
                {"name": "hooks", "source": "context", "key": "hooks", "required": false}
            ],
            "outputs": [
                {"name": "summary", "target": "context", "key": "summary", "save_to_db": false},
                {"name": "chapter_summary", "target": "context", "key": "chapter_summary", "save_to_db": false}
            ]
        },
        {
            "id": "condition_need_input",
            "node_type": "condition",
            "label": "条件分支",
            "description": "保留交互检查点，通常走通过分支",
            "config": {"condition_key": "need_user_input", "pass_value": false, "pass_when_missing": true},
            "position": {"x": 520, "y": 980},
            "inputs": [
                {"name": "summary", "source": "context", "key": "summary", "required": false},
                {"name": "chapter_outline", "source": "context", "key": "chapter_outline", "required": false}
            ],
            "outputs": [
                {"name": "quality_passed", "target": "context", "key": "quality_passed", "save_to_db": false}
            ]
        },
        {
            "id": "input",
            "node_type": "input",
            "label": "用户输入",
            "description": "当需要人工补充时暂停",
            "config": {"prompt": "请补充本章的额外要求或修订意见"},
            "position": {"x": 850, "y": 980},
            "outputs": [
                {"name": "status", "target": "context", "key": "input_status", "save_to_db": false}
            ]
        },
        {
            "id": "master_plotter",
            "node_type": "agent",
            "agent_type": "master_plotter",
            "label": "总编剧 Agent",
            "description": "统一整理为写作计划",
            "config": {},
            "position": {"x": 520, "y": 1100},
            "inputs": [
                {"name": "chapter_outline", "source": "context", "key": "chapter_outline", "required": false},
                {"name": "chapter_goals", "source": "context", "key": "chapter_goals", "required": false},
                {"name": "summary", "source": "context", "key": "summary", "required": false},
                {"name": "hooks", "source": "context", "key": "hooks", "required": false},
                {"name": "events", "source": "context", "key": "events", "required": false},
                {"name": "locations", "source": "context", "key": "locations", "required": false}
            ],
            "outputs": [
                {"name": "plot_outline", "target": "context", "key": "plot_outline", "save_to_db": false},
                {"name": "chapter_outline", "target": "context", "key": "chapter_outline", "save_to_db": false},
                {"name": "chapter_goals", "target": "context", "key": "chapter_goals", "save_to_db": false}
            ]
        },
        {
            "id": "writer",
            "node_type": "agent",
            "agent_type": "writer",
            "label": "作家 Agent",
            "description": "根据大纲与摘要完成章节写作",
            "config": {},
            "position": {"x": 520, "y": 1220},
            "inputs": [
                {"name": "chapter_title", "source": "context", "key": "chapter_title", "required": false},
                {"name": "chapter_outline", "source": "context", "key": "chapter_outline", "required": false},
                {"name": "chapter_goals", "source": "context", "key": "chapter_goals", "required": false},
                {"name": "summary", "source": "context", "key": "summary", "required": false},
                {"name": "scene_directions", "source": "context", "key": "scene_directions", "required": false},
                {"name": "hooks", "source": "context", "key": "hooks", "required": false},
                {"name": "retry_message", "source": "context", "key": "retry_message", "required": false}
            ],
            "outputs": [
                {"name": "content", "target": "context", "key": "chapter_content", "save_to_db": false},
                {"name": "summary", "target": "context", "key": "writer_summary", "save_to_db": false}
            ]
        },
        {
            "id": "evaluator",
            "node_type": "agent",
            "agent_type": "evaluator",
            "label": "评估 Agent",
            "description": "给出质量判定和修订建议",
            "config": {},
            "position": {"x": 520, "y": 1340},
            "inputs": [
                {"name": "chapter_content", "source": "context", "key": "chapter_content", "required": false},
                {"name": "chapter_outline", "source": "context", "key": "chapter_outline", "required": false},
                {"name": "chapter_goals", "source": "context", "key": "chapter_goals", "required": false},
                {"name": "lore_entries", "source": "context", "key": "lore_entries", "required": false}
            ],
            "outputs": [
                {"name": "quality_passed", "target": "context", "key": "quality_passed", "save_to_db": false},
                {"name": "issues", "target": "context", "key": "evaluation_issues", "save_to_db": false},
                {"name": "suggestions", "target": "context", "key": "revision_notes", "save_to_db": false}
            ]
        },
        {
            "id": "condition_quality",
            "node_type": "condition",
            "label": "条件分支",
            "description": "决定结束还是回到写作修订",
            "config": {"condition_key": "evaluation_passed", "pass_value": true, "pass_when_missing": false},
            "position": {"x": 520, "y": 1460},
            "inputs": [
                {"name": "quality_passed", "source": "context", "key": "evaluation_passed", "required": false, "default": false},
                {"name": "evaluation_feedback", "source": "context", "key": "evaluation_feedback", "required": false}
            ],
            "outputs": [
                {"name": "quality_passed", "target": "context", "key": "quality_passed", "save_to_db": false},
                {"name": "revision_notes", "target": "context", "key": "revision_notes", "save_to_db": false}
            ]
        },
        {
            "id": "end",
            "node_type": "end",
            "label": "结束",
            "description": "输出完成",
            "config": {},
            "position": {"x": 520, "y": 1580}
        }
    ]$$::jsonb,
    $$[
        {"id": "e1", "source": "start", "target": "plot_outline"},
        {"id": "e2", "source": "plot_outline", "target": "parallel_prep"},
        {"id": "e3", "source": "parallel_prep", "target": "setting"},
        {"id": "e4", "source": "parallel_prep", "target": "event_generator"},
        {"id": "e5", "source": "parallel_prep", "target": "world_map_manager"},
        {"id": "e6", "source": "parallel_prep", "target": "proc_gen"},
        {"id": "e7", "source": "parallel_prep", "target": "dungeon_generator"},
        {"id": "e8", "source": "setting", "target": "group_discussion"},
        {"id": "e9", "source": "event_generator", "target": "group_discussion"},
        {"id": "e10", "source": "world_map_manager", "target": "group_discussion"},
        {"id": "e11", "source": "proc_gen", "target": "group_discussion"},
        {"id": "e12", "source": "dungeon_generator", "target": "group_discussion"},
        {"id": "e13", "source": "group_discussion", "target": "hook_manager"},
        {"id": "e14", "source": "hook_manager", "target": "scene_performance"},
        {"id": "e15", "source": "scene_performance", "target": "summarizer"},
        {"id": "e16", "source": "summarizer", "target": "condition_need_input", "condition": {"result": "pass"}, "label": "继续"},
        {"id": "e17", "source": "condition_need_input", "target": "master_plotter", "condition": {"result": "pass"}, "label": "继续"},
        {"id": "e18", "source": "condition_need_input", "target": "input", "condition": {"result": "retry"}, "label": "补充"},
        {"id": "e19", "source": "input", "target": "master_plotter"},
        {"id": "e20", "source": "master_plotter", "target": "writer"},
        {"id": "e21", "source": "writer", "target": "evaluator"},
        {"id": "e22", "source": "evaluator", "target": "condition_quality"},
        {"id": "e23", "source": "condition_quality", "target": "end", "condition": {"result": "pass"}, "label": "通过"},
        {"id": "e24", "source": "condition_quality", "target": "writer", "condition": {"result": "retry"}, "label": "返工"}
    ]$$::jsonb,
    '{"chapter_num": 1, "target_word_count": 2000}'::jsonb,
    true
)
ON CONFLICT (id) DO UPDATE SET
    name = EXCLUDED.name,
    description = EXCLUDED.description,
    nodes = EXCLUDED.nodes,
    edges = EXCLUDED.edges,
    variables = EXCLUDED.variables,
    is_template = EXCLUDED.is_template,
    updated_at = CURRENT_TIMESTAMP;

-- ==================== 完成提示 ====================

DO $$
BEGIN
    RAISE NOTICE 'V8 数据库迁移完成';
    RAISE NOTICE '已创建表: workflow_definitions, workflow_executions, intervention_logs';
    RAISE NOTICE '已插入 3 个预设工作流模板';
END $$;
