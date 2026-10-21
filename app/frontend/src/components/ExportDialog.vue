<template>
  <el-dialog v-model="visible" title="导出 Word 文档" width="680px" @close="$emit('close')">
    <div style="margin-bottom: 20px;">
      <div style="font-weight: 600; margin-bottom: 10px;">选择 Word 模板</div>
      <el-radio-group v-model="selectedTemplate" style="display: flex; gap: 10px; flex-wrap: wrap;">
        <el-radio v-for="t in templates" :key="t.id" :label="t.id" border style="margin: 0; width: 180px;">
          {{ t.name }}
        </el-radio>
      </el-radio-group>
    </div>
    <div style="margin-bottom: 20px;">
      <div style="font-weight: 600; margin-bottom: 10px;">格式选项</div>
      <el-checkbox v-model="options.include_references">包含引用标注</el-checkbox>
      <el-checkbox v-model="options.include_appendix">包含附件清单页</el-checkbox>
      <el-checkbox v-model="options.export_pdf">同时导出 PDF 版本</el-checkbox>
    </div>
    <div style="padding: 12px; background: #f5f5f5; border-radius: 8px; display: flex; gap: 32px;">
      <div>
        <div style="font-size: 11px; color: #888;">总字数</div>
        <div style="font-size: 18px; font-weight: 500;">{{ wordCount }}</div>
      </div>
      <div>
        <div style="font-size: 11px; color: #888;">引用数</div>
        <div style="font-size: 18px; font-weight: 500;">{{ refCount }}</div>
      </div>
    </div>
    <template #footer>
      <el-button @click="$emit('close')">取消</el-button>
      <el-button @click="handleExport" type="primary">导出 Word</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import api from '../api'
import { ElMessage } from 'element-plus'

const props = defineProps({
  modelValue: Boolean,
  docId: String,
  templates: Array,
})
const emit = defineEmits(['close', 'update:modelValue'])

const visible = ref(true)
const selectedTemplate = ref(null)
const options = ref({
  include_references: true,
  include_appendix: true,
  export_pdf: false,
})

const wordCount = ref(0)
const refCount = ref(0)

watch(() => props.docId, async (id) => {
  if (id) {
    const doc = await api.get(`/documents/${id}`)
    wordCount.value = (doc.content || '').length
    refCount.value = 0  // will be populated from task references
  }
}, { immediate: true })

async function handleExport() {
  try {
    const result = await api.post('/documents/export', {
      document_id: props.docId,
      template_id: selectedTemplate.value,
      ...options.value,
    })
    ElMessage.success('导出成功')
    emit('close')
  } catch {
  }
}
</script>
