<template>
  <div class="fp-page">
    <!-- ── 顶部：市场状态 + 操作（合并为一张全宽卡，横排压扁，消除空旷） ── -->
    <el-card class="fp-head-card" shadow="never">
      <div class="fp-head">
        <div class="fp-head-main">
          <div class="fp-mkt">
        <span class="fp-mkt-label">当前市场</span>
        <el-tag :type="stateTagType(marketState?.state)" effect="dark" round size="small">
          {{ stateText(marketState?.state) }}
        </el-tag>
        <div class="fp-mkt-weights">
          <div v-for="dim in DIMS" :key="dim.key" class="fp-wchip">
            <span class="fp-wname">{{ dim.label }}</span>
            <span class="fp-wbar"><i :style="{ width: weightPct(activeWeights?.[dim.key]) + '%', background: dim.color }"></i></span>
            <span class="fp-wpct">{{ ((activeWeights?.[dim.key] || 0) * 100).toFixed(0) }}</span>
          </div>
        </div>
        <el-tooltip v-if="marketState?.weights_optimized" placement="top"
                    :content="`权重已被回测优化 · ${fmtTime(marketState.last_optimized_at)}`">
          <el-tag size="small" type="success" effect="plain" round>权重已优化</el-tag>
        </el-tooltip>
      </div>

      <div class="fp-head-divider"></div>

      <div class="fp-params">
          <div class="fp-field-inline">
            <label>精选数量</label>
            <el-input-number v-model="topN" :min="3" :max="30" :step="1" size="small" controls-position="right" class="fp-num" />
          </div>
          <div class="fp-field-inline">
            <label>候选池</label>
            <el-input-number v-model="candidatePool" :min="20" :max="120" :step="10" size="small" controls-position="right" class="fp-num" />
          </div>
        </div>

        <!-- 高级（默认折叠）：不动这里 = 全市场量化初筛 + 全部哲学辩论，对多数人够用 -->
        <el-collapse v-model="advancedOpen" class="fp-advanced">
          <el-collapse-item name="adv">
            <template #title>
              <span class="fp-adv-title">高级选项</span>
              <span class="fp-adv-hint">
                {{ advSummary }}
              </span>
            </template>

            <div class="fp-field fp-field-wide">
              <label>
                叠加策略
                <el-tooltip placement="top" content="把命中你认同风格策略的股票加「协同分」(每多1个来源+3，最多+9)。建议选 2-3 个，不是越多越好；不选=纯全市场量化。">
                  <el-icon class="fp-help"><QuestionFilled /></el-icon>
                </el-tooltip>
              </label>
              <div class="fp-combos">
                <span class="fp-combo-hint">推荐组合</span>
                <el-tag class="fp-combo" type="warning" effect="plain" round @click="applyCombo('market')">
                  🎯 跟随当前{{ stateText(marketState?.state) }}
                </el-tag>
                <el-tag class="fp-combo" effect="plain" round @click="applyCombo('value')">🛡️ 稳健价值</el-tag>
                <el-tag class="fp-combo" effect="plain" round @click="applyCombo('growth')">🚀 进攻成长</el-tag>
                <el-tag class="fp-combo" effect="plain" round @click="applyCombo('short')">⚡ 短线博弈</el-tag>
                <el-button v-if="selectedStrategyIds.length" link size="small" @click="selectedStrategyIds = []">清空</el-button>
              </div>
              <el-select v-model="selectedStrategyIds" multiple collapse-tags collapse-tags-tooltip
                         placeholder="不选 = 纯全市场量化初筛" size="small" filterable popper-class="fp-opt-popper">
                <el-option v-for="s in strategies" :key="s._id" :label="s.name" :value="s._id">
                  <span style="font-weight:500">{{ s.name }}</span>
                  <span style="margin-left:10px;font-size:12px;color:var(--el-text-color-secondary)">{{ s.description }}</span>
                </el-option>
              </el-select>
            </div>

            <div class="fp-field fp-field-wide">
              <label>
                投资哲学
                <el-tooltip placement="top" content="多种流派(价值/成长/趋势…)对同一只股各投票，越一致看多则加「辩论分」(±最多15)。不选=全部流派参与，分歧会互相抵消，结果更保守。">
                  <el-icon class="fp-help"><QuestionFilled /></el-icon>
                </el-tooltip>
              </label>
              <el-select v-model="selectedPhilosophyIds" multiple collapse-tags collapse-tags-tooltip
                         placeholder="不选 = 全部流派参与辩论" size="small" filterable popper-class="fp-opt-popper">
                <el-option v-for="a in philosophies" :key="a.id" :label="a.name" :value="a.id">
                  <span style="font-weight:500">{{ a.name }}</span>
                  <span style="margin-left:10px;font-size:12px;color:var(--el-text-color-secondary)">{{ a.description }}</span>
                </el-option>
              </el-select>
            </div>
          </el-collapse-item>
        </el-collapse>
        </div>

        <div class="fp-head-side">
          <div class="fp-side-title">融合选股引擎</div>
          <div class="fp-side-sub">市场感知 · 多策略叠加 · 多流派辩论</div>
          <el-button v-if="!running" type="primary" :icon="MagicStick" @click="runPick" :loading="loading" class="fp-cta">开始智选</el-button>
          <el-button v-else type="danger" plain @click="cancelPick" class="fp-cta-cancel">取消</el-button>
          <el-tag v-if="showDoneTip" type="success" effect="light" round size="small">智选完成 ✓</el-tag>
        </div>
      </div>

        <div v-if="running || progress.progress > 0" class="fp-progress">
          <el-progress
            :percentage="progress.progress"
            :status="progress.progress >= 100 ? 'success' : undefined"
            :stroke-width="14"
            striped striped-flow
          />
          <div class="fp-progress-status">{{ progress.status }}</div>
        </div>
    </el-card>

    <!-- ── 结果 Tabs ── -->
    <el-card class="fp-result-card" shadow="never">
      <el-tabs v-model="activeTab">
        <!-- 选股结果 -->
        <el-tab-pane name="picks">
          <template #label><span>选股结果<el-badge v-if="result?.picks?.length" :value="result.picks.length" class="fp-badge" /></span></template>

          <div v-if="result?.picks?.length" class="fp-meta-bar">
            <span>全市场 {{ result.universe_count }}</span>
            <el-divider direction="vertical" />
            <span>剔除 {{ result.filtered_count }}</span>
            <el-divider direction="vertical" />
            <span>候选 {{ result.candidate_count }}</span>
            <el-divider direction="vertical" />
            <span>策略 {{ result.strategy_count }}</span>
            <el-divider direction="vertical" />
            <el-tag size="small" :type="result.mode === 'quick' ? 'warning' : 'info'" effect="plain">
              {{ result.mode === 'quick' ? '快速版' : '完整版' }}
            </el-tag>
            <span class="fp-meta-time">{{ fmtTime(result.timestamp) }}</span>
          </div>

          <!-- 一键调仓：按建议仓位 + 模拟盘持仓/现金生成买卖清单，可一键下单 -->
          <div v-if="result?.picks?.length" class="fp-rebal">
            <div class="fp-rebal-head">
              <span class="fp-rebal-title">一键调仓到 AI 组合</span>
              <span class="fp-rebal-sub">按建议仓位对齐模拟盘：自动算整手、现金不足跳过、买不起一手剔除</span>
              <span class="fp-rebal-ratio">目标仓位</span>
              <el-select v-model="investRatio" size="small" style="width:90px" @change="loadRebalance">
                <el-option v-for="r in [0.5,0.6,0.7,0.8,0.9,1.0]" :key="r" :label="Math.round(r*100)+'%'" :value="r" />
              </el-select>
              <el-button size="small" :loading="rebalanceLoading" @click="loadRebalance">生成清单</el-button>
              <el-button size="small" type="primary" :disabled="!rebalance || !rebalance.orders.length"
                         :loading="executingAll" @click="execAll">全部执行</el-button>
            </div>
            <div v-if="rebalance?.dropped?.length" class="fp-rebal-dropped">
              ⚠️ {{ rebalance.dropped.length }} 只因本金不足一手已剔除：{{ rebalance.dropped.map(d => `${d.name}(${d.price}元)`).join('、') }}
            </div>
            <div v-if="rebalance?.message" class="fp-rebal-empty">{{ rebalance.message }}</div>
            <el-table v-else-if="rebalance" :data="rebalance.orders" size="small" border class="fp-rebal-table">
              <el-table-column label="动作" width="68">
                <template #default="{ row }">
                  <el-tag :type="row.action === 'buy' ? 'danger' : 'success'" size="small" effect="light">{{ row.action === 'buy' ? '买入' : '卖出' }}</el-tag>
                </template>
              </el-table-column>
              <el-table-column label="股票">
                <template #default="{ row }">{{ row.name }}（{{ row.code }}）</template>
              </el-table-column>
              <el-table-column label="股数" prop="shares" width="80" align="right" />
              <el-table-column label="现价" width="80" align="right">
                <template #default="{ row }">{{ row.price != null ? row.price.toFixed(2) : '-' }}</template>
              </el-table-column>
              <el-table-column label="目标/当前" width="116" align="right">
                <template #default="{ row }">{{ row.target_weight }}% / {{ row.current_weight }}%</template>
              </el-table-column>
              <el-table-column label="说明" prop="reason" show-overflow-tooltip />
              <el-table-column label="操作" width="88">
                <template #default="{ row }">
                  <el-button v-if="!row.skipped" size="small" plain :disabled="executingAll" :loading="executing[row.code]" @click="execOne(row)">执行</el-button>
                  <el-tooltip v-else :content="row.skip_reason || ''" placement="top">
                    <el-tag type="info" size="small">已跳过</el-tag>
                  </el-tooltip>
                </template>
              </el-table-column>
            </el-table>
          </div>

          <el-table v-if="result?.picks?.length" :data="result.picks" row-key="code" stripe
                    :default-sort="{ prop: 'fusion_score', order: 'descending' }">
            <el-table-column type="expand">
              <template #default="{ row }">
                <div class="fp-expand">
                  <div class="fp-expand-block">
                    <h4>四维因子</h4>
                    <div v-for="dim in DIMS" :key="dim.key" class="fp-dim-row">
                      <span class="fp-dim-name">{{ dim.label }}</span>
                      <el-progress :percentage="Math.round(row.scores?.[dim.key] || 0)" :stroke-width="10"
                                   :color="dim.color" :show-text="false" />
                      <span class="fp-dim-val">{{ (row.scores?.[dim.key] || 0).toFixed(0) }}</span>
                    </div>
                  </div>
                  <div class="fp-expand-block">
                    <h4>来源 / 辩论</h4>
                    <div class="fp-src-tags">
                      <el-tag v-for="s in row.sources" :key="s" size="small" effect="plain">{{ s }}</el-tag>
                    </div>
                    <div v-if="row.debate_consensus" class="fp-consensus">
                      共识度 {{ (row.debate_consensus.consensus_level * 100).toFixed(0) }}% ·
                      倾向 {{ row.debate_consensus.tendency > 0 ? '看多' : row.debate_consensus.tendency < 0 ? '看空' : '中性' }} ·
                      {{ row.debate_consensus.agent_count }}位Agent
                      (多{{ row.debate_consensus.positive_count }}/空{{ row.debate_consensus.negative_count }})
                    </div>
                    <div v-else class="fp-consensus fp-muted">未参与辩论（快速版）</div>
                  </div>
                  <div class="fp-expand-block fp-expand-wide" v-if="row.llm?.summary">
                    <h4>AI 研判</h4>
                    <div class="md-content" v-html="renderMd(row.llm.summary)"></div>
                    <div v-if="row.llm.recommendation" class="md-content fp-rec" v-html="renderMd(row.llm.recommendation)"></div>
                  </div>
                </div>
              </template>
            </el-table-column>

            <el-table-column label="#" width="50" align="center">
              <template #default="{ $index }">{{ $index + 1 }}</template>
            </el-table-column>
            <el-table-column prop="code" label="代码" width="100" />
            <el-table-column prop="name" label="名称" width="110" />
            <el-table-column prop="industry" label="行业" width="120" show-overflow-tooltip />
            <el-table-column prop="fusion_score" label="融合分" width="110" sortable align="center">
              <template #header>
                <span class="fp-th">融合分
                  <el-tooltip placement="top" content="在因子分基础上，把辩论/协同信号按「离满分的剩余空间」折算融入(非简单相加)——因子分越高加幅越小，故不会扎堆满分，头部仍可区分。">
                    <el-icon class="fp-help"><QuestionFilled /></el-icon>
                  </el-tooltip>
                </span>
              </template>
              <template #default="{ row }">
                <span class="fp-score" :class="'fp-score--' + scoreLevel(row.fusion_score)">{{ row.fusion_score.toFixed(1) }}</span>
              </template>
            </el-table-column>
            <el-table-column prop="factor_score" label="因子分" width="90" sortable align="center">
              <template #default="{ row }">{{ row.factor_score.toFixed(1) }}</template>
            </el-table-column>
            <el-table-column width="96" align="center">
              <template #header>
                <span class="fp-th">辩论±
                  <el-tooltip placement="top" content="多投资流派(价值/成长/趋势…)对该股投票的一致看多程度，范围 ±15 分。与「来源」无关，不叠加策略也会有值。">
                    <el-icon class="fp-help"><QuestionFilled /></el-icon>
                  </el-tooltip>
                </span>
              </template>
              <template #default="{ row }">
                <span :class="bonusClass(row.debate_bonus)">{{ fmtBonus(row.debate_bonus) }}</span>
              </template>
            </el-table-column>
            <el-table-column width="96" align="center">
              <template #header>
                <span class="fp-th">协同±
                  <el-tooltip placement="top" content="被多少条选股途径「共同选中」的加分：每多 1 个来源 +3，最多 +9。只被量化选中=0；在「高级」里叠加策略后才会 >0。">
                    <el-icon class="fp-help"><QuestionFilled /></el-icon>
                  </el-tooltip>
                </span>
              </template>
              <template #default="{ row }">
                <span :class="bonusClass(row.source_bonus)">{{ fmtBonus(row.source_bonus) }}</span>
              </template>
            </el-table-column>
            <el-table-column width="90" align="center">
              <template #header>
                <span class="fp-th">来源
                  <el-tooltip placement="top" content="选中该股的途径数。quant=全市场量化初筛(基础，人人有)；叠加策略后会增加策略来源。鼠标悬停看具体是哪些。">
                    <el-icon class="fp-help"><QuestionFilled /></el-icon>
                  </el-tooltip>
                </span>
              </template>
              <template #default="{ row }">
                <el-tooltip :content="(row.sources || []).join('、')" placement="top">
                  <el-tag size="small" :type="row.source_count > 1 ? 'success' : 'info'" effect="plain">
                    {{ row.source_count }} 源
                  </el-tag>
                </el-tooltip>
              </template>
            </el-table-column>
            <el-table-column label="建议仓位" width="120" align="center" sortable :sort-by="'weight'">
              <template #default="{ row }">
                <span class="fp-weight-cell">{{ (row.weight || 0).toFixed(1) }}%</span>
              </template>
            </el-table-column>
          </el-table>

          <el-empty v-else description="暂无选股结果，点击「开始智选」" />
        </el-tab-pane>

        <!-- AI 总结 -->
        <el-tab-pane name="summary" label="AI 总结">
          <div v-if="result?.ai_summary" class="md-content fp-summary" v-html="renderMd(result.ai_summary)"></div>
          <el-empty v-else description="暂无 AI 总结（快速版不生成）" />
        </el-tab-pane>

        <!-- 回测 -->
        <el-tab-pane name="backtest" label="历史回测">
          <div class="fp-panel-actions">
            <el-button size="small" :icon="DataAnalysis" @click="loadBacktest" :loading="btLoading">
              计算回测（最近 {{ btLimit }} 次选股）
            </el-button>
            <el-input-number v-model="btLimit" :min="5" :max="200" :step="5" size="small" controls-position="right" />
            <el-button v-if="isAdmin" size="small" type="danger" plain :icon="Delete"
                       class="fp-reset" @click="resetData" :loading="resetLoading">
              重置回测数据
            </el-button>
          </div>
          <template v-if="backtest">
            <div class="fp-bt-stats">
              <el-statistic title="参与批次" :value="backtest.runs_count" />
              <el-statistic title="融合分相关性" :value="backtest.fusion_score_correlation" :precision="3" />
              <el-statistic title="因子分相关性" :value="backtest.factor_score_correlation" :precision="3" />
              <el-statistic title="辩论加分胜率差" :value="backtest.debate_bonus_effectiveness" suffix="%" :precision="1" />
            </div>

            <h4 class="fp-h4">各持有期表现</h4>
            <el-table :data="overallRows" size="small" border>
              <el-table-column prop="h" label="持有期" width="90"><template #default="{ row }">{{ row.h }} 日</template></el-table-column>
              <el-table-column prop="n" label="样本" width="80" />
              <el-table-column label="平均收益"><template #default="{ row }">{{ fmtPct(row.avg) }}</template></el-table-column>
              <el-table-column label="胜率"><template #default="{ row }">{{ fmtPct(row.win_rate) }}</template></el-table-column>
              <el-table-column label="基准"><template #default="{ row }">{{ fmtPct(row.baseline) }}</template></el-table-column>
              <el-table-column label="超额"><template #default="{ row }"><span :class="bonusClass(row.excess)">{{ fmtPct(row.excess) }}</span></template></el-table-column>
              <el-table-column label="跑赢率"><template #default="{ row }">{{ fmtPct(row.beat_rate) }}</template></el-table-column>
            </el-table>

            <div class="fp-bt-cols">
              <div>
                <h4 class="fp-h4">按市场状态（5日胜率）</h4>
                <el-table :data="marketStateRows" size="small" border>
                  <el-table-column label="状态"><template #default="{ row }">{{ stateText(row.state) }}</template></el-table-column>
                  <el-table-column prop="n" label="样本" width="70" />
                  <el-table-column label="胜率"><template #default="{ row }">{{ fmtPct(row.win_rate) }}</template></el-table-column>
                  <el-table-column label="均收益"><template #default="{ row }">{{ fmtPct(row.avg_return) }}</template></el-table-column>
                </el-table>
              </div>
              <div>
                <h4 class="fp-h4">按来源（5日胜率）</h4>
                <el-table :data="sourceRows" size="small" border>
                  <el-table-column prop="label" label="来源" />
                  <el-table-column prop="n" label="样本" width="70" />
                  <el-table-column label="胜率"><template #default="{ row }">{{ fmtPct(row.win_rate) }}</template></el-table-column>
                </el-table>
              </div>
            </div>
          </template>
          <el-empty v-else description="点击上方按钮计算回测" />
        </el-tab-pane>

        <!-- 权重优化 -->
        <el-tab-pane name="optimize" label="权重优化">
          <div class="fp-panel-actions">
            <el-button size="small" :icon="DataAnalysis" @click="loadSignals" :loading="sigLoading">加载优化信号</el-button>
            <el-button v-if="isAdmin" size="small" type="primary" :icon="MagicStick"
                       @click="doOptimize" :loading="optLoading" :disabled="!signals?.reliable">
              应用优化（管理员）
            </el-button>
            <el-tag v-if="signals" :type="signals.reliable ? 'success' : 'warning'" effect="plain" size="small">
              {{ signals.reliable ? '样本充足，可优化' : '样本不足，仅供参考' }}
            </el-tag>
          </div>
          <template v-if="signals">
            <div v-for="st in STATES" :key="st" class="fp-opt-state">
              <h4 class="fp-h4">
                {{ stateText(st) }}
                <span class="fp-muted">（样本 {{ signals.sample_counts?.[st] ?? 0 }}，胜率 {{ fmtPct(signals.state_performance?.[st]?.win_rate) }}）</span>
              </h4>
              <el-table :data="optRows(st)" size="small" border>
                <el-table-column prop="label" label="维度" width="110" />
                <el-table-column label="与5日收益相关性">
                  <template #default="{ row }"><span :class="bonusClass(row.corr)">{{ row.corr.toFixed(3) }}</span></template>
                </el-table-column>
                <el-table-column label="建议权重">
                  <template #default="{ row }">{{ (row.suggested * 100).toFixed(0) }}%</template>
                </el-table-column>
              </el-table>
            </div>
          </template>
          <el-empty v-else description="点击「加载优化信号」查看各维度与收益的相关性及建议权重" />
        </el-tab-pane>

        <!-- 历史 -->
        <el-tab-pane name="history" label="历史">
          <div class="fp-panel-actions">
            <el-button size="small" @click="loadHistory" :loading="histLoading">刷新历史</el-button>
          </div>
          <el-table v-if="history.length" :data="history" size="small" @row-click="(r:any) => loadResult(r.run_id)" class="fp-history-table">
            <el-table-column label="时间"><template #default="{ row }">{{ fmtTime(row.timestamp) }}</template></el-table-column>
            <el-table-column label="市场"><template #default="{ row }"><el-tag size="small" :type="stateTagType(row.market_state)">{{ stateText(row.market_state) }}</el-tag></template></el-table-column>
            <el-table-column label="模式"><template #default="{ row }">{{ row.mode === 'quick' ? '快速' : '完整' }}</template></el-table-column>
            <el-table-column prop="universe_count" label="全市场" />
            <el-table-column prop="candidate_count" label="候选" />
            <el-table-column prop="selected_count" label="精选" />
          </el-table>
          <el-empty v-else description="暂无历史记录" />
        </el-tab-pane>
      </el-tabs>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { MagicStick, DataAnalysis, QuestionFilled, Delete } from '@element-plus/icons-vue'
