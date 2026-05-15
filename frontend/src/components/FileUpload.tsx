import { useState, useCallback, useRef } from 'react'
import { Upload, Button, Tag, message, Popconfirm } from 'antd'
import {
  InboxOutlined, FileTextOutlined, FilePdfOutlined,
  FileWordOutlined, DeleteOutlined, CheckCircleOutlined,
} from '@ant-design/icons'
import type { UploadFile, RcFile } from 'antd/es/upload'
import { api } from '../api/client'

interface ReferenceFile {
  id: string
  filename: string
  file_type: string
  file_size: number
  page_count?: number
  text_preview?: string
  created_at?: string
}

interface FileUploadProps {
  projectId: string
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

export default function FileUpload({
  projectId,
  existingFiles = [],
  onFilesChange,
  compact = false,
}: FileUploadProps) {
  const [files, setFiles] = useState<ReferenceFile[]>(existingFiles)
  const [uploading, setUploading] = useState(false)
  const fileListRef = useRef(files)

  const updateFiles = useCallback(
    (newFiles: ReferenceFile[]) => {
      fileListRef.current = newFiles
      setFiles(newFiles)
      onFilesChange?.(newFiles)
    },
    [onFilesChange],
  )

  const handleUpload = useCallback(
    async (file: RcFile): Promise<false | void> => {
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
        message.success(`${file.name} 上传成功`)
      } catch (e: any) {
        message.error(e.message || '上传失败')
      } finally {
        setUploading(false)
      }
      return false
    },
    [projectId, updateFiles],
  )

  const handleDelete = useCallback(
    async (fileId: string) => {
      try {
        await api.delete(`/projects/${projectId}/uploads/${fileId}`)
        updateFiles(fileListRef.current.filter((f) => f.id !== fileId))
        message.success('已删除')
      } catch (e: any) {
        message.error(e.detail || '删除失败')
      }
    },
    [projectId, updateFiles],
  )

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
      {!compact && (
        <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--color-ink)' }}>
          参考文件上传
          <span style={{ fontSize: 11, color: 'var(--color-muted)', fontWeight: 400, marginLeft: 8 }}>
            支持 PDF / Word / TXT / Markdown，单文件 ≤20MB
          </span>
        </div>
      )}

      <Upload.Dragger
        accept={ACCEPTED_TYPES}
        showUploadList={false}
        beforeUpload={handleUpload as any}
        disabled={uploading}
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
            {uploading ? '上传解析中...' : '拖拽文件到此处，或点击选择'}
          </p>
        </div>
      </Upload.Dragger>

      {files.length > 0 && (
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
    </div>
  )
}