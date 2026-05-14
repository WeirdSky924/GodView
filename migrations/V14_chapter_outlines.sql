-- V14 章节大纲和小说质量优化相关表
-- GodView v9 需求实现

-- ==================== 章节大纲表 ====================

CREATE TABLE IF NOT EXISTS chapter_outlines (
    id VARCHAR(64) PRIMARY KEY,
    project_id VARCHAR(64) NOT NULL,
    chapter_number INTEGER NOT NULL,

    -- 基本信息
    title VARCHAR(255) NOT NULL,
    summary TEXT,

    -- 状态
    status VARCHAR(32) DEFAULT 'draft',

    -- 场景规划（JSON 数组）
    scenes JSONB DEFAULT '[]',

    -- 情绪曲线（JSON 对象）
    emotion_curve JSONB,

    -- 章节目标（JSON 数组）
    chapter_goals JSONB DEFAULT '[]',

    -- 剧情推进
    plot_advancement TEXT,

    -- 角色发展弧线（JSON 对象）
    character_arcs JSONB DEFAULT '{}',

    -- 伏笔管理（JSON 数组）
    hooks_planted JSONB DEFAULT '[]',
    hooks_resolved JSONB DEFAULT '[]',

    -- 质量指标（JSON 对象）
    quality_metrics JSONB DEFAULT '{}',

    -- 字数规划
    target_word_count INTEGER DEFAULT 3000,
    estimated_word_count INTEGER DEFAULT 0,

    -- 元数据
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    approved_at TIMESTAMP,
    approved_by VARCHAR(64),

    -- 关联信息
    previous_outline_id VARCHAR(64),
    next_outline_id VARCHAR(64),
    deleted_at TIMESTAMP WITH TIME ZONE,

    -- 约束
    UNIQUE(project_id, chapter_number)
);

-- 索引
CREATE INDEX IF NOT EXISTS idx_chapter_outlines_project ON chapter_outlines(project_id);
CREATE INDEX IF NOT EXISTS idx_chapter_outlines_status ON chapter_outlines(status);
CREATE INDEX IF NOT EXISTS idx_chapter_outlines_chapter ON chapter_outlines(chapter_number);
CREATE INDEX IF NOT EXISTS idx_chapter_outlines_active_project_chapter ON chapter_outlines(project_id, chapter_number) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_chapter_outlines_deleted_at ON chapter_outlines(deleted_at);

-- 注释
COMMENT ON TABLE chapter_outlines IS '章节大纲表 - 存储每章的详细规划';
COMMENT ON COLUMN chapter_outlines.scenes IS '场景列表，包含场景类型、参与角色、情绪设计等';
COMMENT ON COLUMN chapter_outlines.emotion_curve IS '情绪曲线数据，用于规划章节情绪起伏';


-- ==================== 黄金三章检测结果表 ====================

CREATE TABLE IF NOT EXISTS golden_three_checks (
    id VARCHAR(64) PRIMARY KEY,
    project_id VARCHAR(64) NOT NULL,

    -- 检测结果
    opening_analysis JSONB,
    chapter_scores JSONB,
    golden_rules JSONB,
    reader_retention_prediction VARCHAR(32),
    improvement_suggestions JSONB,
    overall_score INTEGER,

    -- 元数据
    checked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- 关联章节
    chapter1_id VARCHAR(64),
    chapter2_id VARCHAR(64),
    chapter3_id VARCHAR(64)
);

CREATE INDEX IF NOT EXISTS idx_golden_three_project ON golden_three_checks(project_id);
CREATE INDEX IF NOT EXISTS idx_golden_three_score ON golden_three_checks(overall_score);

COMMENT ON TABLE golden_three_checks IS '黄金三章检测结果 - 存储开篇前三章的质量检测结果';


-- ==================== 爽点分析结果表 ====================

CREATE TABLE IF NOT EXISTS satisfaction_analyses (
    id VARCHAR(64) PRIMARY KEY,
    project_id VARCHAR(64) NOT NULL,
    chapter_number INTEGER NOT NULL,

    -- 分析结果
    cool_points JSONB DEFAULT '[]',
    density_analysis JSONB,
    overall_assessment TEXT,
    suggestions JSONB DEFAULT '[]',

    -- 元数据
    analyzed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    chapter_id VARCHAR(64)
);

CREATE INDEX IF NOT EXISTS idx_satisfaction_project ON satisfaction_analyses(project_id);
CREATE INDEX IF NOT EXISTS idx_satisfaction_chapter ON satisfaction_analyses(chapter_number);

