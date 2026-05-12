import { Skeleton, Card, Row, Col } from 'antd'

interface SkeletonBlockProps {
  rows?: number
  active?: boolean
}

function SkeletonBlock({ rows = 3, active = true }: SkeletonBlockProps) {
  return (
    <Skeleton
      active={active}
      paragraph={{ rows, width: Array.from({ length: rows }, (_, i) => (i === rows - 1 ? '60%' : '100%')) }}
      title={{ width: '40%' }}
    />
  )
}

export function SkeletonDashboard() {
  return (
    <div className="space-y-4">
      <Row gutter={[16, 16]}>
        {[1, 2, 3, 4].map((i) => (
          <Col xs={12} sm={12} md={6} key={i}>
            <Card size="small">
              <Skeleton active paragraph={{ rows: 1 }} title={{ width: '60%' }} />
            </Card>
          </Col>
        ))}
      </Row>
      <Row gutter={[16, 16]}>
        <Col xs={24} md={14}>
          <Card title={<Skeleton.Input active size="small" style={{ width: 120 }} />}>
            <SkeletonBlock rows={4} />
          </Card>
        </Col>
        <Col xs={24} md={10}>
          <Card title={<Skeleton.Input active size="small" style={{ width: 100 }} />}>
            <SkeletonBlock rows={4} />
          </Card>
        </Col>
      </Row>
      <Row gutter={[16, 16]}>
        <Col span={24}>
          <Card title={<Skeleton.Input active size="small" style={{ width: 140 }} />}>
            <SkeletonBlock rows={3} />
          </Card>
        </Col>
      </Row>
    </div>
  )
}

export function SkeletonSceneWorkshop() {
  return (
    <div className="space-y-4">
      <Row gutter={[16, 16]}>
        <Col xs={24} md={8}>
          <Card size="small">
            <Skeleton active paragraph={{ rows: 6 }} title={{ width: '50%' }} />
          </Card>
        </Col>
        <Col xs={24} md={16}>
          <Card>
            <Skeleton active paragraph={{ rows: 8 }} title={{ width: '40%' }} />
          </Card>
        </Col>
      </Row>
    </div>
  )
}

export function SkeletonForeshadows() {
  return (
    <div className="space-y-4">
      <Row gutter={[16, 16]}>
        {[1, 2, 3].map((i) => (
          <Col xs={24} md={8} key={i}>
            <Card size="small">
              <Skeleton active paragraph={{ rows: 4 }} title={{ width: '55%' }} />
            </Card>
          </Col>
        ))}
      </Row>
    </div>
  )
}

export function SkeletonCharacters() {
  return (
    <div className="space-y-4">
      <Row gutter={[16, 16]}>
        {[1, 2, 3, 4].map((i) => (
          <Col xs={24} sm={12} md={6} key={i}>
            <Card size="small">
              <Skeleton.Avatar active size="large" shape="circle" className="mb-3" />
              <Skeleton active paragraph={{ rows: 3 }} title={{ width: '60%' }} />
            </Card>
          </Col>
        ))}
      </Row>
    </div>
  )
}

export function SkeletonChapterOutline() {
  return (
    <div className="space-y-4">
      <Row gutter={[16, 16]}>
        <Col xs={24} md={16}>
          <Card title={<Skeleton.Input active size="small" style={{ width: 140 }} />}>
            <SkeletonBlock rows={6} />
          </Card>
        </Col>
        <Col xs={24} md={8}>
          <Card size="small">
            <Skeleton active paragraph={{ rows: 4 }} title={{ width: '50%' }} />
          </Card>
        </Col>
      </Row>
    </div>
  )
}

export function SkeletonReviewPanel() {
  return (
    <div className="space-y-4">
      <Row gutter={[16, 16]}>
        <Col span={24}>
          <Card>
            <Skeleton active paragraph={{ rows: 5 }} title={{ width: '45%' }} />
          </Card>
        </Col>
      </Row>
      <Row gutter={[16, 16]}>
        <Col xs={24} md={12}>
          <Card size="small">
            <Skeleton active paragraph={{ rows: 3 }} title={{ width: '50%' }} />
          </Card>
        </Col>
        <Col xs={24} md={12}>
          <Card size="small">
            <Skeleton active paragraph={{ rows: 3 }} title={{ width: '50%' }} />
          </Card>
        </Col>
      </Row>
    </div>
  )
}

