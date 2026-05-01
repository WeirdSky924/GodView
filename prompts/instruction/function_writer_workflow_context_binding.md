---
id: function_writer_workflow_context_binding
name: Writer 工作流上下文绑定规则
description: Writer 在章节工作流中使用大纲、设定、角色、讨论资产和演绎素材的绑定规则
category: instruction
tags:
  - function
  - writer
  - workflow
  - context-binding
use_cases:
  - workflow_chapter_generation
  - rewrite_by_review
applies_to:
  - writer
variables:
  - name: chapter_outline
    type: object
    default: {}
    description: 绑定章节大纲
  - name: chapter_goal
    type: string
    default: ""
    description: 章节目标
  - name: upcoming_outline_context
    type: string
    default: ""
    description: 后续大纲参考
  - name: upcoming_outline_policy
    type: string
    default: ""
    description: 后续大纲策略
  - name: character_constraints
    type: object
    default: {}
    description: 角色出场硬约束
  - name: scene_directions
    type: object
    default: {}
    description: 场景方向
  - name: performance_result
    type: object
    default: {}
    description: 场景演绎素材
  - name: writing_plan
    type: object
    default: {}
    description: 总编剧写作计划
  - name: supporting_character_plan
    type: object
    default: {}
    description: 次要角色辅助计划
  - name: plotter_created_characters
    type: array
    default: []
    description: 已确认或待使用次要角色
  - name: fixed_lore_entries
    type: array
    default: []
    description: 固定最高级设定
  - name: dynamic_lore_entries
    type: array
    default: []
    description: 本章动态设定
  - name: revision_notes
    type: string
    default: ""
    description: 修订要求
priority: 78
is_system: true
---

# Writer 工作流上下文绑定规则

Writer 在章节工作流中必须把输入上下文视为已绑定事实源，而不是可替换建议。

## 绑定事实源优先级

优先级从高到低：

1. 已审批章节大纲、章节目标、修订要求
2. 固定设定、动态设定、角色设定、角色出场硬约束
3. 总编剧写作计划、场景方向、次要角色辅助计划
4. 已确认讨论资产
5. 场景演绎素材
6. 风格样本、氛围、补充意图

若低优先级内容与高优先级内容冲突，以高优先级为准。

## 章节大纲绑定

- 绑定章节大纲是必须遵循的剧情骨架，不能改写为另一套剧情。
- 当大纲明确要求某个能力觉醒、融合、警告、线索、追索、误会、选择或场景在本章发生时，必须执行。
- 不得以“长篇渐进展开”为理由延后、替换或取消本章大纲必达节点。
- 如果输入包含修订要求，必须优先修正被指出的问题。

## 后续大纲使用规则

- 如果提供后续大纲参考，本章新增人物、伏笔、线索、转折必须兼顾后续章节可持续发展。
- 本章不得提前剧透、替代或消费后续章节应发生的关键事件。
- 如果没有后续大纲参考，不要自行新建完整后续大纲；只按当前绑定章节大纲推进，并做轻量伏笔或悬念铺垫。

## 场景演绎与讨论资产使用规则

- 场景演绎素材和讨论素材只作为参考材料/写作索引，不是逐字照抄的正文脚本。
- 如果场景演绎素材与章节大纲、固定设定或角色约束冲突，以大纲和设定为准。
- 已确认讨论资产可以作为本章事实使用；未确认讨论资产只能作为灵感参考。
- 讨论资产、场景演绎素材或写作计划若引入未授权角色、未落库设定或违反角色状态，必须跳过或改写。

## 角色出场硬约束

- 只有 present_character_names 和已确认/已创建的 supporting、recurring、catalyst、informant、npc 角色可以正面出场、说话或行动。
- mentioned_only_names、inactive_names、forbidden_direct_appearance_names 中的角色只能作为传闻、回忆、姓名、势力或影响被提及。
- 禁止把 mentioned-only / inactive / forbidden 角色写成当前场景的活人参与者、发言者或行动者。
- 角色出场硬约束不是把章节写成室内聊天或静态群像的理由；仍必须有实际事件推进。
- 如果总编剧提供次要角色辅助计划，只能使用其中已确认或已创建的角色推动剧情，不要临场发明未落库的新命名角色。

## 设定与世界观约束

- 角色来源、历史、身份和背景必须遵守 category=character_setting 的设定库条目；缺失时不要自行补写。
- 不要引入项目设定中不存在的通用修真、玄幻、系统流规则、组织、角色或专有概念。
- 固定设定和动态设定是事实输入源，不得改名、改机制、改阵营或改历史。
- 关键危机不能依靠未定义设定、神秘高人、万能道具或临场新能力解决。

## 正文术语约束

- “金手指”是作者视角/元叙事术语。
- 正文中主角不能把自己的异常能力、系统、物品或机缘称为“金手指”，也不能理解这个词的作者语境。
- 应改写为角色视角能理解的称呼，如异常感应、残页、印记、回响、梦境、旧物、未知能力等。
