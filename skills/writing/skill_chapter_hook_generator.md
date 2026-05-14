---
id: skill_chapter_hook_generator
name: 章节悬念钩子生成
description: 为章节结尾生成吸引人的悬念钩子
category: writing
skill_type: prompt
tags:
  - 悬念
  - 钩子
  - 结尾
use_cases:
  - 设计章节结尾
  - 制造悬念
  - 吸引读者继续阅读
applicable_agent_types:
  - writer
load_mode: on_demand
priority: 75
is_system: true
is_enabled: true
parameters:
  - name: chapter_summary
    type: string
    description: 章节内容摘要
    required: true
  - name: key_events
    type: array
    description: 本章关键事件
  - name: next_chapter_hint
    type: string
    description: 下章预告
---

# 章节悬念钩子生成技能

## 任务：章节悬念钩子生成

请为以下章节内容生成结尾悬念钩子：

### 章节内容摘要

{{chapter_summary}}

### 本章关键事件

{{key_events}}

### 下章预告（如有）

{{next_chapter_hint}}

### 悬念钩子类型

#### 1. 危机型钩子

- 主角陷入危险
- 意外事件发生
- 紧迫的威胁

#### 2. 揭示型钩子

- 重要信息揭晓
- 身份暴露
- 真相浮出水面

#### 3. 转折型钩子

- 意想不到的变化
- 关系逆转
- 新势力介入

#### 4. 期待型钩子

- 即将发生的大事
- 重要的约定或承诺
- 目标临近

### 钩子要求

1. **吸引力**：能让读者想继续看下一章
2. **合理性**：与本章内容自然衔接
3. **适度性**：不夸张，不欺骗读者
4. **独特性**：避免老套的"欲知后事如何"

### 因果与知识边界（强制）

- **钩子可以神秘，但不能无因**：必须有真实来源、触发时机和对当前场景/主角的影响路径。
- 每个钩子都要能回答：真实来源是什么 → 为什么此刻出现 → 为什么影响主角/当前场景 → 主角能感知到什么 → 暂时隐藏什么 → 后续如何兑现。
- 主角只能根据亲眼所见、传闻碎片、残缺线索、职业经验、能力感知或可信角色告知做判断。
- 不要为了强钩子随机投放灾难、国家机密、高阶人物、神器、追杀、最终反派身份或终局真相。
- 隐藏核心威胁优先用异常、痕迹、象征物、传闻、代理人行动、制度压力或历史后果表现。

#### 示例

- ❌ 结尾直接揭示“真正敌人是帝国最高执政官，他已启动国家级清洗协议”。
- ✅ 结尾只让主角看见被抹除的档案编号、重复出现的残缺徽记和巡逻队异常封锁；真实协议仍是 hidden_truth_not_revealed。
- ❌ 天空突然掉下一份国家机密文件作为悬念。
- ✅ 档案室火灾后，一页烧焦名单被排水渠冲到主角脚边，主角只能识别其中一个熟悉名字。

### 输出格式（JSON）

```json
{
  "hook_type": "钩子类型",
  "hook_content": "钩子内容（1-3句话）",
  "emotion_target": "目标读者情绪",
  "next_lead": "对下章的铺垫",
  "causal_source": "钩子的真实来源/前因（可选但建议）",
  "protagonist_visible_clues": ["主角能感知到什么"],
  "hidden_truth_not_revealed": "暂时不能让角色知道的真相",
  "payoff_plan": "后续兑现方式",
  "knowledge_boundary_check": "主角是否只基于可知信息行动"
}
```
