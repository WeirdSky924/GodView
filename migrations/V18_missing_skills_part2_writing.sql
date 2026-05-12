-- V18: 补全缺失的 Skills（第二批：写作能力类）
-- 这些是作家 Agent 和场景协调 Agent 的核心写作能力

-- ==================== 写作能力类 Skills ====================

-- 章节写作（作家核心技能）
INSERT INTO skills (id, name, description, skill_type, category, tags, applicable_agent_types, prompt_template, parameters, output_spec, priority, status, is_system, is_enabled, load_mode)
VALUES (
    'skill_chapter_writing',
    '章节写作',
    '根据大纲和上下文，写作完整章节内容的核心技能',
    'prompt',
    'writing',
    '["写作", "章节", "内容生成"]',
    '["writer", "scene_coordinator"]',
    '## 任务：章节写作

请根据以下信息写作章节内容：

### 章节信息
- 章节标题：{{chapter_title}}
- 章节序号：第 {{chapter_number}} 章
- 目标字数：{{target_words}} 字（最低要求：{{min_words}} 字）

### 章节大纲
{{chapter_outline}}

### 前情提要
{{story_context}}

### 写作要求

1. **字数要求**（强制）
   - 必须达到最低字数要求
   - 建议控制在目标字数的±10%

2. **内容要求**
   - 严格按照大纲展开
   - 与前文自然衔接
   - 包含大纲中的关键情节点

3. **风格要求**
   - 保持与已有章节风格一致
   - 使用具体的感官描写
   - 对话要符合人物性格

4. **技巧要求**
   - 长短句交替使用
   - 场景描写服务于情节
   - 适时加入心理活动

### 输出格式（JSON）
```json
{
  "content": "章节正文内容",
  "word_count": 实际字数,
  "outline_coverage": ["已覆盖的大纲要点"],
  "highlights": ["本章亮点"],
  "hooks_embedded": ["埋入的伏笔"]
}
```',
    '[{"name": "chapter_title", "type": "string", "description": "章节标题", "required": true}, {"name": "chapter_number", "type": "number", "description": "章节序号"}, {"name": "target_words", "type": "number", "description": "目标字数", "default": 3000}, {"name": "min_words", "type": "number", "description": "最低字数", "default": 2400}, {"name": "chapter_outline", "type": "string", "description": "章节大纲", "required": true}, {"name": "story_context", "type": "string", "description": "前情提要"}]',
    '[{"name": "content", "type": "string"}, {"name": "word_count", "type": "number"}, {"name": "outline_coverage", "type": "array"}, {"name": "highlights", "type": "array"}, {"name": "hooks_embedded", "type": "array"}]',
    80,
    'active',
    true,
    true,
    'on_demand'
) ON CONFLICT (id) DO UPDATE SET
    prompt_template = EXCLUDED.prompt_template,
    parameters = EXCLUDED.parameters;

-- 场景描写
INSERT INTO skills (id, name, description, skill_type, category, tags, applicable_agent_types, prompt_template, parameters, priority, status, is_system, is_enabled, load_mode)
VALUES (
    'skill_scene_description',
    '场景描写',
    '生成生动、有画面感的场景描写',
    'prompt',
    'writing',
    '["场景", "描写", "画面感"]',
    '["writer", "scene_coordinator"]',
    '## 任务：场景描写

请根据以下信息生成场景描写：

### 场景信息
- 场景类型：{{scene_type}}
- 场景地点：{{location}}
- 时间：{{time_of_day}}
- 氛围基调：{{atmosphere}}

### 场景作用
{{scene_purpose}}

### 描写要求

1. **感官描写**
   - 视觉：光线、色彩、形态
   - 听觉：声音、动静、节奏
   - 嗅觉：气味、气息
   - 触觉：温度、质感
   - 味觉（如适用）

2. **氛围营造**
   - 环境要与情绪呼应
   - 用细节传递氛围
   - 适度留白，不要过度描写

3. **功能导向**
   - 描写要服务于情节
   - 突出与剧情相关的细节
   - 为后续发展做铺垫

4. **篇幅控制**
   - 主要场景：200-400字
   - 过渡场景：50-100字
   - 战斗场景：精简有力

### 输出
直接输出场景描写内容，不要包含额外说明。',
    '[{"name": "scene_type", "type": "string", "description": "场景类型"}, {"name": "location", "type": "string", "description": "场景地点"}, {"name": "time_of_day", "type": "string", "description": "时间"}, {"name": "atmosphere", "type": "string", "description": "氛围基调"}, {"name": "scene_purpose", "type": "string", "description": "场景作用"}]',
    60,
    'active',
    true,
    true,
    'on_demand'
) ON CONFLICT (id) DO UPDATE SET
    prompt_template = EXCLUDED.prompt_template,
    parameters = EXCLUDED.parameters;

