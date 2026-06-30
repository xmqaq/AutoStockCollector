<template>
  <div class="research-reports">
    <!-- 搜索栏 -->
    <el-card shadow="never" class="search-card">
      <el-form :model="query" inline>
        <el-form-item label="关键字">
          <el-input v-model="query.keyword" placeholder="标题/股票名" clearable @keyup.enter="search" />
        </el-form-item>
        <el-form-item label="股票代码">
          <el-input v-model="query.code" placeholder="如 600519" clearable @keyup.enter="search" style="width: 120px" />
        </el-form-item>
        <el-form-item label="机构">
          <el-select v-model="query.org" placeholder="选择机构" clearable filterable style="width: 150px">
            <el-option v-for="o in orgs" :key="o.org" :label="`${o.org} (${o.count})`" :value="o.org" />
          </el-select>
        </el-form-item>
        <el-form-item label="行业">
          <el-select v-model="query.industry" placeholder="选择行业" clearable filterable style="width: 150px">
            <el-option v-for="ind in industries" :key="ind.industry" :label="`${ind.industry} (${ind.count})`" :value="ind.industry" />
          </el-select>
        </el-form-item>
        <el-form-item label="评级">
          <el-select v-model="query.ratings" multiple placeholder="全部" collapse-tags style="width: 160px">
            <el-option v-for="r in RATING_OPTIONS" :key="r.value" :label="r.label" :value="r.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="作者">
          <el-input v-model="query.author" placeholder="分析师名" clearable @keyup.enter="search" style="width: 120px" />
        </el-form-item>
        <el-form-item label="时间">
          <el-select v-model="query.days" style="width: 100px">
            <el-option label="7天" :value="7" />
            <el-option label="30天" :value="30" />
            <el-option label="90天" :value="90" />
            <el-option label="180天" :value="180" />
            <el-option label="365天" :value="365" />
          </el-select>
        </el-form-item>
        <el-form-item label="排序">
          <el-select v-model="query.sort_by" style="width: 100px">
            <el-option label="日期" value="date" />
            <el-option label="目标价" value="target_price_high" />
          </el-select>
          <el-select v-model="query.sort_order" style="width: 80px; margin-left: 4px;">
            <el-option label="降序" value="desc" />
            <el-option label="升序" value="asc" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="search">查询</el-button>
          <el-button @click="reset">重置</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 视图切换 + 统计 -->
    <el-card shadow="never" class="stats-card">
      <div class="stats-row">
        <div class="stats-tabs">
          <span :class="{ active: viewMode === 'list' }" @click="switchView('list')">研报列表</span>
          <span :class="{ active: viewMode === 'signals' }" @click="switchView('signals')">评级变动</span>
        </div>
        <div class="stats-info">
          <span class="stat-item" v-if="stats">共 <b>{{ stats.total }}</b> 条</span>
          <span class="stat-item" v-if="stats">本周 <b>{{ stats.weekly }}</b></span>
          <span class="stat-item" v-if="stats">已摘要 <b>{{ stats.summarized }}</b></span>
        </div>
      </div>
    </el-card>

    <!-- 评级变动视图 -->
    <el-card v-show="viewMode === 'signals'" shadow="never" class="list-card" v-loading="signalsLoading">
      <el-empty v-if="!signalsLoading && signals.length === 0" description="暂无评级变动" />
      <div v-else class="signal-list">
          <div v-for="s in signals" :key="s.report_id" class="signal-item">
            <div class="signal-header">
              <span class="signal-stock" @click="goToStock(s.code)">{{ s.code }} {{ s.name }}</span>
              <el-tag :type="s.direction === 'upgrade' ? 'success' : 'danger'" size="small">
                {{ s.direction === 'upgrade' ? '上调' : '下调' }}
              </el-tag>
              <span class="signal-ratings">
                <span class="rating-old">{{ s.from_rating }}</span>
                <el-icon><ArrowRightBold /></el-icon>
                <span class="rating-new">{{ s.to_rating }}</span>
              </span>
            </div>
            <div class="signal-meta">
              <span class="signal-org">{{ s.org }}</span>
              <span class="signal-date">{{ s.date }}</span>
            </div>
            <div class="signal-title">{{ s.title }}</div>
          </div>
        </div>
      </el-card>

    <!-- 研报列表视图 -->
    <el-card v-show="viewMode === 'list'" shadow="never" class="list-card" v-loading="loading">
        <template v-if="!loading && list.length === 0">
          <el-empty description="暂无数据" />
        </template>
        <div v-else class="report-list">
        <div v-for="r in list" :key="r.report_id" class="report-item" @click="showDetail(r)">
          <div class="report-header">
            <span class="report-title">{{ r.title }}</span>
            <el-tag v-if="r.rating" size="small" :type="ratingType(r.rating)">{{ r.rating }}</el-tag>
          </div>
          <div class="report-meta">
            <span class="report-stock" @click.stop="goToStock(r.code)">{{ r.code }} {{ r.name }}</span>
            <span class="report-org">{{ r.org }}</span>
            <span class="report-date">{{ r.date }}</span>
            <span v-if="r.industry" class="report-industry">{{ r.industry }}</span>
            <span v-if="r.target_price_high" class="report-target">
              目标价: {{ r.target_price_low || '--' }} ~ {{ r.target_price_high }}
            </span>
            <el-link v-if="r.pdf_url" type="primary" :href="proxyPdfUrl(r.pdf_url!)" target="_blank" class="report-pdf-link" @click.stop>
              查看原文
            </el-link>
          </div>
          <div v-if="r.abstract" class="report-abstract">{{ r.abstract }}</div>
        </div>
      </div>

      <!-- 分页 -->
      <div v-if="totalPages > 1" class="pagination">
        <el-pagination
          v-model:current-page="page"
          :page-size="query.page_size || 50"
          :total="total"
          layout="prev, pager, next"
          @current-change="onPageChange"
        />
      </div>
    </el-card>

    <!-- 详情抽屉 -->
    <el-drawer v-model="drawerVisible" :title="selected?.title || '研报详情'" size="80%">
      <template v-if="selected">
        <div class="detail-section">
          <el-descriptions :column="2" border size="small">
            <el-descriptions-item label="股票">{{ selected.code }} {{ selected.name }}</el-descriptions-item>
            <el-descriptions-item label="机构">{{ selected.org }}</el-descriptions-item>
            <el-descriptions-item label="日期">{{ selected.date }}</el-descriptions-item>
            <el-descriptions-item label="行业">{{ selected.industry || '--' }}</el-descriptions-item>
            <el-descriptions-item label="评级">
              <el-tag :type="ratingType(selected.rating)" size="small">{{ selected.rating }}</el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="目标价">
              <span v-if="selected.target_price_high">{{ selected.target_price_low || '--' }} ~ {{ selected.target_price_high }}</span>
              <span v-else>--</span>
            </el-descriptions-item>
          </el-descriptions>
        </div>
        <div class="detail-section">
          <h4>AI 智能分析</h4>
          <div v-if="summaryText" class="summary-content">
            <div class="summary-text" v-html="renderedSummary"></div>
          </div>
          <div v-else-if="summaryLoading" class="summary-loading">
            <el-icon class="is-loading"><Loading /></el-icon>
            <p class="text-muted">正在调用 AI 生成摘要，约 10-20 秒…</p>
          </div>
          <div v-else-if="summaryError" class="summary-error">
            <p>{{ summaryError }}</p>
            <el-button size="small" type="primary" plain @click="requestSummary(selected!)">重试</el-button>
          </div>
          <div v-else>
            <p class="text-muted">暂无 AI 摘要</p>
          </div>
        </div>
        <div v-if="selected.abstract && selected.abstract !== selected.title" class="detail-section">
          <h4>摘要</h4>
          <p>{{ selected.abstract }}</p>
        </div>
        <div v-if="selected.pdf_url" class="detail-section">
          <h4>原文</h4>
          <div class="pdf-container">
            <iframe :src="proxyPdfUrl(selected.pdf_url!)" class="pdf-viewer" frameborder="0"></iframe>
          </div>
        </div>
      </template>
    </el-drawer>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { researchReportsApi, RATING_OPTIONS, type ResearchReport } from '@/api/researchReports'
