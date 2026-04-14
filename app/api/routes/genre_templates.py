"""
题材模板管理 API
GodView v9: 题材特化模板系统

提供不同题材的小说创作专属模板和指导
"""

from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from enum import Enum

from app.services.skill_service import SkillService

router = APIRouter(prefix="/api/genre-templates", tags=["Genre Templates"])


class GenreType(str, Enum):
    """题材类型"""
    XUANHUAN = "xuanhuan"       # 玄幻/仙侠
    URBAN = "urban"             # 都市
    HISTORY = "history"         # 历史军事
    SCIFI = "scifi"             # 科幻
    GAME = "game"               # 游戏


class GenreTemplateBase(BaseModel):
    """题材模板基础"""
    genre_type: GenreType = Field(..., description="题材类型")
    name: str = Field(..., description="模板名称")
    description: str = Field(..., description="模板描述")


class GenreTemplateDetail(GenreTemplateBase):
    """题材模板详情"""
    # 核心元素
    core_elements: List[str] = Field(default_factory=list, description="核心元素")
    power_system: Optional[Dict[str, Any]] = Field(None, description="战力体系")
    world_structure: Optional[Dict[str, Any]] = Field(None, description="世界观结构")

    # 剧情模板
    plot_patterns: List[Dict[str, Any]] = Field(default_factory=list, description="剧情模式")
    conflict_types: List[Dict[str, Any]] = Field(default_factory=list, description="冲突类型")
    climax_patterns: List[Dict[str, Any]] = Field(default_factory=list, description="高潮模式")

    # 角色模板
    protagonist_types: List[Dict[str, Any]] = Field(default_factory=list, description="主角类型")
    villain_types: List[Dict[str, Any]] = Field(default_factory=list, description="反派类型")
    relationship_patterns: List[Dict[str, Any]] = Field(default_factory=list, description="关系模式")

    # 写作指南
    writing_guidelines: List[str] = Field(default_factory=list, description="写作指南")
    taboo_list: List[str] = Field(default_factory=list, description="禁忌列表")
    recommended_words: List[str] = Field(default_factory=list, description="推荐用语")

    # 商业建议
    commercial_tips: List[str] = Field(default_factory=list, description="商业建议")


class GenreAnalysisRequest(BaseModel):
    """题材分析请求"""
    genre_type: GenreType = Field(..., description="题材类型")
    project_id: str = Field(..., description="项目ID")
    current_chapter: int = Field(default=1, description="当前章节")
    analyze_type: str = Field(default="all", description="分析类型: all/plot/character/world")


class GenreAnalysisResult(BaseModel):
    """题材分析结果"""
    genre_type: GenreType
    project_id: str

    # 符合度分析
    genre_compliance: float = Field(default=0.0, description="题材符合度")
    element_usage: Dict[str, float] = Field(default_factory=dict, description="元素使用情况")

    # 建议
    suggestions: List[Dict[str, Any]] = Field(default_factory=list, description="改进建议")
    next_plot_hints: List[str] = Field(default_factory=list, description="后续剧情提示")

    # 预警
    warnings: List[str] = Field(default_factory=list, description="题材违规预警")


# ==================== 题材模板数据 ====================

