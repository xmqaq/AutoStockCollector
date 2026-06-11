<template>
  <div class="da-page">
    <!-- 搜索栏 -->
    <div class="da-toolbar">
      <el-input
        v-model="inputCode"
        placeholder="输入股票代码，如 600519"
        style="width: 260px"
        @keyup.enter="runAnalysis"
      />
      <el-button type="primary" :loading="loading" :disabled="!inputCode" @click="runAnalysis">
        深度分析
      </el-button>
      <el-tooltip content="分析偏好设置（注入AI报告）" placement="bottom">
        <el-button :icon="Setting" circle @click="openProfileDrawer" />
      </el-tooltip>
    </div>

    <el-empty v-if="!data && !loading" description="输入股票代码开始分析" />

    <template v-if="data">
      <!-- 区块一：基本信息栏 -->
      <div class="da-header">
        <div class="da-header-left">
          <span class="da-name">{{ data.basic_info.name }}</span>
          <span class="da-code">{{ data.basic_info.code }}</span>
          <el-tag size="small" effect="plain" type="info">{{ data.basic_info.industry || '未知行业' }}</el-tag>
        </div>
        <div class="da-header-center">
          <span class="da-price" :class="priceChangeClass">
            {{ fmtNum(data.price_info.current_price, 2, '--') }}
          </span>
          <span class="da-change" :class="priceChangeClass">
            {{ fmtChange(data.price_info.price_change_pct) }}
          </span>
        </div>
        <div class="da-header-right">
          <div class="da-meta"><label>市值</label><span>{{ fmtYi(data.basic_info.market_cap_yi) }}</span></div>
          <div class="da-meta"><label>PE</label><span>{{ fmtNum(data.financial.pe, 1) }}</span></div>
          <div class="da-meta"><label>PB</label><span>{{ fmtNum(data.financial.pb, 2) }}</span></div>
        </div>
      </div>

      <!-- 区块二：量化评分总览 -->
      <el-card shadow="never" class="da-card">
        <template #header>
          <div class="da-score-header">
            <span>量化评分总览</span>
            <span v-if="data.analysis_time" class="da-time-hint">数据时间：{{ data.analysis_time }}</span>
          </div>
        </template>
        <div class="da-scores">
          <div class="da-score-main">
            <div class="da-score-num" :style="{ color: scoreColor(data.scores.composite) }">
              {{ fmtNum(data.scores.composite, 1) }}
            </div>
            <div class="da-score-label">综合评分</div>
          </div>
          <div class="da-score-dims">
            <div v-for="d in scoreDims" :key="d.key" class="da-dim">
              <span class="da-dim-name">{{ d.label }}</span>
              <el-progress
                :percentage="data.scores[d.key]?.score ?? 0"
                :color="scoreColor(data.scores[d.key]?.score ?? 0)"
                :show-text="false"
              />
              <span class="da-dim-val">{{ fmtNum(data.scores[d.key]?.score, 0) }}</span>
            </div>
          </div>
        </div>
        <div v-if="scoreExpanded" class="da-score-details">
          <div v-for="d in scoreDims" :key="d.key" class="da-detail-group">
            <div class="da-detail-title">{{ d.label }}（{{ fmtNum(data.scores[d.key]?.score, 0) }}分）</div>
            <div class="da-detail-items">
              <template v-for="(v, k) in data.scores[d.key]?.details" :key="k">
                <div v-if="typeof v === 'object' && v?.score !== undefined" class="da-detail-item">
                  <span class="da-detail-k">{{ detailLabel(String(k)) }}</span>
                  <span class="da-detail-v">{{ fmtDetailVal(v) }}</span>
                  <span class="da-detail-s">{{ v.score }}/{{ v.max }}</span>
                </div>
              </template>
            </div>
          </div>
        </div>
        <div class="da-score-note">资金面评分基于近5个交易日均值，降低单日波动影响</div>
        <div class="da-expand-toggle" @click="scoreExpanded = !scoreExpanded">
          {{ scoreExpanded ? '收起详情' : '展开评分详情' }}
          <el-icon><component :is="scoreExpanded ? 'ArrowUp' : 'ArrowDown'" /></el-icon>
        </div>
      </el-card>

      <!-- 区块三：K线图 -->
      <el-card shadow="never" class="da-card">
        <template #header>
          <div class="da-kline-header">
            <span>K线走势（近60日）</span>
            <div class="da-kline-meta">
              <span>52周高: <em>{{ fmtNum(data.price_info.high_52w, 2) }}</em></span>
              <span>52周低: <em>{{ fmtNum(data.price_info.low_52w, 2) }}</em></span>
              <span>量比: <em>{{ fmtNum(data.price_info.volume_ratio, 2) }}</em></span>
            </div>
          </div>
        </template>
        <v-chart ref="klineChartRef" :option="klineOption" style="height: 420px" autoresize />
      </el-card>

      <!-- 区块四：财务数据趋势 -->
      <el-card shadow="never" class="da-card">
        <template #header><span>财务数据（{{ data.financial.report_date || '--' }} {{ data.financial.report_type }}）</span></template>
        <div class="da-fin-summary">
          <div class="da-fin-item"><label>营收</label><span>{{ fmtYi(data.financial.revenue_yi) }}</span><em :class="growthClass(data.financial.revenue_growth)">{{ fmtGrowth(data.financial.revenue_growth) }}</em></div>
          <div class="da-fin-item"><label>净利润</label><span>{{ fmtYi(data.financial.net_profit_yi) }}</span><em :class="growthClass(data.financial.profit_growth)">{{ fmtGrowth(data.financial.profit_growth) }}</em></div>
          <div class="da-fin-item"><label>ROE</label><span>{{ fmtPct(data.financial.roe) }}</span></div>
          <div class="da-fin-item"><label>毛利率</label><span>{{ fmtPct(data.financial.gross_margin) }}</span></div>
          <div class="da-fin-item"><label>负债率</label><span>{{ fmtPct(data.financial.debt_ratio) }}</span></div>
          <div class="da-fin-item"><label>EPS</label><span>{{ fmtNum(data.financial.eps, 2) }}</span></div>
        </div>
        <v-chart
          v-if="data.financial.history?.length > 1"
          :option="finChartOption"
          style="height: 260px"
          autoresize
        />
      </el-card>

      <!-- 区块五：AI深度分析报告 -->
      <el-card shadow="never" class="da-card">
        <template #header><span>AI 深度分析报告</span></template>
        <div v-if="!aiReport && !aiLoading" class="da-ai-trigger">
          <el-button type="primary" size="large" @click="runAIReport">
            开始AI深度分析（约15秒）
          </el-button>
          <p class="da-ai-hint">基于以上真实数据，由AI生成多维度分析报告</p>
        </div>
        <div v-if="aiLoading" class="da-ai-loading">
          <el-icon class="is-loading" :size="24"><Loading /></el-icon>
          <span>AI正在分析中，请稍候...</span>
        </div>
        <div v-if="aiReport" class="da-ai-report">
          <div v-if="aiReport.success" class="da-ai-content md-content" v-html="renderMd(aiReport.content || '')" />
          <el-alert v-else type="warning" :closable="false" show-icon>
            {{ aiReport.error || 'AI服务暂不可用' }}
          </el-alert>
          <div v-if="aiReport.provider" class="da-ai-meta">
            <span>Provider: {{ aiReport.provider }}</span>
            <span v-if="aiReport.from_cache">（缓存）</span>
          </div>
        </div>
      </el-card>

      <!-- 区块：历史预测复盘 + 分析记录 -->
      <el-card shadow="never" class="da-card">
        <template #header><span>历史预测复盘</span></template>
        <template v-if="reflectionHistory.length">
          <div class="da-reflect-stats">
            <span class="da-reflect-stat">共复盘 <em>{{ reflectionStats.total }}</em> 次</span>
            <span class="da-reflect-stat ok">正确 <em>{{ reflectionStats.correct }}</em></span>
            <span class="da-reflect-stat bad">错误 <em>{{ reflectionStats.wrong }}</em></span>
            <span class="da-reflect-stat">部分正确 <em>{{ reflectionStats.partial }}</em></span>
          </div>
          <div class="da-reflect-list">
            <div v-for="(r, i) in reflectionHistory" :key="i" class="da-reflect-item">
              <el-tag size="small" :type="accuracyTagType(r.accuracy)">{{ accuracyLabel(r.accuracy) }}</el-tag>
              <span class="da-reflect-summary">{{ r.summary }}</span>
              <span class="da-reflect-return" :class="r.realized_return >= 0 ? 'rise' : 'fall'">
                {{ fmtChange(r.realized_return) }}
              </span>
            </div>
          </div>
        </template>
        <p v-else class="da-block-hint">
          暂无该股的历史预测。生成AI深度分析报告后会自动记录本次结论，下次分析时将用真实走势复盘对错。
        </p>
        <template v-if="analysisHistory.length">
          <el-divider style="margin: 12px 0" />
          <div class="da-history-title">近期分析记录</div>
          <div class="da-history-list">
            <div v-for="(h, i) in analysisHistory" :key="i" class="da-history-item">
              <span class="da-history-date">{{ h.analysis_date }}</span>
              <el-tag size="small" :type="verdictTagType(h.verdict)">{{ h.verdict }}</el-tag>
            </div>
          </div>
        </template>
      </el-card>

      <!-- 区块六：买卖参考建议 -->
      <el-card shadow="never" class="da-card">
        <template #header>
          <div class="da-advice-head">
            <span>买卖参考建议</span>
            <div class="da-advice-inputs">
              <el-input v-model.number="cost" placeholder="成本价(可选)" size="small" style="width: 130px" />
              <el-input v-model.number="position" placeholder="仓位0-1(可选)" size="small" style="width: 130px" />
              <el-button size="small" :loading="adviceLoading" @click="runAdvice">获取建议</el-button>
            </div>
          </div>
        </template>
        <div v-if="advice" class="da-advice-body">
          <el-tag :type="actionType(advice.advice.action)" size="large">{{ advice.advice.action }}</el-tag>
          <p class="da-advice-reason">{{ advice.advice.reason }}</p>
          <div class="da-advice-grid">
            <div><label>参考区间</label><span>{{ advice.advice.buy_zone || '--' }}</span></div>
            <div><label>止损</label><span>{{ advice.advice.stop_loss || '--' }}</span></div>
            <div><label>仓位建议</label><span>{{ advice.advice.position_advice || '--' }}</span></div>
          </div>
        </div>
        <el-empty v-else description="输入成本价和仓位后点击获取建议" :image-size="60" />
      </el-card>

      <!-- 区块七：相关新闻 -->
      <el-card v-if="data.news?.length" shadow="never" class="da-card">
        <template #header><span>相关新闻（{{ data.news.length }}条）</span></template>
        <div class="da-news-list">
          <div v-for="(n, i) in data.news" :key="i" class="da-news-item" @click="toggleNews(i)">
            <div class="da-news-head">
              <span class="da-news-title">{{ n.title }}</span>
              <span class="da-news-meta">{{ n.source }} · {{ n.publish_time }}</span>
            </div>
            <div v-if="expandedNews === i && n.content" class="da-news-content">
              {{ n.content }}
            </div>
          </div>
        </div>
      </el-card>

      <!-- 区块八：多Agent 辩论分析（增强） -->
      <el-card shadow="never" class="da-card">
        <template #header>
          <div class="da-ma-head">
            <span>多Agent 辩论分析（增强）</span>
            <el-button v-if="!showMultiAgent" size="small" type="primary" plain @click="showMultiAgent = true">
              启动辩论分析
            </el-button>
            <el-button v-else size="small" text @click="showMultiAgent = false">收起</el-button>
          </div>
        </template>
        <p v-if="!showMultiAgent" class="da-block-hint">
          由传统分析师团队 + 投资哲学流派 Agent 对该股进行多空辩论并输出最终裁决。涉及多轮大模型调用，耗时较长，按需启动。
        </p>
        <MultiAgentPanel v-else :initial-code="data.basic_info.code" />
      </el-card>

      <p class="da-method-note">评分基于实时数据计算：K线取近60个交易日，财务取最新报告期，资金面取近5日均值，PE/PB取TTM口径</p>
    </template>

    <!-- 分析偏好设置抽屉 -->
    <el-drawer v-model="profileDrawerVisible" title="分析偏好设置" size="380px">
      <el-form label-position="top">
        <el-form-item label="风险偏好">
          <el-radio-group v-model="profileForm.risk_level">
            <el-radio-button value="conservative">保守</el-radio-button>
            <el-radio-button value="balanced">平衡</el-radio-button>
            <el-radio-button value="aggressive">激进</el-radio-button>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="持仓周期偏好">
          <el-radio-group v-model="profileForm.holding_horizon">
            <el-radio-button value="short">短线</el-radio-button>
            <el-radio-button value="medium">中线</el-radio-button>
            <el-radio-button value="long">长线</el-radio-button>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="偏好行业（可输入新增）">
          <el-select
            v-model="profileForm.preferred_industries"
            multiple filterable allow-create default-first-option
            placeholder="如：半导体、医药、银行"
            style="width: 100%"
          >
            <el-option v-for="ind in commonIndustries" :key="ind" :label="ind" :value="ind" />
          </el-select>
        </el-form-item>
        <p class="da-block-hint" style="margin-bottom: 14px">
          偏好会注入AI深度分析报告，影响综合评级与操作建议的口径
        </p>
        <el-button type="primary" :loading="profileSaving" style="width: 100%" @click="saveProfile">
          保存偏好
        </el-button>
      </el-form>
    </el-drawer>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, nextTick, reactive } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Loading, ArrowUp, ArrowDown, Setting } from '@element-plus/icons-vue'
