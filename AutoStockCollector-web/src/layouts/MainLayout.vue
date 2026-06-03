<template>
  <el-container class="main-layout">
    <!-- Sidebar -->
    <el-aside width="220px" class="sidebar">
      <div class="logo">
        <span class="logo-icon">📈</span>
        <span class="logo-text">AutoStockCollector</span>
      </div>
      <el-menu
        :default-active="activeMenu"
        background-color="#141414"
        text-color="#c0c4cc"
        active-text-color="#409eff"
        @select="handleMenuSelect"
      >
        <el-menu-item
          v-for="item in menuItems"
          :key="item.path"
          :index="item.path"
        >
          <el-icon><component :is="item.icon" /></el-icon>
          <template #title>{{ item.label }}</template>
        </el-menu-item>
      </el-menu>
    </el-aside>

    <!-- Main content area -->
    <el-container class="content-wrapper">
      <!-- Header -->
      <el-header class="header" height="56px">
        <div class="header-left">
          <span class="page-title">{{ currentTitle }}</span>
        </div>
        <div class="header-right">
          <div class="status-indicator">
            <span :class="['status-dot', collectStore.backendOnline ? 'online' : 'offline']"></span>
            <span class="status-text">{{ collectStore.backendOnline ? '后端在线' : '后端离线' }}</span>
          </div>
        </div>
      </el-header>

      <!-- Page content -->
      <el-main class="main-content">
        <router-view />
        <div class="disclaimer">
          免责声明：本系统数据仅供参考，不构成任何投资建议。股市有风险，入市需谨慎。
        </div>
      </el-main>

      <!-- AI Chat Float Button -->
      <AIChatFloat />
    </el-container>
  </el-container>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useCollectStore } from '@/stores/collectStore'
import AIChatFloat from '@/components/AIChatFloat/index.vue'
import {
  DataAnalysis,
  Monitor,
  TrendCharts,
  MagicStick,
  Histogram,
  Lightning,
  Connection,
  Promotion,
  ChatDotRound,
  StarFilled,
  Setting,
  Odometer,
  Key,
  Wallet,
  Search,
  Operation,
} from '@element-plus/icons-vue'

const route = useRoute()
const router = useRouter()
const collectStore = useCollectStore()

const menuItems = [
  { path: '/dashboard', label: '系统总览', icon: DataAnalysis },
  { path: '/data-monitor', label: '采集中心', icon: Monitor },
  { path: '/stock-detail', label: '股票详情', icon: TrendCharts },
  { path: '/market', label: '实时行情', icon: Odometer },
  { path: '/ai-dashboard', label: 'AI智能中枢', icon: MagicStick },
  { path: '/ai-picker', label: '量化选股', icon: TrendCharts },
  { path: '/stock-analysis', label: '个股深度分析', icon: Search },
  { path: '/position', label: '仓位管理', icon: Wallet },
  { path: '/ai-keys', label: 'AI Key管理', icon: Key },
  { path: '/ai-agents', label: 'AI Agent管理', icon: MagicStick },
  { path: '/workflow', label: '工作流管理', icon: Operation },
  { path: '/dragon-tiger', label: '龙虎榜', icon: Lightning },
  { path: '/margin-trading', label: '融资融券', icon: Connection },
  { path: '/sector-flow', label: '板块流向', icon: Promotion },
  { path: '/fund-flow', label: '资金流向排行', icon: TrendCharts },
  { path: '/news', label: '新闻舆情', icon: ChatDotRound },
  { path: '/watchlist', label: '自选股', icon: StarFilled },
]

const activeMenu = computed(() => {
  const currentPath = route.path
  const matchingItem = menuItems.find(item => currentPath.startsWith(item.path))
  return matchingItem?.path || currentPath
})

function handleMenuSelect(path: string) {
  console.log('Menu selected:', path, 'Current route:', route.path)
  router.push(path).catch((err) => {
    console.error('Navigation failed:', err)
  })
}

const currentTitle = computed(() => {
  const matchingItem = menuItems.find(item => route.path.startsWith(item.path))
  return matchingItem?.label || 'AutoStockCollector'
})

let healthTimer: ReturnType<typeof setInterval>

onMounted(() => {
  collectStore.checkHealth()
  healthTimer = setInterval(() => {
    collectStore.checkHealth()
  }, 10000)
})

onUnmounted(() => {
  clearInterval(healthTimer)
})
</script>

<style scoped>
.main-layout {
  height: 100vh;
  background: #141414;
}

.sidebar {
  background: #141414;
  border-right: 1px solid #2c2c2c;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.logo {
  height: 56px;
  display: flex;
  align-items: center;
  padding: 0 16px;
  border-bottom: 1px solid #2c2c2c;
  gap: 8px;
}

.logo-icon {
  font-size: 20px;
}

.logo-text {
  font-size: 14px;
  font-weight: 600;
  color: #e5eaf3;
  white-space: nowrap;
}

.el-menu {
  border-right: none;
  flex: 1;
  overflow-y: auto;
}

.header {
  background: #1f1f1f;
  border-bottom: 1px solid #2c2c2c;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px;
}

.header-left {
  display: flex;
  align-items: center;
}

.page-title {
  font-size: 16px;
  font-weight: 600;
  color: #e5eaf3;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 16px;
}

.status-indicator {
  display: flex;
  align-items: center;
  gap: 6px;
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}

.status-dot.online {
  background: #67c23a;
  box-shadow: 0 0 6px #67c23a;
}

.status-dot.offline {
  background: #f56c6c;
  box-shadow: 0 0 6px #f56c6c;
}

.status-text {
  font-size: 13px;
  color: #909399;
}

.content-wrapper {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.main-content {
  flex: 1;
  background: #141414;
  overflow-y: auto;
  padding: 20px;
  min-height: 0;
}

.disclaimer {
  margin-top: 24px;
  padding: 12px 16px;
  background: #1a1a1a;
  border: 1px solid #2c2c2c;
  border-radius: 4px;
  font-size: 12px;
  color: #606266;
  text-align: center;
}
</style>