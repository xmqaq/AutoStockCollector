<template>
  <div v-if="aiSummary" class="ap-ai-summary">
    <div class="ap-summary-toggle" @click="localExpanded = !localExpanded">
      <span class="section-title">AI 综合投资建议</span>
      <svg class="ap-summary-svg" :class="{ 'is-expanded': localExpanded }" viewBox="0 0 12 12" width="12" height="12">
        <path d="M2 4l4 4 4-4" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
      </svg>
    </div>
    <div v-if="localExpanded" class="ap-summary-body md-content" v-html="renderMd(aiSummary)"></div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { renderMd } from '@/utils/markdown'

const props = defineProps<{
  aiSummary: string | undefined
  expanded: boolean
}>()

const emit = defineEmits<{
  (e: 'update:expanded', val: boolean): void
}>()

const localExpanded = computed({
  get: () => props.expanded,
  set: (val) => emit('update:expanded', val)
})
</script>

<style scoped>
.ap-ai-summary {
  background: var(--bg-deep-soft, #f5f7fa);
  border: 1px solid var(--border-alt, #ebeef5);
  border-left: 3px solid #5a7af0;
  border-radius: 6px;
  overflow: hidden;
}
.ap-summary-toggle {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 14px;
  cursor: pointer;
  font-size: 13px;
  font-weight: 600;
  color: var(--text-alt-body, #303133);
  user-select: none;
}
.ap-summary-toggle:hover { background: var(--bg-hover-subtle, #f5f7fa); }
.ap-summary-svg {
  color: var(--text-alt-muted, #909399);
  transition: transform 0.2s;
  vertical-align: middle;
}
.ap-summary-svg.is-expanded { transform: rotate(180deg); }
.ap-summary-body {
  padding: 0 14px 12px;
  font-size: 13px;
  color: var(--text-alt-body, #303133);
  line-height: 1.7;
}

.md-content :deep(h1),
.md-content :deep(h2),
.md-content :deep(h3) {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-alt-primary, #303133);
  margin: 10px 0 4px 0;
}
.md-content :deep(strong) {
  color: var(--text-alt-primary, #303133);
  font-weight: 600;
}
.md-content :deep(p) {
  margin: 4px 0;
  color: var(--text-alt-body, #606266);
}
.md-content :deep(ul),
.md-content :deep(ol) {
  padding-left: 16px;
  margin: 3px 0;
}
.md-content :deep(li) {
  margin: 2px 0;
  color: var(--text-alt-body, #606266);
}
</style>
