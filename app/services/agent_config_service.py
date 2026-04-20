"""
Agent 配置服务层
管理项目级别的 Agent 配置
"""

import json
import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.exc import ProgrammingError

from app.models.agent_config import (
    AgentConfig,
    AgentConfigCreate,
    AgentConfigUpdate,
    ModelConfig,
    SlotOverride,
)
from app.models.agent_template import AgentTemplate, AgentType

logger = logging.getLogger(__name__)


class AgentConfigService:
    """Agent 配置服务"""

    def __init__(self, db=None, agent_template_service=None):
        self._db = db
        self._configs: Dict[str, AgentConfig] = {}
        self._cache_valid: bool = False
        self._agent_template_service = agent_template_service

    @staticmethod
    def _normalize_agent_type(agent_type: Any) -> str:
        if isinstance(agent_type, AgentType):
            return agent_type.value
        return str(agent_type)

    async def _ensure_cache(self):
        """确保缓存有效"""
        if self._cache_valid:
            return

        self._configs.clear()

        if self._db:
            try:
                rows = await self._db.execute_query(
                    "SELECT * FROM agent_configs ORDER BY updated_at DESC, created_at DESC"
                )
                for row in rows:
                    config = self._row_to_config(row)
                    self._configs[config.id] = config
                logger.info(f"从数据库加载 {len(self._configs)} 个 Agent 配置")
            except ProgrammingError as e:
                error_text = str(e)
                if "relation \"agent_configs\" does not exist" in error_text or "UndefinedTableError" in error_text:
                    logger.warning("agent_configs 表不存在，先以空配置启动；需补跑 V7_prompt_management.sql")
                else:
                    logger.warning(f"从数据库加载 Agent 配置失败: {e}")
            except Exception as e:
                logger.warning(f"从数据库加载 Agent 配置失败: {e}")

        self._cache_valid = True

    def invalidate_cache(self):
        """使缓存失效"""
        self._cache_valid = False
        self._configs.clear()

    def _row_to_config(self, row: Dict[str, Any]) -> AgentConfig:
        """将数据库行转换为 AgentConfig"""
        slot_overrides = row.get("slot_overrides", [])
        if isinstance(slot_overrides, str):
            slot_overrides = json.loads(slot_overrides or "[]")

        custom_prompt_order = row.get("custom_prompt_order")
        if isinstance(custom_prompt_order, str):
            custom_prompt_order = json.loads(custom_prompt_order or "null")

        llm_config = row.get("model_config") or row.get("llm_config") or {}
        if isinstance(llm_config, str):
            llm_config = json.loads(llm_config or "{}")

        return AgentConfig(
            id=row["id"],
            project_id=str(row["project_id"]),
            agent_type=row["agent_type"],
            name=row.get("name", f"{row['agent_type']} 配置"),
            description=row.get("description", ""),
            template_id=row.get("template_id"),
            is_custom=row.get("is_custom", False),
            slot_overrides=[SlotOverride(**item) for item in slot_overrides],
            custom_prompt_order=custom_prompt_order,
            llm_config=ModelConfig(**llm_config),
            is_active=row.get("is_active", True),
            version=row.get("version", "1.0.0"),
            usage_count=row.get("usage_count", 0),
            last_used_at=row.get("last_used_at"),
            created_at=row.get("created_at", datetime.now()),
            updated_at=row.get("updated_at", datetime.now()),
        )

    def _config_to_db_dict(self, config: AgentConfig) -> Dict[str, Any]:
        """将 AgentConfig 转换为数据库字段"""
        return {
            "id": config.id,
            "project_id": config.project_id,
            "agent_type": config.agent_type,
            "name": config.name,
            "description": config.description,
            "template_id": config.template_id,
            "is_custom": config.is_custom,
            "slot_overrides": json.dumps(
                [item.model_dump(mode="json") for item in config.slot_overrides],
                ensure_ascii=False,
            ),
            "custom_prompt_order": json.dumps(config.custom_prompt_order, ensure_ascii=False),
            "model_config": json.dumps(config.llm_config.model_dump(mode="json"), ensure_ascii=False),
            "is_active": config.is_active,
            "version": config.version,
            "usage_count": config.usage_count,
            "last_used_at": config.last_used_at,
            "updated_at": config.updated_at,
        }

    async def _save_config(self, config: AgentConfig):
        """保存配置到数据库"""
        if not self._db:
            self._configs[config.id] = config
            return

        data = self._config_to_db_dict(config)
        columns = ", ".join(data.keys())
        placeholders = ", ".join([f":{k}" for k in data.keys()])
        updates = ", ".join([f"{k} = :{k}" for k in data.keys() if k != "id"])

        await self._db.execute_write(
            f"""
            INSERT INTO agent_configs ({columns})
            VALUES ({placeholders})
            ON CONFLICT (id) DO UPDATE SET
            {updates}
            """,
            data,
        )
        self._configs[config.id] = config

    async def _resolve_template_for_agent(
        self,
        project_id: str,
        agent_type: str,
        config: Optional[AgentConfig] = None,
    ) -> Optional[AgentTemplate]:
        """解析运行时实际使用的模板"""
        if not self._agent_template_service:
            return None

        await self._ensure_cache()
        normalized_agent_type = self._normalize_agent_type(agent_type)
        config = config or await self.get_config_by_project_agent(project_id, normalized_agent_type)

        if config and config.template_id:
            template = await self._agent_template_service.get_template(config.template_id)
            if template:
                return template

        try:
            return await self._agent_template_service.get_template_by_type(AgentType(normalized_agent_type))
        except ValueError:
            logger.debug(f"未知 AgentType，无法按类型解析模板: {normalized_agent_type}")
            return None

    # ==================== 基础 CRUD 操作 ====================

    async def get_or_create_config(
        self,
        project_id: str,
        agent_type: str,
        template_id: Optional[str] = None,
    ) -> AgentConfig:
        """获取或创建项目的 Agent 配置"""
        await self._ensure_cache()

        existing = await self.get_config_by_project_agent(project_id, agent_type)
        if existing:
            return existing

        template = None
        resolved_template_id = template_id
        if self._agent_template_service:
            if resolved_template_id:
                template = await self._agent_template_service.get_template(resolved_template_id)
            if not template:
                try:
                    template = await self._agent_template_service.get_template_by_type(AgentType(agent_type))
                    if template and not resolved_template_id:
                        resolved_template_id = template.id
                except ValueError:
                    template = None

        config_id = f"agent_cfg_{uuid.uuid4().hex[:12]}"
        config_name = f"{agent_type} 配置"
        llm_config = ModelConfig()
        if template:
            config_name = f"{template.name} (项目配置)"
            llm_config = ModelConfig(
                model_name=template.default_model or llm_config.model_name,
                temperature=template.default_temperature,
            )

        config = AgentConfig(
            id=config_id,
            project_id=project_id,
            agent_type=agent_type,
            name=config_name,
            description=f"项目 {project_id} 的 {agent_type} Agent 配置",
            template_id=resolved_template_id,
            is_custom=resolved_template_id is None,
            llm_config=llm_config,
        )

        await self._save_config(config)
        logger.info(f"创建 AgentConfig: {config_id} for project {project_id}, agent {agent_type}")
        return config

    async def get_config(self, config_id: str) -> Optional[AgentConfig]:
        """获取 Agent 配置"""
        await self._ensure_cache()
        return self._configs.get(config_id)

    async def get_config_by_project_agent(
        self, project_id: str, agent_type: str
    ) -> Optional[AgentConfig]:
        """获取项目特定 Agent 类型的配置"""
        await self._ensure_cache()
        normalized_agent_type = self._normalize_agent_type(agent_type)
        for config in self._configs.values():
            if config.project_id == project_id and config.agent_type == normalized_agent_type:
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
        await self._ensure_cache()
        configs = [c for c in self._configs.values() if c.project_id == project_id]

        if agent_type:
            configs = [c for c in configs if c.agent_type == agent_type]

        if is_active is not None:
            configs = [c for c in configs if c.is_active == is_active]

        configs.sort(key=lambda x: (-x.updated_at.timestamp(), -x.created_at.timestamp()))
        return configs[offset: offset + limit]

    async def update_config(
        self, config_id: str, dto: AgentConfigUpdate
    ) -> Optional[AgentConfig]:
        """更新 Agent 配置"""
        await self._ensure_cache()
        config = self._configs.get(config_id)
        if not config:
            return None

        update_data = dto.model_dump(exclude_unset=True)
        if "llm_config" in update_data and dto.llm_config is not None:
            update_data["llm_config"] = dto.llm_config
        if "slot_overrides" in update_data and dto.slot_overrides is not None:
            update_data["slot_overrides"] = dto.slot_overrides

        for field, value in update_data.items():
            if value is not None:
                setattr(config, field, value)

        config.updated_at = datetime.now()
        await self._save_config(config)
        logger.info(f"更新 AgentConfig: {config_id}")
        return config

    async def reset_config(self, config_id: str) -> Optional[AgentConfig]:
        """重置配置为模板默认值"""
        await self._ensure_cache()
        config = self._configs.get(config_id)
        if not config or not config.template_id:
            return None

        if not self._agent_template_service:
            logger.warning("AgentTemplateService 未注入，无法重置配置")
            return None

        template = await self._agent_template_service.get_template(config.template_id)
        if not template:
            logger.warning(f"模板不存在: {config.template_id}")
            return None

        config.slot_overrides = []
        config.custom_prompt_order = None
        config.llm_config = ModelConfig(
            model_name=template.default_model or config.llm_config.model_name,
            temperature=template.default_temperature,
            max_tokens=config.llm_config.max_tokens,
            top_p=config.llm_config.top_p,
            frequency_penalty=config.llm_config.frequency_penalty,
            presence_penalty=config.llm_config.presence_penalty,
        )
        config.is_custom = False
        config.updated_at = datetime.now()

        await self._save_config(config)
        logger.info(f"重置 AgentConfig {config_id} 为模板 {config.template_id} 默认值")
        return config

    # ==================== 运行时解析 ====================

    async def resolve_agent_runtime_state(
        self,
        project_id: str,
        agent_type: str,
    ) -> Dict[str, Any]:
        """解析 Agent 在当前项目下的运行时状态"""
        normalized_agent_type = self._normalize_agent_type(agent_type)
        config = await self.get_config_by_project_agent(project_id, normalized_agent_type)
        template = await self._resolve_template_for_agent(project_id, normalized_agent_type, config=config)

        if config and config.is_active is False:
            return {
                "enabled": False,
                "reason": "项目级 Agent 配置已禁用",
                "config": config,
                "template": template,
            }

        if template and template.is_optional and template.is_enabled is False:
            return {
                "enabled": False,
                "reason": "全局模板已禁用该可选 Agent",
                "config": config,
                "template": template,
            }

        return {
            "enabled": True,
            "reason": "enabled",
            "config": config,
            "template": template,
        }

    async def is_agent_enabled(self, project_id: str, agent_type: str) -> Tuple[bool, str]:
        """检查 Agent 是否在当前项目启用"""
        state = await self.resolve_agent_runtime_state(project_id, agent_type)
        return state["enabled"], state["reason"]

    # ==================== Prompt 构建和预览 ====================

    async def get_final_prompt(
        self,
        config_id: str,
        variables: Optional[Dict[str, Any]] = None,
    ) -> str:
        """获取最终拼接的 prompt"""
        config = await self.get_config(config_id)
        if not config:
            raise ValueError(f"配置不存在: {config_id}")

        from app.services.agent_prompt_service import get_agent_prompt_service

        prompt_service = get_agent_prompt_service()
        return await prompt_service.build_agent_prompt(
            agent_type=config.agent_type,
            project_id=config.project_id,
            variables=variables,
        )

    async def preview_prompt(
        self,
        config_id: str,
        variables: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """预览 prompt（返回详细信息和渲染结果）"""
        config = await self.get_config(config_id)
        if not config:
            raise ValueError(f"配置不存在: {config_id}")

        final_prompt = await self.get_final_prompt(config_id, variables)

        template_info = None
        if self._agent_template_service:
            template = await self._resolve_template_for_agent(
                config.project_id,
                config.agent_type,
                config=config,
            )
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
            "llm_config": config.llm_config.model_dump(mode="json"),
            "final_prompt": final_prompt,
            "prompt_length": len(final_prompt),
            "variables_used": variables or {},
        }

    # ==================== 配置验证 ====================

    async def validate_config(self, config_id: str) -> Dict[str, Any]:
        """验证配置的完整性"""
        config = await self.get_config(config_id)
        if not config:
            return {"valid": False, "error": "配置不存在"}

        issues = []

        if config.template_id and self._agent_template_service:
            template = await self._agent_template_service.get_template(config.template_id)
            if not template:
                issues.append(f"关联的模板不存在: {config.template_id}")
            else:
                for override in config.slot_overrides:
                    slot_exists = any(
                        slot.slot_name == override.slot_name
                        for slot in template.prompt_slots
                    )
                    if not slot_exists:
                        issues.append(f"插槽覆盖指向不存在的插槽: {override.slot_name}")

        if config.custom_prompt_order:
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
        config = await self.get_config(config_id)
        if not config:
            return

        config.usage_count += 1
        config.last_used_at = datetime.now()
        config.updated_at = datetime.now()
        await self._save_config(config)


_agent_config_service: Optional[AgentConfigService] = None


def set_agent_config_service(service: AgentConfigService):
    """设置 AgentConfigService 单例。"""
    global _agent_config_service
    _agent_config_service = service


def get_agent_config_service() -> AgentConfigService:
    """获取 AgentConfigService 单例。"""
    global _agent_config_service
    if _agent_config_service is None:
        from app.api.app import postgres_db
        from app.api.routes.agent_templates import get_agent_template_service

        _agent_config_service = AgentConfigService(
            db=postgres_db,
            agent_template_service=get_agent_template_service(),
        )
    return _agent_config_service
