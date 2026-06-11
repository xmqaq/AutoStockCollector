<template>
  <el-card v-if="sections.length" shadow="never" class="section-card">
    <template #header>
      <div class="section-header">
        <span>① 数据采集结果（6大维度）</span>
        <el-tag size="small" type="success">{{ sections.length }} 个数据源</el-tag>
      </div>
    </template>
    <div class="data-source-grid">
      <div
        v-for="ds in sections" :key="ds.tool"
        :class="['data-source-item', { collapsed: collapsed[ds.tool] }]"
        @click="toggleCollapse(ds.tool)"
      >
        <div class="ds-header">
          <span class="ds-icon">{{ ds.icon }}</span>
          <span class="ds-label">{{ ds.label }}</span>
          <span class="ds-badge" :class="ds.badgeClass">{{ ds.badgeText }}</span>
        </div>
        <div class="ds-summary">{{ ds.summary }}</div>
        <div v-if="!collapsed[ds.tool] && ds.tool === 'fund_flow_analysis' && ds.detail?.record" class="ds-detail">
          <div class="ds-row">主力净流入: <strong>{{ ds.detail.record.main_net_inflow }}</strong></div>
          <div class="ds-row">散户净流入: {{ ds.detail.record.retail_net_inflow }}</div>
        </div>
        <div v-else-if="!collapsed[ds.tool] && ds.tool === 'dragon_tiger_analysis' && ds.detail?.records?.length" class="ds-detail">
          <div v-for="(r, i) in ds.detail.records.slice(0, 3)" :key="i" class="ds-row">
            {{ r.dept_name || r.operate_dept }}{{ r.net_amount ? ` · ${r.net_amount}万` : '' }}
          </div>
          <div v-if="ds.detail.records.length > 3" class="ds-row more">等 {{ ds.detail.records.length }} 家营业部</div>
        </div>
        <div v-else-if="!collapsed[ds.tool] && ds.tool === 'news_sentiment' && ds.detail?.records?.length" class="ds-detail">
          <div v-for="(r, i) in ds.detail.records.slice(0, 3)" :key="i" class="ds-row ds-news">
            <span class="news-title">{{ r.title?.slice(0, 35) }}{{ r.title?.length > 35 ? '...' : '' }}</span>
            <span class="news-date">{{ r.publish_date || '' }}</span>
          </div>
        </div>
        <div v-else-if="!collapsed[ds.tool] && ds.tool === 'financial_analysis' && ds.detail?.records?.length" class="ds-detail">
          <div v-for="(r, i) in ds.detail.records.slice(0, 2)" :key="i" class="ds-row">
            {{ r.report_date }} · ROE {{ r.roe }}% · 营收 {{ r.revenue_growth }}%
          </div>
        </div>
        <div v-else-if="!collapsed[ds.tool] && ds.tool === 'kline_trend' && ds.detail?.records?.length" class="ds-detail">
          <div class="ds-row">开盘 {{ ds.detail.records[0]?.open }} · 收盘 {{ ds.detail.records[0]?.close }}</div>
          <div class="ds-row">最高 {{ ds.detail.records[0]?.high }} · 最低 {{ ds.detail.records[0]?.low }}</div>
        </div>
        <div v-else-if="!collapsed[ds.tool] && ds.tool === 'market_capital_flow' && ds.detail" class="ds-detail">
          <div class="ds-row">方向: <strong>{{ ds.detail.market_flow === 'positive' ? '偏多' : '偏空' }}</strong></div>
          <div v-if="ds.detail.date" class="ds-row">日期: {{ ds.detail.date }}</div>
        </div>
      </div>
    </div>
  </el-card>
</template>

<script setup lang="ts">
import { ref, reactive } from 'vue'

const props = defineProps<{
  sections: any[]
}>()

const collapsed = reactive<Record<string, boolean>>({})

function toggleCollapse(tool: string) {
  collapsed[tool] = !collapsed[tool]
}
</script>

<style scoped>
.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.data-source-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 10px;
}
.data-source-item {
  background: var(--border-color);
  border-radius: 8px;
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 6px;
  cursor: pointer;
  transition: all 0.2s;
  border: 1px solid transparent;
}
.data-source-item:hover {
  border-color: #409eff;
}
.data-source-item.collapsed {
  cursor: pointer;
}
.ds-header {
  display: flex;
  align-items: center;
  gap: 6px;
}
.ds-icon {
  font-size: 16px;
}
.ds-label {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-primary);
  flex: 1;
}
.ds-badge {
  font-size: 10px;
  padding: 1px 6px;
  border-radius: 8px;
  font-weight: 600;
}
.ds-badge.ok { background: rgba(103,194,58,0.15); color: #67c23a; }
.ds-badge.err { background: rgba(245,108,108,0.15); color: #f56c6c; }
.ds-summary {
  font-size: 11px;
  color: #67c23a;
}
.ds-detail {
  font-size: 11px;
  color: var(--text-muted);
  line-height: 1.6;
  border-top: 1px solid var(--border-strong);
  padding-top: 6px;
  margin-top: 2px;
}
.ds-row {
  padding: 1px 0;
}
.ds-row.more {
  color: var(--text-faint);
}
.ds-news {
  display: flex;
  justify-content: space-between;
  gap: 8px;
}
.news-title {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.news-date {
  flex-shrink: 0;
  color: var(--text-faint);
}
.section-card {
  background: var(--bg-card);
  border: 1px solid var(--border-color);
}
.section-card :deep(.el-card__header) {
  border-bottom: 1px solid var(--border-color);
  padding: 12px 16px;
  color: var(--text-primary);
  font-size: 14px;
  font-weight: 600;
  display: flex;
  justify-content: space-between;
}
@media (max-width: 900px) {
  .data-source-grid { grid-template-columns: repeat(2, 1fr); }
}
@media (max-width: 600px) {
  .data-source-grid { grid-template-columns: 1fr; }
}
</style>
