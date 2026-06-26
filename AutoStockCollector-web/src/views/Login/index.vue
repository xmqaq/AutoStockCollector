<template>
  <div class="login-page">
    <!-- Left Section with Advanced Tech Background -->
    <div class="login-left">
      <!-- Animated Tech Background Elements -->
      <div class="tech-bg-elements">
        <div class="data-stream ds-1"></div>
        <div class="data-stream ds-2"></div>
        <div class="data-stream ds-3"></div>
        
        <!-- Abstract Candlestick/Chart Elements -->
        <svg class="abstract-chart" viewBox="0 0 400 200" preserveAspectRatio="none">
          <path d="M0,150 L40,120 L80,140 L120,80 L160,100 L200,40 L240,60 L280,20 L320,50 L360,10 L400,30" 
                fill="none" stroke="var(--brand-300)" stroke-width="2" opacity="0.6" />
          <path d="M0,150 L40,120 L80,140 L120,80 L160,100 L200,40 L240,60 L280,20 L320,50 L360,10 L400,30 L400,200 L0,200 Z" 
                fill="url(#chart-grad)" opacity="0.4" />
          <defs>
            <linearGradient id="chart-grad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stop-color="var(--brand-200)" />
              <stop offset="100%" stop-color="transparent" />
            </linearGradient>
          </defs>
        </svg>

        <!-- Floating Particles -->
        <div class="particle p-1"></div>
        <div class="particle p-2"></div>
        <div class="particle p-3"></div>
        <div class="particle p-4"></div>
        <div class="particle p-5"></div>
      </div>

      <div class="brand-info">
        <div class="brand-logo-container">
          <div class="logo-glow"></div>
          <div class="brand-logo">
            <svg viewBox="0 0 24 24" width="48" height="48" aria-hidden="true" class="logo-svg">
              <rect x="3" y="10" width="4" height="9" rx="1" fill="currentColor" opacity="0.6" class="bar-1" />
              <rect x="10" y="5" width="4" height="14" rx="1" fill="currentColor" opacity="0.8" class="bar-2" />
              <rect x="17" y="8" width="4" height="11" rx="1" fill="currentColor" class="bar-3" />
            </svg>
            <h1 class="brand-title">AutoStock <span class="title-highlight">AI</span></h1>
          </div>
        </div>
        
        <p class="brand-desc">新一代智能量化投资监控引擎。<br>基于多因子模型和深度学习，在海量市场数据中为您精准捕捉阿尔法收益。</p>
        
        <div class="feature-cards">
          <div class="feature-card">
            <div class="feature-icon"><el-icon><DataLine /></el-icon></div>
            <div class="feature-text">
              <h3>全息数据监控</h3>
              <p>毫秒级异动捕捉与量价背离预警</p>
            </div>
          </div>
          <div class="feature-card">
            <div class="feature-icon"><el-icon><Cpu /></el-icon></div>
            <div class="feature-text">
              <h3>大模型研报解读</h3>
              <p>NLP情感分析与深层逻辑抽取</p>
            </div>
          </div>
          <div class="feature-card">
            <div class="feature-icon"><el-icon><TrendCharts /></el-icon></div>
            <div class="feature-text">
              <h3>智能策略回测</h3>
              <p>多因子选股池与动态仓位优化</p>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Right Section -->
    <div class="login-right">
      <div class="login-card">
        <div class="login-header">
          <h2>欢迎回来</h2>
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
  </div>
</template>

<script setup lang="ts">
import { ref, reactive } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAuthStore } from '@/stores/authStore'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import { User, Lock, Message, DataLine, Cpu, TrendCharts } from '@element-plus/icons-vue'

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
  height: 100%;
  display: flex;
  background: var(--bg-page);
  background-image: radial-gradient(var(--brand-100) 1px, transparent 1px),
    radial-gradient(var(--brand-100) 1px, transparent 1px);
  background-size: 40px 40px;
  background-position: 0 0, 20px 20px;
  font-family: var(--font-sans);
}

.login-left {
  flex: 1;
  display: flex;
  flex-direction: column;
  justify-content: center;
  padding: 60px 80px;
  background: linear-gradient(135deg, var(--bg-card) 0%, var(--brand-50) 100%);
  color: var(--text-primary);
  position: relative;
  overflow: hidden;
}

/* Tech Background Animations */
.tech-bg-elements {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  overflow: hidden;
  z-index: 0;
}

