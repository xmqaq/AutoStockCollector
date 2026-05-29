<template>
  <div class="profit-chart">
    <div class="chart-header">
      <span class="chart-title">{{ title }}</span>
      <el-radio-group v-model="period" size="small">
        <el-radio-button label="1W">近1周</el-radio-button>
        <el-radio-button label="1M">近1月</el-radio-button>
        <el-radio-button label="3M">近3月</el-radio-button>
        <el-radio-button label="ALL">全部</el-radio-button>
      </el-radio-group>
    </div>
    <div class="chart-stats">
      <div class="stat-item">
        <span class="stat-label">累计收益</span>
        <span class="stat-value" :class="totalPnl >= 0 ? 'rise' : 'fall'">{{ formatChange(totalPnl) }}</span>
      </div>
      <div class="stat-item">
        <span class="stat-label">收益率</span>
        <span class="stat-value" :class="totalReturn >= 0 ? 'rise' : 'fall'">{{ formatPercent(totalReturn) }}</span>
      </div>
      <div class="stat-item">
        <span class="stat-label">最大回撤</span>
        <span class="stat-value fall">{{ formatPercent(maxDrawdown) }}</span>
      </div>
      <div class="stat-item">
        <span class="stat-label">夏普比率</span>
        <span class="stat-value">{{ sharpeRatio > 0 ? '+' : '' }}{{ sharpeRatio.toFixed(2) }}</span>
      </div>
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
import { ref, computed, watch } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { LineChart } from 'echarts/charts'
import {
  TitleComponent,
  TooltipComponent,
  GridComponent,
  LegendComponent,
  MarkAreaComponent,
} from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'

use([
  LineChart,
  TitleComponent,
  TooltipComponent,
  GridComponent,
  LegendComponent,
  MarkAreaComponent,
  CanvasRenderer,
])

interface ProfitData {
  date: string
  value: number
  cost?: number
}

interface Props {
  data: ProfitData[]
  title?: string
  chartHeight?: string
}

const props = withDefaults(defineProps<Props>(), {
  title: '盈亏曲线',
  chartHeight: '300px',
})

const chartRef = ref<InstanceType<typeof VChart> | null>(null)
const period = ref('1M')

const filteredData = computed(() => {
  if (!props.data || props.data.length === 0) return []
  
  const now = new Date()
  let days = 30
  if (period.value === '1W') days = 7
  else if (period.value === '1M') days = 30
  else if (period.value === '3M') days = 90
  else if (period.value === 'ALL') days = 365 * 10
  
  const cutoff = new Date(now.getTime() - days * 24 * 60 * 60 * 1000)
  return props.data.filter(d => new Date(d.date) >= cutoff)
})

const chartOption = computed(() => {
  const data = filteredData.value
  if (!data || data.length === 0) return {}
  
  const dates = data.map(d => d.date)
  const values = data.map(d => d.value)
  const costs = data.map(d => d.cost ?? 0)
  
  const profitLine = data.map((d, i) => d.value - (d.cost ?? d.value))
  
  const baseValue = data[0]?.cost ?? data[0]?.value ?? 100
  const returnData = profitLine.map(p => ((p / baseValue) * 100))
  
  return {
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'axis',
      backgroundColor: '#2c2c2c',
      borderColor: '#444',
      textStyle: { color: '#e5eaf3', fontSize: 12 },
      formatter(params: unknown[]) {
        const arr = params as Array<{ seriesName: string; dataIndex: number; value: number }>
        if (!arr || !arr.length) return ''
        const idx = arr[0]?.dataIndex
        if (idx === undefined || idx < 0) return ''
        const d = data[idx]
        const profit = d.value - (d.cost ?? d.value)
        const ret = ((profit / (d.cost ?? d.value)) * 100)
        const profitColor = profit >= 0 ? '#ef5350' : '#26a69a'
        return `
          <div style="padding:6px 10px">
            <div style="font-weight:bold;margin-bottom:4px;color:#e5eaf3">${d.date}</div>
            <div style="display:flex;justify-content:space-between;gap:16px">
              <span style="color:#909399">市值</span>
              <span style="color:#e5eaf3">${d.value.toFixed(2)}</span>
            </div>
            <div style="display:flex;justify-content:space-between;gap:16px">
              <span style="color:#909399">成本</span>
              <span style="color:#909399">${(d.cost ?? d.value).toFixed(2)}</span>
            </div>
            <div style="display:flex;justify-content:space-between;gap:16px;margin-top:4px;padding-top:4px;border-top:1px solid #444">
              <span style="color:#909399">盈亏</span>
              <span style="color:${profitColor};font-weight:600">${profit >= 0 ? '+' : ''}${profit.toFixed(2)}</span>
            </div>
            <div style="display:flex;justify-content:space-between;gap:16px">
              <span style="color:#909399">收益率</span>
              <span style="color:${profitColor};font-weight:600">${ret >= 0 ? '+' : ''}${ret.toFixed(2)}%</span>
            </div>
          </div>
        `
      },
    },
    legend: {
      show: true,
      top: 0,
      right: 0,
      textStyle: { color: '#909399', fontSize: 11 },
      data: ['盈亏曲线', '成本线'],
    },
    grid: {
      left: 50,
      right: 20,
      top: 40,
      bottom: 30,
    },
    xAxis: {
      type: 'category',
      data: dates,
      axisLine: { lineStyle: { color: '#444' } },
      axisLabel: { color: '#909399', fontSize: 11 },
      splitLine: { show: false },
    },
    yAxis: {
      type: 'value',
      axisLine: { lineStyle: { color: '#444' } },
      splitLine: { lineStyle: { color: '#2c2c2c', type: 'dashed' } },
      axisLabel: {
        color: '#909399',
        fontSize: 11,
        formatter: (v: number) => v >= 0 ? `+${v.toFixed(0)}` : v.toFixed(0),
      },
    },
    series: [
      {
        name: '盈亏曲线',
        type: 'line',
        data: profitLine,
        smooth: true,
        showSymbol: data.length <= 30,
        lineStyle: { width: 2 },
        areaStyle: {
          color: {
            type: 'linear',
            x: 0, y: 0, x2: 0, y2: 1,
            colorStops: [
              { offset: 0, color: 'rgba(239, 83, 80, 0.3)' },
              { offset: 0.5, color: 'rgba(239, 83, 80, 0.1)' },
              { offset: 1, color: 'rgba(38, 166, 154, 0.1)' },
            ],
          },
        },
        markLine: {
          silent: true,
          symbol: ['none', 'none'],
          data: [
            { yAxis: 0, lineStyle: { color: '#909399', type: 'dashed' }, label: { formatter: '成本线', color: '#909399' } },
          ],
        },
      },
      {
        name: '成本线',
        type: 'line',
        data: costs,
        smooth: false,
        showSymbol: false,
        lineStyle: { width: 1, color: '#606266', type: 'dashed' },
      },
    ],
  }
})

