import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ConfigProvider, theme as antTheme, App as AntApp } from 'antd'
import zhCN from 'antd/locale/zh_CN'
import App from './App'
import './styles/globals.css'
import { useThemeStore } from './stores/themeStore'
import GlobalWebSocket from './services/GlobalWebSocket'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
      staleTime: 30_000,
    },
  },
})

function ThemedApp() {
  const isDark = useThemeStore((s) => s.isDark)
  const init = useThemeStore((s) => s.init)

  React.useEffect(() => {
    init()
  }, [init])

  return (
    <ConfigProvider
      locale={zhCN}
      theme={{
        algorithm: isDark ? antTheme.darkAlgorithm : antTheme.defaultAlgorithm,
        token: {
          colorPrimary: '#2563eb',
          borderRadius: 8,
          colorBgContainer: isDark ? '#0f172a' : '#ffffff',
          colorBgElevated: isDark ? '#1e293b' : '#ffffff',
          colorBgLayout: isDark ? '#020617' : '#f8fafc',
          colorBorder: isDark ? '#334155' : '#e2e8f0',
          colorBorderSecondary: isDark ? '#1e293b' : '#f1f5f9',
          colorText: isDark ? '#e2e8f0' : '#1e293b',
          colorTextSecondary: isDark ? '#94a3b8' : '#64748b',
          colorTextTertiary: isDark ? '#64748b' : '#94a3b8',
          fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif",
        },
        components: {
          Card: {
            colorBgContainer: isDark ? '#0f172a' : '#ffffff',
            colorBorderSecondary: isDark ? '#1e293b' : '#f1f5f9',
          },
          Menu: {
            darkItemBg: 'transparent',
            darkItemSelectedBg: '#1e293b',
          },
          Drawer: {
            colorBgElevated: isDark ? '#0f172a' : '#ffffff',
          },
          Modal: {
            contentBg: isDark ? '#0f172a' : '#ffffff',
            headerBg: isDark ? '#0f172a' : '#ffffff',
          },
          Input: {
            colorBgContainer: isDark ? '#1e293b' : '#ffffff',
            colorBorder: isDark ? '#334155' : '#d1d5db',
          },
          Select: {
            colorBgContainer: isDark ? '#1e293b' : '#ffffff',
            colorBorder: isDark ? '#334155' : '#d1d5db',
            optionSelectedBg: isDark ? '#1e293b' : '#eff6ff',
          },
          Table: {
            colorBgContainer: isDark ? '#0f172a' : '#ffffff',
            headerBg: isDark ? '#1e293b' : '#f8fafc',
          },
          Tabs: {
            inkBarColor: '#2563eb',
            itemActiveColor: '#2563eb',
            itemSelectedColor: '#2563eb',
          },
        },
      }}
    >
      <AntApp>
        <GlobalWebSocket />
        <App />
      </AntApp>
    </ConfigProvider>
  )
}

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <ThemedApp />
      </BrowserRouter>
    </QueryClientProvider>
  </React.StrictMode>,
)
