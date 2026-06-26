<template>
  <el-table v-if="picks?.length" :data="picks" row-key="code" stripe
            :default-sort="{ prop: 'fusion_score', order: 'descending' }" class="fp-result-table">
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
    <el-table-column prop="code" label="代码" width="100">
      <template #default="{ row }">
        <el-link type="primary" :underline="false" @click="goToStockAnalysis(row.code)">
          {{ row.code }}
        </el-link>
      </template>
    </el-table-column>
    <el-table-column prop="name" label="名称" min-width="110" />
    <el-table-column prop="industry" label="行业" min-width="120" show-overflow-tooltip />
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
</template>

<script setup lang="ts">
import { QuestionFilled } from '@element-plus/icons-vue'
import { renderMd } from '@/utils/markdown'
import { useRouter } from 'vue-router'

const router = useRouter()

const props = defineProps<{
  picks: any[]
}>()

const DIMS = [
  { key: 'fundamental', label: '基本面', color: '#5a7af0' },
  { key: 'technical', label: '技术面', color: 'var(--el-color-warning)' },
  { key: 'fund_flow', label: '资金面', color: 'var(--el-color-success)' },
  { key: 'valuation', label: '估值面', color: 'var(--text-muted)' },
] as const

function scoreLevel(v: number) { return v >= 90 ? 'hot' : v >= 80 ? 'high' : v >= 70 ? 'mid' : 'low' }
function bonusClass(v: number | null) { return v == null ? 'fp-muted' : v > 0 ? 'fp-up' : v < 0 ? 'fp-down' : 'fp-muted' }
function fmtBonus(v: number) { return v > 0 ? `+${v.toFixed(1)}` : v.toFixed(1) }

function goToStockAnalysis(code: string) {
  router.push({ path: '/stock-analysis', query: { code } })
}
</script>

<style scoped>
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
.fp-th { display: inline-flex; align-items: center; gap: 2px; }
.fp-help { font-size: 13px; color: var(--text-secondary); vertical-align: -2px; margin-left: 2px; cursor: help; }

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
.fp-result-table { font-variant-numeric: tabular-nums; }
.fp-result-table :deep(th.el-table__cell) {
  background: var(--el-fill-color-light);
  font-weight: 600; color: var(--text-primary);
}
.fp-result-table :deep(td.el-table__cell) { padding: 9px 0; }
</style>
