<template>
  <div class="signal-feed">
    <el-card shadow="never" class="section-card">
      <template #header>
        <div class="feed-header">
          <span>Agent 信号源</span>
          <div class="feed-actions">
            <el-select v-model="filterType" placeholder="类型" size="small" clearable style="width:100px">
              <el-option label="全部" value="" />
              <el-option label="交易想法" value="trade_idea" />
              <el-option label="分析" value="analysis" />
              <el-option label="预警" value="alert" />
              <el-option label="风险" value="risk" />
            </el-select>
            <el-select v-model="filterDirection" placeholder="方向" size="small" clearable style="width:100px">
              <el-option label="全部" value="" />
              <el-option label="看多" value="bullish" />
              <el-option label="看空" value="bearish" />
              <el-option label="中性" value="neutral" />
            </el-select>
            <el-button size="small" type="primary" @click="loadFeed" :loading="loading">刷新</el-button>
            <el-button size="small" type="success" @click="showPublish = true" :icon="Plus">发布</el-button>
          </div>
        </div>
      </template>
      <div v-if="loading" style="text-align:center;padding:40px">
        <el-icon class="is-loading" :size="24"><Loading /></el-icon>
      </div>
      <div v-else-if="signals.length === 0" style="text-align:center;padding:40px;color:#909399">
        暂无信号
      </div>
      <div v-else class="signal-list">
        <div v-for="s in signals" :key="s.signal_id" :class="['signal-item', s.direction]">
          <div class="signal-meta" @click="showDetail(s)" style="cursor:pointer">
            <el-tag size="small" :type="directionType(s.direction)" class="direction-tag">
              {{ directionLabel(s.direction) }}
            </el-tag>
            <span class="signal-publisher">{{ s.publisher_name || s.publisher_id }}</span>
            <el-tag size="small" type="info" class="type-tag">{{ s.type }}</el-tag>
            <span class="signal-target">{{ s.target.code }}{{ s.target.name ? ' ' + s.target.name : '' }}</span>
          </div>
          <div v-if="s.price" class="signal-price">@ {{ s.price }}</div>
          <div class="signal-reasoning" @click="showDetail(s)">{{ s.reasoning || '无详细说明' }}</div>
          <div class="signal-footer">
            <span class="signal-confidence">置信度: {{ s.confidence }}%</span>
            <span class="signal-time">{{ formatTime(s.timestamp) }}</span>
            <el-tag v-if="s.status === 'expired'" size="small" type="danger">已过期</el-tag>
            <el-button v-if="s.status === 'active'" size="small" text type="warning" @click="handleExpire(s)">过期</el-button>
          </div>
        </div>
      </div>
    </el-card>

    <el-dialog v-model="showPublish" title="发布信号" width="520px">
      <el-form :model="publishForm" label-width="80px" size="small">
        <el-form-item label="发布者ID">
          <el-input v-model="publishForm.publisher_id" />
        </el-form-item>
        <el-form-item label="发布者名称">
          <el-input v-model="publishForm.publisher_name" />
        </el-form-item>
        <el-form-item label="类型">
          <el-select v-model="publishForm.type">
            <el-option label="交易想法" value="trade_idea" />
            <el-option label="分析" value="analysis" />
            <el-option label="预警" value="alert" />
            <el-option label="风险" value="risk" />
          </el-select>
        </el-form-item>
        <el-form-item label="方向">
          <el-select v-model="publishForm.direction">
            <el-option label="看多" value="bullish" />
            <el-option label="看空" value="bearish" />
            <el-option label="中性" value="neutral" />
          </el-select>
        </el-form-item>
        <el-form-item label="股票代码">
          <el-input v-model="publishForm.target_code" placeholder="000001" />
        </el-form-item>
        <el-form-item label="股票名称">
          <el-input v-model="publishForm.target_name" />
        </el-form-item>
        <el-form-item label="价格">
          <el-input-number v-model="publishForm.price" :min="0" :step="0.01" />
        </el-form-item>
        <el-form-item label="置信度">
          <el-slider v-model="publishForm.confidence" :min="0" :max="100" />
        </el-form-item>
        <el-form-item label="理由">
          <el-input v-model="publishForm.reasoning" type="textarea" :rows="3" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showPublish = false">取消</el-button>
        <el-button type="primary" @click="handlePublish" :loading="publishing">发布</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="showDetailDialog" title="信号详情" width="520px">
      <template v-if="detailSignal">
        <div class="detail-section">
          <el-tag :type="directionType(detailSignal.direction)" size="large">
            {{ directionLabel(detailSignal.direction) }}
          </el-tag>
          <el-tag type="info" style="margin-left:8px">{{ detailSignal.type }}</el-tag>
        </div>
        <div class="detail-section">
          <label>发布者</label>
          <span>{{ detailSignal.publisher_name || detailSignal.publisher_id }}</span>
        </div>
        <div class="detail-section">
          <label>标的</label>
          <span>{{ detailSignal.target.code }} {{ detailSignal.target.name }}</span>
        </div>
        <div class="detail-section">
          <label>价格</label>
          <span>{{ detailSignal.price ?? '--' }}</span>
        </div>
        <div class="detail-section">
          <label>置信度</label>
          <el-progress :percentage="detailSignal.confidence" :stroke-width="12" style="width:200px" />
        </div>
        <div class="detail-section">
          <label>理由</label>
          <p class="detail-reasoning">{{ detailSignal.reasoning || '无' }}</p>
        </div>
        <div class="detail-section">
          <label>时间</label>
          <span>{{ detailSignal.timestamp }}</span>
        </div>
        <div class="detail-section">
          <label>状态</label>
          <el-tag :type="detailSignal.status === 'active' ? 'success' : 'danger'">{{ detailSignal.status }}</el-tag>
        </div>
      </template>
      <template #footer>
        <el-button @click="showDetailDialog = false">关闭</el-button>
        <el-button v-if="detailSignal?.status === 'active'" type="warning" @click="handleExpire(detailSignal)">标记过期</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, watch } from 'vue'
