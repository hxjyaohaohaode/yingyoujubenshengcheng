import { useState, useEffect, useCallback } from 'react'
import {
  Card, Button, Tag, Space, App, Input, Select, InputNumber,
  Spin, Empty, Collapse, Popconfirm, Tooltip, Badge, Descriptions,
} from 'antd'
import {
  PlusOutlined, RobotOutlined, EditOutlined, DeleteOutlined,
  ArrowUpOutlined, ArrowDownOutlined, SaveOutlined,
  BookOutlined, BulbOutlined, DownOutlined, RightOutlined,
  UserOutlined, ThunderboltOutlined,
} from '@ant-design/icons'
import { useProjectStore } from '../stores/projectStore'
import { api, chaptersApi, sectionsApi, choicesApi, Chapter, ChapterSection, ChoiceDesign } from '../api/client'
import { eventBus, DataEvents } from '../services/eventBus'

const { TextArea } = Input

interface SectionData {
  id: string
  project_id: string
  chapter_id: string
  section_number: number
  title: string
  word_target: number
  emotion_target: number
  scene_ids: unknown[]
  choices: unknown | null
  foreshadow_tasks: unknown[]
  focus_characters: unknown[]
  branch_type: string
  summary: string
  status: string
}

interface ChapterData {
  id: string
  chapter_number: number
  title: string
  summary: string
  key_turning_points: string[]
  emotion_target: number
  focus_characters: string[]
  foreshadow_tasks: string[]
  worldview_refs: string[]
  status: string
  sections: SectionData[]
}

const STATUS_OPTIONS = [
  { value: 'draft', label: '草稿', color: 'default' },
  { value: 'outlined', label: '已大纲', color: 'blue' },
  { value: 'writing', label: '写作中', color: 'orange' },
  { value: 'done', label: '已完成', color: 'green' },
]

const BRANCH_TYPE_MAP: Record<string, { label: string; color: string }> = {
  exploration: { label: '探索', color: 'blue' },
  decision: { label: '抉择', color: 'red' },
  convergence: { label: '合流', color: 'green' },
}

const MORAL_ALIGNMENT_MAP: Record<string, { label: string; color: string }> = {
  good: { label: '善', color: 'green' },
  neutral: { label: '中', color: 'blue' },
  evil: { label: '恶', color: 'red' },
  gray: { label: '灰', color: 'default' },
}

const FORESHADOW_TYPE_MAP: Record<string, { icon: string; label: string }> = {
  plant: { icon: '🌱', label: '埋设' },
  reinforce: { icon: '🔄', label: '强化' },
  reveal: { icon: '💡', label: '回收' },
}

function getForeshadowTypeIcon(task: unknown): string {
  if (typeof task === 'string') {
    const lower = task.toLowerCase()
    if (lower.includes('埋设') || lower.includes('plant')) return '🌱'
    if (lower.includes('强化') || lower.includes('reinforce')) return '🔄'
    if (lower.includes('回收') || lower.includes('reveal')) return '💡'
    return '🌱'
  }
  if (typeof task === 'object' && task !== null) {
    const t = task as Record<string, unknown>
    const type = String(t.type || t.fs_type || '')
    if (type.includes('plant') || type.includes('埋设')) return '🌱'
    if (type.includes('reinforce') || type.includes('强化')) return '🔄'
    if (type.includes('reveal') || type.includes('回收')) return '💡'
  }
  return '🌱'
}

function countForeshadowByType(tasks: unknown[]): { plant: number; reinforce: number; reveal: number } {
  let plant = 0, reinforce = 0, reveal = 0
  for (const task of tasks) {
    const icon = getForeshadowTypeIcon(task)
    if (icon === '🌱') plant++
    else if (icon === '🔄') reinforce++
    else if (icon === '💡') reveal++
  }
  return { plant, reinforce, reveal }
}

