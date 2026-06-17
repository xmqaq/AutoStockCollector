<template>
  <el-card shadow="never" class="table-card">
    <el-table :data="records" v-loading="loading" stripe size="small" max-height="600px">
      <el-table-column prop="timestamp" label="时间" width="170">
        <template #default="{ row }">{{ fmtTime(row.timestamp) }}</template>
      </el-table-column>
      <el-table-column prop="provider" label="供应商" width="110">
        <template #default="{ row }">
          <el-tag :type="providerTagType(row.provider)" size="small" effect="plain">{{ row.provider }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="task_type" label="任务类型" width="140" />
      <el-table-column prop="success" label="状态" width="70" align="center">
        <template #default="{ row }">
          <el-tag :type="row.success ? 'success' : 'danger'" size="small">{{ row.success ? '成功' : '失败' }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="error" label="错误信息" min-width="200">
        <template #default="{ row }">
          <span v-if="row.error" class="err-text">{{ row.error }}</span>
          <span v-else class="no-err">--</span>
        </template>
      </el-table-column>
      <el-table-column prop="model_name" label="模型" width="110" />
      <el-table-column prop="input_tokens" label="输入Token" width="100" align="right" />
      <el-table-column prop="output_tokens" label="输出Token" width="100" align="right" />
      <el-table-column label="耗时" width="90" align="right">
        <template #default="{ row }">{{ fmtLatency(row.response_time) }}</template>
      </el-table-column>
    </el-table>

    <div class="pagination-bar">
      <el-pagination
        :current-page="page"
        :page-size="size"
        :total="total"
        layout="total, prev, pager, next"
        background
        small
        @update:current-page="$emit('update:page', $event)"
        @current-change="$emit('page-change')"
      />
    </div>
  </el-card>
</template>

<script setup lang="ts">
import type { AICallRecord } from '@/api/aiCallHistory'

defineProps<{
  records: AICallRecord[]
  loading: boolean
  page: number
  size: number
  total: number
}>()

defineEmits<{
  (e: 'update:page', val: number): void
  (e: 'page-change'): void
}>()

function providerTagType(p: string) {
  const map: Record<string, string> = { deepseek: '', minimax: 'warning', agnes: 'info', qwen: 'danger', Qwen3: 'danger' }
  for (const [k, v] of Object.entries(map)) {
    if (p.includes(k)) return v || ''
  }
  return ''
}

function fmtTime(ts: string) {
  if (!ts) return ''
  return ts.replace('T', ' ').slice(0, 19)
}

function fmtLatency(ms?: number) {
  if (ms === undefined || ms === null) return '--'
  if (ms < 1000) return `${ms.toFixed(0)}ms`
  return `${(ms / 1000).toFixed(1)}s`
}
</script>

<style scoped>
.table-card { margin-bottom: 16px; }
.err-text { font-size: 11px; color: #f56c6c; word-break: break-all; }
.no-err { color: #ccc; }
.pagination-bar { display: flex; justify-content: flex-end; margin-top: 12px; }
</style>
