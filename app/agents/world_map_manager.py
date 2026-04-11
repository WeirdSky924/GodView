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
from app.models.agent_template import AgentType
from app.models.token_usage import UsageCategory

logger = logging.getLogger(__name__)


class WorldMapManagerAgent(BaseAgent):
    """地图管理 Agent - 独立的世界地图管理者"""

    AGENT_TYPE = AgentType.PROC_GEN  # 复用枚举，但实际是独立 Agent

    def __init__(
        self,
        model: Optional[BaseLanguageModel] = None,
        config: Optional[Dict[str, Any]] = None,
        project_id: Optional[str] = None,
        system_prompt: Optional[str] = None,
        agent_id: Optional[str] = None,
    ):
        if not system_prompt:
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
        task = input_data.get("task", "query")
        region_id = input_data.get("region_id")
        region_data = input_data.get("region_data")
        character_id = input_data.get("character_id")
        direction = input_data.get("direction")
        world_info = input_data.get("world_info", {})

        try:
            if task == "query":
                # 查询地图
                return AgentResponse(
                    success=True,
                    data={
                        "regions": list(self._regions.values()),
                        "current_location": self._current_location,
                        "region_count": len(self._regions),
                    },
                )

            elif task == "move" and character_id and direction:
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
        world_name = world_info.get("name", "未知世界")
        world_type = world_info.get("world_type", "奇幻")

        prompt = f"""请为以下世界生成一个地图概述。

【世界信息】
- 名称：{world_name}
- 类型：{world_type}

请生成 3-5 个主要区域的概述，输出 JSON 格式：
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

        response_text = await self._call_llm(
            messages=[HumanMessage(content=prompt)],
            category=UsageCategory.WORLD,
        )

        map_data = self._parse_json_response(response_text)

        # 缓存区域
        for region in map_data.get("regions", []):
            region_id = f"region_{region.get('region_name', 'unknown')}"
            self._regions[region_id] = region

        return AgentResponse(
            success=True,
            data=map_data,
        )
