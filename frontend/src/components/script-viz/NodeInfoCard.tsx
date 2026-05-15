import { useState, useRef, useCallback, useEffect } from 'react'
import { Button, Tag, Divider, Space, Input } from 'antd'
import {
  EditOutlined, RobotOutlined, CloseOutlined,
} from '@ant-design/icons'

const { TextArea } = Input

export type CardNodeType = 'character' | 'scene' | 'foreshadow' | 'event' | 'choice'

export interface CardData {
  nodeType: CardNodeType
  nodeId: string
  title: string
  subtitle: string
  fields: { label: string; value: string }[]
  stats: { label: string; value: number | string; onClick?: () => void }[]
  relatedItems: { type: CardNodeType; id: string; label: string }[]
}

interface NodeInfoCardProps {
  data: CardData
  position: { x: number; y: number }
  onClose: () => void
  onEdit: (nodeType: CardNodeType, nodeId: string) => void
  onAIGenerate: (nodeType: CardNodeType, nodeId: string, instruction: string) => void
  onNavigateToNode: (nodeId: string) => void
  onHighlightRelated: (nodeId: string) => void
  onClearHighlight: () => void
  onPositionChange?: (pos: { x: number; y: number }) => void
}

const TYPE_ICONS: Record<string, string> = {
  character: '👤', scene: '🎬', foreshadow: '🔮', event: '⚡', choice: '🔀',
}

const TYPE_COLORS: Record<string, string> = {
  character: '#6366f1', scene: '#f59e0b', foreshadow: '#10b981', event: '#ef4444', choice: '#8b5cf6',
}

