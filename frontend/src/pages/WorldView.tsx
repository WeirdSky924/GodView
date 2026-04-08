/**
 * 世界观测页面
 * GodView v5 世界观测系统的主要界面
 */

import React, { useState, useEffect } from 'react'
import { Globe, Activity, Clock, TrendingUp, Users, MapPin, Zap, History } from 'lucide-react'
import TimeControlPanel from '@/components/time/TimeControlPanel'
import SimulationControlPanel from '@/components/simulation/SimulationControlPanel'
import { useTimeControl } from '@/hooks/useTimeWebSocket'
import { useTimeHistory } from '@/hooks/useTimeWebSocket'
import { getWorlds, type World } from '@/api/worlds'
import { SimulationStatus } from '@/api/simulation'

export default function WorldView() {
  const [worlds, setWorlds] = useState<World[]>([])
  const [selectedWorldId, setSelectedWorldId] = useState('')
  const [loading, setLoading] = useState(true)
  const [simulationStatus, setSimulationStatus] = useState<SimulationStatus | null>(null)
  const [selectedTab, setSelectedTab] = useState<'time' | 'simulation' | 'entities' | 'events'>('simulation')

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
      if (result.length > 0 && !selectedWorldId && result[0]?.id) {
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
            {simulationStatus && (
              <div className="flex items-center gap-2">
                <Zap className="w-4 h-4 text-yellow-600" />
                <span className="text-gray-600">
                  模拟: {simulationStatus === SimulationStatus.RUNNING ? '运行中' : simulationStatus}
                </span>
              </div>
            )}
          </div>
        )}
      </div>

      {/* 主内容区域 */}
      <div className="flex-1 flex overflow-hidden">
        {/* 左侧面板 - 控制面板 */}
        <div className="w-96 border-r border-gray-200 bg-white overflow-y-auto">
          {/* 标签页导航 */}
          <div className="border-b border-gray-200">
            <nav className="flex">
              <button
                onClick={() => setSelectedTab('simulation')}
                className={`flex-1 py-3 px-4 text-sm font-medium ${
                  selectedTab === 'simulation'
                    ? 'text-blue-600 border-b-2 border-blue-600'
                    : 'text-gray-500 hover:text-gray-700'
                }`}
              >
                模拟控制
              </button>
              <button
                onClick={() => setSelectedTab('time')}
                className={`flex-1 py-3 px-4 text-sm font-medium ${
                  selectedTab === 'time'
                    ? 'text-blue-600 border-b-2 border-blue-600'
                    : 'text-gray-500 hover:text-gray-700'
                }`}
              >
                时间控制
              </button>
            </nav>
          </div>

          {/* 标签页内容 */}
          {selectedTab === 'simulation' && (
            <div className="p-4">
              <SimulationControlPanel worldId={selectedWorldId} onStatusChange={setSimulationStatus} />
            </div>
          )}

          {selectedTab === 'time' && (
            <div className="p-4">
              <TimeControlPanel worldId={selectedWorldId} />
            </div>
          )}
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

        {/* 右侧面板 - 实时信息 */}
        <div className="w-80 border-l border-gray-200 bg-white overflow-y-auto">
          <div className="p-4">
            <h3 className="font-bold text-gray-800 mb-4">实时监控</h3>

            {/* 系统状态卡片 */}
            <div className="space-y-4">
              {/* 时间系统状态 */}
              {timeControl.connected && (
                <div className="p-4 bg-blue-50 rounded-lg border border-blue-200">
                  <div className="flex items-center gap-2 mb-2">
                    <Clock className="w-5 h-5 text-blue-600" />
                    <span className="font-medium text-blue-800">时间系统</span>
                    <span className={`ml-auto px-2 py-0.5 rounded text-xs ${
                      timeControl.isFrozen
                        ? 'bg-yellow-200 text-yellow-800'
                        : 'bg-green-200 text-green-800'
                    }`}>
                      {timeControl.isFrozen ? '已冻结' : '运行中'}
                    </span>
                  </div>
                  <div className="space-y-1 text-sm">
                    <div className="flex justify-between text-gray-600">
                      <span>当前时间</span>
                      <span className="font-medium">
                        {timeControl.currentTime ? new Date(timeControl.currentTime).toLocaleTimeString('zh-CN') : '---'}
                      </span>
                    </div>
                    <div className="flex justify-between text-gray-600">
                      <span>时间流速</span>
                      <span className="font-medium">{timeControl.timeScale?.toFixed(1)}x</span>
                    </div>
                    <div className="flex justify-between text-gray-600">
                      <span>时钟周期</span>
                      <span className="font-medium">{timeControl.tickCount}</span>
                    </div>
                  </div>
                </div>
              )}

              {/* 模拟状态卡片 */}
              {simulationStatus && (
                <div className="p-4 bg-purple-50 rounded-lg border border-purple-200">
                  <div className="flex items-center gap-2 mb-2">
                    <Activity className="w-5 h-5 text-purple-600" />
                    <span className="font-medium text-purple-800">模拟系统</span>
                    <span className={`ml-auto px-2 py-0.5 rounded text-xs ${
                      simulationStatus === SimulationStatus.RUNNING
                        ? 'bg-green-200 text-green-800'
                        : simulationStatus === SimulationStatus.PAUSED
                          ? 'bg-yellow-200 text-yellow-800'
                          : 'bg-gray-200 text-gray-800'
                    }`}>
                      {simulationStatus === SimulationStatus.RUNNING ? '运行中' :
                       simulationStatus === SimulationStatus.PAUSED ? '已暂停' : '已停止'}
                    </span>
                  </div>
                  <div className="space-y-1 text-sm">
                    <div className="flex justify-between text-gray-600">
                      <span>状态</span>
                      <span className="font-medium">{simulationStatus}</span>
                    </div>
                  </div>
                </div>
              )}

              {/* 时间历史记录 */}
              {timeHistory.history && timeHistory.history.time_points.length > 0 && (
                <div className="p-4 bg-green-50 rounded-lg border border-green-200">
                  <div className="flex items-center gap-2 mb-2">
                    <History className="w-5 h-5 text-green-600" />
                    <span className="font-medium text-green-800">时间记录</span>
                  </div>
                  <div className="max-h-40 overflow-y-auto space-y-2">
                    {timeHistory.history.time_points.slice(-5).map((point, index) => (
                      <div key={index} className="text-sm">
                        <div className="font-medium text-gray-800">
                          {point.note || '时间记录'}
                        </div>
                        <div className="text-xs text-gray-600">
                          {new Date(point.time).toLocaleTimeString('zh-CN')} · {point.day_phase}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>

            {/* 系统统计 */}
            <div className="mt-6">
              <h4 className="font-bold text-gray-800 mb-3">系统统计</h4>
              <div className="space-y-2 text-sm">
                <div className="flex justify-between text-gray-600">
                  <span>活跃实体</span>
                  <span className="font-medium">--</span>
                </div>
                <div className="flex justify-between text-gray-600">
                  <span>地点数量</span>
                  <span className="font-medium">--</span>
                </div>
                <div className="flex justify-between text-gray-600">
                  <span>活跃事件</span>
                  <span className="font-medium">--</span>
                </div>
                <div className="flex justify-between text-gray-600">
                  <span>内存使用</span>
                  <span className="font-medium">--</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}