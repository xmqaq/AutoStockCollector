<template>
  <div class="split-layout">
    <!-- 左侧：厂商导航栏 -->
    <div class="sidebar">
      <div class="sidebar-header">
        <span class="sidebar-title">厂商列表</span>
        <el-button v-if="isAdmin" type="primary" size="small" plain @click="handleCreateNew">
          <el-icon><Plus /></el-icon>
        </el-button>
      </div>

      <div class="sidebar-list" v-loading="loading">
        <div
          v-for="item in keys"
          :key="item.provider"
          class="nav-item"
          :class="{ active: selectedProvider === item.provider && !isCreating }"
          @click="selectProvider(item)"
        >
          <el-avatar :size="28" :style="{ background: providerColor(item.provider), fontSize: '12px' }">
            {{ item.name.charAt(0).toUpperCase() }}
          </el-avatar>
          <div class="nav-info">
            <span class="nav-name">{{ item.name }}</span>
            <span class="nav-status">
              <span class="status-dot" :class="item.enabled ? 'is-enabled' : 'is-disabled'"></span>
              {{ item.enabled ? '已启用' : '已禁用' }}
            </span>
          </div>
          <el-icon v-if="selectedProvider === item.provider && !isCreating" class="active-icon"><ArrowRight /></el-icon>
        </div>

        <div v-if="isCreating" class="nav-item active is-creating">
          <el-avatar :size="28" style="background: var(--el-color-primary); color: #fff;">
            <el-icon><Plus /></el-icon>
          </el-avatar>
          <div class="nav-info">
            <span class="nav-name">新增厂商配置</span>
          </div>
        </div>
      </div>
    </div>

    <!-- 右侧：详情面板 -->
    <div class="detail-panel">
      <!-- 空状态 -->
      <div v-if="!isCreating && !selectedRow" class="empty-state">
        <el-icon :size="48" color="var(--border-color-light)"><Setting /></el-icon>
        <p>请在左侧选择一个厂商进行配置</p>
      </div>

      <!-- 新增/编辑 表单 -->
      <div v-else class="config-content">
        <div class="panel-header">
          <div class="panel-title-wrapper">
            <el-avatar v-if="!isCreating" :size="40" :style="{ background: providerColor(selectedRow!.provider) }">
              {{ selectedRow!.name.charAt(0).toUpperCase() }}
            </el-avatar>
            <el-avatar v-else :size="40" style="background: var(--el-color-primary);">
              <el-icon><Plus /></el-icon>
            </el-avatar>
            <div class="title-text">
              <h2>{{ isCreating ? '新增 AI 厂商' : selectedRow!.name }}</h2>
              <span class="subtitle">{{ isCreating ? '配置新的模型接口' : selectedRow!.provider }}</span>
            </div>
          </div>
          <div class="panel-actions" v-if="!isCreating && isAdmin">
            <el-switch
              v-model="formData.enabled"
              inline-prompt
              active-text="启用"
              inactive-text="禁用"
              @change="toggleEnable"
            />
            <el-button type="danger" link @click="removeProvider">删除配置</el-button>
          </div>
        </div>

        <el-form :model="formData" :rules="formRules" ref="formRef" label-position="top" class="detail-form" :disabled="!isAdmin">
          
          <!-- 新增模式专属：选择预设 -->
          <template v-if="isCreating">
            <el-form-item label="选择厂商类型" prop="preset">
              <el-select v-model="formData.preset" placeholder="选择主流厂商或自定义…" style="width:100%" @change="onPresetChange">
                <el-option-group label="主流厂商">
                  <el-option v-for="p in PRESETS.filter(x => x.value !== 'custom')" :key="p.value" :label="p.label" :value="p.value">
                    <div class="preset-opt">
                      <span class="preset-dot" :style="{ background: p.color }"></span>
                      <span>{{ p.label }}</span>
                      <code class="preset-url">{{ p.base_url.replace('https://', '') }}</code>
                    </div>
                  </el-option>
                </el-option-group>
                <el-option-group label="其他">
                  <el-option label="自定义接口（OpenAI 兼容）" value="custom">
                    <div class="preset-opt"><span class="preset-dot" style="background:#666"></span><span>自定义接口</span></div>
                  </el-option>
                </el-option-group>
              </el-select>
            </el-form-item>

            <div class="row-flex" v-if="isCustom">
              <el-form-item label="Provider 标识" prop="provider" class="flex-1">
                <el-input v-model="formData.provider" placeholder="如 my-llm" />
              </el-form-item>
              <el-form-item label="显示名称" prop="name" class="flex-1">
                <el-input v-model="formData.name" placeholder="UI显示的名称" />
              </el-form-item>
            </div>
          </template>

          <el-divider v-if="isCreating" border-style="dashed" />

          <!-- API Key -->
          <el-form-item label="API Key">
            <div class="input-with-button">
              <el-input
                v-model="formData.api_key"
                type="password"
                show-password
                :placeholder="(!isCreating && selectedRow?.has_key) ? '已配置 (输入新 Key 将覆盖)' : '请输入 API Key'"
              />
              <el-button v-if="!isCreating" type="primary" :loading="testing" @click="testConnection">
                验证连接
              </el-button>
            </div>
            <div v-if="!isCreating && testState !== 'idle'" class="test-result" :class="testState">
              <el-icon v-if="testState === 'valid'"><Select /></el-icon>
              <el-icon v-if="testState === 'invalid'"><CloseBold /></el-icon>
              <span>{{ testState === 'valid' ? '验证通过' : testMsg }}</span>
            </div>
          </el-form-item>

          <!-- Base URL -->
          <el-form-item label="Base URL" :prop="(isCreating && isCustom) ? 'base_url' : undefined" v-if="isCreating || (formData.base_url !== undefined && !isBuiltinUrl(formData.provider!, formData.base_url))">
            <el-input v-model="formData.base_url" :disabled="isCreating && !isCustom && !!formData.preset" placeholder="https://api.example.com/v1" />
            <div class="form-help">自定义接口的完整请求前缀。主流厂商通常不需要修改。</div>
          </el-form-item>

          <!-- 默认模型 -->
          <el-form-item label="默认模型" v-if="!isCreating">
            <div class="input-with-button">
              <el-select
                v-model="formData.model"
                placeholder="选择或输入模型名称"
                filterable
                allow-create
                clearable
                style="flex: 1;"
              >
                <el-option
                  v-for="m in modelOptions"
                  :key="m"
                  :label="m"
                  :value="m"
                />
              </el-select>
              <el-button @click="fetchModels" :loading="modelLoading">
                拉取模型列表
              </el-button>
            </div>
          </el-form-item>

          <!-- 优先级 -->
          <el-form-item label="调用优先级">
            <el-input-number
              v-model="formData.priority"
              :min="1"
              :max="99"
              controls-position="right"
            />
            <div class="form-help">数字越小优先级越高（1 最高）。当优先级高的厂商调用失败时，会自动降级调用下一个厂商。</div>
          </el-form-item>

          <!-- 提交区 -->
          <div class="form-actions" v-if="isAdmin">
            <el-button type="primary" size="large" :loading="saving" @click="handleSave">
              {{ isCreating ? '创建厂商配置' : '保存修改' }}
            </el-button>
            <el-button v-if="isCreating" size="large" @click="cancelCreate">取消</el-button>
          </div>
        </el-form>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { Plus, ArrowRight, Setting, Select, CloseBold, Warning } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'
