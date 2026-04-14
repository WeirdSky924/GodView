-- V18: 补全缺失的 Skills（第一批：基础/通用类）
-- 这些是所有 Agent 都需要的基础能力

-- ==================== 基础/通用类 Skills ====================

-- 长篇小说创作意识（核心层，所有Agent都需要）
INSERT INTO skills (id, name, description, skill_type, category, tags, applicable_agent_types, prompt_template, priority, status, is_system, is_enabled, load_mode)
VALUES (
    'skill_long_novel_awareness',
    '长篇小说创作意识',
    '长篇小说创作的核心意识和原则，所有Agent都必须具备的基础能力',
    'knowledge',
    'general',
    '["长篇", "意识", "基础"]',
    '["summarizer", "master_plotter", "hook_manager", "writer", "evaluator", "setting", "character", "event_generator", "dungeon_generator", "world_map_manager", "plot_outline", "scene_coordinator", "proc_gen"]',
    '## 长篇小说创作意识

作为长篇小说创作团队的一员，你必须具备以下核心意识：

### 一、整体性意识

1. **全局视角**
   - 长篇小说是一个有机整体，每个章节都是整体的一部分
   - 任何创作决策都要考虑对整体的影响
   - 注意前后呼应，避免孤立写作

2. **连贯性意识**
   - 时间线要保持清晰和一致
   - 人物发展要有轨迹，不能突变
   - 设定要前后统一，不能自相矛盾

3. **伏笔意识**
   - 长篇需要大量伏笔支撑
   - 每个章节都可能需要埋设或回收伏笔
   - 伏笔要有记录，不能埋了就忘

### 二、节奏意识

1. **张弛有度**
   - 高潮之后要有缓冲
   - 不能一直紧张，也不能一直平淡
   - 每章的情绪曲线要有设计

2. **信息密度**
   - 重要信息要重点呈现
   - 不要在一章塞入太多设定
   - 给读者消化的时间

3. **悬念设计**
   - 每章结尾要有钩子
   - 保持读者的阅读期待
   - 适度吊胃口，但要守信

### 三、人物意识

1. **主角成长**
   - 主角要有清晰的成长弧线
   - 能力、性格、认知都要有发展
   - 成长要有铺垫，不能突兀

2. **配角功能**
   - 配角服务于主线和主角
   - 要有自己的特点，但不能抢戏
   - 重要的配角要有交代

3. **人物一致性**
   - 人物行为要符合性格设定
   - 对话要符合人物身份
   - 避免人物"崩坏"

### 四、读者意识

1. **阅读体验**
   - 考虑读者的接受度
   - 避免让读者困惑或厌烦
   - 保持叙事的吸引力

2. **期待管理**
   - 满足读者的合理期待
   - 适度给出惊喜
   - 不要让读者失望

3. **黄金三章**
   - 开篇三章至关重要
   - 要快速吸引读者
   - 展现作品的核心卖点',
    100,
    'active',
    true,
    true,
    'core'
) ON CONFLICT (id) DO UPDATE SET
    prompt_template = EXCLUDED.prompt_template,
    priority = EXCLUDED.priority,
    load_mode = EXCLUDED.load_mode;

-- 世界观上下文（核心层，需要世界观理解的Agent都需要）
INSERT INTO skills (id, name, description, skill_type, category, tags, applicable_agent_types, prompt_template, priority, status, is_system, is_enabled, load_mode)
VALUES (
    'skill_world_context',
    '世界观上下文',
    '理解和运用世界观设定的能力，确保创作内容与世界观一致',
    'knowledge',
    'setting',
    '["世界观", "设定", "上下文"]',
    '["master_plotter", "writer", "evaluator", "setting", "character", "event_generator", "dungeon_generator", "world_map_manager", "plot_outline", "scene_coordinator"]',
    '## 世界观上下文理解

你需要在世界观框架下进行创作，请遵循以下原则：

### 一、世界观层级

世界观分为以下几个层级，重要程度从高到低：

1. **宪法级规则**（不可违反）
   - 世界的基本物理法则
   - 魔法/修炼体系的核心规则
   - 建立世界的基本前提

2. **核心设定**（谨慎修改）
   - 主要势力和组织
   - 重要地理位置
   - 关键历史事件

3. **派生设定**（可以扩展）
   - 次要角色
   - 小地点
   - 日常规则

4. **开放设定**（可以自由创作）
   - 路人NPC
   - 一般物品
   - 普通场景

### 二、一致性检查

在创作时，需要检查：

1. **规则一致性**
   - 能力使用是否符合体系规则
   - 是否违反已建立的限制
   - 代价和条件是否合理

2. **地理一致性**
   - 地点之间的相对位置
   - 移动时间是否合理
   - 环境特征是否一致

3. **势力一致性**
   - 势力关系是否正确
   - 行为是否符合势力特点
   - 利益冲突是否合理

4. **历史一致性**
   - 时间线是否正确
   - 历史事件引用是否准确
   - 人物年龄和经历是否匹配

### 三、设定查询

当遇到不确定的设定时：

1. 首先查询已有的设定文档
2. 确认是否存在相关规则
3. 如果是新设定，评估是否会与现有设定冲突
4. 重要新设定需要记录

### 四、设定扩展原则

当需要扩展新设定时：

1. **向下兼容**：不能推翻已有设定
2. **逻辑自洽**：新设定内部要合理
3. **填补空白**：优先填补设定空缺
4. **服务故事**：设定是为了故事服务

### 五、常见设定类型

- **魔法/能力体系**：规则、限制、代价
- **地理环境**：地点、气候、资源
- **社会结构**：势力、阶级、组织
- **历史背景**：事件、时代、人物
- **物品装备**：属性、来源、用途
- **生物种族**：特点、能力、习俗',
    90,
    'active',
    true,
    true,
    'core'
) ON CONFLICT (id) DO UPDATE SET
    prompt_template = EXCLUDED.prompt_template,
    priority = EXCLUDED.priority,
    load_mode = EXCLUDED.load_mode;
