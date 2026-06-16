<template>
  <el-card shadow="never" class="pro-card stat-card">
    <template #header>
      <div class="card-header-inner">
        <span class="card-title">交易统计</span>
        <el-tooltip content="仅统计已平仓（买入后卖出）的交易，未卖出的持仓不计入" placement="top">
          <el-icon class="header-icon"><InfoFilled /></el-icon>
        </el-tooltip>
      </div>
    </template>
    
    <div class="stats-grid">
      <div class="stat-item">
        <div class="stat-label">总交易次数</div>
        <div class="stat-value">{{ stats.total_trades }}</div>
      </div>
      
      <div class="stat-item">
        <div class="stat-label">胜率</div>
        <div class="stat-value" :class="stats.win_rate >= 50 ? 'text-rise' : 'text-fall'">
          {{ stats.win_rate.toFixed(1) }}%
        </div>
      </div>
      
      <div class="stat-item">
        <div class="stat-label">平均盈利</div>
        <div class="stat-value text-rise">+{{ stats.avg_profit_pct.toFixed(2) }}%</div>
      </div>
      
      <div class="stat-item">
        <div class="stat-label">平均亏损</div>
        <div class="stat-value text-fall">{{ stats.avg_loss_pct.toFixed(2) }}%</div>
      </div>
      
      <div class="stat-item full-width">
        <div class="stat-label">盈亏比</div>
        <div class="stat-value">{{ stats.profit_factor.toFixed(2) }}</div>
      </div>
    </div>
  </el-card>
</template>

<script setup lang="ts">
import { InfoFilled } from '@element-plus/icons-vue'
import type { PaperStats } from '@/api/paper'

defineProps<{
  stats: PaperStats
}>()
</script>

<style scoped>
.pro-card {
  background: var(--bg-card, #ffffff);
  border: 1px solid var(--border-color, #ebeef5);
  border-radius: 8px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.02);
}

.pro-card :deep(.el-card__header) {
  border-bottom: 1px solid var(--border-color, #ebeef5);
  padding: 16px 20px;
  background-color: rgba(0,0,0,0.01);
}

.card-header-inner {
  display: flex;
  align-items: center;
  gap: 6px;
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

.header-icon {
  color: var(--text-muted);
  cursor: help;
  font-size: 14px;
}

.stat-card { height: 100%; }

.stats-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}

.stat-item {
  background: var(--bg-soft, #f8f9fa);
  padding: 12px 16px;
  border-radius: 8px;
  border: 1px solid var(--border-color-light, #f0f2f5);
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.full-width {
  grid-column: 1 / -1;
  flex-direction: row;
  justify-content: space-between;
  align-items: center;
}

.stat-label {
  font-size: 13px;
  color: var(--text-muted, #909399);
}

.stat-value {
  font-size: 18px;
  font-weight: 600;
  color: var(--text-primary, #303133);
  font-family: var(--font-mono, "DIN Alternate", "Helvetica Neue", sans-serif);
}

.full-width .stat-value {
  font-size: 16px;
}

.text-rise { color: #ef5350; }
.text-fall { color: #26a69a; }
</style>