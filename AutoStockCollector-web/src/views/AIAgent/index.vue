<template>
  <div class="ai-agent-page">
    <el-tabs v-model="activeTab" class="agent-tabs">
      <el-tab-pane label="通用 Agent" name="general">
        <el-card shadow="never" class="section-card">
          <template #header>
            <div class="card-header">
              <span>AI Agent 管理</span>
              <el-button type="primary" size="small" @click="openAddDialog">
                <el-icon><Plus /></el-icon> 添加 Agent
              </el-button>
            </div>
          </template>

          <el-table :data="agents" stripe v-loading="loading">
            <el-table-column prop="name" label="名称" width="160" align="center">
              <template #default="{ row }">
                <div class="agent-name">
                  <el-tag :type="row.enabled ? 'success' : 'info'" size="small">
                    {{ row.enabled ? '启用' : '禁用' }}
                  </el-tag>
                  <span>{{ row.name }}</span>
                </div>
              </template>
            </el-table-column>
            <el-table-column prop="description" label="描述" min-width="200" align="center" show-overflow-tooltip />
            <el-table-column prop="role" label="角色" width="140" align="center">
              <template #default="{ row }">
                <el-tag size="small" type="warning">{{ row.role }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="temperature" label="温度" width="80" align="center">
              <template #default="{ row }">{{ row.temperature }}</template>
            </el-table-column>
            <el-table-column prop="max_tokens" label="最大Token" width="100" align="center" />
            <el-table-column label="优先级" width="80" align="center">
              <template #default="{ row }">
                <el-tag size="small">{{ row.priority }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="150" align="center">
              <template #default="{ row }">
                <div class="action-buttons">
                  <el-button type="primary" size="small" text @click="openEditDialog(row)">编辑</el-button>
                  <el-button type="warning" size="small" text @click="testAgent(row)">测试</el-button>
                  <el-button type="danger" size="small" text @click="deleteAgent(row)">删除</el-button>
                </div>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-tab-pane>

      <el-tab-pane label="投资哲学" name="philosophy">
        <el-card shadow="never" class="section-card">
          <template #header>
            <div class="card-header">
              <span>投资哲学 Agent（内置只读）</span>
              <el-tag type="info">共 {{ philosophyAgents.length }} 个</el-tag>
            </div>
          </template>

          <el-table :data="philosophyAgents" stripe v-loading="philosophyLoading">
            <el-table-column label="名称" width="180" align="center">
              <template #default="{ row }">
                <div class="agent-name">
                  <el-tag size="small" :type="schoolTagType(row.archetype)">{{ schoolLabel(row.archetype) }}</el-tag>
                  <span>{{ row.name }}</span>
                </div>
              </template>
            </el-table-column>
            <el-table-column prop="agent_id" label="ID" width="120" align="center" />
            <el-table-column prop="description" label="描述" min-width="200" align="center" show-overflow-tooltip />
            <el-table-column prop="holding_horizon" label="持有周期" width="80" align="center">
              <template #default="{ row }">
                <el-tag size="small">{{ holdingLabel(row.holding_horizon) }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="risk_tolerance" label="风险容忍" width="80" align="center">
              <template #default="{ row }">
                <span :class="riskClass(row.risk_tolerance)">{{ (row.risk_tolerance * 100).toFixed(0) }}%</span>
              </template>
            </el-table-column>
            <el-table-column label="权重配比" min-width="200" align="center">
              <template #default="{ row }">
                <div class="weight-bars">
                  <div v-for="(w, dim) in row.weight_dimensions" :key="dim" class="weight-item">
                    <span class="weight-label">{{ dim }}</span>
                    <el-progress :percentage="w * 100" :stroke-width="6" size="small" />
                  </div>
                </div>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="100" align="center">
              <template #default="{ row }">
                <el-button type="primary" size="small" text @click="viewPhilosophyDetail(row)">详情</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-tab-pane>
    </el-tabs>

    <!-- Add/Edit Dialog -->
    <el-dialog
      v-model="showDialog"
      :title="isEdit ? '编辑 Agent' : '添加 Agent'"
      width="700px"
      @close="handleDialogClose"
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
        <el-row :gutter="20">
          <el-col :span="8">
            <el-form-item label="温度">
              <el-input-number v-model="form.temperature" :min="0" :max="2" :step="0.1" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="最大Token">
              <el-input-number v-model="form.max_tokens" :min="100" :max="8000" :step="100" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="优先级">
              <el-input-number v-model="form.priority" :min="1" :max="100" />
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

    <!-- Test Dialog -->
    <el-dialog v-model="showTestDialog" title="测试 Agent" width="700px">
      <div class="test-container">
        <el-form :inline="true">
          <el-form-item label="股票代码">
            <el-input v-model="testCode" placeholder="输入股票代码如 SH600519" style="width: 200px" />
          </el-form-item>
          <el-form-item label="测试问题">
            <el-input v-model="testMessage" placeholder="输入问题" style="width: 300px" />
          </el-form-item>
        </el-form>
        <div class="test-actions">
          <el-button type="primary" @click="runTest" :loading="testing">运行测试</el-button>
        </div>
        <div v-if="testResult" class="test-result">
          <div class="test-label">AI 回复：</div>
          <div class="result-content" v-html="formatResult(testResult)"></div>
        </div>
      </div>
    </el-dialog>

    <!-- Philosophy Detail Dialog -->
    <el-dialog v-model="showPhilosophyDetail" :title="philosophyDetail?.name || '投资哲学详情'" width="800px">
      <template v-if="philosophyDetail">
        <div class="philosophy-detail">
          <el-descriptions :column="2" border size="small">
            <el-descriptions-item label="Agent ID">{{ philosophyDetail.agent_id }}</el-descriptions-item>
            <el-descriptions-item label="流派">
              <el-tag size="small" :type="schoolTagType(philosophyDetail.archetype)">{{ schoolLabel(philosophyDetail.archetype) }}</el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="持有周期">{{ holdingLabel(philosophyDetail.holding_horizon) }}</el-descriptions-item>
            <el-descriptions-item label="风险容忍">
              <span :class="riskClass(philosophyDetail.risk_tolerance)">{{ (philosophyDetail.risk_tolerance * 100).toFixed(0) }}%</span>
            </el-descriptions-item>
            <el-descriptions-item label="温度">{{ philosophyDetail.temperature }}</el-descriptions-item>
            <el-descriptions-item label="最大Token">{{ philosophyDetail.max_tokens }}</el-descriptions-item>
          </el-descriptions>
          <div class="detail-section">
            <div class="detail-label">描述</div>
            <div class="detail-content">{{ philosophyDetail.description }}</div>
          </div>
          <div class="detail-section">
            <div class="detail-label">系统提示词</div>
            <div class="detail-content prompt-content">{{ philosophyDetail.system_prompt }}</div>
          </div>
          <div class="detail-section">
            <div class="detail-label">权重配比</div>
            <div class="weight-bars">
              <div v-for="(w, dim) in philosophyDetail.weight_dimensions" :key="dim" class="weight-item">
                <span class="weight-label">{{ dim }}</span>
                <el-progress :percentage="w * 100" :stroke-width="8" size="small" />
              </div>
            </div>
          </div>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { aiAgentApi, type AIAgent, philosophyApi, type PhilosophyAgentDetail } from '@/api/ai'
import { Plus } from '@element-plus/icons-vue'

const activeTab = ref('general')

const loading = ref(false)
const agents = ref<AIAgent[]>([])
const showDialog = ref(false)
const showTestDialog = ref(false)
const isEdit = ref(false)
const saving = ref(false)
const testing = ref(false)
const testMessage = ref('')
const testCode = ref('')
const testResult = ref('')
const testAgentId = ref('')

const philosophyAgents = ref<PhilosophyAgentDetail[]>([])
const philosophyLoading = ref(false)
const showPhilosophyDetail = ref(false)
const philosophyDetail = ref<PhilosophyAgentDetail | null>(null)

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
})

const form = ref<Partial<AIAgent>>(defaultForm())

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
  form.value = { ...agent }
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
  return text
    .replace(/\n/g, '<br>')
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
}

