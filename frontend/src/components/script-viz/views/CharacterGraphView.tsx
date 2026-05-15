import { useMemo, useCallback, useState } from 'react'
import {
  ReactFlow, ReactFlowProvider, Background, Controls, MiniMap, useNodesState, useEdgesState,
  useReactFlow, BackgroundVariant, MarkerType, Node, Edge,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import { Button, Tooltip } from 'antd'
import { ApartmentOutlined } from '@ant-design/icons'
import { ViewPluginProps, CharacterData, RelationData } from '../plugins/types'
import { getDagreLayout } from '../utils/layoutEngine'
import CharacterNode from '../CharacterNode'
import ScriptEdge from '../ScriptEdge'

const NODE_TYPES = { character: CharacterNode }
const EDGE_TYPES = { scriptEdge: ScriptEdge }

const RELATION_COLORS: Record<string, string> = {
  friend: '#10b981', enemy: '#ef4444', lover: '#ec4899',
  family: '#f59e0b', mentor: '#8b5cf6', rival: '#f97316',
  ally: '#06b6d4', related: '#6b7280',
}

function CharacterGraphViewInner({ data, containerWidth, containerHeight, onNodeClick, onEdgeClick, onPaneClick }: ViewPluginProps) {
  const reactFlowInstance = useReactFlow()
  const [layoutVersion, setLayoutVersion] = useState(0)

  const { nodes: initialNodes, edges: initialEdges } = useMemo(() => {
    const nodes: Node[] = []
    const edges: Edge[] = []
    const charSceneCount = new Map<string, number>()
    const charRelationCount = new Map<string, number>()
    data.scene_links.filter(l => l.type === 'appears_in').forEach(l => {
      charSceneCount.set(l.source, (charSceneCount.get(l.source) || 0) + 1)
    })
    data.relations.forEach(r => {
      charRelationCount.set(r.char_a_id, (charRelationCount.get(r.char_a_id) || 0) + 1)
      charRelationCount.set(r.char_b_id, (charRelationCount.get(r.char_b_id) || 0) + 1)
    })
    data.characters.forEach((ch: CharacterData) => {
      nodes.push({
        id: ch.id, type: 'character', position: { x: 0, y: 0 },
        data: {
          label: ch.name, role_type: ch.role_type || 'supporting',
          core_goal: ch.core_goal || '', core_fear: ch.core_fear || '',
          surface_image: ch.surface_image as any,
          arc_description: ch.arc_description || '',
          status: ch.status,
          sceneCount: charSceneCount.get(ch.id) || 0,
          relationCount: charRelationCount.get(ch.id) || 0,
          foreshadowCount: 0,
        },
      })
    })
    data.relations.forEach((rel: RelationData) => {
      const color = RELATION_COLORS[rel.relation_type] || '#6b7280'
      edges.push({
        id: `rel-${rel.id}`, source: rel.char_a_id, target: rel.char_b_id,
        type: 'scriptEdge', label: rel.relation_type,
        data: {
          dbId: rel.id, strength: Math.max(1, Math.min(10, rel.trust / 10)),
          edgeType: rel.relation_type || 'related', trust: rel.trust, favor: rel.favor,
          relationType: 'character', description: rel.description || '',
        },
        markerEnd: { type: MarkerType.ArrowClosed, width: 10, height: 10, color },
        style: { stroke: `${color}90` },
      })
    })
    const { nodes: layouted, edges: layoutedEdges } = getDagreLayout(nodes, edges, 'LR', { nodeWidth: 220, nodeHeight: 160 })
    return { nodes: layouted, edges: layoutedEdges }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [data, layoutVersion])

  const [rfNodes, setRfNodes, onNodesChange] = useNodesState(initialNodes)
  const [rfEdges, setRfEdges, onEdgesChange] = useEdgesState(initialEdges)

  return (
    <div className="w-full h-full relative">
      <ReactFlow nodes={rfNodes} edges={rfEdges} onNodesChange={onNodesChange} onEdgesChange={onEdgesChange}
        onNodeClick={onNodeClick} onEdgeClick={onEdgeClick} onPaneClick={onPaneClick}
        nodeTypes={NODE_TYPES} edgeTypes={EDGE_TYPES} fitView fitViewOptions={{ padding: 0.15 }}
        minZoom={0.05} maxZoom={4} deleteKeyCode={null} panOnDrag zoomOnScroll zoomOnPinch
        zoomOnDoubleClick={false} selectionOnDrag={false} proOptions={{ hideAttribution: true }}
        className="bg-white dark:bg-slate-900">
        <Background variant={BackgroundVariant.Dots} gap={16} size={1} />
        <Controls className="!rounded-lg !shadow-md" position="bottom-right" showInteractive={false} />
      </ReactFlow>
      <div className="absolute top-2 left-2 z-10">
        <Tooltip title="优化布局"><Button size="small" icon={<ApartmentOutlined />} onClick={() => { setLayoutVersion(v => v + 1); setTimeout(() => reactFlowInstance.fitView({ padding: 0.15, duration: 600 }), 100) }}>优化布局</Button></Tooltip>
      </div>
    </div>
  )
}

export default function CharacterGraphView(props: ViewPluginProps) {
  return <ReactFlowProvider><CharacterGraphViewInner {...props} /></ReactFlowProvider>
}