<template>
  <el-card shadow="never" class="section-card search-card">
    <div class="search-bar">
      <el-select
        :model-value="currentCode"
        placeholder="选择自选股"
        filterable
        size="large"
        style="width:220px"
        @update:model-value="$emit('update:currentCode', $event)"
        @change="$emit('load-stock', $event)"
      >
        <el-option
          v-for="stock in watchlist"
          :key="stock.code"
          :label="`${stock.code} ${stock.name}`"
          :value="stock.code"
        />
      </el-select>
      <span class="divider">|</span>
      <StockSearch :model-value="searchCode" @update:model-value="$emit('update:searchCode', $event)" @search="$emit('load-stock', $event)" />
    </div>
  </el-card>
</template>

<script setup lang="ts">
import StockSearch from '@/components/StockSearch/index.vue'
import type { WatchlistItem } from '@/types'

defineProps<{
  currentCode: string
  searchCode: string
  watchlist: WatchlistItem[]
}>()

defineEmits<{
  (e: 'update:currentCode', value: string): void
  (e: 'update:searchCode', value: string): void
  (e: 'load-stock', value: string): void
}>()
</script>

<style scoped>
.search-card {
  border-radius: 12px;
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.02);
  flex-shrink: 0;
}

.search-bar {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 4px;
}

.divider {
  color: var(--border-heavy);
  font-size: 18px;
}
</style>