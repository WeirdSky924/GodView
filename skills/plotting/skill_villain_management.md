---
id: skill_villain_management
name: 反派管理
description: 管理反派角色的出场、发展和结局规划
category: plotting
skill_type: prompt
tags:
  - 反派
  - 角色
  - 规划
use_cases:
  - 设计反派角色
  - 规划反派出场
  - 设计反派结局
applicable_agent_types:
  - plot_outline
load_mode: on_demand
priority: 85
is_system: true
is_enabled: true
parameters:
  - name: villain_info
    type: object
    description: 反派信息
  - name: story_phase
    type: string
    description: 当前故事阶段
---

# 反派管理技能

## 任务：反派管理

请管理以下反派角色：

### 反派信息

{{villain_info}}

### 当前故事阶段

{{story_phase}}

### 反派管理原则

#### 1. 反派设计

- 有合理的动机和行为逻辑
- 不是纯粹的恶，有立体感
- 能力要与主角形成张力
- 要推动剧情发展

#### 2. 出场规划

- 出场时机和方式
- 与主角的冲突节点
- 威胁等级变化曲线

#### 3. 发展轨迹

- 反派的目标和行动
- 与主角的博弈过程
- 可能的转变机会

#### 4. 结局规划

- 合理的结局安排
- 对故事的影响
- 读者的情感满足

### 反派类型

#### 1. 宿敌型

与主角长期对立

#### 2. 阶段型

某个阶段的对手

#### 3. 隐藏型

幕后黑手

#### 4. 转化型

可能转向正方

### 输出格式（JSON）

```json
{
  "villain_profile": {"name": "名称", "type": "类型", "threat_level": "威胁等级"},
  "appearance_plan": [{"chapter": 10, "event": "出场事件", "impact": "影响"}],
  "conflict_timeline": [{"phase": "阶段", "villain_action": "行动", "protagonist_response": "应对"}],
  "development_arc": "发展轨迹",
  "ending_plan": "结局规划"
}
```
