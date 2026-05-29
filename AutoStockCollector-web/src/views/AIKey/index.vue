<template>
  <div class="ak-page">

    <!-- ── 页头 ── -->
    <div class="ak-header">
      <div class="ak-header-left">
        <span class="ak-title">API Key 管理</span>
        <span class="ak-badge">{{ keys.length }}</span>
      </div>
      <button class="ak-add-btn" @click="openAddDialog">
        <svg width="10" height="10" viewBox="0 0 10 10" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round">
          <line x1="5" y1="1" x2="5" y2="9"/><line x1="1" y1="5" x2="9" y2="5"/>
        </svg>
        新增厂商
      </button>
    </div>

    <!-- ── 卡片列表 ── -->
    <div v-loading="loading" element-loading-background="rgba(10,10,14,0.7)" class="ak-list">
      <transition-group name="ak-slide" tag="div">
        <div
          v-for="row in keys"
          :key="row.provider"
          class="ak-card"
          :class="{
            'state-valid':   testState[row.provider] === 'valid',
            'state-invalid': testState[row.provider] === 'invalid',
          }"
          :style="{ '--accent': providerColor(row.provider) }"
        >
          <div class="ak-stripe"></div>

          <!-- 厂商图标 -->
          <div class="ak-icon" :style="{ background: providerColor(row.provider) }">
            {{ row.name.charAt(0).toUpperCase() }}
          </div>

          <!-- 主体 -->
          <div class="ak-body">

            <!-- 行1：名称 + 开关 + 删除 -->
            <div class="ak-row ak-row-title">
              <div class="ak-names">
                <span class="ak-name">{{ row.name }}</span>
                <code class="ak-pid">{{ row.provider }}</code>
              </div>
              <div class="ak-row-title-right">
                <el-switch
                  v-model="row.enabled"
                  size="small"
                  :style="{ '--el-switch-on-color': providerColor(row.provider) }"
                  @change="toggle(row)"
                />
                <button class="ak-del-btn" @click="remove(row.provider)" title="删除">
                  <svg width="13" height="13" viewBox="0 0 13 13" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round">
                    <line x1="2" y1="2" x2="11" y2="11"/><line x1="11" y1="2" x2="2" y2="11"/>
                  </svg>
                </button>
              </div>
            </div>

            <!-- 行2：API Key 输入 + 内联保存 -->
            <div class="ak-row ak-row-key">
              <span class="ak-dot" :class="{ on: row.has_key }"></span>
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
                class="ak-save-btn"
                :class="{
                  active:   !!row.api_key,
                  saving:   row._saving,
                  saved:    row._saved,
                }"
                :disabled="!row.api_key || row._saving"
                @click="saveKey(row)"
              >
                <span v-if="row._saving" class="ak-spinner">◌</span>
                <span v-else-if="row._saved">✓</span>
                <span v-else>保存</span>
              </button>
            </div>

            <!-- 行3：Base URL（有则显示） -->
            <div v-if="row.base_url" class="ak-row ak-row-url">
              <svg width="11" height="11" viewBox="0 0 11 11" fill="none" stroke="currentColor" stroke-width="1.5" opacity="0.4">
                <circle cx="5.5" cy="5.5" r="4.5"/>
                <path d="M5.5 1C5.5 1 3.5 3 3.5 5.5s2 4.5 2 4.5"/>
                <path d="M5.5 1C5.5 1 7.5 3 7.5 5.5s-2 4.5-2 4.5"/>
                <line x1="1" y1="5.5" x2="10" y2="5.5"/>
              </svg>
              <span class="ak-url-text">{{ row.base_url }}</span>
            </div>

            <!-- 行4：验证 -->
            <div class="ak-row ak-row-test">
              <div class="ak-test-result" :class="testState[row.provider]">
                <template v-if="testState[row.provider] === 'valid'">
                  <span class="rdot valid"></span>验证通过
                </template>
                <template v-else-if="testState[row.provider] === 'invalid'">
                  <el-tooltip :content="testMsg[row.provider]" placement="top" effect="dark">
                    <span class="ak-invalid-wrap"><span class="rdot invalid"></span>验证失败</span>
                  </el-tooltip>
                </template>
              </div>
              <button
                class="ak-test-btn"
                :class="testState[row.provider] || 'idle'"
                :disabled="testState[row.provider] === 'testing'"
                @click="testKey(row)"
              >
                <span v-if="testState[row.provider] === 'testing'" class="ak-spinner">◌</span>
                <span v-else-if="testState[row.provider] === 'valid'">✓ 有效</span>
                <span v-else-if="testState[row.provider] === 'invalid'">✗ 无效</span>
                <span v-else>验证 Key</span>
              </button>
            </div>

          </div>
        </div>
      </transition-group>

      <div v-if="!loading && keys.length === 0" class="ak-empty">
        <div class="ak-empty-icon">⚷</div>
        <p>暂无配置，点击右上角新增厂商</p>
      </div>
    </div>

    <!-- ── 新增对话框 ── -->
    <el-dialog
      v-model="showDialog"
      :title="isCustom ? '自定义 AI 接口' : '新增 AI 厂商'"
      width="500px"
      @close="resetForm"
    >
      <el-form :model="form" :rules="formRules" ref="formRef" label-width="88px" class="ak-form">

        <!-- 预设选择 -->
        <el-form-item label="选择厂商">
          <el-select
            v-model="form.preset"
            placeholder="选择主流厂商或自定义…"
            style="width: 100%"
            @change="onPresetChange"
          >
            <el-option-group label="主流厂商">
              <el-option
                v-for="p in PRESETS.filter(x => x.value !== 'custom')"
                :key="p.value"
                :label="p.label"
                :value="p.value"
              >
                <div class="preset-option">
                  <span class="preset-dot" :style="{ background: p.color }"></span>
                  <span>{{ p.label }}</span>
                  <code class="preset-url">{{ p.base_url.replace('https://', '') }}</code>
                </div>
              </el-option>
            </el-option-group>
            <el-option-group label="其他">
              <el-option label="自定义接口（OpenAI 兼容）" value="custom">
                <div class="preset-option">
                  <span class="preset-dot" style="background:#666"></span>
                  <span>自定义接口（OpenAI 兼容）</span>
                </div>
              </el-option>
            </el-option-group>
          </el-select>
        </el-form-item>

        <!-- 自定义时显示 Provider ID -->
        <el-form-item v-if="isCustom" label="Provider" prop="provider">
          <el-input v-model="form.provider" placeholder="自定义标识，如 my-llm" />
        </el-form-item>

        <!-- 显示名称（预设时只读，自定义可编辑） -->
        <el-form-item label="显示名称" prop="name">
          <el-input v-model="form.name" :disabled="!isCustom && !!form.preset" />
        </el-form-item>

        <!-- Base URL -->
        <el-form-item label="Base URL" :prop="isCustom ? 'base_url' : undefined">
          <el-input
            v-model="form.base_url"
            :disabled="!isCustom && !!form.preset"
            placeholder="https://api.example.com/v1"
          />
          <div v-if="!isCustom && form.preset" class="ak-form-tip">
            预设地址，如需修改请选"自定义接口"
          </div>
        </el-form-item>

        <!-- API Key -->
        <el-form-item label="API Key">
          <el-input
            v-model="form.api_key"
            type="password"
            show-password
            placeholder="粘贴 API Key（可留空，稍后配置）"
          />
        </el-form-item>

        <!-- 启用 -->
        <el-form-item label="启用">
          <el-switch v-model="form.enabled" />
        </el-form-item>

      </el-form>

      <template #footer>
        <el-button @click="showDialog = false">取消</el-button>
        <el-button
          type="primary"
          :loading="submitting"
          :disabled="!form.preset"
          @click="submitAdd"
        >
          添加
        </el-button>
      </template>
    </el-dialog>

  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'
