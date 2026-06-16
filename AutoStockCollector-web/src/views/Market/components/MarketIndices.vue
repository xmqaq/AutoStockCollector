<template>
  <div class="market-indices">
    <div class="indices-grid">
      <div
        v-for="idx in indices"
        :key="idx.code"
        :class="['index-card', getColorClass(idx.change)]"
      >
        <div class="index-name">{{ idx.name }}</div>
        <div class="index-price num">{{ fmtPrice(idx.price) }}</div>
        <div :class="['index-change', getTextClass(idx.change)]">
          <span class="num">{{ fmtChange(idx.change) }}</span>
          <span class="change-amount num">{{ fmtAmount(idx.amount) }}</span>
        </div>
      </div>
    </div>
    <div class="refresh-bar">
      <el-button size="small" @click="$emit('refresh')" :loading="loading">
        <el-icon><Refresh /></el-icon> 刷新
      </el-button>
      <span class="update-time">更新时间: {{ updateTime }}</span>
      <span class="auto-tip">每1分钟自动刷新</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { Refresh } from '@element-plus/icons-vue'
import type { MarketIndex } from '@/api/market'

defineProps<{
  indices: MarketIndex[]
  loading: boolean
  updateTime: string
}>()

defineEmits<{
  (e: 'refresh'): void
}>()

function getColorClass(change?: number): string {
  if (change === undefined || change === null) return ''
  return change > 0 ? 'rise' : change < 0 ? 'fall' : 'flat'
}

function getTextClass(change?: number): string {
  if (change === undefined || change === null) return 'flat-text'
  return change > 0 ? 'rise-text' : change < 0 ? 'fall-text' : 'flat-text'
}

function fmtPrice(v?: number | null): string {
  if (v === undefined || v === null) return '--'
  return v.toFixed(2)
}

function fmtChange(v?: number | null): string {
  if (v === undefined || v === null) return '--'
  return (v >= 0 ? '+' : '') + v.toFixed(2) + '%'
}

function fmtAmount(v?: number | null): string {
  if (v === undefined || v === null) return '--'
  if (v >= 1e8) return (v / 1e8).toFixed(2) + '亿'
  if (v >= 1e4) return (v / 1e4).toFixed(2) + '万'
  return v.toFixed(0)
}
</script>

<style scoped>
.indices-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 12px;
  margin-bottom: 16px;
}
.index-card {
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: 6px;
  padding: 16px;
}
.index-name {
  font-size: 13px;
  color: var(--text-muted);
  margin-bottom: 8px;
}
.index-price {
  font-size: 24px;
  font-weight: bold;
  margin-bottom: 4px;
}
.index-change {
  display: flex;
  justify-content: space-between;
  font-size: 13px;
}
.change-amount {
  font-size: 11px;
  opacity: 0.7;
}
.refresh-bar {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
}
.update-time {
  font-size: 12px;
  color: var(--text-muted);
}
.auto-tip {
  font-size: 11px;
  color: var(--text-faint);
}

.rise-text, .rise { color: #ef5350; }
.fall-text, .fall { color: #26a69a; }
.flat-text, .flat { color: var(--text-muted); }

@media (max-width: 768px) {
  .indices-grid { grid-template-columns: repeat(2, 1fr); }
}
</style>