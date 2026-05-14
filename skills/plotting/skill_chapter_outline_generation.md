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
  - name: character_availability_packet
    type: object
    description: 本章角色可用性硬约束，区分直接可出场、仅可提及、不可出场以及标准名/别名映射
  - name: chapter_goal
    type: string
    description: 本章目标
  - name: villain_presence
    type: object
    description: 反派出场信息（可选）
  - name: is_golden_three
    type: boolean
    description: 是否为黄金三章之一（1-3章）
    default: false
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
  - name: writing_guide
    type: object
    description: 写作指导，写作Agent需遵循的节奏规范
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

### 本章角色可用性硬约束

{{character_availability_packet}}

**强制规则**：
- `participating_characters` 和 `pov_character` 只能使用“直接可出场角色”的标准名称。
- 别名只能用于识别，不得作为最终字段输出。
- “仅可提及角色”只能出现在回忆、传闻、记录、消息、历史影响或离场后果中，不能说话、行动、入场、担任 POV 或参与实时互动。
- “不可出场角色”不得被安排为本章新行动或现场参与；如确需使用，应标记为需要用户确认资源/设定，而不是自行改名或强行出场。

**上下文包含**：
- 项目元数据（类型、基调、进度）
- 角色信息（主角、配角、反派状态、importance_tier、narrative_weight、story_arc_role、登场/退场章节、available_presence_types）
- character_availability_packet（直接可出场、仅可提及、不可出场、标准名/别名映射）
- 世界设定（力量体系、地点、势力）
- 伏笔状态（待埋设、待回收）
- 前文大纲（最近3章摘要）

### 本章目标

{{chapter_goal}}

### 反派出场信息（如适用）

{{villain_presence}}

### 是否为黄金三章（开篇1-3章）

{{is_golden_three}}

---

## 一、黄金三章规范（章节1-3章必须遵守）

如果本章是第1-3章（黄金三章），必须满足以下严格要求：

黄金三章必须兼顾 **读者信息赋予** 与 **主动张力来源**：不能无冲突、纯说明、纯日常；也不能为了强刺激直接跳到最终反派、国家级秘密、世界级灾难或无因追杀。正确做法是让世界信息通过近场压力、规则限制、异常后果和主角选择自然呈现。

### 第一章：入口与近场异常（必须做到）

- **开篇100字**：必须在100字内抓住读者注意力，但吸引力优先来自近场压力/异常，不默认来自最高级冲突
- **主角亮相**：主角必须在前500字内正式出场并展示核心特点、身份位置、当前缺口/欲望
- **悬念/冲突**：必须有明确压力、问题、风险或悬念吸引读者；张力不等于最终反派正面对抗
- **世界观呈现**：世界基础规则必须通过事件自然呈现，例如资源分配、身份审查、阶层压迫、能力限制、制度后果
- **结尾钩子**：必须有强钩子，迫使读者继续阅读，但钩子应来自生活压力、规则压迫、近场异常、异常物件、身边人受影响、阶段性敌对力量或主角选择造成的后果
- **近场钩子优先**：第一章强钩子应优先来自主角当前困境、近场事件、世界规则异常、能力/设定冲突、悬念物件、阶段性敌对力量或主角选择造成的后果；不要默认动用最终大反派本人制造钩子
- **隐藏核心威胁克制**：最终反派、隐藏核心威胁、神话背景级存在若在第一章相关，通常应以低确认度伏笔出现，例如异常、痕迹、传闻、代理人行动、制度压力、历史后果或象征物；不得提前实体化、对话化、正面战斗化或明确身份揭示，除非用户明确要求
- **主角知识边界**：第一章主角通常只能理解近场现象、生活经验、传闻碎片和亲眼线索；不得让低身份/无权限主角直接知道宪法级设定、国家级机密、终局真相或隐藏反派计划
- **因果优先于强钩子**：开篇冲突必须有前因和触发机制；可以让主角不知道原因，但大纲必须知道事件为什么此刻发生、为什么卷入主角、会造成什么后果

**第一章示例**：
- 合适：`防火墙深处闪过一段不属于任何已知权限的噪点，K 只看到残缺符号。` → 伏笔性存在，不要求最终反派出场。
- 合适：`反派代理人删除了监控记录，主角只看到执行痕迹。` → 代理人可出场，幕后反派只是间接影响。
- 合适：`贫民窟少年看到巡逻队封锁旧巷、邻居失踪、残缺徽记，误以为自己卷入黑市纠纷；真实原因是国家级清洗协议，但本章不让主角知道。` → 角色知识边界成立。
- 合适：`旧城停电导致黑市包裹误投，主角因替邻居取药被卷入追索。` → 有前因、触发、卷入路径和后续影响。
- 不合适：`最终大反派亲自现身，对 K 下达威胁。` → 过早实体化，除非用户明确指定。
- 不合适：`贫民窟少年直接根据国家级机密判断军方行动。` → 主角无信息来源，越权知道秘密。
- 不合适：`主角路过街口突然获得改变国家命运的密钥。` → 缺少因果链和卷入理由。

