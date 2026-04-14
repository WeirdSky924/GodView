-- V18: 补全缺失的 Skills（第五批：质量检测类）
-- 这些是评估员 Agent 的核心检测能力

-- ==================== 质量检测类 Skills ====================

-- 章节质量评估
INSERT INTO skills (id, name, description, skill_type, category, tags, applicable_agent_types, prompt_template, parameters, output_spec, priority, status, is_system, is_enabled, load_mode)
VALUES (
    'skill_chapter_evaluation',
    '章节质量评估',
    '从多个维度评估章节内容质量',
    'prompt',
    'evaluation',
    '["评估", "质量", "章节"]',
    '["evaluator"]',
    '## 任务：章节质量评估

请评估以下章节内容的质量：

### 章节内容
{{chapter_content}}

### 评估背景
- 目标字数：{{target_words}}
- 章节序号：第 {{chapter_number}} 章
- 是否第一章：{{is_first_chapter}}

### 评估维度

1. **字数达标**（必要项）
   - 实际字数是否达标
   - 未达标则直接打回

2. **前文连贯**（重要项）
   - 与前文是否自然衔接
   - 人物状态是否一致
   - 时间线是否连贯

3. **情节质量**（25分）
   - 逻辑性：事件发展是否合理
   - 吸引力：是否引人入胜
   - 节奏感：张弛是否适度

4. **人物塑造**（25分）
   - 一致性：行为是否符合性格
   - 立体感：人物是否丰满
   - 对话质量：对话是否自然

5. **语言表达**（25分）
   - 流畅度：语言是否流畅
   - 表现力：描写是否生动
   - 准确性：有无语法错误

6. **整体效果**（25分）
   - 可读性：是否容易阅读
   - 感染力：是否能打动读者
   - 完整性：是否有明显缺失

### 评分标准
- 8-10分：优秀，通过
- 6-7分：良好，小问题，通过但建议优化
- 4-5分：一般，需要修改后重新评估
- 1-3分：不合格，需要大幅修改或重写

### 输出格式（JSON）
```json
{
  "total_score": 85,
  "word_count_check": {"actual": 2800, "target": 3000, "passed": true},
  "coherence_check": {"score": 90, "issues": []},
  "dimensions": {
    "plot": {"score": 22, "comment": "评价"},
    "character": {"score": 20, "comment": "评价"},
    "language": {"score": 23, "comment": "评价"},
    "overall": {"score": 20, "comment": "评价"}
  },
  "strengths": ["优点"],
  "weaknesses": ["不足"],
  "critical_issues": ["必须修改的问题"],
  "suggestions": ["改进建议"],
  "conclusion": "通过/需修改/需重写"
}
```',
    '[{"name": "chapter_content", "type": "string", "description": "章节内容", "required": true}, {"name": "target_words", "type": "number", "description": "目标字数"}, {"name": "chapter_number", "type": "number", "description": "章节序号"}, {"name": "is_first_chapter", "type": "boolean", "description": "是否第一章"}]',
    '[{"name": "total_score", "type": "number"}, {"name": "word_count_check", "type": "object"}, {"name": "coherence_check", "type": "object"}, {"name": "dimensions", "type": "object"}, {"name": "strengths", "type": "array"}, {"name": "weaknesses", "type": "array"}, {"name": "critical_issues", "type": "array"}, {"name": "suggestions", "type": "array"}, {"name": "conclusion", "type": "string"}]',
    80,
    'active',
    true,
    true,
    'on_demand'
) ON CONFLICT (id) DO UPDATE SET
    prompt_template = EXCLUDED.prompt_template,
    parameters = EXCLUDED.parameters;

