<template>
  <el-card shadow="never" class="section-card chart-card" v-loading="loading">
    <template #header>
      <div class="card-header">
        <div class="header-left">
          <el-icon class="header-icon"><DataBoard /></el-icon>
          <span class="header-title">板块流向</span>
        </div>
        <el-button size="small" @click="$emit('refresh')">
          <el-icon><Refresh /></el-icon> 刷新
        </el-button>
      </div>
    </template>
    <el-empty v-if="sectors.length === 0 && !loading" description="暂无板块数据" />
    <div class="chart-container" v-else-if="sectors.length > 0">
      <v-chart
        :option="treemapOption"
        style="height: 100%; width: 100%;"
        autoresize
        @click="$emit('sector-click', $event)"
      />
    </div>
  </el-card>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { Refresh, DataBoard } from '@element-plus/icons-vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { TreemapChart } from 'echarts/charts'
import { TooltipComponent, TitleComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import { fmtAmount, fmtChange, RISE_COLOR, FALL_COLOR } from '@/utils/format'
import type { SectorRecord } from '@/types'

use([TreemapChart, TooltipComponent, TitleComponent, CanvasRenderer])

const props = defineProps<{
  loading: boolean
  sectors: SectorRecord[]
}>()

defineEmits<{
  (e: 'refresh'): void
  (e: 'sector-click', params: any): void
}>()

// 计算现代金融热力图颜色，使用不透明的纯色，防止视觉杂乱
function getHeatColor(rate: number) {
  // 按照A股习惯：红涨绿跌。根据板块常规涨跌幅区间划分（板块波动通常小于个股）
  if (rate >= 4) return '#F23645'      // 极强红：>= 4% (暴涨)
  if (rate >= 2) return '#D92634'      // 强红：2% ~ 4% (大涨)
  if (rate >= 1) return '#BF1D28'      // 中红：1% ~ 2% (中涨)
  if (rate > 0.2) return '#8A151F'     // 弱红：0.2% ~ 1% (小涨)
  
  if (rate >= -0.2 && rate <= 0.2) return '#434651' // 平盘：-0.2% ~ 0.2% (深灰)
  
  if (rate > -1) return '#065738'      // 弱绿：-1% ~ -0.2% (小跌)
  if (rate > -2) return '#097A4F'      // 中绿：-2% ~ -1% (中跌)
  if (rate > -4) return '#0D9E67'      // 强绿：-4% ~ -2% (大跌)
  return '#11C27E'                     // 极强绿：<= -4% (暴跌)
}

const treemapOption = computed(() => {
  const data = props.sectors.map(s => ({
    name: s.name,
    // 等权重：每个板块占相同面积，避免成交额差异导致小板块成为细条
    value: 1,
    itemStyle: {
      color: getHeatColor(s.change_rate || 0),
      borderColor: 'var(--bg-card)',
      borderWidth: 4,
      gapWidth: 4,
      borderRadius: 6
    },
    label: {
      show: true,
      formatter: (p: { data: { name: string; sectorData: SectorRecord } }) => {
        const sr = p.data.sectorData
        return `{name|${p.data.name}}\n{rate|${fmtChange(sr?.change_rate || 0)}}`
      },
      rich: {
        name: {
          fontSize: 14,
          fontWeight: 600,
          color: '#fff',
          lineHeight: 24
        },
        rate: {
          fontSize: 12,
          color: 'rgba(255, 255, 255, 0.9)'
        }
      }
    },
    sectorData: s,
  }))

  return {
    backgroundColor: 'transparent',
    tooltip: {
      backgroundColor: 'rgba(30, 30, 30, 0.85)',
      borderColor: 'transparent',
      padding: [12, 16],
      textStyle: {
        color: '#fff',
        fontSize: 13
      },
      formatter: (p: { data: { name: string; sectorData: SectorRecord } }) => {
        const s = p.data.sectorData
        if (!s) return p.data.name
        const flowColor = (s.net_flow || 0) >= 0 ? RISE_COLOR : FALL_COLOR
        const rateColor = (s.change_rate || 0) >= 0 ? RISE_COLOR : FALL_COLOR
        return `
          <div style="font-weight: 600; font-size: 15px; margin-bottom: 8px;">${s.name}</div>
          <div style="display: flex; justify-content: space-between; gap: 24px; margin-bottom: 4px;">
            <span style="color: rgba(255,255,255,0.7)">净流入</span>
            <span style="color: ${flowColor}; font-family: var(--font-mono); font-weight: 500;">${fmtAmount(s.net_flow || 0)}</span>
          </div>
          <div style="display: flex; justify-content: space-between; gap: 24px;">
            <span style="color: rgba(255,255,255,0.7)">涨跌幅</span>
            <span style="color: ${rateColor}; font-family: var(--font-mono); font-weight: 500;">${fmtChange(s.change_rate || 0)}</span>
          </div>
        `
      },
    },
    series: [
      {
        type: 'treemap',
        data,
        sort: false,
        left: 'center',
        top: 'middle',
        width: '90%',
        height: '90%',
        roam: false,
        nodeClick: false,
        breadcrumb: { show: false },
        animationDurationUpdate: 300,
        label: {
          show: true,
          color: '#fff',
          fontSize: 12,
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
.chart-container {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  background-color: var(--bg-color); /* 增加一层稍暗的背景作为画框 */
  border-radius: 8px;
  margin: 12px 0;
}
</style>