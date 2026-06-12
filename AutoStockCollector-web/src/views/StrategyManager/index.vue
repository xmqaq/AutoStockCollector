<template>
  <div class="sm-page">
    <!-- 顶部操作栏 -->
    <div class="sm-toolbar">
      <el-radio-group v-model="activeTab" size="small" @change="loadList">
        <el-radio-button value="selection">📊 选股策略 <el-tag size="small" type="info" round>{{ selectionCount }}</el-tag></el-radio-button>
        <el-radio-button value="trading">🪙 交易策略 <el-tag size="small" type="info" round>{{ tradingCount }}</el-tag></el-radio-button>
      </el-radio-group>
      <div class="sm-toolbar-right">
        <el-input v-model="searchText" size="small" placeholder="搜索策略..." clearable prefix-icon="Search" style="width:200px" @input="filterList" />
        <el-button size="small" @click="applyPresets"><el-icon><Refresh /></el-icon> 重置预设</el-button>
        <el-button type="primary" size="small" @click="openCreate"><el-icon><Plus /></el-icon> 新建策略</el-button>
      </div>
    </div>

    <!-- 加载态 -->
    <div v-if="loading" class="sm-loading"><el-icon class="is-loading"><Loading /></el-icon> 加载中...</div>

    <!-- 空态 -->
    <template v-else-if="filteredList.length === 0">
      <el-empty :description="searchText ? '无匹配策略' : '暂无策略，点击上方「重置预设」或「新建策略」'" />
    </template>

    <!-- 策略卡片网格 -->
    <template v-else>
      <div class="sm-grid">
        <el-card v-for="item in filteredList" :key="item._id" :class="['sm-card', { 'sm-card-disabled': !item.enabled }]" shadow="hover">
          <!-- 卡片头部 -->
          <div class="sm-card-header">
            <div class="sm-card-title-row">
              <div class="sm-card-title-left">
                <span class="sm-card-name">{{ item.name }}</span>
                <el-tag :type="item.enabled ? 'success' : 'info'" size="small" effect="plain" round>
                  {{ item.enabled ? '启用' : '停用' }}
                </el-tag>
              </div>
              <div class="sm-card-header-right">
                <el-button
                  text
                  size="small"
                  type="danger"
                  @click.stop="confirmDelete(item)"
                ><el-icon :size="16"><Delete /></el-icon></el-button>
                <el-switch
                  v-model="item.enabled"
                  size="small"
                  :loading="togglingId === item._id"
                  @click.stop
                  @change="(v: boolean) => toggleEnabled(item, v)"
                />
              </div>
            </div>
            <p class="sm-card-desc">{{ item.description }}</p>
          </div>

          <!-- 维度权重可视化 -->
          <div class="sm-card-body">
            <div class="sm-weight-vis" :title="weightTooltip(item)">
              <div
                v-for="(w, dim) in item.weights"
                :key="dim"
                :style="{ width: (w * 100) + '%', backgroundColor: dimColor(dim), opacity: w > 0 ? 0.85 : 0.1 }"
                class="sm-weight-seg"
              />
            </div>
            <div class="sm-weight-labels">
              <span v-for="(w, dim) in item.weights" :key="dim" class="sm-weight-label-item" :style="{ color: dimColor(dim) }">
                ● {{ dimLabel(dim) }} {{ (w * 100).toFixed(0) }}%
              </span>
            </div>
            <div class="sm-indicator-summary">
              <el-icon :size="14"><List /></el-icon>
              <span>指标 {{ enabledCount(item) }}/{{ totalCount(item) }} 启用</span>
              <template v-if="item.type === 'selection'">
                <el-divider direction="vertical" />
                <el-icon :size="14"><Filter /></el-icon>
                <span>过滤: {{ filterSummary(item) }}</span>
              </template>
            </div>
          </div>

          <!-- 卡片操作按钮 -->
          <div class="sm-card-actions">
            <el-button size="small" @click="openEdit(item)"><el-icon><Edit /></el-icon> 编辑</el-button>
            <el-button size="small" @click="duplicateStrategy(item)"><el-icon><CopyDocument /></el-icon> 复制</el-button>
            <el-button
              v-if="activeTab === 'selection'"
              size="small"
              :loading="testingId === item._id"
              @click="testStrategy(item)"
            ><el-icon><DataAnalysis /></el-icon> 测试</el-button>
          </div>
        </el-card>
      </div>
    </template>

    <!-- 创建/编辑策略对话框 -->
    <el-dialog
      v-model="dialogVisible"
      :title="isEditing ? '编辑策略' : '新建策略'"
      width="800px"
      top="5vh"
      :close-on-click-modal="false"
      destroy-on-close
    >
      <el-form :model="form" label-width="70px" size="small" @submit.prevent>
        <div class="sm-dialog-layout">
          <!-- 左栏: 基本信息 + 维度权重 -->
          <div class="sm-dialog-left">
            <div class="sm-section-title">基本信息</div>
            <el-form-item label="名称">
              <el-input v-model="form.name" placeholder="策略名称，如：价值精选" maxlength="20" show-word-limit />
            </el-form-item>
            <el-form-item label="描述">
              <el-input v-model="form.description" type="textarea" :rows="2" placeholder="简要描述策略思路" maxlength="100" show-word-limit />
            </el-form-item>
            <el-form-item label="状态">
              <el-switch v-model="form.enabled" active-text="启用" inactive-text="停用" />
            </el-form-item>

            <div class="sm-section-title">维度权重</div>
            <div class="sm-weight-editor">
              <div v-for="(val, dim) in form.weights" :key="dim" class="sm-weight-row">
                <span class="sm-weight-label" :style="{ color: dimColor(dim) }">● {{ dimLabel(dim) }}</span>
                <el-slider
                  v-model="form.weights[dim]"
                  :min="0"
                  :max="1"
                  :step="0.05"
                  :format-tooltip="(v: number) => `${Math.round(v * 100)}%`"
                  style="flex:1;margin:0 10px"
                />
                <span class="sm-weight-val">{{ Math.round(val * 100) }}%</span>
              </div>
              <div class="sm-weight-total">
                合计: <span :class="weightTotal === 100 ? 'sm-green' : 'sm-red'">{{ weightTotal }}%</span>
                <span v-if="weightTotal !== 100" class="sm-weight-hint">（建议凑整 100%）</span>
              </div>
            </div>
          </div>

          <!-- 右栏: 指标配置 -->
          <div class="sm-dialog-right">
            <div class="sm-section-title">
              指标明细
              <span class="sm-ind-count">{{ enabledIndicatorCount }}/{{ form.indicators.length }} 启用</span>
            </div>
            <div class="sm-indicator-editor">
              <div
                v-for="group in groupedIndicators"
                :key="group.dimension"
                class="sm-ind-group"
              >
                <div class="sm-ind-group-title" :style="{ color: dimColor(group.dimension) }">
                  {{ dimLabel(group.dimension) }} ({{ group.items.filter(i => i.enabled).length }}/{{ group.items.length }})
                </div>
                <div v-for="(ind, idx) in group.items" :key="ind.key" class="sm-indicator-row">
                  <el-switch v-model="ind.enabled" size="small" @click.stop />
                  <div class="sm-ind-info" :class="{ 'sm-ind-disabled': !ind.enabled }">
                    <span class="sm-ind-label">{{ ind.label }}</span>
                    <span class="sm-ind-desc" v-if="ind.description">{{ ind.description }}</span>
                  </div>
                  <!-- 权重滑块 -->
                  <div v-if="ind.enabled" class="sm-ind-weight-editor">
                    <span class="sm-ind-weight-label">权重</span>
                    <el-slider
                      v-model="ind.weight"
                      :min="1"
                      :max="100"
                      :step="1"
                      :show-tooltip="true"
                      :format-tooltip="(v: number) => `${v}`"
                      style="width:100px"
                      size="small"
                    />
                    <span class="sm-ind-weight-num">{{ ind.weight }}</span>
                  </div>
                  <!-- 参数行 -->
                  <div v-if="ind.enabled && ind.param_schema && ind.param_schema.length" class="sm-ind-params">
                    <div v-for="ps in ind.param_schema" :key="ps.key" class="sm-param-item">
                      <span class="sm-param-label">{{ ps.label }}</span>
                      <el-input-number
                        v-model="ind.params![ps.key]"
                        size="small"
                        :min="ps.min"
                        :max="ps.max"
                        :step="ps.step"
                        controls-position="right"
                        class="sm-param-input"
                      />
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </el-form>
      <template #footer>
        <el-button size="small" @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" size="small" :loading="saving" @click="saveStrategy">保存策略</el-button>
      </template>
    </el-dialog>
  <!-- 测试结果对话框 -->
    <el-dialog
      v-model="testDialogVisible"
      title="📋 策略测试结果"
      width="860px"
      top="5vh"
      :close-on-click-modal="false"
      destroy-on-close
      @close="_stopTestPoll"
    >
      <template v-if="testResult">
        <div class="sm-test-stats">
          <el-tag>全市场 {{ testResult.universe_count }} 只</el-tag>
          <el-tag type="warning">过滤剔除 {{ testResult.filtered_count }} 只</el-tag>
          <el-tag type="success">候选池 {{ testResult.candidate_count }} 只</el-tag>
          <el-tag type="info">Top-{{ testResult.picks.length }} 测试结果</el-tag>
        </div>
        <el-table :data="testResult.picks" stripe size="small" max-height="480">
          <el-table-column type="index" label="#" width="50" />
          <el-table-column prop="code" label="代码" width="100" />
          <el-table-column prop="name" label="名称" min-width="120" />
          <el-table-column prop="industry" label="行业" width="120" />
          <el-table-column label="综合评分" width="100">
            <template #default="{ row }">
              <span :style="{ color: row.composite >= 70 ? '#3f9d70' : row.composite >= 50 ? '#c9943a' : '#d05a51' }">
                {{ row.composite.toFixed(1) }}
              </span>
            </template>
          </el-table-column>
          <el-table-column label="基本面" width="80">
            <template #default="{ row }">
              <span :style="{ color: row.dim_scores?.fundamental >= 70 ? '#3f9d70' : '#c9943a' }">
                {{ (row.dim_scores?.fundamental || 0).toFixed(0) }}
              </span>
            </template>
          </el-table-column>
          <el-table-column label="技术面" width="80">
            <template #default="{ row }">
              <span :style="{ color: row.dim_scores?.technical >= 70 ? '#3f9d70' : '#c9943a' }">
                {{ (row.dim_scores?.technical || 0).toFixed(0) }}
              </span>
            </template>
          </el-table-column>
          <el-table-column label="资金面" width="80">
            <template #default="{ row }">
              <span :style="{ color: row.dim_scores?.fund_flow >= 70 ? '#3f9d70' : '#c9943a' }">
                {{ (row.dim_scores?.fund_flow || 0).toFixed(0) }}
              </span>
            </template>
          </el-table-column>
          <el-table-column label="估值面" width="80">
            <template #default="{ row }">
              <span :style="{ color: row.dim_scores?.valuation >= 70 ? '#3f9d70' : '#c9943a' }">
                {{ (row.dim_scores?.valuation || 0).toFixed(0) }}
              </span>
            </template>
          </el-table-column>
        </el-table>
      </template>
      <div v-else class="sm-test-loading">
        <el-progress :percentage="testProgress" :stroke-width="8" :status="testProgress < 100 ? '' : 'success'" />
        <p>{{ testStatus }}</p>
      </div>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Loading, Plus, Edit, Delete, CopyDocument,
  Search, Refresh, List, Filter, DataAnalysis,
} from '@element-plus/icons-vue'
import { strategyApi } from '@/api/strategy'
import type { StrategyTestPick } from '@/api/strategy'
import type { StrategyRule, IndicatorItem } from '@/types'

