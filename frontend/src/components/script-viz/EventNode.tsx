import { memo } from 'react'
import { Handle, Position, NodeProps } from '@xyflow/react'

export interface EventNodeData {
  label: string
  event_type: string
  emotion_impact: number
  chapter_number: number | null
  related_scene: string | null
}

const EVENT_COLORS: Record<string, string> = {
  plot_twist: '#ef4444',
  climax: '#f59e0b',
  setback: '#8b5cf6',
  revelation: '#ec4899',
  turning_point: '#6366f1',
  resolution: '#10b981',
}

const EVENT_LABELS: Record<string, string> = {
  plot_twist: '剧情反转',
  climax: '高潮',
  setback: '挫折',
  revelation: '揭示',
  turning_point: '转折',
  resolution: '结局',
}

function EventNode({ data, selected }: NodeProps) {
  const nodeData = data as unknown as EventNodeData
  const color = EVENT_COLORS[nodeData.event_type] || '#ef4444'

  return (
    <div
      className={`
        relative rounded-lg border-2 p-3 min-w-[160px] max-w-[190px]
        bg-white dark:bg-slate-800 shadow-lg transition-all duration-200
        ${selected ? 'ring-3 ring-offset-2 scale-105' : 'hover:scale-102 hover:shadow-xl'}
        ${selected ? 'animate-pulse' : ''}
      `}
      style={{
        borderColor: selected ? color : `${color}60`,
        boxShadow: selected ? `0 0 25px ${color}50` : `0 0 8px ${color}20`,
      }}
    >
      <Handle type="target" position={Position.Top} className="!w-3 !h-3 !border-2 !bg-white" style={{ borderColor: color }} />
      <Handle type="source" position={Position.Bottom} className="!w-3 !h-3 !border-2 !bg-white" style={{ borderColor: color }} />

      <div className="flex items-center gap-2 mb-1">
        <span className="text-lg">⚡</span>
        <span className="text-sm font-bold truncate" style={{ color }}>{nodeData.label}</span>
      </div>

      <div className="text-[10px] opacity-50 mb-1">
        {EVENT_LABELS[nodeData.event_type] || nodeData.event_type}
      </div>

      <div className="flex items-center gap-2">
        <div className="flex items-center gap-1">
          <div className="w-1.5 h-1.5 rounded-full" style={{ background: color }} />
          <span className="text-[10px] font-bold" style={{ color }}>{nodeData.emotion_impact}</span>
        </div>
        {nodeData.chapter_number && (
          <span className="text-[10px] opacity-40">Ch.{nodeData.chapter_number}</span>
        )}
      </div>
    </div>
  )
}

export default memo(EventNode)
