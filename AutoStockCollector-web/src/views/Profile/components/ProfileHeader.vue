<template>
  <div class="profile-header">
    <div class="header-bg">
      <div class="bg-pattern"></div>
    </div>
    <div class="header-content">
      <div class="avatar-wrapper">
        <div class="avatar-ring"></div>
        <el-avatar :size="72" class="user-avatar">
          {{ initial }}
        </el-avatar>
        <div class="role-badge" :class="role">
          <el-icon v-if="role === 'admin'"><StarFilled /></el-icon>
          <el-icon v-else><UserFilled /></el-icon>
        </div>
      </div>
      <div class="user-info">
        <h2 class="username">{{ username }}</h2>
        <div class="user-meta">
          <el-tag :type="role === 'admin' ? 'danger' : 'primary'" effect="light" round size="small" class="role-tag">
            {{ role === 'admin' ? '系统管理员' : '量化投资者' }}
          </el-tag>
          <span class="welcome-text">欢迎来到 AutoStock 智能量化监控平台</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useAuthStore } from '@/stores/authStore'
import { StarFilled, UserFilled } from '@element-plus/icons-vue'

const authStore = useAuthStore()

const username = computed(() => authStore.user?.username || 'User')
const role = computed(() => authStore.user?.role || 'user')
const initial = computed(() => username.value.charAt(0).toUpperCase())
</script>

<style scoped>
.profile-header {
  position: relative;
  background: var(--bg-card);
  border-radius: var(--radius-lg);
  overflow: hidden;
  box-shadow: var(--shadow-sm);
  border: 1px solid var(--border-color);
  margin-bottom: 16px;
}

.header-bg {
  height: 80px;
  background: linear-gradient(135deg, var(--brand-100), var(--brand-50));
  position: relative;
  overflow: hidden;
}

.bg-pattern {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background-image: radial-gradient(var(--brand-200) 1px, transparent 1px);
  background-size: 20px 20px;
  opacity: 0.5;
}

.header-content {
  padding: 0 24px 20px;
  display: flex;
  align-items: flex-end;
  gap: 20px;
  margin-top: -36px;
  position: relative;
  z-index: 1;
}

.avatar-wrapper {
  position: relative;
}

.avatar-ring {
  position: absolute;
  top: -4px;
  left: -4px;
  right: -4px;
  bottom: -4px;
  background: var(--bg-card);
  border-radius: 50%;
  z-index: 0;
}

.user-avatar {
  position: relative;
  z-index: 1;
  font-size: 28px;
  font-weight: 700;
  background: linear-gradient(135deg, var(--brand-500), var(--brand-600));
  color: #ffffff;
  border: 2px solid var(--bg-card);
  width: 72px;
  height: 72px;
}

.role-badge {
  position: absolute;
  bottom: 0;
  right: 0;
  width: 24px;
  height: 24px;
  border-radius: 50%;
  background: var(--bg-card);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 2;
  box-shadow: var(--shadow-sm);
  font-size: 12px;
}

.role-badge.admin { color: var(--color-danger); }
.role-badge.user { color: var(--el-color-primary); }

.user-info {
  flex: 1;
  padding-bottom: 2px;
}

.username {
  margin: 0 0 6px 0;
  font-size: 20px;
  font-weight: 700;
  color: var(--text-primary);
  letter-spacing: -0.5px;
}

.user-meta {
  display: flex;
  align-items: center;
  gap: 12px;
}

.role-tag {
  font-weight: 600;
}

.welcome-text {
  font-size: 13px;
  color: var(--text-muted);
}

@media (max-width: 640px) {
  .header-content {
    flex-direction: column;
    align-items: center;
    text-align: center;
    padding: 0 20px 20px;
  }
  .user-info {
    padding-bottom: 0;
  }
  .user-meta {
    justify-content: center;
  }
}
</style>
