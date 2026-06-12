<template>
  <div class="stock-detail">
    <el-card shadow="never" class="section-card">
      <div class="search-bar">
        <el-select
          v-model="currentCode"
          placeholder="选择自选股"
          filterable
          size="large"
          style="width:220px"
          @change="loadStock(currentCode)"
        >
          <el-option
            v-for="stock in watchlist"
            :key="stock.code"
            :label="`${stock.code} ${stock.name}`"
            :value="stock.code"
          />
        </el-select>
        <span class="divider">|</span>
        <StockSearch v-model="searchCode" @search="loadStock" />
      </div>
    </el-card>

    <div v-if="!currentCode" class="empty-hint">
      <el-empty description="请从上方选择股票" />
    </div>

    <template v-else>
      <el-card shadow="never" class="section-card" v-loading="infoLoading">
        <template #header>
          <div class="card-header">
            <span>基础信息</span>
            <el-tag v-if="stockInfo?.name" type="info">{{ stockInfo.name }}</el-tag>
          </div>
        </template>
        <div v-if="stockInfo" class="info-grid">
          <div class="info-item">
            <span class="info-label">代码</span>
            <span class="info-value num">{{ stockInfo.code }}</span>
          </div>
          <div class="info-item">
            <span class="info-label">行业</span>
            <span class="info-value">{{ stockInfo.industry || '--' }}</span>
          </div>
          <div class="info-item">
            <span class="info-label">地区</span>
            <span class="info-value">{{ stockInfo.area || '--' }}</span>
          </div>
          <div class="info-item">
            <span class="info-label">市盈率PE(TTM)</span>
            <span class="info-value num">{{ fmtNumber(stockInfo.pe) }}</span>
          </div>
          <div class="info-item">
            <span class="info-label">市盈率PE(静)</span>
            <span class="info-value num">{{ fmtNumber(stockInfo.pe_static) || '--' }}</span>
          </div>
          <div class="info-item">
            <span class="info-label">市净率PB</span>
            <span class="info-value num">{{ fmtNumber(stockInfo.pb) }}</span>
          </div>
          <div class="info-item">
            <span class="info-label">总市值</span>
            <span class="info-value num">{{ fmtAmount(stockInfo.total_mv || 0) }}</span>
          </div>
          <div class="info-item">
            <span class="info-label">上市日期</span>
            <span class="info-value">{{ stockInfo.list_date || '--' }}</span>
          </div>
        </div>
        <el-empty v-else-if="!infoLoading" description="暂无基础信息" :image-size="60" />
      </el-card>

      <el-card shadow="never" class="section-card" v-loading="klineLoading">
        <template #header>
          <div class="card-header">
            <span>K线图</span>
            <div class="date-filter">
              <el-date-picker
                v-model="klineDateRange"
                type="daterange"
                range-separator="至"
                start-placeholder="开始日期"
                end-placeholder="结束日期"
                format="YYYY年MM月DD日"
                value-format="YYYY-MM-DD"
                size="small"
                style="width:300px"
                :shortcuts="dateShortcuts"
                :clearable="false"
                @change="loadKline"
              />
            </div>
          </div>
        </template>
        <KlineChart 
          v-if="klineData.length > 0" 
          :data="klineData" 
          :annotations="aiAnnotations"
          :support-levels="aiSupportLevels"
          :resistance-levels="aiResistanceLevels"
          chart-height="450px" 
        />
        <el-empty v-else-if="!klineLoading" :description="emptyKlineHint" :image-size="60" />
      </el-card>

      <el-card shadow="never" class="section-card" v-loading="financialLoading">
        <template #header><span>财务数据</span></template>
        <el-empty v-if="financialList.length === 0 && !financialLoading" description="暂无财务数据" :image-size="60" />
        <el-table v-else :data="financialList" stripe size="small">
          <el-table-column prop="report_date" label="报告期" width="120" />
          <el-table-column label="净利润" width="120" class-name="num">
            <template #default="{ row }">{{ fmtAmount(row.net_profit) }}</template>
          </el-table-column>
          <el-table-column label="营业收入" width="120" class-name="num">
            <template #default="{ row }">{{ fmtAmount(row.revenue) }}</template>
          </el-table-column>
          <el-table-column label="ROE" width="100" class-name="num">
            <template #default="{ row }">{{ fmtNumber(row.roe) }}%</template>
          </el-table-column>
          <el-table-column label="ROA" width="100" class-name="num">
            <template #default="{ row }">{{ fmtNumber(row.roa) }}%</template>
          </el-table-column>
          <el-table-column label="EPS" width="100" class-name="num">
            <template #default="{ row }">{{ fmtNumber(row.eps) }}</template>
          </el-table-column>
          <el-table-column label="BPS" width="100" class-name="num">
            <template #default="{ row }">{{ fmtNumber(row.bps) }}</template>
          </el-table-column>
        </el-table>
      </el-card>

      <el-card shadow="never" class="section-card" v-loading="newsLoading">
        <template #header><span>相关新闻</span></template>
        <div v-if="newsList.length === 0 && !newsLoading" class="empty-state">
          <el-empty description="暂无相关新闻" :image-size="60" />
        </div>
        <div v-else class="news-list">
          <div v-for="(news, idx) in newsList" :key="idx" class="news-item">
            <div class="news-title">{{ news.title }}</div>
            <div class="news-meta">
              <span>{{ fmtDateTime(news.publish_date || news.datetime || news.date) }}</span>
              <span v-if="news.source" class="news-source">{{ news.source }}</span>
            </div>
          </div>
        </div>
      </el-card>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import StockSearch from '@/components/StockSearch/index.vue'
