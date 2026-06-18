<template>
  <div class="ff-page">
    <!-- Stats -->
    <div class="ff-stats">
      <el-card shadow="never" class="stat-card">
        <div class="stat-label">监测总量</div>
        <div class="stat-value">{{ summary.total }}</div>
      </el-card>
      <el-card shadow="never" class="stat-card sc-inflow">
        <div class="stat-label">大幅流入</div>
        <div class="stat-value">{{ summary.big_inflow }}</div>
      </el-card>
      <el-card shadow="never" class="stat-card sc-outflow">
        <div class="stat-label">大幅流出</div>
        <div class="stat-value">{{ summary.big_outflow }}</div>
      </el-card>
      <el-card shadow="never" class="stat-card sc-consec-in">
        <div class="stat-label">连续流入</div>
        <div class="stat-value">{{ summary.consec_inflow }}</div>
      </el-card>
      <el-card shadow="never" class="stat-card sc-consec-out">
        <div class="stat-label">连续流出</div>
        <div class="stat-value">{{ summary.consec_outflow }}</div>
      </el-card>
      <el-card shadow="never" class="stat-card sc-reversal">
        <div class="stat-label">趋势反转</div>
        <div class="stat-value">{{ summary.reversals }}</div>
      </el-card>
    </div>

    <!-- Filter -->
    <div class="ff-filter">
      <el-input v-model="searchText" placeholder="搜索股票代码/名称" clearable size="small" style="width: 220px;" @input="onFilter" />
      <el-select v-model="typeFilter" placeholder="异动类型" clearable size="small" style="width: 140px;" @change="onFilter">
        <el-option label="全部" value="" />
        <el-option label="大幅流入" value="大幅流入" />
        <el-option label="大幅流出" value="大幅流出" />
        <el-option label="连续流入" value="连续流入" />
        <el-option label="连续流出" value="连续流出" />
        <el-option label="趋势反转" value="趋势反转" />
      </el-select>
    </div>

    <!-- Table -->
    <el-card shadow="never" class="ff-table-card">
      <el-table :data="filtered" v-loading="loading" stripe size="small" max-height="700" @row-click="handleRowClick" style="cursor: pointer;">
        <el-table-column label="股票" min-width="140">
          <template #default="{ row }">
            <div class="stock-cell">
              <span class="stock-name">{{ row.name }}</span>
              <span class="stock-code">{{ row.code }}</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="异动类型" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="tagType(row.anomaly_type)" size="small" effect="dark">
              {{ row.anomaly_type }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="主力净流入" width="120" align="right" sortable prop="latest_net">
          <template #default="{ row }">
            <span :class="netClass(row.latest_net)">{{ fmtNet(row.latest_net) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="净占比" width="90" align="right" sortable prop="net_ratio">
          <template #default="{ row }">{{ (row.net_ratio * 100).toFixed(1) }}%</template>
        </el-table-column>
        <el-table-column label="Z值" width="80" align="right" sortable prop="z_score">
          <template #default="{ row }">
            <span :class="zClass(row.z_score)">{{ row.z_score > 0 ? '+' : '' }}{{ row.z_score.toFixed(1) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="连续天数" width="80" align="center" sortable prop="consecutive_days">
          <template #default="{ row }">
            <span :class="netClass(row.consecutive_days)">{{ row.consecutive_days > 0 ? '+' : '' }}{{ row.consecutive_days }}</span>
          </template>
        </el-table-column>
        <el-table-column label="成交额" width="110" align="right">
          <template #default="{ row }">¥{{ fmtAmount(row.latest_amount) }}</template>
        </el-table-column>
        <el-table-column label="涨跌幅" width="80" align="right" sortable prop="latest_change">
          <template #default="{ row }">
            <span :class="netClass(row.latest_change)">{{ row.latest_change > 0 ? '+' : '' }}{{ row.latest_change }}%</span>
          </template>
        </el-table-column>
        <el-table-column label="换手率" width="80" align="right">
          <template #default="{ row }">{{ row.latest_turnover }}%</template>
        </el-table-column>
        <el-table-column label="日期" width="100">
          <template #default="{ row }">{{ row.latest_date }}</template>
        </el-table-column>
      </el-table>
      <el-empty v-if="!loading && filtered.length === 0" description="暂无数据" :image-size="60" />
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { monitorApi, type FundFlowAnomaly } from '@/api/monitor'

const loading = ref(false)
const items = ref<FundFlowAnomaly[]>([])
const summary = ref({ total: 0, big_inflow: 0, big_outflow: 0, consec_inflow: 0, consec_outflow: 0, reversals: 0 })
const searchText = ref('')
const typeFilter = ref('')

const filtered = computed(() => {
  let list = items.value
  if (searchText.value) {
    const q = searchText.value.toLowerCase()
    list = list.filter(r => r.code.toLowerCase().includes(q) || r.name.toLowerCase().includes(q))
  }
  if (typeFilter.value) {
    list = list.filter(r => r.anomaly_type === typeFilter.value)
  }
  return list
})

function onFilter() {}

function tagType(t: string) {
  if (t === '大幅流入' || t === '连续流入') return 'danger'
  if (t === '大幅流出' || t === '连续流出') return 'success'
  if (t === '趋势反转') return 'warning'
  return 'info'
}

function netClass(v: number) {
  if (v > 0) return 'up'
  if (v < 0) return 'dn'
  return ''
}

function zClass(v: number) {
  if (v > 1.5) return 'up'
  if (v < -1.5) return 'dn'
  return ''
}

function fmtNet(v: number) {
  const av = Math.abs(v)
  if (av >= 1e8) return `${(v / 1e8).toFixed(2)}亿`
  if (av >= 1e4) return `${(v / 1e4).toFixed(0)}万`
  return v.toFixed(0)
}

function fmtAmount(v: number) {
  if (v >= 1e8) return `${(v / 1e8).toFixed(2)}亿`
  if (v >= 1e4) return `${(v / 1e4).toFixed(0)}万`
  return v.toFixed(0)
}

function handleRowClick(row: FundFlowAnomaly) {
  window.open(`/stock/${row.code.replace(/^(SH|SZ)/, '')}`, '_blank')
}

async function fetchData() {
  loading.value = true
  try {
    const res = await monitorApi.getFundFlowAnomalies()
    items.value = res.data?.data ?? []
    summary.value = res.data?.summary ?? summary.value
  } catch {
    items.value = []
  } finally {
    loading.value = false
  }
}

onMounted(fetchData)
</script>

<style scoped>
.ff-page { display: flex; flex-direction: column; gap: 12px; }
.ff-stats { display: flex; gap: 10px; flex-wrap: wrap; }
.stat-card { flex: 1; min-width: 100px; text-align: center; }
.stat-label { font-size: 12px; color: var(--text-muted, #999); }
.stat-value { font-size: 20px; font-weight: 700; }
.sc-inflow .stat-value { color: #F23645; }
.sc-outflow .stat-value { color: #11C27E; }
.sc-consec-in .stat-value { color: #e6a23c; }
.sc-consec-out .stat-value { color: #909399; }
.sc-reversal .stat-value { color: #409eff; }
.ff-filter { display: flex; gap: 8px; }
.ff-table-card { flex: 1; }
.stock-cell { display: flex; flex-direction: column; line-height: 1.4; }
.stock-name { font-weight: 600; font-size: 13px; }
.stock-code { font-size: 11px; color: var(--text-faint, #bbb); font-family: var(--font-mono); }
.up { color: #F23645; font-weight: 600; }
.dn { color: #11C27E; font-weight: 600; }
</style>