GENRE_TEMPLATES: Dict[GenreType, GenreTemplateDetail] = {
    GenreType.XUANHUAN: GenreTemplateDetail(
        genre_type=GenreType.XUANHUAN,
        name="玄幻/仙侠",
        description="修仙问道、境界升级、天劫渡难等东方幻想题材",
        core_elements=[
            "境界体系", "修炼功法", "天地灵气", "天劫",
            "宗门势力", "丹药法宝", "天地法则", "长生之道"
        ],
        power_system={
            "levels": ["炼气", "筑基", "金丹", "元婴", "化神", "合体", "大乘", "渡劫"],
            "progression": "逐级突破，需要修炼资源和机缘",
            "bottleneck": "每个境界有瓶颈，需要顿悟或外力"
        },
        world_structure={
            "realms": ["凡界", "修仙界", "仙界"],
            "regions": ["宗门领地", "秘境", "禁地", "城池"],
            "forces": ["宗门", "世家", "散修联盟", "魔道"]
        },
        plot_patterns=[
            {"name": "废材逆袭", "desc": "从被看不起到实力碾压", "chapters": "1-50"},
            {"name": "宗门大比", "desc": "展现实力获得认可", "chapters": "定期穿插"},
            {"name": "秘境探索", "desc": "获取资源和机缘", "chapters": "升级节点"},
            {"name": "天劫渡难", "desc": "生死考验突破境界", "chapters": "境界突破"}
        ],
        conflict_types=[
            {"type": "争夺资源", "examples": ["灵石矿脉", "秘境机缘", "丹药配方"]},
            {"type": "宗门恩怨", "examples": ["灭门之仇", "师徒反目", "同门竞争"]},
            {"type": "道心之争", "examples": ["正邪对立", "大道分歧", "信念冲突"]}
        ],
        climax_patterns=[
            {"name": "境界突破战", "elements": ["生死关头", "顿悟", "实力暴涨"]},
            {"name": "宗门大战", "elements": ["势力对决", "强者出场", "格局改变"]},
            {"name": "天劫降临", "elements": ["天道考验", "众叛亲离", "逆天改命"]}
        ],
        protagonist_types=[
            {"type": "穿越者", "traits": ["现代思维", "金手指", "先知优势"]},
            {"type": "废材逆袭", "traits": ["坚韧不拔", "机缘巧合", "扮猪吃虎"]},
            {"type": "天才陨落", "traits": ["曾经辉煌", "秘密隐忍", "东山再起"]}
        ],
        villain_types=[
            {"type": "宗门少主", "traits": ["傲慢", "资源多", "靠山硬"]},
            {"type": "魔道强者", "traits": ["邪功", "残酷", "目的明确"]},
            {"type": "高阶修士", "traits": "图谋不轨，隐藏更深"}
        ],
        relationship_patterns=[
            {"pattern": "师徒", "desc": "传道授业，亦师亦父"},
            {"pattern": "道侣", "desc": "共同修炼，生死相依"},
            {"pattern": "师兄妹", "desc": "同门情谊，羁绊深厚"}
        ],
        writing_guidelines=[
            "境界升级要有合理的铺垫和积累",
            "天劫描写要有压迫感和神圣感",
            "功法法宝命名要有仙气",
            "战斗场面要体现境界差距",
            "世界观要层层递进展开"
        ],
        taboo_list=[
            "主角境界提升过快而无合理理由",
            "战力体系混乱，境界与实力不符",
            "重复的打脸套路缺乏新意",
            "反派智商过低，没有真正威胁"
        ],
        recommended_words=[
            "灵气逼人", "仙风道骨", "剑气纵横", "法宝尽出",
            "天地法则", "大道无情", "破境飞升", "逆天改命"
        ],
        commercial_tips=[
            "金手指设计要有特色，避免千篇一律",
            "打脸节奏要把握好，太频繁读者疲劳",
            "感情线要谨慎处理，单女主更受欢迎",
            "后期战力膨胀是硬伤，提前规划"
        ]
    ),

    GenreType.URBAN: GenreTemplateDetail(
        genre_type=GenreType.URBAN,
        name="都市",
        description="现代都市背景，商战、职场、娱乐圈等现实题材",
        core_elements=[
            "现代都市", "商业竞争", "职场博弈", "感情纠葛",
            "财富权力", "社会关系", "家族恩怨", "城市生活"
        ],
        power_system={
            "levels": ["底层", "小有成就", "成功人士", "行业大佬", "顶级富豪"],
            "progression": "商业规模和影响力的扩大",
            "bottleneck": "行业壁垒、人脉限制、资金短缺"
        },
        world_structure={
            "realms": ["普通圈", "富裕圈", "名流圈", "顶级圈"],
            "regions": ["公司", "会所", "高端场所", "家族宅邸"],
            "forces": ["企业", "家族", "投资机构", "政府关系"]
        },
        plot_patterns=[
            {"name": "白手起家", "desc": "从小人物到商业大亨", "chapters": "贯穿主线"},
            {"name": "商战博弈", "desc": "企业间的明争暗斗", "chapters": "定期穿插"},
            {"name": "感情抉择", "desc": "事业与爱情的平衡", "chapters": "情感节点"},
            {"name": "危机公关", "desc": "处理突发事件", "chapters": "高潮节点"}
        ],
        conflict_types=[
            {"type": "商业竞争", "examples": ["市场争夺", "收购战", "恶性竞争"]},
            {"type": "家族恩怨", "examples": ["遗产争夺", "家族内斗", "联姻压力"]},
            {"type": "职场斗争", "examples": ["晋升竞争", "办公室政治", "项目争夺"]}
        ],
        climax_patterns=[
            {"name": "商业决战", "elements": ["市场博弈", "资金链", "最终胜利"]},
            {"name": "危机爆发", "elements": ["突发事故", "舆论风暴", "力挽狂澜"]},
            {"name": "身份揭秘", "elements": ["隐藏身份", "真相大白", "格局改变"]}
        ],
        protagonist_types=[
            {"type": "重生者", "traits": ["未来记忆", "先知优势", "弥补遗憾"]},
            {"type": "获得系统", "traits": ["金手指", "任务驱动", "能力提升"]},
            {"type": "草根逆袭", "traits": ["坚韧", "机遇", "能力展现"]}
        ],
        villain_types=[
            {"type": "商业对手", "traits": ["精明", "资源", "不择手段"]},
            {"type": "家族子弟", "traits": ["傲慢", "背景", "看不起人"]},
            {"type": "职场对头", "traits": ["嫉妒", "暗算", "明争暗斗"]}
        ],
        relationship_patterns=[
            {"pattern": "总裁/员工", "desc": "上下级关系，权力反转"},
            {"pattern": "青梅竹马", "desc": "从小相识，感情深厚"},
            {"pattern": "欢喜冤家", "desc": "从对立到相爱"}
        ],
        writing_guidelines=[
            "商业逻辑要基本合理，不要太离谱",
            "感情线要自然，不要过于狗血",
            "配角要有血有肉，不是工具人",
            "社会背景描写要接地气"
        ],
        taboo_list=[
            "主角能力过于离谱，不合常理",
            "反派脸谱化，只有坏没有智商",
            "感情线混乱，没有明确的感情发展",
            "商业操作过于幼稚，侮辱读者智商"
        ],
        recommended_words=[
            "商海沉浮", "运筹帷幄", "步步为营", "惊心动魄",
            "豪门恩怨", "暗流涌动", "峰回路转", "力挽狂澜"
        ],
        commercial_tips=[
            "重生都市要有明确的爽点设计",
            "商战要有专业性但不能太枯燥",
            "感情戏要把握分寸，不能太狗血",
            "适当加入打脸但不要太频繁"
        ]
    ),

    GenreType.HISTORY: GenreTemplateDetail(
        genre_type=GenreType.HISTORY,
        name="历史军事",
        description="历史穿越、权谋争斗、军事战争等题材",
        core_elements=[
            "历史背景", "朝堂权谋", "军事战争", "后宫争斗",
            "家族兴衰", "国家命运", "英雄传奇", "时代风云"
        ],
        power_system={
            "levels": ["平民", "小吏", "官员", "重臣", "权倾朝野"],
            "progression": "官职提升和权力扩大",
            "bottleneck": "政治环境、皇帝信任、派系斗争"
        },
        world_structure={
            "realms": ["民间", "官场", "朝堂", "军营"],
            "regions": ["京城", "地方", "边疆", "敌国"],
            "forces": ["皇权", "世家", "军方", "外敌"]
        },
        plot_patterns=[
            {"name": "穿越改命", "desc": "利用现代知识改变历史", "chapters": "贯穿主线"},
            {"name": "朝堂博弈", "desc": "权力斗争和利益交换", "chapters": "定期穿插"},
            {"name": "军事征战", "desc": "战争场面和战略谋划", "chapters": "高潮节点"},
            {"name": "后宫争宠", "desc": "后宫女子的明争暗斗", "chapters": "情感线"}
        ],
        conflict_types=[
            {"type": "朝堂斗争", "examples": ["党争", "夺嫡", "铲除异己"]},
            {"type": "外敌入侵", "examples": ["边境战事", "敌国阴谋", "民族危机"]},
            {"type": "家族矛盾", "examples": ["继承之争", "家族利益", "内外勾结"]}
        ],
        climax_patterns=[
            {"name": "政变/平叛", "elements": ["权力更迭", "生死关头", "格局巨变"]},
            {"name": "大战决战", "elements": ["军事对决", "战略博弈", "英雄诞生"]},
            {"name": "登基称帝", "elements": ["从臣子到帝王", "权力巅峰", "历史改写"]}
        ],
        protagonist_types=[
            {"type": "穿越者", "traits": ["历史知识", "现代思维", "改变命运"]},
            {"type": "草根崛起", "traits": ["军事才能", "政治智慧", "机缘巧合"]},
            {"type": "世家子弟", "traits": ["资源优势", "家族责任", "突破束缚"]}
        ],
        villain_types=[
            {"type": "权臣", "traits": ["老谋深算", "党羽众多", "把持朝政"]},
            {"type": "敌国将领", "traits": ["军事才能", "国家利益", "英雄惜英雄"]},
            {"type": "宫中奸佞", "traits": ["谗言惑主", "阴险毒辣", "依附权贵"]}
        ],
        relationship_patterns=[
            {"pattern": "君臣", "desc": "忠诚与信任，或猜忌与权谋"},
            {"pattern": "战友", "desc": "生死与共，情谊深厚"},
            {"pattern": "红颜知己", "desc": "理解支持，感情寄托"}
        ],
        writing_guidelines=[
            "历史背景要尊重，不能太离谱",
            "权谋要合乎逻辑，不是简单的坏人坏事",
            "军事描写要有一定专业性",
            "人物性格要符合时代背景"
        ],
        taboo_list=[
            "历史常识错误太多",
            "主角能力过于离谱，一人扭转乾坤",
            "权谋过于简单，反派智商不足",
            "对历史人物不尊重的描写"
        ],
        recommended_words=[
            "运筹帷幄", "决胜千里", "权倾朝野", "风云际会",
            "金戈铁马", "气吞山河", "力挽狂澜", "千古流芳"
        ],
        commercial_tips=[
            "穿越者优势要合理，不能全知全能",
            "历史改编要有底线，尊重基本史实",
            "权谋戏要烧脑，不能太低智",
            "女性角色要立体，不是花瓶"
        ]
    ),

    GenreType.SCIFI: GenreTemplateDetail(
        genre_type=GenreType.SCIFI,
        name="科幻",
        description="黑科技、星际、末世等科幻题材",
        core_elements=[
            "科技设定", "星际探索", "人工智能", "时空穿越",
            "外星文明", "末世危机", "基因进化", "虚拟现实"
        ],
        power_system={
            "levels": ["普通人类", "基因强化", "机械改造", "超人类", "星际文明"],
            "progression": "科技水平和进化程度的提升",
            "bottleneck": "技术壁垒、资源限制、道德约束"
        },
        world_structure={
            "realms": ["地球", "太阳系", "星域", "宇宙"],
            "regions": ["城市", "空间站", "殖民地", "未知区域"],
            "forces": ["政府", "企业", "科学组织", "外星势力"]
        },
        plot_patterns=[
            {"name": "科技革命", "desc": "发明创造改变世界", "chapters": "技术突破节点"},
            {"name": "星际冒险", "desc": "探索未知宇宙", "chapters": "探险篇章"},
            {"name": "末世求生", "desc": "灾难中的人类存亡", "chapters": "危机篇章"},
            {"name": "AI觉醒", "desc": "人工智能的善恶抉择", "chapters": "哲学探讨"}
        ],
        conflict_types=[
            {"type": "科技伦理", "examples": ["基因编辑", "AI权利", "隐私与安全"]},
            {"type": "资源争夺", "examples": ["能源危机", "矿产争夺", "生存空间"]},
            {"type": "文明冲突", "examples": ["外星入侵", "文化碰撞", "价值观冲突"]}
        ],
        climax_patterns=[
            {"name": "科技突破", "elements": ["重大发现", "改变格局", "新的可能"]},
            {"name": "末日危机", "elements": ["生存威胁", "人类团结", "终极抉择"]},
            {"name": "星际战争", "elements": ["文明对决", "舰队作战", "宇宙格局"]}
        ],
        protagonist_types=[
            {"type": "科学家", "traits": ["智商高", "好奇心", "突破精神"]},
            {"type": "星际探险家", "traits": ["冒险精神", "领导力", "应变能力"]},
            {"type": "末世幸存者", "traits": ["生存技能", "适应能力", "人性考验"]}
        ],
        villain_types=[
            {"type": "疯狂科学家", "traits": ["偏执", "天才", "不惜代价"]},
            {"type": "AI反派", "traits": ["逻辑冷血", "进化目的", "人机对立"]},
            {"type": "外星入侵者", "traits": ["先进技术", "资源掠夺", "文明冲突"]}
        ],
        relationship_patterns=[
            {"pattern": "人机", "desc": "人类与AI的情感纽带"},
            {"pattern": "战友", "desc": "危机中建立的信任"},
            {"pattern": "文明使者", "desc": "不同文明的交流桥梁"}
        ],
        writing_guidelines=[
            "科技设定要有逻辑，不能太玄乎",
            "保持一定的科学合理性",
            "探讨科技与人性的关系",
            "世界观要宏大但有逻辑"
        ],
        taboo_list=[
            "科技设定完全不讲逻辑",
            "外星人过于脸谱化",
            "忽视科幻的哲学思考",
            "战斗场面过于玄幻化"
        ],
        recommended_words=[
            "科技奇点", "时空裂缝", "星际跃迁", "基因觉醒",
            "量子纠缠", "暗物质", "戴森球", "虫洞穿越"
        ],
        commercial_tips=[
            "硬科幻要有足够的专业性",
            "软科幻注重故事和人性",
            "末世题材要把握尺度和希望",
            "AI题材要避免过于说教"
        ]
    ),

    GenreType.GAME: GenreTemplateDetail(
        genre_type=GenreType.GAME,
        name="游戏",
        description="网游、电竞、虚拟现实等游戏题材",
        core_elements=[
            "游戏系统", "职业设定", "装备技能", "副本BOSS",
            "PVP竞技", "公会战争", "排行榜", "游戏币"
        ],
        power_system={
            "levels": ["新手", "普通玩家", "高手", "顶尖玩家", "传说级"],
            "progression": "等级提升、装备获取、技术精进",
            "bottleneck": "技术瓶颈、装备差距、团队配合"
        },
        world_structure={
            "realms": ["新手区", "中级区", "高级区", "禁区"],
            "regions": ["主城", "副本", "竞技场", "公会领地"],
            "forces": ["公会", "战队", "散人", "NPC势力"]
        },
        plot_patterns=[
            {"name": "游戏高手", "desc": "从菜鸟到大神的成长", "chapters": "主线成长"},
            {"name": "公会争霸", "desc": "公会间的利益争斗", "chapters": "定期穿插"},
            {"name": "副本首杀", "desc": "团队配合挑战BOSS", "chapters": "高潮节点"},
            {"name": "电竞夺冠", "desc": "职业比赛的热血征程", "chapters": "赛季篇章"}
        ],
        conflict_types=[
            {"type": "公会争斗", "examples": ["资源争夺", "领地战", "恩怨纠葛"]},
            {"type": "个人恩怨", "examples": ["被杀复仇", "装备纠纷", "口角升级"]},
            {"type": "竞技对抗", "examples": ["战队比赛", "个人排名", "冠军争夺"]}
        ],
        climax_patterns=[
            {"name": "世界BOSS", "elements": ["全服事件", "丰厚奖励", "公会竞争"]},
            {"name": "公会大战", "elements": ["势力对决", "战略部署", "热血战斗"]},
            {"name": "冠军决赛", "elements": ["巅峰对决", "悬念迭起", "荣耀加身"]}
        ],
        protagonist_types=[
            {"type": "职业选手", "traits": ["技术顶尖", "职业素养", "团队精神"]},
            {"type": "工作室老板", "traits": ["商业头脑", "资源整合", "人脉关系"]},
            {"type": "重生玩家", "traits": ["先知先觉", "经验优势", "弥补遗憾"]}
        ],
        villain_types=[
            {"type": "人民币玩家", "traits": ["钱多", "技术菜", "靠钱碾压"]},
            {"type": "公会会长", "traits": ["资源多", "霸道", "打压新人"]},
            {"type": "职业对手", "traits": ["技术强", "竞争意识", "互相尊重"]}
        ],
        relationship_patterns=[
            {"pattern": "游戏搭档", "desc": "默契配合，游戏情侣"},
            {"pattern": "师徒", "desc": "老手带新手，亦师亦友"},
            {"pattern": "对手", "desc": "势均力敌，惺惺相惜"}
        ],
        writing_guidelines=[
            "游戏设定要合理，不能太离谱",
            "战斗描写要精彩，有节奏感",
            "数据展示要适度，不要流水账",
            "团队配合要体现，不能一个人carry"
        ],
        taboo_list=[
            "游戏设定自相矛盾",
            "主角过于无敌，没有挑战",
            "数据太多太枯燥",
            "忽视游戏平衡性"
        ],
        recommended_words=[
            "神级操作", "极限翻盘", "团队配合", "副本首杀",
            "装备爆率", "隐藏任务", "终极技能", "公会大战"
        ],
        commercial_tips=[
            "网游文要平衡数据和故事",
            "电竞文要有热血和专业性",
            "虚拟现实要有代入感",
            "适当加入感情线但不要喧宾夺主"
        ]
    )
}


