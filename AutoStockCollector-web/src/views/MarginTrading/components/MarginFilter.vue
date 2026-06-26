<template>
  <el-card shadow="never" class="section-card filter-card">
    <div class="filter-bar">
      <div class="filter-left">
        <el-date-picker
          :model-value="dateRange"
          type="daterange"
          range-separator="至"
          start-placeholder="开始日期"
          end-placeholder="结束日期"
          format="YYYY年MM月DD日"
          value-format="YYYY-MM-DD"
          size="default"
          style="width:280px"
          @update:model-value="$emit('update:dateRange', $event)"
        />
        <el-button type="primary" @click="$emit('search')">
          <el-icon><Search /></el-icon> 查询
        </el-button>
      </div>
      <div class="filter-right">
        <el-tag type="info" effect="light" round>
          <el-icon><InfoFilled /></el-icon> 融资融券为全市场汇总数据
        </el-tag>
      </div>
    </div>
  </el-card>
</template>

<script setup lang="ts">
import { Search, InfoFilled } from '@element-plus/icons-vue'

defineProps<{
  dateRange: [string, string] | null
}>()

defineEmits<{
  (e: 'update:dateRange', val: [string, string] | null): void
  (e: 'search'): void
}>()
</script>

<style scoped>
.filter-card {
  border-radius: 12px;
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  box-shadow: 0 2px 8px var(--bg-hover-subtle);
  flex-shrink: 0;
}
.filter-card :deep(.el-card__body) {
  padding: 12px 16px;
}
.filter-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 16px;
}
.filter-left {
  display: flex;
  gap: 12px;
  align-items: center;
}
.filter-right {
  display: flex;
  align-items: center;
}
.filter-right .el-tag {
  display: flex;
  align-items: center;
  gap: 4px;
}
</style>