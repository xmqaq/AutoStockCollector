<template>
  <div class="sm-workspace" v-if="strategy">
    <!-- 工作区工具栏 -->
    <div class="workspace-toolbar">
      <div class="strategy-info">
        <span class="type-badge">{{ strategy.type === 'selection' ? '选股' : '交易' }}</span>
        <h2 class="strategy-name">{{ strategy.name }}</h2>
        <el-tag size="small" :type="strategy.enabled ? 'success' : 'info'" effect="plain">
          {{ strategy.enabled ? '启用中' : '已停用' }}
        </el-tag>
      </div>
      <div class="workspace-actions">
        <el-button @click="$emit('duplicate', strategy)">
          <el-icon><CopyDocument /></el-icon> 复制
        </el-button>
        <el-button type="danger" plain @click="$emit('delete', strategy)">
          <el-icon><Delete /></el-icon> 删除
        </el-button>
        <el-divider direction="vertical" />
        <el-button type="primary" :loading="saving" @click="saveChanges">
          <el-icon><Select /></el-icon> 保存配置
        </el-button>
        <el-button type="success" :loading="testingId === strategy._id" @click="$emit('test', strategy)">
          <el-icon><VideoPlay /></el-icon> 运行回测
        </el-button>
      </div>
    </div>

    <!-- 核心配置区 (上下分屏的上半部分) -->
    <div class="workspace-editor">
      <el-form :model="form" label-width="80px" size="default" label-position="top">
        <div class="editor-layout">
          
          <!-- 左侧：基础与权重 -->
          <div class="editor-left">
            <div class="panel-card">
              <div class="panel-header">基础信息</div>
              <div class="panel-body">
                <el-form-item label="策略名称" required>
                  <el-input v-model="form.name" placeholder="策略名称" />
                </el-form-item>
                <el-form-item label="策略描述">
                  <el-input v-model="form.description" type="textarea" :rows="3" placeholder="简要描述" />
                </el-form-item>
              </div>
            </div>

            <div class="panel-card mt-16">
              <div class="panel-header">
                宏观维度配比
                <span class="weight-total" :class="weightTotal === 100 ? 'text-success' : 'text-danger'">
                  合计: {{ weightTotal }}%
                </span>
              </div>
              <div class="panel-body">
                <div v-for="(val, dim) in form.weights" :key="dim" class="weight-row">
                  <div class="dim-badge" :style="{ backgroundColor: dimColor(String(dim)) }"></div>
                  <span class="dim-name">{{ dimLabel(String(dim)) }}</span>
                  <el-slider
                    v-model="form.weights[dim]"
                    :min="0"
                    :max="1"
                    :step="0.05"
                    :format-tooltip="(v: number) => `${Math.round(v * 100)}%`"
                    class="dim-slider"
                  />
                  <span class="dim-val">{{ Math.round(val * 100) }}%</span>
                </div>
              </div>
            </div>
          </div>

          <!-- 右侧：因子配置 -->
          <div class="editor-right">
            <div class="panel-card h-full flex-col">
              <div class="panel-header">
                因子与参数微调
                <span class="text-muted font-normal ml-2">({{ enabledIndicatorCount }}/{{ form.indicators.length }} 已启用)</span>
              </div>
              <div class="panel-body flex-1 overflow-y-auto p-0">
                <el-collapse v-model="activeCollapse" class="ide-collapse">
                  <el-collapse-item 
                    v-for="group in groupedIndicators" 
                    :key="group.dimension" 
                    :name="group.dimension"
                  >
                    <template #title>
                      <div class="collapse-title">
                        <div class="dim-badge" :style="{ backgroundColor: dimColor(group.dimension) }"></div>
                        <span>{{ dimLabel(group.dimension) }}</span>
                      </div>
                    </template>
                    
                    <div class="indicator-list">
                      <div v-for="ind in group.items" :key="ind.key" class="ind-item">
                        <div class="ind-header">
                          <el-switch v-model="ind.enabled" size="small" />
                          <div class="ind-info" :class="{ 'is-disabled': !ind.enabled }">
                            <span class="ind-name">{{ ind.label }}</span>
                            <span class="ind-desc" v-if="ind.description" :title="ind.description">{{ ind.description }}</span>
                          </div>
                        </div>
                        
                        <div class="ind-params" v-if="ind.enabled">
                          <div class="param-row">
                            <span class="p-label">因子权重</span>
                            <el-slider v-model="ind.weight" :min="1" :max="100" :step="1" size="small" style="width: 120px" />
                            <span class="p-val">{{ ind.weight }}</span>
                          </div>
                          
                          <div class="param-grid" v-if="ind.param_schema && ind.param_schema.length">
                            <div v-for="ps in ind.param_schema" :key="ps.key" class="param-input">
                              <span class="p-label">{{ ps.label }}</span>
                              <el-input-number
                                v-model="ind.params![ps.key]"
                                size="small"
                                :min="ps.min"
                                :max="ps.max"
                                :step="ps.step"
                                controls-position="right"
                              />
                            </div>
                          </div>
                        </div>
                      </div>
                    </div>
                  </el-collapse-item>
                </el-collapse>
              </div>
            </div>
          </div>

        </div>
      </el-form>
    </div>
  </div>
  
  <div v-else class="workspace-empty">
    <el-empty description="请在左侧选择一个策略，或新建策略" />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { CopyDocument, Delete, Select, VideoPlay } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import type { StrategyRule, IndicatorItem } from '@/types'
