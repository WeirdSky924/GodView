---
id: skill_content_summary
name: 内容摘要技能
description: 提取章节或段落的关键内容，生成简洁摘要
category: summary
skill_type: prompt
tags:
  - 摘要
  - 提取
  - 总结
use_cases:
  - 生成章节摘要
  - 提取关键信息
  - 内容压缩
applicable_agent_types:
  - summarizer
load_mode: on_demand
priority: 60
is_system: true
is_enabled: true
parameters:
  - name: content
    type: string
    description: 待摘要内容
    required: true
  - name: summary_length
    type: number
    description: 摘要目标字数
    default: 200
---

# 内容摘要技能

## 任务：内容摘要

请提取以下内容的关键信息，生成简洁摘要：

### 待摘要内容

{{content}}

### 摘要要求

- 目标字数：{{summary_length}}字左右
- 保留核心情节和关键信息
- 保持客观中立
- 语言简洁明了

### 输出格式

直接输出摘要文本。
