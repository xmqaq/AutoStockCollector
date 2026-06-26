<template>
  <div class="data-monitor">
    <!-- Sticky Toolbar -->
    <div class="sticky-toolbar">
      <div class="toolbar-left">
        <div class="action-group">
          <el-button type="primary" @click="openUpdateModal" round class="main-action-btn">
            <el-icon><Refresh /></el-icon> 增量更新
          </el-button>
          <el-button @click="showHistoryModal = true" round class="sub-action-btn">
            <el-icon><VideoPlay /></el-icon> 补全历史
          </el-button>
        </div>
        <div class="divider-vertical"></div>
        <div class="refresh-group">
          <el-button @click="refresh" :loading="loading" plain round size="small" class="refresh-btn">
            <el-icon><Refresh /></el-icon> 刷新状态
          </el-button>
          <span class="auto-refresh-tip">
            <span class="pulse-dot"></span> 自动刷新中
          </span>
        </div>
      </div>
      
      <div class="toolbar-right">
        <el-dropdown trigger="click" placement="bottom-end">
          <el-button plain round size="small" class="setting-btn">
            <el-icon><Setting /></el-icon>
          </el-button>
          <template #dropdown>
            <el-dropdown-menu class="custom-dropdown">
              <div class="dropdown-header">高级操作</div>
              <el-dropdown-item @click="handleClearTasks" class="danger-item warning">
                <el-icon><Delete /></el-icon> 清理任务记录
              </el-dropdown-item>
              <el-dropdown-item @click="handleClearDb" class="danger-item critical">
                <el-icon><Delete /></el-icon> 强制清空数据库
              </el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </div>
    </div>

    <!-- 顶部统计看板 -->
    <el-row :gutter="16" class="dashboard-row">
      <el-col :span="6">
        <el-card shadow="hover" class="dashboard-card">
          <div class="stat-title">总数据量</div>
          <div class="stat-value">{{ totalRecords.toLocaleString() }}</div>
          <div class="stat-footer">涵盖 {{ collectStore.progressList.length }} 个数据源</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="dashboard-card">
          <div class="stat-title">时效状态</div>
          <div class="stat-value freshness-stats">
            <span class="text-success">{{ freshnessOk }}</span>
            <span class="divider">/</span>
            <span class="text-warning">{{ freshnessStale }}</span>
            <span class="divider">/</span>
            <span class="text-danger">{{ freshnessError }}</span>
          </div>
          <div class="stat-footer">健康 / 需更新 / 异常</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="dashboard-card">
          <div class="stat-title">活跃任务</div>
          <div class="stat-value text-primary">{{ runningTasksCount }}</div>
          <div class="stat-footer">当前运行中任务数</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="dashboard-card">
          <div class="stat-title">定时调度</div>
          <div class="stat-value" :class="cronHasAlert ? 'text-danger' : 'text-success'">
            {{ cronHasAlert ? '有异常' : (cronJobs.length ? '正常' : '未启动') }}
          </div>
          <div class="stat-footer">共配置 {{ cronJobs.length }} 个定时任务</div>
        </el-card>
      </el-col>
    </el-row>

    <!-- Tabs 分流 -->
    <el-tabs v-model="activeTab" class="monitor-tabs">
      <el-tab-pane label="数据健康监控" name="health">
        <div class="tab-pane-content health-tab-wrapper">
          <!-- 数据完整性体检（含时效性概览） -->
          <el-card shadow="never" class="section-card health-top-card">
            <template #header>
              <div class="card-header">
                <span>数据完整性（{{ coverage?.ref_date || '--' }}）</span>
                <div class="header-chips">
                  <el-tooltip
                    v-if="coverageRefStale"
                    content="今日资金流向（覆盖率基准）尚未采集，基准已回退到上一交易日，下列覆盖率反映的是该日数据"
                    placement="top"
                  >
                    <el-tag type="info" size="small">基准非今日</el-tag>
                  </el-tooltip>
                  <el-tag v-if="freshnessStale > 0" type="warning" size="small">{{ freshnessStale }} 类需更新</el-tag>
                  <el-tag v-if="freshnessError > 0" type="danger" size="small">{{ freshnessError }} 类异常</el-tag>
                  <el-tag v-if="freshnessStale === 0 && freshnessError === 0" type="success" size="small">{{ freshnessOk }} 类时效正常</el-tag>
                  <el-tag v-if="coverage?.overall === 'bad'" type="danger" size="small">有数据缺口</el-tag>
                  <el-tag v-else-if="coverage?.overall === 'warn'" type="warning" size="small">覆盖偏低</el-tag>
                  <el-tag v-else-if="coverage" type="success" size="small">覆盖完整</el-tag>
                  <el-button 
                    link 
                    type="primary" 
                    class="collapse-btn" 
                    @click="isCoverageCollapsed = !isCoverageCollapsed"
                  >
                    <el-icon><component :is="isCoverageCollapsed ? 'ArrowDown' : 'ArrowUp'" /></el-icon>
                    {{ isCoverageCollapsed ? '展开' : '收起' }}
                  </el-button>
                </div>
              </div>
            </template>
            <el-collapse-transition>
              <div v-show="!isCoverageCollapsed">
                <el-empty v-if="!coverage" description="加载中..." :image-size="40" />
                <div v-else class="coverage-grid">
                  <div v-for="row in coverage.sources" :key="row.label" class="coverage-item" :class="`status-${row.status}`">
                    <div class="coverage-item-header">
                      <span class="coverage-label">{{ row.label }}</span>
                      <el-tag v-if="row.status === 'ok'" type="success" size="small" effect="dark">完整</el-tag>
                      <el-tag v-else-if="row.status === 'warn'" type="warning" size="small" effect="dark">偏低</el-tag>
                      <el-tag v-else type="danger" size="small" effect="dark">缺口</el-tag>
                    </div>
                    <div class="coverage-item-body">
                      <el-progress type="dashboard" 
                                  :percentage="row.expected ? Math.round(row.covered / row.expected * 100) : 0"
                                  :status="row.status === 'ok' ? 'success' : row.status === 'warn' ? 'warning' : 'exception'"
                                  :width="60"
                                  :stroke-width="5">
                        <template #default="{ percentage }">
                          <span class="percentage-value">{{ percentage }}%</span>
                        </template>
                      </el-progress>
                      <div class="coverage-stats">
                        <div class="stat-line">已覆盖: <strong>{{ row.covered }}</strong></div>
                        <div class="stat-line">应覆盖: {{ row.expected }}</div>
                        <div v-if="row.missing_count > 0" class="stat-line" :class="row.status === 'ok' ? 'text-muted' : 'text-danger'">
                          缺 {{ row.missing_count }} 只
                          <el-tooltip v-if="row.missing_sample.length" :content="row.missing_sample.join('、')" placement="top">
                            <el-icon class="info-icon"><InfoFilled /></el-icon>
                          </el-tooltip>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
                <div v-if="coverage" class="coverage-hint">
                  以资金流向（{{ coverage.trading_count }} 只在交易）为基准交叉比对；K线缺口由每日 17:30/21:45 自检任务自动回补
                </div>
              </div>
            </el-collapse-transition>
          </el-card>

          <!-- 数据健康状态总览表 -->
          <div class="health-card-wrapper">
            <DataHealthCard
              :coverage-data="coverage"
              @fill-gap="fillGap"
              @refresh="refresh"
            />
          </div>
        </div>
      </el-tab-pane>

      <el-tab-pane label="任务与调度中心" name="tasks">
        <div class="tab-pane-content task-center-wrapper">
          <el-row :gutter="16" class="task-center-row">
            <!-- 左侧：定时任务状态 -->
            <el-col :span="7" class="task-center-col">
              <el-card shadow="never" class="section-card task-center-left-card">
                <template #header>
                  <div class="card-header">
                    <span>定时任务状态</span>
                    <div class="header-tags">
                      <el-select v-model="cronStatusFilter" size="small" style="width: 100px; margin-right: 8px;" placeholder="全部">
                        <el-option label="全部" value="" />
                        <el-option label="正常" value="normal" />
                        <el-option label="有异常" value="error" />
                      </el-select>
                      <el-tag v-if="cronHasAlert" type="danger" size="small" effect="light" round>有任务连续失败</el-tag>
                      <el-tag v-else-if="cronJobs.length === 0" type="info" size="small" effect="light" round>服务未运行</el-tag>
                    </div>
                  </div>
                </template>
                <div class="cron-scroll-content">
                  <el-empty v-if="filteredCronJobs.length === 0" description="没有符合条件的定时任务" :image-size="40" />
                  <div v-else class="cron-cards-vertical">
                    <div v-for="job in filteredCronJobs" :key="job.id" class="cron-job-card" :class="{ 'is-error': job.alert || !job.last_ok }">
                      <div class="job-header">
                        <div class="job-title-wrap">
                          <el-icon class="job-icon"><AlarmClock /></el-icon>
                          <span class="job-title">{{ job.label }}</span>
                        </div>
                        <el-tag v-if="job.last_run == null" type="info" size="small" effect="dark" round>待首次</el-tag>
                        <el-tag v-else-if="job.alert" type="danger" size="small" effect="dark" round>连续失败</el-tag>
                        <el-tag v-else-if="!job.last_ok" type="warning" size="small" effect="dark" round>上次失败</el-tag>
                        <el-tag v-else type="success" size="small" effect="dark" round>正常</el-tag>
                      </div>
                      
                      <div class="job-body">
                        <div class="time-block">
                          <div class="time-label">下次执行</div>
                          <div class="time-value" :class="{ 'text-muted': !job.next_run }">
                            {{ job.next_run ? fmtDateTime(job.next_run) : '--' }}
                          </div>
                        </div>
                        <div class="time-divider"></div>
                        <div class="time-block">
                          <div class="time-label">最近执行</div>
                          <div class="time-value" :class="{ 'text-muted': !job.last_run }">
                            {{ job.last_run ? fmtDateTime(job.last_run) : '尚未执行' }}
                          </div>
                        </div>
                      </div>
                      
                      <div class="job-footer">
                        <div class="job-msg" :class="job.alert || !job.last_ok ? 'text-danger' : 'text-muted'">
                          <el-icon><InfoFilled /></el-icon>
                          <span class="msg-text">{{ job.last_msg || '系统运行正常' }}</span>
                        </div>
                        <div class="job-count">
                          累计: <strong>{{ job.run_count || 0 }}</strong> 次
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              </el-card>
            </el-col>

            <!-- 右侧：任务执行历史 -->
            <el-col :span="17" class="task-center-col">
              <TaskHistoryCard
                v-model:task-status-filter="taskStatusFilter"
                @refresh="refresh"
                class="task-center-right-card"
              />
            </el-col>
          </el-row>
        </div>
      </el-tab-pane>
    </el-tabs>

    <!-- 补历史 dialog -->
    <el-dialog v-model="showHistoryModal" title="补历史数据" width="560px">
      <el-form label-width="90px">
        <el-form-item label="快捷范围">
          <el-radio-group v-model="historyPreset" @change="applyPreset">
            <el-radio-button value="last1y">近一年</el-radio-button>
            <el-radio-button value="ytd">今年以来</el-radio-button>
            <el-radio-button value="2025">2025全年</el-radio-button>
            <el-radio-button value="2024">2024全年</el-radio-button>
            <el-radio-button value="5y">近5年</el-radio-button>
            <el-radio-button value="custom">自定义</el-radio-button>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="日期范围" v-if="!historyTypes.every(t => ['stock_info','sector'].includes(t))">
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
          <div class="history-types-grid">
            <div v-for="t in COLLECT_TYPES" :key="t.value" class="history-type-item">
              <el-checkbox
                :label="t.value"
                v-model:checked="historyTypesSet[t.value]"
                @change="(v: boolean) => toggleHistoryType(t.value, v)"
              >
                {{ t.label }}
              </el-checkbox>
              <div v-if="historyTypesSet[t.value] && t.value === 'stock_info'" class="type-hint">
                将全量刷新所有A股基本信息，约5200条，预计耗时2分钟
              </div>
              <div v-if="historyTypesSet[t.value] && t.value === 'sector'" class="type-hint">
                板块数据为快照性质，无法补历史，将更新为当前最新数据
              </div>
            </div>
          </div>
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
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { ElMessageBox, ElMessage } from 'element-plus'
import { useCollectStore } from '@/stores/collectStore'
import { collectApi, type DataCoverage } from '@/api/collect'
import { fmtDateTime } from '@/utils/format'
import { RANGE_TYPES, COLLECT_TYPES } from '@/utils/collectTypes'
import { VideoPlay, Delete, Refresh, Setting, InfoFilled, AlarmClock, Calendar, Select } from '@element-plus/icons-vue'
import DataHealthCard from './components/DataHealthCard.vue'
import TaskHistoryCard from './components/TaskHistoryCard.vue'

