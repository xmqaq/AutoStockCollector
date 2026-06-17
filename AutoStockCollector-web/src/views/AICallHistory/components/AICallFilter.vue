<template>
  <div class="filter-bar">
    <el-input 
      v-model="localFilters.keyword" 
      placeholder="搜索供应商/任务类型/错误" 
      clearable 
      size="small" 
      class="search-input" 
      @clear="onSearch" 
      @keyup.enter="onSearch" 
    />
    <el-select 
      v-model="localFilters.provider" 
      placeholder="供应商" 
      clearable 
      size="small" 
      class="filter-select" 
      @change="onSearch"
    >
      <el-option v-for="p in providerOptions" :key="p" :label="p" :value="p" />
    </el-select>
    <el-select 
      v-model="localFilters.task_type" 
      placeholder="任务类型" 
      clearable 
      size="small" 
      class="filter-select" 
      @change="onSearch"
    >
      <el-option v-for="t in taskTypeOptions" :key="t" :label="t" :value="t" />
    </el-select>
    <el-select 
      v-model="localFilters.success" 
      placeholder="状态" 
      clearable 
      size="small" 
      class="filter-select" 
      @change="onSearch"
    >
      <el-option label="全部" value="" />
      <el-option label="成功" value="true" />
      <el-option label="失败" value="false" />
    </el-select>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  filters: { keyword: string, provider: string, task_type: string, success: string }
  providerOptions: string[]
  taskTypeOptions: string[]
}>()

const emit = defineEmits<{
  (e: 'update:filters', val: any): void
  (e: 'search'): void
}>()

const localFilters = computed({
  get: () => props.filters,
  set: (val) => emit('update:filters', val)
})

function onSearch() {
  emit('search')
}
</script>

<style scoped>
.filter-bar { display: flex; gap: 8px; margin-bottom: 12px; flex-wrap: wrap; }
.search-input { width: 220px; }
.filter-select { width: 140px; }
</style>
