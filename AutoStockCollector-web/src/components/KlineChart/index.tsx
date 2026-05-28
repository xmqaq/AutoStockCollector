import React, { useEffect, useRef } from 'react';
import * as echarts from 'echarts';
import type { KlineRecord } from '@/types';
import { RISE_COLOR, FALL_COLOR } from '@/utils/stockCode';

interface KlineChartProps {
  data: KlineRecord[];
  height?: number;
}

export default function KlineChart({ data, height = 500 }: KlineChartProps) {
  const chartRef = useRef<HTMLDivElement>(null);
  const chartInstance = useRef<echarts.ECharts | null>(null);

  useEffect(() => {
    if (!chartRef.current) return;

    chartInstance.current = echarts.init(chartRef.current);

    const dates = data.map((item) => item.date);
    const ohlc = data.map((item) => [item.open, item.close, item.low, item.high]);
    const volumes = data.map((item) => ({
      value: item.volume,
      itemStyle: {
        color: item.change_rate >= 0 ? RISE_COLOR : FALL_COLOR,
      },
    }));

    const option: echarts.EChartsOption = {
      animation: false,
      backgroundColor: 'transparent',
      tooltip: {
        trigger: 'axis',
        axisPointer: { type: 'cross' },
        formatter: (params: unknown) => {
          const p = (params as { dataIndex: number }[]);
          if (!p || p.length === 0) return '';
          const idx = p[0].dataIndex;
          const d = data[idx];
          return `
            <div style="font-family: monospace;">
              <div><strong>${d.date}</strong></div>
              <div>开: ${d.open.toFixed(2)}</div>
              <div>高: ${d.high.toFixed(2)}</div>
              <div>低: ${d.low.toFixed(2)}</div>
              <div>收: ${d.close.toFixed(2)}</div>
              <div>涨跌: ${d.change_rate >= 0 ? '+' : ''}${d.change_rate.toFixed(2)}%</div>
              <div>成交量: ${(d.volume / 10000).toFixed(2)}万</div>
              <div>成交额: ${(d.amount / 100000000).toFixed(2)}亿</div>
            </div>
          `;
        },
      },
      legend: { show: false },
      grid: [
        { left: 60, right: 20, top: 20, height: '55%' },
        { left: 60, right: 20, top: '72%', height: '20%' },
      ],
      xAxis: [
        { type: 'category', data: dates, gridIndex: 0, boundaryGap: false },
        { type: 'category', data: dates, gridIndex: 1, boundaryGap: false },
      ],
      yAxis: [
        { scale: true, gridIndex: 0 },
        { scale: true, gridIndex: 1, splitLine: { show: false } },
      ],
      dataZoom: [
        { type: 'inside', xAxisIndex: [0, 1], start: 70, end: 100 },
        { type: 'slider', xAxisIndex: [0, 1], start: 70, end: 100, height: 15, bottom: 5 },
      ],
      series: [
        {
          name: 'K线',
          type: 'candlestick',
          data: ohlc,
          xAxisIndex: 0,
          yAxisIndex: 0,
          itemStyle: {
            color: RISE_COLOR,
            color0: FALL_COLOR,
            borderColor: RISE_COLOR,
            borderColor0: FALL_COLOR,
          },
        },
        {
          name: '成交量',
          type: 'bar',
          data: volumes,
          xAxisIndex: 1,
          yAxisIndex: 1,
        },
      ],
    };

    chartInstance.current.setOption(option);

    const handleResize = () => chartInstance.current?.resize();
    window.addEventListener('resize', handleResize);

    return () => {
      window.removeEventListener('resize', handleResize);
      chartInstance.current?.dispose();
    };
  }, [data]);

  return <div ref={chartRef} style={{ width: '100%', height }} />;
}