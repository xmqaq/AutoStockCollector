<template>
  <div class="multi-agent-panel">
    <!-- Stock & Task Config -->
    <el-card shadow="never" class="section-card">
      <template #header>
        <div class="header-toolbar">
          <span>多Agent智能协作分析</span>
          <el-tag v-if="analysisId" type="success" size="small">#{{ analysisId.slice(0, 8) }}</el-tag>
        </div>
      </template>
      <div class="task-config">
        <el-select
          v-model="stockCode" filterable remote
          :remote-method="remoteSearch"
          placeholder="输入股票代码 或 从自选股选择"
          style="width: 240px" clearable
        >
          <el-option v-for="s in remoteOptions" :key="s.value" :label="s.label" :value="s.value" />
        </el-select>
        <el-select v-model="analysisType" style="width: 140px">
          <el-option label="综合分析" value="comprehensive" />
          <el-option label="技术分析" value="technical" />
          <el-option label="基本面" value="fundamental" />
        </el-select>
        <el-button type="primary" size="large" :icon="MagicStick" @click="startCombinedAnalysis"
          :loading="isRunning" :disabled="!stockCode || (!selectedIds.length && !enableDebate)">
          开始综合分析
        </el-button>
        <el-button v-if="isRunning" type="danger" size="small" @click="stopAnalysis">停止</el-button>
      </div>
    </el-card>

    <!-- Agent Selection -->
    <el-card shadow="never" class="section-card">
      <template #header>
        <div class="section-header">
          <div class="header-left">
            <span>选择参与分析的 Agent</span>
            <span class="header-hint">传统 5 个 + 投资哲学 {{ agents.length }} 个</span>
          </div>
          <div class="header-actions">
            <el-button size="small" text @click="philosophyStore.selectAll()" :disabled="!agents.length">全选哲学</el-button>
            <el-button size="small" text @click="philosophyStore.deselectAll()" :disabled="!selectedIds.length">取消</el-button>
            <span class="selected-count">已选 {{ selectedIds.length + traditionalCount }} / {{ agents.length + traditionalCount }}</span>
          </div>
        </div>
      </template>
      <div class="agent-selector">
        <div class="agent-group">
          <div class="group-header">
            <span class="group-label">传统分析 Agent</span>
            <span class="group-badge">始终参与</span>
          </div>
          <div class="group-agents">
            <div v-for="a in traditionalAgents" :key="a.id" class="agent-chip selected">
              <el-icon><User /></el-icon>
              <span>{{ a.name }}</span>
            </div>
          </div>
        </div>
        <div v-for="(group, school) in groupedAgents" :key="school" class="agent-group">
          <div class="group-header">
            <span class="group-label">{{ schoolLabels[school] || school }}</span>
            <el-button size="small" text @click.stop="toggleGroup(school)">
              {{ isGroupSelected(school) ? '取消全选' : '全选' }}
            </el-button>
          </div>
          <div class="group-agents">
            <div v-for="agent in group" :key="agent.id"
              :class="['agent-chip', { selected: selectedIds.includes(agent.id) }]"
              @click="philosophyStore.toggleAgent(agent.id)">
              <el-icon v-if="selectedIds.includes(agent.id)"><Check /></el-icon>
              <span>{{ agent.name }}</span>
            </div>
          </div>
        </div>
        <el-divider style="margin: 12px 0" />
        <div class="debate-config">
          <div class="config-row">
            <el-checkbox v-model="enableDebate" size="large">
              <span class="config-label">多空多轮辩论</span>
            </el-checkbox>
            <span class="config-hint">6 个研究员 + 多轮 Bull vs Bear 辩论</span>
            <div class="config-rounds" v-if="enableDebate">
              <span class="rounds-label">辩论轮数</span>
              <el-input-number v-model="debateRounds" :min="1" :max="5" size="small" style="width: 100px" />
            </div>
          </div>
        </div>
      </div>
    </el-card>

    <!-- Results (shown when running or has results) -->
    <transition v-if="isRunning || hasResults" name="fade">
      <div class="analysis-results">
        <!-- Pipeline -->
        <AnalysisPipeline
          :phase="debatePhase"
          :data-ready="researchEvidence.size > 0"
          :researchers-ready="debateResearchAgents.length > 0 || philosophyStore.agentSignals.length > 0"
          :debate-rounds="debateRounds"
          :debate-rounds-done="debateRoundsHistory.length"
          :verdict-ready="!!debateVerdict"
          :has-signals="combinedSignals.length > 0"
        />

        <!-- Stage ①: Data Collection -->
        <DataCollectionPanel :sections="dataSourceSections" />

        <!-- Stage ②: Researcher Analysis -->
        <ResearcherAnalysis
          :debate-researchers="debateResearchAgents"
          :philosophy-signals="philosophyStore.agentSignals"
          @show-detail="showDetail"
        />

        <!-- Stage ③: Debate Arena -->
        <DebateArena
          :rounds="debateRoundsHistory"
          :verdict="debateVerdict"
        />

        <!-- Stage ④: Judge Verdict -->
        <VerdictCard
          :verdict="debateVerdict"
          :researcher-count="debateResearchAgents.length"
          :round-count="debateRounds"
        />

        <!-- Stage ⑤: Decision Board (final aggregation) -->
        <DecisionBoard
          :signals="combinedSignals"
          :traditional-signals="traditionalCombinedSignals"
          :philosophy-signals="philosophyStore.agentSignals"
          :score="combinedScore"
          :verdict="combinedVerdict"
          @show-detail="showDetail"
        />
      </div>
    </transition>

    <!-- Detail Dialog -->
    <el-dialog v-model="showDetailDialog" :title="detailSignal?.agent_name || 'Agent 详情'" width="720px" top="5vh" destroy-on-close>
      <template v-if="detailSignal">
        <div class="detail-grid">
          <div class="detail-section">
            <div class="detail-label">来源</div>
            <div class="detail-value">{{ sourceLabel(detailSignal.source) }}</div>
          </div>
          <div class="detail-section">
            <div class="detail-label">流派</div>
            <div class="detail-value">{{ schoolLabels[detailSignal.archetype || ''] || detailSignal.archetype || '--' }}</div>
          </div>
          <div class="detail-section">
            <div class="detail-label">评分</div>
            <div class="detail-value">
              <span :class="scoreColor(detailSignal.score)">{{ detailSignal.score.toFixed(1) }}</span>
              <span class="detail-unit">/ 100</span>
            </div>
          </div>
          <div class="detail-section">
            <div class="detail-label">操作建议</div>
            <el-tag :type="actionTagType(detailSignal.action)" size="large">{{ actionLabel(detailSignal.action) }}</el-tag>
          </div>
          <div class="detail-section">
            <div class="detail-label">置信度</div>
            <div class="detail-value">{{ ((detailSignal as any).confidence ? (detailSignal as any).confidence * 100 : 0).toFixed(0) }}%</div>
          </div>
          <div class="detail-section">
            <div class="detail-label">Agent ID</div>
            <div class="detail-value mono">{{ detailSignal.agent_id }}</div>
          </div>
        </div>
        <el-divider />
        <div class="detail-section full">
          <div class="detail-label">分析推理</div>
          <div class="detail-content">{{ detailSignal.reasoning || '无详细推理' }}</div>
        </div>
        <div v-if="(detailSignal as any).key_factors?.length" class="detail-section full">
          <div class="detail-label">关键因子</div>
          <div class="detail-tags">
            <el-tag v-for="(f, i) in (detailSignal as any).key_factors" :key="i" type="success" size="small">{{ f }}</el-tag>
          </div>
        </div>
        <div v-if="(detailSignal as any).risk_warnings?.length" class="detail-section full">
          <div class="detail-label">风险警告</div>
          <div class="detail-tags">
            <el-tag v-for="(w, i) in (detailSignal as any).risk_warnings" :key="i" type="danger" size="small">{{ w }}</el-tag>
          </div>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { Check, MagicStick, User } from '@element-plus/icons-vue'
