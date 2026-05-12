-- V18: 补全缺失的 Skills（第三批：剧情规划类）
-- 这些是总编剧和章节大纲规划 Agent 的核心能力

-- ==================== 剧情规划类 Skills ====================

-- 剧情规划
INSERT INTO skills (id, name, description, skill_type, category, tags, applicable_agent_types, prompt_template, parameters, output_spec, priority, status, is_system, is_enabled, load_mode)
VALUES (
    'skill_plot_planning',
    '剧情规划',
    '规划故事剧情发展和章节安排的核心技能',
    'prompt',
    'plotting',
    '["剧情", "规划", "大纲"]',
    '["master_plotter"]',
    '## 任务：剧情规划

请根据以下信息规划剧情发展：

### 故事背景
{{story_background}}

### 当前状态
- 当前章节：第 {{current_chapter}} 章
- 已完成情节：{{completed_plots}}
- 活跃伏笔：{{active_hooks}}

### 规划目标
{{planning_goal}}

### 规划要求

1. **整体架构**
   - 确定故事的主线走向
   - 规划主要转折点
   - 设计高潮和结局

2. **章节安排**
   - 每章的核心事件
   - 情绪曲线设计
   - 信息披露节奏

3. **伏笔布局**
   - 新伏笔的埋设计划
   - 旧伏笔的回收时机
   - 伏笔之间的关联

4. **角色发展**
   - 主角的成长路径
   - 配角的故事线
   - 关系变化节点

### 输出格式（JSON）
```json
{
  "story_arc": {
    "current_phase": "当前阶段",
    "next_phase": "下一阶段",
    "main_conflict": "核心冲突"
  },
  "chapters": [
    {"number": 1, "title": "章节名", "core_event": "核心事件", "emotion": "情绪基调", "hooks": ["涉及伏笔"]}
  ],
  "turning_points": [{"chapter": 10, "event": "转折事件", "impact": "影响"}],
  "foreshadowing_plan": {"new": [], "resolve": []}
}
```',
    '[{"name": "story_background", "type": "string", "description": "故事背景"}, {"name": "current_chapter", "type": "number", "description": "当前章节"}, {"name": "completed_plots", "type": "array", "description": "已完成情节"}, {"name": "active_hooks", "type": "array", "description": "活跃伏笔"}, {"name": "planning_goal", "type": "string", "description": "规划目标"}]',
    '[{"name": "story_arc", "type": "object"}, {"name": "chapters", "type": "array"}, {"name": "turning_points", "type": "array"}, {"name": "foreshadowing_plan", "type": "object"}]',
    80,
    'active',
    true,
    true,
    'on_demand'
) ON CONFLICT (id) DO UPDATE SET
    prompt_template = EXCLUDED.prompt_template,
    parameters = EXCLUDED.parameters;

-- 剧情推进评估
INSERT INTO skills (id, name, description, skill_type, category, tags, applicable_agent_types, prompt_template, parameters, priority, status, is_system, is_enabled, load_mode)
VALUES (
    'skill_plot_advancement',
    '剧情推进评估',
    '评估剧情推进效果，判断是否需要调整节奏',
    'prompt',
    'analysis',
    '["剧情", "推进", "评估"]',
    '["master_plotter"]',
    '## 任务：剧情推进评估

请评估当前剧情推进情况：

### 评估内容
{{content_to_evaluate}}

### 评估维度

1. **节奏评估**
   - 剧情推进是否过快/过慢
   - 高潮和缓冲是否合理分布
   - 读者可能感到无聊的地方

2. **逻辑评估**
   - 情节发展是否合理
   - 因果关系是否清晰
   - 是否有逻辑漏洞

3. **吸引力评估**
   - 是否能保持读者兴趣
   - 是否有足够的悬念
   - 是否有意外惊喜

4. **一致性评估**
   - 与大纲是否一致
   - 人物行为是否合理
   - 设定是否冲突

### 输出格式（JSON）
```json
{
  "overall_score": 85,
  "dimensions": {
    "pacing": {"score": 90, "comment": "评价"},
    "logic": {"score": 85, "comment": "评价"},
    "attraction": {"score": 80, "comment": "评价"},
    "consistency": {"score": 85, "comment": "评价"}
  },
  "issues": ["问题1", "问题2"],
  "suggestions": ["建议1", "建议2"],
  "adjustment_needed": true/false
}
```',
    '[{"name": "content_to_evaluate", "type": "string", "description": "评估内容"}]',
    70,
    'active',
    true,
    true,
    'on_demand'
) ON CONFLICT (id) DO UPDATE SET
    prompt_template = EXCLUDED.prompt_template,
    parameters = EXCLUDED.parameters;

