import React, { useEffect, useState, useCallback } from 'react';
import { Card, Row, Col, Typography, Table, Spin, Empty } from 'antd';
import ReactECharts from 'echarts-for-react';
import { getSectorList, getSectorStocks } from '@/api/sector';
import type { SectorItem } from '@/types';
import { fmtAmount, fmtPercent, RISE_COLOR, FALL_COLOR } from '@/utils/stockCode';
import styles from './SectorFlow.module.css';

const { Title } = Typography;

export default function SectorFlow() {
  const [sectorData, setSectorData] = useState<SectorItem[]>([]);
  const [selectedSector, setSelectedSector] = useState<string | null>(null);
  const [sectorStocks, setSectorStocks] = useState<Array<{ code: string; name: string; change_rate: number; net_flow: number }>>([]);
  const [loading, setLoading] = useState(false);
  const [stocksLoading, setStocksLoading] = useState(false);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const res = await getSectorList();
      if (res?.data && Array.isArray(res.data)) {
        setSectorData(res.data);
      } else {
        setSectorData([]);
      }
    } catch (err) {
      console.error('Failed to fetch sector data:', err);
      setSectorData([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  useEffect(() => {
    if (selectedSector) {
      setStocksLoading(true);
      getSectorStocks(selectedSector)
        .then((res) => {
          if (res?.data && Array.isArray(res.data)) {
            setSectorStocks(res.data);
          } else {
            setSectorStocks([]);
          }
        })
        .catch(() => {
          setSectorStocks([]);
        })
        .finally(() => {
          setStocksLoading(false);
        });
    } else {
      setSectorStocks([]);
    }
  }, [selectedSector]);

  const handleSectorClick = (sectorName: string) => {
    setSelectedSector(sectorName);
  };

  const treemapOption = {
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'item',
      formatter: (params: { name: string; value: number; data: { change_rate: number } }) => {
        return `${params.name}<br/>净流入: ${fmtAmount(params.value)}<br/>涨跌幅: ${fmtPercent(params.data?.change_rate || 0)}`;
      },
    },
    series: [
      {
        type: 'treemap',
        data: sectorData.map((s) => ({
          name: s.name || '',
          value: Math.abs(s.net_flow || 0),
          change_rate: s.change_rate || 0,
          itemStyle: {
            color: (s.net_flow || 0) >= 0 ? RISE_COLOR : FALL_COLOR,
          },
        })),
        label: {
          show: true,
          formatter: '{b}',
          color: '#fff',
        },
        upperLabel: { show: false },
        levels: [
          { itemStyle: { borderWidth: 4, gapWidth: 4 } },
        ],
      },
    ],
  };

  const stockColumns = [
    { title: '股票代码', dataIndex: 'code', key: 'code', width: 100 },
    { title: '股票名称', dataIndex: 'name', key: 'name', width: 120 },
    { title: '涨跌幅', dataIndex: 'change_rate', key: 'change_rate', 
      render: (v: number) => (
        <span style={{ color: v >= 0 ? RISE_COLOR : FALL_COLOR }}>
          {v ? fmtPercent(v) : '-'}
        </span>
      ) },
    { title: '净流入', dataIndex: 'net_flow', key: 'net_flow', render: (v: number) => v ? fmtAmount(v) : '-' },
  ];

  return (
    <div className={styles.container}>
      <Title level={3} style={{ color: '#fff', marginBottom: 16 }}>板块资金流向</Title>

      <Row gutter={16}>
        <Col span={selectedSector ? 12 : 24}>
          <Card className={styles.chartCard} title="板块资金流向 Treemap">
            {loading ? (
              <div style={{ textAlign: 'center', padding: 50 }}>
                <Spin />
              </div>
            ) : sectorData.length > 0 ? (
              <ReactECharts 
                option={treemapOption} 
                style={{ height: 400 }}
                onEvents={{ click: (params: { name: string }) => handleSectorClick(params.name) }}
              />
            ) : (
              <Empty description="暂无板块数据" />
            )}
          </Card>
        </Col>
        {selectedSector && (
          <Col span={12}>
            <Card className={styles.tableCard} title={`${selectedSector}板块股票`}>
              {stocksLoading ? (
                <div style={{ textAlign: 'center', padding: 50 }}>
                  <Spin />
                </div>
              ) : sectorStocks.length > 0 ? (
                <Table
                  columns={stockColumns}
                  dataSource={sectorStocks.map((s, i) => ({ ...s, key: s.code || i }))}
                  pagination={{ pageSize: 10 }}
                  size="small"
                />
              ) : (
                <Empty description="该板块暂无股票数据" />
              )}
            </Card>
          </Col>
        )}
      </Row>
    </div>
  );
}