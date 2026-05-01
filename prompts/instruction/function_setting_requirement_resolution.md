---
id: function_setting_requirement_resolution
name: Setting 大纲资源需求解决
description: 根据大纲资源缺口补齐、绑定或提出设定/角色/地点/势力等资源需求的规则
category: instruction
tags:
  - function
  - setting
  - requirement_resolution
  - outline_resource
use_cases:
  - 大纲资源需求解决
  - 章节 readiness 前置补齐
  - 设定补全
applies_to:
  - setting
priority: 81
is_system: true
---

# Setting 大纲资源需求解决

用于 `setting.outline_requirement_resolution` 场景。你的任务是根据大纲资源缺口，决定应绑定已有资源、创建待确认资源草案、还是提出额外需求。

## 处理顺序

1. 先查找并复用已有设定、角色、地点、势力、道具、能力或伏笔。
2. 若已有资源可满足需求，建议绑定，不要重复创建。
3. 若缺口确实存在，创建待确认草案，并说明它解决哪个 requirement。
4. 若缺口需要多个资源配合，拆分为多个 resource requirement。
5. 若补齐会影响 approved outline，只提出 revision proposal，不直接改大纲。

## Blocking / Advisory / Optional

- `blocking`：缺失会导致章节无法安全生成，例如关键角色、关键设定、危机解决规则、主要地点。
- `advisory`：缺失不会阻止生成，但会降低质量，例如风俗、细节、次要地点。
- `optional`：可增强表现但不是当前章节必需。

## 长篇约束

- 不能为了解决当前章节需求而提前创建终局真相或最终反派正面设定。
- 高阶势力或核心秘密可以创建后台资源，但当前阶段的 usage guidance 必须限制可见层。
- 关键危机解决必须来自已铺垫资源、代价、行动或线索；不能用万能新设定救场。

## 输出要求

给出：

- matched_resource：可绑定的已有资源。
- proposed_resource：待确认的新资源草案。
- unresolved_requirements：仍需补齐的资源缺口。
- potential_conflicts：可能冲突。
- usage_guidance：当前章节如何安全使用。
