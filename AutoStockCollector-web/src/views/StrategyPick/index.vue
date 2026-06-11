<template>
  <div class="sp-page">
    <!-- 顶部控制栏 -->
    <div class="sp-toolbar">
      <div class="sp-title-group">
        <span class="sp-title">策略选股</span>
        <span class="sp-subtitle">多策略合并 · 多Agent深度分析 · 投资哲学辩论</span>
      </div>
      <div class="sp-controls">
        <el-input v-model.number="topN" size="small" style="width:110px" :disabled="running">
          <template #prepend>精选 N</template>
        </el-input>
        <el-button type="primary" size="small" :loading="running" :disabled="running || selectedIds.length === 0" @click="runPick">
          {{ running ? '分析中...' : '开始选股' }}
        </el-button>
        <el-button size="small" :loading="loading" @click="loadResult">刷新结果</el-button>
      </div>
    </div>

    <!-- 折叠选择区 -->
    <el-collapse v-model="collapseActive" accordion class="sp-collapse-group">
      <el-collapse-item name="strategy">
        <template #title>
          <div class="sp-selector-header sp-collapse-header">
            <span class="sp-selector-title">选择策略</span>
            <el-button size="small" text @click.stop="toggleAll">全选 / 反选</el-button>
          </div>
        </template>
        <div v-loading="strategiesLoading" class="sp-strategy-list">
          <div v-if="strategies.length === 0 && !strategiesLoading" class="sp-empty-hint">暂无可用策略，请先在策略管理中创建</div>
          <label v-for="s in strategies" :key="s._id" class="sp-strategy-chip" :class="{ checked: selectedIds.includes(s._id) }">
            <input type="checkbox" :value="s._id" v-model="selectedIds" class="sp-check" />
            <span class="sp-chip-name">{{ s.name }}</span>
            <span class="sp-chip-desc">{{ s.description || '无描述' }}</span>
          </label>
        </div>
      </el-collapse-item>

      <el-collapse-item name="llm">
        <template #title>
          <div class="sp-selector-header sp-collapse-header">
            <span class="sp-selector-title">AI 分析 Agent（深度分析用）</span>
            <el-button size="small" text @click.stop="toggleAllByType('llm')">全选 / 反选</el-button>
          </div>
        </template>
        <div v-loading="agentsLoading" class="sp-strategy-list">
          <div v-if="llmAgents.length === 0 && !agentsLoading" class="sp-empty-hint">暂无可用 Agent</div>
          <label v-for="a in llmAgents" :key="a.id" class="sp-strategy-chip agent-chip" :class="{ checked: selectedAgentIds.includes(a.id) }">
            <input type="checkbox" :value="a.id" v-model="selectedAgentIds" class="sp-check" />
            <span class="sp-chip-name">{{ a.name }}</span>
            <span class="sp-chip-desc">{{ a.description || a.role || '' }}</span>
          </label>
        </div>
      </el-collapse-item>

      <el-collapse-item name="philosophy">
        <template #title>
          <div class="sp-selector-header sp-collapse-header">
            <span class="sp-selector-title">投资哲学 Agent（辩论阶段用）</span>
            <el-button size="small" text @click.stop="toggleAllByType('philosophy')">全选 / 反选</el-button>
          </div>
        </template>
        <div v-loading="agentsLoading" class="sp-strategy-list">
          <div v-if="philosophyAgents.length === 0 && !agentsLoading" class="sp-empty-hint">暂无可用投资哲学 Agent</div>
          <label v-for="a in philosophyAgents" :key="a.id" class="sp-strategy-chip philosophy-chip" :class="{ checked: selectedPhilosophyIds.includes(a.id) }">
            <input type="checkbox" :value="a.id" v-model="selectedPhilosophyIds" class="sp-check" />
            <span class="sp-chip-name">{{ a.name }}</span>
            <span class="sp-chip-desc">{{ a.description || a.archetype || '' }}</span>
          </label>
        </div>
      </el-collapse-item>
    </el-collapse>

    <!-- 进度条 -->
    <div v-if="progress.is_running || showDoneTip" class="sp-progress-box">
      <template v-if="progress.is_running">
        <div class="sp-progress-header">策略选股执行中</div>
        <el-progress :percentage="progress.progress" :stroke-width="14" :color="'#5a7af0'" />
        <div class="sp-progress-status">{{ progress.status }}</div>
      </template>
      <template v-else-if="showDoneTip">
        <div class="sp-progress-done">策略选股完成，结果已更新</div>
      </template>
    </div>

    <!-- 统计信息 -->
    <div v-if="result" class="sp-meta">
      <span>策略数：{{ result.strategy_count }}</span>
      <span>合并候选：{{ result.merged_count }} 只</span>
      <span>精选：{{ result.selected_count }} 只</span>
      <span>更新：{{ fmtTime(result.timestamp) }}</span>
    </div>

    <!-- 策略入选统计 -->
    <div v-if="result?.strategy_stats && Object.keys(result.strategy_stats).length" class="sp-stats">
      <span v-for="(count, name) in result.strategy_stats" :key="name" class="sp-stat-tag">
        {{ name }} <b>{{ count }}</b> 只
      </span>
    </div>

    <!-- 买卖信号 -->
    <div v-if="result?.trade_signals?.length" class="sp-signals-box">
      <div class="sp-signals-header">
        <span class="sp-signals-title">买卖信号建议（基于当前持仓）</span>
      </div>
      <div class="sp-signals-summary">
        <span v-for="g in signalGroups" :key="g.action" class="sp-signal-summary-tag" :class="'sp-ss-' + g.action">{{ g.action }} {{ g.count }} 只</span>
      </div>
      <div class="sp-signals-table-wrap">
        <table class="sp-signals-table">
          <thead><tr>
            <th>代码</th><th>名称</th><th>信号</th><th>优先级</th><th>综合评分</th><th>当前持仓</th><th>理由</th>
          </tr></thead>
          <tbody>
            <tr v-for="s in result.trade_signals" :key="s.code" class="sp-signal-row">
              <td><span class="sp-code" @click.stop="goAnalysis(s.code)">{{ s.code }}</span></td>
              <td>{{ s.name }}</td>
              <td><span class="sp-sig-badge" :class="'sp-sig-' + s.action">{{ s.action }}</span></td>
              <td><span class="sp-priority" :class="'sp-pri-' + s.priority">{{ s.priority }}</span></td>
              <td>{{ s.composite != null ? Math.round(s.composite) : '-' }}</td>
              <td>{{ s.current_shares > 0 ? s.current_shares + ' 股' : '-' }}</td>
              <td class="sp-signal-reason">{{ s.reason }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- 结果表格 -->
    <el-table v-if="result?.picks?.length" :data="result.picks" stripe class="sp-table"
              :row-class-name="tableRowClass" @row-click="showDetail">
      <el-table-column type="index" label="#" width="42" align="center" />
      <el-table-column prop="code" label="代码" width="100">
        <template #default="{ row }">
          <span class="sp-code" @click.stop="goAnalysis(row.code)">{{ row.code }}</span>
        </template>
      </el-table-column>
      <el-table-column prop="name" label="名称" width="90" />
      <el-table-column prop="industry" label="行业" width="80" show-overflow-tooltip />
      <el-table-column label="综合" width="140" sortable :sort-by="(r: StrategyPickItem) => r.composite">
        <template #default="{ row }">
          <el-progress :percentage="Math.round(row.composite)" :color="scoreColor(row.composite)" :stroke-width="8" />
        </template>
      </el-table-column>
      <el-table-column label="基本" width="55" align="center" sortable :sort-by="(r: StrategyPickItem) => r.scores?.fundamental ?? 0">
        <template #default="{ row }">
          <span v-if="row.scores?.fundamental != null" class="sp-score-cell" :style="{ color: dimColor(row.scores.fundamental) }">{{ Math.round(row.scores.fundamental) }}</span>
          <span v-else class="sp-na">-</span>
        </template>
      </el-table-column>
      <el-table-column label="技术" width="55" align="center" sortable :sort-by="(r: StrategyPickItem) => r.scores?.technical ?? 0">
        <template #default="{ row }">
          <span v-if="row.scores?.technical != null" class="sp-score-cell" :style="{ color: dimColor(row.scores.technical) }">{{ Math.round(row.scores.technical) }}</span>
          <span v-else class="sp-na">-</span>
        </template>
      </el-table-column>
      <el-table-column label="资金" width="55" align="center" sortable :sort-by="(r: StrategyPickItem) => r.scores?.fund_flow ?? 0">
        <template #default="{ row }">
          <span v-if="row.scores?.fund_flow != null" class="sp-score-cell" :style="{ color: dimColor(row.scores.fund_flow) }">{{ Math.round(row.scores.fund_flow) }}</span>
          <span v-else class="sp-na">-</span>
        </template>
      </el-table-column>
      <el-table-column label="估值" width="55" align="center" sortable :sort-by="(r: StrategyPickItem) => r.scores?.valuation ?? 0">
        <template #default="{ row }">
          <span v-if="row.scores?.valuation != null" class="sp-score-cell" :style="{ color: dimColor(row.scores.valuation) }">{{ Math.round(row.scores.valuation) }}</span>
          <span v-else class="sp-na">-</span>
        </template>
      </el-table-column>
      <el-table-column label="来源策略" min-width="160">
        <template #default="{ row }">
          <span v-for="(s, i) in (row.from_strategies || [row.from_strategy])" :key="i" class="sp-strategy-tag">{{ s }}</span>
        </template>
      </el-table-column>
      <el-table-column label="来源" width="56" align="center">
        <template #default="{ row }">
          <span v-if="row.source === 'llm'" class="sp-source-tag sp-tag-ai">AI</span>
          <span v-else class="sp-source-tag sp-tag-factor">因子</span>
        </template>
      </el-table-column>
      <el-table-column label="操作建议" width="80" align="center">
        <template #default="{ row }">
          <span class="sp-action-tag" :class="actionClass(row)">{{ getAction(row) }}</span>
        </template>
      </el-table-column>
      <el-table-column label="辩论" width="65" align="center" sortable :sort-by="(r: StrategyPickItem) => r.debate_consensus?.avg_score ?? 0">
        <template #default="{ row }">
          <span v-if="row.debate_consensus" class="sp-debate-cell" :class="debateClass(row.debate_consensus)">
            {{ debateLabel(row.debate_consensus) }}
          </span>
          <span v-else class="sp-na">-</span>
        </template>
      </el-table-column>
    </el-table>

    <!-- AI 分析详情弹窗 -->
    <el-dialog v-model="detailDialogVisible" :title="detailPick?.code + ' ' + detailPick?.name" width="700px" top="5vh" class="sp-detail-dialog" destroy-on-close>
      <template v-if="detailPick">
        <div class="sp-detail-source">策略: {{ detailPick.from_strategy }} | 策略评分: {{ detailPick.strategy_score }}</div>

        <div v-if="detailPick.score_details && Object.keys(detailPick.score_details).length" class="sp-detail-body">
          <div v-for="dim in orderedDimensions" :key="dim.key" class="sp-dim-block">
            <div class="sp-dim-title">
              <span class="sp-dim-label">{{ dim.label }}</span>
              <el-progress class="sp-dim-bar" :percentage="Math.round(dim.score)" :color="scoreColor(dim.score)" :stroke-width="8" />
              <span class="sp-dim-score">{{ dim.score }}分</span>
              <span class="sp-dim-weight">权重{{ Math.round(dim.weight * 100) }}%</span>
              <span class="sp-dim-contrib">贡献{{ dim.contribution }}分</span>
            </div>
          </div>
        </div>

        <div v-if="detailPick.llm" class="sp-detail-advice">
          <div v-if="detailPick.llm.recommendation" class="sp-advice-section">
            <div class="sp-advice-label">AI分析建议：</div>
            <div class="sp-advice-text md-content" v-html="renderMd(detailPick.llm.recommendation)"></div>
          </div>
          <div v-if="detailPick.llm.risk_factors?.length" class="sp-risk-section">
            <div class="sp-advice-label">风险提示：</div>
            <div v-for="(risk, i) in detailPick.llm.risk_factors" :key="i" class="sp-risk-item">{{ risk }}</div>
          </div>
        </div>

        <!-- 辩论信号 -->
        <div v-if="detailPick.debate_signals?.length" class="sp-debate-section">
          <div class="sp-debate-section-title">投资哲学辩论结果</div>
          <div v-if="detailPick.debate_consensus" class="sp-consensus-bar">
            <span>共识度 {{ (detailPick.debate_consensus.consensus_level * 100).toFixed(0) }}%</span>
            <span>看多 {{ detailPick.debate_consensus.positive_count }}</span>
            <span>看空 {{ detailPick.debate_consensus.negative_count }}</span>
            <span>中立 {{ detailPick.debate_consensus.neutral_count }}</span>
            <span>平均分 {{ detailPick.debate_consensus.avg_score.toFixed(1) }}</span>
          </div>
          <div v-for="s in detailPick.debate_signals" :key="s.agent_id" class="sp-signal-row">
            <div class="sp-signal-header">
              <span class="sp-signal-name">{{ s.philosophy }}</span>
              <span class="sp-signal-action" :class="'sp-sig-' + s.action">{{ s.action }}</span>
              <span class="sp-signal-score">评分 {{ s.score.toFixed(0) }}</span>
              <span class="sp-signal-conf">信心 {{ (s.confidence * 100).toFixed(0) }}%</span>
            </div>
            <div class="sp-signal-body">
              <div class="sp-signal-reasoning">{{ s.reasoning }}</div>
              <div v-if="s.key_factors?.length" class="sp-signal-factors">
                <span v-for="(f, fi) in s.key_factors" :key="fi" class="sp-signal-factor">{{ f }}</span>
              </div>
              <div v-if="s.risk_warnings?.length" class="sp-signal-risks">
                <span v-for="(w, wi) in s.risk_warnings" :key="wi" class="sp-signal-warning">{{ w }}</span>
              </div>
            </div>
          </div>
        </div>
      </template>
    </el-dialog>

    <!-- 辩论总览 -->
    <div v-if="result?.debate_results?.length" class="sp-debate-overview">
      <div class="sp-debate-overview-toggle" @click="debateOverviewExpanded = !debateOverviewExpanded">
        <span>辩论结果总览（{{ result.debate_results.length }} 只股票，含投资哲学 Agent 投票）</span>
        <svg class="sp-summary-svg" :class="{ 'is-expanded': debateOverviewExpanded }" viewBox="0 0 12 12" width="12" height="12">
          <path d="M2 4l4 4 4-4" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
      </div>
      <div v-if="debateOverviewExpanded" class="sp-debate-overview-body">
        <div v-for="d in result.debate_results" :key="d.code" class="sp-debate-stock-row">
          <div class="sp-debate-stock-title">
            <span class="sp-code" @click.stop="goAnalysis(d.code)">{{ d.code }}</span>
            <span class="sp-debate-stock-name">{{ d.name }}</span>
            <span v-if="d.consensus" class="sp-debate-stock-consensus" :class="debateClass(d.consensus)">{{ debateLabel(d.consensus) }}</span>
            <span v-if="d.consensus" class="sp-debate-stock-meta">共识度 {{ (d.consensus.consensus_level * 100).toFixed(0) }}% | {{ d.consensus.agent_count }}位Agent | +{{ d.consensus.positive_count }}/{{ d.consensus.negative_count }}/{{ d.consensus.neutral_count }}</span>
          </div>
          <div v-if="d.signals?.length" class="sp-debate-vote-list">
            <span v-for="s in d.signals" :key="s.agent_id" class="sp-vote-tag" :class="'sp-vote-' + s.action" :title="s.reasoning">{{ s.philosophy }}: {{ s.action }}</span>
          </div>
        </div>
      </div>
    </div>

    <!-- 辩论综合结论 -->
    <div v-if="result?.debate_summary" class="sp-ai-summary">
      <div class="sp-summary-toggle" @click="summaryExpanded = !summaryExpanded">
        <span>辩论综合结论</span>
        <svg class="sp-summary-svg" :class="{ 'is-expanded': summaryExpanded }" viewBox="0 0 12 12" width="12" height="12">
          <path d="M2 4l4 4 4-4" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
      </div>
      <div v-if="summaryExpanded" class="sp-summary-body md-content" v-html="renderMd(result.debate_summary)"></div>
    </div>

    <el-empty v-if="!result?.picks?.length && !loading && !running" description="选择策略后点击「开始选股」" />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { marked } from 'marked'
import dayjs from 'dayjs'
import { strategyPickApi, type StrategyPickItem, type StrategyPickResult, type StrategyPickProgress, type StrategyPickAgent, type DebateConsensus } from '@/api/strategyPick'
import type { StrategyRule } from '@/types'

marked.setOptions({ breaks: true, gfm: true })

function renderMd(text: string): string {
  if (!text) return ''
  return marked.parse(text) as string
}

const router = useRouter()

const strategies = ref<StrategyRule[]>([])
const strategiesLoading = ref(false)
const selectedIds = ref<string[]>([])
const agents = ref<StrategyPickAgent[]>([])
const agentsLoading = ref(false)
const llmAgents = computed(() => agents.value.filter(a => a.type === 'llm'))
const philosophyAgents = computed(() => agents.value.filter(a => a.type === 'philosophy'))
const selectedAgentIds = ref<string[]>([])
const selectedPhilosophyIds = ref<string[]>([])
const result = ref<StrategyPickResult | null>(null)
const loading = ref(false)
const running = ref(false)
const topN = ref(20)
const showDoneTip = ref(false)
const summaryExpanded = ref(true)
const debateOverviewExpanded = ref(true)
const collapseActive = ref<string[]>([])
const detailDialogVisible = ref(false)
const detailPick = ref<StrategyPickItem | null>(null)

const progress = ref<StrategyPickProgress>({ is_running: false, progress: 0, status: '' })
let eventSource: EventSource | null = null
let progressTimer: ReturnType<typeof setInterval> | null = null
let sseTimeout: ReturnType<typeof setTimeout> | null = null

const DIM_LABELS: Record<string, string> = {
  fundamental: '基本面', technical: '技术面', fund_flow: '资金面', valuation: '估值面',
}
const DIM_ORDER = ['fundamental', 'technical', 'fund_flow', 'valuation']

const orderedDimensions = computed(() => {
  const pick = detailPick.value
  if (!pick?.score_details) return []
  return DIM_ORDER.filter(k => k in pick.score_details).map(k => {
    const d = pick.score_details[k]
    return {
      key: k,
      label: DIM_LABELS[k] || k,
      score: d.score ?? 0,
      weight: d.normalized_weight ?? d.weight ?? 0,
      contribution: d.contribution ?? 0,
    }
  })
})

const signalGroups = computed(() => {
  const signals = result.value?.trade_signals || []
  const map: Record<string, number> = {}
  for (const s of signals) {
    map[s.action] = (map[s.action] || 0) + 1
  }
  const order = ['买入', '加仓', '关注', '持有', '观望', '减仓', '卖出']
  return order.filter(a => map[a]).map(a => ({ action: a, count: map[a] }))
})

function toggleAll() {
  if (selectedIds.value.length === strategies.value.length) {
    selectedIds.value = []
  } else {
    selectedIds.value = strategies.value.map(s => s._id)
  }
}

function toggleAllByType(type: 'llm' | 'philosophy') {
  const list = type === 'llm' ? llmAgents.value : philosophyAgents.value
  const ids = list.map(a => a.id)
  const target = type === 'llm' ? selectedAgentIds : selectedPhilosophyIds
  if (target.value.length === ids.length && ids.every(id => target.value.includes(id))) {
    target.value = []
  } else {
    target.value = ids
  }
}

function debateLabel(c: DebateConsensus | null): string {
  if (!c) return '无'
  if (c.tendency > 0.15) return '偏多'
  if (c.tendency < -0.15) return '偏空'
  return '分歧'
}

function debateClass(c: DebateConsensus | null): string {
  if (!c) return ''
  if (c.tendency > 0.15) return 'sp-debate-bull'
  if (c.tendency < -0.15) return 'sp-debate-bear'
  return 'sp-debate-neutral'
}

function scoreColor(v: number): string {
  if (v >= 70) return '#3a8a52'
  if (v >= 50) return '#d0a020'
  return '#a04040'
}

function dimColor(v: number): string {
  if (v >= 80) return '#52c41a'
  if (v >= 60) return '#faad14'
  return '#ff4d4f'
}

function getAction(pick: StrategyPickItem): string {
  const c = pick.composite ?? 0
  if (c >= 72) return '强烈推荐'
  if (c >= 60) return '建议关注'
  if (c >= 50) return '可以关注'
  return '观望'
}

const ACTION_CLASS: Record<string, string> = {
  '强烈推荐': 'sp-action-green',
  '建议关注': 'sp-action-lightgreen',
  '可以关注': 'sp-action-orange',
  '观望': 'sp-action-gray',
}
function actionClass(pick: StrategyPickItem): string {
  return ACTION_CLASS[getAction(pick)] || 'sp-action-gray'
}

function tableRowClass() {
  return ['sp-row-clickable']
}

function fmtTime(t: string): string {
  return t ? dayjs(t).format('MM-DD HH:mm') : '--'
}

function goAnalysis(code: string) {
  router.push({ path: '/stock-analysis', query: { code } })
}

function showDetail(row: StrategyPickItem) {
  detailPick.value = row
  detailDialogVisible.value = true
}

async function loadStrategies() {
  strategiesLoading.value = true
  try {
    const res = await strategyPickApi.getStrategies()
    strategies.value = res.data?.data || []
    selectedIds.value = strategies.value.map(s => s._id)
  } catch {
    ElMessage.error('加载策略列表失败')
  } finally {
    strategiesLoading.value = false
  }
}

async function loadAgents() {
  agentsLoading.value = true
  try {
    const res = await strategyPickApi.getAgents()
    agents.value = res.data?.data || []
    // 默认全选
    selectedAgentIds.value = agents.value.filter(a => a.type === 'llm').map(a => a.id)
    selectedPhilosophyIds.value = agents.value.filter(a => a.type === 'philosophy').map(a => a.id)
  } catch {
    ElMessage.error('加载 Agent 列表失败')
  } finally {
    agentsLoading.value = false
  }
}

async function loadResult() {
  loading.value = true
  try {
    const res = await strategyPickApi.getResult()
    result.value = res.data?.data || null
  } catch {
    ElMessage.error('加载结果失败')
  } finally {
    loading.value = false
  }
}

function startProgressPolling() {
  stopProgressPolling()
  progressTimer = setInterval(async () => {
    try {
      const res = await strategyPickApi.getProgress()
      const data = res.data?.data
      if (data) {
        progress.value = data
        if (data.is_running) running.value = true
        if (!data.is_running) {
          stopProgressPolling()
          if (data.progress >= 100) {
            running.value = false
            showDoneTip.value = true
            await loadResult()
            setTimeout(() => { showDoneTip.value = false }, 4000)
          } else {
            running.value = false
          }
        }
      }
    } catch { /* ignore */ }
  }, 2000)
}

function stopProgressPolling() {
  if (progressTimer) { clearInterval(progressTimer); progressTimer = null }
}

function startProgressSSE() {
  stopProgressSSE()
  stopProgressPolling()
  eventSource = new EventSource('/api/v1/strategy-pick/progress/stream')
  let received = false
  eventSource.onmessage = (event) => {
    received = true
    if (sseTimeout) { clearTimeout(sseTimeout); sseTimeout = null }
    try {
      const res = JSON.parse(event.data)
      const data = res?.data
      if (!data) return
      progress.value = data
      if (data.is_running) running.value = true
      if (!data.is_running) {
        stopProgressSSE()
        if (data.progress >= 100) {
          running.value = false
          showDoneTip.value = true
          loadResult()
          setTimeout(() => { showDoneTip.value = false }, 4000)
        } else {
          running.value = false
        }
      }
    } catch { /* ignore */ }
  }
  eventSource.onerror = () => {
    if (received) {
      // SSE was working but error occurred — stop
      stopProgressSSE()
      running.value = false
      progress.value = { is_running: false, progress: 0, status: '连接断开' }
    }
    // if never received, onerror is normal during connection; let the timeout handle fallback
  }
  // Fallback to polling if no SSE data within 3s
  sseTimeout = setTimeout(() => {
    if (!received) {
      stopProgressSSE()
      startProgressPolling()
    }
  }, 3000)
}

function stopProgressSSE() {
  if (eventSource) {
    eventSource.close()
    eventSource = null
  }
  if (sseTimeout) { clearTimeout(sseTimeout); sseTimeout = null }
}

async function runPick() {
  if (selectedIds.value.length === 0) {
    ElMessage.warning('请至少选择一个策略')
    return
  }
  running.value = true
  showDoneTip.value = false
  progress.value = { is_running: true, progress: 0, status: '启动中...' }
  try {
    const res = await strategyPickApi.run(selectedIds.value, topN.value, 15, selectedAgentIds.value, selectedPhilosophyIds.value)
    if (res.data?.success) {
      ElMessage.info(res.data.message || '策略选股已启动')
      startProgressSSE()
    } else {
      ElMessage.error(res.data?.error || '启动失败')
      running.value = false
      progress.value = { is_running: false, progress: 0, status: '' }
    }
  } catch {
    ElMessage.error('请求失败')
    running.value = false
    progress.value = { is_running: false, progress: 0, status: '' }
  }
}

onMounted(async () => {
  await Promise.all([loadStrategies(), loadAgents(), loadResult()])
  // Restore last pick config so result matches selections
  if (result.value?.pick_config) {
    const cfg = result.value.pick_config
    const validStrategyIds = cfg.strategy_ids?.filter(id => strategies.value.some(s => s._id === id)) || []
    if (validStrategyIds.length) selectedIds.value = validStrategyIds
    if (cfg.agent_ids?.length) selectedAgentIds.value = cfg.agent_ids
    if (cfg.philosophy_ids?.length) selectedPhilosophyIds.value = cfg.philosophy_ids
    if (cfg.top_n) topN.value = cfg.top_n
  }
  try {
    const res = await strategyPickApi.getProgress()
    const data = res.data?.data
    if (data?.is_running) {
      progress.value = data
      running.value = true
      startProgressSSE()
    }
  } catch { /* ignore */ }
})

onBeforeUnmount(() => { stopProgressSSE(); stopProgressPolling() })
</script>

<style scoped>
.sp-page { display: flex; flex-direction: column; gap: 10px; }
.sp-toolbar { display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px; }
.sp-title-group { display: flex; align-items: baseline; gap: 10px; }
.sp-title { font-size: 15px; font-weight: 700; color: #d8daf0; }
.sp-subtitle { font-size: 12px; color: #606080; }
.sp-controls { display: flex; gap: 8px; align-items: center; }
.sp-meta { display: flex; gap: 18px; font-size: 12px; color: #606080; }

/* 折叠选择区 */
.sp-collapse-group {
  border: none;
  background: transparent;
}
.sp-collapse-group :deep(.el-collapse-item) {
  background: #1a1a2e;
  border: 1px solid #2a2a4a;
  border-radius: 8px;
  margin-bottom: 10px;
  overflow: hidden;
}
.sp-collapse-group :deep(.el-collapse-item__header) {
  height: auto;
  min-height: 36px;
  padding: 10px 16px;
  background: transparent;
  border-bottom: none;
  color: #b0b0d0;
  font-size: 13px;
  font-weight: 600;
  line-height: 1.4;
}
.sp-collapse-group :deep(.el-collapse-item__wrap) {
  background: transparent;
  border-bottom: none;
}
.sp-collapse-group :deep(.el-collapse-item__content) {
  padding: 0 16px 12px;
}
.sp-collapse-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  width: 100%;
}
/* 买卖信号 */
.sp-signals-box {
  background: #1a1a2e;
  border: 1px solid #2a2a4a;
  border-left: 3px solid #f0a040;
  border-radius: 6px;
  padding: 12px 14px;
}
.sp-signals-header { margin-bottom: 8px; }
.sp-signals-title { font-size: 13px; font-weight: 600; color: #d0b080; }
.sp-signals-summary { display: flex; gap: 8px; margin-bottom: 8px; flex-wrap: wrap; }
.sp-signal-summary-tag {
  font-size: 11px; padding: 2px 10px; border-radius: 4px; font-weight: 600;
}
.sp-ss-买入 { color: #4ade80; background: rgba(74,222,128,0.12); }
.sp-ss-加仓 { color: #60a0f0; background: rgba(96,160,240,0.12); }
.sp-ss-关注 { color: #a0d0a0; background: rgba(160,208,160,0.08); }
.sp-ss-持有 { color: #fbbf24; background: rgba(251,191,36,0.10); }
.sp-ss-观望 { color: #909098; background: rgba(144,144,152,0.10); }
.sp-ss-减仓 { color: #fb923c; background: rgba(251,146,60,0.12); }
.sp-ss-卖出 { color: #f87171; background: rgba(248,113,113,0.12); }
.sp-signals-table-wrap { overflow-x: auto; }
.sp-signals-table {
  width: 100%; border-collapse: collapse; font-size: 12px;
}
.sp-signals-table th {
  text-align: left; color: #707090; padding: 6px 8px; border-bottom: 1px solid #2a2a4a;
  font-weight: 500; white-space: nowrap;
}
.sp-signals-table td { padding: 6px 8px; border-bottom: 1px solid #1e1e3a; color: #b0b0d0; }
.sp-signal-row:hover td { background: rgba(255,255,255,0.03); }
.sp-sig-badge {
  display: inline-block; font-size: 11px; padding: 1px 8px; border-radius: 3px; font-weight: 600;
}
.sp-sig-买入 { color: #4ade80; background: rgba(74,222,128,0.15); }
.sp-sig-加仓 { color: #60a0f0; background: rgba(96,160,240,0.15); }
.sp-sig-关注 { color: #a0d0a0; background: rgba(160,208,160,0.10); }
.sp-sig-持有 { color: #fbbf24; background: rgba(251,191,36,0.12); }
.sp-sig-观望 { color: #909098; background: rgba(144,144,152,0.12); }
.sp-sig-减仓 { color: #fb923c; background: rgba(251,146,60,0.15); }
.sp-sig-卖出 { color: #f87171; background: rgba(248,113,113,0.15); }
.sp-priority { font-size: 11px; }
.sp-pri-高 { color: #f87171; }
.sp-pri-中 { color: #fbbf24; }
.sp-pri-低 { color: #909098; }
.sp-signal-reason { font-size: 11px; color: #808098; max-width: 260px; }

.sp-selector-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}
.sp-selector-title { font-size: 13px; font-weight: 600; color: #b0b0d0; }
.sp-strategy-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  min-height: 24px;
}
.sp-empty-hint { font-size: 12px; color: #606070; }
.sp-strategy-chip {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  border-radius: 6px;
  border: 1px solid #2a2a4a;
  background: #16162a;
  cursor: pointer;
  transition: all 0.2s;
  user-select: none;
}
.sp-strategy-chip:hover { border-color: #4a4a6a; }
.sp-strategy-chip.checked {
  border-color: #5a7af0;
  background: rgba(90, 122, 240, 0.12);
}
.sp-check { width: 14px; height: 14px; accent-color: #5a7af0; }
.sp-chip-name { font-size: 12px; font-weight: 600; color: #c0c0e0; }
.sp-chip-desc { font-size: 11px; color: #606080; max-width: 180px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

.sp-strategy-chip.agent-chip {
  border-color: #3a3a6a;
  background: #12122a;
}
.sp-strategy-chip.agent-chip:hover { border-color: #5a5a9a; }
.sp-strategy-chip.agent-chip.checked {
  border-color: #7a5af0;
  background: rgba(122, 90, 240, 0.12);
}
.sp-progress-box {
  background: #1a1a2e;
  border: 1px solid #2a2a4a;
  border-radius: 8px;
  padding: 12px 16px;
}
.sp-progress-header { font-size: 13px; color: #b0b0d0; margin-bottom: 8px; }
.sp-progress-status { font-size: 12px; color: #808098; margin-top: 6px; }
.sp-progress-done { font-size: 13px; color: #4ade80; text-align: center; padding: 4px 0; }

/* 统计 */
.sp-stats { display: flex; flex-wrap: wrap; gap: 8px; }
.sp-stat-tag {
  font-size: 12px;
  color: #b0b0d0;
  background: #1a1a2e;
  border: 1px solid #2a2a4a;
  border-radius: 4px;
  padding: 3px 10px;
}
.sp-stat-tag b { color: #5a7af0; }

/* 表格 */
.sp-table { background: transparent; }
.sp-table :deep(.el-table__row) { height: 42px; }
.sp-table :deep(.el-table__row:hover > td) { background: rgba(255,255,255,0.04) !important; }
.sp-row-clickable { cursor: pointer; }
.sp-code { color: #5a7af0; cursor: pointer; }
.sp-code:hover { text-decoration: underline; }
.sp-na { color: #505060; }
.sp-score-cell { font-weight: 600; font-size: 13px; }
.sp-strategy-tag {
  display: inline-block;
  font-size: 11px;
  color: #a0a0c0;
  background: rgba(90,122,240,0.08);
  padding: 1px 6px;
  border-radius: 3px;
  margin-right: 4px;
  margin-bottom: 2px;
  white-space: nowrap;
}
.sp-source-tag {
  display: inline-block;
  font-size: 11px;
  padding: 1px 6px;
  border-radius: 3px;
  font-weight: 600;
  line-height: 1.4;
}
.sp-tag-ai { color: #60a0f0; background: rgba(96,160,240,0.12); }
.sp-tag-factor { color: #a0a060; background: rgba(160,160,96,0.12); }
.sp-action-tag {
  display: inline-block;
  font-size: 11px;
  padding: 1px 7px;
  border-radius: 3px;
  font-weight: 600;
  line-height: 1.5;
  white-space: nowrap;
}
.sp-action-green { color: #3aa856; background: rgba(82,196,26,0.14); }
.sp-action-lightgreen { color: #7cc98a; background: rgba(82,196,26,0.07); }
.sp-action-orange { color: #e8912a; background: rgba(250,173,20,0.14); }
.sp-action-gray { color: #909098; background: rgba(144,144,152,0.12); }

/* 弹窗详情 */
.sp-detail-dialog :deep(.el-dialog) {
  background: #1a1a2e;
  border: 1px solid #2a2a4a;
  border-radius: 10px;
  color: #c0c0e0;
}
.sp-detail-dialog :deep(.el-dialog__title) {
  color: #c0c0e0;
  font-size: 15px;
  font-weight: 600;
}
.sp-detail-dialog :deep(.el-dialog__headerbtn .el-dialog__close) {
  color: #606080;
}
.sp-detail-dialog :deep(.el-dialog__body) {
  padding: 16px 20px;
}
.sp-detail-source { font-size: 12px; font-weight: 400; color: #707090; margin-bottom: 12px; }
.sp-detail-body { display: flex; flex-direction: column; gap: 10px; }
.sp-dim-block { background: #16162a; border-radius: 6px; padding: 10px 12px; }
.sp-dim-title {
  display: flex; align-items: center; gap: 10px;
}
.sp-dim-label { font-size: 13px; font-weight: 600; color: #b0b0d0; min-width: 48px; }
.sp-dim-bar { flex: 1; max-width: 180px; }
.sp-dim-score { font-size: 13px; font-weight: 600; color: #d8d8f0; }
.sp-dim-weight { font-size: 11px; color: #707090; }
.sp-dim-contrib { font-size: 11px; color: #808090; }
.sp-detail-advice { margin-top: 10px; border-top: 1px solid #2a2a4a; padding-top: 10px; }
.sp-advice-label { font-size: 12px; color: #808090; margin-bottom: 4px; }
.sp-advice-text { font-size: 13px; color: #b0b0d0; line-height: 1.6; }
.sp-risk-section { margin-top: 8px; }
.sp-risk-item {
  font-size: 12px;
  color: #faad14;
  background: rgba(250,173,20,0.08);
  padding: 4px 8px;
  border-radius: 4px;
  margin-top: 4px;
}

/* AI 综合建议 */
.sp-ai-summary {
  background: #16162a;
  border: 1px solid #2a2a4a;
  border-left: 3px solid #5a7af0;
  border-radius: 6px;
  overflow: hidden;
}
.sp-summary-toggle {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 14px;
  cursor: pointer;
  font-size: 13px;
  font-weight: 600;
  color: #b0b0d0;
  user-select: none;
}
.sp-summary-toggle:hover { background: rgba(255,255,255,0.03); }
.sp-summary-svg {
  color: #606080;
  transition: transform 0.2s;
  vertical-align: middle;
}
.sp-summary-svg.is-expanded { transform: rotate(180deg); }
.sp-summary-body {
  padding: 0 14px 12px;
  font-size: 13px;
  color: #c0c0d8;
  line-height: 1.7;
}

/* Markdown */
.md-content :deep(h1), .md-content :deep(h2), .md-content :deep(h3) {
  font-size: 13px; font-weight: 600; color: #d8d8f0; margin: 10px 0 4px 0;
}
.md-content :deep(h1) { font-size: 14px; }
.md-content :deep(strong) { color: #e8e8ff; font-weight: 600; }
.md-content :deep(p) { margin: 4px 0; color: #c0c0d8; }
.md-content :deep(ul), .md-content :deep(ol) { padding-left: 16px; margin: 3px 0; }
.md-content :deep(li) { margin: 2px 0; color: #c0c0d8; }
.md-content :deep(code) { background: #22223a; padding: 1px 5px; border-radius: 3px; font-size: 12px; color: #d0a0f0; }

/* 投资哲学 Agent 样式 */
.sp-strategy-chip.philosophy-chip {
  border-color: #3a3a5a;
  background: #12122a;
}
.sp-strategy-chip.philosophy-chip:hover { border-color: #5a5a7a; }
.sp-strategy-chip.philosophy-chip.checked {
  border-color: #aa5af0;
  background: rgba(170, 90, 240, 0.12);
}

/* 辩论列 */
.sp-debate-cell {
  display: inline-block;
  font-size: 11px;
  padding: 1px 7px;
  border-radius: 3px;
  font-weight: 600;
  line-height: 1.5;
  white-space: nowrap;
}
.sp-debate-bull { color: #4ade80; background: rgba(74,222,128,0.12); }
.sp-debate-bear { color: #f87171; background: rgba(248,113,113,0.12); }
.sp-debate-neutral { color: #fbbf24; background: rgba(251,191,36,0.12); }

/* 辩论总览 */
.sp-debate-overview {
  background: #16162a;
  border: 1px solid #2a2a4a;
  border-left: 3px solid #aa5af0;
  border-radius: 6px;
  overflow: hidden;
}
.sp-debate-overview-toggle {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 14px;
  cursor: pointer;
  font-size: 13px;
  font-weight: 600;
  color: #b0b0d0;
  user-select: none;
}
.sp-debate-overview-toggle:hover { background: rgba(255,255,255,0.03); }
.sp-debate-overview-body { padding: 0 14px 12px; display: flex; flex-direction: column; gap: 8px; }
.sp-debate-stock-row {
  background: #1a1a2e;
  border: 1px solid #2a2a4a;
  border-radius: 6px;
  padding: 10px;
}
.sp-debate-stock-title {
  display: flex; align-items: center; gap: 10px; margin-bottom: 6px;
}
.sp-debate-stock-name { font-size: 13px; font-weight: 600; color: #c0c0e0; }
.sp-debate-stock-consensus {
  font-size: 11px; padding: 1px 7px; border-radius: 3px; font-weight: 600;
}
.sp-debate-stock-meta { font-size: 11px; color: #707090; }
.sp-debate-vote-list { display: flex; flex-wrap: wrap; gap: 4px; }
.sp-vote-tag {
  font-size: 10px;
  padding: 2px 6px;
  border-radius: 3px;
  white-space: nowrap;
}
.sp-vote-strong_buy { color: #22c55e; background: rgba(34,197,94,0.1); }
.sp-vote-buy { color: #4ade80; background: rgba(74,222,128,0.08); }
.sp-vote-hold { color: #fbbf24; background: rgba(251,191,36,0.08); }
.sp-vote-watch { color: #fb923c; background: rgba(251,146,60,0.08); }
.sp-vote-sell { color: #f87171; background: rgba(248,113,113,0.1); }
.sp-vote-strong_sell { color: #ef4444; background: rgba(239,68,68,0.12); }

/* 辩论信号详情 */
.sp-debate-section { margin-top: 10px; border-top: 1px solid #2a2a4a; padding-top: 10px; }
.sp-debate-section-title { font-size: 12px; font-weight: 600; color: #aa5af0; margin-bottom: 8px; }
.sp-consensus-bar {
  display: flex; gap: 14px; font-size: 11px; color: #808098;
  background: #12122a; border-radius: 4px; padding: 6px 10px; margin-bottom: 8px;
}
.sp-signal-row {
  background: #12122a;
  border: 1px solid #2a2a4a;
  border-radius: 6px;
  padding: 8px 10px;
  margin-bottom: 6px;
}
.sp-signal-header { display: flex; align-items: center; gap: 10px; margin-bottom: 4px; }
.sp-signal-name { font-size: 12px; font-weight: 600; color: #c0c0e0; }
.sp-signal-action {
  font-size: 10px; padding: 1px 6px; border-radius: 3px; font-weight: 600;
}
.sp-sig-strong_buy { color: #22c55e; background: rgba(34,197,94,0.12); }
.sp-sig-buy { color: #4ade80; background: rgba(74,222,128,0.1); }
.sp-sig-hold { color: #fbbf24; background: rgba(251,191,36,0.1); }
.sp-sig-watch { color: #fb923c; background: rgba(251,146,60,0.1); }
.sp-sig-sell { color: #f87171; background: rgba(248,113,113,0.1); }
.sp-sig-strong_sell { color: #ef4444; background: rgba(239,68,68,0.12); }
.sp-signal-score { font-size: 11px; color: #707090; }
.sp-signal-conf { font-size: 11px; color: #707090; }
.sp-signal-body { }
.sp-signal-reasoning { font-size: 11px; color: #a0a0b8; line-height: 1.5; margin-bottom: 4px; }
.sp-signal-factors { display: flex; flex-wrap: wrap; gap: 4px; margin-bottom: 4px; }
.sp-signal-factor {
  font-size: 10px; color: #60a0f0; background: rgba(96,160,240,0.08);
  padding: 1px 6px; border-radius: 3px;
}
.sp-signal-risks { display: flex; flex-wrap: wrap; gap: 4px; }
.sp-signal-warning {
  font-size: 10px; color: #faad14; background: rgba(250,173,20,0.08);
  padding: 1px 6px; border-radius: 3px;
}
</style>
