<template>
  <div style="padding: 24px;">
    <div style="margin-bottom: 24px;">
      <h2 style="margin: 0; font-size: 18px;">生成进度</h2>
    </div>
    <el-row :gutter="24">
      <el-col :span="8">
        <el-card shadow="never">
          <div style="margin-bottom: 16px;">
            <el-progress :percentage="task?.progress || 0" :status="progressStatus" />
          </div>
          <el-steps direction="vertical" :active="currentStepIndex" process-status="process">
            <el-step title="意图解析" description="分析请示类型和关键要素" />
            <el-step title="RAG检索" description="从知识库提取相关条款" />
            <el-step title="大纲生成" description="生成文档结构" />
            <el-step title="分段生成" description="逐段生成正文内容" />
            <el-step title="引用校验" description="验证引用准确性" />
            <el-step title="Word排版" description="格式化输出" />
          </el-steps>
          <div v-if="task?.status === 'failed'" style="margin-top: 16px;">
            <el-alert type="error" :title="task.error_message || '生成失败'" :closable="false" />
          </div>
        </el-card>
      </el-col>
      <el-col :span="16">
        <el-card shadow="never">
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px;">
            <span style="font-weight: 600;">内容预览</span>
            <el-button v-if="task?.status === 'completed'" type="primary" @click="router.push(`/documents/${docId}/edit`)">编辑文档</el-button>
          </div>
          <div v-if="task?.status === 'completed'" style="white-space: pre-wrap; line-height: 1.8; min-height: 400px;">
            {{ task.result_content }}
          </div>
          <div v-else style="min-height: 400px; display: flex; align-items: center; justify-content: center;">
            <el-icon class="is-loading" style="font-size: 24px; color: #534ab7;">
              <Loading />
            </el-icon>
            <span style="margin-left: 8px; color: #888;">正在生成中...</span>
          </div>
        </el-card>
      </el-col>
    </el-row>
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

const stepMap = { init: 0, intent: 1, rag: 2, outline: 3, generate: 4, validate: 5, format: 6, done: 6 }
const currentStepIndex = computed(() => stepMap[task.value?.current_step] || 0)
const progressStatus = computed(() => {
  if (task.value?.status === 'completed') return 'success'
  if (task.value?.status === 'failed') return 'exception'
  return undefined
})

onMounted(async () => {
  // Fetch initial task status
  task.value = await api.get(`/documents/${docId}/task`)
  // Connect WebSocket for live updates
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  const wsUrl = `${protocol}//${window.location.host}/ws/generation/${task.value.id}`
  ws = new WebSocket(wsUrl)
  ws.onmessage = (event) => {
    const data = JSON.parse(event.data)
    task.value = { ...task.value, ...data }
  }
  ws.onclose = () => {
    // Fallback: poll API every 2s
    pollInterval = setInterval(async () => {
      task.value = await api.get(`/documents/${docId}/task`)
      if (['completed', 'failed', 'cancelled'].includes(task.value.status)) {
        clearInterval(pollInterval)
      }
    }, 2000)
  }
})

let pollInterval
onUnmounted(() => {
  if (ws) ws.close()
  if (pollInterval) clearInterval(pollInterval)
})
</script>
