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
        return issues

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
        task_type = input_data.get("task_type", "chapter_end")

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
            self._format_context_block("场景方向", input_data.get("scene_directions")),
            self._format_context_block("总编剧写作计划", input_data.get("writing_plan") or input_data.get("plot_guidance")),
            self._format_context_block("固定最高级设定", input_data.get("fixed_lore_entries")),
            self._format_context_block("本章动态设定", input_data.get("dynamic_lore_entries") or input_data.get("selected_lore_entries")),
            self._format_context_block("世界/项目规则", input_data.get("world_info")),
            self._format_context_block("角色出场硬约束", input_data.get("character_constraints")),
            self._format_context_block("角色参与轨迹", input_data.get("participation_trace")),
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

        prompt = f"""你是章节质量评估员。请评估当前章节是否可以收尾，并判断是否通过质量门禁。

{workflow_context if workflow_context else '（未提供工作流上下文；只能根据正文保守评估）'}

【硬性评估规则】
- 必须以绑定章节大纲、固定设定、动态设定和项目/世界规则为依据，不得套用未提供的通用修真/玄幻规则。
- 如果正文偏离绑定章节大纲、违反固定设定、缺少上游要求的角色/场景/伏笔，quality_passed 必须为 false。
- 如果角色出场硬约束中的 mentioned_only_names / forbidden_direct_appearance_names 被写成当前场景的活人参与者、发言者或行动者，quality_passed 必须为 false。
- 如果正文违反 category=character_setting 的角色来源、历史、身份或背景设定，quality_passed 必须为 false。
- 集体讨论或场景演绎素材若引入未授权角色或违反角色状态，不能作为通过依据，必须指出并要求改写。
- 字数需达到目标字数的 80%；目标字数为 {target_word_count or '未提供'}。
- 如果缺少必要上下文，应在 upstream_context_usage_check 中说明，不能凭空补设定。

【当前章节数据】
- 章节号：第 {chapter_num} 章 / 共 {total_chapters} 章
- 已发生事件数量：{len(events)}
- 事件列表：{events}
- 埋设的伏笔：{hooks_planted}
- 当前字数：{word_count}
- 确定性角色约束预检问题：{direct_character_issues if direct_character_issues else '无'}
- 章节内容：{chapter_content if chapter_content else '无'}

请输出 JSON 格式：
{{
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
  "word_count_check": {{"passed": true/false, "actual": {word_count}, "target": {target_word_count}, "min_required": {int(target_word_count * 0.8) if target_word_count else 0}}},
  "upstream_context_usage_check": {{"passed": true/false, "used_context": ["已使用的上游状态"], "missing_context": ["缺失上下文"]}},
  "asset_persistence_check": {{"passed": true/false, "issues": ["地图/伏笔/设定持久化问题"]}},
  "pacing_check": {{"is_appropriate": true/false, "note": "节奏是否适合当前章节位置"}},
  "long_term_check": {{"has_room_for_future": true/false, "note": "是否为后续剧情留有余地"}},
  "world_consistency_check": {{"is_consistent": true/false, "issues": ["世界观一致性问题"]}},
  "scores": {{"info_gain": 0.0, "suspense": 0.0, "pacing": 0.0, "completeness": 0.0, "world_consistency": 0.0}}
}}"""

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
            if "quality_passed" not in parsed_data:
                parsed_data["quality_passed"] = bool(parsed_data.get("should_end")) and not parsed_data.get("issues")
            return AgentResponse.strict(
                structured_data=parsed_data,
                schema_name="evaluator.chapter_end",
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

        # 构建世界观部分
        world_section = ""
        if world_info:
            world_section = f"""
【世界观设定】
世界：{world_info.get('name', '未知世界')}
类型：{world_info.get('world_type', '奇幻')}
基调：{world_info.get('tone', '正剧')}
"""

        prompt = f"""你是一名首次阅读的挑剔读者，正在阅读一部长篇网文。
请对刚生成的章节进行评分。
{world_section}
【重要：长篇网文读者视角】
- 当前是第 {chapter_num} 章，全书共 {total_chapters} 章
- 作为读者，你希望看到可持续发展的剧情，而不是急于完结
- 前期章节主要是建立世界观和角色，不需要太多高潮
- 你希望看到伏笔和悬念，让你期待后续内容
- 如果感觉"开头就是高潮，马上要大结局"，你会感到失望

【章节信息】
标题：{chapter_title}

【章节内容】
{chapter_content}

【评分维度】（1-10 分）
1. 开篇吸引力 - 开头是否抓人
2. 节奏把控 - 快慢是否适中（不要过于急促）
3. 悬念设置 - 是否有吸引人的悬念或伏笔
4. 角色魅力 - 角色是否讨喜/有趣
5. 情感共鸣 - 是否能引发情感波动
6. 阅读流畅度 - 文字是否流畅
7. 长篇期待感 - 是否让你想继续看后续内容
8. 世界观沉浸 - 世界观是否有吸引力

请输出 JSON 格式：
{{
    "scores": {{
        "opening": 0,
        "pacing": 0,
        "suspense": 0,
        "character": 0,
        "emotion": 0,
        "flow": 0,
        "long_term_appeal": 0,
        "world_immersion": 0
    }},
    "overall": 0,
    "comments": "具体评价（尽可能详细）",
    "detailed_analysis": {{
        "opening_analysis": "开篇详细分析",
        "pacing_analysis": "节奏详细分析",
        "character_analysis": "角色表现详细分析",
        "world_building_analysis": "世界观呈现详细分析"
    }},
    "suggestions": ["改进建议列表（详细）"],
    "long_term_feedback": "作为读者，对后续内容的期待或担忧（详细描述）",
    "world_feedback": "对世界观呈现的评价和期待（详细描述）"
}}"""

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
        forbidden_check = ""
        if forbidden_words:
            forbidden_check = f"- 禁用语：{', '.join(forbidden_words)}"

        samples_text = "\n".join([f"- {s}" for s in voice_samples])

        prompt = f"""你是角色一致性审查员。请检查生成的台词是否符合角色设定。

【角色信息】
- 姓名：{character_name}
- 性格特质：{', '.join(character_traits)}
{forbidden_check}
- 典型台词样本：
{samples_text}

【待审查台词】
"{dialogue}"

【审查标准】
1. 是否使用了禁用语
2. 是否符合角色语言风格
3. 与典型台词样本的语义相似度

请输出 JSON 格式：
{{
    "is_ooc": true/false,
    "confidence": 0.0-1.0,
    "issues": ["问题列表"],
    "suggestion": "修改建议（如有）"
}}"""

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
            )
        except StructuredOutputError as e:
            logger.error(f"OOC 审查 structured 失败：{e}")
            return AgentResponse(success=False, error=str(e))
        except Exception as e:
            logger.error(f"OOC 审查失败：{e}")
            return AgentResponse(success=False, error=str(e))
