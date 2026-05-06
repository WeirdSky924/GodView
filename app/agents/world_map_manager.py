"""
地图管理 Agent - 独立的世界地图管理器

职责：
1. 管理世界地图和区域
2. 追踪角色位置
3. 生成新的地点和区域

与其他 Agent 的区别：
- ProcGenAgent: 生成地图区域（底层生成能力）
- EventGeneratorAgent: 生成事件
- WorldMapManagerAgent: 管理地图和位置（高层管理能力）
"""

import logging
from typing import Any, Dict, List, Optional

from langchain_core.language_models import BaseLanguageModel
from langchain_core.messages import HumanMessage

from app.agents.base import BaseAgent, AgentResponse
from app.models.agent_output_schemas import WorldMapOverviewSchema
from app.models.agent_template import AgentType
from app.models.token_usage import UsageCategory
from app.services.structured_llm import StructuredOutputError

logger = logging.getLogger(__name__)


class WorldMapManagerAgent(BaseAgent):
    """地图管理 Agent - 独立的世界地图管理者"""

    AGENT_TYPE = AgentType.WORLD_MAP_MANAGER
    DEFAULT_SCENARIO = "world_map_management"

    def __init__(
        self,
        model: Optional[BaseLanguageModel] = None,
        config: Optional[Dict[str, Any]] = None,
        project_id: Optional[str] = None,
        system_prompt: Optional[str] = None,
        agent_id: Optional[str] = None,
    ):
        legacy_trace = None
        if not system_prompt and not project_id:
            system_prompt = self._build_system_prompt()
            legacy_trace = getattr(self, "_legacy_fallback_trace", None)

        super().__init__(
            name="WorldMapManagerAgent",
            model=model,
            system_prompt=system_prompt,
            config=config,
            project_id=project_id,
            agent_id=agent_id or "world_map_manager",
        )
        if legacy_trace and not self.get_system_prompt_render_trace():
            self._system_prompt_render_trace = legacy_trace

        # 地图缓存
        self._regions: Dict[str, Dict[str, Any]] = {}
        self._current_location: Optional[str] = None

    def _get_default_variables(self) -> Dict[str, Any]:
        """获取默认变量"""
        return {
            "agent_role": "地图管理员",
            "task_description": "管理世界地图、区域和角色位置",
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
            logger.warning("加载 WorldMapManager md prompt 失败: prompt_id=%s, error=%s", prompt_id, e)
        return ""

    def _build_md_world_map_manager_fallback_prompt(self) -> str:
        prompt_ids = ["role_world_map_manager", "function_map_management"]
        parts = [content for prompt_id in prompt_ids if (content := self._load_md_prompt_content(prompt_id))]
        return "\n\n".join(parts).strip()

    def _world_map_manager_fallback_trace(self, *, deprecated: bool = False, prompt_ids: Optional[List[str]] = None) -> Dict[str, Any]:
        return {
            "agent_type": self.AGENT_TYPE.value,
            "scenario": getattr(self, "scenario", None) or self.DEFAULT_SCENARIO,
            "project_id": getattr(self, "project_id", None),
            "template_id": None,
            "template_scenario": None,
            "config_id": None,
            "prompt_ids": prompt_ids or [],
            "skill_ids": [],
            "writing_rule_ids": [],
            "context_blocks": [],
            "fallbacks_used": ["world_map_manager_deprecated_minimal_system_prompt" if deprecated else "world_map_manager_md_prompt_fallback"],
            "deprecated_sources_used": ["WorldMapManagerAgent._build_system_prompt"] if deprecated else [],
            "missing_prompt_ids": ["role_world_map_manager", "function_map_management"] if deprecated else [],
        }

    def _build_system_prompt(self) -> str:
        """构建系统提示（优先使用 prompts/**/*.md 资产）。"""
        md_prompt = self._build_md_world_map_manager_fallback_prompt()
        if md_prompt:
            self._legacy_fallback_trace = self._world_map_manager_fallback_trace(
                prompt_ids=["role_world_map_manager", "function_map_management"],
            )
            return md_prompt

        logger.warning("WorldMapManager md prompt 资产不可用，使用 deprecated 最小硬编码默认系统提示")
        self._legacy_fallback_trace = self._world_map_manager_fallback_trace(deprecated=True)
        return """你是地图管理员。优先使用 Agent Template 绑定的 md prompt / skills / writing-rules；仅在未能加载配置资产时，将此最小提示作为 deprecated fallback。"""

    async def _ensure_system_prompt_loaded(self):
        """加载 WorldMapManager Agent Template prompt，失败时回退到 md prompt 资产。"""
        if self._system_prompt_loaded or not self._pending_system_prompt_load:
            return

        if not self.project_id or not self.AGENT_TYPE:
            self._system_prompt_loaded = True
            self._pending_system_prompt_load = False
            return

        try:
            from app.services.agent_prompt_service import get_agent_prompt_service

            service = get_agent_prompt_service()
            prompt_data = await service.build_agent_prompt_with_trace(
                agent_type=self.AGENT_TYPE.value,
                project_id=self.project_id,
                variables=self._get_default_variables(),
                scenario=self.scenario,
                context_query="地图管理 地点匹配 区域生成 空间连续性 章节场景",
            )
            prompt = prompt_data.get("content", "")
            self._system_prompt_render_trace = prompt_data.get("trace", {}) or {}
            if prompt.strip():
                self.system_prompt = prompt.strip()
        except Exception as e:
            logger.warning(
                "WorldMapManager 加载模板 prompt 失败: project=%s, scenario=%s, error=%s",
                self.project_id,
                self.scenario,
                e,
            )

        if not self.system_prompt:
            md_prompt = self._build_md_world_map_manager_fallback_prompt()
            if md_prompt:
                self.system_prompt = md_prompt
                self._system_prompt_render_trace = self._world_map_manager_fallback_trace(
                    prompt_ids=["role_world_map_manager", "function_map_management"],
                )
            else:
                self.system_prompt = self._build_system_prompt()
                self._system_prompt_render_trace = self._legacy_fallback_trace

        self._system_prompt_loaded = True
        self._pending_system_prompt_load = False

    async def execute(self, input_data: Dict[str, Any]) -> AgentResponse:
        """
        执行地图管理任务

        Args:
            input_data: 包含以下字段
                - task: 任务类型 (query/create/move/update)
                - region_id: 区域 ID
                - region_data: 区域数据
                - character_id: 角色 ID
                - direction: 移动方向
                - world_info: 世界观信息

        Returns:
            AgentResponse: 地图数据
        """
        task = input_data.get("task")
        region_id = input_data.get("region_id")
        region_data = input_data.get("region_data")
        character_id = input_data.get("character_id")
        direction = input_data.get("direction")
        world_info = dict(input_data.get("world_info") or {})
        chapter_outline = input_data.get("chapter_outline") or input_data.get("plot_focus")
        if chapter_outline and "chapter_outline" not in world_info:
            world_info["chapter_outline"] = chapter_outline
        if input_data.get("scene_directions") and "scene_directions" not in world_info:
            world_info["scene_directions"] = input_data.get("scene_directions")
        existing_regions = input_data.get("existing_regions") or input_data.get("locations") or []

        if task is None:
            task = "match_or_generate" if chapter_outline else "query"

        try:
            if task == "query":
                # 查询地图
                return AgentResponse(
                    success=True,
                    data={
                        "regions": existing_regions or list(self._regions.values()),
                        "current_location": self._current_location,
                        "region_count": len(existing_regions or self._regions),
                    },
                    metadata=self._get_runtime_trace_metadata(),
                )

            elif task == "match_or_generate":
                return await self._match_or_generate_regions(world_info, existing_regions)
                # 移动角色
                return await self._handle_character_move(character_id, direction)

            elif task == "create" and region_data:
                # 创建新区域
                return await self._create_region(region_data, world_info)

            else:
                # 默认生成地图概述
                return await self._generate_map_overview(world_info)

        except Exception as e:
            logger.error(f"地图管理失败: {e}")
            return AgentResponse(success=False, error=str(e))

    def _format_outline_text(self, outline: Any, scene_directions: Any = None) -> str:
        if isinstance(outline, dict):
            parts = []
            title = outline.get("title")
            summary = outline.get("summary")
            scenes = outline.get("scenes") or []
            if title:
                parts.append(f"标题：{title}")
            if summary:
                parts.append(f"摘要：{summary}")
            scene_lines = []
            for scene in scenes:
                if not isinstance(scene, dict):
                    continue
                location = scene.get("location") or "未明确地点"
                scene_lines.append(f"- {scene.get('title', '未命名场景')}｜地点：{location}｜{scene.get('summary', '')}")
            if scene_lines:
                parts.append("场景地点需求：\n" + "\n".join(scene_lines))
            return "\n".join(parts) if parts else str(outline)
        if scene_directions:
            return str(scene_directions)
        return str(outline) if outline else "未提供"

    async def _match_or_generate_regions(
        self,
        world_info: Dict[str, Any],
        existing_regions: List[Dict[str, Any]],
    ) -> AgentResponse:
        chapter_outline = world_info.get("chapter_outline")
        scene_directions = world_info.get("scene_directions")
        outline_text = self._format_outline_text(chapter_outline, scene_directions)

        if existing_regions:
            region_summaries = []
            for region in existing_regions[:20]:
                if not isinstance(region, dict):
                    continue
                name = region.get("name") or region.get("region_name") or "未命名区域"
                description = region.get("description") or ""
                region_type = region.get("region_type") or ""
                region_summaries.append(f"- {name}（{region_type}）：{description[:180]}")

            map_instruction = self._load_md_prompt_content("function_map_management") or "请遵循地图管理原则，优先复用现有地点并维护空间连续性。"
            prompt = f"""{map_instruction}

【当前子任务参数】
- task_mode: match_or_generate_regions
- output_schema: WorldMapOverviewSchema
- existing_region_count: {len(existing_regions)}

【当前章节大纲】
{outline_text}

【现有地图区域】
{chr(10).join(region_summaries)}"""
            try:
                parsed = await self._call_structured(
                    WorldMapOverviewSchema,
                    messages=[HumanMessage(content=prompt)],
                    category=UsageCategory.WORLD,
                )
                map_data = parsed.model_dump()
                return AgentResponse(
                    success=True,
                    data={**map_data, "existing_region_count": len(existing_regions)},
                    metadata=self._get_runtime_trace_metadata(),
                )
            except StructuredOutputError as e:
                logger.error(f"地图匹配 structured 失败: {e}")
                return AgentResponse(success=False, error=str(e))

        return await self._generate_map_overview(world_info)

    async def _handle_character_move(
        self,
        character_id: str,
        direction: str,
    ) -> AgentResponse:
        """处理角色移动"""
        # 简化实现：返回移动结果
        return AgentResponse(
            success=True,
            data={
                "action": "move",
                "character_id": character_id,
                "direction": direction,
                "new_location": f"location_{direction}",
            },
            metadata=self._get_runtime_trace_metadata(),
        )

    async def _create_region(
        self,
        region_data: Dict[str, Any],
        world_info: Dict[str, Any],
    ) -> AgentResponse:
        """创建新区域"""
        region_id = region_data.get("region_id", f"region_{len(self._regions)}")
        self._regions[region_id] = region_data

        return AgentResponse(
            success=True,
            data={
                "action": "create",
                "region": region_data,
            },
            metadata=self._get_runtime_trace_metadata(),
        )

    async def _generate_map_overview(
        self,
        world_info: Dict[str, Any],
    ) -> AgentResponse:
        """生成地图概述"""
        world_name = world_info.get("name") or "未命名世界"
        world_type = world_info.get("world_type") or world_info.get("description") or "未提供世界类型"
        chapter_outline = world_info.get("chapter_outline") or world_info.get("plot_focus") or "未提供"
        scene_directions = world_info.get("scene_directions")
        chapter_outline_text = self._format_outline_text(chapter_outline, scene_directions)
        lore_entries = world_info.get("lore_entries") or []
        lore_titles = []
        for entry in lore_entries[:20]:
            if isinstance(entry, dict):
                title = entry.get("title") or entry.get("name") or entry.get("summary")
                if title:
                    lore_titles.append(title)
            elif isinstance(entry, str):
                lore_titles.append(entry)

        map_instruction = self._load_md_prompt_content("function_map_management") or "请遵循地图管理原则，生成与世界观和当前剧情匹配的区域概述。"
        prompt = f"""{map_instruction}

【当前子任务参数】
- task_mode: map_overview_generation
- output_schema: WorldMapOverviewSchema
- requested_region_count: 3-5

【世界信息】
- 名称：{world_name}
- 类型/风格：{world_type}
- 当前剧情焦点：{chapter_outline_text}
- 相关设定关键词：{', '.join(lore_titles) if lore_titles else '未提供'}"""

        try:
            parsed = await self._call_structured(
                WorldMapOverviewSchema,
                messages=[HumanMessage(content=prompt)],
                category=UsageCategory.WORLD,
            )
            map_data = parsed.model_dump()
        except StructuredOutputError as e:
            logger.error(f"地图概述 structured 失败: {e}")
            return AgentResponse(success=False, error=str(e))

        # 缓存区域
        for region in map_data.get("regions", []):
            region_id = f"region_{region.get('region_name', 'unknown')}"
            self._regions[region_id] = region

        return AgentResponse(
            success=True,
            data=map_data,
            metadata=self._get_runtime_trace_metadata(),
        )
