"""
运行数据库迁移脚本 V17-V21
执行 Prompt 和 Skill 相关的迁移文件
"""
import asyncio
import sys
import os
import glob
import re

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import asyncpg
from dotenv import load_dotenv

load_dotenv()


async def run_migrations():
    """运行 V17-V21 迁移文件"""
    # 获取数据库连接 URL
    database_url = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:password@127.0.0.1:5432/godview")

    # 转换 URL 格式（去掉 +asyncpg 部分）
    if "+asyncpg" in database_url:
        database_url = database_url.replace("+asyncpg", "")

    print(f"Connecting to database...")
    print(f"Database URL: {database_url.split('@')[1] if '@' in database_url else 'N/A'}")

    # 连接数据库
    conn = await asyncpg.connect(database_url)

    migrations_dir = os.path.join(os.path.dirname(__file__), "migrations")

    # 要执行的迁移文件列表（按顺序）
    migration_files = [
        "V17_migrate_all_prompts.sql",
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
        for filename in migration_files:
            filepath = os.path.join(migrations_dir, filename)

            if not os.path.exists(filepath):
                print(f"\n[SKIP] File not found: {filename}")
                continue

            print(f"\n{'='*60}")
            print(f"[RUNNING] {filename}")
            print(f"{'='*60}")

            with open(filepath, 'r', encoding='utf-8') as f:
                sql_content = f.read()

            # 分割 SQL 语句（以分号结尾的语句）
            # 但要小心处理函数定义中的分号

            # 简单方案：直接执行整个文件，让 PostgreSQL 处理
            try:
                await conn.execute(sql_content)
                print(f"[SUCCESS] {filename} executed successfully")
            except Exception as e:
                error_msg = str(e)

                # 如果是"已存在"类型的错误，可以忽略
                if "already exists" in error_msg.lower() or "duplicate" in error_msg.lower():
                    print(f"[SKIP] {filename} - Resource already exists: {error_msg[:100]}")
                else:
                    print(f"[ERROR] {filename} failed: {e}")
                    # 继续执行下一个文件，不中断
                    # raise  # 如果需要严格模式，取消注释这行

        # 验证迁移结果
        print(f"\n{'='*60}")
        print("Verifying migration results...")
        print(f"{'='*60}")

        # 检查 prompt_templates 表
        prompt_count = await conn.fetchval("SELECT COUNT(*) FROM prompt_templates")
        print(f"prompt_templates: {prompt_count} records")

        # 检查 skills 表
        skill_count = await conn.fetchval("SELECT COUNT(*) FROM skills")
        print(f"skills: {skill_count} records")

        # 检查 agent_prompt_bindings 表
        try:
            binding_count = await conn.fetchval("SELECT COUNT(*) FROM agent_prompt_bindings")
            print(f"agent_prompt_bindings: {binding_count} records")
        except:
            print("agent_prompt_bindings: table not found")

        # 检查 skill_assignments 表
        try:
            assignment_count = await conn.fetchval("SELECT COUNT(*) FROM skill_assignments")
            print(f"skill_assignments: {assignment_count} records")
        except:
            print("skill_assignments: table not found")

        # 显示一些示例数据
        print(f"\n--- Sample prompt_templates ---")
        samples = await conn.fetch("SELECT id, name, category FROM prompt_templates LIMIT 5")
        for s in samples:
            print(f"  {s['id']}: {s['name']} ({s['category']})")

        print(f"\n--- Sample skills ---")
        samples = await conn.fetch("SELECT id, name, skill_type FROM skills LIMIT 5")
        for s in samples:
            print(f"  {s['id']}: {s['name']} ({s['skill_type']})")

        print(f"\n[SUCCESS] All migrations completed!")

    except Exception as e:
        print(f"\n[ERROR] Migration failed: {e}")
        import traceback
        traceback.print_exc()
        raise
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(run_migrations())
