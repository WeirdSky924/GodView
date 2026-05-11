# -*- coding: utf-8 -*-
"""
网文小说写作规则数据
包含一套完整的、可复用的网文写作规范
"""

from typing import List, Dict, Any

# 网文写作规则数据
WEB_NOVEL_WRITING_RULES: List[Dict[str, Any]] = [
    # ==================== 对话类规则 ====================
    {
        "id": "dialogue_voice_character",
        "name": "角色声音差异化",
        "description": "不同角色应有独特的说话方式和用词习惯，避免角色同质化",
        "category": "dialogue",
        "severity": "required",
        "tags": ["对话", "角色塑造", "基础"],
        "content": "每个角色应有独特的说话风格、用词习惯和口头禅。避免所有角色说话方式雷同。角色语言应反映其背景、性格、教育程度和当前情绪。\n\n具体要求：\n1. 主角、配角、反派应有明显不同的说话风格\n2. 语言风格需符合角色身份（学者用书面语、市井用口语、贵族用敬语等）\n3. 可设计标志性口头禅或语气词\n4. 情绪变化时语言风格可适当变化，但核心特征保持一致",
        "examples": [
            "【学者】「依愚之见，此事恐有蹊跷，需从长计议。」",
            "【市井】「哎呦喂，这事儿可太邪乎了！」",
            "【武将】「末将请命，定斩敌将于马下！」",
            "【少年主角】「我来试试！大不了从头再来！」"
        ],
        "counter_examples": [
            "所有角色说话方式相同，无法通过对话区分角色",
            "古代背景角色使用现代网络用语",
            "粗犷武将说话文绉绉"
        ]
    },
    {
        "id": "dialogue_natural_flow",
        "name": "对话自然流畅",
        "description": "对话应符合日常交流习惯，避免生硬和刻意",
        "category": "dialogue",
        "severity": "strong",
        "tags": ["对话", "基础"],
        "content": "对话应自然流畅，符合人物性格和场景氛围。\n\n具体要求：\n1. 对话应有来有往，形成自然的交流节奏\n2. 可适当使用省略、打断、语气词增加真实感\n3. 避免大段独白式对话\n4. 对话内容应服务于人物塑造或剧情推进",
        "examples": [
            "「你说……他真的会来吗？」她低头摆弄着衣角。\n\n「会的。」少年握紧拳头，「他答应过。」",
            "「我……」他张了张嘴，话到嘴边又咽了回去。"
        ],
        "counter_examples": [
            "A：你觉得他为什么会这样做？\nB：我认为他这样做的原因有三点：第一……第二……第三……（过于书面化）"
        ]
    },
    {
        "id": "dialogue_no_info_dump",
        "name": "避免信息倾倒式对话",
        "description": "不要让角色说出他们本不该知道或不会说的话来向读者传达信息",
        "category": "dialogue",
        "severity": "required",
        "tags": ["对话", "新手必读"],
        "content": "严禁通过角色对话强行向读者灌输信息。角色不应该说出他们已经知道的事情，或者说出不符合场景的话。\n\n问题示例：\n- 两个亲兄弟互相介绍家世\n- 角色自言自语解释设定\n- 对方已知的信息还要详细说明\n\n正确做法：\n- 通过剧情发展自然展现信息\n- 在合适的场景引入新角色时介绍\n- 通过冲突或事件揭示背景",
        "examples": [
            "【错误】「大哥，我们的父亲林天豪二十年前被仇家所杀，这个仇我们一定要报！」\n\n【正确】「父亲……」望着牌位，兄弟二人同时跪下，眼神中燃烧着仇恨的火焰。"
        ],
        "counter_examples": [
            "「众所周知，我们王国已经建立三百年了，经历五代国王……」",
            "角色自言自语：「我叫张三，今年十八岁，是一名普通的高中生……」"
        ]
    },
    {
        "id": "dialogue_advance_plot",
        "name": "对话推动剧情",
        "description": "每段对话都应有其存在的意义，或塑造人物，或推进剧情",
        "category": "dialogue",
        "severity": "recommended",
        "tags": ["对话", "剧情"],
        "content": "对话不是填充字数的工具。每段对话都应至少满足以下之一：\n\n1. 揭示角色性格或关系\n2. 推进主线/支线剧情\n3. 制造冲突或悬念\n4. 埋下伏笔或呼应前文\n5. 提供必要信息（自然方式）\n\n如果一个对话场景不能明确其目的，考虑删除或改写。",
        "examples": [
            "【塑造性格】「输了就是输了，我林某从不找借口。」他抱拳一礼，转身离去。",
            "【推进剧情】「听说城南的废弃庙宇最近有异常光芒出现……」",
            "【制造冲突】「你救了他？你知不知道他是谁！」"
        ]
    },
    {
        "id": "dialogue_show_not_tell",
        "name": "对话展示而非告知",
        "description": "通过对话暗示和展示，而非直接告知读者",
        "category": "dialogue",
        "severity": "strong",
        "tags": ["对话", "技巧"],
        "content": "优秀的对话应该让读者自己去体会，而非把一切都说透。\n\n技巧：\n1. 言外之意：角色说的话和实际意思不同\n2. 欲言又止：暗示有隐情但不直接说明\n3. 顾左右而言他：回避话题暗示内心\n4. 反话：用相反的话表达真实意思",
        "examples": [
            "【暗示关系】「你……还留着这个？」她指着桌上的旧玉佩。\n\n「随手放的。」他迅速收回目光。",
            "【暗示身份】「十年了，您还是和当年一样……」老人的话戛然而止，似乎意识到了什么。"
        ]
    },

    # ==================== 结构类规则 ====================
    {
        "id": "structure_golden_opening",
        "name": "黄金开头三秒",
        "description": "章节开头三秒内必须抓住读者注意力",
        "category": "structure",
        "severity": "required",
        "tags": ["结构", "开篇", "核心"],
        "content": "网文读者注意力极其有限，每章开头必须在三秒内（约50字内）抓住读者。\n\n有效的开头方式：\n1. 动作开场：直接进入行动或冲突\n2. 悬念开场：抛出问题或异常\n3. 对话开场：以精彩对话开始\n4. 转折开场：出人意料的情境\n5. 危机开场：直接面对困境\n\n避免：\n- 大段景物描写\n- 冗长的背景介绍\n- 平淡无奇的日常",
        "examples": [
            "「林风，跪下！」一声暴喝响彻大殿。",
            "剑，已经架在了他的脖子上。",
            "所有人都以为他死了。但此刻，他正站在大殿门口。",
            "「我不是来投降的，」他扔下手中的断剑，「我是来取你们性命的。」"
        ],
        "counter_examples": [
            "清晨的阳光洒在大地上，鸟儿在枝头歌唱……（太平淡）",
            "林风是一个普通的少年，他今年十六岁……（太老套）"
        ]
    },
    {
        "id": "structure_chapter_hook",
        "name": "章节结尾钩子",
        "description": "每章结尾都要有钩子，吸引读者继续阅读",
        "category": "structure",
        "severity": "required",
        "tags": ["结构", "结尾", "核心"],
        "content": "章末钩子是留住读者的关键。每章结尾都要给读者一个继续阅读的理由。\n\n钩子类型：\n1. 悬念钩子：抛出未解答的问题\n2. 危机钩子：角色陷入困境\n3. 转折钩子：意外的新发展\n4. 期待钩子：即将发生的大事件\n5. 震惊钩子：颠覆认知的揭示\n\n黄金法则：让读者说「再看一章就睡」，然后看到天亮。",
        "examples": [
            "就在这时，他腰间的玉佩突然发出刺目的光芒……",
            "门缓缓打开，走出来的人，竟是三年前死去的师父！",
            "「你以为……你赢了吗？」反派嘴角勾起一抹诡异的笑。",
            "远处，一个黑影正缓缓逼近。"
        ],
        "counter_examples": [
            "今天真是太累了，林风决定好好休息一晚。（太平淡）",
            "这一章就这样结束了，明天又是新的一天。（无聊）"
        ]
    },
    {
        "id": "structure_golden_three_chapters",
        "name": "黄金三章法则",
        "description": "前三章必须完成核心设定展示和主角人设建立",
        "category": "structure",
        "severity": "strong",
        "tags": ["结构", "开篇", "网文核心"],
        "content": "网文黄金三章法则：前三章决定读者是否继续阅读。\n\n第一章：危机与金手指\n- 展示主角现状（通常是不利的）\n- 引入核心矛盾/危机\n- 金手指/机遇的苗头\n- 字数建议：2000-3000字\n\n第二章：金手指激活\n- 金手指正式获得或展现\n- 第一次小爽点\n- 主角性格展示\n- 树立第一个小目标\n\n第三章：初战告捷\n- 第一次使用金手指\n- 解决第一个小危机\n- 爽点释放\n- 引入更大的目标或矛盾\n\n注意事项：\n- 不要过多铺垫，快速进入主线\n- 主角人设要清晰讨喜\n- 世界观设定点到为止",
        "examples": [
            "【第一章示例】废柴主角被退婚羞辱→获得神秘传承\n【第二章示例】传承觉醒，实力大增\n【第三章示例】在族比中击败之前看不起他的人"
        ]
    },
    {
        "id": "structure_plot_twist",
        "name": "情节反转设计",
        "description": "合理使用反转增加阅读趣味",
        "category": "structure",
        "severity": "recommended",
        "tags": ["结构", "剧情", "技巧"],
        "content": "反转是网文的重要爽点来源，但需要合理设计。\n\n反转类型：\n1. 身份反转：看似敌人实为朋友，或反之\n2. 实力反转：看似弱者实为强者\n3. 目的反转：看似救人实为害人\n4. 局中局：一切都在计划中\n\n反转原则：\n- 必须有前期伏笔铺垫\n- 反转后读者恍然大悟而非困惑\n- 反转不能违背人物性格逻辑\n- 反转频次适中，避免审美疲劳",
        "examples": [
            "【伏笔】「大人，一切按计划进行。」黑衣人低声道。\n【反转】原来反派一直被主角利用而不自知。",
            "【伏笔】主角多次展现出超越境界的战斗直觉。\n【反转】体内沉睡着一头远古凶兽的血脉。"
        ]
    },

    # ==================== 风格类规则 ====================
    {
        "id": "style_concise_sentences",
        "name": "简洁有力句式",
        "description": "网文句子应简洁有力，避免长句堆砌",
        "category": "style",
        "severity": "strong",
        "tags": ["风格", "语言", "基础"],
        "content": "网文阅读场景多为手机快速阅读，句式应简洁有力。\n\n原则：\n1. 平均句长控制在15-25字\n2. 长短句交替，营造节奏\n3. 关键动作用短句强调\n4. 一个句子只表达一个意思\n5. 避免嵌套从句\n\n黄金比例：\n- 短句（10字内）：40%\n- 中句（10-20字）：40%\n- 长句（20字以上）：20%",
        "examples": [
            "剑出。\n血溅。\n人头落地。\n\n全场死寂。",
            "他没动。他在等。等一个机会。"
        ],
        "counter_examples": [
            "当林风看到那个站在远处山崖上的穿着一身黑色长袍手中握着一把泛着寒光的宝剑的少年时，他不禁想起了三年前……（太长）"
        ]
    },
    {
        "id": "style_show_dont_tell",
        "name": "展示而非告知",
        "description": "用画面和动作展现，而非直接陈述",
        "category": "style",
        "severity": "required",
        "tags": ["风格", "核心技巧"],
        "content": "网文最核心的写作技巧：展示而非告知。\n\n错误示范：\n- 他很愤怒。\n- 她很美丽。\n- 这是一个危险的地方。\n\n正确示范：\n- 他攥紧拳头，青筋暴起。\n- 她的容颜让月光都黯然失色。\n- 空气中弥漫着血腥味，远处不时传来野兽的嚎叫。\n\n技巧：\n1. 用动作表现情绪\n2. 用环境暗示氛围\n3. 用对话揭示性格\n4. 用细节代替概括",
        "examples": [
            "【愤怒】桌子在他掌下寸寸碎裂。\n【紧张】她的手指无意识地绞着衣角。\n【决心】他抬起头，眼中的犹豫已经消失。",
            "【美丽】周围的人不自觉地停下脚步，目光都被她吸引。"
        ],
        "counter_examples": [
            "他非常非常愤怒，同时也很悲伤，内心充满了复杂的情感。（直接告知）"
        ]
    },
    {
        "id": "style_avoid_purple_prose",
        "name": "避免过度华丽辞藻",
        "description": "网文风格应直接有力，避免过度修饰",
        "category": "style",
        "severity": "recommended",
        "tags": ["风格", "语言"],
        "content": "网文追求的是「爽」和「快」，过度华丽的辞藻会拖慢阅读节奏。\n\n应避免：\n- 大量生僻成语堆砌\n- 冗长的景物描写\n- 过度的心理活动描写\n- 不必要的修辞手法\n\n应该：\n- 用词精准直接\n- 描写点到为止\n- 快速推进剧情\n- 让读者代入而非旁观",
        "examples": [
            "【过度】那轮皎洁的明月宛如白玉盘般高悬于苍穹之中，清冷的光辉如瀑布般倾泻而下，给这寂静的山谷披上了一层银纱……\n\n【简洁】月色如水，洒落山谷。"
        ]
    },
    {
        "id": "style_de_ai_natural_prose",
        "name": "去AI感自然文风",
        "description": "消除模板化、解释腔和助手式口吻，让正文像具体场景而不是生成摘要",
        "category": "style",
        "severity": "required",
        "application_mode": "always_postcheck",
        "tags": ["风格", "去AI感", "自然化", "文笔", "核心"],
        "content": "正文必须消除明显 AI 感和模板化表达，读起来应像人物正在经历场景，而不是旁白在总结一段设定。\n\n硬性禁忌：\n1. 禁止助手式、作文式、报告式表达，例如「这不仅是……更是……」「与此同时……也意味着……」「在这一刻，他终于明白……」连续出现。\n2. 禁止用抽象标签替代画面，例如只写「复杂的情绪翻涌」「一种难以言说的感觉」「空气中弥漫着紧张气氛」。\n3. 禁止段落节奏过度工整：连续用同一种开头、同一种三段式排比、同一种总结句收尾。\n4. 禁止对话像设定说明书：角色不应把双方已知的信息完整解释给对方。\n5. 禁止所有角色使用同一种冷静、完整、漂亮的解释腔。\n\n自然化要求：\n1. 用动作、停顿、错词、回避、打断、身体反应和环境反馈承载情绪。\n2. 每个主要角色的句子长度、用词习惯、回避方式和攻击性都要不同。\n3. 叙述要保留生活噪音和不完美反应，不要把每段都磨成整齐结论。\n4. 情绪高点优先给读者看见具体后果，而不是替读者解释感受。\n5. 输出前自检：删掉可有可无的总结句、套话转折和抽象情绪名词。",
        "examples": [
            "【AI感】这一刻，林默终于明白，这不仅是一场战斗，更是他命运的转折点。\n【自然】林默盯着掌心的血。三秒后，他把通讯器捏碎，声音低得几乎听不见：「开门。」",
            "【AI感】她的内心充满了复杂的情绪，既害怕又坚定。\n【自然】她把门锁拧了两次。第二次没拧动，才发现自己的手一直在抖。"
        ],
        "counter_examples": [
            "空气中弥漫着一种无法言说的紧张感，仿佛所有人都意识到，真正的危机才刚刚开始。",
            "他知道，自己必须做出选择。这不仅关系到他的未来，也关系到整个世界的命运。"
        ]
    },
    {
        "id": "style_web_novel_pace",
        "name": "网文快节奏",
        "description": "保持紧凑的叙事节奏，不拖沓",
        "category": "style",
        "severity": "strong",
        "tags": ["风格", "节奏", "核心"],
        "content": "网文的核心竞争力是快节奏、高爽点密度。\n\n节奏控制原则：\n1. 每500字应有至少一个小看点\n2. 每2000字应有至少一个爽点或转折\n3. 不超过300字的纯环境描写\n4. 不超过500字的纯心理活动\n5. 避免无意义的过渡段落\n\n紧凑技巧：\n- 删掉「他心想」「他觉得」等过渡词\n- 动作直接连着反应\n- 用对话代替心理独白\n- 时间线紧凑，不要跳跃太大",
        "examples": [
            "【拖沓】林风想了想，觉得这个提议不错，但是又有些担心，万一失败了怎么办？他陷入了沉思，过了好一会儿，他终于下定了决心……\n\n【紧凑】林风沉吟片刻，眼中精光一闪：「干！」"
        ]
    },

    # ==================== 角色塑造类规则 ====================
    {
        "id": "character_protagonist_consistency",
        "name": "主角人设一致性",
        "description": "主角性格行为必须前后一致，不OOC",
        "category": "character",
        "severity": "required",
        "tags": ["角色", "主角", "基础"],
        "content": "主角是读者的代入点，人设崩塌会让读者瞬间出戏。\n\n主角人设要求：\n1. 核心性格稳定：热血/腹黑/谨慎/霸道等基调不变\n2. 行为逻辑自洽：不做出与性格矛盾的事\n3. 成长有迹可循：性格变化需有事件触发\n4. 有明显优点也有小缺点：更真实可爱\n\n常见主角类型及禁忌：\n- 热血型：不能变得精于算计\n- 腹黑型：不能突然冲动莽撞\n- 谨慎型：不能轻易相信陌生人\n- 杀伐果断型：不能突然圣母心泛滥",
        "examples": [
            "【正确】谨慎型主角发现陷阱后选择绕道，即使错过宝物也不冒险。\n\n【错误】谨慎型主角突然热血上头，明知是陷阱也要硬闯。"
        ],
        "counter_examples": [
            "前期「人不犯我我不犯人」的主角，后期突然变得嗜杀成性",
            "一直冷静理智的主角，为了救一个刚认识的路人冒险送死"
        ]
    },
    {
        "id": "character_supporting_functional",
        "name": "配角功能性设计",
        "description": "配角设计应服务于剧情和主角塑造",
        "category": "character",
        "severity": "recommended",
        "tags": ["角色", "配角"],
        "content": "配角不是越丰满越好，而是要有明确的功能定位。\n\n配角功能类型：\n1. 推进型：推动剧情发展（情报贩子、引路人）\n2. 对比型：衬托主角（废柴朋友、天才对手）\n3. 辅助型：提供帮助（师父、金手指引导者）\n4. 阻碍型：制造障碍（反派、竞争对手）\n5. 调节型：调节气氛（搞笑担当、吐槽役）\n\n设计原则：\n- 功能明确，不喧宾夺主\n- 重要配角可以有独立支线\n- 配角数量适中，避免读者记不住",
        "examples": [
            "【调节型】每当气氛凝重时，配角张胖子就会来一句：「话说咱们是不是跑错方向了？」打破沉默。"
        ]
    },
    {
        "id": "character_villain_smart",
        "name": "反派智商在线",
        "description": "优秀的反派能提升整体故事质量",
        "category": "character",
        "severity": "strong",
        "tags": ["角色", "反派", "进阶"],
        "content": "低智商反派是网文的大忌，会让爽点打折。\n\n反派设计原则：\n1. 有合理动机：为利益/为复仇/为信仰\n2. 有能力威胁：能真正给主角造成麻烦\n3. 有弱点可击：不是无敌，只是强大\n4. 有层次深度：不是纯粹的恶，有自己的逻辑\n\n反派类型：\n- 阴谋型：善于布局，心机深沉\n- 霸道型：实力碾压，明着来\n- 伪君子型：表面正派，暗中算计\n- 执念型：为执念不择手段\n\n禁止：\n- 为了作恶而作恶\n- 反派话太多导致被翻盘\n- 明明能直接杀主角却各种拖延",
        "examples": [
            "【聪明反派】发现主角是威胁后，立即派出足够的力量抹杀，不再给成长机会。\n\n【愚蠢反派】「哈哈哈，我要让你看着你的朋友一个个死去！」（给主角创造了翻盘机会）"
        ]
    },
    {
        "id": "character_op_avoid_mary_sue",
        "name": "避免过度完美人设",
        "description": "完美的角色不仅无聊，还会让读者反感",
        "category": "character",
        "severity": "recommended",
        "tags": ["角色", "技巧"],
        "content": "玛丽苏/龙傲天式角色会让读者失去代入感。\n\n问题表现：\n- 全能型：什么都擅长，没有短板\n- 人见人爱：所有角色都喜欢他\n- 运气爆棚：好运气随机掉落\n- 道德完美：永远站在道德制高点\n\n改进方法：\n- 给主角一个真实的缺点（如贪财、傲娇、怕死）\n- 让有人不喜欢主角（增加冲突）\n- 好运伴随风险或代价\n- 允许主角有私心和小算盘",
        "examples": [
            "【完美】他实力最强、人缘最好、从不犯错、是所有人的偶像。\n\n【有血有肉】他实力强但贪财，帮人办事要先谈价；虽然傲娇但内心善良，嘴上不饶人行动上却会保护弱者。"
        ]
    },

    # ==================== 剧情类规则 ====================
    {
        "id": "plot_satisfaction_density",
        "name": "爽点密度控制",
        "description": "合理控制爽点出现频率，保持读者期待",
        "category": "plot",
        "severity": "required",
        "tags": ["剧情", "爽点", "核心"],
        "content": "爽点是网文的生命线，需要科学控制密度。\n\n爽点类型：\n1. 打脸型：被轻视后证明实力\n2. 逆袭型：从弱到强的突破\n3. 收获型：获得宝物/美女/权力\n4. 复仇型：报仇雪恨\n5. 装逼型：低调后被震惊\n6. 收小弟型：强者折服\n\n密度控制：\n- 小爽点：每500-800字一个\n- 中爽点：每2000-3000字一个\n- 大爽点：每章或每两章一个\n- 爽点之间要有铺垫和期待\n\n爽点公式：期待→压抑→释放\n压抑越强，释放越爽。",
        "examples": [
            "【打脸爽点】\n期待：即将到来的比武\n压抑：对手嘲讽、众人不看好\n释放：一招击败对手，震惊全场"
        ]
    },
    {
        "id": "plot_golden_finger_reasonable",
        "name": "金手指合理性",
        "description": "金手指是网文标配，但要有合理性限制",
        "category": "plot",
        "severity": "strong",
        "tags": ["剧情", "金手指", "核心"],
        "content": "金手指是主角的优势来源，但不能无敌。\n\n金手指设计原则：\n1. 有代价：使用需付出代价（体力/寿命/资源）\n2. 有限制：等级限制、次数限制、时间限制\n3. 有来源：解释为什么获得（血脉/传承/系统）\n4. 有成长：随主角成长而解锁新能力\n\n禁止：\n- 无代价无限使用的金手指\n- 突然出现新功能救场\n- 金手指让主角完全无敌\n\n常见金手指类型：\n- 穿越者记忆\n- 神秘传承/血脉\n- 系统辅助\n- 随身老爷爷/空间",
        "examples": [
            "【合理】血脉力量强大，但每次使用消耗生命力，主角需要寻找修复之法。\n\n【不合理】系统突然发布任务送神级装备，主角瞬间无敌。"
        ]
    },
    {
        "id": "plot_face_slapping_technique",
        "name": "打脸套路技巧",
        "description": "打脸是网文经典爽点，需要掌握技巧",
        "category": "plot",
        "severity": "recommended",
        "tags": ["剧情", "爽点", "套路"],
        "content": "打脸是网文最常用的爽点形式，使用频率高但需要技巧。\n\n打脸三要素：\n1. 铺垫：反派/对手的嚣张\n2. 压抑：主角暂时被轻视\n3. 反转：主角展现真正实力\n\n打脸节奏：\n- 先抑后扬，抑得越低扬得越高\n- 反派言论要足够嚣张\n- 反转要干脆利落\n- 观众震惊反应增强效果\n\n打脸禁忌：\n- 打脸太过频繁，失去惊喜感\n- 被打脸的角色毫无分量\n- 打脸后反派立即遗忘继续嚣张\n\n打脸后续：\n- 可引发更大冲突\n- 可收获追随者\n- 可推进主线剧情",
        "examples": [
            "【经典打脸】\n反派：「废物也敢来参加大比？赶紧滚回去！」（嚣张）\n众人：「这人是谁？敢这么说话？」\n主角：（沉默不语）\n比赛开始。\n主角一招击败反派。（反转）\n全场震惊：「这……这是天才！」"
        ]
    },
    {
        "id": "plot_conflict_escalation",
        "name": "冲突升级设计",
        "description": "冲突应层层递进，不断升级",
        "category": "plot",
        "severity": "strong",
        "tags": ["剧情", "冲突", "核心"],
        "content": "冲突是故事的引擎，需要持续升级。\n\n冲突升级模式：\n1. 个人冲突 → 家族冲突 → 宗门冲突 → 国家冲突 → 世界冲突\n2. 口角 → 比试 → 生死战 → 灭门战\n3. 小反派 → 中反派 → 大反派 → 最终BOSS\n\n升级原则：\n- 每次冲突解决后，引入更大的矛盾\n- 后期敌人不能弱于前期\n- 主角实力与敌人同步成长\n\n冲突来源：\n- 利益冲突（宝物、资源、地位）\n- 情感冲突（爱情、友情、仇恨）\n- 理念冲突（道不同不相为谋）",
        "examples": [
            "【冲突升级链】\n1. 立威：击败家族中的天才\n2. 复仇：家族被灭，追查幕后黑手\n3. 升级：发现黑手是某宗门长老\n4. 再升级：宗门只是某个大势力的棋子\n5. 最终：对抗操控一切的幕后黑手"
        ]
    },
    {
        "id": "plot_foreshadowing_payoff",
        "name": "伏笔铺垫与回收",
        "description": "伏笔让故事更有深度，回收让读者有惊喜",
        "category": "plot",
        "severity": "strong",
        "tags": ["剧情", "伏笔", "技巧"],
        "content": "伏笔是网文的高级技巧，能让剧情更有说服力。\n\n伏笔类型：\n1. 人物伏笔：角色身份、隐藏实力\n2. 物品伏笔：宝物特殊功能、传承秘密\n3. 事件伏笔：看似普通的对话或事件\n\n伏笔原则：\n- 埋设自然：不影响正常阅读\n- 回收合理：不能硬转\n- 时间适中：太短读者不记得，太长读者等不及\n- 可多重伏笔：交织在一起更有惊喜\n\n伏笔技巧：\n- 草蛇灰线：多处小细节暗示同一件事\n- 误导：让读者以为A，实际是B\n- 呼应：前文埋设，后文呼应",
        "examples": [
            "【埋设】第一章：主角偶尔会感到心脏异常跳动。\n【回收】第一百章：觉醒血脉时，才发现心脏里一直封印着神兽之力。\n\n【误导】所有线索指向A是内奸。\n【反转】实际是B，A是在查B时被栽赃。"
        ]
    },

    # ==================== 节奏类规则 ====================
    {
        "id": "pacing_satisfaction_buildup_ratio",
        "name": "爽点与铺垫配比",
        "description": "合理的铺垫让爽点更有分量",
        "category": "pacing",
        "severity": "strong",
        "tags": ["节奏", "爽点", "核心"],
        "content": "爽点需要铺垫来积蓄力量，铺垫越充分，释放越爽。\n\n黄金配比：\n- 铺垫：爽点 ≈ 3:1 或 4:1\n- 小爽点：铺垫300-500字\n- 中爽点：铺垫1000-2000字\n- 大爽点：铺垫一整章或多章\n\n铺垫内容：\n1. 压抑：主角被低估、被轻视\n2. 期待：暗示即将发生的大事件\n3. 危机：时间紧迫、形势严峻\n4. 准备：主角暗中积蓄力量\n\n节奏把控：\n- 不能一直压抑，中间有小释放\n- 不能一直爽，会审美疲劳\n- 波峰波谷交替，波浪式推进",
        "examples": [
            "【章节节奏】\n- 第1章：铺垫（危机+压抑）\n- 第2章：铺垫继续+小释放\n- 第3章：大爽点释放\n- 第4章：过渡+新铺垫开始"
        ]
    },
    {
        "id": "pacing_conflict_resolution",
        "name": "冲突解决节奏",
        "description": "冲突不能拖太久也不能解决太快",
        "category": "pacing",
        "severity": "recommended",
        "tags": ["节奏", "冲突"],
        "content": "冲突持续时间和解决方式影响阅读体验。\n\n冲突时长：\n- 小冲突：1章内解决\n- 中冲突：3-5章\n- 大冲突：10-20章（可分多个阶段）\n- 主线冲突：贯穿全文\n\n解决节奏：\n1. 冲突爆发→升级→高潮→解决→后续\n2. 不能太容易：削弱成就感\n3. 不能太拖沓：消耗读者耐心\n4. 解决要有高潮点\n\n常见问题：\n- 冲突刚爆发就解决了（太草率）\n- 一个冲突拖了几十章（太拖沓）\n- 解决方式过于巧合（机械降神）",
        "examples": [
            "【小冲突】有人在酒馆挑衅主角→主角当场教训→一章内结束。\n【大冲突】宗门大比→预选赛→正赛→决赛→引发更大矛盾→多章节推进。"
        ]
    },
    {
        "id": "pacing_rest_periods",
        "name": "休息期设计",
        "description": "高潮之后需要休息期，让读者喘口气",
        "category": "pacing",
        "severity": "recommended",
        "tags": ["节奏", "技巧"],
        "content": "持续高潮会让读者疲劳，需要合理安排休息期。\n\n休息期作用：\n1. 让读者喘口气\n2. 展示角色日常一面\n3. 推进感情线或支线\n4. 埋设新伏笔\n\n休息期内容：\n- 日常互动：有趣的对话、生活场景\n- 收获整理：盘点获得的资源\n- 感情发展：与女主/伙伴的互动\n- 世界观展开：了解更多设定\n\n休息期长度：\n- 大高潮后：1-2章\n- 中高潮后：半章到1章\n- 小高潮后：几百字到半章\n\n注意：\n- 休息期不等于无聊\n- 要有看点，只是节奏放慢",
        "examples": [
            "【大战后休息】\n主角大战之后回到住处，盘点这次收获：\n- 获得XXX功法\n- 收服XXX小弟\n- 与XXX关系更进一步\n同时，暗示新的危机正在逼近……"
        ]
    },

    {
        "id": "long_novel_slow_burn_pacing",
        "name": "长篇慢热推进",
        "description": "长篇网文不能按短篇节奏快速解决核心矛盾",
        "category": "pacing",
        "severity": "required",
        "application_mode": "always_postcheck",
        "tags": ["长篇", "慢热", "节奏", "核心"],
        "conditions": [
            {"type": "agent_type", "values": ["writer", "evaluator", "plot_outline", "setting"]},
            {"type": "scenario", "values": ["workflow_chapter_generation", "rewrite_by_review", "chapter_quality_review", "outline_quality_review", "generate_chapter_outline", "validate_long_novel_pacing", "workflow_context", "outline_revision_proposal"]}
        ],
        "content": "本项目按长篇慢热网文处理，不按短篇小说节奏推进。当前章节只解决当前阶段的局部问题，不能提前替代后续章节的核心高潮，不能把短期冲突直接升级为终局矛盾，也不能在早期章节快速揭开世界底层真相。Writer 必须按已审批大纲推进；Plot Outline 必须保留阶段性递进；Evaluator 必须拦截短篇化推进。",
        "examples": [
            "【正确】本章解决地方恶霸引发的小冲突，同时留下背后势力的线索。",
            "【错误】第三章直接让最终幕后黑手现身并被主角击败。"
        ],
        "counter_examples": [
            "为了制造爽点，提前让主角发现终局真相并解决主线危机。"
        ]
    },
    {
        "id": "long_novel_villain_tier_progression",
        "name": "反派层级递进",
        "description": "最终反派和高阶势力早期只能间接影响剧情",
        "category": "plot",
        "severity": "required",
        "application_mode": "always_postcheck",
        "tags": ["长篇", "反派", "势力层级", "核心"],
        "conditions": [
            {"type": "agent_type", "values": ["writer", "evaluator", "plot_outline", "setting"]},
            {"type": "scenario", "values": ["workflow_chapter_generation", "rewrite_by_review", "chapter_quality_review", "outline_quality_review", "generate_chapter_outline", "validate_long_novel_pacing", "workflow_context", "outline_revision_proposal"]}
        ],
        "content": "反派和势力必须按层级递进。早期章节不得让最终反派、高阶势力核心或世界底层真相正面登场。高阶存在可以通过传闻、代理人、符号、后果、禁忌记录、局部异象等方式间接出现，但不能与主角直接摊牌，也不能让主角理解其全貌。Evaluator 必须检查越级反派、越级势力和提前揭示。",
        "examples": [
            "【正确】主角只遇到高阶势力的外围执事，真正核心只以徽记和传闻出现。",
            "【错误】第一卷初期最终反派亲自现身解释全部计划。"
        ],
        "counter_examples": [
            "用最终反派亲自出场来解决当前小冲突。"
        ]
    },
    {
        "id": "long_novel_no_author_view_golden_finger_term",
        "name": "禁止作者视角金手指术语",
        "description": "角色不能使用金手指等作者/读者视角词汇认知自身能力",
        "category": "style",
        "severity": "required",
        "application_mode": "always_postcheck",
        "tags": ["长篇", "金手指", "角色认知", "核心"],
        "conditions": [
            {"type": "agent_type", "values": ["writer", "evaluator", "plot_outline"]},
            {"type": "scenario", "values": ["workflow_chapter_generation", "rewrite_by_review", "chapter_quality_review", "outline_quality_review", "generate_chapter_outline", "validate_long_novel_pacing"]}
        ],
        "content": "主角和故事内角色不能使用“金手指”这种作者视角、读者视角或网文评论术语来称呼自身能力。角色只能按世界内认知理解能力，例如传承、异能、血脉、系统提示、古物、秘法、神通、诅咒等。Evaluator 必须将角色台词或内心独白中的“金手指”术语判为问题；Plot Outline 也不能把该词写入角色可见信息。",
        "examples": [
            "【正确】他低声道：这枚玉佩，或许就是师父说过的传承之钥。",
            "【错误】主角心想：我的金手指终于到账了。"
        ],
        "counter_examples": [
            "角色在正文中直接说自己有金手指。"
        ]
    },
    {
        "id": "long_novel_no_undefined_crisis_resolution",
        "name": "禁止未定义设定救场",
        "description": "关键危机必须由已铺垫或已落库资源解决",
        "category": "plot",
        "severity": "required",
        "application_mode": "always_postcheck",
        "tags": ["长篇", "危机解决", "设定", "核心"],
        "conditions": [
            {"type": "agent_type", "values": ["writer", "evaluator", "plot_outline", "setting"]},
            {"type": "scenario", "values": ["workflow_chapter_generation", "rewrite_by_review", "chapter_quality_review", "outline_quality_review", "generate_chapter_outline", "validate_long_novel_pacing", "workflow_context", "outline_revision_proposal"]}
        ],
        "content": "关键危机不能靠临时发明的未定义设定、未铺垫能力、未落库宝物或突然出现的未知人物解决。危机解决必须来自已审批大纲、已有角色/设定/地点/道具资源、前文铺垫，或已批准的资源补全需求。若缺少必要资源，Plot Outline/Setting 应提出资源需求或修订草案，Writer 不得直接硬写，Evaluator 必须拦截机械降神式救场。",
        "examples": [
            "【正确】主角用前文得到但未完全理解的符箓拖延敌人，并付出代价。",
            "【错误】危急时刻突然出现从未提过的上古神剑自动认主。"
        ],
        "counter_examples": [
            "为了解决本章危机临时新增一个无铺垫的救命设定。"
        ]
    },
    {
        "id": "long_novel_character_resource_gate",
        "name": "命名角色资源门禁",
        "description": "新命名角色正面出场前必须有角色资源或批准需求",
        "category": "character",
        "severity": "required",
        "application_mode": "always_postcheck",
        "tags": ["长篇", "角色资源", "出场权限", "核心"],
        "conditions": [
            {"type": "agent_type", "values": ["writer", "evaluator", "plot_outline", "setting"]},
            {"type": "scenario", "values": ["workflow_chapter_generation", "rewrite_by_review", "chapter_quality_review", "outline_quality_review", "generate_chapter_outline", "validate_long_novel_pacing", "workflow_context", "outline_revision_proposal"]}
        ],
        "content": "关键命名角色、持续出场角色和正面推动剧情的新角色，出场前必须存在角色资源，或来自已批准/已 resolved 的角色补充需求。Writer 不得临场发明关键命名角色；Plot Outline 发现需要新角色时应生成资源需求；Setting 不能把缺失角色硬塞进设定；Evaluator 必须检查 mention-only、inactive、forbidden 或未落库角色是否被正面出场。一次性路人可短暂无名出现，但不得承担关键剧情功能。",
        "examples": [
            "【正确】大纲需要新医师推动剧情，先生成角色资源需求，补齐后再出场。",
            "【错误】正文突然出现名叫玄霜真人的强者救主角，系统中没有任何角色资源。"
        ],
        "counter_examples": [
            "未落库命名角色直接解决关键冲突。"
        ]
    },
    {
        "id": "long_novel_chapter_event_progression",
        "name": "章节必须有事件推进",
        "description": "每章不能只有聊天、解释或静态设定展示",
        "category": "structure",
        "severity": "required",
        "application_mode": "always_postcheck",
        "tags": ["长篇", "章节推进", "事件", "核心"],
        "conditions": [
            {"type": "agent_type", "values": ["writer", "evaluator", "plot_outline"]},
            {"type": "scenario", "values": ["workflow_chapter_generation", "rewrite_by_review", "chapter_quality_review", "outline_quality_review", "generate_chapter_outline", "validate_long_novel_pacing"]}
        ],
        "content": "每章必须发生至少一个可复述的实际事件，并产生清晰的因果结果。不能只有人物聊天、心理活动、世界观说明或静态铺垫。章节应说明：前因是什么、触发事件是什么、角色采取了什么行动、结果如何、对后续产生什么影响。Evaluator 必须拦截“只有对话没有事件推进”的章节；Plot Outline 必须在大纲中明确本章事件链。",
        "examples": [
            "【正确】两人谈话中发现线索，决定夜探祠堂，并因此触发守卫追捕。",
            "【错误】整章都在解释设定和寒暄，没有任何行动结果。"
        ],
        "counter_examples": [
            "章节结尾状态与开头完全一样，只增加了闲聊。"
        ]
    },
    {
        "id": "format_paragraph_length",
        "name": "段落长度控制",
        "description": "手机阅读场景下段落不宜过长",
        "category": "format",
        "severity": "strong",
        "tags": ["格式", "阅读体验"],
        "content": "手机阅读对段落长度有特殊要求。\n\n段落原则：\n1. 单段不超过3-4行（手机屏幕）\n2. 一个意思一个段落\n3. 对话单独成段\n4. 动作描写可短句成段\n\n视觉效果：\n- 屏幕上要有足够的留白\n- 不能出现大段文字墙\n- 方便快速扫读\n\n分段技巧：\n- 对话独立成段\n- 心理活动用短段\n- 动作描写快速切分\n- 环境描写适度控制",
        "examples": [
            "【好】\n他抬起头。\n\n「你来干什么？」\n\n「来杀你。」\n\n剑光闪过。\n\n人头落地。\n\n【不好】\n他抬起头，冷冷地看着来人，眼中闪过一丝杀意，沉声问道：「你来干什么？」来人也不废话，直接拔剑道：「来杀你。」话音未落，剑光闪过，一颗人头已经落地，鲜血喷涌而出。"
        ]
    },
    {
        "id": "format_dialogue_formatting",
        "name": "对话格式规范",
        "description": "对话格式应统一且易读",
        "category": "format",
        "severity": "recommended",
        "tags": ["格式", "对话"],
        "content": "规范的对话格式提升阅读体验。\n\n格式要求：\n1. 对话用中文双引号或书名号\n2. 对话独立成段\n3. 说话人可省略（从上下文推断）\n4. 动作描写可插入对话中\n\n对话格式示例：\n- 简单对话：「内容。」\n- 带动作：「内容。」他转身离去。\n- 动作在前：他皱眉道：「内容。」\n- 分段对话：「内容，」他顿了顿，「继续说。」\n\n常见问题：\n- 引号使用不一致\n- 对话与动作混在一起\n- 说话人不明确",
        "examples": [
            "「你是谁？」他警惕地后退一步。\n\n「你可以叫我……老师。」来人微微一笑。\n\n「老师？」他愣住了，「我不认识你。」\n\n「以后会认识的。」那人转身消失在黑暗中。"
        ]
    }
]