import { useAgentStore } from '@/stores/agentStore'
import { usePhilosophyStore } from '@/stores/philosophyStore'
import { watchlistApi } from '@/api/watchlist'
import { researchBattleApi } from '@/api/ai'

import AnalysisPipeline from './AnalysisPipeline.vue'
import DataCollectionPanel from './DataCollectionPanel.vue'
import ResearcherAnalysis from './ResearcherAnalysis.vue'
import DebateArena from './DebateArena.vue'
import VerdictCard from './VerdictCard.vue'
import DecisionBoard from './DecisionBoard.vue'

const agentStore = useAgentStore()
const philosophyStore = usePhilosophyStore()

// ── Basic state ──
const stockCode = ref('')
const analysisType = ref('comprehensive')
const isRunning = ref(false)
const watchlist = ref<{ code: string; name: string }[]>([])
const remoteOptions = ref<{ value: string; label: string }[]>([])
const analysisId = ref('')
const abortController = ref<AbortController | null>(null)
const showDetailDialog = ref(false)
const detailSignal = ref<any>(null)

// ── Agent selection ──
const enableDebate = ref(false)
const debateRounds = ref(3)

// ── Debate state ──
const debatePhase = ref<'idle' | 'research' | 'battle' | 'judge' | 'done'>('idle')
const debateResearchAgents = ref<any[]>([])
const debateRoundsHistory = ref<{ round: number; arguments: any[]; consensus_shift?: number }[]>([])
const debateVerdict = ref<any>(null)

