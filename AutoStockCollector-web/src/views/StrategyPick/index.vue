<template>
  <div class="sp-page">
    <!-- 顶部控制栏 -->
    <div class="sp-toolbar">
      <div class="sp-title-group">
        <span class="sp-title">策略选股</span>
        <span class="sp-subtitle">多策略合并 · 多Agent深度分析 · 投资哲学辩论</span>
      </div>
      <div class="sp-controls">
        <el-input v-model.number="topN" size="small" style="width:110px" :disabled="running">
          <template #prepend>精选 N</template>
        </el-input>
        <el-button type="primary" size="small" :loading="running" :disabled="running || selectedIds.length === 0" @click="runPick">
          {{ running ? '分析中...' : '开始选股' }}
        </el-button>
        <el-button v-if="running" type="danger" size="small" @click="cancelPick">取消</el-button>
        <el-button size="small" :loading="loading" @click="loadResult">刷新结果</el-button>
        <el-dropdown v-if="historyItems.length" trigger="click" @command="loadHistoryResult">
          <el-button size="small">
            历史结果<el-icon class="el-icon--right"><ArrowDown /></el-icon>
          </el-button>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item v-for="h in historyItems" :key="h.run_id" :command="h.run_id">
                <span class="sp-history-item">
                  <span>
                    <span class="sp-history-time">{{ h.created_at ? dayjs(h.created_at).format('MM-DD HH:mm') : '未知' }}</span>
                    <span class="sp-history-meta">{{ h.selected_count || 0 }}只</span>
                    <span v-if="h.portfolio_metrics" class="sp-history-meta" style="color:#3f9d70">
                      {{ h.portfolio_metrics.avg_composite.toFixed(1) }}分 · {{ h.portfolio_metrics.industry_count }}行业
                    </span>
                    <span class="sp-history-meta" style="display:block;line-height:1.4">
                      {{ (h.pick_config?.strategy_ids || []).map(id => strategyNameMap[id] || id.slice(0,6)).join('、').slice(0, 40) }}{{ (h.pick_config?.strategy_ids?.length || 0) > 1 ? '…' : '' }}
                      <template v-if="h.pick_config?.agent_ids?.length"> | {{ h.pick_config.agent_ids.length }}Agent</template>
                    </span>
                  </span>
                  <el-checkbox v-if="compareRunIds.length < 3 || compareRunIds.includes(h.run_id)" size="small" :model-value="compareRunIds.includes(h.run_id)" @click.stop="toggleCompare(h.run_id)" class="sp-compare-check" />
                </span>
              </el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
        <el-button v-if="compareRunIds.length >= 2" size="small" type="warning" @click="showCompareDialog = true">对比 {{ compareRunIds.length }} 个结果</el-button>
      </div>
    </div>

    <!-- 折叠选择区 -->
    <el-collapse v-model="collapseActive" accordion class="sp-collapse-group">
      <el-collapse-item name="strategy">
        <template #title>
          <div class="sp-selector-header sp-collapse-header">
            <span class="sp-selector-title">选择策略</span>
            <el-button size="small" text @click.stop="toggleAll">全选 / 反选</el-button>
          </div>
        </template>
        <div v-loading="strategiesLoading" class="sp-strategy-list">
          <div v-if="strategies.length === 0 && !strategiesLoading" class="sp-empty-hint">暂无可用策略，请先在策略管理中创建</div>
          <label v-for="s in strategies" :key="s._id" class="sp-strategy-chip" :class="{ checked: selectedIds.includes(s._id) }">
            <input type="checkbox" :value="s._id" v-model="selectedIds" class="sp-check" />
            <span class="sp-chip-name">{{ s.name }}</span>
            <span class="sp-chip-desc">{{ s.description || '无描述' }}</span>
          </label>
        </div>
      </el-collapse-item>

      <el-collapse-item name="llm">
        <template #title>
          <div class="sp-selector-header sp-collapse-header">
            <span class="sp-selector-title">AI 分析 Agent（深度分析用）</span>
            <el-button size="small" text @click.stop="toggleAllByType('llm')">全选 / 反选</el-button>
          </div>
        </template>
        <div v-loading="agentsLoading" class="sp-strategy-list">
          <div v-if="llmAgents.length === 0 && !agentsLoading" class="sp-empty-hint">暂无可用 Agent</div>
          <label v-for="a in llmAgents" :key="a.id" class="sp-strategy-chip agent-chip" :class="{ checked: selectedAgentIds.includes(a.id) }">
            <input type="checkbox" :value="a.id" v-model="selectedAgentIds" class="sp-check" />
            <span class="sp-chip-name">{{ a.name }}</span>
            <span class="sp-chip-desc">{{ a.description || a.role || '' }}</span>
          </label>
        </div>
      </el-collapse-item>

      <el-collapse-item name="philosophy">
        <template #title>
          <div class="sp-selector-header sp-collapse-header">
            <span class="sp-selector-title">投资哲学 Agent（辩论阶段用）</span>
            <el-button size="small" text @click.stop="toggleAllByType('philosophy')">全选 / 反选</el-button>
          </div>
        </template>
        <div v-loading="agentsLoading" class="sp-strategy-list">
          <div v-if="philosophyAgents.length === 0 && !agentsLoading" class="sp-empty-hint">暂无可用投资哲学 Agent</div>
          <label v-for="a in philosophyAgents" :key="a.id" class="sp-strategy-chip philosophy-chip" :class="{ checked: selectedPhilosophyIds.includes(a.id) }">
            <input type="checkbox" :value="a.id" v-model="selectedPhilosophyIds" class="sp-check" />
            <span class="sp-chip-name">{{ a.name }}</span>
            <span class="sp-chip-desc">{{ a.description || a.archetype || '' }}</span>
          </label>
        </div>
      </el-collapse-item>
    </el-collapse>

    <!-- 进度条 -->
    <div v-if="progress.is_running || showDoneTip" class="sp-progress-box">
      <template v-if="progress.is_running">
        <div class="sp-progress-header">策略选股执行中</div>
        <el-progress :percentage="progress.progress" :stroke-width="14" :color="'#5a7af0'" />
        <div class="sp-progress-status">{{ progress.status }}</div>
      </template>
      <template v-else-if="showDoneTip">
        <div class="sp-progress-done">策略选股完成，结果已更新</div>
      </template>
    </div>

    <!-- 定时运行提示 -->
    <div class="sp-cron-bar">
      <el-icon style="margin-right:4px"><Clock /></el-icon>
      定时运行：交易日 08:55 · 12:00 · 14:30
    </div>

    <!-- 统计信息 -->
    <div v-if="result" class="sp-meta">
      <span>策略数：{{ result.strategy_count }}</span>
      <span>合并候选：{{ result.merged_count }} 只</span>
      <span>精选：{{ result.selected_count }} 只</span>
      <span>更新：{{ fmtTime(result.timestamp) }}</span>
    </div>

    <!-- 策略入选统计 -->
    <div v-if="result?.strategy_stats && Object.keys(result.strategy_stats).length" class="sp-stats">
      <span v-for="(count, name) in result.strategy_stats" :key="name" class="sp-stat-tag">
        {{ name }} <b>{{ count }}</b> 只
      </span>
    </div>

    <!-- 买卖信号 -->
    <!-- 持仓组合建议 -->
    <div v-if="result?.portfolio_suggestion?.positions?.length" class="sp-portfolio-suggestion">
      <div class="sp-ps-header">
        <span class="sp-ps-title">持仓组合建议</span>
        <span class="sp-ps-meta">{{ result.portfolio_suggestion.total_count }}只 · {{ result.portfolio_suggestion.industry_count }}个行业 · 最大行业{{ result.portfolio_suggestion.max_industry_pct }}%</span>
        <el-button size="small" type="success" :loading="buyingAll" @click="buyAllPositions">全部一键买入</el-button>
      </div>
      <div class="sp-ps-table-wrap">
        <table class="sp-ps-table">
          <thead><tr><th>代码</th><th>名称</th><th>行业</th><th>评分</th><th>动作</th><th>建议仓位</th><th>累计</th><th style="width:80px">操作</th></tr></thead>
          <tbody>
            <tr v-for="pos in result.portfolio_suggestion.positions" :key="pos.code" class="sp-ps-row">
              <td class="num">{{ pos.code }}</td>
              <td>{{ pos.name }}</td>
              <td>{{ pos.industry }}</td>
              <td><span class="sp-score-badge num" :style="{color: scoreColor(pos.composite)}">{{ pos.composite.toFixed(1) }}</span></td>
              <td><span class="sp-sig-badge" :class="'sp-sig-' + pos.action">{{ pos.action }}</span></td>
              <td><span class="sp-ps-weight num">{{ pos.weight }}%</span></td>
              <td><span class="sp-ps-cum num">{{ pos.cumulative }}%</span></td>
              <td><el-button size="small" type="success" plain :loading="buying[pos.code]" @click.stop="buyPosition(pos)">一键买入</el-button></td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- 再平衡建议 -->
    <div v-if="result" class="sp-rebalance-panel">
      <div class="sp-ps-header">
        <span class="sp-ps-title">再平衡建议（缓冲带 5%）</span>
        <el-button size="small" :loading="rebalanceLoading" @click="loadRebalance">生成建议</el-button>
        <el-button size="small" type="primary"
                   :disabled="!rebalance || !rebalance.orders.length"
                   :loading="executingAll" @click="execAll">全部执行</el-button>
      </div>
      <div v-if="rebalance?.message" class="sp-empty-hint" style="padding:8px 14px 14px">{{ rebalance.message }}</div>
      <div v-else-if="rebalance" class="sp-ps-table-wrap">
        <table class="sp-ps-table">
          <thead><tr><th>动作</th><th>股票</th><th>股数</th><th>现价</th><th>目标/当前权重</th><th>说明</th><th style="width:80px">操作</th></tr></thead>
          <tbody>
            <tr v-for="o in rebalance.orders" :key="o.code" class="sp-ps-row">
              <td><span class="sp-sig-badge" :class="o.action === 'buy' ? 'sp-sig-买入' : 'sp-sig-卖出'">{{ o.action === 'buy' ? '买入' : '卖出' }}</span></td>
              <td>{{ o.name }}（{{ o.code }}）</td>
              <td class="num">{{ o.shares }}</td>
              <td class="num">{{ o.price != null ? o.price.toFixed(2) : '-' }}</td>
              <td class="num">{{ o.target_weight }}% / {{ o.current_weight }}%</td>
              <td class="sp-signal-reason" :title="o.reason">{{ o.reason }}</td>
              <td>
                <el-button v-if="!o.skipped" size="small" plain :loading="executing[o.code]" @click.stop="execOne(o)">执行</el-button>
                <el-tooltip v-else :content="o.skip_reason || ''" placement="top">
                  <el-tag type="info" size="small">已跳过</el-tag>
                </el-tooltip>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <div v-if="result?.trade_signals?.length" class="sp-signals-box">
      <div class="sp-signals-header">
        <span class="sp-signals-title">买卖信号建议（基于当前持仓）</span>
      </div>
      <div class="sp-signals-summary">
        <span v-for="g in signalGroups" :key="g.action" class="sp-signal-summary-tag" :class="'sp-ss-' + g.action">{{ g.action }} {{ g.count }} 只</span>
      </div>
      <div class="sp-signals-table-wrap">
        <table class="sp-signals-table">
          <thead><tr>
            <th>代码</th><th>名称</th><th>信号</th><th>优先级</th><th>综合评分</th><th>当前持仓</th><th>理由</th>
          </tr></thead>
          <tbody>
              <tr v-for="s in personalSignals" :key="s.code" class="sp-signal-row">
              <td><span class="sp-code" @click.stop="goAnalysis(s.code)">{{ s.code }}</span></td>
              <td>{{ s.name }}</td>
              <td><span class="sp-sig-badge" :class="'sp-sig-' + s.action">{{ s.action }}</span></td>
              <td><span class="sp-priority" :class="'sp-pri-' + s.priority">{{ s.priority }}</span></td>
              <td>{{ s.composite != null ? Math.round(s.composite) : '-' }}</td>
              <td>{{ s.current_shares > 0 ? s.current_shares + ' 股' : '-' }}</td>
              <td class="sp-signal-reason">{{ s.reason }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- 结果表格 -->
    <el-table v-if="result?.picks?.length" :data="result.picks" stripe class="sp-table"
              :row-class-name="tableRowClass" @row-click="showDetail">
      <el-table-column type="index" label="#" width="42" align="center" />
      <el-table-column prop="code" label="代码" width="100">
        <template #default="{ row }">
          <span class="sp-code num" @click.stop="goAnalysis(row.code)">{{ row.code }}</span>
        </template>
      </el-table-column>
      <el-table-column prop="name" label="名称" width="90" />
      <el-table-column prop="industry" label="行业" width="80" show-overflow-tooltip />
      <el-table-column label="综合" width="140" sortable :sort-by="(r: StrategyPickItem) => r.composite">
        <template #default="{ row }">
          <el-progress :percentage="Math.round(row.composite)" :color="scoreColor(row.composite)" :stroke-width="8" />
        </template>
      </el-table-column>
      <el-table-column label="基本" width="55" align="center" sortable :sort-by="(r: StrategyPickItem) => r.scores?.fundamental ?? 0">
        <template #default="{ row }">
          <span v-if="row.scores?.fundamental != null" class="sp-score-cell num" :style="{ color: dimColor(row.scores.fundamental) }">{{ Math.round(row.scores.fundamental) }}</span>
          <span v-else class="sp-na">-</span>
        </template>
      </el-table-column>
      <el-table-column label="技术" width="55" align="center" sortable :sort-by="(r: StrategyPickItem) => r.scores?.technical ?? 0">
        <template #default="{ row }">
          <span v-if="row.scores?.technical != null" class="sp-score-cell num" :style="{ color: dimColor(row.scores.technical) }">{{ Math.round(row.scores.technical) }}</span>
          <span v-else class="sp-na">-</span>
        </template>
      </el-table-column>
      <el-table-column label="资金" width="55" align="center" sortable :sort-by="(r: StrategyPickItem) => r.scores?.fund_flow ?? 0">
        <template #default="{ row }">
          <span v-if="row.scores?.fund_flow != null" class="sp-score-cell num" :style="{ color: dimColor(row.scores.fund_flow) }">{{ Math.round(row.scores.fund_flow) }}</span>
          <span v-else class="sp-na">-</span>
        </template>
      </el-table-column>
      <el-table-column label="估值" width="55" align="center" sortable :sort-by="(r: StrategyPickItem) => r.scores?.valuation ?? 0">
        <template #default="{ row }">
          <span v-if="row.scores?.valuation != null" class="sp-score-cell num" :style="{ color: dimColor(row.scores.valuation) }">{{ Math.round(row.scores.valuation) }}</span>
          <span v-else class="sp-na">-</span>
        </template>
      </el-table-column>
      <el-table-column label="来源策略" min-width="160">
        <template #default="{ row }">
          <span v-for="(s, i) in (row.from_strategies || [row.from_strategy])" :key="i" class="sp-strategy-tag">{{ s }}</span>
        </template>
      </el-table-column>
      <el-table-column label="来源" width="56" align="center">
        <template #default="{ row }">
          <span v-if="row.source === 'llm'" class="sp-source-tag sp-tag-ai">AI</span>
          <span v-else class="sp-source-tag sp-tag-factor">因子</span>
        </template>
      </el-table-column>
      <el-table-column label="操作建议" width="80" align="center">
        <template #default="{ row }">
          <span class="sp-action-tag" :class="actionClass(row)">{{ getAction(row) }}</span>
        </template>
      </el-table-column>
      <el-table-column label="辩论" width="65" align="center" sortable :sort-by="(r: StrategyPickItem) => r.debate_consensus?.avg_score ?? 0">
        <template #default="{ row }">
          <span v-if="row.debate_consensus" class="sp-debate-cell" :class="debateClass(row.debate_consensus)">
            {{ debateLabel(row.debate_consensus) }}
          </span>
          <span v-else class="sp-na">-</span>
        </template>
      </el-table-column>
    </el-table>

    <!-- AI 分析详情弹窗 -->
    <el-dialog v-model="detailDialogVisible" :title="detailPick?.code + ' ' + detailPick?.name" width="700px" top="5vh" class="sp-detail-dialog" destroy-on-close>
      <template v-if="detailPick">
        <div class="sp-detail-source">策略: {{ detailPick.from_strategy }} | 策略评分: {{ detailPick.strategy_score }}</div>

        <div v-if="detailPick.score_details && Object.keys(detailPick.score_details).length" class="sp-detail-body">
          <div class="sp-dim-table">
            <div class="sp-dim-tr sp-dim-th">
              <span class="sp-dim-td sp-dim-td-label">维度</span>
              <span class="sp-dim-td sp-dim-td-score">评分</span>
              <span class="sp-dim-td sp-dim-td-weight">权重</span>
              <span class="sp-dim-td sp-dim-td-contrib">贡献</span>
              <span class="sp-dim-td sp-dim-td-bar">进度</span>
            </div>
            <div v-for="dim in orderedDimensions" :key="dim.key" class="sp-dim-tr">
              <span class="sp-dim-td sp-dim-td-label">{{ dim.label }}</span>
              <span class="sp-dim-td sp-dim-td-score">
                <span class="sp-score-badge" :style="{color: scoreColor(dim.score), fontWeight: 600}">{{ dim.score }}</span>
              </span>
              <span class="sp-dim-td sp-dim-td-weight">{{ Math.round(dim.weight * 100) }}%</span>
              <span class="sp-dim-td sp-dim-td-contrib">{{ dim.contribution }}</span>
              <span class="sp-dim-td sp-dim-td-bar">
                <el-progress :percentage="Math.round(dim.score)" :color="scoreColor(dim.score)" :stroke-width="6" />
              </span>
            </div>
          </div>
          <div v-for="dim in orderedDimensionsWithDetails" :key="dim.key" class="sp-dim-detail-row">
            <div class="sp-dim-detail-toggle" @click="dim.expanded = !dim.expanded">
              <el-icon :class="{ 'is-expanded': dim.expanded }" style="transition:transform .2s;vertical-align:middle"><ArrowDown /></el-icon>
              {{ dim.label }}明细
            </div>
            <div v-if="dim.expanded" class="sp-dim-detail-body">
              <div v-for="(val, key) in dim.details" :key="key" class="sp-dim-detail-item">
                <span class="sp-dim-detail-key">{{ key }}</span>
                <span class="sp-dim-detail-val">{{ typeof val === 'number' ? val.toFixed(2) : val }}</span>
              </div>
              <el-empty v-if="!Object.keys(dim.details).length" description="无明细数据" :image-size="40" />
            </div>
          </div>
        </div>

        <div v-if="agentAnalyses.length" class="sp-detail-advice">
          <div v-for="(agent, ai) in agentAnalyses" :key="ai" class="sp-agent-advice">
            <div class="sp-agent-advice-header">{{ agent.agent_name || 'AI分析' }}</div>
            <div v-if="agent.recommendation" class="sp-advice-section">
              <div class="sp-advice-label">操作建议：</div>
              <div class="sp-advice-text md-content" v-html="renderMd(agent.recommendation)"></div>
            </div>
            <div v-if="agent.risk_factors?.length" class="sp-risk-section">
              <div class="sp-advice-label">风险提示：</div>
              <div v-for="(risk, ri) in agent.risk_factors" :key="ri" class="sp-risk-item">{{ risk }}</div>
            </div>
          </div>
        </div>
        <div v-else-if="detailPick.llm" class="sp-detail-advice">
          <div v-if="detailPick.llm.recommendation" class="sp-advice-section">
            <div class="sp-advice-label">AI分析建议：</div>
            <div class="sp-advice-text md-content" v-html="renderMd(detailPick.llm.recommendation)"></div>
          </div>
          <div v-if="detailPick.llm.risk_factors?.length" class="sp-risk-section">
            <div class="sp-advice-label">风险提示：</div>
            <div v-for="(risk, i) in detailPick.llm.risk_factors" :key="i" class="sp-risk-item">{{ risk }}</div>
          </div>
        </div>

        <!-- 辩论信号 -->
        <div v-if="detailPick.debate_signals?.length" class="sp-debate-section">
          <div class="sp-debate-section-title">投资哲学辩论结果</div>
          <div v-if="detailPick.debate_consensus" class="sp-consensus-bar">
            <span>共识度 {{ (detailPick.debate_consensus.consensus_level * 100).toFixed(0) }}%</span>
            <span>看多 {{ detailPick.debate_consensus.positive_count }}</span>
            <span>看空 {{ detailPick.debate_consensus.negative_count }}</span>
            <span>中立 {{ detailPick.debate_consensus.neutral_count }}</span>
            <span>平均分 {{ detailPick.debate_consensus.avg_score.toFixed(1) }}</span>
          </div>
          <div v-for="s in detailPick.debate_signals" :key="s.agent_id" class="sp-signal-row">
            <div class="sp-signal-header">
              <span class="sp-signal-name">{{ s.philosophy }}</span>
              <span class="sp-signal-action" :class="'sp-sig-' + s.action">{{ s.action }}</span>
              <span class="sp-signal-score">评分 {{ s.score.toFixed(0) }}</span>
              <span class="sp-signal-conf">信心 {{ (s.confidence * 100).toFixed(0) }}%</span>
            </div>
            <div class="sp-signal-body">
              <div class="sp-signal-reasoning">{{ s.reasoning }}</div>
              <div v-if="s.key_factors?.length" class="sp-signal-factors">
                <span v-for="(f, fi) in s.key_factors" :key="fi" class="sp-signal-factor">{{ f }}</span>
              </div>
              <div v-if="s.risk_warnings?.length" class="sp-signal-risks">
                <span v-for="(w, wi) in s.risk_warnings" :key="wi" class="sp-signal-warning">{{ w }}</span>
              </div>
            </div>
          </div>
        </div>
      </template>
    </el-dialog>

    <!-- 辩论总览 -->
    <div v-if="result?.debate_results?.length" class="sp-debate-overview">
      <div class="sp-debate-overview-toggle" @click="debateOverviewExpanded = !debateOverviewExpanded">
        <span>辩论结果总览（{{ result.debate_results.length }} 只股票，含投资哲学 Agent 投票）</span>
        <svg class="sp-summary-svg" :class="{ 'is-expanded': debateOverviewExpanded }" viewBox="0 0 12 12" width="12" height="12">
          <path d="M2 4l4 4 4-4" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
      </div>
      <div v-if="debateOverviewExpanded" class="sp-debate-overview-body">
        <div v-for="d in result.debate_results" :key="d.code" class="sp-debate-stock-row">
          <div class="sp-debate-stock-title">
            <span class="sp-code" @click.stop="goAnalysis(d.code)">{{ d.code }}</span>
            <span class="sp-debate-stock-name">{{ d.name }}</span>
            <span v-if="d.consensus" class="sp-debate-stock-consensus" :class="debateClass(d.consensus)">{{ debateLabel(d.consensus) }}</span>
            <span v-if="d.consensus" class="sp-debate-stock-meta">共识度 {{ (d.consensus.consensus_level * 100).toFixed(0) }}% | {{ d.consensus.agent_count }}位Agent | +{{ d.consensus.positive_count }}/{{ d.consensus.negative_count }}/{{ d.consensus.neutral_count }}</span>
          </div>
          <div v-if="d.signals?.length" class="sp-debate-vote-list">
            <span v-for="s in d.signals" :key="s.agent_id" class="sp-vote-tag" :class="'sp-vote-' + s.action" :title="s.reasoning">{{ s.philosophy }}: {{ s.action }}</span>
          </div>
        </div>
      </div>
    </div>

    <!-- 辩论综合结论 -->
    <div v-if="result?.debate_summary" class="sp-ai-summary">
      <div class="sp-summary-toggle" @click="summaryExpanded = !summaryExpanded">
        <span>辩论综合结论</span>
        <svg class="sp-summary-svg" :class="{ 'is-expanded': summaryExpanded }" viewBox="0 0 12 12" width="12" height="12">
          <path d="M2 4l4 4 4-4" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
      </div>
      <div v-if="summaryExpanded" class="sp-summary-body md-content" v-html="renderMd(result.debate_summary)"></div>
    </div>

    <!-- 组合分析 -->
    <div v-if="result?.portfolio_metrics && result.picks?.length" class="sp-portfolio-section">
      <div class="sp-summary-toggle" @click="portfolioExpanded = !portfolioExpanded">
        <span>组合分析</span>
        <svg class="sp-summary-svg" :class="{ 'is-expanded': portfolioExpanded }" viewBox="0 0 12 12" width="12" height="12">
          <path d="M2 4l4 4 4-4" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
      </div>
      <div v-if="portfolioExpanded" class="sp-portfolio-body">
        <!-- 指标卡片 -->
        <div class="sp-metrics-row">
          <div class="sp-metric-card"><span class="sp-metric-value">{{ result.portfolio_metrics.avg_composite }}</span><span class="sp-metric-label">平均评分</span></div>
          <div class="sp-metric-card"><span class="sp-metric-value">{{ result.portfolio_metrics.composite_std }}</span><span class="sp-metric-label">评分标准差</span></div>
          <div class="sp-metric-card"><span class="sp-metric-value">{{ result.portfolio_metrics.composite_max }}~{{ result.portfolio_metrics.composite_min }}</span><span class="sp-metric-label">评分范围</span></div>
          <div class="sp-metric-card"><span class="sp-metric-value">{{ result.portfolio_metrics.industry_count }}</span><span class="sp-metric-label">覆盖行业</span></div>
          <div class="sp-metric-card"><span class="sp-metric-value">{{ result.portfolio_metrics.industry_hhi }}</span><span class="sp-metric-label">行业集中度</span></div>
          <div class="sp-metric-card"><span class="sp-metric-value">{{ result.portfolio_metrics.top_industry_pct }}%</span><span class="sp-metric-label">{{ result.portfolio_metrics.top_industry }}占比</span></div>
        </div>
        <!-- 图表 -->
        <div class="sp-charts-row">
          <div class="sp-chart-box">
            <div class="sp-chart-title">行业分布</div>
            <v-chart :option="industryPieOption" style="height:260px" autoresize />
          </div>
          <div class="sp-chart-box">
            <div class="sp-chart-title">多维度评分对比</div>
            <v-chart :option="dimRadarOption" style="height:260px" autoresize />
          </div>
        </div>
      </div>
    </div>

    <!-- 对比弹窗 -->
    <el-dialog v-model="showCompareDialog" title="历史结果对比" width="800px" top="5vh" class="sp-compare-dialog" destroy-on-close>
      <div v-loading="compareLoading" class="sp-compare-body">
        <div v-for="(cr, ci) in compareResults" :key="cr.run_id" class="sp-compare-col">
          <div class="sp-compare-header">{{ cr.created_at ? dayjs(cr.created_at).format('MM-DD HH:mm') : '未知' }}</div>
          <div class="sp-metrics-row" style="flex-direction:column;gap:4px">
            <div class="sp-metric-card" style="flex:none"><span class="sp-metric-value">{{ cr.portfolio_metrics?.avg_composite ?? '-' }}</span><span class="sp-metric-label">平均分</span></div>
            <div class="sp-metric-card" style="flex:none"><span class="sp-metric-value">{{ cr.portfolio_metrics?.composite_std ?? '-' }}</span><span class="sp-metric-label">标准差</span></div>
            <div class="sp-metric-card" style="flex:none"><span class="sp-metric-value">{{ cr.portfolio_metrics?.industry_count ?? '-' }}</span><span class="sp-metric-label">行业数</span></div>
            <div class="sp-metric-card" style="flex:none"><span class="sp-metric-value">{{ cr.portfolio_metrics?.industry_hhi ?? '-' }}</span><span class="sp-metric-label">集中度</span></div>
          </div>
          <v-chart v-if="cr.picks?.length" :option="comparePieOption(cr.picks)" style="height:200px" autoresize />
        </div>
      </div>
    </el-dialog>

    <el-empty v-if="!result?.picks?.length && !loading && !running" description="选择策略后点击「开始选股」" />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted, onBeforeUnmount } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { renderMd } from '@/utils/markdown'