import { aiKeyApi, type AIKeyConfig } from '@/api/ai'

// ── 预设厂商列表 ──────────────────────────────────────────────
const PRESETS = [
  { value: 'openai',    label: 'OpenAI',                  provider: 'openai',    base_url: 'https://api.openai.com/v1',                         color: '#10a37f' },
  { value: 'anthropic', label: 'Anthropic (Claude)',       provider: 'anthropic', base_url: 'https://api.anthropic.com',                         color: '#d4805a' },
  { value: 'qwen',      label: '通义千问 (Qwen)',           provider: 'qwen',      base_url: 'https://dashscope.aliyuncs.com/compatible-mode/v1', color: '#5664f5' },
  { value: 'deepseek',  label: 'DeepSeek',                 provider: 'deepseek',  base_url: 'https://api.deepseek.com/v1',                       color: '#4b7bf4' },
  { value: 'gemini',    label: 'Google Gemini',            provider: 'gemini',    base_url: 'https://generativelanguage.googleapis.com/v1beta',  color: '#4285f4' },
  { value: 'moonshot',  label: '月之暗面 (Moonshot)',       provider: 'moonshot',  base_url: 'https://api.moonshot.cn/v1',                        color: '#8b5cf6' },
  { value: 'glm',       label: '智谱 AI (GLM)',             provider: 'glm',       base_url: 'https://open.bigmodel.cn/api/paas/v4',             color: '#2563eb' },
  { value: 'doubao',    label: '字节豆包 (Doubao)',          provider: 'doubao',    base_url: 'https://ark.cn-beijing.volces.com/api/v3',          color: '#f59e0b' },
  { value: 'mistral',   label: 'Mistral AI',               provider: 'mistral',   base_url: 'https://api.mistral.ai/v1',                         color: '#f87c56' },
  { value: 'minimax',   label: 'MiniMax',                  provider: 'minimax',   base_url: 'https://api.minimax.io/v1',                         color: '#00d4aa' },
  { value: 'cohere',    label: 'Cohere',                   provider: 'cohere',    base_url: 'https://api.cohere.com/v1',                         color: '#39594d' },
  { value: 'custom',    label: '自定义接口',                provider: '',          base_url: '',                                                  color: '#666688' },
]

