/**
 * 地图视图组件
 * v5.1 功能：显示世界地图、角色位置、区域活动
 */

import React, { useState, useEffect, useRef } from 'react'
import { MapPin, Users, Cloud, Sun, CloudRain, CloudSnow, Wind, Thermometer } from 'lucide-react'

interface Location {
  id: string
  name: string
  description?: string
  type?: string
  x: number
  y: number
  characters?: CharacterPosition[]
  environment?: EnvironmentCondition
}

interface CharacterPosition {
  id: string
  name: string
  location_id: string
}

interface EnvironmentCondition {
  weather?: string
  temperature?: number
  light_level?: string
  safety_level?: number
}

interface MapViewProps {
  worldId: string
  locations?: Location[]
  characterPositions?: CharacterPosition[]
  selectedLocation?: string
  onLocationSelect?: (locationId: string) => void
  onCharacterSelect?: (characterId: string) => void
}

export default function MapView({
  worldId,
  locations = [],
  characterPositions = [],
  selectedLocation,
  onLocationSelect,
  onCharacterSelect
}: MapViewProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const [hoveredLocation, setHoveredLocation] = useState<Location | null>(null)
  const [zoom, setZoom] = useState(1)
  const [pan, setPan] = useState({ x: 0, y: 0 })
  const [isDragging, setIsDragging] = useState(false)
  const [dragStart, setDragStart] = useState({ x: 0, y: 0 })

  // 默认位置（如果没有提供位置数据）
  const defaultLocations: Location[] = [
    { id: 'loc1', name: '王都', type: 'city', x: 400, y: 200, environment: { weather: 'sunny' } },
    { id: 'loc2', name: '北境森林', type: 'forest', x: 200, y: 100, environment: { weather: 'cloudy' } },
    { id: 'loc3', name: '东海港口', type: 'port', x: 600, y: 300, environment: { weather: 'rainy' } },
    { id: 'loc4', name: '火山地带', type: 'danger', x: 500, y: 400, environment: { weather: 'stormy' } },
    { id: 'loc5', name: '隐秘山谷', type: 'hidden', x: 300, y: 350, environment: { weather: 'sunny' } },
  ]

  const displayLocations = locations.length > 0 ? locations : defaultLocations

  // 绘制地图
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

    // 绘制背景网格
    drawGrid(ctx, canvas.width, canvas.height)

    // 绘制连接线
    drawConnections(ctx, displayLocations)

    // 绘制地点
    displayLocations.forEach(location => {
      drawLocation(ctx, location, location.id === selectedLocation)
    })

    ctx.restore()
  }, [displayLocations, selectedLocation, zoom, pan])

  const drawGrid = (ctx: CanvasRenderingContext2D, width: number, height: number) => {
    ctx.strokeStyle = '#e5e7eb'
    ctx.lineWidth = 0.5

    for (let x = 0; x < width; x += 50) {
      ctx.beginPath()
      ctx.moveTo(x, 0)
      ctx.lineTo(x, height)
      ctx.stroke()
    }

    for (let y = 0; y < height; y += 50) {
      ctx.beginPath()
      ctx.moveTo(0, y)
      ctx.lineTo(width, y)
      ctx.stroke()
    }
  }

  const drawConnections = (ctx: CanvasRenderingContext2D, locations: Location[]) => {
    ctx.strokeStyle = '#d1d5db'
    ctx.lineWidth = 1
    ctx.setLineDash([5, 5])

    // 简单连接相邻地点
    for (let i = 0; i < locations.length - 1; i++) {
      ctx.beginPath()
      ctx.moveTo(locations[i].x, locations[i].y)
      ctx.lineTo(locations[i + 1].x, locations[i + 1].y)
      ctx.stroke()
    }
    ctx.setLineDash([])
  }

  const drawLocation = (ctx: CanvasRenderingContext2D, location: Location, isSelected: boolean) => {
    const { x, y, name, type, characters, environment } = location
    const radius = isSelected ? 25 : 20

    // 绘制圆形背景
    ctx.beginPath()
    ctx.arc(x, y, radius, 0, Math.PI * 2)

    // 根据类型设置颜色
    const colors: Record<string, string> = {
      city: '#3b82f6',
      forest: '#22c55e',
      port: '#06b6d4',
      danger: '#ef4444',
      hidden: '#8b5cf6',
      default: '#6b7280'
    }
    ctx.fillStyle = colors[type || 'default'] || colors.default
    ctx.fill()

    // 选中状态
    if (isSelected) {
      ctx.strokeStyle = '#fbbf24'
      ctx.lineWidth = 3
      ctx.stroke()
    }

    // 绘制天气图标
    const weather = environment?.weather
    if (weather) {
      ctx.font = '12px serif'
      ctx.fillStyle = '#ffffff'
      ctx.textAlign = 'center'
      const weatherIcon = getWeatherIcon(weather)
      ctx.fillText(weatherIcon, x, y + 5)
    }

    // 绘制角色数量
    if (characters && characters.length > 0) {
      ctx.beginPath()
      ctx.arc(x + 15, y - 15, 10, 0, Math.PI * 2)
      ctx.fillStyle = '#fbbf24'
      ctx.fill()

      ctx.font = 'bold 10px sans-serif'
      ctx.fillStyle = '#000000'
      ctx.textAlign = 'center'
      ctx.fillText(String(characters.length), x + 15, y - 12)
    }

    // 绘制地点名称
    ctx.font = '12px sans-serif'
    ctx.fillStyle = '#1f2937'
    ctx.textAlign = 'center'
    ctx.fillText(name, x, y + radius + 15)
  }

  const getWeatherIcon = (weather: string): string => {
    const icons: Record<string, string> = {
      sunny: '☀',
      cloudy: '☁',
      rainy: '🌧',
      stormy: '⛈',
      snowy: '❄',
      windy: '💨'
    }
    return icons[weather] || '🌤'
  }

  const handleCanvasClick = (e: React.MouseEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current
    if (!canvas) return

    const rect = canvas.getBoundingClientRect()
    const x = (e.clientX - rect.left - pan.x) / zoom
    const y = (e.clientY - rect.top - pan.y) / zoom

    // 检查是否点击了某个地点
    const clickedLocation = displayLocations.find(loc => {
      const distance = Math.sqrt((loc.x - x) ** 2 + (loc.y - y) ** 2)
      return distance < 25
    })

    if (clickedLocation && onLocationSelect) {
      onLocationSelect(clickedLocation.id)
    }
  }

  const handleMouseDown = (e: React.MouseEvent) => {
    setIsDragging(true)
    setDragStart({ x: e.clientX - pan.x, y: e.clientY - pan.y })
  }

  const handleMouseMove = (e: React.MouseEvent) => {
    if (isDragging) {
      setPan({
        x: e.clientX - dragStart.x,
        y: e.clientY - dragStart.y
      })
    }

    // 检测悬停
    const canvas = canvasRef.current
    if (!canvas) return

    const rect = canvas.getBoundingClientRect()
    const x = (e.clientX - rect.left - pan.x) / zoom
    const y = (e.clientY - rect.top - pan.y) / zoom

    const hovered = displayLocations.find(loc => {
      const distance = Math.sqrt((loc.x - x) ** 2 + (loc.y - y) ** 2)
      return distance < 25
    })

    setHoveredLocation(hovered || null)
  }

  const handleMouseUp = () => {
    setIsDragging(false)
  }

  const handleWheel = (e: React.WheelEvent) => {
    e.preventDefault()
    const delta = e.deltaY > 0 ? 0.9 : 1.1
    setZoom(prev => Math.max(0.5, Math.min(2, prev * delta)))
  }

  const getLocationTypeInfo = (type?: string): { label: string; color: string } => {
    const types: Record<string, { label: string; color: string }> = {
      city: { label: '城市', color: 'bg-blue-100 text-blue-800' },
      forest: { label: '森林', color: 'bg-green-100 text-green-800' },
      port: { label: '港口', color: 'bg-cyan-100 text-cyan-800' },
      danger: { label: '危险区', color: 'bg-red-100 text-red-800' },
      hidden: { label: '隐秘地', color: 'bg-purple-100 text-purple-800' },
    }
    return types[type || ''] || { label: '未知', color: 'bg-gray-100 text-gray-800' }
  }

  return (
    <div className="h-full flex flex-col">
      {/* 控制栏 */}
      <div className="flex items-center justify-between px-4 py-2 border-b border-gray-200 bg-gray-50">
        <div className="flex items-center gap-4">
          <span className="text-sm text-gray-600">缩放: {(zoom * 100).toFixed(0)}%</span>
          <button
            onClick={() => setZoom(1)}
            className="text-xs text-blue-600 hover:underline"
          >
            重置
          </button>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs text-gray-500">滚轮缩放 · 拖拽移动</span>
        </div>
      </div>

      {/* 地图画布 */}
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
        {hoveredLocation && (
          <div className="absolute top-4 left-4 bg-white border border-gray-200 rounded-lg shadow-lg p-4 max-w-xs">
            <div className="flex items-center gap-2 mb-2">
              <MapPin className="w-5 h-5 text-blue-600" />
              <span className="font-bold text-gray-800">{hoveredLocation.name}</span>
              <span className={`text-xs px-2 py-0.5 rounded ${getLocationTypeInfo(hoveredLocation.type).color}`}>
                {getLocationTypeInfo(hoveredLocation.type).label}
              </span>
            </div>
            {hoveredLocation.description && (
              <p className="text-sm text-gray-600 mb-2">{hoveredLocation.description}</p>
            )}
            {hoveredLocation.environment && (
              <div className="flex items-center gap-4 text-xs text-gray-500">
                {hoveredLocation.environment.weather && (
                  <span className="flex items-center gap-1">
                    {getWeatherIcon(hoveredLocation.environment.weather)} {hoveredLocation.environment.weather}
                  </span>
                )}
                {hoveredLocation.environment.temperature && (
                  <span className="flex items-center gap-1">
                    🌡 {hoveredLocation.environment.temperature}°C
                  </span>
                )}
              </div>
            )}
            {hoveredLocation.characters && hoveredLocation.characters.length > 0 && (
              <div className="mt-2 pt-2 border-t border-gray-100">
                <div className="flex items-center gap-1 text-xs text-gray-500">
                  <Users className="w-3 h-3" />
                  <span>{hoveredLocation.characters.length} 个角色在此</span>
                </div>
              </div>
            )}
          </div>
        )}

        {/* 图例 */}
        <div className="absolute bottom-4 right-4 bg-white border border-gray-200 rounded-lg shadow p-3">
          <div className="text-xs font-medium text-gray-700 mb-2">图例</div>
          <div className="grid grid-cols-2 gap-2 text-xs">
            <div className="flex items-center gap-2">
              <div className="w-3 h-3 rounded-full bg-blue-500" />
              <span>城市</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-3 h-3 rounded-full bg-green-500" />
              <span>森林</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-3 h-3 rounded-full bg-cyan-500" />
              <span>港口</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-3 h-3 rounded-full bg-red-500" />
              <span>危险区</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}