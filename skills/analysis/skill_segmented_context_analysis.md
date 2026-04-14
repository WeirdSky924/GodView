---
id: skill_segmented_context_analysis
name: 分段上下文分析
description: 将长上下文信息分段分析，提取关键信息并整合回答
category: analysis
skill_type: prompt
tags:
  - 上下文
  - 分段分析
  - 信息提取
  - 设定管理
use_cases:
  - 处理大量项目上下文信息
  - 分段提取关键设定
  - 整合多源信息回答问题
applicable_agent_types:
  - setting
  - master_plotter
  - evaluator
load_mode: on_demand
priority: 80
is_system: true
is_enabled: true
parameters:
  - name: context_sections
    type: object
    description: 分段的上下文信息（世界管理、角色、伏笔、大纲、设定等）
    required: true
  - name: user_question
    type: string
    description: 用户的问题或请求
    required: true
  - name: world_type
    type: string
    description: 世界类型（scifi/fantasy/modern/historical/wuxia）
    required: false
---

# 分段上下文分析技能

## 任务说明

你是一个设定管理助手，需要从大量项目上下文中提取关键信息来回应用户。上下文已被分为多个段落，请**分段分析**后整合回答。

## 世界类型提示

{{world_type}}

## 分段上下文信息

{{context_sections}}

## 用户问题

{{user_question}}

---

## 分析步骤

### 第一步：理解用户意图

首先分析用户想要什么：
- 查询现有设定？
- 创建新设定？
- 修改设定？
- 解决冲突？
- 其他需求？

### 第二步：分段提取关键信息

**不要一次性处理所有信息**，而是按段落逐步提取：

1. **【世界管理】段落**：
   - 核心世界观是什么？
   - 力量体系/规则有哪些？
   - 与用户问题相关的内容？

2. **【已有设定】段落**：
   - 已有哪些设定条目？
   - 是否与用户问题相关？
   - 是否存在冲突风险？

3. **【角色列表】段落**：
   - 有哪些角色？
   - 角色特征是什么？
   - 与用户问题的关联？

4. **【伏笔列表】段落**：
   - 已埋下哪些伏笔？
   - 是否需要呼应？

5. **【章节大纲】段落**：
   - 剧情进展到哪里？
   - 是否有相关情节？

### 第三步：整合分析结果

将各段落的关键信息整合，形成对用户问题的完整回答。

### 第四步：生成回答

基于整合的信息，直接回答用户的问题。

---

## 输出格式

### 如果是查询类问题

```json
{
  "analysis_type": "query",
  "relevant_sections": ["世界管理", "角色列表"],
  "key_findings": [
    "发现1：...",
    "发现2：..."
  ],
  "answer": "针对用户问题的完整回答...",
  "related_suggestions": ["可能还想了解..."]
}
```

### 如果是创建设定类问题

```json
{
  "analysis_type": "create",
  "relevant_existing_settings": ["相关现有设定1", "相关现有设定2"],
  "potential_conflicts": [],
  "suggested_setting": {
    "title": "设定标题",
    "category": "分类",
    "content": "设定内容",
    "notes": "补充说明"
  },
  "confirmation_needed": true
}
```

### 如果是修改设定类问题

```json
{
  "analysis_type": "modify",
  "target_setting": "目标设定名称",
  "current_value": "当前值",
  "proposed_change": "提议修改",
  "impact_analysis": {
    "affected_settings": ["受影响的设定"],
    "affected_characters": ["受影响的角色"],
    "affected_plots": ["受影响的情节"]
  },
  "recommendation": "修改建议..."
}
```

---

## 重要规则

1. **必须阅读并使用提供的上下文信息**，不要声称"没有设定"
2. **如果上下文中已有相关信息**，必须告诉用户这些信息的内容
3. **遵循世界类型约束**，不要生成与项目类型不符的内容
4. **分段处理，避免遗漏**，每个段落都要检查
5. **不要自动保存设定**，必须经过用户确认
