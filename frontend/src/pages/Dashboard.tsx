import { useMemo, useEffect, useState, useRef } from 'react'
import {
  Card, Row, Col, Statistic, Progress, Tag, Timeline, Badge, Empty,
  Button, Spin, Result, Tooltip, App,
} from 'antd'
import {
  FileTextOutlined, TeamOutlined, EyeOutlined, NodeIndexOutlined,
  ThunderboltOutlined, ClockCircleOutlined, CheckCircleOutlined,
  CloseCircleOutlined, ExclamationCircleOutlined, ReloadOutlined,
  LoadingOutlined, LineChartOutlined, PlayCircleOutlined,
  PauseCircleOutlined, SyncOutlined, ExperimentOutlined,
} from '@ant-design/icons'
import { PieChart, Pie, Cell, ResponsiveContainer, LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip as ReTooltip } from 'recharts'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useProjectStore } from '../stores/projectStore'
import { useAgentStore } from '../stores/agentStore'
import { useAITaskStore } from '../stores/aiTaskStore'
import { api } from '../api/client'
import { eventBus, DataEvents } from '../services/eventBus'
import EmotionChart from '../components/EmotionChart'
import ProjectSelector from '../components/ProjectSelector'

const PHASE_COLORS = ['#3366FF', '#6366f1', '#06B6D4', '#10B981', '#F59E0B', '#f97316', '#EF4444']
const PHASE_LABELS = ['世界观', '角色设计', '剧情大纲', '场景编写', '审核优化', '定稿导出']

interface DashboardPhase { phase: number; name: string; percent: number }
interface DashboardActivity { type: string; description: string; timestamp: string }
interface DashboardEmotionPoint { chapter: string; emotion: number }
interface DashboardStats {
  total_word_count: number
  target_word_count: number
  word_progress: number
  scene_count: number
  scenes_draft: number
  scenes_auditing: number
  scenes_approved: number
  scenes_final: number
  foreshadow_count: number
  foreshadows_normal: number
  foreshadows_warning: number
  foreshadows_danger: number
  character_count: number
  choice_count: number
  chapter_count: number
}
interface DashboardProject {
  id: string; name: string; description: string | null
  genre: string | null; style: string | null
  target_word_count: number | null; current_word_count: number | null
  word_progress: number | null; chapter_count: number | null
  template_id: string | null; status: string; current_phase: number
}
interface DashboardConfig {
  genre: string; core_contradiction: string; theme: string; tone: string
  chapter_count: number; target_ending_count: number; wow_moment_density: number
  world_building_depth: number; character_depth_target: number; plot_complexity: number
}
interface DashboardResponse {
  project: DashboardProject
  stats: DashboardStats
  config: DashboardConfig
  phase_progress: { current_phase: number; phases: DashboardPhase[] }
  recent_activity: DashboardActivity[]
  emotion_curve_preview: DashboardEmotionPoint[]
}

