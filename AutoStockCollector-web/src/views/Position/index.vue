<template>
  <div class="paper-trading">
    <!-- 顶部账户概览 -->
    <el-card shadow="never" class="account-bar" v-loading="accountLoading">
      <div class="account-overview" v-if="account">
        <div class="account-stat">
          <div class="stat-label">初始资金</div>
          <div class="stat-value">{{ formatAmount(account.initial_capital) }}</div>
        </div>
        <div class="account-stat">
          <div class="stat-label">当前现金</div>
          <div class="stat-value">{{ formatAmount(account.cash_balance) }}</div>
        </div>
        <div class="account-stat">
          <div class="stat-label">持仓市值</div>
          <div class="stat-value text-primary">{{ formatAmount(totalMarketValue) }}</div>
        </div>
        <div class="account-stat">
          <div class="stat-label">账户净值</div>
          <div class="stat-value" :class="totalReturn >= 0 ? 'text-rise' : 'text-fall'">
            {{ formatAmount(account.cash_balance + totalMarketValue) }}
          </div>
        </div>
        <div class="account-stat">
          <div class="stat-label">总收益率</div>
          <div class="stat-value" :class="totalReturn >= 0 ? 'text-rise' : 'text-fall'">
            {{ formatPercent(totalReturn) }}
          </div>
        </div>
        <el-button size="small" @click="showInitDialog = true">初始化账户</el-button>
      </div>
      <div v-else class="no-account">
        <span>尚未初始化账户</span>
        <el-button type="primary" size="small" @click="showInitDialog = true">立即初始化</el-button>
      </div>
    </el-card>

    <el-row :gutter="16" style="margin-top: 12px">
      <!-- 左侧：持仓表 -->
      <el-col :span="16">
        <el-card shadow="never" class="section-card">
          <template #header>
            <div class="card-header">
              <span>当前持仓</span>
              <el-button type="primary" size="small" @click="showBuyDialog = true">
                手动买入
              </el-button>
            </div>
          </template>
          <el-table :data="positions" stripe size="small" v-loading="posLoading">
            <el-table-column prop="code" label="代码" width="100" align="center">
              <template #default="{ row }">
                <router-link :to="`/stock-detail?code=${row.code}`" class="stock-link">
                  {{ row.code }}
                </router-link>
              </template>
            </el-table-column>
            <el-table-column prop="name" label="名称" min-width="90" align="center" show-overflow-tooltip />
            <el-table-column prop="shares" label="持仓量" width="80" align="center" />
            <el-table-column label="成本价" width="80" align="center">
              <template #default="{ row }">{{ row.avg_cost.toFixed(2) }}</template>
            </el-table-column>
            <el-table-column label="现价" width="80" align="center">
              <template #default="{ row }">{{ row.current_price.toFixed(2) }}</template>
            </el-table-column>
            <el-table-column label="市值" width="90" align="center">
              <template #default="{ row }">{{ formatAmount(row.market_value) }}</template>
            </el-table-column>
            <el-table-column label="盈亏%" width="90" align="center">
              <template #default="{ row }">
                <span :class="row.pnl_percent >= 0 ? 'text-rise' : 'text-fall'">
                  {{ formatPercent(row.pnl_percent) }}
                </span>
              </template>
            </el-table-column>
            <el-table-column label="占比" width="70" align="center">
              <template #default="{ row }">{{ row.position_ratio.toFixed(1) }}%</template>
            </el-table-column>
            <el-table-column label="操作" width="140" align="center">
              <template #default="{ row }">
                <el-button type="primary" size="small" text @click="fetchAiAdvice(row, 'buy')">
                  AI 建议
                </el-button>
                <el-button type="warning" size="small" text @click="openManualSell(row)">
                  卖出
                </el-button>
              </template>
            </el-table-column>
          </el-table>
          <el-empty v-if="!posLoading && positions.length === 0" description="暂无持仓" :image-size="60" />
        </el-card>
      </el-col>

      <!-- 右侧：统计卡片 -->
      <el-col :span="8">
        <el-card shadow="never" class="section-card">
          <template #header><span>净值曲线</span></template>
          <ProfitChart :data="navChartData" title="" chart-height="200px" />
        </el-card>

        <el-card shadow="never" class="section-card" style="margin-top: 12px">
          <template #header><span>回测统计</span></template>
          <el-descriptions :column="2" border size="small">
            <el-descriptions-item label="总交易次数">{{ stats.total_trades }}</el-descriptions-item>
            <el-descriptions-item label="胜率">
              <span :class="stats.win_rate >= 50 ? 'text-rise' : 'text-fall'">
                {{ stats.win_rate.toFixed(1) }}%
              </span>
            </el-descriptions-item>
            <el-descriptions-item label="平均盈利">
              <span class="text-rise">+{{ stats.avg_profit_pct.toFixed(2) }}%</span>
            </el-descriptions-item>
            <el-descriptions-item label="平均亏损">
              <span class="text-fall">{{ stats.avg_loss_pct.toFixed(2) }}%</span>
            </el-descriptions-item>
            <el-descriptions-item label="盈亏比" :span="2">{{ stats.profit_factor.toFixed(2) }}</el-descriptions-item>
          </el-descriptions>
        </el-card>

        <el-card shadow="never" class="section-card" style="margin-top: 12px">
          <template #header><span>最近交易</span></template>
          <div class="trade-list">
            <div v-for="t in recentTrades" :key="t.traded_at" class="trade-item">
              <div class="trade-header">
                <span class="trade-code">{{ t.code }} {{ t.name }}</span>
                <el-tag size="small" :type="t.action === 'buy' ? 'success' : 'danger'">
                  {{ t.action === 'buy' ? '买入' : '卖出' }}
                </el-tag>
              </div>
              <div class="trade-detail">
                {{ t.shares }} 股 @ {{ t.price.toFixed(2) }}
                <span class="trade-time">{{ t.traded_at.slice(0, 10) }}</span>
              </div>
              <div v-if="t.ai_signal?.action" class="trade-signal">
                AI: {{ t.ai_signal.action }}
              </div>
            </div>
            <el-empty v-if="recentTrades.length === 0" description="暂无记录" :image-size="40" />
          </div>
        </el-card>

        <el-card shadow="never" class="section-card" style="margin-top: 12px">
          <template #header><span>持仓分布</span></template>
          <div v-if="positions.length > 0" class="distribution-chart">
            <div v-for="p in positions" :key="p.code" class="distribution-item">
              <div class="dist-info">
                <span class="dist-label">{{ p.code }}</span>
                <span class="dist-percent">{{ p.position_ratio.toFixed(1) }}%</span>
              </div>
              <div class="dist-bar-container">
                <div class="dist-bar" :style="{ width: p.position_ratio + '%' }" />
              </div>
            </div>
          </div>
          <el-empty v-else description="暂无数据" :image-size="40" />
        </el-card>
      </el-col>
    </el-row>

    <!-- 初始化账户对话框 -->
    <el-dialog v-model="showInitDialog" title="初始化模拟账户" width="400px">
      <el-form label-width="100px">
        <el-form-item label="初始资金">
          <el-input-number v-model="initCapital" :min="1000" :step="10000" style="width: 100%" />
        </el-form-item>
        <div class="dialog-warn">注意：初始化将清空所有交易记录和持仓！</div>
      </el-form>
      <template #footer>
        <el-button @click="showInitDialog = false">取消</el-button>
        <el-button type="primary" :loading="initLoading" @click="doInitAccount">确认初始化</el-button>
      </template>
    </el-dialog>

    <!-- 手动买入对话框 -->
    <el-dialog v-model="showBuyDialog" title="手动买入" width="420px">
      <el-form label-width="100px">
        <el-form-item label="股票代码">
          <el-input v-model="buyForm.code" placeholder="如 SH600000" />
        </el-form-item>
        <el-form-item label="买入数量">
          <el-input-number v-model="buyForm.shares" :min="100" :step="100" style="width: 100%" />
        </el-form-item>
        <div class="dialog-info" v-if="account">可用现金：{{ formatAmount(account.cash_balance) }}</div>
      </el-form>
      <template #footer>
        <el-button @click="showBuyDialog = false">取消</el-button>
        <el-button type="primary" :loading="tradeLoading" @click="doManualBuy">确认买入</el-button>
      </template>
    </el-dialog>

    <!-- AI 买入确认框 -->
    <el-dialog v-model="showAiBuyDialog" title="AI 买入建议" width="480px">
      <div class="ai-advice-panel" v-if="aiAdvice">
        <div class="advice-row">
          <span class="advice-label">建议操作</span>
          <el-tag type="success">{{ aiAdvice.action }}</el-tag>
        </div>
        <div class="advice-row" v-if="aiAdvice.reason">
          <span class="advice-label">理由</span>
          <span class="advice-text">{{ aiAdvice.reason }}</span>
        </div>
        <div class="advice-row" v-if="aiAdvice.buy_zone">
          <span class="advice-label">参考区间</span>
          <span class="advice-text">{{ aiAdvice.buy_zone }}</span>
        </div>
        <el-divider />
        <el-form label-width="100px">
          <el-form-item label="当前价">{{ tradeTarget?.current_price?.toFixed(2) ?? '—' }}</el-form-item>
          <el-form-item label="可用现金">{{ formatAmount(account?.cash_balance ?? 0) }}</el-form-item>
          <el-form-item label="买入数量">
            <el-input-number v-model="tradeShares" :min="100" :step="100" style="width: 100%" />
          </el-form-item>
          <el-form-item label="预计金额">
            <span class="text-primary">
              {{ formatAmount((tradeTarget?.current_price ?? 0) * tradeShares) }}
            </span>
          </el-form-item>
        </el-form>
      </div>
      <template #footer>
        <el-button @click="showAiBuyDialog = false">取消</el-button>
        <el-button type="primary" :loading="tradeLoading" @click="doAiTrade('buy')">确认买入</el-button>
      </template>
    </el-dialog>

    <!-- AI 卖出 / 手动卖出确认框 -->
    <el-dialog v-model="showSellDialog" :title="aiAdvice ? 'AI 卖出建议' : '卖出确认'" width="480px">
      <div class="ai-advice-panel" v-if="aiAdvice">
        <div class="advice-row">
          <span class="advice-label">建议操作</span>
          <el-tag type="danger">{{ aiAdvice.action }}</el-tag>
        </div>
        <div class="advice-row" v-if="aiAdvice.reason">
          <span class="advice-label">理由</span>
          <span class="advice-text">{{ aiAdvice.reason }}</span>
        </div>
        <el-divider />
      </div>
      <el-form label-width="100px">
        <el-form-item label="股票">{{ tradeTarget?.code }} {{ tradeTarget?.name }}</el-form-item>
        <el-form-item label="当前持仓">{{ tradeTarget?.shares }} 股</el-form-item>
        <el-form-item label="当前价">{{ tradeTarget?.current_price?.toFixed(2) ?? '—' }}</el-form-item>
        <el-form-item label="卖出数量">
          <el-input-number
            v-model="tradeShares"
            :min="100"
            :max="tradeTarget?.shares ?? 0"
            :step="100"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="预计回收">
          <span class="text-primary">
            {{ formatAmount((tradeTarget?.current_price ?? 0) * tradeShares) }}
          </span>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showSellDialog = false">取消</el-button>
        <el-button type="danger" :loading="tradeLoading" @click="doAiTrade('sell')">确认卖出</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { paperApi, type PaperAccount, type PaperPosition, type TradeRecord, type PaperStats, type NavPoint, type AiSignal } from '@/api/paper'
