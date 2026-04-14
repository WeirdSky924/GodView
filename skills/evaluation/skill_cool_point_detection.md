---
id: skill_cool_point_detection
name: 爽点检测分析
description: 检测章节中的爽点设计是否合理有效
category: evaluation
skill_type: prompt
tags:
  - 爽点
  - 检测
  - 网文
use_cases:
  - 检测爽点设计
  - 评估爽点效果
  - 优化爽点分布
applicable_agent_types:
  - writer
  - evaluator
load_mode: on_demand
priority: 90
is_system: true
is_enabled: true
parameters:
  - name: chapter_content
    type: string
    description: 章节内容
    required: true
---

# 爽点检测分析技能

## 任务：爽点检测分析

请分析以下内容中的爽点设计：

### 章节内容

{{chapter_content}}

### 爽点类型

#### 1. 打脸爽

被轻视后反击

#### 2. 升级爽

实力提升、获得宝物

#### 3. 逆袭爽

绝境翻盘

#### 4. 装逼爽

低调装逼、扮猪吃虎

#### 5. 复仇爽

报仇雪恨

#### 6. 收获爽

获得认可、奖励

#### 7. 解气爽

恶人受惩

#### 8. 揭秘爽

真相大白

### 分析要求

#### 1. 爽点识别

- 找出所有爽点
- 分析爽点类型
- 评估爽点强度

#### 2. 爽点质量

- 铺垫是否充分
- 释放是否到位
- 节奏是否合理

#### 3. 爽点分布

- 密度是否适中
- 是否有疲劳感
- 是否有期待感

### 输出格式（JSON）

```json
{
  "cool_points": [
    {"type": "打脸爽", "location": "第X段", "intensity": "高", "quality": "优秀", "setup": "铺垫情况", "payoff": "释放情况"}
  ],
  "overall_score": 85,
  "distribution": {"density": "适中", "balance": "合理"},
  "suggestions": ["建议"]
}
```
