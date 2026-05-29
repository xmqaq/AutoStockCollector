<template>
  <div class="strategy-config">
    <el-card shadow="never" class="section-card">
      <template #header>
        <div class="card-header">
          <span>策略管理</span>
          <el-button size="small" type="primary" @click="showAddDialog">
            <el-icon><Plus /></el-icon> 新建策略
          </el-button>
        </div>
      </template>
      <el-empty v-if="list.length === 0 && !loading" description="暂无策略" />
      <el-table v-else :data="list" stripe v-loading="loading">
        <el-table-column prop="name" label="策略名称" min-width="150" />
        <el-table-column prop="strategy_type" label="类型" width="120">
          <template #default="{ row }">
            <el-tag size="small">{{ typeLabel(row.strategy_type) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="description" label="描述" min-width="200" show-overflow-tooltip />
        <el-table-column label="启用" width="80">
          <template #default="{ row }">
            <el-switch v-model="row.enabled" @change="toggleStrategy(row)" />
          </template>
        </el-table-column>
        <el-table-column label="操作" width="150" align="center">
          <template #default="{ row }">
            <el-button size="small" type="primary" plain @click="editStrategy(row)">编辑</el-button>
            <el-button size="small" type="danger" plain @click="deleteStrategy(row.name)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="600px">
      <el-form :model="form" label-width="100px">
        <el-form-item label="策略名称" required>
          <el-input v-model="form.name" :disabled="isEdit" placeholder="如：我的资金策略" />
        </el-form-item>
        <el-form-item label="策略类型" required>
          <el-select v-model="form.strategy_type" style="width:100%">
            <el-option label="资金异动" value="fund_flow" />
            <el-option label="趋势跟踪" value="trend" />
            <el-option label="价值投资" value="fundamental" />
            <el-option label="超跌反弹" value="reversal" />
            <el-option label="板块轮动" value="sector" />
            <el-option label="综合评分" value="multi_factor" />
          </el-select>
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="form.description" type="textarea" :rows="2" placeholder="简要描述策略逻辑" />
        </el-form-item>
        <el-divider content-position="left">参数配置</el-divider>
        <template v-if="form.strategy_type === 'fund_flow'">
          <el-form-item label="最低评分">
            <el-input-number v-model="form.params.min_score" :min="0" :max="100" />
          </el-form-item>
          <el-form-item label="最低净流入">
            <el-input-number v-model="form.params.min_inflow" :min="0" />
          </el-form-item>
          <el-form-item label="量比阈值">
            <el-input-number v-model="form.params.volume_ratio" :min="1" :step="0.1" />
          </el-form-item>
        </template>
        <template v-else-if="form.strategy_type === 'trend'">
          <el-form-item label="短期均线">
            <el-input-number v-model="form.params.ma_short" :min="5" :max="30" />
          </el-form-item>
          <el-form-item label="长期均线">
            <el-input-number v-model="form.params.ma_long" :min="20" :max="120" />
          </el-form-item>
          <el-form-item label="最低评分">
            <el-input-number v-model="form.params.min_trend_score" :min="0" :max="100" />
          </el-form-item>
        </template>
        <template v-else-if="form.strategy_type === 'fundamental'">
          <el-form-item label="最低PE">
            <el-input-number v-model="form.params.min_pe" :min="0" />
          </el-form-item>
          <el-form-item label="最高PE">
            <el-input-number v-model="form.params.max_pe" :min="0" />
          </el-form-item>
          <el-form-item label="最低ROE(%)">
            <el-input-number v-model="form.params.min_roe" :min="0" />
          </el-form-item>
        </template>
        <template v-else-if="form.strategy_type === 'reversal'">
          <el-form-item label="最大回撤(%)">
            <el-input-number v-model="form.params.max_drawdown" :min="0" :max="50" />
          </el-form-item>
          <el-form-item label="最小量比">
            <el-input-number v-model="form.params.min_volume_ratio" :min="1" :step="0.1" />
          </el-form-item>
        </template>
        <template v-else-if="form.strategy_type === 'sector'">
          <el-form-item label="热门板块数">
            <el-input-number v-model="form.params.top_blocks" :min="1" :max="50" />
          </el-form-item>
          <el-form-item label="动量天数">
            <el-input-number v-model="form.params.momentum_days" :min="1" />
          </el-form-item>
        </template>
        <template v-else-if="form.strategy_type === 'multi_factor'">
          <el-form-item label="情绪权重">
            <el-slider v-model="form.params.sentiment_weight" :min="0" :max="1" :step="0.05" show-input />
          </el-form-item>
          <el-form-item label="资金权重">
            <el-slider v-model="form.params.flow_weight" :min="0" :max="1" :step="0.05" show-input />
          </el-form-item>
          <el-form-item label="技术权重">
            <el-slider v-model="form.params.technical_weight" :min="0" :max="1" :step="0.05" show-input />
          </el-form-item>
          <el-form-item label="基本面权重">
            <el-slider v-model="form.params.fundamental_weight" :min="0" :max="1" :step="0.05" show-input />
          </el-form-item>
        </template>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="saveStrategy" :loading="saveLoading">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { strategyConfigApi, type StrategyConfig } from '@/api/strategyConfig'

const loading = ref(false)
const saveLoading = ref(false)
const list = ref<StrategyConfig[]>([])
const dialogVisible = ref(false)
const isEdit = ref(false)

const defaultForm = () => ({
  name: '',
  strategy_type: 'fund_flow' as string,
  description: '',
  params: {} as Record<string, number>,
  enabled: true,
})

const form = ref(defaultForm())

const dialogTitle = computed(() => isEdit.value ? '编辑策略' : '新建策略')

const typeMap: Record<string, string> = {
  fund_flow: '资金异动',
  trend: '趋势跟踪',
  fundamental: '价值投资',
  reversal: '超跌反弹',
  sector: '板块轮动',
  multi_factor: '综合评分',
}

function typeLabel(type: string) {
  return typeMap[type] || type
}

function initParams(type: string) {
  const templates: Record<string, Record<string, number>> = {
    fund_flow: { min_score: 65, min_inflow: 10000000, volume_ratio: 1.5, flow_weight: 0.6, volume_weight: 0.4 },
    trend: { ma_short: 10, ma_long: 20, min_trend_score: 60, volume_threshold: 1.2 },
    fundamental: { min_pe: 5, max_pe: 30, min_roe: 10, min_growth: 5 },
    reversal: { max_drawdown: 10, min_recovery_days: 3, min_volume_ratio: 1.3 },
    sector: { top_blocks: 10, momentum_days: 3, min_momentum_score: 60 },
    multi_factor: { sentiment_weight: 0.2, flow_weight: 0.25, technical_weight: 0.25, fundamental_weight: 0.3, min_total_score: 60 },
  }
  return templates[type] ? { ...templates[type] } : {}
}

async function loadData() {
  loading.value = true
  try {
    const res = await strategyConfigApi.getList()
    list.value = res.data?.data || res.data || []
  } catch {
    list.value = []
  } finally {
    loading.value = false
  }
}

function showAddDialog() {
  isEdit.value = false
  form.value = defaultForm()
  dialogVisible.value = true
}

function editStrategy(row: StrategyConfig) {
  isEdit.value = true
  form.value = {
    name: row.name,
    strategy_type: row.strategy_type,
    description: row.description,
    params: { ...row.params },
    enabled: row.enabled,
  }
  dialogVisible.value = true
}

async function saveStrategy() {
  if (!form.value.name.trim()) {
    ElMessage.warning('请输入策略名称')
    return
  }
  if (!form.value.strategy_type) {
    ElMessage.warning('请选择策略类型')
    return
  }

  saveLoading.value = true
  try {
    await strategyConfigApi.create({
      name: form.value.name,
      strategy_type: form.value.strategy_type,
      description: form.value.description,
      params: form.value.params,
      enabled: form.value.enabled,
    })
    ElMessage.success('保存成功')
    dialogVisible.value = false
    await loadData()
  } catch {
    ElMessage.error('保存失败')
  } finally {
    saveLoading.value = false
  }
}

async function toggleStrategy(row: StrategyConfig) {
  try {
    await strategyConfigApi.toggle(row.name, row.enabled)
    ElMessage.success(row.enabled ? '已启用' : '已禁用')
  } catch {
    row.enabled = !row.enabled
    ElMessage.error('操作失败')
  }
}

async function deleteStrategy(name: string) {
  try {
    await ElMessageBox.confirm(`确定删除策略「${name}」吗？`, '删除确认', { type: 'warning' })
    await strategyConfigApi.delete(name)
    ElMessage.success('已删除')
    await loadData()
  } catch {
    // cancelled
  }
}

onMounted(() => loadData())
</script>

<style scoped>
.strategy-config {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.section-card {
  background: #1f1f1f;
  border: 1px solid #2c2c2c;
}

.section-card :deep(.el-card__header) {
  border-bottom: 1px solid #2c2c2c;
  padding: 12px 16px;
  color: #e5eaf3;
  font-size: 14px;
  font-weight: 600;
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
</style>