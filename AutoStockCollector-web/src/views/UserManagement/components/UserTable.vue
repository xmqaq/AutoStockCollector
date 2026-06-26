<template>
  <el-card shadow="never" class="pro-card">
    <template #header>
      <div class="card-header">
        <span class="card-title">用户列表</span>
      </div>
    </template>
    
    <el-table 
      :data="users" 
      v-loading="loading" 
      size="large"
      class="pro-table"
      :header-cell-style="{ 
        background: '#f4f6f8', 
        color: '#4c4e54', 
        fontWeight: 600, 
        fontSize: '15px',
        borderBottom: '1px solid #ebeef5',
        padding: '16px 0',
        textAlign: 'center'
      }"
      :cell-style="{ textAlign: 'center' }"
      :row-style="{ height: '72px' }"
      style="width: 100%"
    >
      <el-table-column label="用户" min-width="260" align="left" header-align="center">
        <template #default="{ row }">
          <div class="user-cell">
            <div class="user-avatar" :class="getAvatarColor(row.username)">
              {{ row.username.charAt(0).toUpperCase() }}
            </div>
            <div class="user-info">
              <span class="user-name">{{ row.username }}</span>
              <span class="user-id">ID: {{ row.user_id }}</span>
            </div>
          </div>
        </template>
      </el-table-column>
      
      <el-table-column prop="email" label="邮箱" min-width="160" align="left" header-align="center">
        <template #default="{ row }">
          <div class="email-cell-content">
            <span class="email-text">{{ row.email || '未绑定邮箱' }}</span>
          </div>
        </template>
      </el-table-column>
      
      <el-table-column prop="role" label="系统角色" width="200">
        <template #default="{ row }">
          <div class="cell-content">
            <div class="role-badge" :class="row.role === 'admin' ? 'role-admin' : 'role-user'">
              <el-icon v-if="row.role === 'admin'"><Avatar /></el-icon>
              <el-icon v-else><User /></el-icon>
              {{ row.role === 'admin' ? '系统管理员' : '普通用户' }}
            </div>
          </div>
        </template>
      </el-table-column>
      
      <el-table-column label="注册时间" width="240">
        <template #default="{ row }">
          <div class="cell-content">
            <span class="time-text">{{ formatDate(row.created_at) }}</span>
          </div>
        </template>
      </el-table-column>
      
      <el-table-column label="操作" width="220" fixed="right">
        <template #default="{ row }">
          <div class="action-cell">
            <template v-if="row.user_id !== authStore.user?.user_id">
              <el-button
                :type="row.role === 'admin' ? 'warning' : 'primary'"
                size="small"
                plain
                :loading="changingRole === row.user_id"
                @click="$emit('toggle-role', row)"
              >
                {{ row.role === 'admin' ? '降级权限' : '设为管理' }}
              </el-button>
              
              <el-popconfirm
                title="警告：此操作将永久删除该用户，是否继续？"
                confirm-button-text="确认删除"
                confirm-button-type="danger"
                cancel-button-text="取消"
                width="280"
                @confirm="$emit('delete', row)"
              >
                <template #reference>
                  <el-button type="danger" size="small" plain :loading="deleting === row.user_id">
                    删除
                  </el-button>
                </template>
              </el-popconfirm>
            </template>
            
            <div v-else class="self-indicator">
              <span class="self-dot"></span> 当前账号
            </div>
          </div>
        </template>
      </el-table-column>
      
      <template #empty>
        <el-empty description="暂无用户数据" :image-size="80" />
      </template>
    </el-table>
  </el-card>
</template>

<script setup lang="ts">
import { User, Avatar } from '@element-plus/icons-vue'
import { useAuthStore } from '@/stores/authStore'
import type { UserInfo } from '@/api/auth'

const authStore = useAuthStore()

defineProps<{
  users: UserInfo[]
  loading: boolean
  changingRole: string
  deleting: string
}>()

defineEmits<{
  (e: 'toggle-role', row: UserInfo): void
  (e: 'delete', row: UserInfo): void
}>()

function formatDate(dateStr?: string) {
  if (!dateStr) return '-'
  try {
    const d = new Date(dateStr)
    if (isNaN(d.getTime())) return dateStr.slice(0, 10)
    const year = d.getFullYear()
    const month = String(d.getMonth() + 1).padStart(2, '0')
    const day = String(d.getDate()).padStart(2, '0')
    return `${year}年${month}月${day}日`
  } catch {
    return dateStr
  }
}

