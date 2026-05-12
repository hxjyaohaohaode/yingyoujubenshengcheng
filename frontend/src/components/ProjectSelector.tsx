import { useState } from 'react'
import { Card, Button, Tag, Row, Col, Empty, Typography, Modal, App } from 'antd'
import {
  PlayCircleOutlined, ClockCircleOutlined, FileTextOutlined,
  ThunderboltOutlined, ExperimentOutlined, DeleteOutlined,
} from '@ant-design/icons'
import { useProjectStore } from '../stores/projectStore'
import { projectsApi } from '../api/client'
import type { Project } from '../api/client'

const { Text, Paragraph } = Typography

const GENRE_MAP: Record<string, string> = {
  '武侠': '武侠', '悬疑': '悬疑', '爱情': '爱情', '科幻': '科幻',
  '奇幻': '奇幻', '恐怖': '恐怖', '历史': '历史', '都市': '都市',
  '冒险': '冒险', '喜剧': '喜剧',
}

function formatDate(iso: string): string {
  try {
    const d = new Date(iso)
    return `${d.getFullYear()}/${d.getMonth() + 1}/${d.getDate()}`
  } catch { return iso.slice(0, 10) }
}

function ProjectCard({ project, onSelect, isDuplicate, onDelete }: { project: Project; onSelect: () => void; isDuplicate: boolean; onDelete: () => void }) {
  const genre = project.config?.genre || ''
  const genreLabel = GENRE_MAP[genre] || genre
  const wordCount = project.config?.target_word_count

  return (
    <Card
      hoverable
      onClick={onSelect}
      style={{
        borderRadius: 12,
        border: '1px solid var(--color-border)',
        background: 'var(--color-surface)',
        cursor: 'pointer',
        transition: 'all 0.2s',
      }}
      styles={{ body: { padding: '20px 20px 16px' } }}
    >
      <div style={{ display: 'flex', flexDirection: 'column', height: '100%', gap: 12 }}>
        <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 8 }}>
          <div style={{
            width: 40, height: 40, borderRadius: 10,
            background: 'var(--color-accent-soft)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            flexShrink: 0,
          }}>
            <ThunderboltOutlined style={{ fontSize: 18, color: 'var(--color-accent)' }} />
          </div>
          <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap', justifyContent: 'flex-end' }}>
            {genreLabel && (
              <Tag color="blue" style={{ borderRadius: 6, margin: 0, fontSize: 11 }}>
                {genreLabel}
              </Tag>
            )}
            {isDuplicate && (
              <Tag color="orange" style={{ borderRadius: 6, margin: 0, fontSize: 11 }}>
                ID:{project.id.slice(0, 6)}
              </Tag>
            )}
          </div>
        </div>

        <div style={{ flex: 1 }}>
          <Text strong style={{ fontSize: 15, color: 'var(--color-ink)', display: 'block', marginBottom: 4 }}>
            {project.name}
          </Text>
          {project.description ? (
            <Paragraph
              style={{ fontSize: 12, color: 'var(--color-muted)', margin: 0, lineHeight: 1.5 }}
              ellipsis={{ rows: 2 }}
            >
              {project.description}
            </Paragraph>
          ) : (
            <Text style={{ fontSize: 12, color: 'var(--color-subtle)' }}>暂无描述</Text>
          )}
        </div>

        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', fontSize: 11, color: 'var(--color-muted)' }}>
          <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
            <ClockCircleOutlined />
            {formatDate(project.created_at)}
          </span>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            {wordCount && (
              <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                <FileTextOutlined />
                {(wordCount / 10000).toFixed(1)}万字
              </span>
            )}
            <Button
              type="text"
              size="small"
              danger
              icon={<DeleteOutlined />}
              style={{ padding: '0 4px', fontSize: 12 }}
              onClick={(e) => {
                e.stopPropagation()
                onDelete()
              }}
            >
              删除
            </Button>
          </div>
        </div>
      </div>
    </Card>
  )
}

