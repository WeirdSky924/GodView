---
id: skill_chapter_outline_generation
name: 章节大纲生成
description: 根据整体规划生成单个章节的详细大纲，包含完整的输入规范和结构化输出
category: plotting
skill_type: prompt
tags:
  - 大纲
  - 章节
  - 规划
use_cases:
  - 生成章节大纲
  - 规划段落内容
  - 设计情绪曲线
applicable_agent_types:
  - plot_outline
load_mode: on_demand
priority: 90
is_system: true
is_enabled: true
# 记忆集成
use_agent_memory: true
memory_types:
  - decision
  - observation
# 全局状态
reads_global_state:
  - main_plot_progress
  - active_hooks
  - villain_threat_level
writes_global_state:
  - chapter_outlines
  - planned_cool_points
# 评估阈值
evaluation_threshold:
  min_score: 0.7
  blocking: true
  auto_retry: true
  max_retries: 2
  retry_strategy: improve
  dimensions:
    - completeness
    - consistency
    - stance_check
  dimension_weights:
    completeness: 0.4
    consistency: 0.3
    stance_check: 0.3
parameters:
  - name: chapter_number
    type: number
    description: 章节序号
    required: true
  - name: chapter_title
    type: string
    description: 章节标题
  - name: target_words
    type: number
    description: 目标字数
    default: 3000
  - name: story_context
    type: object
    description: 完整故事上下文（包含角色、设定、伏笔等）
    required: true
  - name: chapter_goal
    type: string
    description: 本章目标
  - name: villain_presence
    type: object
    description: 反派出场信息（可选）
output_spec:
  - name: title
    type: string
  - name: summary
    type: string
  - name: scenes
    type: array
  - name: emotion_curve
    type: object
  - name: chapter_goals
    type: array
  - name: cool_points
    type: array
  - name: hooks
    type: object
  - name: villain_arc
    type: object
  - name: quality_check
    type: object
---

# 章节大纲生成技能

## 任务：章节大纲生成

请根据以下信息生成章节大纲：

### 基本信息

- 章节序号：第 {{chapter_number}} 章
- 章节标题：{{chapter_title}}
- 目标字数：{{target_words}} 字

### 故事上下文（完整输入）

{{story_context}}

**上下文包含**：
- 项目元数据（类型、基调、进度）
- 角色信息（主角、配角、反派状态）
- 世界设定（力量体系、地点、势力）
- 伏笔状态（待埋设、待回收）
- 前文大纲（最近3章摘要）

### 本章目标

{{chapter_goal}}

### 反派出场信息（如适用）

{{villain_presence}}

---

## 一、大纲设计要求

### 1. 结构设计

- **开场（引入/承接）**：设计开篇钩子，吸引读者
- **发展（核心内容）**：推进剧情，展示角色
- **高潮（情绪顶点）**：爽点或冲突爆发
- **收尾（铺垫/悬念）**：结尾钩子，维持追读

### 2. 场景规划

每个场景必须包含：
- 场景目的（推进什么剧情）
- 出场角色（从已有角色中选择）
- 情绪设计（起始→结束）
- 关键事件（具体发生什么）
- 预估字数

### 3. 情绪曲线设计

```
位置：0.0 ────────────── 1.0
强度：0.0 ────────────── 1.0

规划情绪起伏：
- 起始情绪和强度
- 关键转折点
- 高潮位置和强度
- 收尾情绪
```

### 4. 爽点设计

每章至少规划一个爽点：

| 类型 | 适用场景 | 设计要点 |
|------|----------|----------|
| 打脸 | 被质疑后 | 先抑后扬，反应震撼 |
| 逆袭 | 处于劣势 | 合理翻盘，收获丰富 |
| 装逼 | 展示实力 | 人设匹配，方式独特 |
| 收获 | 获取成就 | 期待满足，价值明确 |

### 5. 钩子设计

**开篇钩子**（选择一种）：
- 冲突开篇：直接进入冲突
- 悬念开篇：抛出疑问
- 反差开篇：与上文形成对比

**结尾钩子**（选择一种）：
- 悬念式：抛出新问题
- 危机式：关键时刻停止
- 转折式：揭示意外信息

### 6. 反派戏份（如有反派出场）

- 反派当前状态
- 反派行动目的
- 与主角的互动
- 威胁程度变化
- 隐藏信息（读者暂时不知道的）

**反派行为约束**：反派的任何行为不能以"帮助主角实现其核心目标"为出发点。如需做出看似有利主角的行为，必须有自私动机。

### 7. 伏笔管理

- 本章埋设的伏笔（记录内容）
- 本章暗示的伏笔（轻轻带过）
- 本章回收的伏笔（兑现期待）

### 8. 角色立场标注（强制）

每个出场角色必须标注：
```json
{
  "name": "角色名",
  "role_type": "protagonist/antagonist/ally/neutral/rival",
  "importance_tier": "protagonist/archenemy/major_ally/...",
  "stance": "友好/敌对/中立",
  "core_goal": "角色的核心目标"
}
```

### 9. 角色一致性检查

- 出场角色行为符合性格
- 角色状态与上文衔接
- 不引入与设定冲突的新元素
- 反派行为符合敌对立场

---

## 二、输出格式（JSON）

