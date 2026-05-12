import { useState, useEffect } from 'react'
import { Button, Tag, Divider, Space, Input, Spin } from 'antd'
import {
  EditOutlined, RobotOutlined, CloseOutlined, SaveOutlined,
  PlayCircleOutlined, NodeIndexOutlined, ThunderboltOutlined,
} from '@ant-design/icons'

const { TextArea } = Input

export type CardNodeType = 'character' | 'scene' | 'foreshadow' | 'event'

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
}

export default function NodeInfoCard({
  data,
  position,
  onClose,
  onEdit,
  onAIGenerate,
  onNavigateToNode,
  onHighlightRelated,
  onClearHighlight,
}: NodeInfoCardProps) {
  const [editing, setEditing] = useState(false)
  const [aiInstruction, setAiInstruction] = useState('')
  const [aiPanelOpen, setAiPanelOpen] = useState(false)

  useEffect(() => {
    setEditing(false)
    setAiPanelOpen(false)
    setAiInstruction('')
  }, [data.nodeId])

  const typeIcons: Record<string, string> = {
    character: '🎭',
    scene: '🎬',
    foreshadow: '🎯',
    event: '⚡',
  }

  const typeColors: Record<string, string> = {
    character: '#6366f1',
    scene: '#f59e0b',
    foreshadow: '#10b981',
    event: '#ef4444',
  }

  return (
    <div
      className="absolute z-50 w-[320px] bg-white dark:bg-slate-800 rounded-2xl shadow-2xl border border-gray-200 dark:border-slate-700 overflow-hidden animate-in slide-in-from-bottom-2"
      style={{
        left: position.x,
        top: position.y,
      }}
      onMouseEnter={() => onHighlightRelated(data.nodeId)}
      onMouseLeave={onClearHighlight}
    >
      <div className="flex items-center justify-between px-4 py-3 sticky top-0 z-10"
        style={{ background: `linear-gradient(135deg, ${typeColors[data.nodeType]}12, ${typeColors[data.nodeType]}06)` }}>
        <div className="flex items-center gap-2">
          <span className="text-xl">{typeIcons[data.nodeType]}</span>
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
                <div className="text-sm font-bold" style={{ color: typeColors[data.nodeType] }}>
                  {stat.value}
                </div>
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
                  color={typeColors[item.type].slice(1)}
                  className="!text-[10px] cursor-pointer hover:scale-105 transition-transform"
                  onClick={() => onNavigateToNode(item.id)}
                >
                  {typeIcons[item.type]} {item.label}
                </Tag>
              ))}
            </div>
          </div>
        </>
      )}

      <div className="border-t border-gray-100 dark:border-slate-700 px-4 py-2">
        {aiPanelOpen ? (
          <div className="space-y-2">
            <TextArea
              size="small"
              rows={2}
              value={aiInstruction}
              onChange={e => setAiInstruction(e.target.value)}
              placeholder="输入你的修改方向，如：让这个角色性格更加阴暗..."
              className="text-xs"
            />
            <div className="flex justify-end gap-2">
              <Button size="small" onClick={() => setAiPanelOpen(false)}>取消</Button>
              <Button
                size="small" type="primary" icon={<RobotOutlined />}
                onClick={() => {
                  onAIGenerate(data.nodeType, data.nodeId, aiInstruction)
                  setAiPanelOpen(false)
                  setAiInstruction('')
                }}
              >
                AI 优化
              </Button>
            </div>
          </div>
        ) : (
          <Space className="w-full justify-end">
            <Button
              size="small" icon={<EditOutlined />}
              onClick={() => onEdit(data.nodeType, data.nodeId)}
            >
              编辑
            </Button>
            <Button
              size="small" type="primary" ghost icon={<RobotOutlined />}
              onClick={() => setAiPanelOpen(true)}
            >
              AI 优化
            </Button>
          </Space>
        )}
      </div>
    </div>
  )
}
