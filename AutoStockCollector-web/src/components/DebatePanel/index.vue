<template>
  <div class="debate-panel">
    <el-card shadow="never" class="section-card">
      <template #header>
        <div class="header-toolbar">
          <span>多空辩论 &#x26; 风险管控</span>
          <el-tag v-if="debateStore.stockCode" type="info">
            分析中: {{ debateStore.stockCode }}
          </el-tag>
        </div>
      </template>

      <div class="task-config">
        <el-input v-model="stockCode" placeholder="输入股票代码（如 000001）" style="width: 180px" clearable />
        <el-select v-model="stockCode" placeholder="或从自选选择" filterable clearable style="width: 180px">
          <el-option
            v-for="s in watchlist"
            :key="s.code"
            :label="`${s.code} ${s.name}`"
            :value="s.code"
          />
        </el-select>
        <el-button
          type="primary"
          @click="startDebate"
          :loading="debateStore.isAnalyzing"
          :icon="MagicStick"
        >
          开始辩论
        </el-button>
        <el-button v-if="debateStore.isAnalyzing" type="danger" size="small" @click="abortDebate">
          停止
        </el-button>
      </div>
    </el-card>

    <el-card v-if="debateStore.isDataPhase || debateStore.dataSources.length > 0" shadow="never" class="section-card data-card">
      <template #header>
        <div class="section-header">
          <span>数据采集（6个数据源）</span>
          <el-tag v-if="debateStore.isDataPhase" type="warning" size="small">采集中</el-tag>
          <el-tag v-else type="success" size="small">完成</el-tag>
        </div>
      </template>
      <div class="data-grid">
        <div v-for="ds in debateStore.dataSources" :key="ds.name" :class="['data-item', ds.status]">
          <el-icon v-if="ds.status === 'done'" class="data-icon done"><CircleCheck /></el-icon>
          <el-icon v-else-if="ds.status === 'waiting'" class="data-icon waiting"><MoreFilled /></el-icon>
          <el-icon v-else class="data-icon loading is-loading"><Loading /></el-icon>
          <span class="data-label">{{ ds.label }}</span>
        </div>
      </div>
    </el-card>

    <el-card v-if="debateStore.isFactorPhase || debateStore.factorItems.length > 0" shadow="never" class="section-card factor-card">
      <template #header>
        <div class="section-header">
          <span>量化因子计算（4维度）</span>
          <el-tag v-if="debateStore.isFactorPhase" type="warning" size="small">计算中</el-tag>
          <el-tag v-else type="success" size="small">完成</el-tag>
        </div>
      </template>
      <div class="factor-grid">
        <div v-for="fi in debateStore.factorItems" :key="fi.name" :class="['factor-item', fi.status]">
          <div class="factor-header">
            <span class="factor-label">{{ fi.label }}</span>
            <span v-if="fi.status === 'done'" class="factor-score">{{ fi.score }}</span>
            <el-icon v-else-if="fi.status === 'running'" class="is-loading" style="color:#e6a23c"><Loading /></el-icon>
            <el-icon v-else style="color:#4a4a4a"><MoreFilled /></el-icon>
          </div>
          <el-progress
            v-if="fi.status === 'done'"
            :percentage="fi.score"
            :stroke-width="4"
            :format="() => ''"
          />
        </div>
      </div>
      <div v-if="debateStore.factorResults" class="factor-composite">
        综合评分：<strong>{{ debateStore.factorResults.composite }}</strong>/100
        <el-tag size="small" :type="(debateStore.factorResults.composite || 0) >= 60 ? 'success' : 'danger'">
          {{ (debateStore.factorResults.composite || 0) >= 60 ? '偏多' : '偏空' }}
        </el-tag>
      </div>
    </el-card>

    <el-card v-if="debateStore.isBasePhase || debateStore.baseAgents.length > 0" shadow="never" class="section-card base-agents-card">
      <template #header>
        <div class="section-header">
          <span>基础分析结果（6位分析师）</span>
          <el-tag type="info" size="small">{{ debateStore.baseCompletedCount }}/{{ debateStore.baseTotal || 6 }}</el-tag>
        </div>
      </template>
      <div class="base-agents-grid">
        <div
          v-for="agent in debateStore.baseAgents"
          :key="agent.agent_id"
          :class="['base-agent-card', agent.status]"
        >
          <div class="base-agent-header">
            <div class="agent-icon-sm">
              <el-icon v-if="agent.status === 'running'" class="is-loading"><Loading /></el-icon>
              <el-icon v-else-if="agent.status === 'completed'"><CircleCheck /></el-icon>
              <el-icon v-else><User /></el-icon>
            </div>
            <div class="agent-info">
              <span class="agent-name-sm">{{ agent.name }}</span>
              <el-tag size="small" :type="agent.status === 'completed' ? 'success' : agent.status === 'running' ? 'warning' : 'info'">
                {{ agent.status === 'completed' ? '完成' : agent.status === 'running' ? '分析中' : '等待' }}
              </el-tag>
            </div>
          </div>
          <div v-if="agent.status !== 'idle'" class="agent-live-text">{{ agent.content }}<span v-if="agent.status === 'running'" class="cursor-blink">▌</span></div>
        </div>
      </div>
    </el-card>

    <el-card shadow="never" class="section-card">
      <template #header>
        <div class="section-header">
          <span>辩论实时进度</span>
          <el-progress :percentage="debateStore.overallProgress" :stroke-width="8" style="width: 200px" />
        </div>
      </template>

      <div class="debate-arena">
        <div class="debater bull" :class="debateStore.bull.status">
          <div class="debater-header">
            <div class="debater-icon">🐂</div>
            <div class="debater-info">
              <span class="debater-name">多头分析师</span>
              <span class="debater-role">看多方</span>
            </div>
            <el-tag size="small" :type="getStatusType(debateStore.bull.status)">
              {{ getStatusLabel(debateStore.bull.status) }}
            </el-tag>
          </div>
          <el-progress
            v-if="debateStore.bull.status === 'running'"
            :percentage="debateStore.bull.progress"
            :stroke-width="6"
            status="success"
            :text-inside="true"
          />
          <div v-if="debateStore.bull.status !== 'idle'" class="live-content">
            <div class="content-header">
              <span class="live-badge" v-if="debateStore.bull.status === 'running'">LIVE</span>
              <span v-if="debateStore.bull.score !== undefined" class="score-tag bull-score">
                信心指数: {{ debateStore.bull.score }}
              </span>
            </div>
            <div ref="bullContentRef" class="content-text">{{ debateStore.bull.content }}</div>
          </div>
          <div v-if="debateStore.bull.error" class="debater-error">
            <el-icon color="#f56c6c"><Warning /></el-icon>
            <span>{{ debateStore.bull.error }}</span>
          </div>
        </div>

        <div class="vs-divider">
          <span class="vs-text">⚡ VS ⚡</span>
        </div>

        <div class="debater bear" :class="debateStore.bear.status">
          <div class="debater-header">
            <div class="debater-icon">🐻</div>
            <div class="debater-info">
              <span class="debater-name">空头分析师</span>
              <span class="debater-role">看空方</span>
            </div>
            <el-tag size="small" :type="getStatusType(debateStore.bear.status)">
              {{ getStatusLabel(debateStore.bear.status) }}
            </el-tag>
          </div>
          <el-progress
            v-if="debateStore.bear.status === 'running'"
            :percentage="debateStore.bear.progress"
            :stroke-width="6"
            status="exception"
            :text-inside="true"
          />
          <div v-if="debateStore.bear.status !== 'idle'" class="live-content">
            <div class="content-header">
              <span class="live-badge" v-if="debateStore.bear.status === 'running'">LIVE</span>
              <span v-if="debateStore.bear.score !== undefined" class="score-tag bear-score">
                信心指数: {{ debateStore.bear.score }}
              </span>
            </div>
            <div ref="bearContentRef" class="content-text">{{ debateStore.bear.content }}</div>
          </div>
          <div v-if="debateStore.bear.error" class="debater-error">
            <el-icon color="#f56c6c"><Warning /></el-icon>
            <span>{{ debateStore.bear.error }}</span>
          </div>
        </div>
      </div>
    </el-card>

    <el-card shadow="never" class="section-card judge-card">
      <template #header>
        <div class="section-header">
          <span>⚖️ 裁判裁决 &#x26; 风险管控</span>
          <el-tag v-if="debateStore.verdict" :type="getVerdictType(debateStore.verdict.recommendation)" size="large">
            {{ debateStore.verdict.recommendation }}
          </el-tag>
        </div>
      </template>

      <div v-if="debateStore.judge.status === 'running'" class="judge-streaming">
        <el-progress :percentage="debateStore.judge.progress" :stroke-width="6" status="warning" />
        <p class="judge-hint">裁判正在审阅多空双方论点...</p>
        <div class="content-text judge-text">{{ debateStore.judge.content }}</div>
      </div>

      <div v-if="debateStore.verdict" class="verdict-panel">
        <div class="verdict-stats">
          <div class="stat-item bull-stat">
            <div class="stat-icon">🐂</div>
            <div class="stat-value" style="color: #67c23a">{{ debateStore.verdict.bullScore }}</div>
            <div class="stat-label">多方评分</div>
          </div>
          <div class="stat-item vs-stat">
            <div class="stat-value" style="color: #e6a23c; font-size: 20px;">VS</div>
          </div>
          <div class="stat-item bear-stat">
            <div class="stat-icon">🐻</div>
            <div class="stat-value" style="color: #f56c6c">{{ debateStore.verdict.bearScore }}</div>
            <div class="stat-label">空方评分</div>
          </div>
          <el-divider direction="vertical" />
          <div class="stat-item">
            <div class="stat-value" style="color: #409eff">{{ debateStore.verdict.tendency }}</div>
            <div class="stat-label">倾向判断</div>
          </div>
          <div class="stat-item">
            <div class="stat-value">{{ renderRiskLevel(debateStore.verdict.riskLevel) }}</div>
            <div class="stat-label">风险等级</div>
          </div>
        </div>

        <el-divider>裁判裁决</el-divider>
        <div class="content-text judge-text full">{{ debateStore.verdict.judgeVerdict }}</div>
      </div>
    </el-card>

    <el-card v-if="debateStore.error" shadow="never" class="section-card error-card">
      <template #header>
        <span>错误信息</span>
      </template>
      <p>{{ debateStore.error }}</p>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, nextTick, onMounted } from 'vue'
