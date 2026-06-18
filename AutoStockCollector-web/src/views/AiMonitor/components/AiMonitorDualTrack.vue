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
        <el-button size="small" type="primary" @click="openConfig"><el-icon><Setting /></el-icon> 参数配置</el-button>
      </div>
    </div>

    <el-empty v-if="!loading && !data" description="暂无双轨道调仓结果，等待下一次监控刷新（09:30/12:00/15:00）" :image-size="60" />

    <template v-if="data">
      <!-- portfolio summary -->
      <div class="dt-summary">
        <el-card v-for="c in summaryCards" :key="c.label" shadow="never" class="dt-stat">
          <div class="dt-stat-label">{{ c.label }}</div>
          <div class="dt-stat-value">{{ c.value }}</div>
        </el-card>
      </div>

      <!-- two tracks -->
      <div class="dt-tracks">
        <div class="dt-track">
          <div class="dt-track-head">
            <span class="dt-track-title">长线轨道</span>
            <el-tag size="small" effect="plain">可用 {{ fmtMoney(data.portfolio_summary.long_available) }}</el-tag>
          </div>
          <el-table :data="data.long_term_advice" size="small" empty-text="无长线建议">
            <el-table-column label="标的" min-width="120">
              <template #default="{ row }">
                <span class="dt-name">{{ row.name }}</span>
                <span class="dt-code">{{ row.code }}</span>
              </template>
            </el-table-column>
            <el-table-column label="动作" width="76">
              <template #default="{ row }">
                <el-tag :type="actionType(row.action)" effect="dark" size="small">{{ row.action }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="评分" width="60" align="right">
              <template #default="{ row }">{{ row.composite_score?.toFixed(1) }}</template>
            </el-table-column>
            <el-table-column label="买入区" width="110" align="center">
              <template #default="{ row }">{{ zone(row) }}</template>
            </el-table-column>
            <el-table-column label="目标/止损" width="110" align="center">
              <template #default="{ row }">
                <span class="up">{{ row.target_price || '-' }}</span> /
                <span class="dn">{{ row.stop_loss || '-' }}</span>
              </template>
            </el-table-column>
            <el-table-column label="建议金额" width="100" align="right">
              <template #default="{ row }">{{ fmtMoney(row.suggested_amount) }}</template>
            </el-table-column>
            <el-table-column label="理由" min-width="160" show-overflow-tooltip prop="reason" />
          </el-table>
        </div>

        <div class="dt-track">
          <div class="dt-track-head">
            <span class="dt-track-title">短线轨道</span>
            <el-tag size="small" effect="plain" type="warning">可用 {{ fmtMoney(data.portfolio_summary.short_available) }}</el-tag>
          </div>
          <el-table :data="data.short_term_advice" size="small" empty-text="无短线建议">
            <el-table-column label="标的" min-width="120">
              <template #default="{ row }">
                <span class="dt-name">{{ row.name }}</span>
                <span class="dt-code">{{ row.code }}</span>
              </template>
            </el-table-column>
            <el-table-column label="动作" width="76">
              <template #default="{ row }">
                <el-tag :type="actionType(row.action)" effect="dark" size="small">{{ row.action }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="评分" width="60" align="right">
              <template #default="{ row }">{{ row.composite_score?.toFixed(1) }}</template>
            </el-table-column>
            <el-table-column label="买入区" width="110" align="center">
              <template #default="{ row }">{{ zone(row) }}</template>
            </el-table-column>
            <el-table-column label="目标/止损" width="110" align="center">
              <template #default="{ row }">
                <span class="up">{{ row.target_price || '-' }}</span> /
                <span class="dn">{{ row.stop_loss || '-' }}</span>
              </template>
            </el-table-column>
            <el-table-column label="建议金额" width="100" align="right">
              <template #default="{ row }">{{ fmtMoney(row.suggested_amount) }}</template>
            </el-table-column>
            <el-table-column label="理由" min-width="160" show-overflow-tooltip prop="reason" />
          </el-table>
        </div>
      </div>

      <!-- swap out -->
      <div class="dt-section" v-if="data.swap_out_advice?.length">
        <div class="dt-section-head">换股建议 <el-tag size="small" type="warning" effect="light">{{ data.swap_out_advice.length }}</el-tag></div>
        <el-table :data="data.swap_out_advice" size="small">
          <el-table-column label="标的" min-width="140">
            <template #default="{ row }">
              <span class="dt-name">{{ row.name }}</span>
              <span class="dt-code">{{ row.code }}</span>
            </template>
          </el-table-column>
          <el-table-column label="评分" width="70" align="right">
            <template #default="{ row }">{{ row.composite_score?.toFixed(1) }}</template>
          </el-table-column>
          <el-table-column label="理由" min-width="240" prop="reason" />
        </el-table>
      </div>

      <!-- anomaly alerts -->
      <div class="dt-section" v-if="data.anomaly_alerts?.length">
        <div class="dt-section-head">资金异动预警 <el-tag size="small" type="danger" effect="light">{{ data.anomaly_alerts.length }}</el-tag></div>
        <el-table :data="data.anomaly_alerts" size="small">
          <el-table-column label="标的" min-width="150">
            <template #default="{ row }">
              <el-tag v-if="row.is_holding" size="small" type="danger" effect="plain" class="hold-tag">持仓</el-tag>
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

    <!-- config dialog -->
    <el-dialog v-model="configVisible" title="双轨道监控参数" width="720px">
      <div class="dt-cfg" v-if="cfg">
        <div class="dt-cfg-col">
          <div class="dt-cfg-title">长线轨道</div>
          <el-form label-width="120px" size="small">
            <el-form-item label="ROE 下限(%)"><el-input-number v-model="cfg.long_term.roe_min" :min="0" :step="1" /></el-form-item>
            <el-form-item label="营收增速下限(%)"><el-input-number v-model="cfg.long_term.revenue_growth_min" :min="0" :step="1" /></el-form-item>
            <el-form-item label="PE分位上限(%)"><el-input-number v-model="cfg.long_term.pe_percentile_max" :min="0" :max="100" :step="5" /></el-form-item>
            <el-form-item label="最大持仓数"><el-input-number v-model="cfg.long_term.max_positions" :min="1" :step="1" /></el-form-item>
            <el-form-item label="资金占比"><el-input-number v-model="cfg.long_term.fund_ratio" :min="0" :max="1" :step="0.05" :precision="2" /></el-form-item>
            <el-form-item label="候选池"><el-input-number v-model="cfg.long_term.candidate_pool" :min="5" :step="5" /></el-form-item>
            <el-form-item label="权重(基/技/资/估)">
              <div class="dt-weights">
                <el-input-number v-model="cfg.long_term.weight_overrides.fundamental" :min="0" :max="1" :step="0.05" :precision="2" controls-position="right" />
                <el-input-number v-model="cfg.long_term.weight_overrides.technical" :min="0" :max="1" :step="0.05" :precision="2" controls-position="right" />
                <el-input-number v-model="cfg.long_term.weight_overrides.fund_flow" :min="0" :max="1" :step="0.05" :precision="2" controls-position="right" />
                <el-input-number v-model="cfg.long_term.weight_overrides.valuation" :min="0" :max="1" :step="0.05" :precision="2" controls-position="right" />
              </div>
            </el-form-item>
          </el-form>
        </div>
        <div class="dt-cfg-col">
          <div class="dt-cfg-title">短线轨道</div>
          <el-form label-width="130px" size="small">
            <el-form-item label="主力净流入下限(万)"><el-input-number v-model="shortInflowWan" :min="0" :step="500" /></el-form-item>
            <el-form-item label="正面新闻下限(条)"><el-input-number v-model="cfg.short_term.news_positive_min" :min="0" :step="1" /></el-form-item>
            <el-form-item label="最大持仓数"><el-input-number v-model="cfg.short_term.max_positions" :min="1" :step="1" /></el-form-item>
            <el-form-item label="资金占比"><el-input-number v-model="cfg.short_term.fund_ratio" :min="0" :max="1" :step="0.05" :precision="2" /></el-form-item>
            <el-form-item label="候选池"><el-input-number v-model="cfg.short_term.candidate_pool" :min="5" :step="5" /></el-form-item>
            <el-form-item label="权重(基/技/资/估)">
              <div class="dt-weights">
                <el-input-number v-model="cfg.short_term.weight_overrides.fundamental" :min="0" :max="1" :step="0.05" :precision="2" controls-position="right" />
                <el-input-number v-model="cfg.short_term.weight_overrides.technical" :min="0" :max="1" :step="0.05" :precision="2" controls-position="right" />
                <el-input-number v-model="cfg.short_term.weight_overrides.fund_flow" :min="0" :max="1" :step="0.05" :precision="2" controls-position="right" />
                <el-input-number v-model="cfg.short_term.weight_overrides.valuation" :min="0" :max="1" :step="0.05" :precision="2" controls-position="right" />
              </div>
            </el-form-item>
          </el-form>
        </div>
      </div>
      <template #footer>
        <el-button @click="configVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="saveConfig">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { Refresh, Setting } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { monitorApi, type MonitorPortfolio, type MonitorTrackConfig, type TrackAdvice } from '@/api/monitor'

const loading = ref(false)
const saving = ref(false)
const data = ref<MonitorPortfolio | null>(null)
const configVisible = ref(false)
const cfg = ref<MonitorTrackConfig | null>(null)

// 后端主力净流入下限单位是「元」，表单按「万」展示更直观
const shortInflowWan = computed({
  get: () => cfg.value ? Math.round(cfg.value.short_term.main_net_inflow_min / 1e4) : 0,
  set: (v: number) => { if (cfg.value) cfg.value.short_term.main_net_inflow_min = (v || 0) * 1e4 },
})

const summaryCards = computed(() => {
  const p = data.value?.portfolio_summary
  if (!p) return []
  return [
    { label: '总资产', value: fmtMoney(p.total_value) },
    { label: '现金', value: fmtMoney(p.cash) },
    { label: '持仓市值', value: fmtMoney(p.position_value) },
    { label: '持仓数', value: String(p.position_count) },
    { label: `长线可用 (${Math.round(p.long_ratio * 100)}%)`, value: fmtMoney(p.long_available) },
    { label: `短线可用 (${Math.round(p.short_ratio * 100)}%)`, value: fmtMoney(p.short_available) },
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

function zone(row: TrackAdvice): string {
  if (!row.buy_price_low && !row.buy_price_high) return '-'
  return `${row.buy_price_low}~${row.buy_price_high}`
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
    ElMessage.error('获取双轨道结果失败')
  }).finally(() => {
    loading.value = false
  })
}

function openConfig() {
  monitorApi.getConfig().then(resp => {
    cfg.value = (resp.data as any).data
    configVisible.value = true
  }).catch(() => ElMessage.error('获取配置失败'))
}

function saveConfig() {
  if (!cfg.value) return
  saving.value = true
  monitorApi.saveConfig(cfg.value).then(resp => {
    cfg.value = (resp.data as any).data
    ElMessage.success('配置已保存，下次刷新生效')
    configVisible.value = false
  }).catch(() => {
    ElMessage.error('保存配置失败')
  }).finally(() => {
    saving.value = false
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

.dt-tracks { display: flex; gap: 12px; flex-wrap: wrap; }
.dt-track { flex: 1; min-width: 480px; }
.dt-track-head { display: flex; align-items: center; gap: 8px; margin-bottom: 6px; }
.dt-track-title { font-size: 14px; font-weight: 600; }

.dt-section { margin-top: 4px; }
.dt-section-head { font-size: 14px; font-weight: 600; margin-bottom: 6px; display: flex; align-items: center; gap: 6px; }

.dt-name { font-weight: 600; }
.dt-code { font-size: 11px; color: var(--text-muted, #999); margin-left: 6px; }
.hold-tag { margin-right: 4px; }
.up { color: #f56c6c; }
.dn { color: #67c23a; }

.dt-cfg { display: flex; gap: 24px; }
.dt-cfg-col { flex: 1; }
.dt-cfg-title { font-size: 14px; font-weight: 600; margin-bottom: 12px; }
.dt-weights { display: flex; gap: 4px; flex-wrap: wrap; }
.dt-weights :deep(.el-input-number) { width: 90px; }
</style>
