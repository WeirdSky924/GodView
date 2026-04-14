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
import { getWorkflowNodeTypes, type NodeTypeInfo, type WorkflowNodeTypes } from '@/api/nodeTypes'
import { Network, Users, GitBranch, Play, Pause, Save, Trash2, Plus, Loader2 } from 'lucide-react'
import { useTheme } from '@/contexts/ThemeContext'
import { useProject } from '@/contexts/ProjectContext'
import WorkflowHelp from '@/components/workflow/WorkflowHelp'

// ==================== 自定义节点组件 ====================

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

function ConditionNode({ data }: { data: any }) {
  return (
    <div className="px-4 py-3 rounded-lg border-2 border-orange-400 bg-orange-50 min-w-[150px]">
      <Handle type="target" position={Position.Top} className="!bg-orange-400 !w-3 !h-3" />
      <div className="font-medium text-sm">🔀 条件判断</div>
      <div className="text-xs opacity-70">{data.label || '评估结果'}</div>
      <div className="flex justify-between text-xs mt-1 px-1">
        <span className="text-green-600">✓ 通过</span>
        <span className="text-red-600">✗ 重试</span>
      </div>
      <Handle type="source" position={Position.Left} id="pass" className="!bg-green-500 !w-3 !h-3" />
      <Handle type="source" position={Position.Right} id="retry" className="!bg-red-500 !w-3 !h-3" />
    </div>
  )
}

function ParallelNode({ data }: { data: any }) {
  return (
    <div className="px-4 py-3 rounded-lg border-2 border-purple-400 bg-purple-50 min-w-[120px]">
      <Handle type="target" position={Position.Top} className="!bg-purple-400 !w-3 !h-3" />
      <div className="font-medium text-sm">⚡ 并行执行</div>
      <div className="text-xs opacity-70">{data.label || '同时执行多个分支'}</div>
      <Handle type="source" position={Position.Bottom} className="!bg-purple-400 !w-3 !h-3" />
    </div>
  )
}

function ScenePerformanceNode({ data }: { data: any }) {
  return (
    <div className="px-4 py-3 rounded-lg border-2 border-rose-400 bg-rose-50 min-w-[150px]">
      <Handle type="target" position={Position.Top} className="!bg-rose-400 !w-3 !h-3" />
      <div className="font-medium text-sm">🎭 场景演绎</div>
      <div className="text-xs opacity-70">{data.label || '多角色同台表演'}</div>
      <div className="text-xs text-rose-600 mt-1">自动协调角色Agent</div>
      <Handle type="source" position={Position.Bottom} className="!bg-rose-400 !w-3 !h-3" />
    </div>
  )
}

function GroupDiscussionNode({ data }: { data: any }) {
  return (
    <div className="px-4 py-3 rounded-lg border-2 border-indigo-400 bg-indigo-50 min-w-[150px]">
      <Handle type="target" position={Position.Top} className="!bg-indigo-400 !w-3 !h-3" />
      <div className="font-medium text-sm">💬 集体讨论</div>
      <div className="text-xs opacity-70">{data.label || '多Agent讨论'}</div>
      <Handle type="source" position={Position.Bottom} className="!bg-indigo-400 !w-3 !h-3" />
    </div>
  )
}

function StartNode({ data }: { data: any }) {
  return (
    <div className="px-4 py-3 rounded-lg border-2 border-green-500 bg-green-50 min-w-[100px]">
      <Handle type="target" position={Position.Top} id="loop" className="!bg-green-400 !w-3 !h-3" />
      <div className="font-medium text-sm text-center">▶️ {data.label || '开始'}</div>
      <Handle type="source" position={Position.Bottom} className="!bg-green-500 !w-3 !h-3" />
    </div>
  )
}

function EndNode({ data }: { data: any }) {
  return (
    <div className="px-4 py-3 rounded-lg border-2 border-red-500 bg-red-50 min-w-[100px]">
      <Handle type="target" position={Position.Top} className="!bg-red-400 !w-3 !h-3" />
      <div className="font-medium text-sm text-center">⏹️ {data.label || '结束'}</div>
    </div>
  )
}

function InputNode({ data }: { data: any }) {
  return (
    <div className="px-4 py-3 rounded-lg border-2 border-blue-400 bg-blue-50 min-w-[120px]">
      <Handle type="target" position={Position.Top} className="!bg-blue-400 !w-3 !h-3" />
      <div className="font-medium text-sm">📝 用户输入</div>
      <div className="text-xs opacity-70">{data.label || '等待用户输入'}</div>
      <Handle type="source" position={Position.Bottom} className="!bg-blue-400 !w-3 !h-3" />
    </div>
  )
}

