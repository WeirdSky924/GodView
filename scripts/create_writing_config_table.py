"""
创建 project_writing_configs 表的脚本
"""

import asyncio
import sys
import os

# 添加项目根目录到 path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text


async def create_tables():
    from app.config import settings

    if not settings.database_url:
        print("[ERROR] Database URL not configured")
        return

    engine = create_async_engine(settings.database_url)

    statements = [
        """
        CREATE TABLE IF NOT EXISTS project_writing_configs (
            id VARCHAR(100) PRIMARY KEY,
            project_id UUID NOT NULL UNIQUE REFERENCES projects(id) ON DELETE CASCADE,
            enabled_rule_ids JSONB DEFAULT '[]',
            enabled_rule_set_ids JSONB DEFAULT '[]',
            rule_overrides JSONB DEFAULT '{}',
            rule_priorities JSONB DEFAULT '{}',
            default_severity VARCHAR(20) DEFAULT 'recommended',
            apply_to_chapters BOOLEAN DEFAULT TRUE,
            apply_to_characters BOOLEAN DEFAULT TRUE,
            apply_to_descriptions BOOLEAN DEFAULT TRUE,
            apply_to_narration BOOLEAN DEFAULT TRUE,
            is_active BOOLEAN DEFAULT TRUE,
            version VARCHAR(20) DEFAULT '1.0.0',
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        )
        """,
        "CREATE INDEX IF NOT EXISTS idx_project_writing_configs_project_id ON project_writing_configs(project_id)",
        "CREATE INDEX IF NOT EXISTS idx_project_writing_configs_is_active ON project_writing_configs(is_active)",
        """
        CREATE TABLE IF NOT EXISTS writing_rules (
            id VARCHAR(100) PRIMARY KEY,
            name VARCHAR(200) NOT NULL,
            description TEXT,
            category VARCHAR(50) NOT NULL,
            severity VARCHAR(20) DEFAULT 'recommended',
            tags JSONB DEFAULT '[]',
            content TEXT NOT NULL,
            examples JSONB DEFAULT '[]',
            counter_examples JSONB DEFAULT NULL,
            conditions JSONB DEFAULT '[]',
            exceptions JSONB DEFAULT NULL,
            is_system BOOLEAN DEFAULT FALSE,
            version VARCHAR(20) DEFAULT '1.0.0',
            author VARCHAR(200),
            source VARCHAR(500),
            usage_count INTEGER DEFAULT 0,
            last_used_at TIMESTAMP WITH TIME ZONE,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        )
        """,
        "CREATE INDEX IF NOT EXISTS idx_writing_rules_category ON writing_rules(category)",
        "CREATE INDEX IF NOT EXISTS idx_writing_rules_severity ON writing_rules(severity)",
        "CREATE INDEX IF NOT EXISTS idx_writing_rules_is_system ON writing_rules(is_system)",
        "CREATE INDEX IF NOT EXISTS idx_writing_rules_tags ON writing_rules USING GIN(tags)",
        """
        CREATE TABLE IF NOT EXISTS writing_rule_sets (
            id VARCHAR(100) PRIMARY KEY,
            name VARCHAR(200) NOT NULL,
            description TEXT,
            rule_ids JSONB DEFAULT '[]',
            rule_overrides JSONB DEFAULT '{}',
            category VARCHAR(50) NOT NULL,
            tags JSONB DEFAULT '[]',
            target_genres JSONB DEFAULT '[]',
            is_system BOOLEAN DEFAULT FALSE,
            version VARCHAR(20) DEFAULT '1.0.0',
            author VARCHAR(200),
            usage_count INTEGER DEFAULT 0,
            last_used_at TIMESTAMP WITH TIME ZONE,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        )
        """,
        "CREATE INDEX IF NOT EXISTS idx_writing_rule_sets_category ON writing_rule_sets(category)",
        "CREATE INDEX IF NOT EXISTS idx_writing_rule_sets_is_system ON writing_rule_sets(is_system)",
        "CREATE INDEX IF NOT EXISTS idx_writing_rule_sets_tags ON writing_rule_sets USING GIN(tags)",
    ]

    async with engine.begin() as conn:
        for stmt in statements:
            await conn.execute(text(stmt))

    print("[OK] Database tables created successfully!")
    print("  - project_writing_configs")
    print("  - writing_rules")
    print("  - writing_rule_sets")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(create_tables())
