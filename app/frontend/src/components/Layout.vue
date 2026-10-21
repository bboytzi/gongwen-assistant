<template>
  <el-container style="height: 100vh">
    <el-header style="background: #fff; border-bottom: 1px solid #e4e4e7; display: flex; align-items: center; justify-content: space-between;">
      <div style="display: flex; align-items: center; gap: 32px;">
        <span style="font-weight: 600; font-size: 16px; color: #1f1f1f;">天府数产公文辅助系统</span>
        <el-input
          v-model="searchQuery"
          placeholder="搜索材料、办法、案例..."
          style="width: 320px;"
          @keyup.enter="handleSearch"
        >
          <template #prefix>
            <el-icon><Search /></el-icon>
          </template>
        </el-input>
      </div>
      <div style="display: flex; align-items: center; gap: 16px;">
        <el-dropdown>
          <span style="display: flex; align-items: center; gap: 8px; cursor: pointer;">
            <el-avatar size="small" style="background: #534ab7;">{{ userStore.user?.username?.[0]?.toUpperCase() }}</el-avatar>
            <span style="font-size: 13px;">{{ userStore.user?.username }}</span>
          </span>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item @click="$router.push('/settings')">设置</el-dropdown-item>
              <el-dropdown-item divided @click="handleLogout">退出登录</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </div>
    </el-header>
    <el-container>
      <el-aside width="200px" style="background: #fff; border-right: 1px solid #e4e4e7;">
        <el-menu
          :default-active="$route.path"
          router
          style="border-right: none; padding-top: 8px;"
        >
          <el-menu-item index="/">
            <el-icon><HomeFilled /></el-icon>
            <span>首页</span>
          </el-menu-item>
          <el-menu-item index="/documents/new">
            <el-icon><EditPen /></el-icon>
            <span>新建请示</span>
          </el-menu-item>
          <el-menu-item index="/search">
            <el-icon><Search /></el-icon>
            <span>检索中心</span>
          </el-menu-item>
          <el-menu-item index="/knowledge">
            <el-icon><FolderOpened /></el-icon>
            <span>知识库</span>
          </el-menu-item>
          <el-menu-item index="/settings">
            <el-icon><Setting /></el-icon>
            <span>设置</span>
          </el-menu-item>
        </el-menu>
      </el-aside>
      <el-main style="background: #f5f5f5; padding: 0;">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useUserStore } from '../store/user'

const router = useRouter()
const userStore = useUserStore()
const searchQuery = ref('')

onMounted(async () => {
  await userStore.fetchMe()
})

function handleSearch() {
  if (searchQuery.value.trim()) {
    router.push({ path: '/search', query: { q: searchQuery.value } })
  }
}

function handleLogout() {
  userStore.logout()
  router.push('/login')
}
</script>
