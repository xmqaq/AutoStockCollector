<template>
  <div class="ap-page">
    <div class="ap-toolbar">
      <span class="ap-title">AI 智能选股</span>
      <div class="ap-controls">
        <el-input v-model.number="topN" size="small" style="width:110px"><template #prepend>选 N</template></el-input>
        <el-input v-model.number="candidatePool" size="small" style="width:140px"><template #prepend>候选池</template></el-input>
        <el-button type="primary" size="small" :loading="running" @click="runPick">立即重跑</el-button>
        <el-button size="small" :loading="loading" @click="loadResults">刷新结果</el-button>
      </div>
    </div>

    <div v-if="result" class="ap-meta">
      <span>策略：{{ result.strategy }}</span>
      <span v-if="result.universe_count">全市场 {{ result.universe_count }} → 候选 {{ result.candidate_count }} → 精选 {{ result.picks.length }}</span>
      <span>更新：{{ fmtTime(result.timestamp) }}</span>
    </div>

    <el-table v-if="result?.picks?.length" :data="result.picks" stripe class="ap-table">
      <el-table-column type="index" label="#" width="50" />
      <el-table-column prop="code" label="代码" width="120">
        <template #default="{ row }"><span class="ap-code" @click="goAnalysis(row.code)">{{ row.code }}</span></template>
      </el-table-column>
      <el-table-column prop="name" label="名称" width="120" />
      <el-table-column label="综合评分" width="140" sortable :sort-by="(r: AIPick) => r.composite">
        <template #default="{ row }">
          <el-progress :percentage="Math.round(row.composite)" :color="scoreColor(row.composite)" />
        </template>
      </el-table-column>
      <el-table-column prop="recommendation" label="AI建议" min-width="160" show-overflow-tooltip />
      <el-table-column prop="source" label="来源" width="90" />
    </el-table>
    <el-empty v-else :description="loading ? '加载中…' : '暂无选股结果，点击「立即重跑」'" />

    <p v-if="result" class="ap-disclaimer">{{ result.disclaimer }}</p>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import dayjs from 'dayjs'
import { aiServiceApi, type AIPickResult, type AIPick } from '@/api/ai'

const router = useRouter()
const result = ref<AIPickResult | null>(null)
const loading = ref(false)
const running = ref(false)
const topN = ref(10)
const candidatePool = ref(50)

function scoreColor(v: number): string {
  if (v >= 70) return '#3a8a52'
  if (v >= 50) return '#d0a020'
  return '#a04040'
}
function fmtTime(t: string): string {
  return t ? dayjs(t).format('MM-DD HH:mm') : '--'
}
function goAnalysis(code: string) {
  router.push({ path: '/stock-analysis', query: { code } })
}

async function loadResults() {
  loading.value = true
  try {
    const res = await aiServiceApi.pickResults()
    result.value = res.data?.data || null
  } catch {
    ElMessage.error('加载选股结果失败')
  } finally {
    loading.value = false
  }
}

async function runPick() {
  running.value = true
  try {
    const res = await aiServiceApi.pickRun({ top_n: topN.value, candidate_pool: candidatePool.value })
    if (res.data?.success) {
      result.value = res.data.data
      ElMessage.success('选股完成')
    } else {
      ElMessage.error(res.data?.error || '选股失败')
    }
  } catch {
    ElMessage.error('选股请求失败（耗时较长，请稍后刷新结果）')
  } finally {
    running.value = false
  }
}

onMounted(loadResults)
</script>

<style scoped>
.ap-page { display: flex; flex-direction: column; gap: 14px; }
.ap-toolbar { display: flex; justify-content: space-between; align-items: center; }
.ap-title { font-size: 15px; font-weight: 700; color: #d8daf0; }
.ap-controls { display: flex; gap: 8px; align-items: center; }
.ap-meta { display: flex; gap: 18px; font-size: 12px; color: #606080; }
.ap-table { background: transparent; }
.ap-code { color: #5a7af0; cursor: pointer; }
.ap-code:hover { text-decoration: underline; }
.ap-disclaimer { font-size: 11px; color: #44445a; text-align: center; }
</style>
