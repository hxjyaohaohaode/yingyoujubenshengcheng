import { useState, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Card, Button, Tag, Input, App, Modal, Empty, Space, Row, Col,
  Collapse, Radio, Divider, Spin, Result,
} from 'antd'
import {
  AuditOutlined, CheckCircleOutlined, CloseCircleOutlined,
  ExclamationCircleOutlined, EditOutlined, RobotOutlined,
  UndoOutlined, EyeOutlined, WarningOutlined, ClockCircleOutlined,
  FileTextOutlined, ReloadOutlined, ExpandOutlined,
} from '@ant-design/icons'
import { useProjectStore } from '../stores/projectStore'
import { useAgentStore } from '../stores/agentStore'
import { api, scenesApi, type Scene } from '../api/client'

const { TextArea } = Input

interface AuditReport {
  id: string
  version: number
  overall_result: 'pass' | 'pass_with_warnings' | 'fail'
  checker_results: { name: string; pass: boolean; detail: string }[]
  llm_results: { name: string; score: number; detail: string }[]
  issues: string[]
  suggestions: string[]
  created_at: string
}

interface RejectionRecord {
  attempt: number
  reason: string
  suggestions: string[]
  created_at: string
}

interface ReviewScene {
  id: string
  scene_code: string
  scene_type: string
  title: string
  status: 'in_review' | 'needs_human' | 'rejected' | 'passed'
  version: number
  emotion_level: number
  narration_preview: string
  narration: string
  characters: string[]
  audit_summary: {
    checker_pass: number
    checker_total: number
    llm_avg_score: number
    top_issues: string[]
  }
  audit_reports: AuditReport[]
  rejection_history: RejectionRecord[]
  human_feedback: string
}

const SCENE_TYPE_LABELS: Record<string, string> = {
  dialogue: '对白', action: '动作', exploration: '探索', puzzle: '解谜', cutscene: '过场', branch: '分支',
}

const STATUS_CONFIG: Record<string, { label: string; color: string; icon: React.ReactNode }> = {
  in_review: { label: '审核中', color: '#3b82f6', icon: <ClockCircleOutlined /> },
  needs_human: { label: '需人工', color: '#f59e0b', icon: <ExclamationCircleOutlined /> },
  rejected: { label: '已封驳', color: '#ef4444', icon: <CloseCircleOutlined /> },
  passed: { label: '已通过', color: '#10b981', icon: <CheckCircleOutlined /> },
}

function mapApiStatus(status: string): ReviewScene['status'] {
  switch (status) {
    case 'in_review': return 'in_review'
    case 'auditing': return 'in_review'
    case 'rejected': return 'rejected'
    case 'needs_human': return 'needs_human'
    case 'final': return 'passed'
    case 'finalized':
    case 'passed': return 'passed'
    default: return 'in_review'
  }
}

function parseAuditReports(raw: unknown[]): AuditReport[] {
  if (!Array.isArray(raw)) return []
  return raw as AuditReport[]
}

function deriveRejectionHistory(auditReports: AuditReport[]): RejectionRecord[] {
  return auditReports
    .filter(r => r.overall_result === 'fail')
    .map((r, idx) => ({
      attempt: idx + 1,
      reason: r.issues.length > 0 ? r.issues.join('；') : '审核未通过',
      suggestions: r.suggestions || [],
      created_at: r.created_at,
    }))
}

