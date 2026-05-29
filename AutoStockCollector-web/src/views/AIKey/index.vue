<template>
  <div class="ai-key-page">
    <el-card shadow="never" class="section-card">
      <template #header>
        <div class="card-header">
          <span>AI Key 管理</span>
          <el-button size="small" type="primary" @click="showDialog = true">
            <el-icon><Plus /></el-icon> 新增厂商
          </el-button>
        </div>
      </template>
      <el-table :data="keys" stripe v-loading="loading">
        <el-table-column prop="name" label="厂商" min-width="120" />
        <el-table-column prop="provider" label="Provider" width="140" />
        <el-table-column label="API Key" width="280">
          <template #default="{ row }">
            <el-input
              v-model="row.api_key"
              type="password"
              placeholder="输入Key后保存"
              @blur="saveKey(row)"
              @keyup.enter="saveKey(row)"
            />
          </template>
        </el-table-column>
        <el-table-column label="启用" width="80">
          <template #default="{ row }">
            <el-switch v-model="row.enabled" @change="toggle(row)" />
          </template>
        </el-table-column>
        <el-table-column prop="priority" label="优先级" width="80" />
        <el-table-column label="操作" width="100" align="center">
          <template #default="{ row }">
            <el-button size="small" type="danger" plain @click="remove(row.provider)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import { aiKeyApi, type AIKeyConfig } from '@/api/ai'
import { useRouter } from 'vue-router'

const router = useRouter()
const loading = ref(false)
const keys = ref<AIKeyConfig[]>([])
const showDialog = ref(false)

async function loadKeys() {
  loading.value = true
  try {
    const res = await aiKeyApi.list()
    keys.value = res.data?.data || []
  } catch {
    keys.value = []
  } finally {
    loading.value = false
  }
}

async function saveKey(row: AIKeyConfig) {
  try {
    await aiKeyApi.update({ provider: row.provider, name: row.name, enabled: row.enabled, priority: row.priority, api_key: row.api_key })
    ElMessage.success('保存成功')
  } catch {
    ElMessage.error('保存失败')
  }
}

async function toggle(row: AIKeyConfig) {
  await saveKey(row)
}

async function remove(provider: string) {
  try {
    await aiKeyApi.remove(provider)
    ElMessage.success('已删除')
    await loadKeys()
  } catch {
    ElMessage.error('删除失败')
  }
}

onMounted(() => loadKeys())
</script>

<style scoped>
.ai-key-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.section-card {
  background: #1f1f1f;
  border: 1px solid #2c2c2c;
}
.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
</style>