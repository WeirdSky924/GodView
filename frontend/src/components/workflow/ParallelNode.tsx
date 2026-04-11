/**
 * 并行节点组件
 * v8 Agent协作可视化工作台
 */

import { memo } from 'react'
import { Handle, Position, type NodeProps } from 'reactflow'
import { Layers } from 'lucide-react'
import type { NodeStatus } from '@/api/workflows'

const STATUS_COLORS: Record<NodeStatus, string> = {
  pending: 'bg-purple-50 border-purple-300',
  running: 'bg-blue-50 border-blue-400 animate-pulse',
  completed: 'bg-green-50 border-green-400',
  failed: 'bg-red-50 border-red-400',
  skipped: 'bg-gray-50 border-gray-200',
}

export interface ParallelNodeData {
  label: string
  status?: NodeStatus
  branch_count?: number
}

function ParallelNode({ data, selected }: NodeProps<ParallelNodeData>) {
  const status = data.status || 'pending'
  const branchCount = data.branch_count || 2

  return (
    <div
      className={`
        px-4 py-3 rounded-lg border-2 min-w-[140px] transition-all
        ${STATUS_COLORS[status]}
        ${selected ? 'ring-2 ring-purple-400 ring-offset-2' : ''}
      `}
    >
      {/* 输入连接点 */}
      <Handle
        type="target"
        position={Position.Top}
        className="w-3 h-3 bg-purple-400 border-2 border-white"
      />

      {/* 节点内容 */}
      <div className="flex items-center gap-2">
        <Layers size={18} className="text-purple-600" />
        <div className="flex-1">
          <div className="font-medium text-sm">{data.label}</div>
          <div className="text-xs opacity-70">{branchCount} 个并行分支</div>
        </div>
      </div>

      {/* 并行指示条 */}
      <div className="mt-2 flex gap-1">
        {Array.from({ length: Math.min(branchCount, 5) }).map((_, i) => (
          <div
            key={i}
            className="flex-1 h-1.5 bg-purple-300 rounded-full"
          />
        ))}
        {branchCount > 5 && (
          <div className="text-xs opacity-50">+{branchCount - 5}</div>
        )}
      </div>

      {/* 输出连接点 */}
      <Handle
        type="source"
        position={Position.Bottom}
        className="w-3 h-3 bg-purple-400 border-2 border-white"
      />
    </div>
  )
}

export default memo(ParallelNode)
