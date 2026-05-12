-- GodView V38: commercial-grade lore-to-character reference resolution

ALTER TABLE characters
ADD COLUMN IF NOT EXISTS aliases JSONB DEFAULT '[]'::jsonb;

ALTER TABLE lore_entries
ADD COLUMN IF NOT EXISTS related_character_refs JSONB DEFAULT '[]'::jsonb,
ADD COLUMN IF NOT EXISTS unresolved_character_refs JSONB DEFAULT '[]'::jsonb;

CREATE TABLE IF NOT EXISTS lore_character_references (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    lore_id UUID NOT NULL REFERENCES lore_entries(id) ON DELETE CASCADE,
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    character_id UUID REFERENCES characters(id) ON DELETE SET NULL,
    source_text TEXT NOT NULL DEFAULT '',
    confidence NUMERIC(5, 4) NOT NULL DEFAULT 0,
    resolution_method TEXT NOT NULL DEFAULT 'unknown',
    status TEXT NOT NULL DEFAULT 'unresolved',
    provenance JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_lore_character_refs_lore
ON lore_character_references(lore_id);

CREATE INDEX IF NOT EXISTS idx_lore_character_refs_project
ON lore_character_references(project_id, status);

CREATE INDEX IF NOT EXISTS idx_lore_character_refs_character
ON lore_character_references(character_id)
WHERE character_id IS NOT NULL;

-- Backfill: existing UUID-valued related_characters become canonical references only if
-- the character exists in the same project. Non-UUID or missing/cross-project values are
-- moved into unresolved_character_refs so raw strings are not treated as canonical truth.
WITH expanded AS (
    SELECT
        l.id AS lore_id,
        l.project_id,
        elem.value #>> '{}' AS source_text,
        elem.ordinality
    FROM lore_entries l
    CROSS JOIN LATERAL jsonb_array_elements(COALESCE(l.related_characters, '[]'::jsonb)) WITH ORDINALITY AS elem(value, ordinality)
), classified AS (
    SELECT
        e.*,
        c.id AS character_id,
        c.name AS character_name
    FROM expanded e
    LEFT JOIN characters c
      ON e.source_text ~* '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
     AND c.id = e.source_text::uuid
     AND c.project_id = e.project_id
), aggregated AS (
    SELECT
        lore_id,
        COALESCE(
            jsonb_agg(character_id::text ORDER BY ordinality) FILTER (WHERE character_id IS NOT NULL),
            '[]'::jsonb
        ) AS canonical_ids,
        COALESCE(
            jsonb_agg(jsonb_build_object(
                'status', 'resolved',
                'source_text', source_text,
                'character_id', character_id::text,
                'character_name', character_name,
                'confidence', 1.0,
                'resolution_method', 'migration_existing_uuid',
                'provenance', jsonb_build_object('migration', 'V38_character_reference_resolution')
            ) ORDER BY ordinality) FILTER (WHERE character_id IS NOT NULL),
            '[]'::jsonb
        ) AS resolved_refs,
        COALESCE(
            jsonb_agg(jsonb_build_object(
                'status', 'unresolved',
                'source_text', source_text,
                'source_payload', source_text,
                'reason', CASE
                    WHEN source_text ~* '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
                        THEN 'character_id_not_found_or_cross_project'
                    ELSE 'legacy_raw_text_reference'
                END,
                'message', '迁移发现旧 related_characters 值无法确定绑定到当前项目角色，需要用户确认。',
                'candidates', '[]'::jsonb,
                'recommended_actions', jsonb_build_array('bind_existing', 'create_character', 'keep_text_only', 'ignore'),
                'provenance', jsonb_build_object('migration', 'V38_character_reference_resolution')
            ) ORDER BY ordinality) FILTER (WHERE character_id IS NULL AND source_text <> ''),
            '[]'::jsonb
        ) AS unresolved_refs
    FROM classified
    GROUP BY lore_id
)
UPDATE lore_entries l
SET related_characters = a.canonical_ids,
    related_character_refs = a.resolved_refs,
    unresolved_character_refs = a.unresolved_refs
FROM aggregated a
WHERE l.id = a.lore_id;

INSERT INTO lore_character_references (
    lore_id,
    project_id,
    character_id,
    source_text,
    confidence,
    resolution_method,
    status,
    provenance
)
SELECT
    l.id,
    l.project_id,
    (ref->>'character_id')::uuid,
    ref->>'source_text',
    COALESCE((ref->>'confidence')::numeric, 1.0),
    COALESCE(ref->>'resolution_method', 'migration_existing_uuid'),
    'resolved',
    ref
FROM lore_entries l
CROSS JOIN LATERAL jsonb_array_elements(COALESCE(l.related_character_refs, '[]'::jsonb)) AS ref
WHERE ref->>'character_id' IS NOT NULL
ON CONFLICT DO NOTHING;

INSERT INTO lore_character_references (
    lore_id,
    project_id,
    source_text,
    confidence,
    resolution_method,
    status,
    provenance
)
SELECT
    l.id,
    l.project_id,
    ref->>'source_text',
    0,
    COALESCE(ref->>'reason', 'legacy_unresolved'),
    COALESCE(ref->>'status', 'unresolved'),
    ref
FROM lore_entries l
CROSS JOIN LATERAL jsonb_array_elements(COALESCE(l.unresolved_character_refs, '[]'::jsonb)) AS ref
WHERE COALESCE(ref->>'source_text', '') <> ''
ON CONFLICT DO NOTHING;