-- 爽点检测分析
INSERT INTO skills (id, name, description, skill_type, category, tags, applicable_agent_types, prompt_template, parameters, priority, status, is_system, is_enabled, load_mode)
VALUES (
    'skill_cool_point_detection',
    '爽点检测分析',
    '检测章节中的爽点设计是否合理有效',
    'prompt',
    'evaluation',
    '["爽点", "检测", "网文"]',
    '["writer", "evaluator"]',
    '## 任务：爽点检测分析

请分析以下内容中的爽点设计：

### 章节内容
{{chapter_content}}

### 爽点类型

1. **打脸爽**：被轻视后反击
2. **升级爽**：实力提升、获得宝物
3. **逆袭爽**：绝境翻盘
4. **装逼爽**：低调装逼、扮猪吃虎
5. **复仇爽**：报仇雪恨
6. **收获爽**：获得认可、奖励
7. **解气爽**：恶人受惩
8. **揭秘爽**：真相大白

### 分析要求

1. **爽点识别**
   - 找出所有爽点
   - 分析爽点类型
   - 评估爽点强度

2. **爽点质量**
   - 铺垫是否充分
   - 释放是否到位
   - 节奏是否合理

3. **爽点分布**
   - 密度是否适中
   - 是否有疲劳感
   - 是否有期待感

### 输出格式（JSON）
```json
{
  "cool_points": [
    {"type": "打脸爽", "location": "第X段", "intensity": "高", "quality": "优秀", "setup": "铺垫情况", "payoff": "释放情况"}
  ],
  "overall_score": 85,
  "distribution": {"density": "适中", "balance": "合理"},
  "suggestions": ["建议"]
}
```',
    '[{"name": "chapter_content", "type": "string", "description": "章节内容", "required": true}]',
    90,
    'active',
    true,
    true,
    'on_demand'
) ON CONFLICT (id) DO UPDATE SET
    prompt_template = EXCLUDED.prompt_template,
    parameters = EXCLUDED.parameters;

-- OOC角色崩坏检查
INSERT INTO skills (id, name, description, skill_type, category, tags, applicable_agent_types, prompt_template, parameters, priority, status, is_system, is_enabled, load_mode)
VALUES (
    'skill_ooc_check',
    'OOC角色崩坏检查',
    '检测角色行为是否符合人物设定，避免OOC（Out of Character）',
    'prompt',
    'evaluation',
    '["OOC", "角色", "一致性"]',
    '["evaluator", "character"]',
    '## 任务：OOC角色崩坏检查

请检查以下内容中的角色行为是否符合设定：

### 章节内容
{{chapter_content}}

### 角色设定
{{character_profiles}}

### 检查维度

1. **行为一致性**
   - 角色行为是否符合性格
   - 是否有突兀的性格转变
   - 行为动机是否合理

2. **对话一致性**
   - 说话方式是否符合人设
   - 用词是否符合身份背景
   - 是否有人物混同

3. **能力一致性**
   - 角色能力是否与设定匹配
   - 是否有突然变强/变弱
   - 能力使用是否符合规则

4. **情感一致性**
   - 情感反应是否合理
   - 情感变化是否有铺垫
   - 与之前情感状态是否衔接

### 输出格式（JSON）
```json
{
  "ooc_issues": [
    {"character": "角色名", "type": "行为", "location": "位置", "issue": "问题描述", "severity": "严重程度"}
  ],
  "character_scores": {"角色名": {"consistency": 85, "issues": []}},
  "overall_consistency": 90,
  "needs_revision": false,
  "suggestions": ["修改建议"]
}
```',
    '[{"name": "chapter_content", "type": "string", "description": "章节内容", "required": true}, {"name": "character_profiles", "type": "array", "description": "角色设定列表"}]',
    75,
    'active',
    true,
    true,
    'on_demand'
) ON CONFLICT (id) DO UPDATE SET
    prompt_template = EXCLUDED.prompt_template,
    parameters = EXCLUDED.parameters;

