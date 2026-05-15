import React, { useState, useRef, useEffect, useCallback } from 'react'
import { Input, Button, Spin, Tag, Typography, Card, Space, Tooltip } from 'antd'
import { GlobalOutlined, SearchOutlined, LinkOutlined, LoadingOutlined, CheckCircleOutlined, ClearOutlined } from '@ant-design/icons'
import { searchApi } from '../api/client'

const { Text, Paragraph, Title } = Typography

type SearchPhase = 'idle' | 'searching' | 'organizing' | 'streaming' | 'complete' | 'error'

interface SearchSource {
  title: string
  url: string
  snippet: string
  source: string
}

interface Props {
  projectId: string
}

const STATUS_MAP: Record<SearchPhase, { text: string; icon: React.ReactNode; color: string }> = {
  idle: { text: '', icon: null, color: '' },
  searching: { text: '🔎 AI正在搜集信息...', icon: <LoadingOutlined spin />, color: '#3b82f6' },
  organizing: { text: '📝 AI正在整理信息...', icon: <LoadingOutlined spin />, color: '#f59e0b' },
  streaming: { text: '💬 流式输出信息', icon: <LoadingOutlined spin />, color: '#10b981' },
  complete: { text: '✅ 搜索完成', icon: <CheckCircleOutlined />, color: '#10b981' },
  error: { text: '❌ 搜索出错', icon: null, color: '#ef4444' },
}

