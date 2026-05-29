<template>
  <div class="smart-pick">
    <el-card shadow="never" class="section-card">
      <template #header>
        <div class="header-toolbar">
          <span>AI智能选股</span>
          <div class="strategy-select">
            <el-select v-model="selectedStrategy" size="small" style="width:180px">
              <el-option
                v-for="s in strategyList"
                :key="s.name"
                :label="s.name"
                :value="s.name"
              />
            </el-select>
          </div>
        </div>
      </template>
      <div class="pick-toolbar">
        <el-input-number v-model="topN" :min="5" :max="50" size="default" />
        <span class="toolbar-label">Top N</span>
        <el-input-number v-model="minScore" :min="0" :max="100" :step="5" size="default" />
        <span class="toolbar-label">最低评分</span>
        <el-button type="primary" @click="runPick" :loading="loading" :icon="Search">
          开始选股
        </el-button>
      </div>
    </el-card>

    <template v-if="results.length > 0">
      <el-card shadow="never" class="section-card">
        <template #header>
          <div class="result-summary">
            <span>选股结果 ({{ results.length }} 只)</span>
            <div class="summary-tags">
              <el-tag size="small" type="info">
                平均评分: {{ avgScore }}
              </el-tag>
              <el-tag size="small" :type="resultType">
                {{ resultTypeLabel }}
              </el-tag>
            </div>
          </div>
        </template>
        <el-table :data="results" stripe size="small">
          <el-table-column prop="code" label="代码" width="110" fixed>
            <template #default="{ row }">
              <router-link :to="`/stock-detail?code=${row.code}`" class="stock-link">
                {{ row.code }}
              </router-link>
            </template>
          </el-table-column>
          <el-table-column prop="name" label="名称" width="100" show-overflow-tooltip />
          <el-table-column prop="score" label="综合评分" width="100" sortable fixed>
            <template #default="{ row }">
              <el-tag :type="scoreTagType(row.score)" size="small" effect="dark">
                {{ row.score?.toFixed(1) }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="recommendation" label="建议" width="100">
            <template #default="{ row }">
              <el-tag :type="recommendTagType(row.recommendation)" size="small">
                {{ row.recommendation }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="risk_level" label="风险" width="80">
            <template #default="{ row }">
              <el-tag :type="riskTagType(row.risk_level)" size="small">
                {{ row.risk_level }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="技术面" width="90">
            <template #default="{ row }">
              <div class="score-bar">
                <span class="score-value">{{ (row.technical_score || 0).toFixed(0) }}</span>
                <el-progress :percentage="row.technical_score || 0" :stroke-width="6" :show-text="false" :color="scoreColor(row.technical_score)" />
              </div>
            </template>
          </el-table-column>
          <el-table-column label="基本面" width="90">
            <template #default="{ row }">
              <div class="score-bar">
                <span class="score-value">{{ (row.fundamental_score || 0).toFixed(0) }}</span>
                <el-progress :percentage="row.fundamental_score || 0" :stroke-width="6" :show-text="false" :color="scoreColor(row.fundamental_score)" />
              </div>
            </template>
          </el-table-column>
          <el-table-column label="舆情" width="90">
            <template #default="{ row }">
              <div class="score-bar">
                <span class="score-value">{{ (row.sentiment_score || 0).toFixed(0) }}</span>
                <el-progress :percentage="row.sentiment_score || 0" :stroke-width="6" :show-text="false" :color="scoreColor(row.sentiment_score)" />
              </div>
            </template>
          </el-table-column>
          <el-table-column label="资金流" width="90">
            <template #default="{ row }">
              <div class="score-bar">
                <span class="score-value">{{ (row.fund_flow_score || 0).toFixed(0) }}</span>
                <el-progress :percentage="row.fund_flow_score || 0" :stroke-width="6" :show-text="false" :color="scoreColor(row.fund_flow_score)" />
              </div>
            </template>
          </el-table-column>
          <el-table-column label="止损位" width="90">
            <template #default="{ row }">
              <span class="price-text stop-loss">{{ formatPrice(row.stop_loss) }}</span>
            </template>
          </el-table-column>
          <el-table-column label="目标价" width="90">
            <template #default="{ row }">
              <span class="price-text target-price">{{ formatPrice(row.target_price) }}</span>
            </template>
          </el-table-column>
        </el-table>
      </el-card>

      <el-card shadow="never" class="section-card score-distribution">
        <template #header><span>评分分布</span></template>
        <div class="distribution-chart">
          <div
            v-for="(item, idx) in distributionData"
            :key="idx"
            class="distribution-item"
          >
            <div class="dist-label">{{ item.label }}</div>
            <div class="dist-bar-container">
              <div class="dist-bar" :style="{ width: item.percentage + '%', backgroundColor: item.color }"></div>
            </div>
            <div class="dist-count">{{ item.count }}只</div>
          </div>
        </div>
      </el-card>
    </template>

    <el-empty v-else-if="!loading" description="点击开始选股获取推荐结果" />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { Search } from '@element-plus/icons-vue'
import { pickerApi } from '@/api/ai'
import { strategyApi } from '@/api/strategy'
import type { StrategyItem } from '@/types'

interface PickResult {
  code: string
  name?: string
  score: number
  technical_score: number
  fundamental_score: number
  sentiment_score: number
  fund_flow_score: number
  recommendation: string
  risk_level: string
  stop_loss: number
  target_price: number
}

const selectedStrategy = ref('')
const strategyList = ref<StrategyItem[]>([])
const topN = ref(20)
const minScore = ref(60)
const loading = ref(false)
const results = ref<PickResult[]>([])

const avgScore = computed(() => {
  if (results.value.length === 0) return '0'
  const sum = results.value.reduce((acc, r) => acc + r.score, 0)
  return (sum / results.value.length).toFixed(1)
})

const resultType = computed(() => {
  const avg = parseFloat(avgScore.value)
  if (avg >= 70) return 'success'
  if (avg >= 60) return 'warning'
  return 'danger'
})

const resultTypeLabel = computed(() => {
  const avg = parseFloat(avgScore.value)
  if (avg >= 70) return '优质标的'
  if (avg >= 60) return '良好标的'
  return '一般标的'
})

const distributionData = computed(() => {
  const dist = [
    { label: '强烈推荐(≥75)', min: 75, max: 100, color: '#67c23a' },
    { label: '买入(65-75)', min: 65, max: 74.99, color: '#409eff' },
    { label: '观望(55-65)', min: 55, max: 64.99, color: '#e6a23c' },
    { label: '回避(<55)', min: 0, max: 54.99, color: '#f56c6c' },
  ]
  return dist.map(d => {
    const count = results.value.filter(r => r.score >= d.min && r.score <= d.max).length
    const percentage = results.value.length > 0 ? (count / results.value.length) * 100 : 0
    return { ...d, count, percentage }
  })
})

function scoreTagType(score: number): '' | 'success' | 'warning' | 'danger' | 'info' {
  if (score >= 75) return 'success'
  if (score >= 60) return 'warning'
  if (score >= 50) return 'info'
  return 'danger'
}

function recommendTagType(rec: string): '' | 'success' | 'warning' | 'danger' {
  if (rec.includes('推荐') || rec.includes('买入')) return 'success'
  if (rec.includes('谨慎')) return 'warning'
  if (rec.includes('回避')) return 'danger'
  return 'info'
}

function riskTagType(risk: string): '' | 'success' | 'warning' | 'danger' {
  if (risk === '低') return 'success'
  if (risk === '中') return 'warning'
  return 'danger'
}

function scoreColor(score: number): string {
  if (score >= 75) return '#67c23a'
  if (score >= 60) return '#409eff'
  if (score >= 50) return '#e6a23c'
  return '#f56c6c'
}

function formatPrice(price: number): string {
  if (!price || price <= 0) return '--'
  return price.toFixed(2)
}

async function loadStrategies() {
  try {
    const res = await strategyApi.getStrategyList()
    const data = res.data?.strategies || res.data?.data || res.data || []
    strategyList.value = data
    if (data.length > 0) {
      selectedStrategy.value = data[0].name
    }
  } catch {
    strategyList.value = []
  }
}

async function runPick() {
  loading.value = true
  try {
    const res = await pickerApi.smartPickAdvanced({
      strategy: selectedStrategy.value,
      top_n: topN.value,
      min_score: minScore.value
    })
    results.value = res.data?.results || res.data?.data || []
  } catch {
    results.value = []
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  loadStrategies()
})
</script>

<style scoped>
.smart-pick {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.header-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.pick-toolbar {
  display: flex;
  gap: 12px;
  align-items: center;
  flex-wrap: wrap;
}

.toolbar-label {
  color: #909399;
  font-size: 13px;
}

.result-summary {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.summary-tags {
  display: flex;
  gap: 8px;
}

.stock-link {
  color: #409eff;
  text-decoration: none;
}

.stock-link:hover {
  text-decoration: underline;
}

.score-bar {
  display: flex;
  align-items: center;
  gap: 6px;
}

.score-value {
  font-size: 12px;
  color: #e5eaf3;
  width: 24px;
}

.price-text {
  font-size: 12px;
}

.stop-loss {
  color: #f56c6c;
}

.target-price {
  color: #67c23a;
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

.score-distribution {
  padding: 16px;
}

.distribution-chart {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.distribution-item {
  display: grid;
  grid-template-columns: 100px 1fr 60px;
  align-items: center;
  gap: 12px;
}

.dist-label {
  font-size: 12px;
  color: #909399;
}

.dist-bar-container {
  height: 8px;
  background: #2c2c2c;
  border-radius: 4px;
  overflow: hidden;
}

.dist-bar {
  height: 100%;
  border-radius: 4px;
  transition: width 0.3s ease;
}

.dist-count {
  font-size: 12px;
  color: #e5eaf3;
  text-align: right;
}
</style>
