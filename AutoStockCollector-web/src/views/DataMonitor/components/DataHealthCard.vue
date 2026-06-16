<template>
  <el-card shadow="never" class="section-card">
    <template #header>
      <div class="card-header">
        <span>数据覆盖状态</span>
        <el-button size="small" text :loading="gapsLoading" @click="loadDataGaps">
          <el-icon><Refresh /></el-icon> 检测缺口
        </el-button>
      </div>
    </template>
    <el-table
      :data="healthRows"
      size="default"
      stripe
      row-key="value"
      class="health-table"
    >
      <el-table-column type="expand">
        <template #default="{ row }">
          <div class="gap-detail">
            <!-- 无日期序列类型：直接显示说明，不做缺口检测 -->
            <template v-if="NO_DATE_SEQ.has(row.value)">
              <el-descriptions :column="1" size="small" border class="gap-descriptions">
                <template v-if="row.value === 'news'">
                  <el-descriptions-item label="数据量">按条存储，共 <strong>{{ row.record_count?.toLocaleString() ?? '--' }}</strong> 条</el-descriptions-item>
                  <el-descriptions-item label="更新机制">无日期连续性要求，每日增量采集最新新闻</el-descriptions-item>
                </template>
                <template v-else-if="row.value === 'sector'">
                  <el-descriptions-item label="数据量">快照性质，共 <strong>{{ row.record_count?.toLocaleString() ?? '--' }}</strong> 条</el-descriptions-item>
                  <el-descriptions-item label="最后更新">最新更新时间：{{ row.latest_date ?? '--' }}</el-descriptions-item>
                  <el-descriptions-item label="更新机制">每日采集当日板块涨跌数据</el-descriptions-item>
                </template>
                <template v-else-if="row.value === 'stock_info'">
                  <el-descriptions-item label="数据量">全量覆盖，共 <strong>{{ row.record_count?.toLocaleString() ?? '--' }}</strong> 只股票</el-descriptions-item>
                  <el-descriptions-item label="最后刷新">最后刷新时间：{{ row.latest_date ?? '--' }}</el-descriptions-item>
                  <el-descriptions-item label="更新机制">每周自动全量刷新一次</el-descriptions-item>
                </template>
                <template v-else-if="row.value === 'fund_flow'">
                  <el-descriptions-item label="数据量">每日全市场快照数据，共 <strong>{{ row.record_count?.toLocaleString() ?? '--' }}</strong> 条</el-descriptions-item>
                  <el-descriptions-item label="注意事项">受接口限制，不提供历史数据查询</el-descriptions-item>
                  <el-descriptions-item label="更新机制">每个交易日收盘后自动更新当日数据</el-descriptions-item>
                </template>
              </el-descriptions>
            </template>
            <!-- 有日期序列类型：显示缺口检测结果 -->
            <template v-else-if="!gapData[row.value]">
              <el-alert title="点击上方 检测缺口 加载区间详情" type="info" :closable="false" show-icon />
            </template>
            <template v-else-if="gapData[row.value].error">
              <el-alert :title="`查询失败：${gapData[row.value].error}`" type="error" :closable="false" show-icon />
            </template>
            <template v-else-if="row.value === 'financial'">
              <el-descriptions :column="1" size="small" border class="gap-descriptions">
                <el-descriptions-item label="完整度">
                  <span class="gap-pct">{{ gapData[row.value].completeness_pct }}%</span>
                </el-descriptions-item>
                <el-descriptions-item v-if="gapData[row.value].covered_quarters?.length" label="已有报告期">
                  {{ gapData[row.value].covered_quarters?.slice(-4).join(' / ') }}
                </el-descriptions-item>
                <el-descriptions-item v-if="gapData[row.value].missing_quarters?.length" label="缺失季度">
                  <div class="gap-missing">
                    <span v-for="q in gapData[row.value].missing_quarters?.slice(0, 8)" :key="q">
                      <el-tag size="small" type="danger" style="margin:2px; cursor: pointer"
                        @click="() => { const [s,e] = quarterToRange(q); fillGap(row.value, s, e) }">
                        {{ q }} [补采]
                      </el-tag>
                    </span>
                  </div>
                </el-descriptions-item>
              </el-descriptions>
            </template>
            <template v-else>
              <div class="gap-completeness">
                完整度 <strong>{{ gapData[row.value].completeness_pct }}%</strong>
              </div>
              <el-timeline class="gap-timeline">
                <el-timeline-item
                  v-for="seg in getMergedSegments(row.value)"
                  :key="seg.start"
                  :type="seg.type === 'covered' ? 'success' : 'danger'"
                  :hollow="seg.type === 'gap'"
                >
                  <div v-if="seg.type === 'covered'" class="timeline-content">
                    <span class="text-success">{{ seg.start }} ~ {{ seg.end }}</span>
                    <span class="text-muted timeline-desc">（{{ seg.days }}个交易日）</span>
                  </div>
                  <div v-else class="timeline-content">
                    <span class="text-danger">缺口：{{ seg.start }} ~ {{ seg.end }}</span>
                    <span class="text-muted timeline-desc">（{{ seg.days }}天）</span>
                    <el-button size="small" link type="primary" @click="fillGap(row.value, seg.start, seg.end)">
                      点击补采此区间
                    </el-button>
                  </div>
                </el-timeline-item>
                <el-timeline-item v-if="!gapData[row.value].covered_ranges?.length && !gapData[row.value].gap_ranges?.length" type="info">
                  <span class="text-muted">暂无区间数据</span>
                </el-timeline-item>
              </el-timeline>
            </template>
          </div>
        </template>
      </el-table-column>
      <el-table-column prop="label" label="数据类型" min-width="140">
        <template #default="{ row }">
          <div class="data-type-cell">
            <el-icon class="type-icon" :class="`icon-${row.value}`">
              <Document v-if="row.value === 'news' || row.value === 'stock_info'"/>
              <Box v-else-if="row.value === 'sector'"/>
              <Connection v-else-if="row.value === 'fund_flow'"/>
              <DataLine v-else-if="row.value === 'daily'"/>
              <DocumentCopy v-else-if="row.value === 'financial'"/>
              <ClockIcon v-else-if="row.value === 'minute'"/>
              <Calendar v-else/>
            </el-icon>
            <span class="type-label">{{ row.label }}</span>
          </div>
        </template>
      </el-table-column>
      <el-table-column prop="record_count" label="数据库条数" min-width="120" align="right">
        <template #default="{ row }">
          <span class="record-count">{{ row.record_count?.toLocaleString() ?? '--' }}</span>
        </template>
      </el-table-column>
      <el-table-column label="完整度" min-width="160" align="center">
        <template #default="{ row }">
          <div class="completeness-cell">
            <el-progress
              v-if="gapData[row.value]?.completeness_pct != null || coveragePct(row.value) != null"
              :percentage="gapData[row.value]?.completeness_pct ?? coveragePct(row.value) ?? 0"
              :status="(gapData[row.value]?.completeness_pct ?? coveragePct(row.value) ?? 100) < 90 ? 'warning' : 'success'"
              :stroke-width="8"
              :show-text="false"
              class="completeness-progress"
            />
            <span class="pct-text" :class="(gapData[row.value]?.completeness_pct ?? coveragePct(row.value) ?? 100) < 90 ? 'text-warning' : 'text-success'">
              {{ gapData[row.value]?.completeness_pct ?? coveragePct(row.value) ?? '--' }}%
            </span>
          </div>
        </template>
      </el-table-column>
      <el-table-column prop="latest_date" label="最新数据日期" min-width="130">
        <template #default="{ row }">
          <span class="latest-date">{{ row.latest_date ?? '--' }}</span>
        </template>
      </el-table-column>
      <el-table-column prop="days_behind" label="距今" min-width="110" align="center">
        <template #default="{ row }">
          <div class="days-behind-cell" :class="row.days_behind > 1 ? 'is-stale' : 'is-fresh'">
            <el-icon v-if="row.days_behind > 1"><Clock /></el-icon>
            <el-icon v-else-if="row.days_behind === 0"><CircleCheck /></el-icon>
            <span>{{ row.days_behind === 0 ? '今日最新' : (row.days_behind == null ? '--' : `${row.days_behind} 天前`) }}</span>
          </div>
        </template>
      </el-table-column>
      <el-table-column label="健康状态" min-width="100" align="center">
        <template #default="{ row }">
          <el-tag v-if="row.health === 'ok'" type="success" size="small" effect="light" round>正常</el-tag>
          <el-tag v-else-if="row.health === 'stale'" type="warning" size="small" effect="light" round>需更新</el-tag>
          <el-tag v-else type="danger" size="small" effect="light" round>异常</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" min-width="160" align="center">
        <template #default="{ row }">
          <el-button size="small" type="primary" link @click.stop="quickUpdate(row.value)">立即更新</el-button>
          <el-divider direction="vertical" />
          <el-button size="small" type="danger" link @click.stop="handleClearSingle(row)">清空</el-button>
        </template>
      </el-table-column>
    </el-table>
  </el-card>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useCollectStore } from '@/stores/collectStore'
