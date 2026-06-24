<template>
  <div class="wl-sidebar">
    <div class="wl-sidebar-header">
      <span>分组管理</span>
      <el-button size="small" circle @click="$emit('add-group')">
        <el-icon><Plus /></el-icon>
      </el-button>
    </div>
    <el-menu :default-active="activeGroup" @select="$emit('update:activeGroup', $event)" class="wl-group-menu">
      <el-menu-item index="__all__">
        <el-icon><FolderOpened /></el-icon>
        <span>全部 ({{ totalCount }})</span>
      </el-menu-item>
      <el-menu-item v-for="g in groups" :key="g.group_id" :index="g.group_id">
        <el-icon><Folder /></el-icon>
        <span>{{ g.name || g.group_id }} ({{ g.stock_count }})</span>
        <el-button v-if="g.group_id !== 'default'" size="small" text type="danger"
          class="wl-del-group" @click.stop="$emit('delete-group', g.group_id)">
          <el-icon><Delete /></el-icon>
        </el-button>
      </el-menu-item>
    </el-menu>
  </div>
</template>

<script setup lang="ts">
import { Plus, Delete, FolderOpened, Folder } from '@element-plus/icons-vue'
import type { WatchlistGroup } from '@/api/watchlist'

defineProps<{
  groups: WatchlistGroup[]
  activeGroup: string
  totalCount: number
}>()

defineEmits<{
  (e: 'update:activeGroup', val: string): void
  (e: 'add-group'): void
  (e: 'delete-group', groupId: string): void
}>()
</script>

<style scoped>
.wl-sidebar { 
  width: 240px; 
  flex-shrink: 0; 
  background: var(--el-bg-color); 
  border-radius: 12px; 
  border: none;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.04);
  overflow: hidden; 
}
.wl-sidebar-header { 
  display: flex; 
  align-items: center; 
  justify-content: space-between; 
  padding: 16px 20px; 
  border-bottom: 1px solid var(--el-border-color-lighter); 
  font-weight: 600; 
  font-size: 15px; 
  color: var(--el-text-color-primary);
}
.wl-group-menu { 
  border-right: none; 
}
.wl-del-group { 
  margin-left: auto; 
  opacity: 0; 
  transition: opacity 0.2s;
}
.el-menu-item:hover .wl-del-group { 
  opacity: 1; 
}
</style>
