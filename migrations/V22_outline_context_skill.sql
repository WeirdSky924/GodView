-- V22: 添加大纲上下文组装 Skill
-- 为 Plot Outline Agent 提供获取项目完整上下文的能力

-- ==================== 大纲上下文组装 Skill ====================

-- 大纲上下文组装（核心层，大纲Agent必备）
INSERT INTO skills (id, name, description, skill_type, category, tags, applicable_agent_types, prompt_template, priority, status, is_system, is_enabled, load_mode)
VALUES (
    'skill_outline_context',
    '大纲上下文组装',
    '为大纲生成组装项目完整上下文，包括角色、设定、伏笔、前文大纲等',
    'knowledge',
    'plotting',
    '["大纲", "上下文", "设定", "角色", "伏笔"]',
    '["plot_outline", "master_plotter", "event_generator"]',
    '# 大纲上下文组装指南

在生成章节大纲前，必须先收集和整理项目的完整上下文信息。这确保大纲与现有设定保持一致，并能够充分利用已有的剧情资源。

## 一、必须获取的上下文信息

### 1. 角色信息

获取项目中所有角色的核心信息：

- **主角**：性格、目标、当前状态、成长进度
- **重要配角**：与主角的关系、最近动态
- **反派/对手**：当前威胁程度、近期行动
- **角色互动关系**：当前的紧张关系、联盟状态

**用途**：
- 确定本章出场角色
- 规划角色互动和冲突
- 推进角色成长线

### 2. 世界设定 (Lore)

获取与当前章节相关的设定信息：

- **力量体系**：当前阶段的等级、能力限制
- **地理位置**：场景可能发生的地点
- **势力格局**：相关势力的动态
- **关键规则**：不可违反的世界规则

**用途**：
- 确保场景设定符合世界观
- 避免设定冲突
- 合理安排能力展示

### 3. 伏笔状态

获取当前伏笔的管理状态：

- **待埋设伏笔**：计划中但未埋设的伏笔
- **已埋设伏笔**：等待合适的回收时机
- **待回收伏笔**：已经暗示或即将回收的伏笔
- **过期伏笔**：太久未处理需要关注的伏笔

**用途**：
- 规划本章要埋设的伏笔
- 选择本章要回收的伏笔
- 避免伏笔堆积或遗忘

### 4. 前文大纲

获取之前章节的大纲信息：

- **上一章大纲**：承接内容和结尾悬念
- **近期章节摘要**：剧情发展脉络
- **未完成的剧情线**：需要继续推进的内容

**用途**：
- 确保章节衔接自然
- 避免重复或遗漏
- 保持剧情连贯性

### 5. 项目元数据

获取项目的整体信息：

- **作品类型**：玄幻、都市、科幻等
- **叙事基调**：严肃、轻松、暗黑等
- **目标读者**：男频、女频、年龄段
- **当前进度**：已写字数、当前卷数

**用途**：
- 把握章节风格
- 调整节奏和密度
- 符合作品整体定位

## 二、上下文组装流程

### 步骤 1：确定章节位置

- 这是第几章？
- 处于哪一卷？
- 是开篇、中段还是结尾？

### 步骤 2：获取基础信息

```
项目ID → 获取角色列表 → 获取世界设定 → 获取伏笔状态
```

### 步骤 3：筛选相关信息

不是所有信息都需要，要根据章节位置筛选：

- 开篇章节：侧重世界观介绍、角色出场
- 中段章节：侧重剧情推进、角色成长
- 高潮章节：侧重冲突升级、伏笔回收
- 结尾章节：侧重剧情收束、伏笔清理

## 三、上下文使用原则

### 1. 一致性原则

- 所有内容必须与已建立设定一致
- 不引入与世界观冲突的新元素
- 角色行为符合已塑造的性格

### 2. 延续性原则

- 承接上一章的结尾和悬念
- 继续推进未完成的剧情线
- 保持角色发展轨迹

### 3. 平衡性原则

- 新信息与已有信息平衡
- 剧情推进与角色展示平衡
- 新伏笔与伏笔回收平衡

### 4. 服务性原则

- 上下文服务于章节目标
- 不堆砌无关信息
- 聚焦于推动剧情的核心元素',
    95,
    'active',
    true,
    true,
    'core'
)
ON CONFLICT (id) DO UPDATE SET
    name = EXCLUDED.name,
    description = EXCLUDED.description,
    prompt_template = EXCLUDED.prompt_template,
    priority = EXCLUDED.priority,
    applicable_agent_types = EXCLUDED.applicable_agent_types;

