import { useState, useMemo } from 'react'
import {
  ChevronRight,
  ChevronDown,
  Shield,
  Map,
  Clock,
  Users,
  Globe,
  Package,
  Zap,
  Star,
} from 'lucide-react'
import type { LoreEntry, LoreCategory } from '@/api/lore'

interface TreeNode {
  id: string
  name: string
  category: LoreCategory
  priority: string
  children: TreeNode[]
  lore?: LoreEntry
}

interface LoreTreeProps {
  loreList: LoreEntry[]
  selectedLoreId?: string
  onSelectLore: (lore: LoreEntry) => void
  relationships?: Array<{
    parent_id: string
    child_id: string
    relationship_type: string
  }>
}

const categoryIcons: Record<LoreCategory, React.ReactNode> = {
  world_rule: <Shield size={16} />,
  geography: <Map size={16} />,
  history: <Clock size={16} />,
  faction: <Users size={16} />,
  culture: <Globe size={16} />,
  race: <Users size={16} />,
  profession: <Package size={16} />,
  character_setting: <Users size={16} />,
  item: <Package size={16} />,
  skill: <Zap size={16} />,
  custom: <Star size={16} />,
}

const categoryLabels: Record<LoreCategory, string> = {
  world_rule: '世界规则',
  geography: '地理设定',
  history: '历史设定',
  faction: '势力组织',
  culture: '文化设定',
  race: '种族设定',
  profession: '职业体系',
  character_setting: '角色设定',
  item: '物品设定',
  skill: '技能体系',
  custom: '自定义',
}

const priorityColors: Record<string, string> = {
  constitutional: 'text-red-600',
  core: 'text-orange-600',
  standard: 'text-blue-600',
  flexible: 'text-gray-600',
}

function TreeNodeItem({
  node,
  level = 0,
  expandedNodes,
  toggleNode,
  selectedLoreId,
  onSelectLore,
}: {
  node: TreeNode
  level?: number
  expandedNodes: Set<string>
  toggleNode: (id: string) => void
  selectedLoreId?: string
  onSelectLore: (lore: LoreEntry) => void
}) {
  const hasChildren = node.children.length > 0
  const isExpanded = expandedNodes.has(node.id)
  const isSelected = selectedLoreId === node.id

  return (
    <div>
      <div
        className={`flex items-center gap-1 px-2 py-1.5 cursor-pointer rounded-lg transition-colors ${
          isSelected ? 'bg-blue-100 text-blue-700' : 'hover:bg-gray-100'
        }`}
        style={{ paddingLeft: `${level * 16 + 8}px` }}
        onClick={() => {
          if (hasChildren) {
            toggleNode(node.id)
          }
          if (node.lore) {
            onSelectLore(node.lore)
          }
        }}
      >
        {/* 展开/收起按钮 */}
        {hasChildren ? (
          <button
            className="p-0.5 hover:bg-gray-200 rounded"
            onClick={(e) => {
              e.stopPropagation()
              toggleNode(node.id)
            }}
          >
            {isExpanded ? (
              <ChevronDown size={14} className="text-gray-500" />
            ) : (
              <ChevronRight size={14} className="text-gray-500" />
            )}
          </button>
        ) : (
          <span className="w-5" />
        )}

        {/* 类别图标 */}
        <span className={`flex-shrink-0 ${priorityColors[node.priority] || ''}`}>
          {categoryIcons[node.category]}
        </span>

        {/* 名称 */}
        <span className="truncate text-sm">{node.name}</span>

        {/* 子节点数量 */}
        {hasChildren && (
          <span className="ml-auto text-xs text-gray-400 bg-gray-100 px-1.5 rounded">
            {node.children.length}
          </span>
        )}
      </div>

      {/* 子节点 */}
      {hasChildren && isExpanded && (
        <div>
          {node.children.map((child) => (
            <TreeNodeItem
              key={child.id}
              node={child}
              level={level + 1}
              expandedNodes={expandedNodes}
              toggleNode={toggleNode}
              selectedLoreId={selectedLoreId}
              onSelectLore={onSelectLore}
            />
          ))}
        </div>
      )}
    </div>
  )
}

