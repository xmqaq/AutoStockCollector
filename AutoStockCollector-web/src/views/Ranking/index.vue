<template>
  <div class="ranking-page">
    <div class="page-header">
      <h2>盈利排行榜</h2>
      <span class="page-desc">所有用户按总收益率排序，每日更新</span>
    </div>

    <el-card shadow="never" class="ranking-card">
      <el-table :data="ranking" v-loading="loading" stripe style="width: 100%">
        <el-table-column label="排名" width="80" align="center">
          <template #default="{ $index, row }">
            <span :class="['rank-badge', rankClass($index)]">
              {{ row.rank }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="用户" min-width="160">
          <template #default="{ row }">
            <div class="user-cell">
              <span class="nickname">{{ row.username }}</span>
              <span v-if="row.raw_username && row.raw_username !== row.username" class="login-name">@{{ row.raw_username }}</span>
              <span v-if="row.user_id === currentUserId" class="self-tag">我</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="总收益率" width="140" align="right">
          <template #default="{ row }">
            <span :class="['profit-text', row.profit_pct >= 0 ? 'up' : 'dn']">
              {{ row.profit_pct >= 0 ? '+' : '' }}{{ row.profit_pct }}%
            </span>
          </template>
        </el-table-column>
        <el-table-column label="收益额" width="150" align="right">
          <template #default="{ row }">
            <span :class="['profit-text', row.profit_amount >= 0 ? 'up' : 'dn']">
              {{ row.profit_amount >= 0 ? '+' : '' }}¥{{ formatAmount(row.profit_amount) }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="本金" width="140" align="right">
          <template #default="{ row }">
            ¥{{ formatAmount(row.initial_capital) }}
          </template>
        </el-table-column>
        <el-table-column label="胜率" width="100" align="center">
          <template #default="{ row }">
            {{ row.win_rate }}%
          </template>
        </el-table-column>
        <el-table-column label="交易次数" width="100" align="center">
          <template #default="{ row }">
            {{ row.total_trades }}
          </template>
        </el-table-column>
      </el-table>

      <el-empty v-if="!loading && ranking.length === 0" description="暂无排行数据，快去交易吧" />
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useAuthStore } from '@/stores/authStore'
import { paperApi } from '@/api/paper'
import type { RankingEntry } from '@/api/paper'

const authStore = useAuthStore()
const currentUserId = computed(() => authStore.user?.user_id)
const ranking = ref<RankingEntry[]>([])
const loading = ref(false)

function rankClass(index: number) {
  if (index === 0) return 'gold'
  if (index === 1) return 'silver'
  if (index === 2) return 'bronze'
  return ''
}

function formatAmount(v: number) {
  if (Math.abs(v) >= 1e4) return (v / 1e4).toFixed(2) + '万'
  return v.toFixed(2)
}

async function fetchRanking() {
  loading.value = true
  try {
    ranking.value = await paperApi.getRanking()
  } catch {
    // handled by interceptor
  } finally {
    loading.value = false
  }
}

onMounted(fetchRanking)
</script>

<style scoped>
.ranking-page {
  padding: 0;
}

.page-header {
  display: flex;
  align-items: baseline;
  gap: 12px;
  margin-bottom: 20px;
}

.page-header h2 {
  margin: 0;
  font-size: 20px;
  font-weight: 600;
  color: var(--text-primary);
}

.page-desc {
  font-size: 13px;
  color: var(--text-muted);
}

.ranking-card {
  border-radius: var(--radius-md);
}

.rank-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border-radius: 50%;
  font-size: 13px;
  font-weight: 700;
  background: var(--bg-soft);
  color: var(--text-secondary);
}

.rank-badge.gold {
  background: linear-gradient(135deg, #f59e0b, #d97706);
  color: #fff;
}

.rank-badge.silver {
  background: linear-gradient(135deg, #94a3b8, #64748b);
  color: #fff;
}

.rank-badge.bronze {
  background: linear-gradient(135deg, #d97706, #92400e);
  color: #fff;
}

.user-cell {
  display: flex;
  align-items: center;
  gap: 8px;
}

.nickname {
  font-weight: 500;
  color: var(--text-primary);
}

.login-name {
  font-size: 12px;
  color: var(--text-faint);
}

.self-tag {
  font-size: 11px;
  padding: 1px 6px;
  border-radius: 4px;
  background: var(--el-color-primary, #409eff);
  color: #fff;
  font-weight: 500;
}

.profit-text {
  font-weight: 600;
  font-variant-numeric: tabular-nums;
}

.profit-text.up {
  color: #ef4444;
}

.profit-text.dn {
  color: #10b981;
}
</style>