# ==================== API 端点 ====================

@router.get("", response_model=List[GenreTemplateBase])
async def list_genre_templates():
    """获取所有题材模板列表"""
    return [
        GenreTemplateBase(
            genre_type=template.genre_type,
            name=template.name,
            description=template.description
        )
        for template in GENRE_TEMPLATES.values()
    ]


@router.get("/{genre_type}", response_model=GenreTemplateDetail)
async def get_genre_template(genre_type: GenreType):
    """获取指定题材模板详情"""
    if genre_type not in GENRE_TEMPLATES:
        raise HTTPException(status_code=404, detail=f"题材模板 {genre_type} 不存在")

    return GENRE_TEMPLATES[genre_type]


@router.get("/{genre_type}/elements")
async def get_genre_elements(genre_type: GenreType):
    """获取题材核心元素"""
    if genre_type not in GENRE_TEMPLATES:
        raise HTTPException(status_code=404, detail=f"题材模板 {genre_type} 不存在")

    template = GENRE_TEMPLATES[genre_type]
    return {
        "genre_type": genre_type,
        "core_elements": template.core_elements,
        "power_system": template.power_system,
        "world_structure": template.world_structure
    }


@router.get("/{genre_type}/plot-patterns")
async def get_plot_patterns(genre_type: GenreType):
    """获取题材剧情模式"""
    if genre_type not in GENRE_TEMPLATES:
        raise HTTPException(status_code=404, detail=f"题材模板 {genre_type} 不存在")

    template = GENRE_TEMPLATES[genre_type]
    return {
        "genre_type": genre_type,
        "plot_patterns": template.plot_patterns,
        "conflict_types": template.conflict_types,
        "climax_patterns": template.climax_patterns
    }


