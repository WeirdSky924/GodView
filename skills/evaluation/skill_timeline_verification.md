---
id: skill_timeline_verification
name: 时间线校验
description: 校验时间线是否正确，避免时间矛盾
category: evaluation
skill_type: prompt
tags:
  - 时间线
  - 校验
  - 逻辑
use_cases:
  - 校验时间线
  - 检测时间矛盾
  - 验证时间逻辑
applicable_agent_types:
  - evaluator
load_mode: on_demand
priority: 70
is_system: true
is_enabled: true
parameters:
  - name: chapter_content
    type: string
    description: 章节内容
    required: true
  - name: existing_timeline
    type: array
    description: 已有时间线
---

# 时间线校验技能

## 任务：时间线校验

请校验以下内容的时间线：

### 章节内容

{{chapter_content}}

### 已有时间线

{{existing_timeline}}

### 校验维度

#### 1. 时间顺序

- 事件顺序是否正确
- 闪回是否标注清楚
- 有无时间错乱

#### 2. 时间跨度

- 时间流逝是否合理
- 行程时间是否足够
- 季节变化是否正确

#### 3. 时间标记

- 时间描述是否清晰
- "三天后"等是否计算正确
- 年龄/日期是否一致

#### 4. 时间冲突

- 是否有矛盾的时间点
- 同时发生的事件是否正确
- 时间差是否合理

### 输出格式（JSON）

```json
{
  "timeline_valid": true,
  "events": [
    {"event": "事件", "time": "时间点", "order": 1, "valid": true}
  ],
  "time_issues": [
    {"type": "问题类型", "description": "描述", "location": "位置", "fix": "修复建议"}
  ],
  "suggestions": ["建议"]
}
```