const schoolColors: Record<string, string> = {
  value: 'success', growth: '', technical: 'warning',
  macro: 'danger', quant: 'info', hot_money: 'danger',
  risk: '', sentiment: '',
}
const schoolLabelsMap: Record<string, string> = {
  value: '价值派', growth: '成长派', technical: '技术派',
  macro: '宏观派', quant: '量化派', hot_money: '游资派',
  risk: '风控派', sentiment: '舆情派',
}

function schoolTagType(archetype: string): string {
  return schoolColors[archetype] || 'info'
}
function schoolLabel(archetype: string): string {
  return schoolLabelsMap[archetype] || archetype
}
function holdingLabel(h: string): string {
  return { short: '短期', medium: '中期', long: '长期' }[h] || h
}
function riskClass(r: number): string {
  if (r >= 0.7) return 'risk-high'
  if (r >= 0.4) return 'risk-mid'
  return 'risk-low'
}

async function loadPhilosophyAgents() {
  philosophyLoading.value = true
  try {
    const res = await philosophyApi.listAgents()
    if (res.data?.success && Array.isArray(res.data.data)) {
      philosophyAgents.value = res.data.data
    }
  } catch {
    philosophyAgents.value = []
  } finally {
    philosophyLoading.value = false
  }
}

function viewPhilosophyDetail(agent: PhilosophyAgentDetail) {
  philosophyDetail.value = agent
  showPhilosophyDetail.value = true
}

