import React, { useEffect, useState, useCallback } from 'react';
import { Card, Row, Col, Typography, Table, Input, Spin, Tag } from 'antd';
import { getNews } from '@/api/news';
import type { NewsItem } from '@/types';
import StockSearch from '@/components/StockSearch';
import styles from './News.module.css';

const { Title } = Typography;
const { Search } = Input;

const mockData: NewsItem[] = [
  { id: '1', code: 'SH600519', title: '贵州茅台：2023年净利润同比增长19%', content: '贵州茅台今日发布年报...', publish_time: '2024-01-15T10:30:00', source: '同花顺', url: '#' },
  { id: '2', code: 'SH601318', title: '中国平安：科技业务收入同比增长25%', content: '中国平安年报显示...', publish_time: '2024-01-14T14:20:00', source: '东方财富', url: '#' },
  { id: '3', code: 'SZ300750', title: '宁德时代：市场份额持续提升', content: '宁德时代在动力电池领域...', publish_time: '2024-01-14T09:15:00', source: '雪球', url: '#' },
  { id: '4', code: 'SH600036', title: '招商银行：零售业务稳健增长', content: '招商银行发布业绩快报...', publish_time: '2024-01-13T16:45:00', source: '证券时报', url: '#' },
  { id: '5', code: 'SZ000001', title: '平安银行：资产质量持续改善', content: '平安银行不良贷款率...', publish_time: '2024-01-13T11:00:00', source: '财联社', url: '#' },
];

export default function News() {
  const [data, setData] = useState<NewsItem[]>([]);
  const [filteredData, setFilteredData] = useState<NewsItem[]>([]);
  const [searchText, setSearchText] = useState('');
  const [codeFilter, setCodeFilter] = useState('');
  const [loading, setLoading] = useState(false);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const res = await getNews({ limit: 100 });
      const resData = res as unknown as { data?: NewsItem[] };
      if (resData?.data && Array.isArray(resData.data)) {
        setData(resData.data);
        setFilteredData(resData.data);
      } else {
        setData(mockData);
        setFilteredData(mockData);
      }
    } catch {
      setData(mockData);
      setFilteredData(mockData);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  useEffect(() => {
    let result = data;
    
    if (searchText) {
      result = result.filter(
        (item) =>
          item.title.toLowerCase().includes(searchText.toLowerCase()) ||
          item.content.toLowerCase().includes(searchText.toLowerCase())
      );
    }

    if (codeFilter) {
      result = result.filter((item) => item.code === codeFilter);
    }

    setFilteredData(result);
  }, [data, searchText, codeFilter]);

  const handleStockSelect = (selectedCode: string) => {
    setCodeFilter(selectedCode);
  };

  const columns = [
    { 
      title: '时间', 
      dataIndex: 'publish_time', 
      key: 'publish_time', 
      width: 120,
      render: (t: string) => new Date(t).toLocaleString('zh-CN', { year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
    },
    { 
      title: '股票', 
      dataIndex: 'code', 
      key: 'code', 
      width: 100,
      render: (code: string) => <Tag color="blue">{code}</Tag>
    },
    { title: '标题', dataIndex: 'title', key: 'title' },
    { title: '来源', dataIndex: 'source', key: 'source', width: 100 },
    {
      title: '操作',
      key: 'action',
      width: 80,
      render: (_: unknown, record: NewsItem) => (
        <a href={record.url} target="_blank" rel="noopener noreferrer">
          查看原文
        </a>
      ),
    },
  ];

  return (
    <div className={styles.container}>
      <Title level={3} style={{ color: '#fff', marginBottom: 16 }}>新闻舆情</Title>

      <Card className={styles.filterCard}>
        <Row gutter={16} align="middle">
          <Col flex="auto">
            <Search
              placeholder="搜索新闻标题或内容"
              value={searchText}
              onChange={(e) => setSearchText(e.target.value)}
              allowClear
            />
          </Col>
          <Col>
            <StockSearch placeholder="按股票筛选" onSelect={handleStockSelect} />
          </Col>
        </Row>
      </Card>

      <Card className={styles.tableCard}>
        {loading ? (
          <div style={{ textAlign: 'center', padding: 50 }}>
            <Spin />
          </div>
        ) : (
          <Table
            columns={columns}
            dataSource={filteredData.map(d => ({ ...d, key: d.id }))}
            pagination={{ pageSize: 15 }}
            size="small"
            expandable={{
              expandedRowRender: (record) => (
                <div style={{ padding: '8px 0' }}>
                  <p style={{ color: '#8c8c8c', margin: 0 }}>{record.content}</p>
                </div>
              ),
              rowExpandable: (record) => !!record.content,
            }}
          />
        )}
      </Card>
    </div>
  );
}