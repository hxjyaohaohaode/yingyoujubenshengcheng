import { useState, useEffect, useRef, useMemo, useCallback } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  Card, Button, Tag, Tabs, Input, Select, Switch, Slider, Progress,
  Collapse, App, Tooltip, Badge, Drawer, Modal,
  Empty, Space, Row, Col, Spin, Result,
} from 'antd'
import {
  VideoCameraOutlined, RobotOutlined, AuditOutlined, EditOutlined,
  CheckCircleOutlined, CloseCircleOutlined, ExclamationCircleOutlined,
  StarOutlined, ThunderboltOutlined, EyeOutlined, PlusOutlined,
  DeleteOutlined, SaveOutlined, HistoryOutlined, UndoOutlined,
  LoadingOutlined, FullscreenOutlined, FullscreenExitOutlined,
  MinusCircleOutlined, PlusCircleOutlined, ReloadOutlined,
} from '@ant-design/icons'
import { useProjectStore } from '../stores/projectStore'
import { useAgentStore } from '../stores/agentStore'
import { api, chaptersApi, scenesApi, charactersApi } from '../api/client'
import { eventBus, DataEvents } from '../services/eventBus'
import { useTaskProgress } from '../hooks/useTaskProgress'
import ConfirmDialog from '../components/ConfirmDialog'
import EmotionChart from '../components/EmotionChart'
import ForeshadowTag from '../components/ForeshadowTag'
import type { Scene, Chapter, Character } from '../api/client'

const { TextArea } = Input

// ========== Types ==========

interface DialogueLine {
  id: string
  character_id: string
  character_name: string
  text: string
  subtext: string
}

interface ChoiceOption {
  id: string
  text: string
  consequence: string
  jump_scene: string
  hidden: boolean
  hidden_condition: string
}

interface ForeshadowOp {
  fs_id: string
  fs_code: string
  fs_name: string
  op_type: 'plant' | 'reinforce' | 'reveal'
  description: string
  completed: boolean
}

interface CausalChain {
  precondition: string
  catalyst: string
  direct_result: string
  indirect_result: string
  long_term_result: string
}

interface AuditResult {
  id: string
  version: number
  checker_results: { name: string; pass: boolean; detail: string }[]
  llm_results: { name: string; score: number; detail: string }[]
  overall_result: 'pass' | 'pass_with_warnings' | 'fail'
  issues: string[]
  suggestions: string[]
  created_at: string
}

interface SceneVersion {
  version: number
  change_reason: string
  created_at: string
  content?: Record<string, any>
}

interface SceneData {
  id: string
  project_id: string
  chapter_id: string
  scene_code: string
  scene_type: string
  location: string
  weather: string
  emotion_level: number
  narration: string
  dialogue: DialogueLine[]
  actions: string[]
  foreshadow_ops: ForeshadowOp[]
  choices: ChoiceOption[]
  causal_chain: CausalChain
  is_wow_moment: boolean
  wow_type: string
  wow_spec: string
  characters_involved: string[]
  status: string
  version: number
  audit_reports: AuditResult[]
  human_reviewed: boolean
  human_feedback: string
}

interface ChapterGroup {
  chapter_id: string
  chapter_number: number
  title: string
  scenes: SceneData[]
}

const SCENE_TYPES = ['dialogue', 'action', 'exploration', 'puzzle', 'cutscene', 'branch']
const SCENE_TYPE_LABELS: Record<string, string> = {
  dialogue: '对白', action: '动作', exploration: '探索', puzzle: '解谜', cutscene: '过场', branch: '分支',
}
const SCENE_STATUS_ICON: Record<string, { icon: React.ReactNode; color: string; label: string }> = {
  draft: { icon: <EditOutlined />, color: '#d9d9d9', label: '待创作' },
  in_review: { icon: <AuditOutlined />, color: '#3b82f6', label: '审核中' },
  auditing: { icon: <AuditOutlined />, color: '#3b82f6', label: '审核中' },
  rejected: { icon: <CloseCircleOutlined />, color: '#ef4444', label: '审计未通过' },
  passed: { icon: <CheckCircleOutlined />, color: '#52c41a', label: '审核通过' },
  approved: { icon: <CheckCircleOutlined />, color: '#52c41a', label: '审核通过' },
  final: { icon: <CheckCircleOutlined />, color: '#10b981', label: '已定稿' },
  finalized: { icon: <CheckCircleOutlined />, color: '#10b981', label: '已定稿' },
}

const CHECKER_NAMES = ['字数达标', '角色一致', '伏笔植入', '情感目标', '因果链完整', '选择有效性']
const LLM_CHECK_NAMES = ['原创性', '凝聚力', '角色深度', '节奏控制', '对白质量', '选择设计']

function normalizeSceneStatus(status?: string): string {
  switch (status) {
    case 'auditing':
      return 'in_review'
    case 'approved':
      return 'passed'
    case 'finalized':
      return 'final'
    default:
      return status || 'draft'
  }
}

function mapApiSceneToSceneData(scene: Scene, chapterId: string): SceneData {
  const safeDialogue = Array.isArray(scene.dialogue) ? scene.dialogue as DialogueLine[] : []
  const safeActions = Array.isArray(scene.actions) ? scene.actions as string[] : []
  const safeForeshadowOps = Array.isArray(scene.foreshadow_ops) ? scene.foreshadow_ops as ForeshadowOp[] : []
  const safeChoices = Array.isArray(scene.choices) ? scene.choices as ChoiceOption[] : []
  const safeAuditReports = Array.isArray(scene.audit_reports) ? scene.audit_reports as AuditResult[] : []
  const safeCharacters = Array.isArray(scene.characters_involved) ? scene.characters_involved as string[] : []
  const causalChain: CausalChain =
    scene.causal_chain && typeof scene.causal_chain === 'object'
      ? {
          precondition: (scene.causal_chain as any).precondition || '',
          catalyst: (scene.causal_chain as any).catalyst || '',
          direct_result: (scene.causal_chain as any).direct_result || '',
          indirect_result: (scene.causal_chain as any).indirect_result || '',
          long_term_result: (scene.causal_chain as any).long_term_result || '',
        }
      : { precondition: '', catalyst: '', direct_result: '', indirect_result: '', long_term_result: '' }

  return {
    id: scene.id,
    project_id: scene.project_id,
    chapter_id: chapterId,
    scene_code: scene.scene_code,
    scene_type: scene.scene_type || 'dialogue',
    location: scene.location || '',
    weather: scene.weather || '',
    emotion_level: scene.emotion_level ?? 5,
    narration: scene.narration || '',
    dialogue: safeDialogue,
    actions: safeActions,
    foreshadow_ops: safeForeshadowOps,
    choices: safeChoices,
    causal_chain: causalChain,
    is_wow_moment: scene.is_wow_moment ?? false,
    wow_type: scene.wow_type || '',
    wow_spec: scene.wow_spec || '',
    characters_involved: safeCharacters,
    status: normalizeSceneStatus(scene.status),
    version: scene.version ?? 1,
    audit_reports: safeAuditReports,
    human_reviewed: scene.human_reviewed ?? false,
    human_feedback: scene.human_feedback || '',
  }
}

function buildScenePatchPayload(scene: SceneData): Record<string, unknown> {
  return {
    scene_code: scene.scene_code,
    scene_type: scene.scene_type,
    location: scene.location,
    weather: scene.weather,
    emotion_level: scene.emotion_level,
    narration: scene.narration,
    dialogue: scene.dialogue,
    actions: scene.actions,
    foreshadow_ops: scene.foreshadow_ops,
    choices: scene.choices,
    causal_chain: scene.causal_chain,
    is_wow_moment: scene.is_wow_moment,
    wow_type: scene.wow_type || null,
    wow_spec: scene.wow_spec || null,
    characters_involved: scene.characters_involved,
    human_feedback: scene.human_feedback || null,
  }
}

