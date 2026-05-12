import { useState, useEffect } from 'react'
import {
  Card, Button, Select, Checkbox, App, Empty, Spin, Space, Tag, Divider,
  Upload, Tabs, Typography,
} from 'antd'
import {
  FileTextOutlined, FileMarkdownOutlined,
  DownloadOutlined, ExportOutlined, LoadingOutlined,
  UploadOutlined, RobotOutlined,
} from '@ant-design/icons'
import { useProjectStore } from '../stores/projectStore'
import { api, chaptersApi, scenesApi, charactersApi, exportApi } from '../api/client'

const { Text } = Typography

export default function Export() {
  const { notification } = App.useApp()
  const { currentProject } = useProjectStore()
  const [format, setFormat] = useState<string>('markdown')
  const [exportLoading, setExportLoading] = useState(false)
  const [exportComplete, setExportComplete] = useState(false)
  const [chaptersLoading, setChaptersLoading] = useState(false)
  const [selectedChapters, setSelectedChapters] = useState<string[]>([])
  const [chapters, setChapters] = useState<{ id: string; chapter_number: number; title: string }[]>([])
  const [stats, setStats] = useState({ scenes: 0, words: 0, characters: 0 })
  const [uploading, setUploading] = useState(false)
  const [optimizing, setOptimizing] = useState(false)

  useEffect(() => {
    if (!currentProject?.id) return
    const loadData = async () => {
      setChaptersLoading(true)
      try {
        const [chData, scData, charData] = await Promise.all([
          chaptersApi.list(currentProject.id),
          scenesApi.list(currentProject.id),
          charactersApi.list(currentProject.id),
        ])
        setChapters(chData.map((c: any) => ({
          id: c.id, chapter_number: c.chapter_number, title: c.title,
        })))
        const totalWords = scData.reduce((acc: number, s: any) => acc + (s.narration?.length || 0), 0)
        setStats({ scenes: scData.length, words: totalWords, characters: charData.length })
      } catch {
        notification.error({ message: '数据加载失败', description: '无法加载导出所需数据，请检查网络连接', placement: 'topRight' })
      } finally {
        setChaptersLoading(false)
      }
    }
    loadData()
  }, [currentProject?.id])

  const handleExport = async () => {
    if (!currentProject?.id) return
    setExportLoading(true)
    setExportComplete(false)
    try {
      const res = await exportApi.export(currentProject.id, {
        format,
        chapter_ids: selectedChapters.length > 0 ? selectedChapters : undefined,
      })
      const blob = new Blob([res as any], { type: getMimeType(format) })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      const ext = format === 'markdown' ? 'md' : format === 'json' ? 'json' : format === 'excel' ? 'csv' : 'txt'
      a.download = `${currentProject.name}_${new Date().toISOString().slice(0, 10)}.${ext}`
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(url)
      setExportComplete(true)
      notification.success({ message: '导出成功', description: '文件已开始下载', placement: 'topRight' })
    } catch (e: any) {
      notification.error({
        message: '导出失败',
        description: e?.detail || e?.message || '请检查网络连接或下载权限',
        placement: 'topRight',
      })
    }
    setExportLoading(false)
  }

  const getMimeType = (fmt: string) => {
    switch (fmt) {
      case 'markdown': return 'text/markdown'
      case 'json': return 'application/json'
      case 'excel': return 'text/csv'
      case 'text': return 'text/plain'
      default: return 'text/plain'
    }
  }

  const handleUploadOptimize = async (file: File) => {
    if (!currentProject?.id) return
    setUploading(true)
    const formData = new FormData()
    formData.append('file', file)
    try {
      const _apiBase = import.meta.env.VITE_API_BASE_URL
        || (window.location.hostname === 'localhost' ? '/api' : 'https://yingyoujubenshengcheng.onrender.com/api')
      const res = await fetch(`${_apiBase}/script-viz/upload-parse/${currentProject.id}`, {
        method: 'POST', body: formData,
      })
      const data = await res.json()
      if (data.status === 'ok') {
        notification.success({
          message: '剧本上传成功',
          description: `已解析 ${data.filename || file.name}，共 ${data.parsed?.characters?.length || 0} 个角色，${data.parsed?.scenes?.length || 0} 个场景`,
          placement: 'topRight',
        })
      } else {
        notification.error({ message: '解析失败', description: '无法解析上传的剧本文件', placement: 'topRight' })
      }
    } catch (e: any) {
      notification.error({ message: '上传失败', description: e?.message || '网络错误', placement: 'topRight' })
    }
    setUploading(false)
    return false
  }

  const handleAIOptimize = async () => {
    if (!currentProject?.id) return
    setOptimizing(true)
    try {
      await api.post(`/ai/projects/${currentProject.id}/full-audit`, {})
      notification.success({ message: 'AI深度优化已启动', description: '系统正在分析并优化您的剧本，请稍后查看结果', placement: 'topRight' })
    } catch (e: any) {
      notification.error({ message: '优化启动失败', description: e?.detail || e?.message || '请稍后重试', placement: 'topRight' })
    }
    setOptimizing(false)
  }

  if (!currentProject) {
    return (
      <div style={{ fontFamily: 'var(--font-family)' }}>
        <h2 className="section-title" style={{ fontSize: 24 }}>导出交付</h2>
        <div className="card-surface" style={{ textAlign: 'center', padding: 48 }}>
          <Empty description={<span className="text-muted">请先创建或选择一个项目</span>} />
        </div>
      </div>
    )
  }

  return (
    <div style={{ fontFamily: 'var(--font-family)' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 24 }}>
        <div>
          <h2 className="section-title" style={{ fontSize: 24 }}>导出交付</h2>
          <p className="text-muted" style={{ margin: '4px 0 0' }}>
            将项目导出为多种格式，或上传已有剧本进行AI深度优化
          </p>
        </div>
      </div>

      <Tabs
        defaultActiveKey="export"
        items={[
          {
            key: 'export',
            label: <><DownloadOutlined /> 导出剧本</>,
            children: (
              <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
                <div className="lg:col-span-2 space-y-4">
                  <Card title="导出格式" size="small">
                    <div className="grid grid-cols-4 gap-3 mb-4">
                      {([
                        { key: 'markdown', label: 'Markdown', desc: '排版友好', icon: <FileMarkdownOutlined className="text-2xl text-blue-500 mb-2" /> },
                        { key: 'text', label: '纯文本', desc: '通用格式', icon: <FileTextOutlined className="text-2xl text-gray-500 mb-2" /> },
                        { key: 'json', label: 'JSON', desc: '结构化数据', icon: <ExportOutlined className="text-2xl text-cyan-500 mb-2" /> },
                        { key: 'excel', label: 'CSV表格', desc: '适合表格分析', icon: <ExportOutlined className="text-2xl text-emerald-500 mb-2" /> },
                      ] as const).map(fmt => (
                        <div
                          key={fmt.key}
                          onClick={() => setFormat(fmt.key)}
                          className={`p-4 rounded-lg border-2 cursor-pointer text-center transition-all ${
                            format === fmt.key
                              ? 'border-primary-500 bg-primary-50 dark:bg-primary-900/20'
                              : 'border-gray-200 dark:border-slate-600 hover:border-primary-300'
                          }`}
                        >
                          {fmt.icon}
                          <div className="text-sm font-semibold">{fmt.label}</div>
                          <div className="text-xs text-gray-400 mt-1">{fmt.desc}</div>
                        </div>
                      ))}
                    </div>

                    {chapters.length > 0 && (
                      <div className="mb-4">
                        <div className="text-sm font-medium mb-2">导出范围</div>
                        <Checkbox.Group
                          value={selectedChapters}
                          onChange={v => setSelectedChapters(v as string[])}
                        >
                          <div className="space-y-1">
                            {chapters.map(ch => (
                              <div key={ch.id}>
                                <Checkbox value={ch.id}>
                                  <span className="text-xs">
                                    第{ch.chapter_number}章 · {ch.title}
                                  </span>
                                </Checkbox>
                              </div>
                            ))}
                          </div>
                        </Checkbox.Group>
                        <div className="text-xs text-gray-400 mt-2">
                          {selectedChapters.length === 0
                            ? '未选择任何章节，将导出全部内容'
                            : `已选择 ${selectedChapters.length} 章`}
                        </div>
                      </div>
                    )}

                    <Button
                      type="primary"
                      icon={exportLoading ? <LoadingOutlined /> : <DownloadOutlined />}
                      onClick={handleExport}
                      loading={exportLoading}
                      block
                      size="large"
                    >
                      {exportLoading ? '正在生成...' : exportComplete ? '已下载 · 再次导出' : '开始导出'}
                    </Button>
                  </Card>
                </div>

                <div>
                  <Card title="项目概览" size="small" loading={chaptersLoading}>
                    <div className="space-y-3">
                      <div>
                        <div className="text-xs text-gray-400">项目名称</div>
                        <div className="text-sm font-semibold">{currentProject.name}</div>
                      </div>
                      <div>
                        <div className="text-xs text-gray-400">场景总数</div>
                        <div className="text-sm font-semibold">{stats.scenes}</div>
                      </div>
                      <div>
                        <div className="text-xs text-gray-400">总字数</div>
                        <div className="text-sm font-semibold">{stats.words.toLocaleString()}</div>
                      </div>
                      <div>
                        <div className="text-xs text-gray-400">章节数</div>
                        <div className="text-sm font-semibold">{chapters.length}</div>
                      </div>
                      <div>
                        <div className="text-xs text-gray-400">题材</div>
                        <Tag>{currentProject.config?.genre || '未设定'}</Tag>
                      </div>
                    </div>
                  </Card>
                </div>
              </div>
            ),
          },
          {
            key: 'upload',
            label: <><UploadOutlined /> 上传优化</>,
            children: (
              <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
                <div className="lg:col-span-2 space-y-4">
                  <Card title="上传已有剧本" size="small">
                    <Upload.Dragger
                      accept=".txt,.md"
                      showUploadList={false}
                      beforeUpload={handleUploadOptimize as any}
                      className="mb-4"
                    >
                      <p className="text-4xl text-gray-300 mb-3"><UploadOutlined /></p>
                      <p className="text-sm text-gray-600 dark:text-gray-400">点击或拖拽剧本文件到此区域</p>
                      <p className="text-xs text-gray-400 mt-1">
                        目前支持 .txt 和 .md 纯文本剧本
                      </p>
                    </Upload.Dragger>
                    <div className="text-xs text-gray-400 space-y-1">
                      <p>• 系统将自动解析剧本中的角色、场景和伏笔</p>
                      <p>• AI会对角色深度、情节逻辑、伏笔结构进行全面检测</p>
                      <p>• 自动生成优化建议并可直接应用修改</p>
                    </div>
                  </Card>

                  <Card title={<><RobotOutlined className="mr-1" />AI 深度优化</>} size="small">
                    <p className="text-sm text-gray-600 dark:text-gray-400 mb-4">
                      AI将对当前项目进行深度分析，检查逻辑一致性、角色弧完整性、伏笔回收率等，并给出专业优化建议。
                    </p>
                    <Button
                      type="primary"
                      icon={<RobotOutlined />}
                      onClick={handleAIOptimize}
                      loading={optimizing}
                      size="large"
                    >
                      开始AI深度优化
                    </Button>
                  </Card>
                </div>

                <div>
                  <Card title="项目概览" size="small" loading={chaptersLoading}>
                    <div className="space-y-3">
                      <div>
                        <div className="text-xs text-gray-400">项目名称</div>
                        <div className="text-sm font-semibold">{currentProject.name}</div>
                      </div>
                      <div>
                        <div className="text-xs text-gray-400">场景总数</div>
                        <div className="text-sm font-semibold">{stats.scenes}</div>
                      </div>
                      <div>
                        <div className="text-xs text-gray-400">总字数</div>
                        <div className="text-sm font-semibold">{stats.words.toLocaleString()}</div>
                      </div>
                      <div>
                        <div className="text-xs text-gray-400">章节数</div>
                        <div className="text-sm font-semibold">{chapters.length}</div>
                      </div>
                      <div>
                        <div className="text-xs text-gray-400">题材</div>
                        <Tag>{currentProject.config?.genre || '未设定'}</Tag>
                      </div>
                    </div>
                  </Card>
                </div>
              </div>
            ),
          },
        ]}
      />
    </div>
  )
}
