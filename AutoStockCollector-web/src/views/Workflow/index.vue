<template>
  <div class="workflow-page">
    <div class="page-header">
      <div class="header-left">
        <h2>工作流管理</h2>
        <p class="subtitle">可视化编排和管理多种工作流，支持选股、监控、分析等场景</p>
      </div>
      <div class="header-actions">
        <el-button @click="openTemplateDialog">
          <el-icon><DocumentCopy /></el-icon> 从模板创建
        </el-button>
        <el-button type="primary" @click="createNewWorkflow">
          <el-icon><Plus /></el-icon> 新建工作流
        </el-button>
      </div>
    </div>

    <el-card shadow="never" class="workflow-list-card">
      <template #header>
        <div class="card-header">
          <span>工作流列表</span>
          <div class="filter-actions">
            <el-select v-model="filterEnabled" placeholder="筛选状态" clearable size="small" style="width: 120px">
              <el-option label="全部" :value="null" />
              <el-option label="已启用" :value="true" />
              <el-option label="已禁用" :value="false" />
            </el-select>
          </div>
        </div>
      </template>

      <div v-if="loading" class="loading-container">
        <el-icon class="is-loading"><Loading /></el-icon>
        <span>加载中...</span>
      </div>

      <div v-else-if="workflows.length === 0" class="empty-state">
        <el-icon :size="48"><Files /></el-icon>
        <p>暂无工作流</p>
        <el-button type="primary" @click="createNewWorkflow">创建第一个工作流</el-button>
        <el-button @click="loadWorkflows">刷新列表</el-button>
      </div>

      <div v-else class="workflow-grid">
        <div
          v-for="workflow in filteredWorkflows"
          :key="workflow.id"
          class="workflow-card"
          @click="openWorkflow(workflow)"
        >
          <div class="workflow-card-header">
            <h3>{{ workflow.name }}</h3>
            <el-tag :type="workflow.enabled ? 'success' : 'info'" size="small">
              {{ workflow.enabled ? '启用' : '禁用' }}
            </el-tag>
          </div>
          <p class="workflow-description">{{ workflow.description || '暂无描述' }}</p>
          <div class="workflow-meta">
            <span><el-icon><Clock /></el-icon> 运行 {{ workflow.run_count }} 次</span>
            <span v-if="workflow.last_run_at">
              <el-icon><Timer /></el-icon> {{ formatDate(workflow.last_run_at) }}
            </span>
          </div>
          <div class="workflow-tags" v-if="workflow.tags.length">
            <el-tag v-for="tag in workflow.tags" :key="tag" size="small">{{ tag }}</el-tag>
          </div>
          <div class="workflow-actions" @click.stop>
            <el-button type="primary" size="small" text @click="editWorkflow(workflow)">
              <el-icon><Edit /></el-icon> 编辑
            </el-button>
            <el-button type="success" size="small" text @click="runWorkflow(workflow)">
              <el-icon><VideoPlay /></el-icon> 运行
            </el-button>
            <el-button type="danger" size="small" text @click="deleteWorkflow(workflow)">
              <el-icon><Delete /></el-icon> 删除
            </el-button>
          </div>
        </div>
      </div>
    </el-card>

    <el-dialog
      v-model="showEditorDialog"
      :title="editingWorkflow ? '编辑工作流' : '新建工作流'"
      width="95%"
      top="2vh"
      @close="handleEditorClose"
    >
      <WorkflowCanvas
        v-if="showEditorDialog"
        :workflow="editingWorkflow"
        :templates="templates"
        @save="handleSaveWorkflow"
        @cancel="showEditorDialog = false"
      />
    </el-dialog>

    <el-dialog v-model="showTemplateDialog" title="选择模板" width="800px">
      <div class="template-grid">
        <div
          v-for="template in templates"
          :key="template.id"
          class="template-card"
          @click="createFromTemplate(template)"
        >
          <h4>{{ template.name }}</h4>
          <p>{{ template.description }}</p>
          <div class="template-tags">
            <el-tag v-for="tag in template.tags" :key="tag" size="small">{{ tag }}</el-tag>
          </div>
        </div>
      </div>
    </el-dialog>

    <el-dialog
      v-model="showProgressDialog"
      title="工作流执行中..."
      width="700px"
      :close-on-click-modal="false"
      :close-on-press-escape="false"
      show-close
      @close="handleProgressClose"
    >
      <div class="progress-container">
        <div class="progress-header">
          <el-icon class="is-loading" :size="24"><Loading /></el-icon>
          <span>正在执行智能选股工作流，请稍候...</span>
        </div>

        <el-progress
          :percentage="runProgress"
          :status="runProgress === 100 ? 'success' : undefined"
          :stroke-width="20"
          striped
          striped-flow
        />

        <div class="log-container">
          <div class="log-title">执行日志</div>
          <el-scrollbar max-height="300px">
            <div class="log-list">
              <div
                v-for="(log, index) in runLogs"
                :key="index"
                class="log-item"
                :class="{
                  'log-success': log.includes('✅') || log.includes('成功'),
                  'log-error': log.includes('❌') || log.includes('失败'),
                  'log-info': log.includes('⏳') || log.includes('⏱️') || log.includes('📊')
                }"
              >
                {{ log }}
              </div>
            </div>
          </el-scrollbar>
        </div>
      </div>

      <template #footer>
        <el-button
          v-if="!isRunning"
          type="primary"
          @click="showProgressDialog = false"
        >
          查看结果
        </el-button>
        <el-button
          v-else
          disabled
        >
          <el-icon class="is-loading"><Loading /></el-icon> 执行中...
        </el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="showRunDialog" title="选股结果" width="1000px">
      <div v-if="runResult" class="run-result">
        <el-alert
          :title="runResult.success ? '✅ 工作流执行成功' : '❌ 工作流执行失败'"
          :type="runResult.success ? 'success' : 'error'"
          :description="runResult.error || '通过多维度筛选和智能评分，系统为您精选出以下优质股票'"
          show-icon
        />

        <div v-if="runResult.success" class="result-summary">
          <div class="summary-item">
            <div class="summary-icon">📈</div>
            <div class="summary-info">
              <div class="summary-value">{{ runResult.result_count }}</div>
              <div class="summary-label">选股数量</div>
            </div>
          </div>
          <div class="summary-item">
            <div class="summary-icon">⏱️</div>
            <div class="summary-info">
              <div class="summary-value">{{ runResult.duration.toFixed(2) }}s</div>
              <div class="summary-label">执行时间</div>
            </div>
          </div>
          <div class="summary-item">
            <div class="summary-icon">🎯</div>
            <div class="summary-info">
              <div class="summary-value">{{ getAverageScore() }}</div>
              <div class="summary-label">平均评分</div>
            </div>
          </div>
        </div>

        <div v-if="runResult.results && runResult.results.length > 0" class="result-table">
          <el-table :data="runResult.results" stripe max-height="450">
            <el-table-column type="index" label="排名" width="60" align="center" />
            <el-table-column prop="code" label="代码" width="100">
              <template #default="{ row }">
                <el-tag size="small" type="info">{{ row.code }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="name" label="名称" width="120" show-overflow-tooltip />
            <el-table-column prop="score" label="综合评分" width="100" align="center">
              <template #default="{ row }">
                <el-tag :type="getScoreType(row.score)" size="large">{{ row.score.toFixed(1) }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="recommendation" label="推荐" width="100" align="center">
              <template #default="{ row }">
                <el-tag :type="getRecommendationType(row.recommendation)">{{ row.recommendation }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="多维评分" width="220">
              <template #default="{ row }">
                <div class="score-badges">
                  <el-tooltip content="技术面评分" placement="top">
                    <el-tag size="small" type="info">技:{{ row.technical_score?.toFixed(0) }}</el-tag>
                  </el-tooltip>
                  <el-tooltip content="基本面评分" placement="top">
                    <el-tag size="small" type="info">基:{{ row.fundamental_score?.toFixed(0) }}</el-tag>
                  </el-tooltip>
                  <el-tooltip content="资金流评分" placement="top">
                    <el-tag size="small" type="info">资:{{ row.fund_flow_score?.toFixed(0) }}</el-tag>
                  </el-tooltip>
                  <el-tooltip content="舆情评分" placement="top">
                    <el-tag size="small" type="info">舆:{{ row.sentiment_score?.toFixed(0) }}</el-tag>
                  </el-tooltip>
                </div>
              </template>
            </el-table-column>
            <el-table-column label="止损/目标" width="150" align="center">
              <template #default="{ row }">
                <div class="price-info">
                  <div class="price-item stop-loss">止损: {{ row.stop_loss?.toFixed(2) }}</div>
                  <div class="price-item target">目标: {{ row.target_price?.toFixed(2) }}</div>
                </div>
              </template>
            </el-table-column>
          </el-table>
        </div>

        <div class="result-tips">
          <el-alert
            title="投资提示"
            type="info"
            :closable="false"
            show-icon
          >
            <template #default>
              <ul class="tips-list">
                <li>以上选股结果仅供参考，不构成任何投资建议</li>
                <li>股市有风险，投资需谨慎，请根据自身风险承受能力决策</li>
                <li>建议结合市场环境和个人研究，理性投资</li>
                <li>止损价和目标价仅为参考，实际操作需灵活应对</li>
              </ul>
            </template>
          </el-alert>
        </div>
      </div>
      <template #footer>
        <el-button @click="showRunDialog = false">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Plus, Edit, Delete, VideoPlay, Clock, Timer,
  Files, DocumentCopy, Loading
} from '@element-plus/icons-vue'
import { workflowApi, type Workflow, type WorkflowResult, type WorkflowTemplate } from '@/api/workflow'
import WorkflowCanvas from '@/components/WorkflowCanvas/index.vue'

const loading = ref(false)
const workflows = ref<Workflow[]>([])
const filterEnabled = ref<boolean | null>(null)
const showEditorDialog = ref(false)
const showTemplateDialog = ref(false)
const showRunDialog = ref(false)
const showProgressDialog = ref(false)
const editingWorkflow = ref<Workflow | null>(null)
const templates = ref<WorkflowTemplate[]>([])
const runResult = ref<WorkflowResult | null>(null)
const runLogs = ref<string[]>([])
const runProgress = ref(0)
const isRunning = ref(false)

const filteredWorkflows = computed(() => {
  if (filterEnabled.value === null) {
    return workflows.value
  }
  return workflows.value.filter(w => w.enabled === filterEnabled.value)
})

async function loadWorkflows() {
  loading.value = true
  try {
    const res = await workflowApi.list()
    workflows.value = res.data?.data || []
  } catch {
    ElMessage.error('加载工作流列表失败')
  } finally {
    loading.value = false
  }
}

async function loadTemplates() {
  try {
    const res = await workflowApi.getTemplates()
    templates.value = res.data?.data || []
  } catch {
    templates.value = []
  }
}

function createNewWorkflow() {
  editingWorkflow.value = null
  showEditorDialog.value = true
}

function openWorkflow(workflow: Workflow) {
  editWorkflow(workflow)
}

function editWorkflow(workflow: Workflow) {
  editingWorkflow.value = { ...workflow }
  showEditorDialog.value = true
}

async function handleSaveWorkflow(workflow: Workflow) {
  try {
    if (editingWorkflow.value?.id) {
      await workflowApi.update(workflow.id, workflow)
      ElMessage.success('工作流更新成功')
    } else {
      await workflowApi.create(workflow)
      ElMessage.success('工作流创建成功')
    }
    showEditorDialog.value = false
    await loadWorkflows()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.error || '保存失败')
  }
}

function handleEditorClose() {
  editingWorkflow.value = null
}

async function deleteWorkflow(workflow: Workflow) {
  try {
    await ElMessageBox.confirm(
      `确定要删除工作流 "${workflow.name}" 吗？此操作不可恢复。`,
      '删除确认',
      { confirmButtonText: '删除', cancelButtonText: '取消', type: 'warning' }
    )
    await workflowApi.delete(workflow.id)
    ElMessage.success('删除成功')
    await loadWorkflows()
  } catch {
    // cancelled
  }
}

async function runWorkflow(workflow: Workflow) {
  runLogs.value = []
  runProgress.value = 0
  isRunning.value = true
  showProgressDialog.value = true

  try {
    addLog(`🚀 开始执行工作流: ${workflow.name}`)
    addLog(`📊 工作流包含 ${workflow.nodes.length} 个节点`)
    addLog(`📡 正在连接后端API...`)
    addLog(`⏳ 正在执行工作流，请稍候...`)
    runProgress.value = 30

    const res = await workflowApi.run(workflow.id)

    if (res.data?.data?.success) {
      const data = res.data.data
      runResult.value = data
      const resultCount = data.result_count || 0
      const duration = data.duration || 0
      const executionLog = data.execution_log || []

      addLog(`✅ 后端开始执行节点...`)
      for (const log of executionLog) {
        if (log.status === 'completed') {
          addLog(`✅ ${log.label}: ${log.message} (${log.stocks_count}只)`)
        } else {
          addLog(`❌ ${log.label}: ${log.message}`)
        }
      }

      addLog(`✅ 工作流执行成功`)
      addLog(`📈 筛选出 ${resultCount} 只符合条件的股票`)
      addLog(`⏱️ 总耗时: ${duration.toFixed(2)} 秒`)

      runProgress.value = 100

      showProgressDialog.value = false
      showRunDialog.value = true

      await loadWorkflows()
    } else {
      addLog(`❌ 执行失败: ${res.data?.data?.error || '未知错误'}`)
      ElMessage.error('工作流执行失败')
    }
  } catch (e: any) {
    const errorMsg = e?.response?.data?.error || e.message || '运行失败'
    addLog(`❌ 执行失败: ${errorMsg}`)
    ElMessage.error(errorMsg)
  } finally {
    isRunning.value = false
  }
}

function addLog(message: string) {
  const timestamp = new Date().toLocaleTimeString('zh-CN')
  runLogs.value.push(`[${timestamp}] ${message}`)
}

function handleProgressClose() {
  if (isRunning.value) {
    ElMessage.warning('工作流正在执行中，请稍候')
  }
}

function openTemplateDialog() {
  showTemplateDialog.value = true
}

function createFromTemplate(template: WorkflowTemplate) {
  editingWorkflow.value = {
    id: '',
    name: template.name + ' (副本)',
    description: template.description,
    nodes: [...template.nodes],
    edges: [...template.edges],
    enabled: true,
    run_count: 0,
    tags: [...template.tags]
  }
  showTemplateDialog.value = false
  showEditorDialog.value = true
}

function formatDate(dateStr: string) {
  if (!dateStr) return ''
  const date = new Date(dateStr)
  return date.toLocaleDateString('zh-CN')
}

function getScoreType(score: number) {
  if (score >= 75) return 'success'
  if (score >= 65) return 'warning'
  if (score >= 55) return 'info'
  return 'danger'
}

function getRecommendationType(recommendation: string) {
  const map: Record<string, string> = {
    '强烈推荐': 'success',
    '买入': 'warning',
    '谨慎买入': 'info',
    '观望': 'info',
    '回避': 'danger'
  }
  return map[recommendation] || 'info'
}

function getAverageScore() {
  if (!runResult.value?.results || runResult.value.results.length === 0) return '0'
  const total = runResult.value.results.reduce((sum, r) => sum + r.score, 0)
  return (total / runResult.value.results.length).toFixed(1)
}

onMounted(() => {
  loadWorkflows()
  loadTemplates()
})

</script>

<style scoped>
.workflow-page {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  padding: 16px 20px;
  background: #1f1f1f;
  border: 1px solid #2c2c2c;
  border-radius: 8px;
}

.header-left h2 {
  margin: 0 0 8px 0;
  font-size: 20px;
  font-weight: 600;
  color: #e5eaf3;
}

.subtitle {
  margin: 0;
  font-size: 14px;
  color: #909399;
}

.header-actions {
  display: flex;
  gap: 12px;
}

.workflow-list-card {
  background: #1f1f1f;
  border: 1px solid #2c2c2c;
}

.workflow-list-card :deep(.el-card__header) {
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

.loading-container {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 48px;
  color: #909399;
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16px;
  padding: 48px;
  color: #909399;
}

.workflow-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 16px;
  padding: 16px 0;
}

.workflow-card {
  background: #2c2c2c;
  border: 1px solid #3c3c3c;
  border-radius: 8px;
  padding: 16px;
  cursor: pointer;
  transition: all 0.3s;
}

.workflow-card:hover {
  border-color: #409eff;
  transform: translateY(-2px);
}

.workflow-card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.workflow-card-header h3 {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  color: #e5eaf3;
}

.workflow-description {
  margin: 0 0 12px 0;
  font-size: 13px;
  color: #909399;
  line-height: 1.5;
}

.workflow-meta {
  display: flex;
  gap: 16px;
  margin-bottom: 8px;
  font-size: 12px;
  color: #606266;
}

.workflow-meta span {
  display: flex;
  align-items: center;
  gap: 4px;
}

.workflow-tags {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  margin-bottom: 12px;
}

.workflow-actions {
  display: flex;
  gap: 8px;
  padding-top: 12px;
  border-top: 1px solid #3c3c3c;
}

.template-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 16px;
}

