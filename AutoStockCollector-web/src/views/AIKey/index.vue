<template>
  <div class="ak-page">

    <!-- 页头 -->
    <div class="ak-header">
      <div class="ak-header-left">
        <span class="ak-title">API Key 管理</span>
        <span class="ak-count">{{ keys.length }} 个厂商</span>
      </div>
      <button class="ak-add-btn" @click="openAddDialog">
        <svg width="11" height="11" viewBox="0 0 11 11" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"><line x1="5.5" y1="1" x2="5.5" y2="10"/><line x1="1" y1="5.5" x2="10" y2="5.5"/></svg>
        新增厂商
      </button>
    </div>

    <!-- 卡片列表 -->
    <div v-loading="loading" element-loading-background="rgba(8,8,12,0.8)" class="ak-list">
      <div
        v-for="row in keys"
        :key="row.provider"
        class="ak-card"
        :class="testState[row.provider]"
        :style="{ '--accent': providerColor(row.provider) }"
      >
        <!-- 左色条 -->
        <div class="ak-accent-bar"></div>

        <div class="ak-card-inner">
          <!-- ── 卡头 ── -->
          <div class="ak-card-head">
            <div class="ak-provider-icon" :style="{ background: providerColor(row.provider) }">
              {{ row.name.charAt(0).toUpperCase() }}
            </div>
            <div class="ak-provider-info">
              <span class="ak-provider-name">{{ row.name }}</span>
              <code class="ak-provider-id">{{ row.provider }}</code>
            </div>
            <div class="ak-head-actions">
              <span
                class="ak-status-dot"
                :class="{
                  dot_valid:   testState[row.provider] === 'valid',
                  dot_invalid: testState[row.provider] === 'invalid',
                  dot_key:     row.has_key && !testState[row.provider],
                }"
                :title="testState[row.provider] === 'valid' ? '验证通过' : testState[row.provider] === 'invalid' ? testMsg[row.provider] : row.has_key ? 'Key 已配置' : '未配置'"
              ></span>
              <el-switch
                v-model="row.enabled"
                size="small"
                :style="{ '--el-switch-on-color': providerColor(row.provider) }"
                @change="toggle(row)"
              />
              <button class="ak-icon-btn ak-del" @click="remove(row.provider)" title="删除">
                <svg width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><line x1="2" y1="2" x2="10" y2="10"/><line x1="10" y1="2" x2="2" y2="10"/></svg>
              </button>
            </div>
          </div>

          <!-- ── API Key 行 ── -->
          <div class="ak-section">
            <span class="ak-section-label">API Key</span>
            <div class="ak-key-row">
              <el-input
                v-model="row.api_key"
                type="password"
                size="small"
                show-password
                :placeholder="row.has_key ? '已配置 — 重新输入以更新' : '粘贴 API Key…'"
                class="ak-key-input"
                @keyup.enter="saveKey(row)"
              />
              <button
                class="ak-btn ak-btn-save"
                :class="{ active: !!row.api_key, saving: row._saving, saved: row._saved }"
                :disabled="!row.api_key || row._saving"
                @click="saveKey(row)"
              >
                <span v-if="row._saving" class="spin">◌</span>
                <span v-else-if="row._saved">✓ 已保存</span>
                <span v-else>保存</span>
              </button>
            </div>
          </div>

          <!-- ── Base URL（自定义时显示） ── -->
          <div v-if="row.base_url && !isBuiltinUrl(row.provider, row.base_url)" class="ak-section ak-url-section">
            <span class="ak-section-label">Base URL</span>
            <code class="ak-url-val">{{ row.base_url }}</code>
          </div>

          <!-- ── 模型选择 ── -->
          <div class="ak-section">
            <span class="ak-section-label">模型</span>
            <div class="ak-model-row">
              <el-select
                v-model="selectedModels[row.provider]"
                placeholder="选择模型"
                filterable
                clearable
                size="small"
                class="ak-model-select"
                :loading="modelLoading[row.provider]"
              >
                <el-option
                  v-for="m in modelOptions[row.provider] || []"
                  :key="m"
                  :label="m"
                  :value="m"
                >
                  <div class="model-opt">
                    <span>{{ m }}</span>
                    <el-tag v-if="m === confirmedModels[row.provider]" size="small" type="success" effect="plain">已选</el-tag>
                    <el-tag v-else-if="m === defaultModels[row.provider]" size="small" type="info" effect="plain">默认</el-tag>
                  </div>
                </el-option>
              </el-select>
              <!-- 从 API 获取模型 -->
              <button
                class="ak-icon-btn ak-fetch-btn"
                :class="{ loading: modelLoading[row.provider] }"
                :disabled="modelLoading[row.provider]"
                title="从 API 获取可用模型"
                @click="fetchModelsFromApi(row)"
              >
                <svg v-if="!modelLoading[row.provider]" width="13" height="13" viewBox="0 0 13 13" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                  <path d="M11.5 6.5A5 5 0 1 1 8 2.07"/>
                  <polyline points="11.5 1 11.5 4.5 8 4.5"/>
                </svg>
                <span v-else class="spin" style="font-size:12px">◌</span>
              </button>
              <!-- 确认保存 -->
              <button
                v-if="selectedModels[row.provider] && selectedModels[row.provider] !== confirmedModels[row.provider]"
                class="ak-btn ak-btn-confirm"
                @click="confirmModel(row.provider)"
              >
                确认
              </button>
              <span v-else-if="confirmedModels[row.provider]" class="ak-confirmed-badge">
                <svg width="10" height="10" viewBox="0 0 10 10" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><polyline points="1.5 5 4 7.5 8.5 2.5"/></svg>
                {{ confirmedModels[row.provider] }}
              </span>
            </div>
          </div>

          <!-- ── 优先级 ── -->
          <div class="ak-section ak-priority-section">
            <span class="ak-section-label">优先级</span>
            <div class="ak-priority-row">
              <el-input-number
                v-model="row.priority"
                :min="1"
                :max="99"
                size="small"
                controls-position="right"
                class="ak-priority-input"
                @change="savePriority(row)"
              />
              <span class="ak-priority-hint">数字越小越先调用，失败自动切换下一家</span>
            </div>
          </div>

          <!-- ── 验证行 ── -->
          <div class="ak-section ak-test-section">
            <div class="ak-test-status">
              <template v-if="testState[row.provider] === 'valid'">
                <span class="ak-test-dot valid"></span><span class="ak-test-text valid">验证通过</span>
              </template>
              <template v-else-if="testState[row.provider] === 'invalid'">
                <el-tooltip :content="testMsg[row.provider]" placement="top" effect="dark">
                  <span class="ak-test-invalid">
                    <span class="ak-test-dot invalid"></span><span class="ak-test-text invalid">验证失败</span>
                  </span>
                </el-tooltip>
              </template>
              <span v-else class="ak-test-text idle">未验证</span>
            </div>
            <button
              class="ak-btn ak-btn-test"
              :class="testState[row.provider] || 'idle'"
              :disabled="testState[row.provider] === 'testing'"
              @click="testKey(row)"
            >
              <span v-if="testState[row.provider] === 'testing'" class="spin">◌</span>
              <span v-else>验证 Key</span>
            </button>
          </div>

        </div>
      </div>

      <div v-if="!loading && keys.length === 0" class="ak-empty">
        <div class="ak-empty-icon">⚷</div>
        <p>暂无配置，点击右上角新增厂商</p>
      </div>
    </div>

    <!-- 新增对话框 -->
    <el-dialog v-model="showDialog" :title="isCustom ? '自定义 AI 接口' : '新增 AI 厂商'" width="480px" @close="resetForm">
      <el-form :model="form" :rules="formRules" ref="formRef" label-width="90px" class="ak-form">
        <el-form-item label="选择厂商">
          <el-select v-model="form.preset" placeholder="选择主流厂商或自定义…" style="width:100%" @change="onPresetChange">
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
        <el-form-item v-if="isCustom" label="Provider" prop="provider">
          <el-input v-model="form.provider" placeholder="自定义标识，如 my-llm" />
        </el-form-item>
        <el-form-item label="显示名称" prop="name">
          <el-input v-model="form.name" :disabled="!isCustom && !!form.preset" />
        </el-form-item>
        <el-form-item label="Base URL" :prop="isCustom ? 'base_url' : undefined">
          <el-input v-model="form.base_url" :disabled="!isCustom && !!form.preset" placeholder="https://api.example.com/v1" />
          <div v-if="!isCustom && form.preset" class="form-tip">预设地址，如需修改请选"自定义接口"</div>
        </el-form-item>
        <el-form-item label="API Key">
          <el-input v-model="form.api_key" type="password" show-password placeholder="粘贴 API Key（可留空稍后配置）" />
        </el-form-item>
        <el-form-item label="启用">
          <el-switch v-model="form.enabled" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showDialog = false">取消</el-button>
        <el-button type="primary" :loading="submitting" :disabled="!form.preset" @click="submitAdd">添加</el-button>
      </template>
    </el-dialog>

  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'
