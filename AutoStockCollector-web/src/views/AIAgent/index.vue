<template>
  <div class="ai-agent-page">
    <div class="page-header">
      <h2>AI Agent 工作台</h2>
      <p class="subtitle">管理并配置您的智能投资助理，定制您的投资哲学与专属技能</p>
    </div>

    <div class="agent-tabs-container">
      <el-tabs v-model="activeTab" class="custom-segmented-tabs">
        <el-tab-pane name="general">
          <template #label>
            <span class="custom-tab-label">
              <el-icon><User /></el-icon>
              <span>通用 Agent</span>
            </span>
          </template>
          <GeneralAgentTab />
        </el-tab-pane>

        <el-tab-pane name="philosophy">
          <template #label>
            <span class="custom-tab-label">
              <el-icon><DataAnalysis /></el-icon>
              <span>投资哲学</span>
            </span>
          </template>
          <PhilosophyAgentTab />
        </el-tab-pane>
        
        <el-tab-pane name="skills">
          <template #label>
            <span class="custom-tab-label">
              <el-icon><MagicStick /></el-icon>
              <span>技能库</span>
            </span>
          </template>
          <SkillTab />
        </el-tab-pane>
      </el-tabs>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { User, DataAnalysis, MagicStick } from '@element-plus/icons-vue'
import GeneralAgentTab from './components/GeneralAgentTab.vue'
import PhilosophyAgentTab from './components/PhilosophyAgentTab.vue'
import SkillTab from './components/SkillTab.vue'

const activeTab = ref('general')
</script>

<style scoped>
.ai-agent-page {
  display: flex;
  flex-direction: column;
  gap: 20px;
  min-height: 100%;
}

.page-header {
  margin-bottom: 8px;
}

.page-header h2 {
  margin: 0 0 8px 0;
  font-size: 24px;
  color: var(--text-primary);
  font-weight: 600;
}

.subtitle {
  margin: 0;
  color: var(--text-muted);
  font-size: 14px;
}

.agent-tabs-container {
  flex: 1;
  display: flex;
  flex-direction: column;
}

/* 现代化分段控制器样式的 Tabs */
.custom-segmented-tabs :deep(.el-tabs__header) {
  border-bottom: none;
  margin-bottom: 24px;
  display: inline-block;
}

.custom-segmented-tabs :deep(.el-tabs__nav-wrap::after) {
  display: none;
}

.custom-segmented-tabs :deep(.el-tabs__nav) {
  background: var(--bg-elevated);
  border-radius: 8px;
  padding: 4px;
  display: inline-flex;
  border: 1px solid var(--border-color);
}

.custom-segmented-tabs :deep(.el-tabs__active-bar) {
  display: none;
}

.custom-segmented-tabs :deep(.el-tabs__item) {
  height: 36px;
  line-height: 36px;
  padding: 0 20px !important;
  border-radius: 6px;
  color: var(--text-secondary);
  font-size: 14px;
  font-weight: 500;
  transition: all 0.3s cubic-bezier(0.645, 0.045, 0.355, 1);
  margin: 0;
}

.custom-segmented-tabs :deep(.el-tabs__item:hover) {
  color: var(--text-primary);
}

.custom-segmented-tabs :deep(.el-tabs__item.is-active) {
  background: var(--bg-card);
  color: var(--el-color-primary);
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
}

.custom-tab-label {
  display: flex;
  align-items: center;
  gap: 6px;
}

.custom-tab-label .el-icon {
  font-size: 16px;
}
</style>
