<template>
  <div class="hub-panel">
    <!-- 选股 -->
    <div class="hub-toolbar">
      <el-select
        v-model="selectedCode"
        filterable
        placeholder="选择股票查看信号中枢"
        style="width: 280px"
        @change="loadDetail"
      >
        <el-option v-for="s in signals" :key="s.code" :label="`${s.name} (${s.code})`" :value="s.code" />
      </el-select>
      <el-button :loading="loading" @click="loadDetail">刷新明细</el-button>
      <span v-if="detail" class="hub-score">
        综合融合分：<b :class="scoreClass(detail.fusion_score)">{{ detail.fusion_score }}</b>
        <span class="hub-vs">（监控 composite {{ detail.composite.score }}）</span>
      </span>
    </div>

    <el-empty v-if="!selectedCode" description="选择一只股票查看四路信号中枢视图" />

    <div v-else-if="detail" class="hub-content">
      <!-- 四路信号雷达图 -->
      <el-card shadow="never" class="hub-card">
        <template #header><span>📡 四路信号雷达</span></template>
        <div class="radar-wrapper">
          <v-chart :option="radarOption" style="width:100%;height:340px" autoresize />
        </div>
        <div class="signal-legend">
          <div v-for="s in signalEntries" :key="s.key" class="legend-item">
            <span :class="['legend-dot', `dot-${s.key}`]"></span>
            <span class="legend-label">{{ s.label }}</span>
            <span :class="['legend-val', s.val > 60 ? 'up' : s.val < 40 ? 'down' : 'flat']">{{ s.val ?? '—' }}</span>
            <el-tag v-if="s.stale" size="small" type="warning" effect="plain">缺数据</el-tag>
          </div>
        </div>
      </el-card>

      <!-- 融合分构成 + 跨页跳转 -->
      <div class="hub-bottom">
        <el-card shadow="never" class="hub-card">
          <template #header><span>📊 融合分构成</span></template>
          <div class="breakdown-list">
            <div v-for="(v, k) in detail.fusion_breakdown" :key="k" class="breakdown-row">
              <span class="bd-label">{{ sourceLabel(String(k)) }}</span>
              <el-progress :percentage="Number(v)" :stroke-width="10" :show-text="false" :color="barColor(Number(v))" />
              <span class="bd-val">{{ Number(v).toFixed(1) }}</span>
              <span class="bd-weight">权重 {{ ((detail.fusion_weights[k] || 0) * 100).toFixed(0) }}%</span>
            </div>
          </div>
        </el-card>

        <el-card shadow="never" class="hub-card">
          <template #header><span>🔗 跨页跳转</span></template>
          <div class="jump-btns">
            <el-button type="primary" plain @click="jump('/auto-trading')">前往 AutoTrading</el-button>
            <el-button type="success" plain @click="jump('/price-action')">查看 PA 详情</el-button>
            <el-button type="warning" plain @click="jump('/pre-market-radar')">查看竞价雷达</el-button>
            <el-button plain @click="jump('/stock-detail')">查看个股详情</el-button>
          </div>
          <div class="hub-hint">监控分(快照) vs 执行分(实时)：本页 fusion_score 基于快照，AutoTrading 页为实时融合，两者可能有差异。</div>
        </el-card>
      </div>

      <!-- 历史信号曲线 -->
      <el-card shadow="never" class="hub-card">
        <template #header><span>📈 composite 历史曲线</span></template>
        <div v-if="history.length" class="history-chart">
          <v-chart :option="historyOption" style="width:100%;height:240px" autoresize />
        </div>
        <el-empty v-else description="暂无历史信号数据" :image-size="60" />
      </el-card>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { RadarChart, LineChart } from 'echarts/charts'