const activeTab = ref<'selection' | 'trading'>('selection')
const list = ref<StrategyRule[]>([])
const filtered = ref<StrategyRule[]>([])
const loading = ref(false)
const searchText = ref('')
const togglingId = ref('')

const dialogVisible = ref(false)
const isEditing = ref(false)
const saving = ref(false)
const editingId = ref('')

const testingId = ref('')
const testDialogVisible = ref(false)
const testResult = ref<{
  picks: StrategyTestPick[]
  candidate_count: number
  universe_count: number
  filtered_count: number
  timestamp: string
} | null>(null)
const testProgress = ref(0)
const testStatus = ref('')

const defaultWeights = { fundamental: 0.25, technical: 0.25, fund_flow: 0.25, valuation: 0.25 }

const form = ref<{
  name: string; description: string; enabled: boolean
  weights: Record<string, number>
  indicators: IndicatorItem[]
}>({
  name: '', description: '', enabled: true,
  weights: { ...defaultWeights },
  indicators: [],
})

// ==================== computed ====================
const selectionCount = computed(() => list.value.filter(s => s.type === 'selection').length)
const tradingCount = computed(() => list.value.filter(s => s.type === 'trading').length)

const filteredList = computed(() => searchText.value ? filtered.value : list.value)

const weightTotal = computed(() => {
  return Math.round(Object.values(form.value.weights).reduce((s, v) => s + v, 0) * 100)
})

