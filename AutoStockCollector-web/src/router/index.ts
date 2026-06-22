import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/login',
      name: 'Login',
      component: () => import('@/views/Login/index.vue'),
      meta: { title: '登录', noAuth: true },
    },
    {
      path: '/',
      component: () => import('@/layouts/MainLayout.vue'),
      meta: { requiresAuth: true },
      children: [
        {
          path: '',
          redirect: '/dashboard',
        },
        {
          path: 'dashboard',
          name: 'Dashboard',
          component: () => import('@/views/Dashboard/index.vue'),
          meta: { title: '系统总览' },
        },
        {
          path: 'data-monitor',
          name: 'DataMonitor',
          component: () => import('@/views/DataMonitor/index.vue'),
          meta: { title: '采集中心' },
        },
        {
          path: 'stock-detail',
          name: 'StockDetail',
          component: () => import('@/views/StockDetail/index.vue'),
          meta: { title: '股票详情' },
        },
        {
          path: 'market',
          name: 'Market',
          component: () => import('@/views/Market/index.vue'),
          meta: { title: '实时行情' },
        },
        {
          path: 'stock-analysis',
          name: 'StockAnalysis',
          component: () => import('@/views/StockAnalysis/index.vue'),
          meta: { title: '个股深度分析' },
        },
        {
          path: 'ai-keys',
          name: 'AIKeys',
          component: () => import('@/views/AIKey/index.vue'),
          meta: { title: 'AI Key管理' },
        },
        {
          path: 'ai-agents',
          name: 'AIAgents',
          component: () => import('@/views/AIAgent/index.vue'),
          meta: { title: 'AI Agent管理' },
        },
        {
          path: 'dragon-tiger',
          name: 'DragonTiger',
          component: () => import('@/views/DragonTiger/index.vue'),
          meta: { title: '龙虎榜' },
        },
        {
          path: 'margin-trading',
          name: 'MarginTrading',
          component: () => import('@/views/MarginTrading/index.vue'),
          meta: { title: '融资融券' },
        },
        {
          path: 'sector-flow',
          name: 'SectorFlow',
          component: () => import('@/views/SectorFlow/index.vue'),
          meta: { title: '板块流向' },
        },
        {
          path: 'fund-flow',
          name: 'FundFlow',
          component: () => import('@/views/FundFlow/index.vue'),
          meta: { title: '资金流向排行' },
        },
        {
          path: 'news',
          name: 'News',
          component: () => import('@/views/News/index.vue'),
          meta: { title: '新闻舆情' },
        },
        {
          path: 'research-reports',
          name: 'ResearchReports',
          component: () => import('@/views/ResearchReports/index.vue'),
          meta: { title: '投资研报' },
        },
        {
          path: 'watchlist',
          name: 'Watchlist',
          component: () => import('@/views/Watchlist/index.vue'),
          meta: { title: '自选股' },
        },
        {
          path: 'position',
          name: 'Position',
          component: () => import('@/views/Position/index.vue'),
          meta: { title: '仓位管理' },
        },
        {
          path: 'ranking',
          name: 'Ranking',
          component: () => import('@/views/Ranking/index.vue'),
          meta: { title: '盈利排行榜' },
        },
        {
          path: 'fusion-pick',
          name: 'FusionPick',
          component: () => import('@/views/FusionPick/index.vue'),
          meta: { title: 'AI 智选' },
        },
        {
          path: 'research-analysis',
          name: 'ResearchAnalysis',
          component: () => import('@/views/ResearchAnalysis/index.vue'),
          meta: { title: '投资研报分析' },
        },
        {
          path: 'price-action',
          name: 'PriceAction',
          component: () => import('@/views/PriceAction/index.vue'),
          meta: { title: '价格行为学' },
        },
        {
          path: 'pre-market-radar',
          name: 'PreMarketRadar',
          component: () => import('@/views/AuctionRadar/index.vue'),
          meta: { title: '盘前竞价雷达' },
        },
        {
          path: 'strategy-manager',
          name: 'StrategyManager',
          component: () => import('@/views/StrategyManager/index.vue'),
          meta: { title: '策略管理' },
        },
        {
          path: 'profile',
          name: 'Profile',
          component: () => import('@/views/Profile/index.vue'),
          meta: { title: '个人中心' },
        },
        {
          path: 'user-management',
          name: 'UserManagement',
          component: () => import('@/views/UserManagement/index.vue'),
          meta: { title: '用户管理', adminOnly: true },
        },
        {
          path: 'ai-call-history',
          name: 'AICallHistory',
          component: () => import('@/views/AICallHistory/index.vue'),
          meta: { title: 'AI调用记录' },
        },
        {
          path: 'platform-config',
          name: 'PlatformConfig',
          component: () => import('@/views/PlatformConfig/index.vue'),
          meta: { title: '平台配置', adminOnly: true },
        },
        {
          path: 'ai-monitor',
          name: 'AiMonitor',
          component: () => import('@/views/AiMonitor/index.vue'),
          meta: { title: 'AI实时监控' },
        },
        {
          path: 'todo',
          name: 'Todo',
          component: () => import('@/views/Todo/index.vue'),
          meta: { title: '待办事项' },
        },
      ],
    },
  ],
})

router.beforeEach((to, _from) => {
  const token = localStorage.getItem('auth_token')
  const user = (() => {
    try { return JSON.parse(localStorage.getItem('auth_user') || 'null') } catch { return null }
  })()
  
  if (to.meta.noAuth) {
    return true
  } else if (!token && to.meta.requiresAuth !== false) {
    return { path: '/login', query: { redirect: to.fullPath } }
  } else if (to.meta.adminOnly && user?.role !== 'admin') {
    return '/dashboard'
  } else {
    return true
  }
})

export default router
