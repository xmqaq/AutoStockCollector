<template>
  <div class="market-view">
    <MarketIndices 
      :indices="indices"
      :loading="indicesLoading"
      :update-time="updateTime"
      @refresh="loadIndices"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { marketApi, type MarketIndex } from '@/api/market'
import { ElMessage } from 'element-plus'

// 导入子组件
import MarketIndices from './components/MarketIndices.vue'

const indices = ref<MarketIndex[]>([])
const indicesLoading = ref(false)
const updateTime = ref('--')

let refreshTimer: ReturnType<typeof setInterval>

async function loadIndices() {
  indicesLoading.value = true
  try {
    const res = await marketApi.getIndices()
    indices.value = res.data?.data || []
    updateTime.value = new Date().toLocaleTimeString()
  } catch {
    ElMessage.error('获取大盘数据失败')
  } finally {
    indicesLoading.value = false
  }
}

onMounted(() => {
  loadIndices()
  refreshTimer = setInterval(() => {
    loadIndices()
  }, 60000)
})

onUnmounted(() => clearInterval(refreshTimer))
</script>

<style scoped>
.market-view {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
</style>