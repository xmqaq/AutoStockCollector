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
          :format="() => hasDbData(row) ? fmtCount(row.record_count) : `${row.progress || row.success || 0}/${row.total || 0}`"
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
        <span class="status-tag" :class="hasDbData(row) ? 'status-completed' : `status-${row.status}`">
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
        <span :class="freshness(row.date_to, row.task_type).cls">{{ freshness(row.date_to, row.task_type).text }}</span>
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

// 推算"当前应已披露的最新财报报告期"（A股定期报告披露截止日）
// 一季报 4-30 前(报告期 3-31) / 半年报 8-31 前(6-30) / 三季报 10-31 前(9-30) / 年报 次年 4-30 前(12-31)
function expectedLatestReportPeriod(now: Date): Date {
  const cands: Array<[Date, Date]> = []
  for (const yr of [now.getFullYear(), now.getFullYear() - 1]) {
    cands.push([new Date(yr, 3, 30), new Date(yr - 1, 11, 31)]) // 年报
    cands.push([new Date(yr, 3, 30), new Date(yr, 2, 31)])      // 一季报
    cands.push([new Date(yr, 7, 31), new Date(yr, 5, 30)])      // 半年报
    cands.push([new Date(yr, 9, 31), new Date(yr, 8, 30)])      // 三季报
  }
  return cands.filter(([d]) => d <= now).map(([, p]) => p).reduce((a, b) => (b > a ? b : a))
}

function freshness(dateTo?: string, type?: string): { text: string; cls: string } {
  if (!dateTo) return { text: '—', cls: 'fresh-none' }
  // 财务为季度披露：只要已拥有当前应披露的最新报告期即为最新，不按自然天数判断
  if (type === 'financial') {
    const ok = new Date(dateTo) >= expectedLatestReportPeriod(new Date())
    return ok ? { text: '最新', cls: 'fresh-ok' } : { text: '待更新', cls: 'fresh-stale' }
  }
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

function hasDbData(row: CollectProgress): boolean {
  return row.status === 'not_started' && (row.record_count || 0) > 0
}

function calcPercent(row: CollectProgress): number {
  if (hasDbData(row)) return 100
  if (row.percent !== undefined && row.percent > 0) return Math.min(100, Math.round(row.percent))
  if (!row.total || row.total === 0) return 0
  return Math.min(100, Math.round(((row.progress || row.success || 0) / row.total) * 100))
}

function progressStatus(row: CollectProgress): '' | 'success' | 'exception' | 'warning' {
  if (hasDbData(row)) return 'success'
  const pct = calcPercent(row)
  if (pct === 100) return 'success'
  if (row.failed > 0 && row.failed > (row.success || 0)) return 'exception'
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
  if (hasDbData(row)) return '已有数据'
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
  color: var(--text-muted);
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
.fresh-mid { color: var(--text-muted); }
.fresh-stale { color: #e6a23c; }
.fresh-none { color: var(--text-faint); }

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
.status-unknown    { color: var(--text-muted); background: rgba(144,147,153,.12); }
.status-pending    .status-dot,
.status-not_started .status-dot,
.status-unknown    .status-dot { background: var(--text-muted); }
</style>