export default function LoreTree({
  loreList,
  selectedLoreId,
  onSelectLore,
  relationships = [],
}: LoreTreeProps) {
  const [expandedNodes, setExpandedNodes] = useState<Set<string>>(new Set())

  const toggleNode = (id: string) => {
    setExpandedNodes((prev) => {
      const next = new Set(prev)
      if (next.has(id)) {
        next.delete(id)
      } else {
        next.add(id)
      }
      return next
    })
  }

  const expandAll = () => {
    const allIds = new Set<string>()
    const collectIds = (nodes: TreeNode[]) => {
      nodes.forEach((n) => {
        if (n.children.length > 0) {
          allIds.add(n.id)
          collectIds(n.children)
        }
      })
    }
    collectIds(treeData)
    setExpandedNodes(allIds)
  }

  const collapseAll = () => {
    setExpandedNodes(new Set())
  }

  // 构建树结构
  const treeData = useMemo(() => {
    // 如果有关系数据，构建层级树
    if (relationships.length > 0) {
      const nodeMap: Record<string, TreeNode> = {}
      const childIds: Set<string> = new Set()

      // 初始化所有节点
      loreList.forEach((lore) => {
        nodeMap[lore.id] = {
          id: lore.id,
          name: lore.title,
          category: lore.category,
          priority: lore.priority,
          children: [],
          lore,
        }
      })

      // 根据关系构建树
      relationships.forEach((rel) => {
        const parent = nodeMap[rel.parent_id]
        const child = nodeMap[rel.child_id]
        if (parent && child) {
          parent.children.push(child)
          childIds.add(rel.child_id)
        }
      })

      // 找出根节点（没有父节点的）
      const roots: TreeNode[] = []
      Object.entries(nodeMap).forEach(([id, node]) => {
        if (!childIds.has(id)) {
          roots.push(node)
        }
      })

      return roots
    }

    // 默认按类别分组
    const categoryGroups: Record<string, TreeNode> = {}

    // 创建类别节点
    Object.entries(categoryLabels).forEach(([cat, label]) => {
      categoryGroups[cat] = {
        id: `category-${cat}`,
        name: label,
        category: cat as LoreCategory,
        priority: 'standard',
        children: [],
      }
    })

    // 将设定添加到对应类别
    loreList.forEach((lore) => {
      const group = categoryGroups[lore.category]
      if (group) {
        group.children.push({
          id: lore.id,
          name: lore.title,
          category: lore.category,
          priority: lore.priority,
          children: [],
          lore,
        })
      }
    })

    // 过滤空类别
    return Object.values(categoryGroups).filter((g) => g.children.length > 0)
  }, [loreList, relationships])

  // 统计信息
  const stats = useMemo(() => {
    const byCategory: Record<string, number> = {}
    const byPriority: Record<string, number> = {}

    loreList.forEach((lore) => {
      byCategory[lore.category] = (byCategory[lore.category] || 0) + 1
      byPriority[lore.priority] = (byPriority[lore.priority] || 0) + 1
    })

    return { byCategory, byPriority, total: loreList.length }
  }, [loreList])

  if (loreList.length === 0) {
    return (
      <div className="text-center py-8 text-gray-500">
        <Star size={32} className="mx-auto mb-2 opacity-50" />
        <p className="text-sm">暂无设定数据</p>
      </div>
    )
  }

  return (
    <div className="h-full flex flex-col">
      {/* 头部工具栏 */}
      <div className="flex items-center justify-between px-2 py-2 border-b bg-gray-50">
        <span className="text-sm font-medium text-gray-700">
          设定树 ({stats.total})
        </span>
        <div className="flex gap-1">
          <button
            onClick={expandAll}
            className="text-xs text-blue-600 hover:text-blue-700 px-2 py-1 hover:bg-blue-50 rounded"
          >
            全部展开
          </button>
          <button
            onClick={collapseAll}
            className="text-xs text-gray-600 hover:text-gray-700 px-2 py-1 hover:bg-gray-100 rounded"
          >
            全部收起
          </button>
        </div>
      </div>

      {/* 树结构 */}
      <div className="flex-1 overflow-y-auto py-2">
        {treeData.map((node) => (
          <TreeNodeItem
            key={node.id}
            node={node}
            expandedNodes={expandedNodes}
            toggleNode={toggleNode}
            selectedLoreId={selectedLoreId}
            onSelectLore={onSelectLore}
          />
        ))}
      </div>

      {/* 底部统计 */}
      <div className="border-t px-2 py-2 bg-gray-50">
        <div className="flex flex-wrap gap-2 text-xs">
          {Object.entries(stats.byPriority).map(([priority, count]) => (
            <span
              key={priority}
              className={`px-2 py-0.5 rounded ${priorityColors[priority] || 'text-gray-600'} bg-white border`}
            >
              {priority}: {count}
            </span>
          ))}
        </div>
      </div>
    </div>
  )
}
