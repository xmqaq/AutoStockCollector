<template>
  <div class="fp-page">
    <FusionHeader
      :marketState="marketState"
      :activeWeights="activeWeights"
      v-model:topN="topN"
      v-model:candidatePool="candidatePool"
      v-model:selectedStrategyIds="selectedStrategyIds"
      v-model:selectedPhilosophyIds="selectedPhilosophyIds"
      :strategies="strategies"
      :philosophies="philosophies"
      :running="running"
      :loading="loading"
      :showDoneTip="showDoneTip"
      :progress="progress"
      @run-pick="runPick"
      @cancel-pick="cancelPick"
    />

    <!-- ── 仪表盘布局 (方案四) ── -->
    <div class="fp-dashboard-layout" v-if="result || history.length">
      <!-- 顶部信息区：AI总结 & 核心回测数据 (默认折叠) -->
      <el-collapse class="fp-dashboard-top-collapse" v-if="result">
        <el-collapse-item name="insights">
          <template #title>
            <span class="collapse-title">📊 洞察与回测 (AI逻辑总结、策略回测指标)</span>
          </template>
          
          <div class="fp-dashboard-top">
            <!-- AI 总结卡片 -->
            <el-card class="fp-card fp-card-summary" shadow="never">
              <template #header>
                <div class="card-header">
                  <span>🤖 AI 选股逻辑总结</span>
                  <div class="fp-meta-bar">
                    <el-tag size="small" :type="result.mode === 'quick' ? 'warning' : 'info'" effect="plain">
                      {{ result.mode === 'quick' ? '快速版' : '完整版' }}
                    </el-tag>
                    <span class="fp-meta-time">{{ fmtTime(result.timestamp) }}</span>
                  </div>
                </div>
              </template>
              <div v-if="result?.ai_summary" class="md-content fp-summary" v-html="renderMd(result.ai_summary)"></div>
              <el-empty v-else description="暂无 AI 总结（快速版不生成）" :image-size="80" />
              
              <div v-if="result?.picks?.length" class="fp-meta-bar mt-auto">
                <span>全市场 {{ result.universe_count }}</span>
                <el-divider direction="vertical" />
                <span>剔除 {{ result.filtered_count }}</span>
                <el-divider direction="vertical" />
                <span>候选 {{ result.candidate_count }}</span>
                <el-divider direction="vertical" />
                <span>策略 {{ result.strategy_count }}</span>
              </div>
            </el-card>

            <!-- 历史回测卡片 (复用 FusionBacktest) -->
            <el-card class="fp-card fp-card-backtest" shadow="never">
              <template #header>
                <div class="card-header">
                  <span>📈 策略历史回测</span>
                </div>
              </template>
              <div class="fp-backtest-wrapper">
                 <FusionBacktest
                  :isAdmin="isAdmin"
                  v-model:btLimit="btLimit"
                  :btLoading="btLoading"
                  :resetLoading="resetLoading"
                  :backtest="backtest"
                  @load-backtest="loadBacktest"
                  @reset-data="resetData"
                />
              </div>
            </el-card>
          </div>
        </el-collapse-item>
      </el-collapse>

      <!-- 核心表格区 -->
      <el-card v-if="result?.picks?.length" class="fp-card fp-card-table" shadow="never">
        <template #header>
          <div class="card-header">
            <span>🎯 选股结果明细 <el-badge :value="result.picks.length" class="fp-badge" /></span>
          </div>
        </template>
        
        <FusionRebalance
          :hasPicks="!!result?.picks?.length"
          :rebalance="rebalance"
          :rebalanceLoading="rebalanceLoading"
          v-model:investRatio="investRatio"
          :executingAll="executingAll"
          :executing="executing"
          @load-rebalance="loadRebalance"
          @exec-all="execAll"
          @exec-one="execOne"
        />

        <FusionResultTable :picks="result?.picks || []" />
      </el-card>

      <!-- 底部高级功能区 (权重优化 & 历史记录) -->
      <div class="fp-dashboard-bottom">
        <el-collapse class="fp-advanced-collapse">
          <el-collapse-item name="1">
            <template #title>
              <span class="collapse-title">⚙️ 高级配置与历史记录 (权重优化、选股历史)</span>
            </template>
            <div class="fp-advanced-grid">
              <div class="fp-adv-col">
                <h4>权重优化</h4>
                <FusionOptimize
                  :isAdmin="isAdmin"
                  :sigLoading="sigLoading"
                  :optLoading="optLoading"
                  :signals="signals"
                  @load-signals="loadSignals"
                  @do-optimize="doOptimize"
                />
              </div>
              <div class="fp-adv-col">
                <h4>历史记录</h4>
                <FusionHistory
                  :histLoading="histLoading"
                  :history="history"
                  @load-history="loadHistory"
                  @load-result="loadResult"
                />
              </div>
            </div>
          </el-collapse-item>
        </el-collapse>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { renderMd } from '@/utils/markdown'