import { renderMd } from '@/utils/markdown'
import { ArrowRightBold, Loading } from '@element-plus/icons-vue'

const router = useRouter()
const loading = ref(false)
const list = ref<ResearchReport[]>([])
const total = ref(0)
const page = ref(1)
const orgs = ref<{ org: string; count: number }[]>([])
const industries = ref<{ industry: string; count: number }[]>([])
const viewMode = ref<'list' | 'signals'>('list')
const signals = ref<any[]>([])
const signalsLoading = ref(false)
const stats = ref<{ total: number; weekly: number; summarized: number } | null>(null)

const query = reactive({
  keyword: '',
  code: '',
  org: '',
  industry: '',
  ratings: [] as string[],
  author: '',
  days: 90,
  sort_by: 'date',
  sort_order: 'desc',
  page_size: 50,
})

const totalPages = computed(() => Math.ceil(total.value / (query.page_size || 50)))

const drawerVisible = ref(false)
const selected = ref<ResearchReport | null>(null)
const summaryText = ref('')
const summaryLoading = ref(false)
const summaryError = ref('')

const renderedSummary = computed(() => renderMd(summaryText.value))

function ratingType(rating: string): string {
  const r = rating || ''
  if (r.includes('买入') || r.includes('增持') || r.includes('推荐')) return 'success'
  if (r.includes('中性') || r.includes('持有')) return 'warning'
  if (r.includes('卖出') || r.includes('减持')) return 'danger'
  return 'info'
}

