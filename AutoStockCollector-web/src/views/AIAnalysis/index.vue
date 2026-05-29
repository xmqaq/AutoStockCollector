<template>
  <div class="ai-analysis">
    <el-card shadow="never" class="section-card">
      <div class="search-bar">
        <el-select
          v-model="currentCode"
          placeholder="选择自选股"
          filterable
          size="default"
          style="width:220px"
          @change="handleSelectChange"
        >
          <el-option
            v-for="stock in watchlist"
            :key="stock.code"
            :label="`${stock.code} ${stock.name}`"
            :value="stock.code"
          />
        </el-select>
        <span class="divider">|</span>
        <StockSearch v-model="searchCode" @search="handleSearch" />
        <span class="divider">|</span>
        <el-select v-model="form.type" style="width:140px">
          <el-option label="综合分析" value="comprehensive" />
          <el-option label="技术分析" value="technical" />
          <el-option label="基本面分析" value="fundamental" />
          <el-option label="舆情分析" value="sentiment" />
        </el-select>
        <el-button
          type="primary"
          @click="handleAnalyze"
          :loading="loading"
          :disabled="!form.code"
        >
          开始分析
        </el-button>
      </div>
    </el-card>

    <template v-if="result">
      <el-card shadow="never" class="section-card result-header-card">
        <template #header>
          <div class="result-header">
            <div class="header-left">
              <span class="stock-name">{{ result.name || result.code }}</span>
              <el-tag :type="scoreType(result.composite_score)" size="large" effect="dark">
                综合评分: {{ result.composite_score?.toFixed(1) || '--' }}
              </el-tag>
            </div>
            <div class="header-tags">
              <el-tag :type="recommendTagType(result.recommendation)" size="small">
                {{ result.recommendation }}
              </el-tag>
              <el-tag :type="riskTagType(result.risk_level)" size="small">
                风险: {{ result.risk_level }}
              </el-tag>
            </div>
          </div>
        </template>
        <el-descriptions :column="4" border size="small">
          <el-descriptions-item label="止损位">
            <span class="price-text stop-loss">{{ formatPrice(result.stop_loss) }}</span>
          </el-descriptions-item>
          <el-descriptions-item label="目标价">
            <span class="price-text target-price">{{ formatPrice(result.target_price) }}</span>
          </el-descriptions-item>
          <el-descriptions-item label="支撑位">
            {{ (result.support_levels || []).slice(0, 2).join(', ') || '--' }}
          </el-descriptions-item>
          <el-descriptions-item label="压力位">
            {{ (result.resistance_levels || []).slice(0, 2).join(', ') || '--' }}
          </el-descriptions-item>
        </el-descriptions>
      </el-card>

      <el-card shadow="never" class="section-card score-cards">
        <template #header><span>四维评分</span></template>
        <el-row :gutter="12">
          <el-col :span="6">
            <div class="score-card technical">
              <div class="score-card-header">技术面</div>
              <div class="score-card-value">{{ (result.technical?.trend_strength || 0).toFixed(1) }}</div>
              <div class="score-card-label">{{ result.technical?.trend || '--' }}</div>
              <el-progress
                :percentage="result.technical?.trend_strength || 0"
                :stroke-width="8"
                :show-text="false"
                :color="scoreColor(result.technical?.trend_strength)"
              />
            </div>
          </el-col>
          <el-col :span="6">
            <div class="score-card fundamental">
              <div class="score-card-header">基本面</div>
              <div class="score-card-value">
                {{ (((result.fundamental?.valuation_score || 0) + (result.fundamental?.growth_score || 0)) / 2).toFixed(1) }}
              </div>
              <div class="score-card-label">
                PE: {{ result.fundamental?.pe || '--' }} | ROE: {{ result.fundamental?.roe || '--' }}%
              </div>
              <el-progress
                :percentage="((result.fundamental?.valuation_score || 0) + (result.fundamental?.growth_score || 0)) / 2"
                :stroke-width="8"
                :show-text="false"
                :color="scoreColor(((result.fundamental?.valuation_score || 0) + (result.fundamental?.growth_score || 0)) / 2)"
              />
            </div>
          </el-col>
          <el-col :span="6">
            <div class="score-card sentiment">
              <div class="score-card-header">舆情</div>
              <div class="score-card-value">{{ (result.sentiment?.score || 0).toFixed(1) }}</div>
              <div class="score-card-label">{{ result.sentiment?.sentiment || '--' }}</div>
              <el-progress
                :percentage="result.sentiment?.score || 0"
                :stroke-width="8"
                :show-text="false"
                :color="scoreColor(result.sentiment?.score)"
              />
            </div>
          </el-col>
          <el-col :span="6">
            <div class="score-card flow">
              <div class="score-card-header">资金流</div>
              <div class="score-card-value">{{ (result.fund_flow?.score || 50).toFixed(1) }}</div>
              <div class="score-card-label">{{ formatMoney(result.fund_flow?.main_net_inflow || 0) }}</div>
              <el-progress
                :percentage="result.fund_flow?.score || 50"
                :stroke-width="8"
                :show-text="false"
                :color="scoreColor(result.fund_flow?.score)"
              />
            </div>
          </el-col>
        </el-row>
      </el-card>

      <el-card shadow="never" class="section-card">
        <template #header><span>分析详情</span></template>
        <el-row :gutter="12">
          <el-col :span="12">
            <div class="detail-section">
              <div class="detail-title">推荐理由</div>
              <ul class="reason-list">
                <li v-for="(reason, idx) in (result.reasons || [])" :key="idx" class="reason-item">
                  {{ reason }}
                </li>
              </ul>
            </div>
          </el-col>
          <el-col :span="12">
            <div class="detail-section">
              <div class="detail-title risk-title">风险因素</div>
              <ul class="risk-list">
                <li v-for="(risk, idx) in (result.risk_factors || [])" :key="idx" class="risk-item">
                  {{ risk }}
                </li>
              </ul>
            </div>
          </el-col>
        </el-row>
      </el-card>

      <el-card shadow="never" class="section-card">
        <template #header>
          <span>技术指标详情</span>
        </template>
        <el-descriptions :column="3" border size="small">
          <el-descriptions-item label="当前价">{{ result.technical?.current_price || '--' }}</el-descriptions-item>
          <el-descriptions-item label="MA5">{{ result.technical?.ma5?.toFixed(2) || '--' }}</el-descriptions-item>
          <el-descriptions-item label="MA20">{{ result.technical?.ma20?.toFixed(2) || '--' }}</el-descriptions-item>
          <el-descriptions-item label="涨跌幅">{{ (result.technical?.change_pct || 0).toFixed(2) }}%</el-descriptions-item>
          <el-descriptions-item label="RSI">{{ (result.technical?.rsi || 50).toFixed(1) }}</el-descriptions-item>
          <el-descriptions-item label="成交量比">{{ (result.technical?.volume_ratio || 1).toFixed(2) }}倍</el-descriptions-item>
        </el-descriptions>
      </el-card>

      <el-card shadow="never" class="section-card" v-if="(result.sentiment?.key_events?.length || 0) > 0">
        <template #header><span>舆情事件</span></template>
        <div class="events-list">
          <div
            v-for="(event, idx) in (result.sentiment?.key_events || [])"
            :key="idx"
            class="event-item"
          >
            <span class="event-text">{{ event }}</span>
          </div>
        </div>
      </el-card>

      <el-card shadow="never" class="section-card">
        <template #header>
          <span>原始数据</span>
          <el-button size="small" @click="showRaw = !showRaw">
            {{ showRaw ? '隐藏' : '显示' }}
          </el-button>
        </template>
        <div v-if="showRaw" class="raw-result">
          <pre>{{ JSON.stringify(result, null, 2) }}</pre>
        </div>
      </el-card>
    </template>

    <!-- Intro panel (shown only before first analysis) -->
    <el-card v-if="!result && !loading" shadow="never" class="section-card intro-card">
      <template #header><span>支持的分析模式</span></template>
      <div class="intro-grid">
        <div
          v-for="t in analysisTypes"
          :key="t.value"
          class="intro-item"
          :class="{ 'intro-active': form.type === t.value }"
          @click="form.type = t.value"
        >
          <div class="intro-badge">{{ t.badge }}</div>
          <div class="intro-name">{{ t.label }}</div>
          <div class="intro-desc">{{ t.desc }}</div>
        </div>
      </div>
    </el-card>

    <el-card v-if="history.length > 0" shadow="never" class="section-card">
      <template #header><span>分析历史（本次会话）</span></template>
      <div class="history-list">
        <div
          v-for="(item, idx) in history"
          :key="idx"
          class="history-item"
          @click="selectHistory(item)"
        >
          <span class="history-code">{{ item.code }}</span>
          <el-tag size="small" type="info">{{ analysisTypeLabel(item.analysis_type || '') }}</el-tag>
          <span v-if="item.composite_score !== undefined" class="history-score">
            评分: {{ item.composite_score?.toFixed(1) }}
          </span>
        </div>
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { aiApi } from '@/api/ai'
import { watchlistApi } from '@/api/watchlist'
import { useAIStore } from '@/stores/collectStore'
import StockSearch from '@/components/StockSearch/index.vue'
import { ElMessage } from 'element-plus'
import type { WatchlistItem } from '@/types'

