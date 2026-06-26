<template>
  <el-card shadow="never" class="section-card table-card" v-loading="loading">
    <template #header>
      <div class="card-header">
        <div class="header-left">
          <el-icon class="header-icon"><List /></el-icon>
          <span class="header-title">板块列表</span>
        </div>
        <el-tag size="small" type="info" effect="plain" round class="count-tag">
          共 {{ sectors.length }} 个板块
        </el-tag>
      </div>
    </template>
    <el-empty v-if="sectors.length === 0 && !loading" description="暂无板块数据" />
    <div v-else class="table-container">
      <el-table 
        :data="paginatedSectors" 
        stripe 
        size="default" 
        height="100%"
        class="custom-table"
      >
        <el-table-column prop="name" label="板块名称" min-width="100" align="center">
          <template #default="{ row }">
            <el-link type="primary" :underline="false" class="sector-link" @click="$emit('show-stocks', row.name)">
              {{ row.name }}
            </el-link>
          </template>
        </el-table-column>
        <el-table-column label="净流入" min-width="200" prop="net_flow" sortable align="center">
          <template #default="{ row }">
            <span class="money-text" :class="(row.net_flow || 0) >= 0 ? 'is-rise' : 'is-fall'">
              {{ fmtAmount(row.net_flow || 0) }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="涨跌幅" min-width="100" prop="change_rate" sortable align="center">
          <template #default="{ row }">
            <span class="money-text" :class="(row.change_rate || 0) >= 0 ? 'is-rise' : 'is-fall'">
              {{ fmtChange(row.change_rate || 0) }}
            </span>
          </template>
        </el-table-column>
      </el-table>
      <div class="table-pagination-wrapper" v-if="sectors.length > pageSize">
        <el-pagination
          v-model:current-page="currentPage"
          v-model:page-size="pageSize"
          :page-sizes="[20, 50, 100, 200]"
          :total="sectors.length"
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
import { fmtAmount, fmtChange } from '@/utils/format'
import type { SectorRecord } from '@/types'

const props = defineProps<{
  loading: boolean
  sectors: SectorRecord[]
}>()

defineEmits<{
  (e: 'show-stocks', name: string): void
}>()

const currentPage = ref(1)
const pageSize = ref(50)

const paginatedSectors = computed(() =>
  props.sectors.slice((currentPage.value - 1) * pageSize.value, currentPage.value * pageSize.value)
)

watch(() => props.sectors.length, () => {
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
}
.custom-table :deep(.el-table__inner-wrapper::before) {
  display: none;
}
.sector-link {
  font-weight: 500;
}
.money-text {
  font-family: var(--font-mono);
  font-size: 13px;
  font-weight: 500;
  position: relative;
  z-index: 1;
}
.money-text.is-rise { color: var(--el-color-danger); }
.money-text.is-fall { color: var(--el-color-success); }

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