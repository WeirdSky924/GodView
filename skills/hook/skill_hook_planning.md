---
id: skill_hook_planning
name: 伏笔规划
description: 规划故事伏笔系统的埋设和回收计划
category: hook
skill_type: prompt
tags:
  - 伏笔
  - 规划
  - 悬念
use_cases:
  - 设计伏笔布局
  - 规划埋设时机
  - 安排回收计划
applicable_agent_types:
  - hook_manager
load_mode: on_demand
priority: 70
is_system: true
is_enabled: true
parameters:
  - name: story_background
    type: string
    description: 故事背景
  - name: current_chapter
    type: number
    description: 当前章节
  - name: existing_hooks
    type: array
    description: 已有伏笔
output_spec:
  - name: new_hooks
    type: array
  - name: hint_plan
    type: array
  - name: payoff_plan
    type: array
---

# 伏笔规划技能

## 任务：伏笔规划

请规划故事的伏笔系统：

### 故事背景

{{story_background}}

### 当前章节

{{current_chapter}}

### 已有伏笔

{{existing_hooks}}

### 伏笔规划原则

#### 1. 伏笔设计

- 伏笔要有明确的目的和意义
- 埋设方式要自然，不显刻意
- 要有足够的信息量，让读者能记住

#### 2. 类型规划

- **情节伏笔**：暗示后续情节发展
- **人物伏笔**：预示人物命运或秘密
- **设定伏笔**：埋藏世界观秘密
- **情感伏笔**：铺垫人物情感变化

#### 3. 时间规划

- **短期伏笔**：5章内回收
- **中期伏笔**：10-30章回收
- **长期伏笔**：贯穿整个故事

#### 4. 密度控制

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
```