COMMENT ON TABLE satisfaction_analyses IS '爽点分析结果 - 存储章节爽点检测结果';


-- ==================== 反派管理表 ====================

CREATE TABLE IF NOT EXISTS villains (
    id VARCHAR(64) PRIMARY KEY,
    project_id VARCHAR(64) NOT NULL,

    -- 基本信息
    name VARCHAR(255) NOT NULL,
    alias VARCHAR(255),
    description TEXT,

    -- 层级（小反派/中BOSS/大BOSS）
    villain_level VARCHAR(32) DEFAULT 'small',

    -- 动机
    motivation TEXT,
    conflict_with_protagonist TEXT,

    -- 实力设定
    power_level VARCHAR(64),
    strength_gap TEXT,

    -- 退场设计
    defeat_chapter INTEGER,
    defeat_method TEXT,

    -- 状态
    status VARCHAR(32) DEFAULT 'active',

    -- 关联冲突线（JSON 数组）
    conflict_ids JSONB DEFAULT '[]',

    -- 元数据
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    defeated_at TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_villains_project ON villains(project_id);
CREATE INDEX IF NOT EXISTS idx_villains_level ON villains(villain_level);
CREATE INDEX IF NOT EXISTS idx_villains_status ON villains(status);

COMMENT ON TABLE villains IS '反派管理表 - 追踪反派角色和冲突线';


-- ==================== 冲突线追踪表 ====================

CREATE TABLE IF NOT EXISTS conflicts (
    id VARCHAR(64) PRIMARY KEY,
    project_id VARCHAR(64) NOT NULL,

    -- 基本信息
    title VARCHAR(255) NOT NULL,
    description TEXT,

    -- 冲突类型（主线/支线/隐藏）
    conflict_type VARCHAR(32) DEFAULT 'main',

    -- 冲突等级
    intensity VARCHAR(32) DEFAULT 'medium',

    -- 参与方
    parties JSONB DEFAULT '[]',

    -- 进展
    status VARCHAR(32) DEFAULT 'active',
    start_chapter INTEGER,
    resolution_chapter INTEGER,

    -- 升级记录（JSON 数组）
    escalation_history JSONB DEFAULT '[]',

    -- 关联反派
    villain_id VARCHAR(64),

    -- 元数据
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    resolved_at TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_conflicts_project ON conflicts(project_id);
CREATE INDEX IF NOT EXISTS idx_conflicts_type ON conflicts(conflict_type);
CREATE INDEX IF NOT EXISTS idx_conflicts_status ON conflicts(status);

COMMENT ON TABLE conflicts IS '冲突线追踪表 - 管理主线、支线和隐藏冲突';


-- ==================== 卷大纲表 ====================

CREATE TABLE IF NOT EXISTS volume_outlines (
    id VARCHAR(64) PRIMARY KEY,
    project_id VARCHAR(64) NOT NULL,
    volume_number INTEGER NOT NULL,

    -- 基本信息
    title VARCHAR(255) NOT NULL,
    summary TEXT,

    -- 主题设计
    theme TEXT,
    theme_description TEXT,

    -- 高潮设计
    climax_chapter INTEGER,
    climax_description TEXT,

    -- 情绪曲线
    emotion_arc JSONB,

    -- 章节规划
    start_chapter INTEGER,
    end_chapter INTEGER,
    target_word_count INTEGER,

    -- 卷间过渡
    transition_from_previous TEXT,
    transition_to_next TEXT,

    -- 状态
    status VARCHAR(32) DEFAULT 'draft',

    -- 元数据
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    UNIQUE(project_id, volume_number)
);

CREATE INDEX IF NOT EXISTS idx_volume_project ON volume_outlines(project_id);
CREATE INDEX IF NOT EXISTS idx_volume_number ON volume_outlines(volume_number);

COMMENT ON TABLE volume_outlines IS '卷大纲表 - 管理卷级规划';


-- ==================== 配角生命周期表 ====================

CREATE TABLE IF NOT EXISTS character_lifecycles (
    id VARCHAR(64) PRIMARY KEY,
    project_id VARCHAR(64) NOT NULL,
    character_id VARCHAR(64) NOT NULL,

    -- 生命周期阶段（登场期/活跃期/发展期/稳定期/退场期）
    stage VARCHAR(32) DEFAULT 'intro',

    -- 出场统计
    first_appearance_chapter INTEGER,
    last_appearance_chapter INTEGER,
    total_appearances INTEGER DEFAULT 0,

    -- 独立故事线
    story_arc TEXT,

    -- 重要性变化（JSON 数组，记录每个阶段的重要性分数）
    importance_history JSONB DEFAULT '[]',

    -- 退场设计
    exit_planned BOOLEAN DEFAULT FALSE,
    exit_chapter INTEGER,
    exit_method VARCHAR(32),

    -- 状态
    status VARCHAR(32) DEFAULT 'active',

    -- 元数据
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_lifecycle_project ON character_lifecycles(project_id);
CREATE INDEX IF NOT EXISTS idx_lifecycle_character ON character_lifecycles(character_id);
CREATE INDEX IF NOT EXISTS idx_lifecycle_stage ON character_lifecycles(stage);

COMMENT ON TABLE character_lifecycles IS '配角生命周期表 - 追踪配角的出场和发展';


-- ==================== 伏笔追踪表（增强版） ====================

CREATE TABLE IF NOT EXISTS foreshadowings (
    id VARCHAR(64) PRIMARY KEY,
    project_id VARCHAR(64) NOT NULL,

    -- 基本信息
    title VARCHAR(255) NOT NULL,
    description TEXT,
    hook_type VARCHAR(32) DEFAULT 'custom',

    -- 状态
    status VARCHAR(32) DEFAULT 'planted',

    -- 埋设信息
    plant_chapter INTEGER,
    plant_context TEXT,
    plant_hint TEXT,

    -- 回收信息
    reveal_chapter INTEGER,
    reveal_context TEXT,
    reveal_hint TEXT,

    -- 关联
    related_characters JSONB DEFAULT '[]',
    related_locations JSONB DEFAULT '[]',
    related_objects JSONB DEFAULT '[]',

    -- 意图记录（为什么埋这个伏笔）
    author_intent TEXT,

    -- 优先级
    priority INTEGER DEFAULT 3,

    -- 元数据
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    resolved_at TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_foreshadowing_project ON foreshadowings(project_id);
CREATE INDEX IF NOT EXISTS idx_foreshadowing_status ON foreshadowings(status);
CREATE INDEX IF NOT EXISTS idx_foreshadowing_priority ON foreshadowings(priority);

COMMENT ON TABLE foreshadowings IS '伏笔追踪表 - 管理伏笔的埋设和回收';


-- ==================== 记忆条目表 ====================
-- 注意：embedding 向量存储在 Qdrant 中，不在 PostgreSQL 存储

CREATE TABLE IF NOT EXISTS memory_entries (
    id VARCHAR(64) PRIMARY KEY,
    project_id VARCHAR(64) NOT NULL,

    -- 记忆类型（短期/中期/长期）
    memory_type VARCHAR(32) DEFAULT 'short_term',

    -- 内容
    content TEXT NOT NULL,
    summary TEXT,

    -- 关联信息
    chapter_number INTEGER,
    character_ids JSONB DEFAULT '[]',
    event_ids JSONB DEFAULT '[]',

    -- 重要性
    importance_score FLOAT DEFAULT 0.5,

    -- 访问统计
    access_count INTEGER DEFAULT 0,
    last_accessed_at TIMESTAMP,

    -- 元数据
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_memory_project ON memory_entries(project_id);
CREATE INDEX IF NOT EXISTS idx_memory_type ON memory_entries(memory_type);
CREATE INDEX IF NOT EXISTS idx_memory_chapter ON memory_entries(chapter_number);

COMMENT ON TABLE memory_entries IS '记忆条目表 - 存储长篇创作中的关键信息记忆';


-- ==================== 黄金三章规则配置表 ====================

CREATE TABLE IF NOT EXISTS golden_three_rules (
    id VARCHAR(64) PRIMARY KEY,
    rule_type VARCHAR(32) NOT NULL,
    rule_name VARCHAR(255) NOT NULL,
    description TEXT NOT NULL,
    check_points JSONB DEFAULT '[]',
    examples JSONB DEFAULT '[]',
    weight FLOAT DEFAULT 1.0,
    severity VARCHAR(32) DEFAULT 'important',
    applicable_genres JSONB DEFAULT '[]',
    applicable_chapter INTEGER DEFAULT 1,
    fix_suggestions JSONB DEFAULT '[]',
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_golden_rules_type ON golden_three_rules(rule_type);
CREATE INDEX IF NOT EXISTS idx_golden_rules_active ON golden_three_rules(is_active);
CREATE INDEX IF NOT EXISTS idx_golden_rules_chapter ON golden_three_rules(applicable_chapter);

COMMENT ON TABLE golden_three_rules IS '黄金三章规则配置表 - 可配置的检测规则';
