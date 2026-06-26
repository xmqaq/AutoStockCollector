<template>
  <div class="ar-page">
    <el-card shadow="never" class="ar-head">
      <div class="ar-head-row">
        <span class="ar-title">📡 盘前竞价雷达</span>
        <el-tag v-if="statusData?.status === 'running'" type="warning" effect="dark">
          扫描中...{{ statusData.total ? `(${statusData.processed}/${statusData.total})` : '' }}
        </el-tag>
        <el-tag v-else-if="statusData?.status === 'done'" type="success" effect="plain">{{ result?.date || '' }}</el-tag>
        <el-tag v-else-if="statusData?.status === 'failed'" type="danger" effect="dark">扫描失败</el-tag>
        <el-tag v-else type="info" effect="plain">等待</el-tag>
        <el-button size="small" :loading="loading" @click="loadAll">刷新</el-button>
        <el-button size="small" :loading="scanLoading" @click="triggerScan">手动扫描</el-button>
      </div>
      <div v-if="resultsError" class="ar-error">{{ resultsError }}</div>
    </el-card>

    <el-tabs v-model="activeTab" class="ar-tabs">
      <!-- ─── Tab 1: 雷达结果 ─── -->
      <el-tab-pane label="雷达结果" name="radar">
        <el-card v-if="result?.summary" shadow="never" class="ar-summary-card">
          <div class="ar-summary">{{ result.summary }}</div>
        </el-card>

        <el-card v-if="sectorLeaders.length" shadow="never" class="ar-card">
          <template #header><span>🏆 板块龙头</span></template>
          <div class="ar-sector-grid">
            <div v-for="sl in sectorLeaders" :key="sl.sector" class="ar-sector-item">
              <span class="ar-si-name">{{ sl.sector }}</span>
              <span class="ar-si-leader">{{ sl.name }}({{ sl.leader }})</span>
              <span class="ar-si-score">{{ sl.score }}分</span>
            </div>
          </div>
        </el-card>

        <el-card v-if="trapWarnings.length" shadow="never" class="ar-card ar-trap-card">
          <template #header><span>⚠️ 诱多/诱空预警</span></template>
          <div v-for="t in trapWarnings" :key="t.symbol" class="ar-trap-item">
            <el-tag :type="t.trap_type === 'bull_trap' ? 'danger' : 'success'" size="small" effect="dark">
              {{ t.trap_type === 'bull_trap' ? '诱多' : '诱空' }}
            </el-tag>
            <span class="ar-trap-code">{{ t.name }}({{ t.symbol }})</span>
            <span class="ar-trap-reason">{{ t.reason }}</span>
          </div>
        </el-card>

        <el-card v-if="result" shadow="never" class="ar-card">
          <template #header>
            <span>📊 今日强势股 TOP {{ result.top_stocks?.length || 0 }}</span>
            <span class="ar-scan-info">共扫描 {{ result.total_scanned }} 只</span>
          </template>
          <el-table :data="result.top_stocks" stripe size="small" highlight-current-row>
            <el-table-column label="#" width="40" type="index" />
            <el-table-column label="代码" width="80" prop="symbol" />
            <el-table-column label="名称" width="90" prop="name" />
            <el-table-column label="行业" width="90" prop="industry" />
            <el-table-column label="开盘价" width="80" align="right">
              <template #default="{ row }">¥{{ row.open_price?.toFixed(2) }}</template>
            </el-table-column>
            <el-table-column label="跳空%" width="75" align="right">
              <template #default="{ row }">
                <span :class="row.gap_pct >= 0 ? 'ar-gap-up' : 'ar-gap-down'">{{ row.gap_pct >= 0 ? '+' : '' }}{{ row.gap_pct?.toFixed(2) }}%</span>
              </template>
            </el-table-column>
            <el-table-column label="竞价额" width="100" align="right">
              <template #default="{ row }">¥{{ (row.auction_amount / 1e4).toFixed(0) }}万</template>
            </el-table-column>
            <el-table-column label="强度" width="70" align="center">
              <template #default="{ row }">
                <el-tag :type="strengthTagType(row.strength_score)" size="small">{{ row.strength_score }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="预警" width="70" align="center">
              <template #default="{ row }">
                <el-tag v-if="row.trap_warning" :type="row.trap_warning.trap_type === 'bull_trap' ? 'danger' : 'success'" size="small">
                  {{ row.trap_warning.trap_type === 'bull_trap' ? '诱多' : '诱空' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="亮点" width="100">
              <template #default="{ row }">
                <el-tag v-if="row.highlight" type="warning" size="small" effect="dark">🔥 {{ row.highlight_reason }}</el-tag>
              </template>
            </el-table-column>
          </el-table>
        </el-card>

        <el-card v-else-if="!loading && !resultsError" shadow="never">
          <el-empty description="今日尚未扫描，等待 9:25 自动触发，或点击手动扫描" />
        </el-card>
        <el-card v-else-if="resultsError && !result" shadow="never">
          <el-empty :description="resultsError" />
        </el-card>
      </el-tab-pane>

      <!-- ─── Tab 2: 盘中实时 ─── -->
      <el-tab-pane label="盘中实时" name="intraday">
        <div v-if="intradayRecords.length">
          <el-card shadow="never" class="ar-card">
            <template #header>
              <span>📡 盘中追踪（每 15 秒自动刷新）</span>
              <span class="ar-scan-info">{{ intradayRecords.length }} 只追踪中</span>
            </template>
            <el-table :data="intradayRecords" stripe size="small" highlight-current-row>
              <el-table-column label="代码" width="80" prop="code" />
              <el-table-column label="名称" width="80" prop="name" />
              <el-table-column label="行业" width="80" prop="industry" />
              <el-table-column label="开盘价" width="75" align="right" prop="open_price" />
              <el-table-column label="跳空%" width="70" align="right">
                <template #default="{ row }">
                  <span :class="row.gap_pct >= 0 ? 'ar-gap-up' : 'ar-gap-down'">{{ row.gap_pct >= 0 ? '+' : '' }}{{ row.gap_pct?.toFixed(2) }}%</span>
                </template>
              </el-table-column>
              <el-table-column label="强度" width="60" align="center" prop="strength_score" />
              <el-table-column label="实时价" width="80" align="right">
                <template #default="{ row }">
                  <span :class="row.current_price > row.open_price ? 'ar-gap-up' : 'ar-gap-down'">
                    {{ row.current_price ? row.current_price.toFixed(2) : '-' }}
                  </span>
                </template>
              </el-table-column>
              <el-table-column label="实时盈亏" width="90" align="right">
                <template #default="{ row }">
                  <span v-if="row.current_pnl_pct != null" :class="row.current_pnl_pct >= 0 ? 'ar-gap-up' : 'ar-gap-down'" style="font-weight: bold;">
                    {{ row.current_pnl_pct >= 0 ? '+' : '' }}{{ row.current_pnl_pct?.toFixed(2) }}%
                  </span>
                  <span v-else class="ar-text-muted">-</span>
                </template>
              </el-table-column>
              <el-table-column label="状态" width="80" align="center">
                <template #default="{ row }">
                  <el-tag v-if="row.status === 'traded'" type="success" size="small">已交易</el-tag>
                  <el-tag v-else-if="row.is_trap" type="danger" size="small">{{ row.trap_type === 'bull_trap' ? '诱多' : '诱空' }}</el-tag>
                  <el-tag v-else type="warning" size="small">追踪中</el-tag>
                </template>
              </el-table-column>
              <el-table-column label="模拟交易" width="120">
                <template #default="{ row }">
                  <el-tag v-if="row.auto_trade_id" type="success" size="small">已自动建仓</el-tag>
                  <span v-else class="ar-text-muted">-</span>
                </template>
              </el-table-column>
            </el-table>
          </el-card>
        </div>
        <div v-else-if="!intradayLoaded">
          <el-card shadow="never">
            <el-empty description="今日尚未扫描，暂无盘中数据" />
          </el-card>
        </div>
      </el-tab-pane>

      <!-- ─── Tab 3: 仓位建议 ─── -->
      <el-tab-pane label="仓位建议" name="position">
        <el-card v-if="positionResult" shadow="never" class="ar-card">
          <template #header>
            <span>💰 仓位建议</span>
            <span class="ar-scan-info">{{ positionResult.summary }}</span>
          </template>
          <el-table :data="positionResult.suggestions" stripe size="small">
            <el-table-column label="操作" width="70" align="center">
              <template #default="{ row }">
                <el-tag :type="actionTagType(row.action)" size="small" effect="dark">
                  {{ actionLabel(row.action) }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="代码" width="80" prop="symbol" />
            <el-table-column label="名称" width="90" prop="name" />
            <el-table-column label="仓位" width="80" align="right">
              <template #default="{ row }">{{ (row.position_pct * 100).toFixed(1) }}%</template>
            </el-table-column>
            <el-table-column label="信心" width="80" align="center">
              <template #default="{ row }">
                <el-tag :type="confidenceTagType(row.confidence)" size="small">{{ row.confidence }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="理由" min-width="200">
              <template #default="{ row }">{{ row.reason }}</template>
            </el-table-column>
          </el-table>
        </el-card>
        <el-card v-else-if="positionError" shadow="never">
          <el-empty :description="positionError" />
        </el-card>
        <el-card v-else shadow="never">
          <el-empty description="暂无仓位建议，请先执行扫描" />
        </el-card>
      </el-tab-pane>

      <!-- ─── Tab 4: 风控与持仓 ─── -->
      <el-tab-pane label="风控与持仓" name="risk">
        <div v-if="riskLoading" class="ar-loading">加载中…</div>

        <template v-else-if="riskError">
          <el-card shadow="never">
            <el-empty :description="riskError" />
          </el-card>
        </template>

        <template v-else-if="riskData">
          <!-- Summary cards -->
          <div class="ar-risk-grid">
            <div class="ar-risk-card ar-risk-card-green">
              <div class="ar-risk-label">总盈亏</div>
              <div class="ar-risk-value" :class="riskData.total_pnl >= 0 ? 'ar-gap-up' : 'ar-gap-down'">
                ¥{{ riskData.total_pnl.toFixed(2) }}
                <span class="ar-risk-sub">({{ riskData.total_pnl_pct >= 0 ? '+' : '' }}{{ riskData.total_pnl_pct.toFixed(2) }}%)</span>
              </div>
            </div>
            <div class="ar-risk-card">
              <div class="ar-risk-label">持仓</div>
              <div class="ar-risk-value">{{ riskData.auto_trade_count }} / {{ riskData.max_positions }} 只</div>
            </div>
            <div class="ar-risk-card ar-risk-card-orange">
              <div class="ar-risk-label">敞口</div>
              <div class="ar-risk-value">{{ riskData.total_exposure_pct.toFixed(1) }}%</div>
              <div class="ar-risk-sub">上限 {{ riskData.max_exposure_pct }}%</div>
            </div>
            <div class="ar-risk-card ar-risk-card-blue">
              <div class="ar-risk-label">现金余额</div>
              <div class="ar-risk-value">¥{{ riskData.cash_balance.toFixed(2) }}</div>
            </div>
          </div>

          <!-- Positions table -->
          <el-card shadow="never" class="ar-card">
            <template #header>
              <span>📋 今日自动交易持仓</span>
              <el-button size="small" type="danger" plain :loading="closeLoading" @click="handleAutoClose">
                手动平仓所有
              </el-button>
            </template>
            <el-table v-if="riskData.positions.length" :data="riskData.positions" stripe size="small">
              <el-table-column label="代码" width="80" prop="code" />
              <el-table-column label="名称" width="80" prop="name" />
              <el-table-column label="持仓" width="70" align="right" prop="shares" />
              <el-table-column label="成本" width="80" align="right">
                <template #default="{ row }">¥{{ row.avg_cost.toFixed(2) }}</template>
              </el-table-column>
              <el-table-column label="现价" width="80" align="right">
                <template #default="{ row }">¥{{ row.current_price.toFixed(2) }}</template>
              </el-table-column>
              <el-table-column label="市值" width="90" align="right">
                <template #default="{ row }">¥{{ row.market_value.toFixed(2) }}</template>
              </el-table-column>
              <el-table-column label="盈亏%" width="90" align="right">
                <template #default="{ row }">
                  <span :class="row.pnl_percent >= 0 ? 'ar-gap-up' : 'ar-gap-down'">
                    {{ row.pnl_percent >= 0 ? '+' : '' }}{{ row.pnl_percent.toFixed(2) }}%
                  </span>
                </template>
              </el-table-column>
              <el-table-column label="止损" width="80" align="right">
                <template #default="{ row }">
                  <span v-if="row.stop_loss" :class="row.distance_to_sl != null && row.distance_to_sl < 3 ? 'ar-gap-down' : ''">
                    ¥{{ row.stop_loss.toFixed(2) }}
                    <span v-if="row.distance_to_sl != null" class="ar-risk-sub">({{ row.distance_to_sl.toFixed(1) }}%)</span>
                  </span>
                  <span v-else class="ar-text-muted">-</span>
                </template>
              </el-table-column>
              <el-table-column label="止盈" width="80" align="right">
                <template #default="{ row }">
                  <span v-if="row.take_profit">¥{{ row.take_profit.toFixed(2) }}</span>
                  <span v-else class="ar-text-muted">-</span>
                </template>
              </el-table-column>
            </el-table>
            <el-empty v-else description="今日无自动交易持仓" />
          </el-card>

          <!-- Sector exposure -->
          <el-card shadow="never" class="ar-card" v-if="Object.keys(riskData.sector_exposure).length">
            <template #header><span>📊 板块敞口分布</span></template>
            <div class="ar-sector-exposure">
              <div v-for="(val, key) in riskData.sector_exposure" :key="key" class="ar-sector-bar-item">
                <span class="ar-se-label">{{ key }}</span>
                <el-progress :percentage="Math.min(val / riskData.total_market_value * 100, 100)" :stroke-width="16" :text-inside="true" />
              </div>
            </div>
          </el-card>
        </template>
      </el-tab-pane>

      <!-- ─── Tab 5: 表现统计 ─── -->
      <el-tab-pane label="表现统计" name="performance">
        <el-card shadow="never" class="ar-card">
          <template #header>
            <span>📈 历史表现（{{ perfDays }}天）</span>
            <el-radio-group v-model="perfDays" size="small" @change="loadPerformance">
              <el-radio-button :value="7">7天</el-radio-button>
              <el-radio-button :value="30">30天</el-radio-button>
              <el-radio-button :value="90">90天</el-radio-button>
            </el-radio-group>
          </template>

          <div v-if="perfBuckets.length" class="ar-perf-grid">
            <div v-for="b in perfBuckets" :key="b.score_bracket" class="ar-perf-card" :class="perfCardClass(b)">
              <div class="ar-perf-bracket">{{ b.score_bracket }} 分</div>
              <div class="ar-perf-stat">
                胜率 <strong>{{ b.count ? ((b.wins / b.count) * 100).toFixed(1) : '-' }}%</strong>
              </div>
              <div class="ar-perf-stat">
                平均收益 <strong :class="b.avg_return >= 0 ? 'ar-gap-up' : 'ar-gap-down'">{{ b.avg_return ? (b.avg_return * 100).toFixed(2) : '-' }}%</strong>
              </div>
              <div class="ar-perf-stat">
                样本 <strong>{{ b.count }}</strong> 笔
              </div>
            </div>
          </div>
          <el-empty v-else-if="!perfError" description="暂无表现数据" />
          <el-empty v-else :description="perfError" />
        </el-card>

        <el-card shadow="never" class="ar-card">
          <template #header><span>📋 最近记录</span></template>
          <el-table v-if="perfRecords.length" :data="perfRecords" stripe size="small">
            <el-table-column label="日期" width="90" prop="date" />
            <el-table-column label="代码" width="80" prop="code" />
            <el-table-column label="名称" width="80" prop="name" />
            <el-table-column label="强度" width="60" align="center" prop="strength_score" />
            <el-table-column label="跳空%" width="70" align="right">
              <template #default="{ row }">{{ row.gap_pct >= 0 ? '+' : '' }}{{ row.gap_pct?.toFixed(2) }}%</template>
            </el-table-column>
            <el-table-column label="行业" width="80" prop="industry" />
            <el-table-column label="诱骗" width="60" align="center">
              <template #default="{ row }">
                <el-tag v-if="row.is_trap" :type="row.trap_type === 'bull_trap' ? 'danger' : 'success'" size="small">
                  {{ row.trap_type === 'bull_trap' ? '诱多' : '诱空' }}
                </el-tag>
                <span v-else class="ar-text-muted">-</span>
              </template>
            </el-table-column>
            <el-table-column label="结果" width="70" align="center">
              <template #default="{ row }">
                <el-tag v-if="row.result === 'win'" type="success" size="small">盈利</el-tag>
                <el-tag v-else-if="row.result === 'loss'" type="danger" size="small">亏损</el-tag>
                <el-tag v-else type="info" size="small">待定</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="收益率" width="80" align="right">
              <template #default="{ row }">
                <span v-if="row.return_pct != null" :class="row.return_pct >= 0 ? 'ar-gap-up' : 'ar-gap-down'">
                  {{ (row.return_pct * 100).toFixed(2) }}%
                </span>
                <span v-else class="ar-text-muted">-</span>
              </template>
            </el-table-column>
          </el-table>
          <el-empty v-else description="暂无记录" />
        </el-card>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { ElMessage } from 'element-plus'
import { auctionRadarApi, type RadarResult, type PositionResult, type PerformanceBucket, type PerformanceRecord, type IntradayRecord, type RiskSummary } from '@/api/auctionRadar'

const loading = ref(false)
const resultsError = ref('')
const positionError = ref('')
const perfError = ref('')
const scanLoading = ref(false)
const activeTab = ref('radar')
const result = ref<RadarResult | null>(null)
interface StatusData { status: string; scan_time: string; date: string; processed?: number; total?: number }
const statusData = ref<StatusData | null>(null)
const positionResult = ref<PositionResult | null>(null)
const perfBuckets = ref<PerformanceBucket[]>([])
const perfRecords = ref<PerformanceRecord[]>([])
const perfDays = ref(30)
const intradayRecords = ref<IntradayRecord[]>([])
const intradayLoaded = ref(false)
const riskData = ref<RiskSummary | null>(null)
const riskLoading = ref(false)
const riskError = ref('')
const closeLoading = ref(false)

let pollTimer: ReturnType<typeof setInterval> | null = null
let intradayTimer: ReturnType<typeof setInterval> | null = null

const sectorLeaders = computed(() => result.value?.sector_leaders || [])
const trapWarnings = computed(() => result.value?.trap_warnings || [])

function strengthTagType(score: number) {
  if (score >= 80) return 'danger'
  if (score >= 60) return 'warning'
  return 'info'
}

function actionTagType(action: string) {
  if (action === 'buy') return 'danger'
  if (action === 'observe') return 'warning'
  return 'info'
}

function actionLabel(action: string) {
  if (action === 'buy') return '买入'
  if (action === 'observe') return '观察'
  return '跳过'
}

function confidenceTagType(conf: string) {
  if (conf === 'high') return 'danger'
  if (conf === 'medium') return 'warning'
  return 'info'
}

function perfCardClass(b: PerformanceBucket) {
  const winRate = b.count ? b.wins / b.count : 0
  if (winRate >= 0.6) return 'ar-perf-good'
  if (winRate >= 0.4) return 'ar-perf-mid'
  return 'ar-perf-bad'
}

async function pollStatusUntilDone() {
  if (pollTimer) clearInterval(pollTimer)
  return new Promise<void>((resolve) => {
    pollTimer = setInterval(async () => {
      try {
        const res = await auctionRadarApi.getStatus()
        if (res.data?.success && res.data.data) {
          statusData.value = res.data.data as StatusData
          if (res.data.data.status !== 'running') {
            if (pollTimer) clearInterval(pollTimer)
            pollTimer = null
            resolve()
          }
        }
      } catch { /* continue polling */ }
    }, 2000)
  })
}

async function loadStatus() {
  try {
    const res = await auctionRadarApi.getStatus()
    if (res.data?.success && res.data.data) statusData.value = res.data.data as StatusData
  } catch { /* ignore */ }
}

async function loadResults() {
  loading.value = true
  resultsError.value = ''
  try {
    const res = await auctionRadarApi.getResults()
    if (res.data?.success) {
      result.value = res.data.data!
    } else {
      result.value = null
      resultsError.value = res.data?.error || ''
    }
  } catch (e: unknown) {
    result.value = null
    const err = e as { response?: { data?: { error?: string } }; message?: string }
    resultsError.value = err?.response?.data?.error || err?.message || '获取数据失败'
  }
  loading.value = false
}

async function loadPosition() {
  positionError.value = ''
  try {
    const res = await auctionRadarApi.getPositionSuggestions()
    if (res.data?.success) {
      positionResult.value = res.data.data!
    } else {
      positionResult.value = null
      positionError.value = res.data?.error || ''
    }
  } catch (e: unknown) {
    positionResult.value = null
    const err = e as { response?: { data?: { error?: string } }; message?: string }
    positionError.value = err?.response?.data?.error || err?.message || '获取仓位建议失败'
  }
}

async function loadPerformance() {
  perfError.value = ''
  try {
    const [statsRes, historyRes] = await Promise.allSettled([
      auctionRadarApi.getPerformance(perfDays.value),
      auctionRadarApi.getPerformanceHistory(perfDays.value),
    ])
    if (statsRes.status === 'fulfilled' && statsRes.value.data?.success) {
      perfBuckets.value = statsRes.value.data.data?.buckets || []
    } else {
      perfBuckets.value = []
    }
    if (historyRes.status === 'fulfilled' && historyRes.value.data?.success) {
      perfRecords.value = historyRes.value.data.data?.records || []
    } else {
      perfRecords.value = []
    }
    if (statsRes.status === 'rejected' && historyRes.status === 'rejected') {
      perfError.value = '获取表现数据失败'
    }
  } catch {
    perfBuckets.value = []
    perfRecords.value = []
    perfError.value = '获取表现数据失败'
  }
}

async function loadIntraday() {
  try {
    const res = await auctionRadarApi.getIntradayData()
    if (res.data?.success && res.data.data) {
      intradayRecords.value = res.data.data.records || []
      intradayLoaded.value = true
    }
  } catch {
    // silent
  }
}

async function loadRisk() {
  riskLoading.value = true
  riskError.value = ''
  try {
    const res = await auctionRadarApi.getRiskSummary()
    if (res.data?.success) {
      riskData.value = res.data.data!
    } else {
      riskError.value = res.data?.error || ''
    }
  } catch (e: unknown) {
    const err = e as { response?: { data?: { error?: string } }; message?: string }
    riskError.value = err?.response?.data?.error || err?.message || '获取风险数据失败'
  }
  riskLoading.value = false
}

async function handleAutoClose() {
  closeLoading.value = true
  try {
    const res = await auctionRadarApi.triggerAutoClose()
    if (res.data?.success) {
      ElMessage.success(`已平仓 ${res.data.data?.closed || 0} 笔`)
      await loadRisk()
    } else {
      ElMessage.error('平仓失败')
    }
  } catch {
    ElMessage.error('平仓请求异常')
  }
  closeLoading.value = false
}

function startIntradayPolling() {
  if (intradayTimer) clearInterval(intradayTimer)
  intradayTimer = setInterval(loadIntraday, 15000)
}

async function loadAll() {
  await Promise.allSettled([loadResults(), loadPosition(), loadPerformance(), loadIntraday(), loadRisk()])
  startIntradayPolling()
}

async function triggerScan() {
  scanLoading.value = true
  resultsError.value = ''
  statusData.value = { status: 'running', scan_time: new Date().toISOString(), date: '' }

  try {
    const res = await auctionRadarApi.triggerScan()
    if (res.data?.success && res.data.data) {
      const d = res.data.data!
      result.value = d
      statusData.value = { status: 'done', scan_time: d.scan_time, date: d.date }
      ElMessage.success(`扫描完成: ${result.value.top_stocks?.length || 0} 只信号`)
    } else if (res.data?.data?.status === 'running') {
      await pollStatusUntilDone()
      await loadAll()
      ElMessage.success('扫描完成')
    } else {
      ElMessage.error('扫描失败')
    }
  } catch {
    await pollStatusUntilDone()
    await loadAll()
    if (result.value) {
      ElMessage.success('扫描完成')
    } else {
      ElMessage.error('扫描请求异常')
    }
  }
  scanLoading.value = false
}

onMounted(() => {
  loadStatus()
  loadAll()
})

onUnmounted(() => {
  if (pollTimer) clearInterval(pollTimer)
  if (intradayTimer) clearInterval(intradayTimer)
})
</script>

<style scoped>
.ar-page { padding: 16px; max-width: 1200px; margin: 0 auto; }
.ar-head { margin-bottom: 12px; }
.ar-head-row { display: flex; align-items: center; gap: 10px; }
.ar-title { font-size: 18px; font-weight: bold; }
.ar-error { color: var(--el-color-danger); font-size: 13px; margin-top: 6px; }
.ar-tabs { margin-bottom: 12px; }
.ar-summary-card { margin-bottom: 12px; background: linear-gradient(135deg, #667eea33, #764ba233); }
.ar-summary { font-size: 14px; line-height: 1.6; padding: 4px 0; }
.ar-card { margin-bottom: 12px; }
.ar-card :deep(.el-card__header) { display: flex; align-items: center; justify-content: space-between; font-weight: bold; font-size: 14px; padding: 10px 16px; }
.ar-scan-info { font-size: 12px; font-weight: normal; color: var(--text-secondary, var(--text-muted)); }
.ar-sector-grid { display: flex; flex-wrap: wrap; gap: 8px; }
.ar-sector-item { display: flex; align-items: center; gap: 8px; padding: 6px 12px; background: var(--bg-page, #f5f7fa); border-radius: 6px; font-size: 13px; }
.ar-si-name { font-weight: bold; min-width: 60px; }
.ar-si-leader { color: var(--text-secondary, var(--text-muted)); }
.ar-si-score { color: var(--el-color-warning); font-weight: bold; margin-left: auto; }
.ar-trap-card { border-left: 3px solid var(--el-color-warning); }
.ar-trap-item { display: flex; align-items: center; gap: 8px; padding: 6px 0; border-bottom: 1px solid var(--border-color, #ebeef5); font-size: 13px; }
.ar-trap-item:last-child { border-bottom: none; }
.ar-trap-code { font-weight: bold; min-width: 100px; }
.ar-trap-reason { color: var(--text-secondary, var(--text-muted)); }
.ar-gap-up { color: var(--el-color-danger); font-weight: bold; }
.ar-gap-down { color: var(--el-color-success); font-weight: bold; }
.ar-text-muted { color: var(--text-secondary, var(--text-muted)); }

/* Performance cards */
.ar-perf-grid { display: flex; gap: 12px; flex-wrap: wrap; }
.ar-perf-card { flex: 1; min-width: 160px; padding: 16px; border-radius: 8px; text-align: center; }
.ar-perf-good { background: var(--el-color-success-light-9); border: 1px solid var(--el-color-success-light-5); }
.ar-perf-mid { background: var(--el-color-warning-light-9); border: 1px solid var(--el-color-warning-light-5); }
.ar-perf-bad { background: var(--el-color-danger-light-9); border: 1px solid var(--el-color-danger-light-5); }
.ar-perf-bracket { font-size: 14px; font-weight: bold; margin-bottom: 8px; }
.ar-perf-stat { font-size: 12px; margin: 4px 0; color: var(--text-secondary, #555); }

/* Risk dashboard */
.ar-loading { text-align: center; padding: 40px; color: var(--text-muted); }
.ar-risk-grid { display: flex; gap: 12px; flex-wrap: wrap; margin-bottom: 12px; }
.ar-risk-card { flex: 1; min-width: 140px; padding: 16px; border-radius: 8px; text-align: center; background: var(--bg-soft); border: 1px solid var(--border-color); }
.ar-risk-card-green { background: var(--el-color-success-light-9); border-color: var(--el-color-success-light-5); }
.ar-risk-card-orange { background: var(--el-color-warning-light-9); border-color: var(--el-color-warning-light-5); }
.ar-risk-card-blue { background: var(--el-color-primary-light-9); border-color: var(--el-color-primary-light-5); }
.ar-risk-label { font-size: 12px; color: var(--text-secondary, var(--text-muted)); margin-bottom: 4px; }
.ar-risk-value { font-size: 20px; font-weight: bold; }
.ar-risk-sub { font-size: 11px; font-weight: normal; color: var(--text-secondary, var(--text-muted)); }
.ar-sector-exposure { display: flex; flex-direction: column; gap: 8px; }
.ar-sector-bar-item { display: flex; align-items: center; gap: 12px; }
.ar-se-label { min-width: 60px; font-weight: bold; font-size: 13px; }
.ar-sector-bar-item :deep(.el-progress) { flex: 1; }
</style>