.template-card {
  background: #2c2c2c;
  border: 1px solid #3c3c3c;
  border-radius: 8px;
  padding: 16px;
  cursor: pointer;
  transition: all 0.3s;
}

.template-card:hover {
  border-color: #409eff;
}

.template-card h4 {
  margin: 0 0 8px 0;
  font-size: 16px;
  font-weight: 600;
  color: #e5eaf3;
}

.template-card p {
  margin: 0 0 12px 0;
  font-size: 13px;
  color: #909399;
}

.template-tags {
  display: flex;
  gap: 8px;
}

.run-result {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.result-stats {
  display: flex;
  gap: 24px;
  padding: 16px;
  background: #2c2c2c;
  border-radius: 8px;
}

.stat-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.stat-label {
  font-size: 12px;
  color: #909399;
}

.stat-value {
  font-size: 20px;
  font-weight: 600;
  color: #409eff;
}

.result-table {
  margin-top: 16px;
}

.result-summary {
  display: flex;
  gap: 16px;
  padding: 16px;
  background: #2c2c2c;
  border-radius: 8px;
  margin: 16px 0;
}

.summary-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 20px;
  background: #3c3c3c;
  border-radius: 8px;
  flex: 1;
}

.summary-icon {
  font-size: 32px;
}

.summary-info {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.summary-value {
  font-size: 24px;
  font-weight: 600;
  color: #409eff;
}

.summary-label {
  font-size: 12px;
  color: #909399;
}

.score-badges {
  display: flex;
  gap: 4px;
  flex-wrap: wrap;
}

.price-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
  font-size: 12px;
}