export default function NodeInfoCard({
  data, position, onClose, onEdit, onAIGenerate, onNavigateToNode,
  onHighlightRelated, onClearHighlight, onPositionChange,
}: NodeInfoCardProps) {
  const [editing, setEditing] = useState(false)
  const [aiInstruction, setAiInstruction] = useState('')
  const [aiPanelOpen, setAiPanelOpen] = useState(false)
  const [dragPos, setDragPos] = useState(position)
  const [isDragging, setIsDragging] = useState(false)
  const dragRef = useRef<{ startX: number; startY: number; startLeft: number; startTop: number } | null>(null)
  const cardRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    setDragPos(position)
    setEditing(false)
    setAiPanelOpen(false)
    setAiInstruction('')
  }, [data.nodeId, position])

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (cardRef.current && !cardRef.current.contains(e.target as Node)) {
        onClose()
      }
    }
    const timer = setTimeout(() => {
      document.addEventListener('mousedown', handleClickOutside)
    }, 100)
    return () => {
      clearTimeout(timer)
      document.removeEventListener('mousedown', handleClickOutside)
    }
  }, [onClose])

  useEffect(() => {
    if (!isDragging) return
    const handleMouseMove = (e: MouseEvent) => {
      if (!dragRef.current) return
      const dx = e.clientX - dragRef.current.startX
      const dy = e.clientY - dragRef.current.startY
      const newPos = {
        x: Math.max(0, dragRef.current.startLeft + dx),
        y: Math.max(0, dragRef.current.startTop + dy),
      }
      setDragPos(newPos)
    }
    const handleMouseUp = () => {
      setIsDragging(false)
      dragRef.current = null
      if (onPositionChange) onPositionChange(dragPos)
    }
    window.addEventListener('mousemove', handleMouseMove)
    window.addEventListener('mouseup', handleMouseUp)
    return () => {
      window.removeEventListener('mousemove', handleMouseMove)
      window.removeEventListener('mouseup', handleMouseUp)
    }
  }, [isDragging, dragPos, onPositionChange])

  const handleHeaderMouseDown = useCallback((e: React.MouseEvent) => {
    if ((e.target as HTMLElement).closest('button')) return
    setIsDragging(true)
    dragRef.current = {
      startX: e.clientX,
      startY: e.clientY,
      startLeft: dragPos.x,
      startTop: dragPos.y,
    }
  }, [dragPos.x, dragPos.y])

  const color = TYPE_COLORS[data.nodeType] || '#6b7280'
  const icon = TYPE_ICONS[data.nodeType] || '📌'

  return (
    <div
      ref={cardRef}
      className="absolute z-50 w-[320px] bg-white dark:bg-slate-800 rounded-2xl shadow-2xl border border-gray-200 dark:border-slate-700 overflow-hidden"
      style={{ left: dragPos.x, top: dragPos.y, cursor: isDragging ? 'grabbing' : 'default' }}
      onMouseEnter={() => onHighlightRelated(data.nodeId)}
      onMouseLeave={onClearHighlight}
    >
      <div
        className="flex items-center justify-between px-4 py-3 sticky top-0 z-10 cursor-grab active:cursor-grabbing select-none"
        style={{ background: `linear-gradient(135deg, ${color}12, ${color}06)` }}
        onMouseDown={handleHeaderMouseDown}
      >
        <div className="flex items-center gap-2">
          <span className="text-xl">{icon}</span>
          <div>
            <div className="text-sm font-bold">{data.title}</div>
            <div className="text-[10px] opacity-50">{data.subtitle}</div>
          </div>
        </div>
        <Button type="text" size="small" icon={<CloseOutlined />} onClick={onClose} />
      </div>

      <div className="px-4 py-2 space-y-2 max-h-[200px] overflow-auto">
        {data.fields.map((field, i) => (
          field.value && (
            <div key={i}>
              <div className="text-[10px] font-medium opacity-40 mb-0.5">{field.label}</div>
              <p className="text-xs leading-relaxed opacity-80 m-0">{field.value}</p>
            </div>
          )
        ))}
      </div>

      {data.stats.length > 0 && (
        <>
          <Divider className="!my-1" />
          <div className="flex px-4 py-1">
            {data.stats.map((stat, i) => (
              <div
                key={i}
                className={`flex-1 text-center ${i < data.stats.length - 1 ? 'border-r border-gray-100 dark:border-slate-700' : ''} ${stat.onClick ? 'cursor-pointer hover:bg-gray-50 dark:hover:bg-slate-700 rounded-md' : ''}`}
                onClick={stat.onClick}
              >
                <div className="text-sm font-bold" style={{ color }}>{stat.value}</div>
                <div className="text-[9px] opacity-40">{stat.label}</div>
              </div>
            ))}
          </div>
        </>
      )}

      {data.relatedItems.length > 0 && (
        <>
          <Divider className="!my-1" />
          <div className="px-4 py-1">
            <div className="text-[10px] font-medium opacity-40 mb-1">关联项</div>
            <div className="flex flex-wrap gap-1">
              {data.relatedItems.slice(0, 8).map((item, i) => (
                <Tag
                  key={i}
                  color={(TYPE_COLORS[item.type] || '#6b7280').slice(1)}
                  className="!text-[10px] cursor-pointer hover:scale-105 transition-transform"
                  onClick={() => onNavigateToNode(item.id)}
                >
                  {TYPE_ICONS[item.type] || '📌'} {item.label}
                </Tag>
              ))}
              {data.relatedItems.length > 8 && (
                <Tag className="!text-[10px] opacity-50">+{data.relatedItems.length - 8}更多</Tag>
              )}
            </div>
          </div>
        </>
      )}

      <div className="border-t border-gray-100 dark:border-slate-700 px-4 py-2">
        {aiPanelOpen ? (
          <div className="space-y-2">
            <TextArea
              size="small" rows={2} value={aiInstruction}
              onChange={e => setAiInstruction(e.target.value)}
              placeholder="AI修改方向..."
              className="text-xs"
            />
            <div className="flex justify-end gap-2">
              <Button size="small" onClick={() => setAiPanelOpen(false)}>取消</Button>
              <Button size="small" type="primary" icon={<RobotOutlined />}
                onClick={() => {
                  onAIGenerate(data.nodeType, data.nodeId, aiInstruction)
                  setAiPanelOpen(false)
                  setAiInstruction('')
                }}
              >AI 优化</Button>
            </div>
          </div>
        ) : (
          <Space className="w-full justify-end">
            <Button size="small" icon={<EditOutlined />}
              onClick={() => onEdit(data.nodeType, data.nodeId)}>编辑</Button>
            <Button size="small" type="primary" ghost icon={<RobotOutlined />}
              onClick={() => setAiPanelOpen(true)}>AI 优化</Button>
          </Space>
        )}
      </div>
    </div>
  )
}