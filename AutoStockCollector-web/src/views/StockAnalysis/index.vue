<template>
  <div class="sa-page">
    <div class="sa-toolbar">
      <el-input v-model="code" placeholder="输入股票代码，如 600519" style="width:240px" @keyup.enter="runAnalysis" />
      <el-button type="primary" :loading="loading" :disabled="!code" @click="runAnalysis">深度分析</el-button>
      <el-tag v-if="result" :type="result.source === 'llm' ? 'success' : 'info'" effect="plain">
        {{ result.source === 'llm' ? 'AI 研判' : '量化因子（AI不可用）' }}
      </el-tag>
    </div>

    <el-empty v-if="!result && !loading" description="输入代码开始分析" />

    <div v-if="result" class="sa-grid">
      <el-card shadow="never" class="sa-card">
        <template #header><span>{{ result.name }} ({{ result.code }}) 多维评分</span></template>
        <div class="sa-score-main">
          <div class="sa-score-num" :style="{ color: scoreColor(result.scores?.composite) }">
            {{ (result.scores?.composite ?? 0).toFixed(1) }}
          </div>
          <div class="sa-score-label">综合评分</div>
        </div>
        <div class="sa-dims">
          <div v-for="d in dims" :key="d.key" class="sa-dim">
            <span class="sa-dim-name">{{ d.label }}</span>
            <el-progress :percentage="result.scores?.[d.key] ?? 0" :color="scoreColor(result.scores?.[d.key] ?? 0)" :show-text="false" />
            <span class="sa-dim-val">{{ (result.scores?.[d.key] ?? 0).toFixed(0) }}</span>
          </div>
        </div>
        <div class="sa-price">当前价：{{ result.current_price ?? '--' }}</div>
      </el-card>

      <el-card shadow="never" class="sa-card">
        <template #header><span>AI 研判</span></template>
        <template v-if="result.llm">
          <p class="sa-summary">{{ result.llm.summary }}</p>
          <p v-if="result.llm.recommendation" class="sa-reco">建议：{{ result.llm.recommendation }}</p>
          <div v-if="result.llm.risk_factors?.length" class="sa-risks">
            <span class="sa-risks-title">风险因子</span>
            <el-tag v-for="(r, i) in result.llm.risk_factors" :key="i" type="warning" effect="plain" size="small">{{ r }}</el-tag>
          </div>
        </template>
        <el-empty v-else description="AI 暂不可用，以上为量化因子结果" :image-size="60" />
      </el-card>
    </div>

    <el-card v-if="result" shadow="never" class="sa-card sa-advice">
      <template #header>
        <div class="sa-advice-head">
          <span>买卖参考建议</span>
          <div class="sa-pos">
            <el-input v-model.number="cost" placeholder="成本价(可选)" size="small" style="width:130px" />
            <el-input v-model.number="position" placeholder="仓位0-1(可选)" size="small" style="width:130px" />
            <el-button size="small" :loading="adviceLoading" @click="runAdvice">获取建议</el-button>
          </div>
        </div>
      </template>
      <div v-if="advice" class="sa-advice-body">
        <el-tag :type="actionType(advice.advice.action)" size="large">{{ advice.advice.action }}</el-tag>
        <p class="sa-advice-reason">{{ advice.advice.reason }}</p>
        <div class="sa-advice-grid">
          <div><label>参考区间</label><span>{{ advice.advice.buy_zone || '--' }}</span></div>
          <div><label>止损</label><span>{{ advice.advice.stop_loss || '--' }}</span></div>
          <div><label>仓位建议</label><span>{{ advice.advice.position_advice || '--' }}</span></div>
        </div>
      </div>
      <el-empty v-else description="点击「获取建议」" :image-size="60" />
    </el-card>

    <p v-if="result" class="sa-disclaimer">{{ result.disclaimer }}</p>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { aiServiceApi, type AIAnalysisResult, type AIAdviceResult } from '@/api/ai'

