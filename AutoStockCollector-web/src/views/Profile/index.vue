<template>
  <div class="profile-page">
    <div class="page-header">
      <h2 class="page-title">个人中心</h2>
      <p class="page-subtitle">管理您的账户信息与安全设置</p>
    </div>

    <ProfileHeader />

    <div class="profile-grid">
      <div class="grid-col">
        <BasicInfo />
      </div>
      <div class="grid-col">
        <SecuritySetting />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import ProfileHeader from './components/ProfileHeader.vue'
import BasicInfo from './components/BasicInfo.vue'
import SecuritySetting from './components/SecuritySetting.vue'
</script>

<style scoped>
.profile-page {
  max-width: 1000px;
  margin: 0 auto;
  padding-bottom: 10px;
}

.page-header {
  margin-bottom: 16px;
}

.page-title {
  margin: 0 0 4px;
  font-size: 20px;
  font-weight: 700;
  color: var(--text-primary);
  letter-spacing: -0.5px;
}

.page-subtitle {
  margin: 0;
  font-size: 13px;
  color: var(--text-muted);
}

.profile-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
  align-items: stretch;
}

@media (max-width: 860px) {
  .profile-grid {
    grid-template-columns: 1fr;
  }
}
</style>
