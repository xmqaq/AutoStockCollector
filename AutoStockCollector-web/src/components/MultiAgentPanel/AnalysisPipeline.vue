<template>
  <el-card v-if="visible" shadow="never" class="section-card">
    <template #header>
      <div class="section-header">
        <span>分析流程</span>
      </div>
    </template>
    <div class="pipeline">
      <div
        v-for="(stage, i) in stages" :key="i"
        :class="['pipeline-stage', stage.status]"
        @click="$emit('scroll-to', stage.id)"
      >
        <div class="stage-indicator">
          <div v-if="stage.status === 'done'" class="stage-icon done"><el-icon><Check /></el-icon></div>
          <div v-else-if="stage.status === 'active'" class="stage-icon active">{{ i + 1 }}</div>
          <div v-else class="stage-icon pending">{{ i + 1 }}</div>
          <div v-if="i < stages.length - 1" :class="['stage-line', stage.status === 'done' ? 'done' : '']"></div>
        </div>
        <div class="stage-content">
          <div class="stage-label">{{ stage.label }}</div>
          <div class="stage-desc">{{ stage.desc }}</div>
          <div v-if="stage.progress !== undefined" class="stage-progress-bar">
            <div class="stage-progress-fill" :style="{ width: stage.progress + '%' }"></div>
          </div>
        </div>
      </div>
    </div>
  </el-card>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  phase: string
  dataReady: boolean
  researchersReady: boolean
  debateRounds: number
  debateRoundsDone: number
  verdictReady: boolean
  hasSignals: boolean
}>()

defineEmits<{
  'scroll-to': [id: string]
}>()

const visible = computed(() => props.dataReady || props.researchersReady || props.verdictReady || props.hasSignals)

const stages = computed(() => [
  {
    id: 'data-collection',
    label: '数据采集',
    desc: '6大维度',
    status: props.dataReady ? 'done' : (props.phase !== 'idle' ? 'active' : 'pending'),
    progress: props.dataReady ? 100 : (props.phase !== 'idle' ? 60 : 0),
  },
  {
    id: 'researcher-analysis',
    label: '研究员分析',
    desc: '辩论研究员 + 哲学Agent',
    status: props.researchersReady ? 'done' : (props.dataReady ? 'active' : 'pending'),
    progress: props.researchersReady ? 100 : (props.dataReady ? 50 : 0),
  },
  {
    id: 'debate',
    label: '多空辩论',
    desc: `${props.debateRounds}轮`,
    status: props.verdictReady ? 'done' : (props.phase === 'battle' || props.phase === 'judge' ? 'active' : 'pending'),
    progress: props.verdictReady ? 100 : (props.debateRounds > 0 ? Math.round((props.debateRoundsDone / props.debateRounds) * 100) : 0),
  },
  {
    id: 'judge',
    label: '法官判决',
    desc: '最终结论',
    status: props.verdictReady ? 'done' : (props.phase === 'judge' ? 'active' : 'pending'),
    progress: props.verdictReady ? 100 : (props.phase === 'judge' ? 50 : 0),
  },
  {
    id: 'dashboard',
    label: '决策看板',
    desc: '全部信号汇总',
    status: props.hasSignals ? 'done' : 'pending',
    progress: props.hasSignals ? 100 : 0,
  },
])
</script>

<style scoped>
.section-card {
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  margin-bottom: 4px;
}
.section-card :deep(.el-card__header) {
  border-bottom: 1px solid var(--border-color);
  padding: 10px 16px;
  color: var(--text-primary);
  font-size: 14px;
  font-weight: 600;
}
.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.pipeline {
  display: flex;
  gap: 0;
  padding: 4px 0;
}
.pipeline-stage {
  flex: 1;
  display: flex;
  align-items: flex-start;
  gap: 8px;
  cursor: pointer;
  padding: 4px;
  border-radius: 6px;
  transition: background 0.15s;
}
.pipeline-stage:hover {
  background: var(--border-color);
}
.stage-indicator {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  min-width: 24px;
}
.stage-icon {
  width: 22px;
  height: 22px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  font-weight: 700;
  flex-shrink: 0;
}
.stage-icon.done {
  background: var(--el-color-success);
  color: #fff;
}
.stage-icon.active {
  background: var(--el-color-primary);
  color: #fff;
  animation: pulse 1.5s ease-in-out infinite;
}
.stage-icon.pending {
  background: var(--border-color);
  color: var(--text-faint);
  border: 1px solid var(--border-strong);
}
@keyframes pulse {
  0%, 100% { box-shadow: 0 0 0 0 rgba(21, 89, 140, 0.4); }
  50% { box-shadow: 0 0 0 6px rgba(21, 89, 140, 0); }
}
.stage-line {
  width: 2px;
  height: 16px;
  background: var(--border-strong);
  border-radius: 1px;
}
.stage-line.done {
  background: var(--el-color-success);
}
.stage-content {
  flex: 1;
  min-width: 0;
}
.stage-label {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-primary);
}
.stage-desc {
  font-size: 10px;
  color: var(--text-faint);
  margin-top: 1px;
}
.stage-progress-bar {
  height: 2px;
  background: var(--border-color);
  border-radius: 1px;
  margin-top: 4px;
  overflow: hidden;
}
.stage-progress-fill {
  height: 100%;
  background: var(--el-color-primary);
  border-radius: 1px;
  transition: width 0.5s ease;
}
.pipeline-stage.pending .stage-label {
  color: var(--text-faint);
}
.pipeline-stage.pending .stage-desc {
  color: var(--text-faint);
}
</style>
