import React, { useEffect, useState, useCallback } from 'react';
import { useParams, useSearchParams } from 'react-router-dom';
import { Card, Row, Col, Typography, DatePicker, Descriptions, Table, Tabs, Spin, message } from 'antd';
import { LoadingOutlined } from '@ant-design/icons';
import { getKline, getLatestKline } from '@/api/kline';
import { getStockInfo } from '@/api/stock';
import { getFinancial } from '@/api/financial';
import { getFundFlow } from '@/api/fundFlow';
import { getNews } from '@/api/news';
import type { KlineRecord, StockInfo, FinancialRecord, NewsItem, FundFlowRecord } from '@/types';
import { fmtAmount, fmtPercent, RISE_COLOR, FALL_COLOR, normalizeCode } from '@/utils/stockCode';
import KlineChart from '@/components/KlineChart';
import StockSearch from '@/components/StockSearch';
import styles from './StockDetail.module.css';
import dayjs from 'dayjs';

const { Title } = Typography;
const { RangePicker } = DatePicker;

export default function StockDetail() {
  const { code: urlCode } = useParams<{ code: string }>();
  const [searchParams] = useSearchParams();
  const [code, setCode] = useState(urlCode || '');
  const [klineData, setKlineData] = useState<KlineRecord[]>([]);
  const [stockInfo, setStockInfo] = useState<StockInfo | null>(null);
  const [financialData, setFinancialData] = useState<FinancialRecord[]>([]);
  const [fundFlowData, setFundFlowData] = useState<FundFlowRecord[]>([]);
  const [newsData, setNewsData] = useState<NewsItem[]>([]);
  const [dateRange, setDateRange] = useState<[dayjs.Dayjs, dayjs.Dayjs]>([
    dayjs().subtract(1, 'year'),
    dayjs(),
  ]);
  const [loading, setLoading] = useState(false);
  const [latestKline, setLatestKline] = useState<KlineRecord | null>(null);

  const fetchData = useCallback(async (stockCode: string) => {
    if (!stockCode) return;
    setLoading(true);
    try {
      const [klineRes, infoRes, financialRes, fundFlowRes, newsRes, latestRes] = await Promise.allSettled([
        getKline(stockCode, {
          start_date: dateRange[0].format('YYYY-MM-DD'),
          end_date: dateRange[1].format('YYYY-MM-DD'),
        }),
        getStockInfo(stockCode),
        getFinancial(stockCode),
        getFundFlow(stockCode),
        getNews({ code: stockCode, limit: 20 }),
        getLatestKline(stockCode),
      ]);

      if (klineRes.status === 'fulfilled' && klineRes.value) {
        const data = klineRes.value as unknown as KlineRecord[];
        if (Array.isArray(data)) {
          setKlineData(data);
        }
      }

      if (infoRes.status === 'fulfilled' && infoRes.value) {
        const data = infoRes.value as unknown as StockInfo;
        if (data?.code) {
          setStockInfo(data);
        }
      }

      if (financialRes.status === 'fulfilled' && financialRes.value) {
        const data = financialRes.value as unknown as FinancialRecord[];
        if (Array.isArray(data)) {
          setFinancialData(data);
        }
      }

      if (fundFlowRes.status === 'fulfilled' && fundFlowRes.value) {
        const data = fundFlowRes.value as unknown as FundFlowRecord[];
        if (Array.isArray(data)) {
          setFundFlowData(data);
        }
      }

      if (newsRes.status === 'fulfilled' && newsRes.value) {
        const data = newsRes.value as unknown as { data?: NewsItem[] };
        if (data?.data && Array.isArray(data.data)) {
          setNewsData(data.data);
        }
      }

      if (latestRes.status === 'fulfilled' && latestRes.value) {
        const data = latestRes.value as unknown as KlineRecord;
        if (data?.date) {
          setLatestKline(data);
        }
      }
    } catch {
      message.error('获取数据失败');
    } finally {
      setLoading(false);
    }
  }, [dateRange]);

  useEffect(() => {
    if (code) {
      fetchData(code);
    }
  }, [code, fetchData]);

  useEffect(() => {
    const codeParam = searchParams.get('code');
    if (codeParam) {
      setCode(normalizeCode(codeParam));
    }
  }, [searchParams]);

  const handleStockSelect = (selectedCode: string) => {
    setCode(selectedCode);
  };

  const financialColumns = [
    { title: '报告期', dataIndex: 'report_date', key: 'report_date' },
    { title: '营业收入', dataIndex: 'revenue', key: 'revenue', render: (v: number) => fmtAmount(v) },
    { title: '净利润', dataIndex: 'net_profit', key: 'net_profit', render: (v: number) => fmtAmount(v) },
    { title: '每股收益', dataIndex: 'eps', key: 'eps', render: (v: number) => v?.toFixed(2) || '-' },
    { title: 'ROE', dataIndex: 'roe', key: 'roe', render: (v: number) => v ? `${v.toFixed(2)}%` : '-' },
    { title: '净资产', dataIndex: 'net_asset', key: 'net_asset', render: (v: number) => fmtAmount(v) },
  ];

  const fundFlowColumns = [
    { title: '日期', dataIndex: 'date', key: 'date' },
    { title: '成交量', dataIndex: 'volume', key: 'volume', render: (v: number) => fmtAmount(v) },
    { title: '成交额', dataIndex: 'amount', key: 'amount', render: (v: number) => fmtAmount(v) },
    { title: '方向', dataIndex: 'direction', key: 'direction', render: (d: string) => d === 'buy' ? '买入' : '卖出' },
  ];

  const newsColumns = [
    { title: '时间', dataIndex: 'publish_time', key: 'publish_time', width: 120, 
      render: (t: string) => new Date(t).toLocaleDateString('zh-CN') },
    { title: '标题', dataIndex: 'title', key: 'title', 
      render: (t: string, r: NewsItem) => <a href={r.url} target="_blank" rel="noopener noreferrer">{t}</a> },
    { title: '来源', dataIndex: 'source', key: 'source', width: 100 },
  ];

  const tabItems = [
    { key: 'financial', label: '财务数据', children: <Table columns={financialColumns} dataSource={financialData.map(d => ({ ...d, key: d.report_date }))} pagination={false} size="small" /> },
    { key: 'fundflow', label: '资金流向', children: <Table columns={fundFlowColumns} dataSource={fundFlowData.map(d => ({ ...d, key: d.date }))} pagination={false} size="small" /> },
    { key: 'news', label: '相关新闻', children: <Table columns={newsColumns} dataSource={newsData.map(d => ({ ...d, key: d.id }))} pagination={false} size="small" /> },
  ];

  return (
    <div className={styles.container}>
      <div className={styles.header}>
        <Title level={3} style={{ color: '#fff', margin: 0 }}>股票详情</Title>
        <StockSearch onSelect={handleStockSelect} />
      </div>

      {latestKline && (
        <Row gutter={16} className={styles.priceRow}>
          <Col>
            <span className={styles.stockName}>{stockInfo?.name || code}</span>
          </Col>
          <Col>
            <span className={styles.price} style={{ color: latestKline.change_rate >= 0 ? RISE_COLOR : FALL_COLOR }}>
              {latestKline.close.toFixed(2)}
            </span>
          </Col>
          <Col>
            <span style={{ color: latestKline.change_rate >= 0 ? RISE_COLOR : FALL_COLOR, fontSize: 18 }}>
              {fmtPercent(latestKline.change_rate)}
            </span>
          </Col>
        </Row>
      )}

      <Card className={styles.infoCard}>
        <Descriptions column={3} size="small">
          <Descriptions.Item label="股票代码">{code}</Descriptions.Item>
          <Descriptions.Item label="市场">{stockInfo?.market || '-'}</Descriptions.Item>
          <Descriptions.Item label="行业">{stockInfo?.industry || '-'}</Descriptions.Item>
          <Descriptions.Item label="上市日期">{stockInfo?.list_date || '-'}</Descriptions.Item>
          <Descriptions.Item label="总股本">{stockInfo?.total_share ? fmtAmount(stockInfo.total_share) : '-'}</Descriptions.Item>
          <Descriptions.Item label="流通股本">{stockInfo?.float_share ? fmtAmount(stockInfo.float_share) : '-'}</Descriptions.Item>
        </Descriptions>
      </Card>

      <Card 
        className={styles.chartCard}
        title="K线走势"
        extra={
          <RangePicker 
            value={dateRange} 
            onChange={(dates) => dates && setDateRange([dates[0]!, dates[1]!])} 
          />
        }
      >
        {loading ? (
          <div style={{ textAlign: 'center', padding: 50 }}>
            <Spin indicator={<LoadingOutlined style={{ fontSize: 48 }} spin />} />
          </div>
        ) : klineData.length > 0 ? (
          <KlineChart data={klineData} height={450} />
        ) : (
          <div style={{ textAlign: 'center', padding: 50, color: '#8c8c8c' }}>
            暂无K线数据
          </div>
        )}
      </Card>

      <Card className={styles.tableCard}>
        <Tabs items={tabItems} />
      </Card>
    </div>
  );
}