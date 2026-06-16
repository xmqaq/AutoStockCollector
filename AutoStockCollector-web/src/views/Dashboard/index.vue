<template>
  <div class="dashboard">
    <!-- News Ticker & Collapse (Moved to top) -->
    <div class="news-ticker-container">
      <div class="news-ticker-bar" @click="isNewsExpanded = !isNewsExpanded">
        <div class="ticker-label">
          <el-icon><ChatDotRound /></el-icon>
          <span>最新资讯</span>
        </div>
        
        <div class="ticker-content" v-if="newsList.length > 0">
          <div class="ticker-item" :key="currentNewsIndex">
            <span class="ticker-time">{{ fmtDateTime(newsList[currentNewsIndex].publish_date || newsList[currentNewsIndex].datetime || newsList[currentNewsIndex].date).split(' ')[1] }}</span>
            <span class="ticker-title">{{ newsList[currentNewsIndex].title }}</span>
          </div>
        </div>
        <div class="ticker-content empty" v-else>
          <span>暂无新闻</span>
        </div>

        <div class="ticker-action">
          <el-icon class="expand-icon" :class="{ 'is-expanded': isNewsExpanded }"><ArrowDown /></el-icon>
        </div>
      </div>

      <!-- Collapsible News List -->
      <div class="news-collapse-panel" :class="{ 'is-expanded': isNewsExpanded }">
        <div class="news-list-inner">
          <div v-if="newsList.length === 0" class="empty-state">
            <el-empty description="暂无新闻" :image-size="60" />
          </div>
          <div v-else class="news-grid">
            <div
              v-for="(news, idx) in newsList"
              :key="idx"
              class="news-card"
              @click.stop="goToNews(news)"
            >
              <div class="news-time-col">
                <div class="time">{{ fmtDateTime(news.publish_date || news.datetime || news.date).split(' ')[1] }}</div>
                <div class="date">{{ fmtDateTime(news.publish_date || news.datetime || news.date).split(' ')[0].slice(5) }}</div>
              </div>
              <div class="news-content-col">
                <div class="news-title">{{ news.title }}</div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Metric cards -->
    <el-row v-if="!dataLoaded" :gutter="16" class="metric-cards">
      <el-col v-for="i in 4" :key="i" :span="6">
        <div class="metric-card sk-card">
          <div class="sk-line sk-label-line"></div>
          <div class="sk-line sk-value-line"></div>
        </div>
      </el-col>
    </el-row>
    <el-row v-else :gutter="16" class="metric-cards">
      <!-- Card 1: Backend Status (Primary Gradient) -->
      <el-col :span="6">
        <div class="metric-card metric-card--primary">
          <div class="metric-content">
            <div class="metric-label">后端状态</div>
            <div class="metric-value-wrapper">
              <div :class="['status-dot-large', collectStore.backendOnline ? 'online' : 'offline']"></div>
              <div class="metric-value">{{ collectStore.backendOnline ? '正常运行' : '离线' }}</div>
            </div>
          </div>
          <el-icon class="metric-icon-bg"><Monitor /></el-icon>
        </div>
      </el-col>
      <!-- Card 2: Collection Progress -->
      <el-col :span="6">
        <div class="metric-card">
          <div class="metric-content">
            <div class="metric-label">采集完成度</div>
            <div class="metric-value-wrapper">
              <div class="metric-value num">{{ collectStore.completedCount }}</div>
              <div class="metric-sub">/ 8 类</div>
            </div>
          </div>
          <el-icon class="metric-icon-bg"><DataAnalysis /></el-icon>
        </div>
      </el-col>
      <!-- Card 3: Total Records -->
      <el-col :span="6">
        <div class="metric-card">
          <div class="metric-content">
            <div class="metric-label">累计成功条数</div>
            <div class="metric-value-wrapper">
              <div class="metric-value num text-gradient">{{ fmtAmount(collectStore.totalSuccessCount) }}</div>
            </div>
          </div>
          <el-icon class="metric-icon-bg"><TrendCharts /></el-icon>
        </div>
      </el-col>
      <!-- Card 4: News -->
      <el-col :span="6">
        <div class="metric-card">
          <div class="metric-content">
            <div class="metric-label">最新新闻条数</div>
            <div class="metric-value-wrapper">
              <div class="metric-value num">{{ newsCount }}</div>
              <div class="metric-sub"></div>
            </div>
          </div>
          <el-icon class="metric-icon-bg"><ChatDotRound /></el-icon>
        </div>
      </el-col>
    </el-row>

    <!-- Data health card grid - Modernized & Ultra Compact -->
    <el-card shadow="never" class="section-card health-section-card">
      <div class="section-header">
        <h2 class="section-title">数据健康状态</h2>
        <el-button class="modern-btn" text @click="router.push('/data-monitor')">
          → 去采集中心
        </el-button>
      </div>

      <!-- Skeleton: before first data load -->
      <template v-if="!dataLoaded">
        <div class="health-pill-grid">
          <div v-for="i in 8" :key="i" class="health-pill sk-pill">
            <div class="sk-line" style="height:12px;width:80%"></div>
          </div>
        </div>
      </template>

      <!-- Real: after first data load -->
      <template v-else>
        <!-- Ultra compact pill grid -->
        <div class="health-pill-grid">
          <div
            v-for="row in healthCards"
            :key="row.value"
            :class="['health-pill', `health-pill--${row.health}`]"
            @click="router.push('/data-monitor')"
          >
            <div :class="['pill-indicator', row.health]"></div>
            <span class="pill-name">{{ row.label }}</span>
            <div class="pill-divider"></div>
            <span class="pill-date">{{ row.latest_date ?? '--' }}</span>
            
            <!-- Hover details -->
            <div class="pill-hover-info">
              <span class="hover-count num">{{ row.record_count != null ? row.record_count.toLocaleString() : '--' }}</span>
              <span class="hover-unit">{{ row.unit }}</span>
              <span class="hover-status">{{ row.health === 'ok' ? '最新' : row.health === 'stale' ? '需更新' : '异常' }}</span>
            </div>
          </div>
        </div>
      </template>
    </el-card>

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
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useCollectStore } from '@/stores/collectStore'
import { newsApi } from '@/api/news'
import { fmtAmount, fmtDateTime } from '@/utils/format'
import type { NewsRecord, SectorRecord } from '@/types'
import MarketSentiment from '@/components/MarketSentiment/index.vue'
import SectorHeatmap from '@/components/SectorHeatmap/index.vue'
import { Monitor, DataAnalysis, TrendCharts, ChatDotRound, Refresh, ArrowDown } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { TYPE_LABEL } from '@/utils/collectTypes'

