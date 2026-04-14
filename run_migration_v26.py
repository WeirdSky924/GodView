#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
运行数据库迁移脚本 - V26 记忆系统增强
语义检索、上下文感知选择、使用追踪、衰减机制
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
    """运行 V26_memory_enhancement.sql 迁移"""
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
        # 检查 pgvector 扩展是否可用
        print("Checking pgvector extension...")
        pgvector_available = False
        try:
            await conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
            pgvector_available = True
            print("  pgvector extension enabled ✓")
        except Exception as e:
            print(f"  Warning: pgvector not available: {e}")
            print("  Note: vector columns will use JSONB as fallback")

        # 读取 SQL 文件
        sql_file = os.path.join(os.path.dirname(__file__), 'migrations', 'V26_memory_enhancement.sql')
        print(f"Reading SQL file: {sql_file}")

        with open(sql_file, 'r', encoding='utf-8') as f:
            sql_content = f.read()

        # 执行迁移
        print("Executing migration...")

        # 分割并执行语句
        statements = []
        current_stmt = []

        for line in sql_content.split('\n'):
            stripped = line.strip()

            # 跳过空行和注释
            if not stripped or stripped.startswith('--'):
                continue

            current_stmt.append(line)

            # 检测语句结束
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
                    error_str = str(e).lower()
                    if 'already exists' in error_str or '已存在' in error_str:
                        print(f"  语句 {i+1}: 已存在，跳过")
                    elif 'duplicate key' in error_str:
                        print(f"  语句 {i+1}: 数据已存在，跳过")
                    else:
                        print(f"  语句 {i+1} 错误: {e}")

        print(f"  Executed {success_count} statements")

        # 如果 pgvector 可用，添加向量列和索引
        if pgvector_available:
            print("Adding vector column (pgvector available)...")
            try:
                # 检查是否已经有 vector 列
                has_vector = await conn.fetchval("""
                    SELECT EXISTS (
                        SELECT 1 FROM information_schema.columns
                        WHERE table_name = 'memory_embeddings'
                        AND column_name = 'embedding_vec'
                    )
                """)

                if not has_vector:
                    # 添加 vector 类型的列
                    await conn.execute("""
                        ALTER TABLE memory_embeddings
                        ADD COLUMN embedding_vec vector(1536)
                    """)
                    print("  Added embedding_vec column (vector(1536))")

                    # 创建向量索引
                    await conn.execute("""
                        CREATE INDEX IF NOT EXISTS idx_memory_embeddings_vector
                        ON memory_embeddings
                        USING ivfflat (embedding_vec vector_cosine_ops)
                        WITH (lists = 100)
                    """)
                    print("  Created vector index")
                else:
                    print("  Vector column already exists")

            except Exception as e:
                print(f"  Warning: Could not add vector column: {e}")

        # 验证创建的表
        tables = await conn.fetch("""
            SELECT tablename
            FROM pg_tables
            WHERE schemaname = 'public'
            AND tablename IN (
                'memory_embeddings', 'memory_usage_logs',
                'memory_context_configs', 'memory_decay_rules'
            )
            ORDER BY tablename
        """)

        print(f"\n[OK] Migration completed! Created/verified {len(tables)} tables:")
        for table in tables:
            print(f"  - {table['tablename']}")

        # 验证配置数据
        configs = await conn.fetch("""
            SELECT id, name FROM memory_context_configs ORDER BY id
        """)
        print(f"\nMemory context configs ({len(configs)}):")
        for config in configs:
            print(f"  - {config['id']}: {config['name']}")

        # 验证衰减规则
        rules = await conn.fetch("""
            SELECT id, name FROM memory_decay_rules ORDER BY id
        """)
        print(f"\nMemory decay rules ({len(rules)}):")
        for rule in rules:
            print(f"  - {rule['id']}: {rule['name']}")

        print("\n[SUCCESS] V26 记忆系统增强迁移完成!")

    except Exception as e:
        print(f"[ERROR] Migration failed: {e}")
        import traceback
        traceback.print_exc()
        raise
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(run_migration())
