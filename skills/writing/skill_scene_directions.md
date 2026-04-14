---
id: skill_scene_directions
name: 场景表演指导
description: 为多角色场景提供表演指导，协调角色出场、行动和对话
category: direction
skill_type: prompt
tags:
  - 表演
  - 指导
  - 协调
use_cases:
  - 角色出场安排
  - 对话分配
  - 情绪曲线设计
applicable_agent_types:
  - master_plotter
  - scene_coordinator
load_mode: on_demand
priority: 75
is_system: true
is_enabled: true
parameters:
  - name: scene_name
    type: string
    description: 场景名称
  - name: scene_type
    type: string
    description: 场景类型
  - name: characters
    type: array
    description: 参与角色
  - name: scene_goal
    type: string
    description: 场景目标
---

# 场景表演指导技能

## 任务：场景表演指导

请为以下场景提供表演指导：

### 场景信息

- 场景名称：{{scene_name}}
- 场景类型：{{scene_type}}
- 参与角色：{{characters}}

### 场景目标

{{scene_goal}}

### 表演指导要点

#### 1. 角色出场安排

- 出场顺序和方式
- 各角色的关注点
- 舞台位置和移动

#### 2. 对话分配

- 谁说什么、为什么说
- 对话的节奏控制
- 潜台词和信息层次

#### 3. 动作设计

- 关键动作和反应
- 肢体语言表达
- 眼神和微表情

#### 4. 情绪曲线

- 各角色的情绪变化
- 场景整体的节奏
- 高潮点的设置

#### 5. 互动设计

- 角色间的化学反应
- 冲突和和解
- 权力动态变化

### 输出格式（JSON）

```json
{
  "stage_directions": "舞台指导说明",
  "character_beats": [
    {"character": "角色名", "actions": "动作", "emotion": "情绪", "objective": "目标"}
  ],
  "dialogue_hints": {"角色名": "对话风格提示"},
  "climax_point": "场景高潮点",
  "transition": "转场建议"
}
```
