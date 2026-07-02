<template>
  <div class="kline-panel">
    <KlineChart
      :data="klineData"
      :support-levels="supportLevels"
      :resistance-levels="resistanceLevels"
      :annotations="annotations"
      chart-height="450px"
    />
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import KlineChart from '@/components/KlineChart/index.vue'
import type { KlineRecord, PriceLevel, AIAnnotation } from '@/types'
import type { PaKlineBar, PaTradePlan, PaBacktest } from '@/api/priceAction'

const props = defineProps<{
  bars?: PaKlineBar[]
  code?: string
  tradePlan?: PaTradePlan | null
  fibLevels?: Record<string, number> | null
  zones?: any[] | null
  backtest?: PaBacktest | null
}>()

// PaKlineBar → KlineRecord 适配：补 amount/change_rate/code/turnover_rate
const klineData = computed<KlineRecord[]>(() => {
  const code = props.code || ''
  return (props.bars || []).map(b => {
    const open = b.open || 0
    const close = b.close || 0
    return {
      code,
      date: b.time,
      open,
      high: b.high || 0,
      low: b.low || 0,
      close,
      volume: b.volume || 0,
      amount: 0,
      change_rate: open > 0 ? (close - open) / open * 100 : 0,
      turnover_rate: 0,
    }
  })
})

// 支撑位：止损 + 需求区
const supportLevels = computed<PriceLevel[]>(() => {
  const levels: PriceLevel[] = []
  const tp = props.tradePlan
  if (tp && tp.stop_loss) {
    levels.push({ price: tp.stop_loss, type: 'support', label: '止损' })
  }
  if (props.zones) {
    for (const z of props.zones) {
      if (z.type === 'demand' && z.low) {
        levels.push({ price: z.low, type: 'support', label: '需求区' })
      }
    }
  }
  return levels
})

// 阻力位：止盈 + 供给区
const resistanceLevels = computed<PriceLevel[]>(() => {
  const levels: PriceLevel[] = []
  const tp = props.tradePlan
  if (tp && tp.take_profit) {
    levels.push({ price: tp.take_profit, type: 'resistance', label: '止盈' })
  }
  if (tp && tp.entry) {
    levels.push({ price: tp.entry, type: 'resistance', label: '入场' })
  }
  if (props.zones) {
    for (const z of props.zones) {
      if (z.type === 'supply' && z.high) {
        levels.push({ price: z.high, type: 'resistance', label: '供给区' })
      }
    }
  }
  return levels
})

// 回测交易点 → AIAnnotation：entry 用 buy，exit 用 sell
const annotations = computed<AIAnnotation[]>(() => {
  const trades = props.backtest?.trades || []
  const anns: AIAnnotation[] = []
  for (const t of trades) {
    if (t.entry_date && t.entry_price) {
      anns.push({
        date: t.entry_date,
        type: 'buy',
        price: t.entry_price,
        label: t.r_multiple != null ? `R${t.r_multiple.toFixed(1)}` : '买入',
        description: `${t.direction || ''} 入场`,
      })
    }
    if (t.exit_date && t.exit_price) {
      anns.push({
        date: t.exit_date,
        type: t.outcome === 'win' ? 'sell' : 'alert',
        price: t.exit_price,
        label: t.outcome === 'win' ? '盈' : '亏',
        description: `${t.direction || ''} 出场 (${t.outcome})`,
      })
    }
  }
  return anns
})
</script>

<style scoped>
.kline-panel {
  background: var(--bg-card);
  border-radius: 12px;
  padding: 12px;
  border: 1px solid var(--border-color);
}
</style>
