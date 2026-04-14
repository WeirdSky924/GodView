---
id: skill_ooc_check
name: OOC角色崩坏检查
description: 检测角色行为是否符合人物设定，避免OOC（Out of Character）
category: evaluation
skill_type: prompt
tags:
  - OOC
  - 角色
  - 一致性
use_cases:
  - 检查角色一致性
  - 避免角色崩坏
  - 验证行为合理性
applicable_agent_types:
  - evaluator
  - character
load_mode: on_demand
priority: 75
is_system: true
is_enabled: true
parameters:
  - name: chapter_content
    type: string
    description: 章节内容
    required: true
  - name: character_profiles
    type: array
    description: 角色设定列表
---

# OOC角色崩坏检查技能

## 任务：OOC角色崩坏检查

请检查以下内容中的角色行为是否符合设定：

### 章节内容

{{chapter_content}}

### 角色设定

{{character_profiles}}

### 检查维度

#### 1. 行为一致性

- 角色行为是否符合性格
- 是否有突兀的性格转变
- 行为动机是否合理

#### 2. 对话一致性

- 说话方式是否符合人设
- 用词是否符合身份背景
- 是否有人物混同

#### 3. 能力一致性

- 角色能力是否与设定匹配
- 是否有突然变强/变弱
- 能力使用是否符合规则

#### 4. 情感一致性

- 情感反应是否合理
- 情感变化是否有铺垫
- 与之前情感状态是否衔接

### 输出格式（JSON）

```json
{
  "ooc_issues": [
    {"character": "角色名", "type": "行为", "location": "位置", "issue": "问题描述", "severity": "严重程度"}
  ],
  "character_scores": {"角色名": {"consistency": 85, "issues": []}},
  "overall_consistency": 90,
  "needs_revision": false,
  "suggestions": ["修改建议"]
}
```
