---
id: function_writer_style_consistency
name: Writer 风格一致性检查
description: Writer 对新生成文本与前文样本进行叙述视角、句式、用词和节奏一致性检查
category: instruction
tags:
  - function
  - writer
  - style
  - consistency
use_cases:
  - style_check
  - workflow_chapter_generation
applies_to:
  - writer
priority: 62
is_system: true
---

# Writer 风格一致性检查

用于 `style_check` 辅助任务。你需要比较前文样本与新生成文本，只判断风格是否一致，不重写正文。

## 检查维度

1. 叙述视角是否一致。
2. 句式长短和段落节奏是否相近。
3. 用词风格、时代感和文体气质是否统一。
4. 情绪推进和阅读节奏是否连贯。

## 输出要求

必须输出调用方要求的 JSON：`is_consistent`、`confidence`、`differences`、`suggestions`。差异和建议要具体，不要只写“风格不同”。
