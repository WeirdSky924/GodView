/**
 * 事件流显示组件
 * v5.1 功能：实时显示世界事件流
 */

import React, { useState, useEffect, useRef } from 'react'
import {
  Calendar, Clock, Users, MapPin, Zap, AlertCircle,
  Heart, Sword, MessageSquare, Star, TrendingUp, Filter,
  ChevronDown, ChevronUp, Search, X, RefreshCw
} from 'lucide-react'

interface WorldEvent {
  id: string
  timestamp: string
  event_type: string
  title: string
  description: string
  severity: 'low' | 'medium' | 'high' | 'critical'
  involved_characters?: string[]
  location?: string
  tags?: string[]
  metadata?: Record<string, any>
}

interface EventStreamProps {
  worldId: string
  events?: WorldEvent[]
  realTime?: boolean
  onEventSelect?: (eventId: string) => void
  onFilterChange?: (filters: EventFilters) => void
}

interface EventFilters {
  event_types: string[]
  severities: string[]
  time_range?: {
    start: string
    end: string
  }
  search?: string
}

export default function EventStream({
  worldId,
  events = [],
  realTime = true,
  onEventSelect,
  onFilterChange
}: EventStreamProps) {
  const [filteredEvents, setFilteredEvents] = useState<WorldEvent[]>(events)
  const [filters, setFilters] = useState<EventFilters>({
    event_types: [],
    severities: []
  })
  const [searchQuery, setSearchQuery] = useState('')
  const [showFilters, setShowFilters] = useState(false)
  const [selectedEvent, setSelectedEvent] = useState<string | null>(null)
  const [autoScroll, setAutoScroll] = useState(true)
  const eventsEndRef = useRef<HTMLDivElement>(null)

  // 生成默认事件（如果没有提供）
  const generateDefaultEvents = (): WorldEvent[] => {
    const eventTypes = ['social', 'combat', 'discovery', 'weather', 'milestone', 'hazard']
    const severities = ['low', 'medium', 'high', 'critical'] as const
    const locations = ['王都', '北境森林', '东海港口', '火山地带', '隐秘山谷']
    const characters = ['艾伦', '莉娜', '凯文', '索菲亚', '雷克斯', '艾米丽']

    return Array.from({ length: 20 }, (_, i) => {
      const type = eventTypes[Math.floor(Math.random() * eventTypes.length)]
      const severity = severities[Math.floor(Math.random() * severities.length)]
      const hour = (i % 24).toString().padStart(2, '0')
      const minute = (Math.floor(Math.random() * 60)).toString().padStart(2, '0')

      return {
        id: `event_${i}`,
        timestamp: `2026-04-07T${hour}:${minute}:00Z`,
        event_type: type,
        title: getEventTitle(type, i),
        description: getEventDescription(type, i),
        severity,
        involved_characters: characters.slice(0, Math.floor(Math.random() * 3) + 1),
        location: locations[Math.floor(Math.random() * locations.length)],
        tags: getEventTags(type),
        metadata: {
          duration: Math.floor(Math.random() * 60),
          impact_score: Math.random()
        }
      }
    }).sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime())
  }

  const displayEvents = events.length > 0 ? events : generateDefaultEvents()

  // 应用过滤器
  useEffect(() => {
    let result = displayEvents

    // 搜索过滤
    if (searchQuery) {
      const query = searchQuery.toLowerCase()
      result = result.filter(event =>
        event.title.toLowerCase().includes(query) ||
        event.description.toLowerCase().includes(query) ||
        event.tags?.some(tag => tag.toLowerCase().includes(query)) ||
        event.involved_characters?.some(char => char.toLowerCase().includes(query))
      )
    }

    // 事件类型过滤
    if (filters.event_types.length > 0) {
      result = result.filter(event => filters.event_types.includes(event.event_type))
    }

    // 严重程度过滤
    if (filters.severities.length > 0) {
      result = result.filter(event => filters.severities.includes(event.severity))
    }

    setFilteredEvents(result)
  }, [displayEvents, filters, searchQuery])

  // 自动滚动到底部
  useEffect(() => {
    if (autoScroll && eventsEndRef.current) {
      eventsEndRef.current.scrollIntoView({ behavior: 'smooth' })
    }
  }, [filteredEvents, autoScroll])

  const getEventTitle = (type: string, index: number): string => {
    const titles: Record<string, string[]> = {
      social: ['友好会面', '激烈争论', '秘密会议', '浪漫邂逅', '团队合作'],
      combat: ['遭遇战', '伏击', '决斗', '大规模战斗', '撤退'],
      discovery: ['发现宝藏', '找到线索', '揭示秘密', '发现新地点', '学习技能'],
      weather: ['暴风雨', '晴朗天气', '浓雾', '大雪', '干旱'],
      milestone: ['角色成长', '故事转折', '重要决定', '关系突破', '目标达成'],
      hazard: ['自然灾害', '陷阱触发', '疾病爆发', '资源短缺', '危险生物']
    }
    const list = titles[type] || ['未知事件']
    return list[index % list.length]
  }

  const getEventDescription = (type: string, index: number): string => {
    const descriptions: Record<string, string[]> = {
      social: ['角色之间进行了深入的交流', '对话中透露了重要信息', '关系发生了变化', '达成了新的协议'],
      combat: ['战斗激烈进行，双方都有损伤', '战术运用得当，取得了优势', '战斗以平局结束', '一方成功撤退'],
      discovery: ['发现了有价值的物品或信息', '揭开了谜团的一部分', '获得了新的能力或知识', '找到了关键线索'],
      weather: ['天气条件影响了角色的行动', '恶劣天气带来了挑战', '好天气提供了机会', '天气突然变化'],
      milestone: ['故事向前推进了一步', '角色经历了重要成长', '关系达到了新的阶段', '目标更接近完成'],
      hazard: ['危险情况威胁到角色安全', '需要紧急应对的危机', '资源或环境出现问题', '意外障碍出现']
    }
    const list = descriptions[type] || ['发生了某件事']
    return list[index % list.length]
  }

  const getEventTags = (type: string): string[] => {
    const tags: Record<string, string[]> = {
      social: ['社交', '对话', '关系'],
      combat: ['战斗', '冲突', '战术'],
      discovery: ['探索', '发现', '知识'],
      weather: ['环境', '天气', '自然'],
      milestone: ['进展', '成长', '转折'],
      hazard: ['危险', '危机', '挑战']
    }
    return tags[type] || ['事件']
  }

  const getEventIcon = (type: string): JSX.Element => {
    const icons: Record<string, JSX.Element> = {
      social: <Users className="w-4 h-4" />,
      combat: <Sword className="w-4 h-4" />,
      discovery: <Star className="w-4 h-4" />,
      weather: <Zap className="w-4 h-4" />,
      milestone: <TrendingUp className="w-4 h-4" />,
      hazard: <AlertCircle className="w-4 h-4" />
    }
    return icons[type] || <MessageSquare className="w-4 h-4" />
  }

  const getSeverityColor = (severity: string): string => {
    const colors: Record<string, string> = {
      low: 'bg-green-100 text-green-800',
      medium: 'bg-yellow-100 text-yellow-800',
      high: 'bg-orange-100 text-orange-800',
      critical: 'bg-red-100 text-red-800'
    }
    return colors[severity] || 'bg-gray-100 text-gray-800'
  }

  const getEventTypeLabel = (type: string): string => {
    const labels: Record<string, string> = {
      social: '社交',
      combat: '战斗',
      discovery: '发现',
      weather: '天气',
      milestone: '里程碑',
      hazard: '危险'
    }
    return labels[type] || type
  }

  const formatTime = (timestamp: string): string => {
    const date = new Date(timestamp)
    return date.toLocaleTimeString('zh-CN', {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit'
    })
  }

  const formatDate = (timestamp: string): string => {
    const date = new Date(timestamp)
    return date.toLocaleDateString('zh-CN')
  }

  const handleEventClick = (eventId: string) => {
    setSelectedEvent(eventId)
    if (onEventSelect) {
      onEventSelect(eventId)
    }
  }

  const handleFilterToggle = (type: 'event_types' | 'severities', value: string) => {
    setFilters(prev => {
      const current = prev[type]
      const newValues = current.includes(value)
        ? current.filter(v => v !== value)
        : [...current, value]

      const newFilters = { ...prev, [type]: newValues }
      if (onFilterChange) {
        onFilterChange(newFilters)
      }
      return newFilters
    })
  }

  const clearFilters = () => {
    const newFilters: EventFilters = { event_types: [], severities: [] }
    setFilters(newFilters)
    setSearchQuery('')
    if (onFilterChange) {
      onFilterChange(newFilters)
    }
  }

  const eventTypes = ['social', 'combat', 'discovery', 'weather', 'milestone', 'hazard']
  const severities = ['low', 'medium', 'high', 'critical']

  return (
    <div className="h-full flex flex-col">
      {/* 控制栏 */}
      <div className="px-4 py-3 border-b border-gray-200 bg-gray-50">
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-3">
            <Calendar className="w-5 h-5 text-blue-600" />
            <span className="font-medium text-gray-800">事件流</span>
            <span className="text-sm text-gray-600">
              {filteredEvents.length} 个事件
              {filteredEvents.length !== displayEvents.length && ` (已过滤 ${displayEvents.length - filteredEvents.length} 个)`}
            </span>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setAutoScroll(!autoScroll)}
              className={`text-xs px-3 py-1 rounded ${autoScroll ? 'bg-blue-100 text-blue-700' : 'bg-gray-100 text-gray-700'}`}
            >
              {autoScroll ? '自动滚动开启' : '自动滚动关闭'}
            </button>
            <button
              onClick={() => setShowFilters(!showFilters)}
              className="flex items-center gap-1 text-xs px-3 py-1 border border-gray-300 rounded text-gray-700"
            >
              <Filter className="w-3 h-3" />
              {showFilters ? '隐藏筛选' : '显示筛选'}
            </button>
          </div>
        </div>

        {/* 搜索框 */}
        <div className="relative">
          <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-gray-400" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="搜索事件、角色、地点..."
            className="w-full pl-10 pr-10 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm"
          />
          {searchQuery && (
            <button
              onClick={() => setSearchQuery('')}
              className="absolute right-3 top-1/2 transform -translate-y-1/2"
            >
              <X className="w-4 h-4 text-gray-400" />
            </button>
          )}
        </div>

        {/* 筛选器 */}
        {showFilters && (
          <div className="mt-3 p-3 bg-white border border-gray-200 rounded-lg">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm font-medium text-gray-700">筛选条件</span>
              <button
                onClick={clearFilters}
                className="text-xs text-blue-600 hover:underline"
              >
                清除所有
              </button>
            </div>

            <div className="grid grid-cols-2 gap-4">
              {/* 事件类型筛选 */}
              <div>
                <div className="text-xs text-gray-500 mb-1">事件类型</div>
                <div className="flex flex-wrap gap-1">
                  {eventTypes.map(type => (
                    <button
                      key={type}
                      onClick={() => handleFilterToggle('event_types', type)}
                      className={`px-2 py-1 text-xs rounded border ${
                        filters.event_types.includes(type)
                          ? 'bg-blue-100 text-blue-700 border-blue-300'
                          : 'bg-gray-100 text-gray-700 border-gray-300'
                      }`}
                    >
                      {getEventTypeLabel(type)}
                    </button>
                  ))}
                </div>
              </div>

              {/* 严重程度筛选 */}
              <div>
                <div className="text-xs text-gray-500 mb-1">严重程度</div>
                <div className="flex flex-wrap gap-1">
                  {severities.map(severity => (
                    <button
                      key={severity}
                      onClick={() => handleFilterToggle('severities', severity)}
                      className={`px-2 py-1 text-xs rounded border ${getSeverityColor(severity)} ${
                        filters.severities.includes(severity) ? 'border-gray-400' : 'border-transparent'
                      }`}
                    >
                      {severity === 'low' ? '低' :
                       severity === 'medium' ? '中' :
                       severity === 'high' ? '高' : '严重'}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* 事件列表 */}
      <div className="flex-1 overflow-y-auto">
        {filteredEvents.length === 0 ? (
          <div className="h-full flex flex-col items-center justify-center text-gray-500">
            <Calendar className="w-12 h-12 mb-3 text-gray-300" />
            <p>没有找到匹配的事件</p>
            <p className="text-sm mt-1">尝试调整筛选条件</p>
          </div>
        ) : (
          <div className="divide-y divide-gray-100">
            {filteredEvents.map((event) => (
              <div
                key={event.id}
                onClick={() => handleEventClick(event.id)}
                className={`p-4 hover:bg-gray-50 cursor-pointer transition-colors ${
                  selectedEvent === event.id ? 'bg-blue-50 border-l-4 border-blue-500' : ''
                }`}
              >
                <div className="flex items-start gap-3">
                  {/* 事件图标 */}
                  <div className="flex-shrink-0 mt-1">
                    <div className="p-2 rounded-lg bg-gray-100">
                      {getEventIcon(event.event_type)}
                    </div>
                  </div>

                  {/* 事件内容 */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <span className="font-medium text-gray-800 truncate">{event.title}</span>
                      <span className={`text-xs px-2 py-0.5 rounded ${getSeverityColor(event.severity)}`}>
                        {event.severity === 'low' ? '低' :
                         event.severity === 'medium' ? '中' :
                         event.severity === 'high' ? '高' : '严重'}
                      </span>
                      <span className="text-xs text-gray-500 ml-auto flex items-center gap-1">
                        <Clock className="w-3 h-3" />
                        {formatTime(event.timestamp)}
                      </span>
                    </div>

                    <p className="text-sm text-gray-600 mb-2">{event.description}</p>

                    {/* 元信息 */}
                    <div className="flex flex-wrap items-center gap-3 text-xs text-gray-500">
                      {event.location && (
                        <span className="flex items-center gap-1">
                          <MapPin className="w-3 h-3" />
                          {event.location}
                        </span>
                      )}

                      {event.involved_characters && event.involved_characters.length > 0 && (
                        <span className="flex items-center gap-1">
                          <Users className="w-3 h-3" />
                          {event.involved_characters.join(', ')}
                        </span>
                      )}

                      {event.tags && event.tags.length > 0 && (
                        <div className="flex flex-wrap gap-1">
                          {event.tags.map((tag, idx) => (
                            <span key={idx} className="px-1.5 py-0.5 bg-gray-100 rounded">
                              {tag}
                            </span>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            ))}
            <div ref={eventsEndRef} />
          </div>
        )}
      </div>

      {/* 底部状态栏 */}
      <div className="px-4 py-2 border-t border-gray-200 bg-gray-50 flex items-center justify-between text-xs text-gray-500">
        <div className="flex items-center gap-4">
          <span>最后更新: {new Date().toLocaleTimeString('zh-CN')}</span>
          {realTime && (
            <span className="flex items-center gap-1">
              <Zap className="w-3 h-3 text-green-500" />
              实时更新
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          <span>事件类型分布:</span>
          {eventTypes.slice(0, 3).map(type => {
            const count = filteredEvents.filter(e => e.event_type === type).length
            if (count === 0) return null
            return (
              <span key={type} className="flex items-center gap-1">
                {getEventIcon(type)}
                {getEventTypeLabel(type)}: {count}
              </span>
            )
          })}
          {eventTypes.slice(3).some(type => filteredEvents.filter(e => e.event_type === type).length > 0) && (
            <span>...</span>
          )}
        </div>
      </div>
    </div>
  )
}