const route = useRoute()
const code = ref('')
const loading = ref(false)
const adviceLoading = ref(false)
const result = ref<AIAnalysisResult | null>(null)
const advice = ref<AIAdviceResult | null>(null)
const cost = ref<number | undefined>()
const position = ref<number | undefined>()

const dims = [
  { key: 'technical' as const, label: '技术面' },
  { key: 'fundamental' as const, label: '基本面' },
  { key: 'fund_flow' as const, label: '资金面' },
  { key: 'valuation' as const, label: '估值面' },
]

function scoreColor(v: number): string {
  if (v >= 70) return '#3a8a52'
  if (v >= 50) return '#d0a020'
  return '#a04040'
}

function actionType(action: string): string {
  if (['买入参考', '关注', '持有'].some(a => action.includes(a))) return 'success'
  if (['减仓', '回避', '卖出'].some(a => action.includes(a))) return 'danger'
  return 'info'
}

async function runAnalysis() {
  if (!code.value) return
  loading.value = true
  advice.value = null
  try {
    const res = await aiServiceApi.analysis(code.value.trim())
    if (res.data?.success) {
      result.value = res.data.data
    } else {
      ElMessage.error(res.data?.error || '分析失败')
    }
  } catch {
    ElMessage.error('分析请求失败')
  } finally {
    loading.value = false
  }
}

async function runAdvice() {
  if (!result.value) return
  adviceLoading.value = true
  try {
    const payload: { cost?: number; position?: number } = {}
    if (cost.value !== undefined) payload.cost = cost.value
    if (position.value !== undefined) payload.position = position.value
    const res = await aiServiceApi.advice(result.value.code, payload)
    if (res.data?.success) {
      advice.value = res.data.data
    } else {
      ElMessage.error(res.data?.error || '建议获取失败')
    }
  } catch {
    ElMessage.error('建议请求失败')
  } finally {
    adviceLoading.value = false
  }
}

onMounted(() => {
  const q = route.query.code
  if (typeof q === 'string' && q) {
    code.value = q
    runAnalysis()
  }
})
</script>

<style scoped>
.sa-page { display: flex; flex-direction: column; gap: 14px; }
.sa-toolbar { display: flex; align-items: center; gap: 10px; }
.sa-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }
.sa-card { background: #0c0c14; border: 1px solid #18182a; }
.sa-card :deep(.el-card__header) { color: #c8cae8; font-size: 13.5px; font-weight: 600; }
.sa-score-main { text-align: center; padding: 8px 0 16px; }
.sa-score-num { font-size: 44px; font-weight: 800; line-height: 1; }
.sa-score-label { font-size: 12px; color: #606080; margin-top: 6px; }
.sa-dims { display: flex; flex-direction: column; gap: 10px; }
.sa-dim { display: grid; grid-template-columns: 56px 1fr 36px; align-items: center; gap: 8px; }
.sa-dim-name { font-size: 12px; color: #8888a8; }
.sa-dim-val { font-size: 12px; color: #c8cae8; text-align: right; }
.sa-price { margin-top: 14px; font-size: 12px; color: #606080; }
.sa-summary { color: #c0c2dd; line-height: 1.7; font-size: 13px; }
.sa-reco { color: #6bbf88; font-size: 13px; margin-top: 8px; }
.sa-risks { margin-top: 12px; display: flex; flex-wrap: wrap; gap: 6px; align-items: center; }
.sa-risks-title { font-size: 12px; color: #606080; margin-right: 4px; }
.sa-advice-head { display: flex; justify-content: space-between; align-items: center; }
.sa-pos { display: flex; gap: 8px; }
.sa-advice-body { display: flex; flex-direction: column; gap: 12px; }
.sa-advice-reason { color: #c0c2dd; line-height: 1.7; font-size: 13px; }
.sa-advice-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; }
.sa-advice-grid div { display: flex; flex-direction: column; gap: 4px; }
.sa-advice-grid label { font-size: 11px; color: #606080; }
.sa-advice-grid span { font-size: 13px; color: #c8cae8; }
.sa-disclaimer { font-size: 11px; color: #44445a; text-align: center; margin-top: 4px; }
</style>
