# GodView v6 功能实现状态

> 每完成一个功能，就在对应项前面打 `x`
> 基于 `godView_v6.md` 需求文档

---

## Part 1: 项目管理架构改进

### 1.1 数据模型改进

- [x] Character 模型添加 `project_id` 字段 - `app/models/character.py`
- [x] World 模型添加 `project_id` 字段 - `app/models/world.py`
- [x] Chapter 模型添加 `project_id` 字段 - `app/models/plot.py`
- [x] Hook 模型添加 `project_id` 字段 - `app/models/plot.py`

### 1.2 数据库层改进

- [x] `get_characters()` 支持 `project_id` 过滤 - `app/database/postgres.py`
- [x] `get_worlds()` 支持 `project_id` 过滤 - `app/database/postgres.py`
- [x] `get_chapters()` 支持 `project_id` 过滤 - `app/database/postgres.py`
- [x] `get_hooks()` 支持 `project_id` 过滤 - `app/database/postgres.py`

### 1.3 API 层改进

- [x] GET /characters 支持 `project_id` 参数 - `app/api/routes/characters.py`
- [x] GET /worlds 支持 `project_id` 参数 - `app/api/routes/worlds.py`
- [x] GET /chapters 支持 `project_id` 参数 - `app/api/routes/plots.py`
- [x] 伏笔相关路由支持项目过滤 - `app/api/routes/plots.py`

### 1.4 前端架构改进

- [x] 项目上下文组件 - `frontend/src/contexts/ProjectContext.tsx`
- [x] Layout 添加项目选择器 - `frontend/src/components/Layout.tsx`
- [x] main.tsx 包裹 ProjectProvider - 已集成
- [x] `frontend/src/api/characters.ts` 支持 `projectId` 参数
- [x] `frontend/src/api/worlds.ts` 支持 `projectId` 参数
- [x] `frontend/src/api/chapters.ts` 支持 `projectId` 参数

### 1.5 页面项目过滤

- [x] Characters.tsx 使用项目过滤
- [x] Worlds.tsx 使用项目过滤
- [x] Plots.tsx 使用项目过滤
- [x] Hooks.tsx 使用项目过滤
- [x] Director.tsx 使用项目过滤
- [x] Interventions.tsx 使用项目过滤
- [x] NovelView.tsx 使用项目过滤

---

## Part 2: Bootstrap 角色提取与动态创建增强

### 2.1 后端 API

- [x] POST /bootstrap/{session_id}/finalize-setting 端点 - `app/api/routes/bootstrap.py`
- [x] 设定结束自动创建世界和角色

### 2.2 Setting Agent 增强

- [x] `extract_seed_from_history()` 公共方法 - `app/services/setting_agent.py`
- [x] 强制提取 seed（不依赖对话轮数阈值）

### 2.3 Bootstrap Orchestrator 增强

- [x] `_bootstrap_world()` 关联项目 ID - `app/services/bootstrap_orchestrator.py`
- [x] `_bootstrap_characters()` 关联项目 ID
- [x] 创建世界后更新项目的 `world_id`
- [x] `finalize_setting()` 方法

### 2.4 WebSocket 动态角色创建

- [x] `add_character` 消息类型 - `app/api/routes/websocket.py`
- [x] `handle_add_character()` 处理函数
- [x] 动态创建角色并保存到数据库
- [x] `handle_remove_character()` 处理函数
- [x] `handle_get_characters()` 处理函数

### 2.5 Director 服务增强

- [x] `add_character()` 方法 - `app/services/director.py`
- [x] `remove_character()` 方法
- [x] `get_all_characters()` 方法
- [x] `get_character()` 方法

### 2.6 前端 Bootstrap 页面

- [x] 设定结束按钮 - `frontend/src/pages/Bootstrap.tsx`
- [x] `handleFinalizeSetting()` 处理函数
- [x] `finalizeSetting()` API 函数 - `frontend/src/api/bootstrap.ts`

### 2.7 前端 Director 页面

- [x] WebSocket 消息类型定义
- [x] 动态添加角色 UI（可选增强）
- [x] 添加角色 Modal 组件
- [x] 角色列表显示
- [x] 移除角色功能

---

## Part 3: LLM 模型配置增强

### 3.1 后端 Provider 扩展