onMounted(() => {
  loadAgents()
  loadPhilosophyAgents()
})
</script>

<style scoped>
.ai-agent-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.section-card {
  background: #1f1f1f;
  border: 1px solid #2c2c2c;
}

.section-card :deep(.el-card__header) {
  border-bottom: 1px solid #2c2c2c;
  padding: 12px 16px;
  color: #e5eaf3;
  font-size: 14px;
  font-weight: 600;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.agent-name {
  display: flex;
  align-items: center;
  gap: 8px;
}

.action-buttons {
  display: flex;
  gap: 4px;
  justify-content: center;
}

.test-container {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.test-label {
  font-size: 13px;
  color: #909399;
  margin-bottom: 8px;
}

.test-actions {
  display: flex;
  justify-content: flex-start;
}

.test-result {
  margin-top: 8px;
}

.result-content {
  background: #2c2c2c;
  padding: 16px;
  border-radius: 8px;
  font-size: 14px;
  line-height: 1.6;
  color: #e5eaf3;
  max-height: 300px;
  overflow-y: auto;
}
.agent-tabs :deep(.el-tabs__header) {
  margin: 0 0 16px;
  border-bottom: 1px solid #2c2c2c;
}
.agent-tabs :deep(.el-tabs__item) {
  color: #909399;
  font-size: 14px;
}
.agent-tabs :deep(.el-tabs__item.is-active) {
  color: #409eff;
}
.agent-tabs :deep(.el-tabs__active-bar) {
  background-color: #409eff;
}
.weight-bars {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}
.weight-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  min-width: 70px;
}
.weight-label {
  font-size: 10px;
  color: #909399;
  text-transform: uppercase;
}
.weight-item :deep(.el-progress) {
  width: 70px;
}
.risk-high { color: #f56c6c; font-weight: 600; }
.risk-mid { color: #e6a23c; font-weight: 600; }
.risk-low { color: #67c23a; font-weight: 600; }
.philosophy-detail {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.detail-section {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.detail-label {
  font-size: 13px;
  color: #909399;
  font-weight: 600;
}
.detail-content {
  font-size: 13px;
  color: #e5eaf3;
  line-height: 1.6;
  background: #2c2c2c;
  padding: 12px;
  border-radius: 6px;
}
.prompt-content {
  max-height: 300px;
  overflow-y: auto;
  white-space: pre-wrap;
}
</style>