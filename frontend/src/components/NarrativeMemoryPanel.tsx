import { useState, useEffect, useCallback } from 'react';
import { Card, Tabs, Tag, Spin, Empty, Button, Space, Typography, Progress } from 'antd';
import {
  UserOutlined, BulbOutlined, ClockCircleOutlined,
  TeamOutlined, GlobalOutlined, FlagOutlined,
  ReloadOutlined, CheckCircleOutlined, WarningOutlined,
} from '@ant-design/icons';
import { api } from '../api/client';

const { Text, Paragraph, Title } = Typography;

interface MemoryItem {
  id: string;
  content: string;
  entity_id?: string;
}

interface CoherenceCheck {
  layer: string;
  passed: boolean;
  score: number;
  issues: string[];
  suggestions: string[];
}

interface NarrativeMemoryData {
  project_id: string;
  narrative_context: string;
}

interface CategoryMemories {
  category: string;
  memories: MemoryItem[];
}

const CATEGORY_ICONS: Record<string, React.ReactNode> = {
  characters: <UserOutlined />,
  character: <UserOutlined />,
  active_foreshadows: <BulbOutlined />,
  foreshadow: <BulbOutlined />,
  recent_events: <ClockCircleOutlined />,
  timeline: <ClockCircleOutlined />,
  relationships: <TeamOutlined />,
  relation: <TeamOutlined />,
  worldbuilding: <GlobalOutlined />,
  themes: <FlagOutlined />,
  theme: <FlagOutlined />,
};

const CATEGORY_LABELS: Record<string, string> = {
  characters: '角色状态',
  character: '角色状态',
  active_foreshadows: '活跃伏笔',
  foreshadow: '活跃伏笔',
  recent_events: '最近事件',
  timeline: '最近事件',
  relationships: '角色关系',
  relation: '角色关系',
  worldbuilding: '世界观规则',
  themes: '主题约束',
  theme: '主题约束',
};

const LAYER_LABELS: Record<string, string> = {
  '角色一致性': '角色',
  '时间线一致性': '时间线',
  '伏笔一致性': '伏笔',
  '世界观一致性': '世界观',
  '主题一致性': '主题',
};

function parseNarrativeSections(context: string): { label: string; items: string[] }[] {
  const sections: { label: string; items: string[] }[] = [];
  const lines = context.split('\n');
  let currentLabel = '';
  let currentItems: string[] = [];

  for (const line of lines) {
    if (line.startsWith('## ')) {
      if (currentLabel && currentItems.length > 0) {
        sections.push({ label: currentLabel, items: [...currentItems] });
      }
      currentLabel = line.replace('## ', '').trim();
      currentItems = [];
    } else if (line.startsWith('- ') || line.match(/^\d+\.\s/)) {
      const content = line.replace(/^[\-\d]+\.\s*/, '').trim();
      if (content && !content.startsWith('---')) {
        currentItems.push(content);
      }
    }
  }

  if (currentLabel && currentItems.length > 0) {
    sections.push({ label: currentLabel, items: [...currentItems] });
  }

  return sections;
}

