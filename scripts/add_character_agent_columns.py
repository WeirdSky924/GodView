"""
Add agent columns to characters table
"""

import asyncio
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text


async def migrate():
    from app.config import settings

    if not settings.database_url:
        print("[ERROR] Database URL not configured")
        return

    engine = create_async_engine(settings.database_url)

    statements = [
        "ALTER TABLE characters ADD COLUMN IF NOT EXISTS has_agent BOOLEAN DEFAULT FALSE",
        "ALTER TABLE characters ADD COLUMN IF NOT EXISTS agent_enabled BOOLEAN DEFAULT TRUE",
        "ALTER TABLE characters ADD COLUMN IF NOT EXISTS agent_goals JSONB DEFAULT '[]'",
        "ALTER TABLE characters ADD COLUMN IF NOT EXISTS agent_memory JSONB DEFAULT '[]'",
    ]

    async with engine.begin() as conn:
        for stmt in statements:
            try:
                await conn.execute(text(stmt))
                print(f"[OK] {stmt.split('ADD COLUMN IF NOT EXISTS')[1].split()[0] if 'ADD COLUMN IF NOT EXISTS' in stmt else stmt[:50]}")
            except Exception as e:
                print(f"[WARN] {stmt[:50]}... - {e}")

    print("\n[OK] Migration completed!")
    print("  Added: has_agent, agent_enabled, agent_goals, agent_memory")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(migrate())
