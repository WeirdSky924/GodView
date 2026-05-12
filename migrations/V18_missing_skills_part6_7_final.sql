-- V18: 补全缺失的 Skills（第六批：读者模拟类 + 第七批：摘要与讨论类）

-- ==================== 第六批：读者模拟类 ====================

-- 读者模拟评分
INSERT INTO skills (id, name, description, skill_type, category, tags, applicable_agent_types, prompt_template, parameters, priority, status, is_system, is_enabled, load_mode)
VALUES (
    'skill_reader_simulation',
    '读者模拟评分',
    '模拟目标读者群体对内容的反应和评分',
    'prompt',
    'evaluation',
    '["读者", "模拟", "评分"]',
    '["evaluator"]',
    '## 任务：读者模拟评分

请模拟目标读者对以下内容的反应：

### 章节内容
{{chapter_content}}

### 目标读者群体
{{target_audience}}

### 作品类型
{{genre}}

### 模拟维度

1. **吸引力模拟**
   - 开篇是否想继续看
   - 是否有"放不下来"的感觉
   - 是否有无聊想跳过的部分

2. **情感反应模拟**
   - 哪些地方会感动
   - 哪些地方会紧张
   - 哪些地方会期待

3. **认知反应模拟**
   - 是否能理解剧情
   - 是否有困惑的地方
   - 信息是否足够

4. **行为预测模拟**
   - 是否会追更
   - 是否会推荐给朋友
   - 是否会打赏/投票

### 读者类型

- **核心读者**：该类型的忠实粉丝
- **普通读者**：有阅读习惯的读者
- **潜在读者**：可能被吸引的新读者

### 输出格式（JSON）
```json
{
  "reader_scores": {
    "core_reader": {"score": 90, "reaction": "反应描述", "would_continue": true},
    "regular_reader": {"score": 85, "reaction": "反应描述", "would_continue": true},
    "potential_reader": {"score": 80, "reaction": "反应描述", "would_continue": false}
  },
  "emotional_peaks": [{"position": "位置", "emotion": "情绪", "intensity": "强度"}],
  "boring_parts": [{"position": "位置", "reason": "原因"}],
  "confusing_parts": [{"position": "位置", "issue": "困惑点"}],
  "overall_prediction": {"would_recommend": true, "would_vote": true, "completion_likelihood": "高"},
  "suggestions": ["改进建议"]
}
```',
    '[{"name": "chapter_content", "type": "string", "description": "章节内容", "required": true}, {"name": "target_audience", "type": "string", "description": "目标读者群体"}, {"name": "genre", "type": "string", "description": "作品类型"}]',
    70,
    'active',
    true,
    true,
    'on_demand'
) ON CONFLICT (id) DO UPDATE SET
    prompt_template = EXCLUDED.prompt_template,
    parameters = EXCLUDED.parameters;

-- ==================== 第七批：摘要与讨论类 ====================