import { dimColor, dimLabel } from '../utils'

const props = defineProps<{
  strategy: StrategyRule | null
  catalog: any[]
  saving: boolean
  testingId: string
}>()

const emit = defineEmits<{
  (e: 'save', payload: any): void
  (e: 'delete', item: StrategyRule): void
  (e: 'duplicate', item: StrategyRule): void
  (e: 'test', item: StrategyRule): void
}>()

const form = ref<{
  name: string; description: string; enabled: boolean
  weights: Record<string, number>
  indicators: IndicatorItem[]
}>({
  name: '', description: '', enabled: true,
  weights: {}, indicators: []
})

const activeCollapse = ref<string[]>([])

// 当选中的策略改变时，重新初始化表单
watch(() => props.strategy, (newVal) => {
  if (newVal) {
    const indicators = JSON.parse(JSON.stringify(newVal.indicators || []))
    // 合并 param_schema
    const catalogMap = new Map(props.catalog.map(c => [c.key, c]))
    for (const ind of indicators) {
      const cat = catalogMap.get(ind.key)
      if (cat && !ind.param_schema) {
        ind.param_schema = cat.param_schema || []
      }
      if (!ind.params && cat?.params) {
        ind.params = { ...cat.params }
      }
    }
    
    form.value = {
      name: newVal.name,
      description: newVal.description,
      enabled: newVal.enabled,
      weights: { ...newVal.weights },
      indicators
    }
    
    activeCollapse.value = groupedIndicators.value.map(g => g.dimension)
  }
}, { immediate: true })

const weightTotal = computed(() => {
  return Math.round(Object.values(form.value.weights).reduce((s, v) => s + v, 0) * 100)
})

const enabledIndicatorCount = computed(() => form.value.indicators.filter(i => i.enabled).length)

const groupedIndicators = computed(() => {
  const groups: { dimension: string; items: IndicatorItem[] }[] = []
  const map = new Map<string, IndicatorItem[]>()
  for (const ind of form.value.indicators) {
    const d = ind.dimension
    if (!map.has(d)) map.set(d, [])
    map.get(d)!.push(ind)
  }
  for (const [dimension, items] of map) {
    groups.push({ dimension, items })
  }
  return groups
})

function saveChanges() {
  if (!form.value.name.trim()) {
    ElMessage.warning('策略名称不能为空')
    return
  }
  emit('save', {
    ...form.value,
    type: props.strategy?.type || 'selection'
  })
}
</script>

<style scoped>
.sm-workspace {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
  background: var(--bg-body);
}

.workspace-empty {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--bg-body);
}

/* 工具栏 */
.workspace-toolbar {
  height: 64px;
  padding: 0 24px;
  background: var(--bg-card);
  border-bottom: 1px solid var(--border-color-light);
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-shrink: 0;
  box-shadow: 0 1px 2px rgba(0,0,0,0.02);
  z-index: 10;
}

.strategy-info {
  display: flex;
  align-items: center;
  gap: 12px;
}

.type-badge {
  font-size: 12px;
  background: var(--bg-elevated);
  padding: 4px 10px;
  border-radius: 6px;
  color: var(--text-secondary);
  border: 1px solid var(--border-color-light);
  font-weight: 500;
}

.strategy-name {
  margin: 0;
  font-size: 20px;
  font-weight: 600;
  color: var(--text-primary);
  letter-spacing: 0.5px;
}

.workspace-actions {
  display: flex;
  align-items: center;
  gap: 10px;
}

/* 编辑区 */
.workspace-editor {
  flex: 1;
  overflow: hidden;
  padding: 24px;
  display: flex;
  flex-direction: column;
  background: var(--bg-page);
}

.editor-layout {
  display: flex;
  gap: 24px;
  height: 100%;
  overflow: hidden; /* 防止子元素撑开导致外部滚动 */
}

