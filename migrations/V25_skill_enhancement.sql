-- V25: Skills 增强系统
-- 添加子技能、评估阈值、记忆集成、全局状态支持

-- ==================== 全局状态表 ====================

-- 全局状态主表
CREATE TABLE IF NOT EXISTS global_state (
    project_id UUID PRIMARY KEY REFERENCES projects(id) ON DELETE CASCADE,
    state_data JSONB NOT NULL DEFAULT '{}',
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 全局状态变更历史
CREATE TABLE IF NOT EXISTS global_state_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    agent_type VARCHAR(100),
    workflow_execution_id VARCHAR(100),
    changes JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_global_state_history_project ON global_state_history(project_id);
CREATE INDEX idx_global_state_history_workflow ON global_state_history(workflow_execution_id);

-- ==================== Skills 表扩展 ====================

-- 添加新字段到 skills 表
ALTER TABLE skills ADD COLUMN IF NOT EXISTS sub_skills JSONB DEFAULT '[]';
ALTER TABLE skills ADD COLUMN IF NOT EXISTS parent_skill_id VARCHAR(100);
ALTER TABLE skills ADD COLUMN IF NOT EXISTS evaluation_threshold JSONB;
ALTER TABLE skills ADD COLUMN IF NOT EXISTS on_failure_action VARCHAR(50) DEFAULT 'continue';
ALTER TABLE skills ADD COLUMN IF NOT EXISTS use_agent_memory BOOLEAN DEFAULT FALSE;
ALTER TABLE skills ADD COLUMN IF NOT EXISTS memory_types JSONB DEFAULT '[]';
ALTER TABLE skills ADD COLUMN IF NOT EXISTS reads_global_state JSONB DEFAULT '[]';
ALTER TABLE skills ADD COLUMN IF NOT EXISTS writes_global_state JSONB DEFAULT '[]';

-- ==================== 技能执行历史表 ====================

-- 记录技能执行的详细历史
CREATE TABLE IF NOT EXISTS skill_executions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    skill_id VARCHAR(100) NOT NULL,
    project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
    agent_type VARCHAR(100),
    agent_id VARCHAR(100),
    workflow_execution_id VARCHAR(100),
    workflow_node_id VARCHAR(100),

    -- 输入输出
    input_params JSONB DEFAULT '{}',
    output_result JSONB,

    -- 评估结果
    evaluation_score FLOAT,
    evaluation_dimensions JSONB,
    passed_threshold BOOLEAN,

    -- 执行状态
    status VARCHAR(50) DEFAULT 'completed', -- completed, failed, retried
    retry_count INT DEFAULT 0,
    error_message TEXT,

    -- 性能指标
    execution_time_ms INT,
    token_usage JSONB,

    -- 记忆集成
    memory_before JSONB,
    memory_after JSONB,
    global_state_changes JSONB,

    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_skill_executions_skill ON skill_executions(skill_id);
CREATE INDEX idx_skill_executions_project ON skill_executions(project_id);
CREATE INDEX idx_skill_executions_workflow ON skill_executions(workflow_execution_id);
CREATE INDEX idx_skill_executions_status ON skill_executions(status);

-- ==================== 更新现有 Skills ====================

-- 更新角色立场约束技能，添加记忆集成
UPDATE skills
SET
    use_agent_memory = TRUE,
    memory_types = '["decision", "fact"]'::jsonb,
    reads_global_state = '["current_chapter", "active_characters"]'::jsonb
WHERE id = 'skill_character_stance_constraint';

-- 更新章节大纲生成技能
UPDATE skills
SET
    use_agent_memory = TRUE,
    memory_types = '["decision", "observation"]'::jsonb,
    reads_global_state = '["main_plot_progress", "active_hooks", "villain_threat_level"]'::jsonb,
    writes_global_state = '["chapter_outlines", "planned_cool_points"]'::jsonb
WHERE id = 'skill_chapter_outline_generation';

-- 更新爽点设计技能
UPDATE skills
SET
    reads_global_state = '["planned_cool_points", "chapter_outlines"]'::jsonb,
    writes_global_state = '["planned_cool_points"]'::jsonb
WHERE id = 'skill_webnovel_cool_points';

-- 更新钩子设计技能
UPDATE skills
SET
    reads_global_state = '["active_hooks", "chapter_outlines"]'::jsonb,
    writes_global_state = '["planned_hooks"]'::jsonb
WHERE id = 'skill_chapter_hooks_design';

-- 更新反派动态技能
UPDATE skills
SET
    use_agent_memory = TRUE,
    memory_types = '["decision"]'::jsonb,
    reads_global_state = '["villain_threat_level", "villain_actions"]'::jsonb,
    writes_global_state = '["villain_threat_level", "villain_actions"]'::jsonb
WHERE id = 'skill_chapter_villain_arc';

-- ==================== 评估阈值预设 ====================

-- 为章节大纲生成技能添加评估阈值
UPDATE skills
SET evaluation_threshold = '{
    "min_score": 0.7,
    "blocking": true,
    "auto_retry": true,
    "max_retries": 2,
    "retry_strategy": "improve",
    "dimensions": ["completeness", "consistency", "stance_check"],
    "dimension_weights": {"completeness": 0.4, "consistency": 0.3, "stance_check": 0.3}
}'::jsonb
WHERE id = 'skill_chapter_outline_generation';

