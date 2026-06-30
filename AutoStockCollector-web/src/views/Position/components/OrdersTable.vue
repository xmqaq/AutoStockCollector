<template>
  <el-card shadow="never" class="pro-card">
    <template #header>
      <div class="header-row">
        <span class="card-title">挂单与委托</span>
        <el-tag v-if="pendingCount > 0" type="warning" size="small">{{ pendingCount }} 笔待成交</el-tag>
      </div>
    </template>
    <div class="order-list">
      <div v-for="o in orders" :key="o._id" class="order-item">
        <div class="trade-icon" :class="o.action === 'buy' ? 'bg-buy' : 'bg-sell'">
          {{ o.action === 'buy' ? '买' : '卖' }}
        </div>
        <div class="order-info">
          <div class="trade-header">
            <span class="trade-name">{{ o.name || o.code }}</span>
            <span class="trade-code">{{ o.code }}</span>
            <el-tag :type="statusTagType(o.status)" size="small" effect="light">{{ statusText(o.status) }}</el-tag>
          </div>
          <div class="trade-detail">
            <span>{{ o.shares }} 股 @ <span class="number-font">{{ (o.filled_price ?? o.price ?? 0).toFixed(2) }}</span></span>
            <span class="trade-time">{{ (o.filled_at || o.created_at).slice(5, 16) }}</span>
          </div>
          <div v-if="o.status === 'cancelled' && o.cancel_reason" class="order-reason">
            撤单原因：{{ o.cancel_reason }}
          </div>
        </div>
        <div class="order-action" v-if="o.status === 'pending'">
          <el-button type="danger" plain size="small" :loading="cancellingId === o._id" @click="$emit('cancel', o)">
            撤单
          </el-button>
        </div>
      </div>
      <el-empty v-if="orders.length === 0" description="暂无挂单/委托记录" :image-size="60" />
    </div>
  </el-card>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { PaperOrder } from '@/api/paper'

const props = defineProps<{
  orders: PaperOrder[]
}>()

defineEmits<{
  (e: 'cancel', order: PaperOrder): void
}>()

const cancelling = defineModel<string | null>('cancelling', { default: null })
const cancellingId = computed(() => cancelling.value)

const pendingCount = computed(() => props.orders.filter(o => o.status === 'pending').length)

function statusTagType(status: string) {
  if (status === 'filled') return 'success'
  if (status === 'pending') return 'warning'
  return 'info'
}
function statusText(status: string) {
  if (status === 'filled') return '已成交'
  if (status === 'pending') return '挂单中'
  return '已撤单'
}
</script>

<style scoped>
.pro-card {
  background: var(--bg-card, #ffffff);
  border: 1px solid var(--border-color, var(--border-color));
  border-radius: 8px;
  box-shadow: 0 2px 12px var(--bg-hover-subtle);
  display: flex;
  flex-direction: column;
  max-height: 700px;
}

.pro-card :deep(.el-card__header) {
  border-bottom: 1px solid var(--border-color, #ebeef5);
  padding: 16px 20px;
  background-color: var(--bg-hover-subtle);
}

.pro-card :deep(.el-card__body) {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  padding-bottom: 0;
}

.header-row { display: flex; align-items: center; justify-content: space-between; width: 100%; }

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

.order-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
  flex: 1;
  overflow-y: auto;
  max-height: 630px;
  padding-right: 4px;
  padding-bottom: 20px;
}

.order-list::-webkit-scrollbar { width: 6px; }
.order-list::-webkit-scrollbar-thumb { background: rgba(144, 147, 153, 0.3); border-radius: 3px; }

.order-item {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 12px;
  border-radius: 8px;
  background: var(--bg-soft, #f8f9fa);
  border: 1px solid var(--border-color-light, #f0f2f5);
  transition: all 0.2s;
}

.order-item:hover {
  transform: translateX(2px);
  border-color: var(--border-color, var(--border-color));
  box-shadow: 0 2px 8px var(--bg-hover-subtle);
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

.bg-buy { background: linear-gradient(135deg, var(--el-color-danger), #e53935); box-shadow: 0 2px 6px rgba(239, 83, 80, 0.3); }
.bg-sell { background: linear-gradient(135deg, var(--el-color-success), #00897b); box-shadow: 0 2px 6px rgba(38, 166, 154, 0.3); }

.order-info { flex: 1; display: flex; flex-direction: column; gap: 4px; }
.trade-header { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.trade-name { font-size: 14px; font-weight: 600; color: var(--text-primary); }
.trade-code { font-size: 12px; color: var(--text-muted); background: var(--bg-hover-subtle); padding: 1px 6px; border-radius: 4px; }
.trade-detail { font-size: 13px; color: var(--text-regular); display: flex; justify-content: space-between; align-items: center; }
.number-font { font-family: var(--font-mono, "DIN Alternate", "Helvetica Neue", sans-serif); font-weight: 500; }
.trade-time { font-size: 12px; color: var(--text-muted); font-family: var(--font-mono); }
.order-reason { font-size: 11px; color: var(--text-muted); margin-top: 2px; }
.order-action { display: flex; align-items: center; }
</style>
