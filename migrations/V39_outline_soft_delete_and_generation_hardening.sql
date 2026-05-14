-- V39 Outline soft delete and generation hardening
-- Adds soft-delete support for chapter outline versions so stale deleted outlines
-- cannot be reused by Assistant Context or formal workflow selection.

ALTER TABLE chapter_outlines
    ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMP WITH TIME ZONE;

CREATE INDEX IF NOT EXISTS idx_chapter_outlines_active_project_chapter
    ON chapter_outlines(project_id, chapter_number)
    WHERE deleted_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_chapter_outlines_deleted_at
    ON chapter_outlines(deleted_at);
