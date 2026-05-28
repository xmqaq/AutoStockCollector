import React, { useEffect, useState, useCallback } from 'react';
import { Card, Row, Col, Typography, Table, Spin } from 'antd';
import ReactECharts from 'echarts-for-react';
import { getSectorList, getSectorStocks } from '@/api/sector';
import type { SectorItem } from '@/types';
import { fmtAmount, fmtPercent, RISE_COLOR, FALL_COLOR } from '@/utils/stockCode';
import styles from './SectorFlow.module.css';

const { Title } = Typography;

const mockSectorData: SectorItem[] = [
  { name: '银行', type: '申万行业', net_flow: 125000000000, change_rate: 2.35 },
  { name: '白酒', type: '申万行业', net_flow: 89000000000, change_rate: 1.82 },
  { name: '新能源', type: '概念板块', net_flow: -45000000000, change_rate: -1.25 },
  { name: '半导体', type: '申万行业', net_flow: 67000000000, change_rate: 3.15 },
  { name: '医药生物', type: '申万行业', net_flow: -32000000000, change_rate: -0.88 },
  { name: '房地产', type: '申万行业', net_flow: -78000000000, change_rate: -2.45 },
  { name: '券商', type: '申万行业', net_flow: 45600000000, change_rate: 1.65 },
  { name: '军工', type: '概念板块', net_flow: 23400000000, change_rate: 2.88 },
];

export default function SectorFlow() {
  const [sectorData, setSectorData] = useState<SectorItem[]>([]);
  const [selectedSector, setSelectedSector] = useState<string | null>(null);
  const [sectorStocks, setSectorStocks] = useState<Array<{ code: string; name: string; change_rate: number; net_flow: number }>>([]);
  const [loading, setLoading] = useState(false);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const res = await getSectorList();
      const resData = res as unknown as { data?: SectorItem[] };
      if (resData?.data && Array.isArray(resData.data)) {
        setSectorData(resData.data);
      } else {
        setSectorData(mockSectorData);
      }
    } catch {
      setSectorData(mockSectorData);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  useEffect(() => {
    if (selectedSector) {
      getSectorStocks(selectedSector)
        .then((res) => {
          const resData = res as unknown as { data?: typeof sectorStocks };
          if (resData?.data) {
            setSectorStocks(resData.data);
          }
        })
        .catch(() => {
          setSectorStocks([]);
        });
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
          name: s.name,
          value: Math.abs(s.net_flow),
          change_rate: s.change_rate,
          itemStyle: {
            color: s.net_flow >= 0 ? RISE_COLOR : FALL_COLOR,
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
          {fmtPercent(v)}
        </span>
      ) },
    { title: '净流入', dataIndex: 'net_flow', key: 'net_flow', render: (v: number) => fmtAmount(v) },
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
            ) : (
              <ReactECharts 
                option={treemapOption} 
                style={{ height: 400 }}
                onEvents={{ click: (params: { name: string }) => handleSectorClick(params.name) }}
              />
            )}
          </Card>
        </Col>
        {selectedSector && (
          <Col span={12}>
            <Card className={styles.tableCard} title={`${selectedSector}板块股票`}>
              {sectorStocks.length > 0 ? (
                <Table
                  columns={stockColumns}
                  dataSource={sectorStocks.map((s, i) => ({ ...s, key: s.code || i }))}
                  pagination={{ pageSize: 10 }}
                  size="small"
                />
              ) : (
                <div style={{ textAlign: 'center', padding: 50, color: '#8c8c8c' }}>
                  点击上方板块查看股票列表
                </div>
              )}
            </Card>
          </Col>
        )}
      </Row>
    </div>
  );
}