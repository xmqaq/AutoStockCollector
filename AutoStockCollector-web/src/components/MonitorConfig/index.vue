<template>
  <div class="monitor-config">
    <el-card shadow="never" class="section-card">
      <template #header>
        <div class="header-toolbar">
          <span>AI盯盘配置</span>
          <el-switch v-model="enabled" active-text="开启盯盘" inactive-text="关闭" />
        </div>
      </template>
      
      <div class="config-sections">
        <div class="config-section">
          <div class="section-title">
            <el-icon><TrendCharts /></el-icon>
            <span>价格告警</span>
          </div>
          <div class="config-list">
            <div class="config-item">
              <span class="item-label">上涨告警阈值</span>
              <el-input-number v-model="config.priceRiseThreshold" :min="0" :max="100" :step="0.5" size="small" />
              <span class="item-suffix">%</span>
            </div>
            <div class="config-item">
              <span class="item-label">下跌告警阈值</span>
              <el-input-number v-model="config.priceFallThreshold" :min="0" :max="100" :step="0.5" size="small" />
              <span class="item-suffix">%</span>
            </div>
            <div class="config-item">
              <span class="item-label">快速下跌告警</span>
              <el-input-number v-model="config.quickFallThreshold" :min="0" :max="20" :step="0.5" size="small" />
              <span class="item-suffix">%（如5分钟内）</span>
            </div>
          </div>
        </div>
        
        <div class="config-section">
          <div class="section-title">
            <el-icon><Histogram /></el-icon>
            <span>成交量告警</span>
          </div>
          <div class="config-list">
            <div class="config-item">
              <span class="item-label">放量倍数阈值</span>
              <el-input-number v-model="config.volumeRatioThreshold" :min="1" :max="10" :step="0.5" size="small" />
              <span class="item-suffix">倍</span>
            </div>
            <div class="config-item">
              <span class="item-label">缩量告警</span>
              <el-input-number v-model="config.shrinkRatioThreshold" :min="0" :max="100" :step="5" size="small" />
              <span class="item-suffix">%</span>
            </div>
          </div>
        </div>
        
        <div class="config-section">
          <div class="section-title">
            <el-icon><Money /></el-icon>
            <span>资金流告警</span>
          </div>
          <div class="config-list">
            <div class="config-item">
              <span class="item-label">主力净流入阈值</span>
              <el-input-number v-model="config.mainFlowThreshold" :min="0" :step="1000" size="small" />
              <span class="item-suffix">万元</span>
            </div>
            <div class="config-item">
              <span class="item-label">连续净流入天数</span>
              <el-input-number v-model="config.continuousDays" :min="1" :max="10" size="small" />
              <span class="item-suffix">天</span>
            </div>
          </div>
        </div>
        
        <div class="config-section">
          <div class="section-title">
            <el-icon><Bell /></el-icon>
            <span>通知方式</span>
          </div>
          <div class="config-list">
            <div class="config-item">
              <span class="item-label">站内通知</span>
              <el-switch v-model="config.notifyInApp" />
            </div>
            <div class="config-item">
              <span class="item-label">邮件通知</span>
              <el-switch v-model="config.notifyEmail" />
            </div>
            <div class="config-item" v-if="config.notifyEmail">
              <span class="item-label">邮箱地址</span>
              <el-input v-model="config.email" placeholder="your@email.com" size="small" style="width: 200px" />
            </div>
            <div class="config-item">
              <span class="item-label">Webhook通知</span>
              <el-switch v-model="config.notifyWebhook" />
            </div>
            <div class="config-item" v-if="config.notifyWebhook">
              <span class="item-label">Webhook地址</span>
              <el-input v-model="config.webhookUrl" placeholder="https://..." size="small" style="width: 280px" />
            </div>
          </div>
        </div>
      </div>
      
      <div class="config-footer">
        <el-button @click="resetConfig">重置</el-button>
        <el-button type="primary" @click="saveConfig" :loading="saving">保存配置</el-button>
      </div>
    </el-card>
    
    <el-card shadow="never" class="section-card">
      <template #header>
        <span>盯盘股票列表</span>
        <el-button size="small" type="primary" @click="showAddDialog = true">
          <el-icon><Plus /></el-icon> 添加股票
        </el-button>
      </template>
      
      <el-table :data="monitorStocks" stripe size="small">
        <el-table-column prop="code" label="代码" width="100">
          <template #default="{ row }">
            <router-link :to="`/stock-detail?code=${row.code}`" class="stock-link">
              {{ row.code }}
            </router-link>
          </template>
        </el-table-column>
        <el-table-column prop="name" label="名称" width="100" show-overflow-tooltip />
        <el-table-column label="当前价" width="90" align="right">
          <template #default="{ row }">
            <span :class="row.change_rate >= 0 ? 'rise' : 'fall'">
              {{ row.price?.toFixed(2) || '--' }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="涨跌幅" width="90" align="right">
          <template #default="{ row }">
            <span :class="row.change_rate >= 0 ? 'rise' : 'fall'">
              {{ row.change_rate >= 0 ? '+' : '' }}{{ (row.change_rate || 0).toFixed(2) }}%
            </span>
          </template>
        </el-table-column>
        <el-table-column label="今日高/低" width="120">
          <template #default="{ row }">
            <span class="price-range">
              {{ (row.high || 0).toFixed(2) }} / {{ (row.low || 0).toFixed(2) }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.alertType" size="small">
              {{ row.alertLabel }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="100" fixed="right">
          <template #default="{ row }">
            <el-button size="small" text type="danger" @click="removeStock(row.code)">
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
    
    <el-dialog v-model="showAddDialog" title="添加盯盘股票" width="400px">
      <el-form :model="addForm" label-width="80px">
        <el-form-item label="股票代码">
          <el-select
            v-model="addForm.code"
            filterable
            placeholder="搜索或输入代码"
            style="width: 100%"
          >
            <el-option
              v-for="s in watchlist"
              :key="s.code"
              :label="`${s.code} ${s.name}`"
              :value="s.code"
            />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showAddDialog = false">取消</el-button>
        <el-button type="primary" @click="addStock">添加</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { TrendCharts, Histogram, Money, Bell, Plus } from '@element-plus/icons-vue'
import { watchlistApi } from '@/api/watchlist'
import { marketApi } from '@/api/market'
import { ElMessage } from 'element-plus'

interface MonitorConfig {
  priceRiseThreshold: number
  priceFallThreshold: number
  quickFallThreshold: number
  volumeRatioThreshold: number
  shrinkRatioThreshold: number
  mainFlowThreshold: number
  continuousDays: number
  notifyInApp: boolean
  notifyEmail: boolean
  notifyWebhook: boolean
  email: string
  webhookUrl: string
}

interface MonitorStock {
  code: string
  name: string
  price?: number
  change_rate?: number
  high?: number
  low?: number
  alertType?: string
  alertLabel?: string
}

const enabled = ref(false)
const saving = ref(false)
const showAddDialog = ref(false)
const watchlist = ref<{ code: string; name: string }[]>([])
const monitorStocks = ref<MonitorStock[]>([])
const config = ref<MonitorConfig>({
  priceRiseThreshold: 5,
  priceFallThreshold: 3,
  quickFallThreshold: 2,
  volumeRatioThreshold: 2,
  shrinkRatioThreshold: 30,
  mainFlowThreshold: 5000,
  continuousDays: 3,
  notifyInApp: true,
  notifyEmail: false,
  notifyWebhook: false,
  email: '',
  webhookUrl: '',
})

const addForm = ref({
  code: '',
})

async function loadWatchlist() {
  try {
    const res = await watchlistApi.getWatchlist()
    watchlist.value = res.data?.data || res.data || []
    const codes = watchlist.value.slice(0, 10).map((s: any) => s.code)
    const base = watchlist.value.slice(0, 10).map((s: any) => ({
      ...s,
      price: undefined as number | undefined,
      change_rate: 0,
      high: undefined as number | undefined,
      low: undefined as number | undefined,
      alertType: 'success',
      alertLabel: '正常',
    }))
    if (codes.length) {
      try {
        const qres = await marketApi.getRealtimeQuotes(codes)
        const quoteMap: Record<string, any> = {}
        ;(qres.data?.data || []).forEach((q: any) => { quoteMap[q.code] = q })
        base.forEach(s => {
          const q = quoteMap[s.code]
          if (q) {
            s.price = q.price
            s.change_rate = q.change ?? 0
            s.high = q.high
            s.low = q.low
          }
        })
      } catch {
        // 行情拉取失败时保留空值，不显示错误数据
      }
    }
    monitorStocks.value = base
  } catch {
    watchlist.value = []
    monitorStocks.value = []
  }
}

function saveConfig() {
  saving.value = true
  localStorage.setItem('monitorConfig', JSON.stringify({
    enabled: enabled.value,
    ...config.value,
  }))
  setTimeout(() => {
    saving.value = false
    ElMessage.success('配置已保存')
  }, 500)
}

function resetConfig() {
  config.value = {
    priceRiseThreshold: 5,
    priceFallThreshold: 3,
    quickFallThreshold: 2,
    volumeRatioThreshold: 2,
    shrinkRatioThreshold: 30,
    mainFlowThreshold: 5000,
    continuousDays: 3,
    notifyInApp: true,
    notifyEmail: false,
    notifyWebhook: false,
    email: '',
    webhookUrl: '',
  }
  ElMessage.info('配置已重置')
}

async function addStock() {
  if (!addForm.value.code) {
    ElMessage.warning('请选择股票')
    return
  }
  const stock = watchlist.value.find(s => s.code === addForm.value.code)
  if (stock && !monitorStocks.value.find(s => s.code === addForm.value.code)) {
    const entry: MonitorStock = {
      ...stock,
      price: undefined,
      change_rate: 0,
      high: undefined,
      low: undefined,
      alertType: 'success',
      alertLabel: '正常',
    }
    try {
      const qres = await marketApi.getRealtimeQuotes([stock.code])
      const q = (qres.data?.data || [])[0]
      if (q) {
        entry.price = q.price
        entry.change_rate = q.change ?? 0
        entry.high = q.high
        entry.low = q.low
      }
    } catch { /* ignore */ }
    monitorStocks.value.push(entry)
    ElMessage.success('已添加盯盘')
    showAddDialog.value = false
    addForm.value.code = ''
  }
}

function removeStock(code: string) {
  monitorStocks.value = monitorStocks.value.filter(s => s.code !== code)
  ElMessage.info('已移除')
}

onMounted(() => {
  const saved = localStorage.getItem('monitorConfig')
  if (saved) {
    try {
      const data = JSON.parse(saved)
      enabled.value = data.enabled || false
      Object.assign(config.value, data)
    } catch {
      // ignore
    }
  }
  loadWatchlist()
})
</script>

<style scoped>
.monitor-config {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.header-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.config-sections {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.config-section {
  background: var(--border-color);
  border-radius: 8px;
  padding: 16px;
}

.section-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 12px;
}

.config-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.config-item {
  display: flex;
  align-items: center;
  gap: 12px;
}

.item-label {
  font-size: 13px;
  color: var(--text-muted);
  min-width: 120px;
}

.item-suffix {
  font-size: 12px;
  color: var(--text-faint);
}

.config-footer {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px solid var(--border-color);
}

.stock-link {
  color: #409eff;
  text-decoration: none;
}

.stock-link:hover {
  text-decoration: underline;
}

.rise {
  color: #ef5350;
}

.fall {
  color: #26a69a;
}

.price-range {
  font-size: 12px;
  color: var(--text-muted);
}

.section-card {
  background: var(--bg-card);
  border: 1px solid var(--border-color);
}

.section-card :deep(.el-card__header) {
  border-bottom: 1px solid var(--border-color);
  padding: 12px 16px;
  color: var(--text-primary);
  font-size: 14px;
  font-weight: 600;
  display: flex;
  justify-content: space-between;
  align-items: center;
}
</style>