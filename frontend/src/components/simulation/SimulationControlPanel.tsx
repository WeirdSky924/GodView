/**
 * 模拟控制面板组件
 * GodView v5 世界模拟控制UI
 */

import React, { useState, useEffect } from 'react'
import { Play, Pause, Square, RotateCw, Activity, TrendingUp, AlertTriangle, Clock } from 'lucide-react'
import {
  initializeSimulation,
  startSimulation,
  stopSimulation,
  pauseSimulation,
  resumeSimulation,
  manualTick,
  setTickInterval,
  getSimulationStatus,
  type SimulationStatusResponse,
  SimulationStatus
} from '@/api/simulation'

interface SimulationControlPanelProps {
  worldId: string
  onStatusChange?: (status: SimulationStatus) => void
}

export default function SimulationControlPanel({ worldId, onStatusChange }: SimulationControlPanelProps) {
  const [status, setStatus] = useState<SimulationStatus | null>(null)
  const [performance, setPerformance] = useState<any>(null)
  const [loading, setLoading] = useState(false)
  const [tickInterval, setTickIntervalState] = useState(1.0)
  const [initialized, setInitialized] = useState(false)

  // 初始化模拟
  useEffect(() => {
    initializeWorldSimulation()
  }, [worldId])

  // 定期获取状态
  useEffect(() => {
    if (!initialized) return

    const interval = setInterval(() => {
      loadSimulationStatus()
    }, 2000) // 每2秒更新一次状态

    return () => clearInterval(interval)
  }, [worldId, initialized])

  const initializeWorldSimulation = async () => {
    try {
      setLoading(true)
      const result = await initializeSimulation({
        world_id: worldId,
        time_config: {
          time_scale: 1.0,
          time_mode: 'linear',
          day_length: 24
        }
      })

      if (result.success) {
        setInitialized(true)
        await loadSimulationStatus()
      }
    } catch (error) {
      console.error('初始化模拟失败:', error)
    } finally {
      setLoading(false)
    }
  }

  const loadSimulationStatus = async () => {
    try {
      const statusData = await getSimulationStatus(worldId)
      setStatus(statusData.status)
      setPerformance(statusData.performance)
      setTickIntervalState(1.0) // 重置tick间隔显示

      onStatusChange?.(statusData.status)
    } catch (error) {
      console.error('获取模拟状态失败:', error)
    }
  }

  const handleStart = async () => {
    try {
      const result = await startSimulation(worldId)
      if (result.success) {
        await loadSimulationStatus()
      }
    } catch (error) {
      console.error('启动模拟失败:', error)
    }
  }

  const handleStop = async () => {
    try {
      const result = await stopSimulation(worldId)
      if (result.success) {
        await loadSimulationStatus()
      }
    } catch (error) {
      console.error('停止模拟失败:', error)
    }
  }

  const handlePause = async () => {
    try {
      const result = await pauseSimulation(worldId)
      if (result.success) {
        await loadSimulationStatus()
      }
    } catch (error) {
      console.error('暂停模拟失败:', error)
    }
  }

  const handleResume = async () => {
    try {
      const result = await resumeSimulation(worldId)
      if (result.success) {
        await loadSimulationStatus()
      }
    } catch (error) {
      console.error('恢复模拟失败:', error)
    }
  }

  const handleManualTick = async () => {
    try {
      const result = await manualTick(worldId)
      if (result.success) {
        await loadSimulationStatus()
      }
    } catch (error) {
      console.error('手动tick失败:', error)
    }
  }

  const handleSetTickInterval = async (interval: number) => {
    try {
      const result = await setTickInterval(worldId, interval)
      if (result.success) {
        setTickIntervalState(interval)
      }
    } catch (error) {
      console.error('设置tick间隔失败:', error)
    }
  }

  const getStatusColor = () => {
    switch (status) {
      case SimulationStatus.RUNNING:
        return 'bg-green-100 text-green-700'
      case SimulationStatus.PAUSED:
        return 'bg-yellow-100 text-yellow-700'
      case SimulationStatus.STOPPED:
        return 'bg-gray-100 text-gray-600'
      case SimulationStatus.ERROR:
        return 'bg-red-100 text-red-700'
      default:
        return 'bg-gray-100 text-gray-600'
    }
  }

  const getStatusText = () => {
    switch (status) {
      case SimulationStatus.RUNNING:
        return '运行中'
      case SimulationStatus.PAUSED:
        return '已暂停'
      case SimulationStatus.STOPPED:
        return '已停止'
      case SimulationStatus.ERROR:
        return '错误'
      default:
        return '未知'
    }
  }

  return (
    <div className="bg-white rounded-lg shadow-md p-6 space-y-4">
      {/* 标题 */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Activity className="w-6 h-6 text-purple-600" />
          <div>
            <h2 className="text-xl font-bold text-gray-800">模拟控制</h2>
            <p className="text-sm text-gray-500">世界生命模拟器控制台</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <div className={`px-3 py-1 rounded-full text-sm ${getStatusColor()}`}>
            ● {getStatusText()}
          </div>
        </div>
      </div>

      {/* 控制按钮 */}
      <div>
        <h3 className="text-sm font-medium text-gray-700 mb-3">模拟控制</h3>
        <div className="grid grid-cols-4 gap-2">
          <button
            onClick={handleStart}
            disabled={!initialized || status === SimulationStatus.RUNNING || loading}
            className="flex items-center justify-center gap-2 px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <Play className="w-5 h-5" />
            启动
          </button>
          <button
            onClick={handlePause}
            disabled={!initialized || status !== SimulationStatus.RUNNING || loading}
            className="flex items-center justify-center gap-2 px-4 py-2 bg-yellow-600 text-white rounded-lg hover:bg-yellow-700 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <Pause className="w-5 h-5" />
            暂停
          </button>
          <button
            onClick={handleResume}
            disabled={!initialized || status !== SimulationStatus.PAUSED || loading}
            className="flex items-center justify-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <Play className="w-5 h-5" />
            恢复
          </button>
          <button
            onClick={handleStop}
            disabled={!initialized || status === SimulationStatus.STOPPED || loading}
            className="flex items-center justify-center gap-2 px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <Square className="w-5 h-5" />
            停止
          </button>
        </div>
      </div>

      {/* 手动控制 */}
      <div>
        <h3 className="text-sm font-medium text-gray-700 mb-3">手动控制</h3>
        <div className="flex gap-2">
          <button
            onClick={handleManualTick}
            disabled={!initialized || status === SimulationStatus.STOPPED || loading}
            className="flex-1 flex items-center justify-center gap-2 px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <RotateCw className="w-5 h-5" />
            手动推进
          </button>
          <div className="flex items-center gap-2 flex-1">
            <span className="text-sm text-gray-600">Tick间隔:</span>
            <input
              type="number"
              min="0.1"
              max="60"
              step="0.1"
              value={tickInterval}
              onChange={(e) => setTickIntervalState(parseFloat(e.target.value) || 1.0)}
              className="flex-1 px-3 py-2 border border-gray-300 rounded-lg text-center"
              disabled={!initialized || loading}
            />
            <span className="text-sm text-gray-600">秒</span>
          </div>
        </div>
      </div>

      {/* 性能监控 */}
      {performance && (
        <div>
          <h3 className="text-sm font-medium text-gray-700 mb-3">性能监控</h3>
          <div className="grid grid-cols-2 gap-3">
            <div className="flex items-center gap-2 p-3 bg-gray-50 rounded-lg">
              <Clock className="w-5 h-5 text-blue-600" />
              <div>
                <div className="text-xs text-gray-500">时钟周期</div>
                <div className="font-medium text-gray-800">{performance.total_ticks}</div>
              </div>
            </div>
            <div className="flex items-center gap-2 p-3 bg-gray-50 rounded-lg">
              <TrendingUp className="w-5 h-5 text-green-600" />
              <div>
                <div className="text-xs text-gray-500">平均时长</div>
                <div className="font-medium text-gray-800">
                  {performance.average_tick_duration.toFixed(3)}s
                </div>
              </div>
            </div>
            <div className="flex items-center gap-2 p-3 bg-gray-50 rounded-lg">
              <Activity className="w-5 h-5 text-purple-600" />
              <div>
                <div className="text-xs text-gray-500">当前周期</div>
                <div className="font-medium text-gray-800">{performance.current_tick}</div>
              </div>
            </div>
            {performance.error_count > 0 && (
              <div className="flex items-center gap-2 p-3 bg-red-50 rounded-lg">
                <AlertTriangle className="w-5 h-5 text-red-600" />
                <div>
                  <div className="text-xs text-gray-500">错误计数</div>
                  <div className="font-medium text-red-700">{performance.error_count}</div>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* 状态信息 */}
      {loading && (
        <div className="text-center py-4 text-gray-500">
          <div className="flex items-center justify-center gap-2">
            <Activity className="w-5 h-5 animate-spin" />
            <span>初始化中...</span>
          </div>
        </div>
      )}

      {!initialized && !loading && (
        <div className="text-center py-4 text-gray-500">
          <div className="flex items-center justify-center gap-2">
            <Activity className="w-5 h-5" />
            <span>请启动世界模拟</span>
          </div>
        </div>
      )}

      {initialized && status === SimulationStatus.RUNNING && (
        <div className="pt-4 border-t border-gray-200">
          <div className="flex justify-between text-sm text-gray-600">
            <span>模拟运行正常</span>
            <span>Tick: {performance?.current_tick || 0}</span>
          </div>
        </div>
      )}
    </div>
  )
}