---
id: skill_content_merge
name: 内容合并处理
description: 将多个分段内容合并成完整章节，处理衔接和一致性
category: writing
skill_type: prompt
tags:
  - 合并
  - 整合
  - 衔接
use_cases:
  - 合并分段内容
  - 处理段落衔接
  - 统一内容风格
applicable_agent_types:
  - writer
  - scene_coordinator
load_mode: on_demand
priority: 50
is_system: true
is_enabled: true
parameters:
  - name: segments
    type: array
    description: 分段内容列表
    required: true
  - name: merge_mode
    type: string
    description: 合并模式
    default: smooth
---

# 内容合并处理技能

## 任务：内容合并处理

请将以下分段内容合并成完整章节：

### 分段内容列表

{{segments}}

### 合并模式

{{merge_mode}}

### 合并要求

1. 处理段落间的衔接
2. 统一语言风格
3. 消除重复内容
4. 保持情节连贯

### 输出格式（JSON）

```json
{
  "merged_content": "合并后的完整内容",
  "word_count": 3000,
  "connections_handled": ["已处理的衔接点"],
  "deduplication": ["已消除的重复内容"],
  "style_adjustments": ["风格调整说明"]
}
```
