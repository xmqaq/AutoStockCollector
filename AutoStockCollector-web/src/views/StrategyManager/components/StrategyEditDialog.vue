<template>
  <el-drawer
    v-model="visible"
    :title="isEditing ? '配置策略向导' : '新建策略向导'"
    size="800px"
    direction="rtl"
    :close-on-click-modal="false"
    destroy-on-close
    class="strategy-wizard-drawer"
  >
    <div class="wizard-container">
      <!-- 顶部步骤条 -->
      <div class="wizard-steps">
        <el-steps :active="activeStep" finish-status="success" simple>
          <el-step title="基础定义" icon="Document" />
          <el-step title="维度权重" icon="PieChart" />
          <el-step title="因子微调" icon="Setting" />
        </el-steps>
      </div>

      <!-- 步骤内容区 -->
      <div class="wizard-content">
        <el-form :model="form" label-width="80px" size="default" @submit.prevent>
          
          <!-- Step 1: 基础定义 -->
          <div v-show="activeStep === 0" class="step-pane animation-fade-in">
            <div class="pane-header">
              <h3>策略基础信息</h3>
              <p>定义策略的名称与核心描述</p>
            </div>
            <div class="pane-body">
              <el-form-item label="策略名称" required>
                <el-input v-model="form.name" placeholder="例如：价值精选、动量突破" maxlength="20" show-word-limit size="large" />
              </el-form-item>
              <el-form-item label="策略描述">
                <el-input 
                  v-model="form.description" 
                  type="textarea" 
                  :rows="4" 
                  placeholder="简要描述该策略的选股思路、适用行情等" 
                  maxlength="100" 
                  show-word-limit 
                />
              </el-form-item>
              <el-form-item label="当前状态">
                <el-switch v-model="form.enabled" active-text="启用中" inactive-text="已停用" inline-prompt />
              </el-form-item>
            </div>
          </div>

          <!-- Step 2: 维度权重 -->
          <div v-show="activeStep === 1" class="step-pane animation-fade-in">
            <div class="pane-header">
              <h3>宏观维度配比</h3>
              <p>调整各分析维度的占比，决定最终评分的倾斜方向</p>
            </div>
            <div class="pane-body">
              <div class="weight-total-card" :class="weightTotal === 100 ? 'is-valid' : 'is-invalid'">
                <div class="total-label">当前总权重</div>
                <div class="total-value">{{ weightTotal }}%</div>
                <div class="total-hint" v-if="weightTotal !== 100">请调整使总和达到 100%</div>
                <div class="total-hint" v-else>权重配置完美</div>
              </div>

              <div class="weight-sliders">
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

          <!-- Step 3: 因子微调 -->
          <div v-show="activeStep === 2" class="step-pane animation-fade-in">
            <div class="pane-header">
              <h3>具体因子与参数微调</h3>
              <p>开启需要的分析指标，并精细化配置其内部参数 <span class="enabled-count">({{ enabledIndicatorCount }}/{{ form.indicators.length }} 已启用)</span></p>
            </div>
            <div class="pane-body p-0">
              <el-collapse v-model="activeCollapseNames" class="indicator-collapse">
                <el-collapse-item 
                  v-for="group in groupedIndicators" 
                  :key="group.dimension" 
                  :name="group.dimension"
                >
                  <template #title>
                    <div class="collapse-title">
                      <div class="dim-badge" :style="{ backgroundColor: dimColor(group.dimension) }"></div>
                      <span class="title-text">{{ dimLabel(group.dimension) }}</span>
                      <el-tag size="small" round type="info" class="count-tag">
                        {{ group.items.filter(i => i.enabled).length }} / {{ group.items.length }}
                      </el-tag>
                    </div>
                  </template>
                  
                  <div class="indicator-list">
                    <div v-for="ind in group.items" :key="ind.key" :class="['indicator-card', { 'is-active': ind.enabled }]">
                      <div class="ind-header">
                        <el-switch v-model="ind.enabled" size="small" />
                        <div class="ind-info">
                          <span class="ind-name">{{ ind.label }}</span>
                          <span class="ind-desc" v-if="ind.description" :title="ind.description">{{ ind.description }}</span>
                        </div>
                      </div>
                      
                      <div class="ind-body" v-if="ind.enabled">
                        <div class="ind-param-row">
                          <span class="param-label">因子内部权重</span>
                          <el-slider
                            v-model="ind.weight"
                            :min="1"
                            :max="100"
                            :step="1"
                            style="flex: 1; margin: 0 16px;"
                          />
                          <span class="param-val">{{ ind.weight }}</span>
                        </div>
                        
                        <div class="ind-params-grid" v-if="ind.param_schema && ind.param_schema.length">
                          <div v-for="ps in ind.param_schema" :key="ps.key" class="param-input-item">
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
          
        </el-form>
      </div>

      <!-- 底部操作按钮 -->
      <div class="wizard-footer">
        <el-button @click="visible = false">取消</el-button>
        <div class="right-actions">
          <el-button v-if="activeStep > 0" @click="activeStep--">上一步</el-button>
          <el-button v-if="activeStep < 2" type="primary" @click="nextStep">下一步</el-button>
          <el-button v-if="activeStep === 2" type="success" :loading="saving" @click="saveStrategy">完成并保存</el-button>
        </div>
      </div>
    </div>
  </el-drawer>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { Document, PieChart, Setting } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import type { IndicatorItem } from '@/types'
