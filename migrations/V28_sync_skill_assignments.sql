-- V28: 同步所有现有 Skill 的 applicable_agent_types 到 skill_assignments 表
-- 确保统一系统生效

-- 为每个 Skill 的 applicable_agent_types 创建对应的 skill_assignments 记录
-- 使用 category 作为默认 slot_name，priority 使用 Skill 的 priority

INSERT INTO skill_assignments (id, skill_id, agent_type, slot_name, priority, is_enabled, is_required, variable_overrides, assigned_by)
SELECT
    'assign_' || s.id || '_' || agent_type.value as id,
    s.id as skill_id,
    agent_type.value as agent_type,
    COALESCE(s.category, 'general') as slot_name,
    COALESCE(s.priority, 50) as priority,
    true as is_enabled,
    false as is_required,
    '{}'::jsonb as variable_overrides,
    'system' as assigned_by
FROM skills s
CROSS JOIN LATERAL jsonb_array_elements_text(s.applicable_agent_types::jsonb) as agent_type(value)
WHERE s.applicable_agent_types IS NOT NULL
  AND s.applicable_agent_types::jsonb != '[]'::jsonb
  AND s.is_enabled = true
ON CONFLICT (skill_id, agent_type, slot_name) DO UPDATE SET
    priority = EXCLUDED.priority,
    is_enabled = EXCLUDED.is_enabled;

-- 删除不再适用的分配（Skill 的 applicable_agent_types 已更新，但 skill_assignments 未同步）
DELETE FROM skill_assignments sa
WHERE NOT EXISTS (
    SELECT 1 FROM skills s
    WHERE s.id = sa.skill_id
    AND s.applicable_agent_types::jsonb ? sa.agent_type
);