const nodeTypes: NodeTypes = {
  agent: AgentNode,
  condition: ConditionNode,
  parallel: ParallelNode,
  scene_performance: ScenePerformanceNode,
  group_discussion: GroupDiscussionNode,
  start: StartNode,
  end: EndNode,
  input: InputNode,
}

type TabType = 'workflow' | 'plots' | 'snapshots'

const generateId = () => `node_${Date.now()}_${Math.random().toString(36).slice(2, 9)}`

export default function Visualizer() {
  const { theme } = useTheme()
  const isDark = theme === 'dark'
  const { currentProject } = useProject()

  const [activeTab, setActiveTab] = useState<TabType>('workflow')
  const [data, setData] = useState<any>(null)
  const [worlds, setWorlds] = useState<World[]>([])
  const [selectedWorldId, setSelectedWorldId] = useState('')

  // 动态节点类型
  const [nodeTypesData, setNodeTypesData] = useState<WorkflowNodeTypes>({
    agent_nodes: [],
    interaction_nodes: [],
    control_nodes: [],
    character_nodes: [],
  })
  const [loadingNodeTypes, setLoadingNodeTypes] = useState(true)

  // 工作流相关状态
  const [workflows, setWorkflows] = useState<WorkflowDefinition[]>([])
  const [selectedWorkflow, setSelectedWorkflow] = useState<WorkflowDefinition | null>(null)
  const [nodes, setNodes] = useState<Node[]>([])
  const [edges, setEdges] = useState<Edge[]>([])
  const [workflowName, setWorkflowName] = useState('新工作流')
  const [saving, setSaving] = useState(false)
  const [executing, setExecuting] = useState(false)

  // 加载节点类型
  useEffect(() => {
    loadNodeTypes()
  }, [currentProject])

  const loadNodeTypes = async () => {
    setLoadingNodeTypes(true)
    try {
      const result = await getWorkflowNodeTypes(currentProject?.id)
      setNodeTypesData(result)
    } catch (error) {
      console.error('[Visualizer] Failed to load node types:', error)
    } finally {
      setLoadingNodeTypes(false)
    }
  }

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
        const target = e.target as HTMLElement
        if (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA') return
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
      return {
        id: node.id,
        type: node.node_type,
        position: node.position,
        data: {
          label: node.label,
          agent_type: node.agent_type,
          config: node.config,
        },
      }
    })
    const flowEdges = workflow.edges.map((edge) => {
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
      { id: 'start', type: 'start', position: { x: 250, y: 50 }, data: { label: '开始' } },
      { id: 'end', type: 'end', position: { x: 250, y: 400 }, data: { label: '结束' } },
    ])
    setEdges([])
  }

  // 添加节点
  const handleAddNode = (nodeInfo: NodeTypeInfo) => {
    const nodeType = nodeInfo.type
    const newNode: Node = {
      id: generateId(),
      type: nodeType,
      position: { x: 100 + Math.random() * 300, y: 150 + nodes.length * 80 },
      data: {
        label: nodeInfo.label,
        agent_type: nodeInfo.agent_type,
      },
    }
    setNodes((nds) => [...nds, newNode])
  }

  // 保存工作流
  const handleSaveWorkflow = async () => {
    if (!currentProject) return
    setSaving(true)
    try {
      const workflowNodes: WfNode[] = nodes.map((node) => ({
        id: node.id,
        node_type: node.type as any,
        label: node.data.label || '节点',
        agent_type: node.data.agent_type,
        config: node.data.config || {},
        position: node.position,
      }))
      const workflowEdges: WfEdge[] = edges.map((edge, index) => {
        let condition: { result: string } | undefined
        if (edge.sourceHandle === 'pass') condition = { result: 'pass' }
        else if (edge.sourceHandle === 'retry') condition = { result: 'retry' }
        else if (edge.sourceHandle === 'loop') condition = { result: 'retry' }
        return {
          id: edge.id || `edge_${index}`,
          source: edge.source,
          target: edge.target,
          condition,
        }
      })

      if (selectedWorkflow) {
        await updateWorkflow(selectedWorkflow.id, {
          name: workflowName,
          nodes: workflowNodes,
          edges: workflowEdges,
        })
        alert('工作流更新成功！')
      } else {
        await createWorkflow({
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
      tabs={tabs}
      activeTab={activeTab}
      onTabChange={(key) => setActiveTab(key as TabType)}
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
              <WorkflowHelp />
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
      {activeTab === 'workflow' ? (
        <div className="flex gap-4" style={{ height: 'calc(100vh - 280px)', minHeight: '500px' }}>
          {/* 左侧面板 */}
          <div className="w-80 flex flex-col gap-3">
            {/* 工作流列表 */}
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

            {/* 动态节点面板 */}
            <Card className="p-3 flex-1 overflow-y-auto">
              {loadingNodeTypes ? (
                <div className="flex items-center justify-center h-32">
                  <Loader2 size={24} className="animate-spin text-blue-500" />
                </div>
              ) : (
                <>
                  <h3 className={`text-sm font-semibold mb-2 ${isDark ? 'text-gray-200' : 'text-gray-700'}`}>
                    可用节点
                  </h3>

                  {/* Agent 节点 */}
                  <div className="mb-3">
                    <p className={`text-xs font-medium mb-2 ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>
                      🤖 系统 Agent
                    </p>
                    <div className="grid grid-cols-2 gap-1">
                      {nodeTypesData.agent_nodes.map((node) => (
                        <button
                          key={node.agent_type || node.type}
                          onClick={() => handleAddNode(node)}
                          className={`text-left px-2 py-1.5 rounded text-xs transition-colors truncate ${
                            isDark
                              ? 'bg-gray-700 hover:bg-gray-600 text-gray-300'
                              : 'bg-gray-50 hover:bg-gray-100 text-gray-700'
                          }`}
                          title={node.label}
                        >
			
                         {node.label.replace(' Agent', '').replace('管理员', '')}
                        </button>
                      ))}
                    </div>
                  </div>

                  {/* 角色 Agent */}
                  {nodeTypesData.character_nodes.length > 0 && (
                    <div className="mb-3">
                      <p className={`text-xs font-medium mb-2 ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>
                        👤 角色 Agent
                      </p>
                      <div className="grid grid-cols-2 gap-1">
                        {nodeTypesData.character_nodes.map((node) => (
                          <button
                            key={node.character_id}
                            onClick={() => handleAddNode(node)}
                            className={`text-left px-2 py-1.5 rounded text-xs transition-colors truncate ${
                              isDark
                                ? 'bg-orange-900/50 hover:bg-orange-800/50 text-orange-300'
                                : 'bg-orange-50 hover:bg-orange-100 text-orange-700'
                            }`}
                            title={node.label}
                          >
                            {node.character_name}
                          </button>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* 交互节点 */}
                  <div className="mb-3">
                    <p className={`text-xs font-medium mb-2 ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>
                      💬 交互节点
                    </p>
                    <div className="grid grid-cols-2 gap-1">
                      {nodeTypesData.interaction_nodes.map((node) => (
                        <button
                          key={node.type}
                          onClick={() => handleAddNode(node)}
                          className={`text-left px-2 py-1.5 rounded text-xs transition-colors truncate ${
                            isDark
                              ? 'bg-rose-900/50 hover:bg-rose-800/50 text-rose-300'
                              : 'bg-rose-50 hover:bg-rose-100 text-rose-700'
                          }`}
                          title={node.label}
                        >
                          {node.label}
                        </button>
                      ))}
                    </div>
                  </div>

                  {/* 控制节点 */}
                  <div>
                    <p className={`text-xs font-medium mb-2 ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>
                      ⚙️ 控制节点
                    </p>
                    <div className="grid grid-cols-2 gap-1">
                      {nodeTypesData.control_nodes
                        .filter((n) => n.type !== 'start' && n.type !== 'end')
                        .map((node) => (
                          <button
                            key={node.type}
                            onClick={() => handleAddNode(node)}
                            className={`text-left px-2 py-1.5 rounded text-xs transition-colors truncate ${
                              node.type === 'condition'
                                ? isDark
                                  ? 'bg-orange-900/50 hover:bg-orange-800/50 text-orange-300'
                                  : 'bg-orange-50 hover:bg-orange-100 text-orange-700'
                                : node.type === 'parallel'
                                  ? isDark
                                    ? 'bg-purple-900/50 hover:bg-purple-800/50 text-purple-300'
                                    : 'bg-purple-50 hover:bg-purple-100 text-purple-700'
                                  : isDark
                                    ? 'bg-gray-700 hover:bg-gray-600 text-gray-300'
                                    : 'bg-gray-50 hover:bg-gray-100 text-gray-700'
                            }`}
                            title={node.label}
                          >
                            {node.label}
                          </button>
                        ))}
                    </div>
                  </div>
                </>
              )}
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
