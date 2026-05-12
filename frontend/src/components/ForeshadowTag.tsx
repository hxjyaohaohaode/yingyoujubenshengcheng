import { Tag } from 'antd'

type ForeshadowOp = 'plant' | 'reinforce' | 'reveal' | 'clue'

interface ForeshadowTagProps {
  code: string
  op: ForeshadowOp
  content?: string
  onClick?: () => void
}

const config: Record<ForeshadowOp, { label: string; color: string; icon: string }> = {
  plant: { label: '植入', color: '#10b981', icon: '🌱' },
  reinforce: { label: '强化', color: '#3b82f6', icon: '🔄' },
  reveal: { label: '回收', color: '#f59e0b', icon: '💡' },
  clue: { label: '线索', color: '#8b5cf6', icon: '⚡' },
}

export default function ForeshadowTag({ code, op, content, onClick }: ForeshadowTagProps) {
  const cfg = config[op]

  return (
    <Tag
      color={cfg.color}
      className="cursor-pointer hover:opacity-80 transition-opacity px-2 py-0.5 text-xs"
      onClick={onClick}
    >
      <span className="mr-1">{cfg.icon}</span>
      <span className="font-semibold">{code}</span>
      <span className="mx-1 text-white/70">·</span>
      <span>{cfg.label}</span>
      {content && <span className="ml-1 text-white/80">: {content}</span>}
    </Tag>
  )
}
