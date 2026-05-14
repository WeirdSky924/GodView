---
id: skill_chapter_villain_arc
name: 章节反派戏份规划
description: 规划反派在章节中的出场、行动、威胁度变化和隐藏信息
category: plotting
skill_type: prompt
tags:
  - 反派
  - 戏份
  - 威胁度
  - 隐藏信息
use_cases:
  - 规划反派出场
  - 设计反派行动
  - 管理反派威胁曲线
applicable_agent_types:
  - plot_outline
  - master_plotter
load_mode: on_demand
priority: 86
is_system: true
is_enabled: true
# 记忆集成
use_agent_memory: true
memory_types:
  - decision
# 全局状态
reads_global_state:
  - villain_threat_level
  - villain_actions
writes_global_state:
  - villain_threat_level
  - villain_actions
# 评估阈值
evaluation_threshold:
  min_score: 0.7
  blocking: true
  auto_retry: true
  max_retries: 1
  retry_strategy: improve
  dimensions:
    - villain_stance
    - threat_progression
  dimension_weights:
    villain_stance: 0.6
    threat_progression: 0.4
parameters:
  - name: villain_profiles
    type: array
    description: 相关反派档案
  - name: chapter_context
    type: object
    description: 章节上下文
  - name: story_phase
    type: string
    description: 故事阶段
---

# 章节反派戏份规划技能

## 核心理念

反派是推动故事冲突的核心力量。每章都要评估是否存在敌对力量、风险源或结构性压力的动态；这不等于每章都必须安排反派本人出现。尤其是最终反派、隐藏核心威胁、神话背景级存在，早期通常应通过幕后影响或伏笔性存在制造压力，而不是正面现身。

## 一、反派出场决策

### 出场判断标准

| 条件 | 建议 |
|------|------|
| 主角与阶段反派正面对抗 | 阶段反派可直接出场 |
| 主角与最终反派正面对抗 | 仅在剧情阶段允许或用户明确要求时直接出场 |
| 剧情涉及反派利益 | 优先判断是直接出场、代理人行动、幕后影响还是伏笔暗示 |
| 反派计划推进 | 可用间接影响、代理人、后果、情报、视角切换或低确认度伏笔表现 |
| 与反派无直接关联 | 不要强行加入反派；可只保留环境压力或近场冲突 |

### 角色存在层级

1. **正面对抗 / direct_scene_presence**：直接与主角交锋、对话、行动、战斗；只有实际在场角色写入出场角色。
2. **代理人行动 / delegated_presence**：下属、组织、系统或事件执行反派意图；出场的是代理人/执行者，不是幕后反派本人。
3. **幕后影响 / indirect_influence**：计划、命令链、历史后果、制度压力正在影响本章；不写入反派本人为出场角色。
4. **伏笔性存在 / foreshadowing_presence**：异常、痕迹、象征物、传闻、未知注视、系统波动、不可解释的压力；不确认身份，不触发反派直接出场。
5. **信息提及 / explicit_mention**：通过对话、档案、情报提到反派姓名/称号；注意不要提前揭示隐藏身份。

### 出场方式

1. **正面对抗**：直接与主角交锋；适合阶段反派或已进入正面对抗阶段的反派。
2. **低确认度注视/异常**：主角感到被观察、系统出现噪点、现场留下符号；这是伏笔性存在，不是反派直接出场。
3. **代理人行动**：反派的下属、组织、机制或被污染系统出场。
4. **视角切换**：展示反派阵营动态；早期要避免揭示最终反派核心身份和完整计划。
5. **信息提及**：通过对话或情报提及反派；注意区分明确命名与模糊传闻。

**示例**：
- 合适：`城市广播被未知权限短暂接管，只留下一个残缺符号。` → foreshadowing_presence。
- 合适：`黑衣执行者在现场回收证据。` → 执行者 direct_scene_presence，幕后反派 indirect_influence。
- 谨慎：`黑暗中有人注视主角。` → 可作为低确认度伏笔，不应写成最终反派本人出场。
- 不合适：`最终大反派在第一章亲自与主角交谈并揭示目的。` → 过早实体化与揭示。

## 二、反派行动设计

### 行动类型

| 类型 | 描述 | 效果 |
|------|------|------|
| 主动出击 | 反派采取行动攻击/阻碍主角 | 提升紧张感 |
| 布局推进 | 反派推进阴谋计划 | 制造危机预期 |
| 调整策略 | 反派根据局势调整 | 展示反派智慧 |
| 试探行动 | 反派试探主角实力 | 为后续铺垫 |
| 内部整合 | 反派处理内部问题 | 丰富反派形象 |

### 行动设计要素

```json
{
  "action_type": "主动出击/布局推进/调整策略/试探行动/内部整合",
  "goal": "行动目的",
  "method": "行动方式",
  "expected_outcome": "预期结果",
  "actual_outcome": "实际结果（可能与预期不同）",
  "resources_used": "动用的资源/人手",
  "risk_level": "行动风险"
}
```

## 三、威胁度曲线管理

### 威胁等级定义