- [x] 扩展 `LLM_PROVIDERS` 列表 - `app/api/routes/config.py`
  - [x] OpenAI (已有)
  - [x] Anthropic (已有)
  - [x] 智谱AI (GLM)
  - [x] 通义千问 (阿里云)
  - [x] DeepSeek (深度求索)
  - [x] 月之暗面 (Kimi)
  - [x] 百川智能
  - [x] 百度文心一言
  - [x] 零一万物 (Yi)
  - [x] MiniMax
  - [x] OpenRouter (聚合网关)
  - [x] 自定义 (OpenAI 兼容)

### 3.2 后端 API

- [x] GET /config/llm/providers/{provider_id}/models 端点
- [x] 模型列表包含上下文长度信息

### 3.3 前端设置页面

- [x] Provider 选择卡片网格 - `frontend/src/pages/Settings.tsx`
- [x] 模型下拉选择
- [x] 配置提示信息显示
- [x] API Key 获取链接
- [x] Provider 详情展示
- [x] 高级参数（Temperature、Max Tokens）滑块

### 3.4 前端 API

- [x] `getProviderModels()` 函数 - `frontend/src/api/config.ts`

---

## Part 4: 项目 Token 消耗统计

### 4.1 数据模型

- [x] Token 使用记录模型 - `app/models/token_usage.py`
  - [x] `TokenType` 枚举
  - [x] `UsageCategory` 枚举
  - [x] `TokenUsageRecord` 模型
  - [x] `TokenUsageSummary` 模型
  - [x] `ProjectTokenStats` 模型
  - [x] `MODEL_PRICING` 价格表
  - [x] `calculate_cost()` 函数

### 4.2 Project 模型更新

- [x] 添加 `total_tokens` 字段 - `app/models/project.py`
- [x] 添加 `total_cost` 字段

### 4.3 Token 追踪服务

- [x] Token 追踪服务 - `app/services/token_tracker.py`
  - [x] `record_usage()` 方法
  - [x] `get_project_summary()` 方法
  - [x] `get_project_stats()` 方法
  - [x] `get_all_project_stats()` 方法

### 4.4 LLM 调用集成

- [x] `call_llm_with_tracking()` 函数 - `app/services/model_router.py`
- [x] 记录输入/输出 token 数
- [x] 计算费用估算

### 4.5 API 端点

- [x] Token 使用统计 API - `app/api/routes/token_usage.py`
  - [x] GET /token-usage/projects/{project_id}/summary
  - [x] GET /token-usage/projects/{project_id}/stats
  - [x] GET /token-usage/stats

### 4.6 前端组件

- [x] Token 统计组件 - `frontend/src/components/TokenStats.tsx`
  - [x] 核心指标卡片（总量、今日、本周、本月）
  - [x] 7 天趋势柱状图
  - [x] 使用场景分布进度条
- [x] Dashboard 集成 Token 统计 - `frontend/src/pages/Dashboard.tsx`

### 4.7 前端 API

- [x] Token 使用 API - `frontend/src/api/tokenUsage.ts`
  - [x] `getProjectTokenStats()` 函数
  - [x] `getAllTokenStats()` 函数

---

## Part 5: 数据库表结构设计

### 5.1 表结构更新

- [x] projects 表添加 token 统计字段
  ```sql
  total_tokens BIGINT DEFAULT 0,
  total_cost DECIMAL(10, 6) DEFAULT 0
  ```
- [x] worlds 表添加 `project_id` 外键
- [x] characters 表添加 `project_id` 外键
- [x] chapters 表添加 `project_id` 外键
- [x] hooks 表添加 `project_id` 外键

### 5.2 新建表

- [x] token_usage 表
  ```sql
  id, project_id, input_tokens, output_tokens, total_tokens,
  provider, model, category, agent_name, session_id,
  chapter_id, character_id, estimated_cost, created_at, metadata
  ```
- [x] interventions 表（如果不存在）
- [x] snapshots 表（如果不存在）

### 5.3 索引创建

- [x] idx_characters_project_id
- [x] idx_worlds_project_id
- [x] idx_chapters_project_id
- [x] idx_hooks_project_id
- [x] idx_token_usage_project_id
- [x] idx_token_usage_category
- [x] idx_token_usage_created_at
- [x] idx_token_usage_model

### 5.4 数据库服务层方法

- [x] `save_token_usage()` 方法 - `app/database/postgres.py`
- [x] `_update_project_token_stats()` 方法
- [x] `get_token_usage_by_project()` 方法
- [x] `get_token_stats_by_project()` 方法
- [x] `get_token_stats_by_category()` 方法
- [x] `get_token_stats_by_model()` 方法
- [x] `get_daily_token_stats()` 方法
- [x] `get_all_project_token_stats()` 方法