.data-stream {
  position: absolute;
  width: 1px;
  background: linear-gradient(to bottom, transparent, var(--brand-400), transparent);
  animation: streamFall linear infinite;
  opacity: 0.8;
}

.ds-1 { left: 20%; height: 100px; animation-duration: 3s; animation-delay: 0s; }
.ds-2 { left: 50%; height: 150px; animation-duration: 4s; animation-delay: 1.5s; }
.ds-3 { left: 80%; height: 80px; animation-duration: 2.5s; animation-delay: 0.5s; }

@keyframes streamFall {
  0% { top: -200px; opacity: 0; }
  10% { opacity: 1; }
  90% { opacity: 1; }
  100% { top: 100vh; opacity: 0; }
}

.abstract-chart {
  position: absolute;
  bottom: 0;
  left: 0;
  width: 100%;
  height: 40%;
  opacity: 0.4;
}

.particle {
  position: absolute;
  border-radius: 50%;
  background: var(--brand-300);
  box-shadow: 0 0 10px var(--brand-400);
  animation: float linear infinite;
  opacity: 0.5;
}

.p-1 { width: 6px; height: 6px; left: 10%; bottom: 20%; animation-duration: 15s; }
.p-2 { width: 4px; height: 4px; left: 30%; bottom: 50%; animation-duration: 20s; animation-delay: -5s; }
.p-3 { width: 8px; height: 8px; left: 60%; bottom: 10%; animation-duration: 18s; animation-delay: -2s; }
.p-4 { width: 5px; height: 5px; left: 80%; bottom: 40%; animation-duration: 22s; animation-delay: -8s; }
.p-5 { width: 7px; height: 7px; left: 90%; bottom: 70%; animation-duration: 16s; animation-delay: -12s; }

@keyframes float {
  0% { transform: translateY(0) translateX(0); opacity: 0; }
  10% { opacity: 1; }
  90% { opacity: 1; }
  100% { transform: translateY(-500px) translateX(50px); opacity: 0; }
}

/* Brand Info Styles */
.brand-info {
  position: relative;
  z-index: 1;
  max-width: 540px;
}

.brand-logo-container {
  position: relative;
  display: inline-block;
  margin-bottom: 24px;
}

.logo-glow {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  width: 120%;
  height: 120%;
  background: radial-gradient(circle, var(--brand-500) 0%, transparent 70%);
  z-index: -1;
  animation: pulse 4s ease-in-out infinite alternate;
  opacity: 0.3;
}

@keyframes pulse {
  0% { transform: translate(-50%, -50%) scale(0.8); opacity: 0.2; }
  100% { transform: translate(-50%, -50%) scale(1.1); opacity: 0.5; }
}

.brand-logo {
  display: flex;
  align-items: center;
  gap: 16px;
}

.logo-svg {
  color: var(--brand-200);
  filter: drop-shadow(0 0 8px var(--brand-400));
}

.bar-1 { animation: barGrow 1.5s ease-in-out infinite alternate; transform-origin: bottom; }
.bar-2 { animation: barGrow 1.5s ease-in-out infinite alternate 0.5s; transform-origin: bottom; }
.bar-3 { animation: barGrow 1.5s ease-in-out infinite alternate 1s; transform-origin: bottom; }

@keyframes barGrow {
  0% { transform: scaleY(0.6); }
  100% { transform: scaleY(1.1); }
}

.brand-title {
  font-size: 42px;
  font-weight: 800;
  margin: 0;
  letter-spacing: 1px;
  color: var(--text-primary);
}

.title-highlight {
  color: var(--brand-600);
  font-style: italic;
  font-weight: 900;
}

.brand-desc {
  font-size: 18px;
  line-height: 1.8;
  color: var(--text-secondary);
  margin: 0 0 48px;
  font-weight: 400;
}

/* Feature Cards */
.feature-cards {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.feature-card {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 16px 20px;
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-sm);
  transition: all 0.3s ease;
}

.feature-card:hover {
  background: var(--bg-card);
  border-color: var(--brand-300);
  transform: translateX(10px);
  box-shadow: var(--shadow-md);
}

.feature-icon {
  background: var(--brand-50);
  border-radius: 10px;
  width: 48px;
  height: 48px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 24px;
  color: var(--brand-600);
}

.feature-text h3 {
  margin: 0 0 4px 0;
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
}

