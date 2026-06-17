<template>
  <div class="strategy-manager-container">
    <!-- Header Area -->
    <div class="page-header">
      <div class="header-content">
        <h2>策略管理中心</h2>
        <p class="subtitle">灵活配置选股模型与交易规则，驱动自动化投资</p>
      </div>
      <div class="header-actions">
        <el-button type="primary" size="large" @click="openCreate('selection')">
          <el-icon><Plus /></el-icon> 新建选股策略
        </el-button>
        <el-button type="success" size="large" @click="openCreate('trading')">
          <el-icon><Plus /></el-icon> 新建交易策略
        </el-button>
        <el-button size="large" @click="loadList" :loading="loading">
          <el-icon><Refresh /></el-icon>
        </el-button>
      </div>
    </div>

    <!-- Tabs -->
    <div class="strategy-tabs-wrapper">
      <el-tabs v-model="activeTab" class="custom-tabs">
        <el-tab-pane label="选股策略 (Selection)" name="selection">
          <div class="card-grid" v-loading="loading">
            <StrategyCard
              v-for="item in selectionList"
              :key="item._id"
              :item="item"
              :active-tab="activeTab"
              :toggling-id="togglingId"
              :testing-id="testingId"
              @toggle="toggleEnabled"
              @edit="openEdit"
              @duplicate="duplicateStrategy"
              @delete="confirmDelete"
              @test="startTest"
            />
            <div v-if="!loading && selectionList.length === 0" class="empty-state">
              <el-empty description="暂无选股策略，请点击右上角新建" />
            </div>
          </div>
        </el-tab-pane>
        <el-tab-pane label="交易策略 (Trading)" name="trading">
          <div class="card-grid" v-loading="loading">
            <StrategyCard
              v-for="item in tradingList"
              :key="item._id"
              :item="item"
              :active-tab="activeTab"
              :toggling-id="togglingId"
              :testing-id="testingId"
              @toggle="toggleEnabled"
              @edit="openEdit"
              @duplicate="duplicateStrategy"
              @delete="confirmDelete"
              @test="startTest"
            />
            <div v-if="!loading && tradingList.length === 0" class="empty-state">
              <el-empty description="暂无交易策略，请点击右上角新建" />
            </div>
          </div>
        </el-tab-pane>
      </el-tabs>
    </div>

    <!-- Edit Dialog -->
    <StrategyEditDialog
      v-model="editDialogVisible"
      :is-editing="!!editingStrategy?._id"
      :form="editingStrategy || { name: '', description: '', enabled: false, weights: {}, indicators: [] }"
      :saving="saving"
      @save="saveStrategy"
    />

    <!-- Test Dialog -->
    <StrategyTestDialog
      v-model="testDialogVisible"
      :test-result="testResult"
      :test-progress="testProgress"
      :test-status="testStatus"
      @close="testDialogVisible = false"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { Plus, Refresh } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { strategyApi } from '@/api/strategy'
import type { StrategyRule } from '@/types'

import StrategyCard from './components/StrategyCard.vue'
import StrategyEditDialog from './components/StrategyEditDialog.vue'
import StrategyTestDialog from './components/StrategyTestDialog.vue'

const activeTab = ref<'selection' | 'trading'>('selection')
const list = ref<StrategyRule[]>([])
const loading = ref(false)
const togglingId = ref('')
const testingId = ref('')

// Catalog for indicators
const indicatorCatalog = ref<any[]>([])

// Edit Dialog
const editDialogVisible = ref(false)
const editingStrategy = ref<StrategyRule | null>(null)
const saving = ref(false)

// Test Dialog
const testDialogVisible = ref(false)
const testResult = ref<any>(null)
const testProgress = ref(0)
const testStatus = ref('')
let testPollTimer: ReturnType<typeof setInterval> | null = null

const selectionList = computed(() => list.value.filter(item => item.type === 'selection'))
const tradingList = computed(() => list.value.filter(item => item.type === 'trading'))

onMounted(async () => {
  await Promise.all([loadList(), loadIndicatorCatalog()])
})

onUnmounted(() => {
  if (testPollTimer) clearInterval(testPollTimer)
})

async function loadList() {
  loading.value = true
  try {
    const [selRes, trdRes] = await Promise.all([
      strategyApi.list('selection'),
      strategyApi.list('trading')
    ])
    list.value = [...(selRes.data?.data || []), ...(trdRes.data?.data || [])]
  } catch (error) {
    ElMessage.error('加载策略列表失败')
  } finally {
    loading.value = false
  }
}

async function loadIndicatorCatalog() {
  try {
    const res = await strategyApi.getIndicators()
    indicatorCatalog.value = res.data?.data || []
  } catch (error) {
    console.error('Failed to load indicator catalog', error)
  }
}

async function toggleEnabled(item: StrategyRule, val: boolean) {
  togglingId.value = item._id
  try {
    await strategyApi.update(item._id, { enabled: val })
    item.enabled = val
    ElMessage.success(`${val ? '启用' : '停用'}成功`)
  } catch {
    item.enabled = !val
    ElMessage.error('操作失败')
  } finally {
    togglingId.value = ''
  }
}

