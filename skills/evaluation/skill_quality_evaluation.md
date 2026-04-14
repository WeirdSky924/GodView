---
id: skill_quality_evaluation
name: 内容质量评估
description: 对生成的内容进行多维度质量评估，支持阈值检查和自动重试建议
category: evaluation
skill_type: prompt
tags:
  - 评估
  - 质量检查
  - 阈值
use_cases:
  - 评估大纲质量
  - 检查章节内容
  - 验证角色一致性
applicable_agent_types:
  - evaluator
load_mode: on_demand
priority: 85
is_system: true
is_enabled: true
use_agent_memory: true
memory_types:
  - decision
  - observation
reads_global_state:
  - evaluation_history
  - quality_trends
writes_global_state:
  - latest_evaluation
  - quality_alerts
parameters:
  - name: content_type
    type: string
    description: 内容类型 (outline/chapter/character_dialogue)
    required: true
  - name: content
    type: object
    description: 待评估的内容
    required: true
  - name: evaluation_dimensions
    type: array
    description: 评估维度列表
    default: ["quality", "consistency", "stance"]
  - name: threshold_config
    type: object
    description: 阈值配置（覆盖默认设置）
output_spec:
  - name: overall_score
    type: number
    required: true
  - name: dimension_scores
    type: object
    required: true
  - name: passed
    type: boolean
    required: true
  - name: issues
    type: array
    required: true
  - name: suggestions
    type: array
    required: true
  - name: retry_recommended
    type: boolean
evaluation_threshold:
  min_score: 0.7
  blocking: true
  auto_retry: true
  max_retries: 2
  retry_strategy: improve
  dimensions:
    - quality
    - consistency
    - stance_check
  dimension_weights:
    quality: 0.4
    consistency: 0.3
    stance_check: 0.3
---

# 内容质量评估技能

## 任务：质量评估

请对以下内容进行多维度质量评估。

### 评估配置

- 内容类型：{{content_type}}
- 评估维度：{{evaluation_dimensions}}
- 阈值配置：{{threshold_config}}

### 待评估内容

```
{{content}}
```

---

## 一、评估维度定义

### 1. 质量维度 (quality)

| 指标 | 说明 | 评分标准 |
|------|------|----------|
| 完整性 | 内容是否完整，无遗漏 | 1-10 分 |
| 连贯性 | 逻辑是否通顺 | 1-10 分 |
| 生动性 | 描写是否生动有趣 | 1-10 分 |
| 节奏感 | 叙事节奏是否恰当 | 1-10 分 |

### 2. 一致性维度 (consistency)

| 指标 | 说明 | 评分标准 |
|------|------|----------|
| 角色一致性 | 角色行为是否符合设定 | 1-10 分 |
| 设定一致性 | 是否与世界观设定矛盾 | 1-10 分 |
| 剧情一致性 | 是否与前后文衔接 | 1-10 分 |

### 3. 立场检查维度 (stance_check)

| 指标 | 说明 | 评分标准 |
|------|------|----------|
| 反派行为 | 反派是否符合敌对立场 | 1-10 分 |
| 角色动机 | 行为是否有合理动机 | 1-10 分 |
| 立场标注 | 是否正确标注角色立场 | 1-10 分 |

---

## 二、评估方法

### 步骤 1：逐维度评分

对每个维度：
1. 检查内容是否符合该维度的要求
2. 记录发现的问题
3. 给出 0.0-1.0 的分数

### 步骤 2：加权总分

```
总分 = Σ (维度分数 × 权重)
```

### 步骤 3：问题归类

将问题分为：
- **阻断性问题** (blocking): 必须修复才能通过
- **警告性问题** (warning): 建议修复
- **建议性问题** (suggestion): 可选优化

### 步骤 4：重试建议

如果未通过阈值，建议：
- 需要重新生成的部分
- 具体的改进方向
- 预估的重试策略

---

## 三、输出格式

```json
{
  "overall_score": 0.75,
  "passed": true,

  "dimension_scores": {
    "quality": {
      "score": 0.8,
      "breakdown": {
        "completeness": 9,
        "coherence": 8,
        "vividness": 7,
        "pacing": 8
      }
    },
    "consistency": {
      "score": 0.75,
      "breakdown": {
        "character_consistency": 8,
        "setting_consistency": 7,
        "plot_consistency": 8
      }
    },
    "stance_check": {
      "score": 0.7,
      "breakdown": {
        "villain_behavior": 7,
        "character_motivation": 7,
        "stance_labeling": 7
      }
    }
  },

  "issues": [
    {
      "type": "warning",
      "dimension": "stance_check",
      "description": "反派角色'黑衣人'在场景3中过于轻易地放过了主角",
      "location": "场景3结尾",
      "suggested_fix": "添加反派的自私动机，如想借主角找到更大的目标"
    }
  ],

  "suggestions": [
    "建议加强反派角色'黑衣人'的行为动机描写",
    "场景2的节奏可以稍作加快"
  ],

  "retry_recommended": false,
  "retry_strategy": null,

  "evaluation_metadata": {
    "evaluated_at": "{{current_time}}",
    "threshold_used": 0.7,
    "dimensions_evaluated": ["quality", "consistency", "stance_check"]
  }
}
```

---

## 四、特殊情况处理

### 情况 1：反派行为明显不合理

```
如果 stance_check.villain_behavior < 0.6:
    - 标记为阻断性问题
    - 必须重试
    - 提供具体的修正建议
```

### 情况 2：内容不完整

```
如果 quality.completeness < 0.5:
    - 标记为阻断性问题
    - 列出缺失的必要元素
    - 建议重新生成
```

### 情况 3：与设定冲突

```
如果 consistency.setting_consistency < 0.7:
    - 标记为警告性问题
    - 列出具体冲突点
    - 提供修正方案
```

---

## 五、与阈值系统集成

### 阈值配置读取

从 `evaluation_threshold` 参数或技能默认配置读取：

```json
{
  "min_score": 0.7,
  "blocking": true,
  "auto_retry": true,
  "max_retries": 2,
  "retry_strategy": "improve"
}
```

### 通过条件

```
passed = overall_score >= min_score
     AND 所有阻断性问题数量 == 0
```

### 重试建议

```
if not passed and auto_retry:
    retry_recommended = true
    retry_strategy = 计算最佳策略
    retry_focus = 需要重点改进的维度
```

---

## 六、自检清单

评估完成后，确认：

```
[ ] 所有维度都已评分？
[ ] 分数计算是否正确？
[ ] 问题是否已详细记录？
[ ] 阻断性问题是否正确标记？
[ ] 重试建议是否合理？
[ ] 输出格式是否正确？
```
