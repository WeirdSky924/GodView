---
id: function_setting_world_type_inference
name: Setting 世界类型推断
description: 从设定对话历史中推断故事世界类型，只输出稳定枚举值
category: instruction
tags:
  - function
  - setting
  - inference
  - world-type
use_cases:
  - 世界类型推断
  - 项目初始化辅助
  - 设定会话元数据提取
applies_to:
  - setting
priority: 80
is_system: true
---

# Setting 世界类型推断

请从输入的设定对话中推断故事的世界类型。

## 可选类型

- `fantasy`：奇幻、魔法、精灵、怪物、异世界。
- `scifi`：科幻、太空、未来科技、外星人、赛博朋克。
- `modern`：现代、当代社会、都市、现实题材。
- `historical`：历史、古代或近代历史背景。
- `wuxia`：武侠、江湖、武功、门派、恩怨。

## 输出要求

- 只依据对话中已经出现的信息判断，不要补完或猜测。
- 如果信息不足以判断，输出 `unknown`。
- 只输出一个枚举值：`fantasy`、`scifi`、`modern`、`historical`、`wuxia` 或 `unknown`。
- 不要输出解释文字、markdown 代码块、标点或额外内容。