-- 剧情漏洞检测
INSERT INTO skills (id, name, description, skill_type, category, tags, applicable_agent_types, prompt_template, parameters, priority, status, is_system, is_enabled, load_mode)
VALUES (
    'skill_plot_hole_detection',
    '剧情漏洞检测',
    '检测剧情中的逻辑漏洞、前后矛盾和不合理之处',
    'prompt',
    'evaluation',
    '["剧情", "漏洞", "逻辑"]',
    '["evaluator"]',
    '## 任务：剧情漏洞检测

请检测以下内容中的剧情漏洞：

### 章节内容
{{chapter_content}}

### 已有故事背景
{{story_context}}

### 检测类型

1. **逻辑漏洞**
   - 因果关系不合理
   - 行为动机缺失
   - 结果与前提矛盾

2. **前后矛盾**
   - 与前文设定冲突
   - 时间线混乱
   - 人物状态不一致

3. **设定冲突**
   - 违反世界观规则
   - 能力体系问题
   - 地理/时间错误

4. **信息缺失**
   - 关键信息未交代
   - 角色行为缺少铺垫
   - 转折缺乏支撑

### 输出格式（JSON）
```json
{
  "plot_holes": [
    {"type": "逻辑漏洞", "location": "位置", "description": "描述", "severity": "严重程度", "suggestion": "修复建议"}
  ],
  "severity_count": {"critical": 0, "major": 1, "minor": 2},
  "overall_score": 90,
  "needs_fix": true/false,
  "fix_priorities": ["优先修复的问题"]
}
```',
    '[{"name": "chapter_content", "type": "string", "description": "章节内容", "required": true}, {"name": "story_context", "type": "string", "description": "已有故事背景"}]',
    95,
    'active',
    true,
    true,
    'on_demand'
) ON CONFLICT (id) DO UPDATE SET
    prompt_template = EXCLUDED.prompt_template,
    parameters = EXCLUDED.parameters;

-- 角色记忆一致性检查
INSERT INTO skills (id, name, description, skill_type, category, tags, applicable_agent_types, prompt_template, parameters, priority, status, is_system, is_enabled, load_mode)
VALUES (
    'skill_character_memory_check',
    '角色记忆一致性检查',
    '检查角色是否表现出应有的记忆，避免角色"失忆"',
    'prompt',
    'evaluation',
    '["记忆", "一致性", "角色"]',
    '["evaluator", "character"]',
    '## 任务：角色记忆一致性检查

请检查角色的记忆表现是否一致：

### 章节内容
{{chapter_content}}

### 角色已知信息
{{character_knowledge}}

### 历史互动记录
{{interaction_history}}

### 检查维度

1. **信息记忆**
   - 角色是否记得已知道的信息
   - 是否出现不应有的"失忆"
   - 是否有不应有的预知

2. **情感记忆**
   - 对他人的态度是否一致
   - 情感变化是否有依据
   - 好恶是否有延续

3. **经历记忆**
   - 是否记得共同经历
   - 对事件的反应是否合理
   - 成长变化是否有迹可循

### 输出格式（JSON）
```json
{
  "memory_issues": [
    {"character": "角色名", "type": "信息记忆", "issue": "问题描述", "location": "位置"}
  ],
  "characters_checked": ["角色列表"],
  "overall_score": 95,
  "suggestions": ["建议"]
}
```',
    '[{"name": "chapter_content", "type": "string", "description": "章节内容", "required": true}, {"name": "character_knowledge", "type": "object", "description": "角色已知信息"}, {"name": "interaction_history", "type": "array", "description": "历史互动记录"}]',
    90,
    'active',
    true,
    true,
    'on_demand'
) ON CONFLICT (id) DO UPDATE SET
    prompt_template = EXCLUDED.prompt_template,
    parameters = EXCLUDED.parameters;

-- 设定冲突检测
INSERT INTO skills (id, name, description, skill_type, category, tags, applicable_agent_types, prompt_template, parameters, priority, status, is_system, is_enabled, load_mode)
VALUES (
    'skill_setting_conflict_detection',
    '设定冲突检测',
    '检测内容是否与已有世界观设定冲突',
    'prompt',
    'evaluation',
    '["设定", "冲突", "世界观"]',
    '["evaluator", "setting"]',
    '## 任务：设定冲突检测

请检测以下内容是否与世界观设定冲突：

### 章节内容
{{chapter_content}}

### 世界观设定
{{world_settings}}

### 检测维度

1. **规则冲突**
   - 是否违反核心规则
   - 能力使用是否合规
   - 代价条件是否满足

2. **地理冲突**
   - 地点描述是否一致
   - 空间关系是否正确
   - 移动时间是否合理

3. **势力冲突**
   - 势力关系是否正确
   - 行为是否符合势力立场
   - 组织设定是否一致

4. **历史冲突**
   - 历史引用是否正确
   - 时间线是否合理
   - 人物年龄经历是否匹配

### 输出格式（JSON）
```json
{
  "conflicts": [
    {"type": "规则冲突", "setting_id": "设定ID", "conflict": "冲突描述", "severity": "严重程度", "fix_suggestion": "修复建议"}
  ],
  "checked_settings": ["检查的设定"],
  "overall_compliance": 95,
  "critical_conflicts": [],
  "suggestions": ["建议"]
}
```',
    '[{"name": "chapter_content", "type": "string", "description": "章节内容", "required": true}, {"name": "world_settings", "type": "array", "description": "世界观设定"}]',
    85,
    'active',
    true,
    true,
    'on_demand'
) ON CONFLICT (id) DO UPDATE SET
    prompt_template = EXCLUDED.prompt_template,
    parameters = EXCLUDED.parameters;

