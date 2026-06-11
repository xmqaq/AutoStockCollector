<template>
  <div class="model-selector" :class="{ 'is-disabled': disabled || loading || !!error }">
    <el-select
      v-model="selectedModel"
      :placeholder="placeholderText"
      :filterable="true"
      :clearable="true"
      :disabled="disabled || loading || !!error"
      :loading="loading"
      filter-placeholder="搜索模型..."
      @change="handleChange"
      style="width: 100%"
    >
      <template #prefix>
        <el-icon v-if="loading" class="is-loading"><Loading /></el-icon>
        <el-icon v-else-if="error"><Warning /></el-icon>
        <el-icon v-else><Monitor /></el-icon>
      </template>
      
      <template #empty>
        <div v-if="loading" class="selector-empty">
          <el-icon class="is-loading"><Loading /></el-icon>
          <span>加载中...</span>
        </div>
        <div v-else-if="error" class="selector-error">
          <el-icon><Warning /></el-icon>
          <span>{{ error }}</span>
        </div>
        <div v-else-if="models.length === 0" class="selector-empty">
          <span>暂无可用模型</span>
        </div>
      </template>

      <el-option
        v-for="model in models"
        :key="model.id || model"
        :label="getModelLabel(model)"
        :value="getModelValue(model)"
        :disabled="isModelDisabled(model)"
      >
        <div class="model-option">
          <span class="model-name">{{ getModelLabel(model) }}</span>
          <el-tag v-if="isDefaultModel(model)" size="small" type="info">默认</el-tag>
          <el-tag v-if="isRecommendedModel(model)" size="small" type="success">推荐</el-tag>
        </div>
      </el-option>
    </el-select>

    <div v-if="showHint && currentProvider" class="selector-hint">
      <el-icon size="12"><InfoFilled /></el-icon>
      <span>当前: {{ currentProvider.name }}</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
import { Loading, Warning, Monitor, InfoFilled } from '@element-plus/icons-vue'
import { aiKeyApi } from '@/api/ai'
import client from '@/api/client'

interface AIModel {
  id: string
  name: string
  provider?: string
  type?: string
  context_length?: number
}

interface AIKeyConfig {
  provider: string
  name: string
  enabled: boolean
  base_url?: string
  api_key?: string
}

const props = defineProps<{
  model?: string
  provider?: string
  disabled?: boolean
  showHint?: boolean
  defaultModel?: string
}>()

const emit = defineEmits<{
  'update:model': [value: string]
  'change': [value: string, modelInfo?: AIModel]
  'loaded': [models: AIModel[]]
}>()

const loading = ref(false)
const error = ref('')
const models = ref<AIModel[]>([])
const selectedModel = ref(props.model || '')
const currentProvider = ref<AIKeyConfig | null>(null)

const placeholderText = computed(() => {
  if (loading.value) return '加载模型中...'
  if (error.value) return '加载失败'
  if (models.value.length === 0) return '暂无可用模型'
  return '选择AI模型'
})

const modelMap: Record<string, string[]> = {}

const recommendedModels: Record<string, string> = {}

async function fetchModelsFromProvider(provider: AIKeyConfig): Promise<AIModel[]> {
  const providerLower = provider.provider.toLowerCase()
  
  const baseUrl = provider.base_url || ''
  const modelsEndpoint = baseUrl.includes('/v1') 
    ? baseUrl.replace(/\/+$/, '') + '/models'
    : baseUrl.replace(/\/+$/, '') + '/v1/models'

  try {
    const resp = await client.get(modelsEndpoint, {
      headers: {
        'Authorization': `Bearer ${provider.api_key}`
      }
    })
    
    const data = resp.data?.data || resp.data?.models || []
    
    if (Array.isArray(data)) {
      return data.map((m: any) => ({
        id: m.id || m.name || m.model,
        name: m.id || m.name || m.model,
        provider: provider.provider,
        type: m.type,
        context_length: m.context_length || m.max_tokens
      }))
    }
    
    return []
  } catch (e: any) {
    console.warn(`Failed to fetch models from ${provider.provider}:`, e.message)
    return []
  }
}

async function loadModels() {
  if (!props.provider) {
    error.value = '请先选择AI密钥'
    return
  }

  loading.value = true
  error.value = ''

  try {
    const keysResponse = await aiKeyApi.list()
    const keys: AIKeyConfig[] = keysResponse.data?.data || keysResponse.data || []
    
    const providerKey = keys.find(k => k.provider.toLowerCase() === props.provider?.toLowerCase())
    
    if (!providerKey) {
      error.value = '未找到对应的AI密钥配置'
      loading.value = false
      return
    }

    currentProvider.value = providerKey

    let fetchedModels: AIModel[] = []
    
    try {
      fetchedModels = await fetchModelsFromProvider(providerKey)
    } catch (e) {
      fetchedModels = []
    }

    if (fetchedModels.length === 0) {
      error.value = '暂无可用模型，请手动输入模型名称'
    }

    models.value = fetchedModels
    emit('loaded', fetchedModels)

    if (!props.model && props.defaultModel) {
      const defaultExists = fetchedModels.some(m => m.id === props.defaultModel || m.name === props.defaultModel)
      if (defaultExists) {
        selectedModel.value = props.defaultModel
      }
    }

  } catch (e: any) {
    error.value = e.message || '加载模型列表失败'
    models.value = []
  } finally {
    loading.value = false
  }
}

function getModelLabel(model: AIModel | string): string {
  if (typeof model === 'string') return model
  return model.name || model.id
}

function getModelValue(model: AIModel | string): string {
  if (typeof model === 'string') return model
  return model.id || model.name
}

function isDefaultModel(model: AIModel | string): boolean {
  const modelId = getModelValue(model)
  const providerLower = (props.provider || '').toLowerCase()
  const rec = recommendedModels[providerLower]
  return rec === modelId
}

function isRecommendedModel(model: AIModel | string): boolean {
  return isDefaultModel(model)
}

function isModelDisabled(model: AIModel | string): boolean {
  return false
}

function handleChange(value: string) {
  const modelInfo = models.value.find(m => (m.id || m.name) === value)
  emit('update:model', value)
  emit('change', value, modelInfo)
}

watch(() => props.provider, () => {
  if (props.provider) {
    loadModels()
  } else {
    models.value = []
    selectedModel.value = ''
    error.value = ''
  }
})

watch(() => props.model, (newModel) => {
  selectedModel.value = newModel || ''
})

onMounted(() => {
  if (props.provider) {
    loadModels()
  }
})

defineExpose({
  loadModels,
  getModels: () => models.value
})
</script>

<style scoped>
.model-selector {
  width: 100%;
}

.model-selector.is-disabled {
  opacity: 0.6;
}

.selector-empty,
.selector-error {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 12px;
  color: var(--text-muted);
  font-size: 13px;
}

.selector-error {
  color: #f56c6c;
}

.model-option {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
}

.model-name {
  flex: 1;
}

.selector-hint {
  display: flex;
  align-items: center;
  gap: 4px;
  margin-top: 6px;
  font-size: 12px;
  color: var(--text-muted);
}
</style>