import { aiKeyApi, type AIKeyConfig } from '@/api/ai'
import { useAuthStore } from '@/stores/authStore'
import { PRESETS, providerColor, isBuiltinUrl } from './constants'

const authStore = useAuthStore()
const isAdmin = computed(() => authStore.isAdmin)

type KeyRow = AIKeyConfig & { api_key?: string }

// 列表数据
const loading = ref(false)
const keys = ref<KeyRow[]>([])

// 状态控制
const isCreating = ref(false)
const selectedProvider = ref<string | null>(null)
const selectedRow = computed(() => keys.value.find(k => k.provider === selectedProvider.value) || null)

// 表单数据
const formRef = ref<FormInstance>()
const saving = ref(false)
const formData = ref<Partial<KeyRow & { preset?: string }>>({})

// 测试与模型拉取状态
const testing = ref(false)
const testState = ref<'idle' | 'valid' | 'invalid'>('idle')
const testMsg = ref('')
const modelLoading = ref(false)
const modelOptions = ref<string[]>([])

const isCustom = computed(() => formData.value.preset === 'custom')
const formRules = computed<FormRules>(() => ({
  preset: [{ required: true, message: '请选择厂商类型', trigger: 'change' }],
  provider: isCustom.value ? [{ required: true, message: '请输入 Provider 标识', trigger: 'blur' }] : [],
  name: [{ required: true, message: '请输入显示名称', trigger: 'blur' }],
  base_url: isCustom.value ? [{ required: true, message: '请输入 Base URL', trigger: 'blur' }] : [],
}))

