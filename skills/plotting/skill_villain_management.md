---
id: skill_villain_management
name: 反派管理
description: 管理反派角色的出场、发展和结局规划
category: plotting
skill_type: prompt
tags:
  - 反派
  - 角色
  - 规划
use_cases:
  - 设计反派角色
  - 规划反派出场
  - 设计反派结局
applicable_agent_types:
  - plot_outline
load_mode: on_demand
priority: 85
is_system: true
is_enabled: true
parameters:
  - name: villain_info
    type: object
    description: 反派信息
  - name: story_phase
    type: string
    description: 当前故事阶段
---

# 反派管理技能

## 任务：反派管理

请管理以下反派角色：

### 反派信息

{{villain_info}}

### 当前故事阶段

{{story_phase}}

### 反派管理原则

#### 1. 反派设计

- 有合理的动机和行为逻辑
- 不是纯粹的恶，有立体感
- 能力要与主角形成张力
- 要推动剧情发展

#### 2. 出场规划

- 出场时机和方式
- 与主角的冲突节点
- 威胁等级变化曲线
- 反派是推动故事冲突的核心力量；这不等于每章都必须安排反派本人出现
- 最终反派、隐藏核心威胁、神话背景级存在，早期通常应通过幕后影响或伏笔性存在制造压力，而不是正面现身

##### 出场层级

- `direct_scene_presence`：反派本人直接在场、行动、对话或与主角发生正面互动。
- `delegated_presence`：代理人、执行者、爪牙、制度机器替反派行动。
- `indirect_influence`：反派造成的结果、压力、规则、损失或局势变化被角色感知。
- `foreshadowing_presence`：低确认度注视/异常、象征物、残缺标记、传闻、历史后果；不应写成最终反派本人出场。
- `explicit_mention`：角色或叙述明确提到反派名字/称号，但反派不在现场。

#### 3. 发展轨迹

- 反派的目标和行动
- 与主角的博弈过程
- 可能的转变机会

#### 4. 结局规划

- 合理的结局安排
- 对故事的影响
- 读者的情感满足

### 反派信息边界与因果约束

- 早期避免揭示最终反派核心身份和完整计划；读者可感到压力，但主角不能无来源知道幕后真相。
- 反派行动必须服务自身目标；看似有利主角时，也必须有自私动机、资源消耗和风险。
- 反派压力可以通过代理人、制度压力、资源封锁、异常痕迹、误导信息或历史后果出现。
- 低确认度注视、异常波动、残缺标记、被清除的记录，不等于反派直接出场。
- 如果需要新反派、组织、能力或关键资源，应标注资源需求，不要现场发明成事实。

#### 示例

- ❌ 第一章安排最终反派本人现身，向主角解释完整计划。
- ✅ 第一章只出现执行者追查、异常标记和被清除的档案，幕后反派保持 hidden core threat。

### 反派类型

#### 1. 宿敌型

与主角长期对立

#### 2. 阶段型

某个阶段的对手

#### 3. 隐藏型

幕后黑手

#### 4. 转化型

可能转向正方

### 输出格式（JSON）

```json
{
  "villain_profile": {"name": "名称", "type": "类型", "threat_level": "威胁等级"},
  "appearance_plan": [{"chapter": 10, "event": "出场事件", "impact": "影响"}],
  "conflict_timeline": [{"phase": "阶段", "villain_action": "行动", "protagonist_response": "应对"}],
  "development_arc": "发展轨迹",
  "ending_plan": "结局规划"
}
```
