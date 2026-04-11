/**
 * 工作流监控面板组件
 * v8 Agent协作可视化工作台
 */

import { useState, useEffect } from 'react'
import { useTheme } from '@/contexts/ThemeContext'
import type { WorkflowExecution, NodeExecutionState } from '@/api/workflows'
import { getExecution } from '@/api/workflows'
import {
  Activity,
  Clock,
  CheckCircle,
  XCircle,
  Pause,
  Play,
  Loader2,
  ChevronDown,
  ChevronRight,
} from 'lucide-react'

interface WorkflowMonitorProps {
  executionId: string | null
  onRefresh?: () => void
}

// 状态图标
const STATUS_ICONS: Record<string, React.ReactNode> = {
  pending: <Clock size={14} className="text-gray-400" />,
  running: <Loader2 size={14} className="text-blue-500 animate-spin" />,
  completed: <CheckCircle size={14} className="text-green-500" />,
  failed: <XCircle size={14} className="text-red-500" />,
  skipped: <Pause size={14} className="text-gray-400" />,
}

export default function WorkflowMonitor({ executionId, onRefresh }: WorkflowMonitorProps) {
  const { theme } = useTheme()
  const isDark = theme === 'dark'

  const [execution, setExecution] = useState<WorkflowExecution | null>(null)
  const [expandedNodes, setExpandedNodes] = useState<Set<string>>(new Set())
  const [loading, setLoading] = useState(false)

  // 轮询执行状态
  useEffect(() => {
    if (!executionId) {
      setExecution(null)
      return
    }

    const fetchExecution = async () => {
      setLoading(true)
      try {
        const data = await getExecution(executionId)
        setExecution(data)
      } catch (error) {
        console.error('Failed to fetch execution:', error)
      } finally {
        setLoading(false)
      }
    }

    fetchExecution()

    // 如果正在运行，每秒刷新
    if (execution?.status === 'running') {
      const interval = setInterval(fetchExecution, 1000)
      return () => clearInterval(interval)
    }
  }, [executionId, execution?.status])

  const toggleNode = (nodeId: string) => {
    const newExpanded = new Set(expandedNodes)
    if (newExpanded.has(nodeId)) {
      newExpanded.delete(nodeId)
    } else {
      newExpanded.add(nodeId)
    }
    setExpandedNodes(newExpanded)
  }

  // 格式化时间
  const formatTime = (ms?: number) => {
    if (!ms) return '-'
    if (ms < 1000) return `${ms}ms`
    if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`
    return `${(ms / 60000).toFixed(1)}m`
  }

  if (!executionId) {
    return (
      <div
        className={`
          h-full flex items-center justify-center p-4
          ${isDark ? 'bg-gray-900' : 'bg-white'}
        `}
      >
        <p className={`text-sm ${isDark ? 'text-gray-500' : 'text-gray-400'}`}>
          启动工作流以查看执行状态
        </p>
      </div>
    )
  }

  if (loading && !execution) {
    return (
      <div
        className={`
          h-full flex items-center justify-center p-4
          ${isDark ? 'bg-gray-900' : 'bg-white'}
        `}
      >
        <Loader2 size={20} className="animate-spin text-blue-500" />
      </div>
    )
  }

  if (!execution) return null

  return (
    <div className={`h-full overflow-y-auto ${isDark ? 'bg-gray-900' : 'bg-white'}`}>
      {/* 标题 */}
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
          <Activity size={16} />
          执行监控
        </h3>
        <div
          className={`
            px-2 py-1 rounded text-xs font-medium
            ${execution.status === 'running' ? 'bg-blue-100 text-blue-600' : ''}
            ${execution.status === 'completed' ? 'bg-green-100 text-green-600' : ''}
            ${execution.status === 'failed' ? 'bg-red-100 text-red-600' : ''}
            ${execution.status === 'paused' ? 'bg-yellow-100 text-yellow-600' : ''}
          `}
        >
          {execution.status}
        </div>
      </div>

      {/* 执行信息 */}
      <div className="p-4 space-y-3">
        {/* 执行ID */}
        <div>
          <label
            className={`block text-xs font-medium mb-1 ${
              isDark ? 'text-gray-400' : 'text-gray-500'
            }`}
          >
            执行 ID
          </label>
          <div
            className={`text-xs font-mono ${
              isDark ? 'text-gray-300' : 'text-gray-600'
            }`}
          >
            {execution.id.slice(0, 16)}...
          </div>
        </div>

        {/* 当前节点 */}
        {execution.current_node && (
          <div>
            <label
              className={`block text-xs font-medium mb-1 ${
                isDark ? 'text-gray-400' : 'text-gray-500'
              }`}
            >
              当前节点
            </label>
            <div
              className={`flex items-center gap-2 ${
                isDark ? 'text-gray-300' : 'text-gray-600'
              }`}
            >
              <Loader2 size={14} className="animate-spin text-blue-500" />
              <span className="text-sm">{execution.current_node}</span>
            </div>
          </div>
        )}

        {/* 执行时间 */}
        <div>
          <label
            className={`block text-xs font-medium mb-1 ${
              isDark ? 'text-gray-400' : 'text-gray-500'
            }`}
          >
            执行时间
          </label>
          <div className={`text-sm ${isDark ? 'text-gray-300' : 'text-gray-600'}`}>
            {formatTime(execution.total_duration_ms)}
          </div>
        </div>

        {/* 错误信息 */}
        {execution.error && (
          <div className="bg-red-50 border border-red-200 rounded-lg p-3">
            <div className="text-xs font-medium text-red-600 mb-1">错误</div>
            <div className="text-sm text-red-500">{execution.error}</div>
          </div>
        )}
      </div>

      {/* 节点状态列表 */}
      <div
        className={`border-t ${isDark ? 'border-gray-700' : 'border-gray-200'}`}
      >
        <div
          className={`px-4 py-2 text-xs font-medium ${
            isDark ? 'text-gray-400 bg-gray-800' : 'text-gray-500 bg-gray-50'
          }`}
        >
          节点状态 ({Object.keys(execution.node_states).length})
        </div>
        <div className="divide-y dark:divide-gray-700">
          {Object.entries(execution.node_states).map(([nodeId, state]) => (
            <NodeStateItem
              key={nodeId}
              nodeId={nodeId}
              state={state}
              isExpanded={expandedNodes.has(nodeId)}
              onToggle={() => toggleNode(nodeId)}
              isDark={isDark}
            />
          ))}
        </div>
      </div>

      {/* 上下文变量 */}
      {Object.keys(execution.context).length > 0 && (
        <div
          className={`border-t ${isDark ? 'border-gray-700' : 'border-gray-200'}`}
        >
          <div
            className={`px-4 py-2 text-xs font-medium ${
              isDark ? 'text-gray-400 bg-gray-800' : 'text-gray-500 bg-gray-50'
            }`}
          >
            上下文变量
          </div>
          <div className="p-4">
            <pre
              className={`
                text-xs p-2 rounded overflow-x-auto
                ${isDark ? 'bg-gray-800 text-gray-300' : 'bg-gray-50 text-gray-600'}
              `}
            >
              {JSON.stringify(execution.context, null, 2)}
            </pre>
          </div>
        </div>
      )}
    </div>
  )
}

// 节点状态项组件
interface NodeStateItemProps {
  nodeId: string
  state: NodeExecutionState
  isExpanded: boolean
  onToggle: () => void
  isDark: boolean
}

function NodeStateItem({ nodeId, state, isExpanded, onToggle, isDark }: NodeStateItemProps) {
  return (
    <div>
      <button
        onClick={onToggle}
        className={`
          w-full flex items-center gap-2 px-4 py-2 text-left
          hover:bg-gray-50 dark:hover:bg-gray-800
        `}
      >
        {isExpanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
        {STATUS_ICONS[state.status]}
        <span className={`text-sm flex-1 ${isDark ? 'text-gray-300' : 'text-gray-600'}`}>
          {nodeId}
        </span>
        {state.duration_ms && (
          <span className={`text-xs ${isDark ? 'text-gray-500' : 'text-gray-400'}`}>
            {state.duration_ms}ms
          </span>
        )}
      </button>
      {isExpanded && (
        <div className={`px-4 pb-2 ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>
          {state.error && (
            <div className="text-xs text-red-500 mb-2">{state.error}</div>
          )}
          {Object.keys(state.output_data).length > 0 && (
            <pre
              className={`
                text-xs p-2 rounded overflow-x-auto
                ${isDark ? 'bg-gray-800' : 'bg-gray-50'}
              `}
            >
              {JSON.stringify(state.output_data, null, 2)}
            </pre>
          )}
        </div>
      )}
    </div>
  )
}