import dayjs from 'dayjs'
import { strategyPickApi, type StrategyPickItem, type StrategyPickResult, type StrategyPickProgress, type StrategyPickHistoryItem, type PortfolioMetrics, type StrategyPickAgent, type DebateConsensus, type PortfolioSuggestionPosition, type RebalanceOrder, type RebalanceAdvice } from '@/api/strategyPick'
import { paperApi } from '@/api/paper'
import type { StrategyRule } from '@/types'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { PieChart, RadarChart } from 'echarts/charts'
import { TooltipComponent, LegendComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import { getChartTheme as ct } from '@/utils/chartTheme'
use([PieChart, RadarChart, TooltipComponent, LegendComponent, CanvasRenderer])



const router = useRouter()

const strategies = ref<StrategyRule[]>([])
const strategyNameMap = computed(() => {
  const m: Record<string, string> = {}
  for (const s of strategies.value) {
    if (s._id) m[s._id] = s.name
  }
  return m
})
const strategiesLoading = ref(false)
const selectedIds = ref<string[]>([])
const agents = ref<StrategyPickAgent[]>([])
const agentsLoading = ref(false)
const llmAgents = computed(() => agents.value.filter(a => a.type === 'llm'))
const philosophyAgents = computed(() => agents.value.filter(a => a.type === 'philosophy'))
const selectedAgentIds = ref<string[]>([])
const selectedPhilosophyIds = ref<string[]>([])
const result = ref<StrategyPickResult | null>(null)
const loading = ref(false)
const running = ref(false)
const topN = ref(20)
const showDoneTip = ref(false)
const summaryExpanded = ref(true)
const debateOverviewExpanded = ref(true)
const portfolioExpanded = ref(true)
const collapseActive = ref<string[]>([])
const detailDialogVisible = ref(false)
const detailPick = ref<StrategyPickItem | null>(null)

const STORAGE_KEY = 'strategy_pick_config'

function saveConfig() {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({
      selectedIds: selectedIds.value,
      selectedAgentIds: selectedAgentIds.value,
      selectedPhilosophyIds: selectedPhilosophyIds.value,
      topN: topN.value,
    }))
  } catch { /* ignore */ }
}