-- 战力体系校验
INSERT INTO skills (id, name, description, skill_type, category, tags, applicable_agent_types, prompt_template, parameters, priority, status, is_system, is_enabled, load_mode)
VALUES (
    'skill_power_level_check',
    '战力体系校验',
    '校验战斗描写是否符合战力设定，避免战力崩坏',
    'prompt',
    'evaluation',
    '["战力", "体系", "战斗"]',
    '["master_plotter", "evaluator"]',
    '## 任务：战力体系校验

请校验以下战斗内容是否符合战力设定：

### 战斗内容
{{combat_content}}

### 战力设定
{{power_system}}

### 参战角色战力
{{combatant_levels}}

### 校验维度

1. **能力使用**
   - 技能是否在能力范围内
   - 代价/限制是否体现
   - 使用方式是否符合规则

2. **战力对比**
   - 战斗结果是否合理
   - 实力差距是否正确体现
   - 是否有不合逻辑的"越级"

3. **成长合理性**
   - 实力提升是否有铺垫
   - 战斗表现是否稳定
   - 是否有突然变强/变弱

### 输出格式（JSON）
```json
{
  "power_issues": [
    {"character": "角色", "type": "问题类型", "description": "描述", "severity": "严重程度"}
  ],
  "combat_valid": true,
  "power_balance": {"attacker": "高", "defender": "中", "result": "合理"},
  "suggestions": ["建议"]
}
```',
    '[{"name": "combat_content", "type": "string", "description": "战斗内容", "required": true}, {"name": "power_system", "type": "object", "description": "战力设定"}, {"name": "combatant_levels", "type": "object", "description": "参战角色战力"}]',
    90,
    'active',
    true,
    true,
    'on_demand'
) ON CONFLICT (id) DO UPDATE SET
    prompt_template = EXCLUDED.prompt_template,
    parameters = EXCLUDED.parameters;

-- 节奏分析
INSERT INTO skills (id, name, description, skill_type, category, tags, applicable_agent_types, prompt_template, parameters, priority, status, is_system, is_enabled, load_mode)
VALUES (
    'skill_pacing_analysis',
    '节奏分析',
    '分析章节的叙事节奏是否合理',
    'prompt',
    'analysis',
    '["节奏", "叙事", "分析"]',
    '["master_plotter", "evaluator"]',
    '## 任务：节奏分析

请分析以下内容的叙事节奏：

### 章节内容
{{chapter_content}}

### 分析维度

1. **信息节奏**
   - 信息密度是否适中
   - 重要信息是否突出
   - 是否有信息过载

2. **情绪节奏**
   - 情绪曲线是否合理
   - 高潮位置是否恰当
   - 缓冲是否足够

3. **段落节奏**
   - 段落长短是否变化
   - 切换是否自然
   - 重点是否突出

4. **句子节奏**
   - 长短句是否交替
   - 节奏感如何
   - 是否有单调感

### 输出格式（JSON）
```json
{
  "overall_pacing": {"score": 85, "level": "良好"},
  "dimensions": {
    "information": {"score": 90, "comment": "评价"},
    "emotion": {"score": 80, "comment": "评价"},
    "paragraph": {"score": 85, "comment": "评价"},
    "sentence": {"score": 85, "comment": "评价"}
  },
  "rhythm_curve": [{"position": "25%", "intensity": "中"}, {"position": "50%", "intensity": "高"}, {"position": "75%", "intensity": "低"}],
  "suggestions": ["节奏优化建议"]
}
```',
    '[{"name": "chapter_content", "type": "string", "description": "章节内容", "required": true}]',
    75,
    'active',
    true,
    true,
    'on_demand'
) ON CONFLICT (id) DO UPDATE SET
    prompt_template = EXCLUDED.prompt_template,
    parameters = EXCLUDED.parameters;

