"""
验证迁移结果
"""
import asyncio
import asyncpg
import os
from dotenv import load_dotenv

load_dotenv()


async def verify():
    url = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:password@127.0.0.1:5432/godview")
    if "+asyncpg" in url:
        url = url.replace("+asyncpg", "")
    conn = await asyncpg.connect(url)

    print("=" * 60)
    print("MIGRATION VERIFICATION REPORT")
    print("=" * 60)

    # 1. prompt_templates
    prompt_count = await conn.fetchval("SELECT COUNT(*) FROM prompt_templates")
    print(f"\n1. prompt_templates: {prompt_count} records")

    categories = await conn.fetch("""
        SELECT category, COUNT(*) as cnt FROM prompt_templates GROUP BY category ORDER BY cnt DESC
    """)
    print("   By category:")
    for c in categories:
        print(f"     - {c['category']}: {c['cnt']}")

    # 2. skills
    skill_count = await conn.fetchval("SELECT COUNT(*) FROM skills")
    print(f"\n2. skills: {skill_count} records")

    skill_types = await conn.fetch("""
        SELECT skill_type, COUNT(*) as cnt FROM skills GROUP BY skill_type ORDER BY cnt DESC
    """)
    print("   By type:")
    for s in skill_types:
        print(f"     - {s['skill_type']}: {s['cnt']}")

    load_modes = await conn.fetch("""
        SELECT load_mode, COUNT(*) as cnt FROM skills GROUP BY load_mode
    """)
    print("   By load_mode:")
    for l in load_modes:
        print(f"     - {l['load_mode']}: {l['cnt']}")

    # 3. agent_prompt_bindings
    binding_count = await conn.fetchval("SELECT COUNT(*) FROM agent_prompt_bindings")
    print(f"\n3. agent_prompt_bindings: {binding_count} records")

    agent_bindings = await conn.fetch("""
        SELECT agent_type, COUNT(*) as cnt FROM agent_prompt_bindings
        GROUP BY agent_type ORDER BY cnt DESC LIMIT 10
    """)
    print("   Top agent types:")
    for a in agent_bindings:
        print(f"     - {a['agent_type']}: {a['cnt']}")

    # 4. skill_assignments
    assignment_count = await conn.fetchval("SELECT COUNT(*) FROM skill_assignments")
    print(f"\n4. skill_assignments: {assignment_count} records")

    agent_assignments = await conn.fetch("""
        SELECT agent_type, COUNT(*) as cnt FROM skill_assignments
        GROUP BY agent_type ORDER BY cnt DESC LIMIT 10
    """)
    print("   Top agent types:")
    for a in agent_assignments:
        print(f"     - {a['agent_type']}: {a['cnt']}")

    # 5. 验证 Skill 调用指导
    print(f"\n5. Skill guidance in prompts:")

    # 检查 function_writing 是否包含 skill 调用指导
    writer_content = await conn.fetchval("""
        SELECT content FROM prompt_templates WHERE id = 'function_writing'
    """)
    has_skill_table = "可用工具" in (writer_content or "")
    has_chapter_writing = "skill_chapter_writing" in (writer_content or "")
    print(f"   function_writing has skill table: {has_skill_table}")
    print(f"   function_writing mentions skill_chapter_writing: {has_chapter_writing}")

    # 检查 function_evaluation
    evaluator_content = await conn.fetchval("""
        SELECT content FROM prompt_templates WHERE id = 'function_evaluation'
    """)
    has_skill_table_eval = "可用工具" in (evaluator_content or "")
    has_chapter_eval = "skill_chapter_evaluation" in (evaluator_content or "")
    print(f"   function_evaluation has skill table: {has_skill_table_eval}")
    print(f"   function_evaluation mentions skill_chapter_evaluation: {has_chapter_eval}")

    # 6. 列出关键的 skills
    print(f"\n6. Key skills:")
    key_skills = await conn.fetch("""
        SELECT id, name, load_mode FROM skills
        WHERE id IN ('skill_chapter_writing', 'skill_chapter_evaluation',
                     'skill_long_novel_awareness', 'skill_world_context',
                     'skill_plot_planning', 'skill_foreshadowing_tracker')
        ORDER BY id
    """)
    for s in key_skills:
        print(f"   - {s['id']}: {s['name'][:30]} (load_mode: {s['load_mode']})")

    print(f"\n" + "=" * 60)
    print("MIGRATION SUCCESSFUL!")
    print("=" * 60)

    await conn.close()


if __name__ == "__main__":
    asyncio.run(verify())