import { dimColor, dimLabel } from '../utils'

const props = defineProps<{
  modelValue: boolean
  isEditing: boolean
  saving: boolean
  form: {
    name: string
    description: string
    enabled: boolean
    weights: Record<string, number>
    indicators: IndicatorItem[]
  }
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', val: boolean): void
  (e: 'save'): void
}>()

const visible = computed({
  get: () => props.modelValue,
  set: (val) => emit('update:modelValue', val)
})

const activeStep = ref(0)
const activeCollapseNames = ref<string[]>([])

// 每次打开抽屉时重置步骤，并展开第一个有启用指标的面板
watch(visible, (newVal) => {
  if (newVal) {
    activeStep.value = 0
    // 默认展开所有维度面板
    activeCollapseNames.value = groupedIndicators.value.map(g => g.dimension)
  }
})

const weightTotal = computed(() => {
  return Math.round(Object.values(props.form.weights).reduce((s, v) => s + v, 0) * 100)
})

const enabledIndicatorCount = computed(() => props.form.indicators.filter(i => i.enabled).length)

const groupedIndicators = computed(() => {
  const groups: { dimension: string; items: IndicatorItem[] }[] = []
  const map = new Map<string, IndicatorItem[]>()
  for (const ind of props.form.indicators) {
    const d = ind.dimension
    if (!map.has(d)) map.set(d, [])
    map.get(d)!.push(ind)
  }
  for (const [dimension, items] of map) {
    groups.push({ dimension, items })
  }
  return groups
})

function nextStep() {
  if (activeStep.value === 0 && !props.form.name.trim()) {
    ElMessage.warning('请先填写策略名称')
    return
  }
  if (activeStep.value === 1 && weightTotal.value !== 100) {
    ElMessage.warning('建议权重总和调整为 100% 后再继续')
    // 允许继续，只给警告
  }
  activeStep.value++
}

function saveStrategy() {
  if (!props.form.name.trim()) {
    ElMessage.warning('策略名称不能为空')
    activeStep.value = 0
    return
  }
  emit('save')
}
</script>

<style scoped>
.strategy-wizard-drawer :deep(.el-drawer__body) {
  padding: 0;
  overflow: hidden;
}

.wizard-container {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--bg-body);
}

.wizard-steps {
  padding: 20px 40px;
  background: var(--bg-card);
  border-bottom: 1px solid var(--border-color);
}

.wizard-steps :deep(.el-steps--simple) {
  background: transparent;
  padding: 0;
}

.wizard-content {
  flex: 1;
  overflow-y: auto;
  padding: 30px 40px;
}

.step-pane {
  max-width: 600px;
  margin: 0 auto;
}

.pane-header {
  margin-bottom: 30px;
  text-align: center;
}

.pane-header h3 {
  margin: 0 0 8px 0;
  font-size: 24px;
  color: var(--text-primary);
}

.pane-header p {
  margin: 0;
  font-size: 14px;
  color: var(--text-muted);
}

.pane-header .enabled-count {
  color: var(--el-color-primary);
  font-weight: 500;
}

.pane-body {
  background: var(--bg-card);
  padding: 30px;
  border-radius: 12px;
  border: 1px solid var(--border-color);
  box-shadow: 0 4px 12px var(--bg-hover-subtle);
}

.pane-body.p-0 {
  padding: 0;
  background: transparent;
  border: none;
  box-shadow: none;
}

