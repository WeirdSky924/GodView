ALTER TABLE writing_rules
ADD COLUMN IF NOT EXISTS application_mode VARCHAR(50);

UPDATE writing_rules
SET application_mode = CASE severity
    WHEN 'required' THEN 'always_postcheck'
    WHEN 'strong' THEN 'retrieve_postcheck'
    WHEN 'recommended' THEN 'retrieve'
    WHEN 'optional' THEN 'retrieve_on_match'
    WHEN 'info' THEN 'reference'
    ELSE 'retrieve'
END
WHERE application_mode IS NULL OR application_mode = '';

ALTER TABLE writing_rules
ALTER COLUMN application_mode SET DEFAULT 'retrieve';
