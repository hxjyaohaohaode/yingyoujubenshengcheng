import { memo } from 'react'
import { Handle, Position, NodeProps } from '@xyflow/react'

export interface SceneNodeData {
  label: string
  scene_code: string
  scene_type: string
  location: string
  narration_preview: string
  emotion_level: number
  status: string
  is_wow_moment: boolean
  characterCount: number
  foreshadowCount: number
}

const SCENE_TYPE_LABELS: Record<string, string> = {
  action: '动作', dialogue: '对白', exploration: '探索',
  cutscene: '过场', transition: '过渡', branching: '分支',
  climax: '高潮', resolution: '结局',
}

const SCENE_COLORS: Record<string, string> = {
  action: '#f59e0b', dialogue: '#3b82f6', exploration: '#10b981',
  cutscene: '#8b5cf6', transition: '#6b7280', branching: '#ec4899',
  climax: '#ef4444', resolution: '#6366f1',
}

const STATUS_COLORS: Record<string, string> = {
  draft: '#d1d5db', in_review: '#f59e0b', approved: '#10b981',
  passed: '#10b981', final: '#6366f1', rejected: '#ef4444',
}

function SceneNode({ data, selected }: NodeProps) {
  const nodeData = data as unknown as SceneNodeData
  const color = SCENE_COLORS[nodeData.scene_type] || '#6b7280'
  const statusColor = STATUS_COLORS[nodeData.status] || '#d1d5db'

  return (
    <div
      className={`
        relative rounded-xl border-2 p-0 min-w-[180px] max-w-[220px] overflow-hidden
        bg-white dark:bg-slate-800 shadow-lg transition-all duration-200
        ${selected ? 'ring-3 ring-offset-2 scale-105' : 'hover:scale-102 hover:shadow-xl'}
      `}
      style={{ borderColor: selected ? color : `${color}40`, boxShadow: selected ? `0 0 20px ${color}40` : undefined }}
    >
      <Handle type="target" position={Position.Top} className="!w-3 !h-3 !border-2 !bg-white" style={{ borderColor: color }} />
      <Handle type="source" position={Position.Bottom} className="!w-3 !h-3 !border-2 !bg-white" style={{ borderColor: color }} />

      <div className="flex items-center justify-between px-3 py-2.5" style={{ background: `linear-gradient(135deg, ${color}18, ${color}08)` }}>
        <div>
          <div className="text-xs opacity-40 font-mono">{nodeData.scene_code}</div>
          <div className="text-sm font-bold truncate" style={{ color }}>{nodeData.label}</div>
        </div>
        <div className="flex flex-col items-end gap-1">
          <div className="text-[9px] px-1.5 py-0.5 rounded-full font-medium" style={{ background: `${statusColor}20`, color: statusColor }}>
            {nodeData.status}
          </div>
          {nodeData.is_wow_moment && (
            <div className="text-[9px] animate-pulse">⚡</div>
          )}
        </div>
      </div>

      <div className="px-3 py-1.5">
        {nodeData.narration_preview && (
          <p className="text-[10px] leading-tight opacity-60 line-clamp-2">{nodeData.narration_preview}</p>
        )}
        {nodeData.location && (
          <div className="text-[10px] mt-1 opacity-40">📍 {nodeData.location}</div>
        )}
      </div>

      <div className="flex border-t border-gray-100 dark:border-slate-700">
        <div className="flex-1 px-2 py-1.5 text-center">
          <div className="flex items-center justify-center gap-1">
            <span className="text-[10px] font-bold" style={{ color }}>{nodeData.emotion_level}</span>
            <span className="text-[9px] opacity-40">/10</span>
          </div>
          <div className="text-[9px] opacity-40">情感</div>
        </div>
        <div className="flex-1 px-2 py-1.5 text-center border-l border-gray-100 dark:border-slate-700">
          <div className="text-[11px] font-bold" style={{ color }}>{nodeData.characterCount}</div>
          <div className="text-[9px] opacity-40">角色</div>
        </div>
      </div>
    </div>
  )
}

export default memo(SceneNode)
