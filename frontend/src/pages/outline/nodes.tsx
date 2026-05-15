import { Handle, Position, type NodeProps } from '@xyflow/react'
import { Tag, Tooltip } from 'antd'

const hs = (color: string, extra?: React.CSSProperties): React.CSSProperties => ({
  width: 10, height: 10, background: color, border: '2px solid #fff', ...extra,
})

function GH({ type, id, position, color, label, extraStyle }: {
  type: 'source' | 'target'; id: string; position: Position; color: string; label: string; extraStyle?: React.CSSProperties
}) {
  const placement = position === Position.Top ? 'top' : position === Position.Bottom ? 'bottom' : position === Position.Left ? 'left' : 'right'
  return (
    <Tooltip title={label} placement={placement} mouseEnterDelay={0.3} styles={{ root: { fontSize: 11 } }}>
      <Handle type={type} id={id} position={position} style={hs(color, extraStyle)} />
    </Tooltip>
  )
}

export function StoryArcNode({ data, selected }: NodeProps) {
  const d = data as any
  const isMain = d.arc_type === 'main'
  const color = isMain ? '#1677ff' : '#fa8c16'

  return (
    <div style={{
      padding: '12px 18px', borderRadius: 10,
      background: isMain ? '#e6f4ff' : '#fff7e6',
      border: `2px solid ${selected ? '#722ed1' : color}`,
      minWidth: 200, maxWidth: 280,
      boxShadow: selected ? '0 0 0 2px rgba(114,46,209,0.25), 0 4px 12px rgba(0,0,0,0.1)' : '0 2px 8px rgba(0,0,0,0.06)',
      position: 'relative', transition: 'all 0.15s ease',
    }}>
      <GH type="target" id="top-in" position={Position.Top} color={color} label="↑ 上级接入：接收来自更上层故事线的包含关系" />
      <GH type="target" id="left-cross" position={Position.Left} color="#fa8c16" label="← 交汇：接收其他故事线的交叉连接" extraStyle={{ left: -6 }} />

      <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
        <Tag color={isMain ? 'blue' : 'orange'} style={{ margin: 0, fontSize: 10 }}>{isMain ? '主线' : '支线'}</Tag>
        <span style={{ fontWeight: 600, fontSize: 13, color: '#333' }}>{d.label || d.title}</span>
      </div>
      {d.summary && <div style={{ fontSize: 11, color: '#666', lineHeight: 1.5, marginTop: 4 }}>{d.summary.length > 80 ? d.summary.slice(0, 80) + '...' : d.summary}</div>}
      <div style={{ display: 'flex', gap: 8, marginTop: 6, fontSize: 10, color: '#999' }}>
        {d.word_target > 0 && <span>{d.word_target.toLocaleString()}字</span>}
        <span>情感 {d.emotion_target}/10</span>
        {d.metadata?.core_theme && <span>· {d.metadata.core_theme}</span>}
      </div>

      <GH type="source" id="bottom-out" position={Position.Bottom} color={color} label="↓ 下级输出：连接到章节或事件（包含关系）" />
      <GH type="source" id="right-cross" position={Position.Right} color="#fa8c16" label="交汇 →：连接到其他故事线（交叉关系）" extraStyle={{ right: -6 }} />
    </div>
  )
}

export function ChapterOutlineNode({ data, selected }: NodeProps) {
  const d = data as any

  return (
    <div style={{
      padding: '10px 16px', borderRadius: 8,
      background: '#f6ffed', border: `1.5px solid ${selected ? '#722ed1' : '#52c41a'}`,
      minWidth: 180, maxWidth: 260,
      boxShadow: selected ? '0 0 0 2px rgba(114,46,209,0.25), 0 4px 12px rgba(0,0,0,0.08)' : '0 2px 6px rgba(0,0,0,0.05)',
      position: 'relative', transition: 'all 0.15s ease',
    }}>
      <GH type="target" id="top-seq" position={Position.Top} color="#1677ff" label="↑ 前章接入：接收上一章节的顺序连接" />
      <GH type="target" id="left-contain" position={Position.Left} color="#91d5ff" label="← 被包含：接收故事线的包含关系" extraStyle={{ left: -6 }} />

      <div style={{ display: 'flex', alignItems: 'center', gap: 4, marginBottom: 2 }}>
        <Tag color="green" style={{ margin: 0, fontSize: 9 }}>章节</Tag>
        <span style={{ fontWeight: 600, fontSize: 12, color: '#333' }}>{d.label || d.title}</span>
      </div>
      {d.summary && <div style={{ fontSize: 10, color: '#666', lineHeight: 1.4, marginTop: 2 }}>{d.summary.length > 60 ? d.summary.slice(0, 60) + '...' : d.summary}</div>}
      <div style={{ display: 'flex', gap: 6, marginTop: 4, fontSize: 9, color: '#999' }}>
        {d.word_target > 0 && <span>{d.word_target.toLocaleString()}字</span>}
        <span>情感 {d.emotion_target}/10</span>
        {d.arc_type === 'sub' && <Tag color="orange" style={{ fontSize: 8, margin: 0, lineHeight: '14px' }}>支线</Tag>}
        {d.metadata?.core_conflict && <span>· 冲突: {d.metadata.core_conflict.length > 10 ? d.metadata.core_conflict.slice(0, 10) + '..' : d.metadata.core_conflict}</span>}
      </div>

      <GH type="source" id="bottom-seq" position={Position.Bottom} color="#1677ff" label="↓ 后章输出：连接到下一章节（顺序关系）" />
      <GH type="source" id="right-contain" position={Position.Right} color="#52c41a" label="包含 →：连接到事件或抉择（包含关系）" extraStyle={{ right: -6 }} />
    </div>
  )
}

