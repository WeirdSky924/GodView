---
id: skill_character_memory_check
name: 角色记忆一致性检查
description: 检查角色是否表现出应有的记忆，避免角色"失忆"
category: evaluation
skill_type: prompt
tags:
  - 记忆
  - 一致性
  - 角色
use_cases:
  - 检查记忆一致性
  - 避免角色失忆
  - 验证信息知晓
applicable_agent_types:
  - evaluator
  - character
load_mode: on_demand
priority: 90
is_system: true
is_enabled: true
parameters:
  - name: chapter_content
    type: string
    description: 章节内容
    required: true
  - name: character_knowledge
    type: object
    description: 角色已知信息
  - name: interaction_history
    type: array
    description: 历史互动记录
---

# 角色记忆一致性检查技能

## 任务：角色记忆一致性检查

请检查角色的记忆表现是否一致：

### 章节内容

{{chapter_content}}

### 角色已知信息

{{character_knowledge}}

### 历史互动记录

{{interaction_history}}

### 检查维度

#### 1. 信息记忆

- 角色是否记得已知道的信息
- 是否出现不应有的"失忆"
- 是否有不应有的预知

#### 2. 情感记忆

- 对他人的态度是否一致
- 情感变化是否有依据
- 好恶是否有延续

#### 3. 经历记忆

- 是否记得共同经历
- 对事件的反应是否合理
- 成长变化是否有迹可循

### 输出格式（JSON）

```json
{
  "memory_issues": [
    {"character": "角色名", "type": "信息记忆", "issue": "问题描述", "location": "位置"}
  ],
  "characters_checked": ["角色列表"],
  "overall_score": 95,
  "suggestions": ["建议"]
}
```
