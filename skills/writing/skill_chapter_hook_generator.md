---
id: skill_chapter_hook_generator
name: 章节悬念钩子生成
description: 为章节结尾生成吸引人的悬念钩子
category: writing
skill_type: prompt
tags:
  - 悬念
  - 钩子
  - 结尾
use_cases:
  - 设计章节结尾
  - 制造悬念
  - 吸引读者继续阅读
applicable_agent_types:
  - writer
load_mode: on_demand
priority: 75
is_system: true
is_enabled: true
parameters:
  - name: chapter_summary
    type: string
    description: 章节内容摘要
    required: true
  - name: key_events
    type: array
    description: 本章关键事件
  - name: next_chapter_hint
    type: string
    description: 下章预告
---

# 章节悬念钩子生成技能

## 任务：章节悬念钩子生成

请为以下章节内容生成结尾悬念钩子：

### 章节内容摘要

{{chapter_summary}}

### 本章关键事件

{{key_events}}

### 下章预告（如有）

{{next_chapter_hint}}

### 悬念钩子类型

#### 1. 危机型钩子

- 主角陷入危险
- 意外事件发生
- 紧迫的威胁

#### 2. 揭示型钩子

- 重要信息揭晓
- 身份暴露
- 真相浮出水面

#### 3. 转折型钩子

- 意想不到的变化
- 关系逆转
- 新势力介入

#### 4. 期待型钩子

- 即将发生的大事
- 重要的约定或承诺
- 目标临近

### 钩子要求

1. **吸引力**：能让读者想继续看下一章
2. **合理性**：与本章内容自然衔接
3. **适度性**：不夸张，不欺骗读者
4. **独特性**：避免老套的"欲知后事如何"

### 输出格式（JSON）

```json
{
  "hook_type": "钩子类型",
  "hook_content": "钩子内容（1-3句话）",
  "emotion_target": "目标读者情绪",
  "next_lead": "对下章的铺垫"
}
```
