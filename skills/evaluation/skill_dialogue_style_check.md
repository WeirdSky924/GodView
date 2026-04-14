---
id: skill_dialogue_style_check
name: 对话风格一致性检查
description: 检查对话是否符合各角色的说话风格
category: evaluation
skill_type: prompt
tags:
  - 对话
  - 风格
  - 一致性
use_cases:
  - 检查对话风格
  - 验证人物区分
  - 优化对话质量
applicable_agent_types:
  - evaluator
  - character
load_mode: on_demand
priority: 80
is_system: true
is_enabled: true
parameters:
  - name: chapter_content
    type: string
    description: 章节内容
    required: true
  - name: character_speech_styles
    type: object
    description: 角色说话风格设定
---

# 对话风格一致性检查技能

## 任务：对话风格一致性检查

请检查对话风格是否一致：

### 章节内容

{{chapter_content}}

### 角色说话风格设定

{{character_speech_styles}}

### 检查维度

#### 1. 用词风格

- 是否符合角色身份
- 是否符合教育背景
- 是否符合性格特点

#### 2. 句式特点

- 长短句偏好是否一致
- 口头禅是否保留
- 语序特点是否体现

#### 3. 情感表达

- 表达方式是否符合人设
- 情绪反应是否合理
- 内心活动是否一致

#### 4. 人物区分

- 不同角色是否有区别
- 读者能否从对话识别角色
- 是否有人物混同

### 输出格式（JSON）

```json
{
  "dialogues_analyzed": 20,
  "style_issues": [
    {"character": "角色名", "dialogue": "对话内容", "issue": "问题描述", "suggestion": "修改建议"}
  ],
  "character_distinctness": {"score": 85, "comment": "人物区分度评价"},
  "overall_score": 90,
  "suggestions": ["整体建议"]
}
```
