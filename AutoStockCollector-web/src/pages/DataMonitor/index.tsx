import React, { useEffect, useState, useCallback } from 'react';
import { Card, Typography, Alert, Button, Modal, DatePicker, message, Popconfirm, Space, Empty, Spin } from 'antd';
import { RocketOutlined, DeleteOutlined, ReloadOutlined } from '@ant-design/icons';
import ReactECharts from 'echarts-for-react';
import dayjs from 'dayjs';
import { getProgressAll, collectHistory, clearDatabase } from '@/api/collect';
import { useCollectStore } from '@/stores/collectStore';
import ProgressTable from '@/components/ProgressTable';
import styles from './DataMonitor.module.css';

const { Title } = Typography;
const { RangePicker } = DatePicker;

export default function DataMonitor() {
  const { tasks, allDone, setTasks } = useCollectStore();
  const [collecting, setCollecting] = useState(false);
  const [modalVisible, setModalVisible] = useState(false);
  const [dateRange, setDateRange] = useState<[dayjs.Dayjs, dayjs.Dayjs] | null>(null);
  const [loading, setLoading] = useState(false);

  const fetchProgress = useCallback(async () => {
    try {
      setLoading(true);
      const res = await getProgressAll();
      if (res?.data) {
        setTasks(res.data.tasks || [], res.data.all_done || false);
      }
    } catch (err) {
      console.error('Failed to fetch progress:', err);
      message.error('获取采集进度失败');
    } finally {
      setLoading(false);
    }
  }, [setTasks]);

  useEffect(() => {
    fetchProgress();
    const timer = setInterval(fetchProgress, 3000);
    return () => clearInterval(timer);
  }, [fetchProgress]);

  const completedCount = tasks.filter((t) => t.status === 'completed').length;

  const gaugeOption = {
    series: [
      {
        type: 'gauge',
        startAngle: 180,
        endAngle: 0,
        min: 0,
        max: 8,
        splitNumber: 8,
        radius: '100%',
        axisLine: { lineStyle: { width: 12, color: [[completedCount / 8, '#177ddc'], [1, '#262626']] } },
        pointer: { icon: 'path://M12.8,0.7l12,40.1H0.7L12.8,0.7z', length: '50%', width: 8 },
        axisTick: { length: 8, lineStyle: { color: 'auto', width: 1 } },
        splitLine: { length: 12, lineStyle: { color: 'auto', width: 2 } },
        axisLabel: { color: '#8c8c8c', fontSize: 12, distance: -50 },
        title: { show: false },
        detail: { fontSize: 28, offsetCenter: [0, '50%'], valueAnimation: true, formatter: `{value}/8`, color: '#fff' },
        data: [{ value: completedCount }],
      },
    ],
  };

  const handleCollect = async () => {
    if (!dateRange) {
      message.warning('请选择日期范围');
      return;
    }
    setCollecting(true);
    try {
      await collectHistory({
        start_date: dateRange[0].format('YYYY-MM-DD'),
        end_date: dateRange[1].format('YYYY-MM-DD'),
      });
      message.success('采集任务已启动');
      setModalVisible(false);
      fetchProgress();
    } catch {
      message.error('启动采集失败');
    } finally {
      setCollecting(false);
    }
  };

  const handleClear = async () => {
    try {
      await clearDatabase();
      message.success('数据库已清空');
      fetchProgress();
    } catch {
      message.error('清空数据库失败');
    }
  };

  return (
    <div className={styles.container}>
      {allDone && <Alert message="所有 8 类数据采集完成" type="success" showIcon style={{ marginBottom: 16 }} />}

      <Title level={3} className={styles.pageTitle}>数据采集监控</Title>

      <Card className={styles.gaugeCard}>
        <ReactECharts option={gaugeOption} style={{ height: 200 }} />
      </Card>

      <Card title="采集进度详情" className={styles.tableCard}>
        {loading && tasks.length === 0 ? (
          <div style={{ textAlign: 'center', padding: 50 }}>
            <Spin />
          </div>
        ) : tasks.length > 0 ? (
          <ProgressTable data={tasks} />
        ) : (
          <Empty description="暂无采集任务" />
        )}
      </Card>

      <Card className={styles.actionCard}>
        <Space>
          <Button type="primary" icon={<RocketOutlined />} onClick={() => setModalVisible(true)}>
            启动采集
          </Button>
          <Popconfirm 
            title="确认清空数据库？" 
            description="此操作不可恢复，将清空所有采集的数据"
            onConfirm={handleClear}
            okText="确认"
            cancelText="取消"
            okButtonProps={{ danger: true }}
          >
            <Button danger icon={<DeleteOutlined />}>
              清空数据库
            </Button>
          </Popconfirm>
          <Button icon={<ReloadOutlined />} onClick={fetchProgress}>
            刷新
          </Button>
        </Space>
      </Card>

      <Modal
        title="启动数据采集"
        open={modalVisible}
        onOk={handleCollect}
        onCancel={() => setModalVisible(false)}
        confirmLoading={collecting}
        okText="开始采集"
        cancelText="取消"
      >
        <div style={{ marginBottom: 16 }}>
          <p>选择采集日期范围：</p>
          <RangePicker
            value={dateRange}
            onChange={(dates) => setDateRange(dates as [dayjs.Dayjs, dayjs.Dayjs] | null)}
            style={{ width: '100%' }}
            disabledDate={(current) => current && current > dayjs().endOf('day')}
          />
        </div>
      </Modal>
    </div>
  );
}