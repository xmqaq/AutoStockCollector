<template>
  <el-card shadow="never" class="pro-card">
    <template #header>
      <span class="card-title">最近交易</span>
    </template>
    <div class="trade-list">
      <div v-for="t in recentTrades" :key="t.traded_at" class="trade-item">
        <div class="trade-icon" :class="t.action === 'buy' ? 'bg-buy' : 'bg-sell'">
          {{ t.action === 'buy' ? '买' : '卖' }}
        </div>
        <div class="trade-info">
          <div class="trade-header">
            <span class="trade-name">{{ t.name }}</span>
            <span class="trade-code">{{ t.code }}</span>
          </div>
          <div class="trade-detail">
            <span>{{ t.shares }} 股 @ <span class="number-font">{{ t.price.toFixed(2) }}</span></span>
            <span class="trade-time">{{ t.traded_at.slice(5, 16) }}</span>
          </div>
          <div v-if="t.ai_signal?.action" class="trade-signal">
            <el-icon><Monitor /></el-icon> AI: {{ t.ai_signal.action }}
          </div>
        </div>
      </div>
      <el-empty v-if="recentTrades.length === 0" description="暂无近期交易记录" :image-size="60" />
    </div>
  </el-card>
</template>

<script setup lang="ts">
import { Monitor } from '@element-plus/icons-vue'
import type { TradeRecord } from '@/api/paper'

defineProps<{
  recentTrades: TradeRecord[]
}>()
</script>

<style scoped>
.pro-card {
  background: var(--bg-card, #ffffff);
  border: 1px solid var(--border-color, #ebeef5);
  border-radius: 8px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.02);
  display: flex;
  flex-direction: column;
  max-height: 700px;
}

.pro-card :deep(.el-card__header) {
  border-bottom: 1px solid var(--border-color, #ebeef5);
  padding: 16px 20px;
  background-color: rgba(0,0,0,0.01);
}

.pro-card :deep(.el-card__body) {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  padding-bottom: 0;
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

.trade-list { 
  display: flex; 
  flex-direction: column; 
  gap: 12px; 
  flex: 1;
  overflow-y: auto; 
  max-height: 630px;
  padding-right: 4px;
  padding-bottom: 20px;
}

/* 自定义滚动条 */
.trade-list::-webkit-scrollbar {
  width: 6px;
}
.trade-list::-webkit-scrollbar-thumb {
  background: rgba(144, 147, 153, 0.3);
  border-radius: 3px;
}

.trade-item {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 12px; 
  border-radius: 8px; 
  background: var(--bg-soft, #f8f9fa);
  border: 1px solid var(--border-color-light, #f0f2f5);
  transition: all 0.2s;
}

.trade-item:hover {
  transform: translateX(2px);
  border-color: var(--border-color, #ebeef5);
  box-shadow: 0 2px 8px rgba(0,0,0,0.04);
}

.trade-icon {
  width: 32px;
  height: 32px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 13px;
  font-weight: bold;
  color: #fff;
  flex-shrink: 0;
}

.bg-buy { background: linear-gradient(135deg, #ef5350, #e53935); box-shadow: 0 2px 6px rgba(239, 83, 80, 0.3); }
.bg-sell { background: linear-gradient(135deg, #26a69a, #00897b); box-shadow: 0 2px 6px rgba(38, 166, 154, 0.3); }

.trade-info {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.trade-header { 
  display: flex; 
  align-items: center;
  gap: 8px;
}

.trade-name { 
  font-size: 14px; 
  font-weight: 600; 
  color: var(--text-primary, #303133); 
}

.trade-code {
  font-size: 12px;
  color: var(--text-muted, #909399);
  background: rgba(0,0,0,0.04);
  padding: 1px 6px;
  border-radius: 4px;
  font-family: var(--font-mono, "DIN Alternate", "Helvetica Neue", sans-serif);
}

.trade-detail { 
  font-size: 13px; 
  color: var(--text-regular, #606266); 
  display: flex; 
  justify-content: space-between; 
  align-items: center;
}

.number-font {
  font-family: var(--font-mono, "DIN Alternate", "Helvetica Neue", sans-serif);
  font-weight: 500;
}

.trade-time { 
  font-size: 12px;
  color: var(--text-muted, #909399);
  font-family: var(--font-mono, "DIN Alternate", "Helvetica Neue", sans-serif); 
}

.trade-signal { 
  font-size: 11px; 
  color: var(--el-color-primary, #409eff); 
  display: flex;
  align-items: center;
  gap: 4px;
  margin-top: 2px;
  background: rgba(64, 158, 255, 0.1);
  padding: 2px 8px;
  border-radius: 4px;
  width: fit-content;
}
</style>