import { MagicStick, Warning, Loading, CircleCheck, User, MoreFilled } from '@element-plus/icons-vue'
import { useDebateStore } from '@/stores/debateStore'
import { watchlistApi } from '@/api/watchlist'

const debateStore = useDebateStore()

const stockCode = ref('')
const watchlist = ref<{ code: string; name: string }[]>([])
const bullContentRef = ref<HTMLElement | null>(null)
const bearContentRef = ref<HTMLElement | null>(null)
let abortController: AbortController | null = null

function getStatusType(status: string) {
  switch (status) {
    case 'completed': return 'success'
    case 'error': return 'danger'
    case 'running': return 'warning'
    default: return 'info'
  }
}

function getStatusLabel(status: string) {
  switch (status) {
    case 'completed': return '已完成'
    case 'error': return '失败'
    case 'running': return '辩论中'
    default: return '等待'
  }
}

function getVerdictType(rec?: string) {
  if (!rec) return 'info'
  if (rec.includes('买入')) return 'success'
  if (rec.includes('观望')) return 'warning'
  if (rec.includes('回避')) return 'danger'
  return 'info'
}

function renderRiskLevel(level?: string) {
  if (!level) return '⚪'
  const map: Record<string, string> = {
    '低': '🟢',
    '中低': '🟢🟡',
    '中': '🟡',
    '中高': '🟠',
    '高': '🔴',
  }
  return map[level] || '⚪'
}

