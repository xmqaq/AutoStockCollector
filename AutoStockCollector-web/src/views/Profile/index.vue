<template>
  <div class="profile-page">
    <div class="page-header">
      <h2>个人中心</h2>
    </div>

    <el-card shadow="never" class="profile-card">
      <el-form ref="formRef" :model="form" :rules="rules" label-width="100px" label-position="left">
        <el-form-item label="用户名">
          <el-input :model-value="authStore.user?.username" disabled />
        </el-form-item>
        <el-form-item label="昵称" prop="nickname">
          <el-input v-model="form.nickname" placeholder="设置昵称（2-20位字符）" maxlength="20" show-word-limit />
        </el-form-item>
        <el-form-item label="邮箱" prop="email">
          <el-input v-model="form.email" placeholder="邮箱地址" />
        </el-form-item>
        <el-form-item label="角色">
          <el-tag :type="authStore.user?.role === 'admin' ? 'danger' : 'info'" size="small">
            {{ authStore.user?.role === 'admin' ? '管理员' : '普通用户' }}
          </el-tag>
        </el-form-item>
        <el-divider />
        <el-form-item label="原密码" prop="oldPassword">
          <el-input v-model="form.oldPassword" type="password" show-password placeholder="留空则不修改密码" />
        </el-form-item>
        <el-form-item label="新密码" prop="newPassword">
          <el-input v-model="form.newPassword" type="password" show-password placeholder="至少6位" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="saving" @click="handleSave">保存</el-button>
        </el-form-item>
      </el-form>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { useAuthStore } from '@/stores/authStore'
import { authApi } from '@/api/auth'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import { Message } from '@element-plus/icons-vue'

const authStore = useAuthStore()
const formRef = ref<FormInstance>()
const saving = ref(false)

const form = reactive({
  nickname: '',
  email: '',
  oldPassword: '',
  newPassword: '',
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

  saving.value = true
  try {
    const payload: Record<string, unknown> = {}
    if (form.nickname && form.nickname !== (authStore.user?.nickname || '')) {
      payload.nickname = form.nickname
    }
    if (form.email && form.email !== authStore.user?.email) {
      payload.email = form.email
    }
    if (form.oldPassword && form.newPassword) {
      payload.old_password = form.oldPassword
      payload.new_password = form.newPassword
    }

    if (Object.keys(payload).length === 0) {
      ElMessage.info('没有需要修改的内容')
      return
    }

    await authApi.updateProfile(payload)
    ElMessage.success('保存成功')
    await authStore.refreshProfile()
    form.oldPassword = ''
    form.newPassword = ''
  } catch {
    // handled by interceptor
  } finally {
    saving.value = false
  }
}
</script>

<style scoped>
.profile-page {
  max-width: 640px;
}

.page-header h2 {
  margin: 0 0 20px;
  font-size: 20px;
  font-weight: 600;
  color: var(--text-primary);
}

.profile-card {
  border-radius: var(--radius-md);
}
</style>
