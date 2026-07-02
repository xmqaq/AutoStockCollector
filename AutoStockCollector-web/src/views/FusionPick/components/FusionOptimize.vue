<template>
  <div class="fp-panel-actions">
    <el-button size="small" :icon="DataAnalysis" @click="$emit('load-signals')" :loading="sigLoading">加载优化信号</el-button>
    <el-button v-if="isAdmin" size="small" type="primary" :icon="MagicStick"
               @click="$emit('do-optimize')" :loading="optLoading" :disabled="!signals?.reliable">
      应用优化（管理员）
    </el-button>
    <el-tag v-if="signals" :type="signals.reliable ? 'success' : 'warning'" effect="plain" size="small">
      {{ signals.reliable ? '样本充足，可优化' : '样本不足，仅供参考' }}
    </el-tag>
  </div>
  <template v-if="signals">
    <div v-for="st in STATES" :key="st" class="fp-opt-state">
      <h4 class="fp-h4">
        {{ stateText(st) }}
        <span class="fp-muted">（样本 {{ signals.sample_counts?.[st] ?? 0 }}，胜率 {{ fmtPct(signals.state_performance?.[st]?.win_rate) }}）</span>
      </h4>
      <el-table :data="optRows(st)" size="small" border>
        <el-table-column prop="label" label="维度" width="110" />
        <el-table-column label="5日超额收益差">
          <template #default="{ row }"><span :class="bonusClass(row.corr)">{{ row.corr.toFixed(3) }}</span></template>
        </el-table-column>
        <el-table-column label="建议权重">
          <template #default="{ row }">{{ (row.suggested * 100).toFixed(0) }}%</template>
        </el-table-column>
      </el-table>
    </div>
  </template>
  <el-empty v-else description="点击「加载优化信号」查看各维度高低分组的5日超额收益差及建议权重" />
</template>

<script setup lang="ts">
import { DataAnalysis, MagicStick } from '@element-plus/icons-vue'
import type { FusionOptSignals, MarketStateKey, DimWeights } from '@/api/fusionPick'

const props = defineProps<{
  isAdmin: boolean
  sigLoading: boolean
  optLoading: boolean
  signals: FusionOptSignals | null
}>()

const emit = defineEmits<{
  (e: 'load-signals'): void
  (e: 'do-optimize'): void
}>()

const STATES: MarketStateKey[] = ['bull', 'bear', 'volatile']
const DIMS = [
  { key: 'fundamental', label: '基本面', color: '#5a7af0' },
  { key: 'technical', label: '技术面', color: 'var(--el-color-warning)' },
  { key: 'fund_flow', label: '资金面', color: 'var(--el-color-success)' },
  { key: 'valuation', label: '估值面', color: 'var(--text-muted)' },
] as const

function optRows(st: MarketStateKey) {
  const corr = props.signals?.dimension_correlations?.[st] || {} as DimWeights
  const sug = props.signals?.suggested_weights?.[st] || {} as DimWeights
  return DIMS.map(d => ({ label: d.label, corr: corr[d.key] ?? 0, suggested: sug[d.key] ?? 0 }))
}

function stateText(s?: string) { return s === 'bull' ? '牛市' : s === 'bear' ? '熊市' : '震荡市' }
function bonusClass(v: number | null) { return v == null ? 'fp-muted' : v > 0 ? 'fp-up' : v < 0 ? 'fp-down' : 'fp-muted' }
function fmtPct(v: number | null | undefined) { return v == null ? '—' : `${v > 0 ? '+' : ''}${Number(v).toFixed(1)}%` }
</script>

<style scoped>
.fp-panel-actions { display: flex; align-items: center; gap: 12px; margin-bottom: 16px; flex-wrap: wrap; }
.fp-h4 { margin: 18px 0 10px; font-size: 14px; color: var(--text-primary); }
.fp-opt-state { margin-bottom: 18px; }

.fp-up { color: var(--el-color-danger); }
.fp-down { color: var(--el-color-success); }
.fp-muted { color: var(--text-secondary); }
</style>