export function EventOutlineNode({ data, selected }: NodeProps) {
  const d = data as any
  const evtType = d.metadata?.event_type
  const evtColor = evtType === 'turning_point' ? '#ff4d4f' : evtType === 'revelation' ? '#722ed1' : '#fa8c16'
  const evtLabel = evtType === 'turning_point' ? '转折' : evtType === 'revelation' ? '揭示' : evtType === 'confrontation' ? '对峙' : evtType === 'sacrifice' ? '牺牲' : evtType === 'reunion' ? '重逢' : evtType === 'betrayal' ? '背叛' : evtType === 'discovery' ? '发现' : '事件'
  const tagColor = evtType === 'turning_point' ? 'red' : evtType === 'revelation' ? 'purple' : 'orange'

  return (
    <div style={{
      padding: '8px 14px', borderRadius: 6,
      background: '#fff7e6', border: `1.5px solid ${selected ? '#722ed1' : evtColor}`,
      minWidth: 150, maxWidth: 230,
      boxShadow: selected ? '0 0 0 2px rgba(114,46,209,0.25), 0 4px 12px rgba(0,0,0,0.08)' : '0 1px 4px rgba(0,0,0,0.04)',
      position: 'relative', transition: 'all 0.15s ease',
    }}>
      <GH type="target" id="top-in" position={Position.Top} color={evtColor} label="↑ 接入：接收章节包含或上一事件的顺序连接" />
      <GH type="target" id="left-from-chapter" position={Position.Left} color="#52c41a" label="← 所属章节：接收章节的包含关系" extraStyle={{ left: -6 }} />

      <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
        <Tag color={tagColor} style={{ margin: 0, fontSize: 9 }}>{evtLabel}</Tag>
        <span style={{ fontWeight: 500, fontSize: 11, color: '#333' }}>{d.label || d.title}</span>
      </div>
      {d.summary && <div style={{ fontSize: 10, color: '#666', marginTop: 2 }}>{d.summary.length > 50 ? d.summary.slice(0, 50) + '...' : d.summary}</div>}
      {d.metadata?.urgency_level && <div style={{ fontSize: 9, color: '#999', marginTop: 2 }}>紧迫度: {d.metadata.urgency_level}</div>}

      <GH type="source" id="bottom-out" position={Position.Bottom} color={evtColor} label="↓ 输出：连接到下一事件（顺序）或抉择（导致）" />
      <GH type="source" id="right-to-choice" position={Position.Right} color="#722ed1" label="触发抉择 →：连接到抉择节点（导致关系）" extraStyle={{ right: -6 }} />
    </div>
  )
}

export function ChoiceOutlineNode({ data, selected }: NodeProps) {
  const d = data as any
  const options: string[] = d.metadata?.options || []

  return (
    <div style={{
      padding: '8px 14px', borderRadius: 6,
      background: '#f9f0ff', border: `1.5px solid ${selected ? '#722ed1' : '#722ed1'}`,
      minWidth: 150, maxWidth: 230,
      boxShadow: selected ? '0 0 0 2px rgba(114,46,209,0.25), 0 4px 12px rgba(0,0,0,0.08)' : '0 1px 4px rgba(0,0,0,0.04)',
      position: 'relative', transition: 'all 0.15s ease',
    }}>
      <GH type="target" id="top-from-event" position={Position.Top} color="#722ed1" label="↑ 事件触发：接收事件的导致关系" />
      <GH type="target" id="left-from-chapter" position={Position.Left} color="#52c41a" label="← 所属章节：接收章节的包含关系" extraStyle={{ left: -6 }} />

      <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
        <Tag color="purple" style={{ margin: 0, fontSize: 9 }}>抉择</Tag>
        <span style={{ fontWeight: 500, fontSize: 11, color: '#333' }}>{d.label || d.title}</span>
      </div>
      {d.summary && <div style={{ fontSize: 10, color: '#666', marginTop: 2 }}>{d.summary.length > 50 ? d.summary.slice(0, 50) + '...' : d.summary}</div>}
      {options.length > 0 && (
        <div style={{ display: 'flex', gap: 2, marginTop: 3, flexWrap: 'wrap' }}>
          {options.slice(0, 3).map((opt, i) => (
            <Tag key={i} color="purple" style={{ fontSize: 8, margin: 0, lineHeight: '14px' }}>{opt.length > 8 ? opt.slice(0, 8) + '..' : opt}</Tag>
          ))}
          {options.length > 3 && <Tag style={{ fontSize: 8, margin: 0 }}>+{options.length - 3}</Tag>}
        </div>
      )}
      {d.metadata?.moral_weight && <div style={{ fontSize: 9, color: '#999', marginTop: 2 }}>道德权重: {d.metadata.moral_weight}</div>}

      <GH type="source" id="bottom-out" position={Position.Bottom} color="#722ed1" label="↓ 输出：连接到下一章节或事件（导致关系）" />
      <GH type="source" id="right-branch" position={Position.Right} color="#ff4d4f" label="分支 →：连接到分支事件或章节（导致关系）" extraStyle={{ right: -6 }} />
    </div>
  )
}

export const nodeTypes = {
  story_arc: StoryArcNode,
  chapter: ChapterOutlineNode,
  event: EventOutlineNode,
  choice: ChoiceOutlineNode,
}
