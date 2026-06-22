<template>
  <div class="ai-picks-widget" v-loading="loading">
    <div class="widget-header">
      <div class="header-left">
        <h2 class="title"><el-icon><MagicStick /></el-icon> AI 精选股票</h2>
        <span class="subtitle">今日最新推荐</span>
      </div>
      <el-button class="modern-btn" text @click="router.push('/ai-picker')">
        查看全部 →
      </el-button>
    </div>

    <div v-if="!loading && picks.length === 0" class="empty-state">
      <el-empty description="今日暂无 AI 推荐" :image-size="80" />
    </div>

    <div v-else class="picks-list">
      <div v-for="pick in picks.slice(0, 5)" :key="pick.code" class="pick-item" @click="goToStock(pick.code)">
        <div class="pick-main">
          <div class="stock-info">
            <span class="stock-name">{{ pick.name }}</span>
            <span class="stock-code">{{ pick.code }}</span>
          </div>
          <div class="pick-tags">
            <el-tag 
              v-for="tag in (pick.tags || []).slice(0, 2)" 
              :key="tag" 
              size="small" 
              effect="light"
              :type="getTagType(tag)"
            >
              {{ tag }}
            </el-tag>
          </div>
        </div>
        
        <div class="pick-stats">
          <div class="stat-item">
            <span class="stat-label">AI 评分</span>
            <span class="stat-value score">{{ pick.score }}</span>
          </div>
          <div class="stat-item">
            <span class="stat-label">胜率预测</span>
            <span class="stat-value text-danger">{{ pick.win_rate_pred || '--' }}%</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { MagicStick } from '@element-plus/icons-vue'
import { strategyPickApi } from '@/api/strategyPick'

const router = useRouter()
const loading = ref(true)
const picks = ref<any[]>([])

function goToStock(code: string) {
  router.push({ path: '/stock-detail', query: { code } })
}

function getTagType(tag: string) {
  if (tag.includes('龙头') || tag.includes('强势')) return 'danger'
  if (tag.includes('超跌') || tag.includes('低估')) return 'success'
  if (tag.includes('资金') || tag.includes('主力')) return 'warning'
  return 'primary'
}

async function loadData() {
  loading.value = true
  try {
    const res = await strategyPickApi.getHistory()
    if (res.data?.data && res.data.data.length > 0) {
      // Get the latest pick
      const latestRunId = res.data.data[0].run_id
      const resultRes = await strategyPickApi.getResult(latestRunId)
      
      if (resultRes.data?.data) {
         picks.value = (resultRes.data.data as any).results || resultRes.data.data.picks || []
      }
    }
  } catch (err) {
    console.error('Failed to load AI picks for widget', err)
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  loadData()
})
</script>

<style scoped>
.ai-picks-widget {
  display: flex;
  flex-direction: column;
  height: 100%;
}

.widget-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.header-left {
  display: flex;
  align-items: baseline;
  gap: 12px;
}

.title {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
  color: var(--text-primary);
  display: flex;
  align-items: center;
  gap: 8px;
}

.title .el-icon {
  color: var(--brand-500);
}

.subtitle {
  font-size: 13px;
  color: var(--text-muted);
}

.modern-btn {
  color: var(--brand-500);
  font-weight: 500;
}

.modern-btn:hover {
  background-color: var(--brand-50);
}

.empty-state {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
}

.picks-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
  flex: 1;
  overflow-y: auto;
  padding-right: 4px;
}

.pick-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px;
  background: var(--bg-soft);
  border: 1px solid var(--border-light);
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s;
}

.pick-item:hover {
  border-color: var(--brand-300);
  background: var(--bg-card);
  transform: translateY(-2px);
  box-shadow: var(--shadow-sm);
}

.pick-main {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.stock-info {
  display: flex;
  align-items: baseline;
  gap: 8px;
}

.stock-name {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
}

.stock-code {
  font-size: 13px;
  font-family: monospace;
  color: var(--text-muted);
  background: var(--bg-page);
  padding: 2px 6px;
  border-radius: 4px;
}

.pick-tags {
  display: flex;
  gap: 6px;
}

.pick-stats {
  display: flex;
  gap: 24px;
}

.stat-item {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 4px;
}

.stat-label {
  font-size: 12px;
  color: var(--text-muted);
}

.stat-value {
  font-size: 18px;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
}

.score {
  color: var(--brand-600);
}

.text-danger {
  color: var(--el-color-danger);
}
</style>