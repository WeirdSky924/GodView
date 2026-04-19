"""
设定 Agent - 统一工作流设定 Agent 与 /lore 界面设定助手

整合 SettingAgentService 的功能与 AgentMemoryService 的记忆系统，
确保工作流和 /lore 页面使用同一个带有记忆的设定 Agent。
"""

import logging
from typing import Any, Dict, List, Optional

from app.agents.base import BaseAgent, AgentResponse
from app.services.setting_agent_service import SettingAgentService, get_setting_agent_service
from app.services.agent_memory_service import get_memory_service
from app.models.setting_agent import SettingAgentMode

logger = logging.getLogger(__name__)


class SettingAgent(BaseAgent):
    """
    设定 Agent - 统一的工作流 Agent 和设定助手

    特点：
    1. 使用 SettingAgentService 的核心逻辑（设定管理、冲突检测等）
    2. 使用 AgentMemoryService 持久化记忆
    3. 与 /lore 界面共享同一个 SettingAgentService 实例
    """

    AGENT_TYPE = "setting"
    AGENT_PROMPT = """你是一个专业的长篇网络小说设定管理者（Setting Agent）。

【核心职责】
1. 维护项目的世界观设定，确保长篇连载中设定的一致性
2. 帮助用户添加、修改、删除设定
3. 检测和处理设定冲突
4. 提供设定建议和优化方案

【核心原则】
- 严格遵循项目的世界类型设定（科幻/奇幻/现代/历史/武侠），不要生成与项目类型不符的设定
- 保持设定的内在一致性，这对长篇连载尤为重要
- 注意宪法级规则，任何新设定都不能违反它们
- 当发现潜在冲突时，及时提醒并提供解决方案
- 用清晰、结构化的方式组织信息
- 考虑长篇创作的可持续性和扩展性

【世界类型区分】
- 科幻：高科技、太空、外星人、赛博朋克、基因工程等，遵守科学逻辑
- 奇幻：魔法、精灵、怪物、异世界等，可以有魔法但要保持内在逻辑
- 现代：当代社会、都市、职场等现实题材
- 历史：古代/近代背景，需要有历史依据
- 武侠：江湖、武功、门派、恩怨，内功招式等"""

    def __init__(self, model=None, project_id: str = None, agent_id: str = None):
        super().__init__(
            name="Setting Agent",
            model=model,
            project_id=project_id,
            agent_id=agent_id or "setting_agent",
        )

        # 获取共享的 SettingAgentService 实例
        self._setting_service = get_setting_agent_service()

    def _get_default_variables(self) -> Dict[str, Any]:
        """获取默认变量"""
        return {
            "agent_type": "setting",
            "project_id": self.project_id,
        }

    async def execute(self, input_data: Dict[str, Any]) -> AgentResponse:
        """执行设定 Agent 任务（BaseAgent 抽象方法实现）"""
        return await self.run(input_data, task=input_data.get("task"))

    async def load_memory(self, db=None):
        """
        加载 Agent 记忆

        同时加载：
        1. AgentMemoryService 的记忆（用于工作流状态）
        2. SettingAgentService 的会话历史（用于 /lore 界面）
        """
        # 调用父类方法加载 AgentMemoryService 记忆
        await super().load_memory(db)

        # 确保 SettingAgentService 会话也已创建
        if self.project_id:
            try:
                session = await self._setting_service.get_or_create_session(
                    project_id=self.project_id,
                    mode=SettingAgentMode.MANAGEMENT,
                )
                logger.info(f"Setting Agent 会话已加载: {session.id}")
            except Exception as e:
                logger.warning(f"加载 SettingAgentService 会话失败: {e}")

    async def run(
        self,
        context: Dict[str, Any],
        task: Optional[str] = None,
        **kwargs,
    ) -> AgentResponse:
        """
        执行设定 Agent 任务

        支持多种任务类型：
        1. 设定查询和确认
        2. 设定变更（添加/修改/删除）
        3. 冲突检测
        4. 章节设定一致性检查
        """
        task = task or context.get("task", "manage_settings")

        # 提取关键信息
        user_message = context.get("message", context.get("user_input", ""))
        chapter_content = context.get("chapter_content", "")
        change_type = context.get("change_type", "")
        lore_data = context.get("lore_data")

        result_data = {}
        response_text = ""

        try:
            # 任务类型 1：章节设定一致性检查
            if chapter_content:
                response_text = await self._check_chapter_consistency(
                    chapter_content, context
                )
                result_data["consistency_check"] = True

            # 任务类型 2：设定变更
            elif change_type and lore_data:
                from app.models.setting_agent import SettingChangeType
                try:
                    change_type_enum = SettingChangeType(change_type)
                except ValueError:
                    change_type_enum = SettingChangeType.ADD

                change_request = await self._setting_service.process_setting_change(
                    project_id=self.project_id,
                    change_type=change_type_enum,
                    lore_data=lore_data,
                    user_intent=user_message,
                )

                response_text = f"设定变更请求已处理: {change_request.status}"
                if change_request.has_conflicts:
                    conflict_descs = [c.description for c in change_request.conflicts]
                    response_text += f"\n检测到冲突: {', '.join(conflict_descs)}"
                    result_data["conflicts"] = [self._make_json_safe(c.model_dump()) for c in change_request.conflicts]

                result_data["change_request"] = self._make_json_safe(change_request.model_dump())

            # 任务类型 3：对话式设定管理
            elif user_message:
                chat_result = await self._setting_service.chat(
                    project_id=self.project_id,
                    message=user_message,
                    context=context,
                )
                response_text = chat_result.get("response", "")
                result_data["chat_result"] = chat_result

                # 如果保存了设定，添加到结果
                if chat_result.get("lore_saved"):
                    result_data["lore_saved"] = True

            # 任务类型 4：默认设定整理
            else:
                response_text = await self._organize_settings(context)
                result_data["organized"] = True

            # 更新记忆
            if self._memory:
                from app.models.agent_memory import MemoryType, MemoryImportance
                self._memory.add_memory(
                    content=f"设定管理任务: {task}",
                    memory_type=MemoryType.OBSERVATION,
                    importance=MemoryImportance.MEDIUM,
                    context={
                        "task_type": task,
                        "has_response": bool(response_text),
                    },
                )

            return AgentResponse(
                success=True,
                data={**result_data, "message": response_text},
            )

        except Exception as e:
            logger.error(f"Setting Agent 执行失败: {e}")
            return AgentResponse(
                success=False,
                error=str(e),
                data={"message": f"设定管理任务执行失败: {str(e)}"},
            )

    async def _check_chapter_consistency(
        self,
        chapter_content: str,
        context: Dict[str, Any],
    ) -> str:
        """
        检查章节内容与设定的一致性

        Args:
            chapter_content: 章节内容
            context: 上下文信息

        Returns:
            str: 检查结果描述
        """
        # 构建检查提示
        prompt = f"""请检查以下章节内容与世界设定的一致性。

【章节内容】
{chapter_content}

请检查：
1. 力量体系使用是否一致（等级、境界、能力名称）
2. 角色行为是否符合设定
3. 地理、势力信息是否正确
4. 是否有违反核心规则的情节

如果没有发现问题，简要说明"章节设定一致性检查通过"。
如果发现问题，列出具体问题并建议修改方案。"""

        result = await self._setting_service.chat(
            project_id=self.project_id,
            message=prompt,
            context={"chapter_check": True, **context},
        )

        return result.get("response", "一致性检查完成")

    async def _organize_settings(self, context: Dict[str, Any]) -> str:
        """
        根据工作流上下文提取当前章节相关的设定约束与一致性要点。

        Args:
            context: 上下文信息

        Returns:
            str: 整理结果
        """
        chapter_outline = context.get("chapter_outline")
        chapter_goals = context.get("chapter_goals") or []
        lore_entries = context.get("lore_entries") or context.get("lore_data") or []
        world_info = context.get("world_info") or {}
        chapter_num = context.get("chapter_num") or context.get("chapter_number")

        current_outline = chapter_outline
        if isinstance(chapter_outline, dict) and chapter_num is not None:
            current_outline = chapter_outline.get(str(chapter_num), chapter_outline.get(chapter_num, chapter_outline))

        if isinstance(current_outline, dict):
            outline_text = current_outline.get("summary") or current_outline.get("goal") or current_outline.get("description") or str(current_outline)
        else:
            outline_text = str(current_outline) if current_outline else "未提供"

        current_goal = None
        if chapter_num and isinstance(chapter_goals, list) and len(chapter_goals) >= int(chapter_num):
            current_goal = chapter_goals[int(chapter_num) - 1]
        elif chapter_goals:
            current_goal = chapter_goals[0]

        if isinstance(current_goal, dict):
            goal_text = current_goal.get("goal") or current_goal.get("summary") or str(current_goal)
        else:
            goal_text = str(current_goal) if current_goal else "未提供"

        lore_summaries: List[str] = []
        for entry in lore_entries[:20]:
            if isinstance(entry, dict):
                title = entry.get("title") or entry.get("name") or "未命名设定"
                summary = entry.get("summary") or entry.get("content") or entry.get("description") or ""
                forbidden = entry.get("forbidden_actions") or entry.get("taboos") or entry.get("constraints") or []
                forbidden_text = ""
                if isinstance(forbidden, list) and forbidden:
                    forbidden_text = f"；禁止/限制：{'、'.join(str(item) for item in forbidden[:5])}"
                lore_summaries.append(f"- {title}: {summary[:200]}{forbidden_text}")
            elif entry:
                lore_summaries.append(f"- {str(entry)[:220]}")

        world_name = world_info.get("name") or "未命名世界"
        world_type = world_info.get("world_type") or world_info.get("description") or "未提供"
        world_rules = world_info.get("rules") or []
        if isinstance(world_rules, dict):
            world_rules_text = str(world_rules)
        elif isinstance(world_rules, list):
            world_rules_text = "；".join(str(item) for item in world_rules[:10])
        else:
            world_rules_text = str(world_rules) if world_rules else "未提供"

        prompt = f"""请基于当前项目上下文，提取本章写作必须遵守的设定约束，并检查潜在冲突。

【任务目标】
你不是在泛泛整理世界观，而是要服务当前章节/当前工作流，输出对这一章真正有用的设定结论。

【当前章节】
- 章节号：{chapter_num or '未提供'}
- 章节目标：{goal_text}
- 当前大纲/焦点：{outline_text}

【世界信息】
- 世界名：{world_name}
- 类型/风格：{world_type}
- 核心规则：{world_rules_text}

【相关设定】
{chr(10).join(lore_summaries) if lore_summaries else '未提供相关设定'}

要求：
1. 只提取与当前章节直接相关的设定约束、禁忌、风险点、可用素材。
2. 若发现上下文不足，请明确指出缺失点，不要自行脑补默认奇幻/冒险设定。
3. 如果设定之间存在冲突，指出冲突来源、影响范围、建议处理方式。
4. 输出尽量结构化，至少包含：
   - 本章关键设定约束
   - 允许使用的设定素材
   - 潜在冲突/风险
   - 对写作或后续节点的建议
"""
        result = await self._setting_service.chat(
            project_id=self.project_id,
            message=prompt,
            context={**context, "workflow_setting_analysis": True},
        )
        return result.get("response", "设定整理完成")

    async def chat(
        self,
        message: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        与设定 Agent 对话（供 /lore 界面使用）

        Args:
            message: 用户消息
            context: 额外上下文

        Returns:
            Dict: 响应结果
        """
        return await self._setting_service.chat(
            project_id=self.project_id,
            message=message,
            context=context,
        )

    def get_conversation_history(self) -> List[Dict[str, Any]]:
        """
        获取对话历史（供 /lore 界面使用）

        Returns:
            List[Dict]: 对话历史
        """
        if self.project_id:
            session = self._setting_service._management_sessions.get(
                self.project_id
            )
            if session:
                return session.conversation_history
        return []

    async def save_memory(self, db=None):
        """
        保存 Agent 记忆到数据库
        """
        if self._memory:
            memory_service = get_memory_service()
            # 更新数据库连接
            if db:
                memory_service._db = db
            await memory_service.save_memory(self._memory)
            logger.info(f"Setting Agent 记忆已保存: {self._memory.total_memories} 条")

    def _make_json_safe(self, obj: Any) -> Any:
        """递归序列化对象，处理 UUID 等非 JSON 类型"""
        import uuid
        from datetime import datetime

        if isinstance(obj, uuid.UUID):
            return str(obj)
        elif isinstance(obj, datetime):
            return obj.isoformat()
        elif isinstance(obj, dict):
            return {k: self._make_json_safe(v) for k, v in obj.items()}
        elif isinstance(obj, (list, tuple)):
            return [self._make_json_safe(item) for item in obj]
        elif hasattr(obj, 'model_dump'):
            return self._make_json_safe(obj.model_dump(mode="json"))
        else:
            return obj


# 全局实例缓存
_setting_agent_instances: Dict[str, SettingAgent] = {}


async def get_setting_agent(
    project_id: str,
    model=None,
    db=None,
) -> SettingAgent:
    """
    获取 Setting Agent 实例（单例模式，按项目）

    Args:
        project_id: 项目 ID
        model: LLM 模型
        db: 数据库连接

    Returns:
        SettingAgent: 设定 Agent 实例
    """
    if project_id not in _setting_agent_instances:
        agent = SettingAgent(model=model, project_id=project_id)
        if db:
            await agent.load_memory(db)
        _setting_agent_instances[project_id] = agent
        logger.info(f"创建 Setting Agent 实例: project_id={project_id}")

    return _setting_agent_instances[project_id]
