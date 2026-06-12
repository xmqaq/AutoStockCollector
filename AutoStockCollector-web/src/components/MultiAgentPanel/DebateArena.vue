<template>
  <el-card v-if="rounds.length" shadow="never" class="section-card">
    <template #header>
      <div class="section-header">
        <span>③ 多空辩论（{{ rounds.length }} 轮）</span>
        <div class="header-extra">
          <span class="consensus-text">共识度 {{ (latestConsensus * 100).toFixed(0) }}%</span>
          <el-tag v-if="consensusDirection" size="small" :type="consensusDirection === 'bullish' ? 'success' : 'danger'">
            {{ consensusDirection === 'bullish' ? '偏多' : '偏空' }}
          </el-tag>
        </div>
      </div>
    </template>

    <!-- Consensus Evolution Chart -->
    <div v-if="consensusHistory.length > 1" class="consensus-chart">
      <div class="chart-title">共识演化</div>
      <div class="chart-bars">
        <div
          v-for="(c, i) in consensusHistory" :key="i"
          class="chart-bar-group"
        >
          <div class="bar-column">
            <div class="bar bull" :style="{ height: bullHeight(c) + '%' }"></div>
            <div class="bar bear" :style="{ height: bearHeight(c) + '%' }"></div>
          </div>
          <div class="bar-label">R{{ i + 1 }}</div>
        </div>
      </div>
      <div class="chart-legend">
        <span class="legend-item"><span class="dot bull"></span>看多</span>
        <span class="legend-item"><span class="dot bear"></span>看空</span>
      </div>
    </div>

    <!-- Round Tabs -->
    <div class="round-tabs">
      <div
        v-for="(round, ri) in rounds" :key="ri"
        :class="['round-tab', { active: activeRound === ri }]"
        @click="activeRound = ri"
      >
        第 {{ round.round || ri + 1 }} 轮
        <span v-if="round.consensus_shift" class="shift" :class="round.consensus_shift > 0 ? 'bull' : 'bear'">
          {{ round.consensus_shift > 0 ? '↑' : '↓' }}{{ (Math.abs(round.consensus_shift) * 100).toFixed(0) }}
        </span>
      </div>
    </div>

    <!-- Active Round Arguments -->
    <div v-if="currentRound" class="round-arena">
      <div class="arena-columns">
        <div class="arena-col bull-col">
          <div class="col-header bull-header">多头观点</div>
          <div v-for="(arg, ai) in currentRound.arguments" :key="ai">
            <div v-if="arg.stance === 'bullish'" class="arg-card bull-arg">
              <div class="arg-agent-row">
                <span class="arg-agent-icon">▲</span>
                <span class="arg-agent-name">{{ arg.agent_name }}</span>
              </div>
              <div class="arg-text">{{ arg.argument }}</div>
            </div>
          </div>
          <el-empty v-if="!bullCount" :image-size="30" description="暂无多头观点" />
        </div>
        <div class="arena-divider"></div>
        <div class="arena-col bear-col">
          <div class="col-header bear-header">空头观点</div>
          <div v-for="(arg, ai) in currentRound.arguments" :key="ai">
            <div v-if="arg.stance === 'bearish'" class="arg-card bear-arg">
              <div class="arg-agent-row">
                <span class="arg-agent-icon">▼</span>
                <span class="arg-agent-name">{{ arg.agent_name }}</span>
              </div>
              <div class="arg-text">{{ arg.argument }}</div>
            </div>
          </div>
          <el-empty v-if="!bearCount" :image-size="30" description="暂无空头观点" />
        </div>
      </div>
    </div>
  </el-card>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'

const props = defineProps<{
  rounds: any[]
  verdict?: any
}>()

const activeRound = ref(0)

const currentRound = computed(() => props.rounds[activeRound.value])
const bullCount = computed(() => (currentRound.value?.arguments || []).filter((a: any) => a.stance === 'bullish').length)
const bearCount = computed(() => (currentRound.value?.arguments || []).filter((a: any) => a.stance === 'bearish').length)

const consensusHistory = computed(() => {
  return props.rounds.map((r: any) => {
    const bulls = (r.arguments || []).filter((a: any) => a.stance === 'bullish').length
    const bears = (r.arguments || []).filter((a: any) => a.stance === 'bearish').length
    const total = bulls + bears || 1
    return { bulls: bulls / total, bears: bears / total }
  })
})

