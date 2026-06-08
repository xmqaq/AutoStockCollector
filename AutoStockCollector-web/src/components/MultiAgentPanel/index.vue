<template>
  <div class="multi-agent-panel">
    <el-card shadow="never" class="section-card">
      <template #header>
        <div class="header-toolbar">
          <span>多Agent智能协作分析</span>
          <el-tag v-if="analysisId" type="success" size="small">#{{ analysisId.slice(0, 8) }}</el-tag>
        </div>
      </template>

      <div class="task-config">
        <el-select
          v-model="stockCode"
          filterable
          remote
          :remote-method="remoteSearch"
          placeholder="输入股票代码 或 从自选股选择"
          style="width: 240px"
          clearable
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

    <el-card shadow="never" class="section-card">
      <template #header>
        <div class="section-header">
          <div class="header-left">
            <span>选择参与分析的 Agent</span>
            <span class="header-hint">传统 6 个 + 投资哲学 {{ agents.length }} 个</span>
          </div>
          <div class="header-actions">
            <el-button size="small" text @click="philosophyStore.selectAll()" :disabled="!agents.length">
              全选哲学
            </el-button>
            <el-button size="small" text @click="philosophyStore.deselectAll()" :disabled="!selectedIds.length">
              取消
            </el-button>
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

    <transition v-if="isRunning || hasResults" name="fade">
      <div class="analysis-results">
        <el-card shadow="never" class="section-card">
          <template #header>
            <div class="section-header">
              <span>分析进度</span>
              <div class="progress-info">
                <span class="progress-text">传统: {{ agentStore.overallProgress }}%</span>
                <span class="progress-text">哲学: {{ philosophyStore.overallProgress }}%</span>
                <span class="progress-text" v-if="enableDebate">辩论: {{ debateProgress }}%</span>
              </div>
            </div>
          </template>
          <div class="dual-progress">
            <div class="progress-row">
              <span class="progress-label">传统分析</span>
              <el-progress :percentage="agentStore.overallProgress" :stroke-width="8" :status="agentProgressStatus" />
            </div>
            <div class="progress-row">
              <span class="progress-label">投资哲学</span>
              <el-progress :percentage="philosophyStore.overallProgress" :stroke-width="8" :status="philosophyProgressStatus" />
            </div>
            <div v-if="enableDebate" class="progress-row">
              <span class="progress-label">多空辩论</span>
              <el-progress :percentage="debateProgress" :stroke-width="8" :status="debateProgress >= 100 ? 'success' : undefined" />
            </div>
          </div>
        </el-card>

        <el-card v-if="combinedSignals.length" shadow="never" class="section-card dashboard-card">
          <template #header>
            <div class="section-header">
              <span>📊 决策参考看板</span>
              <div class="dashboard-actions">
                <el-tag :type="combinedVerdict.type" size="large" effect="dark" class="verdict-tag">
                  {{ combinedVerdict.label }}
                </el-tag>
              </div>
            </div>
          </template>

          <div class="dashboard-overview">
            <div class="overview-item">
              <div class="overview-value" :class="combinedVerdict.scoreClass">{{ combinedScore }}</div>
              <div class="overview-label">综合评分</div>
            </div>
            <div class="overview-item">
              <div class="overview-value">{{ bullishCount }}</div>
              <div class="overview-label">看多</div>
            </div>
            <div class="overview-item">
              <div class="overview-value">{{ bearishCount }}</div>
              <div class="overview-label">看空</div>
            </div>
            <div class="overview-item">
              <div class="overview-value">{{ neutralCount }}</div>
              <div class="overview-label">中性</div>
            </div>
            <div class="overview-item">
              <div class="overview-value">{{ combinedSignals.length }}</div>
              <div class="overview-label">参与Agent</div>
            </div>
          </div>

          <el-divider style="margin: 12px 0" />

          <div class="signal-groups">
            <div class="signal-group bullish">
              <div class="signal-group-header">
                <el-icon color="#67c23a"><Top /></el-icon>
                <span>看多信号 ({{ bullishSignals.length }})</span>
              </div>
              <div class="signal-cards">
                <div v-for="s in bullishSignals" :key="s.id" class="compact-signal" @click="showDetail(s)">
                  <span class="signal-source">{{ s.source }}</span>
                  <span class="signal-score" :class="scoreColor(s.score)">{{ s.score.toFixed(1) }}</span>
                  <span class="signal-action">{{ actionLabel(s.action) }}</span>
                </div>
                <el-empty v-if="!bullishSignals.length" description="暂无看多信号" :image-size="40" />
              </div>
            </div>

            <div class="signal-group neutral">
              <div class="signal-group-header">
                <el-icon color="#e6a23c"><Minus /></el-icon>
                <span>中性信号 ({{ neutralSignals.length }})</span>
              </div>
              <div class="signal-cards">
                <div v-for="s in neutralSignals" :key="s.id" class="compact-signal" @click="showDetail(s)">
                  <span class="signal-source">{{ s.source }}</span>
                  <span class="signal-score" :class="scoreColor(s.score)">{{ s.score.toFixed(1) }}</span>
                  <span class="signal-action">{{ actionLabel(s.action) }}</span>
                </div>
                <el-empty v-if="!neutralSignals.length" description="暂无中性信号" :image-size="40" />
              </div>
            </div>

            <div class="signal-group bearish">
              <div class="signal-group-header">
                <el-icon color="#f56c6c"><Bottom /></el-icon>
                <span>看空信号 ({{ bearishSignals.length }})</span>
              </div>
              <div class="signal-cards">
                <div v-for="s in bearishSignals" :key="s.id" class="compact-signal" @click="showDetail(s)">
                  <span class="signal-source">{{ s.source }}</span>
                  <span class="signal-score" :class="scoreColor(s.score)">{{ s.score.toFixed(1) }}</span>
                  <span class="signal-action">{{ actionLabel(s.action) }}</span>
                </div>
                <el-empty v-if="!bearishSignals.length" description="暂无看空信号" :image-size="40" />
              </div>
            </div>
          </div>

          <el-divider style="margin: 12px 0" />

        </el-card>

        <el-card v-if="agentStore.aggregatedResult" shadow="never" class="section-card">
          <template #header>
            <div class="section-header">
              <span>传统 Agent 详细分析</span>
              <el-tag :type="getRecommendType(agentStore.aggregatedResult.recommendation)" size="large">
                {{ agentStore.aggregatedResult.recommendation }}
              </el-tag>
            </div>
          </template>

          <el-table :data="agentStore.aggregatedResult.agentResults" stripe size="small">
            <el-table-column prop="name" label="Agent" width="100" />
            <el-table-column prop="score" label="评分" width="70">
              <template #default="{ row }">
                <span :class="getScoreClass(row.score)">{{ row.score.toFixed(1) }}</span>
              </template>
            </el-table-column>
            <el-table-column prop="conclusion" label="结论" />
            <el-table-column prop="recommendation" label="建议" width="100">
              <template #default="{ row }">
                <el-tag size="small" :type="getRecommendType(row.recommendation)">{{ row.recommendation }}</el-tag>
              </template>
            </el-table-column>
          </el-table>
        </el-card>

        <el-card v-if="philosophyStore.agentSignals.length" shadow="never" class="section-card">
          <template #header>
            <div class="section-header">
              <span>投资哲学 Agent 详细研判</span>
              <div class="header-actions">
                <el-tag size="small">{{ philosophyStore.agentSignals.length }} 个信号</el-tag>
              </div>
            </div>
          </template>

          <div class="signals-grid">
            <div v-for="signal in philosophyStore.agentSignals" :key="signal.agent_id" class="signal-card">
              <div class="signal-header">
                <span class="signal-name">{{ signal.agent_name }}</span>
                <el-tag size="small" :type="actionTagType(signal.action)">
                  {{ actionLabel(signal.action) }}
                </el-tag>
              </div>
              <div class="signal-score-row">
                <span class="score-value" :class="scoreColor(signal.score)">{{ signal.score.toFixed(1) }}</span>
                <span class="score-label">分</span>
                <span class="confidence">&nbsp;· 置信 {{ (signal.confidence * 100).toFixed(0) }}%</span>
              </div>
              <div class="signal-reasoning">{{ signal.reasoning?.slice(0, 120) }}</div>
              <div class="signal-footer">
                <div v-if="signal.key_factors?.length" class="signal-tags">
                  <el-tag v-for="(f, i) in signal.key_factors.slice(0, 3)" :key="i" size="small" type="info">{{ f }}</el-tag>
                </div>
                <el-button size="small" text type="primary" @click.stop="showDetail({ ...signal, id: `phi-${signal.agent_id}`, source: 'philosophy' })">详情</el-button>
              </div>
            </div>
          </div>
          <el-card v-if="debateVerdict" shadow="never" class="section-card debate-result-card">
            <template #header>
              <div class="section-header">
                <span>多空辩论结果</span>
                <el-tag :type="debateVerdictTagType" size="large">{{ debateVerdictWinning }}</el-tag>
              </div>
            </template>
            <div class="debate-verdict">
              <div class="verdict-stats">
                <div class="stat-item">
                  <div class="stat-value" :class="debateTendencyClass">{{ (debateVerdict.final_tendency * 100).toFixed(1) }}</div>
                  <div class="stat-label">倾向指数</div>
                </div>
                <div class="stat-item">
                  <div class="stat-value">{{ (debateVerdict.consensus_level * 100).toFixed(1) }}%</div>
                  <div class="stat-label">共识度</div>
                </div>
                <div class="stat-item">
                  <div class="stat-value">{{ (debateVerdict.confidence * 100).toFixed(1) }}%</div>
                  <div class="stat-label">置信度</div>
                </div>
                <div class="stat-item">
                  <div class="stat-value">{{ debateResearchAgents.length }}</div>
                  <div class="stat-label">研究员</div>
                </div>
                <div class="stat-item">
                  <div class="stat-value">{{ debateRounds }}</div>
                  <div class="stat-label">辩论轮数</div>
                </div>
              </div>
              <div v-if="debateVerdict.key_insights?.length" class="debate-insights">
                <div class="section-subtitle">关键洞察</div>
                <ul class="insight-list">
                  <li v-for="(insight, i) in debateVerdict.key_insights" :key="i">{{ insight }}</li>
                </ul>
              </div>
              <div v-if="debateVerdict.risk_flags?.length" class="debate-risks">
                <div class="section-subtitle">风险提示</div>
                <div class="risk-tags">
                  <el-tag v-for="(flag, i) in debateVerdict.risk_flags" :key="i" type="danger" size="small">{{ flag }}</el-tag>
                </div>
              </div>
            </div>
          </el-card>

          <el-card v-if="debateResearchAgents.length" shadow="never" class="section-card">
            <template #header>
              <div class="section-header">
                <span>辩论研究员分析</span>
                <el-tag size="small">{{ debateResearchAgents.length }} 个研究员</el-tag>
              </div>
            </template>
            <div class="signals-grid">
              <div v-for="agent in debateResearchAgents" :key="agent.agent_id" class="signal-card">
                <div class="signal-header">
                  <span class="signal-name">{{ agent.agent_name }}</span>
                  <el-tag size="small" :type="debateSignalTag(agent.signal)">
                    {{ debateSignalLabel(agent.signal) }}
                  </el-tag>
                </div>
                <div class="signal-score-row">
                  <span class="score-value" :class="debateSignalScore(agent.signal)">{{ (agent.confidence * 100).toFixed(0) }}</span>
                  <span class="score-label">置信</span>
                </div>
                <div v-if="agent.key_findings?.length" class="signal-findings">
                  <div v-for="(finding, i) in agent.key_findings.slice(0, 3)" :key="i" class="finding-item">· {{ finding }}</div>
                </div>
                <div v-if="agent.data_sources?.length" class="signal-tags" style="margin-top: 6px">
                  <el-tag v-for="(src, i) in agent.data_sources" :key="i" size="small" type="info">{{ src }}</el-tag>
                </div>
              </div>
            </div>
          </el-card>

          <el-card v-if="debateRoundsHistory.length" shadow="never" class="section-card">
            <template #header>
              <div class="section-header">
                <span>辩论回合记录</span>
                <el-tag size="small">{{ debateRoundsHistory.length }} 轮</el-tag>
              </div>
            </template>
            <div v-for="(round, ri) in debateRoundsHistory" :key="ri" class="debate-round">
              <div class="round-header">
                <span class="round-title">第 {{ round.round }} 轮</span>
                <span class="round-consensus" v-if="round.consensus_shift">
                  共识偏移: {{ (round.consensus_shift * 100).toFixed(1) }}
                </span>
              </div>
              <div v-for="(arg, ai) in round.arguments" :key="ai"
                :class="['argument-item', arg.stance === 'bullish' ? 'bull' : 'bear']">
                <div class="argument-header">
                  <span class="arg-stance">{{ arg.stance === 'bullish' ? '🐂' : '🐻' }}</span>
                  <span class="arg-agent">{{ arg.agent_name }}</span>
                </div>
                <div class="argument-text">{{ arg.argument }}</div>
              </div>
            </div>
          </el-card>
        </el-card>
      </div>
    </transition>

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
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { Check, MagicStick, User, Top, Bottom, Minus } from '@element-plus/icons-vue'
import { useAgentStore, type AgentState } from '@/stores/agentStore'
import { usePhilosophyStore } from '@/stores/philosophyStore'
import { watchlistApi } from '@/api/watchlist'
import { researchBattleApi } from '@/api/ai'
const agentStore = useAgentStore()
const philosophyStore = usePhilosophyStore()

