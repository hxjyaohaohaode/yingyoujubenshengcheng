import { useState, useEffect } from 'react'
import {
  Card, Button, Input, Select, App, Empty, Space,
  Breadcrumb,
} from 'antd'
import {
  SaveOutlined, WarningOutlined, DeleteOutlined, UndoOutlined,
  HomeOutlined, SettingOutlined,
} from '@ant-design/icons'
import { useProjectStore } from '../stores/projectStore'
import { api, projectsApi } from '../api/client'
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

  useEffect(() => {
    if (currentProject) {
      setSettings({
        title: currentProject.name || '',
        genre: currentProject.config?.genre || '',
        target_words: currentProject.config?.target_word_count || 500000,
      })
    }
  }, [currentProject])

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
        <div className="card-surface" style={{ textAlign: 'center', padding: 48 }}>
          <Empty description={<span className="text-muted">请先创建或选择一个项目</span>} />
        </div>
      </div>
    )
  }

  return (
    <div style={{ fontFamily: 'var(--font-family)' }}>
      <Breadcrumb
        className="mb-4 text-xs"
        items={[
          { title: <><HomeOutlined className="mr-1" />项目</> },
          { title: <><SettingOutlined className="mr-1" />{currentProject.name}</> },
          { title: '变量规则' },
        ]}
      />

      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 24 }}>
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

      <div className="max-w-2xl">
        <Card className="mb-4" title="基本信息" size="small">
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

        <Card className="mb-4" title={
          <div className="flex items-center gap-2">
            <WarningOutlined className="text-red-500" />
            <span className="text-red-500">危险操作</span>
          </div>
        } size="small">
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <div>
                <div className="text-sm font-medium">重置项目</div>
                <div className="text-xs text-gray-400">将项目重置为初始状态，清除所有配置数据</div>
              </div>
              <Button danger onClick={() => setConfirmReset(true)} icon={<UndoOutlined />}>
                重置
              </Button>
            </div>
            <div className="flex items-center justify-between">
              <div>
                <div className="text-sm font-medium">删除项目</div>
                <div className="text-xs text-gray-400">永久删除项目及所有关联数据（角色、场景、伏笔等）</div>
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
