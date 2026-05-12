-- V35: Skill Assignment 场景化
-- 将 Skill 分配从 agent_type 级别提升到 agent_type + scenario 级别。

ALTER TABLE skill_assignments
ADD COLUMN IF NOT EXISTS scenario VARCHAR(100) NOT NULL DEFAULT 'default';

UPDATE skill_assignments
SET scenario = 'default'
WHERE scenario IS NULL OR scenario = '';

ALTER TABLE skill_assignments
DROP CONSTRAINT IF EXISTS skill_assignments_skill_id_agent_type_slot_name_key;

ALTER TABLE skill_assignments
ADD CONSTRAINT skill_assignments_skill_agent_scenario_slot_key
UNIQUE(skill_id, agent_type, scenario, slot_name);

DROP INDEX IF EXISTS idx_skill_assignments_agent;

CREATE INDEX IF NOT EXISTS idx_skill_assignments_agent_scenario
ON skill_assignments(agent_type, scenario);