import ProfitChart from '@/components/ProfitChart/index.vue'

const accountLoading = ref(false)
const posLoading = ref(false)
const initLoading = ref(false)
const tradeLoading = ref(false)
const aiLoading = ref(false)

const account = ref<PaperAccount | null>(null)
const positions = ref<PaperPosition[]>([])
const recentTrades = ref<TradeRecord[]>([])
const stats = ref<PaperStats>({
  total_trades: 0, win_trades: 0, loss_trades: 0,
  win_rate: 0, avg_profit_pct: 0, avg_loss_pct: 0, profit_factor: 0,
})
const navData = ref<NavPoint[]>([])

const showInitDialog = ref(false)
const showBuyDialog = ref(false)
const showAiBuyDialog = ref(false)
const showSellDialog = ref(false)

const initCapital = ref(100000)
const buyForm = ref({ code: '', shares: 100 })
const tradeTarget = ref<PaperPosition | null>(null)
const tradeShares = ref(100)
const aiAdvice = ref<AiSignal | null>(null)

const totalMarketValue = computed(() =>
  positions.value.reduce((s, p) => s + p.market_value, 0)
)

const totalReturn = computed(() => {
  if (!account.value || account.value.initial_capital === 0) return 0
  const netValue = account.value.cash_balance + totalMarketValue.value
  return (netValue - account.value.initial_capital) / account.value.initial_capital * 100
})

