#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
运行数据库迁移脚本 - V14 章节大纲和小说质量优化相关表
GodView v9 需求实现
"""
import asyncio
import sys
import os

# 设置控制台编码
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import asyncpg
from dotenv import load_dotenv

load_dotenv()


async def run_migration():
    """运行 V14_chapter_outlines.sql 迁移"""
    # 获取数据库连接 URL
    database_url = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:password@127.0.0.1:5432/godview")

    # 转换 URL 格式（去掉 +asyncpg 部分）
    if "+asyncpg" in database_url:
        database_url = database_url.replace("+asyncpg", "")

    print("Connecting to database...")
    print(f"URL: {database_url.split('@')[1] if '@' in database_url else database_url}")

    # 连接数据库
    conn = await asyncpg.connect(database_url)

    try:
        # 读取 SQL 文件
        sql_file = os.path.join(os.path.dirname(__file__), 'migrations', 'V14_chapter_outlines.sql')
        print(f"Reading SQL file: {sql_file}")

        with open(sql_file, 'r', encoding='utf-8') as f:
            sql_content = f.read()

        # 检查 pgvector 扩展是否存在
        print("Checking pgvector extension...")
        pgvector_available = False
        try:
            await conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
            pgvector_available = True
            print("  pgvector extension enabled")
        except Exception as e:
            print(f"  Warning: pgvector not available: {e}")
            print("  Note: memory_entries will use JSONB instead of vector type")

        # 读取并修改 SQL 内容（处理 pgvector 不可用的情况）
        if not pgvector_available:
            # 将 VECTOR(384) 替换为 JSONB
            sql_content = sql_content.replace('embedding VECTOR(384)', 'embedding JSONB DEFAULT \'[]\'')

        # 执行 SQL（分批执行，跳过注释）
        print("Executing migration...")

        # 分割 SQL 语句
        statements = []
        current_stmt = []
        in_memory_entries = False

        for line in sql_content.split('\n'):
            stripped = line.strip()

            # 跳过空行和注释
            if not stripped or stripped.startswith('--'):
                continue

            # 检测 memory_entries 表定义开始
            if 'CREATE TABLE IF NOT EXISTS memory_entries' in stripped:
                in_memory_entries = True

            current_stmt.append(line)

            # 检测表定义结束（遇到分号且是CREATE TABLE语句的结束）
            if stripped.endswith(');') and current_stmt:
                # 检查是否在 memory_entries 表内
                full_stmt = '\n'.join(current_stmt)
                if in_memory_entries and 'CREATE TABLE IF NOT EXISTS memory_entries' in full_stmt:
                    # 这是 memory_entries 表的结束
                    statements.append(full_stmt)
                    current_stmt = []
                    in_memory_entries = False
                    continue

                if stripped.endswith(';'):
                    statements.append('\n'.join(current_stmt))
                    current_stmt = []

        # 执行每个语句
        success_count = 0
        for i, stmt in enumerate(statements):
            if stmt.strip():
                try:
                    await conn.execute(stmt)
                    success_count += 1
                except Exception as e:
                    # 忽略已存在的错误
                    if 'already exists' in str(e).lower() or '已存在' in str(e):
                        print(f"  语句 {i+1}: 已存在，跳过")
                    else:
                        print(f"  语句 {i+1} 错误: {e}")

        print(f"  Executed {success_count} statements")

        # 验证创建的表
        tables = await conn.fetch("""
            SELECT tablename
            FROM pg_tables
            WHERE schemaname = 'public'
            AND tablename IN (
                'chapter_outlines', 'golden_three_checks', 'satisfaction_analyses',
                'villains', 'conflicts', 'volume_outlines', 'character_lifecycles',
                'foreshadowings', 'memory_entries'
            )
            ORDER BY tablename
        """)

        print(f"\n[OK] Migration completed! Created/verified {len(tables)} tables:")
        for table in tables:
            print(f"  - {table['tablename']}")

        # 显示索引
        indexes = await conn.fetch("""
            SELECT indexname
            FROM pg_indexes
            WHERE schemaname = 'public'
            AND tablename IN (
                'chapter_outlines', 'golden_three_checks', 'satisfaction_analyses',
                'villains', 'conflicts', 'volume_outlines', 'character_lifecycles',
                'foreshadowings', 'memory_entries'
            )
            ORDER BY indexname
        """)
        print(f"\nCreated indexes ({len(indexes)}):")
        for idx in indexes[:15]:  # 只显示前15个
            print(f"  - {idx['indexname']}")
        if len(indexes) > 15:
            print(f"  ... and {len(indexes) - 15} more indexes")

        print("\n[SUCCESS] V14 数据库迁移完成!")

    except Exception as e:
        print(f"[ERROR] Migration failed: {e}")
        import traceback
        traceback.print_exc()
        raise
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(run_migration())
