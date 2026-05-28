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
    <el-table-column label="状态" width="100" align="center">
      <template #default="{ row }">
        <el-badge
          :type="badgeType(row)"
          :value="badgeLabel(row)"
          :max="9999"
        />
      </template>
    </el-table-column>
    <el-table-column label="耗时" width="90" align="center">
      <template #default="{ row }">
        <span class="text-muted">{{ row.elapsed_time ? `${row.elapsed_time}s` : '--' }}</span>
      </template>
    </el-table-column>
  </el-table>
</template>

<script setup lang="ts">
import type { CollectProgress } from '@/types'
import { fmtDateTime } from '@/utils/format'

interface Props {
  data: CollectProgress[]
  loading?: boolean
}

defineProps<Props>()

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
</style>
