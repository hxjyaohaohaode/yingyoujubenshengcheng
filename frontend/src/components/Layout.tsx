import { useState, useEffect, useCallback, useRef } from 'react'
import { Outlet, useNavigate, useLocation } from 'react-router-dom'
import { Layout as AntLayout, Menu, Button, Tooltip, Dropdown, Modal, App } from 'antd'
import type { MenuProps } from 'antd'
import {
  DashboardOutlined, TeamOutlined, AppstoreOutlined,
  NodeIndexOutlined, SettingOutlined,
  AuditOutlined, ExperimentOutlined,
  HomeOutlined, SunOutlined, MoonOutlined,
  BulbOutlined, ApartmentOutlined,
  SafetyOutlined, PlayCircleOutlined, SendOutlined,
  FileTextOutlined,
  ThunderboltOutlined,
  LineChartOutlined, EyeOutlined,
  MenuFoldOutlined, MenuUnfoldOutlined,
  BranchesOutlined, UsergroupAddOutlined,
  DeploymentUnitOutlined,
  RobotOutlined, DeleteOutlined,
} from '@ant-design/icons'
import { useProjectStore } from '../stores/projectStore'
import { useThemeStore } from '../stores/themeStore'
import { projectsApi } from '../api/client'
import { eventBus, DataEvents } from '../services/eventBus'
import CreateProjectModal from './CreateProjectModal'
import LLMConfigModal from './LLMConfigModal'
import PipelineProgressBar from './PipelineProgressBar'

const { Header, Sider, Content } = AntLayout

type NavItem = { key: string; icon: React.ReactNode; label: string }

const NAV_ITEMS: NavItem[] = [
  { key: '/', icon: <DashboardOutlined />, label: '01  总览' },
  { key: '/pipeline', icon: <ExperimentOutlined />, label: '02  素材提取' },
  { key: '/world', icon: <BulbOutlined />, label: '03  改编策略·世界观' },
  { key: '/characters', icon: <TeamOutlined />, label: '04  角色阵营' },
  { key: '/chapters', icon: <ApartmentOutlined />, label: '05  主线合流' },
  { key: '/settings', icon: <SettingOutlined />, label: '06  变量规则' },
  { key: '/scenes', icon: <AppstoreOutlined />, label: '07  Storylet' },
  { key: '/foreshadows', icon: <BranchesOutlined />, label: '08  选项后果' },
  { key: '/review', icon: <UsergroupAddOutlined />, label: '09  多人推演' },
  { key: '/emotion-curve', icon: <SafetyOutlined />, label: '10  审校修补' },
  { key: '/script-preview', icon: <PlayCircleOutlined />, label: '11  试玩预览' },
  { key: '/export', icon: <SendOutlined />, label: '12  导出交付' },
  { key: '/script-viz', icon: <EyeOutlined />, label: '13  可视化' },
]