// ── Interface ──
interface CombinedSignal {
  id: string
  agent_id: string
  agent_name: string
  source: 'traditional' | 'philosophy' | 'research'
  score: number
  action: string
  archetype?: string
  reasoning?: string
  key_factors?: string[]
  risk_warnings?: string[]
  confidence?: number
}

// ── Data source meta ──
const dataSourceMeta: Record<string, { label: string; icon: string }> = {
  dragon_tiger_analysis: { label: '龙虎榜席位分析', icon: '🚀' },
  news_sentiment: { label: '新闻舆情分析', icon: '📰' },
  fund_flow_analysis: { label: '资金流向分析', icon: '💰' },
  financial_analysis: { label: '财务数据分析', icon: '📊' },
  kline_trend: { label: 'K线趋势分析', icon: '📈' },
  market_capital_flow: { label: '全市场资金流向', icon: '🌐' },
}

const researchEvidence = computed(() => {
  const map = new Map<string, any>()
  console.log('[DEBUG] computing researchEvidence, agents:', debateResearchAgents.value.length)
  for (const agent of debateResearchAgents.value) {
    if (agent.evidence) {
      console.log('[DEBUG] agent', agent.agent_id, 'evidence:', Object.keys(agent.evidence))
      for (const [tool, data] of Object.entries(agent.evidence)) {
        if (!map.has(tool)) map.set(tool, data)
      }
    }
  }
  console.log('[DEBUG] researchEvidence map size:', map.size)
  return map
})

const dataSourceSections = computed(() => {
  const sections: any[] = []
  console.log('[DEBUG] computing dataSourceSections, evidence size:', researchEvidence.value.size)
  console.log('[DEBUG] evidence keys:', [...researchEvidence.value.keys()])
  for (const [tool, data] of researchEvidence.value) {
    const meta = dataSourceMeta[tool]
    if (!meta) continue
    const hasError = !!data?.error
    let summary = ''
    if (data?.error) {
      summary = `数据获取失败: ${data.error}`
    } else if (tool === 'dragon_tiger_analysis') {
      const count = data?.count || 0
      summary = count > 0 ? `共 ${count} 条记录` : '暂无龙虎榜数据'
    } else if (tool === 'news_sentiment') {
      const count = data?.count || 0
      summary = count > 0 ? `共 ${count} 条新闻` : '暂无新闻数据'
    } else if (tool === 'fund_flow_analysis') {
      const r = data?.record
      if (r) {
        const inflow = r.main_net_inflow
        const dir = inflow > 0 ? '净流入' : inflow < 0 ? '净流出' : '持平'
        summary = `主力 ${dir} ${Math.abs(inflow || 0).toFixed(2)}万`
      } else {
        summary = '暂无资金流向数据'
      }
    } else if (tool === 'financial_analysis') {
      const count = data?.count || 0
      const latest = data?.records?.[0]
      summary = count > 0 ? `共 ${count} 期数据` : '暂无财务数据'
      if (latest) summary += ` · ${latest.report_date || ''}`
    } else if (tool === 'kline_trend') {
      const count = data?.count || 0
      const first = data?.records?.[data.records.length - 1]
      const last = data?.records?.[0]
      summary = count > 0 ? `${count} 条K线` : '暂无K线数据'
      if (first?.date && last?.date) summary += ` · ${first.date} ~ ${last.date}`
    } else if (tool === 'market_capital_flow') {
      summary = data?.market_flow === 'positive' ? '全市场资金偏多' : '全市场资金偏空'
      if (data?.date) summary += ` · ${data.date}`
    }
    sections.push({
      tool, ...meta, summary, detail: data,
      badgeClass: hasError ? 'err' : 'ok',
      badgeText: hasError ? '失败' : '完成',
    })
  }
  return sections
})

