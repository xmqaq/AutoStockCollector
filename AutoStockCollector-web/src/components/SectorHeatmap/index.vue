<template>
  <div class="sector-heatmap">
    <div class="heatmap-header">
      <span class="heatmap-title">板块轮动</span>
      <el-button size="small" @click="refreshData" :loading="loading">
        <el-icon><Refresh /></el-icon>
      </el-button>
    </div>
    <div class="heatmap-container" ref="chartContainer">
      <div v-if="sectors.length === 0 && !loading" class="empty-hint">
        暂无板块数据
      </div>
      <div v-else class="heatmap-grid">
        <div 
          v-for="(sector, idx) in displayedSectors" 
          :key="idx"
          class="sector-cell"
          :style="getCellStyle(sector.change_rate)"
          @click="handleSectorClick(sector)"
        >
          <div class="sector-name">{{ sector.name }}</div>
          <div class="sector-change">{{ formatChange(sector.change_rate) }}</div>
        </div>
      </div>
    </div>
    <div class="heatmap-legend">
      <span class="legend-label">涨</span>
      <div class="legend-bar">
        <div class="legend-gradient"></div>
      </div>
      <span class="legend-label">跌</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { sectorApi } from '@/api/sector'
import { Refresh } from '@element-plus/icons-vue'
import type { SectorRecord } from '@/types'

const emit = defineEmits<{
  (e: 'select', sector: SectorRecord): void
}>()

const loading = ref(false)
const sectors = ref<SectorRecord[]>([])

const displayedSectors = computed(() => {
  return sectors.value.slice(0, 20)
})

function getCellStyle(changeRate: number): Record<string, string> {
  let bgColor: string
  if (changeRate >= 3) {
    bgColor = 'rgba(208, 90, 81, 0.7)'
  } else if (changeRate >= 1) {
    const alpha = 0.3 + (changeRate / 3) * 0.4
    bgColor = `rgba(208, 90, 81, ${alpha})`
  } else if (changeRate >= 0) {
    const alpha = 0.1 + (changeRate / 3) * 0.2
    bgColor = `rgba(208, 90, 81, ${alpha})`
  } else if (changeRate >= -1) {
    const alpha = 0.1 + Math.abs(changeRate) / 3 * 0.2
    bgColor = `rgba(63, 157, 112, ${alpha})`
  } else if (changeRate >= -3) {
    const alpha = 0.3 + Math.abs(changeRate) / 3 * 0.4
    bgColor = `rgba(63, 157, 112, ${alpha})`
  } else {
    bgColor = 'rgba(63, 157, 112, 0.7)'
  }
  return { backgroundColor: bgColor }
}

function formatChange(changeRate: number): string {
  const sign = changeRate >= 0 ? '+' : ''
  return `${sign}${changeRate.toFixed(2)}%`
}

function handleSectorClick(sector: SectorRecord) {
  emit('select', sector)
}

async function loadSectors() {
  loading.value = true
  try {
    const res = await sectorApi.getSectors()
    const data = res.data?.data || res.data || []
    sectors.value = Array.isArray(data) 
      ? data.sort((a: SectorRecord, b: SectorRecord) => b.change_rate - a.change_rate)
      : []
  } catch {
    sectors.value = []
  } finally {
    loading.value = false
  }
}

function refreshData() {
  loadSectors()
}

onMounted(() => {
  loadSectors()
})
</script>

<style scoped>
.sector-heatmap {
  padding: 16px;
}

.heatmap-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.heatmap-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
}

.heatmap-container {
  min-height: 200px;
}

.empty-hint {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 200px;
  color: var(--text-faint);
  font-size: 13px;
}

.heatmap-grid {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 4px;
}

.sector-cell {
  padding: 8px 4px;
  border-radius: 4px;
  cursor: pointer;
  transition: transform 0.2s, box-shadow 0.2s;
  text-align: center;
}

.sector-cell:hover {
  transform: scale(1.05);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.3);
  z-index: 1;
}

.sector-name {
  font-size: 11px;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  margin-bottom: 2px;
}

.sector-change {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-primary);
}

.heatmap-legend {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  margin-top: 12px;
}

.legend-label {
  font-size: 11px;
  color: var(--text-muted);
}

.legend-bar {
  width: 100px;
  height: 8px;
  border-radius: 4px;
  overflow: hidden;
}

.legend-gradient {
  width: 100%;
  height: 100%;
  background: linear-gradient(to right, var(--dn), var(--border-strong), var(--up));
}
</style>