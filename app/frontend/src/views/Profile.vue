<template>
  <div class="page">
    <div class="page-head">
      <div>
        <div class="crumb">账号 / 个人资料</div>
        <h1 class="page-title">个人资料</h1>
        <div class="page-sub">修改显示名称与登录密码</div>
      </div>
    </div>

    <div class="layout">
      <div class="card card-pad">
        <div class="card-title">基本资料</div>

        <div class="identity">
          <div class="avatar">{{ initial }}</div>
          <div>
            <div class="id-name">{{ profile.username || '-' }}</div>
            <div class="id-role">
              {{ profile.role === 'admin' ? '管理员' : '普通用户' }}
              <span v-if="profile.department">· {{ profile.department }}</span>
            </div>
          </div>
        </div>

        <div class="field">
          <label>用户名</label>
          <el-input v-model="profileForm.username" placeholder="登录名" />
          <div class="hint">修改后下次登录请使用新用户名</div>
        </div>

        <div class="field">
          <label>部门</label>
          <el-input v-model="profileForm.department" placeholder="选填" />
        </div>

        <el-button type="primary" :loading="savingProfile" @click="saveProfile">
          保存资料
        </el-button>
      </div>

      <div class="card card-pad">
        <div class="card-title">修改密码</div>

        <div class="field">
          <label>原密码</label>
          <el-input v-model="pwdForm.old_password" type="password" show-password placeholder="当前密码" />
        </div>

        <div class="field">
          <label>新密码</label>
          <el-input v-model="pwdForm.new_password" type="password" show-password placeholder="至少 6 位" />
        </div>

        <div class="field">
          <label>确认新密码</label>
          <el-input v-model="pwdForm.confirm" type="password" show-password placeholder="再输入一次" />
        </div>

        <el-button type="primary" :loading="savingPwd" @click="savePassword">
          修改密码
        </el-button>

        <div class="pwd-note">
          密码以 bcrypt 加盐存储，管理员也无法查看明文。忘记密码需联系管理员重置。
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import api from '../api'
import { useUserStore } from '../store/user'

const userStore = useUserStore()

const profile = ref({})
const profileForm = ref({ username: '', department: '' })
const savingProfile = ref(false)

const pwdForm = ref({ old_password: '', new_password: '', confirm: '' })
const savingPwd = ref(false)

const initial = computed(() =>
  (profile.value.username || 'A').charAt(0).toUpperCase()
)

onMounted(async () => {
  await load()
})

async function load() {
  try {
    const me = await api.get('/users/me')
    profile.value = me
    profileForm.value = {
      username: me.username || '',
      department: me.department || '',
    }
  } catch { /* 拦截器已提示 */ }
}

async function saveProfile() {
  if (!profileForm.value.username.trim()) {
    ElMessage.warning('用户名不能为空')
    return
  }
  savingProfile.value = true
  try {
    const updated = await api.put('/users/me', {
      username: profileForm.value.username,
      department: profileForm.value.department,
    })
    profile.value = updated
    await userStore.fetchMe()
    ElMessage.success('资料已保存')
  } catch {
    // 拦截器已提示
  } finally {
    savingProfile.value = false
  }
}

async function savePassword() {
  if (!pwdForm.value.old_password) {
    ElMessage.warning('请输入原密码')
    return
  }
  if ((pwdForm.value.new_password || '').length < 6) {
    ElMessage.warning('新密码至少 6 位')
    return
  }
  if (pwdForm.value.new_password !== pwdForm.value.confirm) {
    ElMessage.warning('两次输入的新密码不一致')
    return
  }

  savingPwd.value = true
  try {
    await api.put('/users/me/password', {
      old_password: pwdForm.value.old_password,
      new_password: pwdForm.value.new_password,
    })
    pwdForm.value = { old_password: '', new_password: '', confirm: '' }
    ElMessage.success('密码已修改')
  } catch {
    // 拦截器已提示
  } finally {
    savingPwd.value = false
  }
}
</script>

<style scoped>
.layout {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
  max-width: 860px;
}

.card-title {
  margin-bottom: 16px;
}

.identity {
  display: flex;
  align-items: center;
  gap: 12px;
  padding-bottom: 16px;
  border-bottom: 0.5px solid var(--line-2);
  margin-bottom: 16px;
}

.avatar {
  width: 42px;
  height: 42px;
  border-radius: 50%;
  background: var(--seal-soft);
  color: var(--seal);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 16px;
  font-weight: 500;
}

.id-name {
  font-family: var(--font-serif);
  font-size: 15px;
  color: var(--ink);
  letter-spacing: 0.5px;
}

.id-role {
  font-size: 11px;
  color: var(--ink-4);
  margin-top: 3px;
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

.pwd-note {
  font-size: 11px;
  color: var(--ink-4);
  line-height: 1.7;
  margin-top: 14px;
  padding-top: 12px;
  border-top: 0.5px solid var(--line-2);
}
</style>