// 初始化加载
async function loadKeys() {
  loading.value = true
  try {
    const res = await aiKeyApi.list()
    keys.value = (res.data?.data || [])
      .map((k: AIKeyConfig) => ({ ...k, api_key: '' }))
      .sort((a: AIKeyConfig, b: AIKeyConfig) => (a.priority ?? 99) - (b.priority ?? 99))
    
    // 如果没有选中项且有数据，默认选中第一个
    if (!selectedProvider.value && !isCreating.value && keys.value.length > 0) {
      selectProvider(keys.value[0])
    } else if (selectedProvider.value && !isCreating.value) {
      // 刷新后重新填充表单数据
      const row = keys.value.find(k => k.provider === selectedProvider.value)
      if (row) selectProvider(row)
    }
  } catch {
    keys.value = []
  } finally {
    loading.value = false
  }
}

// 侧边栏交互
function selectProvider(row: KeyRow) {
  isCreating.value = false
  selectedProvider.value = row.provider
  formData.value = { ...row, api_key: '' }
  testState.value = 'idle'
  testMsg.value = ''
  modelOptions.value = row.model ? [row.model] : []
  formRef.value?.clearValidate()
}

function handleCreateNew() {
  isCreating.value = true
  selectedProvider.value = null
  formData.value = { preset: '', provider: '', name: '', api_key: '', base_url: '', enabled: true, priority: 99 }
  formRef.value?.clearValidate()
}

function cancelCreate() {
  isCreating.value = false
  if (keys.value.length > 0) {
    selectProvider(keys.value[0])
  } else {
    formData.value = {}
  }
}

function onPresetChange(val: string) {
  const p = PRESETS.find(x => x.value === val)
  if (!p) return
  formData.value.provider = p.provider
  formData.value.name = p.label
  formData.value.base_url = p.base_url
}

// 功能操作
async function testConnection() {
  if (!formData.value.provider) return
  if (!selectedRow.value?.has_key && !formData.value.api_key) {
    ElMessage.warning('请先输入 API Key')
    return
  }

  testing.value = true
  testState.value = 'idle'
  testMsg.value = ''

  try {
    const res = await aiKeyApi.test(
      formData.value.provider,
      formData.value.api_key || undefined,
      formData.value.base_url
    )
    const { valid, message } = res.data ?? {}
    testState.value = valid ? 'valid' : 'invalid'
    testMsg.value = message || (valid ? '有效' : '无效')
    if (valid) ElMessage.success('连接验证通过')
  } catch {
    testState.value = 'invalid'
    testMsg.value = '请求失败，请检查网络或配置'
  } finally {
    testing.value = false
  }
}

async function fetchModels() {
  if (!formData.value.provider) return
  if (formData.value.api_key) {
    ElMessage.warning('您输入了新的 API Key，请先保存修改后再获取模型')
    return
  }
  if (!selectedRow.value?.has_key) {
    ElMessage.warning('请先配置并保存 API Key')
    return
  }

  modelLoading.value = true
  try {
    const res = await aiKeyApi.fetchModels(formData.value.provider)
    const models: string[] = res.data?.models || []
    if (models.length) {
      modelOptions.value = models
      ElMessage.success(`成功获取 ${models.length} 个模型`)
    } else {
      ElMessage.warning('未获取到模型列表')
    }
  } catch {
    ElMessage.error('获取模型失败')
  } finally {
    modelLoading.value = false
  }
}

async function handleSave() {
  if (!formRef.value) return
  if (!await formRef.value.validate().catch(() => false)) return
  
  const finalProvider = formData.value.provider!
  
  if (isCreating.value && keys.value.some(k => k.provider === finalProvider)) {
    ElMessage.warning(`"${finalProvider}" 已存在`)
    return
  }

  saving.value = true
  try {
    await aiKeyApi.update({
      provider: finalProvider,
      name: formData.value.name!,
      enabled: formData.value.enabled ?? true,
      priority: formData.value.priority ?? 99,
      api_key: formData.value.api_key || undefined,
      base_url: formData.value.base_url,
      model: formData.value.model
    })
    ElMessage.success(isCreating.value ? '厂商添加成功' : '保存成功')
    
    if (isCreating.value) {
      selectedProvider.value = finalProvider
      isCreating.value = false
    }
    
    await loadKeys()
  } catch {
    ElMessage.error('保存失败')
  } finally {
    saving.value = false
  }
}

