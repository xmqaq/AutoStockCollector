<template>
  <el-card shadow="never" class="pro-card stat-card">
    <template #header>
      <span class="card-title">持仓分布</span>
    </template>
    <div v-if="sortedPositions.length > 0" class="distribution-chart">
      <div v-for="p in sortedPositions" :key="p.code" class="distribution-item">
        <div class="dist-info">
          <span class="dist-label">{{ p.code }} <span class="text-muted">{{ p.name }}</span></span>
          <span class="dist-percent number-font">{{ p.position_ratio.toFixed(1) }}%</span>
        </div>
        <div class="dist-bar-container">
          <div class="dist-bar" :style="{ width: p.position_ratio + '%' }" />
        </div>
      </div>
    </div>
    <el-empty v-else description="暂无持仓" :image-size="60" />
  </el-card>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { PaperPosition } from '@/api/paper'

const props = defineProps<{
  positions: PaperPosition[]
}>()

// 按持仓占比从高到低排序
const sortedPositions = computed(() => {
  return [...props.positions].sort((a, b) => b.position_ratio - a.position_ratio)
})
</script>

<style scoped>
.pro-card {
  background: var(--bg-card, #ffffff);
  border: 1px solid var(--border-color, var(--border-color));
  border-radius: 8px;
  box-shadow: 0 2px 12px var(--bg-hover-subtle);
  display: flex;
  flex-direction: column;
  max-height: 440px;
}

.pro-card :deep(.el-card__header) {
  border-bottom: 1px solid var(--border-color, #ebeef5);
  padding: 16px 20px;
  background-color: var(--bg-hover-subtle);
}

.pro-card :deep(.el-card__body) {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  padding-bottom: 8px;
}

.card-title {
  color: var(--text-primary);
  font-size: 15px;
  font-weight: 600;
  display: flex;
  align-items: center;
}

.card-title::before {
  content: '';
  display: inline-block;
  width: 4px;
  height: 16px;
  background: var(--el-color-primary);
  border-radius: 2px;
  margin-right: 8px;
}

.stat-card { height: 100%; }

.distribution-chart { 
  display: flex; 
  flex-direction: column; 
  gap: 16px; 
  padding: 8px 4px 8px 0;
  max-height: 380px; /* 适当增加高度以容纳更多项，超出则滚动 */
  overflow-y: auto;
}

/* 自定义滚动条 */
.distribution-chart::-webkit-scrollbar {
  width: 6px;
}
.distribution-chart::-webkit-scrollbar-thumb {
  background: rgba(144, 147, 153, 0.3);
  border-radius: 3px;
}

.distribution-item { 
  display: flex; 
  flex-direction: column; 
  gap: 6px; 
}

.dist-info { 
  display: flex; 
  justify-content: space-between; 
  font-size: 13px; 
}

.dist-label { 
  font-weight: 600; 
  color: var(--text-primary, var(--text-primary)); 
}

.text-muted {
  font-weight: 400;
  color: var(--text-muted, var(--text-muted));
  margin-left: 4px;
}

.number-font {
  font-family: var(--font-mono, "DIN Alternate", "Helvetica Neue", sans-serif);
}

.dist-percent { 
  color: var(--text-primary, var(--text-primary)); 
  font-weight: 600;
}

.dist-bar-container { 
  height: 8px; 
  background: var(--bg-soft, #f4f4f5); 
  border-radius: 4px; 
  overflow: hidden; 
}

.dist-bar { 
  height: 100%; 
  background: linear-gradient(90deg, #66b1ff, var(--el-color-primary)); 
  border-radius: 4px; 
  transition: width 0.5s ease-out;
}
</style>