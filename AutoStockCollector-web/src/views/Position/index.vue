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
          <div class="stat-value" :class="pnlColorClass(netValue - account.initial_capital)">
            {{ formatAmount(netValue) }}
          </div>
        </div>
        <div class="account-stat">
          <div class="stat-label">总盈亏</div>
          <div class="stat-value" :class="pnlColorClass(totalPnlAmount)">
            {{ totalPnlAmount >= 0 ? '+' : '' }}{{ formatAmount(totalPnlAmount) }}
          </div>
        </div>
        <div class="account-stat">
          <div class="stat-label">总收益率</div>
          <div class="stat-value" :class="pnlColorClass(totalReturn)">
            {{ formatPercent(totalReturn) }}
          </div>
        </div>
        <div class="price-indicator">
          <span v-if="isTradingTime" class="indicator-dot indicator-live" />
          <span v-else class="indicator-dot indicator-close" />
          <span class="indicator-text">{{ isTradingTime ? '实时价格' : '昨日收盘价' }}</span>
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
              <el-button type="primary" size="small" @click="openBuyDialog()">
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
            <el-table-column prop="name" label="名称" min-width="80" align="center" show-overflow-tooltip />
            <el-table-column prop="shares" label="持仓量" width="75" align="center" />
            <el-table-column label="成本价" width="75" align="center">
              <template #default="{ row }">{{ row.avg_cost.toFixed(2) }}</template>
            </el-table-column>
            <el-table-column label="现价" width="75" align="center">
              <template #default="{ row }">
                <span :class="pnlColorClass(row.current_price - row.avg_cost)">
                  {{ row.current_price.toFixed(2) }}
                </span>
              </template>
            </el-table-column>
            <el-table-column label="市值" width="85" align="center">
              <template #default="{ row }">{{ formatAmount(row.market_value) }}</template>
            </el-table-column>
            <el-table-column label="盈亏%" width="80" align="center">
              <template #default="{ row }">
                <span :class="pnlColorClass(row.pnl_percent)">
                  {{ formatPercent(row.pnl_percent) }}
                </span>
              </template>
            </el-table-column>
            <el-table-column label="今日%" width="80" align="center">
              <template #default="{ row }">
                <span :class="pnlColorClass(row.today_pnl_percent)">
                  {{ formatPercent(row.today_pnl_percent ?? 0) }}
                </span>
              </template>
            </el-table-column>
            <el-table-column label="占比" width="60" align="center">
              <template #default="{ row }">{{ row.position_ratio.toFixed(1) }}%</template>
            </el-table-column>
            <el-table-column label="操作" width="160" align="center">
              <template #default="{ row }">
                <el-button type="primary" size="small" text @click="openBuyDialog(row)">
                  加仓
                </el-button>
                <el-button type="warning" size="small" text @click="openSellDialog(row)">
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

    <!-- 买入对话框（三种模式） -->
    <el-dialog v-model="showBuyDialog" :title="buyDialogTitle" width="520px" @close="resetBuyForm">
      <div class="trade-dialog-header" v-if="buyPriceLoading || buyCurrentPrice || buyPriceError">
        <span v-if="buyPriceLoading" class="price-loading">获取价格中...</span>
        <span v-else-if="buyPriceError" class="text-fall">{{ buyPriceError }}</span>
        <template v-else>
          <span>当前价：<b>{{ buyCurrentPrice!.toFixed(2) }}</b> 元
            <span :class="buyPriceType === 'realtime' ? 'indicator-live-text' : 'indicator-close-text'" style="margin-left: 6px">
              {{ buyPriceType === 'realtime' ? '实时' : '收盘价' }}
            </span>
          </span>
        </template>
      </div>
      <el-form label-width="100px">
        <el-form-item label="股票代码" v-if="!buyTargetPosition">
          <el-input v-model="buyForm.code" placeholder="如 SH600000 或 603979" @blur="onBuyCodeBlur" @keyup.enter="onBuyCodeBlur" />
        </el-form-item>

        <el-form-item label="买入方式">
          <el-radio-group v-model="buyForm.mode" size="small">
            <el-radio-button value="shares">按股数</el-radio-button>
            <el-radio-button value="amount">按金额</el-radio-button>
            <el-radio-button value="ratio">按仓位比例</el-radio-button>
          </el-radio-group>
        </el-form-item>

        <!-- 按股数 -->
        <template v-if="buyForm.mode === 'shares'">
          <el-form-item label="买入数量">
            <el-input-number v-model="buyForm.shares" :min="100" :step="100" style="width: 100%" />
            <div class="form-hint">最小单位 100 股（1手）</div>
          </el-form-item>
        </template>

        <!-- 按金额 -->
        <template v-if="buyForm.mode === 'amount'">
          <el-form-item label="买入金额">
            <el-input-number v-model="buyForm.amount" :min="0" :step="1000" style="width: 100%" />
            <div class="form-hint">
              可用现金：{{ formatAmount(account?.cash_balance ?? 0) }}
              <template v-if="buyCurrentPrice && buyCurrentPrice > 0">
                &nbsp;→ 可买 {{ buyAmountShares }} 股，实际 {{ formatAmount(buyAmountActual) }} 元
              </template>
            </div>
          </el-form-item>
        </template>

        <!-- 按仓位比例 -->
        <template v-if="buyForm.mode === 'ratio'">
          <el-form-item label="目标仓位">
            <el-input-number v-model="buyForm.targetRatio" :min="0" :max="100" :step="5" style="width: 100%">
              <template #append>%</template>
            </el-input-number>
            <div class="form-hint">
              账户净值：{{ formatAmount(netValue) }}
              <template v-if="buyTargetPosition">
                &nbsp;| 当前该股仓位：{{ currentStockRatio.toFixed(1) }}%
              </template>
            </div>
            <div class="form-hint" v-if="buyRatioShares > 0">
              → 目标金额 {{ formatAmount(buyRatioTargetAmount) }}，需买 {{ buyRatioShares }} 股
            </div>
            <div class="form-hint text-fall" v-else-if="buyForm.targetRatio > 0 && buyCurrentPrice">
              当前仓位已达目标，如需减仓请使用卖出功能
            </div>
          </el-form-item>
        </template>

        <!-- 确认信息 -->
        <el-divider v-if="buyConfirmShares > 0">确认信息</el-divider>
        <div class="confirm-block" v-if="buyConfirmShares > 0">
          <template v-if="buyForm.mode === 'ratio'">
            <div class="confirm-row"><span>目标仓位</span><span>{{ buyForm.targetRatio }}%</span></div>
            <div class="confirm-row"><span>目标金额</span><span>{{ formatAmount(buyRatioTargetAmount) }}（净值{{ formatAmount(netValue) }}×{{ buyForm.targetRatio }}%）</span></div>
            <div class="confirm-row" v-if="buyTargetPosition">
              <span>当前持仓</span>
              <span>{{ formatAmount(buyRatioCurrentHolding) }}（{{ buyTargetPosition.shares }}股×{{ buyTargetPosition.current_price.toFixed(2) }}元）</span>
            </div>
            <div class="confirm-row"><span>需买金额</span><span>{{ formatAmount(buyRatioNeedBuyAmount) }}</span></div>
          </template>
          <div class="confirm-row"><span>买入数量</span><span>{{ buyConfirmShares }} 股</span></div>
          <div class="confirm-row"><span>买入金额</span><span>{{ formatAmount(buyConfirmAmount) }}</span></div>
          <div class="confirm-row"><span>预估手续费</span><span>约 {{ buyCommission.toFixed(2) }} 元（万三，最低5元）</span></div>
          <div class="confirm-row" :class="{ 'confirm-row-danger': buyCashInsufficient }">
            <span>买入后现金</span>
            <span :class="{ 'text-fall': buyCashInsufficient }">{{ formatAmount(buyAfterCash) }}</span>
          </div>
          <div class="confirm-row" v-if="buyTargetPosition">
            <span>买入后该股仓位</span>
            <span>{{ buyAfterRatio.toFixed(1) }}%</span>
          </div>
          <div class="cash-warning" v-if="buyCashInsufficient">
            <div class="cash-warning-text"><el-icon style="color: var(--el-color-warning)"><WarningFilled /></el-icon> 可用现金不足，当前现金 {{ formatAmount(account?.cash_balance ?? 0) }}，还需 {{ formatAmount(Math.abs(buyAfterCash)) }}</div>
            <div class="cash-warning-hint" v-if="buyMaxAffordableShares > 0">
              最多可买 <a class="max-buy-link" @click="fillMaxAffordableShares">{{ buyMaxAffordableShares }} 股</a>（{{ formatAmount(buyMaxAffordableShares * (buyCurrentPrice ?? 0)) }}）
            </div>
          </div>
        </div>
      </el-form>
      <template #footer>
        <el-button @click="showBuyDialog = false">取消</el-button>
        <el-button type="primary" :loading="tradeLoading" :disabled="buyConfirmShares <= 0 || buyCashInsufficient" @click="doConfirmBuy">
          确认买入
        </el-button>
      </template>
    </el-dialog>

    <!-- 卖出对话框（三种模式） -->
    <el-dialog v-model="showSellDialog" :title="sellDialogTitle" width="520px" @close="resetSellForm">
      <div class="trade-dialog-header" v-if="sellTarget">
        <div>当前价：<b>{{ sellTarget.current_price.toFixed(2) }}</b> 元 &nbsp; 成本价：{{ sellTarget.avg_cost.toFixed(2) }} 元</div>
        <div>持仓：{{ sellTarget.shares }} 股 &nbsp; 当前盈亏：
          <span :class="pnlColorClass(sellTarget.pnl_percent)">{{ formatPercent(sellTarget.pnl_percent) }}</span>
        </div>
      </div>
      <el-form label-width="100px">
        <el-form-item label="卖出方式">
          <el-radio-group v-model="sellForm.mode" size="small">
            <el-radio-button value="shares">按股数</el-radio-button>
            <el-radio-button value="amount">按金额</el-radio-button>
            <el-radio-button value="ratio">按比例卖出</el-radio-button>
          </el-radio-group>
        </el-form-item>

        <!-- 按股数 -->
        <template v-if="sellForm.mode === 'shares'">
          <el-form-item label="卖出数量">
            <el-input-number v-model="sellForm.shares" :min="100" :max="sellTarget?.shares ?? 0" :step="100" style="width: 100%" />
          </el-form-item>
        </template>

        <!-- 按金额 -->
        <template v-if="sellForm.mode === 'amount'">
          <el-form-item label="卖出金额">
            <el-input-number v-model="sellForm.amount" :min="0" :step="1000" style="width: 100%" />
            <div class="form-hint" v-if="sellTarget">
              持仓市值：{{ formatAmount(sellTarget.market_value) }}
              → 卖出 {{ sellAmountShares }} 股
            </div>
          </el-form-item>
        </template>

        <!-- 按比例 -->
        <template v-if="sellForm.mode === 'ratio'">
          <el-form-item label="卖出比例">
            <el-input-number v-model="sellForm.ratio" :min="0" :max="100" :step="25" style="width: 100%">
              <template #append>%</template>
            </el-input-number>
            <div class="form-hint-buttons">
              <el-button size="small" v-for="pct in [25, 50, 75, 100]" :key="pct" @click="sellForm.ratio = pct">
                {{ pct }}%
              </el-button>
            </div>
            <div class="form-hint" v-if="sellTarget">
              → 卖出 {{ sellRatioShares }} 股，约 {{ formatAmount(sellRatioShares * (sellTarget?.current_price ?? 0)) }}
            </div>
          </el-form-item>
        </template>

        <!-- 确认信息 -->
        <el-divider v-if="sellConfirmShares > 0">确认信息</el-divider>
        <div class="confirm-block" v-if="sellConfirmShares > 0 && sellTarget">
          <div class="confirm-row"><span>卖出数量</span><span>{{ sellConfirmShares }} 股</span></div>
          <div class="confirm-row"><span>卖出金额</span><span>{{ formatAmount(sellConfirmAmount) }}</span></div>
          <div class="confirm-row"><span>印花税</span><span>{{ sellStampTax.toFixed(2) }} 元（千分之一，卖出收）</span></div>
          <div class="confirm-row"><span>手续费</span><span>{{ sellCommission.toFixed(2) }} 元（万三，最低5元）</span></div>
          <div class="confirm-row"><span>实际到账</span><span>{{ formatAmount(sellActualGain) }}</span></div>
          <div class="confirm-row">
            <span>本次盈亏</span>
            <span :class="pnlColorClass(sellProfit)">
              {{ sellProfit >= 0 ? '+' : '' }}{{ sellProfit.toFixed(2) }} 元
            </span>
          </div>
        </div>
      </el-form>
      <template #footer>
        <el-button @click="showSellDialog = false">取消</el-button>
        <el-button type="danger" :loading="tradeLoading" :disabled="sellConfirmShares <= 0" @click="doConfirmSell">
          确认卖出
        </el-button>
      </template>
    </el-dialog>

  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { paperApi, type PaperAccount, type PaperPosition, type TradeRecord, type PaperStats, type NavPoint } from '@/api/paper'
