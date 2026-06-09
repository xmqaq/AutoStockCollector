<template>
  <div class="reflection-panel">
    <el-card shadow="never" class="section-card">
      <template #header>
        <div class="panel-header">
          <span>决策反思记录</span>
          <div class="panel-actions">
            <el-input v-model="code" placeholder="输入股票代码" size="small" style="width:130px" clearable />
            <el-button size="small" type="primary" @click="loadData" :loading="loading">查询</el-button>
          </div>
        </div>
      </template>
      <div v-if="loading" style="text-align:center;padding:40px">
        <el-icon class="is-loading" :size="24"><Loading /></el-icon>
      </div>
      <div v-else-if="reflections.length === 0" style="text-align:center;padding:40px;color:#909399">
        暂无反思记录
      </div>
      <div v-else class="reflection-list">
        <div v-for="r in reflections" :key="r.timestamp" class="reflection-item">
          <div class="reflection-header">
            <el-tag size="small" :type="r.accuracy === 'correct' ? 'success' : r.accuracy === 'wrong' ? 'danger' : 'info'">
              {{ r.accuracy === 'correct' ? '正确' : r.accuracy === 'wrong' ? '错误' : '待评估' }}
            </el-tag>
            <span class="reflection-decision">{{ r.decision }}</span>
            <span class="reflection-time">{{ formatTime(r.timestamp) }}</span>
          </div>
          <div class="reflection-detail">
            <div class="detail-row">
              <label>预测:</label>
              <span>{{ r.prediction }}</span>
            </div>
            <div v-if="r.actual_return !== undefined" class="detail-row">
              <label>实际收益:</label>
              <span :style="{ color: r.actual_return >= 0 ? '#67c23a' : '#f56c6c' }">
                {{ (r.actual_return * 100).toFixed(2) }}%
              </span>
            </div>
            <div v-if="r.lessons" class="detail-row">
              <label>经验:</label>
              <span>{{ r.lessons }}</span>
            </div>
          </div>
        </div>
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { reflectionApi } from '@/api/ai'
import { Loading } from '@element-plus/icons-vue'

const code = ref('000001')
const reflections = ref<any[]>([])
const loading = ref(false)

function formatTime(ts: string) {
  if (!ts) return ''
  return new Date(ts).toLocaleString('zh-CN')
}

async function loadData() {
  if (!code.value) return
  loading.value = true
  try {
    const res = await reflectionApi.getForStock(code.value)
    reflections.value = res.data?.data || res.data || []
  } catch {
    reflections.value = []
  } finally {
    loading.value = false
  }
}

onMounted(() => loadData())
</script>

<style scoped>
.reflection-panel { display: flex; flex-direction: column; gap: 16px; }
.section-card { background: #1f1f1f; border: 1px solid #2c2c2c; }
.section-card :deep(.el-card__header) {
  border-bottom: 1px solid #2c2c2c; padding: 12px 16px;
  color: #e5eaf3; font-size: 14px; font-weight: 600;
}
.panel-header { display: flex; justify-content: space-between; align-items: center; }
.panel-actions { display: flex; gap: 8px; align-items: center; }
.reflection-list { display: flex; flex-direction: column; gap: 8px; }
.reflection-item { background: #2c2c2c; border-radius: 6px; padding: 12px; }
.reflection-header { display: flex; align-items: center; gap: 8px; margin-bottom: 8px; }
.reflection-decision { font-size: 13px; font-weight: 600; color: #e5eaf3; }
.reflection-time { font-size: 11px; color: #606266; margin-left: auto; }
.reflection-detail { display: flex; flex-direction: column; gap: 4px; }
.detail-row { display: flex; gap: 8px; font-size: 12px; }
.detail-row label { color: #909399; min-width: 60px; }
.detail-row span { color: #c0c4cc; }
</style>
