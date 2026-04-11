/**
 * 条件节点组件
 * v8 Agent协作可视化工作台
 */

import { memo } from 'react'
import { Handle, Position, type NodeProps } from 'reactflow'
import { GitBranch, Check, X } from 'lucide-react'
import type { NodeStatus } from '@/api/workflows'

const STATUS_COLORS: Record<NodeStatus, string> = {
  pending: 'bg-amber-50 border-amber-300',
  running: 'bg-blue-50 border-blue-400 animate-pulse',
  completed: 'bg-green-50 border-green-400',
  failed: 'bg-red-50 border-red-400',
  skipped: 'bg-gray-50 border-gray-200',
}

export interface ConditionNodeData {
  label: string
  condition?: string
  status?: NodeStatus
  branches?: { id: string; label: string; condition: string }[]
}

function ConditionNode({ data, selected }: NodeProps<ConditionNodeData>) {
  const status = data.status || 'pending'
  const branches = data.branches || [
    { id: 'true', label: '是', condition: 'true' },
    { id: 'false', label: '否', condition: 'false' },
  ]

  return (
    <div
      className={`
        px-4 py-3 rounded-lg border-2 min-w-[160px] transition-all
        ${STATUS_COLORS[status]}
        ${selected ? 'ring-2 ring-amber-400 ring-offset-2' : ''}
      `}
    >
      {/* 输入连接点 */}
      <Handle
        type="target"
        position={Position.Top}
        className="w-3 h-3 bg-amber-400 border-2 border-white"
      />

      {/* 节点内容 */}
      <div className="flex items-center gap-2 mb-2">
        <GitBranch size={18} className="text-amber-600" />
        <div className="font-medium text-sm">{data.label}</div>
      </div>

      {/* 条件表达式 */}
      {data.condition && (
        <div className="text-xs bg-white/50 px-2 py-1 rounded mb-2 font-mono">
          {data.condition}
        </div>
      )}

      {/* 分支列表 */}
      <div className="space-y-1">
        {branches.map((branch, index) => (
          <div
            key={branch.id}
            className="flex items-center gap-2 text-xs bg-white/50 px-2 py-1 rounded"
          >
            {branch.id === 'true' || branch.id === 'yes' ? (
              <Check size={12} className="text-green-500" />
            ) : (
              <X size={12} className="text-red-500" />
            )}
            <span>{branch.label}</span>

            {/* 分支输出连接点 */}
            <Handle
              type="source"
              id={branch.id}
              position={Position.Right}
              className="w-2.5 h-2.5 bg-amber-400 border-2 border-white relative"
              style={{ top: 'auto', position: 'relative' }}
            />
          </div>
        ))}
      </div>

      {/* 默认输出连接点 */}
      <Handle
        type="source"
        position={Position.Bottom}
        className="w-3 h-3 bg-amber-400 border-2 border-white"
      />
    </div>
  )
}

export default memo(ConditionNode)
