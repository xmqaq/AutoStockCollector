<template>
  <div class="ai-monitor">
    <!-- Header -->
    <div class="monitor-header">
      <div class="header-left">
        <h2>AI 实时监控</h2>
        <span class="header-sub">主力资金 · 研报分析 · 长短线建议</span>
      </div>
      <div class="header-right">
        <el-tag v-if="lastRefresh" type="info" effect="plain" class="refresh-tag">
          上次刷新: {{ lastRefresh }}
        </el-tag>
        <el-button type="primary" :loading="refreshing" @click="handleRefresh" size="small">
          <el-icon><Refresh /></el-icon> 刷新
        </el-button>
      </div>
    </div>

    <!-- Filter -->
    <div class="filter-bar">
      <el-input
        v-model="searchText"
        placeholder="搜索代码/名称"
        clearable
        size="small"
        class="search-input"
        @input="onFilter"
      />
      <el-select v-model="signalFilter" placeholder="信号筛选" size="small" clearable class="filter-select" @change="onFilter">
        <el-option label="全部" value="" />
        <el-option label="短期买入" value="short_buy" />
        <el-option label="短期卖出" value="short_sell" />
        <el-option label="长期买入" value="long_buy" />
        <el-option label="长期卖出" value="long_sell" />
      </el-select>
      <el-select v-model="typeFilter" placeholder="来源" size="small" clearable class="filter-select" @change="onFilter">
        <el-option label="全部" value="" />
        <el-option label="持仓" value="持仓" />
        <el-option label="自选" value="自选" />
      </el-select>
    </div>

    <!-- Stats -->
    <div class="stats-bar">
      <el-card shadow="never" class="stat-card">
        <div class="stat-label">持仓监控</div>
        <div class="stat-value">{{ positionCount }}</div>
      </el-card>
      <el-card shadow="never" class="stat-card">
        <div class="stat-label">自选监控</div>
        <div class="stat-value">{{ watchlistCount }}</div>
      </el-card>
      <el-card shadow="never" class="stat-card">
        <div class="stat-label">短期买入</div>
        <div class="stat-value text-success">{{ shortBuyCount }}</div>
      </el-card>
      <el-card shadow="never" class="stat-card">
        <div class="stat-label">长期买入</div>
        <div class="stat-value text-success">{{ longBuyCount }}</div>
      </el-card>
      <el-card shadow="never" class="stat-card">
        <div class="stat-label">短期卖出</div>
        <div class="stat-value text-danger">{{ shortSellCount }}</div>
      </el-card>
      <el-card shadow="never" class="stat-card">
        <div class="stat-label">长期卖出</div>
        <div class="stat-value text-danger">{{ longSellCount }}</div>
      </el-card>
    </div>

    <!-- Signal Grid -->
    <div class="signal-grid" v-loading="loading">
      <el-row :gutter="12">
        <el-col v-for="s in filteredSignals" :key="s.code" :xs="24" :sm="12" :lg="8" :xl="6">
          <el-card shadow="hover" class="signal-card" @click="showDetail(s)">
            <!-- Card Header -->
            <div class="card-header">
              <div class="card-title">
                <span class="stock-code">{{ s.code }}</span>
                <span class="stock-name">{{ s.name }}</span>
              </div>
              <el-tag :type="s.type === '持仓' ? 'warning' : 'info'" size="small" effect="plain">
                {{ s.type }}
              </el-tag>
            </div>

            <!-- Price -->
            <div class="card-price">
              <span class="price-val">{{ fmtPrice(s.price) }}</span>
              <span :class="['change', s.change_rate >= 0 ? 'up' : 'down']">
                {{ fmtChange(s.change_rate) }}
              </span>
            </div>

            <!-- Composite Badge -->
            <div class="composite-row">
              <el-tag :type="signalTagType(s.composite.signal)" size="small" effect="dark">
                {{ s.composite.label }}
              </el-tag>
              <span class="confidence">{{ (s.confidence * 100).toFixed(0) }}% 置信</span>
            </div>

            <!-- Dual signal bars -->
            <div class="signal-bars">
              <div class="signal-bar-row">
                <span class="bar-label">短期</span>
                <el-progress
                  :percentage="s.short_term.score"
                  :color="scoreColor(s.short_term.score)"
                  :stroke-width="10"
                  :format="() => signalLabel(s.short_term.signal)"
                />
              </div>
              <div class="signal-bar-row">
                <span class="bar-label">长期</span>
                <el-progress
                  :percentage="s.long_term.score"
                  :color="scoreColor(s.long_term.score)"
                  :stroke-width="10"
                  :format="() => signalLabel(s.long_term.signal)"
                />
              </div>
            </div>

            <!-- Reasons preview -->
            <div class="reasons-preview">
              <div v-if="s.short_term.reasons?.length" class="reason-line short-reason">
                <el-icon size="12"><Top /></el-icon> {{ s.short_term.reasons[0] }}
              </div>
              <div v-if="s.long_term.reasons?.length" class="reason-line long-reason">
                <el-icon size="12"><Timer /></el-icon> {{ s.long_term.reasons[0] }}
              </div>
            </div>

            <!-- Divergence -->
            <div v-if="s.composite.divergence" class="divergence-tip">
              {{ s.composite.divergence }}
            </div>
          </el-card>
        </el-col>
      </el-row>

      <el-empty v-if="!loading && filteredSignals.length === 0" description="暂无监控信号" />
    </div>

    <!-- Detail Dialog -->
    <el-dialog
      v-model="detailVisible"
      :title="detailData?.name || detailData?.code"
      width="800px"
      top="5vh"
      class="detail-dialog"
      destroy-on-close
    >
      <template v-if="detailData">
        <div class="detail-header">
          <span class="dl-code">{{ detailData.code }}</span>
          <el-tag :type="detailData.type === '持仓' ? 'warning' : 'info'" size="small">
            {{ detailData.type }}
          </el-tag>
          <span v-if="detailData.industry" class="dl-industry">{{ detailData.industry }}</span>
        </div>
        <div class="detail-price">
          现价: <strong>{{ fmtPrice(detailData.price) }}</strong>
          <span :class="['change', detailData.change_rate >= 0 ? 'up' : 'down']">
            {{ fmtChange(detailData.change_rate) }}
          </span>
        </div>

        <!-- Signal Comparison -->
        <el-row :gutter="16" class="dl-signals">
          <el-col :span="12">
            <div class="dl-signal-box short-box">
              <div class="dl-signal-header">短期建议</div>
              <div class="dl-signal-value">
                <el-tag :type="signalTagType(detailData.short_term.signal)" size="large" effect="dark">
                  {{ detailData.short_term.signal_label || detailData.short_term.signal }}
                </el-tag>
                <span class="dl-score">{{ detailData.short_term.score }}</span>
              </div>
              <el-progress
                :percentage="detailData.short_term.score"
                :color="scoreColor(detailData.short_term.score)"
                :stroke-width="8"
                :show-text="false"
              />
              <div class="dl-breakdown">
                <div v-for="(v, k) in detailData.short_term.breakdown" :key="k" class="bd-item">
                  <span class="bd-label">{{ k }}</span>
                  <span :style="{ color: scoreColor(v) }">{{ v }}</span>
                </div>
              </div>
              <ul class="dl-reasons">
                <li v-for="(r, i) in detailData.short_term.reasons" :key="i">{{ r }}</li>
              </ul>
            </div>
          </el-col>
          <el-col :span="12">
            <div class="dl-signal-box long-box">
              <div class="dl-signal-header">长期建议</div>
              <div class="dl-signal-value">
                <el-tag :type="signalTagType(detailData.long_term.signal)" size="large" effect="dark">
                  {{ detailData.long_term.signal_label || detailData.long_term.signal }}
                </el-tag>
                <span class="dl-score">{{ detailData.long_term.score }}</span>
              </div>
              <el-progress
                :percentage="detailData.long_term.score"
                :color="scoreColor(detailData.long_term.score)"
                :stroke-width="8"
                :show-text="false"
              />
              <div class="dl-breakdown">
                <div v-for="(v, k) in detailData.long_term.breakdown" :key="k" class="bd-item">
                  <span class="bd-label">{{ k }}</span>
                  <span :style="{ color: scoreColor(v) }">{{ v }}</span>
                </div>
              </div>
              <ul class="dl-reasons">
                <li v-for="(r, i) in detailData.long_term.reasons" :key="i">{{ r }}</li>
              </ul>
            </div>
          </el-col>
        </el-row>

        <!-- Composite -->
        <el-card shadow="never" class="dl-composite">
          <div class="dl-comp-row">
            <span class="comp-label">综合评分</span>
            <span class="comp-score" :style="{ color: scoreColor(detailData.composite.score) }">
              {{ detailData.composite.score }}
            </span>
            <el-tag :type="signalTagType(detailData.composite.signal)" effect="dark">
              {{ detailData.composite.label }}
            </el-tag>
            <span class="comp-conf">置信度: {{ (detailData.confidence * 100).toFixed(0) }}%</span>
            <span v-if="detailData.composite.divergence" class="comp-div">
              {{ detailData.composite.divergence }}
            </span>
          </div>
        </el-card>

        <!-- Analysis Breakdown -->
        <el-tabs class="dl-tabs" v-model="detailTab">
          <el-tab-pane label="资金流向" name="fund_flow">
            <div class="tab-content">
              <div class="tab-sub">
                <h4>短期资金</h4>
                <p>评分: {{ detailData.analysis.fund_flow.short_term.score }} / 信号: {{ detailData.analysis.fund_flow.short_term.signal }}</p>
                <ul><li v-for="r in detailData.analysis.fund_flow.short_term.reasons" :key="r">{{ r }}</li></ul>
              </div>
              <div class="tab-sub">
                <h4>长期资金</h4>
                <p>评分: {{ detailData.analysis.fund_flow.long_term.score }} / 信号: {{ detailData.analysis.fund_flow.long_term.signal }}</p>
                <ul><li v-for="r in detailData.analysis.fund_flow.long_term.reasons" :key="r">{{ r }}</li></ul>
              </div>
            </div>
          </el-tab-pane>
          <el-tab-pane label="研报分析" name="research">
            <div class="tab-content">
              <p>研报数量: {{ detailData.analysis.research.report_count || 0 }}</p>
              <div class="tab-sub">
                <h4>短期研报</h4>
                <p>评分: {{ detailData.analysis.research.short_term.score }} / 近{{ detailData.analysis.research.short_term.recent_count || 0 }}份</p>
                <ul><li v-for="r in detailData.analysis.research.short_term.reasons" :key="r">{{ r }}</li></ul>
              </div>
              <div class="tab-sub">
                <h4>长期研报</h4>
                <p>评分: {{ detailData.analysis.research.long_term.score }} / 共{{ detailData.analysis.research.long_term.total_reports || 0 }}份</p>
                <ul><li v-for="r in detailData.analysis.research.long_term.reasons" :key="r">{{ r }}</li></ul>
              </div>
            </div>
          </el-tab-pane>
          <el-tab-pane label="技术面" name="technical">
            <div class="tab-content">
              <div class="tab-sub">
                <h4>短期技术</h4>
                <p>评分: {{ detailData.analysis.technical.short_term.score }} / 信号: {{ detailData.analysis.technical.short_term.signal }}</p>
                <ul><li v-for="r in detailData.analysis.technical.short_term.reasons" :key="r">{{ r }}</li></ul>
              </div>
              <div class="tab-sub">
                <h4>长期技术</h4>
                <p>评分: {{ detailData.analysis.technical.long_term.score }} / 信号: {{ detailData.analysis.technical.long_term.signal }}</p>
                <ul><li v-for="r in detailData.analysis.technical.long_term.reasons" :key="r">{{ r }}</li></ul>
              </div>
            </div>
          </el-tab-pane>
          <el-tab-pane label="基本面" name="fundamental">
            <div class="tab-content">
              <p>评分: {{ detailData.analysis.fundamental.score }} / 信号: {{ detailData.analysis.fundamental.signal }}</p>
              <ul><li v-for="r in detailData.analysis.fundamental.reasons" :key="r">{{ r }}</li></ul>
              <div v-if="detailData.analysis.fundamental.details" class="detail-grid">
                <div v-for="(v, k) in detailData.analysis.fundamental.details" :key="k" class="detail-item">
                  <span class="di-label">{{ k }}</span>
                  <span class="di-value">{{ v ?? '--' }}</span>
                </div>
              </div>
            </div>
          </el-tab-pane>
        </el-tabs>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { Refresh, Top, Timer } from '@element-plus/icons-vue'