function loadConfig(): Record<string, any> | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    return raw ? JSON.parse(raw) : null
  } catch { return null }
}

const progress = ref<StrategyPickProgress>({ is_running: false, progress: 0, status: '' })
const historyItems = ref<StrategyPickHistoryItem[]>([])
const compareRunIds = ref<string[]>([])
const showCompareDialog = ref(false)
const compareResults = ref<StrategyPickResult[]>([])
const compareLoading = ref(false)
let eventSource: EventSource | null = null
let progressTimer: ReturnType<typeof setInterval> | null = null
let sseTimeout: ReturnType<typeof setTimeout> | null = null

const DIM_LABELS: Record<string, string> = {
  fundamental: '基本面', technical: '技术面', fund_flow: '资金面', valuation: '估值面',
}
const DIM_ORDER = ['fundamental', 'technical', 'fund_flow', 'valuation']

const orderedDimensions = computed(() => {
  const pick = detailPick.value
  if (!pick?.score_details) return []
  return DIM_ORDER.filter(k => k in pick.score_details).map(k => {
    const d = pick.score_details[k]
    return {
      key: k,
      label: DIM_LABELS[k] || k,
      score: d.score ?? 0,
      weight: d.normalized_weight ?? d.weight ?? 0,
      contribution: d.contribution ?? 0,
    }
  })
})
const orderedDimensionsWithDetails = computed(() => {
  const pick = detailPick.value
  if (!pick?.score_details) return []
  return DIM_ORDER.filter(k => k in pick.score_details && pick.score_details[k].details).map(k => {
    const d = pick.score_details[k]
    return {
      key: k,
      label: DIM_LABELS[k] || k,
      details: typeof d.details === 'object' && d.details ? d.details : {},
      expanded: false,
    }
  })
})