const collectStore = useCollectStore()
const loading = ref(false)

const activeTab = ref('health')
const totalRecords = computed(() => collectStore.progressList.reduce((acc, p) => acc + ((p as any).record_count || 0), 0))
const runningTasksCount = computed(() => collectStore.tasks.filter(t => t.status === 'running').length)

// ── 数据完整性体检（页面打开时加载一次，点击刷新时一并刷新）──
const coverage = ref<DataCoverage | null>(null)
const isCoverageCollapsed = ref(false)

async function loadCoverage() {
  try {
    const res = await collectApi.getDataCoverage()
    coverage.value = res.data?.data || null
  } catch { /* 体检失败不阻塞页面其他功能 */ }
}

// 覆盖率基准日（fund_flow 最近有数据日）是否早于今天：早于则说明今日基准未采集，
// 覆盖率反映的是旧交易日数据，提示用户避免误判“今天数据正常”。
const coverageRefStale = computed(() => {
  const ref = coverage.value?.ref_date
  if (!ref) return false
  const d = new Date()
  const today = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
  return ref < today
})

const taskStatusFilter = ref('')

// ---------------- 补历史 ----------------
const showHistoryModal = ref(false)
const historyLoading = ref(false)
const historyPreset = ref('last1y')
const historyDateRange = ref<[string, string] | null>(null)
const historyTypes = ref<string[]>(RANGE_TYPES.map(t => t.value))
// 用对象追踪每个类型的勾选状态（全部8类）
const historyTypesSet = ref<Record<string, boolean>>(
  Object.fromEntries(COLLECT_TYPES.map(t => [t.value, RANGE_TYPES.some(r => r.value === t.value)]))
)

