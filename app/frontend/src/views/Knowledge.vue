<template>
  <div class="page">
    <div class="page-head">
      <div>
        <div class="crumb">资源 / 知识库</div>
        <h1 class="page-title">知识库</h1>
        <div class="page-sub">制度文件与历史公文，是生成时的依据来源</div>
      </div>
    </div>

    <div class="tabs">
      <span
        v-for="t in tabs"
        :key="t.key"
        class="tab"
        :class="{ active: activeTab === t.key }"
        @click="activeTab = t.key"
      >
        {{ t.label }}
        <span class="tab-count">{{ t.count }}</span>
      </span>
    </div>

    <div v-if="activeTab === 'company' && !isAdmin" class="notice">
      公司级知识库由管理员统一维护，如需上传请联系管理员
    </div>

    <el-upload
      v-if="canUpload"
      class="uploader"
      drag
      :action="uploadUrl"
      :data="uploadData"
      :headers="uploadHeaders"
      :accept="accept"
      :show-file-list="false"
      :before-upload="beforeUpload"
      :on-success="onUploadSuccess"
      :on-error="onUploadError"
    >
      <div class="upload-inner">
        <div class="upload-icon">
          <el-icon><Upload /></el-icon>
        </div>
        <div class="upload-title">拖拽文件到此处，或点击选择</div>
        <div class="upload-sub">支持 PDF、DOCX，单文件不超过 50MB</div>
      </div>
    </el-upload>

    <div v-loading="loading" class="grid-wrap">
      <div v-if="docs.length === 0 && !loading" class="empty">
        <div class="empty-text">这里还没有文档</div>
        <div class="empty-sub">上传制度文件后，生成公文时才能引用条款依据</div>
      </div>

      <div class="grid">
        <div v-for="doc in docs" :key="doc.id" class="doc-card card">
          <div class="doc-head">
            <span class="doc-format">{{ (doc.file_format || '').toUpperCase() || 'DOC' }}</span>
            <span class="doc-status" :style="statusStyle(doc.status)">{{ statusText(doc.status) }}</span>
          </div>
          <div class="doc-name" :title="doc.title">{{ doc.title }}</div>
          <div class="doc-meta">{{ typeText(doc.doc_type) }} · {{ formatDate(doc.created_at) }}</div>
          <div v-if="doc.meta?.note" class="doc-note">{{ doc.meta.note }}</div>
          <div class="doc-actions">
            <span v-if="doc.status === 'failed'" class="link" @click="retry(doc)">重试</span>
            <span class="link danger" @click="remove(doc)">删除</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Upload } from '@element-plus/icons-vue'
import api from '../api'
import { useUserStore } from '../store/user'

const userStore = useUserStore()
const isAdmin = computed(() => userStore.user?.role === 'admin')

const activeTab = ref('personal')
const companyDocs = ref([])
const personalDocs = ref([])
const loading = ref(false)
const companyKbId = ref('')
const personalKbId = ref('')

const accept = '.pdf,.docx'

const tabs = computed(() => [
  { key: 'company', label: '公司级', count: companyDocs.value.length },
  { key: 'personal', label: '个人级', count: personalDocs.value.length },
])

const docs = computed(() =>
  activeTab.value === 'company' ? companyDocs.value : personalDocs.value
)

const canUpload = computed(() => {
  if (activeTab.value === 'company') return isAdmin.value && !!companyKbId.value
  return !!personalKbId.value
})

const uploadUrl = '/api/kb/upload'

const uploadData = computed(() => ({
  kb_id: activeTab.value === 'company' ? companyKbId.value : personalKbId.value,
  doc_type: activeTab.value === 'company' ? 'regulation' : 'case',
}))

const uploadHeaders = computed(() => ({
  Authorization: `Bearer ${userStore.token}`,
}))

onMounted(async () => {
  await userStore.fetchMe()
  const data = await api.get('/kb/bases')
  if (data.company?.length) companyKbId.value = data.company[0].id
  if (data.personal?.length) personalKbId.value = data.personal[0].id
  loadCompany()
  loadPersonal()
})

async function loadCompany() {
  loading.value = true
  try {
    companyDocs.value = await api.get('/kb/documents', { params: { level: 'company' } })
  } finally {
    loading.value = false
  }
}

async function loadPersonal() {
  loading.value = true
  try {
    personalDocs.value = await api.get('/kb/documents', { params: { level: 'personal' } })
  } finally {
    loading.value = false
  }
}

function reload() {
  return activeTab.value === 'company' ? loadCompany() : loadPersonal()
}

watch(activeTab, () => {
  activeTab.value === 'company' ? loadCompany() : loadPersonal()
})

function beforeUpload(file) {
  const ok = /\.(pdf|docx)$/i.test(file.name)
  if (!ok) {
    ElMessage.error('只支持 PDF 和 DOCX 文件')
    return false
  }
  if (file.size > 50 * 1024 * 1024) {
    ElMessage.error('文件不能超过 50MB')
    return false
  }
  return true
}

