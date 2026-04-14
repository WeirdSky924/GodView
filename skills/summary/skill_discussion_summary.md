---
id: skill_discussion_summary
name: 讨论总结
description: 总结多角色讨论场景的关键内容和结论
category: summary
skill_type: prompt
tags:
  - 讨论
  - 总结
  - 会议
use_cases:
  - 总结讨论内容
  - 提取关键观点
  - 记录决议结论
applicable_agent_types:
  - summarizer
load_mode: on_demand
priority: 65
is_system: true
is_enabled: true
parameters:
  - name: discussion_content
    type: string
    description: 讨论内容
    required: true
  - name: participants
    type: array
    description: 参与角色
  - name: discussion_topic
    type: string
    description: 讨论主题
output_spec:
  - name: summary
    type: string
  - name: core_viewpoints
    type: array
  - name: discussion_process
    type: array
  - name: conclusions
    type: object
  - name: character_highlights
    type: array
---

# 讨论总结技能

## 任务：讨论总结

请总结以下讨论场景的内容：

### 讨论内容

{{discussion_content}}

### 参与角色

{{participants}}

### 讨论主题

{{discussion_topic}}

### 总结要求

#### 1. 核心观点

- 各方的主要立场
- 关键论点和论据
- 重要的分歧点

#### 2. 讨论进程

- 讨论的发展脉络
- 观点的变化过程
- 达成的共识

#### 3. 结论决议

- 最终达成的结论
- 未解决的问题
- 后续行动计划

#### 4. 角色表现

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
```
