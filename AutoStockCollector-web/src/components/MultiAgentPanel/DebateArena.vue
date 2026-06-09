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
          <div class="col-header bull-header">🐂 多头观点</div>
          <div v-for="(arg, ai) in currentRound.arguments" :key="ai">
            <div v-if="arg.stance === 'bullish'" class="arg-card bull-arg">
              <div class="arg-agent-row">
                <span class="arg-agent-icon">🐂</span>
                <span class="arg-agent-name">{{ arg.agent_name }}</span>
              </div>
              <div class="arg-text">{{ arg.argument }}</div>
            </div>
          </div>
          <el-empty v-if="!bullCount" :image-size="30" description="暂无多头观点" />
        </div>
        <div class="arena-divider"></div>
        <div class="arena-col bear-col">
          <div class="col-header bear-header">🐻 空头观点</div>
          <div v-for="(arg, ai) in currentRound.arguments" :key="ai">
            <div v-if="arg.stance === 'bearish'" class="arg-card bear-arg">
              <div class="arg-agent-row">
                <span class="arg-agent-icon">🐻</span>
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
  color: #606266;
  font-weight: 400;
}
.consensus-chart {
  background: #2c2c2c;
  border-radius: 8px;
  padding: 12px;
  margin-bottom: 12px;
}
.chart-title {
  font-size: 12px;
  color: #909399;
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
.bar.bull { background: linear-gradient(180deg, #67c23a, #95de64); }
.bar.bear { background: linear-gradient(180deg, #f56c6c, #ff7875); }
.bar-label {
  font-size: 10px;
  color: #606266;
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
  color: #909399;
}
.dot {
  width: 8px;
  height: 8px;
  border-radius: 2px;
}
.dot.bull { background: #67c23a; }
.dot.bear { background: #f56c6c; }
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
  background: #2c2c2c;
  color: #909399;
  cursor: pointer;
  transition: all 0.15s;
  display: flex;
  align-items: center;
  gap: 4px;
}
.round-tab.active {
  background: #409eff;
  color: #fff;
}
.round-tab:hover:not(.active) {
  color: #e5eaf3;
}
.shift {
  font-size: 10px;
  font-weight: 600;
}
.shift.bull { color: #67c23a; }
.shift.bear { color: #f56c6c; }
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
  background: #3c3c3c;
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
.bull-header { color: #67c23a; }
.bear-header { color: #f56c6c; }
.arg-card {
  padding: 10px;
  border-radius: 6px;
}
.bull-arg {
  background: rgba(103,194,58,0.06);
  border: 1px solid rgba(103,194,58,0.15);
}
.bear-arg {
  background: rgba(245,108,108,0.06);
  border: 1px solid rgba(245,108,108,0.15);
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
  color: #c0c4cc;
}
.arg-text {
  font-size: 12px;
  color: #909399;
  line-height: 1.5;
}
.section-card {
  background: #1f1f1f;
  border: 1px solid #2c2c2c;
  margin-top: 16px;
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
