<template>
  <div class="ai-monitor">
    <!-- Header -->
    <div class="monitor-header">
      <div class="header-left">
        <h2>AI 实时监控</h2>
        <span class="header-sub">主力资金 · 研报分析 · 长短线建议</span>
      </div>
      <div class="header-right">
        <el-tag v-if="lastRefresh" type="info" effect="plain" class="refresh-tag">
          上次刷新: {{ lastRefresh }}
        </el-tag>
        <el-button type="primary" :loading="refreshing" @click="handleRefresh" size="small">
          <el-icon><Refresh /></el-icon> 刷新
        </el-button>
      </div>
    </div>

    <!-- Tabs -->
    <el-tabs v-model="activeTab" class="main-tabs">
      <el-tab-pane label="综合信号" name="signal" />
      <el-tab-pane label="新闻舆情" name="news_sentiment">
        <template #label>
          <span>新闻舆情 <el-tag v-if="sentimentBullishCount" size="small" type="danger" effect="light" class="sentiment-count">{{ sentimentBullishCount }}利好</el-tag></span>
        </template>
      </el-tab-pane>
      <el-tab-pane label="资金异动" name="fund_flow" />
      <el-tab-pane label="持仓建议" name="position_advice">
        <template #label>
          <span>持仓建议 <el-tag v-if="positionAdviceCount" size="small" type="warning" effect="light" class="sentiment-count">{{ positionAdviceCount }}条建议</el-tag></span>
        </template>
      </el-tab-pane>
      <el-tab-pane label="监控调仓" name="dual_track" />
    </el-tabs>

    <!-- Signal View -->
    <template v-if="activeTab === 'signal'">
      <AiMonitorFilter
        v-model:search-text="searchText"
        v-model:signal-filter="signalFilter"
        v-model:type-filter="typeFilter"
      />

      <AiMonitorStats
        :position-count="positionCount"
        :watchlist-count="watchlistCount"
        :short-buy-count="shortBuyCount"
        :long-buy-count="longBuyCount"
        :short-sell-count="shortSellCount"
        :long-sell-count="longSellCount"
      />

      <AiMonitorSignalGrid
        :filtered-signals="filteredSignals"
        :loading="loading"
        @show-detail="showDetail"
      />
    </template>

    <!-- News Sentiment View -->
    <template v-if="activeTab === 'news_sentiment'">
      <AiMonitorNewsFeed
        v-model:news-search-text="newsSearchText"
        :news-feed-positive="newsFeedPositive"
        :news-feed-negative="newsFeedNegative"
        :signals-with-news-count="signalsWithNewsCount"
        @show-stock-detail="showStockDetail"
      />
    </template>

    <!-- Fund Flow Anomalies View -->
    <AiMonitorFundFlow v-if="activeTab === 'fund_flow'" />

    <!-- Position Advice View -->
    <AiMonitorPositionAdvice
      v-if="activeTab === 'position_advice'"
      :signals="signals"
      :loading="loading"
    />

    <!-- Dual-Track Rebalance View -->
    <AiMonitorDualTrack v-if="activeTab === 'dual_track'" />

    <!-- Detail Dialog -->
    <AiMonitorDetailDialog
      v-model:visible="detailVisible"
      :detail-data="detailData"
      v-model:detail-tab="detailTab"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { Refresh } from '@element-plus/icons-vue'
import { monitorApi, type MonitorSignal } from '@/api/monitor'
import { ElMessage } from 'element-plus'

import AiMonitorFilter from './components/AiMonitorFilter.vue'
import AiMonitorStats from './components/AiMonitorStats.vue'
import AiMonitorSignalGrid from './components/AiMonitorSignalGrid.vue'
import AiMonitorNewsFeed from './components/AiMonitorNewsFeed.vue'
import AiMonitorDetailDialog from './components/AiMonitorDetailDialog.vue'
import AiMonitorFundFlow from './components/AiMonitorFundFlow.vue'
import AiMonitorPositionAdvice from './components/AiMonitorPositionAdvice.vue'
import AiMonitorDualTrack from './components/AiMonitorDualTrack.vue'

const signals = ref<MonitorSignal[]>([])
const loading = ref(false)
const refreshing = ref(false)
const lastRefresh = ref('')
const searchText = ref('')
const signalFilter = ref('')
const typeFilter = ref('')
const activeTab = ref('signal')
const detailVisible = ref(false)
const detailData = ref<MonitorSignal | null>(null)
const detailTab = ref('fund_flow')

let refreshTimer: ReturnType<typeof setInterval> | null = null

function profitScore(s: MonitorSignal): number {
  const pp = s.price_prediction
  const adv = s.trading_advice
  if (!pp) return s.composite.score || 50
  const expRet = pp.expected_return || 0
  const rr = adv?.risk_reward_ratio || 0
  const comp = s.composite.score || 50
  return comp * 0.40 + Math.min(Math.max(expRet, 0) * 2, 100) * 0.35 + Math.min(rr * 10, 100) * 0.25
}

