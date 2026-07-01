<template>
  <el-card shadow="never" class="modern-ranking-card">
    <el-table 
      :data="ranking" 
      v-loading="loading" 
      :row-class-name="tableRowClassName"
      class="custom-table"
      @row-click="handleRowClick"
    >
      <!-- 排名 -->
      <el-table-column label="排名" width="100" align="center">
        <template #default="{ $index, row }">
          <div :class="['rank-wrapper', getRankClass($index)]">
            <el-icon v-if="$index === 0" class="rank-icon"><Trophy /></el-icon>
            <el-icon v-else-if="$index === 1" class="rank-icon"><Medal /></el-icon>
            <el-icon v-else-if="$index === 2" class="rank-icon"><Medal /></el-icon>
            <span v-else class="rank-number">{{ row.rank }}</span>
          </div>
        </template>
      </el-table-column>

      <!-- 交易员 -->
      <el-table-column label="交易员" min-width="220">
        <template #default="{ $index, row }">
          <div class="user-info">
            <el-avatar 
              :size="42" 
              :class="['user-avatar', getRankClass($index)]"
            >
              {{ row.username.charAt(0).toUpperCase() }}
            </el-avatar>
            <div class="user-details">
              <div class="name-line">
                <span class="nickname">{{ row.username }}</span>
                <el-tag v-if="row.user_id === currentUserId" size="small" type="primary" effect="dark" round class="self-tag">我</el-tag>
              </div>
              <span v-if="row.raw_username && row.raw_username !== row.username" class="login-name">@{{ row.raw_username }}</span>
            </div>
          </div>
        </template>
      </el-table-column>

      <!-- 资产状况 -->
      <el-table-column label="资产状况" min-width="160" align="right" sortable :sort-by="(row: any) => row.total_asset">
        <template #default="{ row }">
          <div class="data-stack">
            <span class="primary-data asset-total">¥{{ formatAmount(row.total_asset) }}</span>
            <span class="secondary-data">持仓 ¥{{ formatAmount(row.market_value) }}</span>
          </div>
        </template>
      </el-table-column>

      <!-- 累计收益 -->
      <el-table-column label="累计收益" min-width="160" align="right" sortable :sort-by="(row: any) => row.profit_pct">
        <template #default="{ row }">
          <div class="data-stack">
            <span :class="['primary-data', 'profit-text', getProfitColorClass(row.profit_pct)]">
              {{ row.profit_pct > 0 ? '+' : '' }}{{ formatPct(row.profit_pct) }}%
            </span>
            <span :class="['secondary-data', getProfitColorClass(row.profit_amount, true)]">
              {{ row.profit_amount > 0 ? '+' : '' }}¥{{ formatAmount(row.profit_amount) }}
            </span>
            <el-tooltip
              content="累计收益已扣手续费；今日表现为不含手续费的当日股价浮动，故两者会差一笔手续费"
              placement="top"
            >
              <span class="tertiary-data">手续费 ¥{{ formatAmount(row.total_fee || 0) }}</span>
            </el-tooltip>
          </div>
        </template>
      </el-table-column>

      <!-- 今日表现 -->
      <el-table-column label="今日表现" min-width="140" align="right" sortable :sort-by="(row: any) => row.today_pnl">
        <template #default="{ row }">
          <div :class="['profit-pill', getProfitBgClass(row.today_pnl)]">
            {{ row.today_pnl > 0 ? '+' : '' }}¥{{ formatAmount(row.today_pnl) }}
          </div>
        </template>
      </el-table-column>

      <!-- 交易统计 -->
      <el-table-column label="交易统计" min-width="120" align="center" sortable :sort-by="(row: any) => row.win_rate">
        <template #default="{ row }">
          <div class="data-stack align-center">
            <span class="primary-data win-rate">{{ formatPct(row.win_rate) }}% 胜率</span>
            <span class="secondary-data">{{ row.total_trades }} 笔交易</span>
          </div>
        </template>
      </el-table-column>
    </el-table>

    <el-empty v-if="!loading && ranking.length === 0" description="暂无排行数据，快去交易吧" />
  </el-card>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useAuthStore } from '@/stores/authStore'
import { Trophy, Medal } from '@element-plus/icons-vue'
import type { RankingEntry } from '@/api/paper'

const props = defineProps<{
  ranking: RankingEntry[]
  loading: boolean
}>()

const emit = defineEmits<{
  viewUser: [userId: string, username: string]
}>()

function handleRowClick(row: RankingEntry) {
  emit('viewUser', row.user_id, row.username)
}

const authStore = useAuthStore()
const currentUserId = computed(() => authStore.user?.user_id)

