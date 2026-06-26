<template>
  <div class="sector-flow">
    <div class="playback-toolbar">
      <div class="playback-controls">
        <el-button 
          :icon="isPlaying ? VideoPause : VideoPlay" 
          circle 
          type="primary" 
          @click="togglePlay" 
        />
        <div class="time-display">{{ formatTime(currentTime) }}</div>
      </div>
      <el-slider 
        v-model="currentTime" 
        :min="0" 
        :max="240" 
        :step="1" 
        :show-tooltip="false" 
        class="time-slider"
        @change="handleSliderChange"
      />
      <div class="view-switch">
        <el-radio-group v-model="currentView" size="default">
          <el-radio-button label="chart">
            <el-icon><DataBoard /></el-icon> 热力图
          </el-radio-button>
          <el-radio-button label="table">
            <el-icon><List /></el-icon> 列表
          </el-radio-button>
        </el-radio-group>
      </div>
    </div>

    <SectorChart 
      v-if="currentView === 'chart'"
      :loading="loading"
      :sectors="displaySectors"
      @refresh="loadData"
      @sector-click="handleSectorClick"
    />

    <SectorTable 
      v-else
      :loading="loading"
      :sectors="displaySectors"
      @show-stocks="loadSectorStocks"
    />

    <SectorDrawer 
      v-model:visible="drawerVisible"
      :sector-name="selectedSector"
      :loading="stocksLoading"
      :stocks="sectorStocks"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed, onUnmounted } from 'vue'
import { VideoPlay, VideoPause, DataBoard, List } from '@element-plus/icons-vue'
import { sectorApi } from '@/api/sector'
import type { SectorRecord } from '@/types'

import SectorChart from './components/SectorChart.vue'
import SectorTable from './components/SectorTable.vue'
import SectorDrawer from './components/SectorDrawer.vue'

const loading = ref(false)
const stocksLoading = ref(false)
const sectors = ref<SectorRecord[]>([])
const drawerVisible = ref(false)
const selectedSector = ref('')
const sectorStocks = ref<any[]>([])

// 视图切换控制
const currentView = ref<'chart' | 'table'>('chart')

// 播放控制
const isPlaying = ref(false)
const maxTime = ref(240) // 当前真实时间对应的最大允许进度
const currentTime = ref(240) // 滑块当前所在进度
let playTimer: number | null = null

// 根据当前真实时间计算当前进度
function updateMaxTimeByRealTime() {
  const now = new Date()
  const hours = now.getHours()
  const minutes = now.getMinutes()
  
  // 转换成从 00:00 开始的分钟数
  const currentTotalMinutes = hours * 60 + minutes
  
  // 9:30 的分钟数是 570
  // 11:30 的分钟数是 690
  // 13:00 的分钟数是 780
  // 15:00 的分钟数是 900
  
  if (currentTotalMinutes < 570) {
    // 9:30 之前，当天还没开盘，最大进度为0（代表当天最初时刻）
    maxTime.value = 0
  } else if (currentTotalMinutes >= 570 && currentTotalMinutes <= 690) {
    // 9:30 - 11:30 之间
    const progress = currentTotalMinutes - 570
    maxTime.value = progress
  } else if (currentTotalMinutes > 690 && currentTotalMinutes < 780) {
    // 11:30 - 13:00 中午休盘
    maxTime.value = 120
  } else if (currentTotalMinutes >= 780 && currentTotalMinutes <= 900) {
    // 13:00 - 15:00 之间
    const progress = 120 + (currentTotalMinutes - 780)
    maxTime.value = progress
  } else {
    // 15:00 之后，展示满进度
    maxTime.value = 240
  }
  
  // 如果当前滑块时间超出了新的最大时间，强制拉回
  if (currentTime.value > maxTime.value) {
    currentTime.value = maxTime.value
  }
}

function formatTime(minutes: number) {
  let h = 9
  let m = 30 + minutes
  // 早盘: 9:30(0) - 11:30(120)
  // 午盘: 13:00(120) - 15:00(240)
  if (minutes >= 120) {
    // 当进度 >= 120时，时间应该从 13:00 开始算
    // 也就是说在 120 这个节点上，显示的时间瞬间从 11:30 跳到 13:00
    // 13:00 对应的原始分钟数是 13 * 60 = 780
    // 120进度点应该对应 780 分钟。
    // 因此 offset 是 780 - 120 = 660
    let totalMinutes = 660 + minutes
    h = Math.floor(totalMinutes / 60)
    m = totalMinutes % 60
  } else {
    // 9:30 对应的原始分钟数是 9 * 60 + 30 = 570
    let totalMinutes = 570 + minutes
    h = Math.floor(totalMinutes / 60)
    m = totalMinutes % 60
  }
  return `${h.toString().padStart(2, '0')}:${m.toString().padStart(2, '0')}`
}

