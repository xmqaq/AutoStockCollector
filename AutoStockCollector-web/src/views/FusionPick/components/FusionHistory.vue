<template>
  <div class="fp-panel-actions">
    <el-button size="small" @click="$emit('load-history')" :loading="histLoading">刷新历史</el-button>
  </div>
  <el-table v-if="history.length" :data="history" size="small" @row-click="(r:any) => $emit('load-result', r.run_id)" class="fp-history-table">
    <el-table-column label="时间"><template #default="{ row }">{{ fmtTime(row.timestamp) }}</template></el-table-column>
    <el-table-column label="市场"><template #default="{ row }"><el-tag size="small" :type="stateTagType(row.market_state)">{{ stateText(row.market_state) }}</el-tag></template></el-table-column>
    <el-table-column label="模式"><template #default="{ row }">{{ row.mode === 'quick' ? '快速' : '完整' }}</template></el-table-column>
    <el-table-column prop="universe_count" label="全市场" />
    <el-table-column prop="candidate_count" label="候选" />
    <el-table-column prop="selected_count" label="精选" />
  </el-table>
  <el-empty v-else description="暂无历史记录" />
</template>

<script setup lang="ts">
import type { FusionHistoryItem } from '@/api/fusionPick'

defineProps<{
  histLoading: boolean
  history: FusionHistoryItem[]
}>()

defineEmits<{
  (e: 'load-history'): void
  (e: 'load-result', runId: string): void
}>()

function fmtTime(t?: string | null) {
  if (!t) return ''
  try { return new Date(t).toLocaleString('zh-CN', { hour12: false }) } catch { return t }
}
function stateText(s?: string) { return s === 'bull' ? '牛市' : s === 'bear' ? '熊市' : '震荡市' }
function stateTagType(s?: string) { return s === 'bull' ? 'danger' : s === 'bear' ? 'success' : 'info' }
</script>

<style scoped>
.fp-panel-actions { display: flex; align-items: center; gap: 12px; margin-bottom: 16px; flex-wrap: wrap; }
.fp-history-table { cursor: pointer; }
</style>