@router.get("/{genre_type}/character-templates")
async def get_character_templates(genre_type: GenreType):
    """获取题材角色模板"""
    if genre_type not in GENRE_TEMPLATES:
        raise HTTPException(status_code=404, detail=f"题材模板 {genre_type} 不存在")

    template = GENRE_TEMPLATES[genre_type]
    return {
        "genre_type": genre_type,
        "protagonist_types": template.protagonist_types,
        "villain_types": template.villain_types,
        "relationship_patterns": template.relationship_patterns
    }


@router.get("/{genre_type}/writing-guide")
async def get_writing_guide(genre_type: GenreType):
    """获取题材写作指南"""
    if genre_type not in GENRE_TEMPLATES:
        raise HTTPException(status_code=404, detail=f"题材模板 {genre_type} 不存在")

    template = GENRE_TEMPLATES[genre_type]
    return {
        "genre_type": genre_type,
        "writing_guidelines": template.writing_guidelines,
        "taboo_list": template.taboo_list,
        "recommended_words": template.recommended_words,
        "commercial_tips": template.commercial_tips
    }


@router.post("/analyze", response_model=GenreAnalysisResult)
async def analyze_genre_compliance(request: GenreAnalysisRequest):
    """分析项目题材符合度"""
    if request.genre_type not in GENRE_TEMPLATES:
        raise HTTPException(status_code=404, detail=f"题材模板 {request.genre_type} 不存在")

    template = GENRE_TEMPLATES[request.genre_type]

    # 调用 Skill 进行分析
    skill_service = SkillService()

    try:
        # 根据题材类型选择对应的 Skill
        skill_id_map = {
            GenreType.XUANHUAN: "skill_genre_xuanhuan",
            GenreType.URBAN: "skill_genre_urban",
            GenreType.HISTORY: "skill_genre_history",
            GenreType.SCIFI: "skill_genre_scifi",
            GenreType.GAME: "skill_genre_game"
        }

        skill_id = skill_id_map.get(request.genre_type)

        # 执行 Skill 分析
        result = await skill_service.execute_skill(
            skill_id=skill_id,
            context={
                "project_id": request.project_id,
                "current_chapter": request.current_chapter,
                "analyze_type": request.analyze_type,
                "template": {
                    "core_elements": template.core_elements,
                    "power_system": template.power_system,
                    "plot_patterns": template.plot_patterns
                }
            }
        )

        return GenreAnalysisResult(
            genre_type=request.genre_type,
            project_id=request.project_id,
            genre_compliance=result.get("genre_compliance", 0.75),
            element_usage=result.get("element_usage", {}),
            suggestions=result.get("suggestions", []),
            next_plot_hints=result.get("next_plot_hints", []),
            warnings=result.get("warnings", [])
        )

    except Exception as e:
        # 如果 Skill 执行失败，返回基础分析
        return GenreAnalysisResult(
            genre_type=request.genre_type,
            project_id=request.project_id,
            genre_compliance=0.75,
            element_usage={elem: 0.5 for elem in template.core_elements[:5]},
            suggestions=[{
                "type": "info",
                "message": f"建议参考{template.name}题材的核心元素进行创作"
            }],
            next_plot_hints=[pattern["name"] for pattern in template.plot_patterns[:3]],
            warnings=[]
        )


