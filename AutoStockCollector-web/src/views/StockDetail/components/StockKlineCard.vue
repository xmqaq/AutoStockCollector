<template>
  <el-card shadow="never" class="section-card kline-card" :class="{ 'is-fullscreen': isFullscreen }" v-loading="klineLoading">
    <template #header>
      <div class="card-header">
        <span class="header-title">K线图与智能标注</span>
        <div class="header-right">
          <div class="date-filter">
            <el-date-picker
              :model-value="klineDateRange"
              type="daterange"
              range-separator="至"
              start-placeholder="开始日期"
              end-placeholder="结束日期"
              format="YYYY年MM月DD日"
              value-format="YYYY-MM-DD"
              size="small"
              style="width:300px"
              :shortcuts="dateShortcuts"
              :clearable="false"
              @update:model-value="$emit('update:klineDateRange', $event)"
              @change="$emit('change-date')"
            />
          </div>
          <el-tooltip :content="isFullscreen ? '退出全屏' : '全屏显示'" placement="top">
            <el-button class="fullscreen-btn" :class="{ 'is-active': isFullscreen }" circle @click="toggleFullscreen">
              <el-icon :size="16"><FullScreen v-if="!isFullscreen" /><Close v-else /></el-icon>
            </el-button>
          </el-tooltip>
        </div>
      </div>
    </template>
    <div class="kline-container">
      <KlineChart 
        v-if="klineData.length > 0" 
        :data="klineData" 
        :annotations="aiAnnotations"
        :support-levels="aiSupportLevels"
        :resistance-levels="aiResistanceLevels"
        chart-height="100%" 
      />
      <el-empty v-else-if="!klineLoading" :description="emptyKlineHint" :image-size="80" />
    </div>
  </el-card>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { FullScreen, Close } from '@element-plus/icons-vue'
import KlineChart from '@/components/KlineChart/index.vue'
import type { KlineRecord, AIAnnotation, PriceLevel } from '@/types'

defineProps<{
  klineLoading: boolean
  klineDateRange: [string, string]
  klineData: KlineRecord[]
  aiAnnotations: AIAnnotation[]
  aiSupportLevels: PriceLevel[]
  aiResistanceLevels: PriceLevel[]
  emptyKlineHint: string
  dateShortcuts: any[]
}>()

defineEmits<{
  (e: 'update:klineDateRange', value: [string, string]): void
  (e: 'change-date'): void
}>()

const isFullscreen = ref(false)

function toggleFullscreen() {
  isFullscreen.value = !isFullscreen.value
  // 图表组件内部已经做了 autoresize，所以在全屏状态改变、CSS 完成重排后，图表会自动响应高度变化
}
</script>

<style scoped>
.kline-card {
  border-radius: 12px;
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  box-shadow: 0 2px 8px var(--bg-hover-subtle);
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 400px; /* Provide a reasonable minimum height */
  height: 100%; /* Ensure it tries to fill the parent */
}

.kline-card :deep(.el-card__body) {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
  padding: 12px 20px;
  height: 100%;
}

.kline-card :deep(.el-card__header) {
  border-bottom: 1px solid var(--border-color);
  padding: 12px 20px;
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.header-title {
  color: var(--text-primary);
  font-size: 15px;
  font-weight: 600;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 16px;
}

.date-filter {
  display: flex;
  align-items: center;
}

.fullscreen-btn {
  color: var(--text-muted);
  background-color: var(--bg-soft);
  border: 1px solid var(--border-color);
  width: 32px;
  height: 32px;
  transition: all 0.2s ease;
}

.fullscreen-btn:hover {
  color: var(--el-color-primary);
  background-color: var(--el-color-primary-light-9);
  border-color: var(--el-color-primary-light-5);
  transform: scale(1.05);
}

.fullscreen-btn.is-active {
  color: var(--el-color-danger);
  background-color: var(--el-color-danger-light-9);
  border-color: var(--el-color-danger-light-5);
}

.fullscreen-btn.is-active:hover {
  background-color: var(--el-color-danger-light-8);
}

/* 全屏样式 */
.is-fullscreen {
  position: fixed !important;
  top: 0;
  left: 0;
  width: 100vw;
  height: 100%;
  z-index: 9999;
  border-radius: 0 !important;
  border: none !important;
}

.kline-container {
  padding: 0;
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  position: relative; /* important for echarts inside */
  height: 100%;
}

.kline-container :deep(.kline-chart-wrapper) {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
}

.kline-container :deep(.vue-echarts) {
  width: 100% !important;
  height: 100% !important;
}
</style>