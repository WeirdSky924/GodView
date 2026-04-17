"""
Agent 基类
"""

import asyncio
import json
import logging
import time
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from langchain_core.language_models import BaseLanguageModel

from app.models.token_usage import UsageCategory

logger = logging.getLogger(__name__)


class AgentResponse(BaseModel):
    """Agent 响应基类"""

    success: bool = Field(default=True, description="是否成功")
    data: Optional[Any] = Field(default=None, description="响应数据")
    error: Optional[str] = Field(default=None, description="错误信息")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="元数据")

    class Config:
        arbitrary_types_allowed = True


class BaseAgent(ABC):
    """Agent 基类"""

    # 类属性，子类必须覆盖
    AGENT_TYPE: Optional[str] = None

    def __init__(
        self,
        name: str,
        model: Optional[BaseLanguageModel] = None,
        system_prompt: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
        project_id: Optional[str] = None,
        agent_id: Optional[str] = None,  # 新增：用于区分同类型多实例
    ):
        self.name = name
        self.model = model
        self.config = config or {}
        self.project_id = project_id
        self.agent_id = agent_id  # 实例 ID
        self.message_history: List = []
        self._lock = asyncio.Lock()
        # 流式输出回调（由 workflow_engine 设置）
        self._stream_callback: Optional[callable] = None

        # Skills 缓存（从模板加载）
        self._skills: Dict[str, Any] = {}  # skill_id -> Skill 对象
        self._skills_loaded: bool = False

        # ========== 记忆系统 ==========
        self._memory = None  # AgentMemory 对象（延迟加载）
        self._memory_loaded: bool = False

        # 延迟加载 system prompt 的标记
        self._system_prompt_loaded: bool = False
        self._pending_system_prompt_load: bool = False

        # 如果有 project_id 且没有手动指定 system_prompt，标记为需要延迟加载
        if project_id and not system_prompt and self.AGENT_TYPE:
            self._pending_system_prompt_load = True
            self.system_prompt = ""  # 先设置为空，稍后在异步上下文中加载
        else:
            self.system_prompt = system_prompt or ""
            self._system_prompt_loaded = True

    @property
    def memory(self):
        """获取 Agent 记忆"""
        return self._memory

    async def load_memory(self, db=None):
        """
        加载 Agent 记忆（从数据库）

        Args:
            db: 数据库连接（可选，如果不提供则尝试自动获取）
        """
        if self._memory_loaded:
            return self._memory

        if not self.project_id:
            logger.debug(f"Agent {self.name} 没有 project_id，跳过记忆加载")
            return None

        try:
            from app.services.agent_memory_service import get_memory_service

            # 获取记忆服务
            service = get_memory_service(db)

            # 加载记忆
            self._memory = await service.get_memory(
                project_id=self.project_id,
                agent_type=self.AGENT_TYPE or self.name,
                agent_id=self.agent_id,
            )

            self._memory_loaded = True
            logger.info(
                f"Agent {self.name} 加载记忆成功: "
                f"{self._memory.total_memories} 条记忆, "
                f"{self._memory.execution_count} 次执行"
            )

            return self._memory

        except Exception as e:
            logger.warning(f"Agent {self.name} 加载记忆失败: {e}")
            return None

    async def save_memory(self, db=None):
        """
        保存 Agent 记忆到数据库

        Args:
            db: 数据库连接
        """
        if not self._memory:
            return False

        try:
            from app.services.agent_memory_service import get_memory_service

            service = get_memory_service(db)
            return await service.save_memory(self._memory)

        except Exception as e:
            logger.error(f"Agent {self.name} 保存记忆失败: {e}")
            return False

    def add_memory(
        self,
        content: str,
        memory_type: str = "observation",
        importance: str = "medium",
        tags: List[str] = None,
        context: Dict[str, Any] = None,
    ):
        """
        添加记忆条目

        Args:
            content: 记忆内容
            memory_type: 记忆类型 (observation/decision/action/learning/reflection)
            importance: 重要性 (critical/high/medium/low/ephemeral)
            tags: 标签列表
            context: 上下文信息
        """
        if not self._memory:
            return None

        from app.models.agent_memory import MemoryType, MemoryImportance

        try:
            mem_type = MemoryType(memory_type)
        except ValueError:
            mem_type = MemoryType.OBSERVATION

        try:
            mem_importance = MemoryImportance(importance)
        except ValueError:
            mem_importance = MemoryImportance.MEDIUM

        entry = self._memory.add_memory(
            content=content,
            memory_type=mem_type,
            importance=mem_importance,
            tags=tags or [],
            context=context or {},
        )

        logger.debug(f"Agent {self.name} 添加记忆: {content[:50]}...")
        return entry

    def get_memory_context(self) -> str:
        """
        获取记忆上下文（用于注入到 prompt 中）

        这是同步版本，使用静态选择策略。
        对于上下文感知选择，请使用 get_enhanced_memory_context()

        Returns:
            str: 格式化的记忆上下文
        """
        if not self._memory:
            return ""

        # 获取最近的记忆
        recent = self._memory.get_recent_memories(5)

        if not recent:
            return ""

        context_parts = ["【Agent 历史记忆】"]

        for entry in recent:
            context_parts.append(
                f"- [{entry.type.value}] {entry.content}"
            )

        # 获取重要记忆
        important = self._memory.get_important_memories()[:3]
        if important:
            context_parts.append("\n【关键记忆】")
            for entry in important:
                context_parts.append(
                    f"- [{entry.importance.value}] {entry.content}"
                )

        return "\n".join(context_parts)

    async def get_enhanced_memory_context(
        self,
        task_type: Optional[str] = None,
        query_text: Optional[str] = None,
        current_context: Optional[Dict[str, Any]] = None,
        db=None,
    ) -> str:
        """
        获取增强的记忆上下文（支持语义检索和上下文感知）

        Args:
            task_type: 任务类型（如 "outline_generation", "chapter_writing"）
            query_text: 查询文本（用于语义匹配）
            current_context: 当前上下文（章节号、角色等）
            db: 数据库连接

        Returns:
            str: 格式化的记忆上下文
        """
        if not self._memory or not self.project_id:
            return ""

        try:
            from app.services.enhanced_memory_service import get_enhanced_memory_service

            # 获取增强记忆服务
            enhanced_service = get_enhanced_memory_service(db=db)

            # 如果指定了任务类型，使用上下文感知选择
            if task_type:
                memories = await enhanced_service.get_context_aware_memories(
                    project_id=self.project_id,
                    agent_type=self.AGENT_TYPE or self.name,
                    task_type=task_type,
                    current_context=current_context,
                    query_text=query_text,
                )
            elif query_text:
                # 使用语义检索
                results = await enhanced_service.get_semantic_memories(
                    project_id=self.project_id,
                    agent_type=self.AGENT_TYPE or self.name,
                    query_text=query_text,
                    limit=10,
                )
                memories = [entry for entry, _ in results]
            else:
                # 降级到默认选择
                memories = await enhanced_service._default_memory_selection(
                    self.project_id,
                    self.AGENT_TYPE or self.name,
                )

            if not memories:
                return ""

            # 格式化输出
            context_parts = ["【相关记忆】"]

            for entry in memories:
                importance_marker = ""
                if entry.importance.value in ["critical", "high"]:
                    importance_marker = "⭐ "

                context_parts.append(
                    f"- {importance_marker}[{entry.type.value}] {entry.content}"
                )

            return "\n".join(context_parts)

        except Exception as e:
            logger.warning(f"获取增强记忆上下文失败: {e}，降级到基础方法")
            return self.get_memory_context()

    async def _ensure_system_prompt_loaded(self):
        """
        确保系统提示词已加载（在异步上下文中调用）
        """
        if self._system_prompt_loaded or not self._pending_system_prompt_load:
            return

        if not self.project_id or not self.AGENT_TYPE:
            self._system_prompt_loaded = True
            return

        try:
            from app.services.agent_prompt_service import get_agent_prompt_service

            service = get_agent_prompt_service()
            prompt = await service.build_agent_prompt(
                agent_type=self.AGENT_TYPE,
                project_id=self.project_id,
            )

            if prompt:
                self.system_prompt = prompt
                logger.debug(f"Agent {self.name} 从模板加载 prompt 成功 (project={self.project_id}, type={self.AGENT_TYPE})")

        except Exception as e:
            logger.warning(f"Agent {self.name} 加载 prompt 失败: {e}")

        self._system_prompt_loaded = True
        self._pending_system_prompt_load = False

    @abstractmethod
    async def execute(self, input_data: Dict[str, Any]) -> AgentResponse:
        pass

    @abstractmethod
    def _get_default_variables(self) -> Dict[str, Any]:
        """
        获取默认变量（子类实现）

        Returns:
            Dict: 默认变量字典，用于 Prompt 模板渲染
        """
        pass

    async def _call_llm(
        self,
        messages: List,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        category: UsageCategory = UsageCategory.OTHER,
        memory_task_type: Optional[str] = None,
        memory_query_text: Optional[str] = None,
        db=None,
    ) -> str:
        """
        调用 LLM

        Args:
            messages: 消息列表
            temperature: 温度参数
            max_tokens: 最大 token 数
            category: 使用类别
            memory_task_type: 记忆选择的任务类型（用于上下文感知选择）
            memory_query_text: 记忆选择的查询文本（用于语义检索）
            db: 数据库连接（用于增强记忆服务）
        """
        if not self.model:
            raise ValueError(f"Agent {self.name} 未配置模型")

        # 确保系统提示词已加载（延迟加载）
        await self._ensure_system_prompt_loaded()

        # 如果设置了流式回调，使用流式输出
        if self._stream_callback:
            return await self._stream_llm(
                messages, temperature, max_tokens, category,
                on_chunk=self._stream_callback,
                memory_task_type=memory_task_type,
                memory_query_text=memory_query_text,
                db=db,
            )

        # 构建完整的 system prompt（包含记忆上下文）
        full_system_prompt = self.system_prompt
        if self._memory:
            # 使用增强记忆上下文（如果提供了 task_type 或 query_text）
            if memory_task_type or memory_query_text:
                memory_context = await self.get_enhanced_memory_context(
                    task_type=memory_task_type,
                    query_text=memory_query_text,
                    db=db,
                )
            else:
                memory_context = self.get_memory_context()
            if memory_context:
                full_system_prompt = f"{self.system_prompt}\n\n{memory_context}"

        if full_system_prompt:
            messages = [SystemMessage(content=full_system_prompt)] + messages

        response = await self.model.ainvoke(messages)

        # 处理不同模型的响应格式
        raw_content = response.content
        if isinstance(raw_content, str):
            content = raw_content
        elif isinstance(raw_content, list):
            # Anthropic 格式：可能是 TextBlock/ThinkingBlock 列表
            content = ""
            for block in raw_content:
                if hasattr(block, 'text'):
                    content += block.text
                # ThinkingBlock 跳过
        else:
            content = str(raw_content)

        # 尝试从响应中获取实际 token 使用量
        input_tokens = 0
        output_tokens = 0

        # LangChain 响应对象包含 usage_metadata
        if hasattr(response, 'usage_metadata') and response.usage_metadata:
            input_tokens = response.usage_metadata.get('input_tokens', 0)
            output_tokens = response.usage_metadata.get('output_tokens', 0)
        elif hasattr(response, 'response_metadata') and response.response_metadata:
            # OpenAI 格式
            token_usage = response.response_metadata.get('token_usage', {})
            if token_usage:
                input_tokens = token_usage.get('prompt_tokens', 0)
                output_tokens = token_usage.get('completion_tokens', 0)

        # 如果无法获取实际值，使用估算
        if input_tokens == 0:
            input_tokens = sum(len(msg.content) // 4 for msg in messages)
        if output_tokens == 0:
            output_tokens = len(content) // 4

        self._record_token_usage(input_tokens, output_tokens, category)

        return content

    async def _stream_llm(
        self,
        messages: List,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        category: UsageCategory = UsageCategory.OTHER,
        on_chunk: Optional[callable] = None,
        memory_task_type: Optional[str] = None,
        memory_query_text: Optional[str] = None,
        db=None,
    ) -> str:
        """
        流式调用 LLM，支持实时输出

        Args:
            messages: 消息列表
            temperature: 温度参数
            max_tokens: 最大 token 数
            category: 使用类别
            on_chunk: 每个 chunk 的回调函数，接收 (chunk_text: str) 参数
            memory_task_type: 记忆选择的任务类型
            memory_query_text: 记忆选择的查询文本
            db: 数据库连接

        Returns:
            str: 完整的响应内容
        """
        if not self.model:
            raise ValueError(f"Agent {self.name} 未配置模型")

        # 确保系统提示词已加载（延迟加载）
        await self._ensure_system_prompt_loaded()

        # 构建完整的 system prompt（包含记忆上下文）
        full_system_prompt = self.system_prompt
        if self._memory:
            # 使用增强记忆上下文（如果提供了 task_type 或 query_text）
            if memory_task_type or memory_query_text:
                memory_context = await self.get_enhanced_memory_context(
                    task_type=memory_task_type,
                    query_text=memory_query_text,
                    db=db,
                )
            else:
                memory_context = self.get_memory_context()
            if memory_context:
                full_system_prompt = f"{self.system_prompt}\n\n{memory_context}"

        if full_system_prompt:
            messages = [SystemMessage(content=full_system_prompt)] + messages

        full_content = ""
        last_chunk = None
        chunk_count = 0

        try:
            logger.info(f"Agent {self.name} 开始流式调用 LLM...")
            # 使用 astream 进行流式输出（添加超时保护）
            async def stream_with_timeout():
                nonlocal full_content, last_chunk, chunk_count
                async for chunk in self.model.astream(messages):
                    # 处理不同模型的响应格式
                    chunk_text = ""
                    if hasattr(chunk, 'content'):
                        content = chunk.content
                        # 如果是字符串，直接使用
                        if isinstance(content, str):
                            chunk_text = content
                        # 如果是列表（Anthropic 格式，可能包含 TextBlock/ThinkingBlock）
                        elif isinstance(content, list):
                            for block in content:
                                if hasattr(block, 'text'):
                                    chunk_text += block.text
                                # ThinkingBlock 跳过
                        else:
                            chunk_text = str(content)
                    else:
                        chunk_text = str(chunk)

                    full_content += chunk_text
                    last_chunk = chunk
                    chunk_count += 1

                    # 调用回调函数
                    if on_chunk:
                        try:
                            await on_chunk(chunk_text) if asyncio.iscoroutinefunction(on_chunk) else on_chunk(chunk_text)
                        except Exception as e:
                            logger.warning(f"流式输出回调失败: {e}")

            # 设置 5 分钟超时
            await asyncio.wait_for(stream_with_timeout(), timeout=300.0)

            logger.info(f"Agent {self.name} 流式调用完成，共 {chunk_count} 个 chunk，总长度 {len(full_content)} 字符")

        except asyncio.TimeoutError:
            logger.error(f"Agent {self.name} 流式调用超时（超过 300 秒）")
            # 返回已有内容
            if full_content:
                logger.info(f"Agent {self.name} 返回已获取的 {len(full_content)} 字符内容")
                return full_content
            raise
        except Exception as e:
            logger.error(f"流式调用 LLM 失败: {e}")
            # 如果流式失败，回退到普通调用
            full_content = await self._call_llm(messages, temperature, max_tokens, category)
            return full_content

        # 尝试从最后一个 chunk 获取 token 使用量
        input_tokens = 0
        output_tokens = 0

        if last_chunk and hasattr(last_chunk, 'usage_metadata') and last_chunk.usage_metadata:
            input_tokens = last_chunk.usage_metadata.get('input_tokens', 0)
            output_tokens = last_chunk.usage_metadata.get('output_tokens', 0)

        # 如果无法获取实际值，使用估算
        if input_tokens == 0:
            input_tokens = sum(len(msg.content) // 4 for msg in messages)
        if output_tokens == 0:
            output_tokens = len(full_content) // 4

        self._record_token_usage(input_tokens, output_tokens, category)

        return full_content

    def _record_token_usage(
        self,
        input_tokens: int,
        output_tokens: int,
        category: UsageCategory,
    ):
        """记录 token 使用量"""
        if not self.project_id:
            return

        try:
            # 从模型中提取 provider 和 model 信息
            provider = "anthropic"
            model = "claude"

            # 尝试从模型配置中获取更多信息
            if hasattr(self.model, 'model'):
                model = self.model.model
            if hasattr(self.model, 'model_name'):
                model = self.model.model_name

            # 获取 provider 信息
            model_str = str(self.model.__class__)
            if "Anthropic" in model_str:
                provider = "anthropic"
            elif "OpenAI" in model_str or "ChatOpenAI" in model_str:
                provider = "openai"

            # 异步记录 token 使用（lazy import 避免循环依赖）
            from app.services.token_tracker import token_tracker
            asyncio.create_task(
                token_tracker.record_usage(
                    project_id=self.project_id,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    provider=provider,
                    model=model,
                    category=category,
                    agent_name=self.name,
                )
            )
        except Exception as e:
            logger.warning(f"记录 token 使用失败: {e}")

    def _parse_json_response(self, text: str) -> Dict[str, Any]:
        import re

        # 尝试多种 JSON 提取模式
        patterns = [
            r"```json\s*(.*?)\s*```",  # 标准 markdown JSON 代码块
            r"```\s*(\{[\s\S]*?\})\s*```",  # 普通代码块中的 JSON 对象
            r"(\{[\s\S]*\})",  # 直接的 JSON 对象
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.DOTALL)
            if match:
                json_str = match.group(1).strip()
                try:
                    return json.loads(json_str)
                except json.JSONDecodeError:
                    continue

        # 最后尝试直接解析整个文本
        try:
            return json.loads(text.strip())
        except json.JSONDecodeError as e:
            logger.error(f"JSON 解析失败：{e}, 原始文本：{text[:500]}...")
            raise ValueError(f"Agent {self.name} 返回了无效的 JSON 格式")

    def add_to_history(self, role: str, content: str):
        if role == "human":
            self.message_history.append(HumanMessage(content=content))
        elif role == "ai":
            self.message_history.append(AIMessage(content=content))
        elif role == "system":
            self.message_history.append(SystemMessage(content=content))

    def clear_history(self):
        self.message_history = []

    def get_history(self) -> List:
        return self.message_history.copy()

    # ==================== Skill 集成 ====================

    async def load_skills(self) -> None:
        """
        加载绑定到当前 Agent 类型的 Skills

        从 Agent 模板的 skill_slots 中获取 Skill ID，然后从 SkillService 加载
        """
        if self._skills_loaded:
            return

        if not self.AGENT_TYPE:
            return

        try:
            from app.services.skill_service import get_skill_service
            service = get_skill_service()

            # 获取适用于此 Agent 类型的所有 Skills
            skills = await service.get_skills_for_agent_type(self.AGENT_TYPE)

            for skill in skills:
                if skill.is_enabled and skill.status.value == 'active':
                    self._skills[skill.id] = skill

            self._skills_loaded = True
            logger.info(f"Agent {self.name} 加载了 {len(self._skills)} 个 Skills")

        except Exception as e:
            logger.warning(f"Agent {self.name} 加载 Skills 失败: {e}")

    async def execute_skill(
        self,
        skill_id: str,
        parameters: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        执行指定的 Skill

        Args:
            skill_id: Skill ID
            parameters: 执行参数

        Returns:
            Dict: 执行结果
        """
        # 确保 Skills 已加载
        if not self._skills_loaded:
            await self.load_skills()

        # 检查 Skill 是否已加载
        if skill_id not in self._skills:
            # 尝试从服务获取
            try:
                from app.services.skill_service import get_skill_service
                service = get_skill_service()
                skill = await service.get_skill(skill_id)
                if skill:
                    self._skills[skill_id] = skill
                else:
                    return {"success": False, "error": f"Skill {skill_id} 不存在"}
            except Exception as e:
                return {"success": False, "error": f"加载 Skill 失败: {e}"}

        skill = self._skills[skill_id]

        try:
            from app.services.skill_service import get_skill_service, ExecuteSkillDTO
            service = get_skill_service()

            dto = ExecuteSkillDTO(
                skill_id=skill_id,
                project_id=self.project_id,
                agent_id=self.name,
                parameters=parameters or {},
            )

            result = await service.execute_skill(dto)
            return result.model_dump()

        except Exception as e:
            logger.error(f"执行 Skill {skill_id} 失败: {e}")
            return {"success": False, "error": str(e)}

    def get_knowledge_context(self) -> str:
        """
        获取所有 knowledge 类型 Skill 的内容

        用于在 Agent 的 system prompt 或 user message 中注入知识上下文

        Returns:
            str: 合并后的知识内容
        """
        knowledge_parts = []

        for skill_id, skill in self._skills.items():
            if skill.skill_type.value == 'knowledge' and skill.knowledge_content:
                knowledge_parts.append(f"【{skill.name}】\n{skill.knowledge_content}")

        return "\n\n".join(knowledge_parts) if knowledge_parts else ""

    def get_skill(self, skill_id: str) -> Optional[Any]:
        """获取已加载的 Skill"""
        return self._skills.get(skill_id)

    def get_all_skills(self) -> Dict[str, Any]:
        """获取所有已加载的 Skills"""
        return self._skills.copy()

    # ==================== 内置工具函数（可作为 Skill 调用）====================

    async def count_words(self, text: str) -> int:
        """
        统计文本字数（支持中英文混合）

        可以作为工具 Skill 调用，也可直接调用

        Args:
            text: 输入文本

        Returns:
            int: 字数
        """
        if not text:
            return 0

        try:
            from app.utils.text_utils import count_mixed_text
            return count_mixed_text(text)
        except ImportError:
            # 回退到简单统计
            import re
            chinese = len(re.findall(r'[\u4e00-\u9fff]', text))
            english = len(re.findall(r'\b[a-zA-Z]+\b', text))
            return chinese + english

    async def __aenter__(self):
        await self._lock.acquire()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self._lock.release()