const filteredSignals = computed(() => {
  let list = signals.value
  if (searchText.value) {
    const q = searchText.value.toLowerCase()
    list = list.filter(s => s.code.toLowerCase().includes(q) || s.name.toLowerCase().includes(q))
  }
  if (signalFilter.value) {
    switch (signalFilter.value) {
      case 'short_buy': list = list.filter(s => s.short_term.score >= 60); break
      case 'short_sell': list = list.filter(s => s.short_term.score < 40); break
      case 'long_buy': list = list.filter(s => s.long_term.score >= 60); break
      case 'long_sell': list = list.filter(s => s.long_term.score < 40); break
    }
  }
  if (typeFilter.value) {
    list = list.filter(s => s.type === typeFilter.value)
  }
  return list.sort((a, b) => profitScore(b) - profitScore(a))
})

const positionCount = computed(() => signals.value.filter(s => s.type === '持仓').length)
const watchlistCount = computed(() => signals.value.filter(s => s.type === '自选').length)
const shortBuyCount = computed(() => signals.value.filter(s => s.short_term.score >= 60).length)
const longBuyCount = computed(() => signals.value.filter(s => s.long_term.score >= 60).length)
const shortSellCount = computed(() => signals.value.filter(s => s.short_term.score < 40).length)
const longSellCount = computed(() => signals.value.filter(s => s.long_term.score < 40).length)

// ── News Feed view ──
const newsSearchText = ref('')

interface NewsFeedItem {
  _key: string
  code: string
  name: string
  title: string
  date: string
  source: string
  keywords: string[]
}

const newsFeedPositive = computed<NewsFeedItem[]>(() => {
  const items: NewsFeedItem[] = []
  for (const s of signals.value) {
    const ns = s.analysis.news_sentiment
    if (!ns?.recent_positive_news?.length) continue
    for (const n of ns.recent_positive_news) {
      items.push({
        _key: `${s.code}_pos_${n.title}_${n.date}`,
        code: s.code,
        name: s.name,
        title: n.title,
        date: n.date || '',
        source: n.source || '',
        keywords: n.keywords || [],
      })
    }
  }
  return items
})

const newsFeedNegative = computed<NewsFeedItem[]>(() => {
  const items: NewsFeedItem[] = []
  for (const s of signals.value) {
    const ns = s.analysis.news_sentiment
    if (!ns?.recent_negative_news?.length) continue
    for (const n of ns.recent_negative_news) {
      items.push({
        _key: `${s.code}_neg_${n.title}_${n.date}`,
        code: s.code,
        name: s.name,
        title: n.title,
        date: n.date || '',
        source: n.source || '',
        keywords: n.keywords || [],
      })
    }
  }
  return items
})

const signalsWithNewsCount = computed(() =>
  signals.value.filter(s => (s.analysis.news_sentiment?.news_count ?? 0) > 0).length
)

const sentimentBullishCount = computed(() =>
  signals.value.filter(s => s.analysis.news_sentiment?.overall?.bullish).length
)

const positionAdviceCount = computed(() =>
  signals.value.filter(s => s.type === '持仓' && s.trading_advice?.action_signal && s.trading_advice.action_signal !== 'hold').length
)

function fetchSignals() {
  loading.value = true
  monitorApi.getSignals().then(resp => {
    signals.value = (resp.data as any).data || []
  }).catch(() => {
    ElMessage.error('获取监控信号失败')
  }).finally(() => {
    loading.value = false
  })
}

function handleRefresh() {
  refreshing.value = true
  monitorApi.refresh().then(() => {
    ElMessage.success('刷新任务已启动')
    setTimeout(fetchSignals, 3000)
  }).catch(() => {
    ElMessage.error('刷新失败')
  }).finally(() => {
    refreshing.value = false
    lastRefresh.value = new Date().toLocaleTimeString()
  })
}

function showDetail(s: MonitorSignal) {
  detailData.value = s
  detailTab.value = 'fund_flow'
  detailVisible.value = true
}

function showStockDetail(code: string) {
  const s = signals.value.find(x => x.code === code)
  if (s) showDetail(s)
}

function isTradingNow(): boolean {
  const now = new Date()
  const day = now.getDay()
  if (day === 0 || day === 6) return false
  const t = now.getHours() * 60 + now.getMinutes()
  return (t >= 570 && t <= 690) || (t >= 780 && t <= 900) // 9:30-11:30 / 13:00-15:00
}

onMounted(() => {
  fetchSignals()
  // 盘中 30s 拿实时数据，非交易时段 60s
  refreshTimer = setInterval(fetchSignals, isTradingNow() ? 30000 : 60000)
})

onUnmounted(() => {
  if (refreshTimer) clearInterval(refreshTimer)
})
</script>

<style scoped>
.ai-monitor {
  padding: 16px;
  height: 100%;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.monitor-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.header-left h2 {
  margin: 0;
  font-size: 20px;
  font-weight: 600;
}

.header-sub {
  font-size: 12px;
  color: var(--text-muted, #999);
  margin-left: 8px;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 8px;
}

.refresh-tag { font-size: 11px; }

/* ===== Main Tabs ===== */
.main-tabs { margin-top: 8px; }
.main-tabs :deep(.el-tabs__header) { margin-bottom: 12px; }
.main-tabs :deep(.el-tabs__item) { font-weight: 600; font-size: 14px; }
.sentiment-count { margin-left: 4px; }
</style>
