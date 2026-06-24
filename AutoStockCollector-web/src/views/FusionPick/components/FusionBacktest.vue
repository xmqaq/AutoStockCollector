<template>
  <div class="fp-panel-actions">
    <el-button size="small" :icon="DataAnalysis" @click="$emit('load-backtest')" :loading="btLoading">
      计算回测（最近 {{ localBtLimit }} 次选股）
    </el-button>
    <el-input-number v-model="localBtLimit" :min="5" :max="200" :step="5" size="small" controls-position="right" />
    <el-button v-if="isAdmin" size="small" type="danger" plain :icon="Delete"
               class="fp-reset" @click="$emit('reset-data')" :loading="resetLoading">
      重置回测数据
    </el-button>
  </div>
  <template v-if="backtest">
    <div class="fp-bt-stats">
      <el-statistic title="参与批次" :value="backtest.runs_count" />
      <el-statistic title="融合分相关性" :value="backtest.fusion_score_correlation" :precision="3" />
      <el-statistic title="因子分相关性" :value="backtest.factor_score_correlation" :precision="3" />
      <el-statistic title="辩论加分胜率差" :value="backtest.debate_bonus_effectiveness" suffix="%" :precision="1" />
    </div>

    <h4 class="fp-h4">各持有期表现</h4>
    <el-table :data="overallRows" size="small" border>
      <el-table-column prop="h" label="持有期" width="90"><template #default="{ row }">{{ row.h }} 日</template></el-table-column>
      <el-table-column prop="n" label="样本" width="80" />
      <el-table-column label="平均收益"><template #default="{ row }">{{ fmtPct(row.avg) }}</template></el-table-column>
      <el-table-column label="胜率"><template #default="{ row }">{{ fmtPct(row.win_rate) }}</template></el-table-column>
      <el-table-column label="基准"><template #default="{ row }">{{ fmtPct(row.baseline) }}</template></el-table-column>
      <el-table-column label="超额"><template #default="{ row }"><span :class="bonusClass(row.excess)">{{ fmtPct(row.excess) }}</span></template></el-table-column>
      <el-table-column label="跑赢率"><template #default="{ row }">{{ fmtPct(row.beat_rate) }}</template></el-table-column>
    </el-table>

    <div class="fp-bt-cols">
      <div>
        <h4 class="fp-h4">按市场状态（5日胜率）</h4>
        <el-table :data="marketStateRows" size="small" border>
          <el-table-column label="状态"><template #default="{ row }">{{ stateText(row.state) }}</template></el-table-column>
          <el-table-column prop="n" label="样本" width="70" />
          <el-table-column label="胜率"><template #default="{ row }">{{ fmtPct(row.win_rate) }}</template></el-table-column>
          <el-table-column label="均收益"><template #default="{ row }">{{ fmtPct(row.avg_return) }}</template></el-table-column>
        </el-table>
      </div>
      <div>
        <h4 class="fp-h4">按来源（5日胜率）</h4>
        <el-table :data="sourceRows" size="small" border>
          <el-table-column prop="label" label="来源" />
          <el-table-column prop="n" label="样本" width="70" />
          <el-table-column label="胜率"><template #default="{ row }">{{ fmtPct(row.win_rate) }}</template></el-table-column>
        </el-table>
      </div>
    </div>
  </template>
  <el-empty v-else description="点击上方按钮计算回测" />
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { DataAnalysis, Delete } from '@element-plus/icons-vue'
import type { FusionBacktestResult, MarketStateKey } from '@/api/fusionPick'

const props = defineProps<{
  isAdmin: boolean
  btLimit: number
  btLoading: boolean
  resetLoading: boolean
  backtest: FusionBacktestResult | null
}>()

const emit = defineEmits<{
  (e: 'update:btLimit', val: number): void
  (e: 'load-backtest'): void
  (e: 'reset-data'): void
}>()

const localBtLimit = computed({
  get: () => props.btLimit,
  set: (v) => emit('update:btLimit', v)
})

const STATES: MarketStateKey[] = ['bull', 'bear', 'volatile']

const overallRows = computed(() => {
  const o = props.backtest?.overall || {}
  return Object.keys(o).sort((a, b) => +a - +b).map(h => ({ h, ...o[h] }))
})
const marketStateRows = computed(() =>
  STATES.map(state => ({ state, ...(props.backtest?.by_market_state?.[state] || { n: 0, win_rate: null, avg_return: null }) })))
const sourceRows = computed(() => {
  const s = props.backtest?.by_source
  if (!s) return []
  return [
    { label: '仅量化选中', ...s.quant_only },
    { label: '多来源共识', ...s.multi_source },
  ]
})

function stateText(s?: string) { return s === 'bull' ? '牛市' : s === 'bear' ? '熊市' : '震荡市' }
function bonusClass(v: number | null) { return v == null ? 'fp-muted' : v > 0 ? 'fp-up' : v < 0 ? 'fp-down' : 'fp-muted' }
function fmtPct(v: number | null | undefined) { return v == null ? '—' : `${v > 0 ? '+' : ''}${Number(v).toFixed(1)}%` }
</script>

<style scoped>
.fp-panel-actions { display: flex; align-items: center; gap: 12px; margin-bottom: 16px; flex-wrap: wrap; }
.fp-bt-stats { display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 18px; }
.fp-h4 { margin: 18px 0 10px; font-size: 14px; color: var(--text-primary); }
.fp-bt-cols { display: grid; grid-template-columns: 1fr 1fr; gap: 24px; }
@media (max-width: 760px) { .fp-bt-cols { grid-template-columns: 1fr; } .fp-bt-stats { grid-template-columns: repeat(2, 1fr); } }
.fp-reset { margin-left: auto; }

.fp-up { color: var(--el-color-danger); }
.fp-down { color: var(--el-color-success); }
.fp-muted { color: var(--text-secondary); }
</style>
