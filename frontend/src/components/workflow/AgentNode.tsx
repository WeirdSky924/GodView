/**
 * Agent 节点组件
 * v8 Agent协作可视化工作台
 */

import { memo } from 'react'
import { Handle, Position, type NodeProps } from 'reactflow'
import {
  Bot,
  Settings,
  PenTool,
  Users,
  GitBranch,
  BookOpen,
  Search,
  Map,
  Dices,
  Play,
  Square,
  MessageSquare,
} from 'lucide-react'
import type { NodeStatus } from '@/api/workflows'

// Agent 类型图标映射
const AGENT_ICONS: Record<string, React.ReactNode> = {
  setting: <Settings size={18} />,
  writer: <PenTool size={18} />,
  plotter: <GitBranch size={18} />,
  character: <Users size={18} />,
  summarizer: <BookOpen size={18} />,
  evaluator: <Search size={18} />,
  hook_manager: <GitBranch size={18} />,
  event_generator: <Dices size={18} />,
  world_map_manager: <Map size={18} />,
  // 控制节点
  start: <Play size={18} />,
  end: <Square size={18} />,
  input: <MessageSquare size={18} />,
  default: <Bot size={18} />,
}

// 节点类型样式映射
const NODE_TYPE_STYLES: Record<string, { bg: string; border: string; text: string }> = {
  start: { bg: 'bg-green-50', border: 'border-green-400', text: 'text-green-600' },
  end: { bg: 'bg-red-50', border: 'border-red-400', text: 'text-red-600' },
  input: { bg: 'bg-blue-50', border: 'border-blue-400', text: 'text-blue-600' },
  condition: { bg: 'bg-amber-50', border: 'border-amber-400', text: 'text-amber-600' },
  parallel: { bg: 'bg-purple-50', border: 'border-purple-400', text: 'text-purple-600' },
  default: { bg: 'bg-gray-100', border: 'border-gray-300', text: 'text-gray-500' },
}

// Agent 状态颜色映射
const STATUS_COLORS: Record<NodeStatus, string> = {
  pending: 'bg-gray-100 border-gray-300 text-gray-500',
  running: 'bg-blue-50 border-blue-400 text-blue-600 animate-pulse',
  completed: 'bg-green-50 border-green-400 text-green-600',
  failed: 'bg-red-50 border-red-400 text-red-600',
  skipped: 'bg-gray-50 border-gray-200 text-gray-400',
}

const STATUS_DOT_COLORS: Record<NodeStatus, string> = {
  pending: 'bg-gray-400',
  running: 'bg-blue-500 animate-pulse',
  completed: 'bg-green-500',
  failed: 'bg-red-500',
  skipped: 'bg-gray-300',
}

export interface AgentNodeData {
  label: string
  agent_type?: string
  status?: NodeStatus
  config?: Record<string, any>
  error?: string
}

function AgentNode({ data, selected, type }: NodeProps<AgentNodeData>) {
  const status = data.status || 'pending'
  const nodeType = type || 'agent'
  const agentType = data.agent_type || 'default'

  // 根据节点类型获取图标
  const icon = AGENT_ICONS[nodeType] || AGENT_ICONS[agentType] || AGENT_ICONS.default

  // 根据节点类型获取样式
  const typeStyle = NODE_TYPE_STYLES[nodeType] || NODE_TYPE_STYLES.default
  const statusColor = status !== 'pending' ? STATUS_COLORS[status] : `${typeStyle.bg} ${typeStyle.border} ${typeStyle.text}`
  const dotColor = STATUS_DOT_COLORS[status]

  // 是否是控制节点（开始/结束/输入）
  const isControlNode = ['start', 'end', 'input'].includes(nodeType)

  return (
    <div
      className={`
        px-4 py-3 rounded-lg border-2 min-w-[140px] transition-all
        ${statusColor}
        ${selected ? 'ring-2 ring-blue-400 ring-offset-2' : ''}
      `}
    >
      {/* 输入连接点（除了开始节点） */}
      {nodeType !== 'start' && (
        <Handle
          type="target"
          position={Position.Top}
          className="w-3 h-3 bg-gray-400 border-2 border-white"
        />
      )}

      {/* 节点内容 */}
      <div className="flex items-center gap-3">
        <div className="p-1.5 rounded-md bg-white/50">{icon}</div>
        <div className="flex-1">
          <div className="font-medium text-sm">{data.label}</div>
          {!isControlNode && agentType && agentType !== 'default' && (
            <div className="text-xs opacity-70">{agentType}</div>
          )}
        </div>
        {status !== 'pending' && (
          <div className={`w-2.5 h-2.5 rounded-full ${dotColor}`} title={status} />
        )}
      </div>

      {/* 错误信息 */}
      {data.error && (
        <div className="mt-2 text-xs text-red-600 bg-red-50 px-2 py-1 rounded">
          {data.error}
        </div>
      )}

      {/* 输出连接点（除了结束节点） */}
      {nodeType !== 'end' && (
        <Handle
          type="source"
          position={Position.Bottom}
          className="w-3 h-3 bg-gray-400 border-2 border-white"
        />
      )}
    </div>
  )
}

export default memo(AgentNode)