function transformScene(scene: Scene): ReviewScene {
  const auditReports = parseAuditReports(scene.audit_reports)
  const rejectionHistory = deriveRejectionHistory(auditReports)
  const latestAudit = auditReports[auditReports.length - 1]

  const auditSummary = latestAudit
    ? {
        checker_pass: latestAudit.checker_results.filter(c => c.pass).length,
        checker_total: latestAudit.checker_results.length,
        llm_avg_score:
          latestAudit.llm_results.length > 0
            ? Math.round(latestAudit.llm_results.reduce((s, l) => s + l.score, 0) / latestAudit.llm_results.length)
            : 0,
        top_issues: latestAudit.issues.slice(0, 3),
      }
    : { checker_pass: 0, checker_total: 0, llm_avg_score: 0, top_issues: [] }

  const isEscalated = rejectionHistory.length >= 3
  const displayStatus = isEscalated ? 'needs_human' : mapApiStatus(scene.status)

  return {
    id: scene.id,
    scene_code: scene.scene_code,
    scene_type: scene.scene_type || 'dialogue',
    title: scene.scene_code,
    status: displayStatus,
    version: scene.version,
    emotion_level: scene.emotion_level,
    narration_preview: (scene.narration || '').slice(0, 200),
    narration: scene.narration || '',
    characters: (scene.characters_involved || []) as string[],
    audit_summary: auditSummary,
    audit_reports: auditReports,
    rejection_history: rejectionHistory,
    human_feedback: scene.human_feedback || '',
  }
}

