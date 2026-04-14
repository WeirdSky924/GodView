---
id: skill_pacing_analysis
name: 节奏分析
description: 分析章节的叙事节奏是否合理
category: analysis
skill_type: prompt
tags:
  - 节奏
  - 叙事
  - 分析
use_cases:
  - 分析叙事节奏
  - 评估信息密度
  - 优化阅读体验
applicable_agent_types:
  - master_plotter
  - evaluator
load_mode: on_demand
priority: 75
is_system: true
is_enabled: true
parameters:
  - name: chapter_content
    type: string
    description: 章节内容
    required: true
---

# 节奏分析技能

## 任务：节奏分析

请分析以下内容的叙事节奏：

### 章节内容

{{chapter_content}}

### 分析维度

#### 1. 信息节奏

- 信息密度是否适中
- 重要信息是否突出
- 是否有信息过载

#### 2. 情绪节奏

- 情绪曲线是否合理
- 高潮位置是否恰当
- 缓冲是否足够

#### 3. 段落节奏

- 段落长短是否变化
- 切换是否自然
- 重点是否突出

#### 4. 句子节奏

- 长短句是否交替
- 节奏感如何
- 是否有单调感

### 输出格式（JSON）

```json
{
  "overall_pacing": {"score": 85, "level": "良好"},
  "dimensions": {
    "information": {"score": 90, "comment": "评价"},
    "emotion": {"score": 80, "comment": "评价"},
    "paragraph": {"score": 85, "comment": "评价"},
    "sentence": {"score": 85, "comment": "评价"}
  },
  "rhythm_curve": [{"position": "25%", "intensity": "中"}, {"position": "50%", "intensity": "高"}, {"position": "75%", "intensity": "低"}],
  "suggestions": ["节奏优化建议"]
}
```