.feature-text p {
  margin: 0;
  font-size: 14px;
  color: var(--text-muted);
}

/* Right Section - Glassmorphism Card */
.login-right {
  width: 520px;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 40px;
  position: relative;
  z-index: 1;
}

.login-right::before {
  content: '';
  position: absolute;
  top: -50%;
  right: -50%;
  width: 200%;
  height: 200%;
  background: radial-gradient(circle at center, var(--brand-50) 0%, transparent 50%);
  z-index: -1;
}

.login-card {
  width: 100%;
  background: var(--bg-card);
  border-radius: var(--radius-lg);
  padding: 48px;
  box-shadow: var(--shadow-lg);
  border: 1px solid var(--border-color);
  transition: transform 0.3s ease, box-shadow 0.3s ease;
}

.login-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 25px 50px rgba(15, 23, 42, 0.08);
}

.login-header {
  text-align: center;
  margin-bottom: 32px;
}

.login-header h2 {
  margin: 0;
  font-size: 28px;
  color: var(--text-primary);
  font-weight: 700;
  letter-spacing: -0.5px;
}

.login-tabs {
  --el-tabs-header-height: 48px;
}

.login-tabs :deep(.el-tabs__item) {
  color: var(--text-muted);
  font-size: 16px;
  font-weight: 500;
  transition: color 0.3s ease;
}

.login-tabs :deep(.el-tabs__item:hover) {
  color: var(--el-color-primary);
}

.login-tabs :deep(.el-tabs__item.is-active) {
  color: var(--el-color-primary);
  font-weight: 600;
}

.login-tabs :deep(.el-tabs__active-bar) {
  background: var(--el-color-primary);
  height: 3px;
  border-radius: 3px 3px 0 0;
}

.login-tabs :deep(.el-form-item__label) {
  color: var(--text-secondary);
  font-size: 14px;
  font-weight: 600;
  padding-bottom: 8px;
}

.login-tabs :deep(.el-input__wrapper) {
  background: var(--bg-soft);
  border: 1px solid var(--border-color);
  box-shadow: none;
  border-radius: var(--radius-sm);
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

.login-tabs :deep(.el-input__wrapper:hover) {
  border-color: var(--brand-300);
  background: var(--bg-card);
}

.login-tabs :deep(.el-input__wrapper.is-focus) {
  background: var(--bg-card);
  border-color: var(--el-color-primary);
  box-shadow: 0 0 0 3px var(--brand-100);
}

.login-tabs :deep(.el-input__inner) {
  color: var(--text-primary);
  height: 48px;
  font-size: 15px;
}

.login-tabs :deep(.el-input__prefix-inner) {
  color: var(--text-faint);
  font-size: 18px;
  transition: color 0.3s ease;
}

.login-tabs :deep(.el-input__wrapper.is-focus .el-input__prefix-inner) {
  color: var(--el-color-primary);
}

.submit-btn {
  width: 100%;
  height: 52px;
  font-size: 16px;
  font-weight: 600;
  border-radius: var(--radius-sm);
  margin-top: 16px;
  background: linear-gradient(135deg, var(--brand-500), var(--brand-700));
  border: none;
  color: white;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  box-shadow: 0 4px 12px rgba(99, 102, 241, 0.3);
  position: relative;
  overflow: hidden;
}

.submit-btn::after {
  content: '';
  position: absolute;
  top: 0;
  left: -100%;
  width: 100%;
  height: 100%;
  background: linear-gradient(90deg, transparent, var(--bg-hover), transparent);
  transition: left 0.5s ease;
}

.submit-btn:hover {
  transform: translateY(-2px);
  box-shadow: 0 8px 16px rgba(99, 102, 241, 0.4);
}

.submit-btn:hover::after {
  left: 100%;
}

.submit-btn:active {
  transform: translateY(0);
  box-shadow: 0 2px 8px rgba(99, 102, 241, 0.3);
}

.login-tabs :deep(.el-form-item) {
  margin-bottom: 24px;
}

@media (max-width: 1024px) {
  .login-left {
    padding: 40px;
  }
  .brand-title {
    font-size: 32px;
  }
  .feature-card {
    padding: 12px 16px;
  }
}

@media (max-width: 900px) {
  .login-left {
    display: none;
  }
  .login-right {
    width: 100%;
    padding: 20px;
  }
  .login-card {
    padding: 32px 24px;
  }
}
</style>
