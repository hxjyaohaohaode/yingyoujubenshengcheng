import { Tooltip } from 'antd'

interface TimelineNode {
  label: string
  chapter: string
  completed: boolean
  isCurrent?: boolean
}

interface TimelineProps {
  nodes: TimelineNode[]
  className?: string
}

export default function Timeline({ nodes, className = '' }: TimelineProps) {
  if (nodes.length === 0) return null

  return (
    <div className={`flex items-center ${className}`}>
      {nodes.map((node, i) => (
        <div key={i} className="flex items-center flex-1 last:flex-none">
          <Tooltip title={`${node.chapter} - ${node.label}${node.isCurrent ? ' (当前)' : ''}`}>
            <div className="flex flex-col items-center cursor-pointer group">
              <div
                className={`
                  w-3 h-3 rounded-full transition-all duration-200
                  ${node.completed ? 'bg-primary-500 shadow-sm shadow-primary-300' : 'border-2 border-gray-300 dark:border-slate-500 bg-white dark:bg-slate-800'}
                  ${node.isCurrent ? 'ring-2 ring-primary-300 ring-offset-2 dark:ring-offset-slate-800' : ''}
                  group-hover:scale-125
                `}
              />
              <span className={`
                text-xs mt-1 whitespace-nowrap
                ${node.isCurrent ? 'text-primary-600 dark:text-primary-400 font-semibold' : 'text-gray-400 dark:text-gray-500'}
              `}>
                {node.label}
              </span>
            </div>
          </Tooltip>
          {i < nodes.length - 1 && (
            <div className={`
              flex-1 h-0.5 mx-1
              ${node.completed ? 'bg-primary-400' : 'bg-gray-200 dark:bg-slate-600'}
            `} />
          )}
        </div>
      ))}
    </div>
  )
}
