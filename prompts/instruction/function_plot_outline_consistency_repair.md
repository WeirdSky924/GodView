---
id: function_plot_outline_consistency_repair
name: Plot Outline 设定一致性修正
description: Plot Outline 在设定一致性检测发现冲突或风险后，对已生成大纲进行一次修正的稳定指令
category: instruction
tags:
  - function
  - outline
  - consistency
  - repair
use_cases:
  - 修正章节大纲设定冲突
  - 根据一致性检测反馈重出大纲 JSON
applies_to:
  - plot_outline
priority: 82
is_system: true
---

# Plot Outline 设定一致性修正

你刚生成的章节大纲存在设定一致性风险。请基于原任务和下方运行时反馈，立即修正大纲并重新输出完整 JSON。

## 修正原则

1. 宪法级设定优先级最高，不得为了戏剧性、爽点、伏笔或输出格式偏好而违反。
2. 核心设定必须保持一致；如果大纲与核心设定冲突，应修改大纲而不是改写设定。
3. 角色立场、能力边界、时间线、地点关系和已确认伏笔状态必须自洽。
4. 只修正被冲突、风险或设定缺口影响的内容；不要无关重写整章结构。
5. 如果原任务与设定约束冲突，以设定约束为准，并选择最小但完整的剧情替代方案。

## 输出要求

- 重新输出完整大纲 JSON。
- 不要输出解释、道歉、Markdown 代码块或 JSON 之外的文字。
- 不要省略字段，不要使用省略号。
- 修正后的 JSON 必须仍符合 Plot Outline 输出格式资产的字段约定。