function formatTimestamp(iso: string): string {
  try {
    const d = new Date(iso)
    const pad = (n: number) => String(n).padStart(2, '0')
    return `${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
  } catch { return iso }
}

function getActivityColor(type: string): string {
  switch (type) {
    case 'scene': return 'blue'
    case 'foreshadow': return 'green'
    case 'character': return 'purple'
    case 'chapter': return 'orange'
    case 'full_audit': return 'red'
    default: return 'gray'
  }
}

function getActivityDot(type: string) {
  switch (type) {
    case 'scene': return <ThunderboltOutlined />
    case 'foreshadow': return <EyeOutlined />
    case 'character': return <TeamOutlined />
    case 'chapter': return <FileTextOutlined />
    case 'full_audit': return <CheckCircleOutlined />
    default: return <ClockCircleOutlined />
  }
}

function PipelineStatusCard() {
  const { currentProject } = useProjectStore()
  const { pipeline, isPipelineRunning, activeTasks, setPipeline, setPipelineRunning } = useAITaskStore()
  const [starting, setStarting] = useState(false)
  const { notification } = App.useApp()
  const [apiKeyStatus, setApiKeyStatus] = useState<{ deepseek: boolean; mimo: boolean } | null>(null)
  const initialFetchedRef = useRef(false)
  const optimisticTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(() => {
    api.get<{ deepseek_api_key_set: boolean; mimo_api_key_set: boolean }>('/config/llm')
      .then(data => setApiKeyStatus({ deepseek: data.deepseek_api_key_set, mimo: data.mimo_api_key_set }))
      .catch(() => {})
  }, [])

  useEffect(() => {
    return () => {
      if (optimisticTimerRef.current) {
        clearTimeout(optimisticTimerRef.current)
      }
    }
  }, [])

  useEffect(() => {
    if (!currentProject?.id || initialFetchedRef.current) return
    initialFetchedRef.current = true

    const fetchPipelineStatus = async () => {
      try {
        const data = await api.get<{
          status: string
          current_phase: number
          current_step: number
          template: string
          error_message: string
          task_results: Array<{ key: string; phase: string; agent: string; skill: string; status: string; completed_at: string }>
        }>(`/projects/${currentProject.id}/pipeline/status`)

        if (!data || data.status === 'not_initialized') return

        const isRunning = data.status === 'running'
        const isFailed = data.status === 'failed'
        const isCompleted = data.status === 'completed'
        const isCancelled = data.status === 'cancelled'
        const isWaiting = data.status === 'waiting_human'

        if (isRunning || isFailed || isCompleted || isCancelled || isWaiting) {
          setPipelineRunning(isRunning)

          let phases: Array<{ name: string; steps: number; humanGate: boolean; currentStep: number; status: 'pending' | 'running' | 'completed' | 'waiting' }> = []
          if (data.template) {
            try {
              const tpl = await api.get<{
                name: string; description: string;
                phases: Array<{ name: string; human_gate: boolean; steps: Array<{ agent: string; skill: string }> }>
              }>(`/templates/${encodeURIComponent(data.template)}`)
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
          const overallProgress = isCompleted ? 100 : Math.round((completedCount / totalSteps) * 100)

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

    fetchPipelineStatus()
  }, [currentProject?.id, setPipeline, setPipelineRunning])

  const noApiKey = apiKeyStatus && !apiKeyStatus.deepseek && !apiKeyStatus.mimo

  if (!currentProject) return null

  const runningTasks = activeTasks.filter(t => t.status === 'running')

  return (
    <Card
      style={{ marginBottom: 16, border: isPipelineRunning ? '2px solid var(--color-accent)' : '2px solid transparent' }}
      styles={{ body: { padding: '20px 24px' } }}
    >
      {noApiKey && (
        <div style={{
          marginBottom: 12, padding: '10px 14px', borderRadius: 8,
          background: '#fff7e6', border: '1px solid #ffd591',
          display: 'flex', alignItems: 'center', gap: 8,
        }}>
          <ExclamationCircleOutlined style={{ color: '#fa8c16', fontSize: 16 }} />
          <span style={{ color: '#ad6800', fontSize: 13 }}>
            尚未配置 AI 模型 API Key，流水线无法运行。请点击右上角
            <strong> 设置 → 大模型 API 配置 </strong>
            填写 DeepSeek 或 MiMo 的密钥。
          </span>
          <Button
            size="small" type="link"
            onClick={() => window.dispatchEvent(new CustomEvent('open-llm-config'))}
          >
            去配置
          </Button>
        </div>
      )}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        <div style={{
          width: 56, height: 56, borderRadius: 16,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontSize: 26,
          background: isPipelineRunning ? 'var(--color-accent-soft)' :
                       pipeline?.status === 'completed' ? 'var(--color-success-soft)' :
                       pipeline?.status === 'waiting_human' ? 'var(--color-warning-soft)' :
                       'linear-gradient(135deg, var(--color-accent-soft), #f0e6ff)',
        }}>
          {isPipelineRunning ? <SyncOutlined spin style={{ color: 'var(--color-accent)' }} /> :
           pipeline?.status === 'completed' ? <CheckCircleOutlined style={{ color: 'var(--color-success)' }} /> :
           <ExperimentOutlined style={{ color: 'var(--color-accent)' }} />}
        </div>

        <div style={{ flex: 1 }}>
          <div style={{ fontSize: 16, fontWeight: 700, color: 'var(--color-ink)' }}>
            {isPipelineRunning ? '🚀 AI全自动生成中...' :
             pipeline?.status === 'completed' ? '✅ 剧本生成完毕' :
             pipeline?.status === 'waiting_human' ? '⏸ 等待确认' :
             '🎬 一键全自动生成完整互动影游剧本'}
          </div>
          <div style={{ fontSize: 13, color: 'var(--color-muted)', marginTop: 4, lineHeight: 1.6 }}>
            {isPipelineRunning && pipeline
              ? `${pipeline.currentPhase || ''} · 整体进度 ${pipeline.overallProgress}%`
              : pipeline?.status === 'completed'
                ? '所有阶段已完成，前往各页面查看成果'
                : pipeline?.status === 'cancelled'
                  ? '流水线已取消，可重新启动'
                  : '全自动流程：设定 → 大纲 → 场景创作 → 终审'}
          </div>

          {!isPipelineRunning && pipeline?.status !== 'completed' && pipeline?.status !== 'cancelled' && (
            <div style={{ marginTop: 10, display: 'flex', flexWrap: 'wrap', gap: 6 }}>
              {['设定', '大纲', '场景创作', '终审'].map((s, i) => (
                <span key={i} className="tag" style={{ fontSize: 11, padding: '2px 8px', background: 'var(--color-surface2)', borderRadius: 6 }}>
                  {i + 1}. {s}
                </span>
              ))}
            </div>
          )}

          {isPipelineRunning && pipeline && (
            <div style={{ marginTop: 8, maxWidth: 500 }}>
              <Progress
                percent={pipeline.overallProgress}
                size="small"
                strokeColor="var(--color-accent)"
              />
              {pipeline.phases && pipeline.phases.length > 0 && (
                <div style={{ display: 'flex', gap: 6, marginTop: 8, flexWrap: 'wrap' }}>
                  {pipeline.phases.map((ph, i) => {
                    const icon = ph.status === 'completed' ? '✅' : ph.status === 'running' ? '🔄' : ph.status === 'failed' ? '❌' : '⏳'
                    return (
                      <span key={i} style={{
                        fontSize: 11, padding: '2px 8px', borderRadius: 6,
                        background: ph.status === 'running' ? 'var(--color-accent-soft)' :
                                     ph.status === 'completed' ? 'var(--color-success-soft)' :
                                     ph.status === 'failed' ? '#fff1f0' : 'var(--color-surface2)',
                        color: ph.status === 'running' ? 'var(--color-accent)' :
                                ph.status === 'completed' ? 'var(--color-success)' :
                                ph.status === 'failed' ? '#ff4d4f' : 'var(--color-muted)',
                      }}>
                        {icon} {ph.name}
                        {ph.status === 'running' && ph.currentStep > 0 && ` (${ph.currentStep}/${ph.steps})`}
                        {ph.status === 'completed' && ` ✓`}
                      </span>
                    )
                  })}
                </div>
              )}
            </div>
          )}

          {runningTasks.length > 0 && (
            <div style={{ marginTop: 6, display: 'flex', flexDirection: 'column', gap: 2 }}>
              {runningTasks.slice(0, 3).map(task => (
                <div key={task.taskId} style={{ fontSize: 11, color: 'var(--color-accent)', display: 'flex', alignItems: 'center', gap: 4 }}>
                  <LoadingOutlined spin /> {task.message}
                </div>
              ))}
            </div>
          )}

        </div>

        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          {!isPipelineRunning && pipeline?.status !== 'completed' && (
            <Button
              type="primary"
              size="large"
              icon={<PlayCircleOutlined />}
              loading={starting}
              style={{ height: 48, fontSize: 16, fontWeight: 700, borderRadius: 12, paddingLeft: 32, paddingRight: 32, minWidth: 180 }}
              onClick={async () => {
                setStarting(true)
                try {
                  const result = await api.post<{ status: string; message: string }>(`/projects/${currentProject.id}/pipeline/auto-run`)
                  useAITaskStore.getState().setPipelineRunning(true)
                  useAITaskStore.getState().setPipeline({
                    status: 'running',
                    currentPhase: '初始化',
                    currentPhaseIndex: 0,
                    totalPhases: 4,
                    overallProgress: 0,
                    message: '流水线启动中...',
                    phases: ['设定', '大纲', '场景创作', '终审'].map((name, i) => ({
                      name,
                      steps: 1,
                      humanGate: false,
                      currentStep: 0,
                      status: i === 0 ? 'running' : 'pending' as const,
                    })),
                  })
                  if (optimisticTimerRef.current) clearTimeout(optimisticTimerRef.current)
                  optimisticTimerRef.current = setTimeout(async () => {
                    try {
                      const checkData = await api.get<{ status: string }>(`/projects/${currentProject.id}/pipeline/status`)
                      if (checkData.status !== 'running') {
                        useAITaskStore.getState().setPipelineRunning(false)
                        useAITaskStore.getState().setPipeline({
                          status: checkData.status as any,
                          currentPhase: '',
                          currentPhaseIndex: 0,
                          totalPhases: 0,
                          overallProgress: 0,
                          message: checkData.status === 'failed' ? '流水线启动失败' : '流水线未在运行',
                          phases: [],
                        })
                      }
                    } catch {}
                  }, 15000)
                } catch (err: any) {
                  useAITaskStore.getState().setPipelineRunning(false)
                  notification.error({ message: '启动流水线失败', description: err?.detail || err?.message || '请检查后端服务是否运行', placement: 'topRight' })
                } finally {
                  setStarting(false)
                }
              }}
            >
              一键全自动生成
            </Button>
          )}
          {isPipelineRunning && (
            <>
              <Button
                danger
                icon={<PauseCircleOutlined />}
                onClick={async () => {
                  try {
                    await api.post(`/projects/${currentProject.id}/pipeline/cancel`)
                    useAITaskStore.getState().setPipelineRunning(false)
                  } catch (err: any) {
                    notification.error({ message: '取消失败', description: err?.detail || '操作失败', placement: 'topRight' })
                  }
                }}
              >
                停止生成
              </Button>
              <Tag color="processing" icon={<SyncOutlined spin />}>
                运行中
              </Tag>
            </>
          )}
          {pipeline?.status === 'waiting_human' && (
            <>
              <Button
                type="primary"
                icon={<CheckCircleOutlined />}
                onClick={async () => {
                  try {
                    await api.post(`/projects/${currentProject.id}/pipeline/approve`)
                  } catch (err: any) {
                    notification.error({ message: '批准失败', description: err?.detail || '操作失败', placement: 'topRight' })
                  }
                }}
              >
                批准继续
              </Button>
              <Button
                danger
                icon={<CloseCircleOutlined />}
                onClick={async () => {
                  try {
                    await api.post(`/projects/${currentProject.id}/pipeline/reject`, { reason: '需要修改' })
                  } catch (err: any) {
                    notification.error({ message: '驳回失败', description: err?.detail || '操作失败', placement: 'topRight' })
                  }
                }}
              >
                驳回修改
              </Button>
            </>
          )}
          {pipeline?.status === 'failed' && (
            <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
              <Button
                type="primary"
                icon={<ReloadOutlined />}
                loading={starting}
                onClick={async () => {
                  setStarting(true)
                  try {
                    const result = await api.post<{ status: string; message: string }>(`/projects/${currentProject.id}/pipeline/resume`)
                    useAITaskStore.getState().setPipelineRunning(true)
                    useAITaskStore.getState().setPipeline({
                      status: 'running',
                      currentPhase: '恢复中',
                      currentPhaseIndex: 0,
                      totalPhases: 4,
                      overallProgress: 0,
                      message: result.message || '从失败处继续...',
                      phases: [],
                    })
                  } catch (err: any) {
                    notification.error({ message: '恢复失败', description: err?.detail || err?.message || '操作失败', placement: 'topRight' })
                  } finally {
                    setStarting(false)
                  }
                }}
                style={{ background: '#f59e0b', borderColor: '#f59e0b' }}
              >
                从失败处继续
              </Button>
              <Button
                icon={<PlayCircleOutlined />}
                loading={starting}
                onClick={async () => {
                  setStarting(true)
                  try {
                    const result = await api.post<{ status: string; message: string }>(`/projects/${currentProject.id}/pipeline/auto-run`)
                    useAITaskStore.getState().setPipelineRunning(true)
                    useAITaskStore.getState().setPipeline({
                      status: 'running',
                      currentPhase: '初始化',
                      currentPhaseIndex: 0,
                      totalPhases: 4,
                      overallProgress: 0,
                      message: '从头开始生成...',
                      phases: [],
                    })
                  } catch (err: any) {
                    notification.error({ message: '启动失败', description: err?.detail || err?.message || '操作失败', placement: 'topRight' })
                  } finally {
                    setStarting(false)
                  }
                }}
              >
                从头重新生成
              </Button>
              <Tag color="error" icon={<CloseCircleOutlined />}>
                生成失败
              </Tag>
            </div>
          )}
          {pipeline?.status === 'cancelled' && (
            <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
              <Button
                type="primary"
                icon={<PlayCircleOutlined />}
                loading={starting}
                onClick={async () => {
                  setStarting(true)
                  try {
                    await api.post<{ status: string; message: string }>(`/projects/${currentProject.id}/pipeline/auto-run`)
                    useAITaskStore.getState().setPipelineRunning(true)
                    useAITaskStore.getState().setPipeline({
                      status: 'running',
                      currentPhase: '初始化',
                      currentPhaseIndex: 0,
                      totalPhases: 4,
                      overallProgress: 0,
                      message: '重新启动流水线...',
                      phases: [],
                    })
                  } catch (err: any) {
                    notification.error({ message: '启动失败', description: err?.detail || err?.message || '操作失败', placement: 'topRight' })
                  } finally {
                    setStarting(false)
                  }
                }}
              >
                重新启动
              </Button>
              <Tag color="default" icon={<CloseCircleOutlined />}>
                已取消
              </Tag>
            </div>
          )}
        </div>
      </div>
    </Card>
  )
}

export default function Dashboard() {
  const { currentProject } = useProjectStore()
  const { agents, taskQueue } = useAgentStore()
  const queryClient = useQueryClient()

  const {
    data: dashboardData, isLoading, isError, error, refetch, isFetching,
  } = useQuery<DashboardResponse>({
    queryKey: ['dashboard', currentProject?.id],
    queryFn: ({ signal }) => api.get<DashboardResponse>(`/projects/${currentProject!.id}/dashboard`, signal),
    enabled: !!currentProject?.id,
    staleTime: 30_000,
    refetchInterval: 30_000,
    retry: (failureCount, err: any) => {
      if (err?.name === 'AbortError') return false
      return failureCount < 2
    },
    refetchOnWindowFocus: (query) => {
      return query.state.error?.name !== 'AbortError'
    },
  })

  const busyAgents = agents.filter(a => a.status === 'busy').length

  useEffect(() => {
    const unsubs = [
      eventBus.on(DataEvents.SCENE_CREATED, () => {
        queryClient.invalidateQueries({ queryKey: ['dashboard', currentProject?.id] })
      }),
      eventBus.on(DataEvents.SCENE_UPDATED, () => {
        queryClient.invalidateQueries({ queryKey: ['dashboard', currentProject?.id] })
      }),
      eventBus.on(DataEvents.SCENE_FINALIZED, () => {
        queryClient.invalidateQueries({ queryKey: ['dashboard', currentProject?.id] })
      }),
      eventBus.on(DataEvents.CHAPTER_CREATED, () => {
        queryClient.invalidateQueries({ queryKey: ['dashboard', currentProject?.id] })
      }),
      eventBus.on(DataEvents.CHAPTER_UPDATED, () => {
        queryClient.invalidateQueries({ queryKey: ['dashboard', currentProject?.id] })
      }),
      eventBus.on(DataEvents.CHARACTER_CREATED, () => {
        queryClient.invalidateQueries({ queryKey: ['dashboard', currentProject?.id] })
      }),
      eventBus.on(DataEvents.CHARACTER_UPDATED, () => {
        queryClient.invalidateQueries({ queryKey: ['dashboard', currentProject?.id] })
      }),
      eventBus.on(DataEvents.CHARACTER_DELETED, () => {
        queryClient.invalidateQueries({ queryKey: ['dashboard', currentProject?.id] })
      }),
      eventBus.on(DataEvents.FORESHADOW_CREATED, () => {
        queryClient.invalidateQueries({ queryKey: ['dashboard', currentProject?.id] })
      }),
      eventBus.on(DataEvents.FORESHADOW_UPDATED, () => {
        queryClient.invalidateQueries({ queryKey: ['dashboard', currentProject?.id] })
      }),
      eventBus.on(DataEvents.FORESHADOW_DELETED, () => {
        queryClient.invalidateQueries({ queryKey: ['dashboard', currentProject?.id] })
      }),
      eventBus.on(DataEvents.WORLD_CONFIG_UPDATED, () => {
        queryClient.invalidateQueries({ queryKey: ['dashboard', currentProject?.id] })
      }),
      eventBus.on(DataEvents.AI_GENERATION_COMPLETED, () => {
        queryClient.invalidateQueries({ queryKey: ['dashboard', currentProject?.id] })
      }),
      eventBus.on(DataEvents.AI_AUDIT_COMPLETED, () => {
        queryClient.invalidateQueries({ queryKey: ['dashboard', currentProject?.id] })
      }),
      eventBus.on(DataEvents.PIPELINE_STATUS_CHANGED, () => {
        queryClient.invalidateQueries({ queryKey: ['dashboard', currentProject?.id] })
      }),
      eventBus.on(DataEvents.PROJECT_SWITCHED, () => {
        queryClient.invalidateQueries({ queryKey: ['dashboard', currentProject?.id] })
      }),
    ]
    return () => unsubs.forEach((unsub) => unsub())
  }, [currentProject?.id, queryClient])

  const emotionChartData = useMemo(() => {
    if (dashboardData?.emotion_curve_preview?.length) {
      return dashboardData.emotion_curve_preview.map(pt => ({ name: pt.chapter, emotion: pt.emotion }))
    }
    return []
  }, [dashboardData])

  const avgEmotion = useMemo(() => {
    if (emotionChartData.length === 0) return 5
    const sum = emotionChartData.reduce((acc, pt) => acc + pt.emotion, 0)
    return Math.round(sum / emotionChartData.length)
  }, [emotionChartData])

  const phaseDataForPie = useMemo(() => {
    const phases = dashboardData?.phase_progress?.phases
    if (phases) {
      return phases.map((p, i) => ({ name: p.name || PHASE_LABELS[i] || `Phase ${p.phase}`, value: p.percent, color: PHASE_COLORS[i] || '#94a3b8' }))
    }
    return []
  }, [dashboardData])

  const stats = dashboardData?.stats
  const recentActivity = dashboardData?.recent_activity

  return (
    <div style={{ fontFamily: 'var(--font-family)', height: '100%', overflow: 'auto' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 24, flexShrink: 0 }}>
        <div>
          <h2 className="section-title" style={{ fontSize: 24 }}>项目总览</h2>
          <p className="text-muted" style={{ margin: '4px 0 0' }}>
            {currentProject?.name || '未命名影游'}
            {dashboardData?.config?.genre ? ` · ${dashboardData.config.genre}` : ''}
          </p>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          {currentProject && dashboardData?.phase_progress?.phases?.[dashboardData.phase_progress.current_phase] && (
            <span className="tag tag-accent">
              {dashboardData.phase_progress.phases[dashboardData.phase_progress.current_phase].name || PHASE_LABELS[dashboardData.phase_progress.current_phase]}
            </span>
          )}
          <Tooltip title="刷新数据">
            <button className="btn-ghost" onClick={() => refetch()} disabled={!currentProject}>
              <ReloadOutlined spin={!!(isFetching && !isLoading)} />
            </button>
          </Tooltip>
        </div>
      </div>

      {!currentProject ? (
        <ProjectSelector
          onCreate={() => {
            const event = new CustomEvent('open-create-project')
            window.dispatchEvent(event)
          }}
        />
      ) : isLoading ? (
        <div style={{ display: 'flex', justifyContent: 'center', padding: 80 }}>
          <Spin size="large" indicator={<LoadingOutlined style={{ fontSize: 36 }} spin />} />
        </div>
      ) : isError ? (
        <div className="card-surface" style={{ padding: 48 }}>
          <Result
            status="error"
            title="数据加载失败"
            subTitle={(error as Error)?.message || '无法获取仪表盘数据'}
            extra={<Button type="primary" icon={<ReloadOutlined />} onClick={() => refetch()}>重新加载</Button>}
          />
        </div>
      ) : (
        <>
          {/* Pipeline Status Summary */}
          <PipelineStatusCard />

          {/* Stat Cards */}
          <Row gutter={[16, 16]}>
            {[
              { title: '总字数', value: stats?.total_word_count ?? 0, suffix: '字', icon: <FileTextOutlined style={{ color: 'var(--color-accent)' }} /> },
              { title: '场景数', value: stats?.scene_count ?? 0, suffix: '', icon: <ThunderboltOutlined style={{ color: 'var(--color-warning)' }} />,
                extra: stats && stats.scene_count > 0 ? (
                  <Tooltip title={<div className="text-xs"><div>草稿: {stats.scenes_draft}</div><div>审核中: {stats.scenes_auditing}</div><div>已通过: {stats.scenes_approved}</div><div>定稿: {stats.scenes_final}</div></div>}>
                    <span className="tag tag-purple" style={{ marginLeft: 4, cursor: 'pointer' }}>详情</span>
                  </Tooltip>
                ) : undefined },
              { title: '伏笔数', value: stats?.foreshadow_count ?? 0, suffix: '', icon: <EyeOutlined style={{ color: 'var(--color-success)' }} /> },
              { title: '角色数', value: stats?.character_count ?? 0, suffix: '', icon: <TeamOutlined style={{ color: 'var(--color-purple)' }} /> },
            ].map((item, idx) => (
              <Col xs={12} sm={6} key={idx}>
                <div className="card-surface" style={{ padding: '20px 24px' }}>
                  <Statistic
                    title={<span className="text-sm text-muted">{item.title}</span>}
                    value={item.value}
                    suffix={item.suffix ? <span style={{ fontSize: 14, color: 'var(--color-muted)' }}>{item.suffix}</span> : undefined}
                    prefix={item.icon}
                    valueStyle={{ fontSize: 28, fontWeight: 700, color: 'var(--color-ink)', fontFamily: 'var(--font-family)' }}
                  />
                  {item.extra}
                </div>
              </Col>
            ))}
          </Row>

          <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
            {/* Progress */}
            <Col xs={24} lg={14}>
              <div className="card-surface" style={{ padding: 24 }}>
                <h3 className="subsection-title" style={{ marginBottom: 16 }}>项目进度</h3>
                <Row gutter={[16, 16]}>
                  <Col xs={24} md={8}>
                    <div style={{ display: 'flex', justifyContent: 'center' }}>
                      <ResponsiveContainer width={160} height={160}>
                        <PieChart>
                          <Pie
                            data={phaseDataForPie}
                            cx="50%" cy="50%"
                            innerRadius={45} outerRadius={68}
                            dataKey="value"
                            strokeWidth={2}
                            stroke="var(--color-surface)"
                          >
                            {phaseDataForPie.map((entry, idx) => (
                              <Cell key={idx} fill={entry.color} opacity={entry.value > 0 ? 1 : 0.1} />
                            ))}
                          </Pie>
                        </PieChart>
                      </ResponsiveContainer>
                    </div>
                    <div style={{ textAlign: 'center', marginTop: 4 }}>
                      <span style={{ fontSize: 28, fontWeight: 700, color: 'var(--color-accent)', fontFamily: 'var(--font-family)' }}>
                        {dashboardData?.phase_progress?.current_phase ?? 0}
                      </span>
                      <span className="text-muted" style={{ fontSize: 13 }}> / 6</span>
                    </div>
                  </Col>
                  <Col xs={24} md={16}>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                      {(dashboardData?.phase_progress?.phases ?? PHASE_LABELS.map((name, i) => ({ phase: i, name, percent: 0 }))).map((phase, i) => {
                        const isActive = dashboardData?.phase_progress?.current_phase === i
                        return (
                          <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                            <span className="text-sm text-muted" style={{ width: 60, textAlign: 'right' }}>Phase {i}</span>
                            <Progress
                              percent={phase.percent}
                              size="small"
                              strokeColor={PHASE_COLORS[i]}
                              trailColor="var(--color-border)"
                              showInfo={false}
                              style={{ flex: 1 }}
                            />
                            <span style={{
                              fontSize: 12, width: 50,
                              color: isActive ? 'var(--color-accent)' : 'var(--color-muted)',
                              fontWeight: isActive ? 700 : 400,
                            }}>
                              {phase.name || PHASE_LABELS[i]}
                            </span>
                          </div>
                        )
                      })}
                    </div>
                  </Col>
                </Row>
              </div>
            </Col>

            {/* Activity */}
            <Col xs={24} lg={10}>
              <div className="card-surface" style={{ padding: 24 }}>
                <h3 className="subsection-title" style={{ marginBottom: 16 }}>最近活动</h3>
                {recentActivity && recentActivity.length > 0 ? (
                  <Timeline
                    items={recentActivity.map(act => ({
                      color: getActivityColor(act.type),
                      dot: getActivityDot(act.type),
                      children: (
                        <div>
                          <div style={{ fontSize: 13 }}>{act.description}</div>
                          <div className="text-xs text-muted" style={{ marginTop: 2 }}>{formatTimestamp(act.timestamp)}</div>
                        </div>
                      ),
                    }))}
                  />
                ) : (
                  <Empty description="暂无活动记录" image={Empty.PRESENTED_IMAGE_SIMPLE} />
                )}
              </div>
            </Col>
          </Row>

          <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
            {/* Foreshadow Health */}
            <Col xs={24} md={8}>
              <div className="card-surface" style={{ padding: 24 }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
                  <h3 className="subsection-title">伏笔健康度</h3>
                  <NodeIndexOutlined className="text-muted" />
                </div>
                <Row gutter={[8, 8]}>
                  {[
                    { label: '正常', count: stats?.foreshadows_normal ?? 0, color: '#10B981' },
                    { label: '警告', count: stats?.foreshadows_warning ?? 0, color: '#F59E0B' },
                    { label: '危险', count: stats?.foreshadows_danger ?? 0, color: '#EF4444' },
                  ].map(item => (
                    <Col span={8} key={item.label} style={{ textAlign: 'center' }}>
                      <Progress
                        type="circle"
                        percent={stats && stats.foreshadow_count > 0 ? Math.round((item.count / stats.foreshadow_count) * 100) : 0}
                        size={70}
                        strokeColor={item.color}
                        format={() => `${item.count}`}
                      />
                      <div className="text-xs text-muted" style={{ marginTop: 6 }}>{item.label}</div>
                    </Col>
                  ))}
                </Row>
                <div style={{ textAlign: 'center', marginTop: 12 }}>
                  {stats && stats.foreshadow_count > 0 ? (
                    <span className="text-sm text-muted">
                      共 <strong style={{ color: 'var(--color-ink)' }}>{stats.foreshadow_count}</strong> 个伏笔
                      {stats.foreshadows_danger > 0 && <span style={{ color: 'var(--color-danger)', marginLeft: 4 }}>⚠ 有 {stats.foreshadows_danger} 个危险项</span>}
                    </span>
                  ) : <span className="text-sm text-muted">暂无伏笔数据</span>}
                </div>
              </div>
            </Col>

            {/* Agent Status */}
            <Col xs={24} md={8}>
              <div className="card-surface" style={{ padding: 24 }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
                  <h3 className="subsection-title">Agent 状态</h3>
                  <Badge status={busyAgents > 0 ? 'processing' : 'success'} text={busyAgents > 0 ? `${busyAgents} 忙碌` : '全部空闲'} />
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                  {agents.map((agent) => (
                    <div
                      key={agent.name}
                      style={{
                        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                        padding: '8px 10px', borderRadius: 8,
                        background: 'var(--color-surface2)',
                        transition: 'background 0.15s',
                      }}
                    >
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                        <span className={`badge-dot ${agent.status === 'busy' ? 'amber' : agent.status === 'error' ? 'red' : agent.status === 'offline' ? 'gray' : 'green'} ${agent.status === 'busy' ? 'agent-pulse' : ''}`} />
                        <span style={{ fontSize: 13 }}>{agent.name}</span>
                      </div>
                      <Tag color={agent.status === 'idle' ? 'green' : agent.status === 'busy' ? 'gold' : agent.status === 'error' ? 'red' : 'default'}>
                        {agent.status === 'idle' ? '空闲' : agent.status === 'busy' ? '忙碌' : agent.status === 'error' ? '错误' : '离线'}
                      </Tag>
                    </div>
                  ))}
                </div>
                {taskQueue > 0 && (
                  <div style={{ marginTop: 12, paddingTop: 12, borderTop: '1px solid var(--color-border)' }}>
                    <span className="text-sm text-muted">任务队列: {taskQueue} 个待处理</span>
                  </div>
                )}
              </div>
            </Col>

            {/* Emotion Preview */}
            <Col xs={24} md={8}>
              <div className="card-surface" style={{ padding: 24 }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
                  <h3 className="subsection-title">情感曲线预览</h3>
                  <LineChartOutlined className="text-muted" />
                </div>
                <ResponsiveContainer width="100%" height={140}>
                  <LineChart data={emotionChartData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
                    <XAxis dataKey="name" tick={{ fontSize: 10 }} stroke="var(--color-subtle)" />
                    <YAxis domain={[0, 10]} tick={{ fontSize: 10 }} stroke="var(--color-subtle)" />
                    <ReTooltip contentStyle={{ borderRadius: 8, border: '1px solid var(--color-border)', fontSize: 12, fontFamily: 'var(--font-family)' }} />
                    <Line type="monotone" dataKey="emotion" stroke="var(--color-accent)" strokeWidth={2} dot={{ fill: 'var(--color-accent)', r: 3 }} activeDot={{ r: 5 }} />
                  </LineChart>
                </ResponsiveContainer>
                <div style={{ marginTop: 8 }}>
                  {emotionChartData.length > 0 ? (
                    <EmotionChart level={avgEmotion} target={6} size="sm" />
                  ) : (
                    <div className="text-xs text-muted" style={{ textAlign: 'center' }}>暂无数据</div>
                  )}
                </div>
                <p className="text-xs text-muted" style={{ textAlign: 'center', marginTop: 8 }}>
                  {dashboardData?.emotion_curve_preview?.length
                    ? `基于 ${dashboardData.emotion_curve_preview.length} 个章节的真实数据`
                    : '创建章节后将自动显示情感曲线'}
                </p>
              </div>
            </Col>
          </Row>
        </>
      )}
    </div>
  )
}
