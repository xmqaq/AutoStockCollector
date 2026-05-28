<template>
  <div class="margin-trading">
    <!-- Filters -->
    <el-card shadow="never" class="section-card">
      <div class="filter-bar">
        <el-date-picker
          v-model="dateRange"
          type="daterange"
          range-separator="至"
          start-placeholder="开始日期"
          end-placeholder="结束日期"
          format="YYYY-MM-DD"
          value-format="YYYY-MM-DD"
          size="small"
          style="width:280px"
        />
        <el-input
          v-model="codeFilter"
          placeholder="股票代码（可选）"
          size="small"
          style="width:200px"
          clearable
        />
        <el-button type="primary" size="small" @click="loadData">
          <el-icon><Search /></el-icon> 查询
        </el-button>
      </div>
    </el-card>

    <!-- Balance chart -->
    <el-card shadow="never" class="section-card" v-loading="loading">
      <template #header><span>融资余额趋势</span></template>
      <div v-if="chartData.length > 0">
        <v-chart :option="lineOption" style="height:300px" autoresize />
      </div>
      <el-empty v-else-if="!loading" description="暂无数据" :image-size="60" />
    </el-card>

    <!-- Table -->
    <el-card shadow="never" class="section-card" v-loading="loading">
      <template #header>
        <span>融资融券明细（共 {{ tableData.length }} 条）</span>
      </template>
      <el-empty v-if="tableData.length === 0 && !loading" description="暂无融资融券数据" />
      <el-table v-else :data="tableData" stripe size="small">
        <el-table-column prop="date" label="日期" width="120" sortable />
        <el-table-column prop="code" label="代码" width="110">
          <template #default="{ row }">
            <el-link type="primary" @click="goToStock(row.code)">{{ row.code }}</el-link>
          </template>
        </el-table-column>
        <el-table-column label="融资余额" width="130" prop="rz_balance" sortable>
          <template #default="{ row }">{{ fmtAmount(row.rz_balance) }}</template>
        </el-table-column>
        <el-table-column label="融资买入" width="130" prop="rz_buy" sortable>
          <template #default="{ row }">{{ fmtAmount(row.rz_buy) }}</template>
        </el-table-column>
        <el-table-column label="融券量" width="120" prop="rq_volume" sortable>
          <template #default="{ row }">{{ fmtAmount(row.rq_volume) }}</template>
        </el-table-column>
        <el-table-column label="融券卖出" width="130" prop="rq_sell" sortable>
          <template #default="{ row }">{{ fmtAmount(row.rq_sell) }}</template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent, DataZoomComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import { marginApi } from '@/api/margin'
import { fmtAmount } from '@/utils/format'
import { normalizeCode } from '@/utils/stockCode'
import type { MarginRecord } from '@/types'
import { Search } from '@element-plus/icons-vue'
import dayjs from 'dayjs'

use([LineChart, GridComponent, TooltipComponent, LegendComponent, DataZoomComponent, CanvasRenderer])

const router = useRouter()
const loading = ref(false)
const tableData = ref<MarginRecord[]>([])
const dateRange = ref<[string, string]>([
  dayjs().subtract(90, 'day').format('YYYY-MM-DD'),
  dayjs().format('YYYY-MM-DD'),
])
const codeFilter = ref('')

const chartData = computed(() => {
  return [...tableData.value].sort((a, b) => a.date.localeCompare(b.date)).slice(0, 60)
})

const lineOption = computed(() => {
  const sorted = chartData.value
  const dates = sorted.map(d => d.date)
  const balances = sorted.map(d => d.rz_balance)
  return {
    backgroundColor: '#1f1f1f',
    tooltip: {
      trigger: 'axis',
      backgroundColor: '#2c2c2c',
      borderColor: '#444',
      textStyle: { color: '#e5eaf3' },
    },
    grid: { left: 80, right: 20, top: 30, bottom: 40 },
    xAxis: {
      type: 'category',
      data: dates,
      axisLabel: { color: '#909399', rotate: 30, fontSize: 10 },
      axisLine: { lineStyle: { color: '#444' } },
    },
    yAxis: {
      type: 'value',
      axisLabel: {
        color: '#909399',
        formatter: (v: number) => (v >= 1e8 ? `${(v / 1e8).toFixed(1)}亿` : `${(v / 1e4).toFixed(0)}万`),
      },
      splitLine: { lineStyle: { color: '#2c2c2c' } },
    },
    series: [
      {
        name: '融资余额',
        type: 'line',
        data: balances,
        smooth: true,
        lineStyle: { color: '#409eff', width: 2 },
        areaStyle: { color: 'rgba(64,158,255,0.1)' },
        showSymbol: false,
      },
    ],
  }
})

async function loadData() {
  loading.value = true
  try {
    const params: { start_date?: string; end_date?: string; code?: string; limit?: number } = {
      limit: 200,
    }
    if (dateRange.value) {
      params.start_date = dateRange.value[0]
      params.end_date = dateRange.value[1]
    }
    if (codeFilter.value) {
      params.code = normalizeCode(codeFilter.value)
    }
    const res = await marginApi.getMargin(params)
    tableData.value = res.data?.data || res.data || []
  } catch {
    tableData.value = []
  } finally {
    loading.value = false
  }
}

function goToStock(code: string) {
  router.push({ path: '/stock-detail', query: { code } })
}

onMounted(() => {
  loadData()
})
</script>

<style scoped>
.margin-trading {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.section-card {
  background: #1f1f1f;
  border: 1px solid #2c2c2c;
}

.section-card :deep(.el-card__header) {
  border-bottom: 1px solid #2c2c2c;
  padding: 12px 16px;
  color: #e5eaf3;
  font-size: 14px;
  font-weight: 600;
}

.filter-bar {
  display: flex;
  gap: 12px;
  align-items: center;
  flex-wrap: wrap;
}
</style>
