<template>
  <el-card shadow="never" class="section-card data-hub-card" v-if="dataLoaded">
    <div class="hub-header">
      <div class="hub-title">
        <el-icon><DataAnalysis /></el-icon>
        <span>底层数据覆盖雷达</span>
      </div>
      <el-button class="modern-btn" text size="small" @click="router.push('/data-monitor')">
        进入数据中心 →
      </el-button>
    </div>
    
    <div class="hub-grid">
      <div
        v-for="row in healthCards"
        :key="row.value"
        :class="['hub-item', `hub-item--${row.health}`]"
        @click="router.push(row.route)"
      >
        <div class="item-header">
          <div :class="['status-dot', row.health]"></div>
          <span class="item-name">{{ row.label }}</span>
        </div>
        <div class="item-body">
          <span class="item-count num">{{ row.record_count != null ? row.record_count.toLocaleString() : '--' }}</span>
          <span class="item-unit">{{ row.unit }}</span>
        </div>
        <div class="item-footer">
          <span class="item-date">{{ row.latest_date || '暂无数据' }}</span>
        </div>
      </div>
    </div>
  </el-card>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { useCollectStore } from '@/stores/collectStore'
import { TYPE_LABEL } from '@/utils/collectTypes'
import { DataAnalysis } from '@element-plus/icons-vue'

defineProps<{
  dataLoaded: boolean
}>()

const router = useRouter()
const collectStore = useCollectStore()

const CARD_META: Record<string, { unit: string; route: string }> = {
  kline:        { unit: '条', route: '/market' },
  financial:    { unit: '条', route: '/stock-detail' },
  dragon_tiger: { unit: '条', route: '/dragon-tiger' },
  margin:       { unit: '条', route: '/margin-trading' },
  news:         { unit: '条', route: '/news' },
  fund_flow:    { unit: '条', route: '/fund-flow' },
  sector:       { unit: '条', route: '/sector-flow' },
  stock_info:   { unit: '只', route: '/market' },
}

const CARD_ORDER = ['kline', 'financial', 'dragon_tiger', 'margin', 'news', 'fund_flow', 'sector', 'stock_info']

const healthCards = computed(() => {
  const byType: Record<string, any> = {}
  collectStore.progressList.forEach(p => { byType[p.task_type] = p })
  return CARD_ORDER.map(key => {
    const p = byType[key] || {}
    const meta = CARD_META[key] || { unit: '条', route: '/data-monitor' }
    return {
      value: key,
      label: (TYPE_LABEL as Record<string, string>)[key] || key,
      unit: meta.unit,
      route: meta.route,
      record_count: (p.record_count ?? (p as any).record_count) as number | null,
      latest_date: ((p as any).latest_date ?? (p as any).date_to) as string | null,
      health: ((p as any).health ?? ((p as any).record_count > 0 ? 'stale' : 'error')) as string,
    }
  })
})
</script>

<style scoped>
.data-hub-card {
  background: var(--bg-card);
  border-radius: var(--radius-lg);
  border: 1px solid var(--border-color);
  padding: 16px 20px;
}

.data-hub-card :deep(.el-card__body) {
  padding: 0;
}

.hub-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.hub-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
}

.hub-title .el-icon {
  color: var(--brand-500);
}

.modern-btn {
  color: var(--brand-500);
  font-weight: 500;
}

.hub-grid {
  display: grid;
  grid-template-columns: repeat(8, 1fr);
  gap: 12px;
}

.hub-item {
  display: flex;
  flex-direction: column;
  padding: 12px;
  background: var(--bg-page);
  border: 1px solid var(--border-light);
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s;
}

.hub-item:hover {
  background: var(--bg-soft);
  border-color: var(--brand-300);
  transform: translateY(-2px);
  box-shadow: var(--shadow-sm);
}

.item-header {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 8px;
}

.status-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
}

.status-dot.ok { background-color: var(--el-color-success); box-shadow: 0 0 4px var(--el-color-success); }
.status-dot.stale { background-color: var(--el-color-warning); box-shadow: 0 0 4px var(--el-color-warning); }
.status-dot.error { background-color: var(--el-color-danger); box-shadow: 0 0 4px var(--el-color-danger); }

.item-name {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
}

.item-body {
  display: flex;
  align-items: baseline;
  gap: 4px;
  margin-bottom: 4px;
}

.item-count {
  font-size: 16px;
  font-weight: 700;
  color: var(--brand-600);
}

.item-unit {
  font-size: 11px;
  color: var(--text-secondary);
}

.item-footer {
  margin-top: auto;
}

.item-date {
  font-size: 11px;
  color: var(--text-muted);
  font-family: monospace;
}

.hub-item--error {
  border-color: var(--el-color-danger-light-5);
  background: var(--el-color-danger-light-9);
}
.hub-item--error .item-count { color: var(--el-color-danger); }

.hub-item--stale {
  border-color: var(--el-color-warning-light-5);
  background: var(--el-color-warning-light-9);
}
.hub-item--stale .item-count { color: var(--el-color-warning); }

.num {
  font-variant-numeric: tabular-nums;
}
</style>
