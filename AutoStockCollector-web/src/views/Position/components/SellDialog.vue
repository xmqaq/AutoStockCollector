<template>
  <el-dialog :model-value="visible" @update:model-value="closeDialog" :title="sellDialogTitle" width="520px" @close="resetSellForm">
    <div class="trade-dialog-header" v-if="sellTarget">
      <div>当前价：<b>{{ sellTarget.current_price.toFixed(2) }}</b> 元 &nbsp; 成本价：{{ sellTarget.avg_cost.toFixed(2) }} 元</div>
      <div>
        持仓：{{ sellTarget.shares }} 股 &nbsp; 可卖：<b>{{ sellTarget.available_shares ?? sellTarget.shares }}</b> 股
        <el-tag v-if="(sellTarget.shares - (sellTarget.available_shares ?? sellTarget.shares)) > 0" type="warning" size="small" effect="light" style="margin-left: 6px;">
          T+1 锁定 {{ sellTarget.shares - (sellTarget.available_shares ?? sellTarget.shares) }} 股
        </el-tag>
        &nbsp; 当前盈亏：
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
          <el-input-number v-model="sellForm.shares" :min="100" :max="sellAvailableShares" :step="100" style="width: 100%" />
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
      <el-button @click="closeDialog">取消</el-button>
      <el-button type="danger" :loading="tradeLoading" :disabled="sellConfirmShares <= 0 || sellAvailableShares <= 0" @click="doConfirmSell">
        {{ isTradingTime ? '确认卖出' : '提交挂单' }}
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { paperApi, type PaperPosition } from '@/api/paper'
import { formatAmount, formatPercent, pnlColorClass } from '../utils'

const props = defineProps<{
  visible: boolean
  target: PaperPosition | null
  isTradingTime?: boolean
}>()

const emit = defineEmits<{
  (e: 'update:visible', val: boolean): void
  (e: 'success'): void
}>()

const tradeLoading = ref(false)
const sellTarget = ref<PaperPosition | null>(null)

const sellForm = ref({
  mode: 'ratio' as 'shares' | 'amount' | 'ratio',
  shares: 100,
  amount: 10000,
  ratio: 100,
})

watch(() => props.visible, (val) => {
  if (val && props.target) {
    sellTarget.value = props.target
    sellForm.value = {
      mode: 'ratio',
      shares: Math.min(100, props.target.shares),
      amount: props.target.market_value,
      ratio: 100,
    }
  }
})

function closeDialog() {
  emit('update:visible', false)
}

function resetSellForm() {
  sellTarget.value = null
}

const sellDialogTitle = computed(() =>
  sellTarget.value
    ? `卖出 ${sellTarget.value.name}（${sellTarget.value.code}）`
    : '卖出'
)

// T+1：可卖股数 = 总持仓 - 当日买入 - 挂单冻结（后端已算好 available_shares，缺失时回退总持仓）
const sellAvailableShares = computed(() => sellTarget.value?.available_shares ?? sellTarget.value?.shares ?? 0)

const sellAmountShares = computed(() => {
  if (!sellTarget.value || sellTarget.value.current_price <= 0) return 0
  const raw = Math.floor(sellForm.value.amount / sellTarget.value.current_price / 100) * 100
  return Math.min(raw, sellAvailableShares.value)
})

const sellRatioShares = computed(() => {
  if (!sellTarget.value) return 0
  const total = sellAvailableShares.value
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

async function doConfirmSell() {
  if (sellConfirmShares.value <= 0 || !sellTarget.value) return
  if (sellAvailableShares.value <= 0) {
    ElMessage.warning('当前可卖份额为 0（当日买入 T+1 锁定），不可卖出')
    return
  }

  // 非连续竞价时段：提醒用户订单将转为挂单，开盘后自动撮合
  if (!props.isTradingTime) {
    try {
      await ElMessageBox.confirm(
        '当前非交易时段，订单将作为挂单保存，开盘后（9:30 连续竞价）自动按市价撮合成交。是否继续？',
        '交易时段提醒',
        { confirmButtonText: '继续下单', cancelButtonText: '取消', type: 'warning' },
      )
    } catch {
      return
    }
  }

  tradeLoading.value = true
  try {
    const result = await paperApi.executeTrade({
      code: sellTarget.value.code,
      action: 'sell',
      shares: sellConfirmShares.value,
      price: sellTarget.value.current_price,
    })
    if (result.status === 'filled') {
      ElMessage.success('卖出成功，已成交')
    } else {
      ElMessage.info('订单已挂单，开盘后将自动撮合成交（可在"挂单与委托"中查看/撤单）')
    }
    closeDialog()
    emit('success')
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.error ?? '卖出失败')
  } finally {
    tradeLoading.value = false
  }
}
</script>

<style scoped>
.trade-dialog-header { padding: 12px 16px; background: var(--bg-soft); border-radius: 6px; margin-bottom: 20px; font-size: 14px; display: flex; flex-direction: column; gap: 6px; }

.form-hint { font-size: 12px; color: var(--text-muted); margin-top: 6px; line-height: 1.4; }
.form-hint-buttons { margin-top: 8px; display: flex; gap: 8px; }

.confirm-block { background: var(--bg-body); padding: 12px 16px; border-radius: 6px; font-size: 13px; display: flex; flex-direction: column; gap: 8px; }
.confirm-row { display: flex; justify-content: space-between; align-items: center; }
.confirm-row span:first-child { color: var(--text-muted); }
.confirm-row span:last-child { font-weight: 500; color: var(--text-primary); }
</style>