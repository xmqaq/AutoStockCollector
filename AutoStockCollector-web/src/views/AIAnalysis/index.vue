<template>
  <div class="ai-analysis">
    <el-card shadow="never" class="section-card">
      <div class="search-bar">
        <el-select
          v-model="currentCode"
          placeholder="选择自选股"
          filterable
          size="large"
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
          <el-option label="情绪分析" value="sentiment" />
          <el-option label="风险评估" value="risk" />
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

    <el-alert
      v-if="cacheHit"
      title="当前结果来自本地缓存"
      type="info"
      show-icon
      closable
      style="margin-bottom:0"
    />

    <el-card v-if="result" shadow="never" class="section-card result-card">
      <template #header>
        <div class="result-header">
          <span>分析结果：{{ result.code }} - {{ analysisTypeLabel(result.type as string) }}</span>
          <el-tag v-if="result.score !== undefined" :type="scoreType(result.score as number)" size="large">
            评分：{{ result.score }}
          </el-tag>
        </div>
      </template>

      <el-descriptions :column="1" border size="small">
        <el-descriptions-item label="分析结论" v-if="result.conclusion">
          <div class="result-text">{{ result.conclusion }}</div>
        </el-descriptions-item>
        <el-descriptions-item label="分析逻辑" v-if="result.logic">
          <div class="result-text">{{ result.logic }}</div>
        </el-descriptions-item>
        <el-descriptions-item label="风险提示" v-if="result.risks">
          <div class="result-text risk-text">{{ result.risks }}</div>
        </el-descriptions-item>
        <el-descriptions-item label="分析时间" v-if="result.timestamp">
          {{ fmtDateTime(result.timestamp as string) }}
        </el-descriptions-item>
      </el-descriptions>

      <div
        v-if="!result.conclusion && !result.logic && rawResult"
        class="raw-result"
      >
        <pre>{{ JSON.stringify(rawResult, null, 2) }}</pre>
      </div>
    </el-card>

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
          <span class="history-code">{{ (item as { code: string }).code }}</span>
          <el-tag size="small" type="info">{{ analysisTypeLabel((item as { type: string }).type) }}</el-tag>
          <span v-if="(item as { score?: number }).score !== undefined" class="history-score">
            评分: {{ (item as { score: number }).score }}
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
import { fmtDateTime } from '@/utils/format'
import { useAIStore } from '@/stores/collectStore'
import StockSearch from '@/components/StockSearch/index.vue'
import { ElMessage } from 'element-plus'
import type { WatchlistItem } from '@/types'

const aiStore = useAIStore()
const loading = ref(false)
const cacheHit = ref(false)
const result = ref<Record<string, unknown> | null>(null)
const rawResult = ref<unknown>(null)
const history = ref<unknown[]>([])
const watchlist = ref<WatchlistItem[]>([])

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
  sentiment: '情绪分析',
  risk: '风险评估',
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

function scoreType(score: number): 'success' | 'warning' | 'danger' | 'info' {
  if (score >= 70) return 'success'
  if (score >= 50) return 'warning'
  return 'danger'
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

  const cacheKey = `${form.value.code}_${form.value.type}`
  const cached = aiStore.getCached(cacheKey)
  if (cached) {
    result.value = cached as Record<string, unknown>
    rawResult.value = cached
    cacheHit.value = true
    return
  }

  loading.value = true
  cacheHit.value = false
  try {
    const res = await aiApi.analyze({ code: form.value.code, type: form.value.type })
    const data = res.data?.result || res.data?.data || res.data
    result.value = data || {}
    rawResult.value = data
    aiStore.setCache(cacheKey, data)
    history.value.unshift(data)
    if (history.value.length > 10) history.value.pop()
  } catch {
    result.value = null
  } finally {
    loading.value = false
  }
}

function selectHistory(item: unknown) {
  result.value = item as Record<string, unknown>
  rawResult.value = item
  const data = item as { code?: string; type?: string }
  if (data.code) form.value.code = data.code
  if (data.type) form.value.type = data.type
  cacheHit.value = true
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
  align-items: center;
  justify-content: space-between;
}

.result-card :deep(.el-descriptions__label) {
  color: #909399;
  width: 100px;
}

.result-card :deep(.el-descriptions__content) {
  color: #e5eaf3;
}

.result-text {
  line-height: 1.6;
  font-size: 13px;
  white-space: pre-wrap;
}

.risk-text {
  color: #f56c6c;
}

.raw-result {
  background: #141414;
  border-radius: 4px;
  padding: 12px;
  margin-top: 8px;
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