-- 为角色立场约束技能添加评估阈值
UPDATE skills
SET evaluation_threshold = '{
    "min_score": 0.9,
    "blocking": true,
    "auto_retry": true,
    "max_retries": 1,
    "retry_strategy": "regenerate",
    "dimensions": ["stance_consistency"],
    "dimension_weights": {"stance_consistency": 1.0}
}'::jsonb
WHERE id = 'skill_character_stance_constraint';

-- ==================== 新增质量评估技能 ====================

INSERT INTO skills (id, name, description, skill_type, category, tags, applicable_agent_types,
                    prompt_template, priority, status, is_system, is_enabled, load_mode,
                    use_agent_memory, memory_types, reads_global_state, writes_global_state,
                    evaluation_threshold)
VALUES (
    'skill_quality_evaluation',
    '内容质量评估',
    '对生成的内容进行多维度质量评估，支持阈值检查和自动重试建议',
    'prompt',
    'evaluation',
    '["评估", "质量检查", "阈值"]',
    '["evaluator"]',
    '# 内容质量评估技能

## 任务：质量评估

请对以下内容进行多维度质量评估。

### 评估配置

- 内容类型：{{content_type}}
- 评估维度：{{evaluation_dimensions}}
- 阈值配置：{{threshold_config}}

### 待评估内容

```
{{content}}
```

## 评估维度

### 1. 质量维度 (quality)
- 完整性：内容是否完整
- 连贯性：逻辑是否通顺
- 生动性：描写是否生动
- 节奏感：叙事节奏是否恰当

### 2. 一致性维度 (consistency)
- 角色一致性：行为是否符合设定
- 设定一致性：是否与世界观矛盾
- 剧情一致性：是否与前后文衔接

### 3. 立场检查维度 (stance_check)
- 反派行为：是否符合敌对立场
- 角色动机：行为是否有合理动机
- 立场标注：是否正确标注角色立场

## 输出格式

```json
{
  "overall_score": 0.75,
  "passed": true,
  "dimension_scores": {
    "quality": {"score": 0.8, "breakdown": {}},
    "consistency": {"score": 0.75, "breakdown": {}},
    "stance_check": {"score": 0.7, "breakdown": {}}
  },
  "issues": [
    {"type": "warning", "dimension": "stance_check", "description": "问题描述", "suggested_fix": "修正建议"}
  ],
  "suggestions": ["改进建议"],
  "retry_recommended": false,
  "retry_strategy": null
}
```',
    85,
    'active',
    true,
    true,
    'on_demand',
    true,
    '["decision", "observation"]',
    '["evaluation_history", "quality_trends"]',
    '["latest_evaluation", "quality_alerts"]',
    '{"min_score": 0.7, "blocking": true, "auto_retry": true, "max_retries": 2, "retry_strategy": "improve", "dimensions": ["quality", "consistency", "stance_check"], "dimension_weights": {"quality": 0.4, "consistency": 0.3, "stance_check": 0.3}}'::jsonb
)
ON CONFLICT (id) DO UPDATE SET
    prompt_template = EXCLUDED.prompt_template,
    evaluation_threshold = EXCLUDED.evaluation_threshold,
    use_agent_memory = EXCLUDED.use_agent_memory,
    reads_global_state = EXCLUDED.reads_global_state,
    writes_global_state = EXCLUDED.writes_global_state;

-- 为 Evaluator Agent 分配质量评估技能
INSERT INTO skill_assignments (id, skill_id, agent_type, slot_name, priority, is_enabled, is_required, load_mode)
SELECT
    'assign_evaluator_quality',
    'skill_quality_evaluation',
    'evaluator',
    'quality_check',
    85,
    true,
    true,
    'on_demand'
WHERE NOT EXISTS (
    SELECT 1 FROM skill_assignments
    WHERE skill_id = 'skill_quality_evaluation' AND agent_type = 'evaluator'
);

-- ==================== 新增复合技能：完整章节规划 ====================

INSERT INTO skills (id, name, description, skill_type, category, tags, applicable_agent_types,
                    priority, status, is_system, is_enabled, load_mode,
                    use_agent_memory, memory_types, reads_global_state, writes_global_state,
                    sub_skills, evaluation_threshold, on_failure_action)
