<template>
  <div class="login-wrap">
    <div class="login-card">
      <div class="brand">
        <Logo :size="52" />
        <div class="brand-name">{{ system.name }}</div>
        <div class="brand-sub">{{ system.subtitle }}</div>
      </div>

      <div class="tabs">
        <span
          class="tab"
          :class="{ active: activeTab === 'login' }"
          @click="activeTab = 'login'"
        >登录</span>
        <span
          class="tab"
          :class="{ active: activeTab === 'register' }"
          @click="activeTab = 'register'"
        >注册</span>
      </div>

      <div v-if="activeTab === 'login'" class="form">
        <div class="field">
          <label>登录名</label>
          <el-input v-model="loginForm.username" placeholder="英文登录名" @keyup.enter="handleLogin" />
        </div>
        <div class="field">
          <label>密码</label>
          <el-input
            v-model="loginForm.password"
            type="password"
            show-password
            placeholder="请输入密码"
            @keyup.enter="handleLogin"
          />
        </div>
        <el-button type="primary" class="submit" :loading="loading" @click="handleLogin">
          登 录
        </el-button>
      </div>

      <div v-else class="form">
        <div class="field">
          <label>登录名 <span class="opt">英文</span></label>
          <el-input v-model="regForm.username" placeholder="zhangsan" />
        </div>
        <div class="field">
          <label>显示名 <span class="opt">中文</span></label>
          <el-input v-model="regForm.display_name" placeholder="张三" />
        </div>
        <div class="field">
          <label>密码</label>
          <el-input v-model="regForm.password" type="password" show-password placeholder="至少 6 位" />
        </div>
        <div class="field">
          <label>部门</label>
          <el-input v-model="regForm.department" placeholder="选填" />
        </div>
        <el-button type="primary" class="submit" :loading="loading" @click="handleRegister">
          注 册
        </el-button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useUserStore } from '../store/user'
import { useSystemStore } from '../store/system'
import Logo from '../components/Logo.vue'

const router = useRouter()
const userStore = useUserStore()
const system = useSystemStore()

const activeTab = ref('login')
const loading = ref(false)
const loginForm = ref({ username: '', password: '' })
const regForm = ref({ username: '', display_name: '', password: '', department: '' })

async function handleLogin() {
  if (!loginForm.value.username || !loginForm.value.password) {
    ElMessage.warning('请输入用户名和密码')
    return
  }
  loading.value = true
  try {
    await userStore.login(loginForm.value.username, loginForm.value.password)
    router.push('/')
  } catch {
    // 拦截器已提示
  } finally {
    loading.value = false
  }
}

async function handleRegister() {
  if (!regForm.value.username || !regForm.value.password) {
    ElMessage.warning('请填写登录名和密码')
    return
  }
  if (!/^[A-Za-z0-9_.-]+$/.test(regForm.value.username.trim())) {
    ElMessage.warning('登录名只能包含字母、数字、下划线、点和短横线')
    return
  }
  if (regForm.value.password.length < 6) {
    ElMessage.warning('密码至少 6 位')
    return
  }
  loading.value = true
  try {
    await userStore.register(
      regForm.value.username.trim(),
      regForm.value.password,
      regForm.value.display_name.trim() || null,
      regForm.value.department
    )
    ElMessage.success('注册成功')
    router.push('/')
  } catch {
    // 拦截器已提示
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-wrap {
  height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--paper);
  position: relative;
}

.login-wrap::before {
  content: "";
  position: absolute;
  inset: 0;
  background-image:
    linear-gradient(var(--line-2) 1px, transparent 1px),
    linear-gradient(90deg, var(--line-2) 1px, transparent 1px);
  background-size: 44px 44px;
  opacity: 0.45;
  pointer-events: none;
}

.login-card {
  position: relative;
  width: 372px;
  background: var(--card);
  border: 0.5px solid var(--line);
  border-radius: var(--r-lg);
  padding: 34px 34px 22px;
}

.brand {
  text-align: center;
  padding-bottom: 22px;
  border-bottom: 1px solid var(--line);
  margin-bottom: 20px;
  display: flex;
  flex-direction: column;
  align-items: center;
}

.brand-name {
  font-family: var(--font-serif);
  font-size: 17px;
  font-weight: 500;
  color: var(--ink);
  letter-spacing: 1.5px;
  margin-top: 13px;
}

.brand-sub {
  font-size: 11px;
  color: var(--ink-4);
  margin-top: 6px;
  letter-spacing: 0.5px;
}

.tabs {
  display: flex;
  gap: 24px;
  margin-bottom: 18px;
}

.tab {
  font-size: 13px;
  color: var(--ink-3);
  cursor: pointer;
  padding-bottom: 6px;
  border-bottom: 1.5px solid transparent;
}

.tab.active {
  color: var(--seal);
  border-bottom-color: var(--seal);
}

.field {
  margin-bottom: 13px;
}

.field label {
  display: block;
  font-size: 11px;
  color: var(--ink-3);
  margin-bottom: 5px;
}

.opt {
  color: var(--ink-4);
}

.submit {
  width: 100%;
  height: 36px;
  margin-top: 8px;
  letter-spacing: 4px;
}
</style>
