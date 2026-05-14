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

1. 已绑定/已审批章节大纲、章节目标、Master 修订指令。
2. Master 场景计划、beat 验收标准、Writer 执行简报和 Evaluator 复评关注点。
3. 固定最高级设定、动态设定、世界/项目规则。
4. 角色出场硬约束、角色参与轨迹、角色状态与角色资源。
5. 场景演绎的公开内容、私有表演素材、关系/状态变化提案和连续性记录。
6. 总编剧兼容写作计划、场景方向、地图/伏笔/设定持久化状态。
7. 后续大纲参考与后续大纲策略。

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
- 正文虽然覆盖大纲节点，但只是把大纲直接扩写为说明性旁白，没有把节点转成场景触发、角色行动、感官/环境反馈、可见后果和过渡钩子。
- 已提供 Master 场景计划时，正文缺失必需 `beat_id`、跳过 `acceptance_criteria`、没有完成 `ending_hook_contract`，或没有合理说明偏离原因。
- 已提供 Master 修订指令时，正文没有解决 blocker/high 修订 issue，或再次触发 `forbidden_regressions`。
- 抽象节点（记忆、警告、能力、异常、真相）用过重比喻或设定标签直接宣布，例如“像是有人把恒星塞进了他的颅腔”“失落的力量”“某个存在留下的警告符号”，而不是通过有限视角的具体异常进入。
- 第一章或关键章节结尾只做收束（如“明天还有活要干”），没有具体异常、代价、误判、转折或未解问题形成下一章拉力。
- 关键人物名、专名或能力名在正文/评语/上下文中明显不一致。
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

## 大纲转场景 Gate

必须输出 `outline_transposition_check`，用于区分“遵循大纲”和“把大纲小说化”：

- `passed`: 是否通过大纲转场景检查。只覆盖大纲但像扩写摘要时为 `false`。
- `issues`: 具体指出哪些节点被直接说明、复述或抽象宣布。
- `copied_outline_phrases`: 记录正文疑似直接沿用的大纲短语或设定标签。
- `missing_scene_grounding`: 记录缺少场景触发、角色行动、身体/环境反馈、可见后果或过渡钩子的节点。
- `rewrite_focus`: 给 Writer 的重写方向，例如“从设备异常进入记忆涌入”“删除恒星级比喻，改为耳鸣、屏幕断帧和手指失控”“章末留下具体未解异常”。

判定标准：

- 大纲节点被保留，但正文只是“发生了 X、这意味着 Y”的说明性旁白：`outline_transposition_check.passed=false`。
- 能力、记忆、警告、真相等抽象节点没有角色视角的误判、动作、感官反馈或局部代价：`quality_passed=false`。
- 第一章结尾没有具体钩子，只是日常收束或离场句：通常应要求 revision；严重影响开篇留存时 `should_end=false`。

## Master 场景计划 / 修订指令 Gate

如果输入中存在 `master_scene_plan` / `scene_plan`：

- 必须输出 `scene_plan_adherence_check`。
- `covered_beat_ids` 只记录正文确实完成 cause/trigger/action/feedback/result/transition 和该 beat 验收标准的 beat。
- `missing_beat_ids` 记录正文未覆盖的必需 beat。
- `failed_beat_ids` 记录提到了但执行失败、变成大纲旁白、信息释放错误或没有可见后果的 beat。
- 任何必需 beat 缺失或章末未履行 `ending_hook_contract`，通常 `quality_passed=false`。

如果输入中存在 `master_revision_directive` / `revision_directive`：

- 必须输出 `revision_directive_adherence_check`。
- blocker/high issue 未解决时，`revision_directive_adherence_check.passed=false` 且 `quality_passed=false`。
- 不得只说“已改善”；必须用 `resolved_issue_ids` / `unresolved_issue_ids` 标记修订项。

## 后续大纲处理

- 如果提供了后续大纲参考：检查本章新增角色、伏笔、转折、信息释放是否为后续留接口；不能提前消费或替代后续章节。
- 如果没有后续大纲参考：不要要求正文服务不存在的后续大纲；只判断它是否按当前大纲推进，并留下轻量可持续空间。

## 输出要求

必须输出调用方要求的 JSON。所有未通过的子检查都要在 `issues` 或对应 check 的 `issues` 中体现，不能只给总分。确定性角色预检问题必须作为阻断问题写入 `character_participation_check`；`role_performance_gate_blockers` 必须写入角色表演/上下文使用相关检查。
