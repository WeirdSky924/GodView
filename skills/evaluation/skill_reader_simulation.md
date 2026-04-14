---
id: skill_reader_simulation
name: 读者模拟评分
description: 模拟目标读者群体对内容的反应和评分
category: evaluation
skill_type: prompt
tags:
  - 读者
  - 模拟
  - 评分
use_cases:
  - 模拟读者反应
  - 预测阅读体验
  - 评估吸引力
applicable_agent_types:
  - evaluator
load_mode: on_demand
priority: 70
is_system: true
is_enabled: true
parameters:
  - name: chapter_content
    type: string
    description: 章节内容
    required: true
  - name: target_audience
    type: string
    description: 目标读者群体
  - name: genre
    type: string
    description: 作品类型
---

# 读者模拟评分技能

## 任务：读者模拟评分

请模拟目标读者对以下内容的反应：

### 章节内容

{{chapter_content}}

### 目标读者群体

{{target_audience}}

### 作品类型

{{genre}}

### 模拟维度

#### 1. 吸引力模拟

- 开篇是否想继续看
- 是否有"放不下来"的感觉
- 是否有无聊想跳过的部分

#### 2. 情感反应模拟

- 哪些地方会感动
- 哪些地方会紧张
- 哪些地方会期待

#### 3. 认知反应模拟

- 是否能理解剧情
- 是否有困惑的地方
- 信息是否足够

#### 4. 行为预测模拟

- 是否会追更
- 是否会推荐给朋友
- 是否会打赏/投票

### 读者类型

- **核心读者**：该类型的忠实粉丝
- **普通读者**：有阅读习惯的读者
- **潜在读者**：可能被吸引的新读者

### 输出格式（JSON）

```json
{
  "reader_scores": {
    "core_reader": {"score": 90, "reaction": "反应描述", "would_continue": true},
    "regular_reader": {"score": 85, "reaction": "反应描述", "would_continue": true},
    "potential_reader": {"score": 80, "reaction": "反应描述", "would_continue": false}
  },
  "emotional_peaks": [{"position": "位置", "emotion": "情绪", "intensity": "强度"}],
  "boring_parts": [{"position": "位置", "reason": "原因"}],
  "confusing_parts": [{"position": "位置", "issue": "困惑点"}],
  "overall_prediction": {"would_recommend": true, "would_vote": true, "completion_likelihood": "高"},
  "suggestions": ["改进建议"]
}
```
