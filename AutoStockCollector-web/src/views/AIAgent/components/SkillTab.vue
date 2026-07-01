<template>
  <div class="skill-tab">
    <!-- 顶部操作与过滤区 -->
    <div class="filter-bar">
      <div class="left-actions">
        <el-input
          v-model="searchQuery"
          placeholder="搜索技能名称或描述..."
          clearable
          class="search-input"
          :prefix-icon="Search"
        />
        <el-select v-model="categoryFilter" placeholder="全部分类" clearable class="category-select">
          <el-option label="全部分类" value="" />
          <el-option v-for="cat in categories" :key="cat" :label="cat" :value="cat" />
        </el-select>
      </div>
      <div class="right-actions">
        <el-button type="primary" @click="loadSkills" :loading="skillsLoading">
          <el-icon><Refresh /></el-icon> 刷新技能
        </el-button>
      </div>
    </div>

    <!-- 技能列表区 -->
    <div v-loading="skillsLoading" class="skill-content">
      <el-empty v-if="filteredSkills.length === 0 && !skillsLoading" description="暂无匹配技能" />
      
      <div v-else class="skill-grid">
        <div
          v-for="s in filteredSkills"
          :key="s.name"
          class="skill-card"
          @click="showSkill(s.skill_name || s.name)"
        >
          <div class="card-top">
            <div class="skill-icon">
              <el-icon><MagicStick /></el-icon>
            </div>
            <div class="skill-name">{{ s.name }}</div>
          </div>
          <div class="skill-desc" :title="s.description">{{ s.description || '暂无描述' }}</div>
          <div class="skill-meta">
            <el-tag size="small" type="info" effect="plain" class="cat-tag">{{ s.category || '未分类' }}</el-tag>
            <span v-if="s.tools" class="skill-tools" :title="s.tools">
              <el-icon><Setting /></el-icon> {{ s.tools }}
            </span>
          </div>
        </div>
      </div>
    </div>

    <!-- 技能详情抽屉 -->
    <el-drawer
      v-model="showSkillDetail"
      title="技能详情 (SKILL.md)"
      size="600px"
      direction="rtl"
      destroy-on-close
    >
      <div class="skill-drawer-content" v-loading="detailLoading">
        <template v-if="skillDetail">
          <div class="drawer-header">
            <h3>{{ skillDetail.name }}</h3>
            <div class="bound-agents" v-if="boundAgents.length">
              <span class="bound-label">被以下 Agent 绑定：</span>
              <el-tag v-for="a in boundAgents" :key="a" size="small" type="success" effect="plain" class="bound-tag">{{ a }}</el-tag>
            </div>
            <div class="bound-agents" v-else>
              <span class="bound-label muted">暂未被任何 Agent 绑定</span>
            </div>
          </div>
          <div class="drawer-body">
            <div class="code-block-wrapper">
              <div class="code-header">
                <span>Definition</span>
                <el-button size="small" link @click="copyCode(skillDetail.content)">
                  <el-icon><DocumentCopy /></el-icon>
                </el-button>
              </div>
              <pre class="skill-code">{{ skillDetail.content }}</pre>
            </div>
          </div>
        </template>
      </div>
    </el-drawer>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { Search, Refresh, MagicStick, Setting, DocumentCopy } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { skillApi, aiAgentApi } from '@/api/ai'

const skills = ref<any[]>([])
const skillsLoading = ref(false)
const agents = ref<any[]>([])

const searchQuery = ref('')
const categoryFilter = ref('')

const showSkillDetail = ref(false)
const detailLoading = ref(false)
const skillDetail = ref<{ name: string; content: string } | null>(null)
const boundAgents = ref<string[]>([])

// 提取所有唯一分类
const categories = computed(() => {
  const cats = new Set<string>()
  skills.value.forEach(s => {
    if (s.category) cats.add(s.category)
  })
  return Array.from(cats)
})

// 过滤后的技能列表
const filteredSkills = computed(() => {
  return skills.value.filter(s => {
    const matchQuery = !searchQuery.value || 
      s.name.toLowerCase().includes(searchQuery.value.toLowerCase()) || 
      (s.description && s.description.toLowerCase().includes(searchQuery.value.toLowerCase()))
    
    const matchCat = !categoryFilter.value || s.category === categoryFilter.value
    
    return matchQuery && matchCat
  })
})