// ── Computed helpers ──
const traditionalAgents = computed(() => agentStore.agents.filter(a => a.role !== 'commander'))
const traditionalCount = computed(() => traditionalAgents.value.length)
const agents = computed(() => philosophyStore.agents)
const selectedIds = computed(() => philosophyStore.selectedIds)

const hasResults = computed(() =>
  combinedSignals.value.length > 0 || agentStore.aggregatedResult !== null ||
  philosophyStore.agentSignals.length > 0 || debateVerdict.value !== null
)

const schoolLabels: Record<string, string> = {
  value: '价值派', growth: '成长派', technical: '技术派',
  macro: '宏观派', quant: '量化派', hot_money: '游资派',
  risk: '风控派', sentiment: '舆情派',
}

const groupedAgents = computed(() => {
  const groups: Record<string, any[]> = {}
  for (const a of agents.value) {
    const s = a.school || 'other'
    if (!groups[s]) groups[s] = []
    groups[s].push(a)
  }
  return groups
})

// ── Combined signals (merge 3 sources) ──
const traditionalCombinedSignals = computed(() => {
  const result: CombinedSignal[] = []
  for (const a of agentStore.agents) {
    if (a.role === 'commander' || !a.result) continue
    result.push({
      id: `trad-${a.id}`, agent_id: a.id, agent_name: a.name, source: 'traditional',
      score: a.result.score || 50, action: mapRecommendationToAction(a.result.recommendation),
      reasoning: a.result.conclusion, key_factors: a.result.signals,
    })
  }
  return result
})

const combinedSignals = computed<CombinedSignal[]>(() => {
  const result: CombinedSignal[] = [...traditionalCombinedSignals.value]

  for (const s of philosophyStore.agentSignals) {
    result.push({
      id: `phi-${s.agent_id}`, agent_id: s.agent_id, agent_name: s.agent_name,
      source: 'philosophy', score: s.score, action: s.action,
      archetype: s.archetype, reasoning: s.reasoning,
      key_factors: s.key_factors, risk_warnings: s.risk_warnings,
      confidence: s.confidence,
    })
  }

  for (const a of debateResearchAgents.value) {
    const action = a.signal === 'bullish' ? 'buy' : a.signal === 'bearish' ? 'sell' : 'hold'
    result.push({
      id: `research-${a.agent_id}`, agent_id: a.agent_id, agent_name: a.agent_name,
      source: 'research', score: (a.confidence || 0.5) * 100, action,
      archetype: a.archetype, reasoning: a.raw_analysis?.slice(0, 200),
      key_factors: a.key_findings, confidence: a.confidence,
    })
  }

  return result
})

const combinedScore = computed(() => {
  const signals = combinedSignals.value
  if (!signals.length) return '--'
  const avg = signals.reduce((s, sig) => s + sig.score, 0) / signals.length
  return avg.toFixed(1)
})

const combinedVerdict = computed(() => {
  const signals = combinedSignals.value
  if (!signals.length) return { label: '等待结果', type: 'info', scoreClass: '' }
  const avg = signals.reduce((s, sig) => s + sig.score, 0) / signals.length
  if (avg >= 65) return { label: '倾向看多', type: 'success', scoreClass: 'score-bull' }
  if (avg >= 50) return { label: '中性观望', type: 'warning', scoreClass: 'score-neutral' }
  return { label: '倾向看空', type: 'danger', scoreClass: 'score-bear' }
})

// ── Utility functions ──
function mapRecommendationToAction(rec?: string): string {
  if (!rec) return 'hold'
  if (rec.includes('强烈推荐') || rec.includes('买入')) return 'buy'
  if (rec.includes('回避') || rec.includes('卖出')) return 'sell'
  if (rec.includes('持有') || rec.includes('观望')) return 'hold'
  return 'hold'
}

