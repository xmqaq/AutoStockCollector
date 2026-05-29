<template>
  <div class="position-management">
    <el-row :gutter="16">
      <el-col :span="16">
        <el-card shadow="never" class="section-card">
          <template #header>
            <div class="card-header">
              <span>持仓列表</span>
              <el-button type="primary" size="small" @click="showAddDialog = true">
                添加持仓
              </el-button>
            </div>
          </template>
          <el-table :data="positions" stripe size="small" v-loading="loading">
            <el-table-column prop="code" label="代码" width="110">
              <template #default="{ row }">
                <router-link :to="`/stock-detail?code=${row.code}`" class="stock-link">
                  {{ row.code }}
                </router-link>
              </template>
            </el-table-column>
            <el-table-column prop="name" label="名称" width="120" show-overflow-tooltip />
            <el-table-column prop="shares" label="持仓数量" width="100" align="right">
              <template #default="{ row }">{{ row.shares || 0 }}</template>
            </el-table-column>
            <el-table-column prop="avg_cost" label="持仓成本" width="100" align="right">
              <template #default="{ row }">
                {{ (row.avg_cost || 0).toFixed(2) }}
              </template>
            </el-table-column>
            <el-table-column prop="current_price" label="当前价" width="100" align="right">
              <template #default="{ row }">
                {{ (row.current_price || 0).toFixed(2) }}
              </template>
            </el-table-column>
            <el-table-column label="持仓市值" width="120" align="right">
              <template #default="{ row }">
                {{ formatAmount(row.market_value) }}
              </template>
            </el-table-column>
            <el-table-column label="盈亏金额" width="110" align="right">
              <template #default="{ row }">
                <span :class="row.pnl >= 0 ? 'text-rise' : 'text-fall'">
                  {{ formatChange(row.pnl) }}
                </span>
              </template>
            </el-table-column>
            <el-table-column label="盈亏比例" width="100" align="right">
              <template #default="{ row }">
                <span :class="row.pnl_percent >= 0 ? 'text-rise' : 'text-fall'">
                  {{ formatPercent(row.pnl_percent) }}
                </span>
              </template>
            </el-table-column>
            <el-table-column prop="position_ratio" label="仓位占比" width="100">
              <template #default="{ row }">
                <el-progress
                  :percentage="row.position_ratio || 0"
                  :stroke-width="8"
                  :show-text="false"
                  :color="row.pnl >= 0 ? '#67c23a' : '#f56c6c'"
                />
              </template>
            </el-table-column>
            <el-table-column label="止损位" width="100" align="right">
              <template #default="{ row }">
                <span class="price-text stop-loss">{{ (row.stop_loss || 0).toFixed(2) }}</span>
              </template>
            </el-table-column>
            <el-table-column label="目标价" width="100" align="right">
              <template #default="{ row }">
                <span class="price-text target-price">{{ (row.target_price || 0).toFixed(2) }}</span>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="120" fixed="right">
              <template #default="{ row }">
                <el-button type="primary" size="small" text @click="editPosition(row)">
                  编辑
                </el-button>
                <el-button type="danger" size="small" text @click="removePosition(row.code)">
                  删除
                </el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-col>

      <el-col :span="8">
        <el-card shadow="never" class="section-card">
          <template #header><span>收益统计</span></template>
          <el-descriptions :column="1" border size="small">
            <el-descriptions-item label="总成本">
              <span class="text-secondary">{{ formatAmount(incomeStats.totalCost) }}</span>
            </el-descriptions-item>
            <el-descriptions-item label="总市值">
              <span class="text-primary">{{ formatAmount(incomeStats.totalMarketValue) }}</span>
            </el-descriptions-item>
            <el-descriptions-item label="浮动盈亏">
              <span :class="incomeStats.unrealizedPnL >= 0 ? 'text-rise' : 'text-fall'">
                {{ formatChange(incomeStats.unrealizedPnL) }}
              </span>
            </el-descriptions-item>
            <el-descriptions-item label="盈亏比例">
              <span :class="incomeStats.unrealizedPnLPercent >= 0 ? 'text-rise' : 'text-fall'">
                {{ formatPercent(incomeStats.unrealizedPnLPercent) }}
              </span>
            </el-descriptions-item>
            <el-descriptions-item label="平均持仓天数">
              {{ incomeStats.holdingDays }} 天
            </el-descriptions-item>
            <el-descriptions-item label="年化收益率">
              <span :class="incomeStats.annualizedReturn >= 0 ? 'text-rise' : 'text-fall'">
                {{ formatPercent(incomeStats.annualizedReturn) }}
              </span>
            </el-descriptions-item>
            <el-descriptions-item label="持仓股票数">
              {{ positions.length }} 只
            </el-descriptions-item>
          </el-descriptions>
        </el-card>

        <el-card shadow="never" class="section-card" style="margin-top: 12px">
          <ProfitChart :data="profitHistory" title="盈亏曲线" chart-height="280px" />
        </el-card>

        <el-card shadow="never" class="section-card" style="margin-top: 12px">
          <template #header><span>仓位预警</span></template>
          <div class="alert-list">
            <div
              v-for="alert in alerts"
              :key="alert.code"
              class="alert-item"
              :class="alert.type"
            >
              <div class="alert-header">
                <span class="alert-code">{{ alert.code }}</span>
                <el-tag size="small" :type="alert.type === 'danger' ? 'danger' : 'warning'">
                  {{ alert.label }}
                </el-tag>
              </div>
              <div class="alert-content">{{ alert.message }}</div>
            </div>
            <el-empty v-if="alerts.length === 0" description="暂无预警" :image-size="60" />
          </div>
        </el-card>

        <el-card shadow="never" class="section-card" style="margin-top: 12px">
          <template #header><span>持仓分布</span></template>
          <div v-if="distributionData.length > 0" class="distribution-chart">
            <div
              v-for="(item, idx) in distributionData"
              :key="idx"
              class="distribution-item"
            >
              <div class="dist-info">
                <span class="dist-label">{{ item.code }}</span>
                <span class="dist-percent">{{ item.percent.toFixed(1) }}%</span>
              </div>
              <div class="dist-bar-container">
                <div class="dist-bar" :style="{ width: item.percent + '%' }"></div>
              </div>
            </div>
          </div>
          <el-empty v-else description="暂无数据" :image-size="60" />
        </el-card>
      </el-col>
    </el-row>

    <el-dialog v-model="showAddDialog" :title="form.isEdit ? '编辑持仓' : '添加持仓'" width="500px">
      <el-form :model="form" label-width="100px" size="default">
        <el-form-item label="股票代码">
          <el-input v-model="form.code" :disabled="form.isEdit" placeholder="如: SH600000" />
        </el-form-item>
        <el-form-item label="持仓数量">
          <el-input-number v-model="form.shares" :min="0" style="width: 100%" />
        </el-form-item>
        <el-form-item label="持仓成本">
          <el-input-number v-model="form.avg_cost" :min="0" :precision="2" style="width: 100%" />
        </el-form-item>
        <el-form-item label="止损位">
          <el-input-number v-model="form.stop_loss" :min="0" :precision="2" style="width: 100%" />
        </el-form-item>
        <el-form-item label="目标价">
          <el-input-number v-model="form.target_price" :min="0" :precision="2" style="width: 100%" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showAddDialog = false">取消</el-button>
        <el-button type="primary" @click="savePosition">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { positionApi } from '@/api/position'
