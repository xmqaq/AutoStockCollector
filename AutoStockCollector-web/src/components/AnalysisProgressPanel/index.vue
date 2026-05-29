<template>
  <div class="analysis-progress-panel">
    <div class="progress-header">
      <div class="progress-title">
        <el-icon class="is-loading" v-if="isRunning"><Loading /></el-icon>
        <el-icon v-else-if="isCompleted"><CircleCheck /></el-icon>
        <el-icon v-else-if="hasError"><Warning /></el-icon>
        <el-icon v-else><Operation /></el-icon>
        <span>{{ title || 'AI分析进度' }}</span>
      </div>
      <div class="progress-stats">
        <el-tag size="small" type="info">{{ completed }}/{{ total }}</el-tag>
        <el-tag v-if="currentStep" size="small" type="warning">{{ currentStep }}</el-tag>
      </div>
    </div>

    <el-progress
      :percentage="percentage"
      :stroke-width="6"
      :status="progressStatus"
      :show-text="true"
      :format="formatProgress"
    />

    <div class="steps-timeline" v-if="steps && steps.length > 0">
      <div
        v-for="(step, index) in (steps || [])"
        :key="index"
        :class="['step-item', step.status, { active: currentStepIndex === index }]"
      >
        <div class="step-indicator">
          <el-icon v-if="step.status === 'completed'"><CircleCheck /></el-icon>
          <el-icon v-else-if="step.status === 'error'"><CircleClose /></el-icon>
          <el-icon v-else-if="step.status === 'running'" class="is-loading"><Loading /></el-icon>
          <span v-else>{{ index + 1 }}</span>
        </div>
        <div class="step-content">
          <div class="step-name">{{ step.name }}</div>
          <div class="step-desc" v-if="step.description">{{ step.description }}</div>
          <div class="step-detail" v-if="step.detail">{{ step.detail }}</div>
        </div>
        <div class="step-time" v-if="step.duration">
          {{ formatDuration(step.duration) }}
        </div>
      </div>
    </div>

    <div class="current-operation" v-if="currentOperation">
      <el-icon class="is-loading"><Loading /></el-icon>
      <span>{{ currentOperation }}</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { Loading, CircleCheck, CircleClose, Warning, Operation } from '@element-plus/icons-vue'

interface AnalysisStep {
  name: string
  description?: string
  detail?: string
  status: 'pending' | 'running' | 'completed' | 'error'
  duration?: number
}

const props = defineProps<{
  title?: string
  steps?: AnalysisStep[]
  currentStep?: string
  currentOperation?: string
  total?: number
  completed?: number
}>()

const isRunning = computed(() => props.steps?.some(s => s.status === 'running'))
const isCompleted = computed(() => props.steps?.every(s => s.status === 'completed' || s.status === 'error'))
const hasError = computed(() => props.steps?.some(s => s.status === 'error'))

const currentStepIndex = computed(() => {
  return props.steps?.findIndex(s => s.status === 'running') ?? -1
})

const percentage = computed(() => {
  if (!props.steps || props.steps.length === 0) {
    if (props.total && props.total > 0) {
      return Math.round((props.completed || 0) / props.total * 100)
    }
    return 0
  }
  const completed = props.steps.filter(s => s.status === 'completed').length
  return Math.round(completed / props.steps.length * 100)
})

const progressStatus = computed(() => {
  if (hasError.value) return 'exception'
  if (isCompleted.value) return 'success'
  return undefined
})

function formatProgress(percentage: number) {
  return `${percentage}%`
}

function formatDuration(ms: number): string {
  if (ms < 1000) return `${ms}ms`
  if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`
  return `${Math.round(ms / 60000)}min`
}
</script>

<style scoped>
.analysis-progress-panel {
  background: #1f1f1f;
  border: 1px solid #2c2c2c;
  border-radius: 8px;
  padding: 16px;
}

.progress-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.progress-title {
  display: flex;
  align-items: center;
  gap: 8px;
  color: #e5eaf3;
  font-size: 14px;
  font-weight: 600;
}

.progress-stats {
  display: flex;
  gap: 8px;
}

.steps-timeline {
  margin-top: 16px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.step-item {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 10px 12px;
  background: #2c2c2c;
  border-radius: 6px;
  transition: all 0.2s;
}

.step-item.active {
  border: 1px solid #409eff;
  background: rgba(64, 158, 255, 0.08);
}

.step-item.completed {
  border-left: 3px solid #67c23a;
}

.step-item.error {
  border-left: 3px solid #f56c6c;
}

.step-item.pending {
  opacity: 0.5;
}

.step-indicator {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  background: #3c3c3c;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  color: #909399;
  flex-shrink: 0;
}

.step-item.completed .step-indicator {
  background: rgba(103, 194, 58, 0.2);
  color: #67c23a;
}

.step-item.running .step-indicator {
  background: rgba(64, 158, 255, 0.2);
  color: #409eff;
}

.step-item.error .step-indicator {
  background: rgba(245, 108, 108, 0.2);
  color: #f56c6c;
}

.step-content {
  flex: 1;
  min-width: 0;
}

.step-name {
  font-size: 13px;
  font-weight: 500;
  color: #e5eaf3;
}

.step-desc {
  font-size: 12px;
  color: #909399;
  margin-top: 2px;
}

.step-detail {
  font-size: 11px;
  color: #606266;
  margin-top: 4px;
  font-family: 'JetBrains Mono', monospace;
}

.step-time {
  font-size: 11px;
  color: #606266;
  flex-shrink: 0;
}

.current-operation {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 12px;
  font-size: 12px;
  color: #909399;
}
</style>