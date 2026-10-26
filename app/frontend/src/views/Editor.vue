<template>
  <div class="page" v-loading="loading">
    <div class="editor-head">
      <div>
        <div class="crumb">工作台 / 编辑请示</div>
        <h1 class="page-title">{{ doc?.title || '编辑请示' }}</h1>
        <div class="page-sub">{{ subline }}</div>
      </div>
      <div class="head-actions">
        <span class="save-state">{{ saveState }}</span>
        <el-button @click="showExport = true" :disabled="!doc">导出 Word</el-button>
      </div>
    </div>

    <el-alert
      v-if="loadError"
      type="error"
      :title="loadError"
      :closable="false"
      style="margin-bottom: 14px"
    />

    <div class="layout">
      <div class="editor-col">
        <div class="paper">
          <el-input
            v-model="content"
            type="textarea"
            :rows="24"
            class="paper-input"
            placeholder="请示正文"
            :disabled="!doc"
            @input="onContentChange"
          />
        </div>
        <div class="editor-foot">
          <span>{{ content.length }} 字</span>
          <span>版本 {{ doc?.version ?? '-' }}</span>
          <span class="foot-note">正文按仿宋排版，导出后与预览一致</span>
        </div>
      </div>

      <div class="side-col">
        <div class="card card-pad">
          <div class="card-title">引用溯源</div>
          <div v-if="references.length === 0" class="ref-empty">暂无引用记录</div>
          <div v-for="(ref, i) in references" :key="i" class="ref-item">
            <div class="ref-title">{{ ref.title }}</div>
            <div class="ref-body">{{ (ref.content || '').substring(0, 90) }}…</div>
          </div>
        </div>

        <div class="card card-pad tip">
          <div class="tip-title">编辑提示</div>
          <div class="tip-line">· 修改后 3 秒自动保存</div>
          <div class="tip-line">· 每次保存生成一个历史版本</div>
          <div class="tip-line">· 导出前建议核对引用条款号</div>
        </div>
      </div>
    </div>

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

const subline = computed(() => {
  if (!doc.value) return '加载中'
  const t = doc.value.updated_at
  return t ? `最近保存 ${String(t).replace('T', ' ').slice(0, 16)}` : '尚未保存'
})

const saveState = computed(() => {
  if (saving.value) return '保存中…'
  if (savedAt.value) return `已保存 ${savedAt.value}`
  return '自动保存已开启'
})

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

<style scoped>
.editor-head {
  display: flex;
  align-items: flex-end;
  margin-bottom: 16px;
}

.head-actions {
  margin-left: auto;
  display: flex;
  align-items: center;
  gap: 12px;
}

.save-state {
  font-size: 11px;
  color: var(--ink-4);
}

.layout {
  display: flex;
  gap: 16px;
  align-items: flex-start;
}

.editor-col {
  flex: 1;
  min-width: 0;
}

.paper {
  background: #ffffff;
  border: 0.5px solid var(--line);
  border-radius: 2px;
  padding: 34px 44px;
  min-height: 560px;
}

.paper-input :deep(.el-textarea__inner) {
  border: none;
  box-shadow: none;
  background: transparent;
  padding: 0;
  resize: none;
  font-family: "FangSong", "STFangsong", "SimSun", var(--font-serif);
  font-size: 13.5px;
  line-height: 2.1;
  color: var(--ink);
  text-indent: 2em;
}

.paper-input :deep(.el-textarea__inner:focus) {
  box-shadow: none;
}

.editor-foot {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 9px 4px 0;
  font-size: 11px;
  color: var(--ink-4);
}

.foot-note {
  margin-left: auto;
}

.side-col {
  width: 244px;
  flex-shrink: 0;
}

.side-col .card {
  margin-bottom: 12px;
}

.side-col .card-title {
  margin-bottom: 10px;
}

.ref-empty {
  font-size: 12px;
  color: var(--ink-4);
  padding: 6px 0 4px;
}

.ref-item {
  padding: 8px 0;
  border-bottom: 0.5px solid var(--line-2);
}

.ref-item:last-child {
  border-bottom: none;
}

.ref-title {
  font-size: 12px;
  color: var(--ink);
  margin-bottom: 3px;
}

.ref-body {
  font-size: 11px;
  color: var(--ink-4);
  line-height: 1.6;
}

.tip {
  background: var(--paper-3);
}

.tip-title {
  font-size: 12px;
  color: var(--ink-2);
  margin-bottom: 7px;
}

.tip-line {
  font-size: 11px;
  color: var(--ink-4);
  line-height: 1.8;
}
</style>