const aiStore = useAIStore()
const loading = ref(false)
const result = ref<AIModelResult | null>(null)
const showRaw = ref(false)
const history = ref<AIModelResult[]>([])
const watchlist = ref<WatchlistItem[]>([])

interface AIModelResult {
  name?: string
  code: string
  composite_score?: number
  recommendation?: string
  risk_level?: string
  stop_loss?: number
  target_price?: number
  support_levels?: number[]
  resistance_levels?: number[]
  analysis_type?: string
  technical?: {
    trend_strength?: number
    trend?: string
    current_price?: number
    ma5?: number
    ma20?: number
    change_pct?: number
    rsi?: number
    volume_ratio?: number
  }
  fundamental?: {
    valuation_score?: number
    growth_score?: number
    pe?: number
    roe?: number
  }
  sentiment?: {
    score?: number
    sentiment?: string
    key_events?: string[]
  }
  fund_flow?: {
    score?: number
    main_net_inflow?: number
  }
  reasons?: string[]
  risk_factors?: string[]
  [key: string]: unknown
}

const currentCode = ref('')
const searchCode = ref('')

const form = ref({
  code: '',
  type: 'comprehensive',
})

const typeLabels: Record<string, string> = {
  comprehensive: '综合分析',
  technical: '技术分析',
  fundamental: '基本面分析',
  sentiment: '舆情分析',
}

