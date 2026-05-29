<template>
  <div class="market-view">
    <el-tabs v-model="activeTab" class="market-tabs">
      <el-tab-pane label="大盘行情" name="indices">
        <div class="indices-grid">
          <div
            v-for="idx in indices"
            :key="idx.code"
            :class="['index-card', getColorClass(idx.change)]"
          >
            <div class="index-name">{{ idx.name }}</div>
            <div class="index-price">{{ fmtPrice(idx.price) }}</div>
            <div :class="['index-change', getTextClass(idx.change)]">
              <span>{{ fmtChange(idx.change) }}</span>
              <span class="change-amount">{{ fmtAmount(idx.amount) }}</span>
            </div>
          </div>
        </div>
        <div class="refresh-bar">
          <el-button size="small" @click="loadIndices" :loading="indicesLoading">
            <el-icon><Refresh /></el-icon> 刷新
          </el-button>
          <span class="update-time">更新时间: {{ updateTime }}</span>
          <span class="auto-tip">每1分钟自动刷新</span>
        </div>
      </el-tab-pane>

      <el-tab-pane label="自选行情" name="watchlist">
        <div class="watchlist-toolbar">
          <el-input
            v-model="addCode"
            placeholder="输入股票代码"
            style="width:200px"
            @keyup.enter="handleAddStock"
          />
          <el-button type="primary" size="small" @click="handleAddStock" :disabled="!addCode">
            <el-icon><Plus /></el-icon> 添加
          </el-button>
          <el-button size="small" @click="loadQuotes" :loading="quotesLoading">
            <el-icon><Refresh /></el-icon> 刷新
          </el-button>
          <el-button size="small" @click="clearAll">清空
          </el-button>
        </div>

        <el-table :data="quotes" stripe size="small" class="quotes-table">
          <el-table-column prop="name" label="名称" width="100" />
          <el-table-column prop="code" label="代码" width="110" />
          <el-table-column label="现价" width="100" align="right">
            <template #default="{ row }">
              <span :class="getTextClass(row.change)">{{ fmtPrice(row.price) }}</span>
            </template>
          </el-table-column>
          <el-table-column label="涨跌幅" width="100" align="center">
            <template #default="{ row }">
              <span :class="getTextClass(row.change)">{{ fmtChange(row.change) }}</span>
            </template>
          </el-table-column>
          <el-table-column label="今开" width="80" align="right">
            <template #default="{ row }">{{ fmtPrice(row.open) }}</template>
          </el-table-column>
          <el-table-column label="最高" width="80" align="right">
            <template #default="{ row }">{{ fmtPrice(row.high) }}</template>
          </el-table-column>
          <el-table-column label="最低" width="80" align="right">
            <template #default="{ row }">{{ fmtPrice(row.low) }}</template>
          </el-table-column>
          <el-table-column label="昨收" width="80" align="right">
            <template #default="{ row }">{{ fmtPrice(row.prev_close) }}</template>
          </el-table-column>
          <el-table-column label="换手率" width="90" align="right">
            <template #default="{ row }">{{ fmtTurnover(row.turnover) }}</template>
          </el-table-column>
          <el-table-column label="成交额" width="100" align="right">
            <template #default="{ row }">{{ fmtAmount(row.amount) }}</template>
          </el-table-column>
          <el-table-column label="分时" width="80" align="center">
            <template #default="{ row }">
              <el-button size="small" link @click="showMiniChart(row)">查看</el-button>
            </template>
          </el-table-column>
          <el-table-column width="60" align="center">
            <template #default="{ row }">
              <el-button size="small" type="danger" link @click="removeStock(row.code)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>

      <el-tab-pane label="新闻舆情" name="news">
        <div class="news-toolbar">
          <el-input
            v-model="newsCodeFilter"
            placeholder="股票代码（可选）"
            style="width:200px"
            size="small"
            clearable
          />
          <el-button type="primary" size="small" @click="loadNews" :loading="newsLoading">
            <el-icon><Refresh /></el-icon> 刷新
          </el-button>
        </div>
        <el-table :data="newsList" stripe size="small" class="news-table" v-loading="newsLoading">
          <el-table-column prop="title" label="标题" min-width="200" show-overflow-tooltip />
          <el-table-column prop="source" label="来源" width="100" />
          <el-table-column label="时间" width="160">
            <template #default="{ row }">
              {{ fmtDateTime(row.publish_date || row.datetime || row.date) }}
            </template>
          </el-table-column>
          <el-table-column label="操作" width="100" align="center">
            <template #default="{ row }">
              <el-button size="small" link @click="analyzeNews(row)">AI分析</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>

      <el-tab-pane label="AI分析" name="ai-analysis">
        <div class="ai-toolbar">
          <el-select v-model="aiCode" placeholder="选择股票" filterable style="width:200px" size="default">
            <el-option
              v-for="stock in watchlistForAI"
              :key="stock.code"
              :label="`${stock.code} ${stock.name}`"
              :value="stock.code"
            />
          </el-select>
          <el-button type="primary" size="small" @click="runAIAnalysis" :loading="aiLoading" :disabled="!aiCode">
            <el-icon><MagicStick /></el-icon> 开始分析
          </el-button>
        </div>
        <el-card v-if="aiResult" shadow="never" class="section-card">
          <template #header>
            <div class="ai-result-header">
              <span>{{ aiResult.name || aiResult.code }}</span>
              <el-tag :type="aiSignalType(aiResult.signal)" size="large">
                {{ aiResult.signal || '观望' }}
              </el-tag>
            </div>
          </template>
          <el-descriptions :column="2" border size="small">
            <el-descriptions-item label="综合评分">
              {{ aiResult.composite_score?.toFixed(1) || '--' }}
            </el-descriptions-item>
            <el-descriptions-item label="推荐操作">
              {{ aiResult.recommendation || '--' }}
            </el-descriptions-item>
            <el-descriptions-item label="止损位">
              <span class="price-text stop-loss">{{ formatPrice(aiResult.stop_loss) }}</span>
            </el-descriptions-item>
            <el-descriptions-item label="目标价">
              <span class="price-text target-price">{{ formatPrice(aiResult.target_price) }}</span>
            </el-descriptions-item>
          </el-descriptions>
          <div class="ai-reasons">
            <div class="reason-title">推荐理由：</div>
            <ul>
              <li v-for="(reason, idx) in (aiResult.reasons || [])" :key="idx">{{ reason }}</li>
            </ul>
          </div>
        </el-card>
        <el-empty v-else description="请选择股票进行AI分析" />
      </el-tab-pane>

      <el-tab-pane label="交易信号" name="signals">
        <div class="signals-toolbar">
          <el-select v-model="signalCode" placeholder="选择股票" filterable style="width:200px" size="default">
            <el-option
              v-for="stock in watchlistForSignal"
              :key="stock.code"
              :label="`${stock.code} ${stock.name}`"
              :value="stock.code"
            />
          </el-select>
          <el-button type="primary" size="small" @click="detectSignals" :loading="signalLoading" :disabled="!signalCode">
            <el-icon><Search /></el-icon> 检测信号
          </el-button>
          <el-button size="small" @click="loadSignalHistory" :loading="signalHistoryLoading">
            历史信号
          </el-button>
        </div>

        <el-tabs v-model="signalSubTab" class="signal-sub-tabs">
          <el-tab-pane label="当前信号" name="current">
            <el-card shadow="never" class="section-card" v-loading="signalLoading">
              <template #header>
                <span>买入/卖出信号</span>
                <el-tag :type="latestSignal?.type === 'buy' ? 'success' : latestSignal?.type === 'sell' ? 'danger' : 'info'" size="small">
                  {{ latestSignal?.type === 'buy' ? '买入信号' : latestSignal?.type === 'sell' ? '卖出信号' : '观望' }}
                </el-tag>
              </template>
              <div v-if="latestSignal" class="signal-detail">
                <div class="signal-info">
                  <div class="signal-item">
                    <span class="label">信号类型：</span>
                    <span :class="latestSignal.type === 'buy' ? 'text-rise' : latestSignal.type === 'sell' ? 'text-fall' : ''">
                      {{ latestSignal.type === 'buy' ? '买入' : latestSignal.type === 'sell' ? '卖出' : '观望' }}
                    </span>
                  </div>
                  <div class="signal-item">
                    <span class="label">信号强度：</span>
                    <span>{{ latestSignal.strength || '--' }}</span>
                  </div>
                  <div class="signal-item">
                    <span class="label">触发价格：</span>
                    <span>{{ latestSignal.price?.toFixed(2) || '--' }}</span>
                  </div>
                  <div class="signal-item">
                    <span class="label">触发时间：</span>
                    <span>{{ latestSignal.time || '--' }}</span>
                  </div>
                </div>
                <div class="signal-reasons">
                  <div class="reason-title">触发原因：</div>
                  <ul>
                    <li v-for="(reason, idx) in latestSignal.reasons" :key="idx">{{ reason }}</li>
                  </ul>
                </div>
              </div>
              <el-empty v-else description="暂无信号，请先检测" />
            </el-card>
          </el-tab-pane>

          <el-tab-pane label="信号历史" name="history">
            <el-table :data="signalHistory" stripe size="small" class="signals-table" v-loading="signalHistoryLoading">
              <el-table-column prop="code" label="代码" width="110" />
              <el-table-column prop="name" label="名称" width="120" />
              <el-table-column label="信号类型" width="100" align="center">
                <template #default="{ row }">
                  <el-tag :type="row.type === 'buy' ? 'success' : row.type === 'sell' ? 'danger' : 'info'" size="small">
                    {{ row.type === 'buy' ? '买入' : row.type === 'sell' ? '卖出' : '观望' }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column label="信号强度" width="100" align="center">
                <template #default="{ row }">{{ row.strength || '--' }}</template>
              </el-table-column>
              <el-table-column label="价格" width="100" align="right">
                <template #default="{ row }">{{ row.price?.toFixed(2) || '--' }}</template>
              </el-table-column>
              <el-table-column label="时间" width="160">
                <template #default="{ row }">{{ row.time || '--' }}</template>
              </el-table-column>
              <el-table-column prop="reasons" label="原因" min-width="200" show-overflow-tooltip />
            </el-table>
          </el-tab-pane>
        </el-tabs>
      </el-tab-pane>
    </el-tabs>

    <el-dialog v-model="chartVisible" :title="chartTitle" width="600px">
      <v-chart :option="chartOption" style="height:400px" autoresize />
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch } from 'vue'
import { marketApi, type MarketIndex, type StockQuote, type MinuteBar } from '@/api/market'
import { newsApi } from '@/api/news'
import { aiApi } from '@/api/ai'
import { watchlistApi } from '@/api/watchlist'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import { ElMessage } from 'element-plus'
import { Refresh, Plus, MagicStick, Search } from '@element-plus/icons-vue'
import { fmtDateTime } from '@/utils/format'

