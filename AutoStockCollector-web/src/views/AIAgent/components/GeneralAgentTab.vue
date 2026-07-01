<template>
  <div class="general-agent-tab">
    <div class="toolbar">
      <el-button type="primary" @click="openAddDialog">
        <el-icon><Plus /></el-icon> 添加 Agent
      </el-button>
    </div>

    <div v-loading="loading" class="agent-grid">
      <el-empty v-if="agents.length === 0 && !loading" description="暂无通用 Agent" />
      
      <el-row :gutter="20">
        <el-col :xs="24" :sm="12" :md="8" :lg="6" v-for="agent in agents" :key="agent.id" class="grid-col">
          <div class="agent-card">
            <div class="card-header">
              <div class="agent-title">
                <div :class="['status-dot', agent.enabled ? 'is-enabled' : 'is-disabled']"></div>
                <span class="name">{{ agent.name }}</span>
              </div>
              <el-tag size="small" type="warning" effect="light" class="role-tag">{{ agent.role }}</el-tag>
            </div>
            
            <div class="card-body">
              <p class="description" :title="agent.description">{{ agent.description || '暂无描述' }}</p>
              
              <div class="params-row">
                <div class="param-item">
                  <span class="label">温度</span>
                  <span class="value">{{ agent.temperature }}</span>
                </div>
                <div class="param-item">
                  <span class="label">Token</span>
                  <span class="value">{{ agent.max_tokens }}</span>
                </div>
                <div class="param-item">
                  <span class="label">优先级</span>
                  <span class="value">{{ agent.priority }}</span>
                </div>
              </div>
              <div class="skills-row" v-if="agent.skills && agent.skills.length">
                <el-tag v-for="s in agent.skills" :key="s" size="small" type="info" effect="plain" class="skill-tag">
                  {{ s }}
                </el-tag>
              </div>
            </div>

            <div class="card-footer">
              <el-button link type="primary" @click="openEditDialog(agent)">
                <el-icon><Edit /></el-icon> 编辑
              </el-button>
              <el-button link type="success" @click="testAgent(agent)">
                <el-icon><ChatDotRound /></el-icon> 测试
              </el-button>
              <el-button link type="danger" @click="deleteAgent(agent)">
                <el-icon><Delete /></el-icon> 删除
              </el-button>
            </div>
          </div>
        </el-col>
      </el-row>
    </div>

    <!-- Add/Edit Dialog -->
    <el-dialog
      v-model="showDialog"
      :title="isEdit ? '编辑 Agent' : '添加 Agent'"
      width="700px"
      @close="handleDialogClose"
      destroy-on-close
    >
      <el-form :model="form" label-width="100px" size="default">
        <el-form-item label="Agent ID" required>
          <el-input v-model="form.id" :disabled="isEdit" placeholder="如: market_analyst" />
        </el-form-item>
        <el-form-item label="名称" required>
          <el-input v-model="form.name" placeholder="如: 市场分析师" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="form.description" placeholder="简短描述此 Agent 的职责" />
        </el-form-item>
        <el-form-item label="角色标识" required>
          <el-input v-model="form.role" placeholder="如: market_analyst" />
        </el-form-item>
        <el-form-item label="系统提示词" required>
          <el-input
            v-model="form.system_prompt"
            type="textarea"
            :rows="6"
            placeholder="定义此 Agent 的角色和行为规则..."
          />
        </el-form-item>
        <el-form-item label="技能绑定">
          <el-select
            v-model="form.skills"
            multiple
            collapse-tags
            collapse-tags-tooltip
            filterable
            placeholder="选择要注入该 Agent system_prompt 的技能（可选）"
            style="width: 100%"
          >
            <el-option
              v-for="s in skillOptions"
              :key="s.skill_name || s.name"
              :label="s.name + (s.description ? ' - ' + s.description : '')"
              :value="s.skill_name || s.name"
            />
          </el-select>
          <div class="skill-hint">绑定的技能正文会在分析时拼接到 system_prompt 末尾（单技能截断 2000 字符，总计 4000 字符）</div>
        </el-form-item>
        <el-row :gutter="20">
          <el-col :span="8">
            <el-form-item label="温度">
              <el-input-number v-model="form.temperature" :min="0" :max="2" :step="0.1" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="最大Token">
              <el-input-number v-model="form.max_tokens" :min="100" :max="8000" :step="100" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="优先级">
              <el-input-number v-model="form.priority" :min="1" :max="100" style="width: 100%" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="启用">
          <el-switch v-model="form.enabled" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showDialog = false">取消</el-button>
        <el-button type="primary" @click="saveAgent" :loading="saving">保存</el-button>
      </template>
    </el-dialog>

    <!-- Test Drawer (Chat Bubble Style) -->
    <el-drawer
      v-model="showTestDialog"
      title="Agent 测试"
      size="500px"
      direction="rtl"
      destroy-on-close
    >
      <div class="test-drawer-content">
        <div class="chat-history">
          <!-- 模拟用户消息 -->
          <div class="chat-message user-message" v-if="testResult || testing">
            <div class="bubble">
              <div class="code-badge" v-if="testCode">{{ testCode }}</div>
              {{ testMessage }}
            </div>
          </div>
          
          <!-- 模拟 AI 回复 -->
          <div class="chat-message ai-message" v-if="testing || testResult">
            <div class="bubble">
              <div v-if="testing" class="typing-indicator">
                <span></span><span></span><span></span>
              </div>
              <div v-else class="result-content" v-html="formatResult(testResult)"></div>
            </div>
          </div>
          
          <div v-if="!testing && !testResult" class="empty-chat">
            <el-icon :size="40" color="var(--text-faint)"><ChatLineRound /></el-icon>
            <p>输入问题开始测试 Agent</p>
          </div>
        </div>

        <div class="chat-input-area">
          <el-input v-model="testCode" placeholder="股票代码 (选填,如 SH600519)" size="small" class="code-input" />
          <div class="input-with-button">
            <el-input
              v-model="testMessage"
              type="textarea"
              :rows="3"
              resize="none"
              placeholder="请输入测试问题..."
              @keyup.enter.exact.prevent="runTest"
            />
            <el-button type="primary" class="send-btn" @click="runTest" :loading="testing" :disabled="!testMessage.trim()">
              <el-icon><Position /></el-icon>
            </el-button>
          </div>
        </div>
      </div>
    </el-drawer>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { Plus, Edit, ChatDotRound, Delete, ChatLineRound, Position } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { aiAgentApi, skillApi, type AIAgent } from '@/api/ai'