.price-item {
  padding: 2px 6px;
  border-radius: 4px;
}

.price-item.stop-loss {
  color: #f56c6c;
  background: rgba(245, 108, 108, 0.1);
}

.price-item.target {
  color: #67c23a;
  background: rgba(103, 194, 58, 0.1);
}

.result-tips {
  margin-top: 16px;
}

.tips-list {
  margin: 0;
  padding-left: 20px;
  color: #909399;
  font-size: 13px;
  line-height: 1.8;
}

.tips-list li {
  margin-bottom: 4px;
}

.tips-list li:last-child {
  margin-bottom: 0;
}

.progress-container {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.progress-header {
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 16px;
  color: #e5eaf3;
  padding: 8px 0;
}

.log-container {
  border: 1px solid #3c3c3c;
  border-radius: 8px;
  padding: 12px;
  background: #1a1a1a;
}

.log-title {
  font-size: 14px;
  font-weight: 600;
  color: #909399;
  margin-bottom: 12px;
  padding-bottom: 8px;
  border-bottom: 1px solid #2c2c2c;
}

.log-list {
  font-family: 'Courier New', monospace;
  font-size: 13px;
  line-height: 1.8;
}

.log-item {
  padding: 4px 8px;
  margin-bottom: 4px;
  border-radius: 4px;
  background: #252525;
  color: #c0c4cc;
  transition: all 0.3s;
}

.log-item:last-child {
  margin-bottom: 0;
}

.log-success {
  background: rgba(103, 194, 58, 0.1);
  color: #67c23a;
  border-left: 3px solid #67c23a;
}

.log-error {
  background: rgba(245, 108, 108, 0.1);
  color: #f56c6c;
  border-left: 3px solid #f56c6c;
}

.log-info {
  background: rgba(64, 158, 255, 0.1);
  color: #409eff;
  border-left: 3px solid #409eff;
}
</style>
