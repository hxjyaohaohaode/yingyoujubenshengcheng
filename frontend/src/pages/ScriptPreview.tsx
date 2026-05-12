import { useState, useEffect, useMemo, useCallback, useRef } from 'react'
import {
  Card, Button, Select, App, Empty, Spin, Tag, Space,
  Breadcrumb, Typography, Divider, Input, Segmented,
  Modal, Collapse, Tooltip, Badge,
} from 'antd'
import {
  FileTextOutlined, BookOutlined,
  HomeOutlined, ReloadOutlined, PlayCircleOutlined,
  PauseCircleOutlined, LockOutlined, StarFilled,
  RightOutlined, CheckCircleFilled, BranchesOutlined,
  FilterOutlined, EyeOutlined, InfoCircleOutlined,
  StepForwardOutlined,
} from '@ant-design/icons'
import { useProjectStore } from '../stores/projectStore'
import { chaptersApi, scenesApi, foreshadowsApi, charactersApi, type Scene, type Chapter, type Foreshadow, type Character } from '../api/client'

const { Text, Title, Paragraph } = Typography

type ViewType = 'chapter' | 'continuous' | 'scenes'

interface DialogueLine {
  id?: string
  character_id?: string
  character_name?: string
  speaker?: string
  text?: string
  content?: string
  subtext?: string
}

interface ChoiceOption {
  id?: string
  text?: string
  consequence?: string
  consequence_direct?: string
  consequence_indirect?: string
  consequence_long_term?: string
  jump_scene?: string
  branch_target?: string
  hidden?: boolean
  hidden_condition?: string
  moral_alignment?: string
  character_impact?: unknown[]
}

interface ForeshadowOp {
  fs_id?: string
  fs_code?: string
  fs_name?: string
  op_type?: 'plant' | 'reinforce' | 'reveal'
  description?: string
  completed?: boolean
}

interface CausalChain {
  precondition?: string
  catalyst?: string
  direct_result?: string
  indirect_result?: string
  long_term_result?: string
}

interface WowPlan {
  id?: string
  type?: string
  summary?: string
  score?: number
  creativity_type?: string
  dimensions?: { surprise: number; logic: number; emotion: number; resonance: number }
  retrospective_clue?: string
}

interface PlayState {
  isPlaying: boolean
  currentSceneIndex: number
  selectedChoices: Record<string, string>
  revealedConsequences: Record<string, string>
  pausedAtChoice: boolean
  pausedSceneId: string | null
}

const MORAL_COLORS: Record<string, string> = {
  good: '#52c41a',
  neutral: '#3b82f6',
  evil: '#ef4444',
  gray: '#8c8c8c',
}
const MORAL_LABELS: Record<string, string> = {
  good: '善',
  neutral: '中',
  evil: '恶',
  gray: '灰',
}

const FS_OP_CONFIG: Record<string, { icon: string; label: string; color: string }> = {
  plant: { icon: '🌱', label: '埋设', color: '#10b981' },
  reinforce: { icon: '🔄', label: '强化', color: '#3b82f6' },
  reveal: { icon: '💡', label: '回收', color: '#f59e0b' },
}

function safeDialogue(raw: unknown): DialogueLine[] {
  if (!Array.isArray(raw)) return []
  return raw as DialogueLine[]
}

function safeChoices(raw: unknown): ChoiceOption[] {
  if (!Array.isArray(raw)) return []
  return raw as ChoiceOption[]
}

function safeForeshadowOps(raw: unknown): ForeshadowOp[] {
  if (!Array.isArray(raw)) return []
  return raw as ForeshadowOp[]
}

function safeCausalChain(raw: unknown): CausalChain | null {
  if (!raw || typeof raw !== 'object') return null
  return raw as CausalChain
}

function safeWowSpec(raw: unknown): WowPlan[] {
  if (!raw) return []
  if (typeof raw === 'string') {
    try { return JSON.parse(raw) } catch { return [] }
  }
  if (Array.isArray(raw)) return raw as WowPlan[]
  return []
}

function safeCharactersInvolved(raw: unknown): string[] {
  if (!Array.isArray(raw)) return []
  return raw as string[]
}

