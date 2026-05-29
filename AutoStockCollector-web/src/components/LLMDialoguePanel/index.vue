<template>
  <div class="llm-dialogue-panel">
    <div class="panel-header">
      <span class="panel-title">
        <el-icon><ChatLineSquare /></el-icon>
        LLM对话详情
      </span>
      <div class="panel-actions">
        <el-button size="small" text @click="toggleExpand">
          {{ isExpanded ? '收起' : '展开' }}
        </el-button>
        <el-button size="small" text @click="copyFullContent">
          <el-icon><CopyDocument /></el-icon>
          复制
        </el-button>
      </div>
    </div>

    <div v-if="isExpanded" class="dialogue-content">
      <div
        v-for="(message, index) in messages"
        :key="index"
        :class="['message-item', message.role]"
      >
        <div class="message-header">
          <div class="message-role">
            <el-icon v-if="message.role === 'user'"><User /></el-icon>
            <el-icon v-else-if="message.role === 'assistant'"><MagicStick /></el-icon>
            <el-icon v-else><Cpu /></el-icon>
            <span>{{ roleLabel(message.role) }}</span>
          </div>
          <div class="message-meta">
            <el-tag v-if="message.model" size="small" type="info">{{ message.model }}</el-tag>
            <span class="message-time" v-if="message.timestamp">
              {{ formatTime(message.timestamp) }}
            </span>
          </div>
        </div>

        <div class="message-body">
          <pre v-if="isJsonMessage(message)" class="json-content">{{ formatJson(message.content) }}</pre>
          <pre v-else class="text-content">{{ message.content }}</pre>
        </div>

        <div class="message-stats" v-if="message.usage">
          <span class="stat-item">
            <el-icon><Document /></el-icon>
            Prompt: {{ message.usage.prompt_tokens }} tokens
          </span>
          <span class="stat-item">
            <el-icon><Tickets /></el-icon>
            Completion: {{ message.usage.completion_tokens }} tokens
          </span>
          <span class="stat-item">
            <el-icon><Clock /></el-icon>
            {{ message.usage.latency || 'N/A' }}
          </span>
        </div>
      </div>

      <div v-if="messages.length === 0" class="empty-state">
        <el-icon size="32"><ChatDotRound /></el-icon>
        <p>暂无对话记录</p>
      </div>
    </div>

    <div v-else class="summary-bar">
      <el-tag size="small" type="info">{{ messages.length }} 条消息</el-tag>
      <span class="summary-text">
        {{ lastUserMessage?.content?.substring(0, 50) || '等待用户输入' }}...
      </span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import {
  ChatLineSquare, CopyDocument, User, MagicStick, Cpu,
  Document, Tickets, Clock, ChatDotRound
} from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'

export interface DialogueMessage {
  role: 'user' | 'assistant' | 'system' | 'tool'
  content: string
  model?: string
  timestamp?: number
  usage?: {
    prompt_tokens?: number
    completion_tokens?: number
    latency?: string
  }
  isJson?: boolean
}

const props = defineProps<{
  messages: DialogueMessage[]
}>()

const isExpanded = ref(true)

const lastUserMessage = computed(() => {
  return [...props.messages].reverse().find(m => m.role === 'user')
})

function roleLabel(role: string): string {
  const labels: Record<string, string> = {
    user: '用户',
    assistant: 'AI助手',
    system: '系统',
    tool: '工具'
  }
  return labels[role] || role
}

function formatTime(timestamp: number): string {
  const date = new Date(timestamp)
  return date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

function isJsonMessage(message: DialogueMessage): boolean {
  if (message.isJson !== undefined) return message.isJson
  try {
    JSON.parse(message.content)
    return true
  } catch {
    return false
  }
}

function formatJson(content: string): string {
  try {
    return JSON.stringify(JSON.parse(content), null, 2)
  } catch {
    return content
  }
}

function toggleExpand() {
  isExpanded.value = !isExpanded.value
}

function copyFullContent() {
  const content = props.messages
    .map(m => `[${roleLabel(m.role)}]\n${m.content}`)
    .join('\n\n---\n\n')

  navigator.clipboard.writeText(content).then(() => {
    ElMessage.success('已复制全部对话内容')
  }).catch(() => {
    ElMessage.error('复制失败')
  })
}
</script>

<style scoped>
.llm-dialogue-panel {
  background: #1f1f1f;
  border: 1px solid #2c2c2c;
  border-radius: 8px;
  overflow: hidden;
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  background: #252525;
  border-bottom: 1px solid #2c2c2c;
}

.panel-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  font-weight: 600;
  color: #e5eaf3;
}

.panel-actions {
  display: flex;
  gap: 8px;
}

.dialogue-content {
  max-height: 400px;
  overflow-y: auto;
  padding: 12px;
}

.message-item {
  margin-bottom: 12px;
  border-radius: 8px;
  overflow: hidden;
  border: 1px solid #2c2c2c;
}

.message-item.user {
  background: rgba(64, 158, 255, 0.05);
  border-color: rgba(64, 158, 255, 0.2);
}

.message-item.assistant {
  background: rgba(103, 194, 58, 0.05);
  border-color: rgba(103, 194, 58, 0.2);
}

.message-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 12px;
  background: rgba(0, 0, 0, 0.2);
  border-bottom: 1px solid #2c2c2c;
}

.message-role {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  font-weight: 500;
  color: #909399;
}

.message-meta {
  display: flex;
  align-items: center;
  gap: 8px;
}

.message-time {
  font-size: 11px;
  color: #606266;
}

.message-body {
  padding: 12px;
}

.json-content, .text-content {
  margin: 0;
  font-family: 'JetBrains Mono', 'SF Mono', monospace;
  font-size: 12px;
  color: #a8b5c1;
  white-space: pre-wrap;
  word-break: break-all;
  line-height: 1.6;
}

.message-stats {
  display: flex;
  gap: 16px;
  padding: 8px 12px;
  background: rgba(0, 0, 0, 0.1);
  border-top: 1px solid #2c2c2c;
}

.stat-item {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 11px;
  color: #606266;
}

.summary-bar {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 16px;
}

.summary-text {
  font-size: 12px;
  color: #909399;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 40px 20px;
  color: #606266;
}

.empty-state p {
  margin: 12px 0 0;
  font-size: 13px;
}
</style>