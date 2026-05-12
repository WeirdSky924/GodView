-- V36 大纲资源需求与章节资源就绪状态
-- 将 workflow / Master Plotter 产生的 resource_requirements 持久化为待处理资源缺口，供后续 readiness gate 和 UI 使用。

CREATE TABLE IF NOT EXISTS outline_resource_requirements (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    outline_id TEXT,
    outline_version_id TEXT,
    chapter_id UUID REFERENCES chapters(id) ON DELETE SET NULL,
    chapter_num INTEGER,
    requirement_type TEXT NOT NULL,
    resource_name TEXT NOT NULL,
    severity TEXT NOT NULL DEFAULT 'advisory',
    status TEXT NOT NULL DEFAULT 'pending',
    reason TEXT NOT NULL DEFAULT '',
    suggested_payload JSONB NOT NULL DEFAULT '{}',
    matched_resource_id TEXT,
    matched_resource_type TEXT,
    source_excerpt TEXT,
    source_agent TEXT,
    source_node_id TEXT,
    source_execution_id TEXT,
    fingerprint TEXT,
    metadata JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    resolved_at TIMESTAMP WITH TIME ZONE
);

CREATE INDEX IF NOT EXISTS idx_outline_resource_requirements_project
    ON outline_resource_requirements(project_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_outline_resource_requirements_outline
    ON outline_resource_requirements(project_id, outline_id, chapter_num);
CREATE INDEX IF NOT EXISTS idx_outline_resource_requirements_status
    ON outline_resource_requirements(project_id, status, severity);
CREATE UNIQUE INDEX IF NOT EXISTS idx_outline_resource_requirements_fingerprint
    ON outline_resource_requirements(project_id, fingerprint)
    WHERE fingerprint IS NOT NULL;

CREATE TABLE IF NOT EXISTS chapter_resource_readiness (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    outline_id TEXT,
    outline_version_id TEXT,
    chapter_id UUID REFERENCES chapters(id) ON DELETE SET NULL,
    chapter_num INTEGER NOT NULL,
    blocking_total INTEGER NOT NULL DEFAULT 0,
    blocking_resolved INTEGER NOT NULL DEFAULT 0,
    advisory_total INTEGER NOT NULL DEFAULT 0,
    advisory_resolved INTEGER NOT NULL DEFAULT 0,
    readiness_status TEXT NOT NULL DEFAULT 'not_audited',
    last_audited_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_chapter_resource_readiness_project
    ON chapter_resource_readiness(project_id, chapter_num);
CREATE INDEX IF NOT EXISTS idx_chapter_resource_readiness_status
    ON chapter_resource_readiness(project_id, readiness_status);
CREATE INDEX IF NOT EXISTS idx_chapter_resource_readiness_outline
    ON chapter_resource_readiness(project_id, outline_id, chapter_num);
