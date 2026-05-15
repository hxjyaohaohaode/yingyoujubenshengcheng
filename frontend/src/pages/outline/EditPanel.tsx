import { Tag, Button } from 'antd'
import type { Node } from '@xyflow/react'
import { EditState, DEFAULT_EDIT } from './constants'

const inputStyle: React.CSSProperties = {
  width: '100%', padding: '6px 10px', borderRadius: 4,
  border: '1px solid #d9d9d9', fontSize: 13,
}
const labelStyle: React.CSSProperties = {
  fontSize: 12, color: '#555', display: 'block', marginBottom: 4, marginTop: 10, fontWeight: 500,
}
const sectionStyle: React.CSSProperties = {
  background: '#fafafa', borderRadius: 6, padding: '10px 12px', marginTop: 12,
  borderLeft: '3px solid #d9d9d9',
}
const sectionTitleStyle: React.CSSProperties = {
  fontSize: 12, fontWeight: 600, color: '#333', marginBottom: 8,
}

interface EditPanelProps {
  node: Node
  edit: EditState
  onChange: (edit: EditState) => void
  onSave: () => void
  onCancel: () => void
  onDelete: () => void
}

function FieldGroup({ title, color, children }: { title: string; color: string; children: React.ReactNode }) {
  return (
    <div style={{ ...sectionStyle, borderLeftColor: color }}>
      <div style={sectionTitleStyle}>{title}</div>
      {children}
    </div>
  )
}