export function SkeletonEmotionCurve() {
  return (
    <div className="space-y-4">
      <Card title={<Skeleton.Input active size="small" style={{ width: 130 }} />}>
        <Skeleton active paragraph={{ rows: 1 }} title={false} />
        <div style={{ height: 300, background: 'var(--skeleton-color, rgba(190,190,190,0.2))', borderRadius: 8, marginTop: 16 }} />
      </Card>
    </div>
  )
}

export function SkeletonWorldSettings() {
  return (
    <div className="space-y-4">
      <Row gutter={[16, 16]}>
        <Col span={24}>
          <Card title={<Skeleton.Input active size="small" style={{ width: 120 }} />}>
            <SkeletonBlock rows={5} />
          </Card>
        </Col>
      </Row>
      <Row gutter={[16, 16]}>
        <Col xs={24} md={12}>
          <Card size="small" title={<Skeleton.Input active size="small" style={{ width: 100 }} />}>
            <SkeletonBlock rows={3} />
          </Card>
        </Col>
        <Col xs={24} md={12}>
          <Card size="small" title={<Skeleton.Input active size="small" style={{ width: 100 }} />}>
            <SkeletonBlock rows={3} />
          </Card>
        </Col>
      </Row>
    </div>
  )
}

export function SkeletonExport() {
  return (
    <div className="space-y-4">
      <Row gutter={[16, 16]}>
        {[1, 2, 3].map((i) => (
          <Col xs={24} md={8} key={i}>
            <Card size="small">
              <Skeleton active paragraph={{ rows: 2 }} title={{ width: '50%' }} />
            </Card>
          </Col>
        ))}
      </Row>
    </div>
  )
}

export function SkeletonSettings() {
  return (
    <div className="space-y-4">
      <Card title={<Skeleton.Input active size="small" style={{ width: 100 }} />}>
        <SkeletonBlock rows={4} />
      </Card>
      <Card title={<Skeleton.Input active size="small" style={{ width: 120 }} />}>
        <SkeletonBlock rows={3} />
      </Card>
    </div>
  )
}

export function SkeletonGeneric() {
  return (
    <div className="space-y-4">
      <Card>
        <Skeleton active paragraph={{ rows: 6 }} title={{ width: '40%' }} />
      </Card>
    </div>
  )
}

export default function GlobalLoading({ pageType }: { pageType?: string }) {
  const skeletonMap: Record<string, React.ReactNode> = {
    dashboard: <SkeletonDashboard />,
    world: <SkeletonWorldSettings />,
    characters: <SkeletonCharacters />,
    foreshadows: <SkeletonForeshadows />,
    chapters: <SkeletonChapterOutline />,
    scenes: <SkeletonSceneWorkshop />,
    review: <SkeletonReviewPanel />,
    'emotion-curve': <SkeletonEmotionCurve />,
    export: <SkeletonExport />,
    settings: <SkeletonSettings />,
    pipeline: <SkeletonDashboard />,
    'script-viz': <SkeletonGeneric />,
    'script-preview': <SkeletonGeneric />,
  }

  return (
    <div className="p-4 animate-fade-in">
      {pageType && skeletonMap[pageType] ? skeletonMap[pageType] : <SkeletonGeneric />}
    </div>
  )
}

export function getEmptyMessage(page: string): string {
  const messages: Record<string, string> = {
    dashboard: '创建第一个项目，开启智能剧本创作之旅',
    world: '项目世界观尚未配置，请先生成或编辑世界观设定',
    characters: '尚未创建角色，请先构建角色体系',
    foreshadows: '尚未设计伏笔体系，伏笔是互动影游的核心驱动力',
    chapters: '尚未规划章节大纲，请先构建叙事结构',
    scenes: '请先创建章节和场景，再开始场景创作',
    review: '所有场景审核完成 🎉',
    'emotion-curve': '暂无情感曲线数据，完成场景创作后将自动生成',
    export: '暂无可导出内容，请先完成场景创作',
    settings: '项目设置将在此处显示',
  }
  return messages[page] || '暂无数据'
}
