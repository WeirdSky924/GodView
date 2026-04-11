/**
 * 节点面板组件 - 可拖拽的节点源
 * v8 Agent协作可视化工作台
 *
 * 动态从后端加载节点类型
 */

import { useTheme } from '@/contexts/ThemeContext'
import { useProject } from '@/contexts/ProjectContext'
import { useNodeTypes } from '@/hooks/useNodeTypes'
import {
  Bot,
  Layers,
  Play,
  Square,
  GitBranch,
  MessageSquare,
  Users,
  MessageCircle,
  Settings,
  PenTool,
  BookOpen,
  Search,
  Link,
  Dices,
  Map,
  User,
  Zap,
  Globe,
  CheckCircle,
  Shuffle,
  Loader2,
} from 'lucide-react'
import * as LucideIcons from 'lucide-react'

// 图标映射
const ICON_MAP: Record<string, React.ElementType> = {
  Bot,
  Settings,
  PenTool,
  BookOpen,
  Search,
  Link,
  GitBranch,
  Dices,
  Map,
  User,
  Users,
  MessageCircle,
  MessageSquare,
  Play,
  Square,
  Layers,
  Zap,
  Globe,
  CheckCircle,
  Shuffle,
}

interface NodePanelProps {
  onDragStart?: (event: React.DragEvent, nodeType: string, data: Record<string, any>) => void
}

export default function NodePanel({ onDragStart }: NodePanelProps) {
  const { theme } = useTheme()
  const { currentProject } = useProject()
  const isDark = theme === 'dark'

  // 动态加载节点类型
  const { nodeTypes, loading } = useNodeTypes(currentProject?.id)

  const handleDragStart = (
    event: React.DragEvent,
    nodeType: string,
    data: Record<string, any>,
  ) => {
    event.dataTransfer.setData('application/reactflow', JSON.stringify({ nodeType, data }))
    event.dataTransfer.effectAllowed = 'move'
    onDragStart?.(event, nodeType, data)
  }

  // 渲染节点项
  const renderNodeItem = (node: any) => {
    const IconComponent = ICON_MAP[node.icon] || Bot
    const colorClass = `text-${node.color}-500`

    return (
      <div
        key={node.agent_type || node.type}
        draggable
        onDragStart={(e) =>
          handleDragStart(e, node.type, {
            agent_type: node.agent_type,
            label: node.label,
            character_id: node.character_id,
            character_name: node.character_name,
          })
        }
        className={`
          flex items-center gap-3 p-2 rounded-lg cursor-grab
          transition-all active:cursor-grabbing
          ${isDark ? 'bg-gray-800 hover:bg-gray-700' : 'bg-gray-50 hover:bg-gray-100'}
        `}
      >
        <IconComponent size={18} className={colorClass} />
        <div className="flex-1 min-w-0">
          <span className={`text-sm truncate block ${isDark ? 'text-gray-300' : 'text-gray-600'}`}>
            {node.label}
          </span>
          {node.description && (
            <span className={`text-xs truncate block ${isDark ? 'text-gray-500' : 'text-gray-400'}`}>
              {node.description.slice(0, 20)}...
            </span>
          )}
        </div>
      </div>
    )
  }

  if (loading) {
    return (
      <div className={`w-64 h-full border-r flex items-center justify-center ${isDark ? 'bg-gray-900 border-gray-700' : 'bg-white border-gray-200'}`}>
        <Loader2 size={24} className="animate-spin text-blue-500" />
      </div>
    )
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
        <h3 className={`text-sm font-semibold mb-3 flex items-center gap-2 ${isDark ? 'text-gray-200' : 'text-gray-700'}`}>
          <Bot size={16} />
          系统 Agent
        </h3>
        <div className="space-y-2">
          {nodeTypes.agent_nodes.map(renderNodeItem)}
        </div>
      </div>

      {/* 角色 Agent 节点 */}
      {nodeTypes.character_nodes.length > 0 && (
        <div className="p-4 border-t border-gray-200 dark:border-gray-700">
          <h3 className={`text-sm font-semibold mb-3 flex items-center gap-2 ${isDark ? 'text-gray-200' : 'text-gray-700'}`}>
            <User size={16} />
            角色 Agent
          </h3>
          <div className="space-y-2">
            {nodeTypes.character_nodes.map(renderNodeItem)}
          </div>
        </div>
      )}

      {/* 交互节点 */}
      <div className="p-4 border-t border-gray-200 dark:border-gray-700">
        <h3 className={`text-sm font-semibold mb-3 flex items-center gap-2 ${isDark ? 'text-gray-200' : 'text-gray-700'}`}>
          <MessageCircle size={16} />
          交互节点
        </h3>
        <div className="space-y-2">
          {nodeTypes.interaction_nodes.map(renderNodeItem)}
        </div>
      </div>

      {/* 控制节点 */}
      <div className="p-4 border-t border-gray-200 dark:border-gray-700">
        <h3 className={`text-sm font-semibold mb-3 flex items-center gap-2 ${isDark ? 'text-gray-200' : 'text-gray-700'}`}>
          <Layers size={16} />
          控制节点
        </h3>
        <div className="space-y-2">
          {nodeTypes.control_nodes.map(renderNodeItem)}
        </div>
      </div>

      {/* 提示 */}
      <div className={`p-4 text-xs ${isDark ? 'text-gray-500' : 'text-gray-400'}`}>
        拖拽节点到画布上创建工作流
      </div>
    </div>
  )
}