export default function ProjectSelector({ onCreate }: { onCreate: () => void }) {
  const { projects, setCurrentProject, setProjects } = useProjectStore()
  const [hovered, setHovered] = useState(false)
  const [deletingId, setDeletingId] = useState<string | null>(null)
  const [confirmOpen, setConfirmOpen] = useState(false)
  const [confirmProject, setConfirmProject] = useState<Project | null>(null)
  const { modal, message } = App.useApp()

  const handleDeleteClick = (project: Project) => {
    setConfirmProject(project)
    setConfirmOpen(true)
  }

  const handleConfirmDelete = async () => {
    if (!confirmProject) return
    const projectId = confirmProject.id
    setDeletingId(projectId)
    try {
      await projectsApi.delete(projectId)
      message.success('项目已删除')
      setProjects(projects.filter(p => p.id !== projectId))
    } catch (err: any) {
      message.error(err?.detail || '删除失败')
    } finally {
      setDeletingId(null)
      setConfirmOpen(false)
      setConfirmProject(null)
    }
  }

  const handleCancelDelete = () => {
    setConfirmOpen(false)
    setConfirmProject(null)
  }

  if (projects.length === 0) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', padding: '80px 20px' }}>
        <div style={{
          width: 80, height: 80, borderRadius: 20,
          background: 'var(--color-accent-soft)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          marginBottom: 24,
        }}>
          <ThunderboltOutlined style={{ fontSize: 36, color: 'var(--color-accent)' }} />
        </div>
        <h2 style={{ fontSize: 22, fontWeight: 700, color: 'var(--color-ink)', margin: '0 0 8px 0' }}>
          AVG Studio — 互动影游创作工作台
        </h2>
        <p style={{ fontSize: 14, color: 'var(--color-muted)', margin: '0 0 24px 0', maxWidth: 380, textAlign: 'center', lineHeight: 1.7 }}>
          支持从世界观构建到多结局剧本的全流程AI协作，适配几万字到150万字的创作需求。
        </p>
        <Button type="primary" size="large" icon={<PlayCircleOutlined />} onClick={onCreate}>
          创建第一个项目
        </Button>
      </div>
    )
  }

  return (
    <div style={{ padding: '32px 0' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 24 }}>
        <div>
          <h2 style={{ fontSize: 20, fontWeight: 700, color: 'var(--color-ink)', margin: 0 }}>
            已有项目
          </h2>
          <Text style={{ fontSize: 13, color: 'var(--color-muted)' }}>
            共 {projects.length} 个项目，点击进入工作台
          </Text>
        </div>
        <Button
          type="primary"
          icon={<PlayCircleOutlined />}
          style={{
            borderRadius: 8,
            fontSize: 13,
          }}
          onMouseEnter={() => setHovered(true)}
          onMouseLeave={() => setHovered(false)}
          onClick={onCreate}
        >
          {hovered ? '开始创作' : '新建项目'}
        </Button>
      </div>

      <Row gutter={[16, 16]}>
        {projects
          .slice()
          .sort((a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime())
          .map((project) => {
            const isDuplicate = projects.filter(p => p.name === project.name).length > 1
            return (
              <Col xs={24} sm={12} md={8} lg={6} key={project.id}>
                <ProjectCard
                  project={project}
                  onSelect={() => setCurrentProject(project)}
                  isDuplicate={isDuplicate}
                  onDelete={() => handleDeleteClick(project)}
                />
              </Col>
            )
          })}
      </Row>

      <Modal
        title="确认删除项目"
        open={confirmOpen}
        onOk={handleConfirmDelete}
        onCancel={handleCancelDelete}
        okText="确认删除"
        okButtonProps={{ danger: true, loading: deletingId !== null }}
        cancelText="取消"
        destroyOnHidden
      >
        {confirmProject && (
          <div>
            <p>确定要删除项目 <strong>{confirmProject.name}</strong> 吗？</p>
            <p style={{ color: '#ff4d4f', fontSize: 12 }}>
              此操作将删除该项目下的所有数据（场景、章节、角色、伏笔等），且不可恢复。
            </p>
          </div>
        )}
      </Modal>
    </div>
  )
}
