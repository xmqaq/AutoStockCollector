<template>
  <div class="profit-chart">
    <el-card shadow="never" class="section-card">
      <template #header>
        <div class="header-toolbar">
          <span>{{ title }}</span>
        </div>
      </template>
      <v-chart :option="chartOption" :style="{ height: chartHeight }" autoresize />
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { getChartTheme as ct } from '@/utils/chartTheme'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'

use([LineChart, GridComponent, TooltipComponent, LegendComponent, CanvasRenderer])

interface ProfitRecord {
  date: string
  value: number
  cost?: number
  profit_amount?: number
  profit_pct?: number
}

const props = withDefaults(defineProps<{
  data: ProfitRecord[]
  title?: string
  chartHeight?: string
}>(), {
  title: '盈亏曲线',
  chartHeight: '280px'
})

const chartOption = computed(() => {
  const data = props.data || []
  const dates = data.map(d => d.date)
  const values = data.map(d => d.value)
  const costs = data.map(d => d.cost || 0)

  const hasCosts = costs.some(c => c !== 0)

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const series: any[] = [
    {
      name: '账户净值',
      type: 'line',
      data: values,
      smooth: true,
      showSymbol: false,
      lineStyle: { width: 2 },
      areaStyle: {
        color: {
          type: 'linear',
          x: 0, y: 0, x2: 0, y2: 1,
          colorStops: [
            { offset: 0, color: values[values.length - 1] >= 0 ? 'rgba(63, 157, 112, 0.4)' : 'rgba(208, 90, 81, 0.4)' },
            { offset: 1, color: 'rgba(0,0,0,0)' },
          ],
        },
      },
    },
  ]

  if (hasCosts) {
    series.push({
      name: '初始资金',
      type: 'line',
      data: costs,
      smooth: false,
      showSymbol: false,
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      lineStyle: { width: 1, type: 'dashed', color: ct().textColor } as any,
    })
  }

  return {
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'axis',
      backgroundColor: ct().tooltipBg,
      borderColor: ct().tooltipBorder,
      textStyle: { color: ct().tooltipText },
      formatter: (params: unknown[]) => {
        const ps = params as Array<{ axisValue: string; value: number; seriesName: string; color: string; dataIndex: number }>
        const idx = ps[0].dataIndex
        const record = data[idx]
        let html = `<div style="padding:8px"><div style="font-weight:bold;color:${ct().tooltipText}">${ps[0].axisValue}</div>`
        if (record?.profit_amount !== undefined) {
          const pnlColor = record.profit_amount >= 0 ? '#ef5350' : '#26a69a'
          html += `<div style="color:${ct().tooltipText}">净值: ${record.value.toFixed(2)}</div>`
          html += `<div style="color:${pnlColor}">盈亏: ${record.profit_amount >= 0 ? '+' : ''}${record.profit_amount.toFixed(2)}</div>`
          html += `<div style="color:${pnlColor}">收益率: ${record.profit_pct !== undefined ? (record.profit_pct >= 0 ? '+' : '') + record.profit_pct.toFixed(2) + '%' : ''}</div>`
        } else {
          ps.forEach(p => {
            html += `<div style="color:${p.color}">${p.seriesName}: ${p.value >= 0 ? '+' : ''}${p.value.toFixed(2)}</div>`
          })
        }
        html += '</div>'
        return html
      },
    },
    legend: hasCosts ? {
      data: ['账户净值', '初始资金'],
      bottom: 0,
      textStyle: { color: ct().textColor },
    } as const : undefined,
    grid: { left: 50, right: 20, top: 20, bottom: hasCosts ? 40 : 30 },
    xAxis: {
      type: 'category',
      data: dates,
      axisLine: { lineStyle: { color: ct().axisLineColor } },
      axisLabel: { color: ct().textColor, fontSize: 10 },
    },
    yAxis: {
      type: 'value',
      axisLine: { lineStyle: { color: ct().axisLineColor } },
      splitLine: { lineStyle: { color: ct().splitLineColor, type: 'dashed' } },
      axisLabel: {
        color: ct().textColor,
        formatter: (val: number) => val >= 0 ? `+${val}` : val.toString(),
      },
    },
    series,
  }
})
</script>

<style scoped>
.profit-chart {
  width: 100%;
}

.header-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.section-card {
  background: var(--bg-card);
  border: 1px solid var(--border-color);
}

.section-card :deep(.el-card__header) {
  border-bottom: 1px solid var(--border-color);
  padding: 12px 16px;
  color: var(--text-primary);
  font-size: 14px;
  font-weight: 600;
}
</style>