async function startDebate() {
  if (!stockCode.value) return
  abortController = new AbortController()
  debateStore.startDebate(stockCode.value)
}

function abortDebate() {
  if (abortController) {
    abortController.abort()
    abortController = null
  }
  debateStore.reset()
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

watch(() => debateStore.bull.content, () => {
  nextTick(() => {
    if (bullContentRef.value) {
      bullContentRef.value.scrollTop = bullContentRef.value.scrollHeight
    }
  })
})

watch(() => debateStore.bear.content, () => {
  nextTick(() => {
    if (bearContentRef.value) {
      bearContentRef.value.scrollTop = bearContentRef.value.scrollHeight
    }
  })
})

onMounted(() => {
  loadWatchlist()
})
</script>

<style scoped>
.debate-panel {
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

.debate-arena {
  display: grid;
  grid-template-columns: 1fr auto 1fr;
  gap: 16px;
  align-items: stretch;
}

.debater {
  background: #2c2c2c;
  border-radius: 8px;
  padding: 16px;
  transition: all 0.3s;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.debater.bull.running {
  border: 1px solid #67c23a;
  box-shadow: 0 0 12px rgba(103, 194, 58, 0.25);
}

.debater.bull.completed {
  border: 1px solid #67c23a;
}

.debater.bear.running {
  border: 1px solid #f56c6c;
  box-shadow: 0 0 12px rgba(245, 108, 108, 0.25);
}

.debater.bear.completed {
  border: 1px solid #f56c6c;
}

.debater-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 4px;
}

.debater-icon {
  font-size: 28px;
  width: 44px;
  height: 44px;
  border-radius: 50%;
  background: #3c3c3c;
  display: flex;
  align-items: center;
  justify-content: center;
}

.debater.bull.completed .debater-icon {
  background: rgba(103, 194, 58, 0.2);
}

.debater.bear.completed .debater-icon {
  background: rgba(245, 108, 108, 0.2);
}

.debater-info {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.debater-name {
  font-size: 14px;
  font-weight: 600;
  color: #e5eaf3;
}

.debater-role {
  font-size: 11px;
  color: #909399;
}

.vs-divider {
  display: flex;
  align-items: center;
  justify-content: center;
}

.vs-text {
  font-size: 16px;
  font-weight: 700;
  color: #e6a23c;
  padding: 8px;
  background: #2c2c2c;
  border-radius: 50%;
  width: 48px;
  height: 48px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.live-content {
  margin-top: 8px;
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.content-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}

.live-badge {
  font-size: 10px;
  font-weight: 700;
  color: #fff;
  background: #f56c6c;
  padding: 1px 6px;
  border-radius: 3px;
  animation: pulse 1.2s ease-in-out infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.3; }
}

.score-tag {
  font-size: 12px;
  font-weight: 600;
  padding: 2px 8px;
  border-radius: 4px;
}

.bull-score {
  color: #67c23a;
  background: rgba(103, 194, 58, 0.15);
}

.bear-score {
  color: #f56c6c;
  background: rgba(245, 108, 108, 0.15);
}

.content-text {
  font-size: 12px;
  color: #c0c4cc;
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-word;
  max-height: 260px;
  overflow-y: auto;
  background: #1a1a1a;
  border-radius: 6px;
  padding: 10px;
  flex: 1;
}

.content-text::-webkit-scrollbar {
  width: 4px;
}

.content-text::-webkit-scrollbar-thumb {
  background: #3c3c3c;
  border-radius: 2px;
}

.debater-error {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: #f56c6c;
  margin-top: 8px;
}

.judge-card {
  border: 1px solid #e6a23c;
}

.judge-streaming {
  padding: 8px 0;
}

.judge-hint {
  font-size: 13px;
  color: #909399;
  margin: 8px 0;
}

.judge-text {
  max-height: 320px;
}

.judge-text.full {
  max-height: 400px;
}

.verdict-panel {
  padding: 8px 0;
}

.verdict-stats {
  display: flex;
  gap: 20px;
  justify-content: center;
  align-items: center;
  margin-bottom: 16px;
  flex-wrap: wrap;
}

.stat-item {
  text-align: center;
}

.stat-icon {
  font-size: 24px;
  margin-bottom: 4px;
}

.stat-value {
  font-size: 28px;
  font-weight: 600;
}

.stat-label {
  font-size: 12px;
  color: #909399;
  margin-top: 2px;
}

.bull-stat, .bear-stat {
  min-width: 80px;
}

.error-card {
  border: 1px solid #f56c6c;
}

.error-card p {
  color: #f56c6c;
  font-size: 13px;
}

.section-card {
  background: #1f1f1f;
  border: 1px solid #2c2c2c;
}

.base-agents-card {
  margin-bottom: 4px;
}

.base-agents-card :deep(.el-card__body) {
  padding: 12px 16px;
}

.data-card, .factor-card {
  margin-bottom: 4px;
}

.data-card :deep(.el-card__body),
.factor-card :deep(.el-card__body) {
  padding: 10px 16px;
}

.data-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.data-item {
  display: flex;
  align-items: center;
  gap: 5px;
  padding: 4px 10px;
  border-radius: 4px;
  font-size: 11px;
  background: #2c2c2c;
  color: #909399;
}

.data-item.done {
  color: #67c23a;
  background: rgba(103, 194, 58, 0.1);
}

.data-item.running {
  color: #e6a23c;
  background: rgba(230, 162, 60, 0.1);
}

.data-icon {
  font-size: 13px;
}

.data-icon.done { color: #67c23a; }
.data-icon.waiting { color: #4a4a4a; }
.data-icon.loading { color: #e6a23c; }

.data-label {
  font-weight: 500;
}

.factor-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 8px;
}

.factor-item {
  background: #2c2c2c;
  border-radius: 6px;
  padding: 8px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.factor-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.factor-label {
  font-size: 11px;
  font-weight: 600;
  color: #e5eaf3;
}

.factor-score {
  font-size: 16px;
  font-weight: 700;
  color: #67c23a;
}

.factor-composite {
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px solid #2c2c2c;
  font-size: 13px;
  color: #e5eaf3;
  display: flex;
  align-items: center;
  gap: 8px;
}

.factor-composite strong {
  font-size: 18px;
  color: #409eff;
}

.base-agents-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 8px;
  width: 100%;
}

.base-agent-card {
  background: #2c2c2c;
  border-radius: 6px;
  padding: 10px;
  border: 1px solid transparent;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.base-agent-card.completed {
  border-color: #67c23a;
}

.base-agent-card.running {
  border-color: #e6a23c;
}

.base-agent-card.error {
  border-color: #f56c6c;
}

.base-agent-header {
  display: flex;
  align-items: center;
  gap: 8px;
}

.agent-icon-sm {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  background: #3c3c3c;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  color: #909399;
  flex-shrink: 0;
}

.base-agent-card.completed .agent-icon-sm {
  color: #67c23a;
}

.base-agent-card.running .agent-icon-sm {
  color: #e6a23c;
}

.agent-live-text {
  font-size: 11px;
  color: #c0c4cc;
  line-height: 1.5;
  white-space: pre-wrap;
  word-break: break-word;
  background: #1a1a1a;
  border-radius: 4px;
  padding: 6px 8px;
  margin-top: 6px;
  max-height: 100px;
  overflow-y: auto;
  flex: 1;
}

.cursor-blink {
  animation: blink 0.8s step-end infinite;
  color: #67c23a;
}

@keyframes blink {
  50% { opacity: 0; }
}

.base-agent-card.running .agent-icon-sm {
  background: rgba(230, 162, 60, 0.2);
  color: #e6a23c;
}

.agent-name-sm {
  font-size: 12px;
  font-weight: 600;
  color: #e5eaf3;
}

.agent-detail-collapse :deep(.el-collapse-item__header) {
  font-size: 11px;
  color: #909399;
  height: 24px;
  line-height: 24px;
  padding: 0;
}

.agent-detail-collapse :deep(.el-collapse-item__wrap) {
  background: transparent;
}

.agent-detail-collapse :deep(.el-collapse-item__content) {
  padding: 4px 0;
}

.agent-text {
  font-size: 11px;
  max-height: 120px;
}

.section-card :deep(.el-card__header) {
  border-bottom: 1px solid #2c2c2c;
  padding: 12px 16px;
  color: #e5eaf3;
  font-size: 14px;
  font-weight: 600;
}
</style>