.editor-left {
  width: 360px;
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
  overflow-y: auto; /* 左侧支持内部滚动 */
  padding-right: 8px;
}

.editor-left::-webkit-scrollbar {
  width: 6px;
}
.editor-left::-webkit-scrollbar-thumb {
  background: var(--border-color-light);
  border-radius: 3px;
}

.editor-right {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden; /* 右侧面板限制高度 */
}

/* 面板卡片 */
.panel-card {
  background: var(--bg-card);
  border-radius: 12px;
  border: 1px solid var(--border-color-light);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.02);
  margin-bottom: 24px;
  transition: box-shadow 0.3s ease;
}

.panel-card:hover {
  box-shadow: 0 6px 16px rgba(0, 0, 0, 0.04);
}

.panel-header {
  padding: 16px 20px;
  font-size: 15px;
  font-weight: 600;
  border-bottom: 1px solid var(--border-color-light);
  background: var(--bg-elevated);
  display: flex;
  justify-content: space-between;
  align-items: center;
  color: var(--text-primary);
}

.panel-body {
  padding: 20px;
}

/* 工具类 */
.mt-16 { margin-top: 16px; }
.h-full { height: 100%; }
.flex-col { display: flex; flex-direction: column; }
.flex-1 { flex: 1; }
.overflow-y-auto { overflow-y: auto; }
.p-0 { padding: 0; }
.ml-2 { margin-left: 8px; }
.text-muted { color: var(--text-muted); }
.font-normal { font-weight: normal; }
.text-success { color: var(--el-color-success); }
.text-danger { color: var(--el-color-danger); }

/* 权重编辑 */
.weight-row {
  display: flex;
  align-items: center;
  margin-bottom: 20px;
}

.weight-row:last-child {
  margin-bottom: 0;
}

.dim-badge {
  width: 12px;
  height: 12px;
  border-radius: 4px;
  margin-right: 10px;
  box-shadow: 0 2px 4px rgba(0,0,0,0.1);
}

.dim-name {
  width: 64px;
  font-size: 14px;
  color: var(--text-secondary);
}

.dim-slider {
  flex: 1;
  margin: 0 20px;
}

.dim-val {
  width: 44px;
  text-align: right;
  font-family: var(--font-mono);
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
}

/* IDE 风格折叠面板 */
.ide-collapse {
  border: none;
  --el-collapse-header-bg-color: transparent;
  --el-collapse-content-bg-color: transparent;
}

.ide-collapse :deep(.el-collapse-item__header) {
  border-bottom: 1px solid var(--border-color-light);
  height: 48px;
  line-height: 48px;
  padding: 0 20px;
  background: var(--bg-body);
  transition: background-color 0.3s;
}

.ide-collapse :deep(.el-collapse-item__header:hover) {
  background: var(--bg-hover-subtle);
}

.collapse-title {
  display: flex;
  align-items: center;
  font-weight: 600;
  font-size: 14px;
  color: var(--text-primary);
}

.ide-collapse :deep(.el-collapse-item__wrap) {
  border-bottom: none;
}

.ide-collapse :deep(.el-collapse-item__content) {
  padding-bottom: 0;
}

.indicator-list {
  display: flex;
  flex-direction: column;
}

.ind-item {
  padding: 16px 20px;
  border-bottom: 1px solid var(--border-color-light);
  transition: background-color 0.3s;
}

.ind-item:hover {
  background: var(--bg-hover-subtle);
}

.ind-item:last-child {
  border-bottom: none;
}

.ind-header {
  display: flex;
  align-items: flex-start;
  gap: 16px;
}

.ind-info {
  flex: 1;
  display: flex;
  flex-direction: column;
  transition: opacity 0.3s;
}

.ind-info.is-disabled {
  opacity: 0.4;
}

.ind-name {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
}

.ind-desc {
  font-size: 13px;
  color: var(--text-muted);
  margin-top: 4px;
  line-height: 1.4;
}

.ind-params {
  margin-top: 16px;
  margin-left: 48px;
  padding: 16px;
  background: var(--bg-elevated);
  border-radius: 8px;
  border: 1px solid var(--border-color-light);
}

.param-row {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 16px;
}

.p-label {
  font-size: 13px;
  color: var(--text-secondary);
  font-weight: 500;
}

.p-val {
  font-family: var(--font-mono);
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
}

.param-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
  gap: 16px;
}

.param-input {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.param-input :deep(.el-input-number) {
  width: 100%;
}

/* 右侧滚动条美化 */
.overflow-y-auto::-webkit-scrollbar {
  width: 6px;
}
.overflow-y-auto::-webkit-scrollbar-thumb {
  background: var(--border-color-light);
  border-radius: 3px;
}
</style>