<template>
  <div style="padding: 24px;">
    <div style="margin-bottom: 16px; display: flex; justify-content: space-between; align-items: center;">
      <h2 style="margin: 0; font-size: 18px;">编辑器</h2>
      <div>
        <el-button @click="showExport = true">导出 Word</el-button>
      </div>
    </div>
    <el-row :gutter="20">
      <el-col :span="16">
        <el-card shadow="never">
          <el-input
            v-model="content"
            type="textarea"
            :rows="24"
            placeholder="请示内容"
            style="font-size: 14px; line-height: 1.8;"
            @input="onContentChange"
          />
          <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 8px; padding: 0 8px;">
            <span style="font-size: 12px; color: #888;">已自动保存 · 版本 {{ doc?.version }}</span>
            <span style="font-size: 12px; color: #888;">{{ content.length }} 字</span>
          </div>
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card shadow="never">
          <div style="font-weight: 600; margin-bottom: 12px;">引用溯源</div>
          <div v-if="references.length === 0" style="color: #888; font-size: 13px;">暂无引用</div>
          <div v-for="(ref, i) in references" :key="i" style="padding: 8px 0; border-bottom: 1px solid #f0f0f0;">
            <div style="font-size: 13px; font-weight: 500;">{{ ref.title }}</div>
            <div style="font-size: 12px; color: #888; margin-top: 4px;">{{ ref.content?.substring(0, 100) }}...</div>
          </div>
          <div style="margin-top: 12px; padding: 8px; background: #f0f9eb; border-radius: 4px;">
            <el-icon color="#67c23a"><CircleCheck /></el-icon>
            <span style="font-size: 12px; color: #67c23a; margin-left: 4px;">引用校验通过</span>
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
import { ref, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import api from '../api'
import ExportDialog from '../components/ExportDialog.vue'

const route = useRoute()
const docId = route.params.id
const doc = ref(null)
const content = ref('')
const references = ref([])
const showExport = ref(false)
const exportTemplates = ref([])
let saveTimer = null

onMounted(async () => {
  doc.value = await api.get(`/documents/${docId}`)
  content.value = doc.value.content || ''
  exportTemplates.value = await api.get('/documents/templates')
})

function onContentChange() {
  if (saveTimer) clearTimeout(saveTimer)
  saveTimer = setTimeout(async () => {
    await api.put(`/documents/${docId}/content`, { content: content.value })
  }, 3000)
}
</script>
