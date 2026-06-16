<template>
  <div class="user-management">
    <!-- Premium Header -->
    <div class="dashboard-header">
      <div class="header-content">
        <h2 class="page-title">系统用户管理</h2>
        <p class="page-subtitle">管理系统中的所有账户权限及信息</p>
      </div>
      <div class="header-stats">
        <div class="stat-item">
          <div class="stat-label">总用户数</div>
          <div class="stat-value font-mono">{{ users.length }}</div>
        </div>
        <div class="stat-divider"></div>
        <div class="stat-item">
          <div class="stat-label">管理员</div>
          <div class="stat-value font-mono text-danger">{{ adminCount }}</div>
        </div>
      </div>
    </div>

    <!-- Main Content -->
    <div class="content-wrapper">
      <UserTable 
        :users="users"
        :loading="loading"
        :changingRole="changingRole"
        :deleting="deleting"
        @toggle-role="toggleRole"
        @delete="handleDelete"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { authApi } from '@/api/auth'
import type { UserInfo } from '@/api/auth'
import { ElMessage } from 'element-plus'
import UserTable from './components/UserTable.vue'

const users = ref<UserInfo[]>([])
const loading = ref(false)
const changingRole = ref('')
const deleting = ref('')

const adminCount = computed(() => {
  return users.value.filter(u => u.role === 'admin').length
})

async function fetchUsers() {
  loading.value = true
  try {
    const res = await authApi.getUsers()
    users.value = res.data.data || []
  } catch {
    // handled by interceptor
  } finally {
    loading.value = false
  }
}

async function toggleRole(row: UserInfo) {
  const newRole = row.role === 'admin' ? 'user' : 'admin'
  changingRole.value = row.user_id
  try {
    await authApi.updateUserRole(row.user_id, newRole)
    ElMessage.success(`已${newRole === 'admin' ? '设为管理员' : '降为普通用户'}`)
    row.role = newRole
  } catch {
    // handled by interceptor
  } finally {
    changingRole.value = ''
  }
}

async function handleDelete(row: UserInfo) {
  deleting.value = row.user_id
  try {
    await authApi.deleteUser(row.user_id)
    ElMessage.success(`已删除用户 ${row.username}`)
    users.value = users.value.filter(u => u.user_id !== row.user_id)
  } catch {
    // handled by interceptor
  } finally {
    deleting.value = ''
  }
}

onMounted(fetchUsers)
</script>

<style scoped>
.user-management {
  display: flex;
  flex-direction: column;
  gap: 20px;
  height: 100%;
}

/* Premium Header Styling */
.dashboard-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: linear-gradient(135deg, #ffffff 0%, #fcfcfd 100%);
  border: 1px solid var(--border-color, #ebeef5);
  border-radius: 12px;
  padding: 24px 32px;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.02);
}

.header-content {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.page-title {
  margin: 0;
  font-size: 22px;
  font-weight: 600;
  color: var(--text-primary);
  letter-spacing: 0.5px;
}

.page-subtitle {
  margin: 0;
  font-size: 14px;
  color: var(--text-muted);
}

.header-stats {
  display: flex;
  align-items: center;
  gap: 32px;
  background: var(--bg-soft, #f8f9fa);
  padding: 12px 24px;
  border-radius: 10px;
  border: 1px solid var(--border-color-light, #f0f2f5);
}

.stat-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 60px;
}

.stat-label {
  font-size: 13px;
  color: var(--text-muted);
  font-weight: 500;
}

.stat-value {
  font-size: 24px;
  font-weight: bold;
  color: var(--text-primary);
  line-height: 1;
}

.stat-divider {
  width: 1px;
  height: 32px;
  background-color: var(--border-color, #ebeef5);
}

.font-mono {
  font-family: var(--font-mono, "DIN Alternate", "Helvetica Neue", sans-serif);
}

.text-danger {
  color: var(--el-color-danger) !important;
}

/* Content Area */
.content-wrapper {
  flex: 1;
  min-height: 0;
}
</style>