function getRankClass(index: number) {
  if (index === 0) return 'rank-gold'
  if (index === 1) return 'rank-silver'
  if (index === 2) return 'rank-bronze'
  return 'rank-normal'
}

function tableRowClassName({ row }: { row: RankingEntry }) {
  if (row.user_id === currentUserId.value) {
    return 'highlight-current-user'
  }
  return ''
}

function formatAmount(v: number) {
  if (Math.abs(v) >= 1e4) return (v / 1e4).toFixed(2) + '万'
  return v.toFixed(2)
}

// 百分比前端兜底格式化：即使后端未 round 也保证两位小数，避免显示 12.345%
function formatPct(v: number) {
  const n = Number(v) || 0
  return n.toFixed(2)
}

function getProfitColorClass(val: number, isLight = false) {
  if (val > 0) return isLight ? 'up-light' : 'up'
  if (val < 0) return isLight ? 'dn-light' : 'dn'
  return 'flat'
}

function getProfitBgClass(val: number) {
  if (val > 0) return 'bg-up'
  if (val < 0) return 'bg-dn'
  return 'bg-flat'
}
</script>

<style scoped>
.modern-ranking-card {
  border-radius: 16px;
  border: 1px solid var(--border-color-light);
  box-shadow: 0 4px 24px var(--bg-hover-subtle);
  overflow: hidden;
  background: var(--bg-card);
}

.custom-table :deep(.el-table__header th) {
  background-color: var(--bg-soft);
  color: var(--text-muted);
  font-weight: 600;
  border-bottom: 1px solid var(--border-color-light);
  padding: 14px 0;
}

.custom-table :deep(.el-table__row) {
  transition: all 0.2s ease;
}

.custom-table :deep(.el-table__row:hover > td.el-table__cell) {
  background-color: var(--bg-soft);
}

.custom-table :deep(.highlight-current-user > td.el-table__cell) {
  background-color: var(--el-color-primary-light-9);
}

/* Rank Styles */
.rank-wrapper {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
}

.rank-icon {
  font-size: 26px;
}

.rank-gold .rank-icon { color: #F59E0B; filter: drop-shadow(0 2px 4px rgba(245, 158, 11, 0.3)); }
.rank-silver .rank-icon { color: #94A3B8; filter: drop-shadow(0 2px 4px rgba(148, 163, 184, 0.3)); }
.rank-bronze .rank-icon { color: #D97706; filter: drop-shadow(0 2px 4px rgba(217, 119, 6, 0.3)); }

.rank-number {
  font-size: 16px;
  font-weight: 700;
  color: var(--text-secondary);
  font-family: var(--font-mono);
}

/* User Info */
.user-info {
  display: flex;
  align-items: center;
  gap: 12px;
}

.user-avatar {
  font-weight: 600;
  font-size: 18px;
  background: var(--bg-soft);
  color: var(--text-secondary);
}

.rank-gold.user-avatar { background: linear-gradient(135deg, #FDE68A, #F59E0B); color: #fff; }
.rank-silver.user-avatar { background: linear-gradient(135deg, #E2E8F0, #94A3B8); color: #fff; }
.rank-bronze.user-avatar { background: linear-gradient(135deg, #FDE047, #D97706); color: #fff; }

.user-details {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.name-line {
  display: flex;
  align-items: center;
  gap: 8px;
}

.nickname {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
}

.login-name {
  font-size: 12px;
  color: var(--text-faint);
}

.self-tag {
  transform: scale(0.9);
  transform-origin: left center;
}

/* Data Stacks */
.data-stack {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.data-stack.align-center {
  align-items: center;
}

.primary-data {
  font-size: 15px;
  font-weight: 600;
  font-family: var(--font-mono);
  color: var(--text-primary);
}

.secondary-data {
  font-size: 12px;
  color: var(--text-muted);
  font-family: var(--font-mono);
}

.tertiary-data {
  font-size: 11px;
  color: var(--text-faint);
  font-family: var(--font-mono);
  cursor: help;
}

/* Profits & Colors */
.profit-text.up { color: #F23645; }
.profit-text.dn { color: #11C27E; }
.profit-text.flat { color: var(--text-secondary); }

.up-light { color: #F23645; opacity: 0.8; }
.dn-light { color: #11C27E; opacity: 0.8; }
.flat { color: var(--text-muted); }

.profit-pill {
  display: inline-block;
  padding: 4px 12px;
  border-radius: 6px;
  font-size: 14px;
  font-weight: 600;
  font-family: var(--font-mono);
  text-align: center;
  min-width: 80px;
}

.bg-up { background-color: #F23645; color: #fff; }
.bg-dn { background-color: #11C27E; color: #fff; }
.bg-flat { background-color: var(--bg-soft); color: var(--text-secondary); }

.win-rate {
  color: var(--text-primary);
}
</style>
