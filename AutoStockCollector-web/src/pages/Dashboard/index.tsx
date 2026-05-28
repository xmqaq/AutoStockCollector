import React, { useEffect, useState } from 'react';
import { Card, Row, Col, Statistic, Table, List, Tag, Typography, Alert } from 'antd';
import ReactECharts from 'echarts-for-react';
import { ArrowUpOutlined, ArrowDownOutlined, FieldTimeOutlined } from '@ant-design/icons';
import { getProgressAll, getHealth } from '@/api/collect';
import { getNews } from '@/api/news';
import type { TaskProgress, NewsItem } from '@/types';
import styles from './Dashboard.module.css';

const { Title } = Typography;

const typeNameMap: Record<string, string> = {
  kline: 'K线数据',
  stock_info: '股票基础信息',
  financial: '财务数据',
  news: '新闻舆情',
  fund_flow: '资金流向',
  dragon_tiger: '龙虎榜',
  block: '板块数据',
  margin_data: '融资融券',
};

export default function Dashboard() {
  const [tasks, setTasks] = useState<TaskProgress[]>([]);
  const [allDone, setAllDone] = useState(false);
  const [news, setNews] = useState<NewsItem[]>([]);
  const [newsCount, setNewsCount] = useState(0);
  const [backendOnline, setBackendOnline] = useState(true);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchData = async () => {
      try {
        setLoading(true);
        const [progressRes, healthRes, newsRes] = await Promise.allSettled([
          getProgressAll(),
          getHealth().catch(() => null),
          getNews({ limit: 100 }),
        ]);

        if (progressRes.status === 'fulfilled' && progressRes.value) {
          const data = progressRes.value as unknown as { data?: { tasks?: TaskProgress[]; all_done?: boolean } };
          if (data?.data) {
            setTasks(data.data.tasks || []);
            setAllDone(data.data.all_done || false);
          }
        }

        if (healthRes.status === 'fulfilled' && healthRes.value) {
          const health = healthRes.value as unknown as { status?: string };
          setBackendOnline(health?.status === 'ok' || health?.status === 'healthy');
        }

        if (newsRes.status === 'fulfilled' && newsRes.value) {
          const newsData = newsRes.value as unknown as { data?: NewsItem[]; count?: number };
          if (newsData?.data) {
            setNews(newsData.data.slice(0, 10));
            setNewsCount(newsData.count || 0);
          }
        }
      } catch (err) {
        console.error('Failed to fetch dashboard data:', err);
      } finally {
        setLoading(false);
      }
    };

    fetchData();
    const timer = setInterval(fetchData, 30000);
    return () => clearInterval(timer);
  }, []);

  const completedCount = tasks.filter((t) => t.status === 'completed').length;
  const dragonTigerTask = tasks.find((t) => t.type === 'dragon_tiger');
  const dragonTigerCount = dragonTigerTask?.success || 0;

  const gaugeOption = {
    series: [
      {
        type: 'gauge',
        startAngle: 180,
        endAngle: 0,
        min: 0,
        max: 8,
        splitNumber: 8,
        axisLine: { lineStyle: { width: 6, color: [[1, '#177ddc']] } },
        pointer: { icon: 'path://M12.8,0.7l12,40.1H0.7L12.8,0.7z', length: '12%', width: 10 },
        axisTick: { length: 6, lineStyle: { color: 'auto', width: 1 } },
        splitLine: { length: 10, lineStyle: { color: 'auto', width: 2 } },
        axisLabel: { color: '#464646', fontSize: 10, distance: -40 },
        detail: { fontSize: 20, offsetCenter: [0, '60%'], valueAnimation: true, formatter: (v: number) => `${v}/8` },
        data: [{ value: completedCount }],
      },
    ],
  };

  const recentNews = news.slice(0, 5);
  const columns = [
    { title: '数据类型', dataIndex: 'type', key: 'type', render: (t: string) => typeNameMap[t] || t },
    { title: '状态', dataIndex: 'status', key: 'status', render: (s: string) => <Tag color={s === 'completed' ? 'green' : s === 'running' ? 'blue' : 'default'}>{s === 'completed' ? '已完成' : s === 'running' ? '采集中' : '等待中'}</Tag> },
    { title: '成功/失败', key: 'count', render: (_: unknown, r: TaskProgress) => <span>{r.success} / {r.failed}</span> },
  ];

  return (
    <div className={styles.container}>
      {allDone && <Alert message="所有 8 类数据采集完成" type="success" showIcon style={{ marginBottom: 16 }} />}

      <Title level={3} className={styles.pageTitle}>数据采集总览</Title>

      <Row gutter={16} className={styles.statsRow}>
        <Col span={6}>
          <Card className={styles.statCard}>
            <Statistic
              title="数据采集完成度"
              value={`${completedCount}/8`}
              suffix={<span style={{ fontSize: 14 }}>类</span>}
              prefix={<FieldTimeOutlined />}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card className={styles.statCard}>
            <Statistic
              title="龙虎榜记录数"
              value={dragonTigerCount}
              prefix={<ArrowUpOutlined style={{ color: '#ef5350' }} />}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card className={styles.statCard}>
            <Statistic
              title="最新新闻条数"
              value={newsCount}
              prefix={<ArrowDownOutlined style={{ color: '#26a69a' }} />}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card className={styles.statCard}>
            <Statistic
              title="后端服务状态"
              value={backendOnline ? '在线' : '离线'}
              valueStyle={{ color: backendOnline ? '#52c41a' : '#ff4d4f' }}
            />
          </Card>
        </Col>
      </Row>

      <Row gutter={16}>
        <Col span={16}>
          <Card title="数据采集进度" className={styles.progressCard}>
            <ReactECharts option={gaugeOption} style={{ height: 150 }} />
            <Table columns={columns} dataSource={tasks.map((t) => ({ ...t, key: t.type }))} pagination={false} size="small" loading={loading} style={{ marginTop: 16 }} />
          </Card>
        </Col>
        <Col span={8}>
          <Card title="最新新闻" className={styles.newsCard}>
            <List
              loading={loading}
              dataSource={recentNews}
              renderItem={(item) => (
                <List.Item>
                  <List.Item.Meta
                    title={<a href={item.url} target="_blank" rel="noopener noreferrer">{item.title}</a>}
                    description={new Date(item.publish_time).toLocaleDateString('zh-CN')}
                  />
                </List.Item>
              )}
            />
          </Card>
        </Col>
      </Row>
    </div>
  );
}