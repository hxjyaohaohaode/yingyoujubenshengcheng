import { useState, useEffect, useRef, useCallback } from 'react'
import { App } from 'antd'
import { api } from '../api/client'

const TIMEOUT_SECONDS = 120
const POLL_INTERVAL_MS = 2000

export function useTaskProgress(taskId: string | null) {
  const { notification } = App.useApp()
  const [progress, setProgress] = useState(0)
  const [status, setStatus] = useState('idle')
  const [estimatedTime, setEstimatedTime] = useState('--')
  const [elapsedSeconds, setElapsedSeconds] = useState(0)
  const [isTimeout, setIsTimeout] = useState(false)
  const startTimeRef = useRef<number | null>(null)
  const progressHistoryRef = useRef<Array<{ time: number; progress: number }>>([])
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const timeoutWarnedRef = useRef(false)
  const pollTimerRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const clearTimer = useCallback(() => {
    if (timerRef.current) {
      clearInterval(timerRef.current)
      timerRef.current = null
    }
    if (pollTimerRef.current) {
      clearInterval(pollTimerRef.current)
      pollTimerRef.current = null
    }
  }, [])

  const cancelTask = useCallback(async () => {
    if (!taskId) return
    try {
      await api.post(`/ai/cancel/${taskId}`)
      setStatus('cancelled')
      setProgress(0)
      startTimeRef.current = null
      clearTimer()
      notification.info({
        message: '任务已取消',
        description: 'AI生成任务已被取消',
        placement: 'topRight',
        duration: 3,
      })
    } catch {
      notification.error({
        message: '取消失败',
        description: '无法取消该任务，请稍后重试',
        placement: 'topRight',
        duration: 3,
      })
    }
  }, [taskId, clearTimer])

  const retryTask = useCallback(() => {
    setIsTimeout(false)
    timeoutWarnedRef.current = false
    startTimeRef.current = Date.now()
  }, [])

  const handleMessage = useCallback((event: Event) => {
    const data = (event as CustomEvent).detail
    if (!data || data.type !== 'task_progress' || data.task_id !== taskId) return

    setProgress(data.progress)
    setStatus(data.status)
    setIsTimeout(false)

    const now = Date.now()
    if (startTimeRef.current === null) {
      startTimeRef.current = now
    }

    if (data.status === 'completed' || data.status === 'failed') {
      clearTimer()
      return
    }

    progressHistoryRef.current.push({ time: now, progress: data.progress })

    if (progressHistoryRef.current.length > 5) {
      progressHistoryRef.current = progressHistoryRef.current.slice(-5)
    }

    if (data.progress > 0 && progressHistoryRef.current.length >= 2) {
      const first = progressHistoryRef.current[0]
      const last = progressHistoryRef.current[progressHistoryRef.current.length - 1]
      const elapsedSec = (last.time - first.time) / 1000
      const progressDelta = last.progress - first.progress

      if (elapsedSec > 0 && progressDelta > 0) {
        const ratePerSec = progressDelta / elapsedSec
        const remaining = (100 - data.progress) / ratePerSec

        if (remaining < 60) {
          setEstimatedTime(`${Math.round(remaining)}秒`)
        } else if (remaining < 3600) {
          setEstimatedTime(`${Math.round(remaining / 60)}分钟`)
        } else {
          setEstimatedTime(`${(remaining / 3600).toFixed(1)}小时`)
        }
      }
    }
  }, [taskId, clearTimer])

  useEffect(() => {
    if (status === 'completed' || status === 'failed' || status === 'cancelled') {
      clearTimer()
    }
  }, [status, clearTimer])

  useEffect(() => {
    if (!taskId) {
      setProgress(0)
      setStatus('idle')
      setEstimatedTime('--')
      setElapsedSeconds(0)
      setIsTimeout(false)
      startTimeRef.current = null
      progressHistoryRef.current = []
      timeoutWarnedRef.current = false
      clearTimer()
      return
    }

    startTimeRef.current = Date.now()

    const syncProgress = async () => {
      try {
        const result = await api.get<{ status: string; progress: number; estimated_time: string }>(`/ai/tasks/${taskId}`)
        if (!result) return
        setStatus(result.status || 'unknown')
        setProgress(result.progress || 0)
        setEstimatedTime(result.estimated_time || '--')
        if (result.status === 'completed' || result.status === 'failed' || result.status === 'cancelled' || result.status === 'timeout') {
          clearTimer()
        }
      } catch {
        // Keep websocket as primary channel; polling is only a reliability fallback.
      }
    }

    void syncProgress()
    pollTimerRef.current = setInterval(() => {
      void syncProgress()
    }, POLL_INTERVAL_MS)

    timerRef.current = setInterval(() => {
      if (startTimeRef.current === null) return
      const elapsed = Math.floor((Date.now() - startTimeRef.current) / 1000)
      setElapsedSeconds(elapsed)

      if (elapsed >= TIMEOUT_SECONDS && !timeoutWarnedRef.current) {
        setIsTimeout(true)
        timeoutWarnedRef.current = true
        notification.warning({
          message: '任务执行超时',
          description: `任务已运行超过${TIMEOUT_SECONDS}秒，您可以等待或取消任务`,
          placement: 'topRight',
          duration: 0,
          key: 'task-timeout',
        })
      }
    }, 1000)

    window.addEventListener('ws-message', handleMessage)
    return () => {
      window.removeEventListener('ws-message', handleMessage)
      clearTimer()
    }
  }, [taskId, handleMessage, clearTimer])

  return {
    progress,
    status,
    estimatedTime,
    elapsedSeconds,
    isTimeout,
    cancelTask,
    retryTask,
  }
}
