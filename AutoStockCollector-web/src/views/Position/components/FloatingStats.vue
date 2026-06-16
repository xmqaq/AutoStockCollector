<template>
  <el-card shadow="never" class="pro-card">
    <template #header>
      <div class="card-header-inner">
        <span class="card-title">浮盈统计</span>
        <el-tooltip content="基于当前持仓的未实现盈亏，实时变动" placement="top">
          <el-icon class="header-icon"><InfoFilled /></el-icon>
        </el-tooltip>
      </div>
    </template>
    
    <div class="stats-grid">
      <div class="stat-item">
        <div class="stat-label">当前持仓数</div>
        <div class="stat-value">{{ floatingStats.count }}</div>
      </div>
      
      <div class="stat-item">
        <div class="stat-label">盈 / 亏 (只)</div>
        <div class="stat-value">
          <span class="text-rise">{{ floatingStats.winning }}</span>
          <span class="text-muted" style="margin: 0 4px">/</span>
          <span class="text-fall">{{ floatingStats.losing }}</span>
        </div>
      </div>
      
      <div class="stat-item max-item">
        <div class="stat-label">最大浮盈</div>
        <div class="stat-value" v-if="floatingStats.maxWin">
          <span class="stock-code">{{ floatingStats.maxWin.code }}</span>
          <span class="badge-tag badge-rise">+{{ floatingStats.maxWin.pnl_percent.toFixed(2) }}%</span>
        </div>
        <div class="stat-value text-muted" v-else>—</div>
      </div>
      
      <div class="stat-item max-item">
        <div class="stat-label">最大浮亏</div>
        <div class="stat-value" v-if="floatingStats.maxLoss">
          <span class="stock-code">{{ floatingStats.maxLoss.code }}</span>
          <span class="badge-tag badge-fall">{{ floatingStats.maxLoss.pnl_percent.toFixed(2) }}%</span>
        </div>
        <div class="stat-value text-muted" v-else>—</div>
      </div>
    </div>
  </el-card>
</template>

<script setup lang="ts">
import { InfoFilled } from '@element-plus/icons-vue'
import type { PaperPosition } from '@/api/paper'

defineProps<{
  floatingStats: {
    count: number
    winning: number
    losing: number
    maxWin: PaperPosition | null
    maxLoss: PaperPosition | null
  }
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

.max-item {
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
  display: flex;
  align-items: center;
  gap: 8px;
}

.max-item .stat-value {
  font-size: 14px;
}

.stock-code {
  font-size: 13px;
  color: var(--text-regular);
}

.badge-tag {
  display: inline-block;
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 12px;
  font-weight: bold;
}

.badge-rise { background: rgba(239, 83, 80, 0.12); color: #ef5350; }
.badge-fall { background: rgba(38, 166, 154, 0.12); color: #26a69a; }

.text-rise { color: #ef5350; }
.text-fall { color: #26a69a; }
.text-muted { color: var(--text-muted); }
</style>