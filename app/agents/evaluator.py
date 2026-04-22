"""
评估 Agent - 章节判定与读者模拟
"""

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
        world_info = input_data.get("world_info", {})

        # 构建世界观部分
        world_section = ""
        if world_info:
            world_section = f"""
【世界观设定】
世界：{world_info.get('name', '未知世界')}
类型：{world_info.get('world_type', '奇幻')}
基调：{world_info.get('tone', '正剧')}
"""

        prompt = f"""你是章节结束判定员。请评估当前章节是否可以收尾。
{world_section}
【重要：长篇网文评估原则】
- 当前是第 {chapter_num} 章，全书共 {total_chapters} 章
- 前期章节（前20%）主要是铺垫和建立，不需要太多高潮
- 中期章节（20%-80%）才是剧情推进和冲突升级的主要阶段
- 不要期望前期章节就有太多高潮和反转
- 确保内容可持续发展，不要急于推进到结局感

【评估标准】
1. 本章信息增量是否足够（前期至少 2 个情节点，后期至少 3 个）
2. 是否埋设了悬念或伏笔（长篇需要）
3. 字数是否达标（至少目标字数的80%）
4. 章节节奏是否完整
5. 是否为后续剧情留有余地
6. 内容是否符合世界观设定

【当前章节数据】
- 章节号：第 {chapter_num} 章
- 已发生事件数量：{len(events)}
- 事件列表：{events}
- 埋设的伏笔：{hooks_planted}
- 字数：{word_count}
- 章节内容：{chapter_content if chapter_content else '无'}

请输出 JSON 格式：
{{
    "should_end": true/false,
    "reason": "判断理由",
    "missing_elements": ["缺失元素列表"],
    "suggested_continuation": "建议的后续发展方向",
    "pacing_check": {{
        "is_appropriate": true/false,
        "note": "节奏是否适合当前章节位置"
    }},
    "long_term_check": {{
        "has_room_for_future": true/false,
        "note": "是否为后续剧情留有余地"
    }},
    "world_consistency_check": {{
        "is_consistent": true/false,
        "issues": ["世界观一致性问题"]
    }},
    "scores": {{
        "info_gain": 0.0,
        "suspense": 0.0,
        "pacing": 0.0,
        "completeness": 0.0,
        "world_consistency": 0.0
    }}
}}"""

        try:
            parsed = await self._call_structured(
                EvaluatorChapterEndSchema,
                messages=[HumanMessage(content=prompt)],
                temperature=0.5,
                category=UsageCategory.DIRECTOR,
            )
            return AgentResponse.strict(
                structured_data=parsed.model_dump(),
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
