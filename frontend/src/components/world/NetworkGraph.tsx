/**
 * 关系网络图组件
 * v5.1 功能：可视化角色关系网络
 */

import React, { useState, useEffect, useRef } from 'react'
import { Users, Heart, Sword, Shield, MessageSquare, Target, Zap, Star } from 'lucide-react'

interface CharacterNode {
  id: string
  name: string
  type: 'main' | 'supporting' | 'antagonist' | 'npc'
  x: number
  y: number
  size: number
  color: string
}

interface RelationshipEdge {
  id: string
  source: string
  target: string
  type: 'friendship' | 'rivalry' | 'romance' | 'family' | 'mentorship' | 'enemy'
  strength: number // 0-1
  label?: string
}

interface NetworkGraphProps {
  worldId: string
  characters?: CharacterNode[]
  relationships?: RelationshipEdge[]
  selectedNode?: string
  onNodeSelect?: (nodeId: string) => void
  onEdgeSelect?: (edgeId: string) => void
}

export default function NetworkGraph({
  worldId,
  characters = [],
  relationships = [],
  selectedNode,
  onNodeSelect,
  onEdgeSelect
}: NetworkGraphProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const [hoveredNode, setHoveredNode] = useState<CharacterNode | null>(null)
  const [hoveredEdge, setHoveredEdge] = useState<RelationshipEdge | null>(null)
  const [zoom, setZoom] = useState(1)
  const [pan, setPan] = useState({ x: 0, y: 0 })
  const [isDragging, setIsDragging] = useState(false)
  const [dragStart, setDragStart] = useState({ x: 0, y: 0 })
  const [selectedEdge, setSelectedEdge] = useState<string | null>(null)

  // 生成默认数据（如果没有提供）
  const generateDefaultCharacters = (): CharacterNode[] => {
    const types = ['main', 'supporting', 'antagonist', 'npc'] as const
    const colors = {
      main: '#3b82f6',
      supporting: '#10b981',
      antagonist: '#ef4444',
      npc: '#6b7280'
    }

    return Array.from({ length: 8 }, (_, i) => ({
      id: `char${i}`,
      name: `角色${i}`,
      type: types[i % types.length],
      x: 300 + Math.cos(i * Math.PI / 4) * 200,
      y: 300 + Math.sin(i * Math.PI / 4) * 200,
      size: i === 0 ? 40 : [30, 25, 20][i % 3],
      color: colors[types[i % types.length]]
    }))
  }

  const generateDefaultRelationships = (chars: CharacterNode[]): RelationshipEdge[] => {
    const types = ['friendship', 'rivalry', 'romance', 'family', 'mentorship', 'enemy'] as const
    const edges: RelationshipEdge[] = []

    for (let i = 0; i < chars.length; i++) {
      for (let j = i + 1; j < chars.length; j++) {
        if (Math.random() > 0.6) {
          const type = types[Math.floor(Math.random() * types.length)]
          const strength = Math.random()
          edges.push({
            id: `edge_${i}_${j}`,
            source: chars[i].id,
            target: chars[j].id,
            type,
            strength,
            label: getEdgeLabel(type)
          })
        }
      }
    }

    return edges
  }

  const defaultCharacters = generateDefaultCharacters()
  const defaultRelationships = generateDefaultRelationships(defaultCharacters)

  const displayCharacters = characters.length > 0 ? characters : defaultCharacters
  const displayRelationships = relationships.length > 0 ? relationships : defaultRelationships

  // 绘制网络图
  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return

    const ctx = canvas.getContext('2d')
    if (!ctx) return

    // 清空画布
    ctx.clearRect(0, 0, canvas.width, canvas.height)

    // 应用变换
    ctx.save()
    ctx.translate(pan.x, pan.y)
    ctx.scale(zoom, zoom)

    // 绘制边
    displayRelationships.forEach(edge => {
      drawEdge(ctx, edge, displayCharacters, edge.id === selectedEdge)
    })

    // 绘制节点
    displayCharacters.forEach(node => {
      drawNode(ctx, node, node.id === selectedNode)
    })

    ctx.restore()
  }, [displayCharacters, displayRelationships, selectedNode, selectedEdge, zoom, pan])

  const getEdgeLabel = (type: string): string => {
    const labels: Record<string, string> = {
      friendship: '友谊',
      rivalry: '竞争',
      romance: '浪漫',
      family: '家庭',
      mentorship: '师徒',
      enemy: '敌对'
    }
    return labels[type] || type
  }

  const getEdgeColor = (type: string, strength: number): string => {
    const baseColors: Record<string, string> = {
      friendship: '#10b981',
      rivalry: '#f59e0b',
      romance: '#ec4899',
      family: '#8b5cf6',
      mentorship: '#06b6d4',
      enemy: '#ef4444'
    }

    const color = baseColors[type] || '#6b7280'
    // 根据强度调整透明度
    const alpha = Math.floor(strength * 255).toString(16).padStart(2, '0')
    return `${color}${alpha}`
  }

  const drawEdge = (
    ctx: CanvasRenderingContext2D,
    edge: RelationshipEdge,
    nodes: CharacterNode[],
    isSelected: boolean
  ) => {
    const source = nodes.find(n => n.id === edge.source)
    const target = nodes.find(n => n.id === edge.target)
    if (!source || !target) return

    ctx.beginPath()
    ctx.moveTo(source.x, source.y)
    ctx.lineTo(target.x, target.y)

    // 设置线条样式
    const color = getEdgeColor(edge.type, edge.strength)
    ctx.strokeStyle = color
    ctx.lineWidth = isSelected ? 5 : 2 + edge.strength * 3
    if (isSelected) {
      ctx.setLineDash([5, 3])
    }
    ctx.stroke()

    // 恢复虚线
    if (isSelected) {
      ctx.setLineDash([])
    }

    // 绘制边标签（在中间）
    if (edge.label) {
      const midX = (source.x + target.x) / 2
      const midY = (source.y + target.y) / 2

      // 背景框
      ctx.fillStyle = 'rgba(255, 255, 255, 0.9)'
      ctx.fillRect(midX - 30, midY - 10, 60, 20)

      // 边框
      ctx.strokeStyle = color
      ctx.lineWidth = 1
      ctx.strokeRect(midX - 30, midY - 10, 60, 20)

      // 文字
      ctx.font = 'bold 10px sans-serif'
      ctx.fillStyle = '#1f2937'
      ctx.textAlign = 'center'
      ctx.textBaseline = 'middle'
      ctx.fillText(edge.label, midX, midY)
    }
  }

  const drawNode = (ctx: CanvasRenderingContext2D, node: CharacterNode, isSelected: boolean) => {
    const { x, y, size, color, type } = node
    const radius = size

    // 绘制圆形节点
    ctx.beginPath()
    ctx.arc(x, y, radius, 0, Math.PI * 2)

    // 填充颜色
    ctx.fillStyle = color
    ctx.fill()

    // 选中状态
    if (isSelected) {
      ctx.strokeStyle = '#fbbf24'
      ctx.lineWidth = 3
      ctx.stroke()
    }

    // 绘制外圈
    ctx.beginPath()
    ctx.arc(x, y, radius + 2, 0, Math.PI * 2)
    ctx.strokeStyle = 'rgba(255, 255, 255, 0.8)'
    ctx.lineWidth = 2
    ctx.stroke()

    // 绘制角色图标
    const icon = getNodeIcon(type)
    ctx.font = '20px sans-serif'
    ctx.fillStyle = '#ffffff'
    ctx.textAlign = 'center'
    ctx.textBaseline = 'middle'
    ctx.fillText(icon, x, y)

    // 绘制角色名称
    ctx.font = '12px sans-serif'
    ctx.fillStyle = '#1f2937'
    ctx.textAlign = 'center'
    ctx.fillText(node.name, x, y + radius + 15)
  }

  const getNodeIcon = (type: string): string => {
    const icons: Record<string, string> = {
      main: '👑',
      supporting: '🛡',
      antagonist: '🗡',
      npc: '👤'
    }
    return icons[type] || '👤'
  }

  const getNodeTypeInfo = (type: string): { label: string; icon: JSX.Element } => {
    const types: Record<string, { label: string; icon: JSX.Element }> = {
      main: { label: '主角', icon: <Star className="w-4 h-4" /> },
      supporting: { label: '配角', icon: <Shield className="w-4 h-4" /> },
      antagonist: { label: '反派', icon: <Sword className="w-4 h-4" /> },
      npc: { label: 'NPC', icon: <Users className="w-4 h-4" /> }
    }
    return types[type] || { label: '未知', icon: <Users className="w-4 h-4" /> }
  }

  const getEdgeTypeInfo = (type: string): { label: string; icon: JSX.Element } => {
    const types: Record<string, { label: string; icon: JSX.Element }> = {
      friendship: { label: '友谊', icon: <Heart className="w-4 h-4" /> },
      rivalry: { label: '竞争', icon: <Target className="w-4 h-4" /> },
      romance: { label: '浪漫', icon: <Heart className="w-4 h-4" /> },
      family: { label: '家庭', icon: <Users className="w-4 h-4" /> },
      mentorship: { label: '师徒', icon: <Zap className="w-4 h-4" /> },
      enemy: { label: '敌对', icon: <Sword className="w-4 h-4" /> }
    }
    return types[type] || { label: '关系', icon: <MessageSquare className="w-4 h-4" /> }
  }

  const handleCanvasClick = (e: React.MouseEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current
    if (!canvas) return

    const rect = canvas.getBoundingClientRect()
    const x = (e.clientX - rect.left - pan.x) / zoom
    const y = (e.clientY - rect.top - pan.y) / zoom

    // 检查是否点击了节点
    const clickedNode = displayCharacters.find(node => {
      const distance = Math.sqrt((node.x - x) ** 2 + (node.y - y) ** 2)
      return distance < node.size
    })

    if (clickedNode) {
      setSelectedEdge(null)
      if (onNodeSelect) {
        onNodeSelect(clickedNode.id)
      }
      return
    }

    // 检查是否点击了边（简化：检查附近的所有边）
    for (const edge of displayRelationships) {
      const source = displayCharacters.find(n => n.id === edge.source)
      const target = displayCharacters.find(n => n.id === edge.target)
      if (!source || !target) continue

      // 计算点到线段的距离
      const distance = pointToLineDistance(x, y, source.x, source.y, target.x, target.y)
      if (distance < 10) {
        setSelectedEdge(edge.id)
        if (onEdgeSelect) {
          onEdgeSelect(edge.id)
        }
        return
      }
    }

    // 点击空白处
    setSelectedEdge(null)
    if (onNodeSelect) {
      onNodeSelect('')
    }
  }

  const pointToLineDistance = (px: number, py: number, x1: number, y1: number, x2: number, y2: number): number => {
    const A = px - x1
    const B = py - y1
    const C = x2 - x1
    const D = y2 - y1

    const dot = A * C + B * D
    const lenSq = C * C + D * D
    let param = -1
    if (lenSq !== 0) param = dot / lenSq

    let xx, yy
    if (param < 0) {
      xx = x1
      yy = y1
    } else if (param > 1) {
      xx = x2
      yy = y2
    } else {
      xx = x1 + param * C
      yy = y1 + param * D
    }

    const dx = px - xx
    const dy = py - yy
    return Math.sqrt(dx * dx + dy * dy)
  }

  const handleMouseMove = (e: React.MouseEvent) => {
    if (isDragging) {
      setPan({
        x: e.clientX - dragStart.x,
        y: e.clientY - dragStart.y
      })
      return
    }

    // 检测悬停
    const canvas = canvasRef.current
    if (!canvas) return

    const rect = canvas.getBoundingClientRect()
    const x = (e.clientX - rect.left - pan.x) / zoom
    const y = (e.clientY - rect.top - pan.y) / zoom

    // 检查节点悬停
    const hovered = displayCharacters.find(node => {
      const distance = Math.sqrt((node.x - x) ** 2 + (node.y - y) ** 2)
      return distance < node.size
    })
    setHoveredNode(hovered || null)

    // 检查边悬停
    let edgeHovered = null
    for (const edge of displayRelationships) {
      const source = displayCharacters.find(n => n.id === edge.source)
      const target = displayCharacters.find(n => n.id === edge.target)
      if (!source || !target) continue

      const distance = pointToLineDistance(x, y, source.x, source.y, target.x, target.y)
      if (distance < 10) {
        edgeHovered = edge
        break
      }
    }
    setHoveredEdge(edgeHovered)
  }

  const handleMouseDown = (e: React.MouseEvent) => {
    setIsDragging(true)
    setDragStart({ x: e.clientX - pan.x, y: e.clientY - pan.y })
  }

  const handleMouseUp = () => {
    setIsDragging(false)
  }

  const handleWheel = (e: React.WheelEvent) => {
    e.preventDefault()
    const delta = e.deltaY > 0 ? 0.9 : 1.1
    setZoom(prev => Math.max(0.5, Math.min(2, prev * delta)))
  }

  const getStrengthLabel = (strength: number): string => {
    if (strength > 0.8) return '非常强'
    if (strength > 0.6) return '强'
    if (strength > 0.4) return '中等'
    if (strength > 0.2) return '弱'
    return '非常弱'
  }

  return (
    <div className="h-full flex flex-col">
      {/* 控制栏 */}
      <div className="flex items-center justify-between px-4 py-2 border-b border-gray-200 bg-gray-50">
        <div className="flex items-center gap-4">
          <Users className="w-5 h-5 text-blue-600" />
          <span className="font-medium text-gray-800">关系网络图</span>
          <span className="text-sm text-gray-600">
            {displayCharacters.length} 个角色，{displayRelationships.length} 条关系
          </span>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={() => setZoom(1)}
            className="text-xs text-blue-600 hover:underline"
          >
            重置视图
          </button>
        </div>
      </div>

      {/* 画布区域 */}
      <div className="flex-1 relative overflow-hidden">
        <canvas
          ref={canvasRef}
          width={800}
          height={600}
          className="w-full h-full cursor-grab active:cursor-grabbing"
          onClick={handleCanvasClick}
          onMouseDown={handleMouseDown}
          onMouseMove={handleMouseMove}
          onMouseUp={handleMouseUp}
          onMouseLeave={handleMouseUp}
          onWheel={handleWheel}
        />

        {/* 悬停信息 */}
        {hoveredNode && (
          <div className="absolute top-4 left-4 bg-white border border-gray-200 rounded-lg shadow-lg p-4 max-w-xs">
            <div className="flex items-center gap-2 mb-2">
              <div className="w-3 h-3 rounded-full" style={{ backgroundColor: hoveredNode.color }} />
              <span className="font-bold text-gray-800">{hoveredNode.name}</span>
              <div className="flex items-center gap-1 ml-auto text-xs px-2 py-0.5 bg-gray-100 text-gray-700 rounded">
                {getNodeTypeInfo(hoveredNode.type).icon}
                {getNodeTypeInfo(hoveredNode.type).label}
              </div>
            </div>
            <div className="text-sm text-gray-600">
              与其他 {displayRelationships.filter(r => r.source === hoveredNode.id || r.target === hoveredNode.id).length} 个角色有关系
            </div>
          </div>
        )}

        {hoveredEdge && (
          <div className="absolute bottom-4 left-4 bg-white border border-gray-200 rounded-lg shadow-lg p-4 max-w-xs">
            <div className="flex items-center gap-2 mb-2">
              {getEdgeTypeInfo(hoveredEdge.type).icon}
              <span className="font-bold text-gray-800">{getEdgeLabel(hoveredEdge.type)}</span>
              <span className="ml-auto text-xs px-2 py-0.5 bg-gray-100 text-gray-700 rounded">
                强度: {getStrengthLabel(hoveredEdge.strength)}
              </span>
            </div>
            <div className="text-sm text-gray-600">
              连接：{displayCharacters.find(c => c.id === hoveredEdge.source)?.name} 和 {displayCharacters.find(c => c.id === hoveredEdge.target)?.name}
            </div>
          </div>
        )}

        {/* 图例 */}
        <div className="absolute bottom-4 right-4 bg-white border border-gray-200 rounded-lg shadow p-3 max-w-xs">
          <div className="text-xs font-medium text-gray-700 mb-2">图例</div>
          <div className="space-y-2">
            {/* 节点类型 */}
            <div>
              <div className="text-xs text-gray-500 mb-1">节点类型</div>
              <div className="grid grid-cols-2 gap-1 text-xs">
                {['main', 'supporting', 'antagonist', 'npc'].map(type => {
                  const info = getNodeTypeInfo(type)
                  return (
                    <div key={type} className="flex items-center gap-2">
                      <div className="w-3 h-3 rounded-full" style={{
                        backgroundColor: {
                          main: '#3b82f6',
                          supporting: '#10b981',
                          antagonist: '#ef4444',
                          npc: '#6b7280'
                        }[type]
                      }} />
                      <span>{info.label}</span>
                    </div>
                  )
                })}
              </div>
            </div>

            {/* 关系类型 */}
            <div>
              <div className="text-xs text-gray-500 mb-1">关系类型</div>
              <div className="grid grid-cols-2 gap-1 text-xs">
                {['friendship', 'rivalry', 'romance', 'enemy'].map(type => {
                  const info = getEdgeTypeInfo(type)
                  return (
                    <div key={type} className="flex items-center gap-2">
                      <div className="w-3 h-3 rounded" style={{
                        backgroundColor: getEdgeColor(type, 0.7)
                      }} />
                      <span>{info.label}</span>
                    </div>
                  )
                })}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}