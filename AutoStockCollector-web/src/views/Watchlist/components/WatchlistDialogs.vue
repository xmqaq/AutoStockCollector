<template>
  <div>
    <!-- 添加自选 -->
    <el-dialog :model-value="showAddModal" @update:model-value="$emit('update:showAddModal', $event)" title="添加自选股" width="400px" custom-class="wl-dialog">
      <el-form :model="addForm" label-width="80px" class="dialog-form">
        <el-form-item label="股票代码">
          <StockSearch v-model="addForm.code" @search="(c) => addForm.code = c" />
        </el-form-item>
        <el-form-item label="所属分组">
          <el-select v-model="addForm.group_id" placeholder="选择分组" clearable class="full-width">
            <el-option v-for="g in groups" :key="g.group_id" :label="g.name || g.group_id" :value="g.group_id" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <div class="dialog-footer">
          <el-button @click="$emit('update:showAddModal', false)" round>取消</el-button>
          <el-button type="primary" @click="$emit('submit-add')" :loading="addLoading" round>确认添加</el-button>
        </div>
      </template>
    </el-dialog>

    <!-- 分组管理 -->
    <el-dialog :model-value="showGroupDialog" @update:model-value="$emit('update:showGroupDialog', $event)" title="新建分组" width="360px" custom-class="wl-dialog">
      <el-form :model="groupForm" label-width="70px" class="dialog-form">
        <el-form-item label="分组标识">
          <el-input v-model="groupForm.group_id" placeholder="英文/数字，如 'tech'" />
        </el-form-item>
        <el-form-item label="分组名称">
          <el-input v-model="groupForm.name" placeholder="显示名称，如 '科技股'" />
        </el-form-item>
        <el-form-item label="分组描述">
          <el-input v-model="groupForm.description" placeholder="选填，备注信息" type="textarea" :rows="2" resize="none" />
        </el-form-item>
      </el-form>
      <template #footer>
        <div class="dialog-footer">
          <el-button @click="$emit('update:showGroupDialog', false)" round>取消</el-button>
          <el-button type="primary" @click="$emit('submit-group')" :loading="groupLoading" round>创建分组</el-button>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import StockSearch from '@/components/StockSearch/index.vue'
import type { WatchlistGroup } from '@/api/watchlist'

defineProps<{
  showAddModal: boolean
  showGroupDialog: boolean
  addLoading: boolean
  groupLoading: boolean
  groups: WatchlistGroup[]
  addForm: { code: string; group_id: string }
  groupForm: { group_id: string; name: string; description: string }
}>()

defineEmits<{
  (e: 'update:showAddModal', val: boolean): void
  (e: 'update:showGroupDialog', val: boolean): void
  (e: 'submit-add'): void
  (e: 'submit-group'): void
}>()
</script>

<style scoped>
.full-width {
  width: 100%;
}
.dialog-form {
  padding: 10px 0;
}
</style>
<style>
/* 针对 el-dialog 的全局样式重写（加前缀防污染） */
.wl-dialog {
  border-radius: 12px;
  overflow: hidden;
}
</style>