// 根据用户名生成固定的头像颜色
function getAvatarColor(username: string) {
  const colors = ['bg-blue', 'bg-green', 'bg-orange', 'bg-purple', 'bg-pink']
  let hash = 0
  for (let i = 0; i < username.length; i++) {
    hash = username.charCodeAt(i) + ((hash << 5) - hash)
  }
  return colors[Math.abs(hash) % colors.length]
}
</script>

<style scoped>
.pro-card {
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: 12px;
  box-shadow: 0 2px 12px 0 rgba(0, 0, 0, 0.05);
}

.pro-card :deep(.el-card__header) {
  border-bottom: 1px solid #ebeef5;
  padding: 18px 24px;
  background-color: var(--bg-card);
  border-radius: 12px 12px 0 0;
}

.pro-card :deep(.el-card__body) {
  padding: 0;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.card-title {
  color: var(--text-primary);
  font-size: 16px;
  font-weight: 600;
  display: flex;
  align-items: center;
}

.card-title::before {
  content: '';
  display: inline-block;
  width: 4px;
  height: 16px;
  background: var(--el-color-primary);
  border-radius: 2px;
  margin-right: 8px;
}

.pro-table {
  --el-table-border-color: var(--border-color);
  --el-table-row-hover-bg-color: #f5f7fa;
}

.pro-table :deep(.el-table__row) {
  transition: background-color 0.2s ease;
}

.pro-table :deep(.el-table__cell) {
  padding: 8px 0;
  vertical-align: middle;
}

/* User Cell */
.user-cell {
  display: flex;
  align-items: center;
  justify-content: flex-start;
  padding-left: 2em;
  gap: 16px;
  height: 100%;
}

.user-avatar {
  width: 40px;
  height: 40px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  font-size: 18px;
  font-weight: bold;
  flex-shrink: 0;
  box-shadow: 0 4px 10px rgba(0,0,0,0.08);
}

.bg-blue { background: linear-gradient(135deg, #36a3f7, #2080e6); }
.bg-green { background: linear-gradient(135deg, var(--el-color-success), #5daf34); }
.bg-orange { background: linear-gradient(135deg, var(--el-color-warning), #cf9236); }
.bg-purple { background: linear-gradient(135deg, #b37feb, #9961db); }
.bg-pink { background: linear-gradient(135deg, var(--el-color-danger), #dd6161); }

.user-info {
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 4px;
}

.email-cell-content {
  display: flex;
  align-items: center;
  justify-content: flex-start;
  padding-left: 2em;
  height: 100%;
}

.cell-content {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
}

.user-name {
  font-weight: 600;
  font-size: 15px;
  color: var(--text-primary);
}

.user-id {
  font-size: 13px;
  color: var(--text-muted);
  font-family: "SF Pro Display", "Roboto", "Helvetica Neue", sans-serif;
}

/* Email & Time */
.email-text {
  color: var(--text-secondary);
  font-size: 14px;
}

.time-text {
  color: var(--text-secondary);
  font-family: "SF Pro Display", "Roboto", "Helvetica Neue", sans-serif;
  font-size: 14px;
}

/* Role Badge */
.role-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  border-radius: 8px;
  font-size: 13px;
  font-weight: 600;
  letter-spacing: 0.5px;
}

.role-admin {
  background: #fef0f0;
  color: var(--el-color-danger);
  border: 1px solid #fde2e2;
}

.role-user {
  background: #f4f4f5;
  color: var(--text-muted);
  border: 1px solid #e9e9eb;
}

/* Actions */
.action-cell {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
}

.action-cell :deep(.el-button) {
  border-radius: 6px;
  padding: 8px 16px;
  font-weight: 500;
}

.self-indicator {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 6px 16px;
  background: #ecf5ff;
  color: #409eff;
  border-radius: 20px;
  font-size: 13px;
  font-weight: 600;
  border: 1px solid #d9ecff;
}

.self-dot {
  width: 6px;
  height: 6px;
  background-color: #409eff;
  border-radius: 50%;
  box-shadow: 0 0 6px rgba(64, 158, 255, 0.6);
}

/* 覆盖特定列的表头样式以匹配内容对齐 */
.pro-table :deep(th.el-table__cell:nth-child(1) .cell),
.pro-table :deep(th.el-table__cell:nth-child(2) .cell) {
  padding-left: 0;
}
</style>