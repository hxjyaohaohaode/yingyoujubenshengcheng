import { Tooltip } from 'antd'

type EmotionLevel = 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10

interface EmotionChartProps {
  level: number
  target?: number
  size?: 'sm' | 'md'
  showLabel?: boolean
}

const labels: Record<number, string> = {
  1: '极低', 2: '低', 3: '较低',
  4: '中低', 5: '中等',
  6: '中高', 7: '较高', 8: '高',
  9: '极高', 10: '巅峰',
}

function getBarColor(level: number): string {
  if (level <= 3) return 'emotion-bar-low'
  if (level <= 5) return 'emotion-bar-mid'
  if (level <= 8) return 'emotion-bar-high'
  return 'emotion-bar-peak'
}

function getTagColor(level: number): string {
  if (level <= 3) return '#3b82f6'
  if (level <= 5) return '#8b5cf6'
  if (level <= 8) return '#f59e0b'
  return '#ef4444'
}

export default function EmotionChart({ level, target, size = 'md', showLabel = true }: EmotionChartProps) {
  const safeLevel = Math.max(1, Math.min(10, Math.round(level)))
  const percent = (safeLevel / 10) * 100
  const barClass = getBarColor(safeLevel)
  const h = size === 'sm' ? 'h-1.5' : 'h-2.5'

  return (
    <div className="flex items-center gap-2 w-full">
      {showLabel && (
        <span
          className="text-xs font-semibold min-w-[28px] text-center px-1.5 py-0.5 rounded"
          style={{ color: getTagColor(safeLevel), background: `${getTagColor(safeLevel)}18` }}
        >
          {safeLevel}
        </span>
      )}
      <Tooltip title={`情感强度: ${safeLevel}/10 ${target ? `(目标: ${target}/10)` : ''}`}>
        <div className={`flex-1 relative bg-gray-200 dark:bg-slate-600 rounded-full overflow-hidden ${h}`}>
          <div
            className={`${barClass} ${h} rounded-full transition-all duration-500`}
            style={{ width: `${percent}%` }}
          />
          {target !== undefined && (
            <div
              className="absolute top-0 w-0.5 h-full bg-white dark:bg-gray-300"
              style={{ left: `${(target / 10) * 100}%` }}
            />
          )}
        </div>
      </Tooltip>
      {showLabel && (
        <span className="text-xs text-gray-400 dark:text-gray-500 w-12 text-right">
          {labels[safeLevel]}
        </span>
      )}
    </div>
  )
}