export default function SceneWorkshop() {
  const { notification } = App.useApp()
  const { currentProject } = useProjectStore()
  const { updateAgent } = useAgentStore()
  const queryClient = useQueryClient()

  const [selectedSceneId, setSelectedSceneId] = useState<string | null>(null)
  const [editScene, setEditScene] = useState<SceneData | null>(null)
  const [activeTab, setActiveTab] = useState('narration')
  const [hasUnsaved, setHasUnsaved] = useState(false)
  const [isFullscreen, setIsFullscreen] = useState(false)
  const [confirmFinalize, setConfirmFinalize] = useState<string | null>(null)
  const [showVersionPanel, setShowVersionPanel] = useState(false)
  const [showRejectModal, setShowRejectModal] = useState(false)
  const [rejectCount, setRejectCount] = useState(0)

  const [expandedChapterIds, setExpandedChapterIds] = useState<Set<string>>(new Set())
  const [sidebarScrollTop, setSidebarScrollTop] = useState(0)
  const [sidebarViewHeight, setSidebarViewHeight] = useState(600)

  const [genTaskId, setGenTaskId] = useState<string | null>(null)
  const [auditTaskId, setAuditTaskId] = useState<string | null>(null)
  const [genRequirements, setGenRequirements] = useState('')

  const [createModalOpen, setCreateModalOpen] = useState(false)
  const [newSceneForm, setNewSceneForm] = useState({
    chapter_id: '',
    scene_code: '',
    scene_type: 'dialogue' as string,
    location: '',
    weather: '',
    emotion_level: 5,
    characters_involved: [] as string[],
  })

  const genProgressHook = useTaskProgress(genTaskId)
  const auditProgressHook = useTaskProgress(auditTaskId)

  const isGenerating = genTaskId !== null && !['completed', 'failed', 'cancelled', 'timeout'].includes(genProgressHook.status)
  const isAuditing = auditTaskId !== null && !['completed', 'failed', 'cancelled', 'timeout'].includes(auditProgressHook.status)

  const autoSaveTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const savingRef = useRef(false)
  const editSceneRef = useRef(editScene)
  editSceneRef.current = editScene
  const hasUnsavedRef = useRef(hasUnsaved)
  hasUnsavedRef.current = hasUnsaved
  const projectIdRef = useRef(currentProject?.id)
  projectIdRef.current = currentProject?.id
  const sidebarRef = useRef<HTMLDivElement>(null)
  const isFirstDataLoad = useRef(true)

  const projectId = currentProject?.id || ''

  const {
    data: chapters = [],
    isLoading: chaptersLoading,
    isError: chaptersError,
    refetch: refetchChapters,
  } = useQuery({
    queryKey: ['chapters', projectId],
    queryFn: () => chaptersApi.list(projectId),
    enabled: !!projectId,
    staleTime: 60_000,
  })

  const {
    data: scenes = [],
    isLoading: scenesLoading,
    isError: scenesError,
    refetch: refetchScenes,
  } = useQuery({
    queryKey: ['scenes', projectId],
    queryFn: () => scenesApi.list(projectId),
    enabled: !!projectId,
    staleTime: 10_000,
  })

  const {
    data: characters = [],
  } = useQuery({
    queryKey: ['characters', projectId],
    queryFn: () => charactersApi.list(projectId),
    enabled: !!projectId,
    staleTime: 300_000,
  })

  const {
    data: versionHistory = [],
    isLoading: versionLoading,
  } = useQuery({
    queryKey: ['sceneVersions', projectId, selectedSceneId],
    queryFn: async () => {
      try {
        return await api.get<SceneVersion[]>(`/projects/${projectId}/scenes/${selectedSceneId}/versions`)
      } catch {
        return []
      }
    },
    enabled: !!(projectId && selectedSceneId),
  })

  const sortedChapters = useMemo(
    () => [...chapters].sort((a, b) => a.chapter_number - b.chapter_number),
    [chapters],
  )

  const chaptersData: ChapterGroup[] = useMemo(() => {
    const sceneMap = new Map<string, Scene[]>()
    for (const s of scenes) {
      const cid = s.chapter_id || '__uncategorized__'
      if (!sceneMap.has(cid)) sceneMap.set(cid, [])
      sceneMap.get(cid)!.push(s)
    }
    return sortedChapters.map(ch => ({
      chapter_id: ch.id,
      chapter_number: ch.chapter_number,
      title: ch.title || `第${ch.chapter_number}章`,
      scenes: (sceneMap.get(ch.id) || []).map(s => mapApiSceneToSceneData(s, ch.id)),
    }))
  }, [sortedChapters, scenes])

  useEffect(() => {
    if (chaptersData.length > 0 && expandedChapterIds.size === 0) {
      setExpandedChapterIds(new Set(chaptersData.map(ch => ch.chapter_id)))
    }
  }, [chaptersData])

  const CHAPTER_H = 42
  const SCENE_H = 34
  const BUFFER_ITEMS = 8

  interface VirtualRow {
    key: string
    type: 'chapter' | 'scene'
    chIdx: number
    scIdx?: number
    y: number
    height: number
  }

  const { virtualRows, totalHeight } = useMemo(() => {
    const rows: VirtualRow[] = []
    let y = 0
    chaptersData.forEach((ch, ci) => {
      rows.push({ key: ch.chapter_id, type: 'chapter', chIdx: ci, y, height: CHAPTER_H })
      y += CHAPTER_H
      if (expandedChapterIds.has(ch.chapter_id)) {
        ch.scenes.forEach((_sc, si) => {
          rows.push({ key: ch.chapter_id + '-scene-' + si, type: 'scene', chIdx: ci, scIdx: si, y, height: SCENE_H })
          y += SCENE_H
        })
      }
    })
    return { virtualRows: rows, totalHeight: y }
  }, [chaptersData, expandedChapterIds])

  const [visibleStart, visibleEnd] = useMemo(() => {
    const bufRows = Math.max(0, Math.floor(sidebarScrollTop / Math.min(CHAPTER_H, SCENE_H)) - BUFFER_ITEMS)
    const endBufRows = Math.min(
      virtualRows.length,
      Math.ceil((sidebarScrollTop + sidebarViewHeight) / Math.min(CHAPTER_H, SCENE_H)) + BUFFER_ITEMS,
    )
    const start = Math.max(0, bufRows)
    const end = Math.min(virtualRows.length, endBufRows)
    return [start, end]
  }, [sidebarScrollTop, sidebarViewHeight, virtualRows.length])

  const visibleRows = useMemo(() => {
    const rows = virtualRows.slice(visibleStart, visibleEnd)
    const offsetY = visibleStart > 0 ? virtualRows[visibleStart].y : 0
    return { rows, offsetY }
  }, [virtualRows, visibleStart, visibleEnd])

  const toggleChapter = useCallback((chapterId: string) => {
    setExpandedChapterIds(prev => {
      const next = new Set(prev)
      if (next.has(chapterId)) {
        next.delete(chapterId)
      } else {
        next.add(chapterId)
      }
      return next
    })
  }, [])

  const handleSidebarScroll = useCallback(() => {
    if (sidebarRef.current) {
      setSidebarScrollTop(sidebarRef.current.scrollTop)
    }
  }, [])

  useEffect(() => {
    const el = sidebarRef.current
    if (!el) return
    setSidebarViewHeight(el.clientHeight)
    const ro = new ResizeObserver(entries => {
      for (const entry of entries) {
        setSidebarViewHeight(entry.contentRect.height)
      }
    })
    ro.observe(el)
    return () => ro.disconnect()
  }, [])

  useEffect(() => {
    if (chaptersData.length > 0 && isFirstDataLoad.current) {
      const allScenes = chaptersData.flatMap(c => c.scenes)
      if (allScenes.length > 0) {
        const currentExists = allScenes.some(s => s.id === selectedSceneId)
        if (!currentExists || !selectedSceneId) {
          setSelectedSceneId(allScenes[0].id)
        }
      }
      isFirstDataLoad.current = false
    }
  }, [chaptersData, selectedSceneId])

  const selectedScene = useMemo(
    () => chaptersData.flatMap(c => c.scenes).find(s => s.id === selectedSceneId) || null,
    [chaptersData, selectedSceneId],
  )

  useEffect(() => {
    setEditScene(selectedScene ? { ...selectedScene } : null)
    setHasUnsaved(false)
  }, [selectedScene])

  useEffect(() => {
    if (!hasUnsaved) return
    const handler = (e: BeforeUnloadEvent) => {
      e.preventDefault()
      e.returnValue = ''
    }
    window.addEventListener('beforeunload', handler)
    return () => window.removeEventListener('beforeunload', handler)
  }, [hasUnsaved])

  useEffect(() => {
    if (genTaskId && genProgressHook.status === 'completed') {
      setGenTaskId(null)
      refetchScenes()
      queryClient.invalidateQueries({ queryKey: ['scenes', projectId] })
      updateAgent('创作Agent', { status: 'idle', currentTask: undefined })
      notification.success({ message: '场景生成完成', placement: 'topRight' })
    }
    if (genTaskId && ['failed', 'timeout'].includes(genProgressHook.status)) {
      setGenTaskId(null)
      updateAgent('创作Agent', { status: 'idle', currentTask: undefined })
      notification.error({ message: '场景生成失败', description: '任务执行失败或超时', placement: 'topRight' })
    }
  }, [genProgressHook.status, genTaskId, notification, projectId, queryClient, refetchScenes, updateAgent])

  useEffect(() => {
    if (auditTaskId && auditProgressHook.status === 'completed') {
      setAuditTaskId(null)
      refetchScenes().then(() => {
        queryClient.invalidateQueries({ queryKey: ['scenes', projectId] }).then(() => {
          const updatedScenes = queryClient.getQueryData<Scene[]>(['scenes', projectId])
          if (updatedScenes && selectedSceneId) {
            const updated = updatedScenes.find((s: Scene) => s.id === selectedSceneId)
            if (updated) {
              const auditReports = Array.isArray(updated.audit_reports)
                ? (updated.audit_reports as AuditResult[])
                : []
              const latest = auditReports[auditReports.length - 1]
              if (latest) {
                if (latest.overall_result === 'fail') {
                  const newReject = rejectCount + 1
                  setRejectCount(newReject)
                  notification.warning({
                    message: '审计封驳',
                    description: `未通过审计，第${newReject}次封驳`,
                    placement: 'topRight',
                  })
                  if (newReject >= 3) {
                    setShowRejectModal(true)
                    setRejectCount(0)
                  }
                } else {
                  setRejectCount(0)
                  notification.success({
                    message: '审计通过',
                    description: '场景符合质量标准',
                    placement: 'topRight',
                  })
                }
              }
            }
          }
        })
      })
      updateAgent('审计Agent', { status: 'idle', currentTask: undefined })
    }
    if (auditTaskId && ['failed', 'timeout'].includes(auditProgressHook.status)) {
      setAuditTaskId(null)
      updateAgent('审计Agent', { status: 'idle', currentTask: undefined })
      notification.error({ message: '审计失败', description: '任务执行失败或超时', placement: 'topRight' })
    }
  }, [auditProgressHook.status, auditTaskId, notification, projectId, queryClient, refetchScenes, rejectCount, selectedSceneId, updateAgent])

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 's') {
        e.preventDefault()
        const pid = projectIdRef.current
        const scene = editSceneRef.current
        const dirty = hasUnsavedRef.current
        if (pid && scene && dirty) {
          saveMutation.mutate(scene)
        }
      }
      if (e.key === 'Escape') {
        if (showVersionPanel) setShowVersionPanel(false)
        if (showRejectModal) setShowRejectModal(false)
        if (confirmFinalize) setConfirmFinalize(null)
      }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [showVersionPanel, showRejectModal, confirmFinalize])

  const selectScene = useCallback(
    (id: string) => {
      if (hasUnsaved && editScene) {
        Modal.confirm({
          title: '未保存的更改',
          content: '当前场景有未保存的修改，确定要切换吗？',
          onOk: () => {
            setSelectedSceneId(id)
            setHasUnsaved(false)
          },
        })
      } else {
        setSelectedSceneId(id)
        setHasUnsaved(false)
      }
    },
    [hasUnsaved, editScene],
  )

  const markUnsaved = useCallback(() => setHasUnsaved(true), [])

  const saveMutation = useMutation({
    mutationFn: (scene: SceneData) => {
      savingRef.current = true
      const payload = buildScenePatchPayload(scene)
      return scenesApi.update(projectId, scene.id, payload as Partial<Scene>)
    },
    onSuccess: (_data, scene) => {
      setHasUnsaved(false)
      savingRef.current = false
      queryClient.invalidateQueries({ queryKey: ['scenes', projectId] })
      eventBus.emit(DataEvents.SCENE_UPDATED, { sceneId: scene.id })
    },
    onError: (err: any) => {
      savingRef.current = false
      notification.error({
        message: '保存失败',
        description: err?.detail || err?.message || '请稍后重试',
        placement: 'topRight',
      })
    },
  })

  useEffect(() => {
    const unsubs = [
      eventBus.on(DataEvents.CHARACTER_CREATED, () => {
        queryClient.invalidateQueries({ queryKey: ['characters', projectId] })
      }),
      eventBus.on(DataEvents.CHARACTER_UPDATED, () => {
        queryClient.invalidateQueries({ queryKey: ['characters', projectId] })
      }),
      eventBus.on(DataEvents.CHAPTER_CREATED, () => {
        queryClient.invalidateQueries({ queryKey: ['chapters', projectId] })
      }),
      eventBus.on(DataEvents.CHAPTER_UPDATED, () => {
        queryClient.invalidateQueries({ queryKey: ['chapters', projectId] })
      }),
      eventBus.on(DataEvents.PROJECT_SWITCHED, () => {
        refetchChapters()
        refetchScenes()
      }),
    ]
    return () => unsubs.forEach((unsub) => unsub())
  }, [projectId, queryClient, refetchChapters, refetchScenes])

  const handleSave = useCallback(() => {
    if (autoSaveTimerRef.current) clearTimeout(autoSaveTimerRef.current)
    const scene = editSceneRef.current
    const dirty = hasUnsavedRef.current
    if (!scene || !dirty || savingRef.current) return
    saveMutation.mutate(scene)
  }, [])

  const updateField = useCallback(
    <K extends keyof SceneData>(key: K, value: SceneData[K]) => {
      if (!editScene) return
      setEditScene({ ...editScene, [key]: value })
      markUnsaved()
      if (autoSaveTimerRef.current) clearTimeout(autoSaveTimerRef.current)
      autoSaveTimerRef.current = setTimeout(() => {
        if (savingRef.current) return
        const pid = projectIdRef.current
        const scene = editSceneRef.current
        if (pid && scene) {
          saveMutation.mutate(scene)
        }
      }, 3000)
    },
    [editScene, markUnsaved],
  )

  const handleAIGenerate = useCallback(async () => {
    if (!selectedScene || isGenerating) return
    updateAgent('创作Agent', { status: 'busy', currentTask: '生成场景' })
    eventBus.emit(DataEvents.AI_GENERATION_STARTED, { sceneId: selectedScene.id })
    try {
      const result = await api.post<{ task_id: string }>('/ai/projects/' + projectId + '/scenes/' + selectedScene.id + '/generate', {
        requirements: genRequirements || '',
      })
      setGenTaskId(result.task_id)
      notification.info({ message: '已进入生成队列', placement: 'topRight' })
    } catch (err: any) {
      const errDetail = err?.response?.data?.detail || err?.detail || err?.message || '请稍后重试'
      notification.error({
        message: 'AI 生成失败',
        description: String(errDetail).slice(0, 200),
        placement: 'topRight',
        duration: 6,
      })
      updateAgent('创作Agent', { status: 'idle', currentTask: undefined })
    }
  }, [selectedScene, isGenerating, updateAgent, projectId, genRequirements, notification])

  const handleCancelGenerate = useCallback(async () => {
    await genProgressHook.cancelTask()
    setGenTaskId(null)
    updateAgent('创作Agent', { status: 'idle', currentTask: undefined })
  }, [genProgressHook, updateAgent])

  const handleAudit = useCallback(async () => {
    if (!selectedScene || isAuditing) return
    updateAgent('审计Agent', { status: 'busy', currentTask: '审计场景' })
    eventBus.emit(DataEvents.AI_AUDIT_STARTED, { sceneId: selectedScene.id })
    try {
      const result = await api.post<{ task_id: string }>('/ai/projects/' + projectId + '/scenes/' + selectedScene.id + '/audit')
      setAuditTaskId(result.task_id)
      notification.info({ message: '已进入审计队列', placement: 'topRight' })
    } catch (err: any) {
      notification.error({
        message: '审计提交失败',
        description: err?.detail || err?.message || '请稍后重试',
        placement: 'topRight',
      })
      updateAgent('审计Agent', { status: 'idle', currentTask: undefined })
    }
  }, [selectedScene, isAuditing, updateAgent, projectId, notification])

  const finalizeMutation = useMutation({
    mutationFn: (sceneId: string) =>
      api.post<Scene>(`/projects/${projectId}/scenes/${sceneId}/finalize`),
    onSuccess: (_data, sceneId) => {
      queryClient.invalidateQueries({ queryKey: ['scenes', projectId] })
      eventBus.emit(DataEvents.SCENE_FINALIZED, { sceneId })
      notification.success({ message: '已定稿', placement: 'topRight' })
      setConfirmFinalize(null)
    },
    onError: (err: any) => {
      notification.error({
        message: '定稿失败',
        description: err?.detail || err?.message || '请稍后重试',
        placement: 'topRight',
      })
    },
  })

  const handleFinalize = useCallback(
    (sceneId: string) => {
      finalizeMutation.mutate(sceneId)
    },
    [finalizeMutation],
  )

  const addDialogue = useCallback(() => {
    const newLine: DialogueLine = {
      id: 'd' + Date.now(),
      character_id: '',
      character_name: '',
      text: '',
      subtext: '',
    }
    updateField('dialogue', [...(editScene?.dialogue || []), newLine])
  }, [editScene, updateField])

  const removeDialogue = useCallback(
    (idx: number) => {
      updateField('dialogue', editScene?.dialogue.filter((_, i) => i !== idx) || [])
    },
    [editScene, updateField],
  )

  const updateDialogue = useCallback(
    (idx: number, key: keyof DialogueLine, val: string) => {
      const arr = [...(editScene?.dialogue || [])]
      if (idx < 0 || idx >= arr.length) return
      ;(arr[idx] as any)[key] = val
      updateField('dialogue', arr)
    },
    [editScene, updateField],
  )

  const moveDialogue = useCallback(
    (from: number, to: number) => {
      const arr = [...(editScene?.dialogue || [])]
      if (arr.length === 0 || from < 0 || from >= arr.length || to < 0 || to >= arr.length) return
      const [item] = arr.splice(from, 1)
      arr.splice(to, 0, item)
      updateField('dialogue', arr)
    },
    [editScene, updateField],
  )

  const addAction = useCallback(
    () => updateField('actions', [...(editScene?.actions || []), '']),
    [editScene, updateField],
  )

  const removeAction = useCallback(
    (idx: number) => updateField('actions', editScene?.actions.filter((_, i) => i !== idx) || []),
    [editScene, updateField],
  )

  const updateAction = useCallback(
    (idx: number, val: string) => {
      const arr = [...(editScene?.actions || [])]
      if (idx < 0 || idx >= arr.length) return
      arr[idx] = val
      updateField('actions', arr)
    },
    [editScene, updateField],
  )

  const addChoice = useCallback(() => {
    const nc: ChoiceOption = {
      id: 'ch' + Date.now(),
      text: '',
      consequence: '',
      jump_scene: '',
      hidden: false,
      hidden_condition: '',
    }
    updateField('choices', [...(editScene?.choices || []), nc])
  }, [editScene, updateField])

  const removeChoice = useCallback(
    (idx: number) => updateField('choices', editScene?.choices.filter((_, i) => i !== idx) || []),
    [editScene, updateField],
  )

  const updateChoice = useCallback(
    (idx: number, key: keyof ChoiceOption, val: any) => {
      const arr = [...(editScene?.choices || [])]
      if (idx < 0 || idx >= arr.length) return
      ;(arr[idx] as any)[key] = val
      updateField('choices', arr)
    },
    [editScene, updateField],
  )

  const addForeshadowOp = useCallback(() => {
    const nfo: ForeshadowOp = {
      fs_id: '',
      fs_code: '',
      fs_name: '',
      op_type: 'plant',
      description: '',
      completed: false,
    }
    updateField('foreshadow_ops', [...(editScene?.foreshadow_ops || []), nfo])
  }, [editScene, updateField])

  const removeForeshadowOp = useCallback(
    (idx: number) =>
      updateField('foreshadow_ops', editScene?.foreshadow_ops.filter((_, i) => i !== idx) || []),
    [editScene, updateField],
  )

  const updateForeshadowOp = useCallback(
    (idx: number, key: keyof ForeshadowOp, val: any) => {
      const arr = [...(editScene?.foreshadow_ops || [])]
      if (idx < 0 || idx >= arr.length) return
      ;(arr[idx] as any)[key] = val
      updateField('foreshadow_ops', arr)
    },
    [editScene, updateField],
  )

  const characterOptions = useMemo(
    () => characters.map(c => ({ value: c.name, label: c.name })),
    [characters],
  )

  const incompleteForeshadows = editScene?.foreshadow_ops.filter(f => !f.completed) || []
  const latestAudit = (selectedScene?.audit_reports?.length ? selectedScene.audit_reports[selectedScene.audit_reports.length - 1] : null) || null

  const dataLoading = chaptersLoading || scenesLoading
  const dataError = chaptersError || scenesError

  if (!currentProject) {
    return (
      <div className="h-full overflow-auto">
        <h1 className="text-2xl font-bold mb-6">场景工作台</h1>
        <Card className="text-center py-12">
          <Empty description={<span className="text-gray-400">请先创建或选择一个项目</span>} />
        </Card>
      </div>
    )
  }

  if (dataLoading) {
    return (
      <div className="h-full overflow-auto">
        <h1 className="text-2xl font-bold mb-6">场景工作台</h1>
        <Card className="text-center py-12">
          <Spin size="large">
            <div className="p-8 text-gray-400">加载场景数据...</div>
          </Spin>
        </Card>
      </div>
    )
  }

  if (dataError) {
    return (
      <div className="h-full overflow-auto">
        <h1 className="text-2xl font-bold mb-6">场景工作台</h1>
        <Result
          status="error"
          title="数据加载失败"
          subTitle="无法加载场景数据，请检查网络连接后重试"
          extra={[
            <Button
              key="retry"
              type="primary"
              icon={<ReloadOutlined />}
              onClick={() => {
                refetchChapters()
                refetchScenes()
              }}
            >
              重新加载
            </Button>,
          ]}
        />
      </div>
    )
  }

  if (chaptersData.length === 0) {
    return (
      <div className="h-full overflow-auto">
        <h1 className="text-2xl font-bold mb-6">场景工作台</h1>
        <Card className="text-center py-12">
          <Empty
            description={
              <span className="text-gray-400">暂无章节和场景数据，请先在章节大纲中创建内容</span>
            }
          />
        </Card>
      </div>
    )
  }

  return (
    <div
      className={`h-full flex flex-col ${
        isFullscreen ? 'fixed inset-0 z-50 bg-white dark:bg-slate-900' : ''
      }`}
    >
      <div className="flex items-center justify-between mb-2 shrink-0">
        <h1 className="text-2xl font-bold m-0">场景工作台</h1>
        <Space>
          <Button
            size="small"
            icon={isFullscreen ? <FullscreenExitOutlined /> : <FullscreenOutlined />}
            onClick={() => setIsFullscreen(!isFullscreen)}
          />
        </Space>
      </div>

      <div className="flex gap-2 flex-1 min-h-0">
        <div className="w-[25%] min-w-[240px] shrink-0 flex flex-col gap-1">
          <Card size="small" className="shrink-0">
            <Button block icon={<PlusOutlined />} size="small"
              onClick={() => {
                const defaultCh = chaptersData.length > 0 ? chaptersData[0] : null
                const nextCode = defaultCh
                  ? `${defaultCh.chapter_id.slice(0, 4).toUpperCase()}-S${String(defaultCh.scenes.length + 1).padStart(2, '0')}`
                  : `SC-${String(scenes.length + 1).padStart(3, '0')}`
                setNewSceneForm({
                  chapter_id: defaultCh?.chapter_id || '',
                  scene_code: nextCode,
                  scene_type: 'dialogue',
                  location: '',
                  weather: '',
                  emotion_level: 5,
                  characters_involved: [],
                })
                setCreateModalOpen(true)
              }}
            >
              新建场景
            </Button>
          </Card>

          <Modal
            title="创建新场景"
            open={createModalOpen}
            onCancel={() => setCreateModalOpen(false)}
            onOk={async () => {
              if (!currentProject?.id || !newSceneForm.chapter_id) {
                notification.warning({ message: '请选择所属章节', placement: 'topRight' })
                return
              }
              try {
                const newScene = await scenesApi.create(currentProject.id, {
                  scene_code: newSceneForm.scene_code,
                  chapter_id: newSceneForm.chapter_id,
                  scene_type: newSceneForm.scene_type,
                  location: newSceneForm.location || undefined,
                  weather: newSceneForm.weather || undefined,
                  emotion_level: newSceneForm.emotion_level,
                  characters_involved: newSceneForm.characters_involved,
                  status: 'draft',
                } as any)
                await refetchScenes()
                setSelectedSceneId(newScene.id)
                setCreateModalOpen(false)
                eventBus.emit(DataEvents.SCENE_CREATED, { sceneId: newScene.id })
                notification.success({ message: '场景已创建', placement: 'topRight' })
              } catch (e) {
                notification.error({
                  message: '创建失败',
                  description: (e as Error).message || '请检查网络连接',
                  placement: 'topRight',
                })
              }
            }}
            okText="创建"
            cancelText="取消"
            destroyOnHidden
          >
            <Space direction="vertical" className="w-full" size="middle">
              <div>
                <div className="text-xs text-gray-500 mb-1">所属章节 <span className="text-red-400">*</span></div>
                <Select
                  className="w-full"
                  placeholder="选择章节"
                  value={newSceneForm.chapter_id || undefined}
                  onChange={val => {
                    const ch = chaptersData.find(c => c.chapter_id === val)
                    const nextCode = ch
                      ? `CH${String(ch.chapter_number).padStart(2, '0')}-S${String(ch.scenes.length + 1).padStart(2, '0')}`
                      : newSceneForm.scene_code
                    setNewSceneForm(prev => ({ ...prev, chapter_id: val, scene_code: nextCode }))
                  }}
                  options={chaptersData.map(ch => ({
                    label: `第${ch.chapter_number}章 ${ch.title || '未命名'}（${ch.scenes.length}个场景）`,
                    value: ch.chapter_id,
                  }))}
                />
              </div>
              <Row gutter={12}>
                <Col span={12}>
                  <div className="text-xs text-gray-500 mb-1">场景编号</div>
                  <Input
                    value={newSceneForm.scene_code}
                    onChange={e => setNewSceneForm(prev => ({ ...prev, scene_code: e.target.value }))}
                    placeholder="如 CH01-S01"
                  />
                </Col>
                <Col span={12}>
                  <div className="text-xs text-gray-500 mb-1">场景类型</div>
                  <Select
                    className="w-full"
                    value={newSceneForm.scene_type}
                    onChange={val => setNewSceneForm(prev => ({ ...prev, scene_type: val }))}
                    options={SCENE_TYPES.map(t => ({ label: SCENE_TYPE_LABELS[t] || t, value: t }))}
                  />
                </Col>
              </Row>
              <Row gutter={12}>
                <Col span={12}>
                  <div className="text-xs text-gray-500 mb-1">地点</div>
                  <Input
                    placeholder="如：城主府正厅"
                    value={newSceneForm.location}
                    onChange={e => setNewSceneForm(prev => ({ ...prev, location: e.target.value }))}
                  />
                </Col>
                <Col span={12}>
                  <div className="text-xs text-gray-500 mb-1">天气</div>
                  <Input
                    placeholder="如：暴雨、晴夜"
                    value={newSceneForm.weather}
                    onChange={e => setNewSceneForm(prev => ({ ...prev, weather: e.target.value }))}
                  />
                </Col>
              </Row>
              <div>
                <div className="text-xs text-gray-500 mb-1">情感强度：{newSceneForm.emotion_level}/10</div>
                <Slider
                  min={1} max={10}
                  value={newSceneForm.emotion_level}
                  onChange={val => setNewSceneForm(prev => ({ ...prev, emotion_level: val }))}
                  marks={{ 1: '平淡', 5: '中等', 10: '激烈' }}
                />
              </div>
              <div>
                <div className="text-xs text-gray-500 mb-1">出场角色</div>
                <Select
                  mode="multiple"
                  className="w-full"
                  placeholder="选择本场景出场的角色（可多选）"
                  value={newSceneForm.characters_involved}
                  onChange={val => setNewSceneForm(prev => ({ ...prev, characters_involved: val }))}
                  options={characters.map(c => ({
                    label: `${c.name}（${c.role_type || '未分类'}）`,
                    value: c.id,
                  }))}
                  notFoundContent={characters.length === 0 ? '暂无角色，请先在角色管理中添加' : '无匹配角色'}
                />
              </div>
            </Space>
          </Modal>
          <div
            ref={sidebarRef}
            className="flex-1 overflow-auto scrollbar-thin"
            onScroll={handleSidebarScroll}
            style={{ position: 'relative' }}
          >
            <div style={{ height: totalHeight, position: 'relative' }}>
              <div style={{ position: 'absolute', top: visibleRows.offsetY, left: 0, right: 0 }}>
                {visibleRows.rows.map(row => {
                  if (row.type === 'chapter') {
                    const ch = chaptersData[row.chIdx]
                    if (!ch) return null
                    const completed = ch.scenes.filter(s => s.status === 'final').length
                    const isExpanded = expandedChapterIds.has(ch.chapter_id)
                    return (
                      <div
                        key={row.key}
                        onClick={() => toggleChapter(ch.chapter_id)}
                        className="flex items-center gap-2 py-1.5 px-2 cursor-pointer hover:bg-gray-50 dark:hover:bg-slate-800 rounded transition-colors"
                        style={{ height: CHAPTER_H }}
                      >
                        <span className="text-[10px] text-gray-400 transition-transform duration-150" style={{ transform: isExpanded ? 'rotate(90deg)' : 'rotate(0deg)' }}>
                          ▶
                        </span>
                        <span className="text-sm font-semibold">第{ch.chapter_number}章</span>
                        <span className="text-xs text-gray-400 truncate flex-1">{ch.title}</span>
                        <Tag className="text-[10px]">{completed}/{ch.scenes.length}</Tag>
                      </div>
                    )
                  }
                  const chData = chaptersData[row.chIdx]
                  if (!chData || row.scIdx === undefined) return null
                  const sc = chData.scenes[row.scIdx]
                  if (!sc) return null
                  const sic = SCENE_STATUS_ICON[sc.status] || SCENE_STATUS_ICON.draft
                  return (
                    <div
                      key={sc.id}
                      onClick={() => selectScene(sc.id)}
                      className={`flex items-center gap-2 px-3 py-1 rounded cursor-pointer transition-all text-sm ${
                        selectedSceneId === sc.id
                          ? 'bg-primary-50 dark:bg-primary-900/20'
                          : 'hover:bg-gray-50 dark:hover:bg-slate-800'
                      }`}
                      style={{ height: SCENE_H, marginLeft: 8 }}
                    >
                      <span className="text-[10px] font-mono text-gray-400 w-[58px] shrink-0">
                        {sc.scene_code}
                      </span>
                      {sc.is_wow_moment && (
                        <StarOutlined className="text-amber-400 text-xs" />
                      )}
                      <span className="text-xs" style={{ color: sic.color }}>
                        {sic.label}
                      </span>
                      <div className="flex-1 min-w-0">
                        <EmotionChart level={sc.emotion_level} size="sm" showLabel={false} />
                      </div>
                    </div>
                  )
                })}
              </div>
            </div>
          </div>
        </div>

        <div className="flex-1 flex flex-col min-w-0 gap-2 overflow-auto">
          {!editScene ? (
            <Card className="flex-1 flex items-center justify-center">
              <Empty description="选择左侧场景开始编辑" />
            </Card>
          ) : (
            <>
              <Card size="small" className="shrink-0">
                <div className="flex flex-wrap items-center gap-2">
                  <Input
                    size="small"
                    className="w-[100px]"
                    value={editScene.scene_code}
                    onChange={e => updateField('scene_code', e.target.value)}
                  />
                  <Select
                    size="small"
                    className="w-[80px]"
                    value={editScene.scene_type}
                    onChange={v => updateField('scene_type', v)}
                    options={SCENE_TYPES.map(t => ({ value: t, label: SCENE_TYPE_LABELS[t] }))}
                  />
                  <Input
                    size="small"
                    className="w-[100px]"
                    placeholder="地点"
                    value={editScene.location}
                    onChange={e => updateField('location', e.target.value)}
                  />
                  <Input
                    size="small"
                    className="w-[60px]"
                    placeholder="天气"
                    value={editScene.weather}
                    onChange={e => updateField('weather', e.target.value)}
                  />
                  <div className="flex items-center gap-1 text-xs text-gray-400">
                    <span>情感</span>
                    <Slider
                      className="w-[80px] scene-slider"
                      min={0}
                      max={10}
                      value={editScene.emotion_level}
                      onChange={v => updateField('emotion_level', v)}
                    />
                    <span className="font-semibold">{editScene.emotion_level}</span>
                  </div>
                  <div className="flex items-center gap-1 text-xs">
                    <span className="text-gray-400">出场</span>
                    <Select
                      size="small"
                      mode="multiple"
                      className="w-[160px]"
                      value={editScene.characters_involved}
                      onChange={v => updateField('characters_involved', v)}
                      options={characterOptions}
                    />
                  </div>
                  <div className="flex items-center gap-1 text-xs">
                    <StarOutlined className="text-amber-400" />
                    <Switch
                      size="small"
                      checked={editScene.is_wow_moment}
                      onChange={v => updateField('is_wow_moment', v)}
                    />
                  </div>
                  <Tag
                    color={
                      editScene.status === 'final'
                        ? 'green'
                        : editScene.status === 'rejected'
                          ? 'red'
                          : editScene.status === 'in_review'
                            ? 'blue'
                            : editScene.status === 'passed'
                            ? 'blue'
                            : 'default'
                    }
                  >
                    {editScene.status === 'final'
                      ? '已定稿'
                      : editScene.status === 'rejected'
                        ? '已封驳'
                        : editScene.status === 'in_review'
                          ? '审计中'
                          : editScene.status === 'passed'
                          ? '审计中'
                          : '草稿'}
                  </Tag>
                  {hasUnsaved && <Tag color="orange">未保存</Tag>}
                </div>
              </Card>

              {(() => {
                const sceneChapter = chapters.find(c => c.id === editScene.chapter_id)
                if (!sceneChapter) return null
                return (
                  <Card size="small" className="shrink-0 bg-blue-50/50 dark:bg-blue-900/10 border-blue-100 dark:border-blue-900/30">
                    <div className="flex items-center gap-3 text-xs flex-wrap">
                      <Tag color="blue" className="text-[11px]">第{sceneChapter.chapter_number}章</Tag>
                      <span className="text-gray-700 dark:text-gray-300 font-medium">{sceneChapter.title || '未命名'}</span>
                      {sceneChapter.core_conflict && (
                        <>
                          <span className="text-gray-300">|</span>
                          <span className="text-gray-500">冲突：</span>
                          <span className="text-gray-700 dark:text-gray-300">{sceneChapter.core_conflict}</span>
                        </>
                      )}
                      {sceneChapter.emotion_target != null && (
                        <>
                          <span className="text-gray-300">|</span>
                          <span className="text-gray-500">情感目标：</span>
                          <span>{sceneChapter.emotion_target}/10</span>
                        </>
                      )}
                      {Array.isArray(sceneChapter.key_turning_points) && sceneChapter.key_turning_points.length > 0 && (
                        <>
                          <span className="text-gray-300">|</span>
                          <span className="text-gray-500">转折点：</span>
                          <span className="text-amber-600 dark:text-amber-400">
                            {sceneChapter.key_turning_points.map((tp: any) => typeof tp === 'string' ? tp : tp?.description || '').filter(Boolean).join(' → ')}
                          </span>
                        </>
                      )}
                    </div>
                  </Card>
                )
              })()}

              <div className="flex gap-2 flex-1 min-h-0">
                <div className="flex-1 flex flex-col gap-2 min-w-0 overflow-hidden">
                  <Card
                    size="small"
                    className="flex-1 overflow-hidden"
                    styles={{ body: { height: '100%', overflow: 'auto' } }}
                    tabProps={{ size: 'small' }}
                    tabList={[
                      { key: 'narration', tab: '场景描述' },
                      { key: 'dialogue', tab: `对白 (${editScene.dialogue.length})` },
                      { key: 'actions', tab: `动作 (${editScene.actions.length})` },
                      { key: 'choices', tab: `选择 (${editScene.choices.length})` },
                    ]}
                    activeTabKey={activeTab}
                    onTabChange={setActiveTab}
                  >
                    {activeTab === 'narration' && (
                      <TextArea
                        className="text-[15px] leading-relaxed"
                        style={{ lineHeight: 1.8, minHeight: '100%' }}
                        value={editScene.narration}
                        onChange={e => updateField('narration', e.target.value)}
                        placeholder="输入场景描述...环境、氛围、角色状态、心理活动"
                        data-scene-editor="narration"
                      />
                    )}
                    {activeTab === 'dialogue' && (
                      <div className="space-y-2">
                        {editScene.dialogue.map((d, i) => (
                          <div
                            key={d.id}
                            className="flex gap-1 items-start p-2 bg-gray-50 dark:bg-slate-800 rounded group"
                          >
                            <div className="flex flex-col items-center gap-1 shrink-0 pt-1">
                              <button
                                className="text-[10px] text-gray-300 hover:text-gray-500 cursor-pointer border-none bg-transparent"
                                onClick={() => moveDialogue(i, Math.max(0, i - 1))}
                              >
                                ▲
                              </button>
                              <button
                                className="text-[10px] text-gray-300 hover:text-gray-500 cursor-pointer border-none bg-transparent"
                                onClick={() =>
                                  moveDialogue(i, Math.min(editScene.dialogue.length - 1, i + 1))
                                }
                              >
                                ▼
                              </button>
                            </div>
                            <Select
                              size="small"
                              className="w-[80px]"
                              value={d.character_name || undefined}
                              onChange={v => updateDialogue(i, 'character_name', v)}
                              options={characterOptions}
                            />
                            <div className="flex-1 space-y-1">
                              <Input
                                size="small"
                                value={d.text}
                                onChange={e => updateDialogue(i, 'text', e.target.value)}
                                placeholder="对白文本"
                              />
                              <Input
                                size="small"
                                className="text-xs text-gray-400"
                                value={d.subtext}
                                onChange={e => updateDialogue(i, 'subtext', e.target.value)}
                                placeholder="潜台词（可选）"
                              />
                            </div>
                            <Button
                              size="small"
                              type="text"
                              danger
                              icon={<DeleteOutlined />}
                              className="opacity-0 group-hover:opacity-100"
                              onClick={() => removeDialogue(i)}
                            />
                          </div>
                        ))}
                        <Button size="small" block icon={<PlusCircleOutlined />} onClick={addDialogue}>
                          添加对白
                        </Button>
                      </div>
                    )}
                    {activeTab === 'actions' && (
                      <div className="space-y-1">
                        {editScene.actions.map((a, i) => (
                          <div key={`action-${i}`} className="flex items-center gap-1">
                            <Input
                              size="small"
                              value={a}
                              onChange={e => updateAction(i, e.target.value)}
                              placeholder={`动作 ${i + 1}`}
                            />
                            <Button
                              size="small"
                              type="text"
                              danger
                              icon={<MinusCircleOutlined />}
                              onClick={() => removeAction(i)}
                            />
                          </div>
                        ))}
                        <Button size="small" block icon={<PlusCircleOutlined />} onClick={addAction}>
                          添加动作
                        </Button>
                      </div>
                    )}
                    {activeTab === 'choices' && (
                      <div className="space-y-2">
                        {editScene.choices.map((ch, i) => (
                          <div
                            key={ch.id}
                            className="p-2 border border-gray-200 dark:border-slate-600 rounded space-y-1"
                          >
                            <div className="flex items-center gap-1">
                              <Input
                                size="small"
                                className="flex-1"
                                value={ch.text}
                                onChange={e => updateChoice(i, 'text', e.target.value)}
                                placeholder="选项文本"
                              />
                              <Button
                                size="small"
                                type="text"
                                danger
                                icon={<MinusCircleOutlined />}
                                onClick={() => removeChoice(i)}
                              />
                            </div>
                            <div className="flex gap-1">
                              <Input
                                size="small"
                                className="flex-1"
                                value={ch.consequence}
                                onChange={e => updateChoice(i, 'consequence', e.target.value)}
                                placeholder="后果描述"
                              />
                              <Input
                                size="small"
                                className="w-[100px]"
                                value={ch.jump_scene}
                                onChange={e => updateChoice(i, 'jump_scene', e.target.value)}
                                placeholder="跳转场景编号"
                              />
                            </div>
                            <div className="flex items-center gap-2">
                              <Switch
                                size="small"
                                checked={ch.hidden}
                                onChange={v => updateChoice(i, 'hidden', v)}
                              />
                              <span className="text-xs text-gray-400">隐藏选项</span>
                              {ch.hidden && (
                                <Input
                                  size="small"
                                  className="flex-1"
                                  value={ch.hidden_condition}
                                  onChange={e =>
                                    updateChoice(i, 'hidden_condition', e.target.value)
                                  }
                                  placeholder="前置条件"
                                />
                              )}
                            </div>
                          </div>
                        ))}
                        <Button size="small" block icon={<PlusCircleOutlined />} onClick={addChoice}>
                          添加选项
                        </Button>
                      </div>
                    )}
                  </Card>

                  <Collapse
                    size="small"
                    items={[
                      {
                        key: 'causal',
                        label: <span className="text-sm font-semibold">🔗 因果链</span>,
                        children: (
                          <div className="space-y-2">
                            {(
                              [
                                'precondition',
                                'catalyst',
                                'direct_result',
                                'indirect_result',
                                'long_term_result',
                              ] as const
                            ).map(f => (
                              <div key={f}>
                                <label className="text-xs text-gray-400 block mb-0.5 font-semibold">
                                  {f === 'precondition'
                                    ? '前置条件'
                                    : f === 'catalyst'
                                      ? '催化剂'
                                      : f === 'direct_result'
                                        ? '直接结果'
                                        : f === 'indirect_result'
                                          ? '间接结果'
                                          : '远期结果'}
                                </label>
                                <TextArea
                                  size="small"
                                  rows={2}
                                  value={editScene?.causal_chain?.[f] || ''}
                                  onChange={e =>
                                    updateField('causal_chain', {
                                      ...editScene.causal_chain,
                                      [f]: e.target.value,
                                    })
                                  }
                                />
                              </div>
                            ))}
                          </div>
                        ),
                      },
                    ]}
                  />
                </div>

                <Card
                  size="small"
                  className="w-[280px] shrink-0 overflow-auto"
                  title={<span className="text-sm">🎯 伏笔操作</span>}
                >
                  <div className="space-y-2">
                    {editScene?.foreshadow_ops.map((fo, i) => (
                      <div
                        key={fo.fs_id || `fo-${i}`}
                        className={`p-2 rounded border text-xs ${
                          fo.completed
                            ? 'border-gray-200 dark:border-slate-600'
                            : 'border-red-300 dark:border-red-700 bg-red-50 dark:bg-red-900/5'
                        }`}
                      >
                        <div className="flex items-center gap-1 mb-1">
                          <Select
                            size="small"
                            className="flex-1"
                            value={fo.op_type}
                            onChange={v => updateForeshadowOp(i, 'op_type', v)}
                            options={[
                              { value: 'plant', label: '🌱 植入' },
                              { value: 'reinforce', label: '🔄 强化' },
                              { value: 'reveal', label: '💡 回收' },
                            ]}
                          />
                          <Button
                            size="small"
                            type="text"
                            danger
                            icon={<MinusCircleOutlined />}
                            onClick={() => removeForeshadowOp(i)}
                          />
                        </div>
                        <Input
                          size="small"
                          className="mb-1"
                          value={fo.fs_name}
                          onChange={e => updateForeshadowOp(i, 'fs_name', e.target.value)}
                          placeholder="伏笔名称"
                        />
                        <Input
                          size="small"
                          value={fo.description}
                          onChange={e => updateForeshadowOp(i, 'description', e.target.value)}
                          placeholder="操作描述"
                        />
                      </div>
                    ))}
                    <Button
                      size="small"
                      block
                      icon={<PlusCircleOutlined />}
                      onClick={addForeshadowOp}
                    >
                      添加伏笔操作
                    </Button>
                  </div>
                  {incompleteForeshadows.length > 0 && (
                    <div className="mt-2 text-xs text-red-500 bg-red-50 dark:bg-red-900/10 p-2 rounded">
                      ⚠ {incompleteForeshadows.length} 个伏笔任务未完成
                    </div>
                  )}
                </Card>
              </div>

              <Card size="small" className="shrink-0">
                <Space direction="vertical" className="w-full" size="small">
                  <div className="flex items-center gap-2">
                    <Input
                      placeholder="额外要求（可选）：如武侠风、情感更激烈、角色对话更犀利..."
                      value={genRequirements}
                      onChange={e => setGenRequirements(e.target.value)}
                      size="small"
                      allowClear
                      className="flex-1"
                      prefix={<ThunderboltOutlined className="text-amber-500" />}
                      disabled={editScene.status === 'final'}
                    />
                  </div>
                  <div className="flex items-center gap-2 flex-wrap">
                  <Tooltip title="调用 AI 生成或补充场景内容">
                    <Button
                      icon={<RobotOutlined />}
                      type="primary"
                      loading={isGenerating}
                      onClick={handleAIGenerate}
                      size="small"
                      disabled={editScene.status === 'final'}
                    >
                      AI 生成
                    </Button>
                  </Tooltip>
                  {isGenerating && (
                    <div className="flex items-center gap-2">
                      <Progress
                        percent={genProgressHook.progress}
                        size="small"
                        className="w-[120px]"
                        strokeColor="#3b82f6"
                      />
                      <span className="text-xs text-gray-400">
                        预计 {genProgressHook.estimatedTime}
                      </span>
                      <Button
                        size="small"
                        danger
                        onClick={handleCancelGenerate}
                        className="text-xs"
                      >
                        取消
                      </Button>
                    </div>
                  )}
                  <Tooltip title="提交场景进行自动化质量审计">
                    <Button
                      icon={<AuditOutlined />}
                      loading={isAuditing}
                      onClick={handleAudit}
                      size="small"
                      type="primary"
                      ghost
                      disabled={editScene.status === 'final'}
                    >
                      提交审计
                    </Button>
                  </Tooltip>
                  {isAuditing && (
                    <div className="flex items-center gap-2">
                      <Progress
                        percent={auditProgressHook.progress}
                        size="small"
                        className="w-[120px]"
                        strokeColor="#10b981"
                      />
                      <span className="text-xs text-gray-400">
                        预计 {auditProgressHook.estimatedTime}
                      </span>
                    </div>
                  )}
                  <Button icon={<EditOutlined />} size="small" onClick={() => {
                    const editorEl = document.querySelector('[data-scene-editor]') as HTMLElement
                    if (editorEl) {
                      editorEl.scrollIntoView({ behavior: 'smooth', block: 'center' })
                      const textArea = editorEl.querySelector('textarea') as HTMLTextAreaElement
                      if (textArea) textArea.focus()
                    }
                  }}>
                    人工编辑
                  </Button>
                  <Button
                    icon={<CheckCircleOutlined />}
                    size="small"
                    type="primary"
                    disabled={
                      editScene.status === 'final' || editScene.status === 'draft'
                    }
                    onClick={() => {
                      if (editScene.status === 'final') {
                        notification.warning({
                          message: '已定稿',
                          description: '修改将创建新版本',
                          placement: 'topRight',
                        })
                      } else {
                        setConfirmFinalize(editScene.id)
                      }
                    }}
                  >
                    定稿
                  </Button>
                  <Button
                    icon={<UndoOutlined />}
                    size="small"
                    disabled={isGenerating}
                    onClick={handleAIGenerate}
                  >
                    重新生成
                  </Button>
                  <Button
                    icon={<HistoryOutlined />}
                    size="small"
                    onClick={() => setShowVersionPanel(true)}
                  >
                    版本历史
                  </Button>
                  <Button
                    icon={<SaveOutlined />}
                    size="small"
                    type={hasUnsaved ? 'primary' : 'default'}
                    onClick={handleSave}
                    loading={saveMutation.isPending}
                  >
                    保存
                  </Button>
                </div>
                </Space>
              </Card>

              {latestAudit && (
                <Collapse
                  size="small"
                  defaultActiveKey={
                    latestAudit.overall_result === 'fail' ? ['audit'] : []
                  }
                  items={[
                    {
                      key: 'audit',
                      label: (
                        <div className="flex items-center gap-2 text-sm">
                          <AuditOutlined />
                          <span>审计结果</span>
                          <Tag
                            color={
                              latestAudit.overall_result === 'pass' ? 'green' : 'red'
                            }
                          >
                            {latestAudit.overall_result === 'pass' ? '✓ 通过' : '✗ 封驳'}
                          </Tag>
                        </div>
                      ),
                      children: (
                        <div className="space-y-3">
                          <div>
                            <div className="text-xs text-gray-400 font-semibold mb-1">
                              程序化检测
                            </div>
                            <div className="grid grid-cols-2 gap-1">
                              {(latestAudit.checker_results || []).map((c, i) => (
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
                                  <span>{c.name}</span>
                                  <span className="text-gray-400">{c.detail}</span>
                                </div>
                              ))}
                            </div>
                          </div>
                          <div>
                            <div className="text-xs text-gray-400 font-semibold mb-1">
                              LLM审计
                            </div>
                            <Row gutter={[4, 4]}>
                              {(latestAudit.llm_results || []).map((l, i) => (
                                <Col span={8} key={i}>
                                  <div className="bg-gray-50 dark:bg-slate-800 rounded p-1.5 text-center">
                                    <div className="text-xs text-gray-500">{l.name}</div>
                                    <div className="text-lg font-bold text-primary-600">
                                      {l.score}
                                    </div>
                                    <div className="text-[10px] text-gray-400">
                                      {l.detail}
                                    </div>
                                  </div>
                                </Col>
                              ))}
                            </Row>
                          </div>
                          {(latestAudit.issues || []).length > 0 && (
                            <div className="bg-red-50 dark:bg-red-900/10 border border-red-200 dark:border-red-800 rounded p-2">
                              <div className="text-xs text-red-600 font-semibold mb-1">
                                问题列表
                              </div>
                              {(latestAudit.issues || []).map((issue, i) => (
                                <div key={i} className="text-xs text-red-500">
                                  · {issue}
                                </div>
                              ))}
                            </div>
                          )}
                          {(latestAudit.suggestions || []).length > 0 && (
                            <div className="text-xs text-gray-600 dark:text-gray-400 space-y-0.5">
                              <div className="font-semibold">修改建议</div>
                              {(latestAudit.suggestions || []).map((s, i) => (
                                <div key={i}>· {s}</div>
                              ))}
                            </div>
                          )}
                        </div>
                      ),
                    },
                  ]}
                />
              )}
            </>
          )}
        </div>
      </div>

      <ConfirmDialog
        open={confirmFinalize !== null}
        title="确认定稿"
        content="定稿后将写入剧本Layer 1/2/5，该操作不可撤销。确认定稿？"
        okText="确认定稿"
        onOk={() => confirmFinalize && handleFinalize(confirmFinalize)}
        onCancel={() => setConfirmFinalize(null)}
      />

      <Modal
        open={showRejectModal}
        title={
          <div className="flex items-center gap-2 text-red-500">
            <ExclamationCircleOutlined />
            需要人类介入
          </div>
        }
        footer={
          <Button type="primary" onClick={() => setShowRejectModal(false)}>
            我知道了
          </Button>
        }
        onCancel={() => setShowRejectModal(false)}
      >
        <div className="space-y-2 text-sm">
          <p className="font-semibold">场景多次审计未通过，建议人工介入修改。</p>
          <p className="text-gray-500">请查看该场景的审核报告了解具体原因。</p>
          <p className="text-gray-400 text-xs">建议重新审视场景的整体结构后再次提交。</p>
        </div>
      </Modal>

      <Drawer
        open={showVersionPanel}
        onClose={() => setShowVersionPanel(false)}
        title="版本历史"
        width={360}
      >
        <div className="space-y-2">
          {versionLoading ? (
            <div className="text-center py-4">
              <Spin size="small" />
            </div>
          ) : versionHistory.length > 0 ? (
            versionHistory.map((v, i) => (
              <Card
                key={i}
                size="small"
                className="hover:shadow-sm cursor-pointer transition-shadow"
                extra={
                  <Button size="small" type="link" icon={<UndoOutlined />} onClick={() => {
                    if (!editScene || !currentProject?.id) return
                    const restored = { ...editScene }
                    if (v.content && typeof v.content === 'object') {
                      if (v.content.narration) restored.narration = v.content.narration
                      if (v.content.dialogue) restored.dialogue = v.content.dialogue
                      if (v.content.actions) restored.actions = v.content.actions
                      if (v.content.foreshadow_ops) restored.foreshadow_ops = v.content.foreshadow_ops
                      if (v.content.choices) restored.choices = v.content.choices
                      if (v.content.causal_chain) restored.causal_chain = v.content.causal_chain
                      if (v.content.emotion_level) restored.emotion_level = v.content.emotion_level
                      if (v.content.location) restored.location = v.content.location
                      if (v.content.weather) restored.weather = v.content.weather
                      if (v.content.characters_involved) restored.characters_involved = v.content.characters_involved
                    }
                    setEditScene(restored)
                    notification.info({ message: `已恢复到 v${v.version}`, description: '内容已填入编辑区，请保存确认', placement: 'topRight' })
                  }}>
                    恢复
                  </Button>
                }
              >
                <div className="flex items-center gap-2 mb-1">
                  <Tag color="blue">v{v.version}</Tag>
                  <span className="text-sm">{v.change_reason}</span>
                </div>
                <span className="text-xs text-gray-400">{v.created_at}</span>
              </Card>
            ))
          ) : (
            <Empty description="暂无版本记录" />
          )}
        </div>
      </Drawer>
    </div>
  )
}
