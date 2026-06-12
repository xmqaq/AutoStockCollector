<template>
  <div class="monitor-view">
    <el-tabs v-model="activeTab">
      <el-tab-pane label="盯盘配置" name="config">
        <MonitorConfig />
      </el-tab-pane>
      <el-tab-pane label="告警通知" name="alert">
        <AlertNotification ref="alertRef" />
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import MonitorConfig from '@/components/MonitorConfig/index.vue'
import AlertNotification from '@/components/AlertNotification/index.vue'

const activeTab = ref('config')
const alertRef = ref<InstanceType<typeof AlertNotification> | null>(null)
</script>

<style scoped>
.monitor-view {
  padding: 16px;
}

.monitor-view :deep(.el-tabs__item) {
  color: var(--text-muted);
}

.monitor-view :deep(.el-tabs__item.is-active) {
  color: var(--el-color-primary);
}

.monitor-view :deep(.el-tabs__active-bar) {
  background-color: var(--el-color-primary);
}
</style>