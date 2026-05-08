# -*- coding: utf-8 -*-
"""
黄金三章规则配置模型
GodView v9: 开局质量保障系统

将黄金三章规则从硬编码迁移到可配置的数据库表
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
import uuid


class GoldenThreeRuleType(str, Enum):
    """黄金三章规则类型"""

    HOOK = "hook"               # 开头钩子
    CONFLICT = "conflict"       # 冲突设置
    PROTAGONIST = "protagonist" # 主角塑造


class RuleSeverity(str, Enum):
    """规则严重程度"""

    CRITICAL = "critical"   # 必须满足
    IMPORTANT = "important" # 重要建议
    OPTIONAL = "optional"   # 可选优化


class GoldenThreeRule(BaseModel):
    """黄金三章规则"""

    id: str = Field(default_factory=lambda: f"rule_{uuid.uuid4().hex[:8]}")
    rule_type: GoldenThreeRuleType = Field(..., description="规则类型")

    # 规则内容
    rule_name: str = Field(..., description="规则名称")
    description: str = Field(..., description="规则描述")
    check_points: List[str] = Field(default_factory=list, description="检查要点")
    examples: List[str] = Field(default_factory=list, description="示例")

    # 权重和严重程度
    weight: float = Field(default=1.0, ge=0, le=2, description="权重")
    severity: RuleSeverity = Field(default=RuleSeverity.IMPORTANT, description="严重程度")

    # 适用范围
    applicable_genres: List[str] = Field(default_factory=list, description="适用题材")
    applicable_chapter: int = Field(default=1, ge=1, le=3, description="适用章节(1-3)")

    # 修复建议
    fix_suggestions: List[str] = Field(default_factory=list, description="修复建议")

    # 元数据
    is_active: bool = Field(default=True, description="是否启用")
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)


class GoldenThreeCheckResult(BaseModel):
    """黄金三章检测结果"""

    id: str = Field(default_factory=lambda: f"check_{uuid.uuid4().hex[:8]}")
    project_id: str = Field(..., description="项目ID")

    # 各章检测结果
    chapter_results: Dict[int, Dict[str, Any]] = Field(
        default_factory=dict,
        description="各章检测结果"
    )

    # 总体评分
    total_score: float = Field(default=0.0, ge=0, le=100, description="总分")
    hook_score: float = Field(default=0.0, ge=0, le=100, description="钩子评分")
    conflict_score: float = Field(default=0.0, ge=0, le=100, description="冲突评分")
    protagonist_score: float = Field(default=0.0, ge=0, le=100, description="主角评分")

    # 问题汇总
    critical_issues: List[str] = Field(default_factory=list, description="严重问题")
    warnings: List[str] = Field(default_factory=list, description="警告")
    suggestions: List[str] = Field(default_factory=list, description="建议")

    # 元数据
    checked_at: datetime = Field(default_factory=datetime.now)


# ==================== 默认规则数据 ====================

DEFAULT_GOLDEN_THREE_RULES: List[Dict[str, Any]] = [
    # === 钩子规则 ===
    {
        "rule_type": "hook",
        "rule_name": "开篇第一句必须抓人",
        "description": "第一章第一句必须能够吸引读者继续阅读，产生阅读欲望",
        "check_points": [
            "是否以动作、对话或悬念开篇",
            "是否避免了冗长的背景介绍",
            "是否在前50字内抓住读者注意力"
        ],
        "examples": [
            "动作开篇：刀光一闪，鲜血飞溅",
            "对话开篇：你确定要这么做？他沉声问道",
            "悬念开篇：当他再次睁开眼睛时，发现自己竟然回到了十年前"
        ],
        "weight": 1.5,
        "severity": "critical",
        "applicable_chapter": 1,
        "fix_suggestions": [
            "将开篇改为动作或对话场景",
            "在第一句设置悬念或冲突",
            "删除冗长的背景介绍，留待后续展开"
        ]
    },
    {
        "rule_type": "hook",
        "rule_name": "前500字必须有冲突或悬念",
        "description": "开篇500字内必须出现冲突、悬念或异常事件",
        "check_points": [
            "是否在前500字内设置了冲突",
            "是否出现了让读者好奇的悬念",
            "是否避免了平淡无奇的开场"
        ],
        "examples": [
            "冲突：被人追杀、被陷害、被退婚",
            "悬念：神秘老人、奇异宝物、时空穿越",
            "异常：反常现象、突发变故、意外事件"
        ],
        "weight": 1.3,
        "severity": "critical",
        "applicable_chapter": 1,
        "fix_suggestions": [
            "在开篇加入一个冲突事件",
            "设置一个悬念让读者想知道后续",
            "用异常事件打破日常的平静"
        ]
    },
    {
        "rule_type": "hook",
        "rule_name": "第一章结尾留钩子",
        "description": "第一章结尾需要留下悬念，吸引读者看第二章",
        "check_points": [
            "是否在结尾设置了悬念",
            "是否留下未解决的问题",
            "是否让读者想要知道后续发展"
        ],
        "examples": [
            "悬念结尾：原来这一切都是那个人安排的",
            "问题结尾：他不知道，更大的危机正在向他逼近",
            "转折结尾：正当他以为一切结束时，一道金光从天而降"
        ],
        "weight": 1.2,
        "severity": "important",
        "applicable_chapter": 1,
        "fix_suggestions": [
            "在结尾设置一个悬念",
            "引入一个新问题或新角色",
            "用一个转折改变读者预期"
        ]
    },

    # === 冲突规则 ===
    {
        "rule_type": "conflict",
        "rule_name": "第一章必须有冲突",
        "description": "第一章必须出现明确的冲突，主角面临困境或挑战",
        "check_points": [
            "是否有明确的冲突事件",
            "主角是否面临困境",
            "冲突是否足以推动剧情发展"
        ],
        "examples": [
            "外部冲突：被追杀、被陷害、被退婚、被羞辱",
            "内部冲突：选择困境、信念动摇、道德挣扎",
            "环境冲突：生存危机、资源争夺、天灾人祸"
        ],
        "weight": 1.5,
        "severity": "critical",
        "applicable_chapter": 1,
        "fix_suggestions": [
            "引入一个敌对角色或势力",
            "设置一个让主角陷入困境的事件",
            "创造一个主角必须面对的挑战"
        ]
    },
    {
        "rule_type": "conflict",
        "rule_name": "冲突等级递进",
        "description": "前三章的冲突应呈递进趋势，一章比一章紧张",
        "check_points": [
            "第二章冲突是否比第一章更紧张",
            "第三章冲突是否达到小高潮",
            "冲突是否推动主角做出选择"
        ],
        "examples": [
            "第一章：小冲突（被羞辱）",
            "第二章：中冲突（被追杀）",
            "第三章：大冲突（生死危机）"
        ],
        "weight": 1.2,
        "severity": "important",
        "applicable_chapter": 2,
        "fix_suggestions": [
            "让冲突的严重程度递增",
            "让主角面临更大的风险",
            "增加冲突的紧迫感"
        ]
    },
    {
        "rule_type": "conflict",
        "rule_name": "冲突必须有解决方向",
        "description": "每个冲突都应暗示解决方向，给读者希望",
        "check_points": [
            "冲突是否有解决的希望",
            "是否暗示了主角的应对方式",
            "是否让读者期待冲突的解决"
        ],
        "examples": [
            "暗示：主角发现了敌人的弱点",
            "转机：神秘人物伸出援手",
            "希望：主角获得了新的力量或资源"
        ],
        "weight": 1.0,
        "severity": "important",
        "applicable_chapter": 1,
        "fix_suggestions": [
            "给冲突设置一个可能的解决方案",
            "让主角获得应对冲突的线索",
            "引入一个帮助主角的元素"
        ]
    },

    # === 主角规则 ===
    {
        "rule_type": "protagonist",
        "rule_name": "主角必须尽快出场",
        "description": "主角应在第一章前1/3部分正式出场",
        "check_points": [
            "主角是否在前1/3出场",
            "主角出场是否有特点",
            "读者是否能快速了解主角身份"
        ],
        "examples": [
            "正面出场：他睁开眼睛，发现自己躺在一片荒野中",
            "侧面出场：所有人都看向那个站在角落的少年",
            "焦点出场：当所有人绝望时，一个身影出现在城门口"
        ],
        "weight": 1.3,
        "severity": "critical",
        "applicable_chapter": 1,
        "fix_suggestions": [
            "调整叙事顺序，让主角尽早出场",
            "减少配角和背景的篇幅",
            "用主角视角进行叙事"
        ]
    },
    {
        "rule_type": "protagonist",
        "rule_name": "主角必须有明确目标",
        "description": "前三章应展现主角的短期目标或长期追求",
        "check_points": [
            "主角是否有明确的目标",
            "目标是否足够吸引人",
            "读者是否理解主角为何追求这个目标"
        ],
        "examples": [
            "短期目标：活下去、复仇、救出某人",
            "中期目标：变强、寻找宝物、进入宗门",
            "长期目标：成仙、统一天下、找到回家的路"
        ],
        "weight": 1.2,
        "severity": "important",
        "applicable_chapter": 1,
        "fix_suggestions": [
            "给主角设置一个明确的目标",
            "让目标与冲突相关联",
            "展现主角追求目标的决心"
        ]
    },
    {
        "rule_type": "protagonist",
        "rule_name": "主角需要有金手指或特殊之处",
        "description": "主角应在前三章展现金手指或与众不同之处",
        "check_points": [
            "主角是否有金手指或特殊能力",
            "金手指是否足够吸引人",
            "是否暗示了金手指的潜力"
        ],
        "examples": [
            "系统：签到系统激活",
            "宝物：手中的玉佩突然发出微光",
            "天赋：发现自己的感知能力远超常人",
            "知识：作为穿越者，他知道未来的所有事情"
        ],
        "weight": 1.3,
        "severity": "important",
        "applicable_chapter": 1,
        "fix_suggestions": [
            "给主角一个独特的金手指",
            "让金手指与剧情产生互动",
            "展现金手指的潜力和限制"
        ]
    },
    {
        "rule_type": "protagonist",
        "rule_name": "主角需要有性格亮点",
        "description": "主角应在前三章展现至少一个鲜明的性格特点",
        "check_points": [
            "主角是否有鲜明的性格特点",
            "性格是否与行为一致",
            "性格是否让读者产生好感或兴趣"
        ],
        "examples": [
            "坚毅：即使遍体鳞伤，他也绝不认输",
            "果断：他毫不犹豫地做出了决定",
            "善良：他冒着危险救下了那个孩子",
            "腹黑：他表面温和，实则早已看穿一切"
        ],
        "weight": 1.1,
        "severity": "important",
        "applicable_chapter": 1,
        "fix_suggestions": [
            "通过行动展现主角性格",
            "让主角做出体现性格的选择",
            "用对话展现主角的性格特点"
        ]
    },
    {
        "rule_type": "protagonist",
        "rule_name": "主角需要读者代入感",
        "description": "主角的处境应让读者产生共情或代入感",
        "check_points": [
            "主角是否有普通人的情感",
            "主角的困境是否让读者感同身受",
            "主角的反应是否合乎常理"
        ],
        "examples": [
            "困境：被家人背叛、被爱人抛弃、被朋友陷害",
            "情感：愤怒、悲伤、不甘、希望",
            "成长：从普通人到强者的蜕变"
        ],
        "weight": 1.2,
        "severity": "important",
        "applicable_chapter": 1,
        "fix_suggestions": [
            "给主角设置读者能理解的困境",
            "展现主角普通人的一面",
            "让主角的情感反应真实可信"
        ]
    },
]


# ==================== DTO 模型 ====================

class CreateGoldenThreeRuleDTO(BaseModel):
    """创建黄金三章规则请求"""

    rule_type: GoldenThreeRuleType
    rule_name: str
    description: str
    check_points: List[str] = Field(default_factory=list)
    examples: List[str] = Field(default_factory=list)
    weight: float = 1.0
    severity: RuleSeverity = RuleSeverity.IMPORTANT
    applicable_genres: List[str] = Field(default_factory=list)
    applicable_chapter: int = 1
    fix_suggestions: List[str] = Field(default_factory=list)


class UpdateGoldenThreeRuleDTO(BaseModel):
    """更新黄金三章规则请求"""

    rule_name: Optional[str] = None
    description: Optional[str] = None
    check_points: Optional[List[str]] = None
    examples: Optional[List[str]] = None
    weight: Optional[float] = None
    severity: Optional[RuleSeverity] = None
    applicable_genres: Optional[List[str]] = None
    applicable_chapter: Optional[int] = None
    fix_suggestions: Optional[List[str]] = None
    is_active: Optional[bool] = None
