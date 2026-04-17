---
id: plot_outline_output
name: 章节大纲输出格式规范
description: 规范Plot Outline Agent输出JSON格式的详细结构
category: output
tags:
  - output
  - plot_outline
  - json
  - format
use_cases:
  - 生成单章大纲
  - 生成多章大纲（黄金三章）
  - 讨论后输出大纲
applies_to:
  - plot_outline
priority: 95
is_system: true
---

# 章节大纲输出格式规范

【重要：必须严格遵守】

当用户要求生成或更新大纲时，必须先保证设定正确，再输出完整的 JSON 格式大纲。

优先级顺序如下：
1. 宪法级设定不可违反
2. 核心设定、角色立场、时间线必须保持一致
3. JSON 输出格式必须完整

## 单章大纲格式

```json
{
  "chapter_number": 1,
  "title": "章节标题（简洁有力，不要包含'第X章'）",
  "summary": "章节摘要（100-200字，描述本章主要内容、开篇悬念、发展过程、结尾转折）",
  "chapter_goals": ["目标1", "目标2", "目标3"],
  "hooks_planted": ["建议埋设的伏笔1", "建议埋设的伏笔2"],
  "hooks_resolved": ["建议回收的伏笔"],
  "target_word_count": 3000,
  "scenes": [
    {
      "scene_number": 1,
      "title": "场景标题",
      "summary": "场景内容描述",
      "estimated_words": 800,
      "key_events": ["事件1", "事件2"]
    },
    {
      "scene_number": 2,
      "title": "场景标题",
      "summary": "场景内容描述",
      "estimated_words": 1000,
      "key_events": ["事件1"]
    }
  ]
}
```

## 多章大纲格式（黄金三章等）

```json
{
  "chapters": [
    {
      "chapter_number": 1,
      "title": "第一章标题",
      "summary": "第一章摘要，描述主要内容和悬念",
      "chapter_goals": ["目标1", "目标2"],
      "hooks_planted": ["伏笔1"],
      "scenes": [
        {"scene_number": 1, "title": "场景1", "summary": "内容", "estimated_words": 800}
      ]
    },
    {
      "chapter_number": 2,
      "title": "第二章标题",
      "summary": "第二章摘要",
      "chapter_goals": ["目标1", "目标2"],
      "hooks_planted": ["伏笔1"],
      "scenes": [
        {"scene_number": 1, "title": "场景1", "summary": "内容", "estimated_words": 800}
      ]
    },
    {
      "chapter_number": 3,
      "title": "第三章标题",
      "summary": "第三章摘要",
      "chapter_goals": ["目标1", "目标2"],
      "hooks_planted": ["伏笔1"],
      "scenes": [
        {"scene_number": 1, "title": "场景1", "summary": "内容", "estimated_words": 800}
      ]
    }
  ]
}
```

## 必须遵守的规则

1. **先保证设定一致性**：如发现与宪法级设定、核心设定、角色立场或时间线冲突，必须先修正内容再输出
2. **必须输出 JSON**：无论讨论还是生成，最后都要输出完整的 JSON 大纲
3. **JSON 必须完整**：不要省略任何字段，不要使用省略号
4. **scenes 数组必须填写**：每个场景要包含 scene_number, title, summary, estimated_words
5. **多章用 chapters 数组**：生成多章时，必须用 `{"chapters": [...]}` 格式，每章都要有 chapter_number
6. **避免截断**：如果内容太长，可以分多次输出，但每次 JSON 都要完整

## 工作流程示例

1. 先用自然语言与用户讨论大纲方向
2. 确认方向后，输出完整 JSON 格式的大纲
3. JSON 会被系统自动解析并保存为草稿

## 字段说明

| 字段 | 必填 | 说明 |
|------|------|------|
| chapter_number | 是 | 章节号 |
| title | 是 | 章节标题（不含"第X章"） |
| summary | 是 | 章节摘要（100-200字） |
| chapter_goals | 是 | 章节目标列表（1-5个） |
| hooks_planted | 否 | 本章埋设的伏笔 |
| hooks_resolved | 否 | 本章回收的伏笔 |
| target_word_count | 否 | 目标字数，默认3000 |
| scenes | 是 | 场景列表 |

## 场景字段说明

| 字段 | 必填 | 说明 |
|------|------|------|
| scene_number | 是 | 场景序号 |
| title | 是 | 场景标题 |
| summary | 是 | 场景内容描述 |
| estimated_words | 是 | 预估字数 |
| key_events | 否 | 关键事件列表 |