export default function ScriptPreview() {
  const { notification, modal } = App.useApp()
  const { currentProject } = useProjectStore()
  const projectId = currentProject?.id || ''

  const [loading, setLoading] = useState(false)
  const [chapters, setChapters] = useState<Chapter[]>([])
  const [scenes, setScenes] = useState<Scene[]>([])
  const [foreshadows, setForeshadows] = useState<Foreshadow[]>([])
  const [characters, setCharacters] = useState<Character[]>([])
  const [selectedChapterId, setSelectedChapterId] = useState<string>('')
  const [viewType, setViewType] = useState<ViewType>('continuous')
  const [searchText, setSearchText] = useState('')
  const [fontSize, setFontSize] = useState<'small' | 'normal' | 'large'>('normal')

  const [filterCharacters, setFilterCharacters] = useState<string[]>([])
  const [filterForeshadows, setFilterForeshadows] = useState<string[]>([])

  const [playState, setPlayState] = useState<PlayState>({
    isPlaying: false,
    currentSceneIndex: 0,
    selectedChoices: {},
    revealedConsequences: {},
    pausedAtChoice: false,
    pausedSceneId: null,
  })

  const [expandedChoice, setExpandedChoice] = useState<string | null>(null)
  const [expandedForeshadow, setExpandedForeshadow] = useState<string | null>(null)
  const [expandedWow, setExpandedWow] = useState<string | null>(null)

  const scrollContainerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!projectId) return
    setLoading(true)
    Promise.all([
      chaptersApi.list(projectId),
      scenesApi.list(projectId),
      foreshadowsApi.list(projectId),
      charactersApi.list(projectId),
    ])
      .then(([chData, scData, fsData, charData]) => {
        setChapters(chData)
        setScenes(scData)
        setForeshadows(fsData)
        setCharacters(charData)
        if (chData.length > 0 && !selectedChapterId) {
          setSelectedChapterId(chData[0].id)
        }
      })
      .catch(() => {
        notification.error({ message: '加载数据失败', placement: 'topRight' })
      })
      .finally(() => setLoading(false))
  }, [projectId])

  const characterOptions = useMemo(() => {
    return characters.map(c => ({ value: c.id, label: c.name }))
  }, [characters])

  const foreshadowOptions = useMemo(() => {
    return foreshadows.map(f => ({ value: f.id, label: `${f.fs_code} · ${f.name}` }))
  }, [foreshadows])

  const filteredScenes = useMemo(() => {
    let list = scenes
    if (selectedChapterId) {
      list = list.filter(s => s.chapter_id === selectedChapterId)
    }
    if (searchText) {
      const lower = searchText.toLowerCase()
      list = list.filter(s =>
        s.scene_code?.toLowerCase().includes(lower) ||
        s.narration?.toLowerCase().includes(lower) ||
        s.location?.toLowerCase().includes(lower)
      )
    }
    if (filterCharacters.length > 0) {
      list = list.filter(s => {
        const involved = safeCharactersInvolved(s.characters_involved)
        return filterCharacters.some(fc => involved.includes(fc))
      })
    }
    if (filterForeshadows.length > 0) {
      list = list.filter(s => {
        const ops = safeForeshadowOps(s.foreshadow_ops)
        return ops.some(op => filterForeshadows.includes(op.fs_id || ''))
      })
    }
    list.sort((a, b) => (a.scene_code || '').localeCompare(b.scene_code || ''))
    return list
  }, [scenes, selectedChapterId, searchText, filterCharacters, filterForeshadows])

  const totalWords = useMemo(() => {
    return filteredScenes.reduce((acc, s) => acc + (s.narration?.length || 0), 0)
  }, [filteredScenes])

  const selectedChapter = useMemo(() => {
    return chapters.find(c => c.id === selectedChapterId)
  }, [chapters, selectedChapterId])

  const getFontClass = () => {
    switch (fontSize) {
      case 'small': return 'text-xs leading-relaxed'
      case 'large': return 'text-base leading-relaxed'
      default: return 'text-sm leading-relaxed'
    }
  }

  const getCharName = useCallback((charId: string) => {
    const ch = characters.find(c => c.id === charId)
    return ch?.name || charId
  }, [characters])

  const getForeshadowById = useCallback((fsId: string) => {
    return foreshadows.find(f => f.id === fsId)
  }, [foreshadows])

  const startPlayMode = () => {
    if (filteredScenes.length === 0) {
      notification.warning({ message: '没有可播放的场景', placement: 'topRight' })
      return
    }
    const firstWithChoice = filteredScenes.findIndex(s => safeChoices(s.choices).length > 0)
    setPlayState({
      isPlaying: true,
      currentSceneIndex: 0,
      selectedChoices: {},
      revealedConsequences: {},
      pausedAtChoice: firstWithChoice === 0,
      pausedSceneId: firstWithChoice === 0 ? filteredScenes[0].id : null,
    })
    setViewType('continuous')
  }

  const exitPlayMode = () => {
    setPlayState({
      isPlaying: false,
      currentSceneIndex: 0,
      selectedChoices: {},
      revealedConsequences: {},
      pausedAtChoice: false,
      pausedSceneId: null,
    })
  }

  const handlePlayChoice = (sceneId: string, choiceId: string, choice: ChoiceOption) => {
    const consequence = choice.consequence_direct || choice.consequence || ''
    setPlayState(prev => ({
      ...prev,
      selectedChoices: { ...prev.selectedChoices, [sceneId]: choiceId },
      revealedConsequences: { ...prev.revealedConsequences, [sceneId]: consequence },
      pausedAtChoice: false,
      pausedSceneId: null,
    }))
  }

  const advancePlay = () => {
    setPlayState(prev => {
      const nextIndex = prev.currentSceneIndex + 1
      if (nextIndex >= filteredScenes.length) {
        notification.success({ message: '模拟游玩结束！', placement: 'topRight' })
        return { ...prev, isPlaying: false }
      }
      const nextScene = filteredScenes[nextIndex]
      const hasChoice = safeChoices(nextScene.choices).length > 0
      return {
        ...prev,
        currentSceneIndex: nextIndex,
        pausedAtChoice: hasChoice,
        pausedSceneId: hasChoice ? nextScene.id : null,
      }
    })
  }

  const isSceneVisibleInPlay = (sceneIndex: number) => {
    if (!playState.isPlaying) return true
    return sceneIndex <= playState.currentSceneIndex
  }

  const isSceneChoiceSelected = (sceneId: string, choiceId: string) => {
    return playState.selectedChoices[sceneId] === choiceId
  }

  const renderNarration = (narration: string | null, sceneId: string) => {
    if (!narration) return <p className="text-sm text-gray-400 italic">[暂无内容]</p>

    const lines = narration.split('\n')
    return (
      <div className={getFontClass()}>
        {lines.map((line, i) => {
          const trimmed = line.trim()
          if (!trimmed) return <div key={i} className="h-2" />

          const isBackground = /^(背景|环境|氛围|场景|天气|时间|光影|远处|四周|周围|空气|天色|暮色|晨光|夜色|月光|阳光|雾|雨|雪|风)/.test(trimmed)
            || /^\[.*\]$/.test(trimmed)
            || /^（.*）$/.test(trimmed)
            || trimmed.startsWith('——')

          if (isBackground) {
            return (
              <p key={i} className="mb-3 text-gray-400 dark:text-gray-500 italic indent-8">
                {trimmed}
              </p>
            )
          }

          return (
            <p key={i} className="mb-3 text-gray-800 dark:text-gray-200 indent-8">
              {trimmed}
            </p>
          )
        })}
      </div>
    )
  }

  const renderDialogue = (dialogue: unknown[], sceneId: string) => {
    const lines = safeDialogue(dialogue)
    if (lines.length === 0) return null

    return (
      <div className="mt-4 space-y-3">
        {lines.map((d, i) => {
          const speaker = d.speaker || d.character_name || ''
          const text = d.text || d.content || ''
          const subtext = d.subtext || ''

          return (
            <div key={i} className="ml-2">
              <div className="border-l-3 border-primary-400 dark:border-primary-500 pl-3 py-1 bg-primary-50/30 dark:bg-primary-900/10 rounded-r-md">
                {speaker && (
                  <span className="font-bold text-primary-600 dark:text-primary-400 text-sm">
                    {speaker}
                  </span>
                )}
                {speaker && <span className="text-gray-400 mx-1">：</span>}
                <span className="text-gray-800 dark:text-gray-200 text-sm">{text}</span>
              </div>
              {subtext && (
                <div className="ml-6 mt-0.5 text-xs text-gray-400 dark:text-gray-500 italic">
                  💭 {subtext}
                </div>
              )}
            </div>
          )
        })}
      </div>
    )
  }

  const renderChoices = (choices: unknown[], sceneId: string) => {
    const options = safeChoices(choices)
    if (options.length === 0) return null

    const isExpanded = expandedChoice === sceneId

    return (
      <div className="mt-4">
        <div
          className="border-2 border-amber-400 dark:border-amber-500 rounded-lg p-4 bg-amber-50/50 dark:bg-amber-900/10 cursor-pointer hover:bg-amber-50 dark:hover:bg-amber-900/20 transition-colors"
          onClick={() => setExpandedChoice(isExpanded ? null : sceneId)}
        >
          <div className="flex items-center gap-2 mb-2">
            <BranchesOutlined className="text-amber-500" />
            <span className="font-semibold text-amber-700 dark:text-amber-400 text-sm">互动选择</span>
            <Tag color="gold" className="text-xs">{options.length} 个选项</Tag>
            <RightOutlined className={`text-amber-400 ml-auto transition-transform ${isExpanded ? 'rotate-90' : ''}`} />
          </div>

          <div className="space-y-2">
            {options.map((opt, i) => {
              const isHidden = opt.hidden || false
              const moral = opt.moral_alignment || 'gray'
              const moralColor = MORAL_COLORS[moral] || MORAL_COLORS.gray
              const moralLabel = MORAL_LABELS[moral] || '灰'

              const isSelected = isSceneChoiceSelected(sceneId, opt.id || String(i))
              const isPlayPaused = playState.pausedAtChoice && playState.pausedSceneId === sceneId

              return (
                <div
                  key={i}
                  className={`flex items-start gap-2 p-2 rounded-md border transition-all ${
                    isHidden
                      ? 'border-gray-200 dark:border-slate-600 opacity-50'
                      : isSelected
                        ? 'border-green-400 bg-green-50 dark:bg-green-900/20'
                        : 'border-gray-200 dark:border-slate-600 hover:border-amber-300'
                  }`}
                  onClick={(e) => {
                    e.stopPropagation()
                    if (isPlayPaused && !isHidden) {
                      handlePlayChoice(sceneId, opt.id || String(i), opt)
                    }
                  }}
                >
                  {isHidden && <LockOutlined className="text-gray-400 mt-0.5 shrink-0" />}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className={`text-sm ${isHidden ? 'text-gray-400' : 'text-gray-800 dark:text-gray-200'}`}>
                        {opt.text || `选项 ${i + 1}`}
                      </span>
                      <Tag
                        color={moralColor}
                        className="text-[10px] leading-none px-1.5 py-0"
                        style={{ borderColor: moralColor, color: '#fff' }}
                      >
                        {moralLabel}
                      </Tag>
                      {isSelected && <CheckCircleFilled className="text-green-500" />}
                    </div>
                    {isHidden && opt.hidden_condition && (
                      <div className="text-[10px] text-gray-400 mt-0.5">
                        解锁条件: {opt.hidden_condition}
                      </div>
                    )}
                  </div>
                </div>
              )
            })}
          </div>

          {isExpanded && (
            <div className="mt-3 space-y-3 border-t border-amber-200 dark:border-amber-700 pt-3">
              {options.map((opt, i) => {
                const direct = opt.consequence_direct || opt.consequence || ''
                const indirect = opt.consequence_indirect || ''
                const longTerm = opt.consequence_long_term || ''

                if (!direct && !indirect && !longTerm) return null

                return (
                  <div key={i} className="bg-white dark:bg-slate-800 rounded-md p-3 border border-amber-100 dark:border-amber-800">
                    <div className="font-semibold text-xs text-amber-600 dark:text-amber-400 mb-2">
                      「{opt.text || `选项 ${i + 1}`}」后果链
                    </div>
                    {direct && (
                      <div className="flex items-start gap-2 text-xs mb-1.5">
                        <Tag color="red" className="text-[10px] shrink-0">直接</Tag>
                        <span className="text-gray-600 dark:text-gray-400">{direct}</span>
                      </div>
                    )}
                    {indirect && (
                      <div className="flex items-start gap-2 text-xs mb-1.5">
                        <Tag color="blue" className="text-[10px] shrink-0">间接</Tag>
                        <span className="text-gray-600 dark:text-gray-400">{indirect}</span>
                      </div>
                    )}
                    {longTerm && (
                      <div className="flex items-start gap-2 text-xs">
                        <Tag color="purple" className="text-[10px] shrink-0">远期</Tag>
                        <span className="text-gray-600 dark:text-gray-400">{longTerm}</span>
                      </div>
                    )}
                  </div>
                )
              })}
            </div>
          )}
        </div>

        {playState.revealedConsequences[sceneId] && (
          <div className="mt-2 p-3 bg-green-50 dark:bg-green-900/10 border border-green-200 dark:border-green-800 rounded-lg">
            <div className="flex items-center gap-2 mb-1">
              <CheckCircleFilled className="text-green-500" />
              <span className="text-xs font-semibold text-green-600 dark:text-green-400">选择后果</span>
            </div>
            <p className="text-xs text-gray-600 dark:text-gray-400 m-0">
              {playState.revealedConsequences[sceneId]}
            </p>
          </div>
        )}
      </div>
    )
  }

  const renderForeshadowOps = (ops: unknown[], sceneId: string) => {
    const foreshadowOps = safeForeshadowOps(ops)
    if (foreshadowOps.length === 0) return null

    const isExpanded = expandedForeshadow === sceneId

    return (
      <div className="mt-3 flex flex-wrap gap-2">
        {foreshadowOps.map((op, i) => {
          const opType = op.op_type || 'plant'
          const config = FS_OP_CONFIG[opType] || FS_OP_CONFIG.plant
          const fsData = op.fs_id ? getForeshadowById(op.fs_id) : null

          return (
            <Tag
              key={i}
              color={config.color}
              className="cursor-pointer hover:opacity-80 transition-opacity px-2 py-0.5 text-xs"
              onClick={() => {
                if (isExpanded && expandedForeshadow === sceneId) {
                  setExpandedForeshadow(null)
                } else {
                  setExpandedForeshadow(sceneId)
                }
              }}
            >
              <span className="mr-1">{config.icon}</span>
              <span className="font-semibold">{op.fs_code || '未知'}</span>
              <span className="mx-1 text-white/70">·</span>
              <span>{config.label}</span>
              {op.description && <span className="ml-1 text-white/80">: {op.description}</span>}
            </Tag>
          )
        })}

        {isExpanded && (
          <div className="w-full mt-2 space-y-2">
            {foreshadowOps.map((op, i) => {
              const fsData = op.fs_id ? getForeshadowById(op.fs_id) : null
              if (!fsData) return null

              return (
                <div key={i} className="bg-gray-50 dark:bg-slate-800 border border-gray-200 dark:border-slate-600 rounded-md p-3">
                  <div className="flex items-center gap-2 mb-2">
                    <Tag color={FS_OP_CONFIG[op.op_type || 'plant']?.color} className="text-xs">
                      {FS_OP_CONFIG[op.op_type || 'plant']?.icon} {FS_OP_CONFIG[op.op_type || 'plant']?.label}
                    </Tag>
                    <span className="font-semibold text-sm">{fsData.name}</span>
                    <span className="text-xs text-gray-400 font-mono">{fsData.fs_code}</span>
                  </div>
                  <div className="space-y-1.5 text-xs">
                    {fsData.surface_layer && (
                      <div className="flex items-start gap-2">
                        <span className="text-gray-400 shrink-0 w-12">表面层</span>
                        <span className="text-gray-600 dark:text-gray-400">{fsData.surface_layer}</span>
                      </div>
                    )}
                    {fsData.deep_layer && (
                      <div className="flex items-start gap-2">
                        <span className="text-blue-400 shrink-0 w-12">深层</span>
                        <span className="text-blue-600 dark:text-blue-400">{fsData.deep_layer}</span>
                      </div>
                    )}
                    {fsData.truth_layer && (
                      <div className="flex items-start gap-2">
                        <span className="text-amber-400 shrink-0 w-12">真相层</span>
                        <span className="text-amber-600 dark:text-amber-400">{fsData.truth_layer}</span>
                      </div>
                    )}
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </div>
    )
  }

  const renderWowMoment = (scene: Scene) => {
    if (!scene.is_wow_moment) return null

    const wowPlans = safeWowSpec(scene.wow_spec)
    const isExpanded = expandedWow === scene.id

    return (
      <div className="mt-3">
        <div
          className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-gradient-to-r from-amber-400 to-yellow-300 dark:from-amber-600 dark:to-yellow-500 cursor-pointer hover:shadow-md transition-shadow"
          onClick={() => setExpandedWow(isExpanded ? null : scene.id)}
        >
          <StarFilled className="text-white text-sm" />
          <span className="text-white font-bold text-sm">★ 哇塞时刻</span>
          {scene.wow_type && (
            <span className="text-white/80 text-xs ml-1">({scene.wow_type})</span>
          )}
        </div>

        {isExpanded && (
          <div className="mt-2 p-3 bg-gradient-to-br from-amber-50 to-yellow-50 dark:from-amber-900/10 dark:to-yellow-900/10 border border-amber-200 dark:border-amber-700 rounded-lg">
            {scene.wow_type && (
              <div className="flex items-center gap-2 mb-2">
                <span className="text-xs text-gray-400">创意类型:</span>
                <Tag color="purple" className="text-xs">{scene.wow_type}</Tag>
              </div>
            )}
            {wowPlans.length > 0 ? (
              <div className="space-y-2">
                {wowPlans.map((plan, i) => (
                  <div key={i} className="bg-white dark:bg-slate-800 rounded-md p-2.5 border border-amber-100 dark:border-amber-800">
                    <div className="flex items-center gap-2 mb-1">
                      <Tag color="purple" className="text-[10px]">{plan.creativity_type || plan.type || '方案'}</Tag>
                      <span className="text-xs text-gray-400">评分: {plan.score ?? '-'}</span>
                    </div>
                    <p className="text-xs text-gray-600 dark:text-gray-400 m-0 mb-1.5">{plan.summary}</p>
                    {plan.dimensions && (
                      <div className="flex gap-3 text-[10px]">
                        <span className="text-red-400">意外性: {plan.dimensions.surprise ?? '-'}</span>
                        <span className="text-blue-400">逻辑性: {plan.dimensions.logic ?? '-'}</span>
                        <span className="text-pink-400">情感冲击: {plan.dimensions.emotion ?? '-'}</span>
                        <span className="text-green-400">共鸣度: {plan.dimensions.resonance ?? '-'}</span>
                      </div>
                    )}
                    {plan.retrospective_clue && (
                      <div className="mt-1.5 text-[10px] text-amber-600 dark:text-amber-400">
                        🔍 回望线索: {plan.retrospective_clue}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-xs text-gray-400 italic">暂无哇塞方案详情</div>
            )}
          </div>
        )}
      </div>
    )
  }

  const renderCausalChain = (causalChain: unknown) => {
    const chain = safeCausalChain(causalChain)
    if (!chain) return null
    const hasContent = chain.precondition || chain.catalyst || chain.direct_result || chain.indirect_result || chain.long_term_result
    if (!hasContent) return null

    return (
      <div className="mt-3 p-3 bg-gray-50 dark:bg-slate-800/50 border border-gray-200 dark:border-slate-600 rounded-lg">
        <div className="text-xs text-gray-400 font-semibold mb-2 flex items-center gap-1">
          <InfoCircleOutlined /> 因果链
        </div>
        <div className="space-y-1.5 text-xs">
          {chain.precondition && (
            <div className="flex items-start gap-2">
              <Tag color="default" className="text-[10px] shrink-0">前提</Tag>
              <span className="text-gray-600 dark:text-gray-400">{chain.precondition}</span>
            </div>
          )}
          {chain.catalyst && (
            <div className="flex items-start gap-2">
              <Tag color="orange" className="text-[10px] shrink-0">催化</Tag>
              <span className="text-gray-600 dark:text-gray-400">{chain.catalyst}</span>
            </div>
          )}
          {chain.direct_result && (
            <div className="flex items-start gap-2">
              <Tag color="red" className="text-[10px] shrink-0">直接</Tag>
              <span className="text-gray-600 dark:text-gray-400">{chain.direct_result}</span>
            </div>
          )}
          {chain.indirect_result && (
            <div className="flex items-start gap-2">
              <Tag color="blue" className="text-[10px] shrink-0">间接</Tag>
              <span className="text-gray-600 dark:text-gray-400">{chain.indirect_result}</span>
            </div>
          )}
          {chain.long_term_result && (
            <div className="flex items-start gap-2">
              <Tag color="purple" className="text-[10px] shrink-0">远期</Tag>
              <span className="text-gray-600 dark:text-gray-400">{chain.long_term_result}</span>
            </div>
          )}
        </div>
      </div>
    )
  }

  const renderSceneCard = (scene: Scene, index: number) => {
    const isInPlay = playState.isPlaying
    const isVisible = isSceneVisibleInPlay(index)
    const isCurrentPlayScene = isInPlay && index === playState.currentSceneIndex
    const isPausedHere = playState.pausedAtChoice && playState.pausedSceneId === scene.id
    const hasChoiceSelected = !!playState.selectedChoices[scene.id]

    const involvedChars = safeCharactersInvolved(scene.characters_involved)
    const choices = safeChoices(scene.choices)
    const fsOps = safeForeshadowOps(scene.foreshadow_ops)

    return (
      <div
        key={scene.id}
        className={`mb-6 transition-all duration-300 ${
          isInPlay && !isVisible ? 'opacity-0 max-h-0 overflow-hidden' : ''
        } ${
          isCurrentPlayScene ? 'ring-2 ring-primary-400 ring-offset-2 dark:ring-offset-slate-900' : ''
        }`}
        id={`scene-${scene.id}`}
      >
        <div className={`border border-gray-200 dark:border-slate-700 rounded-lg p-5 bg-white dark:bg-slate-900 ${
          isPausedHere ? 'border-amber-400 dark:border-amber-500 shadow-lg shadow-amber-100 dark:shadow-amber-900/20' : ''
        }`}>
          <div className="flex items-center gap-2 mb-3 flex-wrap">
            <Tag color="blue" className="font-mono text-xs">{scene.scene_code}</Tag>
            <Tag className="text-xs">{scene.scene_type || 'dialogue'}</Tag>
            {scene.location && <Tag color="purple" className="text-xs">{scene.location}</Tag>}
            {scene.emotion_level != null && (
              <span className="text-xs text-gray-400">情感强度: {scene.emotion_level}/10</span>
            )}
            {involvedChars.length > 0 && (
              <div className="flex gap-1">
                {involvedChars.map(charId => (
                  <Tag key={charId} color="cyan" className="text-[10px]">
                    {getCharName(charId)}
                  </Tag>
                ))}
              </div>
            )}
            {isPausedHere && (
              <Tag color="warning" className="text-xs animate-pulse">
                <PauseCircleOutlined /> 请选择
              </Tag>
            )}
            {hasChoiceSelected && isInPlay && (
              <Tag color="success" className="text-xs">
                <CheckCircleFilled /> 已选择
              </Tag>
            )}
            <span className="text-xs text-gray-400 ml-auto">{scene.narration?.length || 0} 字</span>
          </div>

          {renderNarration(scene.narration, scene.id)}
          {renderDialogue(scene.dialogue, scene.id)}
          {renderForeshadowOps(scene.foreshadow_ops, scene.id)}
          {renderWowMoment(scene)}
          {renderCausalChain(scene.causal_chain)}
          {renderChoices(scene.choices, scene.id)}
        </div>
      </div>
    )
  }

  if (!projectId) {
    return (
      <div style={{ fontFamily: 'var(--font-family)' }}>
        <h2 className="section-title" style={{ fontSize: 24 }}>互动影游预览</h2>
        <div className="card-surface" style={{ textAlign: 'center', padding: 48 }}>
          <Empty description={<span className="text-muted">请先创建或选择一个项目</span>} />
        </div>
      </div>
    )
  }

  return (
    <div style={{ fontFamily: 'var(--font-family)', display: 'flex', flexDirection: 'column', height: 'calc(100vh - 80px)' }}>
      <Breadcrumb
        className="mb-4 text-xs"
        items={[
          { title: <><HomeOutlined className="mr-1" />项目</> },
          { title: <><BookOutlined className="mr-1" />{currentProject?.name || '互动影游预览'}</> },
          { title: '互动影游预览' },
        ]}
      />

      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16, flexWrap: 'wrap', gap: 8 }}>
        <div>
          <h2 className="section-title" style={{ fontSize: 24 }}>互动影游预览</h2>
          <p className="text-muted" style={{ margin: '4px 0 0' }}>
            {scenes.length} 个场景 · {totalWords.toLocaleString()} 字
            {playState.isPlaying && <Tag color="processing" className="ml-2 text-xs">模拟游玩中</Tag>}
          </p>
        </div>
        <Space wrap>
          <Segmented
            size="small"
            value={fontSize}
            onChange={(v) => setFontSize(v as typeof fontSize)}
            options={[
              { label: '小', value: 'small' },
              { label: '中', value: 'normal' },
              { label: '大', value: 'large' },
            ]}
          />
          {playState.isPlaying ? (
            <>
              <Button
                size="small"
                type="primary"
                icon={<StepForwardOutlined />}
                onClick={advancePlay}
                disabled={playState.pausedAtChoice}
              >
                下一步
              </Button>
              <Button size="small" danger onClick={exitPlayMode}>
                退出游玩
              </Button>
            </>
          ) : (
            <Button
              size="small"
              type="primary"
              icon={<PlayCircleOutlined />}
              onClick={startPlayMode}
            >
              模拟游玩
            </Button>
          )}
          <Button size="small" icon={<ReloadOutlined />} onClick={() => {
            if (projectId) {
              setLoading(true)
              Promise.all([
                chaptersApi.list(projectId),
                scenesApi.list(projectId),
                foreshadowsApi.list(projectId),
                charactersApi.list(projectId),
              ])
                .then(([ch, sc, fs, char]) => { setChapters(ch); setScenes(sc); setForeshadows(fs); setCharacters(char) })
                .finally(() => setLoading(false))
            }
          }}>
            刷新
          </Button>
        </Space>
      </div>

      <div className="flex items-center gap-3 mb-4 flex-wrap">
        <Select
          value={selectedChapterId}
          onChange={v => setSelectedChapterId(v)}
          placeholder="选择章节"
          style={{ width: 220 }}
          options={[
            { value: '', label: '全部章节' },
            ...chapters.map(c => ({
              value: c.id,
              label: `第${c.chapter_number}章 · ${c.title || '未命名'}`,
            })),
          ]}
        />
        <Select
          mode="multiple"
          value={filterCharacters}
          onChange={v => setFilterCharacters(v)}
          placeholder="筛选角色"
          style={{ minWidth: 180, maxWidth: 300 }}
          options={characterOptions}
          allowClear
          maxTagCount={2}
          maxTagPlaceholder={(omitted) => `+${omitted.length}`}
        />
        <Select
          mode="multiple"
          value={filterForeshadows}
          onChange={v => setFilterForeshadows(v)}
          placeholder="筛选伏笔"
          style={{ minWidth: 180, maxWidth: 300 }}
          options={foreshadowOptions}
          allowClear
          maxTagCount={2}
          maxTagPlaceholder={(omitted) => `+${omitted.length}`}
        />
        <Input.Search
          placeholder="搜索场景内容..."
          value={searchText}
          onChange={e => setSearchText(e.target.value)}
          style={{ width: 200 }}
          allowClear
        />
        <Segmented
          size="small"
          value={viewType}
          onChange={(v) => setViewType(v as ViewType)}
          options={[
            { label: '章节视图', value: 'chapter' },
            { label: '沉浸阅读', value: 'continuous' },
            { label: '场景列表', value: 'scenes' },
          ]}
        />
      </div>

      {selectedChapter && viewType === 'chapter' && (
        <Card size="small" className="mb-3 bg-blue-50 dark:bg-blue-900/10 border-blue-200 dark:border-blue-800">
          <div className="flex items-center gap-2">
            <BookOutlined className="text-blue-500" />
            <span className="font-semibold">
              第{selectedChapter.chapter_number}章 · {selectedChapter.title || '未命名'}
            </span>
            {selectedChapter.summary && (
              <span className="text-xs text-gray-500 dark:text-gray-400 ml-2">
                {selectedChapter.summary}
              </span>
            )}
          </div>
        </Card>
      )}

      <div ref={scrollContainerRef} className="flex-1 overflow-auto border border-gray-200 dark:border-slate-700 rounded-lg bg-white dark:bg-slate-900">
        {loading ? (
          <div className="flex items-center justify-center py-20">
            <Spin><div className="py-12 text-gray-400">加载剧本内容...</div></Spin>
          </div>
        ) : filteredScenes.length === 0 ? (
          <div className="flex items-center justify-center py-20">
            <Empty description="暂无场景内容" />
          </div>
        ) : (
          <div className="p-6">
            {viewType === 'scenes' ? (
              <div className="space-y-6">
                {filteredScenes.map((scene, idx) => renderSceneCard(scene, idx))}
              </div>
            ) : (
              <div className={viewType === 'continuous' ? getFontClass() : ''}>
                {viewType === 'continuous' && selectedChapter && (
                  <div className="mb-6 text-center">
                    <Title level={3} className="!mb-1">
                      第{selectedChapter.chapter_number}章 · {selectedChapter.title || '未命名'}
                    </Title>
                    {selectedChapter.summary && (
                      <Text type="secondary" className="text-sm">{selectedChapter.summary}</Text>
                    )}
                    <Divider />
                  </div>
                )}

                {filteredScenes.map((scene, idx) => (
                  <div key={scene.id} className="mb-6">
                    {viewType === 'continuous' && (
                      <div className="mb-2 flex items-center gap-2">
                        <Tag color="blue" className="font-mono text-xs">{scene.scene_code}</Tag>
                        {scene.location && <Tag className="text-xs">{scene.location}</Tag>}
                        {scene.is_wow_moment && (
                          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-gradient-to-r from-amber-400 to-yellow-300 text-white text-xs font-bold">
                            <StarFilled /> ★
                          </span>
                        )}
                        {safeForeshadowOps(scene.foreshadow_ops).map((op, i) => {
                          const config = FS_OP_CONFIG[op.op_type || 'plant']
                          return (
                            <Tag key={i} color={config.color} className="text-[10px]">
                              {config.icon} {config.label}
                            </Tag>
                          )
                        })}
                        {safeChoices(scene.choices).length > 0 && (
                          <Tag color="gold" className="text-[10px]">
                            <BranchesOutlined /> {safeChoices(scene.choices).length}个选择
                          </Tag>
                        )}
                      </div>
                    )}

                    {viewType === 'continuous' ? (
                      <>
                        {renderNarration(scene.narration, scene.id)}
                        {renderDialogue(scene.dialogue, scene.id)}
                        {renderForeshadowOps(scene.foreshadow_ops, scene.id)}
                        {renderWowMoment(scene)}
                        {renderCausalChain(scene.causal_chain)}
                        {renderChoices(scene.choices, scene.id)}
                      </>
                    ) : (
                      renderSceneCard(scene, idx)
                    )}

                    {viewType === 'continuous' && idx < filteredScenes.length - 1 && (
                      <div className="text-center text-gray-300 dark:text-gray-600 my-4">* * *</div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>

      <div className="flex items-center justify-between mt-3 text-xs text-gray-400 dark:text-gray-500">
        <span>共 {filteredScenes.length} 个场景 · {totalWords.toLocaleString()} 字</span>
        <Space>
          <Tag className="text-xs">场景 {scenes.length}</Tag>
          <Tag className="text-xs">章节 {chapters.length}</Tag>
          <Tag className="text-xs">伏笔 {foreshadows.length}</Tag>
        </Space>
      </div>
    </div>
  )
}
