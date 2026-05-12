-- V31: normalize persisted workflow node labels to canonical catalog labels
--
-- This migration only updates legacy/default labels in workflow_definitions.nodes.
-- It does NOT change node ids, node_type, agent_type, edges, config, or user-defined custom labels.

WITH label_map (node_type, agent_type, old_label, new_label) AS (
    VALUES
        ('start', NULL, 'Start', '开始'),
        ('start', NULL, 'start', '开始'),
        ('end', NULL, 'End', '结束'),
        ('end', NULL, 'end', '结束'),
        ('input', NULL, 'User Input', '用户输入'),
        ('group_discussion', NULL, 'Group Discussion', '集体讨论'),
        ('scene_performance', NULL, 'Scene Performance', '场景演绎'),
        ('condition', NULL, '条件判断', '条件分支'),
        ('condition', NULL, '章节结束?', '条件分支'),
        ('condition', NULL, '质量达标?', '条件分支'),
        ('condition', NULL, '需要补充输入?', '条件分支'),
        ('condition', NULL, 'Condition', '条件分支'),
        ('parallel', NULL, '并行准备', '并行执行'),
        ('parallel', NULL, 'Parallel', '并行执行'),
        ('agent', 'setting', '设定', '设定 Agent'),
        ('agent', 'setting', '设定Agent', '设定 Agent'),
        ('agent', 'setting', 'Setting', '设定 Agent'),
        ('agent', 'setting', 'Setting Agent', '设定 Agent'),
        ('agent', 'writer', '作家', '作家 Agent'),
        ('agent', 'writer', 'Writer', '作家 Agent'),
        ('agent', 'writer', 'Writer Agent', '作家 Agent'),
        ('agent', 'master_plotter', '总编剧', '总编剧 Agent'),
        ('agent', 'master_plotter', 'Master Plotter', '总编剧 Agent'),
        ('agent', 'master_plotter', 'Master Plotter Agent', '总编剧 Agent'),
        ('agent', 'plotter', '编剧', '编剧 Agent'),
        ('agent', 'plotter', 'Plotter', '编剧 Agent'),
        ('agent', 'plotter', 'Plotter Agent', '编剧 Agent'),
        ('agent', 'summarizer', '摘要', '摘要 Agent'),
        ('agent', 'summarizer', '摘要提取', '摘要 Agent'),
        ('agent', 'summarizer', 'Summarizer', '摘要 Agent'),
        ('agent', 'summarizer', 'Summarize Dialogue', '摘要 Agent'),
        ('agent', 'evaluator', '评估', '评估 Agent'),
        ('agent', 'evaluator', 'Evaluator', '评估 Agent'),
        ('agent', 'evaluator', 'Evaluator Agent', '评估 Agent'),
        ('agent', 'hook_manager', '伏笔管理', '伏笔 Agent'),
        ('agent', 'hook_manager', 'Hook Manager', '伏笔 Agent'),
        ('agent', 'hook_manager', 'Hook Manager Agent', '伏笔 Agent'),
        ('agent', 'event_generator', '事件生成', '事件 Agent'),
        ('agent', 'event_generator', 'Event Generator', '事件 Agent'),
        ('agent', 'event_generator', 'Event Generator Agent', '事件 Agent'),
        ('agent', 'world_map_manager', '地图管理', '地图 Agent'),
        ('agent', 'world_map_manager', 'World Map', '地图 Agent'),
        ('agent', 'world_map_manager', 'Map Agent', '地图 Agent'),
        ('agent', 'world_map_manager', 'World Map Agent', '地图 Agent'),
        ('agent', 'proc_gen', '过程生成', '过程生成 Agent'),
        ('agent', 'proc_gen', 'ProcGen', '过程生成 Agent'),
        ('agent', 'proc_gen', 'Proc Gen', '过程生成 Agent'),
        ('agent', 'proc_gen', 'ProcGen Agent', '过程生成 Agent'),
        ('agent', 'dungeon_generator', '副本生成', '副本生成 Agent'),
        ('agent', 'dungeon_generator', 'Dungeon Generator', '副本生成 Agent'),
        ('agent', 'dungeon_generator', 'Dungeon Generator Agent', '副本生成 Agent'),
        ('agent', 'dungeon_generator', 'Dungeon Agent', '副本生成 Agent'),
        ('agent', 'plot_outline', '章节大纲', '章节大纲 Agent'),
        ('agent', 'plot_outline', '大纲 Agent', '章节大纲 Agent'),
        ('agent', 'plot_outline', 'Plot Outline', '章节大纲 Agent'),
        ('agent', 'plot_outline', 'Plot Outline Agent', '章节大纲 Agent'),
        ('agent', 'scene_coordinator', '场景协调', '场景协调 Agent'),
        ('agent', 'scene_coordinator', 'Scene Coordinator', '场景协调 Agent'),
        ('agent', 'scene_coordinator', 'Scene Coordinator Agent', '场景协调 Agent'),
        ('agent', 'character', '角色', '角色 Agent'),
        ('agent', 'character', '角色对话', '角色 Agent'),
        ('agent', 'character', '角色演绎', '角色 Agent'),
        ('agent', 'character', 'Character', '角色 Agent'),
        ('agent', 'character', 'Character Agent', '角色 Agent')
), normalized_nodes AS (
    SELECT
        wd.id,
        jsonb_agg(
            CASE
                WHEN lm.new_label IS NOT NULL THEN jsonb_set(node_entry.node, '{label}', to_jsonb(lm.new_label), true)
                ELSE node_entry.node
            END
            ORDER BY node_entry.ord
        ) AS nodes
    FROM workflow_definitions AS wd
    CROSS JOIN LATERAL jsonb_array_elements(COALESCE(wd.nodes, '[]'::jsonb)) WITH ORDINALITY AS node_entry(node, ord)
    LEFT JOIN label_map AS lm
        ON COALESCE(node_entry.node->>'node_type', '') = lm.node_type
       AND COALESCE(node_entry.node->>'label', '') = lm.old_label
       AND (
            (lm.agent_type IS NULL AND COALESCE(node_entry.node->>'agent_type', '') = '')
            OR COALESCE(node_entry.node->>'agent_type', '') = COALESCE(lm.agent_type, '')
       )
    GROUP BY wd.id
)
UPDATE workflow_definitions AS wd
SET nodes = normalized_nodes.nodes
FROM normalized_nodes
WHERE wd.id = normalized_nodes.id
  AND wd.nodes IS DISTINCT FROM normalized_nodes.nodes;
