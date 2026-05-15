import { useState, useCallback, useRef, useEffect } from 'react'
import {
  ReactFlow, ReactFlowProvider, Controls, Background, MiniMap,
  useNodesState, useEdgesState, addEdge, useReactFlow,
  type Node, type Edge, type Connection, type NodeChange,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import { App, Button, Switch, Upload } from 'antd'
import { SaveOutlined, LayoutOutlined, QuestionCircleOutlined, UploadOutlined, EyeOutlined, EyeInvisibleOutlined } from '@ant-design/icons'
import { useProjectStore } from '../stores/projectStore'
import { api, API_BASE } from '../api/client'
import { eventBus, DataEvents } from '../services/eventBus'
import {
  EDGE_LABELS, EDGE_STYLE_MAP, EditState, DEFAULT_EDIT,
  inferEdgeType, isValidConnection, getDagreLayout, optimizeLayout, NODE_DEFAULTS,
} from './outline/constants'
import { nodeTypes } from './outline/nodes'
import EditPanel, { nodeToEditState, editStateToNodeData } from './outline/EditPanel'
import EdgeEditPopover from './outline/EdgeEditPopover'
import ContextMenu from './outline/ContextMenu'

function OutlineCanvasInner({ projectId }: { projectId: string }) {
  const { message: msgApi, modal } = App.useApp()
  const [nodes, setNodes, onNodesChange] = useNodesState<Node>([])
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([])
  const [generating, setGenerating] = useState(false)
  const [modifying, setModifying] = useState(false)
  const [selectedNode, setSelectedNode] = useState<Node | null>(null)
  const [editOpen, setEditOpen] = useState(false)
  const [edit, setEdit] = useState<EditState>(DEFAULT_EDIT)
  const [nlInstruction, setNlInstruction] = useState('')
  const [genConfig, setGenConfig] = useState({
    genre: '', theme: '', core_contradiction: '',
    target_chapters: 10, narrative_structure: 'three_act', user_description: '',
  })
  const [showGenPanel, setShowGenPanel] = useState(false)
  const [showGuide, setShowGuide] = useState(false)
  const [showMinimap, setShowMinimap] = useState(true)
  const [showEdgeLabels, setShowEdgeLabels] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [editingEdge, setEditingEdge] = useState<Edge | null>(null)
  const [edgePopoverPos, setEdgePopoverPos] = useState({ x: 0, y: 0 })
  const [edgePopoverVisible, setEdgePopoverVisible] = useState(false)
  const [ctxMenu, setCtxMenu] = useState<{ x: number; y: number; nodes: Node[]; edges: Edge[] } | null>(null)
  const [hasSelection, setHasSelection] = useState(false)
  const rightClickStart = useRef<{ x: number; y: number; moved: boolean } | null>(null)
  const { fitView, getNodes, getEdges } = useReactFlow()
  const dirtyRef = useRef(false)
  const flowRef = useRef<HTMLDivElement>(null)

  const toRfNodes = useCallback((apiNodes: any[]): Node[] =>
    apiNodes.map((n: any) => ({
      id: n.id, type: n.node_type,
      position: { x: n.position_x || 0, y: n.position_y || 0 },
      data: { ...n, label: n.title },
    })), [])

  const toRfEdges = useCallback((apiEdges: any[]): Edge[] =>
    apiEdges.map((e: any) => {
      const style = EDGE_STYLE_MAP[e.edge_type] || { stroke: '#999', strokeWidth: 2 }
      return {
        id: e.id, source: e.source_id, target: e.target_id,
        type: 'smoothstep', animated: e.edge_type === 'sequence',
        label: e.label || EDGE_LABELS[e.edge_type] || '',
        style, data: { edge_type: e.edge_type },
      }
    }), [])

  const loadGraph = useCallback(async () => {
    if (!projectId) return
    try {
      const data = await api.get<any>(`/projects/${projectId}/outline-graph`)
      if (data.nodes?.length > 0) {
        const layouted = getDagreLayout(toRfNodes(data.nodes), toRfEdges(data.edges))
        setNodes(layouted.nodes)
        setEdges(layouted.edges)
        setTimeout(() => fitView({ padding: 0.15 }), 100)
      }
    } catch (err) { console.warn('大纲加载失败:', err) }
  }, [projectId, setNodes, setEdges, fitView, toRfNodes, toRfEdges])

  useEffect(() => { loadGraph() }, [loadGraph])

  useEffect(() => {
    const handler = () => { setTimeout(loadGraph, 500) }
    const events = [
      DataEvents.SCENE_UPDATED, DataEvents.CHARACTER_UPDATED,
      DataEvents.PROJECT_SWITCHED, DataEvents.FORESHADOW_UPDATED,
      DataEvents.WORLD_CONFIG_UPDATED, DataEvents.OUTLINE_UPDATED,
    ]
    events.forEach((e) => eventBus.on(e, handler))
    return () => { events.forEach((e) => eventBus.off(e, handler)) }
  }, [loadGraph])

  useEffect(() => {
    const el = flowRef.current
    if (!el) return
    const onMouseDown = (e: MouseEvent) => {
      if (e.button === 2) {
        rightClickStart.current = { x: e.clientX, y: e.clientY, moved: false }
      }
    }
    const onMouseMove = (e: MouseEvent) => {
      if (rightClickStart.current && !rightClickStart.current.moved) {
        const dx = e.clientX - rightClickStart.current.x
        const dy = e.clientY - rightClickStart.current.y
        if (Math.abs(dx) > 5 || Math.abs(dy) > 5) {
          rightClickStart.current.moved = true
        }
      }
    }
    el.addEventListener('mousedown', onMouseDown)
    el.addEventListener('mousemove', onMouseMove)
    return () => {
      el.removeEventListener('mousedown', onMouseDown)
      el.removeEventListener('mousemove', onMouseMove)
    }
  }, [])

  const saveAndSync = useCallback(async () => {
    if (!projectId) return
    const outlineNodes = nodes.map((n) => ({
      id: n.id, node_type: n.type || 'chapter',
      title: (n.data as any).label || (n.data as any).title || '',
      summary: (n.data as any).summary || '',
      position_x: n.position.x, position_y: n.position.y,
      parent_id: (n.data as any).parent_id || null,
      arc_type: (n.data as any).arc_type || 'main',
      emotion_target: (n.data as any).emotion_target || 5,
      word_target: (n.data as any).word_target || 0,
      metadata: (n.data as any).metadata || {},
    }))
    const outlineEdges = edges.map((e) => ({
      id: e.id, source_id: e.source, target_id: e.target,
      edge_type: (e.data as any)?.edge_type || 'sequence',
      label: (e.label as string) || '',
      metadata: (e.data as any)?.metadata || {},
    }))
    try {
      await api.put(`/projects/${projectId}/outline-graph`, { nodes: outlineNodes, edges: outlineEdges })
      await api.post(`/projects/${projectId}/outline-graph/sync`)
      dirtyRef.current = false
      msgApi.success('大纲已保存并同步')
      eventBus.emit(DataEvents.OUTLINE_UPDATED, { projectId })
      eventBus.emit(DataEvents.CHAPTER_UPDATED, { projectId })
      eventBus.emit(DataEvents.SCENE_UPDATED, { projectId })
      eventBus.emit(DataEvents.FORESHADOW_UPDATED, { projectId })
      eventBus.emit(DataEvents.WORLD_CONFIG_UPDATED, { projectId })
    } catch (err) { console.warn('大纲保存失败:', err) }
  }, [projectId, nodes, edges, msgApi])

  useEffect(() => {
    if (!dirtyRef.current) return
    const timer = setTimeout(saveAndSync, 3000)
    return () => clearTimeout(timer)
  }, [nodes, edges, saveAndSync])

  const applyGraphData = useCallback((data: any) => {
    if (data.nodes?.length > 0) {
      const layouted = getDagreLayout(toRfNodes(data.nodes), toRfEdges(data.edges))
      setNodes(layouted.nodes)
      setEdges(layouted.edges)
      setTimeout(() => fitView({ padding: 0.15 }), 100)
      dirtyRef.current = false
    }
  }, [setNodes, setEdges, fitView, toRfNodes, toRfEdges])

  const handleGenerate = useCallback(async () => {
    if (!projectId) return
    setGenerating(true)
    try {
      applyGraphData(await api.post<any>(`/projects/${projectId}/outline-graph/generate`, genConfig))
    } catch (err) { console.warn('大纲生成失败:', err) }
    finally { setGenerating(false) }
  }, [projectId, genConfig, applyGraphData])

  const handleModify = useCallback(async () => {
    if (!projectId || !nlInstruction.trim()) return
    setModifying(true)
    try {
      applyGraphData(await api.post<any>(`/projects/${projectId}/outline-graph/modify`, { instruction: nlInstruction }))
      setNlInstruction('')
    } catch (err) { console.warn('大纲修改失败:', err) }
    finally { setModifying(false) }
  }, [projectId, nlInstruction, applyGraphData])

  const handleFileUpload = useCallback(async (file: File) => {
    if (!projectId) return false
    setUploading(true)
    const formData = new FormData()
    formData.append('file', file)
    try {
      const res = await fetch(`${API_BASE}/projects/${projectId}/outline-graph/parse-document`, {
        method: 'POST', body: formData,
      })
      const data = await res.json()
      if (data.nodes?.length > 0) {
        applyGraphData(data)
        msgApi.success(`已解析文档，生成 ${data.nodes.length} 个节点`)
      } else {
        msgApi.warning('未能从文档中解析出大纲内容')
      }
    } catch (err) { console.warn('文档解析失败:', err); msgApi.error('文档解析失败') }
    finally { setUploading(false) }
    return false
  }, [projectId, applyGraphData, msgApi])

  const onConnect = useCallback((params: Connection) => {
    const srcNode = nodes.find((n) => n.id === params.source)
    const tgtNode = nodes.find((n) => n.id === params.target)
    const validation = isValidConnection(srcNode?.type || '', tgtNode?.type || '', params.sourceHandle, params.targetHandle)
    if (!validation.valid) { msgApi.warning(validation.reason || '无效连接'); return }
    const edgeType = inferEdgeType(srcNode?.type || '', tgtNode?.type || '', params.sourceHandle, params.targetHandle)
    const style = EDGE_STYLE_MAP[edgeType] || { stroke: '#999', strokeWidth: 2 }
    setEdges((eds) => addEdge({
      ...params, type: 'smoothstep', animated: edgeType === 'sequence',
      label: showEdgeLabels ? (EDGE_LABELS[edgeType] || '') : '',
      style, data: { edge_type: edgeType },
    }, eds))
    dirtyRef.current = true
  }, [nodes, setEdges, msgApi, showEdgeLabels])

  const checkValidConnection = useCallback((connection: Edge | Connection) => {
    const srcNode = nodes.find((n) => n.id === connection.source)
    const tgtNode = nodes.find((n) => n.id === connection.target)
    return isValidConnection(srcNode?.type || '', tgtNode?.type || '', connection.sourceHandle ?? null, connection.targetHandle ?? null).valid
  }, [nodes])

  const onNodeClick = useCallback((_: React.MouseEvent, node: Node) => {
    setSelectedNode(node)
    setEdit(nodeToEditState(node))
    setEditOpen(true)
  }, [])

  const onPaneClick = useCallback(() => {
    setEditOpen(false)
    setSelectedNode(null)
    setEdgePopoverVisible(false)
    setCtxMenu(null)
    setShowGuide(false)
  }, [])

  const onEdgeClick = useCallback((_: React.MouseEvent, edge: Edge) => {
    setEditingEdge(edge)
    const rect = flowRef.current?.getBoundingClientRect()
    setEdgePopoverPos({ x: _.clientX - (rect?.left || 0), y: _.clientY - (rect?.top || 0) })
    setEdgePopoverVisible(true)
  }, [])

  const confirmDelete = useCallback((title: string, onOk: () => void) => {
    modal.confirm({ title: `确认删除`, content: `确定要删除「${title}」吗？此操作不可撤销。`, okText: '确认删除', okType: 'danger', cancelText: '取消', onOk })
  }, [])

  const onNodesDelete = useCallback((deleted: Node[]) => {
    const ids = new Set(deleted.map((n) => n.id))
    setEdges((eds) => eds.filter((e) => !ids.has(e.source) && !ids.has(e.target)))
    dirtyRef.current = true
  }, [setEdges])

  const onEdgesDelete = useCallback((_deleted: Edge[]) => { dirtyRef.current = true }, [])

  const handleEdgeSave = useCallback((edgeId: string, updates: { edge_type: string; label: string; description: string; strength: string }) => {
    const style = EDGE_STYLE_MAP[updates.edge_type] || { stroke: '#999', strokeWidth: 2 }
    setEdges((eds) => eds.map((e) => {
      if (e.id === edgeId) {
        return {
          ...e, label: showEdgeLabels ? (updates.label || EDGE_LABELS[updates.edge_type] || '') : '',
          style, animated: updates.edge_type === 'sequence',
          data: { ...e.data, edge_type: updates.edge_type, description: updates.description, strength: updates.strength },
        }
      }
      return e
    }))
    dirtyRef.current = true
  }, [setEdges, showEdgeLabels])

  const handleNodeEdit = useCallback(() => {
    if (!selectedNode) return
    const newData = editStateToNodeData(edit, selectedNode.data as any)
    setNodes((nds) => nds.map((n) => n.id === selectedNode.id ? { ...n, data: newData } : n))
    dirtyRef.current = true
    setEditOpen(false)
  }, [selectedNode, edit, setNodes])

  const handleDeleteNode = useCallback(() => {
    if (!selectedNode) return
    confirmDelete((selectedNode.data as any).label || (selectedNode.data as any).title || '节点', () => {
      setNodes((nds) => nds.filter((n) => n.id !== selectedNode.id))
      setEdges((eds) => eds.filter((e) => e.source !== selectedNode.id && e.target !== selectedNode.id))
      dirtyRef.current = true
      setEditOpen(false)
      setSelectedNode(null)
      setEdit(DEFAULT_EDIT)
    })
  }, [selectedNode, setNodes, setEdges, confirmDelete])

  const handleAddNode = useCallback((nodeType: string, posX?: number, posY?: number) => {
    const id = `new_${Date.now()}`
    const def = NODE_DEFAULTS[nodeType] || {}
    const newNode: Node = {
      id, type: nodeType,
      position: { x: posX ?? (Math.random() * 400 + 100), y: posY ?? (Math.random() * 400 + 100) },
      data: {
        label: def.label, title: def.label, summary: '',
        arc_type: def.arc_type || 'main', emotion_target: 5, word_target: def.word_target || 0,
        metadata: def.event_type ? { event_type: def.event_type } : def.options ? { options: def.options } : {},
      },
    }
    setNodes((nds) => nds.concat(newNode))
    dirtyRef.current = true
  }, [setNodes])

  const handleOptimizeLayout = useCallback(() => {
    const result = optimizeLayout(nodes, edges)
    setNodes(result.nodes)
    setEdges(result.edges)
    dirtyRef.current = true
    setTimeout(() => fitView({ padding: 0.15 }), 100)
    msgApi.success('布局已优化')
  }, [nodes, edges, setNodes, setEdges, fitView, msgApi])

  const toggleEdgeLabels = useCallback(() => {
    const newVal = !showEdgeLabels
    setShowEdgeLabels(newVal)
    setEdges((eds) => eds.map((e) => ({
      ...e,
      label: newVal ? ((e.label as string) || EDGE_LABELS[(e.data as any)?.edge_type] || '') : '',
    })))
  }, [showEdgeLabels, setEdges])

  const onNodesChangeWrapped = useCallback((changes: NodeChange[]) => {
    onNodesChange(changes)
    if (changes.some((c) => c.type === 'position' && c.dragging === false)) dirtyRef.current = true
  }, [onNodesChange])

  const onSelectionChange = useCallback(({ nodes: selNodes }: { nodes: Node[]; edges: Edge[] }) => {
    setHasSelection(selNodes.length > 0)
  }, [])

  const onNodeContextMenu = useCallback((event: React.MouseEvent, node: Node) => {
    event.preventDefault()
    const wasDrag = rightClickStart.current?.moved ?? false
    rightClickStart.current = null
    if (wasDrag) {
      const selectedNodes = getNodes().filter((n) => n.selected)
      const selectedEdges = getEdges().filter((e) => e.selected)
      setCtxMenu({ x: event.clientX, y: event.clientY, nodes: selectedNodes, edges: selectedEdges })
    } else {
      const selected = getNodes().filter((n) => n.selected)
      setCtxMenu({ x: event.clientX, y: event.clientY, nodes: selected.length > 0 ? selected : [node], edges: [] })
    }
  }, [getNodes, getEdges])

  const onEdgeContextMenu = useCallback((event: React.MouseEvent, edge: Edge) => {
    event.preventDefault()
    const wasDrag = rightClickStart.current?.moved ?? false
    rightClickStart.current = null
    if (wasDrag) {
      const selectedNodes = getNodes().filter((n) => n.selected)
      const selectedEdges = getEdges().filter((e) => e.selected)
      setCtxMenu({ x: event.clientX, y: event.clientY, nodes: selectedNodes, edges: selectedEdges })
    } else {
      setCtxMenu({ x: event.clientX, y: event.clientY, nodes: [], edges: [edge] })
    }
  }, [getNodes, getEdges])

  const onPaneContextMenu = useCallback((event: MouseEvent | React.MouseEvent) => {
    event.preventDefault()
    const wasDrag = rightClickStart.current?.moved ?? false
    rightClickStart.current = null
    if (wasDrag) {
      const selectedNodes = getNodes().filter((n) => n.selected)
      const selectedEdges = getEdges().filter((e) => e.selected)
      setCtxMenu({ x: event.clientX, y: event.clientY, nodes: selectedNodes, edges: selectedEdges })
    } else {
      setCtxMenu({ x: event.clientX, y: event.clientY, nodes: [], edges: [] })
    }
  }, [getNodes, getEdges])

  const ctxDeleteNodes = useCallback((ids: string[]) => {
    const count = ids.length
    confirmDelete(`${count}个节点`, () => {
      const idSet = new Set(ids)
      setNodes((nds) => nds.filter((n) => !idSet.has(n.id)))
      setEdges((eds) => eds.filter((e) => !idSet.has(e.source) && !idSet.has(e.target)))
      dirtyRef.current = true
    })
  }, [setNodes, setEdges, confirmDelete])

  const ctxDeleteEdge = useCallback((id: string) => {
    confirmDelete('连线', () => {
      setEdges((eds) => eds.filter((e) => e.id !== id))
      dirtyRef.current = true
    })
  }, [setEdges, confirmDelete])

  const ctxDuplicateNode = useCallback((node: Node) => {
    const id = `dup_${Date.now()}_${Math.random().toString(36).slice(2, 6)}`
    setNodes((nds) => nds.concat({ ...node, id, position: { x: node.position.x + 30, y: node.position.y + 30 }, selected: false }))
    dirtyRef.current = true
  }, [setNodes])

  const ctxAlignNodes = useCallback((direction: 'horizontal' | 'vertical') => {
    const selected = getNodes().filter((n) => n.selected)
    if (selected.length < 2) return
    if (direction === 'horizontal') {
      const avgY = selected.reduce((s, n) => s + n.position.y, 0) / selected.length
      setNodes((nds) => nds.map((n) => selected.find((s) => s.id === n.id) ? { ...n, position: { ...n.position, y: avgY } } : n))
    } else {
      const avgX = selected.reduce((s, n) => s + n.position.x, 0) / selected.length
      setNodes((nds) => nds.map((n) => selected.find((s) => s.id === n.id) ? { ...n, position: { ...n.position, x: avgX } } : n))
    }
    dirtyRef.current = true
  }, [getNodes, setNodes])

  const ctxSetArcType = useCallback((arcType: string) => {
    const selected = getNodes().filter((n) => n.selected)
    const ids = new Set(selected.map((n) => n.id))
    setNodes((nds) => nds.map((n) => ids.has(n.id) ? { ...n, data: { ...n.data, arc_type: arcType } } : n))
    dirtyRef.current = true
  }, [getNodes, setNodes])

  const inputStyle = { width: '100%', padding: '5px 8px', borderRadius: 4, border: '1px solid #d9d9d9', fontSize: 12 }

  const dimmedStyle = hasSelection ? { opacity: 0.35, transition: 'opacity 0.2s' } : { transition: 'opacity 0.2s' }

  return (
    <div style={{ display: 'flex', height: '100%', width: '100%' }}>
      <div style={{ flex: 1, position: 'relative' }} ref={flowRef}>
        <ReactFlow
          nodes={nodes} edges={edges}
          onNodesChange={onNodesChangeWrapped} onEdgesChange={onEdgesChange}
          onConnect={onConnect} onNodeClick={onNodeClick}
          onPaneClick={onPaneClick} onEdgeClick={onEdgeClick}
          onNodesDelete={onNodesDelete} onEdgesDelete={onEdgesDelete}
          onNodeContextMenu={onNodeContextMenu}
          onEdgeContextMenu={onEdgeContextMenu}
          onPaneContextMenu={onPaneContextMenu}
          onSelectionChange={onSelectionChange}
          isValidConnection={checkValidConnection}
          nodeTypes={nodeTypes} fitView
          selectionOnDrag={true}
          selectionKeyCode="Shift"
          multiSelectionKeyCode="Shift"
          panOnDrag={true}
          panOnScroll={false}
          zoomOnScroll={true}
          deleteKeyCode={null}
          preventScrolling={true}
          style={{ background: '#fafafa' }}
          connectionLineStyle={{ stroke: '#722ed1', strokeWidth: 2 }}
          defaultEdgeOptions={{ type: 'smoothstep' }}
        >
          <Controls />
          <Background color="#e0e0e0" gap={20} />
          {showMinimap && (
            <MiniMap pannable zoomable style={{ position: 'absolute', bottom: 60, right: 12 }}
              nodeStrokeWidth={3} nodeColor={(n) => {
                if (n.type === 'story_arc') return '#1677ff'
                if (n.type === 'chapter') return '#52c41a'
                if (n.type === 'event') return '#fa8c16'
                if (n.type === 'choice') return '#722ed1'
                return '#999'
              }}
            />
          )}
        </ReactFlow>

        <div style={{ position: 'absolute', top: 12, left: 12, zIndex: 10, display: 'flex', gap: 6, flexWrap: 'wrap', maxWidth: editOpen ? `calc(100% - 340px)` : '100%' }}>
          <Button size="small" onClick={() => setShowGenPanel(!showGenPanel)}>{showGenPanel ? '收起' : 'AI生成'}</Button>
          <Button size="small" onClick={() => handleAddNode('story_arc')}>+故事线</Button>
          <Button size="small" onClick={() => handleAddNode('chapter')}>+章节</Button>
          <Button size="small" onClick={() => handleAddNode('event')}>+事件</Button>
          <Button size="small" onClick={() => handleAddNode('choice')}>+抉择</Button>
          <Button size="small" onClick={handleOptimizeLayout} icon={<LayoutOutlined />}>优化布局</Button>
          <Button size="small" onClick={saveAndSync} icon={<SaveOutlined />}>保存同步</Button>
          <Button size="small" onClick={() => setShowGuide(!showGuide)} icon={<QuestionCircleOutlined />}>指南</Button>
          <Button size="small" onClick={toggleEdgeLabels} icon={showEdgeLabels ? <EyeOutlined /> : <EyeInvisibleOutlined />}>
            {showEdgeLabels ? '隐藏标签' : '显示标签'}
          </Button>
          <Button size="small" onClick={() => setShowMinimap(!showMinimap)}>🗺️</Button>
        </div>

        {showGuide && (
          <div style={{
            position: 'absolute', top: 48, right: editOpen ? 340 : 12, zIndex: 20,
            width: 340, maxHeight: 'calc(100vh - 120px)', overflowY: 'auto',
            background: '#fff', borderRadius: 8,
            boxShadow: '0 4px 12px rgba(0,0,0,0.15)', padding: 14,
            fontSize: 11, lineHeight: 1.6,
          }}
            onClick={(e) => e.stopPropagation()}
          >
            <div style={{ fontWeight: 600, fontSize: 13, marginBottom: 8 }}>🔗 连接指南</div>

            <div style={{ color: '#1677ff', fontWeight: 600, fontSize: 12 }}>📘 故事线节点</div>
            <div style={{ paddingLeft: 8 }}>
              <div><b>↑ 上方Handle</b>（目标）：接收上级故事线的<b>包含</b>关系</div>
              <div><b>↓ 下方Handle</b>（源）：输出到章节/事件的<b>包含</b>关系 — 故事线包含哪些章节</div>
              <div><b>← 左侧Handle</b>（目标）：接收其他故事线的<b>交汇</b>关系</div>
              <div><b>→ 右侧Handle</b>（源）：输出到其他故事线的<b>交汇</b>关系 — 两条线交叉</div>
              <div style={{ color: '#999', fontSize: 10 }}>可连接：↓→章节↑←、↓→事件↑←、→→故事线←←</div>
              <div style={{ color: '#ff4d4f', fontSize: 10 }}>不可连接：→→事件/抉择/章节的→或↓</div>
            </div>

            <div style={{ color: '#52c41a', fontWeight: 600, fontSize: 12, marginTop: 8 }}>📗 章节节点</div>
            <div style={{ paddingLeft: 8 }}>
              <div><b>↑ 上方Handle</b>（目标）：接收前一章的<b>顺序</b>关系或故事线的<b>包含</b>关系</div>
              <div><b>↓ 下方Handle</b>（源）：输出到下一章的<b>顺序</b>关系 — 章节按顺序排列</div>
              <div><b>← 左侧Handle</b>（目标）：接收故事线的<b>包含</b>关系 — 属于哪条故事线</div>
              <div><b>→ 右侧Handle</b>（源）：输出到事件/抉择的<b>包含</b>关系 — 章节里有什么</div>
              <div style={{ color: '#999', fontSize: 10 }}>可连接：↓→章节↑、→→事件←、→→抉择←、←←故事线→</div>
              <div style={{ color: '#ff4d4f', fontSize: 10 }}>不可连接：→→故事线、↓→故事线</div>
            </div>

            <div style={{ color: '#fa8c16', fontWeight: 600, fontSize: 12, marginTop: 8 }}>📙 事件节点</div>
            <div style={{ paddingLeft: 8 }}>
              <div><b>↑ 上方Handle</b>（目标）：接收章节的<b>包含</b>或上一事件的<b>顺序</b>关系</div>
              <div><b>↓ 下方Handle</b>（源）：输出到下一事件的<b>顺序</b>或抉择的<b>导致</b>关系</div>
              <div><b>← 左侧Handle</b>（目标）：接收章节的<b>包含</b>关系 — 属于哪个章节</div>
              <div><b>→ 右侧Handle</b>（源）：输出到抉择的<b>触发</b>关系 — 事件触发什么抉择</div>
              <div style={{ color: '#999', fontSize: 10 }}>可连接：↓→事件↑、↓→抉择↑、→→抉择←、←←章节→</div>
              <div style={{ color: '#ff4d4f', fontSize: 10 }}>不可连接：→→故事线、↓→故事线、→→章节</div>
            </div>

            <div style={{ color: '#722ed1', fontWeight: 600, fontSize: 12, marginTop: 8 }}>📕 抉择节点</div>
            <div style={{ paddingLeft: 8 }}>
              <div><b>↑ 上方Handle</b>（目标）：接收事件的<b>导致</b>关系 — 由什么事件触发</div>
              <div><b>↓ 下方Handle</b>（源）：输出到章节/事件的<b>导致</b>关系 — 选择后的结果</div>
              <div><b>← 左侧Handle</b>（目标）：接收章节的<b>包含</b>关系 — 属于哪个章节</div>
              <div><b>→ 右侧Handle</b>（源）：输出到事件/章节的<b>分支</b>关系 — 不同选项导向不同结果</div>
              <div style={{ color: '#999', fontSize: 10 }}>可连接：↓→章节↑、↓→事件↑、→→事件←、→→章节←、←←章节→</div>
              <div style={{ color: '#ff4d4f', fontSize: 10 }}>不可连接：→→故事线、↓→故事线</div>
            </div>

            <div style={{ marginTop: 10, padding: '6px 8px', background: '#f6ffed', borderRadius: 4, fontSize: 10 }}>
              <div style={{ fontWeight: 600, color: '#52c41a', marginBottom: 4 }}>🎯 典型连接流程</div>
              <div>故事线↓ → 章节↑（故事线包含章节）</div>
              <div>章节↓ → 章节↑（章节顺序推进）</div>
              <div>章节→ → 事件←（章节包含事件）</div>
              <div>事件→ → 抉择↑（事件触发抉择）</div>
              <div>抉择↓ → 章节↑（选择导致新章节）</div>
              <div>抉择→ → 事件←（选择分支到事件）</div>
              <div>故事线→ → 故事线←（两条线交汇）</div>
            </div>

            <div style={{ marginTop: 8, padding: '6px 8px', background: '#fff7e6', borderRadius: 4, fontSize: 10 }}>
              <div style={{ fontWeight: 600 }}>⌨️ 操作说明</div>
              <div>🖱️ 左键拖拽空白 = 平移画布</div>
              <div>🖱️ Shift+左键拖拽 = 框选节点</div>
              <div>🖱️ 右键点击 = 上下文菜单</div>
              <div>🖱️ 右键拖拽 = 框选+松开菜单</div>
              <div>🖱️ 滚轮 = 缩放画布</div>
              <div>🖱️ 悬停Handle圆点 = 查看连接提示</div>
              <div>⌨️ Delete = 删除选中（有确认弹窗）</div>
            </div>
          </div>
        )}

        {showGenPanel && (
          <div style={{
            position: 'absolute', top: 48, left: 12, zIndex: 10,
            width: 300, background: '#fff', borderRadius: 8,
            boxShadow: '0 4px 12px rgba(0,0,0,0.15)', padding: 14,
          }}>
            <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 8 }}>AI生成大纲架构</div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              <input placeholder="题材" value={genConfig.genre} onChange={(e) => setGenConfig({ ...genConfig, genre: e.target.value })} style={inputStyle} />
              <input placeholder="主题" value={genConfig.theme} onChange={(e) => setGenConfig({ ...genConfig, theme: e.target.value })} style={inputStyle} />
              <input placeholder="核心矛盾" value={genConfig.core_contradiction} onChange={(e) => setGenConfig({ ...genConfig, core_contradiction: e.target.value })} style={inputStyle} />
              <select value={genConfig.narrative_structure} onChange={(e) => setGenConfig({ ...genConfig, narrative_structure: e.target.value })} style={inputStyle}>
                <option value="three_act">三幕式</option><option value="hero_journey">英雄之旅</option>
                <option value="save_cat">救猫咪</option><option value="hook_reversal">钩子-反转螺旋</option>
                <option value="escalation">爽点递进</option><option value="five_act">五幕式</option>
              </select>
              <input type="number" placeholder="目标章节数" value={genConfig.target_chapters}
                onChange={(e) => setGenConfig({ ...genConfig, target_chapters: parseInt(e.target.value) || 10 })} style={inputStyle} />
              <textarea placeholder="用自然语言描述你想要的故事大纲..." value={genConfig.user_description}
                onChange={(e) => setGenConfig({ ...genConfig, user_description: e.target.value })} rows={3}
                style={{ ...inputStyle, resize: 'vertical' }} />
              <Button type="primary" size="small" loading={generating} onClick={handleGenerate} block>生成</Button>
            </div>
          </div>
        )}

        <div style={{ position: 'absolute', bottom: 12, left: 12, right: editOpen ? 340 : 12, zIndex: 10 }}>
          <div style={{ display: 'flex', background: '#fff', borderRadius: 8, boxShadow: '0 2px 8px rgba(0,0,0,0.1)', overflow: 'hidden' }}>
            <Upload beforeUpload={handleFileUpload} showUploadList={false} accept=".png,.jpg,.jpeg,.pdf,.doc,.docx,.xls,.xlsx,.txt">
              <Button size="small" loading={uploading} icon={<UploadOutlined />} style={{ border: 'none', borderRadius: 0 }}>上传</Button>
            </Upload>
            <div style={{ width: 1, background: '#f0f0f0' }} />
            <input placeholder="自然语言修改：在第三章增加反转事件、把支线2合并到主线..."
              value={nlInstruction} onChange={(e) => setNlInstruction(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && handleModify()}
              style={{ flex: 1, padding: '8px 12px', border: 'none', outline: 'none', fontSize: 12 }}
            />
            <Button type="primary" size="small" loading={modifying} onClick={handleModify} style={{ margin: 4, borderRadius: 4 }}>AI修改</Button>
          </div>
        </div>

        <EdgeEditPopover edge={editingEdge} visible={edgePopoverVisible} onClose={() => setEdgePopoverVisible(false)} onSave={handleEdgeSave} position={edgePopoverPos} />
      </div>

      {editOpen && selectedNode && (
        <EditPanel node={selectedNode} edit={edit} onChange={setEdit} onSave={handleNodeEdit} onCancel={() => { setEditOpen(false); setSelectedNode(null) }} onDelete={handleDeleteNode} />
      )}

      {ctxMenu && (
        <ContextMenu
          x={ctxMenu.x} y={ctxMenu.y} nodes={ctxMenu.nodes} edges={ctxMenu.edges}
          onClose={() => setCtxMenu(null)}
          onDeleteNodes={ctxDeleteNodes} onDeleteEdge={ctxDeleteEdge}
          onEditEdge={(edge) => { setEditingEdge(edge); setEdgePopoverVisible(true) }}
          onDuplicateNode={ctxDuplicateNode}
          onAddNode={(type, x, y) => handleAddNode(type, x - (flowRef.current?.getBoundingClientRect().left || 0), y - (flowRef.current?.getBoundingClientRect().top || 0))}
          onAlignNodes={ctxAlignNodes} onSetArcType={ctxSetArcType}
        />
      )}
    </div>
  )
}

export default function OutlineCanvas() {
  const { currentProject } = useProjectStore()
  const projectId = currentProject?.id || ''
  return (
    <ReactFlowProvider>
      <OutlineCanvasInner projectId={projectId} />
    </ReactFlowProvider>
  )
}