-- 讨论总结
INSERT INTO skills (id, name, description, skill_type, category, tags, applicable_agent_types, prompt_template, parameters, output_spec, priority, status, is_system, is_enabled, load_mode)
VALUES (
    'skill_discussion_summary',
    '讨论总结',
    '总结多角色讨论场景的关键内容和结论',
    'prompt',
    'summary',
    '["讨论", "总结", "会议"]',
    '["summarizer"]',
    '## 任务：讨论总结

请总结以下讨论场景的内容：

### 讨论内容
{{discussion_content}}

### 参与角色
{{participants}}

### 讨论主题
{{discussion_topic}}

### 总结要求

1. **核心观点**
   - 各方的主要立场
   - 关键论点和论据
   - 重要的分歧点

2. **讨论进程**
   - 讨论的发展脉络
   - 观点的变化过程
   - 达成的共识

3. **结论决议**
   - 最终达成的结论
   - 未解决的问题
   - 后续行动计划

4. **角色表现**
   - 各角色的关键发言
   - 态度变化
   - 影响力体现

### 输出格式（JSON）
```json
{
  "summary": "一句话概括",
  "core_viewpoints": [
    {"participant": "角色", "position": "立场", "key_arguments": ["论点"]}
  ],
  "discussion_process": [
    {"stage": "阶段", "content": "内容", "key_moment": "关键时刻"}
  ],
  "conclusions": {
    "agreed": ["达成的共识"],
    "disagreed": ["未解决的分歧"],
    "action_items": ["后续行动"]
  },
  "character_highlights": [{"participant": "角色", "key_quotes": ["关键发言"]}]
}
```',
    '[{"name": "discussion_content", "type": "string", "description": "讨论内容", "required": true}, {"name": "participants", "type": "array", "description": "参与角色"}, {"name": "discussion_topic", "type": "string", "description": "讨论主题"}]',
    '[{"name": "summary", "type": "string"}, {"name": "core_viewpoints", "type": "array"}, {"name": "discussion_process", "type": "array"}, {"name": "conclusions", "type": "object"}, {"name": "character_highlights", "type": "array"}]',
    65,
    'active',
    true,
    true,
    'on_demand'
) ON CONFLICT (id) DO UPDATE SET
    prompt_template = EXCLUDED.prompt_template,
    parameters = EXCLUDED.parameters;

-- 角色表演技能
INSERT INTO skills (id, name, description, skill_type, category, tags, applicable_agent_types, prompt_template, parameters, priority, status, is_system, is_enabled, load_mode)
VALUES (
    'skill_character_performance',
    '角色表演技能',
    '根据角色设定进行角色扮演，生成符合角色的言行',
    'prompt',
    'performance',
    '["表演", "角色", "演绎"]',
    '["character", "scene_coordinator"]',
    '## 任务：角色表演

请以以下角色的身份进行表演：

### 角色信息
- 角色名称：{{character_name}}
- 角色身份：{{character_role}}
- 性格特点：{{personality}}
- 说话风格：{{speech_style}}
- 当前情绪：{{current_emotion}}

### 场景背景
{{scene_context}}

### 当前情境
{{situation}}

### 表演要求

1. **语言风格**
   - 使用符合角色的说话方式
   - 体现角色的身份背景
   - 保持对话的一致性

2. **行为反应**
   - 行为要符合性格
   - 反应要符合当前情绪
   - 考虑角色的动机和目标

3. **互动表现**
   - 与其他角色的互动
   - 对环境的反应
   - 情感表达

4. **内心活动**
   - 适度的心理描写
   - 情感变化过程
   - 决策思考

### 输出格式（JSON）
```json
{
  "dialogue": "角色说的话",
  "action": "角色的动作",
  "expression": "角色的表情",
  "inner_thought": "内心活动（可选）",
  "emotion_shift": "情绪变化（如有）"
}
```',
    '[{"name": "character_name", "type": "string", "description": "角色名称", "required": true}, {"name": "character_role", "type": "string", "description": "角色身份"}, {"name": "personality", "type": "string", "description": "性格特点"}, {"name": "speech_style", "type": "string", "description": "说话风格"}, {"name": "current_emotion", "type": "string", "description": "当前情绪"}, {"name": "scene_context", "type": "string", "description": "场景背景"}, {"name": "situation", "type": "string", "description": "当前情境"}]',
    80,
    'active',
    true,
    true,
    'on_demand'
) ON CONFLICT (id) DO UPDATE SET
    prompt_template = EXCLUDED.prompt_template,
    parameters = EXCLUDED.parameters;

-- ==================== Skill 绑定关系 ====================
-- 将 Skills 绑定到对应的 Agent 类型

-- 创建 skill_assignments 绑定（如果不存在）
INSERT INTO skill_assignments (id, skill_id, agent_type, slot_name, priority, is_enabled)
SELECT 'sa_summarizer_awareness', 'skill_long_novel_awareness', 'summarizer', 'context', 100, true
WHERE NOT EXISTS (SELECT 1 FROM skill_assignments WHERE skill_id = 'skill_long_novel_awareness' AND agent_type = 'summarizer');