import { renderMd } from '@/utils/markdown'
import { useAuthStore } from '@/stores/authStore'
import { fusionPickApi } from '@/api/fusionPick'
import type {
  FusionPickProgress, FusionPickResult, FusionMarketState,
  FusionBacktestResult, FusionOptSignals, FusionHistoryItem, MarketStateKey, DimWeights,
} from '@/api/fusionPick'
import { strategyPickApi } from '@/api/strategyPick'
import type { RebalanceAdvice, RebalanceOrder } from '@/api/strategyPick'
import { paperApi } from '@/api/paper'

const DIMS = [
  { key: 'fundamental', label: '基本面', color: '#5a7af0' },
  { key: 'technical', label: '技术面', color: '#e6a23c' },
  { key: 'fund_flow', label: '资金面', color: '#67c23a' },
  { key: 'valuation', label: '估值面', color: '#909399' },
] as const
const STATES: MarketStateKey[] = ['bull', 'bear', 'volatile']

const auth = useAuthStore()
const isAdmin = computed(() => auth.isAdmin)

// ── 控制状态 ──
const topN = ref(10)
const candidatePool = ref(50)
const selectedStrategyIds = ref<string[]>([])
const selectedPhilosophyIds = ref<string[]>([])
const strategies = ref<any[]>([])
const philosophies = ref<any[]>([])
const advancedOpen = ref<string[]>([])  // 高级选项默认折叠

