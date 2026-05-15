import { useMemo, useCallback, useState } from 'react'
import {
  ReactFlow, ReactFlowProvider, Background, Controls, MiniMap, useNodesState, useEdgesState,
  useReactFlow, BackgroundVariant, MarkerType, Node, Edge,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import { Button, Tooltip } from 'antd'
import { ApartmentOutlined } from '@ant-design/icons'
import { ViewPluginProps, CharacterData, RelationData, SceneData, SceneLinkData, ForeshadowData, ForeshadowLinkData } from '../plugins/types'
import { getDagreLayout } from '../utils/layoutEngine'
import CharacterNode from '../CharacterNode'
import SceneNode from '../SceneNode'
import ChoiceNode from '../ChoiceNode'
import EventNode from '../EventNode'
import ForeshadowNode from '../ForeshadowNode'
import ScriptEdge from '../ScriptEdge'
import ChoiceEdge from '../ChoiceEdge'

const NODE_TYPES = { character: CharacterNode, scene: SceneNode, choice: ChoiceNode, event: EventNode, foreshadow: ForeshadowNode }
const EDGE_TYPES = { scriptEdge: ScriptEdge, choiceEdge: ChoiceEdge }

const RELATION_COLORS: Record<string, string> = {
  friend: '#10b981', enemy: '#ef4444', lover: '#ec4899',
  family: '#f59e0b', mentor: '#8b5cf6', rival: '#f97316',
  ally: '#06b6d4', related: '#6b7280',
}

function TreeBranchViewInner({ data, containerWidth, containerHeight, onNodeClick, onEdgeClick, onPaneClick }: ViewPluginProps) {
  const reactFlowInstance = useReactFlow()
  const [layoutVersion, setLayoutVersion] = useState(0)

  const { nodes: initialNodes, edges: initialEdges } = useMemo(() => {
    const nodes: Node[] = []
    const edges: Edge[] = []
    const nodeIdSet = new Set<string>()
    data.characters.forEach(ch => { nodeIdSet.add(ch.id); nodes.push({ id: ch.id, type: 'character', position: { x: 0, y: 0 }, data: { label: ch.name, role_type: ch.role_type || 'supporting', core_goal: ch.core_goal || '', core_fear: ch.core_fear || '', surface_image: ch.surface_image as any, arc_description: ch.arc_description || '', status: ch.status, sceneCount: 0, relationCount: 0, foreshadowCount: 0 } }) })
    data.scenes.forEach(sc => { nodeIdSet.add(sc.id); nodes.push({ id: sc.id, type: 'scene', position: { x: 0, y: 0 }, data: { label: sc.scene_code, scene_code: sc.scene_code, scene_type: sc.scene_type || 'dialogue', location: sc.location || '', narration_preview: sc.narration_preview || '', emotion_level: sc.emotion_level || 5, status: sc.status, is_wow_moment: sc.is_wow_moment || false, characterCount: (sc.characters_involved || []).length, foreshadowCount: 0 } }) })
    data.foreshadows.forEach(fs => { nodeIdSet.add(fs.id); nodes.push({ id: fs.id, type: 'foreshadow', position: { x: 0, y: 0 }, data: { label: fs.name || fs.fs_code, fs_code: fs.fs_code, fs_type: fs.fs_type || 'plot', surface_layer: fs.surface_layer || '', deep_layer: fs.deep_layer || '', truth_layer: fs.truth_layer || '', health: fs.health || 'normal', current_status: fs.current_status || 'active', reinforce_count: fs.reinforce_count || 0, layer_count: [fs.surface_layer, fs.deep_layer, fs.truth_layer].filter(Boolean).length, connectionCount: 0 } }) })
    data.relations.forEach(rel => { if (!nodeIdSet.has(rel.char_a_id) || !nodeIdSet.has(rel.char_b_id)) return; const color = RELATION_COLORS[rel.relation_type] || '#6b7280'; edges.push({ id: `rel-${rel.id}`, source: rel.char_a_id, target: rel.char_b_id, type: 'scriptEdge', label: rel.relation_type, data: { dbId: rel.id, strength: Math.max(1, Math.min(10, rel.trust / 10)), edgeType: rel.relation_type || 'related', trust: rel.trust, favor: rel.favor, relationType: 'character', description: rel.description || '' }, markerEnd: { type: MarkerType.ArrowClosed, width: 10, height: 10, color }, style: { stroke: `${color}90` } }) })
    data.scene_links.filter(l => l.type === 'sequential').forEach(link => { if (!nodeIdSet.has(link.source) || !nodeIdSet.has(link.target)) return; edges.push({ id: `seq-${link.source}-${link.target}`, source: link.source, target: link.target, type: 'scriptEdge', label: '→', data: { strength: link.strength || 3, edgeType: 'sequential' }, markerEnd: { type: MarkerType.ArrowClosed, width: 12, height: 12, color: '#3b82f6' }, style: { stroke: '#3b82f680', strokeWidth: 2 } }) })
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

export default function TreeBranchView(props: ViewPluginProps) {
  return <ReactFlowProvider><TreeBranchViewInner {...props} /></ReactFlowProvider>
}