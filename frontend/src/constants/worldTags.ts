/**
 * 世界管理多维度标签定义
 * 用于 /worlds 页面的标签选择
 */

export interface TagOption {
  value: string
  label: string
  color: string
  description: string
  gender?: 'male' | 'female' | 'any'
}

// 世界类型标签
export const WORLD_TYPE_TAGS: TagOption[] = [
  { value: 'fantasy', label: '玄幻', color: 'purple', description: '修仙、魔法等玄幻世界' },
  { value: 'xianxia', label: '仙侠', color: 'indigo', description: '仙侠修真世界' },
  { value: 'wuxia', label: '武侠', color: 'gray', description: '传统武侠江湖' },
  { value: 'urban', label: '都市', color: 'blue', description: '现代都市背景' },
  { value: 'scifi', label: '科幻', color: 'cyan', description: '未来科幻世界' },
  { value: 'historical', label: '历史', color: 'amber', description: '历史架空背景' },
  { value: 'xuanhuan', label: '奇幻', color: 'violet', description: '西幻或混合世界' },
  { value: 'mythology', label: '神话', color: 'gold', description: '神话传说背景' },
  { value: 'quick_transmigration', label: '快穿', color: 'pink', description: '主角穿梭多个任务世界' },
  { value: 'infinite_flow', label: '无限流', color: 'blue', description: '副本、主神空间、规则怪谈等多世界结构' },
  { value: 'multiverse', label: '多位面', color: 'violet', description: '主世界统辖多个位面或平行世界' },
  { value: 'apocalypse', label: '末世', color: 'red', description: '灾变、丧尸、废土、生存重建' },
  { value: 'interstellar', label: '星际', color: 'sky', description: '星际文明、舰队、虫族、星域政治' },
  { value: 'cyberpunk', label: '赛博朋克', color: 'teal', description: '高科技低生活、义体、巨企与网络空间' },
  { value: 'steampunk', label: '蒸汽朋克', color: 'amber', description: '蒸汽机械、齿轮工业、复古科技' },
  { value: 'western_fantasy', label: '西幻', color: 'purple', description: '剑与魔法、神祇、种族与王国' },
  { value: 'oriental_fantasy', label: '东方幻想', color: 'rose', description: '东方神话、妖怪志异、玄学体系' },
  { value: 'supernatural', label: '灵异', color: 'zinc', description: '鬼怪、诡异、民俗禁忌与超自然事件' },
  { value: 'mystery', label: '悬疑推理', color: 'slate', description: '案件、谜团、调查与真相反转' },
  { value: 'court_intrigue', label: '宫廷权谋', color: 'amber', description: '朝堂、后宫、夺嫡、权力博弈' },
  { value: 'academy', label: '学院', color: 'green', description: '学院修炼、校园社团、竞赛成长' },
  { value: 'game', label: '游戏异界', color: 'emerald', description: '游戏系统、数据面板、网游或游戏化世界' },
  { value: 'farming', label: '种田经营', color: 'green', description: '建设、经营、领地发展与日常积累' },
  { value: 'other', label: '其他', color: 'slate', description: '其他类型世界' },
]

// 内容风格标签
export const CONTENT_STYLE_TAGS: TagOption[] = [
  { value: 'literary', label: '纯文学', color: 'amber', description: '注重文学性和艺术性' },
  { value: 'sandbag', label: '沙雕搞笑', color: 'yellow', description: '轻松幽默、搞笑沙雕' },
  { value: 'healing', label: '治愈救赎', color: 'pink', description: '温暖治愈、情感救赎' },
  { value: 'dark', label: '黑暗压抑', color: 'gray', description: '黑暗压抑、虐心剧情' },
  { value: 'hot_blooded', label: '热血爽文', color: 'red', description: '热血激情、爽点密集' },
  { value: 'sweet', label: '甜宠', color: 'rose', description: '甜蜜恋爱、撒糖不断' },
  { value: 'angst', label: '虐恋情深', color: 'purple', description: '虐心恋爱、情感纠葛' },
  { value: 'revenge', label: '复仇爽文', color: 'orange', description: '复仇打脸、爽点满满' },
  { value: 'survival', label: '生存游戏', color: 'red', description: '生存挑战、危机四伏' },
  { value: 'infinite', label: '无限流', color: 'blue', description: '无限副本、任务挑战' },
  { value: 'power_fantasy', label: '升级打怪', color: 'indigo', description: '成长升级、资源获取、战力跃迁' },
  { value: 'strategy', label: '智斗权谋', color: 'slate', description: '谋略布局、信息差、政治博弈' },
  { value: 'mystery', label: '悬疑解谜', color: 'zinc', description: '线索推进、谜题破解、真相反转' },
  { value: 'horror', label: '惊悚恐怖', color: 'dark', description: '恐怖氛围、诡异规则、心理压迫' },
  { value: 'romance', label: '情感拉扯', color: 'pink', description: '暧昧、误会、关系张力与情绪推进' },
  { value: 'slice_of_life', label: '日常群像', color: 'green', description: '生活流、日常互动、人物关系沉淀' },
  { value: 'comedy_drama', label: '轻喜剧', color: 'yellow', description: '轻松对白、误会喜剧、欢乐节奏' },
  { value: 'epic_war', label: '史诗战争', color: 'amber', description: '大规模战争、文明冲突、历史纵深' },
  { value: 'political', label: '政治博弈', color: 'slate', description: '派系、制度、利益交换与权力制衡' },
  { value: 'business', label: '经营建设', color: 'emerald', description: '商业、领地、组织或文明建设' },
  { value: 'found_family', label: '羁绊团队', color: 'teal', description: '伙伴关系、团队成长、家人感羁绊' },
  { value: 'antihero', label: '反英雄', color: 'zinc', description: '灰色道德、非常规正义、复杂动机' },
  { value: 'tragedy', label: '宿命悲剧', color: 'purple', description: '命运压迫、牺牲、无可挽回的代价' },
]


