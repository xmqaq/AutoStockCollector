import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      component: () => import('@/layouts/MainLayout.vue'),
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
          path: 'ai-picker',
          name: 'AIPicker',
          component: () => import('@/views/AIPicker/index.vue'),
          meta: { title: '量化选股' },
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
          path: 'memory-settings',
          name: 'MemorySettings',
          component: () => import('@/views/MemorySettings/index.vue'),
          meta: { title: '记忆设置' },
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
          path: 'multi-agent',
          name: 'MultiAgent',
          component: () => import('@/views/MultiAgent/index.vue'),
          meta: { title: '多Agent分析' },
        },
        {
          path: 'workflow',
          name: 'Workflow',
          component: () => import('@/views/Workflow/index.vue'),
          meta: { title: '工作流管理' },
        },
        {
          path: 'factor-lab',
          name: 'FactorLab',
          component: () => import('@/views/FactorLab/index.vue'),
          meta: { title: '因子平台' },
        },
        {
          path: 'todo',
          name: 'Todo',
          component: () => import('@/views/Todo/index.vue'),
          meta: { title: '待办事项' },
        },
        {
          path: 'signals',
          name: 'Signals',
          component: () => import('@/views/Signals/index.vue'),
          meta: { title: 'Agent 信号源' },
        },
        {
          path: 'reflections',
          name: 'Reflections',
          component: () => import('@/views/Reflections/index.vue'),
          meta: { title: '决策反思' },
        },
      ],
    },
  ],
})

export default router