import { monitorApi, type MonitorSignal } from '@/api/monitor'
import { ElMessage } from 'element-plus'

const signals = ref<MonitorSignal[]>([])
const loading = ref(false)
const refreshing = ref(false)
const lastRefresh = ref('')
const searchText = ref('')
const signalFilter = ref('')
const typeFilter = ref('')
const detailVisible = ref(false)
const detailData = ref<MonitorSignal | null>(null)
const detailTab = ref('fund_flow')

let refreshTimer: ReturnType<typeof setInterval> | null = null

const filteredSignals = computed(() => {
  let list = signals.value
  if (searchText.value) {
    const q = searchText.value.toLowerCase()
    list = list.filter(s => s.code.toLowerCase().includes(q) || s.name.toLowerCase().includes(q))
  }
  if (signalFilter.value) {
    switch (signalFilter.value) {
      case 'short_buy': list = list.filter(s => s.short_term.score >= 60); break
      case 'short_sell': list = list.filter(s => s.short_term.score < 40); break
      case 'long_buy': list = list.filter(s => s.long_term.score >= 60); break
      case 'long_sell': list = list.filter(s => s.long_term.score < 40); break
    }
  }
  if (typeFilter.value) {
    list = list.filter(s => s.type === typeFilter.value)
  }
  return list
})