const totalPnl = computed(() => {
  if (filteredData.value.length < 2) return 0
  const first = filteredData.value[0]
  const last = filteredData.value[filteredData.value.length - 1]
  return (last.value - (last.cost ?? last.value)) - (first.value - (first.cost ?? first.value))
})

const totalReturn = computed(() => {
  if (filteredData.value.length < 2) return 0
  const first = filteredData.value[0]
  const last = filteredData.value[filteredData.value.length - 1]
  const firstCost = first.cost ?? first.value
  const lastCost = last.cost ?? last.value
  if (firstCost === 0) return 0
  return ((last.value - first.value) / firstCost) * 100
})

const maxDrawdown = computed(() => {
  if (filteredData.value.length < 2) return 0
  let max = 0
  let peak = filteredData.value[0]?.value ?? 0
  for (const d of filteredData.value) {
    if (d.value > peak) peak = d.value
    const drawdown = ((peak - d.value) / peak) * 100
    if (drawdown > max) max = drawdown
  }
  return -max
})

const sharpeRatio = computed(() => {
  if (filteredData.value.length < 5) return 0
  const returns = filteredData.value.slice(1).map((d, i) => {
    const prev = filteredData.value[i]
    return (d.value - prev.value) / (prev.value || 1)
  })
  const avgReturn = returns.reduce((a, b) => a + b, 0) / returns.length
  const variance = returns.reduce((a, b) => a + Math.pow(b - avgReturn, 2), 0) / returns.length
  const stdDev = Math.sqrt(variance)
  if (stdDev === 0) return 0
  return (avgReturn * 252) / (stdDev * Math.sqrt(252))
})

function formatChange(value: number): string {
  const prefix = value >= 0 ? '+' : ''
  return prefix + value.toFixed(2)
}

function formatPercent(value: number): string {
  const prefix = value >= 0 ? '+' : ''
  return prefix + value.toFixed(2) + '%'
}

watch(period, () => {
  chartRef.value?.resize()
})
</script>

<style scoped>
.profit-chart {
  background: #1f1f1f;
  border-radius: 4px;
  padding: 16px;
}

.chart-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.chart-title {
  font-size: 14px;
  font-weight: 600;
  color: #e5eaf3;
}

.chart-stats {
  display: flex;
  gap: 20px;
  margin-bottom: 16px;
  padding: 12px;
  background: #2c2c2c;
  border-radius: 6px;
}

.stat-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.stat-label {
  font-size: 11px;
  color: #909399;
}

.stat-value {
  font-size: 16px;
  font-weight: 600;
  color: #e5eaf3;
}

.stat-value.rise { color: #ef5350; }
.stat-value.fall { color: #26a69a; }
</style>