import { collectApi } from '@/api/collect'
import { COLLECT_TYPES, TYPE_LABEL } from '@/utils/collectTypes'
import { Refresh, Document, Clock, CircleCheck, InfoFilled, Connection, Calendar, DataLine, Box, Clock as ClockIcon, DocumentCopy } from '@element-plus/icons-vue'

const props = defineProps<{
  coverageData: any
}>()

const emit = defineEmits<{
  (e: 'fill-gap', taskType: string, startDate: string, endDate: string): void
  (e: 'refresh'): void
}>()

const collectStore = useCollectStore()

const NO_DATE_SEQ = new Set(['news', 'fund_flow', 'sector', 'stock_info'])
const gapData = ref<Record<string, any>>({})
const gapsLoading = ref(false)

const healthRows = computed(() => {
  if (collectStore.progressList.length === 0) return []
  return COLLECT_TYPES.map(t => {
    const p = collectStore.progressList.find(p => p.task_type === t.value)
    if (!p) return null
    const rc = (p as any).record_count
    return {
      value: t.value,
      label: t.label,
      record_count: typeof rc === 'number' ? rc : null,
      latest_date: (p as any).latest_date ?? (p as any).date_to ?? null,
      days_behind: (p as any).days_behind ?? null,
      health: (p as any).health ?? (rc > 0 ? 'stale' : 'error'),
    }
  }).filter(Boolean)
})

