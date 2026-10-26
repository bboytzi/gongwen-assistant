<template>
  <div style="padding: 24px;">
    <div style="margin-bottom: 24px;">
      <h2 style="margin: 0; font-size: 18px;">我的请示</h2>
    </div>
    <div style="margin-bottom: 16px;">
      <el-button type="primary" @click="$router.push('/documents/new')">
        <el-icon><Plus /></el-icon> 新建请示
      </el-button>
    </div>
    <el-table :data="documents" v-loading="loading" style="background: #fff; border-radius: 8px;">
      <el-table-column prop="title" label="标题" min-width="200" />
      <el-table-column prop="doc_category" label="类型" width="100" />
      <el-table-column prop="procurement_method" label="采购方式" width="100" />
      <el-table-column prop="status" label="状态" width="100">
        <template #default="{ row }">
          <el-tag :type="statusType(row.status)" size="small">{{ statusText(row.status) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="version" label="版本" width="60" />
      <el-table-column prop="updated_at" label="更新时间" width="180">
        <template #default="{ row }">
          {{ formatDate(row.updated_at) }}
        </template>
      </el-table-column>
      <el-table-column label="操作" width="200">
        <template #default="{ row }">
          <el-button v-if="row.status === 'done'" link type="primary" @click="go(`/documents/${row.id}/edit`)">编辑</el-button>
          <el-button v-if="row.status === 'generating'" link type="warning" @click="go(`/documents/${row.id}/generate`)">查看进度</el-button>
          <el-button v-if="row.status === 'draft'" link type="primary" @click="go(`/documents/${row.id}/generate`)">生成</el-button>
        </template>
      </el-table-column>
    </el-table>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import api from '../api'
import dayjs from 'dayjs'
import { ElMessage } from 'element-plus'

const router = useRouter()
const documents = ref([])
const loading = ref(false)

onMounted(async () => {
  loading.value = true
  try {
    documents.value = await api.get('/documents')
  } finally {
    loading.value = false
  }
})

async function go(path) {
  try {
    await router.push(path)
  } catch (e) {
    // 路由跳转失败（如目标组件 chunk 加载 404）不会抛到这里，
    // 但导航被守卫拦截或重复导航会，给出可见反馈而不是静默
    ElMessage.error(`页面跳转失败：${e?.message || e}`)
  }
}

function statusType(s) {
  return { draft: 'info', generating: 'warning', done: 'success', failed: 'danger' }[s] || 'info'
}
function statusText(s) {
  return { draft: '草稿', generating: '生成中', done: '已完成', failed: '失败' }[s] || s
}
function formatDate(d) {
  return d ? dayjs(d).format('YYYY-MM-DD HH:mm') : ''
}
</script>
