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
          meta: { title: '采集监控' },
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
          path: 'ai-analysis',
          name: 'AIAnalysis',
          component: () => import('@/views/AIAnalysis/index.vue'),
          meta: { title: 'AI分析' },
        },
        {
          path: 'smart-pick',
          name: 'SmartPick',
          component: () => import('@/views/SmartPick/index.vue'),
          meta: { title: '智能选股' },
        },
        {
          path: 'ai-keys',
          name: 'AIKeys',
          component: () => import('@/views/AIKey/index.vue'),
          meta: { title: 'AI Key管理' },
        },
        {
          path: 'strategy-back',
          name: 'StrategyBack',
          component: () => import('@/views/StrategyBack/index.vue'),
          meta: { title: '策略回测' },
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
          path: 'strategy-config',
          name: 'StrategyConfig',
          component: () => import('@/views/StrategyConfig/index.vue'),
          meta: { title: '策略管理' },
        },
      ],
    },
  ],
})

export default router
