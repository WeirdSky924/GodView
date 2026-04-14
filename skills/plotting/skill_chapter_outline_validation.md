---
id: skill_chapter_outline_validation
name: 章节大纲验证
description: 验证章节大纲的合理性和可执行性
category: analysis
skill_type: prompt
tags:
  - 大纲
  - 验证
  - 检查
use_cases:
  - 验证大纲合理性
  - 检查大纲完整性
  - 识别大纲问题
applicable_agent_types:
  - plot_outline
load_mode: on_demand
priority: 75
is_system: true
is_enabled: true
parameters:
  - name: chapter_outline
    type: object
    description: 章节大纲JSON
    required: true
---

# 章节大纲验证技能

## 任务：章节大纲验证

请验证以下章节大纲的合理性：

### 章节大纲

{{chapter_outline}}

### 验证维度

#### 1. 逻辑验证

- 情节发展是否合理
- 因果关系是否清晰
- 与前文是否衔接

#### 2. 字数验证

- 各段字数分配是否合理
- 总字数是否达标
- 高潮部分是否有足够篇幅

#### 3. 情绪验证

- 情绪曲线是否合理
- 是否有足够的起伏
- 结尾情绪是否恰当

#### 4. 可行性验证

- 大纲是否可执行
- 是否过于抽象
- 是否缺少关键信息

### 输出格式（JSON）

```json
{
  "is_valid": true/false,
  "score": 85,
  "issues": [{"type": "问题类型", "description": "问题描述", "segment_index": 1}],
  "suggestions": ["改进建议"],
  "missing_info": ["缺失信息"]
}
```
