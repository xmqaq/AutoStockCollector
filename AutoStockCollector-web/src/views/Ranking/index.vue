<template>
  <div class="ranking-page">
    <div class="page-header">
      <div class="header-content">
        <h2 class="page-title">
          <el-icon class="title-icon"><TrophyBase /></el-icon>
          盈利排行榜
        </h2>
        <span class="page-desc">
          <el-tag size="small" :type="isTradingNow() ? 'success' : 'info'" effect="light" class="status-tag">
            {{ isTradingNow() ? '交易中' : '已收盘' }}
          </el-tag>
          {{ isTradingNow() ? '榜单每 15 秒自动刷新实时数据' : '展示最新收盘结算数据' }}
        </span>
      </div>
      <div class="header-actions">
        <span v-if="lastUpdated" class="last-updated">最后更新于 {{ lastUpdated }}</span>
        <el-button type="primary" :loading="loading || refreshing" @click="fetchRanking(false)" round plain>
          <el-icon><Refresh /></el-icon> 刷新榜单
        </el-button>
      </div>
    </div>

    <RankingTable :ranking="ranking" :loading="loading" />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { Refresh, Trophy as TrophyBase } from '@element-plus/icons-vue'
import { paperApi } from '@/api/paper'
import type { RankingEntry } from '@/api/paper'
import RankingTable from './components/RankingTable.vue'

const ranking = ref<RankingEntry[]>([])
const loading = ref(false)
const refreshing = ref(false)
const lastUpdated = ref('')
let _pollTimer: ReturnType<typeof setInterval> | undefined

// A股交易时段：周一~周五 9:30-11:30 / 13:00-15:00（按本地时间近似，用于决定是否自动轮询）
function isTradingNow(): boolean {
  const d = new Date()
  const day = d.getDay()
  if (day === 0 || day === 6) return false
  const mins = d.getHours() * 60 + d.getMinutes()
  return (mins >= 570 && mins <= 690) || (mins >= 780 && mins <= 900)
}

async function fetchRanking(silent = false) {
  if (silent) {
    refreshing.value = true
  } else {
    loading.value = true
  }
  try {
    ranking.value = await paperApi.getRanking(true)
    const d = new Date()
    lastUpdated.value = `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}:${String(d.getSeconds()).padStart(2, '0')}`
  } catch {
    // handled by interceptor
  } finally {
    loading.value = false
    refreshing.value = false
  }
}

onMounted(() => {
  fetchRanking()
  // 交易时段每 15 秒轮询（后端 live 模式有缓存），非交易时段停止
  _pollTimer = setInterval(() => {
    if (isTradingNow()) fetchRanking(true)
  }, 15000)
})

onUnmounted(() => {
  if (_pollTimer) clearInterval(_pollTimer)
})
</script>

<style scoped>
.ranking-page {
  padding: 0;
  max-width: 1200px;
  margin: 0 auto;
}

.page-header {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  margin-bottom: 24px;
  padding: 0 8px;
}

.header-content {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.page-title {
  margin: 0;
  font-size: 24px;
  font-weight: 700;
  color: var(--text-primary);
  display: flex;
  align-items: center;
  gap: 8px;
}

.title-icon {
  color: #F59E0B;
  font-size: 28px;
}

.page-desc {
  font-size: 13px;
  color: var(--text-muted);
  display: flex;
  align-items: center;
  gap: 8px;
}

.status-tag {
  font-weight: 600;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 16px;
}

.last-updated {
  font-size: 13px;
  color: var(--text-faint);
  font-family: var(--font-mono);
}
</style>