function coveragePct(value: string): number | null {
  const src = props.coverageData?.sources?.find((s: any) => s.name === value)
  if (!src || !src.expected) return null
  return Math.round(src.covered / src.expected * 100)
}

async function loadDataGaps() {
  gapsLoading.value = true
  try {
    const res = await collectApi.getDataGaps()
    gapData.value = res.data?.data ?? {}
    ElMessage.success('缺口检测完成')
  } catch {
    ElMessage.error('缺口检测失败')
  } finally {
    gapsLoading.value = false
  }
}

function quarterToRange(q: string): [string, string] {
  const suffix = q.slice(5)
  const yr = q.slice(0, 4)
  const startMap: Record<string, string> = {
    '03-31': `${yr}-01-01`,
    '06-30': `${yr}-04-01`,
    '09-30': `${yr}-07-01`,
    '12-31': `${yr}-10-01`,
  }
  return [startMap[suffix] ?? q, q]
}

function getMergedSegments(rowValue: string) {
  const data = gapData.value[rowValue]
  if (!data) return []
  
  const covered = (data.covered_ranges || []).map((s: any) => ({...s, type: 'covered'}))
  const gaps = (data.gap_ranges || []).map((s: any) => ({...s, type: 'gap'}))
  
  return [...covered, ...gaps].sort((a, b) => b.start.localeCompare(a.start))
}

function fillGap(taskType: string, startDate: string, endDate: string) {
  emit('fill-gap', taskType, startDate, endDate)
}

async function quickUpdate(taskType: string) {
  try {
    const res = await collectApi.updateLatest({ task_types: [taskType], force: true })
    const started = res.data?.started || {}
    const busy = res.data?.skipped_busy || []
    if (Object.keys(started).length > 0) {
      ElMessage.success(`${TYPE_LABEL[taskType]} 更新任务已启动`)
    } else if (busy.includes(taskType)) {
      ElMessage.info(`${TYPE_LABEL[taskType]} 正在采集中，请稍候`)
    } else {
      ElMessage.info(`${TYPE_LABEL[taskType]} 数据已是最新，无需更新`)
    }
    emit('refresh')
  } catch {
    ElMessage.error('启动失败')
  }
}

async function handleClearSingle(row: { value: string; label: string; record_count: number | null }) {
  const count = row.record_count ?? 0
  try {
    await ElMessageBox.confirm(
      `确定要清空【${row.label}】吗？\n将删除数据库中全部 ${count.toLocaleString()} 条数据，此操作不可恢复。`,
      '清空数据确认',
      {
        confirmButtonText: '确认清空',
        cancelButtonText: '取消',
        type: 'error',
        confirmButtonClass: 'el-button--danger',
      }
    )
    await collectApi.clearSingle(row.value)
    ElMessage.success(`${row.label} 已清空，可通过补历史数据重新采集`)
    emit('refresh')
  } catch {
    // user cancelled
  }
}
</script>