import { aiKeyApi, type AIKeyConfig } from '@/api/ai'

const PRESETS = [
  { value: 'openai',    label: 'OpenAI',                 provider: 'openai',    base_url: 'https://api.openai.com/v1',                         color: '#10a37f' },
  { value: 'anthropic', label: 'Anthropic (Claude)',      provider: 'anthropic', base_url: 'https://api.anthropic.com',                         color: '#d4805a' },
  { value: 'qwen',      label: '通义千问 (Qwen)',          provider: 'qwen',      base_url: 'https://dashscope.aliyuncs.com/compatible-mode/v1', color: '#5664f5' },
  { value: 'deepseek',  label: 'DeepSeek',                provider: 'deepseek',  base_url: 'https://api.deepseek.com/v1',                       color: '#4b7bf4' },
  { value: 'gemini',    label: 'Google Gemini',           provider: 'gemini',    base_url: 'https://generativelanguage.googleapis.com/v1beta',  color: '#4285f4' },
  { value: 'moonshot',  label: '月之暗面 (Moonshot)',      provider: 'moonshot',  base_url: 'https://api.moonshot.cn/v1',                        color: '#8b5cf6' },
  { value: 'glm',       label: '智谱 AI (GLM)',            provider: 'glm',       base_url: 'https://open.bigmodel.cn/api/paas/v4',             color: '#2563eb' },
  { value: 'doubao',    label: '字节豆包 (Doubao)',         provider: 'doubao',    base_url: 'https://ark.cn-beijing.volces.com/api/v3',          color: '#f59e0b' },
  { value: 'mistral',   label: 'Mistral AI',              provider: 'mistral',   base_url: 'https://api.mistral.ai/v1',                         color: '#f87c56' },
  { value: 'minimax',   label: 'MiniMax',                 provider: 'minimax',   base_url: 'https://api.minimax.io/v1/text/chatcompletion_v2',  color: '#00d4aa' },
  { value: 'cohere',    label: 'Cohere',                  provider: 'cohere',    base_url: 'https://api.cohere.com/v1',                         color: '#39594d' },
  { value: 'agnes',     label: 'Agnes AI',               provider: 'agnes',     base_url: 'https://apihub.agnes-ai.com/v1',                    color: '#8B5CF6' },
  { value: 'custom',    label: '自定义接口',               provider: '',          base_url: '',                                                  color: '#666688' },
]

