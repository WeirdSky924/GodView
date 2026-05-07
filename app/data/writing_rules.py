"""
系统内置写作规则数据
提供预定义的写作规则，用于写作风格控制
"""

from datetime import datetime
from app.models.writing_rule import (
    WritingRule,
    WritingRuleSet,
    WritingRuleCategory,
    RuleSeverity,
)


# ==================== 对话类规则 ====================

DIALOGUE_VOICE_CHARACTER = WritingRule(
    id="dialogue_voice_character",
    name="角色声音差异化",
    description="不同角色应有独特的说话方式和用词习惯",
    category=WritingRuleCategory.DIALOGUE,
    severity=RuleSeverity.REQUIRED,
    tags=["dialogue", "character", "voice"],
    content="每个角色应有独特的说话风格、用词习惯和口头禅。避免所有角色说话方式雷同。角色语言应反映其背景、性格、教育程度和当前情绪。",
    examples=[
        "学者角色使用专业术语和复杂句式，农民角色使用方言土语和简单直白的表达",
        "贵族角色说话优雅正式，市井角色说话粗俗直接",
        "外向角色话多活泼，内向角色话少简洁",
        "老年人使用传统词汇和谚语，年轻人使用流行语和新词汇"
    ],
    counter_examples=[
        "所有角色都说同样风格的话，无法从对话中区分角色",
        "农民角色使用学者般的专业术语",
        "古代角色使用现代流行语"
    ],
    is_system=True,
    author="系统",
    source="经典写作理论"
)

DIALOGUE_ACTION_INTERLEAVE = WritingRule(
    id="dialogue_action_interleave",
    name="对话动作穿插",
    description="对话中应穿插角色的动作、表情和反应",
    category=WritingRuleCategory.DIALOGUE,
    severity=RuleSeverity.STRONG,
    tags=["dialogue", "action", "show_dont_tell"],
    content="在对话中穿插角色的动作、表情、肢体语言和环境反应，使对话更生动。避免大段的纯对话文本。",
    examples=[
        "他摇了摇头，苦笑着说：'这件事没那么简单。'",
        "她紧张地绞着手指，声音有些颤抖：'我...我不知道该怎么办。'",
        "窗外传来一声惊雷，他猛地站起身：'什么声音？'",
        "老人慢慢端起茶杯，吹了吹热气，缓缓说道：'那是很久以前的事了...'"
    ],
    counter_examples=[
        "'你好。''你好。''最近怎么样？''还不错。'（纯对话无动作）",
        "他说：'我不同意。'然后她說：'为什么？'然后他又說：'因为...'"
    ],
    is_system=True,
    author="系统",
    source="展示而非讲述原则"
)

DIALOGUE_SPOKEN_FEATURES = WritingRule(
    id="dialogue_spoken_features",
    name="真实口语特征",
    description="对话应具有真实口语的特征，如省略、重复、语气词等",
    category=WritingRuleCategory.DIALOGUE,
    severity=RuleSeverity.RECOMMENDED,
    tags=["dialogue", "realism", "spoken_language"],
    content="对话应模仿真实口语，包含适当的省略、重复、语气词、停顿和不完整句子。避免过于书面化和完美的语法。",
    examples=[
        "'那个...其实我也不太确定。'（使用语气词）",
        "'你你你...你说什么？！'（重复表示震惊）",
        "'我觉得...嗯...可能不是这样。'（停顿和犹豫）",
        "'饭吃了没？'（口语化省略）",
        "'简直了！'（口语感叹）"
    ],
    counter_examples=[
        "'根据我的分析，这件事情存在多个不确定因素，因此我无法给出确切的结论。'（过于书面化）",
        "'你刚才所说的话语让我感到十分震惊和不可思议。'（不自然的口语）"
    ],
    is_system=True,
    author="系统",
    source="口语化写作技巧"
)

