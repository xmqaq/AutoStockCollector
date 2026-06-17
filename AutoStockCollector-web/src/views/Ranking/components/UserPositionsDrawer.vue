<template>
  <el-drawer
    v-model="visible"
    :title="`${username} 的持仓与交易`"
    size="600px"
    @closed="handleClose"
  >
    <template v-if="loading">
      <div class="loading-wrap"><el-icon class="is-loading" :size="32"><Loading /></el-icon></div>
    </template>
    <template v-else>
      <div class="section-title">当前持仓</div>
      <el-table :data="positions" stripe size="small" max-height="300" v-if="positions.length">
        <el-table-column prop="name" label="股票" min-width="120">
          <template #default="{ row }">{{ row.name }}<span class="code-tag">{{ row.code }}</span></template>
        </el-table-column>
        <el-table-column prop="shares" label="持仓" width="80" align="right" />
        <el-table-column prop="avg_cost" label="成本" width="80" align="right">
          <template #default="{ row }">{{ row.avg_cost.toFixed(2) }}</template>
        </el-table-column>
        <el-table-column prop="current_price" label="现价" width="80" align="right">
          <template #default="{ row }">{{ row.current_price.toFixed(2) }}</template>
        </el-table-column>
        <el-table-column prop="pnl_percent" label="盈亏%" width="80" align="right">
          <template #default="{ row }">
            <span :class="pnlClass(row.pnl_percent)">{{ row.pnl_percent > 0 ? '+' : '' }}{{ row.pnl_percent.toFixed(2) }}%</span>
          </template>
        </el-table-column>
        <el-table-column prop="market_value" label="市值" width="90" align="right">
          <template #default="{ row }">¥{{ row.market_value.toFixed(0) }}</template>
        </el-table-column>
      </el-table>
      <el-empty v-else description="暂无持仓" :image-size="60" />

      <div class="section-title" style="margin-top: 20px;">最近交易</div>
      <el-table :data="trades" stripe size="small" max-height="400" v-if="trades.length">
        <el-table-column prop="traded_at" label="时间" width="140">
          <template #default="{ row }">{{ fmtTime(row.traded_at) }}</template>
        </el-table-column>
        <el-table-column prop="action" label="方向" width="60" align="center">
          <template #default="{ row }">
            <el-tag :type="row.action === 'buy' ? 'danger' : 'success'" size="small">{{ row.action === 'buy' ? '买入' : '卖出' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="name" label="股票" min-width="120">
          <template #default="{ row }">{{ row.name }}<span class="code-tag">{{ row.code }}</span></template>
        </el-table-column>
        <el-table-column prop="shares" label="数量" width="70" align="right" />
        <el-table-column prop="price" label="价格" width="80" align="right">
          <template #default="{ row }">{{ row.price.toFixed(2) }}</template>
        </el-table-column>
        <el-table-column prop="amount" label="金额" width="90" align="right">
          <template #default="{ row }">¥{{ row.amount.toFixed(0) }}</template>
        </el-table-column>
      </el-table>
      <el-empty v-else description="暂无交易" :image-size="60" />
    </template>
  </el-drawer>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { Loading } from '@element-plus/icons-vue'
import { paperApi, type PaperPosition, type TradeRecord } from '@/api/paper'

const props = defineProps<{
  modelValue: boolean
  userId: string
  username: string
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
}>()

const visible = ref(false)
const loading = ref(false)
const positions = ref<PaperPosition[]>([])
const trades = ref<TradeRecord[]>([])

watch(() => props.modelValue, async (val) => {
  visible.value = val
  if (val && props.userId) {
    loading.value = true
    const [p, t] = await Promise.all([
      paperApi.getPositionsByUser(props.userId),
      paperApi.getTradesByUser(props.userId),
    ])
    positions.value = p
    trades.value = t
    loading.value = false
  }
})

watch(visible, (val) => {
  if (!val) emit('update:modelValue', false)
})

function handleClose() {
  positions.value = []
  trades.value = []
}

function pnlClass(v: number) {
  if (v > 0) return 'up'
  if (v < 0) return 'dn'
  return ''
}

function fmtTime(ts: string) {
  if (!ts) return ''
  return ts.replace('T', ' ').slice(0, 16)
}
</script>

<style scoped>
.loading-wrap { display: flex; justify-content: center; padding: 80px 0; }
.section-title { font-size: 15px; font-weight: 600; margin-bottom: 10px; color: var(--text-primary); }
.code-tag { font-size: 11px; color: var(--text-faint); margin-left: 4px; font-family: var(--font-mono); }
.up { color: #F23645; }
.dn { color: #11C27E; }
:deep(.el-drawer__body) { padding: 16px; }
</style>
