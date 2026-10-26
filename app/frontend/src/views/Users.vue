<template>
  <div class="page">
    <div class="page-head">
      <div>
        <div class="crumb">资源 / 用户管理</div>
        <h1 class="page-title">用户管理</h1>
        <div class="page-sub">共 {{ users.length }} 个账号，其中管理员 {{ adminCount }} 个</div>
      </div>
      <div class="head-actions">
        <el-button type="primary" @click="openCreate">新增用户</el-button>
      </div>
    </div>

    <div class="card list">
      <el-table :data="users" v-loading="loading" style="width: 100%">
        <el-table-column label="用户" min-width="176">
          <template #default="{ row }">
            <div class="uname">
              {{ row.display_name || row.username }}
              <span v-if="row.id === me?.id" class="self-tag">本人</span>
            </div>
            <div class="ulogin">{{ row.username }}</div>
          </template>
        </el-table-column>

        <el-table-column prop="role" label="角色" width="96">
          <template #default="{ row }">
            <span class="role" :style="row.role === 'admin' ? roleAdmin : roleUser">
              {{ row.role === 'admin' ? '管理员' : '普通用户' }}
            </span>
          </template>
        </el-table-column>

        <el-table-column prop="department" label="部门" width="140">
          <template #default="{ row }">{{ row.department || '-' }}</template>
        </el-table-column>

        <el-table-column prop="is_active" label="状态" width="88">
          <template #default="{ row }">
            <span class="status" :style="row.is_active ? statusOn : statusOff">
              {{ row.is_active ? '正常' : '已停用' }}
            </span>
          </template>
        </el-table-column>

        <el-table-column prop="created_at" label="创建时间" width="130">
          <template #default="{ row }">{{ formatDate(row.created_at) }}</template>
        </el-table-column>

        <el-table-column label="操作" width="216">
          <template #default="{ row }">
            <span class="link" @click="openEdit(row)">编辑</span>
            <span class="link" @click="openReset(row)">重置密码</span>
            <span
              v-if="row.id !== me?.id"
              class="link"
              @click="toggleActive(row)"
            >{{ row.is_active ? '停用' : '启用' }}</span>
            <span
              v-if="row.id !== me?.id"
              class="link danger"
              @click="remove(row)"
            >删除</span>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <el-dialog v-model="editVisible" :title="editMode === 'create' ? '新增用户' : '编辑用户'" width="460px">
      <div class="field">
        <label>登录名 <span class="req">英文</span></label>
        <el-input v-model="editForm.username" placeholder="zhangsan" />
        <div class="hint">用于登录，建议用拼音或工号</div>
      </div>
      <div class="field">
        <label>显示名 <span class="opt">中文</span></label>
        <el-input v-model="editForm.display_name" placeholder="张三" />
        <div class="hint">界面展示用，留空则显示登录名</div>
      </div>
      <div class="field">
        <label>部门</label>
        <el-input v-model="editForm.department" placeholder="选填" />
      </div>
      <div class="field">
        <label>角色</label>
        <el-select v-model="editForm.role" style="width: 100%" :disabled="editMode === 'edit' && editForm.id === me?.id">
          <el-option label="普通用户" value="user" />
          <el-option label="管理员" value="admin" />
        </el-select>
        <div class="hint">管理员可以管理所有账号与公司级知识库</div>
      </div>
      <div v-if="editMode === 'create'" class="field">
        <label>初始密码</label>
        <el-input v-model="editForm.password" placeholder="至少 6 位" show-password />
      </div>
      <template #footer>
        <el-button @click="editVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="submitEdit">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="resetVisible" title="重置密码" width="400px">
      <div class="reset-target">为「{{ resetTarget?.username }}」设置新密码</div>
      <div class="field">
        <label>新密码</label>
        <el-input v-model="resetPassword" placeholder="至少 6 位" show-password />
      </div>
      <div class="hint">重置后请通知本人，登录后可自行修改</div>
      <template #footer>
        <el-button @click="resetVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="submitReset">确认重置</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import api from '../api'
import { useUserStore } from '../store/user'

const router = useRouter()
const userStore = useUserStore()
const me = computed(() => userStore.user)

const users = ref([])
const loading = ref(false)
const saving = ref(false)

const editVisible = ref(false)
const editMode = ref('create')
const editForm = ref({
  id: null,
  username: '',
  display_name: '',
  department: '',
  role: 'user',
  password: '',
})

const resetVisible = ref(false)
const resetTarget = ref(null)
const resetPassword = ref('')

const adminCount = computed(() => users.value.filter(u => u.role === 'admin').length)

const roleAdmin = { color: 'var(--seal)', background: 'var(--seal-soft)' }
const roleUser = { color: 'var(--ink-2)', background: 'var(--paper-2)' }
const statusOn = { color: 'var(--ok)', background: 'var(--ok-soft)' }
const statusOff = { color: 'var(--ink-3)', background: 'var(--paper-2)' }

