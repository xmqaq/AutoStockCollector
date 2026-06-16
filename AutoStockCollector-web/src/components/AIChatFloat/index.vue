<template>
  <div class="ai-chat-fab" @click="toggleChat">
    <el-badge :value="unreadCount" :hidden="unreadCount === 0" :max="99">
      <div :class="['fab-button', { 'fab-active': showChat }]">
        <el-icon :size="24"><ChatDotRound /></el-icon>
        <span v-if="!showChat" class="fab-label">AI助手</span>
      </div>
    </el-badge>
  </div>

  <el-drawer
    v-model="showChat"
    title="AI助手"
    direction="rtl"
    size="420px"
    :before-close="handleClose"
    class="ai-chat-drawer"
  >
    <div class="chat-container">
      <div class="toolbar">
        <el-select v-model="selectedAgent" placeholder="选择分析师" size="small" class="agent-select">
          <el-option
            v-for="agent in agents"
            :key="agent.id"
            :label="agent.name"
            :value="agent.id"
          >
            <div class="agent-option">
              <span>{{ agent.name }}</span>
              <span class="agent-desc">{{ agent.description }}</span>
            </div>
          </el-option>
        </el-select>
        <el-tag
          v-if="stockContext"
          size="small"
          type="success"
          class="stock-context-tag"
          closable
          @close="clearStockContext"
        >
          {{ stockName || stockContext }}
        </el-tag>
      </div>

      <div class="messages" ref="messagesRef">
        <div v-if="currentAgentInfo" class="agent-welcome">
          <el-icon :size="20"><UserFilled /></el-icon>
          <div class="welcome-content">
            <div class="welcome-title">{{ currentAgentInfo.name }}</div>
            <div class="welcome-desc">{{ currentAgentInfo.description }}</div>
          </div>
        </div>

        <div
          v-for="(msg, idx) in messages"
          :key="idx"
          :class="['message', msg.role]"
        >
          <div class="message-avatar">
            <el-icon v-if="msg.role === 'user'" :size="16"><User /></el-icon>
            <el-icon v-else :size="16"><MagicStick /></el-icon>
          </div>
          <div class="message-content">
            <div class="message-text" v-html="formatMessage(msg.content)"></div>
            <div class="message-time">{{ msg.time }}</div>
          </div>
        </div>
        <div v-if="loading" class="message assistant">
          <div class="message-avatar">
            <el-icon :size="16"><MagicStick /></el-icon>
          </div>
          <div class="message-content">
            <div class="message-text typing">
              <span class="dot"></span>
              <span class="dot"></span>
              <span class="dot"></span>
            </div>
          </div>
        </div>
      </div>

      <div class="quick-actions">
        <el-button
          v-for="action in quickActions"
          :key="action.label"
          size="small"
          @click="sendQuickAction(action.prompt)"
        >
          {{ action.label }}
        </el-button>
      </div>

      <div class="model-selector">
        <el-select
          v-model="selectedProvider"
          placeholder="选择服务商"
          size="small"
          class="provider-select"
        >
          <el-option
            v-for="key in enabledProviders"
            :key="key.provider"
            :label="key.name"
            :value="key.provider"
          >
            <div class="provider-option">
              <span>{{ key.name }}</span>
              <el-tag v-if="key.model" type="info" size="small">{{ key.model }}</el-tag>
            </div>
          </el-option>
        </el-select>
      </div>

      <div class="input-area">
        <el-input
          v-model="inputText"
          type="textarea"
          :rows="2"
          placeholder="输入您的问题..."
          resize="none"
          @keydown.enter.ctrl="handleSend"
        />
        <div class="input-actions">
          <el-button @click="clearChat" size="small" text>清空</el-button>
          <el-button type="primary" @click="handleSend" :loading="loading" :disabled="!inputText.trim()">
            发送
          </el-button>
        </div>
      </div>
    </div>
  </el-drawer>
</template>

