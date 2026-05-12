import { useState, useEffect, useRef, useMemo, useCallback } from 'react'
import {
  Card, Button, Tag, Drawer, Input, Select, Slider, Row, Col,
  App, Popconfirm, Tooltip, Empty, Space, Progress, Badge, Spin,
  Timeline,
} from 'antd'
import {
  PlusOutlined, TeamOutlined, RobotOutlined, EditOutlined,
  DeleteOutlined, CloseOutlined, SaveOutlined, NodeIndexOutlined,
  UserOutlined, ThunderboltOutlined, MinusCircleOutlined, PlusCircleOutlined,
  ZoomInOutlined, ZoomOutOutlined, AimOutlined, ReloadOutlined,
  HeartOutlined, DashboardOutlined, StarOutlined, FireOutlined,
  BulbOutlined, TrophyOutlined, BranchesOutlined, EyeInvisibleOutlined,
  WarningOutlined, ClockCircleOutlined,
} from '@ant-design/icons'
import * as d3 from 'd3'
import { useProjectStore } from '../stores/projectStore'
import { useAgentStore } from '../stores/agentStore'
import { api, charactersApi, relationsApi, scenesApi, Character, CharacterRelation } from '../api/client'
import { eventBus, DataEvents } from '../services/eventBus'
import ConfirmDialog from '../components/ConfirmDialog'

const { TextArea } = Input

interface CharacterData {
  id: string; project_id: string; char_code: string
  name: string; role_type: string | null
  background: string | null; core_goal: string | null; core_fear: string | null
  surface_image: string | null; true_self: string | null
  language_style: string | null; catchphrase: string | null
  dark_secret: string | null; arc_description: string | null
  behavior_inevitable: string[]; behavior_never: string[]; behavior_conditional: string[]
  status: string
}

interface RelationData {
  id: string; char_a_id: string; char_b_id: string
  relation_type: string | null; trust: number; favor: number
  info_known_a_about_b: unknown[]; info_known_b_about_a: unknown[]
  info_asymmetry: Record<string, unknown>
  is_hidden: boolean; arc_direction: string
  trigger_condition: string | null; arc_milestones: unknown[]
}

const ROLE_LABELS: Record<string, string> = {
  protagonist: '主角', antagonist: '反派', love_interest: '挚爱',
  rival: '对手', mentor: '导师', sidekick: '伙伴',
  supporting: '配角', cameo: '客串', foil: '对照角色',
}
const ROLE_COLORS: Record<string, string> = {
  protagonist: '#3b82f6', antagonist: '#ef4444', love_interest: '#ec4899',
  rival: '#f59e0b', mentor: '#8b5cf6', sidekick: '#10b981',
  supporting: '#6b7280', cameo: '#9ca3af', foil: '#06b6d4',
}
const REL_TYPE_LABELS: Record<string, string> = {
  family: '亲属', lover: '恋人', friend: '挚友', enemy: '宿敌',
  mentor_student: '师徒', colleague: '同僚', rival: '对手',
  stranger: '陌路', admirer: '仰慕', betrayer: '背叛',
  protector: '守护', manipulator: '操控',
  secret_ally: '秘密盟友', hidden_enemy: '隐藏仇敌',
  debtor: '债务人', blackmailer: '要挟者',
  surrogate: '替身', former_bond: '昔日羁绊',
  information_broker: '信息掮客',
}
const REL_TYPE_COLORS: Record<string, string> = {
  family: '#8b5cf6', lover: '#ec4899', friend: '#10b981', enemy: '#ef4444',
  mentor_student: '#3b82f6', colleague: '#f59e0b', rival: '#f97316',
  stranger: '#9ca3af', admirer: '#d946ef', betrayer: '#dc2626',
  protector: '#06b6d4', manipulator: '#4f46e5',
  secret_ally: '#7c3aed', hidden_enemy: '#991b1b',
  debtor: '#b45309', blackmailer: '#7f1d1d',
  surrogate: '#6d28d9', former_bond: '#6b7280',
  information_broker: '#0e7490',
}

function apiCharToCharData(c: Character): CharacterData {
  return {
    id: c.id, project_id: c.project_id,
    char_code: c.char_code, name: c.name, role_type: c.role_type,
    background: c.background, core_goal: c.core_goal, core_fear: c.core_fear,
    surface_image: c.surface_image, true_self: c.true_self,
    language_style: c.language_style, catchphrase: c.catchphrase,
    dark_secret: (c as any).dark_secret || null,
    arc_description: c.arc_description,
    behavior_inevitable: Array.isArray(c.behavior_inevitable) ? c.behavior_inevitable.map(String) : [],
    behavior_never: Array.isArray(c.behavior_never) ? c.behavior_never.map(String) : [],
    behavior_conditional: Array.isArray(c.behavior_conditional) ? c.behavior_conditional.map(String) : [],
    status: c.status,
  }
}

