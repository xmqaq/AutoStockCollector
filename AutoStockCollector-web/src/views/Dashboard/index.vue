<template>
  <div class="dashboard">
    <!-- Metric cards -->
    <el-row :gutter="16" class="metric-cards">
      <el-col :span="6">
        <el-card class="metric-card" shadow="never">
          <div class="metric-content">
            <div class="metric-label">后端状态</div>
            <div :class="['metric-value', collectStore.backendOnline ? 'text-success' : 'text-danger']">
              {{ collectStore.backendOnline ? '正常运行' : '离线' }}
            </div>
          </div>
          <el-icon class="metric-icon" :color="collectStore.backendOnline ? '#67c23a' : '#f56c6c'" size="36">
            <Monitor />
          </el-icon>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="metric-card" shadow="never">
          <div class="metric-content">
            <div class="metric-label">采集完成度</div>
            <div class="metric-value">
              <span class="text-primary">{{ collectStore.completedCount }}</span>
              <span class="metric-sub"> / 8 类</span>
            </div>
          </div>
          <el-icon class="metric-icon" color="#409eff" size="36">
            <DataAnalysis />
          </el-icon>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="metric-card" shadow="never">
          <div class="metric-content">
            <div class="metric-label">累计成功条数</div>
            <div class="metric-value text-primary">{{ fmtAmount(collectStore.totalSuccessCount) }}</div>
          </div>
          <el-icon class="metric-icon" color="#e6a23c" size="36">
            <TrendCharts />
          </el-icon>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="metric-card" shadow="never">
          <div class="metric-content">
            <div class="metric-label">最新新闻条数</div>
            <div class="metric-value text-primary">{{ newsCount }}</div>
          </div>
          <el-icon class="metric-icon" color="#909399" size="36">
            <ChatDotRound />
          </el-icon>
        </el-card>
      </el-col>
    </el-row>

    <!-- Main content -->
    <el-row :gutter="16" class="main-content-row">
      <!-- Left column: Progress table + Market sentiment -->
      <el-col :span="16">
        <el-card shadow="never" class="section-card">
          <template #header>
            <div class="card-header">
              <span>数据覆盖总览</span>
              <el-button size="small" @click="refreshData" :loading="loading">
                <el-icon><Refresh /></el-icon> 刷新
              </el-button>
            </div>
          </template>
          <ProgressTable :data="collectStore.progressList" :loading="loading" show-freshness />
        </el-card>
        <el-card shadow="never" class="section-card sentiment-card">
          <MarketSentiment />
        </el-card>
      </el-col>

      <!-- Right column: Sector heatmap + News list -->
      <el-col :span="8">
        <el-card shadow="never" class="section-card">
          <SectorHeatmap @select="handleSectorSelect" />
        </el-card>
        <el-card shadow="never" class="section-card">
          <template #header>
            <span>最新资讯</span>
          </template>
          <div v-if="newsList.length === 0" class="empty-state">
            <el-empty description="暂无新闻" :image-size="60" />
          </div>
          <div v-else class="news-list">
            <div
              v-for="(news, idx) in newsList"
              :key="idx"
              class="news-item"
              @click="goToNews(news)"
            >
              <div class="news-title">{{ news.title }}</div>
              <div class="news-meta">{{ fmtDateTime(news.publish_date || news.datetime || news.date) }}</div>
            </div>
          </div>
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
import { fmtAmount, fmtDateTime } from '@/utils/format'
import type { NewsRecord, SectorRecord } from '@/types'
import ProgressTable from '@/components/ProgressTable/index.vue'
import MarketSentiment from '@/components/MarketSentiment/index.vue'
import SectorHeatmap from '@/components/SectorHeatmap/index.vue'
import { Monitor, DataAnalysis, TrendCharts, ChatDotRound, Refresh } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'

const router = useRouter()
const collectStore = useCollectStore()
const loading = ref(false)
const newsList = ref<NewsRecord[]>([])
const newsCount = ref(0)

function goToNews(news: NewsRecord) {
  if (news.url) {
    window.open(news.url, '_blank', 'noopener,noreferrer')
  } else {
    router.push('/news')
  }
}

function handleSectorSelect(sector: SectorRecord) {
  ElMessage.info(`跳转至板块: ${sector.name}`)
  router.push({ path: '/sector-flow', query: { name: sector.name } })
}

async function refreshData() {
  loading.value = true
  try {
    await collectStore.fetchProgress()
    await loadNews()
  } finally {
    loading.value = false
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
  gap: 16px;
}

.metric-cards {
  margin-bottom: 0;
}

.metric-card {
  background: #1f1f1f;
  border: 1px solid #2c2c2c;
}

.metric-card :deep(.el-card__body) {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 20px;
}

.metric-content {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.metric-label {
  font-size: 13px;
  color: #909399;
}

.metric-value {
  font-size: 24px;
  font-weight: 700;
  color: #e5eaf3;
}

.metric-sub {
  font-size: 14px;
  font-weight: normal;
  color: #909399;
}

.metric-icon {
  opacity: 0.7;
}

.text-success { color: #67c23a; }
.text-danger { color: #f56c6c; }
.text-primary { color: #409eff; }

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

.main-content-row {
  flex: 1;
}

.news-list {
  display: flex;
  flex-direction: column;
  gap: 0;
  max-height: 400px;
  overflow-y: auto;
}

.news-item {
  padding: 10px 0;
  border-bottom: 1px solid #2c2c2c;
  cursor: pointer;
}

.news-item:last-child {
  border-bottom: none;
}

.news-title {
  font-size: 13px;
  color: #e5eaf3;
  line-height: 1.4;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.news-title:hover {
  color: #409eff;
}

.news-meta {
  font-size: 11px;
  color: #606266;
  margin-top: 4px;
}

.empty-state {
  padding: 20px 0;
}

.sentiment-card {
  margin-top: 16px;
}
</style>