const latestConsensus = computed(() => {
  if (!consensusHistory.value.length) return 0
  const last = consensusHistory.value[consensusHistory.value.length - 1]
  return Math.max(last.bulls, last.bears)
})

const consensusDirection = computed(() => {
  if (!consensusHistory.value.length) return ''
  const last = consensusHistory.value[consensusHistory.value.length - 1]
  if (last.bulls > last.bears) return 'bullish'
  if (last.bears > last.bulls) return 'bearish'
  return ''
})

function bullHeight(c: { bulls: number; bears: number }): number {
  return Math.max(c.bulls * 100, 4)
}
function bearHeight(c: { bulls: number; bears: number }): number {
  return Math.max(c.bears * 100, 4)
}
</script>

<style scoped>
.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
}
.header-extra {
  display: flex;
  align-items: center;
  gap: 8px;
}
.consensus-text {
  font-size: 12px;
  color: var(--text-faint);
  font-weight: 400;
}
.consensus-chart {
  background: var(--border-color);
  border-radius: 8px;
  padding: 12px;
  margin-bottom: 12px;
}
.chart-title {
  font-size: 12px;
  color: var(--text-muted);
  margin-bottom: 8px;
}
.chart-bars {
  display: flex;
  align-items: flex-end;
  gap: 16px;
  height: 80px;
  padding: 0 8px;
}
.chart-bar-group {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
}
.bar-column {
  width: 24px;
  height: 60px;
  display: flex;
  flex-direction: column-reverse;
  gap: 2px;
}
.bar {
  width: 100%;
  border-radius: 3px 3px 0 0;
  transition: height 0.5s ease;
  min-height: 4px;
}
.bar.bull { background: linear-gradient(180deg, var(--el-color-success), #95de64); }
.bar.bear { background: linear-gradient(180deg, var(--el-color-danger), #ff7875); }
.bar-label {
  font-size: 10px;
  color: var(--text-faint);
}
.chart-legend {
  display: flex;
  gap: 16px;
  justify-content: center;
  margin-top: 8px;
}
.legend-item {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 11px;
  color: var(--text-muted);
}
.dot {
  width: 8px;
  height: 8px;
  border-radius: 2px;
}
.dot.bull { background: var(--el-color-success); }
.dot.bear { background: var(--el-color-danger); }
.round-tabs {
  display: flex;
  gap: 6px;
  margin-bottom: 12px;
  flex-wrap: wrap;
}
.round-tab {
  font-size: 12px;
  padding: 5px 12px;
  border-radius: 6px;
  background: var(--border-color);
  color: var(--text-muted);
  cursor: pointer;
  transition: all 0.15s;
  display: flex;
  align-items: center;
  gap: 4px;
}
.round-tab.active {
  background: var(--el-color-primary);
  color: #fff;
}
.round-tab:hover:not(.active) {
  color: var(--text-primary);
}
.shift {
  font-size: 10px;
  font-weight: 600;
}
.shift.bull { color: var(--el-color-success); }
.shift.bear { color: var(--el-color-danger); }
.round-arena {
  border-radius: 8px;
  overflow: hidden;
}
.arena-columns {
  display: grid;
  grid-template-columns: 1fr 1px 1fr;
  gap: 0;
}
.arena-divider {
  background: var(--border-strong);
  height: 100%;
}
.arena-col {
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.col-header {
  font-size: 13px;
  font-weight: 600;
  margin-bottom: 4px;
}
.bull-header { color: var(--el-color-success); }
.bear-header { color: var(--el-color-danger); }
.arg-card {
  padding: 10px;
  border-radius: 6px;
}
.bull-arg {
  background: rgba(52, 138, 93, 0.06);
  border: 1px solid rgba(52, 138, 93, 0.15);
}
.bear-arg {
  background: rgba(196, 69, 60, 0.06);
  border: 1px solid rgba(196, 69, 60, 0.15);
}
.arg-agent-row {
  display: flex;
  align-items: center;
  gap: 4px;
  margin-bottom: 4px;
}
.arg-agent-icon { font-size: 12px; }
.arg-agent-name {
  font-size: 11px;
  font-weight: 600;
  color: var(--text-secondary);
}
.arg-text {
  font-size: 12px;
  color: var(--text-muted);
  line-height: 1.5;
}
.section-card {
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  margin-top: 16px;
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
</style>