onMounted(async () => {
  await userStore.fetchMe()
  if (userStore.user?.role !== 'admin') {
    ElMessage.error('需要管理员权限')
    router.push('/')
    return
  }
  await load()
})

async function load() {
  loading.value = true
  try {
    users.value = await api.get('/users')
  } catch {
    users.value = []
  } finally {
    loading.value = false
  }
}

function openCreate() {
  editMode.value = 'create'
  editForm.value = {
    id: null,
    username: '',
    display_name: '',
    department: '',
    role: 'user',
    password: '',
  }
  editVisible.value = true
}

function openEdit(row) {
  editMode.value = 'edit'
  editForm.value = {
    id: row.id,
    username: row.username,
    display_name: row.display_name || '',
    department: row.department || '',
    role: row.role,
    password: '',
  }
  editVisible.value = true
}

async function submitEdit() {
  if (!editForm.value.username.trim()) {
    ElMessage.warning('请填写登录名')
    return
  }
  if (!/^[A-Za-z0-9_.-]+$/.test(editForm.value.username.trim())) {
    ElMessage.warning('登录名只能包含字母、数字、下划线、点和短横线')
    return
  }
  if (editMode.value === 'create' && (editForm.value.password || '').length < 6) {
    ElMessage.warning('初始密码至少 6 位')
    return
  }

  saving.value = true
  try {
    const payload = {
      username: editForm.value.username.trim(),
      display_name: editForm.value.display_name.trim() || null,
      department: editForm.value.department || null,
      role: editForm.value.role,
    }
    if (editMode.value === 'create') {
      await api.post('/users', { ...payload, password: editForm.value.password })
      ElMessage.success('用户已创建')
    } else {
      await api.put(`/users/${editForm.value.id}`, payload)
      ElMessage.success('已保存')
      // 改的是自己时刷新本地用户信息
      if (editForm.value.id === me.value?.id) await userStore.fetchMe()
    }
    editVisible.value = false
    await load()
  } catch {
    // 拦截器已提示
  } finally {
    saving.value = false
  }
}

function openReset(row) {
  resetTarget.value = row
  resetPassword.value = ''
  resetVisible.value = true
}

async function submitReset() {
  if ((resetPassword.value || '').length < 6) {
    ElMessage.warning('新密码至少 6 位')
    return
  }
  saving.value = true
  try {
    await api.put(`/users/${resetTarget.value.id}`, { password: resetPassword.value })
    ElMessage.success('密码已重置')
    resetVisible.value = false
  } catch {
    // 拦截器已提示
  } finally {
    saving.value = false
  }
}

async function toggleActive(row) {
  const next = !row.is_active
  try {
    await ElMessageBox.confirm(
      next
        ? `启用「${row.username}」？启用后可正常登录。`
        : `停用「${row.username}」？停用后该账号立即无法登录，历史数据保留。`,
      next ? '启用账号' : '停用账号',
      { type: 'warning', confirmButtonText: '确认', cancelButtonText: '取消' }
    )
  } catch {
    return
  }
  try {
    await api.put(`/users/${row.id}`, { is_active: next })
    ElMessage.success(next ? '已启用' : '已停用')
    await load()
  } catch {
    // 拦截器已提示
  }
}

async function remove(row) {
  try {
    await ElMessageBox.confirm(
      `确认删除「${row.username}」？此操作不可恢复。`,
      '删除用户',
      { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' }
    )
  } catch {
    return
  }
  try {
    await api.delete(`/users/${row.id}`)
    ElMessage.success('已删除')
    await load()
  } catch {
    // 拦截器已提示（有业务数据时会拒绝）
  }
}

function formatDate(d) {
  if (!d) return '-'
  return String(d).replace('T', ' ').slice(0, 10)
}
</script>

<style scoped>
.head-actions {
  margin-left: auto;
}

.list {
  overflow: hidden;
}

.uname {
  font-size: 13px;
  color: var(--ink);
}

.ulogin {
  font-size: 11px;
  color: var(--ink-4);
  margin-top: 2px;
}

.req {
  color: var(--seal);
}

.opt {
  color: var(--ink-4);
}

.self-tag {
  font-size: 10px;
  color: var(--seal);
  background: var(--seal-soft);
  padding: 1px 6px;
  border-radius: 2px;
  margin-left: 7px;
}

.role,
.status {
  display: inline-block;
  padding: 1px 8px;
  border-radius: var(--r-sm);
  font-size: 11px;
}

.link {
  font-size: 12px;
  color: var(--seal);
  cursor: pointer;
  margin-right: 12px;
}

.link:hover {
  text-decoration: underline;
}

.link.danger {
  color: var(--ink-3);
  margin-right: 0;
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

.reset-target {
  font-size: 12px;
  color: var(--ink-2);
  margin-bottom: 14px;
}
</style>
