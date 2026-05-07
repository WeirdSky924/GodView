---
id: function_setting_segmented_context_synthesis
name: Setting 分段上下文综合
description: 长上下文分段提取、JSON 容错、关键信息索引和跨段综合规则
category: instruction
tags:
  - function
  - setting
  - segmented_context
  - synthesis
use_cases:
  - 长上下文设定分析
  - /lore 分段上下文综合
  - 设定互联分析
applies_to:
  - setting
priority: 83
is_system: true
---

# Setting 分段上下文综合

当项目上下文过长并被拆分为多个片段时，必须把分段结果视为“全局信息索引”，而不是只阅读最后一段或用户最新一句话。

## 分段提取要求

每个片段应提取以下信息点：

- 信息类型：世界观、角色、地点、势力、伏笔、章节大纲、时间线、规则、资源缺口等。
- 实体名称：具体角色、地点、设定、事件、组织、道具或章节。
- 关键事实：保留具体细节、限制、状态、层级、时间点和因果关系。
- 与用户问题的相关性：高 / 中 / 低。
- 跨段关系线索：该信息可能依赖、支持、冲突或呼应哪些其他资源。

## 分段提取 JSON 合同

片段级提取必须直接输出 JSON 数组，数组元素使用以下稳定字段：

```json
[
  {
    "category": "信息类型，如世界观、角色、事件、规则、时间线、资源缺口等",
    "entity": "实体名称，如具体角色名、地点名、事件名、势力名或设定名",
    "key_fact": "关键事实，一句话描述并保留具体细节",
    "relevance": "高|中|低",
    "related_entities": ["与该事实有关的其他角色、设定、势力或地点"],
    "relation_type": "depends_on|supports|conflicts_with|mentions|requires_resource",
    "potential_conflicts": ["该事实与其他段落可能冲突的具体点"],
    "resource_requirements": [
      {
        "requirement_type": "character|lore|faction|location|item|ability|relationship|event_rule|crisis_resolution",
        "resource_name": "待补资源名",
        "severity": "blocking|advisory|optional",
        "reason": "为什么需要补全"
      }
    ]
  }
]
```

## 片段提取规则

1. `key_fact` 必须包含具体细节，不要泛泛而谈。
2. 如果有时间线信息，必须记录具体时间点。
3. 如果有数值信息，如等级、数量、年份、章节号，必须记录具体数值。
4. 保持信息点独立，每个信息点只描述一个事实。
5. 如果不同片段之间存在依赖、支撑、冲突或资源缺口，必须通过 `related_entities`、`relation_type`、`potential_conflicts`、`resource_requirements` 标出。
6. 只输出 JSON 数组，不要输出解释文字或 markdown 代码块。

## JSON 容错原则

分段提取输出应尽量是 JSON 数组。轻微格式错误不应导致整段信息丢失：

- 允许解析 markdown 包裹的 JSON。
- 允许尝试修复尾随逗号、中文标点、相邻对象缺逗号、单引号字符串等常见错误。
- 如果结构仍无法解析，应保留可读文本摘要，避免该片段完全丢失。

## 跨段综合要求

主生成阶段必须同时参考：

1. 关键信息索引。
2. 完整原始上下文。
3. 最近对话。
4. 用户当前意图。

不得让后面的片段覆盖前面的关键信息。若前后片段冲突，必须显式说明冲突来源和建议处理方式。

## 输出倾向

生成新设定或建议时，应说明：

- 它连接了哪些已有角色/地点/设定/伏笔/大纲章节。
- 它解决了什么资源缺口。
- 它可能引入什么冲突或需要哪些后续资源。
- 它在当前剧情阶段的可见层级。