import KlineChart from '@/components/KlineChart/index.vue'
import { stockApi } from '@/api/stock'
import { klineApi } from '@/api/kline'
import { financialApi } from '@/api/financial'
import { newsApi } from '@/api/news'
import { watchlistApi } from '@/api/watchlist'
import { aiApi } from '@/api/ai'
import { fmtAmount, fmtDateTime, fmtNumber } from '@/utils/format'
import type { StockInfo, KlineRecord, FinancialRecord, NewsRecord, WatchlistItem, AIAnnotation, PriceLevel } from '@/types'
import dayjs from 'dayjs'

const currentCode = ref('')
const searchCode = ref('')
const watchlist = ref<WatchlistItem[]>([])

const infoLoading = ref(false)
const klineLoading = ref(false)
const financialLoading = ref(false)
const newsLoading = ref(false)

const stockInfo = ref<StockInfo | null>(null)
const klineData = ref<KlineRecord[]>([])
const financialList = ref<FinancialRecord[]>([])
const newsList = ref<NewsRecord[]>([])
const klineDateRange = ref<[string, string]>([
  dayjs().subtract(1, 'year').format('YYYY-MM-DD'),
  dayjs().format('YYYY-MM-DD'),
])

const aiAnnotations = ref<AIAnnotation[]>([])
const aiSupportLevels = ref<PriceLevel[]>([])
const aiResistanceLevels = ref<PriceLevel[]>([])
const aiLoading = ref(false)

const klineDataRange = ref<{ from: string | null; to: string | null }>({ from: null, to: null })

const emptyKlineHint = computed(() => {
  const range = klineDataRange.value
  if (range.from && range.to) {
    return `当前所选区间无 K 线数据（数据库可用区间：${range.from} ~ ${range.to}）`
  }
  return '暂无 K 线数据'
})

function shortcut(daysOrMonths: number, unit: 'day' | 'month' | 'year'): [Date, Date] {
  const end = new Date()
  const start = new Date()
  if (unit === 'day') start.setDate(start.getDate() - daysOrMonths)
  if (unit === 'month') start.setMonth(start.getMonth() - daysOrMonths)
  if (unit === 'year') start.setFullYear(start.getFullYear() - daysOrMonths)
  return [start, end]
}

const dateShortcuts = [
  { text: '近 1 月', value: () => shortcut(1, 'month') },
  { text: '近 3 月', value: () => shortcut(3, 'month') },
  { text: '近 6 月', value: () => shortcut(6, 'month') },
  { text: '近 1 年', value: () => shortcut(1, 'year') },
  { text: '近 3 年', value: () => shortcut(3, 'year') },
]

async function loadWatchlist() {
  try {
    const res = await watchlistApi.getWatchlist()
    watchlist.value = res.data?.data || res.data || []
  } catch {
    watchlist.value = []
  }
}

async function loadStock(code: string) {
  if (!code) return
  currentCode.value = code
  searchCode.value = ''
  aiAnnotations.value = []
  aiSupportLevels.value = []
  aiResistanceLevels.value = []
  await Promise.all([
    loadInfo(),
    loadKline(),
    loadFinancial(),
    loadNews(),
    loadAIAnnotations(),
  ])
}