import ProfitChart from '@/components/ProfitChart/index.vue'

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
const initCapital = ref(100000)

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

// --- Buy dialog state ---
const buyTargetPosition = ref<PaperPosition | null>(null)
const buyCurrentPrice = ref<number | null>(null)
const buyPriceType = ref<string>('close')
const buyPriceLoading = ref(false)
const buyPriceError = ref('')
const buyForm = ref({
  code: '',
  mode: 'shares' as 'shares' | 'amount' | 'ratio',
  shares: 100,
  amount: 10000,
  targetRatio: 50,
})

const buyDialogTitle = computed(() =>
  buyTargetPosition.value
    ? `买入 ${buyTargetPosition.value.name}（${buyTargetPosition.value.code}）`
    : '手动买入'
)

const currentStockRatio = computed(() => {
  if (!buyTargetPosition.value || netValue.value <= 0) return 0
  return buyTargetPosition.value.market_value / netValue.value * 100
})

const buyAmountShares = computed(() => {
  if (!buyCurrentPrice.value || buyCurrentPrice.value <= 0) return 0
  return Math.floor(buyForm.value.amount / buyCurrentPrice.value / 100) * 100
})

const buyAmountActual = computed(() =>
  buyAmountShares.value * (buyCurrentPrice.value ?? 0)
)