function isGroupSelected(school: string): boolean {
  const group = groupedAgents.value[school]
  if (!group?.length) return false
  return group.every(a => selectedIds.value.includes(a.id))
}

function toggleGroup(school: string) {
  const group = groupedAgents.value[school]
  if (!group?.length) return
  const allSelected = isGroupSelected(school)
  for (const a of group) {
    if (allSelected) {
      const idx = selectedIds.value.indexOf(a.id)
      if (idx >= 0) selectedIds.value.splice(idx, 1)
    } else {
      if (!selectedIds.value.includes(a.id)) selectedIds.value.push(a.id)
    }
  }
}

function actionLabel(action: string): string {
  const map: Record<string, string> = {
    strong_buy: '强烈买入', buy: '买入', hold: '持有', sell: '卖出', strong_sell: '强烈卖出',
    强烈推荐: '强烈推荐', 买入建议: '买入建议', 持有建议: '持有建议', 建议观望: '建议观望',
  }
  return map[action] || action
}

function actionTagType(action: string): string {
  if (['strong_buy', 'buy', '强烈推荐', '买入建议'].includes(action)) return 'success'
  if (['strong_sell', 'sell', '回避', '建议观望'].includes(action)) return 'danger'
  return 'info'
}

function scoreColor(score: number): string {
  if (score >= 70) return 'score-high'
  if (score >= 50) return 'score-mid'
  return 'score-low'
}

function sourceLabel(source: string): string {
  const map: Record<string, string> = { traditional: '传统分析', philosophy: '投资哲学', research: '辩论研究员' }
  return map[source] || source
}

// ── Debate SSE handling ──
function resetDebate() {
  debatePhase.value = 'idle'
  debateResearchAgents.value = []
  debateRoundsHistory.value = []
  debateVerdict.value = null
}

async function startResearchBattle(code: string) {
  console.log('[DEBUG] startResearchBattle', code)
  resetDebate()
  debatePhase.value = 'research'
  try {
    const response = await researchBattleApi.stream({ code, num_rounds: debateRounds.value })
    console.log('[DEBUG] stream response', response.status, response.ok, !!response.body)
    if (!response.ok || !response.body) { console.log('[DEBUG] stream not ok, returning'); return }
    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''
      for (const line of lines) {
        if (!line.startsWith('data: ')) continue
        try {
          handleDebateEvent(JSON.parse(line.slice(6)))
        } catch { /* skip */ }
      }
    }
  } catch { console.log('[DEBUG] startResearchBattle caught exception') }
}

function handleDebateEvent(parsed: any) {
  const type = parsed.type
  const data = parsed.data
  console.log('[DEBUG] handleDebateEvent', type, data ? Object.keys(data) : null)
  switch (type) {
    case 'start': break
    case 'research:start': debatePhase.value = 'research'; console.log('[DEBUG] phase -> research'); break
    case 'research:agent_done': if (data) { debateResearchAgents.value.push(data); console.log('[DEBUG] agent pushed', data.agent_id, 'evidence keys:', Object.keys(data.evidence || {})); } break
    case 'battle:start': debatePhase.value = 'battle'; break
    case 'battle:round_done': if (data) debateRoundsHistory.value.push(data); break
    case 'judge:start': debatePhase.value = 'judge'; break
    case 'judge:done': case 'verdict': debateVerdict.value = data; debatePhase.value = 'done'; break
    case 'done': debatePhase.value = 'done'; break
    case 'error': debatePhase.value = 'done'; break
  }
}

function showDetail(signal: CombinedSignal) {
  detailSignal.value = signal
  showDetailDialog.value = true
}

// ── Main orchestrator ──
async function startCombinedAnalysis() {
  console.log('[DEBUG] startCombinedAnalysis called')
  if (!stockCode.value || (selectedIds.value.length === 0 && !enableDebate.value)) { console.log('[DEBUG] early return', { stock: stockCode.value, selLen: selectedIds.value.length, debate: enableDebate.value }); return }
  console.log('[DEBUG] starting analysis, code:', stockCode.value, 'debate:', enableDebate.value, 'tradCount:', traditionalCount.value)
  isRunning.value = true
  analysisId.value = Date.now().toString(36) + Math.random().toString(36).slice(2, 6)
  agentStore.resetAgents()
  philosophyStore.reset()
  resetDebate()
  const controller = new AbortController()
  abortController.value = controller
  const tasks: Promise<any>[] = [
    agentStore.startTask(stockCode.value, analysisType.value),
    philosophyStore.startAnalysis(stockCode.value, [...selectedIds.value]),
  ]
  if (enableDebate.value) tasks.push(startResearchBattle(stockCode.value))
  try {
    await Promise.allSettled(tasks)
  } catch { /* errors handled by each store */ }
  finally {
    isRunning.value = false
    abortController.value = null
  }
}

