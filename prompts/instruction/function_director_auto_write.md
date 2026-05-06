---
id: function_director_auto_write
name: Director 旧自动写作入口要求
category: instruction
description: 定义 Director 直连自动写作回退入口的章节正文生成边界和写作要求；运行时会追加章节标题、目标、角色、世界观与风格参考
tags:
  - function
  - director
  - writer
  - auto-write
  - legacy
use_cases:
  - Director 自动写作回退
  - 单章直连写作
  - 工作流失败后的兼容写作入口
applies_to:
  - director
  - writer
variables:
  - name: chapter_title
    type: string
    default: ""
    description: 章节标题，由运行时代码追加
  - name: chapter_goal
    type: string
    default: ""
    description: 章节目标或大纲，由运行时代码追加
  - name: target_word_count
    type: number
    default: 2000
    description: 目标字数，由运行时代码追加
priority: 70
is_system: true
---

# Director 自动写作入口要求

这是 Director 直连自动写作 / 兼容回退入口使用的写作要求。它必须服从运行时追加的章节标题、章节目标、主要角色、世界观和风格参考；这些动态上下文优先级高于临场发挥。

## 写作要求

1. 展示而非告知（Show, Don't Tell）：通过动作、表情、环境变化、选择和后果表现信息，不要只用说明文字替代剧情。
2. 移动端可读：段落简短有力，节奏清晰，避免大段堆砌设定。
3. 角色一致：对话、行动和情绪必须符合已提供角色身份、关系、状态和说话习惯。
4. 当前章节优先：只完成本章目标，不提前解决终局矛盾，不替后续章节完成高潮。
5. 资源约束：不要临场发明关键命名角色、核心设定、万能道具、关键地点或未铺垫能力来推动/解决剧情。
6. 事件推进：章节必须有可见事件链，包括前因、触发、行动、变化、结果或后续影响；不能只有聊天或设定说明。
7. 冲突与转折：安排与章节目标匹配的局部冲突、选择或外部变化，但不得无端升级为最终危机。
8. 感官和场景：使用适量感官描写、动作描写和环境反馈，让场景有空间感和即时性。
9. 悬念/伏笔：结尾可以保留轻量悬念或伏笔，但不要引入无法由当前资源支撑的新主线。
10. 正文输出：生成完整章节正文，不要输出创作说明、JSON、提纲或分析过程。
