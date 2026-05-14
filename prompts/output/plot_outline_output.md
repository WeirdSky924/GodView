---
id: plot_outline_output
name: 章节大纲输出格式规范
description: 规范Plot Outline Agent输出JSON格式的详细结构
category: output
tags:
  - output
  - plot_outline
  - json
  - format
use_cases:
  - 生成单章大纲
  - 生成多章大纲（黄金三章）
  - 讨论后输出大纲
applies_to:
  - plot_outline
priority: 95
is_system: true
---

# 章节大纲输出格式规范

【重要：必须严格遵守】

当用户要求生成或更新大纲时，必须先保证设定正确，再输出完整的 JSON 格式大纲。

优先级顺序如下：
1. 宪法级设定不可违反
2. 核心设定、角色立场、时间线必须保持一致
3. JSON 输出格式必须完整

## 单章大纲格式

```json
{
  "chapter_number": 1,
  "title": "章节标题（简洁有力，不要包含'第X章'）",
  "summary": "章节摘要（100-200字，描述本章主要内容、开篇悬念、发展过程、结尾转折）",
  "chapter_goals": ["目标1", "目标2", "目标3"],
  "hooks_planted": ["建议埋设的伏笔1", "建议埋设的伏笔2"],
  "hooks_resolved": ["建议回收的伏笔"],
  "target_word_count": 3000,
  "scenes": [
    {
      "scene_number": 1,
      "title": "场景标题",
      "summary": "场景内容描述",
      "participating_characters": ["直接可出场角色标准名"],
      "pov_character": "直接可出场角色标准名",
      "location": "场景地点",
      "scene_type": "dialogue",
      "conflict_level": "low",
      "conflict_description": "冲突描述",
      "estimated_words": 800,
      "key_events": ["事件1", "事件2"],
      "writing_hints": ["写作提示"]
    },
    {
      "scene_number": 2,
      "title": "场景标题",
      "summary": "场景内容描述",
      "estimated_words": 1000,
      "key_events": ["事件1"]
    }
  ]
}
```

## 多章大纲格式（黄金三章等）

```json
{
  "chapters": [
    {
      "chapter_number": 1,
      "title": "第一章标题",
      "summary": "第一章摘要，描述主要内容和悬念",
      "chapter_goals": ["目标1", "目标2"],
      "hooks_planted": ["伏笔1"],
      "scenes": [
        {"scene_number": 1, "title": "场景1", "summary": "内容", "estimated_words": 800}
      ]
    },
    {
      "chapter_number": 2,
      "title": "第二章标题",
      "summary": "第二章摘要",
      "chapter_goals": ["目标1", "目标2"],
      "hooks_planted": ["伏笔1"],
      "scenes": [
        {"scene_number": 1, "title": "场景1", "summary": "内容", "estimated_words": 800}
      ]
    },
    {
      "chapter_number": 3,
      "title": "第三章标题",
      "summary": "第三章摘要",
      "chapter_goals": ["目标1", "目标2"],
      "hooks_planted": ["伏笔1"],
      "scenes": [
        {"scene_number": 1, "title": "场景1", "summary": "内容", "estimated_words": 800}
      ]
    }
  ]
}
```

## 必须遵守的规则

1. **先保证设定一致性**：如发现与宪法级设定、核心设定、角色立场或时间线冲突，必须先修正内容再输出
2. **必须输出 JSON**：无论讨论还是生成，最后都要输出完整的 JSON 大纲
3. **JSON 必须完整**：不要省略任何字段，不要使用省略号
4. **scenes 数组必须填写**：每个场景要包含 scene_number, title, summary, participating_characters, pov_character, location, scene_type, estimated_words
5. **角色标准名与可用性**：participating_characters 和 pov_character 只能使用 character_availability_packet 中“直接可出场角色”的标准名称；不得输出别名；仅可提及/不可出场角色不能直接参与场景
6. **角色存在层级**：幕后影响、伏笔性存在、异常痕迹、未知注视、象征物、传闻、历史后果不等于直接出场，不得写入 participating_characters / pov_character；应放入 hooks_planted、summary、key_events 或 writing_hints 中作为伏笔/设定暗示
7. **角色知识边界**：设定真实不等于角色可知；主角/POV 的判断、台词、选择和行动计划只能基于其身份、经历、位置、权限、能力和本章实际获得的线索。宪法级设定、国家级机密、隐藏真相若无可信信息来源，只能作为幕后因果、异常痕迹、伏笔或读者可知信息，不得写成主角已知事实
8. **事件因果链**：每个关键事件必须有前因/背景压力、触发机制、主角卷入理由、现场阻力/选择、结果和后续影响；事件可以神秘，但不能无因
9. **黄金三章平衡**：第1-3章必须兼顾读者信息赋予与主动张力来源；不能纯说明无冲突，也不能无因跳到最终反派、国家级秘密、世界级灾难或最高级威胁正面对抗
10. **冲突规模合法**：黄金三章优先使用 `life_pressure` / `rule_pressure` / `local_anomaly` / `proxy_conflict` / `mainline_edge` 渐进张力；`core_threat` 正面冲突必须有用户授权和完整因果铺垫
11. **多章用 chapters 数组**：生成多章时，必须用 `{"chapters": [...]}` 格式，每章都要有 chapter_number
12. **避免截断**：如果内容太长，可以分多次输出，但每次 JSON 都要完整

### 角色知识边界与因果链输出示例

