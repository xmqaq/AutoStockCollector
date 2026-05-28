<template>
  <div class="data-monitor">
    <!-- Toolbar -->
    <el-card shadow="never" class="toolbar-card">
      <div class="toolbar">
        <el-button type="primary" @click="showCollectModal = true">
          <el-icon><VideoPlay /></el-icon> 启动采集
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

    <el-row :gutter="16">
      <!-- Gauge + Progress -->
      <el-col :span="8">
        <el-card shadow="never" class="section-card">
          <template #header><span>总体进度</span></template>
          <v-chart :option="gaugeOption" style="height:200px" autoresize />
        </el-card>
      </el-col>

      <!-- Summary stats -->
      <el-col :span="16">
        <el-card shadow="never" class="section-card">
          <template #header><span>采集进度明细</span></template>
          <ProgressTable :data="collectStore.progressList" :loading="loading" />
        </el-card>
      </el-col>
    </el-row>

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
            <el-tag size="small">{{ row.task_type }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="statusType(row.status)" size="small">{{ row.status }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="进度" width="120">
          <template #default="{ row }">
            <span>{{ row.success || 0 }}/{{ row.total || 0 }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="create_time" label="创建时间" width="160">
          <template #default="{ row }">{{ fmtDateTime(row.create_time || row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="160">
          <template #default="{ row }">
            <el-button
              v-if="row.status === 'running' || row.status === 'pending'"
              size="small"
              type="warning"
              @click="handleCancel(row.task_id)"
            >取消</el-button>
            <el-button
              v-if="row.status === 'failed' || row.status === 'cancelled'"
              size="small"
              type="primary"
              @click="handleRetry(row.task_id)"
            >重试</el-button>
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

    <!-- Collect modal -->
    <el-dialog v-model="showCollectModal" title="启动历史数据采集" width="480px">
      <el-form :model="collectForm" label-width="100px">
        <el-form-item label="日期范围">
          <el-date-picker
            v-model="collectDateRange"
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
          <el-checkbox-group v-model="collectForm.task_types">
            <el-checkbox
              v-for="t in taskTypeOptions"
              :key="t.value"
              :label="t.label"
              :value="t.value"
            />
          </el-checkbox-group>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCollectModal = false">取消</el-button>
        <el-button type="primary" @click="handleStartCollect" :loading="collectLoading">
          开始采集
        </el-button>
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
import ProgressTable from '@/components/ProgressTable/index.vue'
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
const showCollectModal = ref(false)
const collectLoading = ref(false)
const taskStatusFilter = ref('')
const collectDateRange = ref<[string, string] | null>(null)
const collectForm = ref({
  task_types: [] as string[],
})

const taskTypeOptions = [
  { label: 'K线数据', value: 'kline' },
  { label: '财务数据', value: 'financial' },
  { label: '新闻资讯', value: 'news' },
  { label: '资金流向', value: 'fund_flow' },
  { label: '龙虎榜', value: 'dragon_tiger' },
  { label: '融资融券', value: 'margin' },
  { label: '板块数据', value: 'sector' },
  { label: '股票信息', value: 'stock_info' },
]

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

async function handleStartCollect() {
  if (!collectDateRange.value || !collectDateRange.value[0]) {
    ElMessage.warning('请选择日期范围')
    return
  }
  collectLoading.value = true
  try {
    const params: { start_date: string; end_date: string; task_types?: string[] } = {
      start_date: collectDateRange.value[0],
      end_date: collectDateRange.value[1],
    }
    if (collectForm.value.task_types.length > 0) {
      params.task_types = collectForm.value.task_types
    }
    const res = await collectApi.collectHistory(params)
    if (res.data?.success !== false) {
      ElMessage.success('采集任务已启动')
      showCollectModal.value = false
      collectForm.value.task_types = []
      collectDateRange.value = null
      await loadTasks()
    }
  } finally {
    collectLoading.value = false
  }
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

async function handleRetry(id: string) {
  await collectApi.retryTask(id)
  ElMessage.success('已重新提交任务')
  await loadTasks()
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
