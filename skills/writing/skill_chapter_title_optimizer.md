---
id: skill_chapter_title_optimizer
name: 章节标题优化
description: 优化章节标题，使其更吸引读者
category: writing
skill_type: prompt
tags:
  - 标题
  - 优化
  - 吸引
use_cases:
  - 优化章节标题
  - 生成备选标题
applicable_agent_types:
  - writer
load_mode: on_demand
priority: 65
is_system: true
is_enabled: true
parameters:
  - name: chapter_summary
    type: string
    description: 章节内容摘要
    required: true
  - name: current_title
    type: string
    description: 当前标题
---

# 章节标题优化技能

## 任务：章节标题优化

请为以下章节优化标题：

### 章节内容摘要

{{chapter_summary}}

### 当前标题

{{current_title}}

### 标题优化原则

1. **信息量**：透露关键信息但不剧透
2. **吸引力**：让读者想点进去看
3. **风格统一**：与作品整体风格一致
4. **简洁有力**：一般不超过10个字

### 标题类型

#### 1. 人物型

突出角色名或身份

#### 2. 事件型

描述关键事件

#### 3. 悬念型

制造疑问

#### 4. 意象型

使用象征或比喻

#### 5. 引用型

引用名句或诗词

### 输出格式（JSON）

```json
{
  "recommended_title": "推荐标题",
  "alternatives": ["备选1", "备选2", "备选3"],
  "title_type": "标题类型",
  "reason": "推荐理由"
}
```
