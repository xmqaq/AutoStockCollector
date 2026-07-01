<template>
  <div class="multi-tf-panel">
    <div class="mtf-header">
      <span class="mtf-title">📡 多周期融合</span>
      <el-tag :type="resonanceType" effect="dark" size="default">{{ multiTf.resonance }}</el-tag>
    </div>
    <div v-if="warning" class="mtf-warning">
      <el-icon><Warning /></el-icon>
      <span>{{ warning }}</span>
    </div>
    <div class="mtf-cards">
      <div v-for="tf in tfEntries" :key="tf.key" :class="['mtf-card', `mtf-${tf.key}`]">
        <div class="mtf-card-title">{{ tf.label }}</div>
        <div :class="['mtf-trend', trendClass(tf.entry?.trend)]">{{ trendLabel(tf.entry?.trend) }}</div>
        <div class="mtf-structure">{{ structureLabel(tf.entry?.structure) }}</div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { Warning } from '@element-plus/icons-vue'
import type { PaMultiTf } from '@/api/priceAction'

const props = defineProps<{
  multiTf: PaMultiTf
  warning?: string
}>()

const tfEntries = computed(() => [
  { key: 'monthly', label: '月线', entry: props.multiTf.monthly },
  { key: 'weekly', label: '周线', entry: props.multiTf.weekly },
  { key: 'daily', label: '日线', entry: props.multiTf.daily },
])

const resonanceType = computed(() => {
  const r = props.multiTf.resonance || ''
  if (r.includes('共振')) return 'danger' as const
  if (r.includes('分歧') || r.includes('逆')) return 'warning' as const
  return 'info' as const
})

function trendClass(t?: string): string {
  if (!t) return 'flat'
  if (t.includes('Bullish')) return 'up'
  if (t.includes('Bearish')) return 'down'
  return 'flat'
}

function trendLabel(t?: string): string {
  if (!t) return '—'
  if (t === 'Strong Bullish') return '强势多头'
  if (t === 'Bullish') return '多头'
  if (t === 'Strong Bearish') return '强势空头'
  if (t === 'Bearish') return '空头'
  return '震荡'
}

function structureLabel(s?: string): string {
  if (!s) return '—'
  return s
}
</script>

<style scoped>
.multi-tf-panel {
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: 12px;
  padding: 14px 16px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.mtf-header { display: flex; align-items: center; justify-content: space-between; }
.mtf-title { font-size: 15px; font-weight: 600; color: var(--text-primary); }
.mtf-warning {
  display: flex; align-items: center; gap: 6px;
  font-size: 12px; color: var(--el-color-warning);
  background: var(--el-color-warning-light-9);
  padding: 6px 10px; border-radius: 6px;
}
.mtf-cards { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; }
.mtf-card {
  text-align: center; padding: 10px 8px; border-radius: 8px;
  background: var(--bg-soft);
}
.mtf-card-title { font-size: 12px; color: var(--text-muted); margin-bottom: 6px; }
.mtf-trend { font-size: 15px; font-weight: 600; }
.mtf-trend.up { color: #f23645; }
.mtf-trend.down { color: #11c27e; }
.mtf-trend.flat { color: var(--text-secondary); }
.mtf-structure { font-size: 11px; color: var(--text-faint); margin-top: 4px; }
@media (max-width: 600px) { .mtf-cards { grid-template-columns: 1fr; } }
</style>