function toggleHistoryType(val: string, checked: boolean) {
  historyTypesSet.value[val] = checked
  historyTypes.value = COLLECT_TYPES.filter(t => historyTypesSet.value[t.value]).map(t => t.value)
}

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
  } else if (p === '5y') {
    const s = new Date(today); s.setFullYear(s.getFullYear() - 5)
    historyDateRange.value = [fmt(s), fmt(today)]
  }
}
applyPreset('last1y')

async function handleHistory() {
  const types = historyTypes.value
  if (!types.length) { ElMessage.warning('请至少选择一类'); return }
  const needDate = types.some(t => !['stock_info', 'sector'].includes(t))
  if (needDate && !historyDateRange.value?.[0]) { ElMessage.warning('请选择日期范围'); return }
  historyLoading.value = true
  try {
    const res = await collectApi.collectHistory({
      start_date: historyDateRange.value?.[0] ?? '',
      end_date: historyDateRange.value?.[1] ?? '',
      task_types: types,
    })
    const busy = res.data?.skipped_busy || []
    ElMessage.success(busy.length ? `已启动，${busy.length} 类正在采集中已跳过` : '历史采集任务已启动')
    showHistoryModal.value = false
    await Promise.all([loadTasks(), collectStore.fetchProgress()])
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
    const busy = res.data?.skipped_busy || []
    const notes = [
      skipped.length ? `${skipped.length} 类已是最新` : '',
      busy.length ? `${busy.length} 类采集中已跳过` : '',
    ].filter(Boolean).join('，')
    ElMessage.success(notes ? `已启动（${notes}）` : '更新任务已启动')
    showUpdateModal.value = false
    await Promise.all([loadTasks(), collectStore.fetchProgress()])
  } finally { updateLoading.value = false }
}