function stopAnalysis() {
  abortController.value?.abort()
  isRunning.value = false
}

function remoteSearch(query: string) {
  if (!query) {
    remoteOptions.value = watchlist.value.map(s => ({ value: s.code, label: `${s.code} ${s.name}` }))
    return
  }
  const q = query.toUpperCase()
  const matched = watchlist.value.filter(s => s.code.includes(q) || s.name.toUpperCase().includes(q))
  remoteOptions.value = matched.length
    ? matched.map(s => ({ value: s.code, label: `${s.code} ${s.name}` }))
    : [{ value: query, label: `手动输入: ${query}` }]
}

async function loadWatchlist() {
  try {
    const res = await watchlistApi.getWatchlist()
    watchlist.value = res.data?.data || res.data || []
    remoteOptions.value = watchlist.value.map(s => ({ value: s.code, label: `${s.code} ${s.name}` }))
    if (watchlist.value.length > 0 && !stockCode.value) {
      stockCode.value = watchlist.value[0].code
    }
  } catch { watchlist.value = [] }
}

onMounted(() => {
  philosophyStore.loadAgents()
  loadWatchlist()
})
</script>

<style scoped>
.multi-agent-panel {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.header-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.task-config {
  display: flex;
  gap: 12px;
  align-items: center;
  flex-wrap: wrap;
}
.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
}
.header-left {
  display: flex;
  align-items: center;
  gap: 8px;
}
.header-hint {
  font-size: 11px;
  color: #606266;
  font-weight: 400;
}
.header-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}
.selected-count {
  font-size: 12px;
  color: #909399;
  font-weight: 400;
}
.agent-selector {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.agent-group {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.group-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.group-label {
  font-size: 13px;
  color: #409eff;
  font-weight: 600;
}
.group-badge {
  font-size: 11px;
  color: #67c23a;
  font-weight: 400;
  margin-left: 8px;
}
.group-agents {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.agent-chip {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 4px 12px;
  background: #2c2c2c;
  border-radius: 16px;
  font-size: 12px;
  color: #c0c4cc;
  cursor: pointer;
  transition: all 0.2s;
  border: 1px solid transparent;
  user-select: none;
}
.agent-chip:hover {
  border-color: #409eff;
  color: #e5eaf3;
}
.agent-chip.selected {
  background: rgba(64, 158, 255, 0.15);
  border-color: #409eff;
  color: #409eff;
}
.analysis-results {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.debate-config {
  display: flex;
  align-items: center;
}
.config-row {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}
.config-label {
  font-size: 14px;
  font-weight: 600;
  color: #e5eaf3;
}
.config-hint {
  font-size: 11px;
  color: #606266;
}
.config-rounds {
  display: flex;
  align-items: center;
  gap: 6px;
}
.rounds-label {
  font-size: 12px;
  color: #909399;
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
  display: flex;
  justify-content: space-between;
}
.detail-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
}
.detail-section {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.detail-section.full {
  grid-column: 1 / -1;
}
.detail-label {
  font-size: 12px;
  color: #909399;
}
.detail-value {
  font-size: 15px;
  color: #e5eaf3;
  font-weight: 600;
}
.detail-value.mono {
  font-family: 'SF Mono', 'Fira Code', monospace;
  font-size: 13px;
  color: #c0c4cc;
}
.detail-unit {
  font-size: 12px;
  color: #606266;
  font-weight: 400;
}
.detail-content {
  background: #2c2c2c;
  padding: 12px;
  border-radius: 6px;
  font-size: 13px;
  color: #c0c4cc;
  line-height: 1.7;
  white-space: pre-wrap;
}
.detail-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.score-high { color: #67c23a; }
.score-mid { color: #409eff; }
.score-low { color: #f56c6c; }
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.3s ease;
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
