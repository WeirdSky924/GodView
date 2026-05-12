-- Unified Assistant Context Fabric schema

CREATE TABLE IF NOT EXISTS assistant_project_snapshots (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
    snapshot_version BIGINT NOT NULL,
    status TEXT NOT NULL DEFAULT 'ready',
    source_revision_hash TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    summary TEXT,
    structured_index JSONB DEFAULT '{}',
    entity_index JSONB DEFAULT '{}',
    retrieval_manifest JSONB DEFAULT '{}',
    token_estimate INTEGER DEFAULT 0,
    build_reason TEXT DEFAULT 'initial',
    forced_by_user_id TEXT,
    force_rebuild_request_id TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    built_at TIMESTAMP WITH TIME ZONE,
    error_message TEXT
);

CREATE INDEX IF NOT EXISTS idx_assistant_snapshots_project_version
    ON assistant_project_snapshots(project_id, snapshot_version DESC);
CREATE INDEX IF NOT EXISTS idx_assistant_snapshots_project_status
    ON assistant_project_snapshots(project_id, status);
CREATE UNIQUE INDEX IF NOT EXISTS idx_assistant_snapshots_project_request
    ON assistant_project_snapshots(project_id, force_rebuild_request_id)
    WHERE force_rebuild_request_id IS NOT NULL;

CREATE TABLE IF NOT EXISTS assistant_snapshot_sections (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    snapshot_id UUID REFERENCES assistant_project_snapshots(id) ON DELETE CASCADE,
    project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
    section_type TEXT NOT NULL,
    scope_key TEXT,
    title TEXT,
    content TEXT NOT NULL DEFAULT '',
    structured_payload JSONB DEFAULT '{}',
    entity_refs JSONB DEFAULT '[]',
    priority INTEGER DEFAULT 100,
    content_hash TEXT NOT NULL,
    token_estimate INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_assistant_sections_project_type
    ON assistant_snapshot_sections(project_id, section_type);
CREATE INDEX IF NOT EXISTS idx_assistant_sections_snapshot_type
    ON assistant_snapshot_sections(snapshot_id, section_type);
CREATE INDEX IF NOT EXISTS idx_assistant_sections_content_hash
    ON assistant_snapshot_sections(content_hash);

CREATE TABLE IF NOT EXISTS assistant_context_deltas (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
    entity_type TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    operation TEXT NOT NULL,
    before_hash TEXT,
    after_hash TEXT,
    payload_summary JSONB DEFAULT '{}',
    source_table TEXT,
    source_updated_at TIMESTAMP WITH TIME ZONE,
    consumed_by_snapshot_id UUID REFERENCES assistant_project_snapshots(id) ON DELETE SET NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_assistant_deltas_project_created
    ON assistant_context_deltas(project_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_assistant_deltas_project_entity
    ON assistant_context_deltas(project_id, entity_type, entity_id);

CREATE TABLE IF NOT EXISTS assistant_sessions (
    id TEXT PRIMARY KEY,
    project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
    assistant_surface TEXT NOT NULL,
    mode TEXT NOT NULL DEFAULT 'default',
    status TEXT DEFAULT 'active',
    snapshot_id UUID REFERENCES assistant_project_snapshots(id) ON DELETE SET NULL,
    snapshot_version BIGINT,
    history_window JSONB DEFAULT '[]',
    history_summary TEXT DEFAULT '',
    history_summary_hash TEXT,
    session_state JSONB DEFAULT '{}',
    pending_items JSONB DEFAULT '[]',
    context_cursor JSONB DEFAULT '{}',
    last_packet_id UUID,
    last_activity_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    reset_at TIMESTAMP WITH TIME ZONE,
    reset_reason TEXT,
    force_reread_after TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_assistant_sessions_project_surface
    ON assistant_sessions(project_id, assistant_surface, status);
CREATE INDEX IF NOT EXISTS idx_assistant_sessions_project_activity
    ON assistant_sessions(project_id, last_activity_at DESC);
CREATE UNIQUE INDEX IF NOT EXISTS idx_assistant_sessions_active_surface_mode
    ON assistant_sessions(project_id, assistant_surface, mode)
    WHERE status = 'active';

CREATE TABLE IF NOT EXISTS assistant_messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id TEXT REFERENCES assistant_sessions(id) ON DELETE CASCADE,
    project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
    request_id TEXT,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    metadata JSONB DEFAULT '{}',
    packet_id UUID,
    snapshot_id UUID REFERENCES assistant_project_snapshots(id) ON DELETE SET NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_assistant_messages_session_created
    ON assistant_messages(session_id, created_at);
CREATE UNIQUE INDEX IF NOT EXISTS idx_assistant_messages_request_role
    ON assistant_messages(session_id, request_id, role)
    WHERE request_id IS NOT NULL;

CREATE TABLE IF NOT EXISTS assistant_context_packets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
    session_id TEXT REFERENCES assistant_sessions(id) ON DELETE SET NULL,
    assistant_surface TEXT NOT NULL,
    request_id TEXT,
    snapshot_id UUID REFERENCES assistant_project_snapshots(id) ON DELETE SET NULL,
    snapshot_version BIGINT,
    packet_scope JSONB NOT NULL DEFAULT '{}',
    budget JSONB NOT NULL DEFAULT '{}',
    selected_sections JSONB NOT NULL DEFAULT '[]',
    delta_ids JSONB DEFAULT '[]',
    retrieval_manifest JSONB DEFAULT '{}',
    token_estimate INTEGER DEFAULT 0,
    truncated BOOLEAN DEFAULT FALSE,
    invalidation_state TEXT DEFAULT 'fresh',
    force_reread BOOLEAN DEFAULT FALSE,
    history_reset_applied BOOLEAN DEFAULT FALSE,
    metadata JSONB DEFAULT '{}',
    content_hash TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_assistant_packets_session_surface_created
    ON assistant_context_packets(session_id, assistant_surface, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_assistant_packets_project_surface_created
    ON assistant_context_packets(project_id, assistant_surface, created_at DESC);
CREATE UNIQUE INDEX IF NOT EXISTS idx_assistant_packets_request
    ON assistant_context_packets(session_id, request_id, assistant_surface)
    WHERE request_id IS NOT NULL;