const buyRatioTargetAmount = computed(() =>
  netValue.value * buyForm.value.targetRatio / 100
)

const buyRatioShares = computed(() => {
  if (!buyCurrentPrice.value || buyCurrentPrice.value <= 0) return 0
  const currentHoldingValue = buyTargetPosition.value
    ? buyTargetPosition.value.current_price * buyTargetPosition.value.shares
    : 0
  const needBuy = buyRatioTargetAmount.value - currentHoldingValue
  if (needBuy <= 0) return 0
  return Math.floor(needBuy / buyCurrentPrice.value / 100) * 100
})

const buyConfirmShares = computed(() => {
  const mode = buyForm.value.mode
  if (mode === 'shares') {
    return buyForm.value.shares % 100 === 0 ? buyForm.value.shares : 0
  }
  if (mode === 'amount') return buyAmountShares.value
  if (mode === 'ratio') return buyRatioShares.value
  return 0
})

const buyConfirmAmount = computed(() =>
  buyConfirmShares.value * (buyCurrentPrice.value ?? 0)
)

const buyCommission = computed(() =>
  Math.max(5, buyConfirmAmount.value * 0.0003)
)

const buyAfterRatio = computed(() => {
  if (netValue.value <= 0) return 0
  const existingValue = buyTargetPosition.value
    ? buyTargetPosition.value.market_value
    : 0
  return (existingValue + buyConfirmAmount.value) / netValue.value * 100
})

