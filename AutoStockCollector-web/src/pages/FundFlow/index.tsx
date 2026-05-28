import React, { useEffect, useState, useCallback } from 'react';
import { Card, Row, Col, Typography, Spin, Empty } from 'antd';
import { getFundFlow } from '@/api/fundFlow';
import type { FundFlowRecord } from '@/types';
import { fmtAmount, RISE_COLOR, FALL_COLOR } from '@/utils/stockCode';
import StockSearch from '@/components/StockSearch';
import ReactECharts from 'echarts-for-react';
import styles from './FundFlow.module.css';

const { Title } = Typography;

export default function FundFlow() {
  const [data, setData] = useState<FundFlowRecord[]>([]);
  const [code, setCode] = useState('');
  const [loading, setLoading] = useState(false);

  const fetchData = useCallback(async () => {
    if (!code) {
      setData([]);
      return;
    }
    
    setLoading(true);
    try {
      const res = await getFundFlow(code);
      if (Array.isArray(res)) {
        setData(res);
      } else {
        setData([]);
      }
    } catch (err) {
      console.error('Failed to fetch fund flow data:', err);
      setData([]);
    } finally {
      setLoading(false);
    }
  }, [code]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const handleStockSelect = (selectedCode: string) => {
    setCode(selectedCode);
  };

  const buyData = data.filter(d => d.direction === 'buy');
  const sellData = data.filter(d => d.direction === 'sell');
  const totalBuy = buyData.reduce((sum, d) => sum + (d.amount || 0), 0);
  const totalSell = sellData.reduce((sum, d) => sum + (d.amount || 0), 0);

  const barOption = {
    backgroundColor: 'transparent',
    tooltip: { trigger: 'axis' },
    legend: { data: ['买入', '卖出'], textStyle: { color: '#8c8c8c' } },
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
      { name: '买入', type: 'bar', data: data.map(d => d.direction === 'buy' ? d.amount : 0), itemStyle: { color: RISE_COLOR } },
      { name: '卖出', type: 'bar', data: data.map(d => d.direction === 'sell' ? d.amount : 0), itemStyle: { color: FALL_COLOR } },
    ],
  };

  return (
    <div className={styles.container}>
      <Title level={3} style={{ color: '#fff', marginBottom: 16 }}>资金流向</Title>

      <Card className={styles.filterCard}>
        <Row gutter={16} align="middle">
          <Col>
            <span style={{ color: '#8c8c8c', marginRight: 8 }}>选择股票：</span>
            <StockSearch placeholder="输入股票代码" onSelect={handleStockSelect} />
          </Col>
        </Row>
      </Card>

      <Row gutter={16} className={styles.statsRow}>
        <Col span={6}>
          <Card className={styles.statCard}>
            <div style={{ color: '#8c8c8c' }}>大单买入总额</div>
            <div style={{ color: RISE_COLOR, fontSize: 24, fontWeight: 'bold' }}>{fmtAmount(totalBuy)}</div>
          </Card>
        </Col>
        <Col span={6}>
          <Card className={styles.statCard}>
            <div style={{ color: '#8c8c8c' }}>大单卖出总额</div>
            <div style={{ color: FALL_COLOR, fontSize: 24, fontWeight: 'bold' }}>{fmtAmount(totalSell)}</div>
          </Card>
        </Col>
        <Col span={6}>
          <Card className={styles.statCard}>
            <div style={{ color: '#8c8c8c' }}>净买入额</div>
            <div style={{ color: totalBuy - totalSell >= 0 ? RISE_COLOR : FALL_COLOR, fontSize: 24, fontWeight: 'bold' }}>
              {totalBuy - totalSell >= 0 ? '+' : ''}{fmtAmount(totalBuy - totalSell)}
            </div>
          </Card>
        </Col>
        <Col span={6}>
          <Card className={styles.statCard}>
            <div style={{ color: '#8c8c8c' }}>记录数</div>
            <div style={{ color: '#fff', fontSize: 24, fontWeight: 'bold' }}>{data.length}</div>
          </Card>
        </Col>
      </Row>

      <Card className={styles.chartCard} title="资金流向柱状图">
        {loading ? (
          <div style={{ textAlign: 'center', padding: 50 }}>
            <Spin />
          </div>
        ) : data.length > 0 ? (
          <ReactECharts option={barOption} style={{ height: 300 }} />
        ) : (
          <Empty description={code ? "暂无资金流向数据" : "请选择股票查看资金流向"} />
        )}
      </Card>
    </div>
  );
}