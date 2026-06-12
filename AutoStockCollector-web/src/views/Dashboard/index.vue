<template>
  <div class="dashboard">
    <!-- Metric cards -->
    <el-row v-if="!dataLoaded" :gutter="16" class="metric-cards">
      <el-col v-for="i in 4" :key="i" :span="6">
        <el-card class="metric-card" shadow="never">
          <div class="metric-content">
            <div class="sk-line sk-label-line"></div>
            <div class="sk-line sk-value-line"></div>
          </div>
          <div class="sk-circle"></div>
        </el-card>
      </el-col>
    </el-row>
    <el-row v-else :gutter="16" class="metric-cards">
      <el-col :span="6">
        <el-card class="metric-card" shadow="never">
          <div class="metric-content">
            <div class="metric-label">后端状态</div>
            <div :class="['metric-value', collectStore.backendOnline ? 'text-success' : 'text-danger']">
              {{ collectStore.backendOnline ? '正常运行' : '离线' }}
            </div>
          </div>
          <el-icon class="metric-icon" :color="collectStore.backendOnline ? '#3f9d70' : '#d05a51'" size="36">
            <Monitor />
          </el-icon>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="metric-card" shadow="never">
          <div class="metric-content">
            <div class="metric-label">采集完成度</div>
            <div class="metric-value">
              <span class="text-primary num">{{ collectStore.completedCount }}</span>
              <span class="metric-sub"> / 8 类</span>
            </div>
          </div>
          <el-icon class="metric-icon" color="#3f7fae" size="36">
            <DataAnalysis />
          </el-icon>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="metric-card" shadow="never">
          <div class="metric-content">
            <div class="metric-label">累计成功条数</div>
            <div class="metric-value text-primary num">{{ fmtAmount(collectStore.totalSuccessCount) }}</div>
          </div>
          <el-icon class="metric-icon" color="#c9943a" size="36">
            <TrendCharts />
          </el-icon>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="metric-card" shadow="never">
          <div class="metric-content">
            <div class="metric-label">最新新闻条数</div>
            <div class="metric-value text-primary num">{{ newsCount }}</div>
          </div>
          <el-icon class="metric-icon" color="#909399" size="36">
            <ChatDotRound />
          </el-icon>
        </el-card>
      </el-col>
    </el-row>

    <!-- Data health card grid -->
    <el-card shadow="never" class="section-card health-summary-card">
      <template #header>
        <div class="card-header">
          <span>数据健康状态</span>
          <el-button size="small" text @click="router.push('/data-monitor')">
            → 去采集中心
          </el-button>
        </div>
      </template>

      <!-- Skeleton: before first data load -->
      <template v-if="!dataLoaded">
        <div class="health-summary-row">
          <div class="sk-line" style="width:90px;height:22px;border-radius:11px"></div>
          <div class="sk-line" style="width:90px;height:22px;border-radius:11px"></div>
          <div class="sk-line" style="width:90px;height:22px;border-radius:11px"></div>
        </div>
        <div class="health-cards-grid">
          <div v-for="i in 8" :key="i" class="health-card sk-health-card">
            <div class="sk-line" style="height:12px;width:60%"></div>
            <div class="sk-line" style="height:22px;width:80%"></div>
            <div class="sk-line" style="height:10px;width:50%"></div>
            <div class="sk-line" style="height:20px;width:40%;border-radius:10px"></div>
          </div>
        </div>
      </template>

      <!-- Real: after first data load -->
      <template v-else>
        <!-- Summary row -->
        <div class="health-summary-row">
          <el-tag type="success" size="small">最新 {{ healthOk }} 类</el-tag>
          <el-tag type="warning" size="small">需更新 {{ healthStale }} 类</el-tag>
          <el-tag type="danger" size="small">异常 {{ healthError }} 类</el-tag>
          <span class="health-stale-list" v-if="staleTypes.length">
            需更新：<span v-for="(t, i) in staleTypes" :key="t" class="stale-name">{{ t }}<span v-if="i < staleTypes.length - 1">、</span></span>
          </span>
        </div>
        <!-- 8 cards grid -->
        <div class="health-cards-grid">
          <div
            v-for="row in healthCards"
            :key="row.value"
            :class="['health-card', `health-card--${row.health}`]"
            @click="router.push('/data-monitor')"
          >
            <div class="hc-icon-name">
              <span class="hc-name">{{ row.label }}</span>
            </div>
            <div class="hc-count num">{{ row.record_count != null ? row.record_count.toLocaleString() : '--' }}<span class="hc-unit">{{ row.unit }}</span></div>
            <div :class="['hc-date', row.health === 'stale' ? 'hc-date--stale' : '']">{{ row.latest_date ?? '--' }}</div>
            <div class="hc-status">
              <el-tag v-if="row.health === 'ok'" type="success" size="small">最新</el-tag>
              <el-tag v-else-if="row.health === 'stale'" type="warning" size="small">需更新</el-tag>
              <el-tag v-else type="danger" size="small">异常</el-tag>
            </div>
          </div>
        </div>
      </template>
    </el-card>

    <!-- Main content: Market sentiment + Sector heatmap side by side -->
    <el-row :gutter="16" class="main-content-row" style="align-items: stretch">
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

    <!-- News list: full width below -->
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
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useCollectStore } from '@/stores/collectStore'
import { newsApi } from '@/api/news'
import { fmtAmount, fmtDateTime } from '@/utils/format'
import type { NewsRecord, SectorRecord } from '@/types'
import MarketSentiment from '@/components/MarketSentiment/index.vue'
import SectorHeatmap from '@/components/SectorHeatmap/index.vue'
import { Monitor, DataAnalysis, TrendCharts, ChatDotRound, Refresh } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { TYPE_LABEL } from '@/utils/collectTypes'

