<template>
  <div style="padding: 24px;" v-loading="loading">
    <div style="margin-bottom: 16px; display: flex; justify-content: space-between; align-items: center;">
      <h2 style="margin: 0; font-size: 18px;">编辑器</h2>
      <div>
        <el-button @click="showExport = true" :disabled="!doc">导出 Word</el-button>
      </div>
    </div>

    <el-alert
      v-if="loadError"
      type="error"
      :title="loadError"
      :closable="false"
      style="margin-bottom: 16px;"
    />

    <el-row :gutter="20">
      <el-col :span="16">
        <el-card shadow="never">
          <el-input
            v-model="content"
            type="textarea"
            :rows="24"
            placeholder="请示内容"
            style="font-size: 14px; line-height: 1.8;"
            :disabled="!doc"
            @input="onContentChange"
          />
          <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 8px; padding: 0 8px;">
            <span style="font-size: 12px; color: #888;">
              {{ saving ? '保存中…' : (savedAt ? `已保存 ${savedAt}` : '已自动保存') }}
              · 版本 {{ doc?.version ?? '-' }}
            </span>
            <span style="font-size: 12px; color: #888;">{{ content.length }} 字</span>
          </div>
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card shadow="never">
          <div style="font-weight: 600; margin-bottom: 12px;">引用溯源</div>
          <div v-if="references.length === 0" style="color: #888; font-size: 13px;">
            暂无引用记录
          </div>
          <div v-for="(ref, i) in references" :key="i" style="padding: 8px 0; border-bottom: 1px solid #f0f0f0;">
            <div style="font-size: 13px; font-weight: 500;">{{ ref.title }}</div>
            <div style="font-size: 12px; color: #888; margin-top: 4px;">{{ (ref.content || '').substring(0, 100) }}...</div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <ExportDialog
      v-if="showExport"
      :doc-id="docId"
      :templates="exportTemplates"
      @close="showExport = false"
    />
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRoute } from 'vue-router'
import api from '../api'
import ExportDialog from '../components/ExportDialog.vue'

const route = useRoute()
const docId = computed(() => route.params.id)

const doc = ref(null)
const content = ref('')
const references = ref([])
const showExport = ref(false)
const exportTemplates = ref([])

const loading = ref(true)
const loadError = ref('')
const saving = ref(false)
const savedAt = ref('')

let saveTimer = null

onMounted(async () => {
  try {
    doc.value = await api.get(`/documents/${docId.value}`)
    content.value = doc.value.content || ''
  } catch (e) {
    const status = e?.response?.status
    loadError.value = status === 404
      ? '文档不存在，可能已被删除'
      : status === 403
        ? '无权访问该文档'
        : `加载文档失败：${e?.message || '未知错误'}`
    loading.value = false
    return
  }

  // 模板列表和引用记录失败不影响编辑，单独容错
  try {
    exportTemplates.value = await api.get('/documents/templates')
  } catch { /* 导出时再提示 */ }

  try {
    const task = await api.get(`/documents/${docId.value}/task`)
    references.value = task.references || []
  } catch { /* 无生成记录时忽略 */ }

  loading.value = false
})

onUnmounted(() => {
  if (saveTimer) clearTimeout(saveTimer)
})

function onContentChange() {
  if (saveTimer) clearTimeout(saveTimer)
  saveTimer = setTimeout(async () => {
    saving.value = true
    try {
      const res = await api.put(`/documents/${docId.value}/content`, {
        content: content.value,
      })
      doc.value = { ...doc.value, version: res.version }
      savedAt.value = new Date().toLocaleTimeString('zh-CN', { hour12: false })
    } finally {
      saving.value = false
    }
  }, 3000)
}
</script>
