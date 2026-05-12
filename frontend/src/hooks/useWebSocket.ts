import { useEffect, useRef, useCallback, useState } from 'react'
import { App } from 'antd'
import { useProjectStore } from '../stores/projectStore'
import { useAgentStore } from '../stores/agentStore'

interface UseWebSocketOptions {
  onMessage?: (data: any) => void
  reconnectAttempts?: number
  reconnectIntervalMs?: number
  heartbeatIntervalMs?: number
}

export function useWebSocket(path: string, options: UseWebSocketOptions = {}) {
  const currentProject = useProjectStore((s) => s.currentProject)
  const updateAgent = useAgentStore((s) => s.updateAgent)
  const { notification } = App.useApp()
  const wsRef = useRef<WebSocket | null>(null)
  const reconnectCountRef = useRef(0)
  const heartbeatTimerRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const mountedRef = useRef(true)
  const [connected, setConnected] = useState(false)
  const [reconnecting, setReconnecting] = useState(false)
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const onMessageRef = useRef(options.onMessage)
  onMessageRef.current = options.onMessage
  const updateAgentRef = useRef(updateAgent)
  updateAgentRef.current = updateAgent
  const notificationRef = useRef(notification)
  notificationRef.current = notification

  const {
    heartbeatIntervalMs = 10000,
  } = options

  const clearHeartbeat = useCallback(() => {
    if (heartbeatTimerRef.current) {
      clearInterval(heartbeatTimerRef.current)
      heartbeatTimerRef.current = null
    }
  }, [])

  const startHeartbeat = useCallback((ws: WebSocket) => {
    clearHeartbeat()
    heartbeatTimerRef.current = setInterval(() => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: 'ping', timestamp: Date.now() }))
      }
    }, heartbeatIntervalMs)
  }, [heartbeatIntervalMs, clearHeartbeat])

  const getReconnectDelay = useCallback((attempt: number): number => {
    const delays = [1000, 2000, 4000, 8000, 16000, 32000]
    if (attempt < delays.length) {
      return delays[attempt]
    }
    return 30000
  }, [])

  const connect = useCallback(() => {
    if (!currentProject?.id || !mountedRef.current) return

    const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws'
    const baseUrl = import.meta.env.VITE_API_BASE_URL
      || (window.location.hostname === 'localhost' ? '/api' : 'https://yingyoujubenshengcheng.onrender.com/api')
    const normalizedPath = path.replace(/^\/+|\/+$/g, '')
    const wsTarget = normalizedPath || currentProject.id
    let wsBase: string
    if (baseUrl.startsWith('http')) {
      const urlObj = new URL(baseUrl)
      wsBase = `${protocol}://${urlObj.host}`
    } else {
      wsBase = `${protocol}://${window.location.host}`
    }
    const wsUrl = `${wsBase}/ws/${wsTarget}`

    try {
      const ws = new WebSocket(wsUrl)
      wsRef.current = ws

      ws.onopen = () => {
        if (!mountedRef.current) return
        reconnectCountRef.current = 0
        setConnected(true)
        setReconnecting(false)
        startHeartbeat(ws)
        updateAgentRef.current('系统', { status: 'idle' })
      }

      ws.onmessage = (event) => {
        if (!mountedRef.current) return
        try {
          const data = JSON.parse(event.data)

          if (data.type === 'pong') return

          if ((data.type === 'agent_status' || data.type === 'agent_update') && data.agent_name && data.status) {
            updateAgentRef.current(data.agent_name, { status: data.status, currentTask: data.current_task })
          }

          if (data.type === 'task_progress') {
            const agentName = data.agent_name || '系统'
            if (data.task_name || data.message) {
              updateAgentRef.current(agentName, {
                currentTask: data.task_name || data.message,
              } as any)
            }
          }

          if (data.type === 'notification') {
            notificationRef.current.info({
              message: data.title || '系统通知',
              description: data.message,
              placement: 'topRight',
              duration: 5000,
            })
          }

          window.dispatchEvent(new CustomEvent('ws-message', { detail: data }))

          onMessageRef.current?.(data)
        } catch {
          // Ignore parse errors for non-JSON messages
        }
      }

      ws.onerror = () => {
        if (!mountedRef.current) return
        updateAgentRef.current('系统', { status: 'error', currentTask: 'WebSocket 连接异常' })
      }

      ws.onclose = (event) => {
        if (!mountedRef.current) return
        setConnected(false)
        clearHeartbeat()

        if (event.code === 1000 || event.code === 1001) return

        updateAgentRef.current('系统', { status: 'error', currentTask: 'WebSocket 断开' })
        reconnectCountRef.current += 1

        const delay = getReconnectDelay(reconnectCountRef.current)
        setReconnecting(true)
        notificationRef.current.warning({
          message: '连接断开',
          description: `将在 ${Math.round(delay / 1000)} 秒后自动重连（第 ${reconnectCountRef.current} 次）`,
          placement: 'topRight',
          duration: 4,
        })

        reconnectTimeoutRef.current = setTimeout(connect, delay)
      }
    } catch {
      if (!mountedRef.current) return
      const delay = getReconnectDelay(reconnectCountRef.current + 1)
      reconnectTimeoutRef.current = setTimeout(connect, delay)
    }
  }, [currentProject?.id, path, clearHeartbeat, startHeartbeat, getReconnectDelay])

  const disconnect = useCallback(() => {
    clearHeartbeat()
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current)
      reconnectTimeoutRef.current = null
    }
    if (wsRef.current) {
      wsRef.current.onclose = null
      wsRef.current.close(1000, 'Client disconnect')
      wsRef.current = null
    }
    setConnected(false)
  }, [clearHeartbeat])

  const reconnect = useCallback(() => {
    reconnectCountRef.current = 0
    disconnect()
    connect()
  }, [disconnect, connect])

  useEffect(() => {
    mountedRef.current = true
    connect()

    return () => {
      mountedRef.current = false
      clearHeartbeat()
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current)
      }
      if (wsRef.current) {
        wsRef.current.onclose = null
        wsRef.current.close(1000, 'Component unmount')
        wsRef.current = null
      }
    }
  }, [connect, clearHeartbeat])

  const send = useCallback((data: any) => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(typeof data === 'string' ? data : JSON.stringify(data))
      return true
    }
    return false
  }, [])

  return {
    send,
    disconnect,
    reconnect,
    connected,
    reconnecting,
    reconnectCount: reconnectCountRef.current,
  }
}