// 推荐策略组合（按 preset 策略名搭配）。点击一键填入，免去从一堆策略里挑。
const COMBOS: Record<string, { label: string; names: string[] }> = {
  value:  { label: '稳健价值', names: ['QARP 质量价值', '红利低波防御', '五因子增强'] },
  growth: { label: '进攻成长', names: ['GARP 成长价值', '因子动量轮动', '行业轮动先锋'] },
  short:  { label: '短线博弈', names: ['交易型阿尔法', '行业轮动先锋'] },
}
function comboByMarket(): string {
  const s = marketState.value?.state
  if (s === 'bull') return 'growth'   // 牛市进攻
  if (s === 'bear') return 'value'    // 熊市防御
  return 'value'                       // 震荡偏稳健
}
function applyCombo(key: string) {
  const realKey = key === 'market' ? comboByMarket() : key
  const combo = COMBOS[realKey]
  if (!combo) return
  if (!strategies.value.length) { ElMessage.warning('策略列表尚未加载'); return }
  const ids = strategies.value.filter(s => combo.names.includes(s.name)).map(s => s._id)
  if (!ids.length) { ElMessage.warning('未匹配到对应策略'); return }
  selectedStrategyIds.value = ids
  if (!advancedOpen.value.includes('adv')) advancedOpen.value = ['adv']
  const byMarket = key === 'market' ? `（按当前${stateText(marketState.value?.state)}）` : ''
  ElMessage.success(`已应用「${combo.label}」组合${byMarket}：${combo.names.join('、')}`)
}

