<template>
  <div class="filter-bar">
    <el-input
      v-model="localSearchText"
      placeholder="搜索代码/名称"
      clearable
      size="small"
      class="search-input"
    />
    <el-select v-model="localSignalFilter" placeholder="信号筛选" size="small" clearable class="filter-select">
      <el-option label="全部" value="" />
      <el-option label="短期买入" value="short_buy" />
      <el-option label="短期卖出" value="short_sell" />
      <el-option label="长期买入" value="long_buy" />
      <el-option label="长期卖出" value="long_sell" />
    </el-select>
    <el-select v-model="localTypeFilter" placeholder="来源" size="small" clearable class="filter-select">
      <el-option label="全部" value="" />
      <el-option label="持仓" value="持仓" />
      <el-option label="自选" value="自选" />
    </el-select>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  searchText: string
  signalFilter: string
  typeFilter: string
}>()

const emit = defineEmits<{
  (e: 'update:searchText', val: string): void
  (e: 'update:signalFilter', val: string): void
  (e: 'update:typeFilter', val: string): void
}>()

const localSearchText = computed({
  get: () => props.searchText,
  set: (val) => emit('update:searchText', val)
})

const localSignalFilter = computed({
  get: () => props.signalFilter,
  set: (val) => emit('update:signalFilter', val)
})

const localTypeFilter = computed({
  get: () => props.typeFilter,
  set: (val) => emit('update:typeFilter', val)
})
</script>

<style scoped>
.filter-bar {
  display: flex;
  gap: 8px;
  align-items: center;
}

.search-input { width: 200px; }
.filter-select { width: 140px; }
</style>
