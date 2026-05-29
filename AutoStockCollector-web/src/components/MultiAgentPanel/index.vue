<template>
  <div class="multi-agent-panel">
    <el-card shadow="never" class="section-card">
      <template #header>
        <div class="header-toolbar">
          <span>多Agent智能协作分析</span>
          <el-tag v-if="agentStore.currentTask" type="info">
            分析中: {{ agentStore.currentTask.code }}
          </el-tag>
        </div>
      </template>
      
      <div class="task-config">
        <el-select v-model="stockCode" placeholder="选择股票" filterable style="width: 200px">
          <el-option
            v-for="s in watchlist"
            :key="s.code"
            :label="`${s.code} ${s.name}`"
            :value="s.code"
          />
        </el-select>
        <el-select v-model="analysisType" style="width: 140px">
          <el-option label="综合分析" value="comprehensive" />
          <el-option label="技术分析" value="technical" />
          <el-option label="基本面" value="fundamental" />
        </el-select>
        <el-button 
          type="primary" 
          @click="startAnalysis"
          :loading="isAnalyzing"
          :icon="MagicStick"
        >
          开始分析
        </el-button>
      </div>
    </el-card>
    
    <el-card shadow="never" class="section-card">
      <template #header>
        <div class="section-header">
          <span>Agent分析进度</span>
          <el-progress :percentage="agentStore.overallProgress" :stroke-width="8" style="width: 200px" />
        </div>
      </template>
      
      <div class="agents-grid">
        <div 
          v-for="agent in agentStore.agents" 
          :key="agent.id"
          :class="['agent-card', agent.status]"
        >
          <div class="agent-header">
            <div class="agent-icon">
              <el-icon v-if="agent.status === 'analyzing'" class="is-loading"><Loading /></el-icon>
              <el-icon v-else-if="agent.status === 'completed'"><CircleCheck /></el-icon>
              <el-icon v-else-if="agent.status === 'error'"><CircleClose /></el-icon>
              <el-icon v-else><User /></el-icon>
            </div>
            <div class="agent-info">
              <span class="agent-name">{{ agent.name }}</span>
              <el-tag size="small" :type="getStatusType(agent.status)">
                {{ getStatusLabel(agent.status) }}
              </el-tag>
            </div>
          </div>
          
          <div class="agent-progress" v-if="agent.status === 'analyzing'">
            <el-progress :percentage="Math.round(agent.progress)" :stroke-width="4" />
          </div>
          
          <div class="agent-result" v-if="agent.result">
            <div class="result-score">
              <span class="score-label">评分</span>
              <span class="score-value" :class="getScoreClass(agent.result.score)">
                {{ (agent.result.score || 0).toFixed(1) }}
              </span>
            </div>
            <div class="result-conclusion" v-if="agent.result.conclusion">
              {{ agent.result.conclusion }}
            </div>
            <div class="result-recommendation" v-if="agent.result.recommendation">
              <el-tag size="small" :type="getRecommendType(agent.result.recommendation)">
                {{ agent.result.recommendation }}
              </el-tag>
            </div>
          </div>
          
          <div class="agent-error" v-if="agent.error">
            <el-icon color="#f56c6c"><Warning /></el-icon>
            <span>{{ agent.error }}</span>
          </div>
        </div>
      </div>
    </el-card>
    
    <el-card v-if="agentStore.aggregatedResult" shadow="never" class="section-card aggregated-card">
      <template #header>
        <div class="section-header">
          <span>综合决策结果</span>
          <el-tag :type="getRecommendType(agentStore.aggregatedResult.recommendation)" size="large">
            {{ agentStore.aggregatedResult.recommendation }}
          </el-tag>
        </div>
      </template>
      
      <div class="aggregated-stats">
        <div class="stat-item main">
          <div class="stat-value">{{ agentStore.aggregatedResult.compositeScore }}</div>
          <div class="stat-label">综合评分</div>
        </div>
        <div class="stat-item">
          <div class="stat-value">{{ agentStore.aggregatedResult.avgScore }}</div>
          <div class="stat-label">平均评分</div>
        </div>
        <div class="stat-item">
          <div class="stat-value">{{ agentStore.completedAgents.length }}</div>
          <div class="stat-label">完成Agent</div>
        </div>
      </div>
      
      <el-divider>关键信号</el-divider>
      
      <div class="signals-list">
        <el-tag 
          v-for="(signal, idx) in agentStore.aggregatedResult.signals" 
          :key="idx"
          size="small"
          type="info"
          class="signal-tag"
        >
          {{ signal }}
        </el-tag>
      </div>
      
      <el-divider>各Agent结论</el-divider>
      
      <el-table :data="agentStore.aggregatedResult.agentResults" stripe size="small">
        <el-table-column prop="name" label="Agent" width="100" />
        <el-table-column prop="score" label="评分" width="80">
          <template #default="{ row }">
            <span :class="getScoreClass(row.score)">{{ row.score.toFixed(1) }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="conclusion" label="结论" />
        <el-table-column prop="recommendation" label="建议" width="100">
          <template #default="{ row }">
            <el-tag size="small" :type="getRecommendType(row.recommendation)">
              {{ row.recommendation }}
            </el-tag>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { MagicStick, Loading, CircleCheck, CircleClose, User, Warning } from '@element-plus/icons-vue'
import { useAgentStore } from '@/stores/agentStore'
import { watchlistApi } from '@/api/watchlist'

const agentStore = useAgentStore()

const stockCode = ref('')
const analysisType = ref('comprehensive')
const isAnalyzing = ref(false)
const watchlist = ref<{ code: string; name: string }[]>([])

const isAnalyzingComputed = ref(false)

function getStatusType(status: string): string {
  switch (status) {
    case 'completed': return 'success'
    case 'error': return 'danger'
    case 'analyzing': return 'warning'
    default: return 'info'
  }
}

function getStatusLabel(status: string): string {
  switch (status) {
    case 'completed': return '完成'
    case 'error': return '失败'
    case 'analyzing': return '分析中'
    default: return '等待'
  }
}

function getScoreClass(score?: number): string {
  const s = score || 0
  if (s >= 70) return 'score-high'
  if (s >= 60) return 'score-mid'
  return 'score-low'
}

function getRecommendType(rec?: string): string {
  if (!rec) return 'info'
  if (rec.includes('推荐') || rec.includes('买入')) return 'success'
  if (rec.includes('谨慎') || rec.includes('观望')) return 'warning'
  if (rec.includes('回避')) return 'danger'
  return 'info'
}

function startAnalysis() {
  if (!stockCode.value) return
  
  isAnalyzing.value = true
  agentStore.startTask(stockCode.value, analysisType.value)
  
  setTimeout(() => {
    isAnalyzing.value = false
  }, 3000)
}

async function loadWatchlist() {
  try {
    const res = await watchlistApi.getWatchlist()
    watchlist.value = res.data?.data || res.data || []
    if (watchlist.value.length > 0) {
      stockCode.value = watchlist.value[0].code
    }
  } catch {
    watchlist.value = []
  }
}

onMounted(() => {
  loadWatchlist()
})
</script>

<style scoped>
.multi-agent-panel {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.header-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.task-config {
  display: flex;
  gap: 12px;
  align-items: center;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.agents-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
}

.agent-card {
  background: #2c2c2c;
  border-radius: 8px;
  padding: 16px;
  transition: all 0.3s;
}

.agent-card.analyzing {
  border: 1px solid #e6a23c;
  box-shadow: 0 0 10px rgba(230, 162, 60, 0.2);
}

.agent-card.completed {
  border: 1px solid #67c23a;
}

.agent-card.error {
  border: 1px solid #f56c6c;
}

.agent-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
}

.agent-icon {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: #3c3c3c;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 18px;
  color: #909399;
}

.agent-card.completed .agent-icon {
  background: rgba(103, 194, 58, 0.2);
  color: #67c23a;
}

.agent-card.analyzing .agent-icon {
  background: rgba(230, 162, 60, 0.2);
  color: #e6a23c;
}

.agent-info {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.agent-name {
  font-size: 14px;
  font-weight: 600;
  color: #e5eaf3;
}

.agent-progress {
  margin-bottom: 12px;
}

.agent-result {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.result-score {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.score-label {
  font-size: 12px;
  color: #909399;
}

.score-value {
  font-size: 24px;
  font-weight: 600;
}

.score-high { color: #67c23a; }
.score-mid { color: #409eff; }
.score-low { color: #f56c6c; }

.result-conclusion {
  font-size: 12px;
  color: #909399;
  line-height: 1.5;
}

.agent-error {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: #f56c6c;
}

.aggregated-card {
  border: 1px solid #409eff;
}

.aggregated-stats {
  display: flex;
  gap: 24px;
  justify-content: center;
  margin-bottom: 16px;
}

.stat-item {
  text-align: center;
}

.stat-item.main {
  padding: 16px 24px;
  background: rgba(64, 158, 255, 0.1);
  border-radius: 8px;
}

.stat-value {
  font-size: 28px;
  font-weight: 600;
  color: #409eff;
}

.stat-label {
  font-size: 12px;
  color: #909399;
  margin-top: 4px;
}

.signals-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.signal-tag {
  background: #2c2c2c;
  border: none;
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
  display: flex;
  justify-content: space-between;
}
</style>