const advSummary = computed(() => {
  const s = selectedStrategyIds.value.length
  const p = selectedPhilosophyIds.value.length
  if (!s && !p) return '默认：全市场量化 + 全部流派辩论'
  const parts: string[] = []
  if (s) parts.push(`叠加 ${s} 策略`)
  parts.push(p ? `${p} 个指定流派` : '全部流派辩论')
  return parts.join(' · ')
})

const running = ref(false)
const loading = ref(false)
const showDoneTip = ref(false)
const progress = ref<FusionPickProgress>({ is_running: false, progress: 0, status: '' })

const activeTab = ref('picks')
const result = ref<FusionPickResult | null>(null)
const marketState = ref<FusionMarketState | null>(null)

// ── 回测 / 优化 / 历史 ──
const btLimit = ref(30)
const btLoading = ref(false)
const backtest = ref<FusionBacktestResult | null>(null)
const sigLoading = ref(false)
const optLoading = ref(false)
const resetLoading = ref(false)
const signals = ref<FusionOptSignals | null>(null)
const histLoading = ref(false)
const history = ref<FusionHistoryItem[]>([])

// 当前生效权重：优先用本次结果，否则市场状态自动权重
const activeWeights = computed<DimWeights | undefined>(
  () => result.value?.weights_used || marketState.value?.weights_optimized || marketState.value?.weights_auto,
)