export default function Characters() {
  const { notification } = App.useApp()
  const { currentProject } = useProjectStore()
  const { updateAgent } = useAgentStore()
  const [characters, setCharacters] = useState<CharacterData[]>([])
  const [relations, setRelations] = useState<RelationData[]>([])
  const [selectedChar, setSelectedChar] = useState<CharacterData | null>(null)
  const [drawerOpen, setDrawerOpen] = useState(false)
  const [editing, setEditing] = useState(false)
  const [editData, setEditData] = useState<CharacterData | null>(null)
  const [deleteConfirm, setDeleteConfirm] = useState<string | null>(null)
  const [relEditor, setRelEditor] = useState<{
    relId: string; a: string; b: string; type: string; trust: number; favor: number
    arcDirection: string; triggerCondition: string | null; arcMilestones: unknown[]
    infoAsymmetry: Record<string, unknown>; infoKnownAAboutB: unknown[]; infoKnownBAboutA: unknown[]
    isHidden: boolean
  } | null>(null)
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [aiGenerating, setAiGenerating] = useState(false)
  const [arcDrawerOpen, setArcDrawerOpen] = useState(false)
  const [graphScaling, setGraphScaling] = useState(d3.zoomIdentity)
  const svgRef = useRef<SVGSVGElement>(null)
  const abortRef = useRef<AbortController | null>(null)

  const fetchData = async (signal?: AbortSignal) => {
    if (!currentProject?.id) return
    setLoading(true)
    try {
      const [chars, rels] = await Promise.all([
        charactersApi.list(currentProject.id, undefined, signal),
        relationsApi.list(currentProject.id, signal),
      ])
      if (signal?.aborted) { setLoading(false); return }
      setCharacters(chars.map(apiCharToCharData))
      setRelations(rels.map(r => ({
        id: r.id, char_a_id: r.char_a_id, char_b_id: r.char_b_id,
        relation_type: r.relation_type, trust: r.trust, favor: r.favor,
        info_known_a_about_b: r.info_known_a_about_b || [],
        info_known_b_about_a: r.info_known_b_about_a || [],
        info_asymmetry: r.info_asymmetry || {},
        is_hidden: r.is_hidden || false,
        arc_direction: r.arc_direction || 'stable',
        trigger_condition: r.trigger_condition || null,
        arc_milestones: r.arc_milestones || [],
      })))
    } catch (e: any) {
      if (signal?.aborted || e?.name === 'AbortError') { setLoading(false); return }
      notification.error({ message: '加载角色数据失败', description: e?.detail || e?.message, placement: 'topRight' })
    }
    setLoading(false)
  }

  const refreshData = useCallback(() => {
    abortRef.current?.abort()
    const ctrl = new AbortController()
    abortRef.current = ctrl
    return fetchData(ctrl.signal)
  }, [currentProject?.id])

  useEffect(() => {
    abortRef.current?.abort()
    const ctrl = new AbortController()
    abortRef.current = ctrl
    fetchData(ctrl.signal)
    return () => { ctrl.abort() }
  }, [currentProject?.id])

  useEffect(() => {
    const unsubs = [
      eventBus.on(DataEvents.SCENE_UPDATED, () => { refreshData() }),
      eventBus.on(DataEvents.CHAPTER_UPDATED, () => { refreshData() }),
      eventBus.on(DataEvents.PROJECT_SWITCHED, () => { refreshData() }),
      eventBus.on(DataEvents.CHARACTER_CREATED, () => { refreshData() }),
      eventBus.on(DataEvents.CHARACTER_UPDATED, () => { refreshData() }),
      eventBus.on(DataEvents.CHARACTER_DELETED, () => { refreshData() }),
      eventBus.on(DataEvents.RELATION_CREATED, () => { refreshData() }),
      eventBus.on(DataEvents.RELATION_UPDATED, () => { refreshData() }),
      eventBus.on(DataEvents.RELATION_DELETED, () => { refreshData() }),
    ]
    return () => unsubs.forEach(u => u())
  }, [refreshData])

  const charRelations = useMemo(() => {
    if (!selectedChar) return []
    return relations
      .filter(r => r.char_a_id === selectedChar.id || r.char_b_id === selectedChar.id)
      .map(r => {
        const otherId = r.char_a_id === selectedChar.id ? r.char_b_id : r.char_a_id
        const other = characters.find(c => c.id === otherId)
        return { ...r, otherId, otherName: other?.name || otherId.slice(0, 8), otherRole: other?.role_type }
      })
  }, [selectedChar, relations, characters])

  const openDrawer = (char: CharacterData) => {
    setSelectedChar(char); setEditing(false); setEditData(null); setDrawerOpen(true)
  }
  const startEdit = () => { setEditData({ ...selectedChar! }); setEditing(true) }

  const saveEdit = async () => {
    if (!editData || !currentProject?.id) return
    setSaving(true)
    try {
      await charactersApi.update(currentProject.id, editData.id, editData as any)
      setCharacters(prev => prev.map(c => c.id === editData.id ? editData : c))
      setSelectedChar(editData); setEditing(false)
      eventBus.emit(DataEvents.CHARACTER_UPDATED, { id: editData.id, name: editData.name })
      notification.success({ message: '角色已保存', placement: 'topRight' })
    } catch (e: any) {
      notification.error({ message: '保存失败', description: e?.detail || e?.message, placement: 'topRight' })
    }
    setSaving(false)
  }

  const handleDelete = async () => {
    if (!deleteConfirm || !currentProject?.id) return
    try {
      await charactersApi.delete(currentProject.id, deleteConfirm)
      setCharacters(prev => prev.filter(c => c.id !== deleteConfirm))
      setRelations(prev => prev.filter(r => r.char_a_id !== deleteConfirm && r.char_b_id !== deleteConfirm))
      if (selectedChar?.id === deleteConfirm) { setDrawerOpen(false); setSelectedChar(null) }
      eventBus.emit(DataEvents.CHARACTER_DELETED, { id: deleteConfirm })
      notification.success({ message: '角色已删除', placement: 'topRight' })
    } catch (e: any) { notification.error({ message: '删除失败', description: e?.detail || e?.message, placement: 'topRight' }) }
    setDeleteConfirm(null)
  }

  const handleAIGenerate = async () => {
    if (!currentProject?.id) return
    setAiGenerating(true)
    updateAgent('创作Agent', { status: 'busy', currentTask: '分析剧本,生成完整角色阵容与关系网络' })
    try {
      let characters_narrative = ''
      try {
        const scenes = await scenesApi.list(currentProject.id)
        characters_narrative = scenes
          .slice(0, 20)
          .map((s: any) => s.narration || '')
          .filter(Boolean)
          .join('\n')
          .slice(0, 3000)
      } catch { /* no scenes yet */ }

      const res = await api.post<{ proposals: any[] }>(`/ai/character-gen/${currentProject.id}`, {
        project_name: currentProject.name,
        genre: currentProject.config?.genre || '未设定',
        target_words: currentProject.config?.target_word_count || 500000,
        existing_count: characters.length,
        existing_names: characters.map(c => c.name).join(', '),
        script_context: characters_narrative,
      })
      if (res.proposals && res.proposals.length > 0) {
        const created: CharacterData[] = []
        const maxCreate = Math.min(res.proposals.length, 50)
        for (const p of res.proposals.slice(0, maxCreate)) {
          try {
            const newChar = await charactersApi.create(currentProject.id, {
              name: p.name || `角色${characters.length + created.length + 1}`,
              char_code: p.char_code || `CHAR-${String(characters.length + created.length + 1).padStart(3, '0')}`,
              role_type: p.role_type || 'supporting',
              core_goal: p.core_goal || p.motivation || '',
              core_fear: p.core_fear || '',
              background: p.background || '',
              surface_image: p.surface_image || '',
              true_self: p.true_self || '',
              language_style: p.language_style || '',
              catchphrase: p.catchphrase || '',
              dark_secret: p.dark_secret || '',
              arc_description: p.arc_description || '',
              behavior_inevitable: p.behavior_inevitable || [],
              behavior_never: p.behavior_never || [],
              behavior_conditional: p.behavior_conditional || [],
              status: 'active',
            })
            created.push(apiCharToCharData(newChar))
          } catch { /* skip */ }
        }
        if (created.length > 0) {
          setCharacters(prev => [...prev, ...created])

          try {
            const relNetRes = await api.post<{ relations: any[] }>(
              `/ai/relation-network-gen/${currentProject.id}`
            )

            if (relNetRes.relations && relNetRes.relations.length > 0) {
              const allChars = [...characters, ...created]
              const nameToId = new Map<string, string>()
              allChars.forEach(c => {
                if (c.name) {
                  nameToId.set(c.name, c.id)
                  nameToId.set(c.name.toLowerCase(), c.id)
                  nameToId.set(c.name.replace(/\s+/g, ''), c.id)
                  nameToId.set(c.name.replace(/\s+/g, '').toLowerCase(), c.id)
                }
                if (c.char_code) {
                  nameToId.set(c.char_code, c.id)
                }
              })

              const resolveCharId = (raw: string | undefined): string | undefined => {
                if (!raw) return undefined
                const key = String(raw).trim()
                if (nameToId.has(key)) return nameToId.get(key)
                const lower = key.toLowerCase()
                if (nameToId.has(lower)) return nameToId.get(lower)
                const normalized = key.replace(/\s+/g, '')
                if (nameToId.has(normalized)) return nameToId.get(normalized)
                const normalizedLower = normalized.toLowerCase()
                if (nameToId.has(normalizedLower)) return nameToId.get(normalizedLower)
                for (const [mapKey, mapId] of nameToId) {
                  if (mapKey.toLowerCase().includes(lower) || lower.includes(mapKey.toLowerCase())) {
                    return mapId
                  }
                }
                return undefined
              }

              let createdRels = 0
              for (const rel of relNetRes.relations) {
                const aId = resolveCharId(rel.char_a_name) || resolveCharId(rel.char_a)
                const bId = resolveCharId(rel.char_b_name) || resolveCharId(rel.char_b)
                if (aId && bId && aId !== bId) {
                  try {
                    await relationsApi.create(currentProject.id, {
                      char_a_id: aId,
                      char_b_id: bId,
                      relation_type: rel.relation_type || 'friend',
                      trust: typeof rel.trust === 'number' ? Math.max(0, Math.min(100, rel.trust)) : 50,
                      favor: typeof rel.favor === 'number' ? Math.max(0, Math.min(100, rel.favor)) : 50,
                      info_known_a_about_b: rel.info_known_a_about_b || [],
                      info_known_b_about_a: rel.info_known_b_about_a || [],
                    })
                    createdRels++
                  } catch { /* skip */ }
                }
              }
              if (createdRels === 0) {
                notification.info({ message: '关系名称匹配失败', description: `AI生成了${relNetRes.relations.length}条关系但无法匹配到角色，可手动创建`, placement: 'topRight' })
              }
            } else {
              notification.info({ message: 'AI未生成关系网络', description: '可手动创建角色关系或重新生成', placement: 'topRight' })
            }

            const rels2 = await relationsApi.list(currentProject.id)
            setRelations(rels2.map(r => ({
              id: r.id, char_a_id: r.char_a_id, char_b_id: r.char_b_id,
              relation_type: r.relation_type, trust: r.trust, favor: r.favor,
              info_known_a_about_b: r.info_known_a_about_b || [],
              info_known_b_about_a: r.info_known_b_about_a || [],
              info_asymmetry: r.info_asymmetry || {},
              is_hidden: r.is_hidden || false,
              arc_direction: r.arc_direction || 'stable',
              trigger_condition: r.trigger_condition || null,
              arc_milestones: r.arc_milestones || [],
            })))
          } catch { /* skip relation generation */ }

          for (const c of created) {
            eventBus.emit(DataEvents.CHARACTER_UPDATED, { id: c.id, name: c.name })
          }
          notification.success({
            message: `成功创建 ${created.length} 个角色及关系网络`,
            description: `AI深度分析了「${currentProject.name}」的剧本内容后，一次性生成完整角色阵容与复杂关系网络`,
            placement: 'topRight',
          })
        }
      } else {
        notification.warning({ message: 'AI未能生成角色', description: '请确认AI服务可用或重试', placement: 'topRight' })
      }
    } catch (e: any) {
      notification.error({ message: 'AI生成失败', description: e?.detail || e?.message || '请检查AI服务', placement: 'topRight' })
    }
    updateAgent('创作Agent', { status: 'idle', currentTask: undefined })
    setAiGenerating(false)
  }

  const saveRelation = async () => {
    if (!relEditor || !currentProject?.id) return
    try {
      await relationsApi.update(currentProject.id, relEditor.relId, {
        trust: relEditor.trust, favor: relEditor.favor, relation_type: relEditor.type,
      })
      setRelations(prev => prev.map(r =>
        r.id === relEditor.relId ? { ...r, trust: relEditor.trust, favor: relEditor.favor, relation_type: relEditor.type } : r
      ))
      setRelEditor(null)
      setArcDrawerOpen(false)
      notification.success({ message: '关系已更新', placement: 'topRight' })
    } catch (e: any) { notification.error({ message: '保存关系失败', description: e?.detail || e?.message, placement: 'topRight' }) }
  }

  const hasRelations = useMemo(() => relations.length > 0, [relations])
  const activeChars = useMemo(() => characters.filter(c => c.status === 'active'), [characters])

  const networkStats = useMemo(() => {
    const n = activeChars.length
    const maxRels = n > 1 ? n * (n - 1) / 2 : 0
    const density = maxRels > 0 ? Math.round((relations.length / maxRels) * 100) : 0
    const charsWithRels = new Set(relations.flatMap(r => [r.char_a_id, r.char_b_id]))
    const isolatedCount = activeChars.filter(c => !charsWithRels.has(c.id)).length
    const hiddenCount = relations.filter(r => r.is_hidden).length
    return { density, isolatedCount, hiddenCount, maxRels }
  }, [activeChars, relations])

  // ======== D3 Force Graph ========
  useEffect(() => {
    if (!svgRef.current || loading || activeChars.length === 0) return
    const svg = d3.select(svgRef.current)
    svg.selectAll('*').remove()
    const width = svgRef.current.clientWidth || 800
    const height = svgRef.current.clientHeight || 500
    svg.attr('viewBox', `0 0 ${width} ${height}`).style('background', 'transparent')

    const g = svg.append('g')
    const zoom = d3.zoom<SVGSVGElement, unknown>()
      .scaleExtent([0.2, 4])
      .on('zoom', (event) => { g.attr('transform', event.transform); setGraphScaling(event.transform) })
    svg.call(zoom)

    const defs = svg.append('defs')
    const arrowColors: { name: string; color: string }[] = [
      { name: 'green', color: '#22c55e' },
      { name: 'blue', color: '#3b82f6' },
      { name: 'amber', color: '#f59e0b' },
      { name: 'red', color: '#ef4444' },
      { name: 'purple', color: '#a855f7' },
      { name: 'gray', color: '#9ca3af' },
    ]
    arrowColors.forEach(({ name, color }) => {
      defs.append('marker')
        .attr('id', `arrow-${name}`)
        .attr('viewBox', '0 -5 10 10')
        .attr('refX', 10)
        .attr('refY', 0)
        .attr('markerWidth', 8)
        .attr('markerHeight', 8)
        .attr('orient', 'auto')
        .append('path')
        .attr('d', 'M0,-4L8,0L0,4')
        .attr('fill', color)
    })

    const charMap = new Map(characters.map(c => [c.id, c]))

    const nodes = activeChars.map(c => ({
      id: c.id, name: c.name, role: c.role_type || 'supporting',
      goal: c.core_goal, fear: c.core_fear,
      radius: c.role_type === 'protagonist' ? 28 : c.role_type === 'antagonist' ? 24 : c.role_type === 'love_interest' ? 22 : 18,
    }))

    const nodeRadiusMap = new Map(nodes.map(n => [n.id, n.radius]))

    const getLinkColor = (d: any) => {
      if (d.isHidden) return '#a855f7'
      if (d.favor >= 70) return '#22c55e'
      if (d.favor >= 40) return '#3b82f6'
      if (d.favor >= 20) return '#f59e0b'
      return '#ef4444'
    }

    const getArrowMarker = (d: any) => {
      const colorName = d.isHidden ? 'purple' : d.favor >= 70 ? 'green' : d.favor >= 40 ? 'blue' : d.favor >= 20 ? 'amber' : 'red'
      return `url(#arrow-${colorName})`
    }

    const ARC_DIR_LABELS: Record<string, { symbol: string; color: string }> = {
      improving: { symbol: '↑', color: '#22c55e' },
      deteriorating: { symbol: '↓', color: '#ef4444' },
      stable: { symbol: '→', color: '#9ca3af' },
    }

    const links = relations.filter(r => charMap.has(r.char_a_id) && charMap.has(r.char_b_id))
      .map(r => ({
        source: r.char_a_id, target: r.char_b_id,
        trust: r.trust, favor: r.favor,
        relation_type: r.relation_type, id: r.id,
        isHidden: r.is_hidden,
        arcDirection: r.arc_direction,
        triggerCondition: r.trigger_condition,
        arcMilestones: r.arc_milestones,
        infoAsymmetry: r.info_asymmetry,
        infoKnownAAboutB: r.info_known_a_about_b,
        infoKnownBAboutA: r.info_known_b_about_a,
      }))

    const sim = d3.forceSimulation(nodes as any)
      .force('link', d3.forceLink(links).id((d: any) => d.id).distance(180))
      .force('charge', d3.forceManyBody().strength(-700))
      .force('center', d3.forceCenter(width / 2, height / 2))
      .force('collision', d3.forceCollide().radius(60))

    const linkG = g.append('g').selectAll('line').data(links).join('line')
      .attr('stroke', getLinkColor)
      .attr('stroke-width', d => Math.max(0.5, Math.min(5, (d.trust + d.favor) / 40)))
      .attr('stroke-opacity', d => d.isHidden ? 0.4 : 0.7)
      .attr('stroke-dasharray', d => {
        if (d.isHidden) return '6,3'
        if (d.favor <= 20) return '4,4'
        return 'none'
      })
      .attr('marker-end', getArrowMarker)
      .style('cursor', 'pointer')
      .on('click', (_e: any, d: any) => {
        _e.stopPropagation()
        const a = characters.find(c => c.id === (d.source as any)?.id || c.id === d.source)
        const b = characters.find(c => c.id === (d.target as any)?.id || c.id === d.target)
        if (a && b) {
          setRelEditor({
            relId: d.id, a: a.name, b: b.name,
            type: d.relation_type || 'friend', trust: d.trust, favor: d.favor,
            arcDirection: d.arcDirection || 'stable',
            triggerCondition: d.triggerCondition || null,
            arcMilestones: d.arcMilestones || [],
            infoAsymmetry: d.infoAsymmetry || {},
            infoKnownAAboutB: d.infoKnownAAboutB || [],
            infoKnownBAboutA: d.infoKnownBAboutA || [],
            isHidden: d.isHidden || false,
          })
          setArcDrawerOpen(true)
        }
      })

    const linkLabelG = g.append('g').selectAll('g').data(links).join('g')
      .style('pointer-events', 'none')
      .style('user-select', 'none')

    linkLabelG.append('text')
      .attr('text-anchor', 'middle')
      .attr('fill', d => d.isHidden ? '#a855f7' : '#9ca3af')
      .attr('font-size', '8px')
      .attr('dy', -10)
      .text(d => REL_TYPE_LABELS[d.relation_type as string] || d.relation_type || '')

    linkLabelG.append('text')
      .attr('text-anchor', 'middle')
      .attr('font-size', '11px')
      .attr('font-weight', 'bold')
      .attr('dy', 2)
      .attr('fill', d => {
        const dir = ARC_DIR_LABELS[d.arcDirection]
        return dir ? dir.color : '#9ca3af'
      })
      .text(d => {
        const dir = ARC_DIR_LABELS[d.arcDirection]
        return dir ? dir.symbol : '→'
      })

    const triggerLabelG = g.append('g').selectAll('g').data(links.filter(l => l.triggerCondition)).join('g')
      .style('pointer-events', 'all')
      .style('cursor', 'pointer')

    triggerLabelG.append('text')
      .attr('text-anchor', 'middle')
      .attr('font-size', '12px')
      .attr('dy', 14)
      .text('💥')

    triggerLabelG.append('title')
      .text((d: any) => `引爆点: ${d.triggerCondition}`)

    const hiddenLabelG = g.append('g').selectAll('text').data(links.filter(l => l.isHidden)).join('text')
      .attr('text-anchor', 'middle')
      .attr('font-size', '10px')
      .attr('dy', -20)
      .style('pointer-events', 'none')
      .style('user-select', 'none')
      .text('🔒')

    const nodeG = g.append('g').selectAll('g').data(nodes).join('g')
      .call(d3.drag<SVGGElement, any, any>()
        .on('start', (e: any, d: any) => {
          if (!e.active) sim.alphaTarget(0.3).restart()
          d.fx = d.x; d.fy = d.y
        })
        .on('drag', (e: any, d: any) => { d.fx = e.x; d.fy = e.y })
        .on('end', (e: any, d: any) => {
          if (!e.active) sim.alphaTarget(0)
          d.fx = null; d.fy = null
        }) as any
      )
      .on('click', (_e: any, d: any) => {
        const char = characters.find(c => c.id === d.id)
        if (char) openDrawer(char)
      })
      .style('cursor', 'pointer')

    nodeG.append('circle')
      .attr('r', d => d.radius)
      .attr('fill', d => ROLE_COLORS[d.role] || '#6b7280')
      .attr('stroke', '#fff')
      .attr('stroke-width', d => d.role === 'protagonist' || d.role === 'antagonist' ? 3 : 2)
      .attr('filter', d => d.role === 'protagonist' || d.role === 'antagonist' ? 'drop-shadow(0 0 4px rgba(0,0,0,0.3))' : '')

    nodeG.append('text')
      .text(d => d.name.length > 5 ? d.name.slice(0, 4) + '...' : d.name)
      .attr('text-anchor', 'middle')
      .attr('dy', d => d.radius + 12)
      .attr('fill', '#4b5563')
      .style('font-size', '10px')
      .style('pointer-events', 'none')
      .style('font-weight', '500')

    nodeG.append('title').text(d => `${d.name}\n${ROLE_LABELS[d.role] || d.role}`)

    sim.on('tick', () => {
      linkG
        .attr('x1', (d: any) => {
          const dx = d.target.x - d.source.x
          const dy = d.target.y - d.source.y
          const dist = Math.sqrt(dx * dx + dy * dy) || 1
          const r = nodeRadiusMap.get(d.source.id) || 18
          return d.source.x + (dx / dist) * r
        })
        .attr('y1', (d: any) => {
          const dx = d.target.x - d.source.x
          const dy = d.target.y - d.source.y
          const dist = Math.sqrt(dx * dx + dy * dy) || 1
          const r = nodeRadiusMap.get(d.source.id) || 18
          return d.source.y + (dy / dist) * r
        })
        .attr('x2', (d: any) => {
          const dx = d.target.x - d.source.x
          const dy = d.target.y - d.source.y
          const dist = Math.sqrt(dx * dx + dy * dy) || 1
          const r = (nodeRadiusMap.get(d.target.id) || 18) + 10
          return d.target.x - (dx / dist) * r
        })
        .attr('y2', (d: any) => {
          const dx = d.target.x - d.source.x
          const dy = d.target.y - d.source.y
          const dist = Math.sqrt(dx * dx + dy * dy) || 1
          const r = (nodeRadiusMap.get(d.target.id) || 18) + 10
          return d.target.y - (dy / dist) * r
        })

      linkLabelG.attr('transform', (d: any) =>
        `translate(${(d.source.x + d.target.x) / 2},${(d.source.y + d.target.y) / 2})`
      )
      triggerLabelG.attr('transform', (d: any) =>
        `translate(${(d.source.x + d.target.x) / 2},${(d.source.y + d.target.y) / 2})`
      )
      hiddenLabelG.attr('transform', (d: any) =>
        `translate(${(d.source.x + d.target.x) / 2},${(d.source.y + d.target.y) / 2})`
      )
      nodeG.attr('transform', (d: any) => `translate(${d.x},${d.y})`)
    })

    return () => { sim.stop() }
  }, [characters, relations, loading])

  if (!currentProject) {
    return (
      <div>
        <h1 className="text-2xl font-bold mb-6">角色管理</h1>
        <Card className="text-center py-12">
          <Empty description={<span className="text-gray-400">请先创建或选择一个项目</span>} />
        </Card>
      </div>
    )
  }

  if (loading && characters.length === 0) {
    return (
      <div className="h-full flex items-center justify-center">
        <Spin tip="加载角色数据..."><div className="py-20" /></Spin>
      </div>
    )
  }

  return (
    <div className="h-full flex flex-col overflow-auto">
      <div className="flex items-center justify-between mb-4 flex-wrap gap-2 flex-shrink-0">
        <div>
          <h1 className="text-2xl font-bold m-0">角色管理</h1>
          <p className="text-xs text-gray-400 mt-1">
            {activeChars.length} 个角色 · {relations.length} 条关系
            {currentProject.config?.genre && <Tag className="ml-1">{currentProject.config.genre}</Tag>}
          </p>
        </div>
        <Space wrap>
          <Tooltip title="AI将分析当前剧本内容，生成贴合故事的角色">
            <Button icon={<RobotOutlined />} onClick={handleAIGenerate} loading={aiGenerating}>
              {aiGenerating ? 'AI分析中...' : 'AI 生成角色'}
            </Button>
          </Tooltip>
          <Button icon={<PlusOutlined />} type="primary" onClick={async () => {
            if (!currentProject?.id) return
            try {
              const n = await charactersApi.create(currentProject.id, {
                name: '', char_code: `CHAR-${String(characters.length + 1).padStart(3, '0')}`,
                role_type: 'supporting', status: 'active',
                behavior_inevitable: [], behavior_never: [], behavior_conditional: [],
              })
              const cd = apiCharToCharData(n)
              setCharacters(prev => [...prev, cd])
              openDrawer(cd)
              startEdit()
            } catch (e: any) {
              notification.error({ message: '新建角色失败', description: e?.detail || e?.message || '请检查后端服务', placement: 'topRight' })
            }
          }}>新建角色</Button>
        </Space>
      </div>

      {characters.length === 0 ? (
        <Card className="text-center py-16 mb-4">
          <TeamOutlined className="text-5xl text-gray-200 mb-4 block" />
          <Empty description={
            <span className="text-gray-400">
              项目「{currentProject.name}」暂无角色<br />
              <span className="text-xs">点击「AI 生成角色」让AI根据剧本内容分析生成</span>
            </span>
          } />
        </Card>
      ) : (
        <Row gutter={[12, 12]} className="mb-4">
          {activeChars.map(char => {
            const relCount = relations.filter(r => r.char_a_id === char.id || r.char_b_id === char.id).length
            return (
              <Col xs={24} sm={12} lg={8} xl={6} key={char.id}>
                <Card
                  hoverable
                  className="h-full transition-all border border-gray-200 dark:border-slate-700 hover:shadow-lg hover:border-primary-300 dark:hover:border-primary-600 bg-white dark:bg-slate-800"
                  onClick={() => openDrawer(char)}
                  size="small"
                >
                  <div className="flex items-start gap-3">
                    <div
                      className="w-12 h-12 rounded-xl flex items-center justify-center text-white text-lg font-bold shadow-sm shrink-0"
                      style={{ background: ROLE_COLORS[char.role_type || 'supporting'] }}
                    >
                      {char.name?.[0] || '?'}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-1.5 mb-0.5">
                        <span className="font-bold text-gray-800 dark:text-gray-200 truncate">{char.name || <span className="italic text-gray-400">未命名</span>}</span>
                      </div>
                      <div className="flex items-center gap-1.5 mb-1 flex-wrap">
                        <Tag color={ROLE_COLORS[char.role_type || 'supporting']} className="!text-[10px] !leading-4 !px-1.5">
                          {ROLE_LABELS[char.role_type || 'supporting'] || char.role_type}
                        </Tag>
                        <span className="text-[10px] text-gray-400 font-mono">{char.char_code}</span>
                      </div>
                      <p className="text-xs text-gray-500 dark:text-gray-400 line-clamp-2 mb-2 leading-relaxed">
                        {char.core_goal || char.arc_description || '暂未设定目标与弧线'}
                      </p>
                      <div className="flex items-center gap-2 text-[10px] text-gray-400 dark:text-gray-500">
                        <Tooltip title={`${relCount} 条关系`}><span>🔗 {relCount}</span></Tooltip>
                        <span>|</span>
                        <Tooltip title={char.arc_description || '角色弧未设定'}><span>{char.arc_description ? '📈 有弧线' : '⚪ 未设定弧'}</span></Tooltip>
                        {char.dark_secret && <><span>|</span><Tooltip title={char.dark_secret}><span>🤐 有秘密</span></Tooltip></>}
                      </div>
                    </div>
                  </div>
                </Card>
              </Col>
            )
          })}
        </Row>
      )}

      {/* ======== 关系图谱 ======== */}
      <Card
        className="mb-4 shadow-sm border-gray-200 dark:border-slate-700 bg-white dark:bg-slate-800"
        size="small"
        title={
          <div className="flex items-center gap-2">
            <NodeIndexOutlined className="text-primary-500" />
            <span className="text-sm font-bold">角色关系网络</span>
            <span className="text-[10px] text-gray-400 ml-2">({activeChars.length}节点 · {relations.length}条边)</span>
            <div className="flex items-center gap-3 ml-auto text-[10px] text-gray-400">
              <span className="flex items-center gap-1"><span className="w-2.5 h-2.5 rounded-full bg-green-500" />亲密</span>
              <span className="flex items-center gap-1"><span className="w-2.5 h-2.5 rounded-full bg-blue-500" />友好</span>
              <span className="flex items-center gap-1"><span className="w-2.5 h-2.5 rounded-full bg-amber-400" />一般</span>
              <span className="flex items-center gap-1"><span className="w-2.5 h-2.5 rounded-full bg-red-500" />恶劣</span>
              <span className="flex items-center gap-1"><span className="w-2.5 h-2.5 rounded-full bg-purple-500" />暗线</span>
              <span className="ml-1">|</span>
              <span className="text-green-500 font-bold">↑改善</span>
              <span className="text-red-500 font-bold">↓恶化</span>
              <span className="text-gray-400 font-bold">→稳定</span>
              <span className="ml-1">|</span>
              <span>💥引爆点</span>
              <span>🔒暗线</span>
            </div>
          </div>
        }
      >
        <div className="flex items-center gap-4 mb-2 px-1 text-[11px]">
          <div className="flex items-center gap-1">
            <DashboardOutlined className="text-blue-400" />
            <span className="text-gray-400">当前密度</span>
            <span className={`font-bold ${networkStats.density >= 60 ? 'text-green-500' : networkStats.density >= 30 ? 'text-amber-500' : 'text-red-500'}`}>
              {networkStats.density}%
            </span>
          </div>
          <div className="flex items-center gap-1">
            <AimOutlined className="text-gray-400" />
            <span className="text-gray-400">目标密度</span>
            <span className="font-bold text-gray-500">60%</span>
          </div>
          <div className="flex items-center gap-1">
            <UserOutlined className="text-orange-400" />
            <span className="text-gray-400">孤立角色</span>
            <span className={`font-bold ${networkStats.isolatedCount > 0 ? 'text-orange-500' : 'text-green-500'}`}>
              {networkStats.isolatedCount}
            </span>
          </div>
          <div className="flex items-center gap-1">
            <EyeInvisibleOutlined className="text-purple-400" />
            <span className="text-gray-400">暗线关系</span>
            <span className={`font-bold ${networkStats.hiddenCount > 0 ? 'text-purple-500' : 'text-gray-400'}`}>
              {networkStats.hiddenCount}
            </span>
          </div>
        </div>

        <div className="bg-gray-50 dark:bg-slate-900 rounded-xl overflow-hidden relative" style={{ height: 500 }}>
          {activeChars.length === 0 ? (
            <div className="h-full flex items-center justify-center">
              <Empty description="暂无活跃角色" />
            </div>
          ) : (
            <svg ref={svgRef} className="w-full h-full" />
          )}
        </div>
        <p className="text-[10px] text-gray-400 mt-2">
          🖱 滚轮缩放 · 拖拽节点 · 点击节点查看详情 · 点击连线查看关系弧线时间轴 · 箭头=关系方向 · ↑↓→=弧线趋势 · 💥=引爆点 · 🔒紫色虚线=暗线关系
        </p>
      </Card>

      {/* ======== 抽屉 ======== */}
      <Drawer
        open={drawerOpen}
        onClose={() => { setDrawerOpen(false); setEditing(false); setEditData(null) }}
        width={500}
        closable={false}
        styles={{ body: { padding: 0 } }}
      >
        {selectedChar && (
          <div className="p-6">
            <div className="flex items-center justify-between mb-5">
              <div className="flex items-center gap-3">
                <div
                  className="w-10 h-10 rounded-xl flex items-center justify-center text-white text-lg font-bold shadow"
                  style={{ background: ROLE_COLORS[selectedChar.role_type || 'supporting'] }}
                >
                  {selectedChar.name?.[0] || '?'}
                </div>
                <div>
                  <h2 className="text-xl font-bold m-0 text-gray-800 dark:text-gray-100">
                    {editing ? '编辑角色' : selectedChar.name || '未命名'}
                  </h2>
                  <span className="text-xs text-gray-400 font-mono">{selectedChar.char_code}</span>
                </div>
              </div>
              <Space size={4}>
                {editing ? (
                  <>
                    <Button size="small" onClick={() => { setEditing(false); setEditData(null) }}>取消</Button>
                    <Button size="small" type="primary" icon={<SaveOutlined />} loading={saving} onClick={saveEdit}>保存</Button>
                  </>
                ) : (
                  <>
                    <Button size="small" icon={<EditOutlined />} onClick={startEdit}>编辑</Button>
                    <Popconfirm
                      title="确定删除该角色？"
                      description="相关场景引用将一同清理"
                      onConfirm={() => setDeleteConfirm(selectedChar.id)}
                      okText="删除" cancelText="取消"
                      okButtonProps={{ danger: true }}
                    >
                      <Button size="small" danger icon={<DeleteOutlined />} />
                    </Popconfirm>
                  </>
                )}
              </Space>
            </div>

            {editing && editData ? (
              <div className="space-y-3">
                <div>
                  <label className="text-xs text-gray-400 block mb-1">代号 *</label>
                  <Input size="small" value={editData.char_code} onChange={e => setEditData({ ...editData, char_code: e.target.value })} />
                </div>
                <div>
                  <label className="text-xs text-gray-400 block mb-1">名称 *</label>
                  <Input size="small" value={editData.name} onChange={e => setEditData({ ...editData, name: e.target.value })} />
                </div>
                <div>
                  <label className="text-xs text-gray-400 block mb-1">角色类型</label>
                  <Select size="small" className="w-full" value={editData.role_type} onChange={v => setEditData({ ...editData, role_type: v })}
                    options={Object.entries(ROLE_LABELS).map(([k, v]) => ({ value: k, label: v }))} />
                </div>
                <div><label className="text-xs text-gray-400 block mb-1">背景故事</label><TextArea size="small" rows={3} value={editData.background || ''} onChange={e => setEditData({ ...editData, background: e.target.value })} /></div>
                <div><label className="text-xs text-gray-400 block mb-1">核心动机</label><TextArea size="small" rows={2} value={editData.core_goal || ''} onChange={e => setEditData({ ...editData, core_goal: e.target.value })} /></div>
                <div><label className="text-xs text-gray-400 block mb-1">深层恐惧</label><TextArea size="small" rows={2} value={editData.core_fear || ''} onChange={e => setEditData({ ...editData, core_fear: e.target.value })} /></div>
                <div><label className="text-xs text-gray-400 block mb-1">不为人知的秘密</label><TextArea size="small" rows={2} value={editData.dark_secret || ''} onChange={e => setEditData({ ...editData, dark_secret: e.target.value })} /></div>
                <div><label className="text-xs text-gray-400 block mb-1">表面形象</label><TextArea size="small" rows={2} value={editData.surface_image || ''} onChange={e => setEditData({ ...editData, surface_image: e.target.value })} /></div>
                <div><label className="text-xs text-gray-400 block mb-1">真实面目</label><TextArea size="small" rows={2} value={editData.true_self || ''} onChange={e => setEditData({ ...editData, true_self: e.target.value })} /></div>
                <div><label className="text-xs text-gray-400 block mb-1">口头禅</label><Input size="small" value={editData.catchphrase || ''} onChange={e => setEditData({ ...editData, catchphrase: e.target.value })} /></div>
                <div><label className="text-xs text-gray-400 block mb-1">语言风格</label><TextArea size="small" rows={2} value={editData.language_style || ''} onChange={e => setEditData({ ...editData, language_style: e.target.value })} /></div>
                <div><label className="text-xs text-gray-400 block mb-1">角色弧</label><TextArea size="small" rows={3} value={editData.arc_description || ''} onChange={e => setEditData({ ...editData, arc_description: e.target.value })} /></div>
                {(['behavior_inevitable', 'behavior_never', 'behavior_conditional'] as const).map(field => (
                  <div key={field}>
                    <div className="flex items-center justify-between mb-1">
                      <label className="text-xs text-gray-400">
                        {field === 'behavior_inevitable' ? '必然行为' : field === 'behavior_never' ? '绝对不会' : '有条件行为'}
                      </label>
                      <Button size="small" type="dashed" icon={<PlusCircleOutlined />} onClick={() => setEditData({ ...editData, [field]: [...editData[field], ''] })}>添加</Button>
                    </div>
                    {editData[field].map((b, i) => (
                      <div key={i} className="flex items-center gap-1 mb-1">
                        <Input size="small" value={b} onChange={e => {
                          const arr = [...editData[field]]; arr[i] = e.target.value; setEditData({ ...editData, [field]: arr })
                        }} />
                        <Button size="small" type="text" danger icon={<MinusCircleOutlined />} onClick={() => setEditData({ ...editData, [field]: editData[field].filter((_, j) => j !== i) })} />
                      </div>
                    ))}
                  </div>
                ))}
              </div>
            ) : (
              <div className="space-y-4">
                <Tag color={ROLE_COLORS[selectedChar.role_type || 'supporting']}>
                  {ROLE_LABELS[selectedChar.role_type || 'supporting'] || selectedChar.role_type}
                </Tag>

                {(selectedChar.background || selectedChar.core_goal || selectedChar.core_fear) && (
                  <Card size="small" className="border-0 bg-gray-50 dark:bg-slate-800" title={<span className="text-xs font-semibold">📋 角色深描</span>}>
                    <div className="space-y-3 text-sm">
                      {selectedChar.background && (
                        <div>
                          <div className="text-xs text-gray-400 mb-1 font-semibold">背景</div>
                          <p className="text-gray-700 dark:text-gray-300 m-0 leading-relaxed">{selectedChar.background}</p>
                        </div>
                      )}
                      {selectedChar.core_goal && (
                        <div>
                          <div className="text-xs text-gray-400 mb-1 font-semibold">🎯 核心动机</div>
                          <p className="text-blue-700 dark:text-blue-300 m-0">{selectedChar.core_goal}</p>
                        </div>
                      )}
                      {selectedChar.core_fear && (
                        <div>
                          <div className="text-xs text-gray-400 mb-1 font-semibold">😨 深层恐惧</div>
                          <p className="text-red-600 dark:text-red-300 m-0">{selectedChar.core_fear}</p>
                        </div>
                      )}
                      {selectedChar.dark_secret && (
                        <div>
                          <div className="text-xs text-gray-400 mb-1 font-semibold">🤐 不为人知的秘密</div>
                          <p className="text-purple-700 dark:text-purple-300 m-0 italic">{selectedChar.dark_secret}</p>
                        </div>
                      )}
                    </div>
                  </Card>
                )}

                {(selectedChar.surface_image || selectedChar.true_self) && (
                  <Card size="small" className="border-0 bg-gray-50 dark:bg-slate-800" title={<span className="text-xs font-semibold">🎭 双面镜</span>}>
                    <div className="grid grid-cols-2 gap-3 text-sm">
                      {selectedChar.surface_image && (
                        <div className="bg-white dark:bg-slate-700 p-3 rounded-lg">
                          <div className="text-[10px] text-gray-400 mb-1">表面形象</div>
                          <p className="text-gray-700 dark:text-gray-300 m-0">{selectedChar.surface_image}</p>
                        </div>
                      )}
                      {selectedChar.true_self && (
                        <div className="bg-white dark:bg-slate-700 p-3 rounded-lg">
                          <div className="text-[10px] text-gray-400 mb-1">真实面目</div>
                          <p className="text-purple-700 dark:text-purple-300 m-0">{selectedChar.true_self}</p>
                        </div>
                      )}
                    </div>
                  </Card>
                )}

                {selectedChar.arc_description && (
                  <Card size="small" className="border-0 bg-gradient-to-r from-purple-50 to-pink-50 dark:from-purple-900/10 dark:to-pink-900/10"
                    title={<span className="text-xs font-semibold">📈 角色弧</span>}>
                    <p className="text-sm text-gray-600 dark:text-gray-400 m-0 leading-relaxed">{selectedChar.arc_description}</p>
                  </Card>
                )}

                {(selectedChar.language_style || selectedChar.catchphrase) && (
                  <Card size="small" className="border-0 bg-gray-50 dark:bg-slate-800" title={<span className="text-xs font-semibold">💬 语言特征</span>}>
                    <div className="space-y-2">
                      {selectedChar.language_style && <p className="text-sm text-gray-600 dark:text-gray-400 m-0">风格: {selectedChar.language_style}</p>}
                      {selectedChar.catchphrase && <Tag color="blue" className="text-sm">「{selectedChar.catchphrase}」</Tag>}
                    </div>
                  </Card>
                )}

                {(['behavior_inevitable', 'behavior_never', 'behavior_conditional'] as const).map(field => {
                  if (!selectedChar[field].length) return null
                  const labels = { behavior_inevitable: '✓ 必然行为', behavior_never: '✗ 绝对不会', behavior_conditional: '◉ 有条件行为' }
                  const colors = { behavior_inevitable: 'green', behavior_never: 'red', behavior_conditional: 'orange' }
                  return (
                    <div key={field}>
                      <Tag color={colors[field]} className="mb-1 text-xs">{labels[field]}</Tag>
                      {selectedChar[field].map((b, i) => (
                        <div key={i} className={`text-sm pl-2 border-l-2 border-${colors[field]}-400 mb-1 text-gray-600 dark:text-gray-400`}>
                          {b}
                        </div>
                      ))}
                    </div>
                  )
                })}

                {charRelations.length > 0 && (
                  <Card size="small" className="border-0 bg-gray-50 dark:bg-slate-800" title={<span className="text-xs font-semibold">🔗 关系网络 ({charRelations.length})</span>}>
                    <div className="space-y-2">
                      {charRelations.map((rel, i) => (
                        <div key={i} className="flex items-center gap-2 p-2 bg-white dark:bg-slate-700 rounded-lg cursor-pointer"
                          onClick={() => {
                            const fullRel = relations.find(fr => fr.id === rel.id)
                            setRelEditor({
                              relId: rel.id, a: selectedChar.name, b: rel.otherName,
                              type: rel.relation_type || 'friend', trust: rel.trust, favor: rel.favor,
                              arcDirection: fullRel?.arc_direction || 'stable',
                              triggerCondition: fullRel?.trigger_condition || null,
                              arcMilestones: fullRel?.arc_milestones || [],
                              infoAsymmetry: (fullRel?.info_asymmetry as Record<string, unknown>) || {},
                              infoKnownAAboutB: fullRel?.info_known_a_about_b || [],
                              infoKnownBAboutA: fullRel?.info_known_b_about_a || [],
                              isHidden: fullRel?.is_hidden || false,
                            })
                            setArcDrawerOpen(true)
                          }}>
                          <span className="text-xs font-medium text-gray-700 dark:text-gray-300 truncate flex-1">{rel.otherName}</span>
                          <Tag color={REL_TYPE_COLORS[rel.relation_type || 'friend']} className="text-[10px]">
                            {REL_TYPE_LABELS[rel.relation_type || 'friend'] || rel.relation_type}
                          </Tag>
                          <Progress percent={rel.trust} size="small" style={{ width: 60 }} strokeColor="#3b82f6" showInfo={false} />
                        </div>
                      ))}
                    </div>
                  </Card>
                )}
              </div>
            )}
          </div>
        )}
      </Drawer>

      <ConfirmDialog
        open={deleteConfirm !== null}
        title="删除角色" content="确认删除该角色？将移除所有关联关系。"
        danger okText="确认删除" onOk={handleDelete} onCancel={() => setDeleteConfirm(null)}
      />

      <Drawer
        open={arcDrawerOpen && relEditor !== null}
        onClose={() => { setArcDrawerOpen(false); setRelEditor(null) }}
        width={520}
        closable={false}
        styles={{ body: { padding: 0 } }}
      >
        {relEditor && (() => {
          const ARC_DIR_MAP: Record<string, { label: string; color: string; icon: React.ReactNode }> = {
            improving: { label: '改善中', color: '#22c55e', icon: <span style={{ color: '#22c55e', fontWeight: 'bold' }}>↑</span> },
            deteriorating: { label: '恶化中', color: '#ef4444', icon: <span style={{ color: '#ef4444', fontWeight: 'bold' }}>↓</span> },
            stable: { label: '稳定', color: '#9ca3af', icon: <span style={{ color: '#9ca3af', fontWeight: 'bold' }}>→</span> },
          }
          const dirInfo = ARC_DIR_MAP[relEditor.arcDirection] || ARC_DIR_MAP.stable
          const milestones = (Array.isArray(relEditor.arcMilestones) ? relEditor.arcMilestones : []) as any[]
          const infoAsym = (relEditor.infoAsymmetry || {}) as Record<string, any>
          const aKnows = (Array.isArray(relEditor.infoKnownAAboutB) ? relEditor.infoKnownAAboutB : []) as string[]
          const bKnows = (Array.isArray(relEditor.infoKnownBAboutA) ? relEditor.infoKnownBAboutA : []) as string[]
          const asymA = Array.isArray(infoAsym.a_knows_about_b) ? infoAsym.a_knows_about_b as string[] : aKnows
          const asymB = Array.isArray(infoAsym.b_knows_about_a) ? infoAsym.b_knows_about_a as string[] : bKnows

          return (
            <div className="p-6">
              <div className="flex items-center justify-between mb-5">
                <div className="flex items-center gap-3">
                  <div className="w-9 h-9 rounded-lg flex items-center justify-center text-white text-sm font-bold shadow"
                    style={{ background: REL_TYPE_COLORS[relEditor.type] || '#6b7280' }}>
                    <BranchesOutlined />
                  </div>
                  <div>
                    <h2 className="text-lg font-bold m-0 text-gray-800 dark:text-gray-100">
                      {relEditor.a} ↔ {relEditor.b}
                    </h2>
                    <div className="flex items-center gap-2 mt-0.5">
                      <Tag color={REL_TYPE_COLORS[relEditor.type] || 'default'} className="text-[10px]">
                        {REL_TYPE_LABELS[relEditor.type] || relEditor.type}
                      </Tag>
                      {dirInfo.icon}
                      <span className="text-[10px]" style={{ color: dirInfo.color }}>{dirInfo.label}</span>
                      {relEditor.isHidden && (
                        <Tag color="purple" className="text-[10px]">
                          <EyeInvisibleOutlined /> 暗线
                        </Tag>
                      )}
                    </div>
                  </div>
                </div>
                <Button type="text" size="small" icon={<CloseOutlined />}
                  onClick={() => { setArcDrawerOpen(false); setRelEditor(null) }} />
              </div>

              <Card size="small" className="border-0 bg-gray-50 dark:bg-slate-800 mb-4"
                title={<span className="text-xs font-semibold">📊 关系指标</span>}>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <div className="flex justify-between text-[10px] mb-1">
                      <span className="text-gray-400">信任度</span>
                      <span className="font-mono text-blue-500 font-bold">{relEditor.trust}</span>
                    </div>
                    <Progress percent={relEditor.trust} size="small" strokeColor="#3b82f6" />
                  </div>
                  <div>
                    <div className="flex justify-between text-[10px] mb-1">
                      <span className="text-gray-400">好感度</span>
                      <span className="font-mono text-pink-500 font-bold">{relEditor.favor}</span>
                    </div>
                    <Progress percent={relEditor.favor} size="small" strokeColor="#ec4899" />
                  </div>
                </div>
              </Card>

              {(asymA.length > 0 || asymB.length > 0) && (
                <Card size="small" className="border-0 bg-gray-50 dark:bg-slate-800 mb-4"
                  title={<span className="text-xs font-semibold">🔮 信息不对称</span>}>
                  <div className="grid grid-cols-2 gap-3">
                    <div className="bg-white dark:bg-slate-700 p-2.5 rounded-lg">
                      <div className="text-[10px] text-gray-400 mb-1.5 font-semibold">
                        {relEditor.a} 知道 {relEditor.b} 的
                      </div>
                      {asymA.length > 0 ? (
                        <div className="space-y-1">
                          {asymA.map((info: string, i: number) => (
                            <div key={i} className="text-xs text-blue-700 dark:text-blue-300 bg-blue-50 dark:bg-blue-900/20 px-2 py-0.5 rounded">
                              {info}
                            </div>
                          ))}
                        </div>
                      ) : (
                        <span className="text-[10px] text-gray-400">无已知信息</span>
                      )}
                    </div>
                    <div className="bg-white dark:bg-slate-700 p-2.5 rounded-lg">
                      <div className="text-[10px] text-gray-400 mb-1.5 font-semibold">
                        {relEditor.b} 知道 {relEditor.a} 的
                      </div>
                      {asymB.length > 0 ? (
                        <div className="space-y-1">
                          {asymB.map((info: string, i: number) => (
                            <div key={i} className="text-xs text-pink-700 dark:text-pink-300 bg-pink-50 dark:bg-pink-900/20 px-2 py-0.5 rounded">
                              {info}
                            </div>
                          ))}
                        </div>
                      ) : (
                        <span className="text-[10px] text-gray-400">无已知信息</span>
                      )}
                    </div>
                  </div>
                </Card>
              )}

              {milestones.length > 0 && (
                <Card size="small" className="border-0 bg-gradient-to-r from-purple-50 to-pink-50 dark:from-purple-900/10 dark:to-pink-900/10 mb-4"
                  title={<span className="text-xs font-semibold">📈 关系弧线时间轴</span>}>
                  <Timeline
                    items={milestones.map((m: any, i: number) => {
                      const trustChange = typeof m.trust_change === 'number' ? m.trust_change : 0
                      const favorChange = typeof m.favor_change === 'number' ? m.favor_change : 0
                      const netChange = trustChange + favorChange
                      return {
                        color: netChange > 0 ? 'green' : netChange < 0 ? 'red' : 'gray',
                        children: (
                          <div key={i}>
                            <div className="flex items-center gap-2 mb-0.5">
                              <Tag color="blue" className="text-[10px] !px-1.5 !py-0">
                                第{m.chapter || '?'}章
                              </Tag>
                              {netChange > 0 && <span className="text-[10px] text-green-500 font-bold">↑</span>}
                              {netChange < 0 && <span className="text-[10px] text-red-500 font-bold">↓</span>}
                            </div>
                            <p className="text-xs text-gray-700 dark:text-gray-300 m-0 mb-1 leading-relaxed">
                              {m.event || '未描述事件'}
                            </p>
                            <div className="flex items-center gap-3 text-[10px]">
                              <span className={trustChange > 0 ? 'text-green-500' : trustChange < 0 ? 'text-red-500' : 'text-gray-400'}>
                                信任{trustChange > 0 ? '+' : ''}{trustChange}
                              </span>
                              <span className={favorChange > 0 ? 'text-green-500' : favorChange < 0 ? 'text-red-500' : 'text-gray-400'}>
                                好感{favorChange > 0 ? '+' : ''}{favorChange}
                              </span>
                            </div>
                          </div>
                        ),
                      }
                    })}
                  />
                </Card>
              )}

              {relEditor.triggerCondition && (
                <Card size="small" className="border-0 bg-red-50 dark:bg-red-900/10 mb-4"
                  title={<span className="text-xs font-semibold">💥 引爆点</span>}>
                  <p className="text-xs text-red-700 dark:text-red-300 m-0 leading-relaxed">
                    {relEditor.triggerCondition}
                  </p>
                </Card>
              )}

              <Card size="small" className="border-0 bg-gray-50 dark:bg-slate-800"
                title={<span className="text-xs font-semibold">✏️ 编辑关系</span>}>
                <div className="space-y-3">
                  <div>
                    <label className="text-[10px] text-gray-400 mb-0.5 block">关系类型</label>
                    <Select
                      size="small" className="w-full"
                      value={relEditor.type}
                      onChange={v => setRelEditor({ ...relEditor, type: v })}
                      options={Object.entries(REL_TYPE_LABELS).map(([k, v]) => ({ value: k, label: v }))}
                    />
                  </div>
                  <div>
                    <div className="flex justify-between text-[10px] mb-0.5">
                      <span className="text-gray-400">信任度</span>
                      <span className="font-mono text-blue-500">{relEditor.trust}</span>
                    </div>
                    <Slider min={0} max={100} value={relEditor.trust}
                      onChange={v => setRelEditor({ ...relEditor, trust: v })} />
                  </div>
                  <div>
                    <div className="flex justify-between text-[10px] mb-0.5">
                      <span className="text-gray-400">好感度</span>
                      <span className="font-mono text-pink-500">{relEditor.favor}</span>
                    </div>
                    <Slider min={0} max={100} value={relEditor.favor}
                      onChange={v => setRelEditor({ ...relEditor, favor: v })} />
                  </div>
                  <Button type="primary" size="small" block onClick={saveRelation} icon={<SaveOutlined />}>
                    保存关系
                  </Button>
                </div>
              </Card>
            </div>
          )
        })()}
      </Drawer>
    </div>
  )
}
