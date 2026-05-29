<template>
  <div class="data-monitor">
    <!-- Toolbar -->
    <el-card shadow="never" class="toolbar-card">
      <div class="toolbar">
        <el-button type="primary" @click="showHistoryModal = true">
          <el-icon><VideoPlay /></el-icon> 补历史
        </el-button>
        <el-button type="success" @click="openUpdateModal">
          <el-icon><Refresh /></el-icon> 更新到最新
        </el-button>
        <el-button @click="handleClearTasks">
          <el-icon><Delete /></el-icon> 清空已完成任务
        </el-button>
        <el-button type="danger" @click="handleClearDb">
          <el-icon><Delete /></el-icon> 清空数据库
        </el-button>
        <el-button @click="refresh" :loading="loading">
          <el-icon><Refresh /></el-icon> 刷新
        </el-button>
        <span class="auto-refresh-tip">每3秒自动刷新</span>
      </div>
    </el-card>

    <!-- Gauge: running tasks overall progress -->
    <el-card shadow="never" class="section-card">
      <template #header><span>整体采集进度</span></template>
      <v-chart :option="gaugeOption" style="height:200px" autoresize />
    </el-card>

    <!-- Task history -->
    <el-card shadow="never" class="section-card" style="margin-top:16px">
      <template #header>
        <div class="card-header">
          <span>任务历史</span>
          <el-select v-model="taskStatusFilter" size="small" style="width:120px" @change="loadTasks">
            <el-option label="全部" value="" />
            <el-option label="运行中" value="running" />
            <el-option label="已完成" value="completed" />
            <el-option label="失败" value="failed" />
            <el-option label="取消" value="cancelled" />
          </el-select>
        </div>
      </template>
      <el-empty v-if="collectStore.tasks.length === 0" description="暂无任务记录" />
      <el-table v-else :data="pagedTasks" stripe>
        <el-table-column prop="task_id" label="任务ID" width="200" show-overflow-tooltip />
        <el-table-column prop="task_type" label="类型" width="120">
          <template #default="{ row }">
            <el-tag size="small">{{ typeLabel(row.task_type) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="statusType(row.status)" size="small">{{ row.status }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="进度" min-width="170">
          <template #default="{ row }">
            <div class="prog-cell">
              <span class="prog-main">{{ row.progress || 0 }}/{{ row.total || 0 }}</span>
              <span class="prog-sub">
                成功 {{ row.success || 0 }}<template v-if="row.failed"> · <span class="prog-fail">失败 {{ row.failed }}</span></template>
              </span>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="create_time" label="创建时间" width="160">
          <template #default="{ row }">{{ fmtDateTime(row.create_time || row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="参数" min-width="200">
          <template #default="{ row }">
            <span v-if="row.params?.start_date">{{ row.params.start_date }} ~ {{ row.params.end_date }}</span>
            <span v-else-if="row.params?.mode">{{ row.params.mode }}</span>
            <span v-else>快照</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="200">
          <template #default="{ row }">
            <el-button
              v-if="row.status === 'running' || row.status === 'pending'"
              size="small"
              type="warning"
              @click="handleCancel(row.task_id)"
            >取消</el-button>
            <template v-else>
              <el-button size="small" type="primary" @click="handleRerun(row)">重跑</el-button>
              <el-button size="small" type="danger" plain @click="handleDelete(row.task_id)">删除</el-button>
            </template>
          </template>
        </el-table-column>
      </el-table>
      <el-pagination
        v-if="collectStore.tasks.length > taskPageSize"
        v-model:current-page="currentTaskPage"
        v-model:page-size="taskPageSize"
        :page-sizes="[20, 50, 100, 200]"
        :total="collectStore.tasks.length"
        layout="total, sizes, prev, pager, next"
        background
        class="table-pagination"
      />
    </el-card>

    <!-- 补历史 dialog -->
    <el-dialog v-model="showHistoryModal" title="补历史数据" width="520px">
      <el-form label-width="90px">
        <el-form-item label="快捷范围">
          <el-radio-group v-model="historyPreset" @change="applyPreset">
            <el-radio-button value="last1y">近一年</el-radio-button>
            <el-radio-button value="ytd">今年以来</el-radio-button>
            <el-radio-button value="2025">2025全年</el-radio-button>
            <el-radio-button value="2024">2024全年</el-radio-button>
            <el-radio-button value="custom">自定义</el-radio-button>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="日期范围">
          <el-date-picker
            v-model="historyDateRange"
            type="daterange"
            range-separator="至"
            start-placeholder="开始日期"
            end-placeholder="结束日期"
            format="YYYY年MM月DD日"
            value-format="YYYY-MM-DD"
            style="width:100%"
          />
        </el-form-item>
        <el-form-item label="采集类型">
          <el-checkbox-group v-model="historyTypes">
            <el-checkbox v-for="t in RANGE_TYPES" :key="t.value" :label="t.label" :value="t.value" />
          </el-checkbox-group>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showHistoryModal = false">取消</el-button>
        <el-button type="primary" :loading="historyLoading" @click="handleHistory">开始采集</el-button>
      </template>
    </el-dialog>

    <!-- 更新到最新 dialog -->
    <el-dialog v-model="showUpdateModal" title="更新到最新" width="560px">
      <el-table :data="updateRows" size="small">
        <el-table-column width="50">
          <template #default="{ row }">
            <el-checkbox v-model="row.checked" />
          </template>
        </el-table-column>
        <el-table-column prop="label" label="数据类型" width="120" />
        <el-table-column label="当前覆盖" min-width="180">
          <template #default="{ row }">{{ row.preview }}</template>
        </el-table-column>
      </el-table>
      <template #footer>
        <el-button @click="showUpdateModal = false">取消</el-button>
        <el-button type="success" :loading="updateLoading" @click="handleUpdate">开始更新</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { ElMessageBox, ElMessage } from 'element-plus'
import { useCollectStore } from '@/stores/collectStore'
import { collectApi } from '@/api/collect'
import { fmtDateTime } from '@/utils/format'
import { RANGE_TYPES, COLLECT_TYPES, TYPE_LABEL } from '@/utils/collectTypes'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { GaugeChart } from 'echarts/charts'
import { TooltipComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import { VideoPlay, Delete, Refresh } from '@element-plus/icons-vue'

use([GaugeChart, TooltipComponent, CanvasRenderer])

const collectStore = useCollectStore()
const loading = ref(false)
const currentTaskPage = ref(1)
const taskPageSize = ref(50)
const pagedTasks = computed(() =>
  collectStore.tasks.slice((currentTaskPage.value - 1) * taskPageSize.value, currentTaskPage.value * taskPageSize.value)
)
watch(() => collectStore.tasks, () => { currentTaskPage.value = 1 })
const taskStatusFilter = ref('')

function typeLabel(type: string): string {
  return TYPE_LABEL[type] || type
}

// ---------------- 补历史 ----------------
const showHistoryModal = ref(false)
const historyLoading = ref(false)
const historyPreset = ref('last1y')
const historyDateRange = ref<[string, string] | null>(null)
const historyTypes = ref<string[]>(RANGE_TYPES.map(t => t.value))

function fmt(d: Date) {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}
function applyPreset(p: string) {
  const today = new Date()
  if (p === 'last1y') {
    const s = new Date(today); s.setDate(s.getDate() - 365)
    historyDateRange.value = [fmt(s), fmt(today)]
  } else if (p === 'ytd') {
    historyDateRange.value = [`${today.getFullYear()}-01-01`, fmt(today)]
  } else if (p === '2025') {
    historyDateRange.value = ['2025-01-01', '2025-12-31']
  } else if (p === '2024') {
    historyDateRange.value = ['2024-01-01', '2024-12-31']
  }
}
applyPreset('last1y')

async function handleHistory() {
  if (!historyDateRange.value?.[0]) { ElMessage.warning('请选择日期范围'); return }
  if (!historyTypes.value.length) { ElMessage.warning('请至少选择一类'); return }
  historyLoading.value = true
  try {
    await collectApi.collectHistory({
      start_date: historyDateRange.value[0],
      end_date: historyDateRange.value[1],
      task_types: historyTypes.value,
    })
    ElMessage.success('历史采集任务已启动')
    showHistoryModal.value = false
    await loadTasks()
  } finally { historyLoading.value = false }
}

// ---------------- 更新到最新 ----------------
const showUpdateModal = ref(false)
const updateLoading = ref(false)
const updateRows = ref<{ value: string; label: string; category: string; checked: boolean; preview: string }[]>([])

function openUpdateModal() {
  const statByType: Record<string, any> = {}
  collectStore.progressList.forEach(p => { statByType[p.task_type] = p })
  updateRows.value = COLLECT_TYPES.map(t => {
    const st = statByType[t.value] || {}
    let preview = ''
    if (t.category === 'range') {
      preview = st.date_to ? `已到 ${st.date_to}，将补到今天` : '暂无数据，将补近一年'
    } else if (t.category === 'snapshot') {
      preview = '抓取最新快照'
    } else {
      preview = '增量补充新增股票'
    }
    return { value: t.value, label: t.label, category: t.category, checked: true, preview }
  })
  showUpdateModal.value = true
}

async function handleUpdate() {
  const types = updateRows.value.filter(r => r.checked).map(r => r.value)
  if (!types.length) { ElMessage.warning('请至少选择一类'); return }
  updateLoading.value = true
  try {
    const res = await collectApi.updateLatest({ task_types: types })
    const skipped = res.data?.skipped || []
    ElMessage.success(skipped.length ? `已启动，${skipped.length} 类已是最新跳过` : '更新任务已启动')
    showUpdateModal.value = false
    await loadTasks()
  } finally { updateLoading.value = false }
}

// 重跑：completed/failed/cancelled 均按原参数新建并启动
async function handleRerun(row: any) {
  const res = await collectApi.createTask(row.task_type, row.params || {})
  const id = res.data?.task_id
  if (id) { await collectApi.startTask(id); ElMessage.success('已按原参数重跑'); await loadTasks() }
}

// ---------------- 仪表盘 ----------------
const overallPercent = computed(() => {
  const list = collectStore.progressList
  if (!list.length) return 0
  const withData = list.filter(p => p.total > 0)
  if (!withData.length) return 0
  const totalItems = withData.reduce((a, p) => a + p.total, 0)
  const doneItems = withData.reduce((a, p) => a + (p.progress || p.success || 0), 0)
  if (totalItems === 0) return 0
  return Math.round((doneItems / totalItems) * 100)
})

const gaugeOption = computed(() => ({
  backgroundColor: '#1f1f1f',
  series: [
    {
      type: 'gauge',
      startAngle: 210,
      endAngle: -30,
      min: 0,
      max: 100,
      splitNumber: 5,
      axisLine: {
        lineStyle: {
          width: 12,
          color: [
            [overallPercent.value / 100, '#409eff'],
            [1, '#2c2c2c'],
          ],
        },
      },
      pointer: { show: true, length: '60%', width: 4 },
      axisTick: { show: false },
      splitLine: { show: false },
      axisLabel: { color: '#909399', fontSize: 10 },
      title: {
        color: '#909399',
        fontSize: 12,
        offsetCenter: [0, '70%'],
      },
      detail: {
        formatter: '{value}%',
        color: '#409eff',
        fontSize: 22,
        fontWeight: 'bold',
        offsetCenter: [0, '40%'],
      },
      data: [{ value: overallPercent.value, name: '整体进度' }],
    },
  ],
}))

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

async function refresh() {
  loading.value = true
  try {
    await collectStore.fetchProgress()
    await loadTasks()
  } finally {
    loading.value = false
  }
}

async function loadTasks() {
  await collectStore.fetchTasks(taskStatusFilter.value || undefined, 50)
}

async function handleClearDb() {
  try {
    await ElMessageBox.confirm(
      '确定要清空数据库吗？此操作不可撤销！',
      '危险操作',
      {
        confirmButtonText: '确定清空',
        cancelButtonText: '取消',
        type: 'error',
        confirmButtonClass: 'el-button--danger',
      }
    )
    const res = await collectApi.clearDb()
    if (res.data?.success !== false) {
      ElMessage.success('数据库已清空')
      await collectStore.fetchProgress()
    }
  } catch {
    // User cancelled
  }
}

async function handleCancel(id: string) {
  await collectApi.cancelTask(id)
  ElMessage.success('已取消任务')
  await loadTasks()
}

async function handleDelete(id: string) {
  try {
    await ElMessageBox.confirm('确定删除这条任务记录吗？', '删除任务', {
      confirmButtonText: '删除', cancelButtonText: '取消', type: 'warning',
    })
    await collectApi.deleteTask(id)
    ElMessage.success('已删除')
    await loadTasks()
  } catch {
    // 用户取消
  }
}

async function handleClearTasks() {
  try {
    await ElMessageBox.confirm(
      '将删除所有已完成/失败/已取消的任务记录（运行中的保留）。确定吗？',
      '清空已完成任务',
      { confirmButtonText: '清空', cancelButtonText: '取消', type: 'warning' }
    )
    const res = await collectApi.clearFinishedTasks()
    ElMessage.success(`已清理 ${res.data?.deleted ?? 0} 条`)
    await loadTasks()
  } catch {
    // 用户取消
  }
}

let timer: ReturnType<typeof setInterval>

onMounted(() => {
  refresh()
  timer = setInterval(refresh, 3000)
})

onUnmounted(() => {
  clearInterval(timer)
})
</script>

<style scoped>
.data-monitor {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.toolbar-card {
  background: #1f1f1f;
  border: 1px solid #2c2c2c;
}

.toolbar-card :deep(.el-card__body) {
  padding: 12px 16px;
}

.toolbar {
  display: flex;
  gap: 8px;
  align-items: center;
}

.auto-refresh-tip {
  font-size: 12px;
  color: #606266;
  margin-left: 8px;
}

.section-card {
  background: #1f1f1f;
  border: 1px solid #2c2c2c;
}

.section-card :deep(.el-card__header) {
  border-bottom: 1px solid #2c2c2c;
  padding: 12px 16px;
  color: #e5eaf3;
  font-size: 14px;
  font-weight: 600;
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.prog-cell {
  display: flex;
  flex-direction: column;
  line-height: 1.3;
}
.prog-main { color: #e5eaf3; font-size: 13px; }
.prog-sub { color: #909399; font-size: 11px; }
.prog-fail { color: #f56c6c; }

.table-pagination {
  margin-top: 12px;
  display: flex;
  justify-content: flex-end;
}
.table-pagination :deep(.el-pagination__total),
.table-pagination :deep(.el-pagination__sizes .el-select .el-input__wrapper) {
  color: #909399;
}
</style>
