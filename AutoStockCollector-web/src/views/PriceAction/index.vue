<template>
  <div class="pa-page">
    <el-card shadow="never" class="pa-head">
      <div class="pa-head-row">
        <el-select v-model="symbol" filterable allow-create clearable placeholder="输入股票代码 如 300750"
          style="width:180px" @keyup.enter="analyze">
          <el-option v-for="s in presetStocks" :key="s.code" :label="`${s.code} ${s.name}`" :value="s.code" />
        </el-select>
        <el-radio-group v-model="timeframe" size="small">
          <el-radio-button value="daily">日线</el-radio-button>
          <el-radio-button value="weekly">周线</el-radio-button>
          <el-radio-button value="30m">30分</el-radio-button>
        </el-radio-group>
        <el-input-number v-model="riskPct" :min="0.5" :max="5" :step="0.5" size="small" style="width:80px" />
        <span class="hint">%</span>
        <el-input-number v-model="accountBalance" :min="10000" :max="10000000" :step="50000" size="small" style="width:110px" />
        <span class="hint">资金</span>
        <el-checkbox v-model="useAi" size="small" style="margin-left:4px">AI增强</el-checkbox>
        <el-button type="primary" :loading="loading" :disabled="loading || !symbol" @click="analyze">
          {{ loading ? `${taskProgress}%` : '分析' }}
        </el-button>
        <el-button text size="small" :icon="Refresh" @click="loadHistory">历史</el-button>
      </div>
    </el-card>

    <!-- 进度展示 -->
    <el-card v-if="loading" shadow="never" class="pa-progress-card">
      <div class="pa-steps">
        <div v-for="(step, i) in steps" :key="i" class="pa-step" :class="stepClass(i)">
          <span class="pa-step-icon">{{ stepIcon(i) }}</span>
          <span class="pa-step-label">{{ step.label }}</span>
        </div>
      </div>
      <el-progress :percentage="taskProgress" :stroke-width="10" striped striped-flow style="margin-top:10px" />
      <p class="pa-step-msg">{{ taskMessage }}</p>
    </el-card>

    <!-- 结果 -->
    <div v-if="result" class="pa-result">
      <!-- 信号横幅 -->
      <div class="pa-signal-banner" :class="signalBannerClass">
        <div class="pa-banner-left">
          <div class="pa-stock-title">
            {{ result.name || result.symbol }}
            <span class="pa-stock-code">{{ result.symbol }}</span>
          </div>
          <div class="pa-stock-price">¥{{ result.current_price?.toFixed(2) }}</div>
        </div>
        <div class="pa-banner-center">
          <div class="pa-signal-badge">{{ signalLabel(result.signal) }}</div>
          <div class="pa-confidence">
            <span v-for="i in 5" :key="i" :class="{ active: i <= result.confidence }">★</span>
            <span class="pa-cfl">{{ result.confidence }}/5</span>
          </div>
        </div>
        <div class="pa-banner-right">
          <div class="pa-meta-item"><span>趋势</span><b>{{ trendLabel(result.trend) }}</b></div>
          <div class="pa-meta-item"><span>ATR</span><b>{{ result.atr?.toFixed(2) }}</b></div>
          <div class="pa-meta-item"><span>抓取</span><b>{{ result.sweeps_detected }}次</b></div>
        </div>
      </div>

      <!-- 价格梯 -->
      <div v-if="hasLevels" class="pa-ladder-card">
        <div class="pa-ladder">
          <div class="pa-ladder-track">
            <div class="pa-ladder-bg" :style="ladderBgStyle" />
            <div v-for="(lv, i) in ladderLevels" :key="i" class="pa-lv-marker"
              :style="{ left: lv.pct + '%' }">
              <span class="pa-lv-dot" :style="{ background: lv.color }" />
              <span class="pa-lv-label" :style="{ color: lv.color }">{{ lv.label }} ¥{{ lv.price }}</span>
            </div>
          </div>
        </div>
      </div>

      <div class="pa-body-grid">
        <div class="pa-main-col">
          <!-- 信号依据 -->
          <el-card v-if="result.reasons?.length" shadow="never" class="pa-card">
            <template #header><span>信号依据</span></template>
            <ul class="pa-reasons">
              <li v-for="(r, i) in result.reasons" :key="i">
                <el-tag size="small" :type="result.signal?.includes('BUY') ? 'danger' : 'success'">
                  {{ result.signal?.includes('BUY') ? '多' : '空' }}
                </el-tag>
                {{ r }}
              </li>
            </ul>
          </el-card>

          <el-card v-if="result.patterns?.length" shadow="never" class="pa-card">
            <template #header><span>K 线形态</span></template>
            <el-tag v-for="p in result.patterns" :key="p" size="small" style="margin:2px 4px">{{ p }}</el-tag>
          </el-card>

          <el-card v-if="result.zones?.length" shadow="never" class="pa-card">
            <template #header><span>供需关键区</span></template>
            <div v-for="(z, i) in result.zones" :key="i" class="pa-zone-bar">
              <span class="pa-zl">{{ zoneType(z, result.signal) }}</span>
              <span class="pa-zr">{{ z.low?.toFixed?.(2) ?? z.price_min }} — {{ z.high?.toFixed?.(2) ?? z.price_max }}</span>
              <span v-if="z.strength" class="pa-zs">强度 {{ z.strength }}/10</span>
            </div>
          </el-card>

          <el-card v-if="result.fib_levels && Object.keys(result.fib_levels).length" shadow="never" class="pa-card">
            <template #header><span>斐波那契</span></template>
            <div class="pa-fib-grid">
              <div v-for="(v, k) in result.fib_levels" :key="k" class="pa-fib-item">
                <span class="pa-fib-label">{{ k }}</span>
                <span class="pa-fib-val">¥{{ v?.toFixed(2) }}</span>
              </div>
            </div>
          </el-card>

          <!-- AI 分析结果 -->
          <el-card v-if="result.ai_commentary" shadow="never" class="pa-card pa-ai-card">
            <template #header>
              <span>🤖 AI 交易解读</span>
              <el-tag size="small" type="warning" effect="plain">LLM 分析</el-tag>
            </template>
            <div class="pa-ai-content">{{ result.ai_commentary }}</div>
          </el-card>
          <el-card v-else-if="useAi && result.signal !== 'NO_DATA' && result.signal !== 'ERROR'" shadow="never" class="pa-card">
            <template #header><span>🤖 AI 解读</span></template>
            <div class="pa-ai-na">本次分析未启用 AI 增强，或暂无可用的 LLM 服务</div>
          </el-card>
        </div>

        <div class="pa-side-col">
          <div v-if="result.trade_plan" class="pa-trade-card">
            <div class="pa-trade-header" :class="result.trade_plan.direction === 'long' ? 'pa-trade-buy' : 'pa-trade-sell'">
              <span class="pa-trade-dir">{{ result.trade_plan.direction === 'long' ? '📈 做多计划' : '📉 做空计划' }}</span>
              <span class="pa-trade-rr">R:R {{ result.trade_plan.r_r_ratio }}</span>
            </div>
            <div class="pa-trade-body">
              <div class="pa-trade-row">
                <div class="pa-trade-item">
                  <span class="pa-ti-label">入场</span>
                  <span class="pa-ti-val">¥{{ result.trade_plan.entry?.toFixed(2) }}</span>
                </div>
                <div class="pa-trade-item pa-ti-sl">
                  <span class="pa-ti-label">止损</span>
                  <span class="pa-ti-val">¥{{ result.trade_plan.stop_loss?.toFixed(2) }}</span>
                </div>
                <div class="pa-trade-item pa-ti-tp">
                  <span class="pa-ti-label">止盈</span>
                  <span class="pa-ti-val">¥{{ result.trade_plan.take_profit?.toFixed(2) }}</span>
                </div>
              </div>
              <el-divider style="margin:8px 0" />
              <div class="pa-trade-detail">
                <div><span>仓位</span><b>{{ result.trade_plan.position_size }} 股</b></div>
                <div><span>价值</span><b>¥{{ result.trade_plan.position_value?.toFixed(0) }}</b></div>
                <div><span>风险</span><b style="color:#e6a23c">¥{{ result.trade_plan.total_risk?.toFixed(0) }}</b></div>
                <div><span>每股风险</span><b>¥{{ result.trade_plan.risk_per_share?.toFixed(2) }}</b></div>
              </div>
            </div>
          </div>

          <div v-else-if="result.signal === 'NO_DATA'" class="pa-trade-card pa-trade-na">
            <div class="pa-trade-body" style="text-align:center;padding:20px">
              <el-empty :description="result.error || '数据不足'" :image-size="60" />
            </div>
          </div>
          <div v-else class="pa-trade-card pa-trade-na">
            <div class="pa-trade-body" style="text-align:center;padding:20px">
              <span style="font-size:18px">⚖️</span>
              <p style="margin:6px 0 0;font-size:13px;color:var(--text-secondary)">当前无明显交易信号，建议观望</p>
            </div>
          </div>

          <el-card shadow="never" class="pa-card">
            <template #header><span>切换周期</span></template>
            <div class="pa-tf-switch">
              <el-button v-for="tf in ['daily','weekly','30m']" :key="tf" size="small"
                :type="timeframe === tf ? 'primary' : 'default'"
                :disabled="timeframe === tf || loading" @click="switchTimeframe(tf)">
                {{ tf === 'daily' ? '日线' : tf === 'weekly' ? '周线' : '30分' }}
              </el-button>
            </div>
            <el-checkbox v-model="useAi" size="small" style="margin-top:8px">AI 增强分析</el-checkbox>
          </el-card>

          <el-button v-if="result" text size="small" @click="result = null; taskProgress = 0">← 新查询</el-button>
        </div>
      </div>
    </div>

    <el-card v-if="!result && !loading" shadow="never" class="pa-history">
      <template #header><span>分析记录</span></template>
      <div v-if="history.length === 0" class="empty-state">
        <el-empty description="暂无分析记录，请输入股票代码开始分析" />
      </div>
      <el-table v-else :data="history" stripe size="small" highlight-current-row @row-click="viewHistory">
        <el-table-column prop="created_at" label="时间" width="160" />
        <el-table-column label="股票" width="200">
          <template #default="{ row }">
            <el-tag v-for="s in row.symbols" :key="s" size="small" style="margin-right:4px">{{ s }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="timeframe" label="周期" width="70" align="center">
          <template #default="{ row }">{{ row.timeframe === 'daily' ? '日线' : row.timeframe === 'weekly' ? '周线' : row.timeframe }}</template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'
import { priceActionApi, type PaSignal } from '@/api/priceAction'

const route = useRoute()

const presetStocks = [
  { code: '300750', name: '宁德时代' },
  { code: '002709', name: '天赐材料' },
  { code: '002594', name: '比亚迪' },
  { code: '600519', name: '贵州茅台' },
  { code: '300014', name: '亿纬锂能' },
  { code: '300124', name: '汇川技术' },
  { code: '688041', name: '海光信息' },
  { code: '300308', name: '中际旭创' },
]

const symbol = ref('')
const timeframe = ref('daily')
const riskPct = ref(2)
const accountBalance = ref(100000)
const useAi = ref(false)
const loading = ref(false)
const result = ref<PaSignal | null>(null)
const history = ref<any[]>([])
const taskId = ref('')
const taskProgress = ref(0)
const taskMessage = ref('')
let pollTimer: ReturnType<typeof setInterval> | null = null
let pollTimeoutTimer: ReturnType<typeof setTimeout> | null = null
const POLL_TIMEOUT_MS = 5 * 60 * 1000 // 5分钟

const stepDefs = [
  { label: '数据获取', pct: 20 },
  { label: '市场结构', pct: 50 },
  { label: '供需区识别', pct: 65 },
  { label: '信号生成', pct: 75 },
  { label: '风控计算', pct: 85 },
  { label: 'AI 分析', pct: 95 },
  { label: '完成', pct: 100 },
]

const steps = computed(() => stepDefs.filter(s => s.label !== 'AI 分析' || useAi.value))

function stepClass(i: number) {
  const pct = taskProgress.value
  const s = steps.value[i]
  if (!s) return ''
  if (pct >= s.pct) return 'pa-step-done'
  if (pct >= s.pct - 10) return 'pa-step-active'
  return ''
}

function stepIcon(i: number) {
  const s = steps.value[i]
  if (!s) return '○'
  if (taskProgress.value >= s.pct) return '●'
  if (taskProgress.value >= s.pct - 10) return '◐'
  return '○'
}

if (route.query.symbol) {
  symbol.value = route.query.symbol as string
  if (route.query.timeframe) timeframe.value = route.query.timeframe as string
}

function signalLabel(sig: string | undefined) {
  const m: Record<string, string> = {
    BUY_SETUP: '买入信号', SELL_SETUP: '卖出信号',
    WEAK_BUY: '弱买入', WEAK_SELL: '弱卖出',
    NEUTRAL: '中性', NO_TRADE: '无信号',
    NO_DATA: '数据不足', ERROR: '错误',
  }
  return m[sig || ''] || sig || ''
}

function trendLabel(t: string | undefined) {
  const m: Record<string, string> = {
    Bullish: '上升', 'Strong Bullish': '强势上升',
    Bearish: '下降', 'Strong Bearish': '强势下降',
    Ranging: '震荡',
  }
  return m[t || ''] || t || '-'
}

function zoneType(z: any, sig: string | undefined) {
  if (z.type) return z.type === 'Demand' ? '需求区' : '供应区'
  return sig?.includes('BUY') ? '需求区' : '供应区'
}

const signalBannerClass = computed(() => {
  const s = result.value?.signal
  if (s === 'BUY_SETUP' || s === 'WEAK_BUY') return 'pa-banner-buy'
  if (s === 'SELL_SETUP' || s === 'WEAK_SELL') return 'pa-banner-sell'
  return 'pa-banner-neutral'
})

const hasLevels = computed(() => {
  const r = result.value
  if (!r) return false
  return !!(r.trade_plan || r.fib_levels || r.zones?.length)
})

interface LadderLevel { label: string; price: number; pct: number; color: string; role: string }

const ladderLevels = computed(() => {
  const r = result.value
  if (!r) return []
  const price = r.current_price || 0
  const all: { label: string; price: number; role: string }[] = []
  const tp = r.trade_plan
  if (tp?.stop_loss) all.push({ label: '止损 SL', price: tp.stop_loss, role: 'sl' })
  if (tp?.take_profit) all.push({ label: '止盈 TP', price: tp.take_profit, role: 'tp' })
  if (tp?.entry) all.push({ label: '入场 Entry', price: tp.entry, role: 'entry' })
  if (r.fib_levels) Object.entries(r.fib_levels).forEach(([k, v]) => all.push({ label: `Fib ${k}`, price: v as number, role: 'fib' }))
  if (r.zones?.length) r.zones.forEach((z: any, i: number) => {
    const hi = z.high ?? z.price_max; const lo = z.low ?? z.price_min
    if (hi) all.push({ label: `区${i + 1}顶`, price: hi, role: 'zone' })
    if (lo) all.push({ label: `区${i + 1}底`, price: lo, role: 'zone' })
  })
  all.push({ label: '当前价', price, role: 'current' })
  all.sort((a, b) => a.price - b.price)
  const minP = all[0]?.price || price - 10
  const maxP = all[all.length - 1]?.price || price + 10
  const range = maxP - minP || 1
  const pad = range * 0.08
  return all.map(lv => {
    let color = '#909399'
    if (lv.role === 'sl') color = '#f56c6c'
    else if (lv.role === 'tp') color = '#67c23a'
    else if (lv.role === 'entry') color = '#409eff'
    else if (lv.role === 'current') color = '#303133'
    else if (lv.role === 'fib') color = '#e6a23c'
    return { label: lv.label, price: lv.price, pct: ((lv.price - minP + pad) / (range + 2 * pad)) * 100, color, role: lv.role }
  })
})

const ladderBgStyle = computed(() => {
  const lv = ladderLevels.value
  if (!lv.length) return {}
  const cp = lv.find(l => l.role === 'current')
  if (!cp) return {}
  return {
    background: `linear-gradient(to right, ${lv.find(l => l.role === 'sl')?.color || '#f56c6c'} 0%, transparent ${Math.max(0, cp.pct - 5)}%, transparent ${Math.min(100, cp.pct + 5)}%, ${lv.find(l => l.role === 'tp')?.color || '#67c23a'} 100%)`,
    opacity: 0.08,
  }
})

async function loadHistory() {
  try {
    const res = await priceActionApi.getHistory()
    if (res.data?.success) history.value = res.data.data
  } catch { /* ignore */ }
}

async function analyze() {
  if (!symbol.value) { ElMessage.warning('请输入股票代码'); return }
  loading.value = true
  result.value = null
  taskProgress.value = 0
  taskMessage.value = '正在提交任务...'

  try {
    const res = await priceActionApi.run(
      [symbol.value], timeframe.value,
      riskPct.value / 100, accountBalance.value,
      useAi.value,
    )
    if (!res.data?.success) { ElMessage.error('提交失败'); loading.value = false; return }
    taskId.value = res.data.task_id
    taskMessage.value = '任务已提交'
    startPolling()
  } catch {
    ElMessage.error('请求失败')
    loading.value = false
  }
}

function startPolling() {
  stopPolling()
  pollTimer = setInterval(pollResult, 1500)
  pollTimeoutTimer = setTimeout(() => {
    stopPolling()
    loading.value = false
    taskProgress.value = 0
    taskMessage.value = ''
    ElMessage.warning('分析超时（5分钟），请重试')
  }, POLL_TIMEOUT_MS)
}

function stopPolling() {
  if (pollTimer) { clearInterval(pollTimer); pollTimer = null }
  if (pollTimeoutTimer) { clearTimeout(pollTimeoutTimer); pollTimeoutTimer = null }
}

async function pollResult() {
  if (!taskId.value) return
  try {
    const res = await priceActionApi.getResult(taskId.value)
    const data = res.data
    if (!data?.success) return
    taskProgress.value = data.progress || 0
    taskMessage.value = data.message || ''

    if (data.status === 'completed') {
      stopPolling()
      loading.value = false
      if (data.data?.length) {
        const sig = data.data[0] as PaSignal
        result.value = sig
        if (sig.signal === 'NO_DATA' || sig.signal === 'ERROR') {
          ElMessage.warning(sig.error || '分析失败，数据不足')
        } else if (sig.signal === 'BUY_SETUP' || sig.signal === 'SELL_SETUP') {
          ElMessage.success(`${signalLabel(sig.signal)}，置信度 ${sig.confidence}/5`)
        } else {
          ElMessage.info(`当前${signalLabel(sig.signal)}`)
        }
        if (sig.ai_commentary) {
          ElMessage({ message: 'AI 交易解读已完成', type: 'success', duration: 2000 })
        }
      }
      loadHistory()
    } else if (data.status === 'failed') {
      stopPolling()
      loading.value = false
      ElMessage.error(data.message || '分析失败')
    }
  } catch { /* ignore */ }
}

function switchTimeframe(tf: string) {
  timeframe.value = tf
  analyze()
}

function viewHistory(row: any) {
  symbol.value = row.symbols?.[0] || ''
  timeframe.value = row.timeframe || 'daily'
  if (symbol.value) analyze()
}

onMounted(() => {
  loadHistory()
  if (symbol.value) analyze()
})

onUnmounted(() => { stopPolling() })
</script>

<style scoped>
.pa-page { padding: 16px; max-width: 1200px; margin: 0 auto; }
.pa-head { margin-bottom: 12px; }
.pa-head-row { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.hint { font-size: 12px; color: var(--text-secondary, #909399); white-space: nowrap; }

/* 进度展示 */
.pa-progress-card { margin-bottom: 12px; }
.pa-steps { display: flex; gap: 4px; justify-content: center; flex-wrap: wrap; }
.pa-step { display: flex; align-items: center; gap: 4px; padding: 4px 10px; border-radius: 12px; font-size: 12px; background: var(--bg-page, #f5f7fa); color: var(--text-secondary); }
.pa-step-done { background: #67c23a; color: #fff; }
.pa-step-active { background: #e6a23c; color: #fff; }
.pa-step-icon { font-size: 10px; }
.pa-step-msg { margin: 6px 0 0; font-size: 12px; color: var(--text-secondary, #909399); text-align: center; }

/* 信号横幅 */
.pa-signal-banner { display: flex; align-items: center; justify-content: space-between; padding: 16px 20px; border-radius: 8px; margin-bottom: 12px; color: #fff; }
.pa-banner-buy { background: linear-gradient(135deg, #c53929 0%, #e67e22 100%); }
.pa-banner-sell { background: linear-gradient(135deg, #1a7a3a 0%, #27ae60 100%); }
.pa-banner-neutral { background: linear-gradient(135deg, #5b6abf 0%, #8e99d6 100%); }
.pa-stock-title { font-size: 20px; font-weight: bold; }
.pa-stock-code { font-size: 12px; opacity: 0.8; margin-left: 6px; }
.pa-stock-price { font-size: 32px; font-weight: bold; margin-top: 2px; }
.pa-banner-center { text-align: center; }
.pa-signal-badge { font-size: 22px; font-weight: bold; letter-spacing: 2px; }
.pa-confidence span { font-size: 22px; color: rgba(255,255,255,0.4); }
.pa-confidence span.active { color: #ffd700; }
.pa-cfl { font-size: 12px; margin-left: 6px; color: rgba(255,255,255,0.8); }
.pa-banner-right { display: flex; gap: 16px; }
.pa-meta-item { text-align: center; }
.pa-meta-item span { display: block; font-size: 11px; opacity: 0.7; }
.pa-meta-item b { font-size: 14px; }

.pa-ladder-card { background: var(--bg-card, #fff); border-radius: 8px; padding: 16px 20px; margin-bottom: 12px; border: 1px solid var(--border-color, #ebeef5); }
.pa-ladder-track { position: relative; height: 36px; background: var(--border-color, #eee); border-radius: 18px; margin: 0 4px; }
.pa-ladder-bg { position: absolute; inset: 0; border-radius: 18px; }
.pa-lv-marker { position: absolute; top: 50%; transform: translate(-50%, -50%); }
.pa-lv-dot { display: block; width: 12px; height: 12px; border-radius: 50%; border: 2px solid #fff; margin: 0 auto; box-shadow: 0 1px 3px rgba(0,0,0,0.3); }
.pa-lv-label { display: block; font-size: 10px; text-align: center; white-space: nowrap; margin-top: 2px; font-weight: bold; }

.pa-body-grid { display: grid; grid-template-columns: 1fr 300px; gap: 12px; margin-bottom: 12px; }
.pa-main-col { display: flex; flex-direction: column; gap: 12px; }
.pa-side-col { display: flex; flex-direction: column; gap: 12px; }
.pa-card :deep(.el-card__header) { font-weight: bold; font-size: 14px; padding: 10px 16px; }

.pa-reasons { list-style: none; padding: 0; margin: 0; }
.pa-reasons li { padding: 6px 0; display: flex; align-items: flex-start; font-size: 13px; border-bottom: 1px solid var(--border-color, #ebeef5); }
.pa-reasons li:last-child { border-bottom: none; }

.pa-zone-bar { display: flex; align-items: center; gap: 12px; padding: 6px 0; border-bottom: 1px solid var(--border-color, #ebeef5); font-size: 13px; }
.pa-zone-bar:last-child { border-bottom: none; }
.pa-zl { font-weight: bold; min-width: 60px; }
.pa-zr { font-family: monospace; }
.pa-zs { color: var(--text-secondary); font-size: 12px; }

.pa-fib-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 6px; }
.pa-fib-item { display: flex; justify-content: space-between; padding: 4px 8px; background: var(--bg-page, #f5f7fa); border-radius: 4px; font-size: 13px; }
.pa-fib-label { color: var(--text-secondary); }
.pa-fib-val { font-family: monospace; font-weight: bold; }

/* AI 解读 */
.pa-ai-card { border-left: 3px solid #e6a23c; }
.pa-ai-content { font-size: 13px; line-height: 1.7; white-space: pre-wrap; color: var(--text-primary); }
.pa-ai-na { font-size: 12px; color: var(--text-secondary); text-align: center; padding: 10px; }

.pa-trade-card { background: var(--bg-card, #fff); border-radius: 8px; overflow: hidden; border: 1px solid var(--border-color, #ebeef5); }
.pa-trade-na { border: 1px dashed var(--border-color, #d9d9d9); }
.pa-trade-header { padding: 12px 16px; display: flex; justify-content: space-between; align-items: center; color: #fff; }
.pa-trade-buy { background: linear-gradient(135deg, #c53929, #e67e22); }
.pa-trade-sell { background: linear-gradient(135deg, #1a7a3a, #27ae60); }
.pa-trade-dir { font-size: 16px; font-weight: bold; }
.pa-trade-rr { font-size: 13px; opacity: 0.9; }
.pa-trade-body { padding: 12px 16px; }
.pa-trade-row { display: flex; gap: 8px; }
.pa-trade-item { flex: 1; text-align: center; padding: 8px 4px; border-radius: 6px; background: var(--bg-page, #f5f7fa); }
.pa-ti-label { display: block; font-size: 11px; color: var(--text-secondary); }
.pa-ti-val { display: block; font-size: 16px; font-weight: bold; margin-top: 2px; }
.pa-ti-sl .pa-ti-val { color: #f56c6c; }
.pa-ti-tp .pa-ti-val { color: #67c23a; }
.pa-trade-detail { display: grid; grid-template-columns: 1fr 1fr; gap: 6px; }
.pa-trade-detail div { display: flex; justify-content: space-between; font-size: 13px; padding: 2px 0; }
.pa-trade-detail span { color: var(--text-secondary); }

.pa-tf-switch { display: flex; gap: 6px; }
.pa-tf-switch .el-button { flex: 1; }

.pa-history { margin-bottom: 16px; }
.empty-state { padding: 40px 0; }

@media (max-width: 768px) {
  .pa-body-grid { grid-template-columns: 1fr; }
  .pa-signal-banner { flex-direction: column; text-align: center; gap: 10px; }
  .pa-banner-right { justify-content: center; }
}
</style>
