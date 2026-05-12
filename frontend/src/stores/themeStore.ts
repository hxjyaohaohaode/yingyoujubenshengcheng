import { create } from 'zustand'

interface ThemeState {
  isDark: boolean
  initialized: boolean
  toggle: () => void
  setDark: (dark: boolean) => void
  init: () => void
}

function getInitialTheme(): boolean {
  if (typeof window === 'undefined') return false
  try {
    const saved = localStorage.getItem('theme')
    if (saved === 'dark') return true
    if (saved === 'light') return false
    return window.matchMedia('(prefers-color-scheme: dark)').matches
  } catch {
    return false
  }
}

function applyTheme(dark: boolean) {
  if (typeof document === 'undefined') return
  const root = document.documentElement
  if (dark) {
    root.classList.add('dark')
  } else {
    root.classList.remove('dark')
  }
  try {
    localStorage.setItem('theme', dark ? 'dark' : 'light')
  } catch {
    // ignore
  }
}

export const useThemeStore = create<ThemeState>((set, get) => ({
  isDark: false,
  initialized: false,

  init: () => {
    if (get().initialized) return
    const initial = getInitialTheme()
    applyTheme(initial)
    set({ isDark: initial, initialized: true })

    if (typeof window !== 'undefined') {
      const mq = window.matchMedia('(prefers-color-scheme: dark)')
      const handler = (e: MediaQueryListEvent) => {
        try {
          if (!localStorage.getItem('theme')) {
            get().setDark(e.matches)
          }
        } catch {
          // ignore
        }
      }
      mq.addEventListener('change', handler)
    }
  },

  toggle: () => {
    const next = !get().isDark
    applyTheme(next)
    set({ isDark: next, initialized: true })
  },

  setDark: (dark: boolean) => {
    applyTheme(dark)
    set({ isDark: dark, initialized: true })
  },
}))
