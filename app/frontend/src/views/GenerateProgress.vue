<template>
  <div class="page">
    <div class="page-head">
      <div>
        <div class="crumb">工作台 / 生成进度</div>
        <h1 class="page-title">{{ headTitle }}</h1>
        <div class="page-sub">{{ headSub }}</div>
      </div>
      <div class="head-actions">
        <el-button
          v-if="task?.status === 'completed'"
          type="primary"
          @click="goEdit"
        >
          编辑文档
        </el-button>
      </div>
    </div>

    <el-alert
      v-if="task?.status === 'failed'"
      type="error"
      :title="task.error_message || '生成失败'"
      :closable="false"
      style="margin-bottom: 14px"
    />

    <div class="layout">
      <div class="steps-col card">
        <div class="ring-wrap">
          <el-progress
            type="circle"
            :percentage="task?.progress || 0"
            :width="96"
            :stroke-width="5"
            :color="ringColor"
          />
          <div class="ring-label">{{ currentStepName }}</div>
        </div>

        <div class="steps">
          <div
            v-for="(s, i) in steps"
            :key="s.key"
            class="step"
            :class="stepClass(i)"
          >
            <div class="step-mark">
              <span v-if="i < activeIndex" class="step-done">✓</span>
              <span v-else class="step-idx">{{ i + 1 }}</span>
            </div>
            <div class="step-body">
              <div class="step-name">{{ s.name }}</div>
              <div class="step-desc">{{ s.desc }}</div>
            </div>
          </div>
        </div>
      </div>

      <div class="content-col">
        <div class="preview-head">
          <span class="preview-label">正文预览</span>
          <span class="preview-note">{{ (task?.result_content || '').length }} 字</span>
        </div>

        <div class="paper">
          <div v-if="task?.result_content" class="paper-body">{{ task.result_content }}</div>
          <div v-else class="paper-wait">
            <div class="wait-dots">
              <span></span><span></span><span></span>
            </div>
            <div class="wait-text">正在生成，请稍候</div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import api from '../api'

const route = useRoute()
const router = useRouter()
const docId = route.params.id

const task = ref(null)
let ws = null
let pollTimer = null

const steps = [
  { key: 'intent', name: '意图解析', desc: '识别公文类别与关键要素' },
  { key: 'rag', name: '制度检索', desc: '从知识库提取相关条款' },
  { key: 'outline', name: '大纲生成', desc: '确定公文结构' },
  { key: 'generate', name: '分段撰写', desc: '逐段生成正文' },
  { key: 'validate', name: '引用校验', desc: '核对条款号与出处' },
  { key: 'format', name: '排版输出', desc: '套用公文格式' },
]

const stepMap = {
  init: 0, intent: 1, rag: 2, outline: 3,
  generate: 4, validate: 5, format: 6, done: 6,
}

const activeIndex = computed(() => stepMap[task.value?.current_step] ?? 0)

const currentStepName = computed(() => {
  const idx = activeIndex.value
  if (task.value?.status === 'completed') return '已完成'
  if (task.value?.status === 'failed') return '已中断'
  return steps[Math.min(idx, steps.length - 1)]?.name || '准备中'
})

const headTitle = computed(() => {
  if (task.value?.status === 'completed') return '生成完成'
  if (task.value?.status === 'failed') return '生成失败'
  return '正在生成'
})

const headSub = computed(() => {
  if (task.value?.status === 'completed') return '可直接编辑，或导出为 Word'
  if (task.value?.status === 'failed') return '请查看下方错误信息后重试'
  return '共六个步骤，通常 30 至 60 秒'
})

const ringColor = computed(() => {
  if (task.value?.status === 'failed') return '#a63a2e'
  if (task.value?.status === 'completed') return '#0f6e56'
  return '#c9a227'
})

function stepClass(i) {
  const idx = activeIndex.value
  const status = task.value?.status
  if (status === 'completed') return 'is-done'
  if (i < idx) return 'is-done'
  if (i === idx && status !== 'failed') return 'is-active'
  return ''
}

