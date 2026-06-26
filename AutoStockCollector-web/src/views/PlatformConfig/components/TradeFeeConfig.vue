<template>
  <el-card shadow="never" class="cfg-card" v-loading="loading">
    <template #header>
      <div class="card-title">
        <div class="title-icon-small">
          <el-icon><Money /></el-icon>
        </div>
        <span>交易费率（模拟盘）</span>
      </div>
    </template>

    <el-form label-position="top" class="cfg-form">
      <div class="form-grid">
        <el-form-item label="买入佣金率">
          <div class="input-group">
            <el-input-number v-model="form.buyCommissionPct" :min="0" :max="1" :step="0.005"
              :precision="4" controls-position="right" class="fluid-input" />
            <span class="unit">%</span>
          </div>
          <div class="field-hint">默认 0.03%（万分之三）</div>
        </el-form-item>

        <el-form-item label="卖出佣金率">
          <div class="input-group">
            <el-input-number v-model="form.sellCommissionPct" :min="0" :max="1" :step="0.005"
              :precision="4" controls-position="right" class="fluid-input" />
            <span class="unit">%</span>
          </div>
          <div class="field-hint">默认 0.03%（万分之三）</div>
        </el-form-item>

        <el-form-item label="最低佣金">
          <div class="input-group">
            <el-input-number v-model="form.minCommission" :min="0" :max="1000" :step="1"
              :precision="2" controls-position="right" class="fluid-input" />
            <span class="unit">元</span>
          </div>
          <div class="field-hint">单笔佣金不低于此值，默认 5 元</div>
        </el-form-item>

        <el-form-item label="印花税率">
          <div class="input-group">
            <el-input-number v-model="form.stampTaxPct" :min="0" :max="1" :step="0.01"
              :precision="4" controls-position="right" class="fluid-input" />
            <span class="unit">%</span>
          </div>
          <div class="field-hint">仅卖出收取，默认 0.1%（千分之一）</div>
        </el-form-item>
      </div>

      <div class="example-box">
        <div class="example-title">费用预览</div>
        <div class="example-row">
          <span>买入 ¥{{ exampleAmount.toLocaleString() }}</span>
          <span class="sep">→</span>
          <span>佣金 <b>¥{{ buyFeeExample.toFixed(2) }}</b></span>
        </div>
        <div class="example-row">
          <span>卖出 ¥{{ exampleAmount.toLocaleString() }}</span>
          <span class="sep">→</span>
          <span>佣金 <b>¥{{ sellCommissionExample.toFixed(2) }}</b> + 印花税 <b>¥{{ stampTaxExample.toFixed(2) }}</b></span>
        </div>
      </div>
    </el-form>
  </el-card>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { Money } from '@element-plus/icons-vue'

const props = defineProps<{
  loading: boolean
  form: {
    buyCommissionPct: number
    sellCommissionPct: number
    minCommission: number
    stampTaxPct: number
  }
}>()

const exampleAmount = 10000

const buyFeeExample = computed(() =>
  Math.max(props.form.minCommission, exampleAmount * props.form.buyCommissionPct / 100)
)
const sellCommissionExample = computed(() =>
  Math.max(props.form.minCommission, exampleAmount * props.form.sellCommissionPct / 100)
)
const stampTaxExample = computed(() => exampleAmount * props.form.stampTaxPct / 100)
</script>

<style scoped>
.cfg-card {
  border-radius: 16px;
  border: none;
  box-shadow: 0 4px 16px var(--bg-hover-subtle, rgba(0, 0, 0, 0.04));
  background: var(--bg-card, #ffffff);
  margin-bottom: 20px;
}

.cfg-card :deep(.el-card__header) {
  border-bottom: 1px solid var(--el-border-color-lighter);
  padding: 16px 24px;
}

.cfg-card :deep(.el-card__body) {
  padding: 24px;
}

.card-title {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 16px;
  font-weight: 600;
  color: var(--el-text-color-primary);
}

.title-icon-small {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border-radius: 8px;
  background: var(--el-color-primary-light-9);
  color: var(--el-color-primary);
  font-size: 18px;
}

.cfg-form {
  width: 100%;
}

.form-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 24px 40px;
}

.input-group {
  display: flex;
  align-items: center;
  width: 100%;
}

.fluid-input {
  flex: 1;
  width: 100%;
}

.fluid-input :deep(.el-input__wrapper) {
  width: 100%;
}

.unit {
  margin-left: 12px;
  color: var(--el-text-color-regular);
  font-size: 14px;
  white-space: nowrap;
}

.field-hint {
  width: 100%;
  margin-top: 6px;
  font-size: 13px;
  color: var(--el-text-color-secondary);
}

.example-box {
  margin-top: 32px;
  padding: 20px;
  border-radius: 12px;
  background: var(--el-fill-color-lighter);
  border: 1px solid var(--el-border-color-lighter);
}

.example-title {
  font-size: 14px;
  font-weight: 500;
  color: var(--el-text-color-regular);
  margin-bottom: 12px;
  display: flex;
  align-items: center;
  gap: 8px;
}

.example-title::before {
  content: '';
  display: inline-block;
  width: 4px;
  height: 14px;
  background: var(--el-color-primary);
  border-radius: 2px;
}

.example-row {
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 14px;
  color: var(--el-text-color-regular);
  padding: 6px 0;
}

.example-row b {
  color: var(--el-color-primary);
  font-variant-numeric: tabular-nums;
  font-weight: 600;
}

.sep {
  color: var(--el-text-color-placeholder);
}

@media (max-width: 640px) {
  .form-grid {
    grid-template-columns: 1fr;
  }
}
</style>
