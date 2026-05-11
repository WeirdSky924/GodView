"""
工作流执行引擎
v8 Agent协作可视化工作台
"""

import asyncio
import json
import logging
import random
import re
import uuid
from collections import defaultdict, deque
from datetime import datetime, timedelta
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Set

from app.agents.base import AgentResponse
from app.models.agent_template import AgentType
from app.models.agent_output_contract import (
    AgentOutputContract,
    DEFAULT_AGENT_OUTPUT_CONTRACT_REGISTRY,
    OutputContractConsumer,
    OutputContractMode,
    OutputContractScene,
)
from app.models.workflow_definition import (
    NodeType,
    NodeStatus,
    WorkflowDefinition,
    WorkflowNode,
    WorkflowEdge,
    WorkflowValidationResult,
    WorkflowDefinitionCreate,
    WorkflowDefinitionUpdate,
)
from app.models.workflow_execution import (
    WorkflowStatus,
    NodeExecutionState,
    WorkflowExecution,
    WorkflowExecutionCreate,
)
from app.services.operation_lifecycle_service import OperationLifecycleService
from app.services.redis_service import redis_service
from app.services.workflow_node_catalog import normalize_workflow_node_data, normalize_workflow_nodes
from app.services.workflow_node_registry import (
    get_workflow_node_adapter,
    get_workflow_node_profile,
)
from app.services.workflow_replay_export_service import (
    get_workflow_replay_export_service,
)
from app.services.trace_service import TraceService, get_trace_service
from app.services.workflow_state import (
    CANONICAL_STATE_KEYS,
    PROTECTED_CONTEXT_KEYS,
    RUNTIME_STATE_KEYS,
    get_workflow_state,
    is_protected_context_key,
)
from app.services.agent_config_service import get_agent_config_service
from app.config import settings

logger = logging.getLogger(__name__)


class ChapterReadinessBlockedError(ValueError):
    """章节存在未解决 blocking 资源需求，禁止启动生成工作流。"""

    def __init__(self, payload: Dict[str, Any]):
        self.payload = payload
        chapter_num = payload.get("chapter_num")
        message = payload.get("message")
        if not message:
            blocking_count = len(payload.get("blocking_requirements") or [])
            message = f"第 {chapter_num or '未知'} 章资源未就绪，存在 {blocking_count} 个 blocking 需求"
        super().__init__(str(message))


class WorkflowOperationError(ValueError):
    """工作流执行操作被状态机拒绝。"""

    def __init__(
        self,
        message: str,
        *,
        code: str,
        operation: str,
        execution_id: str,
        status: Optional[str] = None,
        http_status: int = 409,
        payload: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message)
        self.message = message
        self.code = code
        self.operation = operation
        self.execution_id = execution_id
        self.status = status
        self.http_status = http_status
        self.payload = payload or {}

    def to_payload(self) -> Dict[str, Any]:
        return {
            "success": False,
            "code": self.code,
            "operation": self.operation,
            "execution_id": self.execution_id,
            "status": self.status,
            "message": self.message,
            **self.payload,
        }


@dataclass
class WorkflowExecutionStartResult:
    """工作流启动结果，保留真实幂等命中语义供 API/UI 展示。"""

    execution_id: str
    replayed: bool = False
    deduplicated: bool = False


class WorkflowEngine:
    """工作流执行引擎"""

    WORKFLOW_RUNTIME_CONSTRAINTS_PROMPT_ID = "function_workflow_runtime_constraints"

    def __init__(self):
        # 执行中的工作流实例
        self._executions: Dict[str, WorkflowExecution] = {}
        # 运行中 task registry，避免刷新/恢复后重复启动同一 execution
        self._running_tasks: Dict[str, asyncio.Task] = {}
        self._execution_locks: Dict[str, asyncio.Lock] = {}
        # 工作流定义缓存
        self._workflows: Dict[str, WorkflowDefinition] = {}
        # WebSocket 广播回调
        self._broadcast_callback: Optional[Callable] = None
        self._broadcast_discussion_message: Optional[Callable] = None
        # 执行事件订阅者：execution_id -> queues
        self._event_subscribers: Dict[str, Set[asyncio.Queue]] = defaultdict(set)
        # Agent 实例获取回调
        self._agent_provider: Optional[Callable] = None
        # 干预队列：execution_id -> List[干预消息]
        self._intervention_queues: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        # 干预锁：确保线程安全
        self._intervention_locks: Dict[str, asyncio.Lock] = {}
        # 输入完成事件：execution_id -> asyncio.Event
        self._input_events: Dict[str, asyncio.Event] = {}
        self._workflow_config_prompt_traces: Dict[str, Dict[str, Any]] = {}

    def _workflow_config_trace_key(
        self,
        agent_type: AgentType,
        project_id: Optional[str],
        scenario: str,
    ) -> str:
        return f"{project_id or 'global'}::{agent_type.value}::{scenario or 'default'}"

    async def _build_workflow_node_prompt_trace(
        self,
        agent_type: str,
        project_id: Optional[str],
        scenario: Optional[str],
        variables: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """解析工作流节点运行时 prompt trace，供 node output metadata 使用。"""
        normalized_agent_type = (agent_type or "").strip() or "unknown"
        resolved_scenario = scenario or "default"
        if not project_id:
            return {
                "agent_type": normalized_agent_type,
                "scenario": resolved_scenario,
                "project_id": project_id,
                "template_id": None,
                "template_scenario": None,
                "config_id": None,
                "prompt_ids": [],
                "skill_ids": [],
                "skills": None,
                "writing_rule_ids": [],
                "writing_rules": None,
                "context_blocks": [],
                "fallbacks_used": [],
                "deprecated_sources_used": [],
            }

        try:
            from app.services.agent_prompt_service import get_agent_prompt_service

            prompt_data = await get_agent_prompt_service().build_agent_prompt_with_trace(
                agent_type=normalized_agent_type,
                project_id=project_id,
                variables=variables or {},
                scenario=resolved_scenario,
            )
            return prompt_data.get("trace", {}) or {}
        except Exception as e:
            logger.warning(
                "解析 workflow node prompt trace 失败: agent=%s, scenario=%s, error=%s",
                normalized_agent_type,
                resolved_scenario,
                e,
            )
            return {
                "agent_type": normalized_agent_type,
                "scenario": resolved_scenario,
                "project_id": project_id,
                "template_id": None,
                "template_scenario": None,
                "config_id": None,
                "prompt_ids": [],
                "skill_ids": [],
                "skills": None,
                "writing_rule_ids": [],
                "writing_rules": None,
                "context_blocks": [],
                "fallbacks_used": ["workflow_node_prompt_trace_unavailable"],
                "deprecated_sources_used": [],
            }

    def _attach_prompt_render_trace_metadata(
        self,
        output: Any,
        trace: Optional[Dict[str, Any]],
        source: str = "agent_template_runtime",
    ) -> Any:
        """把 prompt render trace 附加到节点输出 metadata，不覆盖已有 trace。"""
        if not isinstance(output, dict) or not trace:
            return output

        metadata = output.get("metadata") if isinstance(output.get("metadata"), dict) else {}
        metadata.setdefault("prompt_render_trace", trace)
        metadata.setdefault("config_prompt_source", source)
        output["metadata"] = metadata
        return output

    def set_broadcast_callback(self, callback: Callable):
        """设置 WebSocket 广播回调"""
        self._broadcast_callback = callback

    def set_discussion_broadcast_callback(self, callback: Optional[Callable]):
        """设置讨论/角色演绎消息广播回调。"""
        self._broadcast_discussion_message = callback

    async def _broadcast_discussion_message_event(
        self,
        execution_id: str,
        message: Dict[str, Any],
        **flags: Any,
    ) -> None:
        """广播讨论/角色演绎消息，未注册专用回调时降级为普通 workflow event。"""
        if self._broadcast_discussion_message:
            await self._broadcast_discussion_message(execution_id, message, **flags)
            return
        payload = {"message": message}
        if flags:
            payload.update(flags)
        await self._broadcast_status(execution_id, "discussion_message", payload)

    def subscribe_execution_events(
        self,
        execution_id: str,
        max_queue_size: int = 100,
    ) -> asyncio.Queue:
        """订阅工作流执行事件。"""
        queue: asyncio.Queue = asyncio.Queue(maxsize=max_queue_size)
        self._event_subscribers[execution_id].add(queue)
        return queue

    def unsubscribe_execution_events(self, execution_id: str, queue: asyncio.Queue):
        """取消订阅工作流执行事件。"""
        subscribers = self._event_subscribers.get(execution_id)
        if not subscribers:
            return

        subscribers.discard(queue)
        if not subscribers:
            self._event_subscribers.pop(execution_id, None)

    def set_agent_provider(self, provider: Callable):
        """设置 Agent 实例获取回调"""
        self._agent_provider = provider

    # ==================== 干预队列管理 ====================

    async def add_intervention(
        self,
        execution_id: str,
        agent_type: str,
        message: str,
        user_id: Optional[str] = None,
    ) -> bool:
        """
        向工作流添加干预消息

        Args:
            execution_id: 工作流执行ID
            agent_type: 目标Agent类型
            message: 干预消息内容
            user_id: 用户ID（可选）

        Returns:
            bool: 是否成功添加
        """
        if execution_id not in self._executions:
            logger.warning(f"工作流执行不存在: {execution_id}")
            return False

        # 确保有锁
        if execution_id not in self._intervention_locks:
            self._intervention_locks[execution_id] = asyncio.Lock()

        async with self._intervention_locks[execution_id]:
            intervention = {
                "id": f"intervention_{datetime.now().strftime('%Y%m%d%H%M%S%f')}",
                "agent_type": agent_type,
                "message": message,
                "user_id": user_id,
                "timestamp": datetime.now().isoformat(),
                "processed": False,
            }
            self._intervention_queues[execution_id].append(intervention)
            logger.info(f"添加干预到队列: {execution_id} -> {agent_type}: {message[:50]}...")

            # 广播干预已接收
            await self._broadcast_status(execution_id, "intervention_queued", {
                "intervention_id": intervention["id"],
                "agent_type": agent_type,
                "message": message,
            })

        return True

    async def get_pending_interventions(
        self,
        execution_id: str,
        agent_type: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        获取待处理的干预消息

        Args:
            execution_id: 工作流执行ID
            agent_type: 可选，筛选特定Agent的干预

        Returns:
            List: 待处理的干预消息列表
        """
        if execution_id not in self._intervention_queues:
            return []

        if execution_id not in self._intervention_locks:
            return []

        async with self._intervention_locks[execution_id]:
            pending = [
                iv for iv in self._intervention_queues[execution_id]
                if not iv["processed"]
            ]
            if agent_type:
                pending = [iv for iv in pending if iv["agent_type"] == agent_type]
            return pending.copy()

    async def mark_intervention_processed(
        self,
        execution_id: str,
        intervention_id: str,
    ):
        """标记干预消息为已处理"""
        if execution_id not in self._intervention_locks:
            return

        async with self._intervention_locks[execution_id]:
            for iv in self._intervention_queues[execution_id]:
                if iv["id"] == intervention_id:
                    iv["processed"] = True
                    break

    async def clear_interventions(self, execution_id: str):
        """清除工作流的所有干预消息"""
        if execution_id in self._intervention_queues:
            del self._intervention_queues[execution_id]
        if execution_id in self._intervention_locks:
            del self._intervention_locks[execution_id]

    # ==================== 工作流定义 CRUD ====================

    def _normalize_workflow_nodes(self, nodes: List[WorkflowNode]) -> List[WorkflowNode]:
        """规范化工作流节点的显示名称与兼容字段。"""
        return [WorkflowNode(**normalize_workflow_node_data(node.model_dump())) for node in nodes]

    async def create_workflow(
        self,
        definition: WorkflowDefinitionCreate,
        db=None,
    ) -> WorkflowDefinition:
        """创建工作流定义"""
        workflow = WorkflowDefinition(
            project_id=definition.project_id,
            name=definition.name,
            description=definition.description,
            nodes=self._normalize_workflow_nodes(definition.nodes),
            edges=definition.edges,
            variables=definition.variables,
            is_template=definition.is_template,
        )

        # 验证工作流
        validation = self.validate_workflow(workflow)
        if not validation.valid:
            raise ValueError(f"工作流验证失败: {validation.errors}")

        # 保存到数据库
        if db:
            await self._save_workflow_to_db(workflow, db)

        self._workflows[workflow.id] = workflow
        logger.info(f"创建工作流定义: {workflow.id} - {workflow.name}")
        return workflow

    async def get_workflow(self, workflow_id: str, db=None) -> Optional[WorkflowDefinition]:
        """获取工作流定义"""
        # 先查缓存
        if workflow_id in self._workflows:
            return self._workflows[workflow_id]

        # 查数据库
        if db:
            workflow = await self._load_workflow_from_db(workflow_id, db)
            if workflow:
                self._workflows[workflow_id] = workflow
            return workflow

        return None

    async def update_workflow(
        self,
        workflow_id: str,
        update: WorkflowDefinitionUpdate,
        db=None,
    ) -> Optional[WorkflowDefinition]:
        """更新工作流定义"""
        workflow = await self.get_workflow(workflow_id, db)
        if not workflow:
            return None
        if workflow.is_template and workflow.project_id is None:
            raise PermissionError("全局模板不能直接修改，请先复制到项目后再编辑")

        if update.name is not None:
            workflow.name = update.name
        if update.description is not None:
            workflow.description = update.description
        if update.nodes is not None:
            # ========== 自动修正节点类型与规范化名称 ==========
            workflow.nodes = self._normalize_workflow_nodes(update.nodes)

        if update.edges is not None:
            # ========== 自动清理无效的边 ==========
            # 过滤掉引用不存在节点的边
            node_ids = {node.id for node in workflow.nodes}
            valid_edges = []
            invalid_edges = []
            for edge in update.edges:
                if edge.source in node_ids and edge.target in node_ids:
                    valid_edges.append(edge)
                else:
                    invalid_edges.append(edge)
                    logger.warning(f"过滤无效边: {edge.source} -> {edge.target} (源存在: {edge.source in node_ids}, 目标存在: {edge.target in node_ids})")

            if invalid_edges:
                logger.info(f"自动过滤了 {len(invalid_edges)} 条无效边")

            workflow.edges = valid_edges
        if update.variables is not None:
            workflow.variables = update.variables
        if update.is_template is not None:
            workflow.is_template = update.is_template

        # 验证更新后的工作流
        validation = self.validate_workflow(workflow)
        if not validation.valid:
            raise ValueError(f"工作流验证失败: {validation.errors}")

        workflow.updated_at = datetime.now()

        # 更新数据库
        if db:
            await self._save_workflow_to_db(workflow, db)

        logger.info(f"更新工作流定义: {workflow_id}")
        return workflow

    async def delete_workflow(self, workflow_id: str, db=None) -> bool:
        """删除工作流定义"""
        workflow = await self.get_workflow(workflow_id, db)
        if not workflow:
            return False
        if workflow.is_template and workflow.project_id is None:
            raise PermissionError("全局模板不能直接删除")

        if workflow_id in self._workflows:
            del self._workflows[workflow_id]

        if db:
            await self._delete_workflow_from_db(workflow_id, db)

        logger.info(f"删除工作流定义: {workflow_id}")
        return True

    async def list_workflows(
        self,
        project_id: str,
        include_templates: bool = False,
        db=None,
    ) -> List[WorkflowDefinition]:
        """获取工作流列表"""
        if db:
            return await self._list_workflows_from_db(project_id, include_templates, db)

        # 从缓存过滤
        result = []
        for wf in self._workflows.values():
            if wf.project_id == project_id:
                result.append(wf)
            elif include_templates and wf.is_template:
                result.append(wf)
        return result

    # ==================== 工作流验证 ====================

    def validate_workflow(self, workflow: WorkflowDefinition) -> WorkflowValidationResult:
        """验证工作流有效性"""
        errors = []
        warnings = []
        node_ids = {node.id for node in workflow.nodes}

        # 检查节点
        if len(workflow.nodes) == 0:
            errors.append("工作流没有节点")
            return WorkflowValidationResult(
                valid=False,
                errors=errors,
                warnings=warnings,
                node_count=0,
                edge_count=0,
            )

        # 先修复节点类型并规范标签（兼容旧数据）
        fixed_nodes = self._normalize_workflow_nodes(workflow.nodes)

        # 用修复后的节点重新创建 workflow 用于验证
        from app.models.workflow_definition import WorkflowDefinition as WfDef
        fixed_workflow = WfDef(
            id=workflow.id,
            project_id=workflow.project_id,
            name=workflow.name,
            description=workflow.description,
            nodes=fixed_nodes,
            edges=workflow.edges,
            variables=workflow.variables,
            is_template=workflow.is_template,
            created_at=workflow.created_at,
            updated_at=workflow.updated_at,
        )

        # 检查开始和结束节点
        start_nodes = [n for n in fixed_nodes if n.node_type == NodeType.START]
        end_nodes = [n for n in fixed_nodes if n.node_type == NodeType.END]

        if len(start_nodes) == 0:
            errors.append("工作流缺少开始节点")
        elif len(start_nodes) > 1:
            warnings.append("工作流有多个开始节点")

        if len(end_nodes) == 0:
            errors.append("工作流缺少结束节点")

        # 检查边的源和目标节点是否存在
        # 无效边会导致工作流死锁，必须作为错误处理
        invalid_edges = []
        for edge in workflow.edges:
            if edge.source not in node_ids:
                invalid_edges.append(f"边 '{edge.id}': 源节点 '{edge.source}' 不存在")
            if edge.target not in node_ids:
                invalid_edges.append(f"边 '{edge.id}': 目标节点 '{edge.target}' 不存在")

        if invalid_edges:
            # 自动修复：过滤掉无效边
            valid_edges = [
                edge for edge in workflow.edges
                if edge.source in node_ids and edge.target in node_ids
            ]
            if len(valid_edges) < len(workflow.edges):
                warnings.append(f"自动过滤了 {len(workflow.edges) - len(valid_edges)} 条无效边: {invalid_edges}")
                # 更新 workflow 的 edges
                workflow.edges = valid_edges

        # 检查是否有意外的环（retry 循环是允许的）
        has_cycle, cycle_info = self._detect_cycle(fixed_nodes, workflow.edges)
        if has_cycle:
            # 检查是否是合法的 retry 循环
            is_valid_retry_loop = self._is_valid_retry_loop(fixed_workflow, cycle_info)
            if not is_valid_retry_loop:
                errors.append(f"工作流存在意外的循环依赖: {cycle_info}")
            else:
                warnings.append("工作流包含 retry 循环（这是允许的）")

        # 检查连通性
        is_connected = self._check_connectivity(fixed_nodes, workflow.edges)
        if not is_connected:
            warnings.append("工作流存在未连接的节点")

        # 检查 Agent 节点是否有 agent_type
        for node in fixed_nodes:
            if node.node_type == NodeType.AGENT and not node.agent_type:
                errors.append(f"Agent节点 '{node.label}' 缺少 agent_type")

        return WorkflowValidationResult(
            valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            node_count=len(workflow.nodes),
            edge_count=len(workflow.edges),
            has_cycle=has_cycle and not self._is_valid_retry_loop(fixed_workflow, cycle_info),
            is_connected=is_connected,
        )

    def _detect_cycle(self, nodes: List[WorkflowNode], edges: List[WorkflowEdge]) -> tuple:
        """检测图中是否存在环，返回 (是否有环, 循环信息)"""
        # 构建邻接表
        graph = defaultdict(list)
        for edge in edges:
            graph[edge.source].append(edge.target)

        # DFS 检测环并记录路径
        visited = set()
        rec_stack = set()
        path = []
        cycle_path = []

        def dfs(node_id: str) -> bool:
            visited.add(node_id)
            rec_stack.add(node_id)
            path.append(node_id)

            for neighbor in graph[node_id]:
                if neighbor not in visited:
                    if dfs(neighbor):
                        return True
                elif neighbor in rec_stack:
                    # 找到环，记录循环路径
                    cycle_start = path.index(neighbor)
                    cycle_path.extend(path[cycle_start:] + [neighbor])
                    return True

            path.pop()
            rec_stack.remove(node_id)
            return False

        for node in nodes:
            if node.id not in visited:
                if dfs(node.id):
                    cycle_info = " -> ".join(cycle_path) if cycle_path else "未知"
                    return True, cycle_info

        return False, ""

    def _is_valid_retry_loop(self, workflow: WorkflowDefinition, cycle_info: str) -> bool:
        """检查是否是合法的 retry 循环"""
        # retry 循环的特征：
        # 1. 从条件节点的 retry 分支回到 start 节点
        # 2. 或者从任何节点回到之前的某个节点（形成重试逻辑）

        # 获取 start 节点 ID
        start_nodes = [n for n in workflow.nodes if n.node_type == NodeType.START]
        if not start_nodes:
            # 如果没有明确的 start 节点，检查是否有 id='start' 的节点
            start_nodes = [n for n in workflow.nodes if n.id == "start"]
            if not start_nodes:
                return False
        start_id = start_nodes[0].id

        # 检查是否有边回到 start（这是最常见合法循环）
        for edge in workflow.edges:
            if edge.target == start_id:
                # 有一条边回到 start，这是合法的 retry 循环
                return True

        # 检查是否有条件节点的 retry 边
        for edge in workflow.edges:
            condition = edge.condition or {}
            if condition.get("result") == "retry":
                return True

        # 检查循环信息中是否包含 start
        if "start" in cycle_info.lower():
            return True

        return False

    def _check_connectivity(self, nodes: List[WorkflowNode], edges: List[WorkflowEdge]) -> bool:
        """检查图的连通性"""
        if not nodes:
            return True

        # 找到开始节点
        start_node = None
        for node in nodes:
            if node.node_type == NodeType.START:
                start_node = node.id
                break

        if not start_node:
            return False

        # BFS 检查可达性
        graph = defaultdict(list)
        for edge in edges:
            graph[edge.source].append(edge.target)

        visited = set()
        queue = deque([start_node])

        while queue:
            node_id = queue.popleft()
            if node_id in visited:
                continue
            visited.add(node_id)
            queue.extend(graph[node_id])

        # 检查是否所有节点都可达
        node_ids = {n.id for n in nodes}
        return len(visited) == len(node_ids)

    # ==================== 前驱图执行逻辑 ====================

    def _is_completed_status(self, status: Any) -> bool:
        """兼容枚举和持久化字符串的 completed 状态判断。"""
        value = status.value if hasattr(status, "value") else status
        return value == NodeStatus.COMPLETED.value

    def _is_running_status(self, status: Any) -> bool:
        """兼容枚举和持久化字符串的 running 状态判断。"""
        value = status.value if hasattr(status, "value") else status
        return value == NodeStatus.RUNNING.value

    def _build_predecessor_graph(self, workflow: WorkflowDefinition) -> Dict[str, List[str]]:
        """
        构建前驱图：每个节点映射到其所有前驱节点的列表

        Args:
            workflow: 工作流定义

        Returns:
            Dict[str, List[str]]: 节点ID -> 前驱节点ID列表
        """
        # 获取所有节点 ID
        all_node_ids = {node.id for node in workflow.nodes}
        node_order = {node.id: index for index, node in enumerate(workflow.nodes)}
        logger.info(f"工作流包含 {len(all_node_ids)} 个节点: {all_node_ids}")

        predecessors = {node.id: [] for node in workflow.nodes}

        # 记录边的连接情况
        logger.info(f"工作流包含 {len(workflow.edges)} 条边:")
        valid_edge_count = 0
        for edge in workflow.edges:
            # 只处理源和目标都存在的边
            if edge.source not in all_node_ids:
                logger.warning(f"  警告: 边的源节点 {edge.source} 不在节点列表中，跳过此边")
                continue
            if edge.target not in all_node_ids:
                logger.warning(f"  警告: 边的目标节点 {edge.target} 不在节点列表中，跳过此边")
                continue

            logger.info(f"  边: {edge.source} -> {edge.target}")
            if edge.target in predecessors:
                edge_condition = edge.condition or {}
                if edge_condition.get("result") and node_order.get(edge.target, 0) < node_order.get(edge.source, 0):
                    logger.info(
                        f"  条件回边不加入前驱依赖: {edge.source} -> {edge.target} "
                        f"({edge_condition})"
                    )
                    continue
                predecessors[edge.target].append(edge.source)
                valid_edge_count += 1

        logger.info(f"有效边数量: {valid_edge_count}")

        # 详细日志：输出每个节点的前驱
        logger.info("前驱图构建结果:")
        for node_id, preds in predecessors.items():
            if preds:
                logger.info(f"  节点 {node_id} 的前驱: {preds}")
            else:
                logger.info(f"  节点 {node_id} 没有前驱（起始节点）")

        return predecessors

    def _build_successor_graph(self, workflow: WorkflowDefinition) -> Dict[str, List[str]]:
        """
        构建后继图：每个节点映射到其所有后继节点的列表

        Args:
            workflow: 工作流定义

        Returns:
            Dict[str, List[str]]: 节点ID -> 后继节点ID列表
        """
        all_node_ids = {node.id for node in workflow.nodes}
        successors = {node.id: [] for node in workflow.nodes}

        for edge in workflow.edges:
            # 只处理源和目标都存在的边
            if edge.source in all_node_ids and edge.target in all_node_ids:
                if edge.source in successors:
                    successors[edge.source].append(edge.target)

        return successors

    def _get_ready_nodes(
        self,
        workflow: WorkflowDefinition,
        execution: WorkflowExecution,
        predecessors: Dict[str, List[str]],
        completed_nodes: Set[str],
    ) -> List[str]:
        """
        获取可以执行的节点（所有前驱节点都已完成）

        Args:
            workflow: 工作流定义
            execution: 工作流执行实例
            predecessors: 前驱图
            completed_nodes: 已完成的节点集合

        Returns:
            List[str]: 可以执行的节点ID列表
        """
        ready_nodes = []

        logger.debug(f"查找就绪节点，已完成: {completed_nodes}")

        for node in workflow.nodes:
            # 跳过已完成的节点
            if node.id in completed_nodes:
                logger.debug(f"  节点 {node.id} 已完成，跳过")
                continue

            node_state = execution.node_states.get(node.id)
            if node_state and self._is_running_status(node_state.status):
                logger.debug(f"  节点 {node.id} 状态为 {node_state.status}，跳过")
                continue

            # 检查所有前驱是否都已完成
            node_predecessors = predecessors.get(node.id, [])

            if not node_predecessors:
                # 没有前驱的节点（应该只有开始节点）
                logger.debug(f"  节点 {node.id} 没有前驱，标记为就绪")
                ready_nodes.append(node.id)
            else:
                # 检查前驱是否都完成
                pending_preds = [p for p in node_predecessors if p not in completed_nodes]
                if pending_preds:
                    logger.debug(f"  节点 {node.id} 有未完成的前驱: {pending_preds}")
                else:
                    logger.info(f"  节点 {node.id} 所有前驱已完成，标记为就绪")
                    ready_nodes.append(node.id)

        logger.info(f"就绪节点列表: {ready_nodes} (共 {len(ready_nodes)} 个)")
        return ready_nodes

    def _get_goto_reset_nodes(
        self,
        workflow: WorkflowDefinition,
        source_node_id: str,
        target_node_id: str,
    ) -> Set[str]:
        """获取条件回跳时需要重置的节点集合。"""
        successors: Dict[str, List[str]] = defaultdict(list)
        predecessors: Dict[str, List[str]] = defaultdict(list)
        for edge in workflow.edges:
            successors[edge.source].append(edge.target)
            predecessors[edge.target].append(edge.source)

        reachable_from_target: Set[str] = set()
        queue: deque[str] = deque([target_node_id])
        while queue:
            node_id = queue.popleft()
            if node_id in reachable_from_target:
                continue
            reachable_from_target.add(node_id)
            if node_id == source_node_id:
                continue
            for next_node_id in successors.get(node_id, []):
                queue.append(next_node_id)

        can_reach_source: Set[str] = set()
        queue = deque([source_node_id])
        while queue:
            node_id = queue.popleft()
            if node_id in can_reach_source:
                continue
            can_reach_source.add(node_id)
            for previous_node_id in predecessors.get(node_id, []):
                queue.append(previous_node_id)

        reset_nodes = reachable_from_target & can_reach_source
        return reset_nodes or {target_node_id}

    def _reset_nodes_for_goto(
        self,
        execution: WorkflowExecution,
        completed_nodes: Set[str],
        node_ids: Set[str],
        reason: str,
    ) -> None:
        """重置回跳路径上的节点，确保后续节点会重新执行。"""
        for node_id in node_ids:
            completed_nodes.discard(node_id)
            state = execution.node_states.get(node_id)
            if state:
                state.status = NodeStatus.PENDING
                state.started_at = None
                state.completed_at = None
                state.output_data = {}
                state.error = None
                state.duration_ms = None
        logger.info(f"{reason}，已重置节点: {sorted(node_ids)}")

    def _collect_downstream_nodes(self, workflow: WorkflowDefinition, node_id: str) -> Set[str]:
        """Collect a workflow node and every graph descendant reachable from it."""
        successors = self._build_successor_graph(workflow)
        if node_id not in successors:
            return {node_id}

        downstream: Set[str] = set()
        queue: deque[str] = deque([node_id])
        while queue:
            current_node_id = queue.popleft()
            if current_node_id in downstream:
                continue
            downstream.add(current_node_id)
            for next_node_id in successors.get(current_node_id, []):
                queue.append(next_node_id)
        return downstream

    def _reset_nodes_for_recovery(
        self,
        execution: WorkflowExecution,
        reset_node_ids: Set[str],
        *,
        target_node_id: str,
        reason: str,
    ) -> None:
        """Reset failed/downstream node state while preserving upstream execution context."""
        node_outputs = execution.context.get("node_outputs")
        if isinstance(node_outputs, dict):
            for node_id in reset_node_ids:
                node_outputs.pop(node_id, None)

        latest_output = execution.context.get("latest_node_output")
        if isinstance(latest_output, dict):
            source_node_id = latest_output.get("node_id")
            if source_node_id in reset_node_ids:
                execution.context.pop("latest_node_output", None)

        for node_id in reset_node_ids:
            state = execution.node_states.get(node_id)
            if not state:
                state = NodeExecutionState(node_id=node_id)
                execution.node_states[node_id] = state
            previous_retry_count = state.retry_count or 0
            state.status = NodeStatus.PENDING
            state.started_at = None
            state.completed_at = None
            state.input_data = {}
            state.output_data = {}
            state.output_contract_id = None
            state.output_mode = None
            state.output_schema_name = None
            state.output_schema_version = None
            state.error = None
            state.duration_ms = None
            if node_id == target_node_id:
                state.retry_count = previous_retry_count + 1
        logger.info(f"{reason}，已重置恢复节点: {sorted(reset_node_ids)}")

    async def _merge_predecessor_outputs(
        self,
        node: WorkflowNode,
        execution: WorkflowExecution,
        predecessors: Dict[str, List[str]],
        workflow: WorkflowDefinition,
    ) -> Dict[str, Any]:
        """
        合并所有前驱节点的输出作为当前节点的输入

        Args:
            node: 当前节点
            execution: 工作流执行实例
            predecessors: 前驱图
            workflow: 工作流定义

        Returns:
            Dict[str, Any]: 合并后的输入数据
        """
        merged_context = execution.context.copy()
        state = get_workflow_state(execution)
        node_predecessors = predecessors.get(node.id, [])
        node_outputs = merged_context.setdefault("node_outputs", {})

        for pred_id in node_predecessors:
            pred_state = execution.node_states.get(pred_id)
            if not pred_state or not pred_state.output_data:
                continue

            pred_output = pred_state.output_data
            node_outputs[pred_id] = pred_output
            merged_context["latest_node_output"] = pred_output

            allowed_updates: Dict[str, Any] = {}
            retrieved_updates: Dict[str, Any] = {}
            blocked_updates: Dict[str, Any] = {}
            for key, value in pred_output.items():
                if key in {"fixed_lore_entries", "dynamic_lore_entries", "selected_lore_entries"} or key in RUNTIME_STATE_KEYS:
                    retrieved_updates[key] = value
                    merged_context[key] = value
                    continue
                if is_protected_context_key(key):
                    blocked_updates[key] = {
                        "existing": merged_context.get(key),
                        "attempted": value,
                        "reason": "protected_predecessor_output",
                    }
                    continue
                allowed_updates[key] = value
                merged_context[key] = value

            if retrieved_updates:
                state.merge_runtime_state(retrieved_updates, source=f"predecessor_retrieved_merge:{pred_id}")

            if allowed_updates or retrieved_updates or blocked_updates:
                state.record_state_transition(
                    source="predecessor_merge",
                    node_id=node.id,
                    allowed_updates={**allowed_updates, **retrieved_updates},
                    blocked_updates=blocked_updates,
                )
            logger.info(
                f"合并前驱节点 {pred_id} 输出到节点 {node.id}: "
                f"allowed={list(allowed_updates.keys())}, retrieved={list(retrieved_updates.keys())}, blocked={list(blocked_updates.keys())}"
            )

        return merged_context

    # ==================== 工作流执行 ====================

    async def execute_workflow(
        self,
        workflow_id: str,
        project_id: str,
        initial_context: Dict[str, Any] = None,
        db=None,
        request_id: Optional[str] = None,
        force_new: bool = False,
    ) -> str:
        result = await self.start_workflow_execution(
            workflow_id=workflow_id,
            project_id=project_id,
            initial_context=initial_context,
            db=db,
            request_id=request_id,
            force_new=force_new,
        )
        return result.execution_id

    async def start_workflow_execution(
        self,
        workflow_id: str,
        project_id: str,
        initial_context: Dict[str, Any] = None,
        db=None,
        request_id: Optional[str] = None,
        force_new: bool = False,
    ) -> WorkflowExecutionStartResult:
        """执行工作流

        Args:
            workflow_id: 工作流ID
            project_id: 项目ID
            initial_context: 初始上下文，可选包含 target_chapters 参数
            db: 数据库连接
            request_id: 幂等请求 ID
            force_new: 是否强制创建新执行
        """
        workflow = await self.get_workflow(workflow_id, db)
        if not workflow:
            raise ValueError(f"工作流不存在: {workflow_id}")

        # 验证工作流
        validation = self.validate_workflow(workflow)
        if not validation.valid:
            raise ValueError(f"工作流验证失败: {validation.errors}")

        # 初始化上下文；不要在 request_payload/hash 构建前注入隐式默认 world，保持旧请求幂等语义
        context = dict(initial_context or {})
        explicit_world_id = context.get("world_id")
        request_payload = {
            "workflow_id": workflow_id,
            "project_id": project_id,
            "initial_context": context.copy(),
            "workflow_updated_at": workflow.updated_at.isoformat() if workflow.updated_at else None,
        }
        operation_result = None
        operation = None
        if db:
            operation_service = OperationLifecycleService(db=db, redis=redis_service)
            operation_result = await operation_service.begin_or_replay(
                operation_type="workflow_execute",
                project_id=project_id,
                resource_type="workflow",
                resource_id=workflow_id,
                request_payload=request_payload,
                request_id=request_id,
                force_new=force_new,
            )
            operation = operation_result.operation
            response_payload = operation.get("response_payload") or {}
            existing_execution_id = response_payload.get("execution_id")
            if operation_result.replayed and existing_execution_id:
                return WorkflowExecutionStartResult(
                    execution_id=existing_execution_id,
                    replayed=True,
                    deduplicated=False,
                )
            if operation_result.deduplicated:
                existing_execution_id = existing_execution_id or await self._get_execution_id_by_operation_id(
                    str(operation.get("id")), db
                )
                if existing_execution_id:
                    return WorkflowExecutionStartResult(
                        execution_id=existing_execution_id,
                        replayed=False,
                        deduplicated=True,
                    )

        # 显式 world_id 参与幂等；隐式默认 world 只写入执行上下文和 trace，不改变旧请求 hash
        world_scope: Dict[str, Any] = {}
        if db:
            try:
                world = None
                if explicit_world_id and hasattr(db, "get_world"):
                    world = await db.get_world(str(explicit_world_id))
                    if world and world.get("project_id") and str(world.get("project_id")) != str(project_id):
                        raise ValueError("工作流 world_id 不属于当前项目")
                elif hasattr(db, "get_default_world"):
                    world = await db.get_default_world(project_id)
                if world:
                    context["world_id"] = str(world.get("id"))
                    world_scope = {
                        "world_id": str(world.get("id")),
                        "scope_type": world.get("scope_type"),
                        "parent_world_id": str(world.get("parent_world_id")) if world.get("parent_world_id") else None,
                        "is_explicit": bool(explicit_world_id),
                    }
                    context["world_scope"] = world_scope
                    if hasattr(db, "get_world_ancestor_ids"):
                        ancestor_ids = await db.get_world_ancestor_ids(str(world.get("id")))
                        context["world_hierarchy_path"] = [*ancestor_ids, str(world.get("id"))]
            except Exception as exc:
                if explicit_world_id:
                    raise
                logger.warning("解析默认 workflow world scope 失败: %s", exc)

        # ========== 自动章节序号确定 ==========
        chapter_number = context.get("chapter_num")
        if chapter_number is None and db:
            # 自动获取下一章节序号
            try:
                from app.services.plot_outline_service import get_plot_outline_service
                plot_service = get_plot_outline_service()
                chapter_number = await plot_service.get_next_chapter_number(project_id)
                context["chapter_num"] = chapter_number
                logger.info(f"自动确定章节序号: 第 {chapter_number} 章")
            except Exception as e:
                logger.warning(f"自动获取章节号失败: {e}，使用默认值 1")
                context["chapter_num"] = 1

        # ========== 自动加载章节大纲 ==========
        if db:
            await self._resolve_approved_outline_for_chapter_start(project_id, context)

        try:
            readiness_context = await self.check_chapter_resource_readiness(project_id, context, db)
        except ChapterReadinessBlockedError as exc:
            if operation and db:
                operation_service = OperationLifecycleService(db=db, redis=redis_service)
                await operation_service.fail(
                    operation,
                    str(exc),
                    {"blocked": True, **exc.payload},
                )
            raise
        if readiness_context:
            context["chapter_resource_readiness"] = readiness_context.get("readiness")
            if readiness_context.get("advisory_requirements"):
                context["chapter_resource_readiness_warnings"] = readiness_context["advisory_requirements"]

        trace_service = get_trace_service(db)
        trace_id = str(operation.get("trace_id")) if operation and operation.get("trace_id") else str(uuid.uuid4())
        context["_trace"] = {"trace_id": trace_id, "enabled": bool(settings.trace_enabled)}

        # 创建执行实例
        state_seed = {key: context.get(key) for key in CANONICAL_STATE_KEYS if context.get(key) is not None}
        context.setdefault("workflow_state", {})
        context["workflow_state"]["canonical_state"] = {
            **context["workflow_state"].get("canonical_state", {}),
            **state_seed,
        }
        context.setdefault("node_outputs", {})
        context.setdefault("state_transitions", [])
        context.setdefault("asset_state", context["workflow_state"].setdefault("asset_state", {}))

        # 创建执行实例
        execution = WorkflowExecution(
            workflow_id=workflow_id,
            project_id=project_id,
            status=WorkflowStatus.RUNNING,
            context=context,
            operation_id=str(operation.get("id")) if operation else None,
            request_id=operation.get("request_id") if operation else request_id,
            request_hash=operation.get("request_hash") if operation else None,
            director_session_id=context.get("director_session_id"),
            trace_id=trace_id,
            lease_token=operation.get("lease_token") if operation else uuid.uuid4().hex,
            lease_expires_at=datetime.now() + timedelta(seconds=60),
            last_heartbeat_at=datetime.now(),
        )

        if db:
            await trace_service.start_trace(
                trace_type="workflow",
                root_name=workflow.name,
                project_id=project_id,
                operation_id=execution.operation_id,
                request_id=execution.request_id,
                workflow_id=workflow_id,
                workflow_execution_id=execution.id,
                root_input_summary={
                    "chapter_num": context.get("chapter_num"),
                    "chapter_title": context.get("chapter_title"),
                    "world_id": context.get("world_id"),
                    "world_hierarchy_path": context.get("world_hierarchy_path"),
                    "context_keys": sorted([str(k) for k in context.keys() if k != "_trace"]),
                },
                metadata={
                    "node_count": len(workflow.nodes),
                    "edge_count": len(workflow.edges),
                    "world_id": context.get("world_id"),
                    "scope_type": world_scope.get("scope_type"),
                    "world_hierarchy_path": context.get("world_hierarchy_path"),
                },
                trace_id=trace_id,
            )

        # 初始化节点状态
        for node in workflow.nodes:
            execution.node_states[node.id] = NodeExecutionState(node_id=node.id)

        # 保存到数据库
        if db:
            await self._save_execution_to_db(execution, db)
            if operation:
                operation_service = OperationLifecycleService(db=db, redis=redis_service)
                await operation_service.mark_running(operation, {"execution_id": execution.id, "trace_id": trace_id})

        self._executions[execution.id] = execution

        # 广播开始事件
        await self._broadcast_status(execution.id, "workflow_started", {
            "workflow_id": workflow_id,
            "execution_id": execution.id,
            "chapter_number": context.get("chapter_num"),
            "request_id": execution.request_id,
            "trace_id": execution.trace_id,
            "world_id": context.get("world_id"),
            "director_session_id": execution.director_session_id,
        })

        # 异步执行工作流
        self._start_workflow_task(execution.id, workflow, db)

        logger.info(f"启动工作流执行: {execution.id}, 章节: {context.get('chapter_num')}")
        return WorkflowExecutionStartResult(execution_id=execution.id)

    def _start_workflow_task(self, execution_id: str, workflow: WorkflowDefinition, db=None) -> asyncio.Task:
        """启动并登记 workflow task；若已有活跃 task 则复用。"""
        task = self._running_tasks.get(execution_id)
        if task and not task.done():
            return task
        task = asyncio.create_task(self._run_workflow(execution_id, workflow, db))
        self._running_tasks[execution_id] = task
        return task

    async def _get_execution_id_by_operation_id(self, operation_id: str, db) -> Optional[str]:
        """按 operation_id 获取关联 execution。"""
        if not operation_id:
            return None
        results = await db.execute_query(
            """
            SELECT id FROM workflow_executions
            WHERE operation_id = CAST(:operation_id AS UUID)
            ORDER BY started_at DESC
            LIMIT 1
            """,
            {"operation_id": operation_id},
        )
        return results[0]["id"] if results else None

    async def _mark_operation_terminal(self, execution: WorkflowExecution, db=None) -> None:
        """同步 workflow 终态到 operation_requests。"""
        if not db or not execution.operation_id or not execution.request_id:
            return
        operation = await db.get_operation_request_by_request_id(execution.request_id)
        if not operation:
            return
        operation_service = OperationLifecycleService(db=db, redis=redis_service)
        payload = {"execution_id": execution.id, "status": execution.status.value, "trace_id": execution.trace_id}
        if execution.status == WorkflowStatus.COMPLETED:
            await operation_service.complete(operation, payload)
        elif execution.status == WorkflowStatus.CANCELLED:
            await operation_service.cancel_requested(operation, payload)
        elif execution.status == WorkflowStatus.FAILED:
            await operation_service.fail(operation, execution.error or "workflow failed", payload)

    async def create_runtime_fixture(
        self,
        project_id: str,
        db=None,
        *,
        fixture_type: str = "stale_running",
        label: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create an isolated workflow runtime fixture for local smoke validation.

        This is intentionally scoped to DEBUG mode and marks all created records with a
        cleanup token so runtime smokes can exercise governance flows without reusing or
        mutating long-lived user data.
        """
        if not settings.debug:
            self._raise_operation_error(
                "runtime-fixture",
                "fixture",
                "运行时夹具只能在 DEBUG 模式下创建",
                code="workflow_fixture_disabled",
                http_status=403,
            )
        if not db:
            self._raise_operation_error(
                "runtime-fixture",
                "fixture",
                "创建运行时夹具需要数据库连接",
                code="workflow_fixture_database_required",
                http_status=503,
            )
        normalized_type = (fixture_type or "stale_running").strip().lower()
        allowed_fixture_types = {"stale_running", "missing_agent_failed", "saved_chapter", "quality_gate_revision", "state_handoff_context"}
        if normalized_type not in allowed_fixture_types:
            self._raise_operation_error(
                "runtime-fixture",
                "fixture",
                f"不支持的运行时夹具类型: {fixture_type}",
                code="workflow_fixture_type_not_supported",
                payload={"allowed_fixture_types": sorted(allowed_fixture_types)},
            )

        now = datetime.now()
        cleanup_token = uuid.uuid4().hex
        suffix = uuid.uuid4().hex[:8]
        if normalized_type in {"quality_gate_revision", "state_handoff_context"}:
            is_state_handoff_fixture = normalized_type == "state_handoff_context"
            workflow = WorkflowDefinition(
                id=f"workflow_fixture_{suffix}",
                project_id=project_id,
                name=label or f"Runtime {normalized_type} fixture {suffix}",
                description=(
                    "DEBUG-only isolated runtime fixture for confirmed state handoff smoke tests."
                    if is_state_handoff_fixture
                    else "DEBUG-only isolated runtime fixture for quality-gated Writer revision smoke tests."
                ),
                nodes=[
                    WorkflowNode(id="start", node_type=NodeType.START, label="开始", position={"x": 0, "y": 0}),
                    WorkflowNode(
                        id="writer",
                        node_type=NodeType.AGENT,
                        agent_type="writer",
                        label="Writer 状态交接夹具" if is_state_handoff_fixture else "Writer 质量门夹具",
                        config={"quality_gate_enabled": True},
                        position={"x": 220, "y": 0},
                    ),
                    WorkflowNode(
                        id="evaluator",
                        node_type=NodeType.AGENT,
                        agent_type="evaluator",
                        label="Evaluator 状态交接夹具" if is_state_handoff_fixture else "Evaluator 质量门夹具",
                        position={"x": 440, "y": 0},
                    ),
                    WorkflowNode(id="gate", node_type=NodeType.CONDITION, label="质量门", position={"x": 660, "y": 0}),
                    WorkflowNode(id="end", node_type=NodeType.END, label="结束", position={"x": 880, "y": 0}),
                ],
                edges=[
                    WorkflowEdge(id="edge_start_writer", source="start", target="writer"),
                    WorkflowEdge(id="edge_writer_evaluator", source="writer", target="evaluator"),
                    WorkflowEdge(id="edge_evaluator_gate", source="evaluator", target="gate"),
                    WorkflowEdge(id="edge_gate_end", source="gate", target="end", condition={"result": "pass"}),
                    WorkflowEdge(id="edge_gate_retry", source="gate", target="writer", condition={"result": "retry"}),
                ],
                variables={"runtime_fixture": True, "fixture_type": normalized_type, "cleanup_token": cleanup_token},
                is_template=False,
                created_at=now,
                updated_at=now,
            )
        else:
            workflow = WorkflowDefinition(
                id=f"workflow_fixture_{suffix}",
                project_id=project_id,
                name=label or f"Runtime {normalized_type} fixture {suffix}",
                description="DEBUG-only isolated runtime fixture for workflow governance smoke tests.",
                nodes=[
                    WorkflowNode(id="start", node_type=NodeType.START, label="开始", position={"x": 0, "y": 0}),
                    WorkflowNode(
                        id="fixture_agent",
                        node_type=NodeType.AGENT,
                        agent_type=(
                            "smoke_contract_failure"
                            if normalized_type == "missing_agent_failed"
                            else "writer"
                            if normalized_type == "saved_chapter"
                            else "plot_outline"
                        ),
                        label="Writer 夹具" if normalized_type == "saved_chapter" else "夹具 Agent",
                        config={"scenario": "runtime_fixture"},
                        position={"x": 220, "y": 0},
                    ),
                    WorkflowNode(id="end", node_type=NodeType.END, label="结束", position={"x": 440, "y": 0}),
                ],
                edges=[
                    WorkflowEdge(id="edge_start_agent", source="start", target="fixture_agent"),
                    WorkflowEdge(id="edge_agent_end", source="fixture_agent", target="end"),
                ],
                variables={"runtime_fixture": True, "fixture_type": normalized_type, "cleanup_token": cleanup_token},
                is_template=False,
                created_at=now,
                updated_at=now,
            )
        await self._save_workflow_to_db(workflow, db)
        self._workflows[workflow.id] = workflow

        if normalized_type == "stale_running":
            execution = WorkflowExecution(
                id=f"exec_fixture_{suffix}",
                workflow_id=workflow.id,
                project_id=project_id,
                status=WorkflowStatus.RUNNING,
                current_node="fixture_agent",
                node_states={
                    "start": NodeExecutionState(node_id="start", status=NodeStatus.COMPLETED, started_at=now - timedelta(seconds=80), completed_at=now - timedelta(seconds=75)),
                    "fixture_agent": NodeExecutionState(node_id="fixture_agent", status=NodeStatus.RUNNING, started_at=now - timedelta(seconds=70)),
                    "end": NodeExecutionState(node_id="end", status=NodeStatus.PENDING),
                },
                context={
                    "runtime_fixture": True,
                    "fixture_type": normalized_type,
                    "cleanup_token": cleanup_token,
                    "created_by": "workflow_runtime_fixture",
                },
                started_at=now - timedelta(seconds=80),
                lease_token=f"fixture_{cleanup_token}",
                lease_expires_at=now - timedelta(seconds=10),
                last_heartbeat_at=now - timedelta(seconds=80),
                resume_cursor={"runtime_fixture": True, "cleanup_token": cleanup_token},
            )
        elif normalized_type == "missing_agent_failed":
            execution = WorkflowExecution(
                id=f"exec_fixture_{suffix}",
                workflow_id=workflow.id,
                project_id=project_id,
                status=WorkflowStatus.FAILED,
                current_node="fixture_agent",
                node_states={
                    "start": NodeExecutionState(node_id="start", status=NodeStatus.COMPLETED, started_at=now - timedelta(seconds=20), completed_at=now - timedelta(seconds=18)),
                    "fixture_agent": NodeExecutionState(
                        node_id="fixture_agent",
                        status=NodeStatus.FAILED,
                        started_at=now - timedelta(seconds=18),
                        completed_at=now - timedelta(seconds=16),
                        error="无法获取 Agent: smoke_contract_failure",
                    ),
                    "end": NodeExecutionState(node_id="end", status=NodeStatus.PENDING),
                },
                context={
                    "runtime_fixture": True,
                    "fixture_type": normalized_type,
                    "cleanup_token": cleanup_token,
                    "created_by": "workflow_runtime_fixture",
                },
                started_at=now - timedelta(seconds=20),
                completed_at=now - timedelta(seconds=16),
                error="无法获取 Agent: smoke_contract_failure",
                resume_cursor={"runtime_fixture": True, "cleanup_token": cleanup_token},
            )
        elif normalized_type in {"quality_gate_revision", "state_handoff_context"}:
            is_state_handoff_fixture = normalized_type == "state_handoff_context"
            chapter_outline_id = f"outline_fixture_{suffix}"
            prior_chapter_ids: List[str] = []
            excluded_draft_chapter_ids: List[str] = []
            seeded_state_change_ids: List[str] = []
            if is_state_handoff_fixture:
                prior_chapter_one_id = str(uuid.uuid4())
                prior_chapter_two_id = str(uuid.uuid4())
                draft_chapter_id = str(uuid.uuid4())
                prior_chapter_ids = [prior_chapter_one_id, prior_chapter_two_id]
                excluded_draft_chapter_ids = [draft_chapter_id]
                for chapter_data in [
                    {
                        "id": prior_chapter_one_id,
                        "project_id": project_id,
                        "title": f"状态交接前文章节一 {suffix}",
                        "chapter_number": 1,
                        "chapter_num": 1,
                        "summary": "前文一确认主角离开旧城。",
                        "content": "状态交接夹具前文一，用于证明下一章只读取已保存前文摘要。",
                        "word_count": 24,
                        "status": "saved",
                        "content_checksum": f"fixture-prior-one-{suffix}",
                        "events": [],
                        "hooks_planted": [],
                        "hooks_resolved": [],
                        "main_plot_progress": {},
                        "reader_scores": {},
                        "created_at": now - timedelta(days=2),
                        "updated_at": now - timedelta(days=2),
                        "completed_at": now - timedelta(days=2),
                    },
                    {
                        "id": prior_chapter_two_id,
                        "project_id": project_id,
                        "title": f"状态交接前文章节二 {suffix}",
                        "chapter_number": 2,
                        "chapter_num": 2,
                        "summary": "前文二确认主角获得星砂印记。",
                        "content": "状态交接夹具前文二，用于证明下一章读取多个已保存前文章节。",
                        "word_count": 26,
                        "status": "saved",
                        "content_checksum": f"fixture-prior-two-{suffix}",
                        "events": [],
                        "hooks_planted": [],
                        "hooks_resolved": [],
                        "main_plot_progress": {},
                        "reader_scores": {},
                        "created_at": now - timedelta(days=1),
                        "updated_at": now - timedelta(days=1),
                        "completed_at": now - timedelta(days=1),
                    },
                    {
                        "id": draft_chapter_id,
                        "project_id": project_id,
                        "title": f"状态交接草稿章节 {suffix}",
                        "chapter_number": 2,
                        "chapter_num": 2,
                        "summary": "这个草稿必须被 confirmed_prior_state_packet 排除。",
                        "content": "不应进入前文状态包的草稿内容。",
                        "word_count": 12,
                        "status": "draft",
                        "content_checksum": f"fixture-draft-{suffix}",
                        "events": [],
                        "hooks_planted": [],
                        "hooks_resolved": [],
                        "main_plot_progress": {},
                        "reader_scores": {},
                        "created_at": now - timedelta(hours=12),
                        "updated_at": now - timedelta(hours=12),
                        "completed_at": None,
                    },
                ]:
                    await db.save_chapter(chapter_data)

                from app.services.narrative_state_change_service import NarrativeStateChangeService

                state_service = NarrativeStateChangeService(db)
                first_applied_change = await state_service.create_change({
                    "project_id": project_id,
                    "entity_type": "character",
                    "entity_id": "00000000-0000-0000-0000-000000000101",
                    "entity_name": "林砚",
                    "change_type": "status_change",
                    "status": "applied",
                    "confirmation_required": False,
                    "title": f"林砚受伤 {suffix}",
                    "summary": "林砚在第一段前文中受伤，这是后续章节必须承接的已应用状态。",
                    "chapter_id": prior_chapter_one_id,
                    "after_state": {"status": "injured", "location": "旧城", "traits": ["wounded", "steady"], "notes": {"origin": "first-pass"}},
                    "metadata": {"source": "runtime_state_handoff_fixture", "chapter_num": 1, "cleanup_token": cleanup_token},
                    "created_at": now - timedelta(days=2, minutes=-5),
                    "applied_at": now - timedelta(days=2, minutes=-4),
                })
                latest_applied_change = await state_service.create_change({
                    "project_id": project_id,
                    "entity_type": "character",
                    "entity_id": "00000000-0000-0000-0000-000000000101",
                    "entity_name": "林砚",
                    "change_type": "location_change",
                    "status": "applied",
                    "confirmation_required": False,
                    "title": f"林砚抵达星门 {suffix}",
                    "summary": "林砚在第二段前文中带伤抵达星门，这是下一章必须使用的最新角色状态。",
                    "chapter_id": prior_chapter_two_id,
                    "after_state": {"status": "recovering", "location": "星门", "traits": ["steady", "focused"], "notes": {"phase": "stable", "pace": "measured"}},
                    "metadata": {"source": "runtime_state_handoff_fixture", "chapter_num": 2, "cleanup_token": cleanup_token},
                    "created_at": now - timedelta(days=1, minutes=-5),
                    "applied_at": now - timedelta(days=1, minutes=-4),
                })
                confirmed_plot_change = await state_service.create_change({
                    "project_id": project_id,
                    "entity_type": "plot",
                    "entity_id": "fixture-plot-star-sand-mark",
                    "entity_name": "星砂印记",
                    "change_type": "custom",
                    "status": "confirmed",
                    "confirmation_required": True,
                    "title": f"星砂印记已确认 {suffix}",
                    "summary": "主角已获得星砂印记，这是下一章必须尊重的已确认剧情状态。",
                    "chapter_id": prior_chapter_two_id,
                    "after_state": {"obtained": True},
                    "metadata": {"source": "runtime_state_handoff_fixture", "chapter_num": 2, "cleanup_token": cleanup_token},
                    "created_at": now - timedelta(days=1, minutes=-3),
                    "confirmed_at": now - timedelta(days=1, minutes=-2),
                })
                proposed_change = await state_service.create_change({
                    "project_id": project_id,
                    "entity_type": "world",
                    "change_type": "world_state_change",
                    "status": "proposed",
                    "confirmation_required": True,
                    "title": f"星门即将失稳 {suffix}",
                    "summary": "星门失稳仍是待确认提示，下一章不得当作正史。",
                    "chapter_id": prior_chapter_two_id,
                    "metadata": {"source": "runtime_state_handoff_fixture", "chapter_num": 2, "cleanup_token": cleanup_token},
                })
                rejected_change = await state_service.create_change({
                    "project_id": project_id,
                    "entity_type": "plot",
                    "entity_id": "fixture-plot-discarded",
                    "entity_name": "废弃设定",
                    "change_type": "custom",
                    "status": "rejected",
                    "confirmation_required": True,
                    "title": f"废弃设定 {suffix}",
                    "summary": "废弃设定不应进入状态包。",
                    "chapter_id": prior_chapter_two_id,
                    "metadata": {"source": "runtime_state_handoff_fixture", "chapter_num": 2, "cleanup_token": cleanup_token},
                })
                seeded_state_change_ids = [
                    first_applied_change.get("id"),
                    latest_applied_change.get("id"),
                    confirmed_plot_change.get("id"),
                    proposed_change.get("id"),
                    rejected_change.get("id"),
                ]

            execution = WorkflowExecution(
                id=f"exec_fixture_{suffix}",
                workflow_id=workflow.id,
                project_id=project_id,
                status=WorkflowStatus.COMPLETED,
                current_node="end",
                node_states={node.id: NodeExecutionState(node_id=node.id, status=NodeStatus.PENDING) for node in workflow.nodes},
                context={
                    "runtime_fixture": True,
                    "fixture_type": normalized_type,
                    "cleanup_token": cleanup_token,
                    "created_by": "workflow_runtime_fixture",
                    "director_session_id": label or f"director-quality-gate-fixture-{suffix}",
                    "chapter_num": 3 if is_state_handoff_fixture else 1,
                    "chapter_title": f"状态交接下一章夹具 {suffix}" if is_state_handoff_fixture else f"质量门修订夹具 {suffix}",
                    "chapter_outline_id": chapter_outline_id,
                    "target_word_count": 5,
                    "fixture_prior_chapter_ids": prior_chapter_ids,
                    "fixture_excluded_draft_chapter_ids": excluded_draft_chapter_ids,
                    "fixture_seeded_state_change_ids": [item for item in seeded_state_change_ids if item],
                },
                director_session_id=label or f"director-quality-gate-fixture-{suffix}",
                started_at=now - timedelta(seconds=24),
                completed_at=now,
                resume_cursor={"runtime_fixture": True, "cleanup_token": cleanup_token},
            )
            writer_node = next(item for item in workflow.nodes if item.id == "writer")
            evaluator_node = next(item for item in workflow.nodes if item.id == "evaluator")
            gate_node = next(item for item in workflow.nodes if item.id == "gate")
            end_node = next(item for item in workflow.nodes if item.id == "end")
            execution.node_states["start"] = NodeExecutionState(node_id="start", status=NodeStatus.COMPLETED, started_at=now - timedelta(seconds=24), completed_at=now - timedelta(seconds=23))
            await self._save_execution_to_db(execution, db)
            if is_state_handoff_fixture:
                writer_context = await self._load_agent_context("writer", execution, db)
                evaluator_context = await self._load_agent_context("evaluator", execution, db)
                execution.context["fixture_writer_confirmed_prior_state_packet"] = writer_context.get("confirmed_prior_state_packet")
                execution.context["fixture_writer_confirmed_prior_state_packet_provenance"] = writer_context.get("confirmed_prior_state_packet_provenance")
                execution.context["fixture_evaluator_confirmed_prior_state_packet"] = evaluator_context.get("confirmed_prior_state_packet")
                execution.context["fixture_evaluator_confirmed_prior_state_packet_provenance"] = evaluator_context.get("confirmed_prior_state_packet_provenance")

            first_writer_output = {
                "chapter_content": "质量门夹具第一版正文，故意保留动机断裂以触发修订。",
                "word_count": 24,
                "hooks_embedded": [],
                "future_setup": [],
                "style_check": {"passed": True},
                "metadata": {"runtime_fixture": True, "attempt": 1},
            }
            await self._stage_writer_draft(
                execution,
                writer_node,
                first_writer_output,
                db,
                contract_metadata={
                    "output_contract_id": "writer.workflow_output",
                    "output_schema_name": "writer.workflow_output",
                    "output_schema_version": "1.0.0",
                },
                prompt_trace={"prompt_ids": ["runtime_fixture_writer"], "template_scenario": "runtime_fixture"},
            )
            execution.context.setdefault("node_outputs", {})["writer"] = self._make_json_safe(first_writer_output)
            execution.context.setdefault("writer_retry_contexts", [])
            execution.node_states["writer"] = NodeExecutionState(node_id="writer", status=NodeStatus.COMPLETED, started_at=now - timedelta(seconds=23), completed_at=now - timedelta(seconds=22), output_data=self._make_json_safe(first_writer_output))

            first_feedback = {
                "passed": False,
                "score": 4,
                "issues": ["主角动机断裂"],
                "suggestions": ["重写动机承接并强化选择代价"],
                "summary": "第一版未通过质量门。",
                "word_count_check": {"passed": True, "message": "字数满足夹具要求"},
            }
            execution.context["evaluation_passed"] = False
            execution.context["evaluation_feedback"] = first_feedback
            await self._record_quality_gate_result(execution, evaluator_node, first_feedback, db)
            execution.node_states["evaluator"] = NodeExecutionState(node_id="evaluator", status=NodeStatus.COMPLETED, started_at=now - timedelta(seconds=22), completed_at=now - timedelta(seconds=21), output_data=self._make_json_safe(first_feedback))
            await self._execute_condition_node(gate_node, execution, db)
            execution.context["writer_retry_contexts"].append({
                "is_retry": execution.context.get("is_retry"),
                "task_type": "rewrite_by_review",
                "agent_scenario": "rewrite_by_review",
                "has_evaluation_feedback": bool(execution.context.get("evaluation_feedback")),
                "retry_message": execution.context.get("retry_message"),
                "draft_attempt_before_retry": execution.context.get("chapter_draft_attempt"),
            })

            second_writer_output = {
                "chapter_content": "质量门夹具第二版正文，补足动机承接，明确选择代价，并保留后续伏笔。",
                "word_count": 32,
                "hooks_embedded": [],
                "future_setup": [],
                "style_check": {"passed": True},
                "state_changes": [
                    {
                        "entity_type": "plot",
                        "change_type": "custom",
                        "title": "质量门夹具后续伏笔",
                        "summary": "第二版确认选择代价，并保留后续伏笔作为待确认剧情状态。",
                    }
                ],
                "metadata": {"runtime_fixture": True, "attempt": 2},
            }
            await self._stage_writer_draft(
                execution,
                writer_node,
                second_writer_output,
                db,
                contract_metadata={
                    "output_contract_id": "writer.workflow_output",
                    "output_schema_name": "writer.workflow_output",
                    "output_schema_version": "1.0.0",
                },
                prompt_trace={"prompt_ids": ["runtime_fixture_writer"], "template_scenario": "rewrite_by_review"},
            )
            execution.context["node_outputs"]["writer"] = self._make_json_safe(second_writer_output)
            execution.node_states["writer"] = NodeExecutionState(node_id="writer", status=NodeStatus.COMPLETED, started_at=now - timedelta(seconds=20), completed_at=now - timedelta(seconds=19), output_data=self._make_json_safe(second_writer_output))

            second_feedback = {
                "passed": True,
                "score": 8.6,
                "issues": [],
                "suggestions": ["可以保存，后续继续回收伏笔"],
                "summary": "第二版通过质量门。",
                "word_count_check": {"passed": True, "message": "字数满足夹具要求"},
            }
            execution.context["evaluation_passed"] = True
            execution.context["evaluation_feedback"] = second_feedback
            await self._record_quality_gate_result(execution, evaluator_node, second_feedback, db)
            execution.node_states["evaluator"] = NodeExecutionState(node_id="evaluator", status=NodeStatus.COMPLETED, started_at=now - timedelta(seconds=19), completed_at=now - timedelta(seconds=18), output_data=self._make_json_safe(second_feedback))
            await self._execute_condition_node(gate_node, execution, db)
            execution.context["retry_count"] = 0
            execution.context["is_retry"] = False
            execution.node_states["gate"] = NodeExecutionState(node_id="gate", status=NodeStatus.COMPLETED, started_at=now - timedelta(seconds=18), completed_at=now - timedelta(seconds=17), output_data={"quality_passed": True, "chapter_finalized": True})
            execution.node_states["end"] = NodeExecutionState(node_id=end_node.id, status=NodeStatus.COMPLETED, started_at=now - timedelta(seconds=1), completed_at=now)
            execution.context["runtime_fixture_quality_gate_complete"] = True
            execution.context["fixture_expected_final_content_marker"] = "质量门夹具第二版正文"
        else:
            chapter_outline_id = f"outline_fixture_{suffix}"
            execution = WorkflowExecution(
                id=f"exec_fixture_{suffix}",
                workflow_id=workflow.id,
                project_id=project_id,
                status=WorkflowStatus.COMPLETED,
                current_node="end",
                node_states={
                    "start": NodeExecutionState(node_id="start", status=NodeStatus.COMPLETED, started_at=now - timedelta(seconds=24), completed_at=now - timedelta(seconds=23)),
                    "fixture_agent": NodeExecutionState(node_id="fixture_agent", status=NodeStatus.COMPLETED, started_at=now - timedelta(seconds=22), completed_at=now - timedelta(seconds=2)),
                    "end": NodeExecutionState(node_id="end", status=NodeStatus.COMPLETED, started_at=now - timedelta(seconds=1), completed_at=now),
                },
                context={
                    "runtime_fixture": True,
                    "fixture_type": normalized_type,
                    "cleanup_token": cleanup_token,
                    "created_by": "workflow_runtime_fixture",
                    "director_session_id": label or f"director-fixture-{suffix}",
                    "chapter_num": 1,
                    "chapter_title": f"运行时保存交接夹具 {suffix}",
                    "chapter_outline_id": chapter_outline_id,
                    "target_word_count": 800,
                },
                director_session_id=label or f"director-fixture-{suffix}",
                started_at=now - timedelta(seconds=24),
                completed_at=now,
                resume_cursor={"runtime_fixture": True, "cleanup_token": cleanup_token},
            )
            writer_fixture_node = workflow.nodes[1]
            execution.context.setdefault("node_runtime_metadata", {})[writer_fixture_node.id] = {
                "source_node_id": writer_fixture_node.id,
                "source_node_label": writer_fixture_node.label,
                "source_agent_type": writer_fixture_node.agent_type,
                "resolved_agent_type": "writer",
                "resolved_scenario": "runtime_fixture",
                "source_trace_id": execution.trace_id,
                "source_node_input_keys": ["chapter_outline_id", "chapter_title", "target_word_count"],
                "output_contract_id": "writer.workflow_output",
                "output_schema_name": "writer.workflow_output",
                "output_schema_version": "1.0.0",
            }
            await self._save_execution_to_db(execution, db)
            await self._save_chapter_from_writer(
                execution,
                {
                    "chapter_content": "这是一段用于 Director 保存章节交接验证的确定性正文。它验证 Writer 保存、文件系统持久化、SSE 事件元数据和内容页深链选择，而不依赖真实 LLM 输出。",
                    "word_count": 62,
                    "metadata": {"runtime_fixture": True},
                },
                db,
                source_node=writer_fixture_node,
                contract_metadata={
                    "output_contract_id": "writer.workflow_output",
                    "output_schema_name": "writer.workflow_output",
                    "output_schema_version": "1.0.0",
                },
                prompt_trace={"prompt_ids": ["runtime_fixture_writer"], "template_scenario": "runtime_fixture"},
            )
            execution.context["chapter_saved_payload"]["runtime_fixture"] = True

        await self._save_execution_to_db(execution, db)
        self._executions[execution.id] = execution
        await self._broadcast_status(execution.id, "workflow_runtime_fixture_created", self._build_execution_event_payload(
            execution,
            fixture_type=normalized_type,
            cleanup_token=cleanup_token,
        ))
        if hasattr(db, "append_workflow_execution_event"):
            await db.append_workflow_execution_event(execution.id, "workflow_runtime_fixture_created", self._build_execution_event_payload(
                execution,
                fixture_type=normalized_type,
            ))
        return self._serialize_for_json({
            "success": True,
            "fixture_type": normalized_type,
            "cleanup_token": cleanup_token,
            "workflow": workflow,
            "execution": execution,
            "inspection": self.inspect_execution_staleness(execution),
        })

    async def cleanup_runtime_fixture(
        self,
        execution_id: str,
        workflow_id: str,
        cleanup_token: str,
        db=None,
    ) -> Dict[str, Any]:
        """Delete only records created by create_runtime_fixture and guarded by token."""
        if not settings.debug:
            self._raise_operation_error(execution_id, "fixture_cleanup", "运行时夹具只能在 DEBUG 模式下清理", code="workflow_fixture_disabled", http_status=403)
        if not db:
            self._raise_operation_error(execution_id, "fixture_cleanup", "清理运行时夹具需要数据库连接", code="workflow_fixture_database_required", http_status=503)
        execution = await self._get_or_load_execution(execution_id, db)
        workflow = await self.get_workflow(workflow_id, db)
        execution_context = execution.context if execution else {}
        workflow_variables = workflow.variables if workflow else {}
        if not execution or not workflow:
            self._raise_operation_error(execution_id, "fixture_cleanup", "运行时夹具不存在", code="workflow_fixture_not_found", http_status=404)
        if not execution_context.get("runtime_fixture") or not workflow_variables.get("runtime_fixture"):
            self._raise_operation_error(execution_id, "fixture_cleanup", "拒绝清理非夹具数据", code="workflow_fixture_guard_failed")
        if execution_context.get("cleanup_token") != cleanup_token or workflow_variables.get("cleanup_token") != cleanup_token:
            self._raise_operation_error(execution_id, "fixture_cleanup", "运行时夹具清理令牌不匹配", code="workflow_fixture_token_mismatch")

        fixture_chapter_id = execution_context.get("chapter_id")
        if execution_context.get("fixture_type") in {"saved_chapter", "quality_gate_revision", "state_handoff_context"} and fixture_chapter_id:
            try:
                from app.services.chapter_document_storage import chapter_document_storage
                chapter_document_storage.delete_chapter_file(execution_context.get("chapter_content_path"))
            except FileNotFoundError:
                pass
            except Exception as exc:
                logger.warning("清理保存章节夹具文件失败: %s", exc)
            await db.execute_write("DELETE FROM chapters WHERE id = CAST(:id AS UUID)", {"id": fixture_chapter_id})

        for state_change_id in execution_context.get("fixture_seeded_state_change_ids") or []:
            if state_change_id:
                await db.execute_write("DELETE FROM narrative_state_changes WHERE id = CAST(:id AS UUID)", {"id": state_change_id})
        for prior_chapter_id in execution_context.get("fixture_prior_chapter_ids") or []:
            if prior_chapter_id:
                await db.execute_write("DELETE FROM chapters WHERE id = CAST(:id AS UUID)", {"id": prior_chapter_id})
        for draft_chapter_id in execution_context.get("fixture_excluded_draft_chapter_ids") or []:
            if draft_chapter_id:
                await db.execute_write("DELETE FROM chapters WHERE id = CAST(:id AS UUID)", {"id": draft_chapter_id})

        if execution_id in self._executions:
            del self._executions[execution_id]
        if workflow_id in self._workflows:
            del self._workflows[workflow_id]
        await db.execute_write("DELETE FROM workflow_executions WHERE id = :id", {"id": execution_id})
        await self._delete_workflow_from_db(workflow_id, db)
        return {"success": True, "deleted": {"execution_id": execution_id, "workflow_id": workflow_id}}

    def _build_execution_event_payload(self, execution: WorkflowExecution, **extra: Any) -> Dict[str, Any]:
        """Build a compact JSON-safe execution event payload for UI/state reconciliation."""
        payload = {
            "execution_id": execution.id,
            "workflow_id": execution.workflow_id,
            "project_id": execution.project_id,
            "status": execution.status.value,
            "current_node": execution.current_node,
            "trace_id": execution.trace_id,
            "operation_id": execution.operation_id,
            "request_id": execution.request_id,
            "cancel_requested": execution.cancel_requested,
            "error": execution.error,
        }
        payload.update(extra)
        return self._serialize_for_json(payload)

    def _build_node_failure_event_payload(
        self,
        execution: WorkflowExecution,
        node: WorkflowNode,
        node_state: NodeExecutionState,
        *,
        node_type: Optional[NodeType] = None,
        phase: str = "execute",
    ) -> Dict[str, Any]:
        """Build structured node failure details while preserving string error fields."""
        actual_node_type = node_type or node.node_type
        payload = self._build_execution_event_payload(
            execution,
            node_id=node.id,
            node_type=actual_node_type.value,
            label=node.label,
            agent_type=node.agent_type,
            phase=phase,
            status=node_state.status.value,
            error=node_state.error,
            retry_count=node_state.retry_count,
            duration_ms=node_state.duration_ms,
            started_at=node_state.started_at,
            completed_at=node_state.completed_at,
        )
        return payload

    def _build_workflow_failure_event_payload(self, execution: WorkflowExecution) -> Dict[str, Any]:
        """Build compact workflow failure details for frontend recovery panels and SSE replay."""
        failed_nodes = [
            {
                "node_id": state.node_id,
                "status": state.status.value,
                "error": state.error,
                "retry_count": state.retry_count,
                "duration_ms": state.duration_ms,
            }
            for state in execution.node_states.values()
            if state.status == NodeStatus.FAILED
        ]
        first_failed = failed_nodes[0] if failed_nodes else None
        return self._build_execution_event_payload(
            execution,
            failed_node_id=first_failed.get("node_id") if first_failed else None,
            failed_node_error=first_failed.get("error") if first_failed else execution.error,
            failed_nodes=failed_nodes,
            completed_at=execution.completed_at,
            total_duration_ms=execution.total_duration_ms,
        )

    def _operation_capability(
        self,
        *,
        allowed: bool,
        label: str,
        reason: Optional[str] = None,
        severity: str = "info",
        next_status: Optional[str] = None,
    ) -> Dict[str, Any]:
        return {
            "allowed": allowed,
            "label": label,
            "reason": reason,
            "severity": severity,
            "next_status": next_status,
        }

    def build_execution_operation_summary(self, execution: WorkflowExecution) -> Dict[str, Any]:
        """Build backend-authoritative operation capabilities and lifecycle summary for consoles."""
        stale_inspection = self.inspect_execution_staleness(execution)
        active_task = bool(stale_inspection["active_task"])
        status = execution.status.value if hasattr(execution.status, "value") else str(execution.status)
        lease_expired = bool(stale_inspection["lease"]["expired"])
        lease_seconds_remaining = stale_inspection["lease"].get("seconds_remaining")

        failed_nodes = [
            {
                "node_id": node_id,
                "error": state.error,
                "retry_count": state.retry_count,
                "completed_at": state.completed_at,
            }
            for node_id, state in execution.node_states.items()
            if state.status == NodeStatus.FAILED
        ]
        first_failed = failed_nodes[0] if failed_nodes else None
        node_status_counts: Dict[str, int] = {}
        for state in execution.node_states.values():
            state_value = state.status.value if hasattr(state.status, "value") else str(state.status)
            node_status_counts[state_value] = node_status_counts.get(state_value, 0) + 1

        recovery_history = execution.context.get("recovery_history") if isinstance(execution.context, dict) else None
        if not isinstance(recovery_history, list):
            recovery_history = []
        remediation_history = execution.context.get("remediation_history") if isinstance(execution.context, dict) else None
        if not isinstance(remediation_history, list):
            remediation_history = []
        stale_history = execution.context.get("stale_execution_history") if isinstance(execution.context, dict) else None
        if not isinstance(stale_history, list):
            stale_history = []

        can_pause = status == WorkflowStatus.RUNNING.value and not lease_expired
        can_resume = status == WorkflowStatus.PAUSED.value and not active_task
        can_cancel = status in {WorkflowStatus.PENDING.value, WorkflowStatus.RUNNING.value, WorkflowStatus.PAUSED.value}
        can_recover = status == WorkflowStatus.FAILED.value and not active_task
        can_remediate = status == WorkflowStatus.FAILED.value and not active_task and bool(first_failed)

        capabilities = {
            "pause": self._operation_capability(
                allowed=can_pause,
                label="暂停",
                reason=None if can_pause else ("租约已过期，刷新状态后可从失败节点恢复" if lease_expired else "仅运行中的执行可暂停"),
                next_status=WorkflowStatus.PAUSED.value,
            ),
            "resume": self._operation_capability(
                allowed=can_resume,
                label="恢复",
                reason=None if can_resume else ("已有活跃运行任务，不能重复恢复" if active_task else "仅暂停中的执行可恢复"),
                next_status=WorkflowStatus.RUNNING.value,
            ),
            "cancel": self._operation_capability(
                allowed=can_cancel,
                label="取消",
                reason=None if can_cancel else "已完成、失败或已取消的执行不能取消",
                severity="warning",
                next_status=WorkflowStatus.CANCELLED.value,
            ),
            "recover": self._operation_capability(
                allowed=can_recover,
                label="从失败节点重试",
                reason=None if can_recover else ("已有活跃运行任务，不能恢复" if active_task else "仅失败状态可恢复"),
                severity="warning",
                next_status=WorkflowStatus.RUNNING.value,
            ),
            "remediate": self._operation_capability(
                allowed=can_remediate,
                label="修复并恢复",
                reason=None if can_remediate else ("没有可修复的失败节点" if status == WorkflowStatus.FAILED.value else "仅失败状态可修复"),
                severity="warning",
                next_status=WorkflowStatus.RUNNING.value,
            ),
        }

        attention: List[Dict[str, Any]] = []
        if lease_expired:
            attention.append({"type": "stale_lease", "severity": "blocking", "message": "运行租约已过期，执行状态需要刷新/恢复。"})
        if active_task and status != WorkflowStatus.RUNNING.value:
            attention.append({"type": "active_task_conflict", "severity": "blocking", "message": "执行存在活跃任务但状态不是 running，操作被保护。"})
        if first_failed:
            attention.append({"type": "failed_node", "severity": "blocking", "message": f"失败节点：{first_failed.get('node_id')}"})
        if stale_history:
            attention.append({"type": "stale_history", "severity": "warning", "message": f"曾检测到 {len(stale_history)} 次陈旧执行。"})

        return self._serialize_for_json({
            "execution_id": execution.id,
            "workflow_id": execution.workflow_id,
            "project_id": execution.project_id,
            "status": status,
            "current_node": execution.current_node,
            "active_task": active_task,
            "terminal": status in {WorkflowStatus.COMPLETED.value, WorkflowStatus.FAILED.value, WorkflowStatus.CANCELLED.value},
            "capabilities": capabilities,
            "node_summary": {
                "total": len(execution.node_states),
                "counts": node_status_counts,
                "failed_node_id": first_failed.get("node_id") if first_failed else None,
                "failed_node_error": first_failed.get("error") if first_failed else execution.error,
                "failed_nodes": failed_nodes,
            },
            "lease": {
                **stale_inspection["lease"],
                "cancel_requested": execution.cancel_requested,
            },
            "stale_inspection": stale_inspection,
            "recovery": {
                "count": len(recovery_history),
                "latest": recovery_history[-1] if recovery_history else None,
                "resume_cursor": execution.resume_cursor,
            },
            "remediation": {
                "count": len(remediation_history),
                "latest": remediation_history[-1] if remediation_history else None,
            },
            "stale": {
                "count": len(stale_history),
                "latest": stale_history[-1] if stale_history else None,
            },
            "attention": attention,
        })

    async def _run_workflow(
        self,
        execution_id: str,
        workflow: WorkflowDefinition,
        db=None,
    ):
        """
        运行工作流（基于前驱图的执行模式）

        核心逻辑：
        1. 构建前驱图，每个节点知道它的所有前驱节点
        2. 节点执行前检查所有前驱是否完成
        3. 合并所有前驱节点的输出作为当前节点的输入
        4. 支持并行执行多个就绪节点
        """
        execution = self._executions.get(execution_id)
        if not execution:
            return

        try:
            # ========== 构建前驱图和后继图 ==========
            predecessors = self._build_predecessor_graph(workflow)
            successors = self._build_successor_graph(workflow)

            trace_service = get_trace_service(db)
            trace_tokens = TraceService.set_context(execution.trace_id, None)
            try:
                await trace_service.record_event(
                    "workflow_graph_built",
                    {
                        "node_count": len(workflow.nodes),
                        "edge_count": len(workflow.edges),
                        "predecessor_count": len(predecessors),
                        "successor_count": len(successors),
                    },
                )
            finally:
                TraceService.reset_context(trace_tokens)

            logger.info(f"前驱图: {predecessors}")
            logger.info(f"后继图: {successors}")

            # 找到起始节点（使用前驱图更可靠）
            # 方法1：前驱图中没有前驱的节点
            nodes_with_no_predecessors = [
                node_id for node_id, preds in predecessors.items()
                if len(preds) == 0
            ]

            # 方法2：通过节点类型识别
            start_nodes_by_type = [n for n in workflow.nodes if n.node_type == NodeType.START]

            # 方法3：通过 ID 或 label 识别（兼容旧数据）
            start_nodes_by_label = [n for n in workflow.nodes
                               if n.id == "start" or n.label in ["开始", "Start", "start"]]

            # 合并所有识别到的起始节点
            start_node_ids = set()
            if nodes_with_no_predecessors:
                start_node_ids.update(nodes_with_no_predecessors)
                logger.info(f"通过前驱图识别的起始节点: {nodes_with_no_predecessors}")
            if start_nodes_by_type:
                start_node_ids.update(n.id for n in start_nodes_by_type)
                logger.info(f"通过类型识别的起始节点: {[n.id for n in start_nodes_by_type]}")
            if start_nodes_by_label:
                start_node_ids.update(n.id for n in start_nodes_by_label)
                logger.info(f"通过标签识别的起始节点: {[n.id for n in start_nodes_by_label]}")

            if not start_node_ids:
                raise ValueError("工作流缺少开始节点，无法识别任何起始节点")

            # 选择第一个起始节点
            start_node_id = list(start_node_ids)[0]
            logger.info(f"使用起始节点: {start_node_id}")

            # 恢复执行时，进程重启前处于 RUNNING 的节点没有本地任务可等待，需重新排队执行。
            for node_state in execution.node_states.values():
                if self._is_running_status(node_state.status):
                    logger.warning(f"恢复执行时重置未完成运行节点: {node_state.node_id}")
                    if db and execution.trace_id and hasattr(db, "finish_running_trace_spans_for_node"):
                        await db.finish_running_trace_spans_for_node(
                            workflow_execution_id=execution.id,
                            node_id=node_state.node_id,
                            trace_id=execution.trace_id,
                            status="interrupted",
                            error="执行进程中断，节点已重新排队执行",
                            attributes={"requeued": True},
                        )
                    node_state.status = NodeStatus.PENDING
                    node_state.completed_at = None
                    node_state.output_data = {}
                    node_state.error = None

            # 已完成的节点集合（从执行状态恢复）
            completed_nodes: Set[str] = set()
            for node_id, node_state in execution.node_states.items():
                if self._is_completed_status(node_state.status):
                    completed_nodes.add(node_id)
                    logger.debug(f"节点 {node_id} 已完成，跳过重复执行")

            # 正在执行的节点集合
            running_nodes: Set[str] = set()

            # 初始就绪节点（如果已完成节点为空，从起始节点开始；否则查找下一批就绪节点）
            if not completed_nodes:
                ready_nodes = [start_node_id]
            else:
                # 从已完成节点之后继续
                ready_nodes = self._get_ready_nodes(workflow, execution, predecessors, completed_nodes)
                logger.info(f"从已完成节点继续，就绪节点: {ready_nodes}")

            max_iterations = 100
            iteration = 0

            logger.info(f"工作流 {execution_id} 开始执行，起始节点: {ready_nodes}")

            # ========== 主执行循环 ==========
            while len(completed_nodes) < len(workflow.nodes) and iteration < max_iterations:
                iteration += 1

                # 检查是否被暂停或取消
                if execution.cancel_requested:
                    execution.status = WorkflowStatus.CANCELLED
                    execution.completed_at = datetime.now()
                    logger.info(f"工作流 {execution_id} 收到取消请求")
                    return
                if execution.status in [WorkflowStatus.PAUSED, WorkflowStatus.CANCELLED]:
                    logger.info(f"工作流 {execution_id} 被暂停或取消")
                    return

                # 如果没有就绪节点，等待正在执行的节点完成
                if not ready_nodes:
                    if running_nodes:
                        logger.info(f"等待 {len(running_nodes)} 个节点完成: {running_nodes}")
                        await asyncio.sleep(0.1)
                        continue
                    else:
                        # 没有就绪节点也没有运行节点，说明工作流结束或死锁
                        break

                # ========== 执行所有就绪节点（并行执行） ==========
                if len(ready_nodes) > 1:
                    # 多个节点可以并行执行
                    logger.info(f"========== 并行执行 {len(ready_nodes)} 个节点: {ready_nodes} ==========")

                    # 创建任务映射，确保节点ID和任务对应
                    tasks_with_ids = []
                    for node_id in ready_nodes:
                        node = next((n for n in workflow.nodes if n.id == node_id), None)
                        if node:
                            running_nodes.add(node_id)
                            tasks_with_ids.append((node_id, node))
                            logger.info(f"准备并行任务: {node_id} ({node.label})")

                    # 并行执行
                    async def execute_with_id(node_id: str, node: WorkflowNode):
                        try:
                            logger.info(f"开始执行并行节点: {node_id} ({node.label})")
                            await self._execute_node_with_merge(
                                execution, node, predecessors, workflow, db
                            )
                            if execution.status == WorkflowStatus.PAUSED:
                                logger.info(f"并行节点触发工作流暂停: {node_id} ({node.label})")
                                return (node_id, False, "paused")
                            logger.info(f"并行节点执行完成: {node_id} ({node.label})")
                            return (node_id, True, None)
                        except Exception as e:
                            import traceback
                            logger.error(f"节点 {node_id} 执行异常: {e}")
                            logger.error(traceback.format_exc())
                            return (node_id, False, str(e))

                    tasks = [execute_with_id(nid, n) for nid, n in tasks_with_ids]

                    # 等待所有任务完成
                    logger.info(f"等待 {len(tasks)} 个并行任务完成...")
                    results = await asyncio.gather(*tasks, return_exceptions=True)
                    logger.info(f"所有 {len(tasks)} 个并行任务已返回结果")

                    # 处理结果
                    goto_target = None
                    goto_source_node = None  # 记录 goto 来源节点
                    for i, result in enumerate(results):
                        node_id = tasks_with_ids[i][0]
                        node = tasks_with_ids[i][1]
                        running_nodes.discard(node_id)

                        if isinstance(result, Exception):
                            logger.error(f"节点 {node_id} 任务抛出异常: {result}")
                            completed_nodes.add(node_id)  # 标记为完成（失败）以避免死锁
                        elif isinstance(result, tuple):
                            nid, success, error = result
                            if success:
                                logger.info(f"节点 {nid} 执行成功")
                            else:
                                logger.error(f"节点 {nid} 执行失败: {error}")
                            if execution.status == WorkflowStatus.PAUSED:
                                logger.info(f"工作流 {execution_id} 已暂停，等待外部输入")
                                return
                            completed_nodes.add(nid)

                            # 检查条件分支的 goto
                            if success and node.node_type == NodeType.CONDITION:
                                next_node_id = self._get_next_node(nid, execution, workflow)
                                if next_node_id and next_node_id in completed_nodes:
                                    goto_target = next_node_id
                                    goto_source_node = nid
                                    logger.info(f"并行执行中检测到条件分支 goto: {nid} -> {next_node_id}")
                        else:
                            completed_nodes.add(node_id)

                    # 处理 goto（只处理第一个检测到的，最多重试 3 次）
                    if goto_target:
                        # 初始化 goto 重试计数
                        if "goto_retry_counts" not in execution.context:
                            execution.context["goto_retry_counts"] = {}

                        goto_key = f"{goto_source_node}->{goto_target}"
                        current_retry = execution.context["goto_retry_counts"].get(goto_key, 0)

                        # 检查是否达到最大重试次数（3 次）
                        if current_retry >= 3:
                            logger.warning(
                                f"并行执行中 goto 已达最大重试次数 (3次): {goto_source_node} -> {goto_target}，跳过重试"
                            )
                            goto_target = None  # 清除 goto 目标
                        else:
                            # 增加重试计数
                            execution.context["goto_retry_counts"][goto_key] = current_retry + 1
                            logger.info(
                                f"并行执行后处理 goto: 重置节点 {goto_target} "
                                f"(重试 {current_retry + 1}/3 次)"
                            )

                            # 检查目标节点是否是 start 节点
                            target_node = next((n for n in workflow.nodes if n.id == goto_target), None)
                            is_goto_to_start = target_node and (
                                target_node.node_type == NodeType.START or
                                target_node.label in ["开始", "Start", "start"]
                            )

                            if is_goto_to_start:
                                # goto 到 start 节点：重置所有中间节点的状态
                                logger.info(f"并行执行后 goto 到开始节点，重置所有节点状态")
                                for nid in list(completed_nodes):
                                    completed_nodes.discard(nid)
                                    state = execution.node_states.get(nid)
                                    if state:
                                        state.status = NodeStatus.PENDING
                                        state.started_at = None
                                        state.completed_at = None
                                        state.output_data = {}
                                        state.error = None
                            else:
                                reset_nodes = self._get_goto_reset_nodes(
                                    workflow,
                                    goto_source_node,
                                    goto_target,
                                )
                                self._reset_nodes_for_goto(
                                    execution,
                                    completed_nodes,
                                    reset_nodes,
                                    f"并行执行后 goto: {goto_source_node} -> {goto_target}",
                                )

                    logger.info(f"并行执行完成，已完成节点: {completed_nodes}")

                elif len(ready_nodes) == 1:
                    # 单个节点执行
                    node_id = ready_nodes[0]
                    node = next((n for n in workflow.nodes if n.id == node_id), None)
                    if not node:
                        logger.warning(f"节点 {node_id} 不存在，跳过")
                        completed_nodes.add(node_id)
                        continue

                    logger.info(f"========== 执行单个节点: {node.id} ({node.node_type.value}) - {node.label} ==========")
                    execution.current_node = node_id

                    try:
                        await self._execute_node_with_merge(
                            execution, node, predecessors, workflow, db
                        )
                        if execution.status == WorkflowStatus.PAUSED:
                            logger.info(f"工作流 {execution_id} 已暂停，等待外部输入")
                            return
                        completed_nodes.add(node_id)
                        logger.info(f"节点 {node_id} 执行完成")

                        # ========== 条件分支 goto 处理（最多重试 3 次）==========
                        if node.node_type == NodeType.CONDITION:
                            next_node_id = self._get_next_node(node_id, execution, workflow)
                            if next_node_id:
                                # 检查是否是 goto（retry 到已完成的节点）
                                if next_node_id in completed_nodes:
                                    # 初始化 goto 重试计数
                                    if "goto_retry_counts" not in execution.context:
                                        execution.context["goto_retry_counts"] = {}

                                    goto_key = f"{node_id}->{next_node_id}"
                                    current_retry = execution.context["goto_retry_counts"].get(goto_key, 0)

                                    # 检查是否达到最大重试次数（3 次）
                                    if current_retry >= 3:
                                        logger.warning(
                                            f"条件分支 goto 已达最大重试次数 (3次): {node_id} -> {next_node_id}，跳过重试"
                                        )
                                        # 不再执行 goto，继续正常流程
                                    else:
                                        # 增加重试计数
                                        execution.context["goto_retry_counts"][goto_key] = current_retry + 1
                                        logger.info(
                                            f"条件分支 goto: {node_id} -> {next_node_id} "
                                            f"(重试 {current_retry + 1}/3 次)"
                                        )

                                        # 检查目标节点是否是 start 节点
                                        target_node = next((n for n in workflow.nodes if n.id == next_node_id), None)
                                        is_goto_to_start = target_node and (
                                            target_node.node_type == NodeType.START or
                                            target_node.label in ["开始", "Start", "start"]
                                        )

                                        if is_goto_to_start:
                                            # goto 到 start 节点：重置所有中间节点的状态
                                            logger.info(f"goto 到开始节点，重置所有节点状态")
                                            for nid in list(completed_nodes):
                                                completed_nodes.discard(nid)
                                                state = execution.node_states.get(nid)
                                                if state:
                                                    state.status = NodeStatus.PENDING
                                                    state.started_at = None
                                                    state.completed_at = None
                                                    state.output_data = {}
                                                    state.error = None
                                        else:
                                            reset_nodes = self._get_goto_reset_nodes(
                                                workflow,
                                                node_id,
                                                next_node_id,
                                            )
                                            self._reset_nodes_for_goto(
                                                execution,
                                                completed_nodes,
                                                reset_nodes,
                                                f"条件分支 goto: {node_id} -> {next_node_id}",
                                            )

                                        # 将目标节点添加到就绪列表
                                        ready_nodes = [next_node_id]
                                        continue

                    except Exception as e:
                        logger.error(f"节点 {node_id} 执行失败: {e}")
                        node_state = execution.node_states.get(node_id)
                        if node_state:
                            node_state.status = NodeStatus.FAILED
                            node_state.error = str(e)
                        # 标记为完成但失败，避免死锁
                        completed_nodes.add(node_id)
                else:
                    # ready_nodes 为空，这不应该发生
                    logger.warning("ready_nodes 为空，检查是否有死锁")

                # ========== 查找下一批就绪节点 ==========
                ready_nodes = self._get_ready_nodes(workflow, execution, predecessors, completed_nodes)

                # 检查是否到达结束节点
                for node_id in list(completed_nodes):
                    node = next((n for n in workflow.nodes if n.id == node_id), None)
                    if node and (node.node_type == NodeType.END or node.label in ["结束", "End", "end"]):
                        logger.info(f"到达结束节点: {node.id}")
                        # 不再添加结束节点的后继
                        continue

                # 保存循环 checkpoint/heartbeat
                if db:
                    execution.resume_cursor = {
                        "completed_nodes": list(completed_nodes),
                        "ready_nodes": list(ready_nodes),
                        "iteration": iteration,
                    }
                    execution.last_heartbeat_at = datetime.now()
                    execution.lease_expires_at = datetime.now() + timedelta(seconds=getattr(settings, "operation_lease_ttl_seconds", 60))
                    await self._save_execution_to_db(execution, db)
                    if execution.request_id:
                        operation = await db.get_operation_request_by_request_id(execution.request_id)
                        if operation:
                            await OperationLifecycleService(db=db, redis=redis_service).heartbeat(operation)

                logger.info(f"已完成节点: {completed_nodes}, 下批就绪: {ready_nodes}")
                tokens = TraceService.set_context(execution.trace_id, None)
                try:
                    await trace_service.record_event("workflow_checkpoint_saved", {
                        "iteration": iteration,
                        "completed_nodes": list(completed_nodes),
                        "ready_nodes": list(ready_nodes),
                    })
                finally:
                    TraceService.reset_context(tokens)

            # ========== 完成 ==========
            if execution.status == WorkflowStatus.RUNNING:
                failed_nodes = [
                    state for state in execution.node_states.values()
                    if state.status == NodeStatus.FAILED
                ]
                pending_nodes = [
                    state for state in execution.node_states.values()
                    if not self._is_completed_status(state.status) and state.status != NodeStatus.FAILED
                ]
                if failed_nodes:
                    execution.status = WorkflowStatus.FAILED
                    execution.error = failed_nodes[0].error or f"节点 {failed_nodes[0].node_id} 执行失败"
                    execution.completed_at = datetime.now()
                elif pending_nodes:
                    execution.status = WorkflowStatus.FAILED
                    execution.error = f"工作流提前结束，仍有未完成节点: {', '.join(state.node_id for state in pending_nodes)}"
                    execution.completed_at = datetime.now()
                else:
                    execution.status = WorkflowStatus.COMPLETED
                    execution.completed_at = datetime.now()

        except Exception as e:
            logger.error(f"工作流执行失败: {e}")
            execution.status = WorkflowStatus.FAILED
            execution.error = str(e)
            execution.completed_at = datetime.now()

        finally:
            # 计算总耗时
            if execution.started_at and execution.completed_at:
                delta = execution.completed_at - execution.started_at
                execution.total_duration_ms = int(delta.total_seconds() * 1000)

            # 保存到数据库
            if db:
                trace_service = get_trace_service(db)
                await trace_service.finish_trace(execution.trace_id, execution.status.value, error=execution.error)
                await self._save_execution_to_db(execution, db)
                await self._mark_operation_terminal(execution, db)

            self._running_tasks.pop(execution_id, None)

            if execution.status in {
                WorkflowStatus.COMPLETED,
                WorkflowStatus.FAILED,
                WorkflowStatus.CANCELLED,
                WorkflowStatus.PAUSED,
            }:
                replay_path = await self._export_execution_replay_markdown(execution, workflow, db)
                if replay_path and db:
                    await self._save_execution_to_db(execution, db)

            # 广播完成事件；保留 workflow_completed 兼容事件，同时为失败提供显式事件。
            if execution.status == WorkflowStatus.PAUSED:
                await self._broadcast_status(execution_id, "workflow_paused", self._build_execution_event_payload(
                    execution,
                    pending_user_input=execution.context.get("pending_user_input"),
                ))
            else:
                if execution.status == WorkflowStatus.FAILED:
                    await self._broadcast_status(
                        execution_id,
                        "workflow_failed",
                        self._build_workflow_failure_event_payload(execution),
                    )
                await self._broadcast_status(execution_id, "workflow_completed", self._build_execution_event_payload(
                    execution,
                    completed_at=execution.completed_at,
                    total_duration_ms=execution.total_duration_ms,
                ))

    async def _execute_node_with_merge(
        self,
        execution: WorkflowExecution,
        node: WorkflowNode,
        predecessors: Dict[str, List[str]],
        workflow: WorkflowDefinition,
        db=None,
    ):
        """
        执行节点，先合并所有前驱节点的输出

        Args:
            execution: 工作流执行实例
            node: 要执行的节点
            predecessors: 前驱图
            workflow: 工作流定义
            db: 数据库连接
        """
        # 合并前驱节点的输出
        merged_context = await self._merge_predecessor_outputs(
            node, execution, predecessors, workflow
        )
        # 更新执行上下文
        execution.context.update(merged_context)

        # 执行节点
        await self._execute_node(execution, node, db)

    async def _prepare_node_inputs(
        self,
        node: WorkflowNode,
        execution: "WorkflowExecution",
        db=None,
    ) -> Dict[str, Any]:
        """
        根据节点的 inputs 配置准备输入数据

        Args:
            node: 工作流节点
            execution: 工作流执行实例
            db: 数据库连接

        Returns:
            Dict: 准备好的输入数据（将合并到 context）
        """
        context = execution.context.copy()

        # 如果节点没有 inputs 配置，返回原上下文（向后兼容）
        if not node.inputs:
            return context

        project_id = execution.project_id

        for input_config in node.inputs:
            input_name = input_config.name
            source = input_config.source
            required = input_config.required

            # 检查是否已经存在于上下文中
            if input_name in context and context[input_name] is not None:
                logger.debug(f"输入 '{input_name}' 已存在于上下文，跳过加载")
                continue

            value = None

            try:
                if source == "database":
                    # 从数据库加载
                    data_type = input_config.data_type
                    if not data_type:
                        logger.warning(f"输入 '{input_name}' 指定了 database 来源但未设置 data_type")
                        continue

                    value = await self._load_data_from_database(
                        data_type, project_id, db, context
                    )

                elif source == "context":
                    # 从全局上下文获取
                    key = input_config.key or input_name
                    value = execution.context.get(key)

                elif source == "variable":
                    # 从工作流变量获取
                    key = input_config.key or input_name
                    workflow = self._workflows.get(execution.workflow_id)
                    if workflow:
                        value = workflow.variables.get(key)

                elif source == "upstream":
                    # 从上游节点获取
                    upstream_node_id = input_config.upstream_node
                    upstream_field = input_config.upstream_field or input_name

                    if upstream_node_id and upstream_node_id in execution.node_states:
                        upstream_state = execution.node_states[upstream_node_id]
                        if upstream_state.output_data:
                            value = upstream_state.output_data.get(upstream_field)
                    else:
                        # 尝试从边信息中获取上游节点
                        workflow = self._workflows.get(execution.workflow_id)
                        if workflow:
                            for edge in workflow.edges:
                                if edge.target == node.id:
                                    source_node_id = edge.source
                                    if source_node_id in execution.node_states:
                                        source_state = execution.node_states[source_node_id]
                                        if source_state.output_data:
                                            value = source_state.output_data.get(upstream_field)
                                    break

                elif source == "user_input":
                    # 用户运行时输入（在 workflow.variables 或 context 中查找）
                    key = input_config.key or input_name
                    value = execution.context.get(f"user_input_{key}") or execution.context.get(key)

            except Exception as e:
                logger.error(f"加载输入 '{input_name}' 失败: {e}")

            # 处理值
            if value is None:
                if required and input_config.default is None:
                    logger.warning(f"必需的输入 '{input_name}' 未能加载，来源: {source}")
                elif input_config.default is not None:
                    value = input_config.default
                    logger.debug(f"输入 '{input_name}' 使用默认值")
            else:
                logger.info(f"节点 '{node.label}' 加载输入 '{input_name}': {source} 来源，数据量: {len(value) if isinstance(value, (list, dict)) else 1}")

            if value is not None:
                context[input_name] = value

        return context

    def _build_node_input_snapshot(
        self,
        node: WorkflowNode,
        execution: "WorkflowExecution",
        prepared_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """构建节点输入快照，便于前端监控查看。"""
        source_context = prepared_context or execution.context

        if node.inputs:
            snapshot: Dict[str, Any] = {}
            sources: Dict[str, Any] = {}

            for input_config in node.inputs:
                input_name = input_config.name
                if input_name in source_context:
                    snapshot[input_name] = source_context.get(input_name)

                sources[input_name] = {
                    "source": input_config.source,
                    "key": input_config.key,
                    "data_type": input_config.data_type,
                    "upstream_node": input_config.upstream_node,
                    "upstream_field": input_config.upstream_field,
                    "required": input_config.required,
                }

            runtime_snapshot_keys = [
                "scene_performance_context",
                "role_performance_context",
                "character_performance_packets",
                "public_performances",
                "private_performances",
                "relationship_deltas",
                "state_deltas",
                "continuity_notes",
                "performance_warnings",
                "role_performance_gate",
                "role_performance_gate_passed",
                "role_performance_gate_blockers",
                "role_performance_gate_warnings",
                "confirmed_prior_state_packet",
                "confirmed_prior_state_packet_provenance",
            ]
            for key in runtime_snapshot_keys:
                if source_context.get(key) is not None and key not in snapshot:
                    snapshot[key] = source_context.get(key)

            if sources:
                snapshot["_input_trace"] = {
                    "configured_inputs": list(sources.keys()),
                    "sources": sources,
                    "included_runtime_context": [
                        key for key in runtime_snapshot_keys if key in snapshot
                    ],
                }
            return self._make_json_safe(snapshot)

        fallback_keys = [
            "chapter_num",
            "chapter_title",
            "chapter_summary",
            "chapter_outline",
            "target_word_count",
            "chapter_target_word_count",
            "word_count",
            "chapter_goals",
            "scene_directions",
            "project_info",
            "world_info",
            "characters",
            "lore_entries",
            "existing_hooks",
            "events",
            "locations",
            "evaluation_feedback",
            "retry_message",
            "user_feedback",
            "graph_context",
            "graph_context_summary",
            "graph_context_source",
            "graph_context_warnings",
            "workflow_state",
            "node_outputs",
            "asset_state",
            "state_transitions",
            "context_propagation_trace",
            "scene_performance_context",
            "role_performance_context",
            "public_performances",
            "private_performances",
            "relationship_deltas",
            "state_deltas",
            "continuity_notes",
            "performance_warnings",
            "role_performance_gate",
            "role_performance_gate_passed",
            "role_performance_gate_blockers",
            "role_performance_gate_warnings",
            "confirmed_prior_state_packet",
            "confirmed_prior_state_packet_provenance",
        ]
        snapshot = {
            key: source_context.get(key)
            for key in fallback_keys
            if source_context.get(key) is not None
        }
        return self._make_json_safe(snapshot)

    def _compact_prompt_render_trace(self, trace: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """保留可审计的 prompt/config 标识符，不携带 prompt 正文。"""
        if not isinstance(trace, dict):
            return {}
        allowed_keys = [
            "template_id",
            "template_scenario",
            "config_id",
            "prompt_ids",
            "skill_ids",
            "writing_rule_ids",
            "context_blocks",
            "fallbacks_used",
            "deprecated_sources_used",
            "missing_prompt_ids",
        ]
        compact = {key: trace.get(key) for key in allowed_keys if trace.get(key) is not None}
        return self._make_json_safe(compact)

    async def _capture_effective_agent_input_snapshot(
        self,
        execution: "WorkflowExecution",
        node: WorkflowNode,
        resolved_agent_type: str,
        resolved_scenario: Optional[str],
        context: Dict[str, Any],
        db=None,
    ) -> None:
        """记录 Writer 实际执行前的有效输入，覆盖预执行快照的上下文盲区。"""
        execution.context.setdefault("node_runtime_metadata", {}).setdefault(node.id, {}).update({
            "source_node_id": node.id,
            "source_node_label": node.label,
            "source_agent_type": node.agent_type,
            "resolved_agent_type": resolved_agent_type,
            "resolved_scenario": resolved_scenario or "default",
            "source_trace_id": execution.trace_id,
        })
        if resolved_agent_type != "writer":
            return

        node_state = execution.node_states.get(node.id)
        if not node_state:
            return

        snapshot = self._build_node_input_snapshot(node, execution, context)
        context_keys = sorted(str(key) for key in context.keys() if key != "_trace")
        required_context_present = {
            "chapter_outline": bool(context.get("chapter_outline")),
            "target_word_count": context.get("target_word_count") is not None,
            "previous_chapters": bool(context.get("previous_chapters") or context.get("chapter_summaries")),
            "characters": bool(context.get("characters")),
            "lore_entries": bool(context.get("lore_entries")),
            "hooks": bool(context.get("existing_hooks") or context.get("hooks")),
            "workflow_state": bool(context.get("workflow_state")),
            "graph_context": bool(context.get("graph_context") or context.get("graph_context_summary")),
        }
        snapshot["_effective_agent_input"] = self._make_json_safe({
            "resolved_agent_type": resolved_agent_type,
            "resolved_scenario": resolved_scenario or "default",
            "context_keys": context_keys,
            "required_context_present": required_context_present,
        })
        node_state.input_data = self._make_json_safe(snapshot)
        execution.context.setdefault("node_runtime_metadata", {}).setdefault(node.id, {}).update({
            "source_node_id": node.id,
            "source_node_label": node.label,
            "source_agent_type": node.agent_type,
            "resolved_agent_type": resolved_agent_type,
            "resolved_scenario": resolved_scenario or "default",
            "source_trace_id": execution.trace_id,
            "source_node_input_keys": [key for key in node_state.input_data.keys() if key != "_effective_agent_input"],
        })
        if db:
            await self._save_execution_to_db(execution, db)
            trace_service = get_trace_service(db)
            await trace_service.record_event("writer_effective_input_captured", {
                "node_id": node.id,
                "resolved_agent_type": resolved_agent_type,
                "resolved_scenario": resolved_scenario or "default",
                "required_context_present": required_context_present,
            })
            await trace_service.record_artifact("node_effective_input", content=node_state.input_data)

    def _build_writer_save_provenance(
        self,
        execution: "WorkflowExecution",
        node: Optional[WorkflowNode],
        writer_output: Dict[str, Any],
        *,
        contract_metadata: Optional[Dict[str, Any]] = None,
        prompt_trace: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """构建章节保存来源审计信息，仅保存标识符和大小，不保存正文。"""
        node_id = node.id if node else None
        node_state = execution.node_states.get(node_id) if node_id else None
        runtime_metadata = execution.context.get("node_runtime_metadata", {}).get(node_id, {}) if node_id else {}
        contract_metadata = contract_metadata or {}
        compact_prompt_trace = self._compact_prompt_render_trace(prompt_trace)
        content_field = "content" if writer_output.get("content") else "chapter_content"
        content_value = writer_output.get("content") or writer_output.get("chapter_content") or ""
        provenance = {
            "source_node_id": node_id or runtime_metadata.get("source_node_id"),
            "source_node_label": (node.label if node else None) or runtime_metadata.get("source_node_label"),
            "source_agent_type": (node.agent_type if node else None) or runtime_metadata.get("source_agent_type"),
            "resolved_agent_type": runtime_metadata.get("resolved_agent_type") or (node.agent_type if node else None),
            "resolved_scenario": runtime_metadata.get("resolved_scenario"),
            "source_trace_id": execution.trace_id,
            "source_output_contract_id": contract_metadata.get("output_contract_id") or runtime_metadata.get("output_contract_id"),
            "source_output_schema_name": contract_metadata.get("output_schema_name") or runtime_metadata.get("output_schema_name"),
            "source_output_schema_version": contract_metadata.get("output_schema_version") or runtime_metadata.get("output_schema_version"),
            "source_node_input_keys": list((node_state.input_data or {}).keys()) if node_state else runtime_metadata.get("source_node_input_keys", []),
            "source_node_output_keys": list(writer_output.keys()),
            "writer_output_content_field": content_field,
            "writer_output_content_chars": len(content_value),
            "writer_output_word_count": writer_output.get("word_count"),
            "writer_prompt_trace_present": bool(compact_prompt_trace),
        }
        if compact_prompt_trace:
            provenance["writer_prompt_trace"] = compact_prompt_trace
        return self._make_json_safe(provenance)

    async def _load_data_from_database(
        self,
        data_type: str,
        project_id: str,
        db,
        context: Dict[str, Any],
    ) -> Optional[Any]:
        """
        从数据库加载指定类型的数据

        Args:
            data_type: 数据类型
            project_id: 项目 ID
            db: 数据库连接
            context: 当前上下文（用于获取关联数据）

        Returns:
            加载的数据，或 None
        """
        if not db:
            return None

        try:
            if data_type == "characters":
                chars = await db.get_all_characters(project_id) if hasattr(db, 'get_all_characters') else []
                return chars

            elif data_type == "world" or data_type == "world_info":
                world_id = context.get("world_id")
                world = None
                if world_id and hasattr(db, 'get_world'):
                    world = await db.get_world(str(world_id))
                elif hasattr(db, 'get_default_world'):
                    world = await db.get_default_world(project_id)
                else:
                    project = await db.get_project(project_id) if hasattr(db, 'get_project') else None
                    if project and project.get("world_id") and hasattr(db, 'get_world'):
                        world = await db.get_world(project["world_id"])
                if world:
                    return {
                        "id": world.get("id", ""),
                        "name": world.get("name", "未知世界"),
                        "project_id": world.get("project_id"),
                        "parent_world_id": world.get("parent_world_id"),
                        "scope_type": world.get("scope_type", "root"),
                        "inherit_rules": world.get("inherit_rules", True),
                        "world_type": world.get("world_type", "奇幻"),
                        "description": world.get("description", ""),
                        "background": world.get("background", ""),
                        "rules": world.get("rules", {}),
                        "themes": world.get("themes", []),
                        "tone": world.get("tone", "正剧"),
                        "target_audience": world.get("target_audience", "大众"),
                    }
                return None

            elif data_type == "hooks" or data_type == "existing_hooks":
                world_id = context.get("world_id")
                if hasattr(db, 'get_all_hooks'):
                    return await db.get_all_hooks(
                        project_id=project_id,
                        world_id=str(world_id) if world_id else None,
                        include_inherited=bool(world_id),
                        limit=200,
                    )
                hooks = await db.get_hooks(project_id) if hasattr(db, 'get_hooks') else []
                return hooks

            elif data_type == "chapters" or data_type == "previous_chapters":
                world_id = context.get("world_id")
                if world_id and hasattr(db, 'get_chapters_by_world'):
                    chapters = await db.get_chapters_by_world(str(world_id))
                    return [chapter for chapter in chapters if str(chapter.get("project_id")) == str(project_id)]
                chapters = await db.get_chapters_by_project(project_id) if hasattr(db, 'get_chapters_by_project') else []
                return chapters

            elif data_type == "project":
                project = await db.get_project(project_id) if hasattr(db, 'get_project') else None
                return project

            elif data_type == "events":
                events = await db.get_events(project_id) if hasattr(db, 'get_events') else []
                return events

            elif data_type == "graph_context":
                request = context.get("graph_context_request") or {}
                if not isinstance(request, dict) or not request.get("enabled"):
                    return None
                anchor_type = request.get("anchor_type") or "character"
                anchor_id = request.get("anchor_id") or context.get("character_id")
                if not anchor_id:
                    logger.warning("graph_context 请求缺少 anchor_id")
                    return None
                try:
                    from app.api.app import nebula_db
                    from app.models.graph_context import GraphContextOptions, GraphContextSource
                    from app.services.graph_context_service import GraphContextService

                    options = GraphContextOptions(
                        depth=int(request.get("depth") or 1),
                        max_nodes=int(request.get("max_nodes") or 16),
                        include_world=bool(request.get("include_world", True)),
                        include_region=bool(request.get("include_region", True)),
                        include_hooks=bool(request.get("include_hooks", True)),
                        world_id=str(request.get("world_id") or context.get("world_id")) if (request.get("world_id") or context.get("world_id")) else None,
                        include_inherited=bool(request.get("include_inherited", True)),
                        allow_fallback=bool(request.get("allow_fallback", True)),
                        source=GraphContextSource(request.get("source") or "auto"),
                    )
                    graph_service = GraphContextService(db, nebula_db)
                    graph_context = await graph_service.get_local_graph_context(
                        anchor_type,
                        str(anchor_id),
                        project_id=project_id,
                        options=options,
                    )
                    graph_context_data = graph_context.model_dump(mode="json")
                    context["graph_context_candidate"] = graph_context_data
                    return graph_context_data
                except Exception as e:
                    logger.warning(f"加载 graph_context 失败，跳过图上下文: {e}")
                    return None

            elif data_type == "locations":
                locations = await db.get_locations(project_id) if hasattr(db, 'get_locations') else []
                return locations

            elif data_type == "event_pool":
                # 事件池（来自事件生成器）
                events = await db.get_events(project_id) if hasattr(db, 'get_events') else []
                return events

            else:
                logger.warning(f"未知的数据类型: {data_type}")
                return None

        except Exception as e:
            logger.error(f"从数据库加载数据类型 '{data_type}' 失败: {e}")
            return None

    def _resolve_output_contract(self, contract_id: Optional[str]) -> Optional[AgentOutputContract]:
        """根据 contract_id 解析输出契约。"""
        if not contract_id:
            return None
        return DEFAULT_AGENT_OUTPUT_CONTRACT_REGISTRY.get(contract_id)

    def _get_response_payload(self, response: Optional[AgentResponse]) -> Any:
        """提取 AgentResponse 的兼容 payload。"""
        if response is None:
            return None
        if response.structured_data is not None:
            return response.structured_data
        if response.text_output is not None:
            return response.text_output
        if response.data is not None:
            return response.data
        return None

    def _get_response_output_keys(self, response: Optional[AgentResponse]) -> List[str]:
        """提取响应中的结构化字段名。"""
        payload = self._get_response_payload(response)
        if isinstance(payload, dict):
            return list(payload.keys())
        return []

    def _normalize_contract_payload(
        self,
        contract: AgentOutputContract,
        payload: Any,
        response: Optional[AgentResponse] = None,
    ) -> Any:
        """针对兼容期的旧输出形态做最小归一化。"""
        if not isinstance(payload, dict):
            return payload

        normalized = dict(payload)

        if contract.mode == OutputContractMode.HYBRID and contract.text_field and contract.text_field not in normalized:
            if response and response.text_output:
                normalized[contract.text_field] = response.text_output
            else:
                for alias in ("content", "message", "text", "output"):
                    alias_value = normalized.get(alias)
                    if isinstance(alias_value, str) and alias_value:
                        normalized[contract.text_field] = alias_value
                        break

        if response and response.metadata:
            metadata = normalized.get("metadata") if isinstance(normalized.get("metadata"), dict) else {}
            normalized["metadata"] = {**response.metadata, **metadata}

        if contract.contract_id == "writer.workflow_output":
            metadata = normalized.get("metadata") if isinstance(normalized.get("metadata"), dict) else {}
            for field_name in ("word_count", "style_check", "hooks_embedded", "future_setup"):
                if field_name in normalized:
                    metadata[field_name] = normalized[field_name]
            if metadata:
                normalized["metadata"] = metadata

        return normalized

    def _validate_contract_payload(
        self,
        contract: AgentOutputContract,
        payload: Any,
        *,
        node: WorkflowNode,
        response: Optional[AgentResponse] = None,
    ) -> Any:
        """校验 payload 是否符合输出契约。"""
        normalized = self._normalize_contract_payload(contract, payload, response=response)

        if contract.mode == OutputContractMode.TEXT:
            if isinstance(normalized, str):
                return normalized
            if isinstance(normalized, dict) and contract.text_field and isinstance(normalized.get(contract.text_field), str):
                return normalized
            raise ValueError(
                f"节点 '{node.label}' 输出不符合文本契约 {contract.contract_id}: 缺少文本字段"
            )

        if not isinstance(normalized, dict):
            raise ValueError(
                f"节点 '{node.label}' 输出不符合契约 {contract.contract_id}: 期望对象，实际为 {type(normalized).__name__}"
            )

        missing_fields: List[str] = []
        for field_path in contract.structured_fields:
            top_level_field = field_path.split(".")[0].split("[")[0]
            if top_level_field and top_level_field not in normalized:
                missing_fields.append(field_path)

        if contract.mode == OutputContractMode.HYBRID and contract.text_field:
            text_value = normalized.get(contract.text_field)
            if not isinstance(text_value, str) or not text_value:
                missing_fields.append(contract.text_field)

        if missing_fields:
            raise ValueError(
                f"节点 '{node.label}' 输出不符合契约 {contract.contract_id}: 缺少字段 {', '.join(sorted(set(missing_fields)))}"
            )

        return normalized

    def _resolve_node_output_contract(
        self,
        node: WorkflowNode,
        response: Optional[AgentResponse] = None,
    ) -> AgentOutputContract:
        """解析节点本次执行的主输出契约。"""
        explicit_contract_ids = [cfg.contract_id for cfg in node.outputs if cfg.contract_id]
        if explicit_contract_ids:
            contract = self._resolve_output_contract(explicit_contract_ids[0])
            if not contract:
                raise ValueError(f"节点 '{node.label}' 引用了不存在的输出契约: {explicit_contract_ids[0]}")
            return contract

        if response and response.contract_id:
            contract = self._resolve_output_contract(response.contract_id)
            if not contract:
                raise ValueError(f"节点 '{node.label}' 返回了不存在的输出契约: {response.contract_id}")
            return contract

        default_contract = self._resolve_output_contract("workflow.node_output")
        if not default_contract:
            raise ValueError("默认工作流输出契约 workflow.node_output 不存在")
        return default_contract

    def _apply_node_output_contract(
        self,
        node: WorkflowNode,
        output: Any,
        response: Optional[AgentResponse] = None,
    ) -> tuple[Any, AgentOutputContract]:
        """对节点输出应用主契约与工作流包装契约校验。"""
        contract = self._resolve_node_output_contract(node, response)
        validated_output = output

        if contract.contract_id != "workflow.node_output":
            validated_output = self._validate_contract_payload(
                contract,
                output,
                node=node,
                response=response,
            )

        wrapper_contract = self._resolve_output_contract("workflow.node_output")
        if not wrapper_contract:
            raise ValueError("默认工作流输出契约 workflow.node_output 不存在")

        self._validate_contract_payload(
            wrapper_contract,
            {
                "node_id": node.id,
                "output": validated_output,
            },
            node=node,
        )

        return validated_output, contract

    def _build_contract_metadata(
        self,
        contract: Optional[AgentOutputContract],
        response: Optional[AgentResponse] = None,
    ) -> Dict[str, Any]:
        """构建可序列化的输出契约元数据。"""
        if not contract and not response:
            return {}

        mode = response.mode if response and response.mode else (contract.mode if contract else None)
        contract_id = response.contract_id if response and response.contract_id else (contract.contract_id if contract else None)
        schema_name = response.schema_name if response and response.schema_name else (contract.schema_name if contract else None)
        schema_version = (
            response.schema_version
            if response and response.schema_version
            else (contract.schema_version if contract else None)
        )

        return {
            "output_contract_id": contract_id,
            "output_mode": mode.value if isinstance(mode, OutputContractMode) else mode,
            "output_schema_name": schema_name,
            "output_schema_version": schema_version,
        }

    def _normalize_workflow_resource_requirements(
        self,
        output: Any,
        execution: WorkflowExecution,
        node: WorkflowNode,
    ) -> Dict[str, Any]:
        """归一化节点输出中的资源需求建议，仅写入工作流运行期上下文。"""
        if not isinstance(output, dict):
            return {}

        raw_requirements: List[tuple[str, Any]] = []
        for key in ("resource_requirements", "role_delta_resource_requirements"):
            for item in self._ensure_context_list(output.get(key)):
                raw_requirements.append((key, item))

        if not raw_requirements:
            return {}

        existing = self._ensure_context_list(execution.context.get("pending_resource_requirements"))
        normalized: List[Dict[str, Any]] = [item for item in existing if isinstance(item, dict)]
        seen: set[tuple[str, str, str, str]] = set()
        for item in normalized:
            seen.add((
                str(item.get("requirement_type") or "").strip(),
                str(item.get("resource_name") or "").strip(),
                str(item.get("reason") or "").strip(),
                str(item.get("source_node_id") or "").strip(),
            ))

        latest_all: List[Dict[str, Any]] = []
        latest_role_delta: List[Dict[str, Any]] = []
        valid_severities = {"blocking", "advisory", "optional"}

        for source_key, requirement in raw_requirements:
            if not isinstance(requirement, dict):
                continue

            requirement_type = str(requirement.get("requirement_type") or "").strip()
            resource_name = str(requirement.get("resource_name") or requirement.get("name") or "").strip()
            reason = str(requirement.get("reason") or requirement.get("description") or "").strip()
            if not requirement_type or not resource_name:
                continue

            severity = str(requirement.get("severity") or "advisory").strip().lower()
            if severity not in valid_severities:
                severity = "advisory"

            normalized_item = dict(requirement)
            normalized_item.update({
                "requirement_type": requirement_type,
                "resource_name": resource_name,
                "severity": severity,
                "status": str(requirement.get("status") or "pending").strip() or "pending",
                "reason": reason,
                "source_agent": requirement.get("source_agent") or node.agent_type or node.node_type.value,
                "source_field": source_key,
                "source_node_id": node.id,
                "source_node_label": node.label,
                "source_execution_id": execution.id,
                "project_id": execution.project_id,
            })
            if execution.context.get("chapter_num") is not None:
                normalized_item.setdefault("chapter_num", execution.context.get("chapter_num"))
            if execution.context.get("chapter_outline_id") is not None:
                normalized_item.setdefault("chapter_outline_id", execution.context.get("chapter_outline_id"))
            normalized_item.setdefault("suggested_payload", {})

            fingerprint = (requirement_type, resource_name, reason, node.id)
            if fingerprint in seen:
                continue
            seen.add(fingerprint)
            normalized.append(normalized_item)
            latest_all.append(normalized_item)
            if source_key == "role_delta_resource_requirements":
                latest_role_delta.append(normalized_item)

        if not latest_all:
            return {}

        updates: Dict[str, Any] = {
            "pending_resource_requirements": normalized,
            "workflow_resource_requirements": normalized,
            "latest_resource_requirements": latest_all,
        }
        if latest_role_delta:
            updates["latest_role_delta_resource_requirements"] = latest_role_delta
        return updates

    async def _persist_workflow_resource_requirements(
        self,
        requirements: List[Dict[str, Any]],
        execution: WorkflowExecution,
        db,
    ) -> Dict[str, Any]:
        """把运行期资源需求落库，并刷新章节 readiness；不修改大纲或资源本体。"""
        if not db or not requirements or not hasattr(db, "save_outline_resource_requirements"):
            return {}

        saved_ids = await db.save_outline_resource_requirements(requirements)
        readiness_by_chapter: Dict[str, Any] = {}
        if hasattr(db, "update_chapter_resource_readiness"):
            seen_chapters: set[tuple[Optional[str], Optional[int]]] = set()
            for requirement in requirements:
                outline_id = requirement.get("outline_id") or requirement.get("chapter_outline_id")
                chapter_num = self._parse_chapter_number(requirement.get("chapter_num") or requirement.get("chapter_number"))
                if chapter_num is None:
                    continue
                key = (str(outline_id) if outline_id else None, chapter_num)
                if key in seen_chapters:
                    continue
                seen_chapters.add(key)
                readiness = await db.update_chapter_resource_readiness(
                    execution.project_id,
                    outline_id=str(outline_id) if outline_id else None,
                    chapter_num=chapter_num,
                )
                if readiness:
                    readiness_by_chapter[f"{outline_id or 'none'}:{chapter_num}"] = readiness

        persistence_state = {
            "saved_requirement_ids": saved_ids,
            "saved_count": len(saved_ids),
            "readiness_by_chapter": readiness_by_chapter,
            "source": "workflow_resource_requirements",
        }
        get_workflow_state(execution).set_asset_state(
            {"resource_requirement_persistence_state": persistence_state},
            source="workflow_resource_requirement_persistence",
        )
        return persistence_state

    async def _process_node_outputs(
        self,
        node: WorkflowNode,
        output: Dict[str, Any],
        execution: "WorkflowExecution",
        db=None,
    ) -> Dict[str, Any]:
        """
        根据节点的 outputs 配置处理输出数据

        Args:
            node: 工作流节点
            output: 节点输出的原始数据
            execution: 工作流执行实例
            db: 数据库连接

        Returns:
            Dict: 处理后应该保存到上下文的数据
        """
        result = {}

        # 如果节点没有 outputs 配置，默认所有输出都保存到上下文（向后兼容）
        if not node.outputs:
            return output

        for output_config in node.outputs:
            output_name = output_config.name
            target = output_config.target
            key = output_config.key or output_name

            # 从节点输出中获取值
            value = output.get(output_name)

            if value is None:
                logger.debug(f"输出 '{output_name}' 不存在于节点输出中")
                continue

            if target == "context":
                # 保存到上下文
                result[key] = value
                logger.info(f"节点 '{node.label}' 输出 '{key}' 到上下文")

            elif target == "downstream":
                # 标记为下游可用（实际也是保存到上下文）
                result[key] = value
                result[f"_downstream_{key}"] = value
                logger.info(f"节点 '{node.label}' 输出 '{key}' 供下游使用")

            elif target == "database":
                # 保存到数据库
                if output_config.save_to_db and db:
                    await self._save_output_to_database(
                        output_config.db_table or output_name,
                        value,
                        execution.project_id,
                        db,
                        execution=execution,
                    )
                # 同时保存到上下文
                result[key] = value

        return result

    async def _save_output_to_database(
        self,
        table: str,
        data: Any,
        project_id: str,
        db,
        execution: Optional["WorkflowExecution"] = None,
    ):
        """
        保存输出到数据库

        Args:
            table: 数据库表名
            data: 要保存的数据
            project_id: 项目 ID
            db: 数据库连接
            execution: 当前工作流执行，用于上下文/资产状态追踪
        """
        try:
            table_key = str(table or "").strip().lower()

            if table_key == "chapters":
                # 保存章节
                if isinstance(data, dict) and data.get("content"):
                    chapter_record = {
                        "id": data.get("id") or str(uuid.uuid4()),
                        "project_id": project_id,
                        "world_id": data.get("world_id") or (execution.context.get("world_id") if execution else None),
                        "chapter_outline_id": data.get("chapter_outline_id") or (execution.context.get("chapter_outline_id") if execution else None),
                        "title": data.get("title") or (execution.context.get("chapter_title") if execution else "") or "未命名章节",
                        "summary": data.get("summary") or (execution.context.get("chapter_summary") if execution else "") or "",
                        "content": data.get("content", ""),
                        "word_count": data.get("word_count") or len(str(data.get("content", ""))),
                        "status": data.get("status") or "completed",
                        "events": data.get("events", []),
                        "hooks_planted": data.get("hooks_planted", []),
                        "hooks_resolved": data.get("hooks_resolved", []),
                        "main_plot_progress": data.get("main_plot_progress", {}),
                        "reader_scores": data.get("reader_scores", {}),
                        "created_at": data.get("created_at") or datetime.now(),
                        "updated_at": data.get("updated_at") or datetime.now(),
                        "completed_at": data.get("completed_at") or datetime.now(),
                        "deleted_at": data.get("deleted_at"),
                    }
                    from app.services.chapter_document_storage import chapter_document_storage
                    metadata = chapter_document_storage.write_chapter(
                        chapter_id=str(chapter_record["id"]),
                        project_id=chapter_record.get("project_id"),
                        title=chapter_record.get("title") or "未命名章节",
                        content=str(chapter_record.get("content") or ""),
                    )
                    chapter_record.update(metadata)
                    chapter_record["content"] = ""
                    saved_id = await db.save_chapter(chapter_record)
                    if execution:
                        get_workflow_state(execution).set_asset_state(
                            {"saved_chapter_id": saved_id or chapter_record["id"]},
                            source="generic_output_persistence",
                        )
                    logger.info(f"保存章节到本地文档: {chapter_record['title']}")

            elif table_key == "hooks":
                # 保存伏笔：兼容旧 outputs.database 配置，但统一走 HookManager 持久化逻辑
                hooks = data if isinstance(data, list) else [data] if isinstance(data, dict) else []
                if hooks:
                    if execution:
                        await self._save_hooks_from_manager(
                            execution,
                            {"hooks_to_plant": hooks},
                            db,
                            source="generic_output_persistence",
                        )
                    else:
                        saved_count = 0
                        for hook in hooks:
                            if not isinstance(hook, dict):
                                continue
                            title = hook.get("title") or "未命名伏笔"
                            description = hook.get("description") or hook.get("plant_context") or ""
                            duplicate = None
                            if hasattr(db, "find_duplicate_hook"):
                                duplicate = await db.find_duplicate_hook(
                                    project_id,
                                    title,
                                    description,
                                    world_id=hook.get("world_id"),
                                    scope_type=hook.get("scope_type"),
                                )
                            if duplicate:
                                logger.info(f"跳过重复伏笔: {title} -> {duplicate.get('id')}")
                                continue
                            hook_record = {
                                **hook,
                                "id": hook.get("id") or str(uuid.uuid4()),
                                "project_id": project_id,
                                "title": title,
                                "description": description,
                                "hook_type": self._normalize_hook_type(hook.get("hook_type") or hook.get("type")),
                                "status": hook.get("status") or "planted",
                                "priority": self._clamp_hook_priority(hook.get("priority")),
                                "created_at": hook.get("created_at") or datetime.now(),
                            }
                            await db.save_hook(hook_record)
                            saved_count += 1
                        logger.info(f"保存 {saved_count} 个伏笔到数据库")

            elif table_key == "events":
                events = data if isinstance(data, list) else [data] if isinstance(data, dict) else []
                if events:
                    saved_event_ids = []
                    if hasattr(db, "save_event"):
                        for event in events:
                            if not isinstance(event, dict):
                                continue
                            event_record = {
                                **event,
                                "project_id": project_id,
                                "workflow_execution_id": execution.id if execution else event.get("workflow_execution_id"),
                                "workflow_id": execution.workflow_id if execution else event.get("workflow_id"),
                                "source": event.get("source") or "workflow",
                            }
                            saved_event_ids.append(await db.save_event(event_record))
                        logger.info(f"保存 {len(saved_event_ids)} 个事件到数据库")
                    if execution:
                        execution.context.setdefault("generated_events", []).extend(events)
                        execution.context["event_candidates"] = events
                        get_workflow_state(execution).set_asset_state(
                            {
                                "saved_event_ids": saved_event_ids,
                                "event_persistence_state": {
                                    "status": "saved" if saved_event_ids else "context_only",
                                    "saved_event_ids": saved_event_ids,
                                    "count": len(events),
                                    "reason": None if saved_event_ids else "no_database_save_event_method_or_empty_event_payload",
                                },
                            },
                            source="generic_output_persistence",
                        )
                    elif not saved_event_ids:
                        logger.warning("事件输出未落库：数据库对象缺少 save_event，且没有 execution 上下文可记录")

        except Exception as e:
            logger.error(f"保存输出到数据库表 '{table}' 失败: {e}")

    def _build_input_request_payload(
        self,
        node: WorkflowNode,
        execution: WorkflowExecution,
    ) -> Dict[str, Any]:
        config = node.config or {}
        input_key = config.get("input_key") or config.get("key") or f"{node.id}_input"
        return {
            "node_id": node.id,
            "node_type": NodeType.INPUT.value,
            "label": node.label,
            "description": node.description or "",
            "prompt": config.get("prompt") or node.description or "请补充工作流需要的用户输入。",
            "input_key": input_key,
            "input_type": config.get("input_type", "text"),
            "placeholder": config.get("placeholder", "请输入补充要求或修订意见..."),
            "required": config.get("required", True),
            "default_value": config.get("default_value", ""),
        }

    async def submit_user_input(
        self,
        execution_id: str,
        node_id: str,
        value: Any,
        db=None,
        user_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        execution = self._executions.get(execution_id)
        if not execution and db:
            execution = await self._load_execution_from_db(execution_id, db)
            if execution:
                self._executions[execution_id] = execution

        if not execution:
            return {"success": False, "error": "工作流执行不存在"}

        if execution.status != WorkflowStatus.PAUSED:
            return {"success": False, "error": "工作流当前不在等待用户输入状态"}

        node_state = execution.node_states.get(node_id)
        if not node_state:
            return {"success": False, "error": "输入节点不存在"}

        pending_input = execution.context.get("pending_user_input") or {}
        if pending_input.get("node_id") and pending_input.get("node_id") != node_id:
            return {"success": False, "error": "当前等待的不是该输入节点"}

        workflow = await self.get_workflow(execution.workflow_id, db)
        node = next((item for item in workflow.nodes if item.id == node_id), None) if workflow else None
        if not node:
            return {"success": False, "error": "无法加载输入节点定义"}

        request_payload = self._build_input_request_payload(node, execution)
        input_key = request_payload["input_key"]
        required = bool(request_payload.get("required", True))
        if required and (value is None or (isinstance(value, str) and not value.strip())):
            return {"success": False, "error": "用户输入不能为空"}

        submitted_at = datetime.now().isoformat()
        normalized_value = value.strip() if isinstance(value, str) else value
        output = {
            "status": "input_received",
            "user_input": normalized_value,
            input_key: normalized_value,
            "input_key": input_key,
            "submitted_at": submitted_at,
            "submitted_by": user_id,
        }

        node_state.status = NodeStatus.COMPLETED
        node_state.output_data = self._make_json_safe(output)
        node_state.completed_at = datetime.now()
        if node_state.started_at and node_state.completed_at:
            delta = node_state.completed_at - node_state.started_at
            node_state.duration_ms = int(delta.total_seconds() * 1000)

        execution.context[input_key] = normalized_value
        execution.context[f"user_input_{input_key}"] = normalized_value
        execution.context["latest_user_input"] = normalized_value
        execution.context["user_feedback"] = normalized_value
        execution.context.pop("pending_user_input", None)
        execution.status = WorkflowStatus.RUNNING
        execution.cancel_requested = False

        if db:
            processed_output = await self._process_node_outputs(node, node_state.output_data, execution, db)
            execution.context.update(self._make_json_safe(processed_output))
            await self._save_execution_to_db(execution, db)

        await self._broadcast_status(execution.id, "user_input_received", {
            "node_id": node.id,
            "node_type": NodeType.INPUT.value,
            "label": node.label,
            "input_key": input_key,
        })
        await self._broadcast_status(execution.id, "node_completed", {
            "node_id": node.id,
            "node_type": NodeType.INPUT.value,
            "label": node.label,
            "status": node_state.status.value,
            "input": node_state.input_data,
            "output": node_state.output_data,
            "context_updates": [input_key, f"user_input_{input_key}", "latest_user_input", "user_feedback"],
            "duration_ms": node_state.duration_ms,
            "error": node_state.error,
        })

        input_event = self._input_events.get(execution.id)
        has_waiting_runner = False
        if input_event:
            active_task = self._running_tasks.get(execution.id)
            has_waiting_runner = bool(active_task and not active_task.done())
            input_event.set()

        workflow = workflow or await self.get_workflow(execution.workflow_id, db)
        if workflow and not has_waiting_runner:
            self._start_workflow_task(execution.id, workflow, db)

        return {
            "success": True,
            "message": "用户输入已提交",
            "execution_id": execution.id,
            "node_id": node.id,
            "input_key": input_key,
        }

    async def _execute_node(
        self,
        execution: WorkflowExecution,
        node: WorkflowNode,
        db=None,
    ):
        """执行单个节点"""
        node_state = execution.node_states[node.id]
        node_state.status = NodeStatus.RUNNING
        node_state.started_at = datetime.now()

        # ========== 兼容性修正：根据 ID/label 识别开始/结束节点 ==========
        actual_node_type = node.node_type
        if node.id == "start" or node.label in ["开始", "Start", "start"]:
            actual_node_type = NodeType.START
            logger.debug(f"节点 {node.id} 识别为开始节点")
        elif node.id == "end" or node.label in ["结束", "End", "end"]:
            actual_node_type = NodeType.END
            logger.debug(f"节点 {node.id} 识别为结束节点")

        prepared_context: Optional[Dict[str, Any]] = None
        context_updates: List[str] = []
        output_contract: Optional[AgentOutputContract] = None
        agent_response: Optional[AgentResponse] = None

        trace_service = get_trace_service(db)
        trace_tokens = TraceService.set_context(execution.trace_id, None)
        node_span_id: Optional[str] = None
        if db and execution.trace_id and settings.trace_enabled:
            node_span_id = await db.create_trace_span({
                "trace_id": execution.trace_id,
                "name": f"node.{node.agent_type or node.id}",
                "kind": "node",
                "workflow_id": execution.workflow_id,
                "workflow_execution_id": execution.id,
                "node_id": node.id,
                "agent_type": node.agent_type,
                "attributes": {
                    "node_id": node.id,
                    "node_type": actual_node_type.value,
                    "label": node.label,
                    "agent_type": node.agent_type,
                },
            })
            TraceService.reset_context(trace_tokens)
            trace_tokens = TraceService.set_context(execution.trace_id, node_span_id)

        # ========== 根据节点 inputs 配置准备输入数据 ==========
        # 如果节点有 inputs 配置，使用新逻辑；否则保持原有行为（向后兼容）
        if node.inputs:
            prepared_context = await self._prepare_node_inputs(node, execution, db)
            execution.context.update(prepared_context)
            logger.info(f"节点 '{node.label}' 根据 inputs 配置准备了 {len(node.inputs)} 个输入")

        node_state.input_data = self._build_node_input_snapshot(node, execution, prepared_context)
        if db:
            await self._save_execution_to_db(execution, db)
        await trace_service.record_event("node_started", {
            "node_id": node.id,
            "node_type": actual_node_type.value,
            "label": node.label,
            "agent_type": node.agent_type,
        })
        await trace_service.record_artifact("node_input", content=node_state.input_data)

        # 广播节点开始
        broadcast_data = {
            "node_id": node.id,
            "node_type": actual_node_type.value,
            "label": node.label,
            "input": node_state.input_data,
        }
        # 如果是 Agent 节点，添加 agent_type
        if actual_node_type == NodeType.AGENT and node.agent_type:
            broadcast_data["agent_type"] = node.agent_type
        await self._broadcast_status(execution.id, "node_started", broadcast_data)

        try:
            output: Any = {}

            if actual_node_type == NodeType.START:
                # 开始节点：加载基础上下文并传递给后续节点
                logger.info(f"执行开始节点: {node.id}")
                output = await self._execute_start_node(execution, db)

            elif actual_node_type == NodeType.END:
                # 结束节点：直接通过
                logger.info(f"执行结束节点: {node.id}")
                output = {"status": "completed"}

            elif actual_node_type == NodeType.AGENT:
                # Agent节点：调用 Agent
                output, agent_response, output_contract = await self._execute_agent_node(
                    node,
                    execution,
                    execution.project_id,
                    db,
                )
                output, output_contract = self._apply_node_output_contract(
                    node,
                    output,
                    response=agent_response,
                )
                if agent_response and agent_response.metadata:
                    output = self._attach_prompt_render_trace_metadata(
                        output,
                        agent_response.metadata.get("prompt_render_trace"),
                        agent_response.metadata.get("config_prompt_source", "agent_template_runtime"),
                    )

            elif node.node_type == NodeType.CONDITION:
                # 条件节点：评估条件
                output = await self._execute_condition_node(node, execution, db)

            elif node.node_type == NodeType.GROUP_DISCUSSION:
                # 集体讨论节点：创作会议模式
                output = await self._execute_group_discussion_node(node, execution, db)

            elif node.node_type == NodeType.SCENE_PERFORMANCE:
                # 场景演绎节点：多角色同台飙戏
                output = await self._execute_scene_performance_node(node, execution, db)

            elif node.node_type == NodeType.PARALLEL:
                # 并行节点：标记并行执行点
                output = await self._execute_parallel_node(node, execution, db)

            elif node.node_type == NodeType.INPUT:
                request_payload = self._build_input_request_payload(node, execution)
                execution.context["pending_user_input"] = request_payload
                execution.status = WorkflowStatus.PAUSED
                node_state.status = NodeStatus.RUNNING
                node_state.output_data = {"status": "waiting_for_input", **request_payload}
                if db:
                    await self._save_execution_to_db(execution, db)
                await self._broadcast_status(execution.id, "user_input_required", request_payload)
                await trace_service.record_event("user_input_required", request_payload)
                input_event = self._input_events.setdefault(execution.id, asyncio.Event())
                input_event.clear()
                await input_event.wait()
                return

            safe_output = self._make_json_safe(output)
            state = get_workflow_state(execution)
            state.record_node_output(node.id, safe_output, source="node_completed")

            # 更新状态
            node_state.status = NodeStatus.COMPLETED
            node_state.output_data = safe_output
            node_state.completed_at = datetime.now()

            if output_contract:
                contract_metadata = self._build_contract_metadata(output_contract, agent_response)
                node_state.output_contract_id = contract_metadata.get("output_contract_id")
                node_state.output_mode = output_contract.mode
                node_state.output_schema_name = contract_metadata.get("output_schema_name")
                node_state.output_schema_version = contract_metadata.get("output_schema_version")

            if node_state.started_at and node_state.completed_at:
                delta = node_state.completed_at - node_state.started_at
                node_state.duration_ms = int(delta.total_seconds() * 1000)

            if actual_node_type == NodeType.CONDITION and isinstance(safe_output, dict) and "quality_passed" in safe_output:
                execution.context["evaluation_passed"] = safe_output["quality_passed"]

            resource_requirement_updates = self._normalize_workflow_resource_requirements(
                safe_output,
                execution,
                node,
            )
            if resource_requirement_updates and db:
                persisted_state = await self._persist_workflow_resource_requirements(
                    resource_requirement_updates.get("latest_resource_requirements", []),
                    execution,
                    db,
                )
                if persisted_state:
                    resource_requirement_updates["resource_requirement_persistence_state"] = persisted_state

            # ========== 根据节点 outputs 配置处理输出 ==========
            if node.outputs:
                # 使用配置处理输出
                processed_output = await self._process_node_outputs(node, safe_output, execution, db)
                processed_output = self._make_json_safe(processed_output)
                if resource_requirement_updates:
                    processed_output.update(self._make_json_safe(resource_requirement_updates))
                state_update = get_workflow_state(execution).merge_runtime_state(
                    processed_output,
                    source=f"node_outputs:{node.id}",
                )
                context_updates = list(state_update.get("allowed_updates", {}).keys())
                logger.info(f"节点 '{node.label}' 根据 outputs 配置处理了 {len(node.outputs)} 个输出")
            elif isinstance(safe_output, dict):
                # 向后兼容：输出写入运行期状态，保护 canonical/retrieved 状态不被普通节点覆盖
                runtime_output = dict(safe_output)
                if resource_requirement_updates:
                    runtime_output.update(self._make_json_safe(resource_requirement_updates))
                state_update = get_workflow_state(execution).merge_runtime_state(
                    runtime_output,
                    source=f"node_output:{node.id}",
                )
                context_updates = list(state_update.get("allowed_updates", {}).keys())
            elif safe_output is not None:
                default_output_key = f"{node.id}_output"
                get_workflow_state(execution).merge_runtime_state(
                    {default_output_key: safe_output},
                    source=f"node_output:{node.id}",
                )
                context_updates = [default_output_key]

        except Exception as e:
            logger.error(f"节点执行失败: {node.id} - {e}")
            node_state.status = NodeStatus.FAILED
            node_state.error = str(e)
            node_state.completed_at = datetime.now()
            if node_state.started_at and node_state.completed_at:
                delta = node_state.completed_at - node_state.started_at
                node_state.duration_ms = int(delta.total_seconds() * 1000)

        # 广播节点完成
        completed_data = {
            "node_id": node.id,
            "node_type": actual_node_type.value,
            "label": node.label,
            "status": node_state.status.value,
            "input": node_state.input_data,
            "output": node_state.output_data,
            "output_data": node_state.output_data,
            "context_updates": context_updates,
            "duration_ms": node_state.duration_ms,
            "error": node_state.error,
            "output_contract_id": node_state.output_contract_id,
            "output_mode": node_state.output_mode.value if node_state.output_mode else None,
            "output_schema_name": node_state.output_schema_name,
            "output_schema_version": node_state.output_schema_version,
        }
        # 如果是 Agent 节点，添加 agent_type
        if actual_node_type == NodeType.AGENT and node.agent_type:
            completed_data["agent_type"] = node.agent_type
        if db:
            await self._save_execution_to_db(execution, db)
        if node_state.status == NodeStatus.FAILED:
            failure_payload = self._build_node_failure_event_payload(
                execution,
                node,
                node_state,
                node_type=actual_node_type,
            )
            await trace_service.record_event("node_failed", {
                "node_id": node.id,
                "node_type": actual_node_type.value,
                "label": node.label,
                "error": node_state.error,
            }, severity="error")
            if db and node_span_id:
                await db.finish_trace_span(node_span_id, "failed", error=node_state.error)
            await self._broadcast_status(execution.id, "node_failed", failure_payload)
        else:
            await trace_service.record_event("node_completed", {
                "node_id": node.id,
                "node_type": actual_node_type.value,
                "label": node.label,
                "status": node_state.status.value,
                "context_updates": context_updates,
                "duration_ms": node_state.duration_ms,
            })
            await trace_service.record_artifact("node_output", content=node_state.output_data)
            if db and node_span_id:
                await db.finish_trace_span(node_span_id, "completed", attributes={"duration_ms": node_state.duration_ms})
        TraceService.reset_context(trace_tokens)
        await self._broadcast_status(execution.id, "node_completed", completed_data)
    async def _execute_start_node(
        self,
        execution: "WorkflowExecution",
        db=None,
    ) -> Dict[str, Any]:
        """
        执行开始节点：加载基础上下文

        加载项目的基础信息并传递给后续节点：
        - 世界观设定（world_info）
        - 项目信息（project_info）
        - 前文章节（previous_chapters）
        - 角色列表（characters）
        - 设定条目（lore_entries）
        - 伏笔列表（hooks）

        Args:
            execution: 工作流执行实例
            db: 数据库连接

        Returns:
            Dict: 包含所有基础上下文的输出
        """
        output = {"status": "started"}
        project_id = execution.project_id

        if not db:
            logger.warning("开始节点：数据库连接不存在，无法加载基础上下文")
            return output

        logger.info(f"开始节点加载基础上下文，项目ID: {project_id}")

        try:
            # ========== 1. 加载项目信息 ==========
            project = await db.get_project(project_id) if hasattr(db, 'get_project') else None
            if project:
                output["project_info"] = {
                    "id": project.get("id", project_id),
                    "title": project.get("title", ""),
                    "description": project.get("description", ""),
                    "initial_plot": project.get("initial_plot", ""),
                    "world_type": project.get("world_type", "奇幻"),
                    "tone": project.get("tone", "正剧"),
                }
                # 同时保存到执行上下文
                execution.context["project_info"] = output["project_info"]
                logger.info(f"加载项目信息: {project.get('title', '未知')}")

            # ========== 2. 加载世界观设定 ==========
            world_id = project.get("world_id") if project else None
            if not world_id:
                # 尝试从项目的世界列表获取
                worlds = await db.get_worlds_by_project(project_id) if hasattr(db, 'get_worlds_by_project') else []
                if worlds:
                    world_id = worlds[0].get("id")

            if world_id:
                world = await db.get_world(world_id) if hasattr(db, 'get_world') else None
                if world:
                    output["world_info"] = {
                        "id": world.get("id", ""),
                        "name": world.get("name", "未知世界"),
                        "world_type": world.get("world_type", "奇幻"),
                        "description": world.get("description", ""),
                        "background": world.get("background", ""),
                        "rules": world.get("rules", {}),
                        "themes": world.get("themes", []),
                        "tone": world.get("tone", "正剧"),
                        "target_audience": world.get("target_audience", "大众"),
                    }
                    execution.context["world_info"] = output["world_info"]
                    logger.info(f"加载世界观设定: {world.get('name', '未知')} ({world.get('world_type', '奇幻')})")

            # ========== 3. 加载角色列表 ==========
            characters = await db.get_all_characters(project_id) if hasattr(db, 'get_all_characters') else []
            if characters:
                output["characters"] = characters
                execution.context["characters"] = characters
                logger.info(f"加载 {len(characters)} 个角色")

            # ========== 4. 加载前文章节 ==========
            chapters = await db.get_chapters_by_project(project_id) if hasattr(db, 'get_chapters_by_project') else []
            if chapters:
                # 提取章节作为参考
                output["previous_chapters"] = chapters
                output["all_chapters"] = chapters
                execution.context["previous_chapters"] = chapters
                execution.context["all_chapters"] = chapters

                # 提取章节概要
                chapter_summaries = [
                    {"chapter_num": i+1, "title": c.get("title", ""), "summary": c.get("summary", "")}
                    for i, c in enumerate(chapters)
                ]
                output["chapter_summaries"] = chapter_summaries
                execution.context["chapter_summaries"] = chapter_summaries

                # 最近章节的风格参考
                if chapters:
                    last_chapter = chapters[-1]
                    output["previous_style"] = last_chapter.get("content", "")
                    execution.context["previous_style"] = output["previous_style"]

                logger.info(f"加载 {len(chapters)} 个章节")

            # ========== 5. 加载设定条目 ==========
            try:
                lores = await db.execute_query(
                    "SELECT * FROM lore_entries WHERE project_id = CAST(:project_id AS UUID) ORDER BY priority, created_at DESC",
                    {"project_id": project_id}
                ) if hasattr(db, 'execute_query') else []
                if lores:
                    output["lore_entries"] = lores
                    execution.context["lore_entries"] = lores
                    logger.info(f"加载 {len(lores)} 个设定条目")
            except Exception as e:
                logger.warning(f"加载设定条目失败: {e}")

            # ========== 6. 加载伏笔列表 ==========
            hooks = await db.get_hooks(project_id) if hasattr(db, 'get_hooks') else []
            if hooks:
                output["hooks"] = hooks
                output["existing_hooks"] = hooks
                execution.context["existing_hooks"] = hooks
                logger.info(f"加载 {len(hooks)} 个伏笔")

            # ========== 7. 加载事件列表 ==========
            events = await db.get_events(project_id) if hasattr(db, 'get_events') else []
            if events:
                output["events"] = events
                execution.context["events"] = events
                logger.info(f"加载 {len(events)} 个事件")

            # ========== 8. 加载地点列表 ==========
            locations = await db.get_locations(project_id) if hasattr(db, 'get_locations') else []
            if locations:
                output["locations"] = locations
                execution.context["locations"] = locations
                logger.info(f"加载 {len(locations)} 个地点")

            # ========== 9. 处理用户反馈（重试场景）==========
            user_feedback = execution.context.get("user_feedback")
            if user_feedback:
                output["user_feedback"] = user_feedback
                output["is_retry"] = execution.context.get("is_retry", False)
                output["retry_count"] = execution.context.get("retry_count", 0)
                output["user_feedback_timestamp"] = execution.context.get("user_feedback_timestamp")
                logger.info(f"检测到用户反馈（重试 {output.get('retry_count', 0)} 次）: {user_feedback}")

            # 记录加载完成
            loaded_items = [k for k in output.keys() if k != "status"]
            logger.info(f"开始节点完成，加载了 {len(loaded_items)} 项基础上下文: {loaded_items}")

        except Exception as e:
            logger.error(f"开始节点加载基础上下文失败: {e}")
            import traceback
            logger.error(traceback.format_exc())

        return output

    async def _get_agent_runtime_state(
        self,
        project_id: str,
        agent_type: str,
        scenario: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """获取项目级 Agent 运行时状态。"""
        try:
            from app.api.app import postgres_db

            if not postgres_db or not project_id:
                return None

            config_service = get_agent_config_service()
            return await config_service.resolve_agent_runtime_state(project_id, agent_type, scenario)
        except Exception as e:
            logger.warning(
                f"读取 Agent 运行时状态失败: project={project_id}, agent={agent_type}, "
                f"scenario={scenario or 'default'}, error={e}"
            )
            return None

    def _resolve_agent_node_scenario(
        self,
        node: WorkflowNode,
        profile: Any,
    ) -> Optional[str]:
        """从节点配置或执行 profile 推导 Agent 场景。"""
        node_config = node.config or {}
        configured_scenario = node_config.get("scenario") or node_config.get("agent_scenario")
        if configured_scenario:
            return str(configured_scenario)

        if profile and isinstance(getattr(profile, "metadata", None), dict):
            profile_scenario = profile.metadata.get("scenario")
            if profile_scenario:
                return str(profile_scenario)

        return None

    def _coerce_graph_context_bool(self, value: Any, default: bool = False) -> bool:
        if value is None:
            return default
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"1", "true", "yes", "on"}:
                return True
            if normalized in {"0", "false", "no", "off"}:
                return False
        return bool(value)

    def _get_node_graph_context_policy(
        self,
        node: WorkflowNode,
        profile: Any,
        execution: "WorkflowExecution",
    ) -> Optional[Dict[str, Any]]:
        """合并执行请求、profile 和节点配置中的图上下文策略。"""
        request = execution.context.get("graph_context_request") or {}
        if not isinstance(request, dict):
            return None

        profile_policy: Dict[str, Any] = {}
        if profile and isinstance(getattr(profile, "metadata", None), dict):
            raw_profile_policy = profile.metadata.get("graph_context")
            if isinstance(raw_profile_policy, dict):
                profile_policy = raw_profile_policy

        node_policy: Dict[str, Any] = {}
        raw_node_policy = (node.config or {}).get("graph_context")
        if isinstance(raw_node_policy, dict):
            node_policy = raw_node_policy

        node_enabled = self._coerce_graph_context_bool(node_policy.get("enabled"), False)
        request_enabled = self._coerce_graph_context_bool(request.get("enabled"), False)
        profile_supported = self._coerce_graph_context_bool(profile_policy.get("enabled"), False)

        if not (profile_supported or node_enabled):
            return None
        if not (request_enabled or node_enabled):
            return None

        policy = {**profile_policy, **request, **node_policy}
        policy["enabled"] = True
        policy["max_nodes"] = int(policy.get("max_nodes") or profile_policy.get("max_nodes") or 16)
        policy["depth"] = int(policy.get("depth") or 1)
        policy["include_world"] = self._coerce_graph_context_bool(policy.get("include_world"), True)
        policy["include_region"] = self._coerce_graph_context_bool(policy.get("include_region"), True)
        policy["include_hooks"] = self._coerce_graph_context_bool(policy.get("include_hooks"), True)
        policy["allow_fallback"] = self._coerce_graph_context_bool(policy.get("allow_fallback"), True)
        policy["source"] = policy.get("source") or "auto"
        policy["anchor_type"] = policy.get("anchor_type") or "character"
        return policy

    def _extract_graph_context_anchor_id(self, policy: Dict[str, Any], context: Dict[str, Any]) -> Optional[str]:
        """从请求和节点上下文中推导局部图 anchor。"""
        for key in ("anchor_id", "character_id"):
            value = policy.get(key) or context.get(key)
            if value:
                return str(value)

        selected = context.get("selected_characters")
        selected_list = selected if isinstance(selected, list) else []
        if len(selected_list) == 1:
            item = selected_list[0]
            if isinstance(item, dict):
                value = item.get("id") or item.get("character_id")
                if value:
                    return str(value)
            elif item:
                return str(item)

        characters = context.get("characters")
        character_list = characters if isinstance(characters, list) else []
        if len(character_list) == 1:
            item = character_list[0]
            if isinstance(item, dict):
                value = item.get("id") or item.get("character_id")
                if value:
                    return str(value)
        return None

    def _compact_graph_context(self, graph_context: Dict[str, Any], max_nodes: int = 16) -> Dict[str, Any]:
        """把 GraphContextResponse 裁剪成可安全进入 prompt 的小摘要。"""
        if not isinstance(graph_context, dict):
            return {}

        anchor = graph_context.get("anchor") if isinstance(graph_context.get("anchor"), dict) else None
        nodes = graph_context.get("nodes") if isinstance(graph_context.get("nodes"), list) else []
        edges = graph_context.get("edges") if isinstance(graph_context.get("edges"), list) else []
        relationships = graph_context.get("relationships") if isinstance(graph_context.get("relationships"), list) else []
        limit = max(1, min(int(max_nodes or 16), 24))

        compact_anchor = None
        if anchor:
            compact_anchor = {
                key: anchor.get(key)
                for key in ("id", "type", "name", "summary")
                if anchor.get(key) not in (None, "")
            }

        compact_nodes = []
        for node in nodes[:limit]:
            if not isinstance(node, dict):
                continue
            compact_nodes.append({
                key: node.get(key)
                for key in ("id", "type", "name", "summary")
                if node.get(key) not in (None, "")
            })

        compact_edges = []
        for edge in edges[:limit]:
            if not isinstance(edge, dict):
                continue
            compact_edges.append({
                key: edge.get(key)
                for key in ("source", "target", "type", "label")
                if edge.get(key) not in (None, "")
            })

        compact_relationships = []
        for relationship in relationships[: min(limit, 8)]:
            if not isinstance(relationship, dict):
                continue
            compact_relationships.append({
                key: relationship.get(key)
                for key in ("target_id", "target_name", "type", "strength", "source")
                if relationship.get(key) not in (None, "")
            })

        compact = {
            "source": graph_context.get("source"),
            "partial": bool(graph_context.get("partial", False)),
            "warnings": list(graph_context.get("warnings") or [])[:3],
            "summary": graph_context.get("summary") or "",
            "anchor": compact_anchor,
            "nodes": compact_nodes,
            "edges": compact_edges,
            "relationships": compact_relationships,
        }
        if not any([compact.get("summary"), compact_anchor, compact_nodes, compact_edges, compact_relationships]):
            return {}
        return compact

    async def _maybe_attach_graph_context(
        self,
        node: WorkflowNode,
        execution: "WorkflowExecution",
        db,
        context: Dict[str, Any],
        profile: Any,
    ) -> Dict[str, Any]:
        """按节点策略加载局部关系图，并只向节点上下文附加 compact 版本。"""
        policy = self._get_node_graph_context_policy(node, profile, execution)
        if not policy:
            return context

        if not db:
            context["graph_context_warnings"] = ["数据库连接不存在，跳过关系图上下文"]
            return context

        anchor_id = self._extract_graph_context_anchor_id(policy, context)
        if not anchor_id:
            warning = "graph_context 已启用但无法推导 anchor_id，跳过关系图上下文"
            context["graph_context_warnings"] = [warning]
            execution.context["graph_context_warnings"] = [warning]
            logger.warning(warning)
            return context

        try:
            from app.api.app import nebula_db
            from app.models.graph_context import GraphContextOptions, GraphContextSource
            from app.services.graph_context_service import GraphContextService

            trace_service = get_trace_service(db)
            await trace_service.record_event("graph_context_requested", {
                "node_id": node.id,
                "anchor_type": policy.get("anchor_type") or "character",
                "anchor_id": anchor_id,
                "source": policy.get("source") or "auto",
                "world_id": policy.get("world_id") or context.get("world_id") or execution.context.get("world_id"),
            })

            options = GraphContextOptions(
                depth=max(1, min(int(policy.get("depth") or 1), 2)),
                max_nodes=max(1, min(int(policy.get("max_nodes") or 16), 100)),
                include_world=self._coerce_graph_context_bool(policy.get("include_world"), True),
                include_region=self._coerce_graph_context_bool(policy.get("include_region"), True),
                include_hooks=self._coerce_graph_context_bool(policy.get("include_hooks"), True),
                world_id=str(policy.get("world_id") or context.get("world_id") or execution.context.get("world_id")) if (policy.get("world_id") or context.get("world_id") or execution.context.get("world_id")) else None,
                include_inherited=self._coerce_graph_context_bool(policy.get("include_inherited"), True),
                allow_fallback=self._coerce_graph_context_bool(policy.get("allow_fallback"), True),
                source=GraphContextSource(policy.get("source") or "auto"),
            )
            graph_service = GraphContextService(db, nebula_db)
            graph_context = await graph_service.get_local_graph_context(
                policy.get("anchor_type") or "character",
                anchor_id,
                project_id=execution.project_id,
                options=options,
            )
            graph_context_data = graph_context.model_dump(mode="json")
            await trace_service.record_event("graph_context_loaded", {
                "node_id": node.id,
                "anchor_type": policy.get("anchor_type") or "character",
                "anchor_id": anchor_id,
                "source": graph_context_data.get("source"),
                "node_count": len(graph_context_data.get("nodes") or []),
                "edge_count": len(graph_context_data.get("edges") or []),
                "relationship_count": len(graph_context_data.get("relationships") or []),
                "partial": bool(graph_context_data.get("partial", False)),
                "warnings": graph_context_data.get("warnings") or [],
                "world_id": graph_context_data.get("metadata", {}).get("world_id"),
            })
            compact = self._compact_graph_context(graph_context_data, max_nodes=options.max_nodes)
            execution.context["graph_context_candidate"] = graph_context_data
            if not compact:
                warnings = list(graph_context_data.get("warnings") or [])
                warnings.append("关系图上下文为空，未注入 prompt")
                context["graph_context_warnings"] = warnings[:3]
                execution.context["graph_context_warnings"] = warnings[:3]
                return context

            context["graph_context"] = compact
            context["graph_context_summary"] = compact.get("summary", "")
            context["graph_context_source"] = compact.get("source")
            context["graph_context_warnings"] = compact.get("warnings", [])
            await trace_service.record_event("graph_context_compacted", {
                "node_id": node.id,
                "source": compact.get("source"),
                "node_count": len(compact.get("nodes") or []),
                "edge_count": len(compact.get("edges") or []),
                "relationship_count": len(compact.get("relationships") or []),
                "partial": bool(compact.get("partial", False)),
                "warnings": compact.get("warnings") or [],
            })
            await trace_service.record_artifact("graph_context", content=compact)
            await trace_service.record_event("graph_context_attached_to_prompt", {
                "node_id": node.id,
                "source": compact.get("source"),
                "summary_chars": len(compact.get("summary") or ""),
            })
            execution.context.update({
                "graph_context": compact,
                "graph_context_summary": compact.get("summary", ""),
                "graph_context_source": compact.get("source"),
                "graph_context_warnings": compact.get("warnings", []),
            })
            return context
        except Exception as e:
            warning = f"加载关系图上下文失败，已跳过: {e}"
            context["graph_context_warnings"] = [warning]
            execution.context["graph_context_warnings"] = [warning]
            logger.warning(warning)
            try:
                trace_service = get_trace_service(db)
                await trace_service.record_event("graph_context_failed", {
                    "node_id": node.id,
                    "anchor_id": anchor_id,
                    "error": str(e),
                }, severity="warning")
            except Exception:
                pass
            return context

    async def _execute_agent_node(
        self,
        node: WorkflowNode,
        execution: "WorkflowExecution",
        project_id: str,
        db=None,
    ) -> tuple[Any, Optional[AgentResponse], Optional[AgentOutputContract]]:
        """执行 Agent 节点（支持 runtime 禁用校验、adapter 和实时干预）。"""
        profile = get_workflow_node_profile(node.agent_type)
        resolved_agent_type = profile.agent_type if profile else (node.agent_type or "")
        resolved_scenario = self._resolve_agent_node_scenario(node, profile)
        adapter = get_workflow_node_adapter(resolved_agent_type)

        logger.info(
            f"请求 Agent: type={node.agent_type}, resolved={resolved_agent_type}, "
            f"scenario={resolved_scenario or 'default'}, "
            f"label={node.label}, node_id={node.id}, project_id={project_id}"
        )

        context = execution.context.copy()
        enrichment_required = resolved_agent_type in [
            "writer",
            "evaluator",
            "master_plotter",
            "plotter",
            "setting",
            "hook_manager",
            "procgen",
            "proc_gen",
            "world_map_manager",
            "event_generator",
            "dungeon_generator",
        ]
        if enrichment_required or not node.inputs:
            enhanced_context = await self._load_agent_context(resolved_agent_type, execution, db)
            for key, value in enhanced_context.items():
                if key not in context or context[key] is None:
                    context[key] = value

        context["_resolved_agent_type"] = resolved_agent_type
        if resolved_scenario:
            context["scenario"] = resolved_scenario
            context["agent_scenario"] = resolved_scenario

        if resolved_agent_type == "writer":
            if context.get("is_retry") and not context.get("task_type"):
                context["task_type"] = "rewrite_by_review"
            if context.get("is_retry"):
                node_config = node.config or {}
                if not node_config.get("scenario") and not node_config.get("agent_scenario"):
                    context["agent_scenario"] = "rewrite_by_review"
                    context["scenario"] = "rewrite_by_review"

            canonical_target = (
                context.get("target_word_count")
                or context.get("chapter_target_word_count")
                or self._ensure_context_dict(context.get("chapter_outline")).get("target_word_count")
                or context.get("word_count")
                or 2000
            )
            context["target_word_count"] = canonical_target
            context["chapter_target_word_count"] = canonical_target
            context["word_count"] = canonical_target

        if resolved_agent_type in {"writer", "evaluator", "master_plotter", "plotter"}:
            self._attach_upcoming_outline_context(context)

        if resolved_agent_type in {"master_plotter", "plotter"} and context.get("chapter_outline"):
            context.setdefault("task", "prepare_writing_plan")

        execution.context.update(context)
        logger.info(
            f"Agent '{resolved_agent_type}' 使用状态化上下文，包含 {len(context)} 个字段"
        )

        context = await self._maybe_attach_graph_context(node, execution, db, context, profile)

        pending_interventions = await self.get_pending_interventions(
            execution.id,
            agent_type=node.agent_type,
        )

        if pending_interventions:
            logger.info(f"Agent {resolved_agent_type} 收到 {len(pending_interventions)} 条干预消息")
            intervention_messages = []
            for iv in pending_interventions:
                intervention_messages.append(f"[用户干预] {iv['message']}")
                await self.mark_intervention_processed(execution.id, iv["id"])

            context["interventions"] = intervention_messages
            context["user_guidance"] = "\n".join(intervention_messages)
            execution.context["interventions"] = intervention_messages
            execution.context["user_guidance"] = context["user_guidance"]

            await self._broadcast_status(execution.id, "intervention_applied", {
                "agent": node.agent_type,
                "node_id": node.id,
                "intervention_count": len(pending_interventions),
                "messages": intervention_messages,
            })

        runtime_state = await self._get_agent_runtime_state(project_id, resolved_agent_type, resolved_scenario)
        if runtime_state and runtime_state.get("enabled") is False:
            reason = runtime_state.get("reason", "Agent 已禁用")
            logger.info(
                f"跳过 Agent 节点: type={resolved_agent_type}, scenario={resolved_scenario or 'default'}, "
                f"node_id={node.id}, reason={reason}"
            )
            prompt_trace = await self._build_workflow_node_prompt_trace(
                resolved_agent_type,
                project_id,
                resolved_scenario,
                context,
            )
            skipped_output = {
                "skipped": True,
                "reason": reason,
                "agent_type": resolved_agent_type,
                "scenario": resolved_scenario or "default",
                "node_id": node.id,
            }
            skipped_output = self._attach_prompt_render_trace_metadata(
                skipped_output,
                prompt_trace,
                "agent_disabled",
            )
            return skipped_output, None, None

        if adapter:
            execution.context.update(context)
            await self._capture_effective_agent_input_snapshot(execution, node, resolved_agent_type, resolved_scenario, context, db)
            logger.info(f"节点 '{node.label}' 使用 workflow adapter 执行: {resolved_agent_type}")
            prompt_trace = await self._build_workflow_node_prompt_trace(
                resolved_agent_type,
                project_id,
                resolved_scenario,
                context,
            )
            adapter_output = await adapter.execute(node, execution, db)
            adapter_output = self._attach_prompt_render_trace_metadata(adapter_output, prompt_trace)
            return adapter_output, None, None

        if not self._agent_provider:
            raise ValueError("Agent provider 未设置")

        agent = await self._agent_provider(resolved_agent_type, project_id)
        if not agent:
            logger.error(f"无法获取 Agent: {resolved_agent_type}，可用类型请检查 agent_provider 配置")
            raise ValueError(f"无法获取 Agent: {resolved_agent_type}")

        logger.info(f"Agent 实例获取成功: type={resolved_agent_type}, instance_id={id(agent)}")
        return await self._run_agent_execution(agent, context, execution, node, db)

    def _hash_json_payload(self, payload: Any) -> str:
        import hashlib

        serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    def _compact_state_packet_text(self, value: Any, limit: int = 240) -> str:
        text = self._coerce_context_text(value).strip()
        if not text and isinstance(value, (dict, list)):
            try:
                text = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
            except (TypeError, ValueError):
                text = str(value)
        if len(text) > limit:
            return text[: limit - 1] + "…"
        return text

    def _chapter_num_from_record(self, chapter: Dict[str, Any], fallback: int) -> Optional[int]:
        return self._parse_chapter_number(
            chapter.get("chapter_number")
            or chapter.get("chapter_num")
            or chapter.get("number")
            or chapter.get("order")
            or fallback
        )

    def _state_change_sort_key(self, change: Dict[str, Any]) -> tuple:
        timestamp = (
            change.get("applied_at")
            or change.get("confirmed_at")
            or change.get("created_at")
            or ""
        )
        return (str(timestamp), str(change.get("id") or ""))

    def _state_entity_key(self, change: Dict[str, Any]) -> str:
        entity_type = str(change.get("entity_type") or "custom")
        entity_id = change.get("entity_id") or change.get("entity_name") or change.get("id")
        return f"{entity_type}:{entity_id}"

    def _compact_confirmed_state_change(self, change: Dict[str, Any]) -> Dict[str, Any]:
        source_chapter_id = change.get("chapter_id") or self._ensure_context_dict(change.get("metadata")).get("chapter_id")
        return {
            "id": change.get("id"),
            "entity_key": self._state_entity_key(change),
            "entity_type": change.get("entity_type"),
            "entity_id": change.get("entity_id"),
            "entity_name": self._compact_state_packet_text(change.get("entity_name"), 120),
            "change_type": change.get("change_type"),
            "summary": self._compact_state_packet_text(change.get("summary") or change.get("title"), 240),
            "source_chapter_id": source_chapter_id,
            "status": change.get("status"),
            "confirmed_at": self._make_json_safe(change.get("confirmed_at")),
            "applied_at": self._make_json_safe(change.get("applied_at")),
            "created_at": self._make_json_safe(change.get("created_at")),
            "after_state": self._make_json_safe(change.get("after_state") or {}),
        }

    def _merge_state_packet_value(self, current_value: Any, next_value: Any) -> Any:
        if next_value is None:
            return self._make_json_safe(current_value)
        if isinstance(current_value, dict) and isinstance(next_value, dict):
            merged = dict(current_value)
            for key, value in next_value.items():
                merged[key] = self._merge_state_packet_value(merged.get(key), value)
            return merged
        if isinstance(current_value, list) and isinstance(next_value, list):
            merged_list = [self._make_json_safe(item) for item in current_value]
            seen = {json.dumps(item, ensure_ascii=False, sort_keys=True, default=str) for item in merged_list}
            for item in next_value:
                safe_item = self._make_json_safe(item)
                item_key = json.dumps(safe_item, ensure_ascii=False, sort_keys=True, default=str)
                if item_key not in seen:
                    seen.add(item_key)
                    merged_list.append(safe_item)
            return merged_list
        return self._make_json_safe(next_value)

    def _merge_state_packet_payload(self, current_payload: Dict[str, Any], next_payload: Dict[str, Any]) -> Dict[str, Any]:
        merged = dict(current_payload)
        for key, value in (next_payload or {}).items():
            merged[key] = self._merge_state_packet_value(merged.get(key), value)
        return merged

    def _build_confirmed_state_summary(self, changes: List[Dict[str, Any]], *, limit: int) -> List[Dict[str, Any]]:
        grouped: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        for change in changes:
            grouped[self._state_entity_key(change)].append(change)

        summaries: List[Dict[str, Any]] = []
        for entity_key, items in grouped.items():
            ordered = sorted(items, key=self._state_change_sort_key)
            latest = ordered[-1]
            merged_after_state: Dict[str, Any] = {}
            for item in ordered:
                merged_after_state = self._merge_state_packet_payload(merged_after_state, item.get("after_state") or {})
            summaries.append({
                "entity_key": entity_key,
                "entity_type": latest.get("entity_type"),
                "entity_id": latest.get("entity_id"),
                "entity_name": self._compact_state_packet_text(latest.get("entity_name"), 120),
                "latest_change_id": latest.get("id"),
                "latest_status": latest.get("status"),
                "latest_change_type": latest.get("change_type"),
                "latest_summary": self._compact_state_packet_text(latest.get("summary") or latest.get("title"), 240),
                "latest_after_state": self._make_json_safe(merged_after_state),
                "change_count": len(ordered),
                "history_change_ids": [item.get("id") for item in ordered[-5:] if item.get("id")],
            })

        return sorted(
            summaries,
            key=lambda item: (str(item.get("entity_type") or ""), str(item.get("entity_id") or item.get("entity_key") or "")),
        )[:limit]

    async def _load_confirmed_prior_state_packet(
        self,
        project_id: str,
        chapter_num: Optional[int],
        db,
        *,
        limit: int = 20,
    ) -> Dict[str, Any]:
        """Load compact saved/prior accepted state for Writer/Evaluator continuity."""
        packet = {
            "source": {
                "quality_gated_only": True,
                "max_items": limit,
                "prior_chapter_count": 0,
            },
            "prior_chapters": [],
            "confirmed_state_changes": [],
            "confirmed_state_summary": [],
            "open_proposed_changes": [],
            "continuity_notes": [],
        }
        if not db:
            return packet

        prior_chapters: List[Dict[str, Any]] = []
        if hasattr(db, "get_chapters_by_project"):
            try:
                chapters = await db.get_chapters_by_project(project_id, limit=limit * 2)
            except TypeError:
                chapters = await db.get_chapters_by_project(project_id)
            for index, chapter in enumerate(chapters or [], start=1):
                if not isinstance(chapter, dict):
                    continue
                status = chapter.get("status")
                if status != "saved":
                    continue
                record_num = self._chapter_num_from_record(chapter, index)
                if chapter_num is not None and record_num is not None and record_num >= chapter_num:
                    continue
                prior_chapters.append({
                    "chapter_id": chapter.get("id") or chapter.get("chapter_id"),
                    "chapter_number": record_num,
                    "title": self._compact_state_packet_text(chapter.get("title") or chapter.get("chapter_title"), 120),
                    "checksum": chapter.get("content_checksum") or chapter.get("chapter_content_checksum"),
                })
                if len(prior_chapters) >= limit:
                    break
        packet["prior_chapters"] = prior_chapters
        packet["source"]["prior_chapter_count"] = len(prior_chapters)

        if hasattr(db, "list_narrative_state_changes"):
            confirmed_records: List[Dict[str, Any]] = []
            for status in ("applied", "confirmed"):
                fetch_limit = max(limit * 5, limit)
                changes = await db.list_narrative_state_changes(project_id, status=status, limit=fetch_limit)
                for change in changes or []:
                    if isinstance(change, dict):
                        confirmed_records.append(change)
            confirmed_records = sorted(confirmed_records, key=self._state_change_sort_key, reverse=True)
            packet["confirmed_state_changes"] = [
                self._compact_confirmed_state_change(change)
                for change in confirmed_records[:limit]
            ]
            packet["confirmed_state_summary"] = self._build_confirmed_state_summary(confirmed_records, limit=limit)
            packet["source"]["confirmed_state_total"] = len(confirmed_records)
            packet["source"]["confirmed_entity_count"] = len(packet["confirmed_state_summary"])

            proposed_changes = await db.list_narrative_state_changes(project_id, status="proposed", limit=limit)
            packet["open_proposed_changes"] = [
                {
                    "id": change.get("id"),
                    "entity_type": change.get("entity_type"),
                    "summary": self._compact_state_packet_text(change.get("summary") or change.get("title"), 200),
                    "status": change.get("status"),
                }
                for change in (proposed_changes or [])
                if isinstance(change, dict)
            ][:limit]

        return packet

    async def _attach_confirmed_prior_state_packet(
        self,
        context: Dict[str, Any],
        execution: "WorkflowExecution",
        db,
    ) -> None:
        if context.get("confirmed_prior_state_packet"):
            return
        chapter_num = self._parse_chapter_number(context.get("chapter_num") or execution.context.get("chapter_num"))
        packet = await self._load_confirmed_prior_state_packet(execution.project_id, chapter_num, db)
        provenance = {
            "loaded_at": datetime.now().isoformat(),
            "project_id": execution.project_id,
            "chapter_num": chapter_num,
            "prior_chapter_count": len(packet.get("prior_chapters") or []),
            "confirmed_state_count": len(packet.get("confirmed_state_changes") or []),
            "open_proposed_count": len(packet.get("open_proposed_changes") or []),
            "packet_checksum": self._hash_json_payload(packet),
        }
        context["confirmed_prior_state_packet"] = packet
        context["confirmed_prior_state_packet_provenance"] = provenance
        execution.context["confirmed_prior_state_packet"] = packet
        execution.context["confirmed_prior_state_packet_provenance"] = provenance
        await self._broadcast_status(execution.id, "chapter_state_handoff_loaded", {
            "execution_id": execution.id,
            "workflow_id": execution.workflow_id,
            "chapter_num": chapter_num,
            "chapter_number": chapter_num,
            "prior_chapter_count": provenance["prior_chapter_count"],
            "confirmed_state_count": provenance["confirmed_state_count"],
            "pending_count": provenance["open_proposed_count"],
        })

    async def _load_agent_context(
        self,
        agent_type: str,
        execution: "WorkflowExecution",
        db=None,
    ) -> Dict[str, Any]:
        """
        根据 Agent 类型从数据库加载相关数据到上下文

        注意：基础上下文（world_info, characters, previous_chapters 等）
        应该已经在 start 节点加载。此方法主要用于：
        1. 向后兼容（没有 start 节点的工作流）
        2. 为特定 Agent 类型准备特殊格式的输入

        Args:
            agent_type: Agent 类型
            execution: 工作流执行实例
            db: 数据库连接

        Returns:
            Dict: 增强后的上下文
        """
        # 从执行上下文复制基础数据
        context = execution.context.copy()

        # 记录已有上下文状态
        existing_keys = [k for k in ["world_info", "characters", "previous_chapters", "lore_entries", "hooks"]
                         if k in context]
        if existing_keys:
            logger.info(f"Agent '{agent_type}' 上下文已有: {existing_keys}")
        else:
            logger.info(f"Agent '{agent_type}' 上下文为空，将从数据库加载")

        if not db:
            logger.warning("数据库连接不存在，无法加载Agent上下文数据")
            return context

        try:
            project_id = execution.project_id
            data_loaded = False  # 跟踪是否有新数据加载

            # ========== 核心信息：世界观设定（所有 Agent 都需要）==========
            # 如果 start 节点已经加载，这里会跳过
            if "world_info" not in context:
                world_info = await self._load_data_from_database("world_info", project_id, db, context)
                if world_info:
                    context["world_info"] = world_info
                    execution.context["world_info"] = world_info
                    logger.info(f"加载世界观设定（{agent_type}）: {world_info.get('name')} ({world_info.get('world_type')})")

            # ===== 需要角色的 Agent 类型 =====
            character_requiring_agents = ["plotter", "master_plotter", "writer", "character", "evaluator", "hook_manager", "summarizer", "plot_outline"]
            if agent_type in character_requiring_agents:
                if "characters" not in context or not context["characters"]:
                    chars = await db.get_all_characters(project_id)
                    if chars:
                        context["characters"] = chars
                        execution.context["characters"] = chars  # 保存回 execution.context 避免重复加载
                        data_loaded = True
                        logger.info(f"加载 {len(chars)} 个角色到上下文（{agent_type}）")

            # ===== HookManager Agent：需要已有伏笔 =====
            if agent_type == "hook_manager":
                if "existing_hooks" not in context:
                    hooks = await self._load_data_from_database("existing_hooks", project_id, db, context) or []
                    if hooks:
                        context["existing_hooks"] = hooks
                        execution.context["existing_hooks"] = hooks
                        data_loaded = True
                        logger.info(f"加载 {len(hooks)} 个已有伏笔到上下文")

            if agent_type in ["world_map_manager", "event_generator"]:
                context.setdefault("chapter_num", execution.context.get("chapter_num") or execution.context.get("chapter_number"))
                context.setdefault("chapter_number", execution.context.get("chapter_number") or execution.context.get("chapter_num"))
                if execution.context.get("chapter_title") and "chapter_title" not in context:
                    context["chapter_title"] = execution.context.get("chapter_title")
                if execution.context.get("chapter_goal") and "chapter_goal" not in context:
                    context["chapter_goal"] = execution.context.get("chapter_goal")
                if execution.context.get("chapter_summary") and "chapter_summary" not in context:
                    context["chapter_summary"] = execution.context.get("chapter_summary")
                if execution.context.get("chapter_outline") and "chapter_outline" not in context:
                    context["chapter_outline"] = execution.context.get("chapter_outline")
                if execution.context.get("chapter_goals") and "chapter_goals" not in context:
                    context["chapter_goals"] = execution.context.get("chapter_goals")
                if execution.context.get("scene_directions") and "scene_directions" not in context:
                    context["scene_directions"] = execution.context.get("scene_directions")

            if agent_type == "world_map_manager":
                worlds = await db.get_worlds_by_project(project_id) if hasattr(db, 'get_worlds_by_project') else []
                if worlds:
                    world_id = worlds[0].get("id")
                    context.setdefault("world_id", world_id)
                    execution.context.setdefault("world_id", world_id)
                    regions = await db.get_regions_by_world(world_id) if hasattr(db, 'get_regions_by_world') and world_id else []
                    if regions and "existing_regions" not in context:
                        context["existing_regions"] = regions
                        execution.context["existing_regions"] = regions

            # ===== Writer Agent：需要章节历史、伏笔、角色、讨论共识、剧情意图 =====
            if agent_type == "writer":
                await self._attach_confirmed_prior_state_packet(context, execution, db)
                # 已有章节
                if "previous_chapters" not in context:
                    chapters = await self._load_data_from_database("previous_chapters", project_id, db, context) or []
                    if chapters:
                        context["previous_chapters"] = chapters
                        context["all_chapters"] = chapters
                        execution.context["previous_chapters"] = chapters
                        execution.context["all_chapters"] = chapters
                        # 提取最近章节作为风格参考
                        last_chapter = chapters[-1]
                        context["previous_style"] = last_chapter.get("content", "")
                        execution.context["previous_style"] = context["previous_style"]
                        logger.info(f"加载 {len(chapters)} 个章节历史到上下文（writer）")

                # 已有伏笔（需要处理的伏笔）- 转换为 Writer 需要的格式
                if "hooks" not in context:
                    hooks = await self._load_data_from_database("existing_hooks", project_id, db, context) or []
                    if hooks:
                        # 只获取未回收的伏笔
                        pending_hooks = [h for h in hooks if h.get("status") not in ["resolved", "dropped"]]
                        # 转换为 Writer Agent 需要的格式
                        context["hooks"] = [
                            {
                                "id": h.get("id", ""),
                                "type": "plant" if h.get("status") == "pending" else "resolve",
                                "description": h.get("description", h.get("title", "")),
                            }
                            for h in pending_hooks
                        ]
                        context["existing_hooks"] = pending_hooks
                        execution.context["existing_hooks"] = pending_hooks
                        logger.info(f"加载 {len(pending_hooks)} 个待处理伏笔到上下文（writer）")

                # ========== 关键：从剧情规划提取写作意图 ==========
                # 从 chapter_outline 或 chapter_goals 中提取当前章节的写作意图
                raw_chapter_outline = execution.context.get("chapter_outline", {})
                chapter_outline = self._ensure_context_dict(raw_chapter_outline)
                chapter_goals = self._ensure_context_list(execution.context.get("chapter_goals", []))
                plot_outline = self._ensure_context_list(execution.context.get("plot_outline", []))

                # 获取当前章节号
                chapter_num = context.get("chapter_num", 1)

                # 提取写作意图
                intents = []
                if raw_chapter_outline and not chapter_outline:
                    outline_text = self._coerce_context_text(raw_chapter_outline).strip()
                    if outline_text:
                        intents.append(outline_text)
                elif chapter_outline:
                    # 从章节大纲中提取意图
                    current_chapter = chapter_outline.get(str(chapter_num), chapter_outline)
                    if isinstance(current_chapter, dict):
                        if current_chapter.get("goal"):
                            intents.append(current_chapter["goal"])
                        if current_chapter.get("events"):
                            intents.extend(current_chapter["events"])
                        if current_chapter.get("key_points"):
                            intents.extend(current_chapter["key_points"])
                    elif isinstance(current_chapter, str):
                        intents.append(current_chapter)

                if not intents and chapter_goals and len(chapter_goals) >= chapter_num:
                    # 从章节目标中提取
                    goal = chapter_goals[chapter_num - 1]
                    if isinstance(goal, str):
                        intents.append(goal)
                    elif isinstance(goal, dict):
                        if goal.get("goal"):
                            intents.append(goal["goal"])
                        if goal.get("events"):
                            intents.extend(goal["events"])

                if not intents and plot_outline:
                    # 从剧情大纲中提取意图
                    for node in plot_outline:
                        event = self._extract_context_item_text(node, "event", "summary", "description", "content")
                        if event:
                            intents.append(event)

                if intents:
                    context["intents"] = intents
                    logger.info(f"为 Writer 提取 {len(intents)} 条写作意图")

                # ========== 提取写作指导（writing_guide）============
                # 从章节大纲中提取写作指导，供Writer Agent遵循正确的节奏
                writing_guide = None
                if chapter_outline:
                    current_chapter = chapter_outline.get(str(chapter_num), chapter_outline)
                    if isinstance(current_chapter, dict):
                        writing_guide = current_chapter.get("writing_guide")
                if writing_guide:
                    context["writing_guide"] = writing_guide
                    if isinstance(writing_guide, dict):
                        guide_description = writing_guide.get("description", "")
                    else:
                        guide_description = self._coerce_context_text(writing_guide)
                    logger.info(f"为 Writer 加载写作指导: {guide_description}")

                # 提取角色情绪状态（从多个来源合并）
                characters_data = self._ensure_context_list(context.get("characters", []))
                character_states = self._ensure_context_dict(execution.context.get("character_states", {}))
                raw_character_moods = execution.context.get("character_moods", {})
                character_moods = self._ensure_context_dict(raw_character_moods)

                for char in characters_data:
                    if isinstance(char, dict):
                        char_name = char.get("name", "")
                        if char_name and char_name not in character_moods:
                            # 从角色状态获取情绪
                            state = self._ensure_context_dict(character_states.get(char_name, {}))
                            if state.get("mood"):
                                character_moods[char_name] = state["mood"]
                            elif state.get("emotion"):
                                character_moods[char_name] = state["emotion"]
                            elif char.get("personality"):
                                character_moods[char_name] = char["personality"]

                if character_moods:
                    context["character_moods"] = character_moods
                    logger.info(f"为 Writer 提供 {len(character_moods)} 个角色的情绪状态")

                # 提取环境描述（从多个来源）
                environment = ""
                # 1. 从世界数据获取
                world_data = self._ensure_context_dict(execution.context.get("world_data", {}))
                if world_data:
                    current_location = self._ensure_context_dict(world_data.get("current_location", {}))
                    if current_location:
                        environment = current_location.get("description", "")

                # 2. 从当前章节目标获取环境信息
                if not environment:
                    chapter_goal = execution.context.get("chapter_goal", "")
                    if isinstance(chapter_goal, dict):
                        environment = chapter_goal.get("environment", "")
                    elif isinstance(chapter_goal, str) and "环境" in chapter_goal:
                        # 尝试从目标文本中提取环境
                        environment = chapter_goal

                if environment:
                    context["environment"] = environment

                # 讨论共识：从执行上下文获取最近的讨论总结
                discussion_summary = ""
                latest_discussion = execution.context.get("group_discussion", {})
                if isinstance(latest_discussion, dict):
                    discussion_summary = latest_discussion.get("summary", "") or latest_discussion.get("full_content", "")
                    if not discussion_summary:
                        messages = latest_discussion.get("messages", [])
                        if isinstance(messages, list):
                            for message in reversed(messages):
                                if isinstance(message, dict) and message.get("content"):
                                    discussion_summary = message["content"]
                                    break

                if not discussion_summary:
                    discussion_summary = execution.context.get("last_discussion_summary", "")

                if discussion_summary:
                    if "discussion_summary" not in context:
                        context["discussion_summary"] = discussion_summary
                    if "last_discussion_summary" not in context:
                        context["last_discussion_summary"] = discussion_summary

                discussion_assets = execution.context.get("discussion_assets")
                if discussion_assets and "discussion_assets" not in context:
                    context["discussion_assets"] = discussion_assets

                discussion_asset_digest = execution.context.get("discussion_asset_digest")
                if discussion_asset_digest and "discussion_asset_digest" not in context:
                    context["discussion_asset_digest"] = discussion_asset_digest

                persisted_asset_refs = execution.context.get("persisted_asset_refs")
                if persisted_asset_refs and "persisted_asset_refs" not in context:
                    context["persisted_asset_refs"] = persisted_asset_refs

                if execution.context.get("discussion_assets_committed") and "discussion_assets_committed" not in context:
                    context["discussion_assets_committed"] = execution.context.get("discussion_assets_committed")

                # 传递状态化工作流上游产物，Writer 必须能看到大纲、场景演绎、总编剧计划和设定检索结果
                for workflow_key in [
                    "chapter_outline",
                    "chapter_goals",
                    "chapter_summary",
                    "chapter_title",
                    "scene_directions",
                    "performance_result",
                    "role_performance_context",
                    "public_performances",
                    "private_performances",
                    "relationship_deltas",
                    "state_deltas",
                    "continuity_notes",
                    "performance_warnings",
                    "role_performance_gate",
                    "role_performance_gate_passed",
                    "role_performance_gate_blockers",
                    "role_performance_gate_warnings",
                    "resource_requirements",
                    "role_delta_resource_requirements",
                    "pending_resource_requirements",
                    "workflow_resource_requirements",
                    "latest_resource_requirements",
                    "latest_role_delta_resource_requirements",
                    "resource_requirement_persistence_state",
                    "writing_plan",
                    "plot_guidance",
                    "scene_integration_plan",
                    "fixed_lore_entries",
                    "dynamic_lore_entries",
                    "selected_lore_entries",
                    "upcoming_outline_context",
                    "upcoming_outline_policy",
                    "confirmed_prior_state_packet",
                    "confirmed_prior_state_packet_provenance",
                    "node_outputs",
                    "asset_state",
                    "workflow_state",
                ]:
                    if execution.context.get(workflow_key) is not None and workflow_key not in context:
                        context[workflow_key] = execution.context.get(workflow_key)

                if agent_type in {"writer", "master_plotter", "plotter", "evaluator", "summarizer"}:
                    self._attach_role_performance_context(context, execution.context)

                if agent_type in {"writer", "master_plotter", "plotter", "evaluator"}:
                    self._inject_character_constraints(context)

                # ========== 关键：设置字数要求 ==========
                # 从 canonical target 获取目标字数，映射到 Writer 兼容的 word_count
                target_word_count = (
                    execution.context.get("target_word_count")
                    or execution.context.get("chapter_target_word_count")
                    or chapter_outline.get("target_word_count")
                    or 2000
                )
                context["target_word_count"] = target_word_count
                context["chapter_target_word_count"] = target_word_count
                context["word_count"] = target_word_count
                logger.info(f"为 Writer 设置目标字数: {target_word_count}")

                # 记录 Writer Agent 获得的上下文摘要
                logger.info(f"Writer Agent 上下文: intents={len(intents)}, moods={len(character_moods)}, hooks={len(context.get('hooks', []))}")

            # ===== Summarizer Agent：需要章节历史、事件 =====
            if agent_type == "summarizer":
                self._attach_role_performance_context(context, execution.context)
                if "all_chapters" not in context:
                    chapters = await db.get_chapters_by_project(project_id) if hasattr(db, 'get_chapters_by_project') else []
                    if chapters:
                        context["all_chapters"] = chapters
                        execution.context["all_chapters"] = chapters
                        logger.info(f"加载 {len(chapters)} 个章节到摘要上下文（summarizer）")

            # ===== Setting Agent：使用独立的 SettingAgent（与 /lore 界面共享）=====
            # SettingAgent 内部使用 SettingAgentService，自动处理对话历史和记忆
            if agent_type == "setting":
                # 获取世界观设定
                if "world_info" not in context:
                    project = await db.get_project(project_id) if hasattr(db, 'get_project') else None
                    if project and project.get("world_id"):
                        world = await db.get_world(project["world_id"]) if hasattr(db, 'get_world') else None
                        if world:
                            context["world_info"] = {
                                "id": world.get("id", ""),
                                "name": world.get("name", "未知世界"),
                                "world_type": world.get("world_type", "奇幻"),
                                "description": world.get("description", ""),
                                "background": world.get("background", ""),
                                "rules": world.get("rules", {}),
                                "themes": world.get("themes", []),
                                "tone": world.get("tone", "正剧"),
                            }
                            execution.context["world_info"] = context["world_info"]

                # 获取章节内容用于一致性检查
                if "chapter_content" not in context:
                    chapter_content = execution.context.get("written_content", "") or execution.context.get("chapter_content", "")
                    if not chapter_content:
                        chapters = await db.get_chapters_by_project(project_id) if hasattr(db, 'get_chapters_by_project') else []
                        if chapters:
                            chapter_content = chapters[-1].get("content", "") if chapters else ""
                    if chapter_content:
                        context["chapter_content"] = chapter_content
                        logger.info(f"Setting Agent 加载章节内容: {len(chapter_content)} 字符")

                # SettingAgent 会通过 SettingAgentService 自动处理
                # 传入 task 参数指定任务类型
                task = context.get("task", "manage_settings")
                if context.get("chapter_content"):
                    task = "consistency_check"
                context["task"] = task
                logger.info(f"Setting Agent 任务类型: {task}")

            if "character_constraints" not in context:
                self._inject_character_constraints(context)

            # ===== Evaluator Agent：需要章节历史、绑定大纲、设定、写作计划和资产状态 =====
            if agent_type == "evaluator":
                await self._attach_confirmed_prior_state_packet(context, execution, db)
                self._attach_upcoming_outline_context(context)
                for workflow_key in [
                    "chapter_outline",
                    "chapter_goals",
                    "chapter_goal",
                    "chapter_summary",
                    "chapter_title",
                    "target_word_count",
                    "chapter_target_word_count",
                    "scene_directions",
                    "writing_plan",
                    "plot_guidance",
                    "scene_integration_plan",
                    "resource_requirements",
                    "role_delta_resource_requirements",
                    "pending_resource_requirements",
                    "workflow_resource_requirements",
                    "latest_resource_requirements",
                    "latest_role_delta_resource_requirements",
                    "resource_requirement_persistence_state",
                    "fixed_lore_entries",
                    "dynamic_lore_entries",
                    "selected_lore_entries",
                    "upcoming_outline_context",
                    "upcoming_outline_policy",
                    "performance_result",
                    "role_performance_context",
                    "public_performances",
                    "private_performances",
                    "relationship_deltas",
                    "state_deltas",
                    "continuity_notes",
                    "performance_warnings",
                    "role_performance_gate",
                    "role_performance_gate_passed",
                    "role_performance_gate_blockers",
                    "role_performance_gate_warnings",
                    "participation_trace",
                    "map_persistence_state",
                    "asset_persistence_state",
                    "saved_region_ids",
                    "saved_hook_ids",
                    "saved_lore_ids",
                    "confirmed_prior_state_packet",
                    "confirmed_prior_state_packet_provenance",
                    "workflow_state",
                    "asset_state",
                    "node_outputs",
                ]:
                    if execution.context.get(workflow_key) is not None and workflow_key not in context:
                        context[workflow_key] = execution.context.get(workflow_key)

                self._attach_role_performance_context(context, execution.context)

                target_word_count = (
                    context.get("target_word_count")
                    or context.get("chapter_target_word_count")
                    or self._ensure_context_dict(context.get("chapter_outline")).get("target_word_count")
                )
                if target_word_count:
                    context["target_word_count"] = target_word_count
                    context["chapter_target_word_count"] = target_word_count

                if "chapter_content" not in context:
                    chapter_content = (
                        execution.context.get("chapter_content")
                        or execution.context.get("written_content")
                        or execution.context.get("content")
                    )
                    if chapter_content:
                        context["chapter_content"] = chapter_content

                if "previous_chapters" not in context:
                    chapters = await db.get_chapters_by_project(project_id) if hasattr(db, 'get_chapters_by_project') else []
                    if chapters:
                        context["previous_chapters"] = chapters
                        execution.context["previous_chapters"] = chapters
                        logger.info(f"加载 {len(chapters)} 个章节到评估上下文（evaluator）")

            # ===== Plotter Agent：需要初始剧情、角色、伏笔、章节概要、讨论历史 =====
            if agent_type in ["master_plotter", "plotter"]:
                # 初始剧情设定（从项目获取）
                if "initial_plot" not in context:
                    project = await db.get_project(project_id) if hasattr(db, 'get_project') else None
                    if project:
                        initial_plot = project.get("initial_plot", "") or project.get("description", "")
                        if initial_plot:
                            context["initial_plot"] = initial_plot
                            execution.context["initial_plot"] = initial_plot

                # 章节概要
                if "chapter_summaries" not in context:
                    chapters = await db.get_chapters_by_project(project_id) if hasattr(db, 'get_chapters_by_project') else []
                    if chapters:
                        summaries = [
                            {"chapter_num": i+1, "title": c.get("title", ""), "summary": c.get("summary", "")}
                            for i, c in enumerate(chapters)
                        ]
                        context["chapter_summaries"] = summaries
                        execution.context["chapter_summaries"] = summaries
                        logger.info(f"加载 {len(summaries)} 个章节概要到编剧上下文（plotter）")

                # 伏笔状态
                if "existing_hooks" not in context:
                    hooks = await db.get_hooks(project_id) if hasattr(db, 'get_hooks') else []
                    if hooks:
                        context["existing_hooks"] = hooks
                        execution.context["existing_hooks"] = hooks
                        logger.info(f"加载 {len(hooks)} 个伏笔到编剧上下文（plotter）")

                self._attach_role_performance_context(context, execution.context)

                for workflow_key in [
                    "resource_requirements",
                    "role_delta_resource_requirements",
                    "pending_resource_requirements",
                    "workflow_resource_requirements",
                    "latest_resource_requirements",
                    "latest_role_delta_resource_requirements",
                    "resource_requirement_persistence_state",
                ]:
                    if execution.context.get(workflow_key) is not None and workflow_key not in context:
                        context[workflow_key] = execution.context.get(workflow_key)

                # 讨论历史：从执行上下文获取之前的讨论记录
                discussion_history = self._ensure_context_list(execution.context.get("discussion_history", []))
                if discussion_history:
                    context["recent_discussions"] = discussion_history
                    # 提取最后一次讨论的总结
                    last_discussion = discussion_history[-1]
                    if isinstance(last_discussion, dict):
                        last_summary = last_discussion.get("summary", "") or last_discussion.get("full_content", "")
                        if not last_summary:
                            messages = last_discussion.get("messages", [])
                            if isinstance(messages, list):
                                for message in reversed(messages):
                                    if isinstance(message, dict) and message.get("content"):
                                        last_summary = message["content"]
                                        break
                    else:
                        last_summary = self._coerce_context_text(last_discussion)
                    if last_summary:
                        context["discussion_summary"] = last_summary
                        context["last_discussion_summary"] = last_summary

                    discussion_assets = execution.context.get("discussion_assets")
                    if discussion_assets and "discussion_assets" not in context:
                        context["discussion_assets"] = discussion_assets

                    discussion_asset_digest = execution.context.get("discussion_asset_digest")
                    if discussion_asset_digest and "discussion_asset_digest" not in context:
                        context["discussion_asset_digest"] = discussion_asset_digest

                    persisted_asset_refs = execution.context.get("persisted_asset_refs")
                    if persisted_asset_refs and "persisted_asset_refs" not in context:
                        context["persisted_asset_refs"] = persisted_asset_refs

                    if execution.context.get("discussion_assets_committed") and "discussion_assets_committed" not in context:
                        context["discussion_assets_committed"] = execution.context.get("discussion_assets_committed")

                    logger.info(f"加载 {len(discussion_history)} 条讨论记录到编剧上下文（plotter）")
            if agent_type in ["procgen", "proc_gen", "world_map_manager", "event_generator", "dungeon_generator"]:
                # 加载已有区域
                if "existing_regions" not in context:
                    # 尝试获取项目的世界
                    worlds = await db.get_worlds_by_project(project_id) if hasattr(db, 'get_worlds_by_project') else []
                    if worlds:
                        world_id = worlds[0].get("id")
                        regions = await db.get_regions_by_world(world_id) if hasattr(db, 'get_regions_by_world') and world_id else []
                        if regions:
                            context["existing_regions"] = regions
                            context["world_id"] = world_id
                            execution.context["existing_regions"] = regions
                            execution.context["world_id"] = world_id
                            logger.info(f"加载 {len(regions)} 个区域到世界生成上下文（{agent_type}）")

                # 准备 ProcGenAgent 需要的输入参数
                # exploration_direction: 从章节目标或剧情规划中提取
                if "exploration_direction" not in context:
                    chapter_goal = execution.context.get("chapter_goal", "")
                    plot_outline = self._ensure_context_list(execution.context.get("plot_outline", []))
                    world_info = context.get("world_info", {})

                    # 构建探索方向
                    if chapter_goal:
                        context["exploration_direction"] = chapter_goal
                    elif plot_outline:
                        # 从剧情大纲提取最近的探索方向
                        latest_plot = plot_outline[-1] if plot_outline else {}
                        latest_direction = self._extract_context_item_text(
                            latest_plot,
                            "event",
                            "summary",
                            "description",
                            "content",
                        )
                        context["exploration_direction"] = latest_direction or "扩展世界内容"
                    elif world_info:
                        world_name = world_info.get("name", "未知世界") if isinstance(world_info, dict) else "未知世界"
                        context["exploration_direction"] = f"探索 {world_name} 的新区域"
                    else:
                        context["exploration_direction"] = "随机探索"

                    logger.info(f"为 ProcGen Agent 设置探索方向: {context['exploration_direction']}")

                # generation_type: 根据上下文确定生成类型
                if "generation_type" not in context:
                    existing_regions = context.get("existing_regions", [])
                    if not existing_regions:
                        context["generation_type"] = "first_time"
                    else:
                        context["generation_type"] = "expansion"

                # current_location: 从上下文获取当前位置
                if "current_location" not in context:
                    context["current_location"] = execution.context.get("current_location")

                # 根据 agent 类型添加特定的任务提示
                if agent_type == "world_map_manager":
                    context["exploration_direction"] = f"[地图管理任务] {context.get('exploration_direction', '生成新地图区域')}"
                    logger.info(f"World Map Manager 上下文准备完成: exploration_direction={context.get('exploration_direction', 'N/A')}, generation_type={context.get('generation_type', 'N/A')}")
                elif agent_type == "event_generator":
                    context["exploration_direction"] = f"[事件生成任务] {context.get('exploration_direction', '生成世界事件')}"
                    logger.info(f"Event Generator 上下文准备完成: exploration_direction={context.get('exploration_direction', 'N/A')}, generation_type={context.get('generation_type', 'N/A')}")

        except Exception as e:
            logger.error(f"加载Agent上下文数据失败: {e}")

        return context

    async def _run_agent_execution(
        self,
        agent,
        context: Dict[str, Any],
        execution: "WorkflowExecution",
        node: WorkflowNode,
        db=None,
    ) -> tuple[Any, Optional[AgentResponse], Optional[AgentOutputContract]]:
        """执行Agent并处理结果"""
        if isinstance(agent, list):
            logger.info(f"Agent 节点 {node.agent_type} 返回 {len(agent)} 个实例，按多 Agent 模式执行")

            aggregated_outputs: List[Dict[str, Any]] = []
            aggregated_dialogues: List[Dict[str, Any]] = []
            aggregated_moods: Dict[str, str] = {}
            full_content_parts: List[str] = []
            errors: List[str] = []

            for idx, sub_agent in enumerate(agent):
                sub_agent_id = id(sub_agent)
                sub_agent_name = getattr(sub_agent, 'name', f'agent_{idx}')
                logger.info(
                    f"开始执行多 Agent 子实例: node={node.agent_type}, index={idx}, "
                    f"instance_id={sub_agent_id}, name={sub_agent_name}"
                )

                async def on_stream_chunk(chunk: str, sub_name=sub_agent_name):
                    await self._broadcast_status(execution.id, "agent_streaming", {
                        "agent": node.agent_type,
                        "node_id": node.id,
                        "label": node.label,
                        "sub_agent": sub_name,
                        "chunk": chunk,
                    })

                if hasattr(sub_agent, '_stream_callback'):
                    sub_agent._stream_callback = on_stream_chunk

                sub_context = dict(context)
                if hasattr(sub_agent, '_memory') and sub_agent._memory:
                    try:
                        task_type = self._infer_task_type(node.agent_type, node.label)
                        query_text = self._build_memory_query(sub_context, node.agent_type)
                        if hasattr(sub_agent, 'get_enhanced_memory_context'):
                            memory_context = await sub_agent.get_enhanced_memory_context(
                                task_type=task_type,
                                query_text=query_text,
                                current_context={
                                    "chapter_number": sub_context.get("chapter_num", sub_context.get("chapter_number")),
                                    "characters": sub_context.get("characters", []),
                                },
                                db=db,
                            )
                        else:
                            memory_context = sub_agent.get_memory_context()

                        if memory_context:
                            sub_context["agent_memory_context"] = memory_context
                    except Exception as e:
                        logger.warning(f"多 Agent 子实例获取增强记忆失败: {sub_agent_name}, error={e}")

                try:
                    sub_result = await sub_agent.execute(sub_context)
                except asyncio.TimeoutError:
                    sub_result = AgentResponse(success=False, error="Agent 执行超时")
                except Exception as e:
                    logger.error(f"多 Agent 子实例执行异常: {sub_agent_name}, error={e}")
                    sub_result = AgentResponse(success=False, error=str(e))
                finally:
                    if hasattr(sub_agent, '_stream_callback'):
                        sub_agent._stream_callback = None

                sub_payload = self._get_response_payload(sub_result)

                if sub_result.success and isinstance(sub_payload, dict):
                    data = sub_payload
                    character_name = (
                        data.get("character_name")
                        or getattr(getattr(sub_agent, 'character', None), 'name', None)
                        or sub_agent_name
                    )
                    dialogue = data.get("dialogue", data.get("content", ""))
                    emotion = data.get("emotion", data.get("mood", ""))
                    action = data.get("action", "")

                    public_content = data.get("public_content") or " ".join(part for part in [f"（{action}）" if action else "", dialogue] if part)
                    private_thought = data.get("private_thought") or data.get("inner_thought", "")

                    performance_packet = self._build_character_performance_packet(data, source_character=character_name)
                    aggregated_outputs.append({
                        "character": character_name,
                        "agent_id": getattr(sub_agent, 'agent_id', None),
                        "success": True,
                        "character_performance_packet": performance_packet,
                        **data,
                    })

                    if public_content:
                        aggregated_dialogues.append({
                            "character": character_name,
                            "dialogue": dialogue,
                            "content": public_content,
                            "public_content": public_content,
                            "emotion": emotion,
                            "action": action,
                        })
                        full_content_parts.append(f"【{character_name}】{public_content}")
                        execution.context.setdefault("character_dialogues", []).append({
                            "character": character_name,
                            "dialogue": public_content,
                        })

                    if private_thought or data.get("intent") or data.get("withheld_information"):
                        execution.context.setdefault("private_performances", []).append({
                            "agent": character_name,
                            "private_thought": private_thought,
                            "intent": data.get("intent", ""),
                            "withheld_information": data.get("withheld_information", []),
                            "misinterpretations": data.get("misinterpretations", []),
                        })

                    for delta in data.get("relationship_delta", []) or []:
                        if isinstance(delta, dict):
                            execution.context.setdefault("relationship_deltas", []).append({"source_character": character_name, **delta})
                    for delta in data.get("state_delta", []) or []:
                        if isinstance(delta, dict):
                            execution.context.setdefault("state_deltas", []).append({"source_character": character_name, **delta})
                    for note in data.get("continuity_notes", []) or []:
                        execution.context.setdefault("continuity_notes", []).append({"source_character": character_name, "note": note})
                    for warning in data.get("warnings", []) or []:
                        execution.context.setdefault("performance_warnings", []).append({"source_character": character_name, "warning": warning})

                    if emotion:
                        aggregated_moods[character_name] = emotion
                        execution.context.setdefault("character_moods", {})[character_name] = emotion

                    await self._broadcast_status(execution.id, "agent_output", {
                        "agent": node.agent_type,
                        "node_id": node.id,
                        "label": node.label,
                        "sub_agent": sub_agent_name,
                        "output": data,
                    })
                else:
                    errors.append(f"{sub_agent_name}: {sub_result.error}")
                    aggregated_outputs.append({
                        "character": getattr(getattr(sub_agent, 'character', None), 'name', sub_agent_name),
                        "agent_id": getattr(sub_agent, 'agent_id', None),
                        "success": False,
                        "error": sub_result.error,
                    })

                if hasattr(sub_agent, 'save_memory') and getattr(sub_agent, '_memory', None):
                    try:
                        if sub_result.success:
                            sub_agent.add_memory(
                                content=f"执行任务: {node.label} - 成功",
                                memory_type="action",
                                importance="medium",
                                tags=[node.agent_type, "workflow", node.node_type.value],
                                context={
                                    "node_id": node.id,
                                    "execution_id": execution.id,
                                    "output_keys": self._get_response_output_keys(sub_result),
                                },
                            )
                        else:
                            sub_agent.add_memory(
                                content=f"执行任务: {node.label} - 失败: {sub_result.error}",
                                memory_type="action",
                                importance="high",
                                tags=[node.agent_type, "workflow", "error"],
                                context={
                                    "node_id": node.id,
                                    "execution_id": execution.id,
                                    "error": sub_result.error,
                                },
                            )
                        await sub_agent.save_memory(db)
                    except Exception as e:
                        logger.warning(f"保存多 Agent 子实例记忆失败: {sub_agent_name}, error={e}")

            role_context_source = {
                "public_performances": aggregated_dialogues,
                "character_performance_packets": [
                    item.get("character_performance_packet")
                    for item in aggregated_outputs
                    if isinstance(item, dict) and isinstance(item.get("character_performance_packet"), dict)
                ],
                "private_performances": execution.context.get("private_performances", []),
                "relationship_deltas": execution.context.get("relationship_deltas", []),
                "state_deltas": execution.context.get("state_deltas", []),
                "continuity_notes": execution.context.get("continuity_notes", []),
                "performance_warnings": execution.context.get("performance_warnings", []),
                "full_content": "\n".join(full_content_parts),
            }
            role_gate = self._build_role_performance_gate(role_context_source, execution.context)
            role_context_source.update({
                "role_performance_gate": role_gate,
                "role_performance_gate_passed": role_gate.get("passed", False),
                "role_performance_gate_blockers": role_gate.get("blockers", []),
                "role_performance_gate_warnings": role_gate.get("warnings", []),
            })
            role_context = self._extract_role_performance_context(role_context_source)
            result_payload = {
                "outputs": aggregated_outputs,
                "dialogues": aggregated_dialogues,
                "character_moods": aggregated_moods,
                "full_content": "\n".join(full_content_parts),
                "success_count": len([item for item in aggregated_outputs if item.get("success")]),
                "error_count": len(errors),
                **role_context,
            }
            if role_context:
                result_payload["role_performance_context"] = role_context
            if errors:
                result_payload["errors"] = errors
            return result_payload, None, None

        chunk_count = 0  # 统计发送的 chunk 数量
        agent_id = id(agent)  # 获取 agent 实例 ID 用于调试

        # 记录 agent 实例信息
        logger.info(f"Agent 实例信息: type={node.agent_type}, id={agent_id}, name={getattr(agent, 'name', 'unknown')}")

        # 定义流式输出回调
        async def on_stream_chunk(chunk: str):
            """流式输出回调 - 通过 WebSocket 发送 chunk"""
            nonlocal chunk_count
            chunk_count += 1
            await self._broadcast_status(execution.id, "agent_streaming", {
                "agent": node.agent_type,
                "node_id": node.id,
                "label": node.label,
                "chunk": chunk,
            })

        # ========== 设置 Agent 的流式回调 ==========
        # 这样 Agent 在调用 _call_llm 时会自动使用流式输出
        if hasattr(agent, '_stream_callback'):
            agent._stream_callback = on_stream_chunk
            logger.info(f"已为 Agent {node.agent_type} (实例ID: {agent_id}) 设置流式回调")
        else:
            logger.warning(f"Agent {node.agent_type} 不支持流式回调（缺少 _stream_callback 属性）")

        # ========== 注入 Agent 记忆上下文（使用增强记忆服务）=========
        if hasattr(agent, '_memory') and agent._memory:
            try:
                # 确定任务类型（用于上下文感知记忆选择）
                task_type = self._infer_task_type(node.agent_type, node.label)
                query_text = self._build_memory_query(context, node.agent_type)

                # 使用增强记忆上下文
                if hasattr(agent, 'get_enhanced_memory_context'):
                    memory_context = await agent.get_enhanced_memory_context(
                        task_type=task_type,
                        query_text=query_text,
                        current_context={
                            "chapter_number": context.get("chapter_num", context.get("chapter_number")),
                            "characters": context.get("characters", []),
                        },
                        db=db,
                    )
                else:
                    memory_context = agent.get_memory_context()

                if memory_context:
                    context["agent_memory_context"] = memory_context
                    logger.info(f"Agent {node.agent_type} 注入了增强记忆上下文 ({agent._memory.total_memories} 条记忆, task_type={task_type})")
            except Exception as e:
                logger.warning(f"Agent {node.agent_type} 获取增强记忆上下文失败: {e}，使用基础记忆")
                if hasattr(agent, 'get_memory_context'):
                    memory_context = agent.get_memory_context()
                    if memory_context:
                        context["agent_memory_context"] = memory_context

        await self._capture_effective_agent_input_snapshot(
            execution,
            node,
            context.get("_resolved_agent_type") or node.agent_type,
            context.get("agent_scenario") or context.get("scenario"),
            context,
            db,
        )

        try:
            # 执行 Agent（添加超时保护）
            logger.info(f"开始执行 Agent {node.agent_type} (实例ID: {agent_id})")
            result = await agent.execute(context)
            logger.info(f"Agent {node.agent_type} (实例ID: {agent_id}) 执行完成, success={result.success}")
        except asyncio.TimeoutError:
            logger.error(f"Agent {node.agent_type} (实例ID: {agent_id}) 执行超时")
            result = AgentResponse(success=False, error="Agent 执行超时")
        except Exception as e:
            import traceback
            logger.error(f"Agent {node.agent_type} (实例ID: {agent_id}) 执行异常: {e}")
            logger.error(traceback.format_exc())
            result = AgentResponse(success=False, error=str(e))
        finally:
            # 清理回调
            if hasattr(agent, '_stream_callback'):
                agent._stream_callback = None

        payload = self._get_response_payload(result)
        resolved_contract = None
        if result.success:
            try:
                resolved_contract = self._resolve_node_output_contract(node, result)
            except Exception as e:
                logger.warning(f"解析 Agent 输出契约失败: node={node.id}, error={e}")

        result.metadata = result.metadata or {}
        if "prompt_render_trace" not in result.metadata:
            prompt_trace = await self._build_workflow_node_prompt_trace(
                context.get("_resolved_agent_type") or node.agent_type,
                execution.project_id,
                context.get("agent_scenario") or context.get("scenario"),
                context,
            )
            result.metadata["prompt_render_trace"] = prompt_trace
            result.metadata.setdefault("config_prompt_source", "agent_template_runtime")

        contract_metadata = self._build_contract_metadata(resolved_contract, result)
        execution.context.setdefault("node_runtime_metadata", {}).setdefault(node.id, {}).update({
            "source_node_id": node.id,
            "source_node_label": node.label,
            "source_agent_type": node.agent_type,
            "resolved_agent_type": context.get("_resolved_agent_type") or node.agent_type,
            "resolved_scenario": context.get("agent_scenario") or context.get("scenario") or "default",
            "source_trace_id": execution.trace_id,
            **contract_metadata,
        })

        # 日志记录流式输出统计
        if chunk_count > 0:
            logger.info(f"Agent {node.agent_type} (实例ID: {agent_id}) 发送了 {chunk_count} 个流式 chunk")
        else:
            logger.warning(f"Agent {node.agent_type} (实例ID: {agent_id}) 没有发送任何流式 chunk（可能 Agent 内部没有调用 _call_llm 或模型为空）")
            # 额外诊断信息
            if hasattr(agent, 'model') and agent.model is None:
                logger.error(f"Agent {node.agent_type} 的模型为 None！无法调用 LLM")
            elif hasattr(agent, 'model'):
                logger.info(f"Agent {node.agent_type} 的模型类型: {type(agent.model)}")

        # 广播 Agent 完成输出
        if result.success:
            agent_output_event = {
                "agent": node.agent_type,
                "node_id": node.id,
                "label": node.label,
                "output": payload,
            }
            agent_output_event.update(contract_metadata)
            await self._broadcast_status(execution.id, "agent_output", agent_output_event)

        output_data = payload if isinstance(payload, dict) else {}

        # 如果是评估 Agent，保存完整评估结果
        if node.agent_type == "evaluator" and result.success:
            # 字数检查
            word_count_check = output_data.get("word_count_check", {})
            chapter_content = execution.context.get("chapter_content", "")
            target_word_count = execution.context.get("target_word_count", 2000)
            min_word_count = int(target_word_count * 0.8)

            # 如果章节内容存在，进行字数验证
            if chapter_content:
                try:
                    from app.utils.text_utils import count_mixed_text, validate_word_count
                    actual_word_count = count_mixed_text(chapter_content)
                    word_count_passed, _, word_count_msg = validate_word_count(
                        chapter_content,
                        target_word_count,
                        tolerance=0.25,
                    )
                    max_word_count = int(target_word_count * 1.25)
                    word_count_check = {
                        "actual": actual_word_count,
                        "target": target_word_count,
                        "min_required": min_word_count,
                        "max_allowed": max_word_count,
                        "passed": word_count_passed,
                        "message": word_count_msg,
                    }
                    logger.info(f"字数验证: {word_count_msg}")
                except ImportError:
                    word_count_check = output_data.get("word_count_check", {})

            if word_count_check and not word_count_check.get("passed", True):
                output_data["word_count_check"] = word_count_check
                output_data["quality_passed"] = False
                output_data["approved"] = False
                output_data["pass"] = False

            def _get_explicit_bool(data: Dict[str, Any], keys: List[str], default: bool) -> bool:
                for key in keys:
                    if key in data:
                        return bool(data[key])
                return default

            evaluation_passed = _get_explicit_bool(output_data, ["quality_passed", "approved", "pass"], True)
            evaluation_issues = output_data.get("issues", output_data.get("problems", []))
            evaluation_suggestions = output_data.get("suggestions", output_data.get("recommendations", []))
            if not isinstance(evaluation_issues, list):
                evaluation_issues = [str(evaluation_issues)] if evaluation_issues else []
            if not isinstance(evaluation_suggestions, list):
                evaluation_suggestions = [str(evaluation_suggestions)] if evaluation_suggestions else []

            # 字数不达标或超标直接判定为不合格
            if not word_count_check.get("passed", True):
                evaluation_passed = False
                logger.warning(f"字数不符合要求，强制判定为不合格: {word_count_check.get('message')}")

            execution.context["evaluation_passed"] = evaluation_passed
            execution.context["word_count_check"] = word_count_check

            # 保存完整的评估反馈（包括问题和建议）
            evaluation_feedback = {
                "passed": evaluation_passed,
                "score": output_data.get("score", 0),
                "issues": evaluation_issues,
                "suggestions": evaluation_suggestions,
                "summary": output_data.get("summary", output_data.get("comment", "")),
                "word_count_check": word_count_check,
                "coherence_check": output_data.get("coherence_check", {}),
            }

            # 如果字数不达标，添加到issues
            if not word_count_check.get("passed", True):
                evaluation_feedback["issues"].insert(0, word_count_check.get("message", "字数不达标"))

            execution.context["evaluation_feedback"] = evaluation_feedback
            await self._record_quality_gate_result(execution, node, evaluation_feedback, db)

            # 检测角色死亡事件
            character_events = output_data.get("character_events", [])
            for event in character_events:
                if event.get("type") == "death":
                    execution.context.setdefault("character_deaths", []).append({
                        "character_id": event.get("character_id"),
                        "character_name": event.get("character_name"),
                        "cause": event.get("cause", "未知原因"),
                    })

            logger.info(f"评估 Agent 结果: passed={evaluation_passed}, score={evaluation_feedback['score']}, word_count_passed={word_count_check.get('passed')}")

        # 如果是角色 Agent，保存角色对话和状态
        if node.agent_type in ["character", "character_agent"] or node.agent_type.startswith("character:") or node.agent_type.startswith("char_"):
            if result.success and output_data:
                # 保存角色状态
                new_status = output_data.get("new_status")
                if new_status:
                    execution.context.setdefault("character_status_changes", []).append({
                        "character_id": node.agent_type,
                        "new_status": new_status,
                    })

                # 保存角色对话内容（供 Writer 参考）
                dialogue = output_data.get("dialogue", output_data.get("content", ""))
                if dialogue:
                    execution.context.setdefault("character_dialogues", []).append({
                        "character": node.agent_type,
                        "dialogue": dialogue,
                    })

                # 保存角色情绪状态
                emotion = output_data.get("emotion", output_data.get("mood", ""))
                character_name = output_data.get("character_name", node.agent_type.split(":")[-1] if ":" in node.agent_type else "角色")
                if emotion:
                    execution.context.setdefault("character_moods", {})[character_name] = emotion

                logger.info(f"角色 Agent {node.agent_type} 输出已保存")

        resolved_agent_type = execution.context.get("node_runtime_metadata", {}).get(node.id, {}).get("resolved_agent_type") or node.agent_type

        # 如果是 Writer Agent，根据质量门状态暂存草稿或直接保存章节到数据库
        writer_finalized = False
        writer_quality_gated = False
        if resolved_agent_type == "writer" and result.success and output_data:
            writer_quality_gated = self._is_quality_gate_active_for_writer(execution, node)
            if writer_quality_gated:
                await self._stage_writer_draft(
                    execution,
                    node,
                    output_data,
                    db,
                    contract_metadata=contract_metadata,
                    prompt_trace=result.metadata.get("prompt_render_trace"),
                )
            else:
                await self._save_chapter_from_writer(
                    execution,
                    output_data,
                    db,
                    source_node=node,
                    contract_metadata=contract_metadata,
                    prompt_trace=result.metadata.get("prompt_render_trace"),
                )
                writer_finalized = True

        if writer_finalized:
            writer_model = getattr(agent, 'model', None) if agent else None
            await self._run_writer_finalization_side_effects(execution, output_data, db, llm_model=writer_model)

        # 如果是伏笔管理 Agent，保存伏笔到数据库
        if node.agent_type == "hook_manager" and result.success and output_data:
            await self._save_hooks_from_manager(execution, output_data, db)

        # 如果是设定 Agent，保存设定到 lore_entries 表；workflow 只读 adapter 不落库
        if (
            node.agent_type == "setting"
            and result.success
            and output_data
            and output_data.get("setting_read_only") is not True
        ):
            await self._save_lore_from_setting(execution, output_data, db)

        # 如果是世界生成 Agent，保存区域到数据库
        if node.agent_type in ["procgen", "proc_gen", "world_map_manager", "event_generator", "dungeon_generator"] and result.success and output_data:
            await self._save_world_data_from_procgen(execution, output_data, db)

        # 如果是摘要 Agent，保存剧情摘要
        if node.agent_type == "summarizer" and result.success and output_data:
            await self._save_summary_from_summarizer(execution, output_data, db)

        # 如果是编剧 Agent，保存剧情规划
        if node.agent_type in ["master_plotter", "plotter"] and result.success and output_data:
            await self._save_plot_from_plotter(execution, output_data, db)

        # ========== 保存 Agent 记忆 ==========
        if hasattr(agent, 'save_memory') and agent._memory:
            try:
                # 添加执行记录到记忆
                if result.success:
                    agent.add_memory(
                        content=f"执行任务: {node.label} - 成功",
                        memory_type="action",
                        importance="medium",
                        tags=[node.agent_type, "workflow", node.node_type.value],
                        context={
                            "node_id": node.id,
                            "execution_id": execution.id,
                            "output_keys": self._get_response_output_keys(result),
                        },
                    )
                else:
                    agent.add_memory(
                        content=f"执行任务: {node.label} - 失败: {result.error}",
                        memory_type="action",
                        importance="high",  # 失败记录更重要
                        tags=[node.agent_type, "workflow", "error"],
                        context={
                            "node_id": node.id,
                            "execution_id": execution.id,
                            "error": result.error,
                        },
                    )

                # 保存记忆到数据库
                await agent.save_memory(db)
                logger.info(f"Agent {node.agent_type} 记忆已保存")

            except Exception as e:
                logger.warning(f"保存 Agent {node.agent_type} 记忆失败: {e}")

        return (payload if result.success else {"error": result.error}), result, resolved_contract

    def _infer_task_type(self, agent_type: str, node_label: str) -> str:
        """
        根据 Agent 类型和节点标签推断任务类型

        Args:
            agent_type: Agent 类型
            node_label: 节点标签

        Returns:
            str: 任务类型（用于记忆选择配置）
        """
        # Agent 类型到任务类型的映射
        task_type_map = {
            "plot_outline": "outline_generation",
            "master_plotter": "plot_planning",
            "plotter": "plot_planning",
            "writer": "chapter_writing",
            "evaluator": "evaluation",
            "character": "dialogue_generation",
            "hook_manager": "hook_management",
            "summarizer": "summarization",
            "event_generator": "event_planning",
        }

        # 首先根据节点标签推断
        label_lower = node_label.lower()
        if "大纲" in label_lower or "outline" in label_lower:
            return "outline_generation"
        if "写作" in label_lower or "writing" in label_lower:
            return "chapter_writing"
        if "评估" in label_lower or "eval" in label_lower:
            return "evaluation"
        if "对话" in label_lower or "dialogue" in label_lower:
            return "dialogue_generation"
        if "伏笔" in label_lower or "hook" in label_lower:
            return "hook_management"

        # 然后根据 Agent 类型推断
        return task_type_map.get(agent_type, "general")

    def _build_memory_query(self, context: Dict[str, Any], agent_type: str) -> str:
        """
        构建记忆查询文本

        从当前上下文中提取关键信息，用于语义记忆检索

        Args:
            context: 当前上下文
            agent_type: Agent 类型

        Returns:
            str: 查询文本
        """
        query_parts = []

        # 提取章节相关
        chapter_num = context.get("chapter_num", context.get("chapter_number"))
        if chapter_num:
            query_parts.append(f"第{chapter_num}章")

        # 提取角色相关
        characters = self._ensure_context_list(context.get("characters", []))
        if characters:
            char_names = []
            for character in characters:
                if isinstance(character, dict):
                    name = character.get("name") or character.get("character_name") or character.get("display_name")
                else:
                    name = self._coerce_context_text(character).strip()
                if name:
                    char_names.append(str(name))
            if char_names:
                query_parts.append(f"角色: {', '.join(char_names)}")

        # 提取章节目标
        chapter_goal = context.get("chapter_goal", context.get("goal"))
        if chapter_goal:
            query_parts.append(self._coerce_context_text(chapter_goal, str(chapter_goal)))

        # 提取大纲要点
        outline = context.get("chapter_outline", {})
        if isinstance(outline, dict):
            summary = outline.get("summary", outline.get("goal"))
            if summary:
                query_parts.append(self._coerce_context_text(summary, str(summary)))
        else:
            outline_text = self._coerce_context_text(outline).strip()
            if outline_text:
                query_parts.append(outline_text)

        # 提取用户干预
        user_guidance = context.get("user_guidance")
        if user_guidance:
            query_parts.append(self._coerce_context_text(user_guidance, str(user_guidance)))

        query_text = " ".join(part for part in query_parts if isinstance(part, str) and part.strip())
        return query_text if query_text else f"{agent_type} 任务"

    async def _mark_outline_after_writer_save(
        self,
        execution: "WorkflowExecution",
        db,
    ) -> None:
        """Mark the exact approved outline as completed after Writer persists its chapter."""
        outline_id = execution.context.get("chapter_outline_id")
        chapter_num = execution.context.get("chapter_num")
        if not outline_id or not db:
            return

        try:
            results = await db.execute_query(
                """
                SELECT id, project_id, chapter_number, status, next_outline_id
                FROM chapter_outlines
                WHERE id = :id
                LIMIT 1
                """,
                {"id": str(outline_id)},
            )
            if not results:
                logger.warning("Writer 保存章节后未找到对应大纲: %s", outline_id)
                return

            outline = results[0]
            if str(outline.get("project_id")) != str(execution.project_id):
                logger.warning("Writer 保存章节后跳过跨项目大纲状态更新: %s", outline_id)
                return
            if chapter_num is not None and int(outline.get("chapter_number") or 0) != int(chapter_num):
                logger.warning(
                    "Writer 保存章节后跳过章节号不匹配的大纲状态更新: outline=%s outline_chapter=%s context_chapter=%s",
                    outline_id,
                    outline.get("chapter_number"),
                    chapter_num,
                )
                return
            if outline.get("next_outline_id"):
                logger.warning("Writer 保存章节后跳过非当前大纲状态更新: %s", outline_id)
                return
            if str(outline.get("status") or "").lower() != "approved":
                logger.info("Writer 保存章节后大纲状态不是 approved，保持不变: %s", outline_id)
                return

            await db.execute_write(
                """
                UPDATE chapter_outlines
                SET status = 'completed', updated_at = CURRENT_TIMESTAMP
                WHERE id = :id
                  AND project_id = :project_id
                  AND status = 'approved'
                  AND next_outline_id IS NULL
                """,
                {"id": str(outline_id), "project_id": str(execution.project_id)},
            )
            execution.context["chapter_outline_status"] = "completed"
            try:
                from app.services.plot_outline_service import get_plot_outline_service

                get_plot_outline_service()._mark_outline_project_dirty(str(execution.project_id), chapter_num)
            except Exception as cache_exc:
                logger.debug("Writer 保存章节后清理大纲缓存失败: %s", cache_exc)
            trace_service = get_trace_service(db)
            await trace_service.record_event("chapter_outline_completed", {
                "chapter_outline_id": str(outline_id),
                "chapter_num": chapter_num,
                "chapter_id": execution.context.get("chapter_id"),
            })
            logger.info("章节大纲已随 Writer 章节保存标记 completed: %s", outline_id)
        except Exception as exc:
            logger.error("Writer 保存章节后更新大纲状态失败: %s", exc)
            execution.context["chapter_outline_status_update_error"] = str(exc)

    def _is_quality_gate_active_for_writer(self, execution: "WorkflowExecution", node: WorkflowNode) -> bool:
        """Return whether Writer output should wait for Evaluator/condition approval before final save."""
        node_config = node.config or {}
        explicit = (
            node_config.get("quality_gate_enabled")
            if "quality_gate_enabled" in node_config
            else node_config.get("defer_save_until_quality_pass")
        )
        if explicit is not None:
            return bool(explicit)

        context = execution.context if isinstance(execution.context, dict) else {}
        for key in ("quality_gate_enabled", "defer_save_until_quality_pass", "chapter_quality_gate_enabled"):
            if key in context:
                return bool(context.get(key))

        workflow = self._workflows.get(execution.workflow_id)
        if not workflow:
            return False

        node_by_id = {item.id: item for item in workflow.nodes}
        successors = [edge.target for edge in workflow.edges if edge.source == node.id]
        visited: Set[str] = set()
        queue: deque[str] = deque(successors)
        while queue:
            next_id = queue.popleft()
            if next_id in visited:
                continue
            visited.add(next_id)
            next_node = node_by_id.get(next_id)
            if not next_node:
                continue
            next_agent_type = (next_node.agent_type or "").lower()
            if next_agent_type in {"evaluator", "chapter_evaluator"} or next_node.node_type == NodeType.CONDITION:
                return True
            for edge in workflow.edges:
                if edge.source == next_id:
                    queue.append(edge.target)
        return False

    def _extract_writer_content(self, writer_output: Dict[str, Any]) -> str:
        return writer_output.get("content") or writer_output.get("chapter_content") or ""

    def _build_quality_summary(self, feedback: Dict[str, Any]) -> Dict[str, Any]:
        issues = feedback.get("issues") if isinstance(feedback, dict) else []
        suggestions = feedback.get("suggestions") if isinstance(feedback, dict) else []
        if not isinstance(issues, list):
            issues = [str(issues)] if issues else []
        if not isinstance(suggestions, list):
            suggestions = [str(suggestions)] if suggestions else []
        return self._make_json_safe({
            "passed": feedback.get("passed") if isinstance(feedback, dict) else None,
            "score": feedback.get("score") if isinstance(feedback, dict) else None,
            "issues_count": len(issues),
            "suggestions_count": len(suggestions),
            "issues": [str(item)[:240] for item in issues[:5]],
            "suggestions": [str(item)[:240] for item in suggestions[:5]],
            "summary": str(feedback.get("summary") or "")[:500] if isinstance(feedback, dict) else "",
            "word_count_check": feedback.get("word_count_check") if isinstance(feedback, dict) else None,
        })

    def _build_quality_gate_saved_metadata(self, execution: "WorkflowExecution") -> Dict[str, Any]:
        gate = execution.context.get("quality_gate") if isinstance(execution.context, dict) else None
        history = execution.context.get("quality_gate_history") if isinstance(execution.context, dict) else None
        revisions = execution.context.get("revision_history") if isinstance(execution.context, dict) else None
        history = history if isinstance(history, list) else []
        revisions = revisions if isinstance(revisions, list) else []
        if not isinstance(gate, dict) and not history and not revisions:
            return {}
        gate = gate if isinstance(gate, dict) else {}
        return self._make_json_safe({
            "quality_gate_passed": gate.get("passed"),
            "quality_gate_status": gate.get("status"),
            "quality_gate_score": gate.get("score"),
            "quality_gate_attempts": len(history),
            "revision_attempts": len(revisions),
            "finalized_from_draft_attempt": execution.context.get("chapter_draft_attempt"),
            "forced_pass": gate.get("forced_pass"),
        })

    async def _stage_writer_draft(
        self,
        execution: "WorkflowExecution",
        node: WorkflowNode,
        writer_output: Dict[str, Any],
        db=None,
        *,
        contract_metadata: Optional[Dict[str, Any]] = None,
        prompt_trace: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Stage Writer output as a draft for Evaluator review without final persistence."""
        content = self._extract_writer_content(writer_output)
        if not content:
            logger.warning("Writer 输出没有内容，无法进入质量门草稿阶段")
            return

        attempt = int(execution.context.get("chapter_draft_attempt") or 0) + 1
        import hashlib
        checksum = hashlib.sha256(content.encode("utf-8")).hexdigest()
        word_count = writer_output.get("word_count", len(content))
        provenance = self._build_writer_save_provenance(
            execution,
            node,
            writer_output,
            contract_metadata=contract_metadata,
            prompt_trace=prompt_trace,
        )
        draft_payload = {
            "draft_attempt": attempt,
            "chapter_num": execution.context.get("chapter_num"),
            "chapter_number": execution.context.get("chapter_num"),
            "chapter_title": execution.context.get("chapter_title"),
            "chapter_outline_id": execution.context.get("chapter_outline_id"),
            "project_id": execution.project_id,
            "execution_id": execution.id,
            "workflow_id": execution.workflow_id,
            "status": "draft_pending_quality_gate",
            "created_at": datetime.now().isoformat(),
            "word_count": word_count,
            "content_chars": len(content),
            "content_checksum": checksum,
            **provenance,
        }

        execution.context["chapter_content"] = content
        execution.context["chapter_draft_payload"] = self._make_json_safe(draft_payload)
        execution.context["chapter_draft_provenance"] = self._make_json_safe(provenance)
        execution.context["chapter_draft_attempt"] = attempt
        execution.context["chapter_draft_word_count"] = word_count
        execution.context["chapter_draft_checksum"] = checksum
        execution.context["pending_chapter_save"] = True
        execution.context["quality_gate_status"] = "pending_evaluation"
        execution.context["quality_gate"] = self._make_json_safe({
            "status": "pending_evaluation",
            "draft_attempt": attempt,
            "content_chars": len(content),
            "content_checksum": checksum,
            "updated_at": datetime.now().isoformat(),
        })
        await self._broadcast_status(execution.id, "chapter_draft_ready", self._make_json_safe(draft_payload))
        if db:
            await get_trace_service(db).record_event("chapter_draft_ready", self._make_json_safe(draft_payload))

    async def _record_quality_gate_result(
        self,
        execution: "WorkflowExecution",
        node: WorkflowNode,
        evaluation_feedback: Dict[str, Any],
        db=None,
    ) -> None:
        """Record Evaluator gate result as compact audit metadata."""
        if not execution.context.get("pending_chapter_save") and not execution.context.get("chapter_draft_payload"):
            return

        passed = bool(evaluation_feedback.get("passed"))
        draft_payload = execution.context.get("chapter_draft_payload") if isinstance(execution.context.get("chapter_draft_payload"), dict) else {}
        summary = self._build_quality_summary(evaluation_feedback)
        attempt = len(execution.context.get("quality_gate_history") or []) + 1
        entry = self._make_json_safe({
            "attempt": attempt,
            "evaluator_node_id": node.id,
            "evaluator_node_label": node.label,
            "passed": passed,
            "score": evaluation_feedback.get("score"),
            "draft_attempt": execution.context.get("chapter_draft_attempt"),
            "content_chars": draft_payload.get("content_chars"),
            "content_checksum": execution.context.get("chapter_draft_checksum") or draft_payload.get("content_checksum"),
            "issues_count": summary.get("issues_count"),
            "suggestions_count": summary.get("suggestions_count"),
            "issues": summary.get("issues"),
            "suggestions": summary.get("suggestions"),
            "summary": summary.get("summary"),
            "word_count_check": summary.get("word_count_check"),
            "evaluated_at": datetime.now().isoformat(),
        })
        history = execution.context.get("quality_gate_history")
        if not isinstance(history, list):
            history = []
        history.append(entry)
        execution.context["quality_gate_history"] = history
        status = "passed" if passed else "revision_required"
        gate = {
            "status": status,
            "passed": passed,
            "score": evaluation_feedback.get("score"),
            "latest_attempt": attempt,
            "draft_attempt": execution.context.get("chapter_draft_attempt"),
            "issues_count": entry.get("issues_count"),
            "suggestions_count": entry.get("suggestions_count"),
            "updated_at": entry.get("evaluated_at"),
        }
        execution.context["quality_gate"] = self._make_json_safe(gate)
        execution.context["quality_gate_status"] = status
        event_type = "quality_gate_passed" if passed else "quality_gate_failed"
        await self._broadcast_status(execution.id, event_type, entry)
        if db:
            await get_trace_service(db).record_event(event_type, entry)

    async def _finalize_chapter_after_quality_pass(
        self,
        execution: "WorkflowExecution",
        db=None,
    ) -> None:
        """Persist the latest staged Writer draft after quality approval, idempotently."""
        if not execution.context.get("pending_chapter_save"):
            return
        if execution.context.get("chapter_saved") and execution.context.get("chapter_saved_payload"):
            execution.context["pending_chapter_save"] = False
            return
        draft_payload = execution.context.get("chapter_draft_payload")
        if not isinstance(draft_payload, dict):
            raise ValueError("质量门通过但缺少 Writer 草稿元数据，无法保存章节")
        content = execution.context.get("chapter_content") or ""
        if not content:
            raise ValueError("质量门通过但缺少 Writer 草稿正文，无法保存章节")
        writer_output = {
            "chapter_content": content,
            "word_count": draft_payload.get("word_count") or execution.context.get("chapter_draft_word_count") or len(content),
            "metadata": {"quality_gate_finalized": True, "draft_attempt": execution.context.get("chapter_draft_attempt")},
        }
        node_outputs = execution.context.get("node_outputs") if isinstance(execution.context.get("node_outputs"), dict) else {}
        source_node_id = draft_payload.get("source_node_id")
        staged_writer_output = node_outputs.get(source_node_id) if source_node_id else None
        if isinstance(staged_writer_output, dict):
            writer_output = {**staged_writer_output, **writer_output}
        source_node = None
        workflow = self._workflows.get(execution.workflow_id)
        if workflow and source_node_id:
            source_node = next((item for item in workflow.nodes if item.id == source_node_id), None)
        contract_metadata = {
            "output_contract_id": draft_payload.get("source_output_contract_id"),
            "output_schema_name": draft_payload.get("source_output_schema_name"),
            "output_schema_version": draft_payload.get("source_output_schema_version"),
        }
        prompt_trace = draft_payload.get("writer_prompt_trace") if isinstance(draft_payload.get("writer_prompt_trace"), dict) else None
        await self._save_chapter_from_writer(
            execution,
            writer_output,
            db,
            source_node=source_node,
            contract_metadata=contract_metadata,
            prompt_trace=prompt_trace,
        )
        await self._run_writer_finalization_side_effects(execution, writer_output, db)

    async def _run_writer_finalization_side_effects(
        self,
        execution: "WorkflowExecution",
        writer_output: Dict[str, Any],
        db=None,
        *,
        llm_model=None,
    ) -> None:
        """Persist Writer side effects only after the chapter is finally accepted/saved."""
        await self._save_hooks_from_writer_metadata(execution, writer_output, db)
        chapter_content = writer_output.get("content") or writer_output.get("chapter_content", "")
        if chapter_content and len(chapter_content) > 500:
            await self._detect_and_promote_characters(
                execution=execution,
                content=chapter_content,
                db=db,
                llm_model=llm_model,
            )

        writer_character_candidates = self._ensure_context_list(
            writer_output.get("character_candidates")
            or writer_output.get("new_characters")
            or writer_output.get("characters_to_create")
        )
        if writer_character_candidates:
            character_result = await self._persist_discussion_characters(
                execution,
                writer_character_candidates,
                db,
            )
            execution.context["writer_created_characters"] = character_result.get("created", [])
            execution.context["writer_character_persistence_state"] = character_result

        await self._propose_state_changes_from_saved_chapter(execution, writer_output, db)

    def _collect_saved_chapter_state_change_candidates(
        self,
        execution: "WorkflowExecution",
        writer_output: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """Collect accepted Writer/runtime state-change candidates after final chapter save."""
        candidates: List[Dict[str, Any]] = []
        candidate_sources = [
            ("writer.state_deltas", writer_output.get("state_deltas")),
            ("writer.relationship_deltas", writer_output.get("relationship_deltas")),
            ("writer.state_changes", writer_output.get("state_changes")),
            ("writer.narrative_state_changes", writer_output.get("narrative_state_changes")),
            ("writer.chapter_state_changes", writer_output.get("chapter_state_changes")),
            ("runtime.state_deltas", execution.context.get("state_deltas")),
            ("runtime.relationship_deltas", execution.context.get("relationship_deltas")),
        ]

        for source, raw_items in candidate_sources:
            for index, item in enumerate(self._ensure_context_list(raw_items)):
                payload = self._discussion_asset_to_dict(item, default_key="summary")
                if not payload:
                    continue
                payload.setdefault("metadata", {})
                if isinstance(payload["metadata"], dict):
                    payload["metadata"] = {**payload["metadata"], "candidate_source": source, "candidate_index": index}
                else:
                    payload["metadata"] = {"candidate_source": source, "candidate_index": index}
                candidates.append(payload)

        continuity_notes = [
            ("writer.continuity_notes", writer_output.get("continuity_notes")),
            ("runtime.continuity_notes", execution.context.get("continuity_notes")),
        ]
        for source, raw_notes in continuity_notes:
            for index, note in enumerate(self._ensure_context_list(raw_notes)):
                if isinstance(note, dict):
                    summary = self._extract_context_item_text(note, "summary", "note", "content", "description")
                    payload = dict(note)
                else:
                    summary = self._coerce_context_text(note).strip()
                    payload = {"summary": summary}
                if not summary:
                    continue
                payload.update({
                    "entity_type": payload.get("entity_type") or "plot",
                    "change_type": payload.get("change_type") or "custom",
                    "title": payload.get("title") or "章节连续性备注",
                    "summary": summary,
                    "metadata": {
                        **self._ensure_context_dict(payload.get("metadata")),
                        "candidate_source": source,
                        "candidate_index": index,
                        "continuity_note": True,
                    },
                })
                candidates.append(payload)

        return candidates

    def _normalize_saved_chapter_state_change_candidate(
        self,
        raw_change: Dict[str, Any],
        execution: "WorkflowExecution",
    ) -> Dict[str, Any]:
        """Normalize Writer/runtime deltas into NarrativeStateChangeService payload shape."""
        payload = dict(raw_change)
        metadata = self._ensure_context_dict(payload.get("metadata"))
        entity_type = str(
            payload.get("entity_type")
            or payload.get("target_type")
            or payload.get("entity")
            or payload.get("scope")
            or "custom"
        ).lower()
        if entity_type in {"character_state", "character_status", "角色"}:
            entity_type = "character"
        elif entity_type in {"relationship", "关系"}:
            entity_type = "relationship"
        elif entity_type in {"hook", "foreshadowing", "伏笔"}:
            entity_type = "hook"
        elif entity_type in {"region", "location", "place", "地点", "区域"}:
            entity_type = "region"
        elif entity_type in {"world", "lore", "setting", "世界", "设定"}:
            entity_type = "world"
        elif entity_type in {"plot", "story", "剧情"}:
            entity_type = "plot"
        elif entity_type not in {"character", "region", "hook", "relationship", "world", "plot", "custom"}:
            metadata["raw_entity_type"] = entity_type
            entity_type = "custom"

        change_type = str(
            payload.get("change_type")
            or payload.get("type")
            or payload.get("action")
            or payload.get("delta_type")
            or "custom"
        ).lower()
        change_type_aliases = {
            "location": "location_change",
            "move": "location_change",
            "status": "status_change",
            "state": "status_change",
            "relationship": "relationship_change",
            "relation": "relationship_change",
            "hook_resolve": "hook_resolved",
            "resolve_hook": "hook_resolved",
            "hook_trigger": "hook_triggered",
            "trigger_hook": "hook_triggered",
            "region": "region_state_change",
            "world": "world_state_change",
        }
        change_type = change_type_aliases.get(change_type, change_type)
        valid_change_types = {
            "status_change",
            "death",
            "resurrection",
            "location_change",
            "hook_triggered",
            "hook_resolved",
            "hook_dropped",
            "region_state_change",
            "region_destroyed",
            "relationship_change",
            "world_state_change",
            "custom",
        }
        if change_type not in valid_change_types:
            metadata["raw_change_type"] = change_type
            if entity_type == "relationship":
                change_type = "relationship_change"
            elif entity_type == "region":
                change_type = "region_state_change"
            elif entity_type == "world":
                change_type = "world_state_change"
            else:
                change_type = "custom"

        if entity_type == "relationship" and change_type == "custom":
            change_type = "relationship_change"
        if entity_type == "region" and change_type == "custom":
            change_type = "region_state_change"
        if entity_type == "world" and change_type == "custom":
            change_type = "world_state_change"

        entity_id = payload.get("entity_id") or payload.get("target_id") or payload.get("character_id") or payload.get("hook_id") or payload.get("region_id")
        entity_name = payload.get("entity_name") or payload.get("target_name") or payload.get("character_name") or payload.get("name")
        summary = self._extract_context_item_text(payload, "summary", "description", "content", "note", "delta")
        title = payload.get("title") or payload.get("name") or summary[:40] or "章节状态变更提案"
        after_state = self._ensure_context_dict(payload.get("after_state")) or self._ensure_context_dict(payload.get("after"))
        before_state = self._ensure_context_dict(payload.get("before_state")) or self._ensure_context_dict(payload.get("before"))
        diff = self._ensure_context_dict(payload.get("diff"))
        if not after_state:
            after_state = {
                key: value
                for key, value in payload.items()
                if key not in {
                    "project_id", "world_id", "scope_type", "entity_type", "target_type", "entity", "scope",
                    "entity_id", "target_id", "character_id", "hook_id", "region_id", "entity_name",
                    "target_name", "character_name", "name", "change_type", "type", "action", "delta_type",
                    "status", "title", "summary", "description", "content", "note", "reason",
                    "before_state", "after_state", "before", "after", "diff", "metadata",
                }
            }

        return {
            "project_id": payload.get("project_id") or execution.project_id,
            "world_id": payload.get("world_id") or execution.context.get("world_id"),
            "scope_type": payload.get("scope_type") or "chapter",
            "entity_type": entity_type,
            "entity_id": entity_id,
            "entity_name": entity_name,
            "change_type": change_type,
            "status": "proposed",
            "confirmation_required": True,
            "title": str(title)[:120],
            "summary": str(summary or title)[:800],
            "reason": self._coerce_context_text(payload.get("reason"), "accepted_saved_chapter_state_writeback")[:800],
            "before_state": before_state,
            "after_state": after_state,
            "diff": diff,
            "metadata": {
                **metadata,
                "source": "saved_chapter_state_writeback",
                "chapter_id": execution.context.get("chapter_id"),
                "chapter_num": execution.context.get("chapter_num"),
                "chapter_title": execution.context.get("chapter_title"),
                "chapter_content_checksum": execution.context.get("chapter_content_checksum"),
                "quality_gate_status": execution.context.get("quality_gate_status"),
            },
            "workflow_execution_id": execution.id,
            "workflow_id": execution.workflow_id,
            "node_id": payload.get("node_id") or execution.context.get("chapter_writer_provenance", {}).get("source_node_id"),
            "agent_type": "writer",
            "chapter_id": execution.context.get("chapter_id"),
            "source_text": None,
        }

    async def _propose_state_changes_from_saved_chapter(
        self,
        execution: "WorkflowExecution",
        writer_output: Dict[str, Any],
        db=None,
    ) -> Dict[str, Any]:
        """Create auditable narrative-state proposals after final saved chapter acceptance."""
        result = {
            "status": "skipped",
            "chapter_id": execution.context.get("chapter_id"),
            "created": [],
            "applied": [],
            "pending": [],
            "errors": [],
            "entity_type_counts": {},
            "checkpoint": None,
        }
        if not execution.context.get("chapter_saved") or not execution.context.get("chapter_id"):
            return result
        if not db:
            result["status"] = "failed"
            result["errors"].append("数据库连接不存在")
            execution.context["state_writeback_status"] = result["status"]
            execution.context["state_writeback_error"] = result["errors"][0]
            return result

        chapter_id = execution.context.get("chapter_id")
        checkpoint = f"{execution.id}:{chapter_id}:{execution.context.get('chapter_content_checksum') or ''}"
        existing = self._ensure_context_dict(execution.context.get("saved_chapter_state_writeback"))
        if existing.get("checkpoint") == checkpoint and existing.get("status") in {"completed", "completed_with_errors", "no_candidates"}:
            return existing

        candidates = self._collect_saved_chapter_state_change_candidates(execution, writer_output)
        result["checkpoint"] = checkpoint
        if not candidates:
            result["status"] = "no_candidates"
            result["counts"] = {"proposed": 0, "applied": 0, "pending": 0, "errors": 0}
            execution.context["saved_chapter_state_writeback"] = result
            execution.context["state_writeback_status"] = result["status"]
            execution.context["state_writeback_counts"] = result["counts"]
            return result

        from app.services.narrative_state_change_service import NarrativeStateChangeService

        service = NarrativeStateChangeService(db)
        source_context = {
            "workflow_execution_id": execution.id,
            "workflow_id": execution.workflow_id,
            "node_id": execution.context.get("chapter_writer_provenance", {}).get("source_node_id"),
            "agent_type": "writer",
            "chapter_id": chapter_id,
            "source_text": None,
        }
        safe_auto_apply_types = {"character", "hook", "region"}

        for raw_change in candidates:
            payload = self._normalize_saved_chapter_state_change_candidate(raw_change, execution)
            entity_type = payload.get("entity_type") or "custom"
            result["entity_type_counts"][entity_type] = result["entity_type_counts"].get(entity_type, 0) + 1
            try:
                change = await service.create_change(payload, source_context=source_context)
                change_summary = {
                    "id": change.get("id"),
                    "entity_type": change.get("entity_type"),
                    "entity_id": change.get("entity_id"),
                    "entity_name": change.get("entity_name"),
                    "change_type": change.get("change_type"),
                    "status": change.get("status"),
                    "title": change.get("title"),
                }
                result["created"].append(change_summary)
                if entity_type in safe_auto_apply_types and (change.get("entity_id") or change.get("entity_name")):
                    confirmed = await service.confirm_change(change["id"])
                    applied = await service.apply_change(confirmed["id"])
                    applied_change = applied.get("change") or {}
                    result["applied"].append({
                        "id": applied_change.get("id") or change.get("id"),
                        "entity_type": applied_change.get("entity_type") or entity_type,
                        "projection": applied.get("projection"),
                    })
                else:
                    result["pending"].append(change_summary)
            except Exception as e:
                logger.error("章节状态写回提案失败: %s: %s", payload.get("title"), e)
                result["errors"].append({"title": payload.get("title"), "entity_type": entity_type, "error": str(e)})

        counts = {
            "proposed": len(result["created"]),
            "applied": len(result["applied"]),
            "pending": len(result["pending"]),
            "errors": len(result["errors"]),
        }
        result["counts"] = counts
        result["status"] = "completed_with_errors" if result["errors"] else "completed"
        execution.context["saved_chapter_state_writeback"] = result
        execution.context["state_writeback_status"] = result["status"]
        execution.context["state_writeback_counts"] = counts
        execution.context.pop("state_writeback_error", None)
        if result["errors"]:
            execution.context["state_writeback_error"] = result["errors"][0].get("error")

        event_payload = {
            "execution_id": execution.id,
            "workflow_id": execution.workflow_id,
            "chapter_id": chapter_id,
            "chapter_num": execution.context.get("chapter_num"),
            "chapter_number": execution.context.get("chapter_num"),
            "proposed_count": counts["proposed"],
            "applied_count": counts["applied"],
            "pending_count": counts["pending"],
            "error_count": counts["errors"],
            "entity_type_counts": result["entity_type_counts"],
            "state_change_ids": [item.get("id") for item in result["created"][:20] if item.get("id")],
            "source_node_id": source_context.get("node_id"),
        }
        if counts["proposed"]:
            await self._broadcast_status(execution.id, "chapter_state_writeback_proposed", event_payload)
        if counts["applied"]:
            await self._broadcast_status(execution.id, "chapter_state_writeback_applied", event_payload)
        if counts["errors"]:
            await self._broadcast_status(execution.id, "chapter_state_writeback_failed", event_payload)
        return result

    async def _save_chapter_from_writer(
        self,
        execution: "WorkflowExecution",
        writer_output: Dict[str, Any],
        db=None,
        *,
        source_node: Optional[WorkflowNode] = None,
        contract_metadata: Optional[Dict[str, Any]] = None,
        prompt_trace: Optional[Dict[str, Any]] = None,
    ):
        """
        保存 Writer Agent 输出的章节到本地文档
        数据库只保存路径和必要的元数据

        Args:
            execution: 工作流执行实例
            writer_output: Writer Agent 的输出数据
            db: 数据库连接
        """
        if not db:
            logger.warning("数据库连接不存在，无法保存章节")
            return

        import uuid
        from datetime import datetime

        content = writer_output.get("content") or writer_output.get("chapter_content") or ""
        if not content:
            logger.warning("Writer 输出没有内容，跳过保存")
            return

        chapter_num = execution.context.get("chapter_num", 1)
        chapter_title = execution.context.get("chapter_title", f"第{chapter_num}章")
        chapter_outline_id = execution.context.get("chapter_outline_id")
        word_count = writer_output.get("word_count", len(content))
        chapter_id = execution.context.get("chapter_id") or str(uuid.uuid4())
        saved_at = datetime.now().isoformat()

        try:
            chapter_data = {
                "id": chapter_id,
                "title": chapter_title,
                "project_id": execution.project_id,
                "chapter_outline_id": chapter_outline_id,
                "summary": "",  # 摘要可以后续由 Summarizer Agent 生成
                "content": content,
                "word_count": word_count,
                "status": "completed",
                "events": [],
                "hooks_planted": [],
                "hooks_resolved": [],
                "main_plot_progress": 0,
                "reader_scores": None,
                "created_at": datetime.now(),
                "updated_at": datetime.now(),
                "completed_at": datetime.now(),
            }

            # 保存到本地文档，数据库仅保留路径和元数据
            from app.services.chapter_document_storage import chapter_document_storage
            metadata = chapter_document_storage.write_chapter(
                chapter_id=str(chapter_data["id"]),
                project_id=chapter_data.get("project_id"),
                title=chapter_data.get("title") or "未命名章节",
                content=content,
            )
            chapter_data.update(metadata)
            chapter_data["content"] = ""
            await db.save_chapter(chapter_data)

            writer_provenance = self._build_writer_save_provenance(
                execution,
                source_node,
                writer_output,
                contract_metadata=contract_metadata,
                prompt_trace=prompt_trace,
            )
            saved_payload = {
                "chapter_id": chapter_id,
                "chapter_num": chapter_num,
                "chapter_number": chapter_num,
                "title": chapter_title,
                "chapter_title": chapter_title,
                "chapter_outline_id": chapter_outline_id,
                "project_id": execution.project_id,
                "execution_id": execution.id,
                "workflow_id": execution.workflow_id,
                "status": "saved",
                "saved_at": saved_at,
                "word_count": word_count,
                "content_chars": len(content),
                "content_storage": metadata.get("content_storage"),
                "content_path": metadata.get("content_path"),
                "content_size_bytes": metadata.get("content_size_bytes"),
                "content_checksum": metadata.get("content_checksum"),
                "world_id": execution.context.get("world_id"),
                **writer_provenance,
                **self._build_quality_gate_saved_metadata(execution),
            }

            # 更新执行上下文：正文仅作为当前运行内的瞬态上下文保留，持久化/事件只保存元数据。
            execution.context.pop("chapter_save_error", None)
            execution.context["chapter_id"] = chapter_id
            execution.context["chapter_content"] = content
            execution.context["chapter_saved"] = True
            execution.context["chapter_saved_at"] = saved_at
            execution.context["chapter_outline_id"] = chapter_outline_id
            execution.context["chapter_saved_payload"] = dict(saved_payload)
            execution.context["chapter_writer_provenance"] = dict(writer_provenance)
            execution.context["chapter_content_storage"] = metadata.get("content_storage")
            execution.context["chapter_content_path"] = metadata.get("content_path")
            execution.context["chapter_content_size_bytes"] = metadata.get("content_size_bytes")
            execution.context["chapter_content_checksum"] = metadata.get("content_checksum")
            execution.context["pending_chapter_save"] = False
            if isinstance(execution.context.get("quality_gate"), dict):
                execution.context["quality_gate"] = {
                    **execution.context["quality_gate"],
                    "status": "passed" if execution.context["quality_gate"].get("passed") is not False else execution.context["quality_gate"].get("status"),
                    "saved_at": saved_at,
                }
                execution.context["quality_gate_status"] = execution.context["quality_gate"].get("status")
            await self._mark_outline_after_writer_save(execution, db)

            logger.info(f"章节已保存到本地文档: {chapter_id} - {chapter_title} ({word_count} 字)")
            trace_service = get_trace_service(db)
            await trace_service.record_event("chapter_saved", saved_payload)

            if saved_payload.get("quality_gate_passed") is not None:
                await self._broadcast_status(execution.id, "chapter_finalized", saved_payload)

            # 广播章节保存事件
            await self._broadcast_status(execution.id, "chapter_saved", saved_payload)

        except Exception as e:
            logger.error(f"保存章节失败: {e}")
            execution.context["chapter_save_error"] = str(e)
            failure_payload = {
                "execution_id": execution.id,
                "workflow_id": execution.workflow_id,
                "project_id": execution.project_id,
                "chapter_outline_id": chapter_outline_id,
                "chapter_num": chapter_num,
                "title": chapter_title,
                "error": str(e),
            }
            try:
                await self._broadcast_status(execution.id, "chapter_save_failed", failure_payload)
            except Exception as broadcast_error:
                logger.error("广播章节保存失败事件失败: %s", broadcast_error)
            raise

    async def _detect_and_promote_characters(
        self,
        execution: "WorkflowExecution",
        content: str,
        db=None,
        llm_model=None,
    ):
        """
        从章节内容中检测新角色并执行晋升

        Args:
            execution: 工作流执行实例
            content: 章节内容
            db: 数据库连接
            llm_model: LLM 模型实例（用于智能角色检测）
        """
        try:
            from app.services.character_detection import get_character_detection_manager

            # 获取已有角色
            existing_characters = []
            if db:
                existing_characters = await db.get_all_characters(execution.project_id) or []

            # 获取检测管理器
            detection_manager = get_character_detection_manager()

            # 处理内容，检测新角色（传入 LLM 模型进行智能检测）
            result = await detection_manager.process_content(
                content=content,
                project_id=execution.project_id,
                existing_characters=existing_characters,
                context={
                    "chapter_num": execution.context.get("chapter_num", 1),
                    "scene_directions": execution.context.get("scene_directions", {}),
                },
                db=db,
                llm_model=llm_model,
            )

            # 如果检测到新角色或晋升了角色，广播通知
            if result.get("detected"):
                logger.info(f"检测到新角色: {[c.get('name', 'Unknown') for c in result['detected']]}")
                await self._broadcast_status(execution.id, "characters_detected", {
                    "detected": self._make_json_safe(result["detected"]),
                    "candidates": self._make_json_safe(result.get("candidates", [])),
                })

            if result.get("promoted"):
                promoted_names = [p.get("character", {}).get("name", "Unknown") for p in result["promoted"]]
                logger.info(f"角色晋升成功: {promoted_names}")
                await self._broadcast_status(execution.id, "characters_promoted", {
                    "promoted": self._make_json_safe(result["promoted"]),
                    "message": f"新角色晋升: {', '.join(promoted_names)}",
                })

                # 更新上下文中的角色列表
                for promoted in result["promoted"]:
                    char_data = promoted.get("character", {})
                    execution.context.setdefault("new_characters", []).append(char_data)

        except Exception as e:
            logger.warning(f"角色检测失败: {e}")

    def _clamp_hook_priority(self, priority: Any) -> int:
        try:
            value = int(priority)
        except (TypeError, ValueError):
            value = 3
        return max(1, min(5, value))

    def _normalize_hook_type(self, hook_type: Any) -> str:
        """将 Agent 输出的伏笔类型归一化为 Hook 模型允许的类型。"""
        value = str(hook_type or "").strip().lower()
        mapping = {
            "suspense": "mystery",
            "foreshadow": "custom",
            "foreshadowing": "custom",
            "twist": "event",
            "object": "object",
            "item": "object",
            "character": "character",
            "event": "event",
            "location": "location",
            "place": "location",
            "relationship": "relationship",
            "mystery": "mystery",
            "custom": "custom",
        }
        return mapping.get(value, "custom")

    def _coerce_writer_hook_items(self, value: Any, *, source: str) -> List[Dict[str, Any]]:
        """把 Writer 的 hooks_embedded/future_setup 兼容转换为可持久化伏笔。"""
        items: List[Dict[str, Any]] = []
        if not isinstance(value, list):
            return items

        for index, item in enumerate(value):
            if isinstance(item, dict):
                title = item.get("title") or item.get("name") or item.get("summary")
                description = item.get("description") or item.get("content") or item.get("detail") or title
                hook_type = item.get("hook_type") or item.get("type")
                resolution_hint = item.get("resolution_hint") or item.get("future_payoff") or item.get("payoff") or ""
                related_characters = item.get("related_characters") or item.get("characters") or []
                related_objects = item.get("related_objects") or item.get("objects") or []
                related_locations = item.get("related_locations") or item.get("locations") or []
                priority = item.get("priority", 3)
            else:
                text = str(item or "").strip()
                title = text[:80]
                description = text
                hook_type = "custom"
                resolution_hint = ""
                related_characters = []
                related_objects = []
                related_locations = []
                priority = 3

            if not title and not description:
                continue

            title = str(title or description or f"{source}-{index + 1}").strip()[:120]
            description = str(description or title).strip()
            try:
                priority_value = int(priority)
            except (TypeError, ValueError):
                priority_value = 3
            priority_value = max(1, min(5, priority_value))

            items.append({
                "title": title,
                "description": description,
                "hook_type": self._normalize_hook_type(hook_type),
                "resolution_hint": str(resolution_hint or ""),
                "priority": priority_value,
                "related_characters": related_characters if isinstance(related_characters, list) else [],
                "related_objects": related_objects if isinstance(related_objects, list) else [],
                "related_locations": related_locations if isinstance(related_locations, list) else [],
                "source": source,
            })
        return items

    async def _save_hooks_from_writer_metadata(
        self,
        execution: "WorkflowExecution",
        writer_output: Dict[str, Any],
        db=None,
    ) -> Dict[str, Any]:
        """保存 Writer 输出中实际嵌入/铺垫的伏笔，避免完整流程没有 HookManager 新建时伏笔链路为空。"""
        if not db:
            return {"planted": [], "resolved": [], "updated": [], "errors": ["数据库连接不存在，无法保存 Writer 伏笔"]}

        hooks: List[Dict[str, Any]] = []
        hooks.extend(self._coerce_writer_hook_items(writer_output.get("hooks_embedded"), source="writer.hooks_embedded"))
        hooks.extend(self._coerce_writer_hook_items(writer_output.get("future_setup"), source="writer.future_setup"))
        if not hooks:
            return {"planted": [], "resolved": [], "updated": [], "errors": []}

        result = await self._save_hooks_from_manager(
            execution,
            {"hooks_to_plant": hooks},
            db,
            source="writer_metadata",
        )
        if isinstance(result, dict) and result.get("planted"):
            execution.context.setdefault("writer_created_hooks", []).extend(result["planted"])
        return result

    async def _save_hooks_from_manager(
        self,
        execution: "WorkflowExecution",
        hook_output: Dict[str, Any],
        db=None,
        source: str = "hook_manager",
    ):
        """
        保存伏笔管理 Agent 输出的伏笔到数据库

        Args:
            execution: 工作流执行实例
            hook_output: HookManager Agent 的输出数据
            db: 数据库连接
        """
        if not db:
            logger.warning("数据库连接不存在，无法保存伏笔")
            return {"planted": [], "resolved": [], "updated": [], "errors": ["数据库连接不存在，无法保存伏笔"]}

        import uuid
        from datetime import datetime

        try:
            hooks_to_plant = hook_output.get("hooks_to_plant", [])
            hooks_to_resolve = hook_output.get("hooks_to_resolve", [])
            hooks_status_updates = hook_output.get("hooks_status_updates", [])

            def _valid_hook_uuid(raw_id: Any) -> Optional[str]:
                if raw_id in (None, ""):
                    return None
                try:
                    return str(uuid.UUID(str(raw_id)))
                except (TypeError, ValueError, AttributeError):
                    return None

            # 保存新伏笔
            planted_ids = []
            duplicate_candidates = []
            for hook_data in hooks_to_plant:
                title = hook_data.get("title", "未命名伏笔")
                description = hook_data.get("description", "")
                world_id = hook_data.get("world_id") or execution.context.get("world_id")
                scope_type = hook_data.get("scope_type") or ("world" if world_id else "project")
                if hasattr(db, "find_duplicate_hook"):
                    duplicate = await db.find_duplicate_hook(
                        execution.project_id,
                        title,
                        description,
                        world_id=world_id,
                        scope_type=scope_type,
                    )
                    if duplicate:
                        existing_id = str(duplicate.get("id"))
                        duplicate_candidates.append({
                            "type": "hook",
                            "title": title,
                            "existing_id": existing_id,
                        })
                        planted_ids.append(existing_id)
                        logger.info(f"跳过重复伏笔: {title} -> {existing_id}")
                        continue
                hook_id = str(uuid.uuid4())
                hook_record = {
                    "id": hook_id,
                    "title": title,
                    "description": description,
                    "hook_type": self._normalize_hook_type(hook_data.get("hook_type")),
                    "status": "planted",
                    "related_characters": hook_data.get("related_characters", []),
                    "related_locations": hook_data.get("related_locations", []),
                    "related_objects": hook_data.get("related_objects", []),
                    "plant_context": execution.context.get("chapter_title", ""),
                    "plant_chapter": execution.context.get("chapter_id"),
                    "resolution_hint": hook_data.get("resolution_hint", ""),
                    "resolution_context": None,
                    "resolution_chapter": None,
                    "priority": self._clamp_hook_priority(hook_data.get("priority")),
                    "created_at": datetime.now(),
                    "resolved_at": None,
                    "project_id": execution.project_id,
                    "world_id": world_id,
                    "scope_type": scope_type,
                    "character_id": hook_data.get("character_id"),
                    "parent_hook_id": hook_data.get("parent_hook_id"),
                    "promoted_from_hook_id": hook_data.get("promoted_from_hook_id"),
                    "visibility": hook_data.get("visibility") or "global",
                }
                await db.save_hook(hook_record)
                planted_ids.append(hook_id)
                logger.info(f"保存新伏笔: {hook_record['title']}")

            resolved_ids = []
            skipped_hook_updates = []
            for hook_data in hooks_to_resolve:
                raw_hook_id = hook_data.get("id")
                hook_id = _valid_hook_uuid(raw_hook_id)
                if hook_id:
                    await db.update_hook_status(hook_id, "resolved")
                    resolved_ids.append(hook_id)
                    logger.info(f"伏笔已回收: {hook_id}")
                elif raw_hook_id:
                    skipped_hook_updates.append({"id": raw_hook_id, "reason": "invalid_uuid", "action": "resolve"})
                    logger.warning(f"跳过伏笔回收：非 UUID id={raw_hook_id}")

            # 更新伏笔状态
            updated_ids = []
            for update_data in hooks_status_updates:
                raw_hook_id = update_data.get("id")
                hook_id = _valid_hook_uuid(raw_hook_id)
                new_status = update_data.get("new_status")
                if hook_id and new_status:
                    await db.update_hook_status(hook_id, new_status)
                    updated_ids.append(hook_id)
                    logger.info(f"伏笔状态更新: {hook_id} -> {new_status}")
                elif raw_hook_id:
                    skipped_hook_updates.append({"id": raw_hook_id, "reason": "invalid_uuid", "action": "status_update"})
                    logger.warning(f"跳过伏笔状态更新：非 UUID id={raw_hook_id}")

            if planted_ids:
                get_workflow_state(execution).set_asset_state(
                    {
                        "saved_hook_ids": planted_ids,
                        "duplicate_candidates": duplicate_candidates,
                    },
                    source="hook_persistence",
                )
                execution.context.setdefault("hooks_planted_this_run", []).extend(planted_ids)

            # 广播伏笔保存事件
            await self._broadcast_status(execution.id, "hooks_saved", {
                "source": source,
                "planted_count": len(planted_ids) - len(duplicate_candidates),
                "duplicate_count": len(duplicate_candidates),
                "resolved_count": len(resolved_ids),
                "updated_count": len(updated_ids),
                "skipped_count": len(skipped_hook_updates),
                "world_id": execution.context.get("world_id"),
            })

            return {
                "planted": planted_ids,
                "resolved": resolved_ids,
                "updated": updated_ids,
                "skipped": skipped_hook_updates,
                "errors": [],
            }

        except Exception as e:
            logger.error(f"保存伏笔失败: {e}")
            execution.context["hook_save_error"] = str(e)
            return {"planted": [], "resolved": [], "updated": [], "errors": [str(e)]}

    async def _save_lore_from_setting(
        self,
        execution: "WorkflowExecution",
        setting_output: Dict[str, Any],
        db=None,
    ):
        """
        保存设定 Agent 输出的设定到 lore_entries 表

        Args:
            execution: 工作流执行实例
            setting_output: Setting Agent 的输出数据
            db: 数据库连接
        """
        if not db:
            logger.warning("数据库连接不存在，无法保存设定")
            return {"created": [], "updated": [], "validated": [], "errors": ["数据库连接不存在，无法保存设定"]}

        import uuid
        from datetime import datetime

        try:
            # 获取新创建的设定
            new_lores = setting_output.get("new_lores", [])
            updated_lores = setting_output.get("updated_lores", [])
            validated_lores = setting_output.get("validated_lores", [])

            saved_lore_ids = []
            duplicate_candidates = []
            for lore_data in new_lores:
                if hasattr(db, "find_duplicate_lore"):
                    duplicate = await db.find_duplicate_lore(
                        execution.project_id,
                        lore_data.get("title", ""),
                        lore_data.get("content", ""),
                    )
                    if duplicate:
                        duplicate_candidates.append({
                            "type": "lore",
                            "title": lore_data.get("title", ""),
                            "existing_id": str(duplicate.get("id")),
                        })
                        saved_lore_ids.append(str(duplicate.get("id")))
                        logger.info(f"跳过重复设定: {lore_data.get('title', '未命名')} -> {duplicate.get('id')}")
                        continue
                lore_id = str(uuid.uuid4())

                # 确定类别和优先级
                category = lore_data.get("category", "custom")
                priority = lore_data.get("priority", "standard")

                # 映射字符串到枚举值（如果需要）
                from app.models.lore import LoreCategory, LorePriority
                if isinstance(category, str):
                    try:
                        category = LoreCategory(category.lower())
                    except ValueError:
                        category = LoreCategory.CUSTOM
                if isinstance(priority, str):
                    try:
                        priority = LorePriority(priority.lower())
                    except ValueError:
                        priority = LorePriority.STANDARD

                params = {
                    "id": lore_id,
                    "project_id": execution.project_id,
                    "title": lore_data.get("title", "未命名设定"),
                    "category": category.value if hasattr(category, 'value') else str(category),
                    "priority": priority.value if hasattr(priority, 'value') else str(priority),
                    "content": lore_data.get("content", ""),
                    "summary": lore_data.get("summary", "") if lore_data.get("summary") else "",
                    "keywords": json.dumps(lore_data.get("keywords", [])),
                    "tags": json.dumps(lore_data.get("tags", [])),
                    "constraints": json.dumps(lore_data.get("constraints", [])),
                    "related_characters": json.dumps(lore_data.get("related_characters", [])),
                    "related_locations": json.dumps(lore_data.get("related_locations", [])),
                    "related_items": json.dumps(lore_data.get("related_items", [])),
                    "forbidden_actions": json.dumps(lore_data.get("forbidden_actions", [])),
                    "source": lore_data.get("source", ""),
                    "created_at": datetime.now(),
                    "updated_at": datetime.now(),
                }

                await db.execute_write("""
                    INSERT INTO lore_entries (
                        id, project_id, title, category, priority, content, summary,
                        keywords, tags, constraints, related_characters, related_locations, related_items,
                        forbidden_actions, source, created_at, updated_at
                    ) VALUES (
                        CAST(:id AS UUID), CAST(:project_id AS UUID), :title, :category, :priority, :content, :summary,
                        :keywords, :tags, :constraints, :related_characters, :related_locations, :related_items,
                        :forbidden_actions, :source, :created_at, :updated_at
                    )
                """, params)

                saved_lore_ids.append(lore_id)
                logger.info(f"保存新设定: {lore_data.get('title', '未命名')} (ID: {lore_id})")

            # 更新现有设定
            updated_ids = []
            for lore_data in updated_lores:
                lore_id = lore_data.get("id")
                if not lore_id:
                    continue

                update_fields = []
                params = {"id": lore_id}

                json_fields = [
                    "keywords",
                    "tags",
                    "constraints",
                    "related_characters",
                    "related_locations",
                    "related_items",
                    "forbidden_actions",
                ]

                for field in [
                    "title",
                    "category",
                    "priority",
                    "content",
                    "summary",
                    "source",
                ]:
                    if field in lore_data:
                        update_fields.append(f"{field} = :{field}")
                        params[field] = lore_data[field]

                for field in json_fields:
                    if field in lore_data:
                        update_fields.append(f"{field} = :{field}")
                        params[field] = json.dumps(lore_data.get(field, []))

                if update_fields:
                    update_fields.append("updated_at = NOW()")
                    params["id"] = lore_id
                    query = f"UPDATE lore_entries SET {', '.join(update_fields)} WHERE id = CAST(:id AS UUID)"
                    await db.execute_write(query, params)
                    updated_ids.append(lore_id)
                    logger.info(f"更新设定: {lore_id}")

            # 更新执行上下文
            if saved_lore_ids:
                get_workflow_state(execution).set_asset_state(
                    {
                        "saved_lore_ids": saved_lore_ids,
                        "duplicate_candidates": duplicate_candidates,
                    },
                    source="lore_persistence",
                )
                execution.context.setdefault("lores_created_this_run", []).extend(saved_lore_ids)

            # 广播设定保存事件
            await self._broadcast_status(execution.id, "lores_saved", {
                "created_count": len(saved_lore_ids) - len(duplicate_candidates),
                "duplicate_count": len(duplicate_candidates),
                "updated_count": len(updated_lores),
                "validated_count": len(validated_lores),
            })

            # 同时更新 execution.context 中的 lore_entries
            if saved_lore_ids or updated_lores:
                # 重新加载设定列表
                try:
                    results = await db.execute_query(
                        "SELECT * FROM lore_entries WHERE project_id = CAST(:project_id AS UUID) ORDER BY priority, created_at DESC",
                        {"project_id": execution.project_id}
                    )
                    if results:
                        execution.context["lore_entries"] = results
                        logger.info(f"重新加载了 {len(results)} 条设定到上下文")
                except Exception as e:
                    logger.warning(f"重新加载设定列表失败: {e}")

            if saved_lore_ids or updated_lores:
                try:
                    from app.api.routes.lore import _invalidate_plot_outline_context
                    _invalidate_plot_outline_context(execution.project_id)
                except Exception as e:
                    logger.warning(f"Plot Outline 缓存失效失败: {e}")

            return {
                "created": saved_lore_ids,
                "updated": updated_ids,
                "validated": [l.get("id") for l in validated_lores if isinstance(l, dict) and l.get("id")],
                "errors": [],
            }

        except Exception as e:
            logger.error(f"保存设定失败: {e}")
            execution.context["lore_save_error"] = str(e)
            return {"created": [], "updated": [], "validated": [], "errors": [str(e)]}

    def _normalize_region_outputs(self, output_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        candidates: List[Any] = []
        if isinstance(output_data.get("regions"), list):
            candidates.extend(output_data.get("regions") or [])
        if isinstance(output_data.get("region"), dict):
            candidates.append(output_data.get("region"))
        region_like_keys = {"name", "region_name", "terrain_type", "region_type", "landmarks", "features", "terrain_features"}
        if region_like_keys.intersection(output_data.keys()):
            candidates.append(output_data)

        normalized: List[Dict[str, Any]] = []
        seen: set[str] = set()
        for candidate in candidates:
            if not isinstance(candidate, dict):
                continue
            name = candidate.get("name") or candidate.get("region_name")
            if not name:
                continue
            key = str(candidate.get("id") or name)
            if key in seen:
                continue
            seen.add(key)
            normalized.append({
                **candidate,
                "name": name,
                "description": candidate.get("description") or candidate.get("summary") or candidate.get("overview") or "",
                "region_type": candidate.get("region_type") or candidate.get("type") or "custom",
                "terrain_type": candidate.get("terrain_type") or candidate.get("terrain") or "custom",
                "terrain_features": candidate.get("terrain_features") or candidate.get("features") or [],
                "connections": candidate.get("connections") or candidate.get("neighbors") or [],
            })
        return normalized

    async def _resolve_world_id_for_asset(
        self,
        execution: "WorkflowExecution",
        output_data: Dict[str, Any],
        db=None,
    ) -> Optional[str]:
        world_id = execution.context.get("world_id") or output_data.get("world_id")
        if world_id:
            return str(world_id)
        for container in (execution.context.get("world_info"), output_data.get("world_info")):
            if isinstance(container, dict) and container.get("id"):
                return str(container.get("id"))
        if db and hasattr(db, "get_default_world"):
            default_world = await db.get_default_world(execution.project_id)
            if default_world and default_world.get("id"):
                return str(default_world.get("id"))
        return None

    def _normalize_event_outputs(self, procgen_output: Dict[str, Any]) -> List[Dict[str, Any]]:
        """兼容 EventGenerator 的多种输出形态，提取可持久化剧情事件。"""
        raw_events: List[Any] = []
        for key in ("events", "event_candidates"):
            value = procgen_output.get(key)
            if isinstance(value, list):
                raw_events.extend(value)
            elif isinstance(value, dict):
                raw_events.append(value)

        data_value = procgen_output.get("data")
        if isinstance(data_value, list):
            raw_events.extend(data_value)
        elif isinstance(data_value, dict):
            raw_events.append(data_value)

        has_single_event_shape = any(
            procgen_output.get(key)
            for key in ("event_id", "event_name", "event_type", "trigger_condition", "narrative_purpose")
        )
        if has_single_event_shape:
            raw_events.append(procgen_output)

        normalized: List[Dict[str, Any]] = []
        seen: set[str] = set()
        for raw_event in raw_events:
            if not isinstance(raw_event, dict):
                continue
            event_name = raw_event.get("event_name") or raw_event.get("name") or raw_event.get("title")
            event_id = raw_event.get("event_id") or raw_event.get("id")
            description = raw_event.get("description") or raw_event.get("summary")
            if not event_name and not event_id and not description:
                continue
            key = str(event_id or event_name or description)
            if key in seen:
                continue
            seen.add(key)
            normalized.append(raw_event)
        return normalized

    def _normalize_location_outputs(self, procgen_output: Dict[str, Any]) -> List[Dict[str, Any]]:
        """提取 location / sub-location 输出，避免字符串和空值污染保存流程。"""
        raw_locations: List[Any] = []
        for key in ("locations", "location_candidates", "sub_locations"):
            value = procgen_output.get(key)
            if isinstance(value, list):
                raw_locations.extend(value)
            elif isinstance(value, dict):
                raw_locations.append(value)
        normalized: List[Dict[str, Any]] = []
        for raw_location in raw_locations:
            if isinstance(raw_location, dict) and (raw_location.get("name") or raw_location.get("location_name") or raw_location.get("title")):
                normalized.append(raw_location)
        return normalized

    async def _save_world_data_from_procgen(
        self,
        execution: "WorkflowExecution",
        procgen_output: Dict[str, Any],
        db=None,
    ):
        """
        保存世界生成 Agent 输出的区域到数据库

        Args:
            execution: 工作流执行实例
            procgen_output: ProcGen Agent 的输出数据
            db: 数据库连接
        """
        if not db:
            logger.warning("数据库连接不存在，无法保存世界数据")
            return {"saved": [], "events": [], "locations": [], "errors": ["数据库连接不存在，无法保存世界数据"]}

        import uuid
        from datetime import datetime

        try:
            # 获取生成的区域/事件/地点。事件 Agent 常把候选事件放在 data 列表中，不能只读取 events 字段。
            regions = self._normalize_region_outputs(procgen_output)
            events = self._normalize_event_outputs(procgen_output)
            locations = self._normalize_location_outputs(procgen_output)

            if not regions and procgen_output.get("overview"):
                regions = self._normalize_region_outputs(procgen_output)
                if procgen_output.get("suggested_starting_location"):
                    locations = [
                        *locations,
                        {
                            "name": procgen_output.get("suggested_starting_location"),
                            "description": procgen_output.get("overview", ""),
                            "source": "world_map_manager",
                        },
                    ]

            # 保存区域
            saved_regions = []
            world_id = await self._resolve_world_id_for_asset(execution, procgen_output, db)
            if regions and not world_id:
                error_message = "地图未落库，因为没有可关联世界"
                execution.context.setdefault("map_persistence_state", {})["error"] = error_message
                logger.error(error_message)
                return {"saved": [], "events": events, "locations": locations, "errors": [error_message]}

            for region_data in regions:
                region_id = region_data.get("id") or str(uuid.uuid4())
                region_record = {
                    "id": region_id,
                    "name": region_data.get("name") or region_data.get("region_name") or "未命名区域",
                    "description": region_data.get("description") or region_data.get("summary") or region_data.get("overview") or "",
                    "region_type": region_data.get("region_type", "custom"),
                    "terrain_type": region_data.get("terrain_type", "custom"),
                    "atmosphere": region_data.get("atmosphere", ""),
                    "coordinates": region_data.get("coordinates", {}),
                    "area_size": region_data.get("area_size", 0.0),
                    "terrain_features": region_data.get("terrain_features") or region_data.get("features", []),
                    "landmarks": region_data.get("landmarks", []),
                    "encounters": region_data.get("encounters", []),
                    "connections": region_data.get("connections") or region_data.get("neighbors", []),
                    "local_rules": region_data.get("local_rules", []),
                    "metadata": {
                        "asset_kind": "region",
                        "workflow_execution_id": execution.id,
                        "workflow_id": execution.workflow_id,
                        "agent_type": region_data.get("agent_type") or "world_map_manager",
                        "source": region_data.get("source") or "workflow",
                        "source_region": region_data,
                    },
                    "state": region_data.get("state", "normal"),
                    "state_summary": region_data.get("state_summary", ""),
                    "destroyed_at": region_data.get("destroyed_at"),
                    "is_generated": True,
                    "visit_count": 0,
                    "created_at": datetime.now(),
                    "updated_at": datetime.now(),
                    "world_id": world_id,
                }

                await db.save_region(region_record)
                saved_regions.append(region_id)
                logger.info(f"保存世界区域: {region_record['name']}")

            # 保存事件到数据库，同时保留上下文候选，便于当前执行内即时消费。
            saved_event_ids = []
            if events:
                execution.context.setdefault("generated_events", []).extend(events)
                execution.context["event_candidates"] = events
                if hasattr(db, "save_event"):
                    for event_data in events:
                        if not isinstance(event_data, dict):
                            continue
                        event_record = {
                            **event_data,
                            "project_id": execution.project_id,
                            "world_id": event_data.get("world_id") or world_id,
                            "workflow_execution_id": execution.id,
                            "workflow_id": execution.workflow_id,
                            "node_id": event_data.get("node_id"),
                            "agent_type": event_data.get("agent_type") or "event_generator",
                            "source": event_data.get("source") or "workflow",
                        }
                        saved_event_ids.append(await db.save_event(event_record))
                get_workflow_state(execution).set_asset_state(
                    {
                        "saved_event_ids": saved_event_ids,
                        "event_persistence_state": {
                            "status": "saved" if saved_event_ids else "context_only",
                            "saved_event_ids": saved_event_ids,
                            "count": len(events),
                            "reason": None if saved_event_ids else "no_save_event_method_or_empty_event_payload",
                        },
                    },
                    source="event_persistence",
                )

            # 保存地点到数据库，同时保留上下文候选，便于当前执行内即时消费。
            saved_location_ids = []
            if locations:
                execution.context.setdefault("generated_locations", []).extend(locations)
                execution.context["locations"] = [
                    *self._ensure_context_list(execution.context.get("locations", [])),
                    *locations,
                ]
                if not world_id:
                    error_message = "地点未落库，因为没有可关联世界"
                    execution.context.setdefault("location_persistence_state", {})["error"] = error_message
                    logger.error(error_message)
                elif hasattr(db, "save_location"):
                    for location_data in locations:
                        if not isinstance(location_data, dict):
                            continue
                        location_record = {
                            **location_data,
                            "world_id": location_data.get("world_id") or world_id,
                            "metadata": {
                                **(location_data.get("metadata") if isinstance(location_data.get("metadata"), dict) else {}),
                                "workflow_execution_id": execution.id,
                                "workflow_id": execution.workflow_id,
                                "agent_type": location_data.get("agent_type") or "world_map_manager",
                                "source": location_data.get("source") or "workflow",
                            },
                        }
                        saved_location_ids.append(await db.save_location(location_record))
                get_workflow_state(execution).set_asset_state(
                    {
                        "saved_location_ids": saved_location_ids,
                        "location_persistence_state": {
                            "status": "saved" if saved_location_ids else "context_only",
                            "saved_location_ids": saved_location_ids,
                            "count": len(locations),
                            "map_visible_world_id": world_id,
                            "reason": None if saved_location_ids else "no_world_id_or_no_save_location_method_or_empty_location_payload",
                        },
                    },
                    source="location_persistence",
                )

            if saved_regions:
                get_workflow_state(execution).set_asset_state(
                    {
                        "saved_region_ids": saved_regions,
                        "map_persistence_state": {
                            "status": "saved",
                            "saved_region_ids": saved_regions,
                            "map_visible_world_id": world_id,
                        },
                    },
                    source="world_data_persistence",
                )
                execution.context.setdefault("saved_regions", []).extend(saved_regions)
                execution.context["map_visible_world_id"] = world_id

            # 广播世界数据保存事件
            await self._broadcast_status(execution.id, "world_data_saved", {
                "regions_count": len(saved_regions),
                "events_count": len(events),
                "locations_count": len(locations),
                "map_visible_world_id": world_id,
            })

            return {
                "saved": saved_regions,
                "events": events,
                "locations": locations,
                "saved_event_ids": saved_event_ids,
                "saved_location_ids": saved_location_ids,
                "errors": [],
            }

        except Exception as e:
            logger.error(f"保存世界数据失败: {e}")
            execution.context["world_data_save_error"] = str(e)
            return {"saved": [], "events": [], "locations": [], "errors": [str(e)]}

    async def _save_summary_from_summarizer(
        self,
        execution: "WorkflowExecution",
        summarizer_output: Dict[str, Any],
        db=None,
    ):
        """
        保存摘要 Agent 输出的剧情摘要

        Args:
            execution: 工作流执行实例
            summarizer_output: Summarizer Agent 的输出数据
            db: 数据库连接
        """
        try:
            # 更新执行上下文中的摘要信息
            summary = summarizer_output.get("summary", "")
            key_events = summarizer_output.get("key_events", [])
            character_states = summarizer_output.get("character_states", {})
            plot_progress = summarizer_output.get("plot_progress", 0)

            if summary:
                execution.context["current_plot_summary"] = summary
                logger.info(f"更新剧情摘要: {summary}")

            if key_events:
                execution.context.setdefault("all_key_events", []).extend(key_events)

            if character_states:
                execution.context["character_states"] = character_states

            if plot_progress:
                execution.context["main_plot_progress"] = plot_progress

            # 广播摘要保存事件
            await self._broadcast_status(execution.id, "summary_updated", {
                "summary_length": len(summary),
                "events_count": len(key_events),
            })

        except Exception as e:
            logger.error(f"保存摘要失败: {e}")
            execution.context["summary_save_error"] = str(e)

    async def _save_plot_from_plotter(
        self,
        execution: "WorkflowExecution",
        plotter_output: Dict[str, Any],
        db=None,
    ):
        """
        保存编剧 Agent 输出的剧情规划

        Args:
            execution: 工作流执行实例
            plotter_output: Plotter Agent 的输出数据
            db: 数据库连接
        """
        try:
            # 更新执行上下文中的剧情规划。章节工作流中选中/自动加载的大纲是受保护事实源，
            # 总编剧只能提供写作计划和修订建议，不能覆盖绑定大纲。
            state = get_workflow_state(execution)
            outline_source = execution.context.get("chapter_outline_source")
            protect_bound_outline = outline_source in {"selected_outline", "auto_loaded"}

            plot_outline = plotter_output.get("plot_outline", [])
            chapter_outline = plotter_output.get("chapter_outline", {})
            upcoming_events = plotter_output.get("upcoming_events", [])
            character_arcs = plotter_output.get("character_arcs", {})
            chapter_titles = plotter_output.get("chapter_titles", [])
            chapter_goals = plotter_output.get("chapter_goals", [])
            main_conflicts = plotter_output.get("main_conflicts", [])
            runtime_updates: Dict[str, Any] = {}

            for key in (
                "writing_plan",
                "plot_guidance",
                "scene_integration_plan",
                "required_elements_check",
                "outline_adherence_notes",
                "setting_conflict_warnings",
                "supporting_character_plan",
            ):
                if plotter_output.get(key) is not None:
                    runtime_updates[key] = plotter_output[key]

            character_candidates = self._ensure_context_list(
                plotter_output.get("character_candidates")
                or plotter_output.get("new_characters")
                or plotter_output.get("characters_to_create")
            )
            if character_candidates:
                character_result = await self._persist_discussion_characters(
                    execution,
                    character_candidates,
                    db,
                )
                execution.context["plotter_created_characters"] = character_result.get("created", [])
                execution.context["plotter_character_persistence_state"] = character_result
                runtime_updates["character_candidates"] = character_candidates

            if protect_bound_outline:
                suggested_outline = plotter_output.get("suggested_chapter_outline") or chapter_outline
                suggested_goals = plotter_output.get("suggested_chapter_goals") or chapter_goals
                if suggested_outline:
                    runtime_updates["suggested_chapter_outline"] = suggested_outline
                if suggested_goals:
                    runtime_updates["suggested_chapter_goals"] = suggested_goals
                if chapter_outline or chapter_goals:
                    state.record_state_transition(
                        source="plotter_outline_protection",
                        blocked_updates={
                            key: {"reason": "bound_chapter_outline_protected", "source": outline_source}
                            for key, value in {"chapter_outline": chapter_outline, "chapter_goals": chapter_goals}.items()
                            if value
                        },
                    )
                    logger.info("已保护绑定章节大纲，Plotter 输出的大纲/目标保存为建议而非覆盖事实源")
            else:
                if chapter_outline:
                    execution.context["chapter_outline"] = chapter_outline
                    logger.info(f"更新章节大纲: {len(chapter_outline)} 章")
                if chapter_goals:
                    execution.context["chapter_goals"] = chapter_goals
                    logger.info(f"保存章节目标: {len(chapter_goals)} 章")

            if runtime_updates:
                state.merge_runtime_state(runtime_updates, source="plotter_guidance")

            if chapter_titles:
                execution.context["chapter_titles"] = chapter_titles

            if main_conflicts:
                execution.context["main_conflicts"] = main_conflicts

            if upcoming_events:
                execution.context.setdefault("upcoming_events", []).extend(upcoming_events)

            if character_arcs:
                execution.context["character_arcs"] = character_arcs

            # 设置当前章节号（如果还没有）
            if "chapter_num" not in execution.context:
                execution.context["chapter_num"] = 1

            # 设置当前章节标题
            if not protect_bound_outline and chapter_titles and len(chapter_titles) >= execution.context.get("chapter_num", 1):
                execution.context["chapter_title"] = chapter_titles[execution.context.get("chapter_num", 1) - 1]

            # 设置章节目标（用于写作），但不覆盖绑定章节大纲目标
            if not protect_bound_outline and chapter_goals and len(chapter_goals) >= execution.context.get("chapter_num", 1):
                goal = chapter_goals[execution.context.get("chapter_num", 1) - 1]
                execution.context["chapter_goal"] = goal if isinstance(goal, str) else goal.get("goal", str(goal))

            # 广播剧情规划保存事件
            await self._broadcast_status(execution.id, "plot_updated", {
                "outline_length": len(plot_outline),
                "events_count": len(upcoming_events),
                "chapters_planned": len(chapter_goals) if chapter_goals else len(chapter_titles),
            })

        except Exception as e:
            logger.error(f"保存剧情规划失败: {e}")
            execution.context["plot_save_error"] = str(e)

    async def _execute_condition_node(
        self,
        node: WorkflowNode,
        execution: WorkflowExecution,
        db=None,
    ) -> Dict[str, Any]:
        """执行条件节点"""
        condition_key = (node.config or {}).get("condition_key") if node.config else None
        pass_value = (node.config or {}).get("pass_value", True) if node.config else True
        pass_when_missing = (node.config or {}).get("pass_when_missing", False) if node.config else False

        if condition_key:
            raw_value = execution.context.get(condition_key)
            if raw_value is None:
                evaluation_passed = pass_when_missing
            else:
                evaluation_passed = raw_value == pass_value
        else:
            evaluation_passed = execution.context.get("evaluation_passed", False)

        retry_count = execution.context.get("retry_count", 0)
        evaluation_feedback = execution.context.get("evaluation_feedback", {})

        output = {
            "condition_evaluated": True,
            "quality_passed": evaluation_passed,
            "condition_result": evaluation_passed,
            "condition_key": condition_key,
            "retry_count": retry_count,
            "evaluation_feedback": evaluation_feedback,
        }

        if condition_key:
            output[condition_key] = execution.context.get(condition_key)

        if evaluation_feedback:
            output["revision_notes"] = evaluation_feedback.get("suggestions", [])
            output["issues"] = evaluation_feedback.get("issues", [])

        if evaluation_passed and execution.context.get("pending_chapter_save"):
            await self._finalize_chapter_after_quality_pass(execution, db)
            output["chapter_finalized"] = bool(execution.context.get("chapter_saved"))

        if not evaluation_passed:
            execution.context["is_retry"] = True
            revision_parts = []
            if evaluation_feedback.get("word_count_check"):
                revision_parts.append(str(evaluation_feedback["word_count_check"].get("message", "")))
            if output.get("issues"):
                revision_parts.extend(str(issue) for issue in output["issues"])
            if output.get("revision_notes"):
                revision_parts.extend(str(note) for note in output["revision_notes"])
            if revision_parts:
                retry_message = "\n".join(part for part in revision_parts if part)
                execution.context["retry_message"] = retry_message
                execution.context["revision_notes"] = output.get("revision_notes", [])
                output["retry_message"] = retry_message
            revision_history = execution.context.get("revision_history")
            if not isinstance(revision_history, list):
                revision_history = []
            revision_entry = self._make_json_safe({
                "attempt": len(revision_history) + 1,
                "condition_node_id": node.id,
                "condition_node_label": node.label,
                "draft_attempt": execution.context.get("chapter_draft_attempt"),
                "content_checksum": execution.context.get("chapter_draft_checksum"),
                "quality_gate_status": execution.context.get("quality_gate_status"),
                "quality_summary": self._build_quality_summary(evaluation_feedback if isinstance(evaluation_feedback, dict) else {}),
                "retry_count": retry_count,
                "requested_at": datetime.now().isoformat(),
            })
            revision_history.append(revision_entry)
            execution.context["revision_history"] = revision_history
            if isinstance(execution.context.get("quality_gate"), dict):
                execution.context["quality_gate"] = {**execution.context["quality_gate"], "status": "revision_requested"}
                execution.context["quality_gate_status"] = "revision_requested"
            await self._broadcast_status(execution.id, "chapter_revision_requested", revision_entry)

        return output

    def _get_latest_completed_node_output(
        self,
        execution: "WorkflowExecution",
    ) -> Dict[str, Any]:
        """获取最近一个已完成节点的输出。"""
        if not execution.node_states:
            return {}

        completed_nodes = [
            (node_id, state) for node_id, state in execution.node_states.items()
            if self._is_completed_status(state.status)
        ]
        if not completed_nodes:
            return {}

        last_node = max(completed_nodes, key=lambda x: x[1].completed_at or datetime.min)
        return last_node[1].output_data or {}

    def _extract_required_character_names(self, scene_directions: Dict[str, Any]) -> List[str]:
        names: List[str] = []
        for key in ("required_characters", "selected_characters", "participating_characters"):
            value = scene_directions.get(key)
            if isinstance(value, str):
                names.extend([item.strip() for item in value.replace("，", ",").split(",") if item.strip()])
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, dict):
                        name = item.get("name") or item.get("character_name") or item.get("id")
                        if name:
                            names.append(str(name))
                    elif item not in (None, ""):
                        names.append(str(item))
        character_roles = scene_directions.get("character_roles")
        if isinstance(character_roles, dict):
            names.extend(str(name) for name in character_roles.keys() if str(name).strip())
        seen: set[str] = set()
        deduped: List[str] = []
        for name in names:
            if name not in seen:
                seen.add(name)
                deduped.append(name)
        return deduped

    def _character_presence_types(self, character: Dict[str, Any]) -> set[str]:
        presence_types = character.get("available_presence_types")
        if isinstance(presence_types, str):
            return {item.strip().lower() for item in presence_types.replace("，", ",").split(",") if item.strip()}
        if isinstance(presence_types, list):
            return {str(item).lower() for item in presence_types if str(item).strip()}
        return {"present", "mentioned", "background"}

    def _can_character_perform(
        self,
        character: Dict[str, Any],
        chapter_num: Optional[int] = None,
    ) -> tuple[bool, str]:
        status = str(character.get("status") or character.get("activity_status") or "active").lower()
        if status in {"inactive", "archived", "dead", "retired", "disabled"}:
            return False, f"status={status}"
        presence_types = self._character_presence_types(character)
        if presence_types and "present" not in presence_types:
            return False, "available_presence_types excludes present"
        if chapter_num is not None:
            debut = character.get("debut_chapter") or character.get("first_appearance_chapter")
            exit_chapter = character.get("exit_chapter") or character.get("last_appearance_chapter")
            try:
                if debut is not None and int(chapter_num) < int(debut):
                    return False, f"before debut_chapter={debut}"
                if exit_chapter is not None and int(chapter_num) >= int(exit_chapter):
                    return False, f"after exit_chapter={exit_chapter}"
            except (TypeError, ValueError):
                pass
        return True, "eligible"

    def _bucket_scene_participants(
        self,
        characters_data: List[Dict[str, Any]],
        all_characters: List[Dict[str, Any]],
        required_names: List[str],
        chapter_num: Optional[int],
    ) -> Dict[str, Any]:
        by_name = {str(c.get("name")): c for c in all_characters if c.get("name")}
        selected_by_name = {str(c.get("name")): c for c in characters_data if c.get("name")}
        performers: List[Dict[str, Any]] = []
        mentioned_characters: List[Dict[str, Any]] = []
        background_characters: List[Dict[str, Any]] = []
        unavailable_characters: List[Dict[str, Any]] = []
        trace: List[Dict[str, Any]] = []
        warnings: List[str] = []

        def add_unique(bucket: List[Dict[str, Any]], character: Dict[str, Any]) -> None:
            key = character.get("id") or character.get("name")
            if not any((item.get("id") or item.get("name")) == key for item in bucket):
                bucket.append(character)

        for char in characters_data:
            can_perform, reason = self._can_character_perform(char, chapter_num)
            if can_perform:
                add_unique(performers, char)
                trace.append({"character": char.get("name"), "bucket": "performers", "reason": reason})
            else:
                presence_types = self._character_presence_types(char)
                if "mentioned" in presence_types or str(char.get("status") or "").lower() == "inactive":
                    add_unique(mentioned_characters, char)
                    trace.append({"character": char.get("name"), "bucket": "mentioned_characters", "reason": reason})
                else:
                    add_unique(unavailable_characters, char)
                    trace.append({"character": char.get("name"), "bucket": "unavailable_characters", "reason": reason})
                    warnings.append(f"角色 {char.get('name')} 不满足正面出场条件：{reason}")

        for name in required_names:
            char = selected_by_name.get(name) or by_name.get(name)
            if not char:
                warnings.append(f"大纲要求角色 {name}，但角色库未匹配到")
                trace.append({"character": name, "bucket": "unavailable_characters", "reason": "not_found"})
                unavailable_characters.append({"name": name, "reason": "not_found"})
                continue
            can_perform, reason = self._can_character_perform(char, chapter_num)
            if can_perform:
                add_unique(performers, char)
                trace.append({"character": char.get("name"), "bucket": "performers", "reason": "required_character"})
            else:
                add_unique(mentioned_characters, char)
                trace.append({"character": char.get("name"), "bucket": "mentioned_characters", "reason": f"required_but_{reason}"})
                warnings.append(f"大纲要求角色 {name}，但当前只能提及：{reason}")

        for char in characters_data:
            if char in performers or char in mentioned_characters or char in unavailable_characters:
                continue
            add_unique(background_characters, char)
            trace.append({"character": char.get("name"), "bucket": "background_characters", "reason": "not_selected_for_front_stage"})

        return {
            "performers": performers,
            "mentioned_characters": mentioned_characters,
            "background_characters": background_characters,
            "unavailable_characters": unavailable_characters,
            "participation_trace": trace,
            "participation_warnings": warnings,
        }

    async def _prepare_multi_character_scene_inputs(
        self,
        node: WorkflowNode,
        execution: "WorkflowExecution",
        db=None,
        *,
        participant_keys: Optional[List[str]] = None,
        default_scene_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """准备多角色场景执行所需的场景方向、角色列表和前置输出。"""
        node_config = node.config or {}
        participant_keys = participant_keys or ["required_characters"]

        scene_directions = dict(execution.context.get("scene_directions", {}) or {})
        execution.context["project_id"] = execution.project_id
        if not scene_directions:
            plotter_agent = await self._get_agent_for_discussion("plotter", execution.project_id)
            if plotter_agent:
                scene_directions = await self._generate_scene_directions(
                    plotter_agent,
                    execution.context,
                ) or {}
                if scene_directions:
                    execution.context["scene_directions"] = scene_directions

        if not scene_directions:
            scene_directions = {
                "scene_type": node_config.get("scene_mode", "interactive"),
                "main_scene": default_scene_name or node.label,
                "atmosphere": "正剧",
                "character_roles": {},
                "plot_focus": "推进剧情",
                "world_context": execution.context.get("world_info", {}).get("description", ""),
            }

        configured_participants: List[str] = []
        for key in participant_keys:
            values = node_config.get(key, []) or []
            if values:
                configured_participants = values
                break

        if configured_participants:
            scene_directions.setdefault("required_characters", configured_participants)

        if node_config.get("need_background_characters"):
            scene_directions["need_background_characters"] = True
            scene_directions["background_character_count"] = node_config.get("background_character_count", 2)
            scene_directions["background_character_type"] = node_config.get("background_character_type", "路人")
            if node_config.get("background_role"):
                scene_directions["background_role"] = node_config.get("background_role")

        all_characters = []
        if db:
            all_characters = await db.get_all_characters(execution.project_id) or []

        previous_node_output = self._get_latest_completed_node_output(execution)
        characters_data: List[Dict[str, Any]] = []

        selected_by_plotter = scene_directions.get("selected_characters", [])
        if selected_by_plotter and all_characters:
            logger.info(f"使用编剧指定的角色: {selected_by_plotter}")
            for char_name in selected_by_plotter:
                char_info = next((c for c in all_characters if c.get("name") == char_name), None)
                if char_info:
                    characters_data.append(char_info)

        if not characters_data and configured_participants and all_characters:
            logger.info(f"使用节点配置的角色: {configured_participants}")
            for char_name in configured_participants:
                char_info = next((c for c in all_characters if c.get("name") == char_name), None)
                if char_info:
                    characters_data.append(char_info)

        if not characters_data and all_characters:
            logger.info("编剧未指定角色，使用智能选择器")
            from app.services.character_selector import (
                extract_scene_context,
                get_character_selector,
            )

            previous_characters = []
            performance_history = execution.context.get("performance_history", [])
            if performance_history:
                previous_characters = performance_history[-1].get("characters", [])

            scene_ctx = extract_scene_context(
                scene_directions=scene_directions,
                previous_output=previous_node_output,
                plot_focus=scene_directions.get("plot_focus", ""),
            )

            required_names = self._extract_required_character_names(scene_directions)
            if required_names:
                scene_ctx.involved_characters = list({*(scene_ctx.involved_characters or []), *required_names})

            selector = get_character_selector()
            characters_data = await selector.select_characters(
                all_characters=all_characters,
                scene_context=scene_ctx,
                previous_characters=previous_characters,
                director_guidance=scene_directions.get("character_guidance"),
                max_characters=node_config.get("max_characters", 5),
                required_characters=required_names,
            )
            logger.info(f"智能选择角色: {[c.get('name') for c in characters_data]}")

        if not characters_data:
            characters_data = list(execution.context.get("characters", []) or [])

        if scene_directions.get("need_background_characters"):
            background_count = scene_directions.get("background_character_count", 2)
            background_type = scene_directions.get("background_character_type", "路人")
            for i in range(background_count):
                characters_data.append({
                    "name": f"{background_type}{i + 1}",
                    "importance_tier": 5,
                    "character_type": "background",
                    "is_protagonist": False,
                    "is_antagonist": False,
                    "personality": "普通人",
                    "background": "普通路人",
                    "speech_pattern": "自然随意",
                    "traits": [],
                    "role_in_scene": scene_directions.get("background_role", "背景群众"),
                })

        required_names = self._extract_required_character_names(scene_directions)
        if characters_data or all_characters or required_names:
            buckets = self._bucket_scene_participants(
                characters_data=characters_data,
                all_characters=all_characters,
                required_names=required_names,
                chapter_num=execution.context.get("chapter_num"),
            )
            characters_data = [*buckets["performers"], *buckets["background_characters"]]
            scene_directions["performers"] = buckets["performers"]
            scene_directions["mentioned_characters"] = buckets["mentioned_characters"]
            scene_directions["background_characters"] = buckets["background_characters"]
            scene_directions["unavailable_characters"] = buckets["unavailable_characters"]
            scene_directions["participation_trace"] = buckets["participation_trace"]
            scene_directions["participation_warnings"] = buckets["participation_warnings"]
            get_workflow_state(execution).merge_runtime_state(
                {
                    "scene_directions": scene_directions,
                    "performers": buckets["performers"],
                    "mentioned_characters": buckets["mentioned_characters"],
                    "background_characters": buckets["background_characters"],
                    "unavailable_characters": buckets["unavailable_characters"],
                    "participation_trace": buckets["participation_trace"],
                    "participation_warnings": buckets["participation_warnings"],
                },
                source="scene_participant_bucketing",
            )

        return {
            "node_config": node_config,
            "scene_directions": scene_directions,
            "characters_data": characters_data,
            "previous_node_output": previous_node_output,
        }

    def _ensure_context_dict_list(self, value: Any) -> List[Dict[str, Any]]:
        """将运行期上下文字段归一化为 dict 列表，支持 JSON 字符串。"""
        if value in (None, ""):
            return []
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                return []
            try:
                value = json.loads(stripped)
            except (json.JSONDecodeError, TypeError):
                return []
        if isinstance(value, dict):
            return [value]
        if isinstance(value, tuple):
            value = list(value)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
        return []

    def _build_character_performance_packet(
        self,
        performance: Dict[str, Any],
        *,
        source_character: Optional[str] = None,
    ) -> Dict[str, Any]:
        """统一角色表演包结构，兼容旧字段并显式标记公开/私有边界。"""
        character = source_character or performance.get("character") or performance.get("agent") or performance.get("source_character") or "未知角色"
        public_content = performance.get("public_content") or performance.get("content") or ""
        dialogue = performance.get("dialogue") or ""
        action = performance.get("action") or ""
        private_thought = performance.get("private_thought") or performance.get("inner_thought") or ""

        packet = {
            "character": character,
            "public_content": public_content,
            "dialogue": dialogue,
            "action": action,
            "private_thought": private_thought,
            "emotion": performance.get("emotion") or performance.get("mood") or "",
            "intent": performance.get("intent") or "",
            "perceived_facts": self._ensure_context_list(performance.get("perceived_facts")),
            "misinterpretations": self._ensure_context_list(performance.get("misinterpretations")),
            "withheld_information": self._ensure_context_list(performance.get("withheld_information")),
            "relationship_delta": self._ensure_context_dict_list(performance.get("relationship_delta")),
            "state_delta": self._ensure_context_dict_list(performance.get("state_delta")),
            "continuity_notes": self._ensure_context_list(performance.get("continuity_notes")),
            "warnings": self._ensure_context_list(performance.get("warnings")),
            "visibility": {
                "public_fields": ["public_content", "dialogue", "action", "emotion"],
                "writer_only_fields": [
                    "private_thought",
                    "intent",
                    "perceived_facts",
                    "misinterpretations",
                    "withheld_information",
                    "relationship_delta",
                    "state_delta",
                    "continuity_notes",
                    "warnings",
                ],
            },
        }
        if performance.get("round") is not None:
            packet["round"] = performance.get("round")
        return packet

    def _build_scene_performance_context(self, role_context: Dict[str, Any]) -> Dict[str, Any]:
        """构建 Writer/Evaluator 可消费的分层场景演绎上下文。"""
        public_performances = self._ensure_context_list(role_context.get("public_performances"))
        packets = self._ensure_context_list(role_context.get("character_performance_packets"))
        if not packets:
            packets = [
                self._build_character_performance_packet(item)
                for item in public_performances
                if isinstance(item, dict)
            ]

        return {
            "public_performances": public_performances,
            "character_performance_packets": packets,
            "private_performances": self._ensure_context_list(role_context.get("private_performances")),
            "relationship_deltas": self._ensure_context_list(role_context.get("relationship_deltas")),
            "state_deltas": self._ensure_context_list(role_context.get("state_deltas")),
            "continuity_notes": self._ensure_context_list(role_context.get("continuity_notes")),
            "performance_warnings": self._ensure_context_list(role_context.get("performance_warnings")),
            "role_performance_gate": role_context.get("role_performance_gate") or {},
            "role_performance_gate_passed": role_context.get("role_performance_gate_passed", True),
            "role_performance_gate_blockers": self._ensure_context_list(role_context.get("role_performance_gate_blockers")),
            "role_performance_gate_warnings": self._ensure_context_list(role_context.get("role_performance_gate_warnings")),
            "last_performance_content": role_context.get("last_performance_content", ""),
            "last_performance_summary": role_context.get("last_performance_summary", ""),
            "last_scene_directions": role_context.get("last_scene_directions", {}),
            "visibility_policy": "public_performances 可进入其他角色上下文；private_performances、relationship/state delta 和 continuity 仅供 Writer/Evaluator/Summarizer 使用。",
        }

    def _extract_role_performance_context(
        self,
        performance_result: Any,
    ) -> Dict[str, Any]:
        """提取场景演绎的公开/私有分层上下文，供后续节点消费。"""
        result = self._ensure_context_dict(performance_result)
        if not result:
            return {}

        extracted: Dict[str, Any] = {}
        for key in (
            "public_performances",
            "private_performances",
            "relationship_deltas",
            "state_deltas",
            "continuity_notes",
            "performance_warnings",
            "character_performance_packets",
            "scene_performance_context",
            "role_performance_gate",
            "role_performance_gate_passed",
            "role_performance_gate_blockers",
            "role_performance_gate_warnings",
        ):
            value = result.get(key)
            if value:
                extracted[key] = value

        if result.get("full_content"):
            extracted["last_performance_content"] = result.get("full_content")
        if result.get("summary"):
            extracted["last_performance_summary"] = result.get("summary")
        if result.get("scene_directions"):
            extracted["last_scene_directions"] = result.get("scene_directions")

        if extracted and "scene_performance_context" not in extracted:
            extracted["scene_performance_context"] = self._build_scene_performance_context(extracted)
        elif extracted.get("scene_performance_context") and "character_performance_packets" not in extracted:
            scene_context = self._ensure_context_dict(extracted.get("scene_performance_context"))
            packets = self._ensure_context_list(scene_context.get("character_performance_packets"))
            if packets:
                extracted["character_performance_packets"] = packets

        return extracted

    def _build_role_performance_gate(
        self,
        performance_result: Dict[str, Any],
        source_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """确定性检查角色演绎素材的公开/私有边界和出场约束。"""
        source_context = source_context or {}
        constraints_context = dict(source_context)
        if performance_result.get("scene_directions"):
            constraints_context["scene_directions"] = performance_result.get("scene_directions")
        constraints = self._build_character_constraint_state(constraints_context)

        public_performances = self._ensure_context_list(performance_result.get("public_performances"))
        if not public_performances:
            public_performances = self._ensure_context_list(performance_result.get("performances"))
        private_performances = self._ensure_context_list(performance_result.get("private_performances"))
        relationship_deltas = self._ensure_context_list(performance_result.get("relationship_deltas"))
        state_deltas = self._ensure_context_list(performance_result.get("state_deltas"))
        performance_warnings = self._ensure_context_list(performance_result.get("performance_warnings"))

        blockers: List[str] = []
        warnings: List[str] = []
        checks = {
            "private_leakage": [],
            "forbidden_participation": [],
            "performance_warnings": [],
            "delta_schema": [],
        }

        public_text = "\n".join(
            str(item.get("public_content") or item.get("content") or item.get("dialogue") or "")
            for item in public_performances
            if isinstance(item, dict)
        )
        public_text += "\n" + str(performance_result.get("full_content") or "")

        private_fragments: List[Dict[str, str]] = []
        for item in private_performances:
            if not isinstance(item, dict):
                continue
            agent = str(item.get("agent") or item.get("source_character") or "未知角色")
            for key in ("private_thought", "intent"):
                value = str(item.get(key) or "").strip()
                if len(value) >= 8:
                    private_fragments.append({"agent": agent, "field": key, "value": value})
            for private_key in ("withheld_information", "misinterpretations"):
                for value in self._ensure_context_list(item.get(private_key)):
                    text = str(value).strip()
                    if len(text) >= 6:
                        private_fragments.append({"agent": agent, "field": private_key, "value": text})

        for fragment in private_fragments:
            value = fragment["value"]
            if value and value in public_text:
                issue = f"私有演绎内容泄露到公开表演：{fragment['agent']}.{fragment['field']}"
                blockers.append(issue)
                checks["private_leakage"].append(issue)

        for item in public_performances:
            if not isinstance(item, dict):
                continue
            agent = str(item.get("agent") or item.get("character") or "未知角色")
            for key in ("private_thought", "inner_thought", "intent", "withheld_information", "misinterpretations"):
                raw_value = item.get(key)
                values = self._ensure_context_list(raw_value) if isinstance(raw_value, (list, tuple)) else [raw_value]
                for value in values:
                    text = str(value or "").strip()
                    if len(text) >= 6:
                        issue = f"公开表演携带私有字段：{agent}.{key}"
                        blockers.append(issue)
                        checks["private_leakage"].append(issue)

        forbidden_names = set(constraints.get("forbidden_direct_appearance_names") or [])
        mentioned_names = set(constraints.get("mentioned_only_names") or [])
        present_names = set(constraints.get("present_character_names") or [])
        blocked_names = (forbidden_names | mentioned_names) - present_names
        direct_markers = [
            "说", "问", "答", "喊", "低声", "开口", "回应", "走", "站", "看", "伸手", "转身", "出现", "参与", "进入",
            "dialogue", "said", "asked", "replied",
        ]

        for item in public_performances:
            if not isinstance(item, dict):
                continue
            agent = str(item.get("agent") or item.get("character") or "")
            content = str(item.get("public_content") or item.get("content") or item.get("dialogue") or "")
            if agent and agent in blocked_names:
                issue = f"不可正面出场角色 {agent} 被作为公开表演者输出"
                blockers.append(issue)
                checks["forbidden_participation"].append(issue)
            for name in sorted(blocked_names, key=len, reverse=True):
                if not name or name not in content:
                    continue
                idx = content.find(name)
                snippet = content[max(0, idx - 20): idx + len(name) + 35]
                if any(marker in snippet for marker in direct_markers):
                    issue = f"不可正面出场角色 {name} 疑似被写成公开行动/发言者：{snippet}"
                    blockers.append(issue)
                    checks["forbidden_participation"].append(issue)
                    break

        for warning_item in performance_warnings:
            warning_text = ""
            if isinstance(warning_item, dict):
                warning_text = str(warning_item.get("warning") or warning_item.get("message") or warning_item)
            else:
                warning_text = str(warning_item)
            if not warning_text:
                continue
            checks["performance_warnings"].append(warning_text)
            if any(keyword in warning_text for keyword in ("OOC", "信息越界", "出场越界", "缺资源", "未授权", "forbidden", "unavailable")):
                blockers.append(f"角色演绎 warning 需阻断：{warning_text}")
            else:
                warnings.append(f"角色演绎 warning：{warning_text}")

        valid_relationship_dimensions = {"trust", "fear", "suspicion", "debt", "affection", "hostility", "respect"}
        for delta in relationship_deltas:
            if not isinstance(delta, dict):
                issue = f"relationship_delta 不是对象：{delta}"
                warnings.append(issue)
                checks["delta_schema"].append(issue)
                continue
            if not delta.get("target_character"):
                issue = f"relationship_delta 缺少 target_character：{delta}"
                warnings.append(issue)
                checks["delta_schema"].append(issue)
            dimension = str(delta.get("dimension") or "")
            if dimension and dimension not in valid_relationship_dimensions:
                issue = f"relationship_delta dimension 非标准值：{dimension}"
                warnings.append(issue)
                checks["delta_schema"].append(issue)

        for delta in state_deltas:
            if not isinstance(delta, dict):
                issue = f"state_delta 不是对象：{delta}"
                warnings.append(issue)
                checks["delta_schema"].append(issue)
                continue
            if not delta.get("field") or not delta.get("change"):
                issue = f"state_delta 缺少 field/change：{delta}"
                warnings.append(issue)
                checks["delta_schema"].append(issue)

        unique_blockers = list(dict.fromkeys(blockers))
        unique_warnings = list(dict.fromkeys(warnings))
        return {
            "passed": not unique_blockers,
            "blockers": unique_blockers,
            "warnings": unique_warnings,
            "checks": checks,
        }

    def _attach_role_performance_context(
        self,
        context: Dict[str, Any],
        source_context: Dict[str, Any],
    ) -> None:
        """把角色演绎分层上下文注入当前节点输入。"""
        performance_result = source_context.get("performance_result")
        role_context = self._extract_role_performance_context(performance_result)

        for key in (
            "public_performances",
            "private_performances",
            "relationship_deltas",
            "state_deltas",
            "continuity_notes",
            "performance_warnings",
            "role_performance_gate",
            "role_performance_gate_passed",
            "role_performance_gate_blockers",
            "role_performance_gate_warnings",
            "last_performance_content",
            "last_performance_summary",
            "last_scene_directions",
        ):
            if key not in role_context and source_context.get(key):
                role_context[key] = source_context.get(key)

        if role_context:
            context.setdefault("role_performance_context", role_context)
            for key, value in role_context.items():
                context.setdefault(key, value)

    def _sync_role_performance_context(
        self,
        execution: "WorkflowExecution",
        performance_result: Dict[str, Any],
    ) -> None:
        """把 SceneCoordinator 的分层输出同步到 execution.context。"""
        role_gate = self._build_role_performance_gate(performance_result, execution.context)
        performance_result["role_performance_gate"] = role_gate
        performance_result["role_performance_gate_passed"] = role_gate.get("passed", False)
        performance_result["role_performance_gate_blockers"] = role_gate.get("blockers", [])
        performance_result["role_performance_gate_warnings"] = role_gate.get("warnings", [])

        role_context = self._extract_role_performance_context(performance_result)
        if not role_context:
            return

        execution.context["role_performance_context"] = role_context
        for key, value in role_context.items():
            execution.context[key] = value

    def _sync_scene_character_context(
        self,
        execution: "WorkflowExecution",
        performance_result: Dict[str, Any],
    ) -> None:
        """将多角色场景的公开结果同步到通用角色上下文。"""
        for perf in performance_result.get("performances", []):
            character_name = perf.get("agent") or perf.get("character")
            content = perf.get("public_content") or perf.get("content") or perf.get("dialogue")
            emotion = perf.get("emotion") or perf.get("mood")

            if character_name and content:
                execution.context.setdefault("character_dialogues", []).append({
                    "character": character_name,
                    "dialogue": content,
                })
            if character_name and emotion:
                execution.context.setdefault("character_moods", {})[character_name] = emotion

    async def _execute_multi_character_scene(
        self,
        node: WorkflowNode,
        execution: "WorkflowExecution",
        db=None,
        *,
        participant_keys: Optional[List[str]] = None,
        default_scene_name: Optional[str] = None,
        target_word_multiplier: float = 1.0,
        default_iteration_count: int = 3,
    ) -> Dict[str, Any]:
        """执行共享的多角色场景链路，供 scene_performance 与 group_discussion 复用。"""
        try:
            prepared = await self._prepare_multi_character_scene_inputs(
                node,
                execution,
                db,
                participant_keys=participant_keys,
                default_scene_name=default_scene_name,
            )
            node_config = prepared["node_config"]
            scene_directions = prepared["scene_directions"]
            characters_data = prepared["characters_data"]
            previous_node_output = prepared["previous_node_output"]

            logger.info(
                f"多角色场景执行: node={node.id}, scene={scene_directions.get('main_scene', node.label)}, "
                f"characters={len(characters_data)}"
            )

            await self._broadcast_status(execution.id, "performance_started", {
                "node_id": node.id,
                "scene_type": scene_directions.get("scene_type", "interactive"),
                "main_scene": scene_directions.get("main_scene", default_scene_name or node.label),
                "characters": [c.get("name", "未知") for c in characters_data],
                "performance_topic": f"《{scene_directions.get('main_scene', default_scene_name or node.label)}》",
            })

            from app.agents.scene_coordinator import SceneCoordinatorAgent

            existing_agent = await self._get_agent_for_discussion("character", execution.project_id)
            model = existing_agent.model if existing_agent else None

            scene_coordinator = SceneCoordinatorAgent(
                model=model,
                project_id=execution.project_id,
                db=db,
            )

            if self._broadcast_discussion_message:
                async def stream_callback(content: str):
                    await self._broadcast_status(execution.id, "stream", {
                        "content": content,
                        "type": "character_dialogue",
                    })

                scene_coordinator._stream_callback = stream_callback
            iteration_count = node_config.get("iteration_count", default_iteration_count)
            plot_intents = execution.context.get("intents", [])
            chapter_word_count = execution.context.get("target_word_count", 2000)
            configured_target = node_config.get("target_word_count", 0) or 0
            if configured_target:
                target_word_count = configured_target
            else:
                target_word_count = max(1, int(chapter_word_count * target_word_multiplier))

            coordinator_input = {
                "scene_directions": scene_directions,
                "characters": characters_data,
                "world_info": execution.context.get("world_info", {}),
                "previous_output": previous_node_output,
                "mode": scene_directions.get("scene_type", "interactive"),
                "iteration_count": iteration_count,
                "target_word_count": target_word_count,
                "reference_mode": True,
                "material_role": "reference_only",
                "usage_instruction": self._build_workflow_reference_material_instruction(),
                "plot_intents": plot_intents,
                "chapter_word_count": chapter_word_count,
            }

            logger.info(
                f"场景执行参数: {iteration_count} 轮迭代, 目标 {target_word_count} 字, "
                f"{len(characters_data)} 个角色"
            )

            result = await scene_coordinator.execute(coordinator_input)
            if not result.success:
                logger.error(f"场景协调执行失败: {result.error}")
                return {"error": result.error, "status": "failed"}

            performance_result = self._get_response_payload(result)
            if isinstance(performance_result, dict):
                performance_result = dict(performance_result)
            else:
                performance_result = {}
            performance_messages = list(performance_result.get("performances", []))

            for msg in performance_messages:
                await self._broadcast_discussion_message_event(execution.id, msg)
                await asyncio.sleep(0.2)

            performance_result.update({
                "status": "completed",
                "scene_directions": scene_directions,
                "scene_type": scene_directions.get("scene_type", "interactive"),
                "characters": performance_result.get("characters") or [c.get("name", "未知") for c in characters_data],
                "messages": performance_messages,
                "material_role": "reference_only",
                "reference_mode": True,
                "usage_instruction": self._build_workflow_reference_material_instruction(),
                "performers": scene_directions.get("performers", []),
                "mentioned_characters": scene_directions.get("mentioned_characters", []),
                "background_characters": scene_directions.get("background_characters", []),
                "unavailable_characters": scene_directions.get("unavailable_characters", []),
                "participation_trace": scene_directions.get("participation_trace", []),
                "participation_warnings": scene_directions.get("participation_warnings", []),
                "timestamp": datetime.now().isoformat(),
            })

            self._sync_role_performance_context(execution, performance_result)

            summarizer_agent = await self._get_agent_for_discussion("summarizer", execution.project_id)
            if summarizer_agent and performance_messages:
                summary = await self._generate_performance_summary(
                    summarizer_agent,
                    scene_directions,
                    performance_messages,
                    project_id=execution.project_id,
                    role_performance_gate=performance_result.get("role_performance_gate", {}),
                )
                if summary:
                    performance_messages.append(summary)
                    await self._broadcast_discussion_message_event(execution.id, summary)

            performance_summary = self._extract_discussion_summary_text(performance_result)
            performance_result.setdefault("summary", performance_summary)
            performance_result.setdefault("topic", f"《{scene_directions.get('main_scene', default_scene_name or node.label)}》角色演绎")
            performance_result.setdefault("discussion_topic", performance_result.get("topic"))
            performance_result.setdefault("leader", "场景协调器")
            performance_result.setdefault("leader_type", "scene_coordinator")

            execution.context["performance_result"] = performance_result
            execution.context["dialogues"] = performance_messages
            execution.context["last_performance_content"] = performance_result.get("full_content", "")

            performance_history = execution.context.get("performance_history", [])
            performance_history.append(performance_result)
            execution.context["performance_history"] = performance_history

            self._sync_scene_character_context(execution, performance_result)

            actual_word_count = performance_result.get("actual_word_count", 0)
            actual_iterations = performance_result.get("iteration_count", iteration_count)
            logger.info(
                f"多角色场景完成: {len(performance_messages)} 条表演, "
                f"{actual_iterations} 轮迭代, {actual_word_count} 字"
            )

            return {
                "status": "completed",
                "mode": "performance",
                "scene": scene_directions.get("main_scene", default_scene_name or node.label),
                "scene_type": scene_directions.get("scene_type", "interactive"),
                "characters": [c.get("name", "未知") for c in characters_data],
                "messages": performance_messages,
                "full_content": performance_result.get("full_content", ""),
                "public_performances": performance_result.get("public_performances", []),
                "private_performances": performance_result.get("private_performances", []),
                "relationship_deltas": performance_result.get("relationship_deltas", []),
                "state_deltas": performance_result.get("state_deltas", []),
                "continuity_notes": performance_result.get("continuity_notes", []),
                "performance_warnings": performance_result.get("performance_warnings", []),
                "character_performance_packets": performance_result.get("character_performance_packets", []),
                "scene_performance_context": performance_result.get("scene_performance_context") or execution.context.get("scene_performance_context", {}),
                "role_performance_gate": performance_result.get("role_performance_gate", {}),
                "role_performance_gate_passed": performance_result.get("role_performance_gate_passed", False),
                "role_performance_gate_blockers": performance_result.get("role_performance_gate_blockers", []),
                "role_performance_gate_warnings": performance_result.get("role_performance_gate_warnings", []),
                "role_performance_context": execution.context.get("role_performance_context", {}),
                "iteration_count": actual_iterations,
                "performance_word_count": actual_word_count,
                "performance_target_word_count": target_word_count,
                "performance_result": performance_result,
                "participation_trace": scene_directions.get("participation_trace", []),
                "participation_warnings": scene_directions.get("participation_warnings", []),
            }
        except Exception as e:
            logger.error(f"多角色场景执行失败: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return {"error": str(e), "status": "failed"}

    async def _execute_scene_performance_node(
        self,
        node: WorkflowNode,
        execution: "WorkflowExecution",
        db=None,
    ) -> Dict[str, Any]:
        """
        执行场景演绎节点 - 多个角色Agent同台飙戏

        这是专门用于多角色演绎的节点类型，与 GROUP_DISCUSSION 节点区分。
        默认按大纲/前文智能选择参与者；若节点或编剧显式指定角色，则优先使用显式配置。
        """
        logger.info(f"执行场景演绎节点: {node.label}")
        return await self._execute_multi_character_scene(
            node,
            execution,
            db,
            participant_keys=["required_characters"],
            default_scene_name=node.label,
            target_word_multiplier=0.25,
            default_iteration_count=2,
        )

    # 等待用户确认的超时时间（秒）
    USER_CONFIRMATION_TIMEOUT = 60

    def _ensure_discussion_asset_list(self, value: Any) -> List[Any]:
        """将 discussion asset 字段归一化为列表。"""
        if value in (None, ""):
            return []
        if isinstance(value, list):
            return list(value)
        if isinstance(value, tuple):
            return list(value)
        return [value]

    async def check_chapter_resource_readiness(
        self,
        project_id: str,
        context: Dict[str, Any],
        db,
    ) -> Dict[str, Any]:
        """检查章节资源 readiness，供 workflow 与直连章节生成入口复用。"""
        if db and not context.get("_chapter_outline_resolved_for_start"):
            await self._resolve_approved_outline_for_chapter_start(project_id, context)
        return await self._check_chapter_resource_readiness(project_id, context, db)

    async def _resolve_approved_outline_for_chapter_start(
        self,
        project_id: str,
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """解析并校验章节启动所绑定的已审批大纲版本。"""
        from app.services.plot_outline_service import get_plot_outline_service

        plot_service = get_plot_outline_service()
        chapter_num = self._parse_chapter_number(context.get("chapter_num") or context.get("chapter_number"))
        chapter_outline = self._ensure_context_dict(context.get("chapter_outline"))
        requested_outline_id = context.get("chapter_outline_id") or context.get("outline_id") or chapter_outline.get("id")
        requested_outline_id = str(requested_outline_id) if requested_outline_id else None

        try:
            outline = None
            if requested_outline_id and hasattr(plot_service, "get_outline_by_id"):
                outline = await plot_service.get_outline_by_id(str(project_id), requested_outline_id)
                if not outline:
                    raise ChapterReadinessBlockedError({
                        "readiness_status": "blocked",
                        "block_reason": "outline_not_found",
                        "message": "选中的章节大纲不存在，不能启动章节生成工作流。",
                        "chapter_num": chapter_num,
                        "chapter_outline_id": requested_outline_id,
                        "outline_status": None,
                        "blocking_requirements": [],
                        "advisory_requirements": [],
                    })
            elif chapter_num is not None:
                outline = await plot_service.get_outline(str(project_id), chapter_num)

            if not outline:
                raise ChapterReadinessBlockedError({
                    "readiness_status": "blocked",
                    "block_reason": "approved_outline_missing",
                    "message": f"第 {chapter_num or '未知'} 章没有已审批大纲，不能启动章节生成工作流。",
                    "chapter_num": chapter_num,
                    "chapter_outline_id": requested_outline_id,
                    "outline_status": None,
                    "blocking_requirements": [],
                    "advisory_requirements": [],
                })

            outline_payload = self._outline_to_runtime_dict(outline)
            resolved_chapter_num = self._parse_chapter_number(
                outline_payload.get("chapter_number") or outline_payload.get("chapter_num")
            )
            if chapter_num is not None and resolved_chapter_num is not None and chapter_num != resolved_chapter_num:
                raise ChapterReadinessBlockedError({
                    "readiness_status": "blocked",
                    "block_reason": "outline_chapter_mismatch",
                    "message": "选中的章节大纲与请求章节号不一致，不能启动章节生成工作流。",
                    "chapter_num": chapter_num,
                    "chapter_outline_id": outline_payload.get("id") or requested_outline_id,
                    "outline_status": str(outline_payload.get("status") or "").lower() or None,
                    "blocking_requirements": [],
                    "advisory_requirements": [],
                })

            outline_status = str(outline_payload.get("status") or "").lower()
            if outline_status != "approved" or outline_payload.get("next_outline_id"):
                raise ChapterReadinessBlockedError({
                    "readiness_status": "blocked",
                    "block_reason": "outline_not_current_approved",
                    "message": f"第 {resolved_chapter_num or chapter_num or '未知'} 章大纲不是当前已审批版本，不能启动章节生成工作流。",
                    "chapter_num": resolved_chapter_num or chapter_num,
                    "chapter_outline_id": outline_payload.get("id") or requested_outline_id,
                    "outline_status": outline_status,
                    "blocking_requirements": [],
                    "advisory_requirements": [],
                })

            context["chapter_num"] = resolved_chapter_num or chapter_num
            context["chapter_outline_id"] = str(outline_payload.get("id"))
            context["chapter_outline"] = outline_payload
            context.setdefault("chapter_title", outline_payload.get("title", f"第{context.get('chapter_num')}章"))
            context.setdefault("chapter_summary", outline_payload.get("summary", ""))
            outline_target_word_count = outline_payload.get("target_word_count")
            if outline_target_word_count and not context.get("target_word_count"):
                context["target_word_count"] = outline_target_word_count
            if outline_target_word_count and not context.get("chapter_target_word_count"):
                context["chapter_target_word_count"] = outline_target_word_count
            context.setdefault(
                "chapter_outline_source",
                "selected_outline" if requested_outline_id else "auto_loaded",
            )
            context["_chapter_outline_resolved_for_start"] = True
            logger.info("章节启动绑定已审批大纲版本: %s", context["chapter_outline_id"])
            return outline_payload
        except ChapterReadinessBlockedError:
            raise
        except Exception as exc:
            logger.warning("加载章节大纲失败: %s", exc)
            raise ChapterReadinessBlockedError({
                "readiness_status": "blocked",
                "block_reason": "outline_load_failed",
                "message": f"第 {chapter_num or '未知'} 章大纲加载失败，不能启动章节生成工作流。",
                "chapter_num": chapter_num,
                "chapter_outline_id": requested_outline_id,
                "outline_status": None,
                "blocking_requirements": [],
                "advisory_requirements": [],
            })

    def _outline_to_runtime_dict(self, outline: Any) -> Dict[str, Any]:
        """将 ChapterOutline / dict / ORM row 转为运行期大纲字典。"""
        if isinstance(outline, dict):
            return dict(outline)
        if hasattr(outline, "model_dump"):
            return outline.model_dump(mode="json")
        if hasattr(outline, "dict"):
            return outline.dict()
        payload: Dict[str, Any] = {}
        for key in [
            "id", "project_id", "chapter_number", "chapter_num", "title", "summary",
            "status", "chapter_goals", "target_word_count", "previous_outline_id", "next_outline_id",
        ]:
            if hasattr(outline, key):
                payload[key] = getattr(outline, key)
        return payload

    async def _check_chapter_resource_readiness(
        self,
        project_id: str,
        context: Dict[str, Any],
        db,
    ) -> Dict[str, Any]:
        """启动章节工作流前检查未解决 blocking 资源需求。"""
        if not db or not hasattr(db, "get_outline_resource_requirements"):
            return {}

        chapter_num = self._parse_chapter_number(context.get("chapter_num") or context.get("chapter_number"))
        chapter_outline = self._ensure_context_dict(context.get("chapter_outline"))
        outline_id = context.get("chapter_outline_id") or context.get("outline_id") or chapter_outline.get("id")
        outline_id = str(outline_id) if outline_id else None
        if chapter_num is None and not outline_id:
            return {}

        if outline_id:
            raw_requirements = await db.get_outline_resource_requirements(
                project_id=project_id,
                outline_id=outline_id,
                chapter_num=chapter_num,
            )
        elif chapter_num is not None:
            raw_requirements = await db.get_outline_resource_requirements(
                project_id=project_id,
                chapter_num=chapter_num,
            )
        else:
            raw_requirements = []

        requirements: List[Dict[str, Any]] = []
        for item in raw_requirements or []:
            if not isinstance(item, dict):
                continue
            item_outline_id = item.get("outline_id")
            if outline_id and item_outline_id and str(item_outline_id) != outline_id:
                continue
            requirements.append(item)

        unresolved_statuses = {"pending", "in_progress"}
        blocking_requirements = [
            item for item in requirements
            if str(item.get("severity") or "").lower() == "blocking"
            and str(item.get("status") or "pending").lower() in unresolved_statuses
        ]
        advisory_requirements = [
            item for item in requirements
            if str(item.get("severity") or "").lower() == "advisory"
            and str(item.get("status") or "pending").lower() in unresolved_statuses
        ]

        readiness = None
        if chapter_num is not None and hasattr(db, "update_chapter_resource_readiness"):
            readiness = await db.update_chapter_resource_readiness(
                project_id=project_id,
                outline_id=outline_id,
                chapter_num=chapter_num,
            )

        readiness_context = {
            "readiness_status": "blocked" if blocking_requirements else (
                "ready_with_warnings" if advisory_requirements else "ready"
            ),
            "chapter_num": chapter_num,
            "chapter_outline_id": outline_id,
            "readiness": readiness,
            "blocking_requirements": blocking_requirements,
            "advisory_requirements": advisory_requirements,
        }
        if blocking_requirements:
            raise ChapterReadinessBlockedError(readiness_context)
        return readiness_context

    def _ensure_context_dict(self, value: Any) -> Dict[str, Any]:
        """将运行期上下文字段归一化为 dict，避免对字符串/列表调用 .get。"""
        if isinstance(value, dict):
            return value
        return {}

    def _ensure_context_list(self, value: Any) -> List[Any]:
        """将运行期上下文字段归一化为 list。"""
        if value in (None, ""):
            return []
        if isinstance(value, list):
            return value
        if isinstance(value, tuple):
            return list(value)
        return [value]

    def _coerce_context_text(self, value: Any, fallback: str = "") -> str:
        """将上下文字段安全转为文本。"""
        if isinstance(value, str):
            return value
        if isinstance(value, (int, float, bool)):
            return str(value)
        return fallback

    def _parse_chapter_number(self, value: Any) -> Optional[int]:
        """安全解析章节序号。"""
        try:
            if value in (None, ""):
                return None
            return int(value)
        except (TypeError, ValueError):
            return None

    def _chapter_number_from_outline_item(self, item: Any) -> Optional[int]:
        """从大纲项中提取章节序号。"""
        if not isinstance(item, dict):
            return None
        for key in ("chapter_num", "chapter_number", "number", "index", "order"):
            chapter_number = self._parse_chapter_number(item.get(key))
            if chapter_number is not None:
                return chapter_number
        return None

    def _outline_item_summary(self, item: Any) -> str:
        """提取大纲项的紧凑摘要。"""
        if isinstance(item, dict):
            title = self._extract_context_item_text(item, "title", "name")
            summary = self._extract_context_item_text(
                item,
                "goal",
                "summary",
                "description",
                "content",
                "event",
                "events",
                "key_points",
            )
            if title and summary:
                return f"{title}: {summary}"
            return title or summary
        return self._coerce_context_text(item).strip()

    def _build_upcoming_outline_context(
        self,
        context: Dict[str, Any],
        *,
        limit: int = 3,
    ) -> List[Dict[str, Any]]:
        """基于已有后续大纲构建 Writer/Evaluator 可用的后续剧情参考。"""
        chapter_num = self._parse_chapter_number(context.get("chapter_num") or context.get("chapter_number")) or 1
        candidates: List[tuple[Optional[int], Any]] = []

        chapter_goals = self._ensure_context_list(context.get("chapter_goals"))
        for index, goal in enumerate(chapter_goals, start=1):
            if index > chapter_num:
                candidates.append((index, goal))

        plot_outline = self._ensure_context_list(context.get("plot_outline"))
        for index, item in enumerate(plot_outline, start=1):
            item_chapter = self._chapter_number_from_outline_item(item) or index
            if item_chapter > chapter_num:
                candidates.append((item_chapter, item))

        chapter_outline = context.get("chapter_outline")
        if isinstance(chapter_outline, dict):
            for key, item in chapter_outline.items():
                item_chapter = self._parse_chapter_number(key) or self._chapter_number_from_outline_item(item)
                if item_chapter is not None and item_chapter > chapter_num:
                    candidates.append((item_chapter, item))

        seen: set[tuple[Optional[int], str]] = set()
        upcoming: List[Dict[str, Any]] = []
        for chapter_number, item in sorted(candidates, key=lambda pair: pair[0] or 999999):
            summary = self._outline_item_summary(item)
            if not summary:
                continue
            fingerprint = (chapter_number, summary)
            if fingerprint in seen:
                continue
            seen.add(fingerprint)
            upcoming.append({
                "chapter_num": chapter_number,
                "summary": summary,
            })
            if len(upcoming) >= limit:
                break
        return upcoming

    def _attach_upcoming_outline_context(self, context: Dict[str, Any]) -> None:
        """把后续大纲参考写入上下文；没有后续大纲时显式标记为 none。"""
        if context.get("upcoming_outline_context"):
            return
        upcoming = self._build_upcoming_outline_context(context)
        context["upcoming_outline_context"] = upcoming
        context["upcoming_outline_policy"] = (
            "use_existing_upcoming_outline" if upcoming else "no_upcoming_outline_follow_current_outline"
        )

    def _extract_context_item_text(self, item: Any, *keys: str) -> str:
        """从 dict 或文本项中提取用于上下文的文本。"""
        if isinstance(item, dict):
            for key in keys:
                value = item.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()
                if isinstance(value, list):
                    text_parts = [str(part).strip() for part in value if part not in (None, "")]
                    if text_parts:
                        return "；".join(text_parts)
            return ""
        return self._coerce_context_text(item).strip()

    def _extract_discussion_summary_text(self, discussion: Optional[Dict[str, Any]]) -> str:
        """提取讨论摘要文本，兼容 meeting/performance 两种输出。"""
        if not isinstance(discussion, dict):
            return ""

        for key in ("summary", "full_content"):
            value = discussion.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()

        performance_result = discussion.get("performance_result")
        if isinstance(performance_result, dict):
            for key in ("summary", "full_content"):
                value = performance_result.get(key)
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

    def _collect_discussion_assets(self, discussion_result: Dict[str, Any], *keys: str) -> List[Any]:
        """从多个候选字段中收集资产列表。"""
        assets: List[Any] = []
        for key in keys:
            assets.extend(self._ensure_discussion_asset_list(discussion_result.get(key)))
        return assets

    def _extract_discussion_assets_from_text(self, discussion_result: Dict[str, Any]) -> Dict[str, List[Any]]:
        """从讨论文本中的结构化 JSON 区块提取资产提案。"""
        text_parts: List[str] = []
        for key in ("summary", "full_content"):
            value = discussion_result.get(key)
            if isinstance(value, str) and value.strip():
                text_parts.append(value)

        for message in discussion_result.get("messages", []) or []:
            if isinstance(message, dict):
                content = message.get("content")
                if isinstance(content, str) and content.strip():
                    text_parts.append(content)

        text = "\n".join(text_parts)
        if not text:
            return {}

        candidates: List[str] = []
        for match in re.finditer(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", text, re.IGNORECASE):
            candidates.append(match.group(1))

        marker_patterns = [
            r"讨论资产提案\s*[:：]\s*(\{[\s\S]*?\})(?:\n\s*(?:请确认|是否同意|$))",
            r"discussion_assets\s*[:：]?\s*(\{[\s\S]*?\})(?:\n\s*(?:请确认|是否同意|$))",
        ]
        for pattern in marker_patterns:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                candidates.append(match.group(1))

        extracted: Dict[str, List[Any]] = {}
        field_aliases = {
            "plot_updates": ("plot_updates", "剧情加码", "剧情更新"),
            "hooks": ("hooks", "hook_candidates", "hooks_to_plant", "伏笔"),
            "lore_candidates": ("lore_candidates", "lores", "new_lores", "设定", "世界观设定"),
            "region_candidates": ("region_candidates", "regions", "new_regions", "map_candidates", "地点", "地图地点"),
            "character_candidates": ("character_candidates", "new_characters", "characters_to_create", "角色"),
            "character_location_updates": (
                "character_location_updates",
                "location_updates",
                "character_locations",
                "角色位置更新",
                "角色位置",
            ),
            "state_changes": (
                "state_changes",
                "narrative_state_changes",
                "state_change_candidates",
                "剧情状态变更",
                "状态变更",
                "剧情变化",
            ),
        }

        for candidate in candidates:
            try:
                payload = json.loads(candidate)
            except Exception:
                continue
            if not isinstance(payload, dict):
                continue

            asset_payload = payload.get("discussion_assets") if isinstance(payload.get("discussion_assets"), dict) else payload
            for target_key, aliases in field_aliases.items():
                for alias in aliases:
                    if alias in asset_payload:
                        extracted.setdefault(target_key, []).extend(
                            self._ensure_discussion_asset_list(asset_payload.get(alias))
                        )
                        break

        return extracted

    def _build_discussion_asset_preview(self, bundle: Dict[str, Any]) -> Dict[str, Any]:
        """构建用于前端确认与下游消费的讨论资产预览。"""
        def _labels(items: List[Any]) -> List[str]:
            labels: List[str] = []
            for item in items[:5]:
                if isinstance(item, dict):
                    label = item.get("title") or item.get("name") or item.get("id")
                    if label:
                        labels.append(str(label))
                elif item not in (None, ""):
                    labels.append(str(item))
            return labels

        plot_updates = bundle.get("plot_updates", [])
        hooks = bundle.get("hooks", [])
        lore_candidates = bundle.get("lore_candidates", [])
        region_candidates = bundle.get("region_candidates", [])
        character_candidates = bundle.get("character_candidates", [])
        character_location_updates = bundle.get("character_location_updates", [])
        state_changes = bundle.get("state_changes", [])
        source_metadata = bundle.get("source_metadata", {})

        return {
            "topic": source_metadata.get("topic", ""),
            "mode": source_metadata.get("mode", "meeting"),
            "plot_update_count": len(plot_updates),
            "hook_count": len(hooks),
            "lore_count": len(lore_candidates),
            "region_count": len(region_candidates),
            "character_count": len(character_candidates),
            "character_location_update_count": len(character_location_updates),
            "state_change_count": len(state_changes),
            "plot_update_titles": _labels(plot_updates),
            "hook_titles": _labels(hooks),
            "lore_titles": _labels(lore_candidates),
            "region_titles": _labels(region_candidates),
            "character_titles": _labels(character_candidates),
            "character_location_update_titles": _labels(character_location_updates),
            "state_change_titles": _labels(state_changes),
        }

    def _build_discussion_asset_bundle(
        self,
        execution: "WorkflowExecution",
        discussion_result: Dict[str, Any],
        node_id: str,
        discussion_mode: str,
    ) -> Dict[str, Any]:
        """构建统一的 discussion asset bundle。"""
        summary = self._extract_discussion_summary_text(discussion_result)
        extracted_assets = self._extract_discussion_assets_from_text(discussion_result)
        for key, assets in extracted_assets.items():
            if assets and not discussion_result.get(key):
                discussion_result[key] = assets

        plot_updates = self._collect_discussion_assets(discussion_result, "plot_updates")
        if summary:
            plot_updates = [{
                "type": "discussion_summary",
                "topic": discussion_result.get("discussion_topic") or discussion_result.get("topic") or execution.context.get("chapter_title", "当前章节"),
                "summary": summary,
                "mode": discussion_mode,
                "scene": discussion_result.get("scene", ""),
                "source": "group_discussion",
            }, *plot_updates]

        raw_lore_candidates = self._collect_discussion_assets(
            discussion_result,
            "lore_candidates",
            "lores",
            "new_lores",
            "setting_candidates",
        )
        raw_region_candidates = self._collect_discussion_assets(
            discussion_result,
            "region_candidates",
            "regions",
            "new_regions",
            "map_candidates",
        )
        classified_regions, classified_location_lores = self._split_discussion_location_assets(raw_region_candidates)

        bundle = {
            "plot_updates": plot_updates,
            "hooks": self._collect_discussion_assets(discussion_result, "hooks", "hook_candidates", "hooks_to_plant", "new_hooks"),
            "lore_candidates": [*raw_lore_candidates, *classified_location_lores],
            "region_candidates": classified_regions,
            "character_candidates": self._collect_discussion_assets(discussion_result, "character_candidates", "new_characters", "characters_to_create"),
            "character_location_updates": self._collect_discussion_assets(
                discussion_result,
                "character_location_updates",
                "location_updates",
                "character_locations",
            ),
            "state_changes": self._collect_discussion_assets(
                discussion_result,
                "state_changes",
                "narrative_state_changes",
                "state_change_candidates",
            ),
            "persistence_preview": {},
            "source_metadata": {
                "node_id": node_id,
                "execution_id": execution.id,
                "project_id": execution.project_id,
                "mode": discussion_mode,
                "topic": discussion_result.get("discussion_topic") or discussion_result.get("topic") or execution.context.get("chapter_title", "当前章节"),
                "chapter_title": execution.context.get("chapter_title", ""),
                "leader": discussion_result.get("leader", ""),
                "leader_type": discussion_result.get("leader_type", ""),
                "participants": discussion_result.get("participants", []),
                "timestamp": discussion_result.get("timestamp") or datetime.now().isoformat(),
                "status": discussion_result.get("status", "completed"),
                "constraint_warnings": discussion_result.get("constraint_warnings", []),
                "character_constraints": discussion_result.get("character_constraints", {}),
                "contains_unconfirmed_character_material": discussion_result.get("contains_unconfirmed_character_material", False),
            },
        }
        bundle["persistence_preview"] = self._build_discussion_asset_preview(bundle)
        return bundle

    def _apply_discussion_asset_bundle(
        self,
        execution: "WorkflowExecution",
        discussion_result: Dict[str, Any],
        bundle: Dict[str, Any],
        discussion_mode: str,
    ) -> Dict[str, Any]:
        """将 discussion bundle 写回上下文与讨论结果。"""
        discussion_summary = self._extract_discussion_summary_text(discussion_result)
        digest = {
            "topic": bundle.get("source_metadata", {}).get("topic", ""),
            "mode": discussion_mode,
            "summary": discussion_summary[:280],
            "plot_update_count": len(bundle.get("plot_updates", [])),
            "hook_count": len(bundle.get("hooks", [])),
            "lore_count": len(bundle.get("lore_candidates", [])),
            "region_count": len(bundle.get("region_candidates", [])),
            "character_count": len(bundle.get("character_candidates", [])),
            "character_location_update_count": len(bundle.get("character_location_updates", [])),
            "state_change_count": len(bundle.get("state_changes", [])),
            "constraint_warnings": bundle.get("source_metadata", {}).get("constraint_warnings", []),
            "contains_unconfirmed_character_material": bundle.get("source_metadata", {}).get("contains_unconfirmed_character_material", False),
        }

        discussion_result["discussion_assets"] = bundle
        discussion_result["discussion_asset_digest"] = digest

        existing_group_discussion = execution.context.get("group_discussion")
        if isinstance(existing_group_discussion, dict):
            existing_group_discussion["discussion_assets"] = bundle
            existing_group_discussion["discussion_asset_digest"] = digest
            if discussion_summary and not existing_group_discussion.get("summary"):
                existing_group_discussion["summary"] = discussion_summary

        if discussion_mode == "performance" or not isinstance(existing_group_discussion, dict):
            normalized_discussion = {
                "mode": discussion_mode,
                "topic": discussion_result.get("topic") or discussion_result.get("discussion_topic") or execution.context.get("chapter_title", "当前章节"),
                "discussion_topic": discussion_result.get("discussion_topic") or discussion_result.get("topic") or execution.context.get("chapter_title", "当前章节"),
                "leader": discussion_result.get("leader", ""),
                "leader_type": discussion_result.get("leader_type", "master_plotter"),
                "participants": discussion_result.get("participants", []),
                "messages": discussion_result.get("messages", []),
                "characters": discussion_result.get("characters", []),
                "full_content": discussion_result.get("full_content", ""),
                "summary": discussion_summary,
                "timestamp": discussion_result.get("timestamp") or datetime.now().isoformat(),
                "status": discussion_result.get("status", "waiting_confirmation"),
                "discussion_assets": bundle,
                "discussion_asset_digest": digest,
            }
            execution.context["group_discussion"] = normalized_discussion

            discussion_history = execution.context.get("discussion_history", [])
            if not discussion_history or discussion_history[-1] != normalized_discussion:
                discussion_history.append(normalized_discussion)
                execution.context["discussion_history"] = discussion_history

        execution.context["discussion_assets"] = bundle
        execution.context["discussion_asset_digest"] = digest
        execution.context["discussion_assets_committed"] = False
        execution.context.setdefault("discussion_asset_history", []).append(bundle)

        if discussion_summary:
            execution.context["discussion_summary"] = discussion_summary
            execution.context["last_discussion_summary"] = discussion_summary

        return digest

    def _discussion_asset_to_dict(self, asset: Any, default_key: str = "title") -> Dict[str, Any]:
        """将讨论资产归一化为 dict，便于分类和持久化。"""
        if isinstance(asset, dict):
            return dict(asset)
        if asset in (None, ""):
            return {}
        return {default_key: str(asset), "description": str(asset)}

    def _discussion_asset_has_geo_shape(self, asset: Dict[str, Any]) -> bool:
        """判断讨论资产是否具备可作为 Region 的地理实体特征。"""
        if not asset.get("name") and not asset.get("title"):
            return False

        explicit_type = str(
            asset.get("asset_type")
            or asset.get("type")
            or asset.get("kind")
            or asset.get("category")
            or ""
        ).lower()
        if explicit_type in {"region", "location", "place", "map", "geography", "区域", "地点", "地图"}:
            return True

        geo_fields = {
            "connections",
            "terrain_features",
            "landmarks",
            "atmosphere",
            "encounters",
            "region_type",
            "terrain_type",
            "local_rules",
            "coordinates",
            "neighbors",
        }
        return any(asset.get(field) for field in geo_fields)

    def _discussion_asset_has_lore_shape(self, asset: Dict[str, Any]) -> bool:
        """判断讨论资产是否具备应进入 LoreEntry 的背景设定特征。"""
        explicit_type = str(
            asset.get("asset_type")
            or asset.get("type")
            or asset.get("kind")
            or asset.get("category")
            or ""
        ).lower()
        if explicit_type in {
            "lore",
            "world_rule",
            "history",
            "culture",
            "faction",
            "rule",
            "setting",
            "传说",
            "历史",
            "文化",
            "规则",
            "设定",
        }:
            return True

        lore_fields = {
            "content",
            "summary",
            "history",
            "culture",
            "rules",
            "taboos",
            "factions",
            "myth",
            "legend",
            "constraints",
            "forbidden_actions",
        }
        return any(asset.get(field) for field in lore_fields)

    def _split_discussion_location_assets(
        self,
        assets: List[Any],
    ) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """将地图/地点类讨论资产拆分为 Region 与 LoreEntry 候选。"""
        region_candidates: List[Dict[str, Any]] = []
        lore_candidates: List[Dict[str, Any]] = []

        for raw_asset in assets:
            asset = self._discussion_asset_to_dict(raw_asset, default_key="name")
            if not asset:
                continue

            is_region = self._discussion_asset_has_geo_shape(asset)
            is_lore = self._discussion_asset_has_lore_shape(asset)

            if is_region:
                region_candidates.append(asset)

            if is_lore or not is_region:
                title = asset.get("lore_title") or asset.get("title") or asset.get("name") or "未命名设定"
                content = (
                    asset.get("content")
                    or asset.get("lore")
                    or asset.get("history")
                    or asset.get("description")
                    or asset.get("summary")
                    or str(asset)
                )
                lore_asset = {
                    **asset,
                    "title": title,
                    "content": content,
                    "category": asset.get("lore_category") or asset.get("category") or "geography",
                    "related_locations": asset.get("related_locations") or [asset.get("name") or title],
                    "source": asset.get("source") or "group_discussion",
                }
                if is_region:
                    lore_asset.setdefault("metadata", {})
                    if isinstance(lore_asset["metadata"], dict):
                        lore_asset["metadata"]["dual_write_region_name"] = asset.get("name") or title
                lore_candidates.append(lore_asset)

        return region_candidates, lore_candidates

    def _is_persistable_discussion_character(self, candidate: Dict[str, Any]) -> bool:
        """判断讨论中提到的角色是否足够明确，可提前持久化。"""
        name = str(candidate.get("name") or candidate.get("title") or "").strip()
        if not name:
            return False

        vague_markers = ["某", "一名", "一个", "神秘", "路人", "士兵", "商人", "长老", "守卫"]
        if any(marker in name for marker in vague_markers) and not candidate.get("importance_tier"):
            return False

        has_narrative_role = any(
            candidate.get(field)
            for field in ("importance_tier", "role", "character_type", "story_arc_role", "narrative_role")
        )
        has_core_detail = any(
            candidate.get(field)
            for field in (
                "personality",
                "appearance",
                "background",
                "background_story",
                "relationship",
                "relationships",
                "motivation",
                "goals",
                "description",
            )
        )
        return has_narrative_role and has_core_detail

    def _extract_character_location_reason(self, candidate: Dict[str, Any]) -> str:
        """提取角色到达当前位置的原因，兼容 Agent 输出别名。"""
        for key in (
            "current_location_reason",
            "location_reason",
            "arrival_reason",
            "reason_for_arrival",
            "movement_reason",
        ):
            value = candidate.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return ""

    async def _validate_discussion_character_location_update(
        self,
        update_data: Dict[str, Any],
        existing_character: Dict[str, Any],
        db=None,
    ) -> Optional[str]:
        """校验讨论输出中的角色位置更新，返回错误原因或 None。"""
        current_region_id = update_data.get("current_region_id") or update_data.get("region_id")
        if not current_region_id:
            return None

        if not db or not hasattr(db, "get_region"):
            return None

        region = await db.get_region(current_region_id)
        if not region:
            return "当前所在区域不存在"

        region_world_id = str(region.get("world_id")) if region.get("world_id") else None
        character_world_id = str(
            update_data.get("world_id")
            or existing_character.get("world_id")
            or ""
        ).strip() or None

        if character_world_id and region_world_id and character_world_id != region_world_id:
            return "角色所属世界与当前所在区域不一致"

        if not update_data.get("world_id") and not existing_character.get("world_id") and region_world_id:
            update_data["world_id"] = region_world_id

        if not update_data.get("current_location") and region.get("name"):
            update_data["current_location"] = region.get("name")

        return None

    async def _resolve_discussion_character_location_target(
        self,
        execution: "WorkflowExecution",
        update_data: Dict[str, Any],
        db=None,
    ) -> Optional[Dict[str, Any]]:
        """按 character_id 优先、character_name/name 兜底解析要更新的角色。"""
        character_id = str(update_data.get("character_id") or update_data.get("id") or "").strip()
        if character_id and db and hasattr(db, "get_character"):
            character = await db.get_character(character_id)
            if character:
                return dict(character)

        character_name = str(update_data.get("character_name") or update_data.get("name") or "").strip()
        if character_name and db and hasattr(db, "get_character_by_project_and_name"):
            character = await db.get_character_by_project_and_name(execution.project_id, character_name)
            if character:
                return dict(character)

        if character_name and db and hasattr(db, "get_all_characters"):
            characters = await db.get_all_characters(project_id=execution.project_id, limit=500)
            for character in characters or []:
                if str(character.get("name") or "").strip().lower() == character_name.lower():
                    return dict(character)

        return None

    async def _persist_discussion_character_location_updates(
        self,
        execution: "WorkflowExecution",
        character_location_updates: List[Any],
        db=None,
    ) -> Dict[str, Any]:
        """保存讨论输出中针对已有角色的当前位置更新。"""
        result = {"updated": [], "skipped": [], "errors": []}
        if not character_location_updates:
            return result
        if not db:
            result["errors"].append("数据库连接不存在，无法保存角色位置更新")
            return result

        for raw_update in character_location_updates:
            update_data = self._discussion_asset_to_dict(raw_update, default_key="character_name")
            if not update_data:
                continue

            character_name = str(update_data.get("character_name") or update_data.get("name") or "").strip()
            character_id = str(update_data.get("character_id") or update_data.get("id") or "").strip()

            try:
                existing_character = await self._resolve_discussion_character_location_target(
                    execution,
                    update_data,
                    db,
                )
                if not existing_character:
                    result["skipped"].append({
                        "character_id": character_id or None,
                        "character_name": character_name or None,
                        "reason": "未找到要更新的角色",
                    })
                    continue

                validation_error = await self._validate_discussion_character_location_update(
                    update_data,
                    existing_character,
                    db,
                )
                if validation_error:
                    result["skipped"].append({
                        "id": existing_character.get("id"),
                        "name": existing_character.get("name") or character_name,
                        "reason": validation_error,
                    })
                    continue

                reason = self._extract_character_location_reason(update_data)
                merged_character = dict(existing_character)
                merged_character["id"] = existing_character.get("id") or character_id
                merged_character["name"] = existing_character.get("name") or character_name

                if update_data.get("world_id"):
                    merged_character["world_id"] = update_data.get("world_id")
                if update_data.get("current_region_id") or update_data.get("region_id"):
                    merged_character["current_region_id"] = update_data.get("current_region_id") or update_data.get("region_id")
                if update_data.get("current_location") or update_data.get("location"):
                    merged_character["current_location"] = update_data.get("current_location") or update_data.get("location")
                if reason:
                    merged_character["current_location_reason"] = reason

                merged_character["updated_at"] = datetime.now()
                await db.save_character(merged_character)
                result["updated"].append({
                    "id": merged_character.get("id"),
                    "name": merged_character.get("name"),
                    "current_region_id": merged_character.get("current_region_id"),
                    "current_location": merged_character.get("current_location"),
                    "current_location_reason": merged_character.get("current_location_reason") or "",
                })
                logger.info(f"保存角色位置更新: {merged_character.get('name')}")
            except Exception as e:
                logger.error(f"保存角色位置更新失败: {character_name or character_id or raw_update}: {e}")
                result["errors"].append({
                    "character_id": character_id or None,
                    "character_name": character_name or None,
                    "error": str(e),
                })

        return result

    async def _persist_discussion_characters(
        self,
        execution: "WorkflowExecution",
        character_candidates: List[Any],
        db=None,
    ) -> Dict[str, Any]:
        """保存讨论阶段已经明确的重要新角色。"""
        result = {"created": [], "skipped": [], "errors": []}
        if not db:
            result["errors"].append("数据库连接不存在，无法保存讨论角色")
            return result

        import uuid
        from app.api.routes.characters import _auto_configure_character_agent, _derive_role_from_tier
        from app.models.character import CharacterImportanceTier

        valid_tiers = {tier.value for tier in CharacterImportanceTier}

        for raw_candidate in character_candidates:
            candidate = self._discussion_asset_to_dict(raw_candidate, default_key="name")
            name = str(candidate.get("name") or candidate.get("title") or "").strip()
            if not self._is_persistable_discussion_character(candidate):
                if name:
                    result["skipped"].append({"name": name, "reason": "角色信息不够明确，暂不提前落库"})
                continue

            try:
                if hasattr(db, "get_character_by_project_and_name"):
                    existing = await db.get_character_by_project_and_name(execution.project_id, name)
                    if existing:
                        result["skipped"].append({"name": name, "reason": "角色已存在", "id": existing.get("id")})
                        continue

                importance_tier = str(candidate.get("importance_tier") or candidate.get("tier") or CharacterImportanceTier.RECURRING.value)
                if importance_tier not in valid_tiers:
                    importance_tier = CharacterImportanceTier.RECURRING.value

                goals = candidate.get("goals") or candidate.get("agent_goals") or []
                if isinstance(goals, str):
                    goals = [goals]

                char_data = {
                    "id": str(uuid.uuid4()),
                    "name": name,
                    "project_id": execution.project_id,
                    "world_id": candidate.get("world_id") or execution.context.get("world_id"),
                    "description": candidate.get("description") or candidate.get("summary") or "",
                    "status": candidate.get("status") or "active",
                    "importance_tier": importance_tier,
                    "role": _derive_role_from_tier(importance_tier),
                    "appearance": candidate.get("appearance"),
                    "personality": candidate.get("personality"),
                    "background_story": candidate.get("background_story") or candidate.get("background"),
                    "speech_pattern": candidate.get("speech_pattern"),
                    "personality_traits": candidate.get("personality_traits") or [],
                    "relationships": candidate.get("relationships") or [],
                    "key_relationships": candidate.get("key_relationships") or {},
                    "age": candidate.get("age"),
                    "gender": candidate.get("gender"),
                    "lexicon": candidate.get("lexicon") or [],
                    "voice_samples": candidate.get("voice_samples") or [],
                    "attributes": candidate.get("attributes") or {},
                    "goals": goals,
                    "inventory": candidate.get("inventory") or [],
                    "current_location": candidate.get("current_location") or candidate.get("location"),
                    "current_region_id": candidate.get("current_region_id") or candidate.get("region_id"),
                    "current_location_reason": (
                        candidate.get("current_location_reason")
                        or candidate.get("location_reason")
                        or candidate.get("arrival_reason")
                        or candidate.get("reason_for_arrival")
                        or candidate.get("movement_reason")
                        or ""
                    ),
                    "agent_goals": candidate.get("agent_goals") or [],
                    "agent_memory": candidate.get("agent_memory") or [],
                    "has_agent": candidate.get("has_agent"),
                    "agent_enabled": candidate.get("agent_enabled"),
                    "created_at": datetime.now(),
                    "updated_at": datetime.now(),
                }
                if isinstance(char_data["attributes"], dict):
                    char_data["attributes"].setdefault("source", "group_discussion")
                    char_data["attributes"].setdefault("discussion_node_id", execution.context.get("discussion_assets", {}).get("source_metadata", {}).get("node_id"))

                if char_data.get("has_agent") is None:
                    char_data["has_agent"] = False
                if char_data.get("agent_enabled") is None:
                    char_data["agent_enabled"] = True

                char_data = await _auto_configure_character_agent(char_data)
                await db.save_character(char_data)
                result["created"].append({"id": char_data["id"], "name": name})
                logger.info(f"保存讨论新角色: {name}")
            except Exception as e:
                logger.error(f"保存讨论角色失败: {name or raw_candidate}: {e}")
                result["errors"].append({"name": name, "error": str(e)})

        return result

    async def _persist_discussion_state_changes(
        self,
        execution: "WorkflowExecution",
        state_changes: List[Any],
        source_metadata: Dict[str, Any],
        db=None,
    ) -> Dict[str, Any]:
        """保存并应用讨论输出中的剧情状态变更。"""
        result = {"created": [], "applied": [], "errors": []}
        if not state_changes:
            return result
        if not db:
            result["errors"].append("数据库连接不存在")
            return result

        from app.services.narrative_state_change_service import NarrativeStateChangeService

        service = NarrativeStateChangeService(db)
        source_context = {
            "workflow_execution_id": source_metadata.get("execution_id") or execution.id,
            "workflow_id": execution.workflow_id,
            "node_id": source_metadata.get("node_id"),
            "agent_type": source_metadata.get("leader_type") or source_metadata.get("leader"),
            "chapter_id": execution.context.get("chapter_id"),
            "discussion_id": source_metadata.get("discussion_id") or f"{execution.id}:{source_metadata.get('node_id', 'discussion')}",
            "source_text": execution.context.get("discussion_summary") or execution.context.get("last_discussion_summary"),
        }

        for raw_change in state_changes:
            change_payload = self._discussion_asset_to_dict(raw_change, default_key="title")
            if not change_payload:
                continue
            if not change_payload.get("project_id"):
                change_payload["project_id"] = execution.project_id

            try:
                change = await service.create_change(change_payload, source_context=source_context)
                result["created"].append({
                    "id": change.get("id"),
                    "entity_type": change.get("entity_type"),
                    "entity_id": change.get("entity_id"),
                    "change_type": change.get("change_type"),
                    "status": change.get("status"),
                    "title": change.get("title"),
                })

                confirmed = await service.confirm_change(change["id"])
                applied = await service.apply_change(confirmed["id"])
                applied_change = applied.get("change") or {}
                result["applied"].append({
                    "id": applied_change.get("id") or change.get("id"),
                    "projection": applied.get("projection"),
                })
            except Exception as e:
                logger.error(f"保存讨论剧情状态变更失败: {change_payload}: {e}")
                result["errors"].append({"title": change_payload.get("title"), "error": str(e)})

        return result

    async def _persist_discussion_assets(
        self,
        execution: "WorkflowExecution",
        bundle: Dict[str, Any],
        db=None,
        confirmation_mode: str = "user_confirm",
    ) -> Dict[str, Any]:
        """在讨论结果被确认后，将 discussion assets 写入持久层并回填上下文。"""
        state = {
            "committed": False,
            "confirmation_mode": confirmation_mode,
            "persisted_at": datetime.now().isoformat(),
            "hooks": {"planted": [], "resolved": [], "updated": []},
            "lores": {"created": [], "updated": []},
            "regions": {"saved": []},
            "characters": {"created": [], "skipped": [], "errors": []},
            "character_location_updates": {"updated": [], "skipped": [], "errors": []},
            "state_changes": {"created": [], "applied": [], "errors": []},
            "errors": [],
        }

        if not bundle:
            execution.context["discussion_persistence_state"] = state
            return state

        try:
            plot_updates = bundle.get("plot_updates", [])
            if plot_updates:
                execution.context.setdefault("discussion_plot_updates", []).extend(plot_updates)

            if db:
                hook_result = await self._save_hooks_from_manager(
                    execution,
                    {"hooks_to_plant": bundle.get("hooks", [])},
                    db,
                )
                if isinstance(hook_result, dict):
                    state["hooks"] = hook_result

                lore_result = await self._save_lore_from_setting(
                    execution,
                    {"new_lores": bundle.get("lore_candidates", [])},
                    db,
                )
                if isinstance(lore_result, dict):
                    state["lores"] = lore_result

                region_result = await self._save_world_data_from_procgen(
                    execution,
                    {"regions": bundle.get("region_candidates", [])},
                    db,
                )
                if isinstance(region_result, dict):
                    state["regions"] = region_result

                state["characters"] = await self._persist_discussion_characters(
                    execution,
                    bundle.get("character_candidates", []),
                    db,
                )

                state["character_location_updates"] = await self._persist_discussion_character_location_updates(
                    execution,
                    bundle.get("character_location_updates", []),
                    db,
                )

                state["state_changes"] = await self._persist_discussion_state_changes(
                    execution,
                    bundle.get("state_changes", []),
                    bundle.get("source_metadata", {}),
                    db,
                )
            else:
                state["errors"].append("数据库连接不存在，讨论资产仅写入执行上下文")

            persisted_refs = {
                "hooks": state.get("hooks", {}).get("planted", []),
                "lores": state.get("lores", {}).get("created", []),
                "regions": state.get("regions", {}).get("saved", []),
                "characters": [c.get("id") for c in state.get("characters", {}).get("created", []) if c.get("id")],
                "character_location_updates": [
                    c.get("id")
                    for c in state.get("character_location_updates", {}).get("updated", [])
                    if c.get("id")
                ],
                "state_changes": [
                    c.get("id")
                    for c in state.get("state_changes", {}).get("created", [])
                    if c.get("id")
                ],
                "applied_state_changes": [
                    c.get("id")
                    for c in state.get("state_changes", {}).get("applied", [])
                    if c.get("id")
                ],
            }
            state["committed"] = True
            state["persisted_asset_refs"] = persisted_refs

            execution.context["discussion_assets_committed"] = True
            execution.context["discussion_persistence_state"] = state
            execution.context["persisted_asset_refs"] = persisted_refs
            execution.context["discussion_created_hooks"] = persisted_refs["hooks"]
            execution.context["discussion_created_lores"] = persisted_refs["lores"]
            execution.context["discussion_created_regions"] = persisted_refs["regions"]
            execution.context["discussion_created_characters"] = state.get("characters", {}).get("created", [])
            execution.context["discussion_character_location_updates"] = state.get("character_location_updates", {}).get("updated", [])
            execution.context["discussion_state_changes"] = state.get("state_changes", {}).get("created", [])
            execution.context["discussion_applied_state_changes"] = state.get("state_changes", {}).get("applied", [])

            await self._broadcast_status(execution.id, "discussion_assets_persisted", self._make_json_safe(state))
            return state
        except Exception as e:
            logger.error(f"持久化讨论资产失败: {e}", exc_info=True)
            state["errors"].append(str(e))
            execution.context["discussion_persistence_state"] = state
            await self._broadcast_status(execution.id, "discussion_assets_persist_failed", self._make_json_safe(state))
            return state

    def _character_name_set(self, characters: Any) -> set[str]:
        names: set[str] = set()
        for character in self._ensure_context_list(characters):
            if isinstance(character, dict):
                name = character.get("name") or character.get("character_name") or character.get("id")
            else:
                name = character
            if name not in (None, ""):
                names.add(str(name))
        return names

    def _load_prompt_asset_content(self, prompt_id: str) -> str:
        """加载 md prompt 资产内容，失败时返回空字符串。"""
        try:
            from app.services.md_file_service import get_md_file_service

            md_service = get_md_file_service()
            prompt_data = md_service.get_prompt(prompt_id)
            if isinstance(prompt_data, dict):
                return (prompt_data.get("content") or prompt_data.get("raw_content") or "").strip()
            return (md_service.get_prompt_content(prompt_id) or "").strip()
        except Exception as e:
            logger.warning("加载 workflow prompt 资产失败: prompt_id=%s, error=%s", prompt_id, e)
            return ""

    def _build_workflow_runtime_constraints_prompt(self, context: Dict[str, Any]) -> str:
        """构建工作流共享运行期约束块。"""
        prompt_asset = self._load_prompt_asset_content(
            self.WORKFLOW_RUNTIME_CONSTRAINTS_PROMPT_ID,
        ) or (
            "Workflow runtime constraints: respect present/mentioned/forbidden character boundaries, "
            "treat scene performance as reference material only, and keep asset changes pending confirmation."
        )
        constraints = self._build_character_constraint_state(context)
        selected_lore = self._ensure_context_list(context.get("selected_lore_entries") or context.get("dynamic_lore_entries") or [])
        character_setting_lore = [
            entry for entry in selected_lore
            if isinstance(entry, dict) and str(entry.get("category") or "").lower() == "character_setting"
        ]
        sections: List[str] = [prompt_asset]
        if any(constraints.get(key) for key in ("present_character_names", "mentioned_only_names", "forbidden_direct_appearance_names")):
            sections.append("【角色出场运行期数据】\n" + self._format_context_for_prompt(constraints, max_chars=3500))
        if character_setting_lore:
            sections.append("【角色设定库条目（来源/历史/身份必须遵守）】\n" + self._format_context_for_prompt(character_setting_lore, max_chars=3000))
        return "\n\n".join(section for section in sections if section).strip()

    def _build_workflow_reference_material_instruction(self) -> str:
        """构建场景演绎素材使用边界说明。"""
        prompt_asset = self._load_prompt_asset_content(
            self.WORKFLOW_RUNTIME_CONSTRAINTS_PROMPT_ID,
        )
        if prompt_asset:
            return (
                "参见 prompt 资产 function_workflow_runtime_constraints：场景演绎结果是供后续节点参考的素材索引，"
                "不是必须逐字照抄的章节正文；若与章节大纲、固定设定、角色硬约束或已确认资产冲突，必须跳过、改写或标记为风险。"
            )
        return (
            "场景演绎结果是供后续节点参考的素材索引，不是必须逐字照抄的章节正文；"
            "若与章节大纲、固定设定或角色硬约束冲突，必须跳过或改写。"
        )

    def _build_character_constraint_state(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """构建下游 Agent 共享的角色出场硬约束。"""
        scene_directions = self._ensure_context_dict(context.get("scene_directions"))
        performers = scene_directions.get("performers") or context.get("performers") or []
        mentioned = scene_directions.get("mentioned_characters") or context.get("mentioned_characters") or []
        unavailable = scene_directions.get("unavailable_characters") or context.get("unavailable_characters") or []
        background = scene_directions.get("background_characters") or context.get("background_characters") or []
        trace = scene_directions.get("participation_trace") or context.get("participation_trace") or []
        warnings = scene_directions.get("participation_warnings") or context.get("participation_warnings") or []

        performer_names = self._character_name_set(performers)
        background_names = self._character_name_set(background)
        mentioned_names = self._character_name_set(mentioned)
        unavailable_names = self._character_name_set(unavailable)
        hard_blocked_names = sorted((mentioned_names | unavailable_names) - (performer_names | background_names))

        return {
            "performers": performers,
            "background_characters": background,
            "mentioned_characters": mentioned,
            "unavailable_characters": unavailable,
            "present_character_names": sorted(performer_names | background_names),
            "mentioned_only_names": sorted(mentioned_names - performer_names - background_names),
            "forbidden_direct_appearance_names": hard_blocked_names,
            "participation_trace": trace,
            "participation_warnings": warnings,
            "rules_prompt_id": self.WORKFLOW_RUNTIME_CONSTRAINTS_PROMPT_ID,
        }

    def _inject_character_constraints(self, context: Dict[str, Any]) -> None:
        constraints = self._build_character_constraint_state(context)
        if any(constraints.get(key) for key in ("performers", "mentioned_characters", "unavailable_characters", "forbidden_direct_appearance_names")):
            context["character_constraints"] = constraints
            context.setdefault("participation_trace", constraints.get("participation_trace", []))
            context.setdefault("participation_warnings", constraints.get("participation_warnings", []))

    def _sanitize_discussion_result_against_constraints(
        self,
        discussion_result: Dict[str, Any],
        constraints: Dict[str, Any],
    ) -> Dict[str, Any]:
        """标记讨论输出中涉及禁止正面出场角色的风险，避免下游当成已确认事实。"""
        forbidden_names = [name for name in constraints.get("forbidden_direct_appearance_names", []) if name]
        if not forbidden_names:
            return discussion_result

        text = "\n".join(
            str(message.get("content") or "")
            for message in discussion_result.get("messages", []) or []
            if isinstance(message, dict)
        )
        flagged = [name for name in forbidden_names if name and name in text]
        if flagged:
            warnings = discussion_result.setdefault("constraint_warnings", [])
            warnings.append(
                "讨论内容提到了不可正面出场角色，仅允许作为背景/传闻/回忆处理，不得作为已确认正面出场事实："
                + "、".join(flagged)
            )
            discussion_result["character_constraints"] = constraints
            discussion_result["contains_unconfirmed_character_material"] = True
        return discussion_result

    def _format_context_for_prompt(self, value: Any, max_chars: int = 4000) -> str:
        if value in (None, "", [], {}):
            return ""
        try:
            text = json.dumps(value, ensure_ascii=False, indent=2)
        except TypeError:
            text = str(value)
        text = text.strip()
        if len(text) > max_chars:
            return text[:max_chars] + "\n（因长度限制已截取，保留前部结构化信息）"
        return text

    def _format_agent_constraint_context(self, context: Dict[str, Any]) -> str:
        constraints_prompt = self._build_workflow_runtime_constraints_prompt(context)
        if constraints_prompt:
            return "【工作流角色/设定约束】\n" + constraints_prompt
        return ""

    async def _execute_group_discussion_node(
        self,
        node: WorkflowNode,
        execution: "WorkflowExecution",
        db=None,
    ) -> Dict[str, Any]:
        """
        执行集体讨论节点 - 支持两种模式：

        1. 角色演绎模式（performance）: 多个角色Agent同台飙戏，推进剧情
           - 编剧设定场景和表演方向
           - 各角色Agent根据人设进行真实表演
           - 场景可以是同一幕或各自独立场景

        2. 创作讨论模式（meeting）: 传统讨论，评价已写内容
           - 编剧开场说明创作意图
           - 各Agent发表专业意见
           - 总结Agent汇总讨论结果

        完成后暂停等待用户确认（超时自动接受）：
        - 用户同意：继续工作流
        - 用户不同意：提供反馈，工作流重新开始
        - 超时（60秒）：自动接受并继续
        """
        # 检查节点配置，确定讨论模式
        node_config = node.config or {}
        discussion_mode = node_config.get("discussion_mode", "meeting")  # "meeting" 或 "performance"
        require_user_confirmation = node_config.get("require_user_confirmation", True)  # 默认需要用户确认
        confirmation_timeout = node_config.get("confirmation_timeout", self.USER_CONFIRMATION_TIMEOUT)  # 超时时间

        logger.info(f"开始执行集体讨论节点（模式: {discussion_mode}）: {node.id}")

        if discussion_mode == "performance":
            result = await self._execute_character_performance(node, execution, db)
        else:
            result = await self._execute_meeting_discussion(node, execution, db)

        if result.get("status") in {"completed", "waiting_confirmation"}:
            discussion_constraints = self._build_character_constraint_state(execution.context)
            result = self._sanitize_discussion_result_against_constraints(result, discussion_constraints)
            discussion_bundle = self._build_discussion_asset_bundle(
                execution=execution,
                discussion_result=result,
                node_id=node.id,
                discussion_mode=discussion_mode,
            )
            discussion_digest = self._apply_discussion_asset_bundle(
                execution=execution,
                discussion_result=result,
                bundle=discussion_bundle,
                discussion_mode=discussion_mode,
            )
            result["discussion_assets"] = discussion_bundle
            result["discussion_asset_digest"] = discussion_digest

        # 如果需要用户确认，暂停工作流
        if require_user_confirmation and result.get("status") in {"completed", "waiting_confirmation"}:
            logger.info(f"集体讨论节点完成，暂停等待用户确认（超时 {confirmation_timeout} 秒）...")

            # 广播等待用户确认事件
            await self._broadcast_status(execution.id, "waiting_user_confirmation", {
                "node_id": node.id,
                "node_type": "group_discussion",
                "discussion_mode": discussion_mode,
                "discussion_result": result,
                "discussion_assets": result.get("discussion_assets", {}),
                "discussion_asset_digest": result.get("discussion_asset_digest", {}),
                "timeout_seconds": confirmation_timeout,
                "message": f"讨论已完成，请在 {confirmation_timeout} 秒内确认，否则自动接受",
            })

            # 设置等待确认状态
            execution.context["waiting_confirmation"] = {
                "node_id": node.id,
                "discussion_result": result,
                "discussion_assets": result.get("discussion_assets", {}),
                "discussion_asset_digest": result.get("discussion_asset_digest", {}),
                "timestamp": datetime.now().isoformat(),
                "timeout_seconds": confirmation_timeout,
            }

            # 暂停工作流
            execution.status = WorkflowStatus.PAUSED

            # 启动超时自动确认的后台任务
            asyncio.create_task(
                self._auto_confirm_on_timeout(
                    execution_id=execution.id,
                    timeout_seconds=confirmation_timeout,
                    db=db,
                )
            )

            # 更新结果状态。不要写入 waiting_confirmation，避免通用 context 合并覆盖确认详情 dict。
            result["waiting_user_confirmation"] = True
            result["timeout_seconds"] = confirmation_timeout
            result["message"] = f"等待用户确认（{confirmation_timeout}秒后自动接受）"

        return result

    async def _auto_confirm_on_timeout(
        self,
        execution_id: str,
        timeout_seconds: int,
        db=None,
    ):
        """
        超时自动确认讨论结果

        Args:
            execution_id: 执行ID
            timeout_seconds: 超时秒数
            db: 数据库连接
        """
        try:
            # 等待超时时间
            await asyncio.sleep(timeout_seconds)

            # 检查是否仍然在等待确认
            execution = self._executions.get(execution_id)
            if not execution:
                # 尝试从数据库加载
                if db:
                    execution = await self._load_execution_from_db(execution_id, db)
                    if execution:
                        self._executions[execution_id] = execution

            if not execution:
                logger.debug(f"执行 {execution_id} 不存在，跳过自动确认")
                return

            if execution.status != WorkflowStatus.PAUSED:
                logger.debug(f"执行 {execution_id} 不在暂停状态，跳过自动确认")
                return

            waiting_confirmation = execution.context.get("waiting_confirmation")
            if not waiting_confirmation:
                logger.debug(f"执行 {execution_id} 没有等待确认状态，跳过自动确认")
                return

            # 检查是否已经有用户确认（双重检查）
            if waiting_confirmation.get("confirmed"):
                logger.debug(f"执行 {execution_id} 已被用户确认，跳过自动确认")
                return

            # 超时自动接受
            logger.info(f"用户确认超时（{timeout_seconds}秒），自动接受讨论结果: {execution_id}")

            # 标记自动确认元数据，实际 confirmed 状态由 confirm_discussion 统一设置
            waiting_confirmation["auto_confirmed"] = True
            waiting_confirmation["confirmation_mode"] = "timeout_auto_confirm"

            # 广播超时事件
            await self._broadcast_status(execution_id, "confirmation_timeout", {
                "message": f"用户未在 {timeout_seconds} 秒内确认，自动接受讨论结果",
                "auto_approved": True,
            })

            # 调用确认方法（自动接受）
            result = await self.confirm_discussion(
                execution_id=execution_id,
                approved=True,
                feedback=None,
                db=db,
            )

            logger.info(f"自动确认结果: {result}")

        except asyncio.CancelledError:
            logger.debug(f"自动确认任务被取消: {execution_id}")
        except Exception as e:
            logger.error(f"自动确认任务失败: {e}")

    async def _execute_character_performance(
        self,
        node: WorkflowNode,
        execution: "WorkflowExecution",
        db=None,
    ) -> Dict[str, Any]:
        """
        执行集体讨论中的角色演绎模式。

        这里默认应该是“集体讨论=当前 workflow 范围内全员参与”，因此优先读取节点显式配置，
        否则自动回退到本次 workflow 上下文中的角色集合，而不是项目里所有角色。
        """
        logger.info("开始角色演绎模式...")

        node_config = dict(node.config or {})
        if not node_config.get("characters") and not node_config.get("required_characters"):
            scoped_characters = execution.context.get("characters", []) or []
            scoped_names = [c.get("name") for c in scoped_characters if isinstance(c, dict) and c.get("name")]
            if scoped_names:
                node_config["characters"] = scoped_names
                logger.info(f"集体讨论角色演绎默认使用 workflow 范围内全员参与: {scoped_names}")

        original_config = node.config
        try:
            node.config = node_config
            return await self._execute_multi_character_scene(
                node,
                execution,
                db,
                participant_keys=["characters", "required_characters"],
                default_scene_name=node.label,
                target_word_multiplier=2,
                default_iteration_count=3,
            )
        finally:
            node.config = original_config

    async def _execute_meeting_discussion(
        self,
        node: WorkflowNode,
        execution: "WorkflowExecution",
        db=None,
    ) -> Dict[str, Any]:
        """
        执行创作讨论模式 - 领头人机制

        流程：
        1. 领头人开启会话，广播开始
        2. 各 Agent 发表意见，消息广播给所有参与者和前端
        3. 领头人汇总并请求用户确认
        4. 用户同意/拒绝后，领头人结束会话
        5. 同意 -> 工作流继续；拒绝 -> 带反馈重启

        领头人选择优先级：
        1. 节点配置中指定的 leader_agent
        2. 参与讨论的 Agent 中按优先级选择：
           master_plotter > plotter > evaluator > writer > setting > hook_manager
        """
        logger.info("开始创作讨论模式（领头人机制）...")

        try:
            # 收集工作流中所有已执行的 Agent 类型
            workflow = await self.get_workflow(execution.workflow_id, db)
            executed_agents = set()

            if workflow:
                for n in workflow.nodes:
                    if n.node_type == NodeType.AGENT and n.agent_type:
                        executed_agents.add(n.agent_type)

            # Agent 名称映射
            AGENT_NAME_MAP = {
                "plotter": "编剧",
                "master_plotter": "总编剧",
                "writer": "作家",
                "evaluator": "评估员",
                "hook_manager": "伏笔管理员",
                "setting": "设定管理员",
                "world_map_manager": "地图管理员",
                "event_generator": "事件生成器",
                "character": "角色代表",
                "summarizer": "总结员",
            }

            # 不参与讨论的 Agent 类型
            excluded_from_discussion = {
                "world_map_manager", "event_generator", "procgen",
                "scene_coordinator", "summarizer"
            }

            # 过滤出有效参与讨论的 Agent
            discussion_agents = [a for a in executed_agents if a not in excluded_from_discussion]

            # 领头人选择：优先级列表
            LEADER_PRIORITY = [
                "master_plotter",  # 总编剧 - 最优先
                "plotter",         # 编剧
                "evaluator",       # 评估员
                "writer",          # 作家
                "setting",         # 设定管理员
                "hook_manager",    # 伏笔管理员
            ]

            # 从节点配置中获取指定的领头人
            node_config = node.config or {}
            specified_leader = node_config.get("leader_agent")

            # 选择领头人
            LEADER_AGENT = None
            if specified_leader and specified_leader in discussion_agents:
                # 使用指定的领头人
                LEADER_AGENT = specified_leader
                logger.info(f"使用节点配置的领头人: {LEADER_AGENT}")
            else:
                # 按优先级从参与讨论的 Agent 中选择
                for candidate in LEADER_PRIORITY:
                    if candidate in discussion_agents:
                        LEADER_AGENT = candidate
                        logger.info(f"按优先级选择领头人: {LEADER_AGENT}")
                        break

            # 如果还是没有找到，使用第一个参与讨论的 Agent
            if not LEADER_AGENT and discussion_agents:
                LEADER_AGENT = list(discussion_agents)[0]
                logger.info(f"使用默认领头人: {LEADER_AGENT}")

            # 如果没有任何参与者，创建一个默认领头人
            if not LEADER_AGENT:
                LEADER_AGENT = "plotter"
                logger.warning(f"没有参与讨论的 Agent，使用默认领头人: {LEADER_AGENT}")

            leader_name = AGENT_NAME_MAP.get(LEADER_AGENT, LEADER_AGENT)

            # 构建参与讨论的 Agent 列表
            participants = []
            for agent_type in discussion_agents:
                agent_name = AGENT_NAME_MAP.get(agent_type, agent_type)
                participants.append({
                    "type": agent_type,
                    "name": agent_name,
                    "role": self._get_agent_role_description(agent_type),
                    "is_leader": agent_type == LEADER_AGENT,
                })

            # 获取角色列表：讨论阶段只能把可正面出场的角色作为参会/分析对象，死亡或未激活角色仅进入约束说明。
            constraints = self._build_character_constraint_state(execution.context)
            present_names = constraints.get("present_character_names") or []
            characters = present_names
            if not characters:
                characters = [
                    c.get("name", "未知角色")
                    for c in self._ensure_context_list(execution.context.get("characters", []))
                    if isinstance(c, dict) and self._can_character_perform(c, execution.context.get("chapter_num"))[0]
                ]

            if not characters and db:
                try:
                    chars = await db.get_all_characters(execution.project_id)
                    characters = [
                        c.get("name", "未知角色")
                        for c in (chars or [])
                        if isinstance(c, dict) and self._can_character_perform(c, execution.context.get("chapter_num"))[0]
                    ]
                except Exception as e:
                    logger.warning(f"获取角色失败: {e}")

            # 提取讨论上下文
            chapter_title = execution.context.get("chapter_title", "当前章节")
            current_plot_summary = execution.context.get("current_plot_summary", "")
            written_content = execution.context.get("written_content", "")
            evaluation_result = execution.context.get("evaluation_result", {})
            plot_outline = execution.context.get("plot_outline", [])

            execution.context["project_id"] = execution.project_id

            discussion_messages = []

            # ========== 第一步：领头人开启会话 ==========
            leader_agent = await self._get_agent_for_discussion(LEADER_AGENT, execution.project_id)

            # 如果选定的领头人无法获取实例，尝试其他候选人
            if not leader_agent:
                for candidate in LEADER_PRIORITY:
                    if candidate in discussion_agents:
                        leader_agent = await self._get_agent_for_discussion(candidate, execution.project_id)
                        if leader_agent:
                            LEADER_AGENT = candidate
                            leader_name = AGENT_NAME_MAP.get(LEADER_AGENT, candidate)
                            logger.info(f"领头人实例获取回退: {LEADER_AGENT}")
                            break

            # 最后回退到 plotter
            if not leader_agent:
                leader_agent = await self._get_agent_for_discussion("plotter", execution.project_id)
                if leader_agent:
                    LEADER_AGENT = "plotter"
                    leader_name = "编剧"
                    logger.info("领头人最终回退到: plotter")

            if leader_agent:
                opening_message = await self._generate_leader_opening(
                    leader_agent, chapter_title, current_plot_summary,
                    written_content, plot_outline, evaluation_result, participants,
                    context=execution.context,
                )
                if opening_message:
                    discussion_messages.append(opening_message)
                    await self._broadcast_discussion_message_event(execution.id, opening_message, is_leader_action=True)

            # 广播讨论开始
            await self._broadcast_status(execution.id, "group_discussion_started", {
                "node_id": node.id,
                "leader": leader_name,
                "participants": [p["name"] for p in participants],
                "characters": characters,
                "discussion_topic": f"《{chapter_title}》创作讨论会",
                "message": f"【{leader_name}】已开启集体讨论会",
            })

            # ========== 第二步：各 Agent 发表意见 ==========
            excluded_from_discussion = {
                "world_map_manager", "event_generator", "procgen",
                "scene_coordinator", "summarizer", "master_plotter", "plotter"
            }

            agent_speaking_order = [
                "evaluator", "hook_manager", "setting",
                "writer", "character"
            ]

            for agent_type in agent_speaking_order:
                if agent_type in excluded_from_discussion:
                    continue

                if agent_type in executed_agents:
                    await asyncio.sleep(0.3)

                    agent = await self._get_agent_for_discussion(agent_type, execution.project_id)
                    if agent:
                        message = await self._generate_agent_opinion(
                            agent, agent_type, chapter_title,
                            discussion_messages, written_content,
                            evaluation_result, characters, execution.context
                        )
                        if message:
                            discussion_messages.append(message)
                            await self._broadcast_discussion_message_event(execution.id, message, broadcast_to_all=True)

            # ========== 第三步：领头人汇总，请求用户确认 ==========
            if leader_agent and discussion_messages:
                summary_request = await self._generate_leader_summary_request(
                    leader_agent, chapter_title, discussion_messages, context=execution.context
                )
                if summary_request:
                    discussion_messages.append(summary_request)
                    await self._broadcast_discussion_message_event(execution.id, summary_request, is_leader_action=True)

            # ========== 第四步：存储讨论结果 ==========
            full_content = "\n".join([
                msg.get("content", "") for msg in discussion_messages if msg.get("content")
            ])
            discussion_summary = discussion_messages[-1].get("content", "") if discussion_messages else ""

            discussion_result = {
                "mode": "meeting",
                "topic": f"《{chapter_title}》创作讨论会",
                "discussion_topic": f"《{chapter_title}》创作讨论会",
                "leader": leader_name,
                "leader_type": LEADER_AGENT,  # 保存领头人类型，用于后续确认
                "participants": participants,
                "messages": discussion_messages,
                "characters": characters,
                "full_content": full_content,
                "summary": discussion_summary,
                "timestamp": datetime.now().isoformat(),
                "status": "waiting_confirmation",
            }

            execution.context["group_discussion"] = discussion_result
            execution.context["dialogues"] = discussion_messages
            execution.context["discussion_summary"] = discussion_summary
            execution.context["last_discussion_summary"] = discussion_summary

            discussion_history = execution.context.get("discussion_history", [])
            discussion_history.append(discussion_result)
            execution.context["discussion_history"] = discussion_history

            logger.info(f"集体讨论节点完成，共 {len(discussion_messages)} 条发言，等待用户确认")

            return {
                "status": "completed",
                "mode": "meeting",
                "discussion_topic": f"《{chapter_title}》创作讨论会",
                "topic": f"《{chapter_title}》创作讨论会",
                "leader": leader_name,
                "leader_type": LEADER_AGENT,
                "participants": participants,
                "messages": discussion_messages,
                "characters": characters,
                "full_content": full_content,
                "summary": discussion_summary,
            }

        except Exception as e:
            logger.error(f"集体讨论节点执行失败: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return {"error": str(e), "status": "failed"}

    async def _get_agent_for_discussion(
        self,
        agent_type: str,
        project_id: str,
    ):
        """获取用于讨论的 Agent 实例"""
        if not self._agent_provider:
            return None
        try:
            return await self._agent_provider(agent_type, project_id)
        except Exception as e:
            logger.warning(f"获取 {agent_type} Agent 失败: {e}")
            return None

    async def _get_model_response_text(self, model, prompt: str) -> str:
        """统一提取模型响应文本，兼容 Anthropic block list 格式"""
        from langchain_core.messages import HumanMessage

        response = await model.ainvoke([HumanMessage(content=prompt)])
        raw_content = getattr(response, "content", "")

        if isinstance(raw_content, str):
            return raw_content.strip()

        if isinstance(raw_content, list):
            parts: List[str] = []
            for block in raw_content:
                text = getattr(block, "text", None)
                if text:
                    parts.append(text)
                elif isinstance(block, dict) and block.get("text"):
                    parts.append(str(block["text"]))
                elif block is not None:
                    parts.append(str(block))
            return "\n".join(part for part in parts if part).strip()

        if raw_content is None:
            return ""

        return str(raw_content).strip()

    async def _generate_plotter_opening(
        self,
        agent,
        chapter_title: str,
        plot_summary: str,
        written_content: str,
        plot_outline: List,
        evaluation_result: Dict,
        context: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """编剧 Agent 开场发言（要有实质内容，引导讨论方向）"""
        try:
            # 安全地格式化 issues（可能是 dict 列表或 str 列表）
            issues_raw = evaluation_result.get('issues', [])
            if issues_raw:
                issues_formatted = '\n'.join([
                    '- ' + (str(i) if isinstance(i, str) else i.get('issue', i.get('description', str(i))))
                    for i in issues_raw
                ])
            else:
                issues_formatted = "无明显问题"

            config_prompt_data = await self._build_workflow_config_prompt_with_trace(
                AgentType.MASTER_PLOTTER,
                (context or {}).get("project_id") if isinstance(context, dict) else None,
                "workflow_discussion_opening",
                {"scenario": "workflow_discussion_opening", "chapter_title": chapter_title},
            )
            config_prompt = config_prompt_data.get("content", "")
            prompt_render_trace = config_prompt_data.get("trace", {}) or {}
            config_prompt_source = config_prompt_data.get("source", "missing")
            sections = [
                self._format_workflow_prompt_block("Master Plotter 配置规则", config_prompt),
                self._format_workflow_prompt_block("章节", chapter_title),
                self._format_workflow_prompt_block("已写内容", written_content or "暂无"),
                self._format_workflow_prompt_block("当前剧情摘要", plot_summary or "暂无"),
                self._format_workflow_prompt_block("剧情规划进度", {
                    "planned_plot_points": len(plot_outline),
                    "plot_outline": plot_outline or [],
                }),
                self._format_workflow_prompt_block("评估反馈", {
                    "score": evaluation_result.get('score', 'N/A'),
                    "quality_passed": bool(evaluation_result.get('quality_passed', True)),
                    "issues": issues_formatted,
                    "summary": evaluation_result.get('summary', ''),
                }),
            ]
            prompt = "\n\n".join(section for section in sections if section)

            if hasattr(agent, 'model') and agent.model:
                content = await self._get_model_response_text(agent.model, prompt)

                return {
                    "agent": "编剧",
                    "type": "plotter",
                    "content": content,
                    "is_llm_generated": True,
                    "config_prompt_source": config_prompt_source,
                    "prompt_render_trace": prompt_render_trace,
                }
        except Exception as e:
            logger.error(f"编剧开场生成失败: {e}")

        # 回退到静态消息
        return {
            "agent": "编剧",
            "type": "plotter",
            "content": f"【开场】{chapter_title}的创作已完成，请各位从各自专业角度进行分析讨论。",
            "is_llm_generated": False,
            "config_prompt_source": "missing",
            "prompt_render_trace": None,
        }

    def _format_workflow_prompt_block(self, title: str, value: Any) -> str:
        """格式化工作流 prompt 上下文块。"""
        if value is None or value == "":
            return ""
        if isinstance(value, str):
            text = value
        else:
            try:
                text = json.dumps(value, ensure_ascii=False, indent=2)
            except Exception:
                text = str(value)
        return f"【{title}】\n{text}"

    def _workflow_md_prompt_id(self, scenario: str) -> Optional[str]:
        """将工作流场景映射到 prompts/**/*.md 资产。"""
        return {
            "workflow_discussion_opening": "function_workflow_discussion_opening",
            "workflow_discussion_summary": "function_workflow_discussion_summary",
            "workflow_agent_opinion": "function_workflow_agent_opinion",
            "workflow_scene_direction": "function_workflow_scene_direction",
            "workflow_character_performance": "function_workflow_character_performance",
            "workflow_performance_summary": "function_workflow_performance_summary",
        }.get(scenario or "")

    def _load_workflow_md_prompt_content(self, prompt_id: str) -> str:
        """加载工作流 md prompt 资产，供 Agent Template 不可用时短期兜底。"""
        try:
            from app.services.md_file_service import get_md_file_service

            md_service = get_md_file_service()
            prompt = md_service.get_prompt(prompt_id)
            if prompt:
                content = prompt.get("content") or prompt.get("raw_content") or ""
                if content:
                    return content.strip()
        except Exception as e:
            logger.warning("加载工作流 md prompt 失败: prompt_id=%s, error=%s", prompt_id, e)
        return ""

    def _build_workflow_md_prompt_fallback_with_trace(
        self,
        agent_type: AgentType,
        project_id: Optional[str],
        scenario: str,
    ) -> Dict[str, Any]:
        """构建工作流辅助 prompt 的 md fallback trace。"""
        prompt_id = self._workflow_md_prompt_id(scenario)
        content = self._load_workflow_md_prompt_content(prompt_id) if prompt_id else ""
        fallback_used = "workflow_md_prompt_fallback" if content else "workflow_agent_template_fallback"
        trace = {
            "agent_type": agent_type.value,
            "scenario": scenario or "default",
            "project_id": project_id,
            "template_id": None,
            "template_scenario": None,
            "config_id": None,
            "prompt_ids": [prompt_id] if content and prompt_id else [],
            "skill_ids": [],
            "skills": None,
            "writing_rule_ids": [],
            "writing_rules": None,
            "context_blocks": [],
            "fallbacks_used": [fallback_used],
            "deprecated_sources_used": [] if content else ["WorkflowEngine._build_workflow_config_prompt"],
        }
        return {
            "content": content,
            "trace": trace,
            "source": "md_prompt_fallback" if content else "missing",
        }

    async def _build_workflow_config_prompt_with_trace(
        self,
        agent_type: AgentType,
        project_id: Optional[str],
        scenario: str,
        variables: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """通过 Agent Template 构建工作流辅助 prompt，并返回 trace。"""
        if not project_id:
            return self._build_workflow_md_prompt_fallback_with_trace(agent_type, project_id, scenario)
        try:
            from app.services.agent_prompt_service import get_agent_prompt_service

            service = get_agent_prompt_service()
            prompt_data = await service.build_agent_prompt_with_trace(
                agent_type=agent_type.value,
                project_id=project_id,
                variables=variables or {},
                scenario=scenario,
            )
            prompt = prompt_data.get("content", "")
            if not prompt:
                fallback_data = self._build_workflow_md_prompt_fallback_with_trace(agent_type, project_id, scenario)
                cache_key = self._workflow_config_trace_key(agent_type, project_id, scenario)
                self._workflow_config_prompt_traces[cache_key] = fallback_data["trace"]
                return fallback_data
            trace = prompt_data.get("trace", {}) or {}
            cache_key = self._workflow_config_trace_key(agent_type, project_id, scenario)
            self._workflow_config_prompt_traces[cache_key] = trace
            return {"content": prompt, "trace": trace, "source": "agent_template_runtime"}
        except Exception as e:
            logger.warning(
                "加载工作流 Agent Template prompt 失败: agent=%s, scenario=%s, error=%s",
                agent_type.value,
                scenario,
                e,
            )
            fallback_data = self._build_workflow_md_prompt_fallback_with_trace(agent_type, project_id, scenario)
            cache_key = self._workflow_config_trace_key(agent_type, project_id, scenario)
            self._workflow_config_prompt_traces[cache_key] = fallback_data["trace"]
            return fallback_data

    async def _build_workflow_config_prompt(
        self,
        agent_type: AgentType,
        project_id: Optional[str],
        scenario: str,
        variables: Optional[Dict[str, Any]] = None,
    ) -> str:
        """通过 Agent Template 构建工作流辅助 prompt。"""
        prompt_data = await self._build_workflow_config_prompt_with_trace(
            agent_type,
            project_id,
            scenario,
            variables,
        )
        return prompt_data.get("content", "")

    async def _generate_leader_opening(
        self,
        agent,
        chapter_title: str,
        plot_summary: str,
        written_content: str,
        plot_outline: List,
        evaluation_result: Dict,
        participants: List[Dict],
        context: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """领头人开启会话。"""
        try:
            participant_names = [p["name"] for p in participants if not p.get("is_leader")]
            context = context or {}
            constraint_text = self._format_agent_constraint_context(context)
            config_prompt_data = await self._build_workflow_config_prompt_with_trace(
                AgentType.MASTER_PLOTTER,
                context.get("project_id"),
                "workflow_discussion_opening",
                {"scenario": "workflow_discussion_opening", "chapter_title": chapter_title},
            )
            config_prompt = config_prompt_data.get("content", "")
            prompt_render_trace = config_prompt_data.get("trace", {}) or {}
            config_prompt_source = config_prompt_data.get("source", "missing")
            sections = [
                self._format_workflow_prompt_block("Master Plotter 配置规则", config_prompt),
                self._format_workflow_prompt_block("参会人员", ", ".join(participant_names) or "暂无"),
                self._format_workflow_prompt_block("章节", chapter_title),
                self._format_workflow_prompt_block("已写内容", written_content or "暂无"),
                self._format_workflow_prompt_block("当前剧情摘要", plot_summary or "暂无"),
                self._format_workflow_prompt_block("剧情大纲", plot_outline or "暂无"),
                self._format_workflow_prompt_block("评估结果", {"score": evaluation_result.get("score", "N/A"), "summary": evaluation_result.get("summary", "")}),
                self._format_workflow_prompt_block("工作流角色/设定约束", constraint_text or "当前未形成额外角色出场约束。"),
            ]
            prompt = "\n\n".join(section for section in sections if section)

            if hasattr(agent, 'model') and agent.model:
                content = await self._get_model_response_text(agent.model, prompt)

                return {
                    "agent": "总编剧",
                    "type": "master_plotter",
                    "content": content,
                    "is_llm_generated": True,
                    "is_leader_action": True,
                    "action": "open_session",
                    "config_prompt_source": config_prompt_source,
                    "prompt_render_trace": prompt_render_trace,
                }
        except Exception as e:
            logger.error(f"领头人开场生成失败: {e}")

        return {
            "agent": "总编剧",
            "type": "master_plotter",
            "content": f"【宣布讨论开始】各位，《{chapter_title}》创作讨论会现在开始。请各位从专业角度发表意见。",
            "is_llm_generated": False,
            "is_leader_action": True,
            "action": "open_session",
            "config_prompt_source": "missing",
            "prompt_render_trace": None,
        }

    async def _generate_leader_summary_request(
        self,
        agent,
        chapter_title: str,
        discussion_messages: List[Dict],
        context: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """领头人汇总讨论并请求用户确认。"""
        try:
            context = context or {}
            messages_summary = []
            for msg in discussion_messages:
                agent_name = msg.get("agent", "Unknown")
                content = msg.get("content", "")
                messages_summary.append(f"【{agent_name}】{content}")

            config_prompt_data = await self._build_workflow_config_prompt_with_trace(
                AgentType.MASTER_PLOTTER,
                context.get("project_id"),
                "workflow_discussion_summary",
                {"scenario": "workflow_discussion_summary", "chapter_title": chapter_title},
            )
            config_prompt = config_prompt_data.get("content", "")
            prompt_render_trace = config_prompt_data.get("trace", {}) or {}
            config_prompt_source = config_prompt_data.get("source", "missing")
            sections = [
                self._format_workflow_prompt_block("Master Plotter 配置规则", config_prompt),
                self._format_workflow_prompt_block("讨论记录", "\n".join(messages_summary)),
                self._format_workflow_prompt_block(
                    "工作流角色/设定约束",
                    self._format_agent_constraint_context(context) or "当前未形成额外角色出场约束。",
                ),
            ]
            prompt = "\n\n".join(section for section in sections if section)

            if hasattr(agent, 'model') and agent.model:
                content = await self._get_model_response_text(agent.model, prompt)

                return {
                    "agent": "总编剧",
                    "type": "master_plotter",
                    "content": content,
                    "is_llm_generated": True,
                    "is_leader_action": True,
                    "action": "request_confirmation",
                    "config_prompt_source": config_prompt_source,
                    "prompt_render_trace": prompt_render_trace,
                }
        except Exception as e:
            logger.error(f"领头人汇总生成失败: {e}")

        return {
            "agent": "总编剧",
            "type": "master_plotter",
            "content": f"【汇总】本次讨论共{len(discussion_messages)}位Agent发言。请确认是否同意讨论结果？",
            "is_llm_generated": False,
            "is_leader_action": True,
            "action": "request_confirmation",
            "config_prompt_source": "missing",
            "prompt_render_trace": None,
        }

    async def _generate_leader_closing(
        self,
        agent,
        chapter_title: str,
        approved: bool,
        feedback: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        领头人结束会话

        Args:
            agent: 领头人 Agent
            chapter_title: 章节标题
            approved: 用户是否同意
            feedback: 用户反馈（不同意时）
        """
        try:
            if approved:
                content = f"【宣布讨论结束】感谢各位的参与。《{chapter_title}》讨论结果已确认，我们将按照讨论意见继续创作。"
            else:
                content = f"【宣布讨论结束】用户对讨论结果有不同意见。反馈：{feedback or '需要重新讨论'}。我们将根据反馈调整后重新开始。"

            return {
                "agent": "总编剧",
                "type": "master_plotter",
                "content": content,
                "is_llm_generated": False,
                "is_leader_action": True,
                "action": "close_session",
                "approved": approved,
            }
        except Exception as e:
            logger.error(f"领头人结束生成失败: {e}")
            return None

    async def _generate_agent_opinion(
        self,
        agent,
        agent_type: str,
        chapter_title: str,
        previous_messages: List[Dict],
        written_content: str,
        evaluation_result: Dict,
        characters: List[str],
        context: Dict,
    ) -> Optional[Dict[str, Any]]:
        """各 Agent 发表意见。"""
        AGENT_NAME_MAP = {
            "evaluator": "评估员",
            "hook_manager": "伏笔管理员",
            "setting": "设定管理员",
            "world_map_manager": "地图管理员",
            "event_generator": "事件生成器",
            "writer": "作家",
            "character": "角色代表",
        }
        AGENT_TYPE_MAP = {
            "evaluator": AgentType.EVALUATOR,
            "hook_manager": AgentType.HOOK_MANAGER,
            "setting": AgentType.SETTING,
            "writer": AgentType.WRITER,
            "character": AgentType.CHARACTER,
        }

        try:
            mapped_agent_type = AGENT_TYPE_MAP.get(agent_type)
            if not mapped_agent_type:
                return None

            issues_raw = evaluation_result.get('issues', [])
            if issues_raw:
                issues_formatted = ', '.join([
                    str(i) if isinstance(i, str) else i.get('issue', i.get('description', str(i)))
                    for i in issues_raw
                ])
            else:
                issues_formatted = '无明显问题'

            if characters:
                char_names = [
                    str(c) if isinstance(c, str) else c.get('name', '未知角色')
                    for c in characters
                ]
                characters_formatted = ', '.join(char_names)
            else:
                characters_formatted = '暂无角色'

            previous_discussion = []
            for m in previous_messages:
                speaker = m.get('agent', '某Agent')
                content_preview = m.get('content', '')
                previous_discussion.append(f"【{speaker}】\n{content_preview}")

            config_prompt_data = await self._build_workflow_config_prompt_with_trace(
                mapped_agent_type,
                context.get("project_id"),
                "workflow_agent_opinion",
                {
                    "scenario": "workflow_agent_opinion",
                    "chapter_title": chapter_title,
                    "agent_type": agent_type,
                },
            )
            config_prompt = config_prompt_data.get("content", "")
            prompt_render_trace = config_prompt_data.get("trace", {}) or {}
            config_prompt_source = config_prompt_data.get("source", "missing")
            sections = [
                self._format_workflow_prompt_block("Agent 配置规则", config_prompt),
                self._format_workflow_prompt_block("当前发言身份", AGENT_NAME_MAP.get(agent_type, agent_type)),
                self._format_workflow_prompt_block("章节", chapter_title),
                self._format_workflow_prompt_block("章节内容（用于分析）", written_content or "暂无"),
                self._format_workflow_prompt_block("评估结果", {
                    "score": evaluation_result.get('score', 'N/A'),
                    "issues": issues_formatted,
                    "summary": evaluation_result.get('summary', ''),
                }),
                self._format_workflow_prompt_block("参与角色", characters_formatted),
                self._format_workflow_prompt_block("世界观设定", context.get("world_info", {})),
                self._format_workflow_prompt_block("当前伏笔状态", context.get('existing_hooks', [])),
                self._format_workflow_prompt_block("工作流角色/设定约束", self._format_agent_constraint_context(context)),
                self._format_workflow_prompt_block("之前的讨论要点", "\n".join(previous_discussion)),
            ]
            prompt = "\n\n".join(section for section in sections if section)

            if hasattr(agent, 'model') and agent.model:
                content = await self._get_model_response_text(agent.model, prompt)

                return {
                    "agent": AGENT_NAME_MAP.get(agent_type, agent_type),
                    "type": agent_type,
                    "content": content,
                    "is_llm_generated": True,
                    "config_prompt_source": config_prompt_source,
                    "prompt_render_trace": prompt_render_trace,
                }
        except Exception as e:
            logger.error(f"{agent_type} 意见生成失败: {e}")

        return {
            "agent": AGENT_NAME_MAP.get(agent_type, agent_type),
            "type": agent_type,
            "content": f"【{AGENT_NAME_MAP.get(agent_type, agent_type)}观点】从我的专业角度，本章表现符合预期，建议继续保持。",
            "is_llm_generated": False,
            "config_prompt_source": "missing",
            "prompt_render_trace": None,
        }

    def _get_agent_role_description(self, agent_type: str) -> str:
        """获取 Agent 的角色描述"""
        ROLE_DESCRIPTIONS = {
            "plotter": "负责剧情整体规划和节奏把控",
            "master_plotter": "统筹全局，协调各 Agent 工作",
            "writer": "负责文字创作和表现",
            "evaluator": "负责质量评估和问题诊断",
            "hook_manager": "负责伏笔的设计和追踪",
            "setting": "负责世界观设定的维护",
            "world_map_manager": "负责地图和地点的管理",
            "event_generator": "负责事件的生成和追踪",
            "character": "代表角色视角参与讨论",
            "summarizer": "负责内容摘要和整理",
        }
        return ROLE_DESCRIPTIONS.get(agent_type, f"负责{agent_type}相关工作")

    async def _generate_scene_directions(
        self,
        plotter_agent,
        context: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """让编剧 Agent 生成场景设定和表演方向。"""
        try:
            world_info = context.get("world_info", {})
            characters = context.get("characters", [])
            chapter_goal = context.get("chapter_goal", "")
            plot_outline = context.get("plot_outline", [])

            char_info = []
            for c in characters:
                if isinstance(c, dict):
                    name = c.get("name", "未知")
                    tier = c.get("importance_tier", 3)
                    ctype = c.get("character_type", "supporting")
                    is_protag = c.get("is_protagonist", False)
                    is_antag = c.get("is_antagonist", False)
                    char_info.append(
                        f"- {name}（层级{tier}，{ctype}"
                        f"{'，主角' if is_protag else ''}{'，反派' if is_antag else ''}）"
                    )

            config_prompt_data = await self._build_workflow_config_prompt_with_trace(
                AgentType.MASTER_PLOTTER,
                context.get("project_id"),
                "workflow_scene_direction",
                {"scenario": "workflow_scene_direction"},
            )
            config_prompt = config_prompt_data.get("content", "")
            prompt_render_trace = config_prompt_data.get("trace", {}) or {}
            config_prompt_source = config_prompt_data.get("source", "missing")
            sections = [
                self._format_workflow_prompt_block("Master Plotter 配置规则", config_prompt),
                self._format_workflow_prompt_block("世界观设定", {
                    "name": world_info.get('name', '未知世界'),
                    "world_type": world_info.get('world_type', '奇幻'),
                    "background": world_info.get('background', world_info.get('description', '')),
                    "tone": world_info.get('tone', '正剧'),
                    "rules": world_info.get('rules', {}),
                }),
                self._format_workflow_prompt_block("当前章节目标", chapter_goal or '推进主线剧情'),
                self._format_workflow_prompt_block("参与角色（含重要性层级）", "\n".join(char_info) or "暂无"),
                self._format_workflow_prompt_block("剧情大纲（最近）", plot_outline or '暂无'),
                self._format_workflow_prompt_block("工作流角色/设定约束", self._format_agent_constraint_context(context)),
            ]
            prompt = "\n\n".join(section for section in sections if section)

            content = await self._get_model_response_text(plotter_agent.model, prompt)

            json_match = re.search(r'```json\s*(.*?)\s*```', content, re.DOTALL)
            json_str = json_match.group(1) if json_match else content

            result = json.loads(json_str)
            if isinstance(result, dict):
                result["config_prompt_source"] = config_prompt_source
                result["prompt_render_trace"] = prompt_render_trace
            logger.info(f"编剧生成场景方向: {result.get('scene_type')} - {result.get('main_scene')}")
            return result

        except Exception as e:
            logger.error(f"生成场景方向失败: {e}")
            return None


    async def _generate_character_performance(
        self,
        agent,
        char_data: Dict[str, Any],
        scene_directions: Dict[str, Any],
        world_info: Dict[str, Any],
        conversation_history: List[Dict],
        is_interactive: bool,
        turn_number: int,
        total_characters: int,
        distributed_info: Dict[str, Any] = None,
    ) -> Optional[Dict[str, Any]]:
        """生成单个角色的表演内容。"""
        try:
            char_name = char_data.get("name", "未知角色")
            char_role = scene_directions.get("character_roles", {}).get(char_name, {})
            personality = char_data.get("personality", "")
            background = char_data.get("background", char_data.get("description", ""))
            speech_pattern = char_data.get("speech_pattern", "")
            traits = char_data.get("traits", [])
            importance_tier = char_data.get("importance_tier", 3)
            character_type = char_data.get("character_type", "supporting")
            is_protagonist = char_data.get("is_protagonist", False)
            is_antagonist = char_data.get("is_antagonist", False)
            tier_context = self._get_character_tier_context(
                importance_tier, character_type, is_protagonist, is_antagonist
            )
            known_info = self._get_character_known_info(char_data, scene_directions, world_info)

            history_lines = []
            if is_interactive and conversation_history:
                for h in conversation_history:
                    speaker = h.get("agent", "某角色")
                    content = h.get("content", "")
                    history_lines.append(f"{speaker}: {content}")

            config_prompt_data = await self._build_workflow_config_prompt_with_trace(
                AgentType.CHARACTER,
                char_data.get("project_id") or world_info.get("project_id"),
                "workflow_character_performance",
                {
                    "scenario": "workflow_character_performance",
                    "character_background": background or "普通背景",
                    "character_personality": personality or "根据剧情需要表现",
                    "character_goals": char_data.get("goals", ""),
                },
            )
            config_prompt = config_prompt_data.get("content", "")
            prompt_render_trace = config_prompt_data.get("trace", {}) or {}
            config_prompt_source = config_prompt_data.get("source", "missing")
            sections = [
                self._format_workflow_prompt_block("Character 配置规则", config_prompt),
                self._format_workflow_prompt_block("当前扮演角色", char_name),
                self._format_workflow_prompt_block("角色档案", {
                    "name": char_name,
                    "type": character_type,
                    "importance_tier": importance_tier,
                    "tier_context": tier_context,
                    "personality": personality or '根据剧情需要表现',
                    "background": background or '普通背景',
                    "speech_pattern": speech_pattern or '自然随意',
                    "traits": traits,
                }),
                self._format_workflow_prompt_block("角色已知信息", known_info),
                self._format_workflow_prompt_block("当前场景", {
                    "scene_mode": '同场景互动' if is_interactive else '独立场景',
                    "main_scene": scene_directions.get('main_scene', '未设定'),
                    "atmosphere": scene_directions.get('atmosphere', '正剧'),
                    "time_of_day": scene_directions.get('time_of_day', '未设定'),
                    "role_in_scene": char_role.get('role_in_scene', '参与者'),
                    "emotional_state": char_role.get('emotional_state', '平静'),
                    "main_action": char_role.get('main_action', '自然互动'),
                    "hidden_motivation": char_role.get('secret_motivation') or char_role.get('hidden_motivation') or '',
                }),
                self._format_workflow_prompt_block("角色可知上下文包", {
                    "visible_scene": scene_directions.get('main_scene', '未设定'),
                    "public_history": history_lines,
                    "known_info": known_info,
                    "boundary_source": "function_workflow_character_performance",
                    "delta_semantics": "relationship_delta/state_delta are proposals, not persisted facts",
                }),
                self._format_workflow_prompt_block("当前场景中你能听到/看到的对话", "\n".join(history_lines)),
            ]
            prompt = "\n\n".join(section for section in sections if section)

            content = await self._get_model_response_text(agent.model, prompt)
            public_content = str(content or "").strip()
            performance_packet = self._build_character_performance_packet({
                "agent": char_name,
                "character": char_name,
                "public_content": public_content,
                "content": public_content,
                "dialogue": public_content,
                "action": "",
                "private_thought": "",
                "emotion": char_role.get('emotional_state', ''),
                "intent": char_role.get('main_action', ''),
                "perceived_facts": known_info,
                "misinterpretations": [],
                "withheld_information": [],
                "relationship_delta": [],
                "state_delta": [],
                "continuity_notes": [],
                "warnings": [],
                "round": turn_number,
            }, source_character=char_name)

            return {
                "agent": char_name,
                "type": "character_performance",
                "content": public_content,
                "public_content": public_content,
                "dialogue": public_content,
                "action": "",
                "private_thought": "",
                "inner_thought": "",
                "emotion": char_role.get('emotional_state', ''),
                "intent": char_role.get('main_action', ''),
                "perceived_facts": known_info,
                "misinterpretations": [],
                "withheld_information": [],
                "relationship_delta": [],
                "state_delta": [],
                "continuity_notes": [],
                "warnings": [],
                "character_performance_packet": performance_packet,
                "is_llm_generated": True,
                "turn_number": turn_number,
                "total_characters": total_characters,
                "character_tier": importance_tier,
                "character_type": character_type,
                "config_prompt_source": config_prompt_source,
                "prompt_render_trace": prompt_render_trace,
            }

        except Exception as e:
            logger.error(f"角色表演生成失败: {e}")
            return {
                "agent": char_data.get("name", "未知角色"),
                "type": "character_performance",
                "content": "（角色表演生成失败，跳过）",
                "is_llm_generated": False,
                "config_prompt_source": "missing",
                "prompt_render_trace": None,
            }


    def _get_character_tier_context(
        self,
        importance_tier: int,
        character_type: str,
        is_protagonist: bool,
        is_antagonist: bool,
    ) -> Dict[str, Any]:
        """返回角色层级的结构化运行时上下文；稳定表演规则由 prompt/skill 资产提供。"""
        if is_protagonist:
            role_type = "protagonist"
        elif is_antagonist:
            role_type = "antagonist"
        elif importance_tier == 1:
            role_type = "core"
        elif importance_tier == 2:
            role_type = "major"
        elif importance_tier == 3:
            role_type = "regular"
        else:
            role_type = "minor_or_background"

        return {
            "role_type": role_type,
            "importance_tier": importance_tier,
            "character_type": character_type,
            "is_protagonist": bool(is_protagonist),
            "is_antagonist": bool(is_antagonist),
        }

    def _get_character_tier_description(
        self,
        importance_tier: int,
        character_type: str,
        is_protagonist: bool,
        is_antagonist: bool,
    ) -> str:
        """兼容旧调用：返回结构化层级上下文的紧凑文本表示。"""
        return json.dumps(
            self._get_character_tier_context(
                importance_tier,
                character_type,
                is_protagonist,
                is_antagonist,
            ),
            ensure_ascii=False,
        )

    def _get_character_known_info(
        self,
        char_data: Dict[str, Any],
        scene_directions: Dict[str, Any],
        world_info: Dict[str, Any],
    ) -> str:
        """
        获取角色已知信息（信息隔离）

        只返回该角色能够知道的信息，不包含上帝视角的内容
        """
        char_name = char_data.get("name", "未知角色")
        is_protagonist = char_data.get("is_protagonist", False)
        importance_tier = char_data.get("importance_tier", 3)

        # 基础世界观信息（大多数角色都知道）
        known_parts = []

        if world_info:
            # 普通角色都知道的世界常识
            known_parts.append(f"世界：{world_info.get('name', '未知世界')}")
            known_parts.append(f"世界类型：{world_info.get('world_type', '奇幻')}")

            # 根据角色重要性，知道不同程度的世界规则
            rules = world_info.get('rules', {})
            if rules and importance_tier <= 2:
                # 重要角色可能知道更多规则
                if isinstance(rules, dict):
                    rule_items = list(rules.items())
                    known_parts.append("已知世界规则：")
                    for k, v in rule_items:
                        known_parts.append(f"  - {k}: {v}")

        # 角色自己的经历和知识
        background = char_data.get("background", "")
        if background:
            known_parts.append(f"你的经历：{background}")

        # 角色与其他角色的关系（只知道自己这边的关系）
        relationships = char_data.get("relationships", [])
        if relationships:
            known_parts.append("你认识的人：")
            for rel in relationships:
                target = rel.get("target", rel.get("name", "某人"))
                rel_type = rel.get("type", rel.get("relationship", "认识"))
                known_parts.append(f"  - {target}（{rel_type}）")

        # 场景相关的已知信息
        if scene_directions.get("main_scene"):
            known_parts.append(f"你当前位置：{scene_directions.get('main_scene')}")

        # 主角可能知道更多信息
        if is_protagonist:
            known_parts.append("作为主角，你肩负着重要的使命")
            goals = char_data.get("goals", [])
            if goals:
                known_parts.append(f"你的目标：{goals[0] if isinstance(goals[0], str) else goals[0].get('description', str(goals[0]))}")

        return "\n".join(known_parts) if known_parts else "你是这个世界的一员，了解基本的常识。"

    async def _generate_performance_summary(
        self,
        summarizer_agent,
        scene_directions: Dict[str, Any],
        performance_messages: List[Dict],
        project_id: Optional[str] = None,
        role_performance_gate: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """生成表演总结。"""
        try:
            performances = []
            for msg in performance_messages:
                agent = msg.get("agent", "未知")
                content = msg.get("public_content") or msg.get("content", "")
                performances.append(f"【{agent}】\n{content}")

            summary_variables = {
                "scenario": "workflow_performance_summary",
                "public_performances": [
                    {
                        "agent": msg.get("agent"),
                        "content": msg.get("public_content") or msg.get("content", ""),
                        "dialogue": msg.get("dialogue", ""),
                        "action": msg.get("action", ""),
                        "emotion": msg.get("emotion", ""),
                    }
                    for msg in performance_messages
                    if msg.get("public_content") or msg.get("content")
                ],
                "private_performances": [
                    {
                        "agent": msg.get("agent"),
                        "private_thought": msg.get("private_thought", ""),
                        "intent": msg.get("intent", ""),
                        "withheld_information": msg.get("withheld_information", []),
                        "misinterpretations": msg.get("misinterpretations", []),
                    }
                    for msg in performance_messages
                    if msg.get("private_thought") or msg.get("intent") or msg.get("withheld_information")
                ],
                "relationship_deltas": [
                    {"source_character": msg.get("agent"), **delta}
                    for msg in performance_messages
                    for delta in (msg.get("relationship_delta", []) or [])
                    if isinstance(delta, dict)
                ],
                "state_deltas": [
                    {"source_character": msg.get("agent"), **delta}
                    for msg in performance_messages
                    for delta in (msg.get("state_delta", []) or [])
                    if isinstance(delta, dict)
                ],
                "continuity_notes": [
                    {"source_character": msg.get("agent"), "note": note}
                    for msg in performance_messages
                    for note in (msg.get("continuity_notes", []) or [])
                ],
                "performance_warnings": [
                    {"source_character": msg.get("agent"), "warning": warning}
                    for msg in performance_messages
                    for warning in (msg.get("warnings", []) or [])
                ],
                "role_performance_gate": role_performance_gate or {},
                "role_performance_gate_passed": (role_performance_gate or {}).get("passed", True),
                "role_performance_gate_blockers": (role_performance_gate or {}).get("blockers", []),
                "role_performance_gate_warnings": (role_performance_gate or {}).get("warnings", []),
            }
            config_prompt_data = await self._build_workflow_config_prompt_with_trace(
                AgentType.SUMMARIZER,
                project_id,
                "workflow_performance_summary",
                summary_variables,
            )
            config_prompt = config_prompt_data.get("content", "")
            prompt_render_trace = config_prompt_data.get("trace", {}) or {}
            config_prompt_source = config_prompt_data.get("source", "missing")
            sections = [
                self._format_workflow_prompt_block("Summarizer 配置规则", config_prompt),
                self._format_workflow_prompt_block("场景设定", {
                    "main_scene": scene_directions.get('main_scene', '未设定'),
                    "atmosphere": scene_directions.get('atmosphere', '正剧'),
                    "plot_focus": scene_directions.get('plot_focus', '推进剧情'),
                }),
                self._format_workflow_prompt_block("公开角色表演内容", "\n".join(performances)),
                self._format_workflow_prompt_block("私有表演与连续性素材", {
                    "private_performances": summary_variables["private_performances"],
                    "relationship_deltas": summary_variables["relationship_deltas"],
                    "state_deltas": summary_variables["state_deltas"],
                    "continuity_notes": summary_variables["continuity_notes"],
                    "performance_warnings": summary_variables["performance_warnings"],
                    "role_performance_gate": summary_variables["role_performance_gate"],
                    "role_performance_gate_passed": summary_variables["role_performance_gate_passed"],
                    "role_performance_gate_blockers": summary_variables["role_performance_gate_blockers"],
                    "role_performance_gate_warnings": summary_variables["role_performance_gate_warnings"],
                }),
            ]
            prompt = "\n\n".join(section for section in sections if section)

            content = await self._get_model_response_text(summarizer_agent.model, prompt)

            json_match = re.search(r'```json\s*(.*?)\s*```', content, re.DOTALL)
            json_str = json_match.group(1) if json_match else content

            try:
                result = json.loads(json_str)
                return {
                    "agent": "总结员",
                    "type": "performance_summary",
                    "content": result.get("summary", content),
                    "data": result,
                    "is_llm_generated": True,
                    "config_prompt_source": config_prompt_source,
                    "prompt_render_trace": prompt_render_trace,
                }
            except json.JSONDecodeError:
                return {
                    "agent": "总结员",
                    "type": "performance_summary",
                    "content": content,
                    "is_llm_generated": True,
                    "config_prompt_source": config_prompt_source,
                    "prompt_render_trace": prompt_render_trace,
                }

        except Exception as e:
            logger.error(f"表演总结生成失败: {e}")
            return {
                "agent": "总结员",
                "type": "performance_summary",
                "content": "角色演绎已完成，各角色展现了精彩的表现。",
                "is_llm_generated": False,
                "config_prompt_source": "missing",
                "prompt_render_trace": None,
            }


    async def _execute_parallel_node(
        self,
        node: WorkflowNode,
        execution: WorkflowExecution,
        db=None,
    ) -> Dict[str, Any]:
        """执行并行节点"""
        # 并行执行在拓扑排序时处理
        return {"parallel_executed": True}

    async def _execute_branch(
        self,
        execution: WorkflowExecution,
        workflow: WorkflowDefinition,
        start_node_id: str,
        end_node_id: Optional[str],
        db=None,
    ) -> Dict[str, Any]:
        """
        执行并行分支中的所有节点（从 start_node_id 到 end_node_id）

        Args:
            execution: 工作流执行实例
            workflow: 工作流定义
            start_node_id: 分支起始节点ID
            end_node_id: 分支结束节点ID（汇聚点，不包含在执行中）
            db: 数据库连接

        Returns:
            Dict: 分支执行结果
        """
        results = {}
        current_id = start_node_id
        max_iterations = 50  # 防止无限循环
        iteration = 0

        logger.info(f"开始执行并行分支: {start_node_id} -> {end_node_id}")

        while current_id and iteration < max_iterations:
            iteration += 1

            # 检查是否到达汇聚点
            if end_node_id and current_id == end_node_id:
                logger.info(f"分支执行到达汇聚点: {current_id}")
                break

            # 检查是否被暂停或取消
            if execution.status in [WorkflowStatus.PAUSED, WorkflowStatus.CANCELLED]:
                logger.info(f"分支执行被暂停或取消")
                break

            # 获取当前节点
            node = next((n for n in workflow.nodes if n.id == current_id), None)
            if not node:
                logger.warning(f"分支节点 {current_id} 不存在")
                break

            # 如果是结束节点，退出分支
            if node.node_type == NodeType.END:
                logger.info(f"分支到达结束节点: {current_id}")
                break

            # 执行节点
            await self._execute_node(execution, node, db)

            # 检查节点是否失败
            node_state = execution.node_states.get(current_id)
            if node_state and node_state.status == NodeStatus.FAILED:
                logger.error(f"分支节点 {current_id} 执行失败: {node_state.error}")
                results[current_id] = {"error": node_state.error}
                break

            results[current_id] = node_state.output_data if node_state else {}

            # 获取下一个节点
            next_id = self._get_branch_next_node(current_id, workflow, end_node_id)
            current_id = next_id

        logger.info(f"并行分支执行完成，共执行 {iteration} 个节点")
        return results

    def _get_branch_next_node(
        self,
        current_node_id: str,
        workflow: WorkflowDefinition,
        merge_node_id: Optional[str],
    ) -> Optional[str]:
        """
        获取分支中的下一个节点（跳过汇聚点）

        Args:
            current_node_id: 当前节点ID
            workflow: 工作流定义
            merge_node_id: 汇聚点节点ID

        Returns:
            Optional[str]: 下一个节点ID，如果没有则返回None
        """
        outgoing_edges = [e for e in workflow.edges if e.source == current_node_id]

        if not outgoing_edges:
            return None

        # 获取第一个出边
        for edge in outgoing_edges:
            # 跳过指向汇聚点的边（由主流程处理汇聚点）
            if merge_node_id and edge.target == merge_node_id:
                return None
            return edge.target

        return None

    def _topological_sort(
        self,
        nodes: List[WorkflowNode],
        edges: List[WorkflowEdge],
    ) -> List[str]:
        """拓扑排序"""
        # 构建邻接表和入度表
        graph = defaultdict(list)
        in_degree = defaultdict(int)

        node_ids = {n.id for n in nodes}
        for node_id in node_ids:
            in_degree[node_id] = 0

        for edge in edges:
            if edge.source in node_ids and edge.target in node_ids:
                graph[edge.source].append(edge.target)
                in_degree[edge.target] += 1

        # 处理并行节点
        parallel_groups = self._identify_parallel_groups(nodes, edges)

        # BFS 拓扑排序
        queue = deque([n for n in node_ids if in_degree[n] == 0])
        result = []

        while queue:
            node_id = queue.popleft()
            result.append(node_id)

            for neighbor in graph[node_id]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        return result

    def _identify_parallel_groups(
        self,
        nodes: List[WorkflowNode],
        edges: List[WorkflowEdge],
    ) -> List[Set[str]]:
        """识别并行执行的节点组"""
        # 简化实现：并行节点后的直接后继为一组
        parallel_nodes = [n for n in nodes if n.node_type == NodeType.PARALLEL]
        groups = []

        for pn in parallel_nodes:
            group = set()
            for edge in edges:
                if edge.source == pn.id:
                    group.add(edge.target)
            if group:
                groups.append(group)

        return groups

    def _get_parallel_next_nodes(
        self,
        parallel_node_id: str,
        workflow: WorkflowDefinition,
    ) -> List[str]:
        """
        获取并行节点后需要并行执行的节点列表

        Args:
            parallel_node_id: 并行节点的ID
            workflow: 工作流定义

        Returns:
            List[str]: 需要并行执行的节点ID列表
        """
        next_nodes = []

        # 获取并行节点的所有出边
        outgoing_edges = [e for e in workflow.edges if e.source == parallel_node_id]

        for edge in outgoing_edges:
            target_node = next((n for n in workflow.nodes if n.id == edge.target), None)
            if target_node:
                # 跳过结束节点
                if target_node.node_type == NodeType.END:
                    continue
                next_nodes.append(edge.target)

        logger.info(f"并行节点 {parallel_node_id} 后有 {len(next_nodes)} 个节点需要并行执行: {next_nodes}")
        return next_nodes

    def _find_merge_node(
        self,
        parallel_node_ids: List[str],
        workflow: WorkflowDefinition,
    ) -> Optional[str]:
        """
        找到并行执行分支的汇聚节点

        Args:
            parallel_node_ids: 并行执行的节点ID列表
            workflow: 工作流定义

        Returns:
            Optional[str]: 汇聚节点的ID，如果没有则返回None
        """
        if not parallel_node_ids:
            return None

        # 获取所有节点的出边目标
        all_targets = set()
        for node_id in parallel_node_ids:
            for edge in workflow.edges:
                if edge.source == node_id:
                    all_targets.add(edge.target)

        # 构建每个并行节点可达的节点集合
        reachable_from_each = []
        for node_id in parallel_node_ids:
            reachable = self._get_all_reachable_nodes(node_id, workflow)
            reachable_from_each.append(reachable)

        # 找到所有并行分支都能到达的第一个节点（汇聚点）
        if reachable_from_each:
            common_nodes = reachable_from_each[0]
            for reachable_set in reachable_from_each[1:]:
                common_nodes = common_nodes.intersection(reachable_set)

            # 找到最近的汇聚点（拓扑序最靠前的）
            if common_nodes:
                # 排除并行节点本身
                common_nodes = common_nodes - set(parallel_node_ids)

                if common_nodes:
                    # 返回第一个找到的汇聚点
                    # 优先返回非结束节点
                    for node_id in common_nodes:
                        node = next((n for n in workflow.nodes if n.id == node_id), None)
                        if node and node.node_type != NodeType.END:
                            logger.info(f"找到并行汇聚节点: {node_id}")
                            return node_id

                    # 如果没有非结束节点，返回第一个
                    merge_node = list(common_nodes)[0]
                    logger.info(f"找到并行汇聚节点（结束节点）: {merge_node}")
                    return merge_node

        logger.info("未找到并行汇聚节点")
        return None

    def _get_all_reachable_nodes(
        self,
        start_node_id: str,
        workflow: WorkflowDefinition,
    ) -> Set[str]:
        """
        获取从指定节点可达的所有节点

        Args:
            start_node_id: 起始节点ID
            workflow: 工作流定义

        Returns:
            Set[str]: 可达节点的ID集合
        """
        reachable = set()
        queue = deque([start_node_id])

        while queue:
            current = queue.popleft()
            if current in reachable:
                continue

            reachable.add(current)

            # 添加所有后继节点
            for edge in workflow.edges:
                if edge.source == current and edge.target not in reachable:
                    queue.append(edge.target)

        return reachable

    # 重试上限常量
    MAX_RETRY_COUNT = 3

    def _get_next_node(
        self,
        current_node_id: str,
        execution: "WorkflowExecution",
        workflow: "WorkflowDefinition",
    ) -> Optional[str]:
        """获取下一个节点（支持条件分支）"""
        # 获取当前节点的所有出边
        outgoing_edges = [e for e in workflow.edges if e.source == current_node_id]

        if not outgoing_edges:
            return None

        # 获取当前节点
        current_node = next((n for n in workflow.nodes if n.id == current_node_id), None)

        # 如果是条件节点，根据上下文中的评估结果选择分支
        if current_node and current_node.node_type == NodeType.CONDITION:
            # 从上下文中获取评估结果
            evaluation_passed = execution.context.get("evaluation_passed", False)
            retry_count = execution.context.get("retry_count", 0)
            logger.info(f"条件节点评估结果: {evaluation_passed}, 当前重试次数: {retry_count}")

            # 分类边：pass 边和 retry 边
            pass_edge = None
            retry_edge = None
            undefined_edges = []

            for edge in outgoing_edges:
                condition = edge.condition or {}
                result = condition.get("result")

                if result == "pass":
                    pass_edge = edge
                elif result == "retry":
                    retry_edge = edge
                else:
                    # 没有定义 condition.result 的边
                    undefined_edges.append(edge)

            # 如果有未定义的边，记录警告
            if undefined_edges:
                logger.warning(f"条件节点 {current_node_id} 有 {len(undefined_edges)} 条边未定义 condition.result")

            # 根据评估结果选择分支
            if evaluation_passed:
                # 评估通过：走 pass 分支
                if pass_edge:
                    logger.info(f"条件通过，跳转到节点: {pass_edge.target}")
                    # 清除评估相关上下文，准备下一轮
                    execution.context["retry_count"] = 0
                    execution.context["is_retry"] = False
                    return pass_edge.target
                else:
                    # 没有 pass 边，使用第一条未定义的边或报错
                    if undefined_edges:
                        logger.warning(f"未找到 pass 边，使用未定义的边: {undefined_edges[0].target}")
                        return undefined_edges[0].target
                    logger.error(f"条件节点 {current_node_id} 没有 pass 边")
                    return None
            else:
                # 评估不通过：走 retry 分支
                if retry_edge:
                    # 检查是否达到重试上限
                    if retry_count >= self.MAX_RETRY_COUNT:
                        logger.warning(f"已达到重试上限 ({self.MAX_RETRY_COUNT} 次)，强制通过")
                        execution.context["forced_pass"] = True
                        execution.context["forced_pass_reason"] = f"已重试 {retry_count} 次仍未通过评估，自动接受当前内容"
                        if isinstance(execution.context.get("quality_gate"), dict):
                            execution.context["quality_gate"] = {
                                **execution.context["quality_gate"],
                                "status": "forced_pass",
                                "forced_pass": True,
                                "forced_pass_reason": execution.context["forced_pass_reason"],
                            }
                            execution.context["quality_gate_status"] = "forced_pass"
                        # 找到 pass 分支并返回
                        if pass_edge:
                            # 清理控制上下文；保留 retry_history / quality_gate_history / revision_history 作为审计记录。
                            execution.context["retry_count"] = 0
                            execution.context["is_retry"] = False
                            return pass_edge.target
                        # 如果没有 pass 分支，返回 undefined 边或 retry 边
                        return undefined_edges[0].target if undefined_edges else retry_edge.target

                    # 正常重试逻辑
                    retry_count += 1
                    execution.context["retry_count"] = retry_count

                    # 保存历史评估反馈
                    retry_history = execution.context.get("retry_history", [])
                    current_feedback = execution.context.get("evaluation_feedback", {})
                    retry_history.append({
                        "attempt": retry_count,
                        "feedback": current_feedback,
                    })
                    execution.context["retry_history"] = retry_history

                    # 构建重试上下文提示
                    execution.context["is_retry"] = True
                    execution.context["retry_message"] = self._build_retry_message(retry_count, current_feedback)

                    logger.info(f"条件不通过，第 {retry_count} 次重试，跳转到节点: {retry_edge.target}")
                    return retry_edge.target
                else:
                    # 没有 retry 边，评估不通过但没有重试路径
                    logger.warning(f"条件节点 {current_node_id} 没有 retry 边，但评估未通过")
                    # 使用 pass 边或 undefined 边
                    if pass_edge:
                        logger.info(f"使用 pass 边继续: {pass_edge.target}")
                        return pass_edge.target
                    if undefined_edges:
                        return undefined_edges[0].target
                    return None

        # 普通节点：返回第一个出边指向的节点
        return outgoing_edges[0].target if outgoing_edges else None

    def _build_retry_message(self, retry_count: int, feedback: Dict[str, Any]) -> str:
        """构建重试提示消息"""
        issues = feedback.get("issues", [])
        suggestions = feedback.get("suggestions", [])
        summary = feedback.get("summary", "")
        score = feedback.get("score", 0)

        msg_parts = [f"【第 {retry_count} 次重试】"]
        msg_parts.append(f"上次评估得分: {score}/10")

        # 最后一次重试时添加警告
        if retry_count >= self.MAX_RETRY_COUNT - 1:
            msg_parts.append(f"⚠️ 这是最后一次重试机会，如果仍不通过将自动接受当前内容")

        if summary:
            msg_parts.append(f"评估摘要: {summary}")

        if issues:
            msg_parts.append(f"需要改进的问题:")
            for i, issue in enumerate(issues, 1):
                msg_parts.append(f"  {i}. {issue}")

        if suggestions:
            msg_parts.append(f"改进建议:")
            for i, suggestion in enumerate(suggestions, 1):
                msg_parts.append(f"  {i}. {suggestion}")

        return "\n".join(msg_parts)

    def _get_start_node_id(self, workflow: "WorkflowDefinition") -> Optional[str]:
        """获取起始节点ID"""
        start_nodes = [n for n in workflow.nodes if n.node_type == NodeType.START]
        return start_nodes[0].id if start_nodes else None

    # ==================== 执行控制 ====================

    def _execution_lock(self, execution_id: str) -> asyncio.Lock:
        lock = self._execution_locks.get(execution_id)
        if lock is None:
            lock = asyncio.Lock()
            self._execution_locks[execution_id] = lock
        return lock

    async def _get_or_load_execution(self, execution_id: str, db=None) -> Optional[WorkflowExecution]:
        execution = self._executions.get(execution_id)
        if not execution and db:
            execution = await self._load_execution_from_db(execution_id, db)
            if execution:
                self._executions[execution_id] = execution
        return execution

    def _active_task_for_execution(self, execution_id: str) -> Optional[asyncio.Task]:
        task = self._running_tasks.get(execution_id)
        if task and not task.done():
            return task
        if task and task.done():
            self._running_tasks.pop(execution_id, None)
        return None

    def _is_execution_lease_expired(self, execution: WorkflowExecution, now: Optional[datetime] = None) -> bool:
        if execution.status != WorkflowStatus.RUNNING or not execution.lease_expires_at:
            return False
        expires_at = execution.lease_expires_at
        if now is not None:
            current_time = now
        elif expires_at.tzinfo:
            current_time = datetime.now(tz=expires_at.tzinfo)
        else:
            current_time = datetime.now()
        return expires_at <= current_time

    def inspect_execution_staleness(self, execution: WorkflowExecution) -> Dict[str, Any]:
        status = execution.status.value if hasattr(execution.status, "value") else str(execution.status)
        now = datetime.now(tz=execution.lease_expires_at.tzinfo) if execution.lease_expires_at and execution.lease_expires_at.tzinfo else datetime.now()
        lease_expired = self._is_execution_lease_expired(execution, now)
        active_task = self._active_task_for_execution(execution.id) is not None
        lease_seconds_remaining = None
        if execution.lease_expires_at:
            lease_seconds_remaining = max(0, int((execution.lease_expires_at - now).total_seconds()))
        stale_history = execution.context.get("stale_execution_history") if isinstance(execution.context, dict) else None
        if not isinstance(stale_history, list):
            stale_history = []
        safe_actions: List[str] = []
        recommendation = "执行状态正常，无需治理。"
        suspected_stale = status == WorkflowStatus.RUNNING.value and lease_expired and not active_task
        if suspected_stale:
            safe_actions = ["mark_failed", "inspect_only"]
            recommendation = "运行租约已过期且当前进程没有活跃任务，建议标记失败后从失败节点恢复。"
        elif status == WorkflowStatus.RUNNING.value and active_task:
            safe_actions = ["inspect_only"]
            recommendation = "检测到活跃运行任务，不能标记陈旧；可继续观察。"
        elif status == WorkflowStatus.RUNNING.value:
            safe_actions = ["inspect_only"]
            recommendation = "执行仍在租约窗口内，暂不应人工改写状态。"
        elif status == WorkflowStatus.FAILED.value:
            safe_actions = ["recover", "inspect_only"]
            recommendation = "执行已失败，可使用恢复或修复并恢复流程处理。"
        return self._serialize_for_json({
            "execution_id": execution.id,
            "workflow_id": execution.workflow_id,
            "project_id": execution.project_id,
            "status": status,
            "active_task": active_task,
            "suspected_stale": suspected_stale,
            "safe_actions": safe_actions,
            "recommendation": recommendation,
            "lease": {
                "lease_expires_at": execution.lease_expires_at,
                "last_heartbeat_at": execution.last_heartbeat_at,
                "expired": lease_expired,
                "seconds_remaining": lease_seconds_remaining,
            },
            "history": {
                "count": len(stale_history),
                "latest": stale_history[-1] if stale_history else None,
            },
        })

    async def inspect_execution_staleness_state(self, execution_id: str, db=None) -> Optional[Dict[str, Any]]:
        execution = await self._get_or_load_execution(execution_id, db)
        if not execution:
            return None
        return self.inspect_execution_staleness(execution)

    async def resolve_stale_execution(self, execution_id: str, db=None, *, action: str = "mark_failed", reason: Optional[str] = None) -> Dict[str, Any]:
        async with self._execution_lock(execution_id):
            execution = await self._get_or_load_execution(execution_id, db)
            if not execution:
                self._raise_operation_error(execution_id, "stale", "工作流执行不存在", code="workflow_execution_not_found", http_status=404)
            inspection = self.inspect_execution_staleness(execution)
            if action == "inspect_only":
                return {"success": True, "action": action, "inspection": inspection, "execution": self._serialize_for_json(execution)}
            if action != "mark_failed":
                self._raise_operation_error(
                    execution_id,
                    "stale",
                    f"不支持的陈旧执行治理动作: {action}",
                    status=execution.status,
                    payload={"allowed_actions": ["inspect_only", "mark_failed"]},
                )
            if execution.status != WorkflowStatus.RUNNING:
                self._raise_operation_error(
                    execution_id,
                    "stale",
                    "只有 running 状态的执行可以标记为陈旧失败",
                    status=execution.status,
                    payload={"allowed_statuses": [WorkflowStatus.RUNNING.value]},
                )
            if self._active_task_for_execution(execution.id):
                self._raise_operation_error(
                    execution_id,
                    "stale",
                    "执行存在活跃运行任务，不能标记陈旧",
                    status=execution.status,
                    code="workflow_execution_active_task_conflict",
                )
            if not self._is_execution_lease_expired(execution):
                self._raise_operation_error(
                    execution_id,
                    "stale",
                    "执行租约尚未过期，不能标记陈旧",
                    status=execution.status,
                    payload={"lease_expires_at": execution.lease_expires_at.isoformat() if execution.lease_expires_at else None},
                )
            await self._mark_running_execution_stale_if_orphaned(execution, db, operation=reason or "manual_stale_resolution")
            return {
                "success": True,
                "action": action,
                "inspection": self.inspect_execution_staleness(execution),
                "execution": self._serialize_for_json(execution),
            }

    async def _mark_running_execution_stale_if_orphaned(
        self,
        execution: WorkflowExecution,
        db=None,
        *,
        operation: str,
    ) -> bool:
        if execution.status != WorkflowStatus.RUNNING:
            return False
        if self._active_task_for_execution(execution.id):
            return False
        if not self._is_execution_lease_expired(execution):
            return False

        now = datetime.now()
        stale_entry = {
            "detected_at": now.isoformat(),
            "operation": operation,
            "previous_status": execution.status.value,
            "lease_expires_at": execution.lease_expires_at.isoformat() if execution.lease_expires_at else None,
            "last_heartbeat_at": execution.last_heartbeat_at.isoformat() if execution.last_heartbeat_at else None,
            "reason": "running execution has no active task and its lease has expired",
        }
        stale_history = execution.context.get("stale_execution_history")
        if not isinstance(stale_history, list):
            stale_history = []
            execution.context["stale_execution_history"] = stale_history
        stale_history.append(stale_entry)
        failed_node_id = execution.current_node or next(
            (
                node_id
                for node_id, state in execution.node_states.items()
                if state.status in {NodeStatus.RUNNING, NodeStatus.PENDING}
            ),
            None,
        )
        if failed_node_id:
            node_state = execution.node_states.get(failed_node_id) or NodeExecutionState(node_id=failed_node_id)
            node_state.status = NodeStatus.FAILED
            node_state.completed_at = now
            node_state.error = "工作流执行租约已过期，运行任务已丢失"
            execution.node_states[failed_node_id] = node_state
            execution.current_node = failed_node_id

        execution.status = WorkflowStatus.FAILED
        execution.error = "工作流执行租约已过期，且当前进程没有活跃运行任务；已标记为失败，可从失败节点恢复。"
        execution.completed_at = now
        execution.lease_expires_at = None
        execution.resume_cursor = {
            **(execution.resume_cursor or {}),
            "stale_detected_at": now.isoformat(),
            "stale_operation": operation,
        }
        if db:
            await self._save_execution_to_db(execution, db)
            await self._mark_operation_terminal(execution, db)
        if db:
            await self._broadcast_status(execution.id, "workflow_execution_stale", self._build_execution_event_payload(
                execution,
                stale_entry=stale_entry,
            ))
        logger.warning("工作流执行租约过期并被标记为失败: %s", execution.id)
        return True

    def _raise_operation_error(
        self,
        execution_id: str,
        operation: str,
        message: str,
        *,
        code: str = "workflow_operation_conflict",
        status: Optional[WorkflowStatus] = None,
        http_status: int = 409,
        payload: Optional[Dict[str, Any]] = None,
    ) -> None:
        raise WorkflowOperationError(
            message,
            code=code,
            operation=operation,
            execution_id=execution_id,
            status=status.value if hasattr(status, "value") else status,
            http_status=http_status,
            payload=payload,
        )

    async def pause_workflow(self, execution_id: str, db=None) -> bool:
        """暂停工作流"""
        async with self._execution_lock(execution_id):
            execution = await self._get_or_load_execution(execution_id, db)
            if not execution:
                self._raise_operation_error(execution_id, "pause", "工作流执行不存在", code="workflow_execution_not_found", http_status=404)

            await self._mark_running_execution_stale_if_orphaned(execution, db, operation="pause")
            if execution.status == WorkflowStatus.PAUSED:
                return True
            if execution.status != WorkflowStatus.RUNNING:
                self._raise_operation_error(
                    execution_id,
                    "pause",
                    "只能暂停运行中的工作流执行",
                    status=execution.status,
                    payload={"allowed_statuses": [WorkflowStatus.RUNNING.value]},
                )

            execution.status = WorkflowStatus.PAUSED
            execution.lease_expires_at = None

            replay_path = await self._export_execution_replay_markdown(execution, db=db)
            if replay_path:
                execution.context["replay_markdown_path"] = replay_path

            if db:
                await self._save_execution_to_db(execution, db)

            await self._broadcast_status(execution_id, "workflow_paused", self._build_execution_event_payload(execution))
            logger.info(f"暂停工作流: {execution_id}")
            return True

    async def resume_workflow(self, execution_id: str, db=None) -> bool:
        """恢复工作流执行"""
        async with self._execution_lock(execution_id):
            execution = await self._get_or_load_execution(execution_id, db)
            if not execution:
                logger.warning(f"工作流执行不存在: {execution_id}")
                self._raise_operation_error(execution_id, "resume", "工作流执行不存在", code="workflow_execution_not_found", http_status=404)

            active_task = self._active_task_for_execution(execution_id)
            if active_task:
                if execution.status == WorkflowStatus.RUNNING:
                    return True
                self._raise_operation_error(
                    execution_id,
                    "resume",
                    "工作流执行已有活跃运行任务，不能重复恢复",
                    status=execution.status,
                    code="workflow_execution_active_task_conflict",
                )

            await self._mark_running_execution_stale_if_orphaned(execution, db, operation="resume")
            if execution.status == WorkflowStatus.RUNNING:
                workflow = await self.get_workflow(execution.workflow_id, db)
                if not workflow:
                    self._raise_operation_error(execution_id, "resume", f"工作流不存在: {execution.workflow_id}", status=execution.status)
                self._start_workflow_task(execution_id, workflow, db)
                return True
            if execution.status != WorkflowStatus.PAUSED:
                self._raise_operation_error(
                    execution_id,
                    "resume",
                    "只能恢复暂停中的工作流执行",
                    status=execution.status,
                    payload={"allowed_statuses": [WorkflowStatus.PAUSED.value]},
                )

            execution.status = WorkflowStatus.RUNNING
            execution.cancel_requested = False
            execution.last_heartbeat_at = datetime.now()
            execution.lease_expires_at = execution.last_heartbeat_at + timedelta(seconds=getattr(settings, "operation_lease_ttl_seconds", 60))

            if db:
                await self._save_execution_to_db(execution, db)

            await self._broadcast_status(execution_id, "workflow_resumed", self._build_execution_event_payload(execution))
            logger.info(f"恢复工作流: {execution_id}")

            workflow = await self.get_workflow(execution.workflow_id, db)
            if not workflow:
                self._raise_operation_error(execution_id, "resume", f"工作流不存在: {execution.workflow_id}", status=execution.status)
            self._start_workflow_task(execution_id, workflow, db)

            return True

    def _find_failed_recovery_target(
        self,
        execution: "WorkflowExecution",
        workflow: WorkflowDefinition,
        *,
        mode: str = "retry_failed",
        node_id: Optional[str] = None,
    ) -> str:
        workflow_node_ids = {node.id for node in workflow.nodes}
        normalized_mode = (mode or "retry_failed").strip().lower()
        if normalized_mode == "retry_failed":
            failed_entry = next(
                (
                    (failed_node_id, state)
                    for failed_node_id, state in execution.node_states.items()
                    if state.status == NodeStatus.FAILED
                ),
                None,
            )
            if not failed_entry:
                raise ValueError("执行中没有可恢复的失败节点")
            target_node_id = failed_entry[0]
        elif normalized_mode == "retry_from_node":
            if not node_id:
                raise ValueError("retry_from_node 模式需要 node_id")
            target_node_id = node_id
        else:
            raise ValueError("不支持的恢复模式")
        if target_node_id not in workflow_node_ids:
            raise ValueError(f"恢复节点不存在: {target_node_id}")
        return target_node_id

    async def diagnose_failed_workflow_node(
        self,
        execution_id: str,
        db=None,
        *,
        node_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        execution = self._executions.get(execution_id)
        if not execution and db:
            execution = await self._load_execution_from_db(execution_id, db)
            if execution:
                self._executions[execution_id] = execution
        if not execution:
            raise ValueError("执行不存在")
        workflow = await self.get_workflow(execution.workflow_id, db)
        if not workflow:
            raise ValueError(f"工作流不存在: {execution.workflow_id}")
        from app.services.workflow_failure_diagnosis_service import workflow_failure_diagnosis_service
        return workflow_failure_diagnosis_service.diagnose(execution, workflow, node_id=node_id)

    def _build_node_remediation_diff(
        self,
        node,
        patch: Dict[str, Any],
    ) -> Dict[str, Any]:
        before: Dict[str, Any] = {}
        after: Dict[str, Any] = {}
        changed_fields: List[str] = []

        if "agent_type" in patch and patch.get("agent_type") is not None:
            new_agent_type = str(patch["agent_type"]).strip()
            if not new_agent_type:
                raise ValueError("agent_type 不能为空")
            if node.agent_type != new_agent_type:
                before["agent_type"] = node.agent_type
                after["agent_type"] = new_agent_type
                changed_fields.append("agent_type")
                node.agent_type = new_agent_type

        if "scenario" in patch and patch.get("scenario") is not None:
            new_scenario = str(patch["scenario"]).strip()
            if not new_scenario:
                raise ValueError("scenario 不能为空")
            config = dict(node.config or {})
            if config.get("scenario") != new_scenario:
                before["scenario"] = config.get("scenario")
                after["scenario"] = new_scenario
                changed_fields.append("scenario")
                config["scenario"] = new_scenario
                node.config = config

        if not changed_fields:
            raise ValueError("没有可应用的修复字段")
        return {"before": before, "after": after, "changed_fields": changed_fields}

    async def validate_failed_node_remediation(
        self,
        execution_id: str,
        db=None,
        *,
        node_id: Optional[str] = None,
        patch: Optional[Dict[str, Any]] = None,
        context_patch: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        execution = await self._get_or_load_execution(execution_id, db)
        if not execution:
            self._raise_operation_error(execution_id, "remediate", "执行不存在", code="workflow_execution_not_found", http_status=404)
        if self._active_task_for_execution(execution_id):
            self._raise_operation_error(
                execution_id,
                "remediate",
                "工作流执行仍在运行，不能修复",
                status=execution.status,
                code="workflow_execution_active_task_conflict",
            )
        await self._mark_running_execution_stale_if_orphaned(execution, db, operation="remediate")
        if execution.status != WorkflowStatus.FAILED:
            self._raise_operation_error(
                execution_id,
                "remediate",
                "只有失败状态的工作流执行可以修复",
                status=execution.status,
                payload={"allowed_statuses": [WorkflowStatus.FAILED.value]},
            )
        workflow = await self.get_workflow(execution.workflow_id, db)
        if not workflow:
            raise ValueError(f"工作流不存在: {execution.workflow_id}")
        target_node_id = self._find_failed_recovery_target(
            execution,
            workflow,
            mode="retry_from_node" if node_id else "retry_failed",
            node_id=node_id,
        )
        if context_patch:
            protected_keys = [key for key in context_patch if is_protected_context_key(key)]
            if protected_keys:
                raise ValueError(f"修复上下文不能覆盖受保护字段: {', '.join(sorted(protected_keys))}")
        workflow_copy = workflow.model_copy(deep=True)
        target_node = next((node for node in workflow_copy.nodes if node.id == target_node_id), None)
        if not target_node:
            raise ValueError(f"修复节点不存在: {target_node_id}")
        target_node_type = target_node.node_type.value if hasattr(target_node.node_type, "value") else str(target_node.node_type)
        if target_node_type != "agent":
            raise ValueError("当前仅支持修复 Agent 节点")
        diff = self._build_node_remediation_diff(target_node, patch or {})
        validation = self.validate_workflow(workflow_copy)
        if not validation.valid:
            raise ValueError(f"修复后的工作流验证失败: {validation.errors}")
        diagnosis = await self.diagnose_failed_workflow_node(execution_id, db, node_id=target_node_id)
        return {
            "valid": True,
            "execution_id": execution_id,
            "workflow_id": workflow.id,
            "node_id": target_node_id,
            "diagnosis": diagnosis,
            "diff": diff,
            "warnings": validation.warnings,
        }

    async def remediate_failed_workflow_node(
        self,
        execution_id: str,
        db=None,
        *,
        node_id: Optional[str] = None,
        patch: Optional[Dict[str, Any]] = None,
        reason: Optional[str] = None,
        context_patch: Optional[Dict[str, Any]] = None,
        reset_downstream: bool = True,
    ) -> Dict[str, Any]:
        async with self._execution_lock(execution_id):
            preview = await self.validate_failed_node_remediation(
                execution_id,
                db,
                node_id=node_id,
                patch=patch,
                context_patch=context_patch,
            )
            execution = self._executions[execution_id]
            workflow = await self.get_workflow(execution.workflow_id, db)
            target_node = next(node for node in workflow.nodes if node.id == preview["node_id"])
            diff = self._build_node_remediation_diff(target_node, patch or {})
            validation = self.validate_workflow(workflow)
            if not validation.valid:
                raise ValueError(f"修复后的工作流验证失败: {validation.errors}")
            workflow.updated_at = datetime.now()
            if db:
                await self._save_workflow_to_db(workflow, db)
            remediation_history = execution.context.get("remediation_history")
            if not isinstance(remediation_history, list):
                remediation_history = []
                execution.context["remediation_history"] = remediation_history
            applied_at = datetime.now().isoformat()
            previous_error = execution.error or (execution.node_states.get(preview["node_id"]).error if execution.node_states.get(preview["node_id"]) else None)
            remediation_entry = {
                "attempt": len(remediation_history) + 1,
                "node_id": preview["node_id"],
                "category": preview["diagnosis"].get("category"),
                "diagnosis_category": preview["diagnosis"].get("category"),
                "reason": reason or "manual_remediation",
                "started_at": applied_at,
                "applied_at": applied_at,
                "previous_error": previous_error,
                "diff": diff,
            }
            remediation_history.append(remediation_entry)
            if db:
                await self._save_execution_to_db(execution, db)
            await self._broadcast_status(execution_id, "workflow_node_remediated", self._build_execution_event_payload(
                execution,
                node_id=preview["node_id"],
                remediation_entry=remediation_entry,
                previous_error=previous_error,
                diagnosis_category=preview["diagnosis"].get("category"),
            ))
            recovery = await self._recover_failed_workflow_locked(
                execution_id,
                db,
                mode="retry_from_node",
                node_id=preview["node_id"],
                reason=reason or "manual_remediation",
                context_patch=context_patch,
                reset_downstream=reset_downstream,
            )
            return {
                "success": True,
                "message": "失败节点已修复并开始恢复",
                "diagnosis": preview["diagnosis"],
                "remediation_entry": remediation_entry,
                "recovery": recovery,
            }

    async def recover_failed_workflow(
        self,
        execution_id: str,
        db=None,
        *,
        mode: str = "retry_failed",
        node_id: Optional[str] = None,
        reason: Optional[str] = None,
        context_patch: Optional[Dict[str, Any]] = None,
        reset_downstream: bool = True,
    ) -> Dict[str, Any]:
        """Recover a failed execution by resetting the failed node and downstream nodes."""
        async with self._execution_lock(execution_id):
            return await self._recover_failed_workflow_locked(
                execution_id,
                db,
                mode=mode,
                node_id=node_id,
                reason=reason,
                context_patch=context_patch,
                reset_downstream=reset_downstream,
            )

    async def _recover_failed_workflow_locked(
        self,
        execution_id: str,
        db=None,
        *,
        mode: str = "retry_failed",
        node_id: Optional[str] = None,
        reason: Optional[str] = None,
        context_patch: Optional[Dict[str, Any]] = None,
        reset_downstream: bool = True,
    ) -> Dict[str, Any]:
        execution = await self._get_or_load_execution(execution_id, db)
        if not execution:
            self._raise_operation_error(execution_id, "recover", "执行不存在", code="workflow_execution_not_found", http_status=404)

        if self._active_task_for_execution(execution_id):
            self._raise_operation_error(
                execution_id,
                "recover",
                "工作流执行仍在运行，不能重复恢复",
                status=execution.status,
                code="workflow_execution_active_task_conflict",
            )
        await self._mark_running_execution_stale_if_orphaned(execution, db, operation="recover")
        if execution.status != WorkflowStatus.FAILED:
            self._raise_operation_error(
                execution_id,
                "recover",
                "只有失败状态的工作流执行可以恢复",
                status=execution.status,
                payload={"allowed_statuses": [WorkflowStatus.FAILED.value]},
            )

        workflow = await self.get_workflow(execution.workflow_id, db)
        if not workflow:
            raise ValueError(f"工作流不存在: {execution.workflow_id}")
        workflow_node_ids = {node.id for node in workflow.nodes}

        normalized_mode = (mode or "retry_failed").strip().lower()
        target_node_id = self._find_failed_recovery_target(
            execution,
            workflow,
            mode=normalized_mode,
            node_id=node_id,
        )

        reset_node_ids = (
            self._collect_downstream_nodes(workflow, target_node_id)
            if reset_downstream
            else {target_node_id}
        )
        reset_node_ids = {reset_node_id for reset_node_id in reset_node_ids if reset_node_id in workflow_node_ids}
        if not reset_node_ids:
            raise ValueError("没有可重置的恢复节点")

        if context_patch:
            protected_keys = [key for key in context_patch if is_protected_context_key(key)]
            if protected_keys:
                raise ValueError(f"恢复上下文不能覆盖受保护字段: {', '.join(sorted(protected_keys))}")

        previous_status = execution.status.value
        previous_error = execution.error or execution.node_states.get(target_node_id, NodeExecutionState(node_id=target_node_id)).error
        previous_completed_at = execution.completed_at
        recovery_history = execution.context.get("recovery_history")
        if not isinstance(recovery_history, list):
            recovery_history = []
            execution.context["recovery_history"] = recovery_history
        recovery_attempt = len(recovery_history) + 1
        started_at = datetime.now()
        recovery_entry = {
            "attempt": recovery_attempt,
            "mode": normalized_mode,
            "target_node_id": target_node_id,
            "reset_node_ids": sorted(reset_node_ids),
            "reason": reason or "manual_recovery",
            "started_at": started_at.isoformat(),
            "previous_error": previous_error,
            "previous_completed_at": previous_completed_at.isoformat() if previous_completed_at else None,
            "trace_id": execution.trace_id,
            "status_at_start": previous_status,
        }
        recovery_history.append(recovery_entry)

        self._reset_nodes_for_recovery(
            execution,
            reset_node_ids,
            target_node_id=target_node_id,
            reason="恢复失败工作流",
        )
        if context_patch:
            execution.context.update(context_patch)

        execution.status = WorkflowStatus.RUNNING
        execution.started_at = started_at
        execution.error = None
        execution.completed_at = None
        execution.total_duration_ms = None
        execution.cancel_requested = False
        execution.current_node = target_node_id
        execution.last_heartbeat_at = started_at
        execution.lease_expires_at = started_at + timedelta(seconds=getattr(settings, "operation_lease_ttl_seconds", 60))
        execution.resume_cursor = {
            "recovery_attempt": recovery_attempt,
            "recovered_node_id": target_node_id,
            "reset_node_ids": sorted(reset_node_ids),
            "mode": normalized_mode,
            "started_at": started_at.isoformat(),
        }

        if db:
            await self._save_execution_to_db(execution, db)

        recovery_payload = self._build_execution_event_payload(
            execution,
            recovered_node_id=target_node_id,
            reset_node_ids=sorted(reset_node_ids),
            recovery_attempt=recovery_attempt,
            recovery_entry=recovery_entry,
            previous_error=previous_error,
        )
        await self._broadcast_status(execution_id, "workflow_recovery_started", recovery_payload)
        self._start_workflow_task(execution_id, workflow, db)
        logger.info(f"恢复失败工作流: {execution_id}, target={target_node_id}, reset={sorted(reset_node_ids)}")
        return {
            "success": True,
            "message": "工作流已从失败节点恢复",
            "execution_id": execution_id,
            "status": execution.status.value,
            "recovered_node_id": target_node_id,
            "reset_node_ids": sorted(reset_node_ids),
            "recovery_attempt": recovery_attempt,
            "trace_id": execution.trace_id,
            "recovery_entry": recovery_entry,
        }

    async def cancel_workflow(self, execution_id: str, db=None) -> bool:
        """取消工作流"""
        async with self._execution_lock(execution_id):
            execution = await self._get_or_load_execution(execution_id, db)
            if not execution:
                self._raise_operation_error(execution_id, "cancel", "工作流执行不存在", code="workflow_execution_not_found", http_status=404)

            if execution.status == WorkflowStatus.CANCELLED:
                return True
            if execution.status in [WorkflowStatus.COMPLETED, WorkflowStatus.FAILED]:
                self._raise_operation_error(
                    execution_id,
                    "cancel",
                    "只能取消待执行、运行中或暂停中的工作流执行",
                    status=execution.status,
                    payload={"allowed_statuses": [WorkflowStatus.PENDING.value, WorkflowStatus.RUNNING.value, WorkflowStatus.PAUSED.value]},
                )

            execution.cancel_requested = True
            execution.status = WorkflowStatus.CANCELLED
            execution.completed_at = datetime.now()
            execution.lease_expires_at = None

            task = self._active_task_for_execution(execution_id)
            if task:
                task.cancel()

            if db:
                await self._save_execution_to_db(execution, db)
                await self._mark_operation_terminal(execution, db)

            await self._broadcast_status(execution_id, "workflow_cancelled", self._build_execution_event_payload(
                execution,
                completed_at=execution.completed_at,
            ))
            logger.info(f"取消工作流: {execution_id}")
            return True

    async def confirm_discussion(
        self,
        execution_id: str,
        approved: bool,
        feedback: Optional[str] = None,
        db=None,
    ) -> Dict[str, Any]:
        """
        确认集体讨论结果

        流程：
        1. 领头人广播结束消息
        2. 同意 -> 工作流继续
        3. 拒绝 -> 带反馈重启工作流

        Args:
            execution_id: 执行ID
            approved: 用户是否同意讨论结果
            feedback: 用户反馈意见（不同意时必填）
            db: 数据库连接

        Returns:
            Dict: 处理结果
        """
        execution = self._executions.get(execution_id)
        if not execution:
            if db:
                execution = await self._load_execution_from_db(execution_id, db)
                if execution:
                    self._executions[execution_id] = execution

        if not execution:
            return {"success": False, "error": "执行不存在"}

        if execution.status != WorkflowStatus.PAUSED:
            return {"success": False, "error": "工作流未处于暂停状态"}

        waiting_confirmation = execution.context.get("waiting_confirmation")
        if not waiting_confirmation:
            return {"success": False, "error": "没有等待确认的讨论结果"}

        if waiting_confirmation.get("confirmed"):
            return {"success": False, "error": "讨论结果已被确认"}

        # 标记已确认
        confirmation_mode = waiting_confirmation.get("confirmation_mode") or (
            "timeout_auto_confirm" if waiting_confirmation.get("auto_confirmed") else "user_confirm"
        )
        waiting_confirmation["confirmed"] = True
        waiting_confirmation["user_approved"] = approved

        # ========== 领头人广播结束消息 ==========
        # 从上下文中获取领头人类型（在讨论时保存的）
        discussion_info = execution.context.get("group_discussion", {})
        leader_type = discussion_info.get("leader_type", "master_plotter")

        # 领头人优先级
        LEADER_PRIORITY = ["master_plotter", "plotter", "evaluator", "writer", "setting"]

        leader_agent = await self._get_agent_for_discussion(leader_type, execution.project_id)
        if not leader_agent:
            # 尝试其他候选人
            for candidate in LEADER_PRIORITY:
                leader_agent = await self._get_agent_for_discussion(candidate, execution.project_id)
                if leader_agent:
                    leader_type = candidate
                    break

        chapter_title = execution.context.get("chapter_title", "当前章节")
        if leader_agent:
            closing_message = await self._generate_leader_closing(
                leader_agent, chapter_title, approved, feedback
            )
            if closing_message:
                await self._broadcast_discussion_message_event(execution_id, closing_message, is_leader_action=True)

        # 广播讨论结束
        await self._broadcast_status(execution_id, "group_discussion_ended", {
            "approved": approved,
            "feedback": feedback,
            "message": f"讨论会结束，{'用户同意' if approved else '用户不同意'}讨论结果",
        })

        if approved:
            # 用户同意，先持久化讨论资产，再恢复工作流继续执行
            logger.info(f"用户同意讨论结果，继续执行工作流: {execution_id}")

            discussion_bundle = (
                waiting_confirmation.get("discussion_assets")
                or execution.context.get("discussion_assets")
                or {}
            )
            persistence_state = await self._persist_discussion_assets(
                execution=execution,
                bundle=discussion_bundle,
                db=db,
                confirmation_mode=confirmation_mode,
            )

            execution.context.pop("waiting_confirmation", None)
            execution.status = WorkflowStatus.RUNNING
            if db:
                await self._save_execution_to_db(execution, db)

            await self._broadcast_status(execution_id, "discussion_confirmed", {
                "approved": True,
                "confirmation_mode": confirmation_mode,
                "discussion_persistence_state": self._make_json_safe(persistence_state),
                "persisted_asset_refs": self._make_json_safe(persistence_state.get("persisted_asset_refs", {})),
                "message": "用户同意讨论结果，工作流继续执行",
            })

            workflow = await self.get_workflow(execution.workflow_id, db)
            if workflow:
                self._start_workflow_task(execution_id, workflow, db)

            return {
                "success": True,
                "approved": True,
                "confirmation_mode": confirmation_mode,
                "discussion_persistence_state": self._make_json_safe(persistence_state),
                "message": "工作流继续执行",
            }

        else:
            # 用户不同意，重置工作流并注入反馈
            if not feedback:
                return {"success": False, "error": "不同意讨论结果时必须提供反馈意见"}

            logger.info(f"用户不同意讨论结果，将重新执行工作流: {execution_id}")
            logger.info(f"用户反馈: {feedback}")

            workflow = await self.get_workflow(execution.workflow_id, db)
            if not workflow:
                return {"success": False, "error": "工作流定义不存在"}

            # 构建用户反馈上下文
            user_feedback_context = {
                "user_feedback": feedback,
                "user_feedback_timestamp": datetime.now().isoformat(),
                "retry_reason": "用户对讨论结果不满意",
                "is_retry": True,
                "retry_count": execution.context.get("retry_count", 0) + 1,
            }

            # 保留部分上下文（世界观、角色等基础信息）
            preserved_context = {
                "world_info": execution.context.get("world_info"),
                "characters": execution.context.get("characters", []),
                "project_info": execution.context.get("project_info"),
                "previous_chapters": execution.context.get("previous_chapters", []),
                "lore_entries": execution.context.get("lore_entries", []),
                "hooks": execution.context.get("hooks", []),
                "user_feedback": feedback,
                "user_feedback_context": user_feedback_context,
                "discussion_history": execution.context.get("discussion_history", []),
                "performance_history": execution.context.get("performance_history", []),
                "is_retry": True,
                "retry_count": user_feedback_context["retry_count"],
            }

            execution.context = preserved_context

            # 重置所有节点状态
            for node_id, node_state in execution.node_states.items():
                node_state.status = NodeStatus.PENDING
                node_state.started_at = None
                node_state.completed_at = None
                node_state.output_data = {}
                node_state.error = None

            execution.context["goto_retry_counts"] = {}
            execution.status = WorkflowStatus.RUNNING
            execution.current_node = None
            execution.error = None

            if db:
                await self._save_execution_to_db(execution, db)

            await self._broadcast_status(execution_id, "discussion_retry", {
                "approved": False,
                "feedback": feedback,
                "retry_count": user_feedback_context["retry_count"],
                "message": "用户不同意讨论结果，工作流将重新执行",
            })

            asyncio.create_task(self._run_workflow(execution_id, workflow, db))

            return {
                "success": True,
                "approved": False,
                "feedback": feedback,
                "retry_count": user_feedback_context["retry_count"],
                "message": f"工作流将重新执行（第 {user_feedback_context['retry_count']} 次重试）",
            }

    async def step_workflow(self, execution_id: str, db=None) -> Optional[Dict[str, Any]]:
        """
        单步执行工作流

        Args:
            execution_id: 执行ID
            db: 数据库连接

        Returns:
            Dict: 当前步骤执行结果，如果工作流已完成返回 None
        """
        execution = self._executions.get(execution_id)
        if not execution:
            # 尝试从数据库加载
            if db:
                execution = await self._load_execution_from_db(execution_id, db)
                if execution:
                    self._executions[execution_id] = execution

        if not execution:
            raise ValueError(f"执行记录不存在: {execution_id}")

        # 检查状态
        if execution.status == WorkflowStatus.COMPLETED:
            return None
        if execution.status == WorkflowStatus.FAILED:
            raise ValueError("工作流已失败")
        if execution.status == WorkflowStatus.CANCELLED:
            raise ValueError("工作流已取消")

        # 如果是首次执行，设置为运行状态
        if execution.status == WorkflowStatus.PENDING:
            execution.status = WorkflowStatus.RUNNING

        # 获取工作流定义
        workflow = await self.get_workflow(execution.workflow_id, db)
        if not workflow:
            raise ValueError(f"工作流定义不存在: {execution.workflow_id}")

        # 找到下一个待执行的节点
        next_node_id = self._get_next_pending_node(execution, workflow)

        if not next_node_id:
            # 所有节点已完成
            execution.status = WorkflowStatus.COMPLETED
            execution.completed_at = datetime.now()
            if db:
                await self._save_execution_to_db(execution, db)
            return None

        # 找到节点定义
        node = next((n for n in workflow.nodes if n.id == next_node_id), None)
        if not node:
            raise ValueError(f"节点不存在: {next_node_id}")

        # 更新当前节点
        execution.current_node = next_node_id

        # 执行节点
        await self._execute_node(execution, node, db)

        # 保存状态
        if db:
            await self._save_execution_to_db(execution, db)

        # 返回执行结果
        node_state = execution.node_states.get(next_node_id)
        return {
            "node_id": next_node_id,
            "node_type": node.node_type.value,
            "label": node.label,
            "status": node_state.status.value if node_state else "unknown",
            "output": node_state.output_data if node_state else {},
            "error": node_state.error if node_state else None,
        }

    def _get_next_pending_node(
        self,
        execution: WorkflowExecution,
        workflow: WorkflowDefinition,
    ) -> Optional[str]:
        """获取下一个待执行的节点"""
        # 拓扑排序
        order = self._topological_sort(workflow.nodes, workflow.edges)

        for node_id in order:
            node_state = execution.node_states.get(node_id)
            if node_state and node_state.status == NodeStatus.PENDING:
                # 检查前置节点是否完成
                if self._check_dependencies_completed(node_id, execution, workflow):
                    return node_id

        return None

    def _check_dependencies_completed(
        self,
        node_id: str,
        execution: WorkflowExecution,
        workflow: WorkflowDefinition,
    ) -> bool:
        """检查节点的依赖是否已完成"""
        for edge in workflow.edges:
            if edge.target == node_id:
                source_state = execution.node_states.get(edge.source)
                if not source_state or source_state.status != NodeStatus.COMPLETED:
                    return False
        return True

    async def get_execution_state(self, execution_id: str, db=None) -> Optional[WorkflowExecution]:
        """获取执行状态"""
        execution = await self._get_or_load_execution(execution_id, db)
        if execution:
            await self._mark_running_execution_stale_if_orphaned(execution, db, operation="inspect")
        return execution

    async def get_execution_operation_summary(self, execution_id: str, db=None) -> Optional[Dict[str, Any]]:
        execution = await self.get_execution_state(execution_id, db)
        if not execution:
            return None
        return self.build_execution_operation_summary(execution)

    # ==================== WebSocket 广播 ====================

    async def _broadcast_status(self, execution_id: str, event_type: str, data: Dict[str, Any]):
        """广播状态更新"""
        # 序列化数据，处理 UUID 和其他非 JSON 类型
        serialized_data = self._serialize_for_json(data)
        event_payload = {
            "type": event_type,
            "execution_id": execution_id,
            "data": serialized_data,
        }

        sequence_no = 0
        try:
            from app.api.app import postgres_db
            if postgres_db:
                sequence_no = await postgres_db.append_workflow_execution_event(
                    execution_id,
                    event_type,
                    serialized_data,
                )
                if sequence_no:
                    event_payload["sequence_no"] = sequence_no
        except Exception as e:
            logger.debug(f"追加 workflow 事件日志失败: {execution_id}, {event_type}, error={e}")

        if self._broadcast_callback:
            try:
                await self._broadcast_callback(execution_id, event_type, serialized_data)
            except Exception as e:
                # 连接断开是正常情况，使用 debug 级别避免日志污染
                if "close message has been sent" in str(e) or "DISCONNECTED" in str(e):
                    logger.debug(f"WebSocket 已断开，跳过广播: {event_type}")
                else:
                    logger.warning(f"广播状态失败: {e}")

        subscribers = list(self._event_subscribers.get(execution_id, set()))
        stale_queues: List[asyncio.Queue] = []
        for queue in subscribers:
            try:
                queue.put_nowait(event_payload)
            except asyncio.QueueFull:
                logger.debug(f"执行事件订阅队列已满，丢弃最旧事件: {execution_id}")
                try:
                    queue.get_nowait()
                except asyncio.QueueEmpty:
                    pass

                try:
                    queue.put_nowait(event_payload)
                except asyncio.QueueFull:
                    stale_queues.append(queue)
            except Exception as e:
                logger.debug(f"推送执行事件失败，移除订阅者: {execution_id}, error={e}")
                stale_queues.append(queue)

        for queue in stale_queues:
            self.unsubscribe_execution_events(execution_id, queue)

    def _serialize_for_json(self, obj: Any) -> Any:
        """递归序列化对象，处理 UUID 等非 JSON 类型"""
        import uuid
        from datetime import date, datetime
        from decimal import Decimal
        from enum import Enum
        from types import MappingProxyType

        if isinstance(obj, uuid.UUID) or obj.__class__.__name__ == 'UUID':
            return str(obj)
        elif isinstance(obj, datetime):
            return obj.isoformat()
        elif isinstance(obj, date):
            return obj.isoformat()
        elif isinstance(obj, Decimal):
            return float(obj)
        elif isinstance(obj, Enum):
            return obj.value
        elif isinstance(obj, MappingProxyType):
            # 处理 mappingproxy 类型
            return dict(obj)
        elif callable(obj):
            return getattr(obj, '__name__', str(obj))
        elif isinstance(obj, dict):
            return {k: self._serialize_for_json(v) for k, v in obj.items()}
        elif isinstance(obj, (list, tuple)):
            return [self._serialize_for_json(item) for item in obj]
        elif hasattr(obj, 'model_dump'):
            # 处理 Pydantic 模型
            return self._serialize_for_json(obj.model_dump(mode="json"))
        elif hasattr(obj, '__dict__'):
            # 处理其他对象
            return self._serialize_for_json(obj.__dict__)
        else:
            return obj

    def _make_json_safe(self, obj: Any) -> Any:
        """使对象 JSON 安全（别名方法）"""
        return self._serialize_for_json(obj)

    # ==================== 数据库操作 ====================

    async def _export_execution_replay_markdown(
        self,
        execution: WorkflowExecution,
        workflow: Optional[WorkflowDefinition] = None,
        db=None,
    ) -> Optional[str]:
        """导出 execution 的 Markdown 复盘文件。"""
        try:
            workflow_definition = workflow or await self.get_workflow(execution.workflow_id, db)
            if not workflow_definition:
                logger.warning(f"导出 workflow replay 失败，工作流定义不存在: {execution.workflow_id}")
                return None

            export_service = get_workflow_replay_export_service()
            file_path = export_service.save_markdown(execution, workflow_definition)
            execution.context["replay_markdown_path"] = file_path
            trace_service = get_trace_service(db)
            await trace_service.record_event("workflow_replay_exported", {"file_path": file_path})
            await trace_service.record_artifact(
                "replay",
                content={"file_path": file_path, "filename": file_path.split("/")[-1] if file_path else None},
            )
            logger.info(f"已导出 workflow replay markdown: {file_path}")
            return file_path
        except Exception as e:
            logger.warning(f"导出 workflow replay markdown 失败: {e}")
            return None

    async def _save_workflow_to_db(self, workflow: WorkflowDefinition, db):
        """保存工作流到数据库"""
        import json
        query = """
        INSERT INTO workflow_definitions (id, project_id, name, description, nodes, edges, variables, is_template, created_at, updated_at)
        VALUES (:id, :project_id, :name, :description, :nodes, :edges, :variables, :is_template, :created_at, :updated_at)
        ON CONFLICT (id) DO UPDATE SET
            name = EXCLUDED.name,
            description = EXCLUDED.description,
            nodes = EXCLUDED.nodes,
            edges = EXCLUDED.edges,
            variables = EXCLUDED.variables,
            is_template = EXCLUDED.is_template,
            updated_at = EXCLUDED.updated_at
        """
        params = {
            "id": workflow.id,
            "project_id": workflow.project_id,
            "name": workflow.name,
            "description": workflow.description,
            "nodes": json.dumps([n.model_dump() for n in workflow.nodes]),
            "edges": json.dumps([e.model_dump() for e in workflow.edges]),
            "variables": json.dumps(workflow.variables),
            "is_template": workflow.is_template,
            "created_at": workflow.created_at,
            "updated_at": workflow.updated_at,
        }
        await db.execute_write(query, params)

    async def _load_workflow_from_db(self, workflow_id: str, db) -> Optional[WorkflowDefinition]:
        """从数据库加载工作流"""
        query = "SELECT * FROM workflow_definitions WHERE id = :id"
        results = await db.execute_query(query, {"id": workflow_id})
        if not results:
            return None

        row = results[0]
        import json

        # Handle JSONB fields - they may be already parsed as list/dict
        nodes_data = row["nodes"]
        if isinstance(nodes_data, str):
            nodes_data = json.loads(nodes_data)
        edges_data = row["edges"]
        if isinstance(edges_data, str):
            edges_data = json.loads(edges_data)
        variables_data = row["variables"] or {}
        if isinstance(variables_data, str):
            variables_data = json.loads(variables_data)

        fixed_nodes = normalize_workflow_nodes([n.copy() for n in nodes_data])

        return WorkflowDefinition(
            id=row["id"],
            project_id=str(row["project_id"]) if row["project_id"] is not None else None,
            name=row["name"],
            description=row["description"],
            nodes=[WorkflowNode(**n) for n in fixed_nodes],
            edges=[WorkflowEdge(**e) for e in edges_data],
            variables=variables_data,
            is_template=row["is_template"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    async def _delete_workflow_from_db(self, workflow_id: str, db):
        """从数据库删除工作流"""
        query = "DELETE FROM workflow_definitions WHERE id = :id"
        await db.execute_write(query, {"id": workflow_id})

    async def _list_workflows_from_db(
        self,
        project_id: str,
        include_templates: bool,
        db,
    ) -> List[WorkflowDefinition]:
        """从数据库获取工作流列表"""
        if include_templates:
            query = """
            SELECT * FROM workflow_definitions
            WHERE project_id = :project_id OR is_template = true
            ORDER BY created_at DESC
            """
        else:
            query = """
            SELECT * FROM workflow_definitions
            WHERE project_id = :project_id
            ORDER BY created_at DESC
            """

        results = await db.execute_query(query, {"project_id": project_id})
        workflows = []

        import json
        for row in results:
            # Handle JSONB fields - they may be already parsed as list/dict
            nodes_data = row["nodes"]
            if isinstance(nodes_data, str):
                nodes_data = json.loads(nodes_data)
            edges_data = row["edges"]
            if isinstance(edges_data, str):
                edges_data = json.loads(edges_data)
            variables_data = row["variables"] or {}
            if isinstance(variables_data, str):
                variables_data = json.loads(variables_data)

            normalized_nodes = normalize_workflow_nodes([n.copy() for n in nodes_data])

            workflows.append(WorkflowDefinition(
                id=row["id"],
                project_id=str(row["project_id"]) if row["project_id"] is not None else None,
                name=row["name"],
                description=row["description"],
                nodes=[WorkflowNode(**n) for n in normalized_nodes],
                edges=[WorkflowEdge(**e) for e in edges_data],
                variables=variables_data,
                is_template=row["is_template"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            ))

        return workflows

    async def _save_execution_to_db(self, execution: WorkflowExecution, db):
        """保存执行记录到数据库"""
        data = {
            "id": execution.id,
            "workflow_id": execution.workflow_id,
            "project_id": execution.project_id,
            "operation_id": execution.operation_id,
            "request_id": execution.request_id,
            "request_hash": execution.request_hash,
            "director_session_id": execution.director_session_id,
            "trace_id": execution.trace_id,
            "status": execution.status.value,
            "current_node": execution.current_node,
            "node_states": self._make_json_safe({k: v.model_dump(mode='json') for k, v in execution.node_states.items()}),
            "context": self._make_json_safe(execution.context),
            "intervention_ids": self._make_json_safe(execution.intervention_ids),
            "lease_token": execution.lease_token,
            "lease_expires_at": execution.lease_expires_at,
            "last_heartbeat_at": execution.last_heartbeat_at,
            "cancel_requested": execution.cancel_requested,
            "resume_cursor": self._make_json_safe(execution.resume_cursor),
            "started_at": execution.started_at,
            "completed_at": execution.completed_at,
            "total_duration_ms": execution.total_duration_ms,
            "error": execution.error,
        }
        await db.save_workflow_execution(data)

    async def _load_execution_from_db(self, execution_id: str, db) -> Optional[WorkflowExecution]:
        """从数据库加载执行记录"""
        query = "SELECT * FROM workflow_executions WHERE id = :id"
        results = await db.execute_query(query, {"id": execution_id})
        if not results:
            return None

        row = results[0]
        import json
        node_states_data = row["node_states"]
        if isinstance(node_states_data, str):
            node_states_data = json.loads(node_states_data)
        node_states = {}
        for k, v in (node_states_data or {}).items():
            node_states[k] = NodeExecutionState(**v)

        context_data = row["context"]
        if isinstance(context_data, str):
            context_data = json.loads(context_data)

        intervention_ids_data = row["intervention_ids"]
        if isinstance(intervention_ids_data, str):
            intervention_ids_data = json.loads(intervention_ids_data)

        return WorkflowExecution(
            id=row["id"],
            workflow_id=row["workflow_id"],
            project_id=str(row["project_id"]),
            status=WorkflowStatus(row["status"]),
            current_node=row["current_node"],
            node_states=node_states,
            context=context_data or {},
            intervention_ids=intervention_ids_data or [],
            started_at=row["started_at"],
            completed_at=row["completed_at"],
            total_duration_ms=row["total_duration_ms"],
            error=row["error"],
            operation_id=str(row.get("operation_id")) if row.get("operation_id") else None,
            request_id=row.get("request_id"),
            request_hash=row.get("request_hash"),
            director_session_id=row.get("director_session_id"),
            trace_id=str(row.get("trace_id")) if row.get("trace_id") else None,
            lease_token=row.get("lease_token"),
            lease_expires_at=row.get("lease_expires_at"),
            last_heartbeat_at=row.get("last_heartbeat_at"),
            cancel_requested=bool(row.get("cancel_requested") or False),
            resume_cursor=row.get("resume_cursor") or {},
        )


# 全局单例
_workflow_engine: Optional[WorkflowEngine] = None


def get_workflow_engine() -> WorkflowEngine:
    """获取工作流引擎单例"""
    global _workflow_engine
    if _workflow_engine is None:
        _workflow_engine = WorkflowEngine()
    return _workflow_engine


def set_workflow_engine(engine: WorkflowEngine):
    """设置工作流引擎实例"""
    global _workflow_engine
    _workflow_engine = engine