import { marked } from 'marked'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CandlestickChart, BarChart, LineChart } from 'echarts/charts'
import {
  GridComponent, TooltipComponent, LegendComponent,
  DataZoomComponent, MarkLineComponent,
} from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import {
  deepAnalysisApi, aiServiceApi,
  type DeepAnalysisData, type AIReportResult, type AIAdviceResult,
} from '@/api/ai'
import { memoryApi } from '@/api/memory'
import MultiAgentPanel from '@/components/MultiAgentPanel/index.vue'
import { RISE_COLOR, FALL_COLOR } from '@/utils/format'

use([
  CandlestickChart, BarChart, LineChart,
  GridComponent, TooltipComponent, LegendComponent,
  DataZoomComponent, MarkLineComponent, CanvasRenderer,
])

marked.setOptions({ breaks: true, gfm: true })

const route = useRoute()
const inputCode = ref('')
const loading = ref(false)
const data = ref<DeepAnalysisData | null>(null)
const scoreExpanded = ref(false)
const expandedNews = ref<number | null>(null)

const aiLoading = ref(false)
const aiReport = ref<AIReportResult | null>(null)
const adviceLoading = ref(false)
const advice = ref<AIAdviceResult | null>(null)
const cost = ref<number | undefined>()
const position = ref<number | undefined>()

