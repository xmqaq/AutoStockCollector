<template>
  <div class="dashboard">
    <!-- News Ticker & Collapse -->
    <NewsTicker :news-list="newsList" />

    <!-- Metric cards -->
    <MetricCards :data-loaded="dataLoaded" :news-count="newsCount" />

    <!-- Data health card grid -->
    <DataHealthGrid :data-loaded="dataLoaded" />

    <!-- Main content: Market sentiment + Sector heatmap side by side -->
    <el-row :gutter="16" class="main-content-row" style="align-items: stretch; margin-bottom: 0;">
      <!-- Left column: Market sentiment -->
      <el-col :span="15" style="display: flex; flex-direction: column">
        <el-card shadow="never" class="section-card fill-card">
          <MarketSentiment />
        </el-card>
      </el-col>

      <!-- Right column: Sector heatmap only -->
      <el-col :span="9" style="display: flex; flex-direction: column">
        <el-card shadow="never" class="section-card fill-card">
          <SectorHeatmap @select="handleSectorSelect" />
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
import DataHealthGrid from './components/DataHealthGrid.vue'

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
.dashboard {
  display: flex;
  flex-direction: column;
  gap: 1.5vh;
  width: 98%;
  max-width: 1600px;
  margin: 0 auto;
  height: 100%;
  padding-bottom: 0;
}

.section-card {
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-sm);
  overflow: hidden;
}

.main-content-row {
  flex: 1;
  min-height: 0;
}

.fill-card {
  flex: 1;
  display: flex;
  flex-direction: column;
}

.fill-card :deep(.el-card__body) {
  flex: 1;
  display: flex;
  flex-direction: column;
  padding: 16px;
  min-height: 0;
}
</style>