// 重跑：completed/failed/cancelled 均按原参数新建并启动
// 移除 handleRerun 等，因为已经移到组件内部了

// ---------------- 仪表盘（问题六：覆盖度 + 时效性分开展示）----------------
const overallPercent = computed(() => collectStore.overallPercent)

// 时效性：按 health 字段统计 ok/stale/error 数量
const freshnessOk = computed(() => collectStore.progressList.filter(p => (p as any).health === 'ok').length)
const freshnessStale = computed(() => collectStore.progressList.filter(p => (p as any).health === 'stale').length)
const freshnessError = computed(() => collectStore.progressList.filter(p => (p as any).health === 'error').length)

// ---------------- 数据缺口检测（问题五）----------------
// 将缺口检测移入 DataHealthCard 组件

// 点击"补采此区间"：打开历史弹窗并预填日期
function fillGap(taskType: string, startDate: string, endDate: string) {
  historyTypesSet.value = Object.fromEntries(
    COLLECT_TYPES.map(t => [t.value, t.value === taskType])
  )
  historyTypes.value = [taskType]
  historyDateRange.value = [startDate, endDate]
  historyPreset.value = 'custom'
  showHistoryModal.value = true
}

// ── 定时任务状态 ──────────────────────────────────────────────
const cronJobs = ref<any[]>([])
const cronHasAlert = ref(false)
const cronStatusFilter = ref('')