<script setup lang="ts">
import { ref, nextTick, computed, watch, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { ChatDotRound, MagicStick, User, UserFilled } from '@element-plus/icons-vue'
import { aiAgentApi, aiKeyApi, type AIAgent, type AIKeyConfig } from '@/api/ai'
import { stockApi } from '@/api/stock'
import { sanitizeHtml } from '@/utils/markdown'

interface Message {
  role: 'user' | 'assistant'
  content: string
  time: string
}

const showChat = ref(false)
const inputText = ref('')
const messages = ref<Message[]>([])
const loading = ref(false)
const messagesRef = ref<HTMLElement>()
const unreadCount = ref(0)
const agents = ref<AIAgent[]>([])
const selectedAgent = ref('')
const aiKeys = ref<AIKeyConfig[]>([])
const selectedProvider = ref('')

const route = useRoute()
const stockName = ref('')

const stockContext = computed(() => (route.query.code as string) || '')

watch(stockContext, async (code) => {
  if (!code) {
    stockName.value = ''
    return
  }
  try {
    const res = await stockApi.getStockInfo(code)
    stockName.value = res.data?.data?.name || code
  } catch {
    stockName.value = code
  }
}, { immediate: true })

const enabledProviders = computed(() => {
  return aiKeys.value.filter(k => k.enabled && k.has_key)
})

const selectedModel = computed(() => {
  const provider = aiKeys.value.find(k => k.provider === selectedProvider.value)
  return provider?.model || ''
})

const currentAgentInfo = computed(() => {
  return agents.value.find(a => a.id === selectedAgent.value)
})

const quickActions = computed(() => {
  if (stockContext.value) {
    return [
      { label: 'K线走势', prompt: '分析最近的K线走势和关键技术信号' },
      { label: '资金动向', prompt: '分析主力资金流入流出情况' },
      { label: '基本面', prompt: '评估基本面质量和当前估值水平' },
      { label: '风险提示', prompt: '有哪些值得关注的投资风险？' },
    ]
  }
  return [
    { label: '大盘分析', prompt: '分析一下今天的大盘走势' },
    { label: '选股推荐', prompt: '帮我推荐几只值得关注的股票' },
    { label: '风险提示', prompt: '当前市场有什么风险需要注意？' },
  ]
})

async function loadAgents() {
  try {
    const res = await aiAgentApi.list()
    if (res.data?.data) {
      agents.value = res.data.data.filter((a: AIAgent) => a.enabled)
      if (agents.value.length > 0 && !selectedAgent.value) {
        selectedAgent.value = agents.value[0].id
      }
    }
  } catch (e) {
    console.error('加载Agent列表失败:', e)
  }
}

async function loadAIKeys() {
  try {
    const res = await aiKeyApi.list()
    if (res.data?.data) {
      aiKeys.value = res.data.data
      const enabledKeys = aiKeys.value.filter(k => k.enabled && k.has_key)
      if (enabledKeys.length > 0 && !selectedProvider.value) {
        selectedProvider.value = enabledKeys[0].provider
      }
    }
  } catch (e) {
    console.error('加载AI Key列表失败:', e)
  }
}

function toggleChat() {
  showChat.value = !showChat.value
  if (showChat.value) {
    unreadCount.value = 0
    if (agents.value.length === 0) {
      loadAgents()
    }
    if (aiKeys.value.length === 0) {
      loadAIKeys()
    }
  }
}

function handleClose(done: () => void) {
  showChat.value = false
  done()
}

function formatMessage(content: string): string {
  return sanitizeHtml(content
    .replace(/\\n/g, '<br>')
    .replace(/\n/g, '<br>')
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    .replace(/`(.*?)`/g, '<code>$1</code>'))
}

function getTime(): string {
  return new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
}

async function handleSend() {
  const text = inputText.value.trim()
  if (!text || loading.value) return

  messages.value.push({ role: 'user', content: text, time: getTime() })
  inputText.value = ''
  loading.value = true
  scrollToBottom()

  const history = messages.value
    .slice(0, -1)
    .slice(-10)
    .map(m => ({ role: m.role, content: m.content }))

  await streamAgentChat({
    message: text,
    agent_id: selectedAgent.value || undefined,
    stock_code: stockContext.value || undefined,
    history,
    provider: selectedProvider.value || undefined,
  })
}

interface AgentChatParams {
  message: string
  agent_id?: string
  stock_code?: string
  history?: Array<{ role: string; content: string }>
  provider?: string
}

async function streamAgentChat(params: AgentChatParams) {
  const msgIndex = messages.value.length
  messages.value.push({ role: 'assistant', content: '', time: getTime() })
  scrollToBottom()

  try {
    const response = await fetch('/api/v1/ai/agent-chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(params),
    })

    if (!response.ok || !response.body) {
      messages.value[msgIndex].content = '请求失败，请稍后重试'
      return
    }

    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() ?? ''
      for (const line of lines) {
        if (!line.startsWith('data: ')) continue
        try {
          const evt = JSON.parse(line.slice(6))
          if (evt.type === 'content' && evt.data) {
            messages.value[msgIndex].content += evt.data
            scrollToBottom()
          } else if (evt.type === 'error' && evt.data) {
            messages.value[msgIndex].content = `错误：${evt.data}`
          }
        } catch {
          // 忽略不完整 SSE 行
        }
      }
    }

    if (!messages.value[msgIndex].content) {
      messages.value[msgIndex].content = '抱歉，AI助手暂时无法回复'
    }
  } catch (e: any) {
    messages.value[msgIndex].content = `请求失败: ${e.message || '请稍后重试'}`
  } finally {
    loading.value = false
    scrollToBottom()
  }
}

