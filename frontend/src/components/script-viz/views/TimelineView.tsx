import { useMemo, useCallback, useState } from 'react'
import {
  ReactFlow, ReactFlowProvider, Background, Controls, MiniMap, useNodesState, useEdgesState,
  useReactFlow, BackgroundVariant, MarkerType, Node, Edge,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import { Button, Tooltip } from 'antd'
import { ApartmentOutlined } from '@ant-design/icons'
import { ViewPluginProps, SceneData } from '../plugins/types'
import { getDagreLayout } from '../utils/layoutEngine'
import SceneNode from '../SceneNode'
import ChoiceNode from '../ChoiceNode'
import ScriptEdge from '../ScriptEdge'

const NODE_TYPES = { scene: SceneNode, choice: ChoiceNode }
const EDGE_TYPES = { scriptEdge: ScriptEdge }

function TimelineViewInner({ data, containerWidth, containerHeight, onNodeClick, onEdgeClick, onPaneClick }: ViewPluginProps) {
  const reactFlowInstance = useReactFlow()
  const [layoutVersion, setLayoutVersion] = useState(0)

  const { nodes: initialNodes, edges: initialEdges } = useMemo(() => {
    const nodes: Node[] = []
    const edges: Edge[] = []
    const sortedScenes = [...data.scenes].sort((a, b) => (a.scene_code || '').localeCompare(b.scene_code || ''))
    sortedScenes.forEach((sc: SceneData) => {
      nodes.push({
        id: sc.id, type: 'scene', position: { x: 0, y: 0 },
        data: {
          label: sc.scene_code, scene_code: sc.scene_code,
          scene_type: sc.scene_type || 'dialogue', location: sc.location || '',
          narration_preview: sc.narration_preview || '',
          emotion_level: sc.emotion_level || 5, status: sc.status,
          is_wow_moment: sc.is_wow_moment || false,
          characterCount: (sc.characters_involved || []).length, foreshadowCount: 0,
        },
      })
    })
    data.scene_links.filter(l => l.type === 'sequential').forEach(link => {
      edges.push({
        id: `seq-${link.source}-${link.target}`,
        source: link.source, target: link.target,
        type: 'scriptEdge', label: '→',
        data: { strength: link.strength || 3, edgeType: 'sequential' },
        markerEnd: { type: MarkerType.ArrowClosed, width: 12, height: 12, color: '#3b82f6' },
        style: { stroke: '#3b82f680', strokeWidth: 2 },
      })
    })
    const { nodes: layouted, edges: layoutedEdges } = getDagreLayout(nodes, edges, 'LR', { nodeWidth: 180, nodeHeight: 140, rankSep: 100 })
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

export default function TimelineView(props: ViewPluginProps) {
  return <ReactFlowProvider><TimelineViewInner {...props} /></ReactFlowProvider>
}