VALUES (
    'skill_complete_chapter_planning',
    '完整章节规划',
    '复合技能，组合大纲生成、爽点设计、钩子设计和反派动态，生成完整的章节规划',
    'workflow',
    'plotting',
    '["章节", "规划", "复合技能"]',
    '["plot_outline", "master_plotter"]',
    88,
    'active',
    true,
    true,
    'on_demand',
    true,
    '["decision", "observation"]',
    '["main_plot_progress", "active_hooks", "villain_threat_level", "planned_cool_points"]',
    '["chapter_plans", "active_hooks", "villain_threat_level"]',
    '[
        {"skill_id": "skill_chapter_outline_generation", "slot_name": "outline", "execution_order": 1, "pass_output_to": "chapter_outline", "is_required": true},
        {"skill_id": "skill_webnovel_cool_points", "slot_name": "cool_points", "execution_order": 2, "pass_output_to": "cool_points_design", "is_required": true},
        {"skill_id": "skill_chapter_hooks_design", "slot_name": "hooks", "execution_order": 3, "pass_output_to": "hooks_design", "is_required": true},
        {"skill_id": "skill_chapter_villain_arc", "slot_name": "villain", "execution_order": 4, "pass_output_to": "villain_arc", "is_required": false}
    ]'::jsonb,
    '{"min_score": 0.7, "blocking": true, "auto_retry": true, "max_retries": 2, "retry_strategy": "improve", "dimensions": ["completeness", "consistency", "stance_check"], "dimension_weights": {"completeness": 0.4, "consistency": 0.3, "stance_check": 0.3}}'::jsonb,
    'retry'
)
ON CONFLICT (id) DO UPDATE SET
    sub_skills = EXCLUDED.sub_skills,
    evaluation_threshold = EXCLUDED.evaluation_threshold,
    use_agent_memory = EXCLUDED.use_agent_memory,
    reads_global_state = EXCLUDED.reads_global_state,
    writes_global_state = EXCLUDED.writes_global_state;

-- 为 Plot Outline Agent 分配完整章节规划技能
INSERT INTO skill_assignments (id, skill_id, agent_type, slot_name, priority, is_enabled, is_required, load_mode)
SELECT
    'assign_outline_complete_planning',
    'skill_complete_chapter_planning',
    'plot_outline',
    'complete_planning',
    88,
    true,
    false,  -- 推荐，非强制（可以单独使用子技能）
    'on_demand'
WHERE NOT EXISTS (
    SELECT 1 FROM skill_assignments
    WHERE skill_id = 'skill_complete_chapter_planning' AND agent_type = 'plot_outline'
);

-- ==================== 新增统一 IO 格式表 ====================

-- Agent 执行记录表（标准化输入输出）
CREATE TABLE IF NOT EXISTS agent_execution_records (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
    workflow_execution_id VARCHAR(100),
    workflow_node_id VARCHAR(100),

    -- Agent 信息
    agent_type VARCHAR(100) NOT NULL,
    agent_id VARCHAR(100),

    -- 统一输入
    task_type VARCHAR(100),
    instruction TEXT,
    input_context JSONB DEFAULT '{}',
    input_parameters JSONB DEFAULT '{}',

    -- 统一输出
    status VARCHAR(50) DEFAULT 'pending',  -- success/failed/partial/pending/retry
    output_content JSONB,
    structured_output JSONB DEFAULT '{}',
    quality_score FLOAT,
    quality_check JSONB,

    -- 后续动作
    next_actions JSONB DEFAULT '[]',

    -- 状态变更
    state_changes JSONB DEFAULT '{}',
    memory_updates JSONB DEFAULT '[]',

    -- 错误处理
    error_message TEXT,
    error_details JSONB,
    retry_count INT DEFAULT 0,

    -- 性能
    execution_time_ms INT,
    token_usage JSONB,

    -- 追踪
    request_id VARCHAR(100),
    correlation_id VARCHAR(100),

    created_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);

CREATE INDEX idx_agent_exec_records_project ON agent_execution_records(project_id);
CREATE INDEX idx_agent_exec_records_workflow ON agent_execution_records(workflow_execution_id);
CREATE INDEX idx_agent_exec_records_agent ON agent_execution_records(agent_type);
CREATE INDEX idx_agent_exec_records_status ON agent_execution_records(status);
CREATE INDEX idx_agent_exec_records_request ON agent_execution_records(request_id);

-- 技能调用记录表
CREATE TABLE IF NOT EXISTS skill_call_records (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
    workflow_execution_id VARCHAR(100),

    -- 技能信息
    skill_id VARCHAR(100) NOT NULL,
    skill_name VARCHAR(200),
    caller_agent VARCHAR(100) NOT NULL,

    -- 输入
    parameters JSONB DEFAULT '{}',
    context JSONB DEFAULT '{}',

    -- 输出
    success BOOLEAN DEFAULT TRUE,
    output JSONB,
    score FLOAT,
    passed_threshold BOOLEAN DEFAULT TRUE,

    -- 错误
    error_message TEXT,
    retry_count INT DEFAULT 0,

    -- 性能
    execution_time_ms INT,

    -- 关联
    request_id VARCHAR(100),

    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_skill_call_records_skill ON skill_call_records(skill_id);
CREATE INDEX idx_skill_call_records_project ON skill_call_records(project_id);
CREATE INDEX idx_skill_call_records_caller ON skill_call_records(caller_agent);
