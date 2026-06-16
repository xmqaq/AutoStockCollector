<template>
  <div class="user-management">
    <div class="page-header">
      <h2>用户管理</h2>
      <span class="page-desc">共 {{ users.length }} 个用户</span>
    </div>

    <el-card shadow="never" class="table-card">
      <el-table :data="users" v-loading="loading" stripe style="width: 100%">
        <el-table-column prop="username" label="用户名" min-width="120" />
        <el-table-column prop="email" label="邮箱" min-width="180">
          <template #default="{ row }">
            {{ row.email || '-' }}
          </template>
        </el-table-column>
        <el-table-column prop="role" label="角色" width="120">
          <template #default="{ row }">
            <el-tag :type="row.role === 'admin' ? 'danger' : 'info'" size="small">
              {{ row.role === 'admin' ? '管理员' : '普通用户' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="注册时间" width="180">
          <template #default="{ row }">
            {{ formatDate(row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button
              v-if="row.user_id !== authStore.user?.user_id"
              :type="row.role === 'admin' ? 'warning' : 'primary'"
              size="small"
              :loading="changingRole === row.user_id"
              @click="toggleRole(row)"
            >
              {{ row.role === 'admin' ? '降为普通用户' : '设为管理员' }}
            </el-button>
            <el-popconfirm
              v-if="row.user_id !== authStore.user?.user_id"
              title="确定删除该用户？"
              confirm-button-text="删除"
              @confirm="handleDelete(row)"
            >
              <template #reference>
                <el-button type="danger" size="small" :loading="deleting === row.user_id">
                  删除
                </el-button>
              </template>
            </el-popconfirm>
            <span v-if="row.user_id === authStore.user?.user_id" class="self-tag">当前用户</span>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useAuthStore } from '@/stores/authStore'
import { authApi } from '@/api/auth'
import type { UserInfo } from '@/api/auth'
import { ElMessage } from 'element-plus'

const authStore = useAuthStore()
const users = ref<UserInfo[]>([])
const loading = ref(false)
const changingRole = ref('')
const deleting = ref('')

function formatDate(dateStr?: string) {
  if (!dateStr) return '-'
  try {
    return dateStr.slice(0, 19).replace('T', ' ')
  } catch {
    return dateStr
  }
}

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
  padding: 0;
}

.page-header {
  display: flex;
  align-items: baseline;
  gap: 12px;
  margin-bottom: 20px;
}

.page-header h2 {
  margin: 0;
  font-size: 20px;
  font-weight: 600;
  color: var(--text-primary);
}

.page-desc {
  font-size: 13px;
  color: var(--text-muted);
}

.table-card {
  border-radius: var(--radius-md);
}

.self-tag {
  font-size: 12px;
  color: var(--text-muted);
  padding: 0 8px;
}
</style>
