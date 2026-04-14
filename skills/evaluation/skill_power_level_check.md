---
id: skill_power_level_check
name: 战力体系校验
description: 校验战斗描写是否符合战力设定，避免战力崩坏
category: evaluation
skill_type: prompt
tags:
  - 战力
  - 体系
  - 战斗
use_cases:
  - 校验战力合理性
  - 检测战力崩坏
  - 验证战斗逻辑
applicable_agent_types:
  - master_plotter
  - evaluator
load_mode: on_demand
priority: 90
is_system: true
is_enabled: true
parameters:
  - name: combat_content
    type: string
    description: 战斗内容
    required: true
  - name: power_system
    type: object
    description: 战力设定
  - name: combatant_levels
    type: object
    description: 参战角色战力
---

# 战力体系校验技能

## 任务：战力体系校验

请校验以下战斗内容是否符合战力设定：

### 战斗内容

{{combat_content}}

### 战力设定

{{power_system}}

### 参战角色战力

{{combatant_levels}}

### 校验维度

#### 1. 能力使用

- 技能是否在能力范围内
- 代价/限制是否体现
- 使用方式是否符合规则

#### 2. 战力对比

- 战斗结果是否合理
- 实力差距是否正确体现
- 是否有不合逻辑的"越级"

#### 3. 成长合理性

- 实力提升是否有铺垫
- 战斗表现是否稳定
- 是否有突然变强/变弱

### 输出格式（JSON）

```json
{
  "power_issues": [
    {"character": "角色", "type": "问题类型", "description": "描述", "severity": "严重程度"}
  ],
  "combat_valid": true,
  "power_balance": {"attacker": "高", "defender": "中", "result": "合理"},
  "suggestions": ["建议"]
}
```
