import dagre from '@dagrejs/dagre'
import type { Node, Edge } from '@xyflow/react'

export const EDGE_COLORS: Record<string, string> = {
  contains: '#91d5ff', sequence: '#1677ff', leads_to: '#722ed1',
  crosses: '#fa8c16', reverses: '#ff4d4f', foreshadows: '#13c2c2',
  parallels: '#eb2f96', escalates: '#faad14', delays: '#8c8c8c',
  triggers: '#52c41a', resolves: '#2f54eb', conflicts: '#f5222d',
  transforms: '#722ed1', reveals: '#1890ff', separates: '#fa541c',
  merges: '#13c2c2', echoes: '#b37feb', contrasts: '#ff85c0',
  depends: '#ffc53d', excludes: '#ff4d4f', substitutes: '#36cfc9',
}

export const EDGE_LABELS: Record<string, string> = {
  contains: '包含', sequence: '顺序', leads_to: '导致',
  crosses: '交汇', reverses: '逆转', foreshadows: '伏笔',
  parallels: '并行', escalates: '升级', delays: '延缓',
  triggers: '触发', resolves: '解决', conflicts: '冲突',
  transforms: '转化', reveals: '揭示', separates: '分离',
  merges: '合并', echoes: '呼应', contrasts: '对比',
  depends: '依赖', excludes: '排斥', substitutes: '替代',
}

export const EDGE_STYLE_MAP: Record<string, { stroke: string; strokeDasharray?: string; strokeWidth: number }> = {
  contains: { stroke: '#91d5ff', strokeWidth: 1.5, strokeDasharray: '4 4' },
  sequence: { stroke: '#1677ff', strokeWidth: 2.5 },
  leads_to: { stroke: '#722ed1', strokeWidth: 2, strokeDasharray: '8 4' },
  crosses: { stroke: '#fa8c16', strokeWidth: 2, strokeDasharray: '2 6' },
  reverses: { stroke: '#ff4d4f', strokeWidth: 2.5 },
  foreshadows: { stroke: '#13c2c2', strokeWidth: 1.5, strokeDasharray: '3 5' },
  parallels: { stroke: '#eb2f96', strokeWidth: 2, strokeDasharray: '6 3' },
  escalates: { stroke: '#faad14', strokeWidth: 2.5 },
  delays: { stroke: '#8c8c8c', strokeWidth: 1.5, strokeDasharray: '2 2' },
  triggers: { stroke: '#52c41a', strokeWidth: 2 },
  resolves: { stroke: '#2f54eb', strokeWidth: 2, strokeDasharray: '5 3' },
  conflicts: { stroke: '#f5222d', strokeWidth: 2.5 },
  transforms: { stroke: '#722ed1', strokeWidth: 2, strokeDasharray: '10 3 2 3' },
  reveals: { stroke: '#1890ff', strokeWidth: 2, strokeDasharray: '4 2' },
  separates: { stroke: '#fa541c', strokeWidth: 2, strokeDasharray: '6 4' },
  merges: { stroke: '#13c2c2', strokeWidth: 2.5 },
  echoes: { stroke: '#b37feb', strokeWidth: 1.5, strokeDasharray: '3 3' },
  contrasts: { stroke: '#ff85c0', strokeWidth: 2 },
  depends: { stroke: '#ffc53d', strokeWidth: 1.5, strokeDasharray: '4 2 1 2' },
  excludes: { stroke: '#ff4d4f', strokeWidth: 2, strokeDasharray: '8 4 2 4' },
  substitutes: { stroke: '#36cfc9', strokeWidth: 2, strokeDasharray: '5 5' },
}