DIALOGUE_IDENTITY_MATCH = WritingRule(
    id="dialogue_identity_match",
    name="身份时代匹配",
    description="角色的语言应符合其身份、时代和文化背景",
    category=WritingRuleCategory.DIALOGUE,
    severity=RuleSeverity.REQUIRED,
    tags=["dialogue", "character", "consistency", "historical"],
    content="角色的用词、语法和表达方式应符合其身份地位、所处时代和文化背景。避免出现时代错位或身份不符的语言。",
    examples=[
        "古代贵族使用'阁下'、'陛下'等敬语，而非现代称呼",
        "西方中世纪角色使用古英语词汇和句式",
        "科学家角色使用专业术语，农民角色使用农业相关比喻",
        "武侠角色使用江湖黑话和武功术语"
    ],
    counter_examples=[
        "唐朝诗人说出'OK'、'拜拜'等现代词汇",
        "古代将军说：'这个方案需要优化一下用户体验。'",
        "农民角色讨论量子物理概念"
    ],
    conditions=[
        {"type": "historical_setting", "description": "历史或特定时代背景"},
        {"type": "character_established", "description": "角色身份已确立"}
    ],
    is_system=True,
    author="系统",
    source="历史准确性和角色一致性"
)

# ==================== 结构类规则 ====================

SENTENCE_RHYTHM_VARIATION = WritingRule(
    id="sentence_rhythm_variation",
    name="句式节奏变化",
    description="交替使用长短句，创造阅读节奏",
    category=WritingRuleCategory.STRUCTURE,
    severity=RuleSeverity.STRONG,
    tags=["structure", "rhythm", "sentence_variety"],
    content="交替使用长句和短句，简单句和复杂句，创造变化的阅读节奏。避免连续使用相同长度的句子。",
    examples=[
        "夜已深。万籁俱寂。只有远处的狗吠声，偶尔打破这沉重的宁静。（短-短-长）",
        "他跑着。飞快地跑着。穿过街道，越过栏杆，跳过水坑，不顾一切地向前冲。（短-短-长句列举）",
        "雨下得很大。豆大的雨点砸在窗户上，发出噼里啪啦的响声。街道变成了河流。（短-长-短）"
    ],
    counter_examples=[
        "他起床。他刷牙。他洗脸。他吃早餐。他出门。（全是短句）",
        "在那个阳光明媚的早晨，当第一缕晨曦透过窗帘的缝隙洒进房间时，刚刚从睡梦中醒来的他，揉了揉惺忪的睡眼，慢慢地从温暖的被窝中坐起身来。（全是长句）"
    ],
    is_system=True,
    author="系统",
    source="句式变化与节奏控制"
)

SCENE_TRANSITION_TECHNIQUE = WritingRule(
    id="scene_transition_technique",
    name="场景转换技巧",
    description="使用自然的方式转换场景，避免生硬跳跃",
    category=WritingRuleCategory.STRUCTURE,
    severity=RuleSeverity.RECOMMENDED,
    tags=["structure", "scene", "transition", "flow"],
    content="使用时间推移、空间移动、视角切换或情绪变化等自然方式转换场景。避免生硬的'现在我们来到...'式转换。",
    examples=[
        "谈话结束后，他独自走向窗前。窗外，夜幕已经降临。（空间转移）",
        "日子一天天过去，转眼已是深秋。（时间推移）",
        "正当他陷入沉思时，电话铃声突然响起。（事件打断）",
        "她的笑容还停留在脑海里，但眼前已是另一番景象。（情绪引导）"
    ],
    counter_examples=[
        "第一章结束了。现在开始第二章。",
        "场景转换：从客厅到卧室。",
        "话说另一边，与此同时，..."
    ],
    is_system=True,
    author="系统",
    source="场景过渡技巧"
)