// ── 计算属性：回测表格 ──
const overallRows = computed(() => {
  const o = backtest.value?.overall || {}
  return Object.keys(o).sort((a, b) => +a - +b).map(h => ({ h, ...o[h] }))
})
const marketStateRows = computed(() =>
  STATES.map(state => ({ state, ...(backtest.value?.by_market_state?.[state] || { n: 0, win_rate: null, avg_return: null }) })))
const sourceRows = computed(() => {
  const s = backtest.value?.by_source
  if (!s) return []
  return [
    { label: '仅量化选中', ...s.quant_only },
    { label: '多来源共识', ...s.multi_source },
  ]
})
function optRows(st: MarketStateKey) {
  const corr = signals.value?.dimension_correlations?.[st] || {} as DimWeights
  const sug = signals.value?.suggested_weights?.[st] || {} as DimWeights
  return DIMS.map(d => ({ label: d.label, corr: corr[d.key] ?? 0, suggested: sug[d.key] ?? 0 }))
}

// ── 展示工具 ──
function stateText(s?: string) { return s === 'bull' ? '牛市' : s === 'bear' ? '熊市' : '震荡市' }
function stateTagType(s?: string) { return s === 'bull' ? 'danger' : s === 'bear' ? 'success' : 'info' }
function weightPct(v?: number) { return Math.round((v || 0) * 100) }
function scoreType(v: number) { return v >= 72 ? 'danger' : v >= 58 ? 'warning' : v >= 45 ? '' : 'info' }
function scoreLevel(v: number) { return v >= 90 ? 'hot' : v >= 80 ? 'high' : v >= 70 ? 'mid' : 'low' }
function bonusClass(v: number | null) { return v == null ? 'fp-muted' : v > 0 ? 'fp-up' : v < 0 ? 'fp-down' : 'fp-muted' }
function fmtBonus(v: number) { return v > 0 ? `+${v.toFixed(1)}` : v.toFixed(1) }
function fmtPct(v: number | null | undefined) { return v == null ? '—' : `${v > 0 ? '+' : ''}${Number(v).toFixed(1)}%` }
function fmtTime(t?: string | null) {
  if (!t) return ''
  try { return new Date(t).toLocaleString('zh-CN', { hour12: false }) } catch { return t }
}

