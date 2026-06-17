<template>
  <div v-if="pick" class="ap-detail-panel">
    <div class="ap-detail-header">
      <span>{{ pick.code }} {{ pick.name }} 评分详情</span>
      <el-button size="small" text @click="$emit('close')">收起 ▲</el-button>
    </div>

    <div v-if="pick.score_details && Object.keys(pick.score_details).length" class="ap-detail-body">
      <div v-for="dim in orderedDimensions" :key="dim.key" class="ap-dim-block">
        <div class="ap-dim-title">
          <span class="ap-dim-label">{{ dim.label }}</span>
          <el-progress class="ap-dim-bar" :percentage="Math.round(dim.score)" :color="scoreColor(dim.score)" :stroke-width="8" />
          <span class="ap-dim-score">{{ dim.score }}分</span>
          <span class="ap-dim-weight">权重{{ Math.round(dim.weight * 100) }}%</span>
          <span class="ap-dim-contrib">贡献{{ dim.contribution }}分</span>
        </div>
        <div class="ap-dim-grid">
          <div v-for="si in dim.scoreItems" :key="si.key" class="ap-grid-cell">
            <div class="ap-cell-top">
              <span class="ap-cell-name">{{ formatItemName(si.key) }}</span>
              <span class="ap-cell-ratio" :style="{ color: ratioColor(si.item.score, si.item.max) }">{{ si.item.score }}/{{ si.item.max }}</span>
            </div>
            <div class="ap-cell-bottom">
              <span class="ap-cell-value">{{ formatItemValueRich(si.key, si.item) }}</span>
              <div class="ap-mini-bar">
                <div class="ap-mini-fill" :style="{ width: (si.item.score / si.item.max * 100) + '%', background: ratioColor(si.item.score, si.item.max) }"></div>
              </div>
            </div>
          </div>
        </div>
        <div v-for="w in dimWarnings(dim)" :key="w" class="ap-dim-warning"><el-icon style="color: var(--el-color-warning)"><WarningFilled /></el-icon> {{ w }}</div>
      </div>
    </div>
    <div v-else class="ap-detail-empty">
      详情数据不可用，请重新运行选股以生成详情
    </div>

    <div v-if="pick.recommendation" class="ap-detail-advice">
      <div class="ap-advice-label">AI分析建议：</div>
      <div class="ap-advice-text md-content" v-html="renderMd(pick.recommendation)"></div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { WarningFilled } from '@element-plus/icons-vue'
import { renderMd } from '@/utils/markdown'
import type { AIPick } from '@/api/ai'

const props = defineProps<{
  pick: AIPick | null
}>()

defineEmits<{
  (e: 'close'): void
}>()

const DIM_LABELS: Record<string, string> = {
  fundamental: '基本面',
  technical: '技术面',
  fund_flow: '资金面',
  valuation: '估值面',
}
const DIM_ORDER = ['fundamental', 'technical', 'fund_flow', 'valuation']

const orderedDimensions = computed(() => {
  if (!props.pick?.score_details) return []
  return DIM_ORDER.filter(k => k in props.pick!.score_details).map(k => {
    const d = props.pick!.score_details![k]
    const items = d.details ?? {}
    const scoreItems = Object.entries(items)
      .filter(([, v]) => typeof v === 'object' && v !== null && 'score' in (v as any))
      .map(([key, v]) => ({ key, item: v as any }))
    return {
      key: k,
      label: DIM_LABELS[k] || k,
      score: d.score ?? 0,
      weight: d.normalized_weight ?? d.weight ?? 0,
      contribution: d.contribution ?? 0,
      items,
      scoreItems,
    }
  })
})

const ITEM_NAMES: Record<string, string> = {
  roe: 'ROE',
  revenue_growth: '营收增速',
  profit_growth: '利润增速',
  gross_margin: '毛利率',
  debt_ratio: '资产负债率',
  ma_trend: '均线趋势',
  macd: 'MACD',
  rsi: 'RSI',
  momentum: '价格动量',
  net_inflow: '主力净流入',
  main_ratio: '主力占比',
  turnover_rate: '换手率',
  pe: 'PE',
  pb: 'PB',
}

const PCT_KEYS = new Set(['roe', 'revenue_growth', 'profit_growth', 'gross_margin', 'debt_ratio', 'turnover_rate', 'main_ratio', 'momentum'])

function dimWarnings(dim: any): string[] {
  if (!dim.items) return []
  return Object.entries(dim.items)
    .filter(([k, v]) => k.endsWith('_warning') && typeof v === 'string')
    .map(([, v]) => v as string)
}

