import { Modal, Checkbox, Alert, Tag, Space, Typography } from 'antd'
import { ExclamationCircleOutlined, DeleteOutlined, WarningOutlined } from '@ant-design/icons'
import { useState } from 'react'

interface ImpactInfo {
  type: string
  count: number
  label: string
}

interface ConfirmDialogProps {
  open: boolean
  title?: string
  content: string
  okText?: string
  cancelText?: string
  danger?: boolean
  onOk: () => void
  onCancel: () => void
  destructive?: boolean
  impactList?: ImpactInfo[]
  impactDescription?: string
  loading?: boolean
}

export default function ConfirmDialog({
  open,
  title = '确认操作',
  content,
  okText = '确认',
  cancelText = '取消',
  danger = false,
  onOk,
  onCancel,
  destructive = false,
  impactList,
  impactDescription,
  loading = false,
}: ConfirmDialogProps) {
  const [confirmedDestructive, setConfirmedDestructive] = useState(false)

  const okDisabled = destructive && !confirmedDestructive

  return (
    <Modal
      open={open}
      title={
        <div className="flex items-center gap-2">
          {destructive ? (
            <DeleteOutlined className="text-red-500" />
          ) : (
            <ExclamationCircleOutlined className={danger ? 'text-red-500' : 'text-amber-500'} />
          )}
          <span>{title}</span>
        </div>
      }
      okText={destructive ? '永久删除' : okText}
      cancelText={cancelText}
      okButtonProps={{
        danger: destructive || danger,
        disabled: okDisabled,
        icon: destructive ? <DeleteOutlined /> : undefined,
        loading,
      }}
      onOk={onOk}
      onCancel={onCancel}
      centered
      destroyOnHidden
    >
      <div className="my-3 space-y-3">
        <Typography.Text className="text-gray-700 dark:text-gray-300">
          {content}
        </Typography.Text>

        {impactDescription && (
          <Alert
            type="warning"
            showIcon
            icon={<WarningOutlined />}
            message={impactDescription}
            className="text-sm"
          />
        )}

        {impactList && impactList.length > 0 && (
          <div className="bg-gray-50 dark:bg-gray-800 rounded-lg p-3">
            <Typography.Text type="secondary" className="text-xs mb-2 block">
              此操作将影响以下内容：
            </Typography.Text>
            <Space wrap size={[4, 4]}>
              {impactList.map((impact) => (
                <Tag key={impact.type} color="orange">
                  {impact.label}: <strong>{impact.count}</strong>
                </Tag>
              ))}
            </Space>
          </div>
        )}

        {destructive && (
          <Checkbox
            checked={confirmedDestructive}
            onChange={(e) => setConfirmedDestructive(e.target.checked)}
            className="text-red-500"
          >
            <span className="text-sm text-red-500">
              我确认要永久删除此内容，此操作不可撤销
            </span>
          </Checkbox>
        )}
      </div>
    </Modal>
  )
}