INSERT INTO skill_assignments (id, skill_id, agent_type, slot_name, priority, is_enabled)
SELECT 'sa_summarizer_discussion', 'skill_discussion_summary', 'summarizer', 'discussion', 65, true
WHERE NOT EXISTS (SELECT 1 FROM skill_assignments WHERE skill_id = 'skill_discussion_summary' AND agent_type = 'summarizer');

-- 总编剧绑定
INSERT INTO skill_assignments (id, skill_id, agent_type, slot_name, priority, is_enabled)
SELECT 'sa_plotter_awareness', 'skill_long_novel_awareness', 'master_plotter', 'context', 100, true
WHERE NOT EXISTS (SELECT 1 FROM skill_assignments WHERE skill_id = 'skill_long_novel_awareness' AND agent_type = 'master_plotter');

INSERT INTO skill_assignments (id, skill_id, agent_type, slot_name, priority, is_enabled)
SELECT 'sa_plotter_world', 'skill_world_context', 'master_plotter', 'world', 90, true
WHERE NOT EXISTS (SELECT 1 FROM skill_assignments WHERE skill_id = 'skill_world_context' AND agent_type = 'master_plotter');

INSERT INTO skill_assignments (id, skill_id, agent_type, slot_name, priority, is_enabled)
SELECT 'sa_plotter_planning', 'skill_plot_planning', 'master_plotter', 'primary', 80, true
WHERE NOT EXISTS (SELECT 1 FROM skill_assignments WHERE skill_id = 'skill_plot_planning' AND agent_type = 'master_plotter');

INSERT INTO skill_assignments (id, skill_id, agent_type, slot_name, priority, is_enabled)
SELECT 'sa_plotter_advancement', 'skill_plot_advancement', 'master_plotter', 'advancement', 70, true
WHERE NOT EXISTS (SELECT 1 FROM skill_assignments WHERE skill_id = 'skill_plot_advancement' AND agent_type = 'master_plotter');

INSERT INTO skill_assignments (id, skill_id, agent_type, slot_name, priority, is_enabled)
SELECT 'sa_plotter_directions', 'skill_scene_directions', 'master_plotter', 'directions', 75, true
WHERE NOT EXISTS (SELECT 1 FROM skill_assignments WHERE skill_id = 'skill_scene_directions' AND agent_type = 'master_plotter');

INSERT INTO skill_assignments (id, skill_id, agent_type, slot_name, priority, is_enabled)
SELECT 'sa_plotter_power', 'skill_power_level_check', 'master_plotter', 'power_check', 85, true
WHERE NOT EXISTS (SELECT 1 FROM skill_assignments WHERE skill_id = 'skill_power_level_check' AND agent_type = 'master_plotter');

INSERT INTO skill_assignments (id, skill_id, agent_type, slot_name, priority, is_enabled)
SELECT 'sa_plotter_pacing', 'skill_pacing_analysis', 'master_plotter', 'pacing', 75, true
WHERE NOT EXISTS (SELECT 1 FROM skill_assignments WHERE skill_id = 'skill_pacing_analysis' AND agent_type = 'master_plotter');

-- 伏笔管理员绑定
INSERT INTO skill_assignments (id, skill_id, agent_type, slot_name, priority, is_enabled)
SELECT 'sa_hook_awareness', 'skill_long_novel_awareness', 'hook_manager', 'context', 100, true
WHERE NOT EXISTS (SELECT 1 FROM skill_assignments WHERE skill_id = 'skill_long_novel_awareness' AND agent_type = 'hook_manager');

INSERT INTO skill_assignments (id, skill_id, agent_type, slot_name, priority, is_enabled)
SELECT 'sa_hook_planning', 'skill_hook_planning', 'hook_manager', 'primary', 70, true
WHERE NOT EXISTS (SELECT 1 FROM skill_assignments WHERE skill_id = 'skill_hook_planning' AND agent_type = 'hook_manager');

