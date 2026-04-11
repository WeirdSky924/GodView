"""
Agent 记忆服务 - 管理 Agent 的持久化记忆

职责：
1. 从数据库加载 Agent 记忆
2. 保存 Agent 状态到数据库
3. 管理记忆的生命周期（添加、查询、遗忘）
4. 提供记忆检索功能
"""

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.models.agent_memory import (
    AgentMemory,
    AgentKnowledge,
    MemoryEntry,
    MemoryEntryCreate,
    MemoryType,
    MemoryImportance,
)

logger = logging.getLogger(__name__)


class AgentMemoryService:
    """Agent 记忆服务"""

    def __init__(self, db=None):
        self._db = db
        # 内存缓存
        self._memory_cache: Dict[str, AgentMemory] = {}

    async def get_memory(
        self,
        project_id: str,
        agent_type: str,
        agent_id: Optional[str] = None,
    ) -> AgentMemory:
        """
        获取 Agent 记忆（优先从缓存，否则从数据库加载）

        Args:
            project_id: 项目 ID
            agent_type: Agent 类型
            agent_id: Agent 实例 ID（可选）

        Returns:
            AgentMemory: Agent 记忆对象
        """
        cache_key = f"{project_id}:{agent_type}:{agent_id or 'default'}"

        # 检查缓存
        if cache_key in self._memory_cache:
            logger.debug(f"从缓存获取 Agent 记忆: {cache_key}")
            return self._memory_cache[cache_key]

        # 从数据库加载
        memory = await self._load_from_db(project_id, agent_type, agent_id)

        if memory:
            logger.info(f"从数据库加载 Agent 记忆: {agent_type} (项目: {project_id})")
        else:
            # 创建新的记忆对象，使用确定性的 ID
            deterministic_id = self._generate_memory_id(project_id, agent_type, agent_id)
            memory = AgentMemory(
                id=deterministic_id,
                project_id=project_id,
                agent_type=agent_type,
                agent_id=agent_id,
            )
            logger.info(f"创建新的 Agent 记忆: {agent_type} (项目: {project_id}, ID: {deterministic_id})")

        # 缓存
        self._memory_cache[cache_key] = memory
        return memory

    def _generate_memory_id(self, project_id: str, agent_type: str, agent_id: Optional[str]) -> str:
        """
        生成确定性的记忆 ID（基于 project_id + agent_type + agent_id）

        确保相同的组合始终生成相同的 ID，避免主键冲突
        """
        import hashlib
        key = f"{project_id}:{agent_type}:{agent_id or 'default'}"
        hash_val = hashlib.md5(key.encode()).hexdigest()[:12]
        return f"memory_{hash_val}"

    async def _load_from_db(
        self,
        project_id: str,
        agent_type: str,
        agent_id: Optional[str] = None,
    ) -> Optional[AgentMemory]:
        """从数据库加载记忆"""
        if not self._db:
            return None

        try:
            query = """
                SELECT id, project_id, agent_type, agent_id,
                       memories, knowledge, working_memory,
                       total_memories, last_execution, execution_count,
                       created_at, updated_at
                FROM agent_memories
                WHERE project_id = CAST(:project_id AS UUID)
                  AND agent_type = :agent_type
                  AND (agent_id = :agent_id OR (agent_id IS NULL AND :agent_id IS NULL))
            """
            results = await self._db.execute_query(
                query,
                {
                    "project_id": project_id,
                    "agent_type": agent_type,
                    "agent_id": agent_id,
                },
            )

            if results and len(results) > 0:
                row = results[0]
                memory = AgentMemory(
                    id=row["id"],
                    project_id=str(row["project_id"]),
                    agent_type=row["agent_type"],
                    agent_id=row.get("agent_id"),
                    memories=self._parse_memories(row.get("memories", [])),
                    knowledge=AgentKnowledge(**row.get("knowledge", {})),
                    working_memory=row.get("working_memory", {}),
                    total_memories=row.get("total_memories", 0),
                    last_execution=row.get("last_execution"),
                    execution_count=row.get("execution_count", 0),
                    created_at=row.get("created_at", datetime.now()),
                    updated_at=row.get("updated_at", datetime.now()),
                )
                return memory

        except Exception as e:
            logger.error(f"加载 Agent 记忆失败: {e}")

        return None

    def _parse_memories(self, memories_data: Any) -> List[MemoryEntry]:
        """解析记忆数据"""
        if not memories_data:
            return []

        if isinstance(memories_data, str):
            try:
                memories_data = json.loads(memories_data)
            except:
                return []

        entries = []
        for item in memories_data:
            try:
                entry = MemoryEntry(
                    id=item.get("id", str(datetime.now().timestamp())),
                    timestamp=datetime.fromisoformat(item["timestamp"])
                    if isinstance(item.get("timestamp"), str)
                    else item.get("timestamp", datetime.now()),
                    type=MemoryType(item.get("type", "observation")),
                    importance=MemoryImportance(item.get("importance", "medium")),
                    content=item.get("content", ""),
                    summary=item.get("summary"),
                    context=item.get("context", {}),
                    tags=item.get("tags", []),
                    related_chapter=item.get("related_chapter"),
                    related_characters=item.get("related_characters", []),
                    access_count=item.get("access_count", 0),
                    last_accessed=item.get("last_accessed"),
                )
                entries.append(entry)
            except Exception as e:
                logger.warning(f"解析记忆条目失败: {e}")

        return entries

    async def save_memory(self, memory: AgentMemory) -> bool:
        """
        保存 Agent 记忆到数据库

        Args:
            memory: Agent 记忆对象

        Returns:
            bool: 是否保存成功
        """
        if not self._db:
            logger.warning("数据库未连接，无法保存 Agent 记忆")
            return False

        try:
            memory.updated_at = datetime.now()

            # 序列化记忆（使用 mode='json' 处理 datetime 等类型）
            memories_json = json.dumps([m.model_dump(mode='json') for m in memory.memories], default=str)
            knowledge_json = json.dumps(memory.knowledge.model_dump(mode='json'), default=str)
            working_memory_json = json.dumps(memory.working_memory, default=str)

            query = """
                INSERT INTO agent_memories (
                    id, project_id, agent_type, agent_id,
                    memories, knowledge, working_memory,
                    total_memories, last_execution, execution_count,
                    created_at, updated_at
                ) VALUES (
                    :id, CAST(:project_id AS UUID), :agent_type, :agent_id,
                    CAST(:memories AS jsonb), CAST(:knowledge AS jsonb), CAST(:working_memory AS jsonb),
                    :total_memories, :last_execution, :execution_count,
                    :created_at, :updated_at
                )
                ON CONFLICT ON CONSTRAINT unique_agent_in_project DO UPDATE SET
                    memories = EXCLUDED.memories,
                    knowledge = EXCLUDED.knowledge,
                    working_memory = EXCLUDED.working_memory,
                    total_memories = EXCLUDED.total_memories,
                    last_execution = EXCLUDED.last_execution,
                    execution_count = EXCLUDED.execution_count,
                    updated_at = EXCLUDED.updated_at,
                    id = EXCLUDED.id
            """

            await self._db.execute_write(
                query,
                {
                    "id": memory.id,
                    "project_id": memory.project_id,
                    "agent_type": memory.agent_type,
                    "agent_id": memory.agent_id,
                    "memories": memories_json,
                    "knowledge": knowledge_json,
                    "working_memory": working_memory_json,
                    "total_memories": memory.total_memories,
                    "last_execution": memory.last_execution,
                    "execution_count": memory.execution_count,
                    "created_at": memory.created_at,
                    "updated_at": memory.updated_at,
                },
            )

            logger.info(
                f"保存 Agent 记忆成功: {memory.agent_type} "
                f"(项目: {memory.project_id}, 记忆数: {memory.total_memories})"
            )
            return True

        except Exception as e:
            logger.error(f"保存 Agent 记忆失败: {e}")
            return False

    async def add_memory_entry(
        self,
        project_id: str,
        agent_type: str,
        entry: MemoryEntryCreate,
        agent_id: Optional[str] = None,
    ) -> Optional[MemoryEntry]:
        """
        添加记忆条目

        Args:
            project_id: 项目 ID
            agent_type: Agent 类型
            entry: 记忆条目创建请求
            agent_id: Agent 实例 ID

        Returns:
            MemoryEntry: 创建的记忆条目
        """
        memory = await self.get_memory(project_id, agent_type, agent_id)

        new_entry = MemoryEntry(
            type=entry.type,
            importance=entry.importance,
            content=entry.content,
            tags=entry.tags,
            context=entry.context,
            related_chapter=entry.related_chapter,
            related_characters=entry.related_characters,
        )

        memory.memories.append(new_entry)
        memory.total_memories = len(memory.memories)

        await self.save_memory(memory)

        logger.info(
            f"添加记忆条目: {agent_type} - {entry.type.value}: "
            f"{entry.content[:50]}..."
        )

        return new_entry

    async def record_execution(
        self,
        project_id: str,
        agent_type: str,
        input_summary: str,
        output_summary: str,
        decisions: List[Dict[str, Any]] = None,
        observations: List[str] = None,
        duration_ms: int = None,
        tokens_used: int = None,
        success: bool = True,
        error_message: str = None,
        agent_id: Optional[str] = None,
        node_id: Optional[str] = None,
        workflow_execution_id: Optional[str] = None,
    ) -> bool:
        """
        记录 Agent 执行

        Args:
            project_id: 项目 ID
            agent_type: Agent 类型
            input_summary: 输入摘要
            output_summary: 输出摘要
            decisions: 决策列表
            observations: 观察列表
            duration_ms: 执行时长（毫秒）
            tokens_used: 使用的 token 数
            success: 是否成功
            error_message: 错误信息
            agent_id: Agent 实例 ID
            node_id: 工作流节点 ID
            workflow_execution_id: 工作流执行 ID

        Returns:
            bool: 是否记录成功
        """
        # 更新记忆对象
        memory = await self.get_memory(project_id, agent_type, agent_id)
        memory.last_execution = datetime.now()
        memory.execution_count += 1

        # 添加观察记忆
        if observations:
            for obs in observations:
                memory.add_memory(
                    content=obs,
                    memory_type=MemoryType.OBSERVATION,
                    importance=MemoryImportance.LOW,
                )

        # 添加决策记忆
        if decisions:
            for decision in decisions:
                memory.add_memory(
                    content=decision.get("content", ""),
                    memory_type=MemoryType.DECISION,
                    importance=MemoryImportance.HIGH,
                    context=decision.get("context", {}),
                    tags=decision.get("tags", []),
                )

        await self.save_memory(memory)

        # 记录执行日志
        if self._db:
            try:
                query = """
                    INSERT INTO agent_execution_logs (
                        memory_id, project_id, agent_type,
                        execution_type, node_id, workflow_execution_id,
                        input_summary, output_summary,
                        decisions, observations,
                        duration_ms, tokens_used,
                        success, error_message,
                        started_at, completed_at
                    ) VALUES (
                        :memory_id, CAST(:project_id AS UUID), :agent_type,
                        :execution_type, :node_id, :workflow_execution_id,
                        :input_summary, :output_summary,
                        CAST(:decisions AS jsonb), CAST(:observations AS jsonb),
                        :duration_ms, :tokens_used,
                        :success, :error_message,
                        :started_at, CURRENT_TIMESTAMP
                    )
                """

                await self._db.execute_write(
                    query,
                    {
                        "memory_id": memory.id,
                        "project_id": project_id,
                        "agent_type": agent_type,
                        "execution_type": "workflow_node" if node_id else "manual",
                        "node_id": node_id,
                        "workflow_execution_id": workflow_execution_id,
                        "input_summary": input_summary[:500] if input_summary else None,
                        "output_summary": output_summary[:500]
                        if output_summary
                        else None,
                        "decisions": json.dumps(decisions or []),
                        "observations": json.dumps(observations or []),
                        "duration_ms": duration_ms,
                        "tokens_used": tokens_used,
                        "success": success,
                        "error_message": error_message,
                        "started_at": memory.last_execution,
                    },
                )

            except Exception as e:
                logger.error(f"记录执行日志失败: {e}")

        return True

    async def get_relevant_memories(
        self,
        project_id: str,
        agent_type: str,
        query_text: str,
        limit: int = 5,
        agent_id: Optional[str] = None,
    ) -> List[MemoryEntry]:
        """
        获取相关记忆（基于关键词匹配）

        Args:
            project_id: 项目 ID
            agent_type: Agent 类型
            query_text: 查询文本
            limit: 返回数量限制
            agent_id: Agent 实例 ID

        Returns:
            List[MemoryEntry]: 相关记忆列表
        """
        memory = await self.get_memory(project_id, agent_type, agent_id)

        # 简单关键词匹配（后续可以改用向量搜索）
        query_words = set(query_text.lower().split())

        scored_memories = []
        for entry in memory.memories:
            # 计算相关性分数
            content_words = set(entry.content.lower().split())
            tag_words = set(tag.lower() for tag in entry.tags)

            score = len(query_words & content_words) + len(query_words & tag_words) * 2

            # 重要性加权
            importance_weight = {
                MemoryImportance.CRITICAL: 3,
                MemoryImportance.HIGH: 2,
                MemoryImportance.MEDIUM: 1,
                MemoryImportance.LOW: 0.5,
                MemoryImportance.EPHEMERAL: 0.1,
            }
            score *= importance_weight.get(entry.importance, 1)

            if score > 0:
                scored_memories.append((score, entry))

        # 排序并返回
        scored_memories.sort(key=lambda x: x[0], reverse=True)
        return [entry for _, entry in scored_memories[:limit]]

    def clear_cache(self, project_id: str = None):
        """清除缓存"""
        if project_id:
            keys_to_remove = [
                k for k in self._memory_cache if k.startswith(project_id)
            ]
            for key in keys_to_remove:
                del self._memory_cache[key]
        else:
            self._memory_cache.clear()

        logger.info(f"清除 Agent 记忆缓存: {project_id or '全部'}")


# 单例实例
_memory_service: Optional[AgentMemoryService] = None


def get_memory_service(db=None) -> AgentMemoryService:
    """获取记忆服务单例"""
    global _memory_service
    if _memory_service is None:
        _memory_service = AgentMemoryService(db)
    elif db is not None:
        # 始终更新数据库连接（可能是新的会话）
        _memory_service._db = db
    return _memory_service
