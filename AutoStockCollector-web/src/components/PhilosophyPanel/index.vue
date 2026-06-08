<template>
  <div class="philosophy-panel">
    <el-card shadow="never" class="section-card">
      <template #header>
        <div class="header-toolbar">
          <span>投资哲学多Agent分析</span>
          <div class="header-actions">
            <el-button size="small" @click="philosophyStore.selectAll()" :disabled="!philosophyStore.agents.length">全选</el-button>
            <el-button size="small" @click="philosophyStore.deselectAll()" :disabled="!philosophyStore.selectedIds.length">取消</el-button>
          </div>
        </div>
      </template>

      <div class="task-config">
        <el-select v-model="localCode" placeholder="选择股票" filterable style="width: 200px">
          <el-option v-for="s in watchlist" :key="s.code" :label="`${s.code} ${s.name}`" :value="s.code" />
        </el-select>
        <el-button type="primary" @click="startAnalysis" :loading="philosophyStore.isAnalyzing" :disabled="!localCode || !philosophyStore.selectedIds.length">
          开始分析
        </el-button>
      </div>
    </el-card>

    <el-card shadow="never" class="section-card">
      <template #header>
        <div class="section-header">
          <span>选择投资哲学 Agent</span>
          <span class="selected-count">已选 {{ philosophyStore.selectedIds.length }} / {{ philosophyStore.agents.length }}</span>
        </div>
      </template>

      <div class="philosophy-groups">
        <div v-for="(group, school) in groupedAgents" :key="school" class="philosophy-group">
          <div class="group-header">
            <span class="group-label">{{ schoolLabels[school] || school }}</span>
            <el-button size="small" text @click="toggleGroup(school)">
              {{ isGroupSelected(school) ? '取消全选' : '全选' }}
            </el-button>
          </div>
          <div class="group-agents">
            <div v-for="agent in group" :key="agent.id"
              :class="['agent-chip', { selected: philosophyStore.selectedIds.includes(agent.id) }]"
              @click="philosophyStore.toggleAgent(agent.id)"
            >
              <el-icon v-if="philosophyStore.selectedIds.includes(agent.id)"><Check /></el-icon>
              <span>{{ agent.name }}</span>
            </div>
          </div>
        </div>
      </div>
    </el-card>

    <el-card v-if="philosophyStore.isAnalyzing || philosophyStore.phase !== 'idle'" shadow="never" class="section-card">
      <template #header>
        <div class="section-header">
          <span>分析进度</span>
          <el-progress :percentage="philosophyStore.overallProgress" :stroke-width="8" style="width: 200px" />
        </div>
      </template>

      <div class="phase-indicator">
        <el-steps :active="stepIndex" align-center finish-status="success" size="small">
          <el-step title="数据获取" />
          <el-step title="因子计算" />
          <el-step title="Agent研判" />
          <el-step title="综合裁决" />
        </el-steps>
      </div>

      <div v-if="philosophyStore.agentSignals.length" class="signals-grid">
        <div v-for="signal in philosophyStore.agentSignals" :key="signal.agent_id" class="signal-card">
          <div class="signal-header">
            <span class="signal-name">{{ signal.agent_name }}</span>
            <el-tag size="small" :type="actionTagType(signal.action)">
              {{ actionLabel(signal.action) }}
            </el-tag>
          </div>
          <div class="signal-score">
            <span class="score-value" :class="scoreClass(signal.score)">{{ signal.score.toFixed(1) }}</span>
            <span class="score-label">分</span>
          </div>
          <div class="signal-reasoning">{{ signal.reasoning?.slice(0, 120) }}</div>
          <div class="signal-footer">
            <div v-if="signal.key_factors?.length" class="signal-tags">
              <el-tag v-for="(s, i) in signal.key_factors.slice(0, 2)" :key="i" size="small" type="info">{{ s }}</el-tag>
            </div>
            <el-button size="small" text type="primary" @click.stop="showSignalDetail(signal)">详情</el-button>
          </div>
        </div>
      </div>

      <el-empty v-else-if="philosophyStore.isAnalyzing" description="等待 Agent 返回结果..." :image-size="60" />

      <el-alert v-if="philosophyStore.error" type="error" :closable="false" show-icon>
        {{ philosophyStore.error }}
      </el-alert>
    </el-card>

    <el-card v-if="philosophyStore.verdict" shadow="never" class="section-card verdict-card">
      <template #header>
        <div class="section-header">
          <span>综合裁决</span>
          <el-tag :type="verdictTagType" size="large">{{ verdictAction }}</el-tag>
        </div>
      </template>

      <div class="verdict-stats">
        <div class="stat-item">
          <div class="stat-value" :class="verdictScoreClass">{{ tendencyScore }}</div>
          <div class="stat-label">倾向指数</div>
        </div>
        <div class="stat-item">
          <div class="stat-value">{{ (philosophyStore.verdict.consensus?.consensus_level * 100 || 0).toFixed(0) }}%</div>
          <div class="stat-label">共识度</div>
        </div>
        <div class="stat-item">
          <div class="stat-value">{{ (philosophyStore.verdict.consensus?.confidence * 100 || 0).toFixed(0) }}%</div>
          <div class="stat-label">置信度</div>
        </div>
        <div class="stat-item">
          <div class="stat-value">{{ philosophyStore.verdict.agent_signals?.length || 0 }}</div>
          <div class="stat-label">参与Agent</div>
        </div>
      </div>

      <div v-if="philosophyStore.verdict.consensus" class="verdict-meta">
        <span>多头: {{ philosophyStore.verdict.consensus.positive_count }} | 空头: {{ philosophyStore.verdict.consensus.negative_count }}</span>
        <el-tag v-if="philosophyStore.verdict.consensus.high_conviction" type="success" size="small">高确信信号</el-tag>
      </div>
    </el-card>

    <el-dialog v-model="showDetailDialog" :title="detailSignal?.agent_name || 'Agent 详情'" width="700px" top="5vh">
      <template v-if="detailSignal">
        <div class="detail-grid">
          <div class="detail-section">
            <div class="detail-label">投资哲学</div>
            <div class="detail-value">{{ detailSignal.philosophy || '--' }}</div>
          </div>
          <div class="detail-section">
            <div class="detail-label">流派</div>
            <div class="detail-value">{{ schoolLabels[detailSignal.archetype || ''] || detailSignal.archetype || '--' }}</div>
          </div>
          <div class="detail-section">
            <div class="detail-label">评分</div>
            <div class="detail-value">
              <span :class="scoreClass(detailSignal.score)">{{ detailSignal.score.toFixed(1) }}</span>
              <span class="detail-unit">/ 100</span>
            </div>
          </div>
          <div class="detail-section">
            <div class="detail-label">操作建议</div>
            <div class="detail-value">
              <el-tag :type="actionTagType(detailSignal.action)" size="large">
                {{ actionLabel(detailSignal.action) }}
              </el-tag>
            </div>
          </div>
          <div class="detail-section">
            <div class="detail-label">置信度</div>
            <div class="detail-value">{{ (detailSignal.confidence * 100).toFixed(0) }}%</div>
          </div>
          <div class="detail-section">
            <div class="detail-label">Agent ID</div>
            <div class="detail-value">{{ detailSignal.agent_id }}</div>
          </div>
        </div>

        <el-divider />

        <div class="detail-section full">
          <div class="detail-label">分析推理</div>
          <div class="detail-content">{{ detailSignal.reasoning }}</div>
        </div>

        <div v-if="detailSignal.key_factors?.length" class="detail-section full">
          <div class="detail-label">关键因子</div>
          <div class="detail-tags">
            <el-tag v-for="(f, i) in detailSignal.key_factors" :key="i" type="success" size="small">{{ f }}</el-tag>
          </div>
        </div>

        <div v-if="detailSignal.risk_warnings?.length" class="detail-section full">
          <div class="detail-label">风险警告</div>
          <div class="detail-tags">
            <el-tag v-for="(w, i) in detailSignal.risk_warnings" :key="i" type="danger" size="small">{{ w }}</el-tag>
          </div>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { Check } from '@element-plus/icons-vue'
