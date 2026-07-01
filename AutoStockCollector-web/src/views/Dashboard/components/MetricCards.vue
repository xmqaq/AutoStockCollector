<template>
  <el-row v-if="!dataLoaded" :gutter="16" class="metric-cards">
    <el-col v-for="i in 4" :key="i" :span="6">
      <div class="metric-card sk-card">
        <div class="sk-line sk-label-line"></div>
        <div class="sk-line sk-value-line"></div>
      </div>
    </el-col>
  </el-row>
  <el-row v-else :gutter="16" class="metric-cards">
    <!-- Card 1: Account Balance -->
    <el-col :span="6">
      <div class="metric-card metric-card--primary">
        <div class="metric-content">
          <div class="metric-label">模拟盘总资产</div>
          <div class="metric-value-wrapper">
            <div class="metric-value num">¥{{ fmtAmount(accountData?.total_asset || 0) }}</div>
            <div class="metric-sub" :class="getProfitClass(accountData?.today_pnl)">
              {{ accountData?.today_pnl >= 0 ? '+' : '' }}{{ fmtAmount(accountData?.today_pnl || 0) }} (今日)
            </div>
          </div>
        </div>
        <el-icon class="metric-icon-bg"><Wallet /></el-icon>
      </div>
    </el-col>
    <!-- Card 2: Strategy Win Rate -->
    <el-col :span="6">
      <div class="metric-card">
        <div class="metric-content">
          <div class="metric-label">AI 策略组合胜率</div>
          <div class="metric-value-wrapper">
            <div class="metric-value num text-gradient">{{ accountStats?.win_rate || 0 }}%</div>
            <div class="metric-sub">/ {{ accountStats?.total_trades || 0 }} 笔</div>
          </div>
        </div>
        <el-icon class="metric-icon-bg"><Trophy /></el-icon>
      </div>
    </el-col>
    <!-- Card 3: AI Picks -->
    <el-col :span="6">
      <div class="metric-card" style="cursor: pointer" @click="router.push('/ai-picker')">
        <div class="metric-content">
          <div class="metric-label">今日 AI 推荐</div>
          <div class="metric-value-wrapper">
            <div class="metric-value num">{{ aiPicksCount }}</div>
            <div class="metric-sub">只精选标的</div>
          </div>
        </div>
        <el-icon class="metric-icon-bg"><MagicStick /></el-icon>
      </div>
    </el-col>
    <!-- Card 4: Market Sentiment -->
    <el-col :span="6">
      <div class="metric-card">
        <div class="metric-content">
          <div class="metric-label">大盘情绪指数</div>
          <div class="metric-value-wrapper">
            <div class="metric-value num" :style="{ color: getSentimentColor(sentimentScore) }">{{ sentimentScore }}</div>
            <div class="metric-sub">{{ getSentimentText(sentimentScore) }}</div>
          </div>
        </div>
        <el-icon class="metric-icon-bg"><Odometer /></el-icon>
      </div>
    </el-col>
  </el-row>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { fmtAmount } from '@/utils/format'
import { Wallet, Trophy, MagicStick, Odometer } from '@element-plus/icons-vue'
import { paperApi } from '@/api/paper'
import { strategyPickApi } from '@/api/strategyPick'

const props = defineProps<{
  dataLoaded: boolean
}>()

const router = useRouter()
const accountData = ref<any>(null)
const accountStats = ref<any>(null)
const aiPicksCount = ref(0)
const sentimentScore = ref(50)

function getProfitClass(val: number) {
  if (!val) return ''
  return val > 0 ? 'text-danger' : 'text-success' // Red for up, Green for down
}

function getSentimentColor(score: number) {
  if (score >= 80) return 'var(--el-color-danger)' // Extreme greed
  if (score >= 60) return '#ffb822' // Greed
  if (score <= 20) return 'var(--el-color-success)' // Extreme fear
  if (score <= 40) return 'var(--text-muted)' // Fear
  return 'var(--text-primary)' // Neutral
}

function getSentimentText(score: number) {
  if (score >= 80) return '极度贪婪'
  if (score >= 60) return '贪婪'
  if (score <= 20) return '极度恐慌'
  if (score <= 40) return '恐慌'
  return '中性'
}

