<template>
  <el-dialog
    v-model="visible"
    title="导出 Word 文档"
    width="560px"
    @close="$emit('close')"
  >
    <div class="section">
      <div class="section-label">选择模板</div>
      <div class="templates">
        <div
          v-for="t in templateList"
          :key="t.id"
          class="tpl"
          :class="{ active: selectedTemplate === t.id }"
          @click="selectedTemplate = t.id"
        >
          <div class="tpl-name">{{ t.name }}</div>
          <div v-if="t.description" class="tpl-desc">{{ t.description }}</div>
        </div>
      </div>
    </div>

    <div class="section">
      <div class="section-label">格式选项</div>
      <label class="opt">
        <input type="checkbox" v-model="options.include_references" />
        <span>包含引用标注</span>
      </label>
      <label class="opt">
        <input type="checkbox" v-model="options.include_appendix" />
        <span>包含附件清单页</span>
      </label>
      <label class="opt">
        <input type="checkbox" v-model="options.export_pdf" />
        <span>同时导出 PDF 版本</span>
      </label>
    </div>

    <div class="summary">
      <div class="sum-item">
        <div class="sum-label">总字数</div>
        <div class="sum-value">{{ wordCount }}</div>
      </div>
      <div class="sum-item">
        <div class="sum-label">引用数</div>
        <div class="sum-value">{{ refCount }}</div>
      </div>
      <div class="sum-item">
        <div class="sum-label">版本</div>
        <div class="sum-value">{{ version }}</div>
      </div>
    </div>

    <template #footer>
      <el-button @click="$emit('close')">取消</el-button>
      <el-button type="primary" :loading="exporting" @click="handleExport">导出 Word</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, watch, computed } from 'vue'
import { ElMessage } from 'element-plus'
import api from '../api'

const props = defineProps({
  docId: String,
  templates: Array,
})
const emit = defineEmits(['close'])

const visible = ref(true)
const exporting = ref(false)
const selectedTemplate = ref(null)
const options = ref({
  include_references: true,
  include_appendix: true,
  export_pdf: false,
})

const wordCount = ref(0)
const refCount = ref(0)
const version = ref('-')

const templateList = computed(() => props.templates || [])

watch(
  () => props.docId,
  async (id) => {
    if (!id) return
    try {
      const doc = await api.get(`/documents/${id}`)
      wordCount.value = (doc.content || '').length
      version.value = doc.version ?? '-'
    } catch { /* 统计失败不影响导出 */ }

    try {
      const task = await api.get(`/documents/${id}/task`)
      refCount.value = (task.references || []).length
    } catch { /* 无生成记录时留 0 */ }
  },
  { immediate: true }
)

async function handleExport() {
  exporting.value = true
  try {
    const result = await api.post('/documents/export', {
      document_id: props.docId,
      template_id: selectedTemplate.value,
      ...options.value,
    })
    ElMessage.success(`已生成：${result.filename || '文档'}`)
    emit('close')
  } catch {
    // 拦截器已提示
  } finally {
    exporting.value = false
  }
}
</script>

<style scoped>
.section {
  margin-bottom: 20px;
}

.section-label {
  font-size: 11px;
  color: var(--ink-3);
  margin-bottom: 8px;
}

.templates {
  display: flex;
  flex-wrap: wrap;
  gap: 9px;
}

.tpl {
  flex: 1;
  min-width: 180px;
  border: 0.5px solid var(--line);
  border-radius: var(--r-sm);
  padding: 10px 13px;
  cursor: pointer;
  background: var(--paper-3);
  transition: border-color 0.15s;
}

.tpl:hover {
  border-color: var(--gold-line);
}

.tpl.active {
  border-color: var(--seal);
  background: var(--seal-soft);
}

.tpl-name {
  font-size: 12px;
  color: var(--ink);
}

.tpl-desc {
  font-size: 10px;
  color: var(--ink-4);
  margin-top: 3px;
  line-height: 1.5;
}

.opt {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: var(--ink-2);
  padding: 5px 0;
  cursor: pointer;
}

.opt input {
  accent-color: var(--seal);
  margin: 0;
}

.summary {
  display: flex;
  gap: 32px;
  background: var(--paper-2);
  border-radius: var(--r-sm);
  padding: 12px 16px;
}

.sum-label {
  font-size: 10px;
  color: var(--ink-4);
}

.sum-value {
  font-size: 17px;
  color: var(--ink);
  margin-top: 2px;
  font-variant-numeric: tabular-nums;
}
</style>