const stockCode = ref('')
const analysisType = ref('comprehensive')
const isRunning = ref(false)
const watchlist = ref<{ code: string; name: string }[]>([])
const remoteOptions = ref<{ value: string; label: string }[]>([])
const analysisId = ref('')
const abortController = ref<AbortController | null>(null)

const showDetailDialog = ref(false)
const detailSignal = ref<CombinedSignal | null>(null)

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
  signals?: string[]
}

const enableDebate = ref(false)
const debateRounds = ref(3)
const debatePhase = ref<'idle' | 'research' | 'battle' | 'judge' | 'done'>('idle')
const debateResearchAgents = ref<any[]>([])
const debateRoundsHistory = ref<{ round: number; arguments: any[]; consensus_shift?: number }[]>([])
const debateVerdict = ref<any>(null)

const debateProgress = computed(() => {
  switch (debatePhase.value) {
    case 'research': return 30
    case 'battle':
      const total = debateRounds.value
      const done = debateRoundsHistory.value.length
      return 30 + Math.round((done / total) * 50)
    case 'judge': return 85
    case 'done': return 100
    default: return 0
  }
})

const traditionalAgents = computed(() => agentStore.agents.filter(a => a.role !== 'commander'))
const traditionalCount = computed(() => traditionalAgents.value.length)
const agents = computed(() => philosophyStore.agents)
const selectedIds = computed(() => philosophyStore.selectedIds)

