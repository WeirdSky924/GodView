"""
世界模板库
v5.3 功能：提供预设的世界模板，加速项目初始化
"""

import logging
import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class WorldTemplateCategory(str, Enum):
    """世界模板类别枚举"""
    FANTASY = "fantasy"  # 奇幻
    SCIFI = "scifi"  # 科幻
    MODERN = "modern"  # 现代
    HISTORICAL = "historical"  # 历史
    WUXIA = "wuxia"  # 武侠
    XUANHUAN = "xuanhuan"  # 玄幻
    MYTHOLOGY = "mythology"  # 神话
    CUSTOM = "custom"  # 自定义


class CharacterTemplate(BaseModel):
    """角色模板"""
    name: str
    role: str
    description: str
    personality_traits: List[str] = Field(default_factory=list)
    goals: List[str] = Field(default_factory=list)
    abilities: List[str] = Field(default_factory=list)


class RegionTemplate(BaseModel):
    """区域模板"""
    name: str
    region_type: str
    description: str
    climate: Optional[str] = None
    resources: List[str] = Field(default_factory=list)
    dangers: List[str] = Field(default_factory=list)


class PlotHookTemplate(BaseModel):
    """剧情钩子模板"""
    title: str
    description: str
    trigger_condition: str
    potential_outcomes: List[str] = Field(default_factory=list)


class WorldRuleTemplate(BaseModel):
    """世界规则模板"""
    name: str
    description: str
    effects: Dict[str, Any] = Field(default_factory=dict)


class WorldTemplate(BaseModel):
    """世界模板"""
    id: str = Field(default_factory=lambda: f"template_{uuid.uuid4().hex[:12]}")
    name: str
    description: str
    category: WorldTemplateCategory
    tags: List[str] = Field(default_factory=list)
    world_type: str
    tone: str
    power_system: Optional[str] = None
    technology_level: Optional[str] = None
    world_rules: List[WorldRuleTemplate] = Field(default_factory=list)
    default_regions: List[RegionTemplate] = Field(default_factory=list)
    default_characters: List[CharacterTemplate] = Field(default_factory=list)
    plot_hooks: List[PlotHookTemplate] = Field(default_factory=list)
    writing_style: Optional[str] = None
    narrative_tone: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    created_by: str = "system"
    popularity: int = 0
    rating: float = 0.0

    class Config:
        arbitrary_types_allowed = True