export const EDGE_TYPE_OPTIONS = [
  { value: 'contains', label: '包含', group: '结构' },
  { value: 'sequence', label: '顺序', group: '结构' },
  { value: 'parallels', label: '并行', group: '结构' },
  { value: 'leads_to', label: '导致', group: '因果' },
  { value: 'triggers', label: '触发', group: '因果' },
  { value: 'reverses', label: '逆转', group: '因果' },
  { value: 'escalates', label: '升级', group: '因果' },
  { value: 'delays', label: '延缓', group: '因果' },
  { value: 'resolves', label: '解决', group: '因果' },
  { value: 'conflicts', label: '冲突', group: '因果' },
  { value: 'transforms', label: '转化', group: '因果' },
  { value: 'crosses', label: '交汇', group: '关联' },
  { value: 'merges', label: '合并', group: '关联' },
  { value: 'separates', label: '分离', group: '关联' },
  { value: 'foreshadows', label: '伏笔', group: '叙事' },
  { value: 'reveals', label: '揭示', group: '叙事' },
  { value: 'echoes', label: '呼应', group: '叙事' },
  { value: 'contrasts', label: '对比', group: '叙事' },
  { value: 'depends', label: '依赖', group: '逻辑' },
  { value: 'excludes', label: '排斥', group: '逻辑' },
  { value: 'substitutes', label: '替代', group: '逻辑' },
]

export const HANDLE_LABELS: Record<string, string> = {
  'top-in': '↑ 上级接入',
  'top-seq': '↑ 前章接入',
  'top-from-event': '↑ 事件触发',
  'left-cross': '← 交汇',
  'left-contain': '← 被包含',
  'left-from-chapter': '← 所属章节',
  'bottom-out': '↓ 下级输出',
  'bottom-seq': '↓ 后章输出',
  'right-cross': '交汇 →',
  'right-contain': '包含 →',
  'right-to-choice': '触发抉择 →',
  'right-branch': '分支 →',
}

export interface EditState {
  title: string
  summary: string
  arc_type: string
  emotion_target: number
  word_target: number
  core_conflict: string
  key_turning_points: string
  foreshadow_tasks: string
  event_type: string
  options: string
  core_theme: string
  key_characters: string
  resolution_type: string
  pov_character: string
  setting: string
  time_marker: string
  mood: string
  trigger_condition: string
  consequences: string
  affected_characters: string
  urgency_level: string
  decision_context: string
  stakes: string
  moral_weight: string
}

export const DEFAULT_EDIT: EditState = {
  title: '', summary: '', arc_type: 'main', emotion_target: 5, word_target: 0,
  core_conflict: '', key_turning_points: '', foreshadow_tasks: '', event_type: '', options: '',
  core_theme: '', key_characters: '', resolution_type: '',
  pov_character: '', setting: '', time_marker: '', mood: '',
  trigger_condition: '', consequences: '', affected_characters: '', urgency_level: '',
  decision_context: '', stakes: '', moral_weight: '',
}

interface ConnRule {
  sourceType: string
  sourceHandle: string
  targetType: string
  targetHandle: string
  edgeType: string
}

const CONNECTION_RULES: ConnRule[] = [
  { sourceType: 'story_arc', sourceHandle: 'bottom-out', targetType: 'chapter', targetHandle: 'top-seq', edgeType: 'contains' },
  { sourceType: 'story_arc', sourceHandle: 'bottom-out', targetType: 'event', targetHandle: 'top-in', edgeType: 'contains' },
  { sourceType: 'story_arc', sourceHandle: 'right-cross', targetType: 'story_arc', targetHandle: 'left-cross', edgeType: 'crosses' },
  { sourceType: 'story_arc', sourceHandle: 'right-cross', targetType: 'chapter', targetHandle: 'left-contain', edgeType: 'contains' },
  { sourceType: 'chapter', sourceHandle: 'bottom-seq', targetType: 'chapter', targetHandle: 'top-seq', edgeType: 'sequence' },
  { sourceType: 'chapter', sourceHandle: 'right-contain', targetType: 'event', targetHandle: 'left-from-chapter', edgeType: 'contains' },
  { sourceType: 'chapter', sourceHandle: 'right-contain', targetType: 'choice', targetHandle: 'left-from-chapter', edgeType: 'contains' },
  { sourceType: 'chapter', sourceHandle: 'bottom-seq', targetType: 'event', targetHandle: 'top-in', edgeType: 'sequence' },
  { sourceType: 'event', sourceHandle: 'bottom-out', targetType: 'event', targetHandle: 'top-in', edgeType: 'sequence' },
  { sourceType: 'event', sourceHandle: 'right-to-choice', targetType: 'choice', targetHandle: 'top-from-event', edgeType: 'leads_to' },
  { sourceType: 'event', sourceHandle: 'bottom-out', targetType: 'choice', targetHandle: 'top-from-event', edgeType: 'leads_to' },
  { sourceType: 'choice', sourceHandle: 'bottom-out', targetType: 'chapter', targetHandle: 'top-seq', edgeType: 'leads_to' },
  { sourceType: 'choice', sourceHandle: 'bottom-out', targetType: 'event', targetHandle: 'top-in', edgeType: 'leads_to' },
  { sourceType: 'choice', sourceHandle: 'right-branch', targetType: 'event', targetHandle: 'left-from-chapter', edgeType: 'leads_to' },
  { sourceType: 'choice', sourceHandle: 'right-branch', targetType: 'chapter', targetHandle: 'left-contain', edgeType: 'leads_to' },
]

