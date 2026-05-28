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
    // 顶层 axisPointer.link 让两个 grid 的 X 轴联动 —— 鼠标移到下半的成交量区也能触发 tooltip
    axisPointer: {
      link: [{ xAxisIndex: 'all' }],
      label: { backgroundColor: '#555' },
    },
    tooltip: {
      trigger: 'axis',
      axisPointer: {
        type: 'cross',
        crossStyle: { color: '#888' },
      },
      backgroundColor: '#2c2c2c',
      borderColor: '#444',
      textStyle: { color: '#e5eaf3', fontSize: 12 },
      // 任意 series 触发都展示同一份完整 OHLC + 量 + 涨跌
      formatter(params: unknown[]) {
        const arr = params as Array<{ seriesName: string; dataIndex: number }>
        if (!arr || !arr.length) return ''
        // 取任意一个 series 的 dataIndex（K线 / 成交量 / MAx 都来自同一 X 轴）
        const idx = arr[0]?.dataIndex
        if (idx === undefined || idx < 0) return ''
        const rec = kdata[idx]
        if (!rec) return ''
        // 直接从源数据读，避开 ECharts 蜡烛 params.data 形如 [dataIndex, o, c, l, h] 带索引前缀的坑
        const date = rec.date
        const o = Number(rec.open)
        const h = Number(rec.high)
        const l = Number(rec.low)
        const c = Number(rec.close)
        const vol = Number(rec.volume)
        const amt = Number(rec.amount)
        const chg = Number(rec.change_rate)
        const trn = Number(rec.turnover_rate)
        const fmt = (n: number, d = 2) => Number.isFinite(n) ? n.toFixed(d) : '--'
        const volStr = Number.isFinite(vol) && vol > 0 ? `${(vol / 100 / 1e4).toFixed(2)} 万手` : '--'
        const amtStr = Number.isFinite(amt) && amt > 0
          ? (amt >= 1e8 ? `${(amt / 1e8).toFixed(2)} 亿` : `${(amt / 1e4).toFixed(2)} 万`)
          : '--'
        const chgColor = Number.isFinite(chg) ? (chg >= 0 ? '#ef5350' : '#26a69a') : '#e5eaf3'
        const chgStr = Number.isFinite(chg) ? `${chg >= 0 ? '+' : ''}${chg.toFixed(2)}%` : '--'
        const row = (k: string, v: string, color = '#e5eaf3') =>
          `<div style="display:flex;justify-content:space-between;gap:18px;line-height:1.6"><span style="color:#909399">${k}</span><span style="color:${color};font-weight:500">${v}</span></div>`
        return `
          <div style="padding:6px 10px;min-width:170px">
            <div style="font-weight:bold;margin-bottom:6px;color:#e5eaf3">${date}</div>
            ${row('开盘', fmt(o))}
            ${row('最高', fmt(h), '#ef5350')}
            ${row('最低', fmt(l), '#26a69a')}
            ${row('收盘', fmt(c))}
            ${row('涨跌幅', chgStr, chgColor)}
            ${row('成交量', volStr)}
            ${row('成交额', amtStr)}
            ${row('换手率', Number.isFinite(trn) ? `${trn.toFixed(2)}%` : '--')}
          </div>
        `
      },
    },
    // 单个 grid，K 线吃满，量价信息走 tooltip
    grid: [
      { left: 60, right: 20, top: 40, bottom: 60 },
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
    ],
    yAxis: [
      {
        scale: true,
        splitArea: { show: false },
        axisLine: { lineStyle: { color: '#444' } },
        splitLine: { lineStyle: { color: '#2c2c2c' } },
        axisLabel: { color: '#909399', fontSize: 11 },
      },
    ],
    dataZoom: [
      {
        type: 'inside',
        xAxisIndex: 0,
        start: Math.max(0, 100 - (80 / kdata.length) * 100),
        end: 100,
      },
      {
        type: 'slider',
        xAxisIndex: 0,
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
