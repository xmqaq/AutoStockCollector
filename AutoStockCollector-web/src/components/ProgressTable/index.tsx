import React from 'react';
import { Progress, Tag } from 'antd';
import type { TaskProgress } from '@/types';

interface ProgressTableProps {
  data: TaskProgress[];
}

const typeNameMap: Record<string, string> = {
  kline: 'K线数据',
  stock_info: '股票信息',
  financial: '财务数据',
  news: '新闻舆情',
  fund_flow: '资金流向',
  dragon_tiger: '龙虎榜',
  block: '板块数据',
  margin_data: '融资融券',
  margin: '融资融券',
};

const statusMap: Record<string, { text: string; color: string }> = {
  pending: { text: '等待中', color: '#8c8c8c' },
  running: { text: '采集中', color: '#177ddc' },
  completed: { text: '已完成', color: '#52c41a' },
  failed: { text: '失败', color: '#ff4d4f' },
  cancelled: { text: '已取消', color: '#faad14' },
};

export default function ProgressTable({ data }: ProgressTableProps) {
  if (!data || data.length === 0) {
    return <div style={{ textAlign: 'center', padding: 40, color: '#8c8c8c' }}>暂无任务数据</div>;
  }

  return (
    <div style={{ marginTop: 16 }}>
      {data.map((task) => {
        const taskType = task.type || task.task_type || '';
        const percent = task.total > 0 ? Math.round((task.progress / task.total) * 100) : 
          task.status === 'completed' ? 100 : 0;
        const statusInfo = statusMap[task.status] || { text: task.status, color: '#8c8c8c' };

        return (
          <div key={taskType || task.task_id} style={{ marginBottom: 16 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
              <span style={{ color: '#fff' }}>{typeNameMap[taskType] || taskType}</span>
              <Tag color={statusInfo.color}>{statusInfo.text}</Tag>
            </div>
            <Progress 
              percent={percent} 
              status={task.status === 'failed' ? 'exception' : task.status === 'running' ? 'active' : 'normal'}
              strokeColor={statusInfo.color}
              format={(p) => `${p}%`}
            />
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, color: '#8c8c8c', marginTop: 4 }}>
              <span>成功: {task.success}</span>
              <span>失败: {task.failed}</span>
            </div>
          </div>
        );
      })}
    </div>
  );
}