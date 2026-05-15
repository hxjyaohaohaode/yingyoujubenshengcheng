import { useState, useEffect, useCallback, useMemo, useRef } from 'react'
import {
  ReactFlowProvider, Node, Edge, Connection, addEdge,
} from '@xyflow/react'
import {
  Button, Upload, Tag, Space, App, Spin, Empty,
  Drawer, Modal, Input, Tooltip, Slider, Select, Segmented,
} from 'antd'
import {
  UploadOutlined, RobotOutlined, SaveOutlined,
  DiffOutlined, UndoOutlined, ThunderboltOutlined,
  ReloadOutlined, DeleteOutlined, EditOutlined,
} from '@ant-design/icons'
import { useProjectStore } from '../stores/projectStore'
import { api, API_BASE, relationsApi, foreshadowsApi } from '../api/client'
import { eventBus, DataEvents } from '../services/eventBus'
import NodeInfoCard, { CardData, CardNodeType } from '../components/script-viz/NodeInfoCard'
import ExportPanel from '../components/script-viz/ExportPanel'
import { AnalysisData } from '../components/script-viz/plugins/types'
import ScriptVizSection from '../components/script-viz/ScriptVizSection'

const { Option } = Select

const CHARACTER_RELATION_TYPES = [
  { value: 'related', label: '关联' }, { value: 'friend', label: '朋友' },
  { value: 'enemy', label: '敌人' }, { value: 'lover', label: '恋人' },
  { value: 'family', label: '家人' }, { value: 'mentor', label: '师徒' },
  { value: 'rival', label: '对手' }, { value: 'ally', label: '盟友' },
]

const FORESHADOW_RELATION_TYPES = [
  { value: 'related', label: '关联' }, { value: 'depends_on', label: '依赖' },
  { value: 'enables', label: '启用' }, { value: 'contradicts', label: '矛盾' },
  { value: 'reinforces', label: '强化' },
]

const VIEW_TABS = [
  { label: '角色关系', value: 'character-graph' },
  { label: '时间线', value: 'timeline' },
  { label: '分支与结局', value: 'branch-ending' },
  { label: '伏笔网络', value: 'foreshadow-net' },
]

function getViewTabLabel(baseLabel: string, value: string, data: AnalysisData | null) {
  if (!data) return baseLabel
  if (value === 'character-graph') return `${baseLabel} (${data.characters.length})`
  if (value === 'timeline') return `${baseLabel} (${data.scenes.length})`
  if (value === 'branch-ending') return `${baseLabel} (${data.scenes.length})`
  if (value === 'foreshadow-net') return `${baseLabel} (${data.foreshadows.length})`
  return baseLabel
}