INSERT INTO skill_assignments (id, skill_id, agent_type, slot_name, priority, is_enabled)
SELECT 'sa_hook_tracker', 'skill_foreshadowing_tracker', 'hook_manager', 'tracker', 90, true
WHERE NOT EXISTS (SELECT 1 FROM skill_assignments WHERE skill_id = 'skill_foreshadowing_tracker' AND agent_type = 'hook_manager');

-- 作家绑定
INSERT INTO skill_assignments (id, skill_id, agent_type, slot_name, priority, is_enabled)
SELECT 'sa_writer_awareness', 'skill_long_novel_awareness', 'writer', 'context', 100, true
WHERE NOT EXISTS (SELECT 1 FROM skill_assignments WHERE skill_id = 'skill_long_novel_awareness' AND agent_type = 'writer');

INSERT INTO skill_assignments (id, skill_id, agent_type, slot_name, priority, is_enabled)
SELECT 'sa_writer_world', 'skill_world_context', 'writer', 'world', 90, true
WHERE NOT EXISTS (SELECT 1 FROM skill_assignments WHERE skill_id = 'skill_world_context' AND agent_type = 'writer');

INSERT INTO skill_assignments (id, skill_id, agent_type, slot_name, priority, is_enabled)
SELECT 'sa_writer_chapter', 'skill_chapter_writing', 'writer', 'primary', 80, true
WHERE NOT EXISTS (SELECT 1 FROM skill_assignments WHERE skill_id = 'skill_chapter_writing' AND agent_type = 'writer');

INSERT INTO skill_assignments (id, skill_id, agent_type, slot_name, priority, is_enabled)
SELECT 'sa_writer_scene', 'skill_scene_description', 'writer', 'scene', 60, true
WHERE NOT EXISTS (SELECT 1 FROM skill_assignments WHERE skill_id = 'skill_scene_description' AND agent_type = 'writer');

INSERT INTO skill_assignments (id, skill_id, agent_type, slot_name, priority, is_enabled)
SELECT 'sa_writer_cool', 'skill_cool_point_detection', 'writer', 'cool_check', 85, true
WHERE NOT EXISTS (SELECT 1 FROM skill_assignments WHERE skill_id = 'skill_cool_point_detection' AND agent_type = 'writer');

INSERT INTO skill_assignments (id, skill_id, agent_type, slot_name, priority, is_enabled)
SELECT 'sa_writer_sensitive', 'skill_sensitive_word_detection', 'writer', 'sensitive', 95, true
WHERE NOT EXISTS (SELECT 1 FROM skill_assignments WHERE skill_id = 'skill_sensitive_word_detection' AND agent_type = 'writer');

INSERT INTO skill_assignments (id, skill_id, agent_type, slot_name, priority, is_enabled)
SELECT 'sa_writer_golden', 'skill_golden_line_generator', 'writer', 'golden_lines', 70, true
WHERE NOT EXISTS (SELECT 1 FROM skill_assignments WHERE skill_id = 'skill_golden_line_generator' AND agent_type = 'writer');

INSERT INTO skill_assignments (id, skill_id, agent_type, slot_name, priority, is_enabled)
SELECT 'sa_writer_hook_gen', 'skill_chapter_hook_generator', 'writer', 'hook', 75, true
WHERE NOT EXISTS (SELECT 1 FROM skill_assignments WHERE skill_id = 'skill_chapter_hook_generator' AND agent_type = 'writer');

INSERT INTO skill_assignments (id, skill_id, agent_type, slot_name, priority, is_enabled)
SELECT 'sa_writer_title', 'skill_chapter_title_optimizer', 'writer', 'title', 65, true
WHERE NOT EXISTS (SELECT 1 FROM skill_assignments WHERE skill_id = 'skill_chapter_title_optimizer' AND agent_type = 'writer');

