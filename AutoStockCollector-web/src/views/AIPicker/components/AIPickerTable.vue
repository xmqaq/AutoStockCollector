<template>
  <el-table v-if="picks?.length" :data="picks" stripe class="ap-table"
            :row-class-name="tableRowClass" @row-click="$emit('toggleExpand', $event)">
    <el-table-column type="index" label="#" width="42" align="center" />
    <el-table-column prop="code" label="代码" width="100">
      <template #default="{ row }"><span class="ap-code num" @click.stop="$emit('goAnalysis', row.code)">{{ row.code }}</span></template>
    </el-table-column>
    <el-table-column prop="name" label="名称" width="90" />
    <el-table-column label="综合" width="140" sortable :sort-by="(r: AIPick) => r.composite">
      <template #default="{ row }">
        <el-progress :percentage="Math.round(row.composite)" :color="scoreColor(row.composite)" :stroke-width="8" />
      </template>
    </el-table-column>
    <el-table-column label="基本" width="55" align="center" sortable :sort-by="(r: AIPick) => r.scores?.fundamental ?? 0">
      <template #default="{ row }">
        <span v-if="row.scores?.fundamental != null" class="ap-score-cell num" :style="{ color: dimColor(row.scores.fundamental) }">{{ Math.round(row.scores.fundamental) }}</span>
        <span v-else class="ap-na">-</span>
      </template>
    </el-table-column>
    <el-table-column label="技术" width="55" align="center" sortable :sort-by="(r: AIPick) => r.scores?.technical ?? 0">
      <template #default="{ row }">
        <span v-if="row.scores?.technical != null" class="ap-score-cell num" :style="{ color: dimColor(row.scores.technical) }">{{ Math.round(row.scores.technical) }}</span>
        <span v-else class="ap-na">-</span>
      </template>
    </el-table-column>
    <el-table-column label="资金" width="55" align="center" sortable :sort-by="(r: AIPick) => r.scores?.fund_flow ?? 0">
      <template #default="{ row }">
        <span v-if="row.scores?.fund_flow != null" class="ap-score-cell num" :style="{ color: dimColor(row.scores.fund_flow) }">{{ Math.round(row.scores.fund_flow) }}</span>
        <span v-else class="ap-na">-</span>
      </template>
    </el-table-column>
    <el-table-column label="估值" width="55" align="center" sortable :sort-by="(r: AIPick) => r.scores?.valuation ?? 0">
      <template #default="{ row }">
        <span v-if="row.scores?.valuation != null" class="ap-score-cell num" :style="{ color: dimColor(row.scores.valuation) }">{{ Math.round(row.scores.valuation) }}</span>
        <span v-else class="ap-na">-</span>
      </template>
    </el-table-column>
    <el-table-column label="来源" width="56" align="center">
      <template #default="{ row }">
        <span v-if="row.source === 'llm'" class="ap-source-tag ap-tag-ai">AI</span>
        <span v-else class="ap-source-tag ap-tag-factor">因子</span>
      </template>
    </el-table-column>
    <el-table-column label="操作建议" width="80" align="center">
      <template #default="{ row }">
        <span class="ap-action-tag" :class="actionClass(row)">{{ getAction(row) }}</span>
      </template>
    </el-table-column>
    <el-table-column label="建议仓位" width="90" align="center">
      <template #default="{ row }">
        <el-tooltip v-if="getPosition(row) !== '--'" content="分散配置，总仓位建议不超过60%" placement="top">
          <span class="ap-position num">{{ getPosition(row) }}</span>
        </el-tooltip>
        <span v-else class="ap-na">--</span>
      </template>
    </el-table-column>
    <el-table-column width="36" align="center" class-name="ap-col-expand">
      <template #default="{ row }">
        <svg class="ap-expand-svg" :class="{ 'is-expanded': expandedCode === row.code }" viewBox="0 0 12 12" width="12" height="12">
          <path d="M2 4l4 4 4-4" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
      </template>
    </el-table-column>
  </el-table>
</template>

<script setup lang="ts">
import type { AIPick } from '@/api/ai'

const props = defineProps<{
  picks: AIPick[]
  expandedCode: string
}>()