async function sendQuickAction(prompt: string) {
  inputText.value = prompt
  await handleSend()
}

function scrollToBottom() {
  nextTick(() => {
    if (messagesRef.value) {
      messagesRef.value.scrollTop = messagesRef.value.scrollHeight
    }
  })
}

function clearChat() {
  messages.value = []
}

function clearStockContext() {
  const query = { ...route.query }
  delete query.code
  import('@/router/index').then(({ default: router }) =>
    router.replace({ query })
  )
}

onMounted(() => {
  loadAgents()
  loadAIKeys()
})
</script>

<style scoped>
.ai-chat-fab {
  position: fixed;
  right: 24px;
  bottom: 24px;
  z-index: 1000;
}

.fab-button {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 14px 18px;
  background: linear-gradient(135deg, var(--brand-500) 0%, var(--brand-700) 100%);
  border-radius: 30px;
  cursor: pointer;
  box-shadow: 0 8px 24px -6px rgba(99, 102, 241, 0.5);
  transition: all 0.3s cubic-bezier(0.34, 1.56, 0.64, 1);
  color: #fff;
  backdrop-filter: blur(10px);
}

.fab-button:hover {
  transform: translateY(-4px) scale(1.02);
  box-shadow: 0 12px 28px -6px rgba(99, 102, 241, 0.6);
}

.fab-button.fab-active {
  background: linear-gradient(135deg, var(--color-success) 0%, #059669 100%);
  box-shadow: 0 8px 24px -6px rgba(16, 185, 129, 0.5);
  transform: scale(0.95);
}

.fab-label {
  font-size: 15px;
  font-weight: 600;
  letter-spacing: 0.02em;
}

.chat-container {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--bg-overlay);
  backdrop-filter: blur(24px);
  -webkit-backdrop-filter: blur(24px);
}

.toolbar {
  display: flex;
  gap: 12px;
  padding: 16px 20px;
  background: rgba(255, 255, 255, 0.02);
  border-bottom: 1px solid var(--border-color);
  backdrop-filter: blur(10px);
  z-index: 2;
}

.agent-select {
  flex: 1;
}

.stock-context-tag {
  flex-shrink: 0;
  max-width: 120px;
  overflow: hidden;
  text-overflow: ellipsis;
  border-radius: var(--radius-sm);
  background: var(--tint-success-bg);
  border: none;
}

.agent-option {
  display: flex;
  flex-direction: column;
  line-height: 1.3;
}

.agent-desc {
  font-size: 12px;
  color: var(--text-muted);
  margin-top: 4px;
}

.agent-welcome {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 16px;
  background: var(--bg-hover-subtle);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
  margin-bottom: 16px;
}

.agent-welcome .el-icon {
  color: var(--brand-500);
  margin-top: 2px;
}

.welcome-title {
  font-weight: 600;
  color: var(--text-primary);
  font-size: 15px;
  margin-bottom: 4px;
}

.welcome-desc {
  font-size: 13px;
  color: var(--text-secondary);
  line-height: 1.5;
}

.messages {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 20px;
  scroll-behavior: smooth;
}

.message {
  display: flex;
  gap: 12px;
  max-width: 88%;
}

.message.user {
  align-self: flex-end;
  flex-direction: row-reverse;
}

.message.assistant {
  align-self: flex-start;
}

.message-avatar {
  width: 36px;
  height: 36px;
  border-radius: 12px;
  background: var(--bg-soft);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  box-shadow: var(--shadow-sm);
}

.message.user .message-avatar {
  background: linear-gradient(135deg, var(--brand-400), var(--brand-600));
  color: #fff;
}

