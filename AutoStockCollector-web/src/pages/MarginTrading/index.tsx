import React, { useEffect, useState, useCallback } from 'react';
import { Card, Row, Col, Typography, DatePicker, Table, Spin, Empty } from 'antd';
import ReactECharts from 'echarts-for-react';
import dayjs from 'dayjs';
import { getMargin } from '@/api/margin';
import type { MarginRecord } from '@/types';
import { fmtAmount } from '@/utils/stockCode';
import StockSearch from '@/components/StockSearch';
import styles from './MarginTrading.module.css';

const { Title } = Typography;
const { RangePicker } = DatePicker;

export default function MarginTrading() {
  const [data, setData] = useState<MarginRecord[]>([]);
  const [dateRange, setDateRange] = useState<[dayjs.Dayjs, dayjs.Dayjs]>([
    dayjs().subtract(30, 'day'),
    dayjs(),
  ]);
  const [code, setCode] = useState('');
  const [loading, setLoading] = useState(false);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const res = await getMargin({
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
      console.error('Failed to fetch margin data:', err);
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

  const chartOption = {
    backgroundColor: 'transparent',
    tooltip: { trigger: 'axis' },
    legend: { data: ['融资余额', '融资买入额'], textStyle: { color: '#8c8c8c' } },
    grid: { left: 60, right: 20, top: 40, bottom: 40 },
    xAxis: { 
      type: 'category', 
      data: data.map(d => d.date || ''), 
      axisLine: { lineStyle: { color: '#303030' } }, 
      axisLabel: { color: '#8c8c8c' } 
    },
    yAxis: { 
      type: 'value', 
      axisLine: { lineStyle: { color: '#303030' } }, 
      axisLabel: { color: '#8c8c8c', formatter: (v: number) => fmtAmount(v) }, 
      splitLine: { lineStyle: { color: '#262626' } } 
    },
    series: [
      { name: '融资余额', type: 'line', data: data.map(d => d.rz_balance || 0), smooth: true, lineStyle: { color: '#ef5350' }, itemStyle: { color: '#ef5350' } },
      { name: '融资买入额', type: 'line', data: data.map(d => d.rz_buy || 0), smooth: true, lineStyle: { color: '#26a69a' }, itemStyle: { color: '#26a69a' } },
    ],
  };

  const columns = [
    { title: '股票代码', dataIndex: 'code', key: 'code', width: 100 },
    { title: '日期', dataIndex: 'date', key: 'date', width: 120 },
    { title: '融资余额', dataIndex: 'rz_balance', key: 'rz_balance', render: (v: number) => v ? fmtAmount(v) : '-' },
    { title: '融资买入额', dataIndex: 'rz_buy', key: 'rz_buy', render: (v: number) => v ? fmtAmount(v) : '-' },
    { title: '融券余量', dataIndex: 'rq_volume', key: 'rq_volume', render: (v: number) => v ? fmtAmount(v) : '-' },
    { title: '融券卖出量', dataIndex: 'rq_sell', key: 'rq_sell', render: (v: number) => v ? fmtAmount(v) : '-' },
  ];

  return (
    <div className={styles.container}>
      <Title level={3} style={{ color: '#fff', marginBottom: 16 }}>融资融券</Title>

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

      <Card className={styles.chartCard} title="融资余额趋势">
        {loading ? (
          <div style={{ textAlign: 'center', padding: 50 }}>
            <Spin />
          </div>
        ) : data.length > 0 ? (
          <ReactECharts option={chartOption} style={{ height: 300 }} />
        ) : (
          <Empty description="暂无融资融券数据" />
        )}
      </Card>

      <Card className={styles.tableCard}>
        {data.length > 0 ? (
          <Table
            columns={columns}
            dataSource={data.map((d, i) => ({ ...d, key: d.code ? `${d.code}-${d.date}` : i }))}
            pagination={{ 
              pageSize: 10,
              showSizeChanger: true,
              showTotal: (total) => `共 ${total} 条`
            }}
            size="small"
          />
        ) : !loading && (
          <Empty description="暂无融资融券数据" />
        )}
      </Card>
    </div>
  );
}