use([LineChart, GridComponent, TooltipComponent, CanvasRenderer])

interface NewsRecord {
  title: string
  source?: string
  publish_date?: string
  datetime?: string
  date?: string
  url?: string
  summary?: string
  content?: string
}

interface SignalItem {
  code: string
  name?: string
  type: 'buy' | 'sell' | 'neutral'
  strength?: string
  price?: number
  time?: string
  reasons: string[]
}

interface WatchlistItem {
  code: string
  name: string
}

const activeTab = ref('indices')
const indices = ref<MarketIndex[]>([])
const quotes = ref<StockQuote[]>([])
const watchlistCodes = ref<string[]>([])
const indicesLoading = ref(false)
const quotesLoading = ref(false)
const chartVisible = ref(false)
const chartTitle = ref('')
const chartData = ref<MinuteBar[]>([])
const updateTime = ref('--')
const addCode = ref('')

// News tab
const newsLoading = ref(false)
const newsList = ref<NewsRecord[]>([])
const newsCodeFilter = ref('')

// AI Analysis tab
const aiLoading = ref(false)
const aiCode = ref('')
const aiResult = ref<MarketAIResult | null>(null)
const watchlistForAI = ref<WatchlistItem[]>([])

interface MarketAIResult {
  name?: string
  code: string
  signal?: string
  composite_score?: number
  recommendation?: string
  stop_loss?: number
  target_price?: number
  reasons?: string[]
  risk_factors?: string[]
  [key: string]: unknown
}

