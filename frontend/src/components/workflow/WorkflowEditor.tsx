/**
 * 工作流编辑器组件
 * v8 Agent协作可视化工作台
 */

import { useState, useCallback, useMemo, useRef, useEffect } from 'react'
import ReactFlow, {
  Background,
  Controls,
  MiniMap,
  addEdge,
  applyNodeChanges,
  applyEdgeChanges,
  type Node,
  type Edge,
  type OnNodesChange,
  type OnEdgesChange,
  type Connection,
  type NodeTypes,
  Panel,
} from 'reactflow'
import 'reactflow/dist/style.css'

import { useTheme } from '@/contexts/ThemeContext'
import {
  createWorkflow,
  updateWorkflow,
  executeWorkflow,
  type WorkflowNode as WfNode,
  type WorkflowEdge as WfEdge,
  type WorkflowDefinition,
} from '@/api/workflows'

import AgentNode from './AgentNode'
import ConditionNode from './ConditionNode'
import ParallelNode from './ParallelNode'
import NodePanel from './NodePanel'
import PropertyPanel from './PropertyPanel'

import {
  Play,
  Pause,
  Square,
  Save,
  Undo,
  Redo,
  Trash2,
  ZoomIn,
  ZoomOut,
  AlertCircle,
} from 'lucide-react'

// 注册自定义节点类型（必须用 useMemo 包裹，否则 ReactFlow 会重新渲染）
const nodeTypes: NodeTypes = useMemo(() => ({
  agent: AgentNode,
  condition: ConditionNode,
  parallel: ParallelNode,
  group_discussion: AgentNode,  // 集体讨论节点
  scene_performance: AgentNode, // 场景演绎节点
  start: AgentNode,
  end: AgentNode,
  input: AgentNode,
}), [])

interface WorkflowEditorProps {
  projectId: string
  workflow?: WorkflowDefinition
  onExecutionStart?: (executionId: string) => void
  onWorkflowSave?: (workflow: WorkflowDefinition) => void
}

// 生成唯一 ID
const generateId = () => `node_${Date.now()}_${Math.random().toString(36).slice(2, 9)}`

