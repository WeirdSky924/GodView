-- V23: 增强大纲Agent的技能体系
-- 根据评估建议添加网文爽点设计、章节钩子设计、反派戏份规划等技能

-- ==================== 新增 Skills ====================

-- 1. 网文爽点设计技能
INSERT INTO skills (id, name, description, skill_type, category, tags, applicable_agent_types, prompt_template, priority, status, is_system, is_enabled, load_mode)
VALUES (
    'skill_webnovel_cool_points',
    '网文爽点设计',
    '为章节设计爽点分布，包括打脸、逆袭、装逼、收获等网文经典爽点',
    'prompt',
    'plotting',
    '["爽点", "网文", "打脸", "逆袭"]',
    '["plot_outline", "writer", "master_plotter"]',
    '# 网文爽点设计技能

## 一、爽点类型分类

### 1. 打脸型爽点
主角被质疑、轻视后，用实际行动狠狠打脸。
- 先抑后扬：先让主角被看不起
- 反差要大：质疑越狠，打脸越爽
- 围观反应：旁观者的震惊增强效果

### 2. 逆袭型爽点
主角从劣势翻盘，反败为胜。
- 劣势要明显：让读者担心
- 转机要合理：不能无脑翻盘
- 收获要丰富：翻盘后要有回报

### 3. 装逼型爽点
主角展示实力、地位、财富，让人震撼。
- 人设要稳：装逼要符合人设
- 方式要独特：有辨识度
- 收尾要潇洒：装完就跑最潇洒

### 4. 收获型爽点
主角获得重要物品、能力、认可。
- 期待要足：读者期待已久
- 价值要高：物有所值
- 未来要有用：埋下伏笔

### 5. 复仇型爽点
主角对敌人进行报复。
- 积怨要深：读者期待复仇
- 手段要解气：让读者喊爽

### 6. 助人型爽点
主角帮助他人，获得感激和回报。

## 二、章节爽点布局

每章至少一个爽点：

- 单爽点章节：开篇(20%) → 铺垫(30%) → 爽点爆发(30%) → 收尾(20%)
- 双爽点章节：开篇(15%) → 小爽点(25%) → 过渡(20%) → 大爽点(30%) → 收尾(10%)

## 三、爽点禁区

1. 爽点来得太突然 - 缺乏铺垫
2. 爽点力度不足 - 铺垫很久但爆发不够
3. 爽点后没有收获 - 爽完就完
4. 爽点重复 - 同样套路反复使用
5. 主角太完美 - 没有波折直接碾压',
    88,
    'active',
    true,
    true,
    'on_demand'
)
ON CONFLICT (id) DO UPDATE SET
    name = EXCLUDED.name,
    description = EXCLUDED.description,
    prompt_template = EXCLUDED.prompt_template,
    priority = EXCLUDED.priority,
    applicable_agent_types = EXCLUDED.applicable_agent_types;

-- 2. 章节钩子设计技能
INSERT INTO skills (id, name, description, skill_type, category, tags, applicable_agent_types, prompt_template, priority, status, is_system, is_enabled, load_mode)
VALUES (
    'skill_chapter_hooks_design',
    '章节钩子设计',
    '设计章节开头和结尾的钩子，提升读者追读欲望',
    'prompt',
    'plotting',
    '["钩子", "悬念", "追读", "开头", "结尾"]',
    '["plot_outline", "writer", "hook_manager"]',
    '# 章节钩子设计技能

## 一、开篇钩子类型

### 1. 冲突开篇
直接进入冲突场景，制造紧张感。
示例：剑尖距离咽喉只有三寸。

### 2. 悬念开篇
抛出悬念，引发读者好奇。
示例：三天后，整个宗门都将为这个决定而战栗。

### 3. 反差开篇
与上一章结尾形成反差，制造期待。

### 4. 时间跳跃开篇
跳过无聊的过渡，直接进入关键时间点。

### 5. 视角切换开篇
从其他视角切入，提供新信息。

## 二、结尾钩子类型

### 1. 悬念式结尾（强度⭐⭐⭐⭐⭐）
抛出问题，让读者想知道答案。
示例：就在这时，天空裂开了一道缝隙。

### 2. 危机式结尾（强度⭐⭐⭐⭐⭐）
在关键时刻戛然而止。
示例：他还没来得及反应，黑暗已经将他吞没。

### 3. 转折式结尾（强度⭐⭐⭐⭐）
揭示意料之外的信息。
示例："你猜对了，"那人缓缓摘下面具，"我就是他。"

### 4. 期待式结尾（强度⭐⭐⭐）
预告接下来的精彩内容。

### 5. 承诺式结尾（强度⭐⭐⭐⭐）
明确主角接下来的目标。

### 6. 反转式结尾（强度⭐⭐⭐⭐⭐）
推翻读者预期，制造震撼。

## 三、黄金三章法则

- 第一章结尾：必须有强钩子
- 第二章结尾：必须有强钩子
- 第三章结尾：让读者确信值得追

## 四、钩子禁区

1. 钩子太多太密 - 悬念堆积，读者麻木
2. 钩子不兑现 - 悬念烂尾，失去信任
3. 钩子太弱 - 读者无感
4. 钩子与内容不符 - 标题党
5. 同一类型钩子重复 - 审美疲劳',
    87,
    'active',
    true,
    true,
    'on_demand'
)
ON CONFLICT (id) DO UPDATE SET
    name = EXCLUDED.name,
    description = EXCLUDED.description,
    prompt_template = EXCLUDED.prompt_template,
    priority = EXCLUDED.priority,
    applicable_agent_types = EXCLUDED.applicable_agent_types;