const hasResults = computed(() =>
  combinedSignals.value.length > 0 || agentStore.aggregatedResult !== null ||
  philosophyStore.agentSignals.length > 0 || debateVerdict.value !== null
)

const agentProgressStatus = computed(() =>
  agentStore.isAllCompleted ? 'success' : isRunning.value ? 'warning' : undefined
)

const philosophyProgressStatus = computed(() =>
  philosophyStore.isAllCompleted ? 'success' : isRunning.value ? '' : undefined
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

const combinedSignals = computed<CombinedSignal[]>(() => {
  const result: CombinedSignal[] = []

  for (const a of agentStore.agents) {
    if (a.role === 'commander' || !a.result) continue
    result.push({
      id: `trad-${a.id}`,
      agent_id: a.id,
      agent_name: a.name,
      source: 'traditional',
      score: a.result.score || 50,
      action: mapRecommendationToAction(a.result.recommendation),
      reasoning: a.result.conclusion,
      key_factors: a.result.signals,
    })
  }

  for (const s of philosophyStore.agentSignals) {
    result.push({
      id: `phi-${s.agent_id}`,
      agent_id: s.agent_id,
      agent_name: s.agent_name,
      source: 'philosophy',
      score: s.score,
      action: s.action,
      archetype: s.archetype,
      reasoning: s.reasoning,
      key_factors: s.key_factors,
      risk_warnings: s.risk_warnings,
      confidence: s.confidence,
      signals: (s as any).signals,
    })
  }

  for (const a of debateResearchAgents.value) {
    const action = a.signal === 'bullish' ? 'buy' : a.signal === 'bearish' ? 'sell' : 'hold'
    result.push({
      id: `research-${a.agent_id}`,
      agent_id: a.agent_id,
      agent_name: a.agent_name,
      source: 'research',
      score: a.confidence * 100,
      action,
      archetype: a.archetype,
      reasoning: a.raw_analysis?.slice(0, 200),
      key_factors: a.key_findings,
      confidence: a.confidence,
    })
  }

  return result
})

function mapRecommendationToAction(rec?: string): string {
  if (!rec) return 'hold'
  if (rec.includes('强烈推荐') || rec.includes('买入')) return 'buy'
  if (rec.includes('回避') || rec.includes('卖出')) return 'sell'
  if (rec.includes('持有') || rec.includes('观望')) return 'hold'
  return 'hold'
}

function isBullish(signal: CombinedSignal): boolean {
  return ['strong_buy', 'buy', '强烈推荐', '买入建议'].includes(signal.action) ||
    (signal.action === '买入建议' || signal.action === '强烈推荐')
}

function isBearish(signal: CombinedSignal): boolean {
  return ['strong_sell', 'sell', '回避', '建议观望'].includes(signal.action) ||
    signal.action === '建议观望'
}

const bullishSignals = computed(() => {
  const bullishActions = ['strong_buy', 'buy', '强烈推荐', '买入建议']
  return combinedSignals.value.filter(s => bullishActions.includes(s.action))
    .sort((a, b) => b.score - a.score)
})

const bearishSignals = computed(() => {
  const bearishActions = ['strong_sell', 'sell', '回避', '建议观望']
  return combinedSignals.value.filter(s => bearishActions.includes(s.action))
    .sort((a, b) => b.score - a.score)
})

const neutralSignals = computed(() => {
  const allActions = combinedSignals.value.map(s => s.action)
  return combinedSignals.value.filter(s =>
    !bullishSignals.value.includes(s) && !bearishSignals.value.includes(s)
  ).sort((a, b) => b.score - a.score)
})

const bullishCount = computed(() => bullishSignals.value.length)
const bearishCount = computed(() => bearishSignals.value.length)
const neutralCount = computed(() => neutralSignals.value.length)

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
      if (!selectedIds.value.includes(a.id)) {
        selectedIds.value.push(a.id)
      }
    }
  }
}

