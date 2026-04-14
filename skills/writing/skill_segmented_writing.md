---
id: skill_segmented_writing
name: 分段生成规划
description: 将长章节分割成多个段落进行生成，提高质量和可控性
category: writing
skill_type: prompt
tags:
  - 分段
  - 生成
  - 规划
use_cases:
  - 分割长章节
  - 规划分段内容
  - 协调多段生成
applicable_agent_types:
  - writer
  - scene_coordinator
load_mode: on_demand
priority: 85
is_system: true
is_enabled: true
parameters:
  - name: chapter_outline
    type: string
    description: 章节大纲
    required: true
  - name: target_words
    type: number
    description: 目标字数
    default: 3000
  - name: segment_count
    type: number
    description: 分段数量
    default: 3
---

# 分段生成规划技能

## 任务：分段生成规划

请将以下章节大纲分割成多个可独立生成的段落：

### 章节大纲

{{chapter_outline}}

### 目标字数

{{target_words}}

### 分段数量

{{segment_count}}

### 规划要求

1. 每段有独立的主题和目标
2. 段落之间有自然的衔接点
3. 各段字数分配合理
4. 保持情节连贯性

### 输出格式（JSON）

```json
{
  "segments": [
    {
      "index": 1,
      "theme": "主题",
      "target_words": 1000,
      "key_content": "关键内容",
      "start_context": "开头衔接",
      "end_context": "结尾衔接",
      "characters": ["涉及角色"]
    }
  ],
  "total_words": 3000,
  "connections": ["段落间衔接说明"]
}
```
