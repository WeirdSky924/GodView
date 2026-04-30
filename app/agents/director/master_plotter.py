"""
总编剧 Agent - 把控主线进度和剧情走向
"""

import logging
from typing import Any, Dict, List, Optional

from langchain_core.language_models import BaseLanguageModel
from langchain_core.messages import HumanMessage

from app.agents.base import BaseAgent, AgentResponse
from app.models.agent_output_schemas import (
    MasterPlotterAdvanceSchema,
    MasterPlotterPlanSchema,
    MasterPlotterWritingPlanSchema,
)
from app.models.agent_template import AgentType
from app.models.token_usage import UsageCategory
from app.services.structured_llm import StructuredOutputError

logger = logging.getLogger(__name__)


class MasterPlotterAgent(BaseAgent):
    """总编剧 Agent"""

    AGENT_TYPE = AgentType.MASTER_PLOTTER

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
            name="MasterPlotterAgent",
            model=model,
            system_prompt=system_prompt,
            config=config,
            project_id=project_id,
        )

    def _as_list(self, value: Any) -> List[Any]:
        if value in (None, ""):
            return []
        if isinstance(value, list):
            return value
        if isinstance(value, tuple):
            return list(value)
        return [value]

    def _as_dict(self, value: Any) -> Dict[str, Any]:
        return value if isinstance(value, dict) else {}

    def _as_text(self, value: Any, fallback: str = "") -> str:
        if isinstance(value, str):
            return value
        if isinstance(value, (int, float, bool)):
            return str(value)
        return fallback

    def _get_default_variables(self) -> Dict[str, Any]:
        """获取默认变量（MasterPlotter 特定）"""
        return {
            "agent_role": "总编剧",
            "task_description": "把控主线进度和剧情走向",
        }

    def _build_default_system_prompt(self) -> str:
        """构建默认系统提示（向后兼容）"""
        return """你是总编剧，负责把控主线进度和剧情走向，并指导角色演绎环节。

【重要：长篇网文创作原则】
这是一部长篇小说，你需要确保：
1. **可持续发展**：剧情要能支撑后续几百章的发展，不要急于推进
2. **渐进式展开**：设定和秘密要逐步揭示，留有余地给后续剧情
3. **节奏把控**：避免开头即高潮的感觉，保持读者对后续内容的期待
4. **伏笔管理**：埋下的伏笔不要急于回收，长线伏笔能增加故事深度
5. **成长空间**：为主角和配角预留成长空间，不要让他们一开始就无敌
6. **世界观层次**：世界观要有递进层次，让读者感觉还有更深的内容待探索

【你的职责】
1. 评估当前剧情是否应该推进到下一阶段
2. 决定是否需要埋设"即将发生的事件"
3. 如果触发强制推进，提供合理的外部事件
4. 确保剧情不跑题、不拖沓
5. 控制节奏，不要让故事感觉急于完结

【角色演绎指导职责】
当需要为角色演绎环节设定场景时，你需要：
1. **场景选择**：选择能推进剧情的关键场景，避免无意义的日常
2. **场景类型**：
   - "interactive"（同场景互动）：适合角色对话、冲突、合作等需要互动的情节
   - "parallel"（独立场景）：适合角色各自行动、内心独白等独立情节
3. **角色分工**：为每个参与角色设定明确的定位和情绪状态
4. **剧情焦点**：明确本段表演要推进的核心剧情
5. **世界观融入**：确保表演中展现世界观元素
6. **伏笔暗示**：指示可以埋下的伏笔点

输出 JSON 格式：
{
    "should_advance": true/false,
    "reason": "判断理由",
    "current_progress": 0.0-1.0,
    "foreshadow_event": "即将发生的事件描述（如有）",
    "forced_event": "强制推进事件（如触发阈值）",
    "next_milestone": "下一个剧情里程碑",
    "pacing_note": "节奏调整建议（如：当前太快/太慢）",
    "long_term_setup": "为后续剧情埋下的铺垫建议",
    "scene_directions": {
        "scene_type": "interactive 或 parallel",
        "main_scene": "场景描述",
        "atmosphere": "氛围",
        "character_roles": {"角色名": {"role": "定位", "emotion": "情绪"}},
        "plot_focus": "剧情焦点"
    }
}"""

    def _extract_discussion_summary(self, discussion: Dict[str, Any]) -> str:
        """提取单条讨论记录的总结，优先读取统一后的 discussion 结构。"""
        if not isinstance(discussion, dict):
            return ""

        for key in ("summary", "full_content"):
            value = discussion.get(key, "")
            if isinstance(value, str) and value.strip():
                return value.strip()

        messages = discussion.get("messages", [])
        if isinstance(messages, list):
            for message in reversed(messages):
                if isinstance(message, dict):
                    content = message.get("content", "")
                    if isinstance(content, str) and content.strip():
                        return content.strip()

        return ""

    def _resolve_latest_discussion_summary(self, input_data: Dict[str, Any]) -> str:
        """提取当前输入中的最新讨论总结。"""
        discussion_summary = input_data.get("discussion_summary", "")
        if isinstance(discussion_summary, str) and discussion_summary.strip():
            return discussion_summary.strip()

        group_discussion = input_data.get("group_discussion") or {}
        summary = self._extract_discussion_summary(group_discussion)
        if summary:
            return summary

        legacy_summary = input_data.get("last_discussion_summary", "")
        if isinstance(legacy_summary, str):
            return legacy_summary.strip()
        return str(legacy_summary) if legacy_summary else ""

    def _extract_discussion_asset_context(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """提取已确认讨论资产，兼容直接字段与 group_discussion 嵌套字段。"""
        group_discussion = input_data.get("group_discussion") or {}
        if not isinstance(group_discussion, dict):
            group_discussion = {}

        assets = input_data.get("discussion_assets") or group_discussion.get("discussion_assets") or {}
        digest = input_data.get("discussion_asset_digest") or group_discussion.get("discussion_asset_digest") or {}
        persisted_refs = input_data.get("persisted_asset_refs") or {}
        committed = bool(input_data.get("discussion_assets_committed") or persisted_refs)

        return {
            "discussion_assets": assets if isinstance(assets, dict) else {},
            "discussion_asset_digest": digest if isinstance(digest, dict) else {},
            "persisted_asset_refs": persisted_refs if isinstance(persisted_refs, dict) else {},
            "discussion_assets_committed": committed,
        }

    def _format_discussion_asset_context(self, asset_context: Dict[str, Any]) -> str:
        """将讨论资产压缩为剧情规划可用摘要。"""
        assets = asset_context.get("discussion_assets") or {}
        digest = asset_context.get("discussion_asset_digest") or {}
        persisted_refs = asset_context.get("persisted_asset_refs") or {}
        if not assets and not digest and not persisted_refs:
            return ""

        def _labels(items: Any) -> List[str]:
            if not isinstance(items, list):
                return []
            labels: List[str] = []
            for item in items[:8]:
                if isinstance(item, dict):
                    label = item.get("title") or item.get("name") or item.get("id") or item.get("summary")
                    if label:
                        labels.append(str(label)[:100])
                elif item not in (None, ""):
                    labels.append(str(item)[:100])
            return labels

        lines = []
        topic = digest.get("topic") or assets.get("source_metadata", {}).get("topic")
        if topic:
            lines.append(f"讨论主题：{topic}")
        if asset_context.get("discussion_assets_committed"):
            lines.append("状态：已确认并提交，应作为后续剧情规划事实使用")
        elif assets:
            lines.append("状态：讨论资产提案，仅在已确认上下文中作为规划依据")

        sections = [
            ("剧情加码", _labels(assets.get("plot_updates"))),
            ("新增/待埋伏笔", _labels(assets.get("hooks"))),
            ("设定/世界观", _labels(assets.get("lore_candidates"))),
            ("地图/地点", _labels(assets.get("region_candidates"))),
            ("角色", _labels(assets.get("character_candidates"))),
        ]
        for title, labels in sections:
            if labels:
                lines.append(f"{title}：" + "；".join(labels))

        ref_lines = []
        for key, value in persisted_refs.items():
            if value:
                count = len(value) if isinstance(value, list) else 1
                ref_lines.append(f"{key}={count}")
        if ref_lines:
            lines.append("已持久化引用：" + "，".join(ref_lines))

        return "\n".join(lines)

    async def execute(self, input_data: Dict[str, Any]) -> AgentResponse:
        """
        执行主线剧情评估或规划

        Args:
            input_data: 包含以下字段
                - task: 任务类型（"advance" 或 "plan_plot"）
                - main_plot_progress: 主线进度 (0-1)
                - pending_hooks: 已埋设未回收的伏笔列表
                - chapter_goal: 当前章节目标
                - recent_events: 最近发生的事件
                - interaction_turns: 当前交互轮次
                - max_turns_threshold: 最大轮次阈值
                - initial_plot: 初始剧情设定（plan_plot 任务）
                - chapter_count: 章节数量（plan_plot 任务）
                - characters: 角色列表（plan_plot 任务）
                - world_info: 世界观信息（plan_plot 任务）

        Returns:
            AgentResponse: 剧情推进决策或规划结果
        """
        try:
            task = input_data.get("task", "advance")

            if task == "plan_plot":
                return await self._execute_plot_planning(input_data)
            if task in {"prepare_writing_plan", "writing_plan", "chapter_workflow_plan"}:
                return await self._execute_writing_plan(input_data)

            # 默认：剧情推进评估
            main_plot_progress = input_data.get("main_plot_progress", 0.0)
            pending_hooks = self._as_list(input_data.get("pending_hooks", []))
            chapter_goal = self._as_text(input_data.get("chapter_goal", ""))
            recent_events = self._as_list(input_data.get("recent_events", []))
            interaction_turns = input_data.get("interaction_turns", 0)
            max_turns_threshold = input_data.get("max_turns_threshold", 5)

            # 构建用户消息
            user_message = self._build_user_message(
                main_plot_progress=main_plot_progress,
                pending_hooks=pending_hooks,
                chapter_goal=chapter_goal,
                recent_events=recent_events,
                interaction_turns=interaction_turns,
                max_turns_threshold=max_turns_threshold,
            )

            # 调用 LLM (structured)
            parsed = await self._call_structured(
                MasterPlotterAdvanceSchema,
                messages=[HumanMessage(content=user_message)],
                temperature=0.5,
                category=UsageCategory.PLOT,
            )
            result = parsed.model_dump()

            # 检查是否需要强制推进
            if interaction_turns >= max_turns_threshold and not result.get("forced_event"):
                result["forced_event"] = await self._generate_forced_event(
                    recent_events=recent_events,
                    pending_hooks=pending_hooks,
                )

            return AgentResponse(
                success=True,
                data=result,
                metadata={
                    "progress": main_plot_progress,
                    "turns": interaction_turns,
                    "threshold": max_turns_threshold,
                },
            )

        except StructuredOutputError as e:
            logger.error(f"MasterPlotterAgent structured 失败: {e}")
            return AgentResponse(success=False, error=str(e))
        except Exception as e:
            logger.error(f"MasterPlotterAgent 执行失败：{e}")
            return AgentResponse(success=False, error=str(e))

    def _format_context_block(self, title: str, value: Any, max_chars: Optional[int] = None) -> str:
        if value in (None, "", [], {}):
            return ""
        if isinstance(value, str):
            text = value
        else:
            try:
                import json
                text = json.dumps(value, ensure_ascii=False, indent=2)
            except TypeError:
                text = str(value)
        text = text.strip()
        if not text:
            return ""
        return f"【{title}】\n{text}"

    async def _execute_writing_plan(self, input_data: Dict[str, Any]) -> AgentResponse:
        """为章节写作工作流生成索引/检查/写作计划，不覆盖章节事实源。"""
        chapter_outline = self._as_dict(input_data.get("chapter_outline", {}))
        chapter_goals = input_data.get("chapter_goals") or input_data.get("chapter_goal")
        scene_directions = input_data.get("scene_directions")
        performance_result = input_data.get("performance_result")
        fixed_lore_entries = self._as_list(input_data.get("fixed_lore_entries", []))
        dynamic_lore_entries = self._as_list(
            input_data.get("dynamic_lore_entries") or input_data.get("selected_lore_entries") or []
        )
        previous_chapters = self._as_list(input_data.get("previous_chapters", []))
        existing_hooks = self._as_list(input_data.get("existing_hooks", input_data.get("hooks", [])))
        characters = self._as_list(input_data.get("characters", []))
        target_word_count = input_data.get("target_word_count") or input_data.get("chapter_target_word_count")
        world_info = self._as_dict(input_data.get("world_info", {}))

        upcoming_outline_context = self._as_list(input_data.get("upcoming_outline_context", []))
        upcoming_outline_policy = input_data.get("upcoming_outline_policy")
        character_constraints = input_data.get("character_constraints")

        blocks = [
            self._format_context_block("绑定章节大纲（事实源，不可改写）", chapter_outline),
            self._format_context_block("章节目标", chapter_goals),
            self._format_context_block("目标字数", target_word_count),
            self._format_context_block("世界/项目规则", world_info),
            self._format_context_block("固定最高级设定", fixed_lore_entries),
            self._format_context_block("后续大纲参考", upcoming_outline_context),
            self._format_context_block("后续大纲策略", upcoming_outline_policy),
            self._format_context_block("角色出场硬约束", character_constraints),
            self._format_context_block("场景方向", scene_directions),
            self._format_context_block("场景演绎素材", performance_result),
            self._format_context_block("前文概要", previous_chapters, max_chars=2500),
            self._format_context_block("现有伏笔", existing_hooks, max_chars=2500),
            self._format_context_block("角色状态", characters, max_chars=2500),
        ]
        context_text = "\n\n".join(block for block in blocks if block)

        prompt = f"""你是章节工作流中的总编剧索引员。你的职责是整理上游状态，给 Writer 提供写作计划、检查清单和冲突提示。

{context_text if context_text else '（暂无上游上下文）'}

【硬性规则】
1. 绑定章节大纲是事实输入源，不能改写、替换或另起剧情。
2. 固定最高级设定优先于动态设定；动态设定优先于场景演绎素材。
3. 场景演绎素材只能作为写作素材，若与绑定大纲或固定设定冲突，必须标记冲突而不是采纳。
4. 不要输出顶层 chapter_outline 或 chapter_goals；如确实需要修订，只能放入 suggested_chapter_outline / suggested_chapter_goals。
5. 角色出场硬约束优先级高于场景演绎素材和集体讨论素材：只有 present_character_names 可作为当前场景正面参与者。
6. mentioned_only_names / forbidden_direct_appearance_names 中的角色只能作为传闻、回忆、姓名、势力或影响被提及，不能安排其直接出场、发言或行动。
7. 角色来源、历史、身份和背景必须遵守 category=character_setting 的设定；如素材冲突，写入 rewrite_or_skip / avoid，而不是采纳。
8. 如果已有后续大纲参考，写作计划和新角色候选必须服务后续剧情发展，不能只解决本章即时推进。
9. 如果没有后续大纲，不要擅自新建完整后续大纲；只按当前绑定大纲推进，并可在 future_setup / hook_usage 中提出轻量后续铺垫建议。
10. 当 present_character_names 中的主要角色不足以推动本章事件时，可以提出新的 supporting/recurring/catalyst/informant/npc 次要角色候选，但候选必须避开 mentioned_only_names / forbidden_direct_appearance_names，且必须给出可落库的姓名、定位、背景、目标和出场理由。

请输出 JSON：
{{
  "writing_plan": {{
    "chapter_focus": "本章核心焦点",
    "opening": "开篇承接方式",
    "middle_beats": ["中段剧情节拍"],
    "ending": "收束方式",
    "target_word_count": {target_word_count or 0}
  }},
  "plot_guidance": {{
    "must_include": ["必须出现的大纲要点"],
    "avoid": ["必须避免的偏离/冲突"],
    "hook_usage": ["可承接或新埋伏笔建议"]
  }},
  "scene_integration_plan": {{
    "use_from_performance": ["可整合的场景演绎素材"],
    "rewrite_or_skip": ["需改写或跳过的素材"]
  }},
  "required_elements_check": {{
    "outline_elements": [{{"item": "要素", "status": "covered/missing/conflict", "note": "说明"}}],
    "setting_elements": [{{"item": "设定", "status": "covered/missing/conflict", "note": "说明"}}]
  }},
  "supporting_character_plan": {{
    "needed": true/false,
    "reason": "如果主要角色不足以推进剧情，说明需要次要角色辅助的原因；否则说明不需要",
    "avoid_names": ["不得正面出场或不得借用的角色名"],
    "use_with_upcoming_outline": "如有后续大纲，说明候选角色如何服务后续章节；没有则写'无后续大纲，仅服务当前绑定大纲与轻量铺垫'"
  }},
  "character_candidates": [
    {{"name": "新次要角色姓名", "importance_tier": "supporting/recurring/catalyst/informant/npc", "description": "剧情功能定位", "appearance": "外貌", "personality": "性格", "background_story": "来源背景，必须符合设定", "goals": ["短期目标"], "reason_for_arrival": "为何此时出现并能推动剧情", "future_plot_usage": "如有后续大纲，说明后续用途"}}
  ],
  "outline_adherence_notes": ["大纲遵循提示"],
  "setting_conflict_warnings": ["设定冲突警告"],
  "suggested_chapter_outline": null,
  "suggested_chapter_goals": null
}}"""

        try:
            parsed = await self._call_structured(
                MasterPlotterWritingPlanSchema,
                messages=[HumanMessage(content=prompt)],
                temperature=0.4,
                category=UsageCategory.PLOT,
            )
            result = parsed.model_dump()
            result.pop("chapter_outline", None)
            result.pop("chapter_goals", None)
            return AgentResponse(success=True, data=result)
        except StructuredOutputError as e:
            logger.error(f"章节写作计划 structured 失败: {e}")
            return AgentResponse(success=False, error=str(e))
        except Exception as e:
            logger.error(f"章节写作计划失败: {e}")
            return AgentResponse(
                success=True,
                data={
                    "writing_plan": {
                        "chapter_focus": chapter_outline.get("summary") or self._as_text(chapter_goals),
                        "target_word_count": target_word_count,
                    },
                    "plot_guidance": {"must_include": [], "avoid": [], "hook_usage": []},
                    "supporting_character_plan": {
                        "needed": False,
                        "reason": "写作计划生成失败，未自动创建次要角色",
                        "avoid_names": [],
                        "use_with_upcoming_outline": "按当前绑定大纲保守推进",
                    },
                    "character_candidates": [],
                    "scene_integration_plan": {"use_from_performance": [], "rewrite_or_skip": []},
                    "required_elements_check": {},
                    "outline_adherence_notes": ["写作计划生成失败，使用绑定大纲作为保底事实源"],
                    "setting_conflict_warnings": [],
                },
            )

    async def _execute_plot_planning(self, input_data: Dict[str, Any]) -> AgentResponse:
        """
        执行整体剧情规划

        Args:
            input_data: 包含初始剧情、章节数、角色、世界观、讨论历史

        Returns:
            AgentResponse: 剧情规划结果
        """
        initial_plot = self._as_text(input_data.get("initial_plot", ""))
        chapter_count = input_data.get("chapter_count", 3)
        characters = self._as_list(input_data.get("characters", []))
        world_info = self._as_dict(input_data.get("world_info", {}))
        main_plot_progress = input_data.get("main_plot_progress", 0.0)
        recent_discussions = self._as_list(input_data.get("recent_discussions", []))
        last_discussion_summary = self._resolve_latest_discussion_summary(input_data)
        discussion_asset_context = self._extract_discussion_asset_context(input_data)
        discussion_asset_section = self._format_discussion_asset_context(discussion_asset_context)
        existing_hooks = self._as_list(input_data.get("existing_hooks", []))

        # 构建世界观部分（关键信息）
        world_section = ""
        if world_info:
            world_section = f"""
【世界观设定】
名称：{world_info.get('name', '未知世界')}
类型：{world_info.get('world_type', '奇幻')}
基调：{world_info.get('tone', '正剧')}
目标读者：{world_info.get('target_audience', '大众')}

【世界背景】
{world_info.get('description', '无详细描述')}
{chr(10) + world_info.get('background', '') if world_info.get('background') else ''}

【世界规则】
"""
            rules = world_info.get("rules", {})
            if isinstance(rules, dict):
                for key, value in rules.items():
                    world_section += f"- {key}: {value}\n"
            elif isinstance(rules, list):
                for rule in rules:
                    world_section += f"- {rule}\n"

            themes = self._as_list(world_info.get("themes", []))
            if themes:
                world_section += f"\n【核心主题】\n{chr(10).join([f'- {t}' for t in themes])}\n"
        else:
            world_section = """
【世界观设定】
（暂无世界观信息，请根据初始剧情自行推断）
"""

        # 构建角色部分
        characters_section = "【主要角色】\n"
        if characters:
            for char in characters:
                if isinstance(char, dict):
                    name = char.get("name", "未知角色")
                    role = char.get("role", char.get("character_type", ""))
                    desc = char.get("description", char.get("personality", ""))
                    characters_section += f"- {name}"
                    if role:
                        characters_section += f"（{role}）"
                    if desc:
                        characters_section += f": {desc}"
                    characters_section += "\n"
                else:
                    characters_section += f"- {char}\n"
        else:
            characters_section += "（暂无角色信息）\n"

        # 构建伏笔部分
        hooks_section = ""
        if existing_hooks:
            hook_lines = []
            for hook in existing_hooks:
                if isinstance(hook, dict):
                    hook_lines.append(f"- {hook.get('title', hook.get('id', '未知'))}: {hook.get('description', '')}")
                elif hook not in (None, ""):
                    hook_lines.append(f"- {hook}")
            hooks_section = f"""
【已有伏笔】
{chr(10).join(hook_lines)}
""" if hook_lines else ""

        # 构建讨论历史部分
        discussion_section = ""
        if recent_discussions:
            discussion_summaries = []
            for i, d in enumerate(recent_discussions[-2:]):  # 最近2次讨论
                if not isinstance(d, dict):
                    summary_text = self._as_text(d).strip()
                    if summary_text:
                        discussion_summaries.append(f"- 讨论{i+1}: {summary_text}")
                    continue
                topic = d.get("topic", f"讨论{i+1}")
                summary_text = self._extract_discussion_summary(d)
                if summary_text:
                    discussion_summaries.append(f"- {topic}: {summary_text}")
            if discussion_summaries:
                discussion_section = f"""
【团队讨论记录】
{chr(10).join(discussion_summaries)}

【最新讨论共识】
{last_discussion_summary if last_discussion_summary else '暂无'}
"""
        elif last_discussion_summary:
            discussion_section = f"""
【最新讨论共识】
{last_discussion_summary}
"""

        if discussion_asset_section:
            discussion_section += f"""
【已确认讨论资产】
{discussion_asset_section}
请在剧情规划中优先承接这些已确认的剧情加码、伏笔、地点、设定和角色信息；涉及已持久化资产时不要随意改名或改设定。
"""

        prompt = f"""你是一位资深网文编剧，现在需要根据以下信息规划一部小说的整体剧情大纲。
请确保剧情与世界观设定紧密结合，风格基调一致。

【重要：长篇网文创作原则】
这是一部长篇小说，你需要确保：
1. **可持续发展**：剧情要能支撑后续几百章的发展，不要急于推进到高潮
2. **渐进式展开**：设定和秘密要逐步揭示，让读者保持探索的好奇心
3. **节奏把控**：前面章节主要是铺垫和建立，高潮要在后期逐步展开
4. **伏笔管理**：埋下的伏笔不要急于回收，长线伏笔能增加故事深度
5. **成长空间**：为主角和配角预留成长空间，不要让他们一开始就无敌
6. **世界观层次**：世界观要有递进层次，让读者感觉还有更深的内容待探索

【角色演绎指导原则】
在规划章节时，你需要考虑角色演绎环节：
- 为每章规划关键的角色表演场景
- 明确角色的情绪状态和互动方式
- 指定场景类型（同场景互动 vs 独立场景）
- 确保表演能推进剧情，而非单纯的对话

{world_section}

{characters_section}

【初始剧情设定】
{initial_plot if initial_plot else '（无初始设定，请根据世界观自行构思）'}
{hooks_section}
【当前主线进度】
{main_plot_progress * 100:.1f}%
{discussion_section}
【目标】
规划 {chapter_count} 个章节的大纲

请输出 JSON 格式：
{{
    "overall_summary": "整体剧情概述（详细描述，需体现世界观特色和长篇格局）",
    "tone": "故事基调（如热血、黑暗、温馨、搞笑等）",
    "writing_style": "建议的写作风格",
    "pacing_strategy": "节奏策略（详细说明如何保持长篇的可持续发展）",
    "chapter_titles": ["第一章标题", "第二章标题", ...],
    "chapter_goals": [
        {{
            "goal": "本章主要目标",
            "key_events": ["关键事件1", "关键事件2"],
            "character_focus": ["重点关注角色"],
            "environment": "主要场景环境",
            "foreshadowing": "本章埋下的伏笔（如有）",
            "performance_directions": {{
                "scene_type": "interactive 或 parallel",
                "main_scene": "主要表演场景",
                "character_emotions": {{"角色名": "情绪状态"}},
                "plot_focus": "表演要推进的剧情点"
            }}
        }},
        ...
    ],
    "main_conflicts": ["主要冲突1", "主要冲突2", ...],
    "progression_phases": [
        {{"phase": "前期（1-X章）", "focus": "主要内容和目标"}},
        {{"phase": "中期（X-Y章）", "focus": "主要内容和目标"}},
        {{"phase": "后期（Y-Z章）", "focus": "主要内容和目标"}}
    ],
    "climax_chapter": 高潮章节编号,
    "ending_hint": "结局暗示",
    "world_elements_used": ["本小说将运用的世界观元素"],
    "long_term_hooks": ["长线伏笔（需要多章节才能回收）"],
    "discussion_considerations": ["根据讨论记录需要考虑的事项"]
}}

要求：
1. 章节标题要吸引人，符合网文风格，体现世界观特色
2. 每章目标要具体，包含冲突和转折，场景要结合世界观设定
3. 确保有起承转合，但前期不要急于推进到高潮
4. 伏笔要分为短线（近期回收）和长线（后期回收）两种
5. 必须与世界观设定保持一致，充分利用世界观的独特元素
6. 角色行为要符合其设定和世界观规则
7. 为每章规划角色表演场景，确保表演能推进剧情
8. 明确角色在表演中的情绪状态和互动方式
7. 如果有讨论记录，请在规划中体现讨论达成的共识和建议
8. 确保长篇小说的可持续发展，不要让读者感觉开头就是高潮"""

        try:
            parsed = await self._call_structured(
                MasterPlotterPlanSchema,
                messages=[HumanMessage(content=prompt)],
                temperature=0.7,
                category=UsageCategory.PLOT,
            )
            result = parsed.model_dump()

            # 确保返回必要字段
            if not result.get("chapter_titles"):
                result["chapter_titles"] = [f"第{i+1}章" for i in range(chapter_count)]
            if not result.get("chapter_goals"):
                result["chapter_goals"] = [initial_plot for _ in range(chapter_count)]

            return AgentResponse(success=True, data=result)

        except StructuredOutputError as e:
            logger.error(f"剧情规划 structured 失败: {e}")
            return AgentResponse(success=False, error=str(e))
        except Exception as e:
            logger.error(f"剧情规划失败: {e}")
            # 返回默认规划
            return AgentResponse(
                success=True,
                data={
                    "chapter_titles": [f"第{i+1}章" for i in range(chapter_count)],
                    "chapter_goals": [initial_plot for _ in range(chapter_count)],
                    "overall_summary": initial_plot,
                },
            )

    def _build_user_message(
        self,
        main_plot_progress: float,
        pending_hooks: List[Dict[str, Any]],
        chapter_goal: str,
        recent_events: List[str],
        interaction_turns: int,
        max_turns_threshold: int,
    ) -> str:
        """构建用户消息"""
        message_parts = []

        # 主线进度
        message_parts.append(f"【主线进度】\n{main_plot_progress * 100:.1f}%")

        # 当前章节目标
        if chapter_goal:
            message_parts.append(f"【当前章节目标】\n{chapter_goal}")

        #  pending 伏笔
        if pending_hooks:
            hooks_text = "\n".join(
                [
                    f"- {h.get('id')}: {h.get('title', '无标题')} (优先级：{h.get('priority', 1)})"
                    if isinstance(h, dict)
                    else f"- {h}"
                    for h in pending_hooks
                ]
            )
            message_parts.append(f"【已埋设未回收伏笔】\n{hooks_text}")

        # 最近事件
        if recent_events:
            message_parts.append(f"【最近发生的事件】\n{chr(10).join(recent_events)}")

        # 交互轮次
        message_parts.append(f"【当前交互轮次】\n{interaction_turns} / {max_turns_threshold}")
        if interaction_turns >= max_turns_threshold:
            message_parts.append("⚠️ 已达到强制推进阈值！")

        message_parts.append(
            "\n请评估：\n"
            "1. 是否应该推进剧情到下一阶段\n"
            "2. 是否需要埋设即将发生的事件\n"
            "3. 如需强制推进，请提供合理的外部事件"
        )

        return "\n\n".join(message_parts)

    async def _generate_forced_event(
        self,
        recent_events: List[str],
        pending_hooks: List[Dict[str, Any]],
    ) -> str:
        """
        生成强制推进事件

        Args:
            recent_events: 最近事件
            pending_hooks: 待回收伏笔

        Returns:
            str: 强制事件描述
        """
        prompt = f"""基于以下情境，生成一个合理的外部事件来强制推进剧情：

【最近事件】
{chr(10).join(recent_events) if recent_events else '无'}

【待回收伏笔】
{chr(10).join([h.get('title', '') for h in pending_hooks]) if pending_hooks else '无'}

要求：
1. 事件应该是外部的、突然的（如：刺客袭击、天灾、意外来客）
2. 如果能与现有伏笔关联更好
3. 简洁描述（50 字以内）"""

        try:
            response = await self._call_llm(
                messages=[HumanMessage(content=prompt)],
                temperature=0.7,
                max_tokens=100,
                category=UsageCategory.PLOT
            )
            return response.strip()
        except Exception:
            # 默认 fallback 事件
            fallback_events = [
                "突然传来一声巨响，地面开始震动",
                "就在此时，窗外飞进一支冷箭",
                "远处传来急促的号角声",
                "天空突然乌云密布，狂风大作",
            ]
            import random
            return random.choice(fallback_events)

    async def set_next_milestone(
        self, current_progress: float, plot_goals: List[str]
    ) -> AgentResponse:
        """
        设定下一个剧情里程碑

        Args:
            current_progress: 当前进度
            plot_goals: 剧情目标列表

        Returns:
            AgentResponse: 里程碑设定
        """
        remaining_goals = [
            g for i, g in enumerate(plot_goals)
            if i / len(plot_goals) > current_progress
        ]

        next_goal = remaining_goals[0] if remaining_goals else "完成最终目标"

        return AgentResponse(
            success=True,
            data={
                "next_milestone": next_goal,
                "estimated_progress": min(current_progress + 0.2, 1.0),
            },
        )
