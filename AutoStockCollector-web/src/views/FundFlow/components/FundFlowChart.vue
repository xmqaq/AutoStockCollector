<template>
  <el-card shadow="never" class="section-card chart-card">
    <template #header>
      <span>净流入柱状图（单位：亿元）</span>
    </template>
    <div class="chart-container">
      <div class="chart-wrapper">
        <v-chart :option="barOption" style="height: 100%; width: 100%;" autoresize />
      </div>
    </div>
  </el-card>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { getChartTheme as ct } from '@/utils/chartTheme'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { BarChart } from 'echarts/charts'
import { GridComponent, TooltipComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'

use([BarChart, GridComponent, TooltipComponent, CanvasRenderer])

const props = defineProps<{
  rows: Record<string, unknown>[]
}>()

const barOption = computed(() => {
  const top20 = props.rows.slice(0, 20)
  const names = top20.map(r => (r.name as string) || (r.code as string))
  const values = top20.map(r => +((r.main_net_inflow as number) / 1e8).toFixed(3))
  return {
    backgroundColor: 'transparent',
    tooltip: { 
      trigger: 'axis', 
      backgroundColor: 'rgba(30, 30, 30, 0.85)',
      borderColor: 'transparent',
      padding: [12, 16],
      textStyle: {
        color: '#fff',
        fontSize: 13
      },
      formatter: (p: any[]) => {
        const item = p[0]
        const color = item.value >= 0 ? 'var(--el-color-danger)' : 'var(--el-color-success)'
        return `
          <div style="font-weight: 600; font-size: 15px; margin-bottom: 8px;">${item.name}</div>
          <div style="display: flex; justify-content: space-between; gap: 24px;">
            <span style="color: rgba(255,255,255,0.7)">主力净流入</span>
            <span style="color: ${color}; font-family: var(--font-mono); font-weight: 500;">${item.value > 0 ? '+' : ''}${item.value}亿</span>
          </div>
        `
      }
    },
    grid: { left: 50, right: 20, top: 30, bottom: 60 },
    xAxis: { 
      type: 'category', 
      data: names, 
      axisLine: { lineStyle: { color: 'var(--border-color)' } },
      axisLabel: { color: 'var(--text-secondary)', rotate: 30, fontSize: 12, margin: 12 } 
    },
    yAxis: { 
      type: 'value', 
      splitLine: { lineStyle: { type: 'dashed', color: 'var(--border-color-light)' } },
      axisLabel: { color: 'var(--text-secondary)', formatter: '{value} 亿' } 
    },
    series: [{
      type: 'bar',
      barWidth: '40%',
      itemStyle: {
        borderRadius: [4, 4, 0, 0],
        color: (params: any) => {
          return params.value >= 0 ? 'var(--el-color-danger)' : 'var(--el-color-success)'
        }
      },
      data: values
    }]
  }
})
</script>

<style scoped>
.chart-card {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: 12px;
  box-shadow: 0 2px 8px var(--bg-hover-subtle);
}
.chart-card :deep(.el-card__header) {
  border-bottom: 1px solid var(--border-color);
  padding: 12px 16px;
  color: var(--text-primary);
  font-size: 15px;
  font-weight: 600;
}
.chart-card :deep(.el-card__body) {
  flex: 1;
  min-height: 0;
  padding: 16px 20px;
  display: flex;
  flex-direction: column;
}
.chart-container {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  background-color: var(--bg-color); /* 相框背景 */
  border-radius: 8px;
  padding: 20px;
}
.chart-wrapper {
  width: 90%;
  height: 90%;
}
</style>