// Signal detection tab
const signalLoading = ref(false)
const signalHistoryLoading = ref(false)
const signalCode = ref('')
const signalSubTab = ref('current')
const latestSignal = ref<SignalItem | null>(null)
const signalHistory = ref<SignalItem[]>([])
const watchlistForSignal = ref<WatchlistItem[]>([])

let refreshTimer: ReturnType<typeof setInterval>

function getColorClass(change?: number): string {
  if (change === undefined || change === null) return ''
  return change > 0 ? 'rise' : change < 0 ? 'fall' : 'flat'
}

function getTextClass(change?: number): string {
  if (change === undefined || change === null) return 'flat-text'
  return change > 0 ? 'rise-text' : change < 0 ? 'fall-text' : 'flat-text'
}

function fmtPrice(v?: number | null): string {
  if (v === undefined || v === null) return '--'
  return v.toFixed(2)
}

function fmtChange(v?: number | null): string {
  if (v === undefined || v === null) return '--'
  return (v >= 0 ? '+' : '') + v.toFixed(2) + '%'
}

function fmtAmount(v?: number | null): string {
  if (v === undefined || v === null) return '--'
  if (v >= 1e8) return (v / 1e8).toFixed(2) + '亿'
  if (v >= 1e4) return (v / 1e4).toFixed(2) + '万'
  return v.toFixed(0)
}

