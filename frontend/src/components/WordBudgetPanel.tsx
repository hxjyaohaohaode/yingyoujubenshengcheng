import { useState, useEffect, useCallback } from 'react';
import { Card, Slider, InputNumber, Button, Space, Progress, Typography, Table, Tag, Spin, Empty, App, Row, Col, Statistic } from 'antd';
import { EditOutlined, CheckOutlined, BarChartOutlined, ReloadOutlined } from '@ant-design/icons';
import { api } from '../api/client';

const { Text, Title } = Typography;

interface Budget {
  id: string;
  target_words: number;
  actual_words: number;
  chapter_id: string | null;
  scene_id: string | null;
}

interface BudgetData {
  project_id: string;
  budgets: Budget[];
}

interface AllocationResult {
  project_id: string;
  total_words: number;
  allocations: Array<{
    chapter_index: number;
    scene_index: number;
    target_words: number;
  }>;
}

export default function WordBudgetPanel({ projectId }: { projectId: string }) {
  const { message: msgApi } = App.useApp();
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [totalWords, setTotalWords] = useState(500000);
  const [chapterCount, setChapterCount] = useState(10);
  const [scenesPerChapter, setScenesPerChapter] = useState(5);
  const [budgets, setBudgets] = useState<Budget[]>([]);
  const [allocations, setAllocations] = useState<AllocationResult | null>(null);

  const loadBudgets = useCallback(async () => {
    if (!projectId) return;
    setLoading(true);
    try {
      const data = await api.get<BudgetData>(`/projects/${projectId}/word-budget`);
      setBudgets(data.budgets || []);
    } catch (err) {
      console.warn('字数预算加载失败:', err);
      setBudgets([]);
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  const saveBudget = useCallback(async () => {
    if (!projectId) return;
    setSaving(true);
    try {
      const result = await api.put<AllocationResult>(`/projects/${projectId}/word-budget`, {
        total_words: totalWords,
        chapter_count: chapterCount,
        scenes_per_chapter: scenesPerChapter,
      });
      setAllocations(result);
      msgApi.success('字数规划已保存');
      await loadBudgets();
    } catch (err: any) {
      msgApi.error(`保存失败: ${err?.message || '未知错误'}`);
    } finally {
      setSaving(false);
    }
  }, [projectId, totalWords, chapterCount, scenesPerChapter, loadBudgets]);

  useEffect(() => {
    loadBudgets();
  }, [loadBudgets]);

  const totalAllocated = allocations?.allocations?.reduce((sum, a) => sum + a.target_words, 0) || 0;
  const totalActual = budgets.reduce((sum, b) => sum + (b.actual_words || 0), 0);
  const progressPct = totalWords > 0 ? Math.min(100, Math.round((totalActual / totalWords) * 100)) : 0;

  const chapterAllocations = allocations?.allocations?.reduce<Record<number, { target: number; count: number }>>((acc, a) => {
    if (!acc[a.chapter_index]) acc[a.chapter_index] = { target: 0, count: 0 };
    acc[a.chapter_index].target += a.target_words;
    acc[a.chapter_index].count += 1;
    return acc;
  }, {}) || {};

  return (
    <Card
      size="small"
      title={
        <Space>
          <BarChartOutlined />
          <span>字数规划</span>
        </Space>
      }
      extra={
        <Button size="small" icon={<ReloadOutlined />} loading={loading} onClick={loadBudgets}>
          刷新
        </Button>
      }
      style={{ marginBottom: 16 }}
    >
      <Row gutter={[16, 16]}>
        <Col span={24}>
          <div style={{ marginBottom: 16 }}>
            <Progress
              percent={progressPct}
              status={progressPct >= 100 ? 'success' : 'active'}
              format={() => `${totalActual.toLocaleString()} / ${totalWords.toLocaleString()} 字`}
            />
            <Row gutter={16} style={{ marginTop: 8 }}>
              <Col span={6}>
                <Statistic title="总目标" value={totalWords.toLocaleString()} suffix="字" valueStyle={{ fontSize: 14 }} />
              </Col>
              <Col span={6}>
                <Statistic title="已生成" value={totalActual.toLocaleString()} suffix="字" valueStyle={{ fontSize: 14 }} />
              </Col>
              <Col span={6}>
                <Statistic title="进度" value={progressPct} suffix="%" valueStyle={{ fontSize: 14 }} />
              </Col>
              <Col span={6}>
                <Statistic
                  title="剩余"
                  value={Math.max(0, totalWords - totalActual).toLocaleString()}
                  suffix="字"
                  valueStyle={{ fontSize: 14, color: totalWords - totalActual > 0 ? '#1677ff' : '#52c41a' }}
                />
              </Col>
            </Row>
          </div>
        </Col>

        <Col span={24}>
          <div style={{
            padding: '12px',
            background: '#fafafa',
            borderRadius: 8,
            marginBottom: 12,
          }}>
            <Title level={5} style={{ margin: '0 0 12px 0', fontSize: 13 }}>
              <EditOutlined /> 字数分配设置
            </Title>
            <Row gutter={[24, 12]}>
              <Col span={8}>
                <div>
                  <Text style={{ fontSize: 12, marginBottom: 4, display: 'block' }}>总字数目标</Text>
                  <InputNumber
                    style={{ width: '100%' }}
                    value={totalWords}
                    onChange={(v) => setTotalWords(v || 500000)}
                    step={50000}
                    min={10000}
                    max={2000000}
                    formatter={(v) => `${v}`.replace(/\B(?=(\d{3})+(?!\d))/g, ',')}
                  />
                </div>
              </Col>
              <Col span={8}>
                <div>
                  <Text style={{ fontSize: 12, marginBottom: 4, display: 'block' }}>章节数</Text>
                  <InputNumber
                    style={{ width: '100%' }}
                    value={chapterCount}
                    onChange={(v) => setChapterCount(v || 10)}
                    step={1}
                    min={1}
                    max={50}
                  />
                </div>
              </Col>
              <Col span={8}>
                <div>
                  <Text style={{ fontSize: 12, marginBottom: 4, display: 'block' }}>每章场景数</Text>
                  <InputNumber
                    style={{ width: '100%' }}
                    value={scenesPerChapter}
                    onChange={(v) => setScenesPerChapter(v || 5)}
                    step={1}
                    min={1}
                    max={20}
                  />
                </div>
              </Col>
            </Row>

            <div style={{ marginTop: 12 }}>
              <Text style={{ fontSize: 11, color: '#999' }}>
                每章约 {(totalWords / chapterCount).toLocaleString()} 字，
                每场景约 {(totalWords / chapterCount / scenesPerChapter).toLocaleString()} 字
              </Text>
            </div>

            <Button
              type="primary"
              size="small"
              icon={<CheckOutlined />}
              loading={saving}
              onClick={saveBudget}
              style={{ marginTop: 12 }}
            >
              应用字数规划
            </Button>
          </div>
        </Col>

        {Object.keys(chapterAllocations).length > 0 && (
          <Col span={24}>
            <div style={{ maxHeight: 300, overflowY: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
                <thead>
                  <tr style={{ background: '#fafafa' }}>
                    <th style={{ padding: '6px 8px', textAlign: 'left', borderBottom: '2px solid #e8e8e8' }}>章节</th>
                    <th style={{ padding: '6px 8px', textAlign: 'right', borderBottom: '2px solid #e8e8e8' }}>目标字数</th>
                    <th style={{ padding: '6px 8px', textAlign: 'right', borderBottom: '2px solid #e8e8e8' }}>场景数</th>
                    <th style={{ padding: '6px 8px', textAlign: 'right', borderBottom: '2px solid #e8e8e8' }}>每场景</th>
                    <th style={{ padding: '6px 8px', textAlign: 'center', borderBottom: '2px solid #e8e8e8' }}>状态</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(chapterAllocations).map(([chIdx, data]) => (
                    <tr key={chIdx} style={{ borderBottom: '1px solid #f0f0f0' }}>
                      <td style={{ padding: '4px 8px' }}>第{Number(chIdx) + 1}章</td>
                      <td style={{ padding: '4px 8px', textAlign: 'right' }}>{data.target.toLocaleString()}字</td>
                      <td style={{ padding: '4px 8px', textAlign: 'right' }}>{data.count}</td>
                      <td style={{ padding: '4px 8px', textAlign: 'right' }}>
                        {Math.round(data.target / data.count).toLocaleString()}字
                      </td>
                      <td style={{ padding: '4px 8px', textAlign: 'center' }}>
                        <Tag color="processing" style={{ fontSize: 10 }}>规划中</Tag>
                      </td>
                    </tr>
                  ))}
                  <tr style={{ fontWeight: 'bold', borderTop: '2px solid #e8e8e8' }}>
                    <td style={{ padding: '6px 8px' }}>合计</td>
                    <td style={{ padding: '6px 8px', textAlign: 'right' }}>{totalAllocated.toLocaleString()}字</td>
                    <td style={{ padding: '6px 8px', textAlign: 'right' }}></td>
                    <td style={{ padding: '6px 8px', textAlign: 'right' }}></td>
                    <td style={{ padding: '6px 8px', textAlign: 'center' }}>
                      <Tag color="blue" style={{ fontSize: 10 }}>已分配</Tag>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </Col>
        )}
      </Row>
    </Card>
  );
}