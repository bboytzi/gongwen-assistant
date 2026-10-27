<template>
  <div class="page" v-loading="loading">
    <div class="editor-head">
      <div>
        <div class="crumb">工作台 / 编辑公文</div>
        <h1 class="page-title">{{ doc?.title || '编辑公文' }}</h1>
        <div class="page-sub">{{ subline }}</div>
      </div>
      <div class="head-actions">
        <div class="view-switch">
          <span
            class="vs-item"
            :class="{ active: viewMode === 'edit' }"
            @click="switchView('edit')"
          >编辑</span>
          <span
            class="vs-item"
            :class="{ active: viewMode === 'source' }"
            @click="switchView('source')"
          >溯源</span>
        </div>
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
            v-if="viewMode === 'edit'"
            v-model="content"
            type="textarea"
            :rows="24"
            class="paper-input"
            placeholder="公文正文"
            :disabled="!doc"
            @input="onContentChange"
          />

          <div v-else v-loading="loadingCitations" class="paper-read">
            <template v-if="citations">
              <p
                v-for="(para, pi) in citations.paragraphs"
                :key="pi"
                class="read-para"
              >
                <span
                  v-for="(s, si) in para"
                  :key="si"
                  class="sent"
                  :class="{
                    cited: s.ref_index !== null,
                    active: s.ref_index !== null && s.ref_index === activeRef,
                  }"
                  @click="onSentenceClick(s)"
                >{{ s.text }}<sup v-if="s.ref_index !== null" class="mark">{{ s.ref_index + 1 }}</sup></span>
              </p>
              <div v-if="citations.paragraphs.length === 0" class="read-empty">
                正文为空，暂无可溯源的句子
              </div>
            </template>
          </div>
        </div>

        <div class="editor-foot">
          <template v-if="viewMode === 'edit'">
            <span>{{ content.length }} 字</span>
            <span>版本 {{ doc?.version ?? '-' }}</span>
            <span class="foot-note">正文按仿宋排版，导出后与预览一致</span>
          </template>
          <template v-else>
            <span v-if="citations">
              {{ citations.cited_count }} / {{ citations.sentence_count }} 句已溯源
            </span>
            <span class="foot-note">
              点击带下划线的句子，可查看它来自哪份材料
            </span>
          </template>
        </div>
      </div>

      <div class="side-col">
        <div class="card card-pad">
          <div class="card-title">
            引用溯源
            <span v-if="citations?.references?.length" class="ref-count">
              {{ citations.references.length }} 份材料
            </span>
          </div>

          <div v-if="!citations?.references?.length" class="ref-empty">
            暂无引用记录。生成完成后这里会列出参考过的制度与案例。
          </div>

          <div
            v-for="ref in citations?.references || []"
            :id="`ref-card-${ref.index}`"
            :key="ref.index"
            class="ref-item"
            :class="{ active: activeRef === ref.index }"
            @click="onRefClick(ref.index)"
          >
            <div class="ref-head">
              <span class="ref-no">{{ ref.index + 1 }}</span>
              <span class="ref-title">{{ ref.title }}</span>
            </div>
            <div class="ref-body">{{ (ref.content || '').substring(0, 90) }}…</div>
            <div v-if="ref.source" class="ref-source">{{ ref.source }}</div>
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
const showExport = ref(false)
const exportTemplates = ref([])

const loading = ref(true)
const loadError = ref('')
const saving = ref(false)
const savedAt = ref('')

const viewMode = ref('edit')
const citations = ref(null)
const loadingCitations = ref(false)
const activeRef = ref(null)

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

  loading.value = false
})

onUnmounted(() => {
  if (saveTimer) clearTimeout(saveTimer)
})

function switchView(mode) {
  if (mode === viewMode.value) return
  viewMode.value = mode
  activeRef.value = null
  if (mode === 'source') loadCitations()
}

async function loadCitations() {
  loadingCitations.value = true
  try {
    citations.value = await api.get(`/documents/${docId.value}/citations`)
  } catch {
    citations.value = null
  } finally {
    loadingCitations.value = false
  }
}

function onSentenceClick(sentence) {
  if (sentence.ref_index === null) {
    activeRef.value = null
    return
  }
  activeRef.value = activeRef.value === sentence.ref_index ? null : sentence.ref_index
  if (activeRef.value !== null) {
    const el = document.getElementById(`ref-card-${activeRef.value}`)
    el?.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
  }
}

function onRefClick(index) {
  activeRef.value = activeRef.value === index ? null : index
}

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
      // 内容变了，下次进溯源视图要重新匹配
      citations.value = null
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

.view-switch {
  display: flex;
  border: 0.5px solid var(--line);
  border-radius: var(--r-sm);
  overflow: hidden;
}

.vs-item {
  padding: 5px 14px;
  font-size: 12px;
  color: var(--ink-3);
  cursor: pointer;
  background: var(--paper-3);
}

.vs-item.active {
  background: var(--seal-soft);
  color: var(--seal);
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

.paper-read {
  min-height: 492px;
  font-family: "FangSong", "STFangsong", "SimSun", var(--font-serif);
  font-size: 13.5px;
  line-height: 2.1;
  color: var(--ink);
}

.read-para {
  margin: 0 0 2px;
  text-indent: 2em;
}

.sent {
  cursor: default;
}

.sent.cited {
  cursor: pointer;
  border-bottom: 1px dashed var(--seal-line);
  padding-bottom: 1px;
}

.sent.cited:hover {
  background: var(--seal-soft);
}

.sent.active {
  background: var(--seal-soft);
  border-bottom-color: var(--seal);
}

.mark {
  font-size: 9px;
  color: var(--seal);
  margin-left: 1px;
  vertical-align: super;
  line-height: 0;
}

.read-empty {
  font-size: 12px;
  color: var(--ink-4);
  text-indent: 0;
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
  width: 268px;
  flex-shrink: 0;
}

.side-col .card {
  margin-bottom: 12px;
}

.side-col .card-title {
  margin-bottom: 10px;
  display: flex;
  align-items: center;
}

.ref-count {
  margin-left: auto;
  font-family: var(--font-sans);
  font-size: 10px;
  color: var(--ink-4);
  font-weight: 400;
}

.ref-empty {
  font-size: 12px;
  color: var(--ink-4);
  line-height: 1.7;
  padding: 4px 0;
}

.ref-item {
  padding: 9px 10px;
  border-radius: var(--r-sm);
  border: 0.5px solid transparent;
  cursor: pointer;
  margin-bottom: 4px;
  transition: background 0.15s, border-color 0.15s;
}

.ref-item:hover {
  background: var(--paper-3);
}

.ref-item.active {
  background: var(--seal-soft);
  border-color: var(--seal-line);
}

.ref-head {
  display: flex;
  align-items: flex-start;
  gap: 6px;
  margin-bottom: 4px;
}

.ref-no {
  font-size: 9px;
  color: #fff;
  background: var(--seal);
  width: 14px;
  height: 14px;
  border-radius: 2px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  margin-top: 2px;
}

.ref-title {
  font-size: 12px;
  color: var(--ink);
  line-height: 1.5;
}

.ref-body {
  font-size: 11px;
  color: var(--ink-4);
  line-height: 1.6;
}

.ref-source {
  font-size: 10px;
  color: var(--ink-4);
  margin-top: 4px;
  opacity: 0.8;
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