const navChartData = computed(() =>
  navData.value.map(n => ({ date: n.date, value: n.nav * (account.value?.initial_capital ?? 100000), cost: account.value?.initial_capital ?? 100000 }))
)

function formatAmount(v: number): string {
  if (Math.abs(v) >= 1e8) return (v / 1e8).toFixed(2) + '亿'
  if (Math.abs(v) >= 1e4) return (v / 1e4).toFixed(2) + '万'
  return v.toFixed(2)
}

function formatPercent(v: number): string {
  return (v >= 0 ? '+' : '') + v.toFixed(2) + '%'
}

async function loadAll() {
  accountLoading.value = true
  posLoading.value = true
  try {
    const [acct, pos, trades, st, nav] = await Promise.all([
      paperApi.getAccount(),
      paperApi.getPositions(),
      paperApi.getTrades(10),
      paperApi.getStats(),
      paperApi.getNav(),
    ])
    account.value = acct
    positions.value = pos
    recentTrades.value = trades
    stats.value = st
    navData.value = nav
  } finally {
    accountLoading.value = false
    posLoading.value = false
  }
}

async function doInitAccount() {
  if (initCapital.value <= 0) return
  try {
    await ElMessageBox.confirm(
      `确认将模拟账户初始资金设为 ${formatAmount(initCapital.value)}？所有持仓和交易记录将被清空！`,
      '初始化确认',
      { confirmButtonText: '确认', cancelButtonText: '取消', type: 'warning' }
    )
  } catch {
    return
  }
  initLoading.value = true
  try {
    await paperApi.initAccount(initCapital.value)
    ElMessage.success('账户初始化成功')
    showInitDialog.value = false
    loadAll()
  } catch {
    ElMessage.error('初始化失败')
  } finally {
    initLoading.value = false
  }
}

