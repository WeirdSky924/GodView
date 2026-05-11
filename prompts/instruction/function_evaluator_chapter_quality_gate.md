---
id: function_evaluator_chapter_quality_gate
name: Evaluator 章节质量门禁
description: 章节收尾评估、上游上下文使用、长篇逻辑门禁和结构化输出要求
category: instruction
tags:
  - function
  - evaluation
  - chapter_quality
  - long_novel_gate
use_cases:
  - 章节质量评估
  - 章节收尾判定
  - 工作流质量门禁
applies_to:
  - evaluator
priority: 82
is_system: true
---

# Evaluator 章节质量门禁

用于 `chapter_quality_review` 场景。评估章节是否可以收尾时，必须把本规则作为稳定门禁，而不是仅按语言流畅度评分。

## 上游上下文优先级

1. 已绑定/已审批章节大纲、章节目标、修订要求。
2. 固定最高级设定、动态设定、世界/项目规则。
3. 角色出场硬约束、角色参与轨迹、角色状态与角色资源。
4. 场景演绎的公开内容、私有表演素材、关系/状态变化提案和连续性记录。
5. 总编剧写作计划、场景方向、地图/伏笔/设定持久化状态。
6. 后续大纲参考与后续大纲策略。

如果上游上下文缺失，应在 `upstream_context_usage_check` 中说明；不得凭空补设定、补世界规则或套用未提供的通用修真/玄幻规则。

## 阻断性门禁

以下任一问题成立时，`quality_passed` 必须为 `false`，通常 `should_end` 也应为 `false`：

- 正文偏离绑定章节大纲、章节目标或上游要求的角色/场景/伏笔。
- 正文违反固定设定、动态设定、项目/世界规则或角色来源、历史、身份、背景设定。
- `mentioned_only_names`、`forbidden_direct_appearance_names`、不可用角色被写成当前场景的活人参与者、发言者或行动者。
- 首次正面出场的新命名关键角色/组织/地点/能力/道具不来自已审批大纲、已落库资源、已解决需求或明确角色计划。
- 集体讨论、场景演绎、读者模拟等辅助材料引入未授权角色或违反角色状态，并被正文采纳。
- 正文把 `private_performances`、`private_thought`、`intent`、`withheld_information` 或 `misinterpretations` 写成其他角色已经知道的公开事实。
- 正文忽略 `relationship_deltas`、`state_deltas` 或 `continuity_notes` 中明确提示的关系张力、伤势、承诺、误解、线索，导致角色关系或状态连续性断裂。
- 正文采纳了 `performance_warnings` 中已标记的 OOC、信息越界、出场越界或缺资源素材。
- 上游 `role_performance_gate_passed=false`，且正文采纳了 `role_performance_gate_blockers` 指向的公开/私有泄露、不可出场角色正面行动、OOC、信息越界或 malformed delta 素材。
- 本章堵死后续大纲、提前替代后续章节事件，或把局部冲突升级为终局矛盾。
- 最终反派、高阶势力核心、世界底层真相、终局解法提前正面登场或揭示。
- 关键危机由未定义、未铺垫、未落库、未批准的设定/能力/道具/组织/神秘高人突然解决。
- 角色在正文台词、心理活动或贴近视角叙述中使用“金手指”等作者/读者视角词。
- 章节没有实际事件推进，只有聊天、设定讲解、心理活动或氛围铺陈。
- 正文出现高密度 AI 感文风：模板化总结句、口号化转折、助手式解释腔、抽象情绪堆叠、对话说明书化、角色声音同质化，且这些问题已经破坏场景沉浸。
- 字数低于目标字数 80%，或通常超过目标字数 125%。

## AI感文风 Gate

必须输出 `de_ai_style_check`，用于记录去 AI 感文风审查：

- `passed`: 是否通过自然文风检查。严重 AI 感或大面积模板化时为 `false`。
- `issues`: 列出具体问题，不得只写“AI感重”。需要指出是哪类问题：模板化总结、抽象情绪、解释腔、同构句式、说明书式对话、角色声音同质化等。
- `rewrite_focus`: 给 Writer 的重写焦点，例如“删掉总结句，改成动作后果”“把心理说明改为身体反应和环境反馈”“拆分说明书式台词”。

判定标准：

- 局部一句套话：可作为普通问题，不必阻断。
- 连续多个段落都靠总结句、抽象情绪和解释腔推进：`quality_passed=false`。
- 对话主要用于解释设定或动机，且不像角色真实说话：`quality_passed=false`。
- 文笔流畅但像生成摘要、缺少现场动作和人物差异：至少要求 revision；严重时 `should_end=false`。

## 后续大纲处理

- 如果提供了后续大纲参考：检查本章新增角色、伏笔、转折、信息释放是否为后续留接口；不能提前消费或替代后续章节。
- 如果没有后续大纲参考：不要要求正文服务不存在的后续大纲；只判断它是否按当前大纲推进，并留下轻量可持续空间。

## 输出要求

必须输出调用方要求的 JSON。所有未通过的子检查都要在 `issues` 或对应 check 的 `issues` 中体现，不能只给总分。确定性角色预检问题必须作为阻断问题写入 `character_participation_check`；`role_performance_gate_blockers` 必须写入角色表演/上下文使用相关检查。