export default function AppLayout() {
  const navigate = useNavigate()
  const location = useLocation()
  const { currentProject, setCurrentProject, projects, setProjects } = useProjectStore()
  const isDark = useThemeStore((s) => s.isDark)
  const toggleTheme = useThemeStore((s) => s.toggle)
  const [collapsed, setCollapsed] = useState(false)
  const [createModalOpen, setCreateModalOpen] = useState(false)
  const [llmModalOpen, setLlmModalOpen] = useState(false)
  const [deleteModalOpen, setDeleteModalOpen] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const mountedRef = useRef(true)
  const { modal, message } = App.useApp()

  const fetchProjects = useCallback(async () => {
    try {
      const data = await projectsApi.list()
      if (!mountedRef.current) return
      setProjects(data.projects)
    } catch { /* silent */ }
  }, [setProjects])

  useEffect(() => {
    mountedRef.current = true
    fetchProjects()
    return () => { mountedRef.current = false }
  }, [fetchProjects])

  useEffect(() => {
    if (currentProject) document.title = `${currentProject.name} | AVG Studio`
    else document.title = 'AVG Studio - 互动影游创作工作台'
  }, [currentProject])

  useEffect(() => {
    const handler = () => setCreateModalOpen(true)
    window.addEventListener('open-create-project', handler)
    const llmHandler = () => setLlmModalOpen(true)
    window.addEventListener('open-llm-config', llmHandler)
    return () => {
      window.removeEventListener('open-create-project', handler)
      window.removeEventListener('open-llm-config', llmHandler)
    }
  }, [])

  const handleSwitchProject = (projectId: string) => {
    const p = projects.find(p => p.id === projectId)
    if (p) {
      setCurrentProject(p)
      // 直接刷新页面，由页面初始化加载新数据，避免触发事件导致请求竞争
      window.location.href = '/'
    }
  }

  const handleDeleteCurrentProject = () => {
    setDeleteModalOpen(true)
  }

  const handleConfirmDelete = async () => {
    if (!currentProject) return
    setDeleting(true)
    try {
      await projectsApi.delete(currentProject.id)
      message.success('项目已删除')
      const remaining = projects.filter(p => p.id !== currentProject.id)
      setProjects(remaining)
      setCurrentProject(null)
      setDeleteModalOpen(false)
      navigate('/')
    } catch (err: any) {
      message.error(err?.detail || '删除失败')
    } finally {
      setDeleting(false)
    }
  }

  const handleCreateSuccess = useCallback(() => {
    setCreateModalOpen(false)
    fetchProjects()
  }, [fetchProjects])

  const seg = location.pathname.split('/').filter(Boolean)[0]
  const currentPath = seg ? `/${seg}` : '/'
  const selectedKeys = [currentPath]

  const menuItems: MenuProps['items'] = NAV_ITEMS.map((item) => ({
    key: item.key,
    icon: item.icon,
    label: item.label,
  }))

  const handleMenuClick: MenuProps['onClick'] = (info) => {
    navigate(info.key)
  }

  return (
    <AntLayout style={{ minHeight: '100vh', background: 'var(--color-bg)', overflow: 'auto' }}>
      <Sider
        trigger={null}
        collapsible
        collapsed={collapsed}
        width={250}
        style={{
          background: 'var(--color-surface)',
          borderRight: '1px solid var(--color-border)',
          height: '100vh',
          position: 'fixed',
          left: 0,
          top: 0,
          bottom: 0,
          zIndex: 30,
          overflow: 'auto',
        }}
      >
        <div style={{ padding: '16px 20px 12px' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <div
              style={{ fontSize: 20, fontWeight: 700, color: 'var(--color-ink)', cursor: 'pointer', lineHeight: 1.3 }}
              onClick={() => navigate('/')}
            >
              {collapsed ? 'AVG' : 'AVG Studio'}
            </div>
            <Button
              type="text"
              icon={collapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />}
              onClick={() => setCollapsed(!collapsed)}
              style={{ color: 'var(--color-muted)' }}
            />
          </div>
          {!collapsed && <div style={{ fontSize: 12, color: 'var(--color-muted)', marginTop: 2 }}>互动影游创作工作台</div>}

          {!collapsed && (currentProject ? (
            <div style={{ background: 'var(--color-accent-soft)', borderRadius: 14, padding: '8px 14px', marginTop: 14 }}>
              <div style={{ fontSize: 12, color: 'var(--color-accent)', fontWeight: 500, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                项目：{currentProject.name}
              </div>
            </div>
          ) : (
            <div
              style={{ background: 'var(--color-surface2)', borderRadius: 14, padding: '8px 14px', marginTop: 14, cursor: 'pointer', border: '1px dashed var(--color-border)' }}
              onClick={() => setCreateModalOpen(true)}
            >
              <div style={{ fontSize: 12, color: 'var(--color-muted)' }}>+ 创建项目</div>
            </div>
          ))}
        </div>

        <Menu
          mode="inline"
          selectedKeys={selectedKeys}
          items={menuItems}
          onClick={handleMenuClick}
          style={{
            background: 'transparent',
            borderInlineEnd: 'none',
            fontFamily: 'var(--font-family)',
            fontSize: 13,
          }}
          inlineCollapsed={collapsed}
        />

        {!collapsed && (
          <div style={{ position: 'absolute', bottom: 0, left: 0, right: 0, padding: '12px 16px', borderTop: '1px solid var(--color-border)' }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 4 }}>
              <Tooltip title={isDark ? '浅色模式' : '深色模式'}>
                <Button type="text" icon={isDark ? <SunOutlined /> : <MoonOutlined />} onClick={toggleTheme} style={{ color: 'var(--color-muted)' }} />
              </Tooltip>
              <Tooltip title="API 配置">
                <Button type="text" icon={<RobotOutlined />} onClick={() => setLlmModalOpen(true)} style={{ color: 'var(--color-muted)' }} />
              </Tooltip>
              <Tooltip title="新建项目">
                <Button type="text" icon={<FileTextOutlined />} onClick={() => setCreateModalOpen(true)} style={{ color: 'var(--color-muted)' }} />
              </Tooltip>
            </div>
          </div>
        )}
      </Sider>

      <AntLayout style={{ marginLeft: collapsed ? 80 : 250, transition: 'margin-left 0.2s', background: 'transparent' }}>
        <Header style={{
          background: 'var(--color-surface)',
          borderBottom: '1px solid var(--color-border)',
          padding: '0 24px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          height: 56,
          position: 'sticky',
          top: 0,
          zIndex: 20,
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <div style={{ fontSize: 16, fontWeight: 700, color: 'var(--color-ink)' }}>
              {NAV_ITEMS.find(n => n.key === currentPath || (n.key !== '/' && currentPath.startsWith(n.key)))?.label?.replace(/^\d+\s+/, '') || ''}
            </div>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            {currentProject ? (
              <Dropdown
                menu={{
                  items: [
                    {
                      key: 'header',
                      label: (
                        <span style={{ fontSize: 11, color: 'var(--color-muted)', padding: '0 4px' }}>
                          切换项目 ({projects.length}个)
                        </span>
                      ),
                      disabled: true,
                    },
                    ...projects
                      .filter(p => p.id !== currentProject.id)
                      .sort((a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime())
                      .map(p => {
                        const genre = p.config?.genre || ''
                        const wordCount = p.config?.target_word_count
                        const displayWords = wordCount ? `${(wordCount / 10000).toFixed(0)}万字` : ''
                        const isDuplicate = projects.filter(x => x.name === p.name).length > 1
                        const label = isDuplicate
                          ? `${p.name} · ${genre || '无体裁'}${displayWords ? ` · ${displayWords}` : ''} · ${p.id.slice(0, 6)}`
                          : `${p.name}${genre ? ` · ${genre}` : ''}${displayWords ? ` · ${displayWords}` : ''}`
                        return {
                          key: p.id,
                          label: (
                            <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                              <span style={{ fontSize: 13 }}>{p.name}</span>
                              <span style={{ fontSize: 11, color: 'var(--color-muted)' }}>
                                {genre}{displayWords ? ` · ${displayWords}` : ''} · {new Date(p.updated_at).toLocaleDateString('zh-CN')}
                                {isDuplicate && <span style={{ color: 'var(--color-accent)', marginLeft: 4 }}>ID:{p.id.slice(0, 6)}</span>}
                              </span>
                            </div>
                          ),
                          onClick: () => handleSwitchProject(p.id),
                        }
                      }),
                    { type: 'divider' as const },
                    {
                      key: 'delete',
                      label: '删除当前项目',
                      icon: <DeleteOutlined />,
                      danger: true,
                      onClick: () => handleDeleteCurrentProject(),
                    },
                    { type: 'divider' as const },
                    {
                      key: 'new',
                      label: '新建项目',
                      icon: <PlayCircleOutlined />,
                      onClick: () => setCreateModalOpen(true),
                    },
                  ],
                }}
                trigger={['click']}
                placement="bottomRight"
                overlayStyle={{ maxHeight: 400, overflow: 'auto' }}
              >
                <div style={{
                  display: 'flex', alignItems: 'center', gap: 8,
                  background: 'var(--color-accent-soft)',
                  borderRadius: 8, padding: '4px 14px',
                  cursor: 'pointer',
                }}>
                  <ThunderboltOutlined style={{ color: 'var(--color-accent)', fontSize: 13 }} />
                  <span style={{ fontSize: 13, color: 'var(--color-accent)', fontWeight: 600, maxWidth: 160, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {currentProject.name}
                  </span>
                </div>
              </Dropdown>
            ) : (
              <Button
                type="primary"
                size="small"
                icon={<PlayCircleOutlined />}
                onClick={() => setCreateModalOpen(true)}
                style={{ fontSize: 12 }}
              >
                新建项目
              </Button>
            )}
          </div>
        </Header>

        <Content style={{ padding: 0, display: 'flex', flexDirection: 'column', minHeight: 0, flex: 1, overflow: 'auto' }}>
          <PipelineProgressBar />
          <div style={{ padding: 24, minHeight: 0, display: 'flex', flexDirection: 'column', flex: 1 }}>
            <Outlet />
          </div>
        </Content>
      </AntLayout>

      <CreateProjectModal
        open={createModalOpen}
        onClose={() => setCreateModalOpen(false)}
      />
      <LLMConfigModal
        open={llmModalOpen}
        onClose={() => setLlmModalOpen(false)}
      />
      <Modal
        title="确认删除项目"
        open={deleteModalOpen}
        onOk={handleConfirmDelete}
        onCancel={() => setDeleteModalOpen(false)}
        okText="确认删除"
        okButtonProps={{ danger: true, loading: deleting }}
        cancelText="取消"
        destroyOnHidden
      >
        {currentProject && (
          <div>
            <p>确定要删除项目 <strong>{currentProject.name}</strong> 吗？</p>
            <p style={{ color: '#ff4d4f', fontSize: 12 }}>
              此操作将删除该项目下的所有数据（场景、章节、角色、伏笔等），且不可恢复。
            </p>
          </div>
        )}
      </Modal>
    </AntLayout>
  )
}
