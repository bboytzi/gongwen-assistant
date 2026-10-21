<template>
  <el-table :data="documents" v-loading="loading" style="background: #fff; border-radius: 8px;">
    <el-table-column prop="title" label="名称" min-width="200" />
    <el-table-column prop="file_format" label="格式" width="80">
      <template #default="{ row }">
        <el-tag size="small" :type="row.file_format === 'pdf' ? 'danger' : 'primary'">{{ row.file_format?.toUpperCase() }}</el-tag>
      </template>
    </el-table-column>
    <el-table-column prop="doc_type" label="类型" width="100" />
    <el-table-column prop="status" label="状态" width="100">
      <template #default="{ row }">
        <el-tag :type="statusType(row.status)" size="small">{{ statusText(row.status) }}</el-tag>
      </template>
    </el-table-column>
    <el-table-column label="操作" width="200">
      <template #default="{ row }">
        <el-button v-if="row.status === 'failed'" link type="warning" @click="handleRetry(row.id)">重试</el-button>
        <el-button v-if="!readonly || row.user_id" link type="danger" @click="handleDelete(row.id)">删除</el-button>
      </template>
    </el-table-column>
  </el-table>
</template>

<script setup>
import { ref, watch } from 'vue'
import api from '../api'
import { ElMessage, ElMessageBox } from 'element-plus'

const props = defineProps({
  documents: Array,
  readonly: Boolean,
})
const emit = defineEmits(['refresh'])
const loading = ref(false)

function statusType(s) {
  return { pending: 'info', parsing: 'warning', indexing: 'warning', done: 'success', failed: 'danger' }[s] || 'info'
}
function statusText(s) {
  return { pending: '待处理', parsing: '解析中', indexing: '索引中', done: '已索引', failed: '失败' }[s] || s
}

async function handleRetry(id) {
  await api.post(`/kb/documents/${id}/retry`)
  ElMessage.success('已重新提交')
  emit('refresh')
}

async function handleDelete(id) {
  await ElMessageBox.confirm('确认删除此文档？', '提示', { type: 'warning' })
  await api.delete(`/kb/documents/${id}`)
  ElMessage.success('已删除')
  emit('refresh')
}
</script>