import { signalApi, type Signal } from '@/api/signals'
import { Loading, Plus } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'

const signals = ref<Signal[]>([])
const loading = ref(false)
const filterType = ref('')
const filterDirection = ref('')

// Publish
const showPublish = ref(false)
const publishing = ref(false)
const publishForm = reactive({
  publisher_id: 'manual',
  publisher_name: '手动测试',
  type: 'analysis',
  direction: 'bullish',
  target_code: '',
  target_name: '',
  price: 0,
  confidence: 50,
  reasoning: '',
})

// Detail
const showDetailDialog = ref(false)
const detailSignal = ref<Signal | null>(null)

function directionType(d: string) {
  if (d === 'bullish') return 'success'
  if (d === 'bearish') return 'danger'
  return 'warning'
}

function directionLabel(d: string) {
  if (d === 'bullish') return '看多'
  if (d === 'bearish') return '看空'
  return '中性'
}

function formatTime(ts: string) {
  if (!ts) return ''
  const d = new Date(ts)
  return d.toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
}

async function loadFeed() {
  loading.value = true
  try {
    const params: any = { limit: 50 }
    if (filterType.value) params.type = filterType.value
    if (filterDirection.value) params.direction = filterDirection.value
    const res = await signalApi.getFeed(params)
    signals.value = res.data?.data || res.data || []
  } catch {
    signals.value = []
  } finally {
    loading.value = false
  }
}

function showDetail(s: Signal) {
  detailSignal.value = s
  showDetailDialog.value = true
}

async function handlePublish() {
  publishing.value = true
  try {
    await signalApi.publish({
      publisher_id: publishForm.publisher_id,
      publisher_name: publishForm.publisher_name,
      type: publishForm.type,
      direction: publishForm.direction,
      target: { code: publishForm.target_code, name: publishForm.target_name },
      price: publishForm.price || undefined,
      confidence: publishForm.confidence,
      reasoning: publishForm.reasoning,
    })
    ElMessage.success('信号发布成功')
    showPublish.value = false
    loadFeed()
  } catch (e: any) {
    ElMessage.error(e.message || '发布失败')
  } finally {
    publishing.value = false
  }
}

async function handleExpire(s: Signal) {
  try {
    await signalApi.expire(s.signal_id)
    ElMessage.success('信号已过期')
    loadFeed()
    if (detailSignal.value?.signal_id === s.signal_id) {
      detailSignal.value.status = 'expired'
    }
  } catch (e: any) {
    ElMessage.error(e.message || '操作失败')
  }
}

watch([filterType, filterDirection], () => loadFeed())

onMounted(() => loadFeed())
</script>

<style scoped>
.section-card { background: #1f1f1f; border: 1px solid #2c2c2c; }
.section-card :deep(.el-card__header) {
  border-bottom: 1px solid #2c2c2c; padding: 12px 16px;
  color: #e5eaf3; font-size: 14px; font-weight: 600;
}
.feed-header { display: flex; justify-content: space-between; align-items: center; }
.feed-actions { display: flex; gap: 8px; flex-wrap: wrap; }
.signal-list { display: flex; flex-direction: column; gap: 8px; }
.signal-item {
  background: #2c2c2c; border-radius: 6px; padding: 12px;
  border-left: 3px solid #4a4a4a;
}
.signal-item.bullish { border-left-color: #67c23a; }
.signal-item.bearish { border-left-color: #f56c6c; }
.signal-item.neutral { border-left-color: #e6a23c; }
.signal-meta { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.direction-tag { font-weight: 600; }
.signal-publisher { font-size: 12px; color: #909399; }
.type-tag { font-size: 10px; }
.signal-target { font-size: 13px; font-weight: 600; color: #e5eaf3; }
.signal-price { font-size: 12px; color: #e6a23c; margin-top: 4px; }
.signal-reasoning {
  font-size: 12px; color: #c0c4cc; line-height: 1.5;
  margin-top: 8px; background: #1a1a1a; border-radius: 4px; padding: 8px;
  max-height: 80px; overflow-y: auto; cursor: pointer;
}
.signal-footer { display: flex; align-items: center; gap: 12px; margin-top: 8px; font-size: 11px; color: #606266; }
.signal-confidence { color: #409eff; }
.signal-time { color: #606266; }
.detail-section { display: flex; gap: 12px; align-items: center; margin-bottom: 12px; }
.detail-section label { font-size: 13px; color: #909399; min-width: 60px; }
.detail-section span { font-size: 13px; color: #e5eaf3; }
.detail-reasoning {
  font-size: 13px; color: #c0c4cc; line-height: 1.6;
  background: #1a1a1a; border-radius: 4px; padding: 8px; margin: 0;
  max-height: 200px; overflow-y: auto; flex: 1;
}
</style>