---

## Part 6: Agent Skill 系统

> Agent 可以生成 skill 并保存到全局库中，用户可将 skill 分配给特定项目的特定 Agent

### 6.1 数据模型

**新文件**: `app/models/skill.py`

- [x] `SkillType` 枚举 (prompt/function/workflow/knowledge)
- [x] `SkillStatus` 枚举 (draft/active/deprecated)
- [x] `SkillParameter` 模型（参数定义）
- [x] `Skill` 模型
- [x] `SkillAssignment` 模型（分配关系）
- [x] `SkillExecutionLog` 模型（执行记录）
- [x] DTO 类 (CreateSkillDTO, UpdateSkillDTO, AssignSkillDTO, ExecuteSkillDTO)

### 6.2 服务层

**新文件**: `app/services/skill_service.py`

- [x] `SkillService` 类
  - [x] `create_skill()` - 创建 skill
  - [x] `get_skill()` - 获取 skill
  - [x] `get_all_skills()` - 列出 skills（支持过滤）
  - [x] `update_skill()` - 更新 skill
  - [x] `delete_skill()` - 删除 skill
  - [x] `search_skills()` - 搜索 skills
  - [x] `assign_skill_to_agent()` - 分配 skill
  - [x] `unassign_skill_from_agent()` - 取消分配
  - [x] `get_agent_skills()` - 获取 agent 的 skills
  - [x] `execute_skill()` - 执行 skill
  - [x] `_execute_prompt_skill()` - 执行 prompt 类型
  - [x] `_execute_function_skill()` - 执行 function 类型
  - [x] `_execute_workflow_skill()` - 执行 workflow 类型
  - [x] `_execute_knowledge_skill()` - 执行 knowledge 类型
  - [x] `get_execution_logs()` - 获取执行日志
  - [x] `generate_skill_from_description()` - AI 生成 skill

### 6.3 API 端点

**新文件**: `app/api/routes/skills.py`

- [x] `GET /skills` - 获取 skill 列表
- [x] `POST /skills` - 创建新 skill
- [x] `GET /skills/{skill_id}` - 获取 skill 详情
- [x] `PUT /skills/{skill_id}` - 更新 skill
- [x] `DELETE /skills/{skill_id}` - 删除 skill
- [x] `POST /skills/search` - 搜索 skill
- [x] `POST /skills/generate` - AI 生成 skill
- [x] `POST /skills/{skill_id}/test` - 测试 skill
- [x] `POST /skills/{skill_id}/execute` - 执行 skill
- [x] `POST /skills/assign` - 分配 skill 给 agent
- [x] `DELETE /skills/assign` - 取消分配
- [x] `GET /skills/agent/{project_id}/{agent_id}` - 获取 agent 的 skills
- [x] `GET /skills/{skill_id}/logs` - 获取执行日志
- [x] `GET /skills/stats/overview` - 获取统计信息

### 6.4 前端页面

**新文件**: `frontend/src/pages/Skills.tsx`

- [x] Skill 库列表页面
  - [x] 按类型过滤
  - [x] 按状态过滤
  - [x] 搜索功能
- [x] 创建 Skill 按钮和表单
- [x] Skill 详情展示
- [x] Skill 编辑功能
- [x] Skill 删除确认
- [x] Skill 测试功能

### 6.5 前端 API

**新文件**: `frontend/src/api/skills.ts`

- [x] `getSkills()` 函数
- [x] `getSkill()` 函数
- [x] `createSkill()` 函数
- [x] `updateSkill()` 函数
- [x] `deleteSkill()` 函数
- [x] `generateSkill()` 函数
- [x] `testSkill()` 函数
- [x] `executeSkill()` 函数
- [x] `assignSkill()` 函数
- [x] `unassignSkill()` 函数
- [x] `getAgentSkills()` 函数
- [x] `getSkillLogs()` 函数
- [x] `getSkillsStats()` 函数

### 6.6 导航集成

- [x] 添加 Skills 菜单项到 Layout

---

## Part 7: 双 RAG 架构设计（动态剧情 + 静态设定）

> 现有向量/图数据库记录"现在进行时"，需补充充当"世界宪法"和"风物志"的静态设定 RAG

### 7.1 数据模型

