import { useEffect, useRef, useState } from 'react'

export interface MessageHandler {
  onOpen?: () => void
  onClose?: () => void
  onError?: (error: Event) => void
  onMessage?: (data: any) => void
}

export function useWebSocket(url: string, handlers?: MessageHandler) {
  const [status, setStatus] = useState<'connecting' | 'connected' | 'closed'>('closed')
  const wsRef = useRef<WebSocket | null>(null)

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
      handlers?.onOpen?.()
    }

    wsRef.current.onclose = () => {
      setStatus('closed')
      handlers?.onClose?.()
    }

    wsRef.current.onerror = (error) => {
      setStatus('closed')
      handlers?.onError?.(error)
    }

    wsRef.current.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        handlers?.onMessage?.(data)
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
  }, [url, handlers])

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
