-- V20: 修正 Agent-Prompt 绑定关系
-- 使 agent_prompt_bindings 与 system_agent_templates.py 中的 prompt_slots 一致

-- 首先检查并添加 originality_guidelines 和 base_json_output 的绑定
-- system_agent_templates.py 中所有 Agent 都使用 originality_guidelines 和 role_xxx + function_xxx

-- 删除旧的绑定（使用 prompt_common_rules 和 prompt_writing_standards）
DELETE FROM agent_prompt_bindings WHERE prompt_id IN ('prompt_common_rules', 'prompt_writing_standards');

-- 重新创建正确的绑定关系

-- ==================== 摘要员 ====================
INSERT INTO agent_prompt_bindings (id, agent_type, prompt_id, binding_type, priority, is_required) VALUES
('bind_summarizer_orig', 'summarizer', 'originality_guidelines', 'constraint', 95, true),
('bind_summarizer_role', 'summarizer', 'role_summarizer', 'identity', 90, true),
('bind_summarizer_func', 'summarizer', 'function_summarize', 'instruction', 80, true),
('bind_summarizer_output', 'summarizer', 'base_json_output', 'output', 70, true)
ON CONFLICT (id) DO UPDATE SET prompt_id = EXCLUDED.prompt_id, binding_type = EXCLUDED.binding_type;

-- ==================== 总编剧 ====================
INSERT INTO agent_prompt_bindings (id, agent_type, prompt_id, binding_type, priority, is_required) VALUES
('bind_master_plotter_orig', 'master_plotter', 'originality_guidelines', 'constraint', 95, true),
('bind_master_plotter_role', 'master_plotter', 'role_master_plotter', 'identity', 90, true),
('bind_master_plotter_func', 'master_plotter', 'function_plot_management', 'instruction', 80, true),
('bind_master_plotter_output', 'master_plotter', 'base_json_output', 'output', 70, true)
ON CONFLICT (id) DO UPDATE SET prompt_id = EXCLUDED.prompt_id, binding_type = EXCLUDED.binding_type;

-- ==================== 伏笔管理员 ====================
INSERT INTO agent_prompt_bindings (id, agent_type, prompt_id, binding_type, priority, is_required) VALUES
('bind_hook_manager_orig', 'hook_manager', 'originality_guidelines', 'constraint', 95, true),
('bind_hook_manager_role', 'hook_manager', 'role_hook_manager', 'identity', 90, true),
('bind_hook_manager_func', 'hook_manager', 'function_hook_management', 'instruction', 80, true),
('bind_hook_manager_output', 'hook_manager', 'base_json_output', 'output', 70, true)
ON CONFLICT (id) DO UPDATE SET prompt_id = EXCLUDED.prompt_id, binding_type = EXCLUDED.binding_type;

-- ==================== 作家 ====================
INSERT INTO agent_prompt_bindings (id, agent_type, prompt_id, binding_type, priority, is_required) VALUES
('bind_writer_orig', 'writer', 'originality_guidelines', 'constraint', 95, true),
('bind_writer_role', 'writer', 'role_writer', 'identity', 90, true),
('bind_writer_func', 'writer', 'function_writing', 'instruction', 85, true),
('bind_writer_output', 'writer', 'base_json_output', 'output', 70, false)
ON CONFLICT (id) DO UPDATE SET prompt_id = EXCLUDED.prompt_id, binding_type = EXCLUDED.binding_type;

-- ==================== 评估员 ====================
INSERT INTO agent_prompt_bindings (id, agent_type, prompt_id, binding_type, priority, is_required) VALUES
('bind_evaluator_orig', 'evaluator', 'originality_guidelines', 'constraint', 95, true),
('bind_evaluator_role', 'evaluator', 'role_evaluator', 'identity', 90, true),
('bind_evaluator_func', 'evaluator', 'function_evaluation', 'instruction', 80, true),
('bind_evaluator_output', 'evaluator', 'base_json_output', 'output', 70, true)
ON CONFLICT (id) DO UPDATE SET prompt_id = EXCLUDED.prompt_id, binding_type = EXCLUDED.binding_type;

-- ==================== 设定管理员 ====================
INSERT INTO agent_prompt_bindings (id, agent_type, prompt_id, binding_type, priority, is_required) VALUES
('bind_setting_orig', 'setting', 'originality_guidelines', 'constraint', 95, true),
('bind_setting_role', 'setting', 'role_setting', 'identity', 90, true),
('bind_setting_output', 'setting', 'base_json_output', 'output', 70, true)
ON CONFLICT (id) DO UPDATE SET prompt_id = EXCLUDED.prompt_id, binding_type = EXCLUDED.binding_type;

