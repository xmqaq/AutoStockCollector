<template>
  <el-card v-if="verdict" shadow="never" class="section-card verdict-card">
    <template #header>
      <div class="section-header">
        <span>④ 法官判决结果</span>
        <el-tag :type="winningTagType" size="large" effect="dark">
          {{ winningLabel }}
        </el-tag>
      </div>
    </template>
    <div class="verdict-content">
      <div class="verdict-main">
        <div class="verdict-stat">
          <div class="stat-value" :class="tendencyClass">{{ (verdict.final_tendency * 100).toFixed(1) }}</div>
          <div class="stat-label">倾向指数</div>
        </div>
        <div class="verdict-stat">
          <div class="stat-value">{{ (verdict.confidence * 100).toFixed(1) }}%</div>
          <div class="stat-label">置信度</div>
        </div>
        <div class="verdict-stat">
          <div class="stat-value">{{ (verdict.consensus_level * 100).toFixed(1) }}%</div>
          <div class="stat-label">共识度</div>
        </div>
        <div class="verdict-stat">
          <div class="stat-value">{{ researcherCount }}</div>
          <div class="stat-label">研究员</div>
        </div>
        <div class="verdict-stat">
          <div class="stat-value">{{ roundCount }}</div>
          <div class="stat-label">辩论轮数</div>
        </div>
      </div>

      <div v-if="verdict.key_insights?.length" class="verdict-section">
        <div class="section-subtitle section-title"> 关键洞察</div>
        <ul class="insight-list">
          <li v-for="(insight, i) in verdict.key_insights" :key="i">{{ insight }}</li>
        </ul>
      </div>

      <div v-if="verdict.risk_flags?.length" class="verdict-section">
        <div class="section-subtitle section-title"> 风险提示</div>
        <div class="risk-tags">
          <el-tag v-for="(flag, i) in verdict.risk_flags" :key="i" type="danger" size="small">{{ flag }}</el-tag>
        </div>
      </div>
    </div>
  </el-card>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  verdict: any
  researcherCount: number
  roundCount: number
}>()

const winningLabel = computed(() => {
  const side = props.verdict?.winning_side
  if (side === 'bullish') return '多头胜'
  if (side === 'bearish') return '空头胜'
  return '平局'
})

const winningTagType = computed(() => {
  const side = props.verdict?.winning_side
  if (side === 'bullish') return 'success'
  if (side === 'bearish') return 'danger'
  return 'warning'
})

const tendencyClass = computed(() => {
  const t = props.verdict?.final_tendency || 0
  if (t > 0.1) return 'score-bull'
  if (t < -0.1) return 'score-bear'
  return 'score-neutral'
})
</script>

<style scoped>
.verdict-card {
  border: 1px solid var(--el-color-warning);
  margin-top: 16px;
}
.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.verdict-content {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.verdict-main {
  display: flex;
  gap: 24px;
  justify-content: center;
}
.verdict-stat {
  flex: 1;
  min-width: 60px;
  text-align: center;
}
.stat-value {
  font-size: 24px;
  font-weight: 700;
  color: var(--el-color-primary);
}
.stat-label {
  font-size: 11px;
  color: var(--text-faint);
  margin-top: 2px;
}
.score-bull { color: var(--el-color-success); }
.score-bear { color: var(--el-color-danger); }
.score-neutral { color: var(--el-color-warning); }
.verdict-section { }
.section-subtitle {
  font-size: 13px;
  color: var(--text-secondary);
  font-weight: 600;
  margin-bottom: 8px;
  display: flex;
  align-items: center;
  gap: 6px;
}
.section-icon { font-size: 14px; }
.insight-list {
  list-style: none;
  padding: 0;
  margin: 0;
}
.insight-list li {
  padding: 4px 0;
  font-size: 12px;
  color: var(--text-muted);
  line-height: 1.5;
}
.insight-list li::before {
  content: '▶ ';
  color: var(--el-color-primary);
}
.risk-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
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
</style>
