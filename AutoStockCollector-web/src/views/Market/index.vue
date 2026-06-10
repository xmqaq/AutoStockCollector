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
          <span class="valuation-status" v-if="valuationTime">
            <el-tag :type="valuationFresh ? 'success' : 'warning'" size="small" effect="plain">
              {{ valuationFresh ? '估值已同步' : '估值待刷新' }}
            </el-tag>
            <span class="valuation-time">{{ valuationTime }}</span>
          </span>
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
          <el-table-column label="PE" width="80" align="right">
            <template #default="{ row }">{{ fmtVal(row.pe_dynamic) }}</template>
          </el-table-column>
          <el-table-column label="PB" width="80" align="right">
            <template #default="{ row }">{{ fmtVal(row.pb) }}</template>
          </el-table-column>
          <el-table-column label="ROE" width="80" align="right">
            <template #default="{ row }">{{ fmtPct(row.roe) }}</template>
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

    </el-tabs>

    <el-dialog v-model="chartVisible" :title="chartTitle" width="600px">
      <v-chart :option="chartOption" style="height:400px" autoresize />
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch } from 'vue'
import { marketApi, type MarketIndex, type StockQuote, type MinuteBar } from '@/api/market'
import { watchlistApi } from '@/api/watchlist'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import { ElMessage } from 'element-plus'
import { Refresh, Plus } from '@element-plus/icons-vue'

use([LineChart, GridComponent, TooltipComponent, CanvasRenderer])

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
const valuationTime = ref('')
const valuationFresh = ref(false)

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

function fmtVal(v?: number | null): string {
  if (v === undefined || v === null) return '--'
  return v.toFixed(2)
}

function fmtPct(v?: number | null): string {
  if (v === undefined || v === null) return '--'
  return v.toFixed(2) + '%'
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

async function loadWatchlistCodes() {
  try {
    const res = await watchlistApi.list()
    watchlistCodes.value = (res.data?.data || []).map((s: { code: string }) => s.code)
  } catch {
    watchlistCodes.value = []
  }
}

async function loadQuotes() {
  if (watchlistCodes.value.length === 0) return
  quotesLoading.value = true
  try {
    const [quoteRes, valRes] = await Promise.all([
      marketApi.getRealtimeQuotes(watchlistCodes.value),
      marketApi.getValuationBatch(watchlistCodes.value).catch(() => ({ data: { data: [] } })),
    ])
    const quoteList = quoteRes.data?.data || []
    const valList = valRes.data?.data || []
    const valMap: Record<string, any> = {}
    let latestValTime = ''
    for (const v of valList) {
      if (v.code) valMap[v.code] = v
      if (v.updated_at && v.updated_at > latestValTime) latestValTime = v.updated_at
    }
    if (latestValTime) {
      const d = new Date(latestValTime)
      valuationTime.value = d.toLocaleTimeString()
      valuationFresh.value = (Date.now() - d.getTime()) < 10 * 60 * 1000
    }
    quotes.value = quoteList.map((q: any) => {
      const val = valMap[q.code]
      if (val) {
        q.pe_dynamic = val.pe_dynamic
        q.pb = val.pb
        q.roe = val.roe
      }
      return q
    })
    updateTime.value = new Date().toLocaleTimeString()
  } catch {
    ElMessage.error('获取行情数据失败')
  } finally {
    quotesLoading.value = false
  }
}

async function handleAddStock() {
  const code = addCode.value.trim()
  if (!code) return
  try {
    await watchlistApi.addWatchlist({ code })
    addCode.value = ''
    await loadWatchlistCodes()
    loadQuotes()
  } catch {
    ElMessage.error('添加失败，请检查股票代码')
  }
}

async function removeStock(code: string) {
  try {
    await watchlistApi.removeWatchlist(code)
    watchlistCodes.value = watchlistCodes.value.filter(c => c !== code)
    quotes.value = quotes.value.filter(q => q.code !== code)
  } catch {
    ElMessage.error('删除失败')
  }
}

async function clearAll() {
  try {
    for (const code of [...watchlistCodes.value]) {
      await watchlistApi.removeWatchlist(code)
    }
    watchlistCodes.value = []
    quotes.value = []
  } catch {
    ElMessage.error('清空失败')
  }
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

onMounted(async () => {
  await loadWatchlistCodes()
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
.valuation-status {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  margin-left: auto;
}
.valuation-time {
  font-size: 11px;
  color: #909399;
}
@media (max-width: 768px) {
  .indices-grid { grid-template-columns: repeat(2, 1fr); }
}
</style>