class WorldTemplateLibrary:
    """世界模板库"""

    def __init__(self):
        self.templates: Dict[str, WorldTemplate] = {}
        self.categories: Dict[WorldTemplateCategory, List[str]] = {}
        self._initialize_builtin_templates()

        logger.info(f"世界模板库初始化完成，共 {len(self.templates)} 个模板")

    def _initialize_builtin_templates(self):
        """初始化内置模板"""

        # 奇幻模板
        self._create_fantasy_templates()

        # 科幻模板
        self._create_scifi_templates()

        # 现代模板
        self._create_modern_templates()

        # 武侠模板
        self._create_wuxia_templates()

        # 玄幻模板
        self._create_xuanhuan_templates()

    def _create_fantasy_templates(self):
        """创建奇幻模板"""

        # 高魔奇幻
        template = WorldTemplate(
            name="高魔奇幻世界",
            description="一个充满魔法、精灵、龙和史诗冒险的经典高魔奇幻世界。",
            category=WorldTemplateCategory.FANTASY,
            tags=["魔法", "精灵", "巨龙", "冒险", "史诗"],
            world_type="fantasy",
            tone="serious",
            power_system="魔法体系",
            technology_level="中世纪",
            world_rules=[
                WorldRuleTemplate(
                    name="魔法法则",
                    description="魔法遵循特定的规则和限制",
                    effects={"mana_cost": True, "cooldown": True}
                ),
                WorldRuleTemplate(
                    name="种族天赋",
                    description="不同种族拥有独特的天赋能力",
                    effects={"racial_bonus": True}
                ),
            ],
            default_regions=[
                RegionTemplate(
                    name="精灵森林",
                    region_type="forest",
                    description="古老而神秘的精灵王国",
                    climate="温和",
                    resources=["魔法木材", "精灵草药", "秘银"],
                    dangers=["魔兽", "迷失者"]
                ),
                RegionTemplate(
                    name="人类王国",
                    region_type="kingdom",
                    description="繁荣的人类王国首都",
                    climate="温带",
                    resources=["铁矿", "粮食", "贸易"],
                    dangers=["盗贼", "政治阴谋"]
                ),
                RegionTemplate(
                    name="龙之山脉",
                    region_type="mountain",
                    description="巨龙栖息的险峻山脉",
                    climate="寒冷",
                    resources=["秘银", "龙晶", "稀有矿石"],
                    dangers=["巨龙", "悬崖", "雪崩"]
                ),
            ],
            default_characters=[
                CharacterTemplate(
                    name="精灵王子/公主",
                    role="主角",
                    description="来自精灵王国的贵族，拥有非凡的魔法天赋",
                    personality_traits=["高傲", "智慧", "善良"],
                    goals=["保护森林", "拯救世界", "寻找真爱"],
                    abilities=["元素魔法", "箭术", "自然沟通"]
                ),
                CharacterTemplate(
                    name="人类骑士",
                    role="配角",
                    description="忠诚勇敢的人类骑士",
                    personality_traits=["正直", "勇敢", "忠诚"],
                    goals=["效忠国王", "守护弱者"],
                    abilities=["剑术", "骑术", "战术"]
                ),
            ],
            plot_hooks=[
                PlotHookTemplate(
                    title="黑暗势力崛起",
                    description="古老的邪恶力量苏醒，威胁整个世界",
                    trigger_condition="故事开始",
                    potential_outcomes=["英雄集结", "世界大战", "种族联合"]
                ),
                PlotHookTemplate(
                    title="失落的神器",
                    description="传说中能够拯救世界的神器",
                    trigger_condition="探险发现",
                    potential_outcomes=["力量觉醒", "新的冒险", "敌人抢夺"]
                ),
            ],
            writing_style="史诗叙事",
            narrative_tone="英雄主义",
            popularity=100,
            rating=4.5
        )
        self._add_template(template)

        # 低魔奇幻
        template = WorldTemplate(
            name="低魔奇幻世界",
            description="一个魔法稀有而危险的世界，更像中世纪的黑暗历史。",
            category=WorldTemplateCategory.FANTASY,
            tags=["低魔", "黑暗", "中世纪", "权谋"],
            world_type="fantasy",
            tone="dark",
            power_system="血脉力量",
            technology_level="中世纪晚期",
            world_rules=[
                WorldRuleTemplate(
                    name="魔法稀有",
                    description="魔法极其稀有，掌握者往往被视为异类",
                    effects={"magic_rare": True}
                ),
            ],
            default_regions=[
                RegionTemplate(
                    name="破败王国",
                    region_type="kingdom",
                    description="一个正在衰落的人类王国",
                    climate="阴冷",
                    resources=["铁矿", "木材"],
                    dangers=["瘟疫", "匪患", "饥荒"]
                ),
            ],
            default_characters=[
                CharacterTemplate(
                    name="流亡贵族",
                    role="主角",
                    description="失去一切的贵族，在黑暗世界中挣扎求生",
                    personality_traits=["坚韧", "机敏", "复仇心强"],
                    goals=["复仇", "重夺权力", "生存"],
                    abilities=["剑术", "政治", "生存"]
                ),
            ],
            plot_hooks=[
                PlotHookTemplate(
                    title="王位争夺",
                    description="国王驾崩，各方势力为争夺王位展开明争暗斗",
                    trigger_condition="故事开始",
                    potential_outcomes=["政变", "内战", "主角崛起"]
                ),
            ],
            writing_style="写实风格",
            narrative_tone="暗黑",
            popularity=80,
            rating=4.3
        )
        self._add_template(template)

    def _create_scifi_templates(self):
        """创建科幻模板"""

        template = WorldTemplate(
            name="星际帝国",
            description="一个跨越多个星系的庞大帝国，科技高度发达但政治复杂。",
            category=WorldTemplateCategory.SCIFI,
            tags=["太空", "帝国", "科技", "政治"],
            world_type="scifi",
            tone="serious",
            power_system="基因改造",
            technology_level="星际时代",
            world_rules=[
                WorldRuleTemplate(
                    name="超光速旅行",
                    description="通过虫洞技术实现超光速旅行",
                    effects={"ftl_travel": True}
                ),
            ],
            default_regions=[
                RegionTemplate(
                    name="首都星",
                    region_type="planet",
                    description="帝国的政治中心，高度发达的城市星球",
                    climate="人工控制",
                    resources=["科技", "政治", "贸易"],
                    dangers=["阴谋", "间谍"]
                ),
                RegionTemplate(
                    name="边疆星系",
                    region_type="sector",
                    description="帝国的边疆，充满未知和危险",
                    climate="多样",
                    resources=["稀有矿物", "未知生物"],
                    dangers=["海盗", "外星威胁", "叛军"]
                ),
            ],
            default_characters=[
                CharacterTemplate(
                    name="帝国将军",
                    role="主角",
                    description="帝国军队的高级将领，忠诚于皇帝",
                    personality_traits=["冷静", "果断", "忠诚"],
                    goals=["维护帝国稳定", "击败敌人"],
                    abilities=["战略", "指挥", "战斗"]
                ),
            ],
            plot_hooks=[
                PlotHookTemplate(
                    title="帝国危机",
                    description="帝国面临内忧外患，皇帝神秘失踪",
                    trigger_condition="故事开始",
                    potential_outcomes=["权力真空", "内战", "外敌入侵"]
                ),
            ],
            writing_style="硬科幻",
            narrative_tone="史诗",
            popularity=90,
            rating=4.4
        )
        self._add_template(template)

        # 赛博朋克
        template = WorldTemplate(
            name="赛博朋克都市",
            description="高科技与低生活的未来都市，霓虹灯下的黑暗故事。",
            category=WorldTemplateCategory.SCIFI,
            tags=["赛博朋克", "都市", "反乌托邦", "科技"],
            world_type="scifi",
            tone="dark",
            power_system="义体改造",
            technology_level="近未来",
            world_rules=[
                WorldRuleTemplate(
                    name="公司统治",
                    description="大公司控制着社会的方方面面",
                    effects={"corporate_rule": True}
                ),
            ],
            default_regions=[
                RegionTemplate(
                    name="上城区",
                    region_type="district",
                    description="精英们居住的高层区域",
                    climate="人工控制",
                    resources=["财富", "科技", "权力"],
                    dangers=["监控", "保镖"]
                ),
                RegionTemplate(
                    name="下城区",
                    region_type="district",
                    description="贫民窟，犯罪和贫穷的聚集地",
                    climate="污染",
                    resources=["黑市", "情报", "廉价劳动力"],
                    dangers=["帮派", "疾病", "暴力"]
                ),
            ],
            default_characters=[
                CharacterTemplate(
                    name="黑客",
                    role="主角",
                    description="游走于网络世界的精英黑客",
                    personality_traits=["叛逆", "聪明", "孤独"],
                    goals=["揭露真相", "打击公司", "自由"],
                    abilities=["黑客", "潜入", "情报分析"]
                ),
            ],
            plot_hooks=[
                PlotHookTemplate(
                    title="公司阴谋",
                    description="某大公司正在进行不道德的实验",
                    trigger_condition="调查发现",
                    potential_outcomes=["揭露真相", "被追杀", "改变世界"]
                ),
            ],
            writing_style="黑色电影风格",
            narrative_tone="叛逆",
            popularity=85,
            rating=4.3
        )
        self._add_template(template)

    def _create_modern_templates(self):
        """创建现代模板"""

        template = WorldTemplate(
            name="都市生活",
            description="当代都市背景下的人情冷暖与成长故事。",
            category=WorldTemplateCategory.MODERN,
            tags=["都市", "生活", "情感", "成长"],
            world_type="modern",
            tone="lighthearted",
            power_system=None,
            technology_level="当代",
            default_regions=[
                RegionTemplate(
                    name="商业中心",
                    region_type="district",
                    description="繁华的商业区域",
                    climate="四季分明",
                    resources=["工作", "社交", "消费"],
                    dangers=["竞争", "压力"]
                ),
            ],
            default_characters=[
                CharacterTemplate(
                    name="职场新人",
                    role="主角",
                    description="刚踏入社会的年轻人",
                    personality_traits=["热情", "天真", "努力"],
                    goals=["事业成功", "找到真爱", "成长"],
                    abilities=["学习能力", "社交", "专业技能"]
                ),
            ],
            plot_hooks=[
                PlotHookTemplate(
                    title="职场挑战",
                    description="面临重要的项目或晋升机会",
                    trigger_condition="工作场合",
                    potential_outcomes=["成功", "失败", "转机"]
                ),
            ],
            writing_style="轻松都市",
            narrative_tone="温馨",
            popularity=70,
            rating=4.0
        )
        self._add_template(template)

    def _create_wuxia_templates(self):
        """创建武侠模板"""

        template = WorldTemplate(
            name="江湖武林",
            description="刀光剑影的武侠世界，侠客们在江湖中行侠仗义。",
            category=WorldTemplateCategory.WUXIA,
            tags=["武侠", "江湖", "武功", "侠义"],
            world_type="wuxia",
            tone="serious",
            power_system="武功",
            technology_level="古代中国",
            world_rules=[
                WorldRuleTemplate(
                    name="武功境界",
                    description="武功分为不同境界，需要修炼提升",
                    effects={"martial_stages": True}
                ),
            ],
            default_regions=[
                RegionTemplate(
                    name="名山",
                    region_type="mountain",
                    description="各派武学门派所在的雄伟山岳",
                    climate="多变",
                    resources=["武功秘籍", "名剑", "灵药"],
                    dangers=["仇家", "悬崖", "野兽"]
                ),
            ],
            default_characters=[
                CharacterTemplate(
                    name="武林高手",
                    role="主角",
                    description="身怀绝技的江湖侠客",
                    personality_traits=["正义", "豪迈", "淡泊"],
                    goals=["行侠仗义", "寻找真相", "武学精进"],
                    abilities=["武功", "轻功", "内功"]
                ),
            ],
            plot_hooks=[
                PlotHookTemplate(
                    title="武林大会",
                    description="江湖各派齐聚争夺武林盟主",
                    trigger_condition="故事发展",
                    potential_outcomes=["主角夺魁", "阴谋暴露", "门派联合"]
                ),
            ],
            writing_style="传统武侠",
            narrative_tone="侠义",
            popularity=95,
            rating=4.6
        )
        self._add_template(template)

    def _create_xuanhuan_templates(self):
        """创建玄幻模板"""

        template = WorldTemplate(
            name="修仙世界",
            description="一个充满灵气的世界，修仙者追求长生不老。",
            category=WorldTemplateCategory.XUANHUAN,
            tags=["修仙", "仙侠", "灵气", "长生"],
            world_type="fantasy",
            tone="serious",
            power_system="灵气修炼",
            technology_level="古代",
            world_rules=[
                WorldRuleTemplate(
                    name="修炼境界",
                    description="从练气到飞升的修炼等级体系",
                    effects={"cultivation_realms": True}
                ),
            ],
            default_regions=[
                RegionTemplate(
                    name="仙山福地",
                    region_type="mountain",
                    description="灵气充沛的修炼圣地",
                    climate="四季如春",
                    resources=["灵石", "灵药", "法宝"],
                    dangers=["妖兽", "禁制", "其他修仙者"]
                ),
            ],
            default_characters=[
                CharacterTemplate(
                    name="天才修士",
                    role="主角",
                    description="资质卓越的年轻修仙者",
                    personality_traits=["坚毅", "聪明", "低调"],
                    goals=["修炼成仙", "探索秘境", "寻找道侣"],
                    abilities=["功法", "法术", "炼丹"]
                ),
            ],
            plot_hooks=[
                PlotHookTemplate(
                    title="秘境开启",
                    description="古老秘境即将开启，引来无数修仙者",
                    trigger_condition="特定时间",
                    potential_outcomes=["机缘", "争夺", "发现"]
                ),
            ],
            writing_style="仙侠风格",
            narrative_tone="超脱",
            popularity=98,
            rating=4.7
        )
        self._add_template(template)

    def _add_template(self, template: WorldTemplate):
        """添加模板到库"""

        self.templates[template.id] = template

        # 添加到类别索引
        if template.category not in self.categories:
            self.categories[template.category] = []
        self.categories[template.category].append(template.id)

    def get_template(self, template_id: str) -> Optional[WorldTemplate]:
        """获取模板"""

        return self.templates.get(template_id)

    def get_templates_by_category(self, category: WorldTemplateCategory) -> List[WorldTemplate]:
        """根据类别获取模板"""

        template_ids = self.categories.get(category, [])
        return [self.templates[tid] for tid in template_ids if tid in self.templates]

    def search_templates(self, query: str) -> List[WorldTemplate]:
        """搜索模板"""

        query_lower = query.lower()
        results = []

        for template in self.templates.values():
            # 搜索名称
            if query_lower in template.name.lower():
                results.append(template)
                continue

            # 搜索描述
            if query_lower in template.description.lower():
                results.append(template)
                continue

            # 搜索标签
            for tag in template.tags:
                if query_lower in tag.lower():
                    results.append(template)
                    break

        return results

    def create_world_from_template(
        self,
        template_id: str,
        customizations: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """从模板创建世界数据"""

        template = self.get_template(template_id)
        if not template:
            raise ValueError(f"模板不存在: {template_id}")

        # 创建世界数据
        world_data = {
            "name": template.name,
            "description": template.description,
            "world_type": template.world_type,
            "tone": template.tone,
            "power_system": template.power_system,
            "technology_level": template.technology_level,
            "writing_style": template.writing_style,
            "narrative_tone": template.narrative_tone,
            "rules": [rule.dict() for rule in template.world_rules],
            "regions": [region.dict() for region in template.default_regions],
            "characters": [char.dict() for char in template.default_characters],
            "plot_hooks": [hook.dict() for hook in template.plot_hooks],
        }

        # 应用自定义
        if customizations:
            for key, value in customizations.items():
                if key in world_data:
                    world_data[key] = value

        logger.info(f"从模板 {template_id} 创建世界数据")

        return world_data

    def add_custom_template(self, template: WorldTemplate) -> bool:
        """添加自定义模板"""

        if template.id in self.templates:
            return False

        # 标记为自定义
        template.category = WorldTemplateCategory.CUSTOM
        template.created_by = "user"

        self._add_template(template)
        logger.info(f"添加自定义模板: {template.id} - {template.name}")

        return True

    def rate_template(self, template_id: str, rating: float) -> bool:
        """为模板评分"""

        template = self.get_template(template_id)
        if not template:
            return False

        # 更新评分（简单平均）
        # 实际应用中应该记录每个用户的评分
        template.rating = (template.rating * template.popularity + rating) / (template.popularity + 1)
        template.popularity += 1

        logger.info(f"模板评分更新: {template_id} - {rating} - 平均: {template.rating}")

        return True

    def get_popular_templates(self, limit: int = 10) -> List[WorldTemplate]:
        """获取热门模板"""

        sorted_templates = sorted(
            self.templates.values(),
            key=lambda t: (t.popularity, t.rating),
            reverse=True
        )

        return sorted_templates[:limit]

    def get_template_categories(self) -> Dict[str, int]:
        """获取模板类别统计"""

        return {
            category.value: len(template_ids)
            for category, template_ids in self.categories.items()
        }


# 全局模板库实例
_template_library: Optional[WorldTemplateLibrary] = None


def get_template_library() -> WorldTemplateLibrary:
    """获取模板库单例"""

    global _template_library
    if _template_library is None:
        _template_library = WorldTemplateLibrary()
    return _template_library