const positionCount = computed(() => signals.value.filter(s => s.type === '持仓').length)
const watchlistCount = computed(() => signals.value.filter(s => s.type === '自选').length)
const shortBuyCount = computed(() => signals.value.filter(s => s.short_term.score >= 60).length)
const longBuyCount = computed(() => signals.value.filter(s => s.long_term.score >= 60).length)
const shortSellCount = computed(() => signals.value.filter(s => s.short_term.score < 40).length)
const longSellCount = computed(() => signals.value.filter(s => s.long_term.score < 40).length)

function onFilter() {}

function fetchSignals() {
  loading.value = true
  monitorApi.getSignals().then(resp => {
    signals.value = (resp.data as any).data || []
  }).catch(() => {
    ElMessage.error('获取监控信号失败')
  }).finally(() => {
    loading.value = false
  })
}

function handleRefresh() {
  refreshing.value = true
  monitorApi.refresh().then(() => {
    ElMessage.success('刷新任务已启动')
    setTimeout(fetchSignals, 3000)
  }).catch(() => {
    ElMessage.error('刷新失败')
  }).finally(() => {
    refreshing.value = false
    lastRefresh.value = new Date().toLocaleTimeString()
  })
}

function showDetail(s: MonitorSignal) {
  detailData.value = s
  detailTab.value = 'fund_flow'
  detailVisible.value = true
}

