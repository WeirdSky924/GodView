"""
伏笔管理员 Agent - 负责伏笔的埋设与回收

核心职责：
1. 管理项目中已有的伏笔（从数据库加载）
2. 根据剧情需要决定是否创建新伏笔
3. 识别伏笔回收的最佳时机
4. 更新伏笔状态
"""

import logging
from typing import Any, Dict, List, Optional

from langchain_core.language_models import BaseLanguageModel
from langchain_core.messages import HumanMessage

from app.agents.base import BaseAgent, AgentResponse
from app.models.agent_output_schemas import (
    HookManagerDecisionSchema,
    HookPlantSuggestionSchema,
    HookResolutionSuggestionSchema,
)
from app.models.agent_template import AgentType
from app.models.token_usage import UsageCategory
from app.services.structured_llm import StructuredOutputError

logger = logging.getLogger(__name__)


class HookManagerAgent(BaseAgent):
    """伏笔管理员 Agent"""

    AGENT_TYPE = AgentType.HOOK_MANAGER

    def __init__(
        self,
        model: Optional[BaseLanguageModel] = None,
        config: Optional[Dict[str, Any]] = None,
        project_id: Optional[str] = None,
        system_prompt: Optional[str] = None,
    ):
        # 如果没有提供 system_prompt 且没有 project_id，使用默认的硬编码 prompt（向后兼容）
        if not system_prompt and not project_id:
            system_prompt = self._build_default_system_prompt()

        super().__init__(
            name="HookManagerAgent",
            model=model,
            system_prompt=system_prompt,
            config=config,
            project_id=project_id,
        )

    def _get_default_variables(self) -> Dict[str, Any]:
        """获取默认变量（HookManager 特定）"""
        return {
            "agent_role": "伏笔管理员",
            "task_description": "负责管理故事伏笔的埋设与回收",
        }

    def _build_default_system_prompt(self) -> str:
        """构建默认系统提示"""
        return """你是伏笔管理员，负责管理小说中的伏笔系统。

## 核心职责

1. **管理现有伏笔** - 首先检查数据库中已有的伏笔，评估其状态
2. **战略性埋设** - 根据剧情发展需要，决定是否埋设新伏笔
3. **适时回收** - 识别已有伏笔回收的最佳时机
4. **状态追踪** - 更新伏笔的生命周期状态

## 伏笔类型

- **mystery** (谜团): 让读者产生疑问，期待后续解答
- **object** (物件): 与特殊物品、遗物、装备相关的伏笔
- **character** (角色): 与角色身份、动机、命运相关的伏笔
- **event** (事件): 与后续事件、事故、行动相关的伏笔
- **location** (地点): 与地点、地图、隐藏区域相关的伏笔
- **relationship** (关系): 与角色关系变化相关的伏笔
- **custom** (自定义): 不适合以上类型时使用

## 伏笔原则

1. **展示而非告知** - 通过细节、对话、行为暗示，而非直接说明
2. **自然融入** - 伏笔不应突兀，要与场景和角色行为融合
3. **有始有终** - 埋设的伏笔必须在合适时机回收
4. **情感价值** - 回收时能给读者带来惊喜或情感冲击

## 输出格式

```json
{
    "reasoning": "决策理由，说明为什么这样处理伏笔",
    "hooks_to_plant": [
        {
            "title": "伏笔标题",
            "description": "伏笔内容描述",
            "hook_type": "mystery/object/character/event/location/relationship/custom",
            "resolution_hint": "未来如何回收这个伏笔",
            "priority": 1-5,
            "related_characters": ["相关角色"],
            "related_objects": ["相关物品"]
        }
    ],
    "hooks_to_resolve": [
        {
            "id": "伏笔ID（从现有伏笔中选择）",
            "resolution_context": "回收的具体方式"
        }
    ],
    "hooks_status_updates": [
        {
            "id": "伏笔ID",
            "new_status": "triggered/ready_for_resolution",
            "reason": "状态变更原因"
        }
    ],
    "suggestions": ["对伏笔管理的建议"]
}
```

## 重要原则

- 不要随意创建新伏笔，优先考虑现有伏笔
- 如果现有伏笔已经足够，不需要新增
- 回收伏笔比创建新伏笔更重要
- 伏笔数量要适中，太多会让故事混乱"""

    async def execute(self, input_data: Dict[str, Any]) -> AgentResponse:
        """
        执行伏笔管理

        Args:
            input_data: 包含以下字段
                - existing_hooks: 数据库中的现有伏笔
                - hooks_planted_in_chapter: 本章节埋设的伏笔
                - hooks_resolved_in_chapter: 本章节回收的伏笔
                - plot_context: 剧情上下文
                - current_scene: 当前场景描述
                - recent_events: 最近发生的事件
                - chapter_goal: 章节目标

        Returns:
            AgentResponse: 伏笔管理决策
        """
        try:
            existing_hooks = input_data.get("existing_hooks", [])
            planted_in_chapter = input_data.get("hooks_planted_in_chapter", [])
            resolved_in_chapter = input_data.get("hooks_resolved_in_chapter", [])
            plot_context = input_data.get("plot_context", {})
            current_scene = input_data.get("current_scene", "")
            recent_events = input_data.get("recent_events", [])
            chapter_goal = input_data.get("chapter_goal", "")

            raw_chapter_outline = input_data.get("chapter_outline") or {}
            outline_hooks_to_plant = []
            outline_hooks_to_resolve = []
            outline_scene_summaries = []
            if isinstance(raw_chapter_outline, dict):
                outline_hooks_to_plant = [str(item) for item in raw_chapter_outline.get("hooks_planted", []) if item]
                outline_hooks_to_resolve = [str(item) for item in raw_chapter_outline.get("hooks_resolved", []) if item]
                for scene in raw_chapter_outline.get("scenes", []) or []:
                    if not isinstance(scene, dict):
                        continue
                    scene_text = scene.get("summary") or scene.get("title") or ""
                    if scene_text:
                        outline_scene_summaries.append(scene_text)
                    outline_hooks_to_plant.extend(str(item) for item in scene.get("hooks_to_plant", []) or [] if item)
                    outline_hooks_to_resolve.extend(str(item) for item in scene.get("hooks_to_resolve", []) or [] if item)

            if outline_hooks_to_plant:
                planted_in_chapter = list(dict.fromkeys([*planted_in_chapter, *outline_hooks_to_plant]))
            if outline_hooks_to_resolve:
                resolved_in_chapter = list(dict.fromkeys([*resolved_in_chapter, *outline_hooks_to_resolve]))
            if not current_scene and outline_scene_summaries:
                current_scene = "\n".join(f"- {summary}" for summary in outline_scene_summaries)
            if not chapter_goal:
                chapter_goal = input_data.get("chapter_summary") or (raw_chapter_outline.get("summary") if isinstance(raw_chapter_outline, dict) else "")

            # 构建用户消息
            user_message = self._build_user_message(
                existing_hooks=existing_hooks,
                planted_in_chapter=planted_in_chapter,
                resolved_in_chapter=resolved_in_chapter,
                plot_context=plot_context,
                current_scene=current_scene,
                recent_events=recent_events,
                chapter_goal=chapter_goal,
            )

            # 调用 LLM (structured)
            parsed = await self._call_structured(
                HookManagerDecisionSchema,
                messages=[HumanMessage(content=user_message)],
                temperature=0.5,
                category=UsageCategory.HOOK,
            )
            result = parsed.model_dump()
            result = self._postprocess_hook_result(result, existing_hooks)
            if not result.get("hooks_to_plant") and planted_in_chapter:
                result["hooks_to_plant"] = [
                    {
                        "title": hook[:40],
                        "description": hook,
                        "hook_type": "custom",
                        "resolution_hint": "根据后续章节大纲或剧情发展回收",
                        "priority": 3,
                        "related_characters": [],
                        "related_objects": [],
                    }
                    for hook in planted_in_chapter
                ]
                result["suggestions"] = [
                    *result.get("suggestions", []),
                    "已根据当前章节大纲补充待埋设伏笔建议。",
                ]
                result = self._postprocess_hook_result(result, existing_hooks)

            return AgentResponse(
                success=True,
                data=result,
                metadata={
                    "existing_hooks_count": len(existing_hooks),
                    "planted_in_chapter_count": len(planted_in_chapter),
                },
            )

        except StructuredOutputError as e:
            logger.error(f"HookManagerAgent structured 失败：{e}")
            return AgentResponse(success=False, error=str(e))
        except Exception as e:
            logger.error(f"HookManagerAgent 执行失败：{e}")
            return AgentResponse(success=False, error=str(e))

    def _normalize_hook_type(self, hook_type: Any) -> str:
        raw = str(hook_type or "").strip().lower()
        valid_types = {"mystery", "object", "character", "event", "location", "relationship", "custom"}
        if raw in valid_types:
            return raw
        alias_map = {
            "suspense": "mystery",
            "foreshadow": "custom",
            "foreshadowing": "custom",
            "twist": "event",
            "item": "object",
            "artifact": "object",
            "place": "location",
            "relation": "relationship",
        }
        return alias_map.get(raw, "custom")

    def _normalize_hook_priority(self, priority: Any) -> int:
        try:
            value = int(priority)
        except (TypeError, ValueError):
            value = 3
        return max(1, min(5, value))

    def _normalize_duplicate_key(self, title: Any, description: Any = "") -> str:
        title_key = " ".join(str(title or "").lower().split())
        desc_key = " ".join(str(description or "").lower().split())
        return f"{title_key}|{desc_key}"

    def _postprocess_hook_result(
        self,
        result: Dict[str, Any],
        existing_hooks: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        existing_keys = {
            self._normalize_duplicate_key(hook.get("title"), hook.get("description") or hook.get("plant_context"))
            for hook in existing_hooks
            if isinstance(hook, dict)
        }
        duplicate_candidates: List[Dict[str, Any]] = []
        filtered_hooks: List[Dict[str, Any]] = []
        seen_new: set[str] = set()
        for hook in result.get("hooks_to_plant", []) or []:
            if not isinstance(hook, dict):
                continue
            hook["hook_type"] = self._normalize_hook_type(hook.get("hook_type"))
            hook["priority"] = self._normalize_hook_priority(hook.get("priority"))
            duplicate_key = self._normalize_duplicate_key(hook.get("title"), hook.get("description"))
            if duplicate_key in existing_keys or duplicate_key in seen_new:
                duplicate_candidates.append({
                    "title": hook.get("title"),
                    "description": hook.get("description", ""),
                    "reason": "duplicate_existing_or_current_output",
                })
                continue
            seen_new.add(duplicate_key)
            filtered_hooks.append(hook)
        result["hooks_to_plant"] = filtered_hooks
        if duplicate_candidates:
            result["duplicate_candidates"] = [
                *result.get("duplicate_candidates", []),
                *duplicate_candidates,
            ]
        return result

    def _build_user_message(
        self,
        existing_hooks: List[Dict[str, Any]],
        planted_in_chapter: List[str],
        resolved_in_chapter: List[str],
        plot_context: Dict[str, Any],
        current_scene: str,
        recent_events: List[str],
        chapter_goal: str,
    ) -> str:
        """构建用户消息"""
        message_parts = []

        # 剧情上下文
        if plot_context:
            context_text = f"""
- 主线进度: {plot_context.get('main_plot_progress', 0):.1%}
- 当前章节: {plot_context.get('current_chapter', '未知')}
- 章节事件数: {plot_context.get('chapter_events_count', 0)}
- 活跃角色: {', '.join(plot_context.get('active_characters', []))}"""
            message_parts.append(f"【剧情上下文】{context_text}")

        # 章节目标
        if chapter_goal:
            message_parts.append(f"【章节目标】\n{chapter_goal}")

        # 当前场景
        if current_scene:
            message_parts.append(f"【当前场景】\n{current_scene}")

        # 最近事件
        if recent_events:
            message_parts.append(f"【最近发生的事件】\n{chr(10).join(f'- {e}' for e in recent_events)}")

        # 现有伏笔（重点！）
        if existing_hooks:
            hooks_text = []
            for h in existing_hooks[:15]:  # 最多显示15个
                status = h.get('status', 'unknown')
                title = h.get('title', '无标题')
                hook_type = h.get('hook_type', '未知')
                priority = h.get('priority', 5)
                desc = h.get('description', '')[:50]  # 截断描述
                hooks_text.append(f"- [{status}] {title} (类型:{hook_type}, 优先级:{priority})")
                if desc:
                    hooks_text.append(f"  描述: {desc}...")

            message_parts.append(f"【现有伏笔 ({len(existing_hooks)}个)】\n{chr(10).join(hooks_text)}")
            message_parts.append("⚠️ 以上是数据库中已存在的伏笔，请优先考虑如何利用和管理这些伏笔。")
        else:
            message_parts.append("【现有伏笔】\n暂无已存储的伏笔。")

        # 本章节伏笔状态
        if planted_in_chapter:
            message_parts.append(f"【本章节已埋设】\n{chr(10).join(f'- {h}' for h in planted_in_chapter)}")
        if resolved_in_chapter:
            message_parts.append(f"【本章节已回收】\n{chr(10).join(f'- {h}' for h in resolved_in_chapter)}")

        # 决策引导
        message_parts.append("""
【决策要点】

1. **伏笔回收优先**: 检查现有伏笔是否可以在当前场景回收
   - 回收时机是否合适？
   - 回收方式是否能产生"原来如此"的效果？

2. **伏笔状态更新**: 对于不能立即回收的伏笔
   - 是否已触发（开始显现）？
   - 是否需要调整优先级？

3. **新伏笔创建**: 需要同时从两个角度判断
   - 现有伏笔：是否已有伏笔可复用、推进、触发或回收？
   - 本章大纲：是否明确要求埋设新的伏笔？如有，应给出自然埋设方案
   - 新伏笔是否有明确的回收计划？
   - 是否与现有伏笔重复？
   - 是否对未来剧情有重要价值？

请输出 JSON 格式的决策。
""")

        return "\n\n".join(message_parts)

    async def suggest_hook_planting(
        self,
        hook: Dict[str, Any],
        scene_context: str,
        character_ids: List[str],
    ) -> AgentResponse:
        """
        建议特定伏笔的埋设方式

        Args:
            hook: 伏笔数据
            scene_context: 场景上下文
            character_ids: 在场角色 ID 列表

        Returns:
            AgentResponse: 埋设建议
        """
        prompt = f"""请为以下伏笔设计一个自然的埋设方式：

【伏笔信息】
- ID: {hook.get('id')}
- 标题：{hook.get('title')}
- 描述：{hook.get('description')}
- 类型：{hook.get('hook_type')}

【当前场景】
{scene_context}

【在场角色】
{', '.join(character_ids)}

要求：
1. 埋设方式要自然，不突兀
2. 符合"展示而非告知"原则
3. 与场景和角色行为融合

输出 JSON 格式：
{{
    "method": "埋设方式（如：对话暗示/物品发现/行为异常）",
    "context": "具体情境描述",
    "dialogue_hint": "暗示性台词（如有）",
    "attention_level": "low/medium/high"
}}"""

        try:
            parsed = await self._call_structured(
                HookPlantSuggestionSchema,
                messages=[HumanMessage(content=prompt)],
                temperature=0.6,
                category=UsageCategory.HOOK,
            )
            result = parsed.model_dump()
            return AgentResponse(success=True, data=result)
        except StructuredOutputError as e:
            logger.error(f"伏笔埋设建议 structured 失败：{e}")
            return AgentResponse(success=False, error=str(e))
        except Exception as e:
            logger.error(f"伏笔埋设建议失败：{e}")
            return AgentResponse(success=False, error=str(e))

    async def suggest_hook_resolution(
        self,
        hook: Dict[str, Any],
        current_context: str,
    ) -> AgentResponse:
        """
        建议特定伏笔的回收方式

        Args:
            hook: 伏笔数据
            current_context: 当前上下文

        Returns:
            AgentResponse: 回收建议
        """
        prompt = f"""请为以下伏笔设计一个令人满意的回收方式：

【伏笔信息】
- ID: {hook.get('id')}
- 标题：{hook.get('title')}
- 描述：{hook.get('description')}
- 埋设时的情境：{hook.get('plant_context', '未知')}

【当前上下文】
{current_context}

要求：
1. 回收要自然，有"原来如此"的感觉
2. 如果能产生情感冲击更好
3. 与当前情境融合

输出 JSON 格式：
{{
    "resolution": "回收方式描述",
    "emotional_impact": "low/medium/high",
    "ties_to_other_hooks": ["关联的其他伏笔 ID"],
    "suggested_dialogue": "揭示真相时的台词（如有）"
}}"""

        try:
            parsed = await self._call_structured(
                HookResolutionSuggestionSchema,
                messages=[HumanMessage(content=prompt)],
                temperature=0.5,
                category=UsageCategory.HOOK,
            )
            result = parsed.model_dump()
            return AgentResponse(success=True, data=result)
        except StructuredOutputError as e:
            logger.error(f"伏笔回收建议 structured 失败：{e}")
            return AgentResponse(success=False, error=str(e))
        except Exception as e:
            logger.error(f"伏笔回收建议失败：{e}")
            return AgentResponse(success=False, error=str(e))

    async def prioritize_hooks(
        self,
        pending_hooks: List[Dict[str, Any]],
        current_plot_progress: float,
    ) -> AgentResponse:
        """
        对待回收伏笔进行优先级排序

        Args:
            pending_hooks: 待回收伏笔列表
            current_plot_progress: 当前剧情进度

        Returns:
            AgentResponse: 排序后的伏笔列表
        """
        if not pending_hooks:
            return AgentResponse(
                success=True,
                data={"prioritized_hooks": [], "count": 0},
            )

        # 按优先级和剧情进度排序
        scored_hooks = []
        for hook in pending_hooks:
            base_priority = hook.get("priority", 1)
            # 剧情进度越靠后，高优先级伏笔权重越高
            progress_bonus = current_plot_progress * 2
            score = base_priority + progress_bonus
            scored_hooks.append({**hook, "priority_score": score})

        scored_hooks.sort(key=lambda x: x.get("priority_score", 0), reverse=True)

        return AgentResponse(
            success=True,
            data={
                "prioritized_hooks": scored_hooks,
                "count": len(scored_hooks),
            },
        )
