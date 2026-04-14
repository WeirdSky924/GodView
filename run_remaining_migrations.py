"""
执行剩余的迁移文件 V19-V21
"""
import asyncio
import asyncpg
import os
from dotenv import load_dotenv

load_dotenv()


async def run_migrations():
    url = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:password@127.0.0.1:5432/godview")
    if "+asyncpg" in url:
        url = url.replace("+asyncpg", "")
    conn = await asyncpg.connect(url)

    migrations_dir = os.path.join(os.path.dirname(__file__), "migrations")

    # 要执行的迁移文件
    migration_files = [
        "V19_missing_prompts.sql",
        "V20_fix_prompt_bindings.sql",
        "V21_prompt_skill_guidance.sql",
    ]

    try:
        for filename in migration_files:
            filepath = os.path.join(migrations_dir, filename)

            if not os.path.exists(filepath):
                print(f"[SKIP] File not found: {filename}")
                continue

            print(f"\n[RUNNING] {filename}")

            with open(filepath, 'r', encoding='utf-8') as f:
                sql_content = f.read()

            try:
                await conn.execute(sql_content)
                print(f"[SUCCESS] {filename}")
            except Exception as e:
                error_msg = str(e).lower()
                if "already exists" in error_msg or "duplicate" in error_msg:
                    print(f"[SKIP] {filename} - Already exists")
                else:
                    print(f"[ERROR] {filename}: {str(e)[:300]}")

        # 验证结果
        print(f"\n{'='*60}")
        print("Final verification:")
        print(f"{'='*60}")

        prompt_count = await conn.fetchval("SELECT COUNT(*) FROM prompt_templates")
        print(f"prompt_templates: {prompt_count} records")

        skill_count = await conn.fetchval("SELECT COUNT(*) FROM skills")
        print(f"skills: {skill_count} records")

        binding_count = await conn.fetchval("SELECT COUNT(*) FROM agent_prompt_bindings")
        print(f"agent_prompt_bindings: {binding_count} records")

        assignment_count = await conn.fetchval("SELECT COUNT(*) FROM skill_assignments")
        print(f"skill_assignments: {assignment_count} records")

        # 显示 prompt_templates 中的关键记录
        print("\n--- Key prompt_templates ---")
        key_prompts = await conn.fetch("""
            SELECT id, name, category FROM prompt_templates
            WHERE id LIKE 'function_%' OR id LIKE 'role_%'
            ORDER BY id
        """)
        for p in key_prompts[:15]:
            print(f"  {p['id']}: {p['name'][:40]}")

        print(f"\n[SUCCESS] Migration completed!")

    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(run_migrations())
