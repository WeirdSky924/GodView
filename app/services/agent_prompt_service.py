# -*- coding: utf-8 -*-
"""
Agent Prompt 服务
负责动态加载和组装 Agent 的完整 system prompt
集成 Skills 系统，支持从数据库加载 Agent 技能
"""

import logging
from typing import Any, Dict, List, Optional

from app.data.system_prompts import SYSTEM_PROMPTS, PROMPTS_FOR_AGENT_TYPE
from app.data.system_agent_templates import TEMPLATES_BY_TYPE, SYSTEM_AGENT_TEMPLATES
from app.models.agent_template import AgentTemplate, AgentType, SkillSlot
from app.models.prompt_template import PromptTemplate
from app.models.skill import Skill, SkillType
from app.services.writing_rules_init import build_writing_prompt

logger = logging.getLogger(__name__)


class AgentPromptService:
    """Agent Prompt 动态加载服务"""

    def __init__(self):
        # Prompt 模板缓存
        self._prompt_cache: Dict[str, PromptTemplate] = {}
        self._build_cache()

        # Agent 模板缓存
        self._template_cache: Dict[str, AgentTemplate] = {}
        self._build_template_cache()

        # 项目写作规则缓存
        self._project_writing_rules: Dict[str, Dict[str, Any]] = {}

        # Skill 缓存（按 agent_type 索引）
        self._skills_cache: Dict[str, List[Skill]] = {}
        self._skills_cache_valid: bool = False

    def _build_cache(self):
        """构建 Prompt 模板缓存"""
        for prompt in SYSTEM_PROMPTS:
            self._prompt_cache[prompt.id] = prompt

    def _build_template_cache(self):
        """构建 Agent 模板缓存"""
        for template in SYSTEM_AGENT_TEMPLATES:
            self._template_cache[template.id] = template
            # 同时按 agent_type 索引
            self._template_cache[template.agent_type] = template

    async def _load_skills_for_agent(self, agent_type: str) -> List[Skill]:
        """
        加载 Agent 的 Skills

        优先从数据库加载，如果数据库不可用则使用默认 Skills

        Args:
            agent_type: Agent 类型

        Returns:
            List[Skill]: Skill 列表（按优先级降序）
        """
        # 检查缓存
        if self._skills_cache_valid and agent_type in self._skills_cache:
            return self._skills_cache[agent_type]

        skills = []

        try:
            # 尝试从 SkillService 加载
            from app.services.skill_service import get_skill_service
            service = get_skill_service()
            skills = await service.get_skills_for_agent_type(agent_type)

            # 更新缓存
            self._skills_cache[agent_type] = skills
            self._skills_cache_valid = True

            logger.info(f"从 SkillService 加载 {agent_type} 的 Skills: {len(skills)} 个")

        except Exception as e:
            logger.warning(f"从 SkillService 加载 Skills 失败: {e}，使用默认 Skills")
            # 使用默认 Skills
            skills = self._get_default_skills_for_agent(agent_type)
            self._skills_cache[agent_type] = skills

        return skills

    def _get_default_skills_for_agent(self, agent_type: str) -> List[Skill]:
        """
        获取 Agent 的默认 Skills（当数据库不可用时使用）

        Args:
            agent_type: Agent 类型

        Returns:
            List[Skill]: Skill 列表
        """
        try:
            from app.data.default_skills import get_default_skills

            all_skills = get_default_skills()
            result = []

            for skill in all_skills:
                # 空列表表示所有 Agent 都可用
                if not skill.applicable_agent_types:
                    result.append(skill)
                elif agent_type in skill.applicable_agent_types:
                    result.append(skill)

            # 按优先级降序排序
            result.sort(key=lambda x: -x.priority)
            return result

        except Exception as e:
            logger.error(f"获取默认 Skills 失败: {e}")
            return []

    def invalidate_skills_cache(self):
        """使 Skills 缓存失效"""
        self._skills_cache_valid = False
        self._skills_cache.clear()

    def get_skill_cache_status(self) -> Dict[str, Any]:
        """获取 Skills 缓存状态"""
        return {
            "valid": self._skills_cache_valid,
            "cached_agents": list(self._skills_cache.keys()),
            "total_cached_skills": sum(len(s) for s in self._skills_cache.values()),
        }

    def get_prompt_template(self, template_id: str) -> Optional[PromptTemplate]:
        """获取 Prompt 模板"""
        return self._prompt_cache.get(template_id)

    def get_agent_template(self, agent_type: str) -> Optional[AgentTemplate]:
        """获取 Agent 模板"""
        return self._template_cache.get(agent_type) or TEMPLATES_BY_TYPE.get(agent_type)

    def update_project_writing_config(
        self,
        project_id: str,
        enabled_rule_ids: List[str],
        enabled_rule_set_ids: List[str],
    ):
        """
        更新项目的写作规则配置

        Args:
            project_id: 项目ID
            enabled_rule_ids: 启用的规则ID列表
            enabled_rule_set_ids: 启用的规则集ID列表
        """
        self._project_writing_rules[project_id] = {
            "enabled_rule_ids": enabled_rule_ids,
            "enabled_rule_set_ids": enabled_rule_set_ids,
        }
        logger.info(f"更新项目 {project_id} 的写作规则配置: {len(enabled_rule_ids)} 条规则, {len(enabled_rule_set_ids)} 个规则集")

    def get_project_writing_config(self, project_id: str) -> Dict[str, Any]:
        """获取项目的写作规则配置"""
        return self._project_writing_rules.get(project_id, {
            "enabled_rule_ids": [],
            "enabled_rule_set_ids": [],
        })

    async def build_agent_prompt(
        self,
        agent_type: str,
        project_id: Optional[str] = None,
        variables: Optional[Dict[str, Any]] = None,
        characters: Optional[List[Any]] = None,
        include_skills: bool = True,
    ) -> str:
        """
        构建 Agent 的完整 system prompt

        Args:
            agent_type: Agent 类型
            project_id: 项目ID（用于加载写作规则等）
            variables: 模板变量
            characters: 角色列表（用于构建角色层级信息）
            include_skills: 是否包含 Skills

        Returns:
            str: 完整的 system prompt
        """
        # 获取 Agent 模板
        template = self.get_agent_template(agent_type)
        if not template:
            logger.warning(f"未找到 Agent 类型 {agent_type} 的模板")
            return ""

        # 按优先级排序插槽
        sorted_slots = sorted(
            template.prompt_slots,
            key=lambda x: -x.priority
        )

        # 组装 prompt 片段
        prompt_pieces = []

        # 1. 首先加载并渲染 Skills（最高优先级）
        if include_skills:
            skills_content = await self._build_skills_prompt(agent_type, variables)
            if skills_content:
                prompt_pieces.append(skills_content)

        # 2. 处理模板插槽
        for slot in sorted_slots:
            if not slot.is_enabled:
                continue

            # 特殊处理：writing_rules 插槽
            if slot.slot_name == "writing_rules":
                writing_prompt = await self._build_writing_rules_prompt(project_id)
                if writing_prompt:
                    prompt_pieces.append(writing_prompt)
                continue

            # 特殊处理：character_hierarchy 插槽
            if slot.slot_name == "character_hierarchy":
                hierarchy_prompt = self._build_character_hierarchy_prompt(characters)
                if hierarchy_prompt:
                    prompt_pieces.append(hierarchy_prompt)
                continue

            # 普通 Prompt 模板
            prompt_template_id = slot.prompt_template_id
            if not prompt_template_id:
                continue

            prompt_template = self.get_prompt_template(prompt_template_id)
            if not prompt_template:
                logger.warning(f"未找到 Prompt 模板: {prompt_template_id}")
                continue

            # 合并变量
            merged_vars = {}
            merged_vars.update(prompt_template.default_values)
            merged_vars.update(slot.variable_overrides)
            if variables:
                merged_vars.update(variables)

            # 渲染模板
            rendered = self._render_template(prompt_template, merged_vars)
            if rendered:
                prompt_pieces.append(rendered)

        return "\n\n".join(prompt_pieces)

    async def _build_skills_prompt(
        self,
        agent_type: str,
        variables: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        构建 Agent 的 Skills prompt

        按优先级加载和渲染 Skills：
        1. KNOWLEDGE 类型：直接提供知识内容
        2. PROMPT 类型：渲染模板内容

        Args:
            agent_type: Agent 类型
            variables: 模板变量

        Returns:
            str: Skills 组合后的 prompt
        """
        # 加载 Skills
        skills = await self._load_skills_for_agent(agent_type)

        if not skills:
            return ""

        # 按类型分组
        knowledge_pieces = []
        prompt_pieces = []

        for skill in skills:
            if not skill.is_enabled:
                continue

            try:
                if skill.skill_type == SkillType.KNOWLEDGE:
                    # 知识类型：直接使用内容
                    content = skill.knowledge_content or ""
                    if content:
                        # 渲染变量
                        rendered = self._render_skill_content(skill, content, variables)
                        knowledge_pieces.append(rendered)

                elif skill.skill_type == SkillType.PROMPT:
                    # Prompt 类型：渲染模板
                    content = skill.prompt_template or ""
                    if content:
                        rendered = self._render_skill_content(skill, content, variables)
                        prompt_pieces.append(rendered)

            except Exception as e:
                logger.warning(f"渲染 Skill {skill.id} 失败: {e}")

        # 组合：知识在前，prompt 在后
        pieces = []
        if knowledge_pieces:
            pieces.append("【核心知识与原则】\n" + "\n\n".join(knowledge_pieces))
        if prompt_pieces:
            pieces.append("【技能指导】\n" + "\n\n".join(prompt_pieces))

        return "\n\n".join(pieces)

    def _render_skill_content(
        self,
        skill: Skill,
        content: str,
        variables: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        渲染 Skill 内容，替换变量占位符

        Args:
            skill: Skill 对象
            content: 原始内容
            variables: 变量字典

        Returns:
            str: 渲染后的内容
        """
        if not variables:
            variables = {}

        # 合并默认参数值
        for param in skill.parameters:
            if param.name not in variables and param.default is not None:
                variables[param.name] = param.default

        # 替换变量占位符 {var_name}
        rendered = content
        for var_name, var_value in variables.items():
            placeholder = f"{{{var_name}}}"
            if placeholder in rendered:
                # 处理不同类型的值
                if isinstance(var_value, (list, dict)):
                    import json
                    rendered = rendered.replace(placeholder, json.dumps(var_value, ensure_ascii=False, indent=2))
                else:
                    rendered = rendered.replace(placeholder, str(var_value))

        return rendered

    async def build_skill_prompt(
        self,
        skill_id: str,
        variables: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        构建单个 Skill 的完整 prompt

        Args:
            skill_id: Skill ID
            variables: 模板变量

        Returns:
            str: 渲染后的 prompt
        """
        try:
            from app.services.skill_service import get_skill_service
            service = get_skill_service()
            skill = await service.get_skill(skill_id)

            if not skill:
                logger.warning(f"Skill 不存在: {skill_id}")
                return ""

            if skill.skill_type == SkillType.KNOWLEDGE:
                content = skill.knowledge_content or ""
            elif skill.skill_type == SkillType.PROMPT:
                content = skill.prompt_template or ""
            else:
                return ""

            return self._render_skill_content(skill, content, variables)

        except Exception as e:
            logger.error(f"构建 Skill prompt 失败: {e}")
            return ""

    def _build_character_hierarchy_prompt(self, characters: Optional[List[Any]]) -> str:
        """
        构建角色层级 prompt

        Args:
            characters: 角色列表

        Returns:
            str: 角色层级 prompt
        """
        if not characters:
            return ""

        try:
            from app.services.character_hierarchy_service import CharacterHierarchyService

            service = CharacterHierarchyService()
            return service.build_character_hierarchy_prompt(characters)
        except Exception as e:
            logger.warning(f"构建角色层级 prompt 失败: {e}")
            return ""

    async def _build_writing_rules_prompt(self, project_id: Optional[str]) -> str:
        """
        构建写作规则 prompt

        Args:
            project_id: 项目ID

        Returns:
            str: 写作规则 prompt
        """
        if not project_id:
            return ""

        # 获取项目的写作规则配置
        config = self.get_project_writing_config(project_id)
        enabled_rule_ids = config.get("enabled_rule_ids", [])
        enabled_rule_set_ids = config.get("enabled_rule_set_ids", [])

        if not enabled_rule_ids and not enabled_rule_set_ids:
            # 使用默认规则集
            enabled_rule_set_ids = ["rule_set_web_novel_basics"]

        # 构建写作规则 prompt
        writing_prompt = build_writing_prompt(
            rule_ids=enabled_rule_ids,
            rule_set_ids=enabled_rule_set_ids,
        )

        if writing_prompt:
            logger.info(f"为项目 {project_id} 构建写作规则 prompt, 包含 {len(enabled_rule_ids)} 条规则和 {len(enabled_rule_set_ids)} 个规则集")

        return writing_prompt

    def _render_template(self, template: PromptTemplate, variables: Dict[str, Any]) -> str:
        """
        渲染 Prompt 模板

        Args:
            template: Prompt 模板
            variables: 变量字典

        Returns:
            str: 渲染后的内容
        """
        content = template.content

        # 替换变量
        for var_name, var_value in variables.items():
            placeholder = f"{{{var_name}}}"
            if placeholder in content:
                content = content.replace(placeholder, str(var_value))

        return content

    def get_all_templates(self) -> List[AgentTemplate]:
        """获取所有 Agent 模板"""
        return SYSTEM_AGENT_TEMPLATES.copy()

    def get_template_summary(self) -> Dict[str, Any]:
        """获取模板摘要信息"""
        summary = {}
        for template in SYSTEM_AGENT_TEMPLATES:
            summary[template.agent_type] = {
                "id": template.id,
                "name": template.name,
                "slots": [slot.slot_name for slot in template.prompt_slots],
                "skill_slots": [slot.slot_name for slot in template.skill_slots],
                "model": template.default_model,
                "temperature": template.default_temperature,
            }
        return summary

    async def get_agent_skills_info(self, agent_type: str) -> List[Dict[str, Any]]:
        """
        获取 Agent 的 Skills 详细信息

        Args:
            agent_type: Agent 类型

        Returns:
            List[Dict]: Skill 信息列表
        """
        skills = await self._load_skills_for_agent(agent_type)

        result = []
        for skill in skills:
            result.append({
                "id": skill.id,
                "name": skill.name,
                "description": skill.description,
                "skill_type": skill.skill_type.value,
                "category": skill.category.value,
                "priority": skill.priority,
                "is_enabled": skill.is_enabled,
                "is_system": skill.is_system,
            })

        return result


# 全局单例
_agent_prompt_service: Optional[AgentPromptService] = None


def get_agent_prompt_service() -> AgentPromptService:
    """获取 AgentPromptService 单例"""
    global _agent_prompt_service
    if _agent_prompt_service is None:
        _agent_prompt_service = AgentPromptService()
    return _agent_prompt_service