export function inferEdgeType(
  sourceType: string, targetType: string,
  sourceHandle: string | null, targetHandle: string | null,
): string {
  if (!sourceHandle || !targetHandle) {
    return _fallbackEdgeType(sourceType, targetType)
  }
  const rule = CONNECTION_RULES.find(
    (r) => r.sourceType === sourceType && r.sourceHandle === sourceHandle
      && r.targetType === targetType && r.targetHandle === targetHandle,
  )
  if (rule) return rule.edgeType

  if (sourceHandle.includes('cross') || targetHandle.includes('cross')) return 'crosses'
  if (sourceHandle.includes('contain') || targetHandle.includes('contain') || targetHandle.includes('from-chapter')) {
    if (sourceType === 'story_arc' && (targetType === 'chapter' || targetType === 'event')) return 'contains'
    if (sourceType === 'chapter' && (targetType === 'event' || targetType === 'choice')) return 'contains'
  }
  if (sourceHandle.includes('to-choice') || targetHandle.includes('from-event')) return 'leads_to'
  return _fallbackEdgeType(sourceType, targetType)
}

function _fallbackEdgeType(sourceType: string, targetType: string): string {
  if (sourceType === 'chapter' && targetType === 'chapter') return 'sequence'
  if (sourceType === 'story_arc' && targetType === 'chapter') return 'contains'
  if (sourceType === 'event' && targetType === 'choice') return 'leads_to'
  if (sourceType === 'choice' && (targetType === 'chapter' || targetType === 'event')) return 'leads_to'
  if (sourceType === 'event' && targetType === 'event') return 'sequence'
  return 'sequence'
}

export function isValidConnection(
  sourceType: string, targetType: string,
  sourceHandle: string | null, targetHandle: string | null,
): { valid: boolean; reason?: string } {
  if (!sourceHandle || !targetHandle) return { valid: true }

  const INVALID_TARGETS: Record<string, string[]> = {
    choice: ['story_arc'],
    event: ['story_arc'],
    chapter: ['story_arc'],
  }
  const blocked = INVALID_TARGETS[sourceType]
  if (blocked && blocked.includes(targetType)) {
    return { valid: false, reason: `此处暂时不能连接，${_nodeLabel(sourceType)}不能直接连接到${_nodeLabel(targetType)}。请换其他的方式` }
  }

  const srcIsOutput = sourceHandle.includes('bottom') || sourceHandle.includes('right')
  const tgtIsInput = targetHandle.includes('top') || targetHandle.includes('left')
  if (!srcIsOutput) return { valid: false, reason: '此处暂时不能连接，请从源节点的输出Handle（下方/右侧）拖出连线' }
  if (!tgtIsInput) return { valid: false, reason: '此处暂时不能连接，请连接到目标节点的输入Handle（上方/左侧）' }

  const VALID_CONNECTIONS: Record<string, Record<string, string[]>> = {
    'story_arc': {
      'chapter': ['bottom-out→top-seq', 'right-cross→left-contain'],
      'event': ['bottom-out→top-in'],
      'story_arc': ['right-cross→left-cross'],
    },
    'chapter': {
      'chapter': ['bottom-seq→top-seq'],
      'event': ['right-contain→left-from-chapter', 'bottom-seq→top-in'],
      'choice': ['right-contain→left-from-chapter'],
    },
    'event': {
      'event': ['bottom-out→top-in'],
      'choice': ['right-to-choice→top-from-event', 'bottom-out→top-from-event'],
    },
    'choice': {
      'chapter': ['bottom-out→top-seq', 'right-branch→left-contain'],
      'event': ['bottom-out→top-in', 'right-branch→left-from-chapter'],
    },
  }

  const validTargets = VALID_CONNECTIONS[sourceType]
  if (validTargets && !validTargets[targetType]) {
    return { valid: false, reason: `此处暂时不能连接，${_nodeLabel(sourceType)}的此Handle不能连接到${_nodeLabel(targetType)}。请换其他的方式` }
  }

  return { valid: true }
}

