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
import { aiApi, aiAgentApi, aiKeyApi, type AIAgent, type AIKeyConfig } from '@/api/ai'
import { stockApi } from '@/api/stock'

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

const quickActions = [
  { label: '大盘分析', prompt: '分析一下今天的大盘走势' },
  { label: '选股推荐', prompt: '帮我推荐几只值得关注的股票' },
  { label: '风险提示', prompt: '当前市场有什么风险需要注意？' },
]

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
  return content
    .replace(/\\n/g, '<br>')
    .replace(/\n/g, '<br>')
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    .replace(/`(.*?)`/g, '<code>$1</code>')
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

  const stockCodeMatch = text.match(/(\d{6})/)
  const stockCode = stockCodeMatch ? stockCodeMatch[1] : null

  // 股票代码分析：调用对应 Agent 流式接口
  if (stockCode && selectedAgent.value) {
    await streamAgentAnalyze(selectedAgent.value, stockCode)
  } else {
    await streamChat(text)
  }
}

async function streamChat(text: string) {
  // 构建历史（最多10条，排除刚推入的当前用户消息）
  const history = messages.value
    .slice(0, -1)
    .slice(-10)
    .map(m => ({ role: m.role, content: m.content }))

  const msgIndex = messages.value.length
  messages.value.push({ role: 'assistant', content: '', time: getTime() })
  scrollToBottom()

  try {
    const response = await aiApi.chatStream({
      message: text,
      provider: selectedProvider.value || undefined,
      history,
    })

    if (!response.ok) {
      messages.value[msgIndex].content = '抱歉，AI助手暂时无法回复'
      return
    }

    const reader = response.body!.getReader()
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
          }
        } catch {
          // ignore parse errors on partial lines
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

async function streamAgentAnalyze(agentId: string, stockCode: string) {
  const msgIndex = messages.value.length
  messages.value.push({ role: 'assistant', content: '', time: getTime() })
  scrollToBottom()

  try {
    const response = await fetch(`/api/v1/ai-agents/${agentId}/analyze/stream`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ code: stockCode }),
    })

    if (!response.ok) {
      // 降级到非流式
      const res = await aiAgentApi.analyze(agentId, stockCode)
      messages.value[msgIndex].content = res.data?.data?.content || '分析失败'
      return
    }

    const reader = response.body!.getReader()
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
          }
        } catch {
          // ignore
        }
      }
    }

    if (!messages.value[msgIndex].content) {
      messages.value[msgIndex].content = '分析完成，但未返回内容'
    }
  } catch (e: any) {
    messages.value[msgIndex].content = `分析失败: ${e.message || '请稍后重试'}`
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
  right: 20px;
  bottom: 20px;
  z-index: 1000;
}

