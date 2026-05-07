"""
剧情总结员 Agent - 将对话压缩为事件摘要
"""

import logging
from typing import Any, Dict, List, Optional

from langchain_core.language_models import BaseLanguageModel
from langchain_core.messages import HumanMessage

from app.agents.base import BaseAgent, AgentResponse
from app.models.agent_output_schemas import (
    SummarizerSettingCheckSchema,
    SummarizerSettingConfirmSchema,
    SummarizerSummarySchema,
)
from app.models.agent_template import AgentType
from app.models.token_usage import UsageCategory
from app.services.structured_llm import StructuredOutputError

logger = logging.getLogger(__name__)


class SummarizerAgent(BaseAgent):
    """剧情总结员 Agent"""

    AGENT_TYPE = AgentType.SUMMARIZER
    DEFAULT_SCENARIO = "workflow_summary"
    SETTING_CHECK_PROMPT_ID = "function_summarizer_setting_check"

    def __init__(
        self,
        model: Optional[BaseLanguageModel] = None,
        config: Optional[Dict[str, Any]] = None,
        project_id: Optional[str] = None,
        system_prompt: Optional[str] = None,
    ):
        legacy_trace = None
        # 如果没有提供 system_prompt 且没有 project_id，使用 md prompt 资产 fallback（向后兼容）
        if not system_prompt and not project_id:
            system_prompt = self._build_default_system_prompt()
            legacy_trace = getattr(self, "_legacy_fallback_trace", None)

        super().__init__(
            name="SummarizerAgent",
            model=model,
            system_prompt=system_prompt,
            config=config,
            project_id=project_id,
        )
        if legacy_trace and not self.get_system_prompt_render_trace():
            self._system_prompt_render_trace = legacy_trace

    def _get_default_variables(self) -> Dict[str, Any]:
        """获取默认变量（Summarizer 特定）"""
        return {
            "agent_role": "剧情总结员",
            "task_description": "将角色之间的对话压缩成干练的事件摘要",
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
            logger.warning("加载 Summarizer md prompt 失败: prompt_id=%s, error=%s", prompt_id, e)
        return ""

    def _build_md_summarizer_fallback_prompt(self) -> str:
        prompt_ids = [
            "role_summarizer",
            "function_summarize",
            "function_workflow_discussion_summary",
            "function_workflow_performance_summary",
            "function_summarizer_runtime_context_packet",
            self.SETTING_CHECK_PROMPT_ID,
        ]
        parts = [content for prompt_id in prompt_ids if (content := self._load_md_prompt_content(prompt_id))]
        return "\n\n".join(parts).strip()

    def _summarizer_fallback_trace(self, *, deprecated: bool = False, prompt_ids: Optional[List[str]] = None) -> Dict[str, Any]:
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
            "fallbacks_used": ["summarizer_deprecated_minimal_system_prompt" if deprecated else "summarizer_md_prompt_fallback"],
            "deprecated_sources_used": ["SummarizerAgent._build_default_system_prompt"] if deprecated else [],
            "missing_prompt_ids": [
                "role_summarizer",
                "function_summarize",
                "function_workflow_discussion_summary",
                "function_workflow_performance_summary",
                "function_summarizer_runtime_context_packet",
                self.SETTING_CHECK_PROMPT_ID,
            ] if deprecated else [],
        }

    def _build_default_system_prompt(self) -> str:
        """构建默认系统提示（优先使用 prompts/**/*.md 资产）。"""
        md_prompt = self._build_md_summarizer_fallback_prompt()
        if md_prompt:
            self._legacy_fallback_trace = self._summarizer_fallback_trace(
                prompt_ids=[
                    "role_summarizer",
                    "function_summarize",
                    "function_workflow_discussion_summary",
                    "function_workflow_performance_summary",
                    "function_summarizer_runtime_context_packet",
                    self.SETTING_CHECK_PROMPT_ID,
                ],
            )
            return md_prompt

        logger.warning("Summarizer md prompt 资产不可用，使用 deprecated 最小硬编码默认系统提示")
        self._legacy_fallback_trace = self._summarizer_fallback_trace(deprecated=True)
        return """你是剧情总结员。你的任务是将角色之间的对话压缩成干练的"事件摘要"。

要求：
1. 提取核心信息：谁做了什么，结果如何
2. 识别并标记"潜台词"——角色言外之意
3. 检测关键伏笔触发点
4. 保持客观，不添加主观解读
5. 评估信息增量（0-1 分）

输出 JSON 格式：
{
    "summary": "一句话事件摘要",
    "subtext_markers": [{"speaker": "角色名", "implied_meaning": "潜台词内容"}],
    "hook_triggers": ["相关伏笔 ID 列表"],
    "info_gain_score": 0.0-1.0,
    "raw_dialogue_refs": ["需要保留原始对话的引用 ID"]
}"""

    async def _ensure_system_prompt_loaded(self):
        """加载 Summarizer Agent Template prompt，失败时回退到 md prompt 资产。"""
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
                context_query="剧情总结 场景演绎总结 公开私有边界 连续性整理",
            )
            prompt = prompt_data.get("content", "")
            self._system_prompt_render_trace = prompt_data.get("trace", {}) or {}
            if prompt.strip():
                self.system_prompt = prompt.strip()
        except Exception as e:
            logger.warning(
                "Summarizer 加载模板 prompt 失败: project=%s, scenario=%s, error=%s",
                self.project_id,
                self.scenario,
                e,
            )

        if not self.system_prompt:
            md_prompt = self._build_md_summarizer_fallback_prompt()
            if md_prompt:
                self.system_prompt = md_prompt
                self._system_prompt_render_trace = self._summarizer_fallback_trace(
                    prompt_ids=[
                        "role_summarizer",
                        "function_workflow_discussion_summary",
                        "function_workflow_performance_summary",
                        "function_summarizer_runtime_context_packet",
                        self.SETTING_CHECK_PROMPT_ID,
                    ],
                )
            else:
                self.system_prompt = self._build_default_system_prompt()
                self._system_prompt_render_trace = self._legacy_fallback_trace

        self._system_prompt_loaded = True
        self._pending_system_prompt_load = False

    async def execute(self, input_data: Dict[str, Any]) -> AgentResponse:
        """
        执行剧情总结

        Args:
            input_data: 包含以下字段
                - dialogue_history: 对话历史列表
                - participants: 参与角色列表（可以是字符串或字典）
                - context: 当前情境
                - active_hooks: 当前活跃的伏笔列表
                - setting_check_mode: 如果为 True，执行世界观一致性检查

        Returns:
            AgentResponse: 总结结果
        """
        try:
            await self._ensure_system_prompt_loaded()

            # 检查是否为设定检查模式
            setting_check_mode = input_data.get("setting_check_mode", False)
            if setting_check_mode:
                return await self._execute_setting_check(input_data)

            dialogue_history = input_data.get("dialogue_history", [])
            participants = input_data.get("participants", [])
            context = input_data.get("context", "")
            active_hooks = input_data.get("active_hooks", [])

            # 规范化 participants：处理字典类型
            normalized_participants = []
            for p in participants:
                if isinstance(p, dict):
                    normalized_participants.append(p.get("name", p.get("title", "未知角色")))
                elif isinstance(p, str):
                    normalized_participants.append(p)
                else:
                    normalized_participants.append(str(p))

            # 构建用户消息
            user_message = self._build_user_message(
                dialogue_history=dialogue_history,
                participants=normalized_participants,
                context=context,
                active_hooks=active_hooks,
                scene_performance_context=input_data.get("scene_performance_context"),
                private_performances=input_data.get("private_performances"),
                relationship_deltas=input_data.get("relationship_deltas"),
                state_deltas=input_data.get("state_deltas"),
                continuity_notes=input_data.get("continuity_notes"),
                performance_warnings=input_data.get("performance_warnings"),
            )

            # 调用 LLM (structured)
            parsed = await self._call_structured(
                SummarizerSummarySchema,
                messages=[HumanMessage(content=user_message)],
                temperature=0.3,
                category=UsageCategory.PLOT,
            )
            result = parsed.model_dump()

            return AgentResponse(
                success=True,
                data=result,
                metadata={
                    "participant_count": len(normalized_participants),
                    "dialogue_turns": len(dialogue_history),
                    **self._get_runtime_trace_metadata(),
                },
            )

        except StructuredOutputError as e:
            logger.error(f"SummarizerAgent structured 失败：{e}")
            return AgentResponse(success=False, error=str(e))
        except Exception as e:
            logger.error(f"SummarizerAgent 执行失败：{e}")
            return AgentResponse(success=False, error=str(e))

    def _build_setting_check_instruction(self, *, has_chapter_content: bool) -> str:
        """从 md 资产构建设定检查任务说明，保留 schema 字段约束在代码侧。"""
        prompt_ids = [
            self.SETTING_CHECK_PROMPT_ID,
            "role_setting",
            "function_setting_resource_management",
            "function_setting_lore_interconnection",
        ]
        parts = [content for prompt_id in prompt_ids if (content := self._load_md_prompt_content(prompt_id))]
        if parts:
            mode = "章节内容一致性检查" if has_chapter_content else "世界观设定确认"
            return "\n\n".join(parts + [f"【当前任务模式】\n{mode}"]).strip()
        logger.warning("Summarizer setting_check md prompt 资产不可用，使用最小任务说明")
        return "你是世界观设定管理员，负责确认世界观设定并检查章节内容与设定的一致性。"

    async def _execute_setting_check(self, input_data: Dict[str, Any]) -> AgentResponse:
        """
        执行世界观一致性检查（Setting Agent 模式）

        Args:
            input_data: 包含以下字段
                - world_info: 世界观设定
                - lore_entries: 设定条目列表
                - chapter_content: 章节内容

        Returns:
            AgentResponse: 检查结果
        """
        world_info = input_data.get("world_info", {})
        lore_entries = input_data.get("lore_entries", [])
        chapter_content = input_data.get("chapter_content", "") or input_data.get("dialogue_history", [{}])[0].get("content", "")

        # 构建设定信息
        setting_info = ""
        if world_info:
            setting_info = f"""【世界观基础】
世界名称：{world_info.get('name', '未知')}
世界类型：{world_info.get('world_type', '奇幻')}
叙事基调：{world_info.get('tone', '正剧')}
背景设定：{world_info.get('background', '无')}
核心规则：{world_info.get('rules', {})}"""

        if lore_entries:
            lore_text = "\n".join([
                f"- {l.get('title', '无标题')}（{l.get('category', 'general')}）：{l.get('content', '')}"
                for l in lore_entries
            ])
            setting_info += f"\n\n【设定条目】\n{lore_text}"

        # 如果没有章节内容，返回世界观确认
        if not chapter_content or len(chapter_content) < 50:
            task_instruction = self._build_setting_check_instruction(has_chapter_content=False)
            prompt = f"""{task_instruction}

【当前任务参数】
- task_mode: setting_confirmation
- output_schema: SummarizerSettingConfirmSchema

【待确认设定】
{setting_info}"""

            try:
                parsed = await self._call_structured(
                    SummarizerSettingConfirmSchema,
                    messages=[HumanMessage(content=prompt)],
                    temperature=0.3,
                    category=UsageCategory.PLOT,
                )
                result = parsed.model_dump()
                return AgentResponse(success=True, data=result)
            except StructuredOutputError as e:
                logger.error(f"设定确认 structured 失败：{e}")
                return AgentResponse(
                    success=True,
                    data={
                        "status": "confirmed",
                        "consistency_check": "世界观设定已加载，等待内容生成后进行一致性检查",
                        "error": str(e)
                    }
                )
            except Exception as e:
                logger.error(f"设定确认失败：{e}")
                return AgentResponse(
                    success=True,
                    data={
                        "status": "confirmed",
                        "consistency_check": "世界观设定已加载，等待内容生成后进行一致性检查",
                        "error": str(e)
                    }
                )

        # 有章节内容，进行一致性检查
        task_instruction = self._build_setting_check_instruction(has_chapter_content=True)
        prompt = f"""{task_instruction}

【当前任务参数】
- task_mode: setting_consistency_check
- output_schema: SummarizerSettingCheckSchema

【设定资料】
{setting_info}

【章节内容】
{chapter_content}"""

        try:
            parsed = await self._call_structured(
                SummarizerSettingCheckSchema,
                messages=[HumanMessage(content=prompt)],
                temperature=0.3,
                category=UsageCategory.PLOT,
            )
            result = parsed.model_dump()
            return AgentResponse(success=True, data=result)
        except StructuredOutputError as e:
            logger.error(f"设定检查 structured 失败：{e}")
            return AgentResponse(success=False, error=str(e))
        except Exception as e:
            logger.error(f"设定检查失败：{e}")
            return AgentResponse(success=False, error=str(e))

    def _build_summary_runtime_instruction(self) -> str:
        prompt_ids = [
            "function_summarize",
            "function_summarizer_runtime_context_packet",
        ]
        parts = [content for prompt_id in prompt_ids if (content := self._load_md_prompt_content(prompt_id))]
        if parts:
            return "\n\n".join(parts).strip()
        logger.warning("Summarizer summary md prompt 资产不可用，使用最小运行时任务说明")
        return "请总结对话，识别潜台词、伏笔触发和信息增量，并只输出符合 SummarizerSummarySchema 的结果。"

    def _build_user_message(
        self,
        dialogue_history: List[Dict[str, str]],
        participants: List[str],
        context: str,
        active_hooks: List[Dict[str, Any]],
        scene_performance_context: Optional[Dict[str, Any]] = None,
        private_performances: Optional[List[Dict[str, Any]]] = None,
        relationship_deltas: Optional[List[Dict[str, Any]]] = None,
        state_deltas: Optional[List[Dict[str, Any]]] = None,
        continuity_notes: Optional[List[Dict[str, Any]]] = None,
        performance_warnings: Optional[List[Dict[str, Any]]] = None,
    ) -> str:
        """构建用户消息"""
        message_parts = []
        summary_instruction = self._build_summary_runtime_instruction()
        if summary_instruction:
            message_parts.append("【Summarizer 配置规则】\n" + summary_instruction)

        # 情境
        if context:
            message_parts.append(f"【当前情境】\n{context}")

        # 参与角色（确保都是字符串）
        if participants:
            safe_participants = [str(p) if not isinstance(p, str) else p for p in participants]
            message_parts.append(f"【参与角色】\n{', '.join(safe_participants)}")

        # 对话历史
        if dialogue_history:
            dialogue_text = "\n".join(
                [f"{d.get('speaker', 'Unknown')}: {d.get('content', '')}" for d in dialogue_history[-10:]]
            )
            message_parts.append(f"【对话历史】\n{dialogue_text}")

        # 活跃伏笔
        if active_hooks:
            hooks_text = "\n".join(
                [f"- {h.get('id')}: {h.get('title', '无标题')}" for h in active_hooks]
            )
            message_parts.append(f"【活跃伏笔】\n{hooks_text}")
            message_parts.append("【伏笔触发检查】\n" + "\n".join(
                [
                    "- 如对话触发任何已提供伏笔，在 hook_triggers 中返回相关 ID。",
                    "- 不要用伏笔标题替代 ID。",
                ]
            ))

        # 场景演绎分层上下文
        scene_performance_context = scene_performance_context or {}
        public_performances = scene_performance_context.get("public_performances") or []
        private_performances = private_performances or scene_performance_context.get("private_performances") or []
        relationship_deltas = relationship_deltas or scene_performance_context.get("relationship_deltas") or []
        state_deltas = state_deltas or scene_performance_context.get("state_deltas") or []
        continuity_notes = continuity_notes or scene_performance_context.get("continuity_notes") or []
        performance_warnings = performance_warnings or scene_performance_context.get("performance_warnings") or []

        if public_performances:
            public_lines = [
                f"- {item.get('agent', '未知角色')}：{item.get('content') or item.get('public_content') or ''}"
                for item in public_performances[:12]
            ]
            message_parts.append("【公开表演素材】\n" + "\n".join(public_lines))

        private_lines = []
        for item in private_performances[:12]:
            if item.get("private_thought"):
                private_lines.append(f"- {item.get('agent', '未知角色')} 私有内心：{item.get('private_thought')}")
            if item.get("intent"):
                private_lines.append(f"- {item.get('agent', '未知角色')} 下一步意图：{item.get('intent')}")
            for hidden in item.get("withheld_information", []) or []:
                private_lines.append(f"- {item.get('agent', '未知角色')} 隐瞒信息：{hidden}")
        if private_lines:
            message_parts.append(
                "【私有表演素材】\n"
                + "\n".join(private_lines)
            )

        if relationship_deltas or state_deltas or continuity_notes:
            delta_lines = []
            for item in relationship_deltas[:10]:
                delta_lines.append(f"- 关系变化提案：{item}")
            for item in state_deltas[:10]:
                delta_lines.append(f"- 状态变化提案：{item}")
            for item in continuity_notes[:10]:
                delta_lines.append(f"- 连续性记录：{item}")
            message_parts.append("【关系/状态/连续性提案】\n" + "\n".join(delta_lines))

        if performance_warnings:
            warning_lines = [f"- {item}" for item in performance_warnings[:10]]
            message_parts.append("【演绎素材警告】\n" + "\n".join(warning_lines))

        message_parts.append("【运行时任务参数】\n" + "\n".join(
            [
                "- task_mode: summarize_dialogue",
                "- output_schema: SummarizerSummarySchema",
                "- active_hook_count: " + str(len(active_hooks or [])),
                "- public_performance_count: " + str(len(public_performances or [])),
                "- private_performance_count: " + str(len(private_performances or [])),
            ]
        ))

        return "\n\n".join(message_parts)

    async def summarize_batch(
        self, multiple_dialogues: List[Dict[str, Any]]
    ) -> AgentResponse:
        """
        批量总结多段对话

        Args:
            multiple_dialogues: 多段对话数据

        Returns:
            AgentResponse: 包含多个总结结果
        """
        results = []
        for dialogue_data in multiple_dialogues:
            result = await self.execute(dialogue_data)
            if result.success:
                results.append(result.data)
            else:
                return result

        return AgentResponse(
            success=True,
            data={"summaries": results, "count": len(results)},
        )
