import { useEffect, useMemo, useState, useCallback } from 'react'
import { Card } from '@/components/ui'
import PageLayout from '@/components/PageLayout'
import ReactFlow, { Background, Controls, MiniMap, addEdge, applyNodeChanges, applyEdgeChanges, type Node, type Edge, type OnNodesChange, type OnEdgesChange, type Connection, type NodeTypes, Panel, Handle, Position } from 'reactflow'
import 'reactflow/dist/style.css'
import { getVisualizationData } from '@/api/visualization'
import { getWorlds, type World } from '@/api/worlds'
import {
  getWorkflows,
  createWorkflow,
  updateWorkflow,
  deleteWorkflow,
  executeWorkflow,
  type WorkflowDefinition,
  type WorkflowNode as WfNode,
  type WorkflowEdge as WfEdge,
} from '@/api/workflows'
import { Network, Users, GitBranch, Play, Pause, Save, Trash2, Plus } from 'lucide-react'
import { useTheme } from '@/contexts/ThemeContext'
import { useProject } from '@/contexts/ProjectContext'

// 自定义节点组件 - 带连接点
function AgentNode({ data }: { data: any }) {
  const { theme } = useTheme()
  const isDark = theme === 'dark'
  const status = data.status || 'pending'

  const statusColors: Record<string, string> = {
    pending: isDark ? 'bg-gray-700 border-gray-600' : 'bg-gray-100 border-gray-300',
    running: 'bg-blue-100 border-blue-400 animate-pulse',
    completed: 'bg-green-100 border-green-400',
    failed: 'bg-red-100 border-red-400',
  }

  return (
    <div className={`px-4 py-3 rounded-lg border-2 min-w-[120px] ${statusColors[status]}`}>
      <Handle type="target" position={Position.Top} className="!bg-gray-400 !w-3 !h-3" />
      <div className="font-medium text-sm">{data.label}</div>
      {data.agent_type && <div className="text-xs opacity-70">{data.agent_type}</div>}
      <Handle type="source" position={Position.Bottom} className="!bg-gray-400 !w-3 !h-3" />
    </div>
  )
}

// 条件分支节点组件 - 带连接点
function ConditionNode({ data }: { data: any }) {
  return (
    <div className="px-4 py-3 rounded-lg border-2 border-orange-400 bg-orange-50 min-w-[150px]">
      {/* 顶部：输入连接点 */}
      <Handle type="target" position={Position.Top} className="!bg-orange-400 !w-3 !h-3" />
      <div className="font-medium text-sm">🔀 条件判断</div>
      <div className="text-xs opacity-70">{data.label || '评估结果'}</div>
      <div className="flex justify-between text-xs mt-1 px-1">
        <span className="text-green-600">✓ 通过</span>
        <span className="text-red-600">✗ 重试</span>
      </div>
      {/* 左侧：通过连接点 */}
      <Handle type="source" position={Position.Left} id="pass" className="!bg-green-500 !w-3 !h-3" />
      {/* 右侧：重试连接点 */}
      <Handle type="source" position={Position.Right} id="retry" className="!bg-red-500 !w-3 !h-3" />
    </div>
  )
}

// 集体讨论节点组件
function GroupDiscussionNode({ data }: { data: any }) {
  return (
    <div className="px-4 py-3 rounded-lg border-2 border-purple-400 bg-purple-50 min-w-[150px]">
      <Handle type="target" position={Position.Top} className="!bg-purple-400 !w-3 !h-3" />
      <div className="font-medium text-sm">🌟 集体讨论</div>
      <div className="text-xs opacity-70">{data.label || '所有角色剧情讨论'}</div>
      <div className="text-xs text-purple-600 mt-1">评估通过后触发</div>
      <Handle type="source" position={Position.Bottom} className="!bg-purple-400 !w-3 !h-3" />
    </div>
  )
}

