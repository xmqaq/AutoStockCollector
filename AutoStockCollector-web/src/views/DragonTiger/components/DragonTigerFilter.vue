<template>
  <el-card shadow="never" class="section-card filter-card">
    <div class="filter-bar">
      <el-input
        v-model="codeFilter"
        placeholder="搜索股票代码 / 拼音缩写..."
        class="main-search-input"
        clearable
        @keyup.enter="handleSearch"
      >
        <template #prefix>
          <el-icon><Search /></el-icon>
        </template>
        <template #append>
          <el-button @click="handleSearch">搜索</el-button>
        </template>
      </el-input>

      <el-popover placement="bottom-end" :width="320" trigger="click">
        <template #reference>
          <el-button plain class="advanced-filter-btn">
            <el-icon><Filter /></el-icon> 高级筛选
          </el-button>
        </template>
        <div class="advanced-filter-panel">
          <div class="filter-item">
            <div class="filter-label">日期范围</div>
            <el-date-picker
              v-model="dateRange"
              type="daterange"
              range-separator="至"
              start-placeholder="开始日期"
              end-placeholder="结束日期"
              format="YYYY年MM月DD日"
              value-format="YYYY-MM-DD"
              style="width: 100%"
            />
          </div>
          <div class="filter-actions">
            <el-button size="small" @click="resetFilters">重置</el-button>
            <el-button type="primary" size="small" @click="handleSearch">应用筛选</el-button>
          </div>
        </div>
      </el-popover>
    </div>
  </el-card>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { Search, Filter } from '@element-plus/icons-vue'

const emit = defineEmits<{
  (e: 'search', params: { dateRange: [string, string] | null, code: string }): void
}>()

const dateRange = ref<[string, string] | null>(null)
const codeFilter = ref('')

function handleSearch() {
  emit('search', { dateRange: dateRange.value, code: codeFilter.value })
}

function resetFilters() {
  dateRange.value = null
  codeFilter.value = ''
  handleSearch()
}
</script>

<style scoped>
.section-card {
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: 8px;
}
.filter-card {
  border: none;
  background: transparent;
}
.filter-card :deep(.el-card__body) {
  padding: 0;
}
.filter-bar {
  display: flex;
  gap: 16px;
  align-items: center;
  flex-wrap: nowrap;
}
.main-search-input {
  max-width: 400px;
}
.main-search-input :deep(.el-input-group__append) {
  background-color: var(--el-color-primary);
  color: white;
  border: 1px solid var(--el-color-primary);
}
.main-search-input :deep(.el-input-group__append:hover) {
  background-color: var(--el-color-primary-light-3);
  border-color: var(--el-color-primary-light-3);
}
.advanced-filter-btn {
  height: 32px;
}
.advanced-filter-panel {
  padding: 8px 4px;
}
.filter-item {
  margin-bottom: 20px;
}
.filter-label {
  font-size: 13px;
  color: var(--text-regular);
  margin-bottom: 8px;
  font-weight: 500;
}
.filter-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 16px;
  border-top: 1px solid var(--border-color-light, #ebeef5);
  padding-top: 16px;
}
</style>
