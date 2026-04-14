---
id: skill_opening_design
name: 开局设计
description: 设计小说开篇，确保前三章能够吸引读者
category: plotting
skill_type: prompt
tags:
  - 开篇
  - 黄金三章
  - 吸引
use_cases:
  - 设计开篇布局
  - 规划黄金三章
  - 确保开篇吸引力
applicable_agent_types:
  - plot_outline
load_mode: on_demand
priority: 85
is_system: true
is_enabled: true
parameters:
  - name: story_setting
    type: string
    description: 故事设定
  - name: protagonist_info
    type: object
    description: 主角信息
---

# 开局设计技能

## 任务：开局设计

请设计小说的开篇布局（黄金三章）：

### 故事设定

{{story_setting}}

### 主角信息

{{protagonist_info}}

### 开局设计原则

#### 1. 第一章：吸引入场

- 前100字抓住注意力
- 展示主角核心特点
- 制造悬念或冲突
- 世界观自然呈现

#### 2. 第二章：深化兴趣

- 扩展主角困境
- 引入关键配角
- 揭示核心设定
- 推进主线剧情

#### 3. 第三章：确立期待

- 明确故事方向
- 展现核心卖点
- 建立情感连接
- 让读者决定追更

### 常见开局类型

#### 1. 冲突开局

直接进入冲突场景

#### 2. 悬念开局

制造谜团引发好奇

#### 3. 日常开局

从平凡切入，形成对比

#### 4. 高光开局

展示主角高光时刻

### 输出格式（JSON）

```json
{
  "opening_type": "开局类型",
  "chapters": [
    {
      "number": 1,
      "title": "章节标题",
      "opening_line": "开篇第一句",
      "core_event": "核心事件",
      "hooks": ["悬念点"],
      "character_intro": ["人物登场"]
    }
  ],
  "key_points": ["关键卖点"],
  "world_reveal_plan": "世界观呈现方式"
}
```
