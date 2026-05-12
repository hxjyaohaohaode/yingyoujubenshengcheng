import { useState, useEffect } from 'react'
import { Card, Input, Button, Tag, Space, App, Modal, Tooltip, Empty, Spin } from 'antd'
import {
  GlobalOutlined, LockOutlined, UnlockOutlined, RobotOutlined,
  CheckCircleOutlined, LoadingOutlined, BulbOutlined,
} from '@ant-design/icons'
import { useProjectStore } from '../stores/projectStore'
import { api } from '../api/client'
import { eventBus, DataEvents } from '../services/eventBus'
import ConfirmDialog from '../components/ConfirmDialog'

const { TextArea } = Input

interface ConfigItem {
  key: string
  label: string
  desc: string
}

const WORLD_CONFIGS: ConfigItem[] = [
  { key: 'core_contradiction', label: '核心矛盾', desc: '世界运行的终极矛盾，驱动所有剧情发展的核心动力' },
  { key: 'social_structure', label: '社会结构', desc: '权力分布、阶层划分、组织关系' },
  { key: 'tech_magic', label: '科技/魔法体系', desc: '能力上限、代价、规则、稀有度' },
  { key: 'geography', label: '地理环境', desc: '世界地图、重要地标、气候特征' },
  { key: 'history', label: '历史背景', desc: '重大历史事件、传说、被掩盖的真相' },
  { key: 'culture', label: '文化习俗', desc: '信仰、节日、禁忌、性别观、道德观' },
  { key: 'constraints', label: '约束条件', desc: '人物行为在剧情中的硬性限制' },
  { key: 'impossible', label: '不可能事项', desc: '这个世界绝对不可能发生的事' },
]

interface LockState {
  isLocked: boolean
  lockedAt?: string
  id?: string
}