const router = useRouter()
const collectStore = useCollectStore()
const loading = ref(false)
const dataLoaded = ref(false)
const newsList = ref<NewsRecord[]>([])
const newsCount = ref(0)

// News Ticker State
const isNewsExpanded = ref(false)
const currentNewsIndex = ref(0)
let tickerTimer: ReturnType<typeof setInterval> | null = null

function startTicker() {
  stopTicker()
  tickerTimer = setInterval(() => {
    if (newsList.value.length > 0 && !isNewsExpanded.value) {
      currentNewsIndex.value = (currentNewsIndex.value + 1) % newsList.value.length
    }
  }, 4000)
}

function stopTicker() {
  if (tickerTimer) {
    clearInterval(tickerTimer)
    tickerTimer = null
  }
}

// Helper formatters
function fmtTimeOnly(d: string | undefined): string {
  if (!d) return '--:--'
  return fmtDateTime(d).split(' ')[1] || d
}

function fmtDateOnly(d: string | undefined): string {
  if (!d) return '----/--/--'
  return fmtDateTime(d).split(' ')[0] || d
}

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
      if (newsList.value.length > 0) {
        startTicker()
      }
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
  stopTicker()
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

/* --- Typography & Layout --- */
.section-card {
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-sm);
  overflow: hidden;
}

.health-section-card {
  margin-bottom: 0;
}

.health-section-card :deep(.el-card__body) {
  padding: 20px 24px;
}

.section-container {
  display: flex;
  flex-direction: column;
  gap: 1.5vh;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.section-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
  letter-spacing: -0.01em;
}

.fill-height {
  height: 100%;
}

.chart-card {
  background: var(--bg-card);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-sm);
  border: 1px solid var(--border-color);
  padding: 24px;
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