-- 章节大纲生成
INSERT INTO skills (id, name, description, skill_type, category, tags, applicable_agent_types, prompt_template, parameters, output_spec, priority, status, is_system, is_enabled, load_mode)
VALUES (
    'skill_chapter_outline_generation',
    '章节大纲生成',
    '根据整体规划生成单个章节的详细大纲',
    'prompt',
    'plotting',
    '["大纲", "章节", "规划"]',
    '["plot_outline"]',
    '## 任务：章节大纲生成

请根据以下信息生成章节大纲：

### 基本信息
- 章节序号：第 {{chapter_number}} 章
- 章节标题：{{chapter_title}}
- 目标字数：{{target_words}} 字

### 故事背景
{{story_context}}

### 本章目标
{{chapter_goal}}

### 大纲要求

1. **结构设计**
   - 开场（引入/承接）
   - 发展（核心内容）
   - 高潮（情绪顶点）
   - 收尾（铺垫/悬念）

2. **段落规划**
   - 每段的主题和目标字数
   - 关键事件和对话
   - 情绪变化曲线

3. **伏笔安排**
   - 需要埋设的伏笔
   - 需要暗示的伏笔
   - 需要回收的伏笔

4. **人物安排**
   - 出场人物
   - 各自的目标和行动
   - 人物互动设计

### 输出格式（JSON）
```json
{
  "summary": "章节概述（50-100字）",
  "segments": [
    {"index": 1, "topic": "主题", "target_words": 500, "key_content": "关键内容", "emotion": "情绪", "characters": ["出场人物"]}
  ],
  "climax": {"segment_index": 3, "description": "高潮描述"},
  "foreshadowing": {"plant": [], "hint": [], "payoff": []},
  "ending_hook": "结尾悬念",
  "notes": "写作注意事项"
}
```',
    '[{"name": "chapter_number", "type": "number", "description": "章节序号", "required": true}, {"name": "chapter_title", "type": "string", "description": "章节标题"}, {"name": "target_words", "type": "number", "description": "目标字数", "default": 3000}, {"name": "story_context", "type": "string", "description": "故事背景"}, {"name": "chapter_goal", "type": "string", "description": "本章目标"}]',
    '[{"name": "summary", "type": "string"}, {"name": "segments", "type": "array"}, {"name": "climax", "type": "object"}, {"name": "foreshadowing", "type": "object"}, {"name": "ending_hook", "type": "string"}, {"name": "notes", "type": "string"}]',
    90,
    'active',
    true,
    true,
    'on_demand'
) ON CONFLICT (id) DO UPDATE SET
    prompt_template = EXCLUDED.prompt_template,
    parameters = EXCLUDED.parameters;

-- 章节大纲验证
INSERT INTO skills (id, name, description, skill_type, category, tags, applicable_agent_types, prompt_template, parameters, priority, status, is_system, is_enabled, load_mode)
VALUES (
    'skill_chapter_outline_validation',
    '章节大纲验证',
    '验证章节大纲的合理性和可执行性',
    'prompt',
    'analysis',
    '["大纲", "验证", "检查"]',
    '["plot_outline"]',
    '## 任务：章节大纲验证

请验证以下章节大纲的合理性：

### 章节大纲
{{chapter_outline}}

### 验证维度

1. **逻辑验证**
   - 情节发展是否合理
   - 因果关系是否清晰
   - 与前文是否衔接

2. **字数验证**
   - 各段字数分配是否合理
   - 总字数是否达标
   - 高潮部分是否有足够篇幅

3. **情绪验证**
   - 情绪曲线是否合理
   - 是否有足够的起伏
   - 结尾情绪是否恰当

4. **可行性验证**
   - 大纲是否可执行
   - 是否过于抽象
   - 是否缺少关键信息

### 输出格式（JSON）
```json
{
  "is_valid": true/false,
  "score": 85,
  "issues": [{"type": "问题类型", "description": "问题描述", "segment_index": 1}],
  "suggestions": ["改进建议"],
  "missing_info": ["缺失信息"]
}
```',
    '[{"name": "chapter_outline", "type": "object", "description": "章节大纲JSON"}]',
    75,
    'active',
    true,
    true,
    'on_demand'
) ON CONFLICT (id) DO UPDATE SET
    prompt_template = EXCLUDED.prompt_template,
    parameters = EXCLUDED.parameters;

-- 开局设计
INSERT INTO skills (id, name, description, skill_type, category, tags, applicable_agent_types, prompt_template, parameters, priority, status, is_system, is_enabled, load_mode)
VALUES (
    'skill_opening_design',
    '开局设计',
    '设计小说开篇，确保前三章能够吸引读者',
    'prompt',
    'plotting',
    '["开篇", "黄金三章", "吸引"]',
    '["plot_outline"]',
    '## 任务：开局设计

请设计小说的开篇布局（黄金三章）：

### 故事设定
{{story_setting}}

### 主角信息
{{protagonist_info}}

### 开局设计原则

1. **第一章：吸引入场**
   - 前100字抓住注意力
   - 展示主角核心特点
   - 制造悬念或冲突
   - 世界观自然呈现

2. **第二章：深化兴趣**
   - 扩展主角困境
   - 引入关键配角
   - 揭示核心设定
   - 推进主线剧情

3. **第三章：确立期待**
   - 明确故事方向
   - 展现核心卖点
   - 建立情感连接
   - 让读者决定追更

### 常见开局类型

1. **冲突开局**：直接进入冲突场景
2. **悬念开局**：制造谜团引发好奇
3. **日常开局**：从平凡切入，形成对比
4. **高光开局**：展示主角高光时刻

### 输出格式（JSON）
```json
{
  "opening_type": "开局类型",
  "chapters": [
    {
      "number": 1,
      "title": "章节标题",
      "opening_line": "开篇第一句",
      "core_event": "核心事件",
      "hooks": ["悬念点"],
      "character_intro": ["人物登场"]
    }
  ],
  "key_points": ["关键卖点"],
  "world_reveal_plan": "世界观呈现方式"
}
```',
    '[{"name": "story_setting", "type": "string", "description": "故事设定"}, {"name": "protagonist_info", "type": "object", "description": "主角信息"}]',
    85,
    'active',
    true,
    true,
    'on_demand'
) ON CONFLICT (id) DO UPDATE SET
    prompt_template = EXCLUDED.prompt_template,
    parameters = EXCLUDED.parameters;

