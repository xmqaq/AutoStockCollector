<template>
  <div class="paper-trading">
    <!-- 顶部账户概览 -->
    <AccountOverview
      :account="account"
      :loading="accountLoading"
      :is-trading-time="isTradingTime"
      :net-value="netValue"
      :total-market-value="totalMarketValue"
      :total-pnl-amount="totalPnlAmount"
      :total-return="totalReturn"
      @init="showInitDialog = true"
      @deposit="openDepositDialog"
    />

    <!-- 中部主交易区：持仓表占据整行，防止横向溢出 -->
    <el-row :gutter="20" style="margin-top: 20px">
      <el-col :span="24">
        <PositionTable
          :positions="positions"
          :loading="posLoading"
          @buy="openBuyDialog"
          @sell="openSellDialog"
        />
      </el-col>
    </el-row>

    <!-- 底部数据分析区：三列等分布局，解决高度不一产生的留白 -->
    <el-row :gutter="20" style="margin-top: 20px; display: flex; align-items: stretch;">
      
      <!-- 左列：净值图 + 持仓分布 -->
      <el-col :span="8" class="flex-col">
        <el-card shadow="never" class="pro-card nav-chart-card">
          <template #header><span class="card-title">净值曲线</span></template>
          <ProfitChart :data="navChartData" title="" chart-height="220px" />
        </el-card>
        <PositionDistribution :positions="positions" style="margin-top: 20px; flex: 1;" />
      </el-col>

      <!-- 中列：各类浮盈/平仓统计 -->
      <el-col :span="8" class="flex-col">
        <FloatingStats :floating-stats="floatingStats" />
        <TradingStats :stats="stats" style="margin-top: 20px; flex: 1;" />
      </el-col>

      <!-- 右列：最近交易流 -->
      <el-col :span="8" class="flex-col">
        <RecentTrades :recent-trades="recentTrades" style="height: 100%;" />
      </el-col>

    </el-row>

    <!-- 对话框 -->
    <InitDialog
      v-model:visible="showInitDialog"
      :loading="initLoading"
      @confirm="doInitAccount"
    />

    <DepositDialog
      v-model:visible="showDepositDialog"
      :loading="depositLoading"
      @confirm="doDeposit"
    />

    <BuyDialog
      v-model:visible="showBuyDialog"
      :initial-target="buyTargetPosition"
      :account="account"
      :net-value="netValue"
      :positions="positions"
      @success="loadAll"
    />

    <SellDialog
      v-model:visible="showSellDialog"
      :target="sellTarget"
      @success="loadAll"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { paperApi, type PaperAccount, type PaperPosition, type TradeRecord, type PaperStats, type NavPoint } from '@/api/paper'
import ProfitChart from '@/components/ProfitChart/index.vue'
import AccountOverview from './components/AccountOverview.vue'
import PositionTable from './components/PositionTable.vue'
import TradingStats from './components/TradingStats.vue'
import RecentTrades from './components/RecentTrades.vue'
import FloatingStats from './components/FloatingStats.vue'
import PositionDistribution from './components/PositionDistribution.vue'
import InitDialog from './components/InitDialog.vue'
import DepositDialog from './components/DepositDialog.vue'
import BuyDialog from './components/BuyDialog.vue'
import SellDialog from './components/SellDialog.vue'
import { formatAmount, formatPercent, pnlColorClass } from './utils'

const REFRESH_INTERVAL = 30000

const accountLoading = ref(false)
const posLoading = ref(false)
const initLoading = ref(false)
const tradeLoading = ref(false)

const account = ref<PaperAccount | null>(null)
const positions = ref<PaperPosition[]>([])
const recentTrades = ref<TradeRecord[]>([])
const stats = ref<PaperStats>({
  total_trades: 0, win_trades: 0, loss_trades: 0,
  win_rate: 0, avg_profit_pct: 0, avg_loss_pct: 0, profit_factor: 0,
})
const navData = ref<NavPoint[]>([])
const isTradingTime = ref(false)