const router = useRouter()
const collectStore = useCollectStore()
const loading = ref(false)
const dataLoaded = ref(false)
const newsList = ref<NewsRecord[]>([])
const newsCount = ref(0)

// 数据健康摘要（只读，操作去采集中心）
const healthOk = computed(() => collectStore.progressList.filter(p => (p as any).health === 'ok').length)
const healthStale = computed(() => collectStore.progressList.filter(p => (p as any).health === 'stale').length)
const healthError = computed(() => collectStore.progressList.filter(p => (p as any).health === 'error').length)
const staleTypes = computed(() =>
  collectStore.progressList
    .filter(p => (p as any).health === 'stale')
    .map(p => (TYPE_LABEL as Record<string, string>)[p.task_type] || p.task_type)
)

const CARD_META: Record<string, { unit: string }> = {
  kline:        { unit: '条' },
  financial:    { unit: '条' },
  dragon_tiger: { unit: '条' },
  margin:       { unit: '条' },
  news:         { unit: '条' },
  fund_flow:    { unit: '条' },
  sector:       { unit: '条' },
  stock_info:   { unit: '只' },
}

const CARD_ORDER = ['kline', 'financial', 'dragon_tiger', 'margin', 'news', 'fund_flow', 'sector', 'stock_info']

const healthCards = computed(() => {
  const byType: Record<string, any> = {}
  collectStore.progressList.forEach(p => { byType[p.task_type] = p })
  return CARD_ORDER.map(key => {
    const p = byType[key] || {}
    const meta = CARD_META[key] || { unit: '条' }
    return {
      value: key,
      label: (TYPE_LABEL as Record<string, string>)[key] || key,
      unit: meta.unit,
      record_count: (p.record_count ?? (p as any).record_count) as number | null,
      latest_date: ((p as any).latest_date ?? (p as any).date_to) as string | null,
      health: ((p as any).health ?? ((p as any).record_count > 0 ? 'stale' : 'error')) as string,
    }
  })
})

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
  gap: 16px;
}

.metric-cards {
  margin-bottom: 0;
}

.metric-card {
  background: var(--bg-card);
  border: 1px solid var(--border-color);
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
  color: var(--text-muted);
}

.metric-value {
  font-size: 24px;
  font-weight: 700;
  color: var(--text-primary);
}

.metric-sub {
  font-size: 14px;
  font-weight: normal;
  color: var(--text-muted);
}

.metric-icon {
  opacity: 0.7;
}

.text-success { color: var(--el-color-success); }
.text-danger { color: var(--el-color-danger); }
.text-primary { color: var(--el-color-primary); }

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

.main-content-row {
  flex: 1;
}

.news-list {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 0 24px;
  max-height: 320px;
  overflow-y: auto;
}

.news-item {
  padding: 10px 0;
  border-bottom: 1px solid var(--border-color);
  cursor: pointer;
}

.news-item:last-child {
  border-bottom: none;
}

.news-title {
  font-size: 13px;
  color: var(--text-primary);
  line-height: 1.4;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.news-title:hover {
  color: var(--el-color-primary);
}

.news-meta {
  font-size: 11px;
  color: var(--text-faint);
  margin-top: 4px;
}

.empty-state {
  padding: 20px 0;
}

.fill-card {
  flex: 1;
}

.health-summary-card {
  margin-bottom: 0;
}

/* 汇总行 */
.health-summary-row {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  margin-bottom: 14px;
}

.health-stale-list {
  font-size: 12px;
  color: var(--text-muted);
}

.stale-name {
  color: var(--el-color-warning);
  font-weight: 600;
}

/* 8 卡片网格 */
.health-cards-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 10px;
}

.health-card {
  background: var(--bg-soft);
  border-radius: 6px;
  padding: 12px 14px;
  border-left: 3px solid transparent;
  cursor: pointer;
  transition: background 0.15s;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.health-card:hover {
  background: var(--bg-soft);
}

.health-card--ok    { border-left-color: var(--el-color-success); }
.health-card--stale { border-left-color: var(--el-color-warning); }
.health-card--error { border-left-color: var(--el-color-danger); background: rgba(196, 69, 60, 0.05); }

.hc-icon-name {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: var(--text-muted);
}


.hc-name {
  font-weight: 600;
  color: var(--text-secondary);
}

.hc-count {
  font-size: 18px;
  font-weight: 700;
  color: var(--text-primary);
  line-height: 1.2;
}

.hc-unit {
  font-size: 11px;
  font-weight: normal;
  color: var(--text-faint);
  margin-left: 2px;
}

.hc-date {
  font-size: 11px;
  color: var(--text-faint);
}

.hc-date--stale {
  color: var(--el-color-warning);
}

.hc-status {
  margin-top: 2px;
}

/* ── 骨架屏 ── */
@keyframes shimmer {
  0%   { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}

.sk-line {
  background: linear-gradient(
    90deg,
    var(--bg-hover-subtle) 25%,
    var(--bg-hover) 50%,
    var(--bg-hover-subtle) 75%
  );
  background-size: 200% 100%;
  animation: shimmer 1.5s infinite;
  border-radius: 4px;
}

.sk-label-line {
  height: 13px;
  width: 55%;
}

.sk-value-line {
  height: 26px;
  width: 70%;
}

.sk-circle {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: linear-gradient(
    90deg,
    var(--bg-hover-subtle) 25%,
    var(--bg-hover) 50%,
    var(--bg-hover-subtle) 75%
  );
  background-size: 200% 100%;
  animation: shimmer 1.5s infinite;
  flex-shrink: 0;
}

.sk-health-card {
  gap: 8px;
  border-left-color: var(--border-strong);
  cursor: default;
}

.sk-health-card:hover {
  background: var(--bg-soft);
}
</style>
