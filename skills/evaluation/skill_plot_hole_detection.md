---
id: skill_plot_hole_detection
name: 剧情漏洞检测
description: 检测剧情中的逻辑漏洞、前后矛盾和不合理之处
category: evaluation
skill_type: prompt
tags:
  - 剧情
  - 漏洞
  - 逻辑
use_cases:
  - 检测逻辑漏洞
  - 识别前后矛盾
  - 发现不合理情节
applicable_agent_types:
  - evaluator
load_mode: on_demand
priority: 95
is_system: true
is_enabled: true
parameters:
  - name: chapter_content
    type: string
    description: 章节内容
    required: true
  - name: story_context
    type: string
    description: 已有故事背景
---

# 剧情漏洞检测技能

## 任务：剧情漏洞检测

请检测以下内容中的剧情漏洞：

### 章节内容

{{chapter_content}}

### 已有故事背景

{{story_context}}

### 检测类型

#### 1. 逻辑漏洞

- 因果关系不合理
- 行为动机缺失
- 结果与前提矛盾

#### 2. 前后矛盾

- 与前文设定冲突
- 时间线混乱
- 人物状态不一致

#### 3. 设定冲突

- 违反世界观规则
- 能力体系问题
- 地理/时间错误

#### 4. 信息缺失

- 关键信息未交代
- 角色行为缺少铺垫
- 转折缺乏支撑

### 输出格式（JSON）

```json
{
  "plot_holes": [
    {"type": "逻辑漏洞", "location": "位置", "description": "描述", "severity": "严重程度", "suggestion": "修复建议"}
  ],
  "severity_count": {"critical": 0, "major": 1, "minor": 2},
  "overall_score": 90,
  "needs_fix": true/false,
  "fix_priorities": ["优先修复的问题"]
}
```
