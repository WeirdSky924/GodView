---
id: skill_plot_planning
name: 剧情规划
description: 规划故事剧情发展和章节安排的核心技能
category: plotting
skill_type: prompt
tags:
  - 剧情
  - 规划
  - 大纲
use_cases:
  - 规划故事主线
  - 设计情节转折
  - 安排章节节奏
applicable_agent_types:
  - master_plotter
load_mode: on_demand
priority: 80
is_system: true
is_enabled: true
parameters:
  - name: story_background
    type: string
    description: 故事背景
  - name: current_chapter
    type: number
    description: 当前章节
  - name: completed_plots
    type: array
    description: 已完成情节
  - name: active_hooks
    type: array
    description: 活跃伏笔
  - name: planning_goal
    type: string
    description: 规划目标
output_spec:
  - name: story_arc
    type: object
  - name: chapters
    type: array
  - name: turning_points
    type: array
  - name: foreshadowing_plan
    type: object
---

# 剧情规划技能

## 任务：剧情规划

请根据以下信息规划剧情发展：

### 故事背景

{{story_background}}

### 当前状态

- 当前章节：第 {{current_chapter}} 章
- 已完成情节：{{completed_plots}}
- 活跃伏笔：{{active_hooks}}

### 规划目标

{{planning_goal}}

### 规划要求

#### 1. 整体架构

- 确定故事的主线走向
- 规划主要转折点
- 设计高潮和结局

#### 2. 章节安排

- 每章的核心事件
- 情绪曲线设计
- 信息披露节奏

#### 3. 伏笔布局

- 新伏笔的埋设计划
- 旧伏笔的回收时机
- 伏笔之间的关联

#### 4. 角色发展

- 主角的成长路径
- 配角的故事线
- 关系变化节点

### 输出格式（JSON）

```json
{
  "story_arc": {
    "current_phase": "当前阶段",
    "next_phase": "下一阶段",
    "main_conflict": "核心冲突"
  },
  "chapters": [
    {"number": 1, "title": "章节名", "core_event": "核心事件", "emotion": "情绪基调", "hooks": ["涉及伏笔"]}
  ],
  "turning_points": [{"chapter": 10, "event": "转折事件", "impact": "影响"}],
  "foreshadowing_plan": {"new": [], "resolve": []}
}
```
