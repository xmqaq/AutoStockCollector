<template>
  <div class="login-page">
    <div class="login-card">
      <div class="login-header">
        <svg class="logo-mark" viewBox="0 0 24 24" width="32" height="32" aria-hidden="true">
          <rect x="3" y="10" width="4" height="9" rx="1" fill="currentColor" opacity="0.45" />
          <rect x="10" y="5" width="4" height="14" rx="1" fill="currentColor" opacity="0.7" />
          <rect x="17" y="8" width="4" height="11" rx="1" fill="currentColor" />
        </svg>
        <h1 class="login-title">AutoStockCollector</h1>
        <p class="login-subtitle">量化投资监控平台</p>
      </div>

      <el-tabs v-model="activeTab" class="login-tabs" stretch>
        <el-tab-pane label="登录" name="login">
          <el-form ref="loginFormRef" :model="loginForm" :rules="loginRules" label-position="top" @keyup.enter="handleLogin">
            <el-form-item label="用户名" prop="username">
              <el-input v-model="loginForm.username" placeholder="请输入用户名" :prefix-icon="User" />
            </el-form-item>
            <el-form-item label="密码" prop="password">
              <el-input v-model="loginForm.password" type="password" show-password placeholder="请输入密码" :prefix-icon="Lock" />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" class="submit-btn" :loading="loading" @click="handleLogin">
                登 录
              </el-button>
            </el-form-item>
          </el-form>
        </el-tab-pane>

        <el-tab-pane label="注册" name="register">
          <el-form ref="registerFormRef" :model="registerForm" :rules="registerRules" label-position="top" @keyup.enter="handleRegister">
            <el-form-item label="用户名" prop="username">
              <el-input v-model="registerForm.username" placeholder="2-20位字符（字母/数字/中文/下划线）" :prefix-icon="User" />
            </el-form-item>
            <el-form-item label="密码" prop="password">
              <el-input v-model="registerForm.password" type="password" show-password placeholder="至少6位" :prefix-icon="Lock" />
            </el-form-item>
            <el-form-item label="确认密码" prop="confirmPassword">
              <el-input v-model="registerForm.confirmPassword" type="password" show-password placeholder="再次输入密码" :prefix-icon="Lock" />
            </el-form-item>
            <el-form-item label="邮箱（选填）" prop="email">
              <el-input v-model="registerForm.email" placeholder="用于找回密码" :prefix-icon="Message" />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" class="submit-btn" :loading="loading" @click="handleRegister">
                注 册
              </el-button>
            </el-form-item>
          </el-form>
        </el-tab-pane>
      </el-tabs>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAuthStore } from '@/stores/authStore'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import { User, Lock, Message } from '@element-plus/icons-vue'

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()

const activeTab = ref('login')
const loading = ref(false)
const loginFormRef = ref<FormInstance>()
const registerFormRef = ref<FormInstance>()

const loginForm = reactive({
  username: '',
  password: '',
})

const loginRules: FormRules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
}

const registerForm = reactive({
  username: '',
  password: '',
  confirmPassword: '',
  email: '',
})

const validateConfirm = (_rule: unknown, value: string, callback: (e?: Error) => void) => {
  if (value !== registerForm.password) {
    callback(new Error('两次输入的密码不一致'))
  } else {
    callback()
  }
}

const registerRules: FormRules = {
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' },
    { min: 2, max: 20, message: '用户名需2-20位字符', trigger: 'blur' },
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 6, message: '密码至少6位', trigger: 'blur' },
  ],
  confirmPassword: [
    { required: true, message: '请确认密码', trigger: 'blur' },
    { validator: validateConfirm, trigger: 'blur' },
  ],
}

async function handleLogin() {
  const valid = await loginFormRef.value?.validate().catch(() => false)
  if (!valid) return
  loading.value = true
  try {
    await authStore.login(loginForm)
    ElMessage.success('登录成功')
    const redirect = (route.query.redirect as string) || '/dashboard'
    router.push(redirect)
  } catch (e: any) {
    const msg = e?.response?.data?.error || e?.message || '登录失败'
    ElMessage.error(msg)
  } finally {
    loading.value = false
  }
}

async function handleRegister() {
  const valid = await registerFormRef.value?.validate().catch(() => false)
  if (!valid) return
  loading.value = true
  try {
    await authStore.register({
      username: registerForm.username,
      password: registerForm.password,
      email: registerForm.email || undefined,
    })
    ElMessage.success('注册成功')
    router.push('/dashboard')
  } catch (e: any) {
    const msg = e?.response?.data?.error || e?.message || '注册失败'
    ElMessage.error(msg)
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--bg-page);
  padding: 20px;
}

.login-card {
  width: 420px;
  max-width: 100%;
  background: var(--bg-card);
  border-radius: 16px;
  padding: 40px;
  box-shadow: var(--shadow-lg, 0 4px 24px rgba(0,0,0,0.12));
  border: 1px solid var(--border-color);
}

.login-header {
  text-align: center;
  margin-bottom: 32px;
}

.logo-mark {
  color: var(--el-color-primary, #409eff);
  margin-bottom: 12px;
}

.login-title {
  font-size: 24px;
  font-weight: 700;
  color: var(--text-primary);
  margin: 0 0 8px;
  letter-spacing: 0.02em;
}

.login-subtitle {
  font-size: 14px;
  color: var(--text-muted);
  margin: 0;
}

.login-tabs {
  --el-tabs-header-height: 44px;
}

.login-tabs :deep(.el-tabs__item) {
  color: var(--text-muted);
  font-size: 15px;
  font-weight: 500;
}

.login-tabs :deep(.el-tabs__item.is-active) {
  color: var(--el-color-primary, #409eff);
}

.login-tabs :deep(.el-tabs__active-bar) {
  background: var(--el-color-primary, #409eff);
}

.login-tabs :deep(.el-form-item__label) {
  color: var(--text-secondary);
  font-size: 13px;
  padding-bottom: 4px;
}

.login-tabs :deep(.el-input__wrapper) {
  background: var(--bg-soft);
  border: 1px solid var(--border-color);
  box-shadow: none;
  border-radius: 8px;
}

.login-tabs :deep(.el-input__wrapper:hover) {
  border-color: var(--el-color-primary, #409eff);
}

.login-tabs :deep(.el-input__wrapper.is-focus) {
  border-color: var(--el-color-primary, #409eff);
  box-shadow: 0 0 0 1px var(--el-color-primary, #409eff);
}

.login-tabs :deep(.el-input__inner) {
  color: var(--text-primary);
  height: 42px;
}

.login-tabs :deep(.el-input__prefix-inner) {
  color: var(--text-faint);
}

.submit-btn {
  width: 100%;
  height: 44px;
  font-size: 16px;
  font-weight: 600;
  border-radius: 8px;
  margin-top: 8px;
}

.login-tabs :deep(.el-form-item) {
  margin-bottom: 22px;
}
</style>