**新文件**: `app/models/lore.py`

- [x] `LoreCategory` 枚举（设定类别）
  - [x] WORLD_RULE - 世界规则
  - [x] GEOGRAPHY - 地理设定
  - [x] HISTORY - 历史背景
  - [x] FACTION - 势力体系
  - [x] CULTURE - 文化习俗
  - [x] RACE - 种族设定
  - [x] PROFESSION - 职业/阶层
  - [x] ITEM - 物品/装备
  - [x] SKILL - 技能/能力
- [x] `LorePriority` 枚举（优先级）
  - [x] CONSTITUTIONAL - 宪法级（不可违反）
  - [x] CORE - 核心设定
  - [x] STANDARD - 标准设定
  - [x] FLEXIBLE - 灵活设定
- [x] `LoreEntry` 模型
- [x] `LoreReference` 模型
- [x] `LoreConflict` 模型

**新文件**: `app/models/narrative.py`

- [x] `NarrativeEntryType` 枚举
- [x] `TemporalScope` 枚举
- [x] `NarrativeEntry` 模型
- [x] `CharacterState` 模型
- [x] `WorldSnapshot` 模型

### 7.2 Qdrant 集合重构

**文件**: `app/database/qdrant.py`

- [x] 多集合架构
  - [x] `godview_lore` - 静态设定 RAG
  - [x] `godview_narrative` - 动态剧情 RAG
  - [x] `godview_voice` - 角色声音样本
- [x] `init_collections()` 初始化所有集合
- [x] 静态设定 RAG 操作
  - [x] `add_lore_entry()` 添加设定
  - [x] `search_lore()` 搜索设定
  - [x] `get_lore_by_keywords()` 关键词获取
  - [x] `delete_lore_entry()` 删除设定
- [x] 动态剧情 RAG 操作
  - [x] `add_narrative_entry()` 添加剧情
  - [x] `search_narrative()` 搜索剧情
  - [x] `get_recent_narratives()` 获取最近剧情
  - [x] `delete_narrative_entry()` 删除剧情

### 7.3 NebulaGraph Schema 扩展

**文件**: `app/database/nebulagraph.py`

- [x] `init_lore_schema()` 静态设定 Schema
  - [x] Tags: lore_world_rule, lore_geography, lore_faction, lore_race, lore_item
  - [x] Edges: lore_parent_of, lore_related_to, lore_constrains
- [x] `init_narrative_schema()` 动态剧情 Schema
  - [x] Tags: narrative_event, narrative_state_change, narrative_relationship_change
  - [x] Edges: causes, participates_in, occurs_at, references_lore

### 7.4 服务层

**新文件**: `app/services/lore_rag.py`

- [x] `LoreRAGService` 类
  - [x] `add_lore()` 添加设定
  - [x] `search_lore()` 搜索设定
  - [x] `get_constitutional_rules()` 获取宪法级规则
  - [x] `validate_against_lore()` 验证内容合规性
  - [x] `get_lore_context_for_generation()` 获取生成上下文

**新文件**: `app/services/narrative_rag.py`

- [x] `NarrativeRAGService` 类
  - [x] `record_event()` 记录事件
  - [x] `search_narrative()` 搜索剧情
  - [x] `get_character_state()` 获取角色状态
  - [x] `get_narrative_context()` 获取剧情上下文
  - [x] `get_recent_events()` 获取最近事件

**新文件**: `app/services/rag_orchestrator.py`

- [x] `RAGOrchestrator` 类
  - [x] `get_full_context()` 获取完整上下文（静态+动态）
  - [x] `validate_generation()` 验证生成内容
  - [x] `_assemble_prompt()` 组装生成提示

### 7.5 API 端点

**新文件**: `app/api/routes/lore.py`

- [x] `GET /lore` - 获取设定列表
- [x] `POST /lore` - 创建设定
- [x] `GET /lore/{lore_id}` - 获取设定详情
- [x] `PUT /lore/{lore_id}` - 更新设定
- [x] `DELETE /lore/{lore_id}` - 删除设定
- [x] `POST /lore/search` - 搜索设定
- [x] `POST /lore/validate` - 验证内容合规性

### 7.6 前端页面

**新文件**: `frontend/src/pages/Lore.tsx`

- [x] 设定库页面
  - [x] 类别过滤（树形结构）
  - [x] 优先级标识
  - [x] 搜索功能
  - [x] 设定详情查看
