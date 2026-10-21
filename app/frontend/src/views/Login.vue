<template>
  <div style="height: 100vh; display: flex; align-items: center; justify-content: center; background: #f5f5f5;">
    <el-card style="width: 400px;" shadow="never">
      <div style="text-align: center; margin-bottom: 24px;">
        <h2 style="margin: 0; font-size: 18px; font-weight: 600;">天府数产公文辅助系统</h2>
        <p style="color: #888; font-size: 13px; margin: 8px 0 0;">请示材料自动生成 · 检索 · 知识库</p>
      </div>
      <el-tabs v-model="activeTab">
        <el-tab-pane label="登录" name="login">
          <el-form @submit.prevent="handleLogin">
            <el-form-item>
              <el-input v-model="loginForm.username" placeholder="用户名" prefix-icon="User" />
            </el-form-item>
            <el-form-item>
              <el-input v-model="loginForm.password" type="password" placeholder="密码" prefix-icon="Lock" show-password />
            </el-form-item>
            <el-button type="primary" style="width: 100%;" :loading="loading" @click="handleLogin">登录</el-button>
          </el-form>
        </el-tab-pane>
        <el-tab-pane label="注册" name="register">
          <el-form @submit.prevent="handleRegister">
            <el-form-item>
              <el-input v-model="regForm.username" placeholder="用户名" prefix-icon="User" />
            </el-form-item>
            <el-form-item>
              <el-input v-model="regForm.password" type="password" placeholder="密码" prefix-icon="Lock" show-password />
            </el-form-item>
            <el-form-item>
              <el-input v-model="regForm.department" placeholder="部门（可选）" prefix-icon="OfficeBuilding" />
            </el-form-item>
            <el-button type="primary" style="width: 100%;" :loading="loading" @click="handleRegister">注册</el-button>
          </el-form>
        </el-tab-pane>
      </el-tabs>
    </el-card>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useUserStore } from '../store/user'
import { ElMessage } from 'element-plus'

const router = useRouter()
const userStore = useUserStore()
const activeTab = ref('login')
const loading = ref(false)
const loginForm = ref({ username: '', password: '' })
const regForm = ref({ username: '', password: '', department: '' })

async function handleLogin() {
  loading.value = true
  try {
    await userStore.login(loginForm.value.username, loginForm.value.password)
    ElMessage.success('登录成功')
    router.push('/')
  } catch {
  } finally {
    loading.value = false
  }
}

async function handleRegister() {
  loading.value = true
  try {
    await userStore.register(regForm.value.username, regForm.value.password, regForm.value.department)
    ElMessage.success('注册成功')
    router.push('/')
  } catch {
  } finally {
    loading.value = false
  }
}
</script>