<style scoped>
.section-card {
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: 8px;
  overflow: hidden;
  height: 100%;
  display: flex;
  flex-direction: column;
}

.section-card :deep(.el-card__body) {
  flex: 1;
  display: flex;
  flex-direction: column;
  padding: 0;
  min-height: 0;
}

.health-table {
  flex: 1;
  height: 0 !important;
  border-bottom: 1px solid var(--border-color-light);
}

.section-card :deep(.el-card__header) {
  border-bottom: 1px solid var(--border-color);
  padding: 14px 20px;
  color: var(--text-primary);
  font-size: 15px;
  font-weight: 600;
  background-color: var(--bg-soft);
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.stale-days {
  color: var(--el-color-warning);
  font-weight: 600;
}

/* 数据缺口展开行 */
.gap-detail {
  padding: 16px 24px 16px 48px;
  background: var(--bg-soft);
  border-top: 1px solid var(--border-color);
  border-bottom: 1px solid var(--border-color);
}
.gap-section {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 4px 0;
  flex-wrap: wrap;
}
.gap-completeness {
  font-size: 13px;
  color: var(--text-primary);
  margin-bottom: 12px;
}
.gap-timeline {
  padding-left: 4px;
}
.gap-descriptions {
  margin-top: 4px;
}
.timeline-content {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.timeline-desc {
  font-size: 12px;
}
.gap-ok-label { color: var(--el-color-success); font-size: 13px; }
.gap-err-label { color: var(--el-color-danger); font-size: 13px; }
.gap-pct { color: var(--el-color-primary); font-size: 13px; font-weight: bold; }
.gap-hint { font-size: 12px; color: var(--text-faint); font-style: italic; }
.gap-error { font-size: 12px; color: var(--el-color-danger); }
.gap-missing { display: flex; flex-wrap: wrap; gap: 4px; }

/* 无日期序列类型展开说明 */
.no-seq-desc {
  line-height: 1.6;
}
.no-seq-desc p {
  margin: 2px 0;
  font-size: 13px;
  color: var(--text-primary);
}
.no-seq-sub {
  color: var(--text-muted) !important;
  font-size: 12px !important;
}

/* New Table Styles */
.data-type-cell {
  display: flex;
  align-items: center;
  gap: 8px;
}
.type-icon {
  font-size: 16px;
  color: var(--text-muted);
}
.icon-news { color: #409EFF; }
.icon-sector { color: #67C23A; }
.icon-stock_info { color: #E6A23C; }
.icon-fund_flow { color: #F56C6C; }
.icon-daily { color: #909399; }
.icon-financial { color: #8A2BE2; }
.icon-minute { color: #E6A23C; }
.type-label {
  font-weight: 500;
  color: var(--text-primary);
}
.record-count {
  font-variant-numeric: tabular-nums;
  font-family: var(--font-mono, monospace);
}
.completeness-cell {
  display: flex;
  align-items: center;
  gap: 8px;
  justify-content: center;
}
.completeness-progress {
  width: 60px;
}
.pct-text {
  font-size: 13px;
  font-weight: 500;
  font-variant-numeric: tabular-nums;
  min-width: 40px;
  text-align: right;
}
.text-success { color: var(--el-color-success); }
.text-warning { color: var(--el-color-warning); }
.latest-date {
  font-variant-numeric: tabular-nums;
  color: var(--text-regular);
}
.days-behind-cell {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 2px 8px;
  border-radius: 12px;
  font-size: 12px;
}
.days-behind-cell.is-fresh {
  background: var(--el-color-success-light-9);
  color: var(--el-color-success);
}
.days-behind-cell.is-stale {
  background: var(--el-color-warning-light-9);
  color: var(--el-color-warning);
}
.health-table :deep(.el-table__expanded-cell) {
  padding: 0 !important;
  background-color: var(--bg-soft) !important;
}
.health-table :deep(.el-table__row) {
  cursor: pointer;
}
.health-table :deep(th.el-table__cell) {
  background-color: var(--bg-soft);
  color: var(--text-secondary);
  font-weight: 500;
}
</style>
