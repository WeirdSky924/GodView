/**
 * 属性面板组件 - 编辑节点和边属性
 * v8 Agent协作可视化工作台
 */

import { useState, useEffect } from 'react'
import { useTheme } from '@/contexts/ThemeContext'
import type { WorkflowNode } from '@/api/workflows'
import { X, Settings, Save, GitBranch, Plus, Trash2, ArrowDownCircle, ArrowUpCircle, BookOpen, Layers, RefreshCw } from 'lucide-react'
import { getAgentTypeSkills, type Skill } from '@/api/skills'

// Agent 类型选项
const AGENT_TYPE_OPTIONS = [
  { value: 'setting', label: '设定 Agent' },
  { value: 'writer', label: '作家 Agent' },
  { value: 'plotter', label: '编剧 Agent' },
  { value: 'master_plotter', label: '总编剧 Agent' },
  { value: 'character', label: '角色 Agent' },
  { value: 'summarizer', label: '摘要 Agent' },
  { value: 'evaluator', label: '评估 Agent' },
  { value: 'hook_manager', label: '伏笔 Agent' },
  { value: 'event_generator', label: '事件 Agent' },
  { value: 'world_map_manager', label: '地图 Agent' },
  { value: 'proc_gen', label: '过程生成 Agent' },
  { value: 'dungeon_generator', label: '副本生成 Agent' },
  // v9 新增
  { value: 'plot_outline', label: '章节大纲 Agent' },
  { value: 'scene_coordinator', label: '场景协调 Agent' },
]

// 数据输入来源选项
const INPUT_SOURCE_OPTIONS = [
  { value: 'database', label: '数据库' },
  { value: 'context', label: '上下文' },
  { value: 'upstream', label: '上游节点' },
  { value: 'variable', label: '工作流变量' },
  { value: 'user_input', label: '用户输入' },
]

// 数据输出目标选项
const OUTPUT_TARGET_OPTIONS = [
  { value: 'context', label: '上下文' },
  { value: 'downstream', label: '下游节点' },
  { value: 'database', label: '数据库' },
]

// 数据库数据类型选项
const DATABASE_DATA_TYPES = [
  { value: 'characters', label: '角色列表' },
  { value: 'world', label: '世界观设定' },
  { value: 'hooks', label: '伏笔列表' },
  { value: 'chapters', label: '章节列表' },
  { value: 'project', label: '项目信息' },
  { value: 'events', label: '事件列表' },
  { value: 'locations', label: '地点列表' },
]

// 边条件结果选项
const EDGE_CONDITION_OPTIONS = [
  { value: '', label: '无条件（默认路径）' },
  { value: 'pass', label: '通过 (pass)' },
  { value: 'retry', label: '重试 (retry)' },
]

// 输入配置类型
interface NodeInputConfig {
  name: string
  source: string
  data_type?: string
  key?: string
  upstream_node?: string
  upstream_field?: string
  required: boolean
  default?: any
}

// 输出配置类型
interface NodeOutputConfig {
  name: string
  target: string
  key?: string
  save_to_db: boolean
  db_table?: string
}

interface EdgeData {
  id: string
  source: string
  target: string
  condition?: { result?: string }
}

interface PropertyPanelProps {
  node: WorkflowNode | null
  edge: EdgeData | null
  onClose?: () => void
  onUpdateNode?: (nodeId: string, updates: Partial<WorkflowNode>) => void
  onUpdateEdge?: (edgeId: string, updates: any) => void
}

