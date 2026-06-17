<template>
  <div class="platform-config">
    <div class="page-header">
      <div>
        <h2>平台配置</h2>
        <span class="page-desc">全局平台参数，修改后立即对新交易生效（不影响历史成交）</span>
      </div>
      <div class="header-actions">
        <span v-if="config?.updated_at" class="updated-at">更新于 {{ formatTime(config.updated_at) }}</span>
        <el-button :disabled="!dirty || saving" @click="reset">还原</el-button>
        <el-button type="primary" :loading="saving" :disabled="!dirty" @click="save">保存</el-button>
      </div>
    </div>

    <!-- 交易费率 -->
    <el-card shadow="never" class="cfg-card" v-loading="loading">
      <template #header>
        <div class="card-title">
          <el-icon><Money /></el-icon>
          <span>交易费率（模拟盘）</span>
        </div>
      </template>

      <el-form label-position="top" class="cfg-form">
        <div class="form-grid">
          <el-form-item label="买入佣金率">
            <el-input-number v-model="form.buyCommissionPct" :min="0" :max="1" :step="0.005"
              :precision="4" controls-position="right" class="num-input" />
            <span class="unit">%</span>
            <div class="field-hint">默认 0.03%（万分之三）</div>
          </el-form-item>

          <el-form-item label="卖出佣金率">
            <el-input-number v-model="form.sellCommissionPct" :min="0" :max="1" :step="0.005"
              :precision="4" controls-position="right" class="num-input" />
            <span class="unit">%</span>
            <div class="field-hint">默认 0.03%（万分之三）</div>
          </el-form-item>

          <el-form-item label="最低佣金">
            <el-input-number v-model="form.minCommission" :min="0" :max="1000" :step="1"
              :precision="2" controls-position="right" class="num-input" />
            <span class="unit">元</span>
            <div class="field-hint">单笔佣金不低于此值，默认 5 元</div>
          </el-form-item>

          <el-form-item label="印花税率">
            <el-input-number v-model="form.stampTaxPct" :min="0" :max="1" :step="0.01"
              :precision="4" controls-position="right" class="num-input" />
            <span class="unit">%</span>
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

    <!-- 预留：未来可在此追加更多平台配置分区 -->
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Money } from '@element-plus/icons-vue'
import { platformConfigApi, type PlatformConfig } from '@/api/platformConfig'

const loading = ref(false)
const saving = ref(false)
const config = ref<PlatformConfig | null>(null)
const exampleAmount = 10000

const form = reactive({
  buyCommissionPct: 0.03,
  sellCommissionPct: 0.03,
  minCommission: 5,
  stampTaxPct: 0.1,
})

function applyConfig(c: PlatformConfig) {
  form.buyCommissionPct = +(c.buy_commission_rate * 100).toFixed(4)
  form.sellCommissionPct = +(c.sell_commission_rate * 100).toFixed(4)
  form.minCommission = c.min_commission
  form.stampTaxPct = +(c.stamp_tax_rate * 100).toFixed(4)
}

const dirty = computed(() => {
  if (!config.value) return false
  return (
    +(config.value.buy_commission_rate * 100).toFixed(4) !== form.buyCommissionPct ||
    +(config.value.sell_commission_rate * 100).toFixed(4) !== form.sellCommissionPct ||
    config.value.min_commission !== form.minCommission ||
    +(config.value.stamp_tax_rate * 100).toFixed(4) !== form.stampTaxPct
  )
})

const buyFeeExample = computed(() =>
  Math.max(form.minCommission, exampleAmount * form.buyCommissionPct / 100)
)
const sellCommissionExample = computed(() =>
  Math.max(form.minCommission, exampleAmount * form.sellCommissionPct / 100)
)
const stampTaxExample = computed(() => exampleAmount * form.stampTaxPct / 100)

function formatTime(iso: string) {
  return iso.replace('T', ' ').slice(0, 19)
}

async function load() {
  loading.value = true
  try {
    const c = await platformConfigApi.get()
    config.value = c
    applyConfig(c)
  } finally {
    loading.value = false
  }
}

function reset() {
  if (config.value) applyConfig(config.value)
}

async function save() {
  saving.value = true
  try {
    const updated = await platformConfigApi.update({
      buy_commission_rate: form.buyCommissionPct / 100,
      sell_commission_rate: form.sellCommissionPct / 100,
      min_commission: form.minCommission,
      stamp_tax_rate: form.stampTaxPct / 100,
    })
    config.value = updated
    applyConfig(updated)
    ElMessage.success('平台配置已保存')
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.error || e?.message || '保存失败')
  } finally {
    saving.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.platform-config {
  padding: 0;
}

.page-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 20px;
}

.page-header h2 {
  margin: 0;
  font-size: 20px;
  font-weight: 600;
  color: var(--text-primary);
}

.page-desc {
  font-size: 13px;
  color: var(--text-muted);
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

.updated-at {
  font-size: 12px;
  color: var(--text-faint);
  font-variant-numeric: tabular-nums;
}

.cfg-card {
  border-radius: var(--radius-md, 10px);
  margin-bottom: 20px;
}

.card-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
}

.cfg-form {
  max-width: 760px;
}

.form-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(220px, 1fr));
  gap: 20px 32px;
}

.num-input {
  width: 160px;
}

.unit {
  margin-left: 8px;
  color: var(--text-muted);
  font-size: 13px;
}

.field-hint {
  width: 100%;
  margin-top: 4px;
  font-size: 12px;
  color: var(--text-faint);
}

.example-box {
  margin-top: 24px;
  padding: 16px;
  border-radius: 8px;
  background: var(--bg-soft, #f8f9fa);
  border: 1px solid var(--border-color-light, #f0f2f5);
}

.example-title {
  font-size: 13px;
  color: var(--text-muted);
  margin-bottom: 10px;
}

.example-row {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 13px;
  color: var(--text-regular, #606266);
  padding: 4px 0;
}

.example-row b {
  color: var(--el-color-primary, #409eff);
  font-variant-numeric: tabular-nums;
}

.sep {
  color: var(--text-faint);
}

@media (max-width: 640px) {
  .form-grid {
    grid-template-columns: 1fr;
  }
}
</style>
