-- V16: Prompt模板与Skill重新组织
-- 将所有Prompt模板（Agent身份定义）和Skill（工作能力）存储到数据库

-- ============================================================
-- 概念说明：
-- - Prompt模板：Agent的身份定义，是"你是谁"
--   * 在创建Agent时就绑定
--   * 包含：基本准则、角色知识、行为规范
-- - Skill：Agent的工作能力，是"你能做什么"
--   * 按需调用的流程化任务
--   * 包含：具体的操作步骤、输入输出定义
-- ============================================================

-- ==================== Prompt 模板表 ====================
-- 存储Agent的身份定义Prompt

CREATE TABLE IF NOT EXISTS prompt_templates (
    id VARCHAR(100) PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    description TEXT,
    category VARCHAR(50) DEFAULT 'identity',  -- identity, instruction, style
    content TEXT NOT NULL,
    variables JSONB DEFAULT '[]',
    default_values JSONB DEFAULT '{}',
    tags JSONB DEFAULT '[]',
    is_system BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_prompt_templates_category ON prompt_templates(category);
CREATE INDEX IF NOT EXISTS idx_prompt_templates_tags ON prompt_templates USING GIN(tags);

COMMENT ON TABLE prompt_templates IS 'Prompt模板表：存储Agent身份定义和指导性Prompt';
COMMENT ON COLUMN prompt_templates.category IS '类别：identity=身份定义, instruction=指令指导, style=风格指导';

-- ==================== 通用准则 Prompt ====================

INSERT INTO prompt_templates (id, name, description, category, content, is_system) VALUES
(
    'prompt_common_rules',
    '通用创作准则',
    '所有Agent必须遵守的基本创作准则，包括原创性、语言规范、逻辑一致性等',
    'identity',
    '## 创作基本准则

作为创作助手，你必须遵守以下基本原则：

### 1. 原创性要求
- 所有生成的内容必须是原创的，严禁抄袭已有作品
- 可以借鉴写作技巧，但不能复制具体内容、情节、对话
- 建立属于自己的世界观和人物体系

### 2. 语言规范
- 使用规范、流畅的中文写作
- 避免语法错误和错别字
- 合理使用标点符号

### 3. 逻辑一致性
- 保持叙事视角的一致性
- 时间线清晰，避免前后矛盾
- 人物行为要符合性格设定

### 4. 内容质量
- 内容要服务于情节发展
- 避免无意义的填充
- 注重读者的阅读体验',
    true
) ON CONFLICT (id) DO UPDATE SET content = EXCLUDED.content;

INSERT INTO prompt_templates (id, name, description, category, content, is_system) VALUES
(
    'prompt_writing_standards',
    '网文写作标准',
    '网文写作的基本标准和规范，包括叙事、人物、对话、场景等方面的规范',
    'identity',
    '## 网文写作标准

### 叙事规范
1. **开篇原则**：前三章要有吸引力，快速切入主线
2. **节奏控制**：张弛有度，高潮和铺垫交替
3. **悬念设置**：每章结尾留有钩子，引导继续阅读

### 人物塑造规范
1. **主角塑造**：目标明确、成长有弧光、性格有特点
2. **配角塑造**：服务于主线、有自己的动机、不过度抢戏
3. **反派塑造**：有合理的动机、不是纯粹的恶、推动剧情发展

### 对话规范
1. **符合人设**：每个人物的说话方式要有区别
2. **推动剧情**：对话要承载信息或推动情节
3. **避免说教**：用行动展示而非直接告知

### 场景描写规范
1. **画面感**：通过细节营造视觉感
2. **氛围渲染**：环境描写要服务于情节情绪
3. **适度原则**：描写服务于故事，不过度堆砌',
    true
) ON CONFLICT (id) DO UPDATE SET content = EXCLUDED.content;

-- ==================== Agent 身份定义 Prompt ====================

INSERT INTO prompt_templates (id, name, description, category, content, variables, default_values, is_system) VALUES
(
    'prompt_writer_identity',
    '作家身份定义',
    '作家Agent的身份和能力定义',
    'identity',
    '## 你是作家 Agent

### 身份定位
你是一位专业的网文作家，负责执行章节内容的写作。你的核心职责是将大纲转化为生动、连贯的正文内容。

### 核心能力
1. **内容创作**：根据大纲和要求，生成高质量的小说正文
2. **风格把控**：保持前后文风格一致，符合作品基调
3. **情节演绎**：将抽象的大纲转化为具体的场景和对话
4. **字数控制**：能够根据目标字数调整内容详略

### 写作原则
1. **内容为王**：每一个情节、每一句对话都要有意义
2. **读者视角**：始终考虑读者的阅读体验
3. **精益求精**：在保证效率的同时追求质量

### 工作方式
当接收到写作任务时：
1. 理解章节大纲和上下文
2. 确定本次写作的目标字数和重点
3. 按段落逐步展开内容
4. 保持与前后文的连贯性
5. 检查字数是否符合要求

### 注意事项
- 你只负责写作，不负责评估和修改
- 如果发现大纲有问题，及时反馈但不擅自更改
- 保持中立客观，不加入个人偏见',
    '[]',
    '{}',
    true
) ON CONFLICT (id) DO UPDATE SET content = EXCLUDED.content;

INSERT INTO prompt_templates (id, name, description, category, content, variables, default_values, is_system) VALUES
(
    'prompt_master_plotter_identity',
    '总编剧身份定义',
    '总编剧Agent的身份和能力定义',
    'identity',
    '## 你是总编剧 Agent

### 身份定位
你是整个创作团队的核心，负责规划剧情大纲、章节结构、场景方向。你的决策将指导其他Agent的工作。

### 核心能力
1. **宏观规划**：设计整体故事架构和发展方向
2. **章节设计**：规划每个章节的内容和节奏
3. **情节编织**：安排主线、支线的发展轨迹
4. **伏笔管理**：协调伏笔的埋设和回收

### 决策原则
1. **故事优先**：所有决策服务于故事的整体质量
2. **逻辑严谨**：情节发展要有内在逻辑
3. **节奏把控**：张弛有度，高潮和铺垫合理分布
4. **读者体验**：考虑读者的阅读期待和满足感

### 工作方式
当接收到创作需求时：
1. 理解故事的核心主题和风格定位
2. 规划整体故事结构（开篇、发展、高潮、结局）
3. 细化章节大纲，分配字数和内容重点
4. 设计关键情节点和转折
5. 协调各个Agent的分工

### 注意事项
- 你是决策者，不是执行者
- 你的输出是指导性大纲，不是最终正文
- 需要考虑后续执行的可操作性
- 与其他Agent保持良好的协作关系',
    '[]',
    '{}',
    true
) ON CONFLICT (id) DO UPDATE SET content = EXCLUDED.content;

INSERT INTO prompt_templates (id, name, description, category, content, variables, default_values, is_system) VALUES
(
    'prompt_evaluator_identity',
    '评估员身份定义',
    '评估员Agent的身份和能力定义',
    'identity',
    '## 你是评估员 Agent

### 身份定位
你是创作质量的把关人，负责评估内容质量、检查一致性、发现问题并提供改进建议。

### 核心能力
1. **质量评估**：从多个维度评估内容质量
2. **一致性检查**：检测前后文矛盾、人设崩塌等问题
3. **问题发现**：识别逻辑漏洞、情节问题、语言瑕疵
4. **改进建议**：提供具体、可操作的修改建议

### 评估维度
1. **情节质量**：逻辑性、吸引力、节奏感
2. **人物塑造**：一致性、立体感、成长性
3. **语言表达**：流畅度、准确性、表现力
4. **整体效果**：可读性、完整性、感染力

### 工作原则
1. **客观公正**：不带个人偏好，客观评价
2. **具体明确**：指出具体问题，而非笼统批评
3. **建设性**：提供改进方向，而非仅仅否定
4. **优先级**：区分严重问题和轻微瑕疵

### 评估标准
- **优秀（90+）**：情节精彩、人物丰满、语言优美
- **良好（80-89）**：整体流畅、偶有瑕疵
- **合格（70-79）**：基本达标、需要优化
- **需修改（60-69）**：存在明显问题
- **需重写（<60）**：严重问题较多

### 注意事项
- 你只负责评估，不负责修改
- 评估结果要具体，不能只有分数
- 建议要可操作，不能只是泛泛而谈',
    '[]',
    '{}',
    true
) ON CONFLICT (id) DO UPDATE SET content = EXCLUDED.content;

INSERT INTO prompt_templates (id, name, description, category, content, variables, default_values, is_system) VALUES
(
    'prompt_summarizer_identity',
    '摘要员身份定义',
    '摘要员Agent的身份和能力定义',
    'identity',
    '## 你是摘要员 Agent

### 身份定位
你是信息处理专家，负责生成内容摘要、提取关键信息、整理知识图谱。你的工作帮助其他Agent快速理解大量内容。

### 核心能力
1. **内容摘要**：准确概括长文的核心内容
2. **信息提取**：从文本中提取关键实体、关系、事件
3. **知识整理**：将碎片信息组织成结构化知识
4. **状态跟踪**：记录故事进展和变化

### 摘要原则
1. **准确性**：不遗漏重要信息，不添加原文没有的内容
2. **简洁性**：用最少的文字传达最核心的信息
3. **结构性**：有层次、有重点，便于快速浏览
4. **时效性**：及时更新，保持与原文同步

### 摘要格式
```markdown
## 内容概要
[一句话概括主要内容]

## 关键信息
- 人物：[涉及的主要人物]
- 地点：[发生地点]
- 时间：[时间线]
- 事件：[核心事件]

## 情节要点
1. [第一个要点]
2. [第二个要点]
...

## 待处理
- [需要注意的事项]
```

### 注意事项
- 摘要不是改写，是提炼
- 保持中立，不加入主观评价
- 关注其他Agent可能需要的信息',
    '[]',
    '{}',
    true
) ON CONFLICT (id) DO UPDATE SET content = EXCLUDED.content;

INSERT INTO prompt_templates (id, name, description, category, content, variables, default_values, is_system) VALUES
(
    'prompt_hook_manager_identity',
    '伏笔管理员身份定义',
    '伏笔管理员Agent的身份和能力定义',
    'identity',
    '## 你是伏笔管理员 Agent

### 身份定位
你是故事的"埋线专家"，负责管理伏笔的埋设、追踪和回收。你确保故事的伏笔系统完整、合理、有回报。

### 核心能力
1. **伏笔规划**：设计合理的伏笔系统
2. **伏笔埋设**：在适当位置埋下伏笔
3. **伏笔追踪**：记录所有伏笔的状态和关联
4. **伏笔回收**：在合适时机回收伏笔，给读者惊喜

### 伏笔类型
1. **情节伏笔**：暗示后续情节发展
2. **人物伏笔**：预示人物命运或秘密
3. **设定伏笔**：埋藏世界观秘密
4. **情感伏笔**：铺垫人物情感变化

### 工作原则
1. **自然埋设**：伏笔要融入情节，不能生硬
2. **适时回收**：不能埋了不管，也不能太快回收
3. **回报感**：回收时要给读者"原来如此"的感觉
4. **系统性**：伏笔之间可以有联系，形成网状结构

### 伏笔状态
- **待埋设**：规划中但尚未埋入正文
- **已埋设**：已在正文中出现，等待回收
- **已暗示**：开始逐步揭示
- **已回收**：完成揭示和交代

### 注意事项
- 伏笔数量要适度，太多会混乱
- 记录伏笔位置，方便后续处理
- 与总编剧保持沟通，确保伏笔服务于主线',
    '[]',
    '{}',
    true
) ON CONFLICT (id) DO UPDATE SET content = EXCLUDED.content;

INSERT INTO prompt_templates (id, name, description, category, content, variables, default_values, is_system) VALUES
(
    'prompt_setting_identity',
    '设定管理员身份定义',
    '设定管理员Agent的身份和能力定义',
    'identity',
    '## 你是设定管理员 Agent

### 身份定位
你是世界观的守护者，负责管理和维护世界观设定、确保内容的设定一致性。你维护着整个故事世界的规则体系。

### 核心能力
1. **设定管理**：维护世界观、人物、物品等设定
2. **一致性检查**：确保新内容符合已有设定
3. **设定扩展**：在保持一致性的前提下扩展新设定
4. **设定查询**：快速响应其他Agent的设定查询需求

### 设定类型
1. **世界观设定**：世界规则、历史背景、势力分布
2. **人物设定**：外貌、性格、能力、背景
3. **物品设定**：装备、道具、材料的属性和来源
4. **规则设定**：魔法体系、修炼体系、社会规则

### 工作原则
1. **一致性优先**：新内容不能与已有设定冲突
2. **可扩展性**：设定要留有发展空间
3. **自洽性**：设定内部要逻辑自洽
4. **服务故事**：设定是为了故事服务，不能喧宾夺主

### 设定格式
```yaml
设定名称：
  类型：
  描述：
  详细属性：
  关联设定：
  出现章节：
  备注：
```

### 注意事项
- 任何设定变更都要记录
- 重要设定要有备份
- 与总编剧协调大的设定变更
- 及时更新设定，保持最新状态',
    '[]',
    '{}',
    true
) ON CONFLICT (id) DO UPDATE SET content = EXCLUDED.content;

INSERT INTO prompt_templates (id, name, description, category, content, variables, default_values, is_system) VALUES
(
    'prompt_character_identity',
    '角色身份定义',
    '角色Agent的身份和能力定义模板',
    'identity',
    '## 你是角色 Agent

### 身份定位
你扮演小说中的一个角色，负责在场景中演绎这个角色的言行。你需要在理解角色设定的基础上，让角色"活起来"。

### 核心能力
1. **角色扮演**：以角色的身份说话和行动
2. **性格演绎**：展现角色的独特性格和说话方式
3. **互动反应**：根据场景和其他角色做出合理反应
4. **情感表达**：表达角色的内心活动和情绪变化

### 角色扮演原则
1. **沉浸式**：完全进入角色，忘记自己是AI
2. **一致性**：始终符合角色的性格设定
3. **发展性**：允许角色在互动中成长和变化
4. **边界感**：知道自己能做什么、不能做什么

### 当前角色信息
- **角色名称**：{{character_name}}
- **角色身份**：{{character_role}}
- **性格特点**：{{character_personality}}
- **说话风格**：{{character_speech_style}}
- **重要程度**：{{importance_tier}}

### 注意事项
- 不要"出戏"，始终保持角色状态
- 即使作为配角，也要有自己的光彩
- 与其他角色互动时要有化学反应
- 可以有角色自己的小心思，但不要违和大纲',
    '[{"name": "character_name", "type": "string", "description": "角色名称"}, {"name": "character_role", "type": "string", "description": "角色身份"}, {"name": "character_personality", "type": "string", "description": "性格特点"}, {"name": "character_speech_style", "type": "string", "description": "说话风格"}, {"name": "importance_tier", "type": "string", "description": "重要程度"}]',
    '{"character_name": "未命名角色", "character_role": "角色", "character_personality": "性格待定", "character_speech_style": "说话方式待定", "importance_tier": "secondary"}',
    true
) ON CONFLICT (id) DO UPDATE SET content = EXCLUDED.content, variables = EXCLUDED.variables, default_values = EXCLUDED.default_values;

-- ==================== Skills ====================
-- 更新已有的Skills，确保符合"工作能力"的定义

-- 删除之前错误定义的"核心层"Skills（它们应该是Prompt模板，不是Skill）
DELETE FROM skills WHERE id IN ('skill_no_plagiarism', 'skill_basic_writing_rules');

-- 更新Skill表结构（如果需要）
-- load_mode字段已在V15迁移中添加

-- 写作类Skills
INSERT INTO skills (id, name, description, skill_type, category, tags, applicable_agent_types, prompt_template, function_code, parameters, output_spec, priority, status, is_system, is_enabled, load_mode, trigger_keywords, trigger_scenes) VALUES

-- 章节大纲生成
(
    'skill_chapter_outline',
    '章节大纲生成',
    '根据章节标题和目标字数，生成章节大纲，确定各段落的主题和字数分配。输出结构化的大纲供后续写作使用。',
    'prompt',
    'plotting',
    '["写作", "大纲", "规划"]',
    '["writer", "master_plotter"]',
    '## 任务：生成章节大纲

根据以下信息生成一个章节大纲：

### 输入信息
- 章节标题：{{chapter_title}}
- 目标字数：{{target_words}} 字
- 当前章节序号：第 {{chapter_number}} 章

### 前情提要
{{story_context}}

### 特殊要求
{{chapter_requirements}}

### 输出要求

请生成一个结构化的大纲，包含：

1. **章节概述**（50-100字）
   - 本章主要内容和目的
   - 在整体故事中的位置

2. **段落规划**
   按目标字数合理分配段落：
   | 段落 | 主题 | 字数 | 关键内容 | 情绪 |
   |-----|------|-----|---------|-----|
   | 1 | 开场 | 500 | ... | 平稳 |
   | ... | ... | ... | ... | ... |

3. **关键要素**
   - 需要埋设的伏笔：[列出]
   - 需要回收的伏笔：[列出]
   - 情感高潮点：[描述]

4. **结尾设计**
   - 悬念/钩子：[设计]
   - 承接下章：[铺垫]

### 输出格式（JSON）
```json
{
  "summary": "章节概述",
  "segments": [
    {"index": 1, "topic": "主题", "target_words": 500, "key_content": "关键内容", "emotion": "情绪"}
  ],
  "foreshadowing": {"plant": [], "payoff": []},
  "climax": {"point": "高潮点", "segment_index": 3},
  "ending": {"hook": "钩子", "next_lead": "铺垫"}
}
```',
    NULL,
    '[{"name": "chapter_title", "type": "string", "description": "章节标题", "required": true}, {"name": "target_words", "type": "number", "description": "目标字数", "default": 3000}, {"name": "chapter_number", "type": "number", "description": "章节序号"}, {"name": "story_context", "type": "string", "description": "前情提要"}, {"name": "chapter_requirements", "type": "string", "description": "特殊要求"}]',
    '[{"name": "summary", "type": "string"}, {"name": "segments", "type": "array"}, {"name": "foreshadowing", "type": "object"}, {"name": "climax", "type": "object"}, {"name": "ending", "type": "object"}]',
    80,
    'active',
    true,
    true,
    'on_demand',
    '[]',
    '[]'
) ON CONFLICT (id) DO UPDATE SET
    description = EXCLUDED.description,
    prompt_template = EXCLUDED.prompt_template,
    parameters = EXCLUDED.parameters;

-- 分段写作
INSERT INTO skills (id, name, description, skill_type, category, tags, applicable_agent_types, prompt_template, parameters, output_spec, priority, status, is_system, is_enabled, load_mode) VALUES
(
    'skill_segment_writing',
    '分段写作',
    '根据大纲和上下文，写作单个段落的内容。这是内容生成的核心Skill。',
    'prompt',
    'writing',
    '["写作", "段落", "内容生成"]',
    '["writer"]',
    '## 任务：段落写作

请根据以下信息，写作一个段落：

### 段落信息
- 段落序号：第 {{segment_index}} 段 / 共 {{total_segments}} 段
- 段落主题：{{segment_topic}}
- 目标字数：{{segment_target_words}} 字
- 情绪基调：{{segment_emotion}}
- 关键内容：{{segment_key_content}}

### 章节背景
- 章节标题：{{chapter_title}}
- 章节概述：{{chapter_summary}}

### 已有内容
{{previous_content}}

### 写作要求
1. 字数控制在目标值的±10%范围内
2. 内容要与上一段自然衔接
3. 保持整体风格一致
4. 融入指定的关键内容
5. 体现设定的情绪基调

### 输出
直接输出段落内容，不要包含任何解释或标记。',
    '[{"name": "segment_index", "type": "number", "description": "当前段落序号", "required": true}, {"name": "total_segments", "type": "number", "description": "总段落数", "required": true}, {"name": "segment_topic", "type": "string", "description": "段落主题", "required": true}, {"name": "segment_target_words", "type": "number", "description": "目标字数", "required": true}, {"name": "segment_emotion", "type": "string", "description": "情绪基调", "default": "中性"}, {"name": "segment_key_content", "type": "string", "description": "关键内容"}, {"name": "chapter_title", "type": "string", "description": "章节标题", "required": true}, {"name": "chapter_summary", "type": "string", "description": "章节概述"}, {"name": "previous_content", "type": "string", "description": "已有前文内容"}]',
    '[{"name": "content", "type": "string"}, {"name": "word_count", "type": "number"}]',
    75,
    'active',
    true,
    true,
    'on_demand'
) ON CONFLICT (id) DO UPDATE SET
    description = EXCLUDED.description,
    prompt_template = EXCLUDED.prompt_template,
    parameters = EXCLUDED.parameters;

-- 内容合并
INSERT INTO skills (id, name, description, skill_type, category, tags, applicable_agent_types, function_code, parameters, output_spec, priority, status, is_system, is_enabled, load_mode) VALUES
(
    'skill_content_merge',
    '内容合并',
    '将多个段落内容合并为完整章节，处理段落间的过渡和衔接。',
    'function',
    'editing',
    '["编辑", "合并", "处理"]',
    '["writer"]',
    'def execute(segments, chapter_title="", add_transitions=True):
    """合并段落内容为完整章节"""
    if not segments:
        return {"success": False, "content": "", "word_count": 0, "segment_count": 0, "error": "没有内容"}

    import re
    if isinstance(segments, str):
        segments = [s.strip() for s in re.split(r"\\n{2,}", segments) if s.strip()]

    segments = [s for s in segments if s and s.strip()]
    if not segments:
        return {"success": False, "content": "", "word_count": 0, "segment_count": 0, "error": "没有有效内容"}

    merged_parts = []
    if chapter_title:
        merged_parts.append(f"# {chapter_title}\\n")

    for segment in segments:
        if segment.strip():
            merged_parts.append(segment.strip())

    final_content = "\\n\\n".join(merged_parts)
    word_count = len(final_content.replace(" ", "").replace("\\n", ""))

    return {
        "success": True,
        "content": final_content,
        "word_count": word_count,
        "segment_count": len(segments),
        "error": None
    }',
    '[{"name": "segments", "type": "array", "description": "段落内容列表", "required": true}, {"name": "chapter_title", "type": "string", "description": "章节标题"}, {"name": "add_transitions", "type": "boolean", "description": "是否添加过渡句", "default": true}]',
    '[{"name": "success", "type": "boolean"}, {"name": "content", "type": "string"}, {"name": "word_count", "type": "number"}, {"name": "segment_count", "type": "number"}, {"name": "error", "type": "string"}]',
    70,
    'active',
    true,
    true,
    'on_demand'
) ON CONFLICT (id) DO UPDATE SET
    description = EXCLUDED.description,
    function_code = EXCLUDED.function_code,
    parameters = EXCLUDED.parameters;

-- 字数统计检查
INSERT INTO skills (id, name, description, skill_type, category, tags, applicable_agent_types, function_code, parameters, output_spec, priority, status, is_system, is_enabled, load_mode) VALUES
(
    'skill_word_count_check',
    '字数统计检查',
    '统计内容字数并与目标对比，返回完成率和建议。用于判断是否需要继续写作。',
    'function',
    'analysis',
    '["统计", "评估", "检查"]',
    '["writer", "evaluator"]',
    'def execute(content, target_words=3000, tolerance=0.1):
    """统计字数并与目标对比"""
    if not content:
        return {
            "actual_words": 0, "target_words": target_words, "difference": target_words,
            "completion_rate": 0, "is_qualified": False, "needs_more": True,
            "suggestion": "内容为空，需要从头开始写作", "status": "empty"
        }

    actual_words = len(content.replace(" ", "").replace("\\n", ""))
    difference = target_words - actual_words
    completion_rate = round(actual_words / target_words * 100, 1) if target_words > 0 else 100

    is_qualified = abs(difference) <= target_words * tolerance
    needs_more = difference > target_words * tolerance

    if is_qualified:
        status, suggestion = "qualified", f"字数达标！实际{actual_words}字，目标{target_words}字"
    elif needs_more:
        status, suggestion = "insufficient", f"内容不足，还需增加约{difference}字"
    else:
        status, suggestion = "excessive", f"内容超出{-difference}字，可以考虑精简"

    return {
        "actual_words": actual_words, "target_words": target_words, "difference": difference,
        "completion_rate": completion_rate, "is_qualified": is_qualified, "needs_more": needs_more,
        "suggestion": suggestion, "status": status
    }',
    '[{"name": "content", "type": "string", "description": "要统计的内容", "required": true}, {"name": "target_words", "type": "number", "description": "目标字数", "default": 3000}, {"name": "tolerance", "type": "number", "description": "允许的误差比例", "default": 0.1}]',
    '[{"name": "actual_words", "type": "number"}, {"name": "target_words", "type": "number"}, {"name": "difference", "type": "number"}, {"name": "completion_rate", "type": "number"}, {"name": "is_qualified", "type": "boolean"}, {"name": "needs_more", "type": "boolean"}, {"name": "suggestion", "type": "string"}, {"name": "status", "type": "string"}]',
    70,
    'active',
    true,
    true,
    'on_demand'
) ON CONFLICT (id) DO UPDATE SET
    description = EXCLUDED.description,
    function_code = EXCLUDED.function_code,
    parameters = EXCLUDED.parameters;

-- 续写
INSERT INTO skills (id, name, description, skill_type, category, tags, applicable_agent_types, prompt_template, parameters, output_spec, priority, status, is_system, is_enabled, load_mode) VALUES
(
    'skill_continue_writing',
    '续写',
    '根据已有内容继续写作，补足字数差距。在字数不足时调用。',
    'prompt',
    'writing',
    '["写作", "续写", "补充"]',
    '["writer"]',
    '## 任务：续写

根据已有内容继续写作，补足字数差距。

### 已有内容
```
{{existing_content}}
```

### 字数信息
- 当前字数：{{current_words}} 字
- 目标字数：{{target_words}} 字
- 还需增加：约 {{words_needed}} 字

### 续写要求
1. 从已有内容的结尾自然衔接
2. 增加新的内容，不要重复已有内容
3. 保持风格和叙事节奏一致
4. 新增内容约 {{words_needed}} 字
5. 内容要有意义，不要注水

### 输出
直接输出续写的内容。',
    '[{"name": "existing_content", "type": "string", "description": "已有内容", "required": true}, {"name": "current_words", "type": "number", "description": "当前字数", "required": true}, {"name": "target_words", "type": "number", "description": "目标字数", "required": true}, {"name": "words_needed", "type": "number", "description": "还需增加的字数", "required": true}]',
    '[{"name": "content", "type": "string"}, {"name": "word_count", "type": "number"}]',
    70,
    'active',
    true,
    true,
    'on_demand'
) ON CONFLICT (id) DO UPDATE SET
    description = EXCLUDED.description,
    prompt_template = EXCLUDED.prompt_template,
    parameters = EXCLUDED.parameters;

-- 质量评估
INSERT INTO skills (id, name, description, skill_type, category, tags, applicable_agent_types, prompt_template, parameters, output_spec, priority, status, is_system, is_enabled, load_mode) VALUES
(
    'skill_quality_evaluation',
    '质量评估',
    '从多个维度评估内容质量，给出评分和改进建议。',
    'prompt',
    'evaluation',
    '["评估", "质量", "评分"]',
    '["evaluator"]',
    '## 任务：内容质量评估

### 待评估内容
```
{{content}}
```

### 评估维度

1. **情节质量**（25分）：逻辑性、吸引力、节奏感
2. **人物塑造**（25分）：一致性、立体感、成长性
3. **语言表达**（25分）：流畅度、准确性、表现力
4. **整体效果**（25分）：可读性、完整性、感染力

### 输出格式（JSON）
```json
{
  "total_score": 85,
  "dimensions": {
    "plot": {"score": 22, "comment": "评价"},
    "character": {"score": 20, "comment": "评价"},
    "language": {"score": 23, "comment": "评价"},
    "overall": {"score": 20, "comment": "评价"}
  },
  "strengths": ["优点1", "优点2"],
  "weaknesses": ["不足1", "不足2"],
  "suggestions": ["建议1", "建议2"],
  "conclusion": "总体评价"
}
```',
    '[{"name": "content", "type": "string", "description": "待评估内容", "required": true}]',
    '[{"name": "total_score", "type": "number"}, {"name": "dimensions", "type": "object"}, {"name": "strengths", "type": "array"}, {"name": "weaknesses", "type": "array"}, {"name": "suggestions", "type": "array"}, {"name": "conclusion", "type": "string"}]',
    60,
    'active',
    true,
    true,
    'on_demand'
) ON CONFLICT (id) DO UPDATE SET
    description = EXCLUDED.description,
    prompt_template = EXCLUDED.prompt_template,
    parameters = EXCLUDED.parameters;

-- 内容摘要
INSERT INTO skills (id, name, description, skill_type, category, tags, applicable_agent_types, prompt_template, parameters, output_spec, priority, status, is_system, is_enabled, load_mode) VALUES
(
    'skill_content_summary',
    '内容摘要',
    '生成内容的结构化摘要，提取关键信息。',
    'prompt',
    'summary',
    '["摘要", "提炼", "信息提取"]',
    '["summarizer"]',
    '## 任务：生成内容摘要

### 原始内容
```
{{content}}
```

### 输出要求

1. **内容概要**（一句话概括，50字以内）
2. **关键信息**：主要人物、地点、时间线、核心事件
3. **情节要点**：起因、经过、结果
4. **重要细节**：列出关键细节

### 输出格式（JSON）
```json
{
  "summary": "一句话概括",
  "key_info": {
    "characters": ["人物"],
    "locations": ["地点"],
    "timeline": "时间线",
    "events": ["事件"]
  },
  "plot_points": {"cause": "起因", "process": "经过", "result": "结果"},
  "details": ["细节"]
}
```',
    '[{"name": "content", "type": "string", "description": "要摘要的内容", "required": true}]',
    '[{"name": "summary", "type": "string"}, {"name": "key_info", "type": "object"}, {"name": "plot_points", "type": "object"}, {"name": "details", "type": "array"}]',
    60,
    'active',
    true,
    true,
    'on_demand'
) ON CONFLICT (id) DO UPDATE SET
    description = EXCLUDED.description,
    prompt_template = EXCLUDED.prompt_template,
    parameters = EXCLUDED.parameters;

-- 战斗场景写作
INSERT INTO skills (id, name, description, skill_type, category, tags, applicable_agent_types, prompt_template, parameters, priority, status, is_system, is_enabled, load_mode, trigger_keywords, trigger_scenes) VALUES
(
    'skill_combat_scene',
    '战斗场景写作',
    '专门用于战斗场景的写作指导。',
    'prompt',
    'writing',
    '["战斗", "场景", "动作"]',
    '["writer"]',
    '## 战斗场景写作指南

当前场景为战斗场景，请遵循以下原则：

### 动作描写
- 动作要具体、有画面感
- 使用动词增强动态感
- 注意战斗节奏的变化

### 技能描写
- 技能效果要具体生动
- 注意能力的限制和代价
- 保持能力体系一致

### 氛围渲染
- 通过环境描写增强紧张感
- 利用感官细节营造沉浸感
- 适时加入心理描写

### 输出要求
{{scene_requirements}}',
    '[{"name": "scene_requirements", "type": "string", "description": "场景特定要求"}]',
    70,
    'active',
    true,
    true,
    'on_demand',
    '["战斗", "打斗", "对决", "交锋", "厮杀", "比武", "格斗", "对峙", "交手"]',
    '["combat", "battle", "fight"]'
) ON CONFLICT (id) DO UPDATE SET
    description = EXCLUDED.description,
    prompt_template = EXCLUDED.prompt_template,
    trigger_keywords = EXCLUDED.trigger_keywords,
    trigger_scenes = EXCLUDED.trigger_scenes;

-- 恋爱场景写作
INSERT INTO skills (id, name, description, skill_type, category, tags, applicable_agent_types, prompt_template, parameters, priority, status, is_system, is_enabled, load_mode, trigger_keywords, trigger_scenes) VALUES
(
    'skill_romance_scene',
    '恋爱场景写作',
    '专门用于恋爱/情感场景的写作指导。',
    'prompt',
    'writing',
    '["恋爱", "情感", "场景"]',
    '["writer"]',
    '## 恋爱场景写作指南

当前场景为恋爱/情感场景，请遵循以下原则：

### 情感描写
- 情感要细腻真实
- 注意情感的渐进发展
- 用细节传递情感

### 对话设计
- 对话要体现人物性格
- 注意言外之意
- 适当使用肢体语言描写

### 氛围营造
- 环境要与情感呼应
- 利用细节增强代入感

### 分寸把握
- 避免过于露骨的描写
- 留有想象空间

### 输出要求
{{scene_requirements}}',
    '[{"name": "scene_requirements", "type": "string", "description": "场景特定要求"}]',
    70,
    'active',
    true,
    true,
    'on_demand',
    '["恋爱", "爱情", "告白", "暧昧", "情侣", "心动", "甜蜜", "虐恋", "表白", "情愫"]',
    '["romance", "love", "dating"]'
) ON CONFLICT (id) DO UPDATE SET
    description = EXCLUDED.description,
    prompt_template = EXCLUDED.prompt_template,
    trigger_keywords = EXCLUDED.trigger_keywords,
    trigger_scenes = EXCLUDED.trigger_scenes;

-- 对话场景写作
INSERT INTO skills (id, name, description, skill_type, category, tags, applicable_agent_types, prompt_template, parameters, priority, status, is_system, is_enabled, load_mode, trigger_keywords, trigger_scenes) VALUES
(
    'skill_dialogue_scene',
    '对话场景写作',
    '专门用于对话场景的写作指导。',
    'prompt',
    'dialogue',
    '["对话", "场景", "交流"]',
    '["writer"]',
    '## 对话场景写作指南

当前场景以对话为主，请遵循以下原则：

### 对话原则
- 每句对话都要有目的
- 避免无效的寒暄
- 对话要推动情节或展现人物

### 人物语言风格
- 不同人物要有不同说话方式
- 通过用词体现身份性格
- 保持人物语言一致性

### 对话节奏
- 长短句交替
- 适当加入动作和神态描写

### 潜台词
- 话里有话更有意思
- 通过反应展现真实意图

### 输出要求
{{scene_requirements}}',
    '[{"name": "scene_requirements", "type": "string", "description": "场景特定要求"}]',
    70,
    'active',
    true,
    true,
    'on_demand',
    '["对话", "交谈", "商议", "谈判", "争论", "辩论", "沟通", "交流"]',
    '["dialogue", "conversation", "negotiation"]'
) ON CONFLICT (id) DO UPDATE SET
    description = EXCLUDED.description,
    prompt_template = EXCLUDED.prompt_template,
    trigger_keywords = EXCLUDED.trigger_keywords,
    trigger_scenes = EXCLUDED.trigger_scenes;

-- ==================== 注释 ====================
COMMENT ON TABLE prompt_templates IS 'Prompt模板表：存储Agent身份定义（你是谁）';
COMMENT ON TABLE skills IS 'Skill表：存储Agent工作能力（你能做什么）';
