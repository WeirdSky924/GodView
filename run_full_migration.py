"""
运行完整的数据库迁移脚本
按正确顺序执行所有迁移文件
"""
import asyncio
import sys
import os
import asyncpg
from dotenv import load_dotenv

load_dotenv()

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


async def run_migrations():
    """运行迁移"""
    database_url = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:password@127.0.0.1:5432/godview")
    if "+asyncpg" in database_url:
        database_url = database_url.replace("+asyncpg", "")

    print(f"Connecting to database...")
    conn = await asyncpg.connect(database_url)

    migrations_dir = os.path.join(os.path.dirname(__file__), "migrations")

    # 按依赖顺序执行的迁移文件
    migration_files = [
        # 基础表结构
        "V15_skill_dynamic_loading.sql",  # 添加 load_mode 列等
        "V16_prompt_and_skill_reorganization.sql",  # 创建 prompt_templates 表
        # 数据迁移
        "V17_migrate_all_prompts.sql",    # 迁移 prompts
        "V18_missing_skills_part1_general.sql",
        "V18_missing_skills_part2_writing.sql",
        "V18_missing_skills_part3_plotting.sql",
        "V18_missing_skills_part4_hooks.sql",
        "V18_missing_skills_part5_quality.sql",
        "V18_missing_skills_part6_7_final.sql",
        "V19_missing_prompts.sql",
        "V20_fix_prompt_bindings.sql",
        "V21_prompt_skill_guidance.sql",
    ]

    try:
        # 先检查当前表结构
        print("\n--- Current database state ---")
        tables = await conn.fetch("""
            SELECT table_name FROM information_schema.tables
            WHERE table_schema = 'public'
            ORDER BY table_name
        """)
        print(f"Existing tables: {[t['table_name'] for t in tables]}")

        # 检查 skills 表结构
        skills_columns = await conn.fetch("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'skills' ORDER BY ordinal_position
        """)
        print(f"Skills columns: {[c['column_name'] for c in skills_columns]}")

        for filename in migration_files:
            filepath = os.path.join(migrations_dir, filename)

            if not os.path.exists(filepath):
                print(f"\n[SKIP] File not found: {filename}")
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
                    print(f"[ERROR] {filename}: {str(e)[:200]}")
                    # 继续执行下一个

        # 验证结果
        print(f"\n{'='*60}")
        print("Final verification:")
        print(f"{'='*60}")

        try:
            prompt_count = await conn.fetchval("SELECT COUNT(*) FROM prompt_templates")
            print(f"prompt_templates: {prompt_count} records")
        except Exception as e:
            print(f"prompt_templates: Error - {e}")

        try:
            skill_count = await conn.fetchval("SELECT COUNT(*) FROM skills")
            print(f"skills: {skill_count} records")
        except Exception as e:
            print(f"skills: Error - {e}")

        try:
            binding_count = await conn.fetchval("SELECT COUNT(*) FROM agent_prompt_bindings")
            print(f"agent_prompt_bindings: {binding_count} records")
        except Exception as e:
            print(f"agent_prompt_bindings: Not found")

        try:
            assignment_count = await conn.fetchval("SELECT COUNT(*) FROM skill_assignments")
            print(f"skill_assignments: {assignment_count} records")
        except Exception as e:
            print(f"skill_assignments: Not found")

        print(f"\n[SUCCESS] Migration process completed!")

    except Exception as e:
        print(f"\n[FATAL ERROR] {e}")
        import traceback
        traceback.print_exc()
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(run_migrations())
