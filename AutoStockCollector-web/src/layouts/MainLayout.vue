<template>
  <el-container class="main-layout">
    <!-- Sidebar -->
    <el-aside width="220px" class="sidebar">
      <div class="logo">
        <svg class="logo-mark" viewBox="0 0 24 24" width="22" height="22" aria-hidden="true">
          <rect x="3" y="10" width="4" height="9" rx="1" fill="currentColor" opacity="0.45" />
          <rect x="10" y="5" width="4" height="14" rx="1" fill="currentColor" opacity="0.7" />
          <rect x="17" y="8" width="4" height="11" rx="1" fill="currentColor" />
        </svg>
        <span class="logo-text">AutoStockCollector</span>
      </div>
      <el-menu
        :default-active="activeMenu"
        :default-openeds="openedMenus"
        unique-opened
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
          <el-tooltip :content="themeStore.theme === 'dark' ? '切换到浅色' : '切换到暗色'" placement="bottom">
            <el-icon class="theme-toggle" @click="themeStore.toggle()">
              <Sunny v-if="themeStore.theme === 'dark'" />
              <Moon v-else />
            </el-icon>
          </el-tooltip>
          <div class="status-indicator">
            <span :class="['status-dot', collectStore.backendOnline ? 'online' : 'offline']"></span>
            <span class="status-text">{{ collectStore.backendOnline ? '后端在线' : '后端离线' }}</span>
          </div>
          <el-dropdown v-if="authStore.isLoggedIn" trigger="click" @command="handleUserCommand">
            <div class="user-avatar">
              <el-icon :size="18"><User /></el-icon>
              <span class="user-name">{{ authStore.user?.username }}</span>
            </div>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="profile">
                  <el-icon :size="14"><User /></el-icon>个人中心
                </el-dropdown-item>
                <el-dropdown-item v-if="authStore.isAdmin" command="user-management">
                  <el-icon :size="14"><Setting /></el-icon>用户管理
                </el-dropdown-item>
                <el-dropdown-item divided command="logout">
                  <el-icon :size="14"><SwitchButton /></el-icon>退出登录
                </el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
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
import { useThemeStore } from '@/stores/themeStore'
import { useAuthStore } from '@/stores/authStore'
import AIChatFloat from '@/components/AIChatFloat/index.vue'
import {
  Sunny,
  Moon,
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
  Setting,
  List,
  User,
  SwitchButton,
} from '@element-plus/icons-vue'

const route = useRoute()
const router = useRouter()
const collectStore = useCollectStore()
const themeStore = useThemeStore()
const authStore = useAuthStore()

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

const menuGroups = computed((): MenuGroup[] => [
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
      { key: '/ai-monitor',      label: 'AI实时监控',     icon: Monitor },
      { key: '/strategy-pick',   label: '策略选股',       icon: Operation },
      { key: '/ai-picker',       label: '量化选股',       icon: TrendCharts },
      { key: '/stock-analysis',  label: '个股深度分析',    icon: Search },
    ],
  },
  {
    key: 'quant',
    label: '量化交易',
    icon: Operation,
    children: [
      { key: '/position', label: '仓位管理',   icon: Wallet },
      { key: '/workflow', label: '工作流管理',  icon: Operation },
    ],
  },
  {
    key: 'ranking',
    label: '盈利排行榜',
    path: '/ranking',
    icon: TrendCharts,
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
  {
    key: 'settings',
    label: '系统配置',
    icon: Setting,
    children: [
      { key: '/ai-keys',          label: 'AI Key管理',     icon: Key },
      { key: '/ai-agents',        label: 'AI Agent管理',   icon: MagicStick },
      { key: '/strategy-manager', label: '策略管理',       icon: List },
      { key: '/ai-call-history',  label: 'AI调用记录',    icon: Monitor },
      ...(authStore.isAdmin ? [{ key: '/platform-config', label: '平台配置', icon: Setting }] : []),
      ...(authStore.isAdmin ? [{ key: '/user-management', label: '用户管理', icon: User }] : []),
    ],
  },
])

function findLeaf(path: string): string | undefined {
  for (const group of menuGroups.value) {
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
  const group = menuGroups.value.find(
    g => g.children && g.children.some(c => path.startsWith(c.key)),
  )
  return group ? [group.key] : []
})

function handleMenuSelect(path: string) {
  router.push(path).catch(() => {})
}