-- 3. 章节反派戏份规划技能
INSERT INTO skills (id, name, description, skill_type, category, tags, applicable_agent_types, prompt_template, priority, status, is_system, is_enabled, load_mode)
VALUES (
    'skill_chapter_villain_arc',
    '章节反派戏份规划',
    '规划反派在章节中的出场、行动、威胁度变化和隐藏信息',
    'prompt',
    'plotting',
    '["反派", "戏份", "威胁度", "隐藏信息"]',
    '["plot_outline", "master_plotter"]',
    '# 章节反派戏份规划技能

## 核心理念

反派是推动故事冲突的核心力量。每章都要考虑反派的动态，即使反派不出场，也应该有幕后影响。

## 一、反派出场决策

| 条件 | 建议 |
|------|------|
| 主角与反派正面对抗 | 必须出场 |
| 剧情涉及反派利益 | 建议出场或暗示 |
| 反派计划推进 | 暗示或视角切换 |
| 与反派无直接关联 | 幕后影响 |

## 二、反派行动设计

| 类型 | 描述 | 效果 |
|------|------|------|
| 主动出击 | 反派采取行动攻击/阻碍主角 | 提升紧张感 |
| 布局推进 | 反派推进阴谋计划 | 制造危机预期 |
| 调整策略 | 反派根据局势调整 | 展示反派智慧 |
| 试探行动 | 反派试探主角实力 | 为后续铺垫 |

## 三、威胁度曲线管理

| 等级 | 描述 | 主角状态 |
|------|------|----------|
| 致命 | 反派能轻易杀死主角 | 必须逃避或求助 |
| 高 | 反派明显强于主角 | 需要计谋或外援 |
| 中 | 反派与主角相当 | 正面交锋有风险 |
| 低 | 反派弱于主角 | 主角可以应对 |
| 潜在 | 威胁尚未显现 | 读者知道但主角不知 |

## 四、隐藏信息设计

1. 反派真实身份
2. 反派真实目的
3. 反派隐藏实力
4. 反派与主角的关系
5. 反派的弱点
6. 反派的计划

## 五、每章反派检查清单

[ ] 本章反派是否有动态（出场或幕后）？
[ ] 反派行动是否推进了剧情？
[ ] 威胁度变化是否合理？
[ ] 是否有隐藏信息的暗示或揭示？
[ ] 反派行为是否符合其性格和目的？',
    86,
    'active',
    true,
    true,
    'on_demand'
)
ON CONFLICT (id) DO UPDATE SET
    name = EXCLUDED.name,
    description = EXCLUDED.description,
    prompt_template = EXCLUDED.prompt_template,
    priority = EXCLUDED.priority,
    applicable_agent_types = EXCLUDED.applicable_agent_types;

-- ==================== 更新章节大纲生成技能 ====================

UPDATE skills
SET
    prompt_template = '# 章节大纲生成技能

## 任务：章节大纲生成

请根据以下信息生成章节大纲：

### 基本信息
- 章节序号：第 {{chapter_number}} 章
- 目标字数：{{target_words}} 字

### 故事上下文（完整输入）
{{story_context}}

包含：项目元数据、角色信息、世界设定、伏笔状态、前文大纲

## 一、大纲设计要求

### 1. 结构设计
- 开场（引入/承接）：设计开篇钩子
- 发展（核心内容）：推进剧情，展示角色
- 高潮（情绪顶点）：爽点或冲突爆发
- 收尾（铺垫/悬念）：结尾钩子

### 2. 爽点设计（网文必备）
每章至少规划一个爽点：
- 打脸：被质疑后反击
- 逆袭：劣势翻盘
- 装逼：展示实力
- 收获：获得成就

### 3. 钩子设计（网文必备）
- 开篇钩子：吸引继续阅读
- 结尾钩子：维持追读欲望

### 4. 反派戏份
- 反派当前状态
- 反派行动目的
- 威胁度变化
- 隐藏信息（读者暂时不知道的）

## 二、输出格式（JSON）

```json
{
  "title": "章节标题",
  "summary": "章节概述",
  "scenes": [...],
  "emotion_curve": {...},
  "cool_points": [...],
  "hooks": {"opening": {...}, "ending": {...}},
  "villain_arc": {...},
  "foreshadowing": {"plant": [], "hint": [], "payoff": []},
  "chapter_goals": [...],
  "quality_check": {...}
}
```