DESCRIPTION_ORDER_VARIED = WritingRule(
    id="description_order_varied",
    name="描写顺序多样化",
    description="变换描写顺序，避免固定模式",
    category=WritingRuleCategory.STRUCTURE,
    severity=RuleSeverity.RECOMMENDED,
    tags=["structure", "description", "order", "variety"],
    content="变换描写顺序：有时从整体到局部，有时从局部到整体；有时从上到下，有时从下到上；有时从外到内，有时从内到外。避免总是使用相同的描写顺序。",
    examples=[
        "先描写人物的眼睛（局部），再描写整个面部特征（整体）",
        "先写远处的山峦（远景），再写近处的房屋（近景），最后写脚下的花草（特写）",
        "先描写环境声音（听觉），再描写光线明暗（视觉），最后描写气温湿度（触觉）",
        "先写人物的动作（动态），再写服饰外貌（静态）"
    ],
    counter_examples=[
        "总是先写外貌，再写服装，再写动作",
        "总是从左到右，从上到下描写场景",
        "总是先视觉，再听觉，再嗅觉"
    ],
    is_system=True,
    author="系统",
    source="描写技巧多样化"
)

INFORMATION_DENSITY_CONTROL = WritingRule(
    id="information_density_control",
    name="信息密度控制",
    description="合理控制信息密度，避免信息过载或空洞",
    category=WritingRuleCategory.STRUCTURE,
    severity=RuleSeverity.RECOMMENDED,
    tags=["structure", "pacing", "information", "balance"],
    content="在密集的信息段落之后，应有相对舒缓的段落；在动作紧张的场景中，适当插入细节描写放缓节奏；在情感高潮时，聚焦关键细节而非全面描写。",
    examples=[
        "在激烈的打斗场景后，插入人物喘息、环境描写的舒缓段落",
        "在大量背景介绍后，用简短的对话或动作推进剧情",
        "在情感激烈的场景中，只描写最关键的动作和表情细节",
        "在复杂设定解释时，分多次在不同场景中透露信息"
    ],
    counter_examples=[
        "连续三页全是背景设定介绍，没有情节推进",
        "动作场景中每个动作都详细描写，节奏拖沓",
        "情感场景中同时描写过多细节，分散注意力",
        "重要信息被淹没在无关细节中"
    ],
    conditions=[
        {"type": "scene_type", "description": "根据场景类型调整密度"},
        {"type": "reader_fatigue", "description": "考虑读者阅读疲劳度"}
    ],
    is_system=True,
    author="系统",
    source="节奏控制与信息管理"
)

# ==================== 规则集合 ====================

SYSTEM_WRITING_RULES = [
    DIALOGUE_VOICE_CHARACTER,
    DIALOGUE_ACTION_INTERLEAVE,
    DIALOGUE_SPOKEN_FEATURES,
    DIALOGUE_IDENTITY_MATCH,
    SENTENCE_RHYTHM_VARIATION,
    SCENE_TRANSITION_TECHNIQUE,
    DESCRIPTION_ORDER_VARIED,
    INFORMATION_DENSITY_CONTROL,
]

# 按分类分组
RULES_BY_CATEGORY = {
    WritingRuleCategory.DIALOGUE: [
        DIALOGUE_VOICE_CHARACTER,
        DIALOGUE_ACTION_INTERLEAVE,
        DIALOGUE_SPOKEN_FEATURES,
        DIALOGUE_IDENTITY_MATCH,
    ],
    WritingRuleCategory.STRUCTURE: [
        SENTENCE_RHYTHM_VARIATION,
        SCENE_TRANSITION_TECHNIQUE,
        DESCRIPTION_ORDER_VARIED,
        INFORMATION_DENSITY_CONTROL,
    ],
}

# 按严重程度分组
RULES_BY_SEVERITY = {
    RuleSeverity.REQUIRED: [
        DIALOGUE_VOICE_CHARACTER,
        DIALOGUE_IDENTITY_MATCH,
    ],
    RuleSeverity.STRONG: [
        DIALOGUE_ACTION_INTERLEAVE,
        SENTENCE_RHYTHM_VARIATION,
    ],
    RuleSeverity.RECOMMENDED: [
        DIALOGUE_SPOKEN_FEATURES,
        SCENE_TRANSITION_TECHNIQUE,
        DESCRIPTION_ORDER_VARIED,
        INFORMATION_DENSITY_CONTROL,
    ],
}