const filteredCronJobs = computed(() => {
  if (!cronStatusFilter.value) return cronJobs.value
  return cronJobs.value.filter(job => {
    const isError = job.alert || !job.last_ok
    if (cronStatusFilter.value === 'normal') return !isError
    if (cronStatusFilter.value === 'error') return isError
    return true
  })
})

async function loadCronStatus() {
  try {
    const res = await collectApi.getCronStatus()
    cronJobs.value = res.data?.jobs ?? []
    cronHasAlert.value = res.data?.has_alert ?? false
  } catch {
    cronJobs.value = []
  }
}

// manualRefresh：用户点击按钮时显示 loading；自动轮询用 pollSilently 不触发遮罩
async function refresh() {
  loading.value = true
  try {
    await Promise.all([
      collectStore.fetchProgress(),
      loadTasks(),
      loadCronStatus(),
      loadCoverage(),
    ])
  } finally {
    loading.value = false
  }
}

async function loadTasks() {
  await collectStore.fetchTasks(taskStatusFilter.value || undefined, 50)
}

// cron 状态不必每轮都查：累计经过约 60s 才刷新一次
let _cronRefreshAccumMs = 0

// 自动轮询：静默更新数据，不触发组件级 loading（不会显示表格遮罩）
async function pollSilently(elapsedMs = 0) {
  try {
    await Promise.all([
      collectStore.fetchProgress(),
      collectStore.fetchTasks(taskStatusFilter.value || undefined, 50),
    ])
    _cronRefreshAccumMs += elapsedMs
    if (_cronRefreshAccumMs >= 60000) {
      _cronRefreshAccumMs = 0
      loadCronStatus()
    }
  } catch { /* ignore */ }
}

