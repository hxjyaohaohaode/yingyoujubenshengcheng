import { useState, useCallback, useRef } from 'react'
import { Upload, Button, Tag, App, Popconfirm, Radio, Space, Modal, Progress, Typography, Collapse } from 'antd'
import {
  InboxOutlined, FileTextOutlined, FilePdfOutlined,
  FileWordOutlined, DeleteOutlined, CheckCircleOutlined,
  ImportOutlined, EditOutlined, UserOutlined, BookOutlined,
} from '@ant-design/icons'
import type { UploadFile, RcFile } from 'antd/es/upload'
import { api } from '../api/client'

const { Text, Paragraph } = Typography

interface ReferenceFile {
  id: string
  filename: string
  file_type: string
  file_size: number
  page_count?: number
  text_preview?: string
  created_at?: string
}

interface ScriptParseResult {
  title: string
  total_words: number
  chapter_count: number
  character_count: number
  characters: string[]
  characters_detail: Array<{ name: string; description: string; mention_count: number }>
  chapters: Array<{ index: number; title: string; word_count: number }>
  style: {
    avg_sentence_length: number
    dialogue_ratio: number
    narrative_pov: string
    tone_keywords: string[]
    summary: string
    style_guide: string
  }
  memory_initialized: { characters: number; chapters: number; total_words: number }
}