// ── 数据加载 ──
async function loadMarketState() {
  try { const res = await fusionPickApi.getMarketState(); if (res.data?.success) marketState.value = res.data.data } catch { /* ignore */ }
}
async function loadStrategies() {
  try {
    const res = await strategyPickApi.getStrategies()
    if (res.data?.success) strategies.value = res.data.data || []
  } catch { /* ignore */ }
}
async function loadPhilosophies() {
  try {
    const res = await strategyPickApi.getAgents()
    if (res.data?.success) philosophies.value = (res.data.data || []).filter((a: any) => a.type === 'philosophy')
  } catch { /* ignore */ }
}
async function loadResult(runId?: string) {
  try {
    const res = await fusionPickApi.getResult(runId)
    if (res.data?.success && res.data.data?.picks) { result.value = res.data.data; activeTab.value = 'picks' }
  } catch { /* ignore */ }
}
async function loadHistory() {
  histLoading.value = true
  try { const res = await fusionPickApi.getHistory(); if (res.data?.success) history.value = res.data.data || [] }
  catch { /* ignore */ } finally { histLoading.value = false }
}
async function loadBacktest() {
  btLoading.value = true
  try { const res = await fusionPickApi.getBacktest(btLimit.value); if (res.data?.success) backtest.value = res.data.data }
  catch { ElMessage.error('回测失败') } finally { btLoading.value = false }
}
async function loadSignals() {
  sigLoading.value = true
  try { const res = await fusionPickApi.getOptimizationSignals(); if (res.data?.success) signals.value = res.data.data }
  catch { ElMessage.error('加载优化信号失败') } finally { sigLoading.value = false }
}
async function doOptimize() {
  optLoading.value = true
  try {
    const res = await fusionPickApi.optimizeWeights()
    if (res.data?.success) {
      const d = res.data.data
      if (d?.skipped) ElMessage.warning(d.reason || '样本不足，已跳过')
      else { ElMessage.success(`已更新 ${(d?.states_updated || []).map(stateText).join('、') || '0'} 权重`); await loadMarketState() }
    }
  } catch { ElMessage.error('权重优化失败') } finally { optLoading.value = false }
}

async function resetData() {
  try {
    await ElMessageBox.confirm(
      '将清空：回测快照 + 历史选股结果 + 已优化权重(回归市场默认)。用于清掉旧口径产生的脏数据，让回测从新口径重新积累。此操作不可恢复。',
      '重置回测数据', { type: 'warning', confirmButtonText: '确认重置', cancelButtonText: '取消' },
    )
  } catch { return }  // 取消
  resetLoading.value = true
  try {
    const res = await fusionPickApi.resetData('all')
    if (res.data?.success) {
      const d = res.data.data?.deleted || {}
      ElMessage.success(`已重置：快照 ${d.snapshots || 0} · 历史 ${d.results || 0} · 权重 ${d.weight_config || 0}`)
      backtest.value = null
      signals.value = null
      result.value = null
      await Promise.all([loadHistory(), loadMarketState()])
    }
  } catch { /* client 拦截器已提示 */ } finally { resetLoading.value = false }
}

// ── 一键调仓：建议清单 + 执行到模拟盘（复用量化选股 advisor + paper /trade）──
const rebalance = ref<RebalanceAdvice | null>(null)
const rebalanceLoading = ref(false)
const investRatio = ref(1.0)
const executing = ref<Record<string, boolean>>({})
const executingAll = ref(false)

async function loadRebalance() {
  rebalanceLoading.value = true
  try {
    const res = await fusionPickApi.rebalanceAdvice(0.05, investRatio.value)
    rebalance.value = res.data.data
  } catch { ElMessage.error('生成调仓清单失败') }
  finally { rebalanceLoading.value = false }
}

async function execOne(o: RebalanceOrder): Promise<boolean> {
  if (o.skipped || !o.price) return false
  executing.value[o.code] = true
  try {
    await paperApi.executeTrade({
      code: o.code, action: o.action, shares: o.shares,
      price: o.price, ai_signal: { reason: o.reason, position_advice: 'AI 智选调仓' },
    })
    await loadRebalance()  // 执行后刷新（现金/持仓已变）
    return true
  } catch (e: any) {
    ElMessage.error(`执行失败：${e?.response?.data?.error || e?.message || e}`)
    return false
  } finally { executing.value[o.code] = false }
}

async function execAll() {
  if (!rebalance.value) return
  executingAll.value = true
  try {
    // 先卖后买：卖出释放现金才够买
    const ordered = [...rebalance.value.orders].sort(
      (a, b) => (a.action === 'sell' ? 0 : 1) - (b.action === 'sell' ? 0 : 1))
    for (const o of ordered) {
      if (o.skipped || !o.price) continue
      const ok = await execOne(o)
      if (!ok) break  // 卖出失败即中断，避免后续买入在现金未释放时执行
    }
  } finally { executingAll.value = false }
}

// ── 运行 + 进度（SSE，失败回退轮询） ──
let eventSource: EventSource | null = null
let progressTimer: ReturnType<typeof setInterval> | null = null
let sseTimeout: ReturnType<typeof setTimeout> | null = null

async function runPick() {
  running.value = true
  loading.value = true
  showDoneTip.value = false
  progress.value = { is_running: true, progress: 0, status: '启动中...' }
  try {
    const res = await fusionPickApi.run({
      top_n: topN.value, candidate_pool: candidatePool.value,
      strategy_ids: selectedStrategyIds.value, philosophy_ids: selectedPhilosophyIds.value,
    })
    if (res.data?.success) { ElMessage.info(res.data.message || 'AI 智选已启动'); startProgressSSE() }
    else { ElMessage.error(res.data?.error || '启动失败'); resetRunning() }
  } catch { resetRunning() } finally { loading.value = false }
}

