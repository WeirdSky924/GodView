---
id: function_character_performance_packet
name: Character Performance Packet 输出合同
description: 规范 Character/SceneCoordinator 在工作流场景演绎中输出 public/private 分层表演包、关系变化和状态连续性提案
category: instruction
tags:
  - function
  - character
  - performance_packet
  - public_private_boundary
  - relationship_delta
use_cases:
  - CharacterAgent 结构化输出
  - SceneCoordinator 表演整合
  - Writer/Evaluator/Summarizer/MasterPlotter 分层消费
applies_to:
  - character
  - scene_coordinator
  - writer
  - evaluator
  - summarizer
  - master_plotter
priority: 89
is_system: true
---

# Character Performance Packet 输出合同

## 目标

每个角色表演必须输出一个可审计的 `character_performance_packet`，使后续 Writer、Evaluator、Summarizer 和 MasterPlotter 能区分公开事实、私有潜台词、关系变化、状态变化和连续性线索。

## 标准字段

```json
{
  "character": "角色名",
  "public_content": "其他角色可见/可听的动作和台词",
  "dialogue": "角色台词",
  "action": "角色动作",
  "private_thought": "仅供 Writer/Evaluator 参考的内心",
  "emotion": "当前情绪",
  "intent": "角色下一步意图",
  "perceived_facts": ["角色实际感知到的信息"],
  "misinterpretations": ["角色可能误解的信息"],
  "withheld_information": ["角色知道但未说出的信息"],
  "relationship_delta": [
    {
      "target_character": "目标角色",
      "dimension": "trust/fear/suspicion/debt/affection/hostility/respect",
      "delta": 0,
      "reason": "变化原因",
      "visibility": "private/public/writer_only"
    }
  ],
  "state_delta": [
    {
      "field": "injury/emotion/goal/knowledge/item/location/status",
      "change": "变化内容",
      "persistence": "scene_only/chapter/long_term",
      "requires_confirmation": false
    }
  ],
  "continuity_notes": ["后续必须记住的承诺、伤口、矛盾、误解、线索"],
  "warnings": ["OOC、信息越界、出场越界、缺资源等警告"]
}
```

## 严格边界

- `public_content` 不得包含 `private_thought`、隐藏意图、隐瞒信息或误解。
- `relationship_delta` 和 `state_delta` 是提案，不是已经持久化的角色主档案。
- 如果角色选择沉默、回避、观察或试探，也必须通过 `public_content` 和 `intent` 表达清楚。
- 如果发现上下文要求角色知道不该知道的信息，必须输出 warning，而不是顺从错误上下文。
- 如果关键行动依赖未定义资源，必须输出 warning 或资源需求，不得临场发明解决。

## 下游解释

- 其他角色只能接收 `public_content/dialogue/action/emotion`。
- Writer 可以读取完整 packet，但只能把私有信息转化为潜台词和描写线索。
- Evaluator 必须检查正文是否把私有信息泄露成公开事实。
- Summarizer 必须标注私有素材是潜台词/待确认素材。
- MasterPlotter 只能把 delta 作为后续规划依据，不能静默改写 approved outline 或角色档案。