- [x] 设定编辑器
  - [x] Markdown 编辑器
  - [x] 关键词标签
  - [x] 约束条件编辑
  - [x] 关联设定选择

**新文件**: `frontend/src/components/lore/LoreTree.tsx`

- [x] 设定分类树组件
- [x] 层级关系展示
- [x] 快速导航

### 7.7 前端 API

**新文件**: `frontend/src/api/lore.ts`

- [x] `getLoreList()` 函数
- [x] `getLore()` 函数
- [x] `createLore()` 函数
- [x] `updateLore()` 函数
- [x] `deleteLore()` 函数
- [x] `searchLore()` 函数
- [x] `validateLore()` 函数

### 7.8 导航集成

- [x] 添加 Lore 菜单项到 Layout

---

## Part 8: Setting Agent 持续设定管理

> Setting Agent 不是一次性工具，而是持续的设定管理者，负责管理项目的 Lore RAG

### 8.1 数据模型

**新文件**: `app/models/setting_agent.py`

- [x] `SettingAgentMode` 枚举
  - [x] BOOTSTRAP - 初始化模式
  - [x] MANAGEMENT - 管理模式
  - [x] CONFLICT_RESOLUTION - 冲突解决模式
- [x] `SettingChangeType` 枚举 (add/modify/delete/merge)
- [x] `SettingConflict` 模型
  - [x] 冲突类型、描述、严重程度
  - [x] 涉及的现有设定和新设定
  - [x] 解决状态和方案
- [x] `SettingChangeRequest` 模型
  - [x] 变更类型、目标设定
  - [x] 冲突检测结果
- [x] `SettingAgentSession` 模型
  - [x] 持久化会话（每个项目一个）
  - [x] 对话历史
  - [x] 当前请求和待解决冲突
- [x] `LoreKnowledgeIndex` 模型
  - [x] 关键词索引
  - [x] 实体索引
  - [x] 宪法级规则缓存

### 8.2 服务层

**新文件**: `app/services/setting_agent_service.py`

- [x] `SettingAgentService` 类
  - [x] 会话管理
    - [x] `get_or_create_session()` 获取或创建会话
    - [x] `_load_knowledge_index()` 加载知识索引
  - [x] 设定变更处理
    - [x] `process_setting_change()` 处理变更请求
    - [x] `_detect_conflicts()` 冲突检测
  - [x] 冲突解决
    - [x] `_generate_conflict_description()` 生成冲突说明
    - [x] `_generate_resolution_suggestions()` 生成解决建议
  - [x] 协商对话
    - [x] `negotiate()` 协商解决冲突
    - [x] `_analyze_user_intent()` 分析用户意图
    - [x] `_generate_negotiation_response()` 生成协商回复
  - [x] 执行变更
    - [x] `execute_change()` 执行设定变更
  - [x] 查询接口
    - [x] `get_project_lore_summary()` 获取设定摘要
    - [x] `chat()` 与 Agent 聊天

### 8.3 冲突检测引擎

**新文件**: `app/services/conflict_detector.py`

- [x] 名称冲突检测
- [x] 关键词冲突检测
- [x] 语义冲突检测（简化版）
- [x] 宪法级规则违规检测

### 8.4 API 端点

**新文件**: `app/api/routes/setting_agent.py`

- [x] `POST /setting-agent/chat` - 与 Agent 聊天
- [x] `POST /setting-agent/change` - 请求设定变更
- [x] `POST /setting-agent/negotiate` - 协商解决冲突
- [x] `GET /setting-agent/{project_id}/summary` - 获取设定摘要
- [x] `GET /setting-agent/{project_id}/history` - 获取对话历史
- [x] `GET /setting-agent/{project_id}/conflicts` - 获取待处理冲突
- [x] `POST /setting-agent/{project_id}/session` - 创建或获取会话

### 8.5 前端组件

**新文件**: `frontend/src/components/setting/SettingAgentChat.tsx`

- [x] 聊天界面
  - [x] 消息列表
  - [x] 输入框
  - [x] 发送按钮
- [x] 冲突提示组件
  - [x] 冲突说明
  - [x] 解决选项按钮
- [x] 设定摘要展示

**修改文件**: `frontend/src/pages/Lore.tsx`

- [x] 集成 Setting Agent 聊天组件
- [x] 侧边栏聊天面板

### 8.6 前端 API

**新文件**: `frontend/src/api/settingAgent.ts`