/* --- News Ticker & Collapse --- */
.news-ticker-container {
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-sm);
  overflow: hidden;
  margin-bottom: 0;
}

.news-ticker-bar {
  display: flex;
  align-items: center;
  padding: 12px 20px;
  cursor: pointer;
  transition: background-color 0.2s;
  background: var(--bg-elevated);
}

.news-ticker-bar:hover {
  background: var(--bg-hover-subtle);
}

.ticker-label {
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--brand-500);
  font-weight: 600;
  font-size: 14px;
  padding-right: 16px;
  border-right: 1px solid var(--border-color);
  margin-right: 16px;
  white-space: nowrap;
}

.ticker-content {
  flex: 1;
  overflow: hidden;
  position: relative;
  height: 24px;
  display: flex;
  align-items: center;
}

.ticker-item {
  display: flex;
  align-items: center;
  gap: 12px;
  width: 100%;
  animation: slideUp 0.4s ease-out;
}

.ticker-time {
  font-family: var(--font-mono);
  color: var(--text-muted);
  font-size: 13px;
  white-space: nowrap;
}

.ticker-title {
  color: var(--text-primary);
  font-size: 14px;
  font-weight: 500;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.ticker-title:hover {
  color: var(--brand-500);
}

.ticker-content.empty {
  color: var(--text-muted);
  font-size: 14px;
}

.ticker-action {
  padding-left: 16px;
  color: var(--text-muted);
}

.expand-icon {
  transition: transform 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

.expand-icon.is-expanded {
  transform: rotate(180deg);
}

.news-collapse-panel {
  max-height: 0;
  overflow: hidden;
  transition: max-height 0.4s cubic-bezier(0.4, 0, 0.2, 1);
  background: var(--bg-card);
}

.news-collapse-panel.is-expanded {
  max-height: 500px;
  border-top: 1px solid var(--border-color);
}

.news-list-inner {
  padding: 16px 20px;
  overflow-y: auto;
  max-height: 500px;
}

.news-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 16px 24px;
}

.news-card {
  display: flex;
  gap: 16px;
  padding: 16px;
  border-radius: var(--radius-md);
  background: var(--bg-soft);
  border: 1px solid transparent;
  cursor: pointer;
  transition: all 0.2s ease;
}

.news-card:hover {
  background: var(--bg-hover-subtle);
  border-color: var(--border-color);
  transform: translateX(4px);
}

.news-card .news-time-col {
  flex-shrink: 0;
  text-align: right;
  border-right: 2px solid var(--brand-300);
  padding-right: 12px;
  min-width: 60px;
}

.news-card .news-time-col .time {
  font-family: var(--font-mono);
  font-size: 14px;
  font-weight: 700;
  color: var(--text-primary);
  line-height: 1.2;
}

.news-card .news-time-col .date {
  font-family: var(--font-mono);
  font-size: 11px;
  color: var(--text-muted);
  margin-top: 4px;
}

.news-card .news-content-col {
  flex: 1;
}

.news-card .news-content-col .news-title {
  font-size: 14px;
  font-weight: 500;
  color: var(--text-primary);
  line-height: 1.5;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.news-card:hover .news-title {
  color: var(--brand-500);
}

@keyframes slideUp {
  from { opacity: 0; transform: translateY(10px); }
  to { opacity: 1; transform: translateY(0); }
}

/* --- Metric Cards --- */
.metric-cards {
  margin-bottom: 8px;
}

.metric-card {
  position: relative;
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
  padding: 24px;
  box-shadow: var(--shadow-sm);
  overflow: hidden;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.metric-card:hover {
  transform: translateY(-4px);
  box-shadow: var(--shadow-md);
  border-color: var(--brand-300);
}

.metric-card--primary {
  background: linear-gradient(135deg, var(--brand-600) 0%, var(--brand-800) 100%);
  border: none;
  box-shadow: 0 8px 24px -6px rgba(79, 70, 229, 0.5);
}

.metric-card--primary .metric-label,
.metric-card--primary .metric-value,
.metric-card--primary .metric-icon-bg {
  color: #fff;
}

.metric-card--primary:hover {
  box-shadow: 0 12px 28px -6px rgba(79, 70, 229, 0.6);
  border-color: transparent;
}

.metric-content {
  position: relative;
  z-index: 2;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.metric-label {
  font-size: 14px;
  font-weight: 500;
  color: var(--text-secondary);
}

.metric-value-wrapper {
  display: flex;
  align-items: baseline;
  gap: 8px;
}

.metric-value {
  font-size: 32px;
  font-weight: 800;
  color: var(--text-primary);
  line-height: 1;
  letter-spacing: -0.02em;
}

.metric-sub {
  font-size: 14px;
  color: var(--text-muted);
  font-weight: 500;
}

.text-gradient {
  background: linear-gradient(135deg, var(--brand-500) 0%, #3b82f6 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}

.metric-icon-bg {
  position: absolute;
  right: -10px;
  bottom: -20px;
  font-size: 100px;
  opacity: 0.04;
  color: var(--brand-600);
  transform: rotate(-15deg);
  transition: transform 0.4s ease;
}

.metric-card:hover .metric-icon-bg {
  transform: rotate(0deg) scale(1.1);
}

.metric-card--primary .metric-icon-bg {
  opacity: 0.15;
  color: #fff;
}

/* Status Dot */
.status-dot-large {
  width: 12px;
  height: 12px;
  border-radius: 50%;
  position: relative;
}

.status-dot-large.online {
  background-color: #10b981;
  box-shadow: 0 0 12px rgba(16, 185, 129, 0.6);
}

.status-dot-large.offline {
  background-color: #ef4444;
  box-shadow: 0 0 12px rgba(239, 68, 68, 0.6);
}

/* --- Health Cards Grid --- */
.health-pill-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
}

.health-pill {
  background: var(--bg-card);
  border-radius: var(--radius-sm);
  padding: 10px 14px;
  border: 1px solid var(--border-color);
  cursor: pointer;
  transition: all 0.2s ease;
  display: flex;
  align-items: center;
  position: relative;
  overflow: hidden;
}

.health-pill:hover {
  background: var(--bg-hover-subtle);
  border-color: var(--brand-300);
}

.health-pill--error {
  background: var(--tint-danger-bg);
  border-color: rgba(239, 68, 68, 0.2);
}

.pill-indicator {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  margin-right: 10px;
  flex-shrink: 0;
}

.pill-indicator.ok { background-color: var(--color-success); box-shadow: 0 0 6px rgba(16, 185, 129, 0.4); }
.pill-indicator.stale { background-color: var(--color-warning); box-shadow: 0 0 6px rgba(245, 158, 11, 0.4); }
.pill-indicator.error { background-color: var(--color-danger); box-shadow: 0 0 6px rgba(239, 68, 68, 0.4); }

.pill-name {
  font-weight: 500;
  color: var(--text-primary);
  font-size: 13px;
  white-space: nowrap;
}

.pill-divider {
  flex: 1;
  height: 1px;
  border-bottom: 1px dashed var(--border-color);
  margin: 0 10px;
  opacity: 0.5;
}

.pill-date {
  font-size: 12px;
  color: var(--text-muted);
  font-family: var(--font-mono);
  white-space: nowrap;
}

/* Hover Information Overlay */
.pill-hover-info {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background: var(--bg-elevated);
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  opacity: 0;
  transform: translateY(100%);
  transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
}

.health-pill:hover .pill-hover-info {
  opacity: 1;
  transform: translateY(0);
}

.hover-count {
  font-size: 15px;
  font-weight: 700;
  color: var(--text-primary);
}

.hover-unit {
  font-size: 12px;
  color: var(--text-secondary);
}

.hover-status {
  font-size: 11px;
  padding: 2px 6px;
  border-radius: 4px;
  background: var(--bg-soft);
  margin-left: 8px;
}

/* --- Modern Button --- */
.modern-btn {
  color: var(--brand-600);
  font-weight: 600;
  transition: all 0.2s;
}

.modern-btn:hover {
  background: var(--bg-hover-subtle);
  transform: translateX(2px);
}

/* --- Modernized News List Stream --- */

/* --- Skeleton --- */
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

.sk-card {
  flex-direction: column;
  align-items: flex-start;
  gap: 16px;
}

.sk-label-line { height: 16px; width: 40%; }
.sk-value-line { height: 32px; width: 70%; }

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