async function loadData() {
  try {
    const [accRes, statsRes, picksRes, rankingRes] = await Promise.all([
      paperApi.getAccount(),
      paperApi.getStats(),
      strategyPickApi.getHistory(), // Just get latest to see if it's today
      paperApi.getRanking(true) // Get live ranking for accurate total_asset
    ])
    
    let accountInfo = null
    // Some API wrappers return unwrapped data, some return AxiosResponse
    if (accRes && (accRes as any).data) {
      accountInfo = (accRes as any).data.data || (accRes as any).data || accRes
    } else if (accRes) {
      accountInfo = accRes
    }
    
    // Find my live ranking data to get accurate total asset and today pnl
    let myLiveStats = null
    if (rankingRes && rankingRes.length > 0) {
      if (accountInfo) {
        myLiveStats = rankingRes.find((r: any) => r.user_id === accountInfo.user_id)
      }
      // Fallback if user_id doesn't match exactly (e.g., admin vs default mapping)
      if (!myLiveStats) {
        myLiveStats = rankingRes[0]
      }
    }
    
    // Merge live stats into account data
    if (accountInfo || myLiveStats) {
       accountData.value = {
         ...(accountInfo || {}),
         total_asset: myLiveStats ? myLiveStats.total_asset : (accountInfo?.cash_balance || 0),
         today_pnl: myLiveStats ? myLiveStats.today_pnl : 0
       }
    }

    if (statsRes && (statsRes as any).data) {
      accountStats.value = (statsRes as any).data.data || (statsRes as any).data || statsRes
    } else if (statsRes) {
      accountStats.value = statsRes
    }
    
    if (picksRes.data?.data && picksRes.data.data.length > 0) {
      const latest = picksRes.data.data[0]
      const today = new Date().toISOString().slice(0, 10)
      
      // Even if it's not today, we want to show the latest count to avoid showing 0 if the cron runs at 1 AM.
      // But we will still try to fetch the detailed results for accurate length.
      try {
        const resultRes = await strategyPickApi.getResult(latest.run_id)
        if (resultRes.data?.data) {
          const picksArray = (resultRes.data.data as any).results || resultRes.data.data.picks || []
          aiPicksCount.value = picksArray.length
        } else {
          // Fallback to checking if the history summary has a count
          aiPicksCount.value = (latest as any).total_count || (latest as any).picks_count || 0
        }
      } catch {
        aiPicksCount.value = (latest as any).total_count || (latest as any).picks_count || 0
      }
    }
    
    // 板块舆情接口已随监控重构移除，保留中性默认值
    sentimentScore.value = 55
  } catch (err) {
    console.error('Failed to load metric card data', err)
  }
}

onMounted(() => {
  loadData()
})
</script>

<style scoped>
/* --- Metric Cards --- */
.metric-cards {
  margin-bottom: 8px;
}

.metric-card {
  position: relative;
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
  padding: 12px 16px;
  box-shadow: var(--shadow-sm);
  overflow: hidden;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  display: flex;
  justify-content: space-between;
  align-items: center;
  height: 100%;
  min-height: 90px;
  container-type: inline-size;
}

.metric-card:hover {
  transform: translateY(-2px); /* Subtler hover */
  box-shadow: var(--shadow-md);
  border-color: var(--brand-300);
}

.metric-card--primary {
  background: linear-gradient(135deg, var(--brand-600) 0%, var(--brand-800) 100%);
  border: none;
  box-shadow: 0 4px 16px -4px rgba(79, 70, 229, 0.4);
}

.metric-card--primary .metric-label,
.metric-card--primary .metric-value,
.metric-card--primary .metric-icon-bg {
  color: #fff;
}

.metric-card--primary:hover {
  box-shadow: 0 8px 24px -6px rgba(79, 70, 229, 0.5);
  border-color: transparent;
}

.metric-content {
  position: relative;
  z-index: 2;
  display: flex;
  flex-direction: column;
  gap: 4px;
  width: 100%;
  padding-right: 36px; /* Leave space for background icon */
}

.metric-label {
  font-size: clamp(11px, 4cqw, 13px);
  color: var(--text-secondary);
  font-weight: 500;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.metric-value-wrapper {
  display: flex;
  align-items: baseline;
  gap: 6px;
  flex-wrap: nowrap; /* Prevent wrapping, force scale down */
  width: 100%;
}

.metric-value {
  font-size: clamp(16px, 9cqw, 22px);
  font-weight: 700;
  color: var(--text-primary);
  line-height: 1.1;
  letter-spacing: -0.5px;
  white-space: nowrap;
}

.metric-sub {
  font-size: clamp(10px, 3.5cqw, 12px);
  color: var(--text-muted);
  font-weight: 500;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  flex: 1;
}

.text-gradient {
  background: linear-gradient(135deg, var(--brand-500) 0%, #3b82f6 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}

.metric-icon-bg {
  position: absolute;
  right: 12px; /* Adjusted position */
  top: 50%;
  transform: translateY(-50%);
  font-size: 48px; /* Reduced from 64px */
  color: var(--brand-50);
  z-index: 1;
  opacity: 0.8;
  pointer-events: none;
  transition: transform 0.4s ease;
}

.metric-card:hover .metric-icon-bg {
  transform: translateY(-50%) scale(1.1);
}

.metric-card--primary .metric-icon-bg {
  opacity: 0.15;
  color: #fff;
}

/* Status Dot */
.status-dot-large {
  width: 12px;
  height: 12px;
  border-radius: 50%;
  position: relative;
}

.status-dot-large.online {
  background-color: #10b981;
  box-shadow: 0 0 12px rgba(16, 185, 129, 0.6);
}

.status-dot-large.offline {
  background-color: #ef4444;
  box-shadow: 0 0 12px rgba(239, 68, 68, 0.6);
}

/* --- Skeleton --- */
@keyframes shimmer {
  0%   { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}

.sk-line {
  background: linear-gradient(
    90deg,
    var(--bg-hover-subtle) 25%,
    var(--bg-hover) 50%,
    var(--bg-hover-subtle) 75%
  );
  background-size: 200% 100%;
  animation: shimmer 1.5s infinite;
  border-radius: 4px;
}

.sk-card {
  flex-direction: column;
  align-items: flex-start;
  gap: 16px;
}

.sk-label-line { height: 16px; width: 40%; }
.sk-value-line { height: 32px; width: 70%; }
</style>
