import { useState, useEffect } from 'react'
import { Modal, Card, Button, Input, App, Badge, Alert } from 'antd'
import {
  KeyOutlined, ApiOutlined, CheckCircleOutlined,
  SearchOutlined, GlobalOutlined, ReloadOutlined,
} from '@ant-design/icons'
import { api, API_BASE } from '../api/client'

interface LLMConfig {
  deepseek_base_url: string
  deepseek_api_key: string
  mimo_base_url: string
  mimo_api_key: string
  brave_api_key: string
  serpapi_key: string
  bing_api_key: string
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
    brave_api_key: '',
    serpapi_key: '',
    bing_api_key: '',
  })
  const [originalConfig, setOriginalConfig] = useState<LLMConfig>({
    deepseek_base_url: '',
    deepseek_api_key: '',
    mimo_base_url: '',
    mimo_api_key: '',
    brave_api_key: '',
    serpapi_key: '',
    bing_api_key: '',
  })
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [backendOffline, setBackendOffline] = useState(false)
  const [waking, setWaking] = useState(false)

  useEffect(() => {
    if (open) {
      fetchConfig()
    }
  }, [open])

  const wakeBackend = async () => {
    setWaking(true)
    setBackendOffline(false)
    const baseUrl = API_BASE.replace(/\/api$/, '')
    for (let i = 0; i < 6; i++) {
      try {
        await fetch(`${baseUrl}/api/health`, { method: 'GET', signal: AbortSignal.timeout(10000) })
        setWaking(false)
        await fetchConfig()
        return
      } catch {
        await new Promise(r => setTimeout(r, 5000))
      }
    }
    setWaking(false)
    setBackendOffline(true)
  }

  const fetchConfig = async () => {
    setLoading(true)
    setBackendOffline(false)
    try {
      const data = await api.get<{
        deepseek_base_url: string
        deepseek_api_key_set: boolean
        mimo_base_url: string
        mimo_api_key_set: boolean
        brave_api_key_set: boolean
        serpapi_key_set: boolean
        bing_api_key_set: boolean
      }>('/config/llm')
      const newConfig: LLMConfig = {
        deepseek_base_url: data.deepseek_base_url || '',
        deepseek_api_key: data.deepseek_api_key_set ? '••••••••' : '',
        mimo_base_url: data.mimo_base_url || '',
        mimo_api_key: data.mimo_api_key_set ? '••••••••' : '',
        brave_api_key: data.brave_api_key_set ? '••••••••' : '',
        serpapi_key: data.serpapi_key_set ? '••••••••' : '',
        bing_api_key: data.bing_api_key_set ? '••••••••' : '',
      }
      setConfig(newConfig)
      setOriginalConfig({ ...newConfig })
    } catch (e: any) {
      setBackendOffline(true)
      notification.error({
        message: '无法连接后端',
        description: '后端服务可能正在唤醒中，请点击「唤醒后端」按钮重试',
        placement: 'topRight',
      })
    }
    setLoading(false)
  }

  const updateField = <K extends keyof LLMConfig>(key: K, value: LLMConfig[K]) => {
    setConfig(prev => ({ ...prev, [key]: value }))
  }

  const handleSaveProvider = async (provider: 'deepseek' | 'mimo' | 'search') => {
    setSaving(true)
    try {
      const payload: any = {}
      if (provider === 'deepseek') {
        payload.deepseek_base_url = config.deepseek_base_url || undefined
        if (config.deepseek_api_key && config.deepseek_api_key !== '••••••••') {
          payload.deepseek_api_key = config.deepseek_api_key
        }
      } else if (provider === 'mimo') {
        payload.mimo_base_url = config.mimo_base_url || undefined
        if (config.mimo_api_key && config.mimo_api_key !== '••••••••') {
          payload.mimo_api_key = config.mimo_api_key
        }
      } else {
        if (config.brave_api_key && config.brave_api_key !== '••••••••') {
          payload.brave_api_key = config.brave_api_key
        }
        if (config.serpapi_key && config.serpapi_key !== '••••••••') {
          payload.serpapi_key = config.serpapi_key
        }
        if (config.bing_api_key && config.bing_api_key !== '••••••••') {
          payload.bing_api_key = config.bing_api_key
        }
      }

      await api.post('/config/llm', payload)
      const label = provider === 'deepseek' ? 'DeepSeek' : provider === 'mimo' ? 'MiMo' : '搜索'
      notification.success({ message: `${label} 配置已生效`, placement: 'topRight' })
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

  const hasSearchChanges =
    (config.brave_api_key !== originalConfig.brave_api_key && config.brave_api_key !== '••••••••') ||
    (config.serpapi_key !== originalConfig.serpapi_key && config.serpapi_key !== '••••••••') ||
    (config.bing_api_key !== originalConfig.bing_api_key && config.bing_api_key !== '••••••••')

  const deepseekReady = originalConfig.deepseek_api_key === '••••••••'
  const mimoReady = originalConfig.mimo_api_key === '••••••••'
  const searchReady = originalConfig.brave_api_key === '••••••••' || originalConfig.serpapi_key === '••••••••' || originalConfig.bing_api_key === '••••••••'

  return (
    <Modal
      title="外部服务 API 配置"
      open={open}
      onCancel={onClose}
      footer={null}
      width={600}
      destroyOnHidden
    >
      <div style={{ marginTop: 8 }}>
        {backendOffline && (
          <Alert
            type="warning"
            showIcon
            message="后端服务未连接"
            description={
              <div>
                <p style={{ margin: '4px 0' }}>后端服务可能正在休眠（Render 免费版会自动休眠），或尚未启动完成。</p>
                <Button
                  type="primary"
                  size="small"
                  icon={<ReloadOutlined />}
                  loading={waking}
                  onClick={wakeBackend}
                >
                  {waking ? '正在唤醒后端（约需30秒）...' : '唤醒后端'}
                </Button>
              </div>
            }
            style={{ marginBottom: 16 }}
          />
        )}
        {waking && (
          <Alert
            type="info"
            showIcon
            message="正在唤醒后端服务..."
            description="Render 免费版的后端在无活动15分钟后会自动休眠，首次唤醒约需30秒，请耐心等待。"
            style={{ marginBottom: 16 }}
          />
        )}
        {!backendOffline && !waking && (
          <p className="text-muted text-sm" style={{ marginBottom: 16 }}>
            配置大模型和联网搜索的 API 接入信息，修改后即时生效。至少配置一个 LLM 提供商才能使用创作功能。
          </p>

        <Card
          className="mb-4"
          title={
            <div className="flex items-center gap-2">
              <ApiOutlined style={{ color: '#1677ff' }} />
              <span>DeepSeek（创作 / 审计 / 伏笔 / 创意）</span>
              {deepseekReady && (
                <Badge status="success" />
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
                API 密钥 <span className="text-red-400">*</span>
              </label>
              <Input.Password
                value={config.deepseek_api_key}
                onChange={e => updateField('deepseek_api_key', e.target.value)}
                placeholder="sk-..."
                iconRender={visible => (visible ? <KeyOutlined /> : <KeyOutlined />)}
              />
              {deepseekReady && config.deepseek_api_key === '••••••••' && (
                <div className="text-xs text-green-500 mt-1 flex items-center gap-1">
                  <CheckCircleOutlined /> 已配置
                </div>
              )}
              {!deepseekReady && (
                <div className="text-xs text-amber-500 mt-1">未配置 — 创作类功能将不可用</div>
              )}
            </div>
          </div>
        </Card>

        <Card
          className="mb-4"
          title={
            <div className="flex items-center gap-2">
              <ApiOutlined style={{ color: '#fa8c16' }} />
              <span>MiMo（状态 / 素材 / 编排）</span>
              {mimoReady && (
                <Badge status="success" />
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
              {mimoReady && config.mimo_api_key === '••••••••' && (
                <div className="text-xs text-green-500 mt-1 flex items-center gap-1">
                  <CheckCircleOutlined /> 已配置
                </div>
              )}
              {!mimoReady && (
                <div className="text-xs text-gray-400 mt-1">可选 — 未配置时将使用 DeepSeek 作为回退</div>
              )}
            </div>
          </div>
        </Card>

        <Card
          className="mb-4"
          title={
            <div className="flex items-center gap-2">
              <GlobalOutlined style={{ color: '#52c41a' }} />
              <span>联网搜索（可选）</span>
              {searchReady && (
                <Badge status="success" />
              )}
            </div>
          }
          size="small"
          extra={
            <Button
              type="primary"
              size="small"
              loading={saving}
              disabled={!hasSearchChanges}
              onClick={() => handleSaveProvider('search')}
            >
              保存并生效
            </Button>
          }
        >
          <div className="space-y-4">
            <div className="text-xs text-gray-400" style={{ marginBottom: 8 }}>
              至少配置一个搜索引擎即可启用联网搜索。未配置时将使用 DuckDuckGo 免费搜索（可能不稳定）。
            </div>
            <div>
              <label className="text-sm text-gray-600 dark:text-gray-400 block mb-1">
                <SearchOutlined className="mr-1" />Brave Search API Key
              </label>
              <Input.Password
                value={config.brave_api_key}
                onChange={e => updateField('brave_api_key', e.target.value)}
                placeholder="BSA-..."
                iconRender={visible => (visible ? <KeyOutlined /> : <KeyOutlined />)}
              />
              {originalConfig.brave_api_key === '••••••••' && config.brave_api_key === '••••••••' && (
                <div className="text-xs text-green-500 mt-1 flex items-center gap-1">
                  <CheckCircleOutlined /> 已配置
                </div>
              )}
            </div>
            <div>
              <label className="text-sm text-gray-600 dark:text-gray-400 block mb-1">
                <SearchOutlined className="mr-1" />SerpAPI Key
              </label>
              <Input.Password
                value={config.serpapi_key}
                onChange={e => updateField('serpapi_key', e.target.value)}
                placeholder="..."
                iconRender={visible => (visible ? <KeyOutlined /> : <KeyOutlined />)}
              />
              {originalConfig.serpapi_key === '••••••••' && config.serpapi_key === '••••••••' && (
                <div className="text-xs text-green-500 mt-1 flex items-center gap-1">
                  <CheckCircleOutlined /> 已配置
                </div>
              )}
            </div>
            <div>
              <label className="text-sm text-gray-600 dark:text-gray-400 block mb-1">
                <SearchOutlined className="mr-1" />Bing Search API Key
              </label>
              <Input.Password
                value={config.bing_api_key}
                onChange={e => updateField('bing_api_key', e.target.value)}
                placeholder="..."
                iconRender={visible => (visible ? <KeyOutlined /> : <KeyOutlined />)}
              />
              {originalConfig.bing_api_key === '••••••••' && config.bing_api_key === '••••••••' && (
                <div className="text-xs text-green-500 mt-1 flex items-center gap-1">
                  <CheckCircleOutlined /> 已配置
                </div>
              )}
            </div>
          </div>
        </Card>
        )}
      </div>
    </Modal>
  )
}
