<template>
  <div class="ap-ai-summary ap-track">
    <div class="ap-summary-toggle" @click="toggleTrack">
      <span class="section-title">历史选股效果 <span class="ap-track-sub">vs 等权全市场基准</span></span>
      <svg class="ap-summary-svg" :class="{ 'is-expanded': trackExpanded }" viewBox="0 0 12 12" width="12" height="12">
        <path d="M2 4l4 4 4-4" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
      </svg>
    </div>
    <div v-if="trackExpanded" class="ap-track-body">
      <div v-if="trackLoading" class="ap-track-tip">⏳ 正在计算全市场等权基准对比，约需10-20秒...</div>
      <div v-else-if="trackError" class="ap-track-tip">{{ trackError }}</div>
      <template v-else-if="track">
        <div class="ap-track-meta">
          已跟踪 {{ track.runs_count }} 次选股（仅 default 策略）· 入场=选股日(含)后首个收盘价 · 基准=同窗口全市场等权平均收益 · 当日批次需待收盘K线入库后才可评估（显示为 -）
        </div>
        <el-table :data="overallRows" size="small" class="ap-table ap-track-table">
          <el-table-column prop="horizon" label="持有期" width="70" align="center" />
          <el-table-column label="选股收益" width="90" align="center">
            <template #default="{ row }"><span :style="{ color: pctColor(row.avg) }">{{ fmtPct(row.avg) }}</span></template>
          </el-table-column>
          <el-table-column label="胜率" width="70" align="center">
            <template #default="{ row }">{{ row.win_rate != null ? row.win_rate + '%' : '-' }}</template>
          </el-table-column>
          <el-table-column label="市场基准" width="90" align="center">
            <template #default="{ row }"><span :style="{ color: pctColor(row.baseline) }">{{ fmtPct(row.baseline) }}</span></template>
          </el-table-column>
          <el-table-column label="超额收益" width="90" align="center">
            <template #default="{ row }"><span class="ap-track-excess" :style="{ color: pctColor(row.excess) }">{{ fmtPct(row.excess) }}</span></template>
          </el-table-column>
          <el-table-column label="跑赢率" width="70" align="center">
            <template #default="{ row }">{{ row.beat_rate != null ? row.beat_rate + '%' : '-' }}</template>
          </el-table-column>
          <el-table-column prop="n" label="样本" width="60" align="center" />
        </el-table>

        <div class="ap-track-runs-title">最近选股批次</div>
        <el-table :data="track.runs.slice(0, 8)" size="small" class="ap-table ap-track-table">
          <el-table-column label="时间" width="110">
            <template #default="{ row }">{{ fmtTime(row.timestamp) }}</template>
          </el-table-column>
          <el-table-column label="精选/可评估" width="92" align="center">
            <template #default="{ row }">{{ row.picks_count }} / {{ row.evaluated }}</template>
          </el-table-column>
          <el-table-column v-for="h in track.horizons" :key="h" :label="h + '日超额'" width="86" align="center">
            <template #default="{ row }">
              <span :style="{ color: pctColor(row.returns[String(h)]?.excess) }">{{ fmtPct(row.returns[String(h)]?.excess) }}</span>
            </template>
          </el-table-column>
        </el-table>
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import dayjs from 'dayjs'
import type { PickTrackData } from '@/api/ai'
import { RISE_COLOR, FALL_COLOR, FLAT_COLOR } from '@/utils/format'

const props = defineProps<{
  trackExpanded: boolean
  trackLoading: boolean
  trackError: string
  track: PickTrackData | null
}>()

const emit = defineEmits<{
  (e: 'toggleTrack'): void
}>()

const overallRows = computed(() => {
  if (!props.track) return []
  return props.track.horizons.map(h => ({
    horizon: `${h}日`,
    ...props.track!.overall[String(h)],
  }))
})

function toggleTrack() {
  emit('toggleTrack')
}

function fmtPct(v: number | null | undefined): string {
  if (v == null) return '-'
  return `${v > 0 ? '+' : ''}${v.toFixed(2)}%`
}

function pctColor(v: number | null | undefined): string {
  if (v == null) return FLAT_COLOR
  return v > 0 ? RISE_COLOR : v < 0 ? FALL_COLOR : FLAT_COLOR
}

function fmtTime(t: string): string {
  return t ? dayjs(t).format('MM-DD HH:mm') : '--'
}
</script>

<style scoped>
.ap-ai-summary {
  background: var(--bg-deep-soft, #f5f7fa);
  border: 1px solid var(--border-alt, #ebeef5);
  border-left: 3px solid #5a7af0;
  border-radius: 6px;
  overflow: hidden;
}
.ap-summary-toggle {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 14px;
  cursor: pointer;
  font-size: 13px;
  font-weight: 600;
  color: var(--text-alt-body, #303133);
  user-select: none;
}
.ap-summary-toggle:hover { background: var(--bg-hover-subtle, #f5f7fa); }
.ap-summary-svg {
  color: var(--text-alt-muted, #909399);
  transition: transform 0.2s;
  vertical-align: middle;
}
.ap-summary-svg.is-expanded { transform: rotate(180deg); }

.ap-track-sub { font-size: 11px; font-weight: 400; color: var(--text-alt-muted, #909399); margin-left: 6px; }
.ap-track-body { padding: 0 14px 12px; display: flex; flex-direction: column; gap: 8px; }
.ap-track-tip { font-size: 12px; color: var(--text-alt-muted, #909399); padding: 8px 0; }
.ap-track-meta { font-size: 11px; color: var(--text-alt-muted, #909399); }
.ap-track-table { font-size: 12px; }
.ap-track-excess { font-weight: 600; }
.ap-track-runs-title { font-size: 12px; font-weight: 600; color: var(--text-alt-body, #303133); margin-top: 4px; }
.ap-table { background: transparent; }
</style>