const buyAfterCash = computed(() =>
  (account.value?.cash_balance ?? 0) - buyConfirmAmount.value - buyCommission.value
)

const buyCashInsufficient = computed(() =>
  buyConfirmShares.value > 0 && buyAfterCash.value < 0
)

const buyMaxAffordableShares = computed(() => {
  if (!buyCurrentPrice.value || buyCurrentPrice.value <= 0) return 0
  const cash = account.value?.cash_balance ?? 0
  const raw = Math.floor(cash / (buyCurrentPrice.value * 1.0003) / 100) * 100
  return Math.max(0, raw)
})

const buyRatioCurrentHolding = computed(() => {
  if (!buyTargetPosition.value) return 0
  return buyTargetPosition.value.current_price * buyTargetPosition.value.shares
})

const buyRatioNeedBuyAmount = computed(() =>
  buyRatioTargetAmount.value - buyRatioCurrentHolding.value
)

// --- Sell dialog state ---
const sellTarget = ref<PaperPosition | null>(null)
const sellForm = ref({
  mode: 'ratio' as 'shares' | 'amount' | 'ratio',
  shares: 100,
  amount: 10000,
  ratio: 100,
})

const sellDialogTitle = computed(() =>
  sellTarget.value
    ? `卖出 ${sellTarget.value.name}（${sellTarget.value.code}）`
    : '卖出'
)

