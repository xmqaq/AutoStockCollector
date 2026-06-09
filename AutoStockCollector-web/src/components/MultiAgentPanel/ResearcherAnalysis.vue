<template>
  <div v-if="debateResearchers.length || philosophySignals.length" class="researcher-section">
    <el-card shadow="never" class="section-card">
      <template #header>
        <div class="section-header">
          <span>② 研究员分析报告（{{ totalCount }} 位）</span>
          <div class="header-tabs">
            <span :class="['tab-btn', { active: activeTab === 'all' }]" @click="activeTab = 'all'">全部</span>
            <span :class="['tab-btn', { active: activeTab === 'bullish' }]" @click="activeTab = 'bullish'">看多</span>
            <span :class="['tab-btn', { active: activeTab === 'bearish' }]" @click="activeTab = 'bearish'">看空</span>
            <span :class="['tab-btn', { active: activeTab === 'neutral' }]" @click="activeTab = 'neutral'">中性</span>
          </div>
        </div>
      </template>
      <div class="researcher-groups">
        <div v-if="visibleDebate.length" class="agent-group-block">
          <div class="group-title">
            <span class="group-icon">🗣️</span>
            <span>辩论研究员</span>
            <span class="group-count">{{ visibleDebate.length }} 位</span>
          </div>
          <div class="signals-grid">
            <div
              v-for="agent in visibleDebate" :key="'d-' + agent.agent_id"
              :class="['signal-card', signalClass(agent.signal)]"
              @click="$emit('show-detail', { ...agent, id: 'research-' + agent.agent_id, source: 'research', score: (agent.confidence || 0.5) * 100, action: agent.signal === 'bullish' ? 'buy' : agent.signal === 'bearish' ? 'sell' : 'hold', reasoning: agent.raw_analysis?.slice(0, 200) })"
            >
              <div class="signal-header-row">
                <span class="signal-name">{{ agent.agent_name }}</span>
                <span :class="['signal-tag', agent.signal]">{{ signalLabel(agent.signal) }}</span>
              </div>
              <div class="signal-body">
                <div class="confidence-bar">
                  <div class="confidence-fill" :class="agent.signal" :style="{ width: ((agent.confidence || 0.5) * 100) + '%' }"></div>
                </div>
                <span class="confidence-text">{{ ((agent.confidence || 0.5) * 100).toFixed(0) }}% 置信</span>
              </div>
              <div v-if="agent.key_findings?.length" class="signal-findings">
                <div v-for="(f, i) in agent.key_findings.slice(0, 2)" :key="i" class="finding-item">▸ {{ f }}</div>
              </div>
              <div v-if="agent.data_sources?.length" class="signal-tags">
                <span v-for="src in agent.data_sources" :key="src" class="data-source-tag">{{ src }}</span>
              </div>
            </div>
          </div>
        </div>
        <div v-if="visiblePhilosophy.length" class="agent-group-block">
          <div class="group-title">
            <span class="group-icon">🧠</span>
            <span>投资哲学 Agent</span>
            <span class="group-count">{{ visiblePhilosophy.length }} 位</span>
          </div>
          <div class="signals-grid">
            <div
              v-for="signal in visiblePhilosophy" :key="'p-' + signal.agent_id"
              :class="['signal-card', 'philosophy', actionTagType(signal.action)]"
              @click="$emit('show-detail', { ...signal, id: 'phi-' + signal.agent_id, source: 'philosophy' })"
            >
              <div class="signal-header-row">
                <span class="signal-name">{{ signal.agent_name }}</span>
                <el-tag size="small" :type="actionTagType(signal.action)">
                  {{ actionLabel(signal.action) }}
                </el-tag>
              </div>
              <div class="signal-score-row">
                <span class="score-value" :class="scoreColor(signal.score)">{{ signal.score.toFixed(1) }}</span>
                <span class="score-label">分</span>
                <span class="confidence-sep">· 置信 {{ (signal.confidence * 100).toFixed(0) }}%</span>
              </div>
              <div class="signal-reasoning">{{ signal.reasoning?.slice(0, 100) }}</div>
              <div v-if="signal.key_factors?.length" class="signal-tags">
                <span v-for="(f, i) in signal.key_factors.slice(0, 2)" :key="i" class="factor-tag">{{ f }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'

const props = defineProps<{
  debateResearchers: any[]
  philosophySignals: any[]
}>()

defineEmits<{
  'show-detail': [signal: any]
}>()

const activeTab = ref<'all' | 'bullish' | 'bearish' | 'neutral'>('all')

const totalCount = computed(() => props.debateResearchers.length + props.philosophySignals.length)

const visibleDebate = computed(() => {
  if (activeTab.value === 'all') return props.debateResearchers
  return props.debateResearchers.filter(a => {
    const s = a.signal
    if (activeTab.value === 'bullish') return s === 'bullish'
    if (activeTab.value === 'bearish') return s === 'bearish'
    return s === 'neutral'
  })
})

const visiblePhilosophy = computed(() => {
  if (activeTab.value === 'all') return props.philosophySignals
  return props.philosophySignals.filter(s => {
    const a = s.action
    if (activeTab.value === 'bullish') return ['buy', 'strong_buy', '强烈推荐', '买入建议'].includes(a)
    if (activeTab.value === 'bearish') return ['sell', 'strong_sell', '回避', '建议观望'].includes(a)
    return ['hold', '持有建议', '持有'].includes(a)
  })
})

function signalLabel(signal: string): string {
  return signal === 'bullish' ? '看多' : signal === 'bearish' ? '看空' : '中性'
}
function signalClass(signal: string): string {
  return signal === 'bullish' ? 'bullish' : signal === 'bearish' ? 'bearish' : 'neutral'
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
</script>

<style scoped>
.researcher-section { margin-top: 16px; }
.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
}
.header-tabs {
  display: flex;
  gap: 4px;
  background: #2c2c2c;
  border-radius: 6px;
  padding: 2px;
}
.tab-btn {
  font-size: 11px;
  font-weight: 400;
  padding: 3px 10px;
  border-radius: 4px;
  cursor: pointer;
  color: #909399;
  transition: all 0.15s;
}
.tab-btn.active {
  background: #409eff;
  color: #fff;
}
.tab-btn:hover:not(.active) {
  color: #e5eaf3;
}
.researcher-groups {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.agent-group-block {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.group-title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  font-weight: 600;
  color: #e5eaf3;
}
.group-icon { font-size: 16px; }
.group-count {
  font-size: 11px;
  font-weight: 400;
  color: #909399;
}
.signals-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 10px;
}
.signal-card {
  background: #2c2c2c;
  border-radius: 8px;
  padding: 12px;
  border: 1px solid #3c3c3c;
  cursor: pointer;
  transition: all 0.2s;
}
.signal-card:hover {
  border-color: #409eff;
  transform: translateY(-1px);
}
.signal-card.bullish { border-left: 3px solid #67c23a; }
.signal-card.bearish { border-left: 3px solid #f56c6c; }
.signal-card.neutral { border-left: 3px solid #e6a23c; }
.signal-card.philosophy { border-left: 3px solid #409eff; }
.signal-card.philosophy.success { border-left-color: #67c23a; }
.signal-card.philosophy.danger { border-left-color: #f56c6c; }
.signal-card.philosophy.info { border-left-color: #e6a23c; }
.signal-header-row {
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
.signal-tag {
  font-size: 10px;
  padding: 1px 8px;
  border-radius: 8px;
  font-weight: 600;
}
.signal-tag.bullish { background: rgba(103,194,58,0.15); color: #67c23a; }
.signal-tag.bearish { background: rgba(245,108,108,0.15); color: #f56c6c; }
.signal-tag.neutral { background: rgba(230,162,60,0.15); color: #e6a23c; }
.signal-body {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}
.confidence-bar {
  flex: 1;
  height: 4px;
  background: #1f1f1f;
  border-radius: 2px;
  overflow: hidden;
}
.confidence-fill {
  height: 100%;
  border-radius: 2px;
  transition: width 0.5s ease;
}
.confidence-fill.bullish { background: #67c23a; }
.confidence-fill.bearish { background: #f56c6c; }
.confidence-fill.neutral { background: #e6a23c; }
.confidence-text {
  font-size: 11px;
  color: #909399;
  white-space: nowrap;
}
.signal-score-row {
  display: flex;
  align-items: baseline;
  gap: 2px;
  margin-bottom: 6px;
}
.score-value { font-size: 16px; font-weight: 700; }
.score-high { color: #67c23a; }
.score-mid { color: #409eff; }
.score-low { color: #f56c6c; }
.score-label { font-size: 11px; color: #909399; }
.confidence-sep { font-size: 11px; color: #606266; }
.signal-reasoning {
  font-size: 11px;
  color: #909399;
  line-height: 1.5;
  margin-bottom: 6px;
}
.signal-findings {
  font-size: 11px;
  color: #909399;
  line-height: 1.6;
  margin-bottom: 6px;
}
.finding-item {
  padding: 1px 0;
}
.signal-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}
.data-source-tag {
  font-size: 10px;
  padding: 1px 6px;
  border-radius: 4px;
  background: #1f1f1f;
  color: #606266;
}
.factor-tag {
  font-size: 10px;
  padding: 1px 6px;
  border-radius: 4px;
  background: rgba(64,158,255,0.1);
  color: #409eff;
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
</style>
