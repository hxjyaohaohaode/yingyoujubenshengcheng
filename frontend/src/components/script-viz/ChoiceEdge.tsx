import { memo } from 'react'
import { BaseEdge, EdgeProps, getBezierPath, EdgeLabelRenderer } from '@xyflow/react'

export interface ChoiceEdgeData {
  strength: number
  edgeType: string
  label?: string
  isHighlighted?: boolean
}

const TYPE_COLORS: Record<string, string> = {
  branch: '#8b5cf6',
  choice_a: '#3b82f6',
  choice_b: '#f59e0b',
  choice_c: '#10b981',
  ending_a: '#ec4899',
  ending_b: '#ef4444',
  consequence: '#6366f1',
  sequential: '#3b82f6',
}

function ChoiceEdge({
  id, sourceX, sourceY, targetX, targetY,
  sourcePosition, targetPosition, data, markerEnd, selected,
}: EdgeProps) {
  const edgeData = (data as unknown as ChoiceEdgeData) || { strength: 3, edgeType: 'branch' }
  const isHighlighted = edgeData.isHighlighted || selected

  const [edgePath, labelX, labelY] = getBezierPath({
    sourceX, sourceY, sourcePosition,
    targetX, targetY, targetPosition,
    curvature: 0.35,
  })

  const maxWidth = 6
  const minWidth = 1.5
  const strokeWidth = Math.min(maxWidth, Math.max(minWidth, ((edgeData.strength || 3) / 10) * maxWidth))
  const baseColor = TYPE_COLORS[edgeData.edgeType] || '#8b5cf6'

  return (
    <>
      <BaseEdge
        id={id}
        path={edgePath}
        className="transition-all duration-300"
        style={{
          stroke: isHighlighted ? baseColor : `${baseColor}60`,
          strokeWidth: isHighlighted ? strokeWidth + 1.5 : strokeWidth,
          strokeDasharray: edgeData.edgeType.startsWith('choice_') || edgeData.edgeType.startsWith('ending_') ? '6 4' : undefined,
          strokeOpacity: isHighlighted ? 1 : 0.55,
          filter: isHighlighted ? `drop-shadow(0 0 6px ${baseColor}70)` : undefined,
          transition: 'all 0.3s ease',
        }}
        markerEnd={markerEnd}
      />

      {edgeData.label && (
        <EdgeLabelRenderer>
          <div
            className="absolute pointer-events-none text-[9px] px-1.5 py-0.5 rounded-full shadow-sm whitespace-nowrap"
            style={{
              transform: `translate(-50%, -50%) translate(${labelX}px, ${labelY}px)`,
              background: isHighlighted ? baseColor : 'white',
              color: isHighlighted ? 'white' : baseColor,
              border: `1px solid ${baseColor}40`,
            }}
          >
            {edgeData.label}
          </div>
        </EdgeLabelRenderer>
      )}
    </>
  )
}

export default memo(ChoiceEdge)