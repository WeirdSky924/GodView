-- V9 Character Fields Migration
-- Adds missing character fields that are defined in model but not in database

-- Add debut_scene column (for detailed debut description)
ALTER TABLE characters ADD COLUMN IF NOT EXISTS debut_scene TEXT;

-- Add exit_reason column (for death/leave reason)
ALTER TABLE characters ADD COLUMN IF NOT EXISTS exit_reason TEXT;

-- Add relationships column (array of relationship types)
ALTER TABLE characters ADD COLUMN IF NOT EXISTS relationships JSONB DEFAULT '[]';

-- Create indexes for new columns
CREATE INDEX IF NOT EXISTS idx_characters_debut_chapter ON characters(debut_chapter);
CREATE INDEX IF NOT EXISTS idx_characters_exit_chapter ON characters(exit_chapter);