async function cancelPick() {
  try {
    const res = await fusionPickApi.cancel()
    if (res.data?.success) { stopProgressSSE(); stopProgressPolling(); progress.value = { is_running: false, progress: 0, status: '已取消' }; running.value = false }
  } catch { ElMessage.error('取消失败') }
}

function resetRunning() { running.value = false; progress.value = { is_running: false, progress: 0, status: '' } }

function onProgressData(data: FusionPickProgress, stop: () => void) {
  progress.value = data
  if (data.is_running) running.value = true
  if (!data.is_running) {
    stop()
    running.value = false
    if (data.progress >= 100) {
      showDoneTip.value = true
      Promise.all([loadResult(), loadHistory(), loadMarketState()])
      setTimeout(() => { showDoneTip.value = false }, 4000)
    }
  }
}

function startProgressPolling() {
  stopProgressPolling()
  progressTimer = setInterval(async () => {
    try { const res = await fusionPickApi.getProgress(); if (res.data?.data) onProgressData(res.data.data, stopProgressPolling) }
    catch { /* ignore */ }
  }, 2000)
}
function stopProgressPolling() { if (progressTimer) { clearInterval(progressTimer); progressTimer = null } }

function startProgressSSE() {
  stopProgressSSE(); stopProgressPolling()
  eventSource = new EventSource('/api/v1/fusion-pick/progress/stream')
  let received = false
  eventSource.onmessage = (event) => {
    received = true
    if (sseTimeout) { clearTimeout(sseTimeout); sseTimeout = null }
    try { const res = JSON.parse(event.data); if (res?.data) onProgressData(res.data, stopProgressSSE) } catch { /* ignore */ }
  }
  eventSource.onerror = () => {
    if (received) { stopProgressSSE(); running.value = false; progress.value = { is_running: false, progress: 0, status: '连接断开' } }
  }
  sseTimeout = setTimeout(() => { if (!received) { stopProgressSSE(); startProgressPolling() } }, 3000)
}
function stopProgressSSE() {
  if (eventSource) { eventSource.close(); eventSource = null }
  if (sseTimeout) { clearTimeout(sseTimeout); sseTimeout = null }
}

onMounted(async () => {
  await Promise.all([loadMarketState(), loadStrategies(), loadPhilosophies(), loadResult(), loadHistory()])
  // 如果后台正有任务在跑，接上进度
  try {
    const res = await fusionPickApi.getProgress()
    if (res.data?.data?.is_running) { running.value = true; startProgressSSE() }
  } catch { /* ignore */ }
})
onUnmounted(() => { stopProgressSSE(); stopProgressPolling() })
</script>

<style scoped>
.fp-page { display: flex; flex-direction: column; gap: 16px; }