const currentTitle = computed(() => {
  const path = route.path
  for (const group of menuGroups.value) {
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

function handleUserCommand(cmd: string) {
  if (cmd === 'logout') {
    authStore.logout()
    router.push('/login')
  } else if (cmd === 'profile') {
    router.push('/profile')
  } else if (cmd === 'user-management') {
    router.push('/user-management')
  }
}

onMounted(() => {
  collectStore.checkHealth()
  if (authStore.isLoggedIn) {
    authStore.refreshProfile()
  }
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
  background: var(--bg-page);
}

.sidebar {
  background: var(--bg-card);
  border-right: 1px solid var(--border-color);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  box-shadow: var(--shadow-sm);
  z-index: 10;
}

.logo {
  height: 60px;
  display: flex;
  align-items: center;
  padding: 0 20px;
  border-bottom: 1px solid var(--border-color);
  gap: 12px;
}

.logo-mark {
  color: var(--el-color-primary);
  flex-shrink: 0;
}

.logo-text {
  font-size: 15px;
  font-weight: 700;
  letter-spacing: 0.02em;
  color: var(--text-primary);
  white-space: nowrap;
}

.el-menu {
  border-right: none;
  flex: 1;
  overflow-y: auto;
  --el-menu-bg-color: var(--bg-card);
  --el-menu-text-color: var(--text-secondary);
  --el-menu-hover-bg-color: var(--bg-hover-subtle);
  padding: 8px 0;
}

.el-menu-item {
  margin: 0 12px; /* 移除垂直方向的 margin，改为 0 */
  border-radius: var(--radius-sm);
  height: 44px;
  line-height: 44px;
  display: flex;
  align-items: center;
  justify-content: flex-start;
}

.el-menu-item.is-active {
  background-color: var(--bg-hover);
  color: var(--el-color-primary);
  font-weight: 600;
}

.el-menu-item .el-icon {
  margin-right: 12px;
  width: 20px;
  text-align: center;
}

/* 移除 :deep(.el-sub-menu__title) 的 margin，只保留左右的 margin，以解决折叠时的抖动问题 */
:deep(.el-sub-menu__title) {
  margin: 0 12px; 
  border-radius: var(--radius-sm);
  height: 44px;
  line-height: 44px;
  display: flex;
  align-items: center;
  justify-content: flex-start;
}

:deep(.el-sub-menu__title .el-icon) {
  margin-right: 12px;
  width: 20px;
  text-align: center;
}

.header {
  background: var(--bg-card);
  border-bottom: 1px solid var(--border-color);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px;
  box-shadow: var(--shadow-sm);
  z-index: 9;
}

.header-left {
  display: flex;
  align-items: center;
}

.page-title {
  font-size: var(--fs-page-title);
  font-weight: 600;
  color: var(--text-primary);
}

.theme-toggle {
  cursor: pointer;
  font-size: 20px;
  color: var(--text-muted);
  transition: color 0.2s, transform 0.2s;
}

.theme-toggle:hover {
  color: var(--el-color-primary);
  transform: scale(1.1);
}

.header-right {
  display: flex;
  align-items: center;
  gap: 20px;
}

.status-indicator {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 12px;
  background: var(--bg-soft);
  border-radius: 20px;
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}

.status-dot.online {
  background: var(--el-color-success);
  box-shadow: 0 0 8px var(--el-color-success);
}

.status-dot.offline {
  background: var(--el-color-danger);
  box-shadow: 0 0 8px var(--el-color-danger);
}

.status-text {
  font-size: 13px;
  font-weight: 500;
  color: var(--text-secondary);
}

.content-wrapper {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background: var(--bg-page);
}

.main-content {
  flex: 1;
  background: var(--bg-page);
  overflow-y: auto;
  scrollbar-gutter: stable; /* 预留滚动条空间，防止出现滚动条时页面整体左移 */
  padding: 1.5%;
  min-height: 0;
}

.user-avatar {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 4px 12px;
  cursor: pointer;
  border-radius: 20px;
  background: var(--bg-soft);
  color: var(--text-secondary);
  transition: background 0.2s, color 0.2s;
}

.user-avatar:hover {
  background: var(--bg-hover-subtle);
  color: var(--el-color-primary);
}

.user-name {
  font-size: 13px;
  font-weight: 500;
}
</style>