-- 反派管理
INSERT INTO skills (id, name, description, skill_type, category, tags, applicable_agent_types, prompt_template, parameters, priority, status, is_system, is_enabled, load_mode)
VALUES (
    'skill_villain_management',
    '反派管理',
    '管理反派角色的出场、发展和结局规划',
    'prompt',
    'plotting',
    '["反派", "角色", "规划"]',
    '["plot_outline"]',
    '## 任务：反派管理

请管理以下反派角色：

### 反派信息
{{villain_info}}

### 当前故事阶段
{{story_phase}}

### 反派管理原则

1. **反派设计**
   - 有合理的动机和行为逻辑
   - 不是纯粹的恶，有立体感
   - 能力要与主角形成张力
   - 要推动剧情发展

2. **出场规划**
   - 出场时机和方式
   - 与主角的冲突节点
   - 威胁等级变化曲线

3. **发展轨迹**
   - 反派的目标和行动
   - 与主角的博弈过程
   - 可能的转变机会

4. **结局规划**
   - 合理的结局安排
   - 对故事的影响
   - 读者的情感满足

### 反派类型

1. **宿敌型**：与主角长期对立
2. **阶段型**：某个阶段的对手
3. **隐藏型**：幕后黑手
4. **转化型**：可能转向正方

### 输出格式（JSON）
```json
{
  "villain_profile": {"name": "名称", "type": "类型", "threat_level": "威胁等级"},
  "appearance_plan": [{"chapter": 10, "event": "出场事件", "impact": "影响"}],
  "conflict_timeline": [{"phase": "阶段", "villain_action": "行动", "protagonist_response": "应对"}],
  "development_arc": "发展轨迹",
  "ending_plan": "结局规划"
}
```',
    '[{"name": "villain_info", "type": "object", "description": "反派信息"}, {"name": "story_phase", "type": "string", "description": "当前故事阶段"}]',
    85,
    'active',
    true,
    true,
    'on_demand'
) ON CONFLICT (id) DO UPDATE SET
    prompt_template = EXCLUDED.prompt_template,
    parameters = EXCLUDED.parameters;

-- 卷规划
INSERT INTO skills (id, name, description, skill_type, category, tags, applicable_agent_types, prompt_template, parameters, priority, status, is_system, is_enabled, load_mode)
VALUES (
    'skill_volume_planning',
    '卷规划',
    '规划故事分卷结构和各卷内容',
    'prompt',
    'plotting',
    '["分卷", "结构", "规划"]',
    '["plot_outline"]',
    '## 任务：卷规划

请规划故事的分卷结构：

### 故事概要
{{story_summary}}

### 预计总字数
{{total_words}}

### 卷规划原则

1. **分卷逻辑**
   - 每卷有独立的主题或阶段
   - 卷与卷之间有承接关系
   - 每卷有起承转合

2. **内容分配**
   - 主线发展节奏
   - 支线穿插安排
   - 高潮点分布

3. **篇幅控制**
   - 各卷字数分配
   - 章节数量规划
   - 节奏密度设计

### 分卷类型

1. **地点型**：按故事发生地点分卷
2. **时间型**：按时间阶段分卷
3. **事件型**：按核心事件分卷
4. **成长型**：按主角成长阶段分卷

### 输出格式（JSON）
```json
{
  "total_volumes": 3,
  "volumes": [
    {
      "number": 1,
      "title": "卷名",
      "theme": "主题",
      "chapters": "第1-30章",
      "target_words": 100000,
      "summary": "本卷概要",
      "climax": "高潮事件",
      "ending_state": "卷末状态"
    }
  ],
  "main_arc": "主线发展轨迹",
  "milestones": [{"volume": 1, "event": "里程碑事件"}]
}
```',
    '[{"name": "story_summary", "type": "string", "description": "故事概要"}, {"name": "total_words", "type": "number", "description": "预计总字数"}]',
    80,
    'active',
    true,
    true,
    'on_demand'
) ON CONFLICT (id) DO UPDATE SET
    prompt_template = EXCLUDED.prompt_template,
    parameters = EXCLUDED.parameters;
