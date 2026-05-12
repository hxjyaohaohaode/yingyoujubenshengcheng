import { memo } from 'react'
import { Handle, Position, NodeProps } from '@xyflow/react'

export interface ForeshadowNodeData {
  label: string
  fs_code: string
  fs_type: string
  surface_layer: string
  deep_layer: string
  truth_layer: string
  health: string
  current_status: string
  reinforce_count: number
  layer_count: number
}

const HEALTH_COLORS: Record<string, string> = {
  normal: '#10b981',
  warning: '#f59e0b',
  danger: '#ef4444',
}

const HEALTH_LABELS: Record<string, string> = {
  normal: '健康', warning: '关注', danger: '危险',
}

function ForeshadowNode({ data, selected }: NodeProps) {
  const nodeData = data as unknown as ForeshadowNodeData
  const healthColor = HEALTH_COLORS[nodeData.health] || '#6b7280'

  return (
    <div
      className={`
        relative rounded-xl border-2 p-0 min-w-[170px] max-w-[200px] overflow-hidden
        bg-white dark:bg-slate-800 shadow-lg transition-all duration-200
        ${selected ? 'ring-3 ring-offset-2 scale-105' : 'hover:scale-102 hover:shadow-xl'}
      `}
      style={{
        borderColor: selected ? '#10b981' : '#10b98140',
        boxShadow: selected ? '0 0 20px #10b98140' : undefined,
      }}
    >
      <Handle type="target" position={Position.Top} className="!w-3 !h-3 !border-2 !bg-white" style={{ borderColor: '#10b981' }} />
      <Handle type="source" position={Position.Bottom} className="!w-3 !h-3 !border-2 !bg-white" style={{ borderColor: '#10b981' }} />

      <div className="flex items-center justify-between px-3 py-2.5" style={{ background: 'linear-gradient(135deg, #10b98118, #05966908)' }}>
        <div className="min-w-0 flex-1">
          <div className="text-xs opacity-40 font-mono">{nodeData.fs_code}</div>
          <div className="text-sm font-bold truncate text-emerald-600 dark:text-emerald-400">{nodeData.label}</div>
        </div>
        <div className="flex items-center gap-1 shrink-0">
          <div className="w-2 h-2 rounded-full" style={{ background: healthColor }} />
          <span className="text-[9px] opacity-50">{HEALTH_LABELS[nodeData.health]}</span>
        </div>
      </div>

      <div className="px-3 py-1.5 space-y-1">
        <div className="flex items-center gap-1 text-[10px]">
          <div className="w-1.5 h-1.5 rounded-full bg-emerald-200 dark:bg-emerald-800 shrink-0" />
          <span className="opacity-50 line-clamp-1">表层: {nodeData.surface_layer || '未设定'}</span>
        </div>
        <div className="flex items-center gap-1 text-[10px]">
          <div className="w-1.5 h-1.5 rounded-full bg-emerald-400 shrink-0" />
          <span className="opacity-50 line-clamp-1">深层: {nodeData.deep_layer || '未设定'}</span>
        </div>
        <div className="flex items-center gap-1 text-[10px]">
          <div className="w-1.5 h-1.5 rounded-full bg-emerald-600 shrink-0" />
          <span className="opacity-50 line-clamp-1">核心: {nodeData.truth_layer || '未设定'}</span>
        </div>
      </div>

      <div className="flex border-t border-gray-100 dark:border-slate-700">
        <div className="flex-1 px-2 py-1 text-center border-r border-gray-100 dark:border-slate-700">
          <div className="text-[11px] font-bold text-emerald-600 dark:text-emerald-400">{nodeData.reinforce_count}</div>
          <div className="text-[9px] opacity-40">强化</div>
        </div>
        <div className="flex-1 px-2 py-1 text-center">
          <div className="text-[11px] font-bold text-emerald-600 dark:text-emerald-400">{nodeData.layer_count}</div>
          <div className="text-[9px] opacity-40">层级</div>
        </div>
      </div>
    </div>
  )
}

export default memo(ForeshadowNode)