-- 场景表演指导
INSERT INTO skills (id, name, description, skill_type, category, tags, applicable_agent_types, prompt_template, parameters, priority, status, is_system, is_enabled, load_mode)
VALUES (
    'skill_scene_directions',
    '场景表演指导',
    '为多角色场景提供表演指导，协调角色出场、行动和对话',
    'prompt',
    'direction',
    '["表演", "指导", "协调"]',
    '["master_plotter", "scene_coordinator"]',
    '## 任务：场景表演指导

请为以下场景提供表演指导：

### 场景信息
- 场景名称：{{scene_name}}
- 场景类型：{{scene_type}}
- 参与角色：{{characters}}

### 场景目标
{{scene_goal}}

### 表演指导要点

1. **角色出场安排**
   - 出场顺序和方式
   - 各角色的关注点
   - 舞台位置和移动

2. **对话分配**
   - 谁说什么、为什么说
   - 对话的节奏控制
   - 潜台词和信息层次

3. **动作设计**
   - 关键动作和反应
   - 肢体语言表达
   - 眼神和微表情

4. **情绪曲线**
   - 各角色的情绪变化
   - 场景整体的节奏
   - 高潮点的设置

5. **互动设计**
   - 角色间的化学反应
   - 冲突和和解
   - 权力动态变化

### 输出格式（JSON）
```json
{
  "stage_directions": "舞台指导说明",
  "character_beats": [
    {"character": "角色名", "actions": "动作", "emotion": "情绪", "objective": "目标"}
  ],
  "dialogue_hints": {"角色名": "对话风格提示"},
  "climax_point": "场景高潮点",
  "transition": "转场建议"
}
```',
    '[{"name": "scene_name", "type": "string", "description": "场景名称"}, {"name": "scene_type", "type": "string", "description": "场景类型"}, {"name": "characters", "type": "array", "description": "参与角色"}, {"name": "scene_goal", "type": "string", "description": "场景目标"}]',
    75,
    'active',
    true,
    true,
    'on_demand'
) ON CONFLICT (id) DO UPDATE SET
    prompt_template = EXCLUDED.prompt_template,
    parameters = EXCLUDED.parameters;

-- 章节悬念钩子生成
INSERT INTO skills (id, name, description, skill_type, category, tags, applicable_agent_types, prompt_template, parameters, priority, status, is_system, is_enabled, load_mode)
VALUES (
    'skill_chapter_hook_generator',
    '章节悬念钩子生成',
    '为章节结尾生成吸引人的悬念钩子',
    'prompt',
    'writing',
    '["悬念", "钩子", "结尾"]',
    '["writer"]',
    '## 任务：章节悬念钩子生成

请为以下章节内容生成结尾悬念钩子：

### 章节内容摘要
{{chapter_summary}}

### 本章关键事件
{{key_events}}

### 下章预告（如有）
{{next_chapter_hint}}

### 悬念钩子类型

1. **危机型钩子**
   - 主角陷入危险
   - 意外事件发生
   - 紧迫的威胁

2. **揭示型钩子**
   - 重要信息揭晓
   - 身份暴露
   - 真相浮出水面

3. **转折型钩子**
   - 意想不到的变化
   - 关系逆转
   - 新势力介入

4. **期待型钩子**
   - 即将发生的大事
   - 重要的约定或承诺
   - 目标临近

### 钩子要求

1. **吸引力**：能让读者想继续看下一章
2. **合理性**：与本章内容自然衔接
3. **适度性**：不夸张，不欺骗读者
4. **独特性**：避免老套的"欲知后事如何"

### 输出格式（JSON）
```json
{
  "hook_type": "钩子类型",
  "hook_content": "钩子内容（1-3句话）",
  "emotion_target": "目标读者情绪",
  "next_lead": "对下章的铺垫"
}
```',
    '[{"name": "chapter_summary", "type": "string", "description": "章节内容摘要"}, {"name": "key_events", "type": "array", "description": "本章关键事件"}, {"name": "next_chapter_hint", "type": "string", "description": "下章预告"}]',
    75,
    'active',
    true,
    true,
    'on_demand'
) ON CONFLICT (id) DO UPDATE SET
    prompt_template = EXCLUDED.prompt_template,
    parameters = EXCLUDED.parameters;