-- 评估员绑定
INSERT INTO skill_assignments (id, skill_id, agent_type, slot_name, priority, is_enabled)
SELECT 'sa_eval_awareness', 'skill_long_novel_awareness', 'evaluator', 'context', 100, true
WHERE NOT EXISTS (SELECT 1 FROM skill_assignments WHERE skill_id = 'skill_long_novel_awareness' AND agent_type = 'evaluator');

INSERT INTO skill_assignments (id, skill_id, agent_type, slot_name, priority, is_enabled)
SELECT 'sa_eval_world', 'skill_world_context', 'evaluator', 'world', 90, true
WHERE NOT EXISTS (SELECT 1 FROM skill_assignments WHERE skill_id = 'skill_world_context' AND agent_type = 'evaluator');

INSERT INTO skill_assignments (id, skill_id, agent_type, slot_name, priority, is_enabled)
SELECT 'sa_eval_chapter', 'skill_chapter_evaluation', 'evaluator', 'primary', 80, true
WHERE NOT EXISTS (SELECT 1 FROM skill_assignments WHERE skill_id = 'skill_chapter_evaluation' AND agent_type = 'evaluator');

INSERT INTO skill_assignments (id, skill_id, agent_type, slot_name, priority, is_enabled)
SELECT 'sa_eval_reader', 'skill_reader_simulation', 'evaluator', 'simulation', 70, true
WHERE NOT EXISTS (SELECT 1 FROM skill_assignments WHERE skill_id = 'skill_reader_simulation' AND agent_type = 'evaluator');

INSERT INTO skill_assignments (id, skill_id, agent_type, slot_name, priority, is_enabled)
SELECT 'sa_eval_ooc', 'skill_ooc_check', 'evaluator', 'ooc', 75, true
WHERE NOT EXISTS (SELECT 1 FROM skill_assignments WHERE skill_id = 'skill_ooc_check' AND agent_type = 'evaluator');

INSERT INTO skill_assignments (id, skill_id, agent_type, slot_name, priority, is_enabled)
SELECT 'sa_eval_cool', 'skill_cool_point_detection', 'evaluator', 'cool_detection', 90, true
WHERE NOT EXISTS (SELECT 1 FROM skill_assignments WHERE skill_id = 'skill_cool_point_detection' AND agent_type = 'evaluator');

INSERT INTO skill_assignments (id, skill_id, agent_type, slot_name, priority, is_enabled)
SELECT 'sa_eval_plothole', 'skill_plot_hole_detection', 'evaluator', 'plot_hole', 95, true
WHERE NOT EXISTS (SELECT 1 FROM skill_assignments WHERE skill_id = 'skill_plot_hole_detection' AND agent_type = 'evaluator');

INSERT INTO skill_assignments (id, skill_id, agent_type, slot_name, priority, is_enabled)
SELECT 'sa_eval_memory', 'skill_character_memory_check', 'evaluator', 'memory_check', 90, true
WHERE NOT EXISTS (SELECT 1 FROM skill_assignments WHERE skill_id = 'skill_character_memory_check' AND agent_type = 'evaluator');

INSERT INTO skill_assignments (id, skill_id, agent_type, slot_name, priority, is_enabled)
SELECT 'sa_eval_sensitive', 'skill_sensitive_word_detection', 'evaluator', 'sensitive', 95, true
WHERE NOT EXISTS (SELECT 1 FROM skill_assignments WHERE skill_id = 'skill_sensitive_word_detection' AND agent_type = 'evaluator');

INSERT INTO skill_assignments (id, skill_id, agent_type, slot_name, priority, is_enabled)
SELECT 'sa_eval_power', 'skill_power_level_check', 'evaluator', 'power_check', 90, true
WHERE NOT EXISTS (SELECT 1 FROM skill_assignments WHERE skill_id = 'skill_power_level_check' AND agent_type = 'evaluator');

