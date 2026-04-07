/**
 * 时间系统WebSocket连接管理
 * GodView v5 时间流逝系统前端WebSocket管理
 */

import { useState, useEffect, useRef, useCallback } from 'react'
import { api } from '@/api/client'
import { TimeUpdateResult, TimeUpdateHandler, TimeConnectionHandler, ErrorHandler, TimeHistoryResponse } from '@/api/time'

interface UseTimeWebSocketOptions {
  worldId: string
  onTimeUpdate?: TimeUpdateHandler
  onConnected?: TimeConnectionHandler
  onError?: ErrorHandler
  autoConnect?: boolean
}

interface UseTimeWebSocketResult {
  connected: boolean
  error: Event | null
  connect: () => void
  disconnect: () => void
  send: (data: any) => void
  currentTime: string | null
  timeScale: number | null
  tickCount: number | null
  isFrozen: boolean | null
}

const TIME_WS_URL = 'ws://localhost:8000'

export function useTimeWebSocket({
  worldId,
  onTimeUpdate,
  onConnected,
  onError,
  autoConnect = true,
}: UseTimeWebSocketOptions): UseTimeWebSocketResult {
  const wsRef = useRef<WebSocket | null>(null)
  const [connected, setConnected] = useState(false)
  const [error, setError] = useState<Event | null>(null)
  const [currentTime, setCurrentTime] = useState<string | null>(null)
  const [timeScale, setTimeScale] = useState<number | null>(null)
  const [tickCount, setTickCount] = useState<number | null>(null)
  const [isFrozen, setIsFrozen] = useState<boolean | null>(null)

  // 连接WebSocket
  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      return // 已经连接
    }

    try {
      const wsUrl = `${TIME_WS_URL}/ws/time/${worldId}`
      wsRef.current = new WebSocket(wsUrl)

      wsRef.current.onopen = () => {
        setConnected(true)
        setError(null)
        console.log(`时间WebSocket已连接: ${worldId}`)

        // 通知连接成功
        onConnected?.({
          world_id: worldId,
          message: '时间系统连接成功'
        })
      }

      wsRef.current.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data)
          handleMessage(data)
        } catch (e) {
          console.error('解析时间WebSocket消息失败:', e)
        }
      }

      wsRef.current.onerror = (event) => {
        setError(event)
        console.error('时间WebSocket错误:', event)
        onError?.(event)
      }

      wsRef.current.onclose = () => {
        setConnected(false)
        console.log(`时间WebSocket已断开: ${worldId}`)

        // 自动重连
        if (autoConnect) {
          setTimeout(connect, 2000)
        }
      }
    } catch (e) {
      setError(e as Event)
      console.error('创建时间WebSocket失败:', e)
    }
  }, [worldId, onConnected, onError, autoConnect])

  // 断开连接
  const disconnect = useCallback(() => {
    if (wsRef.current) {
      wsRef.current.close()
      wsRef.current = null
      setConnected(false)
    }
  }, [])

  // 发送消息
  const send = useCallback((data: any) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(data))
    }
  }, [])

  // 处理接收的消息
  const handleMessage = useCallback((message: any) => {
    switch (message.type) {
      case 'connected':
        // 初始连接信息
        break

      case 'time_update':
        const update: TimeUpdateResult = message.data
        setCurrentTime(update.current_time)
        setTimeScale(update.time_scale)
        setTickCount(update.tick_count)
        setIsFrozen(update.time_scale === 0)

        // 通知时间更新
        onTimeUpdate?.(update)
        break

      case 'time_info':
        // 时间信息更新
        if (message.data?.time_info) {
          setCurrentTime(message.data.time_info.current_time)
          setTimeScale(message.data.time_info.time_scale)
          setTickCount(message.data.time_info.tick_count)
          setIsFrozen(message.data.is_frozen)
        }
        break

      case 'freeze_toggle':
        if (message.data?.is_frozen !== undefined) {
          setIsFrozen(message.data.is_frozen)
        }
        break

      case 'scale_set':
        if (message.data?.time_scale !== undefined) {
          setTimeScale(message.data.time_scale)
        }
        break

      default:
        console.log('未知的时间WebSocket消息类型:', message.type)
    }
  }, [onTimeUpdate])

  // 自动连接
  useEffect(() => {
    if (autoConnect) {
      connect()
    }

    return () => {
      disconnect()
    }
  }, [autoConnect, connect, disconnect])

  // 复制到剪贴板
  const copyTimeToClipboard = useCallback(() => {
    if (currentTime) {
      navigator.clipboard.writeText(currentTime)
    }
  }, [currentTime])

  // 获取时间格式的友好显示
  const getFriendlyTimeDisplay = useCallback(() => {
    if (!currentTime) return '等待连接...'

    const date = new Date(currentTime)
    const now = new Date()
    const diff = now.getTime() - date.getTime()

    if (diff < 60000) {
      return '刚刚'
    } else if (diff < 3600000) {
      return `${Math.floor(diff / 60000)} 分钟前`
    } else if (diff < 86400000) {
      return `${Math.floor(diff / 3600000)} 小时前`
    } else {
      return date.toLocaleDateString('zh-CN', {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit'
      })
    }
  }, [currentTime])

  return {
    connected,
    error,
    connect,
    disconnect,
    send,
    currentTime,
    timeScale,
    tickCount,
    isFrozen,
    getFriendlyTimeDisplay,
    copyTimeToClipboard,
  }
}

