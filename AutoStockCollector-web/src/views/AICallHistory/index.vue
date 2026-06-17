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
    <AICallStats :stats="stats" :success-rate="successRate" />

    <!-- Provider cards -->
    <AICallProviders :provider-stats="providerStats" />

    <!-- Filter -->
    <AICallFilter 
      v-model:filters="filters" 
      :provider-options="providerOptions" 
      :task-type-options="taskTypeOptions" 
      @search="search" 
    />

    <!-- Table -->
    <AICallTable 
      :records="records" 
      :loading="loading" 
      v-model:page="page" 
      :size="size" 
      :total="total" 
      @page-change="fetchData" 
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { Refresh } from '@element-plus/icons-vue'
import { aiCallHistoryApi, type AICallRecord, type AICallStats as AICallStatsType } from '@/api/aiCallHistory'

import AICallStats from './components/AICallStats.vue'
import AICallProviders from './components/AICallProviders.vue'
import AICallFilter from './components/AICallFilter.vue'
import AICallTable from './components/AICallTable.vue'

const loading = ref(false)
const records = ref<AICallRecord[]>([])
const stats = ref<AICallStatsType>({} as AICallStatsType)
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
</style>