function fmtTurnover(v?: number | null): string {
  if (v === undefined || v === null) return '--'
  return v.toFixed(2) + '%'
}

function formatPrice(v?: number | null): string {
  if (v === undefined || v === null) return '--'
  return '¥' + v.toFixed(2)
}

function aiSignalType(signal?: string): string {
  if (!signal) return 'info'
  const s = signal.toLowerCase()
  if (s.includes('买入') || s.includes('强烈买入') || s.includes('buy')) return 'success'
  if (s.includes('卖出') || s.includes('强烈卖出') || s.includes('sell')) return 'danger'
  return 'info'
}

async function loadNews() {
  newsLoading.value = true
  try {
    const res = await newsApi.latest({ code: newsCodeFilter.value || undefined, limit: 50 })
    newsList.value = res.data?.data || []
  } catch {
    ElMessage.error('获取新闻列表失败')
  } finally {
    newsLoading.value = false
  }
}

async function analyzeNews(row: NewsRecord) {
  try {
    ElMessage.info('正在分析新闻...')
    const res = await aiApi.analyzeNews({ news: row as unknown as Record<string, unknown> })
    if (res.data?.data) {
      const analysis = res.data.data
      ElMessage({
        type: analysis.signal?.toLowerCase().includes('buy') || analysis.signal?.toLowerCase().includes('利好') ? 'success' : 'warning',
        message: `AI分析结果: ${analysis.signal || '观望'}\n${analysis.summary || ''}`,
        duration: 5000
      })
    }
  } catch {
    ElMessage.error('新闻分析失败')
  }
}

async function loadWatchlistForAI() {
  try {
    const res = await watchlistApi.list()
    watchlistForAI.value = res.data?.data || []
  } catch {
    watchlistForAI.value = []
  }
}

