<template>
  <div class="ap-toolbar">
    <div class="ap-title-group">
      <span class="ap-title">量化选股</span>
      <span class="ap-subtitle">多因子模型 · AI解读</span>
    </div>
    <div class="ap-controls">
      <el-input v-model.number="localTopN" size="small" style="width:110px"><template #prepend>选 N</template></el-input>
      <el-input v-model.number="localCandidatePool" size="small" style="width:140px"><template #prepend>候选池</template></el-input>
      <el-button type="primary" size="small" :loading="running" :disabled="running" @click="$emit('runPick')">
        {{ running ? '运行中...' : '立即重跑' }}
      </el-button>
      <el-button size="small" :loading="loading" @click="$emit('loadResults')">刷新结果</el-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  topN: number
  candidatePool: number
  running: boolean
  loading: boolean
}>()

const emit = defineEmits<{
  (e: 'update:topN', val: number): void
  (e: 'update:candidatePool', val: number): void
  (e: 'runPick'): void
  (e: 'loadResults'): void
}>()

const localTopN = computed({
  get: () => props.topN,
  set: (val) => emit('update:topN', val)
})

const localCandidatePool = computed({
  get: () => props.candidatePool,
  set: (val) => emit('update:candidatePool', val)
})
</script>

<style scoped>
.ap-toolbar { display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px; }
.ap-title-group { display: flex; align-items: baseline; gap: 10px; }
.ap-title { font-size: 15px; font-weight: 700; color: var(--text-alt-primary, #303133); }
.ap-subtitle { font-size: 12px; color: var(--text-alt-muted, #909399); }
.ap-controls { display: flex; gap: 8px; align-items: center; }
</style>