const showInitDialog = ref(false)
const showBuyDialog = ref(false)
const showSellDialog = ref(false)

const showDepositDialog = ref(false)
const depositLoading = ref(false)

let refreshTimer: ReturnType<typeof setInterval> | null = null

// --- computed ---
const totalMarketValue = computed(() =>
  positions.value.reduce((s, p) => s + p.market_value, 0)
)

const netValue = computed(() =>
  (account.value?.cash_balance ?? 0) + totalMarketValue.value
)

const totalPnlAmount = computed(() =>
  netValue.value - (account.value?.initial_capital ?? 0)
)

const totalReturn = computed(() => {
  if (!account.value || account.value.initial_capital === 0) return 0
  return totalPnlAmount.value / account.value.initial_capital * 100
})

const floatingStats = computed(() => {
  const list = positions.value
  const winning = list.filter(p => p.pnl_percent > 0)
  const losing = list.filter(p => p.pnl_percent < 0)
  const maxWin = winning.reduce<PaperPosition | null>(
    (m, p) => (!m || p.pnl_percent > m.pnl_percent ? p : m), null)
  const maxLoss = losing.reduce<PaperPosition | null>(
    (m, p) => (!m || p.pnl_percent < m.pnl_percent ? p : m), null)
  return {
    count: list.length,
    winning: winning.length,
    losing: losing.length,
    maxWin,
    maxLoss,
  }
})

const navChartData = computed(() =>
  navData.value.map(n => {
    const initial = n.initial_capital ?? account.value?.initial_capital ?? 100000
    const netVal = n.net_value ?? (n.nav ? n.nav * initial : n.cash)
    return {
      date: n.date,
      value: netVal,
      cost: initial,
      profit_amount: n.profit_amount ?? (netVal - initial),
      profit_pct: n.profit_pct ?? ((netVal - initial) / initial * 100),
    }
  })
)

const buyTargetPosition = ref<PaperPosition | null>(null)
const sellTarget = ref<PaperPosition | null>(null)

// --- data loading ---
async function loadAll() {
  accountLoading.value = true
  posLoading.value = true
  try {
    const [posResult, acct, trades, st, nav] = await Promise.all([
      paperApi.getPositions(),
      paperApi.getAccount(),
      paperApi.getTrades(10),
      paperApi.getStats(),
      paperApi.getNav(),
    ])
    positions.value = posResult.positions
    isTradingTime.value = posResult.is_trading_time
    account.value = acct
    recentTrades.value = trades
    stats.value = st
    navData.value = nav
  } finally {
    accountLoading.value = false
    posLoading.value = false
  }
  setupAutoRefresh()
}

async function refreshPositions() {
  try {
    const posResult = await paperApi.getPositions()
    positions.value = posResult.positions
    isTradingTime.value = posResult.is_trading_time
    const acct = await paperApi.getAccount()
    account.value = acct
  } catch {
    // silent
  }
  if (!isTradingTime.value && refreshTimer) {
    clearInterval(refreshTimer)
    refreshTimer = null
  }
}

function setupAutoRefresh() {
  if (refreshTimer) {
    clearInterval(refreshTimer)
    refreshTimer = null
  }
  if (isTradingTime.value) {
    refreshTimer = setInterval(refreshPositions, REFRESH_INTERVAL)
  }
}

// --- account init ---
async function doInitAccount(capital: number) {
  initLoading.value = true
  try {
    await paperApi.initAccount(capital)
    ElMessage.success('账户初始化成功')
    showInitDialog.value = false
    loadAll()
  } catch {
    ElMessage.error('初始化失败')
  } finally {
    initLoading.value = false
  }
}

// --- deposit / withdraw ---
function openDepositDialog() {
  showDepositDialog.value = true
}

