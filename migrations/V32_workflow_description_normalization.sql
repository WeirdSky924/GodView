-- V32: normalize workflow descriptions that still reference legacy parallel wording

UPDATE workflow_definitions
SET description = REPLACE(description, '并行准备', '并行执行')
WHERE description LIKE '%并行准备%';

UPDATE workflow_definitions
SET nodes = (
    SELECT jsonb_agg(
        CASE
            WHEN node_entry.node ? 'description' AND node_entry.node->>'description' LIKE '%并行准备%'
                THEN jsonb_set(
                    node_entry.node,
                    '{description}',
                    to_jsonb(REPLACE(node_entry.node->>'description', '并行准备', '并行执行')),
                    true
                )
            ELSE node_entry.node
        END
        ORDER BY node_entry.ord
    )
    FROM jsonb_array_elements(COALESCE(workflow_definitions.nodes, '[]'::jsonb)) WITH ORDINALITY AS node_entry(node, ord)
)
WHERE EXISTS (
    SELECT 1
    FROM jsonb_array_elements(COALESCE(workflow_definitions.nodes, '[]'::jsonb)) AS node(node)
    WHERE node.node ? 'description'
      AND node.node->>'description' LIKE '%并行准备%'
);