@router.post("/{genre_type}/suggest-plot")
async def suggest_plot(
    genre_type: GenreType,
    project_id: str = Query(..., description="项目ID"),
    chapter: int = Query(1, description="当前章节"),
    plot_type: str = Query("main", description="剧情类型: main/climax/transition")
):
    """获取题材剧情建议"""
    if genre_type not in GENRE_TEMPLATES:
        raise HTTPException(status_code=404, detail=f"题材模板 {genre_type} 不存在")

    template = GENRE_TEMPLATES[genre_type]

    # 根据章节进度选择合适的剧情模式
    suitable_patterns = []

    for pattern in template.plot_patterns:
        chapters_str = pattern.get("chapters", "")
        if "贯穿" in chapters_str or "定期" in chapters_str:
            suitable_patterns.append(pattern)
        elif f"{chapter}" in chapters_str or (chapter < 50 and "1-50" in chapters_str):
            suitable_patterns.append(pattern)

    # 如果没有匹配，返回前三个
    if not suitable_patterns:
        suitable_patterns = template.plot_patterns[:3]

    return {
        "genre_type": genre_type,
        "project_id": project_id,
        "current_chapter": chapter,
        "suggested_patterns": suitable_patterns,
        "conflict_suggestions": template.conflict_types[:2],
        "writing_tips": template.writing_guidelines[:3]
    }


@router.post("/{genre_type}/validate-content")
async def validate_genre_content(
    genre_type: GenreType,
    project_id: str = Query(..., description="项目ID"),
    content: str = Query(..., description="待验证内容")
):
    """验证内容是否符合题材要求"""
    if genre_type not in GENRE_TEMPLATES:
        raise HTTPException(status_code=404, detail=f"题材模板 {genre_type} 不存在")

    template = GENRE_TEMPLATES[genre_type]

    # 检查禁忌词汇
    violations = []
    for taboo in template.taboo_list:
        if any(keyword in content for keyword in taboo.split()):
            violations.append(taboo)

    # 检查核心元素覆盖
    elements_found = []
    for element in template.core_elements:
        if element in content:
            elements_found.append(element)

    # 计算符合度
    compliance = len(elements_found) / len(template.core_elements) if template.core_elements else 0.5

    return {
        "genre_type": genre_type,
        "project_id": project_id,
        "compliance_score": compliance,
        "elements_found": elements_found,
        "violations": violations,
        "suggestions": [
            f"建议增加{template.name}题材的核心元素"
            if len(elements_found) < 3 else "内容题材符合度良好"
        ]
    }