const agentAnalyses = computed(() => {
  return detailPick.value?.agent_analyses || (detailPick.value?.llm ? [{
    agent_id: '', agent_name: '',
    summary: detailPick.value.llm.summary || '',
    recommendation: detailPick.value.llm.recommendation || '',
    risk_factors: detailPick.value.llm.risk_factors || [],
  }] : [])
})

// 当前用户持仓（用于重算买卖信号）
const userPositions = ref<Map<string, number>>(new Map())
let positionsFetched = false

async function fetchUserPositions() {
  if (positionsFetched) return
  positionsFetched = true
  try {
    const posResult = await paperApi.getPositions()
    const map = new Map<string, number>()
    for (const p of posResult.positions) map.set(p.code, p.shares)
    userPositions.value = map
  } catch {
    // ignore
  }
}

// 根据当前用户持仓重算买卖信号
function computePersonalSignals(picks: any[], held: Map<string, number>) {
  const actions: { code: string; name: string; action: string; priority: string; composite: number; current_shares: number; reason: string }[] = []
  for (const p of picks) {
    const code = p.code
    const composite = p.composite ?? 0
    const shares = held.get(code) ?? 0
    let action: string
    if (shares > 0) {
      if (composite >= 72) action = '加仓'
      else if (composite >= 55) action = '持有'
      else action = '减仓'
    } else {
      if (composite >= 72) action = '买入'
      else if (composite >= 55) action = '关注'
      else action = '观望'
    }
    const priority = composite >= 72 ? '高' : composite >= 55 ? '中' : '低'
    actions.push({
      code, name: p.name || '',
      action, priority, composite,
      current_shares: shares,
      reason: `综合评分${Math.round(composite)}，${shares > 0 ? `持仓${shares}股` : '未持仓'}，建议${action}`,
    })
  }
  // 持有但未入选的 → 卖出
  for (const [code, shares] of held) {
    if (shares <= 0) continue
    if (!picks.some((p: any) => p.code === code)) {
      const pick = picks.find((p: any) => p.code === code)
      actions.push({
        code, name: pick?.name || code,
        action: '卖出', priority: '高', composite: 0,
        current_shares: shares,
        reason: `未入选本次选股结果，持仓${shares}股建议卖出清仓`,
      })
    }
  }
  const order: Record<string, number> = { '买入': 0, '加仓': 1, '关注': 2, '持有': 3, '观望': 4, '减仓': 5, '卖出': 6 }
  actions.sort((a, b) => (order[a.action] ?? 99) - (order[b.action] ?? 99) || (b.composite ?? 0) - (a.composite ?? 0))
  return actions
}

// 根据选股结果与"执行者用户"判断是否需要重算信号
const personalSignals = computed(() => {
  const picks = result.value?.picks
  if (!picks?.length) return result.value?.trade_signals || []
  const held = userPositions.value
  if (held.size === 0) return result.value?.trade_signals || []
  return computePersonalSignals(picks, held)
})

const signalGroups = computed(() => {
  const signals = personalSignals.value
  const map: Record<string, number> = {}
  for (const s of signals) {
    map[s.action] = (map[s.action] || 0) + 1
  }
  const order = ['买入', '加仓', '关注', '持有', '观望', '减仓', '卖出']
  return order.filter(a => map[a]).map(a => ({ action: a, count: map[a] }))
})

const theme = computed(() => ct())
const palette = ['#5a7af0', '#d05a51', '#3f9d70', '#c9943a', '#909399', '#36cfc9', '#b37feb', '#ff85c0', '#597ef7', '#95de64']

const industryPieOption = computed(() => {
  const picks = result.value?.picks || []
  const map: Record<string, number> = {}
  for (const p of picks) {
    const ind = p.industry || '未知'
    map[ind] = (map[ind] || 0) + 1
  }
  const sorted = Object.entries(map).sort((a, b) => b[1] - a[1])
  return {
    tooltip: { trigger: 'item', formatter: '{b}: {c}只 ({d}%)' },
    legend: { bottom: 0, textStyle: { color: theme.value.legendText }, itemWidth: 10, itemHeight: 10 },
    series: [{
      type: 'pie', radius: ['30%', '65%'], center: ['50%', '45%'],
      avoidLabelOverlap: true,
      label: { show: false },
      emphasis: { label: { show: true, fontSize: 13, fontWeight: 'bold' } },
      data: sorted.map(([name, count], i) => ({ name, value: count, itemStyle: { color: palette[i % palette.length] } })),
    }],
  }
})

const dimRadarOption = computed(() => {
  const pm = result.value?.portfolio_metrics
  if (!pm?.dimension_avg) return {}
  const dims = Object.keys(pm.dimension_avg)
  const maxVal = Math.max(...Object.values(pm.dimension_avg), 80)
  return {
    tooltip: {},
    radar: {
      indicator: dims.map(k => ({ name: DIM_LABELS[k] || k, max: Math.ceil(maxVal / 10) * 10 + 10 })),
      center: ['50%', '50%'], radius: '65%',
      axisName: { color: theme.value.textColorStrong },
      splitArea: { areaStyle: { color: ['rgba(90,122,240,0.02)', 'rgba(90,122,240,0.06)'] } },
    },
    series: [{
      type: 'radar',
      data: [{ value: dims.map(k => pm.dimension_avg[k]), name: '平均分', areaStyle: { color: 'rgba(90,122,240,0.2)' }, lineStyle: { color: '#5a7af0', width: 2 }, itemStyle: { color: '#5a7af0' } }],
    }],
  }
})

watch([selectedIds, selectedAgentIds, selectedPhilosophyIds, topN], saveConfig, { deep: true })

function toggleAll() {
  if (selectedIds.value.length === strategies.value.length) {
    selectedIds.value = []
  } else {
    selectedIds.value = strategies.value.map(s => s._id)
  }
}

function toggleAllByType(type: 'llm' | 'philosophy') {
  const list = type === 'llm' ? llmAgents.value : philosophyAgents.value
  const ids = list.map(a => a.id)
  const target = type === 'llm' ? selectedAgentIds : selectedPhilosophyIds
  if (target.value.length === ids.length && ids.every(id => target.value.includes(id))) {
    target.value = []
  } else {
    target.value = ids
  }
}

function debateLabel(c: DebateConsensus | null): string {
  if (!c) return '无'
  if (c.tendency > 0.15) return '偏多'
  if (c.tendency < -0.15) return '偏空'
  return '分歧'
}

function debateClass(c: DebateConsensus | null): string {
  if (!c) return ''
  if (c.tendency > 0.15) return 'sp-debate-bull'
  if (c.tendency < -0.15) return 'sp-debate-bear'
  return 'sp-debate-neutral'
}

function scoreColor(v: number): string {
  if (v >= 70) return '#3a8a52'
  if (v >= 50) return '#d0a020'
  return '#a04040'
}

function dimColor(v: number): string {
  if (v >= 80) return '#52c41a'
  if (v >= 60) return '#faad14'
  return '#ff4d4f'
}

function getAction(pick: StrategyPickItem): string {
  const c = pick.composite ?? 0
  if (c >= 72) return '强烈推荐'
  if (c >= 60) return '建议关注'
  if (c >= 50) return '可以关注'
  return '观望'
}

const ACTION_CLASS: Record<string, string> = {
  '强烈推荐': 'sp-action-green',
  '建议关注': 'sp-action-lightgreen',
  '可以关注': 'sp-action-orange',
  '观望': 'sp-action-gray',
}
function actionClass(pick: StrategyPickItem): string {
  return ACTION_CLASS[getAction(pick)] || 'sp-action-gray'
}

function tableRowClass() {
  return ['sp-row-clickable']
}

function fmtTime(t: string): string {
  return t ? dayjs(t).format('MM-DD HH:mm') : '--'
}

function goAnalysis(code: string) {
  router.push({ path: '/stock-analysis', query: { code } })
}

function showDetail(row: StrategyPickItem) {
  detailPick.value = row
  detailDialogVisible.value = true
}

const buying = ref<Record<string, boolean>>({})
const buyingAll = ref(false)

async function calcShares(price: number, targetAmount: number): Promise<number> {
  const shares = Math.floor(targetAmount / price / 100) * 100
  return Math.max(shares, 0)
}

