<template>
  <div class="sector-heatmap">
    <div class="heatmap-header">
      <span class="heatmap-title">板块轮动</span>
      <div class="header-actions">
        <el-button class="refresh-btn" size="small" circle @click="refreshData" :loading="loading">
          <el-icon><Refresh /></el-icon>
        </el-button>
      </div>
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
          <div class="sector-content">
            <div class="sector-name">{{ sector.name }}</div>
            <div class="sector-change num">{{ formatChange(sector.change_rate) }}</div>
          </div>
        </div>
      </div>
    </div>

    <div class="heatmap-legend">
      <span class="legend-label">跌</span>
      <div class="legend-bar">
        <div class="legend-gradient"></div>
      </div>
      <span class="legend-label">涨</span>
    </div>

    <div v-if="loading" class="loading-mask">
      <div class="loading-spinner"></div>
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
  // Using global CSS variables for up/down colors to maintain theme consistency
  const isUp = changeRate >= 0
  const absRate = Math.abs(changeRate)
  
  // Calculate intensity based on change rate (0-5% range)
  const intensity = Math.min(Math.max(absRate / 5, 0.15), 1)
  
  // Use rgba to blend the brand colors
  const color = isUp ? `rgba(239, 68, 68, ${intensity})` : `rgba(16, 185, 129, ${intensity})`
  
  return { 
    backgroundColor: color,
    borderColor: isUp ? `rgba(239, 68, 68, ${intensity + 0.2})` : `rgba(16, 185, 129, ${intensity + 0.2})`
  }
}

function formatChange(changeRate: number): string {
  const sign = changeRate > 0 ? '+' : ''
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
  display: flex;
  flex-direction: column;
  height: 100%;
  position: relative;
}

.heatmap-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
  flex-shrink: 0;
}

.heatmap-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
  position: relative;
  padding-left: 12px;
}

.heatmap-title::before {
  content: '';
  position: absolute;
  left: 0;
  top: 50%;
  transform: translateY(-50%);
  width: 4px;
  height: 16px;
  background: var(--brand-500);
  border-radius: 2px;
}

.refresh-btn {
  background: var(--bg-soft);
  border: 1px solid var(--border-color);
  color: var(--text-secondary);
}

.refresh-btn:hover {
  background: var(--bg-hover);
  color: var(--brand-500);
}

.heatmap-container {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 240px;
}

.empty-hint {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-muted);
  font-size: 14px;
}

.heatmap-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 8px;
  flex: 1;
}

.sector-cell {
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
  display: flex;
  align-items: center;
  justify-content: center;
  border: 1px solid transparent;
  min-height: 60px;
  position: relative;
  overflow: hidden;
}

.sector-cell::after {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: linear-gradient(180deg, rgba(255,255,255,0.1) 0%, rgba(255,255,255,0) 100%);
  opacity: 0;
  transition: opacity 0.2s;
}

.sector-cell:hover {
  transform: scale(1.05);
  box-shadow: 0 8px 16px rgba(0, 0, 0, 0.15);
  z-index: 2;
  border-color: var(--border-color) !important;
}

.sector-cell:hover::after {
  opacity: 1;
}

.sector-content {
  text-align: center;
  padding: 8px;
  z-index: 1;
}

.sector-name {
  font-size: 13px;
  font-weight: 600;
  color: #fff;
  text-shadow: 0 1px 2px rgba(0,0,0,0.4);
  margin-bottom: 4px;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  line-height: 1.2;
}

.sector-change {
  font-size: 14px;
  font-weight: 800;
  color: #fff;
  text-shadow: 0 1px 2px rgba(0,0,0,0.4);
}

.heatmap-legend {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px dashed var(--border-color);
  flex-shrink: 0;
}

.legend-label {
  font-size: 12px;
  font-weight: 500;
  color: var(--text-muted);
}

.legend-bar {
  width: 140px;
  height: 6px;
  border-radius: 3px;
  overflow: hidden;
  box-shadow: inset 0 1px 2px var(--bg-hover);
}

.legend-gradient {
  width: 100%;
  height: 100%;
  background: linear-gradient(to right, rgba(16, 185, 129, 1), rgba(16, 185, 129, 0.2), rgba(239, 68, 68, 0.2), rgba(239, 68, 68, 1));
}

/* Loading */
.loading-mask {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: var(--bg-overlay);
  backdrop-filter: blur(4px);
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--radius-lg);
  z-index: 10;
}

.loading-spinner {
  width: 30px;
  height: 30px;
  border: 3px solid var(--border-color);
  border-top-color: var(--brand-500);
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}
</style>