async function fetchAiAdvice(pos: PaperPosition, intent: 'buy' | 'sell') {
  aiAdvice.value = null
  tradeTarget.value = pos
  aiLoading.value = true

  // 默认买入数量：按可用现金 20% 估算
  if (intent === 'buy' && account.value) {
    const budget = account.value.cash_balance * 0.2
    const estimatedShares = Math.floor(budget / (pos.current_price || 1) / 100) * 100
    tradeShares.value = Math.max(100, estimatedShares)
  } else if (intent === 'sell') {
    tradeShares.value = Math.floor(pos.shares * 0.5 / 100) * 100 || 100
  }

  try {
    const advice = await paperApi.getAiAdvice(pos.code, pos.avg_cost, pos.position_ratio / 100)
    aiAdvice.value = advice

    const actionLower = (advice.action ?? '').toLowerCase()
    const isSellSignal = actionLower.includes('卖') || actionLower.includes('减仓') || actionLower.includes('清仓') ||
      actionLower.includes('sell') || actionLower.includes('reduce')

    // 尝试解析 position_advice 中的卖出比例
    if (intent === 'sell' && advice.position_advice) {
      const match = advice.position_advice.match(/(\d+)\s*%/)
      if (match) {
        const ratio = parseInt(match[1]) / 100
        tradeShares.value = Math.max(100, Math.floor(pos.shares * ratio / 100) * 100)
      }
    }

    if (isSellSignal || intent === 'sell') {
      showSellDialog.value = true
    } else {
      showAiBuyDialog.value = true
    }
  } catch {
    ElMessage.error('获取 AI 建议失败')
  } finally {
    aiLoading.value = false
  }
}