const enabledIndicatorCount = computed(() => form.value.indicators.filter(i => i.enabled).length)

const groupedIndicators = computed(() => {
  const groups: { dimension: string; items: IndicatorItem[] }[] = []
  const map = new Map<string, IndicatorItem[]>()
  for (const ind of form.value.indicators) {
    const d = ind.dimension
    if (!map.has(d)) map.set(d, [])
    map.get(d)!.push(ind)
  }
  for (const [dimension, items] of map) {
    groups.push({ dimension, items })
  }
  return groups
})

// ==================== helpers ====================
const dimLabels: Record<string, string> = {
  fundamental: '基本面', technical: '技术面', fund_flow: '资金面', valuation: '估值面',
  entry: '买入信号', exit: '卖出信号',
}

function dimLabel(d: string) { return dimLabels[d] || d }
function dimColor(d: string) {
  const c: Record<string, string> = {
    fundamental: '#3f7fae', technical: '#c9943a', fund_flow: '#3f9d70',
    valuation: '#d05a51', entry: '#909399', exit: '#909399',
  }
  return c[d] || '#909399'
}

function paramLabel(k: string): string {
  const map: Record<string, string> = {
    min: '最小值', max: '最大值', threshold: '阈值',
    fast: '快线周期', slow: '慢线周期', volume_ratio: '量比阈值',
    loss_pct: '止损%', profit_pct: '止盈%', grid_pct: '网格%',
    max_grids: '最大网格', ratio: '放量倍数',
  }
  return map[k] || k
}

