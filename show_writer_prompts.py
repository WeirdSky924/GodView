"""
获取作家相关的所有 Prompt 内容
"""
import asyncio
import asyncpg
import os
from dotenv import load_dotenv

load_dotenv()


async def get_writer_prompt():
    url = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:password@127.0.0.1:5432/godview")
    if "+asyncpg" in url:
        url = url.replace("+asyncpg", "")
    conn = await asyncpg.connect(url)

    # 获取作家相关的所有 prompts
    rows = await conn.fetch("""
        SELECT id, name, category, content FROM prompt_templates
        WHERE id IN ('role_writer', 'function_writing', 'originality_guidelines', 'base_json_output')
        ORDER BY priority DESC
    """)

    for row in rows:
        print("=" * 70)
        print(f"ID: {row['id']}")
        print(f"Name: {row['name']}")
        print(f"Category: {row['category']}")
        print("=" * 70)
        print(row["content"])
        print("\n")

    await conn.close()


if __name__ == "__main__":
    asyncio.run(get_writer_prompt())
