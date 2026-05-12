import { useState, useCallback, useEffect, useRef } from 'react'
import { Modal, Button, App, Tag, Tooltip } from 'antd'
import type { ProjectCreatePayload } from '../api/client'
import { projectsApi } from '../api/client'
import { useProjectStore } from '../stores/projectStore'
import { useNavigate } from 'react-router-dom'
import { eventBus, DataEvents } from '../services/eventBus'

const GENRE_OPTIONS = ['', '悬疑', '爱情', '武侠', '科幻', '奇幻', '恐怖', '历史', '玄幻', '仙侠', '推理', '都市', '古装', '末世', '战争', '青春']
const TONE_OPTIONS: Record<string, string> = { neutral: '中性', dark: '暗黑沉重', light: '轻松明快', epic: '史诗宏大', intimate: '细腻亲密' }
const POV_OPTIONS: Record<string, string> = { third_person: '第三人称', first_person: '第一人称', omniscient: '全知视角', multiple: '多视角切换' }
const MIN_TARGET_WORD_COUNT_WAN = 1
const MAX_TARGET_WORD_COUNT_WAN = 150

interface CreateProjectModalProps {
  open: boolean
  onClose: () => void
}

interface FormConfig {
  targetWordCountWan: number
  targetWordCountCustom: string
  genre: string
  configSubGenre: string
  configCoreContradiction: string
  configTheme: string
  configTone: string
  configNarrativePov: string
  configChapterCount: number
  configMinWordsPerChapter: number
  configMaxWordsPerChapter: number
  configScenesPerChapterMin: number
  configScenesPerChapterMax: number
  configTargetEndingCount: number
  configMaxBranchDepth: number
  configMinBranchesPerChoice: number
  configMaxBranchesPerChoice: number
  configWowMomentDensity: number
  configMinDialogueRatio: number
  configMaxNarrationRatio: number
  configWorldBuildingDepth: number
  configCharacterDepthTarget: number
  configPlotComplexity: number
}

interface RecommendationInfo {
  chapter_count: number
  min_words_per_chapter: number
  max_words_per_chapter: number
  scenes_per_chapter_min: number
  scenes_per_chapter_max: number
  target_ending_count: number
  max_branch_depth: number
  min_branches_per_choice: number
  max_branches_per_choice: number
  wow_moment_density: number
  world_building_depth: number
  character_depth_target: number
  plot_complexity: number
  min_dialogue_ratio: number
  max_narration_ratio: number
}

interface ValidationResult {
  is_valid: boolean
  message: string
  suggestions: Record<string, number> | null
}

function makeEmptyConfig(): FormConfig {
  return {
    targetWordCountWan: 5,
    targetWordCountCustom: '',
    genre: '',
    configSubGenre: '',
    configCoreContradiction: '',
    configTheme: '',
    configTone: 'neutral',
    configNarrativePov: 'third_person',
    configChapterCount: 10,
    configMinWordsPerChapter: 2000,
    configMaxWordsPerChapter: 8000,
    configScenesPerChapterMin: 2,
    configScenesPerChapterMax: 6,
    configTargetEndingCount: 3,
    configMaxBranchDepth: 3,
    configMinBranchesPerChoice: 2,
    configMaxBranchesPerChoice: 4,
    configWowMomentDensity: 2.5,
    configMinDialogueRatio: 0.20,
    configMaxNarrationRatio: 0.50,
    configWorldBuildingDepth: 5,
    configCharacterDepthTarget: 5,
    configPlotComplexity: 5,
  }
}

function applyRecommendation(config: FormConfig, rec: RecommendationInfo): FormConfig {
  return {
    ...config,
    configChapterCount: rec.chapter_count,
    configMinWordsPerChapter: rec.min_words_per_chapter,
    configMaxWordsPerChapter: rec.max_words_per_chapter,
    configScenesPerChapterMin: rec.scenes_per_chapter_min,
    configScenesPerChapterMax: rec.scenes_per_chapter_max,
    configTargetEndingCount: rec.target_ending_count,
    configMaxBranchDepth: rec.max_branch_depth,
    configMinBranchesPerChoice: rec.min_branches_per_choice,
    configMaxBranchesPerChoice: rec.max_branches_per_choice,
    configWowMomentDensity: rec.wow_moment_density,
    configWorldBuildingDepth: rec.world_building_depth,
    configCharacterDepthTarget: rec.character_depth_target,
    configPlotComplexity: rec.plot_complexity,
    configMinDialogueRatio: rec.min_dialogue_ratio,
    configMaxNarrationRatio: rec.max_narration_ratio,
  }
}

