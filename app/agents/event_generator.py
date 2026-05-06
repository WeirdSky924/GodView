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
    DEFAULT_SCENARIO = "event_generation"

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
            name="EventGeneratorAgent",
            model=model,
            system_prompt=system_prompt,
            config=config,
            project_id=project_id,
            agent_id=agent_id or "event_generator",
        )
        if legacy_trace and not self.get_system_prompt_render_trace():
            self._system_prompt_render_trace = legacy_trace

        # 事件池缓存
        self._event_pool: List[Dict[str, Any]] = []

    def _get_default_variables(self) -> Dict[str, Any]:
        """获取默认变量"""
        return {
            "agent_role": "事件生成器",
            "task_description": "生成符合世界观的事件和剧情转折",
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
            logger.warning("加载 EventGenerator md prompt 失败: prompt_id=%s, error=%s", prompt_id, e)
        return ""

    def _build_md_event_generator_fallback_prompt(self) -> str:
        prompt_ids = ["role_event_generator", "function_event_generation"]
        parts = [content for prompt_id in prompt_ids if (content := self._load_md_prompt_content(prompt_id))]
        return "\n\n".join(parts).strip()

    def _event_generator_fallback_trace(self, *, deprecated: bool = False, prompt_ids: Optional[List[str]] = None) -> Dict[str, Any]:
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
            "fallbacks_used": ["event_generator_deprecated_minimal_system_prompt" if deprecated else "event_generator_md_prompt_fallback"],
            "deprecated_sources_used": ["EventGeneratorAgent._build_system_prompt"] if deprecated else [],
            "missing_prompt_ids": ["role_event_generator", "function_event_generation"] if deprecated else [],
        }

    def _build_system_prompt(self) -> str:
        """构建系统提示（优先使用 prompts/**/*.md 资产）。"""
        md_prompt = self._build_md_event_generator_fallback_prompt()
        if md_prompt:
            self._legacy_fallback_trace = self._event_generator_fallback_trace(
                prompt_ids=["role_event_generator", "function_event_generation"],
            )
            return md_prompt

        logger.warning("EventGenerator md prompt 资产不可用，使用 deprecated 最小硬编码默认系统提示")
        self._legacy_fallback_trace = self._event_generator_fallback_trace(deprecated=True)
        return """你是事件生成器。优先使用 Agent Template 绑定的 md prompt / skills / writing-rules；仅在未能加载配置资产时，将此最小提示作为 deprecated fallback。"""

    async def _ensure_system_prompt_loaded(self):
        """加载 EventGenerator Agent Template prompt，失败时回退到 md prompt 资产。"""
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
                context_query="事件生成 章节目标 因果链 当前阶段 长篇节奏",
            )
            prompt = prompt_data.get("content", "")
            self._system_prompt_render_trace = prompt_data.get("trace", {}) or {}
            if prompt.strip():
                self.system_prompt = prompt.strip()
        except Exception as e:
            logger.warning(
                "EventGenerator 加载模板 prompt 失败: project=%s, scenario=%s, error=%s",
                self.project_id,
                self.scenario,
                e,
            )

        if not self.system_prompt:
            md_prompt = self._build_md_event_generator_fallback_prompt()
            if md_prompt:
                self.system_prompt = md_prompt
                self._system_prompt_render_trace = self._event_generator_fallback_trace(
                    prompt_ids=["role_event_generator", "function_event_generation"],
                )
            else:
                self.system_prompt = self._build_system_prompt()
                self._system_prompt_render_trace = self._legacy_fallback_trace

        self._system_prompt_loaded = True
        self._pending_system_prompt_load = False

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
        raw_context = input_data.get("context")
        context = dict(input_data)
        if isinstance(raw_context, dict):
            context.update(raw_context)
        characters = input_data.get("characters") or context.get("characters", [])
        world_info = input_data.get("world_info") or context.get("world_info", {})

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
                metadata={"task": task, "event_type": event_type, **self._get_runtime_trace_metadata()},
            )

        except StructuredOutputError as e:
            logger.error(f"事件生成 structured 失败: {e}")
            return AgentResponse(success=False, error=str(e))
        except Exception as e:
            logger.error(f"事件生成失败: {e}")
            return AgentResponse(success=False, error=str(e))

    def _format_outline_text(self, outline: Any) -> str:
        if isinstance(outline, dict):
            parts = []
            title = outline.get("title")
            summary = outline.get("summary")
            goals = outline.get("chapter_goals") or []
            hooks = outline.get("hooks_planted") or []
            scenes = outline.get("scenes") or []

            if title:
                parts.append(f"标题：{title}")
            if summary:
                parts.append(f"摘要：{summary}")
            if goals:
                parts.append("章节目标：" + "；".join(str(goal) for goal in goals if goal))
            if hooks:
                parts.append("计划伏笔：" + "；".join(str(hook) for hook in hooks if hook))
            if scenes:
                scene_lines = []
                for scene in scenes:
                    if not isinstance(scene, dict):
                        continue
                    scene_title = scene.get("title") or f"场景{scene.get('scene_number', '')}"
                    scene_summary = scene.get("summary") or ""
                    key_events = scene.get("key_events") or []
                    event_text = f"；关键事件：{'、'.join(str(event) for event in key_events if event)}" if key_events else ""
                    scene_lines.append(f"- {scene_title}: {scene_summary}{event_text}")
                if scene_lines:
                    parts.append("场景安排：\n" + "\n".join(scene_lines))
            return "\n".join(parts) if parts else str(outline)
        return str(outline) if outline else "无章节大纲"

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

        chapter_num = context.get("chapter_num") or context.get("chapter_number")
        chapter_title = context.get("chapter_title")
        chapter_outline = context.get("chapter_outline") or context.get("main_scene") or context.get("plot_focus") or "无章节大纲"
        outline_text = self._format_outline_text(chapter_outline)
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

        event_instruction = self._load_md_prompt_content("function_event_generation") or "请生成符合世界观、章节目标和因果链的事件。"
        prompt = f"""{event_instruction}

【当前子任务参数】
- task_mode: current_chapter_event_generation
- event_type: {event_type}
- output_schema: EventGeneratorEventSchema

【当前章节】
- 章节号：{chapter_num or '未提供'}
- 章节标题：{chapter_title or (chapter_outline.get('title') if isinstance(chapter_outline, dict) else '未提供')}

【世界观】
- 世界：{world_name}
- 类型/风格：{world_type}

【章节目标】
{chapter_goals if chapter_goals else '未提供'}

【当前章节大纲】
{outline_text}

【相关角色】
{', '.join(character_names) if character_names else '无特定角色'}

【相关设定关键词】
{', '.join(lore_titles) if lore_titles else '未提供'}

【补充上下文】
{context.get('situation', '无特定情境')}"""

        return prompt
