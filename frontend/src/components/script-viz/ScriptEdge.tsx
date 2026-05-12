import { memo } from 'react'
import {
  BaseEdge,
  EdgeProps,
  getBezierPath,
  EdgeLabelRenderer,
} from '@xyflow/react'

export interface ScriptEdgeData {
  strength: number
  edgeType: string
  label?: string
}

const EDGE_COLORS: Record<string, string> = {
  sequential: '#3b82f6',
  appears_in: '#8b5cf6',
  related: '#10b981',
  friend: '#10b981',
  enemy: '#ef4444',
  lover: '#ec4899',
  family: '#f59e0b',
  rival: '#ef4444',
  planted_in: '#6366f1',
  revealed_in: '#f59e0b',
  depends_on: '#8b5cf6',
  enables: '#10b981',
}

function ScriptEdge({
  id,
  sourceX,
  sourceY,
  targetX,
  targetY,
  sourcePosition,
  targetPosition,
  data,
  markerEnd,
  selected,
}: EdgeProps) {
  const edgeData = (data as unknown as ScriptEdgeData) || { strength: 3, edgeType: 'related' }
  const [edgePath, labelX, labelY] = getBezierPath({
    sourceX, sourceY, sourcePosition,
    targetX, targetY, targetPosition,
    curvature: 0.3,
  })

  const maxWidth = 8
  const minWidth = 1
  const strokeWidth = Math.min(maxWidth, Math.max(minWidth, (edgeData.strength / 10) * maxWidth))

  const baseColor = EDGE_COLORS[edgeData.edgeType] || '#6b7280'

  const dashArray = edgeData.edgeType === 'planted_in' || edgeData.edgeType === 'revealed_in'
    ? '6 4'
    : undefined

  return (
    <>
      <BaseEdge
        id={id}
        path={edgePath}
        className="transition-all duration-300"
        style={{
          stroke: selected ? baseColor : `${baseColor}80`,
          strokeWidth,
          strokeDasharray: dashArray,
          strokeOpacity: selected ? 1 : 0.7,
          filter: selected ? `drop-shadow(0 0 4px ${baseColor}60)` : undefined,
        }}
        markerEnd={markerEnd}
      />

      {edgeData.label && (
        <EdgeLabelRenderer>
          <div
            className="absolute pointer-events-none text-[9px] px-1.5 py-0.5 rounded-full bg-white dark:bg-slate-800 border border-gray-200 dark:border-slate-600 shadow-sm whitespace-nowrap"
            style={{
              transform: `translate(-50%, -50%) translate(${labelX}px, ${labelY}px)`,
            }}
          >
            {edgeData.label}
          </div>
        </EdgeLabelRenderer>
      )}
    </>
  )
}

export default memo(ScriptEdge)