// 主角类型标签
export const PROTAGONIST_TYPE_TAGS: TagOption[] = [
  { value: 'male_lead', label: '大男主', color: 'blue', description: '男性主角，主线围绕其成长' },
  { value: 'female_lead', label: '大女主', color: 'pink', description: '女性主角，主线围绕其成长' },
  { value: 'dual_lead', label: '双主角', color: 'purple', description: '双主角，两条主线交织' },
  { value: 'group', label: '群像剧', color: 'teal', description: '群像叙事，多角色并重' },
  { value: 'non_human', label: '非人类', color: 'red', description: '非人类主角，主线围绕其成长' },
  { value: 'quick_transmigrator', label: '快穿任务者', color: 'pink', description: '穿梭多个世界完成任务或修正剧情' },
  { value: 'world_hopper', label: '位面旅者', color: 'violet', description: '跨位面探索、交易、冒险或征服' },
  { value: 'reincarnated', label: '重生者', color: 'amber', description: '带着前世记忆重来一次' },
  { value: 'transmigrated', label: '穿越者', color: 'cyan', description: '从原世界进入异世界或书中世界' },
  { value: 'system_host', label: '系统宿主', color: 'emerald', description: '绑定系统，依靠任务、面板或奖励成长' },
  { value: 'native_genius', label: '本土天才', color: 'indigo', description: '世界内自然成长的天赋型主角' },
  { value: 'underdog', label: '废柴逆袭', color: 'orange', description: '低起点、受压制后逐步翻盘' },
  { value: 'chosen_one', label: '天命之子', color: 'gold', description: '被预言、命运或世界规则选中的核心人物' },
  { value: 'villain_protagonist', label: '反派主角', color: 'zinc', description: '以反派、魔头、黑化阵营为主视角' },
  { value: 'antihero_lead', label: '灰色主角', color: 'slate', description: '动机复杂、手段不完全正派的主角' },
  { value: 'detective_lead', label: '侦探调查者', color: 'gray', description: '以调查、推理和揭露真相为核心行动' },
  { value: 'leader_builder', label: '领袖建设者', color: 'green', description: '建立组织、领地、国家或文明秩序' },
]