function onUploadSuccess() {
  ElMessage.success('上传成功，正在解析入库')
  reload()
}

function onUploadError() {
  ElMessage.error('上传失败，请检查文件格式或稍后重试')
}

async function retry(doc) {
  try {
    await api.post(`/kb/documents/${doc.id}/retry`)
    ElMessage.success('已重新提交解析')
    reload()
  } catch { /* 拦截器已提示 */ }
}

async function remove(doc) {
  try {
    await ElMessageBox.confirm(`确认删除「${doc.title}」？`, '删除文档', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消',
    })
  } catch {
    return
  }
  try {
    await api.delete(`/kb/documents/${doc.id}`)
    ElMessage.success('已删除')
    reload()
  } catch { /* 拦截器已提示 */ }
}

function statusText(s) {
  return {
    pending: '待处理', parsing: '解析中', indexing: '索引中',
    done: '已索引', failed: '失败',
  }[s] || s
}

function statusStyle(s) {
  const map = {
    done: { color: 'var(--ok)', background: 'var(--ok-soft)' },
    parsing: { color: 'var(--warn)', background: 'var(--warn-soft)' },
    indexing: { color: 'var(--warn)', background: 'var(--warn-soft)' },
    pending: { color: 'var(--ink-3)', background: 'var(--paper-2)' },
    failed: { color: 'var(--err)', background: 'var(--err-soft)' },
  }
  return map[s] || map.pending
}

function typeText(t) {
  return { regulation: '管理办法', case: '历史公文', template: '模板', other: '其他' }[t] || '其他'
}

function formatDate(d) {
  if (!d) return '-'
  return String(d).replace('T', ' ').slice(5, 16)
}
</script>

<style scoped>
.tabs {
  display: flex;
  gap: 22px;
  border-bottom: 0.5px solid var(--line);
  margin-bottom: 16px;
}

.tab {
  padding: 0 2px 9px;
  font-size: 13px;
  color: var(--ink-3);
  cursor: pointer;
  border-bottom: 1.5px solid transparent;
  margin-bottom: -0.5px;
  display: flex;
  align-items: center;
  gap: 6px;
}

.tab.active {
  color: var(--seal);
  border-bottom-color: var(--seal);
}

.tab-count {
  font-size: 11px;
  color: var(--ink-4);
}

.notice {
  font-size: 12px;
  color: var(--ink-3);
  background: var(--paper-2);
  border: 0.5px solid var(--line);
  border-radius: var(--r-sm);
  padding: 9px 13px;
  margin-bottom: 14px;
}

.uploader {
  margin-bottom: 16px;
}

.uploader :deep(.el-upload-dragger) {
  background: var(--paper-3);
  border: 1px dashed var(--line);
  border-radius: var(--r-md);
  padding: 22px 16px;
  transition: border-color 0.15s, background 0.15s;
}

.uploader :deep(.el-upload-dragger:hover) {
  border-color: var(--gold-line);
  background: var(--gold-soft);
}

.upload-inner {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 5px;
}

.upload-icon {
  width: 32px;
  height: 32px;
  border-radius: var(--r-sm);
  background: var(--paper-2);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--ink-3);
  font-size: 15px;
  margin-bottom: 2px;
}

.upload-title {
  font-size: 12px;
  color: var(--ink-2);
}

.upload-sub {
  font-size: 11px;
  color: var(--ink-4);
}

.grid-wrap {
  min-height: 120px;
}

.grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(232px, 1fr));
  gap: 12px;
}

.doc-card {
  padding: 13px 15px 11px;
  display: flex;
  flex-direction: column;
}

.doc-head {
  display: flex;
  align-items: center;
  margin-bottom: 8px;
}

.doc-format {
  font-size: 10px;
  color: var(--ink-3);
  background: var(--paper-2);
  border-radius: 2px;
  padding: 1px 6px;
  letter-spacing: 0.5px;
}

.doc-status {
  margin-left: auto;
  font-size: 10px;
  padding: 1px 7px;
  border-radius: 2px;
}

.doc-name {
  font-size: 13px;
  color: var(--ink);
  line-height: 1.5;
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  margin-bottom: 5px;
}

.doc-meta {
  font-size: 11px;
  color: var(--ink-4);
}

.doc-note {
  font-size: 10px;
  color: var(--warn);
  margin-top: 5px;
  line-height: 1.5;
}

.doc-actions {
  margin-top: auto;
  padding-top: 9px;
  display: flex;
  gap: 12px;
}

.link {
  font-size: 11px;
  color: var(--seal);
  cursor: pointer;
}

.link:hover {
  text-decoration: underline;
}

.link.danger {
  color: var(--ink-3);
  margin-left: auto;
}

.empty {
  padding: 42px 0;
  text-align: center;
}

.empty-text {
  font-size: 13px;
  color: var(--ink-3);
}

.empty-sub {
  font-size: 11px;
  color: var(--ink-4);
  margin-top: 5px;
}
</style>