const klineChartRef = ref<InstanceType<typeof VChart> | null>(null)

// ── 多Agent辩论增强区块 ──
const showMultiAgent = ref(false)

// ── 历史预测复盘 / 分析记录 ──
const reflectionHistory = computed(() => data.value?.reflection?.history ?? [])
const reflectionStats = computed(() =>
  data.value?.reflection?.stats ?? { total: 0, correct: 0, wrong: 0, partial: 0 })
const analysisHistory = computed(() => data.value?.analysis_history ?? [])

function accuracyLabel(acc: string): string {
  return { correct: '判断正确', wrong: '判断错误', partial: '部分正确' }[acc] || acc
}

function accuracyTagType(acc: string): string {
  return { correct: 'success', wrong: 'danger', partial: 'warning' }[acc] || 'info'
}

function verdictTagType(verdict: string): string {
  if (verdict.includes('强烈关注') || verdict.includes('适度关注')) return 'success'
  if (verdict.includes('回避')) return 'danger'
  return 'info'
}

// ── 分析偏好设置 ──
const profileDrawerVisible = ref(false)
const profileSaving = ref(false)
const profileForm = reactive({
  risk_level: 'balanced',
  holding_horizon: 'medium',
  preferred_industries: [] as string[],
})
const commonIndustries = ['半导体', '医药生物', '银行', '新能源', '白酒', '军工', '计算机', '消费电子']

