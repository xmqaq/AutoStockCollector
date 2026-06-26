<template>
  <el-card shadow="never" class="section-card chart-card" v-loading="loading">
    <template #header>
      <div class="card-header">
        <div class="header-left">
          <el-icon class="header-icon"><TrendCharts /></el-icon>
          <span class="header-title">融资余额趋势</span>
        </div>
        <div class="header-right" v-if="latestRecord">
          <div class="latest-info">
            <span class="info-label">最新余额 ({{ latestRecord.date }})</span>
            <span class="info-value">{{ fmtAmount(latestRecord.rz_balance) }}</span>
          </div>
        </div>
      </div>
    </template>
    <div class="chart-container" v-if="chartData.length > 0">
      <v-chart :option="lineOption" style="height:100%; width:100%" autoresize />
    </div>
    <el-empty v-else-if="!loading" description="暂无数据" :image-size="60" />
  </el-card>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { getChartTheme as ct } from '@/utils/chartTheme'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent, DataZoomComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import * as echarts from 'echarts/core'
import { TrendCharts } from '@element-plus/icons-vue'
import { fmtAmount } from '@/utils/format'
import type { MarginRecord } from '@/types'

use([LineChart, GridComponent, TooltipComponent, LegendComponent, DataZoomComponent, CanvasRenderer])

const props = defineProps<{
  loading: boolean
  data: MarginRecord[]
}>()

const chartData = computed(() => {
  return [...props.data].sort((a, b) => a.date.localeCompare(b.date))
})

const latestRecord = computed(() => {
  if (chartData.value.length === 0) return null
  return chartData.value[chartData.value.length - 1]
})

const lineOption = computed(() => {
  const sorted = chartData.value
  const dates = sorted.map(d => d.date)
  const balances = sorted.map(d => d.rz_balance)
  return {
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(30, 30, 30, 0.85)',
      borderColor: 'transparent',
      borderRadius: 8,
      padding: 12,
      textStyle: { color: '#fff' },
      formatter: (params: any) => {
        const p = params[0]
        const date = p.name
        const val = p.value
        const record = sorted.find(s => s.date === date)
        
        let html = `<div style="font-weight:bold;margin-bottom:8px;border-bottom:1px solid rgba(255,255,255,0.1);padding-bottom:4px;">${date}</div>`
        html += `<div style="display:flex;justify-content:space-between;gap:24px;margin-bottom:4px;">`
        html += `<span style="color:#aaa;">融资余额</span><span style="font-weight:600;color:var(--el-color-primary);">${fmtAmount(val)}</span>`
        html += `</div>`
        
        if (record) {
          html += `<div style="display:flex;justify-content:space-between;gap:24px;margin-bottom:4px;">`
          html += `<span style="color:#aaa;">融资买入</span><span style="font-weight:500;">${fmtAmount(record.rz_buy)}</span>`
          html += `</div>`
          html += `<div style="display:flex;justify-content:space-between;gap:24px;margin-bottom:4px;">`
          html += `<span style="color:#aaa;">融券卖出</span><span style="font-weight:500;">${fmtAmount(record.rq_sell)}</span>`
          html += `</div>`
        }
        return html
      }
    },
    grid: { left: 60, right: 20, top: 20, bottom: 45 },
    dataZoom: [
      { type: 'inside', start: 0, end: 100 },
      { 
        type: 'slider', 
        start: 0, 
        end: 100, 
        height: 12, 
        bottom: 8,
        borderColor: 'transparent',
        backgroundColor: 'transparent',
        fillerColor: 'rgba(150, 150, 150, 0.2)',
        handleStyle: { color: '#bbb', borderColor: 'transparent' },
        showDataShadow: false,
        showDetail: false
      },
    ],
    xAxis: {
      type: 'category',
      data: dates,
      axisLabel: {
        color: ct().textColor,
        fontSize: 10,
        interval: Math.max(0, Math.floor(dates.length / 8) - 1),
      },
      axisLine: { lineStyle: { color: ct().axisLineColor } },
      axisTick: { show: false }
    },
    yAxis: {
      type: 'value',
      axisLabel: {
        color: ct().textColor,
        fontSize: 10,
        formatter: (v: number) => (v >= 1e8 ? `${(v / 1e8).toFixed(1)}亿` : `${(v / 1e4).toFixed(0)}万`),
      },
      splitLine: { 
        lineStyle: { 
          color: ct().splitLineColor,
          type: 'dashed',
          opacity: 0.5
        } 
      },
    },
    series: [
      {
        name: '融资余额',
        type: 'line',
        data: balances,
        smooth: true,
        symbol: 'circle',
        symbolSize: 6,
        showSymbol: false,
        itemStyle: {
          color: '#3f7fae'
        },
        lineStyle: { 
          color: '#3f7fae', 
          width: 2,
          shadowColor: 'rgba(63, 127, 174, 0.3)',
          shadowBlur: 10,
          shadowOffsetY: 5
        },
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: 'rgba(63, 127, 174, 0.4)' },
            { offset: 1, color: 'rgba(63, 127, 174, 0.05)' }
          ])
        },
      },
    ],
  }
})
</script>

<style scoped>
.chart-card {
  border-radius: 12px;
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  box-shadow: 0 2px 8px var(--bg-hover-subtle);
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
}
.chart-card :deep(.el-card__header) {
  border-bottom: 1px solid var(--border-color);
  padding: 12px 16px;
}
.chart-card :deep(.el-card__body) {
  flex: 1;
  min-height: 0;
  padding: 12px 16px;
  display: flex;
  flex-direction: column;
}
.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 12px;
}
.header-left {
  display: flex;
  align-items: center;
  gap: 8px;
}

.header-icon {
  font-size: 16px;
  color: var(--el-color-primary);
}

.header-title {
  color: var(--text-primary);
  font-size: 15px;
  font-weight: 600;
}

.header-right {
  display: flex;
  align-items: center;
}

.latest-info {
  display: flex;
  align-items: center;
  gap: 12px;
  background: var(--bg-soft);
  padding: 4px 12px;
  border-radius: 6px;
  border: 1px solid var(--border-color);
}

.info-label {
  font-size: 12px;
  color: var(--text-muted);
}

.info-value {
  font-size: 16px;
  font-weight: bold;
  color: var(--el-color-primary);
  font-family: var(--font-mono);
}
.chart-container {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}
</style>