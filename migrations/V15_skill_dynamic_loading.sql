-- V15: Skill 动态加载支持
-- 添加双层加载机制：核心层(CORE)始终加载，按需层(ON_DEMAND)根据场景关键词动态加载

-- ==================== Skills 表：添加加载模式字段 ====================

-- 添加加载模式字段
ALTER TABLE skills ADD COLUMN IF NOT EXISTS load_mode VARCHAR(50) DEFAULT 'on_demand';
COMMENT ON COLUMN skills.load_mode IS '加载模式: core=始终加载, on_demand=按需加载';

-- 添加触发关键词字段
ALTER TABLE skills ADD COLUMN IF NOT EXISTS trigger_keywords JSONB DEFAULT '[]';
COMMENT ON COLUMN skills.trigger_keywords IS '触发关键词列表（按需加载时匹配场景关键词）';

-- 添加触发场景字段
ALTER TABLE skills ADD COLUMN IF NOT EXISTS trigger_scenes JSONB DEFAULT '[]';
COMMENT ON COLUMN skills.trigger_scenes IS '触发场景类型列表（如：战斗、对话、谈判）';

-- 创建索引以支持关键词搜索
CREATE INDEX IF NOT EXISTS idx_skills_load_mode ON skills(load_mode);
CREATE INDEX IF NOT EXISTS idx_skills_trigger_keywords ON skills USING GIN(trigger_keywords);
CREATE INDEX IF NOT EXISTS idx_skills_trigger_scenes ON skills USING GIN(trigger_scenes);

-- ==================== Skill Assignments 表：添加覆盖配置 ====================

-- 添加加载模式覆盖字段
ALTER TABLE skill_assignments ADD COLUMN IF NOT EXISTS load_mode VARCHAR(50);
COMMENT ON COLUMN skill_assignments.load_mode IS '加载模式覆盖（NULL表示使用Skill的默认设置）';

-- 添加触发关键词覆盖字段
ALTER TABLE skill_assignments ADD COLUMN IF NOT EXISTS trigger_keywords JSONB DEFAULT '[]';
COMMENT ON COLUMN skill_assignments.trigger_keywords IS '触发关键词覆盖';

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_skill_assignments_load_mode ON skill_assignments(load_mode);

-- ==================== 示例数据：核心层 Skills ====================
-- 这些 Skills 将始终加载到 Agent 的上下文中

-- 示例：不可抄袭规则（核心层）
INSERT INTO skills (id, name, description, skill_type, category, knowledge_content, priority, status, is_system, is_enabled, load_mode)
VALUES (
    'skill_no_plagiarism',
    '不可抄袭原则',
    '所有 Agent 必须遵守的创作基础规则：严禁抄袭已有作品内容',
    'knowledge',
    'general',
    '## 不可抄袭原则

作为创作助手，你必须遵守以下原则：

1. **原创性要求**：所有生成的内容必须是原创的，不能直接复制或模仿已有作品的情节、对话、人物设定等。

2. **借鉴与抄袭的区别**：
   - 借鉴：学习优秀作品的写作技巧、叙事手法、结构安排
   - 抄袭：直接复制具体内容、情节走向、人物对话等

3. **避免行为**：
   - 不使用其他作品中的经典台词或名场面
   - 不照搬其他作品的情节发展
   - 不模仿其他作品的角色设定

4. **正确做法**：
   - 学习优秀作品的技巧，融入自己的创作
   - 在通用框架下创造独特的内容
   - 建立属于自己的世界观和人物体系',
    100,
    'active',
    true,
    true,
    'core'
) ON CONFLICT (id) DO UPDATE SET
    knowledge_content = EXCLUDED.knowledge_content,
    priority = EXCLUDED.priority,
    load_mode = EXCLUDED.load_mode;

-- 示例：基础创作规范（核心层）
INSERT INTO skills (id, name, description, skill_type, category, knowledge_content, priority, status, is_system, is_enabled, load_mode)
VALUES (
    'skill_basic_writing_rules',
    '基础创作规范',
    '所有 Agent 必须遵守的基础创作规范',
    'knowledge',
    'writing',
    '## 基础创作规范

### 语言规范
1. 使用规范、流畅的中文写作
2. 避免语法错误和错别字
3. 合理使用标点符号

### 叙事规范
1. 保持叙事视角的一致性
2. 时间线清晰，避免逻辑矛盾
3. 场景描写要服务于情节

### 人物塑造规范
1. 人物行为要符合性格设定
2. 对话要体现人物特点
3. 人物成长要有铺垫

### 情节设计规范
1. 情节发展要有内在逻辑
2. 冲突要有起因、发展和结果
3. 高潮要铺垫到位',
    95,
    'active',
    true,
    true,
    'core'
) ON CONFLICT (id) DO UPDATE SET
    knowledge_content = EXCLUDED.knowledge_content,
    priority = EXCLUDED.priority,
    load_mode = EXCLUDED.load_mode;

