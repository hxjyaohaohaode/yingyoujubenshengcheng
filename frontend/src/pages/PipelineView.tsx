import { useState, useEffect, useCallback, useRef } from 'react'
import { Card, Button, Tag, App, Progress, Spin, Empty, Checkbox, Input, Popconfirm, Select } from 'antd'
import {
  PlayCircleOutlined, CheckCircleOutlined, CloseCircleOutlined,
  SyncOutlined, ThunderboltOutlined, ReloadOutlined, StepBackwardOutlined,
} from '@ant-design/icons'
import { api, pipelineApi } from '../api/client'
import { useProjectStore } from '../stores/projectStore'
import { useAITaskStore } from '../stores/aiTaskStore'
import { eventBus, DataEvents } from '../services/eventBus'

interface PipelineStatus {
  status: string
  current_phase: number
  current_step: number
  template: string
  error_message: string
  task_results: Array<{
    key: string
    phase: string
    agent: string
    skill: string
    status: string
    completed_at: string
  }>
}

interface TemplateInfo {
  name: string
  description: string
  phases: Array<{
    name: string
    human_gate: boolean
    steps: Array<{ agent: string; skill: string }>
  }>
}

const STATUS_CONFIG: Record<string, { label: string; color: string; icon: React.ReactNode }> = {
  not_started: { label: '未开始', color: '#6b7280', icon: <PlayCircleOutlined /> },
  not_initialized: { label: '未初始化', color: '#9ca3af', icon: <PlayCircleOutlined /> },
  running: { label: '运行中', color: '#3b82f6', icon: <SyncOutlined spin /> },
  waiting_human: { label: '等待审核', color: '#f59e0b', icon: <PlayCircleOutlined /> },
  completed: { label: '已完成', color: '#10b981', icon: <CheckCircleOutlined /> },
  failed: { label: '失败', color: '#ef4444', icon: <CloseCircleOutlined /> },
  cancelled: { label: '已取消', color: '#6b7280', icon: <CloseCircleOutlined /> },
}

const STEP_STATUS: Record<string, { label: string; color: string }> = {
  completed: { label: '完成', color: '#10b981' },
  failed: { label: '失败', color: '#ef4444' },
  running: { label: '运行中', color: '#3b82f6' },
  rejected: { label: '已驳回', color: '#f59e0b' },
  pending: { label: '等待中', color: '#6b7280' },
}