onMounted(async () => {
  try {
    task.value = await api.get(`/documents/${docId}/task`)
  } catch {
    return
  }

  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  ws = new WebSocket(`${protocol}//${window.location.host}/ws/generation/${task.value.id}`)

  ws.onmessage = (event) => {
    try {
      task.value = { ...task.value, ...JSON.parse(event.data) }
    } catch { /* 忽略非法帧 */ }
  }

  ws.onclose = () => {
    pollTimer = setInterval(async () => {
      try {
        task.value = await api.get(`/documents/${docId}/task`)
        if (['completed', 'failed', 'cancelled'].includes(task.value.status)) {
          clearInterval(pollTimer)
        }
      } catch { /* 重试下一轮 */ }
    }, 2000)
  }
})

onUnmounted(() => {
  if (ws) ws.close()
  if (pollTimer) clearInterval(pollTimer)
})

function goEdit() {
  router.push(`/documents/${docId}/edit`)
}
</script>

<style scoped>
.head-actions {
  margin-left: auto;
}

.layout {
  display: flex;
  gap: 16px;
  align-items: flex-start;
}

.steps-col {
  width: 268px;
  flex-shrink: 0;
  padding: 20px 18px;
}

.ring-wrap {
  text-align: center;
  padding-bottom: 18px;
  border-bottom: 0.5px solid var(--line-2);
  margin-bottom: 16px;
}

.ring-label {
  font-size: 12px;
  color: var(--ink-2);
  margin-top: 10px;
}

.steps {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.step {
  display: flex;
  gap: 10px;
  padding: 7px 6px;
  border-radius: var(--r-sm);
}

.step.is-active {
  background: var(--seal-soft);
}

.step-mark {
  width: 18px;
  height: 18px;
  border-radius: 50%;
  border: 1px solid var(--line);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  font-size: 10px;
  color: var(--ink-4);
  margin-top: 1px;
}

.step.is-done .step-mark {
  border-color: var(--ok);
  background: var(--ok-soft);
  color: var(--ok);
}

.step.is-active .step-mark {
  border-color: var(--seal);
  color: var(--seal);
}

.step-done {
  font-size: 10px;
}

.step-name {
  font-size: 12px;
  color: var(--ink-2);
}

.step.is-active .step-name {
  color: var(--seal);
}

.step.is-done .step-name {
  color: var(--ink);
}

.step-desc {
  font-size: 10px;
  color: var(--ink-4);
  margin-top: 1px;
}

.content-col {
  flex: 1;
  min-width: 0;
}

.preview-head {
  display: flex;
  align-items: center;
  margin-bottom: 9px;
}

.preview-label {
  font-size: 11px;
  color: var(--ink-3);
}

.preview-note {
  margin-left: auto;
  font-size: 10px;
  color: var(--ink-4);
}

.paper {
  background: #ffffff;
  border: 0.5px solid var(--line);
  border-radius: 2px;
  padding: 32px 40px;
  min-height: 520px;
}

.paper-body {
  font-family: "FangSong", "STFangsong", "SimSun", var(--font-serif);
  font-size: 13.5px;
  line-height: 2.1;
  color: var(--ink);
  white-space: pre-wrap;
  word-break: break-word;
}

.paper-wait {
  height: 456px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 14px;
}

.wait-dots {
  display: flex;
  gap: 5px;
}

.wait-dots span {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--gold);
  animation: pulse 1.2s infinite ease-in-out;
}

.wait-dots span:nth-child(2) {
  animation-delay: 0.15s;
}

.wait-dots span:nth-child(3) {
  animation-delay: 0.3s;
}

@keyframes pulse {
  0%, 100% { opacity: 0.25; transform: scale(0.9); }
  50% { opacity: 1; transform: scale(1.1); }
}

.wait-text {
  font-size: 12px;
  color: var(--ink-4);
}
</style>