async function loadSkills() {
  skillsLoading.value = true
  try {
    const res = await skillApi.list()
    skills.value = res.data?.data || res.data || []
  } catch {
    skills.value = []
  } finally {
    skillsLoading.value = false
  }
}

async function loadAgents() {
  try {
    const res = await aiAgentApi.list()
    agents.value = res.data?.data || []
  } catch {
    agents.value = []
  }
}

async function showSkill(name: string) {
  showSkillDetail.value = true
  detailLoading.value = true
  skillDetail.value = null
  boundAgents.value = []
  try {
    const res = await skillApi.get(name)
    skillDetail.value = res.data?.data || null
    // 反查：哪些 agent 绑定了该 skill（按 skill_name 目录名匹配）
    boundAgents.value = agents.value
      .filter(a => Array.isArray(a.skills) && (a.skills.includes(name) || a.skills.includes(skillDetail.value?.name)))
      .map(a => a.name)
  } catch {
    ElMessage.error('获取技能详情失败')
  } finally {
    detailLoading.value = false
  }
}

function copyCode(text: string) {
  navigator.clipboard.writeText(text).then(() => {
    ElMessage.success('已复制到剪贴板')
  }).catch(() => {
    ElMessage.error('复制失败')
  })
}

onMounted(() => {
  loadSkills()
  loadAgents()
})
</script>

<style scoped>
.skill-tab {
  display: flex;
  flex-direction: column;
  gap: 20px;
  height: 100%;
}

.filter-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: var(--bg-card);
  padding: 16px;
  border-radius: 12px;
  border: 1px solid var(--border-color);
}

.left-actions {
  display: flex;
  gap: 12px;
}

.search-input {
  width: 280px;
}

.category-select {
  width: 160px;
}

.skill-content {
  flex: 1;
}

.skill-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 16px;
}

.skill-card {
  background: var(--bg-card);
  border-radius: 12px;
  padding: 20px;
  border: 1px solid var(--border-color);
  cursor: pointer;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.skill-card:hover {
  border-color: var(--el-color-primary-light-5);
  transform: translateY(-2px);
  box-shadow: 0 6px 16px var(--bg-hover-subtle);
}

.card-top {
  display: flex;
  align-items: center;
  gap: 12px;
}

.skill-icon {
  width: 36px;
  height: 36px;
  border-radius: 8px;
  background: var(--el-color-primary-light-9);
  color: var(--el-color-primary);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 20px;
}

.skill-name {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
}

.skill-desc {
  font-size: 13px;
  color: var(--text-secondary);
  line-height: 1.5;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  flex: 1;
  min-height: 39px;
}

.skill-meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: auto;
  padding-top: 12px;
  border-top: 1px dashed var(--border-color);
}

.cat-tag {
  border-radius: 4px;
}

.skill-tools {
  font-size: 12px;
  color: var(--text-muted);
  display: flex;
  align-items: center;
  gap: 4px;
  max-width: 150px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* 抽屉样式 */
.skill-drawer-content {
  display: flex;
  flex-direction: column;
  height: 100%;
  padding: 0 20px 20px;
}

.drawer-header h3 {
  margin: 0 0 12px 0;
  font-size: 20px;
  color: var(--text-primary);
}

.bound-agents {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
  margin-bottom: 8px;
}

.bound-label {
  font-size: 13px;
  color: var(--text-secondary);
}

.bound-label.muted {
  color: var(--text-muted);
  font-size: 12px;
}

.bound-tag {
  border-radius: 4px;
}

.drawer-body {
  flex: 1;
  display: flex;
  flex-direction: column;
}

.code-block-wrapper {
  background: var(--bg-deep);
  border-radius: 8px;
  display: flex;
  flex-direction: column;
  flex: 1;
  overflow: hidden;
}

.code-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 16px;
  background: #2d2d2d;
  color: #a0a0a0;
  font-size: 12px;
  font-family: monospace;
}

.code-header .el-button {
  color: #a0a0a0;
}
.code-header .el-button:hover {
  color: #fff;
}

.skill-code {
  margin: 0;
  padding: 16px;
  font-size: 13px;
  line-height: 1.6;
  color: #d4d4d4;
  font-family: 'SF Mono', Consolas, Menlo, monospace;
  overflow-y: auto;
  flex: 1;
}
</style>