export default function ReviewPanel() {
  const navigate = useNavigate()
  const { notification } = App.useApp()
  const { currentProject } = useProjectStore()
  const { updateAgent } = useAgentStore()

  const [scenes, setScenes] = useState<ReviewScene[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [selectedSceneId, setSelectedSceneId] = useState<string | null>(null)
  const [decision, setDecision] = useState<string>('accept')
  const [editSuggestions, setEditSuggestions] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [isRegenerating, setIsRegenerating] = useState(false)
  const [showFullContent, setShowFullContent] = useState(false)

  const projectId = currentProject?.id

  const fetchScenes = useCallback(async () => {
    if (!projectId) {
      setLoading(false)
      return
    }
    setLoading(true)
    setError(null)
    try {
      const data = await scenesApi.list(projectId)
      const transformed = data.map(transformScene).filter(
        s => s.status === 'in_review' || s.status === 'needs_human' || s.status === 'rejected'
      )
      setScenes(transformed)
      setSelectedSceneId(prev => {
        if (transformed.length === 0) return null
        if (prev && transformed.some(s => s.id === prev)) return prev
        return transformed[0].id
      })
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : '获取审核列表失败'
      setError(message)
      notification.error({
        message: '获取审核列表失败',
        description: message,
        placement: 'topRight',
      })
    } finally {
      setLoading(false)
    }
  }, [projectId])

  useEffect(() => {
    fetchScenes()
  }, [fetchScenes])

  const selectedScene = scenes.find(s => s.id === selectedSceneId) || null

  const stats = {
    pending: scenes.filter(s => s.status === 'in_review').length,
    needsHuman: scenes.filter(s => s.status === 'needs_human').length,
    rejected: scenes.filter(s => s.status === 'rejected').length,
    passed: 0,
    total: scenes.length,
  }
  const canFinalizeCurrentScene = selectedScene?.status === 'passed'

  const handleSubmitDecision = async () => {
    if (!selectedScene || !projectId) return
    setIsSubmitting(true)
    updateAgent('审计Agent', { status: 'busy', currentTask: '处理审核决定' })

    try {
      switch (decision) {
        case 'accept':
          await api.put(`/projects/${projectId}/scenes/${selectedScene.id}`, {
            status: 'approved',
            human_reviewed: true,
            human_feedback: editSuggestions || selectedScene.human_feedback || '人工审核通过，接受当前版本',
          })
          await api.post(`/projects/${projectId}/scenes/${selectedScene.id}/finalize`)
          notification.success({
            message: '已接受当前版本',
            description: `${selectedScene.scene_code} 已定稿`,
            placement: 'topRight',
          })
          break
        case 'revise':
          await api.put(`/projects/${projectId}/scenes/${selectedScene.id}`, {
            status: 'rejected',
            human_reviewed: true,
            human_feedback: editSuggestions || '请按照审计建议修改',
          })
          notification.success({
            message: '修改建议已提交',
            description: `${selectedScene.scene_code} 已标记为待修改，请前往场景工作台或重新生成`,
            placement: 'topRight',
          })
          break
        case 'manual':
          navigate('/scenes')
          notification.info({
            message: '已跳转至场景工作台',
            description: `正在打开场景 ${selectedScene.scene_code}`,
            placement: 'topRight',
          })
          break
        case 'regenerate':
          await api.post(`/ai/projects/${currentProject?.id}/scenes/${selectedScene.id}/generate`, { requirements: '' })
          notification.success({
            message: '已加入生成队列',
            description: `${selectedScene.scene_code} 正在重新生成`,
            placement: 'topRight',
          })
          break
      }
      setEditSuggestions('')
      await fetchScenes()
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : '请稍后重试'
      notification.error({
        message: '操作失败',
        description: message,
        placement: 'topRight',
      })
    } finally {
      updateAgent('审计Agent', { status: 'idle', currentTask: undefined })
      setIsSubmitting(false)
    }
  }

  const handleRegenerate = async () => {
    if (!selectedScene) return
    setIsRegenerating(true)
    updateAgent('创作Agent', { status: 'busy', currentTask: '重新生成场景' })

    try {
      await api.post(`/ai/projects/${currentProject?.id}/scenes/${selectedScene.id}/generate`, { requirements: '' })
      notification.success({ message: '场景已加入生成队列', placement: 'topRight' })
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : '重新生成失败'
      notification.error({ message: '重新生成失败', description: message, placement: 'topRight' })
    } finally {
      updateAgent('创作Agent', { status: 'idle', currentTask: undefined })
      setIsRegenerating(false)
    }
  }

  if (!currentProject) {
    return (
      <div>
        <h1 className="text-2xl font-bold mb-6">审核面板</h1>
        <Card className="text-center py-12">
          <Empty description="请先创建或选择一个项目" />
        </Card>
      </div>
    )
  }

  if (error) {
    return (
      <div style={{ fontFamily: 'var(--font-family)' }}>
        <h2 className="section-title" style={{ fontSize: 24 }}>多人推演</h2>
        <Result
          status="error"
          title="加载审核数据失败"
          subTitle={error}
          extra={[
            <Button key="retry" type="primary" onClick={fetchScenes}>重试</Button>,
            <Button key="refresh" onClick={() => window.location.reload()}>刷新页面</Button>,
          ]}
        />
      </div>
    )
  }

  if (loading) {
    return (
      <div style={{ fontFamily: 'var(--font-family)' }}>
        <h2 className="section-title" style={{ fontSize: 24 }}>多人推演</h2>
        <div className="card-surface" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: 200 }}>
          <Spin size="large"><div style={{ padding: '48px 0', color: 'var(--color-muted)' }}>正在加载审核列表...</div></Spin>
        </div>
      </div>
    )
  }

  if (scenes.length === 0) {
    return (
      <div style={{ fontFamily: 'var(--font-family)' }}>
        <h2 className="section-title" style={{ fontSize: 24 }}>多人推演</h2>
        <div className="card-surface" style={{ textAlign: 'center', padding: 48 }}>
          <Empty
            description={
              <span className="text-muted">
                所有场景已审核完毕，暂无待审核内容 🎉
                <br />
                <span className="text-xs">项目的每一个场景都经过了严格把关，这是创作质量的重要保障</span>
              </span>
            }
          >
            <Space>
              <Button type="primary" icon={<EditOutlined />} onClick={() => navigate('/scenes')}>
                前往场景工作台
              </Button>
              <Button icon={<ReloadOutlined />} onClick={fetchScenes}>刷新</Button>
            </Space>
          </Empty>
        </div>
      </div>
    )
  }

  return (
    <div style={{ fontFamily: 'var(--font-family)', display: 'flex', flexDirection: 'column', height: 'calc(100vh - 80px)' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 24, flexShrink: 0 }}>
        <div>
          <h2 className="section-title" style={{ fontSize: 24 }}>多人推演</h2>
        </div>
        <Button size="small" icon={<ReloadOutlined />} onClick={fetchScenes} loading={loading}>
          刷新列表
        </Button>
      </div>

      <Row gutter={8} className="mb-2 shrink-0">
        <Col span={6}>
          <Card size="small" className="text-center">
            <div className="text-2xl font-bold text-blue-500">{stats.pending}</div>
            <div className="text-xs text-gray-400">待审核</div>
          </Card>
        </Col>
        <Col span={6}>
          <Card size="small" className="text-center">
            <div className="text-2xl font-bold text-yellow-500">{stats.needsHuman}</div>
            <div className="text-xs text-gray-400">需人工</div>
          </Card>
        </Col>
        <Col span={6}>
          <Card size="small" className="text-center">
            <div className="text-2xl font-bold text-red-500">{stats.rejected}</div>
            <div className="text-xs text-gray-400">已封驳</div>
          </Card>
        </Col>
        <Col span={6}>
          <Card size="small" className="text-center">
            <div className="text-2xl font-bold text-green-500">{stats.passed}</div>
            <div className="text-xs text-gray-400">已通过</div>
          </Card>
        </Col>
      </Row>

      <div className="flex gap-2 flex-1 min-h-0">
        <div className="w-[300px] shrink-0 overflow-auto flex flex-col gap-1">
          <div className="text-xs text-gray-400 font-semibold px-1">
            待审核场景 ({scenes.length})
          </div>
          {scenes.map(sc => {
            const scCfg = STATUS_CONFIG[sc.status]
            return (
              <div
                key={sc.id}
                onClick={() => setSelectedSceneId(sc.id)}
                className={`p-2 rounded cursor-pointer border transition-all text-xs ${
                  selectedSceneId === sc.id
                    ? 'border-blue-300 dark:border-blue-700 bg-blue-50 dark:bg-blue-900/10'
                    : 'border-gray-200 dark:border-slate-600 hover:border-gray-300 dark:hover:border-slate-500'
                }`}
              >
                <div className="flex items-center gap-1.5 mb-1">
                  <span className="text-[10px] font-mono text-gray-400">{sc.scene_code}</span>
                  <Tag className="text-[10px] leading-tight m-0">
                    {SCENE_TYPE_LABELS[sc.scene_type] || sc.scene_type}
                  </Tag>
                  <Tag color={scCfg.color} className="text-[10px] leading-tight m-0 ml-auto">
                    <span className="flex items-center gap-0.5">{scCfg.icon}{scCfg.label}</span>
                  </Tag>
                </div>
                <div className="font-semibold text-xs mb-0.5">{sc.title}</div>
                <div className="text-[10px] text-gray-400 mb-1 line-clamp-2">
                  {sc.narration_preview}
                </div>
                <div className="flex items-center gap-2 text-[10px]">
                  <span className="text-green-500">
                    {sc.audit_summary.checker_pass}/{sc.audit_summary.checker_total}检测通过
                  </span>
                  <span className="text-purple-500">LLM均分{sc.audit_summary.llm_avg_score}</span>
                </div>
                {sc.rejection_history.length > 0 && (
                  <div className="mt-1 text-[10px] text-red-400">
                    封驳{sc.rejection_history.length}次 · 最近:{' '}
                    {sc.rejection_history[sc.rejection_history.length - 1].reason.slice(0, 20)}...
                  </div>
                )}
                {sc.status === 'needs_human' && (
                  <div className="mt-1">
                    <Tag color="red" className="text-[10px]">⚠ 需人类介入</Tag>
                  </div>
                )}
              </div>
            )
          })}
        </div>

        <div className="flex-1 flex flex-col gap-2 overflow-auto">
          {!selectedScene ? (
            <Card className="flex-1 flex items-center justify-center">
              <Empty description="选择左侧场景开始审核" />
            </Card>
          ) : (
            <>
              <Card
                size="small"
                title={
                  <div className="flex items-center gap-2 text-sm">
                    <FileTextOutlined />
                    <span>{selectedScene.scene_code}</span>
                    <Tag>{SCENE_TYPE_LABELS[selectedScene.scene_type]}</Tag>
                    <span className="text-gray-400">{selectedScene.title}</span>
                  </div>
                }
                extra={
                  <Space size="small">
                    <Button
                      size="small"
                      icon={<ExpandOutlined />}
                      onClick={() => setShowFullContent(true)}
                    >
                      查看全文
                    </Button>
                    <Button
                      size="small"
                      icon={<EyeOutlined />}
                      onClick={() => navigate('/scenes')}
                    >
                      打开编辑器
                    </Button>
                  </Space>
                }
              >
                <div className="text-xs text-gray-600 dark:text-gray-300 whitespace-pre-wrap leading-relaxed bg-gray-50 dark:bg-slate-800 p-2 rounded">
                  {selectedScene.narration_preview}
                  {selectedScene.narration.length > 200 && (
                    <span
                      className="text-blue-500 ml-1 cursor-pointer hover:underline"
                      onClick={() => setShowFullContent(true)}
                    >
                      ... 点击展开全文
                    </span>
                  )}
                </div>
                <div className="flex items-center gap-1 mt-2 text-xs text-gray-400">
                  <span>角色:</span>
                  {selectedScene.characters.map(c => (
                    <Tag key={c} className="text-[10px]">{c}</Tag>
                  ))}
                  <span className="ml-2">
                    情感:{' '}
                    <span className="font-semibold text-purple-500">
                      {selectedScene.emotion_level}/10
                    </span>
                  </span>
                  <span className="ml-2">版本: v{selectedScene.version}</span>
                </div>
              </Card>

              {selectedScene.audit_reports.length > 0 && selectedScene.audit_reports[0] && (
                <Collapse
                  size="small"
                  defaultActiveKey={['audit']}
                  items={[
                    {
                      key: 'audit',
                      label: (
                        <div className="flex items-center gap-2 text-sm">
                          <AuditOutlined />
                          <span>审计报告</span>
                          <Tag
                            color={
                              selectedScene.audit_reports[0].overall_result === 'pass'
                                ? 'green'
                                : 'red'
                            }
                          >
                            {selectedScene.audit_reports[0].overall_result === 'pass'
                              ? '通过'
                              : '封驳'}
                          </Tag>
                        </div>
                      ),
                      children: (
                        <div className="space-y-2">
                          <div>
                            <div className="text-xs text-gray-400 font-semibold mb-1">
                              程序化检测
                            </div>
                            <div className="grid grid-cols-2 gap-1">
                              {(selectedScene.audit_reports[0].checker_results || []).map((c, i) => (
                                <div
                                  key={i}
                                  className={`flex items-center gap-1 text-xs p-1 rounded ${
                                    c.pass
                                      ? 'bg-green-50 dark:bg-green-900/10'
                                      : 'bg-red-50 dark:bg-red-900/10'
                                  }`}
                                >
                                  {c.pass ? (
                                    <CheckCircleOutlined className="text-green-500" />
                                  ) : (
                                    <CloseCircleOutlined className="text-red-500" />
                                  )}
                                  <span>{c.name}: {c.detail}</span>
                                </div>
                              ))}
                            </div>
                          </div>
                          <div>
                            <div className="text-xs text-gray-400 font-semibold mb-1">
                              LLM审计评分
                            </div>
                            <Row gutter={4}>
                              {(selectedScene.audit_reports[0].llm_results || []).map((l, i) => (
                                <Col span={8} key={i}>
                                  <div className="bg-gray-50 dark:bg-slate-800 rounded p-1.5 text-center">
                                    <div className="text-xs text-gray-500">{l.name}</div>
                                    <div
                                      className={`text-lg font-bold ${
                                        l.score >= 80
                                          ? 'text-green-600'
                                          : l.score >= 60
                                            ? 'text-yellow-600'
                                            : 'text-red-600'
                                      }`}
                                    >
                                      {l.score}
                                    </div>
                                    <div className="text-[10px] text-gray-400">{l.detail}</div>
                                  </div>
                                </Col>
                              ))}
                            </Row>
                          </div>
                          {(selectedScene.audit_reports[0].issues || []).length > 0 && (
                            <div className="bg-red-50 dark:bg-red-900/10 border border-red-200 dark:border-red-800 rounded p-2">
                              <div className="text-xs text-red-600 font-semibold mb-1">问题:</div>
                              {(selectedScene.audit_reports[0].issues || []).map((issue, i) => (
                                <div key={i} className="text-xs text-red-500">· {issue}</div>
                              ))}
                            </div>
                          )}
                          {(selectedScene.audit_reports[0].suggestions || []).length > 0 && (
                            <div>
                              <div className="text-xs text-gray-400 font-semibold mb-1">建议:</div>
                              {(selectedScene.audit_reports[0].suggestions || []).map((s, i) => (
                                <div key={i} className="text-xs text-gray-600 dark:text-gray-400">
                                  · {s}
                                </div>
                              ))}
                            </div>
                          )}
                        </div>
                      ),
                    },
                  ]}
                />
              )}

              {selectedScene.audit_reports.length === 0 &&
                selectedScene.rejection_history.length === 0 && (
                  <Card size="small" className="text-center py-4">
                    <div className="text-xs text-gray-400">
                      <AuditOutlined className="mr-1" />
                      该场景尚未进行审计，请先在场景工作台提交审计
                    </div>
                  </Card>
                )}

              {selectedScene.rejection_history.length > 0 && (
                <Collapse
                  size="small"
                  defaultActiveKey={
                    selectedScene.rejection_history.length >= 3 ? ['rejections'] : []
                  }
                  items={[
                    {
                      key: 'rejections',
                      label: (
                        <div className="flex items-center gap-2 text-sm">
                          <WarningOutlined className="text-red-500" />
                          <span>
                            封驳历史 ({selectedScene.rejection_history.length}次)
                          </span>
                          {selectedScene.rejection_history.length >= 3 && (
                            <Tag color="red">需人类介入</Tag>
                          )}
                        </div>
                      ),
                      children: (
                        <div className="space-y-2">
                          {selectedScene.rejection_history.map((r, i) => (
                            <div
                              key={i}
                              className="border-l-2 border-red-300 dark:border-red-700 pl-2"
                            >
                              <div className="flex items-center gap-2 text-xs mb-0.5">
                                <Tag color="red" className="text-[10px]">
                                  第{r.attempt}次
                                </Tag>
                                <span className="text-gray-400">
                                  {new Date(r.created_at).toLocaleDateString()}
                                </span>
                              </div>
                              <div className="text-xs text-red-600 font-semibold mb-0.5">
                                {r.reason}
                              </div>
                              {r.suggestions.length > 0 && (
                                <div className="text-xs text-gray-500">
                                  {r.suggestions.map((s, j) => (
                                    <div key={j}>· {s}</div>
                                  ))}
                                </div>
                              )}
                            </div>
                          ))}
                          {selectedScene.rejection_history.length >= 3 && (
                            <div className="bg-red-50 dark:bg-red-900/10 border border-red-200 dark:border-red-800 rounded p-2 mt-2">
                              <div className="text-xs text-red-600 font-semibold mb-1">
                                ⚠ 该场景已被连续封驳
                                {selectedScene.rejection_history.length}次
                              </div>
                              <div className="text-xs text-red-500">
                                建议进行人工深度修改或重新构思场景结构。AI自动修改可能已不足以解决现存问题。
                              </div>
                            </div>
                          )}
                        </div>
                      ),
                    },
                  ]}
                />
              )}

              <Card
                size="small"
                title={<span className="text-sm font-semibold">审核决策</span>}
                className="shrink-0"
              >
                <Radio.Group
                  value={decision}
                  onChange={e => setDecision(e.target.value)}
                  className="w-full"
                >
                  <div className="space-y-2">
                    <div className="flex items-center gap-2">
                      <Radio value="accept">
                        <span className="text-sm">接受当前版本</span>
                      </Radio>
                      <Tag color="green" className="text-[10px]">审核通过后定稿</Tag>
                    </div>
                    <div className="ml-6 text-[11px] text-gray-400">
                      当前操作会先标记为人工审核通过，再执行定稿。
                    </div>
                    <div className="flex items-center gap-2">
                      <Radio value="revise">
                        <span className="text-sm">按审计建议修改</span>
                      </Radio>
                      <Tag color="blue" className="text-[10px]">可指定修改方向</Tag>
                    </div>
                    {decision === 'revise' && (
                      <TextArea
                        size="small"
                        className="ml-6"
                        rows={2}
                        value={editSuggestions}
                        onChange={e => setEditSuggestions(e.target.value)}
                        placeholder="输入修改建议或指定修改方向（可选）..."
                      />
                    )}
                    <div className="flex items-center gap-2">
                      <Radio value="manual">
                        <span className="text-sm">人工修改</span>
                      </Radio>
                      <Tag color="orange" className="text-[10px]">打开场景编辑器</Tag>
                    </div>
                    <div className="flex items-center gap-2">
                      <Radio value="regenerate">
                        <span className="text-sm">重新生成</span>
                      </Radio>
                      <Tag color="purple" className="text-[10px]">AI全新创作</Tag>
                    </div>
                  </div>
                </Radio.Group>
                <Divider className="my-2" />
                <div className="flex items-center gap-2">
                  <Button
                    type="primary"
                    icon={<CheckCircleOutlined />}
                    loading={isSubmitting}
                    onClick={handleSubmitDecision}
                    size="small"
                    disabled={decision === 'accept' && !selectedScene}
                  >
                    提交决定
                  </Button>
                  {decision === 'regenerate' && (
                    <Button
                      icon={<RobotOutlined />}
                      loading={isRegenerating}
                      onClick={handleRegenerate}
                      size="small"
                      danger
                    >
                      立即重新生成
                    </Button>
                  )}
                  {decision === 'manual' && (
                    <Button
                      icon={<EditOutlined />}
                      onClick={() => navigate('/scenes')}
                      size="small"
                    >
                      打开场景工作台
                    </Button>
                  )}
                  <Button
                    icon={<UndoOutlined />}
                    size="small"
                    onClick={() => {
                      setDecision('accept')
                      setEditSuggestions('')
                    }}
                  >
                    重置
                  </Button>
                </div>
              </Card>
            </>
          )}
        </div>
      </div>

      <Modal
        title={
          <div className="flex items-center gap-2">
            <FileTextOutlined />
            <span>{selectedScene?.scene_code}</span>
            <Tag>
              {selectedScene ? SCENE_TYPE_LABELS[selectedScene.scene_type] : ''}
            </Tag>
          </div>
        }
        open={showFullContent}
        onCancel={() => setShowFullContent(false)}
        footer={null}
        width={720}
        styles={{ body: { maxHeight: '70vh', overflow: 'auto' } }}
      >
        <div className="whitespace-pre-wrap leading-relaxed text-sm text-gray-700 dark:text-gray-300 bg-gray-50 dark:bg-slate-800 p-4 rounded">
          {selectedScene?.narration || '暂无内容'}
        </div>
        {selectedScene && selectedScene.characters.length > 0 && (
          <div className="mt-3 flex items-center gap-2 text-xs text-gray-400 flex-wrap">
            <span>出场角色:</span>
            {selectedScene.characters.map(c => (
              <Tag key={c} className="text-[10px]">{c}</Tag>
            ))}
            <span className="ml-2">情感强度: {selectedScene.emotion_level}/10</span>
            <span className="ml-2">版本: v{selectedScene.version}</span>
          </div>
        )}
      </Modal>
    </div>
  )
}
