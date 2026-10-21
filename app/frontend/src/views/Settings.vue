<template>
  <div style="padding: 24px;">
    <div style="margin-bottom: 24px;">
      <h2 style="margin: 0; font-size: 18px;">设置</h2>
    </div>
    <el-row :gutter="24">
      <el-col :span="10">
        <el-card shadow="never">
          <div style="font-weight: 600; margin-bottom: 16px;">LLM 配置列表</div>
          <div v-for="c in configs" :key="c.id" style="padding: 12px; border: 1px solid #e4e4e7; border-radius: 8px; margin-bottom: 8px; cursor: pointer;"
            :style="{ borderColor: c.is_active ? '#534ab7' : '#e4e4e7', background: c.is_active ? '#eeedfe' : '#fff' }"
            @click="selectConfig(c)"
          >
            <div style="display: flex; justify-content: space-between; align-items: center;">
              <span style="font-weight: 500; font-size: 14px;">{{ c.name }}</span>
              <el-tag v-if="c.is_active" type="success" size="small">已激活</el-tag>
            </div>
            <div style="font-size: 12px; color: #888; margin-top: 4px;">{{ c.provider }} · {{ c.chat_model }}</div>
          </div>
          <el-button style="width: 100%; margin-top: 8px;" @click="showForm = true; editing = null">+ 新增配置</el-button>
        </el-card>
      </el-col>
      <el-col :span="14">
        <el-card shadow="never">
          <div style="font-weight: 600; margin-bottom: 16px;">{{ editing ? '编辑配置' : '新增配置' }}</div>
          <el-form v-if="showForm" :model="form" label-width="100px">
            <el-form-item label="配置名称"><el-input v-model="form.name" placeholder="DeepSeek-Chat" /></el-form-item>
            <el-form-item label="Provider">
              <el-select v-model="form.provider" style="width: 100%;">
                <el-option label="DeepSeek" value="deepseek" />
                <el-option label="通义千问" value="qwen" />
                <el-option label="智谱GLM" value="zhipu" />
                <el-option label="自定义" value="custom" />
              </el-select>
            </el-form-item>
            <el-form-item v-if="form.provider === 'custom'" label="API地址"><el-input v-model="form.api_url" placeholder="https://your-api.com/v1" /></el-form-item>
            <el-form-item label="API Key"><el-input v-model="form.api_key" type="password" show-password placeholder="sk-..." /></el-form-item>
            <el-form-item label="对话模型"><el-input v-model="form.chat_model" placeholder="deepseek-chat" /></el-form-item>
            <el-form-item label="Embedding模型"><el-input v-model="form.embedding_model" placeholder="text-embedding-v2" /></el-form-item>
            <el-form-item>
              <el-button @click="handleTest" :loading="testing">测试连通性</el-button>
              <el-button type="primary" @click="handleSave">保存</el-button>
              <el-button v-if="editing" @click="handleActivate">设为激活</el-button>
            </el-form-item>
            <div v-if="testResult" style="margin-top: 8px;">
              <el-alert
                :type="testResult.chat_ok ? 'success' : 'error'"
                :title="`Chat: ${testResult.chat_ok ? 'OK (' + testResult.chat_latency_ms + 'ms)' : testResult.chat_error}`"
                :closable="false" style="margin-bottom: 8px;"
              />
              <el-alert
                v-if="testResult.embedding_ok !== undefined"
                :type="testResult.embedding_ok ? 'success' : 'error'"
                :title="`Embedding: ${testResult.embedding_ok ? 'OK (' + testResult.embedding_latency_ms + 'ms)' : testResult.embedding_error}`"
                :closable="false"
              />
            </div>
          </el-form>
          <div v-else style="color: #888; text-align: center; padding: 40px;">点击「新增配置」或选择已有配置</div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import api from '../api'
import { ElMessage } from 'element-plus'

const configs = ref([])
const showForm = ref(false)
const editing = ref(null)
const testing = ref(false)
const testResult = ref(null)

const form = ref({
  name: '',
  provider: 'deepseek',
  api_url: '',
  api_key: '',
  chat_model: 'deepseek-chat',
  embedding_model: '',
})

onMounted(loadConfigs)

async function loadConfigs() {
  configs.value = await api.get('/llm/configs')
}

function selectConfig(c) {
  editing.value = c
  showForm.value = true
  form.value = { ...c, api_key: '' }
}

async function handleTest() {
  testing.value = true
  testResult.value = null
  try {
    testResult.value = await api.post('/llm/test', form.value)
  } finally {
    testing.value = false
  }
}

async function handleSave() {
  if (editing.value) {
    await api.put(`/llm/configs/${editing.value.id}`, form.value)
  } else {
    await api.post('/llm/configs', form.value)
  }
  ElMessage.success('保存成功')
  await loadConfigs()
  showForm.value = false
}

async function handleActivate() {
  if (!editing.value) return
  await api.put(`/llm/configs/${editing.value.id}`, { is_active: true })
  ElMessage.success('已激活')
  await loadConfigs()
}
</script>
