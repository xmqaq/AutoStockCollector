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
      name: '盈亏金额',
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
            { offset: 0, color: values[values.length - 1] >= 0 ? 'rgba(103,194,58,0.4)' : 'rgba(245,108,108,0.4)' },
            { offset: 1, color: 'rgba(0,0,0,0)' },
          ],
        },
      },
    },
  ]

  if (hasCosts) {
    series.push({
      name: '成本线',
      type: 'line',
      data: costs,
      smooth: false,
      showSymbol: false,
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      lineStyle: { width: 1, type: 'dashed', color: '#909399' } as any,
    })
  }

  return {
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'axis',
      backgroundColor: '#2c2c2c',
      borderColor: '#444',
      textStyle: { color: '#e5eaf3' },
      formatter: (params: unknown[]) => {
        const ps = params as Array<{ axisValue: string; value: number; seriesName: string; color: string }>
        let html = `<div style="padding:8px"><div style="font-weight:bold;color:#e5eaf3">${ps[0].axisValue}</div>`
        ps.forEach(p => {
          html += `<div style="color:${p.color}">${p.seriesName}: ${p.value >= 0 ? '+' : ''}${p.value.toFixed(2)}</div>`
        })
        html += '</div>'
        return html
      },
    },
    legend: hasCosts ? {
      data: ['盈亏金额', '成本线'],
      bottom: 0,
      textStyle: { color: '#909399' },
    } : undefined,
    grid: { left: 50, right: 20, top: 20, bottom: hasCosts ? 40 : 30 },
    xAxis: {
      type: 'category',
      data: dates,
      axisLine: { lineStyle: { color: '#444' } },
      axisLabel: { color: '#909399', fontSize: 10 },
    },
    yAxis: {
      type: 'value',
      axisLine: { lineStyle: { color: '#444' } },
      splitLine: { lineStyle: { color: '#2c2c2c', type: 'dashed' } },
      axisLabel: {
        color: '#909399',
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
  background: #1f1f1f;
  border: 1px solid #2c2c2c;
}

.section-card :deep(.el-card__header) {
  border-bottom: 1px solid #2c2c2c;
  padding: 12px 16px;
  color: #e5eaf3;
  font-size: 14px;
  font-weight: 600;
}
</style>