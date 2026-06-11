<template>
  <div class="batch-pick">
    <el-card shadow="never" class="section-card">
      <template #header>
        <div class="header-toolbar">
          <span>批量AI分析</span>
          <el-radio-group v-model="selectMode" size="small">
            <el-radio-button label="top">主力TOP</el-radio-button>
            <el-radio-button label="custom">自定义</el-radio-button>
            <el-radio-button label="watchlist">自选股</el-radio-button>
          </el-radio-group>
        </div>
      </template>
      
      <div class="select-config" v-if="selectMode === 'top'">
        <span class="config-label">选择数量：</span>
        <el-radio-group v-model="topCount" size="small">
          <el-radio-button :value="10">10只</el-radio-button>
          <el-radio-button :value="20">20只</el-radio-button>
          <el-radio-button :value="30">30只</el-radio-button>
          <el-radio-button :value="50">50只</el-radio-button>
        </el-radio-group>
        <span class="config-tip">（按主力资金净流入排序）</span>
      </div>
      
      <div class="select-config" v-if="selectMode === 'custom'">
        <el-input
          v-model="customCodes"
          type="textarea"
          :rows="3"
          placeholder="输入股票代码，多个用逗号分隔，如: SH600000, SZ000001, SH600519"
        />
      </div>
      
      <div class="select-config" v-if="selectMode === 'watchlist'">
        <el-checkbox-group v-model="selectedWatchlist">
          <el-checkbox 
            v-for="stock in watchlist" 
            :key="stock.code" 
            :value="stock.code"
            :label="stock.code"
          >
            {{ stock.code }} {{ stock.name }}
          </el-checkbox>
        </el-checkbox-group>
      </div>
      
      <div class="toolbar-actions">
        <div class="analysis-options">
          <el-select v-model="analysisType" size="small" style="width:140px">
            <el-option label="综合分析" value="comprehensive" />
            <el-option label="技术分析" value="technical" />
            <el-option label="基本面" value="fundamental" />
            <el-option label="舆情分析" value="sentiment" />
          </el-select>
          <el-checkbox v-model="parallelMode" size="small">并行模式（快速）</el-checkbox>
        </div>
        <el-button 
          type="primary" 
          @click="startBatchAnalysis"
          :loading="isAnalyzing"
          :disabled="!canStart"
          :icon="DataAnalysis"
        >
          开始分析 ({{ selectedCount }}只)
        </el-button>
      </div>
    </el-card>
    
    <AnalysisProgress
      v-if="isAnalyzing"
      :task-id="taskId"
      :task-name="`批量分析 ${selectedCount} 只股票`"
      @complete="handleComplete"
      @error="handleError"
    />
    
    <el-card v-if="results.length > 0 && !isAnalyzing" shadow="never" class="section-card">
      <template #header>
        <div class="result-header">
          <span>分析结果 ({{ results.length }} 只)</span>
          <div class="result-actions">
            <el-button size="small" @click="addAllToWatchlist" :icon="Star">加入自选</el-button>
            <el-button size="small" @click="exportResults" :icon="Download">导出</el-button>
          </div>
        </div>
      </template>
      
      <div class="result-filters">
        <el-radio-group v-model="resultFilter" size="small">
          <el-radio-button label="all">全部</el-radio-button>
          <el-radio-button label="good">优质(≥75)</el-radio-button>
          <el-radio-button label="fair">良好(60-75)</el-radio-button>
          <el-radio-button label="poor">一般(<60)</el-radio-button>
        </el-radio-group>
      </div>
      
      <el-table :data="filteredResults" stripe size="small" :loading="isAnalyzing">
        <el-table-column prop="code" label="代码" width="100" fixed>
          <template #default="{ row }">
            <router-link :to="`/stock-detail?code=${row.code}`" class="stock-link">
              {{ row.code }}
            </router-link>
          </template>
        </el-table-column>
        <el-table-column prop="name" label="名称" width="100" show-overflow-tooltip />
        <el-table-column prop="score" label="评分" width="80" sortable>
          <template #default="{ row }">
            <el-tag :type="getScoreType(row.score)" size="small" effect="dark">
              {{ (row.score || 0).toFixed(1) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="recommendation" label="建议" width="90">
          <template #default="{ row }">
            <el-tag :type="getRecommendType(row.recommendation)" size="small">
              {{ row.recommendation || '--' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="技术面" width="80">
          <template #default="{ row }">
            {{ (row.technical?.trend_strength || 0).toFixed(0) }}
          </template>
        </el-table-column>
        <el-table-column label="基本面" width="80">
          <template #default="{ row }">
            {{ (((row.fundamental?.valuation_score || 0) + (row.fundamental?.growth_score || 0)) / 2 || 0).toFixed(0) }}
          </template>
        </el-table-column>
        <el-table-column label="舆情" width="80">
          <template #default="{ row }">
            {{ (row.sentiment?.score || 0).toFixed(0) }}
          </template>
        </el-table-column>
        <el-table-column label="止损位" width="80">
          <template #default="{ row }">
            <span class="price-text stop-loss">{{ formatPrice(row.stop_loss) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="120" fixed="right">
          <template #default="{ row }">
            <el-button size="small" text @click="addToWatchlist(row.code)">
              <el-icon><Star /></el-icon>
            </el-button>
          </template>
        </el-table-column>
      </el-table>
      
      <div class="summary-cards">
        <div class="summary-card good">
          <div class="card-value">{{ goodCount }}</div>
          <div class="card-label">优质标的</div>
        </div>
        <div class="summary-card fair">
          <div class="card-value">{{ fairCount }}</div>
          <div class="card-label">良好标的</div>
        </div>
        <div class="summary-card poor">
          <div class="card-value">{{ poorCount }}</div>
          <div class="card-label">一般标的</div>
        </div>
        <div class="summary-card avg">
          <div class="card-value">{{ avgScore }}</div>
          <div class="card-label">平均评分</div>
        </div>
      </div>
    </el-card>
    
    <el-card v-if="historyRecords.length > 0" shadow="never" class="section-card">
      <template #header>
        <div class="header-toolbar">
          <span>历史记录</span>
          <el-button size="small" text @click="clearHistory">清空</el-button>
        </div>
      </template>
      <div class="history-list">
        <div 
          v-for="(record, idx) in historyRecords" 
          :key="idx" 
          class="history-item"
          @click="loadHistory(record)"
        >
          <div class="history-info">
            <span class="history-time">{{ record.time }}</span>
            <span class="history-count">{{ record.count }}只</span>
          </div>
          <div class="history-result">
            <el-tag size="small" :type="record.type">{{ record.label }}</el-tag>
          </div>
        </div>
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { DataAnalysis, Star, Download } from '@element-plus/icons-vue'
import { aiApi } from '@/api/ai'
import { watchlistApi } from '@/api/watchlist'
import AnalysisProgress from '@/components/AnalysisProgress/index.vue'
import { ElMessage } from 'element-plus'

interface BatchResult {
  code: string
  name?: string
  score?: number
  recommendation?: string
  technical?: { trend_strength?: number }
  fundamental?: { valuation_score?: number; growth_score?: number }
  sentiment?: { score?: number }
  stop_loss?: number
  target_price?: number
}

interface HistoryRecord {
  time: string
  count: number
  results: BatchResult[]
  type: string
  label: string
}

const selectMode = ref<'top' | 'custom' | 'watchlist'>('top')
const topCount = ref(20)
const customCodes = ref('')
const selectedWatchlist = ref<string[]>([])
const analysisType = ref('comprehensive')
const parallelMode = ref(false)
const isAnalyzing = ref(false)
const taskId = ref('')
const results = ref<BatchResult[]>([])
const resultFilter = ref('all')
const watchlist = ref<{ code: string; name: string }[]>([])
const historyRecords = ref<HistoryRecord[]>([])

const selectedCount = computed(() => {
  switch (selectMode.value) {
    case 'top': return topCount.value
    case 'custom': 
      return customCodes.value.split(',').filter(c => c.trim()).length
    case 'watchlist': return selectedWatchlist.value.length
    default: return 0
  }
})

const canStart = computed(() => selectedCount.value > 0 && !isAnalyzing.value)

const filteredResults = computed(() => {
  if (resultFilter.value === 'all') return results.value
  if (resultFilter.value === 'good') return results.value.filter(r => (r.score || 0) >= 75)
  if (resultFilter.value === 'fair') return results.value.filter(r => (r.score || 0) >= 60 && (r.score || 0) < 75)
  if (resultFilter.value === 'poor') return results.value.filter(r => (r.score || 0) < 60)
  return results.value
})

const goodCount = computed(() => results.value.filter(r => (r.score || 0) >= 75).length)
const fairCount = computed(() => results.value.filter(r => (r.score || 0) >= 60 && (r.score || 0) < 75).length)
const poorCount = computed(() => results.value.filter(r => (r.score || 0) < 60).length)
const avgScore = computed(() => {
  if (results.value.length === 0) return '0'
  const sum = results.value.reduce((acc, r) => acc + (r.score || 0), 0)
  return (sum / results.value.length).toFixed(1)
})

function getScoreType(score?: number): string {
  const s = score || 0
  if (s >= 75) return 'success'
  if (s >= 60) return 'warning'
  return 'danger'
}

function getRecommendType(rec?: string): string {
  if (!rec) return 'info'
  if (rec.includes('推荐') || rec.includes('买入')) return 'success'
  if (rec.includes('谨慎')) return 'warning'
  if (rec.includes('回避')) return 'danger'
  return 'info'
}

function formatPrice(price?: number): string {
  if (!price || price <= 0) return '--'
  return price.toFixed(2)
}

async function loadWatchlist() {
  try {
    const res = await watchlistApi.getWatchlist()
    watchlist.value = res.data?.data || res.data || []
  } catch {
    watchlist.value = []
  }
}

function getSelectedCodes(): string[] {
  switch (selectMode.value) {
    case 'top':
      return Array.from({ length: topCount.value }, (_, i) => `TOP${i + 1}`)
    case 'custom':
      return customCodes.value.split(',').map(c => c.trim()).filter(c => c)
    case 'watchlist':
      return selectedWatchlist.value
    default: return []
  }
}

async function startBatchAnalysis() {
  const codes = getSelectedCodes()
  if (codes.length === 0) {
    ElMessage.warning('请选择要分析的股票')
    return
  }
  
  isAnalyzing.value = true
  taskId.value = `batch_${Date.now()}`
  results.value = []
  
  try {
    const res = await aiApi.batchAnalyze({ codes, type: analysisType.value })
    const data = res.data?.results || res.data?.data || []
    results.value = data
    
    const avg = data.reduce((acc: number, r: BatchResult) => acc + (r.score || 0), 0) / data.length
    historyRecords.value.unshift({
      time: new Date().toLocaleString(),
      count: data.length,
      results: data,
      type: avg >= 70 ? 'success' : avg >= 60 ? 'warning' : 'danger',
      label: avg >= 70 ? '优质' : avg >= 60 ? '良好' : '一般',
    })
    
    if (historyRecords.value.length > 10) {
      historyRecords.value.pop()
    }
  } catch {
    ElMessage.error('批量分析失败')
    results.value = []
  } finally {
    isAnalyzing.value = false
  }
}

function handleComplete(batchResults: BatchResult[]) {
  results.value = batchResults
  isAnalyzing.value = false
}

function handleError(msg: string) {
  ElMessage.error(msg)
  isAnalyzing.value = false
}

async function addToWatchlist(code: string) {
  try {
    await watchlistApi.addWatchlist({ code })
    ElMessage.success('已加入自选')
  } catch {
    ElMessage.error('加入自选失败')
  }
}

async function addAllToWatchlist() {
  for (const r of results.value.slice(0, 10)) {
    try {
      await watchlistApi.addWatchlist({ code: r.code })
    } catch {
    }
  }
  ElMessage.success('已添加前10只到自选')
}

function exportResults() {
  const csv = [
    '代码,名称,评分,建议,技术面,基本面,舆情,止损位,目标价',
    ...results.value.map(r => 
      `${r.code},${r.name || ''},${r.score || 0},${r.recommendation || ''},` +
      `${r.technical?.trend_strength || 0},${(((r.fundamental?.valuation_score || 0) + (r.fundamental?.growth_score || 0)) / 2 || 0).toFixed(0)},` +
      `${r.sentiment?.score || 0},${r.stop_loss || ''},${r.target_price || ''}`
    )
  ].join('\n')
  
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' })
  const link = document.createElement('a')
  link.href = URL.createObjectURL(blob)
  link.download = `batch_analysis_${Date.now()}.csv`
  link.click()
}

function loadHistory(record: HistoryRecord) {
  results.value = record.results
}

function clearHistory() {
  historyRecords.value = []
}

onMounted(() => {
  loadWatchlist()
})
</script>

<style scoped>
.batch-pick {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.header-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.select-config {
  margin-bottom: 16px;
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.config-label {
  font-size: 13px;
  color: var(--text-muted);
}

.config-tip {
  font-size: 12px;
  color: var(--text-faint);
}

.toolbar-actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.analysis-options {
  display: flex;
  gap: 16px;
  align-items: center;
}

.result-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.result-actions {
  display: flex;
  gap: 8px;
}

.result-filters {
  margin-bottom: 12px;
}

.stock-link {
  color: #409eff;
  text-decoration: none;
}

.stock-link:hover {
  text-decoration: underline;
}

.price-text {
  font-size: 12px;
}

.stop-loss {
  color: #f56c6c;
}

.summary-cards {
  display: flex;
  gap: 16px;
  margin-top: 16px;
}

.summary-card {
  flex: 1;
  padding: 16px;
  border-radius: 8px;
  text-align: center;
}

.summary-card.good {
  background: rgba(103, 194, 58, 0.1);
  border: 1px solid rgba(103, 194, 58, 0.3);
}

.summary-card.fair {
  background: rgba(64, 158, 255, 0.1);
  border: 1px solid rgba(64, 158, 255, 0.3);
}

.summary-card.poor {
  background: rgba(245, 108, 108, 0.1);
  border: 1px solid rgba(245, 108, 108, 0.3);
}

.summary-card.avg {
  background: rgba(230, 162, 60, 0.1);
  border: 1px solid rgba(230, 162, 60, 0.3);
}

.card-value {
  font-size: 24px;
  font-weight: 600;
  color: var(--text-primary);
}

.summary-card.good .card-value { color: #67c23a; }
.summary-card.fair .card-value { color: #409eff; }
.summary-card.poor .card-value { color: #f56c6c; }
.summary-card.avg .card-value { color: #e6a23c; }

.card-label {
  font-size: 12px;
  color: var(--text-muted);
  margin-top: 4px;
}

.history-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.history-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 12px;
  background: var(--border-color);
  border-radius: 4px;
  cursor: pointer;
  transition: background 0.2s;
}

.history-item:hover {
  background: var(--border-strong);
}

.history-info {
  display: flex;
  gap: 12px;
}

.history-time {
  font-size: 12px;
  color: var(--text-muted);
}

.history-count {
  font-size: 12px;
  color: #409eff;
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
}
</style>