async function openProfileDrawer() {
  profileDrawerVisible.value = true
  try {
    const res = await memoryApi.getProfile()
    const p = res.data?.data
    if (p) {
      profileForm.risk_level = p.risk_level || 'balanced'
      profileForm.holding_horizon = p.holding_horizon || 'medium'
      profileForm.preferred_industries = p.preferred_industries || []
    }
  } catch { /* 加载失败保留默认值 */ }
}

async function saveProfile() {
  profileSaving.value = true
  try {
    await memoryApi.updateProfile({ ...profileForm })
    ElMessage.success('偏好已保存，将在下次AI报告中生效')
    profileDrawerVisible.value = false
  } catch {
    ElMessage.error('保存失败')
  } finally {
    profileSaving.value = false
  }
}

const scoreDims = [
  { key: 'fundamental' as const, label: '基本面' },
  { key: 'technical' as const, label: '技术面' },
  { key: 'fund_flow' as const, label: '资金面' },
  { key: 'valuation' as const, label: '估值面' },
]

const priceChangeClass = computed(() => {
  const pct = data.value?.price_info?.price_change_pct
  if (pct == null) return ''
  return pct >= 0 ? 'rise' : 'fall'
})

function scoreColor(v: number | null | undefined): string {
  if (v == null) return '#606080'
  if (v >= 70) return '#3a8a52'
  if (v >= 50) return '#d0a020'
  return '#a04040'
}

function fmtNum(v: number | null | undefined, decimals = 2, fallback = '--'): string {
  if (v == null) return fallback
  return Number(v).toFixed(decimals)
}

function fmtYi(v: number | null | undefined): string {
  if (v == null) return '--'
  return `${v.toFixed(2)}亿`
}

function fmtPct(v: number | null | undefined): string {
  if (v == null) return '--'
  return `${v.toFixed(2)}%`
}

function fmtChange(v: number | null | undefined): string {
  if (v == null) return '--'
  return `${v >= 0 ? '+' : ''}${v.toFixed(2)}%`
}

function fmtGrowth(v: number | null | undefined): string {
  if (v == null) return ''
  return `${v >= 0 ? '+' : ''}${v.toFixed(1)}%`
}

function growthClass(v: number | null | undefined): string {
  if (v == null) return ''
  return v >= 0 ? 'rise' : 'fall'
}

function actionType(action: string): string {
  if (['买入参考', '关注', '持有'].some(a => action.includes(a))) return 'success'
  if (['减仓', '回避', '卖出'].some(a => action.includes(a))) return 'danger'
  return 'info'
}

function renderMd(text: string): string {
  if (!text) return ''
  return marked.parse(text) as string
}