export default function EditPanel({ node, edit, onChange, onSave, onCancel, onDelete }: EditPanelProps) {
  const nodeType = node.type || 'chapter'
  const nodeLabel = { story_arc: '故事线', chapter: '章节', event: '事件', choice: '抉择' }[nodeType] || nodeType
  const nodeColor = { story_arc: 'blue', chapter: 'green', event: 'orange', choice: 'purple' }[nodeType] || 'default'

  const set = (partial: Partial<EditState>) => onChange({ ...edit, ...partial })

  return (
    <div style={{
      width: 360, borderLeft: '1px solid #e8e8e8', background: '#fff',
      padding: 16, display: 'flex', flexDirection: 'column', gap: 2,
      overflowY: 'auto', maxHeight: '100%',
    }}>
      <div style={{ fontSize: 15, fontWeight: 600, marginBottom: 6 }}>
        编辑: <Tag color={nodeColor} style={{ fontSize: 10 }}>{nodeLabel}</Tag>
      </div>

      <label style={labelStyle}>标题</label>
      <input value={edit.title} onChange={(e) => set({ title: e.target.value })} style={inputStyle} />

      <label style={labelStyle}>摘要</label>
      <textarea value={edit.summary} onChange={(e) => set({ summary: e.target.value })}
        rows={3} style={{ ...inputStyle, resize: 'vertical' }} />

      <FieldGroup title="基础属性" color="#1677ff">
        <label style={labelStyle}>弧线类型</label>
        <select value={edit.arc_type} onChange={(e) => set({ arc_type: e.target.value })} style={inputStyle}>
          <option value="main">主线</option>
          <option value="sub">支线</option>
          <option value="side">旁线</option>
        </select>

        <label style={labelStyle}>情感目标 ({edit.emotion_target}/10)</label>
        <input type="range" min={1} max={10} value={edit.emotion_target}
          onChange={(e) => set({ emotion_target: parseInt(e.target.value) })}
          style={{ width: '100%' }} />

        <label style={labelStyle}>字数目标</label>
        <input type="number" value={edit.word_target}
          onChange={(e) => set({ word_target: parseInt(e.target.value) || 0 })}
          style={inputStyle} placeholder="0" />
      </FieldGroup>

      {nodeType === 'story_arc' && (
        <FieldGroup title="故事线专属" color="#fa8c16">
          <label style={labelStyle}>核心主题</label>
          <input value={edit.core_theme} onChange={(e) => set({ core_theme: e.target.value })}
            style={inputStyle} placeholder="如：复仇与救赎" />

          <label style={labelStyle}>关键角色（逗号分隔）</label>
          <input value={edit.key_characters} onChange={(e) => set({ key_characters: e.target.value })}
            style={inputStyle} placeholder="角色A, 角色B" />

          <label style={labelStyle}>结局类型</label>
          <select value={edit.resolution_type} onChange={(e) => set({ resolution_type: e.target.value })} style={inputStyle}>
            <option value="">未定</option>
            <option value="triumph">胜利</option>
            <option value="tragedy">悲剧</option>
            <option value="bittersweet">苦甜参半</option>
            <option value="open">开放式</option>
            <option value="twist">反转</option>
          </select>
        </FieldGroup>
      )}

      {nodeType === 'chapter' && (
        <FieldGroup title="章节专属" color="#52c41a">
          <label style={labelStyle}>核心冲突</label>
          <input value={edit.core_conflict} onChange={(e) => set({ core_conflict: e.target.value })}
            style={inputStyle} placeholder="本章核心冲突" />

          <label style={labelStyle}>关键转折点（每行一个）</label>
          <textarea value={edit.key_turning_points}
            onChange={(e) => set({ key_turning_points: e.target.value })}
            rows={2} style={{ ...inputStyle, resize: 'vertical' }} placeholder="转折1&#10;转折2" />

          <label style={labelStyle}>伏笔任务（每行一个）</label>
          <textarea value={edit.foreshadow_tasks}
            onChange={(e) => set({ foreshadow_tasks: e.target.value })}
            rows={2} style={{ ...inputStyle, resize: 'vertical' }} placeholder="伏笔1&#10;伏笔2" />

          <label style={labelStyle}>视点角色</label>
          <input value={edit.pov_character} onChange={(e) => set({ pov_character: e.target.value })}
            style={inputStyle} placeholder="以谁的视角展开" />

          <label style={labelStyle}>场景设定</label>
          <input value={edit.setting} onChange={(e) => set({ setting: e.target.value })}
            style={inputStyle} placeholder="如：深夜的废弃工厂" />

          <label style={labelStyle}>时间标记</label>
          <input value={edit.time_marker} onChange={(e) => set({ time_marker: e.target.value })}
            style={inputStyle} placeholder="如：第三天黄昏" />

          <label style={labelStyle}>氛围/情绪</label>
          <select value={edit.mood} onChange={(e) => set({ mood: e.target.value })} style={inputStyle}>
            <option value="">未设定</option>
            <option value="tense">紧张</option>
            <option value="mysterious">神秘</option>
            <option value="warm">温馨</option>
            <option value="gloomy">阴郁</option>
            <option value="exciting">激昂</option>
            <option value="sad">悲伤</option>
            <option value="humorous">幽默</option>
          </select>
        </FieldGroup>
      )}

      {nodeType === 'event' && (
        <FieldGroup title="事件专属" color="#fa8c16">
          <label style={labelStyle}>事件类型</label>
          <select value={edit.event_type} onChange={(e) => set({ event_type: e.target.value })} style={inputStyle}>
            <option value="">普通事件</option>
            <option value="turning_point">转折点</option>
            <option value="revelation">揭示/真相</option>
            <option value="confrontation">对峙</option>
            <option value="sacrifice">牺牲</option>
            <option value="reunion">重逢</option>
            <option value="betrayal">背叛</option>
            <option value="discovery">发现</option>
          </select>

          <label style={labelStyle}>触发条件</label>
          <input value={edit.trigger_condition} onChange={(e) => set({ trigger_condition: e.target.value })}
            style={inputStyle} placeholder="如：当角色A发现真相时" />

          <label style={labelStyle}>后果（每行一个）</label>
          <textarea value={edit.consequences}
            onChange={(e) => set({ consequences: e.target.value })}
            rows={2} style={{ ...inputStyle, resize: 'vertical' }} placeholder="后果1&#10;后果2" />

          <label style={labelStyle}>受影响角色（逗号分隔）</label>
          <input value={edit.affected_characters} onChange={(e) => set({ affected_characters: e.target.value })}
            style={inputStyle} placeholder="角色A, 角色B" />

          <label style={labelStyle}>紧迫度</label>
          <select value={edit.urgency_level} onChange={(e) => set({ urgency_level: e.target.value })} style={inputStyle}>
            <option value="">未设定</option>
            <option value="low">低</option>
            <option value="medium">中</option>
            <option value="high">高</option>
            <option value="critical">危急</option>
          </select>
        </FieldGroup>
      )}

      {nodeType === 'choice' && (
        <FieldGroup title="抉择专属" color="#722ed1">
          <label style={labelStyle}>选项列表（每行一个）</label>
          <textarea value={edit.options}
            onChange={(e) => set({ options: e.target.value })}
            rows={3} style={{ ...inputStyle, resize: 'vertical' }} placeholder="选项A&#10;选项B&#10;选项C" />

          <label style={labelStyle}>决策背景</label>
          <textarea value={edit.decision_context}
            onChange={(e) => set({ decision_context: e.target.value })}
            rows={2} style={{ ...inputStyle, resize: 'vertical' }} placeholder="玩家在什么情境下做此抉择" />

          <label style={labelStyle}>利害关系</label>
          <input value={edit.stakes} onChange={(e) => set({ stakes: e.target.value })}
            style={inputStyle} placeholder="如：信任vs背叛" />

          <label style={labelStyle}>道德权重</label>
          <select value={edit.moral_weight} onChange={(e) => set({ moral_weight: e.target.value })} style={inputStyle}>
            <option value="">中性</option>
            <option value="good">善</option>
            <option value="evil">恶</option>
            <option value="ambiguous">模糊</option>
            <option value="sacrifice">牺牲</option>
          </select>
        </FieldGroup>
      )}

      <div style={{ display: 'flex', gap: 8, marginTop: 14 }}>
        <Button type="primary" size="small" onClick={onSave}>保存</Button>
        <Button size="small" onClick={onCancel}>取消</Button>
        <Button danger size="small" onClick={onDelete}>删除</Button>
      </div>
    </div>
  )
}