INSERT INTO skill_assignments (id, skill_id, agent_type, slot_name, priority, is_enabled)
SELECT 'sa_eval_setting', 'skill_setting_conflict_detection', 'evaluator', 'setting_conflict', 85, true
WHERE NOT EXISTS (SELECT 1 FROM skill_assignments WHERE skill_id = 'skill_setting_conflict_detection' AND agent_type = 'evaluator');

INSERT INTO skill_assignments (id, skill_id, agent_type, slot_name, priority, is_enabled)
SELECT 'sa_eval_pacing', 'skill_pacing_analysis', 'evaluator', 'pacing', 80, true
WHERE NOT EXISTS (SELECT 1 FROM skill_assignments WHERE skill_id = 'skill_pacing_analysis' AND agent_type = 'evaluator');

INSERT INTO skill_assignments (id, skill_id, agent_type, slot_name, priority, is_enabled)
SELECT 'sa_eval_dialogue', 'skill_dialogue_style_check', 'evaluator', 'dialogue_check', 80, true
WHERE NOT EXISTS (SELECT 1 FROM skill_assignments WHERE skill_id = 'skill_dialogue_style_check' AND agent_type = 'evaluator');

INSERT INTO skill_assignments (id, skill_id, agent_type, slot_name, priority, is_enabled)
SELECT 'sa_eval_golden3', 'skill_golden_three_chapters', 'evaluator', 'golden_three', 85, true
WHERE NOT EXISTS (SELECT 1 FROM skill_assignments WHERE skill_id = 'skill_golden_three_chapters' AND agent_type = 'evaluator');

INSERT INTO skill_assignments (id, skill_id, agent_type, slot_name, priority, is_enabled)
SELECT 'sa_eval_timeline', 'skill_timeline_verification', 'evaluator', 'timeline', 70, true
WHERE NOT EXISTS (SELECT 1 FROM skill_assignments WHERE skill_id = 'skill_timeline_verification' AND agent_type = 'evaluator');

-- 设定管理员绑定
INSERT INTO skill_assignments (id, skill_id, agent_type, slot_name, priority, is_enabled)
SELECT 'sa_setting_awareness', 'skill_long_novel_awareness', 'setting', 'context', 100, true
WHERE NOT EXISTS (SELECT 1 FROM skill_assignments WHERE skill_id = 'skill_long_novel_awareness' AND agent_type = 'setting');

INSERT INTO skill_assignments (id, skill_id, agent_type, slot_name, priority, is_enabled)
SELECT 'sa_setting_world', 'skill_world_context', 'setting', 'world', 90, true
WHERE NOT EXISTS (SELECT 1 FROM skill_assignments WHERE skill_id = 'skill_world_context' AND agent_type = 'setting');

-- 角色Agent绑定
INSERT INTO skill_assignments (id, skill_id, agent_type, slot_name, priority, is_enabled)
SELECT 'sa_character_awareness', 'skill_long_novel_awareness', 'character', 'context', 100, true
WHERE NOT EXISTS (SELECT 1 FROM skill_assignments WHERE skill_id = 'skill_long_novel_awareness' AND agent_type = 'character');

INSERT INTO skill_assignments (id, skill_id, agent_type, slot_name, priority, is_enabled)
SELECT 'sa_character_world', 'skill_world_context', 'character', 'world', 90, true
WHERE NOT EXISTS (SELECT 1 FROM skill_assignments WHERE skill_id = 'skill_world_context' AND agent_type = 'character');

INSERT INTO skill_assignments (id, skill_id, agent_type, slot_name, priority, is_enabled)
SELECT 'sa_character_perform', 'skill_character_performance', 'character', 'primary', 80, true
WHERE NOT EXISTS (SELECT 1 FROM skill_assignments WHERE skill_id = 'skill_character_performance' AND agent_type = 'character');

INSERT INTO skill_assignments (id, skill_id, agent_type, slot_name, priority, is_enabled)
SELECT 'sa_character_ooc', 'skill_ooc_check', 'character', 'ooc', 70, true
WHERE NOT EXISTS (SELECT 1 FROM skill_assignments WHERE skill_id = 'skill_ooc_check' AND agent_type = 'character');