const detailLabelMap: Record<string, string> = {
  roe: 'ROE', revenue_growth: '营收增速', profit_growth: '利润增速',
  gross_margin: '毛利率', debt_ratio: '负债率', ma_trend: '均线趋势',
  macd: 'MACD', rsi: 'RSI', momentum: '价格动量',
  net_inflow: '主力净流入', main_ratio: '主力占比', turnover_rate: '换手率',
  pe: 'PE', pb: 'PB',
}

function detailLabel(key: string): string {
  return detailLabelMap[key] || key
}

function fmtDetailVal(v: any): string {
  if (v?.value == null) return '--'
  if (typeof v.value === 'string') return v.value
  if (typeof v.value_yi === 'number') return `${v.value_yi.toFixed(4)}亿`
  if (typeof v.value === 'number') return v.value.toFixed(2)
  return String(v.value)
}

function toggleNews(i: number) {
  expandedNews.value = expandedNews.value === i ? null : i
}

function cleanDate(raw: string): string {
  if (!raw) return ''
  const s = raw.trim()
  if (s.length >= 10 && s[4] === '-') return s.slice(0, 10)
  if (s.length === 8 && /^\d+$/.test(s)) return `${s.slice(0, 4)}-${s.slice(4, 6)}-${s.slice(6)}`
  return s.slice(0, 10)
}

function shortDate(d: string): string {
  const clean = cleanDate(d)
  return clean.length >= 10 ? clean.slice(5) : clean
}

// ── K线图配置 ──
const klineOption = computed(() => {
  const kdata = data.value?.kline
  if (!kdata?.length) return {}

  const dates = kdata.map(d => cleanDate(d.date))
  const ohlc = kdata.map(d => [d.open, d.close, d.low, d.high])

  function calcMA(period: number): (number | string)[] {
    const result: (number | string)[] = []
    for (let i = 0; i < kdata!.length; i++) {
      if (i < period - 1) { result.push('-'); continue }
      let sum = 0
      for (let j = 0; j < period; j++) sum += kdata![i - j].close ?? 0
      result.push(+(sum / period).toFixed(2))
    }
    return result
  }

  const volumes = kdata.map((d, i) => ({
    value: d.volume,
    itemStyle: {
      color: (d.close ?? 0) >= (d.open ?? 0) ? RISE_COLOR : FALL_COLOR,
    },
  }))

  return {
    backgroundColor: 'transparent',
    animation: false,
    legend: {
      top: 0, left: 'center',
      textStyle: { color: '#909399', fontSize: 11 },
      data: ['MA5', 'MA20', 'MA60'],
    },
    axisPointer: {
      link: [{ xAxisIndex: 'all' }],
      label: { backgroundColor: '#555' },
    },
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'cross', crossStyle: { color: '#888' } },
      backgroundColor: '#1a1a2e',
      borderColor: '#333',
      textStyle: { color: '#e5eaf3', fontSize: 12 },
      formatter(params: any[]) {
        if (!params?.length) return ''
        const idx = params[0]?.dataIndex
        if (idx == null || !kdata![idx]) return ''
        const r = kdata![idx]
        const row = (k: string, v: string, c = '#e5eaf3') =>
          `<div style="display:flex;justify-content:space-between;gap:16px"><span style="color:#909399">${k}</span><span style="color:${c}">${v}</span></div>`
        return `<div style="padding:4px 8px;min-width:150px">
          <div style="font-weight:600;margin-bottom:4px">${r.date}</div>
          ${row('开', fmtNum(r.open))}
          ${row('高', fmtNum(r.high), RISE_COLOR)}
          ${row('低', fmtNum(r.low), FALL_COLOR)}
          ${row('收', fmtNum(r.close))}
          ${row('成交额', r.volume != null ? (r.volume >= 1e8 ? (r.volume / 1e8).toFixed(2) + '亿' : (r.volume / 1e4).toFixed(0) + '万') : '--')}
        </div>`
      },
    },
    grid: [
      { left: 60, right: 20, top: 30, bottom: '28%' },
      { left: 60, right: 20, top: '75%', bottom: 50 },
    ],
    xAxis: [
      { type: 'category', data: dates, boundaryGap: false, axisLine: { lineStyle: { color: '#333' } }, splitLine: { show: false }, axisLabel: { color: '#666', fontSize: 10, formatter: (v: string) => shortDate(v) }, gridIndex: 0 },
      { type: 'category', data: dates, boundaryGap: false, axisLine: { lineStyle: { color: '#333' } }, splitLine: { show: false }, axisLabel: { show: false }, gridIndex: 1 },
    ],
    yAxis: [
      { scale: true, splitArea: { show: false }, axisLine: { lineStyle: { color: '#333' } }, splitLine: { lineStyle: { color: '#1a1a2e' } }, axisLabel: { color: '#666', fontSize: 10 }, gridIndex: 0 },
      { scale: true, splitArea: { show: false }, axisLine: { lineStyle: { color: '#333' } }, splitLine: { lineStyle: { color: '#1a1a2e' } }, axisLabel: { color: '#666', fontSize: 10, formatter: (v: number) => v >= 1e8 ? (v / 1e8).toFixed(0) + '亿' : (v / 1e4).toFixed(0) + '万' }, gridIndex: 1 },
    ],
    dataZoom: [
      { type: 'inside', xAxisIndex: [0, 1], start: 0, end: 100 },
      { type: 'slider', xAxisIndex: [0, 1], bottom: 8, height: 16, borderColor: '#333', fillerColor: 'rgba(100,100,200,0.1)', handleStyle: { color: '#555' }, textStyle: { color: '#666' }, labelFormatter: (_: number, v: string) => shortDate(v) },
    ],
    series: [
      {
        name: 'K线', type: 'candlestick', data: ohlc, xAxisIndex: 0, yAxisIndex: 0,
        itemStyle: { color: RISE_COLOR, color0: FALL_COLOR, borderColor: RISE_COLOR, borderColor0: FALL_COLOR },
      },
      { name: 'MA5', type: 'line', data: calcMA(5), smooth: true, showSymbol: false, lineStyle: { width: 1, color: '#ffc107' }, xAxisIndex: 0, yAxisIndex: 0 },
      { name: 'MA20', type: 'line', data: calcMA(20), smooth: true, showSymbol: false, lineStyle: { width: 1, color: '#42a5f5' }, xAxisIndex: 0, yAxisIndex: 0 },
      { name: 'MA60', type: 'line', data: calcMA(60), smooth: true, showSymbol: false, lineStyle: { width: 1, color: '#ab47bc' }, xAxisIndex: 0, yAxisIndex: 0 },
      { name: '成交额', type: 'bar', data: volumes, xAxisIndex: 1, yAxisIndex: 1 },
    ],
  }
})