const analysisTypes = [
  { value: 'comprehensive', label: '综合分析', badge: '综', desc: '全面评估技术面、基本面及市场情绪，给出综合投资建议' },
  { value: 'technical', label: '技术分析', badge: '技', desc: '基于K线、均线、MACD、RSI等技术指标，判断价格趋势与买卖时机' },
  { value: 'fundamental', label: '基本面', badge: '基', desc: '分析财务数据、估值指标、行业地位，评估公司内在价值' },
  { value: 'sentiment', label: '情绪分析', badge: '情', desc: '基于新闻舆情、市场热度、资金流向，判断市场情绪与短期走势' },
  { value: 'risk', label: '风险评估', badge: '险', desc: '评估持仓风险等级、波动率及市场系统性风险，辅助控仓决策' },
]

function analysisTypeLabel(type: string): string {
  return typeLabels[type] || type
}

function scoreType(score: number | string | undefined): '' | 'success' | 'warning' | 'danger' | 'info' {
  const s = Number(score) || 0
  if (s >= 70) return 'success'
  if (s >= 50) return 'warning'
  return 'danger'
}

function recommendTagType(rec: string | undefined): string {
  if (!rec) return 'info'
  if (rec.includes('推荐') || rec.includes('买入')) return 'success'
  if (rec.includes('谨慎')) return 'warning'
  if (rec.includes('回避')) return 'danger'
  return 'info'
}

function riskTagType(risk: string | undefined): string {
  if (risk === '低') return 'success'
  if (risk === '中') return 'warning'
  return 'danger'
}

function scoreColor(score: number | undefined): string {
  const s = score || 0
  if (s >= 75) return '#67c23a'
  if (s >= 60) return '#409eff'
  if (s >= 50) return '#e6a23c'
  return '#f56c6c'
}

function formatPrice(price: number | undefined): string {
  if (!price || price <= 0) return '--'
  return price.toFixed(2)
}

function formatMoney(amount: number): string {
  if (Math.abs(amount) >= 1e8) {
    return (amount / 1e8).toFixed(2) + '亿'
  } else if (Math.abs(amount) >= 1e4) {
    return (amount / 1e4).toFixed(2) + '万'
  }
  return amount.toFixed(0)
}

