<template>
  <div class="fund-flow-view">
    <!-- Filter Bar -->
    <el-card shadow="never" class="section-card">
      <div class="filter-bar">
        <el-select v-model="topN" size="small" style="width:100px">
          <el-option label="Top 20" :value="20" />
          <el-option label="Top 50" :value="50" />
          <el-option label="Top 100" :value="100" />
        </el-select>
        <el-radio-group v-model="direction" size="small">
          <el-radio-button value="inflow">净流入</el-radio-button>
          <el-radio-button value="outflow">净流出</el-radio-button>
        </el-radio-group>
        <el-button type="primary" size="small" :loading="loading" @click="loadData">
          <el-icon><Refresh /></el-icon> 刷新
        </el-button>
        <span v-if="dataDate" class="date-label">数据日期：{{ dataDate }}</span>
      </div>
    </el-card>

    <!-- Ranking Table -->
    <el-card shadow="never" class="section-card" v-loading="loading">
      <template #header>
        <span>全市场资金流向排行（{{ direction === 'inflow' ? '主力净流入' : '主力净流出' }} Top {{ topN }}）</span>
      </template>
      <el-empty v-if="!loading && rows.length === 0" description="暂无资金流向数据，请先采集" />
      <el-table v-else :data="rows" stripe size="small" @row-click="goToStock">
        <el-table-column type="index" label="#" width="50" />
        <el-table-column prop="code" label="代码" width="110">
          <template #default="{ row }">
            <span class="code-link">{{ row.code }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="name" label="名称" min-width="90" />
        <el-table-column label="主力净流入" width="140" sortable>
          <template #default="{ row }">
            <span :class="row.main_net_inflow >= 0 ? 'val-pos' : 'val-neg'">
              {{ fmtAmount(row.main_net_inflow) }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="总流入" width="120">
          <template #default="{ row }">
            <span class="val-pos">{{ fmtAmount(row.main_inflow) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="总流出" width="120">
          <template #default="{ row }">
            <span class="val-neg">{{ fmtAmount(row.main_outflow) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="成交额" width="120">
          <template #default="{ row }">
            {{ fmtAmount(row.total_amount) }}
          </template>
        </el-table-column>
        <el-table-column prop="price" label="价格" width="80" />
        <el-table-column prop="change_pct" label="涨跌幅" width="90">
          <template #default="{ row }">
            <span :class="parseFloat(row.change_pct) >= 0 ? 'val-pos' : 'val-neg'">
              {{ row.change_pct }}
            </span>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- Bar Chart -->
    <el-card v-if="rows.length > 0" shadow="never" class="section-card">
      <template #header><span>净流入柱状图（单位：亿元）</span></template>
      <v-chart :option="barOption" style="height:320px" autoresize />
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { BarChart } from 'echarts/charts'
import { GridComponent, TooltipComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import { fundFlowApi } from '@/api/fundFlow'
import { Refresh } from '@element-plus/icons-vue'

use([BarChart, GridComponent, TooltipComponent, CanvasRenderer])

const router = useRouter()
const loading = ref(false)
const rows = ref<Record<string, unknown>[]>([])
const dataDate = ref('')
const topN = ref(50)
const direction = ref<'inflow' | 'outflow'>('inflow')

const RISE_COLOR = '#f56c6c'
const FALL_COLOR = '#67c23a'

function fmtAmount(v: unknown): string {
  const n = typeof v === 'number' ? v : parseFloat(String(v || 0))
  if (isNaN(n)) return '--'
  const abs = Math.abs(n)
  if (abs >= 1e8) return `${(n / 1e8).toFixed(2)}亿`
  if (abs >= 1e4) return `${(n / 1e4).toFixed(2)}万`
  return n.toFixed(0)
}

async function loadData() {
  loading.value = true
  try {
    const limit = direction.value === 'outflow' ? topN.value : topN.value
    const res = await fundFlowApi.getRank({ limit })
    const data = res.data?.data || []
    dataDate.value = res.data?.date || ''
    // 净流出：按升序取前 N
    if (direction.value === 'outflow') {
      rows.value = [...data].sort((a: Record<string, unknown>, b: Record<string, unknown>) =>
        (a.main_net_inflow as number) - (b.main_net_inflow as number)
      ).slice(0, topN.value)
    } else {
      rows.value = data
    }
  } catch {
    rows.value = []
  } finally {
    loading.value = false
  }
}

watch([topN, direction], loadData)

function goToStock(row: Record<string, unknown>) {
  if (row.code) router.push(`/stock-detail?code=${row.code}`)
}

const barOption = computed(() => {
  const top20 = rows.value.slice(0, 20)
  const names = top20.map(r => (r.name as string) || (r.code as string))
  const values = top20.map(r => +((r.main_net_inflow as number) / 1e8).toFixed(3))
  return {
    backgroundColor: '#1a1a1a',
    tooltip: { trigger: 'axis', formatter: (p: unknown[]) => {
      const item = (p as { name: string; value: number }[])[0]
      return `${item.name}: ${item.value > 0 ? '+' : ''}${item.value}亿`
    }},
    grid: { left: 60, right: 20, top: 20, bottom: 60 },
    xAxis: { type: 'category', data: names, axisLabel: { color: '#909399', rotate: 30, fontSize: 11 } },
    yAxis: { type: 'value', axisLabel: { color: '#909399', formatter: '{value}亿' } },
    series: [{
      type: 'bar',
      data: values.map(v => ({
        value: v,
        itemStyle: { color: v >= 0 ? RISE_COLOR : FALL_COLOR }
      }))
    }]
  }
})

onMounted(loadData)
</script>

<style scoped>
.fund-flow-view { display: flex; flex-direction: column; gap: 16px; }
.section-card { background: #1f1f1f; border: 1px solid #2c2c2c; }
.section-card :deep(.el-card__header) {
  border-bottom: 1px solid #2c2c2c; padding: 12px 16px;
  color: #e5eaf3; font-size: 14px; font-weight: 600;
}
.filter-bar { display: flex; gap: 12px; align-items: center; flex-wrap: wrap; }
.date-label { font-size: 12px; color: #606266; }
.code-link { color: #409eff; cursor: pointer; }
.code-link:hover { text-decoration: underline; }
.val-pos { color: #f56c6c; }
.val-neg { color: #67c23a; }
</style>