async function loadWatchlistForSignal() {
  try {
    const res = await watchlistApi.list()
    watchlistForSignal.value = res.data?.data || []
  } catch {
    watchlistForSignal.value = []
  }
}

async function runAIAnalysis() {
  if (!aiCode.value) return
  aiLoading.value = true
  aiResult.value = null
  try {
    const res = await aiApi.analyzeStock({ code: aiCode.value })
    aiResult.value = res.data?.data || null
    if (!aiResult.value) {
      ElMessage.warning('未获取到分析结果')
    }
  } catch {
    ElMessage.error('AI分析失败')
  } finally {
    aiLoading.value = false
  }
}

async function detectSignals() {
  if (!signalCode.value) return
  signalLoading.value = true
  latestSignal.value = null
  try {
    const res = await marketApi.detectSignals(signalCode.value)
    latestSignal.value = res.data?.data || null
    if (!latestSignal.value) {
      ElMessage.warning('未检测到信号')
    }
  } catch {
    ElMessage.error('信号检测失败')
  } finally {
    signalLoading.value = false
  }
}

async function loadSignalHistory() {
  signalHistoryLoading.value = true
  try {
    const res = await marketApi.getSignalHistory(signalCode.value || undefined)
    signalHistory.value = res.data?.data || []
  } catch {
    ElMessage.error('获取信号历史失败')
  } finally {
    signalHistoryLoading.value = false
  }
}

async function loadIndices() {
  indicesLoading.value = true
  try {
    const res = await marketApi.getIndices()
    indices.value = res.data?.data || []
    updateTime.value = new Date().toLocaleTimeString()
  } catch {
    ElMessage.error('获取大盘数据失败')
  } finally {
    indicesLoading.value = false
  }
}

async function loadQuotes() {
  if (watchlistCodes.value.length === 0) return
  quotesLoading.value = true
  try {
    const res = await marketApi.getRealtimeQuotes(watchlistCodes.value)
    quotes.value = res.data?.data || []
    updateTime.value = new Date().toLocaleTimeString()
  } catch {
    ElMessage.error('获取行情数据失败')
  } finally {
    quotesLoading.value = false
  }
}

function handleAddStock() {
  const code = addCode.value.trim().toUpperCase()
  if (!code) return
  if (watchlistCodes.value.includes(code)) {
    ElMessage.warning('已在列表中')
    return
  }
  watchlistCodes.value.push(code)
  localStorage.setItem('market_watchlist', JSON.stringify(watchlistCodes.value))
  addCode.value = ''
  loadQuotes()
}

function removeStock(code: string) {
  watchlistCodes.value = watchlistCodes.value.filter(c => c !== code)
  quotes.value = quotes.value.filter(q => q.code !== code)
  localStorage.setItem('market_watchlist', JSON.stringify(watchlistCodes.value))
}

function clearAll() {
  watchlistCodes.value = []
  quotes.value = []
  localStorage.removeItem('market_watchlist')
}

async function showMiniChart(row: StockQuote) {
  chartTitle.value = `${row.name} 分时图`
  chartVisible.value = true
  try {
    const res = await marketApi.getMinuteKline(row.code)
    chartData.value = res.data?.data || []
  } catch {
    chartData.value = []
  }
}

const chartOption = ref({})

watch([chartVisible, chartData], ([visible, data]) => {
  if (visible && data.length > 0) {
    const prices = data.map(d => d.price)
    const min = Math.min(...prices)
    const max = Math.max(...prices)
    const pad = (max - min) * 0.1 || 1
    chartOption.value = {
      grid: { top: 20, right: 60, bottom: 30, left: 60 },
      xAxis: { type: 'category', data: data.map(d => d.time.slice(-8)), axisLabel: { color: '#909399', fontSize: 10 } },
      yAxis: { type: 'value', min: min - pad, max: max + pad, axisLabel: { color: '#909399', fontSize: 10 } },
      tooltip: { trigger: 'axis' },
      series: [{ type: 'line', data, smooth: true, symbol: 'none', lineStyle: { color: '#409eff', width: 2 } }]
    }
  }
})

