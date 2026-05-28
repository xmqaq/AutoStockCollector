<template>
  <div class="ai-analysis">
    <!-- Input form -->
    <el-card shadow="never" class="section-card">
      <template #header><span>AI智能分析</span></template>
      <el-form :model="form" label-width="100px" style="max-width:500px">
        <el-form-item label="股票代码">
          <StockSearch v-model="form.code" @search="(c) => form.code = c" />
        </el-form-item>
        <el-form-item label="分析类型">
          <el-select v-model="form.type" style="width:100%">
            <el-option label="综合分析" value="comprehensive" />
            <el-option label="技术分析" value="technical" />
            <el-option label="基本面分析" value="fundamental" />
            <el-option label="情绪分析" value="sentiment" />
            <el-option label="风险评估" value="risk" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button
            type="primary"
            @click="handleAnalyze"
            :loading="loading"
            :disabled="!form.code"
          >
            开始分析
          </el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- Cache hint -->
    <el-alert
      v-if="cacheHit"
      title="当前结果来自本地缓存"
      type="info"
      show-icon
      closable
      style="margin-bottom:0"
    />

    <!-- Result -->
    <el-card v-if="result" shadow="never" class="section-card result-card">
      <template #header>
        <div class="result-header">
          <span>分析结果：{{ result.code }} - {{ analysisTypeLabel(result.type as string) }}</span>
          <el-tag v-if="result.score !== undefined" :type="scoreType(result.score as number)" size="large">
            评分：{{ result.score }}
          </el-tag>
        </div>
      </template>

      <el-descriptions :column="1" border size="small">
        <el-descriptions-item label="分析结论" v-if="result.conclusion">
          <div class="result-text">{{ result.conclusion }}</div>
        </el-descriptions-item>
        <el-descriptions-item label="分析逻辑" v-if="result.logic">
          <div class="result-text">{{ result.logic }}</div>
        </el-descriptions-item>
        <el-descriptions-item label="风险提示" v-if="result.risks">
          <div class="result-text risk-text">{{ result.risks }}</div>
        </el-descriptions-item>
        <el-descriptions-item label="分析时间" v-if="result.timestamp">
          {{ fmtDateTime(result.timestamp as string) }}
        </el-descriptions-item>
      </el-descriptions>

      <!-- Raw output if no structured fields -->
      <div
        v-if="!result.conclusion && !result.logic && rawResult"
        class="raw-result"
      >
        <pre>{{ JSON.stringify(rawResult, null, 2) }}</pre>
      </div>
    </el-card>

    <!-- History -->
    <el-card v-if="history.length > 0" shadow="never" class="section-card">
      <template #header><span>分析历史（本次会话）</span></template>
      <div class="history-list">
        <div
          v-for="(item, idx) in history"
          :key="idx"
          class="history-item"
          @click="selectHistory(item)"
        >
          <span class="history-code">{{ (item as { code: string }).code }}</span>
          <el-tag size="small" type="info">{{ analysisTypeLabel((item as { type: string }).type) }}</el-tag>
          <span v-if="(item as { score?: number }).score !== undefined" class="history-score">
            评分: {{ (item as { score: number }).score }}
          </span>
        </div>
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { aiApi } from '@/api/ai'
import { fmtDateTime } from '@/utils/format'
import { useAIStore } from '@/stores/collectStore'
import StockSearch from '@/components/StockSearch/index.vue'
import { ElMessage } from 'element-plus'

const aiStore = useAIStore()
const loading = ref(false)
const cacheHit = ref(false)
const result = ref<Record<string, unknown> | null>(null)
const rawResult = ref<unknown>(null)
const history = ref<unknown[]>([])

const form = ref({
  code: '',
  type: 'comprehensive',
})

const typeLabels: Record<string, string> = {
  comprehensive: '综合分析',
  technical: '技术分析',
  fundamental: '基本面分析',
  sentiment: '情绪分析',
  risk: '风险评估',
}

function analysisTypeLabel(type: string): string {
  return typeLabels[type] || type
}

function scoreType(score: number): 'success' | 'warning' | 'danger' | 'info' {
  if (score >= 70) return 'success'
  if (score >= 50) return 'warning'
  return 'danger'
}

const cacheKey = computed(() => `${form.value.code}_${form.value.type}`)

async function handleAnalyze() {
  if (!form.value.code) {
    ElMessage.warning('请输入股票代码')
    return
  }

  // Check cache
  const cached = aiStore.getCached(cacheKey.value)
  if (cached) {
    result.value = cached as Record<string, unknown>
    rawResult.value = cached
    cacheHit.value = true
    return
  }

  loading.value = true
  cacheHit.value = false
  try {
    const res = await aiApi.analyze({ code: form.value.code, type: form.value.type })
    const data = res.data?.result || res.data?.data || res.data
    result.value = data || {}
    rawResult.value = data
    // Cache it
    aiStore.setCache(cacheKey.value, data)
    // Add to history
    history.value.unshift(data)
    if (history.value.length > 10) history.value.pop()
  } catch {
    result.value = null
  } finally {
    loading.value = false
  }
}

function selectHistory(item: unknown) {
  result.value = item as Record<string, unknown>
  rawResult.value = item
  const data = item as { code?: string; type?: string }
  if (data.code) form.value.code = data.code
  if (data.type) form.value.type = data.type
  cacheHit.value = true
}
</script>

<style scoped>
.ai-analysis {
  display: flex;
  flex-direction: column;
  gap: 16px;
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

.result-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.result-card :deep(.el-descriptions__label) {
  color: #909399;
  width: 100px;
}

.result-card :deep(.el-descriptions__content) {
  color: #e5eaf3;
}

.result-text {
  line-height: 1.6;
  font-size: 13px;
  white-space: pre-wrap;
}

.risk-text {
  color: #f56c6c;
}

.raw-result {
  background: #141414;
  border-radius: 4px;
  padding: 12px;
  margin-top: 8px;
  max-height: 400px;
  overflow-y: auto;
}

.raw-result pre {
  font-size: 12px;
  color: #a8b5c1;
  margin: 0;
  white-space: pre-wrap;
  word-break: break-all;
}

.history-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.history-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 12px;
  background: #2c2c2c;
  border-radius: 4px;
  cursor: pointer;
  transition: background 0.2s;
}

.history-item:hover {
  background: #3c3c3c;
}

.history-code {
  font-weight: 600;
  color: #409eff;
  font-size: 13px;
}

.history-score {
  font-size: 12px;
  color: #909399;
}
</style>