function weightTooltip(item: StrategyRule) {
  return Object.entries(item.weights || {})
    .map(([k, v]) => `${dimLabel(k)} ${Math.round(v * 100)}%`).join(' | ')
}

function enabledCount(item: StrategyRule) { return (item.indicators || []).filter(i => i.enabled).length }
function totalCount(item: StrategyRule) { return (item.indicators || []).length }
function hasParams(ind: IndicatorItem) { return ind.params && Object.keys(ind.params).length > 0 }
function globalIdx(group: { dimension: string; items: IndicatorItem[] }, idx: number) {
  return form.value.indicators.indexOf(group.items[idx])
}

function filterSummary(item: StrategyRule) {
  const f = item.filters || {}
  const parts: string[] = []
  if (f.exclude_st !== false) parts.push('去ST')
  if (f.min_kline_bars) parts.push(`K线≥${f.min_kline_bars}`)
  if (f.min_avg_amount) parts.push(`成交≥${(Number(f.min_avg_amount) / 1e8).toFixed(1)}亿`)
  return parts.join(' ') || '默认'
}

// ==================== data loading ====================
async function loadList() {
  loading.value = true
  try {
    const res = await strategyApi.list(activeTab.value)
    list.value = res.data?.data || []
  } catch { list.value = [] }
  finally { loading.value = false }
}

