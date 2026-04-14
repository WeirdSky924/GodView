-- V24: 角色立场约束系统
-- 添加角色立场约束skill，并更新相关Agent配置

-- ==================== 新增 Skill ====================

-- 角色立场约束skill
INSERT INTO skills (id, name, description, skill_type, category, tags, applicable_agent_types, prompt_template, priority, status, is_system, is_enabled, load_mode)
VALUES (
    'skill_character_stance_constraint',
    '角色立场约束',
    '确保所有角色的行为符合其立场定位，反派不得以帮助主角为核心目的',
    'knowledge',
    'core',
    '["角色", "立场", "反派", "约束"]',
    '["plot_outline", "writer", "master_plotter", "character", "scene_coordinator"]',
    '# 角色立场约束规范

## 核心原则

每个角色都有明确的立场定位，所有行为必须符合该定位。**反派的任何行为不能以"帮助主角实现其核心目标"为出发点。**

## 一、角色立场分类

### 1. 主角阵营
- 主角 (protagonist): 追求自身目标，可能接受他人帮助
- 盟友 (ally): 主动帮助主角，与主角目标一致

### 2. 反派阵营
- 宿敌 (archenemy): 与主角核心目标直接对立
- 主要反派 (major_antagonist): 阶段性对抗
- 爪牙 (minion): 执行反派命令

### 3. 中立/变数
- 竞争对手 (rival): 与主角竞争，但非敌人
- 变数 (wild_card): 立场不明，可能随时变化

## 二、反派行为禁区

### 绝对禁止的行为

反派**不能**做以下事情（除非有合理动机）：

1. **主动帮助主角实现核心目标**
   - 告诉主角关键情报
   - 给主角关键道具
   - 教主角关键技能
   - 解救主角于危难

2. **无代价的善意行为**
   - 无理由放过主角
   - 无条件的合作
   - 牺牲自己帮助主角

### 允许的行为（需合理动机）

反派可以做出看似帮助主角的行为，但必须有**自私动机**：

- 告诉情报 → 情报有假/有陷阱
- 给道具 → 道具有追踪/诅咒
- 合作 → 有共同敌人，利用后消灭主角
- 放过 → 有更大阴谋

## 三、反派行为三问

在编写反派任何行为前，必须回答：

1. 这个行为服务于反派的什么目标？
2. 这个行为如何损害或阻碍主角？
3. 如果看起来在帮助主角，真正的目的是什么？

## 四、角色上下文组装要求

在任何生成内容前，必须明确标注每个出场角色的信息：

```json
{
  "character_context": [
    {
      "name": "角色名",
      "role_type": "protagonist/antagonist/ally/neutral/rival",
      "stance": "敌对/友好/中立",
      "core_goal": "角色的核心目标"
    }
  ]
}
```',
    92,
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

-- ==================== 为相关 Agent 分配技能 ====================

-- 为 Writer Agent 分配角色立场约束
INSERT INTO skill_assignments (id, skill_id, agent_type, slot_name, priority, is_enabled, is_required, load_mode)
SELECT
    'assign_writer_stance',
    'skill_character_stance_constraint',
    'writer',
    'character_stance',
    92,
    true,
    true,  -- 强制要求
    'core'
WHERE NOT EXISTS (
    SELECT 1 FROM skill_assignments
    WHERE skill_id = 'skill_character_stance_constraint' AND agent_type = 'writer'
);

-- 为 Plot Outline Agent 分配角色立场约束
INSERT INTO skill_assignments (id, skill_id, agent_type, slot_name, priority, is_enabled, is_required, load_mode)
SELECT
    'assign_outline_stance',
    'skill_character_stance_constraint',
    'plot_outline',
    'character_stance',
    92,
    true,
    true,  -- 强制要求
    'core'
WHERE NOT EXISTS (
    SELECT 1 FROM skill_assignments
    WHERE skill_id = 'skill_character_stance_constraint' AND agent_type = 'plot_outline'
);

-- 为 Master Plotter Agent 分配角色立场约束
INSERT INTO skill_assignments (id, skill_id, agent_type, slot_name, priority, is_enabled, is_required, load_mode)
SELECT
    'assign_plotter_stance',
    'skill_character_stance_constraint',
    'master_plotter',
    'character_stance',
    92,
    true,
    false,  -- 推荐但非强制
    'core'
WHERE NOT EXISTS (
    SELECT 1 FROM skill_assignments
    WHERE skill_id = 'skill_character_stance_constraint' AND agent_type = 'master_plotter'
);

-- 为 Scene Coordinator Agent 分配角色立场约束
INSERT INTO skill_assignments (id, skill_id, agent_type, slot_name, priority, is_enabled, is_required, load_mode)
SELECT
    'assign_scene_stance',
    'skill_character_stance_constraint',
    'scene_coordinator',
    'character_stance',
    92,
    true,
    false,  -- 推荐但非强制
    'core'
WHERE NOT EXISTS (
    SELECT 1 FROM skill_assignments
    WHERE skill_id = 'skill_character_stance_constraint' AND agent_type = 'scene_coordinator'
);

-- ==================== 更新 Prompt 模板 ====================

-- 更新 Writer 角色定义，添加反派立场约束
UPDATE prompt_templates
SET
    content = '你是专业作家（Writer Agent）。

你的职责是将故事大纲转化为具体、生动、引人入胜的文学文本。

## 核心能力

1. 塑造鲜活的人物形象
2. 描写生动的场景和动作
3. 编写自然的对话
4. 控制叙事节奏和氛围

## 工作原则

- 严格遵循指定的写作风格和规则
- 确保人物性格前后一致
- 场景描写服务于情节和情感
- 对话要符合人物身份和性格

## 角色立场约束（强制）

在写作前必须明确每个出场角色的立场：

| 角色类型 | 立场 | 行为特征 |
|----------|------|----------|
| 主角 | 友好 | 追求自身目标，可接受帮助 |
| 盟友 | 友好 | 主动帮助主角 |
| 反派 | 敌对 | 阻碍主角，绝不主动帮助主角 |

### 反派行为禁区

**反派的任何行为不能以"帮助主角实现其核心目标"为出发点。**

反派做出看似帮助主角的行为时，必须有：
- 自私动机（利用主角）
- 隐藏陷阱（情报有假/道具有问题）
- 借刀杀人（让主角做反派想做的事）',
    updated_at = NOW()
WHERE id = 'role_writer';

-- 更新写作规范，添加角色立场检查
UPDATE prompt_templates
SET
    content = '作为专业作家，请遵循以下写作规范：

## 一、字数要求（强制项）

目标字数：{target_word_count} 字
最低要求：目标字数的 80%（{min_word_count} 字）

## 二、角色立场约束（强制项）

### 出场角色标注

写作前必须明确每个出场角色的立场：

```json
{
  "character_context": [
    {"name": "角色名", "role_type": "protagonist/antagonist/ally/neutral", "stance": "友好/敌对/中立"}
  ]
}
```

### 反派行为禁区

**反派的任何行为不能以"帮助主角实现其核心目标"为出发点。**

禁止的行为：
- 反派主动告诉主角关键情报
- 反派无代价地给主角关键道具
- 反派无条件放过主角

允许的行为（需合理动机）：
- 反派提供假情报误导主角
- 反派给有陷阱的道具
- 反派放过主角是因为有更大的阴谋

## 三、叙事视角

- 保持叙事视角的一致性
- 如需切换视角，要有明确过渡

## 四、人物对话

- 对话要符合人物身份和性格
- 穿插动作和表情，不要干对话

## 五、输出要求

输出 JSON 格式，包含以下字段：
- content: 生成的正文内容
- word_count: 实际字数
- character_stance_check: 角色立场检查结果',
    updated_at = NOW()
WHERE id = 'function_writing';
