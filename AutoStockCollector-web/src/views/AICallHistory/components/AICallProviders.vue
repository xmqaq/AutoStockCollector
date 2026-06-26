<template>
  <div class="provider-row" v-if="providerStats.length">
    <el-card v-for="p in providerStats" :key="p.name" shadow="never" class="provider-card" :class="'pc-' + colorIdx(p.name)">
      <div class="pc-header">
        <span class="pc-name">{{ p.name }}</span>
        <el-tag size="small" :type="p.fail === 0 ? 'success' : 'danger'" effect="light">{{ p.count }}</el-tag>
      </div>
      <el-progress :percentage="p.rate" :stroke-width="6" :color="p.rate >= 80 ? 'var(--el-color-success)' : p.rate >= 50 ? 'var(--el-color-warning)' : 'var(--el-color-danger)'" />
      <div class="pc-detail">{{ p.success }}/{{ p.count }} 成功</div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  providerStats: any[]
}>()

function colorIdx(name: string) {
  const colors = ['blue', 'green', 'orange', 'purple', 'cyan', 'pink']
  let h = 0
  for (const c of name) h = (h * 31 + c.charCodeAt(0)) % colors.length
  return colors[h]
}
</script>

<style scoped>
.provider-row { display: flex; gap: 10px; margin-bottom: 16px; flex-wrap: wrap; }
.provider-card { flex: 1; min-width: 130px; padding: 4px; }
.pc-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px; }
.pc-name { font-weight: 600; font-size: 13px; }
.pc-detail { font-size: 10px; color: var(--text-muted); margin-top: 2px; }
.pc-blue .pc-name { color: #409eff; }
.pc-green .pc-name { color: var(--el-color-success); }
.pc-orange .pc-name { color: var(--el-color-warning); }
.pc-purple .pc-name { color: #9b59b6; }
.pc-cyan .pc-name { color: #00bcd4; }
.pc-pink .pc-name { color: #e91e63; }
</style>
