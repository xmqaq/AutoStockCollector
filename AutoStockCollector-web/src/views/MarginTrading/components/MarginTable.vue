<template>
  <el-card shadow="never" class="section-card table-card" v-loading="loading">
    <template #header>
      <div class="card-header">
        <div class="header-left">
          <el-icon class="header-icon"><List /></el-icon>
          <span class="header-title">融资融券明细</span>
        </div>
        <el-tag size="small" type="info" effect="plain" round class="count-tag">
          共 {{ data.length }} 条记录
        </el-tag>
      </div>
    </template>
    <el-empty v-if="data.length === 0 && !loading" description="暂无融资融券数据" />
    <div v-else class="table-container">
      <el-table 
        :data="paginatedData" 
        stripe 
        size="default" 
        height="100%"
        class="custom-table"
      >
        <el-table-column prop="date" label="交易日期" min-width="20%" sortable fixed="left" align="center">
          <template #default="{ row }">
            <span class="date-text">{{ row.date }}</span>
          </template>
        </el-table-column>
        <el-table-column label="融资余额" min-width="20%" prop="rz_balance" sortable align="center">
          <template #default="{ row }">
            <span class="money-text highlight">{{ fmtAmount(row.rz_balance) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="融资买入额" min-width="20%" prop="rz_buy" sortable align="center">
          <template #default="{ row }">
            <span class="money-text">{{ fmtAmount(row.rz_buy) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="融券余量" min-width="20%" prop="rq_volume" sortable align="center">
          <template #default="{ row }">
            <span class="money-text">{{ fmtAmount(row.rq_volume) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="融券卖出量" min-width="20%" prop="rq_sell" sortable align="center">
          <template #default="{ row }">
            <span class="money-text">{{ fmtAmount(row.rq_sell) }}</span>
          </template>
        </el-table-column>
      </el-table>
      <div class="table-pagination-wrapper" v-if="data.length > pageSize">
        <el-pagination
          v-model:current-page="currentPage"
          v-model:page-size="pageSize"
          :page-sizes="[20, 50, 100, 200]"
          :total="data.length"
          layout="total, sizes, prev, pager, next, jumper"
          background
          class="custom-pagination"
        />
      </div>
    </div>
  </el-card>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { List } from '@element-plus/icons-vue'
import { fmtAmount } from '@/utils/format'
import type { MarginRecord } from '@/types'

const props = defineProps<{
  loading: boolean
  data: MarginRecord[]
}>()

const currentPage = ref(1)
const pageSize = ref(50)

const paginatedData = computed(() =>
  props.data.slice((currentPage.value - 1) * pageSize.value, currentPage.value * pageSize.value)
)

watch(() => props.data, () => {
  currentPage.value = 1
})
</script>

<style scoped>
.table-card {
  border-radius: 12px;
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  box-shadow: 0 2px 8px var(--bg-hover-subtle);
  flex: 1.2;
  display: flex;
  flex-direction: column;
  min-height: 0;
}
.table-card :deep(.el-card__header) {
  border-bottom: 1px solid var(--border-color);
  padding: 12px 16px;
}
.table-card :deep(.el-card__body) {
  flex: 1;
  min-height: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
}
.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.header-left {
  display: flex;
  align-items: center;
  gap: 8px;
}
.header-icon {
  font-size: 16px;
  color: var(--el-color-primary);
}
.header-title {
  color: var(--text-primary);
  font-size: 15px;
  font-weight: 600;
}
.count-tag {
  font-family: var(--font-mono);
  font-weight: 500;
}
.table-container {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}
.table-container :deep(.el-table) {
  flex: 1;
  min-height: 0;
  --el-table-border-color: var(--border-color-light);
  --el-table-header-bg-color: var(--bg-soft);
  --el-table-header-text-color: var(--text-muted);
}
.custom-table :deep(th.el-table__cell) {
  font-weight: 500;
  padding: 8px 0;
  text-align: center;
}
.custom-table :deep(.el-table__inner-wrapper::before) {
  display: none; /* 移除底部外边框 */
}
.date-text {
  font-family: var(--font-mono);
  color: var(--text-muted);
  font-size: 13px;
}
.money-text {
  font-family: var(--font-mono);
  font-size: 13px;
  color: var(--text-primary);
}
.money-text.highlight {
  font-weight: 600;
  color: var(--el-color-primary);
}
.table-pagination-wrapper {
  padding: 12px 16px;
  border-top: 1px solid var(--border-color);
  background: var(--bg-card);
  display: flex;
  justify-content: flex-end;
}
.custom-pagination :deep(.el-pagination__total),
.custom-pagination :deep(.el-pagination__sizes .el-select .el-input__wrapper) {
  color: var(--text-muted);
}
.custom-pagination :deep(.el-pager li:not(.is-active)) {
  background-color: transparent;
}
</style>