```json
{
  "title": "章节标题",
  "summary": "章节概述（100-200字，包含本章核心事件和情绪走向）",

  "scenes": [
    {
      "scene_number": 1,
      "title": "场景标题",
      "scene_type": "dialogue/action/description/climax/transition",
      "purpose": "场景目的",
      "summary": "场景摘要（50-100字）",

      "characters": {
        "main": [
          {"name": "主角名", "role_type": "protagonist", "stance": "友好", "core_goal": "目标"}
        ],
        "supporting": [
          {"name": "配角名", "role_type": "ally", "stance": "友好", "core_goal": "目标"}
        ],
        "villain": [
          {"name": "反派名", "role_type": "antagonist", "stance": "敌对", "core_goal": "目标"}
        ]
      },

      "location": "场景地点",
      "time": "时间/时段",

      "emotion": {
        "start": {"type": "neutral", "intensity": 0.3},
        "end": {"type": "tension", "intensity": 0.6},
        "arc": ["neutral", "curiosity", "tension"]
      },

      "conflict_level": "low/medium/high/critical",
      "key_events": ["事件1", "事件2"],
      "estimated_words": 800,

      "villain_involvement": {
        "present": false,
        "hidden_action": "幕后行动（读者暂不知）",
        "threat_change": "威胁度变化"
      }
    }
  ],

  "emotion_curve": {
    "points": [
      {"position": 0.0, "emotion": "neutral", "intensity": 0.3, "event": "开场"},
      {"position": 0.3, "emotion": "curiosity", "intensity": 0.5, "event": "发现异常"},
      {"position": 0.6, "emotion": "tension", "intensity": 0.8, "event": "冲突爆发"},
      {"position": 1.0, "emotion": "anticipation", "intensity": 0.6, "event": "悬念收尾"}
    ],
    "dominant_emotion": "tension",
    "pacing": "快/中/慢"
  },

  "cool_points": [
    {
      "type": "打脸/逆袭/装逼/收获/复仇/助人",
      "position": "场景2结尾",
      "setup": "铺垫内容",
      "climax": "爆发内容",
      "intensity": 7
    }
  ],

  "hooks": {
    "opening": {
      "type": "悬念/冲突/反差/时间跳跃",
      "content": "开篇钩子内容",
      "strength": 8
    },
    "ending": {
      "type": "悬念/危机/转折/期待",
      "content": "结尾钩子内容",
      "strength": 9,
      "expectation_created": "制造的期待",
      "resolve_by_chapter": 15
    }
  },

  "villain_arc": {
    "appearing": true,
    "villain_name": "反派名",
    "current_threat_level": "medium",
    "chapter_actions": ["行动1", "行动2"],
    "hidden_information": "读者暂时不知道的信息",
    "protagonist_interaction": "与主角的互动",
    "threat_change": "increased/stable/decreased"
  },

  "foreshadowing": {
    "plant": [
      {"content": "伏笔内容", "importance": "high/medium/low"}
    ],
    "hint": [
      {"hook_id": "伏笔ID", "hint_type": "暗示方式"}
    ],
    "payoff": [
      {"hook_id": "伏笔ID", "resolution": "回收方式"}
    ]
  },

  "chapter_goals": [
    "目标1：推进主线剧情",
    "目标2：展示角色成长"
  ],

  "word_count": {
    "target": 3000,
    "by_scenes": [600, 800, 1000, 600],
    "recommended": 3000
  },

  "quality_check": {
    "opening_hook_present": true,
    "ending_hook_present": true,
    "cool_point_count": 1,
    "villain_consistent": true,
    "character_consistency": true,
    "setting_consistency": true,
    "word_count_reasonable": true,
    "warnings": ["注意：反派威胁度在本章有所提升"]
  },

  "notes": "写作注意事项和特殊要求"
}
```

---

## 三、自检清单

生成大纲后，检查以下要素：

```
[ ] 开篇有钩子？
[ ] 结尾有钩子？
[ ] 至少有一个爽点？
[ ] 出场角色已标注 role_type 和 stance？
[ ] 出场角色与设定一致？
[ ] 反派行为符合敌对立场？（不自相矛盾地帮助主角）
[ ] 场景地点在世界观中存在？
[ ] 伏笔有记录？
[ ] 反派戏份合理（如有）？
[ ] 字数分配合理？
[ ] 与前文衔接自然？
[ ] 情绪曲线有起伏？
```

### 反派行为专项检查

如果本章有反派出场，额外检查：

```
[ ] 反派的目标是什么？
[ ] 反派的行为是否服务于自身目标？
[ ] 反派是否无理由帮助了主角？（如有则需修改）
[ ] 看似善意的反派行为是否有隐藏目的？
```

---

## 四、常见问题处理

### 问题1：不知道如何开场

**解决方案**：
- 回顾上一章结尾，找承接点
- 考虑时间跳跃，直接进入关键场景
- 使用视角切换，从其他角色切入

### 问题2：场景太单薄

**解决方案**：
- 增加角色互动
- 加入环境描写
- 设计小冲突或意外

### 问题3：缺乏爽点

**解决方案**：
- 检查是否有被轻视的角色可以打脸
- 是否有意外收获可以设计
- 是否有隐藏实力可以展示

### 问题4：反派没有存在感

**解决方案**：
- 即使不出场，也可以有幕后行动
- 让反派的行为影响本章剧情
- 暗示反派的下一步计划
