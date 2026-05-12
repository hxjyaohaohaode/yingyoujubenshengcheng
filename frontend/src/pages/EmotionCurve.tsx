import { useState, useMemo, useEffect, useCallback } from 'react'
import {
  Card, Button, Tag, Slider, Empty, App, Space, Collapse, Row, Col, Spin,
} from 'antd'
import {
  RobotOutlined, ThunderboltOutlined, WarningOutlined,
  StarOutlined, CaretRightOutlined, BulbOutlined, LineChartOutlined,
  LoadingOutlined,
} from '@ant-design/icons'
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip as ReTooltip, ResponsiveContainer,
  ReferenceDot, Area, ComposedChart,
} from 'recharts'
import { useProjectStore } from '../stores/projectStore'
import { useAgentStore } from '../stores/agentStore'
import { api } from '../api/client'
import { eventBus, DataEvents } from '../services/eventBus'

interface SceneEmotion {
  scene_id: string
  scene_code: string
  title: string
  emotion_level: number
  scene_type: string
  is_wow: boolean
}

interface ChapterEmotion {
  chapter_number: number
  title: string
  avg_emotion: number
  peak_emotion: number
  valley_emotion: number
  emotion_target: number
  scenes: SceneEmotion[]
  rhythm_warnings: string[]
  wow_count: number
}

interface RhythmCheckResult {
  violations: { chapter: number | null; type: string; detail: string }[]
  warnings: { chapter: number | null; type: string; detail: string }[]
  overall_score: number
  suggestions: string[]
  ai_analyzed?: boolean
}

const RHYTHM_RULES: { name: string; check: (chs: ChapterEmotion[]) => { chapter: number; type: string; detail: string }[] }[] = [
  {
    name: '连续高潮规则',
    check: (chs) => {
      const results: { chapter: number; type: string; detail: string }[] = []
      for (let i = 0; i < chs.length - 2; i++) {
        if (chs[i].avg_emotion >= 7 && chs[i + 1].avg_emotion >= 7 && chs[i + 2].avg_emotion >= 7) {
          results.push({ chapter: chs[i + 2].chapter_number, type: '连续高潮', detail: `第${chs[i].chapter_number}-${chs[i + 2].chapter_number}章连续三章情感强度≥7，建议插入过渡章节` })
        }
      }
      return results
    },
  },
  {
    name: '连续低谷规则',
    check: (chs) => {
      const results: { chapter: number; type: string; detail: string }[] = []
      for (let i = 0; i < chs.length - 2; i++) {
        if (chs[i].avg_emotion <= 3 && chs[i + 1].avg_emotion <= 3 && chs[i + 2].avg_emotion <= 3) {
          results.push({ chapter: chs[i + 2].chapter_number, type: '连续低谷', detail: `第${chs[i].chapter_number}-${chs[i + 2].chapter_number}章连续三章情感强度≤3，可能导致读者流失` })
        }
      }
      return results
    },
  },
  {
    name: '过山车规则',
    check: (chs) => {
      const results: { chapter: number; type: string; detail: string }[] = []
      for (let i = 1; i < chs.length - 1; i++) {
        const diff1 = Math.abs(chs[i].avg_emotion - chs[i - 1].avg_emotion)
        const diff2 = Math.abs(chs[i + 1].avg_emotion - chs[i].avg_emotion)
        if (diff1 >= 5 && diff2 >= 5) {
          results.push({ chapter: chs[i].chapter_number, type: '过山车波动', detail: `第${chs[i].chapter_number}章前后波动均≥5，情感切换过于剧烈` })
        }
      }
      return results
    },
  },
  {
    name: '峰值间距规则',
    check: (chs) => {
      const results: { chapter: number; type: string; detail: string }[] = []
      const peakChapters = chs.filter(c => c.peak_emotion >= 8)
      for (let i = 1; i < peakChapters.length; i++) {
        const gap = peakChapters[i].chapter_number - peakChapters[i - 1].chapter_number
        if (gap < 2) {
          results.push({ chapter: peakChapters[i].chapter_number, type: '峰值过密', detail: `第${peakChapters[i - 1].chapter_number}章和${peakChapters[i].chapter_number}章峰值间距仅${gap}章，建议拉开至少2章` })
        }
      }
      return results
    },
  },
]

const SCENE_TYPE_LABELS: Record<string, string> = {
  dialogue: '对白', action: '动作', exploration: '探索', puzzle: '解谜', cutscene: '过场', branch: '分支',
}