// ── 财务趋势图配置 ──
const finChartOption = computed(() => {
  const hist = data.value?.financial?.history
  if (!hist?.length) return {}
  const reversed = [...hist].reverse()
  const labels = reversed.map(h => h.report_date?.slice(0, 7) || '')
  return {
    backgroundColor: 'transparent',
    legend: { top: 0, textStyle: { color: '#909399', fontSize: 11 }, data: ['营收(亿)', '净利润(亿)', 'ROE(%)', '毛利率(%)'] },
    tooltip: { trigger: 'axis', backgroundColor: '#1a1a2e', borderColor: '#333', textStyle: { color: '#e5eaf3', fontSize: 12 } },
    grid: { left: 50, right: 50, top: 40, bottom: 30 },
    xAxis: { type: 'category', data: labels, axisLabel: { color: '#666', fontSize: 10 }, axisLine: { lineStyle: { color: '#333' } } },
    yAxis: [
      { type: 'value', name: '亿元', nameTextStyle: { color: '#666', fontSize: 10 }, axisLabel: { color: '#666', fontSize: 10 }, splitLine: { lineStyle: { color: '#1a1a2e' } }, axisLine: { lineStyle: { color: '#333' } } },
      { type: 'value', name: '%', nameTextStyle: { color: '#666', fontSize: 10 }, axisLabel: { color: '#666', fontSize: 10 }, splitLine: { show: false }, axisLine: { lineStyle: { color: '#333' } } },
    ],
    series: [
      { name: '营收(亿)', type: 'bar', data: reversed.map(h => h.revenue_yi), barMaxWidth: 30, itemStyle: { color: '#409eff', borderRadius: [2, 2, 0, 0] } },
      { name: '净利润(亿)', type: 'bar', data: reversed.map(h => h.net_profit_yi), barMaxWidth: 30, itemStyle: { color: '#67c23a', borderRadius: [2, 2, 0, 0] } },
      { name: 'ROE(%)', type: 'line', data: reversed.map(h => h.roe), yAxisIndex: 1, smooth: true, showSymbol: true, symbolSize: 6, lineStyle: { color: '#e6a23c' }, itemStyle: { color: '#e6a23c' } },
      { name: '毛利率(%)', type: 'line', data: reversed.map(h => h.gross_margin), yAxisIndex: 1, smooth: true, showSymbol: true, symbolSize: 6, lineStyle: { color: '#f56c6c' }, itemStyle: { color: '#f56c6c' } },
    ],
  }
})

// ── 业务逻辑 ──
async function runAnalysis() {
  if (!inputCode.value) return
  loading.value = true
  aiReport.value = null
  advice.value = null
  scoreExpanded.value = false
  expandedNews.value = null
  showMultiAgent.value = false
  try {
    const res = await deepAnalysisApi.getData(inputCode.value.trim())
    if (res.data?.success) {
      data.value = res.data.data
      nextTick(() => klineChartRef.value?.resize())
    } else {
      ElMessage.error(res.data?.error || '分析失败')
    }
  } catch {
    ElMessage.error('分析请求失败')
  } finally {
    loading.value = false
  }
}