const sellAmountShares = computed(() => {
  if (!sellTarget.value || sellTarget.value.current_price <= 0) return 0
  const raw = Math.floor(sellForm.value.amount / sellTarget.value.current_price / 100) * 100
  return Math.min(raw, sellTarget.value.shares)
})

const sellRatioShares = computed(() => {
  if (!sellTarget.value) return 0
  const total = sellTarget.value.shares
  if (sellForm.value.ratio >= 100) return total
  const raw = Math.floor(total * sellForm.value.ratio / 100 / 100) * 100
  return Math.min(raw, total)
})

const sellConfirmShares = computed(() => {
  const mode = sellForm.value.mode
  if (mode === 'shares') return sellForm.value.shares
  if (mode === 'amount') return sellAmountShares.value
  if (mode === 'ratio') return sellRatioShares.value
  return 0
})

const sellConfirmAmount = computed(() =>
  sellConfirmShares.value * (sellTarget.value?.current_price ?? 0)
)

const sellStampTax = computed(() =>
  sellConfirmAmount.value * 0.001
)

const sellCommission = computed(() =>
  Math.max(5, sellConfirmAmount.value * 0.0003)
)

const sellActualGain = computed(() =>
  sellConfirmAmount.value - sellStampTax.value - sellCommission.value
)

const sellProfit = computed(() => {
  if (!sellTarget.value) return 0
  return (sellTarget.value.current_price - sellTarget.value.avg_cost) * sellConfirmShares.value
    - sellStampTax.value - sellCommission.value
})


// --- helpers ---
function pnlColorClass(v: number) {
  if (v > 0) return 'text-rise'
  if (v < 0) return 'text-fall'
  return 'text-neutral'
}

function formatAmount(v: number): string {
  if (Math.abs(v) >= 1e8) return (v / 1e8).toFixed(2) + '亿'
  if (Math.abs(v) >= 1e4) return (v / 1e4).toFixed(2) + '万'
  return v.toFixed(2)
}