function togglePlay() {
  if (isPlaying.value) {
    pause()
  } else {
    if (currentTime.value >= maxTime.value) {
      currentTime.value = 0
    }
    play()
  }
}

function play() {
  isPlaying.value = true
  playTimer = window.setInterval(() => {
    if (currentTime.value >= maxTime.value) {
      currentTime.value = maxTime.value
      pause()
    } else {
      currentTime.value += 1 // 每次前进1分钟
    }
  }, 50) // 每50ms前进1分钟，完整回放约12秒
}

function pause() {
  isPlaying.value = false
  if (playTimer) {
    clearInterval(playTimer)
    playTimer = null
  }
}

function handleSliderChange() {
  if (isPlaying.value) pause()
  // 如果手动拖动超出了当前允许的最大进度，强制拉回
  if (currentTime.value > maxTime.value) {
    currentTime.value = maxTime.value
  }
}

onUnmounted(() => {
  pause()
})

// 计算展示的模拟数据
const displaySectors = computed(() => {
  let result = sectors.value

  // 如果进度在 0（最初时刻），则直接返回原始数据（即昨天最后时刻的数据）
  if (currentTime.value === 0) {
    return [...result].sort((a, b) => (b.change_rate || 0) - (a.change_rate || 0))
  }

  if (currentTime.value < 240) {
    result = sectors.value.map((sector, index) => {
      const finalFlow = sector.net_flow || 0
      const finalChange = sector.change_rate || 0
      
      // 进度 0 -> 1，基于收盘时间(240)计算
      const progress = currentTime.value / 240
      
      // 使用正弦波和 index 制造确定性的伪随机波动，越接近尾声波动越小
      const noiseAmplitude = 0.3 * (1 - progress)
      const noise = Math.sin(currentTime.value / 10 + index) * noiseAmplitude
      
      // 对于早盘刚开始的情况，赋予一个小基数避免全是 0
      const baseProgress = Math.max(progress, 0.05)
      
      const currentFlow = finalFlow * baseProgress + finalFlow * noise
      const currentChange = finalChange * baseProgress + finalChange * noise
      
      return {
        ...sector,
        net_flow: currentFlow,
        change_rate: currentChange
      }
    })
  }

  // 按照涨幅高的排下顺序
  return [...result].sort((a, b) => (b.change_rate || 0) - (a.change_rate || 0))
})

async function loadData() {
  loading.value = true
  try {
    const res = await sectorApi.getSectors()
    sectors.value = res.data?.data || res.data || []
  } catch {
    sectors.value = []
  } finally {
    loading.value = false
  }
}

async function loadSectorStocks(name: string) {
  selectedSector.value = name
  drawerVisible.value = true
  stocksLoading.value = true
  try {
    const res = await sectorApi.getSectorStocks(name)
    sectorStocks.value = res.data?.data || res.data || []
  } catch {
    sectorStocks.value = []
  } finally {
    stocksLoading.value = false
  }
}

function handleSectorClick(params: any) {
  if (params.data?.name) {
    loadSectorStocks(params.data.name)
  }
}

onMounted(() => {
  updateMaxTimeByRealTime()
  // 初始化时，让当前时间等于最大允许时间
  currentTime.value = maxTime.value
  
  // 定时每分钟更新一下真实时间的最大进度，并处理越界
  const realTimer = window.setInterval(() => {
    updateMaxTimeByRealTime()
  }, 60 * 1000)
  
  loadData()
  
  onUnmounted(() => {
    pause()
    clearInterval(realTimer)
  })
})
</script>

<style scoped>
.sector-flow {
  display: flex;
  flex-direction: column;
  gap: 12px;
  height: 100%;
  overflow: hidden;
}

.playback-toolbar {
  display: flex;
  align-items: center;
  gap: 24px;
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: 12px;
  padding: 12px 20px;
  box-shadow: 0 2px 8px var(--bg-hover-subtle);
  flex-shrink: 0;
}

.playback-controls {
  display: flex;
  align-items: center;
  gap: 16px;
  min-width: 130px;
}

.time-display {
  font-family: var(--font-mono);
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
  user-select: none;
}

.time-slider {
  flex: 1;
  margin: 0 16px;
}

.view-switch {
  display: flex;
  align-items: center;
  padding-left: 16px;
  border-left: 1px solid var(--border-color);
}

.time-slider :deep(.el-slider__runway) {
  background-color: var(--border-color-light);
}
</style>
