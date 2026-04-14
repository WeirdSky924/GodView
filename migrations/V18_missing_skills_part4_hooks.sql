-- V18: 补全缺失的 Skills（第四批：伏笔管理类）
-- 这些是伏笔管理员 Agent 的核心能力

-- ==================== 伏笔管理类 Skills ====================

-- 伏笔规划
INSERT INTO skills (id, name, description, skill_type, category, tags, applicable_agent_types, prompt_template, parameters, output_spec, priority, status, is_system, is_enabled, load_mode)
VALUES (
    'skill_hook_planning',
    '伏笔规划',
    '规划故事伏笔系统的埋设和回收计划',
    'prompt',
    'hook',
    '["伏笔", "规划", "悬念"]',
    '["hook_manager"]',
    '## 任务：伏笔规划

请规划故事的伏笔系统：

### 故事背景
{{story_background}}

### 当前章节
{{current_chapter}}

### 已有伏笔
{{existing_hooks}}

### 伏笔规划原则

1. **伏笔设计**
   - 伏笔要有明确的目的和意义
   - 埋设方式要自然，不显刻意
   - 要有足够的信息量，让读者能记住

2. **类型规划**
   - 情节伏笔：暗示后续情节发展
   - 人物伏笔：预示人物命运或秘密
   - 设定伏笔：埋藏世界观秘密
   - 情感伏笔：铺垫人物情感变化

3. **时间规划**
   - 短期伏笔：5章内回收
   - 中期伏笔：10-30章回收
   - 长期伏笔：贯穿整个故事

4. **密度控制**
   - 每章建议1-2个伏笔动作
   - 保持适量，避免读者遗忘或混乱
   - 重要伏笔要多次暗示

### 输出格式（JSON）
```json
{
  "new_hooks": [
    {
      "id": "hook_xxx",
      "type": "伏笔类型",
      "content": "伏笔内容",
      "plant_chapter": 10,
      "plant_method": "埋设方式",
      "hint_schedule": [12, 15, 18],
      "payoff_chapter": 20,
      "payoff_method": "回收方式"
    }
  ],
  "hint_plan": [{"hook_id": "xxx", "chapter": 12, "method": "暗示方式"}],
  "payoff_plan": [{"hook_id": "xxx", "chapter": 20, "satisfaction": "读者满足感设计"}]
}
```',
    '[{"name": "story_background", "type": "string", "description": "故事背景"}, {"name": "current_chapter", "type": "number", "description": "当前章节"}, {"name": "existing_hooks", "type": "array", "description": "已有伏笔"}]',
    '[{"name": "new_hooks", "type": "array"}, {"name": "hint_plan", "type": "array"}, {"name": "payoff_plan", "type": "array"}]',
    70,
    'active',
    true,
    true,
    'on_demand'
) ON CONFLICT (id) DO UPDATE SET
    prompt_template = EXCLUDED.prompt_template,
    parameters = EXCLUDED.parameters;

-- 伏笔追踪与提醒
INSERT INTO skills (id, name, description, skill_type, category, tags, applicable_agent_types, prompt_template, parameters, output_spec, priority, status, is_system, is_enabled, load_mode)
VALUES (
    'skill_foreshadowing_tracker',
    '伏笔追踪与提醒',
    '追踪所有伏笔状态，提醒需要暗示或回收的伏笔',
    'prompt',
    'hook',
    '["伏笔", "追踪", "提醒"]',
    '["hook_manager"]',
    '## 任务：伏笔追踪与提醒

请追踪当前所有伏笔状态：

### 当前章节
{{current_chapter}}

### 伏笔列表
{{hooks_list}}

### 最近章节内容
{{recent_chapters}}

### 追踪要求

1. **状态追踪**
   - dormant: 等待暗示阶段
   - hinted: 已开始暗示
   - ready: 可以回收
   - resolved: 已回收
   - abandoned: 放弃

2. **提醒机制**
   - 即将到期的伏笔（计划回收章节临近）
   - 需要暗示的伏笔（埋设后未暗示超过N章）
   - 可能遗忘的伏笔（长时间未处理）

3. **效果评估**
   - 暗示是否足够
   - 读者是否能记住
   - 回收时机是否合适

### 输出格式（JSON）
```json
{
  "hooks_status": [
    {
      "id": "hook_xxx",
      "status": "hinted",
      "plant_chapter": 5,
      "hint_count": 2,
      "last_hint_chapter": 10,
      "planned_payoff": 20,
      "chapters_until_payoff": 10,
      "needs_hint": false,
      "urgency": "normal"
    }
  ],
  "reminders": [
    {"type": "hint_reminder", "hook_id": "xxx", "message": "需要暗示"},
    {"type": "payoff_reminder", "hook_id": "xxx", "message": "接近回收时机"}
  ],
  "suggestions": ["建议暗示xxx", "建议回收xxx"]
}
```',
    '[{"name": "current_chapter", "type": "number", "description": "当前章节", "required": true}, {"name": "hooks_list", "type": "array", "description": "伏笔列表"}, {"name": "recent_chapters", "type": "string", "description": "最近章节内容"}]',
    '[{"name": "hooks_status", "type": "array"}, {"name": "reminders", "type": "array"}, {"name": "suggestions", "type": "array"}]',
    90,
    'active',
    true,
    true,
    'on_demand'
) ON CONFLICT (id) DO UPDATE SET
    prompt_template = EXCLUDED.prompt_template,
    parameters = EXCLUDED.parameters;