import { usePhilosophyStore } from '@/stores/philosophyStore'
import { watchlistApi } from '@/api/watchlist'
import type { PhilosophySignal } from '@/api/ai'

const philosophyStore = usePhilosophyStore()

const localCode = ref('')
const watchlist = ref<{ code: string; name: string }[]>([])

const showDetailDialog = ref(false)
const detailSignal = ref<PhilosophySignal | null>(null)

function showSignalDetail(signal: PhilosophySignal) {
  detailSignal.value = signal
  showDetailDialog.value = true
}

const schoolLabels: Record<string, string> = {
  value: '价值派',
  growth: '成长派',
  technical: '技术派',
  macro: '宏观派',
  quant: '量化派',
  hot_money: '游资派',
  risk: '风控派',
  sentiment: '舆情派',
}

const groupedAgents = computed(() => {
  const groups: Record<string, any[]> = {}
  for (const a of philosophyStore.agents) {
    const s = a.school || 'other'
    if (!groups[s]) groups[s] = []
    groups[s].push(a)
  }
  return groups
})

const stepIndex = computed(() => {
  switch (philosophyStore.phase) {
    case 'data': return 0
    case 'factor': return 1
    case 'agent': return 2
    case 'verdict':
    case 'done': return 3
    default: return 0
  }
})