async function doDeposit(signedAmount: number) {
  depositLoading.value = true
  try {
    await paperApi.depositAccount(signedAmount)
    ElMessage.success(signedAmount > 0 ? '入金成功' : '出金成功')
    showDepositDialog.value = false
    loadAll()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.error || '操作失败')
  } finally {
    depositLoading.value = false
  }
}

// --- buy ---
function openBuyDialog(pos?: PaperPosition) {
  buyTargetPosition.value = pos ?? null
  showBuyDialog.value = true
}

// --- sell ---
function openSellDialog(pos: PaperPosition) {
  sellTarget.value = pos
  showSellDialog.value = true
}

onMounted(loadAll)
onUnmounted(() => {
  if (refreshTimer) clearInterval(refreshTimer)
})
</script>

<style scoped>
.paper-trading { 
  display: flex; 
  flex-direction: column; 
  background-color: var(--bg-body, #f5f7fa);
  min-height: 100vh;
}

.pro-card {
  background: var(--bg-card, #ffffff);
  border: 1px solid var(--border-color, #ebeef5);
  border-radius: 8px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.02);
}

.pro-card :deep(.el-card__header) {
  border-bottom: 1px solid var(--border-color, #ebeef5);
  padding: 16px 20px;
  background-color: rgba(0,0,0,0.01);
}

.card-title {
  color: var(--text-primary);
  font-size: 15px;
  font-weight: 600;
  display: flex;
  align-items: center;
}

.card-title::before {
  content: '';
  display: inline-block;
  width: 4px;
  height: 16px;
  background: var(--el-color-primary);
  border-radius: 2px;
  margin-right: 8px;
}

.nav-chart-card :deep(.el-card__body) {
  padding: 12px 20px 20px;
}

.flex-col {
  display: flex;
  flex-direction: column;
}

/* 对话框共有样式 */
.dialog-warn { margin-top: 16px; color: var(--el-color-danger); font-size: 13px; padding: 8px 12px; background: var(--el-color-danger-light-9); border-radius: 4px; }
.dialog-hint { margin-top: 16px; color: var(--text-muted); font-size: 13px; line-height: 1.5; padding: 8px 12px; background: var(--bg-body); border-radius: 4px; }

.trade-dialog-header { padding: 12px 16px; background: var(--bg-soft); border-radius: 6px; margin-bottom: 20px; font-size: 14px; display: flex; flex-direction: column; gap: 6px; }
.price-loading { color: var(--text-muted); font-style: italic; }
.indicator-live-text { color: var(--el-color-success); font-size: 12px; font-weight: 600; }
.indicator-close-text { color: var(--text-muted); font-size: 12px; }

.form-hint { font-size: 12px; color: var(--text-muted); margin-top: 6px; line-height: 1.4; }
.form-hint-buttons { margin-top: 8px; display: flex; gap: 8px; }

.confirm-block { background: var(--bg-body); padding: 12px 16px; border-radius: 6px; font-size: 13px; display: flex; flex-direction: column; gap: 8px; }
.confirm-row { display: flex; justify-content: space-between; align-items: center; }
.confirm-row span:first-child { color: var(--text-muted); }
.confirm-row span:last-child { font-weight: 500; color: var(--text-primary); }
.confirm-row-danger span:last-child { color: var(--el-color-danger); }

.cash-warning { margin-top: 8px; padding-top: 12px; border-top: 1px dashed var(--border-color); display: flex; flex-direction: column; gap: 4px; }
.cash-warning-text { color: var(--el-color-warning); font-size: 13px; display: flex; align-items: center; gap: 4px; }
.cash-warning-hint { font-size: 12px; color: var(--text-muted); margin-left: 18px; }
.max-buy-link { color: var(--el-color-primary); cursor: pointer; text-decoration: underline; font-weight: 500; }
.max-buy-link:hover { opacity: 0.8; }
.text-fall { color: #26a69a; }
</style>