function apiChapterToChapterData(c: Chapter): ChapterData {
  const rawSections = Array.isArray(c.sections) ? c.sections : []
  return {
    id: c.id,
    chapter_number: c.chapter_number,
    title: c.title || `第${c.chapter_number}章`,
    summary: c.summary || '',
    key_turning_points: Array.isArray((c as any).key_turning_points) ? (c as any).key_turning_points : [],
    emotion_target: c.emotion_target || 5,
    focus_characters: Array.isArray((c as any).focus_characters) ? (c as any).focus_characters.map(String) : [],
    foreshadow_tasks: Array.isArray(c.foreshadow_tasks) ? c.foreshadow_tasks.map(String) : [],
    worldview_refs: Array.isArray((c as any).worldview_refs) ? (c as any).worldview_refs.map(String) : [],
    status: c.status,
    sections: rawSections.map((s: ChapterSection) => ({
      id: s.id,
      project_id: s.project_id,
      chapter_id: s.chapter_id,
      section_number: s.section_number,
      title: s.title || '',
      word_target: s.word_target || 1000,
      emotion_target: s.emotion_target || 5,
      scene_ids: Array.isArray(s.scene_ids) ? s.scene_ids : [],
      choices: s.choices,
      foreshadow_tasks: Array.isArray(s.foreshadow_tasks) ? s.foreshadow_tasks : [],
      focus_characters: Array.isArray(s.focus_characters) ? s.focus_characters : [],
      branch_type: s.branch_type || 'exploration',
      summary: s.summary || '',
      status: s.status || 'draft',
    })),
  }
}