// 开始节点组件 - 支持循环回到开始
function StartNode({ data }: { data: any }) {
  return (
    <div className="px-4 py-3 rounded-lg border-2 border-green-500 bg-green-50 min-w-[100px]">
      {/* 顶部：循环输入连接点（retry 可以连回来） */}
      <Handle type="target" position={Position.Top} id="loop" className="!bg-green-400 !w-3 !h-3" />
      <div className="font-medium text-sm text-center">▶️ {data.label || '开始'}</div>
      {/* 底部：输出连接点 */}
      <Handle type="source" position={Position.Bottom} className="!bg-green-500 !w-3 !h-3" />
    </div>
  )
}

// 结束节点组件
function EndNode({ data }: { data: any }) {
  return (
    <div className="px-4 py-3 rounded-lg border-2 border-red-500 bg-red-50 min-w-[100px]">
      <Handle type="target" position={Position.Top} className="!bg-red-400 !w-3 !h-3" />
      <div className="font-medium text-sm text-center">⏹️ {data.label || '结束'}</div>
    </div>
  )
}

const nodeTypes: NodeTypes = {
  agent: AgentNode,
  condition: ConditionNode,
  group_discussion: GroupDiscussionNode,
  start: StartNode,
  end: EndNode,
}

type TabType = 'workflow' | 'plots' | 'snapshots'

// Agent 类型选项
const AGENT_TYPES = [
  { type: 'setting', label: '设定 Agent' },
  { type: 'writer', label: '作家 Agent' },
  { type: 'plotter', label: '编剧 Agent' },
  { type: 'character', label: '角色 Agent' },
  { type: 'summarizer', label: '摘要 Agent' },
  { type: 'evaluator', label: '评估 Agent' },
  { type: 'hook_manager', label: '伏笔 Agent' },
  { type: 'event_generator', label: '事件 Agent' },
  { type: 'world_map_manager', label: '地图 Agent' },
]

// 节点类型选项
const NODE_TYPES = [
  { type: 'agent', label: 'Agent 节点' },
  { type: 'condition', label: '条件分支' },
  { type: 'group_discussion', label: '集体讨论' },
]

const generateId = () => `node_${Date.now()}_${Math.random().toString(36).slice(2, 9)}`