function _nodeLabel(t: string): string {
  const m: Record<string, string> = { story_arc: '故事线', chapter: '章节', event: '事件', choice: '抉择' }
  return m[t] || t
}

export type LayoutDirection = 'TB' | 'LR' | 'RL' | 'BT'

export function getDagreLayout(
  nodes: Node[], edges: Edge[],
  direction: LayoutDirection = 'TB',
): { nodes: Node[]; edges: Edge[] } {
  const g = new dagre.graphlib.Graph()
  g.setDefaultEdgeLabel(() => ({}))
  const ranksep = direction === 'TB' || direction === 'BT' ? 80 : 120
  const nodesep = direction === 'TB' || direction === 'BT' ? 50 : 60
  g.setGraph({ rankdir: direction, ranksep, nodesep })
  nodes.forEach((node) => {
    const w = node.type === 'story_arc' ? 240 : 190
    const h = node.type === 'story_arc' ? 110 : 80
    g.setNode(node.id, { width: w, height: h })
  })
  edges.forEach((edge) => {
    g.setEdge(edge.source, edge.target, { label: (edge.label as string) || '' })
  })
  dagre.layout(g)
  const layoutedNodes = nodes.map((node) => {
    const dagreNode = g.node(node.id)
    if (!dagreNode) return node
    return { ...node, position: { x: dagreNode.x - dagreNode.width / 2, y: dagreNode.y - dagreNode.height / 2 } }
  })
  return { nodes: layoutedNodes, edges }
}