-- ==================== 角色Agent ====================
INSERT INTO agent_prompt_bindings (id, agent_type, prompt_id, binding_type, priority, is_required) VALUES
('bind_character_orig', 'character', 'originality_guidelines', 'constraint', 95, true),
('bind_character_role', 'character', 'role_character', 'identity', 90, true)
ON CONFLICT (id) DO UPDATE SET prompt_id = EXCLUDED.prompt_id, binding_type = EXCLUDED.binding_type;

-- ==================== 事件生成器 ====================
INSERT INTO agent_prompt_bindings (id, agent_type, prompt_id, binding_type, priority, is_required) VALUES
('bind_event_generator_orig', 'event_generator', 'originality_guidelines', 'constraint', 95, true),
('bind_event_generator_role', 'event_generator', 'role_event_generator', 'identity', 90, true),
('bind_event_generator_func', 'event_generator', 'function_event_generation', 'instruction', 80, true),
('bind_event_generator_output', 'event_generator', 'base_json_output', 'output', 70, true)
ON CONFLICT (id) DO UPDATE SET prompt_id = EXCLUDED.prompt_id, binding_type = EXCLUDED.binding_type;

-- ==================== 副本生成器 ====================
INSERT INTO agent_prompt_bindings (id, agent_type, prompt_id, binding_type, priority, is_required) VALUES
('bind_dungeon_generator_orig', 'dungeon_generator', 'originality_guidelines', 'constraint', 95, true),
('bind_dungeon_generator_role', 'dungeon_generator', 'role_dungeon_generator', 'identity', 90, true),
('bind_dungeon_generator_func', 'dungeon_generator', 'function_dungeon_design', 'instruction', 80, true),
('bind_dungeon_generator_output', 'dungeon_generator', 'base_json_output', 'output', 70, true)
ON CONFLICT (id) DO UPDATE SET prompt_id = EXCLUDED.prompt_id, binding_type = EXCLUDED.binding_type;

-- ==================== 世界地图管理员 ====================
INSERT INTO agent_prompt_bindings (id, agent_type, prompt_id, binding_type, priority, is_required) VALUES
('bind_world_map_manager_orig', 'world_map_manager', 'originality_guidelines', 'constraint', 95, true),
('bind_world_map_manager_role', 'world_map_manager', 'role_world_map_manager', 'identity', 90, true),
('bind_world_map_manager_func', 'world_map_manager', 'function_map_management', 'instruction', 80, true),
('bind_world_map_manager_output', 'world_map_manager', 'base_json_output', 'output', 70, true)
ON CONFLICT (id) DO UPDATE SET prompt_id = EXCLUDED.prompt_id, binding_type = EXCLUDED.binding_type;

-- ==================== 章节大纲规划 ====================
INSERT INTO agent_prompt_bindings (id, agent_type, prompt_id, binding_type, priority, is_required) VALUES
('bind_plot_outline_orig', 'plot_outline', 'originality_guidelines', 'constraint', 95, true),
('bind_plot_outline_role', 'plot_outline', 'role_plot_outline', 'identity', 90, true),
('bind_plot_outline_func', 'plot_outline', 'function_plot_outline', 'instruction', 80, true),
('bind_plot_outline_output', 'plot_outline', 'base_json_output', 'output', 70, true)
ON CONFLICT (id) DO UPDATE SET prompt_id = EXCLUDED.prompt_id, binding_type = EXCLUDED.binding_type;

-- ==================== 场景协调器 ====================
INSERT INTO agent_prompt_bindings (id, agent_type, prompt_id, binding_type, priority, is_required) VALUES
('bind_scene_coordinator_orig', 'scene_coordinator', 'originality_guidelines', 'constraint', 95, true),
('bind_scene_coordinator_role', 'scene_coordinator', 'role_scene_coordinator', 'identity', 90, true),
('bind_scene_coordinator_func', 'scene_coordinator', 'function_scene_coordination', 'instruction', 80, true),
('bind_scene_coordinator_output', 'scene_coordinator', 'base_json_output', 'output', 70, true)
ON CONFLICT (id) DO UPDATE SET prompt_id = EXCLUDED.prompt_id, binding_type = EXCLUDED.binding_type;

-- ==================== 过程生成器 ====================
INSERT INTO agent_prompt_bindings (id, agent_type, prompt_id, binding_type, priority, is_required) VALUES
('bind_proc_gen_orig', 'proc_gen', 'originality_guidelines', 'constraint', 95, true),
('bind_proc_gen_role', 'proc_gen', 'role_proc_gen', 'identity', 90, true),
('bind_proc_gen_output', 'proc_gen', 'base_json_output', 'output', 70, true)
ON CONFLICT (id) DO UPDATE SET prompt_id = EXCLUDED.prompt_id, binding_type = EXCLUDED.binding_type;

-- ==================== 注释 ====================
COMMENT ON TABLE agent_prompt_bindings IS 'Agent与Prompt模板的绑定关系表';
COMMENT ON COLUMN agent_prompt_bindings.binding_type IS '绑定类型：identity=身份定义, instruction=工作指令, constraint=约束规则, output=输出格式';
