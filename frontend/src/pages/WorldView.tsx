/**
 * 世界观测页面
 * GodView v5 世界观测系统的主要界面
 */

import React, { useState, useEffect } from 'react'
import { Globe, Activity, Clock, TrendingUp } from 'lucide-react'
import TimeControlPanel from '@/components/time/TimeControlPanel'
import { useTimeControl, useTimeHistory } from '@/hooks/useTimeWebSocket'
import { getWorlds, type World } from '@/api/worlds'

export default function WorldView() {
  const [worlds, setWorlds] = useState<World[]>([])
  const [selectedWorldId, setSelectedWorldId] = useState('')
  const [loading, setLoading] = useState(true)

  const timeControl = useTimeControl(selectedWorldId)
  const timeHistory = useTimeHistory(selectedWorldId)

  // 加载世界列表
  useEffect(() => {
    loadWorlds()
  }, [])

  // 当选择世界时，初始化时间系统
  useEffect(() => {
    if (selectedWorldId) {
      initializeTimeSystem()
    }
  }, [selectedWorldId])

  const loadWorlds = async () => {
    try {
      const result = await getWorlds()
      setWorlds(result)
      if (result.length > 0 && !selectedWorldId) {
        setSelectedWorldId(result[0].id)
      }
    } catch (error) {
      console.error('Failed to load worlds:', error)
    } finally {
      setLoading(false)
    }
  }

  const initializeTimeSystem = async () => {
    // 这里可以调用API来初始化时间系统
    console.log('Initializing time system for world:', selectedWorldId)
  }

  if (loading) {
    return (
      <div className="h-screen flex items-center justify-center">
        <div className="text-gray-500">加载中...</div>
      </div>
    )
  }

  if (!selectedWorldId) {
    return (
      <div className="h-screen flex items-center justify-center">
        <div className="text-gray-500">暂无世界，请先创建世界</div>
      </div>
    )
  }

  const selectedWorld = worlds.find(w => w.id === selectedWorldId)

  return (
    <div className="h-screen bg-gray-50 flex flex-col">
      {/* 顶部导航 */}
      <div className="bg-white border-b border-gray-200 px-6 py-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <Globe className="w-8 h-8 text-blue-600" />
            <div>
              <h1 className="text-2xl font-bold text-gray-800">世界观测</h1>
              <p className="text-sm text-gray-500">GodView v5 世界生命模拟器</p>
            </div>
          </div>

          {/* 世界选择器 */}
          <div className="flex items-center gap-4">
            <select
              value={selectedWorldId}
              onChange={(e) => setSelectedWorldId(e.target.value)}
              className="px-4 py-2 border border-gray-300 rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              {worlds.map((world) => (
                <option key={world.id} value={world.id}>
                  {world.name || world.id}
                </option>
              ))}
            </select>
          </div>
        </div>

        {/* 状态指示器 */}
        {selectedWorld && (
          <div className="mt-4 flex items-center gap-6 text-sm">
            <div className="flex items-center gap-2">
              <Activity className="w-4 h-4 text-green-600" />
              <span className="text-gray-600">
                状态: {timeControl.isFrozen ? '时间冻结' : '正常运行'}
              </span>
            </div>
            {timeControl.currentTime && (
              <div className="flex items-center gap-2">
                <Clock className="w-4 h-4 text-blue-600" />
                <span className="text-gray-600">
                  世界时间: {new Date(timeControl.currentTime).toLocaleString('zh-CN')}
                </span>
              </div>
            )}
            {timeControl.tickCount !== null && (
              <div className="flex items-center gap-2">
                <TrendingUp className="w-4 h-4 text-purple-600" />
                <span className="text-gray-600">
                  时钟周期: {timeControl.tickCount}
                </span>
              </div>
            )}
          </div>
        )}
      </div>

      {/* 主内容区域 */}
      <div className="flex-1 flex overflow-hidden">
        {/* 左侧面板 - 时间控制 */}
        <div className="w-96 border-r border-gray-200 bg-white overflow-y-auto">
          <TimeControlPanel worldId={selectedWorldId} />
        </div>

        {/* 中间区域 - 世界地图/可视化 */}
        <div className="flex-1 p-6 overflow-y-auto">
          <div className="h-full bg-white rounded-lg shadow-sm border border-gray-200 p-8 flex items-center justify-center">
            <div className="text-center space-y-4">
              <Globe className="w-16 h-16 text-gray-300 mx-auto" />
              <h3 className="text-lg font-medium text-gray-600">世界可视化</h3>
              <p className="text-gray-500 max-w-md">
                这里将显示世界的实时状态，包括角色位置、区域活动、事件分布等信息。
                可视化功能正在开发中...
              </p>
              <div className="text-sm text-gray-400">
                当前世界: {selectedWorld?.name || '未知'}
              </div>
            </div>
          </div>
        </div>

        {/* 右侧面板 - 事件流/状态 */}
        <div className="w-80 border-l border-gray-200 bg-white overflow-y-auto">
          <div className="p-4">
            <h3 className="font-bold text-gray-800 mb-4">实时事件流</h3>
            {timeControl.connected ? (
              <div className="space-y-3">
                <div className="p-3 bg-blue-50 rounded-lg border border-blue-200">
                  <div className="text-sm font-medium text-blue-800">系统初始化</div>
                  <div className="text-xs text-blue-600 mt-1">
                    时间系统已连接
                  </div>
                </div>

                {timeHistory.history?.time_points.length > 0 && (
                  <div className="space-y-2">
                    {timeHistory.history.time_points.slice(-5).map((point, index) => (
                      <div key={index} className="p-3 bg-gray-50 rounded-lg border border-gray-200">
                        <div className="text-sm font-medium text-gray-800">
                          {point.note || '时间记录'}
                        </div>
                        <div className="text-xs text-gray-500 mt-1">
                          {new Date(point.time).toLocaleTimeString('zh-CN')} · {point.day_phase}
                        </div>
                      </div>
                    ))}
                  </div>
                )}

                {(!timeHistory.history || timeHistory.history.time_points.length === 0) && (
                  <div className="text-center py-8 text-gray-500">
                    <Clock className="w-8 h-8 mx-auto mb-2 text-gray-300" />
                    <div className="text-sm">暂无事件记录</div>
                    <div className="text-xs mt-1">
                      时间系统正在运行，事件将在此显示
                    </div>
                  </div>
                )}
              </div>
            ) : (
              <div className="text-center py-8 text-gray-500">
                <Clock className="w-8 h-8 mx-auto mb-2 text-gray-300" />
                <div className="text-sm">等待连接...</div>
                <div className="text-xs mt-1">
                  时间系统连接中，请稍候
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}