async function handleClearDb() {
  const countText = totalRecords.value > 0 ? `共 ${totalRecords.value.toLocaleString()} 条数据，` : ''
  try {
    await ElMessageBox.confirm(
      `确定要清空全部数据库吗？\n${countText}此操作不可撤销！`,
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

async function handleClearTasks() {
  try {
    await ElMessageBox.confirm(
      '将删除所有已完成/失败/已取消的任务记录（运行中的保留）。\n定时任务执行状态不受影响。',
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

let _pollTimer: ReturnType<typeof setTimeout>

function hasActiveTasks(): boolean {
  return collectStore.tasks.some(t => t.status === 'running' || t.status === 'pending') ||
         collectStore.progressList.some(p => p.status === 'running' || p.status === 'pending')
}

function scheduleNext() {
  const delay = hasActiveTasks() ? 3000 : 15000
  _pollTimer = setTimeout(async () => {
    await pollSilently(delay)
    scheduleNext()
  }, delay)
}

onMounted(() => {
  refresh().then(scheduleNext)
})

onUnmounted(() => {
  clearTimeout(_pollTimer)
})
</script>

<style scoped>
.data-monitor {
  display: flex;
  flex-direction: column;
  gap: 16px;
  position: relative;
  padding-top: 12px;
  height: 100%;
  box-sizing: border-box;
}

/* Dashboard Styles */
.dashboard-row {
  margin-bottom: 8px;
}
.dashboard-card {
  border-radius: 8px;
  border: 1px solid var(--border-color);
  background: var(--bg-card);
  transition: transform 0.2s, box-shadow 0.2s;
}
.dashboard-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05);
}
.dashboard-card :deep(.el-card__body) {
  padding: 16px 20px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.stat-title {
  font-size: 13px;
  color: var(--text-muted);
  font-weight: 500;
}
.stat-value {
  font-size: 24px;
  font-weight: 600;
  color: var(--text-primary);
  line-height: 1.2;
}
.stat-footer {
  font-size: 12px;
  color: var(--text-faint);
  margin-top: 4px;
}
.freshness-stats {
  display: flex;
  align-items: center;
  gap: 6px;
}
.freshness-stats .divider {
  color: var(--border-color);
  font-size: 18px;
  font-weight: 300;
}
.text-success { color: var(--el-color-success); }
.text-warning { color: var(--el-color-warning); }
.text-danger { color: var(--el-color-danger); }
.text-primary { color: var(--el-color-primary); }

/* Tabs Styles */
.monitor-tabs {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
  background: var(--bg-card);
  border-radius: 8px;
  border: 1px solid var(--border-color);
  padding: 0 16px 16px;
}
.monitor-tabs :deep(.el-tabs__header) {
  margin-bottom: 16px;
}
.monitor-tabs :deep(.el-tabs__content) {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
}
.monitor-tabs :deep(.el-tab-pane) {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
}
.tab-pane-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 16px;
  min-height: 0;
}
.health-tab-wrapper {
  overflow: hidden !important;
}
.health-top-card {
  flex-shrink: 0;
  transition: all 0.3s ease;
}
.health-top-card :deep(.el-card__body) {
  padding: 12px 16px;
  transition: all 0.3s ease;
}
.health-card-wrapper {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
}
.health-card-wrapper :deep(.el-card) {
  height: 100%;
  display: flex;
  flex-direction: column;
}
.health-card-wrapper :deep(.el-card__body) {
  flex: 1;
  padding: 0;
  display: flex;
  flex-direction: column;
  min-height: 0;
}
.health-card-wrapper :deep(.el-table) {
  flex: 1;
  height: 0 !important;
}
.task-center-wrapper {
  overflow: hidden !important;
}

/* Collapse Button */
.collapse-btn {
  margin-left: auto;
  font-size: 13px;
  padding: 4px 8px;
}
.collapse-btn .el-icon {
  margin-right: 4px;
}

/* Coverage Grid */
.coverage-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
}
.coverage-item {
  flex: 1 1 calc(20% - 12px); /* 默认每行5个 */
  min-width: 150px; /* 进一步缩小最小宽度限制，确保5个能挤在一排 */
  border: 1px solid var(--border-color);
  border-radius: 8px;
  padding: 12px;
  background: var(--bg-soft);
  transition: transform 0.2s;
}
.coverage-item:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05);
}
.coverage-item-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}
.coverage-label {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
}
.coverage-item-body {
  display: flex;
  align-items: center;
  gap: 12px;
}
.percentage-value {
  font-size: 12px;
  font-weight: bold;
}
.coverage-stats {
  display: flex;
  flex-direction: column;
  gap: 2px;
  font-size: 12px;
}
.stat-line {
  color: var(--text-secondary);
}
.stat-line strong {
  color: var(--text-primary);
}
.text-muted { color: var(--text-muted); }
.text-danger { color: var(--el-color-danger); }
.info-icon {
  margin-left: 4px;
  cursor: pointer;
  color: var(--text-muted);
  vertical-align: middle;
}

