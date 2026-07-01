<template>
  <el-card v-if="backtest" shadow="never" class="pa-card pa-bt-card">
    <template #header><span>📊 回测验证</span></template>
    <template v-if="backtest.total_trades >= 5">
      <div class="pa-bt-grid">
        <div class="pa-bt-item"><span class="pa-bt-label">交易次数</span><span class="pa-bt-val">{{ backtest.total_trades }}</span></div>
        <div class="pa-bt-item"><span class="pa-bt-label">胜率</span><span class="pa-bt-val" :class="backtest.win_rate >= 40 ? 'pa-bt-green' : 'pa-bt-red'">{{ backtest.win_rate }}%</span></div>
        <div class="pa-bt-item"><span class="pa-bt-label">平均R</span><span class="pa-bt-val">{{ backtest.avg_r }}</span></div>
        <div class="pa-bt-item"><span class="pa-bt-label">夏普</span><span class="pa-bt-val" :class="backtest.sharpe_ratio >= 1 ? 'pa-bt-green' : ''">{{ backtest.sharpe_ratio }}</span></div>
        <div class="pa-bt-item"><span class="pa-bt-label">盈亏比</span><span class="pa-bt-val">{{ backtest.profit_factor }}</span></div>
        <div class="pa-bt-item"><span class="pa-bt-label">最大回撤</span><span class="pa-bt-val pa-bt-red">{{ backtest.max_drawdown_pct }}%</span></div>
        <div class="pa-bt-item"><span class="pa-bt-label">期望值</span><span class="pa-bt-val" :class="backtest.expectancy > 0 ? 'pa-bt-green' : 'pa-bt-red'">{{ backtest.expectancy }}</span></div>
        <div class="pa-bt-item"><span class="pa-bt-label">连续亏损</span><span class="pa-bt-val pa-bt-red">{{ backtest.max_consecutive_losses }}</span></div>
      </div>
      <div v-if="equityCurve.length > 1" class="pa-bt-equity">
        <div class="pa-bt-equity-title">权益曲线</div>
        <v-chart :option="equityOption" style="width:100%;height:200px" autoresize />
      </div>
    </template>
    <template v-else>
      <div class="pa-ai-na">{{ backtest.message || '历史信号不足，无法回测' }}</div>
    </template>
  </el-card>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { LineChart } from 'echarts/charts'
import { TooltipComponent, GridComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import { getChartTheme as ct } from '@/utils/chartTheme'
import type { PaBacktest } from '@/api/priceAction'

use([LineChart, TooltipComponent, GridComponent, CanvasRenderer])

const props = defineProps<{ backtest?: PaBacktest | null }>()

const equityCurve = computed<number[]>(() => props.backtest?.equity_curve || [])

const equityOption = computed(() => {
  const curve = equityCurve.value
  const theme = ct()
  return {
    backgroundColor: 'transparent',
    animation: false,
    tooltip: { trigger: 'axis', backgroundColor: theme.tooltipBg, borderColor: theme.tooltipBorder, textStyle: { color: theme.tooltipText } },
    grid: { left: 50, right: 16, top: 16, bottom: 28 },
    xAxis: {
      type: 'category', data: curve.map((_, i) => i + 1), boundaryGap: false,
      axisLine: { lineStyle: { color: theme.axisLineColor } },
      axisLabel: { color: theme.textColor, fontSize: 10 },
      splitLine: { show: false },
    },
    yAxis: {
      type: 'value', scale: true,
      axisLine: { lineStyle: { color: theme.axisLineColor } },
      axisLabel: { color: theme.textColor, fontSize: 10 },
      splitLine: { lineStyle: { color: theme.splitLineColor, type: 'dashed', opacity: 0.5 } },
    },
    series: [{
      type: 'line', data: curve, smooth: false, showSymbol: false,
      lineStyle: { width: 2, color: theme.upColor },
      areaStyle: { color: theme.upColor, opacity: 0.08 },
    }],
  }
})
</script>

<style scoped>
.pa-bt-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 10px;
}
.pa-bt-item {
  display: flex; flex-direction: column; align-items: center; gap: 4px;
  padding: 8px; background: var(--bg-soft); border-radius: 6px;
}
.pa-bt-label { font-size: 11px; color: var(--text-muted); }
.pa-bt-val { font-size: 15px; font-weight: 600; color: var(--text-primary); font-family: var(--font-mono); }
.pa-bt-green { color: #f23645; }
.pa-bt-red { color: #11c27e; }
.pa-bt-equity { margin-top: 12px; }
.pa-bt-equity-title { font-size: 13px; font-weight: 600; color: var(--text-secondary); margin-bottom: 6px; }
.pa-ai-na { color: var(--text-muted); font-size: 13px; padding: 8px 0; }
@media (max-width: 600px) { .pa-bt-grid { grid-template-columns: repeat(2, 1fr); } }
</style>
