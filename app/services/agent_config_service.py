"""
Agent 配置服务层
管理项目级别的 Agent 配置
"""

import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.models.agent_config import (
    ConfigOverrideType,
    SlotOverride,
    ModelConfig,
    AgentConfig,
    AgentConfigCreate,
    AgentConfigUpdate,
)
from app.models.agent_template import AgentType, AgentTemplate

logger = logging.getLogger(__name__)


class AgentConfigService:
    """Agent 配置服务"""

    def __init__(self, agent_template_service=None):
        # 内存存储（生产环境应使用数据库）
        self._configs: Dict[str, AgentConfig] = {}
        self._agent_template_service = agent_template_service

    # ==================== 基础 CRUD 操作 ====================

    async def get_or_create_config(
        self,
        project_id: str,
        agent_type: str,
        template_id: Optional[str] = None,
    ) -> AgentConfig:
        """获取或创建项目的 Agent 配置"""
        # 查找现有配置
        for config in self._configs.values():
            if config.project_id == project_id and config.agent_type == agent_type:
                return config

        # 创建新配置
        config_id = f"agent_cfg_{uuid.uuid4().hex[:12]}"
        config_name = f"{agent_type} 配置"

        # 如果有模板，基于模板创建
        if template_id and self._agent_template_service:
            template = await self._agent_template_service.get_template(template_id)
            if template:
                config_name = f"{template.name} (项目配置)"

        config = AgentConfig(
            id=config_id,
            project_id=project_id,
            agent_type=agent_type,
            name=config_name,
            description=f"项目 {project_id} 的 {agent_type} Agent 配置",
            template_id=template_id,
            is_custom=template_id is None,
        )

        self._configs[config_id] = config
        logger.info(f"创建 AgentConfig: {config_id} for project {project_id}, agent {agent_type}")

        return config

    async def get_config(self, config_id: str) -> Optional[AgentConfig]:
        """获取 Agent 配置"""
        return self._configs.get(config_id)

    async def get_config_by_project_agent(
        self, project_id: str, agent_type: str
    ) -> Optional[AgentConfig]:
        """获取项目特定 Agent 类型的配置"""
        for config in self._configs.values():
            if config.project_id == project_id and config.agent_type == agent_type:
                return config
        return None

    async def get_all_configs(
        self,
        project_id: str,
        agent_type: Optional[str] = None,
        is_active: Optional[bool] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[AgentConfig]:
        """获取项目的所有 Agent 配置"""
        configs = [c for c in self._configs.values() if c.project_id == project_id]

        # 按 Agent 类型过滤
        if agent_type:
            configs = [c for c in configs if c.agent_type == agent_type]

        # 按激活状态过滤
        if is_active is not None:
            configs = [c for c in configs if c.is_active == is_active]

        # 排序：按创建时间倒序
        configs.sort(key=lambda x: -x.created_at.timestamp())

        # 分页
        start = offset
        end = start + limit
        return configs[start:end]

    async def update_config(
        self, config_id: str, dto: AgentConfigUpdate
    ) -> Optional[AgentConfig]:
        """更新 Agent 配置"""
        config = self._configs.get(config_id)
        if not config:
            return None

        # 更新字段
        update_data = dto.dict(exclude_unset=True)
        for field, value in update_data.items():
            if value is not None:
                setattr(config, field, value)

        config.updated_at = datetime.now()
        logger.info(f"更新 AgentConfig: {config_id}")

        return config

    async def reset_config(self, config_id: str) -> Optional[AgentConfig]:
        """重置配置为模板默认值"""
        config = self._configs.get(config_id)
        if not config or not config.template_id:
            return None

        if not self._agent_template_service:
            logger.warning("AgentTemplateService 未注入，无法重置配置")
            return None

        # 获取模板
        template = await self._agent_template_service.get_template(config.template_id)
        if not template:
            logger.warning(f"模板不存在: {config.template_id}")
            return None

        # 重置配置
        config.slot_overrides = []
        config.custom_prompt_order = None
        config.llm_config = ModelConfig(
            model_name=template.default_model,
            temperature=template.default_temperature,
            max_tokens=template.default_max_tokens,
        )
        config.is_custom = False
        config.updated_at = datetime.now()

        logger.info(f"重置 AgentConfig {config_id} 为模板 {config.template_id} 默认值")
        return config

    # ==================== Prompt 构建和预览 ====================

    async def get_final_prompt(
        self,
        config_id: str,
        variables: Optional[Dict[str, Any]] = None,
    ) -> str:
        """获取最终拼接的 prompt"""
        config = self._configs.get(config_id)
        if not config:
            raise ValueError(f"配置不存在: {config_id}")

        if not self._agent_template_service:
            raise ValueError("AgentTemplateService 未注入，无法构建 prompt")

        # 获取模板
        template = None
        if config.template_id:
            template = await self._agent_template_service.get_template(config.template_id)

        if not template:
            # 如果没有模板，返回空字符串
            logger.warning(f"配置 {config_id} 没有关联模板，无法构建 prompt")
            return ""

        # 构建 prompt 片段列表
        prompt_pieces = []

        # 确定要使用的插槽顺序
        slot_order = config.custom_prompt_order or template.default_prompt_order

        for slot_name in slot_order:
            # 查找插槽定义
            slot_def = None
            for slot in template.prompt_slots:
                if slot.slot_name == slot_name:
                    slot_def = slot
                    break

            if not slot_def or not slot_def.is_enabled:
                continue

            # 检查是否有覆盖配置
            slot_override = None
            for override in config.slot_overrides:
                if override.slot_name == slot_name:
                    slot_override = override
                    break

            # 应用覆盖
            if slot_override:
                if slot_override.override_type == ConfigOverrideType.SLOT_DISABLE:
                    # 跳过禁用的插槽
                    continue
                elif slot_override.override_type == ConfigOverrideType.PROMPT_REPLACE:
                    # 使用新的 PromptTemplate
                    prompt_template_id = slot_override.prompt_template_id
                else:
                    # 使用原始插槽的 PromptTemplate
                    prompt_template_id = slot_def.prompt_template_id
            else:
                prompt_template_id = slot_def.prompt_template_id

            if not prompt_template_id:
                continue

            # TODO: 这里需要调用 PromptTemplateService 来获取和渲染 PromptTemplate
            # 目前返回占位符
            prompt_pieces.append(f"[{slot_name}: {prompt_template_id}]")

        # 合并所有片段
        final_prompt = "\n\n".join(prompt_pieces)

        # TODO: 应用变量插值
        if variables:
            # 这里应该实现变量替换
            pass

        return final_prompt

    async def preview_prompt(
        self,
        config_id: str,
        variables: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """预览 prompt（返回详细信息和渲染结果）"""
        config = self._configs.get(config_id)
        if not config:
            raise ValueError(f"配置不存在: {config_id}")

        # 获取最终 prompt
        final_prompt = await self.get_final_prompt(config_id, variables)

        # 获取模板信息
        template_info = None
        if config.template_id and self._agent_template_service:
            template = await self._agent_template_service.get_template(config.template_id)
            if template:
                template_info = {
                    "id": template.id,
                    "name": template.name,
                    "agent_type": template.agent_type,
                }

        return {
            "config_id": config_id,
            "project_id": config.project_id,
            "agent_type": config.agent_type,
            "template": template_info,
            "is_custom": config.is_custom,
            "llm_config": config.llm_config.dict(),
            "final_prompt": final_prompt,
            "prompt_length": len(final_prompt),
            "variables_used": variables or {},
        }

    # ==================== 配置验证 ====================

    async def validate_config(self, config_id: str) -> Dict[str, Any]:
        """验证配置的完整性"""
        config = self._configs.get(config_id)
        if not config:
            return {"valid": False, "error": "配置不存在"}

        issues = []

        # 如果有模板，验证模板是否存在
        if config.template_id and self._agent_template_service:
            template = await self._agent_template_service.get_template(config.template_id)
            if not template:
                issues.append(f"关联的模板不存在: {config.template_id}")
            else:
                # 验证插槽覆盖是否有效
                for override in config.slot_overrides:
                    slot_exists = any(
                        slot.slot_name == override.slot_name
                        for slot in template.prompt_slots
                    )
                    if not slot_exists:
                        issues.append(f"插槽覆盖指向不存在的插槽: {override.slot_name}")

        # 验证自定义顺序
        if config.custom_prompt_order:
            # 检查是否有重复
            if len(config.custom_prompt_order) != len(set(config.custom_prompt_order)):
                issues.append("自定义顺序中有重复的插槽")

        return {
            "valid": len(issues) == 0,
            "issues": issues,
            "config_id": config_id,
            "project_id": config.project_id,
            "agent_type": config.agent_type,
            "is_active": config.is_active,
            "usage_count": config.usage_count,
        }

    # ==================== 使用统计 ====================

    async def record_usage(self, config_id: str):
        """记录配置使用次数"""
        config = self._configs.get(config_id)
        if not config:
            return

        config.usage_count += 1
        config.last_used_at = datetime.now()
        config.updated_at = datetime.now()