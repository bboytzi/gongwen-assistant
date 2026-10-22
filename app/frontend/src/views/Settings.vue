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
          <el-form v-if="showForm" :model="form" label-width="110px">
            <el-form-item label="配置名称"><el-input v-model="form.name" placeholder="TokenHub-DeepSeek" /></el-form-item>
            <el-form-item label="Provider">
              <el-select v-model="form.provider" style="width: 100%;" @change="onProviderChange">
                <el-option label="腾讯云 TokenHub" value="tokenhub" />
                <el-option label="DeepSeek" value="deepseek" />
                <el-option label="通义千问" value="qwen" />
                <el-option label="智谱GLM" value="zhipu" />
                <el-option label="自定义" value="custom" />
              </el-select>
            </el-form-item>
            <el-form-item label="API地址">
              <el-input v-model="form.api_url" placeholder="https://tokenhub-intl.tencentcloudmaas.com/plan/v3" />
              <div class="field-hint">对话接口。填 base 或完整地址均可，系统会自动补全 /chat/completions</div>
            </el-form-item>
            <el-form-item label="API Key"><el-input v-model="form.api_key" type="password" show-password placeholder="sk-..." /></el-form-item>
            <el-form-item label="对话模型"><el-input v-model="form.chat_model" placeholder="deepseek/deepseek-flash" /></el-form-item>
            <el-form-item label="Embedding模型">
              <el-input v-model="form.embedding_model" placeholder="kinfra-text-embedding-0.6b" />
              <div class="field-hint">留空则不做向量化，检索降级为关键词匹配</div>
            </el-form-item>
            <el-form-item label="Embedding地址">
              <el-input v-model="form.embedding_url" placeholder="https://tokenhub-intl.tencentcloudmaas.com/v1" />
              <div class="field-hint">向量接口地址。与对话地址不同时必填，留空则复用 API 地址</div>
            </el-form-item>
            <el-form-item label="Embedding Key">
              <el-input
                v-model="form.embedding_api_key"
                type="password"
                show-password
                :placeholder="editing && editing.has_embedding_key ? '已配置，留空则不修改' : '留空则复用上面的 API Key'"
              />
              <div class="field-hint">
                向量接口与对话接口使用不同 Key 时填写。
                腾讯云 TokenHub 的 Token Plan Key 只能调 /plan/v3，调 /v1 向量接口需另建一个 Key
              </div>
            </el-form-item>
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
              <div v-if="testResult.resolved_chat_url" class="url-echo">
                实际请求 {{ testResult.resolved_chat_url }}
              </div>
              <el-alert
                v-if="testResult.embedding_ok !== undefined"
                :type="testResult.embedding_ok ? 'success' : (testResult.embedding_dim ? 'warning' : 'info')"
                :title="`Embedding: ${testResult.embedding_ok ? 'OK (' + testResult.embedding_latency_ms + 'ms' + (testResult.embedding_dim ? ', ' + testResult.embedding_dim + ' 维' : '') + ')' : testResult.embedding_error}`"
                :closable="false"
              />
              <div v-if="testResult.resolved_embedding_url" class="url-echo">
                实际请求 {{ testResult.resolved_embedding_url }}
              </div>
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
const providerDefaults = ref({})

const form = ref({
  name: '',
  provider: 'tokenhub',
  api_url: '',
  api_key: '',
  chat_model: '',
  embedding_model: '',
  embedding_url: '',
  embedding_api_key: '',
})

onMounted(async () => {
  await loadConfigs()
  try {
    const data = await api.get('/llm/providers')
    providerDefaults.value = data.defaults || {}
  } catch {
    // 老版本后端没有 defaults 字段，忽略
  }
})

async function loadConfigs() {
  configs.value = await api.get('/llm/configs')
}

function onProviderChange(provider) {
  const d = providerDefaults.value[provider]
  if (!d) return
  form.value.api_url = d.api_url || ''
  form.value.chat_model = d.chat_model || ''
  form.value.embedding_model = d.embedding_model || ''
  form.value.embedding_url = d.embedding_url || ''
}

function selectConfig(c) {
  editing.value = c
  showForm.value = true
  // 两个 Key 都不回显明文，留空表示不修改
  form.value = { ...c, api_key: '', embedding_api_key: '' }
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
  const payload = { ...form.value }
  // 编辑时若未重新填写，不提交这些字段，否则会把已存的 Key 覆盖成空串
  if (editing.value && !payload.api_key) {
    delete payload.api_key
  }
  if (editing.value && !payload.embedding_api_key) {
    delete payload.embedding_api_key
  }
  if (editing.value) {
    await api.put(`/llm/configs/${editing.value.id}`, payload)
  } else {
    await api.post('/llm/configs', payload)
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

<style scoped>
.field-hint {
  font-size: 11px;
  color: #999;
  line-height: 1.5;
  margin-top: 2px;
}

.url-echo {
  font-size: 11px;
  color: #999;
  font-family: monospace;
  word-break: break-all;
  margin: -4px 0 8px 0;
}
</style>
