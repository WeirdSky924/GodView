# -*- coding: utf-8 -*-
"""
Agent Prompt 服务
负责动态加载和组装 Agent 的完整 system prompt
集成 Skills 系统，支持从数据库加载 Agent 技能

支持双层 Skill 加载：
- 核心层(CORE): 始终加载到上下文中，如"不可抄袭"等基础规则
- 按需层(ON_DEMAND): 根据 Embedding + LLM 智能检索动态加载
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Tuple

from app.data.system_prompts import SYSTEM_PROMPTS, PROMPTS_FOR_AGENT_TYPE
from app.data.system_agent_templates import TEMPLATES_BY_TYPE, SYSTEM_AGENT_TEMPLATES
from app.models.agent_config import AgentConfig, ConfigOverrideType, ModelConfig
from app.models.agent_template import AgentTemplate, AgentType, PromptSlot, SkillSlot
from app.models.prompt_template import PromptTemplate
from app.models.skill import Skill, SkillType, SkillLoadMode
from app.services.prompt_builder import PromptBuilder
from app.services.writing_rule_service import get_writing_rule_service

logger = logging.getLogger(__name__)


class AgentPromptService:
    """Agent Prompt 动态加载服务"""

    def __init__(self, prompt_template_service=None, agent_template_service=None):
        self._prompt_template_service = prompt_template_service
        self._agent_template_service = agent_template_service
        self._prompt_builder = PromptBuilder(
            prompt_template_service=prompt_template_service,
            agent_template_service=agent_template_service,
        )

        # Prompt 模板缓存
        self._prompt_cache: Dict[str, PromptTemplate] = {}

        # Agent 模板缓存
        self._template_cache: Dict[str, AgentTemplate] = {}

        self._build_cache()
        self._build_template_cache()

        # 项目写作规则缓存
        self._project_writing_rules: Dict[str, Dict[str, Any]] = {}

        # Skill 缓存（按 agent_type 索引）
        self._skills_cache: Dict[str, List[Skill]] = {}
        self._skills_cache_valid: bool = False

    def set_services(self, prompt_template_service=None, agent_template_service=None):
        """注入运行时服务依赖"""
        self._prompt_template_service = prompt_template_service
        self._agent_template_service = agent_template_service
        self._prompt_builder = PromptBuilder(
            prompt_template_service=prompt_template_service,
            agent_template_service=agent_template_service,
        )

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

    async def _resolve_template_for_agent(
        self,
        agent_type: str,
        project_id: Optional[str] = None,
    ) -> Optional[AgentTemplate]:
        """按项目配置解析运行时模板。"""
        try:
            from app.services.agent_config_service import get_agent_config_service
            from app.api.routes.agent_templates import get_agent_template_service
            from app.models.agent_template import AgentType as AgentTypeEnum

            if project_id:
                config_service = get_agent_config_service()
                state = await config_service.resolve_agent_runtime_state(project_id, agent_type)
                template = state.get("template")
                if template:
                    return template

            template_service = self._agent_template_service or get_agent_template_service()
            return await template_service.get_template_by_type(AgentTypeEnum(agent_type))
        except Exception as e:
            logger.debug(f"解析 AgentTemplate 失败: agent={agent_type}, project={project_id}, error={e}")

        return self.get_agent_template(agent_type)

    async def _load_skills_for_agent(
        self,
        agent_type: str,
        project_id: Optional[str] = None,
        context_query: Optional[str] = None,
        context_keywords: Optional[List[str]] = None,
        context_scene: Optional[str] = None,
        use_intelligent_retrieval: bool = True,
    ) -> List[tuple[Skill, Dict[str, Any]]]:
        """
        加载 Agent 的 Skills（双层加载 + 智能检索）

        加载优先级：
        1. 首先从 agent_templates.skill_slots 加载绑定的 Skills
        2. 然后根据 load_mode 决定是核心层还是按需层
        3. 按需层通过 Embedding + LLM 智能检索进一步筛选
        """
        skills_with_params: List[tuple[Skill, Dict[str, Any]]] = []

        try:
            slot_skills = await self._load_skills_from_template_slots(
                agent_type,
                project_id=project_id,
            )
            if slot_skills:
                logger.info(f"从 agent_templates.skill_slots 加载 {len(slot_skills)} 个 Skills")
                slot_skills.sort(key=lambda x: -x[0].priority)
                return slot_skills

            from app.services.skill_service import get_skill_service
            service = get_skill_service()

            core_skills = await service.get_core_skills_for_agent(agent_type)
            for skill in core_skills:
                skills_with_params.append((skill, {}))

            if use_intelligent_retrieval and context_query:
                on_demand_skills = await self._intelligent_skill_retrieval(
                    agent_type, context_query
                )
                skills_with_params.extend(on_demand_skills)
            else:
                on_demand_skills = await service.get_on_demand_skills_for_agent(
                    agent_type,
                    context_keywords=context_keywords,
                    context_scene=context_scene,
                )
                for skill in on_demand_skills:
                    skills_with_params.append((skill, {}))

            seen_ids: Set[str] = set()
            unique_skills: List[tuple[Skill, Dict[str, Any]]] = []
            for skill, params in skills_with_params:
                if skill.id not in seen_ids:
                    seen_ids.add(skill.id)
                    unique_skills.append((skill, params))

            unique_skills.sort(key=lambda x: -x[0].priority)

            logger.info(
                f"加载 Agent {agent_type} 的 Skills: {len(core_skills)} 核心 + "
                f"{len(unique_skills) - len(core_skills)} 按需 = {len(unique_skills)} 总计"
                f"{'(智能检索)' if use_intelligent_retrieval and context_query else '(关键词匹配)'}"
            )

            return unique_skills

        except Exception as e:
            logger.warning(f"从 SkillService 加载 Skills 失败: {e}，使用默认 Skills")
            default_skills = self._get_default_skills_for_agent(agent_type)
            return [(s, {}) for s in default_skills]

    async def _intelligent_skill_retrieval(
        self,
        agent_type: str,
        context_query: str,
    ) -> List[tuple[Skill, Dict[str, Any]]]:
        """按查询文本做轻量技能检索，避免运行时因缺少实现而退回默认路径。"""
        if not context_query:
            return []

        try:
            from app.services.skill_service import get_skill_service

            service = get_skill_service()
            assigned_skills = await service.get_assigned_skills_for_agent(agent_type)
            if not assigned_skills:
                return []

            query_tokens = {
                token.strip().lower()
                for token in self.extract_keywords_from_text(context_query)
                if token and token.strip()
            }
            if not query_tokens:
                return []

            ranked: List[tuple[int, Skill, Dict[str, Any]]] = []
            for skill, assignment in assigned_skills:
                if assignment.load_mode == SkillLoadMode.CORE:
                    continue
                if assignment.load_mode is None and skill.load_mode == SkillLoadMode.CORE:
                    continue

                score = 0
                trigger_keywords = [kw.lower() for kw in (assignment.trigger_keywords or skill.trigger_keywords or []) if kw]
                tags = [tag.lower() for tag in (skill.tags or []) if tag]
                haystack = trigger_keywords + tags
                score += sum(3 for token in query_tokens if token in haystack)

                skill_name = (skill.name or "").lower()
                skill_desc = (skill.description or "").lower()
                for token in query_tokens:
                    if token in skill_name:
                        score += 2
                    if token in skill_desc:
                        score += 1

                if score > 0:
                    ranked.append((score, skill, assignment.variable_overrides or {}))

            ranked.sort(key=lambda item: (-item[0], -item[1].priority, item[1].id))
            return [(skill, params) for _, skill, params in ranked[:8]]
        except Exception as e:
            logger.warning(f"智能检索 Skill 失败: {e}")
            return []

    async def _load_skills_from_template_slots(
        self,
        agent_type: str,
        project_id: Optional[str] = None,
    ) -> List[tuple[Skill, Dict[str, Any]]]:
        """
        从 agent_templates.skill_slots 加载 Skills

        这是前端 UI 管理的绑定关系的真实数据源。
        优先从数据库加载，如果数据库不可用则使用内存缓存。
        """
        try:
            template = await self._resolve_template_for_agent(
                agent_type,
                project_id=project_id,
            )
            if not template or not template.skill_slots:
                return []

            from app.services.skill_service import get_skill_service
            service = get_skill_service()

            results: List[tuple[Skill, Dict[str, Any]]] = []

            for slot in template.skill_slots:
                if not slot.is_enabled:
                    continue

                if not slot.skill_id:
                    continue

                skill = await service.get_skill(slot.skill_id)
                if not skill:
                    logger.warning(f"Skill {slot.skill_id} 不存在，跳过")
                    continue

                if not skill.is_enabled:
                    continue

                params = slot.variable_overrides.copy() if slot.variable_overrides else {}
                results.append((skill, params))

            return results

        except Exception as e:
            logger.error(f"从 template skill_slots 加载 Skills 失败: {e}")
            return []

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

    async def _update_skill_usage_counts(self, skills: List[Skill]):
        """更新Skills的使用计数"""
        try:
            from app.services.skill_service import get_skill_service
            service = get_skill_service()

            for skill in skills:
                if not skill.is_enabled:
                    continue

                # 更新使用计数
                await service.increment_skill_usage(skill.id)

        except Exception as e:
            logger.warning(f"更新Skill使用计数失败: {e}")

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

    async def _build_prompt_from_config(
        self,
        agent_type: str,
        project_id: str,
        variables: Optional[Dict[str, Any]] = None,
    ) -> str:
        """基于项目级 AgentConfig + AgentTemplate 构建 prompt。"""
        try:
            from app.services.agent_config_service import get_agent_config_service
            from app.api.routes.agent_templates import get_agent_template_service
            from app.services.prompt_template_service import get_prompt_template_service

            config_service = get_agent_config_service()
            template_service = self._agent_template_service or get_agent_template_service()
            prompt_service = self._prompt_template_service or get_prompt_template_service()

            state = await config_service.resolve_agent_runtime_state(project_id, agent_type)
            template = state.get("template")
            config = state.get("config")

            if not template:
                try:
                    template = await template_service.get_template_by_type(AgentType(agent_type))
                except ValueError:
                    logger.debug(f"未知 Agent 类型，无法按项目配置构建 prompt: {agent_type}")
                    return ""

            if not template:
                return ""

            if not config:
                config = AgentConfig(
                    id=f"runtime_{project_id}_{agent_type}",
                    project_id=project_id,
                    agent_type=agent_type,
                    name=f"{agent_type} 运行时配置",
                    description="runtime fallback config",
                    template_id=template.id,
                    is_custom=False,
                    slot_overrides=[],
                    custom_prompt_order=None,
                    llm_config=ModelConfig(
                        model_name=template.default_model or ModelConfig().model_name,
                        temperature=template.default_temperature,
                    ),
                    is_active=True,
                    version=template.version,
                    created_at=datetime.now(),
                    updated_at=datetime.now(),
                )

            self.set_services(
                prompt_template_service=prompt_service,
                agent_template_service=template_service,
            )
            return await self._prompt_builder.build_prompt(config, template, variables or {})
        except Exception as e:
            logger.warning(
                f"按项目配置构建 Agent prompt 失败: project={project_id}, agent={agent_type}, error={e}"
            )
            return ""

    async def build_agent_prompt(
        self,
        agent_type: str,
        project_id: Optional[str] = None,
        variables: Optional[Dict[str, Any]] = None,
        characters: Optional[List[Any]] = None,
        include_skills: bool = True,
        context_query: Optional[str] = None,
        context_keywords: Optional[List[str]] = None,
        context_scene: Optional[str] = None,
        use_intelligent_retrieval: bool = True,
    ) -> str:
        """构建 Agent 的完整 system prompt。"""
        template = await self._resolve_template_for_agent(agent_type, project_id=project_id)
        if not template:
            logger.warning(f"未找到 Agent 类型 {agent_type} 的模板")
            return ""

        prompt_pieces = []

        if include_skills:
            skills_content = await self._build_skills_prompt(
                agent_type,
                project_id=project_id,
                variables=variables,
                context_query=context_query,
                context_keywords=context_keywords,
                context_scene=context_scene,
                use_intelligent_retrieval=use_intelligent_retrieval,
            )
            if skills_content:
                prompt_pieces.append(skills_content)

        config_prompt = ""
        if project_id:
            config_prompt = await self._build_prompt_from_config(
                agent_type=agent_type,
                project_id=project_id,
                variables=variables,
            )

        if config_prompt:
            prompt_pieces.append(config_prompt)

            slot_names = {slot.slot_name for slot in template.prompt_slots if slot.is_enabled}
            if "writing_rules" in slot_names:
                writing_prompt = await self._build_writing_rules_prompt(project_id)
                if writing_prompt:
                    prompt_pieces.append(writing_prompt)

            if "character_hierarchy" in slot_names:
                hierarchy_prompt = self._build_character_hierarchy_prompt(characters)
                if hierarchy_prompt:
                    prompt_pieces.append(hierarchy_prompt)

            return "\n\n".join(piece for piece in prompt_pieces if piece)

        sorted_slots = sorted(template.prompt_slots, key=lambda x: -x.priority)
        for slot in sorted_slots:
            if not slot.is_enabled:
                continue

            if slot.slot_name == "writing_rules":
                writing_prompt = await self._build_writing_rules_prompt(project_id)
                if writing_prompt:
                    prompt_pieces.append(writing_prompt)
                continue

            if slot.slot_name == "character_hierarchy":
                hierarchy_prompt = self._build_character_hierarchy_prompt(characters)
                if hierarchy_prompt:
                    prompt_pieces.append(hierarchy_prompt)
                continue

            prompt_template_id = slot.prompt_template_id
            if not prompt_template_id:
                continue

            prompt_template = self.get_prompt_template(prompt_template_id)
            if not prompt_template:
                logger.warning(f"未找到 Prompt 模板: {prompt_template_id}")
                continue

            merged_vars = {}
            merged_vars.update(prompt_template.default_values)
            merged_vars.update(slot.variable_overrides)
            if variables:
                merged_vars.update(variables)

            rendered = self._render_template(prompt_template, merged_vars)
            if rendered:
                prompt_pieces.append(rendered)

        return "\n\n".join(prompt_pieces)

    async def _build_skills_prompt(
        self,
        agent_type: str,
        project_id: Optional[str] = None,
        variables: Optional[Dict[str, Any]] = None,
        context_query: Optional[str] = None,
        context_keywords: Optional[List[str]] = None,
        context_scene: Optional[str] = None,
        use_intelligent_retrieval: bool = True,
    ) -> str:
        """
        构建 Agent 的 Skills prompt（双层加载 + 智能检索）

        核心层 Skills 始终加载，按需层 Skills 通过智能检索加载。

        按优先级加载和渲染 Skills：
        1. KNOWLEDGE 类型：直接提供知识内容
        2. PROMPT 类型：渲染模板内容
        """
        skills_with_params = await self._load_skills_for_agent(
            agent_type,
            project_id=project_id,
            context_query=context_query,
            context_keywords=context_keywords,
            context_scene=context_scene,
            use_intelligent_retrieval=use_intelligent_retrieval,
        )

        if not skills_with_params:
            return ""

        core_knowledge_pieces = []
        core_prompt_pieces = []
        on_demand_knowledge_pieces = []
        on_demand_prompt_pieces = []

        skills_only = [s for s, _ in skills_with_params]
        await self._update_skill_usage_counts(skills_only)

        for skill, params in skills_with_params:
            if not skill.is_enabled:
                continue

            merged_vars = variables.copy() if variables else {}
            merged_vars.update(params)

            try:
                is_core = skill.load_mode == SkillLoadMode.CORE

                if skill.skill_type == SkillType.KNOWLEDGE:
                    content = skill.knowledge_content or ""
                    if content:
                        rendered = self._render_skill_content(skill, content, merged_vars)
                        if is_core:
                            core_knowledge_pieces.append(rendered)
                        else:
                            on_demand_knowledge_pieces.append(rendered)

                elif skill.skill_type == SkillType.PROMPT:
                    content = skill.prompt_template or ""
                    if content:
                        rendered = self._render_skill_content(skill, content, merged_vars)
                        if is_core:
                            core_prompt_pieces.append(rendered)
                        else:
                            on_demand_prompt_pieces.append(rendered)

            except Exception as e:
                logger.warning(f"渲染 Skill {skill.id} 失败: {e}")

        pieces = []
        if core_knowledge_pieces:
            pieces.append("【核心知识与原则】\n" + "\n\n".join(core_knowledge_pieces))
        if core_prompt_pieces:
            pieces.append("【核心技能指导】\n" + "\n\n".join(core_prompt_pieces))
        if on_demand_knowledge_pieces:
            pieces.append("【场景知识】\n" + "\n\n".join(on_demand_knowledge_pieces))
        if on_demand_prompt_pieces:
            pieces.append("【场景技能指导】\n" + "\n\n".join(on_demand_prompt_pieces))

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

    async def get_runtime_agent_skills(
        self,
        agent_type: str,
        project_id: Optional[str] = None,
        context_query: Optional[str] = None,
        context_keywords: Optional[List[str]] = None,
        context_scene: Optional[str] = None,
        use_intelligent_retrieval: bool = True,
    ) -> List[Skill]:
        """获取 Agent 运行时应加载的 Skills 列表。"""
        skills_with_params = await self._load_skills_for_agent(
            agent_type,
            project_id=project_id,
            context_query=context_query,
            context_keywords=context_keywords,
            context_scene=context_scene,
            use_intelligent_retrieval=use_intelligent_retrieval,
        )

        result: List[Skill] = []
        seen_ids: Set[str] = set()
        for skill, _ in skills_with_params:
            if not skill.is_enabled or skill.status.value != 'active':
                continue
            if skill.id in seen_ids:
                continue
            seen_ids.add(skill.id)
            result.append(skill)

        return result

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

        try:
            writing_rule_service = get_writing_rule_service()
            scope = await writing_rule_service.resolve_project_rule_scope(project_id)
            scope_summary = writing_rule_service.describe_project_rule_scope(scope)
            if not scope_summary.get("is_active"):
                return ""
            lines = [
                "## 写作规则检索协议",
                "- 写作前先按当前章节目标、环境、讨论摘要、角色状态检索相关写作规则。",
                "- 常驻规则只保留不可违反的高优先级约束；其余规则按需检索注入。",
                "- 场景、分段焦点或修订目标发生明显变化时，应再次检索。",
                f"- 当前作用域规则数：{scope_summary.get('resolved_rule_count', 0)}，基线规则集：{'是' if scope_summary.get('used_baseline') else '否'}。",
            ]
            return "\n".join(lines)
        except Exception as e:
            logger.error(f"构建写作规则 prompt 失败: {e}")
            return ""

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

    async def get_agent_skills_info(
        self,
        agent_type: str,
        project_id: Optional[str] = None,
        context_query: Optional[str] = None,
        context_keywords: Optional[List[str]] = None,
        context_scene: Optional[str] = None,
        use_intelligent_retrieval: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        获取 Agent 的 Skills 详细信息

        Args:
            agent_type: Agent 类型
            project_id: 项目 ID
            context_query: 场景描述/用户指令（用于智能检索）
            context_keywords: 上下文关键词列表（传统关键词匹配）
            context_scene: 当前场景类型（传统场景匹配）
            use_intelligent_retrieval: 是否使用智能检索

        Returns:
            List[Dict]: Skill 信息列表
        """
        skills_with_params = await self._load_skills_for_agent(
            agent_type,
            project_id=project_id,
            context_query=context_query,
            context_keywords=context_keywords,
            context_scene=context_scene,
            use_intelligent_retrieval=use_intelligent_retrieval,
        )

        result = []
        for skill, params in skills_with_params:
            result.append({
                "id": skill.id,
                "name": skill.name,
                "description": skill.description,
                "skill_type": skill.skill_type.value,
                "category": skill.category.value,
                "priority": skill.priority,
                "is_enabled": skill.is_enabled,
                "is_system": skill.is_system,
                "load_mode": skill.load_mode.value,
                "trigger_keywords": skill.trigger_keywords,
                "trigger_scenes": skill.trigger_scenes,
                "extracted_params": params,  # LLM 提取的参数
            })

        return result

    def extract_keywords_from_text(self, text: str) -> List[str]:
        """
        从文本中提取关键词（用于按需 Skill 匹配）

        简单实现：提取中文词汇和英文单词
        实际使用时可替换为更复杂的 NLP 方法

        Args:
            text: 输入文本

        Returns:
            List[str]: 关键词列表
        """
        import re

        if not text:
            return []

        keywords = []

        # 提取中文词汇（连续的中文字符）
        chinese_pattern = r'[\u4e00-\u9fff]+'
        chinese_matches = re.findall(chinese_pattern, text)
        keywords.extend(chinese_matches)

        # 提取英文单词
        english_pattern = r'[a-zA-Z]+'
        english_matches = re.findall(english_pattern, text)
        keywords.extend([w.lower() for w in english_matches])

        # 去重并保持顺序
        seen = set()
        unique_keywords = []
        for kw in keywords:
            if kw not in seen:
                seen.add(kw)
                unique_keywords.append(kw)

        return unique_keywords


# 全局单例
_agent_prompt_service: Optional[AgentPromptService] = None


def set_agent_prompt_service(prompt_template_service=None, agent_template_service=None):
    """设置 AgentPromptService 的运行时依赖。"""
    global _agent_prompt_service
    if _agent_prompt_service is None:
        _agent_prompt_service = AgentPromptService(
            prompt_template_service=prompt_template_service,
            agent_template_service=agent_template_service,
        )
    else:
        _agent_prompt_service.set_services(
            prompt_template_service=prompt_template_service,
            agent_template_service=agent_template_service,
        )


def get_agent_prompt_service() -> AgentPromptService:
    """获取 AgentPromptService 单例"""
    global _agent_prompt_service
    if _agent_prompt_service is None:
        _agent_prompt_service = AgentPromptService()
    return _agent_prompt_service
