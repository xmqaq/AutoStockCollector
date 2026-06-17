<template>
  <el-card shadow="never" class="section-card health-section-card">
    <div class="section-header">
      <h2 class="section-title">数据健康状态</h2>
      <el-button class="modern-btn" text @click="router.push('/data-monitor')">
        → 去采集中心
      </el-button>
    </div>

    <!-- Skeleton: before first data load -->
    <template v-if="!dataLoaded">
      <div class="health-pill-grid">
        <div v-for="i in 8" :key="i" class="health-pill sk-pill">
          <div class="sk-line" style="height:12px;width:80%"></div>
        </div>
      </div>
    </template>

    <!-- Real: after first data load -->
    <template v-else>
      <!-- Ultra compact pill grid -->
      <div class="health-pill-grid">
        <div
          v-for="row in healthCards"
          :key="row.value"
          :class="['health-pill', `health-pill--${row.health}`]"
          @click="router.push(row.route)"
        >
          <div :class="['pill-indicator', row.health]"></div>
          <span class="pill-name">{{ row.label }}</span>
          <div class="pill-divider"></div>
          <span class="pill-date">{{ row.latest_date ?? '--' }}</span>
          
          <!-- Hover details -->
          <div class="pill-hover-info">
            <span class="hover-count num">{{ row.record_count != null ? row.record_count.toLocaleString() : '--' }}</span>
            <span class="hover-unit">{{ row.unit }}</span>
            <span class="hover-status">{{ row.health === 'ok' ? '最新' : row.health === 'stale' ? '需更新' : '异常' }}</span>
          </div>
        </div>
      </div>
    </template>
  </el-card>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { useCollectStore } from '@/stores/collectStore'
import { TYPE_LABEL } from '@/utils/collectTypes'

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
.section-card {
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-sm);
  overflow: hidden;
}

.health-section-card {
  margin-bottom: 0;
}

.health-section-card :deep(.el-card__body) {
  padding: 20px 24px;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.section-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
  letter-spacing: -0.01em;
}

/* --- Health Cards Grid --- */
.health-pill-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
}

.health-pill {
  background: var(--bg-card);
  border-radius: var(--radius-sm);
  padding: 10px 14px;
  border: 1px solid var(--border-color);
  cursor: pointer;
  transition: all 0.2s ease;
  display: flex;
  align-items: center;
  position: relative;
  overflow: hidden;
}

.health-pill:hover {
  background: var(--bg-hover-subtle);
  border-color: var(--brand-300);
}

.health-pill--error {
  background: var(--tint-danger-bg);
  border-color: rgba(239, 68, 68, 0.2);
}

.pill-indicator {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  margin-right: 10px;
  flex-shrink: 0;
}

.pill-indicator.ok { background-color: var(--color-success); box-shadow: 0 0 6px rgba(16, 185, 129, 0.4); }
.pill-indicator.stale { background-color: var(--color-warning); box-shadow: 0 0 6px rgba(245, 158, 11, 0.4); }
.pill-indicator.error { background-color: var(--color-danger); box-shadow: 0 0 6px rgba(239, 68, 68, 0.4); }

.pill-name {
  font-weight: 500;
  color: var(--text-primary);
  font-size: 13px;
  white-space: nowrap;
}

.pill-divider {
  flex: 1;
  height: 1px;
  border-bottom: 1px dashed var(--border-color);
  margin: 0 10px;
  opacity: 0.5;
}

.pill-date {
  font-size: 12px;
  color: var(--text-muted);
  font-family: var(--font-mono);
  white-space: nowrap;
}

/* Hover Information Overlay */
.pill-hover-info {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background: var(--bg-elevated);
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  opacity: 0;
  transform: translateY(100%);
  transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
}

.health-pill:hover .pill-hover-info {
  opacity: 1;
  transform: translateY(0);
}

.hover-count {
  font-size: 15px;
  font-weight: 700;
  color: var(--text-primary);
}

.hover-unit {
  font-size: 12px;
  color: var(--text-secondary);
}

.hover-status {
  font-size: 11px;
  padding: 2px 6px;
  border-radius: 4px;
  background: var(--bg-soft);
  margin-left: 8px;
}

/* --- Modern Button --- */
.modern-btn {
  color: var(--brand-600);
  font-weight: 600;
  transition: all 0.2s;
}

.modern-btn:hover {
  background: var(--bg-hover-subtle);
  transform: translateX(2px);
}

/* --- Skeleton --- */
@keyframes shimmer {
  0%   { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}

.sk-line {
  background: linear-gradient(
    90deg,
    var(--bg-hover-subtle) 25%,
    var(--bg-hover) 50%,
    var(--bg-hover-subtle) 75%
  );
  background-size: 200% 100%;
  animation: shimmer 1.5s infinite;
  border-radius: 4px;
}

.sk-pill {
  height: 34px;
}
</style>