const BUILTIN_URLS: Record<string, string> = Object.fromEntries(
  PRESETS.filter(p => p.value !== 'custom').map(p => [p.provider, p.base_url])
)

const COLOR_MAP: Record<string, string> = Object.fromEntries(
  PRESETS.filter(p => p.value !== 'custom').map(p => [p.provider, p.color])
)

function providerColor(provider: string): string {
  const lower = provider.toLowerCase()
  for (const [k, v] of Object.entries(COLOR_MAP)) {
    if (lower.includes(k)) return v
  }
  let h = 0
  for (let i = 0; i < provider.length; i++) h = provider.charCodeAt(i) + ((h << 5) - h)
  return `hsl(${Math.abs(h) % 360},50%,52%)`
}

function isBuiltinUrl(provider: string, url: string): boolean {
  return BUILTIN_URLS[provider] === url
}

type KeyRow = AIKeyConfig & { _saving?: boolean; _saved?: boolean }
type TestSt = 'idle' | 'testing' | 'valid' | 'invalid'

const loading    = ref(false)
const keys       = ref<KeyRow[]>([])
const showDialog = ref(false)
const submitting = ref(false)
const formRef    = ref<FormInstance>()

const testState = ref<Record<string, TestSt>>({})
const testMsg   = ref<Record<string, string>>({})