import { sanitizeHtml } from '@/utils/markdown'

const loading = ref(false)
const agents = ref<AIAgent[]>([])
const skillOptions = ref<any[]>([])

const showDialog = ref(false)
const isEdit = ref(false)
const saving = ref(false)

const showTestDialog = ref(false)
const testing = ref(false)
const testMessage = ref('')
const testCode = ref('')
const testResult = ref('')
const testAgentId = ref('')

const defaultForm = (): Partial<AIAgent> => ({
  id: '',
  name: '',
  description: '',
  role: '',
  system_prompt: '',
  temperature: 0.7,
  max_tokens: 2000,
  priority: 99,
  enabled: true,
  skills: [],
})

const form = ref<Partial<AIAgent>>(defaultForm())

async function loadSkills() {
  try {
    const res = await skillApi.list()
    skillOptions.value = res.data?.data || res.data || []
  } catch {
    skillOptions.value = []
  }
}

async function loadAgents() {
  loading.value = true
  try {
    const res = await aiAgentApi.list()
    agents.value = res.data?.data || []
  } catch {
    ElMessage.error('加载 Agent 列表失败')
  } finally {
    loading.value = false
  }
}

function openAddDialog() {
  isEdit.value = false
  form.value = defaultForm()
  showDialog.value = true
}

function openEditDialog(agent: AIAgent) {
  isEdit.value = true
  form.value = { ...agent, skills: agent.skills || [] }
  showDialog.value = true
}

function handleDialogClose() {
  form.value = defaultForm()
}

async function saveAgent() {
  if (!form.value.id || !form.value.name || !form.value.role || !form.value.system_prompt) {
    ElMessage.warning('请填写必填项')
    return
  }

  saving.value = true
  try {
    if (isEdit.value) {
      await aiAgentApi.update(form.value.id!, form.value)
      ElMessage.success('更新成功')
    } else {
      await aiAgentApi.create(form.value)
      ElMessage.success('创建成功')
    }
    showDialog.value = false
    await loadAgents()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.error || '保存失败')
  } finally {
    saving.value = false
  }
}

async function deleteAgent(agent: AIAgent) {
  try {
    await ElMessageBox.confirm(`确定要删除 Agent "${agent.name}" 吗？`, '删除确认', {
      confirmButtonText: '删除',
      cancelButtonText: '取消',
      type: 'warning',
    })
    await aiAgentApi.delete(agent.id)
    ElMessage.success('删除成功')
    await loadAgents()
  } catch {
    // cancelled
  }
}

function testAgent(agent: AIAgent) {
  testAgentId.value = agent.id
  testMessage.value = `请分析这只股票的${agent.name}要点`
  testCode.value = ''
  testResult.value = ''
  showTestDialog.value = true
}

