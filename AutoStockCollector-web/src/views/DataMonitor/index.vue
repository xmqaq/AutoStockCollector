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

    <!-- Gauge: data coverage + freshness -->
    <el-card shadow="never" class="section-card">
      <template #header><span>整体采集进度</span></template>
      <div class="gauge-wrapper">
        <v-chart :option="gaugeOption" style="height:200px;flex:1" autoresize />
        <div class="freshness-panel">
          <div class="freshness-title">数据时效性</div>
          <div class="freshness-row">
            <el-tag type="success" size="small">✅ 最新</el-tag>
            <span class="freshness-count">{{ freshnessOk }} 类</span>
          </div>
          <div class="freshness-row">
            <el-tag type="warning" size="small">⚠️ 需更新</el-tag>
            <span class="freshness-count">{{ freshnessStale }} 类</span>
          </div>
          <div class="freshness-row">
            <el-tag type="danger" size="small">❌ 异常</el-tag>
            <span class="freshness-count">{{ freshnessError }} 类</span>
          </div>
          <div class="freshness-hint">{{ coverageText }}</div>
        </div>
      </div>
    </el-card>

    <!-- 定时任务状态 -->
    <el-card shadow="never" class="section-card">
      <template #header>
        <div class="card-header">
          <span>定时任务状态</span>
          <el-tag v-if="cronHasAlert" type="danger" size="small">⚠️ 有任务连续失败</el-tag>
          <el-tag v-else-if="cronJobs.length === 0" type="info" size="small">服务未运行</el-tag>
          <el-tag v-else type="success" size="small">运行中</el-tag>
        </div>
      </template>
      <el-empty v-if="cronJobs.length === 0" description="定时任务未启动（服务启动后自动加载）" :image-size="40" />
      <el-table v-else :data="cronJobs" size="small" stripe>
        <el-table-column prop="label" label="任务名称" min-width="160" />
        <el-table-column prop="next_run" label="下次执行" width="160">
          <template #default="{ row }">{{ row.next_run ?? '--' }}</template>
        </el-table-column>
        <el-table-column prop="last_run" label="最近执行" width="160">
          <template #default="{ row }">{{ row.last_run ?? '尚未执行' }}</template>
        </el-table-column>
        <el-table-column label="状态" width="100" align="center">
          <template #default="{ row }">
            <el-tag v-if="row.last_run == null" type="info" size="small">待首次</el-tag>
            <el-tag v-else-if="row.alert" type="danger" size="small">❌ 连续失败</el-tag>
            <el-tag v-else-if="!row.last_ok" type="warning" size="small">⚠️ 上次失败</el-tag>
            <el-tag v-else type="success" size="small">✅ 正常</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="last_msg" label="最近信息" min-width="180" show-overflow-tooltip />
      </el-table>
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
            <el-tag :type="statusType(row.status)" size="small">{{ statusLabel(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="进度" min-width="200">
          <template #default="{ row }">
            <div class="prog-cell">
              <span class="prog-main">
                已完成 {{ row.progress || 0 }}/{{ row.total || 0 }} 只
                <span v-if="row.total > 0" class="prog-pct">
                  ({{ Math.round((row.progress || 0) / row.total * 100) }}%)
                </span>
              </span>
              <el-progress
                v-if="row.status === 'running' && row.total > 0"
                :percentage="Math.min(100, Math.round((row.progress || 0) / row.total * 100))"
                :stroke-width="4"
                style="margin: 2px 0; width: 160px"
              />
              <span class="prog-sub">
                成功 {{ row.success || 0 }}<template v-if="row.failed"> · <span class="prog-fail">失败 {{ row.failed }}</span></template>
                <template v-if="row.eta_seconds != null && row.status === 'running'">
                  · <span class="prog-eta">剩余约 {{ fmtEta(row.eta_seconds) }}</span>
                </template>
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

    <!-- 数据健康状态总览表 -->
    <el-card shadow="never" class="section-card">
      <template #header>
        <div class="card-header">
          <span>数据覆盖状态</span>
          <el-button size="small" text :loading="gapsLoading" @click="loadDataGaps">
            <el-icon><Refresh /></el-icon> 检测缺口
          </el-button>
        </div>
      </template>
      <el-table
        :data="healthRows"
        size="small"
        stripe
        row-key="value"
      >
        <el-table-column type="expand">
          <template #default="{ row }">
            <div class="gap-detail">
              <!-- 无日期序列类型：直接显示说明，不做缺口检测 -->
              <template v-if="NO_DATE_SEQ.has(row.value)">
                <div class="no-seq-desc">
                  <template v-if="row.value === 'news'">
                    <p>按条存储，共 <strong>{{ row.record_count?.toLocaleString() ?? '--' }}</strong> 条</p>
                    <p class="no-seq-sub">无日期连续性要求，每日增量采集最新新闻</p>
                  </template>
                  <template v-else-if="row.value === 'sector'">
                    <p>快照性质，共 <strong>{{ row.record_count?.toLocaleString() ?? '--' }}</strong> 条</p>
                    <p class="no-seq-sub">最新更新时间：{{ row.latest_date ?? '--' }}</p>
                    <p class="no-seq-sub">每日采集当日板块涨跌数据</p>
                  </template>
                  <template v-else-if="row.value === 'stock_info'">
                    <p>全量覆盖，共 <strong>{{ row.record_count?.toLocaleString() ?? '--' }}</strong> 只股票</p>
                    <p class="no-seq-sub">最后刷新时间：{{ row.latest_date ?? '--' }}</p>
                    <p class="no-seq-sub">每周自动全量刷新一次</p>
                  </template>
                  <template v-else-if="row.value === 'fund_flow'">
                    <p>每日全市场快照数据，共 <strong>{{ row.record_count?.toLocaleString() ?? '--' }}</strong> 条</p>
                    <p class="no-seq-sub">受接口限制，不提供历史数据查询</p>
                    <p class="no-seq-sub">每个交易日收盘后自动更新当日数据</p>
                  </template>
                </div>
              </template>
              <!-- 有日期序列类型：显示缺口检测结果 -->
              <template v-else-if="!gapData[row.value]">
                <span class="gap-hint">点击上方"检测缺口"加载区间详情</span>
              </template>
              <template v-else-if="gapData[row.value].error">
                <span class="gap-error">查询失败：{{ gapData[row.value].error }}</span>
              </template>
              <template v-else-if="row.value === 'financial'">
                <div v-if="gapData[row.value].covered_quarters?.length" class="gap-section">
                  <span class="gap-ok-label">✅ 已有报告期：</span>
                  <span>{{ gapData[row.value].covered_quarters?.slice(-4).join(' / ') }}</span>
                  <span class="gap-pct"> 完整度 {{ gapData[row.value].completeness_pct }}%</span>
                </div>
                <div v-if="gapData[row.value].missing_quarters?.length" class="gap-section gap-missing">
                  <span class="gap-err-label">❌ 缺失季度：</span>
                  <span v-for="q in gapData[row.value].missing_quarters?.slice(0, 8)" :key="q">
                    <el-tag size="small" type="danger" style="margin:2px"
                      @click="() => { const [s,e] = quarterToRange(q); fillGap(row.value, s, e) }">
                      {{ q }} [补采]
                    </el-tag>
                  </span>
                </div>
              </template>
              <template v-else>
                <div class="gap-completeness">
                  完整度 <strong>{{ gapData[row.value].completeness_pct }}%</strong>
                </div>
                <div v-for="seg in gapData[row.value].covered_ranges" :key="seg.start" class="gap-section">
                  <el-tag size="small" type="success">✅ {{ seg.start }} ~ {{ seg.end }}（{{ seg.days }}个交易日）</el-tag>
                </div>
                <div v-for="seg in gapData[row.value].gap_ranges" :key="seg.start" class="gap-section">
                  <el-tag size="small" type="danger">❌ 缺口：{{ seg.start }} ~ {{ seg.end }}（{{ seg.days }}天）</el-tag>
                  <el-button size="small" link type="primary" @click="fillGap(row.value, seg.start, seg.end)">
                    点击补采此区间
                  </el-button>
                </div>
                <div v-if="!gapData[row.value].covered_ranges?.length && !gapData[row.value].gap_ranges?.length">
                  <span class="gap-hint">暂无区间数据</span>
                </div>
              </template>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="label" label="数据类型" width="110" />
        <el-table-column prop="record_count" label="数据库条数" width="110" align="right">
          <template #default="{ row }">{{ row.record_count?.toLocaleString() ?? '--' }}</template>
        </el-table-column>
        <el-table-column label="完整度" width="90" align="center">
          <template #default="{ row }">
            <span v-if="gapData[row.value]?.completeness_pct != null" :class="gapData[row.value].completeness_pct < 90 ? 'stale-days' : ''">
              {{ gapData[row.value].completeness_pct }}%
            </span>
            <span v-else class="gap-hint">--</span>
          </template>
        </el-table-column>
        <el-table-column prop="latest_date" label="最新数据日期" width="120">
          <template #default="{ row }">{{ row.latest_date ?? '--' }}</template>
        </el-table-column>
        <el-table-column prop="days_behind" label="距今" width="80" align="center">
          <template #default="{ row }">
            <span v-if="row.days_behind != null" :class="row.days_behind > 1 ? 'stale-days' : ''">
              {{ row.days_behind === 0 ? '最新' : `${row.days_behind}天前` }}
            </span>
            <span v-else class="stale-days">--</span>
          </template>
        </el-table-column>
        <el-table-column label="健康状态" width="100" align="center">
          <template #default="{ row }">
            <el-tag v-if="row.health === 'ok'" type="success" size="small">✅ 最新</el-tag>
            <el-tag v-else-if="row.health === 'stale'" type="warning" size="small">⚠️ 需更新</el-tag>
            <el-tag v-else type="danger" size="small">❌ 异常</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="180" align="center">
          <template #default="{ row }">
            <el-button size="small" type="primary" plain @click="quickUpdate(row.value)">立即更新</el-button>
            <el-button size="small" type="danger" plain @click="handleClearSingle(row)">清空</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

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

// 无日期序列的数据类型：不做缺口检测，展开时显示说明文字
const NO_DATE_SEQ = new Set(['news', 'fund_flow', 'sector', 'stock_info'])
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

function fmtEta(seconds: number): string {
  if (seconds < 60) return `${seconds}秒`
  if (seconds < 3600) return `${Math.round(seconds / 60)}分钟`
  const h = Math.floor(seconds / 3600)
  const m = Math.round((seconds % 3600) / 60)
  return m > 0 ? `${h}小时${m}分钟` : `${h}小时`
}

// ---------------- 数据健康状态总览 ----------------
const healthRows = computed(() => {
  // progressList 未加载时返回空，避免渲染 0
  if (collectStore.progressList.length === 0) return []
  return COLLECT_TYPES.map(t => {
    const p = collectStore.progressList.find(p => p.task_type === t.value)
    if (!p) return null
    const rc = (p as any).record_count
    return {
      value: t.value,
      label: t.label,
      record_count: typeof rc === 'number' ? rc : null,
      latest_date: (p as any).latest_date ?? (p as any).date_to ?? null,
      days_behind: (p as any).days_behind ?? null,
      health: (p as any).health ?? (rc > 0 ? 'stale' : 'error'),
    }
  }).filter(Boolean)
})

async function quickUpdate(taskType: string) {
  try {
    const res = await collectApi.updateLatest({ task_types: [taskType], force: true })
    const started = res.data?.started || {}
    if (Object.keys(started).length > 0) {
      ElMessage.success(`${TYPE_LABEL[taskType]} 更新任务已启动`)
    } else {
      ElMessage.info(`${TYPE_LABEL[taskType]} 数据已是最新，无需更新`)
    }
    await loadTasks()
  } catch {
    ElMessage.error('启动失败')
  }
}

async function handleClearSingle(row: { value: string; label: string; record_count: number | null }) {
  const count = row.record_count ?? 0
  try {
    await ElMessageBox.confirm(
      `确定要清空【${row.label}】吗？\n将删除数据库中全部 ${count.toLocaleString()} 条数据，此操作不可恢复。`,
      '清空数据确认',
      {
        confirmButtonText: '确认清空',
        cancelButtonText: '取消',
        type: 'error',
        confirmButtonClass: 'el-button--danger',
      }
    )
    await collectApi.clearSingle(row.value)
    ElMessage.success(`${row.label} 已清空，可通过补历史数据重新采集`)
    await collectStore.fetchProgress()
  } catch {
    // user cancelled
  }
}

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
    await collectApi.collectHistory({
      start_date: historyDateRange.value?.[0] ?? '',
      end_date: historyDateRange.value?.[1] ?? '',
      task_types: types,
    })
    ElMessage.success('历史采集任务已启动')
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
    ElMessage.success(skipped.length ? `已启动，${skipped.length} 类已是最新跳过` : '更新任务已启动')
    showUpdateModal.value = false
    await Promise.all([loadTasks(), collectStore.fetchProgress()])
  } finally { updateLoading.value = false }
}

// 重跑：completed/failed/cancelled 均按原参数新建并启动
async function handleRerun(row: any) {
  const res = await collectApi.createTask(row.task_type, row.params || {})
  const id = res.data?.task_id
  if (id) { await collectApi.startTask(id); ElMessage.success('已按原参数重跑'); await Promise.all([loadTasks(), collectStore.fetchProgress()]) }
}

// ---------------- 仪表盘（问题六：覆盖度 + 时效性分开展示）----------------
const overallPercent = computed(() => collectStore.overallPercent)

// 时效性：按 health 字段统计 ok/stale/error 数量
const freshnessOk = computed(() => collectStore.progressList.filter(p => (p as any).health === 'ok').length)
const freshnessStale = computed(() => collectStore.progressList.filter(p => (p as any).health === 'stale').length)
const freshnessError = computed(() => collectStore.progressList.filter(p => (p as any).health === 'error').length)
const coverageText = computed(() => {
  const n = collectStore.progressList.filter(p => ((p as any).record_count || 0) > 0).length
  return `${n}/8 类已有数据`
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
      data: [{ value: overallPercent.value, name: '数据覆盖度' }],
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

// 任务状态英文 → 中文
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

// ---------------- 数据缺口检测（问题五）----------------
const gapData = ref<Record<string, any>>({})
const gapsLoading = ref(false)

async function loadDataGaps() {
  gapsLoading.value = true
  try {
    const res = await collectApi.getDataGaps()
    gapData.value = res.data?.data ?? {}
    ElMessage.success('缺口检测完成')
  } catch {
    ElMessage.error('缺口检测失败')
  } finally {
    gapsLoading.value = false
  }
}

// 将季度末日期转为该季度的完整起止范围
// 例：2025-09-30 → ['2025-07-01', '2025-09-30']
function quarterToRange(q: string): [string, string] {
  const suffix = q.slice(5)  // 'MM-DD'
  const yr = q.slice(0, 4)
  const startMap: Record<string, string> = {
    '03-31': `${yr}-01-01`,
    '06-30': `${yr}-04-01`,
    '09-30': `${yr}-07-01`,
    '12-31': `${yr}-10-01`,
  }
  return [startMap[suffix] ?? q, q]
}

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
    ])
  } finally {
    loading.value = false
  }
}

