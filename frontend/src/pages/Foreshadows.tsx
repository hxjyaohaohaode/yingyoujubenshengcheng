import { useState, useEffect, useRef, useMemo, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Card, Button, Tag, Table, App, Space, Progress,
  Empty, Modal, Input, Select, Badge, Spin,
} from 'antd'
const { Option } = Select
import {
  EyeOutlined, PlusOutlined, RobotOutlined, CheckCircleOutlined,
  ThunderboltOutlined, NodeIndexOutlined, BulbOutlined,
  EditOutlined, DeleteOutlined, WarningOutlined, ExperimentOutlined,
  FilterOutlined, TrophyOutlined,
  CloseOutlined, SearchOutlined, GlobalOutlined, UserOutlined,
  EnvironmentOutlined, ApartmentOutlined,
} from '@ant-design/icons'
import * as d3 from 'd3'
import { useProjectStore } from '../stores/projectStore'
import { api, foreshadowsApi } from '../api/client'
import { useTaskProgress } from '../hooks/useTaskProgress'
import { eventBus, DataEvents } from '../services/eventBus'

const { TextArea } = Input

interface WowPlan {
  id: string
  type: string
  summary: string
  score: number
}

interface WorldviewRef {
  config_key: string
  description: string
}

interface CharacterRef {
  character_name: string
  description: string
}

interface ForeshadowData {
  id: string
  project_id: string
  fs_code: string
  name: string
  fs_type: string
  surface_layer: string | null
  deep_layer: string | null
  truth_layer: string | null
  plant_scene_id: string | null
  reinforce_scenes: string[]
  reveal_scene_id: string | null
  wow_factor: string | null
  player_reaction: string | null
  depends_on: string[]
  enables: string[]
  current_status: string
  reinforce_count: number
  health: string
  wow_plans: WowPlan[]
  wow_selected: string | null
  worldview_refs: WorldviewRef[]
  character_refs: CharacterRef[]
  foreshadow_links: string[]
  plant_location: string | null
  reinforce_locations: string[]
  reveal_location: string | null
  created_at?: string
}

interface FSRelation {
  id: string
  project_id?: string
  from_fs_id: string
  to_fs_id: string
  relation_type: string
}

const TYPE_LABELS: Record<string, string> = {
  global: '全剧级', chapter: '章节级', scene: '场景级', interactive: '互动型',
}
const TYPE_COLORS: Record<string, string> = {
  global: '#8b5cf6', chapter: '#3b82f6', scene: '#10b981', interactive: '#f59e0b',
}
const STATUS_LABELS: Record<string, string> = {
  design: '设计中', planted: '已埋设', reinforced: '已强化', revealed: '已回收',
}
const HEALTH_COLORS: Record<string, string> = {
  normal: '#52c41a', warning: '#faad14', danger: '#ff4d4f',
}
const NODE_RADIUS: Record<string, number> = {
  global: 22, chapter: 16, scene: 12, interactive: 14,
}

const EMPTY_FS_FORM: Partial<ForeshadowData> = {
  fs_code: '', name: '', fs_type: 'global',
  surface_layer: '', deep_layer: '', truth_layer: '',
  plant_scene_id: null, reinforce_scenes: [], reveal_scene_id: null,
  wow_factor: '', player_reaction: '',
  depends_on: [], enables: [], current_status: 'design',
  health: 'normal', wow_plans: [], wow_selected: null, reinforce_count: 0,
  worldview_refs: [], character_refs: [], foreshadow_links: [],
  plant_location: null, reinforce_locations: [], reveal_location: null,
}