import ProfitChart from '@/components/ProfitChart/index.vue'

interface Position {
  code: string
  name?: string
  shares: number
  avg_cost: number
  current_price?: number
  market_value?: number
  pnl?: number
  pnl_percent?: number
  position_ratio?: number
  stop_loss: number
  target_price: number
  created_at?: string
}

interface Alert {
  code: string
  label: string
  type: string
  message: string
}

interface IncomeStat {
  totalCost: number
  totalMarketValue: number
  unrealizedPnL: number
  unrealizedPnLPercent: number
  holdingDays: number
  annualizedReturn: number
}

interface ProfitRecord {
  date: string
  value: number
  cost?: number
}

const loading = ref(false)
const showAddDialog = ref(false)
const positions = ref<Position[]>([])
const profitHistory = ref<ProfitRecord[]>([])
const form = ref({
  code: '',
  shares: 0,
  avg_cost: 0,
  stop_loss: 0,
  target_price: 0,
  isEdit: false
})

const totalMarketValue = computed(() => {
  return positions.value.reduce((sum, p) => sum + (p.market_value || 0), 0)
})

const totalCost = computed(() => {
  return positions.value.reduce((sum, p) => sum + (p.shares * p.avg_cost), 0)
})

const totalPnl = computed(() => {
  return positions.value.reduce((sum, p) => sum + (p.pnl || 0), 0)
})