import { useAuthStore } from '@/stores/authStore'
import { fusionPickApi } from '@/api/fusionPick'
import type {
  FusionPickProgress, FusionPickResult, FusionMarketState,
  FusionBacktestResult, FusionOptSignals, FusionHistoryItem, DimWeights
} from '@/api/fusionPick'
import { strategyPickApi } from '@/api/strategyPick'
import type { RebalanceAdvice, RebalanceOrder } from '@/api/strategyPick'
import { paperApi } from '@/api/paper'

import FusionHeader from './components/FusionHeader.vue'
import FusionResultTable from './components/FusionResultTable.vue'
import FusionRebalance from './components/FusionRebalance.vue'
import FusionBacktest from './components/FusionBacktest.vue'
import FusionOptimize from './components/FusionOptimize.vue'
import FusionHistory from './components/FusionHistory.vue'

const auth = useAuthStore()
const isAdmin = computed(() => auth.isAdmin)

// ── 控制状态 ──
const topN = ref(10)
const candidatePool = ref(50)
const selectedStrategyIds = ref<string[]>([])
const selectedPhilosophyIds = ref<string[]>([])
const strategies = ref<any[]>([])
const philosophies = ref<any[]>([])

const running = ref(false)
const loading = ref(false)
const showDoneTip = ref(false)
const progress = ref<FusionPickProgress>({ is_running: false, progress: 0, status: '' })

const result = ref<FusionPickResult | null>(null)
const marketState = ref<FusionMarketState | null>(null)

// ── 回测 / 优化 / 历史 ──
const btLimit = ref(30)
const btLoading = ref(false)
const backtest = ref<FusionBacktestResult | null>(null)
const sigLoading = ref(false)
const optLoading = ref(false)
const resetLoading = ref(false)
const signals = ref<FusionOptSignals | null>(null)
const histLoading = ref(false)
const history = ref<FusionHistoryItem[]>([])

// 当前生效权重：优先用本次结果，否则市场状态自动权重
const activeWeights = computed<DimWeights | undefined>(
  () => result.value?.weights_used || marketState.value?.weights_optimized || marketState.value?.weights_auto,
)

// ── 展示工具 ──
function stateText(s?: string) { return s === 'bull' ? '牛市' : s === 'bear' ? '熊市' : '震荡市' }
function fmtTime(t?: string | null) {
  if (!t) return ''
  try { return new Date(t).toLocaleString('zh-CN', { hour12: false }) } catch { return t }
}

