import { useState, useEffect, useRef } from 'react'
import { Progress, Tag, Button, Tooltip, Popover } from 'antd'
import { App } from 'antd'
import {
  PlayCircleOutlined, PauseCircleOutlined,
  ExperimentOutlined, RobotOutlined,
  LoadingOutlined, CheckCircleOutlined,
  CloseCircleOutlined, ExclamationCircleOutlined,
  SyncOutlined, RedoOutlined,
} from '@ant-design/icons'
import { useAITaskStore, AgentStatusType, PipelinePhase } from '../stores/aiTaskStore'
import { useProjectStore } from '../stores/projectStore'
import { api } from '../api/client'

const AGENT_LABELS: Record<string, string> = {
  creator: '创作', auditor: '审核', orchestrator: '编排',
  foreshadow: '伏笔', material: '素材', state_manager: '状态',
  '系统': '系统',
}

const STATUS_COLORS: Record<AgentStatusType, string> = {
  idle: '#10B981', busy: '#F59E0B', error: '#EF4444', offline: '#9CA3AF',
}

function AgentDot({ name, status, task }: { name: string; status: AgentStatusType; task: string }) {
  return (
    <Tooltip title={`${AGENT_LABELS[name] || name}${task ? ': ' + task : ' · ' + status}`}>
      <span style={{
        width: 8, height: 8, borderRadius: '50%', display: 'inline-block',
        background: STATUS_COLORS[status],
        boxShadow: status === 'busy' ? `0 0 6px ${STATUS_COLORS[status]}` : 'none',
        transition: 'all 0.3s',
      }} />
    </Tooltip>
  )
}

function AgentStatusBar() {
  const agents = useAITaskStore(s => s.agents)
  const displayAgents = agents.filter(a => a.name !== '系统')
  return (
    <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
      {displayAgents.map(a => (
        <AgentDot key={a.name} name={a.name} status={a.status} task={a.currentTask} />
      ))}
    </div>
  )
}

