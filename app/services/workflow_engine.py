"""
工作流执行引擎
v8 Agent协作可视化工作台
"""

import asyncio
import logging
import random
from collections import defaultdict, deque
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Set

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

logger = logging.getLogger(__name__)


class WorkflowEngine:
    """工作流执行引擎"""

    def __init__(self):
        # 执行中的工作流实例
        self._executions: Dict[str, WorkflowExecution] = {}
        # 工作流定义缓存
        self._workflows: Dict[str, WorkflowDefinition] = {}
        # WebSocket 广播回调
        self._broadcast_callback: Optional[Callable] = None
        # Agent 实例获取回调
        self._agent_provider: Optional[Callable] = None
        # 干预队列：execution_id -> List[干预消息]
        self._intervention_queues: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        # 干预锁：确保线程安全
        self._intervention_locks: Dict[str, asyncio.Lock] = {}

    def set_broadcast_callback(self, callback: Callable):
        """设置 WebSocket 广播回调"""
        self._broadcast_callback = callback

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
            nodes=definition.nodes,
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

        if update.name is not None:
            workflow.name = update.name
        if update.description is not None:
            workflow.description = update.description
        if update.nodes is not None:
            # ========== 自动修正节点类型 ==========
            # 根据 ID 和 label 修正开始/结束节点的类型
            fixed_nodes = []
            for node in update.nodes:
                node_dict = node.model_dump()
                original_type = node.node_type

                # 检查是否应该是开始节点
                if (node.id == "start" or node.label in ["开始", "Start", "start"]):
                    if node_dict.get("node_type") != NodeType.START.value:
                        logger.info(f"修正节点类型: {node.id} 从 {node_dict.get('node_type')} 改为 start")
                        node_dict["node_type"] = NodeType.START.value
                        node_dict.pop("agent_type", None)  # 开始节点不需要 agent_type

                # 检查是否应该是结束节点
                elif (node.id == "end" or node.label in ["结束", "End", "end"]):
                    if node_dict.get("node_type") != NodeType.END.value:
                        logger.info(f"修正节点类型: {node.id} 从 {node_dict.get('node_type')} 改为 end")
                        node_dict["node_type"] = NodeType.END.value
                        node_dict.pop("agent_type", None)  # 结束节点不需要 agent_type

                fixed_nodes.append(WorkflowNode(**node_dict))

            workflow.nodes = fixed_nodes

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

        # 先修复节点类型（兼容旧数据）
        fixed_nodes = []
        for node in workflow.nodes:
            node_dict = node.model_dump()
            node_type = node.node_type
            node_id = node.id
            label = node.label

            # 根据 ID 或 label 推断正确的类型
            if node_type == NodeType.AGENT:
                if node_id == "start" or label in ["开始", "Start", "start"]:
                    node_dict["node_type"] = NodeType.START
                    node_dict.pop("agent_type", None)
                elif node_id == "end" or label in ["结束", "End", "end"]:
                    node_dict["node_type"] = NodeType.END
                    node_dict.pop("agent_type", None)

            fixed_nodes.append(WorkflowNode(**node_dict))

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

            # 跳过正在执行或已完成的节点（检查状态）
            node_state = execution.node_states.get(node.id)
            if node_state and node_state.status in [NodeStatus.RUNNING, NodeStatus.COMPLETED]:
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
        node_predecessors = predecessors.get(node.id, [])

        # 收集所有前驱节点的输出
        for pred_id in node_predecessors:
            pred_state = execution.node_states.get(pred_id)
            if pred_state and pred_state.output_data:
                # 合并前驱节点的输出
                merged_context.update(pred_state.output_data)
                logger.info(f"合并前驱节点 {pred_id} 的输出到节点 {node.id}: {list(pred_state.output_data.keys())}")

        return merged_context

    # ==================== 工作流执行 ====================

    async def execute_workflow(
        self,
        workflow_id: str,
        project_id: str,
        initial_context: Dict[str, Any] = None,
        db=None,
    ) -> str:
        """执行工作流

        Args:
            workflow_id: 工作流ID
            project_id: 项目ID
            initial_context: 初始上下文，可选包含 target_chapters 参数
            db: 数据库连接
        """
        workflow = await self.get_workflow(workflow_id, db)
        if not workflow:
            raise ValueError(f"工作流不存在: {workflow_id}")

        # 验证工作流
        validation = self.validate_workflow(workflow)
        if not validation.valid:
            raise ValueError(f"工作流验证失败: {validation.errors}")

        # 初始化上下文
        context = initial_context or {}

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
            try:
                from app.services.plot_outline_service import get_plot_outline_service
                plot_service = get_plot_outline_service()
                outline = await plot_service.get_chapter_outline_for_workflow(
                    project_id=project_id,
                    chapter_number=context.get("chapter_num")
                )
                if outline:
                    context["chapter_outline"] = outline
                    context["chapter_title"] = outline.get("title", f"第{context.get('chapter_num')}章")
                    context["chapter_summary"] = outline.get("summary", "")
                    logger.info(f"自动加载第 {context.get('chapter_num')} 章大纲: {outline.get('title')}")
                else:
                    logger.warning(f"未找到第 {context.get('chapter_num')} 章大纲，将由大纲Agent生成")
            except Exception as e:
                logger.warning(f"加载章节大纲失败: {e}")

        # 创建执行实例
        execution = WorkflowExecution(
            workflow_id=workflow_id,
            project_id=project_id,
            status=WorkflowStatus.RUNNING,
            context=context,
        )

        # 初始化节点状态
        for node in workflow.nodes:
            execution.node_states[node.id] = NodeExecutionState(node_id=node.id)

        # 保存到数据库
        if db:
            await self._save_execution_to_db(execution, db)

        self._executions[execution.id] = execution

        # 广播开始事件
        await self._broadcast_status(execution.id, "workflow_started", {
            "workflow_id": workflow_id,
            "execution_id": execution.id,
            "chapter_number": context.get("chapter_num"),
        })

        # 异步执行工作流
        asyncio.create_task(self._run_workflow(execution.id, workflow, db))

        logger.info(f"启动工作流执行: {execution.id}, 章节: {context.get('chapter_num')}")
        return execution.id

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

            # 已完成的节点集合（从执行状态恢复）
            completed_nodes: Set[str] = set()
            for node_id, node_state in execution.node_states.items():
                if node_state.status == NodeStatus.COMPLETED:
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
                                # 普通 goto：只重置目标节点状态
                                completed_nodes.discard(goto_target)
                                target_state = execution.node_states.get(goto_target)
                                if target_state:
                                    target_state.status = NodeStatus.PENDING
                                    target_state.started_at = None
                                    target_state.completed_at = None
                                    target_state.output_data = {}

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
                                            # 普通 goto：只重置目标节点状态
                                            completed_nodes.discard(next_node_id)
                                            target_state = execution.node_states.get(next_node_id)
                                            if target_state:
                                                target_state.status = NodeStatus.PENDING
                                                target_state.started_at = None
                                                target_state.completed_at = None
                                                target_state.output_data = {}

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

                logger.info(f"已完成节点: {completed_nodes}, 下批就绪: {ready_nodes}")

            # ========== 完成 ==========
            if execution.status == WorkflowStatus.RUNNING:
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
                await self._save_execution_to_db(execution, db)

            # 广播完成事件
            await self._broadcast_status(execution_id, "workflow_completed", {
                "status": execution.status.value,
                "error": execution.error,
            })

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
                # 从项目获取 world_id
                project = await db.get_project(project_id) if hasattr(db, 'get_project') else None
                if project and project.get("world_id"):
                    world = await db.get_world(project["world_id"]) if hasattr(db, 'get_world') else None
                    if world:
                        return {
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
                return None

            elif data_type == "hooks" or data_type == "existing_hooks":
                hooks = await db.get_hooks(project_id) if hasattr(db, 'get_hooks') else []
                return hooks

            elif data_type == "chapters" or data_type == "previous_chapters":
                chapters = await db.get_chapters_by_project(project_id) if hasattr(db, 'get_chapters_by_project') else []
                return chapters

            elif data_type == "project":
                project = await db.get_project(project_id) if hasattr(db, 'get_project') else None
                return project

            elif data_type == "events":
                events = await db.get_events(project_id) if hasattr(db, 'get_events') else []
                return events

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
    ):
        """
        保存输出到数据库

        Args:
            table: 数据库表名
            data: 要保存的数据
            project_id: 项目 ID
            db: 数据库连接
        """
        try:
            if table == "chapters":
                # 保存章节
                if isinstance(data, dict) and data.get("content"):
                    await db.save_chapter(
                        project_id=project_id,
                        chapter_num=data.get("chapter_num", 1),
                        title=data.get("title", ""),
                        content=data.get("content", ""),
                        summary=data.get("summary", ""),
                    )
                    logger.info(f"保存章节到数据库: 第 {data.get('chapter_num', 1)} 章")

            elif table == "hooks":
                # 保存伏笔
                if isinstance(data, list):
                    for hook in data:
                        await db.save_hook(project_id=project_id, hook=hook)
                    logger.info(f"保存 {len(data)} 个伏笔到数据库")

            elif table == "events":
                # 保存事件
                if isinstance(data, list):
                    for event in data:
                        await db.save_event(project_id=project_id, event=event)
                    logger.info(f"保存 {len(data)} 个事件到数据库")

        except Exception as e:
            logger.error(f"保存输出到数据库表 '{table}' 失败: {e}")

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

        # 广播节点开始
        broadcast_data = {
            "node_id": node.id,
            "node_type": actual_node_type.value,
            "label": node.label,
        }
        # 如果是 Agent 节点，添加 agent_type
        if actual_node_type == NodeType.AGENT and node.agent_type:
            broadcast_data["agent_type"] = node.agent_type
        await self._broadcast_status(execution.id, "node_started", broadcast_data)

        try:
            output = {}

            # ========== 根据节点 inputs 配置准备输入数据 ==========
            # 如果节点有 inputs 配置，使用新逻辑；否则保持原有行为（向后兼容）
            if node.inputs:
                prepared_context = await self._prepare_node_inputs(node, execution, db)
                # 更新执行上下文（临时合并）
                execution.context.update(prepared_context)
                logger.info(f"节点 '{node.label}' 根据 inputs 配置准备了 {len(node.inputs)} 个输入")

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
                output = await self._execute_agent_node(node, execution, execution.project_id, db)

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
                # 输入节点：暂停等待用户输入
                execution.status = WorkflowStatus.PAUSED
                output = {"status": "waiting_for_input"}

            # 更新状态
            node_state.status = NodeStatus.COMPLETED
            node_state.output_data = output
            node_state.completed_at = datetime.now()

            if node_state.started_at and node_state.completed_at:
                delta = node_state.completed_at - node_state.started_at
                node_state.duration_ms = int(delta.total_seconds() * 1000)

            # ========== 根据节点 outputs 配置处理输出 ==========
            if node.outputs:
                # 使用配置处理输出
                processed_output = await self._process_node_outputs(node, output, execution, db)
                execution.context.update(processed_output)
                logger.info(f"节点 '{node.label}' 根据 outputs 配置处理了 {len(node.outputs)} 个输出")
            else:
                # 向后兼容：所有输出保存到上下文
                execution.context.update(output)

        except Exception as e:
            logger.error(f"节点执行失败: {node.id} - {e}")
            node_state.status = NodeStatus.FAILED
            node_state.error = str(e)
            node_state.completed_at = datetime.now()

        # 广播节点完成
        completed_data = {
            "node_id": node.id,
            "node_type": node.node_type.value,
            "label": node.label,
            "status": node_state.status.value,
            "output": node_state.output_data,
            "error": node_state.error,
        }
        # 如果是 Agent 节点，添加 agent_type
        if node.node_type == NodeType.AGENT and node.agent_type:
            completed_data["agent_type"] = node.agent_type
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
                # 提取最近的章节作为参考
                recent_chapters = chapters[-5:] if len(chapters) > 5 else chapters
                output["previous_chapters"] = recent_chapters
                output["all_chapters"] = chapters
                execution.context["previous_chapters"] = recent_chapters
                execution.context["all_chapters"] = chapters

                # 提取章节概要
                chapter_summaries = [
                    {"chapter_num": i+1, "title": c.get("title", ""), "summary": c.get("summary", "")}
                    for i, c in enumerate(chapters)
                ]
                output["chapter_summaries"] = chapter_summaries
                execution.context["chapter_summaries"] = chapter_summaries

                # 最近章节的风格参考
                if recent_chapters:
                    last_chapter = recent_chapters[-1]
                    output["previous_style"] = last_chapter.get("content", "")[:1000]
                    execution.context["previous_style"] = output["previous_style"]

                logger.info(f"加载 {len(chapters)} 个章节（最近 {len(recent_chapters)} 章）")

            # ========== 5. 加载设定条目 ==========
            try:
                lores = await db.execute_query(
                    "SELECT * FROM lore_entries WHERE project_id = CAST(:project_id AS UUID) ORDER BY priority, created_at DESC LIMIT 30",
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
                logger.info(f"检测到用户反馈（重试 {output.get('retry_count', 0)} 次）: {user_feedback[:100]}...")

            # 记录加载完成
            loaded_items = [k for k in output.keys() if k != "status"]
            logger.info(f"开始节点完成，加载了 {len(loaded_items)} 项基础上下文: {loaded_items}")

        except Exception as e:
            logger.error(f"开始节点加载基础上下文失败: {e}")
            import traceback
            logger.error(traceback.format_exc())

        return output

    async def _execute_agent_node(
        self,
        node: WorkflowNode,
        execution: "WorkflowExecution",
        project_id: str,
        db=None,
    ) -> Dict[str, Any]:
        """执行 Agent 节点（支持流式输出和实时干预）"""
        if not self._agent_provider:
            raise ValueError("Agent provider 未设置")

        logger.info(f"请求 Agent: type={node.agent_type}, label={node.label}, node_id={node.id}, project_id={project_id}")

        # 获取 Agent 实例
        agent = await self._agent_provider(node.agent_type, project_id)
        if not agent:
            logger.error(f"无法获取 Agent: {node.agent_type}，可用类型请检查 agent_provider 配置")
            raise ValueError(f"无法获取 Agent: {node.agent_type}")

        logger.info(f"Agent 实例获取成功: type={node.agent_type}, instance_id={id(agent)}")

        # ========== 从数据库加载相关数据 ==========
        # 如果节点有 inputs 配置，使用 execution.context（已被 _prepare_node_inputs 准备好）
        # 否则使用旧的 _load_agent_context（向后兼容）
        if node.inputs:
            # 使用已准备好的上下文
            context = execution.context.copy()
            logger.info(f"Agent '{node.agent_type}' 使用节点 inputs 配置的上下文，包含 {len(context)} 个字段")
        else:
            # 向后兼容：使用旧的硬编码逻辑
            context = await self._load_agent_context(node.agent_type, execution, db)

        # ========== 检查并注入干预消息 ==========
        pending_interventions = await self.get_pending_interventions(
            execution.id,
            agent_type=node.agent_type,
        )

        if pending_interventions:
            logger.info(f"Agent {node.agent_type} 收到 {len(pending_interventions)} 条干预消息")

            # 合并所有干预消息
            intervention_messages = []
            for iv in pending_interventions:
                intervention_messages.append(f"[用户干预] {iv['message']}")
                await self.mark_intervention_processed(execution.id, iv["id"])

            # 注入到上下文
            context["interventions"] = intervention_messages
            context["user_guidance"] = "\n".join(intervention_messages)

            # 广播干预已应用
            await self._broadcast_status(execution.id, "intervention_applied", {
                "agent": node.agent_type,
                "node_id": node.id,
                "intervention_count": len(pending_interventions),
                "messages": intervention_messages,
            })

        return await self._run_agent_execution(agent, context, execution, node, db)

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
                # 从项目获取 world_id
                project = await db.get_project(project_id) if hasattr(db, 'get_project') else None
                if project and project.get("world_id"):
                    world = await db.get_world(project["world_id"]) if hasattr(db, 'get_world') else None
                    if world:
                        world_info = {
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
                    hooks = await db.get_hooks(project_id) if hasattr(db, 'get_hooks') else []
                    if hooks:
                        context["existing_hooks"] = hooks
                        execution.context["existing_hooks"] = hooks
                        data_loaded = True
                        logger.info(f"加载 {len(hooks)} 个已有伏笔到上下文")

            # ===== Writer Agent：需要章节历史、伏笔、角色、讨论共识、剧情意图 =====
            if agent_type == "writer":
                # 已有章节
                if "previous_chapters" not in context:
                    chapters = await db.get_chapters_by_project(project_id) if hasattr(db, 'get_chapters_by_project') else []
                    if chapters:
                        # 获取最近几章的内容作为参考
                        recent_chapters = chapters[-3:] if len(chapters) > 3 else chapters
                        context["previous_chapters"] = recent_chapters
                        execution.context["previous_chapters"] = recent_chapters
                        # 提取最近章节作为风格参考
                        if recent_chapters:
                            last_chapter = recent_chapters[-1]
                            context["previous_style"] = last_chapter.get("content", "")[:1000]
                            execution.context["previous_style"] = context["previous_style"]
                        logger.info(f"加载 {len(chapters)} 个章节历史到上下文（writer）")

                # 已有伏笔（需要处理的伏笔）- 转换为 Writer 需要的格式
                if "hooks" not in context:
                    hooks = await db.get_hooks(project_id) if hasattr(db, 'get_hooks') else []
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
                chapter_outline = execution.context.get("chapter_outline", {})
                chapter_goals = execution.context.get("chapter_goals", [])
                plot_outline = execution.context.get("plot_outline", [])

                # 获取当前章节号
                chapter_num = context.get("chapter_num", 1)

                # 提取写作意图
                intents = []
                if chapter_outline:
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
                    # 从剧情大纲中提取最近的意图
                    for node in plot_outline[-3:]:
                        if node.get("event"):
                            intents.append(node["event"])

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
                    logger.info(f"为 Writer 加载写作指导: {writing_guide.get('description', '')[:50]}...")

                # 提取角色情绪状态（从多个来源合并）
                characters_data = context.get("characters", [])
                character_states = execution.context.get("character_states", {})
                character_moods = execution.context.get("character_moods", {})  # 从角色 Agent 获取的情绪

                for char in characters_data:
                    if isinstance(char, dict):
                        char_name = char.get("name", "")
                        if char_name and char_name not in character_moods:
                            # 从角色状态获取情绪
                            state = character_states.get(char_name, {})
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
                world_data = execution.context.get("world_data", {})
                if world_data:
                    current_location = world_data.get("current_location", {})
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
                last_summary = execution.context.get("last_discussion_summary", "")
                if last_summary and "last_discussion_summary" not in context:
                    context["last_discussion_summary"] = last_summary

                # ========== 关键：设置字数要求 ==========
                # 从 execution.context 获取 target_word_count，映射到 word_count
                target_word_count = execution.context.get("target_word_count", 2000)
                context["word_count"] = target_word_count
                logger.info(f"为 Writer 设置目标字数: {target_word_count}")

                # 记录 Writer Agent 获得的上下文摘要
                logger.info(f"Writer Agent 上下文: intents={len(intents)}, moods={len(character_moods)}, hooks={len(context.get('hooks', []))}")

            # ===== Summarizer Agent：需要章节历史、事件 =====
            if agent_type == "summarizer":
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

            # ===== Evaluator Agent：需要章节历史、设定 =====
            if agent_type == "evaluator":
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

                # 讨论历史：从执行上下文获取之前的讨论记录
                discussion_history = execution.context.get("discussion_history", [])
                if discussion_history:
                    # 提取最近的讨论摘要供编剧参考
                    recent_discussions = discussion_history[-3:] if len(discussion_history) > 3 else discussion_history
                    context["recent_discussions"] = recent_discussions
                    # 提取最后一次讨论的总结
                    if recent_discussions:
                        last_discussion = recent_discussions[-1]
                        last_summary = last_discussion.get("messages", [{}])[-1].get("content", "") if last_discussion.get("messages") else ""
                        context["last_discussion_summary"] = last_summary
                        logger.info(f"加载 {len(recent_discussions)} 条讨论记录到编剧上下文（plotter）")

            # ===== ProcGen/World Agent：需要已有区域 =====
            if agent_type in ["procgen", "world_map_manager", "event_generator"]:
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
                    plot_outline = execution.context.get("plot_outline", [])
                    world_info = context.get("world_info", {})

                    # 构建探索方向
                    if chapter_goal:
                        context["exploration_direction"] = chapter_goal
                    elif plot_outline:
                        # 从剧情大纲提取最近的探索方向
                        latest_plot = plot_outline[-1] if plot_outline else {}
                        context["exploration_direction"] = latest_plot.get("event", "扩展世界内容")
                    elif world_info:
                        context["exploration_direction"] = f"探索 {world_info.get('name', '未知世界')} 的新区域"
                    else:
                        context["exploration_direction"] = "随机探索"

                    logger.info(f"为 ProcGen Agent 设置探索方向: {context['exploration_direction'][:100]}")

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
                    logger.info(f"World Map Manager 上下文准备完成: exploration_direction={context.get('exploration_direction', 'N/A')[:100]}, generation_type={context.get('generation_type', 'N/A')}")
                elif agent_type == "event_generator":
                    context["exploration_direction"] = f"[事件生成任务] {context.get('exploration_direction', '生成世界事件')}"
                    logger.info(f"Event Generator 上下文准备完成: exploration_direction={context.get('exploration_direction', 'N/A')[:100]}, generation_type={context.get('generation_type', 'N/A')}")

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
    ) -> Dict[str, Any]:
        """执行Agent并处理结果"""
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

        # ========== 注入 Agent 记忆上下文（使用增强记忆服务）==========
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
            await self._broadcast_status(execution.id, "agent_output", {
                "agent": node.agent_type,
                "node_id": node.id,
                "label": node.label,
                "output": result.data,
            })

        # 如果是评估 Agent，保存完整评估结果
        if node.agent_type == "evaluator" and result.success:
            output_data = result.data or {}

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
                        chapter_content, target_word_count
                    )
                    word_count_check = {
                        "actual": actual_word_count,
                        "target": target_word_count,
                        "min_required": min_word_count,
                        "passed": word_count_passed,
                        "message": word_count_msg,
                    }
                    logger.info(f"字数验证: {word_count_msg}")
                except ImportError:
                    word_count_check = output_data.get("word_count_check", {})

            # 评估结果可以从 agent 的返回值中获取
            evaluation_passed = output_data.get("quality_passed") or output_data.get("approved") or output_data.get("pass", True)

            # 字数不达标直接判定为不合格
            if not word_count_check.get("passed", True):
                evaluation_passed = False
                logger.warning(f"字数不达标，强制判定为不合格: {word_count_check.get('message')}")

            execution.context["evaluation_passed"] = evaluation_passed
            execution.context["word_count_check"] = word_count_check

            # 保存完整的评估反馈（包括问题和建议）
            evaluation_feedback = {
                "passed": evaluation_passed,
                "score": output_data.get("score", 0),
                "issues": output_data.get("issues", output_data.get("problems", [])),
                "suggestions": output_data.get("suggestions", output_data.get("recommendations", [])),
                "summary": output_data.get("summary", output_data.get("comment", "")),
                "word_count_check": word_count_check,
                "coherence_check": output_data.get("coherence_check", {}),
            }

            # 如果字数不达标，添加到issues
            if not word_count_check.get("passed", True):
                evaluation_feedback["issues"].insert(0, word_count_check.get("message", "字数不达标"))

            execution.context["evaluation_feedback"] = evaluation_feedback

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
            if result.success and result.data:
                # 保存角色状态
                new_status = result.data.get("new_status")
                if new_status:
                    execution.context.setdefault("character_status_changes", []).append({
                        "character_id": node.agent_type,
                        "new_status": new_status,
                    })

                # 保存角色对话内容（供 Writer 参考）
                dialogue = result.data.get("dialogue", result.data.get("content", ""))
                if dialogue:
                    execution.context.setdefault("character_dialogues", []).append({
                        "character": node.agent_type,
                        "dialogue": dialogue,
                    })

                # 保存角色情绪状态
                emotion = result.data.get("emotion", result.data.get("mood", ""))
                character_name = result.data.get("character_name", node.agent_type.split(":")[-1] if ":" in node.agent_type else "角色")
                if emotion:
                    execution.context.setdefault("character_moods", {})[character_name] = emotion

                logger.info(f"角色 Agent {node.agent_type} 输出已保存")

        # 如果是 Writer Agent，保存章节到数据库
        if node.agent_type == "writer" and result.success and result.data:
            await self._save_chapter_from_writer(execution, result.data, db)

            # ========== 角色检测与晋升 ==========
            # 在章节内容生成后，检测可能的新角色
            chapter_content = result.data.get("content", "")
            if chapter_content and len(chapter_content) > 500:
                # 获取 Writer Agent 的 LLM 模型用于智能角色检测
                writer_model = getattr(agent, 'model', None) if agent else None
                await self._detect_and_promote_characters(
                    execution=execution,
                    content=chapter_content,
                    db=db,
                    llm_model=writer_model,
                )

        # 如果是伏笔管理 Agent，保存伏笔到数据库
        if node.agent_type == "hook_manager" and result.success and result.data:
            await self._save_hooks_from_manager(execution, result.data, db)

        # 如果是设定 Agent，保存设定到 lore_entries 表
        if node.agent_type == "setting" and result.success and result.data:
            await self._save_lore_from_setting(execution, result.data, db)

        # 如果是世界生成 Agent，保存区域到数据库
        if node.agent_type in ["procgen", "world_map_manager", "event_generator"] and result.success and result.data:
            await self._save_world_data_from_procgen(execution, result.data, db)

        # 如果是摘要 Agent，保存剧情摘要
        if node.agent_type == "summarizer" and result.success and result.data:
            await self._save_summary_from_summarizer(execution, result.data, db)

        # 如果是编剧 Agent，保存剧情规划
        if node.agent_type in ["master_plotter", "plotter"] and result.success and result.data:
            await self._save_plot_from_plotter(execution, result.data, db)

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
                            "output_keys": list(result.data.keys()) if result.data else [],
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

        return result.data if result.success else {"error": result.error}

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
        characters = context.get("characters", [])
        if characters:
            char_names = [c.get("name", "") for c in characters[:3] if c.get("name")]
            if char_names:
                query_parts.append(f"角色: {', '.join(char_names)}")

        # 提取章节目标
        chapter_goal = context.get("chapter_goal", context.get("goal"))
        if chapter_goal:
            query_parts.append(chapter_goal)

        # 提取大纲要点
        outline = context.get("chapter_outline", {})
        if isinstance(outline, dict):
            summary = outline.get("summary", outline.get("goal"))
            if summary:
                query_parts.append(summary[:100])

        # 提取用户干预
        user_guidance = context.get("user_guidance")
        if user_guidance:
            query_parts.append(user_guidance[:100])

        return " ".join(query_parts) if query_parts else f"{agent_type} 任务"

    async def _save_chapter_from_writer(
        self,
        execution: "WorkflowExecution",
        writer_output: Dict[str, Any],
        db=None,
    ):
        """
        保存 Writer Agent 输出的章节到数据库
        只保存正文内容和必要的元数据

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

        try:
            # 获取章节正文内容
            content = writer_output.get("content", "")
            if not content:
                logger.warning("Writer 输出没有内容，跳过保存")
                return

            # 获取上下文中的章节信息
            chapter_num = execution.context.get("chapter_num", 1)
            chapter_title = execution.context.get("chapter_title", f"第{chapter_num}章")

            # 计算字数
            word_count = writer_output.get("word_count", len(content))

            # 生成章节 ID
            chapter_id = execution.context.get("chapter_id") or str(uuid.uuid4())

            # 构建章节数据 - 只保存正文内容和基本信息
            chapter_data = {
                "id": chapter_id,
                "title": chapter_title,
                "project_id": execution.project_id,
                "summary": "",  # 摘要可以后续由 Summarizer Agent 生成
                "content": content,  # 只保存正文
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

            # 保存到数据库
            await db.save_chapter(chapter_data)

            # 更新执行上下文
            execution.context["chapter_id"] = chapter_id
            execution.context["chapter_content"] = content
            execution.context["chapter_saved"] = True

            logger.info(f"章节已保存到数据库: {chapter_id} - {chapter_title} ({word_count} 字)")

            # 广播章节保存事件
            await self._broadcast_status(execution.id, "chapter_saved", {
                "chapter_id": chapter_id,
                "title": chapter_title,
                "word_count": word_count,
            })

        except Exception as e:
            logger.error(f"保存章节失败: {e}")
            execution.context["chapter_save_error"] = str(e)

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

    async def _save_hooks_from_manager(
        self,
        execution: "WorkflowExecution",
        hook_output: Dict[str, Any],
        db=None,
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
            return

        import uuid
        from datetime import datetime

        try:
            hooks_to_plant = hook_output.get("hooks_to_plant", [])
            hooks_to_resolve = hook_output.get("hooks_to_resolve", [])
            hooks_status_updates = hook_output.get("hooks_status_updates", [])

            # 保存新伏笔
            planted_ids = []
            for hook_data in hooks_to_plant:
                hook_id = str(uuid.uuid4())
                hook_record = {
                    "id": hook_id,
                    "title": hook_data.get("title", "未命名伏笔"),
                    "description": hook_data.get("description", ""),
                    "hook_type": hook_data.get("hook_type", "foreshadow"),
                    "status": "planted",
                    "related_characters": hook_data.get("related_characters", []),
                    "related_locations": [],
                    "related_objects": hook_data.get("related_objects", []),
                    "plant_context": execution.context.get("chapter_title", ""),
                    "plant_chapter": execution.context.get("chapter_id"),
                    "resolution_hint": hook_data.get("resolution_hint", ""),
                    "resolution_context": None,
                    "resolution_chapter": None,
                    "priority": hook_data.get("priority", 5),
                    "created_at": datetime.now(),
                    "resolved_at": None,
                    "project_id": execution.project_id,
                }
                await db.save_hook(hook_record)
                planted_ids.append(hook_id)
                logger.info(f"保存新伏笔: {hook_record['title']}")

            # 更新伏笔状态（回收）
            for hook_data in hooks_to_resolve:
                hook_id = hook_data.get("id")
                if hook_id:
                    await db.update_hook_status(hook_id, "resolved")
                    logger.info(f"伏笔已回收: {hook_id}")

            # 更新伏笔状态
            for update_data in hooks_status_updates:
                hook_id = update_data.get("id")
                new_status = update_data.get("new_status")
                if hook_id and new_status:
                    await db.update_hook_status(hook_id, new_status)
                    logger.info(f"伏笔状态更新: {hook_id} -> {new_status}")

            # 更新执行上下文
            if planted_ids:
                execution.context.setdefault("hooks_planted_this_run", []).extend(planted_ids)

            # 广播伏笔保存事件
            await self._broadcast_status(execution.id, "hooks_saved", {
                "planted_count": len(planted_ids),
                "resolved_count": len(hooks_to_resolve),
                "updated_count": len(hooks_status_updates),
            })

        except Exception as e:
            logger.error(f"保存伏笔失败: {e}")
            execution.context["hook_save_error"] = str(e)

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
            return

        import uuid
        from datetime import datetime

        try:
            # 获取新创建的设定
            new_lores = setting_output.get("new_lores", [])
            updated_lores = setting_output.get("updated_lores", [])
            validated_lores = setting_output.get("validated_lores", [])

            # 保存新设定
            created_ids = []
            for lore_data in new_lores:
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
                    "summary": lore_data.get("summary", "")[:500] if lore_data.get("summary") else "",
                    "keywords": json.dumps(lore_data.get("keywords", [])),
                    "tags": json.dumps(lore_data.get("tags", [])),
                    "constraints": json.dumps(lore_data.get("constraints", [])),
                    "related_characters": json.dumps(lore_data.get("related_characters", [])),
                    "related_locations": json.dumps(lore_data.get("related_locations", [])),
                    "related_items": json.dumps(lore_data.get("related_items", [])),
                    "created_at": datetime.now(),
                    "updated_at": datetime.now(),
                }

                await db.execute_write("""
                    INSERT INTO lore_entries (
                        id, project_id, title, category, priority, content, summary,
                        keywords, tags, constraints, related_characters, related_locations, related_items,
                        created_at, updated_at
                    ) VALUES (
                        CAST(:id AS UUID), CAST(:project_id AS UUID), :title, :category, :priority, :content, :summary,
                        :keywords, :tags, :constraints, :related_characters, :related_locations, :related_items,
                        :created_at, :updated_at
                    )
                """, params)

                created_ids.append(lore_id)
                logger.info(f"保存新设定: {lore_data.get('title', '未命名')} (ID: {lore_id})")

            # 更新现有设定
            for lore_data in updated_lores:
                lore_id = lore_data.get("id")
                if not lore_id:
                    continue

                update_fields = []
                params = {"id": lore_id}

                for field in ["title", "content", "summary"]:
                    if field in lore_data:
                        update_fields.append(f"{field} = :{field}")
                        params[field] = lore_data[field]

                if update_fields:
                    update_fields.append("updated_at = NOW()")
                    params["id"] = lore_id
                    query = f"UPDATE lore_entries SET {', '.join(update_fields)} WHERE id = CAST(:id AS UUID)"
                    await db.execute_write(query, params)
                    logger.info(f"更新设定: {lore_id}")

            # 更新执行上下文
            if created_ids:
                execution.context.setdefault("lores_created_this_run", []).extend(created_ids)

            # 广播设定保存事件
            await self._broadcast_status(execution.id, "lores_saved", {
                "created_count": len(created_ids),
                "updated_count": len(updated_lores),
                "validated_count": len(validated_lores),
            })

            # 同时更新 execution.context 中的 lore_entries
            if created_ids or updated_lores:
                # 重新加载设定列表
                try:
                    results = await db.execute_query(
                        "SELECT * FROM lore_entries WHERE project_id = CAST(:project_id AS UUID) ORDER BY priority, created_at DESC LIMIT 30",
                        {"project_id": execution.project_id}
                    )
                    if results:
                        execution.context["lore_entries"] = results
                        logger.info(f"重新加载了 {len(results)} 条设定到上下文")
                except Exception as e:
                    logger.warning(f"重新加载设定列表失败: {e}")

        except Exception as e:
            logger.error(f"保存设定失败: {e}")
            execution.context["lore_save_error"] = str(e)

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
            return

        import uuid
        from datetime import datetime

        try:
            # 获取生成的区域
            regions = procgen_output.get("regions", [])
            events = procgen_output.get("events", [])
            locations = procgen_output.get("locations", [])

            # 保存区域
            saved_regions = []
            for region_data in regions:
                region_id = region_data.get("id") or str(uuid.uuid4())
                region_record = {
                    "id": region_id,
                    "name": region_data.get("name", "未命名区域"),
                    "description": region_data.get("description", ""),
                    "region_type": region_data.get("region_type", "custom"),
                    "terrain_type": region_data.get("terrain_type", "custom"),
                    "atmosphere": region_data.get("atmosphere", ""),
                    "terrain_features": region_data.get("terrain_features", []),
                    "landmarks": region_data.get("landmarks", []),
                    "encounters": region_data.get("encounters", []),
                    "local_rules": region_data.get("local_rules", []),
                    "is_generated": True,
                    "visit_count": 0,
                    "created_at": datetime.now(),
                }

                # 如果有 world_id，添加到记录中
                world_id = execution.context.get("world_id")
                if world_id:
                    region_record["world_id"] = world_id

                await db.save_region(region_record)
                saved_regions.append(region_id)
                logger.info(f"保存世界区域: {region_record['name']}")

            # 保存事件到上下文
            if events:
                execution.context.setdefault("generated_events", []).extend(events)

            # 保存地点到上下文
            if locations:
                execution.context.setdefault("generated_locations", []).extend(locations)

            # 更新执行上下文
            if saved_regions:
                execution.context.setdefault("saved_regions", []).extend(saved_regions)

            # 广播世界数据保存事件
            await self._broadcast_status(execution.id, "world_data_saved", {
                "regions_count": len(saved_regions),
                "events_count": len(events),
                "locations_count": len(locations),
            })

        except Exception as e:
            logger.error(f"保存世界数据失败: {e}")
            execution.context["world_data_save_error"] = str(e)

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
                logger.info(f"更新剧情摘要: {summary[:100]}...")

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
            # 更新执行上下文中的剧情规划
            plot_outline = plotter_output.get("plot_outline", [])
            chapter_outline = plotter_output.get("chapter_outline", {})
            upcoming_events = plotter_output.get("upcoming_events", [])
            character_arcs = plotter_output.get("character_arcs", {})
            chapter_titles = plotter_output.get("chapter_titles", [])
            chapter_goals = plotter_output.get("chapter_goals", [])
            main_conflicts = plotter_output.get("main_conflicts", [])

            if plot_outline:
                execution.context["plot_outline"] = plot_outline
                logger.info(f"更新剧情大纲: {len(plot_outline)} 个节点")

            if chapter_outline:
                execution.context["chapter_outline"] = chapter_outline
                logger.info(f"更新章节大纲: {len(chapter_outline)} 章")

            # 保存章节目标（这是 Writer Agent 的关键输入）
            if chapter_goals:
                execution.context["chapter_goals"] = chapter_goals
                logger.info(f"保存章节目标: {len(chapter_goals)} 章")

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
            if chapter_titles and len(chapter_titles) >= execution.context.get("chapter_num", 1):
                execution.context["chapter_title"] = chapter_titles[execution.context.get("chapter_num", 1) - 1]

            # 设置章节目标（用于写作）
            if chapter_goals and len(chapter_goals) >= execution.context.get("chapter_num", 1):
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
        # 条件评估在边的选择时处理
        # 这里返回上下文中的条件字段
        return {"condition_evaluated": True}

    async def _execute_scene_performance_node(
        self,
        node: WorkflowNode,
        execution: "WorkflowExecution",
        db=None,
    ) -> Dict[str, Any]:
        """
        执行场景演绎节点 - 多个角色Agent同台飙戏

        这是专门用于多角色演绎的节点类型，与 GROUP_DISCUSSION 节点区分。

        节点配置 (node.config):
        - scene_mode: "interactive"（同场景互动）或 "parallel"（并行独立）
        - required_characters: 需要参与的角色名列表
        - need_background_characters: 是否需要背景角色
        - background_character_count: 背景角色数量
        - background_character_type: 背景角色类型（路人/侍从/村民等）

        输入（通过 node.inputs 配置）:
        - scene_directions: 场景方向（编剧设定）
        - characters: 参与角色列表

        输出:
        - performance_result: 完整的表演结果
        - dialogues: 对话列表
        - full_content: 完整文本内容
        """
        logger.info(f"执行场景演绎节点: {node.label}")

        # 获取节点配置
        node_config = node.config or {}

        # 获取场景方向（从上下文或生成）
        scene_directions = execution.context.get("scene_directions", {})

        # 如果没有场景方向，让编剧生成
        if not scene_directions:
            plotter_agent = await self._get_agent_for_discussion("plotter", execution.project_id)
            if plotter_agent:
                scene_directions = await self._generate_scene_directions(
                    plotter_agent, execution.context
                )
                if scene_directions:
                    execution.context["scene_directions"] = scene_directions

        # 默认场景方向
        if not scene_directions:
            scene_directions = {
                "scene_type": node_config.get("scene_mode", "interactive"),
                "main_scene": node.label,
                "atmosphere": "正剧",
                "character_roles": {},
                "plot_focus": "推进剧情",
            }

        # 合并节点配置到场景方向
        if node_config.get("required_characters"):
            scene_directions["required_characters"] = node_config["required_characters"]
        if node_config.get("need_background_characters"):
            scene_directions["need_background_characters"] = True
            scene_directions["background_character_count"] = node_config.get("background_character_count", 2)
            scene_directions["background_character_type"] = node_config.get("background_character_type", "路人")

        # ========== 角色选择逻辑 ==========
        # 优先级：
        # 1. 编剧在 scene_directions 中指定的角色（selected_characters）
        # 2. 节点配置中的 required_characters
        # 3. CharacterSelector 智能选择（后备方案）

        # 获取所有可用角色
        all_characters = []
        if db:
            all_characters = await db.get_all_characters(execution.project_id) or []

        # 获取上一个节点的输出（供智能角色选择和后续协调使用）
        previous_node_output = {}
        if execution.node_states:
            completed_nodes = [
                (node_id, state) for node_id, state in execution.node_states.items()
                if state.status == "completed"
            ]
            if completed_nodes:
                last_node = max(completed_nodes, key=lambda x: x[1].completed_at or datetime.min)
                previous_node_output = last_node[1].output_data or {}

        characters_data = []

        # 优先级 1: 编剧在 scene_directions 中指定的角色
        selected_by_plotter = scene_directions.get("selected_characters", [])
        if selected_by_plotter and all_characters:
            logger.info(f"使用编剧指定的角色: {selected_by_plotter}")
            for char_name in selected_by_plotter:
                char_info = next((c for c in all_characters if c.get("name") == char_name), None)
                if char_info:
                    characters_data.append(char_info)

        # 优先级 2: 节点配置中的 required_characters
        if not characters_data:
            required_characters = node_config.get("required_characters", [])
            if required_characters and all_characters:
                logger.info(f"使用节点配置的角色: {required_characters}")
                for char_name in required_characters:
                    char_info = next((c for c in all_characters if c.get("name") == char_name), None)
                    if char_info:
                        characters_data.append(char_info)

        # 优先级 3: CharacterSelector 智能选择（后备方案）
        if not characters_data and all_characters:
            logger.info("编剧未指定角色，使用智能选择器")
            from app.services.character_selector import (
                get_character_selector,
                extract_scene_context,
            )

            # 获取上一场出现的角色
            previous_characters = []
            performance_history = execution.context.get("performance_history", [])
            if performance_history:
                previous_characters = performance_history[-1].get("characters", [])

            # 提取场景上下文
            scene_ctx = extract_scene_context(
                scene_directions=scene_directions,
                previous_output=previous_node_output,
                plot_focus=scene_directions.get("plot_focus", ""),
            )

            # 智能选择角色
            selector = get_character_selector()
            selected_chars = await selector.select_characters(
                all_characters=all_characters,
                scene_context=scene_ctx,
                previous_characters=previous_characters,
                director_guidance=scene_directions.get("character_guidance"),
                max_characters=node_config.get("max_characters", 5),
            )
            characters_data = selected_chars

            logger.info(f"智能选择角色: {[c.get('name') for c in characters_data]}")

        # 回退：从上下文获取
        if not characters_data:
            characters_data = execution.context.get("characters", [])

        # 添加背景角色
        if node_config.get("need_background_characters"):
            bg_count = node_config.get("background_character_count", 2)
            bg_type = node_config.get("background_character_type", "路人")
            for i in range(bg_count):
                characters_data.append({
                    "name": f"{bg_type}{i+1}",
                    "importance_tier": 5,
                    "character_type": "background",
                    "is_protagonist": False,
                    "is_antagonist": False,
                    "personality": "普通人",
                    "background": "普通路人",
                    "traits": [],
                    "speech_pattern": "自然随意",
                })

        logger.info(f"场景演绎参与角色: {len(characters_data)} 个")

        # 广播表演开始
        await self._broadcast_status(execution.id, "performance_started", {
            "node_id": node.id,
            "scene_type": scene_directions.get("scene_type", "interactive"),
            "main_scene": scene_directions.get("main_scene", node.label),
            "characters": [c.get("name", "未知") for c in characters_data],
            "performance_topic": f"《{scene_directions.get('main_scene', node.label)}》",
        })

        # 使用 SceneCoordinatorAgent 统筹多角色表演
        from app.agents.scene_coordinator import SceneCoordinatorAgent

        # 获取模型
        existing_agent = await self._get_agent_for_discussion("character", execution.project_id)
        model = existing_agent.model if existing_agent else None

        # 创建场景协调者
        scene_coordinator = SceneCoordinatorAgent(
            model=model,
            project_id=execution.project_id,
            db=db,  # 传递数据库连接以使用字数统计 skill
        )

        # 获取节点配置中的迭代参数
        iteration_count = node_config.get("iteration_count", 3)  # 默认3轮迭代
        plot_intents = execution.context.get("intents", [])  # 从上下文获取剧情意图

        # 目标字数：场景演绎目标字数 = 章节要求字数 × 2
        chapter_word_count = execution.context.get("target_word_count", 2000)
        target_word_count = chapter_word_count * 2  # 场景演绎内容需要更丰富

        # 如果节点有自定义配置，使用配置值（但不低于章节字数×2）
        node_target = node_config.get("target_word_count")
        if node_target and node_target > target_word_count:
            target_word_count = node_target

        # 执行场景协调（支持多轮迭代）
        coordinator_input = {
            "scene_directions": scene_directions,
            "characters": characters_data,
            "world_info": execution.context.get("world_info", {}),
            "previous_output": previous_node_output,
            "mode": scene_directions.get("scene_type", "interactive"),
            "iteration_count": iteration_count,
            "target_word_count": target_word_count,
            "plot_intents": plot_intents,
            "chapter_word_count": chapter_word_count,  # 传递章节字数供参考
        }

        logger.info(f"场景演绎参数: {iteration_count} 轮迭代, 目标 {target_word_count} 字 (章节 {chapter_word_count} 字 × 2), {len(characters_data)} 个角色")

        result = await scene_coordinator.execute(coordinator_input)

        if not result.success:
            logger.error(f"场景协调执行失败: {result.error}")
            return {"error": result.error, "status": "failed"}

        performance_result = result.data
        performance_messages = performance_result.get("performances", [])

        # 广播每条表演消息
        for msg in performance_messages:
            await self._broadcast_discussion_message(execution.id, msg)
            await asyncio.sleep(0.2)

        # 生成表演总结
        summarizer_agent = await self._get_agent_for_discussion("summarizer", execution.project_id)
        if summarizer_agent and performance_messages:
            summary = await self._generate_performance_summary(
                summarizer_agent, scene_directions, performance_messages
            )
            if summary:
                performance_messages.append(summary)
                await self._broadcast_discussion_message(execution.id, summary)

        # 存入上下文
        performance_result["status"] = "completed"
        execution.context["performance_result"] = performance_result
        execution.context["dialogues"] = performance_messages
        execution.context["last_performance_content"] = performance_result.get("full_content", "")

        # 添加到表演历史
        performance_history = execution.context.get("performance_history", [])
        performance_history.append(performance_result)
        execution.context["performance_history"] = performance_history

        # 记录统计信息
        actual_word_count = performance_result.get("actual_word_count", 0)
        actual_iterations = performance_result.get("iteration_count", iteration_count)

        logger.info(f"场景演绎完成: {len(performance_messages)} 条表演, {actual_iterations} 轮迭代, {actual_word_count} 字")

        return {
            "status": "completed",
            "scene": scene_directions.get("main_scene", node.label),
            "characters": [c.get("name") for c in characters_data],
            "messages": performance_messages,
            "full_content": performance_result.get("full_content", ""),
            "iteration_count": actual_iterations,
            "word_count": actual_word_count,
            "target_word_count": target_word_count,
        }

    # 等待用户确认的超时时间（秒）
    USER_CONFIRMATION_TIMEOUT = 60

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

        # 如果需要用户确认，暂停工作流
        if require_user_confirmation and result.get("status") == "completed":
            logger.info(f"集体讨论节点完成，暂停等待用户确认（超时 {confirmation_timeout} 秒）...")

            # 广播等待用户确认事件
            await self._broadcast_status(execution.id, "waiting_user_confirmation", {
                "node_id": node.id,
                "node_type": "group_discussion",
                "discussion_mode": discussion_mode,
                "discussion_result": result,
                "timeout_seconds": confirmation_timeout,
                "message": f"讨论已完成，请在 {confirmation_timeout} 秒内确认，否则自动接受",
            })

            # 设置等待确认状态
            execution.context["waiting_confirmation"] = {
                "node_id": node.id,
                "discussion_result": result,
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

            # 更新结果状态
            result["waiting_confirmation"] = True
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

            # 标记已确认，防止重复确认
            waiting_confirmation["confirmed"] = True
            waiting_confirmation["auto_confirmed"] = True

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
        执行角色演绎节点 - 多个角色Agent同台飙戏

        流程：
        1. 编剧Agent设定场景和表演方向（从上下文获取或生成）
        2. 获取参与表演的角色Agent列表
        3. 每个角色Agent根据人设和世界观进行表演
        4. 表演可以是同一场景的互动或各自独立的场景
        5. 汇总表演内容，形成剧情推进
        """
        logger.info("开始角色演绎模式...")

        try:
            # ========== 第一步：获取场景设定和表演方向 ==========
            # 从上下文获取编剧设定的场景方向
            scene_directions = execution.context.get("scene_directions", {})
            performance_config = execution.context.get("performance_config", {})

            # 如果没有预设场景方向，让编剧生成
            if not scene_directions:
                plotter_agent = await self._get_agent_for_discussion("plotter", execution.project_id)
                if plotter_agent:
                    scene_directions = await self._generate_scene_directions(
                        plotter_agent, execution.context
                    )
                    if scene_directions:
                        execution.context["scene_directions"] = scene_directions

            # 默认场景方向
            if not scene_directions:
                scene_directions = {
                    "scene_type": "interactive",  # "interactive" 同场景互动 或 "parallel" 各自独立
                    "main_scene": "未设定场景",
                    "atmosphere": "正剧",
                    "character_roles": {},
                    "plot_focus": "推进主线剧情",
                    "world_context": execution.context.get("world_info", {}).get("description", ""),
                }

            # ========== 第二步：角色选择 ==========
            # 优先级：
            # 1. 编剧在 scene_directions.selected_characters 中指定的角色
            # 2. 节点配置中的 characters 或 required_characters
            # 3. CharacterSelector 智能选择（后备方案）

            # 获取节点配置
            node_config = node.config or {}

            # 获取所有可用角色
            all_characters = []
            if db:
                all_characters = await db.get_all_characters(execution.project_id) or []

            # 获取上一个节点的输出
            previous_node_output = {}
            if execution.node_states:
                completed_nodes = [
                    (node_id, state) for node_id, state in execution.node_states.items()
                    if state.status == "completed"
                ]
                if completed_nodes:
                    last_node = max(completed_nodes, key=lambda x: x[1].completed_at or datetime.min)
                    previous_node_output = last_node[1].output_data or {}

            characters_data = []

            # 优先级 1: 编剧在 scene_directions.selected_characters 中指定的角色
            selected_by_plotter = scene_directions.get("selected_characters", [])
            if selected_by_plotter and all_characters:
                logger.info(f"使用编剧指定的角色: {selected_by_plotter}")
                for char_name in selected_by_plotter:
                    char_info = next((c for c in all_characters if c.get("name") == char_name), None)
                    if char_info:
                        characters_data.append(char_info)

            # 优先级 2: 节点配置中的角色
            if not characters_data:
                participant_characters = node_config.get("characters", [])
                if not participant_characters:
                    participant_characters = scene_directions.get("required_characters", [])
                if participant_characters and all_characters:
                    logger.info(f"使用节点配置的角色: {participant_characters}")
                    for char_name in participant_characters:
                        char_info = next((c for c in all_characters if c.get("name") == char_name), None)
                        if char_info:
                            characters_data.append(char_info)

            # 优先级 3: CharacterSelector 智能选择（后备方案）
            if not characters_data and all_characters:
                logger.info("编剧未指定角色，使用智能选择器")
                from app.services.character_selector import (
                    get_character_selector,
                    extract_scene_context,
                )

                # 获取上一场出现的角色
                previous_characters = []
                performance_history = execution.context.get("performance_history", [])
                if performance_history:
                    previous_characters = performance_history[-1].get("characters", [])

                # 提取场景上下文
                scene_ctx = extract_scene_context(
                    scene_directions=scene_directions,
                    previous_output=previous_node_output,
                    plot_focus=scene_directions.get("plot_focus", ""),
                )

                # 智能选择角色
                selector = get_character_selector()
                selected_chars = await selector.select_characters(
                    all_characters=all_characters,
                    scene_context=scene_ctx,
                    previous_characters=previous_characters,
                    director_guidance=scene_directions.get("character_guidance"),
                    max_characters=node_config.get("max_characters", 5),
                )
                characters_data = selected_chars

                logger.info(f"智能选择角色: {[c.get('name') for c in characters_data]}")

            # 回退：使用上下文中的角色
            if not characters_data:
                characters_data = execution.context.get("characters", [])

            # 如果场景需要背景角色/路人
            background_characters = []
            if scene_directions.get("need_background_characters"):
                background_count = scene_directions.get("background_character_count", 2)
                background_type = scene_directions.get("background_character_type", "路人")
                # 生成临时背景角色数据
                for i in range(background_count):
                    background_characters.append({
                        "name": f"{background_type}{i+1}",
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

            # 添加背景角色
            if background_characters:
                characters_data.extend(background_characters)

            logger.info(f"参与角色演绎: {len(characters_data)} 个角色 (其中 {len(background_characters)} 个背景角色)")

            # 广播表演开始
            await self._broadcast_status(execution.id, "performance_started", {
                "node_id": node.id,
                "scene_type": scene_directions.get("scene_type", "interactive"),
                "main_scene": scene_directions.get("main_scene", ""),
                "characters": [c.get("name", "未知") for c in characters_data],
                "performance_topic": f"《{scene_directions.get('main_scene', '角色演绎')}》",
            })

            # ========== 第三步：使用 SceneCoordinatorAgent 统筹多角色表演 ==========
            # 创建场景协调者 Agent（每个角色会有独立的 Agent 实例）
            from app.agents.scene_coordinator import SceneCoordinatorAgent
            from app.api.app import postgres_db

            # 获取一个已有的 Agent 来复用其 model
            existing_agent = await self._get_agent_for_discussion("character", execution.project_id)
            model = existing_agent.model if existing_agent else None

            # 创建场景协调者
            scene_coordinator = SceneCoordinatorAgent(
                model=model,
                project_id=execution.project_id,
            )

            # 设置流式回调
            if self._broadcast_discussion_message:
                async def stream_callback(content: str):
                    await self._broadcast_status(execution.id, "stream", {
                        "content": content,
                        "type": "character_dialogue",
                    })
                scene_coordinator._stream_callback = stream_callback

            # 执行场景协调
            coordinator_input = {
                "scene_directions": scene_directions,
                "characters": characters_data,
                "world_info": execution.context.get("world_info", {}),
                "previous_output": previous_node_output,
                "mode": scene_directions.get("scene_type", "interactive"),
            }

            result = await scene_coordinator.execute(coordinator_input)

            if not result.success:
                logger.error(f"场景协调执行失败: {result.error}")
                return {"error": result.error, "status": "failed"}

            performance_result = result.data
            performance_messages = performance_result.get("performances", [])

            # 广播每条表演消息
            for msg in performance_messages:
                await self._broadcast_discussion_message(execution.id, msg)
                await asyncio.sleep(0.2)

            # ========== 第四步：生成表演总结 ==========
            summarizer_agent = await self._get_agent_for_discussion("summarizer", execution.project_id)
            if summarizer_agent and performance_messages:
                summary = await self._generate_performance_summary(
                    summarizer_agent, scene_directions, performance_messages
                )
                if summary:
                    performance_messages.append(summary)
                    await self._broadcast_discussion_message(execution.id, summary)

            # ========== 第五步：存储结果 ==========
            performance_result = {
                "mode": "performance",
                "scene_type": scene_type,
                "scene_directions": scene_directions,
                "characters": [c.get("name", "未知") for c in characters_data],
                "messages": performance_messages,
                "timestamp": datetime.now().isoformat(),
                "status": "completed",
            }

            # 存入上下文
            execution.context["performance_result"] = performance_result
            execution.context["last_performance_content"] = "\n".join([
                m.get("content", "") for m in performance_messages if m.get("content")
            ])

            # 添加到表演历史
            performance_history = execution.context.get("performance_history", [])
            performance_history.append(performance_result)
            execution.context["performance_history"] = performance_history

            logger.info(f"角色演绎完成，共 {len(performance_messages)} 条表演")

            return {
                "status": "completed",
                "mode": "performance",
                "scene_type": scene_type,
                "characters": [c.get("name", "未知") for c in characters_data],
                "messages": performance_messages,
            }

        except Exception as e:
            logger.error(f"角色演绎节点执行失败: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return {"error": str(e), "status": "failed"}

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

            # 获取角色列表
            characters = execution.context.get("characters", [])
            if characters and isinstance(characters[0], dict):
                characters = [c.get("name", "未知角色") for c in characters]

            if not characters and db:
                try:
                    chars = await db.get_all_characters(execution.project_id)
                    characters = [c.get("name", "未知角色") for c in chars] if chars else []
                except Exception as e:
                    logger.warning(f"获取角色失败: {e}")

            # 提取讨论上下文
            chapter_title = execution.context.get("chapter_title", "当前章节")
            current_plot_summary = execution.context.get("current_plot_summary", "")
            written_content = execution.context.get("written_content", "")
            evaluation_result = execution.context.get("evaluation_result", {})
            plot_outline = execution.context.get("plot_outline", [])

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
                    written_content, plot_outline, evaluation_result, participants
                )
                if opening_message:
                    discussion_messages.append(opening_message)
                    await self._broadcast_discussion_message(execution.id, opening_message, is_leader_action=True)

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
                            await self._broadcast_discussion_message(execution.id, message, broadcast_to_all=True)

            # ========== 第三步：领头人汇总，请求用户确认 ==========
            if leader_agent and discussion_messages:
                summary_request = await self._generate_leader_summary_request(
                    leader_agent, chapter_title, discussion_messages
                )
                if summary_request:
                    discussion_messages.append(summary_request)
                    await self._broadcast_discussion_message(execution.id, summary_request, is_leader_action=True)

            # ========== 第四步：存储讨论结果 ==========
            discussion_result = {
                "topic": f"《{chapter_title}》创作讨论会",
                "leader": leader_name,
                "leader_type": LEADER_AGENT,  # 保存领头人类型，用于后续确认
                "participants": participants,
                "messages": discussion_messages,
                "characters": characters,
                "timestamp": datetime.now().isoformat(),
                "status": "waiting_confirmation",
            }

            execution.context["group_discussion"] = discussion_result
            execution.context["last_discussion_summary"] = discussion_messages[-1].get("content", "") if discussion_messages else ""

            discussion_history = execution.context.get("discussion_history", [])
            discussion_history.append(discussion_result)
            execution.context["discussion_history"] = discussion_history

            logger.info(f"集体讨论节点完成，共 {len(discussion_messages)} 条发言，等待用户确认")

            return {
                "status": "completed",
                "discussion_topic": f"《{chapter_title}》创作讨论会",
                "leader": leader_name,
                "participants": participants,
                "messages": discussion_messages,
                "characters": characters,
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

    async def _generate_plotter_opening(
        self,
        agent,
        chapter_title: str,
        plot_summary: str,
        written_content: str,
        plot_outline: List,
        evaluation_result: Dict,
    ) -> Optional[Dict[str, Any]]:
        """编剧 Agent 开场发言（要有实质内容，引导讨论方向）"""
        try:
            # 安全地格式化 issues（可能是 dict 列表或 str 列表）
            issues_raw = evaluation_result.get('issues', [])
            if issues_raw:
                issues_formatted = '\n'.join([
                    '- ' + (str(i) if isinstance(i, str) else i.get('issue', i.get('description', str(i))))
                    for i in issues_raw[:5]
                ])
                issues_section = f"\n问题点：\n{issues_formatted}"
            else:
                issues_section = ''

            # 构建开场提示
            prompt = f"""你是总编剧，现在召开《{chapter_title}》创作讨论会。

【重要】作为讨论主持者，你的开场发言必须：
- **有实质内容**：不要说空话套话，要有具体的分析和判断
- **引导讨论**：提出需要讨论的具体问题
- **明确方向**：让其他Agent知道该关注什么

【当前章节】{chapter_title}

【已写内容】
{written_content[:1500] if written_content else "暂无"}

【剧情规划进度】
{len(plot_outline)} 个情节点已规划
{f"当前进度：{plot_outline[-3:]}" if plot_outline else "暂无详细规划"}

【评估反馈】
评分: {evaluation_result.get('score', 'N/A')}/10
{'✅ 通过' if evaluation_result.get('quality_passed', True) else '⚠️ 需要改进'}{issues_section}

请输出你的开场发言，必须包含：

## 章节创作总结
[本章的核心创作意图、主要情节、想达到的效果]

## 创作完成度评估
[自我评价：哪些达到了预期，哪些还有差距]

## 需要讨论的问题
[列出具体需要各位Agent讨论的问题，比如：
- 角色表现是否到位？
- 节奏是否合适？
- 有没有世界观冲突？
- 伏笔埋设是否自然？
- 文字表达有什么问题？]

## 后续规划重点
[接下来要关注什么，剧情要往哪个方向发展]

## 对各位的期待
[希望各位Agent重点关注什么方面]

请以总编剧的身份发言，直接输出内容，不要有任何格式标记或解释。"""

            if hasattr(agent, 'model') and agent.model:
                from langchain_core.messages import HumanMessage
                response = await agent.model.ainvoke([HumanMessage(content=prompt)])
                content = response.content.strip()

                return {
                    "agent": "编剧",
                    "type": "plotter",
                    "content": content,
                    "is_llm_generated": True,
                }
        except Exception as e:
            logger.error(f"编剧开场生成失败: {e}")

        # 回退到静态消息
        return {
            "agent": "编剧",
            "type": "plotter",
            "content": f"【开场】{chapter_title}的创作已完成，请各位从各自专业角度进行分析讨论。",
            "is_llm_generated": False,
        }

    async def _generate_leader_opening(
        self,
        agent,
        chapter_title: str,
        plot_summary: str,
        written_content: str,
        plot_outline: List,
        evaluation_result: Dict,
        participants: List[Dict],
    ) -> Optional[Dict[str, Any]]:
        """
        领头人开启会话

        领头人（总编剧）负责：
        1. 宣布讨论开始
        2. 介绍讨论议题
        3. 引导讨论方向
        """
        try:
            participant_names = [p["name"] for p in participants if not p.get("is_leader")]

            prompt = f"""你是总编剧（讨论领头人），现在正式开启《{chapter_title}》创作讨论会。

【参会人员】
{', '.join(participant_names)}

【讨论内容】
章节：{chapter_title}
已写内容：{written_content[:1000] if written_content else "暂无"}...

【评估结果】
评分: {evaluation_result.get('score', 'N/A')}/10

请输出你的开场发言，宣布讨论开始，说明本次讨论的目标和重点。
格式要求：
1. 宣布讨论会开始
2. 简要介绍本章创作情况
3. 说明本次讨论需要解决的问题
4. 邀请各位发言

直接输出内容，不要有格式标记。"""

            if hasattr(agent, 'model') and agent.model:
                from langchain_core.messages import HumanMessage
                response = await agent.model.ainvoke([HumanMessage(content=prompt)])
                content = response.content.strip()

                return {
                    "agent": "总编剧",
                    "type": "master_plotter",
                    "content": content,
                    "is_llm_generated": True,
                    "is_leader_action": True,
                    "action": "open_session",
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
        }

    async def _generate_leader_summary_request(
        self,
        agent,
        chapter_title: str,
        discussion_messages: List[Dict],
    ) -> Optional[Dict[str, Any]]:
        """
        领头人汇总讨论并请求用户确认

        领头人负责：
        1. 汇总各位发言的要点
        2. 提出建议方案
        3. 请求用户确认
        """
        try:
            # 提取各 Agent 的发言要点
            messages_summary = []
            for msg in discussion_messages:
                agent_name = msg.get("agent", "Unknown")
                content = msg.get("content", "")[:200]
                messages_summary.append(f"【{agent_name}】{content}...")

            prompt = f"""你是总编剧（讨论领头人），现在需要汇总讨论结果并请求用户确认。

【讨论记录】
{chr(10).join(messages_summary)}

请输出你的汇总发言，格式要求：
1. 总结本次讨论的主要观点
2. 归纳达成的共识和分歧
3. 提出后续创作建议
4. 最后明确询问用户是否同意

直接输出内容。"""

            if hasattr(agent, 'model') and agent.model:
                from langchain_core.messages import HumanMessage
                response = await agent.model.ainvoke([HumanMessage(content=prompt)])
                content = response.content.strip()

                return {
                    "agent": "总编剧",
                    "type": "master_plotter",
                    "content": content,
                    "is_llm_generated": True,
                    "is_leader_action": True,
                    "action": "request_confirmation",
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
        """各 Agent 发表意见"""
        AGENT_NAME_MAP = {
            "evaluator": "评估员",
            "hook_manager": "伏笔管理员",
            "setting": "设定管理员",
            "world_map_manager": "地图管理员",
            "event_generator": "事件生成器",
            "writer": "作家",
            "character": "角色代表",
        }

        AGENT_OPINION_PROMPTS = {
            "evaluator": """你是评估员，请从质量控制角度进行**深度专业分析**。

【重要】你需要在讨论中发挥关键作用：
- 你是质量把关者，不要敷衍说"好的"
- 要指出具体问题，不要模棱两可
- 要提出可执行的改进方案

【评估结果】
评分: {score}/10
问题: {issues}
建议: {suggestions}

【你的专业分析职责】
1. **质量诊断**：深入分析章节的优缺点，不只是表面评价
2. **问题定位**：具体指出哪里有问题、为什么有问题、问题的影响
3. **改进方案**：提出具体的、可执行的修改建议
4. **风险预警**：预测可能出现的问题，提前预警
5. **标准把控**：确保内容符合长篇网文的质量标准

请从以下维度详细分析：

## 质量诊断
[深入分析本章的质量水平，优点要具体，缺点要尖锐]

## 问题清单
[列出发现的所有问题，每个问题说明：位置、性质、严重程度]

## 改进建议
[针对每个问题提出具体的修改方案，包括修改方向和预期效果]

## 风险预警
[预测后续可能出现的问题，提出预防措施]

## 后续章节建议
[从质量角度对后续创作提出专业建议]""",

            "hook_manager": """你是伏笔管理员，请从伏笔和悬念角度进行**深度专业分析**。

【重要】你是伏笔专家，要在讨论中发挥核心作用：
- 不要简单说"伏笔埋得不错"，要具体分析
- 追踪每一个伏笔的状态和回收计划
- 提出新伏笔的创意建议

【已有伏笔】{hooks_count} 个伏笔在追踪中

【你的专业分析职责】
1. **伏笔审计**：检查本章埋设的伏笔是否自然、合理
2. **回收规划**：追踪所有待回收伏笔，规划最佳回收时机
3. **悬念设计**：评估悬念设置是否有效，能否吸引读者
4. **风险识别**：发现可能遗忘或处理不当的伏笔
5. **创意贡献**：提出新的伏笔创意

请详细输出：

## 伏笔状态报告
[列出所有伏笔的状态：新埋设/待回收/已回收，以及具体内容]

## 伏笔质量评估
[分析每个伏笔的自然度、关联性、预期效果]

## 回收规划建议
[每个待回收伏笔的最佳回收时机和方式]

## 悬念效果分析
[评估本章悬念是否足够，能否吸引读者继续阅读]

## 新伏笔建议
[提出可以埋设的新伏笔，包括内容和预期作用]""",

            "setting": """你是设定管理员，请从世界观一致性角度进行**深度专业分析**。

【重要】你是世界观守护者，要确保设定不被破坏：
- 不要只说"设定一致"，要具体检查每个细节
- 发现设定冲突是重要贡献
- 提出深化世界观的具体方案

【你的专业分析职责】
1. **设定一致性检查**：逐一核对世界观规则是否被遵守
2. **设定冲突发现**：识别可能的设定矛盾或漏洞
3. **设定深化机会**：找出可以展现更多世界观的机会
4. **设定创新建议**：提出符合世界观的新元素创意
5. **规则完善建议**：发现规则模糊处，提出补充建议

请详细输出：

## 设定一致性报告
[逐一检查世界观规则在本章的应用情况]

## 发现的问题
[列出所有设定冲突、漏洞或不合理之处]

## 设定深化建议
[哪些地方可以更深入展现世界观，具体如何做]

## 创新元素建议
[提出可以引入的新设定元素，符合世界逻辑]

## 规则补充建议
[发现的世界观规则漏洞，提出补充方案]""",

            "world_map_manager": """你是地图管理员，请从场景和空间角度进行**深度专业分析**。

【重要】你是空间设计师，要让场景服务于剧情：
- 不要只说"场景描写不错"
- 分析场景与剧情的配合度
- 提出场景创新的具体方案

【你的专业分析职责】
1. **场景功能分析**：评估每个场景的功能和效果
2. **空间逻辑检查**：确保地点转换合理、空间关系清晰
3. **氛围营造评估**：分析场景氛围是否符合剧情需要
4. **场景创新建议**：提出新的、有趣的场景创意
5. **感官描写指导**：建议如何增强场景的感官体验

请详细输出：

## 场景功能报告
[每个场景的功能、效果、与剧情的配合度分析]

## 空间逻辑检查
[地点转换是否合理，空间关系是否清晰，有无漏洞]

## 氛围营造评估
[场景氛围是否到位，如何改进]

## 新场景建议
[可以引入的新场景，以及它们的作用]

## 感官描写建议
[如何增强视觉、听觉、嗅觉等感官体验]""",

            "event_generator": """你是事件生成器，请从事件和剧情推进角度进行**深度专业分析**。

【重要】你是剧情推进专家，要确保事件有实质意义：
- 不要只说"事件安排合理"
- 分析每个事件的因果和意义
- 提出更有张力的事件创意

【你的专业分析职责】
1. **事件效果分析**：评估每个事件的作用和效果
2. **因果逻辑检查**：确保事件的因果链条严密
3. **节奏推进评估**：分析事件是否有效推进剧情
4. **张力设计建议**：提出增加张力和冲突的方法
5. **新事件创意**：提出更有冲击力的事件创意

请详细输出：

## 事件效果报告
[每个事件的作用、效果、对剧情的推动分析]

## 因果逻辑分析
[事件的因果链条是否严密，有无逻辑漏洞]

## 节奏推进评估
[事件是否有效推进了剧情，节奏是否合适]

## 张力设计建议
[如何增加事件之间的张力和冲突]

## 新事件创意
[可以引入的新事件，包括内容、作用、预期效果]""",

            "writer": """你是作家，请从文字创作角度进行**深度专业分析**。

【重要】你是文字专家，要对表达效果负责：
- 不要只说"写得不错"
- 分析具体的文字技巧和效果
- 指出表达问题并提出修改方案

【字数检查】{word_count_info}

【你的专业分析职责】
1. **文字效果分析**：评估描写、对话、心理活动的表达效果
2. **风格一致性检查**：确保文风与整体一致
3. **技巧运用评估**：分析Show don't Tell、感官描写等技巧
4. **表达问题诊断**：发现具体的表达问题
5. **修改方案建议**：提出具体的文字修改方案

请详细输出：

## 文字效果报告
[描写、对话、心理活动的效果分析，好的和不好的都要指出]

## 风格一致性检查
[文风是否与整体一致，有无突兀之处]

## 技巧运用评估
[Show don't Tell、感官描写、节奏控制等技巧的运用情况]

## 表达问题诊断
[发现的具体表达问题，每一条都要有位置和改进建议]

## 修改方案
[针对发现的问题，提出具体的修改示例]""",

            "character": """你是角色代表，请从角色塑造角度进行**深度专业分析**。

【重要】你是角色专家，要确保角色塑造到位：
- 不要只说"角色表现得当"
- 分析每个角色的行为逻辑和成长
- 指出角色塑造的问题并提出改进

【参与角色】{characters}

【你的专业分析职责】
1. **角色行为分析**：评估每个角色的行为是否符合人设
2. **角色成长评估**：分析角色是否有成长或变化
3. **对话质量检查**：评估对话是否符合角色性格
4. **角色张力分析**：分析角色之间的张力和化学反应
5. **改进建议**：提出角色塑造的具体改进方案

请详细输出：

## 角色表现报告
[每个角色的表现分析，是否符合人设，有无OOC]

## 角色成长分析
[角色是否有成长或变化，成长弧线是否合理]

## 对话质量评估
[对话是否符合角色性格，有无突兀之处]

## 角色张力分析
[角色之间的互动是否有火花，如何增强]

## 改进建议
[针对发现的问题，提出具体的修改方案]""",
        }

        try:
            prompt_template = AGENT_OPINION_PROMPTS.get(agent_type, "")
            if not prompt_template:
                return None

            # 安全地格式化 issues（可能是 dict 列表或 str 列表）
            issues_raw = evaluation_result.get('issues', [])
            if issues_raw:
                issues_formatted = ', '.join([
                    str(i) if isinstance(i, str) else i.get('issue', i.get('description', str(i)))
                    for i in issues_raw[:5]
                ])
            else:
                issues_formatted = '无明显问题'

            # 安全地格式化 characters（可能是 dict 列表或 str 列表）
            if characters:
                char_names = [
                    str(c) if isinstance(c, str) else c.get('name', '未知角色')
                    for c in characters[:5]
                ]
                characters_formatted = ', '.join(char_names)
            else:
                characters_formatted = '暂无角色'

            # 格式化提示
            prompt = prompt_template.format(
                score=evaluation_result.get('score', 'N/A'),
                issues=issues_formatted,
                suggestions=evaluation_result.get('summary', '继续保持')[:200] if evaluation_result.get('summary') else '继续保持',
                hooks_count=len(context.get('existing_hooks', [])),
                word_count_info=context.get('word_count_check', {}).get('actual', '已统计') if context.get('word_count_check') else '字数已达标',
                characters=characters_formatted,
            )

            # 添加章节内容（重要：让Agent有具体的分析对象）
            if written_content:
                prompt += f"\n\n【章节内容（用于分析）】\n{written_content[:2000]}"

            # 添加世界观设定
            world_info = context.get("world_info", {})
            if world_info:
                prompt += f"\n\n【世界观设定】\n世界：{world_info.get('name', '未知')}\n类型：{world_info.get('world_type', '奇幻')}\n基调：{world_info.get('tone', '正剧')}"

            # 添加已有的伏笔信息
            existing_hooks = context.get('existing_hooks', [])
            if existing_hooks:
                hooks_info = [f"- {h.get('title', h.get('id', '未知'))}: {h.get('status', 'pending')}" for h in existing_hooks[:5]]
                prompt += f"\n\n【当前伏笔状态】\n{chr(10).join(hooks_info)}"

            # 添加前文讨论摘要（让后续发言能回应前面的问题）
            if previous_messages:
                recent_messages = []
                for m in previous_messages[-3:]:
                    speaker = m.get('agent', '某Agent')
                    content_preview = m.get('content', '')[:300]
                    recent_messages.append(f"【{speaker}】\n{content_preview}")
                if recent_messages:
                    prompt += f"\n\n【之前的讨论要点】\n{chr(10).join(recent_messages)}"
                prompt += "\n\n请结合以上讨论内容，提出你独特的专业见解。如果前面提到了问题，请给出你的解决方案。"

            if hasattr(agent, 'model') and agent.model:
                from langchain_core.messages import HumanMessage
                response = await agent.model.ainvoke([HumanMessage(content=prompt)])
                content = response.content.strip()

                return {
                    "agent": AGENT_NAME_MAP.get(agent_type, agent_type),
                    "type": agent_type,
                    "content": content,
                    "is_llm_generated": True,
                }
        except Exception as e:
            logger.error(f"{agent_type} 意见生成失败: {e}")

        # 回退到静态消息
        return {
            "agent": AGENT_NAME_MAP.get(agent_type, agent_type),
            "type": agent_type,
            "content": f"【{AGENT_NAME_MAP.get(agent_type, agent_type)}观点】从我的专业角度，本章表现符合预期，建议继续保持。",
            "is_llm_generated": False,
        }

    async def _generate_discussion_summary(
        self,
        agent,
        chapter_title: str,
        discussion_messages: List[Dict],
    ) -> Optional[Dict[str, Any]]:
        """总结 Agent 总结讨论（不限制字数，尽可能详细）"""
        try:
            # 构建讨论摘要
            discussion_text = "\n\n".join([
                f"【{m['agent']}】{m['content']}"
                for m in discussion_messages
            ])

            prompt = f"""你是总结员，请为本次创作讨论会做一个**有价值的总结**。

【重要】你的总结必须：
- **提炼关键问题**：从讨论中找出真正需要解决的核心问题
- **整合建议**：把各位Agent的建议整合成可执行的方案
- **明确行动项**：列出具体要做什么、谁来做、何时做
- **不要敷衍**：不要只说"大家意见很好"，要给出明确的结论

【讨论主题】《{chapter_title}》创作讨论

【讨论内容】
{discussion_text}

请输出结构化的总结：

## 核心问题总结
[从讨论中提炼出的最关键的3-5个问题]

## 各Agent意见摘要
[每个Agent的核心观点，包括：
- 编剧的判断
- 评估员的问题
- 伏笔管理员的风险预警
- 设定管理员的冲突发现
- 其他Agent的关键意见]

## 改进方案汇总
[针对每个问题，整合各位的建议，形成具体方案]

## 必须修改项
[列出必须修改的内容，包括：位置、问题、修改方向]

## 建议优化项
[列出可以优化的内容，非强制但建议做]

## 后续创作指南
[对下一章/下一阶段创作的具体指导]

## 需要追踪的事项
[伏笔回收计划、设定完善计划等需要长期追踪的事项]

直接输出总结内容。"""

            if hasattr(agent, 'model') and agent.model:
                from langchain_core.messages import HumanMessage
                response = await agent.model.ainvoke([HumanMessage(content=prompt)])
                content = response.content.strip()

                return {
                    "agent": "总结员",
                    "type": "summarizer",
                    "content": content,
                    "is_llm_generated": True,
                    "is_summary": True,
                }
        except Exception as e:
            logger.error(f"讨论总结生成失败: {e}")

        # 回退
        return {
            "agent": "总结员",
            "type": "summarizer",
            "content": f"【总结】本次讨论共{len(discussion_messages)}位Agent发言，讨论了{chapter_title}的创作表现。各方意见已记录，将作为后续创作的参考。",
            "is_llm_generated": False,
            "is_summary": True,
        }

    async def _broadcast_discussion_message(
        self,
        execution_id: str,
        message: Dict[str, Any],
        is_leader_action: bool = False,
        broadcast_to_all: bool = False,
    ):
        """
        广播讨论消息

        Args:
            execution_id: 执行 ID
            message: 消息内容
            is_leader_action: 是否是领头人的操作（开启/结束会话）
            broadcast_to_all: 是否广播给所有参与者
        """
        await self._broadcast_status(execution_id, "discussion_message", {
            "agent": message.get("agent", "Unknown"),
            "type": message.get("type", "unknown"),
            "content": message.get("content", ""),
            "is_llm_generated": message.get("is_llm_generated", False),
            "is_leader_action": is_leader_action,
            "broadcast_to_all": broadcast_to_all,
            "timestamp": datetime.now().isoformat(),
        })

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
        """
        让编剧Agent生成场景设定和表演方向

        注意：不限制字数，尽可能详细地规划场景
        """
        try:
            world_info = context.get("world_info", {})
            characters = context.get("characters", [])
            chapter_goal = context.get("chapter_goal", "")
            plot_outline = context.get("plot_outline", [])

            # 构建角色列表（包含重要性层级）
            char_info = []
            for c in characters[:8]:  # 最多8个主要角色
                if isinstance(c, dict):
                    name = c.get("name", "未知")
                    tier = c.get("importance_tier", 3)
                    ctype = c.get("character_type", "supporting")
                    is_protag = c.get("is_protagonist", False)
                    is_antag = c.get("is_antagonist", False)
                    char_info.append({
                        "name": name,
                        "tier": tier,
                        "type": ctype,
                        "is_protagonist": is_protag,
                        "is_antagonist": is_antag,
                    })

            prompt = f"""作为总编剧，你需要为接下来的角色演绎环节设定场景和表演方向。

【世界观设定】
名称：{world_info.get('name', '未知世界')}
类型：{world_info.get('world_type', '奇幻')}
背景：{world_info.get('background', world_info.get('description', ''))[:500]}
基调：{world_info.get('tone', '正剧')}
规则：{str(world_info.get('rules', {}))[:300]}

【当前章节目标】
{chapter_goal[:600] if chapter_goal else '推进主线剧情'}

【参与角色（含重要性层级）】
{chr(10).join([f"- {c['name']}（层级{c['tier']}，{c['type']}{'，主角' if c['is_protagonist'] else ''}{'，反派' if c['is_antagonist'] else ''}）" for c in char_info])}

【剧情大纲（最近）】
{str(plot_outline[-3:]) if plot_outline else '暂无'}

【重要原则】
1. 角色信息隔离：不要让角色知道不该知道的信息
2. 角色定位明确：主角推动剧情、反派制造冲突、配角辅助主线
3. 详细规划：场景描述要详细，角色分工要明确

请输出 JSON 格式（尽可能详细）：
{{
    "scene_type": "interactive 或 parallel",
    "scene_type_reason": "详细说明为什么选择这种场景类型",
    "main_scene": "主要场景的详细描述（地点、布置、氛围细节）",
    "atmosphere": "场景氛围（紧张、温馨、神秘等）",
    "time_of_day": "时间设定",
    "weather": "天气（如有必要）",
    "sensory_details": {{
        "visual": "视觉细节",
        "auditory": "听觉细节",
        "olfactory": "嗅觉细节（如有）"
    }},
    "character_roles": {{
        "角色名": {{
            "role_in_scene": "该角色在场景中的详细定位",
            "importance_tier": "角色重要性层级",
            "emotional_state": "情绪状态（详细描述）",
            "main_action": "主要行为和目标",
            "known_info": "该角色在场景中能知道的信息",
            "hidden_motivation": "隐藏动机（如果有）",
            "relationships_in_scene": "与场景中其他角色的关系"
        }}
    }},
    "required_characters": ["本场景必须出现的角色名列表"],
    "need_background_characters": true/false,
    "background_character_count": 2,
    "background_character_type": "路人/侍从/村民/商贩等",
    "background_role": "背景角色的作用描述",
    "background_interaction": true/false,
    "plot_focus": "本段表演要推进的核心剧情（详细描述）",
    "key_dialogue_topics": ["主要对话话题"],
    "conflict_points": ["场景中的冲突点"],
    "world_elements_to_use": ["要展示的世界观元素"],
    "foreshadowing_hints": ["可以埋下的伏笔暗示"],
    "pacing_note": "节奏控制建议",
    "visible_events": ["普通角色能看到的事件"],
    "character_filter": {{
        "min_tier": 1,
        "max_tier": 5,
        "locations": ["场景相关位置"],
        "tags": ["需要包含的角色标签"]
    }}
}}"""

            from langchain_core.messages import HumanMessage
            response = await plotter_agent.model.ainvoke([HumanMessage(content=prompt)])
            content = response.content.strip()

            # 解析 JSON
            import re
            import json
            json_match = re.search(r'```json\s*(.*?)\s*```', content, re.DOTALL)
            json_str = json_match.group(1) if json_match else content

            result = json.loads(json_str)
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
        """
        生成单个角色的表演内容

        重要原则：
        1. 信息隔离：角色只能知道自己应该知道的信息，不能有上帝视角
        2. 角色定位：角色要根据自己的重要性层级做出符合定位的行为
        3. 详细生成：不限制字数，尽可能详细地展现角色

        Args:
            agent: Character Agent 实例
            char_data: 角色数据（包含名字、性格、背景等）
            scene_directions: 场景方向（编剧设定）
            world_info: 世界观信息
            conversation_history: 对话历史（同场景模式下使用）
            is_interactive: 是否同场景互动模式
            turn_number: 当前轮次
            total_characters: 总角色数
            distributed_info: 智能分发的信息（可选）

        Returns:
            Dict: 包含角色名、表演内容等
        """
        try:
            char_name = char_data.get("name", "未知角色")
            char_role = scene_directions.get("character_roles", {}).get(char_name, {})

            # 构建角色信息
            personality = char_data.get("personality", "")
            background = char_data.get("background", char_data.get("description", ""))
            speech_pattern = char_data.get("speech_pattern", "")
            traits = char_data.get("traits", [])

            # 角色重要性层级
            importance_tier = char_data.get("importance_tier", 3)
            character_type = char_data.get("character_type", "supporting")
            is_protagonist = char_data.get("is_protagonist", False)
            is_antagonist = char_data.get("is_antagonist", False)

            # 根据重要性层级确定角色定位说明
            tier_description = self._get_character_tier_description(
                importance_tier, character_type, is_protagonist, is_antagonist
            )

            # 角色已知信息（信息隔离：只给角色应该知道的信息）
            known_info = self._get_character_known_info(
                char_data, scene_directions, world_info
            )

            # 构建对话历史（如果是互动模式）- 只保留该角色能感知到的内容
            history_context = ""
            if is_interactive and conversation_history:
                # 过滤对话历史，只保留在同一场合能听到的内容
                recent_history = conversation_history[-5:]
                history_lines = []
                for h in recent_history:
                    speaker = h.get("agent", "某角色")
                    content = h.get("content", "")[:150]
                    history_lines.append(f"{speaker}: {content}")
                history_context = f"\n【当前场景中你能听到/看到的对话】\n" + "\n".join(history_lines)

            prompt = f"""你现在扮演角色「{char_name}」，请进行真实的角色表演。

═══════════════════════════════════════════════════════
【核心原则 - 必须遵守】
═══════════════════════════════════════════════════════

⚠️ 【信息隔离原则】
你只能使用「{char_name}」这个角色已知的信息！
- 你不知道其他角色的内心想法
- 你不知道还没发生的事件
- 你不知道别人私下说的话
- 你不知道剧情的全貌
- 你不能"预知"接下来会发生什么
- 你的所有反应必须基于角色当下的认知

⚠️ 【角色定位原则】
{tier_description}

你必须根据自己的定位行动：
- 如果是主角，你要推动剧情、展现成长、面对挑战
- 如果是反派，你要制造冲突、阻碍主角、展现威胁
- 如果是配角，你要辅助主线、丰富世界、不抢戏份
- 如果是路人，你要反应真实、烘托氛围、不干扰主线

═══════════════════════════════════════════════════════
【角色档案】
═══════════════════════════════════════════════════════
名字：{char_name}
类型：{character_type}
重要性层级：{importance_tier}（1=核心，2=重要，3=普通，4=配角，5=路人）
性格：{personality[:300] if personality else '根据剧情需要表现'}
背景：{background[:400] if background else '普通背景'}
说话风格：{speech_pattern if speech_pattern else '自然随意'}
特质：{', '.join(traits[:5]) if traits else '无特殊特质'}

═══════════════════════════════════════════════════════
【角色已知信息】（你只知道这些！）
═══════════════════════════════════════════════════════
{known_info}

═══════════════════════════════════════════════════════
【当前场景】
═══════════════════════════════════════════════════════
场景类型：{'同场景互动' if is_interactive else '独立场景'}
主场景：{scene_directions.get('main_scene', '未设定')}
氛围：{scene_directions.get('atmosphere', '正剧')}
时间：{scene_directions.get('time_of_day', '未设定')}

【你的角色在场景中的定位】
{char_role.get('role_in_scene', '参与者')}
情绪状态：{char_role.get('emotional_state', '平静')}
主要行为：{char_role.get('main_action', '自然互动')}
{f'隐藏动机：{char_role.get("secret_motivation")}' if char_role.get('secret_motivation') else ''}

{history_context}

═══════════════════════════════════════════════════════
【表演要求】
═══════════════════════════════════════════════════════
1. 用第一人称表演，完全沉浸在这个角色中
2. 展现角色的性格、说话风格和思维模式
3. 严格遵守信息隔离，不要表现出不该知道的信息
4. 根据你的角色定位行动，做自己该做的事
5. 如果是同场景互动，回应其他角色的话语
6. 展现内心活动和情感波动
7. 表演要有剧情意义，不要无意义的闲聊
8. 可以埋下符合你角色视角的暗示或伏笔

【字数要求】
不限字数，尽可能详细地展现角色的行为、对话、心理活动。

直接输出你的表演内容（包含动作描写、对话、内心独白等），不要有任何格式标记或解释。"""

            from langchain_core.messages import HumanMessage
            response = await agent.model.ainvoke([HumanMessage(content=prompt)])
            content = response.content.strip()

            return {
                "agent": char_name,
                "type": "character_performance",
                "content": content,
                "is_llm_generated": True,
                "turn_number": turn_number,
                "total_characters": total_characters,
                "character_tier": importance_tier,
                "character_type": character_type,
            }

        except Exception as e:
            logger.error(f"角色表演生成失败: {e}")
            return {
                "agent": char_data.get("name", "未知角色"),
                "type": "character_performance",
                "content": f"（角色表演生成失败，跳过）",
                "is_llm_generated": False,
            }

    def _match_character_filter(self, character: Dict[str, Any], filter_config: Dict[str, Any]) -> bool:
        """
        检查角色是否匹配场景筛选条件

        Args:
            character: 角色数据
            filter_config: 筛选条件，如:
                {
                    "min_tier": 3,           # 最低重要性层级
                    "max_tier": 5,           # 最高重要性层级
                    "character_types": ["supporting", "background"],  # 角色类型
                    "locations": ["客栈", "街道"],  # 当前位置
                    "tags": ["商人", "武者"],  # 标签匹配
                    "must_include": ["李明"], # 必须包含的角色
                }

        Returns:
            bool: 是否匹配
        """
        # 必须包含的角色
        if filter_config.get("must_include"):
            if character.get("name") in filter_config["must_include"]:
                return True

        # 重要性层级范围
        min_tier = filter_config.get("min_tier", 1)
        max_tier = filter_config.get("max_tier", 5)
        char_tier = character.get("importance_tier", 3)
        if not (min_tier <= char_tier <= max_tier):
            return False

        # 角色类型
        if filter_config.get("character_types"):
            char_type = character.get("character_type", "supporting")
            if char_type not in filter_config["character_types"]:
                return False

        # 位置匹配
        if filter_config.get("locations"):
            char_location = character.get("current_location", "")
            if char_location and char_location not in filter_config["locations"]:
                return False

        # 标签匹配
        if filter_config.get("tags"):
            char_tags = character.get("tags", []) or character.get("traits", [])
            if not any(tag in char_tags for tag in filter_config["tags"]):
                return False

        return True

    def _distribute_scene_info_to_character(
        self,
        char_data: Dict[str, Any],
        scene_directions: Dict[str, Any],
        world_info: Dict[str, Any],
        previous_node_output: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        将场景信息智能分发给角色

        根据角色的重要性和在场景中的定位，分配合适的信息

        Args:
            char_data: 角色数据
            scene_directions: 场景方向
            world_info: 世界观信息
            previous_node_output: 上一个节点的输出

        Returns:
            Dict: 该角色应该知道的信息
        """
        char_name = char_data.get("name", "未知角色")
        importance_tier = char_data.get("importance_tier", 3)
        char_role = scene_directions.get("character_roles", {}).get(char_name, {})

        distributed_info = {
            "scene_info": {},
            "plot_context": {},
            "character_specific": {},
        }

        # 1. 场景基础信息（所有在场角色都知道）
        distributed_info["scene_info"] = {
            "location": scene_directions.get("main_scene", "未知地点"),
            "atmosphere": scene_directions.get("atmosphere", "正剧"),
            "time": scene_directions.get("time_of_day", "白天"),
        }

        # 2. 剧情上下文（根据重要性分发不同程度）
        if importance_tier <= 2:
            # 重要角色知道更多
            distributed_info["plot_context"] = {
                "plot_focus": scene_directions.get("plot_focus", ""),
                "conflict_points": scene_directions.get("conflict_points", []),
                "key_events": previous_node_output.get("key_events", [])[:3],
            }
        else:
            # 普通角色只知道表面
            distributed_info["plot_context"] = {
                "visible_events": scene_directions.get("visible_events", []),
            }

        # 3. 角色专属信息
        if char_role:
            distributed_info["character_specific"] = {
                "role_in_scene": char_role.get("role_in_scene", "参与者"),
                "emotional_state": char_role.get("emotional_state", "平静"),
                "known_info": char_role.get("known_info", ""),
                "hidden_motivation": char_role.get("hidden_motivation", ""),
            }

        # 4. 处理上一个节点传递的信息
        if previous_node_output:
            # 提取与该角色相关的信息
            related_dialogues = []
            for dialogue in previous_node_output.get("dialogues", []):
                # 如果对话涉及该角色或发生在同一地点
                if char_name in dialogue.get("content", "") or dialogue.get("is_public", True):
                    related_dialogues.append(dialogue)

            distributed_info["previous_context"] = {
                "related_dialogues": related_dialogues[-3:],  # 最近3条相关对话
                "recent_events": previous_node_output.get("events", [])[-2:],
            }

        return distributed_info

    def _generate_background_character_behavior(
        self,
        background_char: Dict[str, Any],
        scene_directions: Dict[str, Any],
        main_characters: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        生成背景角色的行为

        背景角色行为应该简短、自然、不干扰主线

        Args:
            background_char: 背景角色数据
            scene_directions: 场景方向
            main_characters: 场景中的主要角色列表

        Returns:
            Dict: 背景角色的行为描述
        """
        char_name = background_char.get("name", "路人")
        scene_type = scene_directions.get("scene_type", "interactive")
        atmosphere = scene_directions.get("atmosphere", "正剧")

        # 根据场景氛围生成适合的背景行为
        behavior_templates = {
            "正剧": [
                f"({char_name}在一旁静静观看)",
                f"({char_name}走过，没有停留)",
                f"({char_name}低声交谈了几句)",
            ],
            "紧张": [
                f"({char_name}神色紧张地望向这边)",
                f"({char_name}快步走过)",
                f"({char_name}低着头匆匆离开)",
            ],
            "欢快": [
                f"({char_name}笑着走过)",
                f"({char_name}在远处闲聊)",
                f"({char_name}心情不错的样子)",
            ],
            "悲伤": [
                f"({char_name}默默走过)",
                f"({char_name}低着头，似乎在沉思)",
            ],
        }

        behaviors = behavior_templates.get(atmosphere, behavior_templates["正剧"])

        # 选择一个合适的行为
        import random
        selected_behavior = random.choice(behaviors)

        # 如果场景需要互动，可能让背景角色有简单反应
        if scene_directions.get("background_interaction") and random.random() < 0.3:
            main_char = random.choice(main_characters) if main_characters else {"name": "某人"}
            return {
                "agent": char_name,
                "type": "background_action",
                "content": selected_behavior + f"，看了{main_char.get('name', '某人')}一眼",
                "is_llm_generated": False,
                "importance": "background",
            }

        return {
            "agent": char_name,
            "type": "background_action",
            "content": selected_behavior,
            "is_llm_generated": False,
            "importance": "background",
        }

    def _get_character_tier_description(
        self,
        importance_tier: int,
        character_type: str,
        is_protagonist: bool,
        is_antagonist: bool,
    ) -> str:
        """根据角色重要性层级返回定位说明"""
        if is_protagonist:
            return """【你是主角】
你的职责：
- 推动主线剧情发展
- 展现角色的成长和变化
- 面对挑战，做出关键抉择
- 你的行动直接影响故事走向
- 让读者能够代入你的视角

注意事项：
- 不要太过完美，要有弱点和成长空间
- 你的每个决定都应该有后果
- 展现真实的情感和挣扎"""

        if is_antagonist:
            return """【你是反派/对立角色】
你的职责：
- 制造冲突和阻碍
- 对主角形成真正的威胁
- 展现你的动机和逻辑（你觉得自己是对的）
- 推动剧情走向高潮

注意事项：
- 你不是单纯的坏人，你有自己的目标和理由
- 你的行为要有威胁感，但也要合理
- 你的存在是为了让主角成长，不是为了送死
- 要有作为反派的气场和压迫感"""

        if importance_tier == 1:
            return """【你是核心角色】
你的职责：
- 参与主线剧情的关键节点
- 你的行动和选择影响故事走向
- 展现丰富的性格和成长弧线
- 与主角有重要互动

注意事项：
- 你的出场要有分量
- 你的行为要有前后一致性
- 要让观众记住你"""

        if importance_tier == 2:
            return """【你是重要角色】
你的职责：
- 辅助主线剧情
- 丰富故事世界
- 在关键时刻提供帮助或制造变数
- 展现独特的个性

注意事项：
- 不要抢主角的风头
- 但也要有存在感
- 你的行为要符合你的定位"""

        if importance_tier == 3:
            return """【你是普通角色】
你的职责：
- 丰富故事的背景和世界
- 在特定场景发挥作用
- 展现普通人/普通角色的视角
- 烘托氛围和情境

注意事项：
- 你的行为要自然、真实
- 不要过度介入主线
- 但也要有合理的作用"""

        if importance_tier >= 4:
            return """【你是配角/路人】
你的职责：
- 填充世界，让故事更真实
- 对剧情做自然的反应
- 烘托主角和重要角色的存在
- 展现世界观的一个侧面

注意事项：
- 不要干扰主线
- 要有真实自然的反应
- 可以用简短的台词或行为表达"""

        return ""

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
                    rule_items = list(rules.items())[:3]
                    known_parts.append("已知世界规则：")
                    for k, v in rule_items:
                        known_parts.append(f"  - {k}: {v}")

        # 角色自己的经历和知识
        background = char_data.get("background", "")
        if background:
            known_parts.append(f"你的经历：{background[:200]}")

        # 角色与其他角色的关系（只知道自己这边的关系）
        relationships = char_data.get("relationships", [])
        if relationships:
            known_parts.append("你认识的人：")
            for rel in relationships[:3]:
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
    ) -> Optional[Dict[str, Any]]:
        """
        生成表演总结（不限制字数，尽可能详细）

        Args:
            summarizer_agent: 总结 Agent
            scene_directions: 场景方向
            performance_messages: 表演消息列表

        Returns:
            Dict: 总结内容
        """
        try:
            # 提取表演内容（使用更多内容）
            performances = []
            for msg in performance_messages:
                agent = msg.get("agent", "未知")
                content = msg.get("content", "")[:500]
                performances.append(f"【{agent}】\n{content}")

            prompt = f"""作为总结员，请对刚才的角色演绎进行详细总结。

【场景设定】
{scene_directions.get('main_scene', '未设定')}
氛围：{scene_directions.get('atmosphere', '正剧')}
剧情焦点：{scene_directions.get('plot_focus', '推进剧情')}

【角色表演内容】
{chr(10).join(performances)}

请输出 JSON 格式（尽可能详细）：
{{
    "summary": "表演内容详细总结",
    "plot_advancement": "详细分析剧情推进要点",
    "character_performances": {{
        "角色名": {{
            "performance_quality": "表演质量评价",
            "character_consistency": "角色一致性分析",
            "highlight_moments": ["亮点时刻"]
        }}
    }},
    "character_highlights": ["各角色亮点时刻汇总"],
    "world_elements_shown": ["展示的世界观元素及评价"],
    "foreshadowing_planted": ["埋下的伏笔及其预期效果"],
    "dialogue_quality": "对话质量评价",
    "pacing_analysis": "节奏分析",
    "next_scene_suggestion": "下一场景的详细建议",
    "improvement_suggestions": ["改进建议"]
}}"""

            from langchain_core.messages import HumanMessage
            response = await summarizer_agent.model.ainvoke([HumanMessage(content=prompt)])
            content = response.content.strip()

            # 尝试解析 JSON
            import re
            import json
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
                }
            except json.JSONDecodeError:
                return {
                    "agent": "总结员",
                    "type": "performance_summary",
                    "content": content,
                    "is_llm_generated": True,
                }

        except Exception as e:
            logger.error(f"表演总结生成失败: {e}")
            return {
                "agent": "总结员",
                "type": "performance_summary",
                "content": "角色演绎已完成，各角色展现了精彩的表现。",
                "is_llm_generated": False,
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
                    execution.context["retry_history"] = []
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
                        # 找到 pass 分支并返回
                        if pass_edge:
                            # 清理上下文
                            execution.context["retry_count"] = 0
                            execution.context["retry_history"] = []
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
            for i, issue in enumerate(issues[:5], 1):  # 最多显示5个问题
                msg_parts.append(f"  {i}. {issue}")

        if suggestions:
            msg_parts.append(f"改进建议:")
            for i, suggestion in enumerate(suggestions[:5], 1):  # 最多显示5条建议
                msg_parts.append(f"  {i}. {suggestion}")

        return "\n".join(msg_parts)

    def _get_start_node_id(self, workflow: "WorkflowDefinition") -> Optional[str]:
        """获取起始节点ID"""
        start_nodes = [n for n in workflow.nodes if n.node_type == NodeType.START]
        return start_nodes[0].id if start_nodes else None

    # ==================== 执行控制 ====================

    async def pause_workflow(self, execution_id: str, db=None) -> bool:
        """暂停工作流"""
        execution = self._executions.get(execution_id)
        if not execution:
            return False

        if execution.status != WorkflowStatus.RUNNING:
            return False

        execution.status = WorkflowStatus.PAUSED

        if db:
            await self._save_execution_to_db(execution, db)

        await self._broadcast_status(execution_id, "workflow_paused", {})
        logger.info(f"暂停工作流: {execution_id}")
        return True

    async def resume_workflow(self, execution_id: str, db=None) -> bool:
        """恢复工作流执行"""
        execution = self._executions.get(execution_id)
        if not execution:
            # 尝试从数据库加载
            if db:
                execution = await self._load_execution_from_db(execution_id, db)
                if execution:
                    self._executions[execution_id] = execution

        if not execution:
            logger.warning(f"工作流执行不存在: {execution_id}")
            return False

        if execution.status != WorkflowStatus.PAUSED:
            return False

        execution.status = WorkflowStatus.RUNNING

        if db:
            await self._save_execution_to_db(execution, db)

        await self._broadcast_status(execution_id, "workflow_resumed", {})
        logger.info(f"恢复工作流: {execution_id}")

        # 重新启动执行循环
        workflow = await self.get_workflow(execution.workflow_id, db)
        if workflow:
            asyncio.create_task(self._run_workflow(execution_id, workflow, db))

        return True

    async def cancel_workflow(self, execution_id: str, db=None) -> bool:
        """取消工作流"""
        execution = self._executions.get(execution_id)
        if not execution:
            return False

        if execution.status in [WorkflowStatus.COMPLETED, WorkflowStatus.FAILED]:
            return False

        execution.status = WorkflowStatus.CANCELLED
        execution.completed_at = datetime.now()

        if db:
            await self._save_execution_to_db(execution, db)

        await self._broadcast_status(execution_id, "workflow_cancelled", {})
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
                await self._broadcast_discussion_message(execution_id, closing_message, is_leader_action=True)

        # 广播讨论结束
        await self._broadcast_status(execution_id, "group_discussion_ended", {
            "approved": approved,
            "feedback": feedback,
            "message": f"讨论会结束，{'用户同意' if approved else '用户不同意'}讨论结果",
        })

        if approved:
            # 用户同意，恢复工作流继续执行
            logger.info(f"用户同意讨论结果，继续执行工作流: {execution_id}")

            execution.context.pop("waiting_confirmation", None)
            execution.status = WorkflowStatus.RUNNING
            if db:
                await self._save_execution_to_db(execution, db)

            await self._broadcast_status(execution_id, "discussion_confirmed", {
                "approved": True,
                "message": "用户同意讨论结果，工作流继续执行",
            })

            workflow = await self.get_workflow(execution.workflow_id, db)
            if workflow:
                asyncio.create_task(self._run_workflow(execution_id, workflow, db))

            return {
                "success": True,
                "approved": True,
                "message": "工作流继续执行",
            }

        else:
            # 用户不同意，重置工作流并注入反馈
            if not feedback:
                return {"success": False, "error": "不同意讨论结果时必须提供反馈意见"}

            logger.info(f"用户不同意讨论结果，将重新执行工作流: {execution_id}")
            logger.info(f"用户反馈: {feedback[:200]}...")

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
        # 先查内存
        if execution_id in self._executions:
            return self._executions[execution_id]

        # 查数据库
        if db:
            return await self._load_execution_from_db(execution_id, db)

        return None

    # ==================== WebSocket 广播 ====================

    async def _broadcast_status(self, execution_id: str, event_type: str, data: Dict[str, Any]):
        """广播状态更新"""
        if self._broadcast_callback:
            try:
                # 序列化数据，处理 UUID 和其他非 JSON 类型
                serialized_data = self._serialize_for_json(data)
                await self._broadcast_callback(execution_id, event_type, serialized_data)
            except Exception as e:
                # 连接断开是正常情况，使用 debug 级别避免日志污染
                if "close message has been sent" in str(e) or "DISCONNECTED" in str(e):
                    logger.debug(f"WebSocket 已断开，跳过广播: {event_type}")
                else:
                    logger.warning(f"广播状态失败: {e}")

    def _serialize_for_json(self, obj: Any) -> Any:
        """递归序列化对象，处理 UUID 等非 JSON 类型"""
        import uuid
        from datetime import datetime
        from types import MappingProxyType

        if isinstance(obj, uuid.UUID):
            return str(obj)
        elif isinstance(obj, datetime):
            return obj.isoformat()
        elif isinstance(obj, MappingProxyType):
            # 处理 mappingproxy 类型
            return dict(obj)
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

        # 自动修复节点类型（兼容旧数据）
        def fix_node_type(node: dict) -> dict:
            node_type = node.get("node_type", "")
            node_id = node.get("id", "")
            label = node.get("label", "")

            # 根据 ID 或 label 推断正确的类型
            if node_type == "agent":
                if node_id == "start" or label in ["开始", "Start", "start"]:
                    node["node_type"] = "start"
                    node.pop("agent_type", None)  # 移除错误的 agent_type
                elif node_id == "end" or label in ["结束", "End", "end"]:
                    node["node_type"] = "end"
                    node.pop("agent_type", None)
                elif node_type == "agent" and not node.get("agent_type"):
                    # Agent 节点没有 agent_type，尝试从 label 推断
                    label_lower = label.lower()
                    if "作家" in label or "writer" in label_lower:
                        node["agent_type"] = "writer"
                    elif "编剧" in label or "plotter" in label_lower:
                        node["agent_type"] = "plotter"
                    elif "角色" in label or "character" in label_lower:
                        node["agent_type"] = "character"
                    elif "评估" in label or "evaluator" in label_lower:
                        node["agent_type"] = "evaluator"
                    elif "伏笔" in label or "hook" in label_lower:
                        node["agent_type"] = "hook_manager"
                    elif "摘要" in label or "summarizer" in label_lower:
                        node["agent_type"] = "summarizer"
                    elif "设定" in label or "setting" in label_lower:
                        node["agent_type"] = "setting"
                    elif "事件" in label or "event" in label_lower:
                        node["agent_type"] = "event_generator"
                    elif "地图" in label or "map" in label_lower:
                        node["agent_type"] = "world_map_manager"

            return node

        # 修复所有节点
        fixed_nodes = [fix_node_type(n.copy()) for n in nodes_data]

        return WorkflowDefinition(
            id=row["id"],
            project_id=str(row["project_id"]),
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

            workflows.append(WorkflowDefinition(
                id=row["id"],
                project_id=str(row["project_id"]),
                name=row["name"],
                description=row["description"],
                nodes=[WorkflowNode(**n) for n in nodes_data],
                edges=[WorkflowEdge(**e) for e in edges_data],
                variables=variables_data,
                is_template=row["is_template"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            ))

        return workflows

    async def _save_execution_to_db(self, execution: WorkflowExecution, db):
        """保存执行记录到数据库"""
        import json
        query = """
        INSERT INTO workflow_executions (id, workflow_id, project_id, status, current_node, node_states, context, intervention_ids, started_at, completed_at, total_duration_ms, error)
        VALUES (:id, :workflow_id, :project_id, :status, :current_node, :node_states, :context, :intervention_ids, :started_at, :completed_at, :total_duration_ms, :error)
        ON CONFLICT (id) DO UPDATE SET
            status = EXCLUDED.status,
            current_node = EXCLUDED.current_node,
            node_states = EXCLUDED.node_states,
            context = EXCLUDED.context,
            intervention_ids = EXCLUDED.intervention_ids,
            completed_at = EXCLUDED.completed_at,
            total_duration_ms = EXCLUDED.total_duration_ms,
            error = EXCLUDED.error
        """
        params = {
            "id": execution.id,
            "workflow_id": execution.workflow_id,
            "project_id": execution.project_id,
            "status": execution.status.value,
            "current_node": execution.current_node,
            "node_states": json.dumps({k: v.model_dump(mode='json') for k, v in execution.node_states.items()}),
            "context": json.dumps(execution.context, default=str),
            "intervention_ids": json.dumps(execution.intervention_ids),
            "started_at": execution.started_at,
            "completed_at": execution.completed_at,
            "total_duration_ms": execution.total_duration_ms,
            "error": execution.error,
        }
        await db.execute_write(query, params)

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
