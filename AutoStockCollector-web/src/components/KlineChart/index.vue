<template>
  <div class="kline-chart-wrapper">
    <div class="chart-toolbar">
      <el-checkbox-group v-model="selectedMAs" size="small">
        <el-checkbox-button label="MA5" value="MA5" />
        <el-checkbox-button label="MA10" value="MA10" />
        <el-checkbox-button label="MA20" value="MA20" />
      </el-checkbox-group>
      <el-divider direction="vertical" />
      <el-checkbox v-model="showAnnotations" size="small">AI标注</el-checkbox>
      <el-checkbox v-model="showLevels" size="small">支撑压力位</el-checkbox>
      <el-checkbox v-model="showVolume" size="small">成交量</el-checkbox>
    </div>
    <v-chart
      ref="chartRef"
      :option="chartOption"
      :style="{ height: chartHeight }"
      autoresize
    />
    <div v-if="annotations.length > 0 && showAnnotations" class="annotation-legend">
      <span class="legend-item buy">● 买入信号</span>
      <span class="legend-item sell">● 卖出信号</span>
      <span class="legend-item hold">● 持有</span>
      <span class="legend-item alert">● 告警</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted, nextTick } from 'vue'
import { getChartTheme as ct } from '@/utils/chartTheme'
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
import type { KlineRecord, AIAnnotation, PriceLevel } from '@/types'
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
  annotations?: AIAnnotation[]
  supportLevels?: PriceLevel[]
  resistanceLevels?: PriceLevel[]
}

const props = withDefaults(defineProps<Props>(), {
  chartHeight: '500px',
  annotations: () => [],
  supportLevels: () => [],
  resistanceLevels: () => [],
})

const chartRef = ref<InstanceType<typeof VChart> | null>(null)
const selectedMAs = ref<string[]>(['MA5', 'MA10', 'MA20'])
const showAnnotations = ref(true)
const showLevels = ref(true)
const showVolume = ref(true)

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