async function loadTasks() {
  await collectStore.fetchTasks(taskStatusFilter.value || undefined, 50)
}

// 自动轮询：静默更新数据，不触发组件级 loading（不会显示表格遮罩）
async function pollSilently() {
  try {
    await Promise.all([
      collectStore.fetchProgress(),
      collectStore.fetchTasks(taskStatusFilter.value || undefined, 50),
    ])
    // cron 状态每分钟刷新一次（不必每次都查）
    if (Date.now() % 60000 < 15000) loadCronStatus()
  } catch { /* ignore */ }
}

async function handleClearDb() {
  const totalRecords = collectStore.progressList.reduce((acc, p) => acc + ((p as any).record_count || 0), 0)
  const countText = totalRecords > 0 ? `共 ${totalRecords.toLocaleString()} 条数据，` : ''
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

let _pollTimer: ReturnType<typeof setTimeout>

function hasActiveTasks(): boolean {
  return collectStore.tasks.some(t => t.status === 'running' || t.status === 'pending') ||
         collectStore.progressList.some(p => p.status === 'running' || p.status === 'pending')
}

function scheduleNext() {
  const delay = hasActiveTasks() ? 3000 : 15000
  _pollTimer = setTimeout(async () => {
    await pollSilently()
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
.prog-pct { color: #409eff; font-size: 12px; margin-left: 4px; }
.prog-sub { color: #909399; font-size: 11px; }
.prog-fail { color: #f56c6c; }
.prog-eta { color: #e6a23c; }

.table-pagination {
  margin-top: 12px;
  display: flex;
  justify-content: flex-end;
}
.table-pagination :deep(.el-pagination__total),
.table-pagination :deep(.el-pagination__sizes .el-select .el-input__wrapper) {
  color: #909399;
}
.stale-days {
  color: #e6a23c;
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
  color: #909399;
  margin-top: 2px;
  margin-left: 24px;
  line-height: 1.4;
}

/* 数据缺口展开行 */
.gap-detail {
  padding: 12px 16px 12px 40px;
  background: #252525;
  border-top: 1px solid #2c2c2c;
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
  color: #e5eaf3;
  margin-bottom: 8px;
}
.gap-ok-label { color: #67c23a; font-size: 13px; }
.gap-err-label { color: #f56c6c; font-size: 13px; }
.gap-pct { color: #409eff; font-size: 12px; margin-left: 4px; }
.gap-hint { font-size: 12px; color: #606266; font-style: italic; }
.gap-error { font-size: 12px; color: #f56c6c; }
.gap-missing { flex-wrap: wrap; }

/* 无日期序列类型展开说明 */
.no-seq-desc {
  line-height: 1.6;
}
.no-seq-desc p {
  margin: 2px 0;
  font-size: 13px;
  color: #e5eaf3;
}
.no-seq-sub {
  color: #909399 !important;
  font-size: 12px !important;
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
  background: #252525;
  border-radius: 6px;
}
.freshness-title {
  font-size: 13px;
  color: #909399;
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
  color: #e5eaf3;
}
.freshness-hint {
  font-size: 11px;
  color: #606266;
  margin-top: 4px;
}
</style>
