<template>
  <el-card shadow="never" class="section-card">
    <template #header>
      <div class="card-header">
        <div class="header-left">
          <span class="title">任务执行历史</span>
          <el-badge :value="collectStore.tasks.length" type="info" class="task-count-badge" />
        </div>
        <div class="header-right">
          <el-input
            v-model="searchQuery"
            placeholder="搜索任务ID/类型"
            size="small"
            clearable
            class="search-input"
            prefix-icon="Search"
          />
          <el-radio-group v-model="taskStatusFilter" size="small" @change="loadTasks">
            <el-radio-button value="">全部</el-radio-button>
            <el-radio-button value="running">运行中</el-radio-button>
            <el-radio-button value="completed">已完成</el-radio-button>
            <el-radio-button value="failed">异常</el-radio-button>
          </el-radio-group>
        </div>
      </div>
    </template>
    <el-empty v-if="collectStore.tasks.length === 0" description="暂无任务记录" />
    <el-table v-else :data="pagedTasks" stripe border height="100%">
      <el-table-column prop="task_id" label="任务ID" min-width="160" show-overflow-tooltip>
        <template #default="{ row }">
          <span class="font-mono text-muted">{{ row.task_id }}</span>
        </template>
      </el-table-column>
      <el-table-column prop="task_type" label="类型" min-width="120">
        <template #default="{ row }">
          <el-tag size="small" effect="plain">{{ typeLabel(row.task_type) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="进度与状态" min-width="210">
        <template #default="{ row }">
          <div class="prog-cell">
            <div class="prog-header">
              <el-tag
                :type="row.status === 'completed' && (row.success || 0) === 0 ? 'info' : statusType(row.status)"
                size="small"
                effect="light"
                round
                class="status-tag"
              >{{ row.status === 'completed' && (row.success || 0) === 0 ? '无数据' : statusLabel(row.status) }}</el-tag>
              
              <div v-if="row.status === 'running' || row.total > 0" class="prog-numbers">
                <span class="current">{{ row.progress || 0 }}</span>
                <span class="separator">/</span>
                <span class="total">{{ row.total || 0 }}</span>
              </div>
            </div>

            <el-progress
              v-if="row.status === 'running' || row.total > 0"
              :percentage="Math.min(100, Math.round((row.progress || 0) / (row.total || 1) * 100))"
              :stroke-width="8"
              :show-text="false"
              :status="row.status === 'failed' ? 'exception' : (row.status === 'completed' ? 'success' : '')"
              class="slim-progress"
            />
            
            <div class="prog-footer" v-if="row.status === 'running' || row.success > 0 || row.failed > 0">
              <div class="stats-group">
                <span v-if="row.success > 0" class="stat-item success">
                  <span class="dot"></span> 成功 {{ row.success }}
                </span>
                <span v-if="row.failed > 0" class="stat-item danger">
                  <span class="dot"></span> 失败 {{ row.failed }}
                </span>
              </div>
              
              <span v-if="row.eta_seconds != null && row.status === 'running'" class="eta-text">
                <el-icon class="is-loading"><Loading /></el-icon> 约 {{ fmtEta(row.eta_seconds) }}
              </span>
            </div>
          </div>
        </template>
      </el-table-column>
      <el-table-column prop="create_time" label="创建时间" min-width="160">
        <template #default="{ row }">
          <div class="time-cell">
            <el-icon class="text-muted"><Timer /></el-icon>
            <span class="tabular-nums">{{ fmtDateTime(row.create_time || row.created_at) }}</span>
          </div>
        </template>
      </el-table-column>
      <el-table-column label="参数" min-width="200">
        <template #default="{ row }">
          <div class="params-cell">
            <el-tag v-if="row.params?.start_date" size="small" type="info" effect="plain" class="param-tag">
              <el-icon><Calendar /></el-icon> {{ row.params.start_date }} ~ {{ row.params.end_date }}
            </el-tag>
            <el-tag v-else-if="row.params?.mode" size="small" type="info" effect="plain" class="param-tag">
              <el-icon><Setting /></el-icon> {{ row.params.mode }}
            </el-tag>
            <el-tag v-else size="small" type="info" effect="plain" class="param-tag">快照</el-tag>
          </div>
        </template>
      </el-table-column>
      <el-table-column label="操作" min-width="140" align="center">
        <template #default="{ row }">
          <el-button
            v-if="row.status === 'running' || row.status === 'pending'"
            size="small"
            type="warning"
            link
            @click="handleCancel(row.task_id)"
          >
            <el-icon><Close /></el-icon> 取消
          </el-button>
          <template v-else>
            <el-button size="small" type="primary" link @click="handleRerun(row)">
              <el-icon><Refresh /></el-icon> 重跑
            </el-button>
            <el-divider direction="vertical" />
            <el-button size="small" type="danger" link @click="handleDelete(row.task_id)">
              删除
            </el-button>
          </template>
        </template>
      </el-table-column>
    </el-table>
    <el-pagination
      v-if="collectStore.tasks.length > taskPageSize"
      v-model:current-page="currentTaskPage"
      v-model:page-size="taskPageSize"
      :page-sizes="[10, 20, 50, 100]"
      :total="collectStore.tasks.length"
      layout="total, sizes, prev, pager, next"
      background
      class="table-pagination"
    />
  </el-card>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useCollectStore } from '@/stores/collectStore'
import { collectApi } from '@/api/collect'
import { fmtDateTime } from '@/utils/format'
import { TYPE_LABEL } from '@/utils/collectTypes'
import { Timer, Search, SwitchButton, MagicStick, Warning, Checked, Close, Right, Document, Loading, Calendar, Setting, Refresh } from '@element-plus/icons-vue'

const props = defineProps<{
  taskStatusFilter: string
}>()

const emit = defineEmits<{
  (e: 'update:taskStatusFilter', val: string): void
  (e: 'refresh'): void
}>()

const collectStore = useCollectStore()

const taskStatusFilter = computed({
  get: () => props.taskStatusFilter,
  set: (val) => emit('update:taskStatusFilter', val)
})

const currentTaskPage = ref(1)
const taskPageSize = ref(10)
const searchQuery = ref('')

const pagedTasks = computed(() => {
  let list = collectStore.tasks
  if (searchQuery.value) {
    const q = searchQuery.value.toLowerCase()
    list = list.filter(t => 
      t.task_id?.toLowerCase().includes(q) || 
      typeLabel(t.task_type).toLowerCase().includes(q)
    )
  }
  return list.slice((currentTaskPage.value - 1) * taskPageSize.value, currentTaskPage.value * taskPageSize.value)
})

watch(() => collectStore.tasks, () => { currentTaskPage.value = 1 })

async function loadTasks() {
  await collectStore.fetchTasks(taskStatusFilter.value || undefined, 50)
}

function typeLabel(type: string): string {
  return TYPE_LABEL[type] || type
}

function fmtEta(seconds: number): string {
  if (seconds < 60) return `${seconds}秒`
  if (seconds < 3600) return `${Math.round(seconds / 60)}分钟`
  const h = Math.floor(seconds / 3600)
  const m = Math.round((seconds % 3600) / 60)
  return m > 0 ? `${h}小时${m}分钟` : `${h}小时`
}

function statusType(status: string) {
  const map: Record<string, 'success' | 'danger' | 'warning' | 'info' | 'primary'> = {
    completed: 'success',
    failed: 'danger',
    running: 'primary',
    pending: 'info',
    cancelled: 'warning',
  }
  return map[status] || 'info'
}

function statusLabel(status: string): string {
  const map: Record<string, string> = {
    completed: '已完成',
    failed: '失败',
    running: '运行中',
    pending: '等待中',
    cancelled: '已取消',
    not_started: '未开始',
  }
  return map[status] || status || '未知'
}

async function handleCancel(id: string) {
  await collectApi.cancelTask(id)
  ElMessage.success('已取消任务')
  await loadTasks()
  emit('refresh')
}

async function handleDelete(id: string) {
  try {
    await ElMessageBox.confirm('确定删除这条任务记录吗？', '删除任务', {
      confirmButtonText: '删除', cancelButtonText: '取消', type: 'warning',
    })
    await collectApi.deleteTask(id)
    ElMessage.success('已删除')
    await loadTasks()
    emit('refresh')
  } catch {
    // 用户取消
  }
}

async function handleRerun(row: any) {
  const res = await collectApi.createTask(row.task_type, row.params || {})
  const id = res.data?.task_id
  if (id) { 
    await collectApi.startTask(id)
    ElMessage.success('已按原参数重跑')
    await Promise.all([loadTasks(), collectStore.fetchProgress()])
    emit('refresh')
  }
}
</script>

<style scoped>
.section-card {
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: 8px;
  overflow: hidden;
  height: 100%;
  display: flex;
  flex-direction: column;
}

.section-card :deep(.el-card__body) {
  flex: 1;
  display: flex;
  flex-direction: column;
  padding: 0;
  min-height: 0;
}

.section-card :deep(.el-table) {
  flex: 1;
  height: 0 !important;
  border-bottom: 1px solid var(--border-color-light);
}

.section-card :deep(.el-card__header) {
  border-bottom: 1px solid var(--border-color);
  padding: 14px 20px;
  color: var(--text-primary);
  font-size: 15px;
  font-weight: 600;
  background-color: var(--bg-soft);
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.task-count-badge {
  margin-top: 2px;
}
.header-right {
  display: flex;
  align-items: center;
  gap: 16px;
}
.search-input {
  width: 200px;
}

.time-cell {
  display: flex;
  align-items: center;
  gap: 6px;
}

.params-cell {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}
.param-tag {
  border-radius: 4px;
}

.prog-cell {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.prog-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.prog-numbers {
  font-family: monospace;
  font-size: 13px;
}

.prog-numbers .current {
  color: var(--text-primary);
  font-weight: 600;
}

.prog-numbers .separator {
  color: var(--text-muted);
  margin: 0 4px;
}

.prog-numbers .total {
  color: var(--text-secondary);
}

.slim-progress {
  width: 100%;
}

.prog-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 12px;
}

.stats-group {
  display: flex;
  gap: 12px;
}

.stat-item {
  display: flex;
  align-items: center;
  gap: 4px;
}

.stat-item .dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
}

.stat-item.success { color: var(--el-color-success); }
.stat-item.success .dot { background-color: var(--el-color-success); }

.stat-item.danger { color: var(--el-color-danger); }
.stat-item.danger .dot { background-color: var(--el-color-danger); }

.eta-text {
  color: var(--el-color-primary);
  display: flex;
  align-items: center;
  gap: 4px;
}

.eta-text .el-icon {
  font-size: 14px;
}

.table-pagination {
  margin-top: 16px;
  display: flex;
  justify-content: flex-end;
  padding: 0 16px 16px;
}
.table-pagination :deep(.el-pagination__total),
.table-pagination :deep(.el-pagination__sizes .el-select .el-input__wrapper) {
  color: var(--text-muted);
}
.el-table {
  --el-table-header-bg-color: var(--bg-soft);
  --el-table-header-text-color: var(--text-secondary);
}
.el-table :deep(th.el-table__cell) {
  font-weight: 500;
}
</style>