export default function PipelineView() {
  const { notification } = App.useApp()
  const { currentProject } = useProjectStore()
  const { pipeline: storePipeline, isPipelineRunning, setPipeline: setStorePipeline, setPipelineRunning: setStorePipelineRunning } = useAITaskStore()
  const projectId = currentProject?.id || ''
  const [status, setStatus] = useState<PipelineStatus | null>(null)
  const [template, setTemplate] = useState<TemplateInfo | null>(null)
  const [loading, setLoading] = useState(false)
  const [advancing, setAdvancing] = useState(false)
  const [error, setError] = useState('')
  const [rejectReason, setRejectReason] = useState('')
  const [autoAdvance, setAutoAdvance] = useState(false)
  const [approving, setApproving] = useState(false)
  const [rejecting, setRejecting] = useState(false)
  const [retrying, setRetrying] = useState(false)
  const [rollingBack, setRollingBack] = useState(false)
  const [rollbackPhase, setRollbackPhase] = useState<number>(0)
  const [rollbackStep, setRollbackStep] = useState<number>(0)
  const advancingRef = useRef(false)
  const mountedRef = useRef(true)
  const fetchingRef = useRef(false)
  const abortRef = useRef<AbortController | null>(null)
  const [backendDown, setBackendDown] = useState(false)

  const backendDownRef = useRef(false)

  const fetchStatus = useCallback(async (signal?: AbortSignal) => {
    if (!projectId || fetchingRef.current) return
    fetchingRef.current = true
    try {
      const data = await api.get<PipelineStatus>(`/projects/${projectId}/pipeline/status`, signal)
      if (!mountedRef.current || signal?.aborted) return
      setStatus(data)
      setError('')
      if (backendDownRef.current) {
        backendDownRef.current = false
        setBackendDown(false)
      }

      const isRunning = data.status === 'running'
      const isFailed = data.status === 'failed'
      const isCompleted = data.status === 'completed'
      const isCancelled = data.status === 'cancelled'
      const isWaiting = data.status === 'waiting_human'

      if (isRunning || isFailed || isCompleted || isCancelled || isWaiting) {
        setStorePipelineRunning(isRunning)
        if (data.template && (!storePipeline || storePipeline.phases.length === 0)) {
          try {
            const tpl = await pipelineApi.getTemplate(data.template)
            if (!mountedRef.current || signal?.aborted) return
            setTemplate(tpl)
            const phases = (tpl.phases || []).map((p, i) => ({
              name: p.name,
              steps: p.steps.length,
              humanGate: p.human_gate,
              currentStep: i < data.current_phase ? p.steps.length : i === data.current_phase ? data.current_step : 0,
              status: i < data.current_phase ? 'completed' as const : i === data.current_phase ? 'running' as const : 'pending' as const,
            }))
            const completedCount = (data.task_results || []).filter(r => r.status === 'completed').length
            const totalSteps = phases.reduce((sum, p) => sum + p.steps, 0) || 1
            const overallProgress = isCompleted ? 100 : Math.round((completedCount / totalSteps) * 100)
            setStorePipeline({
              status: isRunning ? 'running' : isFailed ? 'failed' : isCancelled ? 'cancelled' : isWaiting ? 'waiting_human' : 'completed',
              currentPhase: phases[data.current_phase]?.name || '',
              currentPhaseIndex: data.current_phase,
              totalPhases: phases.length,
              overallProgress,
              message: data.error_message || (isRunning ? '流水线运行中' : isCompleted ? '已完成' : isFailed ? '执行失败' : isCancelled ? '已取消' : '等待审核'),
              phases,
            })
          } catch {}
        }
      }

      if (data.template && !template) {
        try {
          const tpl = await pipelineApi.getTemplate(data.template)
          if (!mountedRef.current || signal?.aborted) return
          setTemplate(tpl)
        } catch (e: any) {
          if (e?.status === 0 || signal?.aborted) return
        }
      }
    } catch (e: any) {
      if (!mountedRef.current || e?.status === 0 || signal?.aborted) return
      if (e?.status === 0) {
        if (!backendDownRef.current) {
          backendDownRef.current = true
          setBackendDown(true)
        }
      } else {
        setError(e?.detail || e?.message || '获取状态失败')
      }
    } finally {
      fetchingRef.current = false
    }
  }, [projectId, storePipeline, template])

  useEffect(() => {
    mountedRef.current = true
    fetchStatus()
    const interval = setInterval(() => {
      if (mountedRef.current && !backendDownRef.current) {
        fetchStatus()
      }
    }, 3000)
    const onPipelineChange = () => {
      if (mountedRef.current && !fetchingRef.current) {
        fetchStatus()
      }
    }
    eventBus.on(DataEvents.PIPELINE_STATUS_CHANGED, onPipelineChange)
    return () => {
      mountedRef.current = false
      if (abortRef.current) {
        abortRef.current.abort()
        abortRef.current = null
      }
      clearInterval(interval)
      eventBus.off(DataEvents.PIPELINE_STATUS_CHANGED, onPipelineChange)
    }
  }, [fetchStatus])

  useEffect(() => {
    if (!autoAdvance || !status || advancingRef.current) return
    const isRunning = effectiveIsRunning
    if (isRunning) {
      const timer = setTimeout(() => handleAdvance(), 2000)
      return () => clearTimeout(timer)
    }
    if (effectiveIsWaitingHuman) {
      setAutoAdvance(false)
    }
  }, [autoAdvance, status?.status, storePipeline?.status])

  const handleAdvance = async () => {
    if (!projectId || advancingRef.current) return
    advancingRef.current = true
    setAdvancing(true)
    setError('')
    try {
      const result = await api.post<{ status: string; message?: string }>(
        `/projects/${projectId}/pipeline/advance`
      )
      await fetchStatus()
      if (result.status === 'waiting_human') {
        setAutoAdvance(false)
      }
      if (result.status === 'completed') {
        notification.success({ message: '流程执行完毕', description: '所有编排阶段已完成', placement: 'topRight' })
      }
    } catch (e: any) {
      setError(e?.detail || e?.message || '推进失败')
    } finally {
      setAdvancing(false)
      advancingRef.current = false
    }
  }

  const handleApprove = async () => {
    if (!projectId) return
    setApproving(true)
    try {
      await api.post(`/projects/${projectId}/pipeline/approve`)
      await fetchStatus()
      notification.success({ message: '已审核通过', placement: 'topRight' })
    } catch (e: any) {
      setError(e?.detail || e?.message || '审核失败')
    } finally {
      setApproving(false)
    }
  }

  const handleReject = async () => {
    if (!projectId) return
    setRejecting(true)
    try {
      await api.post(`/projects/${projectId}/pipeline/reject`, { reason: rejectReason })
      setRejectReason('')
      await fetchStatus()
      notification.info({ message: '已驳回，等待重新执行', placement: 'topRight' })
    } catch (e: any) {
      setError(e?.detail || e?.message || '驳回失败')
    } finally {
      setRejecting(false)
    }
  }

  const handleRetry = async () => {
    if (!projectId || retrying) return
    setRetrying(true)
    setError('')
    try {
      await pipelineApi.retry(projectId)
      notification.success({ message: '已重新开始', description: '从失败步骤继续执行', placement: 'topRight' })
      await fetchStatus()
      setTimeout(() => handleAdvance(), 500)
    } catch (e: any) {
      setError(e?.detail || e?.message || '重试失败')
    } finally {
      setRetrying(false)
    }
  }

  const handleRollback = async () => {
    if (!projectId || rollingBack) return
    setRollingBack(true)
    setError('')
    try {
      await pipelineApi.rollback(projectId, rollbackPhase, rollbackStep)
      notification.success({
        message: '已回退',
        description: `回退到阶段${rollbackPhase}步骤${rollbackStep}，请点击「推进下一步」重新执行`,
        placement: 'topRight',
      })
      await fetchStatus()
    } catch (e: any) {
      setError(e?.detail || e?.message || '回退失败')
    } finally {
      setRollingBack(false)
    }
  }

  const isDependencyError = status?.error_message?.includes('依赖的前置步骤尚未完成')
  const failedPhaseIdx = status?.current_phase ?? 0
  const failedStepIdx = status?.current_step ?? 0

  const effectiveStatus = storePipeline?.status || status?.status || 'not_started'
  const effectiveIsRunning = isPipelineRunning || effectiveStatus === 'running' || effectiveStatus === 'not_started' || effectiveStatus === 'not_initialized'
  const effectiveIsWaitingHuman = effectiveStatus === 'waiting_human'
  const effectiveIsCompleted = effectiveStatus === 'completed'
  const effectiveIsFailed = effectiveStatus === 'failed'
  const effectiveIsCancelled = effectiveStatus === 'cancelled'

  if (!projectId) {
    return (
      <div className="flex items-center justify-center py-20">
        <Empty description="请先选择一个项目" />
      </div>
    )
  }

  const statusInfo = STATUS_CONFIG[effectiveStatus] || { label: effectiveStatus, color: '#6b7280', icon: null }
  const phaseIdx = storePipeline?.currentPhaseIndex ?? status?.current_phase ?? 0
  const stepIdx = status?.current_step ?? 0
  const currentPhaseName = storePipeline?.currentPhase || template?.phases?.[phaseIdx >= 0 ? phaseIdx : 0]?.name || '-'
  const completedCount = status?.task_results?.filter(r => r.status === 'completed').length || 0
  const totalPhases = template?.phases?.length || 0
  const progressPct = storePipeline?.overallProgress ?? (totalPhases > 0 ? Math.round((phaseIdx / totalPhases) * 100) : 0)

  return (
    <div style={{ fontFamily: 'var(--font-family)' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 24 }}>
        <div>
          <h2 className="section-title" style={{ fontSize: 24 }}>素材提取</h2>
          <p className="text-muted" style={{ margin: '4px 0 0' }}>
            {currentProject?.name} · 流程编排与自动化创作
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Tag color={advancingRef.current ? 'processing' : 'default'} className="text-xs">
            {advancingRef.current ? '执行中' : '就绪'}
          </Tag>
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded-full" style={{ backgroundColor: statusInfo.color }} />
            <span className="font-semibold text-sm">{statusInfo.label}</span>
          </div>
          <Button size="small" icon={<ReloadOutlined />} onClick={() => { backendDownRef.current = false; setBackendDown(false); fetchStatus() }}>刷新</Button>
        </div>
      </div>

      {backendDown && (
        <div className="mb-4 p-4 bg-amber-50 dark:bg-amber-900/10 border border-amber-200 dark:border-amber-800 rounded-lg">
          <div className="flex items-center justify-between">
            <div>
              <p className="font-semibold text-amber-700 dark:text-amber-400">后端服务未连接</p>
              <p className="text-sm text-amber-600 dark:text-amber-500 mt-1">
                请启动后端服务: <code className="px-1 py-0.5 bg-amber-100 dark:bg-amber-900/30 rounded text-xs">cd script-engine/backend && python -m uvicorn main:app --port 8000 --reload</code>
              </p>
            </div>
            <Button size="small" icon={<ReloadOutlined />} onClick={() => { backendDownRef.current = false; setBackendDown(false); fetchStatus() }}>
              重试连接
            </Button>
          </div>
        </div>
      )}

      {error && !backendDown && (
        <div className="mb-4 p-3 bg-red-50 dark:bg-red-900/10 border border-red-200 dark:border-red-800 rounded-lg text-red-600 dark:text-red-400 text-sm">
          {error}
        </div>
      )}

      <div className="mb-4">
        <Progress
          percent={progressPct}
          status={effectiveIsCompleted ? 'success' : effectiveIsFailed ? 'exception' : effectiveIsCancelled ? 'normal' : 'active'}
          strokeColor={{
            '0%': '#3b82f6',
            '100%': '#10b981',
          }}
        />
      </div>

      <Card className="mb-4 shadow-sm border-gray-200 dark:border-slate-700 bg-white dark:bg-slate-800" size="small">
        <div className="grid grid-cols-3 gap-4 mb-4 text-center">
          <div>
            <div className="text-xs text-gray-500 dark:text-gray-400 mb-1">当前阶段</div>
            <div className="text-lg font-bold text-gray-800 dark:text-gray-100">{currentPhaseName}</div>
          </div>
          <div>
            <div className="text-xs text-gray-500 dark:text-gray-400 mb-1">当前步骤</div>
            <div className="text-lg font-bold text-gray-800 dark:text-gray-100">
              {status ? `${(phaseIdx >= 0 ? phaseIdx : 0) + 1}-${(stepIdx >= 0 ? stepIdx : 0) + 1}` : '-'}
            </div>
          </div>
          <div>
            <div className="text-xs text-gray-500 dark:text-gray-400 mb-1">已完成</div>
            <div className="text-lg font-bold text-green-600 dark:text-green-400">{completedCount}</div>
          </div>
        </div>

        <div className="flex items-center gap-3 flex-wrap">
          {!effectiveIsCompleted && !effectiveIsFailed && !effectiveIsCancelled && (
            <>
              <Button
                type="primary"
                icon={advancing ? <SyncOutlined spin /> : <PlayCircleOutlined />}
                onClick={handleAdvance}
                loading={advancing}
                disabled={effectiveIsWaitingHuman}
              >
                {effectiveIsWaitingHuman ? '等待审核中' : advancing ? '执行中...' : '推进下一步'}
              </Button>
              <Checkbox
                checked={autoAdvance}
                onChange={(e) => setAutoAdvance(e.target.checked)}
              >
                <span className="text-sm text-gray-600 dark:text-gray-400">自动推进</span>
              </Checkbox>
            </>
          )}
          {effectiveIsWaitingHuman && (
            <div className="flex items-center gap-3 flex-wrap">
              <Button
                type="primary"
                icon={<CheckCircleOutlined />}
                onClick={handleApprove}
                loading={approving}
                style={{ background: '#10b981', borderColor: '#10b981' }}
              >
                审核通过
              </Button>
              <Input
                placeholder="驳回原因..."
                value={rejectReason}
                onChange={(e) => setRejectReason(e.target.value)}
                style={{ width: 200 }}
                size="small"
              />
              <Button
                danger
                icon={<CloseCircleOutlined />}
                onClick={handleReject}
                loading={rejecting}
              >
                驳回
              </Button>
            </div>
          )}
          {effectiveIsFailed && (
            <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
              <Button
                icon={<ReloadOutlined />}
                onClick={handleRetry}
                loading={retrying}
                style={{ background: '#f59e0b', borderColor: '#f59e0b', color: '#fff' }}
              >
                {retrying ? '重试中...' : '重试当前步骤'}
              </Button>
              {isDependencyError && (
                <Popconfirm
                  title="回退到缺失的依赖步骤"
                  description={
                    <div style={{ maxWidth: 280 }}>
                      <p style={{ margin: '0 0 8px', color: '#ef4444', fontSize: 12 }}>
                        检测到依赖缺失，建议回退到该步骤之前的步骤重新执行
                      </p>
                      <div style={{ display: 'flex', gap: 8, marginBottom: 8 }}>
                        <Select
                          size="small"
                          value={rollbackPhase}
                          onChange={(v) => { setRollbackPhase(v); setRollbackStep(0) }}
                          style={{ width: 120 }}
                          options={template?.phases?.map((p, i) => ({ label: p.name, value: i })) || []}
                          placeholder="阶段"
                        />
                        <Select
                          size="small"
                          value={rollbackStep}
                          onChange={(v) => setRollbackStep(v)}
                          style={{ width: 80 }}
                          options={
                            template?.phases?.[rollbackPhase]?.steps?.map((_, i) => ({
                              label: `步骤${i}`,
                              value: i,
                            })) || []
                          }
                          placeholder="步骤"
                        />
                      </div>
                    </div>
                  }
                  onConfirm={handleRollback}
                  okText="确认回退"
                  cancelText="取消"
                >
                  <Button
                    icon={<StepBackwardOutlined />}
                    loading={rollingBack}
                    danger
                  >
                    回退修复
                  </Button>
                </Popconfirm>
              )}
              {!isDependencyError && (
                <Popconfirm
                  title="回退到指定步骤重新执行"
                  description={
                    <div style={{ maxWidth: 280 }}>
                      <div style={{ display: 'flex', gap: 8 }}>
                        <Select
                          size="small"
                          value={rollbackPhase}
                          onChange={(v) => { setRollbackPhase(v); setRollbackStep(0) }}
                          style={{ width: 120 }}
                          options={template?.phases?.map((p, i) => ({ label: p.name, value: i })) || []}
                          placeholder="阶段"
                        />
                        <Select
                          size="small"
                          value={rollbackStep}
                          onChange={(v) => setRollbackStep(v)}
                          style={{ width: 80 }}
                          options={
                            template?.phases?.[rollbackPhase]?.steps?.map((_, i) => ({
                              label: `步骤${i}`,
                              value: i,
                            })) || []
                          }
                          placeholder="步骤"
                        />
                      </div>
                      <p style={{ margin: '8px 0 0', fontSize: 11, color: '#6b7280' }}>
                        回退后该步骤及其后续步骤将重新执行
                      </p>
                    </div>
                  }
                  onConfirm={handleRollback}
                  okText="确认回退"
                  cancelText="取消"
                >
                  <Button
                    icon={<StepBackwardOutlined />}
                    loading={rollingBack}
                    danger
                  >
                    回退修复
                  </Button>
                </Popconfirm>
              )}
            </div>
          )}
          {effectiveIsCancelled && (
            <Button
              type="primary"
              icon={<PlayCircleOutlined />}
              onClick={handleAdvance}
              loading={advancing}
            >
              重新启动
            </Button>
          )}
        </div>

        {status?.error_message && (
          <div className="mt-3 p-2 bg-red-50 dark:bg-red-900/10 border border-red-200 dark:border-red-800 rounded text-red-600 dark:text-red-400 text-sm">
            {status.error_message}
          </div>
        )}
      </Card>

      {template && (
        <Card className="mb-4 shadow-sm border-gray-200 dark:border-slate-700 bg-white dark:bg-slate-800" size="small"
          title={<span className="font-semibold">编排阶段</span>}>
          <div className="flex rounded-lg overflow-hidden border border-gray-200 dark:border-slate-600">
            {template.phases.map((phase, idx) => {
              const isActive = idx === phaseIdx
              const isPast = idx < phaseIdx
              return (
                <div
                  key={phase.name}
                  className={`flex-1 p-3 text-center transition-colors ${
                    isActive ? 'bg-blue-500 text-white' :
                    isPast ? 'bg-green-500 text-white' :
                    'bg-gray-100 dark:bg-slate-700 text-gray-600 dark:text-gray-300'
                  }`}
                  style={{ borderRight: idx < template.phases.length - 1 ? '1px solid #e5e7eb' : 'none' }}
                >
                  <div className="text-sm font-semibold mb-1">
                    {phase.name}
                    {phase.human_gate && <span className="text-xs opacity-70"> 🔒</span>}
                  </div>
                  <div className="text-xs opacity-70">{phase.steps.length} 步骤</div>
                </div>
              )
            })}
          </div>
        </Card>
      )}

      <Card className="shadow-sm border-gray-200 dark:border-slate-700 bg-white dark:bg-slate-800" size="small"
        title={<span className="font-semibold">执行历史</span>}>
        {!status?.task_results?.length ? (
          <p className="text-center text-gray-400 dark:text-gray-500 py-8">暂无执行记录</p>
        ) : (
          <div className="flex flex-col gap-2 max-h-80 overflow-auto">
            {[...(status.task_results || [])].reverse().map((task, idx) => {
              const st = STEP_STATUS[task.status] || { label: task.status, color: '#6b7280' }
              return (
                <div
                  key={idx}
                  className="flex items-center p-3 rounded-lg bg-gray-50 dark:bg-slate-700/50 gap-3"
                >
                  <div className="w-2 h-2 rounded-full flex-shrink-0" style={{ backgroundColor: st.color }} />
                  <div className="flex-1 min-w-0">
                    <span className="font-semibold text-sm text-gray-800 dark:text-gray-200">
                      {task.phase} / {task.agent}.{task.skill}
                    </span>
                    <span className="text-xs text-gray-400 dark:text-gray-500 ml-2">
                      {task.completed_at ? new Date(task.completed_at).toLocaleTimeString() : '-'}
                    </span>
                  </div>
                  <Tag color={st.color} className="text-xs">{st.label}</Tag>
                </div>
              )
            })}
          </div>
        )}
      </Card>
    </div>
  )
}