async function search() {
  page.value = 1
  await loadData()
}

async function reset() {
  query.keyword = ''
  query.code = ''
  query.org = ''
  query.industry = ''
  query.ratings = []
  query.author = ''
  query.days = 90
  query.sort_by = 'date'
  query.sort_order = 'desc'
  page.value = 1
  await loadData()
}

async function loadData() {
  loading.value = true
  try {
    const params: any = { ...query, page: page.value }
    if (params.ratings && params.ratings.length > 0) {
      params.ratings = params.ratings.join(',')
    } else {
      delete params.ratings
    }
    const res = await researchReportsApi.search(params)
    list.value = res.data?.data || []
    total.value = res.data?.total || 0
  } finally {
    loading.value = false
  }
}

async function loadOrgs() {
  try {
    const res = await researchReportsApi.getOrgs()
    orgs.value = res.data?.data || []
  } catch { /* ignore */ }
}

async function loadIndustries() {
  try {
    const res = await researchReportsApi.getIndustries()
    industries.value = res.data?.data || []
  } catch { /* ignore */ }
}

async function loadSignals() {
  signalsLoading.value = true
  try {
    const res = await researchReportsApi.getRatingSignals({ days: 30, limit: 100 })
    signals.value = res.data?.data || []
  } catch { /* ignore */ }
  finally { signalsLoading.value = false }
}

function switchView(mode: 'list' | 'signals') {
  viewMode.value = mode
  if (mode === 'signals' && signals.value.length === 0) {
    loadSignals()
  }
}

async function loadStats() {
  try {
    const res = await researchReportsApi.getStats()
    stats.value = res.data?.data || null
  } catch { /* ignore */ }
}

function onPageChange(p: number) {
  page.value = p
  loadData()
}

function goToStock(code: string) {
  router.push({ path: '/stock-detail', query: { code } })
}

function showDetail(r: ResearchReport) {
  selected.value = r
  summaryText.value = r.generated_abstract || ''
  summaryError.value = ''
  // 已有摘要直接展示；否则打开抽屉后异步生成
  if (!summaryText.value && r.report_id) {
    requestSummary(r)
  }
  drawerVisible.value = true
}

async function requestSummary(r: ResearchReport) {
  if (!r.report_id) return
  summaryLoading.value = true
  summaryError.value = ''
  summaryText.value = ''
  try {
    const res = await researchReportsApi.summarize(r.report_id)
    const abstract = res.data?.data?.abstract || ''
    if (abstract) {
      summaryText.value = abstract
      // 回写本地缓存，避免重复请求 + 同列表内其它条目复用
      r.generated_abstract = abstract
      const item = list.value.find(x => x.report_id === r.report_id)
      if (item) item.generated_abstract = abstract
    } else {
      summaryError.value = '摘要生成失败，请稍后重试'
    }
  } catch (e: any) {
    summaryError.value = e?.response?.data?.error || '摘要生成失败，请稍后重试'
  } finally {
    summaryLoading.value = false
  }
}

function proxyPdfUrl(url: string): string {
  return `/api/v1/research-reports/pdf?url=${encodeURIComponent(url)}`
}

onMounted(() => {
  loadData()
  loadOrgs()
  loadIndustries()
  loadStats()
})
</script>