function formatItemName(key: string): string {
  return ITEM_NAMES[key] || key
}

function formatItemValueRich(key: string, item: any): string {
  if (item.value == null && item.value_yi == null) return '无数据'
  if (typeof item.value === 'string') return item.value
  if (item.value_yi != null) return `${item.value_yi}亿`
  if (PCT_KEYS.has(key)) return `${item.value}%`
  if (key === 'pe' || key === 'pb') return Number(item.value).toFixed(2)
  return String(item.value)
}

function scoreColor(v: number): string {
  if (v >= 70) return '#3a8a52'
  if (v >= 50) return '#d0a020'
  return '#a04040'
}

function ratioColor(score: number, max: number): string {
  if (!max) return '#606070'
  const pct = score / max
  if (pct >= 0.8) return '#52c41a'
  if (pct >= 0.6) return '#faad14'
  return '#ff4d4f'
}
</script>

<style scoped>
.ap-detail-panel {
  background: var(--bg-card-alt, #ffffff);
  border: 1px solid var(--border-alt, #ebeef5);
  border-radius: 8px;
  padding: 14px;
  margin-top: -4px;
}
.ap-detail-header {
  display: flex; justify-content: space-between; align-items: center;
  font-size: 14px; font-weight: 600; color: var(--text-alt-body, #303133); margin-bottom: 10px;
}
.ap-detail-body { display: flex; flex-direction: column; gap: 10px; }
.ap-dim-block { background: var(--bg-deep-soft, #f5f7fa); border-radius: 6px; padding: 10px 12px; }
.ap-dim-title {
  display: flex; align-items: center; gap: 10px; margin-bottom: 8px;
}
.ap-dim-label { font-size: 13px; font-weight: 600; color: var(--text-alt-body, #303133); min-width: 48px; }
.ap-dim-bar { flex: 1; max-width: 180px; }
.ap-dim-score { font-size: 13px; font-weight: 600; color: var(--text-alt-primary, #303133); }
.ap-dim-weight { font-size: 11px; color: var(--text-alt-muted, #909399); }
.ap-dim-contrib { font-size: 11px; color: var(--text-alt-muted, #909399); }

.ap-dim-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 6px;
}
@media (min-width: 900px) {
  .ap-dim-grid { grid-template-columns: repeat(3, 1fr); }
}
.ap-grid-cell {
  background: var(--bg-card-alt, #ffffff);
  border-radius: 4px;
  padding: 7px 10px;
}
.ap-cell-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 3px;
}
.ap-cell-name { font-size: 11px; color: var(--text-alt-muted, #909399); }
.ap-cell-ratio { font-size: 11px; font-weight: 600; }
.ap-cell-bottom {
  display: flex;
  align-items: center;
  gap: 8px;
}
.ap-cell-value { font-size: 14px; font-weight: 600; color: var(--text-alt-body, #303133); white-space: nowrap; }
.ap-mini-bar {
  flex: 1;
  height: 4px;
  border-radius: 2px;
  background: var(--bg-hover, #ebeef5);
  min-width: 30px;
  max-width: 100px;
}
.ap-mini-fill {
  height: 100%;
  border-radius: 2px;
  transition: width 0.3s;
}

.ap-dim-warning {
  margin-top: 6px;
  padding: 5px 10px;
  background: rgba(250, 173, 20, 0.12);
  border-left: 3px solid #faad14;
  border-radius: 4px;
  font-size: 12px;
  color: #faad14;
  line-height: 1.4;
}
.ap-detail-empty { color: var(--text-alt-muted, #909399); font-size: 13px; text-align: center; padding: 16px 0; }
.ap-detail-advice { margin-top: 10px; border-top: 1px solid var(--border-alt, #ebeef5); padding-top: 10px; }
.ap-advice-label { font-size: 12px; color: var(--text-alt-muted, #909399); margin-bottom: 4px; }
.ap-advice-text { font-size: 13px; color: var(--text-alt-body, #303133); line-height: 1.6; }

.md-content :deep(h1),
.md-content :deep(h2),
.md-content :deep(h3) {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-alt-primary, #303133);
  margin: 10px 0 4px 0;
}
.md-content :deep(strong) {
  color: var(--text-alt-primary, #303133);
  font-weight: 600;
}
.md-content :deep(p) {
  margin: 4px 0;
  color: var(--text-alt-body, #606266);
}
</style>
