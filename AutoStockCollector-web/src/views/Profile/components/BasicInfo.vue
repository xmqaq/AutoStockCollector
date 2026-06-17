<template>
  <el-card shadow="hover" class="profile-card basic-info-card">
    <template #header>
      <div class="card-header">
        <div class="header-icon"><el-icon><User /></el-icon></div>
        <span class="header-title">基础信息</span>
      </div>
    </template>
    
    <el-form ref="formRef" :model="form" :rules="rules" label-position="top" class="custom-form">
      <el-form-item label="用户名" class="readonly-item">
        <el-input :model-value="authStore.user?.username" disabled>
          <template #prefix><el-icon><User /></el-icon></template>
        </el-input>
      </el-form-item>
      
      <el-form-item label="昵称" prop="nickname">
        <el-input v-model="form.nickname" placeholder="设置昵称（2-20位字符）" maxlength="20" show-word-limit>
          <template #prefix><el-icon><Postcard /></el-icon></template>
        </el-input>
      </el-form-item>
      
      <el-form-item label="联系邮箱" prop="email">
        <el-input v-model="form.email" placeholder="绑定邮箱以便接收异动提醒">
          <template #prefix><el-icon><Message /></el-icon></template>
        </el-input>
      </el-form-item>
      
      <div class="form-actions">
        <el-button type="primary" :loading="saving" @click="handleSave" class="action-btn">
          <el-icon class="btn-icon"><Check /></el-icon>保存基本信息
        </el-button>
      </div>
    </el-form>
  </el-card>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { useAuthStore } from '@/stores/authStore'
import { authApi } from '@/api/auth'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import { User, Message, Postcard, Check } from '@element-plus/icons-vue'

const authStore = useAuthStore()
const formRef = ref<FormInstance>()
const saving = ref(false)

const form = reactive({
  nickname: '',
  email: '',
})

const rules: FormRules = {
  nickname: [
    { min: 2, max: 20, message: '昵称需2-20位字符', trigger: 'blur' },
  ],
  email: [
    { type: 'email', message: '邮箱格式不正确', trigger: 'blur' },
  ],
}

onMounted(() => {
  form.nickname = authStore.user?.nickname || authStore.user?.username || ''
  form.email = authStore.user?.email || ''
})

async function handleSave() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return

  const payload: Record<string, unknown> = {}
  if (form.nickname && form.nickname !== (authStore.user?.nickname || '')) {
    payload.nickname = form.nickname
  }
  if (form.email !== authStore.user?.email) {
    payload.email = form.email
  }

  if (Object.keys(payload).length === 0) {
    ElMessage.info('基础信息未修改')
    return
  }

  saving.value = true
  try {
    await authApi.updateProfile(payload)
    ElMessage.success('基础信息保存成功')
    await authStore.refreshProfile()
  } catch {
    // handled by interceptor
  } finally {
    saving.value = false
  }
}
</script>

<style scoped>
.profile-card {
  border-radius: var(--radius-md);
  border: 1px solid var(--border-color);
  height: 100%;
}

.profile-card :deep(.el-card__body) {
  padding: 16px 20px;
}

.profile-card :deep(.el-card__header) {
  padding: 12px 20px;
}

.card-header {
  display: flex;
  align-items: center;
  gap: 10px;
}

.header-icon {
  width: 28px;
  height: 28px;
  border-radius: 6px;
  background: var(--brand-100);
  color: var(--brand-600);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 16px;
}

.header-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
}

.custom-form :deep(.el-form-item) {
  margin-bottom: 16px;
}

.custom-form :deep(.el-form-item__label) {
  font-weight: 500;
  color: var(--text-secondary);
  padding-bottom: 4px;
}

.custom-form :deep(.el-input__wrapper) {
  background-color: var(--bg-soft);
  box-shadow: none;
  border: 1px solid transparent;
  transition: all 0.2s ease;
}

.custom-form :deep(.el-input__wrapper:hover) {
  background-color: var(--bg-card);
  border-color: var(--border-strong);
}

.custom-form :deep(.el-input__wrapper.is-focus) {
  background-color: var(--bg-card);
  border-color: var(--el-color-primary);
  box-shadow: 0 0 0 2px var(--brand-100);
}

.readonly-item :deep(.el-input__wrapper) {
  background-color: var(--bg-page);
  border-color: var(--border-color);
}

.form-actions {
  margin-top: 20px;
  display: flex;
  justify-content: flex-start;
}

.action-btn {
  padding: 8px 20px;
  font-weight: 600;
  border-radius: var(--radius-sm);
}

.btn-icon {
  margin-right: 6px;
}
</style>