function actionLabel(action: string): string {
  const map: Record<string, string> = {
    strong_buy: '强烈买入', buy: '买入', hold: '持有',
    sell: '卖出', strong_sell: '强烈卖出',
    强烈推荐: '强烈推荐', 买入建议: '买入建议',
    持有建议: '持有建议', 建议观望: '建议观望',
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

function getScoreClass(score: number): string {
  return scoreColor(score)
}

function getRecommendType(rec?: string): string {
  if (!rec) return 'info'
  if (rec.includes('推荐') || rec.includes('买入')) return 'success'
  if (rec.includes('谨慎') || rec.includes('观望') || rec.includes('持有')) return 'warning'
  if (rec.includes('回避')) return 'danger'
  return 'info'
}

function sourceLabel(source: string): string {
  const map: Record<string, string> = { traditional: '传统分析', philosophy: '投资哲学', research: '辩论研究员' }
  return map[source] || source
}

function debateSignalTag(signal: string): string {
  return signal === 'bullish' ? 'success' : signal === 'bearish' ? 'danger' : 'info'
}
function debateSignalLabel(signal: string): string {
  return signal === 'bullish' ? '看多' : signal === 'bearish' ? '看空' : '中性'
}
function debateSignalScore(signal: string): string {
  return signal === 'bullish' ? 'score-high' : signal === 'bearish' ? 'score-low' : 'score-mid'
}

const debateVerdictWinning = computed(() => {
  if (!debateVerdict.value) return ''
  const side = debateVerdict.value.winning_side
  if (side === 'bullish') return '多头胜'
  if (side === 'bearish') return '空头胜'
  return '平局'
})
const debateVerdictTagType = computed(() => {
  const side = debateVerdict.value?.winning_side
  if (side === 'bullish') return 'success'
  if (side === 'bearish') return 'danger'
  return 'warning'
})
const debateTendencyClass = computed(() => {
  const t = debateVerdict.value?.final_tendency || 0
  if (t > 0.1) return 'score-bull'
  if (t < -0.1) return 'score-bear'
  return 'score-neutral'
})

function resetDebate() {
  debatePhase.value = 'idle'
  debateResearchAgents.value = []
  debateRoundsHistory.value = []
  debateVerdict.value = null
}

async function startResearchBattle(code: string) {
  resetDebate()
  debatePhase.value = 'research'

  try {
    const response = await researchBattleApi.stream({ code, num_rounds: debateRounds.value })
    if (!response.ok || !response.body) return

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
          const parsed = JSON.parse(line.slice(6))
          handleDebateEvent(parsed)
        } catch { /* skip */ }
      }
    }
  } catch { /* handled inline */ }
}