-- 对话风格一致性检查
INSERT INTO skills (id, name, description, skill_type, category, tags, applicable_agent_types, prompt_template, parameters, priority, status, is_system, is_enabled, load_mode)
VALUES (
    'skill_dialogue_style_check',
    '对话风格一致性检查',
    '检查对话是否符合各角色的说话风格',
    'prompt',
    'evaluation',
    '["对话", "风格", "一致性"]',
    '["evaluator", "character"]',
    '## 任务：对话风格一致性检查

请检查对话风格是否一致：

### 章节内容
{{chapter_content}}

### 角色说话风格设定
{{character_speech_styles}}

### 检查维度

1. **用词风格**
   - 是否符合角色身份
   - 是否符合教育背景
   - 是否符合性格特点

2. **句式特点**
   - 长短句偏好是否一致
   - 口头禅是否保留
   - 语序特点是否体现

3. **情感表达**
   - 表达方式是否符合人设
   - 情绪反应是否合理
   - 内心活动是否一致

4. **人物区分**
   - 不同角色是否有区别
   - 读者能否从对话识别角色
   - 是否有人物混同

### 输出格式（JSON）
```json
{
  "dialogues_analyzed": 20,
  "style_issues": [
    {"character": "角色名", "dialogue": "对话内容", "issue": "问题描述", "suggestion": "修改建议"}
  ],
  "character_distinctness": {"score": 85, "comment": "人物区分度评价"},
  "overall_score": 90,
  "suggestions": ["整体建议"]
}
```',
    '[{"name": "chapter_content", "type": "string", "description": "章节内容", "required": true}, {"name": "character_speech_styles", "type": "object", "description": "角色说话风格设定"}]',
    80,
    'active',
    true,
    true,
    'on_demand'
) ON CONFLICT (id) DO UPDATE SET
    prompt_template = EXCLUDED.prompt_template,
    parameters = EXCLUDED.parameters;

-- 敏感词检测
INSERT INTO skills (id, name, description, skill_type, category, tags, applicable_agent_types, prompt_template, parameters, priority, status, is_system, is_enabled, load_mode)
VALUES (
    'skill_sensitive_word_detection',
    '敏感词检测',
    '检测内容中是否包含敏感词汇，确保内容安全',
    'prompt',
    'evaluation',
    '["敏感词", "检测", "安全"]',
    '["writer", "evaluator"]',
    '## 任务：敏感词检测

请检测以下内容中的敏感词：

### 章节内容
{{chapter_content}}

### 检测类型

1. **政治敏感**
   - 政治人物、事件相关
   - 政治体制相关表述
   - 敏感政治词汇

2. **色情低俗**
   - 露骨描写
   - 低俗表达
   - 暗示性内容

3. **暴力恐怖**
   - 过度暴力描写
   - 恐怖主义相关
   - 血腥内容

4. **违法内容**
   - 违法行为描写
   - 毒品相关
   - 赌博相关

5. **歧视偏见**
   - 种族歧视
   - 地域歧视
   - 性别歧视

### 输出格式（JSON）
```json
{
  "sensitive_words": [
    {"word": "敏感词", "type": "类型", "location": "位置", "severity": "严重程度", "suggestion": "替换建议"}
  ],
  "severity_count": {"critical": 0, "major": 0, "minor": 1},
  "overall_safe": true,
  "needs_revision": false,
  "auto_replace_suggestions": {"原词": "替换词"}
}
```',
    '[{"name": "chapter_content", "type": "string", "description": "章节内容", "required": true}]',
    95,
    'active',
    true,
    true,
    'on_demand'
) ON CONFLICT (id) DO UPDATE SET
    prompt_template = EXCLUDED.prompt_template,
    parameters = EXCLUDED.parameters;