// ── 数据加载 ──
async function loadMarketState() {
  try { const res = await fusionPickApi.getMarketState(); if (res.data?.success) marketState.value = res.data.data } catch { /* ignore */ }
}
async function loadStrategies() {
  try {
    const res = await strategyPickApi.getStrategies()
    if (res.data?.success) strategies.value = res.data.data || []
  } catch { /* ignore */ }
}
async function loadPhilosophies() {
  try {
    const res = await strategyPickApi.getAgents()
    if (res.data?.success) philosophies.value = (res.data.data || []).filter((a: any) => a.type === 'philosophy')
  } catch { /* ignore */ }
}
async function loadResult(runId?: string) {
  try {
    const res = await fusionPickApi.getResult(runId)
    if (res.data?.success && res.data.data?.picks) { result.value = res.data.data; }
  } catch { /* ignore */ }
}
async function loadHistory() {
  histLoading.value = true
  try { const res = await fusionPickApi.getHistory(); if (res.data?.success) history.value = res.data.data || [] }
  catch { /* ignore */ } finally { histLoading.value = false }
}
async function loadBacktest() {
  btLoading.value = true
  try { const res = await fusionPickApi.getBacktest(btLimit.value); if (res.data?.success) backtest.value = res.data.data }
  catch { ElMessage.error('回测失败') } finally { btLoading.value = false }
}
async function loadSignals() {
  sigLoading.value = true
  try { const res = await fusionPickApi.getOptimizationSignals(); if (res.data?.success) signals.value = res.data.data }
  catch { ElMessage.error('加载优化信号失败') } finally { sigLoading.value = false }
}
async function doOptimize() {
  optLoading.value = true
  try {
    const res = await fusionPickApi.optimizeWeights()
    if (res.data?.success) {
      const d = res.data.data
      if (d?.skipped) ElMessage.warning(d.reason || '样本不足，已跳过')
      else { ElMessage.success(`已更新 ${(d?.states_updated || []).map(stateText).join('、') || '0'} 权重`); await loadMarketState() }
    }
  } catch { ElMessage.error('权重优化失败') } finally { optLoading.value = false }
}

async function resetData() {
  try {
    await ElMessageBox.confirm(
      '将清空：回测快照 + 历史选股结果 + 已优化权重(回归市场默认)。用于清掉旧口径产生的脏数据，让回测从新口径重新积累。此操作不可恢复。',
      '重置回测数据', { type: 'warning', confirmButtonText: '确认重置', cancelButtonText: '取消' },
    )
  } catch { return }  // 取消
  resetLoading.value = true
  try {
    const res = await fusionPickApi.resetData('all')
    if (res.data?.success) {
      const d = res.data.data?.deleted || {}
      ElMessage.success(`已重置：快照 ${d.snapshots || 0} · 历史 ${d.results || 0} · 权重 ${d.weight_config || 0}`)
      backtest.value = null
      signals.value = null
      result.value = null
      await Promise.all([loadHistory(), loadMarketState()])
    }
  } catch { /* client 拦截器已提示 */ } finally { resetLoading.value = false }
}

// ── 一键调仓：建议清单 + 执行到模拟盘（复用量化选股 advisor + paper /trade）──
const rebalance = ref<RebalanceAdvice | null>(null)
const rebalanceLoading = ref(false)
const investRatio = ref(1.0)
const executing = ref<Record<string, boolean>>({})
const executingAll = ref(false)

async function loadRebalance() {
  rebalanceLoading.value = true
  try {
    const res = await fusionPickApi.rebalanceAdvice(0.05, investRatio.value)
    rebalance.value = res.data.data
  } catch { ElMessage.error('生成调仓清单失败') }
  finally { rebalanceLoading.value = false }
}

async function execOne(o: RebalanceOrder): Promise<boolean> {
  if (o.skipped || !o.price) return false
  executing.value[o.code] = true
  try {
    await paperApi.executeTrade({
      code: o.code, action: o.action, shares: o.shares,
      price: o.price, ai_signal: { reason: o.reason, position_advice: 'AI 智选调仓' },
    })
    await loadRebalance()  // 执行后刷新（现金/持仓已变）
    return true
  } catch (e: any) {
    ElMessage.error(`执行失败：${e?.response?.data?.error || e?.message || e}`)
    return false
  } finally { executing.value[o.code] = false }
}

async function execAll() {
  if (!rebalance.value) return
  executingAll.value = true
  try {
    // 先卖后买：卖出释放现金才够买
    const ordered = [...rebalance.value.orders].sort(
      (a, b) => (a.action === 'sell' ? 0 : 1) - (b.action === 'sell' ? 0 : 1))
    for (const o of ordered) {
      if (o.skipped || !o.price) continue
      const ok = await execOne(o)
      if (!ok) break  // 卖出失败即中断，避免后续买入在现金未释放时执行
    }
  } finally { executingAll.value = false }
}

// ── 运行 + 进度（SSE，失败回退轮询） ──
let eventSource: EventSource | null = null
let progressTimer: ReturnType<typeof setInterval> | null = null
let sseTimeout: ReturnType<typeof setTimeout> | null = null