function signalLabel(sig: string): string {
  const map: Record<string, string> = { strong_buy: '强烈买入', buy: '买入', hold: '持有', sell: '卖出', strong_sell: '强烈卖出' }
  return map[sig] || sig
}

function signalTagType(sig: string): string {
  if (sig === 'strong_buy' || sig === 'buy') return 'danger'
  if (sig === 'sell' || sig === 'strong_sell') return 'success'
  return 'info'
}

function scoreColor(score: number): string {
  if (score >= 75) return '#f56c6c'
  if (score >= 60) return '#e6a23c'
  if (score >= 40) return '#909399'
  return '#67c23a'
}

function fmtPrice(v: number | undefined | null): string {
  if (v == null || v === 0) return '--'
  return '¥' + v.toFixed(2)
}

function fmtChange(v: number | undefined | null): string {
  if (v == null) return '--'
  const sign = v >= 0 ? '+' : ''
  return sign + v.toFixed(2) + '%'
}

onMounted(() => {
  fetchSignals()
  refreshTimer = setInterval(fetchSignals, 60000)
})

onUnmounted(() => {
  if (refreshTimer) clearInterval(refreshTimer)
})
</script>

<style scoped>
.ai-monitor {
  padding: 16px;
  height: 100%;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.monitor-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.header-left h2 {
  margin: 0;
  font-size: 20px;
  font-weight: 600;
}

.header-sub {
  font-size: 12px;
  color: var(--text-muted, #999);
  margin-left: 8px;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 8px;
}

.refresh-tag { font-size: 11px; }

.filter-bar {
  display: flex;
  gap: 8px;
  align-items: center;
}

.search-input { width: 200px; }
.filter-select { width: 140px; }

.stats-bar {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.stat-card { flex: 1; min-width: 100px; }
.stat-label { font-size: 12px; color: var(--text-muted, #999); }
.stat-value { font-size: 22px; font-weight: 700; margin-top: 4px; }
.text-success { color: #67c23a; }
.text-danger { color: #f56c6c; }

.signal-grid {
  flex: 1;
  overflow-y: auto;
}

.signal-card {
  margin-bottom: 12px;
  cursor: pointer;
  transition: transform 0.15s, box-shadow 0.15s;
}
.signal-card:hover {
  transform: translateY(-2px);
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.card-title {
  display: flex;
  align-items: center;
  gap: 6px;
}

.stock-code {
  font-family: 'IBM Plex Mono', monospace;
  font-size: 13px;
  color: var(--text-muted, #999);
}

.stock-name {
  font-size: 15px;
  font-weight: 600;
}

.card-price {
  display: flex;
  align-items: baseline;
  gap: 8px;
  margin-bottom: 8px;
}

.price-val {
  font-size: 20px;
  font-weight: 700;
  font-family: 'IBM Plex Mono', monospace;
}

.change { font-size: 13px; font-weight: 600; }
.change.up { color: #f56c6c; }
.change.down { color: #67c23a; }

.composite-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
}

.confidence { font-size: 12px; color: var(--text-muted, #999); }

.signal-bars {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-bottom: 8px;
}

.signal-bar-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.bar-label {
  font-size: 11px;
  color: var(--text-muted, #999);
  width: 28px;
  flex-shrink: 0;
}

.reasons-preview {
  font-size: 12px;
  color: var(--text-secondary, #666);
}

.reason-line {
  display: flex;
  align-items: center;
  gap: 4px;
  margin-bottom: 2px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.short-reason { color: #e6a23c; }
.long-reason { color: #409eff; }

.divergence-tip {
  margin-top: 6px;
  padding: 4px 8px;
  background: var(--el-color-warning-light-9, #fdf6ec);
  border-radius: 4px;
  font-size: 11px;
  color: #e6a23c;
}

/* Detail Dialog */
.detail-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.dl-code {
  font-family: 'IBM Plex Mono', monospace;
  font-size: 14px;
  color: var(--text-muted, #999);
}

.dl-industry {
  font-size: 12px;
  color: var(--text-muted, #999);
}

.detail-price {
  margin-bottom: 16px;
  font-size: 14px;
}

.dl-signals { margin-bottom: 16px; }

.dl-signal-box {
  padding: 12px;
  border-radius: 8px;
  border: 1px solid var(--border-color, #eee);
}

.short-box { border-left: 3px solid #e6a23c; }
.long-box { border-left: 3px solid #409eff; }

.dl-signal-header {
  font-size: 12px;
  font-weight: 600;
  margin-bottom: 8px;
  color: var(--text-muted, #999);
}

.dl-signal-value {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.dl-score {
  font-size: 24px;
  font-weight: 700;
}

.dl-breakdown {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin: 8px 0;
}

.bd-item {
  font-size: 11px;
  padding: 2px 6px;
  background: var(--el-fill-color, #f5f5f5);
  border-radius: 4px;
}

.bd-label { margin-right: 4px; color: var(--text-muted, #999); }

.dl-reasons {
  margin: 8px 0 0;
  padding-left: 16px;
  font-size: 12px;
  color: var(--text-secondary, #666);
}

.dl-reasons li { margin-bottom: 2px; }

.dl-composite { margin-bottom: 16px; }

.dl-comp-row {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.comp-label { font-size: 12px; color: var(--text-muted, #999); }
.comp-score { font-size: 28px; font-weight: 700; }
.comp-conf { font-size: 12px; color: var(--text-muted, #999); }
.comp-div { font-size: 11px; color: #e6a23c; }

.dl-tabs { margin-top: 8px; }

.tab-content { padding: 8px 0; }
.tab-sub { margin-bottom: 12px; }
.tab-sub h4 { margin: 0 0 4px; font-size: 13px; }
.tab-sub p { font-size: 12px; color: var(--text-muted, #999); margin: 0 0 4px; }
.tab-sub ul { margin: 0; padding-left: 16px; font-size: 12px; }
.tab-sub li { margin-bottom: 2px; }

.detail-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(120px, 1fr));
  gap: 8px;
  margin-top: 12px;
}

.detail-item {
  padding: 6px 8px;
  background: var(--el-fill-color, #f5f5f5);
  border-radius: 4px;
}

.di-label {
  display: block;
  font-size: 11px;
  color: var(--text-muted, #999);
}

.di-value {
  display: block;
  font-size: 14px;
  font-weight: 600;
  font-family: 'IBM Plex Mono', monospace;
}
</style>
