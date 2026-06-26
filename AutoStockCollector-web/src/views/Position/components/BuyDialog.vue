<template>
  <el-dialog :model-value="visible" @update:model-value="closeDialog" :title="buyDialogTitle" width="520px" @close="resetBuyForm">
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
      <el-button @click="closeDialog">取消</el-button>
      <el-button type="primary" :loading="tradeLoading" :disabled="buyConfirmShares <= 0 || buyCashInsufficient" @click="doConfirmBuy">
        确认买入
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { WarningFilled } from '@element-plus/icons-vue'
import { paperApi, type PaperAccount, type PaperPosition } from '@/api/paper'
import { formatAmount } from '../utils'

const props = defineProps<{
  visible: boolean
  initialTarget: PaperPosition | null
  account: PaperAccount | null
  netValue: number
  positions: PaperPosition[]
}>()

const emit = defineEmits<{
  (e: 'update:visible', val: boolean): void
  (e: 'success'): void
}>()

const tradeLoading = ref(false)

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

watch(() => props.visible, (val) => {
  if (val) {
    buyTargetPosition.value = props.initialTarget
    buyCurrentPrice.value = props.initialTarget?.current_price ?? null
    buyPriceType.value = props.initialTarget?.price_type ?? 'close'
    buyPriceLoading.value = false
    buyPriceError.value = ''
    buyForm.value = {
      code: props.initialTarget?.code ?? '',
      mode: 'shares',
      shares: 100,
      amount: 10000,
      targetRatio: 50,
    }
  }
})

function closeDialog() {
  emit('update:visible', false)
}

function resetBuyForm() {
  buyTargetPosition.value = null
  buyCurrentPrice.value = null
  buyPriceLoading.value = false
  buyPriceError.value = ''
}

const buyDialogTitle = computed(() =>
  buyTargetPosition.value
    ? `买入 ${buyTargetPosition.value.name}（${buyTargetPosition.value.code}）`
    : '手动买入'
)

const currentStockRatio = computed(() => {
  if (!buyTargetPosition.value || props.netValue <= 0) return 0
  return buyTargetPosition.value.market_value / props.netValue * 100
})

const buyAmountShares = computed(() => {
  if (!buyCurrentPrice.value || buyCurrentPrice.value <= 0) return 0
  return Math.floor(buyForm.value.amount / buyCurrentPrice.value / 100) * 100
})

const buyAmountActual = computed(() =>
  buyAmountShares.value * (buyCurrentPrice.value ?? 0)
)

const buyRatioTargetAmount = computed(() =>
  props.netValue * buyForm.value.targetRatio / 100
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
  if (props.netValue <= 0) return 0
  const existingValue = buyTargetPosition.value
    ? buyTargetPosition.value.market_value
    : 0
  return (existingValue + buyConfirmAmount.value) / props.netValue * 100
})

const buyAfterCash = computed(() =>
  (props.account?.cash_balance ?? 0) - buyConfirmAmount.value - buyCommission.value
)

const buyCashInsufficient = computed(() =>
  buyConfirmShares.value > 0 && buyAfterCash.value < 0
)

const buyMaxAffordableShares = computed(() => {
  if (!buyCurrentPrice.value || buyCurrentPrice.value <= 0) return 0
  const cash = props.account?.cash_balance ?? 0
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
      const existingPos = props.positions.find(p => p.code === code)
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
    closeDialog()
    emit('success')
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.error ?? '买入失败')
  } finally {
    tradeLoading.value = false
  }
}
</script>

<style scoped>
.trade-dialog-header { padding: 12px 16px; background: var(--bg-soft); border-radius: 6px; margin-bottom: 20px; font-size: 14px; display: flex; flex-direction: column; gap: 6px; }
.price-loading { color: var(--text-muted); font-style: italic; }
.indicator-live-text { color: var(--el-color-success); font-size: 12px; font-weight: 600; }
.indicator-close-text { color: var(--text-muted); font-size: 12px; }

.form-hint { font-size: 12px; color: var(--text-muted); margin-top: 6px; line-height: 1.4; }

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
.text-fall { color: var(--el-color-success); }
</style>