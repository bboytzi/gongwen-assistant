<template>
  <div class="shell">
    <header class="topbar">
      <Logo :size="26" />
      <span class="brand">{{ system.name }}</span>

      <div class="search">
        <el-icon class="search-icon"><Search /></el-icon>
        <input
          ref="searchRef"
          v-model="keyword"
          class="search-input"
          placeholder="搜索材料、办法、案例"
          @keyup.enter="handleSearch"
        />
        <span class="search-kbd">Ctrl K</span>
      </div>

      <div class="topbar-right">
        <el-dropdown trigger="click">
          <div class="user">
            <div class="avatar">{{ initial }}</div>
            <span class="user-name">{{ userStore.shownName || '-' }}</span>
            <el-icon class="caret"><ArrowDown /></el-icon>
          </div>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item @click="$router.push('/profile')">个人资料</el-dropdown-item>
              <el-dropdown-item v-if="isAdmin" @click="$router.push('/users')">用户管理</el-dropdown-item>
              <el-dropdown-item divided @click="handleLogout">退出登录</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </div>
    </header>

    <div class="body">
      <aside class="sidebar">
        <div class="nav-group">工作台</div>
        <el-menu :default-active="activeMenu" router>
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
        </el-menu>

        <div class="nav-group">资源</div>
        <el-menu :default-active="activeMenu" router>
          <el-menu-item index="/knowledge">
            <el-icon><FolderOpened /></el-icon>
            <span>知识库</span>
          </el-menu-item>
          <el-menu-item v-if="isAdmin" index="/users">
            <el-icon><User /></el-icon>
            <span>用户管理</span>
          </el-menu-item>
          <el-menu-item index="/settings">
            <el-icon><Setting /></el-icon>
            <span>设置</span>
          </el-menu-item>
        </el-menu>
      </aside>

      <main class="main">
        <router-view />
      </main>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useUserStore } from '../store/user'
import { useSystemStore } from '../store/system'
import Logo from './Logo.vue'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()
const system = useSystemStore()

const keyword = ref('')
const searchRef = ref(null)

const initial = computed(() =>
  (userStore.shownName || 'A').charAt(0).toUpperCase()
)

const isAdmin = computed(() => userStore.user?.role === 'admin')

// 详情页高亮对应的列表项
const activeMenu = computed(() => {
  const p = route.path
  if (p.startsWith('/documents')) {
    return p === '/documents/new' ? '/documents/new' : '/'
  }
  return p
})

onMounted(async () => {
  await userStore.fetchMe()
  window.addEventListener('keydown', onKeydown)
})

onUnmounted(() => {
  window.removeEventListener('keydown', onKeydown)
})

function onKeydown(e) {
  if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
    e.preventDefault()
    searchRef.value?.focus()
  }
}

function handleSearch() {
  const q = keyword.value.trim()
  if (!q) return
  router.push({ path: '/search', query: { q } })
}

function handleLogout() {
  userStore.logout()
  router.push('/login')
}
</script>

<style scoped>
.shell {
  height: 100vh;
  display: flex;
  flex-direction: column;
  background: var(--paper);
}

.topbar {
  height: 54px;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  gap: 11px;
  padding: 0 22px;
  background: var(--paper-2);
  border-bottom: 1.5px solid var(--gold);
}

.brand {
  font-family: var(--font-serif);
  font-size: 15px;
  font-weight: 500;
  color: var(--ink);
  letter-spacing: 1px;
  white-space: nowrap;
}

.search {
  display: flex;
  align-items: center;
  gap: 7px;
  margin-left: 26px;
  width: 268px;
  height: 30px;
  padding: 0 10px;
  background: var(--paper-3);
  border: 0.5px solid var(--line);
  border-radius: var(--r-sm);
}

.search:focus-within {
  border-color: var(--gold-line);
}

.search-icon {
  font-size: 13px;
  color: var(--ink-4);
}

.search-input {
  flex: 1;
  min-width: 0;
  border: none;
  outline: none;
  background: transparent;
  font-family: inherit;
  font-size: 12px;
  color: var(--ink);
}

.search-input::placeholder {
  color: var(--ink-4);
}

.search-kbd {
  font-size: 10px;
  color: var(--ink-4);
  white-space: nowrap;
}

.topbar-right {
  margin-left: auto;
}

.user {
  display: flex;
  align-items: center;
  gap: 7px;
  cursor: pointer;
  padding: 4px 6px;
  border-radius: var(--r-sm);
}

.user:hover {
  background: var(--paper-3);
}

.avatar {
  width: 26px;
  height: 26px;
  border-radius: 50%;
  background: var(--seal-soft);
  color: var(--seal);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  font-weight: 500;
}

.user-name {
  font-size: 12px;
  color: var(--ink-2);
}

.caret {
  font-size: 11px;
  color: var(--ink-4);
}

.body {
  flex: 1;
  display: flex;
  min-height: 0;
}

.sidebar {
  width: 176px;
  flex-shrink: 0;
  background: var(--paper);
  border-right: 0.5px solid var(--line);
  padding-top: 12px;
  display: flex;
  flex-direction: column;
  overflow-y: auto;
}

.nav-group {
  padding: 12px 22px 6px;
  font-size: 11px;
  color: var(--ink-4);
  letter-spacing: 1px;
}

.main {
  flex: 1;
  min-width: 0;
  overflow-y: auto;
  background: var(--paper);
}
</style>
