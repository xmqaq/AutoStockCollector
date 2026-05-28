import React, { useEffect, useState, useCallback } from 'react';
import { useParams, useSearchParams } from 'react-router-dom';
import { Card, Row, Col, Typography, DatePicker, Descriptions, Table, Tabs, Spin, message, Empty, Alert } from 'antd';
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
  const [hasError, setHasError] = useState(false);

  const fetchData = useCallback(async (stockCode: string) => {
    if (!stockCode) return;
    setLoading(true);
    setHasError(false);
    
    try {
      const results = await Promise.allSettled([
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

      const [klineRes, infoRes, financialRes, fundFlowRes, newsRes, latestRes] = results;

      if (klineRes.status === 'fulfilled' && Array.isArray(klineRes.value)) {
        setKlineData(klineRes.value);
      }

      if (infoRes.status === 'fulfilled' && infoRes.value?.data) {
        setStockInfo(infoRes.value.data);
      }

      if (financialRes.status === 'fulfilled' && Array.isArray(financialRes.value)) {
        setFinancialData(financialRes.value);
      }

      if (fundFlowRes.status === 'fulfilled' && Array.isArray(fundFlowRes.value)) {
        setFundFlowData(fundFlowRes.value);
      }

      if (newsRes.status === 'fulfilled' && newsRes.value?.data && Array.isArray(newsRes.value.data)) {
        setNewsData(newsRes.value.data);
      }

      if (latestRes.status === 'fulfilled' && latestRes.value?.data) {
        setLatestKline(latestRes.value.data);
      }
    } catch (err) {
      console.error('Failed to fetch stock data:', err);
      setHasError(true);
      message.error('获取股票数据失败');
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
    { title: '营业收入', dataIndex: 'revenue', key: 'revenue', render: (v: number) => v ? fmtAmount(v) : '-' },
    { title: '净利润', dataIndex: 'net_profit', key: 'net_profit', render: (v: number) => v ? fmtAmount(v) : '-' },
    { title: '每股收益', dataIndex: 'eps', key: 'eps', render: (v: number) => v?.toFixed(2) || '-' },
    { title: 'ROE', dataIndex: 'roe', key: 'roe', render: (v: number) => v ? `${v.toFixed(2)}%` : '-' },
    { title: '净资产', dataIndex: 'net_asset', key: 'net_asset', render: (v: number) => v ? fmtAmount(v) : '-' },
  ];

  const fundFlowColumns = [
    { title: '日期', dataIndex: 'date', key: 'date' },
    { title: '成交量', dataIndex: 'volume', key: 'volume', render: (v: number) => v ? fmtAmount(v) : '-' },
    { title: '成交额', dataIndex: 'amount', key: 'amount', render: (v: number) => v ? fmtAmount(v) : '-' },
    { title: '方向', dataIndex: 'direction', key: 'direction', render: (d: string) => d === 'buy' ? '买入' : '卖出' },
    { title: '价格', dataIndex: 'price', key: 'price', render: (v: number) => v ? `¥${v.toFixed(2)}` : '-' },
  ];

  const newsColumns = [
    { title: '时间', dataIndex: 'publish_time', key: 'publish_time', width: 120, 
      render: (t: string) => t ? new Date(t).toLocaleDateString('zh-CN') : '-' },
    { title: '标题', dataIndex: 'title', key: 'title', 
      render: (t: string, r: NewsItem) => t ? <a href={r.url} target="_blank" rel="noopener noreferrer">{t}</a> : '-' },
    { title: '来源', dataIndex: 'source', key: 'source', width: 100 },
  ];

  const renderLoading = () => (
    <div style={{ textAlign: 'center', padding: 50 }}>
      <Spin indicator={<LoadingOutlined style={{ fontSize: 48 }} spin />} />
    </div>
  );

  const renderEmpty = (message: string) => (
    <Empty description={message} style={{ padding: 50 }} />
  );

  const tabItems = [
    { 
      key: 'financial', 
      label: '财务数据', 
      children: financialData.length > 0 ? (
        <Table 
          columns={financialColumns} 
          dataSource={financialData.map(d => ({ ...d, key: d.report_date }))} 
          pagination={false} 
          size="small" 
        />
      ) : renderEmpty('暂无财务数据')
    },
    { 
      key: 'fundflow', 
      label: '资金流向', 
      children: fundFlowData.length > 0 ? (
        <Table 
          columns={fundFlowColumns} 
          dataSource={fundFlowData.map(d => ({ ...d, key: `${d.date}-${d.direction}` }))} 
          pagination={false} 
          size="small" 
        />
      ) : renderEmpty('暂无资金流向数据')
    },
    { 
      key: 'news', 
      label: '相关新闻', 
      children: newsData.length > 0 ? (
        <Table 
          columns={newsColumns} 
          dataSource={newsData.map(d => ({ ...d, key: d.id }))} 
          pagination={false} 
          size="small" 
        />
      ) : renderEmpty('暂无相关新闻')
    },
  ];

  return (
    <div className={styles.container}>
      <div className={styles.header}>
        <Title level={3} style={{ color: '#fff', margin: 0 }}>股票详情</Title>
        <StockSearch onSelect={handleStockSelect} />
      </div>

      {code && latestKline && (
        <Alert
          message={
            <Row gutter={16} align="middle">
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
          }
          type="none"
          style={{ background: '#1a1a1a', border: '1px solid #303030' }}
        />
      )}

      <Card className={styles.infoCard}>
        <Descriptions column={3} size="small">
          <Descriptions.Item label="股票代码">{code || '-'}</Descriptions.Item>
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
          renderLoading()
        ) : klineData.length > 0 ? (
          <KlineChart data={klineData} height={450} />
        ) : (
          renderEmpty('暂无K线数据，请输入股票代码查询')
        )}
      </Card>

      <Card className={styles.tableCard}>
        <Tabs items={tabItems} />
      </Card>
    </div>
  );
}