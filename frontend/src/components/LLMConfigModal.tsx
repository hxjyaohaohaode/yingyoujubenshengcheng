import { useState, useEffect } from 'react'
import { Modal, Card, Button, Input, App } from 'antd'
import {
  KeyOutlined, ApiOutlined, CheckCircleOutlined,
} from '@ant-design/icons'
import { api } from '../api/client'

interface LLMConfig {
  deepseek_base_url: string
  deepseek_api_key: string
  mimo_base_url: string
  mimo_api_key: string
}

interface LLMConfigModalProps {
  open: boolean
  onClose: () => void
}

export default function LLMConfigModal({ open, onClose }: LLMConfigModalProps) {
  const { notification } = App.useApp()
  const [config, setConfig] = useState<LLMConfig>({
    deepseek_base_url: '',
    deepseek_api_key: '',
    mimo_base_url: '',
    mimo_api_key: '',
  })
  const [originalConfig, setOriginalConfig] = useState<LLMConfig>({
    deepseek_base_url: '',
    deepseek_api_key: '',
    mimo_base_url: '',
    mimo_api_key: '',
  })
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    if (open) {
      fetchConfig()
    }
  }, [open])

  const fetchConfig = async () => {
    setLoading(true)
    try {
      const data = await api.get<{
        deepseek_base_url: string
        deepseek_api_key_set: boolean
        mimo_base_url: string
        mimo_api_key_set: boolean
      }>('/config/llm')
      const newConfig: LLMConfig = {
        deepseek_base_url: data.deepseek_base_url || '',
        deepseek_api_key: data.deepseek_api_key_set ? '••••••••' : '',
        mimo_base_url: data.mimo_base_url || '',
        mimo_api_key: data.mimo_api_key_set ? '••••••••' : '',
      }
      setConfig(newConfig)
      setOriginalConfig({ ...newConfig })
    } catch (e: any) {
      notification.error({
        message: '获取配置失败',
        description: e?.detail || e?.message || '请检查网络连接',
        placement: 'topRight',
      })
    }
    setLoading(false)
  }

  const updateField = <K extends keyof LLMConfig>(key: K, value: LLMConfig[K]) => {
    setConfig(prev => ({ ...prev, [key]: value }))
  }

  const handleSaveProvider = async (provider: 'deepseek' | 'mimo') => {
    setSaving(true)
    try {
      const payload: Partial<LLMConfig> = {}
      if (provider === 'deepseek') {
        payload.deepseek_base_url = config.deepseek_base_url || undefined
        if (config.deepseek_api_key && config.deepseek_api_key !== '••••••••') {
          payload.deepseek_api_key = config.deepseek_api_key
        }
      } else {
        payload.mimo_base_url = config.mimo_base_url || undefined
        if (config.mimo_api_key && config.mimo_api_key !== '••••••••') {
          payload.mimo_api_key = config.mimo_api_key
        }
      }

      await api.post('/config/llm', payload)
      notification.success({ message: `${provider === 'deepseek' ? 'DeepSeek' : 'MiMo'} 配置已生效`, placement: 'topRight' })
      await fetchConfig()
    } catch (e: any) {
      notification.error({
        message: '保存失败',
        description: e?.detail || e?.message || '请检查网络连接',
        placement: 'topRight',
      })
    }
    setSaving(false)
  }

  const hasDeepSeekChanges =
    config.deepseek_base_url !== originalConfig.deepseek_base_url ||
    (config.deepseek_api_key !== originalConfig.deepseek_api_key && config.deepseek_api_key !== '••••••••')

  const hasMimoChanges =
    config.mimo_base_url !== originalConfig.mimo_base_url ||
    (config.mimo_api_key !== originalConfig.mimo_api_key && config.mimo_api_key !== '••••••••')

  return (
    <Modal
      title="大模型 API 配置"
      open={open}
      onCancel={onClose}
      footer={null}
      width={560}
      destroyOnHidden
    >
      <div style={{ marginTop: 8 }}>
        <p className="text-muted text-sm" style={{ marginBottom: 16 }}>
          配置 DeepSeek 和 MiMo 的 API 接入信息，修改后即时生效
        </p>

        <Card
          className="mb-4"
          title={
            <div className="flex items-center gap-2">
              <ApiOutlined style={{ color: '#1677ff' }} />
              <span>DeepSeek</span>
              {originalConfig.deepseek_api_key && originalConfig.deepseek_api_key !== '' && (
                <CheckCircleOutlined style={{ color: '#52c41a', fontSize: 14 }} />
              )}
            </div>
          }
          size="small"
          extra={
            <Button
              type="primary"
              size="small"
              loading={saving}
              disabled={!hasDeepSeekChanges}
              onClick={() => handleSaveProvider('deepseek')}
            >
              保存并生效
            </Button>
          }
        >
          <div className="space-y-4">
            <div>
              <label className="text-sm text-gray-600 dark:text-gray-400 block mb-1">
                Base URL
              </label>
              <Input
                value={config.deepseek_base_url}
                onChange={e => updateField('deepseek_base_url', e.target.value)}
                placeholder="https://api.deepseek.com/v1"
              />
              <div className="text-xs text-gray-400 mt-1">默认: https://api.deepseek.com/v1</div>
            </div>
            <div>
              <label className="text-sm text-gray-600 dark:text-gray-400 block mb-1">
                API 密钥
              </label>
              <Input.Password
                value={config.deepseek_api_key}
                onChange={e => updateField('deepseek_api_key', e.target.value)}
                placeholder="sk-..."
                iconRender={visible => (visible ? <KeyOutlined /> : <KeyOutlined />)}
              />
              {originalConfig.deepseek_api_key === '••••••••' && config.deepseek_api_key === '••••••••' && (
                <div className="text-xs text-green-500 mt-1 flex items-center gap-1">
                  <CheckCircleOutlined /> 已配置 API 密钥
                </div>
              )}
            </div>
          </div>
        </Card>

        <Card
          className="mb-4"
          title={
            <div className="flex items-center gap-2">
              <ApiOutlined style={{ color: '#fa8c16' }} />
              <span>MiMo</span>
              {originalConfig.mimo_api_key && originalConfig.mimo_api_key !== '' && (
                <CheckCircleOutlined style={{ color: '#52c41a', fontSize: 14 }} />
              )}
            </div>
          }
          size="small"
          extra={
            <Button
              type="primary"
              size="small"
              loading={saving}
              disabled={!hasMimoChanges}
              onClick={() => handleSaveProvider('mimo')}
            >
              保存并生效
            </Button>
          }
        >
          <div className="space-y-4">
            <div>
              <label className="text-sm text-gray-600 dark:text-gray-400 block mb-1">
                Base URL
              </label>
              <Input
                value={config.mimo_base_url}
                onChange={e => updateField('mimo_base_url', e.target.value)}
                placeholder="https://token-plan-cn.xiaomimimo.com/v1"
              />
              <div className="text-xs text-gray-400 mt-1">默认: https://token-plan-cn.xiaomimimo.com/v1</div>
            </div>
            <div>
              <label className="text-sm text-gray-600 dark:text-gray-400 block mb-1">
                API 密钥
              </label>
              <Input.Password
                value={config.mimo_api_key}
                onChange={e => updateField('mimo_api_key', e.target.value)}
                placeholder="..."
                iconRender={visible => (visible ? <KeyOutlined /> : <KeyOutlined />)}
              />
              {originalConfig.mimo_api_key === '••••••••' && config.mimo_api_key === '••••••••' && (
                <div className="text-xs text-green-500 mt-1 flex items-center gap-1">
                  <CheckCircleOutlined /> 已配置 API 密钥
                </div>
              )}
            </div>
          </div>
        </Card>
      </div>
    </Modal>
  )
}