async function runPick() {
  running.value = true
  loading.value = true
  showDoneTip.value = false
  progress.value = { is_running: true, progress: 0, status: '启动中...' }
  try {
    const res = await fusionPickApi.run({
      top_n: topN.value, candidate_pool: candidatePool.value,
      strategy_ids: selectedStrategyIds.value, philosophy_ids: selectedPhilosophyIds.value,
    })
    if (res.data?.success) { ElMessage.info(res.data.message || 'AI 智选已启动'); startProgressSSE() }
    else { ElMessage.error(res.data?.error || '启动失败'); resetRunning() }
  } catch { resetRunning() } finally { loading.value = false }
}

async function cancelPick() {
  try {
    const res = await fusionPickApi.cancel()
    if (res.data?.success) { stopProgressSSE(); stopProgressPolling(); progress.value = { is_running: false, progress: 0, status: '已取消' }; running.value = false }
  } catch { ElMessage.error('取消失败') }
}

function resetRunning() { running.value = false; progress.value = { is_running: false, progress: 0, status: '' } }

function onProgressData(data: FusionPickProgress, stop: () => void) {
  progress.value = data
  if (data.is_running) running.value = true
  if (!data.is_running) {
    stop()
    running.value = false
    if (data.progress >= 100) {
      showDoneTip.value = true
      Promise.all([loadResult(), loadHistory(), loadMarketState()])
      setTimeout(() => { showDoneTip.value = false }, 4000)
    }
  }
}

function startProgressPolling() {
  stopProgressPolling()
  progressTimer = setInterval(async () => {
    try { const res = await fusionPickApi.getProgress(); if (res.data?.data) onProgressData(res.data.data, stopProgressPolling) }
    catch { /* ignore */ }
  }, 2000)
}
function stopProgressPolling() { if (progressTimer) { clearInterval(progressTimer); progressTimer = null } }

function startProgressSSE() {
  stopProgressSSE(); stopProgressPolling()
  eventSource = new EventSource('/api/v1/fusion-pick/progress/stream')
  let received = false
  eventSource.onmessage = (event) => {
    received = true
    if (sseTimeout) { clearTimeout(sseTimeout); sseTimeout = null }
    try { const res = JSON.parse(event.data); if (res?.data) onProgressData(res.data, stopProgressSSE) } catch { /* ignore */ }
  }
  eventSource.onerror = () => {
    if (received) { stopProgressSSE(); running.value = false; progress.value = { is_running: false, progress: 0, status: '连接断开' } }
  }
  sseTimeout = setTimeout(() => { if (!received) { stopProgressSSE(); startProgressPolling() } }, 3000)
}
function stopProgressSSE() {
  if (eventSource) { eventSource.close(); eventSource = null }
  if (sseTimeout) { clearTimeout(sseTimeout); sseTimeout = null }
}

onMounted(async () => {
  await Promise.all([loadMarketState(), loadStrategies(), loadPhilosophies(), loadResult(), loadHistory()])
  // 如果后台正有任务在跑，接上进度
  try {
    const res = await fusionPickApi.getProgress()
    if (res.data?.data?.is_running) { running.value = true; startProgressSSE() }
  } catch { /* ignore */ }
})
onUnmounted(() => { stopProgressSSE(); stopProgressPolling() })
</script>

<style scoped>
.fp-page { display: flex; flex-direction: column; gap: 16px; }

