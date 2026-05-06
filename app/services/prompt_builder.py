"""
Prompt 构建器
负责构建完整的 prompt，处理模板拼接、变量插值、优先级排序等
"""

import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from app.models.agent_config import AgentConfig
from app.models.agent_template import AgentTemplate, PromptSlot
from app.models.prompt_template import PromptTemplate

logger = logging.getLogger(__name__)


class PromptBuilder:
    """Prompt 构建器"""

    def __init__(
        self,
        prompt_template_service=None,
        agent_template_service=None,
    ):
        self._prompt_template_service = prompt_template_service
        self._agent_template_service = agent_template_service

    # ==================== 主构建方法 ====================

    async def build_prompt(
        self,
        config: AgentConfig,
        template: AgentTemplate,
        variables: Optional[Dict[str, Any]] = None,
    ) -> str:
        """构建完整 prompt

        Args:
            config: Agent 配置
            template: Agent 模板
            variables: 变量值

        Returns:
            构建完成的 prompt 字符串
        """
        result = await self.build_prompt_with_trace(config, template, variables)
        return result["content"]

    async def build_prompt_with_trace(
        self,
        config: AgentConfig,
        template: AgentTemplate,
        variables: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """构建完整 prompt，并返回 PromptTemplate 解析/渲染 trace。"""
        # 获取要使用的插槽列表
        slot_order = config.custom_prompt_order or template.default_prompt_order
        enabled_slots = await self._get_enabled_slots(template, config)

        # 前端维护的 order 是 Agent-md 绑定关系的一部分，必须优先生效。
        # 未出现在 order 中的启用插槽再按 priority 追加，避免遗漏。
        ordered_slots = []
        used_slot_names = set()
        for slot_name in slot_order:
            if slot_name in enabled_slots:
                ordered_slots.append((slot_name, enabled_slots[slot_name]))
                used_slot_names.add(slot_name)

        remaining_slots = [
            (slot_name, slot)
            for slot_name, slot in enabled_slots.items()
            if slot_name not in used_slot_names
        ]
        ordered_slots.extend(self._sort_by_priority(remaining_slots))

        trace: Dict[str, Any] = {
            "prompt_ids": [],
            "context_blocks": [],
            "fallbacks_used": [],
            "deprecated_sources_used": [],
            "missing_prompt_ids": [],
        }

        # 构建 prompt 片段
        prompt_pieces = []
        for slot_name, slot in ordered_slots:
            slot_result = await self._build_slot_prompt_with_trace(
                slot, config, template, variables or {}
            )
            prompt_piece = slot_result.get("content")
            slot_trace = slot_result.get("trace", {})
            self._merge_trace(trace, slot_trace)
            if prompt_piece:
                prompt_pieces.append(prompt_piece)

        # 合并所有片段
        return {"content": "\n\n".join(prompt_pieces), "trace": trace}

    # ==================== 辅助方法 ====================

    async def _get_enabled_slots(
        self, template: AgentTemplate, config: AgentConfig
    ) -> Dict[str, PromptSlot]:
        """获取启用的插槽（考虑配置覆盖）"""
        enabled_slots = {}

        # 应用配置覆盖
        slot_overrides = {o.slot_name: o for o in config.slot_overrides}

        for slot in template.prompt_slots:
            slot_name = slot.slot_name

            # 检查是否被覆盖禁用
            if slot_name in slot_overrides:
                override = slot_overrides[slot_name]
                if override.override_type == "slot_disable":
                    continue
                # 其他覆盖类型不影响启用状态

            # 检查插槽本身是否启用
            if slot.is_enabled:
                enabled_slots[slot_name] = slot

        return enabled_slots

    def _sort_by_priority(
        self, slots: List[Tuple[str, PromptSlot]]
    ) -> List[Tuple[str, PromptSlot]]:
        """按优先级排序插槽（优先级高的在前）"""
        return sorted(slots, key=lambda x: -x[1].priority)

    async def _build_slot_prompt(
        self,
        slot: PromptSlot,
        config: AgentConfig,
        template: AgentTemplate,
        variables: Dict[str, Any],
    ) -> Optional[str]:
        """构建单个插槽的 prompt"""
        result = await self._build_slot_prompt_with_trace(slot, config, template, variables)
        return result.get("content")

    async def _build_slot_prompt_with_trace(
        self,
        slot: PromptSlot,
        config: AgentConfig,
        template: AgentTemplate,
        variables: Dict[str, Any],
    ) -> Dict[str, Any]:
        """构建单个插槽的 prompt，并记录模板解析 trace。"""
        trace: Dict[str, Any] = {
            "prompt_ids": [],
            "fallbacks_used": [],
            "deprecated_sources_used": [],
            "missing_prompt_ids": [],
        }
        # 获取要使用的 PromptTemplate ID
        prompt_template_id = await self._get_prompt_template_id(slot, config)
        if not prompt_template_id:
            return {"content": None, "trace": trace}

        if not self._prompt_template_service:
            trace["fallbacks_used"].append(f"missing_prompt_template_service:{prompt_template_id}")
            return {"content": None, "trace": trace}

        # 获取 PromptTemplate
        prompt_template = await self._prompt_template_service.get_template(
            prompt_template_id
        )
        if not prompt_template:
            logger.warning(f"PromptTemplate 不存在: {prompt_template_id}")
            trace["fallbacks_used"].append(f"missing_prompt_template:{prompt_template_id}")
            trace["missing_prompt_ids"].append(prompt_template_id)
            return {"content": None, "trace": trace}

        # 合并变量
        merged_variables = await self._merge_variables(
            prompt_template, slot, config, template, variables
        )

        # 渲染模板
        try:
            rendered = await self._render_template(prompt_template, merged_variables)
        except Exception as e:
            logger.warning(f"PromptTemplate 渲染失败，使用原始内容: {prompt_template_id}, error={e}")
            rendered = self._simple_render(prompt_template.content, merged_variables)
            trace["fallbacks_used"].append(f"prompt_template_raw:{prompt_template_id}")

        if rendered:
            trace["prompt_ids"].append(prompt_template_id)

        return {"content": rendered, "trace": trace}

    @staticmethod
    def _extend_unique(target: List[Any], values: Optional[List[Any]]) -> None:
        if not values:
            return
        seen = set(target)
        for value in values:
            if value in seen:
                continue
            seen.add(value)
            target.append(value)

    def _merge_trace(self, target: Dict[str, Any], source: Dict[str, Any]) -> None:
        for key in ("prompt_ids", "context_blocks", "fallbacks_used", "deprecated_sources_used", "missing_prompt_ids"):
            self._extend_unique(target.setdefault(key, []), source.get(key, []))

    async def _get_prompt_template_id(
        self, slot: PromptSlot, config: AgentConfig
    ) -> Optional[str]:
        """获取插槽使用的 PromptTemplate ID（考虑配置覆盖）"""
        # 检查配置覆盖
        for override in config.slot_overrides:
            if override.slot_name == slot.slot_name:
                if override.override_type == "prompt_replace":
                    return override.prompt_template_id
                # 其他覆盖类型不影响 PromptTemplate ID

        return slot.prompt_template_id

    async def _merge_variables(
        self,
        prompt_template: PromptTemplate,
        slot: PromptSlot,
        config: AgentConfig,
        template: AgentTemplate,
        variables: Dict[str, Any],
    ) -> Dict[str, Any]:
        """合并所有变量源"""
        merged = {}

        # 1. PromptTemplate 的默认值
        merged.update(prompt_template.default_values)

        # 2. 插槽的变量覆盖
        merged.update(slot.variable_overrides)

        # 3. 配置中的变量覆盖
        for override in config.slot_overrides:
            if (
                override.slot_name == slot.slot_name
                and override.override_type == "variable_override"
                and override.variable_values
            ):
                merged.update(override.variable_values)

        # 4. 调用时传入的变量（优先级最高）
        merged.update(variables)

        return merged

    async def _render_template(
        self,
        template: PromptTemplate,
        variables: Dict[str, Any],
    ) -> str:
        """渲染单个模板"""
        if not self._prompt_template_service:
            # 如果没有服务，简单替换
            return self._simple_render(template.content, variables)

        # 使用 PromptTemplateService 渲染
        from app.models.prompt_template import PromptRenderRequest

        request = PromptRenderRequest(
            template_id=template.id,
            variables=variables,
        )
        result = await self._prompt_template_service.render_template(request)
        return result.rendered_content

    def _simple_render(self, content: str, variables: Dict[str, Any]) -> str:
        """简单渲染（无服务依赖）"""
        rendered = content

        for var_name, var_value in variables.items():
            value = str(var_value)
            for placeholder in (f"{{{{{var_name}}}}}", f"{{{var_name}}}"):
                if placeholder in rendered:
                    rendered = rendered.replace(placeholder, value)

        return rendered

    # ==================== 工具方法 ====================

    def extract_variables(self, text: str) -> List[str]:
        """从文本中提取变量名"""
        pattern = r'\{([^{}]+)\}'
        matches = re.findall(pattern, text)
        # 去重并去除空格
        return list(set([match.strip() for match in matches]))

    async def validate_variables(
        self,
        template: PromptTemplate,
        provided_variables: Dict[str, Any],
    ) -> Tuple[bool, List[str], List[str]]:
        """验证变量是否完整"""
        required_vars = template.variables
        provided_var_names = list(provided_variables.keys())

        # 检查缺失的变量
        missing_vars = [var for var in required_vars if var not in provided_var_names]

        # 检查多余的变量
        extra_vars = [var for var in provided_var_names if var not in required_vars]

        is_valid = len(missing_vars) == 0
        return is_valid, missing_vars, extra_vars

    async def estimate_tokens(
        self,
        prompt: str,
        model_name: str = "gpt-4o-mini",
    ) -> int:
        """估算 prompt 的 token 数量（简化版）"""
        # 简单估算：4个字符大约等于1个token
        char_count = len(prompt)
        estimated_tokens = max(1, char_count // 4)

        # 模型特定调整
        if "gpt-4" in model_name:
            # GPT-4 tokenizer 更高效
            estimated_tokens = estimated_tokens * 3 // 4
        elif "claude" in model_name.lower():
            # Claude tokenizer 有所不同
            estimated_tokens = estimated_tokens * 5 // 4

        return estimated_tokens

    # ==================== 批量构建 ====================

    async def build_multiple_prompts(
        self,
        configs: List[AgentConfig],
        variables_map: Optional[Dict[str, Dict[str, Any]]] = None,
    ) -> Dict[str, str]:
        """批量构建多个配置的 prompt"""
        results = {}

        for config in configs:
            try:
                # 获取模板
                template = None
                if config.template_id and self._agent_template_service:
                    template = await self._agent_template_service.get_template(
                        config.template_id
                    )

                if not template:
                    logger.warning(f"配置 {config.id} 没有有效模板，跳过")
                    continue

                # 获取变量
                variables = {}
                if variables_map and config.id in variables_map:
                    variables = variables_map[config.id]

                # 构建 prompt
                prompt = await self.build_prompt(config, template, variables)
                results[config.id] = prompt

            except Exception as e:
                logger.error(f"构建配置 {config.id} 的 prompt 失败: {e}")
                results[config.id] = f"[构建失败: {str(e)}]"

        return results