async function getPortfolioContext() {
  const [account, posResult] = await Promise.all([paperApi.getAccount(), paperApi.getPositions()])
  if (!account) throw new Error('获取账户信息失败')
  const cash = account.cash_balance
  const existingPositions = posResult.positions || []
  const existingValue = existingPositions.reduce((s, p) => s + p.market_value, 0)
  const totalPortfolio = cash + existingValue
  return { cash, totalPortfolio, existingPositions }
}

async function buyPosition(pos: PortfolioSuggestionPosition) {
  if (buying.value[pos.code]) return
  buying.value[pos.code] = true
  try {
    const priceInfo = await paperApi.getPrice(pos.code)
    if (!priceInfo) { ElMessage.error('获取实时价格失败'); return }
    const { price, is_trading_time } = priceInfo
    if (!is_trading_time) {
      const confirmed = await ElMessageBox.confirm(
        '当前非交易时间，获取的价格为最新收盘价。确认要下单？',
        '非交易时间', { confirmButtonText: '确认下单', cancelButtonText: '取消', type: 'warning' }
      ).catch(() => false)
      if (!confirmed) return
    }

    const { cash, totalPortfolio, existingPositions } = await getPortfolioContext()
    const existingPos = existingPositions.find(p => p.code === pos.code)
    const existingValue = existingPos ? existingPos.market_value : 0

    // target = totalPortfolio * weight% - existing position value
    const targetAmount = Math.max(0, totalPortfolio * pos.weight / 100 - existingValue)
    const buyAmount = Math.min(targetAmount, cash)
    const shares = await calcShares(price, buyAmount)
    if (shares < 100) { ElMessage.warning(`可用资金不足，最少需买入 100 股（约 ¥${(price * 100).toFixed(2)}）`); return }

    const amount = shares * price
    const confirmed = await ElMessageBox.confirm(
      `<div style="line-height:2">
        <div><b>${pos.name}</b>（${pos.code}）</div>
        <div>实时价格：<b>¥${price.toFixed(2)}</b></div>
        <div>建议仓位：${pos.weight}%</div>
        <div>可用资金：¥${cash.toFixed(2)}</div>
        <div>目标市值：¥${(totalPortfolio * pos.weight / 100).toFixed(2)}</div>
        <hr style="border:none;border-top:1px solid var(--border-color);margin:8px 0">
        <div>买入数量：<b>${shares} 股</b></div>
        <div>预计金额：<b>¥${amount.toFixed(2)}</b></div>
        <div>剩余资金：¥${(cash - amount).toFixed(2)}</div>
      </div>`,
      '确认买入',
      { confirmButtonText: '确认买入', cancelButtonText: '取消', dangerouslyUseHTMLString: true, type: 'info' }
    ).catch(() => false)
    if (!confirmed) return

    const trade = await paperApi.executeTrade({
      code: pos.code, action: 'buy', shares, price,
      ai_signal: { action: 'buy', reason: '策略选股组合建议', composite: pos.composite },
    })
    ElMessage.success(`已买入 ${pos.name} ${shares} 股，成交价 ¥${trade.price.toFixed(2)}`)
  } catch (e: any) {
    if (e?.message) ElMessage.error(e.message)
    else ElMessage.error('买入失败')
  } finally {
    buying.value[pos.code] = false
  }
}

async function buyAllPositions() {
  if (buyingAll.value) return
  buyingAll.value = true
  try {
    const positions = result.value?.portfolio_suggestion?.positions
    if (!positions?.length) { ElMessage.warning('暂无组合建议'); return }
    const { cash } = await getPortfolioContext()
    if (cash <= 0) { ElMessage.warning('可用资金为 0'); return }

    const totalWeight = positions.reduce((s, p) => s + p.weight, 0)
    if (totalWeight <= 0) { ElMessage.warning('无效的权重分配'); return }

    // fetch prices for all positions in parallel
    const priceResults = await Promise.all(
      positions.map(p => paperApi.getPrice(p.code).then(r => ({ code: p.code, info: r })))
    )
    const priceMap: Record<string, { price: number; is_trading_time: boolean }> = {}
    let anyNonTrading = false
    for (const r of priceResults) {
      if (!r.info) { ElMessage.error(`获取 ${r.code} 价格失败`); return }
      priceMap[r.code] = r.info
      if (!r.info.is_trading_time) anyNonTrading = true
    }
    if (anyNonTrading) {
      const ok = await ElMessageBox.confirm(
        '当前非交易时间，获取的价格为最新收盘价。确认要下单？',
        '非交易时间', { confirmButtonText: '确认下单', cancelButtonText: '取消', type: 'warning' }
      ).catch(() => false)
      if (!ok) return
    }

    // build order list: distribute cash by weight proportion
    const orders: { pos: PortfolioSuggestionPosition; shares: number; price: number; amount: number }[] = []
    let remainingCash = cash
    let remainingWeight = totalWeight

    for (let i = 0; i < positions.length; i++) {
      const pos = positions[i]
      const isLast = i === positions.length - 1
      const { price } = priceMap[pos.code]

      let targetAmount: number
      if (isLast) {
        targetAmount = remainingCash
      } else if (remainingWeight > 0) {
        targetAmount = remainingCash * pos.weight / remainingWeight
      } else {
        targetAmount = 0
      }

      const shares = Math.floor(targetAmount / price / 100) * 100
      if (shares >= 100) {
        const amount = shares * price
        orders.push({ pos, shares, price, amount })
        remainingCash -= amount
        remainingWeight -= pos.weight
      }
    }

    if (!orders.length) { ElMessage.warning('所有股票都不足 100 股，无法买入'); return }

    const orderRows = orders.map(o =>
      `<tr><td>${o.pos.code}</td><td>${o.pos.name}</td><td style="text-align:right">${o.shares}</td><td style="text-align:right">¥${o.price.toFixed(2)}</td><td style="text-align:right">¥${o.amount.toFixed(2)}</td></tr>`
    ).join('')
    const totalAmount = orders.reduce((s, o) => s + o.amount, 0)

    const confirmed = await ElMessageBox.confirm(
      `<div style="line-height:1.8">
        <div>可用资金：¥${cash.toFixed(2)}</div>
        <table style="width:100%;border-collapse:collapse;margin-top:8px;font-size:12px">
          <thead><tr style="border-bottom:1px solid var(--border-color)">
            <th style="text-align:left">代码</th><th style="text-align:left">名称</th><th style="text-align:right">数量</th><th style="text-align:right">价格</th><th style="text-align:right">金额</th>
          </tr></thead>
          <tbody>${orderRows}</tbody>
          <tfoot><tr style="border-top:1px solid var(--border-color);font-weight:700">
            <td colspan="4" style="text-align:right">合计</td>
            <td style="text-align:right">¥${totalAmount.toFixed(2)}</td>
          </tr></tfoot>
        </table>
        <div style="margin-top:8px">剩余资金：¥${(cash - totalAmount).toFixed(2)}</div>
      </div>`,
      '确认批量买入',
      { confirmButtonText: '确认买入', cancelButtonText: '取消', dangerouslyUseHTMLString: true, customStyle: { width: '520px' }, type: 'info' }
    ).catch(() => false)
    if (!confirmed) return

    // execute orders sequentially
    let success = 0
    for (const o of orders) {
      try {
        await paperApi.executeTrade({
          code: o.pos.code, action: 'buy', shares: o.shares, price: o.price,
          ai_signal: { action: 'buy', reason: '策略选股组合建议', composite: o.pos.composite },
        })
        success++
      } catch (e: any) {
        ElMessage.error(`${o.pos.name} 买入失败: ${e?.message || '未知错误'}`)
      }
    }
    ElMessage.success(`批量买入完成，成功 ${success}/${orders.length} 只`)
  } catch (e: any) {
    if (e?.message) ElMessage.error(e.message)
    else ElMessage.error('批量买入失败')
  } finally {
    buyingAll.value = false
  }
}

const rebalance = ref<RebalanceAdvice | null>(null)
const rebalanceLoading = ref(false)
const executing = ref<Record<string, boolean>>({})
const executingAll = ref(false)

async function loadRebalance() {
  rebalanceLoading.value = true
  try {
    const res = await strategyPickApi.getRebalanceAdvice(0.05)
    rebalance.value = res.data.data
  } catch {
    ElMessage.error('加载再平衡建议失败')
  } finally {
    rebalanceLoading.value = false
  }
}

async function execOne(o: RebalanceOrder) {
  if (o.skipped || !o.price) return
  executing.value[o.code] = true
  try {
    await paperApi.executeTrade({
      code: o.code, action: o.action, shares: o.shares,
      price: o.price, ai_signal: { reason: o.reason, position_advice: '再平衡建议' },
    })
    await loadRebalance() // 执行后刷新清单（现金/持仓已变）
  } catch (e: any) {
    ElMessage.error(`执行失败：${e?.response?.data?.error || e?.message || e}`)
  } finally {
    executing.value[o.code] = false
  }
}

async function execAll() {
  if (!rebalance.value) return
  executingAll.value = true
  try {
    // 先卖后买：卖出释放现金才够买
    const ordered = [...rebalance.value.orders].sort(
      (a, b) => (a.action === 'sell' ? 0 : 1) - (b.action === 'sell' ? 0 : 1),
    )
    for (const o of ordered) {
      if (o.skipped || !o.price) continue
      await execOne(o)
    }
  } finally {
    executingAll.value = false
  }
}

async function loadStrategies() {
  strategiesLoading.value = true
  try {
    const res = await strategyPickApi.getStrategies()
    strategies.value = res.data?.data || []
    selectedIds.value = strategies.value.map(s => s._id)
  } catch {
    ElMessage.error('加载策略列表失败')
  } finally {
    strategiesLoading.value = false
  }
}

async function loadAgents() {
  agentsLoading.value = true
  try {
    const res = await strategyPickApi.getAgents()
    agents.value = res.data?.data || []
    // 默认全选
    selectedAgentIds.value = agents.value.filter(a => a.type === 'llm').map(a => a.id)
    selectedPhilosophyIds.value = agents.value.filter(a => a.type === 'philosophy').map(a => a.id)
  } catch {
    ElMessage.error('加载 Agent 列表失败')
  } finally {
    agentsLoading.value = false
  }
}

