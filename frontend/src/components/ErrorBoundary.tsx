import React from 'react'
import { Button, Result, Collapse, Typography } from 'antd'
import { BugOutlined, ReloadOutlined, HomeOutlined, CopyOutlined } from '@ant-design/icons'
import { Link } from 'react-router-dom'

interface ErrorBoundaryProps {
  children: React.ReactNode
  fallback?: React.ReactNode
  onError?: (error: Error, errorInfo: React.ErrorInfo) => void
}

interface ErrorBoundaryState {
  hasError: boolean
  error: Error | null
  errorInfo: React.ErrorInfo | null
  errorCount: number
}

export default class ErrorBoundary extends React.Component<ErrorBoundaryProps, ErrorBoundaryState> {
  private errorHistory: Array<{ error: Error; time: number }> = []

  constructor(props: ErrorBoundaryProps) {
    super(props)
    this.state = { hasError: false, error: null, errorInfo: null, errorCount: 0 }
  }

  static getDerivedStateFromError(error: Error): Partial<ErrorBoundaryState> {
    return { hasError: true, error }
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    this.errorHistory.push({ error, time: Date.now() })

    console.error('[ErrorBoundary] 捕获到渲染错误:', {
      error: error.message,
      stack: error.stack,
      componentStack: errorInfo.componentStack,
      time: new Date().toISOString(),
    })

    this.setState((prev) => ({
      errorInfo,
      errorCount: prev.errorCount + 1,
    }))

    this.props.onError?.(error, errorInfo)
  }

  handleReset = () => {
    this.setState({ hasError: false, error: null, errorInfo: null })
  }

  handleReload = () => {
    window.location.reload()
  }

  handleCopyError = () => {
    const info = [
      `错误: ${this.state.error?.message}`,
      `堆栈: ${this.state.error?.stack}`,
      `组件堆栈: ${this.state.errorInfo?.componentStack}`,
      `时间: ${new Date().toISOString()}`,
    ].join('\n\n')
    navigator.clipboard.writeText(info).catch(() => {})
  }

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback
      }

      const isSevere = this.state.errorCount >= 3

      return (
        <div className="flex items-center justify-center min-h-[60vh] p-4">
          <Result
            status={isSevere ? '500' : 'error'}
            icon={isSevere ? <BugOutlined className="text-red-500" /> : undefined}
            title={isSevere ? '发生持续性错误' : '页面发生了错误'}
            subTitle={
              <div className="space-y-2">
                <p>{this.state.error?.message || '未知错误，请联系技术支持'}</p>
                {isSevere && (
                  <p className="text-amber-500 text-sm">
                    已累计发生 {this.state.errorCount} 次错误，建议刷新页面后重试
                  </p>
                )}
              </div>
            }
            extra={[
              <Button type="primary" key="reset" onClick={this.handleReset} icon={<ReloadOutlined />}>
                重试
              </Button>,
              <Button key="reload" onClick={this.handleReload} icon={<ReloadOutlined />}>
                刷新页面
              </Button>,
              <Link to="/" key="home">
                <Button icon={<HomeOutlined />}>返回首页</Button>
              </Link>,
              <Button key="copy" onClick={this.handleCopyError} icon={<CopyOutlined />} type="dashed">
                复制错误信息
              </Button>,
            ]}
          >
            {this.state.errorInfo && (
              <Collapse
                ghost
                size="small"
                className="mt-4 max-w-[600px] mx-auto"
                items={[{
                  key: 'details',
                  label: <span className="text-xs text-gray-400">技术详情</span>,
                  children: (
                    <div className="text-xs space-y-2">
                      <div>
                        <Typography.Text type="secondary" strong>错误堆栈:</Typography.Text>
                        <pre className="mt-1 p-2 bg-gray-50 dark:bg-gray-800 rounded text-xs overflow-auto max-h-[200px]">
                          {this.state.error?.stack}
                        </pre>
                      </div>
                      <div>
                        <Typography.Text type="secondary" strong>组件堆栈:</Typography.Text>
                        <pre className="mt-1 p-2 bg-gray-50 dark:bg-gray-800 rounded text-xs overflow-auto max-h-[150px]">
                          {this.state.errorInfo.componentStack}
                        </pre>
                      </div>
                    </div>
                  ),
                }]}
              />
            )}
          </Result>
        </div>
      )
    }
    return this.props.children
  }
}
