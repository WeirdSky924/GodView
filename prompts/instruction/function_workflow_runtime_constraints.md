---
id: function_workflow_runtime_constraints
name: Workflow 运行期角色与素材约束
description: 工作流讨论、场景演绎和后续写作节点共享的角色出场、角色设定来源和演绎素材使用边界
category: instruction
tags:
  - function
  - workflow
  - constraints
  - character
  - continuity
use_cases:
  - 工作流角色出场约束注入
  - 场景演绎素材使用边界
  - 讨论资产与后续写作衔接
applies_to:
  - workflow
priority: 83
is_system: true
---

# Workflow 运行期角色与素材约束

用于 WorkflowEngine 在讨论、场景演绎、总结和后续写作节点之间传递共享边界。运行时代码会提供具体角色名单、出场状态、设定库条目、讨论资产和场景演绎结果；本资产只定义这些动态数据的解释规则。

## 角色出场硬约束

- 只有 `present_character_names` 中的角色可以在当前正面场景中说话、行动或直接参与互动。
- `mentioned_only_names` 只能作为传闻、回忆、姓名、势力影响、背景信息或环境痕迹被提及，不能直接出场、发言或行动。
- `forbidden_direct_appearance_names` 包含死亡、未激活、退场、章节外或不可用角色；这些角色不得被写成当前场景中的活人参与者。
- 如果讨论素材、场景演绎或写作计划引入未授权角色，必须视为未确认素材并跳过、改写或提交待确认资产/修订提案。

## 角色设定来源

- 角色来源、历史、身份和背景必须服从 `selected_lore_entries` 中 `category=character_setting` 的设定库条目。
- 如果角色设定库缺失，不要自行补写成事实；应标记为缺失设定或待确认资产。
- 新角色、新身份、新地点、新道具、新能力或关键组织不得仅凭讨论文本直接生效，必须进入待确认资产或修订提案流程。

## 场景演绎素材边界

- 场景演绎结果是供 Writer、Master Plotter、Evaluator 和后续节点参考的素材索引，不是必须逐字照抄的章节正文。
- 若场景演绎与章节大纲、固定设定、角色硬约束或已确认资产冲突，必须跳过、改写或标记为风险。
- `relationship_delta`、`state_delta`、`continuity_notes` 和类似字段是待确认变化提案，不是已经持久化的世界事实。
- 私有表演素材只能作为 Writer/Evaluator 的潜台词、误解、隐瞒或动机参考，不得写成场内所有角色都知道的公开事实。

## 下游使用要求

- 讨论总结和写作计划可以引用这些约束，但不能静默覆盖 approved outline 或已落库设定。
- 会影响 approved outline 的建议必须标为 revision proposal。
- 会影响角色库、设定库、地图、伏笔或状态的建议必须保留为待确认资产，等待专门落库流程处理。