function SectionCard({
  section,
  chapterId,
  projectId,
  onRefresh,
}: {
  section: SectionData
  chapterId: string
  projectId: string
  onRefresh: () => void
}) {
  const { notification } = App.useApp()
  const [expanded, setExpanded] = useState(false)
  const [choices, setChoices] = useState<ChoiceDesign[]>([])
  const [choicesLoading, setChoicesLoading] = useState(false)

  const fetchChoices = useCallback(async () => {
    if (!projectId || !chapterId || !section.id) return
    setChoicesLoading(true)
    try {
      const data = await choicesApi.list(projectId, chapterId, section.id)
      setChoices(data)
    } catch {
      setChoices([])
    } finally {
      setChoicesLoading(false)
    }
  }, [projectId, chapterId, section.id])

  useEffect(() => {
    if (expanded) {
      fetchChoices()
    }
  }, [expanded, fetchChoices])

  const branchInfo = BRANCH_TYPE_MAP[section.branch_type] || BRANCH_TYPE_MAP.exploration
  const choiceCount = Array.isArray(section.choices) ? section.choices.length : 0

  return (
    <div
      style={{
        border: '1px solid var(--border-color, #e5e7eb)',
        borderRadius: 6,
        marginBottom: 8,
        overflow: 'hidden',
      }}
    >
      <div
        style={{
          padding: '8px 12px',
          cursor: 'pointer',
          display: 'flex',
          alignItems: 'center',
          gap: 8,
          background: expanded ? 'var(--hover-bg, #f9fafb)' : 'transparent',
        }}
        onClick={() => setExpanded(!expanded)}
      >
        {expanded ? (
          <DownOutlined style={{ fontSize: 10, color: '#999' }} />
        ) : (
          <RightOutlined style={{ fontSize: 10, color: '#999' }} />
        )}
        <span style={{ fontSize: 12, color: '#999', fontFamily: 'monospace' }}>
          §{section.section_number}
        </span>
        <span style={{ fontSize: 13, fontWeight: 500 }}>
          {section.title || `第${section.section_number}节`}
        </span>
        <Tag color={branchInfo.color} style={{ fontSize: 11, margin: 0 }}>
          {branchInfo.label}
        </Tag>
        <span style={{ fontSize: 11, color: '#999', marginLeft: 'auto' }}>
          {section.word_target}字 · 情感{section.emotion_target}/10
          {choiceCount > 0 && ` · ${choiceCount}个选择`}
        </span>
      </div>

      {expanded && (
        <div style={{ padding: '0 12px 12px', borderTop: '1px solid var(--border-color, #e5e7eb)' }}>
          {section.summary && (
            <p style={{ fontSize: 12, color: '#666', margin: '8px 0' }}>{section.summary}</p>
          )}

          <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap', marginTop: 8 }}>
            {Array.isArray(section.focus_characters) && section.focus_characters.length > 0 && (
              <div>
                <div style={{ fontSize: 11, color: '#999', marginBottom: 4 }}>
                  <UserOutlined style={{ marginRight: 4 }} />聚焦角色
                </div>
                <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
                  {section.focus_characters.map((fc: unknown, i: number) => {
                    const name = typeof fc === 'string' ? fc : String((fc as Record<string, unknown>)?.name || fc)
                    return <Tag key={i} color="purple" style={{ fontSize: 11 }}>{name as string}</Tag>
                  })}
                </div>
              </div>
            )}

            {Array.isArray(section.foreshadow_tasks) && section.foreshadow_tasks.length > 0 && (
              <div>
                <div style={{ fontSize: 11, color: '#999', marginBottom: 4 }}>
                  <ThunderboltOutlined style={{ marginRight: 4 }} />伏笔任务
                </div>
                <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
                  {section.foreshadow_tasks.map((task: unknown, i: number) => {
                    const icon = getForeshadowTypeIcon(task)
                    const text = typeof task === 'string' ? task : String((task as Record<string, unknown>)?.name || (task as Record<string, unknown>)?.text || JSON.stringify(task))
                    return (
                      <Tag key={i} style={{ fontSize: 11 }}>
                        {icon} {text.length > 20 ? text.slice(0, 20) + '…' : text}
                      </Tag>
                    )
                  })}
                </div>
              </div>
            )}
          </div>

          <div style={{ marginTop: 12 }}>
            <div style={{ fontSize: 11, color: '#999', marginBottom: 6, fontWeight: 500 }}>
              互动选择
            </div>
            {choicesLoading ? (
              <Spin size="small" />
            ) : choices.length > 0 ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                {choices.map((choice) => {
                  const moralInfo = MORAL_ALIGNMENT_MAP[choice.moral_alignment] || MORAL_ALIGNMENT_MAP.gray
                  return (
                    <div
                      key={choice.id}
                      style={{
                        padding: '6px 10px',
                        background: 'var(--hover-bg, #f9fafb)',
                        borderRadius: 4,
                        border: '1px solid var(--border-color, #e5e7eb)',
                      }}
                    >
                      <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                        <span style={{ fontSize: 12, fontWeight: 500, flex: 1 }}>
                          {choice.text}
                        </span>
                        <Tag color={moralInfo.color} style={{ fontSize: 10, margin: 0 }}>
                          {moralInfo.label}
                        </Tag>
                        {choice.is_hidden && (
                          <Tag color="default" style={{ fontSize: 10, margin: 0 }}>隐藏</Tag>
                        )}
                      </div>
                      {choice.consequence_direct && (
                        <div style={{ fontSize: 11, color: '#888', marginTop: 4 }}>
                          → {choice.consequence_direct}
                        </div>
                      )}
                    </div>
                  )
                })}
              </div>
            ) : (
              <div style={{ fontSize: 11, color: '#bbb' }}>暂无互动选择</div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

export default function ChapterOutline() {
  const { notification } = App.useApp()
  const { currentProject } = useProjectStore()
  const [chapters, setChapters] = useState<ChapterData[]>([])
  const [loading, setLoading] = useState(false)
  const [editId, setEditId] = useState<string | null>(null)
  const [editData, setEditData] = useState<ChapterData | null>(null)
  const [saving, setSaving] = useState(false)
  const [genLoading, setGenLoading] = useState(false)
  const [expandedChapterIds, setExpandedChapterIds] = useState<Set<string>>(new Set())

  const toggleChapterExpand = (id: string) => {
    setExpandedChapterIds(prev => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  const fetchChapters = useCallback(async () => {
    if (!currentProject?.id) return
    setLoading(true)
    try {
      const data = await chaptersApi.list(currentProject.id)
      setChapters(data.map(apiChapterToChapterData))
    } catch (e: any) {
      notification.warning({
        message: '加载章节失败',
        description: e?.message || '请检查网络连接',
        placement: 'topRight',
      })
    } finally {
      setLoading(false)
    }
  }, [currentProject?.id])

  useEffect(() => {
    fetchChapters()
  }, [fetchChapters])

  useEffect(() => {
    const unsubs = [
      eventBus.on(DataEvents.SCENE_UPDATED, () => { fetchChapters() }),
      eventBus.on(DataEvents.CHARACTER_UPDATED, () => { fetchChapters() }),
      eventBus.on(DataEvents.PROJECT_SWITCHED, () => { fetchChapters() }),
    ]
    return () => unsubs.forEach(u => u())
  }, [fetchChapters])

  const handleCreate = async () => {
    if (!currentProject?.id) return
    try {
      const nextNum = chapters.length + 1
      const newChapter = await chaptersApi.create(currentProject.id, {
        chapter_number: nextNum,
        title: `第${nextNum}章`,
        status: 'draft',
        emotion_target: 5,
      } as any)
      setChapters(prev => [...prev, {
        id: newChapter.id,
        chapter_number: newChapter.chapter_number,
        title: newChapter.title || `第${nextNum}章`,
        summary: newChapter.summary || '',
        key_turning_points: [],
        emotion_target: newChapter.emotion_target || 5,
        focus_characters: [],
        foreshadow_tasks: [],
        worldview_refs: [],
        status: newChapter.status || 'draft',
        sections: [],
      }])
      notification.success({ message: '章节已创建', placement: 'topRight' })
    } catch (e: any) {
      notification.error({
        message: '创建失败',
        description: e?.message || '请检查网络连接',
        placement: 'topRight',
      })
    }
  }

  const handleDelete = async (id: string) => {
    if (!currentProject?.id) return
    try {
      await chaptersApi.delete(currentProject.id, id)
      setChapters(prev => prev.filter(c => c.id !== id))
      notification.success({ message: '章节已删除', placement: 'topRight' })
    } catch (e: any) {
      notification.error({
        message: '删除失败',
        description: e?.message || '请检查网络连接',
        placement: 'topRight',
      })
    }
  }

  const startEdit = (chapter: ChapterData) => {
    setEditId(chapter.id)
    setEditData({ ...chapter })
  }

  const cancelEdit = () => {
    setEditId(null)
    setEditData(null)
  }

  const saveEdit = async () => {
    if (!editData || !currentProject?.id) return
    setSaving(true)
    try {
      await chaptersApi.update(currentProject.id, editData.id, {
        title: editData.title,
        summary: editData.summary,
        emotion_target: editData.emotion_target,
        foreshadow_tasks: editData.foreshadow_tasks,
        status: editData.status,
      } as any)
      setChapters(prev => prev.map(c => c.id === editData.id ? editData : c))
      setEditId(null)
      setEditData(null)
      notification.success({ message: '保存成功', placement: 'topRight' })
    } catch (e: any) {
      notification.error({
        message: '保存失败',
        description: e?.message || '请检查网络连接',
        placement: 'topRight',
      })
    } finally {
      setSaving(false)
    }
  }

  const moveChapter = async (id: string, direction: -1 | 1) => {
    if (!currentProject?.id) return
    const idx = chapters.findIndex(c => c.id === id)
    if (idx < 0) return
    const newIdx = idx + direction
    if (newIdx < 0 || newIdx >= chapters.length) return
    const newChapters = [...chapters]
    const a = newChapters[idx]
    const b = newChapters[newIdx]
    const tmpNum = a.chapter_number
    a.chapter_number = b.chapter_number
    b.chapter_number = tmpNum
    newChapters[idx] = b
    newChapters[newIdx] = a
    setChapters(newChapters)
    try {
      await Promise.all([
        chaptersApi.update(currentProject.id, a.id, { chapter_number: a.chapter_number } as any),
        chaptersApi.update(currentProject.id, b.id, { chapter_number: b.chapter_number } as any),
      ])
    } catch {
      notification.warning({ message: '排序更新失败', description: '章节排序未能保存到服务器', placement: 'topRight' })
    }
  }

  const handleAIExpand = async () => {
    if (!currentProject?.id) return
    setGenLoading(true)
    try {
      const res = await api.post<{ outline: any[] }>(
        `/ai/chapter-outline/${currentProject.id}`
      )
      if (res.outline && res.outline.length > 0) {
        await fetchChapters()
        notification.success({
          message: 'AI 大纲生成完成',
          description: `已生成包含节的完整章节结构`,
          placement: 'topRight',
        })
      }
    } catch (e: any) {
      notification.warning({
        message: 'AI 生成失败',
        description: e?.message || '请检查 AI 服务是否可用',
        placement: 'topRight',
      })
    } finally {
      setGenLoading(false)
    }
  }

  if (!currentProject) {
    return (
      <div style={{ fontFamily: 'var(--font-family)' }}>
        <h2 className="section-title" style={{ fontSize: 24 }}>主线合流</h2>
        <div className="card-surface" style={{ textAlign: 'center', padding: 48 }}>
          <Empty description={<span className="text-muted">请先创建或选择一个项目</span>} />
        </div>
      </div>
    )
  }

  if (loading) {
    return (
      <div style={{ fontFamily: 'var(--font-family)', display: 'flex', justifyContent: 'center', padding: 80 }}>
        <Spin size="large" />
      </div>
    )
  }

  return (
    <div style={{ fontFamily: 'var(--font-family)', height: '100%', overflow: 'auto' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 24, flexShrink: 0 }}>
        <div>
          <h2 className="section-title" style={{ fontSize: 24 }}>主线合流</h2>
          <p className="text-muted" style={{ margin: '4px 0 0' }}>
            {currentProject?.name} · 章节大纲与真实分歧设计
          </p>
        </div>
        <Space>
          <Button icon={<RobotOutlined />} onClick={handleAIExpand} loading={genLoading}>
            AI 展开大纲
          </Button>
          <Button icon={<PlusOutlined />} type="primary" onClick={handleCreate}>
            新建章节
          </Button>
        </Space>
      </div>

      {chapters.length === 0 ? (
        <Card className="text-center py-12">
          <Empty description={
            <div>
              <p className="text-gray-400 mb-3">暂无章节大纲</p>
              <Space>
                <Button icon={<PlusOutlined />} type="primary" onClick={handleCreate}>新建章节</Button>
                <Button icon={<BulbOutlined />} onClick={handleAIExpand}>AI 生成大纲</Button>
              </Space>
            </div>
          } />
        </Card>
      ) : (
        <div className="space-y-2">
          {chapters
            .sort((a, b) => a.chapter_number - b.chapter_number)
            .map((chapter, idx) => {
              const isExpanded = expandedChapterIds.has(chapter.id)
              const foreshadowStats = countForeshadowByType(chapter.foreshadow_tasks)
              const totalForeshadow = chapter.foreshadow_tasks.length
              const sortedSections = [...chapter.sections].sort((a, b) => a.section_number - b.section_number)

              return (
                <Card
                  key={chapter.id}
                  size="small"
                  className={`transition-all ${editId === chapter.id ? 'ring-2 ring-primary-400' : ''}`}
                >
                  {editId === chapter.id && editData ? (
                    <div className="space-y-3">
                      <div className="flex gap-2">
                        <Input
                          size="small" value={editData.title}
                          onChange={e => setEditData({ ...editData, title: e.target.value })}
                          placeholder="章节标题" className="flex-1"
                          status={!editData.title.trim() ? 'error' : undefined}
                        />
                        <Select
                          size="small" value={editData.status}
                          onChange={v => setEditData({ ...editData, status: v })}
                          options={STATUS_OPTIONS} style={{ width: 110 }}
                        />
                        <InputNumber
                          size="small" value={editData.emotion_target}
                          onChange={v => setEditData({ ...editData, emotion_target: v || 5 })}
                          min={0} max={10} style={{ width: 70 }} placeholder="情感"
                        />
                      </div>
                      <TextArea
                        size="small" rows={2} value={editData.summary}
                        onChange={e => setEditData({ ...editData, summary: e.target.value })}
                        placeholder="章节核心内容摘要..."
                      />
                      <div className="flex justify-end gap-2">
                        <Button size="small" onClick={cancelEdit}>取消</Button>
                        <Button size="small" type="primary" icon={<SaveOutlined />} loading={saving} onClick={saveEdit}>保存</Button>
                      </div>
                    </div>
                  ) : (
                    <div>
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-3 flex-1 min-w-0">
                          <span
                            style={{ cursor: 'pointer', display: 'inline-flex', alignItems: 'center' }}
                            onClick={() => toggleChapterExpand(chapter.id)}
                          >
                            {isExpanded ? (
                              <DownOutlined style={{ fontSize: 10, color: '#999', marginRight: 4 }} />
                            ) : (
                              <RightOutlined style={{ fontSize: 10, color: '#999', marginRight: 4 }} />
                            )}
                          </span>
                          <span className="text-xs text-gray-400 font-mono shrink-0">
                            Ch.{chapter.chapter_number}
                          </span>
                          <h3 className="text-sm font-semibold m-0 truncate">{chapter.title}</h3>
                          <Tag color={STATUS_OPTIONS.find(s => s.value === chapter.status)?.color}>
                            {STATUS_OPTIONS.find(s => s.value === chapter.status)?.label || chapter.status}
                          </Tag>
                          <span className="text-xs text-gray-400 flex items-center gap-1">
                            情感 <strong>{chapter.emotion_target}</strong>/10
                          </span>
                          {sortedSections.length > 0 && (
                            <Tag color="cyan" style={{ fontSize: 11 }}>
                              {sortedSections.length}节
                            </Tag>
                          )}
                        </div>
                        <Space className="shrink-0 ml-2">
                          <Tooltip title="上移">
                            <Button size="small" type="text" icon={<ArrowUpOutlined />}
                              disabled={idx === 0} onClick={() => moveChapter(chapter.id, -1)} />
                          </Tooltip>
                          <Tooltip title="下移">
                            <Button size="small" type="text" icon={<ArrowDownOutlined />}
                              disabled={idx === chapters.length - 1} onClick={() => moveChapter(chapter.id, 1)} />
                          </Tooltip>
                          <Button size="small" type="text" icon={<EditOutlined />}
                            onClick={() => startEdit(chapter)} />
                          <Popconfirm
                            title="确定删除该章节？"
                            onConfirm={() => handleDelete(chapter.id)}
                            okText="删除" cancelText="取消"
                            okButtonProps={{ danger: true }}
                          >
                            <Button size="small" type="text" danger icon={<DeleteOutlined />} />
                          </Popconfirm>
                        </Space>
                      </div>
                      {chapter.summary && (
                        <p className="text-xs text-gray-500 mt-2 mb-0 line-clamp-2">{chapter.summary}</p>
                      )}
                      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, marginTop: 8 }}>
                        {chapter.key_turning_points && chapter.key_turning_points.length > 0 &&
                          chapter.key_turning_points.map((evt: string, i: number) => (
                            <Tag key={`tp-${i}`} color="orange" style={{ fontSize: 11 }}>{evt}</Tag>
                          ))
                        }
                        {chapter.worldview_refs && chapter.worldview_refs.length > 0 &&
                          chapter.worldview_refs.map((ref: string, i: number) => (
                            <Tag key={`wv-${i}`} color="geekblue" style={{ fontSize: 11 }}>
                              <BookOutlined style={{ marginRight: 2 }} />{ref}
                            </Tag>
                          ))
                        }
                        {totalForeshadow > 0 && (
                          <>
                            {foreshadowStats.plant > 0 && (
                              <Tag style={{ fontSize: 11 }}>🌱埋设 ×{foreshadowStats.plant}</Tag>
                            )}
                            {foreshadowStats.reinforce > 0 && (
                              <Tag color="blue" style={{ fontSize: 11 }}>🔄强化 ×{foreshadowStats.reinforce}</Tag>
                            )}
                            {foreshadowStats.reveal > 0 && (
                              <Tag color="gold" style={{ fontSize: 11 }}>💡回收 ×{foreshadowStats.reveal}</Tag>
                            )}
                          </>
                        )}
                      </div>

                      {isExpanded && sortedSections.length > 0 && (
                        <div style={{ marginTop: 12, paddingLeft: 4 }}>
                          <div style={{ fontSize: 12, color: '#999', marginBottom: 8, fontWeight: 500 }}>
                            节结构
                          </div>
                          {sortedSections.map(section => (
                            <SectionCard
                              key={section.id}
                              section={section}
                              chapterId={chapter.id}
                              projectId={currentProject.id}
                              onRefresh={fetchChapters}
                            />
                          ))}
                        </div>
                      )}

                      {isExpanded && sortedSections.length === 0 && (
                        <div style={{ marginTop: 12, textAlign: 'center', padding: '16px 0' }}>
                          <span style={{ fontSize: 12, color: '#bbb' }}>
                            暂无节结构，点击「AI 展开大纲」生成
                          </span>
                        </div>
                      )}
                    </div>
                  )}
                </Card>
              )
            })}
        </div>
      )}
    </div>
  )
}
