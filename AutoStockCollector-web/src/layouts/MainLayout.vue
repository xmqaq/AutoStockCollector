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
        :default-openeds="openedMenus"
        background-color="#141414"
        text-color="#c0c4cc"
        active-text-color="#409eff"
        @select="handleMenuSelect"
      >
        <template v-for="group in menuGroups" :key="group.key">
          <el-menu-item v-if="!group.children" :index="group.path!">
            <el-icon><component :is="group.icon" /></el-icon>
            <template #title>{{ group.label }}</template>
          </el-menu-item>
          <el-sub-menu v-else :index="group.key">
            <template #title>
              <el-icon><component :is="group.icon" /></el-icon>
              <span>{{ group.label }}</span>
            </template>
            <el-menu-item
              v-for="child in group.children"
              :key="child.key"
              :index="child.key"
            >
              <el-icon><component :is="child.icon" /></el-icon>
              <template #title>{{ child.label }}</template>
            </el-menu-item>
          </el-sub-menu>
        </template>
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
      </el-main>

      <!-- AI Chat Float Button -->
      <AIChatFloat />
    </el-container>
  </el-container>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, type Component } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useCollectStore } from '@/stores/collectStore'
import AIChatFloat from '@/components/AIChatFloat/index.vue'
import {
  DataAnalysis,
  Monitor,
  TrendCharts,
  MagicStick,
  Lightning,
  Connection,
  Promotion,
  ChatDotRound,
  StarFilled,
  Odometer,
  Key,
  Wallet,
  Search,
  Operation,
  EditPen,
} from '@element-plus/icons-vue'

const route = useRoute()
const router = useRouter()
const collectStore = useCollectStore()

interface MenuChild {
  key: string
  label: string
  icon: Component
}

interface MenuGroup {
  key: string
  label: string
  icon: Component
  path?: string
  children?: MenuChild[]
}

const menuGroups: MenuGroup[] = [
  {
    key: 'system',
    label: '系统总览',
    path: '/dashboard',
    icon: DataAnalysis,
  },
  {
    key: 'data-center',
    label: '数据中心',
    icon: Monitor,
    children: [
      { key: '/data-monitor', label: '采集中心', icon: Monitor },
      { key: '/stock-detail', label: '股票详情', icon: TrendCharts },
      { key: '/market', label: '实时行情', icon: Odometer },
      { key: '/dragon-tiger', label: '龙虎榜', icon: Lightning },
      { key: '/margin-trading', label: '融资融券', icon: Connection },
      { key: '/sector-flow', label: '板块流向', icon: Promotion },
      { key: '/fund-flow', label: '资金流向排行', icon: TrendCharts },
      { key: '/news', label: '新闻舆情', icon: ChatDotRound },
    ],
  },
  {
    key: 'ai',
    label: 'AI智能',
    icon: MagicStick,
    children: [
      { key: '/ai-picker', label: '量化选股', icon: TrendCharts },
      { key: '/stock-analysis', label: '个股深度分析', icon: Search },
      { key: '/ai-keys', label: 'AI Key管理', icon: Key },
      { key: '/ai-agents', label: 'AI Agent管理', icon: MagicStick },
    ],
  },
  {
    key: 'quant',
    label: '量化交易',
    icon: Operation,
    children: [
      { key: '/position', label: '仓位管理', icon: Wallet },
      { key: '/workflow', label: '工作流管理', icon: Operation },
    ],
  },
  {
    key: 'factor-lab',
    label: '因子平台',
    icon: Operation,
    children: [
      { key: '/factor-lab', label: '因子平台', icon: Operation },
    ],
  },
  {
    key: 'watchlist',
    label: '自选股',
    path: '/watchlist',
    icon: StarFilled,
  },
  {
    key: 'todo',
    label: '待办事项',
    path: '/todo',
    icon: EditPen,
  },
]

function findLeaf(path: string): string | undefined {
  for (const group of menuGroups) {
    if (group.children) {
      const child = group.children.find(c => path.startsWith(c.key))
      if (child) return child.key
    } else if (group.path && path.startsWith(group.path)) {
      return group.path
    }
  }
}

const activeMenu = computed(() => findLeaf(route.path) || route.path)

const openedMenus = computed(() => {
  const path = route.path
  const group = menuGroups.find(
    g => g.children && g.children.some(c => path.startsWith(c.key)),
  )
  return group ? [group.key] : []
})

function handleMenuSelect(path: string) {
  router.push(path).catch(() => {})
}

const currentTitle = computed(() => {
  const path = route.path
  for (const group of menuGroups) {
    if (group.children) {
      const child = group.children.find(c => path.startsWith(c.key))
      if (child) return child.label
    } else if (group.path && path.startsWith(group.path)) {
      return group.label
    }
  }
  return 'AutoStockCollector'
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


</style>