function filterList() {
  const q = searchText.value.toLowerCase()
  filtered.value = list.value.filter(s =>
    s.name.toLowerCase().includes(q) || s.description.toLowerCase().includes(q)
  )
}

// ==================== CRUD ====================
async function toggleEnabled(item: StrategyRule, val: boolean) {
  togglingId.value = item._id
  try {
    await strategyApi.update(item._id, { enabled: val })
  } catch { item.enabled = !val }
  finally { togglingId.value = '' }
}

async function applyPresets() {
  try {
    await ElMessageBox.confirm('将重置所有策略为内置预设，当前修改将丢失，确认？', '重置预设')
    await strategyApi.applyPresets()
    ElMessage.success('预设已重置')
    await loadList()
  } catch { /* cancelled */ }
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
  } catch { /* ignore */ }
}

function openCreate() {
  isEditing.value = false
  editingId.value = ''
  form.value = {
    name: '', description: '', enabled: true,
    weights: { ...defaultWeights },
    indicators: [],
  }
  loadIndicatorCatalog()
  dialogVisible.value = true
}

async function openEdit(item: StrategyRule) {
  isEditing.value = true
  editingId.value = item._id
  // 先加载指标目录以获取 param_schema
  let catalogMap: Record<string, any> = {}
  try {
    const res = await strategyApi.getIndicators()
    for (const c of (res.data?.data || [])) {
      catalogMap[c.key] = c
    }
  } catch { /* ignore */ }
  const indicators = JSON.parse(JSON.stringify(item.indicators || []))
  // 合并 param_schema 到已有指标
  for (const ind of indicators) {
    const cat = catalogMap[ind.key]
    if (cat && !ind.param_schema) {
      ind.param_schema = cat.param_schema || []
    }
    // 确保 params 存在
    if (!ind.params && cat?.params) {
      ind.params = { ...cat.params }
    }
  }
  form.value = {
    name: item.name,
    description: item.description,
    enabled: item.enabled,
    weights: { ...defaultWeights, ...(item.weights || {}) },
    indicators,
  }
  dialogVisible.value = true
}

async function loadIndicatorCatalog() {
  try {
    const res = await strategyApi.getIndicators()
    const catalog = res.data?.data || []
    form.value.indicators = catalog.map((c: any) => ({
      key: c.key,
      dimension: c.dimension,
      label: c.label,
      enabled: false,
      weight: c.default_weight || 20,
      params: { ...(c.params || {}) },
      param_schema: c.param_schema || [],
      description: c.description || '',
    }))
  } catch { /* ignore */ }
}

async function saveStrategy() {
  if (!form.value.name.trim()) {
    ElMessage.warning('请输入策略名称')
    return
  }
  saving.value = true
  try {
    const payload = {
      name: form.value.name,
      description: form.value.description,
      enabled: form.value.enabled,
      type: activeTab.value,
      weights: form.value.weights,
      indicators: form.value.indicators,
      filters: {},
    }
    if (isEditing.value && editingId.value) {
      await strategyApi.update(editingId.value, payload)
      ElMessage.success('策略已更新')
    } else {
      await strategyApi.create(payload)
      ElMessage.success('策略已创建')
    }
    dialogVisible.value = false
    await loadList()
  } catch { /* error handled by client */ }
  finally { saving.value = false }
}

function confirmDelete(item: StrategyRule) {
  ElMessageBox.confirm(`确认删除策略「${item.name}」？此操作不可恢复。`, '删除确认', { confirmButtonText: '删除', cancelButtonText: '取消', type: 'warning' }).then(async () => {
    try {
      await strategyApi.delete(item._id)
      ElMessage.success('已删除')
      await loadList()
    } catch { /* ignore */ }
  }).catch(() => {})
}