-- ==================== 示例数据：按需层 Skills ====================
-- 这些 Skills 只在特定场景下才会加载

-- 示例：战斗场景技能（按需层）
INSERT INTO skills (id, name, description, skill_type, category, prompt_template, priority, status, is_system, is_enabled, load_mode, trigger_keywords, trigger_scenes)
VALUES (
    'skill_combat_scene',
    '战斗场景写作',
    '战斗场景的写作技巧和规范',
    'prompt',
    'writing',
    '## 战斗场景写作指南

当前场景为战斗场景，请遵循以下原则：

### 动作描写
- 动作要具体、有画面感
- 注意战斗节奏的变化
- 合理安排攻防转换

### 氛围渲染
- 通过环境描写增强紧张感
- 利用感官细节营造沉浸感
- 适时加入心理描写

### 技能/能力描写
- 技能效果要具体生动
- 注意能力的限制和代价
- 避免过度夸张

### 结果呈现
- 战斗结果要符合逻辑
- 留有后续发展的空间',
    70,
    'active',
    true,
    true,
    'on_demand',
    '["战斗", "打斗", "对决", "交锋", "厮杀", "比武", "格斗"]',
    '["combat", "battle", "fight"]'
) ON CONFLICT (id) DO UPDATE SET
    prompt_template = EXCLUDED.prompt_template,
    priority = EXCLUDED.priority,
    load_mode = EXCLUDED.load_mode,
    trigger_keywords = EXCLUDED.trigger_keywords,
    trigger_scenes = EXCLUDED.trigger_scenes;

-- 示例：恋爱场景技能（按需层）
INSERT INTO skills (id, name, description, skill_type, category, prompt_template, priority, status, is_system, is_enabled, load_mode, trigger_keywords, trigger_scenes)
VALUES (
    'skill_romance_scene',
    '恋爱场景写作',
    '恋爱/情感场景的写作技巧',
    'prompt',
    'writing',
    '## 恋爱场景写作指南

当前场景为恋爱/情感场景，请遵循以下原则：

### 情感描写
- 情感要细腻真实
- 注意情感的渐进发展
- 避免过于直白或生硬

### 对话设计
- 对话要体现人物性格
- 注意言外之意和潜台词
- 适当使用肢体语言描写

### 氛围营造
- 环境要与情感相呼应
- 利用细节增强代入感
- 注意节奏把控

### 分寸把握
- 避免过于露骨的描写
- 注意读者接受度
- 留有想象空间',
    70,
    'active',
    true,
    true,
    'on_demand',
    '["恋爱", "爱情", "告白", "暧昧", "情侣", "心动", "甜蜜", "虐恋"]',
    '["romance", "love", "dating"]'
) ON CONFLICT (id) DO UPDATE SET
    prompt_template = EXCLUDED.prompt_template,
    priority = EXCLUDED.priority,
    load_mode = EXCLUDED.load_mode,
    trigger_keywords = EXCLUDED.trigger_keywords,
    trigger_scenes = EXCLUDED.trigger_scenes;

-- 示例：谈判场景技能（按需层）
INSERT INTO skills (id, name, description, skill_type, category, prompt_template, priority, status, is_system, is_enabled, load_mode, trigger_keywords, trigger_scenes)
VALUES (
    'skill_negotiation_scene',
    '谈判场景写作',
    '谈判/博弈场景的写作技巧',
    'prompt',
    'writing',
    '## 谈判场景写作指南

当前场景为谈判/博弈场景，请遵循以下原则：

### 心理博弈
- 展现人物的思考和算计
- 注意信息的透露和隐藏
- 描写微表情和心理活动

### 语言艺术
- 对话要有锋芒
- 注意语言的策略性
- 展现言语中的试探与反击

### 节奏把控
- 张弛有度，制造紧张感
- 适时加入外部因素
- 合理安排转折点

### 结果呈现
- 结果要符合逻辑
- 为后续发展埋下伏笔',
    70,
    'active',
    true,
    true,
    'on_demand',
    '["谈判", "博弈", "交涉", "协商", "对峙", "斡旋", "角力"]',
    '["negotiation", "politics", "diplomacy"]'
) ON CONFLICT (id) DO UPDATE SET
    prompt_template = EXCLUDED.prompt_template,
    priority = EXCLUDED.priority,
    load_mode = EXCLUDED.load_mode,
    trigger_keywords = EXCLUDED.trigger_keywords,
    trigger_scenes = EXCLUDED.trigger_scenes;

-- ==================== 更新现有 Skills 的默认加载模式 ====================
-- 将所有未设置 load_mode 的 Skills 设置为 on_demand
UPDATE skills SET load_mode = 'on_demand' WHERE load_mode IS NULL;