function formatPercent(v: number): string {
  return (v >= 0 ? '+' : '') + v.toFixed(2) + '%'
}

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
async function doInitAccount() {
  if (initCapital.value <= 0) return
  try {
    await ElMessageBox.confirm(
      `确认将模拟账户初始资金设为 ${formatAmount(initCapital.value)}？所有持仓和交易记录将被清空！`,
      '初始化确认',
      { confirmButtonText: '确认', cancelButtonText: '取消', type: 'warning' }
    )
  } catch { return }
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

// --- buy ---
function openBuyDialog(pos?: PaperPosition) {
  buyTargetPosition.value = pos ?? null
  buyCurrentPrice.value = pos?.current_price ?? null
  buyPriceType.value = pos?.price_type ?? 'close'
  buyPriceLoading.value = false
  buyPriceError.value = ''
  buyForm.value = {
    code: pos?.code ?? '',
    mode: 'shares',
    shares: 100,
    amount: 10000,
    targetRatio: 50,
  }
  showBuyDialog.value = true
}

function resetBuyForm() {
  buyTargetPosition.value = null
  buyCurrentPrice.value = null
  buyPriceLoading.value = false
  buyPriceError.value = ''
}

function normalizeCode(code: string): string {
  const c = code.trim().toUpperCase()
  if (c.startsWith('SH') || c.startsWith('SZ')) return c
  if (c.startsWith('6')) return 'SH' + c
  if (c.startsWith('0') || c.startsWith('3')) return 'SZ' + c
  return c
}

async function onBuyCodeBlur() {
  const raw = buyForm.value.code.trim()
  if (!raw || raw.length < 6) return
  const code = normalizeCode(raw)
  buyForm.value.code = code

  buyPriceLoading.value = true
  buyPriceError.value = ''
  buyCurrentPrice.value = null

  try {
    const result = await paperApi.getPrice(code)
    if (result) {
      buyCurrentPrice.value = result.price
      buyPriceType.value = result.price_type
      const existingPos = positions.value.find(p => p.code === code)
      if (existingPos && !buyTargetPosition.value) {
        buyTargetPosition.value = existingPos
      }
    } else {
      buyPriceError.value = '未找到该股票，请确认代码'
    }
  } catch {
    buyPriceError.value = '获取价格失败，请重试'
  } finally {
    buyPriceLoading.value = false
  }
}

function fillMaxAffordableShares() {
  if (buyMaxAffordableShares.value <= 0) return
  buyForm.value.mode = 'shares'
  buyForm.value.shares = buyMaxAffordableShares.value
}

async function doConfirmBuy() {
  if (buyConfirmShares.value <= 0 || !buyCurrentPrice.value) return
  const code = buyTargetPosition.value?.code ?? normalizeCode(buyForm.value.code.trim())
  if (!code) { ElMessage.warning('请输入股票代码'); return }
  if (buyCashInsufficient.value) { ElMessage.warning('现金不足'); return }
  tradeLoading.value = true
  try {
    await paperApi.executeTrade({
      code,
      action: 'buy',
      shares: buyConfirmShares.value,
      price: buyCurrentPrice.value,
    })
    ElMessage.success('买入成功')
    showBuyDialog.value = false
    loadAll()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.error ?? '买入失败')
  } finally {
    tradeLoading.value = false
  }
}

// --- sell ---
function openSellDialog(pos: PaperPosition) {
  sellTarget.value = pos
  sellForm.value = {
    mode: 'ratio',
    shares: Math.min(100, pos.shares),
    amount: pos.market_value,
    ratio: 100,
  }
  showSellDialog.value = true
}

function resetSellForm() {
  sellTarget.value = null
}

async function doConfirmSell() {
  if (sellConfirmShares.value <= 0 || !sellTarget.value) return
  tradeLoading.value = true
  try {
    await paperApi.executeTrade({
      code: sellTarget.value.code,
      action: 'sell',
      shares: sellConfirmShares.value,
      price: sellTarget.value.current_price,
    })
    ElMessage.success('卖出成功')
    showSellDialog.value = false
    loadAll()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.error ?? '卖出失败')
  } finally {
    tradeLoading.value = false
  }
}

onMounted(loadAll)
onUnmounted(() => {
  if (refreshTimer) clearInterval(refreshTimer)
})
</script>

<style scoped>
.paper-trading { display: flex; flex-direction: column; gap: 0; }

.account-bar { background: var(--bg-card); border: 1px solid var(--border-color); }
.account-overview { display: flex; align-items: center; gap: 28px; flex-wrap: wrap; }
.account-stat { display: flex; flex-direction: column; gap: 4px; }
.stat-label { font-size: 12px; color: var(--text-muted); }
.stat-value { font-size: 16px; font-weight: 600; color: var(--text-primary); }
.no-account { display: flex; align-items: center; gap: 12px; color: var(--text-muted); }

