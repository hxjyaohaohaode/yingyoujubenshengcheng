import { Spin } from 'antd'
import { LoadingOutlined } from '@ant-design/icons'

interface LoadingSpinnerProps {
  tip?: string
  fullScreen?: boolean
  size?: 'small' | 'default' | 'large'
}

export default function LoadingSpinner({ tip = '加载中...', fullScreen = false, size = 'default' }: LoadingSpinnerProps) {
  const icon = <LoadingOutlined style={{ fontSize: size === 'large' ? 40 : 24 }} spin />

  if (fullScreen) {
    return (
      <div className="fixed inset-0 flex items-center justify-center bg-white/80 dark:bg-slate-900/80 z-50">
        <Spin indicator={icon} tip={tip}>
          <div className="p-12" />
        </Spin>
      </div>
    )
  }

  return (
    <div className="flex items-center justify-center py-12">
      <Spin indicator={icon} tip={tip}>
        <div className="p-8" />
      </Spin>
    </div>
  )
}