let testPollTimer: ReturnType<typeof setInterval> | null = null

function _stopTestPoll() {
  if (testPollTimer) { clearInterval(testPollTimer); testPollTimer = null }
}

async function testStrategy(item: StrategyRule) {
  _stopTestPoll()
  testingId.value = item._id
  testResult.value = null
  testProgress.value = 0
  testStatus.value = '启动中...'
  testDialogVisible.value = true
  try {
    await strategyApi.testToPicker(item._id, { top_n: 10, candidate_pool: 30 })
  } catch {
    testResult.value = null
    testingId.value = ''
    ElMessage.error('测试启动失败')
    return
  }
  testPollTimer = setInterval(async () => {
    try {
      const res = await strategyApi.getTestResult()
      const data = res.data?.data
      if (!data) return
      testProgress.value = data.progress ?? 0
      testStatus.value = data.status || '测试中...'
      if (!data.is_running) {
        _stopTestPoll()
        testingId.value = ''
        if (data.picks && data.picks.length > 0) {
          testResult.value = {
            picks: data.picks || [],
            candidate_count: data.candidate_count || 0,
            universe_count: data.universe_count || 0,
            filtered_count: data.filtered_count || 0,
            timestamp: data.timestamp || '',
          }
        } else {
          testDialogVisible.value = false
          ElMessage.warning(data.status || '测试无结果')
        }
      }
    } catch { _stopTestPoll(); testingId.value = ''; testDialogVisible.value = false }
  }, 2000)
}

onMounted(loadList)
onUnmounted(() => { if (testPollTimer) clearInterval(testPollTimer) })
</script>

<style scoped>
.sm-page { padding: 20px; height: 100%; display: flex; flex-direction: column; }

/* ── 工具栏 ── */
.sm-toolbar { display: flex; align-items: center; justify-content: space-between; margin-bottom: 20px; flex-shrink: 0; flex-wrap: wrap; gap: 10px; }
.sm-toolbar-right { display: flex; align-items: center; gap: 8px; }

/* ── 加载/空态 ── */
.sm-loading { text-align: center; padding: 60px; color: var(--text-muted); font-size: 14px; }

/* ── 卡片网格 ── */
.sm-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(380px, 1fr)); gap: 14px; overflow-y: auto; padding-bottom: 20px; align-items: start; }
.sm-card { border-radius: 10px; transition: all .25s; border: 1px solid var(--border-color); overflow: visible !important; display: flex; flex-direction: column; }
.sm-card:hover { border-color: var(--text-faint); }
.sm-card-disabled { opacity: .55; }
.sm-card :deep(.el-card__body) { overflow: visible !important; padding: 18px; }