// 角色人设标签
export const CHARACTER_ARCHETYPE_TAGS: TagOption[] = [
  // 男性角色人设
  { value: 'ceo', label: '霸总', color: 'navy', description: '霸道总裁，强势霸道又不失温柔', gender: 'male' },
  { value: 'scheming', label: '腹黑', color: 'slate', description: '表面温和实则城府极深', gender: 'any' },
  { value: 'obsessive', label: '偏执狂', color: 'purple', description: '偏执占有欲强，深情偏执', gender: 'any' },
  { value: 'crazy_beauty', label: '疯批美人', color: 'rose', description: '美丽动人却疯狂危险', gender: 'any' },
  { value: 'aloof', label: '高岭之花', color: 'cyan', description: '高冷疏离，难以接近', gender: 'any' },
  { value: 'immortal', label: '谪仙', color: 'sky', description: '如谪仙般超凡脱俗', gender: 'male' },
  { value: 'green_tea_male', label: '绿茶男', color: 'green', description: '外表无害实则心机深沉', gender: 'male' },
  { value: 'puppy', label: '小奶狗', color: 'pink', description: '可爱温顺，黏人忠诚', gender: 'male' },
  { value: 'wolf', label: '小狼狗', color: 'orange', description: '外表乖巧实则野性难驯', gender: 'male' },
  { value: 'villain_lord', label: '反派大佬', color: 'zinc', description: '强大反派，霸气侧漏', gender: 'any' },
  { value: 'tragic_beauty', label: '美强惨', color: 'violet', description: '美丽强大却命运悲惨', gender: 'any' },
  { value: 'daddy', label: '爹系男友', color: 'amber', description: '成熟稳重，照顾周到', gender: 'male' },
  // 中性/女性角色人设
  { value: 'salted_fish', label: '咸鱼', color: 'stone', description: '躺平佛系，不想努力', gender: 'any' },
  { value: 'cool_beauty', label: '清冷', color: 'cyan', description: '清冷疏离，气质出尘', gender: 'female' },
  { value: 'soft', label: '娇软', color: 'pink', description: '娇小柔弱，令人怜爱', gender: 'female' },
  { value: 'sassy', label: '飒爽', color: 'teal', description: '英姿飒爽，干脆利落', gender: 'female' },
  { value: 'villainess', label: '恶毒女配', color: 'fuchsia', description: '反派女配，心机深沉', gender: 'female' },
  { value: 'lucky', label: '锦鲤', color: 'emerald', description: '运气爆棚，好事连连', gender: 'any' },
  { value: 'charmer', label: '万人迷', color: 'yellow', description: '魅力无限，人人喜爱', gender: 'any' },
  { value: 'dumb_beauty', label: '笨蛋美女', color: 'amber', description: '美丽却单纯迷糊', gender: 'female' },
  { value: 'secret_master', label: '马甲大佬', color: 'neutral', description: '多重身份，深藏不露', gender: 'any' },
  { value: 'black_lotus', label: '黑莲花', color: 'dark', description: '外表纯洁内心腹黑', gender: 'female' },
  // 多世界/剧情功能型人设
  { value: 'world_anchor', label: '世界锚点', color: 'indigo', description: '维系某个世界稳定或剧情核心的人物', gender: 'any' },
  { value: 'mission_target', label: '任务目标', color: 'rose', description: '快穿/无限流中需要攻略、拯救或击败的目标', gender: 'any' },
  { value: 'hidden_boss', label: '隐藏Boss', color: 'zinc', description: '前期伪装，后期揭示真实威胁或幕后身份', gender: 'any' },
  { value: 'mentor', label: '导师', color: 'blue', description: '传授知识、规则或力量体系的引路人', gender: 'any' },
  { value: 'rival', label: '宿敌', color: 'red', description: '长期竞争、镜像成长或价值观对立者', gender: 'any' },
  { value: 'foil', label: '镜像角色', color: 'slate', description: '与主角形成对照，凸显主题选择', gender: 'any' },
  { value: 'trickster', label: '搅局者', color: 'orange', description: '用谎言、玩笑或混乱推动局势变化', gender: 'any' },
  { value: 'guardian', label: '守护者', color: 'green', description: '守护地点、规则、人物或秘密的人', gender: 'any' },
  { value: 'fallen_hero', label: '堕落英雄', color: 'purple', description: '曾经正义强大，因创伤或诱惑走向黑暗', gender: 'any' },
  { value: 'redeemed_villain', label: '洗白反派', color: 'teal', description: '经历转变，从敌对走向赎罪或合作', gender: 'any' },
  { value: 'unreliable_ally', label: '不可靠盟友', color: 'amber', description: '立场摇摆、信息不全或另有所图的同伴', gender: 'any' },
  { value: 'comic_relief', label: '气氛担当', color: 'yellow', description: '缓和紧张节奏、提供幽默与情绪调剂', gender: 'any' },
]

// 基调标签
export const TONE_TAGS: TagOption[] = [
  { value: 'serious', label: '严肃', color: 'stone', description: '严肃认真，深度思考' },
  { value: 'light', label: '轻松', color: 'yellow', description: '轻松愉快，阅读轻松' },
  { value: 'dark', label: '黑暗', color: 'zinc', description: '黑暗压抑，深度压抑' },
  { value: 'humorous', label: '幽默', color: 'orange', description: '幽默风趣，笑点不断' },
  { value: 'epic', label: '史诗', color: 'amber', description: '史诗宏大，气势磅礴' },
  { value: 'sweet', label: '甜蜜', color: 'pink', description: '甜蜜温馨，温暖治愈' },
  { value: 'angst', label: '虐心', color: 'purple', description: '虐心揪心，情感撕扯' },
]

