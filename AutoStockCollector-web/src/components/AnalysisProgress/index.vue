<template>
  <div class="analysis-progress">
    <div class="progress-header">
      <div class="header-info">
        <span class="task-name">{{ taskName || '批量分析任务' }}</span>
        <el-tag :type="statusType" size="small">{{ statusLabel }}</el-tag>
      </div>
      <div class="header-actions">
        <el-button v-if="status === 'running'" size="small" @click="pauseTask" :icon="VideoPause">
          暂停
        </el-button>
        <el-button v-if="status === 'paused'" size="small" type="success" @click="resumeTask" :icon="VideoPlay">
          继续
        </el-button>
        <el-button v-if="status === 'running' || status === 'paused'" size="small" type="danger" @click="stopTask" :icon="Close">
          停止
        </el-button>
      </div>
    </div>
    
    <div class="progress-stats">
      <div class="stat-item">
        <span class="stat-value">{{ completedCount }}</span>
        <span class="stat-label">已完成</span>
      </div>
      <div class="stat-item">
        <span class="stat-value">{{ failedCount }}</span>
        <span class="stat-label">失败</span>
      </div>
      <div class="stat-item">
        <span class="stat-value">{{ totalCount }}</span>
        <span class="stat-label">总计</span>
      </div>
      <div class="stat-item">
        <span class="stat-value">{{ elapsedTime }}</span>
        <span class="stat-label">耗时</span>
      </div>
    </div>
    
    <div class="progress-bar-container">
      <el-progress 
        :percentage="progressPercent" 
        :status="progressStatus"
        :stroke-width="12"
      />
      <div class="progress-detail">
        <span>{{ progressPercent.toFixed(1) }}%</span>
        <span class="speed">{{ speed }}</span>
      </div>
    </div>
    
    <div class="current-item" v-if="currentItem">
      <el-icon class="is-loading" color="#409eff"><Loading /></el-icon>
      <span>正在分析: {{ currentItem }}</span>
    </div>
    
    <div class="failed-list" v-if="failedItems.length > 0">
      <div class="failed-header">
        <span>失败项目 ({{ failedItems.length }})</span>
        <el-button size="small" text @click="retryFailed">重试</el-button>
      </div>
      <div class="failed-items">
        <el-tag v-for="(item, idx) in failedItems.slice(0, 5)" :key="idx" size="small" type="danger">
          {{ item }}
        </el-tag>
        <span v-if="failedItems.length > 5" class="more-count">+{{ failedItems.length - 5 }} 更多</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { Loading, VideoPause, VideoPlay, Close } from '@element-plus/icons-vue'

interface Props {
  taskId: string
  taskName?: string
  autoStart?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  autoStart: true,
})

const emit = defineEmits<{
  (e: 'progress', data: BatchProgress): void
  (e: 'complete', results: BatchResult[]): void
  (e: 'error', msg: string): void
}>()

interface BatchProgress {
  task_id: string
  status: 'pending' | 'running' | 'paused' | 'completed' | 'failed'
  total: number
  completed: number
  failed: number
  current?: string
  elapsed_time?: number
}

interface BatchResult {
  code: string
  success: boolean
  data?: Record<string, unknown>
  error?: string
}

const status = ref<BatchProgress['status']>('pending')
const totalCount = ref(0)
const completedCount = ref(0)
const failedCount = ref(0)
const currentItem = ref('')
const failedItems = ref<string[]>([])
const startTime = ref<number>(0)
const elapsedTime = ref('00:00')
const results = ref<BatchResult[]>([])
let pollTimer: ReturnType<typeof setInterval> | null = null

const statusLabel = computed(() => {
  switch (status.value) {
    case 'pending': return '等待中'
    case 'running': return '分析中'
    case 'paused': return '已暂停'
    case 'completed': return '已完成'
    case 'failed': return '失败'
    default: return '未知'
  }
})

const statusType = computed(() => {
  switch (status.value) {
    case 'completed': return 'success'
    case 'failed': return 'danger'
    case 'paused': return 'warning'
    case 'running': return ''
    default: return 'info'
  }
})

