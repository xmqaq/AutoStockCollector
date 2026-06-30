<template>
  <el-card shadow="never" class="ra-head">
    <div class="ra-head-inner">
      <div class="ra-head-left">
        <div class="title-wrapper">
          <div class="title-icon">📊</div>
          <h2>投资研报分析</h2>
        </div>
        <p class="subtitle">基于供应链视角的板块研报聚合与标的筛选引擎</p>
      </div>
      <div class="ra-head-right">
        <el-button type="success" :icon="Star" @click="$emit('load-today')" round class="hover-btn">今日精选</el-button>
        <el-button :icon="Refresh" @click="$emit('load-history')" round class="hover-btn">刷新历史</el-button>
        <el-button 
          :icon="isCollapsed ? ArrowDown : ArrowUp" 
          @click="isCollapsed = !isCollapsed" 
          round 
          class="hover-btn"
        >
          {{ isCollapsed ? '展开' : '收起' }}
        </el-button>
      </div>
    </div>

    <el-collapse-transition>
      <div v-show="!isCollapsed">
        <div class="ra-controls-wrapper">
          <div class="ra-controls">
            <div class="ra-sector-select">
          <span class="label">
            <el-icon class="label-icon"><Filter /></el-icon>
            行业板块
          </span>
          <el-checkbox-group v-model="localSelectedSectors" size="default" class="sector-group">
            <el-checkbox-button v-for="s in presetSectors" :key="s" :value="s" :label="s">
              {{ s }}
            </el-checkbox-button>
          </el-checkbox-group>
        </div>
        <div class="ra-actions">
          <div class="action-item">
            <span class="label">候选数</span>
            <el-input-number v-model="localTopN" :min="5" :max="50" size="default" controls-position="right" class="topn-input" />
          </div>
          <el-button
            type="primary"
            :icon="MagicStick"
            :loading="running"
            :disabled="localSelectedSectors.length === 0"
            @click="$emit('start-analysis')"
            size="large"
            class="start-btn"
          >
            {{ running ? '深度分析中...' : '开始智能分析' }}
          </el-button>
        </div>
      </div>
    </div>
      </div>
    </el-collapse-transition>

    <!-- 进度条 -->
    <div v-if="running" class="ra-progress">
      <div class="progress-header">
        <span class="progress-title">任务执行进度</span>
        <span class="progress-percent">{{ taskProgress }}%</span>
      </div>
      <el-progress
        :percentage="taskProgress"
        :stroke-width="10"
        :show-text="false"
        striped
        striped-flow
        :status="taskStatus === 'failed' ? 'exception' : 'success'"
        class="custom-progress"
      />
      <div class="ra-progress-row">
        <p class="ra-progress-msg">
          <el-icon class="is-loading" v-if="taskStatus === 'processing'"><Loading /></el-icon>
          {{ taskMessage }}
        </p>
        <el-button v-if="taskId && taskStatus === 'processing'" size="small" type="danger" plain round @click="$emit('cancel-analysis')">中断分析</el-button>
      </div>
    </div>
  </el-card>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { MagicStick, Refresh, Filter, Loading, ArrowUp, ArrowDown, Star } from '@element-plus/icons-vue'

const isCollapsed = ref(false)

const props = defineProps<{
  selectedSectors: string[]
  topN: number
  presetSectors: string[]
  running: boolean
  taskId: string
  taskStatus: string
  taskProgress: number
  taskMessage: string
}>()

const emit = defineEmits<{
  (e: 'update:selectedSectors', val: string[]): void
  (e: 'update:topN', val: number): void
  (e: 'load-history'): void
  (e: 'load-today'): void
  (e: 'start-analysis'): void
  (e: 'cancel-analysis'): void
}>()

const localSelectedSectors = computed({
  get: () => props.selectedSectors,
  set: (val) => emit('update:selectedSectors', val)
})

const localTopN = computed({
  get: () => props.topN,
  set: (val) => emit('update:topN', val)
})
</script>

<style scoped>
.ra-head {
  border-radius: 16px;
  border: none;
  box-shadow: 0 4px 16px var(--bg-hover-subtle);
  background: var(--bg-card);
  overflow: hidden;
}
.ra-head :deep(.el-card__body) {
  padding: 24px;
}

