/**
 * 节点面板组件 - 可拖拽的节点源
 * v8 Agent协作可视化工作台
 */

import { useTheme } from '@/contexts/ThemeContext'
import {
  Bot,
  GitBranch,
  Layers,
  Play,
  Square,
  MessageSquare,
  Settings,
  PenTool,
  Users,
  BookOpen,
  Search,
  Dices,
  Map,
  MessageCircle,
} from 'lucide-react'

// Agent 类型定义
const AGENT_TYPES = [
  { type: 'setting', label: '设定 Agent', icon: Settings, color: 'text-blue-500' },
  { type: 'writer', label: '作家 Agent', icon: PenTool, color: 'text-green-500' },
  { type: 'plotter', label: '编剧 Agent', icon: GitBranch, color: 'text-purple-500' },
  { type: 'character', label: '角色 Agent', icon: Users, color: 'text-orange-500' },
  { type: 'summarizer', label: '摘要 Agent', icon: BookOpen, color: 'text-cyan-500' },
  { type: 'evaluator', label: '评估 Agent', icon: Search, color: 'text-red-500' },
  { type: 'hook_manager', label: '伏笔 Agent', icon: GitBranch, color: 'text-yellow-500' },
  { type: 'event_generator', label: '事件 Agent', icon: Dices, color: 'text-pink-500' },
  { type: 'world_map_manager', label: '地图 Agent', icon: Map, color: 'text-teal-500' },
]

// 节点类型定义
const NODE_TYPES = [
  { type: 'start', label: '开始', icon: Play, color: 'text-green-500' },
  { type: 'end', label: '结束', icon: Square, color: 'text-gray-500' },
  { type: 'condition', label: '条件分支', icon: GitBranch, color: 'text-amber-500' },
  { type: 'parallel', label: '并行执行', icon: Layers, color: 'text-purple-500' },
  { type: 'group_discussion', label: '集体讨论', icon: MessageCircle, color: 'text-indigo-500' },
  { type: 'input', label: '用户输入', icon: MessageSquare, color: 'text-blue-500' },
]

interface NodePanelProps {
  onDragStart?: (event: React.DragEvent, nodeType: string, data: Record<string, any>) => void
}

export default function NodePanel({ onDragStart }: NodePanelProps) {
  const { theme } = useTheme()
  const isDark = theme === 'dark'

  const handleDragStart = (
    event: React.DragEvent,
    nodeType: string,
    data: Record<string, any>,
  ) => {
    event.dataTransfer.setData('application/reactflow', JSON.stringify({ nodeType, data }))
    event.dataTransfer.effectAllowed = 'move'
    onDragStart?.(event, nodeType, data)
  }

  return (
    <div
      className={`
        w-64 h-full border-r overflow-y-auto
        ${isDark ? 'bg-gray-900 border-gray-700' : 'bg-white border-gray-200'}
      `}
    >
      {/* Agent 节点 */}
      <div className="p-4">
        <h3
          className={`text-sm font-semibold mb-3 flex items-center gap-2 ${
            isDark ? 'text-gray-200' : 'text-gray-700'
          }`}
        >
          <Bot size={16} />
          Agent 节点
        </h3>
        <div className="space-y-2">
          {AGENT_TYPES.map((agent) => (
            <div
              key={agent.type}
              draggable
              onDragStart={(e) =>
                handleDragStart(e, 'agent', {
                  agent_type: agent.type,
                  label: agent.label,
                })
              }
              className={`
                flex items-center gap-3 p-2 rounded-lg cursor-grab
                transition-all active:cursor-grabbing
                ${isDark ? 'bg-gray-800 hover:bg-gray-700' : 'bg-gray-50 hover:bg-gray-100'}
              `}
            >
              <agent.icon size={18} className={agent.color} />
              <span className={`text-sm ${isDark ? 'text-gray-300' : 'text-gray-600'}`}>
                {agent.label}
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* 控制节点 */}
      <div className="p-4 border-t border-gray-200 dark:border-gray-700">
        <h3
          className={`text-sm font-semibold mb-3 flex items-center gap-2 ${
            isDark ? 'text-gray-200' : 'text-gray-700'
          }`}
        >
          <Layers size={16} />
          控制节点
        </h3>
        <div className="space-y-2">
          {NODE_TYPES.map((node) => (
            <div
              key={node.type}
              draggable
              onDragStart={(e) =>
                handleDragStart(e, node.type, {
                  label: node.label,
                })
              }
              className={`
                flex items-center gap-3 p-2 rounded-lg cursor-grab
                transition-all active:cursor-grabbing
                ${isDark ? 'bg-gray-800 hover:bg-gray-700' : 'bg-gray-50 hover:bg-gray-100'}
              `}
            >
              <node.icon size={18} className={node.color} />
              <span className={`text-sm ${isDark ? 'text-gray-300' : 'text-gray-600'}`}>
                {node.label}
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* 提示 */}
      <div
        className={`p-4 text-xs ${isDark ? 'text-gray-500' : 'text-gray-400'}`}
      >
        拖拽节点到画布上创建工作流
      </div>
    </div>
  )
}
