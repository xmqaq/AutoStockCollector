<template>
  <div v-if="hasPicks" class="fp-rebal">
    <div class="fp-rebal-head">
      <span class="fp-rebal-title">一键调仓到 AI 组合</span>
      <span class="fp-rebal-sub">按建议仓位对齐模拟盘：自动算整手、现金不足跳过、买不起一手剔除</span>
      <span class="fp-rebal-ratio">目标仓位</span>
      <el-select v-model="localInvestRatio" size="small" style="width:90px" @change="$emit('load-rebalance')">
        <el-option v-for="r in [0.5,0.6,0.7,0.8,0.9,1.0]" :key="r" :label="Math.round(r*100)+'%'" :value="r" />
      </el-select>
      <el-button size="small" :loading="rebalanceLoading" @click="$emit('load-rebalance')">生成清单</el-button>
      <el-button size="small" type="primary" :disabled="!rebalance || !rebalance.orders.length"
                 :loading="executingAll" @click="$emit('exec-all')">全部执行</el-button>
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
          <el-button v-if="!row.skipped" size="small" plain :disabled="executingAll" :loading="executing[row.code]" @click="$emit('exec-one', row)">执行</el-button>
          <el-tooltip v-else :content="row.skip_reason || ''" placement="top">
            <el-tag type="info" size="small">已跳过</el-tag>
          </el-tooltip>
        </template>
      </el-table-column>
    </el-table>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { RebalanceAdvice, RebalanceOrder } from '@/api/strategyPick'

const props = defineProps<{
  hasPicks: boolean
  rebalance: RebalanceAdvice | null
  rebalanceLoading: boolean
  investRatio: number
  executingAll: boolean
  executing: Record<string, boolean>
}>()

const emit = defineEmits<{
  (e: 'update:investRatio', val: number): void
  (e: 'load-rebalance'): void
  (e: 'exec-all'): void
  (e: 'exec-one', order: RebalanceOrder): void
}>()

const localInvestRatio = computed({
  get: () => props.investRatio,
  set: (v) => emit('update:investRatio', v)
})
</script>

<style scoped>
.fp-rebal { margin: 0 0 16px; padding: 14px 16px; border-radius: 12px; background: var(--el-fill-color-light); border: 1px solid var(--el-border-color-lighter); }
.fp-rebal-head { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.fp-rebal-title { font-size: 14px; font-weight: 600; color: var(--text-primary); }
.fp-rebal-sub { margin-right: auto; font-size: 12px; color: var(--text-secondary); }
.fp-rebal-ratio { font-size: 12px; color: var(--text-secondary); }
.fp-rebal-dropped { margin-top: 10px; font-size: 12px; color: var(--el-color-warning); }
.fp-rebal-empty { margin-top: 10px; font-size: 13px; color: var(--text-secondary); }
.fp-rebal-table { margin-top: 12px; }
</style>