.sticky-toolbar {
  position: sticky;
  top: -24px;
  z-index: 100;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 24px;
  margin: -12px 0 0 0;
  background: rgba(var(--bg-card-rgb), 0.85);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  border-bottom: 1px solid var(--border-color-light);
  border-radius: 2px;
  box-shadow: 0 4px 16px -8px rgba(0, 0, 0, 0.08);
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

.toolbar-left {
  display: flex;
  align-items: center;
  gap: 16px;
}

.action-group, .refresh-group {
  display: flex;
  align-items: center;
  gap: 10px;
}

.divider-vertical {
  width: 1px;
  height: 24px;
  background-color: var(--border-color);
  opacity: 0.6;
  margin: 0 4px;
}

.main-action-btn, .sub-action-btn {
  padding: 8px 18px;
  font-weight: 500;
  letter-spacing: 0.5px;
  box-shadow: 0 2px 6px rgba(0, 0, 0, 0.05);
}

.refresh-btn {
  border-color: transparent;
  background-color: var(--bg-soft);
  color: var(--text-secondary);
}
.refresh-btn:hover {
  background-color: var(--el-color-primary-light-9);
  color: var(--el-color-primary);
}

.setting-btn {
  border-color: transparent;
  background-color: transparent;
  font-size: 16px;
  padding: 8px;
  color: var(--text-secondary);
}
.setting-btn:hover {
  background-color: var(--bg-soft);
  color: var(--text-primary);
}

.auto-refresh-tip {
  font-size: 12px;
  color: var(--text-muted);
  display: flex;
  align-items: center;
  gap: 6px;
  user-select: none;
}

.pulse-dot {
  width: 6px;
  height: 6px;
  background-color: var(--el-color-success);
  border-radius: 50%;
  box-shadow: 0 0 0 0 rgba(var(--el-color-success-rgb), 0.7);
  animation: pulse 2s infinite cubic-bezier(0.4, 0, 0.2, 1);
}

@keyframes pulse {
  0% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(103, 194, 58, 0.7); }
  70% { transform: scale(1); box-shadow: 0 0 0 6px rgba(103, 194, 58, 0); }
  100% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(103, 194, 58, 0); }
}

/* Dropdown Menu Customization */
.custom-dropdown {
  padding: 4px 0;
  min-width: 160px;
}
.dropdown-header {
  padding: 8px 16px;
  font-size: 12px;
  font-weight: 600;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  border-bottom: 1px solid var(--border-color-light);
  margin-bottom: 4px;
}
.danger-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 16px;
  font-size: 13px;
  font-weight: 500;
  transition: all 0.2s;
}
.danger-item.warning {
  color: var(--el-color-warning);
}
.danger-item.warning:hover {
  background-color: var(--el-color-warning-light-9);
}
.danger-item.critical {
  color: var(--el-color-danger);
}
.danger-item.critical:hover {
  background-color: var(--el-color-danger-light-9);
}

.coverage-missing { color: var(--el-color-danger); font-size: 12px; }
.coverage-ok-text { color: var(--el-text-color-secondary); font-size: 12px; }
.coverage-hint { margin-top: 8px; font-size: 12px; color: var(--el-text-color-secondary); }

.header-chips {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
  margin-left: 12px;
}

.section-card {
  background: var(--bg-card);
  border: 1px solid var(--border-color);
}

.section-card :deep(.el-card__header) {
  border-bottom: 1px solid var(--border-color);
  padding: 12px 16px;
  color: var(--text-primary);
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
.prog-main { color: var(--text-primary); font-size: 13px; }
.prog-pct { color: var(--el-color-primary); font-size: 12px; margin-left: 4px; }
.prog-sub { color: var(--text-muted); font-size: 11px; }
.prog-fail { color: var(--el-color-danger); }
.prog-eta { color: var(--el-color-warning); }

.table-pagination {
  margin-top: 12px;
  display: flex;
  justify-content: flex-end;
}
.table-pagination :deep(.el-pagination__total),
.table-pagination :deep(.el-pagination__sizes .el-select .el-input__wrapper) {
  color: var(--text-muted);
}
.stale-days {
  color: var(--el-color-warning);
  font-weight: 600;
}
.history-types-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 4px 16px;
}
.history-type-item {
  display: flex;
  flex-direction: column;
  min-width: 110px;
}
.type-hint {
  font-size: 11px;
  color: var(--text-muted);
  margin-top: 2px;
  margin-left: 24px;
  line-height: 1.4;
}

/* 数据缺口展开行 */
.gap-detail {
  padding: 12px 16px 12px 40px;
  background: var(--bg-soft);
  border-top: 1px solid var(--border-color);
}
.gap-section {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 4px 0;
  flex-wrap: wrap;
}
.gap-completeness {
  font-size: 13px;
  color: var(--text-primary);
  margin-bottom: 8px;
}
.gap-ok-label { color: var(--el-color-success); font-size: 13px; }
.gap-err-label { color: var(--el-color-danger); font-size: 13px; }
.gap-pct { color: var(--el-color-primary); font-size: 12px; margin-left: 4px; }
.gap-hint { font-size: 12px; color: var(--text-faint); font-style: italic; }
.gap-error { font-size: 12px; color: var(--el-color-danger); }
.gap-missing { flex-wrap: wrap; }