async function runTest() {
  if (!testMessage.value.trim()) return
  testing.value = true
  testResult.value = ''
  try {
    const res = await aiAgentApi.test(testAgentId.value, testMessage.value, testCode.value)
    testResult.value = res.data?.data?.content || ''
    if (!testResult.value) {
      ElMessage.warning('未获取到回复')
    }
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.error || '测试失败')
  } finally {
    testing.value = false
  }
}

function formatResult(text: string): string {
  return sanitizeHtml(text
    .replace(/\n/g, '<br>')
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>'))
}

onMounted(() => {
  loadAgents()
  loadSkills()
})
</script>

<style scoped>
.general-agent-tab {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.toolbar {
  display: flex;
  justify-content: flex-end;
}

.grid-col {
  margin-bottom: 20px;
}

.agent-card {
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: 12px;
  padding: 16px;
  display: flex;
  flex-direction: column;
  height: 100%;
  transition: all 0.3s ease;
  box-shadow: 0 2px 8px var(--bg-hover-subtle);
}

.agent-card:hover {
  border-color: var(--el-color-primary-light-5);
  box-shadow: 0 4px 12px rgba(0,0,0,0.05);
  transform: translateY(-2px);
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 12px;
}

.agent-title {
  display: flex;
  align-items: center;
  gap: 8px;
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}
.status-dot.is-enabled { background-color: var(--el-color-success); box-shadow: 0 0 4px var(--el-color-success); }
.status-dot.is-disabled { background-color: var(--text-faint); }

.agent-title .name {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
}

.role-tag {
  border-radius: 12px;
  font-weight: 500;
}

.card-body {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.description {
  margin: 0;
  font-size: 13px;
  color: var(--text-secondary);
  line-height: 1.5;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  text-overflow: ellipsis;
  min-height: 39px;
}

.params-row {
  display: flex;
  justify-content: space-between;
  background: var(--bg-elevated);
  padding: 8px 12px;
  border-radius: 8px;
}

.param-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
}

.param-item .label {
  font-size: 11px;
  color: var(--text-muted);
}

.param-item .value {
  font-size: 13px;
  font-weight: 500;
  color: var(--text-primary);
  font-family: 'SF Mono', monospace;
}

.skills-row {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 4px;
}

.skill-tag {
  border-radius: 4px;
}

.skill-hint {
  font-size: 12px;
  color: var(--text-muted);
  line-height: 1.4;
  margin-top: 4px;
}

.card-footer {
  margin-top: 16px;
  padding-top: 12px;
  border-top: 1px solid var(--border-color);
  display: flex;
  justify-content: space-around;
}

.card-footer .el-button {
  padding: 4px 8px;
}

/* Chat Drawer Styles */
.test-drawer-content {
  display: flex;
  flex-direction: column;
  height: 100%;
  padding: 0 20px 20px;
}

.chat-history {
  flex: 1;
  overflow-y: auto;
  padding: 16px 0;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.empty-chat {
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: var(--text-muted);
  gap: 12px;
}

.chat-message {
  display: flex;
  max-width: 85%;
}

.user-message {
  align-self: flex-end;
}

.user-message .bubble {
  background: var(--el-color-primary);
  color: #fff;
  border-radius: 16px 16px 0 16px;
  padding: 12px 16px;
  font-size: 14px;
  line-height: 1.5;
}

.code-badge {
  background: var(--bg-hover);
  display: inline-block;
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 12px;
  margin-bottom: 4px;
  font-family: monospace;
}

.ai-message {
  align-self: flex-start;
}

.ai-message .bubble {
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  color: var(--text-primary);
  border-radius: 16px 16px 16px 0;
  padding: 12px 16px;
  font-size: 14px;
  line-height: 1.6;
}

.chat-input-area {
  margin-top: auto;
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: 12px;
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.code-input {
  width: 180px;
}

.input-with-button {
  display: flex;
  gap: 8px;
  align-items: flex-end;
}

.input-with-button :deep(.el-textarea__inner) {
  border: none;
  background: var(--bg-elevated);
  box-shadow: none;
  padding: 8px 12px;
}

.send-btn {
  height: 36px;
  width: 36px;
  padding: 8px;
  border-radius: 8px;
}

.typing-indicator {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 4px 8px;
}

.typing-indicator span {
  width: 6px;
  height: 6px;
  background-color: var(--text-muted);
  border-radius: 50%;
  animation: typing 1.4s infinite ease-in-out both;
}

.typing-indicator span:nth-child(1) { animation-delay: -0.32s; }
.typing-indicator span:nth-child(2) { animation-delay: -0.16s; }

@keyframes typing {
  0%, 80%, 100% { transform: scale(0); }
  40% { transform: scale(1); }
}

.result-content :deep(p) { margin: 0 0 8px 0; }
.result-content :deep(p:last-child) { margin: 0; }
</style>
