import { useState, useEffect, useCallback, useRef } from 'react'
import { App } from 'antd'
import { useProjectStore } from '../stores/projectStore'

export function useNetworkStatus() {
  const [isOnline, setIsOnline] = useState(navigator.onLine)
  const [wasOffline, setWasOffline] = useState(false)
  const { notification } = App.useApp()

  useEffect(() => {
    const handleOnline = () => {
      setIsOnline(true)
      if (wasOffline) {
        notification.success({
          message: '网络已恢复',
          description: '已重新连接到服务器',
          placement: 'topRight',
          duration: 3,
        })
        setWasOffline(false)
      }
    }
    const handleOffline = () => {
      setIsOnline(false)
      setWasOffline(true)
      notification.warning({
        message: '网络已断开',
        description: '部分功能可能无法使用，请检查网络连接',
        placement: 'topRight',
        duration: 0,
      })
    }

    window.addEventListener('online', handleOnline)
    window.addEventListener('offline', handleOffline)
    return () => {
      window.removeEventListener('online', handleOnline)
      window.removeEventListener('offline', handleOffline)
    }
  }, [wasOffline])

  return { isOnline, wasOffline }
}

export function useUnsavedChanges(hasUnsaved: boolean) {
  useEffect(() => {
    if (!hasUnsaved) return

    const handler = (e: BeforeUnloadEvent) => {
      e.preventDefault()
      e.returnValue = ''
    }

    window.addEventListener('beforeunload', handler)
    return () => window.removeEventListener('beforeunload', handler)
  }, [hasUnsaved])
}

export function useDebounce<T extends (...args: any[]) => any>(fn: T, delay: number) {
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  return useCallback((...args: Parameters<T>) => {
    if (timerRef.current) {
      clearTimeout(timerRef.current)
    }
    timerRef.current = setTimeout(() => fn(...args), delay)
  }, [fn, delay])
}

export function useThrottle<T extends (...args: any[]) => any>(fn: T, interval: number) {
  const lastRunRef = useRef(0)
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  return useCallback((...args: Parameters<T>) => {
    const now = Date.now()
    if (now - lastRunRef.current >= interval) {
      lastRunRef.current = now
      fn(...args)
    } else {
      if (timerRef.current) clearTimeout(timerRef.current)
      timerRef.current = setTimeout(() => {
        lastRunRef.current = Date.now()
        fn(...args)
      }, interval - (now - lastRunRef.current))
    }
  }, [fn, interval])
}

export function useIdle(timeout: number) {
  const [isIdle, setIsIdle] = useState(false)
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(() => {
    const resetTimer = () => {
      setIsIdle(false)
      if (timerRef.current) clearTimeout(timerRef.current)
      timerRef.current = setTimeout(() => setIsIdle(true), timeout)
    }

    const events = ['mousedown', 'mousemove', 'keydown', 'scroll', 'touchstart']
    events.forEach((e) => window.addEventListener(e, resetTimer))
    resetTimer()

    return () => {
      events.forEach((e) => window.removeEventListener(e, resetTimer))
      if (timerRef.current) clearTimeout(timerRef.current)
    }
  }, [timeout])

  return isIdle
}

export function useWindowSize() {
  const [size, setSize] = useState({
    width: window.innerWidth,
    height: window.innerHeight,
  })

  useEffect(() => {
    let timer: ReturnType<typeof setTimeout>
    const handler = () => {
      clearTimeout(timer)
      timer = setTimeout(() => {
        setSize({ width: window.innerWidth, height: window.innerHeight })
      }, 100)
    }

    window.addEventListener('resize', handler)
    return () => {
      window.removeEventListener('resize', handler)
      clearTimeout(timer)
    }
  }, [])

  return size
}

export function useKeyboard(shortcuts: Record<string, (e: KeyboardEvent) => void>) {
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      const key = [
        e.ctrlKey && 'ctrl',
        e.metaKey && 'meta',
        e.altKey && 'alt',
        e.shiftKey && 'shift',
        e.key.toLowerCase(),
      ]
        .filter(Boolean)
        .join('+')

      if (shortcuts[key]) {
        e.preventDefault()
        shortcuts[key](e)
      }
    }

    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [shortcuts])
}

export function useLocalStorage<T>(key: string, initialValue: T) {
  const [value, setValue] = useState<T>(() => {
    try {
      const stored = localStorage.getItem(key)
      return stored ? JSON.parse(stored) : initialValue
    } catch {
      return initialValue
    }
  })

  useEffect(() => {
    try {
      localStorage.setItem(key, JSON.stringify(value))
    } catch {
      // 存储空间不足等异常静默处理
    }
  }, [key, value])

  return [value, setValue] as const
}

export function useGlobalUnsavedGuard() {
  const { unsavedChanges } = useProjectStore()

  useUnsavedChanges(unsavedChanges)

  return unsavedChanges
}

export function getPageKeyFromPath(pathname: string): string {
  const map: Record<string, string> = {
    '/': 'dashboard',
    '/world': 'world',
    '/characters': 'characters',
    '/foreshadows': 'foreshadows',
    '/chapters': 'chapters',
    '/scenes': 'scenes',
    '/review': 'review',
    '/emotion-curve': 'emotion-curve',
    '/export': 'export',
    '/settings': 'settings',
  }
  return map[pathname] || 'dashboard'
}
