<template>
  <div class="ar-page">
    <el-card shadow="never" class="ar-head">
      <div class="ar-head-row">
        <span class="ar-title">📡 盘前竞价雷达</span>
        <el-tag v-if="statusData?.status === 'running'" type="warning" effect="dark">扫描中...</el-tag>
        <el-tag v-else-if="statusData?.status === 'done'" type="success" effect="plain">{{ today }}</el-tag>
        <el-tag v-else type="info" effect="plain">等待</el-tag>
        <el-button size="small" :loading="loading" @click="loadResults">刷新</el-button>
        <el-button size="small" :loading="scanLoading" @click="triggerScan">手动扫描</el-button>
      </div>
    </el-card>

    <!-- 情绪摘要 -->
    <el-card v-if="result?.summary" shadow="never" class="ar-summary-card">
      <div class="ar-summary">{{ result.summary }}</div>
    </el-card>

    <!-- 板块龙头 -->
    <el-card v-if="sectorLeaders.length" shadow="never" class="ar-card">
      <template #header><span>🏆 板块龙头</span></template>
      <div class="ar-sector-grid">
        <div v-for="sl in sectorLeaders" :key="sl.sector" class="ar-sector-item">
          <span class="ar-si-name">{{ sl.sector }}</span>
          <span class="ar-si-leader">{{ sl.name }}({{ sl.leader }})</span>
          <span class="ar-si-score">{{ sl.score }}分</span>
        </div>
      </div>
    </el-card>

    <!-- 诱多/诱空预警 -->
    <el-card v-if="trapWarnings.length" shadow="never" class="ar-card ar-trap-card">
      <template #header><span>⚠️ 诱多/诱空预警</span></template>
      <div v-for="t in trapWarnings" :key="t.symbol" class="ar-trap-item">
        <el-tag :type="t.trap_type === 'bull_trap' ? 'danger' : 'success'" size="small" effect="dark">
          {{ t.trap_type === 'bull_trap' ? '诱多' : '诱空' }}
        </el-tag>
        <span class="ar-trap-code">{{ t.name }}({{ t.symbol }})</span>
        <span class="ar-trap-reason">{{ t.reason }}</span>
      </div>
    </el-card>

    <!-- 个股列表 -->
    <el-card v-if="result" shadow="never" class="ar-card">
      <template #header>
        <span>📊 今日强势股 TOP {{ result.top_stocks?.length || 0 }}</span>
        <span class="ar-scan-info">共扫描 {{ result.total_scanned }} 只</span>
      </template>
      <el-table :data="result.top_stocks" stripe size="small" highlight-current-row>
        <el-table-column label="#" width="40" type="index" />
        <el-table-column label="代码" width="80" prop="symbol" />
        <el-table-column label="名称" width="90" prop="name" />
        <el-table-column label="行业" width="90" prop="industry" />
        <el-table-column label="开盘价" width="80" align="right">
          <template #default="{ row }">¥{{ row.open_price?.toFixed(2) }}</template>
        </el-table-column>
        <el-table-column label="跳空%" width="75" align="right">
          <template #default="{ row }">
            <span :class="row.gap_pct >= 0 ? 'ar-gap-up' : 'ar-gap-down'">{{ row.gap_pct >= 0 ? '+' : '' }}{{ row.gap_pct?.toFixed(2) }}%</span>
          </template>
        </el-table-column>
        <el-table-column label="竞价额" width="100" align="right">
          <template #default="{ row }">¥{{ (row.auction_amount / 1e4).toFixed(0) }}万</template>
        </el-table-column>
        <el-table-column label="强度" width="70" align="center">
          <template #default="{ row }">
            <el-tag :type="strengthTagType(row.strength_score)" size="small">{{ row.strength_score }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="预警" width="70" align="center">
          <template #default="{ row }">
            <el-tag v-if="row.trap_warning" :type="row.trap_warning.trap_type === 'bull_trap' ? 'danger' : 'success'" size="small">
              {{ row.trap_warning.trap_type === 'bull_trap' ? '诱多' : '诱空' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="亮点" width="100">
          <template #default="{ row }">
            <el-tag v-if="row.highlight" type="warning" size="small" effect="dark">🔥 {{ row.highlight_reason }}</el-tag>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-card v-else-if="!loading" shadow="never">
      <el-empty description="今日尚未扫描，等待 9:25 自动触发，或点击手动扫描" />
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { auctionRadarApi, type RadarResult } from '@/api/auctionRadar'

const loading = ref(false)
const scanLoading = ref(false)
const result = ref<RadarResult | null>(null)
const statusData = ref<{ status: string; scan_time: string; date: string } | null>(null)

const today = new Date().toISOString().slice(0, 10)

const sectorLeaders = computed(() => result.value?.sector_leaders || [])
const trapWarnings = computed(() => result.value?.trap_warnings || [])

function strengthTagType(score: number) {
  if (score >= 80) return 'danger'
  if (score >= 60) return 'warning'
  return 'info'
}

async function loadStatus() {
  try {
    const res = await auctionRadarApi.getStatus()
    if (res.data?.success) statusData.value = res.data.data
  } catch { /* ignore */ }
}

async function loadResults() {
  loading.value = true
  try {
    const res = await auctionRadarApi.getResults()
    if (res.data?.success) {
      result.value = res.data.data
    } else {
      result.value = null
    }
  } catch {
    result.value = null
  }
  loading.value = false
}

async function triggerScan() {
  scanLoading.value = true
  try {
    const res = await auctionRadarApi.triggerScan()
    if (res.data?.success) {
      result.value = res.data.data
      statusData.value = { status: 'done', scan_time: res.data.data.scan_time, date: res.data.data.date }
      ElMessage.success(`扫描完成: ${result.value.top_stocks?.length || 0} 只信号`)
    } else {
      ElMessage.error('扫描失败')
    }
  } catch {
    ElMessage.error('扫描请求异常')
  }
  scanLoading.value = false
}

onMounted(() => {
  loadStatus()
  loadResults()
})
</script>

<style scoped>
.ar-page { padding: 16px; max-width: 1200px; margin: 0 auto; }
.ar-head { margin-bottom: 12px; }
.ar-head-row { display: flex; align-items: center; gap: 10px; }
.ar-title { font-size: 18px; font-weight: bold; }
.ar-summary-card { margin-bottom: 12px; background: linear-gradient(135deg, #667eea33, #764ba233); }
.ar-summary { font-size: 14px; line-height: 1.6; padding: 4px 0; }
.ar-card { margin-bottom: 12px; }
.ar-card :deep(.el-card__header) { display: flex; align-items: center; justify-content: space-between; font-weight: bold; font-size: 14px; padding: 10px 16px; }
.ar-scan-info { font-size: 12px; font-weight: normal; color: var(--text-secondary, #909399); }
.ar-sector-grid { display: flex; flex-wrap: wrap; gap: 8px; }
.ar-sector-item { display: flex; align-items: center; gap: 8px; padding: 6px 12px; background: var(--bg-page, #f5f7fa); border-radius: 6px; font-size: 13px; }
.ar-si-name { font-weight: bold; min-width: 60px; }
.ar-si-leader { color: var(--text-secondary, #909399); }
.ar-si-score { color: #e6a23c; font-weight: bold; margin-left: auto; }
.ar-trap-card { border-left: 3px solid #e6a23c; }
.ar-trap-item { display: flex; align-items: center; gap: 8px; padding: 6px 0; border-bottom: 1px solid var(--border-color, #ebeef5); font-size: 13px; }
.ar-trap-item:last-child { border-bottom: none; }
.ar-trap-code { font-weight: bold; min-width: 100px; }
.ar-trap-reason { color: var(--text-secondary, #909399); }
.ar-gap-up { color: #ef5350; font-weight: bold; }
.ar-gap-down { color: #26a69a; font-weight: bold; }
</style>
