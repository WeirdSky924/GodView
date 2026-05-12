-- V34: Agent Template 场景化
-- 为 AgentTemplate / AgentConfig 增加 scenario 字段，支持 agent_type + scenario 解析运行时模板。

ALTER TABLE agent_templates
ADD COLUMN IF NOT EXISTS scenario VARCHAR(100) NOT NULL DEFAULT 'default';

ALTER TABLE agent_configs
ADD COLUMN IF NOT EXISTS scenario VARCHAR(100) NOT NULL DEFAULT 'default';

UPDATE agent_templates
SET scenario = 'workflow_summary'
WHERE id = 'director_summarizer' AND (scenario IS NULL OR scenario = 'default');

UPDATE agent_templates
SET scenario = 'workflow_plot_planning'
WHERE id = 'director_master_plotter' AND (scenario IS NULL OR scenario = 'default');

UPDATE agent_templates
SET scenario = 'workflow_hook_management'
WHERE id = 'director_hook_manager' AND (scenario IS NULL OR scenario = 'default');

UPDATE agent_templates
SET scenario = 'workflow_chapter_generation'
WHERE id = 'director_writer' AND (scenario IS NULL OR scenario = 'default');

UPDATE agent_templates
SET scenario = 'chapter_quality_review'
WHERE id = 'evaluator' AND (scenario IS NULL OR scenario = 'default');

UPDATE agent_templates
SET scenario = 'procedural_generation'
WHERE id = 'proc_gen' AND (scenario IS NULL OR scenario = 'default');

UPDATE agent_templates
SET scenario = 'workflow_context'
WHERE id = 'setting' AND (scenario IS NULL OR scenario = 'default');

UPDATE agent_templates
SET scenario = 'roleplay'
WHERE id = 'character' AND (scenario IS NULL OR scenario = 'default');

UPDATE agent_templates
SET scenario = 'event_generation'
WHERE id = 'event_generator' AND (scenario IS NULL OR scenario = 'default');

UPDATE agent_templates
SET scenario = 'world_map_management'
WHERE id = 'world_map_manager' AND (scenario IS NULL OR scenario = 'default');

UPDATE agent_templates
SET scenario = 'dungeon_generation'
WHERE id = 'dungeon_generator' AND (scenario IS NULL OR scenario = 'default');

UPDATE agent_templates
SET scenario = 'generate_chapter_outline'
WHERE id = 'plot_outline' AND (scenario IS NULL OR scenario = 'default');

UPDATE agent_templates
SET scenario = 'scene_coordination'
WHERE id = 'scene_coordinator' AND (scenario IS NULL OR scenario = 'default');

CREATE INDEX IF NOT EXISTS idx_agent_templates_agent_type_scenario
ON agent_templates(agent_type, scenario);

CREATE INDEX IF NOT EXISTS idx_agent_configs_project_agent_scenario
ON agent_configs(project_id, agent_type, scenario);
