<template>
  <el-card v-if="signals.length" shadow="never" class="section-card dashboard-card">
    <template #header>
      <div class="section-header">
        <span>⑤ 决策参考看板（全部 Agent 汇总）</span>
        <el-tag :type="verdict.type" size="large" effect="dark" class="verdict-tag">
          {{ verdict.label }}
        </el-tag>
      </div>
    </template>

    <div class="dashboard-overview">
      <div class="overview-item">
        <div class="overview-value" :class="verdict.scoreClass">{{ score }}</div>
        <div class="overview-label">综合评分</div>
      </div>
      <div class="overview-item">
        <div class="overview-value bullish-count">{{ bullishCount }}</div>
        <div class="overview-label">看多</div>
      </div>
      <div class="overview-item">
        <div class="overview-value bearish-count">{{ bearishCount }}</div>
        <div class="overview-label">看空</div>
      </div>
      <div class="overview-item">
        <div class="overview-value neutral-count">{{ neutralCount }}</div>
        <div class="overview-label">中性</div>
      </div>
      <div class="overview-item">
        <div class="overview-value total-count">{{ signals.length }}</div>
        <div class="overview-label">参与Agent</div>
      </div>
    </div>

    <el-divider style="margin: 12px 0" />

    <div class="signal-groups">
      <div class="signal-group">
        <div class="signal-group-header green">
          <span>看多信号 ({{ bullishSignals.length }})</span>
        </div>
        <div class="signal-cards">
          <div v-for="s in bullishSignals" :key="s.id" class="compact-signal" @click="$emit('show-detail', s)">
            <span class="signal-source" :class="'src-' + s.source">{{ sourceLabel(s.source) }}</span>
            <span class="signal-name-text">{{ s.agent_name }}</span>
            <span class="signal-score green">{{ s.score.toFixed(1) }}</span>
          </div>
          <el-empty v-if="!bullishSignals.length" :image-size="30" description="暂无看多信号" />
        </div>
      </div>

      <div class="signal-group">
        <div class="signal-group-header yellow">
          <span>中性信号 ({{ neutralSignals.length }})</span>
        </div>
        <div class="signal-cards">
          <div v-for="s in neutralSignals" :key="s.id" class="compact-signal" @click="$emit('show-detail', s)">
            <span class="signal-source" :class="'src-' + s.source">{{ sourceLabel(s.source) }}</span>
            <span class="signal-name-text">{{ s.agent_name }}</span>
            <span class="signal-score yellow">{{ s.score.toFixed(1) }}</span>
          </div>
          <el-empty v-if="!neutralSignals.length" :image-size="30" description="暂无中性信号" />
        </div>
      </div>

      <div class="signal-group">
        <div class="signal-group-header red">
          <span>看空信号 ({{ bearishSignals.length }})</span>
        </div>
        <div class="signal-cards">
          <div v-for="s in bearishSignals" :key="s.id" class="compact-signal" @click="$emit('show-detail', s)">
            <span class="signal-source" :class="'src-' + s.source">{{ sourceLabel(s.source) }}</span>
            <span class="signal-name-text">{{ s.agent_name }}</span>
            <span class="signal-score red">{{ s.score.toFixed(1) }}</span>
          </div>
          <el-empty v-if="!bearishSignals.length" :image-size="30" description="暂无看空信号" />
        </div>
      </div>
    </div>

    <el-divider style="margin: 12px 0" />

    <div class="bottom-toggles">
      <div v-if="traditionalSignals.length" class="toggle-section">
        <div class="toggle-header" @click="showTraditional = !showTraditional">
          <span>{{ showTraditional ? '▼' : '▶' }} 传统 Agent 详细分析（{{ traditionalSignals.length }}）</span>
        </div>
        <div v-if="showTraditional" class="toggle-content">
          <el-table :data="traditionalSignals" stripe size="small">
            <el-table-column prop="agent_name" label="Agent" width="100" />
            <el-table-column prop="score" label="评分" width="70">
              <template #default="{ row }">
                <span :class="scoreColor(row.score)">{{ row.score.toFixed(1) }}</span>
              </template>
            </el-table-column>
            <el-table-column prop="action" label="建议" width="80">
              <template #default="{ row }">
                <el-tag size="small" :type="actionTagType(row.action)">{{ actionLabel(row.action) }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="reasoning" label="结论" />
          </el-table>
        </div>
      </div>

      <div v-if="philosophySignals.length" class="toggle-section">
        <div class="toggle-header" @click="showPhilosophy = !showPhilosophy">
          <span>{{ showPhilosophy ? '▼' : '▶' }} 投资哲学 Agent 详细分析（{{ philosophySignals.length }}）</span>
        </div>
        <div v-if="showPhilosophy" class="toggle-content">
          <div class="signals-grid">
            <div v-for="signal in philosophySignals" :key="'p-' + signal.agent_id" class="signal-card">
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
              <div class="signal-reasoning">{{ signal.reasoning?.slice(0, 120) }}</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </el-card>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'

const props = defineProps<{
  signals: any[]
  traditionalSignals: any[]
  philosophySignals: any[]
  score: string
  verdict: { label: string; type: string; scoreClass: string }
}>()

defineEmits<{
  'show-detail': [signal: any]
}>()

const showTraditional = ref(false)
const showPhilosophy = ref(false)

const bullishSignals = computed(() => {
  const ba = ['strong_buy', 'buy', '强烈推荐', '买入建议']
  return props.signals.filter((s: any) => ba.includes(s.action)).sort((a: any, b: any) => b.score - a.score)
})
const bearishSignals = computed(() => {
  const ba = ['strong_sell', 'sell', '回避', '建议观望']
  return props.signals.filter((s: any) => ba.includes(s.action)).sort((a: any, b: any) => b.score - a.score)
})
const neutralSignals = computed(() => {
  return props.signals.filter((s: any) =>
    !['strong_buy', 'buy', '强烈推荐', '买入建议', 'strong_sell', 'sell', '回避', '建议观望'].includes(s.action)
  ).sort((a: any, b: any) => b.score - a.score)
})
const bullishCount = computed(() => bullishSignals.value.length)
const bearishCount = computed(() => bearishSignals.value.length)
const neutralCount = computed(() => neutralSignals.value.length)

function sourceLabel(source: string): string {
  const map: Record<string, string> = { traditional: '传统', philosophy: '哲学', research: '辩论' }
  return map[source] || source
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
.dashboard-card {
  border: 1px solid var(--el-color-primary);
  margin-top: 16px;
}
.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
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
  color: var(--el-color-primary);
}
.bullish-count { color: var(--el-color-success); }
.bearish-count { color: var(--el-color-danger); }
.neutral-count { color: var(--el-color-warning); }
.total-count { color: var(--el-color-primary); }
.overview-label {
  font-size: 11px;
  color: var(--text-faint);
  margin-top: 2px;
}
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
  margin-bottom: 8px;
  font-weight: 600;
}
.signal-group-header.green { color: var(--el-color-success); }
.signal-group-header.yellow { color: var(--el-color-warning); }
.signal-group-header.red { color: var(--el-color-danger); }
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
  background: var(--border-color);
  border-radius: 6px;
  cursor: pointer;
  transition: background 0.15s;
}
.compact-signal:hover {
  background: var(--border-strong);
}
.signal-source {
  font-size: 10px;
  padding: 1px 6px;
  border-radius: 4px;
  background: var(--bg-card);
  color: var(--text-faint);
}
.signal-source.src-traditional { color: var(--el-color-primary); }
.signal-source.src-philosophy { color: #b37feb; }
.signal-source.src-research { color: var(--el-color-success); }
.signal-name-text {
  font-size: 12px;
  color: var(--text-primary);
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
.signal-score.green { color: var(--el-color-success); }
.signal-score.yellow { color: var(--el-color-warning); }
.signal-score.red { color: var(--el-color-danger); }
.bottom-toggles {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.toggle-section {
  border-radius: 6px;
  overflow: hidden;
}
.toggle-header {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 12px;
  background: var(--border-color);
  cursor: pointer;
  font-size: 12px;
  color: var(--text-secondary);
  border-radius: 6px;
  transition: background 0.15s;
}
.toggle-header:hover {
  background: var(--border-strong);
}
.toggle-content {
  padding: 12px;
  background: var(--bg-card);
}
.signals-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 10px;
}
.signal-card {
  background: var(--border-color);
  border-radius: 8px;
  padding: 12px;
  border: 1px solid var(--border-strong);
}
.signal-header-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 6px;
}
.signal-name {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
}
.signal-score-row {
  display: flex;
  align-items: baseline;
  gap: 2px;
  margin-bottom: 4px;
}
.score-value { font-size: 16px; font-weight: 700; }
.score-high { color: var(--el-color-success); }
.score-mid { color: var(--el-color-primary); }
.score-low { color: var(--el-color-danger); }
.score-label { font-size: 11px; color: var(--text-muted); }
.confidence-sep { font-size: 11px; color: var(--text-faint); }
.signal-reasoning {
  font-size: 11px;
  color: var(--text-muted);
  line-height: 1.5;
}
.section-card {
  background: var(--bg-card);
  border: 1px solid var(--border-color);
}
.section-card :deep(.el-card__header) {
  border-bottom: 1px solid var(--border-color);
  padding: 12px 16px;
  color: var(--text-primary);
  font-size: 14px;
  font-weight: 600;
  display: flex;
  justify-content: space-between;
}
@media (max-width: 900px) {
  .signal-groups { grid-template-columns: 1fr; }
}
</style>