// ── 颜色 ──────────────────────────────────────────────────────
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

// ── 行数据类型（含前端临时状态） ──────────────────────────────
type KeyRow = AIKeyConfig & { _saving?: boolean; _saved?: boolean }

// ── 状态 ─────────────────────────────────────────────────────
const loading    = ref(false)
const keys       = ref<KeyRow[]>([])
const showDialog = ref(false)
const submitting = ref(false)
const formRef    = ref<FormInstance>()

type TestSt = 'idle' | 'testing' | 'valid' | 'invalid'
const testState = ref<Record<string, TestSt>>({})
const testMsg   = ref<Record<string, string>>({})

// ── 对话框表单 ────────────────────────────────────────────────
const defaultForm = () => ({
  preset:   '',
  provider: '',
  name:     '',
  api_key:  '',
  base_url: '',
  enabled:  false,
})
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

// ── 数据加载 ──────────────────────────────────────────────────
async function loadKeys() {
  loading.value = true
  try {
    const res = await aiKeyApi.list()
    keys.value = (res.data?.data || []).map((k: AIKeyConfig) => ({ ...k, api_key: '' }))
  } catch {
    keys.value = []
  } finally {
    loading.value = false
  }
}

// ── 保存 Key ─────────────────────────────────────────────────
async function saveKey(row: KeyRow) {
  if (!row.api_key) return
  row._saving = true
  try {
    await aiKeyApi.update({
      provider: row.provider,
      name: row.name,
      enabled: row.enabled,
      priority: row.priority,
      api_key: row.api_key,
      base_url: row.base_url,
    })
    row.has_key  = true
    row.api_key  = ''
    row._saved   = true
    testState.value[row.provider] = 'idle'
    setTimeout(() => { row._saved = false }, 2200)
  } catch {
    ElMessage.error('保存失败')
  } finally {
    row._saving = false
  }
}

// ── 开关 ──────────────────────────────────────────────────────
async function toggle(row: KeyRow) {
  try {
    await aiKeyApi.update({
      provider: row.provider,
      name: row.name,
      enabled: row.enabled,
      priority: row.priority,
      base_url: row.base_url,
    })
    ElMessage.success(row.enabled ? '已启用' : '已禁用')
  } catch {
    ElMessage.error('操作失败')
    row.enabled = !row.enabled
  }
}

// ── 删除 ──────────────────────────────────────────────────────
async function remove(provider: string) {
  try {
    await ElMessageBox.confirm(`确认删除 "${provider}"？`, '删除确认', {
      type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消',
    })
    await aiKeyApi.remove(provider)
    ElMessage.success('已删除')
    await loadKeys()
  } catch (e: any) {
    if (e !== 'cancel') ElMessage.error('删除失败')
  }
}

// ── 验证 Key ─────────────────────────────────────────────────
async function testKey(row: KeyRow) {
  if (!row.has_key && !row.api_key) {
    ElMessage.warning('请先输入 API Key')
    return
  }
  testState.value[row.provider] = 'testing'
  testMsg.value[row.provider]   = ''
  try {
    const res = await aiKeyApi.test(row.provider, row.api_key || undefined, row.base_url)
    const { valid, message } = res.data ?? {}
    testState.value[row.provider] = valid ? 'valid' : 'invalid'
    testMsg.value[row.provider]   = message || (valid ? '有效' : '无效')
    valid
      ? ElMessage.success(`${row.name} — Key 有效`)
      : ElMessage.error(`${row.name} — ${message || '无效'}`)
  } catch {
    testState.value[row.provider] = 'invalid'
    testMsg.value[row.provider]   = '请求失败，请检查后端'
  }
}

