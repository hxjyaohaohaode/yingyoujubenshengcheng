import { useState, useEffect } from 'react'
import {
  Card, Button, Input, Select, App, Empty, Space,
  Breadcrumb,
} from 'antd'
import {
  SaveOutlined, WarningOutlined, DeleteOutlined, UndoOutlined,
  HomeOutlined, SettingOutlined,
  RobotOutlined, ApiOutlined, CheckCircleOutlined,
} from '@ant-design/icons'
import { useProjectStore } from '../stores/projectStore'
import { api, projectsApi } from '../api/client'
import { eventBus, DataEvents } from '../services/eventBus'
import ConfirmDialog from '../components/ConfirmDialog'

const GENRES = ['武侠', '仙侠', '奇幻', '科幻', '悬疑', '都市', '历史', '古装', '末世', '游戏', '动漫', '言情', '爱情', '推理', '冒险']

export default function Settings() {
  const { notification } = App.useApp()
  const { currentProject, setCurrentProject } = useProjectStore()
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [settings, setSettings] = useState({
      title: '',
      genre: '',
      target_words: 500000,
    })
  const [dirty, setDirty] = useState(false)
  const [confirmDelete, setConfirmDelete] = useState(false)
  const [confirmReset, setConfirmReset] = useState(false)
  const [apiStatus, setApiStatus] = useState<{
    deepseek: boolean
    mimo: boolean
    search: boolean
  }>({ deepseek: false, mimo: false, search: false })

  useEffect(() => {
    if (currentProject) {
      setSettings({
        title: currentProject.name || '',
        genre: currentProject.config?.genre || '',
        target_words: currentProject.config?.target_word_count || 500000,
      })
    }
  }, [currentProject])

  useEffect(() => {
    api.get<{
      deepseek_api_key_set: boolean
      mimo_api_key_set: boolean
      brave_api_key_set: boolean
      serpapi_key_set: boolean
      bing_api_key_set: boolean
    }>('/config/llm').then(data => {
      setApiStatus({
        deepseek: data.deepseek_api_key_set,
        mimo: data.mimo_api_key_set,
        search: data.brave_api_key_set || data.serpapi_key_set || data.bing_api_key_set,
      })
    }).catch(() => {})
  }, [])

  const updateField = <K extends keyof typeof settings>(key: K, value: typeof settings[K]) => {
    setSettings(prev => ({ ...prev, [key]: value }))
    setDirty(true)
  }

  const handleSave = async () => {
    if (!currentProject?.id) return
    setSaving(true)
    try {
      const payload: any = {
        name: settings.title,
        config: {
          genre: settings.genre,
          target_word_count: settings.target_words,
        },
      }
      const updated = await projectsApi.update(currentProject.id, payload)
      setCurrentProject(updated)
      eventBus.emit(DataEvents.PROJECT_CONFIG_UPDATED, { projectId: currentProject.id })
      setDirty(false)
      notification.success({ message: '项目设置已保存', placement: 'topRight' })
    } catch (e: any) {
      notification.error({
        message: '保存失败',
        description: e?.detail || e?.message || '请检查网络连接',
        placement: 'topRight',
      })
    }
    setSaving(false)
  }

  const handleDelete = async () => {
    if (!currentProject?.id) return
    try {
      await projectsApi.delete(currentProject.id)
      setCurrentProject(null)
      setConfirmDelete(false)
      notification.success({ message: '项目已删除', placement: 'topRight' })
    } catch (e: any) {
      notification.error({
        message: '删除失败',
        description: e?.detail || e?.message || '请检查网络连接',
        placement: 'topRight',
      })
    }
  }

  const handleReset = async () => {
    if (!currentProject?.id) return
    setSaving(true)
    try {
      await api.post(`/projects/${currentProject.id}/reset`)
      setConfirmReset(false)
      notification.success({ message: '项目已重置为默认设置', placement: 'topRight' })
      setDirty(false)
    } catch (e: any) {
      notification.error({
        message: '重置失败',
        description: e?.detail || e?.message || '请检查网络连接',
        placement: 'topRight',
      })
    }
    setSaving(false)
  }

  if (!currentProject) {
    return (
      <div style={{ fontFamily: 'var(--font-family)' }}>
        <h2 className="section-title" style={{ fontSize: 24 }}>变量规则</h2>
        <Card
          title={
            <div className="flex items-center gap-2">
              <ApiOutlined style={{ color: '#1677ff' }} />
              <span>外部服务 API 配置</span>
            </div>
          }
          size="small"
          extra={
            <Button
              type="primary"
              icon={<RobotOutlined />}
              onClick={() => window.dispatchEvent(new Event('open-llm-config'))}
            >
              配置 API
            </Button>
          }
          style={{ maxWidth: 500 }}
        >
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-sm">DeepSeek（创作 / 审计 / 伏笔 / 创意）</span>
              {apiStatus.deepseek ? (
                <span className="text-xs text-green-500 flex items-center gap-1"><CheckCircleOutlined /> 已配置</span>
              ) : (
                <span className="text-xs text-amber-500">未配置</span>
              )}
            </div>
            <div className="flex items-center justify-between">
              <span className="text-sm">MiMo（状态 / 素材 / 编排）</span>
              {apiStatus.mimo ? (
                <span className="text-xs text-green-500 flex items-center gap-1"><CheckCircleOutlined /> 已配置</span>
              ) : (
                <span className="text-xs text-gray-400">可选</span>
              )}
            </div>
            <div className="flex items-center justify-between">
              <span className="text-sm">联网搜索（Brave / SerpAPI / Bing）</span>
              {apiStatus.search ? (
                <span className="text-xs text-green-500 flex items-center gap-1"><CheckCircleOutlined /> 已配置</span>
              ) : (
                <span className="text-xs text-gray-400">可选</span>
              )}
            </div>
            {!apiStatus.deepseek && (
              <div className="text-xs text-amber-500 mt-2 p-2 rounded" style={{ background: 'var(--color-accent-soft)' }}>
                ⚠️ DeepSeek API 未配置，创作类功能将不可用。请点击「配置 API」按钮填写。
              </div>
            )}
          </div>
        </Card>
        <div className="card-surface" style={{ textAlign: 'center', padding: 48, marginTop: 16 }}>
          <Empty description={<span className="text-muted">请先创建或选择一个项目以编辑项目设置</span>} />
        </div>
      </div>
    )
  }

  return (
    <div style={{ fontFamily: 'var(--font-family)', flex: 1, overflow: 'auto', display: 'flex', flexDirection: 'column' }}>
      <Breadcrumb
        className="mb-4 text-xs"
        items={[
          { title: <><HomeOutlined className="mr-1" />项目</> },
          { title: <><SettingOutlined className="mr-1" />{currentProject.name}</> },
          { title: '变量规则' },
        ]}
      />

      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 24, flexShrink: 0 }}>
        <div>
          <h2 className="section-title" style={{ fontSize: 24 }}>变量规则</h2>
          <p className="text-muted" style={{ margin: '4px 0 0' }}>
            低代码编辑变量与触发规则
          </p>
        </div>
        <Space>
          {dirty && (
            <span className="text-xs text-amber-500 flex items-center gap-1">
              <WarningOutlined /> 有未保存的更改
            </span>
          )}
          <Button icon={<SaveOutlined />} type="primary" onClick={handleSave} loading={saving}
            disabled={!dirty}
          >
            保存设置
          </Button>
        </Space>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '3fr 2fr', gap: 16, flex: 1 }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          <Card title="基本信息" size="small">
            <div className="space-y-4">
              <div>
                <label className="text-sm text-gray-600 dark:text-gray-400 block mb-1">
                  项目名称 <span className="text-red-400">*</span>
                </label>
                <Input
                  value={settings.title}
                  onChange={e => updateField('title', e.target.value)}
                  placeholder="请输入项目名称"
                  status={!settings.title.trim() ? 'error' : undefined}
                />
                {!settings.title.trim() && (
                  <div className="text-xs text-red-400 mt-0.5">项目名称不能为空</div>
                )}
              </div>
              <div>
                <label className="text-sm text-gray-600 dark:text-gray-400 block mb-1">题材</label>
                <Select
                  className="w-full"
                  value={settings.genre || undefined}
                  onChange={v => updateField('genre', v)}
                  placeholder="选择题材"
                  options={GENRES.map(g => ({ value: g, label: g }))}
                  allowClear
                />
              </div>
              <div>
                <label className="text-sm text-gray-600 dark:text-gray-400 block mb-1">目标字数</label>
                <Select
                  className="w-full"
                  value={settings.target_words}
                  onChange={v => updateField('target_words', v)}
                  options={[
                    { value: 50000, label: '5万字（短篇）' },
                    { value: 150000, label: '15万字（中篇）' },
                    { value: 500000, label: '50万字（长篇）' },
                    { value: 1000000, label: '100万字（超长篇）' },
                    { value: 1500000, label: '150万字（史诗）' },
                  ]}
                />
              </div>
            </div>
          </Card>

          <Card
            title={
              <div className="flex items-center gap-2">
                <ApiOutlined style={{ color: '#1677ff' }} />
                <span>外部服务 API 配置</span>
              </div>
            }
            size="small"
            extra={
              <Button
                icon={<RobotOutlined />}
                onClick={() => window.dispatchEvent(new Event('open-llm-config'))}
              >
                配置 API
              </Button>
            }
          >
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="text-sm">DeepSeek</span>
                  <span className="text-xs text-gray-400">创作 / 审计 / 伏笔 / 创意</span>
                </div>
                {apiStatus.deepseek ? (
                  <span className="text-xs text-green-500 flex items-center gap-1">
                    <CheckCircleOutlined /> 已配置
                  </span>
                ) : (
                  <span className="text-xs text-amber-500">未配置</span>
                )}
              </div>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="text-sm">MiMo</span>
                  <span className="text-xs text-gray-400">状态 / 素材 / 编排</span>
                </div>
                {apiStatus.mimo ? (
                  <span className="text-xs text-green-500 flex items-center gap-1">
                    <CheckCircleOutlined /> 已配置
                  </span>
                ) : (
                  <span className="text-xs text-gray-400">可选</span>
                )}
              </div>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="text-sm">联网搜索</span>
                  <span className="text-xs text-gray-400">Brave / SerpAPI / Bing</span>
                </div>
                {apiStatus.search ? (
                  <span className="text-xs text-green-500 flex items-center gap-1">
                    <CheckCircleOutlined /> 已配置
                  </span>
                ) : (
                  <span className="text-xs text-gray-400">可选（有免费备用）</span>
                )}
              </div>
              {!apiStatus.deepseek && (
                <div className="text-xs text-amber-500 mt-2 p-2 rounded" style={{ background: 'var(--color-accent-soft)' }}>
                  ⚠️ DeepSeek API 未配置，创作类功能将不可用。请点击「配置 API」按钮填写。
                </div>
              )}
            </div>
          </Card>
        </div>

        <Card className="mb-4" title={
          <div className="flex items-center gap-2">
            <WarningOutlined className="text-red-500" />
            <span className="text-red-500">危险操作</span>
          </div>
        } size="small" style={{ display: 'flex', flexDirection: 'column' }}>
          <div className="space-y-4" style={{ flex: 1 }}>
            <div className="flex items-center justify-between p-3 rounded-lg bg-red-50/50 dark:bg-red-900/5 border border-red-100 dark:border-red-900/20">
              <div>
                <div className="text-sm font-medium">重置项目</div>
                <div className="text-xs text-gray-400 mt-0.5">将项目重置为初始状态，清除所有配置数据</div>
              </div>
              <Button danger onClick={() => setConfirmReset(true)} icon={<UndoOutlined />}>
                重置
              </Button>
            </div>
            <div className="flex items-center justify-between p-3 rounded-lg bg-red-50/50 dark:bg-red-900/5 border border-red-100 dark:border-red-900/20">
              <div>
                <div className="text-sm font-medium">删除项目</div>
                <div className="text-xs text-gray-400 mt-0.5">永久删除项目及所有关联数据（角色、场景、伏笔等）</div>
              </div>
              <Button danger type="primary" onClick={() => setConfirmDelete(true)} icon={<DeleteOutlined />}>
                删除项目
              </Button>
            </div>
          </div>
        </Card>
      </div>

      <ConfirmDialog
        open={confirmDelete}
        title="确认删除项目"
        content={`确定要永久删除「${currentProject.name}」吗？所有角色、场景、伏笔数据将被彻底清除，此操作不可撤销。`}
        danger
        okText="确认删除"
        onOk={handleDelete}
        onCancel={() => setConfirmDelete(false)}
      />

      <ConfirmDialog
        open={confirmReset}
        title="确认重置项目"
        content={`确定要重置「${currentProject.name}」吗？所有配置数据将被清空，但角色和场景数据保留。`}
        onOk={handleReset}
        onCancel={() => setConfirmReset(false)}
        okText="确认重置"
      />
    </div>
  )
}
