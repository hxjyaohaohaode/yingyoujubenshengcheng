import { useState, useEffect, useRef } from 'react'
import { Select, Input } from 'antd'
import type { Edge } from '@xyflow/react'
import { EDGE_TYPE_OPTIONS, EDGE_LABELS, EDGE_STYLE_MAP, EDGE_COLORS } from './constants'

interface EdgeEditPopoverProps {
  edge: Edge | null
  visible: boolean
  onClose: () => void
  onSave: (edgeId: string, updates: { edge_type: string; label: string; description: string; strength: string }) => void
  position: { x: number; y: number }
}

export default function EdgeEditPopover({ edge, visible, onClose, onSave, position }: EdgeEditPopoverProps) {
  const [edgeType, setEdgeType] = useState('')
  const [label, setLabel] = useState('')
  const [description, setDescription] = useState('')
  const [strength, setStrength] = useState('normal')
  const [dragging, setDragging] = useState(false)
  const [pos, setPos] = useState(position)
  const dragStart = useRef({ x: 0, y: 0, px: 0, py: 0 })
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => { setPos(position) }, [position])

  useEffect(() => {
    if (edge) {
      setEdgeType((edge.data as any)?.edge_type || 'sequence')
      setLabel((edge.label as string) || '')
      setDescription((edge.data as any)?.description || '')
      setStrength((edge.data as any)?.strength || 'normal')
    }
  }, [edge])

  useEffect(() => {
    if (!dragging) return
    const onMove = (e: MouseEvent) => {
      setPos({ x: dragStart.current.px + e.clientX - dragStart.current.x, y: dragStart.current.py + e.clientY - dragStart.current.y })
    }
    const onUp = () => setDragging(false)
    window.addEventListener('mousemove', onMove)
    window.addEventListener('mouseup', onUp)
    return () => { window.removeEventListener('mousemove', onMove); window.removeEventListener('mouseup', onUp) }
  }, [dragging])

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as HTMLElement)) onClose()
    }
    if (visible) setTimeout(() => document.addEventListener('mousedown', handler), 100)
    return () => document.removeEventListener('mousedown', handler)
  }, [visible, onClose])

  if (!visible || !edge) return null

  const currentColor = EDGE_COLORS[edgeType] || '#999'

  const groupedOptions = EDGE_TYPE_OPTIONS.reduce((acc, opt) => {
    const g = opt.group || '其他'
    if (!acc[g]) acc[g] = []
    acc[g].push(opt)
    return acc
  }, {} as Record<string, typeof EDGE_TYPE_OPTIONS>)

  const inputStyle = { width: '100%', padding: '5px 8px', borderRadius: 4, border: '1px solid #d9d9d9', fontSize: 12 }
  const labelStyle = { fontSize: 11, color: '#666', display: 'block', marginBottom: 3, marginTop: 8 }

  return (
    <div ref={ref} style={{
      position: 'absolute', left: pos.x, top: pos.y, zIndex: 100,
      background: '#fff', borderRadius: 8,
      boxShadow: '0 4px 16px rgba(0,0,0,0.15)', padding: 0,
      minWidth: 260, maxWidth: 300, overflow: 'hidden',
    }}
      onClick={(e) => e.stopPropagation()}
    >
      <div style={{
        padding: '8px 12px', cursor: 'move', userSelect: 'none',
        background: '#fafafa', borderBottom: '1px solid #f0f0f0',
        display: 'flex', alignItems: 'center', gap: 6,
      }}
        onMouseDown={(e) => {
          setDragging(true)
          dragStart.current = { x: e.clientX, y: e.clientY, px: pos.x, py: pos.y }
        }}
      >
        <div style={{ width: 20, height: 3, background: currentColor, borderRadius: 2 }} />
        <span style={{ fontSize: 12, fontWeight: 600 }}>编辑连线</span>
        <span style={{ marginLeft: 'auto', cursor: 'pointer', fontSize: 14, color: '#999' }} onClick={onClose}>✕</span>
      </div>

      <div style={{ padding: '8px 12px' }}>
        <label style={labelStyle}>关系类型</label>
        <Select value={edgeType} onChange={(v) => setEdgeType(v)} style={{ width: '100%' }} size="small"
          options={Object.entries(groupedOptions).map(([group, opts]) => ({
            label: group, options: opts.map((o) => ({
              value: o.value,
              label: (
                <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <div style={{ width: 14, height: 2, background: EDGE_COLORS[o.value] || '#999' }} />
                  {o.label}
                </div>
              ),
            })),
          }))}
        />

        <label style={labelStyle}>连线标签</label>
        <Input value={label} onChange={(e) => setLabel(e.target.value)} size="small" placeholder="如：推进、触发、伏笔..." allowClear />

        <label style={labelStyle}>关系描述</label>
        <textarea value={description} onChange={(e) => setDescription(e.target.value)}
          rows={2} style={{ ...inputStyle, resize: 'vertical' }} placeholder="描述这条连线的具体含义..." />

        <label style={labelStyle}>关系强度</label>
        <select value={strength} onChange={(e) => setStrength(e.target.value)} style={inputStyle}>
          <option value="weak">弱（暗示/间接）</option>
          <option value="normal">中（正常）</option>
          <option value="strong">强（关键/必然）</option>
        </select>

        <div style={{ display: 'flex', gap: 6, justifyContent: 'flex-end', marginTop: 10 }}>
          <button onClick={onClose} style={{ padding: '3px 10px', fontSize: 11, borderRadius: 4, border: '1px solid #d9d9d9', background: '#fff', cursor: 'pointer' }}>取消</button>
          <button onClick={() => { onSave(edge.id, { edge_type: edgeType, label, description, strength }); onClose() }}
            style={{ padding: '3px 10px', fontSize: 11, borderRadius: 4, border: 'none', background: '#1677ff', color: '#fff', cursor: 'pointer' }}>保存</button>
        </div>
      </div>
    </div>
  )
}