// ── 提交新增 ──────────────────────────────────────────────────
async function submitAdd() {
  if (!formRef.value) return
  if (!await formRef.value.validate().catch(() => false)) return

  const finalProvider = isCustom.value ? form.value.provider : form.value.provider
  if (keys.value.some(k => k.provider === finalProvider)) {
    ElMessage.warning(`"${finalProvider}" 已存在`)
    return
  }

  submitting.value = true
  try {
    await aiKeyApi.update({
      provider: finalProvider,
      name:     form.value.name,
      enabled:  form.value.enabled,
      priority: 99,
      api_key:  form.value.api_key || undefined,
      base_url: form.value.base_url || undefined,
    })
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
/* ── 整体 ──────────────────────────── */
.ak-page {
  display: flex;
  flex-direction: column;
  gap: 12px;
  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', sans-serif;
}

/* ── 页头 ──────────────────────────── */
.ak-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.ak-header-left { display: flex; align-items: center; gap: 8px; }
.ak-title { font-size: 15px; font-weight: 700; color: #dde0f0; }
.ak-badge {
  font-size: 11px; padding: 1px 7px; border-radius: 20px;
  background: #18182a; border: 1px solid #28283e; color: #5050a0;
}
.ak-add-btn {
  display: flex; align-items: center; gap: 7px;
  padding: 6px 14px; font-size: 12.5px; cursor: pointer;
  background: #15151e; border: 1px solid #2a2a40; border-radius: 7px;
  color: #7070aa; transition: all 0.15s;
}
.ak-add-btn:hover { background: #1e1e30; border-color: #5555aa; color: #bbbbee; }

/* ── 列表容器 ──────────────────────── */
.ak-list { display: flex; flex-direction: column; gap: 0; }

/* ── 卡片 ──────────────────────────── */
.ak-card {
  position: relative;
  display: flex;
  align-items: stretch;
  background: #111118;
  border: 1px solid #1c1c28;
  border-radius: 10px;
  overflow: hidden;
  margin-bottom: 8px;
  transition: border-color 0.2s, box-shadow 0.2s;
}
.ak-card:hover { border-color: #26263a; box-shadow: 0 2px 14px rgba(0,0,0,0.35); }
.ak-card.state-valid   { border-color: #1a3824; }
.ak-card.state-invalid { border-color: #381a1a; }

/* 左侧彩条 */
.ak-stripe { width: 3px; background: var(--accent); flex-shrink: 0; opacity: 0.8; }

/* 图标 */
.ak-icon {
  width: 34px; height: 34px; border-radius: 8px;
  display: flex; align-items: center; justify-content: center;
  font-size: 14px; font-weight: 800; color: rgba(255,255,255,0.88);
  flex-shrink: 0; align-self: center; margin: 0 12px 0 12px;
}

/* 主体 */
.ak-body {
  flex: 1; padding: 11px 14px 11px 0;
  display: flex; flex-direction: column; gap: 8px; min-width: 0;
}
.ak-row { display: flex; align-items: center; }

/* 行1 */
.ak-row-title { justify-content: space-between; }
.ak-names { display: flex; align-items: baseline; gap: 7px; min-width: 0; flex: 1; }
.ak-name { font-size: 13.5px; font-weight: 600; color: #d0d0e8; white-space: nowrap; }
.ak-pid {
  font-size: 10.5px; color: #40405a;
  font-family: 'JetBrains Mono', 'SF Mono', monospace;
  padding: 1px 5px; background: #16162a; border: 1px solid #22223a; border-radius: 4px;
}
.ak-row-title-right { display: flex; align-items: center; gap: 10px; flex-shrink: 0; }
.ak-del-btn {
  width: 26px; height: 26px; display: flex; align-items: center; justify-content: center;
  background: transparent; border: 1px solid transparent; border-radius: 5px;
  color: #383850; cursor: pointer; transition: all 0.12s; padding: 0;
}
.ak-del-btn:hover { border-color: #6a2a2a; color: #c05050; background: #1c0d0d; }

/* 行2：Key 输入 */
.ak-row-key { gap: 7px; }
.ak-dot {
  width: 7px; height: 7px; border-radius: 50%;
  background: #222235; flex-shrink: 0; transition: background 0.3s, box-shadow 0.3s;
}
.ak-dot.on { background: var(--accent); box-shadow: 0 0 6px var(--accent); }

.ak-key-input { flex: 1; }
.ak-key-input :deep(.el-input__wrapper) {
  background: #161620 !important; box-shadow: none !important;
  border: 1px solid #20203a !important;
}
.ak-key-input :deep(.el-input__wrapper:hover) { border-color: #30304a !important; }
.ak-key-input :deep(.el-input__wrapper.is-focus) { border-color: var(--accent) !important; }
.ak-key-input :deep(.el-input__inner) {
  color: #9090b8; font-family: 'JetBrains Mono', monospace; font-size: 12px;
}

/* 保存按钮 */
.ak-save-btn {
  flex-shrink: 0;
  padding: 4px 11px; font-size: 12px; border-radius: 5px; cursor: pointer;
  border: 1px solid #20203a; background: #14141e; color: #38385a;
  transition: all 0.15s;
}
.ak-save-btn.active {
  border-color: var(--accent); color: var(--accent);
  background: color-mix(in srgb, var(--accent) 12%, transparent);
}
.ak-save-btn.saved {
  border-color: #1a4a2a; background: #0d1e14; color: #3d9a5a;
}
.ak-save-btn:disabled { opacity: 0.35; cursor: not-allowed; }

/* 行3：Base URL */
.ak-row-url { gap: 5px; }
.ak-url-text {
  font-size: 10.5px; color: #333350;
  font-family: 'JetBrains Mono', monospace;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}

/* 行4：验证 */
.ak-row-test { justify-content: space-between; }
.ak-test-result {
  font-size: 11.5px; color: #2a2a40; display: flex; align-items: center; gap: 5px; min-height: 20px;
}
.ak-test-result.valid   { color: #3a8a52; }
.ak-test-result.invalid { color: #8a3a3a; }
.ak-invalid-wrap { display: flex; align-items: center; gap: 5px; cursor: help; }
.rdot { width: 6px; height: 6px; border-radius: 50%; display: inline-block; flex-shrink: 0; }
.rdot.valid   { background: #3a8a52; box-shadow: 0 0 6px rgba(58,138,82,.6); }
.rdot.invalid { background: #8a3a3a; box-shadow: 0 0 6px rgba(138,58,58,.6); }

/* 验证按钮 */
.ak-test-btn {
  padding: 4px 12px; font-size: 11.5px; border-radius: 5px; cursor: pointer;
  border: 1px solid #20203a; background: #12121c; color: #555588;
  transition: all 0.15s;
}
.ak-test-btn:hover:not(:disabled) {
  background: #1a1a2c; border-color: var(--accent); color: var(--accent);
}
.ak-test-btn.testing  { color: #444488; cursor: wait; }
.ak-test-btn.valid    { border-color: #1a3824; background: #0a1810; color: #3a8a52; }
.ak-test-btn.invalid  { border-color: #3a1a1a; background: #160a0a; color: #8a4040; }
.ak-test-btn:disabled { opacity: 0.4; }

/* 旋转 */
.ak-spinner { display: inline-block; animation: akSpin 0.9s linear infinite; }
@keyframes akSpin { to { transform: rotate(360deg); } }

/* 空状态 */
.ak-empty {
  text-align: center; padding: 56px 0; color: #28284a;
}
.ak-empty-icon { font-size: 36px; opacity: 0.3; margin-bottom: 10px; }

/* 过渡动画 */
.ak-slide-enter-active { transition: all 0.25s ease; }
.ak-slide-leave-active { transition: all 0.2s ease; }
.ak-slide-enter-from  { opacity: 0; transform: translateY(-8px); }
.ak-slide-leave-to    { opacity: 0; transform: translateY(-4px); }

/* ── 对话框 ──────────────────────────── */
.ak-form :deep(.el-form-item__label) { color: #888899; font-size: 12.5px; }

/* 预设选项 */
.preset-option {
  display: flex; align-items: center; gap: 8px; width: 100%;
}
.preset-dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
.preset-url {
  margin-left: auto; font-size: 10.5px; color: #44445a;
  font-family: 'JetBrains Mono', monospace; overflow: hidden;
  text-overflow: ellipsis; white-space: nowrap; max-width: 200px;
}
.ak-form-tip { font-size: 11px; color: #44445a; margin-top: 4px; }
</style>
