"""
事件生成 Agent - 独立的世界事件生成器

职责：
1. 生成符合世界观的随机事件
2. 管理事件池和事件触发条件
3. 追踪事件对剧情的影响

与其他 Agent 的区别：
- ProcGenAgent: 生成地图区域
- WorldMapManagerAgent: 管理地图和位置
- EventGeneratorAgent: 生成和管理事件
"""

import logging
from typing import Any, Dict, List, Optional

from langchain_core.language_models import BaseLanguageModel
from langchain_core.messages import HumanMessage

from app.agents.base import BaseAgent, AgentResponse
from app.models.agent_output_schemas import EventGeneratorEventSchema
from app.models.agent_template import AgentType
from app.models.token_usage import UsageCategory
from app.services.structured_llm import StructuredOutputError

logger = logging.getLogger(__name__)


class EventGeneratorAgent(BaseAgent):
    """事件生成 Agent - 独立的世界事件管理器"""

    AGENT_TYPE = AgentType.EVENT_GENERATOR

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
            name="EventGeneratorAgent",
            model=model,
            system_prompt=system_prompt,
            config=config,
            project_id=project_id,
            agent_id=agent_id or "event_generator",
        )

        # 事件池缓存
        self._event_pool: List[Dict[str, Any]] = []

    def _get_default_variables(self) -> Dict[str, Any]:
        """获取默认变量"""
        return {
            "agent_role": "事件生成器",
            "task_description": "生成符合世界观的事件和剧情转折",
        }

    def _build_system_prompt(self) -> str:
        """构建系统提示"""
        return """你是事件生成器（Event Generator），专门负责为小说创作生成各类事件。

【核心职责】
1. 生成随机事件：根据世界观和剧情需要生成合适的事件
2. 事件池管理：维护可用事件的列表，确保事件多样性
3. 事件触发设计：为事件设计合理的触发条件和影响

【事件类型】
- 主线事件：推动剧情发展的关键事件
- 支线事件：丰富剧情的次要事件
- 随机事件：增加趣味性的随机遭遇
- 角色事件：与特定角色相关的事件
- 环境事件：天气、灾害等环境变化

【输出格式】
生成事件时，输出 JSON 格式：
```json
{
    "event_id": "event_xxx",
    "event_name": "事件名称",
    "event_type": "main/side/random/character/environment",
    "description": "事件描述",
    "trigger_condition": "触发条件",
    "participants": ["参与角色"],
    "consequences": ["事件影响"],
    "narrative_purpose": "叙事目的",
    "suggested_chapter": "建议出现章节"
}
```

【工作原则】
- 事件要有因果逻辑
- 要考虑对现有剧情的影响
- 事件要有戏剧张力
- 避免重复和陈腐的事件设计"""

    async def execute(self, input_data: Dict[str, Any]) -> AgentResponse:
        """
        执行事件生成任务

        Args:
            input_data: 包含以下字段
                - task: 任务类型 (generate/pool/query)
                - event_type: 事件类型
                - context: 上下文信息
                - characters: 相关角色
                - world_info: 世界观信息

        Returns:
            AgentResponse: 生成的事件数据
        """
        task = input_data.get("task", "generate")
        event_type = input_data.get("event_type", "random")
        context = input_data.get("context", {})
        characters = input_data.get("characters", [])
        world_info = input_data.get("world_info", {})

        try:
            if task == "pool":
                # 返回事件池
                return AgentResponse(
                    success=True,
                    data={"events": self._event_pool, "count": len(self._event_pool)},
                )

            # 生成事件
            prompt = self._build_generation_prompt(event_type, context, characters, world_info)

            response_parsed = await self._call_structured(
                EventGeneratorEventSchema,
                messages=[HumanMessage(content=prompt)],
                category=UsageCategory.PLOT,
            )
            event_data = response_parsed.model_dump()

            # 添加到事件池
            if event_data:
                self._event_pool.append(event_data)
                # 保持事件池大小
                if len(self._event_pool) > 50:
                    self._event_pool = self._event_pool[-50:]

            logger.info(f"事件生成成功: {event_data.get('event_name', 'N/A')}")

            return AgentResponse(
                success=True,
                data=event_data,
                metadata={"task": task, "event_type": event_type},
            )

        except StructuredOutputError as e:
            logger.error(f"事件生成 structured 失败: {e}")
            return AgentResponse(success=False, error=str(e))
        except Exception as e:
            logger.error(f"事件生成失败: {e}")
            return AgentResponse(success=False, error=str(e))

    def _build_generation_prompt(
        self,
        event_type: str,
        context: Dict[str, Any],
        characters: List[str],
        world_info: Dict[str, Any],
    ) -> str:
        """构建事件生成提示"""
        world_name = world_info.get("name") or "未命名世界"
        world_type = world_info.get("world_type") or world_info.get("description") or "未提供世界类型"
        character_names = [
            c if isinstance(c, str) else c.get("name", "未知角色")
            for c in (characters or [])
            if c
        ]

        chapter_outline = context.get("chapter_outline") or context.get("main_scene") or context.get("plot_focus") or "无章节大纲"
        chapter_goals = context.get("chapter_goals") or []
        lore_entries = context.get("lore_entries") or []
        lore_titles = []
        for entry in lore_entries[:20]:
            if isinstance(entry, dict):
                title = entry.get("title") or entry.get("name") or entry.get("summary")
                if title:
                    lore_titles.append(title)
            elif isinstance(entry, str):
                lore_titles.append(entry)

        prompt = f"""请基于当前项目上下文生成一个事件。

【世界观】
- 世界：{world_name}
- 类型/风格：{world_type}

【章节目标】
{chapter_goals if chapter_goals else '未提供'}

【当前剧情焦点】
{chapter_outline}

【相关角色】
{', '.join(character_names) if character_names else '无特定角色'}

【相关设定关键词】
{', '.join(lore_titles) if lore_titles else '未提供'}

【补充上下文】
{context.get('situation', '无特定情境')}

要求：
1. 事件必须严格贴合当前世界观与章节目标，禁止套用默认奇幻冒险套路。
2. 如果上下文体现了明确题材（如赛博朋克、科幻、都市、武侠等），事件必须使用对应题材语言和要素。
3. 参与者、触发条件、后果要尽量引用已有角色、设定和剧情目标。
4. 输出 JSON 格式。"""

        return prompt