import { TooltipComponent, GridComponent, LegendComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import { monitorApi, type MonitorSignal, type ExternalSignals } from '@/api/monitor'
import { getChartTheme as ct } from '@/utils/chartTheme'

use([RadarChart, LineChart, TooltipComponent, GridComponent, LegendComponent, CanvasRenderer])

const props = defineProps<{ signals: MonitorSignal[] }>()
const router = useRouter()

const selectedCode = ref('')
const detail = ref<any>(null)
const history = ref<any[]>([])
const loading = ref(false)

const ext = computed<ExternalSignals>(() => detail.value?.external_signals || {})

const signalEntries = computed(() => {
  const e = ext.value
  const paScore = e.pa ? paToScore(e.pa.signal) : null
  return [
    { key: 'monitor', label: 'AI 监控', val: detail.value?.composite?.score ?? null, stale: false },
    { key: 'pa', label: 'PA 价格行为', val: paScore, stale: !e.pa },
    { key: 'auction', label: '竞价雷达', val: e.auction?.score ?? null, stale: !e.auction },
    { key: 'agent', label: 'AI Agent', val: e.agent?.score ?? null, stale: !e.agent },
  ]
})

const radarOption = computed(() => {
  const e = ext.value
  const paScore = e.pa ? paToScore(e.pa.signal) : 0
  const theme = ct()
  return {
    backgroundColor: 'transparent',
    tooltip: { trigger: 'item' },
    radar: {
      indicator: [
        { name: 'AI监控', max: 100 },
        { name: 'PA', max: 100 },
        { name: '竞价', max: 100 },
        { name: 'Agent', max: 100 },
      ],
      axisName: { color: theme.textColor },
      splitLine: { lineStyle: { color: theme.splitLineColor } },
      splitArea: { areaStyle: { color: ['transparent', 'transparent'] } },
      axisLine: { lineStyle: { color: theme.axisLineColor } },
    },
    series: [{
      type: 'radar',
      data: [{
        value: [
          detail.value?.composite?.score ?? 0,
          paScore,
          e.auction?.score ?? 0,
          e.agent?.score ?? 0,
        ],
        areaStyle: { color: theme.upColor, opacity: 0.15 },
        lineStyle: { color: theme.upColor, width: 2 },
        itemStyle: { color: theme.upColor },
      }],
    }],
  }
})

const historyOption = computed(() => {
  const theme = ct()
  const pts = [...history.value].reverse()
  return {
    backgroundColor: 'transparent',
    tooltip: { trigger: 'axis', backgroundColor: theme.tooltipBg, borderColor: theme.tooltipBorder, textStyle: { color: theme.tooltipText } },
    grid: { left: 40, right: 16, top: 20, bottom: 28 },
    xAxis: {
      type: 'category', data: pts.map(p => (p.created_at || '').slice(5, 16)),
      axisLine: { lineStyle: { color: theme.axisLineColor } },
      axisLabel: { color: theme.textColor, fontSize: 10 },
    },
    yAxis: { type: 'value', min: 0, max: 100, axisLine: { lineStyle: { color: theme.axisLineColor } }, axisLabel: { color: theme.textColor }, splitLine: { lineStyle: { color: theme.splitLineColor, type: 'dashed', opacity: 0.5 } } },
    series: [{
      type: 'line', data: pts.map(p => p.composite?.score ?? 0), smooth: false, showSymbol: false,
      lineStyle: { width: 2, color: theme.upColor }, areaStyle: { color: theme.upColor, opacity: 0.08 },
    }],
  }
})

function paToScore(signal: string): number {
  const m: Record<string, number> = { BUY_SETUP: 95, WEAK_BUY: 70, NEUTRAL: 50, WEAK_SELL: 30, SELL_SETUP: 5, NO_DATA: 50, NO_TRADE: 50 }
  return m[signal] ?? 50
}

function scoreClass(s: number): string {
  if (s >= 62) return 'up'
  if (s < 38) return 'down'
  return 'flat'
}

function barColor(v: number): string {
  if (v >= 62) return '#f23645'
  if (v < 38) return '#11c27e'
  return '#909399'
}

function sourceLabel(k: string): string {
  return ({ auction: '竞价雷达', pa: 'PA 价格行为', ai_monitor: 'AI 监控', agent: 'AI Agent' } as Record<string, string>)[k] || k
}

async function loadDetail() {
  if (!selectedCode.value) return
  loading.value = true
  try {
    const [dRes, hRes] = await Promise.all([
      monitorApi.getFusionDetail(selectedCode.value),
      monitorApi.getSignalHistory(selectedCode.value, 30),
    ])
    detail.value = dRes.data?.data || null
    history.value = hRes.data?.data || []
  } catch { /* ignore */ } finally {
    loading.value = false
  }
}

function jump(path: string) {
  router.push({ path, query: selectedCode.value ? { code: selectedCode.value, symbol: selectedCode.value } : {} })
}

watch(() => props.signals, (ss) => {
  if (!selectedCode.value && ss.length) {
    selectedCode.value = ss[0].code
    loadDetail()
  }
}, { immediate: true })
</script>

<style scoped>
.hub-panel { display: flex; flex-direction: column; gap: 16px; }
.hub-toolbar { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }
.hub-score { font-size: 14px; color: var(--text-secondary); }
.hub-score b { font-size: 18px; font-family: var(--font-mono); }
.hub-vs { font-size: 12px; color: var(--text-muted); margin-left: 6px; }
.hub-content { display: flex; flex-direction: column; gap: 16px; }
.hub-card { border-radius: 12px; }
.radar-wrapper { display: flex; justify-content: center; }
.signal-legend { display: flex; flex-wrap: wrap; gap: 16px; justify-content: center; margin-top: 8px; }
.legend-item { display: flex; align-items: center; gap: 6px; font-size: 13px; }
.legend-dot { width: 10px; height: 10px; border-radius: 50%; }
.dot-monitor { background: #f23645; }
.dot-pa { background: #ffc107; }
.dot-auction { background: #409eff; }
.dot-agent { background: #9c27b0; }
.legend-label { color: var(--text-secondary); }
.legend-val { font-weight: 600; font-family: var(--font-mono); }
.legend-val.up { color: #f23645; }
.legend-val.down { color: #11c27e; }
.legend-val.flat { color: var(--text-muted); }
.hub-bottom { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
.breakdown-list { display: flex; flex-direction: column; gap: 10px; }
.breakdown-row { display: grid; grid-template-columns: 90px 1fr 50px 70px; align-items: center; gap: 8px; font-size: 13px; }
.bd-label { color: var(--text-secondary); }
.bd-val { font-weight: 600; font-family: var(--font-mono); text-align: right; }
.bd-weight { font-size: 11px; color: var(--text-faint); }
.jump-btns { display: flex; flex-direction: column; gap: 10px; }
.hub-hint { font-size: 12px; color: var(--text-muted); margin-top: 8px; line-height: 1.5; }
@media (max-width: 768px) { .hub-bottom { grid-template-columns: 1fr; } }
</style>
