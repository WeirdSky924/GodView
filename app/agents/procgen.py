"""
世界生成 Agent - 程序化生成世界内容
"""

import logging
from typing import Any, Dict, List, Optional

from langchain_core.language_models import BaseLanguageModel
from langchain_core.messages import HumanMessage

from app.agents.base import BaseAgent, AgentResponse
from app.models.world import World, Region, RegionType, TerrainType

logger = logging.getLogger(__name__)


class ProcGenAgent(BaseAgent):
    """世界生成 Agent"""

    def __init__(
        self,
        world: World,
        model: Optional[BaseLanguageModel] = None,
        config: Optional[Dict[str, Any]] = None,
    ):
        self.world = world
        system_prompt = self._build_system_prompt()
        super().__init__(
            name="ProcGenAgent",
            model=model,
            system_prompt=system_prompt,
            config=config,
        )

    def _build_system_prompt(self) -> str:
        """构建系统提示"""
        prompt = f"""你是造物主助理，负责根据世界观规则程序化生成新的区域和内容。

【世界观】
- 世界名称：{self.world.name}
- 世界类型：{self.world.world_type}
- 核心法则：{chr(10).join([r.description for r in self.world.rules[:3]]) if self.world.rules else '暂无特殊规则'}
- 力量体系：{self.world.power_system or '无特殊力量体系'}
- 科技水平：{self.world.technology_level or '未设定'}

请根据探索方向和世界观，生成合理的新区域内容。输出 JSON 格式：
{{
    "region_id": "自动生成的 ID",
    "region_name": "区域名称",
    "region_type": "区域类型 (city/village/wilderness/dungeon/building/water/mountain/forest)",
    "terrain_type": "地形类型 (plain/hill/mountain/desert/swamp/ice/volcano)",
    "description": "环境描述",
    "atmosphere": "氛围描述",
    "terrain_features": [{{"name": "特征名", "description": "特征描述"}}],
    "landmarks": [{{"name": "地标名", "description": "地标描述"}}],
    "encounters": [{{"type": "monster/npc/event/treasure", "name": "名称", "description": "描述", "weight": 1.0}}],
    "connections": ["相邻区域 ID 列表"],
    "loot": [{{"name": "物品名", "description": "描述"}}]
}}"""
        return prompt

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

            # 构建用户消息
            user_message = self._build_user_message(
                exploration_direction=exploration_direction,
                current_location=current_location,
                existing_regions=existing_regions,
                generation_type=generation_type,
            )

            # 调用 LLM
            response_text = await self._call_llm(
                messages=[HumanMessage(content=user_message)]
            )

            # 解析响应
            try:
                region_data = self._parse_json_response(response_text)
            except ValueError as e:
                return AgentResponse(
                    success=False, error=f"生成内容格式错误：{str(e)}"
                )

            # 验证必要字段
            required_fields = ["region_name", "region_type", "description"]
            missing_fields = [f for f in required_fields if f not in region_data]
            if missing_fields:
                return AgentResponse(
                    success=False, error=f"缺少必要字段：{', '.join(missing_fields)}"
                )

            return AgentResponse(
                success=True,
                data=region_data,
                metadata={
                    "world_id": self.world.id,
                    "generation_type": generation_type,
                },
            )

        except Exception as e:
            logger.error(f"ProcGenAgent 执行失败：{e}")
            return AgentResponse(success=False, error=str(e))

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

        # 生成类型
        type_desc = {
            "first_time": "首次探索，需要完整生成",
            "returning": "返回已访问区域，可生成新事件",
            "expansion": "世界扩展，生成相邻区域",
        }
        message_parts.append(f"【生成类型】\n{type_desc.get(generation_type, '未知')}")

        # 已有区域（避免重复）
        if existing_regions:
            region_names = [r.get("name", "") for r in existing_regions[:10]]
            message_parts.append(f"【已有区域参考】\n{', '.join(region_names)}")
            message_parts.append("请避免生成风格重复的区域。")

        message_parts.append(
            "\n请根据以上信息，生成一个符合世界观的新区域。"
            "确保区域设计有趣、有探索价值，并能与现有世界产生联系。"
        )

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
        prompt = f"""根据以下情境生成一个遭遇事件：

【区域信息】
- 名称：{region.name}
- 类型：{region.region_type.value}
- 描述：{region.description}

【情境】
- 角色：{context.get('characters', [])}
- 时间：{context.get('time', '未知')}
- 天气：{context.get('weather', '未知')}

请生成一个符合区域特色的遭遇事件。输出 JSON 格式：
{{
    "id": "enc_xxx",
    "type": "monster/npc/event/treasure",
    "name": "事件名称",
    "description": "详细描述",
    "data": {{...}},
    "weight": 1.0
}}"""

        try:
            response_text = await self._call_llm(
                messages=[HumanMessage(content=prompt)]
            )
            encounter_data = self._parse_json_response(response_text)
            return AgentResponse(success=True, data=encounter_data)
        except Exception as e:
            logger.error(f"生成遭遇事件失败：{e}")
            return AgentResponse(success=False, error=str(e))