```json
{
  "summary": "贫民窟少年阿野在旧巷封锁中发现邻居失踪，只获得残缺徽记和'黑箱'一词，不知道背后的国家级清洗协议。",
  "hooks_planted": ["残缺徽记：真实关联国家级清洗协议，但本章主角只把它当成危险标记"],
  "scenes": [
    {
      "scene_number": 1,
      "title": "旧巷封锁",
      "summary": "巡逻队突然封锁旧巷，阿野因替邻居取药被困在警戒线内，发现门缝下有一枚被烧焦的徽记。",
      "participating_characters": ["阿野"],
      "pov_character": "阿野",
      "location": "贫民窟旧巷",
      "scene_type": "conflict",
      "key_events": [
        "前因：黑市转运包裹误入旧巷，引发巡逻队清查",
        "触发：阿野替邻居取药时撞见封锁",
        "卷入：邻居失踪且药包留在阿野手中",
        "结果：阿野获得残缺徽记，但不知道国家级机密真相"
      ],
      "writing_hints": [
        "主角只知道封锁、失踪、残缺徽记三个线索，不得让他直接说出清洗协议或国家机密",
        "真实原因可作为幕后因果保留，暂不向主角完整揭示"
      ]
    }
  ],
  "quality_check": {
    "protagonist_knowledge_boundary": true,
    "causal_chain_complete": true,
    "secret_information_source_valid": true,
    "opening_information_delivery": "通过救济编号异常、旧巷封锁和邻居失踪自然展示贫民区资源制度与主角处境",
    "active_tension_source": "资源断供 + 局部封锁 + 残缺徽记",
    "conflict_scale": "local_anomaly",
    "protagonist_access_reason": "阿野替邻居取药时被封锁卷入，且药包留在他手中",
    "not_over_escalated": true
  }
}
```

上例中，国家级机密是真实世界因果，但主角只接触到低层可感知线索。

### 角色存在层级输出示例

```json
{
  "summary": "K 在裂隙港发现未知权限留下的噪点，意识到防火墙深处存在更高层级的异常。",
  "hooks_planted": ["未知高权限噪点：暗示隐藏核心威胁正在影响防火墙"],
  "scenes": [
    {
      "scene_number": 1,
      "title": "噪点警报",
      "summary": "K 调查异常波动，只看到残缺符号和被清除的日志。",
      "participating_characters": ["K"],
      "pov_character": "K",
      "key_events": ["防火墙出现未知权限噪点", "日志被某个非现场力量清除"],
      "writing_hints": ["隐藏核心威胁只以痕迹和系统异常存在，不要安排其现身或对话"]
    }
  ]
}
```

上例中，隐藏威胁是 `foreshadowing_presence` / `indirect_influence`，不应出现在 `participating_characters`。

## 工作流程示例

1. 先用自然语言与用户讨论大纲方向
2. 确认方向后，输出完整 JSON 格式的大纲
3. JSON 会被系统自动解析并保存为草稿

## 字段说明

| 字段 | 必填 | 说明 |
|------|------|------|
| chapter_number | 是 | 章节号 |
| title | 是 | 章节标题（不含"第X章"） |
| summary | 是 | 章节摘要（100-200字） |
| chapter_goals | 是 | 章节目标列表（1-5个） |
| hooks_planted | 否 | 本章埋设的伏笔 |
| hooks_resolved | 否 | 本章回收的伏笔 |
| target_word_count | 否 | 目标字数，默认3000 |
| scenes | 是 | 场景列表 |

## 场景字段说明

| 字段 | 必填 | 说明 |
|------|------|------|
| scene_number | 是 | 场景序号 |
| title | 是 | 场景标题 |
| summary | 是 | 场景内容描述 |
| participating_characters | 是 | 直接参与本场景的角色标准名列表，只能来自直接可出场角色 |
| pov_character | 是 | 视角角色标准名，只能来自直接可出场角色 |
| location | 是 | 场景地点 |
| scene_type | 否 | 场景类型 |
| conflict_level | 否 | 冲突强度 |
| conflict_description | 否 | 冲突描述 |
| estimated_words | 是 | 预估字数 |
| key_events | 否 | 关键事件列表 |
| writing_hints | 否 | 写作提示；必须标注主角/POV 当前知道与不知道的信息边界、秘密信息来源、关键事件因果链中暂不揭示的真实原因 |
| quality_check.protagonist_knowledge_boundary | 建议 | 主角/POV 是否只基于可知信息行动 |
| quality_check.causal_chain_complete | 建议 | 关键事件是否具备前因、触发、卷入、结果、后续影响 |
| quality_check.secret_information_source_valid | 建议 | 机密/隐藏真相是否有可信揭示渠道；无渠道时是否仅作为伏笔或幕后因果 |
| quality_check.opening_information_delivery | 建议 | 黄金三章如何通过冲突自然赋予读者主角处境、世界基础规则、社会/力量限制 |
| quality_check.active_tension_source | 建议 | 本章吸引读者的压力/问题/风险/悬念来源 |
| quality_check.conflict_scale | 建议 | life_pressure / rule_pressure / local_anomaly / proxy_conflict / mainline_edge / core_threat |
| quality_check.protagonist_access_reason | 建议 | 主角为什么能接触该冲突，而不是任意路人 |
| quality_check.not_over_escalated | 建议 | 是否避免无因正面抛出最终反派、国家级秘密或世界级灾难 |