// 战斗能力标签
export const POWER_TYPE_TAGS: TagOption[] = [
  // 超自然能力
  { value: 'superpower', label: '异能', color: 'rose', description: '超能力、异能觉醒' },
  { value: 'magic', label: '魔法', color: 'purple', description: '魔法体系、法术施放' },
  { value: 'cultivation', label: '修炼', color: 'indigo', description: '修炼升级、境界突破' },
  { value: 'martial_arts', label: '武功', color: 'amber', description: '武学功法、内功外功' },
  { value: 'psychic', label: '精神力', color: 'violet', description: '念力、精神控制、心灵感应' },
  { value: 'elemental', label: '元素', color: 'cyan', description: '金木水火土等元素操控' },
  // 科幻能力
  { value: 'mech', label: '机甲', color: 'blue', description: '机甲驾驶、机体战斗' },
  { value: 'gene', label: '基因', color: 'green', description: '基因改造、超凡体质' },
  { value: 'cyber', label: '赛博', color: 'teal', description: '机械义体、赛博改造' },
  { value: 'psionic', label: '灵能', color: 'sky', description: '灵能力场、念动力量' },
  // 特殊能力
  { value: 'summon', label: '召唤', color: 'emerald', description: '召唤兽、契约生物' },
  { value: 'transformation', label: '变身', color: 'orange', description: '形态变化、变身战斗' },
  { value: 'time_space', label: '时空', color: 'slate', description: '时间操控、空间转移' },
  { value: 'soul', label: '灵魂', color: 'fuchsia', description: '灵魂出窍、亡灵操控' },
  { value: 'curse', label: '诅咒', color: 'red', description: '诅咒术、蛊毒' },
  { value: 'divination', label: '预言', color: 'gold', description: '预知未来、占卜' },
  { value: 'alchemy', label: '炼金', color: 'yellow', description: '炼金术、药剂炼制' },
  { value: 'formation', label: '阵法', color: 'cyan', description: '阵纹、结界、风水与空间布置' },
  { value: 'artifact', label: '法宝器物', color: 'amber', description: '神器、法宝、遗物或武装装备体系' },
  { value: 'bloodline', label: '血脉', color: 'red', description: '血统觉醒、种族传承、天赋能力' },
  { value: 'contract', label: '契约', color: 'emerald', description: '契约兽、契约神明、规则契约' },
  { value: 'system_panel', label: '系统面板', color: 'green', description: '任务、属性、技能树、奖励兑换' },
  { value: 'rule_power', label: '规则权柄', color: 'slate', description: '掌控世界规则、概念、法则或权限' },
  { value: 'faith', label: '信仰神术', color: 'gold', description: '神明、信徒、神术与信仰反馈' },
  { value: 'technology_weapon', label: '科技武装', color: 'blue', description: '枪械、舰船、无人机、高能武器' },
  { value: 'biotech', label: '生物科技', color: 'green', description: '生化改造、虫族、克隆与器官强化' },
  { value: 'horror_rule', label: '诡异规则', color: 'dark', description: '怪谈、禁忌、污染与规则杀' },
  { value: 'political_power', label: '权谋资源', color: 'stone', description: '权势、军队、情报网、经济资源' },
  { value: 'no_power', label: '无超能力', color: 'gray', description: '普通人类、无特殊能力' },
]

// 标签分类配置
export interface TagCategory {
  key: string
  label: string
  description: string
  tags: TagOption[]
  multiSelect: boolean
  maxSelect?: number
}

export const TAG_CATEGORIES: TagCategory[] = [
  {
    key: 'world_type',
    label: '世界类型',
    description: '故事发生的背景世界',
    tags: WORLD_TYPE_TAGS,
    multiSelect: false,
  },
  {
    key: 'content_styles',
    label: '内容风格',
    description: '小说的整体风格和内容倾向',
    tags: CONTENT_STYLE_TAGS,
    multiSelect: true,
    maxSelect: 5,
  },
  {
    key: 'protagonist_types',
    label: '主角类型',
    description: '主角的性别和叙事视角',
    tags: PROTAGONIST_TYPE_TAGS,
    multiSelect: false,
  },
  {
    key: 'power_types',
    label: '战斗能力',
    description: '世界观中的力量体系和战斗方式',
    tags: POWER_TYPE_TAGS,
    multiSelect: true,
    maxSelect: 5,
  },
  {
    key: 'character_archetypes',
    label: '角色人设',
    description: '热门角色人设模板，用于角色创建参考',
    tags: CHARACTER_ARCHETYPE_TAGS,
    multiSelect: true,
    maxSelect: 5,
  },
  {
    key: 'tone',
    label: '故事基调',
    description: '故事的整体氛围和情感基调',
    tags: TONE_TAGS,
    multiSelect: true,
    maxSelect: 2,
  },
]

// 根据值获取标签信息的辅助函数
export function getTagByValue(category: string, value: string): TagOption | undefined {
  const categoryConfig = TAG_CATEGORIES.find(c => c.key === category)
  return categoryConfig?.tags.find(t => t.value === value)
}

export function getTagLabel(category: string, value: string): string {
  return getTagByValue(category, value)?.label || value
}