<style scoped>
.research-reports { display: flex; flex-direction: column; gap: 12px; }
.search-card { background: var(--bg-card); border: 1px solid var(--border-color); }
.search-card :deep(.el-card__body) { padding: 12px 16px; }
.search-card :deep(.el-form-item) { margin-bottom: 0; }
.stats-card { background: var(--bg-card); border: 1px solid var(--border-color); }
.stats-card :deep(.el-card__body) { padding: 8px 16px; }
.stats-row { display: flex; justify-content: space-between; align-items: center; font-size: 13px; }
.list-card { background: var(--bg-card); border: 1px solid var(--border-color); }
.report-list { display: flex; flex-direction: column; gap: 1px; }
.report-item { padding: 10px 12px; cursor: pointer; border-bottom: 1px solid var(--border-color); transition: background 0.15s; }
.report-item:hover { background: var(--el-fill-color-light); }
.report-item:last-child { border-bottom: none; }
.report-header { display: flex; align-items: center; gap: 8px; margin-bottom: 4px; }
.report-title { font-size: 14px; font-weight: 500; color: var(--text-primary); flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.report-meta { display: flex; gap: 16px; font-size: 12px; color: var(--text-secondary); }
.report-stock { color: var(--el-color-primary); cursor: pointer; }
.report-stock:hover { color: #79bbff; }
.report-abstract { margin-top: 4px; font-size: 12px; color: var(--text-faint); display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
.pagination { display: flex; justify-content: center; padding: 16px; }
.text-muted { color: var(--text-faint); }
.detail-section { margin-bottom: 16px; }
.detail-section h4 { font-size: 14px; margin-bottom: 8px; }
.detail-section p { font-size: 13px; line-height: 1.6; color: var(--text-secondary); white-space: pre-wrap; }
.pdf-container { width: 100%; height: 70vh; border: 1px solid var(--border-color); border-radius: 4px; overflow: hidden; }
.pdf-viewer { width: 100%; height: 100%; }
.report-pdf-link { margin-left: auto; font-size: 12px; }
.summary-loading { padding: 16px 0; }
.summary-loading .text-muted { margin-top: 8px; font-size: 12px; text-align: center; }
.summary-error { padding: 16px; text-align: center; color: var(--el-color-danger); }
.summary-content { background: var(--el-fill-color-light); border-radius: 6px; padding: 12px 16px; }
.summary-text { font-size: 13px; line-height: 1.7; color: var(--text-primary); }
.summary-text h2 { font-size: 14px; margin: 12px 0 6px; color: var(--el-color-primary); }
.summary-text h2:first-child { margin-top: 0; }
.summary-text h3, .summary-text h4 { font-size: 13px; margin: 8px 0 4px; }
.summary-text ul, .summary-text ol { padding-left: 20px; margin: 4px 0; }
.summary-text li { margin-bottom: 2px; }
.summary-text p { margin: 4px 0; }
.stats-tabs { display: flex; gap: 0; }
.stats-tabs span { padding: 4px 16px; cursor: pointer; border-radius: 4px; font-size: 13px; }
.stats-tabs span.active { background: var(--el-color-primary-light-8); color: var(--el-color-primary); font-weight: 500; }
.stats-tabs span:hover { background: var(--el-fill-color-light); }
.signal-list { display: flex; flex-direction: column; gap: 1px; }
.signal-item { padding: 10px 12px; border-bottom: 1px solid var(--border-color); }
.signal-item:last-child { border-bottom: none; }
.signal-header { display: flex; align-items: center; gap: 8px; margin-bottom: 4px; }
.signal-stock { color: var(--el-color-primary); cursor: pointer; font-weight: 500; font-size: 13px; }
.signal-stock:hover { color: #79bbff; }
.signal-ratings { display: flex; align-items: center; gap: 4px; font-size: 13px; }
.signal-ratings .el-icon { font-size: 12px; }
.rating-old { color: var(--text-faint); text-decoration: line-through; }
.rating-new { color: var(--el-color-danger); font-weight: 500; }
.signal-item .el-tag--success + .signal-ratings .rating-new { color: var(--el-color-success); }
.signal-meta { display: flex; gap: 16px; font-size: 12px; color: var(--text-secondary); margin-bottom: 2px; }
.signal-title { font-size: 12px; color: var(--text-faint); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.stats-info { display: flex; gap: 16px; }
.stat-item { font-size: 12px; color: var(--text-secondary); }
</style>
