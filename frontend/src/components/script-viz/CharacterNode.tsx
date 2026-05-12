import { memo } from 'react'
import { Handle, Position, NodeProps } from '@xyflow/react'

export interface CharacterNodeData {
  label: string
  role_type: string
  core_goal: string
  core_fear: string
  surface_image: string | null
  arc_description: string | null
  status: string
  sceneCount: number
  relationCount: number
  foreshadowCount: number
}

const ROLE_COLORS: Record<string, string> = {
  protagonist: '#6366f1',
  antagonist: '#ef4444',
  love_interest: '#ec4899',
  rival: '#f59e0b',
  mentor: '#8b5cf6',
  sidekick: '#10b981',
  supporting: '#6b7280',
  cameo: '#9ca3af',
}

const ROLE_LABELS: Record<string, string> = {
  protagonist: '主角', antagonist: '反派', love_interest: '女主',
  rival: '对手', mentor: '导师', sidekick: '伙伴',
  supporting: '配角', cameo: '客串',
}

function CharacterNode({ data, selected }: NodeProps) {
  const nodeData = data as unknown as CharacterNodeData
  const color = ROLE_COLORS[nodeData.role_type] || '#6b7280'
  const roleLabel = ROLE_LABELS[nodeData.role_type] || nodeData.role_type

  return (
    <div
      className={`
        relative rounded-2xl border-2 p-0 min-w-[180px] max-w-[220px] overflow-hidden
        bg-white dark:bg-slate-800 shadow-lg transition-all duration-200
        ${selected ? 'ring-3 ring-offset-2 scale-105' : 'hover:scale-102 hover:shadow-xl'}
      `}
      style={{ borderColor: selected ? color : `${color}40`, boxShadow: selected ? `0 0 20px ${color}40` : undefined }}
    >
      <Handle type="target" position={Position.Top} className="!w-3 !h-3 !border-2 !bg-white" style={{ borderColor: color }} />
      <Handle type="source" position={Position.Bottom} className="!w-3 !h-3 !border-2 !bg-white" style={{ borderColor: color }} />

      <div className="flex items-center gap-2 px-3 py-2.5" style={{ background: `linear-gradient(135deg, ${color}18, ${color}08)` }}>
        <div
          className="w-9 h-9 rounded-xl flex items-center justify-center text-white text-sm font-bold shrink-0 shadow-sm"
          style={{ background: `linear-gradient(135deg, ${color}, ${color}cc)` }}
        >
          {nodeData.label[0]}
        </div>
        <div className="min-w-0 flex-1">
          <div className="text-sm font-bold truncate" style={{ color }}>{nodeData.label}</div>
          <div className="text-[10px] opacity-60">{roleLabel}</div>
        </div>
      </div>

      <div className="px-3 py-1.5 space-y-0.5">
        {nodeData.core_goal && (
          <div className="text-[10px] leading-tight">
            <span className="opacity-40">动机:</span>
            <span className="ml-1 opacity-70 line-clamp-1">{nodeData.core_goal}</span>
          </div>
        )}
        {nodeData.core_fear && (
          <div className="text-[10px] leading-tight">
            <span className="opacity-40">恐惧:</span>
            <span className="ml-1 opacity-70 line-clamp-1">{nodeData.core_fear}</span>
          </div>
        )}
      </div>

      <div className="flex border-t border-gray-100 dark:border-slate-700">
        <div className="flex-1 px-2 py-1 text-center border-r border-gray-100 dark:border-slate-700">
          <div className="text-[11px] font-bold" style={{ color }}>{nodeData.sceneCount}</div>
          <div className="text-[9px] opacity-40">场景</div>
        </div>
        <div className="flex-1 px-2 py-1 text-center border-r border-gray-100 dark:border-slate-700">
          <div className="text-[11px] font-bold" style={{ color }}>{nodeData.relationCount}</div>
          <div className="text-[9px] opacity-40">关联</div>
        </div>
        <div className="flex-1 px-2 py-1 text-center">
          <div className="text-[11px] font-bold" style={{ color }}>{nodeData.foreshadowCount}</div>
          <div className="text-[9px] opacity-40">伏笔</div>
        </div>
      </div>
    </div>
  )
}

export default memo(CharacterNode)