function findDateIndex(dates: string[], targetDate: string): number {
  const idx = dates.indexOf(targetDate)
  if (idx !== -1) return idx
  for (let i = 0; i < dates.length; i++) {
    if (dates[i] >= targetDate) return i
  }
  return dates.length - 1
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

  const markLineData: { yAxis?: number; label?: { formatter?: string; color?: string }; lineStyle?: { color?: string } }[] = []

  if (showLevels.value) {
    props.supportLevels.forEach(level => {
      markLineData.push({
        yAxis: level.price,
        label: {
          formatter: `支撑 ${level.price.toFixed(2)}`,
          color: '#26a69a',
        },
        lineStyle: { color: '#26a69a' },
      })
    })
    props.resistanceLevels.forEach(level => {
      markLineData.push({
        yAxis: level.price,
        label: {
          formatter: `压力 ${level.price.toFixed(2)}`,
          color: '#ef5350',
        },
        lineStyle: { color: '#ef5350' },
      })
    })
  }

  const annotationSeries = showAnnotations.value && props.annotations.length > 0
    ? [{
        name: 'AI标注',
        type: 'scatter',
        data: props.annotations.map(a => {
          const idx = findDateIndex(dates, a.date)
          return { value: [idx, a.price], itemStyle: getAnnotationStyle(a.type), label: { show: true, formatter: getAnnotationLabel(a.type), color: getAnnotationColor(a.type), fontSize: 10 } }
        }),
        symbol: 'circle',
        symbolSize: 12,
        xAxisIndex: 0,
        yAxisIndex: 0,
      }]
    : []

  const volumeSeries = showVolume.value
    ? [{
        name: '成交量',
        type: 'bar',
        data: kdata.map(d => ({
          value: d.volume,
          itemStyle: { color: d.change_rate >= 0 ? RISE_COLOR : FALL_COLOR },
        })),
        xAxisIndex: 1,
        yAxisIndex: 1,
      }]
    : []

  const klineSeries = {
    name: 'K线',
    type: 'candlestick',
    data: ohlc,
    itemStyle: {
      color: RISE_COLOR,
      color0: FALL_COLOR,
      borderColor: RISE_COLOR,
      borderColor0: FALL_COLOR,
    },
    xAxisIndex: 0,
    yAxisIndex: 0,
  }

  if (markLineData.length > 0) {
    ;(klineSeries as Record<string, unknown>).markLine = {
      silent: true,
      symbol: ['none', 'none'],
      data: markLineData,
    }
  }

  const grids = showVolume.value
    ? [
        { left: 60, right: 20, top: 40, bottom: showVolume.value ? '28%' : 60 },
        { left: 60, right: 20, top: showVolume.value ? '75%' : 40, bottom: 60 },
      ]
    : [
        { left: 60, right: 20, top: 40, bottom: 60 },
      ]

  const yAxis = showVolume.value
    ? [
        { scale: true, splitArea: { show: false }, axisLine: { lineStyle: { color: ct().axisLineColor } }, splitLine: { lineStyle: { color: ct().splitLineColor } }, axisLabel: { color: ct().textColor, fontSize: 11 }, gridIndex: 0 },
        { scale: true, splitArea: { show: false }, axisLine: { lineStyle: { color: ct().axisLineColor } }, splitLine: { lineStyle: { color: ct().splitLineColor } }, axisLabel: { color: ct().textColor, fontSize: 11, formatter: (v: number) => (v / 100 / 1e4).toFixed(0) + '万' }, gridIndex: 1 },
      ]
    : [
        { scale: true, splitArea: { show: false }, axisLine: { lineStyle: { color: ct().axisLineColor } }, splitLine: { lineStyle: { color: ct().splitLineColor } }, axisLabel: { color: ct().textColor, fontSize: 11 } },
      ]

  const xAxis = showVolume.value
    ? [
        { type: 'category', data: dates, scale: true, boundaryGap: false, axisLine: { lineStyle: { color: ct().axisLineColor } }, splitLine: { show: false }, axisLabel: { color: ct().textColor, fontSize: 11 }, min: 'dataMin', max: 'dataMax', gridIndex: 0 },
        { type: 'category', data: dates, scale: true, boundaryGap: false, axisLine: { lineStyle: { color: ct().axisLineColor } }, splitLine: { show: false }, axisLabel: { show: false }, min: 'dataMin', max: 'dataMax', gridIndex: 1 },
      ]
    : [
        { type: 'category', data: dates, scale: true, boundaryGap: false, axisLine: { lineStyle: { color: ct().axisLineColor } }, splitLine: { show: false }, axisLabel: { color: ct().textColor, fontSize: 11 }, min: 'dataMin', max: 'dataMax' },
      ]

  const allSeries: unknown[] = [klineSeries, ...maSeries, ...annotationSeries, ...volumeSeries]

  return {
    backgroundColor: 'transparent',
    animation: false,
    legend: showVolume.value
      ? { top: 4, left: 'center', textStyle: { color: ct().textColor }, data: ['K线', ...selectedMAs.value, ...(showAnnotations.value && props.annotations.length > 0 ? ['AI标注'] : []), '成交量'] }
      : { top: 4, left: 'center', textStyle: { color: ct().textColor }, data: ['K线', ...selectedMAs.value] },
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
      backgroundColor: ct().tooltipBg,
      borderColor: ct().tooltipBorder,
      textStyle: { color: ct().tooltipText, fontSize: 12 },
      formatter(params: unknown[]) {
        const arr = params as Array<{ seriesName: string; dataIndex: number }>
        if (!arr || !arr.length) return ''
        const idx = arr[0]?.dataIndex
        if (idx === undefined || idx < 0) return ''
        const rec = kdata[idx]
        if (!rec) return ''
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
        const chgColor = Number.isFinite(chg) ? (chg >= 0 ? '#ef5350' : '#26a69a') : ct().tooltipText
        const chgStr = Number.isFinite(chg) ? `${chg >= 0 ? '+' : ''}${chg.toFixed(2)}%` : '--'
        const row = (k: string, v: string, color = ct().tooltipText) =>
          `<div style="display:flex;justify-content:space-between;gap:18px;line-height:1.6"><span style="color:#909399">${k}</span><span style="color:${color};font-weight:500">${v}</span></div>`
        const annotInfo = props.annotations.find(a => findDateIndex(dates, a.date) === idx)
        let annotHtml = ''
        if (annotInfo) {
          const annotColor = getAnnotationColor(annotInfo.type)
          annotHtml = `<div style="margin-top:6px;padding-top:6px;border-top:1px solid #444;color:${annotColor}">AI信号: ${annotInfo.type === 'buy' ? '买入' : annotInfo.type === 'sell' ? '卖出' : annotInfo.type === 'hold' ? '持有' : '告警'}</div>`
          if (annotInfo.label) {
            annotHtml += `<div style="color:#909399;font-size:11px">${annotInfo.label}</div>`
          }
        }
        return `
          <div style="padding:6px 10px;min-width:170px">
            <div style="font-weight:bold;margin-bottom:6px;color:${ct().tooltipText}">${date}</div>
            ${row('开盘', fmt(o))}
            ${row('最高', fmt(h), '#ef5350')}
            ${row('最低', fmt(l), '#26a69a')}
            ${row('收盘', fmt(c))}
            ${row('涨跌幅', chgStr, chgColor)}
            ${row('成交量', volStr)}
            ${row('成交额', amtStr)}
            ${row('换手率', Number.isFinite(trn) ? `${trn.toFixed(2)}%` : '--')}
            ${annotHtml}
          </div>
        `
      },
    },
    grid: grids,
    xAxis: xAxis,
    yAxis: yAxis,
    dataZoom: [
      {
        type: 'inside',
        xAxisIndex: showVolume.value ? [0, 1] : 0,
        start: 0,
        end: 100,
      },
      {
        type: 'slider',
        xAxisIndex: showVolume.value ? [0, 1] : 0,
        bottom: 8,
        height: 20,
        start: 0,
        end: 100,
        textStyle: { color: ct().textColor },
        borderColor: ct().tooltipBorder,
        fillerColor: 'rgba(63, 127, 174, 0.1)',
        handleStyle: { color: '#3f7fae' },
      },
    ],
    series: allSeries,
  }
})