async function runAIReport() {
  if (!data.value) return
  aiLoading.value = true
  try {
    const res = await deepAnalysisApi.getAIReport(data.value.basic_info.code)
    if (res.data?.success) {
      aiReport.value = res.data.data
    } else {
      aiReport.value = { success: false, error: res.data?.data?.error || res.data?.error || 'AI服务暂不可用' }
    }
  } catch {
    aiReport.value = { success: false, error: 'AI请求失败，请检查网络或API配置' }
  } finally {
    aiLoading.value = false
  }
}

async function runAdvice() {
  if (!data.value) return
  adviceLoading.value = true
  try {
    const payload: { cost?: number; position?: number } = {}
    if (cost.value !== undefined) payload.cost = cost.value
    if (position.value !== undefined) payload.position = position.value
    const res = await aiServiceApi.advice(data.value.basic_info.code, payload)
    if (res.data?.success) {
      advice.value = res.data.data
    } else {
      ElMessage.error(res.data?.error || '建议获取失败')
    }
  } catch {
    ElMessage.error('建议请求失败')
  } finally {
    adviceLoading.value = false
  }
}

onMounted(() => {
  const q = route.query.code
  if (typeof q === 'string' && q) {
    inputCode.value = q
    runAnalysis()
  }
})
</script>

<style scoped>
.da-page { display: flex; flex-direction: column; gap: 14px; max-width: 1200px; }
.da-toolbar { display: flex; align-items: center; gap: 10px; }

