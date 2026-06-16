<template>
  <el-card shadow="never" class="section-card table-card" v-loading="loading">
    <template #header>
      <span>全市场资金流向排行（{{ direction === 'inflow' ? '主力净流入' : '主力净流出' }} Top {{ topN }}）</span>
    </template>
    <el-empty v-if="!loading && rows.length === 0" description="暂无资金流向数据，请先采集" />
    <div v-else class="table-container">
      <el-table :data="rows" stripe size="default" @row-click="goToStock" height="100%" class="custom-table">
        <el-table-column type="index" label="#" width="50" align="center" />
        <el-table-column prop="code" label="代码" width="110" align="center">
          <template #default="{ row }">
            <span class="code-link">{{ row.code }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="name" label="名称" min-width="90" align="center" />
        <el-table-column label="主力净流入" min-width="120" sortable align="center">
          <template #default="{ row }">
            <span class="money-text" :class="row.main_net_inflow >= 0 ? 'is-rise' : 'is-fall'">
              {{ fmtAmount(row.main_net_inflow) }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="总流入" min-width="100" align="center">
          <template #default="{ row }">
            <span class="money-text is-rise">{{ fmtAmount(row.main_inflow) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="总流出" min-width="100" align="center">
          <template #default="{ row }">
            <span class="money-text is-fall">{{ fmtAmount(row.main_outflow) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="成交额" min-width="100" align="center">
          <template #default="{ row }">
            <span class="money-text">{{ fmtAmount(row.total_amount) }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="price" label="价格" min-width="80" align="center">
          <template #default="{ row }">
            <span class="money-text">{{ row.price }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="change_pct" label="涨跌幅" min-width="90" align="center">
          <template #default="{ row }">
            <span class="money-text" :class="parseFloat(row.change_pct) >= 0 ? 'is-rise' : 'is-fall'">
              {{ row.change_pct }}%
            </span>
          </template>
        </el-table-column>
      </el-table>
    </div>
  </el-card>
</template>

<script setup lang="ts">
import { useRouter } from 'vue-router'

const props = defineProps<{
  loading: boolean
  rows: Record<string, unknown>[]
  direction: 'inflow' | 'outflow'
  topN: number
}>()

const router = useRouter()

function fmtAmount(v: unknown): string {
  const n = typeof v === 'number' ? v : parseFloat(String(v || 0))
  if (isNaN(n)) return '--'
  const abs = Math.abs(n)
  if (abs >= 1e8) return `${(n / 1e8).toFixed(2)}亿`
  if (abs >= 1e4) return `${(n / 1e4).toFixed(2)}万`
  return n.toFixed(0)
}

function goToStock(row: Record<string, unknown>) {
  if (row.code) router.push(`/stock-detail?code=${row.code}`)
}
</script>

<style scoped>
.table-card {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: 12px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.02);
}
.table-card :deep(.el-card__header) {
  border-bottom: 1px solid var(--border-color);
  padding: 12px 16px;
  color: var(--text-primary);
  font-size: 15px;
  font-weight: 600;
}
.table-card :deep(.el-card__body) {
  flex: 1;
  min-height: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
}
.table-container {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}
.custom-table {
  --el-table-border-color: var(--border-color-light);
  --el-table-header-bg-color: var(--bg-soft);
  --el-table-header-text-color: var(--text-muted);
}
.custom-table :deep(th.el-table__cell) {
  font-weight: 500;
  padding: 10px 0;
}
.custom-table :deep(.el-table__inner-wrapper::before) {
  display: none;
}
.code-link {
  color: var(--el-color-primary);
  font-family: var(--font-mono);
  font-size: 13px;
  cursor: pointer;
  padding: 2px 6px;
  border-radius: 4px;
  background: var(--el-color-primary-light-9);
  transition: all 0.2s;
}
.code-link:hover {
  background: var(--el-color-primary-light-8);
  text-decoration: none;
}
.money-text {
  font-family: var(--font-mono);
  font-size: 14px;
  font-weight: 600;
}
.money-text.is-rise { color: #ef5350; }
.money-text.is-fall { color: #26a69a; }
</style>