.fab-button {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 16px;
  background: linear-gradient(135deg, #409eff 0%, #337ecc 100%);
  border-radius: 24px;
  cursor: pointer;
  box-shadow: 0 4px 12px rgba(64, 158, 255, 0.4);
  transition: all 0.3s ease;
  color: #fff;
}

.fab-button:hover {
  transform: translateY(-2px);
  box-shadow: 0 6px 16px rgba(64, 158, 255, 0.5);
}

.fab-button.fab-active {
  background: linear-gradient(135deg, #67c23a 0%, #529b2e 100%);
  box-shadow: 0 4px 12px rgba(103, 194, 58, 0.4);
}

.fab-label {
  font-size: 14px;
  font-weight: 500;
}

.chat-container {
  display: flex;
  flex-direction: column;
  height: calc(100vh - 60px);
  padding: 0;
}

.toolbar {
  display: flex;
  gap: 8px;
  padding: 12px 16px;
  background: #1a1a1a;
  border-bottom: 1px solid #2c2c2c;
}

.agent-select {
  flex: 1;
  min-width: 120px;
}

.stock-context-tag {
  flex-shrink: 0;
  max-width: 100px;
  overflow: hidden;
  text-overflow: ellipsis;
}

.agent-option {
  display: flex;
  flex-direction: column;
  line-height: 1.2;
}

.agent-desc {
  font-size: 11px;
  color: #909399;
  margin-top: 2px;
}



.agent-welcome {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 16px;
  background: #2c2c2c;
  border-radius: 8px;
  margin-bottom: 8px;
}

.agent-welcome .el-icon {
  color: #409eff;
}

.welcome-title {
  font-weight: 600;
  color: #fff;
  font-size: 14px;
}

.welcome-desc {
  font-size: 12px;
  color: #909399;
  margin-top: 2px;
}

.messages {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.message {
  display: flex;
  gap: 12px;
  max-width: 85%;
}

.message.user {
  align-self: flex-end;
  flex-direction: row-reverse;
}

.message.assistant {
  align-self: flex-start;
}

.message-avatar {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: #2c2c2c;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.message.user .message-avatar {
  background: #409eff;
  color: #fff;
}

.message.assistant .message-avatar {
  background: #67c23a;
  color: #fff;
}

.message-content {
  background: #2c2c2c;
  padding: 12px 16px;
  border-radius: 12px;
  word-break: break-word;
}

.message.user .message-content {
  background: #409eff;
  color: #fff;
}

.message-text {
  font-size: 14px;
  line-height: 1.6;
  white-space: pre-wrap;
}

.message-text :deep(code) {
  background: rgba(0, 0, 0, 0.3);
  padding: 2px 6px;
  border-radius: 4px;
  font-family: monospace;
}

.message-text :deep(strong) {
  color: #409eff;
}

.message.user .message-text :deep(strong) {
  color: #fff;
}

.message-time {
  font-size: 11px;
  color: #909399;
  margin-top: 4px;
}

.message.user .message-time {
  color: rgba(255, 255, 255, 0.6);
  text-align: right;
}

.typing {
  display: flex;
  gap: 4px;
  padding: 8px 0;
}

.typing .dot {
  width: 8px;
  height: 8px;
  background: #909399;
  border-radius: 50%;
  animation: typing 1.4s infinite;
}

.typing .dot:nth-child(2) {
  animation-delay: 0.2s;
}

.typing .dot:nth-child(3) {
  animation-delay: 0.4s;
}

@keyframes typing {
  0%, 60%, 100% {
    transform: translateY(0);
    opacity: 0.4;
  }
  30% {
    transform: translateY(-8px);
    opacity: 1;
  }
}

.quick-actions {
  display: flex;
  gap: 8px;
  padding: 12px 16px;
  border-top: 1px solid #2c2c2c;
  flex-wrap: wrap;
}

.model-selector {
  display: flex;
  gap: 8px;
  padding: 8px 16px;
  background: #1a1a1a;
  border-top: 1px solid #2c2c2c;
}

.provider-select {
  width: 100%;
}

.provider-option {
  display: flex;
  align-items: center;
  gap: 8px;
}

.input-area {
  padding: 16px;
  border-top: 1px solid #2c2c2c;
  background: #1a1a1a;
}

.input-actions {
  display: flex;
  justify-content: space-between;
  margin-top: 12px;
}
</style>

<style>
.ai-chat-drawer .el-drawer__header {
  margin-bottom: 0;
  padding: 16px 20px;
  background: #1a1a1a;
  border-bottom: 1px solid #2c2c2c;
}

.ai-chat-drawer .el-drawer__header span {
  color: #e5eaf3;
  font-size: 16px;
  font-weight: 600;
}

.ai-chat-drawer .el-drawer__body {
  padding: 0;
}

.agent-select .el-select-dropdown__item {
  height: auto;
  padding: 8px 12px;
}

.agent-select .el-select-dropdown__item.hover,
.agent-select .el-select-dropdown__item:hover {
  background: #2c2c2c;
}
</style>