INSERT INTO skill_assignments (id, skill_id, agent_type, slot_name, priority, is_enabled)
SELECT 'sa_character_dialogue', 'skill_dialogue_style_check', 'character', 'dialogue', 85, true
WHERE NOT EXISTS (SELECT 1 FROM skill_assignments WHERE skill_id = 'skill_dialogue_style_check' AND agent_type = 'character');

INSERT INTO skill_assignments (id, skill_id, agent_type, slot_name, priority, is_enabled)
SELECT 'sa_character_memory', 'skill_character_memory_check', 'character', 'memory', 80, true
WHERE NOT EXISTS (SELECT 1 FROM skill_assignments WHERE skill_id = 'skill_character_memory_check' AND agent_type = 'character');

-- 事件生成器绑定
INSERT INTO skill_assignments (id, skill_id, agent_type, slot_name, priority, is_enabled)
SELECT 'sa_event_awareness', 'skill_long_novel_awareness', 'event_generator', 'context', 100, true
WHERE NOT EXISTS (SELECT 1 FROM skill_assignments WHERE skill_id = 'skill_long_novel_awareness' AND agent_type = 'event_generator');

INSERT INTO skill_assignments (id, skill_id, agent_type, slot_name, priority, is_enabled)
SELECT 'sa_event_world', 'skill_world_context', 'event_generator', 'world', 90, true
WHERE NOT EXISTS (SELECT 1 FROM skill_assignments WHERE skill_id = 'skill_world_context' AND agent_type = 'event_generator');

-- 世界地图管理员绑定
INSERT INTO skill_assignments (id, skill_id, agent_type, slot_name, priority, is_enabled)
SELECT 'sa_worldmap_awareness', 'skill_long_novel_awareness', 'world_map_manager', 'context', 100, true
WHERE NOT EXISTS (SELECT 1 FROM skill_assignments WHERE skill_id = 'skill_long_novel_awareness' AND agent_type = 'world_map_manager');

INSERT INTO skill_assignments (id, skill_id, agent_type, slot_name, priority, is_enabled)
SELECT 'sa_worldmap_world', 'skill_world_context', 'world_map_manager', 'world', 90, true
WHERE NOT EXISTS (SELECT 1 FROM skill_assignments WHERE skill_id = 'skill_world_context' AND agent_type = 'world_map_manager');

-- 副本生成器绑定
INSERT INTO skill_assignments (id, skill_id, agent_type, slot_name, priority, is_enabled)
SELECT 'sa_dungeon_awareness', 'skill_long_novel_awareness', 'dungeon_generator', 'context', 100, true
WHERE NOT EXISTS (SELECT 1 FROM skill_assignments WHERE skill_id = 'skill_long_novel_awareness' AND agent_type = 'dungeon_generator');

INSERT INTO skill_assignments (id, skill_id, agent_type, slot_name, priority, is_enabled)
SELECT 'sa_dungeon_world', 'skill_world_context', 'dungeon_generator', 'world', 90, true
WHERE NOT EXISTS (SELECT 1 FROM skill_assignments WHERE skill_id = 'skill_world_context' AND agent_type = 'dungeon_generator');

-- 章节大纲规划绑定
INSERT INTO skill_assignments (id, skill_id, agent_type, slot_name, priority, is_enabled)
SELECT 'sa_outline_awareness', 'skill_long_novel_awareness', 'plot_outline', 'context', 100, true
WHERE NOT EXISTS (SELECT 1 FROM skill_assignments WHERE skill_id = 'skill_long_novel_awareness' AND agent_type = 'plot_outline');

INSERT INTO skill_assignments (id, skill_id, agent_type, slot_name, priority, is_enabled)
SELECT 'sa_outline_world', 'skill_world_context', 'plot_outline', 'world', 90, true
WHERE NOT EXISTS (SELECT 1 FROM skill_assignments WHERE skill_id = 'skill_world_context' AND agent_type = 'plot_outline');

