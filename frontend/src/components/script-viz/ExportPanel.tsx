import { useState } from 'react'
import { Button, Dropdown, Modal, App, Segmented, Space, InputNumber } from 'antd'
import { DownloadOutlined, PictureOutlined, FilePdfOutlined, FileImageOutlined } from '@ant-design/icons'

interface ExportPanelProps {
  onExport?: (format: string, scale: number) => void
  hasData: boolean
}

export default function ExportPanel({ onExport, hasData }: ExportPanelProps) {
  const [exportModalOpen, setExportModalOpen] = useState(false)
  const [exportFormat, setExportFormat] = useState<string>('png')
  const [exportScale, setExportScale] = useState(2)
  const [exporting, setExporting] = useState(false)
  const { notification } = App.useApp()

  const handleExport = async () => {
    if (!hasData) {
      notification.warning({ message: '暂无数据可导出', placement: 'topRight' })
      return
    }
    setExporting(true)
    try {
      if (onExport) {
        await onExport(exportFormat, exportScale)
      } else {
        const flowElement = document.querySelector('.react-flow__viewport') as HTMLElement
        if (!flowElement) throw new Error('未找到图谱元素')

        let dataUrl: string
        try {
          const { toPng, toJpeg, toSvg } = await import('html-to-image')
          const pixelRatio = exportScale
          if (exportFormat === 'svg') {
            dataUrl = await toSvg(flowElement, { pixelRatio })
          } else if (exportFormat === 'jpg') {
            dataUrl = await toJpeg(flowElement, { pixelRatio, quality: 0.95 })
          } else {
            dataUrl = await toPng(flowElement, { pixelRatio })
          }
        } catch {
          notification.warning({
            message: '导出组件未安装',
            description: '请运行 npm install html-to-image 安装导出依赖',
            placement: 'topRight',
          })
          setExporting(false)
          setExportModalOpen(false)
          return
        }

        const link = document.createElement('a')
        link.download = `剧本图谱_${new Date().toISOString().slice(0, 10)}.${exportFormat}`
        link.href = dataUrl
        link.click()
      }
      notification.success({ message: `已导出 ${exportFormat.toUpperCase()} 图谱`, placement: 'topRight' })
      setExportModalOpen(false)
    } catch (e: any) {
      console.error('Export failed:', e)
      notification.error({
        message: '导出失败',
        description: e?.message || '导出过程发生错误',
        placement: 'topRight',
      })
    } finally {
      setExporting(false)
    }
  }

  const dropdownItems = {
    items: [
      {
        key: 'quick-png',
        label: '快速导出 PNG (2x)',
        icon: <FileImageOutlined />,
        onClick: () => { setExportFormat('png'); setExportScale(2); handleExport() },
      },
      {
        key: 'custom',
        label: '自定义导出...',
        icon: <PictureOutlined />,
        onClick: () => setExportModalOpen(true),
      },
    ],
  }

  return (
    <>
      <Dropdown menu={dropdownItems} trigger={['click']}>
        <Button size="small" icon={<DownloadOutlined />} disabled={!hasData}>
          导出
        </Button>
      </Dropdown>

      <Modal
        title="导出高清图谱"
        open={exportModalOpen}
        onCancel={() => setExportModalOpen(false)}
        onOk={handleExport}
        confirmLoading={exporting}
        okText="导出"
        cancelText="取消"
        width={400}
      >
        <div className="space-y-4 py-2">
          <div>
            <div className="text-sm font-medium mb-2">导出格式</div>
            <Segmented
              block
              value={exportFormat}
              onChange={(v) => setExportFormat(v as string)}
              options={[
                { label: 'PNG (推荐)', value: 'png', icon: <FileImageOutlined /> },
                { label: 'JPG', value: 'jpg', icon: <FileImageOutlined /> },
                { label: 'SVG', value: 'svg', icon: <FilePdfOutlined /> },
              ]}
            />
          </div>

          <div>
            <div className="text-sm font-medium mb-2">缩放倍率 (越高越清晰)</div>
            <Space>
              <InputNumber
                min={1}
                max={4}
                value={exportScale}
                onChange={(v) => setExportScale(v || 2)}
                addonAfter="x"
              />
              <span className="text-xs opacity-50">
                {exportScale}x = {exportScale * 1920}×{exportScale * 1080}px (估算)
              </span>
            </Space>
          </div>

          <div className="p-2 bg-amber-50 dark:bg-amber-900/10 border border-amber-200 dark:border-amber-800 rounded text-xs text-amber-600">
            提示：导出功能需要安装 <code>html-to-image</code> 包。当前为占位实现，未来将支持直接导出为交付级高清图谱。
          </div>
        </div>
      </Modal>
    </>
  )
}