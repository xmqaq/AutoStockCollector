<template>
  <div class="debate-panel">
    <el-card shadow="never" class="section-card">
      <template #header>
        <div class="header-toolbar">
          <span>LangGraph 多空分析编排</span>
          <el-tag v-if="store.stockCode" type="info">
            分析中: {{ store.stockCode }}
          </el-tag>
        </div>
      </template>

      <div class="task-config">
        <el-input v-model="stockCode" placeholder="输入股票代码（如 000001）" style="width: 180px" clearable />
        <el-select v-model="stockCode" placeholder="或从自选选择" filterable clearable style="width: 180px">
          <el-option
            v-for="s in watchlist"
            :key="s.code"
            :label="`${s.code} ${s.name}`"
            :value="s.code"
          />
        </el-select>
        <el-button
          type="primary"
          @click="startAnalysis"
          :loading="store.isAnalyzing"
          :icon="MagicStick"
        >
          开始分析
        </el-button>
      </div>
    </el-card>

    <el-card v-if="store.nodes.length > 0" shadow="never" class="section-card">
      <template #header>
        <div class="section-header">
          <span>编排节点执行进度</span>
          <el-progress :percentage="store.overallProgress" :stroke-width="6" style="width:200px" />
        </div>
      </template>
      <div class="node-grid">
        <div v-for="node in store.nodes" :key="node.node_id" :class="['node-item', node.status]">
          <el-icon v-if="node.status === 'completed'" class="node-icon done"><CircleCheck /></el-icon>
          <el-icon v-else-if="node.status === 'running'" class="node-icon loading is-loading"><Loading /></el-icon>
          <el-icon v-else-if="node.status === 'error'" class="node-icon error"><CloseBold /></el-icon>
          <el-icon v-else class="node-icon idle"><MoreFilled /></el-icon>
          <span class="node-label">{{ node.name || node.node_id }}</span>
        </div>
      </div>
    </el-card>

    <el-card v-if="store.verdict" shadow="never" class="section-card verdict-card">
      <template #header>
        <div class="section-header">
          <span>最终裁决</span>
          <el-tag :type="getVerdictType(store.verdict)" size="large">
            {{ store.verdict.recommendation || '已生成' }}
          </el-tag>
        </div>
      </template>
      <div class="verdict-content md-content" v-html="renderMd(formatVerdict(store.verdict))"></div>
    </el-card>

    <el-card v-if="store.error" shadow="never" class="section-card error-card">
      <template #header><span>错误信息</span></template>
      <p>{{ store.error }}</p>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useOrchestrationStore } from '@/stores/orchestrationStore'
import { ElMessage } from 'element-plus'
import { MagicStick, CircleCheck, MoreFilled, Loading, CloseBold } from '@element-plus/icons-vue'
import { watchlistApi } from '@/api/watchlist'

const store = useOrchestrationStore()

const stockCode = ref('')
const watchlist = ref<{ code: string; name: string }[]>([])

function getVerdictType(v: any) {
  const rec = v?.recommendation || v?.suggestion || ''
  if (rec.includes('买入') || rec.includes('看多')) return 'success'
  if (rec.includes('观望') || rec.includes('中性')) return 'warning'
  if (rec.includes('回避') || rec.includes('看空')) return 'danger'
  return 'info'
}

function formatVerdict(v: any): string {
  const lines: string[] = []
  if (v.recommendation) lines.push(`**建议**: ${v.recommendation}`)
  if (v.bullScore !== undefined) lines.push(`**多方评分**: ${v.bullScore}`)
  if (v.bearScore !== undefined) lines.push(`**空方评分**: ${v.bearScore}`)
  if (v.tendency) lines.push(`**倾向**: ${v.tendency}`)
  if (v.judgeVerdict) lines.push(`\n${v.judgeVerdict}`)
  if (v.reasoning) lines.push(`\n${v.reasoning}`)
  if (v.analysis) lines.push(`\n${v.analysis}`)
  if (v.conclusion) lines.push(`\n${v.conclusion}`)
  return lines.join('\n\n')
}

function renderMd(text: string): string {
  if (!text) return ''
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/^### (.+)$/gm, '<h4>$1</h4>')
    .replace(/^## (.+)$/gm, '<h3>$1</h3>')
    .replace(/^# (.+)$/gm, '<h2>$1</h2>')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\n/g, '<br>')
}

async function startAnalysis() {
  if (!stockCode.value) {
    ElMessage.warning('请输入股票代码')
    return
  }
  await store.startAnalysis(stockCode.value)
}

async function loadWatchlist() {
  try {
    const res = await watchlistApi.getWatchlist()
    watchlist.value = res.data?.data || res.data || []
    if (watchlist.value.length > 0) {
      stockCode.value = watchlist.value[0].code
    }
  } catch {
    watchlist.value = []
  }
}

onMounted(() => {
  loadWatchlist()
})
</script>

<style scoped>
.debate-panel { display: flex; flex-direction: column; gap: 16px; }
.header-toolbar { display: flex; justify-content: space-between; align-items: center; }
.task-config { display: flex; gap: 12px; align-items: center; }
.section-header { display: flex; justify-content: space-between; align-items: center; }
.section-card { background: var(--bg-card); border: 1px solid var(--border-color); }
.section-card :deep(.el-card__header) {
  border-bottom: 1px solid var(--border-color); padding: 12px 16px;
  color: var(--text-primary); font-size: 14px; font-weight: 600;
}
.node-grid { display: flex; flex-wrap: wrap; gap: 8px; }
.node-item {
  display: flex; align-items: center; gap: 6px;
  padding: 6px 12px; border-radius: 6px;
  font-size: 12px; background: var(--border-color); color: var(--text-muted);
  border: 1px solid transparent;
}
.node-item.completed { color: #67c23a; border-color: #67c23a; }
.node-item.running { color: #e6a23c; border-color: #e6a23c; }
.node-item.error { color: #f56c6c; border-color: #f56c6c; }
.node-icon { font-size: 14px; }
.node-icon.done { color: #67c23a; }
.node-icon.loading { color: #e6a23c; }
.node-icon.error { color: #f56c6c; }
.node-icon.idle { color: #4a4a4a; }
.verdict-card { border: 1px solid #409eff; }
.verdict-content { font-size: 13px; color: var(--text-secondary); line-height: 1.7; padding: 8px 0; }
.error-card { border: 1px solid #f56c6c; }
.error-card p { color: #f56c6c; font-size: 13px; }
.md-content :deep(strong) { color: var(--text-primary); }
.md-content :deep(h2), .md-content :deep(h3), .md-content :deep(h4) { color: var(--text-primary); margin: 8px 0 4px; }
</style>