const KnowledgeSearch: React.FC<Props> = ({ projectId }) => {
  const [query, setQuery] = useState('')
  const [phase, setPhase] = useState<SearchPhase>('idle')
  const [statusText, setStatusText] = useState('')
  const [streamContent, setStreamContent] = useState('')
  const [sources, setSources] = useState<SearchSource[]>([])
  const [totalTime, setTotalTime] = useState<number | null>(null)
  const [errorMsg, setErrorMsg] = useState('')
  const [searching, setSearching] = useState(false)
  const contentRef = useRef<HTMLDivElement>(null)
  const abortRef = useRef<AbortController | null>(null)

  const resetState = useCallback(() => {
    setPhase('idle')
    setStatusText('')
    setStreamContent('')
    setSources([])
    setTotalTime(null)
    setErrorMsg('')
    setSearching(false)
  }, [])

  const scrollToBottom = useCallback(() => {
    if (contentRef.current) {
      const el = contentRef.current
      el.scrollTop = el.scrollHeight
    }
  }, [])

  useEffect(() => {
    if (phase === 'streaming' || phase === 'complete') {
      scrollToBottom()
    }
  }, [streamContent, phase, scrollToBottom])

  const handleSearch = async () => {
    const trimmed = query.trim()
    if (!trimmed || searching) return
    if (!projectId) return

    resetState()
    setSearching(true)
    setPhase('searching')
    setStatusText('🔎 AI正在搜集信息...')

    const controller = new AbortController()
    abortRef.current = controller

    try {
      const stream = await searchApi.searchStream(projectId, trimmed)
      const reader = stream.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

      const readLoop = async () => {
        while (true) {
          if (controller.signal.aborted) break
          const { done, value } = await reader.read()
          if (done) break

          buffer += decoder.decode(value, { stream: true })
          const lines = buffer.split('\n')
          buffer = lines.pop() || ''

          for (const line of lines) {
            const trimmedLine = line.trim()
            if (!trimmedLine || !trimmedLine.startsWith('data: ')) continue

            const dataStr = trimmedLine.slice(6)
            if (dataStr === '[DONE]') {
              setPhase('complete')
              setStatusText(`✅ 搜索完成${totalTime ? ` (${totalTime}秒)` : ''}`)
              setSearching(false)
              return
            }

            try {
              const event = JSON.parse(dataStr)
              handleSSEEvent(event)
            } catch {
              continue
            }
          }
        }
        setSearching(false)
      }

      await readLoop()
    } catch (err: any) {
      if (err.name === 'AbortError') return

      console.warn('[KnowledgeSearch] SSE流式搜索失败，尝试非流式搜索', err.message)
      try {
        setStatusText('🔎 SSE连接失败，切换到备用搜索...')
        const result = await searchApi.searchQuick(projectId, trimmed)
        if (result.status === 'ok') {
          setStreamContent(result.summary || '未获取到摘要')
          setSources(result.sources || [])
          setPhase('complete')
          setStatusText('✅ 搜索完成（备用模式）')
        } else {
          throw new Error(result.message || '搜索失败')
        }
      } catch (fallbackErr: any) {
        setPhase('error')
        setErrorMsg(fallbackErr.message || '搜索请求失败，请检查后端服务是否运行')
        setStatusText('❌ 搜索出错')
      }
      setSearching(false)
    }
  }

  const handleSSEEvent = (event: any) => {
    const p = event.phase as string

    switch (p) {
      case 'searching':
        setPhase('searching')
        setStatusText(event.text || '🔎 AI正在搜集信息...')
        break

      case 'organizing':
        setPhase('organizing')
        setStatusText(event.text || '📝 AI正在整理信息...')
        break

      case 'sources':
        setSources((event.sources || []) as SearchSource[])
        break

      case 'streaming_start':
        setPhase('streaming')
        setStatusText('💬 流式输出信息')
        break

      case 'streaming':
        setStreamContent(prev => prev + (event.text || ''))
        break

      case 'complete':
        setPhase('complete')
        setTotalTime(event.total_time || null)
        setStatusText(`✅ 搜索完成`)
        break

      case 'error':
        setPhase('error')
        setErrorMsg(event.text || '搜索出错')
        setStatusText('❌ 搜索出错')
        break
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      handleSearch()
    }
  }

  const handleClear = () => {
    if (abortRef.current) {
      abortRef.current.abort()
    }
    setQuery('')
    resetState()
  }

  const phaseDot = (p: SearchPhase) => {
    if (p === phase) {
      return <span className="inline-block w-2 h-2 rounded-full animate-pulse" style={{ backgroundColor: STATUS_MAP[p]?.color || '#6b7280' }} />
    }
    return null
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12, height: '100%' }}>
      <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexShrink: 0 }}>
        <Input
          prefix={<SearchOutlined style={{ color: 'var(--color-muted)' }} />}
          placeholder="输入关键词搜索相关资料（如：越王勾践、卧薪尝胆）"
          value={query}
          onChange={e => setQuery(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={searching}
          allowClear={!searching}
          style={{ flex: 1 }}
        />
        <Tooltip title="联网搜索">
          <Button
            type="primary"
            icon={<GlobalOutlined />}
            onClick={handleSearch}
            loading={searching}
            disabled={!query.trim() || searching}
          >
            搜索
          </Button>
        </Tooltip>
        {phase !== 'idle' && (
          <Button
            icon={<ClearOutlined />}
            onClick={handleClear}
            size="small"
            type="text"
          />
        )}
      </div>

      {phase !== 'idle' && (
        <Card
          size="small"
          style={{
            flex: 1,
            minHeight: 0,
            display: 'flex',
            flexDirection: 'column',
            overflow: 'hidden',
          }}
          styles={{ body: { flex: 1, minHeight: 0, display: 'flex', flexDirection: 'column', overflow: 'hidden', padding: 12 } }}
        >
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 8,
              marginBottom: 8,
              flexShrink: 0,
            }}
          >
            {phaseDot(phase)}
            <Text
              style={{
                color: STATUS_MAP[phase]?.color || '#6b7280',
                fontWeight: 500,
                fontSize: 13,
              }}
            >
              {STATUS_MAP[phase]?.icon}
              <span style={{ marginLeft: 4 }}>{statusText}</span>
            </Text>
            {totalTime && phase === 'complete' && (
              <Tag color="green" style={{ fontSize: 11 }}>
                {totalTime}秒
              </Tag>
            )}
          </div>

          <div
            ref={contentRef}
            style={{
              flex: 1,
              minHeight: 0,
              overflow: 'auto',
              padding: '0 4px',
            }}
          >
            {streamContent && (
              <div style={{ marginBottom: 8 }}>
                <div
                  style={{
                    fontSize: 14,
                    lineHeight: 1.8,
                    whiteSpace: 'pre-wrap',
                    wordBreak: 'break-word',
                  }}
                >
                  {streamContent}
                  {phase === 'streaming' && (
                    <span className="inline-block w-2 h-4 ml-1 bg-blue-500 animate-pulse" />
                  )}
                </div>
              </div>
            )}

            {errorMsg && (
              <div style={{ color: '#ef4444', fontSize: 13, padding: '8px 0' }}>
                {errorMsg}
              </div>
            )}

            {sources.length > 0 && (
              <div
                style={{
                  marginTop: streamContent ? 12 : 0,
                  padding: '8px 0',
                  borderTop: streamContent ? '1px solid var(--color-border, #e5e7eb)' : 'none',
                }}
              >
                <Text type="secondary" style={{ fontSize: 12, fontWeight: 500 }}>
                  📚 信息来源 ({sources.length})
                </Text>
                <div style={{ marginTop: 6, display: 'flex', flexDirection: 'column', gap: 6 }}>
                  {sources.map((s, i) => (
                    <a
                      key={i}
                      href={s.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      style={{
                        display: 'flex',
                        alignItems: 'flex-start',
                        gap: 6,
                        padding: '4px 6px',
                        borderRadius: 4,
                        textDecoration: 'none',
                        fontSize: 12,
                        transition: 'background 0.15s',
                      }}
                      className="hover:bg-gray-50 dark:hover:bg-slate-800"
                    >
                      <LinkOutlined style={{ color: 'var(--color-muted)', marginTop: 2, flexShrink: 0 }} />
                      <div>
                        <div style={{ color: '#3b82f6', fontWeight: 500, lineHeight: 1.4 }}>
                          {s.title}
                        </div>
                        {s.snippet && (
                          <div style={{ color: 'var(--color-muted)', fontSize: 11, lineHeight: 1.4, marginTop: 2 }}>
                            {s.snippet.slice(0, 150)}
                          </div>
                        )}
                        {s.source && (
                          <Tag
                            color={s.source === 'brave' ? 'blue' : s.source === 'duckduckgo' ? 'orange' : 'default'}
                            style={{ fontSize: 10, marginTop: 3 }}
                          >
                            {s.source}
                          </Tag>
                        )}
                      </div>
                    </a>
                  ))}
                </div>
              </div>
            )}

            {phase === 'searching' && !streamContent && sources.length === 0 && (
              <div style={{ textAlign: 'center', padding: '32px 0' }}>
                <Spin indicator={<LoadingOutlined style={{ fontSize: 24, color: '#3b82f6' }} spin />} />
              </div>
            )}
          </div>
        </Card>
      )}
    </div>
  )
}

export default KnowledgeSearch