function ScriptVizInner() {
  const { notification } = App.useApp()
  const { currentProject } = useProjectStore()

  const [analysisData, setAnalysisData] = useState<AnalysisData | null>(null)
  const [loading, setLoading] = useState(false)
  const [activeTab, setActiveTab] = useState<string>('character-graph')
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

  const [selectedEdge, setSelectedEdge] = useState<Edge | null>(null)
  const [edgeEditOpen, setEdgeEditOpen] = useState(false)
  const [edgeEditType, setEdgeEditType] = useState('related')
  const [edgeEditTrust, setEdgeEditTrust] = useState(5)
  const [edgeEditFavor, setEdgeEditFavor] = useState(5)
  const [edgeEditStrength, setEdgeEditStrength] = useState(5)
  const [edgeEditDescription, setEdgeEditDescription] = useState('')
  const [edgeDeleting, setEdgeDeleting] = useState(false)
  const refreshTimerRef = useRef<number | null>(null)

  const fetchAnalysis = useCallback(async () => {
    if (!currentProject?.id) return
    setLoading(true)
    setCardData(null)
    setSelectedEdge(null)
    try {
      const data = await api.post<AnalysisData>(`/script-viz/analyze-project/${currentProject.id}`)
      setAnalysisData(data)
    } catch (e: any) {
      notification.error({ message: '解析失败', description: e?.message || '无法获取剧本数据', placement: 'topRight' })
    } finally {
      setLoading(false)
    }
  }, [currentProject?.id, notification])

  const scheduleAnalysisRefresh = useCallback((delay = 180) => {
    if (refreshTimerRef.current) {
      window.clearTimeout(refreshTimerRef.current)
    }
    refreshTimerRef.current = window.setTimeout(() => {
      refreshTimerRef.current = null
      fetchAnalysis()
    }, delay)
  }, [fetchAnalysis])

  useEffect(() => { fetchAnalysis() }, [currentProject?.id])

  useEffect(() => {
    const unsubs = [
      eventBus.on(DataEvents.SCENE_CREATED, () => scheduleAnalysisRefresh()),
      eventBus.on(DataEvents.SCENE_UPDATED, () => scheduleAnalysisRefresh()),
      eventBus.on(DataEvents.SCENE_DELETED, () => scheduleAnalysisRefresh()),
      eventBus.on(DataEvents.SCENE_FINALIZED, () => scheduleAnalysisRefresh()),
      eventBus.on(DataEvents.CHAPTER_CREATED, () => scheduleAnalysisRefresh()),
      eventBus.on(DataEvents.CHAPTER_UPDATED, () => scheduleAnalysisRefresh()),
      eventBus.on(DataEvents.CHAPTER_DELETED, () => scheduleAnalysisRefresh()),
      eventBus.on(DataEvents.CHARACTER_CREATED, () => scheduleAnalysisRefresh()),
      eventBus.on(DataEvents.CHARACTER_UPDATED, () => scheduleAnalysisRefresh()),
      eventBus.on(DataEvents.CHARACTER_DELETED, () => scheduleAnalysisRefresh()),
      eventBus.on(DataEvents.RELATION_CREATED, () => scheduleAnalysisRefresh()),
      eventBus.on(DataEvents.RELATION_UPDATED, () => scheduleAnalysisRefresh()),
      eventBus.on(DataEvents.RELATION_DELETED, () => scheduleAnalysisRefresh()),
      eventBus.on(DataEvents.FORESHADOW_CREATED, () => scheduleAnalysisRefresh()),
      eventBus.on(DataEvents.FORESHADOW_UPDATED, () => scheduleAnalysisRefresh()),
      eventBus.on(DataEvents.FORESHADOW_DELETED, () => scheduleAnalysisRefresh()),
      eventBus.on(DataEvents.PROJECT_SWITCHED, () => scheduleAnalysisRefresh(0)),
      eventBus.on(DataEvents.PROJECT_CONFIG_UPDATED, () => scheduleAnalysisRefresh()),
      eventBus.on(DataEvents.AI_GENERATION_COMPLETED, () => scheduleAnalysisRefresh()),
      eventBus.on(DataEvents.PIPELINE_STATUS_CHANGED, () => scheduleAnalysisRefresh()),
    ]
    return () => {
      if (refreshTimerRef.current) {
        window.clearTimeout(refreshTimerRef.current)
        refreshTimerRef.current = null
      }
      unsubs.forEach(u => u())
    }
  }, [scheduleAnalysisRefresh])

  const handleConnect = useCallback(async (connection: Connection) => {
    if (!currentProject?.id || !connection.source || !connection.target) return
    const srcId = connection.source
    const tgtId = connection.target

    try {
      if (activeTab === 'character-graph') {
        await relationsApi.create(currentProject.id, {
          char_a_id: srcId, char_b_id: tgtId,
          relation_type: 'related', trust: 50, favor: 50,
        })
        notification.success({ message: '角色关系已创建', description: '请在弹窗中编辑关系详情', placement: 'topRight' })
      } else if (activeTab === 'foreshadow-net') {
        await foreshadowsApi.createRelation(currentProject.id, {
          from_fs_id: srcId, to_fs_id: tgtId,
          relation_type: 'related',
        })
        notification.success({ message: '伏笔关联已创建', placement: 'topRight' })
      } else {
        notification.info({ message: '此视图暂不支持手动连线', description: '场景连线请通过编辑场景顺序来建立', placement: 'topRight' })
        return
      }
      fetchAnalysis()
    } catch (e: any) {
      notification.error({ message: '创建连线失败', description: e?.message || '请检查节点类型是否匹配', placement: 'topRight' })
    }
  }, [currentProject?.id, activeTab, notification, fetchAnalysis])

  const buildCardData = useCallback((node: Node): CardData => {
    const nodeType = (node.type as CardNodeType) || 'scene'
    let title = '', subtitle = ''
    const fields: { label: string; value: string }[] = []
    const stats: { label: string; value: number | string }[] = []
    const relatedItems: { type: CardNodeType; id: string; label: string }[] = []

    if (nodeType === 'character') {
      const d = node.data as any
      title = d.label || ''; subtitle = d.role_type || ''
      if (d.core_goal) fields.push({ label: '核心动机', value: d.core_goal })
      if (d.core_fear) fields.push({ label: '核心恐惧', value: d.core_fear })
      if (d.arc_description) fields.push({ label: '角色弧', value: d.arc_description })
      stats.push({ label: '场景', value: d.sceneCount || 0 })
      stats.push({ label: '关联', value: d.relationCount || 0 })
    } else if (nodeType === 'scene') {
      const d = node.data as any
      title = d.scene_code || d.label || ''; subtitle = d.scene_type || ''
      if (d.narration_preview) fields.push({ label: '内容预览', value: d.narration_preview })
      if (d.location) fields.push({ label: '地点', value: d.location })
      stats.push({ label: '情感', value: `${d.emotion_level}/10` })
      stats.push({ label: '角色', value: d.characterCount || 0 })
    } else if (nodeType === 'foreshadow') {
      const d = node.data as any
      title = d.label || d.fs_code || ''; subtitle = d.fs_type || ''
      if (d.surface_layer) fields.push({ label: '表层', value: d.surface_layer })
      if (d.deep_layer) fields.push({ label: '深层', value: d.deep_layer })
      if (d.truth_layer) fields.push({ label: '核心层', value: d.truth_layer })
      stats.push({ label: '强化', value: d.reinforce_count || 0 })
      stats.push({ label: '状态', value: d.health || 'normal' })
    } else if (nodeType === 'choice') {
      const d = node.data as any
      title = d.label || ''; subtitle = d.choiceType === 'branch' ? '分支点' : d.choiceType === 'ending' ? '结局' : '决策'
      stats.push({ label: '选项数', value: d.optionCount || 0 })
    } else if (nodeType === 'event') {
      const d = node.data as any
      title = d.label || ''; subtitle = d.event_type || ''
      stats.push({ label: '冲击力', value: `${d.emotion_impact}/10` })
    }

    return { nodeType, nodeId: node.id, title, subtitle, fields, stats, relatedItems }
  }, [])

  const handleNodeClick = useCallback((_event: React.MouseEvent, node: Node) => {
    setSelectedNode(node.id)
    setCardData(buildCardData(node))
    setCardPosition({ x: window.innerWidth * 0.25, y: window.innerHeight * 0.12 })
  }, [buildCardData])

  const handleEdgeClick = useCallback((_event: React.MouseEvent, edge: Edge) => {
    setSelectedEdge(edge)
    setEdgeEditType((edge.data?.edgeType as string) || 'related')
    setEdgeEditTrust((edge.data?.trust as number) || 5)
    setEdgeEditFavor((edge.data?.favor as number) || 5)
    setEdgeEditStrength((edge.data?.strength as number) || 5)
    setEdgeEditDescription((edge.data?.description as string) || '')
    setEdgeEditOpen(true)
  }, [])

  const handlePaneClick = useCallback(() => {
    setSelectedNode(null); setCardData(null); setHighlightedNode(null); setSelectedEdge(null)
  }, [])

  const handleSaveEdgeEdit = useCallback(async () => {
    if (!selectedEdge || !currentProject?.id) return
    const dbId = selectedEdge.data?.dbId
    if (!dbId) { notification.warning({ message: '无法编辑此连线', placement: 'topRight' }); return }
    try {
      if (selectedEdge.data?.relationType === 'character') {
        await relationsApi.update(currentProject.id, String(dbId), {
          relation_type: edgeEditType, trust: edgeEditTrust, favor: edgeEditFavor, description: edgeEditDescription,
        })
      } else if (selectedEdge.data?.relationType === 'foreshadow') {
        await foreshadowsApi.updateRelation(currentProject.id, String(dbId), {
          relation_type: edgeEditType, description: edgeEditDescription,
        })
      }
      notification.success({ message: '连线已更新', placement: 'topRight' })
      setEdgeEditOpen(false); setSelectedEdge(null); fetchAnalysis()
    } catch (e: any) {
      notification.error({ message: '更新失败', description: e?.message || '无法更新连线', placement: 'topRight' })
    }
  }, [selectedEdge, currentProject?.id, edgeEditType, edgeEditTrust, edgeEditFavor, edgeEditDescription, notification, fetchAnalysis])

  const handleDeleteEdge = useCallback(async () => {
    if (!selectedEdge || !currentProject?.id) return
    const dbId = selectedEdge.data?.dbId
    if (!dbId) { notification.warning({ message: '无法删除此连线', placement: 'topRight' }); return }
    setEdgeDeleting(true)
    try {
      if (selectedEdge.data?.relationType === 'character') await relationsApi.delete(currentProject.id, String(dbId))
      else if (selectedEdge.data?.relationType === 'foreshadow') await foreshadowsApi.deleteRelation(currentProject.id, String(dbId))
      notification.success({ message: '连线已删除', placement: 'topRight' })
      setEdgeEditOpen(false); setSelectedEdge(null); fetchAnalysis()
    } catch (e: any) {
      notification.error({ message: '删除失败', description: e?.message || '无法删除连线', placement: 'topRight' })
    } finally { setEdgeDeleting(false) }
  }, [selectedEdge, currentProject?.id, notification, fetchAnalysis])

  const handleEdit = useCallback((nodeType: CardNodeType, nodeId: string) => {
    setEditTarget({ type: nodeType, id: nodeId }); setEditDrawerOpen(true); setEditChanges({}); setEditInstruction('')
  }, [])

  const handleAIEdit = useCallback((nodeType: CardNodeType, nodeId: string, instruction: string) => {
    setAllEdits(prev => [...prev, { target_type: nodeType, target_id: nodeId, changes: { label: nodeId }, instruction }])
    notification.success({ message: '编辑指令已记录', placement: 'topRight' }); setCardData(null)
  }, [notification])

  const handleRegenerate = useCallback(async () => {
    if (!currentProject?.id || allEdits.length === 0) { notification.warning({ message: '暂无待处理的编辑', placement: 'topRight' }); return }
    setRegenerating(true)
    try {
      const result = await api.post<any>(`/script-viz/regenerate/${currentProject.id}`, { edits: allEdits, target_type: 'project' })
      setRegenerateResult(result); setAllEdits([])
      notification.success({ message: '剧本升级完成', description: result.changes_summary || '剧本已根据编辑方向全面优化', placement: 'topRight' })
    } catch (e: any) {
      notification.error({ message: '升级失败', description: e?.message || 'AI 服务暂不可用', placement: 'topRight' })
    }
    setRegenerating(false)
  }, [currentProject?.id, allEdits, notification])

  const handleApplyEdit = useCallback(async () => {
    if (!editTarget) return
    setAllEdits(prev => [...prev, { target_type: editTarget.type, target_id: editTarget.id, changes: editChanges, instruction: editInstruction }])
    setEditDrawerOpen(false); setEditTarget(null)
    notification.success({ message: '编辑已暂存', placement: 'topRight' })
  }, [editTarget, editChanges, editInstruction, notification])

  const handleUploadParse = useCallback(async (file: File) => {
    if (!currentProject?.id) return
    setUploading(true)
    const formData = new FormData(); formData.append('file', file)
    try {
      const res = await fetch(`${API_BASE}/script-viz/upload-parse/${currentProject.id}`, { method: 'POST', body: formData })
      if (!res.ok) { const errorBody = await res.json().catch(() => ({ detail: '上传解析失败' })); throw new Error(errorBody.detail || `请求失败 (${res.status})`) }
      const data = await res.json()
      if (data.status === 'ok') {
        notification.success({ message: '上传解析成功', description: `已解析 ${data.filename}`, placement: 'topRight' })
        fetchAnalysis()
      }
    } catch (e: any) {
      notification.error({ message: '解析失败', description: e?.message || '无法解析上传的剧本', placement: 'topRight' })
    }
    setUploading(false)
    return false
  }, [currentProject?.id, fetchAnalysis, notification])

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

  const canConnect = activeTab === 'character-graph' || activeTab === 'foreshadow-net'

  return (
    <div style={{ fontFamily: 'var(--font-family)' }} className="h-full flex flex-col overflow-hidden">
      <div className="flex items-center justify-between px-4 py-2 border-b border-gray-200 dark:border-slate-700 bg-white dark:bg-slate-900 shrink-0">
        <div className="flex items-center gap-3">
          <h2 className="text-lg font-bold m-0">剧本可视化</h2>
          {analysisData && (
            <Tag className="text-[10px]">
              {analysisData.characters.length}角色 · {analysisData.scenes.length}场景 · {analysisData.foreshadows.length}伏笔
            </Tag>
          )}
        </div>
        <div className="flex items-center gap-2">
          <Button size="small" icon={<ReloadOutlined />} onClick={fetchAnalysis} loading={loading}>刷新</Button>
          <Upload accept=".txt,.md" showUploadList={false} beforeUpload={handleUploadParse as any}>
            <Button size="small" icon={<UploadOutlined />} loading={uploading}>导入</Button>
          </Upload>
          <ExportPanel hasData={!!analysisData} />
          <Button size="small" type="primary" icon={<RobotOutlined />} onClick={handleRegenerate} loading={regenerating} disabled={allEdits.length === 0}>
            AI升级 {allEdits.length > 0 && `(${allEdits.length})`}
          </Button>
          {allEdits.length > 0 && (
            <Button size="small" danger type="text" icon={<UndoOutlined />}
              onClick={() => { setAllEdits([]); notification.info({ message: '已清除所有待处理编辑', placement: 'topRight' }) }}>
              清除
            </Button>
          )}
        </div>
      </div>

      <div className="flex items-center gap-2 px-4 py-2 border-b border-gray-100 dark:border-slate-800 bg-white dark:bg-slate-900 shrink-0">
        <Segmented
          size="small"
          value={activeTab}
          onChange={(v) => { setActiveTab(v as string); setCardData(null); setSelectedNode(null) }}
          options={VIEW_TABS.map(t => ({ label: <span className="text-xs">{getViewTabLabel(t.label, t.value, analysisData)}</span>, value: t.value }))}
        />
        {canConnect && (
          <Tag color="blue" className="!text-[10px] !m-0">拖拽节点连接点可创建新连线</Tag>
        )}
      </div>

      <div className="flex-1 overflow-hidden">
        {loading ? (
          <div className="h-full flex items-center justify-center"><Spin size="large" /></div>
        ) : !analysisData ? (
          <div className="h-full flex items-center justify-center">
            <Empty description={
              <div className="text-center">
                <p className="text-gray-400 mb-2">暂无数据</p>
                <Space>
                  <Button icon={<ReloadOutlined />} onClick={fetchAnalysis}>加载数据</Button>
                  <Upload accept=".txt,.md" showUploadList={false} beforeUpload={handleUploadParse as any}>
                    <Button icon={<UploadOutlined />}>导入剧本</Button>
                  </Upload>
                </Space>
              </div>
            } />
          </div>
        ) : (
          <ScriptVizSection
            data={analysisData}
            sectionType={activeTab as any}
            onNodeClick={handleNodeClick}
            onEdgeClick={handleEdgeClick}
            onPaneClick={handlePaneClick}
            onConnect={canConnect ? handleConnect : undefined}
            selectedNodeId={selectedNode}
            highlightedNodeId={highlightedNode}
          />
        )}
      </div>

      {cardData && (
        <NodeInfoCard
          data={cardData} position={cardPosition}
          onClose={() => { setCardData(null); setHighlightedNode(null) }}
          onEdit={handleEdit} onAIGenerate={handleAIEdit}
          onNavigateToNode={(nodeId: string) => { setSelectedNode(nodeId); setCardPosition({ x: cardPosition.x + 20, y: cardPosition.y + 20 }) }}
          onHighlightRelated={setHighlightedNode} onClearHighlight={() => setHighlightedNode(null)}
          onPositionChange={setCardPosition}
        />
      )}

      <Modal
        title={<><EditOutlined className="mr-2" />连线详情</>}
        open={edgeEditOpen}
        onCancel={() => { setEdgeEditOpen(false); setSelectedEdge(null) }}
        footer={Boolean(selectedEdge?.data?.dbId) ? [
          <Button key="cancel" onClick={() => { setEdgeEditOpen(false); setSelectedEdge(null) }}>取消</Button>,
          <Button key="delete" danger icon={<DeleteOutlined />} loading={edgeDeleting} onClick={handleDeleteEdge}>删除</Button>,
          <Button key="save" type="primary" icon={<SaveOutlined />} onClick={handleSaveEdgeEdit}>保存</Button>,
        ] : [<Button key="close" onClick={() => { setEdgeEditOpen(false); setSelectedEdge(null) }}>关闭</Button>]}
      >
        {selectedEdge && (
          <div className="space-y-4">
            {!Boolean(selectedEdge.data?.dbId) && (
              <div className="p-2 bg-amber-50 dark:bg-amber-900/10 border border-amber-200 dark:border-amber-800 rounded text-xs text-amber-600">
                此连线为系统自动生成，不支持编辑
              </div>
            )}
            {Boolean(selectedEdge.data?.dbId) && (
              <>
                <div><label className="text-sm font-medium block mb-1">关系类型</label>
                  <Select className="w-full" value={edgeEditType} onChange={setEdgeEditType}>
                    {(selectedEdge.data?.relationType === 'character' ? CHARACTER_RELATION_TYPES : FORESHADOW_RELATION_TYPES).map(t => (
                      <Option key={t.value} value={t.value}>{t.label}</Option>
                    ))}
                  </Select>
                </div>
                {selectedEdge.data?.relationType === 'character' && (
                  <>
                    <div><label className="text-sm font-medium block mb-1">信任度: {edgeEditTrust}</label><Slider min={1} max={10} value={edgeEditTrust} onChange={setEdgeEditTrust} /></div>
                    <div><label className="text-sm font-medium block mb-1">好感度: {edgeEditFavor}</label><Slider min={1} max={10} value={edgeEditFavor} onChange={setEdgeEditFavor} /></div>
                  </>
                )}
                <div><label className="text-sm font-medium block mb-1">关系描述</label><Input.TextArea rows={2} value={edgeEditDescription} onChange={e => setEdgeEditDescription(e.target.value)} placeholder="描述这条连线的具体含义..." /></div>
              </>
            )}
          </div>
        )}
      </Modal>

      <Drawer
        title={editTarget ? `编辑${editTarget.type === 'character' ? '角色' : editTarget.type === 'scene' ? '场景' : '伏笔'}` : '编辑'}
        open={editDrawerOpen} onClose={() => setEditDrawerOpen(false)} width={400}
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
          <div><div className="text-sm font-medium mb-2">修改指令</div><Input.TextArea rows={3} value={editInstruction} onChange={e => setEditInstruction(e.target.value)} placeholder="例如：让这个角色更加阴暗..." /></div>
          <Button type="primary" block icon={<SaveOutlined />} onClick={handleApplyEdit}>暂存修改</Button>
        </div>
      </Drawer>

      <Modal
        title={<><DiffOutlined className="mr-2" />新旧版本对比</>}
        open={compareModalOpen} onCancel={() => setCompareModalOpen(false)} width={800}
        footer={<Space><Button onClick={() => setCompareModalOpen(false)}>关闭</Button><Button type="primary" onClick={() => { fetchAnalysis(); setCompareModalOpen(false) }}>应用新版本</Button></Space>}
      >
        {regenerateResult && (
          <div className="p-2 bg-green-50 dark:bg-green-900/10 border border-green-200 dark:border-green-800 rounded">
            <div className="flex items-center gap-2">
              <ThunderboltOutlined className="text-green-500" />
              <span className="text-sm font-medium text-green-700 dark:text-green-400">{regenerateResult.changes_summary}</span>
            </div>
          </div>
        )}
      </Modal>
    </div>
  )
}

export default function ScriptViz() {
  return (
    <div className="h-full flex flex-col overflow-hidden">
      <ReactFlowProvider>
        <ScriptVizInner />
      </ReactFlowProvider>
    </div>
  )
}
