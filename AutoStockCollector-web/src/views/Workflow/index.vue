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

    <el-tabs v-model="activeTab" class="workflow-tabs">
      <el-tab-pane label="工作流列表" name="list">
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
                <el-button type="warning" size="small" text @click="duplicateWorkflow(workflow)">
                  <el-icon><CopyDocument /></el-icon> 复制
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
      </el-tab-pane>

      <el-tab-pane name="executions">
        <template #label>
          <span>执行历史</span>
          <el-badge v-if="runningCount > 0" :value="runningCount" type="danger" class="execution-badge" />
        </template>
        <el-card shadow="never" class="execution-list-card">
          <template #header>
            <div class="card-header">
              <span>执行历史</span>
              <div class="header-actions">
                <el-button size="small" type="warning" @click="cleanupZombies" :loading="cleaningUp">
                  <el-icon><Warning /></el-icon> 清理僵尸任务
                </el-button>
                <el-button
                  size="small"
                  type="danger"
                  :disabled="selectedExecutions.length === 0"
                  @click="batchDeleteExecutions"
                >
                  <el-icon><Delete /></el-icon> 批量删除 {{ selectedExecutions.length > 0 ? `(${selectedExecutions.length})` : '' }}
                </el-button>
                <el-button size="small" type="danger" plain @click="clearAllExecutions">
                  <el-icon><DeleteFilled /></el-icon> 清空全部
                </el-button>
                <el-button size="small" @click="loadExecutionHistory" :loading="loadingExecutions">
                  <el-icon><Refresh /></el-icon> 刷新
                </el-button>
              </div>
            </div>
          </template>

          <div class="execution-stats" v-if="allExecutions.length > 0">
            <div class="stat-card stat-total">
              <div class="stat-value">{{ allExecutions.length }}</div>
              <div class="stat-label">总执行</div>
            </div>
            <div class="stat-card stat-completed">
              <div class="stat-value">{{ completedCount }}</div>
              <div class="stat-label">已完成</div>
            </div>
            <div class="stat-card stat-running">
              <div class="stat-value">{{ runningCount }}</div>
              <div class="stat-label">进行中</div>
            </div>
            <div class="stat-card stat-failed">
              <div class="stat-value">{{ failedCount }}</div>
              <div class="stat-label">失败</div>
            </div>
            <div class="stat-card stat-success-rate">
              <div class="stat-value">{{ successRate }}%</div>
              <div class="stat-label">成功率</div>
            </div>
          </div>

          <div class="execution-filters" v-if="allExecutions.length > 0">
            <el-input
              v-model="executionFilter"
              placeholder="搜索工作流名称"
              size="small"
              clearable
              style="width: 200px"
            >
              <template #prefix><el-icon><Search /></el-icon></template>
            </el-input>
            <el-select v-model="executionStatusFilter" size="small" clearable placeholder="状态筛选" style="width: 120px">
              <el-option label="全部" value="" />
              <el-option label="执行中" value="running" />
              <el-option label="已暂停" value="paused" />
              <el-option label="已完成" value="completed" />
              <el-option label="失败" value="failed" />
              <el-option label="已取消" value="cancelled" />
            </el-select>
            <el-date-picker
              v-model="executionDateRange"
              type="daterange"
              range-separator="至"
              start-placeholder="开始日期"
              end-placeholder="结束日期"
              size="small"
              value-format="YYYY-MM-DD"
            />
          </div>

          <div v-if="loadingExecutions" class="loading-container">
            <el-icon class="is-loading"><Loading /></el-icon>
            <span>加载中...</span>
          </div>

          <div v-else-if="allExecutions.length === 0" class="empty-state">
            <el-icon :size="48"><Timer /></el-icon>
            <p>暂无执行记录</p>
            <el-button @click="loadExecutionHistory">刷新列表</el-button>
          </div>

          <el-table
            v-else
            :data="filteredExecutions"
            stripe
            class="execution-table"
            @selection-change="handleSelectionChange"
            :row-class-name="getExecutionRowClass"
          >
            <el-table-column type="selection" width="45" />
            <el-table-column prop="workflow_name" label="工作流" width="180">
              <template #default="{ row }">
                <el-tag type="info">{{ row.workflow_name || row.workflow_id }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="status" label="状态" width="100">
              <template #default="{ row }">
                <el-tag :type="getStatusType(row.status)" size="small">
                  {{ getStatusLabel(row.status) }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="progress" label="进度" width="150">
              <template #default="{ row }">
                <el-progress
                  :percentage="Math.round(row.progress || 0)"
                  :status="row.status === 'completed' ? 'success' : row.status === 'failed' ? 'exception' : undefined"
                  :stroke-width="12"
                />
              </template>
            </el-table-column>
            <el-table-column prop="current_step" label="当前步骤" min-width="150" show-overflow-tooltip />
            <el-table-column prop="started_at" label="开始时间" width="160">
              <template #default="{ row }">
                {{ formatDateTime(row.started_at) }}
              </template>
            </el-table-column>
            <el-table-column prop="finished_at" label="结束时间" width="160">
              <template #default="{ row }">
                {{ row.finished_at ? formatDateTime(row.finished_at) : '-' }}
              </template>
            </el-table-column>
            <el-table-column label="操作" width="220" fixed="right">
              <template #default="{ row }">
                <div class="execution-actions">
                  <template v-if="row.status === 'running' || row.status === 'pending'">
                    <el-button type="primary" size="small" text @click="viewExecutionProgress(row)">
                      <el-icon><View /></el-icon> 进度
                    </el-button>
                    <el-button type="warning" size="small" text @click="pauseExecution(row)">
                      <el-icon><VideoPause /></el-icon> 暂停
                    </el-button>
                    <el-button type="danger" size="small" text @click="stopExecution(row)">
                      <el-icon><SwitchButton /></el-icon> 终止
                    </el-button>
                  </template>
                  <template v-else-if="row.status === 'paused'">
                    <el-button type="success" size="small" text @click="resumeExecution(row)">
                      <el-icon><VideoPlay /></el-icon> 继续
                    </el-button>
                    <el-button type="danger" size="small" text @click="stopExecution(row)">
                      <el-icon><SwitchButton /></el-icon> 终止
                    </el-button>
                  </template>
                  <template v-else>
                    <el-button v-if="row.result" type="primary" size="small" text @click="viewExecutionResult(row)">
                      <el-icon><View /></el-icon> 结果
                    </el-button>
                    <el-button v-if="row.steps && row.steps.length > 0" size="small" text @click="viewExecutionProgress(row)">
                      详情
                    </el-button>
                  </template>
                  <el-button
                    type="danger"
                    size="small"
                    text
                    :disabled="row.status === 'running' || row.status === 'pending'"
                    @click="deleteSingleExecution(row)"
                  >
                    <el-icon><Delete /></el-icon>
                  </el-button>
                </div>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-tab-pane>
    </el-tabs>

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
      :title="isRunning ? '工作流执行中...' : '工作流执行完成'"
      width="700px"
      :close-on-click-modal="false"
      :close-on-press-escape="false"
      show-close
      @close="handleProgressClose"
    >
      <div class="progress-container">
        <div class="progress-header">
          <el-icon class="is-loading" :size="24" v-if="isRunning"><Loading /></el-icon>
          <el-icon :size="24" v-else :color="currentExecution?.status === 'completed' ? '#67c23a' : '#f56c6c'">
            <CircleCheck v-if="currentExecution?.status === 'completed'" />
            <CircleClose v-else-if="currentExecution?.status === 'failed'" />
            <Warning v-else />
          </el-icon>
          <span>{{ isRunning ? '正在执行智能选股工作流，请稍候...' : (currentExecution?.status === 'completed' ? '工作流执行成功' : '工作流执行' + (currentExecution?.status === 'failed' ? '失败' : '已' + (currentExecution?.status === 'cancelled' ? '取消' : '结束'))) }}</span>
        </div>

        <div class="current-step" v-if="currentExecution?.current_step">
          <el-tag :type="isRunning ? 'primary' : currentExecution?.status === 'completed' ? 'success' : 'danger'" size="small">
            正在执行: {{ currentExecution.current_step }}
          </el-tag>
        </div>

        <el-progress
          :percentage="runProgress"
          :status="runProgress === 100 ? 'success' : runProgress > 0 && currentExecution?.status === 'failed' ? 'exception' : undefined"
          :stroke-width="20"
          :striped="isRunning"
          striped-flow
        />

        <!-- Step list detail -->
        <div v-if="currentExecution?.steps && currentExecution.steps.length > 0" class="step-list-container">
          <div class="step-list-title">步骤详情（{{ currentExecution.steps.length }} 步）</div>
          <el-scrollbar max-height="180px">
            <div class="step-list">
              <div
                v-for="(step, idx) in currentExecution.steps"
                :key="idx"
                class="step-item"
                :class="{ 'step-current': idx === currentExecution.steps.length - 1 && isRunning }"
              >
                <span class="step-index">{{ idx + 1 }}</span>
                <span class="step-node">{{ step.node_label }}</span>
                <span class="step-desc">{{ step.step }}</span>
                <el-progress
                  :percentage="Math.round(step.progress || 0)"
                  :stroke-width="6"
                  style="width: 80px; flex-shrink: 0"
                />
                <span class="step-time">{{ formatStepTime(step.timestamp) }}</span>
              </div>
            </div>
          </el-scrollbar>
        </div>

        <div class="log-container">
          <div class="log-title">执行日志</div>
          <el-scrollbar max-height="200px">
            <div class="log-list">
              <div
                v-for="(log, index) in runLogs"
                :key="index"
                class="log-item"
                :class="{
                  'log-success': log.includes('✅') || log.includes('成功'),
                  'log-error': log.includes('❌') || log.includes('失败'),
                  'log-warning': log.includes('⚠️') || log.includes('取消'),
                  'log-info': log.includes('⏳') || log.includes('⏱️') || log.includes('📊') || log.includes('🚀') || log.includes('正在')
                }"
              >
                {{ log }}
              </div>
            </div>
          </el-scrollbar>
        </div>
      </div>

      <template #footer>
        <template v-if="isRunning">
          <el-button @click="pauseCurrentExecution" type="warning">
            <el-icon><VideoPause /></el-icon> 暂停
          </el-button>
          <el-button @click="cancelWorkflow" type="danger">
            <el-icon><SwitchButton /></el-icon> 终止
          </el-button>
        </template>
        <el-button
          v-if="!isRunning && runResult"
          type="primary"
          @click="() => { showProgressDialog = false; openResultDialog() }"
        >
          查看结果
        </el-button>
        <el-button @click="forceCloseProgressDialog">
          关闭
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
            <el-table-column label="AI分析" min-width="200" show-overflow-tooltip>
              <template #default="{ row }">
                <div class="ai-analysis-cell" v-if="getAiAnalysis(row)">
                  <el-popover placement="left" width="400" trigger="hover">
                    <template #reference>
                      <span class="ai-analysis-preview">{{ getAiAnalysis(row).slice(0, 40) }}...</span>
                    </template>
                    <div class="ai-analysis-full" v-html="formatResult(getAiAnalysis(row))"></div>
                  </el-popover>
                </div>
                <span v-else class="text-muted">-</span>
              </template>
            </el-table-column>
          </el-table>
        </div>

        <div class="result-tips">
          <el-alert
            title="投资提示"
            type="info"
            :closable="false"
          />
        </div>
      </div>
      <template #footer>
        <el-button @click="showRunDialog = false">关闭</el-button>
      </template>
    </el-dialog>

    <!-- 量化多因子选股结果对话框 -->
    <el-dialog v-model="showQuantResultDialog" title="量化多因子选股 — 筛选结果" width="1200px" top="2vh">
      <div v-if="quantResult" class="quant-result">


        <!-- Summary -->
        <div class="quant-summary">
          <div class="qs-item">
            <div class="qs-value">{{ quantResult.total_analyzed || 0 }}</div>
            <div class="qs-label">分析股票数</div>
          </div>
          <div class="qs-item">
            <div class="qs-value">{{ quantResult.after_filter || 0 }}</div>
            <div class="qs-label">通过硬性过滤</div>
          </div>
          <div class="qs-item">
            <div class="qs-value">{{ quantResult.result_count || 0 }}</div>
            <div class="qs-label">最终入选 Top30</div>
          </div>
          <div class="qs-item">
            <div class="qs-value">{{ (quantResult.duration || 0).toFixed(1) }}s</div>
            <div class="qs-label">执行耗时</div>
          </div>
        </div>

        <!-- Result Table -->
        <el-table
          v-if="quantResult.results && quantResult.results.length > 0"
          :data="quantResult.results"
          stripe
          border
          max-height="560"
          row-key="code"
        >
          <el-table-column prop="rank" label="排名" width="60" align="center">
            <template #default="{ row }">
              <el-tag
                :type="row.rank <= 3 ? 'danger' : row.rank <= 10 ? 'warning' : 'info'"
                size="small"
              >{{ row.rank }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="code" label="代码" width="90">
            <template #default="{ row }">
              <el-tag type="info" size="small">{{ row.code }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="name" label="名称" width="100" show-overflow-tooltip />
          <el-table-column prop="total_score" label="综合评分" width="90" align="center">
            <template #default="{ row }">
              <el-tag
                :type="row.total_score >= 70 ? 'success' : row.total_score >= 60 ? 'warning' : 'info'"
                size="large"
              >{{ row.total_score }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="各维度评分" width="260">
            <template #default="{ row }">
              <div class="quant-score-badges">
                <el-tooltip content="基本面评分(权重30%)" placement="top">
                  <el-tag size="small" :type="row.fundamental_score >= 70 ? 'success' : 'info'">基:{{ row.fundamental_score }}</el-tag>
                </el-tooltip>
                <el-tooltip content="技术面评分(权重25%)" placement="top">
                  <el-tag size="small" :type="row.technical_score >= 70 ? 'success' : 'info'">技:{{ row.technical_score }}</el-tag>
                </el-tooltip>
                <el-tooltip content="资金面评分(权重20%)" placement="top">
                  <el-tag size="small" :type="row.fund_flow_score >= 70 ? 'success' : 'info'">资:{{ row.fund_flow_score }}</el-tag>
                </el-tooltip>
                <el-tooltip content="估值面评分(权重15%)" placement="top">
                  <el-tag size="small" :type="row.valuation_score >= 70 ? 'success' : 'info'">估:{{ row.valuation_score }}</el-tag>
                </el-tooltip>
              </div>
            </template>
          </el-table-column>
          <el-table-column prop="industry" label="行业" width="100" show-overflow-tooltip />
          <el-table-column label="市值(亿)" width="80" align="right">
            <template #default="{ row }">{{ row.market_cap_yi || '-' }}</template>
          </el-table-column>
          <el-table-column label="PE" width="70" align="right">
            <template #default="{ row }">{{ row.pe ?? '-' }}</template>
          </el-table-column>
          <el-table-column label="PB" width="70" align="right">
            <template #default="{ row }">{{ row.pb ?? '-' }}</template>
          </el-table-column>
          <el-table-column label="ROE%" width="75" align="right">
            <template #default="{ row }">{{ row.roe ?? '-' }}</template>
          </el-table-column>
          <el-table-column prop="reason" label="选股理由" min-width="180" show-overflow-tooltip />
          <el-table-column label="因子分析" width="80" align="center">
            <template #default="{ row }">
              <el-button type="primary" size="small" text @click="openFactorRadar(row)">
                <el-icon><View /></el-icon>
              </el-button>
            </template>
          </el-table-column>
        </el-table>
      </div>
      <template #footer>
        <el-button @click="showQuantResultDialog = false">关闭</el-button>
      </template>
    </el-dialog>

    <!-- 因子雷达图 dialog -->
    <el-dialog v-model="showFactorRadarDialog" :title="'因子分析 — ' + (factorRadarStock?.name || '')" width="500px" top="10vh">
      <div v-if="factorRadarStock" style="height:380px">
        <VChart :option="factorRadarOptions" autoresize style="height:100%;width:100%" />
      </div>
      <template #footer>
        <el-button @click="showFactorRadarDialog = false">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Plus, Edit, Delete, VideoPlay, VideoPause, Clock, Timer,
  Files, DocumentCopy, Loading, CircleCheck, CircleClose, Warning, SwitchButton, Refresh, View,
  DeleteFilled, Search, CopyDocument
} from '@element-plus/icons-vue'
import { workflowApi, type Workflow, type WorkflowResult, type WorkflowTemplate, type WorkflowExecution } from '@/api/workflow'
import WorkflowCanvas from '@/components/WorkflowCanvas/index.vue'
import { fmtDateTime } from '@/utils/format'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { RadarChart } from 'echarts/charts'
import { RadarComponent, TooltipComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
use([RadarChart, RadarComponent, TooltipComponent, CanvasRenderer])

const loading = ref(false)
const activeTab = ref('list')
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
const currentExecutionId = ref('')
const currentExecution = ref<WorkflowExecution | null>(null)
let pollingTimer: number | null = null

const showQuantResultDialog = ref(false)
const quantResult = ref<any>(null)

const showFactorRadarDialog = ref(false)
const factorRadarStock = ref<any>(null)
const factorRadarOptions = computed(() => {
  const s = factorRadarStock.value
  if (!s) return {}
  const dims = [
    { name: '基本面', value: s.fundamental_score ?? 50 },
    { name: '技术面', value: s.technical_score ?? 50 },
    { name: '资金面', value: s.fund_flow_score ?? 50 },
    { name: '估值面', value: s.valuation_score ?? 50 },
    { name: '衍生因子', value: s.mining_score ?? 50 },
  ]
  return {
    tooltip: { trigger: 'item' as const },
    radar: {
      indicator: dims.map(d => ({ name: d.name, max: 100 })),
      center: ['50%', '55%'],
      radius: '65%',
      axisName: { color: '#606266', fontSize: 13 },
      splitArea: { areaStyle: { color: ['rgba(64,158,255,0.02)', 'rgba(64,158,255,0.05)'] } },
    },
    series: [{
      type: 'radar',
      data: [{ value: dims.map(d => d.value), name: s.name || s.code }],
      areaStyle: { color: 'rgba(64,158,255,0.2)' },
      lineStyle: { color: '#409EFF', width: 2 },
      itemStyle: { color: '#409EFF' },
    }],
  }
})

const loadingExecutions = ref(false)
const allExecutions = ref<any[]>([])
const selectedExecutions = ref<any[]>([])
const cleaningUp = ref(false)

const runningCount = computed(() => {
  return allExecutions.value.filter(e => e.status === 'running' || e.status === 'pending').length
})

const completedCount = computed(() => {
  return allExecutions.value.filter(e => e.status === 'completed').length
})

const failedCount = computed(() => {
  return allExecutions.value.filter(e => e.status === 'failed').length
})

const successRate = computed(() => {
  const total = allExecutions.value.filter(e => e.status === 'completed' || e.status === 'failed').length
  if (total === 0) return 100
  return Math.round((completedCount.value / total) * 100)
})

const executionFilter = ref('')
const executionStatusFilter = ref('')
const executionDateRange = ref<string[]>([])

const filteredExecutions = computed(() => {
  let result = allExecutions.value

  if (executionFilter.value) {
    const keyword = executionFilter.value.toLowerCase()
    result = result.filter(e =>
      (e.workflow_name || e.workflow_id || '').toLowerCase().includes(keyword)
    )
  }

  if (executionStatusFilter.value) {
    result = result.filter(e => e.status === executionStatusFilter.value)
  }

  if (executionDateRange.value && executionDateRange.value.length === 2) {
    const [startDate, endDate] = executionDateRange.value
    result = result.filter(e => {
      const execDate = e.started_at?.split(' ')[0] || ''
      return execDate >= startDate && execDate <= endDate
    })
  }

  return result
})

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

async function duplicateWorkflow(workflow: Workflow) {
  try {
    const newWorkflow = {
      name: `${workflow.name} (副本)`,
      description: workflow.description,
      nodes: workflow.nodes,
      edges: workflow.edges,
      tags: workflow.tags
    }
    await workflowApi.create(newWorkflow)
    ElMessage.success('复制成功')
    await loadWorkflows()
  } catch (err: any) {
    ElMessage.error(err.message || '复制失败')
  }
}

async function pollExecutionProgress(workflowId: string, executionId: string) {
  try {
    const res = await workflowApi.getExecutionProgress(workflowId, executionId)
    if (res.data?.success) {
      const execution = res.data.data
      currentExecution.value = execution
      runProgress.value = Math.round(execution.progress || 0)

      // Append only NEW steps, never replace the whole log (preserves startup messages)
      const steps: any[] = execution.steps || []
      const existingStepCount = runLogs.value.filter((l: string) => l.startsWith('[')).length
      if (steps.length > existingStepCount) {
        const icon = execution.status === 'completed' ? '✅' : execution.status === 'failed' ? '❌' : '⏳'
        for (let i = existingStepCount; i < steps.length; i++) {
          const step = steps[i]
          runLogs.value.push(
            `[${new Date(step.timestamp).toLocaleTimeString('zh-CN')}] ${icon} ${step.node_label}: ${step.step}`
          )
        }
      }

      if (execution.status === 'running' || execution.status === 'pending') {
        pollingTimer = window.setTimeout(() => pollExecutionProgress(workflowId, executionId), 3000)
      } else {
        isRunning.value = false
        stopPolling()

        if (execution.status === 'completed' && execution.result) {
          runResult.value = execution.result
          runLogs.value.push(`✅ 工作流执行成功`)
          runLogs.value.push(`📈 筛选出 ${execution.result.result_count || 0} 只符合条件的股票`)
          runLogs.value.push(`⏱️ 总耗时: ${(execution.result.duration || 0).toFixed(2)} 秒`)
          showProgressDialog.value = false
          if (execution.result.result_type === 'quant_multi_factor') {
            quantResult.value = execution.result
            showQuantResultDialog.value = true
          } else {
            showRunDialog.value = true
          }
        } else if (execution.status === 'failed') {
          runLogs.value.push(`❌ 执行失败: ${execution.error || '未知错误'}`)
          ElMessage.error(execution.error || '工作流执行失败')
        } else if (execution.status === 'cancelled') {
          runLogs.value.push(`⚠️ 执行已取消`)
          ElMessage.warning('工作流已取消')
        }

        await loadWorkflows()
      }
    }
  } catch (e: any) {
    console.error('Poll progress failed:', e)
  }
}

function stopPolling() {
  if (pollingTimer) {
    clearTimeout(pollingTimer)
    pollingTimer = null
  }
}

async function runWorkflow(workflow: Workflow) {
  runLogs.value = []
  runProgress.value = 0
  isRunning.value = true
  currentExecutionId.value = ''
  currentExecution.value = null
  showProgressDialog.value = true

  try {
    addLog(`🚀 正在启动工作流: ${workflow.name}`)
    addLog(`📊 工作流包含 ${workflow.nodes.length} 个节点`)

    const res = await workflowApi.run(workflow.id)

    if (res.data?.success) {
      const data = res.data
      currentExecutionId.value = data.execution_id
      addLog(`✅ 工作流已启动 (ID: ${data.execution_id})`)
      addLog(`⏳ 正在执行中，请稍候...`)

      pollExecutionProgress(workflow.id, data.execution_id)
    } else {
      const errorMsg = res.data?.error || '启动失败'
      addLog(`❌ 启动失败: ${errorMsg}`)
      ElMessage.error(errorMsg)
      isRunning.value = false
    }
  } catch (e: any) {
    const errorMsg = e?.response?.data?.error || e.message || '运行失败'
    addLog(`❌ 执行失败: ${errorMsg}`)
    ElMessage.error(errorMsg)
    isRunning.value = false
  }
}

async function cancelWorkflow() {
  if (!currentExecutionId.value) return

  try {
    await ElMessageBox.confirm('确定要取消当前执行的工作流吗？', '取消确认', {
      confirmButtonText: '确定取消',
      cancelButtonText: '继续执行',
      type: 'warning'
    })

    const workflow = workflows.value.find(w => w.id === currentExecution.value?.workflow_id)
    if (workflow) {
      await workflowApi.cancelExecution(workflow.id, currentExecutionId.value)
      addLog(`⚠️ 已请求取消执行...`)
    }
  } catch {
    // cancelled or continue
  }
}

async function loadExecutionHistory() {
  loadingExecutions.value = true
  try {
    const historyData: any[] = []
    for (const workflow of workflows.value) {
      try {
        const res = await workflowApi.listExecutions(workflow.id, 10)
        const executions = res.data?.data || []
        for (const exec of executions) {
          historyData.push({
            ...exec,
            workflow_name: workflow.name
          })
        }
      } catch {
        // skip errors
      }
    }
    historyData.sort((a, b) => {
      const timeA = a.started_at || ''
      const timeB = b.started_at || ''
      return timeB.localeCompare(timeA)
    })
    allExecutions.value = historyData
  } catch {
    ElMessage.error('加载执行历史失败')
  } finally {
    loadingExecutions.value = false
  }
}

async function stopExecution(execution: any) {
  try {
    await ElMessageBox.confirm(
      '终止后无法恢复，确定要永久终止该工作流吗？',
      '终止确认',
      { confirmButtonText: '确定终止', cancelButtonText: '取消', type: 'warning' }
    )
    await workflowApi.cancelExecution(execution.workflow_id, execution.id)
    ElMessage.success('已请求终止执行')
    execution.status = 'cancelled'
    execution.finished_at = new Date().toISOString()
  } catch {
    // cancelled
  }
}

async function pauseExecution(execution: any) {
  try {
    await workflowApi.pauseExecution(execution.workflow_id, execution.id)
    ElMessage.success('暂停请求已发送，将在当前步骤完成后暂停')
    execution.status = 'paused'
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.error || '暂停失败')
  }
}

async function pauseCurrentExecution() {
  if (!currentExecutionId.value || !currentExecution.value) return
  try {
    await workflowApi.pauseExecution(currentExecution.value.workflow_id, currentExecutionId.value)
    ElMessage.success('暂停请求已发送，将在当前步骤完成后暂停')
    isRunning.value = false
    stopPolling()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.error || '暂停失败')
  }
}

async function resumeExecution(execution: any) {
  try {
    await ElMessageBox.confirm(
      `继续从暂停点（步骤 ${execution.paused_node_idx + 1}）恢复执行吗？`,
      '继续执行',
      { confirmButtonText: '继续', cancelButtonText: '取消', type: 'info' }
    )
    const res = await workflowApi.resumeExecution(execution.workflow_id, execution.id)
    if (res.data?.success) {
      ElMessage.success('已恢复执行')
      execution.status = 'running'
      execution.finished_at = undefined
      // Open progress dialog to monitor
      runLogs.value = []
      runProgress.value = Math.round(execution.progress || 0)
      currentExecutionId.value = execution.id
      currentExecution.value = execution
      isRunning.value = true
      showProgressDialog.value = true
      addLog(`▶️ 从步骤 ${execution.paused_node_idx + 1} 继续执行...`)
      pollExecutionProgress(execution.workflow_id, execution.id)
    } else {
      ElMessage.error(res.data?.error || '恢复失败')
    }
  } catch {
    // cancelled
  }
}

function openResultDialog() {
  if (!runResult.value) return
  if (runResult.value.result_type === 'quant_multi_factor') {
    quantResult.value = runResult.value
    showQuantResultDialog.value = true
  } else {
    showRunDialog.value = true
  }
}

function viewExecutionResult(execution: any) {
  if (execution.result) {
    runResult.value = execution.result
    if (execution.result.result_type === 'quant_multi_factor') {
      quantResult.value = execution.result
      showQuantResultDialog.value = true
    } else {
      showRunDialog.value = true
    }
  }
}

async function viewExecutionProgress(execution: any) {
  runLogs.value = []
  runProgress.value = Math.round(execution.progress || 0)
  currentExecutionId.value = execution.id
  currentExecution.value = execution
  showProgressDialog.value = true

  // Only set isRunning if the task is actually still running
  const alreadyDone = !['running', 'pending'].includes(execution.status)
  isRunning.value = !alreadyDone

  if (execution.steps && execution.steps.length > 0) {
    for (const step of execution.steps) {
      const icon = execution.status === 'completed' ? '✅' : execution.status === 'failed' ? '❌' : '⏳'
      runLogs.value.push(`[${new Date(step.timestamp).toLocaleTimeString('zh-CN')}] ${icon} ${step.node_label}: ${step.step}`)
    }
  }

  if (alreadyDone) {
    const icon = execution.status === 'completed' ? '✅' : execution.status === 'failed' ? '❌' : '⚠️'
    addLog(`${icon} 任务已${getStatusLabel(execution.status)}`)
    if (execution.status === 'completed' && execution.result) {
      runResult.value = execution.result
    }
    return
  }

  addLog(`⏳ 正在监控工作流执行...`)

  const pollId = window.setInterval(async () => {
    try {
      const res = await workflowApi.getExecutionProgress(execution.workflow_id, execution.id)
      if (res.data?.success) {
        const latest = res.data.data
        currentExecution.value = latest
        runProgress.value = Math.round(latest.progress || 0)

        const latestStepCount = latest.steps?.length || 0
        const currentLogCount = runLogs.value.filter(l => l.startsWith('[')).length
        if (latestStepCount > currentLogCount && latest.steps) {
          for (let i = currentLogCount; i < latestStepCount; i++) {
            const step = latest.steps[i]
            const icon = latest.status === 'completed' ? '✅' : latest.status === 'failed' ? '❌' : '⏳'
            runLogs.value.push(`[${new Date(step.timestamp).toLocaleTimeString('zh-CN')}] ${icon} ${step.node_label}: ${step.step}`)
          }
        }

        if (latest.status !== 'running' && latest.status !== 'pending') {
          clearInterval(pollId)
          isRunning.value = false

          if (latest.status === 'completed' && latest.result) {
            runResult.value = latest.result
            runLogs.value.push(`✅ 工作流执行成功`)
            runLogs.value.push(`📈 筛选出 ${latest.result.result_count || 0} 只符合条件的股票`)
            runLogs.value.push(`⏱️ 总耗时: ${(latest.result.duration || 0).toFixed(2)} 秒`)
          } else if (latest.status === 'failed') {
            runLogs.value.push(`❌ 执行失败: ${latest.error || '未知错误'}`)
          } else if (latest.status === 'cancelled') {
            runLogs.value.push(`⚠️ 执行已取消`)
          }
        }
      }
    } catch {
      clearInterval(pollId)
      isRunning.value = false
    }
  }, 3000)
}

function getStatusType(status: string) {
  const map: Record<string, string> = {
    'pending': 'info',
    'running': 'warning',
    'completed': 'success',
    'failed': 'danger',
    'cancelled': 'info',
    'paused': 'warning'
  }
  return map[status] || 'info'
}

function getStatusLabel(status: string) {
  const map: Record<string, string> = {
    'pending': '等待中',
    'running': '执行中',
    'completed': '已完成',
    'failed': '失败',
    'cancelled': '已取消',
    'paused': '已暂停'
  }
  return map[status] || status
}

function formatDateTime(dateStr: string) {
  return fmtDateTime(dateStr) || ''
}

function addLog(message: string) {
  const timestamp = new Date().toLocaleTimeString('zh-CN')
  runLogs.value.push(`[${timestamp}] ${message}`)
}

function forceCloseProgressDialog() {
  stopPolling()
  isRunning.value = false
  showProgressDialog.value = false
}

function handleProgressClose() {
  // Always allow closing; if task was running in background it continues
  stopPolling()
  isRunning.value = false
}

function handleSelectionChange(selection: any[]) {
  selectedExecutions.value = selection
}

function getExecutionRowClass({ row }: { row: any }) {
  if (row.status === 'cancelled') return 'row-cancelled'
  if (row.status === 'failed') return 'row-failed'
  if (row.status === 'paused') return 'row-paused'
  return ''
}

async function deleteSingleExecution(execution: any) {
  try {
    await ElMessageBox.confirm(
      `确定删除该执行记录吗？`,
      '删除确认',
      { confirmButtonText: '删除', cancelButtonText: '取消', type: 'warning' }
    )
    const workflowId = execution.workflow_id
    await workflowApi.deleteExecution(workflowId, execution.id)
    ElMessage.success('删除成功')
    allExecutions.value = allExecutions.value.filter(e => e.id !== execution.id)
  } catch {
    // cancelled
  }
}

async function batchDeleteExecutions() {
  if (selectedExecutions.value.length === 0) return
  try {
    await ElMessageBox.confirm(
      `确定删除选中的 ${selectedExecutions.value.length} 条记录吗？`,
      '批量删除确认',
      { confirmButtonText: '删除', cancelButtonText: '取消', type: 'warning' }
    )
    // Group by workflow_id for batch API calls
    const byWorkflow: Record<string, string[]> = {}
    for (const exec of selectedExecutions.value) {
      const wid = exec.workflow_id
      if (!byWorkflow[wid]) byWorkflow[wid] = []
      byWorkflow[wid].push(exec.id)
    }
    for (const [wid, ids] of Object.entries(byWorkflow)) {
      await workflowApi.batchDeleteExecutions(wid, ids)
    }
    ElMessage.success(`已删除 ${selectedExecutions.value.length} 条记录`)
    const deletedIds = new Set(selectedExecutions.value.map((e: any) => e.id))
    allExecutions.value = allExecutions.value.filter(e => !deletedIds.has(e.id))
    selectedExecutions.value = []
  } catch {
    // cancelled
  }
}

async function clearAllExecutions() {
  if (allExecutions.value.length === 0) {
    ElMessage.info('没有执行记录')
    return
  }
  try {
    await ElMessageBox.confirm(
      `确定清空所有 ${allExecutions.value.length} 条执行历史吗？此操作不可恢复！`,
      '清空确认',
      { confirmButtonText: '全部清空', cancelButtonText: '取消', type: 'warning' }
    )
    // Group by workflow_id and clear all
    const workflowIds = [...new Set(allExecutions.value.map((e: any) => e.workflow_id))]
    for (const wid of workflowIds) {
      try {
        await workflowApi.clearAllExecutions(wid)
      } catch { /* skip */ }
    }
    ElMessage.success('已清空所有历史记录')
    allExecutions.value = []
    selectedExecutions.value = []
  } catch {
    // cancelled
  }
}

async function cleanupZombies() {
  cleaningUp.value = true
  try {
    const res = await workflowApi.cleanupStaleExecutions(30)
    const cleaned = res.data?.cleaned || 0
    ElMessage.success(cleaned > 0 ? `已清理 ${cleaned} 条僵尸任务` : '没有需要清理的僵尸任务')
    await loadExecutionHistory()
  } catch (e: any) {
    ElMessage.error('清理失败: ' + (e?.response?.data?.error || e.message))
  } finally {
    cleaningUp.value = false
  }
}

function formatStepTime(timestamp: string): string {
  if (!timestamp) return ''
  try {
    return new Date(timestamp).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
  } catch {
    return ''
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

function getAiAnalysis(row: any): string {
  if (!row.metadata) return ''
  // Find any ai_*_analysis key in metadata
  const keys = Object.keys(row.metadata).filter(k => k.startsWith('ai_') && k.endsWith('_analysis'))
  if (keys.length === 0) return row.metadata.ai_analysis || ''
  return row.metadata[keys[0]] || ''
}

function formatResult(text: string): string {
  return text
    .replace(/\n/g, '<br>')
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
}

function openFactorRadar(row: any) {
  factorRadarStock.value = row
  showFactorRadarDialog.value = true
}

onMounted(async () => {
  await loadWorkflows()
  await Promise.all([loadTemplates(), loadExecutionHistory()])
})

onUnmounted(() => {
  stopPolling()
})

</script>

<style scoped>
.workflow-page {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.workflow-tabs {
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: 8px;
  padding: 16px;
}

.workflow-tabs :deep(.el-tabs__header) {
  margin-bottom: 16px;
}

.workflow-tabs :deep(.el-tabs__nav-wrap::after) {
  background-color: var(--border-strong);
}

.execution-badge {
  margin-left: 4px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  padding: 16px 20px;
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: 8px;
}

.header-left h2 {
  margin: 0 0 8px 0;
  font-size: 20px;
  font-weight: 600;
  color: var(--text-primary);
}

.subtitle {
  margin: 0;
  font-size: 14px;
  color: var(--text-muted);
}

.header-actions {
  display: flex;
  gap: 12px;
}

.workflow-list-card {
  background: var(--bg-card);
  border: 1px solid var(--border-color);
}

.workflow-list-card :deep(.el-card__header) {
  border-bottom: 1px solid var(--border-color);
  padding: 12px 16px;
  color: var(--text-primary);
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
  color: var(--text-muted);
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16px;
  padding: 48px;
  color: var(--text-muted);
}

.workflow-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 16px;
  padding: 16px 0;
}

.workflow-card {
  background: var(--border-color);
  border: 1px solid var(--border-strong);
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
  color: var(--text-primary);
}

.workflow-description {
  margin: 0 0 12px 0;
  font-size: 13px;
  color: var(--text-muted);
  line-height: 1.5;
}

.workflow-meta {
  display: flex;
  gap: 16px;
  margin-bottom: 8px;
  font-size: 12px;
  color: var(--text-faint);
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
  border-top: 1px solid var(--border-strong);
}

.template-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 16px;
}

.template-card {
  background: var(--border-color);
  border: 1px solid var(--border-strong);
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
  color: var(--text-primary);
}

.template-card p {
  margin: 0 0 12px 0;
  font-size: 13px;
  color: var(--text-muted);
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
  background: var(--border-color);
  border-radius: 8px;
}

.stat-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.stat-label {
  font-size: 12px;
  color: var(--text-muted);
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
  background: var(--border-color);
  border-radius: 8px;
  margin: 16px 0;
}

.summary-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 20px;
  background: var(--border-strong);
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
  color: var(--text-muted);
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

.execution-stats {
  display: flex;
  gap: 12px;
  padding: 12px 0;
  margin-bottom: 16px;
}

.stat-card {
  flex: 1;
  padding: 16px;
  background: var(--border-color);
  border-radius: 8px;
  text-align: center;
  border-left: 3px solid #409eff;
}

.stat-card.stat-total { border-left-color: #409eff; }
.stat-card.stat-completed { border-left-color: #67c23a; }
.stat-card.stat-running { border-left-color: #e6a23c; }
.stat-card.stat-failed { border-left-color: #f56c6c; }
.stat-card.stat-success-rate { border-left-color: #909eff; }

.stat-value {
  font-size: 28px;
  font-weight: 700;
  color: var(--text-primary);
}

.stat-label {
  font-size: 12px;
  color: var(--text-muted);
  margin-top: 4px;
}

.execution-filters {
  display: flex;
  gap: 12px;
  margin-bottom: 16px;
  padding: 12px;
  background: var(--border-color);
  border-radius: 8px;
}

.execution-actions {
  display: flex;
  gap: 4px;
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
  color: var(--text-muted);
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
  color: var(--text-primary);
  padding: 8px 0;
}

.current-step {
  margin-bottom: 8px;
}

.log-container {
  border: 1px solid var(--border-strong);
  border-radius: 8px;
  padding: 12px;
  background: var(--bg-elevated);
}

.log-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-muted);
  margin-bottom: 12px;
  padding-bottom: 8px;
  border-bottom: 1px solid var(--border-color);
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
  background: var(--bg-soft);
  color: var(--text-secondary);
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

.log-warning {
  background: rgba(230, 162, 60, 0.1);
  color: #e6a23c;
  border-left: 3px solid #e6a23c;
}

.execution-table :deep(.el-table__header th) {
  background: var(--border-color) !important;
}

.execution-actions {
  display: flex;
  gap: 8px;
}

.result-link {
  color: #409eff;
  cursor: pointer;
  font-size: 13px;
}

.result-link:hover {
  text-decoration: underline;
}

.text-muted {
  color: var(--text-muted);
}

.ai-analysis-preview {
  font-size: 12px;
  color: #a0cfff;
  cursor: pointer;
  line-height: 1.4;
}

.ai-analysis-full {
  font-size: 13px;
  line-height: 1.6;
  color: #303133;
  max-height: 300px;
  overflow-y: auto;
}

/* Cancelled row style */
.execution-table :deep(.row-cancelled td) {
  color: var(--text-muted) !important;
  opacity: 0.7;
}

.execution-table :deep(.row-failed td) {
  color: #f56c6c !important;
}

.execution-table :deep(.row-paused td) {
  color: #e6a23c !important;
}

/* Step list in progress dialog */
.step-list-container {
  border: 1px solid var(--border-strong);
  border-radius: 8px;
  padding: 12px;
  background: var(--bg-elevated);
  margin-bottom: 8px;
}

.step-list-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-muted);
  margin-bottom: 8px;
  padding-bottom: 6px;
  border-bottom: 1px solid var(--border-color);
}

.step-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.step-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 8px;
  border-radius: 4px;
  background: var(--bg-soft);
  font-size: 12px;
  color: var(--text-secondary);
}

.step-item.step-current {
  background: rgba(64, 158, 255, 0.1);
  border-left: 2px solid #409eff;
}

.step-index {
  color: var(--text-faint);
  font-size: 11px;
  min-width: 18px;
}

.step-node {
  color: #409eff;
  font-weight: 500;
  min-width: 80px;
  flex-shrink: 0;
}

.step-desc {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.step-time {
  color: var(--text-faint);
  font-size: 11px;
  flex-shrink: 0;
}

/* 量化多因子选股结果样式 */
.quant-result {
  padding: 4px 0;
}
.quant-summary {
  display: flex;
  gap: 20px;
  margin-bottom: 20px;
  background: #f5f7fa;
  border-radius: 8px;
  padding: 16px 24px;
}
.qs-item {
  text-align: center;
  flex: 1;
}
.qs-value {
  font-size: 24px;
  font-weight: 700;
  color: #409eff;
}
.qs-label {
  font-size: 12px;
  color: var(--text-muted);
  margin-top: 4px;
}
.quant-score-badges {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}
</style>
