import { useEffect, useRef, useState } from 'react'
import { getWsBaseUrl } from '@/api/systemConfig'

export interface MessageHandler {
  onOpen?: () => void
  onClose?: () => void
  onError?: (error: Event) => void
  onMessage?: (data: any) => void
}

/**
 * WebSocket Hook - 使用完整 URL
 */
export function useWebSocket(url: string, handlers?: MessageHandler) {
  const [status, setStatus] = useState<'connecting' | 'connected' | 'closed'>('closed')
  const wsRef = useRef<WebSocket | null>(null)
  const handlersRef = useRef(handlers)

  // Keep handlers ref up to date without triggering re-renders
  useEffect(() => {
    handlersRef.current = handlers
  }, [handlers])

  useEffect(() => {
    if (!url) {
      setStatus('closed')
      if (wsRef.current) {
        wsRef.current.close()
        wsRef.current = null
      }
      return
    }

    setStatus('connecting')
    wsRef.current = new WebSocket(url)

    wsRef.current.onopen = () => {
      setStatus('connected')
      handlersRef.current?.onOpen?.()
    }

    wsRef.current.onclose = () => {
      setStatus('closed')
      handlersRef.current?.onClose?.()
    }

    wsRef.current.onerror = (error) => {
      setStatus('closed')
      handlersRef.current?.onError?.(error)
    }

    wsRef.current.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        handlersRef.current?.onMessage?.(data)
      } catch (e) {
        console.error('Failed to parse WebSocket message:', e)
      }
    }

    return () => {
      if (wsRef.current) {
        wsRef.current.close()
        wsRef.current = null
      }
    }
  }, [url]) // Only depend on url, not handlers

  const send = (data: any) => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(data))
      return true
    }
    return false
  }

  return {
    status,
    send,
  }
}

/**
 * 动态 WebSocket Hook - 使用相对路径，自动从配置获取基础 URL
 * @param path WebSocket 相对路径，如 "/api/ws/connect/{sessionId}"
 */
export function useDynamicWebSocket(path: string, handlers?: MessageHandler) {
  const [status, setStatus] = useState<'connecting' | 'connected' | 'closed'>('closed')
  const wsRef = useRef<WebSocket | null>(null)
  const handlersRef = useRef(handlers)

  // Keep handlers ref up to date without triggering re-renders
  useEffect(() => {
    handlersRef.current = handlers
  }, [handlers])

  useEffect(() => {
    if (!path) {
      setStatus('closed')
      if (wsRef.current) {
        wsRef.current.close()
        wsRef.current = null
      }
      return
    }

    let mounted = true

    const connect = async () => {
      try {
        const wsBaseUrl = await getWsBaseUrl()
        if (!mounted) return

        const fullPath = path.startsWith('/') ? path : `/${path}`
        const url = `${wsBaseUrl}${fullPath}`

        setStatus('connecting')
        wsRef.current = new WebSocket(url)

        wsRef.current.onopen = () => {
          if (mounted) {
            setStatus('connected')
            handlersRef.current?.onOpen?.()
          }
        }

        wsRef.current.onclose = () => {
          if (mounted) {
            setStatus('closed')
            handlersRef.current?.onClose?.()
          }
        }

        wsRef.current.onerror = (error) => {
          if (mounted) {
            setStatus('closed')
            handlersRef.current?.onError?.(error)
          }
        }

        wsRef.current.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data)
            handlersRef.current?.onMessage?.(data)
          } catch (e) {
            console.error('Failed to parse WebSocket message:', e)
          }
        }
      } catch (error) {
        if (mounted) {
          setStatus('closed')
          console.error('Failed to connect WebSocket:', error)
        }
      }
    }

    connect()

    return () => {
      mounted = false
      if (wsRef.current) {
        wsRef.current.close()
        wsRef.current = null
      }
    }
  }, [path]) // Only depend on path, not handlers

  const send = (data: any) => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(data))
      return true
    }
    return false
  }

  return {
    status,
    send,
  }
}