/* ── 基本信息栏 ── */
.da-header {
  display: flex; align-items: center; gap: 20px;
  padding: 14px 18px; border-radius: 8px;
  background: #0c0c14; border: 1px solid var(--bg-deep-soft);
}
.da-header-left { display: flex; align-items: center; gap: 8px; }
.da-name { font-size: 18px; font-weight: 700; color: var(--text-alt-primary); }
.da-code { font-size: 13px; color: var(--text-alt-secondary); }
.da-header-center { margin-left: auto; display: flex; align-items: baseline; gap: 10px; }
.da-price { font-size: 26px; font-weight: 800; }
.da-change { font-size: 14px; font-weight: 600; }
.da-price.rise, .da-change.rise { color: #ef5350; }
.da-price.fall, .da-change.fall { color: #26a69a; }
.da-header-right { display: flex; gap: 18px; margin-left: 24px; }
.da-meta { display: flex; flex-direction: column; align-items: center; gap: 2px; }
.da-meta label { font-size: 10px; color: #606080; }
.da-meta span { font-size: 14px; color: var(--text-alt-body); font-weight: 600; }

/* ── 通用卡片 ── */
.da-card { background: #0c0c14; border: 1px solid var(--bg-deep-soft); }
.da-card :deep(.el-card__header) { color: var(--text-alt-body); font-size: 13.5px; font-weight: 600; padding: 12px 18px; border-bottom-color: var(--bg-deep-soft); }
.da-card :deep(.el-card__body) { padding: 14px 18px; }

/* ── 评分区 ── */
.da-scores { display: flex; gap: 30px; align-items: center; }
.da-score-main { text-align: center; min-width: 100px; }
.da-score-num { font-size: 44px; font-weight: 800; line-height: 1; }
.da-score-label { font-size: 12px; color: #606080; margin-top: 6px; }
.da-score-dims { flex: 1; display: flex; flex-direction: column; gap: 10px; }
.da-dim { display: grid; grid-template-columns: 56px 1fr 36px; align-items: center; gap: 8px; }
.da-dim-name { font-size: 12px; color: var(--text-alt-secondary); }
.da-dim-val { font-size: 12px; color: var(--text-alt-body); text-align: right; }
.da-score-header { display: flex; justify-content: space-between; align-items: center; }
.da-time-hint { font-size: 11px; color: #606080; font-weight: 400; }
.da-score-note { font-size: 11px; color: #505068; text-align: center; margin-top: 10px; }
.da-expand-toggle {
  text-align: center; padding: 8px 0 0; cursor: pointer;
  font-size: 12px; color: #606080; display: flex; align-items: center; justify-content: center; gap: 4px;
}
.da-expand-toggle:hover { color: #409eff; }
.da-score-details {
  margin-top: 14px; padding-top: 14px; border-top: 1px solid var(--bg-deep-soft);
  display: grid; grid-template-columns: 1fr 1fr; gap: 16px;
}
.da-detail-group {}
.da-detail-title { font-size: 12px; color: var(--text-alt-secondary); margin-bottom: 6px; font-weight: 600; }
.da-detail-items { display: flex; flex-direction: column; gap: 4px; }
.da-detail-item { display: grid; grid-template-columns: 70px 1fr 50px; gap: 6px; font-size: 11px; }
.da-detail-k { color: #606080; }
.da-detail-v { color: var(--text-alt-body); }
.da-detail-s { color: var(--text-alt-secondary); text-align: right; }

/* ── K线图 ── */
.da-kline-header { display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px; }
.da-kline-meta { display: flex; gap: 14px; font-size: 12px; color: #606080; }
.da-kline-meta em { color: var(--text-alt-body); font-style: normal; font-weight: 500; }

/* ── 财务区 ── */
.da-fin-summary {
  display: grid; grid-template-columns: repeat(auto-fill, minmax(140px, 1fr)); gap: 12px;
  margin-bottom: 14px;
}
.da-fin-item { display: flex; flex-direction: column; gap: 2px; }
.da-fin-item label { font-size: 10px; color: #606080; }
.da-fin-item span { font-size: 15px; color: var(--text-alt-body); font-weight: 600; }
.da-fin-item em { font-size: 11px; font-style: normal; }
.da-fin-item em.rise { color: #ef5350; }
.da-fin-item em.fall { color: #26a69a; }

/* ── AI分析报告 ── */
.da-ai-trigger { text-align: center; padding: 20px 0; }
.da-ai-hint { font-size: 12px; color: #606080; margin-top: 8px; }
.da-ai-loading { display: flex; align-items: center; justify-content: center; gap: 10px; padding: 30px 0; color: var(--text-alt-secondary); }
.da-ai-report {}
.da-ai-content { color: var(--text-alt-body); line-height: 1.8; font-size: 13.5px; }
.da-ai-content :deep(h2) { font-size: 15px; color: var(--text-alt-primary); margin: 18px 0 8px; padding-bottom: 6px; border-bottom: 1px solid var(--bg-card-alt); }
.da-ai-content :deep(h2:first-child) { margin-top: 0; }
.da-ai-content :deep(p) { margin: 6px 0; }
.da-ai-content :deep(ul), .da-ai-content :deep(ol) { padding-left: 20px; margin: 6px 0; }
.da-ai-content :deep(strong) { color: var(--text-alt-primary); }
.da-ai-meta { margin-top: 12px; font-size: 11px; color: #44445a; }

/* ── 买卖建议 ── */
.da-advice-head { display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px; }
.da-advice-inputs { display: flex; gap: 8px; }
.da-advice-body { display: flex; flex-direction: column; gap: 12px; }
.da-advice-reason { color: var(--text-alt-body); line-height: 1.7; font-size: 13px; }
.da-advice-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; }
.da-advice-grid div { display: flex; flex-direction: column; gap: 4px; }
.da-advice-grid label { font-size: 11px; color: #606080; }
.da-advice-grid span { font-size: 13px; color: var(--text-alt-body); }

/* ── 新闻列表 ── */
.da-news-list { display: flex; flex-direction: column; }
.da-news-item { padding: 10px 0; border-bottom: 1px solid var(--bg-deep-soft); cursor: pointer; }
.da-news-item:last-child { border-bottom: none; }
.da-news-item:hover .da-news-title { color: #409eff; }
.da-news-head { display: flex; justify-content: space-between; align-items: flex-start; gap: 10px; }
.da-news-title { font-size: 13px; color: var(--text-alt-body); flex: 1; }
.da-news-meta { font-size: 11px; color: #606080; white-space: nowrap; }
.da-news-content { margin-top: 8px; font-size: 12px; color: var(--text-alt-secondary); line-height: 1.6; }

.da-method-note { font-size: 11px; color: #44445a; text-align: center; margin-top: 8px; }

/* ── 历史预测复盘 ── */
.da-block-hint { font-size: 12px; color: #606080; line-height: 1.7; }
.da-reflect-stats { display: flex; gap: 18px; margin-bottom: 12px; font-size: 12px; color: var(--text-alt-secondary); }
.da-reflect-stat em { font-style: normal; font-weight: 700; color: var(--text-alt-body); }
.da-reflect-stat.ok em { color: #3a8a52; }
.da-reflect-stat.bad em { color: #a04040; }
.da-reflect-list { display: flex; flex-direction: column; gap: 8px; }
.da-reflect-item { display: flex; align-items: center; gap: 10px; }
.da-reflect-summary { flex: 1; font-size: 12.5px; color: var(--text-alt-body); }
.da-reflect-return { font-size: 12.5px; font-weight: 600; }
.da-history-title { font-size: 12px; color: var(--text-alt-secondary); font-weight: 600; margin-bottom: 8px; }
.da-history-list { display: flex; flex-direction: column; gap: 6px; }
.da-history-item { display: flex; align-items: center; gap: 12px; }
.da-history-date { font-size: 12px; color: var(--text-alt-secondary); min-width: 120px; }

/* ── 多Agent辩论区块 ── */
.da-ma-head { display: flex; justify-content: space-between; align-items: center; }

.rise { color: #ef5350; }
.fall { color: #26a69a; }
</style>