const totalPnlPercent = computed(() => {
  if (totalCost.value === 0) return 0
  return (totalPnl.value / totalCost.value) * 100
})

const incomeStats = computed<IncomeStat>(() => {
  const stats: IncomeStat = {
    totalCost: totalCost.value,
    totalMarketValue: totalMarketValue.value,
    unrealizedPnL: totalPnl.value,
    unrealizedPnLPercent: totalPnlPercent.value,
    holdingDays: 0,
    annualizedReturn: 0
  }
  
  if (positions.value.length > 0) {
    const now = new Date()
    let totalDays = 0
    let count = 0
    
    for (const pos of positions.value) {
      if (pos.created_at) {
        const created = new Date(pos.created_at)
        const days = Math.floor((now.getTime() - created.getTime()) / (1000 * 60 * 60 * 24))
        totalDays += days
        count++
      }
    }
    
    if (count > 0) {
      stats.holdingDays = Math.floor(totalDays / count)
      if (stats.holdingDays > 0 && stats.unrealizedPnLPercent !== 0) {
        stats.annualizedReturn = (stats.unrealizedPnLPercent / stats.holdingDays) * 365
      }
    }
  }
  
  return stats
})

const alerts = computed<Alert[]>(() => {
  const list: Alert[] = []
  
  for (const pos of positions.value) {
    const pnlPercent = pos.pnl_percent ?? 0
    const positionRatio = pos.position_ratio ?? 0
    const currentPrice = pos.current_price ?? 0
    const posName = pos.name || pos.code
    
    if (pnlPercent <= -10) {
      list.push({
        code: pos.code,
        label: '止损预警',
        type: 'danger',
        message: `${posName} 亏损已达 ${Math.abs(pnlPercent).toFixed(2)}%，建议关注`
      })
    } else if (pnlPercent <= -5) {
      list.push({
        code: pos.code,
        label: '亏损预警',
        type: 'warning',
        message: `${posName} 亏损 ${Math.abs(pnlPercent).toFixed(2)}%`
      })
    }
    
    if (positionRatio > 30) {
      list.push({
        code: pos.code,
        label: '仓位过重',
        type: 'warning',
        message: `${posName} 仓位占比 ${positionRatio.toFixed(1)}%，建议分散风险`
      })
    }
    
    if (currentPrice <= pos.stop_loss && pos.stop_loss > 0) {
      list.push({
        code: pos.code,
        label: '触发止损',
        type: 'danger',
        message: `${posName} 当前价已跌破止损位 ${pos.stop_loss.toFixed(2)}`
      })
    }
  }
  
  return list
})

const positionStore = positionApi.state

watch(() => positionStore.positions, (newPositions) => {
  if (newPositions) {
    positions.value = newPositions
  }
}, { immediate: true })

const distributionData = computed(() => {
  if (totalMarketValue.value === 0) return []
  
  return positions.value
    .map(p => ({
      code: p.code,
      percent: ((p.market_value || 0) / totalMarketValue.value) * 100
    }))
    .sort((a, b) => b.percent - a.percent)
})

function formatAmount(amount: number): string {
  if (Math.abs(amount) >= 1e8) {
    return (amount / 1e8).toFixed(2) + '亿'
  } else if (Math.abs(amount) >= 1e4) {
    return (amount / 1e4).toFixed(2) + '万'
  }
  return amount.toFixed(2)
}