export default function NarrativeMemoryPanel({ projectId }: { projectId: string }) {
  const [loading, setLoading] = useState(false);
  const [context, setContext] = useState<NarrativeMemoryData | null>(null);
  const [categories, setCategories] = useState<CategoryMemories[]>([]);
  const [coherenceReport, setCoherenceReport] = useState<{
    project_id: string;
    structure_issues: Array<{ severity: string; description: string }>;
    rhythm_issues: Array<{ severity: string; description: string }>;
    unresolved_foreshadows: Array<{ name: string; status: string }>;
    character_arc_issues: Array<{ character: string; issue: string }>;
    overall_score: number;
    summary: string;
  } | null>(null);
  const [reviewLoading, setReviewLoading] = useState(false);
  const [activeTab, setActiveTab] = useState('memory');

  const loadMemory = useCallback(async () => {
    if (!projectId) return;
    setLoading(true);
    try {
      const [ctxData, catPromises] = await Promise.all([
        api.get<NarrativeMemoryData>(`/projects/${projectId}/narrative-memory`),
        Promise.all([
          api.get<CategoryMemories>(`/projects/${projectId}/narrative-memory/category/character`).catch(() => ({ category: 'character', memories: [] })),
          api.get<CategoryMemories>(`/projects/${projectId}/narrative-memory/category/foreshadow`).catch(() => ({ category: 'foreshadow', memories: [] })),
          api.get<CategoryMemories>(`/projects/${projectId}/narrative-memory/category/worldbuilding`).catch(() => ({ category: 'worldbuilding', memories: [] })),
          api.get<CategoryMemories>(`/projects/${projectId}/narrative-memory/category/relation`).catch(() => ({ category: 'relation', memories: [] })),
        ]),
      ]);
      setContext(ctxData);
      setCategories(catPromises.filter(c => c.memories && c.memories.length > 0));
    } catch (err) {
      console.warn('叙事记忆加载失败:', err);
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  const runGlobalReview = useCallback(async () => {
    if (!projectId) return;
    setReviewLoading(true);
    try {
      const report = await api.post<any>(`/projects/${projectId}/review/global`);
      setCoherenceReport(report);
    } catch (err) {
      console.warn('全局审查失败:', err);
    } finally {
      setReviewLoading(false);
    }
  }, [projectId]);

  useEffect(() => {
    loadMemory();
  }, [loadMemory]);

  const sections = context?.narrative_context ? parseNarrativeSections(context.narrative_context) : [];

  return (
    <Card
      size="small"
      title={
        <Space>
          <BulbOutlined />
          <span>叙事记忆中枢</span>
        </Space>
      }
      extra={
        <Space size="small">
          <Button size="small" icon={<ReloadOutlined />} loading={loading} onClick={loadMemory}>
            刷新
          </Button>
          <Button
            size="small"
            type="primary"
            icon={<CheckCircleOutlined />}
            loading={reviewLoading}
            onClick={runGlobalReview}
          >
            全局审查
          </Button>
        </Space>
      }
      style={{ marginBottom: 16 }}
    >
      <Tabs
        activeKey={activeTab}
        onChange={setActiveTab}
        size="small"
        items={[
          {
            key: 'memory',
            label: '叙事记忆',
            children: loading ? (
              <div style={{ textAlign: 'center', padding: 24 }}><Spin /></div>
            ) : sections.length === 0 ? (
              <Empty description="暂无叙事记忆数据" image={Empty.PRESENTED_IMAGE_SIMPLE} />
            ) : (
              <div style={{ maxHeight: 400, overflowY: 'auto' }}>
                {sections.map((section, idx) => (
                  <div key={idx} style={{ marginBottom: 16 }}>
                    <Title level={5} style={{ margin: '0 0 8px 0', fontSize: 13 }}>
                      {section.label}
                    </Title>
                    {section.items.map((item, i) => (
                      <div
                        key={i}
                        style={{
                          padding: '6px 10px',
                          marginBottom: 4,
                          background: '#fafafa',
                          borderRadius: 4,
                          fontSize: 12,
                          lineHeight: 1.6,
                          borderLeft: '3px solid #1677ff',
                        }}
                      >
                        {item}
                      </div>
                    ))}
                    {section.items.length === 0 && (
                      <Text type="secondary" style={{ fontSize: 12 }}>暂无数据</Text>
                    )}
                  </div>
                ))}
              </div>
            ),
          },
          {
            key: 'categories',
            label: '分类记忆',
            children: loading ? (
              <div style={{ textAlign: 'center', padding: 24 }}><Spin /></div>
            ) : categories.length === 0 ? (
              <Empty description="暂无分类记忆" image={Empty.PRESENTED_IMAGE_SIMPLE} />
            ) : (
              <div style={{ maxHeight: 400, overflowY: 'auto' }}>
                {categories.map((cat) => (
                  <div key={cat.category} style={{ marginBottom: 12 }}>
                    <Space style={{ marginBottom: 4 }}>
                      {CATEGORY_ICONS[cat.category]}
                      <Text strong style={{ fontSize: 12 }}>
                        {CATEGORY_LABELS[cat.category] || cat.category}
                      </Text>
                      <Tag color="blue" style={{ fontSize: 10 }}>{cat.memories.length}</Tag>
                    </Space>
                    {cat.memories.map((mem) => (
                      <div key={mem.id} style={{
                        padding: '4px 8px',
                        marginBottom: 2,
                        fontSize: 11,
                        background: '#f5f5f5',
                        borderRadius: 3,
                      }}>
                        <Text ellipsis={{ tooltip: mem.content }}>{mem.content}</Text>
                        {mem.entity_id && (
                          <Tag color="geekblue" style={{ fontSize: 10, marginLeft: 4 }}>
                            {mem.entity_id}
                          </Tag>
                        )}
                      </div>
                    ))}
                  </div>
                ))}
              </div>
            ),
          },
          {
            key: 'review',
            label: '全局审查',
            children: reviewLoading ? (
              <div style={{ textAlign: 'center', padding: 24 }}><Spin tip="正在执行全局审查..." /></div>
            ) : coherenceReport ? (
              <div style={{ maxHeight: 400, overflowY: 'auto' }}>
                <div style={{ textAlign: 'center', marginBottom: 12 }}>
                  <Progress
                    type="circle"
                    percent={Math.round(coherenceReport.overall_score)}
                    size={80}
                    format={(p) => `${p}分`}
                    status={coherenceReport.overall_score >= 70 ? 'success' : 'exception'}
                  />
                  <Paragraph style={{ marginTop: 4, fontSize: 11, color: '#666' }}>
                    {coherenceReport.summary}
                  </Paragraph>
                </div>

                {coherenceReport.structure_issues?.length > 0 && (
                  <div style={{ marginBottom: 12 }}>
                    <Text strong style={{ fontSize: 12 }}>结构问题</Text>
                    {coherenceReport.structure_issues.map((issue, i) => (
                      <Tag key={i} color={issue.severity === 'high' ? 'red' : 'orange'} style={{ margin: 2, fontSize: 11 }}>
                        {issue.description}
                      </Tag>
                    ))}
                  </div>
                )}

                {coherenceReport.rhythm_issues?.length > 0 && (
                  <div style={{ marginBottom: 12 }}>
                    <Text strong style={{ fontSize: 12 }}>节奏问题</Text>
                    {coherenceReport.rhythm_issues.map((issue, i) => (
                      <Tag key={i} color="purple" style={{ margin: 2, fontSize: 11 }}>
                        {issue.description}
                      </Tag>
                    ))}
                  </div>
                )}

                {coherenceReport.unresolved_foreshadows?.length > 0 && (
                  <div style={{ marginBottom: 12 }}>
                    <Text strong style={{ fontSize: 12 }}>
                      <WarningOutlined style={{ color: '#faad14' }} /> 未闭合伏笔
                    </Text>
                    {coherenceReport.unresolved_foreshadows.map((fs, i) => (
                      <Tag key={i} color="gold" style={{ margin: 2, fontSize: 11 }}>
                        {fs.name}: {fs.status}
                      </Tag>
                    ))}
                  </div>
                )}

                {coherenceReport.character_arc_issues?.length > 0 && (
                  <div style={{ marginBottom: 12 }}>
                    <Text strong style={{ fontSize: 12 }}>角色弧线问题</Text>
                    {coherenceReport.character_arc_issues.map((issue, i) => (
                      <Tag key={i} color="cyan" style={{ margin: 2, fontSize: 11 }}>
                        {issue.character}: {issue.issue}
                      </Tag>
                    ))}
                  </div>
                )}
              </div>
            ) : (
              <Empty description={'点击「全局审查」按钮进行分析'} image={Empty.PRESENTED_IMAGE_SIMPLE} />
            ),
          },
        ]}
      />
    </Card>
  );
}