export default function EmotionCurve() {
  const { notification } = App.useApp()
  const { currentProject } = useProjectStore()
  const { updateAgent } = useAgentStore()

  const [chapters, setChapters] = useState<ChapterEmotion[]>([])
  const [selectedChapter, setSelectedChapter] = useState<ChapterEmotion | null>(null)
  const [rhythmResult, setRhythmResult] = useState<RhythmCheckResult | null>(null)
  const [llmRhythmAnalysis, setLlmRhythmAnalysis] = useState<RhythmCheckResult | null>(null)
  const [isGenerating, setIsGenerating] = useState(false)
  const [isChecking, setIsChecking] = useState(false)
  const [isOptimizing, setIsOptimizing] = useState(false)
  const [loading, setLoading] = useState(false)
  const [fetchError, setFetchError] = useState<string | null>(null)

  const [wowSuggestions, setWowSuggestions] = useState<string[]>([])

  const fetchEmotionData = useCallback(async () => {
    if (!currentProject?.id) return
    setLoading(true)
    setFetchError(null)
    try {
      const [chaptersData, scenesData] = await Promise.all([
        api.get<any[]>(`/projects/${currentProject.id}/chapters`),
        api.get<any[]>(`/projects/${currentProject.id}/scenes`),
      ])

      const chapterMap = new Map<string, any>(chaptersData.map((ch: any) => [ch.id, ch]))
      const scenesByChapter = new Map<string, any[]>()

      for (const scene of scenesData) {
        const chId = scene.chapter_id
        if (!chId || !chapterMap.has(chId)) continue
        if (!scenesByChapter.has(chId)) scenesByChapter.set(chId, [])
        scenesByChapter.get(chId)!.push(scene)
      }

      const sortedChapters = [...chaptersData].sort((a: any, b: any) => a.chapter_number - b.chapter_number)
      const chapterEmotions: ChapterEmotion[] = []

      for (const ch of sortedChapters) {
        const scenes = scenesByChapter.get(ch.id) || []
        const emotionLevels = scenes.map((s: any) => s.emotion_level ?? 0)
        const sceneEmotions: SceneEmotion[] = scenes.map((s: any) => ({
          scene_id: s.id,
          scene_code: s.scene_code,
          title: s.scene_code,
          emotion_level: s.emotion_level ?? 0,
          scene_type: s.scene_type || 'dialogue',
          is_wow: s.is_wow_moment || false,
        }))

        const hasScenes = emotionLevels.length > 0
        const sceneAvg = hasScenes
          ? Math.round((emotionLevels.reduce((a: number, b: number) => a + b, 0) / emotionLevels.length) * 10) / 10
          : 0
        const aiTarget = ch.emotion_target ?? 0

        chapterEmotions.push({
          chapter_number: ch.chapter_number,
          title: ch.title || `第${ch.chapter_number}章`,
          avg_emotion: hasScenes ? sceneAvg : aiTarget,
          peak_emotion: hasScenes ? emotionLevels.reduce((a: number, b: number) => Math.max(a, b), -Infinity) : aiTarget,
          valley_emotion: hasScenes ? emotionLevels.reduce((a: number, b: number) => Math.min(a, b), Infinity) : aiTarget,
          emotion_target: aiTarget,
          scenes: sceneEmotions,
          rhythm_warnings: [],
          wow_count: scenes.filter((s: any) => s.is_wow_moment).length,
        })
      }

      if (chapterEmotions.length === 0) {
        setFetchError('项目中暂无章节数据，请先在「章节大纲」页面创建章节')
      } else {
        setChapters(chapterEmotions)
      }
    } catch {
      setFetchError('无法连接到服务器，请检查后端服务是否正常运行')
      notification.error({ message: '数据加载失败', description: '请检查网络连接和后端服务状态', placement: 'topRight' })
    } finally {
      setLoading(false)
    }
  }, [currentProject?.id])

  useEffect(() => {
    fetchEmotionData()
  }, [fetchEmotionData])

  useEffect(() => {
    const unsubs = [
      eventBus.on(DataEvents.SCENE_CREATED, () => { fetchEmotionData() }),
      eventBus.on(DataEvents.SCENE_UPDATED, () => { fetchEmotionData() }),
      eventBus.on(DataEvents.SCENE_DELETED, () => { fetchEmotionData() }),
      eventBus.on(DataEvents.SCENE_FINALIZED, () => { fetchEmotionData() }),
      eventBus.on(DataEvents.CHAPTER_CREATED, () => { fetchEmotionData() }),
      eventBus.on(DataEvents.CHAPTER_UPDATED, () => { fetchEmotionData() }),
      eventBus.on(DataEvents.CHAPTER_DELETED, () => { fetchEmotionData() }),
      eventBus.on(DataEvents.AI_GENERATION_COMPLETED, () => { fetchEmotionData() }),
      eventBus.on(DataEvents.AI_AUDIT_COMPLETED, () => { fetchEmotionData() }),
      eventBus.on(DataEvents.PIPELINE_STATUS_CHANGED, () => { fetchEmotionData() }),
      eventBus.on(DataEvents.PROJECT_SWITCHED, () => { fetchEmotionData() }),
    ]
    return () => unsubs.forEach((u) => u())
  }, [fetchEmotionData])

  const chartData = useMemo(() =>
    chapters.map(ch => ({
      name: `ch${ch.chapter_number}`,
      chapter_number: ch.chapter_number,
      label: `第${ch.chapter_number}章`,
      avg_emotion: ch.avg_emotion,
      peak_emotion: ch.peak_emotion,
      valley_emotion: ch.valley_emotion,
      emotion_target: ch.emotion_target,
      has_scenes: ch.scenes.length > 0,
      has_wow: ch.wow_count > 0,
      has_warning: ch.rhythm_warnings.length > 0,
      title: ch.title,
    })),
    [chapters]
  )

  const rhythmViolations = useMemo(() => {
    const all: { chapter: number; type: string; detail: string }[] = []
    RHYTHM_RULES.forEach(rule => all.push(...rule.check(chapters)))
    return all
  }, [chapters])

  const handleAIDesign = async () => {
    if (!currentProject?.id) return
    setIsGenerating(true)
    updateAgent('创意Agent', { status: 'busy', currentTask: '设计情感曲线' })
    try {
      const result = await api.post<{ status: string; message: string; chapters?: Array<{ chapter_number: number; emotion_target: number }> }>(`/ai/emotion-curve-design/${currentProject.id}`)
      if (result.status === 'error') {
        notification.error({ message: 'AI 设计失败', description: result.message || '请检查 AI 服务是否可用', placement: 'topRight', duration: 6 })
        return
      }
      if (result.chapters && result.chapters.length > 0) {
        notification.success({ message: '情感曲线设计完成', description: `AI已优化${result.chapters.length}个章节的目标情感值，图表将自动更新`, placement: 'topRight' })
      } else {
        notification.warning({ message: '情感曲线设计完成但无结果', description: result.message || 'AI未返回有效的章节数据', placement: 'topRight' })
      }
      await fetchEmotionData()
    } catch (e) {
      notification.error({ message: 'AI 设计失败', description: (e as Error).message || '请检查 AI 服务是否可用', placement: 'topRight' })
    } finally {
      updateAgent('创意Agent', { status: 'idle', currentTask: undefined })
      setIsGenerating(false)
    }
  }

  const handleRhythmCheck = async () => {
    if (!currentProject?.id) return
    setIsChecking(true)
    updateAgent('审计Agent', { status: 'busy', currentTask: '节奏检查' })

    const localViolations = [...rhythmViolations]

    let backendResult: RhythmCheckResult | null = null
    try {
      const raw = await api.post<any>(`/ai/rhythm-check/${currentProject.id}`)
      backendResult = {
        violations: Array.isArray(raw?.violations)
          ? raw.violations
          : Array.isArray(raw?.issues)
            ? raw.issues.map((detail: string) => ({ chapter: null, type: raw?.rhythm_status || 'rhythm', detail }))
            : [],
        warnings: Array.isArray(raw?.warnings) ? raw.warnings : [],
        overall_score: typeof raw?.overall_score === 'number' ? raw.overall_score : 80,
        suggestions: Array.isArray(raw?.suggestions) ? raw.suggestions : [],
        ai_analyzed: raw?.stats?.ai_analyzed === true || raw?.ai_analyzed === true,
      }
    } catch {
      backendResult = {
        violations: [],
        warnings: [],
        overall_score: 0,
        suggestions: [
          localViolations.length > 0 ? `本地规则检测到${localViolations.length}个节奏违规项，建议逐一优化` : '未获取到后端节奏分析结果，请稍后重试',
        ],
      }
    }

    setLlmRhythmAnalysis(backendResult)

    const mergedResult: RhythmCheckResult = {
      violations: [
        ...localViolations.map(v => ({ chapter: v.chapter, type: `[本地规则] ${v.type}`, detail: v.detail })),
        ...(backendResult?.violations || []).map(v => ({ chapter: v.chapter, type: `[AI分析] ${v.type}`, detail: v.detail })),
      ],
      warnings: backendResult?.warnings || [],
      overall_score: backendResult?.overall_score ?? 80,
      suggestions: [
        ...(backendResult?.suggestions || []),
      ],
    }

    setRhythmResult(mergedResult)
    updateAgent('审计Agent', { status: 'idle', currentTask: undefined })
    setIsChecking(false)
    notification.info({
      message: '节奏检查完成',
      description: backendResult?.ai_analyzed
        ? `综合评分: ${mergedResult.overall_score}/100，本地规则${localViolations.length}项 + AI深度分析`
        : `综合评分: ${mergedResult.overall_score}/100（仅本地规则，AI未参与。共检出${localViolations.length}项问题）`,
      placement: 'topRight',
    })
  }

  const handleWowOptimization = async () => {
    if (!currentProject?.id) return
    setIsOptimizing(true)
    updateAgent('创意Agent', { status: 'busy', currentTask: '哇塞时刻分布优化' })
    try {
      const result = await api.post<any>(`/ai/wow-distribution/${currentProject.id}`)
      if (result?.status === 'error') {
        notification.error({ message: '哇塞时刻分析失败', description: result.message || 'AI 服务不可用', placement: 'topRight', duration: 6 })
        setWowSuggestions([])
        updateAgent('创意Agent', { status: 'idle', currentTask: undefined })
        setIsOptimizing(false)
        return
      }
      const suggestions = Array.isArray(result?.suggestions) ? result.suggestions : []
      setWowSuggestions(suggestions)
      if (suggestions.length > 0) {
        const aiLabel = result?.ai_generated ? 'AI ' : ''
        notification.success({ message: '哇塞时刻分布分析完成', description: `${aiLabel}提供了 ${suggestions.length} 条优化建议`, placement: 'topRight' })
      } else {
        notification.info({ message: '哇塞时刻分布分析完成', description: result?.message || '当前分布已较为合理', placement: 'topRight' })
      }
    } catch (e) {
      notification.error({ message: '优化失败', description: (e as Error).message || '请检查 AI 服务是否可用', placement: 'topRight' })
    } finally {
      updateAgent('创意Agent', { status: 'idle', currentTask: undefined })
      setIsOptimizing(false)
    }
  }

  const handleDotClick = (data: any) => {
    if (data && data.activePayload && data.activePayload.length > 0) {
      const payload = data.activePayload[0].payload
      const chapter = chapters.find(c => c.chapter_number === payload.chapter_number)
      if (chapter) setSelectedChapter(chapter)
    }
  }

  const rhythmWarningSet = useMemo(() => new Set(rhythmViolations.map(v => v.chapter)), [rhythmViolations])
  const wowChapterSet = useMemo(() => new Set(chapters.filter(c => c.wow_count > 0).map(c => c.chapter_number)), [chapters])

  if (!currentProject) {
    return (
      <div style={{ fontFamily: 'var(--font-family)' }}>
        <h2 className="section-title" style={{ fontSize: 24 }}>审校修补</h2>
        <div className="card-surface" style={{ textAlign: 'center', padding: 48 }}><Empty description="请先创建或选择一个项目" /></div>
      </div>
    )
  }

  if (loading) {
    return (
      <div style={{ fontFamily: 'var(--font-family)', display: 'flex', justifyContent: 'center', padding: 80 }}>
        <div style={{ textAlign: 'center' }}>
          <Spin indicator={<LoadingOutlined style={{ fontSize: 36, color: 'var(--color-accent)' }} spin />} />
          <div className="text-muted" style={{ fontSize: 13, marginTop: 12 }}>正在加载情感曲线数据...</div>
        </div>
      </div>
    )
  }

  const allEmotionTargetsZero = chapters.length > 0 && chapters.every(ch => ch.emotion_target === 0)
  const hasUndesignedChapters = chapters.length > 0 && allEmotionTargetsZero
  return (
    <div style={{ fontFamily: 'var(--font-family)', display: 'flex', flexDirection: 'column', flex: 1, minHeight: 0 }}>
      {fetchError && (
        <div style={{ background: '#fff3cd', border: '1px solid #ffc107', borderRadius: 8, padding: '8px 14px', marginBottom: 8, fontSize: 13, color: '#856404', flexShrink: 0 }}>
          ⚠ {fetchError}
          <Button type="link" size="small" onClick={fetchEmotionData} style={{ marginLeft: 8, padding: 0 }}>重试</Button>
        </div>
      )}
      {!fetchError && hasUndesignedChapters && (
        <div style={{ background: '#e0f2fe', border: '1px solid #0ea5e9', borderRadius: 8, padding: '10px 14px', marginBottom: 8, fontSize: 13, color: '#0369a1', flexShrink: 0, display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <span>💡 {chapters.length}个章节已创建，但尚未设计情感曲线。所有章节目标值均为默认值，图表可能显示为底部的平直线。</span>
          <Button type="primary" size="small" icon={<RobotOutlined />} loading={isGenerating} onClick={handleAIDesign}>一键设计情感曲线</Button>
        </div>
      )}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16, flexShrink: 0 }}>
        <div>
          <h2 className="section-title" style={{ fontSize: 24 }}>审校修补</h2>
          <p className="text-muted" style={{ margin: '4px 0 0' }}>情感曲线分析与逻辑质量控制</p>
        </div>
        <Space>
          <Tag color="purple">3幕结构</Tag>
          <Tag color="blue">{chapters.length}章</Tag>
          <Tag color="gold">{chapters.reduce((s, c) => s + c.wow_count, 0)}个哇塞时刻</Tag>
          {fetchError && <Tag color="orange">数据加载失败</Tag>}
        </Space>
      </div>

      <div style={{ display: 'flex', gap: 8, flex: 1, minHeight: 0, overflow: 'hidden' }}>
        {/* 左侧：曲线大图 */}
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 8, minWidth: 0, overflow: 'hidden' }}>
          <Card size="small" style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden', minHeight: 280 }}
            styles={{ body: { flex: 1, overflow: 'hidden', padding: 12 } }}>
            <ResponsiveContainer width="100%" height="100%">
              <ComposedChart data={chartData} margin={{ top: 20, right: 30, left: 10, bottom: 10 }}
                onClick={handleDotClick}>
                <defs>
                  <linearGradient id="emotionGradient" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#8b5cf6" stopOpacity={0.4} />
                    <stop offset="50%" stopColor="#6366f1" stopOpacity={0.15} />
                    <stop offset="100%" stopColor="#3b82f6" stopOpacity={0.02} />
                  </linearGradient>
                  <linearGradient id="peakGradient" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#ef4444" stopOpacity={0.3} />
                    <stop offset="100%" stopColor="#ef4444" stopOpacity={0.0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                <XAxis dataKey="label" tick={{ fontSize: 11, fill: '#6b7280' }} axisLine={{ stroke: '#e5e7eb' }} />
                <YAxis domain={[0, 10]} ticks={[0, 2, 4, 6, 8, 10]} tick={{ fontSize: 11, fill: '#6b7280' }}
                  label={{ value: '情感强度', angle: -90, position: 'insideLeft', style: { fontSize: 11, fill: '#9ca3af' } }}
                  axisLine={{ stroke: '#e5e7eb' }} />
                <ReTooltip
                  content={({ active, payload }) => {
                    if (!active || !payload?.length) return null
                    const d = payload[0].payload
                    return (
                      <div className="bg-white dark:bg-slate-800 border border-gray-200 dark:border-slate-600 rounded-lg p-2 shadow-lg text-xs">
                        <div className="font-semibold mb-1">{d.label} · {d.title}</div>
                        <div className="space-y-0.5">
                          <div className="flex items-center gap-1"><span className="text-purple-500">●</span>均值: {d.avg_emotion}</div>
                          <div className="flex items-center gap-1"><span className="text-red-400">●</span>峰值: {d.peak_emotion}</div>
                          <div className="flex items-center gap-1"><span className="text-blue-400">●</span>低谷: {d.valley_emotion}</div>
                          {d.emotion_target > 0 && (
                            <div className="flex items-center gap-1"><span className="text-emerald-500">◆</span>AI目标: {d.emotion_target}</div>
                          )}
                          {!d.has_scenes && <div className="text-gray-400 italic">暂未创建场景，显示AI目标值</div>}
                          {d.has_scenes && Math.abs(d.avg_emotion - d.emotion_target) > 1.5 && d.emotion_target > 0 && (
                            <div className="text-amber-500 text-[10px]">⚠ 实际均值与AI目标偏差 {Math.abs(d.avg_emotion - d.emotion_target).toFixed(1)}</div>
                          )}
                          {d.has_wow && <div className="text-amber-500">⭐ 哇塞时刻</div>}
                          {d.has_warning && <div className="text-orange-500">⚠ 节奏警告</div>}
                        </div>
                      </div>
                    )
                  }}
                />
                <Area type="monotone" dataKey="avg_emotion" stroke="none" fill="url(#emotionGradient)" />
                <Line type="monotone" dataKey="avg_emotion" stroke="#8b5cf6" strokeWidth={2.5}
                  dot={{ r: 4, fill: '#8b5cf6', stroke: '#fff', strokeWidth: 2, cursor: 'pointer' }}
                  activeDot={{ r: 7, fill: '#8b5cf6', stroke: '#fff', strokeWidth: 3 }} />
                <Line type="monotone" dataKey="peak_emotion" stroke="#ef4444" strokeWidth={1.5} strokeDasharray="5 5"
                  dot={false} />
                <Line type="monotone" dataKey="valley_emotion" stroke="#3b82f6" strokeWidth={1.5} strokeDasharray="3 3"
                  dot={false} />
                <Line type="monotone" dataKey="emotion_target" stroke="#10b981" strokeWidth={2.5} strokeDasharray="6 3"
                  dot={{ r: 3, fill: '#10b981', stroke: '#fff', strokeWidth: 1.5 }}
                  connectNulls={true} />
                {chartData.filter(d => d.has_wow).map((d, i) => (
                  <ReferenceDot key={`wow-${i}`} x={d.label} y={d.avg_emotion + 0.8} r={12}
                    fill="#fbbf24" fillOpacity={0.25} stroke="#f59e0b" strokeWidth={1}
                    label={{ value: '★', position: 'center', fill: '#d97706', fontSize: 14, fontWeight: 'bold' }} />
                ))}
                {chartData.filter(d => rhythmWarningSet.has(d.chapter_number)).map((d, i) => (
                  <ReferenceDot key={`warn-${i}`} x={d.label} y={d.avg_emotion - 0.8}
                    r={6} fill="#f97316" stroke="#fff" strokeWidth={2} />
                ))}
              </ComposedChart>
            </ResponsiveContainer>
          </Card>

          {/* 图例 */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 16, fontSize: 12, color: '#6b7280', padding: '0 8px', flexShrink: 0 }}>
            <span className="flex items-center gap-1"><span className="inline-block w-3 h-0.5 bg-purple-500 rounded" />均值曲线</span>
            <span className="flex items-center gap-1"><span className="inline-block w-3 h-0.5 bg-red-400 rounded" style={{ borderStyle: 'dashed' }} />峰值线</span>
            <span className="flex items-center gap-1"><span className="inline-block w-3 h-0.5 bg-blue-400 rounded" style={{ borderStyle: 'dotted' }} />低谷线</span>
            <span className="flex items-center gap-1"><span className="inline-block w-3 h-0.5 bg-emerald-500 rounded" style={{ borderStyle: 'dashed' }} />AI设计目标</span>
            <span className="flex items-center gap-1"><span className="text-amber-500">★</span>哇塞时刻</span>
            <span className="flex items-center gap-1"><span className="inline-block w-2.5 h-2.5 rounded-full bg-orange-500" />节奏警告</span>
          </div>
        </div>

        {/* 右侧：章节详情面板 */}
        <div style={{ width: 320, flexShrink: 0, display: 'flex', flexDirection: 'column', gap: 8, overflow: 'auto' }}>
          {selectedChapter ? (
            <Card size="small" title={<span className="text-sm">{`第${selectedChapter.chapter_number}章 · ${selectedChapter.title}`}</span>}
              extra={<Button size="small" type="text" onClick={() => setSelectedChapter(null)}>关闭</Button>}>
              <div className="space-y-3">
                <div>
                  <div className="text-xs text-gray-400 mb-1">章节统计</div>
                  <Row gutter={4}>
                    <Col span={6}><div className="bg-purple-50 dark:bg-purple-900/10 rounded p-1.5 text-center">
                      <div className="text-lg font-bold text-purple-600">{selectedChapter.avg_emotion}</div>
                      <div className="text-[10px] text-gray-400">均值</div>
                    </div></Col>
                    <Col span={6}><div className="bg-red-50 dark:bg-red-900/10 rounded p-1.5 text-center">
                      <div className="text-lg font-bold text-red-500">{selectedChapter.peak_emotion}</div>
                      <div className="text-[10px] text-gray-400">峰值</div>
                    </div></Col>
                    <Col span={6}><div className="bg-blue-50 dark:bg-blue-900/10 rounded p-1.5 text-center">
                      <div className="text-lg font-bold text-blue-500">{selectedChapter.valley_emotion}</div>
                      <div className="text-[10px] text-gray-400">低谷</div>
                    </div></Col>
                    <Col span={6}><div className="bg-emerald-50 dark:bg-emerald-900/10 rounded p-1.5 text-center">
                      <div className="text-lg font-bold text-emerald-500">{selectedChapter.emotion_target || '-'}</div>
                      <div className="text-[10px] text-gray-400">AI目标</div>
                    </div></Col>
                  </Row>
                </div>

                <div>
                  <div className="text-xs text-gray-400 mb-1 font-semibold">场景情感强度</div>
                  <div className="space-y-1.5">
                    {selectedChapter.scenes.map(sc => (
                      <div key={sc.scene_id} className="flex items-center gap-2">
                        <span className="text-[10px] font-mono text-gray-400 w-[58px]">{sc.scene_code}</span>
                        <Tag className="text-[10px] leading-tight">{SCENE_TYPE_LABELS[sc.scene_type] || sc.scene_type}</Tag>
                        <div style={{ flex: 1 }}>
                          <div className="h-1.5 bg-gray-200 dark:bg-slate-600 rounded-full overflow-hidden">
                            <div className="h-full rounded-full transition-all"
                              style={{
                                width: `${sc.emotion_level * 10}%`,
                                background: sc.emotion_level <= 3 ? '#3b82f6' : sc.emotion_level <= 5 ? '#8b5cf6' : sc.emotion_level <= 7 ? '#f59e0b' : '#ef4444',
                              }} />
                          </div>
                        </div>
                        <span className="text-xs font-semibold w-5 text-right">{sc.emotion_level}</span>
                        {sc.is_wow && <StarOutlined className="text-amber-400 text-xs" />}
                      </div>
                    ))}
                  </div>
                </div>

                {selectedChapter.rhythm_warnings.length > 0 && (
                  <div>
                    <div className="text-xs text-gray-400 mb-1 font-semibold">⚠ 节奏警告</div>
                    <div className="space-y-1">
                      {selectedChapter.rhythm_warnings.map((w, i) => (
                        <div key={i} className="text-xs text-orange-600 bg-orange-50 dark:bg-orange-900/10 p-1.5 rounded">{w}</div>
                      ))}
                    </div>
                  </div>
                )}

                {selectedChapter.wow_count > 0 && (
                  <div>
                    <div className="text-xs text-gray-400 mb-1 font-semibold">⭐ 哇塞时刻</div>
                    {selectedChapter.scenes.filter(s => s.is_wow).map(s => (
                      <div key={s.scene_id} className="text-xs text-amber-600 bg-amber-50 dark:bg-amber-900/10 p-1.5 rounded">
                        {s.scene_code} {s.title}: 情感巅峰 {s.emotion_level}/10
                      </div>
                    ))}
                  </div>
                )}

                <div>
                  <div className="text-xs text-gray-400 mb-1 font-semibold">节奏规则检查</div>
                  {rhythmViolations.filter(v => v.chapter === selectedChapter.chapter_number).length > 0
                    ? rhythmViolations.filter(v => v.chapter === selectedChapter.chapter_number).map((v, i) => (
                      <div key={i} className={`text-xs p-1.5 rounded mb-1 ${v.type.includes('连续') ? 'bg-red-50 dark:bg-red-900/10 text-red-600' : 'bg-yellow-50 dark:bg-yellow-900/10 text-yellow-600'}`}>
                        <span className="font-semibold">{v.type}</span>: {v.detail}
                      </div>
                    ))
                    : <div className="text-xs text-green-600 bg-green-50 dark:bg-green-900/10 p-1.5 rounded">✅ 节奏正常，无违规</div>
                  }
                </div>

                {llmRhythmAnalysis && llmRhythmAnalysis.violations.filter(v => v.chapter === selectedChapter.chapter_number).length > 0 && (
                  <div>
                    <div className="text-xs text-gray-400 mb-1 font-semibold">🤖 AI节奏分析</div>
                    {llmRhythmAnalysis.violations.filter(v => v.chapter === selectedChapter.chapter_number).map((v, i) => (
                      <div key={i} className="text-xs p-1.5 rounded mb-1 bg-indigo-50 dark:bg-indigo-900/10 text-indigo-600">
                        <span className="font-semibold">{v.type}</span>: {v.detail}
                      </div>
                    ))}
                    {llmRhythmAnalysis.suggestions.filter((_, idx) => idx < 2).map((s, i) => (
                      <div key={i} className="text-xs text-gray-500">· {s}</div>
                    ))}
                  </div>
                )}
              </div>
            </Card>
          ) : (
            <Card size="small" style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <Empty description="点击曲线上的数据点查看章节详情" image={Empty.PRESENTED_IMAGE_SIMPLE} />
            </Card>
          )}
        </div>
      </div>

      {/* 节奏检查结果 */}
      {rhythmResult && (
        <Collapse size="small" style={{ flexShrink: 0, marginTop: 4 }} items={[{
          key: 'rhythm',
          label: (
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13 }}>
              <ThunderboltOutlined />
              <span>节奏检查结果</span>
              <Tag color={rhythmResult.overall_score >= 85 ? 'green' : rhythmResult.overall_score >= 70 ? 'orange' : 'red'}>
                综合评分: {rhythmResult.overall_score}/100
              </Tag>
              <span className="text-xs text-gray-400">
                (本地规则{rhythmViolations.length}项 + AI分析{rhythmResult.violations.filter(v => v.type.startsWith('[AI分析]')).length}项)
              </span>
            </div>
          ),
          children: (
            <div className="space-y-2">
              {rhythmResult.violations.length > 0 && (
                <div>
                  <div className="text-xs text-red-500 font-semibold mb-1">违规项</div>
                  {rhythmResult.violations.map((v, i) => (
                    <div key={i} className={`text-xs p-1.5 rounded mb-1 ${v.type.startsWith('[AI分析]') ? 'bg-indigo-50 dark:bg-indigo-900/10 text-indigo-600' : 'bg-red-50 dark:bg-red-900/10 text-red-600'}`}>
                      <span className="font-semibold">{v.type}</span>: {v.detail}
                    </div>
                  ))}
                </div>
              )}
              {rhythmResult.warnings.length > 0 && (
                <div>
                  <div className="text-xs text-orange-500 font-semibold mb-1">警告项</div>
                  {rhythmResult.warnings.map((w, i) => (
                    <div key={i} className="text-xs text-orange-600 bg-orange-50 dark:bg-orange-900/10 p-1.5 rounded mb-1">
                      <span className="font-semibold">{w.type}</span>: {w.detail}
                    </div>
                  ))}
                </div>
              )}
              {rhythmResult.suggestions.length > 0 && (
                <div>
                  <div className="text-xs text-gray-400 font-semibold mb-1">优化建议</div>
                  {rhythmResult.suggestions.map((s, i) => (
                    <div key={i} className="text-xs text-gray-600 dark:text-gray-400">· {s}</div>
                  ))}
                </div>
              )}
            </div>
          ),
        }]} />
      )}

      {/* 哇塞时刻分布建议 */}
      {wowSuggestions.length > 0 && (
        <Collapse size="small" style={{ flexShrink: 0, marginTop: 4 }} items={[{
          key: 'wow',
          label: (
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13 }}>
              <StarOutlined style={{ color: '#f59e0b' }} />
              <span>哇塞时刻分布建议</span>
              <Tag color="gold">{wowSuggestions.length}条建议</Tag>
            </div>
          ),
          children: (
            <div>
              {wowSuggestions.map((s, i) => (
                <div key={i} style={{ fontSize: 12, padding: '4px 0', color: 'var(--color-ink)', borderBottom: i < wowSuggestions.length - 1 ? '1px solid var(--color-border)' : 'none' }}>
                  <span style={{ color: '#f59e0b', marginRight: 6 }}>◆</span>{s}
                </div>
              ))}
            </div>
          ),
        }]} />
      )}

      {/* 底部操作栏 */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexShrink: 0, marginTop: 8 }}>
        <Button icon={<RobotOutlined />} type="primary" loading={isGenerating} onClick={handleAIDesign} size="small">
          AI 设计情感曲线
        </Button>
        <Button icon={<ThunderboltOutlined />} loading={isChecking} onClick={handleRhythmCheck} size="small" type="primary" ghost>
          节奏规则检查
        </Button>
        <Button icon={<BulbOutlined />} loading={isOptimizing} onClick={handleWowOptimization} size="small" type="dashed">
          哇塞时刻分布优化
        </Button>
        <Button icon={<LineChartOutlined />} onClick={fetchEmotionData} size="small" type="text" disabled={loading}>
          刷新数据
        </Button>
      </div>
    </div>
  )
}
