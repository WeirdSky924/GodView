---
id: function_setting_tone_inference
name: Setting 叙事基调推断
description: 从设定对话历史中推断叙事基调，只输出稳定枚举值
category: instruction
tags:
  - function
  - setting
  - inference
  - tone
use_cases:
  - 叙事基调推断
  - 项目初始化辅助
  - 设定会话元数据提取
applies_to:
  - setting
priority: 80
is_system: true
---

# Setting 叙事基调推断

请从输入的设定对话中推断故事的叙事基调。

## 可选基调

- `serious`：严肃、正剧、深刻主题、命运沉重。
- `lighthearted`：轻松、幽默、日常、甜蜜。
- `dark`：暗黑、悲剧、虐心、压抑。
- `comedic`：喜剧、搞笑、荒诞、无厘头。
- `adventurous`：冒险、热血、成长、挑战。

## 输出要求

- 只依据对话中已经出现的信息判断，不要补完或猜测。
- 如果信息不足以判断，输出 `unknown`。
- 只输出一个枚举值：`serious`、`lighthearted`、`dark`、`comedic`、`adventurous` 或 `unknown`。
- 不要输出解释文字、markdown 代码块、标点或额外内容。
