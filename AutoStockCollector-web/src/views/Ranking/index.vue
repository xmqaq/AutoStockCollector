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
        <el-input
          v-model="searchQuery"
          placeholder="搜索交易员..."
          clearable
          size="default"
          class="search-input"
          :prefix-icon="Search"
        />
        <span v-if="lastUpdated" class="last-updated">最后更新于 {{ lastUpdated }}</span>
        <el-button type="primary" :loading="loading || refreshing" @click="fetchRanking(false)" round plain>
          <el-icon><Refresh /></el-icon> 刷新榜单
        </el-button>
      </div>
    </div>

    <div v-if="errorMsg && !loading" class="error-banner">
      <el-icon><WarningFilled /></el-icon>
      <span>加载失败：{{ errorMsg }}</span>
      <el-button size="small" type="primary" plain @click="fetchRanking(false)">重试</el-button>
    </div>

    <RankingTable :ranking="filteredRanking" :loading="loading" @view-user="openDrawer" />

    <UserPositionsDrawer
      v-model="drawerVisible"
      :user-id="drawerUserId"
      :username="drawerUsername"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { Refresh, Trophy as TrophyBase, Search, WarningFilled } from '@element-plus/icons-vue'
import { paperApi } from '@/api/paper'
import type { RankingEntry } from '@/api/paper'
import RankingTable from './components/RankingTable.vue'
import UserPositionsDrawer from './components/UserPositionsDrawer.vue'

const ranking = ref<RankingEntry[]>([])
const loading = ref(false)
const refreshing = ref(false)
const lastUpdated = ref('')
const errorMsg = ref('')
const searchQuery = ref('')
const drawerVisible = ref(false)
const drawerUserId = ref('')
const drawerUsername = ref('')
let _pollTimer: ReturnType<typeof setInterval> | undefined

// 搜索过滤：按用户名/原始用户名/user_id 模糊匹配，保留原排名顺序
const filteredRanking = computed(() => {
  const q = searchQuery.value.trim().toLowerCase()
  if (!q) return ranking.value
  return ranking.value.filter(r =>
    (r.username || '').toLowerCase().includes(q) ||
    (r.raw_username || '').toLowerCase().includes(q) ||
    (r.user_id || '').toLowerCase().includes(q)
  )
})

function openDrawer(userId: string, username: string) {
  drawerUserId.value = userId
  drawerUsername.value = username
  drawerVisible.value = true
}

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
    errorMsg.value = ''
  }
  try {
    // silent（轮询）模式：skipErrorMessage 抑制全局 toast，避免失败时每 15s 刷屏
    const data = await paperApi.getRanking(true, silent)
    if (data.length === 0 && !silent) {
      errorMsg.value = '暂无排行数据'
    } else {
      ranking.value = data
      const d = new Date()
      lastUpdated.value = `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}:${String(d.getSeconds()).padStart(2, '0')}`
    }
  } catch (e: any) {
    // 仅显式请求失败才设错误态；轮询失败静默（保留旧数据）
    if (!silent) errorMsg.value = e?.message || '未知错误'
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

.search-input {
  width: 200px;
}

.error-banner {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
  margin-bottom: 16px;
  border-radius: 8px;
  background: var(--el-color-danger-light-9);
  border: 1px solid var(--el-color-danger-light-5);
  color: var(--el-color-danger);
  font-size: 14px;
}

.last-updated {
  font-size: 13px;
  color: var(--text-faint);
  font-family: var(--font-mono);
}
</style>