/* 无日期序列类型展开说明 */
.no-seq-desc {
  line-height: 1.6;
}
.no-seq-desc p {
  margin: 2px 0;
  font-size: 13px;
  color: var(--text-primary);
}
.no-seq-sub {
  color: var(--text-muted) !important;
  font-size: 12px !important;
}

.run-count {
  font-size: 12px;
  color: var(--text-muted);
}
.run-count-zero {
  font-size: 12px;
  color: var(--text-faint);
}

/* 仪表盘布局：左侧仪表 + 右侧时效性面板 */
.gauge-wrapper {
  display: flex;
  align-items: center;
  gap: 24px;
}
.freshness-panel {
  min-width: 160px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 12px 16px;
  background: var(--bg-soft);
  border-radius: 6px;
}
.freshness-title {
  font-size: 13px;
  color: var(--text-muted);
  font-weight: 600;
  margin-bottom: 4px;
}
.freshness-row {
  display: flex;
  align-items: center;
  gap: 8px;
}
.freshness-count {
  font-size: 18px;
  font-weight: bold;
  color: var(--text-primary);
}
.freshness-hint {
  font-size: 11px;
  color: var(--text-faint);
  margin-top: 4px;
}
.cron-table :deep(th.el-table__cell) {
  background-color: var(--bg-soft);
  color: var(--text-secondary);
  font-weight: 500;
}
.font-medium {
  font-weight: 500;
  color: var(--text-primary);
}
.tabular-nums {
  font-variant-numeric: tabular-nums;
}
/* 任务与调度中心新排版 */
.task-center-row {
  flex: 1;
  display: flex;
  align-items: stretch;
  min-height: 0;
  height: 100%;
  flex-wrap: nowrap;
}
.task-center-col {
  display: flex;
  flex-direction: column;
  min-height: 0;
  height: 100%;
}
.task-center-left-card {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
  height: 100%;
}
.task-center-left-card :deep(.el-card__body) {
  flex: 1;
  padding: 0;
  display: flex;
  flex-direction: column;
  min-height: 0;
}
.cron-scroll-content {
  flex: 1;
  padding: 16px;
  background-color: var(--bg-soft);
  box-sizing: border-box;
  overflow-y: auto;
}
.cron-cards-vertical {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.task-center-right-card {
  margin-top: 0 !important;
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
  height: 100%;
}

.cron-job-card {
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: 10px;
  padding: 16px;
  box-shadow: 0 2px 8px var(--bg-hover-subtle);
  transition: all 0.2s ease;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.cron-job-card:hover {
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.08);
  border-color: var(--el-color-primary-light-5);
  transform: translateY(-2px);
}

.cron-job-card.is-error {
  border-color: var(--el-color-danger-light-5);
  background: linear-gradient(to bottom right, var(--bg-card), var(--el-color-danger-light-9));
}

.job-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.job-title-wrap {
  display: flex;
  align-items: center;
  gap: 8px;
}

.job-icon {
  font-size: 18px;
  color: var(--el-color-primary);
}

.job-title {
  font-weight: 600;
  font-size: 15px;
  color: var(--text-primary);
}

.job-body {
  display: flex;
  align-items: center;
  background: var(--bg-soft);
  border-radius: 8px;
  padding: 12px;
}

.time-block {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.time-label {
  font-size: 12px;
  color: var(--text-muted);
}

.time-value {
  font-size: 14px;
  font-weight: 500;
  font-variant-numeric: tabular-nums;
  color: var(--text-regular);
}

.time-divider {
  width: 1px;
  height: 32px;
  background-color: var(--border-color-light);
  margin: 0 16px;
}

.job-footer {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  font-size: 12px;
  border-top: 1px dashed var(--border-color-light);
  padding-top: 12px;
  margin-top: auto;
}

.job-msg {
  display: flex;
  align-items: flex-start;
  gap: 4px;
  flex: 1;
  padding-right: 12px;
}

.job-msg .el-icon {
  margin-top: 2px;
}

.msg-text {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  line-height: 1.4;
}

.job-count {
  color: var(--text-muted);
  white-space: nowrap;
}

.job-count strong {
  color: var(--text-primary);
  font-size: 14px;
}

</style>
