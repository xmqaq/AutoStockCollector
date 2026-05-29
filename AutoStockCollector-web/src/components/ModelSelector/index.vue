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

const modelMap: Record<string, string[]> = {
  'openai': ['gpt-4o', 'gpt-4o-mini', 'gpt-4-turbo', 'gpt-4', 'gpt-3.5-turbo'],
  'anthropic': ['claude-3-5-sonnet-20241022', 'claude-3-5-sonnet-latest', 'claude-3-opus-latest', 'claude-3-sonnet-latest', 'claude-3-haiku-latest'],
  'qwen': ['qwen-max', 'qwen-plus', 'qwen-turbo', 'qwen-max-longcontext'],
  'deepseek': ['deepseek-chat', 'deepseek-coder'],
  'gemini': ['gemini-1.5-pro', 'gemini-1.5-flash', 'gemini-1.0-pro'],
  'moonshot': ['moonshot-v1-8k', 'moonshot-v1-32k', 'moonshot-v1-128k'],
  'glm': ['glm-4', 'glm-4-plus', 'glm-4-air', 'glm-4-flash'],
  'doubao': ['doubao-pro-32k', 'doubao-pro-128k', 'doubao-lite-32k'],
  'minimax': ['MiniMax-Text-01', 'abab6-chat'],
  'mistral': ['mistral-large-latest', 'mistral-medium-latest', 'mistral-small-latest'],
}

const recommendedModels: Record<string, string> = {
  'openai': 'gpt-4o-mini',
  'anthropic': 'claude-3-5-sonnet-latest',
  'qwen': 'qwen-plus',
  'deepseek': 'deepseek-chat',
  'gemini': 'gemini-1.5-flash',
  'moonshot': 'moonshot-v1-8k',
  'glm': 'glm-4-flash',
  'doubao': 'doubao-pro-32k',
  'minimax': 'MiniMax-Text-01',
  'mistral': 'mistral-small-latest',
}

async function fetchModelsFromProvider(provider: AIKeyConfig): Promise<AIModel[]> {
  const providerLower = provider.provider.toLowerCase()
  
  if (providerLower === 'minimax') {
    return modelMap['minimax'].map(id => ({
      id,
      name: id,
      provider: provider.provider
    }))
  }

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
    return getFallbackModels(providerLower)
  }
}

function getFallbackModels(provider: string): AIModel[] {
  const modelIds = modelMap[provider] || []
  return modelIds.map(id => ({
    id,
    name: id,
    provider
  }))
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
      fetchedModels = getFallbackModels(props.provider.toLowerCase())
    }

    if (fetchedModels.length === 0) {
      fetchedModels = getFallbackModels(props.provider.toLowerCase())
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
    models.value = getFallbackModels(props.provider?.toLowerCase() || '')
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
  color: #909399;
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
  color: #909399;
}
</style>