import React, { useEffect, useState, useCallback } from 'react';
import { Card, Row, Col, Typography, Table, Input, Spin, Tag, Empty } from 'antd';
import { getNews } from '@/api/news';
import type { NewsItem } from '@/types';
import StockSearch from '@/components/StockSearch';
import styles from './News.module.css';

const { Title } = Typography;
const { Search } = Input;

export default function News() {
  const [data, setData] = useState<NewsItem[]>([]);
  const [filteredData, setFilteredData] = useState<NewsItem[]>([]);
  const [searchText, setSearchText] = useState('');
  const [codeFilter, setCodeFilter] = useState('');
  const [loading, setLoading] = useState(false);
  const [total, setTotal] = useState(0);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const res = await getNews({ limit: 100 });
      if (res?.data && Array.isArray(res.data)) {
        setData(res.data);
        setFilteredData(res.data);
        setTotal(res.count || res.data.length);
      } else {
        setData([]);
        setFilteredData([]);
        setTotal(0);
      }
    } catch (err) {
      console.error('Failed to fetch news:', err);
      setData([]);
      setFilteredData([]);
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
          (item.title && item.title.toLowerCase().includes(searchText.toLowerCase())) ||
          (item.content && item.content.toLowerCase().includes(searchText.toLowerCase()))
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

  const handleSearch = (value: string) => {
    setSearchText(value);
  };

  const formatDate = (dateStr: string | undefined) => {
    if (!dateStr) return '-';
    try {
      return new Date(dateStr).toLocaleString('zh-CN', {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
      });
    } catch {
      return '-';
    }
  };

  const columns = [
    {
      title: '时间',
      key: 'time',
      width: 150,
      render: (_: unknown, record: NewsItem) => formatDate(record.publish_time || record.publish_date),
    },
    {
      title: '股票',
      dataIndex: 'code',
      key: 'stock',
      width: 100,
      render: (code: string) => code ? <Tag color="blue">{code}</Tag> : '-',
    },
    { title: '标题', dataIndex: 'title', key: 'title', ellipsis: true },
    { title: '来源', dataIndex: 'source', key: 'source', width: 100 },
    {
      title: '操作',
      key: 'action',
      width: 80,
      render: (_: unknown, record: NewsItem) =>
        record.url ? (
          <a href={record.url} target="_blank" rel="noopener noreferrer">
            查看原文
          </a>
        ) : '-',
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
              onSearch={handleSearch}
              onChange={(e) => setSearchText(e.target.value)}
              allowClear
              enterButton="搜索"
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
        ) : filteredData.length > 0 ? (
          <Table
            columns={columns}
            dataSource={filteredData.map((d, i) => ({ ...d, key: d.id || d.title || String(i) }))}
            pagination={{
              pageSize: 15,
              total: total,
              showSizeChanger: true,
              showQuickJumper: true,
              showTotal: (tot) => `共 ${tot} 条`,
            }}
            size="small"
            expandable={{
              expandedRowRender: (record) => (
                <div style={{ padding: '8px 0' }}>
                  <p style={{ color: '#8c8c8c', margin: 0 }}>
                    {record.content || '暂无详细内容'}
                  </p>
                </div>
              ),
              rowExpandable: (record) => !!record.content,
            }}
          />
        ) : (
          <Empty description={data.length === 0 ? '暂无新闻数据' : '未找到匹配的新闻'} />
        )}
      </Card>
    </div>
  );
}