.message.assistant .message-avatar {
  background: linear-gradient(135deg, var(--color-success), #059669);
  color: #fff;
}

.message-content {
  background: var(--bg-elevated);
  padding: 14px 18px;
  border-radius: 18px;
  border-top-left-radius: 4px;
  word-break: break-word;
  box-shadow: var(--shadow-sm);
  border: 1px solid var(--border-color);
}

.message.user .message-content {
  background: linear-gradient(135deg, var(--brand-500), var(--brand-700));
  color: #fff;
  border: none;
  border-radius: 18px;
  border-top-right-radius: 4px;
  box-shadow: 0 4px 12px rgba(99, 102, 241, 0.2);
}

.message-text {
  font-size: 14.5px;
  line-height: 1.6;
  white-space: pre-wrap;
  color: var(--text-primary);
}

.message.user .message-text {
  color: #fff;
}

.message-text :deep(code) {
  background: var(--bg-soft);
  padding: 2px 6px;
  border-radius: 6px;
  font-family: var(--font-mono);
  font-size: 13px;
  color: var(--brand-600);
}

.message.user .message-text :deep(code) {
  background: rgba(255, 255, 255, 0.2);
  color: #fff;
}

.message-text :deep(strong) {
  color: var(--brand-600);
  font-weight: 600;
}

.message.user .message-text :deep(strong) {
  color: #fff;
}

.message-time {
  font-size: 11px;
  color: var(--text-muted);
  margin-top: 6px;
  text-align: left;
}

.message.user .message-time {
  color: rgba(255, 255, 255, 0.7);
  text-align: right;
}

.typing {
  display: flex;
  gap: 6px;
  padding: 8px 4px;
}

.typing .dot {
  width: 6px;
  height: 6px;
  background: var(--brand-400);
  border-radius: 50%;
  animation: typing 1.4s infinite ease-in-out both;
}

.typing .dot:nth-child(1) { animation-delay: -0.32s; }
.typing .dot:nth-child(2) { animation-delay: -0.16s; }

@keyframes typing {
  0%, 80%, 100% { transform: scale(0); opacity: 0.4; }
  40% { transform: scale(1); opacity: 1; }
}

.quick-actions {
  display: flex;
  gap: 10px;
  padding: 12px 20px;
  flex-wrap: nowrap;
  overflow-x: auto;
  scrollbar-width: none;
}

.quick-actions::-webkit-scrollbar {
  display: none;
}

.quick-actions .el-button {
  border-radius: 20px;
  padding: 8px 16px;
  background: var(--bg-elevated);
  border: 1px solid var(--border-color);
  color: var(--text-secondary);
  white-space: nowrap;
  transition: all 0.2s;
}

.quick-actions .el-button:hover {
  background: var(--bg-hover-subtle);
  color: var(--brand-600);
  border-color: var(--brand-300);
  transform: translateY(-2px);
}

.model-selector {
  display: flex;
  gap: 8px;
  padding: 10px 20px;
  background: rgba(255, 255, 255, 0.02);
  border-top: 1px solid var(--border-color);
}

.provider-select {
  width: 100%;
}

.provider-option {
  display: flex;
  align-items: center;
  gap: 10px;
}

.input-area {
  padding: 16px 20px 24px;
  background: var(--bg-elevated);
  border-top: 1px solid var(--border-color);
  box-shadow: 0 -4px 20px rgba(0, 0, 0, 0.02);
}

.input-area :deep(.el-textarea__inner) {
  border-radius: 12px;
  padding: 12px 16px;
  background: var(--bg-soft);
  border: 1px solid transparent;
  box-shadow: none;
  transition: all 0.2s;
  font-family: var(--font-sans);
}

.input-area :deep(.el-textarea__inner:focus) {
  background: var(--bg-card);
  border: 1px solid var(--brand-400);
  box-shadow: 0 0 0 2px rgba(99, 102, 241, 0.1);
}

.input-actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 16px;
}

.input-actions .el-button--primary {
  border-radius: 8px;
  padding: 8px 24px;
  font-weight: 600;
  background: linear-gradient(135deg, var(--brand-500), var(--brand-600));
  border: none;
}
</style>

<style>
/* 覆盖抽屉全局样式，实现完全的玻璃拟态 */
.ai-chat-drawer {
  background: transparent !important;
  box-shadow: -10px 0 30px rgba(0, 0, 0, 0.1) !important;
}

.ai-chat-drawer .el-drawer__header {
  margin-bottom: 0;
  padding: 20px 24px;
  background: var(--bg-overlay);
  backdrop-filter: blur(24px);
  -webkit-backdrop-filter: blur(24px);
  border-bottom: 1px solid var(--border-color);
}

.ai-chat-drawer .el-drawer__header span {
  color: var(--text-primary);
  font-size: 18px;
  font-weight: 700;
  letter-spacing: -0.02em;
}

.ai-chat-drawer .el-drawer__body {
  padding: 0;
  overflow: hidden;
  background: transparent;
}

.agent-select .el-select-dropdown__item {
  height: auto;
  padding: 10px 14px;
}

.agent-select .el-select-dropdown__item.hover,
.agent-select .el-select-dropdown__item:hover {
  background: var(--bg-hover-subtle);
}
</style>