# ==================== 系统内置规则集 ====================

RULE_SET_WEB_NOVEL = WritingRuleSet(
    id="rule_set_web_novel",
    name="网文爽文风格规则集",
    description="适用于网络爽文的写作规则集，强调节奏快、爽点密集、阅读轻松",
    rule_ids=[
        "dialogue_voice_character",
        "dialogue_action_interleave",
        "sentence_rhythm_variation",
        "information_density_control",
    ],
    rule_overrides={
        "information_density_control": {
            "severity": "required",
            "content": "保持高信息密度和快节奏，避免冗长描写。每章应有明确爽点或冲突推进。"
        },
        "sentence_rhythm_variation": {
            "severity": "strong",
            "content": "多使用短句和分段，创造快节奏阅读体验。重要情节使用长句加强氛围。"
        }
    },
    category=WritingRuleCategory.STYLE,
    tags=["web_novel", "爽文", "fast_paced", "entertainment"],
    target_genres=["fantasy", "xianxia", "urban", "system", "reincarnation"],
    is_system=True,
    author="系统",
    source="网文写作经验总结"
)

RULE_SET_ROMANCE = WritingRuleSet(
    id="rule_set_romance",
    name="晋江言情风格规则集",
    description="适用于晋江风格言情小说的写作规则集，强调情感描写、人物互动和细节刻画",
    rule_ids=[
        "dialogue_voice_character",
        "dialogue_action_interleave",
        "dialogue_spoken_features",
        "scene_transition_technique",
        "description_order_varied",
    ],
    rule_overrides={
        "dialogue_action_interleave": {
            "severity": "required",
            "content": "情感对话必须穿插细腻的动作、表情和微表情描写，展现人物内心活动。"
        },
        "description_order_varied": {
            "severity": "strong",
            "content": "注重人物外貌、服饰、环境的细节描写，顺序应从最能体现角色特质的部分开始。"
        }
    },
    category=WritingRuleCategory.STYLE,
    tags=["romance", "晋江", "情感", "细节", "character_driven"],
    target_genres=["modern_romance", "historical_romance", "sweet_love", "虐恋"],
    is_system=True,
    author="系统",
    source="言情小说写作技巧"
)

RULE_SET_LITERARY = WritingRuleSet(
    id="rule_set_literary",
    name="传统文学风格规则集",
    description="适用于传统文学作品的写作规则集，强调语言艺术、深度思考和文学性",
    rule_ids=[
        "dialogue_identity_match",
        "sentence_rhythm_variation",
        "scene_transition_technique",
        "description_order_varied",
        "information_density_control",
    ],
    rule_overrides={
        "sentence_rhythm_variation": {
            "severity": "required",
            "content": "精心设计句式节奏，利用长短句变化创造音乐性和韵律感。"
        },
        "dialogue_identity_match": {
            "severity": "required",
            "content": "对话必须严格符合人物身份、时代背景，并体现深层性格和主题。"
        },
        "information_density_control": {
            "severity": "strong",
            "content": "合理控制信息密度，在关键处使用密集意象和象征，留白处给予读者思考空间。"
        }
    },
    category=WritingRuleCategory.STYLE,
    tags=["literary", "traditional", "artistic", "deep", "symbolism"],
    target_genres=["literary_fiction", "realism", "historical", "philosophical"],
    is_system=True,
    author="系统",
    source="文学创作理论"
)

# 系统内置规则集列表
SYSTEM_WRITING_RULE_SETS = [
    RULE_SET_WEB_NOVEL,
    RULE_SET_ROMANCE,
    RULE_SET_LITERARY,
]