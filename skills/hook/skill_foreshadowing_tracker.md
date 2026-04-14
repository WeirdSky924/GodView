---
id: skill_foreshadowing_tracker
name: 伏笔追踪与提醒
description: 追踪所有伏笔状态，提醒需要暗示或回收的伏笔
category: hook
skill_type: prompt
tags:
  - 伏笔
  - 追踪
  - 提醒
use_cases:
  - 追踪伏笔状态
  - 提醒回收时机
  - 避免伏笔遗忘
applicable_agent_types:
  - hook_manager
load_mode: on_demand
priority: 90
is_system: true
is_enabled: true
parameters:
  - name: current_chapter
    type: number
    description: 当前章节
    required: true
  - name: hooks_list
    type: array
    description: 伏笔列表
  - name: recent_chapters
    type: string
    description: 最近章节内容
output_spec:
  - name: hooks_status
    type: array
  - name: reminders
    type: array
  - name: suggestions
    type: array
---

# 伏笔追踪与提醒技能

## 任务：伏笔追踪与提醒

请追踪当前所有伏笔状态：

### 当前章节

{{current_chapter}}

### 伏笔列表

{{hooks_list}}

### 最近章节内容

{{recent_chapters}}

### 追踪要求

#### 1. 状态追踪

- **dormant**：等待暗示阶段
- **hinted**：已开始暗示
- **ready**：可以回收
- **resolved**：已回收
- **abandoned**：放弃

#### 2. 提醒机制

- 即将到期的伏笔（计划回收章节临近）
- 需要暗示的伏笔（埋设后未暗示超过N章）
- 可能遗忘的伏笔（长时间未处理）

#### 3. 效果评估

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
```