## 三、自检清单

[ ] 开篇有钩子？
[ ] 结尾有钩子？
[ ] 至少有一个爽点？
[ ] 出场角色与设定一致？
[ ] 反派戏份合理（如有）？
[ ] 情绪曲线有起伏？',
    updated_at = NOW()
WHERE id = 'skill_chapter_outline_generation';

-- ==================== 为 plot_outline Agent 分配新技能 ====================

-- 分配网文爽点设计技能
INSERT INTO skill_assignments (id, skill_id, agent_type, slot_name, priority, is_enabled, is_required, load_mode)
SELECT
    'assign_outline_cool_points',
    'skill_webnovel_cool_points',
    'plot_outline',
    'cool_points',
    88,
    true,
    true,  -- 网文必备
    'on_demand'
WHERE NOT EXISTS (
    SELECT 1 FROM skill_assignments
    WHERE skill_id = 'skill_webnovel_cool_points' AND agent_type = 'plot_outline'
);

-- 分配章节钩子设计技能
INSERT INTO skill_assignments (id, skill_id, agent_type, slot_name, priority, is_enabled, is_required, load_mode)
SELECT
    'assign_outline_hooks',
    'skill_chapter_hooks_design',
    'plot_outline',
    'hooks_design',
    87,
    true,
    true,  -- 网文必备
    'on_demand'
WHERE NOT EXISTS (
    SELECT 1 FROM skill_assignments
    WHERE skill_id = 'skill_chapter_hooks_design' AND agent_type = 'plot_outline'
);

-- 分配章节反派戏份规划技能
INSERT INTO skill_assignments (id, skill_id, agent_type, slot_name, priority, is_enabled, is_required, load_mode)
SELECT
    'assign_outline_villain_arc',
    'skill_chapter_villain_arc',
    'plot_outline',
    'villain_arc',
    86,
    true,
    false,
    'on_demand'
WHERE NOT EXISTS (
    SELECT 1 FROM skill_assignments
    WHERE skill_id = 'skill_chapter_villain_arc' AND agent_type = 'plot_outline'
);

-- 分配大纲上下文组装技能（核心）
INSERT INTO skill_assignments (id, skill_id, agent_type, slot_name, priority, is_enabled, is_required, load_mode)
SELECT
    'assign_outline_context',
    'skill_outline_context',
    'plot_outline',
    'outline_context',
    95,
    true,
    true,
    'core'
WHERE NOT EXISTS (
    SELECT 1 FROM skill_assignments
    WHERE skill_id = 'skill_outline_context' AND agent_type = 'plot_outline'
);

-- ==================== 更新 Prompt 模板 ====================

-- 更新角色定义
UPDATE prompt_templates
SET
    content = '你是章节大纲规划专家（Plot Outline Agent）。

你的职责是为每一章生成详细的剧情大纲，确保章节内容结构清晰、节奏合理、爽点充足。

## 核心能力

1. **剧情结构设计**
   - 分析前一章结尾的故事状态
   - 规划本章的核心情节点
   - 设计场景转换和节奏安排

2. **角色戏份安排**
   - 主角的行动和成长
   - 配角的出场时机
   - 反派的动态（出场或幕后影响）

3. **爽点与钩子设计**
   - 设计本章的爽点（打脸/逆袭/装逼/收获等）
   - 开篇钩子（吸引继续阅读）
   - 结尾钩子（维持追读欲望）

4. **伏笔管理**
   - 埋设新的伏笔
   - 暗示已有伏笔
   - 回收待处理伏笔

## 工作原则

- **上下文一致性**：所有内容必须与已有设定一致
- **读者体验优先**：每章至少一个爽点，开头结尾有钩子
- **反派动态管理**：即使反派不出场，也要考虑其幕后影响',
    updated_at = NOW()
WHERE id = 'role_plot_outline';

-- 更新功能规范
UPDATE prompt_templates
SET
    content = '作为章节大纲规划专家，你的具体职责包括：

## 一、输入信息获取

必须获取以下上下文信息：
- 项目元数据（类型、基调、进度）
- 角色信息（主角、配角、反派状态）
- 世界设定（力量体系、地点、势力）
- 伏笔状态（待埋设、待回收）
- 前文大纲（最近章节摘要）

## 二、大纲生成职责

1. 场景规划（2-5个场景）
2. 角色安排（含反派戏份）
3. 爽点设计（每章至少一个）
4. 钩子设计（开篇和结尾）
5. 情绪曲线设计
6. 伏笔管理

## 三、反派戏份规划

即使反派不出场，也要考虑：
- 反派的幕后行动
- 威胁度的变化
- 隐藏信息的暗示

## 四、质量检查

[ ] 开篇有钩子？
[ ] 结尾有钩子？
[ ] 至少有一个爽点？
[ ] 反派戏份合理？
[ ] 情绪曲线有起伏？',
    updated_at = NOW()
WHERE id = 'function_plot_outline';
