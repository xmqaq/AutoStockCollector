<template>
  <div class="system-tasks-widget" v-loading="loading">
    <div class="widget-header">
      <div class="header-left">
        <h2 class="title"><el-icon><Cpu /></el-icon> 引擎运行动态</h2>
      </div>
      <el-button class="modern-btn" text @click="router.push('/data-monitor')">
        任务中心 →
      </el-button>
    </div>

    <div class="tasks-list">
      <div v-if="tasks.length === 0" class="empty-state">
        <el-empty description="当前无任务运行记录" :image-size="60" />
      </div>
      
      <div 
        v-else 
        v-for="task in tasks.slice(0, 8)" 
        :key="task.id" 
        class="task-item"
      >
        <div class="task-icon-wrap" :class="task.status">
          <el-icon v-if="task.status === 'running'" class="is-loading"><Loading /></el-icon>
          <el-icon v-else-if="task.status === 'completed'"><Select /></el-icon>
          <el-icon v-else-if="task.status === 'failed'"><CloseBold /></el-icon>
          <el-icon v-else><Clock /></el-icon>
        </div>
        
        <div class="task-content">
          <div class="task-top">
            <span class="t-name">{{ getTaskName(task.task_type) }}</span>
            <span class="t-time">{{ formatTime(task.updated_at || task.created_at) }}</span>
          </div>
          
          <div class="task-bottom">
            <span class="t-status" :class="task.status">
              {{ getStatusLabel(task.status) }}
            </span>
            <span v-if="task.duration" class="t-duration">耗时 {{ task.duration.toFixed(1) }}s</span>
            <span v-else-if="task.progress !== undefined" class="t-progress">
              进度 {{ Math.min(100, Math.round(task.progress > 1 ? task.progress : task.progress * 100)) }}%
            </span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { Cpu, Loading, Select, CloseBold, Clock } from '@element-plus/icons-vue'
import client from '@/api/client'
import { TYPE_LABEL } from '@/utils/collectTypes'

const router = useRouter()
const loading = ref(true)
const tasks = ref<any[]>([])
let timer: ReturnType<typeof setInterval>

function getTaskName(type: string) {
  if (type.startsWith('workflow_')) {
    return `执行策略工作流 [${type.replace('workflow_', '')}]`
  }
  return (TYPE_LABEL as any)[type] ? `采集: ${(TYPE_LABEL as any)[type]}` : `任务: ${type}`
}

function getStatusLabel(status: string) {
  const map: Record<string, string> = {
    'running': '运行中...',
    'completed': '执行成功',
    'failed': '执行失败',
    'pending': '排队中'
  }
  return map[status] || status
}

function formatTime(ts: string) {
  if (!ts) return ''
  // Handle python ISO strings
  const date = new Date(ts.replace ? ts.replace(' ', 'T') : ts)
  return `${String(date.getHours()).padStart(2, '0')}:${String(date.getMinutes()).padStart(2, '0')}`
}

async function loadData() {
  try {
    const res = await client.get('/api/v1/tasks', { params: { limit: 20 } })
    const data = res.data?.tasks || []
    
    // Sort so running comes first, then by date descending
    tasks.value = data.sort((a: any, b: any) => {
      if (a.status === 'running' && b.status !== 'running') return -1
      if (a.status !== 'running' && b.status === 'running') return 1
      
      const tsA = a.updated_at || a.created_at || ''
      const tsB = b.updated_at || b.created_at || ''
      
      const timeA = tsA ? new Date(tsA.replace ? tsA.replace(' ', 'T') : tsA).getTime() : 0
      const timeB = tsB ? new Date(tsB.replace ? tsB.replace(' ', 'T') : tsB).getTime() : 0
      
      return timeB - timeA
    })
  } catch (err) {
    console.error('Failed to load tasks', err)
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  loadData()
  timer = setInterval(loadData, 10000) // Refresh every 10s
})

onUnmounted(() => {
  clearInterval(timer)
})
</script>

<style scoped>
.system-tasks-widget {
  display: flex;
  flex-direction: column;
  height: 100%;
}

.widget-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
  flex-shrink: 0;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.title {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
  display: flex;
  align-items: center;
  gap: 6px;
}

.title .el-icon {
  color: var(--brand-500);
}

.modern-btn {
  color: var(--brand-500);
  font-weight: 500;
}

.tasks-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
  /* Remove flex: 1 and min-height to allow natural growth */
}

.tasks-list::-webkit-scrollbar {
  width: 4px;
}
.tasks-list::-webkit-scrollbar-thumb {
  background-color: var(--border-color);
  border-radius: 2px;
}

.task-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px 10px;
  border-radius: 8px;
  background: var(--bg-page);
  border: 1px solid var(--border-light);
  transition: all 0.2s;
}

.task-item:hover {
  border-color: var(--brand-300);
  background: var(--bg-soft);
}

.task-icon-wrap {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  flex-shrink: 0;
}

.task-icon-wrap.running {
  background: var(--brand-50);
  color: var(--brand-500);
}
.task-icon-wrap.completed {
  background: var(--el-color-success-light-9);
  color: var(--el-color-success);
}
.task-icon-wrap.failed {
  background: var(--el-color-danger-light-9);
  color: var(--el-color-danger);
}
.task-icon-wrap.pending {
  background: var(--el-color-info-light-9);
  color: var(--el-color-info);
}

.task-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
}

.task-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.t-name {
  font-size: 13px;
  font-weight: 500;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.t-time {
  font-size: 11px;
  color: var(--text-muted);
  font-family: monospace;
}

.task-bottom {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 11px;
}

.t-status {
  font-weight: 500;
}

.t-status.running { color: var(--brand-500); }
.t-status.completed { color: var(--el-color-success); }
.t-status.failed { color: var(--el-color-danger); }
.t-status.pending { color: var(--el-color-info); }

.t-duration, .t-progress {
  color: var(--text-secondary);
}

.empty-state {
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
}
</style>