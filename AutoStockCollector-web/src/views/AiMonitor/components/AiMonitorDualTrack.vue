<template>
  <div class="dt-page" v-loading="loading">
    <!-- toolbar -->
    <div class="dt-toolbar">
      <div class="dt-meta">
        <el-tag v-if="data" type="info" effect="plain" size="small">分析 {{ data.analyzed }} 只</el-tag>
        <el-tag v-if="data?.timestamp" type="info" effect="plain" size="small">{{ fmtTime(data.timestamp) }}</el-tag>
      </div>
      <div class="dt-actions">
        <el-button size="small" @click="fetchPortfolio"><el-icon><Refresh /></el-icon> 重新加载</el-button>
      </div>
    </div>

    <el-empty v-if="!loading && !data" description="暂无监控结果，AI智选完成后自动刷新（盘中 10:00 / 13:30 / 14:45 增量更新买卖点）" :image-size="60" />

    <template v-if="data">
      <!-- portfolio summary -->
      <div class="dt-summary">
        <el-card v-for="c in summaryCards" :key="c.label" shadow="never" class="dt-stat">
          <div class="dt-stat-label">{{ c.label }}</div>
          <div class="dt-stat-value">{{ c.value }}</div>
        </el-card>
      </div>

      <!-- grouped advice by source -->
      <div class="dt-section" v-for="g in grouped" :key="g.key">
        <div class="dt-section-head">
          <el-tag :type="g.tag" effect="dark" size="small">{{ g.title }}</el-tag>
          <span class="dt-count">{{ g.rows.length }}</span>
          <span v-if="g.key === 'position'" class="dt-hint">（强制监控，持仓期间不可移除）</span>
          <span v-else-if="g.key === 'fusion_pick'" class="dt-hint">（连续3次未入选自动移出）</span>
        </div>
        <el-table :data="g.rows" size="small" :empty-text="`无${g.title}`">
          <el-table-column label="标的" min-width="200">
            <template #default="{ row }">
              <span class="dt-name">{{ row.name }}</span>
              <span class="dt-code">{{ row.code }}</span>
              <el-tag v-for="s in row.sources" :key="s" size="small" effect="plain"
                      :type="srcType(s)" class="src-tag">{{ srcLabel(s) }}</el-tag>
              <el-tag v-if="row.strong_signal" size="small" type="danger" effect="dark" class="src-tag">🔥连{{ row.consecutive_days }}天</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="动作" width="76">
            <template #default="{ row }">
              <el-tag :type="actionType(row.action)" effect="dark" size="small">{{ row.action }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="现价" width="72" align="right">
            <template #default="{ row }">{{ row.price || '-' }}</template>
          </el-table-column>
          <el-table-column label="买入区" width="110" align="center">
            <template #default="{ row }">{{ zone(row) }}</template>
          </el-table-column>
          <el-table-column label="目标/止损" width="110" align="center">
            <template #default="{ row }">
              <span class="up">{{ row.take_profit || '-' }}</span> /
              <span class="dn">{{ row.stop_loss || '-' }}</span>
            </template>
          </el-table-column>
          <el-table-column v-if="g.key === 'fusion_pick'" label="连续入选" width="84" align="center">
            <template #default="{ row }">
              <el-tag v-if="row.consecutive_days > 0" :type="row.strong_signal ? 'danger' : 'info'"
                      size="small" effect="plain">{{ row.consecutive_days }}天</el-tag>
              <span v-else>-</span>
            </template>
          </el-table-column>
          <el-table-column label="理由" min-width="180" show-overflow-tooltip prop="reason" />
        </el-table>
      </div>

      <!-- anomaly alerts -->
      <div class="dt-section" v-if="data.anomaly_alerts?.length">
        <div class="dt-section-head">资金异动预警 <el-tag size="small" type="danger" effect="light">{{ data.anomaly_alerts.length }}</el-tag></div>
        <el-table :data="data.anomaly_alerts" size="small">
          <el-table-column label="标的" min-width="170">
            <template #default="{ row }">
              <el-tag v-if="row.is_holding" size="small" type="danger" effect="plain" class="hold-tag">持仓</el-tag>
              <el-tag v-else-if="row.in_monitor" size="small" type="warning" effect="plain" class="hold-tag">监控</el-tag>
              <span class="dt-name">{{ row.name }}</span>
              <span class="dt-code">{{ row.code }}</span>
            </template>
          </el-table-column>
          <el-table-column label="类型" width="90">
            <template #default="{ row }"><el-tag size="small" effect="plain">{{ row.anomaly_type }}</el-tag></template>
          </el-table-column>
          <el-table-column label="异动分" width="80" align="right" prop="anomaly_score" />
          <el-table-column label="Z-score" width="80" align="right">
            <template #default="{ row }">{{ row.z_score?.toFixed(2) }}</template>
          </el-table-column>
          <el-table-column label="连续天数" width="80" align="right" prop="consecutive_days" />
          <el-table-column label="最新净流入" width="120" align="right">
            <template #default="{ row }">
              <span :class="row.latest_net >= 0 ? 'up' : 'dn'">{{ fmtMoney(row.latest_net) }}</span>
            </template>
          </el-table-column>
          <el-table-column label="日期" width="110" prop="latest_date" />
        </el-table>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { Refresh } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { monitorApi, type MonitorPortfolio, type MonitorAdvice, type MonitorSource } from '@/api/monitor'

const loading = ref(false)
const data = ref<MonitorPortfolio | null>(null)

const SOURCE_GROUPS: { key: MonitorSource; title: string; tag: string }[] = [
  { key: 'position', title: '持仓', tag: 'danger' },
  { key: 'watchlist', title: '自选股', tag: 'primary' },
  { key: 'fusion_pick', title: 'AI智选候选', tag: 'success' },
  { key: 'research', title: '投研分析', tag: 'warning' },
]

const SRC_LABEL: Record<MonitorSource, string> = { position: '持仓', watchlist: '自选', fusion_pick: '智选', research: '投研' }
const SRC_TYPE: Record<MonitorSource, string> = { position: 'danger', watchlist: 'primary', fusion_pick: 'success', research: 'warning' }
function srcLabel(s: MonitorSource): string { return SRC_LABEL[s] || s }
function srcType(s: MonitorSource): string { return SRC_TYPE[s] || 'info' }

// 一只股票可同时属于多个来源 → 在它所属的每个分组里都出现（持仓+智选会两处可见，符合强制监控语义）
const grouped = computed(() =>
  SOURCE_GROUPS.map(g => ({
    ...g,
    rows: (data.value?.advice || []).filter(a => a.sources?.includes(g.key)),
  })),
)

const summaryCards = computed(() => {
  const p = data.value?.portfolio_summary
  if (!p) return []
  return [
    { label: '总资产', value: fmtMoney(p.total_value) },
    { label: '现金', value: fmtMoney(p.cash) },
    { label: '持仓市值', value: fmtMoney(p.position_value) },
    { label: '监控总数', value: String(p.monitor_count) },
    { label: '持仓 / 自选 / 智选', value: `${p.position_count} / ${p.watchlist_count} / ${p.fusion_pick_count}` },
    { label: '重叠 / 三合一', value: `${p.overlap_count} / ${p.all_three_count}` },
  ]
})

function actionType(action: string): string {
  switch (action) {
    case '买入': case '加仓': return 'danger'   // A股红=多
    case '卖出': return 'success'
    case '减仓': case '换股': return 'warning'
    default: return 'info'                        // 持有
  }
}

function zone(row: MonitorAdvice): string {
  const lo = row.entry_price_range?.low
  const hi = row.entry_price_range?.high
  if (!lo && !hi) return '-'
  return `${lo ?? '-'}~${hi ?? '-'}`
}

function fmtMoney(v?: number): string {
  if (v == null) return '-'
  const abs = Math.abs(v)
  if (abs >= 1e8) return (v / 1e8).toFixed(2) + '亿'
  if (abs >= 1e4) return (v / 1e4).toFixed(1) + '万'
  return v.toFixed(0)
}

function fmtTime(t: string): string {
  return t ? t.slice(0, 19).replace('T', ' ') : ''
}

function fetchPortfolio() {
  loading.value = true
  monitorApi.getPortfolio().then(resp => {
    data.value = (resp.data as any).data || null
  }).catch(() => {
    ElMessage.error('获取监控调仓结果失败')
  }).finally(() => {
    loading.value = false
  })
}

onMounted(fetchPortfolio)
</script>

<style scoped>
.dt-page { display: flex; flex-direction: column; gap: 12px; }

.dt-toolbar { display: flex; justify-content: space-between; align-items: center; }
.dt-meta { display: flex; gap: 8px; }
.dt-actions { display: flex; gap: 8px; }

.dt-summary { display: flex; gap: 8px; flex-wrap: wrap; }
.dt-stat { flex: 1; min-width: 120px; }
.dt-stat-label { font-size: 12px; color: var(--text-muted, #999); }
.dt-stat-value { font-size: 20px; font-weight: 700; margin-top: 4px; }

.dt-section { margin-top: 4px; }
.dt-section-head { font-size: 14px; font-weight: 600; margin-bottom: 6px; display: flex; align-items: center; gap: 6px; }
.dt-count { font-size: 13px; color: var(--text-muted, #999); }
.dt-hint { font-size: 12px; color: var(--text-muted, #bbb); font-weight: 400; }

.dt-name { font-weight: 600; }
.dt-code { font-size: 11px; color: var(--text-muted, #999); margin-left: 6px; }
.src-tag { margin-left: 4px; }
.hold-tag { margin-right: 4px; }
.up { color: var(--el-color-danger); }
.dn { color: var(--el-color-success); }
</style>