function formatChange(value: number): string {
  const prefix = value >= 0 ? '+' : ''
  return prefix + value.toFixed(2)
}

function formatPercent(value: number): string {
  const prefix = value >= 0 ? '+' : ''
  return prefix + value.toFixed(2) + '%'
}

async function loadPositions() {
  loading.value = true
  try {
    await positionApi.loadPositions()
    generateMockProfitHistory()
  } catch {
    positions.value = []
    profitHistory.value = []
  } finally {
    loading.value = false
  }
}

function generateMockProfitHistory() {
  const history: ProfitRecord[] = []
  const now = new Date()
  let cost = 100000
  let value = 100000
  
  for (let i = 90; i >= 0; i--) {
    const date = new Date(now.getTime() - i * 24 * 60 * 60 * 1000)
    const dateStr = date.toISOString().split('T')[0]
    
    const change = (Math.random() - 0.45) * 2000
    value += change
    cost += Math.random() * 100
    
    history.push({
      date: dateStr,
      value: Math.round(value * 100) / 100,
      cost: Math.round(cost * 100) / 100,
    })
  }
  
  profitHistory.value = history
}

async function savePosition() {
  if (!form.value.code) {
    ElMessage.warning('请输入股票代码')
    return
  }
  
  try {
    const positionData = {
      code: form.value.code,
      shares: form.value.shares,
      avg_cost: form.value.avg_cost,
      stop_loss: form.value.stop_loss,
      target_price: form.value.target_price
    }
    
    if (form.value.isEdit) {
      await positionApi.updatePosition(positionData)
    } else {
      await positionApi.addPosition(positionData)
    }
    
    ElMessage.success(form.value.isEdit ? '更新成功' : '保存成功')
    showAddDialog.value = false
    resetForm()
    loadPositions()
  } catch {
    ElMessage.error(form.value.isEdit ? '更新失败' : '保存失败')
  }
}

function resetForm() {
  form.value = {
    code: '',
    shares: 0,
    avg_cost: 0,
    stop_loss: 0,
    target_price: 0,
    isEdit: false
  }
}

function editPosition(row: Position) {
  form.value = {
    code: row.code,
    shares: row.shares,
    avg_cost: row.avg_cost,
    stop_loss: row.stop_loss,
    target_price: row.target_price,
    isEdit: true
  }
  showAddDialog.value = true
}

async function removePosition(code: string) {
  try {
    await ElMessageBox.confirm('确定要删除该持仓吗？', '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    })
    
    await positionApi.deletePosition(code)
    ElMessage.success('删除成功')
    loadPositions()
  } catch {
    // 用户取消
  }
}

onMounted(() => {
  loadPositions()
})
</script>

<style scoped>
.position-management {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
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

.stock-link {
  color: #409eff;
  text-decoration: none;
}

.stock-link:hover {
  text-decoration: underline;
}

.text-rise {
  color: #ef5350;
}

.text-fall {
  color: #26a69a;
}

.text-primary {
  color: #409eff;
}

.text-secondary {
  color: #909399;
}

.price-text {
  font-size: 12px;
}

.stop-loss {
  color: #f56c6c;
}

.target-price {
  color: #67c23a;
}

.alert-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.alert-item {
  padding: 10px 12px;
  border-radius: 4px;
  background: #2c2c2c;
}

.alert-item.danger {
  border-left: 3px solid #f56c6c;
}

.alert-item.warning {
  border-left: 3px solid #e6a23c;
}

.alert-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 4px;
}

.alert-code {
  font-weight: 600;
  color: #e5eaf3;
  font-size: 13px;
}

.alert-content {
  font-size: 12px;
  color: #909399;
}

.distribution-chart {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.distribution-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.dist-info {
  display: flex;
  justify-content: space-between;
  font-size: 12px;
}

.dist-label {
  color: #e5eaf3;
}

.dist-percent {
  color: #909399;
}

.dist-bar-container {
  height: 6px;
  background: #2c2c2c;
  border-radius: 3px;
  overflow: hidden;
}

.dist-bar {
  height: 100%;
  background: #409eff;
  border-radius: 3px;
  transition: width 0.3s ease;
}
</style>