function getAnnotationStyle(type: AIAnnotation['type']): { color: string; borderColor: string } {
  switch (type) {
    case 'buy': return { color: '#3f9d70', borderColor: '#3f9d70' }
    case 'sell': return { color: '#d05a51', borderColor: '#d05a51' }
    case 'hold': return { color: '#3f7fae', borderColor: '#3f7fae' }
    case 'alert': return { color: '#c9943a', borderColor: '#c9943a' }
  }
}

function getAnnotationColor(type: AIAnnotation['type']): string {
  switch (type) {
    case 'buy': return '#3f9d70'
    case 'sell': return '#d05a51'
    case 'hold': return '#3f7fae'
    case 'alert': return '#c9943a'
  }
}

function getAnnotationLabel(type: AIAnnotation['type']): string {
  switch (type) {
    case 'buy': return '买'
    case 'sell': return '卖'
    case 'hold': return '持'
    case 'alert': return '!'
  }
}

watch(() => props.data, () => {
  nextTick(() => {
    chartRef.value?.resize()
  })
})
</script>

<style scoped>
.kline-chart-wrapper {
  background: var(--bg-card);
  border-radius: 4px;
  padding: 12px;
}

.chart-toolbar {
  margin-bottom: 8px;
  display: flex;
  gap: 8px;
  align-items: center;
}

.annotation-legend {
  display: flex;
  gap: 16px;
  padding: 8px 0;
  font-size: 12px;
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 4px;
}

.legend-item.buy { color: var(--el-color-success); }
.legend-item.sell { color: var(--el-color-danger); }
.legend-item.hold { color: var(--el-color-primary); }
.legend-item.alert { color: var(--el-color-warning); }
</style>