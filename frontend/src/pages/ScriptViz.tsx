import { useState, useEffect, useCallback, useMemo, useRef } from 'react'
import {
  ReactFlow, Background, Controls, MiniMap, useNodesState, useEdgesState,
  Node, Edge, BackgroundVariant, Panel, ConnectionMode, MarkerType,
  ReactFlowProvider, useReactFlow, addEdge, Connection,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import {
  Card, Button, Upload, Tag, Space, App, Spin, Empty,
  Drawer, Modal, Input, Tooltip, Segmented, Badge, Typography, Slider, Select,
} from 'antd'
import {
  AimOutlined, UploadOutlined, RobotOutlined, SaveOutlined,
  DiffOutlined, CloseOutlined, UndoOutlined,
  PlayCircleOutlined, ThunderboltOutlined,
  NodeIndexOutlined, ReloadOutlined, DeleteOutlined, EditOutlined,
} from '@ant-design/icons'
import { useProjectStore } from '../stores/projectStore'
import { api, relationsApi, foreshadowsApi } from '../api/client'
import { eventBus, DataEvents } from '../services/eventBus'
import CharacterNode from '../components/script-viz/CharacterNode'
import SceneNode from '../components/script-viz/SceneNode'
import ForeshadowNode from '../components/script-viz/ForeshadowNode'
import EventNode from '../components/script-viz/EventNode'
import ScriptEdge from '../components/script-viz/ScriptEdge'
import NodeInfoCard, { CardData, CardNodeType } from '../components/script-viz/NodeInfoCard'

const { Text } = Typography
const { Option } = Select

type ViewMode = 'characters' | 'branches' | 'foreshadows' | 'timeline' | 'endings'

interface AnalysisData {
  project_id: string
  characters: any[]
  relations: any[]
  scenes: any[]
  foreshadows: any[]
  events: any[]
  scene_links: any[]
  foreshadow_links: any[]
}

const NODE_TYPES = {
  character: CharacterNode,
  scene: SceneNode,
  foreshadow: ForeshadowNode,
  event: EventNode,
} as const

const EDGE_TYPES = {
  scriptEdge: ScriptEdge,
} as const

const initialNodes: Node[] = []
const initialEdges: Edge[] = []

// Relation type options for characters
const CHARACTER_RELATION_TYPES = [
  { value: 'related', label: '关联' },
  { value: 'friend', label: '朋友' },
  { value: 'enemy', label: '敌人' },
  { value: 'lover', label: '恋人' },
  { value: 'family', label: '家人' },
  { value: 'mentor', label: '师徒' },
  { value: 'rival', label: '对手' },
  { value: 'ally', label: '盟友' },
]

// Relation type options for foreshadows
const FORESHADOW_RELATION_TYPES = [
  { value: 'related', label: '关联' },
  { value: 'depends_on', label: '依赖' },
  { value: 'enables', label: '启用' },
  { value: 'contradicts', label: '矛盾' },
  { value: 'reinforces', label: '强化' },
]

function ScriptVizInner() {
  const { notification } = App.useApp()
  const { currentProject } = useProjectStore()
  const { fitView } = useReactFlow()

  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes)
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges)
  const [analysisData, setAnalysisData] = useState<AnalysisData | null>(null)
  const [loading, setLoading] = useState(false)
  const [viewMode, setViewMode] = useState<ViewMode>('characters')
  const [selectedNode, setSelectedNode] = useState<string | null>(null)
  const [cardData, setCardData] = useState<CardData | null>(null)
  const [cardPosition, setCardPosition] = useState({ x: 0, y: 0 })
  const [highlightedNode, setHighlightedNode] = useState<string | null>(null)
  const [editDrawerOpen, setEditDrawerOpen] = useState(false)
  const [editTarget, setEditTarget] = useState<{ type: CardNodeType; id: string } | null>(null)
  const [regenerating, setRegenerating] = useState(false)
  const [regenerateResult, setRegenerateResult] = useState<any>(null)
  const [compareModalOpen, setCompareModalOpen] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [editInstruction, setEditInstruction] = useState('')
  const [editChanges, setEditChanges] = useState<Record<string, string>>({})
  const [allEdits, setAllEdits] = useState<any[]>([])
  const [savingEdge, setSavingEdge] = useState(false)

  // Edge editing state
  const [selectedEdge, setSelectedEdge] = useState<Edge | null>(null)
  const [edgeEditOpen, setEdgeEditOpen] = useState(false)
  const [edgeEditType, setEdgeEditType] = useState('related')
  const [edgeEditTrust, setEdgeEditTrust] = useState(5)
  const [edgeEditFavor, setEdgeEditFavor] = useState(5)
  const [edgeEditStrength, setEdgeEditStrength] = useState(5)
  const [edgeEditDescription, setEdgeEditDescription] = useState('')
  const [edgeDeleting, setEdgeDeleting] = useState(false)

  const containerRef = useRef<HTMLDivElement>(null)

  const buildGraph = useCallback((data: AnalysisData, mode: ViewMode, options?: { preservePositions?: boolean }) => {
    const newNodes: Node[] = []
    const newEdges: Edge[] = []
    const nodePositions = new Map<string, { x: number; y: number }>()
    const existingNodesMap = new Map<string, Node>()
    nodes.forEach(n => existingNodesMap.set(n.id, n))

    const cols = 4
    const spacingX = 280
    const spacingY = 260

    if (mode === 'characters') {
      data.characters.forEach((ch: any, i: number) => {
        const col = i % cols
        const row = Math.floor(i / cols)
        const defaultX = 100 + col * spacingX
        const defaultY = 80 + row * spacingY
        const existing = options?.preservePositions ? existingNodesMap.get(ch.id) : undefined
        const x = existing?.position?.x ?? defaultX
        const y = existing?.position?.y ?? defaultY
        nodePositions.set(ch.id, { x, y })

        const sceneCount = data.scene_links.filter(
          (l: any) => l.source === ch.id || l.target === ch.id
        ).length
        const relationCount = data.relations.filter(
          (r: any) => r.char_a_id === ch.id || r.char_b_id === ch.id
        ).length

        newNodes.push({
          id: ch.id, type: 'character', position: { x, y },
          width: existing?.width,
          height: existing?.height,
          data: {
            label: ch.name, role_type: ch.role_type || 'supporting',
            core_goal: ch.core_goal || '', core_fear: ch.core_fear || '',
            surface_image: ch.surface_image, arc_description: ch.arc_description,
            status: ch.status, sceneCount, relationCount,
            foreshadowCount: 0,
          },
        })
      })

      data.relations.forEach((rel: any) => {
        newEdges.push({
          id: `rel-${rel.id}`,
          source: rel.char_a_id, target: rel.char_b_id,
          type: 'scriptEdge',
          animated: false,
          data: {
            dbId: rel.id,
            strength: Math.max(1, Math.min(10, rel.trust / 10)),
            edgeType: rel.relation_type || 'related',
            trust: rel.trust,
            favor: rel.favor,
            relationType: 'character',
            description: rel.description || '',
          },
          markerEnd: { type: MarkerType.ArrowClosed, width: 10, height: 10 },
        })
      })
    } else if (mode === 'branches') {
      data.scenes.forEach((sc: any, i: number) => {
        const col = i % cols
        const row = Math.floor(i / cols)
        const defaultX = 80 + col * spacingX
        const defaultY = 80 + row * spacingY
        const existing = options?.preservePositions ? existingNodesMap.get(sc.id) : undefined
        const x = existing?.position?.x ?? defaultX
        const y = existing?.position?.y ?? defaultY
        nodePositions.set(sc.id, { x, y })

        const chCount = Array.isArray(sc.characters_involved) ? sc.characters_involved.length : 0

        newNodes.push({
          id: sc.id, type: 'scene', position: { x, y },
          width: existing?.width,
          height: existing?.height,
          data: {
            label: sc.scene_code, scene_code: sc.scene_code,
            scene_type: sc.scene_type || 'dialogue',
            location: sc.location || '',
            narration_preview: sc.narration_preview || '',
            emotion_level: sc.emotion_level || 5,
            status: sc.status, is_wow_moment: sc.is_wow_moment || false,
            characterCount: chCount, foreshadowCount: 0,
          },
        })
      })

      data.scene_links
        .filter((l: any) => l.type === 'sequential')
        .forEach((link: any) => {
          newEdges.push({
            id: `seq-${link.source}-${link.target}`,
            source: link.source, target: link.target,
            type: 'scriptEdge', animated: true,
            data: { strength: link.strength || 3, edgeType: 'sequential' },
            markerEnd: { type: MarkerType.ArrowClosed, width: 12, height: 12, color: '#3b82f6' },
          })
        })
    } else if (mode === 'foreshadows') {
      const fsMap = new Map<string, any>()
      data.foreshadows.forEach((fs: any) => fsMap.set(fs.id, fs))

      const connectionCount = new Map<string, number>()
      data.foreshadow_links.forEach((link: any) => {
        connectionCount.set(link.source, (connectionCount.get(link.source) || 0) + 1)
        connectionCount.set(link.target, (connectionCount.get(link.target) || 0) + 1)
      })

      const sortedFs = [...data.foreshadows].sort((a: any, b: any) => {
        const ca = connectionCount.get(a.id) || 0
        const cb = connectionCount.get(b.id) || 0
        return cb - ca
      })

      const fsCols = Math.min(5, Math.ceil(Math.sqrt(sortedFs.length)))
      sortedFs.forEach((fs: any, i: number) => {
        const col = i % fsCols
        const row = Math.floor(i / fsCols)
        const defaultX = 100 + col * spacingX
        const defaultY = 80 + row * spacingY
        const existing = options?.preservePositions ? existingNodesMap.get(fs.id) : undefined
        const x = existing?.position?.x ?? defaultX
        const y = existing?.position?.y ?? defaultY
        nodePositions.set(fs.id, { x, y })

        newNodes.push({
          id: fs.id, type: 'foreshadow', position: { x, y },
          width: existing?.width,
          height: existing?.height,
          data: {
            label: fs.name || fs.fs_code, fs_code: fs.fs_code,
            fs_type: fs.fs_type || 'plot',
            surface_layer: fs.surface_layer || '',
            deep_layer: fs.deep_layer || '',
            truth_layer: fs.truth_layer || '',
            health: fs.health || 'normal',
            current_status: fs.current_status || 'active',
            reinforce_count: fs.reinforce_count || 0,
            layer_count: [fs.surface_layer, fs.deep_layer, fs.truth_layer].filter(Boolean).length,
            connectionCount: connectionCount.get(fs.id) || 0,
          },
        })
      })

      data.foreshadow_links.forEach((link: any) => {
        const linkType = link.type || 'related'
        const isPlant = linkType === 'planted_in'
        const isReveal = linkType === 'revealed_in'
        const color = isPlant ? '#6366f1' : isReveal ? '#f59e0b' : '#10b981'
        const dashArray = isPlant ? '6 4' : isReveal ? '3 3' : undefined

        newEdges.push({
          id: `fs-${link.source}-${link.target}-${linkType}`,
          source: link.source, target: link.target,
          type: 'scriptEdge',
          animated: isReveal,
          data: {
            dbId: link.id,
            strength: link.strength || 5,
            edgeType: linkType,
            relationType: 'foreshadow',
            description: link.description || '',
          },
          markerEnd: { type: MarkerType.ArrowClosed, width: 10, height: 10, color },
          style: { stroke: color, strokeDasharray: dashArray },
        })
      })
    } else if (mode === 'timeline') {
      const sortedScenes = [...data.scenes].sort((a: any, b: any) =>
        (a.scene_code || '').localeCompare(b.scene_code || '')
      )

      sortedScenes.forEach((sc: any, i: number) => {
        const defaultX = 80 + i * 220
        const defaultY = 150 + (i % 2 === 0 ? 0 : 140)
        const existing = options?.preservePositions ? existingNodesMap.get(sc.id) : undefined
        const x = existing?.position?.x ?? defaultX
        const y = existing?.position?.y ?? defaultY
        nodePositions.set(sc.id, { x, y })

        const sceneForeshadows = data.foreshadow_links.filter((l: any) =>
          l.target === sc.id && (l.type === 'planted_in' || l.type === 'revealed_in')
        )

        newNodes.push({
          id: sc.id, type: 'scene', position: { x, y },
          width: existing?.width,
          height: existing?.height,
          data: {
            label: sc.scene_code, scene_code: sc.scene_code,
            scene_type: sc.scene_type || 'dialogue',
            location: sc.location || '',
            narration_preview: sc.narration_preview || '',
            emotion_level: sc.emotion_level || 5,
            status: sc.status, is_wow_moment: sc.is_wow_moment || false,
            characterCount: (sc.characters_involved || []).length,
            foreshadowCount: sceneForeshadows.length,
          },
        })
      })

      for (let i = 0; i < sortedScenes.length - 1; i++) {
        newEdges.push({
          id: `tl-${sortedScenes[i].id}-${sortedScenes[i + 1].id}`,
          source: sortedScenes[i].id, target: sortedScenes[i + 1].id,
          type: 'scriptEdge', animated: true,
          data: { strength: 5, edgeType: 'sequential' },
          markerEnd: { type: MarkerType.ArrowClosed, width: 14, height: 14, color: '#f59e0b' },
          style: { stroke: '#f59e0b', strokeWidth: 2 },
        })
      }
    }

    setNodes(newNodes)
    setEdges(newEdges)

    if (!options?.preservePositions) {
      setTimeout(() => {
        fitView({ padding: 0.2, duration: 500 })
      }, 100)
    }
  }, [setNodes, setEdges, fitView, nodes])

  const fetchAnalysis = useCallback(async (options?: { preservePositions?: boolean }) => {
    if (!currentProject?.id) return
    setLoading(true)
    setCardData(null)
    setSelectedEdge(null)
    try {
      const data = await api.post<AnalysisData>(
        `/script-viz/analyze-project/${currentProject.id}`
      )
      setAnalysisData(data)
      buildGraph(data, viewMode, { preservePositions: options?.preservePositions !== false })
    } catch (e: any) {
      notification.error({
        message: '解析失败',
        description: e?.message || '无法获取剧本数据',
        placement: 'topRight',
      })
    } finally {
      setLoading(false)
    }
  }, [currentProject?.id, viewMode, buildGraph])

  useEffect(() => {
    fetchAnalysis({ preservePositions: false })
  }, [currentProject?.id])

  useEffect(() => {
    const unsubs = [
      eventBus.on(DataEvents.SCENE_CREATED, () => fetchAnalysis()),
      eventBus.on(DataEvents.SCENE_UPDATED, () => fetchAnalysis()),
      eventBus.on(DataEvents.SCENE_DELETED, () => fetchAnalysis()),
      eventBus.on(DataEvents.SCENE_FINALIZED, () => fetchAnalysis()),
      eventBus.on(DataEvents.CHAPTER_CREATED, () => fetchAnalysis()),
      eventBus.on(DataEvents.CHAPTER_UPDATED, () => fetchAnalysis()),
      eventBus.on(DataEvents.CHARACTER_CREATED, () => fetchAnalysis()),
      eventBus.on(DataEvents.CHARACTER_UPDATED, () => fetchAnalysis()),
      eventBus.on(DataEvents.CHARACTER_DELETED, () => fetchAnalysis()),
      eventBus.on(DataEvents.RELATION_CREATED, () => fetchAnalysis()),
      eventBus.on(DataEvents.RELATION_UPDATED, () => fetchAnalysis()),
      eventBus.on(DataEvents.FORESHADOW_CREATED, () => fetchAnalysis()),
      eventBus.on(DataEvents.FORESHADOW_UPDATED, () => fetchAnalysis()),
      eventBus.on(DataEvents.FORESHADOW_DELETED, () => fetchAnalysis()),
      eventBus.on(DataEvents.PROJECT_SWITCHED, () => fetchAnalysis()),
    ]
    return () => unsubs.forEach(u => u())
  }, [fetchAnalysis])

  useEffect(() => {
    if (analysisData) {
      buildGraph(analysisData, viewMode, { preservePositions: false })
    }
  }, [viewMode])

  // Check if edge already exists between two nodes
  const edgeExists = useCallback((source: string, target: string) => {
    return edges.some(e =>
      (e.source === source && e.target === target) ||
      (e.source === target && e.target === source)
    )
  }, [edges])

  const handleConnect = useCallback(async (connection: Connection) => {
    if (!currentProject?.id || !connection.source || !connection.target) return
    if (connection.source === connection.target) {
      notification.warning({ message: '不能连接到自己', placement: 'topRight' })
      return
    }

    // Prevent duplicate edges
    if (edgeExists(connection.source, connection.target)) {
      notification.warning({ message: '这两个节点之间已存在连线', placement: 'topRight' })
      return
    }

    const sourceNode = nodes.find(n => n.id === connection.source)
    const targetNode = nodes.find(n => n.id === connection.target)
    if (!sourceNode || !targetNode) return

    setSavingEdge(true)
    try {
      if (viewMode === 'characters' && sourceNode.type === 'character' && targetNode.type === 'character') {
        const result = await relationsApi.create(currentProject.id, {
          char_a_id: connection.source,
          char_b_id: connection.target,
          relation_type: 'related',
          trust: 5,
          favor: 5,
        })
        notification.success({
          message: '关系已创建',
          description: `${sourceNode.data?.label || ''} → ${targetNode.data?.label || ''}`,
          placement: 'topRight',
        })

        const newEdge: Edge = {
          id: `rel-${result.id}`,
          source: connection.source,
          target: connection.target,
          type: 'scriptEdge',
          animated: false,
          data: {
            dbId: result.id,
            strength: 5,
            edgeType: 'related',
            trust: 5,
            favor: 5,
            relationType: 'character',
            description: '',
          },
          markerEnd: { type: MarkerType.ArrowClosed, width: 10, height: 10 },
        }
        setEdges((eds) => addEdge(newEdge, eds))
      } else if (viewMode === 'foreshadows' && sourceNode.type === 'foreshadow' && targetNode.type === 'foreshadow') {
        const result = await foreshadowsApi.createRelation(currentProject.id, {
          from_fs_id: connection.source,
          to_fs_id: connection.target,
          relation_type: 'related',
        })
        notification.success({
          message: '伏笔关联已创建',
          description: `${sourceNode.data?.label || ''} → ${targetNode.data?.label || ''}`,
          placement: 'topRight',
        })

        const newEdge: Edge = {
          id: `fs-${connection.source}-${connection.target}-related`,
          source: connection.source,
          target: connection.target,
          type: 'scriptEdge',
          animated: false,
          data: {
            dbId: result.id,
            strength: 5,
            edgeType: 'related',
            relationType: 'foreshadow',
            description: '',
          },
          markerEnd: { type: MarkerType.ArrowClosed, width: 10, height: 10, color: '#10b981' },
          style: { stroke: '#10b981' },
        }
        setEdges((eds) => addEdge(newEdge, eds))
      } else {
        notification.info({
          message: '暂不支持此连接',
          description: '当前视图模式下不支持该类型节点之间的连接',
          placement: 'topRight',
        })
      }
    } catch (e: any) {
      notification.error({
        message: '保存连接失败',
        description: e?.message || '无法保存关系到数据库',
        placement: 'topRight',
      })
    } finally {
      setSavingEdge(false)
    }
  }, [currentProject?.id, viewMode, nodes, notification, setEdges, edgeExists])

  // Edge click handler
  const handleEdgeClick = useCallback((_event: React.MouseEvent, edge: Edge) => {
    setSelectedEdge(edge)
    setEdgeEditType((edge.data?.edgeType as string) || 'related')
    setEdgeEditTrust((edge.data?.trust as number) || 5)
    setEdgeEditFavor((edge.data?.favor as number) || 5)
    setEdgeEditStrength((edge.data?.strength as number) || 5)
    setEdgeEditDescription((edge.data?.description as string) || '')
    setEdgeEditOpen(true)
  }, [])

  // Save edge edit
  const handleSaveEdgeEdit = useCallback(async () => {
    if (!selectedEdge || !currentProject?.id) return
    const dbId = selectedEdge.data?.dbId
    if (!dbId) {
      notification.warning({ message: '无法编辑此连线', description: '该连线没有对应的数据库记录', placement: 'topRight' })
      return
    }

    try {
      if (selectedEdge.data?.relationType === 'character') {
        await relationsApi.update(currentProject.id, String(dbId), {
          relation_type: edgeEditType,
          trust: edgeEditTrust,
          favor: edgeEditFavor,
          description: edgeEditDescription,
        })
      } else if (selectedEdge.data?.relationType === 'foreshadow') {
        await foreshadowsApi.updateRelation(currentProject.id, String(dbId), {
          relation_type: edgeEditType,
          description: edgeEditDescription,
        })
      }

      // Update local edge
      setEdges((eds) => eds.map(e => {
        if (e.id === selectedEdge.id) {
          return {
            ...e,
            data: {
              ...e.data,
              edgeType: edgeEditType,
              trust: edgeEditTrust,
              favor: edgeEditFavor,
              strength: edgeEditStrength,
              description: edgeEditDescription,
            },
          }
        }
        return e
      }))

      notification.success({ message: '连线已更新', placement: 'topRight' })
      setEdgeEditOpen(false)
      setSelectedEdge(null)
    } catch (e: any) {
      notification.error({
        message: '更新失败',
        description: e?.message || '无法更新连线',
        placement: 'topRight',
      })
    }
  }, [selectedEdge, currentProject?.id, edgeEditType, edgeEditTrust, edgeEditFavor, edgeEditStrength, edgeEditDescription, setEdges, notification])

  // Delete edge - using a separate confirm modal instead of Popconfirm
  const handleDeleteEdge = useCallback(async () => {
    if (!selectedEdge || !currentProject?.id) return
    const dbId = selectedEdge.data?.dbId
    if (!dbId) {
      notification.warning({ message: '无法删除此连线', description: '该连线没有对应的数据库记录', placement: 'topRight' })
      return
    }

    setEdgeDeleting(true)
    try {
      if (selectedEdge.data?.relationType === 'character') {
        await relationsApi.delete(currentProject.id, String(dbId))
      } else if (selectedEdge.data?.relationType === 'foreshadow') {
        await foreshadowsApi.deleteRelation(currentProject.id, String(dbId))
      }

      setEdges((eds) => eds.filter(e => e.id !== selectedEdge.id))
      notification.success({ message: '连线已删除', placement: 'topRight' })
      setEdgeEditOpen(false)
      setSelectedEdge(null)
    } catch (e: any) {
      notification.error({
        message: '删除失败',
        description: e?.message || '无法删除连线',
        placement: 'topRight',
      })
    } finally {
      setEdgeDeleting(false)
    }
  }, [selectedEdge, currentProject?.id, setEdges, notification])

  const buildCardData = useCallback((node: Node): CardData => {
    const nodeType = (node.type || 'scene') as CardNodeType
    let title = ''
    let subtitle = ''
    const fields: { label: string; value: string }[] = []
    const stats: { label: string; value: number | string }[] = []
    const relatedItems: { type: CardNodeType; id: string; label: string }[] = []

    if (nodeType === 'character') {
      const d = node.data as any
      title = d.label || ''
      subtitle = d.role_type || ''
      if (d.core_goal) fields.push({ label: '核心动机', value: d.core_goal })
      if (d.core_fear) fields.push({ label: '核心恐惧', value: d.core_fear })
      if (d.arc_description) fields.push({ label: '角色弧', value: d.arc_description })
      stats.push({ label: '场景', value: d.sceneCount || 0 })
      stats.push({ label: '关联', value: d.relationCount || 0 })
      stats.push({ label: '伏笔', value: d.foreshadowCount || 0 })
    } else if (nodeType === 'scene') {
      const d = node.data as any
      title = d.scene_code || d.label || ''
      subtitle = d.scene_type || ''
      if (d.narration_preview) fields.push({ label: '内容预览', value: d.narration_preview })
      if (d.location) fields.push({ label: '地点', value: d.location })
      stats.push({ label: '情感', value: `${d.emotion_level}/10` })
      stats.push({ label: '角色', value: d.characterCount || 0 })
      if (d.is_wow_moment) stats.push({ label: '哇塞', value: '⚡' })
    } else if (nodeType === 'foreshadow') {
      const d = node.data as any
      title = d.label || d.fs_code || ''
      subtitle = d.fs_type || ''
      if (d.surface_layer) fields.push({ label: '表层', value: d.surface_layer })
      if (d.deep_layer) fields.push({ label: '深层', value: d.deep_layer })
      if (d.truth_layer) fields.push({ label: '核心层', value: d.truth_layer })
      stats.push({ label: '强化', value: d.reinforce_count || 0 })
      stats.push({ label: '层级', value: d.layer_count || 0 })
      stats.push({ label: '状态', value: d.health || 'normal' })
    } else if (nodeType === 'event') {
      const d = node.data as any
      title = d.label || ''
      subtitle = d.event_type || ''
      fields.push({ label: '类型', value: d.event_type || '' })
      stats.push({ label: '冲击力', value: `${d.emotion_impact}/10` })
    }

    return { nodeType, nodeId: node.id, title, subtitle, fields, stats, relatedItems }
  }, [])

  const handleNodeClick = useCallback((_event: React.MouseEvent, node: Node) => {
    setSelectedNode(node.id)
    const data = buildCardData(node)
    setCardData(data)
    setCardPosition({ x: window.innerWidth * 0.35, y: window.innerHeight * 0.15 })
  }, [buildCardData])

  const handlePaneClick = useCallback(() => {
    setSelectedNode(null)
    setCardData(null)
    setHighlightedNode(null)
    setSelectedEdge(null)
  }, [])

  const handleEdit = useCallback((nodeType: CardNodeType, nodeId: string) => {
    setEditTarget({ type: nodeType, id: nodeId })
    setEditDrawerOpen(true)
    setEditChanges({})
    setEditInstruction('')
    const node = nodes.find(n => n.id === nodeId)
    if (node) {
      const card = buildCardData(node)
      const initial: Record<string, string> = {}
      card.fields.forEach(f => { initial[f.label] = f.value })
      setEditChanges(initial)
    }
  }, [nodes, buildCardData])

  const handleAIEdit = useCallback((nodeType: CardNodeType, nodeId: string, instruction: string) => {
    const node = nodes.find(n => n.id === nodeId)
    const nodeLabel = node?.data?.label || nodeId
    setAllEdits(prev => [...prev, { target_type: nodeType, target_id: nodeId, changes: { label: nodeLabel }, instruction }])
    notification.success({ message: '编辑指令已记录', description: `「${nodeLabel}」的修改方向已加入待处理队列`, placement: 'topRight' })
    setCardData(null)
  }, [nodes])

  const handleRegenerate = useCallback(async () => {
    if (!currentProject?.id || allEdits.length === 0) {
      notification.warning({ message: '暂无待处理的编辑', placement: 'topRight' })
      return
    }
    setRegenerating(true)
    try {
      const result = await api.post<any>(`/script-viz/regenerate/${currentProject.id}`, { edits: allEdits, target_type: 'project' })
      setRegenerateResult(result)
      setAllEdits([])
      notification.success({ message: '剧本升级完成', description: result.changes_summary || '剧本已根据编辑方向全面优化', placement: 'topRight' })
    } catch (e: any) {
      notification.error({ message: '升级失败', description: e?.message || 'AI 服务暂不可用', placement: 'topRight' })
    }
    setRegenerating(false)
  }, [currentProject?.id, allEdits])

  const handleApplyEdit = useCallback(async () => {
    if (!editTarget) return
    const node = nodes.find(n => n.id === editTarget.id)
    const nodeLabel = node?.data?.label || editTarget.id
    setAllEdits(prev => [...prev, { target_type: editTarget.type, target_id: editTarget.id, changes: editChanges, instruction: editInstruction }])
    setEditDrawerOpen(false)
    setEditTarget(null)
    notification.success({ message: '编辑已暂存', description: `「${nodeLabel}」的修改将在点击「AI升级剧本」时统一处理`, placement: 'topRight' })
  }, [editTarget, editChanges, editInstruction, nodes])

  const handleUploadParse = useCallback(async (file: File) => {
    if (!currentProject?.id) return
    setUploading(true)
    const formData = new FormData()
    formData.append('file', file)
    try {
      const apiBase = import.meta.env.VITE_API_BASE_URL || (window.location.hostname === 'localhost' ? '/api' : 'https://yingyoujubenshengcheng.onrender.com/api')
      const res = await fetch(`${apiBase}/script-viz/upload-parse/${currentProject.id}`, { method: 'POST', body: formData })
      if (!res.ok) {
        const errorBody = await res.json().catch(() => ({ detail: '上传解析失败' }))
        throw new Error(errorBody.detail || `请求失败 (${res.status})`)
      }
      const data = await res.json()
      if (data.status === 'ok') {
        notification.success({ message: '上传解析成功', description: `已解析 ${data.filename}，共识别出 ${data.parsed?.characters?.length || 0} 个角色`, placement: 'topRight' })
        fetchAnalysis()
      }
    } catch (e: any) {
      notification.error({ message: '解析失败', description: e?.message || '无法解析上传的剧本', placement: 'topRight' })
    }
    setUploading(false)
    return false
  }, [currentProject?.id, fetchAnalysis])

  const handleCreateScene = useCallback(() => {
    const sceneNum = (analysisData?.scenes?.length || 0) + 1
    setAllEdits(prev => [...prev, { target_type: 'new_scene', target_id: `new-scene-${sceneNum}`, changes: { scene_code: `SC-${String(sceneNum).padStart(3, '0')}`, scene_type: 'dialogue' }, instruction: '创建一个新的对白场景' }])
    notification.success({ message: '新场景已加入待处理队列', placement: 'topRight' })
  }, [analysisData])

  const handleCreateForeshadow = useCallback(() => {
    const fsNum = (analysisData?.foreshadows?.length || 0) + 1
    setAllEdits(prev => [...prev, { target_type: 'new_foreshadow', target_id: `new-fs-${fsNum}`, changes: { fs_code: `FS-${String(fsNum).padStart(3, '0')}`, name: `新伏笔${fsNum}` }, instruction: '创建一个新的伏笔线索' }])
    notification.success({ message: '新伏笔已加入待处理队列', placement: 'topRight' })
  }, [analysisData])

  const highlightedNodes = useMemo(() => {
    if (!highlightedNode) return nodes
    const relatedIds = new Set<string>()
    relatedIds.add(highlightedNode)
    edges.forEach(e => {
      if (e.source === highlightedNode) relatedIds.add(e.target)
      if (e.target === highlightedNode) relatedIds.add(e.source)
    })
    return nodes.map(n => ({
      ...n,
      style: { ...(n.style || {}), opacity: relatedIds.has(n.id) ? 1 : 0.15, transition: 'opacity 0.3s ease' },
    }))
  }, [nodes, edges, highlightedNode])

  const highlightedEdges = useMemo(() => {
    if (!highlightedNode) return edges
    return edges.map(e => ({
      ...e,
      style: { ...(e.style || {}), opacity: (e.source === highlightedNode || e.target === highlightedNode) ? 1 : 0.12, transition: 'opacity 0.3s ease' },
    }))
  }, [edges, highlightedNode])

  if (!currentProject) {
    return (
      <div style={{ fontFamily: 'var(--font-family)' }} className="h-full flex items-center justify-center">
        <div className="card-surface" style={{ textAlign: 'center', padding: 48 }}>
          <h2 className="section-title" style={{ fontSize: 24, marginBottom: 24 }}>剧本可视化</h2>
          <Empty description={<span className="text-muted">请先选择或创建一个项目</span>} />
        </div>
      </div>
    )
  }

  return (
    <div ref={containerRef} style={{ fontFamily: 'var(--font-family)', display: 'flex', flexDirection: 'column', height: '100%' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 24, flexShrink: 0 }}>
        <div>
          <h2 className="section-title" style={{ fontSize: 24 }}>剧本可视化</h2>
          <p className="text-muted" style={{ margin: '4px 0 0' }}>结构与关联全景交互式视图</p>
        </div>
      </div>
      <div className="flex items-center justify-between px-3 py-2 border-b border-gray-200 dark:border-slate-700 bg-white dark:bg-slate-900 gap-2 flex-wrap">
        <div className="flex items-center gap-2">
          <NodeIndexOutlined className="text-primary-500 text-lg" />
          <span className="text-sm font-bold">剧本可视化工作台</span>
          {analysisData && (
            <Tag className="text-[10px]">
              {analysisData.characters.length}角色 · {analysisData.scenes.length}场景 · {analysisData.foreshadows.length}伏笔
            </Tag>
          )}
        </div>

        <Space size="small" wrap>
          <Segmented
            size="small"
            value={viewMode}
            onChange={(v) => setViewMode(v as ViewMode)}
            options={[
              { label: <span className="text-xs">角色</span>, value: 'characters' },
              { label: <span className="text-xs">分支</span>, value: 'branches' },
              { label: <span className="text-xs">伏笔</span>, value: 'foreshadows' },
              { label: <span className="text-xs">时间线</span>, value: 'timeline' },
              { label: <span className="text-xs">结局</span>, value: 'endings' },
            ]}
          />

          <Button size="small" icon={<ReloadOutlined />} onClick={() => fetchAnalysis()} loading={loading}>
            刷新
          </Button>

          <Upload accept=".txt,.md" showUploadList={false} beforeUpload={handleUploadParse as any}>
            <Button size="small" icon={<UploadOutlined />} loading={uploading}>导入剧本</Button>
          </Upload>

          <Button size="small" type="primary" icon={<RobotOutlined />} onClick={handleRegenerate} loading={regenerating} disabled={allEdits.length === 0}>
            AI 升级剧本 {allEdits.length > 0 && `(${allEdits.length})`}
          </Button>

          {regenerateResult && (
            <Button size="small" icon={<DiffOutlined />} onClick={() => setCompareModalOpen(true)} type="dashed">查看对比</Button>
          )}

          {allEdits.length > 0 && (
            <Button size="small" danger type="text" icon={<UndoOutlined />} onClick={() => { setAllEdits([]); notification.info({ message: '已清除所有待处理编辑', placement: 'topRight' }) }}>
              清除({allEdits.length})
            </Button>
          )}
        </Space>
      </div>

      {allEdits.length > 0 && (
        <div className="px-3 py-1.5 bg-amber-50 dark:bg-amber-900/10 border-b border-amber-200 dark:border-amber-800 flex items-center gap-2 overflow-x-auto">
          <span className="text-xs font-medium text-amber-600 shrink-0">待处理:</span>
          {allEdits.map((edit, i) => (
            <Tag key={i} color="orange" className="!text-[10px] shrink-0">
              {edit.target_type === 'character' ? '角色' : edit.target_type === 'scene' ? '场景' : edit.target_type === 'foreshadow' ? '伏笔' : edit.target_type === 'new_scene' ? '新场景' : edit.target_type === 'new_foreshadow' ? '新伏笔' : '编辑'}
              {' '}{edit.instruction?.slice(0, 15) || edit.target_id?.slice(0, 15) || '编辑'}
            </Tag>
          ))}
        </div>
      )}

      <div className="flex-1 relative">
        {loading ? (
          <div className="h-full flex items-center justify-center">
            <Spin size="large"><div className="py-12 text-gray-400">解析剧本数据...</div></Spin>
          </div>
        ) : nodes.length === 0 ? (
          <div className="h-full flex items-center justify-center">
            <Empty description={
              <div className="text-center">
                <p className="text-gray-400 mb-2">暂无数据</p>
                <Space>
                  <Button icon={<ReloadOutlined />} onClick={() => fetchAnalysis()}>加载数据</Button>
                  <Upload accept=".txt,.md" showUploadList={false} beforeUpload={handleUploadParse as any}>
                    <Button icon={<UploadOutlined />}>导入剧本</Button>
                  </Upload>
                </Space>
              </div>
            } />
          </div>
        ) : (
          <>
            <ReactFlow
              nodes={highlightedNodes}
              edges={highlightedEdges}
              onNodesChange={onNodesChange}
              onEdgesChange={onEdgesChange}
              onConnect={handleConnect}
              onNodeClick={handleNodeClick}
              onPaneClick={handlePaneClick}
              onEdgeClick={handleEdgeClick}
              nodeTypes={NODE_TYPES as any}
              edgeTypes={EDGE_TYPES as any}
              fitView
              fitViewOptions={{ padding: 0.2 }}
              minZoom={0.1}
              maxZoom={2.5}
              deleteKeyCode={null}
              multiSelectionKeyCode="Shift"
              panOnDrag={[1, 2]}
              selectionOnDrag
              connectionMode={ConnectionMode.Loose}
              className="bg-gray-50 dark:bg-slate-950"
            >
              <Background variant={BackgroundVariant.Dots} gap={20} size={1} className="text-gray-300 dark:text-gray-700" />
              <Controls className="!rounded-lg !shadow-md" position="bottom-right" />
              <MiniMap className="!rounded-lg !shadow-md" position="bottom-left" nodeStrokeWidth={3} pannable zoomable
                nodeColor={(n) => {
                  if (n.type === 'character') return '#6366f1'
                  if (n.type === 'scene') return '#f59e0b'
                  if (n.type === 'foreshadow') return '#10b981'
                  if (n.type === 'event') return '#ef4444'
                  return '#6b7280'
                }}
              />

              <Panel position="top-left" className="space-y-2">
                <div className="flex flex-col gap-1">
                  <Tooltip title="新建场景" placement="right">
                    <Button size="small" icon={<PlayCircleOutlined />} shape="circle" onClick={handleCreateScene} className="shadow-md" />
                  </Tooltip>
                  <Tooltip title="新建伏笔" placement="right">
                    <Button size="small" icon={<AimOutlined />} shape="circle" onClick={handleCreateForeshadow} className="shadow-md" />
                  </Tooltip>
                </div>
              </Panel>
            </ReactFlow>

            {cardData && (
              <NodeInfoCard
                data={cardData}
                position={cardPosition}
                onClose={() => { setCardData(null); setHighlightedNode(null) }}
                onEdit={handleEdit}
                onAIGenerate={handleAIEdit}
                onNavigateToNode={(nodeId: string) => {
                  const node = nodes.find(n => n.id === nodeId)
                  if (node) { setCardData(null); setTimeout(() => handleNodeClick({} as any, node), 50) }
                }}
                onHighlightRelated={setHighlightedNode}
                onClearHighlight={() => setHighlightedNode(null)}
              />
            )}
          </>
        )}
      </div>

      {analysisData && (
        <div className="flex items-center justify-between px-3 py-1 border-t border-gray-200 dark:border-slate-700 bg-white dark:bg-slate-900 text-[10px] opacity-60">
          <span>剧本 · {analysisData.characters.length}角色 {analysisData.scenes.length}场景 {analysisData.foreshadows.length}伏笔</span>
          <span>节点 {nodes.length} · 连线 {edges.length}</span>
        </div>
      )}

      {/* Edge Edit Modal */}
      <Modal
        title={<><EditOutlined className="mr-2" />连线详情</>}
        open={edgeEditOpen}
        onCancel={() => { setEdgeEditOpen(false); setSelectedEdge(null) }}
        footer={Boolean(selectedEdge?.data?.dbId) ? [
          <Button key="cancel" onClick={() => { setEdgeEditOpen(false); setSelectedEdge(null) }}>取消</Button>,
          <Button key="delete" danger icon={<DeleteOutlined />} loading={edgeDeleting} onClick={handleDeleteEdge}>删除连线</Button>,
          <Button key="save" type="primary" icon={<SaveOutlined />} onClick={handleSaveEdgeEdit}>保存</Button>,
        ] : [
          <Button key="close" onClick={() => { setEdgeEditOpen(false); setSelectedEdge(null) }}>关闭</Button>,
        ]}
      >
        {selectedEdge && (
          <div className="space-y-4">
            {!Boolean(selectedEdge.data?.dbId) && (
              <div className="p-2 bg-amber-50 dark:bg-amber-900/10 border border-amber-200 dark:border-amber-800 rounded text-xs text-amber-600">
                此连线为系统自动生成（{selectedEdge.data?.edgeType === 'planted_in' ? '伏笔埋设' : selectedEdge.data?.edgeType === 'revealed_in' ? '伏笔回收' : selectedEdge.data?.edgeType === 'sequential' ? '场景顺序' : selectedEdge.data?.edgeType === 'appears_in' ? '角色出场' : '自动关联'}），不支持编辑或删除
              </div>
            )}

            {Boolean(selectedEdge.data?.dbId) && (
              <>
                <div>
                  <label className="text-sm font-medium block mb-1">关系类型</label>
                  <Select
                    className="w-full"
                    value={edgeEditType}
                    onChange={setEdgeEditType}
                  >
                    {(selectedEdge.data?.relationType === 'character' ? CHARACTER_RELATION_TYPES : FORESHADOW_RELATION_TYPES).map(t => (
                      <Option key={t.value} value={t.value}>{t.label}</Option>
                    ))}
                  </Select>
                </div>

                {selectedEdge.data?.relationType === 'character' && (
                  <>
                    <div>
                      <label className="text-sm font-medium block mb-1">信任度: {edgeEditTrust}</label>
                      <Slider min={1} max={10} value={edgeEditTrust} onChange={setEdgeEditTrust} />
                    </div>
                    <div>
                      <label className="text-sm font-medium block mb-1">好感度: {edgeEditFavor}</label>
                      <Slider min={1} max={10} value={edgeEditFavor} onChange={setEdgeEditFavor} />
                    </div>
                  </>
                )}

                <div>
                  <label className="text-sm font-medium block mb-1">连线强度: {edgeEditStrength}</label>
                  <Slider min={1} max={10} value={edgeEditStrength} onChange={setEdgeEditStrength} />
                </div>

                <div>
                  <label className="text-sm font-medium block mb-1">关系描述</label>
                  <Input.TextArea
                    rows={2}
                    value={edgeEditDescription}
                    onChange={e => setEdgeEditDescription(e.target.value)}
                    placeholder="描述这条连线的具体含义..."
                  />
                </div>
              </>
            )}

            <div className="text-xs text-gray-400">
              从 <span className="inline-block bg-indigo-500 text-white text-xs px-2 py-0.5 rounded">{String(nodes.find(n => n.id === selectedEdge.source)?.data?.label || selectedEdge.source)}</span>
              {' '}连接到{' '}
              <span className="inline-block bg-emerald-500 text-white text-xs px-2 py-0.5 rounded">{String(nodes.find(n => n.id === selectedEdge.target)?.data?.label || selectedEdge.target)}</span>
            </div>
          </div>
        )}
      </Modal>

      {/* Edit Drawer */}
      <Drawer
        title={editTarget ? `编辑${editTarget.type === 'character' ? '角色' : editTarget.type === 'scene' ? '场景' : '伏笔'}` : '编辑'}
        open={editDrawerOpen}
        onClose={() => setEditDrawerOpen(false)}
        width={400}
      >
        <div className="space-y-4">
          <div>
            <div className="text-sm font-medium mb-2">修改内容</div>
            {Object.entries(editChanges).map(([key, value]) => (
              <div key={key} className="mb-3">
                <label className="text-xs text-gray-400 block mb-1">{key}</label>
                <Input.TextArea size="small" rows={2} value={value} onChange={e => setEditChanges(prev => ({ ...prev, [key]: e.target.value }))} />
              </div>
            ))}
          </div>
          <div>
            <div className="text-sm font-medium mb-2">修改指令（告诉AI你想要什么方向）</div>
            <Input.TextArea rows={3} value={editInstruction} onChange={e => setEditInstruction(e.target.value)} placeholder="例如：让这个角色更加阴暗、增加与女主角的情感冲突..." />
          </div>
          <Button type="primary" block icon={<SaveOutlined />} onClick={handleApplyEdit}>暂存修改（稍后统一AI升级）</Button>
        </div>
      </Drawer>

      {/* Compare Modal */}
      <Modal
        title={<><DiffOutlined className="mr-2" />新旧版本对比</>}
        open={compareModalOpen}
        onCancel={() => setCompareModalOpen(false)}
        width={800}
        footer={
          <Space>
            <Button onClick={() => setCompareModalOpen(false)}>关闭</Button>
            <Button type="primary" onClick={() => { fetchAnalysis(); setCompareModalOpen(false); }}>应用新版本</Button>
          </Space>
        }
      >
        {regenerateResult && (
          <div className="space-y-4">
            <Card size="small" className="bg-green-50 dark:bg-green-900/10 border-green-200 dark:border-green-800">
              <div className="flex items-center gap-2">
                <ThunderboltOutlined className="text-green-500" />
                <span className="text-sm font-medium text-green-700 dark:text-green-400">{regenerateResult.changes_summary}</span>
              </div>
            </Card>
          </div>
        )}
      </Modal>
    </div>
  )
}

export default function ScriptViz() {
  return (
    <div className="h-full">
      <ReactFlowProvider>
        <ScriptVizInner />
      </ReactFlowProvider>
    </div>
  )
}