-- 章节标题优化
INSERT INTO skills (id, name, description, skill_type, category, tags, applicable_agent_types, prompt_template, parameters, priority, status, is_system, is_enabled, load_mode)
VALUES (
    'skill_chapter_title_optimizer',
    '章节标题优化',
    '优化章节标题，使其更吸引读者',
    'prompt',
    'writing',
    '["标题", "优化", "吸引"]',
    '["writer"]',
    '## 任务：章节标题优化

请为以下章节优化标题：

### 章节内容摘要
{{chapter_summary}}

### 当前标题
{{current_title}}

### 标题优化原则

1. **信息量**：透露关键信息但不剧透
2. **吸引力**：让读者想点进去看
3. **风格统一**：与作品整体风格一致
4. **简洁有力**：一般不超过10个字

### 标题类型

1. **人物型**：突出角色名或身份
2. **事件型**：描述关键事件
3. **悬念型**：制造疑问
4. **意象型**：使用象征或比喻
5. **引用型**：引用名句或诗词

### 输出格式（JSON）
```json
{
  "recommended_title": "推荐标题",
  "alternatives": ["备选1", "备选2", "备选3"],
  "title_type": "标题类型",
  "reason": "推荐理由"
}
```',
    '[{"name": "chapter_summary", "type": "string", "description": "章节内容摘要"}, {"name": "current_title", "type": "string", "description": "当前标题"}]',
    65,
    'active',
    true,
    true,
    'on_demand'
) ON CONFLICT (id) DO UPDATE SET
    prompt_template = EXCLUDED.prompt_template,
    parameters = EXCLUDED.parameters;

-- 金句生成
INSERT INTO skills (id, name, description, skill_type, category, tags, applicable_agent_types, prompt_template, parameters, priority, status, is_system, is_enabled, load_mode)
VALUES (
    'skill_golden_line_generator',
    '金句生成',
    '为章节生成适合引用传播的金句',
    'prompt',
    'writing',
    '["金句", "名句", "传播"]',
    '["writer"]',
    '## 任务：金句生成

请根据以下内容生成金句：

### 场景/对话上下文
{{context}}

### 情感基调
{{emotion}}

### 金句要求

1. **简洁有力**：一般不超过20字
2. **含义深刻**：有哲理或情感共鸣
3. **朗朗上口**：易于记忆和传播
4. **符合语境**：自然融入情节

### 金句类型

1. **人生哲理型**：关于人生、成长的感悟
2. **情感共鸣型**：触动情感的表白或内心独白
3. **霸气宣言型**：展现人物决心或气势
4. **幽默机智型**：风趣幽默的妙语
5. **诗意唯美型**：意境优美的描述

### 输出格式（JSON）
```json
{
  "golden_lines": [
    {"content": "金句内容", "type": "类型", "context": "适用场景"},
    {"content": "金句内容2", "type": "类型", "context": "适用场景"}
  ],
  "recommended": "最推荐的金句",
  "insertion_hint": "建议插入位置"
}
```',
    '[{"name": "context", "type": "string", "description": "场景/对话上下文"}, {"name": "emotion", "type": "string", "description": "情感基调"}]',
    70,
    'active',
    true,
    true,
    'on_demand'
) ON CONFLICT (id) DO UPDATE SET
    prompt_template = EXCLUDED.prompt_template,
    parameters = EXCLUDED.parameters;