export default function WorldSettings() {
  const { notification } = App.useApp()
  const { currentProject } = useProjectStore()
  const [activeKey, setActiveKey] = useState<string>(WORLD_CONFIGS[0].key)
  const [content, setContent] = useState<Record<string, string>>({})
  const [locks, setLocks] = useState<Record<string, LockState>>({})
  const [generating, setGenerating] = useState<string | null>(null)
  const [proposals, setProposals] = useState<{ key: string; items: string[] } | null>(null)
  const [confirmOpen, setConfirmOpen] = useState<{ key: string; type: 'lock' | 'unlock' } | null>(null)
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)

  const fetchConfigs = async () => {
    if (!currentProject?.id) return
    setLoading(true)
    try {
      const data = await api.get<{ configs: any[] }>(`/projects/${currentProject.id}/config`)
      const newContent: Record<string, string> = {}
      const newLocks: Record<string, LockState> = {}
      for (const c of data.configs) {
        if (typeof c.config_key === 'string') {
          newContent[c.config_key] = c.config_value || ''
          if (c.is_locked) {
            newLocks[c.config_key] = { isLocked: true, lockedAt: c.locked_at, id: c.id }
          }
        }
      }
      setContent(newContent)
      setLocks(newLocks)
    } catch {
      notification.error({ message: '配置加载失败', description: '无法加载世界观配置', placement: 'topRight' })
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    let cancelled = false
    if (!currentProject?.id) return
    setLoading(true)
    api.get<{ configs: any[] }>(`/projects/${currentProject.id}/config`)
      .then(data => {
        if (cancelled) return
        const newContent: Record<string, string> = {}
        const newLocks: Record<string, LockState> = {}
        for (const c of data.configs) {
          if (typeof c.config_key === 'string') {
            newContent[c.config_key] = c.config_value || ''
            if (c.is_locked) {
              newLocks[c.config_key] = { isLocked: true, lockedAt: c.locked_at, id: c.id }
            }
          }
        }
        setContent(newContent)
        setLocks(newLocks)
        setLoading(false)
      })
      .catch(() => {
        if (!cancelled) setLoading(false)
      })
    return () => { cancelled = true }
  }, [currentProject?.id])

  useEffect(() => {
    const unsub = eventBus.on(DataEvents.WORLD_CONFIG_UPDATED, () => {
      fetchConfigs()
    })
    return unsub
  }, [currentProject?.id])

  const handleChange = async (value: string) => {
    setContent(prev => ({ ...prev, [activeKey]: value }))
  }

  const saveConfig = async (key: string, value: string) => {
    if (!currentProject?.id) return
    try {
      const currentLock = locks[key]?.isLocked ?? false
      await api.put(`/projects/${currentProject.id}/config/${key}`, {
        config_value: value,
        is_locked: currentLock,
      })
    } catch {
      notification.warning({ message: '自动保存失败', description: '配置可能未保存，请手动保存', placement: 'topRight' })
    }
  }

  const handleBlur = () => {
    const currentValue = content[activeKey] || ''
    saveConfig(activeKey, currentValue)
  }

  const handleLockToggle = async () => {
    if (isLocked) {
      setConfirmOpen({ key: activeKey, type: 'unlock' })
    } else {
      const current = content[activeKey]
      if (!current || current.trim().length === 0) {
        notification.warning({ message: '内容为空', description: '请先填写内容后再锁定', placement: 'topRight' })
        return
      }
      setConfirmOpen({ key: activeKey, type: 'lock' })
    }
  }

  const confirmLockToggle = async () => {
    if (!confirmOpen || !currentProject?.id) return
    const { key, type } = confirmOpen
    setSaving(true)
    try {
      await api.put(`/projects/${currentProject.id}/config/${key}`, {
        config_value: content[key] || '',
        is_locked: type === 'lock',
      })
      await fetchConfigs()
      notification.success({
        message: type === 'lock' ? '已锁定' : '已解锁',
        description: type === 'lock' ? '该配置项已被锁定，无法编辑' : '该配置项已解锁，可以编辑',
        placement: 'topRight',
      })
    } catch (e) {
      notification.error({
        message: '操作失败',
        description: (e as Error).message || '请检查网络连接',
        placement: 'topRight',
      })
    } finally {
      setSaving(false)
    }
    setConfirmOpen(null)
  }

  const activeConfig = WORLD_CONFIGS.find(c => c.key === activeKey)!
  const isLocked = locks[activeKey]?.isLocked ?? false

  const handleAIGenerate = async () => {
    if (!currentProject) {
      notification.warning({ message: '请先选择项目', placement: 'topRight' })
      return
    }
    setGenerating(activeKey)
    setProposals(null)
    try {
      const res = await api.post<{ proposals: string[] }>(
        `/ai/world-gen/${currentProject.id}/${activeKey}`
      )
      if (res.proposals && res.proposals.length > 0) {
        setProposals({ key: activeKey, items: res.proposals })
      }
    } catch (e) {
      notification.error({
        message: 'AI 生成失败',
        description: (e as Error).message || '请检查 AI 服务',
        placement: 'topRight',
      })
    } finally {
      setGenerating(null)
    }
  }

  const selectProposal = (text: string) => {
    setContent(prev => ({ ...prev, [activeKey]: text }))
    saveConfig(activeKey, text)
    setProposals(null)
    eventBus.emit(DataEvents.WORLD_CONFIG_UPDATED, { key: activeKey })
    notification.success({ message: '方案已应用', placement: 'topRight' })
  }

  const isContentEmpty = !content[activeKey] || content[activeKey].trim().length === 0

  if (!currentProject) {
    return (
      <div>
        <h1 className="text-2xl font-bold mb-6">世界观设置</h1>
        <Card className="text-center py-12">
          <Empty description={<span className="text-gray-400">请先创建或选择一个项目</span>} />
        </Card>
      </div>
    )
  }

  if (loading) {
    return (
      <div className="h-full flex items-center justify-center">
        <Spin size="large">
          <div className="p-12 text-gray-400">加载世界观配置...</div>
        </Spin>
      </div>
    )
  }

  const lockedCount = Object.values(locks).filter(l => l.isLocked).length

  return (
    <div style={{ fontFamily: 'var(--font-family)', height: '100%', overflow: 'auto' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 24, flexShrink: 0 }}>
        <div>
          <h2 className="section-title" style={{ fontSize: 24 }}>世界观与改编策略</h2>
          <p className="text-muted" style={{ margin: '4px 0 0' }}>
            {currentProject?.name || '未命名影游'} · 构建世界观基础与互动规则
          </p>
        </div>
      </div>

      <div className="flex gap-4 flex-1 min-h-0">
        <div className="w-[220px] shrink-0 bg-gray-50 dark:bg-slate-800 rounded-lg p-2 overflow-auto">
          {WORLD_CONFIGS.map(item => {
            const hasContent = content[item.key] && content[item.key].trim().length > 0
            const itemLocked = locks[item.key]?.isLocked
            return (
              <div
                key={item.key}
                onClick={() => { setActiveKey(item.key); setProposals(null) }}
                className={`
                  flex items-center gap-2 px-3 py-2.5 rounded-md cursor-pointer mb-0.5 transition-all
                  ${activeKey === item.key
                    ? 'bg-primary-50 dark:bg-primary-900/20 text-primary-700 dark:text-primary-300 font-medium'
                    : 'hover:bg-gray-100 dark:hover:bg-slate-700 text-gray-700 dark:text-slate-300'}
                `}
              >
                <div className="flex-1 min-w-0">
                  <div className="text-sm truncate">{item.label}</div>
                </div>
                <div className="flex items-center gap-1 shrink-0">
                  {hasContent && <CheckCircleOutlined className="text-green-500 text-xs" />}
                  {itemLocked && <LockOutlined className="text-gray-400 text-xs" />}
                </div>
              </div>
            )
          })}
        </div>

        <div className="flex-1 flex flex-col gap-3 min-w-0 overflow-hidden">
          <div className="flex items-center justify-between flex-shrink-0">
            <div>
              <h2 className="text-lg font-semibold m-0">{activeConfig.label}</h2>
              <p className="text-xs text-gray-400 mt-0.5">{activeConfig.desc}</p>
            </div>
            <Space>
              {isLocked && (
                <Tag color="default" icon={<LockOutlined />} className="select-none">
                  已锁定 {locks[activeKey]?.lockedAt ? `· ${new Date(locks[activeKey].lockedAt!).toLocaleString('zh-CN')}` : ''}
                </Tag>
              )}
              <Tooltip title={isLocked ? '解锁' : '锁定（锁定后不可编辑）'}>
                <Button
                  icon={isLocked ? <UnlockOutlined /> : <LockOutlined />}
                  onClick={handleLockToggle}
                  type={isLocked ? 'default' : 'primary'}
                  ghost={!isLocked}
                  size="small"
                  loading={saving}
                >
                  {isLocked ? '解锁' : '锁定'}
                </Button>
              </Tooltip>
              <Button
                icon={generating === activeKey ? <LoadingOutlined /> : <BulbOutlined />}
                onClick={handleAIGenerate}
                loading={generating === activeKey}
                disabled={isLocked}
                size="small"
              >
                AI 生成方案
              </Button>
            </Space>
          </div>

          {!isContentEmpty && !isLocked && (
            <div className="text-xs text-amber-500 bg-amber-50 dark:bg-amber-900/10 border border-amber-200 dark:border-amber-800 rounded-md px-3 py-1.5 flex-shrink-0">
              ⚠ 内容已填写但未锁定，切换左侧导航前建议先锁定
            </div>
          )}

          {isContentEmpty && !isLocked && (
            <div className="text-xs text-red-500 bg-red-50 dark:bg-red-900/10 border border-red-200 dark:border-red-800 rounded-md px-3 py-1.5 flex-shrink-0">
              ⚠ 内容尚未填写
            </div>
          )}

          {proposals && proposals.key === activeKey && (
            <Card size="small" title="AI 生成方案（点击选择）" className="border-primary-200 dark:border-primary-800 flex-shrink-0">
              <div className="space-y-2 max-h-[240px] overflow-auto">
                {proposals.items.map((p, i) => (
                  <div
                    key={`proposal-${i}`}
                    onClick={() => selectProposal(p)}
                    className="flex items-start gap-2 p-3 rounded-md border border-gray-200 dark:border-slate-600 hover:border-primary-400 cursor-pointer hover:bg-primary-50 dark:hover:bg-primary-900/10 transition-all"
                  >
                    <Tag color="blue" className="shrink-0 mt-0.5">方案 {i + 1}</Tag>
                    <p className="text-sm m-0 text-gray-700 dark:text-gray-300 whitespace-pre-line">{p}</p>
                  </div>
                ))}
              </div>
            </Card>
          )}

          <div className="flex-1 min-h-0">
            <TextArea
              value={content[activeKey] || ''}
              onChange={e => handleChange(e.target.value)}
              onBlur={handleBlur}
              placeholder={`请输入${activeConfig.label}的详细设定...`}
              disabled={isLocked}
              className={`
                h-full text-[15px] leading-relaxed resize-none
                ${isLocked ? 'bg-gray-100 dark:bg-slate-800 text-gray-500 dark:text-gray-500 cursor-not-allowed' : ''}
                ${isContentEmpty ? 'border-red-300 dark:border-red-700' : ''}
              `}
              style={{ height: '100%', lineHeight: 1.8 }}
            />
          </div>
        </div>
      </div>

      <ConfirmDialog
        open={confirmOpen !== null}
        title={confirmOpen?.type === 'lock' ? '确认锁定' : '确认解锁'}
        content={
          confirmOpen?.type === 'lock'
            ? '锁定后该配置项将无法编辑。确认锁定？'
            : '解锁后该配置项可以重新编辑。确认解锁？'
        }
        onOk={confirmLockToggle}
        onCancel={() => setConfirmOpen(null)}
      />
    </div>
  )
}