function handleDebateEvent(parsed: any) {
  const type = parsed.type
  const data = parsed.data

  switch (type) {
    case 'start': break
    case 'research:start':
      debatePhase.value = 'research'
      break
    case 'research:agents':
      // agents list from backend
      break
    case 'research:agent_done':
      if (data) debateResearchAgents.value.push(data)
      break
    case 'research:done':
      break
    case 'battle:start':
      debatePhase.value = 'battle'
      break
    case 'battle:round_done':
      if (data) debateRoundsHistory.value.push(data)
      break
    case 'battle:done':
      break
    case 'judge:start':
      debatePhase.value = 'judge'
      break
    case 'judge:done':
    case 'verdict':
      debateVerdict.value = data
      debatePhase.value = 'done'
      break
    case 'done':
      debatePhase.value = 'done'
      break
    case 'error':
      debatePhase.value = 'done'
      break
  }
}

function showDetail(signal: CombinedSignal) {
  detailSignal.value = signal
  showDetailDialog.value = true
}

async function startCombinedAnalysis() {
  if (!stockCode.value || (selectedIds.value.length === 0 && !enableDebate.value)) return

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

  if (enableDebate.value) {
    tasks.push(startResearchBattle(stockCode.value))
  }

  try {
    await Promise.allSettled(tasks)
  } catch {
    // errors handled by each store
  } finally {
    isRunning.value = false
    abortController.value = null
  }
}

