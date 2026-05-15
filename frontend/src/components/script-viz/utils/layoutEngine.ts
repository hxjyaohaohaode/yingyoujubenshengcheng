import dagre from '@dagrejs/dagre'
import { Node, Edge } from '@xyflow/react'
import { AnalysisData } from '../plugins/types'

export type LayoutDirection = 'TB' | 'LR'

export function getDagreLayout(
  nodes: Node[],
  edges: Edge[],
  direction: LayoutDirection = 'LR',
  options?: {
    nodeWidth?: number
    nodeHeight?: number
    rankSep?: number
    nodeSep?: number
  }
): { nodes: Node[]; edges: Edge[] } {
  const {
    nodeWidth = 220,
    nodeHeight = 160,
    rankSep = 80,
    nodeSep = 40,
  } = options || {}

  const dagreGraph = new dagre.graphlib.Graph()
  dagreGraph.setDefaultEdgeLabel(() => ({}))
  dagreGraph.setGraph({
    rankdir: direction,
    ranksep: rankSep,
    nodesep: nodeSep,
    marginx: 40,
    marginy: 40,
  })

  nodes.forEach(node => {
    const w = (node.data as any)?._width || nodeWidth
    const h = (node.data as any)?._height || nodeHeight
    dagreGraph.setNode(node.id, { width: w, height: h })
  })

  edges.forEach(edge => {
    dagreGraph.setEdge(edge.source, edge.target)
  })

  dagre.layout(dagreGraph)

  const layoutedNodes = nodes.map(node => {
    const nodeWithPosition = dagreGraph.node(node.id)
    const w = (node.data as any)?._width || nodeWidth
    const h = (node.data as any)?._height || nodeHeight
    return {
      ...node,
      position: {
        x: nodeWithPosition.x - w / 2,
        y: nodeWithPosition.y - h / 2,
      },
    }
  })

  return { nodes: layoutedNodes, edges }
}

export function detectBranches(data: AnalysisData): Array<{
  branchPoint: string
  children: string[]
  labels: string[]
}> {
  const branches: Array<{ branchPoint: string; children: string[]; labels: string[] }> = []

  const outgoing = new Map<string, Set<string>>()
  data.scene_links
    .filter(l => l.type === 'sequential')
    .forEach(l => {
      if (!outgoing.has(l.source)) outgoing.set(l.source, new Set())
      outgoing.get(l.source)!.add(l.target)
    })

  outgoing.forEach((targets, source) => {
    if (targets.size > 1) {
      const sourceScene = data.scenes.find(s => s.id === source)
      const children = Array.from(targets).map(tid => {
        const scene = data.scenes.find(s => s.id === tid)
        return scene?.scene_code || tid
      })
      branches.push({
        branchPoint: sourceScene?.scene_code || source,
        children,
        labels: children.map(c => `分支: ${c}`),
      })
    }
  })

  return branches
}