.fp-head-card :deep(.el-card__body) { padding: 16px 18px; }
/* 市场状态：横排压扁 */
.fp-mkt { display: flex; align-items: center; flex-wrap: wrap; gap: 10px 14px; }
.fp-mkt-label { font-size: 13px; color: var(--text-secondary); }
.fp-mkt-weights { display: flex; align-items: center; flex-wrap: wrap; gap: 18px; margin-left: 4px; }
.fp-wchip { display: flex; align-items: center; gap: 6px; }
.fp-wname { font-size: 12px; color: var(--text-secondary); }
.fp-wbar { display: inline-block; width: 54px; height: 6px; border-radius: 3px; background: var(--el-fill-color, #eef0f3); overflow: hidden; }
.fp-wbar > i { display: block; height: 100%; border-radius: 3px; }
.fp-wpct { font-size: 12px; font-weight: 600; color: var(--text-primary); min-width: 20px; }
.fp-head-divider { height: 1px; background: var(--el-border-color-lighter); margin: 14px 0; }

.fp-head { display: flex; align-items: stretch; gap: 20px; }
.fp-head-main { flex: 1 1 auto; min-width: 0; }
.fp-head-side {
  flex: 0 0 240px; display: flex; flex-direction: column; justify-content: center; gap: 6px;
  padding: 18px; border-radius: 12px;
  background: linear-gradient(160deg, var(--el-fill-color-light), var(--el-fill-color));
}
.fp-side-title { font-size: 15px; font-weight: 600; color: var(--text-primary); }
.fp-side-sub { font-size: 12px; color: var(--text-secondary); line-height: 1.5; margin-bottom: 8px; }
.fp-params { display: flex; align-items: flex-end; flex-wrap: wrap; gap: 16px; }
.fp-field-inline { display: flex; flex-direction: column; gap: 6px; }
.fp-field-inline label { font-size: 12px; color: var(--text-secondary); }
.fp-num { width: 118px; }
.fp-cta, .fp-cta-cancel { width: 100%; }
@media (max-width: 860px) { .fp-head { flex-direction: column; } .fp-head-side { flex-basis: auto; } }
.fp-field { display: flex; flex-direction: column; gap: 6px; }
.fp-field-wide { grid-column: span 2; }
.fp-field label { font-size: 12px; color: var(--text-secondary); }
.fp-advanced { margin-top: 14px; border: none; border-top: 1px solid var(--el-border-color-lighter); }
.fp-advanced :deep(.el-collapse-item__header) { border: none; height: 44px; }
.fp-advanced :deep(.el-collapse-item__arrow) { margin-left: 6px; margin-right: auto; }
.fp-advanced :deep(.el-collapse-item__wrap) { border: none; }
.fp-advanced :deep(.el-collapse-item__content) { padding: 8px 2px 0; display: flex; flex-direction: column; gap: 12px; }
.fp-adv-title { font-size: 13px; color: var(--text-primary); font-weight: 500; margin-right: 10px; }
.fp-adv-hint { font-size: 12px; color: var(--text-secondary); }
.fp-help { font-size: 13px; color: var(--text-secondary); vertical-align: -2px; margin-left: 2px; cursor: help; }
.fp-th { display: inline-flex; align-items: center; gap: 2px; }
.fp-combos { display: flex; align-items: center; flex-wrap: wrap; gap: 6px; margin: 2px 0 2px; }
.fp-combo-hint { font-size: 12px; color: var(--text-secondary); margin-right: 2px; }
.fp-combo { cursor: pointer; transition: transform .1s; }
.fp-combo:hover { transform: translateY(-1px); }
.fp-progress { margin-top: 14px; }
.fp-progress-status { margin-top: 6px; font-size: 12px; color: var(--text-secondary); }

.fp-result-card :deep(.el-card__body) { padding: 8px 16px 16px; }
.fp-badge { margin-left: 4px; }
.fp-meta-bar { display: flex; align-items: center; gap: 6px; font-size: 12px; color: var(--text-secondary); margin: 8px 0 14px; flex-wrap: wrap; }
.fp-meta-time { margin-left: auto; }

.fp-expand { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; padding: 12px 24px; }
.fp-expand-wide { grid-column: span 2; }
.fp-expand-block h4 { margin: 0 0 8px; font-size: 13px; color: var(--text-primary); }
.fp-dim-row { display: grid; grid-template-columns: 48px 1fr 30px; align-items: center; gap: 8px; margin-bottom: 6px; }
.fp-dim-name, .fp-dim-val { font-size: 12px; color: var(--text-secondary); }
.fp-dim-val { text-align: right; }
.fp-src-tags { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 8px; }
.fp-consensus { font-size: 12px; color: var(--text-secondary); }
.fp-rec { margin-top: 8px; }

.fp-score { font-weight: 700; font-size: 13px; min-width: 52px; }
.fp-weight-cell { font-weight: 600; color: var(--el-color-primary); }
.fp-up { color: var(--el-color-danger); }
.fp-down { color: var(--el-color-success); }
.fp-muted { color: var(--text-secondary); }

.fp-summary { padding: 8px 4px; line-height: 1.7; }
.fp-panel-actions { display: flex; align-items: center; gap: 12px; margin-bottom: 16px; flex-wrap: wrap; }
.fp-bt-stats { display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 18px; }
.fp-h4 { margin: 18px 0 10px; font-size: 14px; color: var(--text-primary); }
.fp-bt-cols { display: grid; grid-template-columns: 1fr 1fr; gap: 24px; }
@media (max-width: 760px) { .fp-bt-cols { grid-template-columns: 1fr; } .fp-bt-stats { grid-template-columns: repeat(2, 1fr); } }
.fp-opt-state { margin-bottom: 18px; }
.fp-reset { margin-left: auto; }
.fp-history-table { cursor: pointer; }

/* ───── 精致化（清爽 SaaS 调性） ───── */
.fp-head-card, .fp-result-card {
  border-radius: 14px;
  border: 1px solid var(--el-border-color-lighter);
  box-shadow: 0 1px 3px rgba(0, 0, 0, .04);
}
.fp-wbar { width: 56px; height: 7px; border-radius: 4px; }
.fp-cta {
  height: 40px; padding: 0 22px; font-size: 14px; font-weight: 600;
  border: none; border-radius: 10px;
  background: linear-gradient(135deg, #6366f1, #8b5cf6);
  box-shadow: 0 6px 16px rgba(99, 102, 241, .28);
}
.fp-cta:hover { background: linear-gradient(135deg, #5457e6, #7c4ddc); }
/* 融合分：渐变焦点徽章 */
.fp-score {
  display: inline-block; min-width: 50px; padding: 4px 11px;
  border-radius: 9px; font-weight: 700; font-size: 13px; color: #fff;
  font-variant-numeric: tabular-nums; letter-spacing: .2px;
}
.fp-score--hot  { background: linear-gradient(135deg, #ff6b6b, #e8503a); box-shadow: 0 3px 8px rgba(238, 80, 58, .26); }
.fp-score--high { background: linear-gradient(135deg, #ffa94d, #ff922b); box-shadow: 0 3px 8px rgba(255, 146, 43, .22); }
.fp-score--mid  { background: linear-gradient(135deg, #5c9dff, #3b82f6); box-shadow: 0 3px 8px rgba(59, 130, 246, .2); }
.fp-score--low  { background: var(--el-fill-color); color: var(--text-secondary); }
/* 结果表：表头底色 + 等宽数字 + 紧凑行 */
.fp-result-card :deep(.el-table) { font-variant-numeric: tabular-nums; }
.fp-result-card :deep(.el-table th.el-table__cell) {
  background: var(--el-fill-color-light);
  font-weight: 600; color: var(--text-primary);
}
.fp-result-card :deep(.el-table td.el-table__cell) { padding: 9px 0; }
/* 一键调仓卡 */
.fp-rebal { margin: 0 0 16px; padding: 14px 16px; border-radius: 12px; background: var(--el-fill-color-light); border: 1px solid var(--el-border-color-lighter); }
.fp-rebal-head { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.fp-rebal-title { font-size: 14px; font-weight: 600; color: var(--text-primary); }
.fp-rebal-sub { margin-right: auto; font-size: 12px; color: var(--text-secondary); }
.fp-rebal-ratio { font-size: 12px; color: var(--text-secondary); }
.fp-rebal-dropped { margin-top: 10px; font-size: 12px; color: var(--el-color-warning); }
.fp-rebal-empty { margin-top: 10px; font-size: 13px; color: var(--text-secondary); }
.fp-rebal-table { margin-top: 12px; }
</style>