/* ───── 方案四 Dashboard 布局样式 ───── */
.fp-dashboard-layout {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

/* 顶部折叠面板样式 */
.fp-dashboard-top-collapse {
  border: 1px solid var(--el-border-color-light);
  border-radius: 12px;
  overflow: hidden;
  margin-bottom: 0;
  box-shadow: 0 2px 8px var(--bg-hover-subtle);
  background-color: var(--el-bg-color);
  transition: all 0.3s ease;
}
.fp-dashboard-top-collapse:hover {
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
  border-color: var(--el-border-color);
}
.fp-dashboard-top-collapse :deep(.el-collapse-item__header) {
  padding: 0 20px;
  background-color: var(--el-fill-color-light);
  font-weight: 600;
  color: var(--el-color-primary);
  height: 56px;
  line-height: 56px;
  font-size: 15px;
  border-bottom: 1px solid var(--el-border-color-lighter);
}
.fp-dashboard-top-collapse :deep(.el-collapse-item__header.is-active) {
  border-bottom-color: var(--el-border-color-light);
}
.fp-dashboard-top-collapse :deep(.el-collapse-item__wrap) {
  border-bottom: none;
}
.fp-dashboard-top-collapse :deep(.el-collapse-item__content) {
  padding: 20px;
  background-color: var(--el-bg-color-page);
}

.fp-dashboard-top {
  display: grid;
  grid-template-columns: minmax(300px, 1fr) minmax(400px, 1fr);
  gap: 16px;
}

.fp-card {
  border-radius: 12px;
  border: 1px solid var(--el-border-color-lighter);
  box-shadow: 0 1px 3px rgba(0, 0, 0, .04);
  display: flex;
  flex-direction: column;
}
.fp-card :deep(.el-card__header) {
  padding: 12px 16px;
  border-bottom: 1px solid var(--el-border-color-lighter);
  background-color: var(--el-fill-color-light);
}
.fp-card :deep(.el-card__body) {
  padding: 16px;
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden; /* 防止内容撑破 */
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-weight: 600;
  color: var(--text-primary);
}

.fp-badge { margin-left: 4px; }
.fp-meta-bar { display: flex; align-items: center; gap: 6px; font-size: 12px; color: var(--text-secondary); flex-wrap: wrap; }
.fp-meta-time { margin-left: auto; }
.mt-auto { margin-top: auto; padding-top: 16px; }

/* AI总结卡片内样式 */
.fp-summary { line-height: 1.6; font-size: 14px; }
.fp-card-summary { height: 100%; }

/* 回测卡片内样式 */
.fp-card-backtest { height: 100%; }
.fp-backtest-wrapper {
  overflow-y: auto;
  max-height: 400px; /* 限制回测内容最大高度，避免卡片过高 */
  margin: -8px; /* 抵消 card body 的部分 padding */
  padding: 8px;
}

/* 核心表格区 */
.fp-card-table {
  overflow: visible; /* 表格本身有滚动条处理 */
}
.fp-card-table :deep(.el-card__body) {
  padding: 0; /* 表格自带 padding 或边距，这里清空让它贴边 */
}
.fp-card-table :deep(.fp-rebalance-panel) {
  margin: 16px 16px 0; /* 给 rebalance 面板加点边距 */
}

/* 高级配置区 */
.fp-dashboard-bottom {
  margin-top: 8px;
}
.fp-advanced-collapse {
  border: 1px solid var(--el-border-color-light);
  border-radius: 12px;
  overflow: hidden;
  box-shadow: 0 2px 8px var(--bg-hover-subtle);
  background-color: var(--el-bg-color);
  transition: all 0.3s ease;
}
.fp-advanced-collapse:hover {
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
  border-color: var(--el-border-color);
}
.fp-advanced-collapse :deep(.el-collapse-item__header) {
  padding: 0 20px;
  background-color: var(--el-fill-color-light);
  font-weight: 600;
  color: var(--text-regular);
  height: 56px;
  line-height: 56px;
  font-size: 15px;
  border-bottom: 1px solid var(--el-border-color-lighter);
}
.fp-advanced-collapse :deep(.el-collapse-item__header.is-active) {
  border-bottom-color: var(--el-border-color-light);
}
.fp-advanced-collapse :deep(.el-collapse-item__wrap) {
  border-bottom: none;
}
.collapse-title {
  font-size: 15px;
}
.fp-advanced-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 24px;
  padding: 16px;
}
.fp-adv-col h4 {
  margin: 0 0 16px 0;
  color: var(--text-primary);
  font-size: 15px;
  padding-bottom: 8px;
  border-bottom: 1px dashed var(--el-border-color-lighter);
}

@media (max-width: 1200px) {
  .fp-dashboard-top, .fp-advanced-grid {
    grid-template-columns: 1fr; /* 屏幕较窄时变为单列 */
  }
}
</style>