export default function CreateProjectModal({ open, onClose }: CreateProjectModalProps) {
  const { notification } = App.useApp()
  const navigate = useNavigate()
  const { projects, setProjects, setCurrentProject } = useProjectStore()
  const [creatingProject, setCreatingProject] = useState(false)
  const [activeConfigTab, setActiveConfigTab] = useState('basic')
  const [newProjectName, setNewProjectName] = useState('')
  const [newProjectDesc, setNewProjectDesc] = useState('')
  const [config, setConfig] = useState<FormConfig>(() => makeEmptyConfig())
  const [recommendation, setRecommendation] = useState<RecommendationInfo | null>(null)
  const [recommendationReasoning, setRecommendationReasoning] = useState('')
  const [recommendationNotes, setRecommendationNotes] = useState('')
  const [estimates, setEstimates] = useState({ total_scenes: 0, wow_moments: 0, branch_nodes: 0 })
  const [validation, setValidation] = useState<ValidationResult | null>(null)
  const [hasUserModified, setHasUserModified] = useState(false)
  const [showRecommendationBanner, setShowRecommendationBanner] = useState(false)
  const recommendAbortRef = useRef<AbortController | null>(null)
  const validateAbortRef = useRef<AbortController | null>(null)
  const recommendTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const resolveWordCount = (): number => {
    if (config.targetWordCountCustom) {
      const parsed = parseFloat(config.targetWordCountCustom)
      if (!isNaN(parsed) && parsed >= MIN_TARGET_WORD_COUNT_WAN && parsed <= MAX_TARGET_WORD_COUNT_WAN) {
        return Math.round(parsed * 10000)
      }
    }
    return config.targetWordCountWan * 10000
  }

  const reset = useCallback(() => {
    setNewProjectName('')
    setNewProjectDesc('')
    setConfig(makeEmptyConfig())
    setActiveConfigTab('basic')
    setRecommendation(null)
    setRecommendationReasoning('')
    setRecommendationNotes('')
    setEstimates({ total_scenes: 0, wow_moments: 0, branch_nodes: 0 })
    setValidation(null)
    setHasUserModified(false)
    setShowRecommendationBanner(false)
    if (recommendAbortRef.current) {
      recommendAbortRef.current.abort()
      recommendAbortRef.current = null
    }
    if (validateAbortRef.current) {
      validateAbortRef.current.abort()
      validateAbortRef.current = null
    }
    if (recommendTimeoutRef.current) {
      clearTimeout(recommendTimeoutRef.current)
      recommendTimeoutRef.current = null
    }
  }, [])

  const updateConfig = useCallback((key: keyof FormConfig, value: unknown) => {
    setConfig((prev) => ({ ...prev, [key]: value }))
    setHasUserModified(true)
  }, [])

  // 智能推荐：当字数或体裁变化时自动获取推荐参数
  useEffect(() => {
    if (!open) return

    const wordCount = resolveWordCount()
    const genre = config.genre

    if (recommendTimeoutRef.current) {
      clearTimeout(recommendTimeoutRef.current)
    }

    recommendTimeoutRef.current = setTimeout(async () => {
      if (recommendAbortRef.current) {
        recommendAbortRef.current.abort()
      }
      recommendAbortRef.current = new AbortController()

      try {
        const res = await projectsApi.recommendConfig({
          target_word_count: wordCount,
          genre,
        })

        setRecommendation(res.recommendation)
        setRecommendationReasoning(res.reasoning)
        setRecommendationNotes(res.genre_notes)
        setEstimates(res.estimates)

        // 如果用户没有手动修改过参数，自动应用推荐值
        if (!hasUserModified) {
          setConfig((prev) => applyRecommendation(prev, res.recommendation))
        } else {
          // 用户修改过，显示推荐横幅
          setShowRecommendationBanner(true)
        }
      } catch (e: any) {
        if (e?.detail !== '请求已取消') {
          console.warn('推荐参数获取失败:', e)
        }
      }
    }, 500)

    return () => {
      if (recommendTimeoutRef.current) {
        clearTimeout(recommendTimeoutRef.current)
      }
    }
  }, [config.targetWordCountWan, config.targetWordCountCustom, config.genre, open])

  // 参数校验
  useEffect(() => {
    if (!open) return

    const wordCount = resolveWordCount()

    const timeout = setTimeout(async () => {
      if (validateAbortRef.current) {
        validateAbortRef.current.abort()
      }
      validateAbortRef.current = new AbortController()

      try {
        const res = await projectsApi.validateConfig({
          target_word_count: wordCount,
          chapter_count: config.configChapterCount,
          min_words_per_chapter: config.configMinWordsPerChapter,
          max_words_per_chapter: config.configMaxWordsPerChapter,
          target_ending_count: config.configTargetEndingCount,
          max_branch_depth: config.configMaxBranchDepth,
        })
        setValidation(res)
      } catch (e: any) {
        if (e?.detail !== '请求已取消') {
          console.warn('参数校验失败:', e)
        }
      }
    }, 800)

    return () => clearTimeout(timeout)
  }, [
    config.configChapterCount,
    config.configMinWordsPerChapter,
    config.configMaxWordsPerChapter,
    config.configTargetEndingCount,
    config.configMaxBranchDepth,
    config.targetWordCountWan,
    config.targetWordCountCustom,
    open,
  ])

  const handleApplyRecommendation = () => {
    if (recommendation) {
      setConfig((prev) => applyRecommendation(prev, recommendation))
      setHasUserModified(false)
      setShowRecommendationBanner(false)
      notification.success({
        message: '已应用智能推荐参数',
        description: recommendationReasoning,
        placement: 'topRight',
      })
    }
  }

  const handleClose = useCallback(() => {
    reset()
    onClose()
  }, [reset, onClose])

  const handleCreateProject = async () => {
    const trimmedName = newProjectName.trim()
    if (!trimmedName) {
      notification.warning({ message: '请输入项目名称', placement: 'topRight' })
      return
    }
    // Check for duplicate name
    const existingProject = projects.find(p => p.name === trimmedName)
    if (existingProject) {
      notification.warning({
        message: '项目名称已存在',
        description: `「${trimmedName}」已存在，请使用不同的名称以区分项目。`,
        placement: 'topRight',
      })
      return
    }

    const resolvedWordCount = resolveWordCount()
    if (resolvedWordCount < 10000 || resolvedWordCount > 1500000) {
      notification.warning({
        message: '目标总字数超出范围',
        description: '当前项目目标总字数必须在 1 万字到 150 万字之间。',
        placement: 'topRight',
      })
      return
    }

    // 如果有校验错误，提示用户
    if (validation && !validation.is_valid) {
      notification.warning({
        message: '参数配置可能不合理',
        description: validation.message,
        placement: 'topRight',
      })
      // 不阻止创建，但给用户警告
    }

    setCreatingProject(true)
    try {
      const project = await projectsApi.create({
        name: newProjectName.trim(),
        description: newProjectDesc.trim() || undefined,
        template_id: 'interactive_drama',
        config: {
          target_word_count: resolvedWordCount,
          genre: config.genre || undefined,
          sub_genre: config.configSubGenre || undefined,
          core_contradiction: config.configCoreContradiction || undefined,
          theme: config.configTheme || undefined,
          tone: config.configTone,
          chapter_count: config.configChapterCount,
          min_words_per_chapter: config.configMinWordsPerChapter,
          max_words_per_chapter: config.configMaxWordsPerChapter,
          scenes_per_chapter_min: config.configScenesPerChapterMin,
          scenes_per_chapter_max: config.configScenesPerChapterMax,
          target_ending_count: config.configTargetEndingCount,
          max_branch_depth: config.configMaxBranchDepth,
          min_branches_per_choice: config.configMinBranchesPerChoice,
          max_branches_per_choice: config.configMaxBranchesPerChoice,
          wow_moment_density: config.configWowMomentDensity,
          min_dialogue_ratio: config.configMinDialogueRatio,
          max_narration_ratio: config.configMaxNarrationRatio,
          narrative_pov: config.configNarrativePov,
          world_building_depth: config.configWorldBuildingDepth,
          character_depth_target: config.configCharacterDepthTarget,
          plot_complexity: config.configPlotComplexity,
        },
      })
      setProjects([project, ...projects])
      setCurrentProject(project)
      eventBus.emit(DataEvents.PROJECT_SWITCHED, { projectId: project.id })
      handleClose()
      navigate('/')
      notification.success({
        message: '项目创建成功',
        description: `「${project.name}」已创建，目标${(resolvedWordCount / 10000).toFixed(1)}万字`,
        placement: 'topRight',
      })
    } catch (e) {
      notification.error({
        message: '创建失败',
        description: (e as Error).message || '请检查网络连接',
        placement: 'topRight',
      })
    }
    setCreatingProject(false)
  }

  const displayWordCount = config.targetWordCountCustom || config.targetWordCountWan
  const wordCount = resolveWordCount()
  const wordCountWan = wordCount / 10000

  // 计算当前容量
  const minCapacity = config.configChapterCount * config.configMinWordsPerChapter
  const maxCapacity = config.configChapterCount * config.configMaxWordsPerChapter
  const capacityRatio = wordCount > 0 ? Math.min(100, Math.round((wordCount / maxCapacity) * 100)) : 0

  return (
    <Modal
      title="创建互动影游项目"
      open={open}
      onCancel={handleClose}
      footer={false}
      width={720}
      destroyOnHidden
    >
      <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
        {/* 顶部信息栏 */}
        <div style={{
          background: 'linear-gradient(135deg, var(--color-accent-soft), #F0F5FF)',
          borderRadius: 12, padding: '12px 16px', fontSize: 12,
          color: 'var(--color-muted)', border: '1px solid rgba(51, 102, 255, 0.1)',
        }}>
          支持生成 1 ~ 150 万字的互动影游剧本。创建后可随时在项目设置中调整参数。
        </div>

        {/* 智能推荐横幅 */}
        {showRecommendationBanner && recommendation && hasUserModified && (
          <div style={{
            background: '#FFF7E6',
            borderRadius: 12,
            padding: '12px 16px',
            border: '1px solid #FFD591',
            display: 'flex',
            flexDirection: 'column',
            gap: 8,
          }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <span style={{ fontSize: 16 }}>💡</span>
                <span style={{ fontSize: 13, fontWeight: 600, color: '#D46B08' }}>
                  检测到更优的参数配置
                </span>
              </div>
              <Button type="primary" size="small" onClick={handleApplyRecommendation}>
                一键应用推荐
              </Button>
            </div>
            <div style={{ fontSize: 12, color: '#8C6B3D', lineHeight: 1.6 }}>
              {recommendationReasoning}
            </div>
            {recommendationNotes && (
              <div style={{ fontSize: 11, color: '#A68B5B', lineHeight: 1.5 }}>
                {recommendationNotes}
              </div>
            )}
          </div>
        )}

        {/* 校验提示 */}
        {validation && !validation.is_valid && (
          <div style={{
            background: '#FFF2F0',
            borderRadius: 12,
            padding: '10px 14px',
            border: '1px solid #FFCCC7',
            display: 'flex',
            alignItems: 'center',
            gap: 8,
          }}>
            <span style={{ fontSize: 14 }}>⚠️</span>
            <span style={{ fontSize: 12, color: '#CF1322' }}>{validation.message}</span>
          </div>
        )}

        {/* Tab 导航 */}
        <div style={{ display: 'flex', gap: 0, borderBottom: '1px solid var(--color-border)' }}>
          {[
            { key: 'basic', label: '基础信息' },
            { key: 'story', label: '剧情设定' },
            { key: 'structure', label: '结构参数' },
            { key: 'branch', label: '分支结局' },
          ].map(tab => (
            <Button
              key={tab.key}
              type="text"
              onClick={() => setActiveConfigTab(tab.key)}
              style={{
                color: activeConfigTab === tab.key ? 'var(--color-accent)' : 'var(--color-muted)',
                fontWeight: activeConfigTab === tab.key ? 600 : 400,
                borderBottom: activeConfigTab === tab.key ? '2px solid var(--color-accent)' : '2px solid transparent',
                borderRadius: 0,
              }}
            >
              {tab.label}
            </Button>
          ))}
        </div>

        {/* 基础信息 Tab */}
        {activeConfigTab === 'basic' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            <div>
              <label style={{ fontSize: 13, fontWeight: 600, color: 'var(--color-ink)', display: 'block', marginBottom: 6 }}>
                项目名称 <span style={{ color: 'var(--color-danger)' }}>*</span>
              </label>
              <input
                className="input-field"
                placeholder="例：《暗影迷城》"
                value={newProjectName}
                onChange={e => setNewProjectName(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && handleCreateProject()}
              />
            </div>
            <div>
              <label style={{ fontSize: 13, fontWeight: 600, color: 'var(--color-ink)', display: 'block', marginBottom: 6 }}>
                项目描述
              </label>
              <input
                className="input-field"
                placeholder="简短描述这个项目的核心创意..."
                value={newProjectDesc}
                onChange={e => setNewProjectDesc(e.target.value)}
              />
            </div>
            <div>
              <label style={{ fontSize: 13, fontWeight: 600, color: 'var(--color-ink)', display: 'block', marginBottom: 8 }}>
                目标总字数 <span style={{ fontSize: 11, color: 'var(--color-subtle)' }}>{displayWordCount}万字 = {wordCount.toLocaleString()}字</span>
              </label>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginBottom: 10 }}>
                {[1, 5, 10, 20, 50, 100, 150].map(v => (
                  <Button
                    key={v}
                    size="small"
                    type={!config.targetWordCountCustom && config.targetWordCountWan === v ? 'primary' : 'default'}
                    onClick={() => { updateConfig('targetWordCountWan', v); updateConfig('targetWordCountCustom', '') }}
                  >
                    {v}万
                  </Button>
                ))}
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <span style={{ fontSize: 11, color: 'var(--color-muted)' }}>自定义：</span>
                <input
                  className="input-field"
                  style={{ width: 100, fontSize: 11 }}
                  placeholder="万字"
                  value={config.targetWordCountCustom}
                  onChange={e => updateConfig('targetWordCountCustom', e.target.value)}
                />
              </div>
              <input
                type="range" min={MIN_TARGET_WORD_COUNT_WAN} max={MAX_TARGET_WORD_COUNT_WAN} step={1}
                value={config.targetWordCountCustom
                  ? Math.min(MAX_TARGET_WORD_COUNT_WAN, Math.max(MIN_TARGET_WORD_COUNT_WAN, Math.round(parseFloat(config.targetWordCountCustom) || MIN_TARGET_WORD_COUNT_WAN)))
                  : config.targetWordCountWan
                }
                onChange={e => { updateConfig('targetWordCountWan', Number(e.target.value)); updateConfig('targetWordCountCustom', '') }}
                style={{ width: '100%', accentColor: 'var(--color-accent)', marginTop: 8 }}
              />
            </div>

            {/* 规模预览 */}
            {estimates.total_scenes > 0 && (
              <div style={{
                background: '#F6FFED',
                borderRadius: 10,
                padding: '10px 14px',
                border: '1px solid #B7EB8F',
                display: 'flex',
                flexWrap: 'wrap',
                gap: '8px 16px',
              }}>
                <Tag color="green">约 {estimates.total_scenes} 个场景</Tag>
                <Tag color="blue">约 {estimates.wow_moments} 个爽点</Tag>
                <Tag color="purple">约 {estimates.branch_nodes} 个分支节点</Tag>
                <Tag color="orange">{config.configChapterCount} 章</Tag>
                <Tag color="cyan">{config.configTargetEndingCount} 个结局</Tag>
              </div>
            )}
          </div>
        )}

        {/* 剧情设定 Tab */}
        {activeConfigTab === 'story' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
              <div>
                <label style={{ fontSize: 13, fontWeight: 600, color: 'var(--color-ink)', display: 'block', marginBottom: 6 }}>体裁</label>
                <select className="select-field" value={config.genre} onChange={e => updateConfig('genre', e.target.value)}>
                  {GENRE_OPTIONS.map(g => <option key={g} value={g}>{g || '不设定'}</option>)}
                </select>
              </div>
              <div>
                <label style={{ fontSize: 13, fontWeight: 600, color: 'var(--color-ink)', display: 'block', marginBottom: 6 }}>子类型</label>
                <input className="input-field" placeholder="如：古装悬疑" value={config.configSubGenre} onChange={e => updateConfig('configSubGenre', e.target.value)} />
              </div>
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
              <div>
                <label style={{ fontSize: 13, fontWeight: 600, color: 'var(--color-ink)', display: 'block', marginBottom: 6 }}>基调</label>
                <select className="select-field" value={config.configTone} onChange={e => updateConfig('configTone', e.target.value)}>
                  {Object.entries(TONE_OPTIONS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
                </select>
              </div>
              <div>
                <label style={{ fontSize: 13, fontWeight: 600, color: 'var(--color-ink)', display: 'block', marginBottom: 6 }}>叙事视角</label>
                <select className="select-field" value={config.configNarrativePov} onChange={e => updateConfig('configNarrativePov', e.target.value)}>
                  {Object.entries(POV_OPTIONS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
                </select>
              </div>
            </div>
            <div>
              <label style={{ fontSize: 13, fontWeight: 600, color: 'var(--color-ink)', display: 'block', marginBottom: 6 }}>核心矛盾</label>
              <input className="input-field" placeholder="例：真相与谎言的终极对决" value={config.configCoreContradiction} onChange={e => updateConfig('configCoreContradiction', e.target.value)} />
            </div>
            <div>
              <label style={{ fontSize: 13, fontWeight: 600, color: 'var(--color-ink)', display: 'block', marginBottom: 6 }}>主题思想</label>
              <input className="input-field" placeholder="例：在绝望中寻找希望" value={config.configTheme} onChange={e => updateConfig('configTheme', e.target.value)} />
            </div>
          </div>
        )}

        {/* 结构参数 Tab */}
        {activeConfigTab === 'structure' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
            {/* 容量指示器 */}
            <div style={{
              background: capacityRatio > 100 ? '#FFF2F0' : capacityRatio > 80 ? '#FFF7E6' : '#F6FFED',
              borderRadius: 10,
              padding: '10px 14px',
              border: `1px solid ${capacityRatio > 100 ? '#FFCCC7' : capacityRatio > 80 ? '#FFD591' : '#B7EB8F'}`,
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
                <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--color-ink)' }}>章节容量利用率</span>
                <span style={{ fontSize: 12, color: capacityRatio > 100 ? '#CF1322' : 'var(--color-muted)' }}>
                  {wordCount.toLocaleString()}字 / {maxCapacity.toLocaleString()}字 ({capacityRatio}%)
                </span>
              </div>
              <div style={{
                width: '100%',
                height: 6,
                background: '#E8E8E8',
                borderRadius: 3,
                overflow: 'hidden',
              }}>
                <div style={{
                  width: `${Math.min(100, capacityRatio)}%`,
                  height: '100%',
                  background: capacityRatio > 100 ? '#FF4D4F' : capacityRatio > 80 ? '#FAAD14' : '#52C41A',
                  borderRadius: 3,
                  transition: 'all 0.3s',
                }} />
              </div>
              {capacityRatio > 100 && (
                <div style={{ fontSize: 11, color: '#CF1322', marginTop: 6 }}>
                  ⚠️ 当前章节容量不足以容纳目标字数，请增加章节数或提高每章字数上限
                </div>
              )}
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
              <div>
                <label style={{ fontSize: 13, fontWeight: 600, color: 'var(--color-ink)', display: 'block', marginBottom: 6 }}>
                  章节数 ({config.configChapterCount})
                </label>
                <input type="range" min={1} max={500} value={config.configChapterCount}
                  onChange={e => updateConfig('configChapterCount', Number(e.target.value))}
                  style={{ width: '100%', accentColor: 'var(--color-accent)' }}
                />
                <div style={{ fontSize: 11, color: 'var(--color-muted)', marginTop: 4 }}>
                  预计每章 {Math.round(wordCount / config.configChapterCount).toLocaleString()} 字
                </div>
              </div>
              <div>
                <label style={{ fontSize: 13, fontWeight: 600, color: 'var(--color-ink)', display: 'block', marginBottom: 6 }}>
                  目标结局数 ({config.configTargetEndingCount})
                </label>
                <input type="range" min={1} max={20} value={config.configTargetEndingCount}
                  onChange={e => updateConfig('configTargetEndingCount', Number(e.target.value))}
                  style={{ width: '100%', accentColor: 'var(--color-accent)' }}
                />
                <div style={{ fontSize: 11, color: 'var(--color-muted)', marginTop: 4 }}>
                  {wordCountWan >= 100 && config.configTargetEndingCount < 5
                    ? '⚠️ 史诗级项目建议≥5个结局'
                    : config.configMaxBranchDepth > 1 && config.configTargetEndingCount < 2
                      ? '⚠️ 分支深度>1时需要≥2个结局'
                      : '不同结局提供重玩价值'}
                </div>
              </div>
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
              <div>
                <label style={{ fontSize: 13, fontWeight: 600, color: 'var(--color-ink)', display: 'block', marginBottom: 6 }}>
                  每章最少字数
                  <Tooltip title="每章最少字数不能大于最多字数">
                    <span style={{ marginLeft: 4, cursor: 'help', color: 'var(--color-muted)' }}>ⓘ</span>
                  </Tooltip>
                </label>
                <input type="number" className="input-field" value={config.configMinWordsPerChapter}
                  min={500}
                  max={50000}
                  onChange={e => updateConfig('configMinWordsPerChapter', Number(e.target.value))}
                />
              </div>
              <div>
                <label style={{ fontSize: 13, fontWeight: 600, color: 'var(--color-ink)', display: 'block', marginBottom: 6 }}>
                  每章最多字数
                  <Tooltip title="长篇项目建议每章8000-20000字">
                    <span style={{ marginLeft: 4, cursor: 'help', color: 'var(--color-muted)' }}>ⓘ</span>
                  </Tooltip>
                </label>
                <input type="number" className="input-field" value={config.configMaxWordsPerChapter}
                  min={1000}
                  max={100000}
                  onChange={e => updateConfig('configMaxWordsPerChapter', Number(e.target.value))}
                />
              </div>
            </div>
            <div>
              <label style={{ fontSize: 13, fontWeight: 600, color: 'var(--color-ink)', display: 'block', marginBottom: 8 }}>
                爽点密度 ({config.configWowMomentDensity}个/章)
                <Tooltip title="每章平均设置多少个'爽点/反转/哇塞时刻'。短篇可密集，长篇需节奏控制">
                  <span style={{ marginLeft: 4, cursor: 'help', color: 'var(--color-muted)' }}>ⓘ</span>
                </Tooltip>
              </label>
              <input type="range" min={0.5} max={10} step={0.5} value={config.configWowMomentDensity}
                onChange={e => updateConfig('configWowMomentDensity', Number(e.target.value))}
                style={{ width: '100%', accentColor: 'var(--color-accent)' }}
              />
              <div style={{ fontSize: 11, color: 'var(--color-muted)', marginTop: 4 }}>
                全篇预计约 {Math.round(config.configChapterCount * config.configWowMomentDensity)} 个爽点/反转时刻
              </div>
            </div>
          </div>
        )}

        {/* 分支结局 Tab */}
        {activeConfigTab === 'branch' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
            <div>
              <label style={{ fontSize: 13, fontWeight: 600, color: 'var(--color-ink)', display: 'block', marginBottom: 6 }}>
                最大分支深度 ({config.configMaxBranchDepth}层)
                <Tooltip title="分支树的最大层数。1=线性，2-3=轻度互动，5+=深度互动">
                  <span style={{ marginLeft: 4, cursor: 'help', color: 'var(--color-muted)' }}>ⓘ</span>
                </Tooltip>
              </label>
              <input type="range" min={1} max={10} value={config.configMaxBranchDepth}
                onChange={e => updateConfig('configMaxBranchDepth', Number(e.target.value))}
                style={{ width: '100%', accentColor: 'var(--color-accent)' }}
              />
              <div style={{ fontSize: 11, color: 'var(--color-muted)', marginTop: 4 }}>
                {config.configMaxBranchDepth === 1
                  ? '线性叙事，无分支'
                  : config.configMaxBranchDepth <= 3
                    ? '轻度互动，适合初次体验'
                    : config.configMaxBranchDepth <= 5
                      ? '中度互动，有探索深度'
                      : '深度互动，高重玩价值'}
                {config.configMaxBranchDepth > 1 && config.configTargetEndingCount < 2 && (
                  <span style={{ color: '#CF1322', marginLeft: 8 }}>⚠️ 需要≥2个结局</span>
                )}
              </div>
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
              <div>
                <label style={{ fontSize: 13, fontWeight: 600, color: 'var(--color-ink)', display: 'block', marginBottom: 6 }}>
                  最少分支选项
                  <Tooltip title="每个选择点至少提供几个选项">
                    <span style={{ marginLeft: 4, cursor: 'help', color: 'var(--color-muted)' }}>ⓘ</span>
                  </Tooltip>
                </label>
                <input type="number" className="input-field" value={config.configMinBranchesPerChoice}
                  min={1}
                  max={10}
                  onChange={e => updateConfig('configMinBranchesPerChoice', Number(e.target.value))}
                />
              </div>
              <div>
                <label style={{ fontSize: 13, fontWeight: 600, color: 'var(--color-ink)', display: 'block', marginBottom: 6 }}>
                  最多分支选项
                  <Tooltip title="每个选择点最多提供几个选项">
                    <span style={{ marginLeft: 4, cursor: 'help', color: 'var(--color-muted)' }}>ⓘ</span>
                  </Tooltip>
                </label>
                <input type="number" className="input-field" value={config.configMaxBranchesPerChoice}
                  min={1}
                  max={20}
                  onChange={e => updateConfig('configMaxBranchesPerChoice', Number(e.target.value))}
                />
              </div>
            </div>
            {config.configMinBranchesPerChoice > config.configMaxBranchesPerChoice && (
              <div style={{ fontSize: 11, color: '#CF1322' }}>
                ⚠️ 最少分支选项不能大于最多分支选项
              </div>
            )}
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              <label style={{ fontSize: 13, fontWeight: 600, color: 'var(--color-ink)' }}>
                深度与复杂度
                <Tooltip title="这些参数直接影响AI生成剧本的复杂度和深度">
                  <span style={{ marginLeft: 4, cursor: 'help', color: 'var(--color-muted)' }}>ⓘ</span>
                </Tooltip>
              </label>
              {[
                { label: '世界观深度', value: config.configWorldBuildingDepth, key: 'configWorldBuildingDepth' as const, desc: '世界观构建的详细程度' },
                { label: '角色立体度', value: config.configCharacterDepthTarget, key: 'configCharacterDepthTarget' as const, desc: '角色塑造的复杂程度' },
                { label: '情节复杂度', value: config.configPlotComplexity, key: 'configPlotComplexity' as const, desc: '情节线索的交织程度' },
              ].map(item => (
                <div key={item.key} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <Tooltip title={item.desc}>
                    <span style={{ width: 72, fontSize: 12, color: 'var(--color-muted)', cursor: 'help' }}>{item.label}</span>
                  </Tooltip>
                  <input type="range" min={1} max={10} value={item.value}
                    onChange={e => updateConfig(item.key, Number(e.target.value))}
                    style={{ flex: 1, accentColor: 'var(--color-accent)' }}
                  />
                  <span style={{ fontFamily: 'var(--font-mono)', fontSize: 12, color: 'var(--color-muted)', width: 20 }}>{item.value}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        <div style={{ display: 'flex', gap: 10, justifyContent: 'flex-end' }}>
          <Button onClick={handleClose}>取消</Button>
          <Button
            type="primary"
            onClick={handleCreateProject}
            loading={creatingProject}
            disabled={!newProjectName.trim() || capacityRatio > 100}
          >
            创建项目 · {displayWordCount}万字
          </Button>
        </div>
      </div>
    </Modal>
  )
}