# 网文写作规则集
WEB_NOVEL_RULE_SETS: List[Dict[str, Any]] = [
    {
        "id": "rule_set_web_novel_basics",
        "name": "网文基础规范",
        "description": "新手必读的基础写作规范，包含最核心的写作要求",
        "rule_ids": [
            "dialogue_voice_character",
            "dialogue_no_info_dump",
            "structure_golden_opening",
            "structure_chapter_hook",
            "style_show_dont_tell",
            "style_de_ai_natural_prose",
            "character_protagonist_consistency",
            "plot_satisfaction_density",
            "long_novel_slow_burn_pacing",
            "long_novel_villain_tier_progression",
            "long_novel_no_author_view_golden_finger_term",
            "long_novel_no_undefined_crisis_resolution",
            "long_novel_character_resource_gate",
            "long_novel_chapter_event_progression",
            "format_paragraph_length"
        ],
        "category": "style",
        "tags": ["基础", "新手必读", "核心"],
        "target_genres": ["fantasy", "xianxia", "urban", "history", "scifi"],
        "is_system": True
    },
    {
        "id": "rule_set_web_novel_advanced",
        "name": "网文进阶技巧",
        "description": "提升作品质量的进阶写作技巧",
        "rule_ids": [
            "dialogue_show_not_tell",
            "structure_golden_three_chapters",
            "structure_plot_twist",
            "style_web_novel_pace",
            "style_de_ai_natural_prose",
            "character_villain_smart",
            "plot_golden_finger_reasonable",
            "plot_face_slapping_technique",
            "plot_foreshadowing_payoff",
            "pacing_satisfaction_buildup_ratio",
            "long_novel_slow_burn_pacing",
            "long_novel_villain_tier_progression",
            "long_novel_no_author_view_golden_finger_term",
            "long_novel_no_undefined_crisis_resolution",
            "long_novel_character_resource_gate",
            "long_novel_chapter_event_progression"
        ],
        "category": "style",
        "tags": ["进阶", "技巧", "质量提升"],
        "target_genres": ["fantasy", "xianxia", "urban", "history", "scifi"],
        "is_system": True
    },
    {
        "id": "rule_set_xianxia_novel",
        "name": "仙侠玄幻专用规则",
        "description": "适用于仙侠、玄幻类网文的专项规则",
        "rule_ids": [
            "dialogue_voice_character",
            "structure_golden_opening",
            "structure_chapter_hook",
            "style_concise_sentences",
            "character_protagonist_consistency",
            "plot_golden_finger_reasonable",
            "plot_conflict_escalation",
            "plot_satisfaction_density"
        ],
        "category": "style",
        "tags": ["仙侠", "玄幻", "修真"],
        "target_genres": ["xianxia", "fantasy"],
        "is_system": True
    },
    {
        "id": "rule_set_urban_novel",
        "name": "都市小说专用规则",
        "description": "适用于都市、现代类网文的专项规则",
        "rule_ids": [
            "dialogue_natural_flow",
            "dialogue_no_info_dump",
            "structure_golden_opening",
            "structure_chapter_hook",
            "style_show_dont_tell",
            "character_protagonist_consistency",
            "character_op_avoid_mary_sue",
            "plot_satisfaction_density"
        ],
        "category": "style",
        "tags": ["都市", "现代", "都市异能"],
        "target_genres": ["urban", "urban_fantasy"],
        "is_system": True
    }
]


def get_all_writing_rules() -> List[Dict[str, Any]]:
    """获取所有写作规则"""
    return WEB_NOVEL_WRITING_RULES


def get_all_rule_sets() -> List[Dict[str, Any]]:
    """获取所有规则集"""
    return WEB_NOVEL_RULE_SETS


def get_rule_by_id(rule_id: str) -> Dict[str, Any] | None:
    """根据ID获取规则"""
    for rule in WEB_NOVEL_WRITING_RULES:
        if rule["id"] == rule_id:
            return rule
    return None


def get_rules_by_category(category: str) -> List[Dict[str, Any]]:
    """根据分类获取规则"""
    return [rule for rule in WEB_NOVEL_WRITING_RULES if rule["category"] == category]


def get_rules_by_tag(tag: str) -> List[Dict[str, Any]]:
    """根据标签获取规则"""
    return [rule for rule in WEB_NOVEL_WRITING_RULES if tag in rule.get("tags", [])]
