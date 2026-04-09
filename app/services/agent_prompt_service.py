# -*- coding: utf-8 -*-
"""
Agent Prompt 服务
负责动态加载和组装 Agent 的完整 system prompt
"""

import logging
from typing import Any, Dict, List, Optional

from app.data.system_prompts import SYSTEM_PROMPTS, PROMPTS_FOR_AGENT_TYPE
from app.data.system_agent_templates import TEMPLATES_BY_TYPE, SYSTEM_AGENT_TEMPLATES
from app.models.agent_template import AgentTemplate, AgentType
from app.models.prompt_template import PromptTemplate
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
    ) -> str:
        """
        构建 Agent 的完整 system prompt

        Args:
            agent_type: Agent 类型
            project_id: 项目ID（用于加载写作规则等）
            variables: 模板变量

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

        for slot in sorted_slots:
            if not slot.is_enabled:
                continue

            # 特殊处理：writing_rules 插槽
            if slot.slot_name == "writing_rules":
                writing_prompt = await self._build_writing_rules_prompt(project_id)
                if writing_prompt:
                    prompt_pieces.append(writing_prompt)
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
                "model": template.default_model,
                "temperature": template.default_temperature,
            }
        return summary


# 全局单例
_agent_prompt_service: Optional[AgentPromptService] = None


def get_agent_prompt_service() -> AgentPromptService:
    """获取 AgentPromptService 单例"""
    global _agent_prompt_service
    if _agent_prompt_service is None:
        _agent_prompt_service = AgentPromptService()
    return _agent_prompt_service
