<template>
  <div class="alert-notification">
    <div class="alert-header">
      <span class="alert-title">告警通知</span>
      <div class="header-actions">
        <el-badge :value="unreadCount" :hidden="unreadCount === 0" :max="99">
          <el-button size="small" @click="markAllRead" :disabled="unreadCount === 0">
            全部已读
          </el-button>
        </el-badge>
      </div>
    </div>
    
    <div class="alert-tabs">
      <el-radio-group v-model="activeTab" size="small">
        <el-radio-button label="all">全部</el-radio-button>
        <el-radio-button label="price">价格告警</el-radio-button>
        <el-radio-button label="volume">成交量</el-radio-button>
        <el-radio-button label="flow">资金流</el-radio-button>
      </el-radio-group>
    </div>
    
    <div class="alert-list">
      <div 
        v-for="(alert, idx) in filteredAlerts" 
        :key="idx"
        :class="['alert-item', alert.level, { unread: !alert.read }]"
        @click="handleAlertClick(alert)"
      >
        <div class="alert-icon">
          <el-icon v-if="alert.type === 'price'" color="#c9943a"><TrendCharts /></el-icon>
          <el-icon v-else-if="alert.type === 'volume'" color="#3f7fae"><Histogram /></el-icon>
          <el-icon v-else-if="alert.type === 'flow'" color="#3f9d70"><Money /></el-icon>
          <el-icon v-else color="#909399"><Bell /></el-icon>
        </div>
        <div class="alert-content">
          <div class="alert-title-row">
            <span class="alert-stock">{{ alert.code }} {{ alert.name }}</span>
            <span class="alert-time">{{ alert.time }}</span>
          </div>
          <div class="alert-message">{{ alert.message }}</div>
          <div class="alert-detail" v-if="alert.detail">
            {{ alert.detail }}
          </div>
        </div>
        <div class="alert-actions">
          <el-button size="small" text @click.stop="viewStock(alert.code)">
            查看
          </el-button>
          <el-button size="small" text type="danger" @click.stop="deleteAlert(idx)">
            删除
          </el-button>
        </div>
      </div>
      
      <el-empty v-if="filteredAlerts.length === 0" description="暂无告警记录" :image-size="60" />
    </div>
    
    <div class="alert-settings">
      <el-divider content-position="left">通知设置</el-divider>
      <div class="setting-item">
        <span>免打扰时段</span>
        <el-time-select
          v-model="quietStart"
          placeholder="开始"
          style="width: 120px"
          start="00:00"
          step="01:00"
          end="23:00"
        />
        <span>至</span>
        <el-time-select
          v-model="quietEnd"
          placeholder="结束"
          style="width: 120px"
          start="00:00"
          step="01:00"
          end="23:00"
        />
      </div>
      <div class="setting-item">
        <span>声音提醒</span>
        <el-switch v-model="soundEnabled" />
      </div>
      <div class="setting-item">
        <span>桌面通知</span>
        <el-switch v-model="desktopEnabled" />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { TrendCharts, Histogram, Money, Bell } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'

interface Alert {
  id: string
  code: string
  name: string
  type: 'price' | 'volume' | 'flow' | 'other'
  level: 'info' | 'warning' | 'danger'
  message: string
  detail?: string
  time: string
  read: boolean
}

const router = useRouter()

const activeTab = ref('all')
const alerts = ref<Alert[]>([])
const quietStart = ref('22:00')
const quietEnd = ref('08:00')
const soundEnabled = ref(true)
const desktopEnabled = ref(true)

const filteredAlerts = computed(() => {
  if (activeTab.value === 'all') return alerts.value
  return alerts.value.filter(a => a.type === activeTab.value)
})

const unreadCount = computed(() => alerts.value.filter(a => !a.read).length)

function handleAlertClick(alert: Alert) {
  alert.read = true
}

function markAllRead() {
  alerts.value.forEach(a => a.read = true)
}

function viewStock(code: string) {
  router.push({ path: '/stock-detail', query: { code } })
}

function deleteAlert(idx: number) {
  alerts.value.splice(idx, 1)
  ElMessage.info('已删除')
}

function addMockAlert() {
  const types = ['price', 'volume', 'flow'] as const
  const type = types[Math.floor(Math.random() * types.length)]
  const levels = ['info', 'warning', 'danger'] as const
  const level = levels[Math.floor(Math.random() * levels.length)]
  
  const messages = {
    price: ['价格突破新高', '快速下跌预警', '触及止损位'],
    volume: ['成交量异常放大', '主力资金大幅流入', '量能萎缩'],
    flow: ['连续3日净流入', '大单净买入', '资金出逃'],
  }
  
  alerts.value.unshift({
    id: `alert_${Date.now()}`,
    code: `SH${600000 + Math.floor(Math.random() * 100)}`,
    name: '股票名称',
    type,
    level,
    message: messages[type][Math.floor(Math.random() * 3)],
    detail: `当前价格: ${(Math.random() * 100 + 10).toFixed(2)}`,
    time: new Date().toLocaleTimeString(),
    read: false,
  })
}

defineExpose({ addMockAlert })
</script>

<style scoped>
.alert-notification {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.alert-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.alert-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
}

.alert-tabs {
  margin-bottom: 8px;
}

.alert-list {
  max-height: 400px;
  overflow-y: auto;
}

.alert-item {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 12px;
  background: var(--border-color);
  border-radius: 8px;
  margin-bottom: 8px;
  cursor: pointer;
  transition: background 0.2s;
}

.alert-item:hover {
  background: var(--border-strong);
}

.alert-item.unread {
  background: rgba(21, 89, 140, 0.1);
  border-left: 3px solid var(--el-color-primary);
}

.alert-item.warning {
  border-left: 3px solid var(--el-color-warning);
}

.alert-item.danger {
  border-left: 3px solid var(--el-color-danger);
}

.alert-icon {
  flex-shrink: 0;
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: var(--border-strong);
  display: flex;
  align-items: center;
  justify-content: center;
}

.alert-content {
  flex: 1;
  min-width: 0;
}

.alert-title-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 4px;
}

.alert-stock {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
}

.alert-time {
  font-size: 11px;
  color: var(--text-muted);
}

.alert-message {
  font-size: 12px;
  color: var(--text-primary);
  margin-bottom: 2px;
}

.alert-detail {
  font-size: 11px;
  color: var(--text-muted);
}

.alert-actions {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.alert-settings {
  background: var(--border-color);
  border-radius: 8px;
  padding: 12px;
}

.setting-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px 0;
  font-size: 13px;
  color: var(--text-muted);
}

.setting-item span:first-child {
  min-width: 80px;
}
</style>