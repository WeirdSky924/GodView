---
id: skill_complete_chapter_planning
name: 完整章节规划
description: 复合技能，组合大纲生成、爽点设计、钩子设计和反派动态，生成完整的章节规划
category: plotting
skill_type: workflow
tags:
  - 章节
  - 规划
  - 复合技能
use_cases:
  - 生成完整的章节规划方案
  - 协调多个子技能输出
applicable_agent_types:
  - plot_outline
  - master_plotter
load_mode: on_demand
priority: 88
is_system: true
is_enabled: true
use_agent_memory: true
memory_types:
  - decision
  - observation
reads_global_state:
  - main_plot_progress
  - active_hooks
  - villain_threat_level
  - planned_cool_points
writes_global_state:
  - chapter_plans
  - active_hooks
  - villain_threat_level
parameters:
  - name: chapter_number
    type: number
    description: 章节序号
    required: true
  - name: chapter_title
    type: string
    description: 章节标题
  - name: target_words
    type: number
    description: 目标字数
    default: 3000
  - name: story_context
    type: object
    description: 完整故事上下文
    required: true
  - name: chapter_goal
    type: string
    description: 本章目标
  - name: villain_presence
    type: object
    description: 反派出场信息（可选）
output_spec:
  - name: chapter_outline
    type: object
    required: true
  - name: cool_points
    type: array
    required: true
  - name: hooks
    type: object
    required: true
  - name: villain_arc
    type: object
  - name: quality_check
    type: object
    required: true
sub_skills:
  - skill_id: skill_chapter_outline_generation
    slot_name: outline
    execution_order: 1
    pass_output_to: chapter_outline
    is_required: true
  - skill_id: skill_webnovel_cool_points
    slot_name: cool_points
    execution_order: 2
    pass_output_to: cool_points_design
    is_required: true
  - skill_id: skill_chapter_hooks_design
    slot_name: hooks
    execution_order: 3
    pass_output_to: hooks_design
    is_required: true
  - skill_id: skill_chapter_villain_arc
    slot_name: villain
    execution_order: 4
    pass_output_to: villain_arc
    is_required: false
evaluation_threshold:
  min_score: 0.7
  blocking: true
  auto_retry: true
  max_retries: 2
  retry_strategy: improve
  dimensions:
    - completeness
    - consistency
    - stance_check
  dimension_weights:
    completeness: 0.4
    consistency: 0.3
    stance_check: 0.3
on_failure_action: retry
---

# 完整章节规划技能（复合技能）

## 技能说明

这是一个**复合技能**，它将章节规划的多个步骤分解为独立的子技能，按顺序执行并组合输出。

### 子技能执行流程

```
┌─────────────────────────────────────────────────────────┐
│  输入: 章节编号、标题、目标、上下文                        │
└────────────────────────┬────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│  子技能 1: 章节大纲生成 (skill_chapter_outline_generation) │
│  输出: 章节大纲 (scenes, emotion_curve, chapter_goals)    │
└────────────────────────┬────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│  子技能 2: 爽点设计 (skill_webnovel_cool_points)          │
│  输入: 章节大纲                                         │
│  输出: 爽点设计方案                                      │
└────────────────────────┬────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│  子技能 3: 钩子设计 (skill_chapter_hooks_design)          │
│  输入: 章节大纲 + 爽点设计                               │
│  输出: 开篇钩子、结尾钩子                                │
└────────────────────────┬────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│  子技能 4: 反派动态 (skill_chapter_villain_arc) [可选]    │
│  条件: 有反派出场                                       │
│  输出: 反派行动、威胁变化                                │
└────────────────────────┬────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│  组装输出 + 质量检查                                    │
│  输出: 完整章节规划方案                                  │
└─────────────────────────────────────────────────────────┘
```

---

## 执行规范

### 1. 输入准备

将用户输入转换为各子技能需要的格式：

```json
{
  "chapter_number": 10,
  "chapter_title": "暗夜追踪",
  "target_words": 3000,
  "story_context": {
    "project_metadata": {...},
    "characters": [...],
    "world_settings": {...},
    "active_hooks": [...],
    "previous_outlines": [...]
  },
  "chapter_goal": "主角发现敌人的踪迹，但陷入陷阱",
  "villain_presence": {
    "villain_name": "黑衣人",
    "current_threat_level": "medium",
    "suggested_action": "暗中观察"
  }
}
```

### 2. 子技能 1：章节大纲生成

**调用参数**：
```json
{
  "chapter_number": 10,
  "chapter_title": "暗夜追踪",
  "target_words": 3000,
  "story_context": "...",
  "chapter_goal": "..."
}
```

**输出传递给下一子技能**：
- `chapter_outline.scenes` → 传递给爽点设计
- `chapter_outline.emotion_curve` → 传递给钩子设计

### 3. 子技能 2：爽点设计

**调用参数**：
```json
{
  "chapter_context": {
    "scenes": [...],
    "emotion_curve": {...},
    "chapter_goal": "..."
  },
  "available_characters": ["主角", "配角A"],
  "previous_cool_points": []
}
```

### 4. 子技能 3：钩子设计

**调用参数**：
```json
{
  "chapter_context": {...},
  "previous_ending_hook": "上一章结尾钩子内容",
  "story_progress": 0.35
}
```

### 5. 子技能 4：反派动态（条件执行）

**执行条件**：`villain_presence` 参数不为空

**调用参数**：
```json
{
  "villain_info": {...},
  "chapter_context": {...},
  "protagonist_actions": [...]
}
```

### 6. 输出组装

```json
{
  "chapter_outline": {
    "title": "暗夜追踪",
    "scenes": [...],
    "emotion_curve": {...},
    "chapter_goals": [...]
  },
  "cool_points": [
    {
      "type": "逆袭",
      "position": "场景3",
      "design": {...}
    }
  ],
  "hooks": {
    "opening": {...},
    "ending": {...}
  },
  "villain_arc": {
    "appearing": true,
    "chapter_actions": [...],
    "threat_change": "increased"
  },
  "quality_check": {
    "passed": true,
    "overall_score": 0.82,
    "issues": []
  },
  "global_state_updates": {
    "active_hooks": ["新钩子ID"],
    "villain_threat_level": "high"
  }
}
```

---

## 错误处理

### 子技能执行失败

```
if 子技能执行失败:
    if 子技能.is_required:
        整体失败，返回错误信息
    else:
        跳过该子技能，继续执行后续
```

### 质量检查未通过

```
if quality_check.passed == false:
    if evaluation_threshold.auto_retry:
        重试失败的子技能
    else:
        返回结果，标记为"需要修改"
```

---

## 与全局状态集成

### 读取的状态

| 状态键 | 用途 |
|--------|------|
| `main_plot_progress` | 确定当前进度 |
| `active_hooks` | 获取现有伏笔 |
| `villain_threat_level` | 反派威胁等级 |
| `planned_cool_points` | 已规划的爽点 |

### 写入的状态

| 状态键 | 更新内容 |
|--------|----------|
| `chapter_plans` | 新增章节规划 |
| `active_hooks` | 新增/更新钩子 |
| `villain_threat_level` | 更新威胁等级 |

---

## 与记忆系统集成

### 执行前

加载 Agent 的历史决策和观察：
- 之前章节的规划决策
- 读者反馈观察
- 质量评估历史

### 执行后

记录本次执行的：
- 规划决策
- 遇到的问题
- 调整过程