function openCreate(type: 'selection' | 'trading') {
  // Initialize default strategy payload
  const defaultWeights = type === 'selection' 
    ? { fundamental: 0.25, technical: 0.25, fund_flow: 0.25, valuation: 0.25 }
    : { entry: 0.5, exit: 0.5 }
    
  const indicators = indicatorCatalog.value
    .filter((c: any) => type === 'selection' ? !['entry', 'exit'].includes(c.dimension) : ['entry', 'exit'].includes(c.dimension))
    .map((c: any) => ({
      key: c.key, dimension: c.dimension, label: c.label,
      enabled: false, weight: c.default_weight || 20,
      params: { ...(c.params || {}) },
      param_schema: c.param_schema || [],
      description: c.description || ''
    }))

  editingStrategy.value = {
    _id: '',
    name: '',
    type,
    description: '',
    enabled: false,
    weights: defaultWeights,
    indicators,
    filters: {}
  } as unknown as StrategyRule
  
  editDialogVisible.value = true
}

function openEdit(item: StrategyRule) {
  editingStrategy.value = JSON.parse(JSON.stringify(item))
  editDialogVisible.value = true
}

async function saveStrategy() {
  if (!editingStrategy.value) return
  const payload = editingStrategy.value
  saving.value = true
  try {
    if (payload._id) {
      await strategyApi.update(payload._id, payload)
      ElMessage.success('配置已保存')
    } else {
      // Remove empty _id for creation
      const { _id, ...createPayload } = payload
      await strategyApi.create(createPayload)
      ElMessage.success('创建成功')
    }
    editDialogVisible.value = false
    await loadList()
  } catch {
    ElMessage.error('保存失败')
  } finally {
    saving.value = false
  }
}

function confirmDelete(item: StrategyRule) {
  ElMessageBox.confirm(`确认删除策略「${item.name}」？此操作不可恢复。`, '删除确认', { 
    type: 'warning' 
  }).then(async () => {
    try {
      await strategyApi.delete(item._id)
      ElMessage.success('已删除')
      await loadList()
    } catch { 
      ElMessage.error('删除失败')
    }
  }).catch(() => {})
}

async function duplicateStrategy(item: StrategyRule) {
  try {
    await strategyApi.create({
      name: item.name + ' (副本)',
      type: item.type,
      description: item.description,
      enabled: false,
      weights: item.weights,
      indicators: JSON.parse(JSON.stringify(item.indicators || [])),
      filters: item.filters,
    })
    ElMessage.success('已复制')
    await loadList()
  } catch { 
    ElMessage.error('复制失败')
  }
}

function _stopTestPoll() {
  if (testPollTimer) { clearInterval(testPollTimer); testPollTimer = null }
}

async function startTest(item: StrategyRule) {
  _stopTestPoll()
  testingId.value = item._id
  
  testResult.value = null
  testProgress.value = 0
  testStatus.value = '>>> 准备测试环境...'
  testDialogVisible.value = true
  
  try {
    await strategyApi.testToPicker(item._id, { top_n: 10, candidate_pool: 30 })
  } catch {
    testingId.value = ''
    testDialogVisible.value = false
    ElMessage.error('测试启动失败')
    return
  }

  testStatus.value = '>>> 正在运行回测，请稍候...'

  testPollTimer = setInterval(async () => {
    try {
      const res = await strategyApi.getTestResult()
      const data = res.data?.data
      if (!data) return
      
      testProgress.value = data.progress ?? 0
      if (data.status && data.status !== testStatus.value) {
        testStatus.value = data.status
      }

      if (!data.is_running) {
        _stopTestPoll()
        testingId.value = ''
        
        if (data.picks && data.picks.length > 0) {
          testResult.value = {
            picks: data.picks || [],
            candidate_count: data.candidate_count || 0,
            universe_count: data.universe_count || 0,
            filtered_count: data.filtered_count || 0,
            timestamp: data.timestamp || new Date().toLocaleTimeString(),
          }
        } else {
          testDialogVisible.value = false
          ElMessage.warning(data.status || '测试无结果')
        }
      }
    } catch { 
      _stopTestPoll()
      testingId.value = ''
      testDialogVisible.value = false
      ElMessage.error('连接测试服务失败')
    }
  }, 1500)
}
</script>

<style scoped>
.strategy-manager-container {
  padding: 24px;
  background-color: var(--bg-page, #f5f7fa);
  min-height: 100%;
  display: flex;
  flex-direction: column;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 24px;
}

.header-content h2 {
  margin: 0;
  font-size: 24px;
  font-weight: 600;
  color: var(--text-primary, #303133);
}

.header-content .subtitle {
  margin: 8px 0 0;
  font-size: 14px;
  color: var(--text-secondary, #909399);
}

.header-actions {
  display: flex;
  gap: 12px;
}

.strategy-tabs-wrapper {
  background: var(--bg-card, #ffffff);
  border-radius: 12px;
  padding: 20px;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.04);
  flex: 1;
  display: flex;
  flex-direction: column;
}

.custom-tabs :deep(.el-tabs__content) {
  padding-top: 16px;
}

.card-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(360px, 1fr));
  gap: 20px;
  min-height: 200px;
}

.empty-state {
  grid-column: 1 / -1;
  display: flex;
  justify-content: center;
  align-items: center;
  padding: 60px 0;
}
</style>