function handleSelectChange(code: string) {
  if (code) {
    form.value.code = code
    searchCode.value = ''
  }
}

function handleSearch(code: string) {
  if (code) {
    currentCode.value = ''
    form.value.code = code
  }
}

async function loadWatchlist() {
  try {
    const res = await watchlistApi.getWatchlist()
    watchlist.value = res.data?.data || res.data || []
    if (watchlist.value.length > 0 && !form.value.code) {
      form.value.code = watchlist.value[0].code
      currentCode.value = watchlist.value[0].code
    }
  } catch {
    watchlist.value = []
  }
}

async function handleAnalyze() {
  if (!form.value.code) {
    ElMessage.warning('请输入股票代码')
    return
  }

  loading.value = true
  try {
    const res = await aiApi.analyze({ code: form.value.code, type: form.value.type })
    const data = res.data?.result || res.data?.data || res.data
    result.value = data || {}
    history.value.unshift(data)
    if (history.value.length > 10) history.value.pop()
  } catch {
    result.value = null
  } finally {
    loading.value = false
  }
}

function selectHistory(item: AIModelResult) {
  result.value = item
}

onMounted(() => {
  loadWatchlist()
})
</script>

<style scoped>
.ai-analysis {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

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

.search-bar {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.divider {
  color: #444;
  font-size: 18px;
}

.result-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.stock-name {
  font-size: 18px;
  font-weight: 600;
  color: #e5eaf3;
}

.header-tags {
  display: flex;
  gap: 8px;
}

.price-text {
  font-weight: 600;
}

.stop-loss {
  color: #f56c6c;
}

.target-price {
  color: #67c23a;
}

.score-cards {
  padding: 16px;
}

.score-card {
  background: #2c2c2c;
  border-radius: 8px;
  padding: 16px;
  text-align: center;
}

.score-card-header {
  font-size: 13px;
  color: #909399;
  margin-bottom: 8px;
}

.score-card-value {
  font-size: 28px;
  font-weight: 700;
  color: #e5eaf3;
  margin-bottom: 4px;
}

.score-card-label {
  font-size: 11px;
  color: #606266;
  margin-bottom: 8px;
}

.detail-section {
  padding: 8px 0;
}

.detail-title {
  font-size: 14px;
  font-weight: 600;
  color: #67c23a;
  margin-bottom: 8px;
}

.risk-title {
  color: #f56c6c;
}

.reason-list, .risk-list {
  list-style: none;
  padding: 0;
  margin: 0;
}

.reason-item, .risk-item {
  font-size: 13px;
  color: #e5eaf3;
  padding: 4px 0;
  border-bottom: 1px solid #2c2c2c;
}

.risk-item {
  color: #f56c6c;
}

.events-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.event-item {
  padding: 8px 12px;
  background: #2c2c2c;
  border-radius: 4px;
  font-size: 13px;
  color: #e5eaf3;
}

.raw-result {
  background: #141414;
  border-radius: 4px;
  padding: 12px;
  max-height: 400px;
  overflow-y: auto;
}

.raw-result pre {
  font-size: 12px;
  color: #a8b5c1;
  margin: 0;
  white-space: pre-wrap;
  word-break: break-all;
}

.intro-grid {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 12px;
}

.intro-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding: 20px 12px;
  border-radius: 8px;
  border: 1px solid #2c2c2c;
  cursor: pointer;
  transition: border-color 0.2s, background 0.2s;
  text-align: center;
}

.intro-item:hover {
  border-color: #409eff;
  background: rgba(64,158,255,0.06);
}

.intro-active {
  border-color: #409eff !important;
  background: rgba(64,158,255,0.10) !important;
}

.intro-badge {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  background: rgba(64,158,255,0.15);
  color: #409eff;
  font-size: 16px;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
}

.intro-name {
  font-size: 13px;
  font-weight: 600;
  color: #e5eaf3;
}

.intro-desc {
  font-size: 12px;
  color: #7a8089;
  line-height: 1.5;
}

.history-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.history-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 12px;
  background: #2c2c2c;
  border-radius: 4px;
  cursor: pointer;
  transition: background 0.2s;
}

.history-item:hover {
  background: #3c3c3c;
}

.history-code {
  font-weight: 600;
  color: #409eff;
  font-size: 13px;
}

.history-score {
  font-size: 12px;
  color: #909399;
}
</style>