-- ==================== 为 plot_outline Agent 分配 Skills ====================

-- 确保 plot_outline Agent 拥有核心 skills
INSERT INTO skill_assignments (id, skill_id, agent_type, slot_name, priority, is_enabled, is_required, load_mode)
SELECT
    'assign_outline_' || skill_id,
    skill_id,
    'plot_outline',
    'core_skills',
    priority,
    true,
    true,
    'core'
FROM skills
WHERE id IN ('skill_long_novel_awareness', 'skill_world_context', 'skill_outline_context')
AND NOT EXISTS (
    SELECT 1 FROM skill_assignments
    WHERE skill_id = skills.id AND agent_type = 'plot_outline'
);

-- ==================== 更新章节大纲生成 Skill ====================

-- 更新章节大纲生成 Skill 以使用上下文
UPDATE skills
SET
    prompt_template = '# 章节大纲生成技能

## 任务：章节大纲生成

请根据以下信息生成章节大纲：

### 基本信息

- 章节序号：第 {{chapter_number}} 章
- 章节标题：{{chapter_title}}
- 目标字数：{{target_words}} 字

### 故事上下文

{{story_context}}

### 本章目标

{{chapter_goal}}

### 大纲要求

#### 1. 结构设计

- 开场（引入/承接）
- 发展（核心内容）
- 高潮（情绪顶点）
- 收尾（铺垫/悬念）

#### 2. 段落规划

- 每段的主题和目标字数
- 关键事件和对话
- 情绪变化曲线

#### 3. 伏笔安排

- 需要埋设的伏笔
- 需要暗示的伏笔
- 需要回收的伏笔

#### 4. 人物安排

- 出场人物（从已有角色中选择）
- 各自的目标和行动
- 人物互动设计

### 输出格式（JSON）

```json
{
  "title": "章节标题",
  "summary": "章节概述（50-100字）",
  "scenes": [
    {
      "scene_number": 1,
      "title": "场景标题",
      "scene_type": "dialogue/action/description/climax",
      "summary": "场景摘要",
      "participating_characters": ["出场人物"],
      "location": "地点",
      "emotion_start": "neutral",
      "emotion_end": "tension",
      "conflict_level": "low/medium/high/critical",
      "estimated_words": 800,
      "key_events": ["事件1", "事件2"]
    }
  ],
  "climax": {"segment_index": 3, "description": "高潮描述"},
  "foreshadowing": {"plant": [], "hint": [], "payoff": []},
  "ending_hook": "结尾悬念",
  "chapter_goals": ["目标1", "目标2"],
  "emotion_curve": {
    "points": [
      {"position": 0.0, "emotion": "neutral", "intensity": 0.3},
      {"position": 0.5, "emotion": "tension", "intensity": 0.8},
      {"position": 1.0, "emotion": "relief", "intensity": 0.5}
    ],
    "dominant_emotion": "tension"
  },
  "notes": "写作注意事项"
}
```

### 注意事项

1. 出场角色必须从已有角色中选择，保持性格一致
2. 场景设定必须符合世界观规则
3. 合理安排伏笔的埋设和回收
4. 确保与上一章的衔接自然',
    updated_at = NOW()
WHERE id = 'skill_chapter_outline_generation';
