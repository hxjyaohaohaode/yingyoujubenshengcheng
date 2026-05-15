import { useMemo, useCallback, useState } from 'react'
import {
  ReactFlow, ReactFlowProvider, Background, Controls, MiniMap, useNodesState, useEdgesState,
  useReactFlow, BackgroundVariant, MarkerType, Node, Edge,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import { Button, Tooltip } from 'antd'
import { ApartmentOutlined } from '@ant-design/icons'
import { ViewPluginProps, ForeshadowData, ForeshadowLinkData } from '../plugins/types'
import { getDagreLayout } from '../utils/layoutEngine'
import ForeshadowNode from '../ForeshadowNode'
import ScriptEdge from '../ScriptEdge'

const NODE_TYPES = { foreshadow: ForeshadowNode }
const EDGE_TYPES = { scriptEdge: ScriptEdge }

function ForeshadowNetViewInner({ data, containerWidth, containerHeight, onNodeClick, onEdgeClick, onPaneClick }: ViewPluginProps) {
  const reactFlowInstance = useReactFlow()
  const [layoutVersion, setLayoutVersion] = useState(0)

  const { nodes: initialNodes, edges: initialEdges } = useMemo(() => {
    const nodes: Node[] = []
    const edges: Edge[] = []
    const connectionCount = new Map<string, number>()
    data.foreshadow_links.forEach(link => {
      connectionCount.set(link.source, (connectionCount.get(link.source) || 0) + 1)
      connectionCount.set(link.target, (connectionCount.get(link.target) || 0) + 1)
    })
    const sortedFs = [...data.foreshadows].sort((a, b) => (connectionCount.get(b.id) || 0) - (connectionCount.get(a.id) || 0))
    sortedFs.forEach((fs: ForeshadowData) => {
      nodes.push({
        id: fs.id, type: 'foreshadow', position: { x: 0, y: 0 },
        data: {
          label: fs.name || fs.fs_code, fs_code: fs.fs_code,
          fs_type: fs.fs_type || 'plot', surface_layer: fs.surface_layer || '',
          deep_layer: fs.deep_layer || '', truth_layer: fs.truth_layer || '',
          health: fs.health || 'normal', current_status: fs.current_status || 'active',
          reinforce_count: fs.reinforce_count || 0,
          layer_count: [fs.surface_layer, fs.deep_layer, fs.truth_layer].filter(Boolean).length,
          connectionCount: connectionCount.get(fs.id) || 0,
        },
      })
    })
    data.foreshadow_links.forEach((link: ForeshadowLinkData) => {
      const linkType = link.type || 'related'
      const isPlant = linkType === 'planted_in'
      const isReveal = linkType === 'revealed_in'
      const color = isPlant ? '#6366f1' : isReveal ? '#f59e0b' : '#10b981'
      edges.push({
        id: `fs-${link.source}-${link.target}-${linkType}`,
        source: link.source, target: link.target,
        type: 'scriptEdge', label: isPlant ? '铺设' : isReveal ? '回收' : linkType,
        animated: isReveal,
        data: { dbId: link.id, strength: link.strength || 5, edgeType: linkType, relationType: 'foreshadow', description: link.description || '' },
        markerEnd: { type: MarkerType.ArrowClosed, width: 10, height: 10, color },
        style: { stroke: color, strokeDasharray: isPlant ? '6 4' : undefined, opacity: 0.8 },
      })
    })
    const { nodes: layouted, edges: layoutedEdges } = getDagreLayout(nodes, edges, 'LR', { nodeWidth: 200, nodeHeight: 140 })
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

export default function ForeshadowNetView(props: ViewPluginProps) {
  return <ReactFlowProvider><ForeshadowNetViewInner {...props} /></ReactFlowProvider>
}