export default function Foreshadows() {
  const { notification } = App.useApp()
  const { currentProject } = useProjectStore()
  const navigate = useNavigate()
  const projectId = currentProject?.id || null

  const [foreshadows, setForeshadows] = useState<ForeshadowData[]>([])
  const [relations, setRelations] = useState<FSRelation[]>([])
  const [typeFilter, setTypeFilter] = useState<string>('all')
  const [statusFilter, setStatusFilter] = useState<string>('all')
  const [selectedFS, setSelectedFS] = useState<ForeshadowData | null>(null)
  const [editFS, setEditFS] = useState<ForeshadowData | null>(null)
  const [editing, setEditing] = useState(false)
  const [confirmDelete, setConfirmDelete] = useState<string | null>(null)
  const [healthReport, setHealthReport] = useState<{ total: number; normal: number; warning: number; danger: number; suggestions: string[] } | null>(null)
  const [reactionReport, setReactionReport] = useState<string[] | null>(null)
  const [healthLoading, setHealthLoading] = useState(false)
  const [reactionLoading, setReactionLoading] = useState(false)
  const [wowGenerating, setWowGenerating] = useState(false)
  const [loading, setLoading] = useState(true)
  const [createModalOpen, setCreateModalOpen] = useState(false)
  const [createForm, setCreateForm] = useState<Partial<ForeshadowData>>({ ...EMPTY_FS_FORM })
  const [creating, setCreating] = useState(false)
  const [saving, setSaving] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const [graphSearch, setGraphSearch] = useState('')
  const [aiGenerating, setAiGenerating] = useState(false)
  const [aiGenerateTaskId, setAiGenerateTaskId] = useState<string | null>(null)
  const [arcMode, setArcMode] = useState(false)
  const [relCreateOpen, setRelCreateOpen] = useState(false)
  const [relCreateForm, setRelCreateForm] = useState<{ from_fs_id: string; to_fs_id: string; relation_type: string }>({ from_fs_id: '', to_fs_id: '', relation_type: 'enables' })
  const [relEditOpen, setRelEditOpen] = useState(false)
  const [relEditTarget, setRelEditTarget] = useState<FSRelation | null>(null)
  const [relEditType, setRelEditType] = useState('enables')

  const svgRef = useRef<SVGSVGElement>(null)
  const hasAutoZoomed = useRef(false)
  const tooltipRef = useRef<d3.Selection<HTMLDivElement, unknown, HTMLElement, any> | null>(null)

  const { progress: aiProgress, status: aiStatus } = useTaskProgress(aiGenerateTaskId)

  const abortRef = useRef<AbortController | null>(null)

  const fetchData = async (signal?: AbortSignal) => {
    if (!projectId) {
      setForeshadows([])
      setRelations([])
      setLoading(false)
      return
    }
    setLoading(true)
    try {
      const [fsList, relList] = await Promise.all([
        foreshadowsApi.list(projectId, {
          ...(typeFilter !== 'all' ? { fs_type: typeFilter } : {}),
          ...(statusFilter !== 'all' ? { current_status: statusFilter } : {}),
        }, signal),
        foreshadowsApi.listRelations(projectId, signal),
      ])
      if (signal?.aborted) return
      setForeshadows(fsList.map(mapFS))
      setRelations(relList.map(mapRel))
    } catch (e: any) {
      if (signal?.aborted || e?.name === 'AbortError' || e?.detail === '请求已取消') return
      notification.error({ message: '加载伏笔数据失败', description: e?.detail || e?.message || '未知错误', placement: 'topRight' })
    }
    if (!signal?.aborted) setLoading(false)
  }

  const refreshData = useCallback(() => {
    abortRef.current?.abort()
    const ctrl = new AbortController()
    abortRef.current = ctrl
    return fetchData(ctrl.signal)
  }, [projectId, typeFilter, statusFilter])

  useEffect(() => {
    abortRef.current?.abort()
    const ctrl = new AbortController()
    abortRef.current = ctrl
    fetchData(ctrl.signal)
    return () => { ctrl.abort() }
  }, [projectId, typeFilter, statusFilter])

  useEffect(() => {
    const unsubs = [
      eventBus.on(DataEvents.SCENE_UPDATED, () => { refreshData() }),
      eventBus.on(DataEvents.CHAPTER_UPDATED, () => { refreshData() }),
      eventBus.on(DataEvents.CHARACTER_UPDATED, () => { refreshData() }),
      eventBus.on(DataEvents.PROJECT_SWITCHED, () => { refreshData() }),
    ]
    return () => unsubs.forEach(u => u())
  }, [refreshData])

  useEffect(() => {
    if (aiStatus === 'completed') {
      setAiGenerateTaskId(null)
      notification.success({ message: 'AI伏笔体系设计完成', placement: 'topRight' })
      refreshData()
    }
    if (aiStatus === 'failed') {
      setAiGenerateTaskId(null)
      notification.error({ message: 'AI伏笔体系设计失败', placement: 'topRight' })
      setAiGenerating(false)
    }
  }, [aiStatus])

  const filteredFS = useMemo(() => {
    let list = foreshadows
    return list
  }, [foreshadows])

  const healthStats = useMemo(() => ({
    normal: foreshadows.filter(f => f.health === 'normal').length,
    warning: foreshadows.filter(f => f.health === 'warning').length,
    danger: foreshadows.filter(f => f.health === 'danger').length,
  }), [foreshadows])

  const getLinkDensity = (fs: ForeshadowData) => {
    return (fs.worldview_refs?.length || 0) + (fs.character_refs?.length || 0) + (fs.foreshadow_links?.length || 0)
  }

  const getDensityLevel = (density: number): { label: string; color: string } => {
    if (density >= 5) return { label: '优秀', color: '#52c41a' }
    if (density >= 3) return { label: '良好', color: '#3b82f6' }
    if (density >= 1) return { label: '不足', color: '#faad14' }
    return { label: '缺失', color: '#ff4d4f' }
  }

  // ======== D3 Force Graph ========

  useEffect(() => {
    if (!svgRef.current || loading) return

    const svgEl = svgRef.current
    const svg = d3.select(svgEl)
    svg.selectAll('*').remove()
    if (tooltipRef.current) {
      tooltipRef.current.remove()
      tooltipRef.current = null
    }
    hasAutoZoomed.current = false

    const container = svgEl.parentElement
    const width = container?.clientWidth || svgEl.clientWidth || 800
    const height = container?.clientHeight || svgEl.clientHeight || 400

    if (width <= 0 || height <= 0) return

    svg.attr('width', width)
      .attr('height', height)
      .attr('viewBox', `0 0 ${width} ${height}`)

    const g = svg.append('g')

    const zoomBehavior = d3.zoom<SVGSVGElement, unknown>()
      .scaleExtent([0.2, 4])
      .on('zoom', (e) => { g.attr('transform', e.transform) })
    svg.call(zoomBehavior as any)

    const searchLower = graphSearch.toLowerCase()

    let fsList = foreshadows
    if (searchLower) {
      fsList = foreshadows.filter(f =>
        f.fs_code.toLowerCase().includes(searchLower) ||
        f.name.toLowerCase().includes(searchLower),
      )
    }

    const visibleIds = new Set(fsList.map(f => f.id))

    const connectionCount = new Map<string, number>()
    relations.forEach(r => {
      if (visibleIds.has(r.from_fs_id) && visibleIds.has(r.to_fs_id)) {
        connectionCount.set(r.from_fs_id, (connectionCount.get(r.from_fs_id) || 0) + 1)
        connectionCount.set(r.to_fs_id, (connectionCount.get(r.to_fs_id) || 0) + 1)
      }
    })

    const nodesData: any[] = fsList.map((f) => ({
      id: f.id,
      name: f.name,
      fsType: f.fs_type,
      nodeCategory: 'foreshadow',
      status: f.current_status,
      health: f.health,
      fs_code: f.fs_code,
      hasReveal: !!f.reveal_scene_id,
      connectionCount: connectionCount.get(f.id) || 0,
      density: getLinkDensity(f),
    }))

    const rawLinks = relations
      .filter(r => visibleIds.has(r.from_fs_id) && visibleIds.has(r.to_fs_id))
      .map(r => ({
        source: r.from_fs_id,
        target: r.to_fs_id,
        type: r.relation_type || 'enables',
        linkCategory: 'relation',
      }))

    const arcLinks: any[] = []
    const selectedFsData = selectedFS && arcMode ? foreshadows.find(f => f.id === selectedFS.id) : null

    if (selectedFsData && arcMode) {
      const selNode = nodesData.find((n: any) => n.id === selectedFsData.id)
      if (selNode) {
        const wvRefs = selectedFsData.worldview_refs || []
        wvRefs.forEach((w: WorldviewRef, i: number) => {
          const wvId = `wv-${selectedFsData.id}-${i}`
          nodesData.push({
            id: wvId,
            name: w.config_key,
            fsType: 'worldview',
            nodeCategory: 'worldview',
            description: w.description,
            fs_code: w.config_key,
            connectionCount: 0,
            density: 0,
          })
          arcLinks.push({
            source: wvId,
            target: selectedFsData.id,
            type: 'worldview_arc',
            linkCategory: 'arc',
          })
        })

        const crRefs = selectedFsData.character_refs || []
        crRefs.forEach((c: CharacterRef, i: number) => {
          const crId = `cr-${selectedFsData.id}-${i}`
          nodesData.push({
            id: crId,
            name: c.character_name,
            fsType: 'character',
            nodeCategory: 'character',
            description: c.description,
            fs_code: c.character_name,
            connectionCount: 0,
            density: 0,
          })
          arcLinks.push({
            source: crId,
            target: selectedFsData.id,
            type: 'character_arc',
            linkCategory: 'arc',
          })
        })

        const sceneLocations: { label: string; loc: string; tag: string }[] = []
        if (selectedFsData.plant_location) {
          sceneLocations.push({ label: '埋设', loc: selectedFsData.plant_location, tag: 'plant' })
        }
        ;(selectedFsData.reinforce_locations || []).forEach((loc, i) => {
          sceneLocations.push({ label: `强化${i + 1}`, loc, tag: 'reinforce' })
        })
        if (selectedFsData.reveal_location) {
          sceneLocations.push({ label: '揭露', loc: selectedFsData.reveal_location, tag: 'reveal' })
        }
        sceneLocations.forEach((s, i) => {
          const scId = `sc-${selectedFsData.id}-${i}`
          nodesData.push({
            id: scId,
            name: `${s.label}: ${s.loc}`,
            fsType: 'scene_location',
            nodeCategory: 'scene',
            sceneTag: s.tag,
            fs_code: s.label,
            connectionCount: 0,
            density: 0,
          })
          arcLinks.push({
            source: selectedFsData.id,
            target: scId,
            type: 'scene_arc',
            linkCategory: 'arc',
          })
        })
      }
    }

    const allLinks = [...rawLinks, ...arcLinks]

    if (nodesData.length === 0) {
      g.append('text')
        .attr('x', width / 2).attr('y', height / 2)
        .attr('text-anchor', 'middle')
        .attr('fill', '#9ca3af')
        .style('font-size', '14px')
        .text('暂无伏笔数据')
      return
    }

    const getNodeRadius = (d: any) => {
      if (d.nodeCategory === 'worldview') return 16
      if (d.nodeCategory === 'character') return 14
      if (d.nodeCategory === 'scene') return 12
      return (NODE_RADIUS[d.fsType] || 14) + Math.min((d.connectionCount || 0) * 2, 10)
    }

    const getNodeFill = (d: any) => {
      if (d.nodeCategory === 'worldview') return '#6366f1'
      if (d.nodeCategory === 'character') return '#10b981'
      if (d.nodeCategory === 'scene') return '#f97316'
      return HEALTH_COLORS[d.health] || '#6b7280'
    }

    const nodeCount = nodesData.length
    const area = width * height
    const idealAreaPerNode = Math.max(5000, area / nodeCount)
    const idealDist = Math.sqrt(idealAreaPerNode) * 0.85

    const sim = d3.forceSimulation(nodesData)
      .force('link', d3.forceLink(allLinks).id((d: any) => d.id).distance((d: any) => {
        if (d.linkCategory === 'arc') return 90
        return Math.min(idealDist, 140)
      }).strength((d: any) => {
        if (d.linkCategory === 'arc') return 0.7
        return 0.5
      }))
      .force('charge', d3.forceManyBody().strength(-Math.min(idealDist * 2.2, 400)))
      .force('center', d3.forceCenter(width / 2, height / 2).strength(0.07))
      .force('collision', d3.forceCollide().radius((d: any) => getNodeRadius(d) + 18))
      .force('x', d3.forceX(width / 2).strength(0.05))
      .force('y', d3.forceY(height / 2).strength(0.05))
      .alphaDecay(0.02)
      .velocityDecay(0.3)

    const defs = svg.append('defs')
    const arrowTypes = ['enables', 'depends_on', 'conflicts', 'reinforces']
    arrowTypes.forEach(type => {
      const color = type === 'conflicts' ? '#ef4444' : type === 'depends_on' ? '#f59e0b' : type === 'enables' ? '#3b82f6' : '#10b981'
      defs.append('marker')
        .attr('id', `arrow-${type}`)
        .attr('viewBox', '0 -5 10 10')
        .attr('refX', (d: any) => {
          // Dynamic refX based on target radius will be handled in tick
          return 20
        })
        .attr('refY', 0)
        .attr('markerWidth', 7)
        .attr('markerHeight', 7)
        .attr('orient', 'auto')
        .append('path')
        .attr('d', 'M0,-4L9,0L0,4')
        .attr('fill', color)
    })

    const arcTypes = [
      { type: 'worldview_arc', color: '#3b82f6', label: '世界观→伏笔' },
      { type: 'character_arc', color: '#10b981', label: '角色→伏笔' },
      { type: 'scene_arc', color: '#f97316', label: '伏笔→场景' },
    ]
    arcTypes.forEach(at => {
      defs.append('marker')
        .attr('id', `arrow-${at.type}`)
        .attr('viewBox', '0 -5 10 10')
        .attr('refX', 18)
        .attr('refY', 0)
        .attr('markerWidth', 6)
        .attr('markerHeight', 6)
        .attr('orient', 'auto')
        .append('path')
        .attr('d', 'M0,-4L8,0L0,4')
        .attr('fill', at.color)
        .attr('fill-opacity', 0.7)
    })

    const linkSelection = g.append('g').attr('class', 'links')
      .selectAll('line')
      .data(allLinks)
      .enter()
      .append('line')
      .attr('stroke', (d: any) => {
        if (d.linkCategory === 'arc') {
          if (d.type === 'worldview_arc') return '#3b82f6'
          if (d.type === 'character_arc') return '#10b981'
          if (d.type === 'scene_arc') return '#f97316'
        }
        return d.type === 'conflicts' ? '#ef4444' : d.type === 'depends_on' ? '#f59e0b' : d.type === 'enables' ? '#3b82f6' : '#10b981'
      })
      .attr('stroke-width', (d: any) => d.linkCategory === 'arc' ? 1.5 : 2)
      .attr('stroke-dasharray', (d: any) => {
        if (d.linkCategory === 'arc') return '6,3'
        return d.type === 'depends_on' ? '5,3' : d.type === 'conflicts' ? '3,3' : 'none'
      })
      .attr('stroke-opacity', (d: any) => d.linkCategory === 'arc' ? 0.6 : 0.8)
      .attr('marker-end', (d: any) => `url(#arrow-${d.type})`)

    const nodeSelection = g.append('g').attr('class', 'nodes')
      .selectAll('g')
      .data(nodesData)
      .enter()
      .append('g')
      .call(d3.drag<SVGGElement, any>()
        .on('start', (e: any, d: any) => { if (!e.active) sim.alphaTarget(0.3).restart(); d.fx = d.x; d.fy = d.y })
        .on('drag', (e: any, d: any) => { d.fx = e.x; d.fy = e.y })
        .on('end', (e: any, d: any) => { if (!e.active) sim.alphaTarget(0); d.fx = null; d.fy = null }) as any
      )
      .on('click', (_e: any, d: any) => {
        if (d.nodeCategory === 'foreshadow') {
          const fs = foreshadows.find(f => f.id === d.id)
          if (fs) setSelectedFS(fs)
        }
      })
      .style('cursor', (d: any) => d.nodeCategory === 'foreshadow' ? 'pointer' : 'default')

    // Node circles with ring for foreshadows
    nodeSelection.append('circle')
      .attr('r', (d: any) => getNodeRadius(d))
      .attr('fill', (d: any) => getNodeFill(d))
      .attr('stroke', (d: any) => {
        if (d.nodeCategory !== 'foreshadow') return 'rgba(255,255,255,0.9)'
        return TYPE_COLORS[d.fsType] || '#6b7280'
      })
      .attr('stroke-width', (d: any) => d.nodeCategory === 'foreshadow' ? 3 : 2)
      .attr('opacity', 0.95)

    // Inner white circle for foreshadows to create ring effect
    nodeSelection.filter((d: any) => d.nodeCategory === 'foreshadow')
      .append('circle')
      .attr('r', (d: any) => getNodeRadius(d) - 4)
      .attr('fill', (d: any) => {
        if (d.health === 'danger') return '#fef2f2'
        if (d.health === 'warning') return '#fffbeb'
        return '#f0fdf4'
      })
      .attr('pointer-events', 'none')

    // Type icon inside foreshadow nodes
    nodeSelection.filter((d: any) => d.nodeCategory === 'foreshadow')
      .append('text')
      .text((d: any) => {
        const icons: Record<string, string> = { global: '★', chapter: '◆', scene: '●', interactive: '▲' }
        return icons[d.fsType] || '●'
      })
      .attr('text-anchor', 'middle')
      .attr('dy', 1)
      .style('font-size', '10px')
      .style('font-weight', 'bold')
      .style('fill', (d: any) => TYPE_COLORS[d.fsType] || '#6b7280')
      .style('pointer-events', 'none')

    nodeSelection.filter((d: any) => d.nodeCategory === 'worldview')
      .append('text')
      .text('🌐')
      .attr('text-anchor', 'middle')
      .attr('dy', 4)
      .style('font-size', '12px')
      .style('pointer-events', 'none')

    nodeSelection.filter((d: any) => d.nodeCategory === 'character')
      .append('text')
      .text('👤')
      .attr('text-anchor', 'middle')
      .attr('dy', 4)
      .style('font-size', '11px')
      .style('pointer-events', 'none')

    nodeSelection.filter((d: any) => d.nodeCategory === 'scene')
      .append('text')
      .text('📍')
      .attr('text-anchor', 'middle')
      .attr('dy', 4)
      .style('font-size', '10px')
      .style('pointer-events', 'none')

    // Connection count badge
    nodeSelection.filter((d: any) => d.nodeCategory === 'foreshadow' && (d.connectionCount || 0) > 0)
      .append('circle')
      .attr('r', 7)
      .attr('cx', (d: any) => getNodeRadius(d) - 2)
      .attr('cy', -7)
      .attr('fill', '#3b82f6')
      .attr('stroke', '#fff')
      .attr('stroke-width', 1.5)

    nodeSelection.filter((d: any) => d.nodeCategory === 'foreshadow' && (d.connectionCount || 0) > 0)
      .append('text')
      .text((d: any) => d.connectionCount)
      .attr('x', (d: any) => getNodeRadius(d) - 2)
      .attr('y', -4)
      .attr('text-anchor', 'middle')
      .attr('fill', '#fff')
      .style('font-size', '9px')
      .style('font-weight', 'bold')
      .style('pointer-events', 'none')

    // Labels
    nodeSelection.filter((d: any) => d.nodeCategory === 'foreshadow')
      .append('text')
      .text((d: any) => d.fs_code)
      .attr('text-anchor', 'middle')
      .attr('dy', (d: any) => getNodeRadius(d) + 14)
      .attr('fill', '#374151')
      .style('font-size', '11px')
      .style('font-weight', '600')
      .style('pointer-events', 'none')

    nodeSelection.filter((d: any) => d.nodeCategory === 'foreshadow')
      .append('text')
      .text((d: any) => {
        const name = d.name || ''
        return name.length > 8 ? name.slice(0, 8) + '...' : name
      })
      .attr('text-anchor', 'middle')
      .attr('dy', (d: any) => getNodeRadius(d) + 28)
      .attr('fill', '#6b7280')
      .style('font-size', '9px')
      .style('pointer-events', 'none')

    nodeSelection.filter((d: any) => d.nodeCategory !== 'foreshadow')
      .append('text')
      .text((d: any) => {
        const name = d.name || ''
        const maxLen = d.nodeCategory === 'worldview' ? 10 : 6
        return name.length > maxLen ? name.slice(0, maxLen) + '...' : name
      })
      .attr('text-anchor', 'middle')
      .attr('dy', (d: any) => getNodeRadius(d) + 14)
      .attr('fill', (d: any) => {
        if (d.nodeCategory === 'worldview') return '#4f46e5'
        if (d.nodeCategory === 'character') return '#059669'
        return '#ea580c'
      })
      .style('font-size', '9px')
      .style('font-weight', '500')
      .style('pointer-events', 'none')

    // Tooltip
    const tooltip = d3.select('body').append('div')
      .attr('class', 'fs-graph-tooltip')
      .style('position', 'absolute')
      .style('visibility', 'hidden')
      .style('background', 'rgba(17,24,39,0.95)')
      .style('color', '#fff')
      .style('padding', '10px 14px')
      .style('border-radius', '8px')
      .style('font-size', '12px')
      .style('pointer-events', 'none')
      .style('z-index', '1000')
      .style('max-width', '240px')
      .style('line-height', '1.5')
      .style('box-shadow', '0 4px 12px rgba(0,0,0,0.2)')
    tooltipRef.current = tooltip

    nodeSelection.filter((d: any) => d.nodeCategory === 'foreshadow')
      .on('mouseenter', (e: any, d: any) => {
        const fs = foreshadows.find(f => f.id === d.id)
        const healthText = d.health === 'normal' ? '正常' : d.health === 'warning' ? '警告' : '危险'
        const healthColor = d.health === 'normal' ? '#86efac' : d.health === 'warning' ? '#fcd34d' : '#fca5a5'
        const html = `<div style="font-weight:700;margin-bottom:6px;font-size:13px;">${d.fs_code} · ${d.name}</div>
          <div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:6px;">
            <span style="background:${TYPE_COLORS[d.fsType]}22;color:${TYPE_COLORS[d.fsType]};padding:1px 6px;border-radius:4px;font-size:10px;font-weight:600;">${TYPE_LABELS[d.fsType] || d.fsType}</span>
            <span style="background:${healthColor}22;color:${healthColor};padding:1px 6px;border-radius:4px;font-size:10px;font-weight:600;">${healthText}</span>
            <span style="background:rgba(255,255,255,0.1);padding:1px 6px;border-radius:4px;font-size:10px;">${STATUS_LABELS[d.status] || d.status}</span>
          </div>
          ${fs?.surface_layer ? `<div style="border-top:1px solid rgba(255,255,255,0.15);padding-top:6px;font-size:11px;color:#d1d5db;">${fs.surface_layer.slice(0, 50)}${fs.surface_layer.length > 50 ? '...' : ''}</div>` : ''}`
        tooltip.html(html).style('visibility', 'visible')
      })
      .on('mousemove', (e: any) => {
        tooltip.style('left', (e.pageX + 12) + 'px').style('top', (e.pageY + 12) + 'px')
      })
      .on('mouseleave', () => {
        tooltip.style('visibility', 'hidden')
      })

    sim.on('tick', () => {
      nodesData.forEach((d: any) => {
        const r = getNodeRadius(d) + 15
        d.x = Math.max(r, Math.min(width - r, d.x))
        d.y = Math.max(r, Math.min(height - r, d.y))
      })

      linkSelection
        .attr('x1', (d: any) => d.source.x)
        .attr('y1', (d: any) => d.source.y)
        .attr('x2', (d: any) => {
          const r = getNodeRadius(d.target) + 6
          const dx = d.source.x - d.target.x
          const dy = d.source.y - d.target.y
          const dist = Math.sqrt(dx * dx + dy * dy) || 1
          return d.target.x + (dx / dist) * r
        })
        .attr('y2', (d: any) => {
          const r = getNodeRadius(d.target) + 6
          const dx = d.source.x - d.target.x
          const dy = d.source.y - d.target.y
          const dist = Math.sqrt(dx * dx + dy * dy) || 1
          return d.target.y + (dy / dist) * r
        })

      nodeSelection.attr('transform', (d: any) => `translate(${d.x},${d.y})`)
    })

    sim.on('end', () => {
      if (hasAutoZoomed.current) return
      hasAutoZoomed.current = true

      const bounds = g.node()?.getBBox()
      if (!bounds || bounds.width === 0 || bounds.height === 0) return

      const padding = 40
      const scale = Math.min(
        (width - padding * 2) / bounds.width,
        (height - padding * 2) / bounds.height,
        1.2
      )
      const translateX = (width - bounds.width * scale) / 2 - bounds.x * scale
      const translateY = (height - bounds.height * scale) / 2 - bounds.y * scale

      svg.transition().duration(600).call(
        zoomBehavior.transform as any,
        d3.zoomIdentity.translate(translateX, translateY).scale(scale)
      )
    })

    return () => {
      sim.stop()
      if (tooltipRef.current) {
        tooltipRef.current.remove()
        tooltipRef.current = null
      }
    }
  }, [foreshadows, relations, loading, graphSearch, selectedFS, arcMode])

  // ======== Handlers ========

  const openCreate = () => {
    setCreateForm({ ...EMPTY_FS_FORM, fs_code: '' })
    setCreateModalOpen(true)
  }

  const handleCreate = async () => {
    if (!projectId || !createForm.name) {
      notification.warning({ message: '请填写伏笔名称', placement: 'topRight' })
      return
    }
    setCreating(true)
    try {
      await foreshadowsApi.create(projectId, createForm)
      notification.success({ message: '伏笔创建成功', placement: 'topRight' })
      setCreateModalOpen(false)
      eventBus.emit(DataEvents.FORESHADOW_CREATED, { name: createForm.name })
      fetchData()
    } catch (e: any) {
      notification.error({ message: '创建失败', description: e?.detail || e?.message || '未知错误', placement: 'topRight' })
    }
    setCreating(false)
  }

  const startEdit = () => {
    if (!selectedFS) return
    setEditFS({ ...selectedFS })
    setEditing(true)
  }

  const saveEdit = async () => {
    if (!editFS || !projectId) return
    setSaving(true)
    try {
      const updated = await foreshadowsApi.update(projectId, editFS.id, editFS)
      const mapped = mapFS(updated)
      setForeshadows(prev => prev.map(f => f.id === mapped.id ? mapped : f))
      setSelectedFS(mapped)
      setEditing(false)
      eventBus.emit(DataEvents.FORESHADOW_UPDATED, { id: editFS.id, name: editFS.name })
      notification.success({ message: '保存成功', placement: 'topRight' })
    } catch (e: any) {
      notification.error({ message: '保存失败', description: e?.detail || e?.message || '未知错误', placement: 'topRight' })
    }
    setSaving(false)
  }

  const handleDelete = async () => {
    if (!confirmDelete || !projectId) return
    setDeleting(true)
    try {
      await foreshadowsApi.delete(projectId, confirmDelete)
      setForeshadows(prev => prev.filter(f => f.id !== confirmDelete))
      setRelations(prev => prev.filter(r => r.from_fs_id !== confirmDelete && r.to_fs_id !== confirmDelete))
      if (selectedFS?.id === confirmDelete) setSelectedFS(null)
      eventBus.emit(DataEvents.FORESHADOW_DELETED, { id: confirmDelete })
      notification.success({ message: '伏笔已删除', placement: 'topRight' })
    } catch (e: any) {
      notification.error({ message: '删除失败', description: e?.detail || e?.message || '未知错误', placement: 'topRight' })
    }
    setConfirmDelete(null)
    setDeleting(false)
  }

  const selectWowPlan = async (planId: string) => {
    if (!selectedFS || !projectId) return
    try {
      const updated = await foreshadowsApi.update(projectId, selectedFS.id, { wow_selected: planId })
      const mapped = mapFS(updated)
      setForeshadows(prev => prev.map(f => f.id === mapped.id ? mapped : f))
      setSelectedFS(mapped)
      notification.success({ message: '已设为最终方案', placement: 'topRight' })
    } catch (e: any) {
      notification.error({ message: '设置失败', description: e?.detail || e?.message || '未知错误', placement: 'topRight' })
    }
  }

  const handleAIWowPlan = async () => {
    if (!selectedFS || !projectId) return
    setWowGenerating(true)
    try {
      const data = await api.post<{ plans: Array<{ id?: string; type?: string; summary?: string; score?: number }> }>(`/ai/foreshadow-wow-gen/${selectedFS.id}`)
      const updatedFS = {
        ...selectedFS,
        wow_plans: Array.isArray(data.plans)
          ? data.plans.map((p, index) => ({
              id: p.id || `${selectedFS.id}-wow-${index + 1}`,
              type: p.type || 'AI方案',
              summary: p.summary || '',
              score: p.score || 0,
            }))
          : [],
      }
      setForeshadows(prev => prev.map(f => f.id === updatedFS.id ? updatedFS : f))
      setSelectedFS(updatedFS)
      notification.success({ message: '哇塞方案已生成', placement: 'topRight' })
    } catch (e: any) {
      notification.error({ message: '生成失败', description: e?.detail || e?.message || '未知错误', placement: 'topRight' })
    }
    setWowGenerating(false)
  }

  const handleAIDesign = async () => {
    if (!projectId) return
    setAiGenerating(true)
    try {
      const data = await api.post<{ task_id?: string }>(`/ai/projects/${projectId}/foreshadows/generate`)
      if (data.task_id) {
        setAiGenerateTaskId(data.task_id)
        notification.info({ message: 'AI伏笔体系设计已启动', description: '通过WebSocket实时追踪进度', placement: 'topRight' })
      } else {
        notification.success({ message: 'AI伏笔体系设计完成', placement: 'topRight' })
        setAiGenerating(false)
        fetchData()
      }
    } catch (e: any) {
      notification.error({ message: 'AI设计启动失败', description: e?.detail || e?.message || '未知错误', placement: 'topRight' })
      setAiGenerating(false)
    }
  }

  const handleHealthCheck = async () => {
    if (!projectId) return
    setHealthLoading(true)
    try {
      const data = await api.post<{ total: number; normal: number; warning: number; danger: number; suggestions: string[] }>(`/ai/foreshadow-health/${projectId}`)
      setHealthReport(data)
    } catch (e: any) {
      notification.error({ message: '健康检查失败', description: e?.detail || e?.message || '未知错误', placement: 'topRight' })
    }
    setHealthLoading(false)
  }

  const handleReactionCheck = async () => {
    if (!projectId) return
    setReactionLoading(true)
    try {
      const data = await api.post<{ suggestions?: string[] }>(`/ai/foreshadow-reaction/${projectId}`)
      setReactionReport(data.suggestions || [])
    } catch (e: any) {
      notification.error({ message: '化学反应分析失败', description: e?.detail || e?.message || '未知错误', placement: 'topRight' })
    }
    setReactionLoading(false)
  }

  if (!currentProject) {
    return (
      <div style={{ fontFamily: 'var(--font-family)' }}>
        <h2 className="section-title" style={{ fontSize: 24 }}>选项后果</h2>
        <div className="card-surface" style={{ textAlign: 'center', padding: 48 }}><Empty description={<span className="text-muted">请先创建或选择一个项目</span>} /></div>
      </div>
    )
  }

  const threeLayerEmpty = selectedFS && (!selectedFS.surface_layer || !selectedFS.deep_layer || !selectedFS.truth_layer)
  const isAiGenerating = aiGenerating && aiGenerateTaskId

  return (
      <div style={{ fontFamily: 'var(--font-family)', display: 'flex', flexDirection: 'column', height: '100%' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12, flexShrink: 0 }}>
          <div>
            <h2 className="section-title" style={{ fontSize: 24 }}>选项后果</h2>
            <p className="text-muted" style={{ margin: '4px 0 0' }}>选项后果网络与哇塞方案</p>
          </div>
        <div className="flex items-center gap-2 flex-wrap">
          <FilterOutlined className="text-gray-400" />
          <Select
            value={typeFilter} onChange={v => { setTypeFilter(v); setSelectedFS(null) }}
            size="small" style={{ width: 100 }}
            options={[
              { value: 'all', label: '全部类型' },
              { value: 'global', label: '全剧级' },
              { value: 'chapter', label: '章节级' },
              { value: 'scene', label: '场景级' },
              { value: 'interactive', label: '互动型' },
            ]}
          />
          <div className="w-px h-5 bg-gray-200 dark:bg-slate-600 mx-1" />
          <Select
            value={statusFilter} onChange={v => { setStatusFilter(v); setSelectedFS(null) }}
            size="small" style={{ width: 100 }}
            options={[
              { value: 'all', label: '全部状态' },
              { value: 'design', label: '设计中' },
              { value: 'planted', label: '已埋设' },
              { value: 'reinforced', label: '已强化' },
              { value: 'revealed', label: '已回收' },
            ]}
          />
          <div className="w-px h-5 bg-gray-200 dark:bg-slate-600 mx-1" />
          <Badge status="processing" text={<span className="text-xs">在线</span>} />
        </div>
        <Space>
          <Button
            icon={<RobotOutlined />}
            type="primary"
            size="small"
            loading={!!isAiGenerating}
            onClick={handleAIDesign}
          >
            {isAiGenerating ? `AI设计中 ${aiProgress}%` : 'AI设计伏笔体系'}
          </Button>
          <Button icon={<PlusOutlined />} size="small" onClick={openCreate}>新建伏笔</Button>
        </Space>
      </div>

      {/* ======== 图谱区域 ======== */}
      <Card size="small" title={
        <div className="flex items-center gap-2">
          <NodeIndexOutlined /><span className="text-sm font-semibold">伏笔关联图谱</span>
          <Button
            size="small"
            type={arcMode ? 'primary' : 'default'}
            icon={<ApartmentOutlined />}
            onClick={() => setArcMode(!arcMode)}
          >
            {arcMode ? '关闭弧线' : '联系弧线'}
          </Button>
          <div className="flex items-center gap-3 ml-auto text-xs text-gray-400">
            <Input
              prefix={<SearchOutlined />}
              placeholder="搜索编号/名称过滤节点..."
              size="small"
              style={{ width: 180 }}
              value={graphSearch}
              onChange={e => setGraphSearch(e.target.value)}
              allowClear
            />
            <span>━━ 支撑</span><span>╌╌ 依赖</span><span className="text-red-400">━━ 冲突</span>
            <span className="ml-2">● 正常</span><span className="text-amber-400">● 警告</span><span className="text-red-400">● 危险</span>
            {arcMode && (
              <>
                <span className="ml-2 border-l border-gray-300 pl-2">
                  <span className="text-blue-500">╌╌ 世界观</span>
                  <span className="text-green-500 ml-1">╌╌ 角色</span>
                  <span className="text-orange-500 ml-1">╌╌ 场景</span>
                </span>
              </>
            )}
          </div>
        </div>
      } styles={{ body: { padding: 0, minHeight: 300 } }} className="flex-1 min-h-0">
        {loading ? (
          <div className="h-full w-full flex items-center justify-center">
            <Spin><div className="py-12 text-gray-400">加载图谱数据...</div></Spin>
          </div>
        ) : (
          <div className="flex flex-col h-full">
            <div className="flex-1 relative" style={{ minHeight: 280 }}>
              <svg ref={svgRef} style={{ width: '100%', height: '100%', display: 'block' }} />
            </div>
            <p className="text-[10px] text-gray-400 px-3 py-1 shrink-0">🖱 缩放/拖拽 · 点击节点查看详情</p>
          </div>
        )}
      </Card>

      {/* ======== 下半部分 ======== */}
      <div className="flex gap-3 flex-1 min-h-0">
        {/* 左侧表格 */}
        <Card size="small" className="flex-1 min-w-0 flex flex-col" title={<span className="text-sm font-semibold">伏笔列表 ({filteredFS.length})</span>}>
          <Table<ForeshadowData>
            dataSource={filteredFS}
            rowKey="id"
            size="small"
            loading={loading}
            pagination={false}
            scroll={{ y: 'calc(50vh - 200px)' }}
            onRow={(r) => ({ onClick: () => setSelectedFS(r), className: selectedFS?.id === r.id ? 'bg-primary-50 dark:bg-primary-900/10' : '' })}
            columns={[
              { title: '编号', dataIndex: 'fs_code', width: 120, render: v => <Tag className="text-xs font-mono">{v}</Tag> },
              { title: '名称', dataIndex: 'name', width: 140, ellipsis: true },
              { title: '类型', dataIndex: 'fs_type', width: 70, render: v => <Tag color={TYPE_COLORS[v]} className="text-xs">{TYPE_LABELS[v]}</Tag> },
              {
                title: '状态', dataIndex: 'current_status', width: 80, render: v => (
                  <Badge status={v === 'revealed' ? 'success' : v === 'reinforced' ? 'processing' : v === 'planted' ? 'default' : 'warning'} text={<span className="text-xs">{STATUS_LABELS[v]}</span>} />
                ),
              },
              {
                title: '健康度', dataIndex: 'health', width: 80, render: v => (
                  <Progress percent={v === 'normal' ? 100 : v === 'warning' ? 66 : 33} size="small" strokeColor={HEALTH_COLORS[v]} showInfo={false} />
                ),
              },
              { title: '埋设', dataIndex: 'plant_scene_id', width: 80, ellipsis: true, render: v => v || <span className="text-gray-300">—</span> },
              { title: '揭露', dataIndex: 'reveal_scene_id', width: 80, ellipsis: true, render: v => v || <span className="text-gray-300">—</span> },
              {
                title: '密度', width: 70, render: (_: any, r: ForeshadowData) => {
                  const density = getLinkDensity(r)
                  const level = getDensityLevel(density)
                  return <Tag color={level.color === '#52c41a' ? 'green' : level.color === '#3b82f6' ? 'blue' : level.color === '#faad14' ? 'orange' : 'red'} className="text-[10px]">{density} {level.label}</Tag>
                },
              },
            ]}
          />
        </Card>

        {/* 右侧详情 */}
        <Card size="small" className="w-[420px] shrink-0 overflow-auto" title={null}>
          {selectedFS ? (
            <div>
              <div className="flex items-center justify-between mb-3">
                <div>
                  <Tag color={TYPE_COLORS[selectedFS.fs_type]} className="mb-1">{TYPE_LABELS[selectedFS.fs_type]}</Tag>
                  <h3 className="text-lg font-bold m-0">{selectedFS.name}</h3>
                  <span className="text-xs text-gray-400 font-mono">{selectedFS.fs_code}</span>
                </div>
                <Space size={4}>
                  <Button size="small" icon={<EditOutlined />} onClick={startEdit}>编辑</Button>
                  <Button size="small" danger icon={<DeleteOutlined />} onClick={() => setConfirmDelete(selectedFS.id)} />
                </Space>
              </div>

              {threeLayerEmpty && (
                <div className="flex items-center gap-1 text-red-500 text-xs mb-2 bg-red-50 dark:bg-red-900/10 p-2 rounded">
                  <WarningOutlined /> 三层结构中存在未填项
                </div>
              )}

              {/* 三层结构 */}
              <div className="space-y-2 mb-3">
                <div className="bg-gray-50 dark:bg-slate-800 border border-gray-200 dark:border-slate-600 rounded-md p-2.5">
                  <div className="text-[10px] text-gray-400 mb-1 font-semibold">🔍 表面层</div>
                  <p className="text-xs m-0 text-gray-600 dark:text-gray-400">{selectedFS.surface_layer || <span className="text-red-400 italic">未填写</span>}</p>
                </div>
                <div className="bg-blue-50 dark:bg-blue-900/10 border border-blue-200 dark:border-blue-800 rounded-md p-2.5">
                  <div className="text-[10px] text-blue-500 mb-1 font-semibold">🔍 深层</div>
                  <p className="text-xs m-0 text-blue-700 dark:text-blue-300">{selectedFS.deep_layer || <span className="text-red-400 italic">未填写</span>}</p>
                </div>
                <div className="bg-amber-50 dark:bg-amber-900/10 border border-amber-200 dark:border-amber-800 rounded-md p-2.5">
                  <div className="text-[10px] text-amber-600 mb-1 font-semibold">🔍 真相层</div>
                  <p className="text-xs m-0 text-amber-800 dark:text-amber-300">{selectedFS.truth_layer || <span className="text-red-400 italic">未填写</span>}</p>
                </div>
              </div>

              {/* 时间线 */}
              <div className="mb-3 p-2 bg-gray-50 dark:bg-slate-800 rounded">
                <div className="text-xs text-gray-400 mb-1 font-semibold">⏱ 伏笔时间线</div>
                <div className="flex items-center gap-1 text-xs flex-wrap">
                  <Tag color="purple" className="text-[10px]">🌱 埋设</Tag>
                  {selectedFS.reinforce_scenes.length > 0 ? (
                    selectedFS.reinforce_scenes.map((_, i) => <Tag key={i} color="blue" className="text-[10px]">🔄 强化{i + 1}</Tag>)
                  ) : <span className="text-gray-300 text-xs">暂无强化</span>}
                  <Tag color={selectedFS.reveal_scene_id ? 'gold' : 'default'} className="text-[10px]">
                    💡 {selectedFS.reveal_scene_id ? '回收' : '未规划回收'}
                  </Tag>
                </div>
              </div>

              {/* 哇塞方案 */}
              <div className="mb-3">
                <div className="flex items-center justify-between mb-1">
                  <span className="text-xs text-gray-400 font-semibold">⭐ 哇塞方案</span>
                  <Button size="small" type="link" icon={<BulbOutlined />} loading={wowGenerating} onClick={handleAIWowPlan} className="text-xs">生成方案</Button>
                </div>
                {selectedFS.wow_plans.length === 0 ? (
                  <div className="text-xs text-gray-300 italic p-2 bg-gray-50 dark:bg-slate-800 rounded">尚未设计</div>
                ) : (
                  <div className="space-y-1.5 max-h-48 overflow-auto">
                    {selectedFS.wow_plans.map(p => (
                      <div key={p.id}
                        onClick={() => selectWowPlan(p.id)}
                        className={`flex items-start gap-2 p-2 rounded-md border cursor-pointer transition-all text-xs ${selectedFS.wow_selected === p.id ? 'border-amber-400 bg-amber-50 dark:bg-amber-900/20' : 'border-gray-200 dark:border-slate-600 hover:border-amber-300'}`}
                      >
                        {selectedFS.wow_selected === p.id && <TrophyOutlined className="text-amber-500 mt-0.5" />}
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-1.5 mb-0.5">
                            <Tag color="purple" className="text-[10px] leading-none">{p.type}</Tag>
                            <span className="text-[10px] text-gray-400">评分 {p.score}</span>
                          </div>
                          <p className="m-0 text-gray-600 dark:text-gray-400">{p.summary}</p>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* 关联世界观 */}
              <div className="mb-3">
                <div className="text-xs text-gray-400 mb-1 font-semibold flex items-center gap-1">
                  <GlobalOutlined /> 关联世界观
                </div>
                {(!selectedFS.worldview_refs || selectedFS.worldview_refs.length === 0) ? (
                  <div className="text-xs text-gray-300 italic p-2 bg-gray-50 dark:bg-slate-800 rounded">暂无关联世界观</div>
                ) : (
                  <div className="space-y-1.5">
                    {selectedFS.worldview_refs.map((w, i) => (
                      <div
                        key={i}
                        className="flex items-start gap-2 p-2 rounded-md border border-blue-200 dark:border-blue-800 bg-blue-50/50 dark:bg-blue-900/10 cursor-pointer hover:border-blue-400 transition-all"
                        onClick={() => navigate('/world')}
                      >
                        <GlobalOutlined className="text-blue-500 mt-0.5 shrink-0" />
                        <div className="flex-1 min-w-0">
                          <div className="text-[10px] text-blue-600 dark:text-blue-400 font-semibold mb-0.5">{w.config_key}</div>
                          <p className="m-0 text-xs text-gray-600 dark:text-gray-400">{w.description}</p>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* 关联角色 */}
              <div className="mb-3">
                <div className="text-xs text-gray-400 mb-1 font-semibold flex items-center gap-1">
                  <UserOutlined /> 关联角色
                </div>
                {(!selectedFS.character_refs || selectedFS.character_refs.length === 0) ? (
                  <div className="text-xs text-gray-300 italic p-2 bg-gray-50 dark:bg-slate-800 rounded">暂无关联角色</div>
                ) : (
                  <div className="space-y-1.5">
                    {selectedFS.character_refs.map((c, i) => (
                      <div
                        key={i}
                        className="flex items-start gap-2 p-2 rounded-md border border-green-200 dark:border-green-800 bg-green-50/50 dark:bg-green-900/10"
                      >
                        <div className="w-7 h-7 rounded-full bg-green-500 flex items-center justify-center text-white text-xs font-bold shrink-0">
                          {c.character_name.charAt(0)}
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className="text-xs text-green-700 dark:text-green-400 font-semibold">{c.character_name}</div>
                          <p className="m-0 text-[10px] text-gray-500 dark:text-gray-400">{c.description}</p>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* 关联场景 */}
              <div className="mb-3">
                <div className="text-xs text-gray-400 mb-1 font-semibold flex items-center gap-1">
                  <EnvironmentOutlined /> 关联场景
                </div>
                <div className="space-y-1">
                  {selectedFS.plant_location && (
                    <div className="flex items-center gap-2 text-xs">
                      <Tag color="purple" className="text-[10px]">🌱 埋设</Tag>
                      <span className="text-gray-600 dark:text-gray-400">{selectedFS.plant_location}</span>
                    </div>
                  )}
                  {selectedFS.reinforce_locations?.length > 0 && selectedFS.reinforce_locations.map((loc, i) => (
                    <div key={i} className="flex items-center gap-2 text-xs">
                      <Tag color="blue" className="text-[10px]">🔄 强化{i + 1}</Tag>
                      <span className="text-gray-600 dark:text-gray-400">{loc}</span>
                    </div>
                  ))}
                  {selectedFS.reveal_location && (
                    <div className="flex items-center gap-2 text-xs">
                      <Tag color="gold" className="text-[10px]">💡 揭露</Tag>
                      <span className="text-gray-600 dark:text-gray-400">{selectedFS.reveal_location}</span>
                    </div>
                  )}
                  {!selectedFS.plant_location && (!selectedFS.reinforce_locations || selectedFS.reinforce_locations.length === 0) && !selectedFS.reveal_location && (
                    <div className="text-xs text-gray-300 italic p-2 bg-gray-50 dark:bg-slate-800 rounded">暂无关联场景</div>
                  )}
                </div>
              </div>

              {/* 关联密度 */}
              <div className="mb-3 p-2 bg-gray-50 dark:bg-slate-800 rounded">
                <div className="text-xs text-gray-400 mb-1 font-semibold flex items-center gap-1">
                  <ApartmentOutlined /> 关联密度
                </div>
                {(() => {
                  const density = getLinkDensity(selectedFS)
                  const level = getDensityLevel(density)
                  return (
                    <div className="flex items-center gap-2">
                      <span className="text-xs text-gray-500">关联数: {density}</span>
                      <Tag color={level.color === '#52c41a' ? 'green' : level.color === '#3b82f6' ? 'blue' : level.color === '#faad14' ? 'orange' : 'red'} className="text-[10px]">
                        {level.label}
                      </Tag>
                      <div className="flex-1">
                        <Progress
                          percent={Math.min(density * 20, 100)}
                          size="small"
                          strokeColor={level.color}
                          showInfo={false}
                        />
                      </div>
                    </div>
                  )
                })()}
              </div>

              {/* 关联信息 */}
              <div className="space-y-2 text-xs">
                <div className="flex items-center justify-between">
                  <span className="text-gray-400 font-semibold">伏笔关联</span>
                  <Button size="small" type="link" className="text-xs !px-0" onClick={() => {
                    setRelCreateOpen(true)
                    setRelCreateForm({ from_fs_id: selectedFS.id, to_fs_id: '', relation_type: 'enables' })
                  }}>+ 新建关联</Button>
                </div>
                {relations.filter(r => r.from_fs_id === selectedFS.id || r.to_fs_id === selectedFS.id).length > 0 ? (
                  <div className="space-y-1">
                    {relations.filter(r => r.from_fs_id === selectedFS.id || r.to_fs_id === selectedFS.id).map(r => {
                      const isFrom = r.from_fs_id === selectedFS.id
                      const otherId = isFrom ? r.to_fs_id : r.from_fs_id
                      const other = foreshadows.find(f => f.id === otherId)
                      const typeLabel: Record<string, { text: string; color: string }> = {
                        enables: { text: '支撑', color: 'blue' },
                        depends_on: { text: '依赖', color: 'orange' },
                        conflicts: { text: '冲突', color: 'red' },
                        related: { text: '关联', color: 'default' },
                        reinforces: { text: '强化', color: 'green' },
                      }
                      const info = typeLabel[r.relation_type] || typeLabel.related
                      return (
                        <div key={r.id} className="flex items-center gap-1 bg-gray-50 dark:bg-slate-800 rounded px-2 py-1">
                          <Tag color={info.color} className="text-[10px] !m-0">{info.text}</Tag>
                          <span className="text-gray-500">{isFrom ? '→' : '←'}</span>
                          <span className="font-medium">{other ? `${other.fs_code} ${other.name}` : otherId.slice(0, 8)}</span>
                          <div className="ml-auto flex gap-1">
                            <Button size="small" type="text" className="!text-xs !h-4 !w-4 !p-0" icon={<EditOutlined />} onClick={() => {
                              setRelEditTarget(r)
                              setRelEditType(r.relation_type)
                              setRelEditOpen(true)
                            }} />
                            <Button size="small" type="text" danger className="!text-xs !h-4 !w-4 !p-0" icon={<DeleteOutlined />} onClick={async () => {
                              if (!projectId) return
                              try {
                                await foreshadowsApi.deleteRelation(projectId, r.id)
                                setRelations(prev => prev.filter(x => x.id !== r.id))
                                notification.success({ message: '关联已删除', placement: 'topRight' })
                                eventBus.emit(DataEvents.FORESHADOW_UPDATED)
                              } catch (e: any) {
                                notification.error({ message: '删除失败', description: e?.detail || e?.message, placement: 'topRight' })
                              }
                            }} />
                          </div>
                        </div>
                      )
                    })}
                  </div>
                ) : (
                  <div className="text-gray-300 italic p-2 bg-gray-50 dark:bg-slate-800 rounded">暂无关联</div>
                )}
              </div>
            </div>
          ) : (
            <div className="text-center py-12 text-gray-300"><EyeOutlined className="text-3xl mb-2 block" />点击伏笔查看详情</div>
          )}
        </Card>
      </div>

      {/* ======== 底部工具栏 ======== */}
      <Card size="small" className="shrink-0">
        <div className="flex items-center gap-2">
          <Button icon={<CheckCircleOutlined />} loading={healthLoading} onClick={handleHealthCheck} size="small">
            伏笔健康检查
          </Button>
          <Button icon={<ExperimentOutlined />} loading={reactionLoading} onClick={handleReactionCheck} size="small">
            化学反应分析
          </Button>
          {healthReport && (
            <div className="flex items-center gap-2 ml-2 text-xs">
              <span className="text-gray-400">健康报告:</span>
              <Tag color="green">{healthReport.normal} 正常</Tag>
              <Tag color="gold">{healthReport.warning} 警告</Tag>
              <Tag color="red">{healthReport.danger} 危险</Tag>
              <Button type="text" size="small" icon={<CloseOutlined />} onClick={() => setHealthReport(null)} />
            </div>
          )}
          {reactionReport && (
            <Button type="link" size="small" onClick={() => Modal.info({ title: '化学反应分析', content: <div>{reactionReport.map((s, i) => <p key={i} className="text-sm">{s}</p>)}</div>, width: 500 })}>
              查看分析结果 ({reactionReport.length} 条)
            </Button>
          )}
        </div>
        {(healthReport?.suggestions?.length || 0) > 0 && (
          <div className="mt-2 p-2 bg-gray-50 dark:bg-slate-800 rounded text-xs space-y-1">
            {healthReport?.suggestions?.map((s, i) => (
              <div key={i} className="flex items-start gap-1 text-gray-600 dark:text-gray-400">
                <WarningOutlined className="text-amber-500 mt-0.5 shrink-0" /><span>{s}</span>
              </div>
            ))}
          </div>
        )}
      </Card>

      {/* ======== 新建伏笔弹窗 ======== */}
      <Modal
        open={createModalOpen}
        title="新建伏笔"
        width={640}
        onOk={handleCreate}
        onCancel={() => setCreateModalOpen(false)}
        okText="创建"
        confirmLoading={creating}
      >
        <div className="space-y-3 max-h-[60vh] overflow-auto">
          <div className="flex gap-2">
            <div className="flex-1">
              <label className="text-xs text-gray-400 block mb-1">编号</label>
              <Input size="small" value={createForm.fs_code || ''} onChange={e => setCreateForm({ ...createForm, fs_code: e.target.value })} />
            </div>
            <div className="flex-1">
              <label className="text-xs text-gray-400 block mb-1">名称 *</label>
              <Input size="small" value={createForm.name || ''} onChange={e => setCreateForm({ ...createForm, name: e.target.value })} />
            </div>
          </div>
          <div className="flex gap-2">
            <div className="flex-1">
              <label className="text-xs text-gray-400 block mb-1">类型</label>
              <Select size="small" className="w-full" value={createForm.fs_type} onChange={v => setCreateForm({ ...createForm, fs_type: v })}
                options={Object.entries(TYPE_LABELS).map(([k, v]) => ({ value: k, label: v }))} />
            </div>
            <div className="flex-1">
              <label className="text-xs text-gray-400 block mb-1">状态</label>
              <Select size="small" className="w-full" value={createForm.current_status} onChange={v => setCreateForm({ ...createForm, current_status: v })}
                options={Object.entries(STATUS_LABELS).map(([k, v]) => ({ value: k, label: v }))} />
            </div>
          </div>
          <div><label className="text-xs text-gray-400 block mb-1">表面层</label><TextArea size="small" rows={2} value={createForm.surface_layer || ''} onChange={e => setCreateForm({ ...createForm, surface_layer: e.target.value })} /></div>
          <div><label className="text-xs text-gray-400 block mb-1">深层</label><TextArea size="small" rows={2} value={createForm.deep_layer || ''} onChange={e => setCreateForm({ ...createForm, deep_layer: e.target.value })} /></div>
          <div><label className="text-xs text-gray-400 block mb-1">真相层</label><TextArea size="small" rows={3} value={createForm.truth_layer || ''} onChange={e => setCreateForm({ ...createForm, truth_layer: e.target.value })} /></div>
        </div>
      </Modal>

      {/* ======== 编辑弹窗 ======== */}
      <Modal open={editing && editFS !== null} title="编辑伏笔" width={640}
        onOk={saveEdit} onCancel={() => { setEditing(false); setEditFS(null) }} okText="保存" confirmLoading={saving}>
        {editFS && (
          <div className="space-y-3 max-h-[60vh] overflow-auto">
            <div className="flex gap-2">
              <div className="flex-1">
                <label className="text-xs text-gray-400 block mb-1">编号</label>
                <Input size="small" value={editFS.fs_code} onChange={e => setEditFS({ ...editFS, fs_code: e.target.value })} />
              </div>
              <div className="flex-1">
                <label className="text-xs text-gray-400 block mb-1">名称</label>
                <Input size="small" value={editFS.name} onChange={e => setEditFS({ ...editFS, name: e.target.value })} />
              </div>
            </div>
            <div className="flex gap-2">
              <div className="flex-1">
                <label className="text-xs text-gray-400 block mb-1">类型</label>
                <Select size="small" className="w-full" value={editFS.fs_type} onChange={v => setEditFS({ ...editFS, fs_type: v })}
                  options={Object.entries(TYPE_LABELS).map(([k, v]) => ({ value: k, label: v }))} />
              </div>
              <div className="flex-1">
                <label className="text-xs text-gray-400 block mb-1">状态</label>
                <Select size="small" className="w-full" value={editFS.current_status} onChange={v => setEditFS({ ...editFS, current_status: v })}
                  options={Object.entries(STATUS_LABELS).map(([k, v]) => ({ value: k, label: v }))} />
              </div>
            </div>
            <div><label className="text-xs text-gray-400 block mb-1">表面层</label><TextArea size="small" rows={2} value={editFS.surface_layer || ''} onChange={e => setEditFS({ ...editFS, surface_layer: e.target.value })} /></div>
            <div><label className="text-xs text-gray-400 block mb-1">深层</label><TextArea size="small" rows={2} value={editFS.deep_layer || ''} onChange={e => setEditFS({ ...editFS, deep_layer: e.target.value })} /></div>
            <div><label className="text-xs text-gray-400 block mb-1">真相层</label><TextArea size="small" rows={3} value={editFS.truth_layer || ''} onChange={e => setEditFS({ ...editFS, truth_layer: e.target.value })} /></div>
          </div>
        )}
      </Modal>

      {/* ======== 删除确认弹窗 ======== */}
      <Modal
        open={confirmDelete !== null}
        title="删除伏笔"
        onOk={handleDelete}
        onCancel={() => setConfirmDelete(null)}
        okText="确认删除"
        okButtonProps={{ danger: true, loading: deleting }}
        cancelText="取消"
      >
        <p>确认删除该伏笔？将同时清理所有关联关系。</p>
      </Modal>

      {/* 新建关联弹窗 */}
      <Modal
        open={relCreateOpen}
        title="新建伏笔关联"
        width={480}
        onCancel={() => setRelCreateOpen(false)}
        okText="创建"
        onOk={async () => {
          if (!projectId || !relCreateForm.to_fs_id) {
            notification.warning({ message: '请选择目标伏笔', placement: 'topRight' })
            return
          }
          try {
            const result = await foreshadowsApi.createRelation(projectId, {
              from_fs_id: relCreateForm.from_fs_id,
              to_fs_id: relCreateForm.to_fs_id,
              relation_type: relCreateForm.relation_type,
            })
            setRelations(prev => [...prev, mapRel(result)])
            setRelCreateOpen(false)
            notification.success({ message: '关联已创建', placement: 'topRight' })
            eventBus.emit(DataEvents.FORESHADOW_UPDATED)
          } catch (e: any) {
            notification.error({ message: '创建失败', description: e?.detail || e?.message, placement: 'topRight' })
          }
        }}
      >
        <div className="space-y-3">
          <div>
            <label className="text-sm font-medium block mb-1">源伏笔</label>
            <Select className="w-full" value={relCreateForm.from_fs_id} onChange={v => setRelCreateForm(p => ({ ...p, from_fs_id: v }))}>
              {foreshadows.map(f => <Option key={f.id} value={f.id}>{f.fs_code} - {f.name}</Option>)}
            </Select>
          </div>
          <div>
            <label className="text-sm font-medium block mb-1">目标伏笔</label>
            <Select className="w-full" value={relCreateForm.to_fs_id || undefined} placeholder="选择目标伏笔" onChange={v => setRelCreateForm(p => ({ ...p, to_fs_id: v }))}>
              {foreshadows.filter(f => f.id !== relCreateForm.from_fs_id).map(f => <Option key={f.id} value={f.id}>{f.fs_code} - {f.name}</Option>)}
            </Select>
          </div>
          <div>
            <label className="text-sm font-medium block mb-1">关系类型</label>
            <Select className="w-full" value={relCreateForm.relation_type} onChange={v => setRelCreateForm(p => ({ ...p, relation_type: v }))}>
              <Option value="enables">支撑</Option>
              <Option value="depends_on">依赖</Option>
              <Option value="conflicts">冲突</Option>
              <Option value="reinforces">强化</Option>
              <Option value="related">关联</Option>
            </Select>
          </div>
        </div>
      </Modal>

      {/* 编辑关联弹窗 */}
      <Modal
        open={relEditOpen}
        title="编辑伏笔关联"
        width={400}
        onCancel={() => { setRelEditOpen(false); setRelEditTarget(null) }}
        okText="保存"
        onOk={async () => {
          if (!projectId || !relEditTarget) return
          try {
            await foreshadowsApi.updateRelation(projectId, relEditTarget.id, {
              relation_type: relEditType,
            })
            setRelations(prev => prev.map(r => r.id === relEditTarget.id ? { ...r, relation_type: relEditType } : r))
            setRelEditOpen(false)
            setRelEditTarget(null)
            notification.success({ message: '关联已更新', placement: 'topRight' })
            eventBus.emit(DataEvents.FORESHADOW_UPDATED)
          } catch (e: any) {
            notification.error({ message: '更新失败', description: e?.detail || e?.message, placement: 'topRight' })
          }
        }}
      >
        {relEditTarget && (
          <div className="space-y-3">
            <div>
              <label className="text-sm font-medium block mb-1">关系类型</label>
              <Select className="w-full" value={relEditType} onChange={setRelEditType}>
                <Option value="enables">支撑</Option>
                <Option value="depends_on">依赖</Option>
                <Option value="conflicts">冲突</Option>
                <Option value="reinforces">强化</Option>
                <Option value="related">关联</Option>
              </Select>
            </div>
            <div className="text-xs text-gray-400">
              {foreshadows.find(f => f.id === relEditTarget.from_fs_id)?.fs_code || relEditTarget.from_fs_id.slice(0, 8)}
              {' → '}
              {foreshadows.find(f => f.id === relEditTarget.to_fs_id)?.fs_code || relEditTarget.to_fs_id.slice(0, 8)}
            </div>
          </div>
        )}
      </Modal>
    </div>
  )
}

function mapFS(f: any): ForeshadowData {
  return {
    id: f.id,
    project_id: f.project_id,
    fs_code: f.fs_code,
    name: f.name,
    fs_type: f.fs_type,
    surface_layer: f.surface_layer || null,
    deep_layer: f.deep_layer || null,
    truth_layer: f.truth_layer || null,
    plant_scene_id: f.plant_scene_id || null,
    reinforce_scenes: Array.isArray(f.reinforce_scenes) ? f.reinforce_scenes : [],
    reveal_scene_id: f.reveal_scene_id || null,
    wow_factor: f.wow_factor || null,
    player_reaction: f.player_reaction || null,
    depends_on: Array.isArray(f.depends_on) ? f.depends_on : [],
    enables: Array.isArray(f.enables) ? f.enables : [],
    current_status: f.current_status || 'design',
    reinforce_count: f.reinforce_count || 0,
    health: f.health || 'normal',
    wow_plans: Array.isArray(f.wow_plans) ? f.wow_plans.map((p: any) => ({
      id: p.id || '',
      type: p.type || '',
      summary: p.summary || '',
      score: p.score || 0,
    })) : [],
    wow_selected: f.wow_selected || null,
    worldview_refs: Array.isArray(f.worldview_refs) ? f.worldview_refs.map((w: any) => ({
      config_key: w.config_key || '',
      description: w.description || '',
    })) : [],
    character_refs: Array.isArray(f.character_refs) ? f.character_refs.map((c: any) => ({
      character_name: c.character_name || '',
      description: c.description || '',
    })) : [],
    foreshadow_links: Array.isArray(f.foreshadow_links) ? f.foreshadow_links : [],
    plant_location: f.plant_location || null,
    reinforce_locations: Array.isArray(f.reinforce_locations) ? f.reinforce_locations : [],
    reveal_location: f.reveal_location || null,
    created_at: f.created_at,
  }
}

function mapRel(r: any): FSRelation {
  return {
    id: r.id,
    project_id: r.project_id,
    from_fs_id: r.from_fs_id,
    to_fs_id: r.to_fs_id,
    relation_type: r.relation_type,
  }
}