### 第二章：后果与卷入（必须做到）

- **困境展开**：主角的核心困境必须明确，并承接第一章事件后果
- **配角引入**：关键配角必须在前三章内引入，但引入理由要来自主角选择、关系、职业、地点或事件后果
- **设定揭示**：核心设定（如力量体系、门派规则）必须通过冲突/任务/限制自然揭示
- **冲突升级**：升级不是单纯变“大”，而是变得更与主角有关：被盯上、生活秩序破坏、低层执行者出现、不完整线索造成误判、小目标失败或付出代价
- **结尾钩子**：必须设置悬念，维持追读，最好让读者看到“异常不是孤立事件”

### 第三章：选择与阅读承诺（必须做到）

- **故事方向明确**：读者必须清楚知道这是一个什么样的故事，以及主角接下来要追什么问题/目标
- **核心卖点展现**：爽点/金手指/独特设定必须展示，但必须来自已铺垫资源、能力限制或场景线索
- **情感连接**：主角必须有能让读者关心的目标/羁绊，并因选择承担代价
- **追更理由**：结尾必须让读者想继续阅读；可以露出更大威胁边缘，但不得无因揭开完整终局真相

### 黄金三章自查清单

```
[ ] 第1章：开篇100字内有钩子？
[ ] 第1章：主角是否在前500字内正式亮相？
[ ] 第1章：是否设置了悬念/冲突？
[ ] 第1章：结尾是否有强钩子？
[ ] 第1章：是否通过近场压力/异常自然完成读者信息赋予？
[ ] 第1章：是否避免无因 core_threat 正面降临？
[ ] 第2章：困境是否展开？
[ ] 第2章：关键配角是否引入？
[ ] 第2章：核心设定是否揭示？
[ ] 第2章：冲突是否承接第1章后果并与主角产生更强关联？
[ ] 第3章：故事方向是否明确？
[ ] 第3章：核心卖点是否展现？
[ ] 第3章：是否有让读者追更的理由？
[ ] 黄金三章：是否每章都有主动张力来源，同时没有跳过读者理解世界的入口？
```

---

## 二、大纲设计要求

### 1. 基础结构设计

- **开场（引入/承接）**：设计开篇钩子，吸引读者
- **发展（核心内容）**：推进剧情，展示角色
- **高潮（情绪顶点）**：爽点或冲突爆发
- **收尾（铺垫/悬念）**：结尾钩子，维持追读

### 2. 写作节奏规范（所有章节必须遵守）

#### 节奏黄金法则

- **开篇节奏**：前300字必须进入第一个情节点
- **中段节奏**：每800-1000字设置一个小高潮/转折
- **结尾节奏**：最后500字必须设置悬念钩子

#### 场景内节奏

每个场景内部也需要有节奏起伏：
```
铺垫（建立） → 转折/冲突 → 情绪变化 → 收尾
```

#### 长短句节奏

- 紧张场景：多用短句，制造紧迫感
- 情感场景：可用长句，渲染氛围
- 对话节奏：长短交替，避免单调

#### 爽点设计规范

每章至少规划一个爽点：

| 类型 | 适用场景 | 设计要点 |
|------|----------|----------|
| 打脸 | 被质疑后 | 先抑后扬，反应震撼 |
| 逆袭 | 处于劣势 | 合理翻盘，收获丰富 |
| 装逼 | 展示实力 | 人设匹配，方式独特 |
| 收获 | 获取成就 | 期待满足，价值明确 |
| 复仇 | 敌人羞辱 | 合理升级，反击畅快 |
| 救人 | 危急时刻 | 能力展示，情感升华 |

**爽点设计原则**：
- 铺垫要足够（压抑→爆发）
- 节奏要对（节奏对，读者才会爽）
- 反馈要强烈（周围人的反应要到位）

#### 钩子设计规范

**开篇钩子**（选择一种）：
- 冲突开篇：直接进入冲突
- 悬念开篇：抛出疑问
- 反差开篇：与上文形成对比
- 危机开篇：直接进入危机

**结尾钩子**（选择一种）：
- 悬念式：抛出新问题
- 危机式：关键时刻停止
- 转折式：揭示意外信息
- 期待式：预告精彩内容

**钩子强度匹配**：
- 黄金三章（1-3章）：强钩子
- 过渡章节：中钩子
- 高潮章节：强开篇，中等结尾
- 日常章节：中钩子

