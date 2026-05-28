import React, { useEffect, useState, useCallback } from 'react';
import { Card, Row, Col, Typography, DatePicker, Table, Spin, Empty } from 'antd';
import { useNavigate } from 'react-router-dom';
import dayjs from 'dayjs';
import { getDragonTiger } from '@/api/dragonTiger';
import type { DragonTigerRecord } from '@/types';
import { fmtAmount, normalizeCode } from '@/utils/stockCode';
import StockSearch from '@/components/StockSearch';
import styles from './DragonTiger.module.css';

const { Title } = Typography;
const { RangePicker } = DatePicker;

export default function DragonTiger() {
  const navigate = useNavigate();
  const [data, setData] = useState<DragonTigerRecord[]>([]);
  const [dateRange, setDateRange] = useState<[dayjs.Dayjs, dayjs.Dayjs]>([
    dayjs().subtract(30, 'day'),
    dayjs(),
  ]);
  const [code, setCode] = useState('');
  const [loading, setLoading] = useState(false);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const res = await getDragonTiger({
        start_date: dateRange[0].format('YYYY-MM-DD'),
        end_date: dateRange[1].format('YYYY-MM-DD'),
        code: code || undefined,
      });
      
      if (res?.data && Array.isArray(res.data)) {
        setData(res.data);
      } else {
        setData([]);
      }
    } catch (err) {
      console.error('Failed to fetch dragon tiger data:', err);
      setData([]);
    } finally {
      setLoading(false);
    }
  }, [dateRange, code]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const handleStockSelect = (selectedCode: string) => {
    setCode(selectedCode);
  };

  const handleRowClick = (record: DragonTigerRecord) => {
    navigate(`/stock/${record.code}`);
  };

  const columns = [
    { title: '股票代码', dataIndex: 'code', key: 'code', width: 100 },
    { title: '股票名称', dataIndex: 'name', key: 'name', width: 120 },
    { title: '日期', dataIndex: 'date', key: 'date', width: 120 },
    { title: '上榜原因', dataIndex: 'reason', key: 'reason' },
    { title: '总成交额', dataIndex: 'total_amount', key: 'total_amount', 
      render: (v: number) => v ? fmtAmount(v) : '-', width: 120 },
    { title: '净买入额', dataIndex: 'net_buy', key: 'net_buy', 
      render: (v: number) => (
        <span style={{ color: v >= 0 ? '#ef5350' : '#26a69a' }}>
          {v ? `${v >= 0 ? '+' : ''}${fmtAmount(v)}` : '-'}
        </span>
      ), width: 120 },
  ];

  return (
    <div className={styles.container}>
      <Title level={3} style={{ color: '#fff', marginBottom: 16 }}>龙虎榜</Title>

      <Card className={styles.filterCard}>
        <Row gutter={16} align="middle">
          <Col>
            <span style={{ color: '#8c8c8c', marginRight: 8 }}>日期范围：</span>
            <RangePicker 
              value={dateRange} 
              onChange={(dates) => dates && setDateRange([dates[0]!, dates[1]!])} 
            />
          </Col>
          <Col>
            <StockSearch placeholder="筛选股票代码" onSelect={handleStockSelect} />
          </Col>
        </Row>
      </Card>

      <Card className={styles.tableCard}>
        {loading ? (
          <div style={{ textAlign: 'center', padding: 50 }}>
            <Spin />
          </div>
        ) : data.length > 0 ? (
          <Table
            columns={columns}
            dataSource={data.map((d, i) => ({ ...d, key: d.code ? `${d.code}-${d.date}` : i }))}
            pagination={{ 
              pageSize: 10,
              showSizeChanger: true,
              showTotal: (total) => `共 ${total} 条`
            }}
            size="small"
            onRow={(record) => ({
              onClick: () => handleRowClick(record),
              style: { cursor: 'pointer' },
            })}
          />
        ) : (
          <Empty description="暂无龙虎榜数据" />
        )}
      </Card>
    </div>
  );
}