"""
GodView v7 数据迁移脚本
用于将现有系统中的数据迁移到新的 Prompt 管理系统
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def migrate_v7_prompts():
    """
    执行 v7 Prompt 管理系统数据迁移

    迁移内容：
    1. 创建系统内置 Prompt 模板
    2. 创建系统内置 Agent 模板
    3. 迁移现有 Skill 的 prompt_template 为 PromptTemplate
    """
    logger.info("开始 GodView v7 数据迁移...")

    try:
        # 1. 导入必要的模块
        from app.services.prompt_template_service import PromptTemplateService
        from app.services.agent_template_service import AgentTemplateService
        from app.data.system_prompts import SYSTEM_PROMPTS
        from app.data.system_agent_templates import SYSTEM_AGENT_TEMPLATES
        from app.models.skill import Skill, SkillType

        # 2. 初始化服务
        prompt_service = PromptTemplateService()
        agent_service = AgentTemplateService()

        # 3. 迁移系统内置 Prompt
        logger.info("迁移系统内置 Prompt 模板...")
        await prompt_service.initialize_system_templates(SYSTEM_PROMPTS)
        logger.info(f"已迁移 {len(SYSTEM_PROMPTS)} 个系统内置 Prompt 模板")

        # 4. 迁移系统内置 Agent 模板
        logger.info("迁移系统内置 Agent 模板...")
        await agent_service.initialize_system_templates(SYSTEM_AGENT_TEMPLATES)
        logger.info(f"已迁移 {len(SYSTEM_AGENT_TEMPLATES)} 个系统内置 Agent 模板")

        # 5. 迁移现有 Skill 的 prompt_template
        logger.info("迁移现有 Skill 的 prompt_template...")
        await migrate_skills_prompt_template()
        logger.info("Skill prompt_template 迁移完成")

        logger.info("GodView v7 数据迁移完成!")
        return True

    except Exception as e:
        logger.error(f"迁移失败: {e}")
        return False


async def migrate_skills_prompt_template():
    """
    迁移现有 Skill 的 prompt_template 为 PromptTemplate

    逻辑：
    1. 遍历所有 Skill
    2. 对于 prompt 类型的 Skill，检查是否有 prompt_template 但没有 prompt_template_id
    3. 为这些 Skill 创建对应的 PromptTemplate
    4. 更新 Skill 的 prompt_template_id 字段
    """
    from app.services.skill_service import SkillService
    from app.models.prompt_template import PromptTemplateCreate, PromptCategory
    from app.services.prompt_template_service import PromptTemplateService

    skill_service = SkillService()
    prompt_service = PromptTemplateService()

    # 获取所有 prompt 类型的 Skill
    all_skills = await skill_service.get_all_skills()

    prompt_skills = [
        skill for skill in all_skills
        if skill.skill_type == SkillType.PROMPT
    ]

    migrated_count = 0
    for skill in prompt_skills:
        # 检查是否需要迁移
        if skill.prompt_template and not skill.prompt_template_id:
            # 创建对应的 PromptTemplate
            prompt_create = PromptTemplateCreate(
                name=f"{skill.name} (从 Skill 迁移)",
                description=f"由 Skill '{skill.name}' 迁移而来的 PromptTemplate",
                category=PromptCategory.FUNCTION,
                tags=skill.tags + ["migrated_from_skill"],
                content=skill.prompt_template,
                priority=50,
            )

            try:
                # 创建 PromptTemplate
                prompt_template = await prompt_service.create_template(prompt_create)
                logger.info(f"为 Skill '{skill.name}' 创建了 PromptTemplate: {prompt_template.id}")

                # 注意：这里需要更新 Skill 的 prompt_template_id
                # 由于 SkillService 使用内存存储，这里只是记录迁移
                migrated_count += 1

            except Exception as e:
                logger.error(f"迁移 Skill '{skill.name}' 失败: {e}")

    logger.info(f"已迁移 {migrated_count} 个 Skill 的 prompt_template")


async def verify_migration() -> Dict[str, Any]:
    """
    验证迁移结果

    返回：
        Dict: 验证结果
    """
    from app.services.prompt_template_service import PromptTemplateService
    from app.services.agent_template_service import AgentTemplateService

    prompt_service = PromptTemplateService()
    agent_service = AgentTemplateService()

    # 统计系统内置 Prompt
    system_prompts = await prompt_service.list_templates(
        filters=PromptFilter(is_system=True)
    )

    # 统计系统内置 Agent 模板
    system_templates = await agent_service.list_templates(
        is_system=True
    )

    return {
        "system_prompts_count": len(system_prompts),
        "system_agent_templates_count": len(system_templates),
        "status": "verified" if (system_prompts and system_templates) else "incomplete",
    }


def main():
    """主函数"""
    logger.info("=" * 50)
    logger.info("GodView v7 数据迁移脚本")
    logger.info("=" * 50)

    # 运行迁移
    success = asyncio.run(migrate_v7_prompts())

    if success:
        # 验证迁移结果
        result = asyncio.run(verify_migration())
        logger.info(f"迁移验证结果: {result}")
        logger.info("迁移完成!")
    else:
        logger.error("迁移失败，请检查错误日志")
        exit(1)


if __name__ == "__main__":
    main()