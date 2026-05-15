import { Tag, Divider } from 'antd'

interface ParsedScene {
  narration?: string
  dialogue?: Array<{ char: string; text: string; subtext?: string }>
  actions?: string[]
  foreshadow_ops?: Array<{ fs_id: string; op: string; content: string }>
  choices?: Array<{ id: string; text: string; consequence: string; next_scene?: string }>
  causal_chain?: {
    preconditions?: string[]
    catalyst?: string
    direct_result?: string
    indirect_result?: string
    far_result?: string
  }
  emotion_level?: number
  suggestions?: string[]
}

function tryParseJson(text: string): ParsedScene | null {
  if (!text || typeof text !== 'string') return null
  const trimmed = text.trim()
  if (!trimmed.startsWith('{') && !trimmed.startsWith('```')) return null
  let cleanText = trimmed
  if (cleanText.startsWith('```')) {
    cleanText = cleanText.replace(/^```(?:json)?\s*\n?/, '').replace(/\n?```\s*$/, '')
  }
  try {
    const parsed = JSON.parse(cleanText)
    if (typeof parsed === 'object' && parsed !== null) return parsed as ParsedScene
    return null
  } catch {
    return null
  }
}

function renderNarrationParagraphs(text: string) {
  if (!text) return null
  const paragraphs = text.split(/\n\n+|\n/).filter(p => p.trim())
  return paragraphs.map((p, i) => {
    const trimmed = p.trim()
    const isBackground = /^(背景|环境|氛围|场景|天气|时间|光影|远处|四周|周围|空气|天色|暮色|晨光|夜色|月光|阳光|雾|雨|雪|风)/.test(trimmed)
      || /^\[.*\]$/.test(trimmed)
      || /^（.*）$/.test(trimmed)
      || trimmed.startsWith('——')
    return (
      <p key={i} className={`mb-3 indent-8 leading-[1.9] ${isBackground ? 'text-gray-400 dark:text-gray-500 italic' : 'text-gray-800 dark:text-gray-200'}`}>
        {trimmed}
      </p>
    )
  })
}

interface NarrationRendererProps {
  content: string
  compact?: boolean
  showMeta?: boolean
}

