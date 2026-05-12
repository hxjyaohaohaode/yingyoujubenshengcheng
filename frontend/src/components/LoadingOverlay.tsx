import { Spin } from 'antd'
import { LoadingOutlined } from '@ant-design/icons'

interface LoadingOverlayProps {
  message?: string
  visible: boolean
}

export default function LoadingOverlay({ message = '处理中...', visible }: LoadingOverlayProps) {
  if (!visible) return null

  return (
    <div className="fixed inset-0 z-[1000] flex items-center justify-center bg-black/20 dark:bg-black/40 backdrop-blur-sm transition-all">
      <div className="bg-white dark:bg-slate-800 rounded-xl shadow-2xl p-8 flex flex-col items-center gap-4 min-w-[200px]">
        <Spin indicator={<LoadingOutlined style={{ fontSize: 36 }} spin />} />
        <span className="text-sm text-gray-500 dark:text-gray-400">{message}</span>
      </div>
    </div>
  )
}
