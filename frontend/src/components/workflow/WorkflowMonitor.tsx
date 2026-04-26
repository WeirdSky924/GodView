/**
 * 工作流监控面板组件
 * v8 Agent协作可视化工作台
 */

import { useState, useEffect, useRef } from 'react'
import { useTheme } from '@/contexts/ThemeContext'
import type { WorkflowExecution, NodeExecutionState, WorkflowEventMessage } from '@/api/workflows'
import { createWorkflowExecutionEventSource, getExecution } from '@/api/workflows'
import {
  Activity,
  Clock,
  CheckCircle,
  XCircle,
  Pause,
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

function JsonBlock({
  title,
  value,
  isDark,
}: {
  title: string
  value: unknown
  isDark: boolean
}) {
  if (
    value == null ||
    (typeof value === 'object' && !Array.isArray(value) && Object.keys(value as Record<string, unknown>).length === 0) ||
    (Array.isArray(value) && value.length === 0)
  ) {
    return null
  }

  return (
    <div className="space-y-1">
      <div className={`text-[11px] font-medium ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>
        {title}
      </div>
      <pre
        className={`
          text-xs p-2 rounded overflow-x-auto whitespace-pre-wrap break-all
          ${isDark ? 'bg-gray-800 text-gray-300' : 'bg-gray-50 text-gray-600'}
        `}
      >
        {JSON.stringify(value, null, 2)}
      </pre>
    </div>
  )
}

export default function WorkflowMonitor({ executionId, onRefresh }: WorkflowMonitorProps) {
  const { theme } = useTheme()
  const isDark = theme === 'dark'

  const [execution, setExecution] = useState<WorkflowExecution | null>(null)
  const [expandedNodes, setExpandedNodes] = useState<Set<string>>(new Set())
  const [loading, setLoading] = useState(false)
  const onRefreshRef = useRef(onRefresh)

  useEffect(() => {
    onRefreshRef.current = onRefresh
  }, [onRefresh])

  const applyExecutionSnapshot = (snapshot: WorkflowExecution) => {
    setExecution(snapshot)
    onRefreshRef.current?.()
  }

  const applyWorkflowEvent = (payload: WorkflowEventMessage) => {
    if (payload.type === 'execution_snapshot') {
      applyExecutionSnapshot(payload.data as unknown as WorkflowExecution)
      return
    }

    setExecution((current) => {
      if (!current || current.id !== payload.execution_id) return current

      const next: WorkflowExecution = {
        ...current,
        context: { ...current.context },
        node_states: { ...current.node_states },
      }
      const data = payload.data || {}

      if (payload.type === 'workflow_started') {
        next.status = 'running'
      } else if (payload.type === 'workflow_completed') {
        const status = data.status
        if (status === 'completed' || status === 'failed' || status === 'cancelled' || status === 'paused') {
          next.status = status
        }
        if (typeof data.error === 'string') next.error = data.error
      } else if (payload.type === 'workflow_paused') {
        next.status = 'paused'
      } else if (payload.type === 'workflow_resumed') {
        next.status = 'running'
      } else if (payload.type === 'workflow_cancelled') {
        next.status = 'cancelled'
      } else if (payload.type === 'waiting_user_confirmation') {
        next.status = 'paused'
        next.context.waiting_confirmation = data
      } else if (payload.type === 'discussion_confirmed') {
        next.status = 'running'
        next.context.waiting_confirmation = {
          ...(typeof next.context.waiting_confirmation === 'object' && next.context.waiting_confirmation
            ? next.context.waiting_confirmation
            : {}),
          confirmed: true,
        }
      } else if (payload.type === 'discussion_assets_persisted') {
        next.context.discussion_assets_committed = true
        next.context.discussion_persistence_state = data
        if (data.persisted_asset_refs) {
          next.context.persisted_asset_refs = data.persisted_asset_refs
        }
      } else if (payload.type === 'node_started' || payload.type === 'node_completed') {
        const nodeId = typeof data.node_id === 'string' ? data.node_id : null
        if (nodeId) {
          const previousState = next.node_states[nodeId]
          next.node_states[nodeId] = {
            node_id: nodeId,
            status: payload.type === 'node_started' ? 'running' : (data.status as NodeExecutionState['status']) || 'completed',
            input_data: (data.input as Record<string, any>) || previousState?.input_data || {},
            output_data: (data.output as Record<string, any>) || previousState?.output_data || {},
            output_contract_id: (data.output_contract_id as string | undefined) || previousState?.output_contract_id,
            output_mode: (data.output_mode as NodeExecutionState['output_mode']) || previousState?.output_mode,
            output_schema_name: (data.output_schema_name as string | undefined) || previousState?.output_schema_name,
            output_schema_version: (data.output_schema_version as string | undefined) || previousState?.output_schema_version,
            error: (data.error as string | undefined) || previousState?.error,
            duration_ms: (data.duration_ms as number | undefined) || previousState?.duration_ms,
          }
          next.current_node = payload.type === 'node_started' ? nodeId : next.current_node
          if (payload.type === 'node_completed') {
            const contextUpdates = Array.isArray(data.context_updates) ? data.context_updates : []
            for (const key of contextUpdates) {
              if (typeof key === 'string' && key in next.node_states[nodeId].output_data) {
                next.context[key] = next.node_states[nodeId].output_data[key]
              }
            }
          }
        }
      }

      return next
    })
    onRefreshRef.current?.()
  }

  // 通过 SSE 订阅执行状态，避免每秒 REST 轮询刷屏
  useEffect(() => {
    if (!executionId) {
      setExecution(null)
      return
    }

    let active = true
    let eventSource: EventSource | null = null
    let fallbackInterval: ReturnType<typeof setInterval> | null = null

    const fetchExecution = async () => {
      setLoading(true)
      try {
        const data = await getExecution(executionId)
        if (!active) return
        applyExecutionSnapshot(data)
      } catch (error) {
        if (active) console.error('Failed to fetch execution:', error)
      } finally {
        if (active) setLoading(false)
      }
    }

    const startFallbackPolling = () => {
      if (fallbackInterval) return
      fallbackInterval = setInterval(fetchExecution, 15000)
    }

    void fetchExecution()
    eventSource = createWorkflowExecutionEventSource(executionId)

    eventSource.addEventListener('workflow_event', ((event: MessageEvent<string>) => {
      try {
        const payload = JSON.parse(event.data) as WorkflowEventMessage
        if (active) applyWorkflowEvent(payload)
      } catch (error) {
        console.error('Failed to parse workflow SSE message:', error)
      }
    }) as EventListener)

    eventSource.onerror = () => {
      if (!active) return
      startFallbackPolling()
    }

    return () => {
      active = false
      if (fallbackInterval) clearInterval(fallbackInterval)
      if (eventSource) eventSource.close()
    }
  }, [executionId])

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

      <div className="p-4 space-y-3">
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

        {execution.error && (
          <div className="bg-red-50 border border-red-200 rounded-lg p-3">
            <div className="text-xs font-medium text-red-600 mb-1">错误</div>
            <div className="text-sm text-red-500">{execution.error}</div>
          </div>
        )}
      </div>

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
                text-xs p-2 rounded overflow-x-auto whitespace-pre-wrap break-all
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

interface NodeStateItemProps {
  nodeId: string
  state: NodeExecutionState
  isExpanded: boolean
  onToggle: () => void
  isDark: boolean
}

function NodeStateItem({ nodeId, state, isExpanded, onToggle, isDark }: NodeStateItemProps) {
  const inputData = state.input_data || {}
  const outputData = state.output_data || {}
  const trace = typeof inputData._input_trace === 'object' ? inputData._input_trace : null
  const highlightedOutput = {
    chapter_number: outputData.chapter_number,
    chapter_title: outputData.chapter_title,
    chapter_outline: outputData.chapter_outline,
    chapter_goals: outputData.chapter_goals,
    scene_directions: outputData.scene_directions,
    quality_passed: outputData.quality_passed,
    revision_notes: outputData.revision_notes,
  }

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
        <div className={`px-4 pb-3 space-y-2 ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>
          {state.error && (
            <div className="text-xs text-red-500">{state.error}</div>
          )}
          {trace && (
            <JsonBlock title="输入来源" value={trace} isDark={isDark} />
          )}
          <JsonBlock title="输入" value={inputData} isDark={isDark} />
          <JsonBlock title="关键输出" value={highlightedOutput} isDark={isDark} />
          <JsonBlock title="完整输出" value={outputData} isDark={isDark} />
        </div>
      )}
    </div>
  )
}
