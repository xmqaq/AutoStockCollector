import React, { useEffect, useState } from 'react';
import { Card, Row, Col, Statistic, Table, List, Tag, Typography, Alert, Empty, Spin } from 'antd';
import ReactECharts from 'echarts-for-react';
import { ArrowUpOutlined, ArrowDownOutlined, FieldTimeOutlined, CloudServerOutlined } from '@ant-design/icons';
import { getProgressAll, healthCheck } from '@/api/collect';
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

const statusMap: Record<string, { color: string; text: string }> = {
  completed: { color: 'green', text: '已完成' },
  running: { color: 'blue', text: '采集中' },
  pending: { color: 'default', text: '等待中' },
  failed: { color: 'red', text: '失败' },
  cancelled: { color: 'orange', text: '已取消' },
};

export default function Dashboard() {
  const [tasks, setTasks] = useState<TaskProgress[]>([]);
  const [allDone, setAllDone] = useState(false);
  const [news, setNews] = useState<NewsItem[]>([]);
  const [newsCount, setNewsCount] = useState(0);
  const [backendOnline, setBackendOnline] = useState(true);
  const [loading, setLoading] = useState(true);
  const [newsLoading, setNewsLoading] = useState(false);

  const fetchData = async () => {
    try {
      setLoading(true);
      const [progressRes, healthRes] = await Promise.allSettled([
        getProgressAll(),
        healthCheck().catch(() => null),
      ]);

      if (progressRes.status === 'fulfilled' && progressRes.value?.data) {
        const data = progressRes.value.data;
        setTasks(data.tasks || []);
        setAllDone(data.all_done || false);
      }

      if (healthRes.status === 'fulfilled' && healthRes.value) {
        const health = healthRes.value;
        setBackendOnline(health?.status === 'ok' || health?.status === 'healthy');
      } else {
        setBackendOnline(false);
      }
    } catch (err) {
      console.error('Failed to fetch dashboard data:', err);
      setBackendOnline(false);
    } finally {
      setLoading(false);
    }
  };

  const fetchNews = async () => {
    try {
      setNewsLoading(true);
      const res = await getNews({ limit: 100 });
      if (res?.data && Array.isArray(res.data)) {
        setNews(res.data.slice(0, 10));
        setNewsCount(res.count || res.data.length);
      }
    } catch (err) {
      console.error('Failed to fetch news:', err);
    } finally {
      setNewsLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
    fetchNews();
    const timer = setInterval(fetchData, 30000);
    return () => clearInterval(timer);
  }, []);

  const completedCount = tasks.filter((t) => t.status === 'completed').length;
  const dragonTigerTask = tasks.find((t) => t.type === 'dragon_tiger' || t.task_type === 'dragon_tiger');
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
        axisLine: { lineStyle: { width: 6, color: [[completedCount / 8, '#177ddc'], [1, '#262626']] } },
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
    { 
      title: '数据类型', 
      dataIndex: 'type', 
      key: 'type', 
      render: (t: string) => typeNameMap[t] || t 
    },
    { 
      title: '状态', 
      dataIndex: 'status', 
      key: 'status', 
      render: (s: string) => {
        const status = statusMap[s] || { color: 'default', text: s };
        return <Tag color={status.color}>{status.text}</Tag>;
      }
    },
    { 
      title: '成功/失败', 
      key: 'count', 
      render: (_: unknown, r: TaskProgress) => <span>{r.success} / {r.failed}</span> 
    },
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
              styles={{ content: { color: backendOnline ? '#52c41a' : '#ff4d4f', fontSize: 24, fontWeight: 'bold' } }}
              prefix={<CloudServerOutlined />}
            />
          </Card>
        </Col>
      </Row>

      <Row gutter={16}>
        <Col span={16}>
          <Card title="数据采集进度" className={styles.progressCard}>
            <ReactECharts option={gaugeOption} style={{ height: 150 }} />
            {loading ? (
              <div style={{ textAlign: 'center', padding: 16 }}>
                <Spin />
              </div>
            ) : tasks.length > 0 ? (
              <Table 
                columns={columns} 
                dataSource={tasks.map((t) => ({ ...t, key: t.type || t.task_id }))} 
                pagination={false} 
                size="small" 
                style={{ marginTop: 16 }} 
              />
            ) : (
              <Empty description="暂无采集任务" style={{ marginTop: 16 }} />
            )}
          </Card>
        </Col>
        <Col span={8}>
          <Card title="最新新闻" className={styles.newsCard}>
            {newsLoading ? (
              <div style={{ textAlign: 'center', padding: 20 }}>
                <Spin />
              </div>
            ) : recentNews.length > 0 ? (
              <List
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
            ) : (
              <Empty description="暂无新闻" />
            )}
          </Card>
        </Col>
      </Row>
    </div>
  );
}