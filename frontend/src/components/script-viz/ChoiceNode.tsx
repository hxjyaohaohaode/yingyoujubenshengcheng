import { memo } from 'react'
import { Handle, Position, NodeProps } from '@xyflow/react'

export interface ChoiceNodeData {
  label: string
  choiceType: 'branch' | 'ending' | 'decision'
  optionCount: number
  isHighlighted: boolean
  chapterInfo?: string
}

const TYPE_COLORS: Record<string, string> = {
  branch: '#8b5cf6',
  ending: '#ec4899',
  decision: '#f59e0b',
}

const TYPE_LABELS: Record<string, string> = {
  branch: '分支点',
  ending: '结局',
  decision: '决策',
}

const TYPE_ICONS: Record<string, string> = {
  branch: '[分支]',
  ending: '[结局]',
  decision: '决策',
}

function ChoiceNode({ data, selected }: NodeProps) {
  const nodeData = data as unknown as ChoiceNodeData
  const color = TYPE_COLORS[nodeData.choiceType] || '#8b5cf6'
  const isHighlighted = nodeData.isHighlighted || selected

  return (
    <div
      className={`
        relative rounded-lg border-2 p-0 min-w-[150px] max-w-[190px] overflow-hidden
        bg-white dark:bg-slate-800 shadow-lg transition-all duration-300
        ${isHighlighted ? 'ring-4 ring-offset-2 scale-110' : 'hover:scale-105 hover:shadow-xl'}
        ${isHighlighted ? 'animate-pulse' : ''}
      `}
      style={{
        borderColor: isHighlighted ? color : `${color}80`,
        boxShadow: isHighlighted
          ? `0 0 25px ${color}60, 0 0 60px ${color}20`
          : `0 0 10px ${color}15`,
      }}
    >
      <Handle type="target" position={Position.Top} className="!w-3 !h-3 !border-2 !bg-white" style={{ borderColor: color }} />
      <Handle type="source" position={Position.Bottom} className="!w-3 !h-3 !border-2 !bg-white" style={{ borderColor: color }} />

      <div className="flex items-center gap-2 px-3 py-2.5" style={{ background: `linear-gradient(135deg, ${color}20, ${color}08)` }}>
        <div
          className="w-9 h-9 rounded-full flex items-center justify-center text-white text-sm font-bold shrink-0 shadow-sm"
          style={{ background: `linear-gradient(135deg, ${color}, ${color}cc)` }}
        >
          {TYPE_ICONS[nodeData.choiceType]}
        </div>
        <div className="min-w-0 flex-1">
          <div className="text-sm font-bold truncate" style={{ color }}>{nodeData.label}</div>
          <div className="text-[10px] opacity-50">{TYPE_LABELS[nodeData.choiceType]}</div>
        </div>
      </div>

      <div className="flex items-center justify-between px-3 py-2">
        <div className="flex items-center gap-1.5">
          {Array.from({ length: nodeData.optionCount }).map((_, i) => (
            <div
              key={i}
              className="w-2 h-2 rounded-full"
              style={{
                backgroundColor: isHighlighted ? color : `${color}50`,
                animationDelay: `${i * 0.2}s`,
              }}
            />
          ))}
          <span className="text-[10px] opacity-60 ml-1">{nodeData.optionCount}选项</span>
        </div>
        {nodeData.chapterInfo && (
          <span className="text-[9px] opacity-40">{nodeData.chapterInfo}</span>
        )}
      </div>

      {isHighlighted && (
        <div
          className="absolute inset-0 rounded-lg pointer-events-none"
          style={{
            animation: 'choicePulse 2s ease-in-out infinite',
            border: `2px solid ${color}`,
            opacity: 0.3,
          }}
        />
      )}
    </div>
  )
}

export default memo(ChoiceNode)