### 2. 场景规划

每个场景必须包含：
- 场景目的（推进什么剧情）
- 出场角色（从已有角色中选择）
- 情绪设计（起始→结束）
- 关键事件（具体发生什么）
- 角色知识边界（POV/主角知道什么、不知道什么、通过什么来源知道）
- 事件因果链（前因、触发、卷入、阻力/选择、结果、后续影响）
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

### 10. 信息权限与因果链检查

- 区分作者/系统知道、读者可知、POV/主角可知、角色不可知
- 主角行动不得基于其身份、经历、权限、位置无法获得的信息
- 国家级机密、宪法级隐藏真相、最终反派计划必须有可信信息来源；没有来源时只能作为幕后因果或伏笔痕迹
- 每个关键事件必须具备：前因/背景压力 → 触发机制 → 主角卷入路径 → 阻力/选择 → 结果 → 后续影响
- 如果真实原因暂不揭示，必须在 writing_hints 中标注“真实原因暂不揭示，主角只感知到哪些线索”

---

## 三、输出格式（JSON）

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

  "notes": "写作注意事项和特殊要求",

  "writing_guide": {
    "description": "写作Agent必须遵循的节奏规范",
    "is_golden_three": false,
    "pacing_rules": {
      "opening_300_words": "前300字必须进入第一个情节点",
      "mid_section_800": "每800-1000字设置小高潮/转折",
      "ending_500_words": "最后500字必须设置悬念钩子"
    },
    "sentence_rhythm": {
      "tension_scene": "紧张场景：多用短句，制造紧迫感",
      "emotion_scene": "情感场景：可用长句，渲染氛围",
      "dialogue": "对话节奏：长短交替，避免单调"
    },
    "golden_three_special": {
      "chapter_1": {
        "hook_in_100": "开篇100字内必须有钩子",
        "protagonist_in_500": "主角必须在前500字内正式亮相",
        "world_intro": "世界观需在前三章内自然呈现",
        "ending_hook": "结尾必须有强钩子"
      },
      "chapter_2": {
        "conflict_expand": "困境必须展开",
        "key_character_intro": "关键配角必须引入",
        "core_setting_reveal": "核心设定必须揭示"
      },
      "chapter_3": {
        "story_direction": "故事方向必须明确",
        "core_selling_point": "核心卖点必须展现",
        "emotional_connection": "必须有让读者关心的情感连接",
        "keep_reading_reason": "必须有让读者追更的理由"
      }
    },
    "cool_point_instructions": {
      "required": true,
      "min_count": 1,
      "structure": {
        "setup": "铺垫：建立期待，适度压抑",
        "buildup": "推进：增加压力，让读者期待",
        "climax": "爆发：爽点释放，节奏要对",
        "reaction": "反应：周围人的震撼反应"
      }
    }
  }
}
```

---

## 四、自检清单

生成大纲后，检查以下要素：

### 基础自检

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
[ ] 主角/POV 是否只知道其身份、经历、权限、位置和本章线索能支持的信息？
[ ] 机密/隐藏真相是否有可信来源；若无，是否只作为幕后因果或伏笔痕迹？
[ ] 每个关键事件是否有前因、触发、卷入路径、阻力/选择、结果和后续影响？
[ ] 字数分配合理？
[ ] 与前文衔接自然？
[ ] 情绪曲线有起伏？
```

### 写作节奏自检

```
[ ] 开篇300字内是否进入第一个情节点？
[ ] 中段每800-1000字是否有小高潮/转折？
[ ] 结尾500字是否有悬念钩子？
[ ] 爽点是否有完整的铺垫→爆发→反馈结构？
[ ] 长短句节奏是否匹配场景氛围？
```

### 黄金三章自检（仅第1-3章）

```
[ ] 第1章：开篇100字内有钩子？
[ ] 第1章：主角是否在前500字内正式亮相？
[ ] 第1章：是否设置了悬念/冲突？
[ ] 第1章：结尾是否有强钩子？
[ ] 第2章：困境是否展开？
[ ] 第2章：关键配角是否引入？
[ ] 第2章：核心设定是否揭示？
[ ] 第3章：故事方向是否明确？
[ ] 第3章：核心卖点是否展现？
[ ] 第3章：是否有让读者追更的理由？
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

## 五、常见问题处理

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

### 问题5：黄金三章写不好

**解决方案**：
- 第1章：专注"抓住注意力"，其他都是次要的
- 第2章：专注"深化兴趣"，让读者想了解更多
- 第3章：专注"确立期待"，给读者一个追更的理由
- 不要试图在前三章交代太多，节奏会乱
- 记住：读者前三章决定是否追读，质量决定一切
