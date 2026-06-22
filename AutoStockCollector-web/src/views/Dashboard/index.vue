<template>
  <div class="dashboard-scrollable">
    <!-- News Ticker -->
    <NewsTicker :news-list="newsList" />

    <!-- Metric cards -->
    <MetricCards :data-loaded="dataLoaded" />

    <!-- Row 1: Account NAV (Left) + Market Sentiment (Right) -->
    <el-row :gutter="16" class="dashboard-row">
      <el-col :span="16">
        <el-card shadow="never" class="section-card fixed-height-card">
          <AccountNavWidget />
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card shadow="never" class="section-card fixed-height-card">
          <MarketSentiment />
        </el-card>
      </el-col>
    </el-row>

    <!-- Row 2: AI Picks (Left) + Sector Heatmap (Right) -->
    <el-row :gutter="16" class="dashboard-row">
      <el-col :span="14">
        <el-card shadow="never" class="section-card tall-card">
          <AIPicksWidget />
        </el-card>
      </el-col>
      <el-col :span="10">
        <el-card shadow="never" class="section-card tall-card">
          <SectorHeatmap @select="handleSectorSelect" />
        </el-card>
      </el-col>
    </el-row>

    <!-- Row 3: Realtime Signals & System Tasks -->
    <el-row :gutter="16" class="dashboard-row signals-row">
      <el-col :span="14">
        <el-card shadow="never" class="section-card">
          <RealtimeSignalsWidget />
        </el-card>
      </el-col>
      <el-col :span="10">
        <el-card shadow="never" class="section-card">
          <SystemTasksWidget />
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useCollectStore } from '@/stores/collectStore'
import { newsApi } from '@/api/news'
import type { NewsRecord, SectorRecord } from '@/types'
import { ElMessage } from 'element-plus'

import MarketSentiment from '@/components/MarketSentiment/index.vue'
import SectorHeatmap from '@/components/SectorHeatmap/index.vue'
import NewsTicker from './components/NewsTicker.vue'
import MetricCards from './components/MetricCards.vue'
import AIPicksWidget from './components/AIPicksWidget.vue'
import AccountNavWidget from './components/AccountNavWidget.vue'
import RealtimeSignalsWidget from './components/RealtimeSignalsWidget.vue'
import SystemTasksWidget from './components/SystemTasksWidget.vue'

const router = useRouter()
const collectStore = useCollectStore()
const loading = ref(false)
const dataLoaded = ref(false)
const newsList = ref<NewsRecord[]>([])
const newsCount = ref(0)

function handleSectorSelect(sector: SectorRecord) {
  ElMessage.info(`跳转至板块: ${sector.name}`)
  router.push({ path: '/sector-flow', query: { name: sector.name } })
}

async function refreshData() {
  loading.value = true
  try {
    await Promise.all([collectStore.fetchProgress(), loadNews()])
  } finally {
    loading.value = false
    dataLoaded.value = true
  }
}

async function loadNews() {
  try {
    const res = await newsApi.getNews({ limit: 10 })
    if (res.data) {
      const data = res.data.data || res.data || []
      newsList.value = Array.isArray(data) ? data : []
      // 使用接口返回的 count 字段（DB 实际总条数），而非当前加载条数
      newsCount.value = res.data.count ?? newsList.value.length
    }
  } catch {
    // ignore
  }
}

let _refreshTimer: ReturnType<typeof setInterval>

onMounted(() => {
  refreshData()
  _refreshTimer = setInterval(refreshData, 30000)  // 每 30s 自动刷新
})

onUnmounted(() => {
  clearInterval(_refreshTimer)
})
</script>

<style scoped>
.dashboard-scrollable {
  display: flex;
  flex-direction: column;
  gap: 16px;
  width: 98%;
  max-width: 1600px;
  margin: 0 auto;
  min-height: 100%;
  padding-bottom: 24px;
}

.dashboard-row {
  margin-bottom: 0;
}

.section-card {
  height: 100%;
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-sm);
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.fixed-height-card {
  height: 320px;
}

.tall-card {
  height: 420px;
}

.signals-row {
  /* Let it be driven by the natural height of the tasks widget */
  min-height: 200px;
}

.signals-row .el-col {
  display: flex;
}

.signals-row .section-card {
  width: 100%;
  position: relative;
}

.section-card :deep(.el-card__body) {
  flex: 1;
  display: flex;
  flex-direction: column;
  padding: 16px;
  min-height: 0;
  overflow-y: auto;
}

/* Ensure inner scrollbars look clean if they appear */
.section-card :deep(.el-card__body)::-webkit-scrollbar {
  width: 6px;
}
.section-card :deep(.el-card__body)::-webkit-scrollbar-thumb {
  background-color: var(--border-color);
  border-radius: 3px;
}
</style>
