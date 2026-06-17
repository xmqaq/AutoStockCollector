<template>
  <el-card shadow="never" class="section-card" v-loading="loading">
    <template #header>
      <span>龙虎榜数据（共 {{ total }} 条）</span>
    </template>
    <el-empty v-if="data.length === 0 && !loading" description="暂无龙虎榜数据" />
    <el-table v-else :data="data" stripe>
      <el-table-column prop="date" label="日期" width="120" sortable />
      <el-table-column prop="code" label="代码" width="110">
        <template #default="{ row }">
          <span class="code-link" @click="goToStock(row.code)">{{ row.code }}</span>
        </template>
      </el-table-column>
      <el-table-column prop="name" label="名称" width="100" />
      <el-table-column prop="reason" label="上榜原因" min-width="220">
        <template #default="{ row }">
          <el-tag
            :type="getReasonTagType(row.reason)"
            size="small"
            effect="light"
            style="white-space: normal; height: auto; text-align: left; padding: 4px 8px; line-height: 1.4;"
          >
            {{ row.reason }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="上榜金额" width="130" sortable prop="total_amount">
        <template #default="{ row }">
          <span>{{ fmtAmount(row.total_amount) }}</span>
        </template>
      </el-table-column>
      <el-table-column label="净买入" width="130" sortable prop="net_buy">
        <template #default="{ row }">
          <span :style="{ color: row.net_buy >= 0 ? RISE_COLOR : FALL_COLOR }">
            {{ fmtAmount(row.net_buy) }}
          </span>
        </template>
      </el-table-column>
      <el-table-column label="涨跌幅" width="110" sortable prop="change_rate">
        <template #default="{ row }">
          <div v-if="row.change_rate !== undefined && row.change_rate !== 0"
            :style="{ color: row.change_rate >= 0 ? RISE_COLOR : FALL_COLOR, display: 'flex', alignItems: 'center', gap: '2px' }">
            <el-icon v-if="row.change_rate > 0"><Top /></el-icon>
            <el-icon v-else-if="row.change_rate < 0"><Bottom /></el-icon>
            <span>{{ fmtChange(row.change_rate) }}</span>
          </div>
          <span v-else>--</span>
        </template>
      </el-table-column>
      <el-table-column label="收盘价" width="100" prop="close">
        <template #default="{ row }">
          {{ row.close ? fmtNumber(row.close) : '--' }}
        </template>
      </el-table-column>
    </el-table>
    <el-pagination
      v-if="total > 0"
      :current-page="currentPage"
      :page-size="pageSize"
      :page-sizes="[20, 50, 100, 200]"
      :total="total"
      layout="total, sizes, prev, pager, next"
      background
      class="table-pagination"
      @update:current-page="$emit('update:currentPage', $event)"
      @update:page-size="$emit('update:pageSize', $event)"
      @current-change="$emit('page-change', $event)"
      @size-change="$emit('size-change', $event)"
    />
  </el-card>
</template>

<script setup lang="ts">
import { useRouter } from 'vue-router'
import { Top, Bottom } from '@element-plus/icons-vue'
import { fmtAmount, fmtChange, fmtNumber, RISE_COLOR, FALL_COLOR } from '@/utils/format'
import type { DragonTigerRecord } from '@/types'

function getReasonTagType(reason: string) {
  if (!reason) return 'info'
  if (reason.includes('跌') || reason.includes('退市')) return 'success'
  if (reason.includes('涨')) return 'danger'
  return 'warning'
}

defineProps<{
  data: DragonTigerRecord[]
  loading: boolean
  total: number
  currentPage: number
  pageSize: number
}>()

defineEmits<{
  (e: 'update:currentPage', val: number): void
  (e: 'update:pageSize', val: number): void
  (e: 'page-change', val: number): void
  (e: 'size-change', val: number): void
}>()

const router = useRouter()

function goToStock(code: string) {
  router.push({ path: '/stock-detail', query: { code } })
}
</script>

<style scoped>
.section-card {
  background: var(--bg-card);
  border: 1px solid var(--border-color);
}
.section-card :deep(.el-card__header) {
  border-bottom: 1px solid var(--border-color);
  padding: 12px 16px;
  color: var(--text-primary);
  font-size: 14px;
  font-weight: 600;
}
.code-link {
  color: var(--el-color-primary);
  cursor: pointer;
}
.code-link:hover {
  color: #79bbff;
}
.table-pagination {
  margin-top: 12px;
  display: flex;
  justify-content: flex-end;
}
.table-pagination :deep(.el-pagination__total),
.table-pagination :deep(.el-pagination__sizes .el-select .el-input__wrapper) {
  color: var(--text-muted);
}
</style>
