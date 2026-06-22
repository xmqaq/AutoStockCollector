<template>
  <div class="realtime-signals-widget" v-loading="loading">
    <div class="widget-header">
      <div class="header-left">
        <h2 class="title"><el-icon><Monitor /></el-icon> 实时异动监控</h2>
        <div class="live-indicator">
          <span class="pulse"></span> 实时扫描中
        </div>
      </div>
      <el-button class="modern-btn" text @click="router.push('/ai-monitor')">
        详情监控 →
      </el-button>
    </div>

    <div class="signals-list">
      <div v-if="signals.length === 0" class="empty-state">
        <el-empty description="暂无异动信号" :image-size="60" />
      </div>
      
      <div 
        v-else 
        v-for="sig in signals.slice(0, 10)" 
        :key="sig.code" 
        class="signal-item"
        @click="goToStock(sig.code)"
      >
        <div class="signal-time">{{ formatTime(sig.updated_at) }}</div>
        
        <div class="signal-content">
          <div class="stock-badge">
            <span class="s-name">{{ sig.name }}</span>
            <span class="s-code">{{ sig.code }}</span>
          </div>
          
          <div class="signal-desc">
            <span class="desc-text">{{ getSignalDesc(sig) }}</span>
            <el-tag 
              size="small" 
              :type="sig.composite?.signal === 'buy' ? 'danger' : (sig.composite?.signal === 'sell' ? 'success' : 'info')"
              effect="dark"
              class="mini-tag"
            >
              {{ sig.composite?.signal === 'buy' ? '看多' : (sig.composite?.signal === 'sell' ? '看空' : '观望') }}
            </el-tag>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { Monitor } from '@element-plus/icons-vue'
import { monitorApi } from '@/api/monitor'

const router = useRouter()
const loading = ref(true)
const signals = ref<any[]>([])
let timer: ReturnType<typeof setInterval>

function goToStock(code: string) {
  router.push({ path: '/stock-detail', query: { code } })
}

function formatTime(ts: string) {
  if (!ts) return ''
  const date = new Date(ts)
  return `${String(date.getHours()).padStart(2, '0')}:${String(date.getMinutes()).padStart(2, '0')}`
}

function getSignalDesc(sig: any) {
  if (sig.composite?.divergence && sig.composite.divergence !== '无') {
    return `技术面与基本面背离: ${sig.composite.divergence}`
  }
  if (sig.short_term?.reasons && sig.short_term.reasons.length > 0) {
    return sig.short_term.reasons[0]
  }
  return sig.composite?.label || '发生异动'
}

async function loadData() {
  try {
    const res = await monitorApi.getSignals()
    const data = res.data?.data || res.data || []
    signals.value = Array.isArray(data) ? data : []
  } catch (err) {
    console.error('Failed to load signals', err)
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  loadData()
  timer = setInterval(loadData, 15000) // Refresh every 15s for live feel
})

onUnmounted(() => {
  clearInterval(timer)
})
</script>

<style scoped>
.realtime-signals-widget {
  display: flex;
  flex-direction: column;
  height: 100%;
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  padding: inherit; /* inherit padding from card body */
}

.widget-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
  flex-shrink: 0;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.title {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
  display: flex;
  align-items: center;
  gap: 6px;
}

.title .el-icon {
  color: var(--brand-500);
}

.live-indicator {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: var(--el-color-success);
  background: var(--el-color-success-light-9);
  padding: 2px 8px;
  border-radius: 12px;
}

.pulse {
  width: 6px;
  height: 6px;
  background-color: var(--el-color-success);
  border-radius: 50%;
  box-shadow: 0 0 0 0 rgba(103, 194, 58, 0.7);
  animation: pulse 1.5s infinite;
}

@keyframes pulse {
  0% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(103, 194, 58, 0.7); }
  70% { transform: scale(1); box-shadow: 0 0 0 6px rgba(103, 194, 58, 0); }
  100% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(103, 194, 58, 0); }
}

.modern-btn {
  color: var(--brand-500);
  font-weight: 500;
}

.signals-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding-right: 4px;
}

.signals-list::-webkit-scrollbar {
  width: 4px;
}
.signals-list::-webkit-scrollbar-thumb {
  background-color: var(--border-color);
  border-radius: 2px;
}

.signal-item {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 10px;
  border-radius: 8px;
  background: var(--bg-page);
  border: 1px solid transparent;
  cursor: pointer;
  transition: all 0.2s;
  position: relative;
}

.signal-item::before {
  content: '';
  position: absolute;
  left: 0;
  top: 10px;
  bottom: 10px;
  width: 3px;
  background: var(--border-color);
  border-radius: 0 2px 2px 0;
  opacity: 0.5;
}

.signal-item:hover {
  background: var(--bg-hover-subtle);
  border-color: var(--border-light);
}

.signal-item:hover::before {
  background: var(--brand-500);
  opacity: 1;
}

.signal-time {
  font-size: 11px;
  color: var(--text-muted);
  font-family: monospace;
  padding-top: 2px;
  min-width: 40px;
}

.signal-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.stock-badge {
  display: flex;
  align-items: baseline;
  gap: 6px;
}

.s-name {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
}

.s-code {
  font-size: 11px;
  color: var(--text-secondary);
}

.signal-desc {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 8px;
}

.desc-text {
  font-size: 12px;
  color: var(--text-regular);
  line-height: 1.4;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.mini-tag {
  transform: scale(0.9);
  transform-origin: right center;
}

.empty-state {
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
}
</style>