const tendencyScore = computed(() => {
  const t = philosophyStore.verdict?.consensus?.tendency
  if (t == null) return '--'
  return (t * 100).toFixed(0)
})

const verdictAction = computed(() => {
  const t = philosophyStore.verdict?.consensus?.tendency
  if (t == null) return '未知'
  if (t > 0.1) return '看多'
  if (t < -0.1) return '看空'
  return '中性'
})

const verdictTagType = computed(() => {
  const t = philosophyStore.verdict?.consensus?.tendency
  if (t == null) return 'info'
  if (t > 0.1) return 'success'
  if (t < -0.1) return 'danger'
  return 'warning'
})

const verdictScoreClass = computed(() => {
  const t = philosophyStore.verdict?.consensus?.tendency
  if (t == null) return ''
  if (t > 0.1) return 'score-bull'
  if (t < -0.1) return 'score-bear'
  return 'score-neutral'
})

function isGroupSelected(school: string): boolean {
  const group = groupedAgents.value[school]
  if (!group?.length) return false
  return group.every(a => philosophyStore.selectedIds.includes(a.id))
}

function toggleGroup(school: string) {
  const group = groupedAgents.value[school]
  if (!group?.length) return
  const allSelected = isGroupSelected(school)
  for (const a of group) {
    if (allSelected) {
      const idx = philosophyStore.selectedIds.indexOf(a.id)
      if (idx >= 0) philosophyStore.selectedIds.splice(idx, 1)
    } else {
      if (!philosophyStore.selectedIds.includes(a.id)) {
        philosophyStore.selectedIds.push(a.id)
      }
    }
  }
}

function actionLabel(action: string): string {
  const map: Record<string, string> = {
    strong_buy: '强烈买入', buy: '买入', hold: '持有', sell: '卖出', strong_sell: '强烈卖出',
  }
  return map[action] || action
}

function actionTagType(action: string): string {
  if (['strong_buy', 'buy'].includes(action)) return 'success'
  if (['strong_sell', 'sell'].includes(action)) return 'danger'
  return 'info'
}

function scoreClass(score: number): string {
  if (score >= 70) return 'score-high'
  if (score >= 50) return 'score-mid'
  return 'score-low'
}

async function startAnalysis() {
  if (!localCode.value || !philosophyStore.selectedIds.length) return
  philosophyStore.startAnalysis(localCode.value, [...philosophyStore.selectedIds])
}

async function loadWatchlist() {
  try {
    const res = await watchlistApi.getWatchlist()
    watchlist.value = res.data?.data || res.data || []
    if (watchlist.value.length > 0) {
      localCode.value = watchlist.value[0].code
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
.philosophy-panel {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.header-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.header-actions {
  display: flex;
  gap: 8px;
}
.task-config {
  display: flex;
  gap: 12px;
  align-items: center;
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
.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.selected-count {
  font-size: 12px;
  color: #909399;
  font-weight: 400;
}
.philosophy-groups {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.philosophy-group {
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
.phase-indicator {
  margin-bottom: 16px;
}
.phase-indicator :deep(.el-step__title) {
  font-size: 12px;
}
.signals-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
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
.signal-score {
  display: flex;
  align-items: baseline;
  gap: 2px;
  margin-bottom: 6px;
}
.score-value {
  font-size: 22px;
  font-weight: 700;
}
.score-label {
  font-size: 11px;
  color: #909399;
}
.score-high { color: #67c23a; }
.score-mid { color: #409eff; }
.score-low { color: #f56c6c; }
.signal-reasoning {
  font-size: 11px;
  color: #909399;
  line-height: 1.5;
  margin-bottom: 8px;
}
.signal-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
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
.verdict-card {
  border: 1px solid #409eff;
}
.verdict-stats {
  display: flex;
  gap: 24px;
  justify-content: center;
  margin-bottom: 12px;
}
.stat-item {
  flex: 1;
  min-width: 80px;
  text-align: center;
}
.stat-value {
  font-size: 24px;
  font-weight: 700;
  color: #409eff;
}
.stat-label {
  font-size: 11px;
  color: #606266;
  margin-top: 2px;
}
.score-bull { color: #67c23a; }
.score-bear { color: #f56c6c; }
.score-neutral { color: #e6a23c; }
.verdict-meta {
  display: flex;
  align-items: center;
  gap: 12px;
  justify-content: center;
  font-size: 12px;
  color: #909399;
}
</style>