defineEmits<{
  (e: 'toggleExpand', row: AIPick): void
  (e: 'goAnalysis', code: string): void
}>()

function scoreColor(v: number): string {
  if (v >= 70) return '#3a8a52'
  if (v >= 50) return '#d0a020'
  return '#a04040'
}

function dimColor(v: number): string {
  if (v >= 80) return '#52c41a'
  if (v >= 60) return '#faad14'
  return '#ff4d4f'
}

function pickHasWarning(pick: AIPick): boolean {
  const details = pick.score_details
  if (!details) return false
  for (const dim of Object.values(details)) {
    const items = (dim as any)?.details
    if (!items) continue
    for (const [k, v] of Object.entries(items)) {
      if (k.endsWith('_warning') && typeof v === 'string' && v) return true
    }
  }
  return false
}

function getAction(pick: AIPick): string {
  const composite = pick.composite ?? pick.scores?.composite ?? 0
  const hasWarning = pickHasWarning(pick)
  const valuation = pick.scores?.valuation ?? 50
  if (hasWarning && composite < 82) return '观望'
  if (valuation <= 20 && composite >= 80) return '谨慎关注'
  if (composite >= 80 && !hasWarning) return '建议关注'
  if (composite >= 75 && !hasWarning) return '可以关注'
  return '观望'
}

function getPosition(pick: AIPick): string {
  const action = getAction(pick)
  const composite = pick.composite ?? pick.scores?.composite ?? 0
  if (action === '谨慎关注') return '5%以内'
  if (action === '建议关注') return composite >= 80 ? '10-15%' : '5-10%'
  if (action === '可以关注') return '5-10%'
  return '--'
}

const ACTION_CLASS: Record<string, string> = {
  '建议关注': 'ap-action-green',
  '可以关注': 'ap-action-lightgreen',
  '谨慎关注': 'ap-action-orange',
  '观望': 'ap-action-gray',
}
function actionClass(pick: AIPick): string {
  return ACTION_CLASS[getAction(pick)] || 'ap-action-gray'
}

function tableRowClass({ row }: { row: AIPick }) {
  const classes = ['ap-row-clickable']
  if (row.code === props.expandedCode) classes.push('ap-row-active')
  return classes.join(' ')
}
</script>

<style scoped>
.ap-table { background: transparent; }
.ap-table :deep(.el-table__row) { height: 42px; }
.ap-table :deep(.el-table__row:hover > td) { background: var(--bg-hover-subtle, #f5f7fa) !important; }
.ap-row-clickable { cursor: pointer; }
.ap-row-active :deep(td) {
  background: rgba(90,122,240,0.08) !important;
  border-left: 2px solid #5a7af0;
}
.ap-code { color: #5a7af0; cursor: pointer; }
.ap-code:hover { text-decoration: underline; }
.ap-na { color: var(--text-alt-muted, #909399); }
.ap-score-cell { font-weight: 600; font-size: 13px; }
.ap-source-tag {
  display: inline-block;
  font-size: 11px;
  padding: 1px 6px;
  border-radius: 3px;
  font-weight: 600;
  line-height: 1.4;
}
.ap-tag-ai { color: #60a0f0; background: rgba(96,160,240,0.12); }
.ap-tag-factor { color: #a0a060; background: rgba(160,160,96,0.12); }

.ap-action-tag {
  display: inline-block;
  font-size: 11px;
  padding: 1px 7px;
  border-radius: 3px;
  font-weight: 600;
  line-height: 1.5;
  white-space: nowrap;
}
.ap-action-green { color: #3aa856; background: rgba(82,196,26,0.14); }
.ap-action-lightgreen { color: #7cc98a; background: rgba(82,196,26,0.07); }
.ap-action-orange { color: #e8912a; background: rgba(250,173,20,0.14); }
.ap-action-gray { color: var(--text-alt-muted, #909399); background: rgba(144,144,152,0.12); }
.ap-position { font-size: 12px; color: #5a7af0; cursor: default; white-space: nowrap; }
.ap-expand-svg {
  color: var(--text-alt-muted, #909399);
  transition: transform 0.2s;
  vertical-align: middle;
}
.ap-expand-svg.is-expanded { transform: rotate(180deg); }
.ap-col-expand { overflow: visible !important; }
</style>