export default function Visualizer() {
  const { theme } = useTheme()
  const isDark = theme === 'dark'
  const { currentProject } = useProject()

  const [activeTab, setActiveTab] = useState<TabType>('workflow')
  const [data, setData] = useState<any>(null)
  const [worlds, setWorlds] = useState<World[]>([])
  const [selectedWorldId, setSelectedWorldId] = useState('')

  // 工作流相关状态
  const [workflows, setWorkflows] = useState<WorkflowDefinition[]>([])
  const [selectedWorkflow, setSelectedWorkflow] = useState<WorkflowDefinition | null>(null)
  const [nodes, setNodes] = useState<Node[]>([])
  const [edges, setEdges] = useState<Edge[]>([])
  const [workflowName, setWorkflowName] = useState('新工作流')
  const [saving, setSaving] = useState(false)
  const [executing, setExecuting] = useState(false)

  useEffect(() => {
    loadWorlds()
  }, [])

  useEffect(() => {
    if (currentProject) {
      loadWorkflows()
    }
  }, [currentProject])

  useEffect(() => {
    if (!selectedWorldId) return
    loadData(selectedWorldId)
  }, [selectedWorldId])

  // 键盘事件：Delete/Backspace 删除选中节点
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Delete' || e.key === 'Backspace') {
        // 检查是否在输入框中
        const target = e.target as HTMLElement
        if (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA') return

        // 删除选中的节点和边
        setNodes((nds) => nds.filter((node) => !node.selected))
        setEdges((eds) => eds.filter((edge) => !edge.selected))
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [setNodes, setEdges])

  const loadWorlds = async () => {
    try {
      const result = await getWorlds()
      setWorlds(result)
      setSelectedWorldId((current) => current || result[0]?.id || '')
    } catch (error) {
      console.error('Failed to load worlds:', error)
    }
  }

  const loadWorkflows = async () => {
    if (!currentProject) return
    try {
      const result = await getWorkflows(currentProject.id, true)
      setWorkflows(result)
    } catch (error) {
      console.error('Failed to load workflows:', error)
    }
  }

  const loadData = async (worldId: string) => {
    try {
      const result = await getVisualizationData(worldId)
      setData(result)
    } catch (error) {
      console.error('Failed to load visualization data:', error)
    }
  }

  // 工作流节点变化处理
  const onNodesChange: OnNodesChange = useCallback((changes) => {
    setNodes((nds) => applyNodeChanges(changes, nds))
  }, [])

  const onEdgesChange: OnEdgesChange = useCallback((changes) => {
    setEdges((eds) => applyEdgeChanges(changes, eds))
  }, [])

  const onConnect = useCallback((connection: Connection) => {
    setEdges((eds) => addEdge({ ...connection, animated: true }, eds))
  }, [])

  // 选择工作流
  const handleSelectWorkflow = (workflow: WorkflowDefinition) => {
    setSelectedWorkflow(workflow)
    setWorkflowName(workflow.name)
    const flowNodes = workflow.nodes.map((node) => {
      // 确定节点类型
      let nodeType = 'agent'
      if (node.node_type === 'agent') nodeType = 'agent'
      else if (node.node_type === 'condition') nodeType = 'condition'
      else if (node.node_type === 'group_discussion') nodeType = 'group_discussion'
      else if (node.node_type === 'start') nodeType = 'start'
      else if (node.node_type === 'end') nodeType = 'end'

      return {
        id: node.id,
        type: nodeType,
        position: node.position,
        data: {
          label: node.label,
          agent_type: node.agent_type,
          config: node.config,
        },
      }
    })
    // 恢复边，包括 sourceHandle（从 condition 恢复）
    const flowEdges = workflow.edges.map((edge) => {
      // 从 condition 恢复 sourceHandle
      let sourceHandle: string | undefined
      if (edge.condition?.result === 'pass') {
        sourceHandle = 'pass'
      } else if (edge.condition?.result === 'retry') {
        sourceHandle = 'retry'
      }

      return {
        id: edge.id,
        source: edge.source,
        target: edge.target,
        sourceHandle,
        animated: true,
        // 保存样式以区分 pass 和 retry 边
        style: sourceHandle === 'pass'
          ? { stroke: '#22c55e', strokeWidth: 2 }
          : sourceHandle === 'retry'
            ? { stroke: '#ef4444', strokeWidth: 2 }
            : undefined,
      }
    })
    setNodes(flowNodes)
    setEdges(flowEdges)
  }

  // 创建新工作流
  const handleNewWorkflow = () => {
    setSelectedWorkflow(null)
    setWorkflowName('新工作流')
    setNodes([
      {
        id: 'start',
        type: 'start',
        position: { x: 250, y: 50 },
        data: { label: '开始' },
      },
      {
        id: 'end',
        type: 'end',
        position: { x: 250, y: 400 },
        data: { label: '结束' },
      },
    ])
    setEdges([])
  }

  // 添加 Agent 节点
  const handleAddAgentNode = (agentType: string, label: string) => {
    const newNode: Node = {
      id: generateId(),
      type: 'agent',
      position: { x: 100 + Math.random() * 300, y: 150 + nodes.length * 80 },
      data: { label, agent_type: agentType },
    }
    setNodes((nds) => [...nds, newNode])
  }

  // 添加条件节点
  const handleAddConditionNode = (label: string) => {
    const newNode: Node = {
      id: generateId(),
      type: 'condition',
      position: { x: 100 + Math.random() * 300, y: 150 + nodes.length * 80 },
      data: { label },
    }
    setNodes((nds) => [...nds, newNode])
  }

  // 添加集体讨论节点
  const handleAddGroupDiscussionNode = (label: string) => {
    const newNode: Node = {
      id: generateId(),
      type: 'group_discussion',
      position: { x: 100 + Math.random() * 300, y: 150 + nodes.length * 80 },
      data: { label },
    }
    setNodes((nds) => [...nds, newNode])
  }

  // 保存工作流 - 更新或新建
  const handleSaveWorkflow = async () => {
    if (!currentProject) return
    setSaving(true)
    try {
      // 类型映射函数
      const mapNodeType = (type: string | undefined): string => {
        const typeMap: Record<string, string> = {
          'agent': 'agent',
          'condition': 'condition',
          'group_discussion': 'group_discussion',
          'parallel': 'parallel',
          'input': 'start',      // ReactFlow input 映射为 start
          'output': 'end',       // ReactFlow output 映射为 end
          'start': 'start',      // 直接是 start
          'end': 'end',          // 直接是 end
        }
        return typeMap[type || ''] || 'agent'
      }

      // 检测循环依赖
      const detectCycle = (): string | null => {
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
              return cyclePath.join(' → ')
            }
          }
        }
        return null
      }

      // 检查是否是合法的 retry 循环（边连接回 start 节点）
      const isValidRetryLoop = (): boolean => {
        // 检查是否有边回到 start 节点
        const hasEdgeToStart = edges.some((edge) => edge.target === 'start')
        if (hasEdgeToStart) return true

        // 检查是否有带 retry 条件的边
        const hasRetryEdge = edges.some((edge) => edge.condition?.result === 'retry')
        if (hasRetryEdge) return true

        return false
      }

      // 检查循环依赖
      const cycleInfo = detectCycle()
      if (cycleInfo && !isValidRetryLoop()) {
        alert(`工作流存在意外的循环依赖：${cycleInfo}\n\n请删除形成环路的连接线。\n\n提示：如果需要创建重试循环，请将条件节点的连接线指向"开始"节点。`)
        setSaving(false)
        return
      }

      const workflowNodes: WfNode[] = nodes.map((node) => ({
        id: node.id,
        node_type: mapNodeType(node.type) as any,
        label: node.data.label || '节点',
        agent_type: node.data.agent_type,
        config: node.data.config || {},
        position: node.position,
      }))
      const workflowEdges: WfEdge[] = edges.map((edge, index) => {
        // 确定边的条件 - 基于连接点ID
        let condition: { result: string } | undefined
        if (edge.sourceHandle === 'pass') {
          condition = { result: 'pass' }
        } else if (edge.sourceHandle === 'retry') {
          condition = { result: 'retry' }
        } else if (edge.sourceHandle === 'loop') {
          condition = { result: 'retry' }
        }

        return {
          id: edge.id || `edge_${index}`,
          source: edge.source,
          target: edge.target,
          condition,
        }
      })

      if (selectedWorkflow) {
        // 更新现有工作流
        await updateWorkflow(selectedWorkflow.id, {
          name: workflowName,
          nodes: workflowNodes,
          edges: workflowEdges,
        })
        alert('工作流更新成功！')
      } else {
        // 创建新工作流
        const result = await createWorkflow({
          project_id: currentProject.id,
          name: workflowName,
          nodes: workflowNodes,
          edges: workflowEdges,
        })
        alert('工作流创建成功！')
      }

      await loadWorkflows()
    } catch (error) {
      console.error('Failed to save workflow:', error)
      alert('保存失败')
    } finally {
      setSaving(false)
    }
  }

  // 执行工作流
  const handleExecuteWorkflow = async () => {
    if (!selectedWorkflow || !currentProject) return
    setExecuting(true)
    try {
      const result = await executeWorkflow(selectedWorkflow.id, currentProject.id)
      alert(`工作流已启动！执行ID: ${result.execution_id}`)
    } catch (error) {
      console.error('Failed to execute workflow:', error)
      alert('执行失败')
    } finally {
      setExecuting(false)
    }
  }

  // 删除工作流
  const handleDeleteWorkflow = async (workflow: WorkflowDefinition, e: React.MouseEvent) => {
    e.stopPropagation()
    if (!confirm(`确定要删除工作流 "${workflow.name}" 吗？`)) return
    try {
      await deleteWorkflow(workflow.id)
      if (selectedWorkflow?.id === workflow.id) {
        setSelectedWorkflow(null)
        setNodes([])
        setEdges([])
        setWorkflowName('新工作流')
      }
      await loadWorkflows()
    } catch (error) {
      console.error('Failed to delete workflow:', error)
      alert('删除失败')
    }
  }

  // 删除选中的节点
  const handleDeleteSelectedNodes = useCallback(() => {
    setNodes((nds) => nds.filter((node) => !node.selected))
    setEdges((eds) => eds.filter((edge) => !edge.selected))
  }, [])

  const currentWorld = useMemo(
    () => worlds.find((world) => world.id === selectedWorldId) || null,
    [worlds, selectedWorldId],
  )

  const plotNodes = (data?.plot_tree?.nodes || []).map((node: any, index: number) => ({
    id: node.id,
    position: { x: 160 + index * 180, y: 180 + (index % 2) * 120 },
    data: { label: node.label },
    style: { padding: 10, borderRadius: 10, background: '#fef3c7', border: '1px solid #f59e0b' },
  }))
  const plotEdges = (data?.plot_tree?.edges || []).map((edge: any, index: number) => ({
    id: `plot-${index}`,
    source: edge.source,
    target: edge.target,
  }))

  const snapshotNodes = (data?.snapshot_tree?.nodes || []).map((node: any, index: number) => ({
    id: node.id,
    position: { x: 160 + index * 180, y: 180 + (index % 3) * 100 },
    data: { label: node.label },
    style: {
      padding: 10,
      borderRadius: 10,
      background: node.is_branch ? '#f5d0fe' : '#ede9fe',
      border: '1px solid #a78bfa',
    },
  }))
  const snapshotEdges = (data?.snapshot_tree?.edges || []).map((edge: any, index: number) => ({
    id: `snap-${index}`,
    source: edge.source,
    target: edge.target,
  }))

  const tabs = [
    { key: 'workflow', label: '工作流', icon: <Network size={18} /> },
    { key: 'plots', label: '剧情树', icon: <Users size={18} /> },
    { key: 'snapshots', label: '版本树', icon: <GitBranch size={18} /> },
  ]

  return (
    <PageLayout
      title="可视化工作台"
      description="可视化展示工作流、剧情树和版本树"
      actions={
        <div className="flex items-center gap-4">
          {activeTab === 'workflow' && (
            <>
              <input
                type="text"
                value={workflowName}
                onChange={(e) => setWorkflowName(e.target.value)}
                className={`px-3 py-1.5 rounded border text-sm ${
                  isDark ? 'bg-gray-800 border-gray-600 text-white' : 'bg-white border-gray-300'
                }`}
                placeholder="工作流名称"
              />
              <button
                onClick={handleSaveWorkflow}
                disabled={saving || !currentProject}
                className="flex items-center gap-1 px-3 py-1.5 bg-blue-500 text-white rounded text-sm hover:bg-blue-600 disabled:opacity-50"
              >
                <Save size={14} />
                {saving ? '保存中...' : '保存'}
              </button>
            </>
          )}
          <div className="w-48">
            <label className={`block text-sm font-medium mb-1 ${isDark ? 'text-gray-300' : 'text-gray-700'}`}>世界</label>
            <select
              className={`w-full px-3 py-2 border rounded-lg ${isDark ? 'bg-gray-800 border-gray-600 text-white' : 'bg-white border-gray-300'}`}
              value={selectedWorldId}
              onChange={(e) => setSelectedWorldId(e.target.value)}
            >
              <option value="">选择世界...</option>
              {worlds.map((world) => (
                <option key={world.id} value={world.id}>{world.name || world.id}</option>
              ))}
            </select>
          </div>
        </div>
      }
    >
      {/* Tab 切换 */}
      <div className="mb-4 flex gap-4">
        {tabs.map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key as TabType)}
            className={`px-4 py-2 rounded-lg font-medium transition-colors ${
              activeTab === tab.key
                ? 'bg-blue-500 text-white'
                : isDark
                  ? 'bg-gray-800 text-gray-300 hover:bg-gray-700'
                  : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
            }`}
          >
            <span className="inline mr-2">{tab.icon}</span>
            {tab.label}
          </button>
        ))}
      </div>

      {activeTab === 'workflow' ? (
        <div className="flex gap-4" style={{ height: 'calc(100vh - 280px)', minHeight: '500px' }}>
          {/* 左侧：工作流列表和节点面板 - 改为更宽敞的两列布局 */}
          <div className="w-80 flex flex-col gap-3">
            {/* 已保存的工作流 - 放在顶部可折叠 */}
            <Card className="p-3">
              <div className="flex items-center justify-between mb-2">
                <h3 className={`text-sm font-semibold ${isDark ? 'text-gray-200' : 'text-gray-700'}`}>
                  工作流
                </h3>
                <button
                  onClick={handleNewWorkflow}
                  className="flex items-center gap-1 px-2 py-1 bg-green-500 text-white rounded text-xs hover:bg-green-600"
                >
                  <Plus size={12} /> 新建
                </button>
              </div>
              <div className="space-y-1 max-h-32 overflow-y-auto">
                {workflows.length === 0 ? (
                  <p className={`text-xs ${isDark ? 'text-gray-500' : 'text-gray-400'}`}>暂无</p>
                ) : (
                  workflows.map((wf) => (
                    <div
                      key={wf.id}
                      onClick={() => handleSelectWorkflow(wf)}
                      className={`p-1.5 rounded cursor-pointer text-xs flex justify-between items-center ${
                        selectedWorkflow?.id === wf.id
                          ? 'bg-blue-100 text-blue-700'
                          : isDark
                            ? 'bg-gray-700 hover:bg-gray-600 text-gray-300'
                            : 'bg-gray-50 hover:bg-gray-100 text-gray-700'
                      }`}
                    >
                      <span className="truncate flex-1">{wf.name}</span>
                      <button
                        onClick={(e) => handleDeleteWorkflow(wf, e)}
                        className="text-red-500 hover:text-red-700 ml-2"
                        title="删除"
                      >
                        <Trash2 size={10} />
                      </button>
                    </div>
                  ))
                )}
              </div>
            </Card>

            {/* Agent 节点面板 + 流程控制合并为一个更宽敞的面板 */}
            <Card className="p-3 flex-1 overflow-y-auto">
              <h3 className={`text-sm font-semibold mb-2 ${isDark ? 'text-gray-200' : 'text-gray-700'}`}>
                可用节点
              </h3>

              {/* Agent 节点 */}
              <div className="mb-3">
                <p className={`text-xs font-medium mb-2 ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>Agent 节点</p>
                <div className="grid grid-cols-2 gap-1">
                  {AGENT_TYPES.map((agent) => (
                    <button
                      key={agent.type}
                      onClick={() => handleAddAgentNode(agent.type, agent.label)}
                      className={`text-left px-2 py-1.5 rounded text-xs transition-colors truncate ${
                        isDark
                          ? 'bg-gray-700 hover:bg-gray-600 text-gray-300'
                          : 'bg-gray-50 hover:bg-gray-100 text-gray-700'
                      }`}
                      title={agent.label}
                    >
                      {agent.label.replace(' Agent', '')}
                    </button>
                  ))}
                </div>
              </div>

              {/* 流程控制 */}
              <div>
                <p className={`text-xs font-medium mb-2 ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>流程控制</p>
                <div className="grid grid-cols-2 gap-1">
                  {NODE_TYPES.filter(n => n.type === 'condition').map((node) => (
                    <button
                      key={node.type}
                      onClick={() => handleAddConditionNode('条件判断')}
                      className={`text-left px-2 py-1.5 rounded text-xs transition-colors ${
                        isDark
                          ? 'bg-orange-900/50 hover:bg-orange-800/50 text-orange-300'
                          : 'bg-orange-50 hover:bg-orange-100 text-orange-700'
                      }`}
                    >
                      {node.label}
                    </button>
                  ))}
                  {NODE_TYPES.filter(n => n.type === 'group_discussion').map((node) => (
                    <button
                      key={node.type}
                      onClick={() => handleAddGroupDiscussionNode('集体讨论')}
                      className={`text-left px-2 py-1.5 rounded text-xs transition-colors ${
                        isDark
                          ? 'bg-purple-900/50 hover:bg-purple-800/50 text-purple-300'
                          : 'bg-purple-50 hover:bg-purple-100 text-purple-700'
                      }`}
                    >
                      {node.label}
                    </button>
                  ))}
                </div>
              </div>
            </Card>

            {/* 执行控制 */}
            {selectedWorkflow && (
              <Card className="p-3">
                <button
                  onClick={handleExecuteWorkflow}
                  disabled={executing}
                  className="w-full flex items-center justify-center gap-2 px-3 py-2 bg-green-500 text-white rounded text-sm hover:bg-green-600 disabled:opacity-50"
                >
                  <Play size={14} />
                  {executing ? '执行中...' : '执行'}
                </button>
              </Card>
            )}
          </div>

          {/* 右侧：工作流画布 */}
          <div className="flex-1 border-2 border-dashed border-gray-300 rounded-xl overflow-hidden" style={{ height: 'calc(100vh - 280px)', minHeight: '500px' }}>
            {nodes.length === 0 ? (
              <div className="h-full flex flex-col items-center justify-center text-gray-400">
                <Network size={48} className="mb-4 opacity-50" />
                <p className="text-lg mb-2">点击"新建工作流"开始创建</p>
                <p className="text-sm">或从左侧选择一个已保存的工作流</p>
              </div>
            ) : (
            <ReactFlow
              nodes={nodes}
              edges={edges}
              onNodesChange={onNodesChange}
              onEdgesChange={onEdgesChange}
              onConnect={onConnect}
              nodeTypes={nodeTypes}
              fitView
              selectNodesOnDrag={false}
              panOnScroll
              selectionOnDrag
              proOptions={{ hideAttribution: true }}
            >
              <MiniMap />
              <Controls />
              <Background color={isDark ? '#374151' : '#e5e7eb'} gap={16} />
              <Panel position="top-right">
                <div className="flex gap-2">
                  <button
                    onClick={handleDeleteSelectedNodes}
                    className={`px-3 py-1.5 rounded text-sm ${
                      isDark ? 'bg-red-900 text-red-200 hover:bg-red-800' : 'bg-red-100 text-red-700 hover:bg-red-200'
                    }`}
                    title="删除选中节点 (Delete)"
                  >
                    <Trash2 size={14} className="inline mr-1" /> 删除选中
                  </button>
                  <button
                    onClick={() => {
                      // 只保留开始和结束节点，删除其他节点和所有边
                      setNodes((nds) => nds.filter((node) => node.id === 'start' || node.id === 'end'))
                      setEdges([])
                    }}
                    className={`px-3 py-1.5 rounded text-sm ${
                      isDark ? 'bg-gray-800 text-gray-300 hover:bg-gray-700' : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                    }`}
                    title="清空所有节点（保留开始和结束）"
                  >
                    清空
                  </button>
                </div>
              </Panel>
            </ReactFlow>
            )}
          </div>
        </div>
      ) : (
        <Card className="min-h-[600px]">
          {selectedWorldId ? (
            <ReactFlow
              nodes={activeTab === 'plots' ? plotNodes : snapshotNodes}
              edges={activeTab === 'plots' ? plotEdges : snapshotEdges}
              fitView
            >
              <MiniMap zoomable pannable />
              <Controls />
              <Background />
            </ReactFlow>
          ) : (
            <div className={`h-[600px] flex items-center justify-center ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>
              暂无世界数据，请先创建世界
            </div>
          )}
        </Card>
      )}
    </PageLayout>
  )
}
