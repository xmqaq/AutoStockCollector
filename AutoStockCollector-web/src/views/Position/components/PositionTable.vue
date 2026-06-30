<template>
  <el-card shadow="never" class="pro-card">
    <template #header>
      <div class="card-header">
        <span class="card-title">当前持仓</span>
        <el-button type="primary" @click="$emit('buy')">
          手动交易
        </el-button>
      </div>
    </template>
    
    <el-table 
      :data="positions" 
      size="default" 
      v-loading="loading" 
      class="pro-table"
      :header-cell-style="{ background: 'var(--bg-soft, #f8f9fa)', color: 'var(--text-muted, var(--text-muted))', fontWeight: 500, borderBottom: '1px solid var(--border-color, #ebeef5)' }"
      :row-style="{ height: '56px' }"
      max-height="340px"
    >
      <!-- 左侧对齐文本 -->
      <el-table-column prop="code" label="代码" min-width="90" align="left">
        <template #default="{ row }">
          <router-link :to="`/stock-detail?code=${row.code}`" class="stock-link">
            {{ row.code }}
          </router-link>
        </template>
      </el-table-column>
      <el-table-column prop="name" label="名称" min-width="110" align="left" show-overflow-tooltip>
        <template #default="{ row }">
          <span class="stock-name">{{ row.name }}</span>
        </template>
      </el-table-column>
      
      <!-- 右侧对齐数值（符合金融报表规范） -->
      <el-table-column prop="shares" label="持仓量" min-width="90" align="right" />
      <el-table-column label="可卖" min-width="100" align="right">
        <template #default="{ row }">
          <span>{{ row.available_shares ?? row.shares }}</span>
          <el-tag v-if="(row.shares - (row.available_shares ?? row.shares)) > 0" type="warning" size="small" effect="light" style="margin-left: 4px;">T+1</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="成本价" min-width="90" align="right">
        <template #default="{ row }">{{ row.avg_cost.toFixed(2) }}</template>
      </el-table-column>
      <el-table-column label="现价" min-width="90" align="right">
        <template #default="{ row }">
          <span :class="pnlColorClass(row.current_price - row.avg_cost)">
            {{ row.current_price.toFixed(2) }}
          </span>
        </template>
      </el-table-column>
      <el-table-column label="市值" min-width="110" align="right">
        <template #default="{ row }">
          <span class="number-font">{{ formatAmount(row.market_value) }}</span>
        </template>
      </el-table-column>
      <el-table-column label="盈亏%" min-width="100" align="right">
        <template #default="{ row }">
          <span class="badge-tag" :class="row.pnl_percent >= 0 ? 'badge-rise' : 'badge-fall'">
            {{ formatPercent(row.pnl_percent) }}
          </span>
        </template>
      </el-table-column>
      <el-table-column label="今日%" min-width="100" align="right">
        <template #default="{ row }">
          <span :class="pnlColorClass(row.today_pnl_percent)">
            {{ formatPercent(row.today_pnl_percent ?? 0) }}
          </span>
        </template>
      </el-table-column>
      
      <!-- 居中/特殊格式 -->
      <el-table-column label="仓位" min-width="80" align="right">
        <template #default="{ row }">
          <span class="number-font text-muted">{{ row.position_ratio.toFixed(1) }}%</span>
        </template>
      </el-table-column>
      
      <el-table-column label="操作" width="140" align="right" fixed="right">
        <template #default="{ row }">
          <el-button type="primary" size="small" plain @click="$emit('buy', row)">
            加仓
          </el-button>
          <el-button type="danger" size="small" plain @click="$emit('sell', row)">
            卖出
          </el-button>
        </template>
      </el-table-column>
      
      <template #empty>
        <el-empty v-if="!loading" description="当前没有持仓股票" :image-size="80" />
      </template>
    </el-table>
  </el-card>
</template>

<script setup lang="ts">
import type { PaperPosition } from '@/api/paper'
import { pnlColorClass, formatAmount, formatPercent } from '../utils'

defineProps<{
  positions: PaperPosition[]
  loading: boolean
}>()

defineEmits<{
  (e: 'buy', pos?: PaperPosition): void
  (e: 'sell', pos: PaperPosition): void
}>()
</script>

<style scoped>
.pro-card {
  background: var(--bg-card, #ffffff);
  border: 1px solid var(--border-color, var(--border-color));
  border-radius: 8px;
  box-shadow: 0 2px 12px var(--bg-hover-subtle);
}

.pro-card :deep(.el-card__header) {
  border-bottom: 1px solid var(--border-color, #ebeef5);
  padding: 16px 20px;
  background-color: var(--bg-hover-subtle);
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.card-title {
  color: var(--text-primary);
  font-size: 15px;
  font-weight: 600;
  display: flex;
  align-items: center;
}

.card-title::before {
  content: '';
  display: inline-block;
  width: 4px;
  height: 16px;
  background: var(--el-color-primary);
  border-radius: 2px;
  margin-right: 8px;
}

/* 表格专业化样式 */
.pro-table {
  --el-table-border-color: var(--border-color-light, #f0f2f5);
}

.pro-table :deep(.el-table__row) {
  transition: background-color 0.2s;
}

.pro-table :deep(.el-table__row:hover > td.el-table__cell) {
  background-color: rgba(64, 158, 255, 0.04);
}

.stock-link {
  color: var(--el-color-primary, #409eff);
  text-decoration: none;
  font-weight: 600;
  font-family: var(--font-mono, "DIN Alternate", "Helvetica Neue", sans-serif);
}

.stock-link:hover {
  text-decoration: underline;
}

.stock-name {
  font-weight: 500;
  color: var(--text-primary, var(--text-primary));
}

.number-font {
  font-family: var(--font-mono, "DIN Alternate", "Helvetica Neue", sans-serif);
}

.text-muted {
  color: var(--text-muted, var(--text-muted));
}

.text-rise { color: var(--el-color-danger); }
.text-fall { color: var(--el-color-success); }
.text-neutral { color: var(--text-primary, var(--text-primary)); }

.badge-tag {
  display: inline-block;
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 12px;
  font-weight: bold;
  font-family: var(--font-mono, "DIN Alternate", "Helvetica Neue", sans-serif);
}

.badge-rise { background: rgba(239, 83, 80, 0.12); color: var(--el-color-danger); }
.badge-fall { background: rgba(38, 166, 154, 0.12); color: var(--el-color-success); }
</style>