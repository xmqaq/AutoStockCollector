<template>
  <div class="filter-actions">
    <el-select
      :model-value="typeFilter"
      @update:model-value="$emit('update:typeFilter', $event)"
      placeholder="全部类型"
      class="filter-select"
      clearable
      @change="$emit('search')"
    >
      <template #prefix>
        <el-icon><Filter /></el-icon>
      </template>
      <el-option
        v-for="cat in categories"
        :key="cat.id"
        :label="cat.name"
        :value="cat.id"
      />
    </el-select>
    
    <el-input
      :model-value="codeFilter"
      @update:model-value="$emit('update:codeFilter', $event)"
      placeholder="搜索关键词或股票代码"
      class="search-input"
      clearable
      @keyup.enter="$emit('search')"
      @clear="$emit('search')"
    >
      <template #prefix>
        <el-icon><Search /></el-icon>
      </template>
    </el-input>
    
    <el-button type="primary" class="search-btn" @click="$emit('search')">
      搜索
    </el-button>
  </div>
</template>

<script setup lang="ts">
import { Search, Filter } from '@element-plus/icons-vue'
import type { NewsCategory } from '@/api/news'

defineProps<{
  categories: NewsCategory[]
  typeFilter: string
  codeFilter: string
}>()

defineEmits<{
  (e: 'update:typeFilter', val: string): void
  (e: 'update:codeFilter', val: string): void
  (e: 'search'): void
}>()
</script>

<style scoped>
.filter-actions {
  display: flex;
  gap: 12px;
  align-items: center;
}

.filter-select {
  width: 140px;
}

.filter-select :deep(.el-input__wrapper) {
  border-radius: 20px;
  box-shadow: 0 0 0 1px var(--border-color-light, #dcdfe6) inset;
}

.search-input {
  width: 220px;
}

.search-input :deep(.el-input__wrapper) {
  border-radius: 20px;
  box-shadow: 0 0 0 1px var(--border-color-light, #dcdfe6) inset;
}

.search-btn {
  border-radius: 20px;
  padding: 8px 20px;
}
</style>