/* ── 卡片头部 ── */
.sm-card-header { margin-bottom: 14px; flex-shrink: 0; }
.sm-card-title-row { display: flex; align-items: center; justify-content: space-between; margin-bottom: 6px; }
.sm-card-title-left { display: flex; align-items: center; gap: 8px; min-width: 0; }
.sm-card-header-right { display: flex; align-items: center; gap: 2px; flex-shrink: 0; }
.sm-card-name { font-size: 15px; font-weight: 600; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.sm-card-desc { font-size: 12px; color: var(--text-muted); line-height: 1.5; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; margin: 0; }

/* ── 卡片权重可视化 ── */
.sm-card-body { margin-bottom: 14px; }
.sm-weight-vis { display: flex; height: 6px; border-radius: 3px; overflow: hidden; background: var(--bg-soft); margin-bottom: 8px; }
.sm-weight-seg { transition: width .3s; }
.sm-weight-labels { display: flex; flex-wrap: wrap; gap: 4px 12px; margin-bottom: 8px; }
.sm-weight-label-item { font-size: 11px; }
.sm-indicator-summary { display: flex; align-items: center; gap: 4px; font-size: 12px; color: var(--text-muted); }

/* ── 卡片操作 ── */
.sm-card-actions { display: flex; gap: 6px; flex-wrap: wrap; border-top: 1px solid var(--border-color); padding-top: 12px; margin-top: auto; }

/* ── 对话框双栏布局 ── */
.sm-dialog-layout { display: flex; gap: 20px; max-height: 580px; }
.sm-dialog-left { flex: 1; min-width: 0; overflow-y: auto; padding-right: 4px; }
.sm-dialog-right { flex: 1; min-width: 0; overflow-y: auto; padding-right: 4px; }
.sm-section-title { font-size: 14px; font-weight: 600; margin-bottom: 12px; padding-bottom: 6px; border-bottom: 2px solid var(--el-color-primary); display: flex; align-items: center; justify-content: space-between; }
.sm-ind-count { font-size: 12px; font-weight: 400; color: var(--text-muted); }

/* ── 权重编辑 ── */
.sm-weight-editor { padding: 0 4px; }
.sm-weight-row { display: flex; align-items: center; margin-bottom: 10px; gap: 4px; }
.sm-weight-label { width: 56px; font-size: 12px; flex-shrink: 0; }
.sm-weight-val { width: 36px; text-align: right; font-size: 12px; color: var(--text-secondary); flex-shrink: 0; }
.sm-weight-total { text-align: right; font-size: 12px; padding-top: 4px; border-top: 1px solid var(--border-color); }
.sm-green { color: var(--el-color-success); font-weight: 600; }
.sm-red { color: var(--el-color-danger); font-weight: 600; }
.sm-weight-hint { color: var(--el-color-warning); font-size: 11px; margin-left: 4px; }

/* ── 指标编辑 ── */
.sm-indicator-editor { display: flex; flex-direction: column; gap: 8px; overflow-y: auto; }
.sm-ind-group { border: 1px solid var(--border-color); border-radius: 8px; padding: 8px; }
.sm-ind-group-title { font-size: 12px; font-weight: 600; margin-bottom: 6px; padding-bottom: 4px; border-bottom: 1px solid var(--border-color); }
.sm-indicator-row { display: flex; flex-direction: column; gap: 4px; padding: 6px 0; border-bottom: 1px solid var(--bg-soft); }
.sm-indicator-row:last-child { border-bottom: none; }
.sm-indicator-row > *:first-child { /* switch sits on its own line is not ideal, we want row layout */ }
.sm-indicator-row { flex-direction: row; flex-wrap: wrap; align-items: flex-start; }
.sm-ind-info { flex: 1; min-width: 0; }
.sm-ind-label { font-size: 12px; display: block; line-height: 1.4; }
.sm-ind-desc { font-size: 10px; color: var(--text-faint); display: block; }
.sm-ind-disabled .sm-ind-label { color: var(--text-faint); }
.sm-ind-disabled .sm-ind-desc { color: var(--text-faint); }
.sm-ind-weight-editor { display: flex; align-items: center; gap: 4px; flex-shrink: 0; }
.sm-ind-weight-label { font-size: 10px; color: var(--text-muted); }
.sm-ind-weight-num { font-size: 11px; color: var(--text-secondary); width: 24px; text-align: right; font-variant-numeric: tabular-nums; }
.sm-ind-params { width: 100%; display: flex; flex-wrap: wrap; gap: 6px; padding: 4px 0 0 24px; }
.sm-param-item { display: flex; align-items: center; gap: 4px; }
.sm-param-label { font-size: 10px; color: var(--text-muted); white-space: nowrap; }
.sm-param-input { width: 110px; }

/* ── 测试结果 ── */
.sm-test-stats { display: flex; gap: 8px; margin-bottom: 14px; flex-wrap: wrap; }
.sm-test-loading { text-align: center; padding: 40px 20px; }
.sm-test-loading p { margin-top: 12px; font-size: 13px; color: var(--text-muted); }

/* ── 响应式 ── */
@media (max-width: 768px) {
  .sm-dialog-layout { flex-direction: column; max-height: none; }
  .sm-toolbar { flex-direction: column; align-items: stretch; }
  .sm-toolbar-right { flex-wrap: wrap; }
}
</style>