-- ==================== 章节写作工作流 Skills ====================
-- 这些 Skills 用于编排长文写作

-- 章节 大纲 Skill
INSERT INTO skills (id, name, description, skill_type, category, prompt_template, priority, status, is_system, is_enabled, load_mode, parameters)
VALUES (
    'skill_chapter_outline',
    '章节大纲生成',
    '根据章节标题和目标字数，生成章节大纲，确定各段落的主题和字数分配',
    'prompt',
    'writing',
    '## 任务：生成章节大纲

根据以下信息生成一个章节大纲：

- 章节标题：{{chapter_title}}
- 目标字数：{{target_words}} 字
{{#chapter_context}}
- 上下文信息：{{chapter_context}}
{{/chapter_context}}

## 输出要求

请生成一个结构化的大纲，包含：

1. **章节概述**（50-100字）
   - 本章主要内容和目的

2. **段落划分**（按目标字数分配）
   | 段落序号 | 主题 | 字数目标 | 关键内容 |
   |---------|------|---------|---------|
   | 1 | ... | ... | ... |
   | ... | ... | ... | ... |

3. **关键要素**
   - 需要埋设的伏笔
   - 需要回收的伏笔
   - 情感高潮点

4. **结尾设计**
   - 悬念/钩子设计

输出格式为 JSON：
```json
{
  "summary": "章节概述",
  "segments": [
    {"index": 1, "topic": "主题", "target_words": 500, "key_content": "关键内容"}
  ],
  "foreshadowing": {"plant": [], "payoff": []},
  "climax_point": "情感高潮点",
  "ending_hook": "结尾钩子"
}
```',
    80,
    'active',
    true,
    true,
    'on_demand',
    '[{"name": "chapter_title", "type": "string", "description": "章节标题", "required": true}, {"name": "target_words", "type": "number", "description": "目标字数", "required": true}, {"name": "chapter_context", "type": "string", "description": "上下文信息"}]'
) ON CONFLICT (id) DO UPDATE SET
    prompt_template = EXCLUDED.prompt_template,
    parameters = EXCLUDED.parameters;

-- 分段写作 Skill
INSERT INTO skills (id, name, description, skill_type, category, prompt_template, priority, status, is_system, is_enabled, load_mode, parameters)
VALUES (
    'skill_segment_writing',
    '分段写作',
    '根据大纲生成单个段落的内容',
    'prompt',
    'writing',
    '## 任务：段落写作

请根据以下大纲和上下文，写作一个段落：

## 段落信息
- 段落序号：{{segment_index}}
- 主题：{{segment_topic}}
- 目标字数：{{segment_target_words}} 字
- 关键内容：{{segment_key_content}}

## 已有内容
{{previous_content}}

## 写作要求
1. 字数尽量接近目标（误差不超过10%）
2. 内容要与上一段自然衔接
3. 风格保持一致
4. 包含大纲中的关键内容

## 输出
直接输出段落内容，不要包含任何解释或标记。',
    75,
    'active',
    true,
    true,
    'on_demand',
    '[{"name": "segment_index", "type": "number", "description": "段落序号", "required": true}, {"name": "segment_topic", "type": "string", "description": "段落主题", "required": true}, {"name": "segment_target_words", "type": "number", "description": "目标字数", "required": true}, {"name": "segment_key_content", "type": "string", "description": "关键内容"}, {"name": "previous_content", "type": "string", "description": "已有的前文内容"}]'
) ON CONFLICT (id) DO UPDATE SET
    prompt_template = EXCLUDED.prompt_template,
    parameters = EXCLUDED.parameters;

-- 内容合并 Skill
INSERT INTO skills (id, name, description, skill_type, category, function_code, priority, status, is_system, is_enabled, load_mode, parameters, output_spec)
VALUES (
    'skill_content_merge',
    '内容合并',
    '将多个段落内容合并为完整章节',
    'function',
    'writing',
    'def execute(segments, chapter_title="", add_transitions=True):
    """
    合并段落内容

    Args:
        segments: 段落内容列表
        chapter_title: 章节标题
        add_transitions: 是否添加过渡句

    Returns:
        dict: {"content": "合并后的内容", "total_words": 总字数}
    """
    if not segments:
        return {"content": "", "total_words": 0}

    # 合并内容
    if isinstance(segments, str):
        # 如果直接传入字符串，尝试按分割符拆分
        import re
        segments = re.split(r"\n{2,}", segments.strip())

    merged_parts = []

    # 添加标题
    if chapter_title:
        merged_parts.append(f"# {chapter_title}\n")

    # 合并段落
    for i, segment in enumerate(segments):
        if segment and segment.strip():
            merged_parts.append(segment.strip())

    content = "\n\n".join(merged_parts)

    return {
        "content": content,
        "total_words": len(content.replace(" ", "").replace("\n", "")),
        "segment_count": len(segments)
    }',
    70,
    'active',
    true,
    true,
    'on_demand',
    '[{"name": "segments", "type": "array", "description": "段落内容列表", "required": true}, {"name": "chapter_title", "type": "string", "description": "章节标题"}, {"name": "add_transitions", "type": "boolean", "description": "是否添加过渡句", "default": true}]',
    '[{"name": "content", "type": "string", "description": "合并后的内容"}, {"name": "total_words", "type": "number", "description": "总字数"}, {"name": "segment_count", "type": "number", "description": "段落数量"}]'
) ON CONFLICT (id) DO UPDATE SET
    function_code = EXCLUDED.function_code,
    parameters = EXCLUDED.parameters,
    output_spec = EXCLUDED.output_spec;

-- 字数统计 Skill
INSERT INTO skills (id, name, description, skill_type, category, function_code, priority, status, is_system, is_enabled, load_mode, parameters, output_spec)
VALUES (
    'skill_word_count',
    '字数统计与评估',
    '统计内容字数并与目标对比，返回差值和建议',
    'function',
    'analysis',
    'def execute(content, target_words=3000):
    """
    统计字数并与目标对比

    Args:
        content: 要统计的内容
        target_words: 目标字数

    Returns:
        dict: 字数统计结果
    """
    if not content:
        return {
            "actual_words": 0,
            "target_words": target_words,
            "difference": target_words,
            "completion_rate": 0,
            "needs_more": True,
            "suggestion": "内容为空，需要从头开始写作"
        }

    # 计算字数（排除空白字符）
    actual_words = len(content.replace(" ", "").replace("\n", ""))

    difference = target_words - actual_words
    completion_rate = round(actual_words / target_words * 100, 1) if target_words > 0 else 100

    needs_more = difference > target_words * 0.1  # 误差超过10%才需要继续

    suggestion = ""
    if needs_more:
        if difference > 0:
            suggestion = f"还需要增加约 {difference} 字"
        else:
            suggestion = f"已超出目标 {-difference} 字，可以适当删减"
    else:
        suggestion = "字数达标"

    return {
        "actual_words": actual_words,
        "target_words": target_words,
        "difference": difference,
        "completion_rate": completion_rate,
        "needs_more": needs_more,
        "suggestion": suggestion
    }',
    70,
    'active',
    true,
    true,
    'on_demand',
    '[{"name": "content", "type": "string", "description": "要统计的内容", "required": true}, {"name": "target_words", "type": "number", "description": "目标字数", "default": 3000}]',
    '[{"name": "actual_words", "type": "number", "description": "实际字数"}, {"name": "target_words", "type": "number", "description": "目标字数"}, {"name": "difference", "type": "number", "description": "差值（正数表示不足）"}, {"name": "completion_rate", "type": "number", "description": "完成率（百分比）"}, {"name": "needs_more", "type": "boolean", "description": "是否需要更多内容"}, {"name": "suggestion", "type": "string", "description": "建议"}]'
) ON CONFLICT (id) DO UPDATE SET
    function_code = EXCLUDED.function_code,
    parameters = EXCLUDED.parameters,
    output_spec = EXCLUDED.output_spec;

-- 续写 Skill
INSERT INTO skills (id, name, description, skill_type, category, prompt_template, priority, status, is_system, is_enabled, load_mode, parameters)
VALUES (
    'skill_continue_writing',
    '续写',
    '根据已有内容继续写作',
    'prompt',
    'writing',
    '## 任务：续写

根据已有内容继续写作，补足字数。

## 已有内容
{{existing_content}}

## 字数信息
- 当前字数：{{current_words}} 字
- 目标字数：{{target_words}} 字
- 还需增加：约 {{words_needed}} 字

## 续写要求
1. 从已有内容的结尾自然衔接
2. 增加新的内容（不要重复已有内容）
3. 保持风格和叙事节奏一致
4. 新增内容约 {{words_needed}} 字

## 输出
直接输出续写的内容，不要包含任何解释或标记。',
    70,
    'active',
    true,
    true,
    'on_demand',
    '[{"name": "existing_content", "type": "string", "description": "已有内容", "required": true}, {"name": "current_words", "type": "number", "description": "当前字数"}, {"name": "target_words", "type": "number", "description": "目标字数"}, {"name": "words_needed", "type": "number", "description": "还需增加的字数"}]'
) ON CONFLICT (id) DO UPDATE SET
    prompt_template = EXCLUDED.prompt_template,
    parameters = EXCLUDED.parameters;

-- ==================== 注释更新 ====================
COMMENT ON TABLE skills IS 'Agent 技能定义表，支持双层加载机制和编排';
