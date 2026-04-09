"""
添加 personality 列到 characters 表
运行: python scripts/add_personality_column.py
"""

import asyncio
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import settings
from app.database.postgres import PostgresDatabase


async def add_personality_column():
    """添加 personality 列"""
    db = PostgresDatabase(settings.database_url)
    await db.connect()

    try:
        # 检查列是否存在
        check_query = """
        SELECT column_name FROM information_schema.columns
        WHERE table_name = 'characters' AND column_name = 'personality'
        """
        result = await db.execute_query(check_query)

        if result:
            print("✓ personality 列已存在")
            return

        # 添加 personality 列
        alter_query = """
        ALTER TABLE characters ADD COLUMN personality TEXT
        """
        await db.execute_write(alter_query, {})
        print("✓ 已添加 personality 列到 characters 表")

    except Exception as e:
        print(f"✗ 添加列失败: {e}")
        raise
    finally:
        await db.disconnect()


if __name__ == "__main__":
    asyncio.run(add_personality_column())
