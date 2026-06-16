<template>
  <div class="stock-detail">
    <StockSearchHeader 
      v-model:currentCode="currentCode"
      v-model:searchCode="searchCode"
      :watchlist="watchlist"
      @load-stock="loadStock"
    />

    <div v-if="!currentCode" class="empty-hint">
      <el-empty description="请从上方选择股票" />
    </div>

    <template v-else>
      <StockBasicInfo 
        :info-loading="infoLoading"
        :stock-info="stockInfo"
      />

      <StockKlineCard 
        v-model:klineDateRange="klineDateRange"
        :kline-loading="klineLoading"
        :kline-data="klineData"
        :ai-annotations="aiAnnotations"
        :ai-support-levels="aiSupportLevels"
        :ai-resistance-levels="aiResistanceLevels"
        :empty-kline-hint="emptyKlineHint"
        :date-shortcuts="dateShortcuts"
        @change-date="loadKline"
      />
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import StockSearchHeader from './components/StockSearchHeader.vue'
import StockBasicInfo from './components/StockBasicInfo.vue'
import StockKlineCard from './components/StockKlineCard.vue'
import { stockApi } from '@/api/stock'
import { klineApi } from '@/api/kline'
import { watchlistApi } from '@/api/watchlist'
import { aiApi } from '@/api/ai'
import { fmtAmount, fmtDateTime, fmtNumber } from '@/utils/format'
import type { StockInfo, KlineRecord, WatchlistItem, AIAnnotation, PriceLevel } from '@/types'
import dayjs from 'dayjs'

const currentCode = ref('')
const searchCode = ref('')
const watchlist = ref<WatchlistItem[]>([])

const infoLoading = ref(false)
const klineLoading = ref(false)

const stockInfo = ref<StockInfo | null>(null)
const klineData = ref<KlineRecord[]>([])
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

.empty-hint {
  display: flex;
  justify-content: center;
  padding: 60px 0;
}
</style>