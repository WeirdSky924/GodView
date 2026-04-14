---
id: skill_volume_planning
name: 卷规划
description: 规划故事分卷结构和各卷内容
category: plotting
skill_type: prompt
tags:
  - 分卷
  - 结构
  - 规划
use_cases:
  - 规划分卷结构
  - 设计各卷主题
  - 安排故事节奏
applicable_agent_types:
  - plot_outline
load_mode: on_demand
priority: 80
is_system: true
is_enabled: true
parameters:
  - name: story_summary
    type: string
    description: 故事概要
  - name: total_words
    type: number
    description: 预计总字数
---

# 卷规划技能

## 任务：卷规划

请规划故事的分卷结构：

### 故事概要

{{story_summary}}

### 预计总字数

{{total_words}}

### 卷规划原则

#### 1. 分卷逻辑

- 每卷有独立的主题或阶段
- 卷与卷之间有承接关系
- 每卷有起承转合

#### 2. 内容分配

- 主线发展节奏
- 支线穿插安排
- 高潮点分布

#### 3. 篇幅控制

- 各卷字数分配
- 章节数量规划
- 节奏密度设计

### 分卷类型

#### 1. 地点型

按故事发生地点分卷

#### 2. 时间型

按时间阶段分卷

#### 3. 事件型

按核心事件分卷

#### 4. 成长型

按主角成长阶段分卷

### 输出格式（JSON）

```json
{
  "total_volumes": 3,
  "volumes": [
    {
      "number": 1,
      "title": "卷名",
      "theme": "主题",
      "chapters": "第1-30章",
      "target_words": 100000,
      "summary": "本卷概要",
      "climax": "高潮事件",
      "ending_state": "卷末状态"
    }
  ],
  "main_arc": "主线发展轨迹",
  "milestones": [{"volume": 1, "event": "里程碑事件"}]
}
```