function openManualSell(pos: PaperPosition) {
  tradeTarget.value = pos
  aiAdvice.value = null
  tradeShares.value = pos.shares
  showSellDialog.value = true
}

async function doManualBuy() {
  if (!buyForm.value.code || buyForm.value.shares <= 0) {
    ElMessage.warning('请填写股票代码和数量')
    return
  }
  tradeLoading.value = true
  try {
    await paperApi.executeTrade({ code: buyForm.value.code, action: 'buy', shares: buyForm.value.shares })
    ElMessage.success('买入成功')
    showBuyDialog.value = false
    buyForm.value = { code: '', shares: 100 }
    loadAll()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.error ?? '买入失败')
  } finally {
    tradeLoading.value = false
  }
}

async function doAiTrade(action: 'buy' | 'sell') {
  if (!tradeTarget.value || tradeShares.value <= 0) return
  tradeLoading.value = true
  try {
    await paperApi.executeTrade({
      code: tradeTarget.value.code,
      action,
      shares: tradeShares.value,
      ai_signal: aiAdvice.value ?? undefined,
    })
    ElMessage.success(action === 'buy' ? '买入成功' : '卖出成功')
    showAiBuyDialog.value = false
    showSellDialog.value = false
    loadAll()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.error ?? '交易失败')
  } finally {
    tradeLoading.value = false
  }
}

onMounted(loadAll)
</script>

<style scoped>
.paper-trading { display: flex; flex-direction: column; gap: 0; }

.account-bar { background: #1f1f1f; border: 1px solid #2c2c2c; }
.account-overview { display: flex; align-items: center; gap: 32px; flex-wrap: wrap; }
.account-stat { display: flex; flex-direction: column; gap: 4px; }
.stat-label { font-size: 12px; color: #909399; }
.stat-value { font-size: 16px; font-weight: 600; color: #e5eaf3; }
.no-account { display: flex; align-items: center; gap: 12px; color: #909399; }

.section-card { background: #1f1f1f; border: 1px solid #2c2c2c; }
.section-card :deep(.el-card__header) {
  border-bottom: 1px solid #2c2c2c; padding: 12px 16px;
  color: #e5eaf3; font-size: 14px; font-weight: 600;
}
.card-header { display: flex; justify-content: space-between; align-items: center; }

.stock-link { color: #409eff; text-decoration: none; }
.stock-link:hover { text-decoration: underline; }

.text-rise { color: #ef5350; }
.text-fall { color: #26a69a; }
.text-primary { color: #409eff; }

.trade-list { display: flex; flex-direction: column; gap: 8px; max-height: 240px; overflow-y: auto; }
.trade-item { padding: 8px 10px; background: #2c2c2c; border-radius: 4px; }
.trade-header { display: flex; justify-content: space-between; align-items: center; }
.trade-code { font-size: 13px; font-weight: 600; color: #e5eaf3; }
.trade-detail { font-size: 12px; color: #909399; margin-top: 4px; display: flex; justify-content: space-between; }
.trade-time { color: #606266; }
.trade-signal { font-size: 11px; color: #e6a23c; margin-top: 2px; }

.distribution-chart { display: flex; flex-direction: column; gap: 8px; }
.distribution-item { display: flex; flex-direction: column; gap: 4px; }
.dist-info { display: flex; justify-content: space-between; font-size: 12px; }
.dist-label { color: #e5eaf3; }
.dist-percent { color: #909399; }
.dist-bar-container { height: 6px; background: #2c2c2c; border-radius: 3px; overflow: hidden; }
.dist-bar { height: 100%; background: #409eff; border-radius: 3px; transition: width 0.3s ease; }

.ai-advice-panel { margin-bottom: 8px; }
.advice-row { display: flex; align-items: flex-start; gap: 12px; margin-bottom: 8px; }
.advice-label { font-size: 12px; color: #909399; min-width: 60px; padding-top: 2px; }
.advice-text { font-size: 13px; color: #e5eaf3; line-height: 1.5; }

.dialog-warn { color: #f56c6c; font-size: 12px; margin-top: 8px; padding-left: 100px; }
.dialog-info { color: #909399; font-size: 12px; margin-top: 4px; padding-left: 100px; }
</style>
