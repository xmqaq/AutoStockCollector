<template>
  <div class="smart-pick">
    <el-card shadow="never" class="section-card">
      <template #header>
        <span>AI智能选股</span>
      </template>
      <div class="pick-toolbar">
        <el-checkbox-group v-model="selectedFactors">
          <el-checkbox label="trend">趋势</el-checkbox>
          <el-checkbox label="volume">成交量</el-checkbox>
          <el-checkbox label="value">估值</el-checkbox>
          <el-checkbox label="fund_flow">资金流向</el-checkbox>
          <el-checkbox label="momentum">动量</el-checkbox>
        </el-checkbox-group>
        <el-input-number v-model="topN" :min="5" :max="50" />
        <el-button type="primary" @click="runPick" :loading="loading">
          开始选股
        </el-button>
      </div>
    </el-card>

    <el-card v-if="results.length > 0" shadow="never" class="section-card">
      <template #header>
        <span>推荐结果 ({{ results.length }} 只)</span>
      </template>
      <el-table :data="results" stripe>
        <el-table-column prop="code" label="代码" width="120">
          <template #default="{ row }">
            <router-link :to="`/stock-detail?code=${row.code}`">{{ row.code }}</router-link>
          </template>
        </el-table-column>
        <el-table-column prop="total" label="综合评分" width="100">
          <template #default="{ row }">
            <el-tag :type="row.total >= 70 ? 'success' : row.total >= 50 ? 'warning' : 'info'">
              {{ row.total.toFixed(1) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="趋势" width="80">
          <template #default="{ row">{{ (row.scores.trend || '--').toFixed(1) }}</template>
        </el-table-column>
        <el-table-column label="量能" width="80">
          <template #default="{ row">{{ (row.scores.volume || '--').toFixed(1) }}</template>
        </el-table-column>
        <el-table-column label="估值" width="80">
          <template #default="{ row">{{ (row.scores.value || '--').toFixed(1) }}</template>
        </el-table-column>
        <el-table-column label="资金" width="80">
          <template #default="{ row">{{ row.scores.fund_flow ? row.scores.fund_flow.toFixed(1) : '--' }}</template>
        </el-table-column>
        <el-table-column label="动量" width="80">
          <template #default="{ row">{{ row.scores.momentum ? row.scores.momentum.toFixed(1) : '--' }}</template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { pickerApi, type PickedStock } from '@/api/ai'

const selectedFactors = ref(['trend', 'volume', 'value', 'fund_flow'])
const topN = ref(10)
const loading = ref(false)
const results = ref<PickedStock[]>([])

async function runPick() {
  loading.value = true
  try {
    const res = await pickerApi.smartPick(topN.value, selectedFactors.value)
    results.value = res.data?.data || []
  } catch {
    results.value = []
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.smart-pick {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.pick-toolbar {
  display: flex;
  gap: 16px;
  align-items: center;
  flex-wrap: wrap;
}
.section-card {
  background: #1f1f1f;
  border: 1px solid #2c2c2c;
}
</style>