interface FileUploadProps {
  projectId: string
  allowScriptImport?: boolean
  onScriptParsed?: (result: ScriptParseResult) => void
  onUploadComplete?: () => void
  existingFiles?: ReferenceFile[]
  onFilesChange?: (files: ReferenceFile[]) => void
  compact?: boolean
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes}B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)}KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)}MB`
}

function getFileIcon(fileType: string) {
  if (fileType === 'pdf') return <FilePdfOutlined style={{ color: '#EF4444' }} />
  if (fileType === 'docx') return <FileWordOutlined style={{ color: '#3B82F6' }} />
  return <FileTextOutlined style={{ color: '#10B981' }} />
}

const ACCEPTED_TYPES = '.pdf,.docx,.txt,.md,.markdown'

type UploadMode = 'reference' | 'import_project' | 'modify_script'

export default function FileUpload({
  projectId,
  allowScriptImport = false,
  onScriptParsed,
  onUploadComplete,
  existingFiles = [],
  onFilesChange,
  compact = false,
}: FileUploadProps) {
  const { message: msgApi } = App.useApp()
  const [files, setFiles] = useState<ReferenceFile[]>(existingFiles)
  const [uploading, setUploading] = useState(false)
  const [uploadMode, setUploadMode] = useState<UploadMode>('reference')
  const [parseResult, setParseResult] = useState<ScriptParseResult | null>(null)
  const [parseModalVisible, setParseModalVisible] = useState(false)
  const [parsing, setParsing] = useState(false)
  const [parseProgress, setParseProgress] = useState(0)
  const fileListRef = useRef(files)

  const updateFiles = useCallback(
    (newFiles: ReferenceFile[]) => {
      fileListRef.current = newFiles
      setFiles(newFiles)
      onFilesChange?.(newFiles)
    },
    [onFilesChange],
  )

  const handleScriptUpload = useCallback(
    async (file: RcFile): Promise<false | void> => {
      if (uploadMode === 'reference') {
        setUploading(true)
        try {
          const formData = new FormData()
          formData.append('file', file)

          const res = await fetch(`/api/projects/${projectId}/upload`, {
            method: 'POST',
            body: formData,
          })

          if (!res.ok) {
            const errData = await res.json().catch(() => ({ detail: '上传失败' }))
            throw new Error(errData.detail || `HTTP ${res.status}`)
          }

          const data = await res.json()
          const newFile: ReferenceFile = {
            id: data.file_id,
            filename: data.filename,
            file_type: data.file_type,
            file_size: data.size,
            page_count: data.pages,
            text_preview: data.preview,
          }

          updateFiles([...fileListRef.current, newFile])
          msgApi.success(`${file.name} 上传成功`)
          onUploadComplete?.()
        } catch (e: any) {
          msgApi.error(e.message || '上传失败')
        } finally {
          setUploading(false)
        }
        return false
      }

      setParsing(true)
      setParseProgress(10)

      try {
        const content = await file.text().catch(() => file.arrayBuffer().then(buf => {
          const decoder = new TextDecoder('utf-8')
          const text = decoder.decode(buf)
          return text
        }))

        setParseProgress(30)

        const formData = new FormData()
        const blob = new Blob([content], { type: 'text/plain;charset=utf-8' })
        formData.append('file', blob, file.name)
        formData.append('project_id', projectId)

        setParseProgress(50)

        const res = await fetch(`/api/projects/scripts/parse`, {
          method: 'POST',
          body: formData,
        })

        setParseProgress(80)

        if (!res.ok) {
          const errData = await res.json().catch(() => ({ detail: '解析失败' }))
          throw new Error(errData.detail || `HTTP ${res.status}`)
        }

        const data = await res.json()
        const result = data.data as ScriptParseResult

        setParseResult(result)
        setParseProgress(100)
        setParseModalVisible(true)

        onScriptParsed?.(result)

        if (uploadMode === 'import_project') {
          msgApi.success(`剧本解析完成: ${result.chapter_count}章, ${result.character_count}个角色, ${result.total_words}字`)
        } else {
          msgApi.success(`剧本解析完成，已初始化叙事记忆: ${result.memory_initialized.characters}角色, ${result.memory_initialized.chapters}章节`)
        }
      } catch (e: any) {
        msgApi.error(e.message || '解析失败')
      } finally {
        setParsing(false)
        setParseProgress(0)
      }
      return false
    },
    [projectId, uploadMode, updateFiles, onScriptParsed, onUploadComplete],
  )

  const handleDelete = useCallback(
    async (fileId: string) => {
      try {
        await api.delete(`/projects/${projectId}/uploads/${fileId}`)
        updateFiles(fileListRef.current.filter((f) => f.id !== fileId))
        msgApi.success('已删除')
      } catch (e: any) {
        msgApi.error(e.detail || '删除失败')
      }
    },
    [projectId, updateFiles],
  )

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
      {!compact && (
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 8 }}>
          <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--color-ink)' }}>
            {uploadMode === 'reference' && '参考文件上传'}
            {uploadMode === 'import_project' && '剧本导入'}
            {uploadMode === 'modify_script' && '剧本修改'}
            <span style={{ fontSize: 11, color: 'var(--color-muted)', fontWeight: 400, marginLeft: 8 }}>
              支持 PDF / Word / TXT / Markdown，单文件 ≤20MB
            </span>
          </div>
          {allowScriptImport && (
            <Radio.Group
              size="small"
              value={uploadMode}
              onChange={(e) => setUploadMode(e.target.value)}
              optionType="button"
              buttonStyle="solid"
            >
              <Radio.Button value="reference">参考文件</Radio.Button>
              <Radio.Button value="modify_script">
                <EditOutlined /> 修改已有剧本
              </Radio.Button>
              <Radio.Button value="import_project">
                <ImportOutlined /> 导入为项目
              </Radio.Button>
            </Radio.Group>
          )}
        </div>
      )}

      {uploadMode === 'modify_script' && !compact && (
        <div style={{
          padding: '8px 12px',
          background: '#fff7e6',
          border: '1px solid #ffd591',
          borderRadius: 6,
          fontSize: 12,
          color: '#ad6800',
        }}>
          上传您的剧本文件，系统将解析角色、章节、风格，初始化叙事记忆。
          生成的后续内容将基于您上传的剧本风格和角色进行创作。
        </div>
      )}

      {uploadMode === 'import_project' && !compact && (
        <div style={{
          padding: '8px 12px',
          background: '#e6f7ff',
          border: '1px solid #91d5ff',
          borderRadius: 6,
          fontSize: 12,
          color: '#0050b3',
        }}>
          上传完整剧本，系统将自动解析全部章节和角色，创建项目并初始化世界观和叙事记忆。
        </div>
      )}

      {parsing ? (
        <div style={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          gap: 12,
          padding: 24,
          background: 'var(--color-surface2)',
          border: '1px dashed var(--color-accent)',
          borderRadius: 10,
        }}>
          <CheckCircleOutlined style={{ fontSize: 32, color: 'var(--color-accent)' }} spin />
          <Text style={{ fontSize: 13 }}>
            {parseProgress < 80 ? '正在解析剧本内容...' : '正在初始化叙事记忆...'}
          </Text>
          <Progress percent={parseProgress} size="small" style={{ width: 200 }} showInfo={false} />
        </div>
      ) : (
        <Upload.Dragger
          accept={ACCEPTED_TYPES}
          showUploadList={false}
          beforeUpload={handleScriptUpload as any}
          disabled={uploading || parsing}
          style={{
            background: 'var(--color-surface2)',
            border: '1px dashed var(--color-border)',
            borderRadius: 10,
            padding: compact ? '16px 0' : '24px 0',
          }}
        >
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 6 }}>
            {uploading ? (
              <CheckCircleOutlined style={{ fontSize: compact ? 24 : 32, color: 'var(--color-accent)' }} spin />
            ) : (
              <InboxOutlined style={{ fontSize: compact ? 24 : 32, color: 'var(--color-muted)' }} />
            )}
            <p style={{ fontSize: compact ? 12 : 13, color: 'var(--color-muted)', margin: 0 }}>
              {uploadMode === 'import_project' && '拖拽剧本文件，自动创建项目'}
              {uploadMode === 'modify_script' && '拖拽您的剧本，基于原内容创作'}
              {uploadMode === 'reference' && (uploading ? '上传解析中...' : '拖拽文件到此处，或点击选择')}
            </p>
          </div>
        </Upload.Dragger>
      )}

      {files.length > 0 && uploadMode === 'reference' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          {files.map((file) => (
            <div
              key={file.id}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 10,
                padding: '8px 12px',
                borderRadius: 8,
                background: 'var(--color-surface2)',
                border: '1px solid var(--color-border)',
              }}
            >
              {getFileIcon(file.file_type)}
              <div style={{ flex: 1, minWidth: 0 }}>
                <div
                  style={{ fontSize: 12, fontWeight: 500, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}
                >
                  {file.filename}
                </div>
                <div style={{ fontSize: 11, color: 'var(--color-muted)' }}>
                  {formatSize(file.file_size)}
                  {file.page_count ? ` · ${file.page_count}页` : ''}
                </div>
              </div>
              <Tag color="green" style={{ fontSize: 10, margin: 0 }}>
                {file.file_type.toUpperCase()}
              </Tag>
              <Popconfirm
                title="确定删除这个文件？"
                onConfirm={() => handleDelete(file.id)}
                okText="删除"
                cancelText="取消"
              >
                <Button type="text" size="small" danger icon={<DeleteOutlined />} />
              </Popconfirm>
            </div>
          ))}
        </div>
      )}

      <Modal
        title={
          <Space>
            <BookOutlined />
            <span>剧本解析结果: {parseResult?.title}</span>
          </Space>
        }
        open={parseModalVisible}
        onCancel={() => setParseModalVisible(false)}
        footer={[
          <Button key="close" onClick={() => setParseModalVisible(false)}>关闭</Button>,
          uploadMode === 'import_project' && (
            <Button key="import" type="primary" onClick={() => {
              setParseModalVisible(false)
              msgApi.success('剧本解析完成，请前往世界设定完善细节')
            }}>
              确认导入
            </Button>
          ),
        ]}
        width={640}
      >
        {parseResult && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap' }}>
              <div style={{
                flex: 1, minWidth: 120, padding: 12, background: '#f0f5ff',
                borderRadius: 8, textAlign: 'center',
              }}>
                <div style={{ fontSize: 24, fontWeight: 700, color: '#1677ff' }}>{parseResult.total_words.toLocaleString()}</div>
                <div style={{ fontSize: 11, color: '#888' }}>总字数</div>
              </div>
              <div style={{
                flex: 1, minWidth: 120, padding: 12, background: '#f6ffed',
                borderRadius: 8, textAlign: 'center',
              }}>
                <div style={{ fontSize: 24, fontWeight: 700, color: '#52c41a' }}>{parseResult.chapter_count}</div>
                <div style={{ fontSize: 11, color: '#888' }}>章节数</div>
              </div>
              <div style={{
                flex: 1, minWidth: 120, padding: 12, background: '#fff7e6',
                borderRadius: 8, textAlign: 'center',
              }}>
                <div style={{ fontSize: 24, fontWeight: 700, color: '#fa8c16' }}>{parseResult.character_count}</div>
                <div style={{ fontSize: 11, color: '#888' }}>角色数</div>
              </div>
            </div>

            <div>
              <Text strong style={{ fontSize: 13 }}><UserOutlined /> 角色列表</Text>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, marginTop: 4 }}>
                {parseResult.characters.map((name, i) => (
                  <Tag key={i} color="blue" style={{ fontSize: 11 }}>{name}</Tag>
                ))}
              </div>
            </div>

            <div>
              <Text strong style={{ fontSize: 13 }}><BookOutlined /> 章节概览</Text>
              <div style={{ maxHeight: 150, overflowY: 'auto', marginTop: 4 }}>
                {parseResult.chapters.map((ch) => (
                  <div key={ch.index} style={{
                    padding: '4px 8px', fontSize: 11,
                    borderBottom: '1px solid #f0f0f0',
                    display: 'flex', justifyContent: 'space-between',
                  }}>
                    <span>第{ch.index + 1}章 {ch.title}</span>
                    <Tag color="green" style={{ fontSize: 10 }}>{ch.word_count.toLocaleString()}字</Tag>
                  </div>
                ))}
              </div>
            </div>

            <div>
              <Text strong style={{ fontSize: 13 }}>写作风格分析</Text>
              <Paragraph style={{ fontSize: 11, color: '#666', marginTop: 4 }}>
                {parseResult.style.summary}
              </Paragraph>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
                {parseResult.style.tone_keywords.map((kw, i) => (
                  <Tag key={i} color="purple" style={{ fontSize: 10 }}>{kw}</Tag>
                ))}
              </div>
            </div>

            <div style={{
              padding: 8, background: '#f6ffed', borderRadius: 6,
              fontSize: 11, color: '#389e0d',
            }}>
              叙事记忆已初始化: {parseResult.memory_initialized.characters}个角色,
              {parseResult.memory_initialized.chapters}个章节记忆,
              共{parseResult.memory_initialized.total_words.toLocaleString()}字
            </div>
          </div>
        )}
      </Modal>
    </div>
  )
}