.ra-head-inner { 
  display: flex; 
  justify-content: space-between; 
  align-items: flex-start; 
  margin-bottom: 24px;
}

.title-wrapper {
  display: flex;
  align-items: center;
  gap: 12px;
}
.title-icon {
  font-size: 28px;
  background: var(--el-color-primary-light-9);
  width: 48px;
  height: 48px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 12px;
  color: var(--el-color-primary);
}
.ra-head-left h2 { 
  margin: 0; 
  font-size: 22px; 
  font-weight: 600;
  color: var(--el-text-color-primary); 
  letter-spacing: 0.5px;
}
.subtitle { 
  margin: 8px 0 0 60px; 
  font-size: 14px; 
  color: var(--el-text-color-secondary); 
}

.hover-btn {
  transition: all 0.3s;
}
.hover-btn:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
}

.ra-controls-wrapper {
  background: var(--el-fill-color-lighter);
  border-radius: 12px;
  padding: 20px;
  border: 1px solid var(--el-border-color-lighter);
}

.ra-controls { 
  display: flex; 
  flex-direction: column; 
  gap: 20px; 
}

.ra-sector-select { 
  display: flex; 
  align-items: flex-start; 
  gap: 16px; 
}
.label { 
  font-size: 14px; 
  color: var(--el-text-color-regular); 
  white-space: nowrap; 
  font-weight: 600; 
  display: flex;
  align-items: center;
  gap: 6px;
  padding-top: 6px;
}
.label-icon {
  font-size: 16px;
  color: var(--el-color-primary);
}

.sector-group {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}
.sector-group :deep(.el-checkbox-button__inner) {
  border-radius: 8px !important;
  border: 1px solid var(--el-border-color) !important;
  padding: 8px 16px;
  font-size: 13px;
  box-shadow: none !important;
  background: var(--bg-card);
  transition: all 0.2s;
}
.sector-group :deep(.el-checkbox-button.is-checked .el-checkbox-button__inner) {
  background-color: var(--el-color-primary-light-9);
  border-color: var(--el-color-primary) !important;
  color: var(--el-color-primary);
  font-weight: 600;
}
.sector-group :deep(.el-checkbox-button:hover .el-checkbox-button__inner) {
  color: var(--el-color-primary);
  border-color: var(--el-color-primary-light-5) !important;
}

.ra-actions { 
  display: flex; 
  align-items: center; 
  justify-content: flex-end;
  gap: 24px; 
  padding-top: 16px;
  border-top: 1px dashed var(--el-border-color-light);
}

.action-item {
  display: flex;
  align-items: center;
  gap: 12px;
}
.action-item .label {
  padding-top: 0;
}

.topn-input {
  width: 120px;
}

.start-btn {
  padding: 0 32px;
  font-weight: 600;
  letter-spacing: 1px;
  border-radius: 8px;
  box-shadow: 0 4px 12px rgba(var(--el-color-primary-rgb), 0.3);
  transition: all 0.3s;
}
.start-btn:hover:not(:disabled) {
  transform: translateY(-2px);
  box-shadow: 0 6px 16px rgba(var(--el-color-primary-rgb), 0.4);
}

/* 进度条美化 */
.ra-progress { 
  margin-top: 24px; 
  padding: 20px; 
  background: var(--bg-card); 
  border-radius: 12px; 
  border: 1px solid var(--el-border-color-lighter);
  box-shadow: 0 2px 12px var(--bg-hover-subtle);
}
.progress-header {
  display: flex;
  justify-content: space-between;
  margin-bottom: 12px;
  font-size: 14px;
  font-weight: 600;
}
.progress-title {
  color: var(--el-text-color-primary);
}
.progress-percent {
  color: var(--el-color-primary);
}
.custom-progress :deep(.el-progress-bar__outer) {
  border-radius: 6px;
  background-color: var(--el-fill-color-light);
}
.custom-progress :deep(.el-progress-bar__inner) {
  border-radius: 6px;
}
.ra-progress-row { 
  display: flex; 
  align-items: center; 
  justify-content: space-between; 
  margin-top: 12px; 
}
.ra-progress-msg { 
  font-size: 13px; 
  color: var(--el-text-color-secondary); 
  margin: 0; 
  display: flex;
  align-items: center;
  gap: 8px;
}
</style>
