"""
运行数据库迁移脚本 - Agent Skill 系统
"""
import asyncio
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import asyncpg
from dotenv import load_dotenv

load_dotenv()


async def run_migration():
    """运行 V10_skill_system.sql 迁移"""
    # 获取数据库连接 URL
    database_url = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:password@127.0.0.1:5432/godview")

    # 转换 URL 格式（去掉 +asyncpg 部分）
    if "+asyncpg" in database_url:
        database_url = database_url.replace("+asyncpg", "")

    print("Connecting to database...")

    # 连接数据库
    conn = await asyncpg.connect(database_url)

    try:
        # 检查现有的 skills 表结构
        existing_skills = await conn.fetch("""
            SELECT table_name FROM information_schema.tables
            WHERE table_schema = 'public' AND table_name = 'skills'
        """)

        if existing_skills:
            # 检查现有列
            columns = await conn.fetch("""
                SELECT column_name FROM information_schema.columns
                WHERE table_name = 'skills' ORDER BY ordinal_position
            """)
            existing_columns = [c['column_name'] for c in columns]
            print(f"Existing skills table columns: {existing_columns}")

            # 检查是否是旧的 skills 表（有 character_id 列）
            if 'character_id' in existing_columns:
                print("Found old skills table (for character skills). Renaming to character_skills...")
                await conn.execute("ALTER TABLE IF EXISTS character_skills RENAME TO character_skills_old")
                await conn.execute("ALTER TABLE skills RENAME TO character_skills")
                if existing_columns:
                    await conn.execute("DROP TABLE IF EXISTS character_skills_old")
                print("Renamed old skills table to character_skills")
                existing_skills = []

        if not existing_skills:
            print("Creating new skills table...")
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS skills (
                    id VARCHAR(100) PRIMARY KEY,
                    name VARCHAR(200) NOT NULL,
                    description TEXT DEFAULT '',

                    -- 类型和分类
                    skill_type VARCHAR(50) NOT NULL,
                    category VARCHAR(50) DEFAULT 'general',
                    tags JSONB DEFAULT '[]',

                    -- 适用范围
                    applicable_agent_types JSONB DEFAULT '[]',

                    -- 内容定义
                    prompt_template TEXT,
                    prompt_template_id VARCHAR(100),
                    function_code TEXT,
                    workflow_steps JSONB,
                    knowledge_content TEXT,

                    -- 参数和输出
                    parameters JSONB DEFAULT '[]',
                    output_spec JSONB DEFAULT '[]',

                    -- 执行配置
                    temperature FLOAT DEFAULT 0.7,
                    max_tokens INTEGER,
                    timeout INTEGER DEFAULT 60,
                    retry_count INTEGER DEFAULT 0,

                    -- 优先级和状态
                    priority INTEGER DEFAULT 50,
                    status VARCHAR(50) DEFAULT 'active',
                    is_system BOOLEAN DEFAULT FALSE,
                    is_enabled BOOLEAN DEFAULT TRUE,
                    is_composable BOOLEAN DEFAULT TRUE,

                    -- 创建来源
                    creator_project_id UUID,
                    creator_agent_id VARCHAR(100),
                    creator_user_id VARCHAR(100),

                    -- 元数据
                    version VARCHAR(20) DEFAULT '1.0.0',
                    author VARCHAR(100) DEFAULT 'system',
                    examples JSONB DEFAULT '[]',

                    -- 使用统计
                    usage_count INTEGER DEFAULT 0,
                    last_used_at TIMESTAMP WITH TIME ZONE,

                    -- 时间戳
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                )
            """)
            print("Skills table created.")

        # 创建索引
        print("Creating indexes...")
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_skills_type ON skills(skill_type)",
            "CREATE INDEX IF NOT EXISTS idx_skills_category ON skills(category)",
            "CREATE INDEX IF NOT EXISTS idx_skills_status ON skills(status)",
            "CREATE INDEX IF NOT EXISTS idx_skills_system ON skills(is_system)",
            "CREATE INDEX IF NOT EXISTS idx_skills_applicable ON skills USING GIN(applicable_agent_types)",
            "CREATE INDEX IF NOT EXISTS idx_skills_tags ON skills USING GIN(tags)",
        ]

        for idx_sql in indexes:
            try:
                await conn.execute(idx_sql)
            except Exception as e:
                print(f"  Index warning: {e}")

        # 创建 skill_assignments 表
        assignment_tables = await conn.fetch("""
            SELECT table_name FROM information_schema.tables
            WHERE table_schema = 'public' AND table_name = 'skill_assignments'
        """)

        if not assignment_tables:
            print("Creating skill_assignments table...")
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS skill_assignments (
                    id VARCHAR(100) PRIMARY KEY,
                    skill_id VARCHAR(100) NOT NULL REFERENCES skills(id) ON DELETE CASCADE,
                    agent_type VARCHAR(50) NOT NULL,
                    slot_name VARCHAR(100) DEFAULT '',
                    custom_parameters JSONB,
                    variable_overrides JSONB DEFAULT '{}',
                    priority INTEGER DEFAULT 50,
                    execution_condition TEXT,
                    is_enabled BOOLEAN DEFAULT TRUE,
                    is_required BOOLEAN DEFAULT FALSE,
                    assigned_by VARCHAR(50) DEFAULT 'user',
                    assigned_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(skill_id, agent_type, slot_name)
                )
            """)
            print("Table skill_assignments created.")

            # 创建索引
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_skill_assignments_skill ON skill_assignments(skill_id)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_skill_assignments_agent ON skill_assignments(agent_type)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_skill_assignments_enabled ON skill_assignments(is_enabled)")

        # 创建 skill_execution_logs 表
        log_tables = await conn.fetch("""
            SELECT table_name FROM information_schema.tables
            WHERE table_schema = 'public' AND table_name = 'skill_execution_logs'
        """)

        if not log_tables:
            print("Creating skill_execution_logs table...")
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS skill_execution_logs (
                    id VARCHAR(100) PRIMARY KEY,
                    skill_id VARCHAR(100) REFERENCES skills(id) ON DELETE SET NULL,
                    project_id UUID REFERENCES projects(id) ON DELETE SET NULL,
                    agent_id VARCHAR(100),
                    input_params JSONB DEFAULT '{}',
                    output_result TEXT,
                    success BOOLEAN DEFAULT TRUE,
                    error_message TEXT,
                    execution_time_ms INTEGER,
                    token_usage JSONB,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                )
            """)
            print("Table skill_execution_logs created.")

            # 创建索引
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_skill_logs_skill ON skill_execution_logs(skill_id)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_skill_logs_project ON skill_execution_logs(project_id)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_skill_logs_created ON skill_execution_logs(created_at DESC)")

        # 检查 agent_templates 表是否存在，如果存在则添加 skill_slots 列
        agent_template_exists = await conn.fetch("""
            SELECT table_name FROM information_schema.tables
            WHERE table_schema = 'public' AND table_name = 'agent_templates'
        """)

        if agent_template_exists:
            print("Adding skill_slots column to agent_templates...")
            try:
                await conn.execute("ALTER TABLE agent_templates ADD COLUMN IF NOT EXISTS skill_slots JSONB DEFAULT '[]'")
                print("Column 'skill_slots' added to agent_templates.")
            except Exception as e:
                print(f"  Warning: {e}")
        else:
            print("Note: agent_templates table does not exist. Skill slots will be managed in memory.")

        # 创建更新时间戳的触发器
        print("Creating update trigger...")
        await conn.execute("""
            CREATE OR REPLACE FUNCTION update_skills_updated_at()
            RETURNS TRIGGER AS $$
            BEGIN
                NEW.updated_at = CURRENT_TIMESTAMP;
                RETURN NEW;
            END;
            $$ LANGUAGE plpgsql
        """)

        # 检查触发器是否存在
        trigger_exists = await conn.fetch("""
            SELECT trigger_name FROM information_schema.triggers
            WHERE event_object_table = 'skills' AND trigger_name = 'skills_updated_at'
        """)

        if not trigger_exists:
            await conn.execute("""
                CREATE TRIGGER skills_updated_at
                    BEFORE UPDATE ON skills
                    FOR EACH ROW
                    EXECUTE FUNCTION update_skills_updated_at()
            """)
            print("Update trigger created.")

        # 最终验证
        tables = await conn.fetch("""
            SELECT table_name FROM information_schema.tables
            WHERE table_schema = 'public' AND table_name IN ('skills', 'skill_assignments', 'skill_execution_logs')
            ORDER BY table_name
        """)
        print(f"\nFinal tables created: {[t['table_name'] for t in tables]}")

        # 显示 skills 表的列
        columns = await conn.fetch("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'skills' ORDER BY ordinal_position
        """)
        print(f"Skills table columns ({len(columns)}): {[c['column_name'] for c in columns][:10]}...")

        print("\n[SUCCESS] Migration completed!")

    except Exception as e:
        print(f"[ERROR] Migration failed: {e}")
        import traceback
        traceback.print_exc()
        raise
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(run_migration())
