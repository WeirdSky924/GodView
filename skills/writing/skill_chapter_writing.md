---
id: skill_chapter_writing
name: 章节写作
description: 根据大纲和上下文，写作完整章节内容的核心技能
category: writing
skill_type: prompt
tags:
  - 写作
  - 章节
  - 内容生成
use_cases:
  - 根据大纲写章节
  - 扩写简短场景
  - 生成人物对话
applicable_agent_types:
  - writer
  - scene_coordinator
load_mode: on_demand
priority: 80
is_system: true
is_enabled: true
parameters:
  - name: chapter_title
    type: string
    description: 章节标题
    required: true
  - name: chapter_number
    type: number
    description: 章节序号
  - name: target_words
    type: number
    description: 目标字数
    default: 3000
  - name: min_words
    type: number
    description: 最低字数
    default: 2400
  - name: chapter_outline
    type: string
    description: 章节大纲
    required: true
  - name: story_context
    type: string
    description: 前情提要
output_spec:
  - name: content
    type: string
  - name: word_count
    type: number
  - name: outline_coverage
    type: array
  - name: highlights
    type: array
  - name: hooks_embedded
    type: array
---

# 章节写作技能

## 任务：章节写作

请根据以下信息写作章节内容：

### 章节信息

- 章节标题：{{chapter_title}}
- 章节序号：第 {{chapter_number}} 章
- 目标字数：{{target_words}} 字（最低要求：{{min_words}} 字）

### 章节大纲

{{chapter_outline}}

### 前情提要

{{story_context}}

### 写作要求

#### 1. 字数要求（强制）

- 必须达到最低字数要求
- 建议控制在目标字数的±10%

#### 2. 内容要求

- 严格按照大纲展开，但不能把大纲句子直接扩写成正文
- 与前文自然衔接
- 包含大纲中的关键情节点
- 必须完成大纲转场景：每个关键情节点都要有场景触发、角色行动、感官/环境反馈、可见后果和过渡钩子
- 抽象节点（记忆、警告、能力、异常、真相）要从角色有限视角进入，优先写设备异常、身体反应、误判、物件变化或局部代价，不要直接堆“失落的力量”“某个存在”等设定标签

#### 3. 风格要求

- 保持与已有章节风格一致
- 使用具体的感官描写
- 对话要符合人物性格

#### 4. 技巧要求

- 长短句交替使用
- 场景描写服务于情节
- 适时加入心理活动

### 输出格式（JSON）

```json
{
  "content": "章节正文内容",
  "word_count": 实际字数,
  "outline_coverage": ["已覆盖的大纲要点"],
  "highlights": ["本章亮点"],
  "hooks_embedded": ["埋入的伏笔"]
}
```
