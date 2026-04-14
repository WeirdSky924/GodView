---
id: skill_plot_advancement
name: 剧情推进评估
description: 评估剧情推进效果，判断是否需要调整节奏
category: analysis
skill_type: prompt
tags:
  - 剧情
  - 推进
  - 评估
use_cases:
  - 评估剧情节奏
  - 识别剧情问题
  - 提供调整建议
applicable_agent_types:
  - master_plotter
load_mode: on_demand
priority: 70
is_system: true
is_enabled: true
parameters:
  - name: content_to_evaluate
    type: string
    description: 评估内容
    required: true
---

# 剧情推进评估技能

## 任务：剧情推进评估

请评估当前剧情推进情况：

### 评估内容

{{content_to_evaluate}}

### 评估维度

#### 1. 节奏评估

- 剧情推进是否过快/过慢
- 高潮和缓冲是否合理分布
- 读者可能感到无聊的地方

#### 2. 逻辑评估

- 情节发展是否合理
- 因果关系是否清晰
- 是否有逻辑漏洞

#### 3. 吸引力评估

- 是否能保持读者兴趣
- 是否有足够的悬念
- 是否有意外惊喜

#### 4. 一致性评估

- 与大纲是否一致
- 人物行为是否合理
- 设定是否冲突

### 输出格式（JSON）

```json
{
  "overall_score": 85,
  "dimensions": {
    "pacing": {"score": 90, "comment": "评价"},
    "logic": {"score": 85, "comment": "评价"},
    "attraction": {"score": 80, "comment": "评价"},
    "consistency": {"score": 85, "comment": "评价"}
  },
  "issues": ["问题1", "问题2"],
  "suggestions": ["建议1", "建议2"],
  "adjustment_needed": true/false
}
```