export function hierarchicalLayout(nodes: Node[], edges: Edge[]): { nodes: Node[]; edges: Edge[]; direction: LayoutDirection } {
  const arcs = nodes.filter((n) => n.type === 'story_arc')
  const nonArcNodes = nodes.filter((n) => n.type !== 'story_arc')
  const nonArcEdges = edges.filter((e) => {
    const src = nodes.find((n) => n.id === e.source)
    const tgt = nodes.find((n) => n.id === e.target)
    return src?.type !== 'story_arc' && tgt?.type !== 'story_arc'
  })

  const ARC_COL_WIDTH = 320
  const ARC_ROW_HEIGHT = 140
  const CHAPTER_GAP = 60
  const EVENT_GAP = 40

  const arcGroups: Map<string, { chapters: Node[]; chapterEdges: Edge[]; orphanNodes: Node[] }> = new Map()
  arcs.forEach((arc) => arcGroups.set(arc.id, { chapters: [], chapterEdges: [], orphanNodes: [] }))

  const arcContainEdges = edges.filter((e) => {
    const src = nodes.find((n) => n.id === e.source)
    return src?.type === 'story_arc'
  })

  const chapterToArc: Map<string, string> = new Map()
  arcContainEdges.forEach((e) => { chapterToArc.set(e.target, e.source) })

  nonArcNodes.forEach((node) => {
    const visited = new Set<string>()
    const findArc = (n: Node): string | null => {
      if (visited.has(n.id)) return null
      visited.add(n.id)
      const parentEdge = arcContainEdges.find((e) => e.target === n.id)
      if (parentEdge) return parentEdge.source
      const incomingEdges = edges.filter((e) => e.target === n.id)
      for (const ie of incomingEdges) {
        const src = nodes.find((nn) => nn.id === ie.source)
        if (src) {
          if (src.type === 'story_arc') return src.id
          const arc = findArc(src)
          if (arc) return arc
        }
      }
      return null
    }
    const arcId = findArc(node)
    if (arcId && arcGroups.has(arcId)) {
      const group = arcGroups.get(arcId)!
      if (node.type === 'chapter') group.chapters.push(node)
      else group.orphanNodes.push(node)
    } else {
      const firstArc = arcs[0]
      if (firstArc) {
        const group = arcGroups.get(firstArc.id)!
        group.orphanNodes.push(node)
      }
    }
  })

  const layoutedNodes: Node[] = []
  const mainArc = arcs.find((a) => (a.data as any).arc_type === 'main') || arcs[0]

  arcs.forEach((arc, arcIdx) => {
    const isMain = arc.id === mainArc?.id
    const colX = isMain ? 0 : arcIdx * ARC_COL_WIDTH
    const arcY = 0
    layoutedNodes.push({ ...arc, position: { x: colX, y: arcY } })

    const group = arcGroups.get(arc.id)!
    if (group.chapters.length === 0 && group.orphanNodes.length === 0) return

    const g = new dagre.graphlib.Graph()
    g.setDefaultEdgeLabel(() => ({}))
    g.setGraph({ rankdir: 'TB', ranksep: CHAPTER_GAP, nodesep: EVENT_GAP, marginx: 20, marginy: 20 })

    const groupNodes = [...group.chapters, ...group.orphanNodes]
    groupNodes.forEach((node) => {
      const w = node.type === 'chapter' ? 200 : 170
      const h = node.type === 'chapter' ? 80 : 60
      g.setNode(node.id, { width: w, height: h })
    })

    const groupNodeIds = new Set(groupNodes.map((n) => n.id))
    const groupEdges = nonArcEdges.filter((e) => groupNodeIds.has(e.source) && groupNodeIds.has(e.target))
    groupEdges.forEach((e) => g.setEdge(e.source, e.target))

    dagre.layout(g)

    groupNodes.forEach((node) => {
      const dagreNode = g.node(node.id)
      if (dagreNode) {
        layoutedNodes.push({
          ...node,
          position: {
            x: colX + dagreNode.x - dagreNode.width / 2,
            y: arcY + ARC_ROW_HEIGHT + dagreNode.y,
          },
        })
      } else {
        layoutedNodes.push(node)
      }
    })
  })

  const crossEdges = edges.filter((e) => (e.data as any)?.edge_type === 'crosses')
  const hasManyCrosses = crossEdges.length >= 2
  const direction: LayoutDirection = arcs.length >= 3 && hasManyCrosses ? 'LR' : 'TB'

  return { nodes: layoutedNodes, edges, direction }
}

export function optimizeLayout(nodes: Node[], edges: Edge[]): { nodes: Node[]; edges: Edge[]; direction: LayoutDirection } {
  const arcs = nodes.filter((n) => n.type === 'story_arc')
  if (arcs.length > 0) {
    return hierarchicalLayout(nodes, edges)
  }
  const arcCount = arcs.length
  const chapterCount = nodes.filter((n) => n.type === 'chapter').length
  const crossEdges = edges.filter((e) => (e.data as any)?.edge_type === 'crosses')
  let direction: LayoutDirection = 'TB'
  if (arcCount >= 3 && crossEdges.length >= 2) direction = 'LR'
  else if (chapterCount > 8) direction = 'LR'
  return { ...getDagreLayout(nodes, edges, direction), direction }
}

export const NODE_DEFAULTS: Record<string, Record<string, any>> = {
  story_arc: { label: '新故事线', arc_type: 'sub', word_target: 100000 },
  chapter: { label: '新章节', arc_type: 'main', word_target: 30000 },
  event: { label: '新事件', event_type: 'turning_point' },
  choice: { label: '新抉择', options: ['选项A', '选项B'] },
}
