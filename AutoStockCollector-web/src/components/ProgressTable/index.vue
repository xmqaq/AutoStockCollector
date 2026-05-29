<template>
  <el-table :data="data" stripe style="width: 100%" v-loading="loading">
    <el-table-column prop="task_type" label="任务类型" width="160">
      <template #default="{ row }">
        <el-tag size="small" type="info">{{ taskTypeLabel(row.task_type) }}</el-tag>
      </template>
    </el-table-column>
    <el-table-column label="进度" min-width="200">
      <template #default="{ row }">
        <el-progress
          :percentage="calcPercent(row)"
          :status="progressStatus(row)"
          :stroke-width="8"
          :format="() => `${row.progress || row.success || 0}/${row.total || 0}`"
        />
      </template>
    </el-table-column>
    <el-table-column prop="success" label="成功" width="80" align="center">
      <template #default="{ row }">
        <span class="text-success">{{ row.success || 0 }}</span>
      </template>
    </el-table-column>
    <el-table-column prop="failed" label="失败" width="80" align="center">
      <template #default="{ row }">
        <span :class="row.failed > 0 ? 'text-danger' : 'text-muted'">{{ row.failed || 0 }}</span>
      </template>
    </el-table-column>
    <el-table-column label="状态" width="110" align="center">
      <template #default="{ row }">
        <span class="status-tag" :class="`status-${row.status}`">
          <span class="status-dot" />
          {{ badgeLabel(row) }}
        </span>
      </template>
    </el-table-column>
    <el-table-column label="数据量" width="100" align="center">
      <template #default="{ row }">
        <span class="text-count">{{ fmtCount(row.record_count) }}</span>
      </template>
    </el-table-column>
    <el-table-column label="数据区间" min-width="180">
      <template #default="{ row }">
        <span class="text-muted date-range">
          {{ row.date_from && row.date_to ? `${row.date_from} ~ ${row.date_to}` : '--' }}
        </span>
      </template>
    </el-table-column>
    <el-table-column v-if="showFreshness" label="新鲜度" width="100" align="center">
      <template #default="{ row }">
        <span :class="freshness(row.date_to).cls">{{ freshness(row.date_to).text }}</span>
      </template>
    </el-table-column>
  </el-table>
</template>

<script setup lang="ts">
import type { CollectProgress } from '@/types'

interface Props {
  data: CollectProgress[]
  loading?: boolean
  showFreshness?: boolean
}

defineProps<Props>()

function freshness(dateTo?: string): { text: string; cls: string } {
  if (!dateTo) return { text: '—', cls: 'fresh-none' }
  const diff = Math.floor((Date.now() - new Date(dateTo).getTime()) / 86400000)
  if (diff <= 1) return { text: '最新', cls: 'fresh-ok' }
  if (diff <= 7) return { text: `${diff} 天前`, cls: 'fresh-mid' }
  return { text: `${diff} 天前`, cls: 'fresh-stale' }
}

const TASK_TYPE_LABELS: Record<string, string> = {
  kline: 'K线数据',
  financial: '财务数据',
  news: '新闻资讯',
  fund_flow: '资金流向',
  dragon_tiger: '龙虎榜',
  margin: '融资融券',
  sector: '板块数据',
  stock_info: '股票信息',
}

function taskTypeLabel(type: string): string {
  return TASK_TYPE_LABELS[type] || type
}

function fmtCount(n?: number): string {
  if (!n) return '--'
  if (n >= 10000) return `${(n / 10000).toFixed(1)}万`
  return String(n)
}

function calcPercent(row: CollectProgress): number {
  if (row.percent !== undefined && row.percent > 0) return Math.min(100, Math.round(row.percent))
  if (!row.total || row.total === 0) return 0
  return Math.min(100, Math.round(((row.progress || row.success || 0) / row.total) * 100))
}

function progressStatus(row: CollectProgress): '' | 'success' | 'exception' | 'warning' {
  const pct = calcPercent(row)
  if (pct === 100) return 'success'
  if (row.failed > 0 && row.failed > (row.success || 0)) return 'exception'
  if (pct > 0) return ''
  return ''
}

function badgeType(row: CollectProgress): 'success' | 'danger' | 'warning' | 'info' | 'primary' {
  if (row.status === 'completed') return 'success'
  if (row.status === 'failed') return 'danger'
  if (row.status === 'running') return 'primary'
  if (row.status === 'cancelled') return 'warning'
  return 'info'
}

function badgeLabel(row: CollectProgress): string {
  const labels: Record<string, string> = {
    completed: '完成', failed: '失败', running: '进行中',
    cancelled: '取消', pending: '等待', not_started: '未开始',
  }
  return labels[row.status] || row.status || '未开始'
}
</script>

<style scoped>
.text-success {
  color: #67c23a;
}
.text-danger {
  color: #f56c6c;
}
.text-muted {
  color: #909399;
  font-size: 12px;
}
.text-count {
  color: #409eff;
  font-size: 13px;
  font-weight: 500;
}
.date-range {
  font-size: 11px;
}
.fresh-ok { color: #67c23a; }
.fresh-mid { color: #909399; }
.fresh-stale { color: #e6a23c; }
.fresh-none { color: #606266; }

.status-tag {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-size: 12px;
  font-weight: 500;
  padding: 2px 8px;
  border-radius: 10px;
}
.status-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  flex-shrink: 0;
}
.status-completed  { color: #67c23a; background: rgba(103,194,58,.12); }
.status-completed  .status-dot { background: #67c23a; }
.status-running    { color: #409eff; background: rgba(64,158,255,.12); }
.status-running    .status-dot { background: #409eff; box-shadow: 0 0 4px #409eff; }
.status-failed     { color: #f56c6c; background: rgba(245,108,108,.12); }
.status-failed     .status-dot { background: #f56c6c; }
.status-cancelled  { color: #e6a23c; background: rgba(230,162,60,.12); }
.status-cancelled  .status-dot { background: #e6a23c; }
.status-pending,
.status-not_started,
.status-unknown    { color: #909399; background: rgba(144,147,153,.12); }
.status-pending    .status-dot,
.status-not_started .status-dot,
.status-unknown    .status-dot { background: #909399; }
</style>