async function toggleEnable(val: boolean | string | number) {
  if (!selectedRow.value) return
  try {
    await aiKeyApi.update({
      provider: selectedRow.value.provider,
      name: selectedRow.value.name,
      enabled: val as boolean,
      priority: selectedRow.value.priority,
      base_url: selectedRow.value.base_url
    })
    ElMessage.success(val ? '已启用' : '已禁用')
    loadKeys()
  } catch {
    ElMessage.error('操作失败')
    formData.value.enabled = !val
  }
}

async function removeProvider() {
  if (!selectedRow.value) return
  try {
    await ElMessageBox.confirm(`确认删除厂商 "${selectedRow.value.name}" 及其所有配置？`, '删除确认', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消'
    })
    await aiKeyApi.remove(selectedRow.value.provider)
    ElMessage.success('已删除')
    selectedProvider.value = null
    loadKeys()
  } catch (e: any) {
    if (e !== 'cancel') ElMessage.error('删除失败')
  }
}

onMounted(loadKeys)
</script>

<style scoped>
.split-layout {
  display: flex;
  height: calc(100vh - 120px); /* 根据外层容器调整 */
  min-height: 600px;
  background: var(--bg-card);
  border-radius: 12px;
  border: 1px solid var(--border-color-light);
  overflow: hidden;
  box-shadow: 0 4px 24px rgba(0, 0, 0, 0.02);
}

/* 左侧边栏 */
.sidebar {
  width: 260px;
  border-right: 1px solid var(--border-color-light);
  display: flex;
  flex-direction: column;
  background: var(--bg-soft);
}

.sidebar-header {
  padding: 16px 20px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid var(--border-color-light);
}

.sidebar-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-secondary);
}

.sidebar-list {
  flex: 1;
  overflow-y: auto;
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 12px;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s;
  border: 1px solid transparent;
}

.nav-item:hover {
  background: var(--bg-card);
}

.nav-item.active {
  background: var(--bg-card);
  border-color: var(--border-color-light);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);
}

.nav-item.is-creating {
  border-color: var(--el-color-primary-light-5);
  background: var(--el-color-primary-light-9);
}

.nav-info {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.nav-name {
  font-size: 14px;
  font-weight: 500;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.nav-status {
  font-size: 11px;
  color: var(--text-muted);
  display: flex;
  align-items: center;
  gap: 4px;
}

.status-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
}
.status-dot.is-enabled { background-color: #10b981; }
.status-dot.is-disabled { background-color: #94a3b8; }

.active-icon {
  color: var(--text-muted);
  font-size: 12px;
}

/* 右侧面板 */
.detail-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
  background: var(--bg-card);
  overflow-y: auto;
}

.empty-state {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: var(--text-muted);
  gap: 16px;
}

.config-content {
  padding: 40px;
  max-width: 680px;
}

.panel-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  margin-bottom: 40px;
}

.panel-title-wrapper {
  display: flex;
  align-items: center;
  gap: 16px;
}

.title-text {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.title-text h2 {
  margin: 0;
  font-size: 20px;
  font-weight: 600;
  color: var(--text-primary);
}

.subtitle {
  font-size: 13px;
  color: var(--text-muted);
  font-family: var(--font-mono);
}

.panel-actions {
  display: flex;
  align-items: center;
  gap: 16px;
}

/* 表单内部样式 */
.detail-form :deep(.el-form-item__label) {
  font-weight: 500;
  color: var(--text-secondary);
}

.input-with-button {
  display: flex;
  width: 100%;
  gap: 12px;
}

.form-help {
  font-size: 12px;
  color: var(--text-muted);
  margin-top: 6px;
  line-height: 1.4;
}

.row-flex {
  display: flex;
  gap: 16px;
}
.flex-1 {
  flex: 1;
}

.test-result {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  font-weight: 500;
  margin-top: 8px;
}
.test-result.valid { color: #10b981; }
.test-result.invalid { color: #ef4444; }

.form-actions {
  margin-top: 40px;
  padding-top: 24px;
  border-top: 1px solid var(--border-color-light);
  display: flex;
  gap: 12px;
}

/* 新增预设选项样式 */
.preset-opt { display: flex; align-items: center; gap: 8px; width: 100%; }
.preset-dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
.preset-url { margin-left: auto; font-size: 10px; color: var(--text-muted); font-family: monospace; max-width: 200px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
</style>
