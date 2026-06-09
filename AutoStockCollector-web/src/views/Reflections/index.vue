<template>
  <div class="reflections-page">
    <div class="page-tabs">
      <el-radio-group v-model="tab" size="small">
        <el-radio-button value="reflection">决策反思</el-radio-button>
        <el-radio-button value="quick">快速分析</el-radio-button>
      </el-radio-group>
    </div>
    <ReflectionPanel v-if="tab === 'reflection'" />
    <el-card v-else shadow="never" class="section-card">
      <template #header>
        <div class="panel-header">
          <span>快速分析 (非流式)</span>
          <div class="panel-actions">
            <el-input v-model="quickCode" placeholder="股票代码" size="small" style="width:130px" clearable />
            <el-button size="small" type="primary" @click="runQuick" :loading="store.quickLoading">运行</el-button>
          </div>
        </div>
      </template>
      <div v-if="store.quickLoading" style="text-align:center;padding:40px">
        <el-icon class="is-loading" :size="24"><Loading /></el-icon>
      </div>
      <div v-else-if="store.quickError" class="error-box">{{ store.quickError }}</div>
      <div v-else-if="store.quickResult" class="quick-result">
        <pre>{{ JSON.stringify(store.quickResult, null, 2) }}</pre>
      </div>
      <div v-else style="text-align:center;padding:40px;color:#909399">输入股票代码点击运行</div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import ReflectionPanel from '@/components/ReflectionPanel/index.vue'
import { useAdvancedStore } from '@/stores/advancedStore'
import { Loading } from '@element-plus/icons-vue'

const store = useAdvancedStore()
const tab = ref('reflection')
const quickCode = ref('000001')

async function runQuick() {
  if (!quickCode.value) return
  await store.quickAnalyze(quickCode.value)
}
</script>

<style scoped>
.reflections-page { padding: 16px; display: flex; flex-direction: column; gap: 16px; }
.page-tabs { margin-bottom: 4px; }
.section-card { background: #1f1f1f; border: 1px solid #2c2c2c; }
.section-card :deep(.el-card__header) {
  border-bottom: 1px solid #2c2c2c; padding: 12px 16px;
  color: #e5eaf3; font-size: 14px; font-weight: 600;
}
.panel-header { display: flex; justify-content: space-between; align-items: center; }
.panel-actions { display: flex; gap: 8px; align-items: center; }
.quick-result pre {
  font-size: 12px; color: #c0c4cc; line-height: 1.5;
  background: #1a1a1a; border-radius: 4px; padding: 16px;
  max-height: 600px; overflow-y: auto;
  font-family: 'SF Mono', Menlo, monospace;
}
.error-box { color: #f56c6c; font-size: 13px; padding: 16px; text-align: center; }
</style>