| 等级 | 描述 | 主角状态 |
|------|------|----------|
| 致命 | 反派能轻易杀死主角 | 必须逃避或求助 |
| 高 | 反派明显强于主角 | 需要计谋或外援 |
| 中 | 反派与主角相当 | 正面交锋有风险 |
| 低 | 反派弱于主角 | 主角可以应对 |
| 潜在 | 威胁尚未显现 | 读者知道但主角不知 |

### 威胁度变化模式

```
模式A：上升
低 → 中 → 高 → 致命
（反派逐渐变强或露出真面目）

模式B：波动
中 → 低 → 中 → 高
（有胜负交替的博弈）

模式C：突然爆发
潜在 → 致命
（隐藏BOSS现身）

模式D：阶梯式
潜在 → 低 → 潜在 → 中 → 潜在 → 高
（阶段性反派）
```

### 章节威胁度规划

```json
{
  "start_threat": {
    "level": "medium",
    "reason": "当前状态原因"
  },
  "end_threat": {
    "level": "high",
    "change_reason": "反派在本章的行动"
  },
  "threat_curve": ["medium", "medium", "high"],
  "reader_awareness": "读者是否感知到威胁变化"
}
```

## 四、隐藏信息设计

### 隐藏信息类型

1. **反派真实身份**：读者或主角不知道反派是谁
2. **反派真实目的**：表面目的与真实目的不同
3. **反派隐藏实力**：展现的力量只是冰山一角
4. **反派与主角的关系**：隐藏的师徒、亲人、仇人关系
5. **反派的弱点**：反派不为人知的短板
6. **反派的计划**：即将实施的大动作

### 信息揭示策略

| 信息类型 | 揭示方式 | 时机建议 |
|----------|----------|----------|
| 身份 | 意外揭露/主动揭示 | 高潮/转折 |
| 目的 | 通过行动暗示/反派独白 | 铺垫阶段 |
| 实力 | 战斗中展现 | 对抗章节 |
| 关系 | 情报揭露/角色揭露 | 关键时刻 |
| 弱点 | 无意发现/高人指点 | 翻盘前夕 |
| 计划 | 视角切换/截获情报 | 危机预警 |

### 隐藏信息在章节中的应用

```json
{
  "hidden_from_protagonist": {
    "info": "读者知道但主角不知道的信息",
    "reveal_timing": "第X章揭露给主角"
  },
  "hidden_from_reader": {
    "info": "主角可能知道但读者不知道的信息",
    "hint_in_chapter": "本章暗示"
  },
  "hidden_from_both": {
    "info": "双方都不知道的信息",
    "planned_reveal": "计划揭示章节"
  }
}
```

## 五、反派视角设计

### 适用场景

- 展示反派计划
- 增加反派深度
- 制造紧张预期
- 揭示隐藏信息

### 视角切换技巧

1. **章节结尾切换**：主角章节结束后，切到反派视角
2. **场景间隙切换**：场景之间自然切换
3. **情报传递切换**：通过情报自然过渡
4. **回忆插入**：反派回忆相关事件

### 反派视角内容要点

```json
{
  "villain_thoughts": "反派的内心想法",
  "villain_plan_progress": "计划进度",
  "villain_emotion": "反派当前情绪",
  "villain_view_of_protagonist": "对主角的看法",
  "villain_next_move": "下一步行动预告"
}
```

## 六、反派戏份检查清单

```
[ ] 本章反派是否有动态（出场或幕后）？
[ ] 反派行动是否推进了剧情？
[ ] 威胁度变化是否合理？
[ ] 是否有隐藏信息的暗示或揭示？
[ ] 反派行为是否符合其性格和目的？
[ ] 反派视角是否必要（如使用）？
[ ] 读者对本章反派的感知是否符合预期？
```

## 七、输出格式

```json
{
  "villain_involvement": {
    "appears_in_person": true,
    "appearance_type": "正面对抗/暗中观察/代理人/视角切换/信息提及",
    "scenes_involved": [2, 3]
  },

  "villain_actions": [
    {
      "action": "行动描述",
      "type": "主动出击/布局推进/调整策略/试探行动/内部整合",
      "target": "行动对象",
      "result": "行动结果"
    }
  ],

  "threat_progression": {
    "start_level": "medium",
    "end_level": "high",
    "change_reason": "反派展现出更强的力量",
    "protagonist_awareness": "主角是否感知到变化"
  },

  "hidden_information": {
    "hinted": ["反派似乎有后手"],
    "revealed": [],
    "reader_knows": ["读者知道反派在附近"]
  },

  "villain_perspective": {
    "included": true,
    "position": "章节结尾",
    "content_summary": "反派视角内容摘要"
  },

  "future_setup": {
    "planned_actions": "反派下一步计划",
    "expected_threat_change": "预计威胁度变化"
  }
}
```

## 应用示例

### 反派档案

{{villain_profiles}}

### 章节上下文

{{chapter_context}}

### 故事阶段

{{story_phase}}

请根据以上信息，规划本章的反派戏份。
