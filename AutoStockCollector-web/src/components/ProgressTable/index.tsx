import React from 'react';
import { Table, Tag, Progress, Badge } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import type { TaskProgress } from '@/types';
import { formatDuration } from '@/utils/stockCode';

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
  completed: { color: 'success', text: '已完成' },
  running: { color: 'processing', text: '采集中' },
  pending: { color: 'default', text: '等待中' },
  failed: { color: 'error', text: '失败' },
  cancelled: { color: 'warning', text: '已取消' },
};

interface ProgressTableProps {
  data: TaskProgress[];
  loading?: boolean;
}

export default function ProgressTable({ data, loading }: ProgressTableProps) {
  const columns: ColumnsType<TaskProgress> = [
    {
      title: '数据类型',
      dataIndex: 'type',
      key: 'type',
      render: (type: string) => typeNameMap[type] || type,
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 100,
      render: (status: string) => {
        const s = statusMap[status] || { color: 'default', text: status };
        return <Badge status={s.color as 'success' | 'processing' | 'default' | 'error' | 'warning'} text={s.text} />;
      },
    },
    {
      title: '进度',
      dataIndex: 'progress',
      key: 'progress',
      width: 200,
      render: (progress: number, record: TaskProgress) => (
        <Progress
          percent={record.total > 0 ? Math.round((progress / record.total) * 100) : 0}
          status={record.status === 'failed' ? 'exception' : undefined}
          format={() => `${progress}/${record.total}`}
        />
      ),
    },
    {
      title: '成功',
      dataIndex: 'success',
      key: 'success',
      width: 80,
      render: (v: number) => <Tag color="green">{v}</Tag>,
    },
    {
      title: '失败',
      dataIndex: 'failed',
      key: 'failed',
      width: 80,
      render: (v: number) => (v > 0 ? <Tag color="red">{v}</Tag> : <span>0</span>),
    },
    {
      title: '耗时',
      dataIndex: 'duration',
      key: 'duration',
      width: 100,
      render: (d: number) => formatDuration(d),
    },
  ];

  return (
    <Table
      columns={columns}
      dataSource={data.map((item) => ({ ...item, key: item.type }))}
      loading={loading}
      pagination={false}
      size="small"
    />
  );
}