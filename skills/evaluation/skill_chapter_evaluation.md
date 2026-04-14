---
id: skill_chapter_evaluation
name: 章节质量评估
description: 从多个维度评估章节内容质量
category: evaluation
skill_type: prompt
tags:
  - 评估
  - 质量
  - 章节
use_cases:
  - 评估章节质量
  - 识别内容问题
  - 提供改进建议
applicable_agent_types:
  - evaluator
load_mode: on_demand
priority: 80
is_system: true
is_enabled: true
parameters:
  - name: chapter_content
    type: string
    description: 章节内容
    required: true
  - name: target_words
    type: number
    description: 目标字数
  - name: chapter_number
    type: number
    description: 章节序号
  - name: is_first_chapter
    type: boolean
    description: 是否第一章
output_spec:
  - name: total_score
    type: number
  - name: word_count_check
    type: object
  - name: coherence_check
    type: object
  - name: dimensions
    type: object
  - name: strengths
    type: array
  - name: weaknesses
    type: array
  - name: critical_issues
    type: array
  - name: suggestions
    type: array
  - name: conclusion
    type: string
---

# 章节质量评估技能

## 任务：章节质量评估

请评估以下章节内容的质量：

### 章节内容

{{chapter_content}}

### 评估背景

- 目标字数：{{target_words}}
- 章节序号：第 {{chapter_number}} 章
- 是否第一章：{{is_first_chapter}}

### 评估维度

#### 1. 字数达标（必要项）

- 实际字数是否达标
- 未达标则直接打回

#### 2. 前文连贯（重要项）

- 与前文是否自然衔接
- 人物状态是否一致
- 时间线是否连贯

#### 3. 情节质量（25分）

- 逻辑性：事件发展是否合理
- 吸引力：是否引人入胜
- 节奏感：张弛是否适度

#### 4. 人物塑造（25分）

- 一致性：行为是否符合性格
- 立体感：人物是否丰满
- 对话质量：对话是否自然

#### 5. 语言表达（25分）

- 流畅度：语言是否流畅
- 表现力：描写是否生动
- 准确性：有无语法错误

#### 6. 整体效果（25分）

- 可读性：是否容易阅读
- 感染力：是否能打动读者
- 完整性：是否有明显缺失

### 评分标准

- **8-10分**：优秀，通过
- **6-7分**：良好，小问题，通过但建议优化
- **4-5分**：一般，需要修改后重新评估
- **1-3分**：不合格，需要大幅修改或重写

### 输出格式（JSON）

```json
{
  "total_score": 85,
  "word_count_check": {"actual": 2800, "target": 3000, "passed": true},
  "coherence_check": {"score": 90, "issues": []},
  "dimensions": {
    "plot": {"score": 22, "comment": "评价"},
    "character": {"score": 20, "comment": "评价"},
    "language": {"score": 23, "comment": "评价"},
    "overall": {"score": 20, "comment": "评价"}
  },
  "strengths": ["优点"],
  "weaknesses": ["不足"],
  "critical_issues": ["必须修改的问题"],
  "suggestions": ["改进建议"],
  "conclusion": "通过/需修改/需重写"
}
```
