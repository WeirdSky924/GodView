"""
修复数据库 Schema - 添加缺失的表和列
"""
import asyncio
import asyncpg
import os
from dotenv import load_dotenv

load_dotenv()


async def fix_schema():
    url = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:password@127.0.0.1:5432/godview")
    if "+asyncpg" in url:
        url = url.replace("+asyncpg", "")
    conn = await asyncpg.connect(url)

    try:
        # 1. 创建 agent_prompt_bindings 表
        print("1. Creating agent_prompt_bindings table...")
        try:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS agent_prompt_bindings (
                    id VARCHAR(100) PRIMARY KEY,
                    agent_type VARCHAR(50) NOT NULL,
                    prompt_id VARCHAR(100) NOT NULL REFERENCES prompt_templates(id),
                    binding_type VARCHAR(20),
                    priority INTEGER DEFAULT 50,
                    is_required BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(agent_type, prompt_id)
                )
            """)
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_agent_prompt_bindings_agent ON agent_prompt_bindings(agent_type)")
            print("   Done!")
        except Exception as e:
            print(f"   Error: {e}")

        # 2. 添加 skills 表缺失的列
        print("2. Adding columns to skills table...")

        # 检查现有列
        cols = await conn.fetch("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'skills' AND table_schema = 'public'
        """)
        existing = [c["column_name"] for c in cols]
        print(f"   Existing columns: {len(existing)}")

        if "load_mode" not in existing:
            try:
                await conn.execute("ALTER TABLE skills ADD COLUMN load_mode VARCHAR(50) DEFAULT 'on_demand'")
                print("   Added load_mode")
            except Exception as e:
                print(f"   load_mode error: {e}")

        if "trigger_keywords" not in existing:
            try:
                await conn.execute("ALTER TABLE skills ADD COLUMN trigger_keywords JSONB")
                print("   Added trigger_keywords")
            except Exception as e:
                print(f"   trigger_keywords error: {e}")

        if "trigger_scenes" not in existing:
            try:
                await conn.execute("ALTER TABLE skills ADD COLUMN trigger_scenes JSONB")
                print("   Added trigger_scenes")
            except Exception as e:
                print(f"   trigger_scenes error: {e}")

        # 设置默认值
        try:
            await conn.execute("UPDATE skills SET trigger_keywords = '[]'::jsonb WHERE trigger_keywords IS NULL")
            await conn.execute("UPDATE skills SET trigger_scenes = '[]'::jsonb WHERE trigger_scenes IS NULL")
            print("   Set default values for JSONB columns")
        except Exception as e:
            print(f"   Default values error: {e}")

        # 3. 验证结果
        print("\n3. Verification:")
        tables = await conn.fetch("""
            SELECT table_name FROM information_schema.tables
            WHERE table_schema = 'public' AND table_name IN ('agent_prompt_bindings', 'prompt_templates', 'skills')
        """)
        print(f"   Tables: {[t['table_name'] for t in tables]}")

        skills_cols = await conn.fetch("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'skills' AND column_name IN ('load_mode', 'trigger_keywords', 'trigger_scenes')
        """)
        print(f"   Skills new columns: {[c['column_name'] for c in skills_cols]}")

        print("\n[SUCCESS] Schema fix completed!")

    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(fix_schema())