/* Step 2: Weight Sliders */
.weight-total-card {
  text-align: center;
  padding: 20px;
  border-radius: 8px;
  margin-bottom: 30px;
  background: var(--bg-elevated);
  border: 1px solid var(--border-color);
  transition: all 0.3s;
}

.weight-total-card.is-valid {
  border-color: var(--el-color-success-light-5);
  background: var(--el-color-success-light-9);
}

.weight-total-card.is-invalid {
  border-color: var(--el-color-warning-light-5);
  background: var(--el-color-warning-light-9);
}

.total-label {
  font-size: 13px;
  color: var(--text-secondary);
  margin-bottom: 4px;
}

.total-value {
  font-size: 32px;
  font-weight: 700;
  font-family: 'SF Mono', monospace;
}

.is-valid .total-value { color: var(--el-color-success); }
.is-invalid .total-value { color: var(--el-color-warning); }

.total-hint {
  font-size: 12px;
  margin-top: 4px;
}
.is-valid .total-hint { color: var(--el-color-success); }
.is-invalid .total-hint { color: var(--el-color-warning); }

.weight-row {
  display: flex;
  align-items: center;
  margin-bottom: 20px;
  padding: 0 10px;
}

.dim-badge {
  width: 12px;
  height: 12px;
  border-radius: 4px;
  margin-right: 12px;
}

.dim-name {
  width: 80px;
  font-size: 14px;
  font-weight: 500;
  color: var(--text-primary);
}

.dim-slider {
  flex: 1;
  margin: 0 20px;
}

.dim-val {
  width: 40px;
  text-align: right;
  font-family: 'SF Mono', monospace;
  font-size: 14px;
  font-weight: 600;
  color: var(--text-secondary);
}

/* Step 3: Indicators */
.indicator-collapse {
  border: none;
  --el-collapse-header-bg-color: var(--bg-card);
  --el-collapse-content-bg-color: var(--bg-soft);
}

.indicator-collapse :deep(.el-collapse-item__header) {
  border-radius: 8px;
  margin-bottom: 8px;
  border: 1px solid var(--border-color);
  padding: 0 20px;
  height: 56px;
  line-height: 56px;
  font-size: 15px;
  font-weight: 600;
}

.indicator-collapse :deep(.el-collapse-item__wrap) {
  border: none;
  background: transparent;
}

.indicator-collapse :deep(.el-collapse-item__content) {
  padding: 0 0 16px 0;
}

.collapse-title {
  display: flex;
  align-items: center;
  width: 100%;
}

.collapse-title .dim-badge {
  width: 14px;
  height: 14px;
  border-radius: 4px;
  margin-right: 12px;
}

.collapse-title .title-text {
  flex: 1;
}

.collapse-title .count-tag {
  margin-right: 12px;
}

.indicator-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 0 4px;
}

.indicator-card {
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: 8px;
  padding: 16px;
  transition: all 0.2s;
}

.indicator-card.is-active {
  border-color: var(--el-color-primary-light-5);
  box-shadow: 0 2px 8px var(--bg-hover-subtle);
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
  gap: 4px;
}

.ind-name {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
}

.ind-desc {
  font-size: 12px;
  color: var(--text-muted);
  line-height: 1.4;
}

.is-active .ind-name { color: var(--el-color-primary); }

.ind-body {
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px dashed var(--border-color);
}

.ind-param-row {
  display: flex;
  align-items: center;
  background: var(--bg-soft);
  padding: 8px 16px;
  border-radius: 6px;
  margin-bottom: 12px;
}

.param-label {
  font-size: 12px;
  color: var(--text-secondary);
}

.param-val {
  font-family: 'SF Mono', monospace;
  font-size: 13px;
  font-weight: 600;
  width: 30px;
  text-align: right;
}

.ind-params-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: 12px;
}

.param-input-item {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.p-label {
  font-size: 11px;
  color: var(--text-muted);
}

.param-input-item :deep(.el-input-number) {
  width: 100%;
}

/* 底部按钮区 */
.wizard-footer {
  padding: 16px 40px;
  background: var(--bg-card);
  border-top: 1px solid var(--border-color);
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.right-actions {
  display: flex;
  gap: 12px;
}

/* 动画 */
.animation-fade-in {
  animation: fadeIn 0.4s ease-out forwards;
}

@keyframes fadeIn {
  from { opacity: 0; transform: translateY(10px); }
  to { opacity: 1; transform: translateY(0); }
}
</style>