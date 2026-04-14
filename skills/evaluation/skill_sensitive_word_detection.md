---
id: skill_sensitive_word_detection
name: 敏感词检测
description: 检测内容中是否包含敏感词汇，确保内容安全
category: evaluation
skill_type: prompt
tags:
  - 敏感词
  - 检测
  - 安全
use_cases:
  - 检测敏感内容
  - 确保内容安全
  - 提供替换建议
applicable_agent_types:
  - writer
  - evaluator
load_mode: on_demand
priority: 95
is_system: true
is_enabled: true
parameters:
  - name: chapter_content
    type: string
    description: 章节内容
    required: true
---

# 敏感词检测技能

## 任务：敏感词检测

请检测以下内容中的敏感词：

### 章节内容

{{chapter_content}}

### 检测类型

#### 1. 政治敏感

- 政治人物、事件相关
- 政治体制相关表述
- 敏感政治词汇

#### 2. 色情低俗

- 露骨描写
- 低俗表达
- 暗示性内容

#### 3. 暴力恐怖

- 过度暴力描写
- 恐怖主义相关
- 血腥内容

#### 4. 违法内容

- 违法行为描写
- 毒品相关
- 赌博相关

#### 5. 歧视偏见

- 种族歧视
- 地域歧视
- 性别歧视

### 输出格式（JSON）

```json
{
  "sensitive_words": [
    {"word": "敏感词", "type": "类型", "location": "位置", "severity": "严重程度", "suggestion": "替换建议"}
  ],
  "severity_count": {"critical": 0, "major": 0, "minor": 1},
  "overall_safe": true,
  "needs_revision": false,
  "auto_replace_suggestions": {"原词": "替换词"}
}
```
