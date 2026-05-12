import { useEffect } from 'react'
import { Alert, App } from 'antd'
import { WifiOutlined } from '@ant-design/icons'
import { useNetworkStatus } from '../hooks/useApp'

export default function NetworkStatus() {
  const { isOnline, wasOffline } = useNetworkStatus()
  const { notification } = App.useApp()

  useEffect(() => {
    if (isOnline && wasOffline) {
      notification.success({
        message: '网络已恢复',
        description: '所有功能已恢复正常使用',
        placement: 'topRight',
        duration: 3,
        key: 'network-recovered',
      })
    }
  }, [isOnline, wasOffline])

  if (isOnline) return null

  return (
    <Alert
      type="warning"
      showIcon
      icon={<WifiOutlined />}
      message="网络连接已断开，部分功能不可用"
      description="请检查您的网络连接。实时协作、AI生成等功能需要稳定的网络连接。"
      banner
      closable={false}
      className="sticky top-0 z-[1001] rounded-none border-0"
      style={{
        background: 'linear-gradient(90deg, #faad14, #fa8c16)',
        color: '#fff',
      }}
    />
  )
}