-- 时间线校验
INSERT INTO skills (id, name, description, skill_type, category, tags, applicable_agent_types, prompt_template, parameters, priority, status, is_system, is_enabled, load_mode)
VALUES (
    'skill_timeline_verification',
    '时间线校验',
    '校验时间线是否正确，避免时间矛盾',
    'prompt',
    'evaluation',
    '["时间线", "校验", "逻辑"]',
    '["evaluator"]',
    '## 任务：时间线校验

请校验以下内容的时间线：

### 章节内容
{{chapter_content}}

### 已有时间线
{{existing_timeline}}

### 校验维度

1. **时间顺序**
   - 事件顺序是否正确
   - 闪回是否标注清楚
   - 有无时间错乱

2. **时间跨度**
   - 时间流逝是否合理
   - 行程时间是否足够
   - 季节变化是否正确

3. **时间标记**
   - 时间描述是否清晰
   - "三天后"等是否计算正确
   - 年龄/日期是否一致

4. **时间冲突**
   - 是否有矛盾的时间点
   - 同时发生的事件是否正确
   - 时间差是否合理

### 输出格式（JSON）
```json
{
  "timeline_valid": true,
  "events": [
    {"event": "事件", "time": "时间点", "order": 1, "valid": true}
  ],
  "time_issues": [
    {"type": "问题类型", "description": "描述", "location": "位置", "fix": "修复建议"}
  ],
  "suggestions": ["建议"]
}
```',
    '[{"name": "chapter_content", "type": "string", "description": "章节内容", "required": true}, {"name": "existing_timeline", "type": "array", "description": "已有时间线"}]',
    70,
    'active',
    true,
    true,
    'on_demand'
) ON CONFLICT (id) DO UPDATE SET
    prompt_template = EXCLUDED.prompt_template,
    parameters = EXCLUDED.parameters;

-- 黄金三章检测
INSERT INTO skills (id, name, description, skill_type, category, tags, applicable_agent_types, prompt_template, parameters, priority, status, is_system, is_enabled, load_mode)
VALUES (
    'skill_golden_three_chapters',
    '黄金三章检测',
    '检测小说开篇三章是否符合黄金三章标准',
    'prompt',
    'evaluation',
    '["黄金三章", "开篇", "吸引"]',
    '["evaluator"]',
    '## 任务：黄金三章检测

请检测开篇三章是否符合黄金三章标准：

### 前三章内容
{{first_three_chapters}}

### 检测维度

1. **第一章检测**
   - 开篇100字是否抓住注意力
   - 主角是否有清晰亮相
   - 是否有悬念/钩子
   - 世界观呈现是否自然

2. **第二章检测**
   - 是否深化读者兴趣
   - 冲突/困境是否展开
   - 关键配角是否引入
   - 核心设定是否揭示

3. **第三章检测**
   - 故事方向是否明确
   - 核心卖点是否展现
   - 情感连接是否建立
   - 读者是否想继续看

4. **整体检测**
   - 三章是否形成完整体验
   - 节奏是否流畅
   - 是否有让人追更的欲望

### 输出格式（JSON）
```json
{
  "overall_score": 85,
  "chapters": [
    {"number": 1, "score": 90, "strengths": ["优点"], "issues": ["问题"], "suggestions": ["建议"]}
  ],
  "golden_rules_checked": {
    "attention_grabbing": true,
    "protagonist_clear": true,
    "hook_present": true,
    "world_natural": true,
    "direction_clear": true,
    "want_to_read_more": true
  },
  "improvement_priorities": ["优先改进项"]
}
```',
    '[{"name": "first_three_chapters", "type": "string", "description": "前三章内容", "required": true}]',
    85,
    'active',
    true,
    true,
    'on_demand'
) ON CONFLICT (id) DO UPDATE SET
    prompt_template = EXCLUDED.prompt_template,
    parameters = EXCLUDED.parameters;
