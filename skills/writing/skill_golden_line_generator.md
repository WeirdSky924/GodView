---
id: skill_golden_line_generator
name: 金句生成
description: 为章节生成适合引用传播的金句
category: writing
skill_type: prompt
tags:
  - 金句
  - 名句
  - 传播
use_cases:
  - 生成经典语录
  - 提升文笔亮点
  - 增强传播性
applicable_agent_types:
  - writer
load_mode: on_demand
priority: 70
is_system: true
is_enabled: true
parameters:
  - name: context
    type: string
    description: 场景/对话上下文
    required: true
  - name: emotion
    type: string
    description: 情感基调
---

# 金句生成技能

## 任务：金句生成

请根据以下内容生成金句：

### 场景/对话上下文

{{context}}

### 情感基调

{{emotion}}

### 金句要求

1. **简洁有力**：一般不超过20字
2. **含义深刻**：有哲理或情感共鸣
3. **朗朗上口**：易于记忆和传播
4. **符合语境**：自然融入情节

### 金句类型

#### 1. 人生哲理型

关于人生、成长的感悟

#### 2. 情感共鸣型

触动情感的表白或内心独白

#### 3. 霸气宣言型

展现人物决心或气势

#### 4. 幽默机智型

风趣幽默的妙语

#### 5. 诗意唯美型

意境优美的描述

### 输出格式（JSON）

```json
{
  "golden_lines": [
    {"content": "金句内容", "type": "类型", "context": "适用场景"}
  ],
  "recommended": "最推荐的金句",
  "insertion_hint": "建议插入位置"
}
```