- [x] `chatWithSettingAgent()` 函数
- [x] `requestSettingChange()` 函数
- [x] `negotiateConflict()` 函数
- [x] `getLoreSummary()` 函数
- [x] `getChatHistory()` 函数
- [x] `getPendingConflicts()` 函数
- [x] `executeSettingChange()` 函数
- [x] `createOrGetSession()` 函数

### 8.7 导航集成

- [x] Lore 页面添加 Setting Agent 入口

---

## 实现状态总结

### Part 1: 项目管理架构改进 (100%)
- 数据模型: 4/4 ✅
- 数据库层: 4/4 ✅
- API 层: 4/4 ✅
- 前端架构: 6/6 ✅
- 页面过滤: 7/7 ✅

### Part 7: 双 RAG 架构 (100%)
- 数据模型: 10/10 ✅
- Qdrant 集合重构: 11/11 ✅
- NebulaGraph Schema: 2/2 ✅
- 服务层: 17/17 ✅
- API 端点: 7/7 ✅
- 前端页面: 3/3 ✅
- 前端 API: 7/7 ✅
- 导航集成: 1/1 ✅

### Part 8: Setting Agent 持续管理 (100%)
- 数据模型: 6/6 ✅
- 服务层: 14/14 ✅
- 冲突检测引擎: 4/4 ✅
- API 端点: 7/7 ✅
- 前端组件: 3/3 ✅
- 前端 API: 8/8 ✅
- 导航集成: 1/1 ✅

### Part 2: Bootstrap 角色提取增强 (100%)
- 后端 API: 2/2 ✅
- Setting Agent: 2/2 ✅
- Bootstrap Orchestrator: 4/4 ✅
- WebSocket: 5/5 ✅
- Director 服务: 4/4 ✅
- 前端 Bootstrap: 3/3 ✅
- 前端 Director: 2/2 ✅

### Part 3: LLM 模型配置增强 (100%)
- 后端 Provider: 12/12 ✅
- 后端 API: 2/2 ✅
- 前端设置页面: 6/6 ✅
- 前端 API: 1/1 ✅

### Part 4: Token 消耗统计 (100%)
- 数据模型: 7/7 ✅
- Project 模型: 2/2 ✅
- 追踪服务: 4/4 ✅
- LLM 集成: 3/3 ✅
- API 端点: 3/3 ✅
- 前端组件: 3/3 ✅
- 前端 API: 2/2 ✅

### Part 5: 数据库表结构 (100%)
- 表结构更新: 5/5 ✅
- 新建表: 3/3 ✅
- 索引创建: 8/8 ✅
- 服务层方法: 8/8 ✅

### Part 6: Agent Skill 系统 (100%)
- 数据模型: 6/6 ✅
- 服务层: 18/18 ✅
- API 端点: 14/14 ✅
- 前端页面: 6/6 ✅
- 前端 API: 13/13 ✅
- 导航集成: 1/1 ✅

---

## 优先级建议

1. **已完成 - Part 1 项目管理架构**
   - ✅ 项目隔离基础设施

2. **已完成 - Part 7 双 RAG 架构**
   - ✅ 静态设定 + 动态剧情分离

3. **已完成 - Part 8 Setting Agent 持续管理**
   - ✅ 冲突检测和协商解决

4. **已完成 - Part 2 Bootstrap 增强**
   - ✅ 角色提取和动态创建

5. **已完成 - Part 6 Agent Skill 系统**
   - ✅ Skill 创建、管理、执行

6. **已完成 - Part 3 LLM 配置增强**
   - ✅ 国内模型支持（智谱、通义、DeepSeek、Kimi、百川、文心、Yi、MiniMax）
   - ✅ OpenRouter 聚合网关
   - ✅ 自定义 OpenAI 兼容服务

7. **已完成 - Part 4 Token 统计**
   - ✅ Token 消耗追踪和成本估算
   - ✅ 每日/每周/每月统计
   - ✅ 使用场景分布

8. **已完成 - Part 5 数据库表结构**
   - ✅ 表结构更新（project_id 外键、token 统计字段）
   - ✅ 新建表（token_usage、interventions、snapshots、skills 相关表）
   - ✅ 索引创建
   - ✅ 数据库服务层方法

---

*最后更新: 2026/04/07*
*基于 godView_v6.md 需求文档*
*包含 Part 1-8 全部需求*
*所有 Part 已完成！🎉*
