<template>
  <div class="memory-settings-panel">
    <el-card shadow="never" class="section-card">
      <template #header>
        <div class="section-header">
          <span>用户画像</span>
          <el-button size="small" type="primary" @click="saveProfile" :loading="savingProfile">保存</el-button>
        </div>
      </template>
      <div class="profile-form">
        <el-form label-position="top" size="small">
          <el-form-item label="风险偏好">
            <el-radio-group v-model="profile.risk_level">
              <el-radio value="conservative">保守</el-radio>
              <el-radio value="balanced">均衡</el-radio>
              <el-radio value="aggressive">激进</el-radio>
            </el-radio-group>
          </el-form-item>
          <el-form-item label="持仓周期">
            <el-radio-group v-model="profile.holding_horizon">
              <el-radio value="short">短期 (1-30天)</el-radio>
              <el-radio value="medium">中期 (1-6月)</el-radio>
              <el-radio value="long">长期 (6月+)</el-radio>
            </el-radio-group>
          </el-form-item>
          <el-form-item label="偏好行业">
            <el-select v-model="profile.preferred_industries" multiple filterable placeholder="选择关注的行业" style="width: 100%">
              <el-option v-for="ind in industries" :key="ind" :label="ind" :value="ind" />
            </el-select>
          </el-form-item>
          <el-form-item label="偏好的投资策略">
            <el-select v-model="profile.preferred_strategies" multiple filterable placeholder="选择策略类型" style="width: 100%">
              <el-option v-for="s in strategies" :key="s" :label="s" :value="s" />
            </el-select>
          </el-form-item>
        </el-form>
      </div>
    </el-card>

    <el-card shadow="never" class="section-card">
      <template #header>
        <div class="section-header">
          <span>记忆统计数据</span>
          <el-button size="small" @click="refreshStats" :loading="loadingStats">刷新</el-button>
        </div>
      </template>
      <div v-if="stats" class="stats-grid">
        <div class="stat-card">
          <div class="stat-value">{{ stats.analysis_count }}</div>
          <div class="stat-label">分析记录</div>
        </div>
        <div class="stat-card">
          <div class="stat-value">{{ stats.pattern_count }}</div>
          <div class="stat-label">投资模式</div>
        </div>
        <div class="stat-card">
          <div class="stat-value">{{ stats.holding_count }}</div>
          <div class="stat-label">持仓记录</div>
        </div>
      </div>
      <div v-if="stats?.memory_rings" class="rings-list">
        <div v-for="ring in stats.memory_rings" :key="ring.name" class="ring-item">
          <span class="ring-label">{{ ring.label }}</span>
          <span class="ring-count">{{ ring.item_count }} 项</span>
        </div>
      </div>
    </el-card>

    <el-card shadow="never" class="section-card">
      <template #header>
        <div class="section-header">
          <span>持仓记忆</span>
          <el-button size="small" @click="refreshHoldings" :loading="loadingHoldings">刷新</el-button>
        </div>
      </template>
      <el-table v-if="holdings.length" :data="holdings" stripe size="small">
        <el-table-column prop="code" label="代码" width="90" />
        <el-table-column prop="stock_name" label="名称" width="120" />
        <el-table-column prop="buy_date" label="买入日期" width="110" />
        <el-table-column prop="buy_price" label="买入价" width="90">
          <template #default="{ row }">{{ row.buy_price?.toFixed(2) }}</template>
        </el-table-column>
        <el-table-column prop="shares" label="持仓量" width="90" />
        <el-table-column prop="reason" label="买入理由" min-width="150" />
      </el-table>
      <el-empty v-else description="暂无持仓记录" :image-size="60" />
    </el-card>

    <el-card shadow="never" class="section-card">
      <template #header>
        <div class="section-header">
          <span>投资模式发现</span>
          <el-button size="small" @click="runPatternAnalysis" :loading="analyzingPatterns">
            {{ patterns.length ? '重新分析' : '开始分析' }}
          </el-button>
        </div>
      </template>
      <div v-if="patterns.length" class="patterns-list">
        <div v-for="p in patterns" :key="p.id" class="pattern-card">
          <div class="pattern-header">
            <span class="pattern-type">{{ p.pattern_type }}</span>
            <el-tag size="small" :type="p.confidence > 0.7 ? 'success' : 'warning'">
              {{ (p.confidence * 100).toFixed(0) }}% 置信
            </el-tag>
          </div>
          <div class="pattern-desc">{{ p.description }}</div>
          <div class="pattern-meta">出现 {{ p.frequency }} 次</div>
        </div>
      </div>
      <el-empty v-else description="点击「开始分析」发现您的投资模式" :image-size="60" />
    </el-card>

    <el-card shadow="never" class="section-card">
      <template #header>
        <div class="section-header">
          <span>会话管理</span>
        </div>
      </template>
      <div class="session-actions">
        <el-button type="danger" plain @click="clearSession" :loading="clearing">
          清除当前会话
        </el-button>
        <span class="session-hint">将清空工作记忆中的临时上下文，不影响持久化存储</span>
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { memoryApi, type UserProfile, type HoldingRecord, type InvestmentPattern, type MemoryStats } from '@/api/memory'