async function loadResult() {
  loading.value = true
  try {
    const res = await strategyPickApi.getResult()
    result.value = res.data?.data || null
    if (result.value) fetchUserPositions()
  } catch {
    ElMessage.error('加载结果失败')
  } finally {
    loading.value = false
  }
}

async function loadHistory() {
  try {
    const res = await strategyPickApi.getHistory()
    historyItems.value = res.data?.data || []
  } catch { /* ignore */ }
}

async function loadHistoryResult(runId: string) {
  loading.value = true
  try {
    const res = await strategyPickApi.getResult(runId)
    const data = res.data?.data
    result.value = data || null
    if (data?.pick_config) {
      const cfg = data.pick_config
      const validStrategyIds = cfg.strategy_ids?.filter(id => strategies.value.some(s => s._id === id)) || []
      if (validStrategyIds.length) selectedIds.value = validStrategyIds
      if (cfg.agent_ids?.length) selectedAgentIds.value = cfg.agent_ids
      if (cfg.philosophy_ids?.length) selectedPhilosophyIds.value = cfg.philosophy_ids
      if (cfg.top_n) topN.value = cfg.top_n
    }
  } catch {
    ElMessage.error('加载历史结果失败')
  } finally {
    loading.value = false
  }
}

function startProgressPolling() {
  stopProgressPolling()
  progressTimer = setInterval(async () => {
    try {
      const res = await strategyPickApi.getProgress()
      const data = res.data?.data
      if (data) {
        progress.value = data
        if (data.is_running) running.value = true
        if (!data.is_running) {
          stopProgressPolling()
          if (data.progress >= 100) {
            running.value = false
            showDoneTip.value = true
            await Promise.all([loadResult(), loadHistory()])
            setTimeout(() => { showDoneTip.value = false }, 4000)
          } else {
            running.value = false
          }
        }
      }
    } catch { /* ignore */ }
  }, 2000)
}

function stopProgressPolling() {
  if (progressTimer) { clearInterval(progressTimer); progressTimer = null }
}

function startProgressSSE() {
  stopProgressSSE()
  stopProgressPolling()
  eventSource = new EventSource('/api/v1/strategy-pick/progress/stream')
  let received = false
  eventSource.onmessage = (event) => {
    received = true
    if (sseTimeout) { clearTimeout(sseTimeout); sseTimeout = null }
    try {
      const res = JSON.parse(event.data)
      const data = res?.data
      if (!data) return
      progress.value = data
      if (data.is_running) running.value = true
      if (!data.is_running) {
        stopProgressSSE()
        if (data.progress >= 100) {
          running.value = false
          showDoneTip.value = true
          Promise.all([loadResult(), loadHistory()])
          setTimeout(() => { showDoneTip.value = false }, 4000)
        } else {
          running.value = false
        }
      }
    } catch { /* ignore */ }
  }
  eventSource.onerror = () => {
    if (received) {
      // SSE was working but error occurred — stop
      stopProgressSSE()
      running.value = false
      progress.value = { is_running: false, progress: 0, status: '连接断开' }
    }
    // if never received, onerror is normal during connection; let the timeout handle fallback
  }
  // Fallback to polling if no SSE data within 3s
  sseTimeout = setTimeout(() => {
    if (!received) {
      stopProgressSSE()
      startProgressPolling()
    }
  }, 3000)
}

function stopProgressSSE() {
  if (eventSource) {
    eventSource.close()
    eventSource = null
  }
  if (sseTimeout) { clearTimeout(sseTimeout); sseTimeout = null }
}

async function runPick() {
  if (selectedIds.value.length === 0) {
    ElMessage.warning('请至少选择一个策略')
    return
  }
  running.value = true
  showDoneTip.value = false
  progress.value = { is_running: true, progress: 0, status: '启动中...' }
  try {
    const res = await strategyPickApi.run(selectedIds.value, topN.value, 15, selectedAgentIds.value, selectedPhilosophyIds.value)
    if (res.data?.success) {
      ElMessage.info(res.data.message || '策略选股已启动')
      startProgressSSE()
    } else {
      ElMessage.error(res.data?.error || '启动失败')
      running.value = false
      progress.value = { is_running: false, progress: 0, status: '' }
    }
  } catch {
    ElMessage.error('请求失败')
    running.value = false
    progress.value = { is_running: false, progress: 0, status: '' }
  }
}

async function cancelPick() {
  try {
    const res = await strategyPickApi.cancel()
    if (res.data?.success) {
      stopProgressSSE()
      stopProgressPolling()
      running.value = false
      progress.value = { is_running: false, progress: 0, status: '已取消' }
    }
  } catch {
    ElMessage.error('取消失败')
  }
}

function toggleCompare(runId: string) {
  const idx = compareRunIds.value.indexOf(runId)
  if (idx >= 0) {
    compareRunIds.value.splice(idx, 1)
  } else {
    if (compareRunIds.value.length >= 3) {
      ElMessage.warning('最多对比 3 个结果')
      return
    }
    compareRunIds.value.push(runId)
  }
  if (compareRunIds.value.length >= 2) {
    loadCompareResults()
  }
}

async function loadCompareResults() {
  compareLoading.value = true
  try {
    const results: StrategyPickResult[] = []
    for (const rid of compareRunIds.value) {
      const res = await strategyPickApi.getResult(rid)
      if (res.data?.data) results.push(res.data.data)
    }
    compareResults.value = results
  } catch {
    ElMessage.error('加载对比数据失败')
  } finally {
    compareLoading.value = false
  }
}

function comparePieOption(picks: StrategyPickItem[]) {
  const map: Record<string, number> = {}
  for (const p of picks) {
    const ind = p.industry || '未知'
    map[ind] = (map[ind] || 0) + 1
  }
  const sorted = Object.entries(map).sort((a, b) => b[1] - a[1])
  return {
    tooltip: { trigger: 'item', formatter: '{b}: {c}只' },
    series: [{
      type: 'pie', radius: ['30%', '60%'], center: ['50%', '50%'],
      label: { show: false },
      data: sorted.map(([name, count], i) => ({ name, value: count, itemStyle: { color: palette[i % palette.length] } })),
    }],
  }
}

onMounted(async () => {
  await Promise.all([loadStrategies(), loadAgents(), loadResult(), loadHistory()])
  // Restore config from localStorage first, fall back to pick_config from result
  const stored = loadConfig()
  if (stored) {
    const validStrategyIds = stored.selectedIds?.filter((id: string) => strategies.value.some(s => s._id === id)) || []
    if (validStrategyIds.length) selectedIds.value = validStrategyIds
    if (stored.selectedAgentIds?.length) selectedAgentIds.value = stored.selectedAgentIds
    if (stored.selectedPhilosophyIds?.length) selectedPhilosophyIds.value = stored.selectedPhilosophyIds
    if (stored.topN) topN.value = stored.topN
  } else if (result.value?.pick_config) {
    const cfg = result.value.pick_config
    const validStrategyIds = cfg.strategy_ids?.filter(id => strategies.value.some(s => s._id === id)) || []
    if (validStrategyIds.length) selectedIds.value = validStrategyIds
    if (cfg.agent_ids?.length) selectedAgentIds.value = cfg.agent_ids
    if (cfg.philosophy_ids?.length) selectedPhilosophyIds.value = cfg.philosophy_ids
    if (cfg.top_n) topN.value = cfg.top_n
  }
  try {
    const res = await strategyPickApi.getProgress()
    const data = res.data?.data
    if (data?.is_running) {
      progress.value = data
      running.value = true
      startProgressSSE()
    }
  } catch { /* ignore */ }
})

onBeforeUnmount(() => { stopProgressSSE(); stopProgressPolling() })
</script>

<style scoped>
.sp-page { display: flex; flex-direction: column; gap: 10px; }
.sp-toolbar { display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px; }
.sp-title-group { display: flex; align-items: baseline; gap: 10px; }
.sp-title { font-size: 15px; font-weight: 700; color: var(--text-alt-primary); }
.sp-subtitle { font-size: 12px; color: var(--text-alt-muted); }
.sp-controls { display: flex; gap: 8px; align-items: center; }
.sp-history-item { display: flex; flex-direction: row; align-items: center; gap: 8px; width: 100%; }
.sp-history-item > :first-child { flex: 1; min-width: 0; }
.sp-history-time { font-weight: 600; font-size: 13px; }
.sp-history-meta { font-size: 11px; color: var(--text-alt-muted); }
.sp-meta { display: flex; gap: 18px; font-size: 12px; color: var(--text-alt-muted); }
.sp-cron-bar { display: flex; align-items: center; font-size: 12px; color: var(--text-alt-muted); padding: 8px 0 4px; }

