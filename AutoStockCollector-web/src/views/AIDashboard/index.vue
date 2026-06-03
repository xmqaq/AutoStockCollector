<template>
  <div class="hub-page">
    <div class="hub-header">
      <span class="hub-title">🧠 AI 智能中枢</span>
      <span class="hub-sub">一体化 AI 股票服务</span>
    </div>

    <div class="hub-entries">
      <div class="hub-entry" @click="go('/ai-picker')">
        <div class="hub-entry-icon">📈</div>
        <div class="hub-entry-title">量化选股</div>
        <div class="hub-entry-desc">多因子模型 · AI解读</div>
      </div>
      <div class="hub-entry" @click="go('/stock-analysis')">
        <div class="hub-entry-icon">🔍</div>
        <div class="hub-entry-title">个股深度分析</div>
        <div class="hub-entry-desc">四维评分 + AI 研判</div>
      </div>
      <div class="hub-entry" @click="go('/stock-analysis')">
        <div class="hub-entry-icon">💡</div>
        <div class="hub-entry-title">买卖参考建议</div>
        <div class="hub-entry-desc">基于分析的操作参考</div>
      </div>
    </div>

    <el-card shadow="never" class="hub-card">
      <template #header>
        <div class="hub-card-head">
          <span>今日 AI 选股</span>
          <el-button size="small" text @click="go('/ai-picker')">查看全部 →</el-button>
        </div>
      </template>
      <el-table v-if="picks.length" :data="picks" size="small" stripe>
        <el-table-column type="index" label="#" width="48" />
        <el-table-column prop="code" label="代码" width="110">
          <template #default="{ row }"><span class="hub-code" @click="goAnalysis(row.code)">{{ row.code }}</span></template>
        </el-table-column>
        <el-table-column prop="name" label="名称" width="110" />
        <el-table-column label="评分" width="90">
          <template #default="{ row }"><span :style="{ color: scoreColor(row.composite) }">{{ row.composite.toFixed(0) }}</span></template>
        </el-table-column>
        <el-table-column prop="recommendation" label="AI建议" min-width="140" show-overflow-tooltip />
      </el-table>
      <el-empty v-else description="暂无选股结果" :image-size="60" />
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { aiServiceApi, type AIPickResult } from '@/api/ai'

const router = useRouter()
const result = ref<AIPickResult | null>(null)

const picks = computed(() => (result.value?.picks || []).slice(0, 8))

function go(path: string) { router.push(path) }
function goAnalysis(code: string) { router.push({ path: '/stock-analysis', query: { code } }) }
function scoreColor(v: number): string {
  if (v >= 70) return '#3a8a52'
  if (v >= 50) return '#d0a020'
  return '#a04040'
}

async function load() {
  try {
    const res = await aiServiceApi.pickResults()
    result.value = res.data?.data || null
  } catch {
    result.value = null
  }
}
onMounted(load)
</script>

<style scoped>
.hub-page { display: flex; flex-direction: column; gap: 16px; }
.hub-header { display: flex; align-items: baseline; gap: 10px; }
.hub-title { font-size: 18px; font-weight: 800; color: #d8daf0; }
.hub-sub { font-size: 12px; color: #606080; }
.hub-entries { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; }
.hub-entry { background: #0c0c14; border: 1px solid #18182a; border-radius: 10px; padding: 18px; cursor: pointer; transition: all 0.15s; }
.hub-entry:hover { border-color: #3a3a5a; transform: translateY(-2px); }
.hub-entry-icon { font-size: 26px; }
.hub-entry-title { font-size: 14px; font-weight: 600; color: #c8cae8; margin-top: 8px; }
.hub-entry-desc { font-size: 11px; color: #606080; margin-top: 4px; }
.hub-card { background: #0c0c14; border: 1px solid #18182a; }
.hub-card :deep(.el-card__header) { color: #c8cae8; font-size: 13.5px; font-weight: 600; }
.hub-card-head { display: flex; justify-content: space-between; align-items: center; }
.hub-code { color: #5a7af0; cursor: pointer; }
.hub-code:hover { text-decoration: underline; }
</style>
