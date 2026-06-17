<template>
  <el-card shadow="hover" class="profile-card security-card">
    <template #header>
      <div class="card-header">
        <div class="header-icon"><el-icon><Lock /></el-icon></div>
        <span class="header-title">安全设置</span>
      </div>
    </template>
    
    <el-form ref="formRef" :model="form" :rules="rules" label-position="top" class="custom-form">
      <el-alert
        title="密码修改提示"
        type="warning"
        description="定期修改密码可提升账号安全性。若无需修改请留空。"
        show-icon
        :closable="false"
        class="security-alert"
      />

      <el-form-item label="当前密码" prop="oldPassword">
        <el-input v-model="form.oldPassword" type="password" show-password placeholder="请输入当前密码">
          <template #prefix><el-icon><Key /></el-icon></template>
        </el-input>
      </el-form-item>
      
      <el-form-item label="新密码" prop="newPassword">
        <el-input v-model="form.newPassword" type="password" show-password placeholder="请输入至少6位新密码">
          <template #prefix><el-icon><Lock /></el-icon></template>
        </el-input>
      </el-form-item>
      
      <el-form-item label="确认新密码" prop="confirmPassword">
        <el-input v-model="form.confirmPassword" type="password" show-password placeholder="请再次输入新密码">
          <template #prefix><el-icon><CircleCheck /></el-icon></template>
        </el-input>
      </el-form-item>
      
      <div class="form-actions">
        <el-button type="primary" :loading="saving" @click="handleSave" class="action-btn" :disabled="!isFormFilled">
          <el-icon class="btn-icon"><RefreshRight /></el-icon>更新密码
        </el-button>
      </div>
    </el-form>
  </el-card>
</template>

<script setup lang="ts">
import { ref, reactive, computed } from 'vue'
import { authApi } from '@/api/auth'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import { Lock, Key, CircleCheck, RefreshRight } from '@element-plus/icons-vue'

const formRef = ref<FormInstance>()
const saving = ref(false)

const form = reactive({
  oldPassword: '',
  newPassword: '',
  confirmPassword: '',
})

const validateConfirmPassword = (_rule: any, value: string, callback: any) => {
  if (value === '') {
    callback(new Error('请再次输入新密码'))
  } else if (value !== form.newPassword) {
    callback(new Error('两次输入密码不一致!'))
  } else {
    callback()
  }
}

const rules: FormRules = {
  oldPassword: [
    { required: true, message: '请输入当前密码', trigger: 'blur' }
  ],
  newPassword: [
    { required: true, message: '请输入新密码', trigger: 'blur' },
    { min: 6, message: '密码长度至少为6位', trigger: 'blur' }
  ],
  confirmPassword: [
    { required: true, validator: validateConfirmPassword, trigger: 'blur' }
  ]
}

const isFormFilled = computed(() => {
  return form.oldPassword.length > 0 && form.newPassword.length >= 6 && form.confirmPassword.length >= 6
})

async function handleSave() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return

  saving.value = true
  try {
    await authApi.updateProfile({
      old_password: form.oldPassword,
      new_password: form.newPassword
    })
    ElMessage.success('密码更新成功')
    form.oldPassword = ''
    form.newPassword = ''
    form.confirmPassword = ''
    formRef.value?.resetFields()
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
  background: var(--up-tint);
  color: var(--color-danger);
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

.security-alert {
  margin-bottom: 16px;
  border-radius: var(--radius-sm);
}

.security-alert :deep(.el-alert__title) {
  font-size: 13px;
}

.security-alert :deep(.el-alert__description) {
  font-size: 12px;
  margin-top: 2px;
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
