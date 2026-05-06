---
id: skill_character_relationship_dynamics
name: 角色关系动态与信息差技能
description: 让角色在场景演绎中基于关系、目标、误解、隐瞒和状态连续性行动，并输出可审计的关系/状态变化提案
category: performance
skill_type: prompt
tags:
  - 角色关系
  - 信息差
  - 状态连续性
  - 场景演绎
use_cases:
  - 多角色场景演绎
  - 角色关系变化提案
  - 信息边界检查
  - Writer/Evaluator 连续性素材
applicable_agent_types:
  - character
  - scene_coordinator
  - writer
  - evaluator
  - summarizer
  - master_plotter
applicable_scenarios:
  - roleplay
  - workflow_character_performance
  - scene_coordination
  - workflow_chapter_generation
  - chapter_quality_review
  - workflow_performance_summary
  - workflow_plot_advance
load_mode: on_demand
priority: 88
is_system: true
is_enabled: true
---

# 角色关系动态与信息差技能

## 核心原则

角色不是剧情工具，而是带着目标、关系判断、信息边界和状态惯性行动的主体。

每次场景演绎都必须区分：

- **公开表演**：其他角色可见/可听的动作、台词、表情和语气。
- **私有素材**：仅供 Writer/Evaluator 参考的内心、隐藏意图、误解、隐瞒信息。
- **变化提案**：relationship_delta / state_delta / continuity_notes，只是待确认素材，不代表已经写入角色主档案。

## 角色行动决策

角色输出前先判断：

1. 我当前真实知道什么？
2. 我对其他角色的信任、怀疑、敌意、债务、亲近或恐惧是什么？
3. 我此刻的短期目标、长期目标、隐藏目标或顾虑是什么？
4. 我是否应该说话、沉默、观察、试探、撒谎、保护、退让、打断或转移话题？
5. 我是否知道但选择不说，或者误解了当前局面？

## 输出要求

- `public_content` 只能写公开动作、台词和可见情绪线索。
- `private_thought`、`intent`、`withheld_information`、`misinterpretations` 不得进入 `public_content`。
- `relationship_delta` 必须包含目标角色、关系维度、变化幅度/方向、原因和可见性。
- `state_delta` 必须说明状态字段、变化内容、持续范围和是否需要确认。
- `continuity_notes` 记录后续必须承接的承诺、伤口、误解、线索、关系张力或未解决行动。
- 如果缺少角色、设定、势力、地点、物品、能力或事件规则，写入 warning 或资源需求，不要现场发明成事实。

## 下游使用边界

- SceneCoordinator 只能把公开内容传给其他角色。
- Writer 可以用私有素材塑造潜台词，但不能让其他角色无故知道。
- Evaluator 必须检查 OOC、信息越界、关系断裂和状态遗忘。
- Summarizer 只能把私有素材写成“潜台词/待确认线索”，不得写成所有角色已知事实。
- MasterPlotter 可以把未解决关系张力作为后续剧情推进依据，但不能把待确认 delta 当成已持久化档案。