watch(activeTab, (tab) => {
  if (tab === 'news') loadNews()
  else if (tab === 'ai-analysis') loadWatchlistForAI()
  else if (tab === 'signals') loadWatchlistForSignal()
})

onMounted(() => {
  const saved = localStorage.getItem('market_watchlist')
  if (saved) {
    try {
      watchlistCodes.value = JSON.parse(saved)
    } catch {}
  }
  loadIndices()
  if (watchlistCodes.value.length > 0) loadQuotes()
  refreshTimer = setInterval(() => {
    if (activeTab.value === 'indices') loadIndices()
    else if (watchlistCodes.value.length > 0) loadQuotes()
  }, 60000)
})

onUnmounted(() => clearInterval(refreshTimer))
</script>

<style scoped>
.market-view {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.market-tabs :deep(.el-tabs__header) {
  margin-bottom: 12px;
}
.indices-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 12px;
  margin-bottom: 16px;
}
.index-card {
  background: #1f1f1f;
  border: 1px solid #2c2c2c;
  border-radius: 6px;
  padding: 16px;
}
.index-name {
  font-size: 13px;
  color: #909399;
  margin-bottom: 8px;
}
.index-price {
  font-size: 24px;
  font-weight: bold;
  margin-bottom: 4px;
}
.index-change {
  display: flex;
  justify-content: space-between;
  font-size: 13px;
}
.change-amount {
  font-size: 11px;
  opacity: 0.7;
}
.refresh-bar {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
}
.update-time {
  font-size: 12px;
  color: #909399;
}
.auto-tip {
  font-size: 11px;
  color: #606266;
}
.watchlist-toolbar {
  display: flex;
  gap: 8px;
  margin-bottom: 12px;
  align-items: center;
}
.quotes-table {
  background: #1f1f1f;
  border-radius: 6px;
}
.quotes-table :deep(.el-table__header th) {
  background: #1f1f1f;
  color: #909399;
}
.rise-text, .rise { color: #ef5350; }
.fall-text, .fall { color: #26a69a; }
.flat-text, .flat { color: #909399; }
.news-toolbar, .ai-toolbar, .signals-toolbar {
  display: flex;
  gap: 8px;
  margin-bottom: 12px;
  align-items: center;
}
.news-table, .signals-table {
  background: #1f1f1f;
  border-radius: 6px;
}
.news-table :deep(.el-table__header th),
.signals-table :deep(.el-table__header th) {
  background: #1f1f1f;
  color: #909399;
}
.section-card {
  margin-top: 12px;
  background: #1f1f1f;
  border-color: #2c2c2c;
}
.section-card :deep(.el-card__header) {
  background: #252525;
  border-color: #2c2c2c;
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.ai-result-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.ai-reasons {
  margin-top: 12px;
  padding: 12px;
  background: #252525;
  border-radius: 4px;
}
.reason-title {
  font-weight: 500;
  margin-bottom: 8px;
}
.ai-reasons ul {
  margin: 0;
  padding-left: 20px;
  color: #909399;
}
.ai-reasons li {
  margin-bottom: 4px;
}
.signal-detail {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.signal-info {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 8px;
}
.signal-item {
  display: flex;
  gap: 8px;
}
.signal-item .label {
  color: #909399;
}
.signal-reasons {
  margin-top: 12px;
  padding: 12px;
  background: #252525;
  border-radius: 4px;
}
.signal-reasons ul {
  margin: 0;
  padding-left: 20px;
  color: #909399;
}
.signal-sub-tabs {
  margin-top: 12px;
}
.text-rise { color: #ef5350; }
.text-fall { color: #26a69a; }
.price-text { font-weight: 500; }
.stop-loss { color: #26a69a; }
.target-price { color: #ef5350; }
@media (max-width: 768px) {
  .indices-grid { grid-template-columns: repeat(2, 1fr); }
}
</style>