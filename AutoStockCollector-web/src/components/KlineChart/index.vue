<template>
  <div class="kline-chart-wrapper">
    <div class="chart-toolbar">
      <el-checkbox-group v-model="selectedMAs" size="small">
        <el-checkbox-button label="MA5" value="MA5" />
        <el-checkbox-button label="MA10" value="MA10" />
        <el-checkbox-button label="MA20" value="MA20" />
      </el-checkbox-group>
    </div>
    <v-chart
      ref="chartRef"
      :option="chartOption"
      :style="{ height: chartHeight }"
      autoresize
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted, nextTick } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import {
  CandlestickChart,
  BarChart,
  LineChart,
} from 'echarts/charts'
import {
  TitleComponent,
  TooltipComponent,
  GridComponent,
  DataZoomComponent,
  LegendComponent,
  MarkLineComponent,
} from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import type { KlineRecord } from '@/types'
import { RISE_COLOR, FALL_COLOR } from '@/utils/format'

use([
  CandlestickChart,
  BarChart,
  LineChart,
  TitleComponent,
  TooltipComponent,
  GridComponent,
  DataZoomComponent,
  LegendComponent,
  MarkLineComponent,
  CanvasRenderer,
])

interface Props {
  data: KlineRecord[]
  chartHeight?: string
}

const props = withDefaults(defineProps<Props>(), {
  chartHeight: '500px',
})

const chartRef = ref<InstanceType<typeof VChart> | null>(null)
const selectedMAs = ref<string[]>(['MA5', 'MA10', 'MA20'])

onMounted(() => {
  nextTick(() => {
    setTimeout(() => {
      chartRef.value?.resize()
    }, 100)
  })
})

function calcMA(data: KlineRecord[], period: number): (number | string)[] {
  const result: (number | string)[] = []
  for (let i = 0; i < data.length; i++) {
    if (i < period - 1) {
      result.push('-')
      continue
    }
    let sum = 0
    for (let j = 0; j < period; j++) {
      sum += data[i - j].close
    }
    result.push(+(sum / period).toFixed(2))
  }
  return result
}

const chartOption = computed(() => {
  const kdata = props.data
  if (!kdata || kdata.length === 0) return {}

  const dates = kdata.map(d => d.date)
  const ohlc = kdata.map(d => [d.open, d.close, d.low, d.high])
  const volumes = kdata.map(d => ({
    value: d.volume,
    itemStyle: {
      color: d.close >= d.open ? RISE_COLOR : FALL_COLOR,
    },
  }))

  const ma5 = calcMA(kdata, 5)
  const ma10 = calcMA(kdata, 10)
  const ma20 = calcMA(kdata, 20)

  const maSeries = []
  if (selectedMAs.value.includes('MA5')) {
    maSeries.push({
      name: 'MA5',
      type: 'line',
      data: ma5,
      smooth: true,
      lineStyle: { width: 1, color: '#ffc107' },
      showSymbol: false,
      xAxisIndex: 0,
      yAxisIndex: 0,
    })
  }
  if (selectedMAs.value.includes('MA10')) {
    maSeries.push({
      name: 'MA10',
      type: 'line',
      data: ma10,
      smooth: true,
      lineStyle: { width: 1, color: '#9c27b0' },
      showSymbol: false,
      xAxisIndex: 0,
      yAxisIndex: 0,
    })
  }
  if (selectedMAs.value.includes('MA20')) {
    maSeries.push({
      name: 'MA20',
      type: 'line',
      data: ma20,
      smooth: true,
      lineStyle: { width: 1, color: '#2196f3' },
      showSymbol: false,
      xAxisIndex: 0,
      yAxisIndex: 0,
    })
  }

  return {
    backgroundColor: '#1f1f1f',
    animation: false,
    legend: {
      top: 4,
      left: 'center',
      textStyle: { color: '#909399' },
      data: ['K线', ...selectedMAs.value],
    },
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'cross' },
      backgroundColor: '#2c2c2c',
      borderColor: '#444',
      textStyle: { color: '#e5eaf3', fontSize: 12 },
      formatter(params: unknown[]) {
        if (!params || !params.length) return ''
        const kParam = (params as Array<{ seriesName: string; data: number[]; dataIndex: number }>).find(p => p.seriesName === 'K线')
        if (!kParam) return ''
        const date = dates[kParam.dataIndex]
        const [open, close, low, high] = kParam.data
        const vol = kdata[kParam.dataIndex]?.volume || 0
        const chg = kdata[kParam.dataIndex]?.change_rate || 0
        return `
          <div style="padding:4px 8px">
            <div style="font-weight:bold;margin-bottom:4px">${date}</div>
            <div>开: ${open}</div>
            <div>高: ${high}</div>
            <div>低: ${low}</div>
            <div>收: ${close}</div>
            <div>量: ${(vol / 1e4).toFixed(2)}万手</div>
            <div>涨跌: ${chg >= 0 ? '+' : ''}${chg?.toFixed(2)}%</div>
          </div>
        `
      },
    },
    grid: [
      { left: 60, right: 20, top: 40, height: '60%' },
      { left: 60, right: 20, bottom: 60, height: '20%' },
    ],
    xAxis: [
      {
        type: 'category',
        data: dates,
        scale: true,
        boundaryGap: false,
        axisLine: { lineStyle: { color: '#444' } },
        splitLine: { show: false },
        axisLabel: { color: '#909399', fontSize: 11 },
        min: 'dataMin',
        max: 'dataMax',
      },
      {
        type: 'category',
        gridIndex: 1,
        data: dates,
        scale: true,
        boundaryGap: false,
        axisLine: { lineStyle: { color: '#444' } },
        axisTick: { show: false },
        axisLabel: { show: false },
        splitLine: { show: false },
        min: 'dataMin',
        max: 'dataMax',
      },
    ],
    yAxis: [
      {
        scale: true,
        splitArea: { show: false },
        axisLine: { lineStyle: { color: '#444' } },
        splitLine: { lineStyle: { color: '#2c2c2c' } },
        axisLabel: { color: '#909399', fontSize: 11 },
      },
      {
        scale: true,
        gridIndex: 1,
        splitNumber: 2,
        axisLine: { lineStyle: { color: '#444' } },
        axisTick: { show: false },
        axisLabel: { color: '#909399', fontSize: 11 },
        splitLine: { lineStyle: { color: '#2c2c2c' } },
      },
    ],
    dataZoom: [
      {
        type: 'inside',
        xAxisIndex: [0, 1],
        start: Math.max(0, 100 - (80 / kdata.length) * 100),
        end: 100,
      },
      {
        type: 'slider',
        xAxisIndex: [0, 1],
        bottom: 8,
        height: 20,
        start: Math.max(0, 100 - (80 / kdata.length) * 100),
        end: 100,
        textStyle: { color: '#909399' },
        borderColor: '#444',
        fillerColor: 'rgba(64,158,255,0.1)',
        handleStyle: { color: '#409eff' },
      },
    ],
    series: [
      {
        name: 'K线',
        type: 'candlestick',
        data: ohlc,
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
        xAxisIndex: 1,
        yAxisIndex: 1,
        data: volumes,
      },
      ...maSeries,
    ],
  }
})

watch(() => props.data, () => {
  nextTick(() => {
    chartRef.value?.resize()
  })
})
</script>

<style scoped>
.kline-chart-wrapper {
  background: #1f1f1f;
  border-radius: 4px;
  padding: 12px;
}

.chart-toolbar {
  margin-bottom: 8px;
  display: flex;
  gap: 8px;
  align-items: center;
}
</style>