export default function PropertyPanel({ node, edge, onClose, onUpdateNode, onUpdateEdge }: PropertyPanelProps) {
  const { theme } = useTheme()
  const isDark = theme === 'dark'

  const [label, setLabel] = useState('')
  const [agentType, setAgentType] = useState('')
  const [config, setConfig] = useState<Record<string, any>>({})
  const [edgeCondition, setEdgeCondition] = useState('')
  // 输入输出配置状态
  const [inputs, setInputs] = useState<NodeInputConfig[]>([])
  const [outputs, setOutputs] = useState<NodeOutputConfig[]>([])
  // Skills 状态
  const [agentSkills, setAgentSkills] = useState<Skill[]>([])
  const [loadingSkills, setLoadingSkills] = useState(false)

  // 加载 Agent 类型的 Skills
  const loadAgentSkills = async (agentType: string) => {
    if (!agentType) {
      setAgentSkills([])
      return
    }

    setLoadingSkills(true)
    try {
      const skills = await getAgentTypeSkills(agentType)
      setAgentSkills(skills)
    } catch (error) {
      console.error('Failed to load agent skills:', error)
      setAgentSkills([])
    } finally {
      setLoadingSkills(false)
    }
  }

  useEffect(() => {
    if (node) {
      setLabel(node.label)
      setAgentType(node.agent_type || '')
      setConfig(node.config || {})
      // 加载 inputs 和 outputs
      setInputs((node as any).inputs || [])
      setOutputs((node as any).outputs || [])
      // 加载 Agent Skills
      if (node.node_type === 'agent' && node.agent_type) {
        loadAgentSkills(node.agent_type)
      } else {
        setAgentSkills([])
      }
    }
    if (edge) {
      setEdgeCondition(edge.condition?.result || '')
    }
  }, [node, edge])

  // 当 agentType 变化时重新加载 Skills
  useEffect(() => {
    if (node?.node_type === 'agent' && agentType) {
      loadAgentSkills(agentType)
    }
  }, [agentType])

  // 添加输入配置
  const handleAddInput = () => {
    setInputs([
      ...inputs,
      { name: '', source: 'database', data_type: 'characters', required: true },
    ])
  }

  // 更新输入配置
  const handleUpdateInput = (index: number, updates: Partial<NodeInputConfig>) => {
    const newInputs = [...inputs]
    newInputs[index] = { ...newInputs[index], ...updates }
    setInputs(newInputs)
  }

  // 删除输入配置
  const handleRemoveInput = (index: number) => {
    setInputs(inputs.filter((_, i) => i !== index))
  }

  // 添加输出配置
  const handleAddOutput = () => {
    setOutputs([
      ...outputs,
      { name: '', target: 'context', save_to_db: false },
    ])
  }

  // 更新输出配置
  const handleUpdateOutput = (index: number, updates: Partial<NodeOutputConfig>) => {
    const newOutputs = [...outputs]
    newOutputs[index] = { ...newOutputs[index], ...updates }
    setOutputs(newOutputs)
  }

  // 删除输出配置
  const handleRemoveOutput = (index: number) => {
    setOutputs(outputs.filter((_, i) => i !== index))
  }

  // 无选中状态
  if (!node && !edge) {
    return (
      <div
        className={`
          w-72 h-full border-l flex items-center justify-center
          ${isDark ? 'bg-gray-900 border-gray-700' : 'bg-white border-gray-200'}
        `}
      >
        <p className={`text-sm ${isDark ? 'text-gray-500' : 'text-gray-400'}`}>
          选择节点或连线以编辑属性
        </p>
      </div>
    )
  }

  // 边属性编辑
  if (edge && !node) {
    const handleSaveEdge = () => {
      const condition = edgeCondition ? { result: edgeCondition } : undefined
      onUpdateEdge?.(edge.id, { condition })
    }

    return (
      <div
        className={`
          w-72 h-full border-l overflow-y-auto
          ${isDark ? 'bg-gray-900 border-gray-700' : 'bg-white border-gray-200'}
        `}
      >
        {/* 标题栏 */}
        <div
          className={`
            flex items-center justify-between p-4 border-b
            ${isDark ? 'border-gray-700' : 'border-gray-200'}
          `}
        >
          <h3
            className={`text-sm font-semibold flex items-center gap-2 ${
              isDark ? 'text-gray-200' : 'text-gray-700'
            }`}
          >
            <GitBranch size={16} />
            连线属性
          </h3>
          <button
            onClick={onClose}
            className={`p-1 rounded hover:bg-gray-100 dark:hover:bg-gray-800`}
          >
            <X size={16} />
          </button>
        </div>

        {/* 边属性编辑 */}
        <div className="p-4 space-y-4">
          {/* 边ID */}
          <div>
            <label
              className={`block text-xs font-medium mb-1 ${
                isDark ? 'text-gray-400' : 'text-gray-500'
              }`}
            >
              连线 ID
            </label>
            <div
              className={`text-sm font-mono ${
                isDark ? 'text-gray-300' : 'text-gray-600'
              }`}
            >
              {edge.id}
            </div>
          </div>

          {/* 源节点和目标节点 */}
          <div className="grid grid-cols-2 gap-2">
            <div>
              <label
                className={`block text-xs font-medium mb-1 ${
                  isDark ? 'text-gray-400' : 'text-gray-500'
                }`}
              >
                源节点
              </label>
              <div
                className={`text-sm truncate ${
                  isDark ? 'text-gray-300' : 'text-gray-600'
                }`}
              >
                {edge.source}
              </div>
            </div>
            <div>
              <label
                className={`block text-xs font-medium mb-1 ${
                  isDark ? 'text-gray-400' : 'text-gray-500'
                }`}
              >
                目标节点
              </label>
              <div
                className={`text-sm truncate ${
                  isDark ? 'text-gray-300' : 'text-gray-600'
                }`}
              >
                {edge.target}
              </div>
            </div>
          </div>

          {/* 条件结果 */}
          <div>
            <label
              className={`block text-xs font-medium mb-1 ${
                isDark ? 'text-gray-400' : 'text-gray-500'
              }`}
            >
              条件结果
            </label>
            <select
              value={edgeCondition}
              onChange={(e) => setEdgeCondition(e.target.value)}
              className={`
                w-full px-3 py-2 rounded-lg border text-sm
                ${isDark
                  ? 'bg-gray-800 border-gray-600 text-white'
                  : 'bg-white border-gray-300'
                }
              `}
            >
              {EDGE_CONDITION_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
            <p className={`mt-1 text-xs ${isDark ? 'text-gray-500' : 'text-gray-400'}`}>
              从条件节点出发的连线需要设置结果类型
            </p>
          </div>

          {/* 保存按钮 */}
          <button
            onClick={handleSaveEdge}
            className={`
              w-full flex items-center justify-center gap-2 px-4 py-2 rounded-lg
              bg-blue-500 text-white hover:bg-blue-600 transition-colors
            `}
          >
            <Save size={16} />
            保存修改
          </button>
        </div>
      </div>
    )
  }

  // 节点属性编辑
  const handleSave = () => {
    onUpdateNode?.(node!.id, {
      label,
      agent_type: agentType,
      config,
      // 包含输入输出配置
      inputs: inputs.length > 0 ? inputs : undefined,
      outputs: outputs.length > 0 ? outputs : undefined,
    } as any)
  }

  // 渲染输入配置项
  const renderInputConfig = (input: NodeInputConfig, index: number) => (
    <div
      key={index}
      className={`
        p-3 rounded-lg border space-y-2
        ${isDark ? 'bg-gray-800 border-gray-600' : 'bg-gray-50 border-gray-200'}
      `}
    >
      <div className="flex items-center justify-between">
        <span className={`text-xs font-medium ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>
          输入 #{index + 1}
        </span>
        <button
          onClick={() => handleRemoveInput(index)}
          className="p-1 rounded hover:bg-red-100 dark:hover:bg-red-900/30 text-red-500"
        >
          <Trash2 size={12} />
        </button>
      </div>

      {/* 输入名称 */}
      <div>
        <label className={`block text-xs mb-1 ${isDark ? 'text-gray-500' : 'text-gray-400'}`}>
          名称
        </label>
        <input
          type="text"
          value={input.name}
          onChange={(e) => handleUpdateInput(index, { name: e.target.value })}
          placeholder="如: characters"
          className={`
            w-full px-2 py-1 rounded border text-xs
            ${isDark ? 'bg-gray-700 border-gray-600 text-white' : 'bg-white border-gray-300'}
          `}
        />
      </div>

      {/* 数据来源 */}
      <div>
        <label className={`block text-xs mb-1 ${isDark ? 'text-gray-500' : 'text-gray-400'}`}>
          来源
        </label>
        <select
          value={input.source}
          onChange={(e) => handleUpdateInput(index, { source: e.target.value })}
          className={`
            w-full px-2 py-1 rounded border text-xs
            ${isDark ? 'bg-gray-700 border-gray-600 text-white' : 'bg-white border-gray-300'}
          `}
        >
          {INPUT_SOURCE_OPTIONS.map((opt) => (
            <option key={opt.value} value={opt.value}>{opt.label}</option>
          ))}
        </select>
      </div>

      {/* 数据库数据类型（仅当来源为 database） */}
      {input.source === 'database' && (
        <div>
          <label className={`block text-xs mb-1 ${isDark ? 'text-gray-500' : 'text-gray-400'}`}>
            数据类型
          </label>
          <select
            value={input.data_type || 'characters'}
            onChange={(e) => handleUpdateInput(index, { data_type: e.target.value })}
            className={`
              w-full px-2 py-1 rounded border text-xs
              ${isDark ? 'bg-gray-700 border-gray-600 text-white' : 'bg-white border-gray-300'}
            `}
          >
            {DATABASE_DATA_TYPES.map((opt) => (
              <option key={opt.value} value={opt.value}>{opt.label}</option>
            ))}
          </select>
        </div>
      )}

      {/* 上下文/变量 key（仅当来源为 context 或 variable） */}
      {(input.source === 'context' || input.source === 'variable') && (
        <div>
          <label className={`block text-xs mb-1 ${isDark ? 'text-gray-500' : 'text-gray-400'}`}>
            Key
          </label>
          <input
            type="text"
            value={input.key || ''}
            onChange={(e) => handleUpdateInput(index, { key: e.target.value })}
            placeholder="上下文中的键名"
            className={`
              w-full px-2 py-1 rounded border text-xs
              ${isDark ? 'bg-gray-700 border-gray-600 text-white' : 'bg-white border-gray-300'}
            `}
          />
        </div>
      )}

      {/* 是否必需 */}
      <div className="flex items-center gap-2">
        <input
          type="checkbox"
          checked={input.required}
          onChange={(e) => handleUpdateInput(index, { required: e.target.checked })}
          className="rounded"
        />
        <label className={`text-xs ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>
          必需
        </label>
      </div>
    </div>
  )

  // 渲染输出配置项
  const renderOutputConfig = (output: NodeOutputConfig, index: number) => (
    <div
      key={index}
      className={`
        p-3 rounded-lg border space-y-2
        ${isDark ? 'bg-gray-800 border-gray-600' : 'bg-gray-50 border-gray-200'}
      `}
    >
      <div className="flex items-center justify-between">
        <span className={`text-xs font-medium ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>
          输出 #{index + 1}
        </span>
        <button
          onClick={() => handleRemoveOutput(index)}
          className="p-1 rounded hover:bg-red-100 dark:hover:bg-red-900/30 text-red-500"
        >
          <Trash2 size={12} />
        </button>
      </div>

      {/* 输出名称 */}
      <div>
        <label className={`block text-xs mb-1 ${isDark ? 'text-gray-500' : 'text-gray-400'}`}>
          名称
        </label>
        <input
          type="text"
          value={output.name}
          onChange={(e) => handleUpdateOutput(index, { name: e.target.value })}
          placeholder="如: chapter_goals"
          className={`
            w-full px-2 py-1 rounded border text-xs
            ${isDark ? 'bg-gray-700 border-gray-600 text-white' : 'bg-white border-gray-300'}
          `}
        />
      </div>

      {/* 输出目标 */}
      <div>
        <label className={`block text-xs mb-1 ${isDark ? 'text-gray-500' : 'text-gray-400'}`}>
          目标
        </label>
        <select
          value={output.target}
          onChange={(e) => handleUpdateOutput(index, { target: e.target.value })}
          className={`
            w-full px-2 py-1 rounded border text-xs
            ${isDark ? 'bg-gray-700 border-gray-600 text-white' : 'bg-white border-gray-300'}
          `}
        >
          {OUTPUT_TARGET_OPTIONS.map((opt) => (
            <option key={opt.value} value={opt.value}>{opt.label}</option>
          ))}
        </select>
      </div>

      {/* 保存键名（可选） */}
      <div>
        <label className={`block text-xs mb-1 ${isDark ? 'text-gray-500' : 'text-gray-400'}`}>
          保存键名（可选）
        </label>
        <input
          type="text"
          value={output.key || ''}
          onChange={(e) => handleUpdateOutput(index, { key: e.target.value })}
          placeholder="默认使用名称"
          className={`
            w-full px-2 py-1 rounded border text-xs
            ${isDark ? 'bg-gray-700 border-gray-600 text-white' : 'bg-white border-gray-300'}
          `}
        />
      </div>

      {/* 是否保存到数据库 */}
      {output.target === 'database' && (
        <div className="space-y-2">
          <div className="flex items-center gap-2">
            <input
              type="checkbox"
              checked={output.save_to_db}
              onChange={(e) => handleUpdateOutput(index, { save_to_db: e.target.checked })}
              className="rounded"
            />
            <label className={`text-xs ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>
              保存到数据库
            </label>
          </div>
          {output.save_to_db && (
            <input
              type="text"
              value={output.db_table || ''}
              onChange={(e) => handleUpdateOutput(index, { db_table: e.target.value })}
              placeholder="数据库表名"
              className={`
                w-full px-2 py-1 rounded border text-xs
                ${isDark ? 'bg-gray-700 border-gray-600 text-white' : 'bg-white border-gray-300'}
              `}
            />
          )}
        </div>
      )}
    </div>
  )

  return (
    <div
      className={`
        w-72 h-full border-l overflow-y-auto
        ${isDark ? 'bg-gray-900 border-gray-700' : 'bg-white border-gray-200'}
      `}
    >
      {/* 标题栏 */}
      <div
        className={`
          flex items-center justify-between p-4 border-b
          ${isDark ? 'border-gray-700' : 'border-gray-200'}
        `}
      >
        <h3
          className={`text-sm font-semibold flex items-center gap-2 ${
            isDark ? 'text-gray-200' : 'text-gray-700'
          }`}
        >
          <Settings size={16} />
          节点属性
        </h3>
        <button
          onClick={onClose}
          className={`p-1 rounded hover:bg-gray-100 dark:hover:bg-gray-800`}
        >
          <X size={16} />
        </button>
      </div>

      {/* 属性编辑 */}
      <div className="p-4 space-y-4">
        {/* 节点ID */}
        <div>
          <label
            className={`block text-xs font-medium mb-1 ${
              isDark ? 'text-gray-400' : 'text-gray-500'
            }`}
          >
            节点 ID
          </label>
          <div
            className={`text-sm font-mono ${
              isDark ? 'text-gray-300' : 'text-gray-600'
            }`}
          >
            {node!.id}
          </div>
        </div>

        {/* 节点类型 */}
        <div>
          <label
            className={`block text-xs font-medium mb-1 ${
              isDark ? 'text-gray-400' : 'text-gray-500'
            }`}
          >
            节点类型
          </label>
          <div
            className={`inline-block px-2 py-1 rounded text-xs ${
              isDark ? 'bg-gray-800 text-gray-300' : 'bg-gray-100 text-gray-600'
            }`}
          >
            {node!.node_type}
          </div>
        </div>

        {/* 节点名称 */}
        <div>
          <label
            className={`block text-xs font-medium mb-1 ${
              isDark ? 'text-gray-400' : 'text-gray-500'
            }`}
          >
            节点名称
          </label>
          <input
            type="text"
            value={label}
            onChange={(e) => setLabel(e.target.value)}
            className={`
              w-full px-3 py-2 rounded-lg border text-sm
              ${isDark
                ? 'bg-gray-800 border-gray-600 text-white'
                : 'bg-white border-gray-300'
              }
            `}
          />
        </div>

        {/* Agent 类型选择 (仅 Agent 节点) */}
        {node!.node_type === 'agent' && (
          <div>
            <label
              className={`block text-xs font-medium mb-1 ${
                isDark ? 'text-gray-400' : 'text-gray-500'
              }`}
            >
              Agent 类型
            </label>
            <select
              value={agentType}
              onChange={(e) => setAgentType(e.target.value)}
              className={`
                w-full px-3 py-2 rounded-lg border text-sm
                ${isDark
                  ? 'bg-gray-800 border-gray-600 text-white'
                  : 'bg-white border-gray-300'
                }
              `}
            >
              <option value="">选择 Agent 类型...</option>
              {AGENT_TYPE_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </div>
        )}

        {/* 条件表达式 (仅条件节点) */}
        {node!.node_type === 'condition' && (
          <div>
            <label
              className={`block text-xs font-medium mb-1 ${
                isDark ? 'text-gray-400' : 'text-gray-500'
              }`}
            >
              条件表达式
            </label>
            <textarea
              value={config.condition || ''}
              onChange={(e) => setConfig({ ...config, condition: e.target.value })}
              placeholder="例如: context.word_count > 1000"
              rows={3}
              className={`
                w-full px-3 py-2 rounded-lg border text-sm font-mono
                ${isDark
                  ? 'bg-gray-800 border-gray-600 text-white'
                  : 'bg-white border-gray-300'
                }
              `}
            />
          </div>
        )}

        {/* 并行分支数 (仅并行节点) */}
        {node!.node_type === 'parallel' && (
          <div>
            <label
              className={`block text-xs font-medium mb-1 ${
                isDark ? 'text-gray-400' : 'text-gray-500'
              }`}
            >
              并行分支数
            </label>
            <input
              type="number"
              min={2}
              max={10}
              value={config.branch_count || 2}
              onChange={(e) =>
                setConfig({ ...config, branch_count: parseInt(e.target.value) || 2 })
              }
              className={`
                w-full px-3 py-2 rounded-lg border text-sm
                ${isDark
                  ? 'bg-gray-800 border-gray-600 text-white'
                  : 'bg-white border-gray-300'
                }
              `}
            />
          </div>
        )}

        {/* 场景演绎配置 (仅场景演绎节点) */}
        {node!.node_type === 'scene_performance' && (
          <div className="space-y-3">
            <div>
              <label
                className={`block text-xs font-medium mb-1 ${
                  isDark ? 'text-gray-400' : 'text-gray-500'
                }`}
              >
                演绎模式
              </label>
              <select
                value={config.scene_mode || 'interactive'}
                onChange={(e) => setConfig({ ...config, scene_mode: e.target.value })}
                className={`
                  w-full px-3 py-2 rounded-lg border text-sm
                  ${isDark
                    ? 'bg-gray-800 border-gray-600 text-white'
                    : 'bg-white border-gray-300'
                  }
                `}
              >
                <option value="interactive">互动模式 - 角色按顺序互动</option>
                <option value="parallel">并行模式 - 角色独立表演</option>
              </select>
            </div>
            <div>
              <label
                className={`block text-xs font-medium mb-1 ${
                  isDark ? 'text-gray-400' : 'text-gray-500'
                }`}
              >
                场景方向
              </label>
              <textarea
                value={config.scene_direction || ''}
                onChange={(e) => setConfig({ ...config, scene_direction: e.target.value })}
                placeholder="描述场景的主要内容、氛围、冲突点..."
                rows={3}
                className={`
                  w-full px-3 py-2 rounded-lg border text-sm
                  ${isDark
                    ? 'bg-gray-800 border-gray-600 text-white'
                    : 'bg-white border-gray-300'
                  }
                `}
              />
            </div>
            <div>
              <label
                className={`flex items-center gap-2 text-xs font-medium ${
                  isDark ? 'text-gray-400' : 'text-gray-500'
                }`}
              >
                <input
                  type="checkbox"
                  checked={config.need_background_characters !== false}
                  onChange={(e) => setConfig({ ...config, need_background_characters: e.target.checked })}
                  className="w-4 h-4 rounded"
                />
                需要背景角色
              </label>
              <p className={`text-xs mt-1 ml-6 ${isDark ? 'text-gray-500' : 'text-gray-400'}`}>
                自动生成背景角色的行为描述
              </p>
            </div>
          </div>
        )}

        {/* 输入配置区域 (Agent 节点、讨论节点、场景演绎节点) */}
        {(node!.node_type === 'agent' || node!.node_type === 'group_discussion' || node!.node_type === 'scene_performance') && (
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <label
                className={`flex items-center gap-1 text-xs font-medium ${
                  isDark ? 'text-gray-400' : 'text-gray-500'
                }`}
              >
                <ArrowDownCircle size={14} />
                输入配置
              </label>
              <button
                onClick={handleAddInput}
                className="flex items-center gap-1 px-2 py-1 text-xs text-blue-500 hover:bg-blue-50 dark:hover:bg-blue-900/30 rounded"
              >
                <Plus size={12} />
                添加
              </button>
            </div>
            <p className={`text-xs ${isDark ? 'text-gray-500' : 'text-gray-400'}`}>
              定义此节点需要的数据来源
            </p>
            {inputs.length > 0 && (
              <div className="space-y-2 max-h-60 overflow-y-auto">
                {inputs.map((input, index) => renderInputConfig(input, index))}
              </div>
            )}
          </div>
        )}

        {/* 输出配置区域 (Agent 节点、讨论节点、场景演绎节点) */}
        {(node!.node_type === 'agent' || node!.node_type === 'group_discussion' || node!.node_type === 'scene_performance') && (
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <label
                className={`flex items-center gap-1 text-xs font-medium ${
                  isDark ? 'text-gray-400' : 'text-gray-500'
                }`}
              >
                <ArrowUpCircle size={14} />
                输出配置
              </label>
              <button
                onClick={handleAddOutput}
                className="flex items-center gap-1 px-2 py-1 text-xs text-green-500 hover:bg-green-50 dark:hover:bg-green-900/30 rounded"
              >
                <Plus size={12} />
                添加
              </button>
            </div>
            <p className={`text-xs ${isDark ? 'text-gray-500' : 'text-gray-400'}`}>
              定义此节点输出的数据去向
            </p>
            {outputs.length > 0 && (
              <div className="space-y-2 max-h-60 overflow-y-auto">
                {outputs.map((output, index) => renderOutputConfig(output, index))}
              </div>
            )}
          </div>
        )}

        {/* Skills 展示区域 (仅 Agent 节点) */}
        {node!.node_type === 'agent' && agentType && (
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <label
                className={`flex items-center gap-1 text-xs font-medium ${
                  isDark ? 'text-gray-400' : 'text-gray-500'
                }`}
              >
                <Layers size={14} />
                Agent Skills
              </label>
              <button
                onClick={() => loadAgentSkills(agentType)}
                disabled={loadingSkills}
                className={`flex items-center gap-1 px-2 py-1 text-xs text-purple-500 hover:bg-purple-50 dark:hover:bg-purple-900/30 rounded ${loadingSkills ? 'opacity-50' : ''}`}
              >
                <RefreshCw size={12} className={loadingSkills ? 'animate-spin' : ''} />
                刷新
              </button>
            </div>
            <p className={`text-xs ${isDark ? 'text-gray-500' : 'text-gray-400'}`}>
              该 Agent 类型可用的技能（从 Skills 系统加载）
            </p>

            {loadingSkills ? (
              <div className={`p-4 text-center text-xs ${isDark ? 'text-gray-500' : 'text-gray-400'}`}>
                加载 Skills...
              </div>
            ) : agentSkills.length > 0 ? (
              <div className="space-y-1 max-h-48 overflow-y-auto">
                {agentSkills.map((skill) => (
                  <div
                    key={skill.id}
                    className={`
                      p-2 rounded-lg border text-xs
                      ${isDark ? 'bg-gray-800 border-gray-600' : 'bg-gray-50 border-gray-200'}
                    `}
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <BookOpen size={12} className={isDark ? 'text-gray-400' : 'text-gray-500'} />
                        <span className={`font-medium ${isDark ? 'text-gray-200' : 'text-gray-700'}`}>
                          {skill.name}
                        </span>
                      </div>
                      <span className={`text-[10px] px-1.5 py-0.5 rounded ${
                        skill.skill_type === 'knowledge'
                          ? (isDark ? 'bg-blue-900 text-blue-300' : 'bg-blue-100 text-blue-700')
                          : skill.skill_type === 'prompt'
                          ? (isDark ? 'bg-purple-900 text-purple-300' : 'bg-purple-100 text-purple-700')
                          : (isDark ? 'bg-gray-700 text-gray-300' : 'bg-gray-200 text-gray-600')
                      }`}>
                        {skill.skill_type === 'knowledge' ? '知识' : skill.skill_type === 'prompt' ? '提示词' : skill.skill_type}
                      </span>
                    </div>
                    <p className={`mt-1 line-clamp-2 ${isDark ? 'text-gray-500' : 'text-gray-500'}`}>
                      {skill.description}
                    </p>
                    <div className="flex items-center gap-2 mt-1">
                      <span className={`text-[10px] ${isDark ? 'text-gray-500' : 'text-gray-400'}`}>
                        优先级: {skill.priority}
                      </span>
                      {skill.is_system && (
                        <span className={`text-[10px] ${isDark ? 'text-yellow-500' : 'text-yellow-600'}`}>
                          系统内置
                        </span>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className={`p-4 text-center text-xs ${isDark ? 'text-gray-500' : 'text-gray-400'}`}>
                暂无可用 Skills
              </div>
            )}

            <a
              href="/skills"
              className={`block text-xs text-center text-blue-500 hover:underline mt-2`}
            >
              前往 Skills 管理页面 →
            </a>
          </div>
        )}

        {/* 保存按钮 */}
        <button
          onClick={handleSave}
          className={`
            w-full flex items-center justify-center gap-2 px-4 py-2 rounded-lg
            bg-blue-500 text-white hover:bg-blue-600 transition-colors
          `}
        >
          <Save size={16} />
          保存修改
        </button>
      </div>
    </div>
  )
}