const savingProfile = ref(false)
const loadingStats = ref(false)
const loadingHoldings = ref(false)
const analyzingPatterns = ref(false)
const clearing = ref(false)

const profile = reactive<UserProfile>({
  user_id: 'default',
  risk_level: 'balanced',
  preferred_industries: [],
  preferred_strategies: [],
  holding_horizon: 'medium',
})

const stats = ref<MemoryStats | null>(null)
const holdings = ref<HoldingRecord[]>([])
const patterns = ref<InvestmentPattern[]>([])

const industries = [
  '银行', '证券', '保险', '房地产', '汽车', '新能源', '半导体', '消费电子',
  '医药生物', '食品饮料', '白酒', '家电', '机械设备', '化工', '有色金属',
  '钢铁', '煤炭', '电力', '军工', '通信', '计算机', '传媒', '交通运输',
  '建筑装饰', '农林牧渔', '纺织服装', '轻工制造', '商业贸易', '休闲服务',
]

const strategies = [
  '价值投资', '成长投资', '趋势跟踪', '动量交易', '宏观经济',
  '量化交易', '事件驱动', '波段操作', '定投策略', '对冲策略',
]

async function loadProfile() {
  try {
    const res = await memoryApi.getProfile()
    if (res.data?.success && res.data.data) {
      const p = res.data.data
      Object.assign(profile, p)
    }
  } catch {
    // use defaults
  }
}

async function saveProfile() {
  savingProfile.value = true
  try {
    await memoryApi.updateProfile({ ...profile })
    ElMessage.success('用户画像已保存')
  } catch {
    ElMessage.error('保存失败')
  } finally {
    savingProfile.value = false
  }
}

async function refreshStats() {
  loadingStats.value = true
  try {
    const res = await memoryApi.getStats()
    if (res.data?.success) {
      stats.value = res.data.data
    }
  } catch {
    // ignore
  } finally {
    loadingStats.value = false
  }
}

async function refreshHoldings() {
  loadingHoldings.value = true
  try {
    const res = await memoryApi.getHoldings()
    if (res.data?.success) {
      holdings.value = res.data.holdings || []
    }
  } catch {
    // ignore
  } finally {
    loadingHoldings.value = false
  }
}

async function runPatternAnalysis() {
  analyzingPatterns.value = true
  try {
    const res = await memoryApi.analyzePatterns()
    if (res.data?.success) {
      patterns.value = res.data.data || []
      ElMessage.success(res.data.message || '分析完成')
    }
  } catch {
    ElMessage.error('模式分析失败')
  } finally {
    analyzingPatterns.value = false
  }
}

async function clearSession() {
  try {
    await ElMessageBox.confirm('确认清除当前会话？所有工作记忆中的临时上下文将被清空。', '确认', {
      confirmButtonText: '确认',
      cancelButtonText: '取消',
      type: 'warning',
    })
    clearing.value = true
    await memoryApi.clearSession()
    ElMessage.success('会话已清除')
  } catch {
    // cancelled
  } finally {
    clearing.value = false
  }
}

onMounted(() => {
  loadProfile()
  refreshStats()
  refreshHoldings()
})
</script>

<style scoped>
.memory-settings-panel {
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
.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.profile-form {
  max-width: 600px;
}
.profile-form :deep(.el-form-item__label) {
  color: #909399;
  font-size: 12px;
  padding-bottom: 4px;
}
.stats-grid {
  display: flex;
  gap: 24px;
}
.stat-card {
  text-align: center;
  padding: 12px 24px;
  background: #2c2c2c;
  border-radius: 8px;
  min-width: 100px;
}
.stat-value {
  font-size: 28px;
  font-weight: 700;
  color: #409eff;
}
.stat-label {
  font-size: 12px;
  color: #909399;
  margin-top: 4px;
}
.rings-list {
  display: flex;
  gap: 16px;
  margin-top: 12px;
}
.ring-item {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 8px 16px;
  background: #2c2c2c;
  border-radius: 6px;
}
.ring-label {
  font-size: 12px;
  color: #e5eaf3;
  font-weight: 600;
}
.ring-count {
  font-size: 11px;
  color: #909399;
}
.patterns-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.pattern-card {
  background: #2c2c2c;
  border-radius: 6px;
  padding: 12px;
}
.pattern-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 4px;
}
.pattern-type {
  font-size: 13px;
  font-weight: 600;
  color: #e5eaf3;
}
.pattern-desc {
  font-size: 12px;
  color: #c0c4cc;
  line-height: 1.5;
}
.pattern-meta {
  font-size: 11px;
  color: #606266;
  margin-top: 4px;
}
.session-actions {
  display: flex;
  align-items: center;
  gap: 16px;
}
.session-hint {
  font-size: 12px;
  color: #606266;
}
</style>