const progressPercent = computed(() => {
  if (totalCount.value === 0) return 0
  return (completedCount.value / totalCount.value) * 100
})

const progressStatus = computed(() => {
  if (failedCount.value > 0 && status.value === 'completed') return 'warning'
  if (status.value === 'completed') return 'success'
  if (status.value === 'failed') return 'exception'
  return ''
})

const speed = computed(() => {
  if (elapsedTime.value === '00:00' || completedCount.value === 0) return ''
  const elapsed = (Date.now() - startTime.value) / 1000
  if (elapsed === 0) return ''
  const spd = completedCount.value / elapsed
  return `速度: ${spd.toFixed(2)}/秒`
})

function updateProgress(data: BatchProgress) {
  status.value = data.status
  totalCount.value = data.total
  completedCount.value = data.completed
  failedCount.value = data.failed
  currentItem.value = data.current || ''
  
  if (data.elapsed_time) {
    elapsedTime.value = formatDuration(data.elapsed_time)
  }
  
  if (data.status === 'completed' || data.status === 'failed') {
    stopPolling()
    emit('complete', results.value)
  }
}

function formatDuration(seconds: number): string {
  const mins = Math.floor(seconds / 60)
  const secs = seconds % 60
  return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`
}

function startPolling() {
  pollTimer = setInterval(() => {
    updateElapsedTime()
  }, 1000)
}

function stopPolling() {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

function updateElapsedTime() {
  if (startTime.value === 0) return
  const elapsed = Math.floor((Date.now() - startTime.value) / 1000)
  elapsedTime.value = formatDuration(elapsed)
}

function pauseTask() {
  status.value = 'paused'
  emit('progress', {
    task_id: props.taskId,
    status: 'paused',
    total: totalCount.value,
    completed: completedCount.value,
    failed: failedCount.value,
  })
}

function resumeTask() {
  status.value = 'running'
  emit('progress', {
    task_id: props.taskId,
    status: 'running',
    total: totalCount.value,
    completed: completedCount.value,
    failed: failedCount.value,
  })
}

function stopTask() {
  status.value = 'failed'
  stopPolling()
}

function retryFailed() {
  emit('progress', {
    task_id: props.taskId,
    status: 'running',
    total: failedItems.value.length,
    completed: 0,
    failed: 0,
  })
}

onMounted(() => {
  if (props.autoStart) {
    startTime.value = Date.now()
    startPolling()
  }
})

onUnmounted(() => {
  stopPolling()
})
</script>

<style scoped>
.analysis-progress {
  background: var(--border-color);
  border-radius: 8px;
  padding: 16px;
}

.progress-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.header-info {
  display: flex;
  align-items: center;
  gap: 12px;
}

.task-name {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
}

.header-actions {
  display: flex;
  gap: 8px;
}

.progress-stats {
  display: flex;
  gap: 24px;
  margin-bottom: 16px;
}

.stat-item {
  display: flex;
  flex-direction: column;
  align-items: center;
}

.stat-value {
  font-size: 20px;
  font-weight: 600;
  color: var(--text-primary);
}

.stat-label {
  font-size: 11px;
  color: var(--text-muted);
  margin-top: 2px;
}

.progress-bar-container {
  margin-bottom: 12px;
}

.progress-detail {
  display: flex;
  justify-content: space-between;
  font-size: 12px;
  color: var(--text-muted);
  margin-top: 4px;
}

.speed {
  color: #409eff;
}

.current-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  background: var(--border-strong);
  border-radius: 4px;
  font-size: 12px;
  color: var(--text-muted);
  margin-bottom: 12px;
}

.failed-list {
  background: rgba(245, 108, 108, 0.1);
  border-radius: 4px;
  padding: 12px;
}

.failed-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
  font-size: 12px;
  color: #f56c6c;
}

.failed-items {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.more-count {
  font-size: 11px;
  color: var(--text-muted);
  align-self: center;
}
</style>