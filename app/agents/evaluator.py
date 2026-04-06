"""
评估 Agent - 章节判定与读者模拟
"""

import logging
from typing import Any, Dict, List, Optional

from langchain_core.language_models import BaseLanguageModel
from langchain_core.messages import HumanMessage

from app.agents.base import BaseAgent, AgentResponse

logger = logging.getLogger(__name__)


class EvaluatorAgent(BaseAgent):
    """评估 Agent"""

    def __init__(
        self,
        model: Optional[BaseLanguageModel] = None,
        config: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(
            name="EvaluatorAgent",
            model=model,
            system_prompt="",
            config=config,
        )

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

        prompt = f"""你是章节结束判定员。请评估当前章节是否可以收尾。

【评估标准】
1. 本章信息增量是否足够（至少 3 个有效情节点）
2. 是否埋设了至少 1 个新悬念
3. 主线进度是否达标
4. 章节节奏是否完整

【当前章节数据】
- 已发生事件数量：{len(events)}
- 事件列表：{events}
- 埋设的伏笔：{hooks_planted}
- 字数：{word_count}
- 章节内容：{chapter_content[:2000] if chapter_content else '无'}

请输出 JSON 格式：
{{
    "should_end": true/false,
    "reason": "判断理由",
    "missing_elements": ["缺失元素列表"],
    "suggested_continuation": "建议的后续发展方向",
    "scores": {{
        "info_gain": 0.0,
        "suspense": 0.0,
        "pacing": 0.0,
        "completeness": 0.0
    }}
}}"""

        try:
            response_text = await self._call_llm(
                messages=[HumanMessage(content=prompt)], temperature=0.5
            )
            result = self._parse_json_response(response_text)
            return AgentResponse(success=True, data=result)
        except Exception as e:
            logger.error(f"章节结束评估失败：{e}")
            return AgentResponse(success=False, error=str(e))

    async def _simulate_reader(self, input_data: Dict[str, Any]) -> AgentResponse:
        """
        模拟读者体验评分
        """
        chapter_content = input_data.get("chapter_content", "")
        chapter_title = input_data.get("chapter_title", "无标题")

        if not chapter_content:
            return AgentResponse(success=False, error="章节内容为空")

        prompt = f"""你是一名首次阅读的挑剔读者。请对刚生成的章节进行评分。

【章节信息】
标题：{chapter_title}

【章节内容】
{chapter_content[:5000]}

【评分维度】（1-10 分）
1. 开篇吸引力 - 开头是否抓人
2. 节奏把控 - 快慢是否适中
3. 悬念设置 - 是否有吸引人的悬念
4. 角色魅力 - 角色是否讨喜/有趣
5. 情感共鸣 - 是否能引发情感波动
6. 阅读流畅度 - 文字是否流畅

请输出 JSON 格式：
{{
    "scores": {{
        "opening": 0,
        "pacing": 0,
        "suspense": 0,
        "character": 0,
        "emotion": 0,
        "flow": 0
    }},
    "overall": 0,
    "comments": "具体评价（100 字左右）",
    "suggestions": ["改进建议列表"]
}}"""

        try:
            response_text = await self._call_llm(
                messages=[HumanMessage(content=prompt)], temperature=0.3
            )
            result = self._parse_json_response(response_text)

            # 计算总体评分
            if "scores" in result:
                scores = result["scores"]
                if isinstance(scores, dict):
                    values = [
                        v
                        for v in scores.values()
                        if isinstance(v, (int, float)) and 0 <= v <= 10
                    ]
                    if values:
                        result["overall"] = round(sum(values) / len(values), 2)

            return AgentResponse(success=True, data=result)
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

        samples_text = "\n".join([f"- {s}" for s in voice_samples[:5]])

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
            response_text = await self._call_llm(
                messages=[HumanMessage(content=prompt)], temperature=0.2
            )
            result = self._parse_json_response(response_text)
            return AgentResponse(success=True, data=result)
        except Exception as e:
            logger.error(f"OOC 审查失败：{e}")
            return AgentResponse(success=False, error=str(e))