INSERT INTO skill_assignments (id, skill_id, agent_type, slot_name, priority, is_enabled)
SELECT 'sa_outline_gen', 'skill_chapter_outline_generation', 'plot_outline', 'outline_gen', 90, true
WHERE NOT EXISTS (SELECT 1 FROM skill_assignments WHERE skill_id = 'skill_chapter_outline_generation' AND agent_type = 'plot_outline');

INSERT INTO skill_assignments (id, skill_id, agent_type, slot_name, priority, is_enabled)
SELECT 'sa_outline_val', 'skill_chapter_outline_validation', 'plot_outline', 'outline_val', 75, true
WHERE NOT EXISTS (SELECT 1 FROM skill_assignments WHERE skill_id = 'skill_chapter_outline_validation' AND agent_type = 'plot_outline');

INSERT INTO skill_assignments (id, skill_id, agent_type, slot_name, priority, is_enabled)
SELECT 'sa_outline_opening', 'skill_opening_design', 'plot_outline', 'opening', 85, true
WHERE NOT EXISTS (SELECT 1 FROM skill_assignments WHERE skill_id = 'skill_opening_design' AND agent_type = 'plot_outline');

INSERT INTO skill_assignments (id, skill_id, agent_type, slot_name, priority, is_enabled)
SELECT 'sa_outline_villain', 'skill_villain_management', 'plot_outline', 'villain', 85, true
WHERE NOT EXISTS (SELECT 1 FROM skill_assignments WHERE skill_id = 'skill_villain_management' AND agent_type = 'plot_outline');

INSERT INTO skill_assignments (id, skill_id, agent_type, slot_name, priority, is_enabled)
SELECT 'sa_outline_volume', 'skill_volume_planning', 'plot_outline', 'volume', 80, true
WHERE NOT EXISTS (SELECT 1 FROM skill_assignments WHERE skill_id = 'skill_volume_planning' AND agent_type = 'plot_outline');

-- 场景协调器绑定
INSERT INTO skill_assignments (id, skill_id, agent_type, slot_name, priority, is_enabled)
SELECT 'sa_scene_awareness', 'skill_long_novel_awareness', 'scene_coordinator', 'context', 100, true
WHERE NOT EXISTS (SELECT 1 FROM skill_assignments WHERE skill_id = 'skill_long_novel_awareness' AND agent_type = 'scene_coordinator');

INSERT INTO skill_assignments (id, skill_id, agent_type, slot_name, priority, is_enabled)
SELECT 'sa_scene_world', 'skill_world_context', 'scene_coordinator', 'world', 90, true
WHERE NOT EXISTS (SELECT 1 FROM skill_assignments WHERE skill_id = 'skill_world_context' AND agent_type = 'scene_coordinator');

INSERT INTO skill_assignments (id, skill_id, agent_type, slot_name, priority, is_enabled)
SELECT 'sa_scene_directions', 'skill_scene_directions', 'scene_coordinator', 'directions', 85, true
WHERE NOT EXISTS (SELECT 1 FROM skill_assignments WHERE skill_id = 'skill_scene_directions' AND agent_type = 'scene_coordinator');

INSERT INTO skill_assignments (id, skill_id, agent_type, slot_name, priority, is_enabled)
SELECT 'sa_scene_perform', 'skill_character_performance', 'scene_coordinator', 'performance', 75, true
WHERE NOT EXISTS (SELECT 1 FROM skill_assignments WHERE skill_id = 'skill_character_performance' AND agent_type = 'scene_coordinator');

-- 过程生成器绑定
INSERT INTO skill_assignments (id, skill_id, agent_type, slot_name, priority, is_enabled)
SELECT 'sa_procgen_awareness', 'skill_long_novel_awareness', 'proc_gen', 'context', 100, true
WHERE NOT EXISTS (SELECT 1 FROM skill_assignments WHERE skill_id = 'skill_long_novel_awareness' AND agent_type = 'proc_gen');
