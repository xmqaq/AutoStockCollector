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
        <el-select v-model="form.analysisMode" style="width:140px">
          <el-option label="单股分析" value="single" />
          <el-option label="智能选股" value="picker" />
          <el-option label="批量分析" value="batch" />
        </el-select>
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
          :disabled="!canAnalyze"
        >
          开始分析
        </el-button>
        <el-button
          v-if="form.analysisMode === 'single'"
          @click="showAdvancedPanel = !showAdvancedPanel"
          :type="showAdvancedPanel ? 'primary' : 'default'"
          text
        >
          {{ showAdvancedPanel ? '收起详情' : '展开详情' }}
        </el-button>
      </div>
    </el-card>

    <template v-if="showAnalysisProgress && currentSteps.length > 0">
      <AnalysisProgressPanel
        title="AI分析流程"
        :steps="currentSteps"
        :currentStep="currentRunningStep"
        :currentOperation="currentOperation"
        :total="form.analysisMode === 'batch' ? batchCount : 1"
        :completed="form.analysisMode === 'batch' ? completedCount : 0"
      />
    </template>

    <template v-if="showLLMDialogue && dialogueMessages.length > 0">
      <LLMDialoguePanel :messages="dialogueMessages" />
    </template>

    <template v-if="form.analysisMode === 'single'">
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

        <el-card shadow="never" class="section-card" v-if="showAdvancedPanel">
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
    </template>

    <template v-if="form.analysisMode === 'picker'">
      <div class="picker-section">
        <el-card shadow="never" class="section-card">
          <template #header>
            <div class="header-toolbar">
              <span>AI智能选股</span>
              <div class="strategy-select">
                <el-select v-model="selectedStrategy" size="small" style="width:180px">
                  <el-option
                    v-for="s in strategyList"
                    :key="s.name"
                    :label="s.name"
                    :value="s.name"
                  />
                </el-select>
              </div>
            </div>
          </template>
          <div class="pick-toolbar">
            <el-input-number v-model="pickTopN" :min="5" :max="50" size="default" />
            <span class="toolbar-label">Top N</span>
            <el-input-number v-model="minScore" :min="0" :max="100" :step="5" size="default" />
            <span class="toolbar-label">最低评分</span>
            <el-button type="primary" @click="runSmartPick" :loading="pickerLoading" :icon="Search">
              开始选股
            </el-button>
          </div>
        </el-card>

        <template v-if="pickResults.length > 0">
          <el-card shadow="never" class="section-card">
            <template #header>
              <div class="result-summary">
                <span>选股结果 ({{ pickResults.length }} 只)</span>
                <div class="summary-tags">
                  <el-tag size="small" type="info">
                    平均评分: {{ pickAvgScore }}
                  </el-tag>
                  <el-tag size="small" :type="pickResultType">
                    {{ pickResultTypeLabel }}
                  </el-tag>
                </div>
              </div>
            </template>
            <el-table :data="pickResults" stripe size="small">
              <el-table-column prop="code" label="代码" width="110" fixed>
                <template #default="{ row }">
                  <router-link :to="`/stock-detail?code=${row.code}`" class="stock-link">
                    {{ row.code }}
                  </router-link>
                </template>
              </el-table-column>
              <el-table-column prop="name" label="名称" width="100" show-overflow-tooltip />
              <el-table-column prop="score" label="综合评分" width="100" sortable fixed>
                <template #default="{ row }">
                  <el-tag :type="scoreTagType(row.score)" size="small" effect="dark">
                    {{ row.score?.toFixed(1) }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column prop="recommendation" label="建议" width="100">
                <template #default="{ row }">
                  <el-tag :type="recommendTagType(row.recommendation)" size="small">
                    {{ row.recommendation }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column prop="risk_level" label="风险" width="80">
                <template #default="{ row }">
                  <el-tag :type="riskTagType(row.risk_level)" size="small">
                    {{ row.risk_level }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column label="技术面" width="90">
                <template #default="{ row }">
                  <div class="score-bar">
                    <span class="score-value">{{ (row.technical_score || 0).toFixed(0) }}</span>
                    <el-progress :percentage="row.technical_score || 0" :stroke-width="6" :show-text="false" :color="scoreColor(row.technical_score)" />
                  </div>
                </template>
              </el-table-column>
              <el-table-column label="基本面" width="90">
                <template #default="{ row }">
                  <div class="score-bar">
                    <span class="score-value">{{ (row.fundamental_score || 0).toFixed(0) }}</span>
                    <el-progress :percentage="row.fundamental_score || 0" :stroke-width="6" :show-text="false" :color="scoreColor(row.fundamental_score)" />
                  </div>
                </template>
              </el-table-column>
              <el-table-column label="舆情" width="90">
                <template #default="{ row }">
                  <div class="score-bar">
                    <span class="score-value">{{ (row.sentiment_score || 0).toFixed(0) }}</span>
                    <el-progress :percentage="row.sentiment_score || 0" :stroke-width="6" :show-text="false" :color="scoreColor(row.sentiment_score)" />
                  </div>
                </template>
              </el-table-column>
              <el-table-column label="止损位" width="90">
                <template #default="{ row }">
                  <span class="price-text stop-loss">{{ formatPrice(row.stop_loss) }}</span>
                </template>
              </el-table-column>
              <el-table-column label="目标价" width="90">
                <template #default="{ row }">
                  <span class="price-text target-price">{{ formatPrice(row.target_price) }}</span>
                </template>
              </el-table-column>
            </el-table>
          </el-card>
        </template>

        <el-empty v-else-if="!pickerLoading" description="点击开始选股获取推荐结果" />
      </div>
    </template>

    <template v-if="form.analysisMode === 'batch'">
      <BatchPick ref="batchPickRef" />
    </template>

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
import { ref, computed, onMounted, watch } from 'vue'
import { Search } from '@element-plus/icons-vue'
import { aiApi, pickerApi } from '@/api/ai'
import { watchlistApi } from '@/api/watchlist'
import { strategyApi } from '@/api/strategy'
import StockSearch from '@/components/StockSearch/index.vue'
import AnalysisProgressPanel from '@/components/AnalysisProgressPanel/index.vue'
import LLMDialoguePanel, { type DialogueMessage } from '@/components/LLMDialoguePanel/index.vue'
import BatchPick from '@/components/BatchPick/index.vue'
import { ElMessage } from 'element-plus'
import type { WatchlistItem, StrategyItem } from '@/types'

const loading = ref(false)
const pickerLoading = ref(false)
const result = ref<AIModelResult | null>(null)
const showRaw = ref(false)
const history = ref<AIModelResult[]>([])
const watchlist = ref<WatchlistItem[]>([])
const showAdvancedPanel = ref(true)
const showLLMDialogue = ref(true)

const currentCode = ref('')
const searchCode = ref('')

const form = ref({
  code: '',
  type: 'comprehensive',
  analysisMode: 'single' as 'single' | 'picker' | 'batch',
})

const showAnalysisProgress = ref(false)
const currentSteps = ref<AnalysisStep[]>([])
const currentRunningStep = ref('')
const currentOperation = ref('')
const batchCount = ref(0)
const completedCount = ref(0)

const dialogueMessages = ref<DialogueMessage[]>([])

const strategyList = ref<StrategyItem[]>([])
const selectedStrategy = ref('')
const pickTopN = ref(20)
const minScore = ref(60)
const pickResults = ref<PickResult[]>([])

const batchPickRef = ref<InstanceType<typeof BatchPick> | null>(null)

interface AnalysisStep {
  name: string
  description?: string
  detail?: string
  status: 'pending' | 'running' | 'completed' | 'error'
  duration?: number
}

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

interface PickResult {
  code: string
  name?: string
  score: number
  technical_score: number
  fundamental_score: number
  sentiment_score: number
  fund_flow_score: number
  recommendation: string
  risk_level: string
  stop_loss: number
  target_price: number
}

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
]

const canAnalyze = computed(() => {
  if (form.value.analysisMode === 'single') {
    return !!form.value.code && !loading.value
  }
  return true
})

const pickAvgScore = computed(() => {
  if (pickResults.value.length === 0) return '0'
  const sum = pickResults.value.reduce((acc, r) => acc + r.score, 0)
  return (sum / pickResults.value.length).toFixed(1)
})

const pickResultType = computed(() => {
  const avg = parseFloat(pickAvgScore.value)
  if (avg >= 70) return 'success'
  if (avg >= 60) return 'warning'
  return 'danger'
})

const pickResultTypeLabel = computed(() => {
  const avg = parseFloat(pickAvgScore.value)
  if (avg >= 70) return '优质标的'
  if (avg >= 60) return '良好标的'
  return '一般标的'
})

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

function scoreTagType(score: number): '' | 'success' | 'warning' | 'danger' | 'info' {
  if (score >= 75) return 'success'
  if (score >= 60) return 'warning'
  if (score >= 50) return 'info'
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

async function loadStrategies() {
  try {
    const res = await strategyApi.getStrategyList()
    const data = res.data?.strategies || res.data?.data || res.data || []
    strategyList.value = data
    if (data.length > 0) {
      selectedStrategy.value = data[0].name
    }
  } catch {
    strategyList.value = []
  }
}

function initAnalysisSteps() {
  currentSteps.value = [
    { name: '数据收集', description: '获取K线、财务、舆情、资金流数据', status: 'pending' },
    { name: '技术面分析', description: '计算MA、RSI、趋势等技术指标', status: 'pending' },
    { name: '基本面分析', description: '评估PE、PB、成长性等财务指标', status: 'pending' },
    { name: '舆情分析', description: '分析新闻舆情和市场情绪', status: 'pending' },
    { name: '资金流分析', description: '评估主力资金净流入情况', status: 'pending' },
    { name: '综合评分', description: '加权计算综合评分和投资建议', status: 'pending' },
  ]
}

function updateStepStatus(stepName: string, status: AnalysisStep['status'], detail?: string) {
  const step = currentSteps.value.find(s => s.name === stepName)
  if (step) {
    step.status = status
    if (detail) step.detail = detail
    if (status === 'completed') {
      step.duration = Date.now()
    }
  }
  currentRunningStep.value = stepName
}

async function handleAnalyze() {
  if (form.value.analysisMode === 'single') {
    await analyzeSingleStock()
  }
}

async function analyzeSingleStock() {
  if (!form.value.code) {
    ElMessage.warning('请输入股票代码')
    return
  }

  loading.value = true
  showAnalysisProgress.value = true
  dialogueMessages.value = []
  initAnalysisSteps()

  const startTime = Date.now()
  dialogueMessages.value.push({
    role: 'user',
    content: `分析股票 ${form.value.code}，分析类型：${form.value.type}`,
    timestamp: startTime,
  })

  try {
    updateStepStatus('数据收集', 'running')
    const res = await aiApi.analyze({ code: form.value.code, type: form.value.type })
    updateStepStatus('数据收集', 'completed', '数据获取成功')

    const data = res.data?.result || res.data?.data || res.data
    result.value = data || {}

    updateStepStatus('技术面分析', 'completed')
    updateStepStatus('基本面分析', 'completed')
    updateStepStatus('舆情分析', 'completed')
    updateStepStatus('资金流分析', 'completed')
    updateStepStatus('综合评分', 'completed', `评分: ${result.value?.composite_score?.toFixed(1) || '0'}`)

    dialogueMessages.value.push({
      role: 'assistant',
      content: JSON.stringify(result.value, null, 2),
      timestamp: Date.now(),
      model: 'auto-selected',
      usage: {
        prompt_tokens: 500,
        completion_tokens: 300,
        latency: `${Date.now() - startTime}ms`,
      },
      isJson: true,
    })

    history.value.unshift(data)
    if (history.value.length > 10) history.value.pop()
  } catch {
    updateStepStatus('综合评分', 'error', '分析失败')
    result.value = null
  } finally {
    loading.value = false
  }
}

async function runSmartPick() {
  pickerLoading.value = true
  showAnalysisProgress.value = true
  initAnalysisSteps()

  currentSteps.value = [
    { name: '策略选择', description: '加载选股策略配置', status: 'pending' },
    { name: '股票筛选', description: '根据策略因子筛选股票', status: 'pending' },
    { name: '评分计算', description: '计算各股票综合评分', status: 'pending' },
    { name: '结果排序', description: '按评分排序并返回结果', status: 'pending' },
  ]

  try {
    updateStepStatus('策略选择', 'running')
    const res = await pickerApi.smartPickAdvanced({
      strategy: selectedStrategy.value,
      top_n: pickTopN.value,
      min_score: minScore.value,
    })
    updateStepStatus('策略选择', 'completed')

    updateStepStatus('股票筛选', 'completed')
    updateStepStatus('评分计算', 'completed')
    updateStepStatus('结果排序', 'completed')

    pickResults.value = res.data?.results || res.data?.data || []
  } catch {
    pickResults.value = []
  } finally {
    pickerLoading.value = false
  }
}

function selectHistory(item: AIModelResult) {
  result.value = item
}

watch(() => form.value.code, (newCode) => {
  if (newCode) {
    currentCode.value = newCode
  }
})

watch(() => form.value.analysisMode, (mode) => {
  if (mode !== 'single') {
    showAnalysisProgress.value = false
  }
})

onMounted(() => {
  loadWatchlist()
  loadStrategies()
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
  grid-template-columns: repeat(4, 1fr);
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

.picker-section {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.header-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.pick-toolbar {
  display: flex;
  gap: 12px;
  align-items: center;
  flex-wrap: wrap;
}

.toolbar-label {
  color: #909399;
  font-size: 13px;
}

.result-summary {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.summary-tags {
  display: flex;
  gap: 8px;
}

.stock-link {
  color: #409eff;
  text-decoration: none;
}

.stock-link:hover {
  text-decoration: underline;
}

.score-bar {
  display: flex;
  align-items: center;
  gap: 6px;
}

.score-value {
  font-size: 12px;
  color: #e5eaf3;
  width: 24px;
}
</style>