---
id: skill_word_count
name: 字数统计分析
description: 统计和分析文本字数，确保达到目标要求
category: analysis
skill_type: prompt
tags:
  - 字数
  - 统计
  - 分析
use_cases:
  - 统计字数
  - 分析篇幅
  - 达标检查
applicable_agent_types:
  - writer
  - summarizer
  - scene_coordinator
  - evaluator
load_mode: on_demand
priority: 55
is_system: true
is_enabled: true
parameters:
  - name: content
    type: string
    description: 待统计内容
    required: true
  - name: target_words
    type: number
    description: 目标字数
---

# 字数统计分析技能

## 任务：字数统计分析

请统计以下内容的字数：

### 待统计内容

{{content}}

### 目标字数

{{target_words}}

### 统计要求

1. 统计实际字数（不含标点符号）
2. 计算达标百分比
3. 如不达标，计算差额

### 输出格式（JSON）

```json
{
  "actual_words": 2800,
  "target_words": 3000,
  "percentage": 93.3,
  "passed": true,
  "shortfall": 0,
  "details": {
    "chinese_chars": 2500,
    "punctuation": 150,
    "spaces": 50,
    "total_chars": 2700
  }
}
```
