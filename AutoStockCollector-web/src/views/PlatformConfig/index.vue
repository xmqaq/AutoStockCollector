<template>
  <div class="platform-config">
    <el-card shadow="never" class="page-header-card">
      <div class="page-header-inner">
        <div class="header-left">
          <div class="title-wrapper">
            <div class="title-icon">⚙️</div>
            <h2>平台配置</h2>
          </div>
          <p class="subtitle">全局平台参数，修改后立即对新交易生效（不影响历史成交）</p>
        </div>
        <div class="header-right">
          <span v-if="config?.updated_at" class="updated-at">更新于 {{ formatTime(config.updated_at) }}</span>
          <el-button :disabled="!dirty || saving" @click="reset" round class="hover-btn">还原</el-button>
          <el-button type="primary" :loading="saving" :disabled="!dirty" @click="save" round class="hover-btn">保存</el-button>
        </div>
      </div>
    </el-card>

    <!-- 交易费率 -->
    <TradeFeeConfig :loading="loading" :form="form" />

    <!-- 预留：未来可在此追加更多平台配置分区 -->
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { platformConfigApi, type PlatformConfig } from '@/api/platformConfig'
import TradeFeeConfig from './components/TradeFeeConfig.vue'

const loading = ref(false)
const saving = ref(false)
const config = ref<PlatformConfig | null>(null)

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
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.page-header-card {
  border-radius: 16px;
  border: none;
  box-shadow: 0 4px 16px var(--bg-hover-subtle, rgba(0, 0, 0, 0.04));
  background: var(--bg-card, #ffffff);
  overflow: hidden;
}

.page-header-card :deep(.el-card__body) {
  padding: 24px;
}

.page-header-inner {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  flex-wrap: wrap;
  gap: 16px;
}

.title-wrapper {
  display: flex;
  align-items: center;
  gap: 12px;
}

.title-icon {
  font-size: 28px;
  background: var(--el-color-primary-light-9);
  width: 48px;
  height: 48px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 12px;
  color: var(--el-color-primary);
}

.header-left h2 {
  margin: 0;
  font-size: 22px;
  font-weight: 600;
  color: var(--el-text-color-primary);
  letter-spacing: 0.5px;
}

.subtitle {
  margin: 8px 0 0 60px;
  font-size: 14px;
  color: var(--el-text-color-secondary);
}

.header-right {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-top: 8px;
}

.updated-at {
  font-size: 13px;
  color: var(--el-text-color-secondary);
  font-variant-numeric: tabular-nums;
  margin-right: 8px;
}

.hover-btn {
  transition: all 0.3s;
}

.hover-btn:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
}
</style>
