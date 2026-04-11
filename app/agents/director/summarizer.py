"""
剧情总结员 Agent - 将对话压缩为事件摘要
"""

import logging
from typing import Any, Dict, List, Optional

from langchain_core.language_models import BaseLanguageModel
from langchain_core.messages import HumanMessage

from app.agents.base import BaseAgent, AgentResponse
from app.models.agent_template import AgentType
from app.models.token_usage import UsageCategory

logger = logging.getLogger(__name__)


class SummarizerAgent(BaseAgent):
    """剧情总结员 Agent"""

    AGENT_TYPE = AgentType.SUMMARIZER

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
            name="SummarizerAgent",
            model=model,
            system_prompt=system_prompt,
            config=config,
            project_id=project_id,
        )

    def _get_default_variables(self) -> Dict[str, Any]:
        """获取默认变量（Summarizer 特定）"""
        return {
            "agent_role": "剧情总结员",
            "task_description": "将角色之间的对话压缩成干练的事件摘要",
        }

    def _build_default_system_prompt(self) -> str:
        """构建默认系统提示（向后兼容）"""
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
            )

            # 调用 LLM
            response_text = await self._call_llm(
                messages=[HumanMessage(content=user_message)], temperature=0.3,
                category=UsageCategory.PLOT
            )

            # 解析响应
            result = self._parse_json_response(response_text)

            return AgentResponse(
                success=True,
                data=result,
                metadata={"participant_count": len(normalized_participants), "dialogue_turns": len(dialogue_history)},
            )

        except Exception as e:
            logger.error(f"SummarizerAgent 执行失败：{e}")
            return AgentResponse(success=False, error=str(e))

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
背景设定：{world_info.get('background', '无')[:500]}
核心规则：{world_info.get('rules', {})}"""

        if lore_entries:
            lore_text = "\n".join([
                f"- {l.get('title', '无标题')}（{l.get('category', 'general')}）：{l.get('content', '')[:200]}"
                for l in lore_entries[:10]
            ])
            setting_info += f"\n\n【设定条目】\n{lore_text}"

        # 如果没有章节内容，返回世界观确认
        if not chapter_content or len(chapter_content) < 50:
            prompt = f"""你是世界观设定管理员。请确认以下世界观设定，并提供设定管理建议。

{setting_info}

请输出 JSON 格式：
{{
    "status": "confirmed",
    "world_name": "世界名称",
    "key_settings": ["核心设定点1", "核心设定点2"],
    "suggestions": ["设定管理建议"],
    "consistency_check": "世界观设定已确认，等待内容生成后进行一致性检查"
}}"""

            try:
                response_text = await self._call_llm(
                    messages=[HumanMessage(content=prompt)], temperature=0.3,
                    category=UsageCategory.PLOT
                )
                result = self._parse_json_response(response_text)
                return AgentResponse(success=True, data=result)
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
        prompt = f"""你是世界观设定管理员。请检查以下章节内容与世界观设定的一致性。

{setting_info}

【章节内容】
{chapter_content[:3000]}

请检查：
1. 角色能力使用是否符合设定
2. 世界规则是否被遵守
3. 是否有设定冲突或矛盾
4. 是否有需要补充的设定

请输出 JSON 格式：
{{
    "consistency_status": "consistent/inconsistent/partial",
    "world_name": "世界名称",
    "checked_items": ["检查项目1", "检查项目2"],
    "issues": [
        {{
            "type": "设定冲突类型",
            "description": "问题描述",
            "location": "问题位置",
            "suggestion": "修改建议"
        }}
    ],
    "suggestions": ["改进建议"],
    "lore_expansion_suggestions": ["可以扩展的设定点"]
}}"""

        try:
            response_text = await self._call_llm(
                messages=[HumanMessage(content=prompt)], temperature=0.3,
                category=UsageCategory.PLOT
            )
            result = self._parse_json_response(response_text)
            return AgentResponse(success=True, data=result)
        except Exception as e:
            logger.error(f"设定检查失败：{e}")
            return AgentResponse(success=False, error=str(e))

    def _build_user_message(
        self,
        dialogue_history: List[Dict[str, str]],
        participants: List[str],
        context: str,
        active_hooks: List[Dict[str, Any]],
    ) -> str:
        """构建用户消息"""
        message_parts = []

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
            message_parts.append("如果对话触发了任何伏笔，请在 hook_triggers 中列出相关 ID。")

        message_parts.append(
            "\n请将以上对话压缩成事件摘要，识别潜台词，检测伏笔触发。"
        )

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