export function nodeToEditState(node: Node): EditState {
  const d = node.data as any
  return {
    ...DEFAULT_EDIT,
    title: d.label || d.title || '',
    summary: d.summary || '',
    arc_type: d.arc_type || 'main',
    emotion_target: d.emotion_target || 5,
    word_target: d.word_target || 0,
    core_conflict: d.metadata?.core_conflict || '',
    key_turning_points: (d.metadata?.key_turning_points || []).join('\n'),
    foreshadow_tasks: (d.metadata?.foreshadow_tasks || []).join('\n'),
    event_type: d.metadata?.event_type || '',
    options: (d.metadata?.options || []).join('\n'),
    core_theme: d.metadata?.core_theme || '',
    key_characters: (d.metadata?.key_characters || []).join(', '),
    resolution_type: d.metadata?.resolution_type || '',
    pov_character: d.metadata?.pov_character || '',
    setting: d.metadata?.setting || '',
    time_marker: d.metadata?.time_marker || '',
    mood: d.metadata?.mood || '',
    trigger_condition: d.metadata?.trigger_condition || '',
    consequences: (d.metadata?.consequences || []).join('\n'),
    affected_characters: (d.metadata?.affected_characters || []).join(', '),
    urgency_level: d.metadata?.urgency_level || '',
    decision_context: d.metadata?.decision_context || '',
    stakes: d.metadata?.stakes || '',
    moral_weight: d.metadata?.moral_weight || '',
  }
}

export function editStateToNodeData(edit: EditState, existingData: any): any {
  const newMetadata = { ...(existingData.metadata || {}) }

  if (edit.core_conflict) newMetadata.core_conflict = edit.core_conflict
  if (edit.key_turning_points) newMetadata.key_turning_points = edit.key_turning_points.split('\n').filter(Boolean)
  if (edit.foreshadow_tasks) newMetadata.foreshadow_tasks = edit.foreshadow_tasks.split('\n').filter(Boolean)
  if (edit.event_type) newMetadata.event_type = edit.event_type
  if (edit.options) newMetadata.options = edit.options.split('\n').filter(Boolean)
  if (edit.core_theme) newMetadata.core_theme = edit.core_theme
  if (edit.key_characters) newMetadata.key_characters = edit.key_characters.split(',').map((s: string) => s.trim()).filter(Boolean)
  if (edit.resolution_type) newMetadata.resolution_type = edit.resolution_type
  if (edit.pov_character) newMetadata.pov_character = edit.pov_character
  if (edit.setting) newMetadata.setting = edit.setting
  if (edit.time_marker) newMetadata.time_marker = edit.time_marker
  if (edit.mood) newMetadata.mood = edit.mood
  if (edit.trigger_condition) newMetadata.trigger_condition = edit.trigger_condition
  if (edit.consequences) newMetadata.consequences = edit.consequences.split('\n').filter(Boolean)
  if (edit.affected_characters) newMetadata.affected_characters = edit.affected_characters.split(',').map((s: string) => s.trim()).filter(Boolean)
  if (edit.urgency_level) newMetadata.urgency_level = edit.urgency_level
  if (edit.decision_context) newMetadata.decision_context = edit.decision_context
  if (edit.stakes) newMetadata.stakes = edit.stakes
  if (edit.moral_weight) newMetadata.moral_weight = edit.moral_weight

  return {
    ...existingData,
    label: edit.title,
    title: edit.title,
    summary: edit.summary,
    arc_type: edit.arc_type,
    emotion_target: edit.emotion_target,
    word_target: edit.word_target,
    metadata: newMetadata,
  }
}