const modelOptions    = ref<Record<string, string[]>>({})
const modelLoading    = ref<Record<string, boolean>>({})
const selectedModels  = ref<Record<string, string>>({})
const confirmedModels = ref<Record<string, string>>({})

const defaultModels: Record<string, string> = {}

const defaultForm = () => ({ preset: '', provider: '', name: '', api_key: '', base_url: '', enabled: false })
const form = ref(defaultForm())
const isCustom = computed(() => form.value.preset === 'custom')
const formRules = computed<FormRules>(() => ({
  provider: isCustom.value ? [{ required: true, message: '请输入 Provider 标识', trigger: 'blur' }] : [],
  name:     [{ required: true, message: '请输入显示名称', trigger: 'blur' }],
  base_url: isCustom.value ? [{ required: true, message: '请输入 Base URL', trigger: 'blur' }] : [],
}))

function onPresetChange(val: string) {
  const p = PRESETS.find(x => x.value === val)
  if (!p) return
  form.value.provider = p.provider
  form.value.name     = p.label
  form.value.base_url = p.base_url
}

function openAddDialog() { resetForm(); showDialog.value = true }
function resetForm()     { form.value = defaultForm(); formRef.value?.clearValidate() }

async function loadKeys() {
  loading.value = true
  try {
    const res = await aiKeyApi.list()
    keys.value = (res.data?.data || [])
      .map((k: AIKeyConfig) => ({ ...k, api_key: '' }))
      .sort((a: AIKeyConfig, b: AIKeyConfig) => (a.priority ?? 99) - (b.priority ?? 99))
    for (const key of keys.value) {
      if (!modelOptions.value[key.provider]?.length) {
        modelOptions.value[key.provider] = []
      }
      if (key.model) {
        selectedModels.value[key.provider]  = key.model
        confirmedModels.value[key.provider] = key.model
      }
    }
  } catch {
    keys.value = []
  } finally {
    loading.value = false
  }
}

async function fetchModelsFromApi(row: KeyRow) {
  if (!row.has_key && !row.api_key) {
    ElMessage.warning('请先保存 API Key')
    return
  }
  modelLoading.value[row.provider] = true
  try {
    const res = await aiKeyApi.fetchModels(row.provider)
    const models: string[] = res.data?.models || []
    if (models.length) {
      modelOptions.value[row.provider] = models
      const source = res.data?.source
      ElMessage.success(source === 'api' ? `已从 API 获取 ${models.length} 个模型` : '使用内置模型列表')
    } else {
      ElMessage.warning('未获取到模型列表')
    }
  } catch {
    ElMessage.error('获取模型失败')
  } finally {
    modelLoading.value[row.provider] = false
  }
}

async function saveKey(row: KeyRow) {
  if (!row.api_key) return
  row._saving = true
  try {
    await aiKeyApi.update({
      provider: row.provider, name: row.name, enabled: row.enabled,
      priority: row.priority, api_key: row.api_key, base_url: row.base_url,
    })
    row.has_key = true
    row.api_key = ''
    row._saved  = true
    testState.value[row.provider] = 'idle'
    setTimeout(() => { row._saved = false }, 2200)
  } catch {
    ElMessage.error('保存失败')
  } finally {
    row._saving = false
  }
}

async function toggle(row: KeyRow) {
  try {
    await aiKeyApi.update({ provider: row.provider, name: row.name, enabled: row.enabled, priority: row.priority, base_url: row.base_url })
    ElMessage.success(row.enabled ? '已启用' : '已禁用')
  } catch {
    ElMessage.error('操作失败')
    row.enabled = !row.enabled
  }
}

async function savePriority(row: KeyRow) {
  if (row.priority == null) return
  try {
    await aiKeyApi.update({ provider: row.provider, name: row.name, enabled: row.enabled, priority: row.priority, base_url: row.base_url })
    keys.value = [...keys.value].sort((a, b) => (a.priority ?? 99) - (b.priority ?? 99))
    ElMessage.success(`${row.name} 优先级 → ${row.priority}`)
  } catch {
    ElMessage.error('优先级保存失败')
  }
}