async function loadInfo() {
  infoLoading.value = true
  try {
    const res = await stockApi.getStockInfo(currentCode.value)
    const raw = res.data?.data || res.data || null
    if (raw) {
      stockInfo.value = {
        ...raw,
        code: raw.code || currentCode.value,
        name: raw.name || raw['A股简称'] || raw['公司名称'] || '--',
        industry: raw.industry || raw['所属行业'] || '--',
        area: raw.area || raw['注册地址'] || raw['办公地址'] || '--',
        list_date: raw.list_date || raw['上市日期'] || '--',
        market: raw.market || raw['所属市场'] || '--',
        pe: raw.pe ?? null,
        pb: raw.pb ?? null,
        total_mv: raw.total_mv ?? null,
      } as StockInfo
    } else {
      stockInfo.value = null
    }
  } catch {
    stockInfo.value = null
  } finally {
    infoLoading.value = false
  }
}

async function loadKline() {
  klineLoading.value = true
  try {
    const params: { start_date?: string; end_date?: string } = {}
    if (klineDateRange.value) {
      params.start_date = klineDateRange.value[0]
      params.end_date = klineDateRange.value[1]
    }
    const res = await klineApi.getKline(currentCode.value, params)
    klineData.value = res.data?.data || res.data || []
    const dates = (
      klineData.value.length > 0
        ? klineData.value
        : ((await klineApi.getKline(currentCode.value)).data?.data || [])
    ).map((r: { date: string }) => r.date).filter(Boolean).sort()
    klineDataRange.value = dates.length > 0
      ? { from: dates[0], to: dates[dates.length - 1] }
      : { from: null, to: null }
  } catch {
    klineData.value = []
  } finally {
    klineLoading.value = false
  }
}

async function loadFinancial() {
  financialLoading.value = true
  try {
    const res = await financialApi.getFinancial(currentCode.value)
    const data = res.data?.data || res.data || []
    financialList.value = Array.isArray(data) ? data : [data]
  } catch {
    financialList.value = []
  } finally {
    financialLoading.value = false
  }
}

async function loadNews() {
  newsLoading.value = true
  try {
    const res = await newsApi.getNews({ code: currentCode.value, limit: 10 })
    const data = res.data?.data || res.data || []
    newsList.value = Array.isArray(data) ? data : []
  } catch {
    newsList.value = []
  } finally {
    newsLoading.value = false
  }
}

async function loadAIAnnotations() {
  aiLoading.value = true
  try {
    const res = await aiApi.analyzeStock({ code: currentCode.value })
    const data = res.data?.data || res.data
    if (data) {
      if (data.annotations) {
        aiAnnotations.value = data.annotations
      }
      if (data.support_levels) {
        aiSupportLevels.value = data.support_levels.map((p: number) => ({ price: p, type: 'support' as const }))
      }
      if (data.resistance_levels) {
        aiResistanceLevels.value = data.resistance_levels.map((p: number) => ({ price: p, type: 'resistance' as const }))
      }
    }
  } catch {
    aiAnnotations.value = []
    aiSupportLevels.value = []
    aiResistanceLevels.value = []
  } finally {
    aiLoading.value = false
  }
}

onMounted(async () => {
  await loadWatchlist()
  if (watchlist.value.length > 0) {
    await loadStock(watchlist.value[0].code)
  }
})
</script>

<style scoped>
.stock-detail {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

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

.search-bar {
  display: flex;
  align-items: center;
  gap: 12px;
}

.divider {
  color: var(--border-heavy);
  font-size: 18px;
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.date-filter {
  display: flex;
  align-items: center;
}

.info-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
}

.info-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.info-label {
  font-size: 12px;
  color: var(--text-faint);
}

.info-value {
  font-size: 14px;
  color: var(--text-primary);
  font-weight: 500;
}

.news-list {
  display: flex;
  flex-direction: column;
}

.news-item {
  padding: 10px 0;
  border-bottom: 1px solid var(--border-color);
}

.news-item:last-child {
  border-bottom: none;
}

.news-title {
  font-size: 13px;
  color: var(--text-primary);
  line-height: 1.4;
  margin-bottom: 4px;
}

.news-meta {
  display: flex;
  gap: 12px;
  font-size: 11px;
  color: var(--text-faint);
}

.news-source {
  color: var(--text-muted);
}

.empty-hint {
  display: flex;
  justify-content: center;
  padding: 60px 0;
}

.empty-state {
  padding: 20px 0;
}
</style>