<template>
  <div class="ai-dashboard">
    <el-row :gutter="16" class="stats-row">
      <el-col :span="6">
        <div class="stat-card">
          <div class="stat-icon tech"><el-icon><TrendCharts /></el-icon></div>
          <div class="stat-info">
            <div class="stat-value">{{ stats.totalAnalyzed }}</div>
            <div class="stat-label">已分析股票</div>
          </div>
        </div>
      </el-col>
      <el-col :span="6">
        <div class="stat-card">
          <div class="stat-icon good"><el-icon><StarFilled /></el-icon></div>
          <div class="stat-info">
            <div class="stat-value">{{ stats.goodCount }}</div>
            <div class="stat-label">优质标的</div>
          </div>
        </div>
      </el-col>
      <el-col :span="6">
        <div class="stat-card">
          <div class="stat-icon avg"><el-icon><DataLine /></el-icon></div>
          <div class="stat-info">
            <div class="stat-value">{{ stats.avgScore }}</div>
            <div class="stat-label">平均评分</div>
          </div>
        </div>
      </el-col>
      <el-col :span="6">
        <div class="stat-card">
          <div class="stat-icon api"><el-icon><Key /></el-icon></div>
          <div class="stat-info">
            <div class="stat-value">{{ stats.apiProviders }}</div>
            <div class="stat-label">API配置</div>
          </div>
        </div>
      </el-col>
    </el-row>

    <el-card shadow="never" class="section-card">
      <template #header>
        <div class="section-header">
          <span>分析模式选择</span>
        </div>
      </template>
      <div class="mode-cards">
        <div
          class="mode-card"
          :class="{ active: selectedMode === 'single' }"
          @click="navigateTo('/ai-analysis')"
        >
          <div class="mode-icon"><el-icon><MagicStick /></el-icon></div>
          <div class="mode-title">单股分析</div>
          <div class="mode-desc">深度分析单只股票的技术面、基本面、舆情等</div>
          <div class="mode-tags">
            <el-tag size="small" type="info">K线分析</el-tag>
            <el-tag size="small" type="info">财务评估</el-tag>
            <el-tag size="small" type="info">舆情追踪</el-tag>
          </div>
        </div>

        <div
          class="mode-card"
          :class="{ active: selectedMode === 'picker' }"
          @click="navigateTo('/ai-analysis')"
        >
          <div class="mode-icon"><el-icon><Search /></el-icon></div>
          <div class="mode-title">智能选股</div>
          <div class="mode-desc">基于策略因子筛选符合条件的优质股票</div>
          <div class="mode-tags">
            <el-tag size="small" type="info">策略选股</el-tag>
            <el-tag size="small" type="info">多因子</el-tag>
            <el-tag size="small" type="info">排序推荐</el-tag>
          </div>
        </div>

        <div
          class="mode-card"
          :class="{ active: selectedMode === 'batch' }"
          @click="navigateTo('/ai-analysis')"
        >
          <div class="mode-icon"><el-icon><Histogram /></el-icon></div>
          <div class="mode-title">批量分析</div>
          <div class="mode-desc">批量处理多只股票的AI分析任务</div>
          <div class="mode-tags">
            <el-tag size="small" type="info">并行处理</el-tag>
            <el-tag size="small" type="info">进度追踪</el-tag>
            <el-tag size="small" type="info">结果导出</el-tag>
          </div>
        </div>

        <div
          class="mode-card"
          :class="{ active: selectedMode === 'multiagent' }"
          @click="navigateTo('/multi-agent')"
        >
          <div class="mode-icon"><el-icon><Operation /></el-icon></div>
          <div class="mode-title">多Agent协作</div>
          <div class="mode-desc">多角色智能体协作分析，综合决策</div>
          <div class="mode-tags">
            <el-tag size="small" type="info">分析师</el-tag>
            <el-tag size="small" type="info">研究员</el-tag>
            <el-tag size="small" type="info">风控</el-tag>
          </div>
        </div>
      </div>
    </el-card>

    <el-row :gutter="16">
      <el-col :span="12">
        <el-card shadow="never" class="section-card">
          <template #header>
            <span>最近分析记录</span>
          </template>
          <el-table :data="recentRecords" stripe size="small">
            <el-table-column prop="code" label="代码" width="100">
              <template #default="{ row }">
                <router-link :to="`/stock-detail?code=${row.code}`" class="stock-link">
                  {{ row.code }}
                </router-link>
              </template>
            </el-table-column>
            <el-table-column prop="name" label="名称" width="100" show-overflow-tooltip />
            <el-table-column prop="score" label="评分" width="80">
              <template #default="{ row }">
                <el-tag :type="getScoreType(row.score)" size="small">
                  {{ row.score?.toFixed(1) }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="recommendation" label="建议" width="90">
              <template #default="{ row }">
                <el-tag :type="getRecommendType(row.recommendation)" size="small">
                  {{ row.recommendation }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="time" label="时间" />
          </el-table>
        </el-card>
      </el-col>

      <el-col :span="12">
        <el-card shadow="never" class="section-card">
          <template #header>
            <span>评分分布</span>
          </template>
          <div class="distribution-chart">
            <div
              v-for="item in distributionData"
              :key="item.label"
              class="distribution-item"
            >
              <div class="dist-label">{{ item.label }}</div>
              <div class="dist-bar-container">
                <div
                  class="dist-bar"
                  :style="{ width: item.percentage + '%', backgroundColor: item.color }"
                ></div>
              </div>
              <div class="dist-count">{{ item.count }}只</div>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-card shadow="never" class="section-card">
      <template #header>
        <span>AI分析流程说明</span>
      </template>
      <div class="flow-steps">
        <div class="flow-step">
          <div class="step-number">1</div>
          <div class="step-content">
            <div class="step-title">数据收集</div>
            <div class="step-desc">获取股票K线、财务数据、新闻舆情、资金流向等多维度数据</div>
          </div>
        </div>
        <div class="flow-arrow"><el-icon><DArrowRight /></el-icon></div>
        <div class="flow-step">
          <div class="step-number">2</div>
          <div class="step-content">
            <div class="step-title">多维分析</div>
            <div class="step-desc">技术面、基本面、舆情、资金流四维度独立分析评估</div>
          </div>
        </div>
        <div class="flow-arrow"><el-icon><DArrowRight /></el-icon></div>
        <div class="flow-step">
          <div class="step-number">3</div>
          <div class="step-content">
            <div class="step-title">LLM推理</div>
            <div class="step-desc">大语言模型整合分析结果，生成投资建议和风险评估</div>
          </div>
        </div>
        <div class="flow-arrow"><el-icon><DArrowRight /></el-icon></div>
        <div class="flow-step">
          <div class="step-number">4</div>
          <div class="step-content">
            <div class="step-title">综合决策</div>
            <div class="step-desc">加权计算综合评分，输出止损位、目标价等操作建议</div>
          </div>
        </div>
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import {
  TrendCharts,
  MagicStick,
  StarFilled,
  DataLine,
  Key,
  Search,
  Histogram,
  Operation,
  DArrowRight,
} from '@element-plus/icons-vue'
import { aiApi } from '@/api/ai'

const router = useRouter()

const selectedMode = ref('single')
const stats = ref({
  totalAnalyzed: 0,
  goodCount: 0,
  avgScore: '0.0',
  apiProviders: 0,
})

const recentRecords = ref([
  { code: 'SH600000', name: '浦发银行', score: 72, recommendation: '买入', time: '10分钟前' },
  { code: 'SH600519', name: '贵州茅台', score: 85, recommendation: '强烈推荐', time: '30分钟前' },
  { code: 'SZ000001', name: '平安银行', score: 65, recommendation: '观望', time: '1小时前' },
  { code: 'SH601318', name: '中国平安', score: 78, recommendation: '买入', time: '2小时前' },
])

const distributionData = computed(() => {
  const records = recentRecords.value
  const dist = [
    { label: '强烈推荐(≥75)', min: 75, max: 100, color: '#67c23a' },
    { label: '买入(65-75)', min: 65, max: 74.99, color: '#409eff' },
    { label: '观望(55-65)', min: 55, max: 64.99, color: '#e6a23c' },
    { label: '回避(<55)', min: 0, max: 54.99, color: '#f56c6c' },
  ]
  return dist.map(d => {
    const count = records.filter(r => r.score >= d.min && r.score <= d.max).length
    const percentage = records.length > 0 ? (count / records.length) * 100 : 0
    return { ...d, count, percentage }
  })
})

function getScoreType(score: number): string {
  if (score >= 75) return 'success'
  if (score >= 60) return 'warning'
  if (score >= 50) return 'info'
  return 'danger'
}

function getRecommendType(rec: string): string {
  if (rec.includes('推荐') || rec.includes('买入')) return 'success'
  if (rec.includes('谨慎') || rec.includes('观望')) return 'warning'
  if (rec.includes('回避')) return 'danger'
  return 'info'
}

function navigateTo(path: string) {
  router.push(path)
}

async function loadStats() {
  try {
    const res = await aiKeyApi.list()
    const keys = res.data?.data || res.data || []
    stats.value.apiProviders = keys.length
  } catch {
    stats.value.apiProviders = 0
  }

  stats.value.totalAnalyzed = recentRecords.value.length
  stats.value.goodCount = recentRecords.value.filter(r => r.score >= 75).length
  const avg = recentRecords.value.reduce((acc, r) => acc + r.score, 0) / recentRecords.value.length
  stats.value.avgScore = avg.toFixed(1)
}

onMounted(() => {
  loadStats()
})
</script>

<script lang="ts">
import { aiKeyApi } from '@/api/ai'
export { aiKeyApi }
</script>

<style scoped>
.ai-dashboard {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.stats-row {
  margin-bottom: 0;
}

.stat-card {
  background: #1f1f1f;
  border: 1px solid #2c2c2c;
  border-radius: 8px;
  padding: 20px;
  display: flex;
  align-items: center;
  gap: 16px;
}

.stat-icon {
  width: 48px;
  height: 48px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 24px;
}

.stat-icon.tech {
  background: rgba(64, 158, 255, 0.15);
  color: #409eff;
}

.stat-icon.good {
  background: rgba(103, 194, 58, 0.15);
  color: #67c23a;
}

.stat-icon.avg {
  background: rgba(230, 162, 60, 0.15);
  color: #e6a23c;
}

.stat-icon.api {
  background: rgba(138, 113, 213, 0.15);
  color: #8a71d5;
}

.stat-info {
  flex: 1;
}

.stat-value {
  font-size: 28px;
  font-weight: 700;
  color: #e5eaf3;
}

.stat-label {
  font-size: 13px;
  color: #909399;
  margin-top: 4px;
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

.mode-cards {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
}

.mode-card {
  background: #2c2c2c;
  border: 2px solid #2c2c2c;
  border-radius: 12px;
  padding: 24px 16px;
  cursor: pointer;
  transition: all 0.3s;
  text-align: center;
}

.mode-card:hover {
  border-color: #409eff;
  transform: translateY(-4px);
}

.mode-card.active {
  border-color: #409eff;
  background: rgba(64, 158, 255, 0.08);
}

.mode-icon {
  width: 56px;
  height: 56px;
  border-radius: 50%;
  background: rgba(64, 158, 255, 0.15);
  color: #409eff;
  font-size: 28px;
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0 auto 16px;
}

.mode-title {
  font-size: 16px;
  font-weight: 600;
  color: #e5eaf3;
  margin-bottom: 8px;
}

.mode-desc {
  font-size: 12px;
  color: #909399;
  line-height: 1.5;
  margin-bottom: 12px;
}

.mode-tags {
  display: flex;
  justify-content: center;
  gap: 6px;
  flex-wrap: wrap;
}

.stock-link {
  color: #409eff;
  text-decoration: none;
}

.stock-link:hover {
  text-decoration: underline;
}

.distribution-chart {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.distribution-item {
  display: grid;
  grid-template-columns: 120px 1fr 60px;
  align-items: center;
  gap: 12px;
}

.dist-label {
  font-size: 12px;
  color: #909399;
}

.dist-bar-container {
  height: 10px;
  background: #2c2c2c;
  border-radius: 5px;
  overflow: hidden;
}

.dist-bar {
  height: 100%;
  border-radius: 5px;
  transition: width 0.3s ease;
}

.dist-count {
  font-size: 12px;
  color: #e5eaf3;
  text-align: right;
}

.flow-steps {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 20px 0;
}

.flow-step {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding: 16px 24px;
  background: #2c2c2c;
  border-radius: 8px;
  text-align: center;
}

.step-number {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: #409eff;
  color: #fff;
  font-size: 16px;
  font-weight: 600;
  display: flex;
  align-items: center;
  justify-content: center;
}

.step-title {
  font-size: 14px;
  font-weight: 600;
  color: #e5eaf3;
}

.step-desc {
  font-size: 12px;
  color: #909399;
  max-width: 120px;
}

.flow-arrow {
  color: #409eff;
  font-size: 20px;
}
</style>