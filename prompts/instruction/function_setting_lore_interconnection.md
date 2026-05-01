---
id: function_setting_lore_interconnection
name: Setting 设定互联规则
description: 新设定与已有角色、地点、势力、伏笔、大纲和设定库之间的互联、依赖、冲突与用途说明
category: instruction
tags:
  - function
  - setting
  - lore_interconnection
  - resource_graph
use_cases:
  - 设定生成
  - 设定修订
  - 资源关联分析
applies_to:
  - setting
priority: 82
is_system: true
---

# Setting 设定互联规则

每个新设定都应作为项目资源网络中的节点，而不是孤立文本。

## 必须分析的关系

- 与已有设定的关系：依赖、扩展、支撑、冲突、替代、限制。
- 与角色的关系：谁知道、谁受影响、谁能使用、谁不能接触。
- 与地点/势力的关系：归属、管辖、传播范围、禁区、资源来源。
- 与伏笔的关系：可埋设、可回收、可误导、可延后揭示。
- 与大纲的关系：支撑哪些章节，是否影响已审批大纲，是否需要 revision proposal。

## 结构化建议

如果当前模型或数据库字段支持，应输出：

```json
{
  "related_characters": [],
  "related_locations": [],
  "related_items": [],
  "related_factions": [],
  "depends_on_lore": [],
  "supports_lore": [],
  "potential_conflicts": [],
  "usage_guidance": "如何在章节中使用，当前阶段可见到什么程度"
}
```

若字段暂不支持，可把这些信息放入 `summary`、`constraints`、`tags` 或待确认说明中。

## 冲突处理

- 发现潜在冲突时，不要静默覆盖旧设定。
- 明确列出冲突对象、冲突原因、影响范围和建议处理方式。
- 对宪法级或核心设定冲突，应优先保护既有设定，除非用户明确要求走修订流程。
