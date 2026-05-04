"""
评估 Agent - 章节判定与读者模拟
"""

import json
import logging
from typing import Any, Dict, List, Optional

from langchain_core.language_models import BaseLanguageModel
from langchain_core.messages import HumanMessage

from app.agents.base import BaseAgent, AgentResponse
from app.models.agent_output_schemas import (
    EvaluatorChapterEndSchema,
    EvaluatorOOCSchema,
    EvaluatorReaderSimulateSchema,
)
from app.models.agent_template import AgentType
from app.models.token_usage import UsageCategory
from app.services.structured_llm import StructuredOutputError

logger = logging.getLogger(__name__)


class EvaluatorAgent(BaseAgent):
    """评估 Agent"""

    AGENT_TYPE = AgentType.EVALUATOR
    DEFAULT_SCENARIO = "chapter_quality_review"

    def __init__(
        self,
        model: Optional[BaseLanguageModel] = None,
        config: Optional[Dict[str, Any]] = None,
        project_id: Optional[str] = None,
        system_prompt: Optional[str] = None,
    ):
        super().__init__(
            name="EvaluatorAgent",
            model=model,
            system_prompt=system_prompt or "",
            config=config,
            project_id=project_id,
        )

    def _get_default_variables(self) -> Dict[str, Any]:
        """获取默认变量（Evaluator 特定）"""
        return {
            "agent_role": "评估员",
            "task_description": "章节判定与读者模拟",
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
            logger.warning(f"加载 {prompt_id} prompt 失败: {e}")

        return ""

    def _build_md_evaluator_fallback_prompt(self) -> str:
        """从 md prompt 资产构建 Evaluator 备用 prompt。"""
        prompt_ids = [
            "role_evaluator",
            "function_evaluation",
            "function_evaluator_chapter_quality_gate",
            "function_evaluator_reader_simulation",
            "function_evaluator_ooc_review",
        ]
        parts = [content for prompt_id in prompt_ids if (content := self._load_md_prompt_content(prompt_id))]
        return "\n\n".join(parts).strip()

    async def _get_evaluator_config_prompt(self, variables: Optional[Dict[str, Any]] = None) -> str:
        """获取 Evaluator Agent Template 渲染后的配置 prompt。"""
        if getattr(self, "_evaluator_config_prompt", None):
            return self._evaluator_config_prompt

        await self._ensure_system_prompt_loaded()
        prompt = (self.system_prompt or "").strip()
        if prompt:
            self._evaluator_config_prompt = prompt
            self._evaluator_config_prompt_source = "agent_template_runtime"
            return prompt

        fallback = self._build_md_evaluator_fallback_prompt()
        if fallback:
            self._evaluator_config_prompt = fallback
            self._evaluator_config_prompt_source = "md_prompt_fallback"
            return fallback

        self._evaluator_config_prompt = ""
        self._evaluator_config_prompt_source = "missing"
        return ""

    def _evaluator_chapter_end_output_schema(self, word_count: int, target_word_count: int) -> str:
        return f"""{{
  "should_end": true/false,
  "quality_passed": true/false,
  "score": 0.0,
  "reason": "判断理由",
  "issues": ["主要问题"],
  "suggestions": ["修改建议"],
  "missing_elements": ["缺失元素列表"],
  "suggested_continuation": "建议的后续发展方向",
  "outline_adherence_check": {{"passed": true/false, "issues": ["大纲偏离问题"]}},
  "world_rule_check": {{"passed": true/false, "issues": ["项目/世界规则问题"]}},
  "lore_conflict_check": {{"passed": true/false, "issues": ["设定冲突问题"]}},
  "character_participation_check": {{"passed": true/false, "issues": ["角色参与问题"]}},
  "word_count_check": {{"passed": true/false, "actual": {word_count}, "target": {target_word_count}, "min_required": {int(target_word_count * 0.8) if target_word_count else 0}, "max_allowed": {int(target_word_count * 1.25) if target_word_count else 0}}},
  "upstream_context_usage_check": {{"passed": true/false, "used_context": ["已使用的上游状态"], "missing_context": ["缺失上下文"]}},
  "asset_persistence_check": {{"passed": true/false, "issues": ["地图/伏笔/设定持久化问题"]}},
  "pacing_check": {{"is_appropriate": true/false, "note": "节奏是否适合当前章节位置"}},
  "long_term_check": {{"has_room_for_future": true/false, "note": "是否为后续剧情留有余地"}},
  "world_consistency_check": {{"is_consistent": true/false, "issues": ["世界观一致性问题"]}},
  "scores": {{"info_gain": 0.0, "suspense": 0.0, "pacing": 0.0, "completeness": 0.0, "world_consistency": 0.0}}
}}"""

    def _evaluator_reader_simulation_output_schema(self) -> str:
        return """{
    "scores": {
        "opening": 0,
        "pacing": 0,
        "suspense": 0,
        "character": 0,
        "emotion": 0,
        "flow": 0,
        "long_term_appeal": 0,
        "world_immersion": 0
    },
    "overall": 0,
    "comments": "具体评价（尽可能详细）",
    "detailed_analysis": {
        "opening_analysis": "开篇详细分析",
        "pacing_analysis": "节奏详细分析",
        "character_analysis": "角色表现详细分析",
        "world_building_analysis": "世界观呈现详细分析"
    },
    "suggestions": ["改进建议列表（详细）"],
    "long_term_feedback": "作为读者，对后续内容的期待或担忧（详细描述）",
    "world_feedback": "对世界观呈现的评价和期待（详细描述）"
}"""

    def _evaluator_ooc_output_schema(self) -> str:
        return """{
    "is_ooc": true/false,
    "confidence": 0.0-1.0,
    "issues": ["问题列表"],
    "suggestion": "修改建议（如有）"
}"""

    def _evaluator_task_title(self, task_type: str) -> str:
        titles = {
            "chapter_end": "评估当前章节是否可以收尾，并判断是否通过质量门禁。",
            "reader_simulate": "以首次阅读的挑剔长篇网文读者视角，对刚生成的章节进行评分。",
            "ooc_review": "检查生成的台词是否符合角色设定、禁用语和典型台词样本。",
        }
        return titles.get(task_type, task_type)

    def _evaluator_task_notes(self, task_type: str) -> List[str]:
        notes = {
            "chapter_end": [
                "必须以 Agent Template / md prompt / writing-rules 中的门禁为准。",
                "确定性角色约束预检问题必须作为阻断问题写入 character_participation_check。",
                "确定性 role_performance_gate 问题必须写入 character_participation_check 或 upstream_context_usage_check；若正文采纳 blocker 指向素材，quality_passed=false。",
            ],
            "reader_simulate": [],
            "ooc_review": [],
        }
        return notes.get(task_type, [])

    def _evaluator_task_schema(self, task_type: str, **kwargs: Any) -> str:
        if task_type == "chapter_end":
            return self._evaluator_chapter_end_output_schema(
                kwargs.get("word_count", 0),
                kwargs.get("target_word_count", 0),
            )
        if task_type == "reader_simulate":
            return self._evaluator_reader_simulation_output_schema()
        if task_type == "ooc_review":
            return self._evaluator_ooc_output_schema()
        return "{}"

    def _format_evaluator_task_prompt(
        self,
        task_title: str,
        sections: List[tuple[str, Any]],
        output_schema: str,
        task_notes: Optional[List[str]] = None,
        config_prompt: str = "",
    ) -> str:
        parts: List[str] = []
        if config_prompt:
            parts.append(
                "【Evaluator 配置规则】\n"
                "以下内容来自 Agent Template 绑定的 md prompt / skills / writing-rules，是本次评估的稳定规则来源。\n"
                f"{config_prompt}"
            )

        parts.append(f"【当前任务】\n{task_title}")
        for title, value in sections:
            block = self._format_context_block(title, value)
            if block:
                parts.append(block)

        if task_notes:
            parts.append("【本次任务补充要求】\n" + "\n".join(f"- {note}" for note in task_notes if note))

        parts.append(f"【输出 JSON Schema】\n{output_schema}")
        return "\n\n".join(part for part in parts if part)

    def _get_evaluator_config_metadata(self) -> Dict[str, Any]:
        config_prompt = getattr(self, "_evaluator_config_prompt", "") or ""
        return {
            "config_prompt_source": getattr(self, "_evaluator_config_prompt_source", None),
            "config_prompt_length": len(config_prompt),
            **self._get_runtime_trace_metadata(),
        }

    def _format_context_block(self, title: str, value: Any, max_chars: Optional[int] = None) -> str:
        if value in (None, "", [], {}):
            return ""
        if isinstance(value, str):
            text = value
        else:
            try:
                text = json.dumps(value, ensure_ascii=False, indent=2)
            except TypeError:
                text = str(value)
        text = text.strip()
        if not text:
            return ""
        return f"【{title}】\n{text}"

    def _get_target_word_count(self, input_data: Dict[str, Any]) -> int:
        raw_value = (
            input_data.get("target_word_count")
            or input_data.get("chapter_target_word_count")
            or input_data.get("word_count_target")
            or input_data.get("word_count")
            or 0
        )
        try:
            return int(raw_value)
        except (TypeError, ValueError):
            return 0

    def _character_name_set(self, value: Any) -> set[str]:
        names: set[str] = set()
        if not isinstance(value, list):
            value = [] if value in (None, "") else [value]
        for item in value:
            if isinstance(item, dict):
                name = item.get("name") or item.get("character_name") or item.get("id")
            else:
                name = item
            if name not in (None, ""):
                names.add(str(name))
        return names

    def _direct_character_constraint_issues(self, input_data: Dict[str, Any]) -> List[str]:
        """对正文做确定性角色约束预检，模型评估不能把此类问题放过。"""
        content = str(input_data.get("chapter_content") or "")
        if not content:
            return []
        constraints = input_data.get("character_constraints")
        if not isinstance(constraints, dict):
            constraints = {}
        forbidden = set(constraints.get("forbidden_direct_appearance_names") or [])
        unavailable = self._character_name_set(input_data.get("unavailable_characters"))
        mentioned_only = self._character_name_set(input_data.get("mentioned_characters"))
        present = set(constraints.get("present_character_names") or [])
        candidate_names = sorted((forbidden | unavailable | mentioned_only) - present, key=len, reverse=True)
        issues: List[str] = []
        direct_markers = [
            "说", "问", "答", "喊", "低声", "开口", "回应", "走", "站", "看", "伸手", "转身", "出现", "参与", "进入",
            "dialogue", "said", "asked", "replied",
        ]
        for name in candidate_names:
            if not name or name not in content:
                continue
            snippets = []
            start = 0
            while True:
                idx = content.find(name, start)
                if idx == -1:
                    break
                snippet = content[max(0, idx - 20): idx + len(name) + 35]
                snippets.append(snippet)
                start = idx + len(name)
                if len(snippets) >= 3:
                    break
            if any(any(marker in snippet for marker in direct_markers) for snippet in snippets):
                issues.append(f"不可正面出场角色 {name} 疑似被写成当前场景行动/发言者：{' / '.join(snippets[:2])}")
        declared_new_names = self._character_name_set(
            input_data.get("character_candidates")
            or input_data.get("new_characters")
            or input_data.get("characters_to_create")
            or input_data.get("writer_created_characters")
            or input_data.get("plotter_created_characters")
        )
        if declared_new_names:
            for name in declared_new_names:
                if name in forbidden or name in unavailable or name in mentioned_only:
                    issues.append(f"新增次要角色候选 {name} 与不可正面出场/仅可提及角色冲突")

        return issues

    def _context_list(self, value: Any) -> List[Any]:
        """将上游上下文字段归一化为列表。"""
        if value in (None, ""):
            return []
        if isinstance(value, list):
            return value
        if isinstance(value, tuple):
            return list(value)
        return [value]

    def _context_dict(self, value: Any) -> Dict[str, Any]:
        """将上游上下文字段归一化为字典。"""
        return value if isinstance(value, dict) else {}

    def _role_performance_value(self, input_data: Dict[str, Any], key: str, default: Any = None) -> Any:
        """从顶层、scene/role performance context 或 performance_result 中读取角色演绎上下文。"""
        if input_data.get(key) is not None:
            return input_data.get(key)
        scene_context = self._context_dict(input_data.get("scene_performance_context"))
        if scene_context.get(key) is not None:
            return scene_context.get(key)
        role_context = self._context_dict(input_data.get("role_performance_context"))
        if role_context.get(key) is not None:
            return role_context.get(key)
        performance_result = self._context_dict(input_data.get("performance_result"))
        if performance_result.get(key) is not None:
            return performance_result.get(key)
        nested_scene_context = self._context_dict(performance_result.get("scene_performance_context"))
        if nested_scene_context.get(key) is not None:
            return nested_scene_context.get(key)
        return default

    def _private_performance_fragments(self, input_data: Dict[str, Any]) -> List[Dict[str, str]]:
        """提取 Writer/Evaluator-only 的私有演绎片段，用于检测是否被正文公开采纳。"""
        private_performances = self._context_list(self._role_performance_value(input_data, "private_performances", []))
        public_performances = self._context_list(self._role_performance_value(input_data, "public_performances", []))
        packets = self._context_list(self._role_performance_value(input_data, "character_performance_packets", []))
        fragments: List[Dict[str, str]] = []

        for item in [*private_performances, *packets, *public_performances]:
            if not isinstance(item, dict):
                continue
            agent = str(item.get("agent") or item.get("source_character") or item.get("character") or "未知角色")
            for key in ("private_thought", "inner_thought", "intent"):
                text = str(item.get(key) or "").strip()
                if key == "intent":
                    if len(text) >= 2:
                        fragments.append({"agent": agent, "field": key, "value": text})
                    continue
                if len(text) >= 8:
                    fragments.append({"agent": agent, "field": key, "value": text})
            for key in ("withheld_information", "misinterpretations"):
                for value in self._context_list(item.get(key)):
                    text = str(value or "").strip()
                    if len(text) >= 6:
                        fragments.append({"agent": agent, "field": key, "value": text})
        return fragments

    def _role_performance_gate_issues(self, input_data: Dict[str, Any]) -> Dict[str, List[str]]:
        """对正文做角色演绎 gate 确定性预检：只在正文采纳问题素材时阻断。"""
        content = str(input_data.get("chapter_content") or "")
        gate = self._context_dict(self._role_performance_value(input_data, "role_performance_gate", {}))
        gate_passed = self._role_performance_value(input_data, "role_performance_gate_passed", gate.get("passed", True))
        blockers = self._context_list(gate.get("blockers") or self._role_performance_value(input_data, "role_performance_gate_blockers", []))
        gate_warnings = self._context_list(gate.get("warnings") or self._role_performance_value(input_data, "role_performance_gate_warnings", []))

        issues: List[str] = []
        warnings: List[str] = []
        if gate_passed is False and blockers:
            warnings.append("上游 role_performance_gate 未通过；Evaluator 必须确认正文没有采纳 blocker 指向素材。")

        for fragment in self._private_performance_fragments(input_data):
            value = fragment["value"]
            if content and value in content:
                issues.append(f"正文采纳了角色私有演绎素材：{fragment['agent']}.{fragment['field']}")

        direct_markers = [
            "说", "问", "答", "喊", "低声", "开口", "回应", "走", "站", "看", "伸手", "转身", "出现", "参与", "进入",
            "dialogue", "said", "asked", "replied",
        ]
        blocked_names: set[str] = set()
        for blocker in blockers:
            text = str(blocker)
            if "不可正面出场角色 " not in text:
                continue
            tail = text.split("不可正面出场角色 ", 1)[1].strip()
            name = tail.split()[0].strip("：:，,。.") if tail else ""
            if name:
                blocked_names.add(name)

        for name in sorted(blocked_names, key=len, reverse=True):
            if not content or not name or name not in content:
                continue
            snippets: List[str] = []
            start = 0
            while True:
                idx = content.find(name, start)
                if idx == -1:
                    break
                snippets.append(content[max(0, idx - 20): idx + len(name) + 35])
                start = idx + len(name)
                if len(snippets) >= 3:
                    break
            if any(any(marker in snippet for marker in direct_markers) for snippet in snippets):
                issues.append(f"正文采纳了 role_performance_gate 阻断的不可出场角色行动/发言：{name}：{' / '.join(snippets[:2])}")

        for blocker in blockers:
            text = str(blocker)
            if text and not any(text in item for item in warnings):
                warnings.append(f"role_performance_gate blocker 待核查：{text}")
        for warning in gate_warnings:
            text = str(warning)
            if text:
                warnings.append(f"role_performance_gate warning：{text}")

        return {
            "issues": list(dict.fromkeys(issues)),
            "warnings": list(dict.fromkeys(warnings)),
            "blockers": [str(item) for item in blockers if str(item)],
        }

    async def execute(self, input_data: Dict[str, Any]) -> AgentResponse:
        """
        执行评估任务

        Args:
            input_data: 包含以下字段
                - task_type: 评估类型 (chapter_end/reader_simulate)
                - chapter_content: 章节内容
                - events: 事件列表
                - hooks_planted: 埋设的伏笔
                - word_count: 字数

        Returns:
            AgentResponse: 评估结果
        """
        task_type = str(input_data.get("task_type", "chapter_end"))

        if task_type == "chapter_end":
            return await self._evaluate_chapter_end(input_data)
        elif task_type == "reader_simulate":
            return await self._simulate_reader(input_data)
        else:
            return AgentResponse(success=False, error=f"未知的评估类型：{task_type}")

    async def _evaluate_chapter_end(self, input_data: Dict[str, Any]) -> AgentResponse:
        """
        评估章节是否可以收尾
        """
        events = input_data.get("events", [])
        hooks_planted = input_data.get("hooks_planted", [])
        word_count = input_data.get("word_count", 0)
        chapter_content = input_data.get("chapter_content", "")
        chapter_num = input_data.get("chapter_num", 1)
        total_chapters = input_data.get("total_chapters", 10)
        target_word_count = self._get_target_word_count(input_data)
        context_blocks = [
            self._format_context_block("绑定章节大纲", input_data.get("chapter_outline")),
            self._format_context_block("章节目标", input_data.get("chapter_goals") or input_data.get("chapter_goal")),
            self._format_context_block("后续大纲参考", input_data.get("upcoming_outline_context")),
            self._format_context_block("后续大纲策略", input_data.get("upcoming_outline_policy")),
            self._format_context_block("场景方向", input_data.get("scene_directions")),
            self._format_context_block("总编剧写作计划", input_data.get("writing_plan") or input_data.get("plot_guidance")),
            self._format_context_block("固定最高级设定", input_data.get("fixed_lore_entries")),
            self._format_context_block("本章动态设定", input_data.get("dynamic_lore_entries") or input_data.get("selected_lore_entries")),
            self._format_context_block("世界/项目规则", input_data.get("world_info")),
            self._format_context_block("角色出场硬约束", input_data.get("character_constraints")),
            self._format_context_block("角色参与轨迹", input_data.get("participation_trace")),
            self._format_context_block("角色演绎 Gate", {
                "role_performance_gate": self._role_performance_value(input_data, "role_performance_gate", {}),
                "role_performance_gate_passed": self._role_performance_value(input_data, "role_performance_gate_passed", True),
                "role_performance_gate_blockers": self._role_performance_value(input_data, "role_performance_gate_blockers", []),
                "role_performance_gate_warnings": self._role_performance_value(input_data, "role_performance_gate_warnings", []),
            }),
            self._format_context_block("角色演绎连续性素材", {
                "public_performances": self._role_performance_value(input_data, "public_performances", []),
                "private_performances": self._role_performance_value(input_data, "private_performances", []),
                "relationship_deltas": self._role_performance_value(input_data, "relationship_deltas", []),
                "state_deltas": self._role_performance_value(input_data, "state_deltas", []),
                "continuity_notes": self._role_performance_value(input_data, "continuity_notes", []),
                "performance_warnings": self._role_performance_value(input_data, "performance_warnings", []),
            }),
            self._format_context_block("地图/资产持久化状态", {
                "map_persistence_state": input_data.get("map_persistence_state"),
                "asset_persistence_state": input_data.get("asset_persistence_state"),
                "saved_region_ids": input_data.get("saved_region_ids"),
                "saved_hook_ids": input_data.get("saved_hook_ids"),
                "saved_lore_ids": input_data.get("saved_lore_ids"),
            }),
        ]
        workflow_context = "\n\n".join(block for block in context_blocks if block)
        direct_character_issues = self._direct_character_constraint_issues(input_data)
        role_gate_check = self._role_performance_gate_issues(input_data)

        evaluator_config_prompt = await self._get_evaluator_config_prompt({
            "task_type": "chapter_end",
            "chapter_num": chapter_num,
            "total_chapters": total_chapters,
            "target_word_count": target_word_count,
        })

        prompt = self._format_evaluator_task_prompt(
            self._evaluator_task_title(task_type),
            [
                ("工作流上下文", workflow_context if workflow_context else "（未提供工作流上下文；只能根据正文保守评估）"),
                ("当前章节数据", {
                    "chapter_num": chapter_num,
                    "total_chapters": total_chapters,
                    "events_count": len(events),
                    "events": events,
                    "hooks_planted": hooks_planted,
                    "word_count": word_count,
                    "target_word_count": target_word_count or None,
                    "deterministic_character_constraint_issues": direct_character_issues,
                    "deterministic_role_performance_gate_issues": role_gate_check["issues"],
                    "deterministic_role_performance_gate_warnings": role_gate_check["warnings"],
                    "chapter_content": chapter_content or "无",
                }),
            ],
            output_schema=self._evaluator_task_schema(
                "chapter_end",
                word_count=word_count,
                target_word_count=target_word_count,
            ),
            task_notes=self._evaluator_task_notes("chapter_end"),
            config_prompt=evaluator_config_prompt,
        )

        try:
            parsed = await self._call_structured(
                EvaluatorChapterEndSchema,
                messages=[HumanMessage(content=prompt)],
                temperature=0.5,
                category=UsageCategory.DIRECTOR,
            )
            parsed_data = parsed.model_dump()
            if not parsed_data.get("issues"):
                issues: List[str] = []
                for key in (
                    "outline_adherence_check",
                    "world_rule_check",
                    "lore_conflict_check",
                    "character_participation_check",
                    "word_count_check",
                    "asset_persistence_check",
                ):
                    check = parsed_data.get(key)
                    if isinstance(check, dict) and check.get("passed") is False:
                        for issue in check.get("issues", []):
                            if issue:
                                issues.append(str(issue))
                        if not check.get("issues"):
                            issues.append(f"{key} 未通过")
                parsed_data["issues"] = issues
            if direct_character_issues:
                parsed_data.setdefault("issues", [])
                parsed_data["issues"].extend(issue for issue in direct_character_issues if issue not in parsed_data["issues"])
                parsed_data["quality_passed"] = False
                parsed_data["should_end"] = False
                parsed_data["approved"] = False
                parsed_data["pass"] = False
                character_check = parsed_data.setdefault("character_participation_check", {})
                if isinstance(character_check, dict):
                    character_check["passed"] = False
                    existing = character_check.get("issues") or []
                    if not isinstance(existing, list):
                        existing = [existing]
                    character_check["issues"] = [*existing, *direct_character_issues]
            deterministic_role_issues = role_gate_check["issues"]
            deterministic_role_warnings = role_gate_check["warnings"]
            if deterministic_role_issues:
                parsed_data.setdefault("issues", [])
                parsed_data["issues"].extend(issue for issue in deterministic_role_issues if issue not in parsed_data["issues"])
                parsed_data["quality_passed"] = False
                parsed_data["should_end"] = False
                parsed_data["approved"] = False
                parsed_data["pass"] = False
                character_check = parsed_data.setdefault("character_participation_check", {})
                if isinstance(character_check, dict):
                    character_check["passed"] = False
                    existing = character_check.get("issues") or []
                    if not isinstance(existing, list):
                        existing = [existing]
                    character_check["issues"] = [*existing, *deterministic_role_issues]
            if deterministic_role_warnings:
                upstream_check = parsed_data.setdefault("upstream_context_usage_check", {})
                if isinstance(upstream_check, dict):
                    existing = upstream_check.get("issues") or []
                    if not isinstance(existing, list):
                        existing = [existing]
                    upstream_check["issues"] = [*existing, *deterministic_role_warnings]
            parsed_data.setdefault("role_performance_gate_check", {})
            parsed_data["role_performance_gate_check"] = {
                "passed": not deterministic_role_issues,
                "issues": deterministic_role_issues,
                "warnings": deterministic_role_warnings,
                "blockers": role_gate_check["blockers"],
            }
            if "quality_passed" not in parsed_data:
                parsed_data["quality_passed"] = bool(parsed_data.get("should_end")) and not parsed_data.get("issues")
            return AgentResponse.strict(
                structured_data=parsed_data,
                schema_name="evaluator.chapter_end",
                metadata=self._get_evaluator_config_metadata(),
            )
        except StructuredOutputError as e:
            logger.error(f"章节结束评估 structured 失败：{e}")
            return AgentResponse(success=False, error=str(e))
        except Exception as e:
            logger.error(f"章节结束评估失败：{e}")
            return AgentResponse(success=False, error=str(e))

    async def _simulate_reader(self, input_data: Dict[str, Any]) -> AgentResponse:
        """
        模拟读者体验评分
        """
        chapter_content = input_data.get("chapter_content", "")
        chapter_title = input_data.get("chapter_title", "无标题")
        chapter_num = input_data.get("chapter_num", 1)
        total_chapters = input_data.get("total_chapters", 10)
        world_info = input_data.get("world_info", {})

        if not chapter_content:
            return AgentResponse(success=False, error="章节内容为空")

        evaluator_config_prompt = await self._get_evaluator_config_prompt({
            "task_type": "reader_simulate",
            "chapter_num": chapter_num,
            "total_chapters": total_chapters,
        })

        prompt = self._format_evaluator_task_prompt(
            self._evaluator_task_title("reader_simulate"),
            [
                ("世界观设定", {
                    "name": world_info.get("name", "未知世界") if isinstance(world_info, dict) else "未知世界",
                    "world_type": world_info.get("world_type", "奇幻") if isinstance(world_info, dict) else "奇幻",
                    "tone": world_info.get("tone", "正剧") if isinstance(world_info, dict) else "正剧",
                } if world_info else None),
                ("章节信息", {
                    "chapter_title": chapter_title,
                    "chapter_num": chapter_num,
                    "total_chapters": total_chapters,
                }),
                ("章节内容", chapter_content),
            ],
            output_schema=self._evaluator_task_schema("reader_simulate"),
            task_notes=self._evaluator_task_notes("reader_simulate"),
            config_prompt=evaluator_config_prompt,
        )

        try:
            parsed = await self._call_structured(
                EvaluatorReaderSimulateSchema,
                messages=[HumanMessage(content=prompt)],
                temperature=0.3,
                category=UsageCategory.DIRECTOR,
            )
            result = parsed.model_dump()

            # 计算总体评分
            scores = result.get("scores") or {}
            if isinstance(scores, dict):
                values = [
                    v
                    for v in scores.values()
                    if isinstance(v, (int, float)) and 0 <= v <= 10
                ]
                if values:
                    result["overall"] = round(sum(values) / len(values), 2)

            return AgentResponse.strict(
                structured_data=result,
                schema_name="evaluator.reader_simulate",
                metadata=self._get_evaluator_config_metadata(),
            )
        except StructuredOutputError as e:
            logger.error(f"读者模拟评分 structured 失败：{e}")
            return AgentResponse(success=False, error=str(e))
        except Exception as e:
            logger.error(f"读者模拟评分失败：{e}")
            return AgentResponse(success=False, error=str(e))

    async def evaluate_ooc(
        self,
        character_name: str,
        character_traits: List[str],
        voice_samples: List[str],
        dialogue: str,
        forbidden_words: Optional[List[str]] = None,
    ) -> AgentResponse:
        """
        OOC（角色崩坏）审查

        Args:
            character_name: 角色名称
            character_traits: 性格特质列表
            voice_samples: 典型台词样本
            dialogue: 待审查台词
            forbidden_words: 禁用语列表

        Returns:
            AgentResponse: 审查结果
        """
        prompt = self._format_evaluator_task_prompt(
            self._evaluator_task_title("ooc_review"),
            [
                ("角色信息", {
                    "name": character_name,
                    "traits": character_traits,
                    "forbidden_words": forbidden_words or [],
                    "voice_samples": voice_samples,
                }),
                ("待审查台词", dialogue),
            ],
            output_schema=self._evaluator_task_schema("ooc_review"),
            config_prompt=await self._get_evaluator_config_prompt({"task_type": "ooc_review"}),
        )

        try:
            parsed = await self._call_structured(
                EvaluatorOOCSchema,
                messages=[HumanMessage(content=prompt)],
                temperature=0.2,
                category=UsageCategory.CHARACTER,
            )
            return AgentResponse.strict(
                structured_data=parsed.model_dump(),
                schema_name="evaluator.ooc",
                metadata=self._get_evaluator_config_metadata(),
            )
        except StructuredOutputError as e:
            logger.error(f"OOC 审查 structured 失败：{e}")
            return AgentResponse(success=False, error=str(e))
        except Exception as e:
            logger.error(f"OOC 审查失败：{e}")
            return AgentResponse(success=False, error=str(e))
