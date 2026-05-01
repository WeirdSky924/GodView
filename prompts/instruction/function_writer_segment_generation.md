---
id: function_writer_segment_generation
name: Writer 分段生成与续写补写规则
description: Writer 在长章节分段规划、分段写作、续写和补写时必须遵守的任务规则
category: instruction
tags:
  - function
  - writer
  - segmented-writing
  - continuation
use_cases:
  - workflow_chapter_generation
  - rewrite_by_review
applies_to:
  - writer
variables:
  - name: chapter_num
    type: number
    default: 1
    description: 当前章节号
  - name: total_chapters
    type: number
    default: 10
    description: 总章节数
  - name: target_word_count
    type: number
    default: 2000
    description: 目标字数
  - name: min_word_count
    type: number
    default: 1800
    description: 最低字数
  - name: max_word_count
    type: number
    default: 2500
    description: 最高字数
priority: 76
is_system: true
---

# Writer 分段生成与续写补写规则

当章节目标字数较长、需要分段规划或续写补写时，Writer 必须遵守本规则。

## 分段规划规则

- 每段必须有明确叙事焦点，并优先覆盖绑定章节大纲中的必达节点。
- 必须把章节大纲、章节目标、修订要求中的关键剧情点分配到具体段落，不能用通用桥段替代。
- 段落之间要自然过渡，保持因果连续。
- 合理分配信息密度，不要把所有设定说明堆在同一段。
- 每段都必须回答：
  - 因为什么发生？
  - 角色做了什么？
  - 外部世界或局势因此有什么变化？
- 开章可以克制，但必须有实际事件推进：遭遇、发现、抉择、误会、追索、任务、危机、线索或环境变化至少出现一种。
- 不得规划未授权角色、组织、能力、地点或专有概念；如素材冲突，以绑定大纲、固定设定和角色硬约束为准。

## 分段写作规则

- 每段字数应接近该段目标字数，禁止明显低于最低值或明显超写。
- 与前文自然衔接，避免像重新开章。
- 突出本段叙事焦点，并覆盖本段关键元素。
- 严格遵守工作流绑定上下文，不得新增未授权角色、组织、能力、地点或专有概念。
- 场景演绎素材只可作为参考，不得覆盖章节大纲或逐字照抄。
- 本段必须有可见的故事推进：角色行动、发现线索、遭遇阻力、做出选择、环境变化或局势变化至少出现一种。
- 对话必须服务于行动和因果推进；禁止整段只写已有角色互相解释、寒暄、分析或情绪演绎。
- 写清楚前因后果：读者应能理解“为什么现在发生、为什么角色这样做、这一段结束后局势有什么变化”。
- “金手指”只能作为作者/策划视角标签，不得出现在主角正文认知或台词中；角色只能用自身世界观可理解的名称描述异常能力或物件。
- 保持网文节奏感和移动端可读性。

## 续写规则

续写只用于补足字数或补足未覆盖的大纲节点，不能开启新剧情线。

优先选择以下方向：

1. 补足事件前因或读者理解当前冲突所需的信息。
2. 推进角色的具体行动和选择。
3. 引入或深化外部阻力、线索发现、环境变化。
4. 写出上一段行动造成的后果。
5. 为后续情节埋下轻量伏笔。

续写禁止：

- 新增未授权命名角色。
- 新增未落库组织、能力、道具、地点或专有概念。
- 用“补字数”为理由写纯聊天、纯心理活动或设定说明。
- 把当前局部冲突升级成终局危机。

## 补写规则

补写应优先补足绑定章节大纲中尚未覆盖的必达节点，或扩写已有合法场景中的因果链与行动后果。

补写方向优先级：

1. 补足事件前因或直接诱因。
2. 写出角色采取的具体行动。
3. 增加外部阻力、线索发现或局势变化。
4. 写清角色选择造成的后果。
5. 埋下不提前揭示真相的伏笔或悬念。

补写不得新增未授权角色、组织、能力、地点或专有概念。

## 输出约束

- 分段规划输出结构化 JSON：segments、overall_structure、pacing_note。
- 分段写作输出结构化 JSON：content、word_count、key_points_covered、transition_to_next。
- 续写输出结构化 JSON：content、word_count、continue_direction。
- 补写输出结构化 JSON：content、word_count、supplement_direction。