export default function WorkflowEditor({
  projectId,
  workflow,
  onExecutionStart,
  onWorkflowSave,
}: WorkflowEditorProps) {
  const { theme } = useTheme()
  const isDark = theme === 'dark'

  const reactFlowWrapper = useRef<HTMLDivElement>(null)

  // 转换工作流数据为 ReactFlow 格式
  const initialNodes: Node[] = useMemo(() => {
    if (!workflow) {
      // 默认开始和结束节点（使用自定义类型）
      return [
        {
          id: 'start',
          type: 'start',
          position: { x: 250, y: 50 },
          data: { label: '开始' },
        },
        {
          id: 'end',
          type: 'end',
          position: { x: 250, y: 500 },
          data: { label: '结束' },
        },
      ]
    }
    return workflow.nodes.map((node) => ({
      id: node.id,
      type: node.node_type,
      position: node.position,
      data: {
        label: node.label,
        agent_type: node.agent_type,
        config: node.config,
      },
    }))
  }, [workflow])

  const initialEdges: Edge[] = useMemo(() => {
    if (!workflow) return []
    return workflow.edges.map((edge) => ({
      id: edge.id,
      source: edge.source,
      target: edge.target,
      animated: true,
    }))
  }, [workflow])

  // 状态
  const [nodes, setNodes] = useState<Node[]>(initialNodes)
  const [edges, setEdges] = useState<Edge[]>(initialEdges)
  const [selectedNode, setSelectedNode] = useState<Node | null>(null)

  // 当 workflow 改变时，重新加载节点和边
  useEffect(() => {
    if (workflow) {
      console.log('重新加载工作流:', workflow.id)
      console.log('节点数量:', workflow.nodes.length)
      console.log('边数量:', workflow.edges.length)

      setNodes(workflow.nodes.map((node) => ({
        id: node.id,
        type: node.node_type,
        position: node.position,
        data: {
          label: node.label,
          agent_type: node.agent_type,
          config: node.config,
          inputs: node.inputs,
          outputs: node.outputs,
        },
      })))

      setEdges(workflow.edges.map((edge) => ({
        id: edge.id,
        source: edge.source,
        target: edge.target,
        animated: true,
      })))
    }
  }, [workflow?.id])  // 只在 workflow.id 改变时重新加载
  const [workflowName, setWorkflowName] = useState(workflow?.name || '新工作流')
  const [saving, setSaving] = useState(false)
  const [executing, setExecuting] = useState(false)
  const [executionId, setExecutionId] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  // 节点变化处理
  const onNodesChange: OnNodesChange = useCallback(
    (changes) => {
      // 检测删除操作，同时清理相关边
      const removedIds = new Set<string>()
      changes.forEach((change) => {
        if (change.type === 'remove') {
          removedIds.add(change.id)
        }
      })

      // 先清理边，再更新节点
      if (removedIds.size > 0) {
        console.log('检测到节点删除，清理相关边:', Array.from(removedIds))
        setEdges((eds) => {
          const filtered = eds.filter((e) => !removedIds.has(e.source) && !removedIds.has(e.target))
          console.log(`边数量: ${eds.length} -> ${filtered.length}`)
          return filtered
        })
      }

      setNodes((nds) => applyNodeChanges(changes, nds))
    },
    [],
  )

  // 边变化处理
  const onEdgesChange: OnEdgesChange = useCallback(
    (changes) => {
      // 检测删除操作
      const removedEdgeIds = new Set<string>()
      changes.forEach((change) => {
        if (change.type === 'remove') {
          removedEdgeIds.add(change.id)
        }
      })

      if (removedEdgeIds.size > 0) {
        console.log('检测到边删除:', Array.from(removedEdgeIds))
      }

      setEdges((eds) => applyEdgeChanges(changes, eds))
    },
    [],
  )

  // 连接处理
  const onConnect = useCallback(
    (connection: Connection) => {
      setEdges((eds) => addEdge({ ...connection, animated: true }, eds))
    },
    [],
  )

  // 拖放处理
  const onDragOver = useCallback((event: React.DragEvent) => {
    event.preventDefault()
    event.dataTransfer.dropEffect = 'move'
  }, [])

  const onDrop = useCallback(
    (event: React.DragEvent) => {
      event.preventDefault()

      const data = event.dataTransfer.getData('application/reactflow')
      if (!data) return

      const { nodeType, data: nodeData } = JSON.parse(data)

      // 获取画布位置
      const bounds = reactFlowWrapper.current?.getBoundingClientRect()
      if (!bounds) return

      const position = {
        x: event.clientX - bounds.left - 70,
        y: event.clientY - bounds.top - 30,
      }

      // 创建新节点
      const newNode: Node = {
        id: generateId(),
        type: nodeType,
        position,
        data: nodeData,
      }

      setNodes((nds) => [...nds, newNode])
    },
    [],
  )

  // 节点选择处理
  const onNodeClick = useCallback((_: React.MouseEvent, node: Node) => {
    setSelectedNode(node)
    setSelectedEdge(null)
  }, [])

  // 边选择处理
  const onEdgeClick = useCallback((_: React.MouseEvent, edge: Edge) => {
    setSelectedEdge(edge)
    setSelectedNode(null)
  }, [])

  // 选中的边
  const [selectedEdge, setSelectedEdge] = useState<Edge | null>(null)

  // 画布点击处理
  const onPaneClick = useCallback(() => {
    setSelectedNode(null)
    setSelectedEdge(null)
  }, [])

  // 保存工作流
  const handleSave = async () => {
    setSaving(true)
    setError(null)

    // 类型映射：ReactFlow 类型 -> 后端类型
    const mapNodeType = (type: string): string => {
      const typeMap: Record<string, string> = {
        'input': 'start',      // ReactFlow input 节点映射为 start
        'output': 'end',       // ReactFlow output 节点映射为 end
        'agent': 'agent',
        'condition': 'condition',
        'parallel': 'parallel',
        'start': 'start',
        'end': 'end',
      }
      return typeMap[type] || type
    }

    // 检测循环依赖
    const detectCycle = (nodes: Node[], edges: Edge[]): string | null => {
      const graph = new Map<string, string[]>()
      edges.forEach((edge) => {
        if (!graph.has(edge.source)) graph.set(edge.source, [])
        graph.get(edge.source)!.push(edge.target)
      })

      const visited = new Set<string>()
      const recStack = new Set<string>()
      const path: string[] = []

      const dfs = (nodeId: string): boolean => {
        visited.add(nodeId)
        recStack.add(nodeId)
        path.push(nodeId)

        const neighbors = graph.get(nodeId) || []
        for (const neighbor of neighbors) {
          if (!visited.has(neighbor)) {
            if (dfs(neighbor)) return true
          } else if (recStack.has(neighbor)) {
            path.push(neighbor)
            return true
          }
        }

        path.pop()
        recStack.delete(nodeId)
        return false
      }

      for (const node of nodes) {
        if (!visited.has(node.id)) {
          if (dfs(node.id)) {
            const cycleStart = path.indexOf(path[path.length - 1])
            const cyclePath = path.slice(cycleStart).map((id) => {
              const node = nodes.find((n) => n.id === id)
              return node?.data?.label || id
            })
            return cyclePath.join(' -> ')
          }
        }
      }
      return null
    }

    // 映射后的节点类型
    const mappedNodes = nodes.map((node) => ({
      ...node,
      mappedType: mapNodeType(node.type || ''),
    }))

    // 调试日志 - 详细输出
    console.log('=== 保存工作流调试信息 ===')
    console.log('原始 nodes:', nodes.map((n) => ({ id: n.id, type: n.type, label: n.data?.label })))
    console.log('映射后 mappedNodes:', mappedNodes.map((n) => ({ id: n.id, type: n.type, mappedType: n.mappedType, label: n.data?.label })))
    console.log('workflowNodes:', mappedNodes.map((n) => ({
      id: n.id,
      node_type: n.mappedType,
      label: n.data?.label,
    })))
    console.log('=== 调试信息结束 ===')

    // 前端验证
    const startNodes = mappedNodes.filter((n) => n.mappedType === 'start')
    const endNodes = mappedNodes.filter((n) => n.mappedType === 'end')
    const agentNodes = mappedNodes.filter((n) => n.mappedType === 'agent')

    if (startNodes.length === 0) {
      setError('工作流缺少开始节点，请从左侧面板的"控制节点"区域拖入"开始"节点')
      setSaving(false)
      return
    }
    if (endNodes.length === 0) {
      setError('工作流缺少结束节点，请从左侧面板的"控制节点"区域拖入"结束"节点')
      setSaving(false)
      return
    }

    // 检查循环依赖
    const cycleInfo = detectCycle(nodes, edges)
    if (cycleInfo) {
      setError(`工作流存在循环依赖: ${cycleInfo}，请删除形成环路的连接`)
      setSaving(false)
      return
    }

    // 检查 Agent 节点是否有 agent_type
    const missingAgentType = agentNodes.find((n) => !n.data.agent_type)
    if (missingAgentType) {
      setError(`Agent节点 "${missingAgentType.data.label || '未命名'}" 缺少 agent_type，请选择具体的 Agent 类型`)
      setSaving(false)
      return
    }

    try {
      const workflowNodes: WfNode[] = mappedNodes.map((node) => ({
        id: node.id,
        node_type: node.mappedType as any,  // 使用映射后的类型
        label: node.data.label || '节点',
        agent_type: node.data.agent_type,
        config: node.data.config || {},
        // 包含输入输出配置
        inputs: node.data.inputs || [],
        outputs: node.data.outputs || [],
        position: node.position,
      }))

      // 过滤掉引用不存在节点的边
      const nodeIds = new Set(workflowNodes.map(n => n.id))

      // 调试日志：输出节点和边的信息
      console.log('=== 保存调试 ===')
      console.log('节点 IDs:', Array.from(nodeIds))
      console.log('原始边:', edges.map(e => ({ id: e.id, source: e.source, target: e.target })))

      // 检查哪些边会被过滤掉
      const filteredOutEdges = edges.filter((edge) => !nodeIds.has(edge.source) || !nodeIds.has(edge.target))
      if (filteredOutEdges.length > 0) {
        console.warn('将被过滤掉的边（引用了不存在的节点）:', filteredOutEdges.map(e => ({
          id: e.id,
          source: e.source,
          target: e.target,
          sourceExists: nodeIds.has(e.source),
          targetExists: nodeIds.has(e.target),
        })))
      }

      const workflowEdges: WfEdge[] = edges
        .filter((edge) => nodeIds.has(edge.source) && nodeIds.has(edge.target))
        .map((edge, index) => ({
          id: edge.id || `edge_${index}`,
          source: edge.source,
          target: edge.target,
          condition: (edge as any).condition || undefined,
        }))

      console.log('过滤后的边:', workflowEdges.map(e => ({ id: e.id, source: e.source, target: e.target })))
      console.log('=== 调试结束 ===')

      // 如果工作流已存在，使用更新接口；否则创建新工作流
      if (workflow?.id) {
        const result = await updateWorkflow(workflow.id, {
          name: workflowName,
          nodes: workflowNodes,
          edges: workflowEdges,
        })
        onWorkflowSave?.(result.workflow)
      } else {
        const result = await createWorkflow({
          project_id: projectId,
          name: workflowName,
          nodes: workflowNodes,
          edges: workflowEdges,
        })
        onWorkflowSave?.(result.workflow)
      }
    } catch (err: any) {
      const errorMsg = err?.response?.data?.detail || err?.message || '保存失败'
      setError(errorMsg)
      console.error(err)
    } finally {
      setSaving(false)
    }
  }

  // 执行工作流
  const handleExecute = async () => {
    if (!workflow?.id && !executionId) {
      setError('请先保存工作流')
      return
    }

    setExecuting(true)
    setError(null)

    try {
      const result = await executeWorkflow(workflow?.id || '', projectId)
      setExecutionId(result.execution_id)
      onExecutionStart?.(result.execution_id)
    } catch (err) {
      setError('执行失败')
      console.error(err)
    } finally {
      setExecuting(false)
    }
  }

  // 删除选中节点或边
  const handleDeleteSelected = () => {
    if (selectedNode) {
      setNodes((nds) => nds.filter((n) => n.id !== selectedNode.id))
      setEdges((eds) => eds.filter((e) => e.source !== selectedNode.id && e.target !== selectedNode.id))
      setSelectedNode(null)
    }
    if (selectedEdge) {
      setEdges((eds) => eds.filter((e) => e.id !== selectedEdge.id))
      setSelectedEdge(null)
    }
  }

  // 更新节点属性
  const handleUpdateNode = useCallback((nodeId: string, updates: any) => {
    setNodes((nds) =>
      nds.map((node) => {
        if (node.id === nodeId) {
          return {
            ...node,
            data: { ...node.data, ...updates },
          }
        }
        return node
      }),
    )
  }, [])

  // 更新边属性
  const handleUpdateEdge = useCallback((edgeId: string, updates: any) => {
    setEdges((eds) =>
      eds.map((edge) => {
        if (edge.id === edgeId) {
          return {
            ...edge,
            ...updates,
            data: { ...edge.data, ...updates },
          }
        }
        return edge
      }),
    )
  }, [])

  return (
    <div className="h-full flex">
      {/* 节点面板 */}
      <NodePanel />

      {/* 画布区域 */}
      <div className="flex-1 flex flex-col">
        {/* 工具栏 */}
        <div
          className={`
            flex items-center gap-2 px-4 py-2 border-b
            ${isDark ? 'bg-gray-900 border-gray-700' : 'bg-white border-gray-200'}
          `}
        >
          <input
            type="text"
            value={workflowName}
            onChange={(e) => setWorkflowName(e.target.value)}
            className={`
              px-3 py-1.5 rounded border text-sm font-medium
              ${isDark
                ? 'bg-gray-800 border-gray-600 text-white'
                : 'bg-gray-50 border-gray-300'
              }
            `}
          />

          <div className="flex-1" />

          <button
            onClick={handleSave}
            disabled={saving}
            className="flex items-center gap-1 px-3 py-1.5 bg-blue-500 text-white rounded text-sm hover:bg-blue-600 disabled:opacity-50"
          >
            <Save size={14} />
            {saving ? '保存中...' : '保存'}
          </button>

          <button
            onClick={handleExecute}
            disabled={executing || !workflow?.id}
            className="flex items-center gap-1 px-3 py-1.5 bg-green-500 text-white rounded text-sm hover:bg-green-600 disabled:opacity-50"
          >
            <Play size={14} />
            执行
          </button>

          <button
            onClick={handleDeleteSelected}
            disabled={!selectedNode && !selectedEdge}
            className="p-1.5 rounded hover:bg-gray-100 dark:hover:bg-gray-800 disabled:opacity-50"
            title="删除选中"
          >
            <Trash2 size={16} />
          </button>
        </div>

        {/* 错误提示 */}
        {error && (
          <div className="px-4 py-2 bg-red-50 border-b border-red-100 flex items-center gap-2 text-sm text-red-600">
            <AlertCircle size={14} />
            {error}
          </div>
        )}

        {/* ReactFlow 画布 */}
        <div ref={reactFlowWrapper} className="flex-1">
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onConnect={onConnect}
            onDragOver={onDragOver}
            onDrop={onDrop}
            onNodeClick={onNodeClick}
            onEdgeClick={onEdgeClick}
            onPaneClick={onPaneClick}
            nodeTypes={nodeTypes}
            fitView
            className={isDark ? 'bg-gray-950' : 'bg-gray-50'}
          >
            <MiniMap
              nodeColor={(node) => {
                if (node.type === 'agent') return '#3b82f6'
                if (node.type === 'condition') return '#f59e0b'
                if (node.type === 'parallel') return '#8b5cf6'
                return '#6b7280'
              }}
              className={isDark ? 'bg-gray-800' : 'bg-white'}
            />
            <Controls className={isDark ? 'bg-gray-800' : 'bg-white'} />
            <Background color={isDark ? '#374151' : '#e5e7eb'} gap={16} />
          </ReactFlow>
        </div>
      </div>

      {/* 属性面板 */}
      <PropertyPanel
        node={
          selectedNode
            ? {
                id: selectedNode.id,
                node_type: selectedNode.type as any,
                label: selectedNode.data.label || '',
                agent_type: selectedNode.data.agent_type,
                config: selectedNode.data.config || {},
                position: selectedNode.position,
              }
            : null
        }
        edge={
          selectedEdge
            ? {
                id: selectedEdge.id,
                source: selectedEdge.source,
                target: selectedEdge.target,
                condition: (selectedEdge as any).condition,
              }
            : null
        }
        onClose={() => {
          setSelectedNode(null)
          setSelectedEdge(null)
        }}
        onUpdateNode={handleUpdateNode}
        onUpdateEdge={handleUpdateEdge}
      />
    </div>
  )
}
