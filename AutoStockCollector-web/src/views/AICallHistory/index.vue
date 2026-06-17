<template>
  <div class="ai-call-page">
    <div class="dashboard-header">
      <div class="header-left">
        <h2>AI 调用记录</h2>
        <span class="header-sub">各 AI 供应商的 API 调用历史、成功率与耗时统计</span>
      </div>
      <div class="header-right">
        <el-button size="small" @click="fetchData"><el-icon><Refresh /></el-icon> 刷新</el-button>
      </div>
    </div>

    <!-- Stats -->
    <div class="stats-bar">
      <el-card shadow="never" class="stat-card stat-total">
        <div class="stat-label">调用总数</div>
        <div class="stat-value">{{ stats.total ?? '-' }}</div>
      </el-card>
      <el-card shadow="never" class="stat-card stat-success">
        <div class="stat-label">成功</div>
        <div class="stat-value">{{ stats.success ?? '-' }}</div>
      </el-card>
      <el-card shadow="never" class="stat-card stat-fail">
        <div class="stat-label">失败</div>
        <div class="stat-value">{{ stats.fail ?? '-' }}</div>
      </el-card>
      <el-card shadow="never" class="stat-card">
        <div class="stat-label">今日调用</div>
        <div class="stat-value">{{ stats.today ?? '-' }}</div>
      </el-card>
      <el-card shadow="never" class="stat-card">
        <div class="stat-label">成功率</div>
        <div class="stat-value">{{ successRate }}%</div>
      </el-card>
    </div>

    <!-- Provider cards -->
    <div class="provider-row" v-if="providerStats.length">
      <el-card v-for="p in providerStats" :key="p.name" shadow="never" class="provider-card" :class="'pc-' + colorIdx(p.name)">
        <div class="pc-header">
          <span class="pc-name">{{ p.name }}</span>
          <el-tag size="small" :type="p.fail === 0 ? 'success' : 'danger'" effect="light">{{ p.count }}</el-tag>
        </div>
        <el-progress :percentage="p.rate" :stroke-width="6" :color="p.rate >= 80 ? '#67c23a' : p.rate >= 50 ? '#e6a23c' : '#f56c6c'" />
        <div class="pc-detail">{{ p.success }}/{{ p.count }} 成功</div>
      </el-card>
    </div>

    <!-- Filter -->
    <div class="filter-bar">
      <el-input v-model="filters.keyword" placeholder="搜索供应商/任务类型/错误" clearable size="small" class="search-input" @clear="search" @keyup.enter="search" />
      <el-select v-model="filters.provider" placeholder="供应商" clearable size="small" class="filter-select" @change="search">
        <el-option v-for="p in providerOptions" :key="p" :label="p" :value="p" />
      </el-select>
      <el-select v-model="filters.task_type" placeholder="任务类型" clearable size="small" class="filter-select" @change="search">
        <el-option v-for="t in taskTypeOptions" :key="t" :label="t" :value="t" />
      </el-select>
      <el-select v-model="filters.success" placeholder="状态" clearable size="small" class="filter-select" @change="search">
        <el-option label="全部" value="" />
        <el-option label="成功" value="true" />
        <el-option label="失败" value="false" />
      </el-select>
    </div>

    <!-- Table -->
    <el-card shadow="never" class="table-card">
      <el-table :data="records" v-loading="loading" stripe size="small" max-height="600px">
        <el-table-column prop="timestamp" label="时间" width="170">
          <template #default="{ row }">{{ fmtTime(row.timestamp) }}</template>
        </el-table-column>
        <el-table-column prop="provider" label="供应商" width="110">
          <template #default="{ row }">
            <el-tag :type="providerTagType(row.provider)" size="small" effect="plain">{{ row.provider }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="task_type" label="任务类型" width="140" />
        <el-table-column prop="success" label="状态" width="70" align="center">
          <template #default="{ row }">
            <el-tag :type="row.success ? 'success' : 'danger'" size="small">{{ row.success ? '成功' : '失败' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="error" label="错误信息" min-width="200">
          <template #default="{ row }">
            <span v-if="row.error" class="err-text">{{ row.error }}</span>
            <span v-else class="no-err">--</span>
          </template>
        </el-table-column>
        <el-table-column prop="model_name" label="模型" width="110" />
        <el-table-column prop="input_tokens" label="输入Token" width="100" align="right" />
        <el-table-column prop="output_tokens" label="输出Token" width="100" align="right" />
        <el-table-column label="耗时" width="90" align="right">
          <template #default="{ row }">{{ fmtLatency(row.response_time) }}</template>
        </el-table-column>
      </el-table>

      <div class="pagination-bar">
        <el-pagination
          v-model:current-page="page"
          :page-size="size"
          :total="total"
          layout="total, prev, pager, next"
          background
          small
          @current-change="fetchData"
        />
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { Refresh } from '@element-plus/icons-vue'
import { aiCallHistoryApi, type AICallRecord, type AICallStats } from '@/api/aiCallHistory'

const loading = ref(false)
const records = ref<AICallRecord[]>([])
const stats = ref<AICallStats>({} as AICallStats)
const page = ref(1)
const size = ref(50)
const total = ref(0)

const filters = ref({ keyword: '', provider: '', task_type: '', success: '' })

const providerOptions = ref<string[]>([])
const taskTypeOptions = ref<string[]>([])

const successRate = computed(() => {
  const s = stats.value
  if (!s.total || s.total === 0) return '--'
  return ((s.success / s.total) * 100).toFixed(1)
})

const providerStats = computed(() => {
  const bp = stats.value.by_provider
  const bs = stats.value.success
  const bf = stats.value.fail
  if (!bp) return []
  // estimate per-provider success/fail from total counts
  const totalCalls = stats.value.total || 1
  return Object.entries(bp)
    .map(([name, count]) => ({
      name,
      count,
      // approximate: use global ratio since we don't have per-provider breakdown
      success: Math.round(count * (bs / totalCalls)),
      fail: Math.round(count * (bf / totalCalls)),
      rate: Math.round((count > 0 ? Math.round(count * (bs / totalCalls)) / count : 0) * 100),
    }))
    .sort((a, b) => b.count - a.count)
})

function colorIdx(name: string) {
  const colors = ['blue', 'green', 'orange', 'purple', 'cyan', 'pink']
  let h = 0
  for (const c of name) h = (h * 31 + c.charCodeAt(0)) % colors.length
  return colors[h]
}

function providerTagType(p: string) {
  const map: Record<string, string> = { deepseek: '', minimax: 'warning', agnes: 'info', qwen: 'danger', Qwen3: 'danger' }
  for (const [k, v] of Object.entries(map)) {
    if (p.includes(k)) return v || ''
  }
  return ''
}

function fmtTime(ts: string) {
  if (!ts) return ''
  return ts.replace('T', ' ').slice(0, 19)
}

function fmtLatency(ms?: number) {
  if (ms === undefined || ms === null) return '--'
  if (ms < 1000) return `${ms.toFixed(0)}ms`
  return `${(ms / 1000).toFixed(1)}s`
}

function buildOptions() {
  const bp = stats.value.by_provider
  if (bp) providerOptions.value = Object.keys(bp).sort()
  const bt = stats.value.by_task_type
  if (bt) taskTypeOptions.value = Object.keys(bt).sort()
}

function search() {
  page.value = 1
  fetchData()
}

async function fetchData() {
  loading.value = true
  try {
    const resp = await aiCallHistoryApi.list({
      page: page.value,
      size: size.value,
      provider: filters.value.provider || undefined,
      task_type: filters.value.task_type || undefined,
      success: filters.value.success || undefined,
      keyword: filters.value.keyword || undefined,
    })
    const d = (resp.data as any)
    records.value = d.data || []
    total.value = d.total || 0
    stats.value = d.stats || {}
    buildOptions()
  } catch {
    records.value = []
  } finally {
    loading.value = false
  }
}

onMounted(fetchData)
</script>

<style scoped>
.ai-call-page { padding: 16px; }
.dashboard-header {
  display: flex; justify-content: space-between; align-items: center;
  margin-bottom: 16px;
}
.dashboard-header h2 { margin: 0; font-size: 20px; }
.header-sub { font-size: 12px; color: #999; margin-left: 8px; }
.header-right { display: flex; gap: 8px; align-items: center; }

.stats-bar { display: flex; gap: 10px; margin-bottom: 16px; flex-wrap: wrap; }
.stat-card { flex: 1; min-width: 100px; text-align: center; }
.stat-label { font-size: 12px; color: #999; }
.stat-value { font-size: 22px; font-weight: 700; }
.stat-total .stat-value { color: #409eff; }
.stat-success .stat-value { color: #67c23a; }
.stat-fail .stat-value { color: #f56c6c; }

.provider-row { display: flex; gap: 10px; margin-bottom: 16px; flex-wrap: wrap; }
.provider-card { flex: 1; min-width: 130px; padding: 4px; }
.pc-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px; }
.pc-name { font-weight: 600; font-size: 13px; }
.pc-detail { font-size: 10px; color: #999; margin-top: 2px; }
.pc-blue .pc-name { color: #409eff; }
.pc-green .pc-name { color: #67c23a; }
.pc-orange .pc-name { color: #e6a23c; }
.pc-purple .pc-name { color: #9b59b6; }
.pc-cyan .pc-name { color: #00bcd4; }
.pc-pink .pc-name { color: #e91e63; }

.filter-bar { display: flex; gap: 8px; margin-bottom: 12px; flex-wrap: wrap; }
.search-input { width: 220px; }
.filter-select { width: 140px; }

.table-card { margin-bottom: 16px; }
.err-text { font-size: 11px; color: #f56c6c; word-break: break-all; }
.no-err { color: #ccc; }
.pagination-bar { display: flex; justify-content: flex-end; margin-top: 12px; }
</style>
