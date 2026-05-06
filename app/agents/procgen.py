"""
世界生成 Agent - 程序化生成世界内容
"""

import logging
from typing import Any, Dict, List, Optional

from langchain_core.language_models import BaseLanguageModel
from langchain_core.messages import HumanMessage

from app.agents.base import BaseAgent, AgentResponse
from app.models.agent_output_schemas import ProcGenEncounterSchema, ProcGenRegionSchema
from app.models.world import World, Region, RegionType, TerrainType
from app.models.agent_template import AgentType
from app.models.token_usage import UsageCategory
from app.services.structured_llm import StructuredOutputError

logger = logging.getLogger(__name__)


class ProcGenAgent(BaseAgent):
    """世界生成 Agent"""

    AGENT_TYPE = AgentType.PROC_GEN
    DEFAULT_SCENARIO = "procedural_generation"

    def __init__(
        self,
        world: World,
        model: Optional[BaseLanguageModel] = None,
        config: Optional[Dict[str, Any]] = None,
        project_id: Optional[str] = None,
        system_prompt: Optional[str] = None,
        agent_id: Optional[str] = None,  # 新增：支持多实例
        agent_type: Optional[str] = None,
    ):
        self.world = world
        self.AGENT_TYPE = agent_type or self.__class__.AGENT_TYPE

        legacy_trace = None
        # 如果没有提供 system_prompt 且没有 project_id，使用 md prompt 资产 fallback（向后兼容）
        if not system_prompt and not project_id:
            system_prompt = self._build_system_prompt()
            legacy_trace = getattr(self, "_legacy_fallback_trace", None)

        super().__init__(
            name="ProcGenAgent",
            model=model,
            system_prompt=system_prompt,
            config=config,
            project_id=project_id,
            agent_id=agent_id,
        )
        if legacy_trace and not self.get_system_prompt_render_trace():
            self._system_prompt_render_trace = legacy_trace

    def _get_default_variables(self) -> Dict[str, Any]:
        """获取默认变量（ProcGen 特定）"""
        return {
            "agent_role": "造物主助理",
            "task_description": "根据世界观规则程序化生成新的区域和内容",
            "world_name": self.world.name,
            "world_type": self.world.world_type,
        }

    def _load_md_prompt_content(self, prompt_id: str) -> str:
        try:
            from app.services.md_file_service import get_md_file_service

            md_service = get_md_file_service()
            prompt = md_service.get_prompt(prompt_id)
            if prompt:
                content = prompt.get("content") or prompt.get("raw_content") or ""
                if content:
                    return content.strip()
        except Exception as e:
            logger.warning("加载 ProcGen md prompt 失败: prompt_id=%s, error=%s", prompt_id, e)
        return ""

    def _build_md_procgen_fallback_prompt(self) -> str:
        prompt_ids = ["role_proc_gen"]
        parts = [content for prompt_id in prompt_ids if (content := self._load_md_prompt_content(prompt_id))]
        return "\n\n".join(parts).strip()

    def _procgen_fallback_trace(self, *, deprecated: bool = False, prompt_ids: Optional[List[str]] = None) -> Dict[str, Any]:
        agent_type = self.AGENT_TYPE.value if hasattr(self.AGENT_TYPE, "value") else str(self.AGENT_TYPE)
        return {
            "agent_type": agent_type,
            "scenario": getattr(self, "scenario", None) or self.DEFAULT_SCENARIO,
            "project_id": getattr(self, "project_id", None),
            "template_id": None,
            "template_scenario": None,
            "config_id": None,
            "prompt_ids": prompt_ids or [],
            "skill_ids": [],
            "writing_rule_ids": [],
            "context_blocks": [],
            "fallbacks_used": ["proc_gen_deprecated_minimal_system_prompt" if deprecated else "proc_gen_md_prompt_fallback"],
            "deprecated_sources_used": ["ProcGenAgent._build_system_prompt"] if deprecated else [],
            "missing_prompt_ids": ["role_proc_gen"] if deprecated else [],
        }

    def _build_system_prompt(self) -> str:
        """构建系统提示（优先使用 prompts/**/*.md 资产）。"""
        md_prompt = self._build_md_procgen_fallback_prompt()
        world_block = "\n".join(
            [
                "【当前世界变量】",
                f"- 世界名称：{self.world.name}",
                f"- 世界类型：{self.world.world_type}",
                f"- 核心法则：{chr(10).join([r.description for r in self.world.rules[:3]]) if self.world.rules else '暂无特殊规则'}",
                f"- 力量体系：{self.world.power_system or '无特殊力量体系'}",
                f"- 科技水平：{self.world.technology_level or '未设定'}",
            ]
        )
        if md_prompt:
            self._legacy_fallback_trace = self._procgen_fallback_trace(prompt_ids=["role_proc_gen"])
            return f"{md_prompt}\n\n{world_block}"

        logger.warning("ProcGen md prompt 资产不可用，使用 deprecated 最小硬编码默认系统提示")
        self._legacy_fallback_trace = self._procgen_fallback_trace(deprecated=True)
        return f"""你是过程生成专家。优先使用 Agent Template 绑定的 md prompt / skills / writing-rules；仅在未能加载配置资产时，将此最小提示作为 deprecated fallback。

{world_block}"""

    async def _ensure_system_prompt_loaded(self):
        """加载 ProcGen Agent Template prompt，失败时回退到 md prompt 资产。"""
        if self._system_prompt_loaded or not self._pending_system_prompt_load:
            return

        if not self.project_id or not self.AGENT_TYPE:
            self._system_prompt_loaded = True
            self._pending_system_prompt_load = False
            return

        try:
            from app.services.agent_prompt_service import get_agent_prompt_service

            variables = self._get_default_variables()
            service = get_agent_prompt_service()
            agent_type = self.AGENT_TYPE.value if hasattr(self.AGENT_TYPE, "value") else str(self.AGENT_TYPE)
            prompt_data = await service.build_agent_prompt_with_trace(
                agent_type=agent_type,
                project_id=self.project_id,
                variables=variables,
                scenario=self.scenario,
                context_query=f"{self.world.name} 程序生成 区域 遭遇 世界规则 一致性",
            )
            prompt = prompt_data.get("content", "")
            self._system_prompt_render_trace = prompt_data.get("trace", {}) or {}
            if prompt.strip():
                self.system_prompt = prompt.strip()
        except Exception as e:
            logger.warning(
                "ProcGen 加载模板 prompt 失败: project=%s, scenario=%s, error=%s",
                self.project_id,
                self.scenario,
                e,
            )

        if not self.system_prompt:
            md_prompt = self._build_md_procgen_fallback_prompt()
            world_block = "\n".join(
                [
                    "【当前世界变量】",
                    f"- 世界名称：{self.world.name}",
                    f"- 世界类型：{self.world.world_type}",
                    f"- 核心法则：{chr(10).join([r.description for r in self.world.rules[:3]]) if self.world.rules else '暂无特殊规则'}",
                    f"- 力量体系：{self.world.power_system or '无特殊力量体系'}",
                    f"- 科技水平：{self.world.technology_level or '未设定'}",
                ]
            )
            if md_prompt:
                self.system_prompt = f"{md_prompt}\n\n{world_block}"
                self._system_prompt_render_trace = self._procgen_fallback_trace(prompt_ids=["role_proc_gen"])
            else:
                self.system_prompt = self._build_system_prompt()
                self._system_prompt_render_trace = self._legacy_fallback_trace

        self._system_prompt_loaded = True
        self._pending_system_prompt_load = False

    async def execute(self, input_data: Dict[str, Any]) -> AgentResponse:
        """
        生成新区域内容

        Args:
            input_data: 包含以下字段
                - exploration_direction: 探索方向描述
                - current_location: 当前位置 ID
                - existing_regions: 已有区域列表（用于避免重复）
                - generation_type: 生成类型 (first_time/returning/expansion)

        Returns:
            AgentResponse: 生成的区域数据
        """
        try:
            exploration_direction = input_data.get("exploration_direction", "随机探索")
            current_location = input_data.get("current_location", None)
            existing_regions = input_data.get("existing_regions", [])
            generation_type = input_data.get("generation_type", "first_time")

            logger.info(f"ProcGenAgent 开始执行: exploration_direction={exploration_direction[:100] if exploration_direction else 'N/A'}, generation_type={generation_type}")

            # 构建用户消息
            user_message = self._build_user_message(
                exploration_direction=exploration_direction,
                current_location=current_location,
                existing_regions=existing_regions,
                generation_type=generation_type,
            )

            # 调用 LLM (structured)
            try:
                parsed = await self._call_structured(
                    ProcGenRegionSchema,
                    messages=[HumanMessage(content=user_message)],
                    category=UsageCategory.WORLD,
                )
                region_data = parsed.model_dump()
            except StructuredOutputError as e:
                logger.error(f"ProcGenAgent structured 失败: {e}")
                return AgentResponse(success=False, error=str(e))

            logger.info(f"ProcGenAgent structured 完成")

            # 放宽验证：只要求有 description，其他字段可选
            # 这样可以支持多种输出格式（事件、区域、地图等）
            if "description" not in region_data and "content" not in region_data:
                region_data["description"] = ""
                region_data["raw_response"] = True

            # 为缺少的字段提供默认值
            region_data.setdefault("region_name", region_data.get("name", "未命名区域"))
            region_data.setdefault("region_type", region_data.get("type", "custom"))
            region_data.setdefault("name", region_data.get("region_name", "未命名"))

            logger.info(f"ProcGenAgent 执行成功: name={region_data.get('name', region_data.get('region_name', 'N/A'))}")

            return AgentResponse(
                success=True,
                data=region_data,
                metadata={
                    "world_id": self.world.id,
                    "generation_type": generation_type,
                    **self._get_runtime_trace_metadata(),
                },
            )

        except Exception as e:
            import traceback
            logger.error(f"ProcGenAgent 执行失败：{e}")
            logger.error(traceback.format_exc())
            return AgentResponse(success=False, error=str(e))

    def _try_extract_any_json(self, text: str) -> Optional[Dict[str, Any]]:
        """尝试从文本中提取任何 JSON 对象"""
        import re
        import json

        # 尝试找 JSON 对象
        json_pattern = r'\{[\s\S]*\}'
        matches = re.findall(json_pattern, text)

        for match in matches:
            try:
                return json.loads(match)
            except json.JSONDecodeError:
                continue

        return None

    def _build_user_message(
        self,
        exploration_direction: str,
        current_location: Optional[str],
        existing_regions: List[Dict[str, Any]],
        generation_type: str,
    ) -> str:
        """构建用户消息"""
        message_parts = []

        # 探索方向
        message_parts.append(f"【探索方向】\n{exploration_direction}")

        # 当前位置
        if current_location:
            message_parts.append(f"【当前位置】\n{current_location}")

        # 生成类型：仅输出运行时参数；稳定含义由 role_proc_gen md 资产维护
        generation_type_context = {
            "first_time": {"mode": "first_time", "requires_full_region": True},
            "returning": {"mode": "returning", "prefer_existing_region_changes": True},
            "expansion": {"mode": "expansion", "prefer_adjacent_region": True},
        }
        message_parts.append(f"【生成类型】\n{generation_type_context.get(generation_type, {'mode': generation_type})}")

        # 已有区域（避免重复）
        if existing_regions:
            region_names = [r.get("name", "") for r in existing_regions[:10]]
            message_parts.append(f"【已有区域参考】\n{', '.join(region_names)}")
            message_parts.append("【重复控制参数】\n- existing_region_count: " + str(len(existing_regions)))

        message_parts.append("【运行时任务参数】\n" + "\n".join(
            [
                "- task_mode: region_generation",
                "- output_schema: ProcGenRegionSchema",
                "- generation_type: " + str(generation_type),
            ]
        ))

        return "\n\n".join(message_parts)

    async def generate_encounter(
        self, region: Region, context: Dict[str, Any]
    ) -> AgentResponse:
        """
        生成特定区域的遭遇事件

        Args:
            region: 区域对象
            context: 上下文信息（角色、时间等）

        Returns:
            AgentResponse: 遭遇事件数据
        """
        procgen_instruction = self._load_md_prompt_content("role_proc_gen") or "请根据区域上下文生成合理、可用且与世界观一致的遭遇事件。"
        prompt = f"""{procgen_instruction}

【当前子任务参数】
- task_mode: encounter_generation
- output_schema: ProcGenEncounterSchema

【区域信息】
- 名称：{region.name}
- 类型：{region.region_type.value}
- 描述：{region.description}

【情境】
- 角色：{context.get('characters', [])}
- 时间：{context.get('time', '未知')}
- 天气：{context.get('weather', '未知')}"""

        try:
            parsed = await self._call_structured(
                ProcGenEncounterSchema,
                messages=[HumanMessage(content=prompt)],
                category=UsageCategory.WORLD,
            )
            encounter_data = parsed.model_dump()
            return AgentResponse(success=True, data=encounter_data)
        except StructuredOutputError as e:
            logger.error(f"生成遭遇事件 structured 失败: {e}")
            return AgentResponse(success=False, error=str(e))
        except Exception as e:
            logger.error(f"生成遭遇事件失败：{e}")
            return AgentResponse(success=False, error=str(e))