function stopAnalysis() {
  abortController.value?.abort()
  isRunning.value = false
  // individual stores may still have running requests
}

function remoteSearch(query: string) {
  if (!query) {
    remoteOptions.value = watchlist.value.map(s => ({ value: s.code, label: `${s.code} ${s.name}` }))
    return
  }
  const q = query.toUpperCase()
  const matched = watchlist.value.filter(s => s.code.includes(q) || s.name.toUpperCase().includes(q))
  if (matched.length > 0) {
    remoteOptions.value = matched.map(s => ({ value: s.code, label: `${s.code} ${s.name}` }))
  } else {
    remoteOptions.value = [{ value: query, label: `手动输入: ${query}` }]
  }
}

async function loadWatchlist() {
  try {
    const res = await watchlistApi.getWatchlist()
    watchlist.value = res.data?.data || res.data || []
    remoteOptions.value = watchlist.value.map(s => ({ value: s.code, label: `${s.code} ${s.name}` }))
    if (watchlist.value.length > 0 && !stockCode.value) {
      stockCode.value = watchlist.value[0].code
    }
  } catch {
    watchlist.value = []
  }
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
  gap: 16px;
}
.progress-info {
  display: flex;
  gap: 16px;
}
.progress-text {
  font-size: 12px;
  color: #909399;
  font-weight: 400;
}
.dual-progress {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.progress-row {
  display: flex;
  align-items: center;
  gap: 12px;
}
.progress-label {
  font-size: 12px;
  color: #c0c4cc;
  white-space: nowrap;
  width: 60px;
}
.dashboard-card {
  border: 1px solid #409eff;
}
.dashboard-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}
.verdict-tag {
  font-size: 14px;
  font-weight: 600;
  border: none;
}
.dashboard-overview {
  display: flex;
  gap: 24px;
  justify-content: center;
  padding: 8px 0;
}
.overview-item {
  flex: 1;
  min-width: 80px;
  text-align: center;
}
.overview-value {
  font-size: 28px;
  font-weight: 700;
  color: #409eff;
}
.overview-label {
  font-size: 11px;
  color: #606266;
  margin-top: 2px;
}
.score-bull { color: #67c23a; }
.score-bear { color: #f56c6c; }
.score-neutral { color: #e6a23c; }
.signal-groups {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
}
.signal-group-header {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  color: #c0c4cc;
  margin-bottom: 8px;
}
.signal-cards {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.compact-signal {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 10px;
  background: #2c2c2c;
  border-radius: 6px;
  cursor: pointer;
  transition: background 0.15s;
}
.compact-signal:hover {
  background: #3c3c3c;
}
.signal-source {
  font-size: 12px;
  color: #e5eaf3;
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.signal-score {
  font-size: 14px;
  font-weight: 700;
  min-width: 28px;
  text-align: right;
}
.signal-action {
  font-size: 11px;
  color: #909399;
  min-width: 48px;
  text-align: right;
}
.signals-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
  gap: 12px;
}
.signal-card {
  background: #2c2c2c;
  border-radius: 8px;
  padding: 12px;
  border: 1px solid #3c3c3c;
}
.signal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}
.signal-name {
  font-size: 13px;
  font-weight: 600;
  color: #e5eaf3;
}
.signal-score-row {
  display: flex;
  align-items: baseline;
  gap: 2px;
  margin-bottom: 6px;
}
.score-high { color: #67c23a; }
.score-mid { color: #409eff; }
.score-low { color: #f56c6c; }
.score-label {
  font-size: 11px;
  color: #909399;
}
.confidence {
  font-size: 11px;
  color: #606266;
}
.signal-reasoning {
  font-size: 11px;
  color: #909399;
  line-height: 1.5;
  margin-bottom: 8px;
}
.signal-tags :deep(.el-tag) {
  background: #1f1f1f;
  border: none;
  color: #c0c4cc;
}
.signal-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 8px;
}
.signal-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
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
.debate-result-card {
  border: 1px solid #e6a23c;
}
.debate-verdict {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.verdict-stats {
  display: flex;
  gap: 24px;
  justify-content: center;
}
.section-subtitle {
  font-size: 13px;
  color: #c0c4cc;
  font-weight: 600;
  margin-bottom: 8px;
}
.insight-list {
  list-style: none;
  padding: 0;
  margin: 0;
}
.insight-list li {
  padding: 4px 0;
  font-size: 12px;
  color: #909399;
  line-height: 1.5;
}
.insight-list li::before {
  content: '▶ ';
  color: #409eff;
}
.risk-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.signal-findings {
  font-size: 11px;
  color: #909399;
  line-height: 1.6;
}
.finding-item {
  padding: 1px 0;
}
.debate-round {
  background: #2c2c2c;
  border-radius: 8px;
  padding: 12px;
  margin-bottom: 8px;
}
.round-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}
.round-title {
  font-size: 13px;
  font-weight: 600;
  color: #e5eaf3;
}
.round-consensus {
  font-size: 11px;
  color: #909399;
}
.argument-item {
  padding: 8px;
  border-radius: 6px;
  margin-bottom: 4px;
}
.argument-item.bull {
  background: rgba(103, 194, 58, 0.08);
}
.argument-item.bear {
  background: rgba(245, 108, 108, 0.08);
}
.argument-header {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 4px;
}
.arg-stance {
  font-size: 14px;
}
.arg-agent {
  font-size: 12px;
  color: #c0c4cc;
  font-weight: 600;
}
.argument-text {
  font-size: 12px;
  color: #909399;
  line-height: 1.5;
}
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.3s ease;
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
