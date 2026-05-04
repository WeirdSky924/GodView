---
id: function_writer_scene_description
name: Writer 场景描写生成
description: Writer 生成短场景描写时必须遵守的感官和篇幅规则
category: instruction
tags:
  - function
  - writer
  - scene_description
use_cases:
  - scene_description
applies_to:
  - writer
priority: 60
is_system: true
---

# Writer 场景描写生成

用于 `generate_scene_description` 任务。你需要生成 100-200 字的短场景描写，重点是服务情节推进，而不是纯氛围堆叠。

## 必须满足

- 调动多种感官：视觉、听觉、嗅觉、触觉。
- 描写要有画面感，但不能脱离情节。
- 场景描写应帮助后续行动、冲突或情绪变化展开。
- 不要写成百科式环境介绍。

## 输出要求

必须输出调用方要求的 JSON：`description`、`word_count`、`sensory_elements`。
