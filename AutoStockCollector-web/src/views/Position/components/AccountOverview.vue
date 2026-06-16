<template>
  <div class="premium-account-panel" v-loading="loading">
    <div v-if="account" class="account-content">
      
      <!-- 主资产区 -->
      <div class="main-balance-area">
        <div class="balance-header">
          <span class="label">账户总资产 (CNY)</span>
          <div class="price-indicator" v-if="isTradingTime">
            <span class="indicator-dot indicator-live" />
            <span class="indicator-text">盘中实时</span>
          </div>
          <div class="price-indicator" v-else>
            <span class="indicator-dot indicator-close" />
            <span class="indicator-text">已收盘</span>
          </div>
        </div>
        
        <div class="balance-amount">
          <span class="currency">¥</span>
          <span class="amount-value" :class="pnlColorClass(totalPnlAmount)">{{ formatAmount(netValue) }}</span>
        </div>
        
        <div class="balance-pnl" :class="pnlColorClass(totalPnlAmount)">
          <span class="pnl-label">总盈亏</span>
          <span class="pnl-val">{{ totalPnlAmount >= 0 ? '+' : '' }}{{ formatAmount(totalPnlAmount) }}</span>
          <span class="pnl-badge" :class="totalReturn >= 0 ? 'badge-rise' : 'badge-fall'">
            {{ totalReturn >= 0 ? '↑' : '↓' }} {{ formatPercent(Math.abs(totalReturn)) }}
          </span>
        </div>
      </div>

      <div class="divider"></div>

      <!-- 次要数据区 -->
      <div class="sub-stats-area">
        <div class="stat-box">
          <div class="stat-label">可用资金 (购买力)</div>
          <div class="stat-val">{{ formatAmount(account.cash_balance) }}</div>
        </div>
        <div class="stat-box">
          <div class="stat-label">持仓市值</div>
          <div class="stat-val text-primary">{{ formatAmount(totalMarketValue) }}</div>
        </div>
        <div class="stat-box">
          <div class="stat-label">初始本金</div>
          <div class="stat-val text-faint">{{ formatAmount(account.initial_capital) }}</div>
        </div>
      </div>

      <!-- 操作区 -->
      <div class="action-area">
        <el-button type="primary" class="action-btn primary-btn" @click="$emit('deposit')">
          资金划转
        </el-button>
        <el-button plain class="action-btn" @click="$emit('init')">
          重置账户
        </el-button>
      </div>

    </div>
    
    <div v-else class="no-account">
      <el-empty description="尚未初始化模拟账户" :image-size="80">
        <el-button type="primary" size="large" @click="$emit('init')">立即初始化</el-button>
      </el-empty>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { PaperAccount } from '@/api/paper'
import { pnlColorClass, formatAmount, formatPercent } from '../utils'

defineProps<{
  account: PaperAccount | null
  loading: boolean
  isTradingTime: boolean
  netValue: number
  totalMarketValue: number
  totalPnlAmount: number
  totalReturn: number
}>()

defineEmits<{
  (e: 'init'): void
  (e: 'deposit'): void
}>()
</script>

<style scoped>
.premium-account-panel {
  background: linear-gradient(135deg, #ffffff 0%, #f8fafd 100%);
  border: 1px solid var(--border-color, #ebeef5);
  border-radius: 12px;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.03);
  padding: 24px 32px;
  position: relative;
  overflow: hidden;
}

/* 增加一点背景装饰纹理 */
.premium-account-panel::after {
  content: '';
  position: absolute;
  top: 0; right: 0; width: 300px; height: 100%;
  background: linear-gradient(90deg, transparent, rgba(64, 158, 255, 0.03));
  pointer-events: none;
}

.account-content {
  display: flex;
  align-items: center;
  justify-content: space-between;
  position: relative;
  z-index: 1;
  flex-wrap: wrap;
  gap: 20px;
}

/* 主资产区 */
.main-balance-area {
  display: flex;
  flex-direction: column;
  gap: 8px;
  min-width: 280px;
}

.balance-header {
  display: flex;
  align-items: center;
  gap: 12px;
}

.balance-header .label {
  font-size: 14px;
  color: var(--text-muted, #909399);
  font-weight: 500;
}

.price-indicator {
  display: flex;
  align-items: center;
  gap: 6px;
  background: rgba(0,0,0,0.04);
  padding: 2px 8px;
  border-radius: 12px;
}

.indicator-dot {
  width: 6px; height: 6px; border-radius: 50%;
}
.indicator-live { background: #67c23a; box-shadow: 0 0 4px #67c23a; }
.indicator-close { background: #c0c4cc; }
.indicator-text { font-size: 12px; color: var(--text-regular, #606266); font-weight: 500; }

.balance-amount {
  display: flex;
  align-items: baseline;
  gap: 4px;
  margin-top: 4px;
}

.currency {
  font-size: 24px;
  font-weight: 600;
  color: var(--text-primary, #303133);
}

.amount-value {
  font-size: 38px;
  font-weight: 700;
  font-family: var(--font-mono, "DIN Alternate", "Helvetica Neue", sans-serif);
  line-height: 1;
  letter-spacing: -0.5px;
}

.balance-pnl {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  font-weight: 600;
}

.pnl-badge {
  padding: 2px 8px;
  border-radius: 6px;
  font-size: 12px;
  font-weight: bold;
}
.badge-rise { background: rgba(239, 83, 80, 0.12); color: #ef5350; }
.badge-fall { background: rgba(38, 166, 154, 0.12); color: #26a69a; }

/* 分割线 */
.divider {
  width: 1px;
  height: 80px;
  background: var(--border-color, #ebeef5);
  margin: 0 16px;
}

@media (max-width: 900px) {
  .divider { display: none; }
}

/* 次要数据区 */
.sub-stats-area {
  display: flex;
  gap: 32px;
  flex: 1;
  flex-wrap: wrap;
  min-width: 250px;
}

.stat-box {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.stat-label {
  font-size: 13px;
  color: var(--text-muted, #909399);
}

.stat-val {
  font-size: 20px;
  font-weight: 600;
  font-family: var(--font-mono, "DIN Alternate", "Helvetica Neue", sans-serif);
  color: var(--text-primary, #303133);
}

.text-primary { color: var(--el-color-primary, #409eff); }
.text-faint { color: var(--text-placeholder, #c0c4cc); }

/* 操作区 */
.action-area {
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin-left: 32px;
  justify-content: center;
}

.action-btn {
  width: 120px;
  border-radius: 6px;
  font-weight: 600;
  margin-left: 0 !important; /* 强制覆盖 Element Plus 按钮组默认的 margin-left */
}

.primary-btn {
  background: linear-gradient(90deg, var(--el-color-primary), #66b1ff);
  border: none;
  box-shadow: 0 4px 12px rgba(64, 158, 255, 0.3);
}
.primary-btn:hover {
  transform: translateY(-1px);
  box-shadow: 0 6px 16px rgba(64, 158, 255, 0.4);
}

.no-account {
  width: 100%;
  display: flex;
  justify-content: center;
}

.text-rise { color: #ef5350; }
.text-fall { color: #26a69a; }
.text-neutral { color: var(--text-primary); }
</style>