export default function NarrationRenderer({ content, compact = false, showMeta = true }: NarrationRendererProps) {
  const parsed = tryParseJson(content)

  if (!parsed) {
    return (
      <div className="whitespace-pre-wrap leading-relaxed text-gray-800 dark:text-gray-200">
        {renderNarrationParagraphs(content)}
      </div>
    )
  }

  return (
    <div className="novel-renderer">
      {parsed.narration && (
        <div className="mb-4">
          {renderNarrationParagraphs(parsed.narration)}
        </div>
      )}

      {parsed.dialogue && parsed.dialogue.length > 0 && (
        <div className="mb-4">
          {parsed.dialogue.map((d, i) => (
            <div key={i} className="mb-3">
              <div className="flex items-baseline gap-2">
                <span className="text-sm font-bold text-indigo-600 dark:text-indigo-400 shrink-0">{d.char}</span>
                <span className="text-gray-800 dark:text-gray-200 leading-[1.9]">「{d.text}」</span>
              </div>
              {d.subtext && (
                <div className="ml-8 mt-0.5 text-xs text-gray-400 dark:text-gray-500 italic">
                  〔潜台词：{d.subtext}〕
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {parsed.actions && parsed.actions.length > 0 && (
        <div className="mb-4">
          {parsed.actions.map((a, i) => (
            <p key={i} className="mb-2 indent-8 text-gray-500 dark:text-gray-400 italic leading-[1.9]">
              {a}
            </p>
          ))}
        </div>
      )}

      {showMeta && parsed.foreshadow_ops && parsed.foreshadow_ops.length > 0 && (
        <div className="mb-3">
          <Divider orientation="left" className="!text-xs !text-gray-400 !my-2">伏笔操作</Divider>
          <div className="space-y-1.5">
            {parsed.foreshadow_ops.map((f, i) => {
              const opLabel = f.op === 'plant' ? '植入' : f.op === 'reinforce' ? '强化' : f.op === 'reveal' ? '揭示' : f.op
              const opColor = f.op === 'plant' ? 'blue' : f.op === 'reinforce' ? 'green' : f.op === 'reveal' ? 'orange' : 'default'
              return (
                <div key={i} className="flex items-start gap-2 text-xs">
                  <Tag color={opColor} className="!text-[10px] !leading-tight !m-0 shrink-0">{f.fs_id} {opLabel}</Tag>
                  <span className="text-gray-600 dark:text-gray-400">{f.content}</span>
                </div>
              )
            })}
          </div>
        </div>
      )}

      {showMeta && parsed.choices && parsed.choices.length > 0 && (
        <div className="mb-3">
          <Divider orientation="left" className="!text-xs !text-gray-400 !my-2">分支选择</Divider>
          <div className="space-y-2">
            {parsed.choices.map((c, i) => (
              <div key={i} className="bg-amber-50 dark:bg-amber-900/10 border border-amber-200 dark:border-amber-800 rounded-lg p-2.5">
                <div className="flex items-center gap-2 mb-1">
                  <Tag color="orange" className="!text-[10px] !m-0">选项{c.id}</Tag>
                  <span className="text-sm font-medium text-gray-800 dark:text-gray-200">{c.text}</span>
                </div>
                <div className="text-xs text-gray-500 dark:text-gray-400 ml-12">
                  后果：{c.consequence}
                  {c.next_scene && <span className="text-gray-400 ml-2">→ {c.next_scene}</span>}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {showMeta && parsed.causal_chain && (
        <div className="mb-3">
          <Divider orientation="left" className="!text-xs !text-gray-400 !my-2">因果链</Divider>
          <div className="space-y-1.5 text-xs">
            {parsed.causal_chain.preconditions && parsed.causal_chain.preconditions.length > 0 && (
              <div>
                <span className="text-gray-400 font-medium">前提：</span>
                <span className="text-gray-600 dark:text-gray-400">{parsed.causal_chain.preconditions.join('；')}</span>
              </div>
            )}
            {parsed.causal_chain.catalyst && (
              <div>
                <span className="text-blue-500 font-medium">催化：</span>
                <span className="text-gray-600 dark:text-gray-400">{parsed.causal_chain.catalyst}</span>
              </div>
            )}
            {parsed.causal_chain.direct_result && (
              <div>
                <span className="text-green-500 font-medium">直接结果：</span>
                <span className="text-gray-600 dark:text-gray-400">{parsed.causal_chain.direct_result}</span>
              </div>
            )}
            {parsed.causal_chain.indirect_result && (
              <div>
                <span className="text-purple-500 font-medium">间接结果：</span>
                <span className="text-gray-600 dark:text-gray-400">{parsed.causal_chain.indirect_result}</span>
              </div>
            )}
            {parsed.causal_chain.far_result && (
              <div>
                <span className="text-red-500 font-medium">远期影响：</span>
                <span className="text-gray-600 dark:text-gray-400">{parsed.causal_chain.far_result}</span>
              </div>
            )}
          </div>
        </div>
      )}

      {showMeta && parsed.suggestions && parsed.suggestions.length > 0 && (
        <div className="mb-2">
          <Divider orientation="left" className="!text-xs !text-gray-400 !my-2">创作建议</Divider>
          <div className="space-y-1">
            {parsed.suggestions.map((s, i) => (
              <div key={i} className="text-xs text-gray-500 dark:text-gray-400 flex items-start gap-1.5">
                <span className="text-gray-300 mt-0.5">•</span>
                <span>{s}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {showMeta && parsed.emotion_level != null && (
        <div className="flex items-center gap-2 text-xs text-gray-400 mt-2">
          <span>情感强度：</span>
          <div className="flex gap-0.5">
            {Array.from({ length: 10 }, (_, i) => (
              <div
                key={i}
                className="w-2 h-4 rounded-sm"
                style={{
                  backgroundColor: i < parsed.emotion_level!
                    ? (i < 3 ? '#3b82f6' : i < 5 ? '#8b5cf6' : i < 7 ? '#f59e0b' : '#ef4444')
                    : '#e5e7eb',
                }}
              />
            ))}
          </div>
          <span className="font-bold">{parsed.emotion_level}/10</span>
        </div>
      )}
    </div>
  )
}

export { tryParseJson }
export type { ParsedScene }
