---
id: skill_setting_conflict_detection
name: 设定冲突检测
description: 检测内容是否与已有世界观设定冲突
category: evaluation
skill_type: prompt
tags:
  - 设定
  - 冲突
  - 世界观
use_cases:
  - 检测设定冲突
  - 验证世界观一致性
  - 发现设定问题
applicable_agent_types:
  - evaluator
  - setting
load_mode: on_demand
priority: 85
is_system: true
is_enabled: true
parameters:
  - name: chapter_content
    type: string
    description: 章节内容
    required: true
  - name: world_settings
    type: array
    description: 世界观设定
---

# 设定冲突检测技能

## 任务：设定冲突检测

请检测以下内容是否与世界观设定冲突：

### 章节内容

{{chapter_content}}

### 世界观设定

{{world_settings}}

### 检测维度

#### 1. 规则冲突

- 是否违反核心规则
- 能力使用是否合规
- 代价条件是否满足

#### 2. 地理冲突

- 地点描述是否一致
- 空间关系是否正确
- 移动时间是否合理

#### 3. 势力冲突

- 势力关系是否正确
- 行为是否符合势力立场
- 组织设定是否一致

#### 4. 历史冲突

- 历史引用是否正确
- 时间线是否合理
- 人物年龄经历是否匹配

### 输出格式（JSON）

```json
{
  "conflicts": [
    {"type": "规则冲突", "setting_id": "设定ID", "conflict": "冲突描述", "severity": "严重程度", "fix_suggestion": "修复建议"}
  ],
  "checked_settings": ["检查的设定"],
  "overall_compliance": 95,
  "critical_conflicts": [],
  "suggestions": ["建议"]
}
```