/* 折叠选择区 */
.sp-collapse-group {
  border: none;
  background: transparent;
}
.sp-collapse-group :deep(.el-collapse-item) {
  background: var(--bg-card-alt);
  border: 1px solid var(--border-alt);
  border-radius: 8px;
  margin-bottom: 10px;
  overflow: hidden;
}
.sp-collapse-group :deep(.el-collapse-item__header) {
  height: auto;
  min-height: 36px;
  padding: 10px 16px;
  background: transparent;
  border-bottom: none;
  color: var(--text-alt-body);
  font-size: 13px;
  font-weight: 600;
  line-height: 1.4;
}
.sp-collapse-group :deep(.el-collapse-item__wrap) {
  background: transparent;
  border-bottom: none;
}
.sp-collapse-group :deep(.el-collapse-item__content) {
  padding: 0 16px 12px;
}
.sp-collapse-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  width: 100%;
}
/* 买卖信号 */
.sp-signals-box {
  background: var(--bg-card-alt);
  border: 1px solid var(--border-alt);
  border-left: 3px solid #f0a040;
  border-radius: 6px;
  padding: 12px 14px;
}
.sp-signals-header { margin-bottom: 8px; }
.sp-signals-title { font-size: 13px; font-weight: 600; color: #d0b080; }
.sp-signals-summary { display: flex; gap: 8px; margin-bottom: 8px; flex-wrap: wrap; }
.sp-signal-summary-tag {
  font-size: 11px; padding: 2px 10px; border-radius: 4px; font-weight: 600;
}
.sp-ss-买入 { color: #4ade80; background: rgba(74,222,128,0.12); }
.sp-ss-加仓 { color: #60a0f0; background: rgba(96,160,240,0.12); }
.sp-ss-关注 { color: #a0d0a0; background: rgba(160,208,160,0.08); }
.sp-ss-持有 { color: #fbbf24; background: rgba(251,191,36,0.10); }
.sp-ss-观望 { color: var(--text-alt-muted); background: rgba(144,144,152,0.10); }
.sp-ss-减仓 { color: #fb923c; background: rgba(251,146,60,0.12); }
.sp-ss-卖出 { color: #f87171; background: rgba(248,113,113,0.12); }
.sp-signals-table-wrap { overflow-x: auto; }
.sp-signals-table {
  width: 100%; border-collapse: collapse; font-size: 14px;
}
.sp-signals-table th {
  text-align: left; color: var(--text-alt-muted); padding: 6px 8px; border-bottom: 1px solid var(--border-alt);
  font-weight: 500; white-space: nowrap;
}
.sp-signals-table td { padding: 6px 8px; border-bottom: 1px solid var(--border-alt); color: var(--text-alt-body); }
.sp-signal-row:hover td { background: var(--bg-hover-subtle); }
.sp-sig-badge {
  display: inline-block; font-size: 13px; padding: 2px 10px; border-radius: 3px; font-weight: 600;
}
.sp-sig-买入 { color: #4ade80; background: rgba(74,222,128,0.15); }
.sp-sig-加仓 { color: #60a0f0; background: rgba(96,160,240,0.15); }
.sp-sig-关注 { color: #a0d0a0; background: rgba(160,208,160,0.10); }
.sp-sig-持有 { color: #fbbf24; background: rgba(251,191,36,0.12); }
.sp-sig-观望 { color: var(--text-alt-muted); background: rgba(144,144,152,0.12); }
.sp-sig-减仓 { color: #fb923c; background: rgba(251,146,60,0.15); }
.sp-sig-卖出 { color: #f87171; background: rgba(248,113,113,0.15); }
.sp-priority { font-size: 13px; }
.sp-pri-高 { color: #f87171; }
.sp-pri-中 { color: #fbbf24; }
.sp-pri-低 { color: var(--text-alt-muted); }
.sp-signal-reason { font-size: 13px; color: var(--text-alt-muted); max-width: 260px; }

.sp-selector-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}
.sp-selector-title { font-size: 13px; font-weight: 600; color: var(--text-alt-body); }
.sp-strategy-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  min-height: 24px;
}
.sp-empty-hint { font-size: 12px; color: var(--text-alt-muted); }
.sp-strategy-chip {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  border-radius: 6px;
  border: 1px solid var(--border-alt);
  background: var(--bg-deep-soft);
  cursor: pointer;
  transition: all 0.2s;
  user-select: none;
}
.sp-strategy-chip:hover { border-color: var(--border-alt-hover); }
.sp-strategy-chip.checked {
  border-color: #5a7af0;
  background: rgba(90, 122, 240, 0.12);
}
.sp-check { width: 14px; height: 14px; accent-color: #5a7af0; }
.sp-chip-name { font-size: 12px; font-weight: 600; color: var(--text-alt-body); }
.sp-chip-desc { font-size: 11px; color: var(--text-alt-muted); max-width: 180px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

.sp-strategy-chip.agent-chip {
  border-color: var(--border-alt);
  background: var(--bg-deep);
}
.sp-strategy-chip.agent-chip:hover { border-color: var(--border-alt-hover); }
.sp-strategy-chip.agent-chip.checked {
  border-color: #7a5af0;
  background: rgba(122, 90, 240, 0.12);
}
.sp-progress-box {
  background: var(--bg-card-alt);
  border: 1px solid var(--border-alt);
  border-radius: 8px;
  padding: 12px 16px;
}
.sp-progress-header { font-size: 13px; color: var(--text-alt-body); margin-bottom: 8px; }
.sp-progress-status { font-size: 12px; color: var(--text-alt-muted); margin-top: 6px; }
.sp-progress-done { font-size: 13px; color: #4ade80; text-align: center; padding: 4px 0; }

/* 统计 */
.sp-stats { display: flex; flex-wrap: wrap; gap: 8px; }
.sp-stat-tag {
  font-size: 12px;
  color: var(--text-alt-body);
  background: var(--bg-card-alt);
  border: 1px solid var(--border-alt);
  border-radius: 4px;
  padding: 3px 10px;
}
.sp-stat-tag b { color: #5a7af0; }

/* 表格 */
.sp-table { background: transparent; }
.sp-table :deep(.el-table__row) { height: 42px; }
.sp-table :deep(.el-table__row:hover > td) { background: var(--bg-hover) !important; }
.sp-row-clickable { cursor: pointer; }
.sp-code { color: #5a7af0; cursor: pointer; }
.sp-code:hover { text-decoration: underline; }
.sp-na { color: var(--text-alt-muted); }
.sp-score-cell { font-weight: 600; font-size: 13px; }
.sp-strategy-tag {
  display: inline-block;
  font-size: 11px;
  color: var(--text-alt-body);
  background: rgba(90,122,240,0.08);
  padding: 1px 6px;
  border-radius: 3px;
  margin-right: 4px;
  margin-bottom: 2px;
  white-space: nowrap;
}
.sp-source-tag {
  display: inline-block;
  font-size: 11px;
  padding: 1px 6px;
  border-radius: 3px;
  font-weight: 600;
  line-height: 1.4;
}
.sp-tag-ai { color: #60a0f0; background: rgba(96,160,240,0.12); }
.sp-tag-factor { color: #a0a060; background: rgba(160,160,96,0.12); }
.sp-action-tag {
  display: inline-block;
  font-size: 11px;
  padding: 1px 7px;
  border-radius: 3px;
  font-weight: 600;
  line-height: 1.5;
  white-space: nowrap;
}
.sp-action-green { color: #3aa856; background: rgba(82,196,26,0.14); }
.sp-action-lightgreen { color: #7cc98a; background: rgba(82,196,26,0.07); }
.sp-action-orange { color: #e8912a; background: rgba(250,173,20,0.14); }
.sp-action-gray { color: var(--text-alt-muted); background: rgba(144,144,152,0.12); }

/* 弹窗详情 */
.sp-detail-dialog :deep(.el-dialog) {
  background: var(--bg-card-alt);
  border: 1px solid var(--border-alt);
  border-radius: 10px;
  color: var(--text-alt-body);
}
.sp-detail-dialog :deep(.el-dialog__title) {
  color: var(--text-alt-body);
  font-size: 15px;
  font-weight: 600;
}
.sp-detail-dialog :deep(.el-dialog__headerbtn .el-dialog__close) {
  color: var(--text-alt-muted);
}
.sp-detail-dialog :deep(.el-dialog__body) {
  padding: 16px 20px;
}
.sp-detail-source { font-size: 12px; font-weight: 400; color: var(--text-alt-muted); margin-bottom: 12px; }
.sp-detail-body { display: flex; flex-direction: column; gap: 10px; }
.sp-dim-block { background: var(--bg-deep-soft); border-radius: 6px; padding: 10px 12px; }
.sp-dim-title {
  display: flex; align-items: center; gap: 10px;
}
.sp-dim-label { font-size: 13px; font-weight: 600; color: var(--text-alt-body); min-width: 48px; }
.sp-dim-bar { flex: 1; max-width: 180px; }
.sp-dim-score { font-size: 13px; font-weight: 600; color: var(--text-alt-primary); }
.sp-dim-weight { font-size: 11px; color: var(--text-alt-muted); }
.sp-dim-contrib { font-size: 11px; color: var(--text-alt-muted); }
.sp-detail-advice { margin-top: 10px; border-top: 1px solid var(--border-alt); padding-top: 10px; }
.sp-agent-advice { margin-bottom: 14px; }
.sp-agent-advice-header { font-size: 13px; font-weight: 600; color: var(--accent); margin-bottom: 6px; padding-bottom: 4px; border-bottom: 1px dashed var(--border-alt); }
.sp-advice-label { font-size: 12px; color: var(--text-alt-muted); margin-bottom: 4px; }
.sp-advice-text { font-size: 13px; color: var(--text-alt-body); line-height: 1.6; }
.sp-risk-section { margin-top: 8px; }
.sp-risk-item {
  font-size: 12px;
  color: #faad14;
  background: rgba(250,173,20,0.08);
  padding: 4px 8px;
  border-radius: 4px;
  margin-top: 4px;
}

/* AI 综合建议 */
.sp-ai-summary {
  background: var(--bg-deep-soft);
  border: 1px solid var(--border-alt);
  border-left: 3px solid #5a7af0;
  border-radius: 6px;
  overflow: hidden;
}
.sp-summary-toggle {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 14px;
  cursor: pointer;
  font-size: 13px;
  font-weight: 600;
  color: var(--text-alt-body);
  user-select: none;
}
.sp-summary-toggle:hover { background: var(--bg-hover-subtle); }
.sp-summary-svg {
  color: var(--text-alt-muted);
  transition: transform 0.2s;
  vertical-align: middle;
}
.sp-summary-svg.is-expanded { transform: rotate(180deg); }
.sp-summary-body {
  padding: 0 14px 12px;
  font-size: 13px;
  color: var(--text-alt-body);
  line-height: 1.7;
}

/* 组合分析 */
.sp-portfolio-section {
  margin-top: 14px;
  background: var(--bg-deep-soft);
  border: 1px solid var(--border-alt);
  border-left: 3px solid var(--el-color-success);
  border-radius: 6px;
  overflow: hidden;
}
.sp-portfolio-body { padding: 0 14px 14px; }
.sp-metrics-row { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 12px; }
.sp-metric-card {
  flex: 1 0 100px;
  background: var(--bg-card);
  border: 1px solid var(--border-alt);
  border-radius: 6px;
  padding: 10px 12px;
  text-align: center;
  min-width: 80px;
}
.sp-metric-value { display: block; font-size: 18px; font-weight: 700; color: var(--accent); line-height: 1.3; }
.sp-metric-label { display: block; font-size: 11px; color: var(--text-alt-muted); margin-top: 2px; }
.sp-charts-row { display: flex; gap: 12px; }
.sp-chart-box {
  flex: 1;
  background: var(--bg-card);
  border: 1px solid var(--border-alt);
  border-radius: 6px;
  padding: 10px;
}
.sp-chart-title { font-size: 12px; font-weight: 600; color: var(--text-alt-body); margin-bottom: 6px; }

/* Markdown */
.md-content :deep(h1), .md-content :deep(h2), .md-content :deep(h3) {
  font-size: 13px; font-weight: 600; color: var(--text-alt-primary); margin: 10px 0 4px 0;
}
.md-content :deep(h1) { font-size: 14px; }
.md-content :deep(strong) { color: var(--text-alt-primary); font-weight: 600; }
.md-content :deep(p) { margin: 4px 0; color: var(--text-alt-body); }
.md-content :deep(ul), .md-content :deep(ol) { padding-left: 16px; margin: 3px 0; }
.md-content :deep(li) { margin: 2px 0; color: var(--text-alt-body); }
.md-content :deep(code) { background: var(--bg-deep-soft); padding: 1px 5px; border-radius: 3px; font-size: 12px; color: #d0a0f0; }

/* 投资哲学 Agent 样式 */
.sp-strategy-chip.philosophy-chip {
  border-color: var(--border-alt);
  background: var(--bg-deep);
}
.sp-strategy-chip.philosophy-chip:hover { border-color: var(--border-alt-hover); }
.sp-strategy-chip.philosophy-chip.checked {
  border-color: #aa5af0;
  background: rgba(170, 90, 240, 0.12);
}

/* 辩论列 */
.sp-debate-cell {
  display: inline-block;
  font-size: 11px;
  padding: 1px 7px;
  border-radius: 3px;
  font-weight: 600;
  line-height: 1.5;
  white-space: nowrap;
}
.sp-debate-bull { color: #4ade80; background: rgba(74,222,128,0.12); }
.sp-debate-bear { color: #f87171; background: rgba(248,113,113,0.12); }
.sp-debate-neutral { color: #fbbf24; background: rgba(251,191,36,0.12); }

/* 辩论总览 */
.sp-debate-overview {
  background: var(--bg-deep-soft);
  border: 1px solid var(--border-alt);
  border-left: 3px solid #aa5af0;
  border-radius: 6px;
  overflow: hidden;
}
.sp-debate-overview-toggle {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 14px;
  cursor: pointer;
  font-size: 13px;
  font-weight: 600;
  color: var(--text-alt-body);
  user-select: none;
}
.sp-debate-overview-toggle:hover { background: var(--bg-hover-subtle); }
.sp-debate-overview-body { padding: 0 14px 12px; display: flex; flex-direction: column; gap: 8px; }
.sp-debate-stock-row {
  background: var(--bg-card-alt);
  border: 1px solid var(--border-alt);
  border-radius: 6px;
  padding: 10px;
}
.sp-debate-stock-title {
  display: flex; align-items: center; gap: 10px; margin-bottom: 6px;
}
.sp-debate-stock-name { font-size: 13px; font-weight: 600; color: var(--text-alt-body); }
.sp-debate-stock-consensus {
  font-size: 11px; padding: 1px 7px; border-radius: 3px; font-weight: 600;
}
.sp-debate-stock-meta { font-size: 11px; color: var(--text-alt-muted); }
.sp-debate-vote-list { display: flex; flex-wrap: wrap; gap: 4px; }
.sp-vote-tag {
  font-size: 10px;
  padding: 2px 6px;
  border-radius: 3px;
  white-space: nowrap;
}
.sp-vote-strong_buy { color: #22c55e; background: rgba(34,197,94,0.1); }
.sp-vote-buy { color: #4ade80; background: rgba(74,222,128,0.08); }
.sp-vote-hold { color: #fbbf24; background: rgba(251,191,36,0.08); }
.sp-vote-watch { color: #fb923c; background: rgba(251,146,60,0.08); }
.sp-vote-sell { color: #f87171; background: rgba(248,113,113,0.1); }
.sp-vote-strong_sell { color: #ef4444; background: rgba(239,68,68,0.12); }

/* 辩论信号详情 */
.sp-debate-section { margin-top: 10px; border-top: 1px solid var(--border-alt); padding-top: 10px; }
.sp-debate-section-title { font-size: 12px; font-weight: 600; color: #aa5af0; margin-bottom: 8px; }
.sp-consensus-bar {
  display: flex; gap: 14px; font-size: 11px; color: var(--text-alt-muted);
  background: var(--bg-deep); border-radius: 4px; padding: 6px 10px; margin-bottom: 8px;
}
.sp-signal-row {
  background: var(--bg-deep);
  border: 1px solid var(--border-alt);
  border-radius: 6px;
  padding: 8px 10px;
  margin-bottom: 6px;
}
.sp-signal-header { display: flex; align-items: center; gap: 10px; margin-bottom: 4px; }
.sp-signal-name { font-size: 12px; font-weight: 600; color: var(--text-alt-body); }
.sp-signal-action {
  font-size: 10px; padding: 1px 6px; border-radius: 3px; font-weight: 600;
}
.sp-sig-strong_buy { color: #22c55e; background: rgba(34,197,94,0.12); }
.sp-sig-buy { color: #4ade80; background: rgba(74,222,128,0.1); }
.sp-sig-hold { color: #fbbf24; background: rgba(251,191,36,0.1); }
.sp-sig-watch { color: #fb923c; background: rgba(251,146,60,0.1); }
.sp-sig-sell { color: #f87171; background: rgba(248,113,113,0.1); }
.sp-sig-strong_sell { color: #ef4444; background: rgba(239,68,68,0.12); }
.sp-signal-score { font-size: 11px; color: var(--text-alt-muted); }
.sp-signal-conf { font-size: 11px; color: var(--text-alt-muted); }
.sp-signal-body { }
.sp-signal-reasoning { font-size: 11px; color: var(--text-alt-body); line-height: 1.5; margin-bottom: 4px; }
.sp-signal-factors { display: flex; flex-wrap: wrap; gap: 4px; margin-bottom: 4px; }
.sp-signal-factor {
  font-size: 10px; color: #60a0f0; background: rgba(96,160,240,0.08);
  padding: 1px 6px; border-radius: 3px;
}
.sp-signal-risks { display: flex; flex-wrap: wrap; gap: 4px; }
.sp-signal-warning {
  font-size: 10px; color: #faad14; background: rgba(250,173,20,0.08);
   padding: 1px 6px; border-radius: 3px;
}

/* 维度表格 */
.sp-dim-table { width: 100%; border: 1px solid var(--border-alt); border-radius: 6px; overflow: hidden; }
.sp-dim-tr { display: flex; align-items: center; padding: 6px 10px; gap: 6px; }
.sp-dim-th { background: var(--bg-deep-soft); font-size: 11px; font-weight: 600; color: var(--text-alt-muted); }
.sp-dim-tr:not(:last-child) { border-bottom: 1px solid var(--border-alt); }
.sp-dim-td { flex-shrink: 0; }
.sp-dim-td-label { flex: 1; min-width: 0; font-size: 13px; font-weight: 600; color: var(--text-alt-body); }
.sp-dim-td-score { width: 40px; text-align: right; font-size: 13px; }
.sp-dim-td-weight { width: 44px; text-align: right; font-size: 11px; color: var(--text-alt-muted); }
.sp-dim-td-contrib { width: 44px; text-align: right; font-size: 11px; color: var(--text-alt-muted); }
.sp-dim-td-bar { flex: 1; min-width: 80px; }
.sp-dim-td-bar .el-progress { margin: 0; }
.sp-score-badge { font-variant-numeric: tabular-nums; }
.sp-dim-detail-row { margin-top: 6px; }
.sp-dim-detail-toggle { font-size: 12px; color: var(--text-alt-muted); cursor: pointer; padding: 4px 10px; user-select: none; }
.sp-dim-detail-toggle:hover { color: var(--accent); }
.sp-dim-detail-body { padding: 6px 10px 10px 24px; display: flex; flex-wrap: wrap; gap: 4px 16px; }
.sp-dim-detail-item { font-size: 12px; display: flex; gap: 6px; }
.sp-dim-detail-key { color: var(--text-alt-muted); }
.sp-dim-detail-val { color: var(--text-alt-body); font-weight: 500; font-variant-numeric: tabular-nums; }

/* 持仓组合建议 */
.sp-portfolio-suggestion {
  margin-top: 14px;
  background: var(--bg-deep-soft);
  border: 1px solid var(--border-alt);
  border-left: 3px solid var(--el-color-primary);
  border-radius: 6px;
  overflow: hidden;
}
.sp-ps-header { padding: 10px 14px 0; display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }
.sp-ps-title { font-size: 14px; font-weight: 600; color: var(--text-alt-body); }
.sp-ps-meta { font-size: 12px; color: var(--text-alt-muted); }
.sp-ps-table-wrap { padding: 8px 14px 14px; overflow-x: auto; }
.sp-ps-table { width: 100%; border-collapse: collapse; font-size: 13px; }
.sp-ps-table th { text-align: left; color: var(--text-alt-muted); padding: 5px 8px; border-bottom: 1px solid var(--border-alt); font-weight: 500; white-space: nowrap; }
.sp-ps-table td { padding: 5px 8px; border-bottom: 1px solid var(--border-alt); color: var(--text-alt-body); }
.sp-ps-row:hover td { background: var(--bg-hover-subtle); }
.sp-ps-weight { font-weight: 600; color: var(--el-color-primary); }
.sp-ps-cum { font-size: 11px; color: var(--text-alt-muted); }

/* 再平衡建议 */
.sp-rebalance-panel {
  margin-top: 14px;
  background: var(--bg-deep-soft);
  border: 1px solid var(--border-alt);
  border-left: 3px solid #60a0f0;
  border-radius: 6px;
  overflow: hidden;
}

/* 对比 */
.sp-compare-check { margin-left: auto; }
.sp-compare-dialog .el-dialog__body { padding: 16px 20px; }
.sp-compare-body { display: flex; gap: 16px; }
.sp-compare-col { flex: 1; min-width: 0; }
.sp-compare-header { font-size: 13px; font-weight: 600; color: var(--text-alt-body); margin-bottom: 10px; padding-bottom: 6px; border-bottom: 1px solid var(--border-alt); }
</style>
