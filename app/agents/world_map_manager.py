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

    def __init__(
        self,
        model: Optional[BaseLanguageModel] = None,
        config: Optional[Dict[str, Any]] = None,
        project_id: Optional[str] = None,
        system_prompt: Optional[str] = None,
        agent_id: Optional[str] = None,
    ):
        if not system_prompt and not project_id:
            system_prompt = self._build_system_prompt()

        super().__init__(
            name="WorldMapManagerAgent",
            model=model,
            system_prompt=system_prompt,
            config=config,
            project_id=project_id,
            agent_id=agent_id or "world_map_manager",
        )

        # 地图缓存
        self._regions: Dict[str, Dict[str, Any]] = {}
        self._current_location: Optional[str] = None

    def _get_default_variables(self) -> Dict[str, Any]:
        """获取默认变量"""
        return {
            "agent_role": "地图管理员",
            "task_description": "管理世界地图、区域和角色位置",
        }

    def _build_system_prompt(self) -> str:
        """构建系统提示"""
        return """你是地图管理员（World Map Manager），专门负责管理小说世界的地图和地点。

【核心职责】
1. 地图管理：维护世界地图的结构和区域信息
2. 位置追踪：追踪角色当前位置和移动路径
3. 区域生成：在需要时生成新的地点和区域

【地图层级】
- 世界（World）：整个故事世界
- 大陆/国家（Continent/Kingdom）：主要地理划分
- 区域（Region）：具体的地点，如城市、森林、山脉等
- 地点（Location）：区域内的具体位置，如酒馆、商店等

【输出格式】
管理地图时，输出 JSON 格式：
```json
{
    "action": "create/update/query/move",
    "region": {
        "region_id": "region_xxx",
        "region_name": "区域名称",
        "region_type": "city/village/wilderness/dungeon/...",
        "description": "区域描述",
        "connections": ["相邻区域"],
        "features": ["区域特征"]
    },
    "character_positions": {
        "character_id": "position"
    }
}
```

【工作原则】
- 保持地图的一致性
- 区域之间要有合理的连接
- 地点描述要有画面感
- 考虑地理位置对剧情的影响"""

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

            prompt = f"""请判断现有地图区域是否适合当前章节大纲的发展。

【当前章节大纲】
{outline_text}

【现有地图区域】
{chr(10).join(region_summaries)}

要求输出 JSON：
{{
  "overview": "判断说明：哪些地点可用，是否需要补充新地点",
  "regions": [
    {{"region_name": "区域名称", "region_type": "existing/new", "description": "用途说明", "importance": "为什么适合当前章节"}}
  ],
  "suggested_starting_location": "最适合本章开场的地点"
}}

规则：
1. 优先复用现有地图区域。
2. 只有现有区域无法承载大纲里的关键场景时，才建议 new 区域。
3. 地点必须服务当前章节，不要生成与当前大纲无关的大地图。"""
            try:
                parsed = await self._call_structured(
                    WorldMapOverviewSchema,
                    messages=[HumanMessage(content=prompt)],
                    category=UsageCategory.WORLD,
                )
                map_data = parsed.model_dump()
                return AgentResponse(success=True, data={**map_data, "existing_region_count": len(existing_regions)})
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

        prompt = f"""请基于当前项目世界观生成地图/区域概述。

【世界信息】
- 名称：{world_name}
- 类型/风格：{world_type}
- 当前剧情焦点：{chapter_outline_text}
- 相关设定关键词：{', '.join(lore_titles) if lore_titles else '未提供'}

要求：
1. 区域设计必须服务当前世界观与剧情，不得默认转向奇幻地下城套路。
2. 若世界观是赛博朋克/科幻/都市等，应体现对应空间形态、基础设施与社会氛围。
3. 输出 3-5 个与当前项目匹配的主要区域，JSON 格式：
{{
    "overview": "地图概述",
    "regions": [
        {{
            "region_name": "区域名称",
            "region_type": "类型",
            "description": "描述",
            "importance": "重要性"
        }}
    ],
    "suggested_starting_location": "建议的起始地点"
}}"""

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
        )
