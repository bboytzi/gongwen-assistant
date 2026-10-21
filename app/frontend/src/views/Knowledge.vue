<template>
  <div style="padding: 24px;">
    <div style="margin-bottom: 24px;">
      <h2 style="margin: 0; font-size: 18px;">知识库管理</h2>
    </div>
    <el-tabs v-model="activeTab">
      <el-tab-pane label="公司级" name="company">
        <el-alert v-if="!isAdmin" type="info" title="公司级知识库为只读，如需上传请联系管理员" :closable="false" style="margin-bottom: 16px;" />
        <div v-if="isAdmin">
          <el-upload
            action="/api/kb/upload"
            :data="{ kb_id: companyKbId, doc_type: 'regulation' }"
            :headers="uploadHeaders"
            accept=".pdf,.docx"
            :on-success="onUploadSuccess"
            drag
            style="margin-bottom: 16px;"
          >
            <el-icon style="font-size: 24px; color: #999;"><Upload /></el-icon>
            <div style="font-size: 13px; color: #666; margin-top: 4px;">拖拽文件到此处或点击上传 (PDF/DOCX)</div>
          </el-upload>
        </div>
        <DocumentList :documents="companyDocs" :readonly="!isAdmin" @refresh="loadCompanyDocs" />
      </el-tab-pane>
      <el-tab-pane label="个人级" name="personal">
        <el-upload
          action="/api/kb/upload"
          :data="{ kb_id: personalKbId, doc_type: 'case' }"
          :headers="uploadHeaders"
          accept=".pdf,.docx"
          :on-success="onUploadSuccess"
          drag
          style="margin-bottom: 16px;"
        >
          <el-icon style="font-size: 24px; color: #999;"><Upload /></el-icon>
          <div style="font-size: 13px; color: #666; margin-top: 4px;">拖拽文件到此处或点击上传 (PDF/DOCX)</div>
        </el-upload>
        <DocumentList :documents="personalDocs" @refresh="loadPersonalDocs" />
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useUserStore } from '../store/user'
import api from '../api'
import { ElMessage } from 'element-plus'
import DocumentList from '../components/DocumentList.vue'

const userStore = useUserStore()
const isAdmin = computed(() => userStore.user?.role === 'admin')
const activeTab = ref('personal')
const companyDocs = ref([])
const personalDocs = ref([])
const companyKbId = ref('')
const personalKbId = ref('')

const uploadHeaders = computed(() => ({
  Authorization: `Bearer ${userStore.token}`,
}))

onMounted(async () => {
  const data = await api.get('/kb/bases')
  if (data.company.length > 0) companyKbId.value = data.company[0].id
  if (data.personal.length > 0) personalKbId.value = data.personal[0].id
  loadCompanyDocs()
  loadPersonalDocs()
})

async function loadCompanyDocs() {
  companyDocs.value = await api.get('/kb/documents', { params: { level: 'company' } })
}
async function loadPersonalDocs() {
  personalDocs.value = await api.get('/kb/documents', { params: { level: 'personal' } })
}

function onUploadSuccess() {
  ElMessage.success('上传成功，正在解析')
  if (activeTab.value === 'company') loadCompanyDocs()
  else loadPersonalDocs()
}
</script>
