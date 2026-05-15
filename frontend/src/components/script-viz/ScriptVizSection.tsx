import { useMemo, useCallback, useState, useRef, useEffect } from 'react'
import {
  ReactFlow, ReactFlowProvider, Background, Controls, MiniMap, useNodesState, useEdgesState,
  useReactFlow, BackgroundVariant, MarkerType, Node, Edge, Connection,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import { Button, Tooltip, Collapse } from 'antd'
import { ApartmentOutlined, ExpandOutlined } from '@ant-design/icons'
import { AnalysisData, CharacterData, RelationData, SceneData, SceneLinkData, ForeshadowData, ForeshadowLinkData } from './plugins/types'
import { getDagreLayout, LayoutDirection } from './utils/layoutEngine'
import CharacterNode from './CharacterNode'
import SceneNode from './SceneNode'
import ChoiceNode from './ChoiceNode'
import EventNode from './EventNode'
import ForeshadowNode from './ForeshadowNode'
import ScriptEdge from './ScriptEdge'
import ChoiceEdge from './ChoiceEdge'

const NODE_TYPES = {
  character: CharacterNode,
  scene: SceneNode,
  choice: ChoiceNode,
  event: EventNode,
  foreshadow: ForeshadowNode,
}

const EDGE_TYPES = {
  scriptEdge: ScriptEdge,
  choiceEdge: ChoiceEdge,
}

const RELATION_COLORS: Record<string, string> = {
  friend: '#10b981', enemy: '#ef4444', lover: '#ec4899',
  family: '#f59e0b', mentor: '#8b5cf6', rival: '#f97316',
  ally: '#06b6d4', related: '#6b7280',
}

interface ScriptVizSectionProps {
  data: AnalysisData
  sectionType: 'character-graph' | 'timeline' | 'branch-ending' | 'foreshadow-net'
  onNodeClick?: (event: React.MouseEvent, node: Node) => void
  onEdgeClick?: (event: React.MouseEvent, edge: Edge) => void
  onPaneClick?: () => void
  onConnect?: (connection: Connection) => void
  selectedNodeId?: string | null
  highlightedNodeId?: string | null
}

function SectionFlow({ data, sectionType, onNodeClick, onEdgeClick, onPaneClick, onConnect, selectedNodeId, highlightedNodeId }: Omit<ScriptVizSectionProps, 'title' | 'description'>) {
  const reactFlowInstance = useReactFlow()
  const containerRef = useRef<HTMLDivElement>(null)
  const [containerSize, setContainerSize] = useState({ w: 800, h: 400 })
  const [layoutVersion, setLayoutVersion] = useState(0)

  useEffect(() => {
    if (!containerRef.current) return
    const obs = new ResizeObserver(entries => {
      const { width, height } = entries[0].contentRect
      if (width > 0 && height > 0) setContainerSize({ w: width, h: height })
    })
    obs.observe(containerRef.current)
    return () => obs.disconnect()
  }, [])

  const isEmpty = useMemo(() => {
    if (sectionType === 'character-graph') return data.characters.length === 0
    if (sectionType === 'timeline') return data.scenes.length === 0
    if (sectionType === 'branch-ending') return data.scenes.length === 0
    if (sectionType === 'foreshadow-net') return data.foreshadows.length === 0
    return false
  }, [data, sectionType])

  const emptyMessage = useMemo(() => {
    if (sectionType === 'character-graph') return '暂无角色数据。请等待流水线完成角色设计阶段，或手动创建角色。'
    if (sectionType === 'timeline') return '暂无场景数据。请等待流水线完成场景编写阶段。'
    if (sectionType === 'branch-ending') return '暂无场景数据。分支与结局视图需要场景数据才能展示。'
    if (sectionType === 'foreshadow-net') return '暂无伏笔数据。请等待流水线完成伏笔设计阶段。'
    return '暂无数据'
  }, [sectionType])

  const { nodes: initialNodes, edges: initialEdges } = useMemo(() => {
    const nodes: Node[] = []
    const edges: Edge[] = []
    const nodeIdSet = new Set<string>()
    const sequentialLinks = data.scene_links.filter(l => l.type === 'sequential')

    if (sectionType === 'character-graph') {
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
        nodeIdSet.add(ch.id)
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
        if (!nodeIdSet.has(rel.char_a_id) || !nodeIdSet.has(rel.char_b_id)) return
        const color = RELATION_COLORS[rel.relation_type] || '#6b7280'
        edges.push({
          id: `rel-${rel.id}`, source: rel.char_a_id, target: rel.char_b_id,
          type: 'scriptEdge',
          label: rel.relation_type,
          data: {
            dbId: rel.id,
            strength: Math.max(1, Math.min(10, rel.trust / 10)),
            edgeType: rel.relation_type || 'related',
            trust: rel.trust, favor: rel.favor,
            relationType: 'character',
            description: rel.description || '',
          },
          markerEnd: { type: MarkerType.ArrowClosed, width: 10, height: 10, color },
          style: { stroke: `${color}90`, strokeWidth: 2 },
        })
      })
    }

    if (sectionType === 'timeline') {
      const sortedScenes = [...data.scenes].sort((a, b) =>
        (a.scene_code || '').localeCompare(b.scene_code || '')
      )

      sortedScenes.forEach((sc: SceneData) => {
        nodeIdSet.add(sc.id)
        nodes.push({
          id: sc.id, type: 'scene', position: { x: 0, y: 0 },
          data: {
            label: sc.scene_code, scene_code: sc.scene_code,
            scene_type: sc.scene_type || 'dialogue',
            location: sc.location || '',
            narration_preview: sc.narration_preview || '',
            emotion_level: sc.emotion_level || 5,
            status: sc.status,
            is_wow_moment: sc.is_wow_moment || false,
            characterCount: (sc.characters_involved || []).length,
            foreshadowCount: 0,
          },
        })
      })

      sequentialLinks.forEach((link: SceneLinkData) => {
        if (!nodeIdSet.has(link.source) || !nodeIdSet.has(link.target)) return
        edges.push({
          id: `seq-${link.source}-${link.target}`,
          source: link.source, target: link.target,
          type: 'scriptEdge',
          label: '→',
          data: { strength: link.strength || 3, edgeType: 'sequential' },
          markerEnd: { type: MarkerType.ArrowClosed, width: 12, height: 12, color: '#3b82f6' },
          style: { stroke: '#3b82f680', strokeWidth: 2 },
        })
      })

      data.events.forEach(ev => {
        if (ev.scene_id && nodeIdSet.has(ev.scene_id)) {
          nodeIdSet.add(ev.id)
          nodes.push({
            id: ev.id, type: 'event', position: { x: 0, y: 0 },
            data: {
              label: ev.name, event_type: ev.type || 'turning_point',
              emotion_impact: ev.emotion_impact || 5,
              chapter_number: ev.chapter_number || null,
              related_scene: ev.scene_id || null,
            },
          })
          edges.push({
            id: `event-scene-${ev.id}`,
            source: ev.id, target: ev.scene_id,
            type: 'scriptEdge',
            label: '关联',
            data: { strength: 3, edgeType: 'related' },
            markerEnd: { type: MarkerType.ArrowClosed, width: 8, height: 8, color: '#ef4444' },
            style: { stroke: '#ef444450', strokeDasharray: '3 3', strokeWidth: 1.5 },
          })
        }
      })
    }

    if (sectionType === 'branch-ending') {
      const sceneIndexById = new Map(data.scenes.map((scene, index) => [scene.id, index]))
      const choiceBridgeEdgeIds = new Set<string>()
      data.scenes.forEach((sc: SceneData) => {
        nodeIdSet.add(sc.id)
        nodes.push({
          id: sc.id, type: 'scene', position: { x: 0, y: 0 },
          data: {
            label: sc.scene_code, scene_code: sc.scene_code,
            scene_type: sc.scene_type || 'dialogue',
            location: sc.location || '',
            narration_preview: sc.narration_preview || '',
            emotion_level: sc.emotion_level || 5,
            status: sc.status,
            is_wow_moment: sc.is_wow_moment || false,
            characterCount: (sc.characters_involved || []).length,
            foreshadowCount: 0,
          },
        })
      })

      const sceneOutgoing = new Map<string, string[]>()
      sequentialLinks.forEach(l => {
        if (!sceneOutgoing.has(l.source)) sceneOutgoing.set(l.source, [])
        sceneOutgoing.get(l.source)!.push(l.target)
      })

      sceneOutgoing.forEach((targets, sourceId) => {
        if (targets.length > 1 && nodeIdSet.has(sourceId)) {
          const choiceId = `choice-${sourceId}`
          nodeIdSet.add(choiceId)
          nodes.push({
            id: choiceId, type: 'choice', position: { x: 0, y: 0 },
            data: {
              label: '分支选择',
              choiceType: 'branch',
              optionCount: targets.length,
              isHighlighted: false,
              chapterInfo: '',
            },
          })
        }
      })

      const endingSceneIds = new Set<string>()
      data.scenes.forEach(sc => {
        const hasOutgoing = (sceneOutgoing.get(sc.id) || []).length > 0
        const sceneIdx = sceneIndexById.get(sc.id) ?? -1
        if (!hasOutgoing && sceneIdx > 0) {
          endingSceneIds.add(sc.id)
          const endingId = `ending-${sc.id}`
          nodeIdSet.add(endingId)
          nodes.push({
            id: endingId, type: 'choice', position: { x: 0, y: 0 },
            data: {
              label: '结局',
              choiceType: 'ending',
              optionCount: 1,
              isHighlighted: false,
              chapterInfo: sc.scene_code,
            },
          })
        }
      })

      data.scene_links.filter(l => l.type === 'sequential').forEach((link: SceneLinkData) => {
        if (!nodeIdSet.has(link.source) || !nodeIdSet.has(link.target)) return
        const outgoing = sceneOutgoing.get(link.source) || []
        if (outgoing.length > 1) {
          const choiceId = `choice-${link.source}`
          const sourceChoiceEdgeId = `seq-src-choice-${link.source}`
          if (!choiceBridgeEdgeIds.has(sourceChoiceEdgeId)) {
            choiceBridgeEdgeIds.add(sourceChoiceEdgeId)
            edges.push({
              id: sourceChoiceEdgeId,
              source: link.source, target: choiceId,
              type: 'scriptEdge',
              data: { strength: 5, edgeType: 'sequential' },
              markerEnd: { type: MarkerType.ArrowClosed, width: 12, height: 12, color: '#3b82f6' },
              style: { stroke: '#3b82f680', strokeWidth: 2 },
            })
          }
          edges.push({
            id: `seq-choice-${link.source}-${link.target}`,
            source: choiceId, target: link.target,
            type: 'choiceEdge',
            data: { strength: link.strength || 5, edgeType: 'branch', label: '分支', isHighlighted: false },
            markerEnd: { type: MarkerType.ArrowClosed, width: 14, height: 14, color: '#8b5cf6' },
            style: { stroke: '#8b5cf680', strokeWidth: 2.5 },
            animated: true,
          })
        } else {
          edges.push({
            id: `seq-${link.source}-${link.target}`,
            source: link.source, target: link.target,
            type: 'scriptEdge',
            label: '→',
            data: { strength: link.strength || 3, edgeType: 'sequential' },
            markerEnd: { type: MarkerType.ArrowClosed, width: 12, height: 12, color: '#3b82f6' },
            style: { stroke: '#3b82f680', strokeWidth: 2 },
          })
        }
      })

      endingSceneIds.forEach(scId => {
        edges.push({
          id: `ending-edge-${scId}`,
          source: scId, target: `ending-${scId}`,
          type: 'choiceEdge',
          data: { strength: 5, edgeType: 'ending_a', label: '结局', isHighlighted: false },
          markerEnd: { type: MarkerType.ArrowClosed, width: 14, height: 14, color: '#ec4899' },
          style: { stroke: '#ec489980', strokeWidth: 2 },
        })
      })
    }

    if (sectionType === 'foreshadow-net') {
      data.foreshadows.forEach((fs: ForeshadowData) => {
        nodeIdSet.add(fs.id)
        nodes.push({
          id: fs.id, type: 'foreshadow', position: { x: 0, y: 0 },
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
            connectionCount: 0,
          },
        })
      })

      data.foreshadow_links.forEach((link: ForeshadowLinkData) => {
        if (!nodeIdSet.has(link.source) || !nodeIdSet.has(link.target)) return
        const linkType = link.type || 'related'
        const isPlant = linkType === 'planted_in'
        const isReveal = linkType === 'revealed_in'
        const color = isPlant ? '#6366f1' : isReveal ? '#f59e0b' : '#10b981'
        const edgeLabel = isPlant ? '铺设' : isReveal ? '回收' : linkType

        edges.push({
          id: `fs-${link.source}-${link.target}-${linkType}`,
          source: link.source, target: link.target,
          type: 'scriptEdge',
          label: edgeLabel,
          animated: isReveal,
          data: {
            dbId: link.id,
            strength: link.strength || 5,
            edgeType: linkType,
            relationType: 'foreshadow',
            description: link.description || '',
          },
          markerEnd: { type: MarkerType.ArrowClosed, width: 10, height: 10, color },
          style: { stroke: color, strokeDasharray: isPlant ? '6 4' : undefined, opacity: 0.8, strokeWidth: 2 },
        })
      })
    }

    const direction: LayoutDirection = sectionType === 'timeline' ? 'LR' : 'LR'
    const nodeCount = nodes.length
    const { nodes: layoutedNodes, edges: layoutedEdges } = getDagreLayout(nodes, edges, direction, {
      nodeWidth: sectionType === 'character-graph' ? 220 : 180,
      nodeHeight: sectionType === 'character-graph' ? 160 : 140,
      rankSep: nodeCount > 15 ? 120 : nodeCount > 8 ? 100 : 80,
      nodeSep: nodeCount > 15 ? 60 : nodeCount > 8 ? 50 : 40,
    })

    return { nodes: layoutedNodes, edges: layoutedEdges }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [data, sectionType, layoutVersion])

  const [rfNodes, setRfNodes, onNodesChange] = useNodesState(initialNodes)
  const [rfEdges, setRfEdges, onEdgesChange] = useEdgesState(initialEdges)

  const handleOptimizeLayout = useCallback(() => {
    setLayoutVersion(v => v + 1)
    setTimeout(() => {
      reactFlowInstance.fitView({ padding: 0.15, duration: 600 })
    }, 100)
  }, [reactFlowInstance])

  return (
    <div ref={containerRef} className="w-full h-full relative">
      {isEmpty ? (
        <div className="w-full h-full flex items-center justify-center">
          <div style={{ textAlign: 'center', padding: 48 }}>
            <div style={{ fontSize: 20, marginBottom: 12, fontWeight: 600 }}>暂无内容</div>
            <div style={{ fontSize: 14, color: 'var(--color-muted)', maxWidth: 320, lineHeight: 1.6 }}>
              {emptyMessage}
            </div>
          </div>
        </div>
      ) : (
      <ReactFlow
        nodes={rfNodes}
        edges={rfEdges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onNodeClick={onNodeClick}
        onEdgeClick={onEdgeClick}
        onPaneClick={onPaneClick}
        onConnect={onConnect}
        nodeTypes={NODE_TYPES}
        edgeTypes={EDGE_TYPES}
        fitView
        fitViewOptions={{ padding: 0.15 }}
        minZoom={0.05}
        maxZoom={4}
        deleteKeyCode={null}
        panOnDrag={true}
        panOnScroll={false}
        zoomOnScroll={true}
        zoomOnPinch={true}
        zoomOnDoubleClick={false}
        selectionOnDrag={false}
        connectOnClick={false}
        onlyRenderVisibleElements
        proOptions={{ hideAttribution: true }}
        className="bg-white dark:bg-slate-900 rounded-lg"
      >
        <Background variant={BackgroundVariant.Dots} gap={16} size={1} className="text-gray-200 dark:text-gray-700" />
        <Controls className="!rounded-lg !shadow-md !border-gray-200" position="bottom-right" showInteractive={false} />
      </ReactFlow>
      )}
      {!isEmpty && (
      <div className="absolute top-2 left-2 z-10">
        <Tooltip title="优化布局">
          <Button size="small" icon={<ApartmentOutlined />} onClick={handleOptimizeLayout}>优化布局</Button>
        </Tooltip>
      </div>
      )}
    </div>
  )
}

export default function ScriptVizSection({ data, sectionType, onNodeClick, onEdgeClick, onPaneClick, onConnect, selectedNodeId, highlightedNodeId }: ScriptVizSectionProps) {
  return (
    <div className="w-full h-full">
      <ReactFlowProvider>
        <SectionFlow
          data={data}
          sectionType={sectionType}
          onNodeClick={onNodeClick}
          onEdgeClick={onEdgeClick}
          onPaneClick={onPaneClick}
          onConnect={onConnect}
          selectedNodeId={selectedNodeId}
          highlightedNodeId={highlightedNodeId}
        />
      </ReactFlowProvider>
    </div>
  )
}