.price-indicator { display: flex; align-items: center; gap: 6px; margin-left: auto; margin-right: 8px; }
.indicator-dot { width: 8px; height: 8px; border-radius: 50%; display: inline-block; }
.indicator-live { background: var(--el-color-success); box-shadow: 0 0 4px var(--el-color-success); }
.indicator-close { background: var(--text-faint); }
.indicator-text { font-size: 12px; color: var(--text-muted); }
.indicator-live-text { color: var(--el-color-success); font-size: 12px; font-weight: 600; }
.indicator-close-text { color: var(--text-muted); font-size: 12px; }

.section-card { background: var(--bg-card); border: 1px solid var(--border-color); }
.section-card :deep(.el-card__header) {
  border-bottom: 1px solid var(--border-color); padding: 12px 16px;
  color: var(--text-primary); font-size: 14px; font-weight: 600;
}
.card-header { display: flex; justify-content: space-between; align-items: center; }

.stock-link { color: var(--el-color-primary); text-decoration: none; }
.stock-link:hover { text-decoration: underline; }

.text-rise { color: #ef5350; }
.text-fall { color: #26a69a; }
.text-neutral { color: var(--text-muted); }
.text-primary { color: var(--el-color-primary); }

.trade-list { display: flex; flex-direction: column; gap: 8px; max-height: 240px; overflow-y: auto; }
.trade-item { padding: 8px 10px; background: var(--border-color); border-radius: 4px; }
.trade-header { display: flex; justify-content: space-between; align-items: center; }
.trade-code { font-size: 13px; font-weight: 600; color: var(--text-primary); }
.trade-detail { font-size: 12px; color: var(--text-muted); margin-top: 4px; display: flex; justify-content: space-between; }
.trade-time { color: var(--text-faint); }
.trade-signal { font-size: 11px; color: var(--el-color-warning); margin-top: 2px; }

.distribution-chart { display: flex; flex-direction: column; gap: 8px; }
.distribution-item { display: flex; flex-direction: column; gap: 4px; }
.dist-info { display: flex; justify-content: space-between; font-size: 12px; }
.dist-label { color: var(--text-primary); }
.dist-percent { color: var(--text-muted); }
.dist-bar-container { height: 6px; background: var(--border-color); border-radius: 3px; overflow: hidden; }
.dist-bar { height: 100%; background: var(--el-color-primary); border-radius: 3px; transition: width 0.3s ease; }


.dialog-warn { color: var(--el-color-danger); font-size: 12px; margin-top: 8px; padding-left: 100px; }
.dialog-info { color: var(--text-muted); font-size: 12px; margin-top: 4px; padding-left: 100px; }

.trade-dialog-header {
  padding: 8px 12px; margin-bottom: 12px;
  background: var(--border-color); border-radius: 4px;
  font-size: 13px; color: var(--text-primary);
  display: flex; flex-direction: column; gap: 4px;
}
.trade-dialog-header span { display: inline-flex; align-items: center; gap: 6px; }

.form-hint { font-size: 12px; color: var(--text-muted); margin-top: 4px; }
.form-hint-buttons { display: flex; gap: 4px; margin-top: 6px; }

.confirm-block { padding: 0 12px; }
.confirm-row {
  display: flex; justify-content: space-between; align-items: center;
  padding: 6px 0; font-size: 13px; color: var(--text-primary);
  border-bottom: 1px solid var(--border-color);
}
.confirm-row:last-child { border-bottom: none; }
.confirm-row span:first-child { color: var(--text-muted); }
.confirm-row-danger { background: rgba(196, 69, 60, 0.08); border-radius: 4px; padding: 6px 8px !important; }

.price-loading { color: var(--text-muted); font-size: 13px; }

.cash-warning {
  margin-top: 8px; padding: 10px 12px;
  background: rgba(196, 69, 60, 0.1); border: 1px solid rgba(196, 69, 60, 0.3);
  border-radius: 4px;
}
.cash-warning-text { font-size: 13px; color: var(--el-color-danger); }
.cash-warning-hint { font-size: 12px; color: var(--el-color-warning); margin-top: 6px; }
.max-buy-link { color: var(--el-color-primary); cursor: pointer; text-decoration: underline; }
.max-buy-link:hover { color: #66b1ff; }
</style>