async function remove(provider: string) {
  try {
    await ElMessageBox.confirm(`确认删除 "${provider}"？`, '删除确认', { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' })
    await aiKeyApi.remove(provider)
    ElMessage.success('已删除')
    await loadKeys()
  } catch (e: any) {
    if (e !== 'cancel') ElMessage.error('删除失败')
  }
}

async function testKey(row: KeyRow) {
  if (!row.has_key && !row.api_key) { ElMessage.warning('请先输入 API Key'); return }
  testState.value[row.provider] = 'testing'
  testMsg.value[row.provider]   = ''
  try {
    const res = await aiKeyApi.test(row.provider, row.api_key || undefined, row.base_url)
    const { valid, message } = res.data ?? {}
    testState.value[row.provider] = valid ? 'valid' : 'invalid'
    testMsg.value[row.provider]   = message || (valid ? '有效' : '无效')
    if (valid) {
      ElMessage.success(`${row.name} — Key 有效`)
      await fetchModelsFromApi(row)
    } else {
      ElMessage.error(`${row.name} — ${message || '无效'}`)
    }
  } catch {
    testState.value[row.provider] = 'invalid'
    testMsg.value[row.provider]   = '请求失败，请检查后端'
  }
}

async function confirmModel(provider: string) {
  const model = selectedModels.value[provider]
  if (!model) { ElMessage.warning('请先选择模型'); return }
  const row = keys.value.find(k => k.provider === provider)
  if (!row) return
  try {
    await aiKeyApi.update({ provider: row.provider, name: row.name, enabled: row.enabled, priority: row.priority, base_url: row.base_url, model })
    confirmedModels.value[provider] = model
    ElMessage.success(`已保存模型: ${model}`)
  } catch {
    ElMessage.error('模型保存失败')
  }
}

async function submitAdd() {
  if (!formRef.value) return
  if (!await formRef.value.validate().catch(() => false)) return
  const finalProvider = form.value.provider
  if (keys.value.some(k => k.provider === finalProvider)) { ElMessage.warning(`"${finalProvider}" 已存在`); return }
  submitting.value = true
  try {
    await aiKeyApi.update({ provider: finalProvider, name: form.value.name, enabled: form.value.enabled, priority: 99, api_key: form.value.api_key || undefined, base_url: form.value.base_url || undefined })
    ElMessage.success(`已添加 ${form.value.name}`)
    showDialog.value = false
    await loadKeys()
  } catch {
    ElMessage.error('添加失败')
  } finally {
    submitting.value = false
  }
}

onMounted(loadKeys)
</script>

<style scoped>
/* ── 页面 ── */
.ak-page { display: flex; flex-direction: column; gap: 14px; font-family: -apple-system, 'SF Pro Text', 'Segoe UI', sans-serif; color: #ffffff; }

/* ── 页头 ── */
.ak-header { display: flex; align-items: center; justify-content: space-between; }
.ak-header-left { display: flex; align-items: center; gap: 8px; }
.ak-title { font-size: 15px; font-weight: 700; color: #ffffff; letter-spacing: -0.01em; }
.ak-count { font-size: 11px; color: #9090d0; background: #111120; border: 1px solid #1e1e30; border-radius: 20px; padding: 1px 8px; }

.ak-add-btn {
  display: flex; align-items: center; gap: 6px; padding: 6px 14px;
  font-size: 12.5px; cursor: pointer; border-radius: 7px;
  background: #0e0e1a; border: 1px solid #22223a; color: #9090d0;
  transition: all 0.15s;
}
.ak-add-btn:hover { background: #16162a; border-color: #4444aa; color: #a0a0dd; }

/* ── 卡片列表 ── */
.ak-list { display: grid; grid-template-columns: repeat(auto-fill, minmax(380px, 1fr)); gap: 12px; }

/* ── 卡片 ── */
.ak-card {
  display: flex; border-radius: 10px; overflow: hidden;
  background: #0c0c14; border: 1px solid #18182a;
  transition: border-color 0.2s, box-shadow 0.2s;
}
.ak-card:hover { border-color: #222238; box-shadow: 0 2px 20px rgba(0,0,0,0.4); }
.ak-card.valid   { border-color: #152a1e; }
.ak-card.invalid { border-color: #2a1515; }

.ak-accent-bar { width: 3px; background: var(--accent); flex-shrink: 0; opacity: 0.7; }
.ak-card-inner { flex: 1; padding: 14px 16px; display: flex; flex-direction: column; gap: 10px; min-width: 0; color: #ffffff; }

/* ── 卡头 ── */
.ak-card-head { display: flex; align-items: center; gap: 10px; }

.ak-provider-icon {
  width: 32px; height: 32px; border-radius: 8px; flex-shrink: 0;
  display: flex; align-items: center; justify-content: center;
  font-size: 13px; font-weight: 800; color: rgba(255,255,255,0.9);
}
.ak-provider-info { flex: 1; min-width: 0; display: flex; align-items: baseline; gap: 7px; }
.ak-provider-name { font-size: 13.5px; font-weight: 700; color: #ffffff; white-space: nowrap; }
.ak-provider-id {
  font-size: 10px; color: #9090d0; padding: 1px 5px;
  background: #0e0e1e; border: 1px solid #1a1a2e; border-radius: 4px;
  font-family: 'JetBrains Mono', 'SF Mono', monospace;
}

.ak-head-actions { display: flex; align-items: center; gap: 8px; flex-shrink: 0; }

.ak-status-dot {
  width: 8px; height: 8px; border-radius: 50%; background: #505090;
  flex-shrink: 0; transition: all 0.3s; cursor: help;
}
.ak-status-dot.dot_valid   { background: #2ecc71; box-shadow: 0 0 7px rgba(46,204,113,0.5); }
.ak-status-dot.dot_invalid { background: #e74c3c; box-shadow: 0 0 7px rgba(231,76,60,0.4); }
.ak-status-dot.dot_key     { background: var(--accent); box-shadow: 0 0 5px var(--accent); opacity: 0.6; }

.ak-icon-btn {
  width: 26px; height: 26px; display: flex; align-items: center; justify-content: center;
  background: transparent; border: 1px solid transparent; border-radius: 5px;
  cursor: pointer; color: #7070b0; transition: all 0.12s; padding: 0; flex-shrink: 0;
}
.ak-del:hover { border-color: #4a1a1a; color: #cc4444; background: #160a0a; }

/* ── Section 通用 ── */
.ak-section { display: flex; align-items: center; gap: 8px; }
.ak-section-label { font-size: 11px; color: #ffffff; min-width: 52px; flex-shrink: 0; text-align: right; }

/* ── Key 行 ── */
.ak-key-row { flex: 1; display: flex; gap: 7px; }
.ak-key-input { flex: 1; }
.ak-key-input :deep(.el-input__wrapper) { background: #0e0e1c !important; box-shadow: none !important; border: 1px solid #1a1a2e !important; }
.ak-key-input :deep(.el-input__wrapper:hover) { border-color: #252545 !important; }
.ak-key-input :deep(.el-input__wrapper.is-focus) { border-color: var(--accent) !important; }
.ak-key-input :deep(.el-input__inner) { color: #ffffff; font-family: 'JetBrains Mono', monospace; font-size: 12px; }
.ak-key-input :deep(.el-input__inner::placeholder) { color: #505090; }

/* ── URL 行 ── */
.ak-url-section { opacity: 0.7; }
.ak-url-val {
  font-size: 10.5px; color: #9090d0; font-family: 'JetBrains Mono', monospace;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 300px;
}

/* ── 模型行 ── */
.ak-model-row { flex: 1; display: flex; align-items: center; gap: 6px; }
.ak-model-select { flex: 1; }
.ak-model-select :deep(.el-input__wrapper) { background: #0e0e1c !important; box-shadow: none !important; border: 1px solid #1a1a2e !important; }
.ak-model-select :deep(.el-input__wrapper:hover) { border-color: #252545 !important; }
.ak-model-select :deep(.el-select__wrapper) { background: #0e0e1c !important; box-shadow: none !important; border: 1px solid #1a1a2e !important; }
.ak-model-select :deep(.el-select__selected-item) { color: #ffffff !important; font-weight: 500; }
.ak-model-select :deep(.el-select__placeholder) { color: #7070b0 !important; }
.ak-model-select :deep(.el-select-dropdown__item) { color: #ffffff !important; }
.ak-model-select :deep(.el-select-dropdown__item.hover) { background: #1a1a30 !important; }
.ak-model-select :deep(.el-select-dropdown__item.selected) { color: #ffffff !important; font-weight: 600; }

.ak-fetch-btn {
  border: 1px solid #1a1a2e; background: #0e0e1c; color: #505080;
}
.ak-fetch-btn:hover:not(:disabled) { border-color: var(--accent); color: var(--accent); background: color-mix(in srgb, var(--accent) 10%, transparent); }
.ak-fetch-btn.loading { opacity: 0.5; cursor: wait; }

.ak-confirmed-badge {
  display: flex; align-items: center; gap: 4px;
  font-size: 11px; color: #4ade80; white-space: nowrap;
  background: #0a1a10; border: 1px solid #152a1e; border-radius: 5px; padding: 2px 8px;
}

.model-opt { display: flex; align-items: center; justify-content: space-between; width: 100%; gap: 6px; }

/* ── 测试行 ── */
.ak-test-section { justify-content: space-between; padding-top: 4px; border-top: 1px solid #111120; margin-top: 2px; }

/* 优先级 */
.ak-priority-row { display: flex; align-items: center; gap: 8px; flex: 1; min-width: 0; }
.ak-priority-input { width: 86px; flex-shrink: 0; }
.ak-priority-hint { font-size: 11px; color: #565670; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.ak-test-status { display: flex; align-items: center; gap: 5px; }
.ak-test-dot { width: 6px; height: 6px; border-radius: 50%; flex-shrink: 0; }
.ak-test-dot.valid   { background: #2ecc71; }
.ak-test-dot.invalid { background: #e74c3c; }
.ak-test-text { font-size: 11.5px; }
.ak-test-text.valid  { color: #4ade80; }
.ak-test-text.invalid{ color: #f87171; }
.ak-test-text.idle   { color: #8080c0; }
.ak-test-invalid { display: flex; align-items: center; gap: 5px; cursor: help; }

/* ── 通用按钮 ── */
.ak-btn {
  flex-shrink: 0; padding: 4px 11px; font-size: 12px; border-radius: 5px;
  cursor: pointer; border: 1px solid #1c1c2e; background: #0e0e1c; color: #8080c0;
  transition: all 0.15s; white-space: nowrap;
}
.ak-btn:disabled { opacity: 0.3; cursor: not-allowed; }

.ak-btn-save.active { border-color: var(--accent); color: var(--accent); background: color-mix(in srgb, var(--accent) 10%, transparent); }
.ak-btn-save.saved  { border-color: #152a1e; background: #0a1810; color: #3a8a52; }

.ak-btn-confirm { border-color: var(--accent); color: var(--accent); background: color-mix(in srgb, var(--accent) 10%, transparent); }
.ak-btn-confirm:hover { background: color-mix(in srgb, var(--accent) 18%, transparent); }

.ak-btn-test:hover:not(:disabled) { border-color: #303060; background: #141428; color: #8888cc; }
.ak-btn-test.valid   { border-color: #152a1e; background: #0a1810; color: #3a8a52; }
.ak-btn-test.invalid { border-color: #2a1515; background: #140a0a; color: #8a4040; }

/* ── 旋转 ── */
.spin { display: inline-block; animation: spinIt 0.8s linear infinite; }
@keyframes spinIt { to { transform: rotate(360deg); } }

/* ── 空状态 ── */
.ak-empty { text-align: center; padding: 60px 0; color: #6060a0; }
.ak-empty-icon { font-size: 34px; opacity: 0.25; margin-bottom: 10px; }

/* ── 对话框 ── */
.ak-form :deep(.el-form-item__label) { color: #ffffff; font-size: 12.5px; }
.ak-form :deep(.el-input__inner) { color: #ffffff !important; }
.preset-opt { display: flex; align-items: center; gap: 8px; width: 100%; }
.preset-dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
.preset-url { margin-left: auto; font-size: 10px; color: #7070b0; font-family: monospace; max-width: 200px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.form-tip { font-size: 11px; color: #7070b0; margin-top: 4px; }
</style>