/**
 * 高级时间控制Hook
 * 提供手动时间控制功能
 */
export function useTimeControl(worldId: string) {
  const timeWebSocket = useTimeWebSocket({ worldId })

  // 手动推进一个时钟周期
  const manualTick = useCallback(async (minutes: number = 10) => {
    if (timeWebSocket.connected) {
      timeWebSocket.send({
        type: 'manual_tick',
        minutes
      })
    }
  }, [timeWebSocket.connected, timeWebSocket.send])

  // 切换时间冻结状态
  const toggleFreeze = useCallback(async () => {
    if (timeWebSocket.connected) {
      timeWebSocket.send({
        type: 'toggle_freeze'
      })
    }
  }, [timeWebSocket.connected, timeWebSocket.send])

  // 设置时间流速
  const setTimeScale = useCallback(async (scale: number) => {
    if (timeWebSocket.connected) {
      timeWebSocket.send({
        type: 'set_time_scale',
        scale
      })
    }
  }, [timeWebSocket.connected, timeWebSocket.send])

  // 获取当前时间信息
  const getCurrentTimeInfo = useCallback(async () => {
    try {
      return await api.get('/time/systems/' + worldId)
    } catch (error) {
      console.error('获取时间信息失败:', error)
      return null
    }
  }, [worldId])

  return {
    ...timeWebSocket,
    manualTick,
    toggleFreeze,
    setTimeScale,
    getCurrentTimeInfo,
  }
}

/**
 * 时间历史管理Hook
 */
export function useTimeHistory(worldId: string, limit: number = 100) {
  const [history, setHistory] = useState<TimeHistoryResponse | null>(null)
  const [loading, setLoading] = useState(false)

  const loadHistory = useCallback(async () => {
    if (!worldId) return

    setLoading(true)
    try {
      const response = await api.get('/time/history/' + worldId, {
        params: { limit }
      })
      setHistory(response.data)
    } catch (error) {
      console.error('加载时间历史失败:', error)
    } finally {
      setLoading(false)
    }
  }, [worldId, limit])

  // 初始加载
  useEffect(() => {
    loadHistory()
  }, [loadHistory])

  // 记录时间点
  const recordTimePoint = useCallback(async (note: string) => {
    try {
      await api.post('/time/record', {
        world_id: worldId,
        note,
      })
      // 重新加载历史
      loadHistory()
      return true
    } catch (error) {
      console.error('记录时间点失败:', error)
      return false
    }
  }, [worldId, loadHistory])

  // 创建时间分支
  const createBranch = useCallback(async (branchName: string, note: string = '') => {
    try {
      await api.post('/time/branches', {
        world_id: worldId,
        branch_name: branchName,
        note,
      })
      // 重新加载历史
      loadHistory()
      return true
    } catch (error) {
      console.error('创建时间分支失败:', error)
      return false
    }
  }, [worldId, loadHistory])

  // 切换时间分支
  const switchBranch = useCallback(async (branchId: string) => {
    try {
      await api.post('/time/branches/' + worldId + '/switch', null, {
        params: { branch_id: branchId }
      })
      // 重新加载历史
      loadHistory()
      return true
    } catch (error) {
      console.error('切换时间分支失败:', error)
      return false
    }
  }, [worldId, loadHistory])

  return {
    history,
    loading,
    loadHistory,
    recordTimePoint,
    createBranch,
    switchBranch,
  }
}