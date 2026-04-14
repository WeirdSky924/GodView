---
id: skill_golden_three_chapters
name: 黄金三章检测
description: 检测小说开篇三章是否符合黄金三章标准
category: evaluation
skill_type: prompt
tags:
  - 黄金三章
  - 开篇
  - 吸引
use_cases:
  - 检测开篇质量
  - 评估吸引力
  - 优化开篇设计
applicable_agent_types:
  - evaluator
load_mode: on_demand
priority: 85
is_system: true
is_enabled: true
parameters:
  - name: first_three_chapters
    type: string
    description: 前三章内容
    required: true
---

# 黄金三章检测技能

## 任务：黄金三章检测

请检测开篇三章是否符合黄金三章标准：

### 前三章内容

{{first_three_chapters}}

### 检测维度

#### 1. 第一章检测

- 开篇100字是否抓住注意力
- 主角是否有清晰亮相
- 是否有悬念/钩子
- 世界观呈现是否自然

#### 2. 第二章检测

- 是否深化读者兴趣
- 冲突/困境是否展开
- 关键配角是否引入
- 核心设定是否揭示

#### 3. 第三章检测

- 故事方向是否明确
- 核心卖点是否展现
- 情感连接是否建立
- 读者是否想继续看

#### 4. 整体检测

- 三章是否形成完整体验
- 节奏是否流畅
- 是否有让人追更的欲望

### 输出格式（JSON）

```json
{
  "overall_score": 85,
  "chapters": [
    {"number": 1, "score": 90, "strengths": ["优点"], "issues": ["问题"], "suggestions": ["建议"]}
  ],
  "golden_rules_checked": {
    "attention_grabbing": true,
    "protagonist_clear": true,
    "hook_present": true,
    "world_natural": true,
    "direction_clear": true,
    "want_to_read_more": true
  },
  "improvement_priorities": ["优先改进项"]
}
```