export default function PipelineProgressBar() {
  const { currentProject } = useProjectStore()
  const { pipeline, isPipelineRunning, activeTasks, setPipeline, setPipelineRunning } = useAITaskStore()
  const [starting, setStarting] = useState(false)
  const { notification } = App.useApp()
  const projectIdRef = useRef<string | null>(null)
  const abortRef = useRef<AbortController | null>(null)

  useEffect(() => {
    if (!currentProject?.id || projectIdRef.current === currentProject.id) return
    projectIdRef.current = currentProject.id

    abortRef.current?.abort()
    const ctrl = new AbortController()
    abortRef.current = ctrl

    const fetchInitialStatus = async () => {
      try {
        const data = await api.get<{
          status: string
          current_phase: number
          current_step: number
          template: string
          error_message: string
          task_results: Array<{ key: string; phase: string; agent: string; skill: string; status: string; completed_at: string }>
        }>(`/projects/${currentProject.id}/pipeline/status`, ctrl.signal)

        if (ctrl.signal.aborted) return
        if (!data || data.status === 'not_initialized') return

        const isRunning = data.status === 'running'
        const isFailed = data.status === 'failed'
        const isCompleted = data.status === 'completed'
        const isCancelled = data.status === 'cancelled'
        const isWaiting = data.status === 'waiting_human'

        if (isRunning || isFailed || isCompleted || isCancelled || isWaiting) {
          setPipelineRunning(isRunning)

          let phases: PipelinePhase[] = []
          if (data.template) {
            try {
              const tpl = await api.get<{
                name: string
                description: string
                phases: Array<{ name: string; human_gate: boolean; steps: Array<{ agent: string; skill: string }> }>
              }>(`/templates/${encodeURIComponent(data.template)}`, ctrl.signal)
              phases = (tpl.phases || []).map((p, i) => ({
                name: p.name,
                steps: p.steps.length,
                humanGate: p.human_gate,
                currentStep: i < data.current_phase ? p.steps.length : i === data.current_phase ? data.current_step : 0,
                status: i < data.current_phase ? 'completed' as const : i === data.current_phase ? 'running' as const : 'pending' as const,
              }))
            } catch {}
          }

          const completedCount = (data.task_results || []).filter(r => r.status === 'completed').length
          const totalSteps = phases.reduce((sum, p) => sum + p.steps, 0) || 1
          const overallProgress = isCompleted ? 100 : isFailed || isCancelled ? Math.round((completedCount / totalSteps) * 100) : Math.round((completedCount / totalSteps) * 100)

          setPipeline({
            status: isRunning ? 'running' : isFailed ? 'failed' : isCancelled ? 'cancelled' : isWaiting ? 'waiting_human' : 'completed',
            currentPhase: phases[data.current_phase]?.name || '',
            currentPhaseIndex: data.current_phase,
            totalPhases: phases.length,
            overallProgress,
            message: data.error_message || (isRunning ? '流水线运行中' : isCompleted ? '已完成' : isFailed ? '执行失败' : isCancelled ? '已取消' : '等待审核'),
            phases,
          })
        }
      } catch {}
    }

    fetchInitialStatus()
    return () => { ctrl.abort() }
  }, [currentProject?.id, setPipeline, setPipelineRunning])

  if (!currentProject) return null

  const runningTasks = activeTasks.filter(t => t.status === 'running')
  const latestTask = runningTasks[0]

  const barBg = pipeline?.status === 'completed' ? 'var(--color-success-soft)' :
    pipeline?.status === 'failed' ? 'var(--color-danger-soft)' :
    pipeline?.status === 'cancelled' ? 'var(--color-danger-soft)' :
    pipeline?.status === 'waiting_human' ? 'var(--color-warning-soft)' :
    isPipelineRunning ? 'var(--color-accent-soft)' : 'var(--color-surface2)'

  const showBar = pipeline || isPipelineRunning || runningTasks.length > 0

  return (
    <div style={{
      borderBottom: '1px solid var(--color-border)',
      background: showBar ? barBg : 'var(--color-surface2)',
      padding: showBar ? '6px 24px' : '6px 24px',
      transition: 'background 0.3s',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, height: 24 }}>
        {showBar ? (
          <>
            {pipeline && (
              <Popover
                content={
                  <div style={{ maxWidth: 320 }}>
                    <div style={{ fontWeight: 600, fontSize: 13, marginBottom: 10 }}>
                      {pipeline.status === 'running' && <SyncOutlined spin style={{ color: 'var(--color-accent)', marginRight: 6 }} />}
                      {pipeline.status === 'completed' && <CheckCircleOutlined style={{ color: 'var(--color-success)', marginRight: 6 }} />}
                      {pipeline.status === 'waiting_human' && <ExclamationCircleOutlined style={{ color: 'var(--color-warning)', marginRight: 6 }} />}
                      {pipeline.status === 'failed' && <CloseCircleOutlined style={{ color: 'var(--color-danger)', marginRight: 6 }} />}
                      {pipeline.status === 'cancelled' && <CloseCircleOutlined style={{ color: 'var(--color-danger)', marginRight: 6 }} />}
                      {pipeline.message || '流水线运行中'}
                    </div>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                      {pipeline.phases.map((phase, idx) => {
                        const isRunning = phase.status === 'running'
                        const isDone = phase.status === 'completed'
                        return (
                          <div key={phase.name} style={{
                            display: 'flex', alignItems: 'center', gap: 8,
                            padding: '6px 10px', borderRadius: 8,
                            background: isRunning ? 'var(--color-accent-soft)' :
                              isDone ? 'var(--color-success-soft)' : 'var(--color-surface2)',
                            opacity: phase.status === 'pending' ? 0.45 : 1,
                          }}>
                            <span style={{
                              width: 22, height: 22, borderRadius: '50%',
                              display: 'flex', alignItems: 'center', justifyContent: 'center',
                              fontSize: 11, fontWeight: 700, flexShrink: 0,
                              background: isDone ? 'var(--color-success)' :
                                isRunning ? 'var(--color-accent)' : 'var(--color-border)',
                              color: isDone || isRunning ? '#fff' : 'var(--color-muted)',
                            }}>
                              {isDone ? <CheckCircleOutlined /> :
                               isRunning ? <LoadingOutlined spin /> : idx + 1}
                            </span>
                            <div style={{ flex: 1, minWidth: 0 }}>
                              <div style={{ fontSize: 12, fontWeight: 500 }}>{phase.name}</div>
                              <div style={{ fontSize: 10, color: 'var(--color-muted)' }}>
                                {phase.currentStep}/{phase.steps} 步骤{phase.humanGate ? ' · 需人工确认' : ''}
                              </div>
                            </div>
                          </div>
                        )
                      })}
                    </div>
                  </div>
                }
                trigger="click"
              >
                <div style={{
                  display: 'flex', alignItems: 'center', gap: 6,
                  cursor: 'pointer', padding: '1px 10px', borderRadius: 6,
                  background: isPipelineRunning ? 'rgba(99,102,241,0.1)' : 'var(--color-surface)',
                  border: isPipelineRunning ? '1px solid rgba(99,102,241,0.2)' : '1px solid var(--color-border)',
                }}>
                  <ExperimentOutlined style={{ fontSize: 12, color: 'var(--color-accent)' }} />
                  <span style={{ fontSize: 12, fontWeight: 500 }}>
                    {pipeline.currentPhase || '流水线'}
                  </span>
                  <Tag
                    color={pipeline.status === 'running' ? 'processing' :
                           pipeline.status === 'completed' ? 'success' :
                           pipeline.status === 'waiting_human' ? 'warning' :
                           pipeline.status === 'cancelled' ? 'default' : 'default'}
                    style={{ fontSize: 10, lineHeight: '17px', margin: 0 }}
                  >
                    {pipeline.status === 'running' ? '运行中' :
                     pipeline.status === 'completed' ? '已完成' :
                     pipeline.status === 'waiting_human' ? '待确认' :
                     pipeline.status === 'failed' ? '失败' :
                     pipeline.status === 'cancelled' ? '已取消' : pipeline.status}
                  </Tag>
                </div>
              </Popover>
            )}

            {isPipelineRunning && pipeline && (
              <Progress
                percent={pipeline.overallProgress}
                size="small"
                strokeColor="var(--color-accent)"
                trailColor="var(--color-border)"
                showInfo={false}
                style={{ flex: '0 0 160px', margin: 0 }}
              />
            )}

            {latestTask && (
              <div style={{
                display: 'flex', alignItems: 'center', gap: 4,
                fontSize: 12, color: 'var(--color-muted)',
                maxWidth: 280, overflow: 'hidden',
              }}>
                <LoadingOutlined spin style={{ fontSize: 11, flexShrink: 0 }} />
                <span style={{ whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                  {latestTask.message}
                </span>
              </div>
            )}

            <div style={{ flex: 1 }} />
            <AgentStatusBar />

            {isPipelineRunning && (
              <Tooltip title="取消流水线">
                <Button
                  type="text" size="small" danger
                  icon={<PauseCircleOutlined />}
                  onClick={async () => {
                    try { await api.post(`/projects/${currentProject.id}/pipeline/cancel`) } catch {}
                  }}
                />
              </Tooltip>
            )}

            {pipeline?.status === 'failed' && (
              <Tooltip title="从失败处继续运行，已完成的步骤不会重做">
                <Button
                  type="primary" size="small"
                  icon={<RedoOutlined />}
                  loading={starting}
                  onClick={async () => {
                    setStarting(true)
                    setPipelineRunning(true)
                    try {
                      const res: any = await api.post(`/projects/${currentProject.id}/pipeline/resume`)
                      notification.info({
                        message: '流水线已恢复',
                        description: res?.message || '从失败处继续运行',
                        placement: 'topRight',
                        duration: 3,
                      })
                    } catch (e: any) {
                      setPipelineRunning(false)
                      notification.error({
                        message: '恢复失败',
                        description: e?.response?.data?.detail || e?.message || '请检查后端服务',
                        placement: 'topRight',
                        duration: 5,
                      })
                    }
                    setStarting(false)
                  }}
                >
                  从失败处继续
                </Button>
              </Tooltip>
            )}
            {pipeline?.status === 'cancelled' && (
              <Tooltip title="重新启动流水线">
                <Button
                  type="primary" size="small"
                  icon={<PlayCircleOutlined />}
                  loading={starting}
                  onClick={async () => {
                    setStarting(true)
                    setPipelineRunning(true)
                    setPipeline({
                      status: 'running',
                      currentPhase: '初始化中...',
                      currentPhaseIndex: 0,
                      totalPhases: 4,
                      overallProgress: 0,
                      message: '正在启动流水线...',
                      phases: [],
                    })
                    try {
                      await api.post(`/projects/${currentProject.id}/pipeline/auto-run`)
                    } catch (e: any) {
                      setPipelineRunning(false)
                      setPipeline(null)
                      notification.error({
                        message: '启动失败',
                        description: e?.message || e?.detail || '请检查后端服务',
                        placement: 'topRight',
                        duration: 5,
                      })
                    }
                    setStarting(false)
                  }}
                >
                  重新启动
                </Button>
              </Tooltip>
            )}
          </>
        ) : (
          <>
            <span style={{ fontSize: 12, color: 'var(--color-muted)' }}>
              <ExperimentOutlined style={{ marginRight: 6 }} />
              流水线就绪 — 点击启动AI全流程协作
            </span>
            <div style={{ flex: 1 }} />
            <Tooltip title="AI自动依次完成：世界观构建 → 角色设计 → 章节大纲 → 场景创作 → 质量审核">
              <Button
                type="primary" size="small"
                loading={starting}
                icon={<PlayCircleOutlined />}
                onClick={async () => {
                  setStarting(true)
                  setPipelineRunning(true)
                  setPipeline({
                    status: 'running',
                    currentPhase: '初始化中...',
                    currentPhaseIndex: 0,
                    totalPhases: 4,
                    overallProgress: 0,
                    message: '正在初始化流水线...',
                    phases: [],
                  })
                  try {
                    await api.post(`/projects/${currentProject.id}/pipeline/auto-run`)
                  } catch (e: any) {
                    setPipelineRunning(false)
                    setPipeline(null)
                    notification.error({
                      message: '启动失败',
                      description: e?.message || e?.detail || '请检查后端服务是否可用',
                      placement: 'topRight',
                      duration: 5,
                    })
                  }
                  setStarting(false)
                }}
              >
                启动流水线
              </Button>
            </Tooltip>
          </>
        )}
      </div>
    </div>
  )
}
