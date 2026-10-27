<template>
  <div class="page">
    <div class="page-head">
      <div>
        <div class="crumb">资源 / 设置</div>
        <h1 class="page-title">{{ tab === 'brand' ? '系统外观' : '模型设置' }}</h1>
        <div class="page-sub">
          {{ tab === 'brand'
            ? '修改系统名称与标识，全站与登录页同步生效'
            : '配置对话与向量模型，生成和检索都依赖激活的配置' }}
        </div>
      </div>
    </div>

    <div class="tabs">
      <span class="tab" :class="{ active: tab === 'model' }" @click="tab = 'model'">模型配置</span>
      <span v-if="isAdmin" class="tab" :class="{ active: tab === 'brand' }" @click="switchToBrand">系统外观</span>
    </div>

    <div v-show="tab === 'model'" class="layout">
      <div class="list-col">
        <div class="card card-pad">
          <div class="card-title">配置列表</div>

          <div
            v-for="c in configs"
            :key="c.id"
            class="cfg"
            :class="{ active: c.is_active, editing: editing?.id === c.id }"
            @click="selectConfig(c)"
          >
            <div class="cfg-head">
              <span class="cfg-name">{{ c.name }}</span>
              <span v-if="c.is_active" class="cfg-badge">已激活</span>
            </div>
            <div class="cfg-meta">{{ providerLabel(c.provider) }}</div>
            <div class="cfg-meta">对话 {{ c.chat_model }}</div>
            <div class="cfg-meta">
              向量 {{ c.embedding_model || '未配置' }}
              <span v-if="c.has_embedding_key" class="cfg-key">独立 Key</span>
            </div>
          </div>

          <div v-if="configs.length === 0" class="cfg-empty">还没有配置</div>

          <el-button class="add-btn" @click="startCreate">新增配置</el-button>
        </div>
      </div>

      <div class="form-col">
        <div v-if="!showForm" class="card card-pad placeholder">
          <div class="placeholder-title">选择左侧配置进行编辑</div>
          <div class="placeholder-sub">或点击「新增配置」开始</div>
        </div>

        <div v-else class="card card-pad">
          <div class="card-title">{{ editing ? '编辑配置' : '新增配置' }}</div>

          <div class="field">
            <label>配置名称</label>
            <el-input v-model="form.name" placeholder="阿里云百炼" />
          </div>

          <div class="field">
            <label>服务商</label>
            <el-select v-model="form.provider" style="width: 100%" @change="onProviderChange">
              <el-option label="阿里云百炼" value="qwen" />
              <el-option label="腾讯云 TokenHub" value="tokenhub" />
              <el-option label="DeepSeek" value="deepseek" />
              <el-option label="智谱 GLM" value="zhipu" />
              <el-option label="自定义" value="custom" />
            </el-select>
            <div class="hint">切换服务商会自动填入该家的默认地址与模型名</div>
          </div>

          <div class="field">
            <label>API 地址</label>
            <el-input v-model="form.api_url" placeholder="https://dashscope.aliyuncs.com/compatible-mode/v1" />
            <div class="hint">填 base 或完整接口地址均可，系统自动补全 /chat/completions</div>
          </div>

          <div class="field">
            <label>API Key</label>
            <el-input
              v-model="form.api_key"
              type="password"
              show-password
              :placeholder="editing ? '已配置，留空则不修改' : 'sk-...'"
            />
          </div>

          <div class="field">
            <label>对话模型</label>
            <el-input v-model="form.chat_model" placeholder="qwen-plus" />
          </div>

          <div class="divider"></div>

          <div class="field">
            <label>Embedding 模型</label>
            <el-input v-model="form.embedding_model" placeholder="text-embedding-v4" />
            <div class="hint">留空则不做向量化，检索降级为关键词匹配</div>
          </div>

          <div class="field">
            <label>Embedding 地址</label>
            <el-input v-model="form.embedding_url" placeholder="留空则复用 API 地址" />
            <div class="hint">向量接口与对话接口不同源时填写</div>
          </div>

          <div class="field">
            <label>Embedding Key</label>
            <el-input
              v-model="form.embedding_api_key"
              type="password"
              show-password
              :placeholder="editing && editing.has_embedding_key ? '已配置，留空则不修改' : '留空则复用上面的 API Key'"
            />
            <div class="hint">腾讯云 TokenHub 的套餐 Key 不能调向量接口，需另填</div>
          </div>

          <div class="actions">
            <el-button @click="handleTest" :loading="testing">测试连通性</el-button>
            <el-button type="primary" @click="handleSave">保存</el-button>
            <el-button v-if="editing && !editing.is_active" @click="handleActivate">设为激活</el-button>
            <el-button v-if="editing" class="del" @click="handleDelete">删除</el-button>
          </div>

          <div v-if="testResult" class="result">
            <div class="res-line" :style="resStyle(testResult.chat_ok)">
              <span class="res-tag">{{ testResult.chat_ok ? '对话正常' : '对话失败' }}</span>
              <span class="res-text">
                {{ testResult.chat_ok
                  ? `${testResult.chat_latency_ms} ms`
                  : testResult.chat_error }}
              </span>
            </div>
            <div v-if="testResult.resolved_chat_url" class="res-url">{{ testResult.resolved_chat_url }}</div>

            <div
              v-if="testResult.embedding_ok !== undefined"
              class="res-line"
              :style="resStyle(testResult.embedding_ok)"
            >
              <span class="res-tag">{{ testResult.embedding_ok ? '向量正常' : '向量不可用' }}</span>
              <span class="res-text">
                {{ testResult.embedding_ok
                  ? `${testResult.embedding_latency_ms} ms · ${testResult.embedding_dim} 维`
                  : testResult.embedding_error }}
              </span>
            </div>
            <div v-if="testResult.resolved_embedding_url" class="res-url">{{ testResult.resolved_embedding_url }}</div>
          </div>
        </div>
      </div>
    </div>

    <div v-if="tab === 'brand'" class="brand-wrap">
      <div class="card card-pad">
        <div class="card-title">系统名称</div>
        <div class="field">
          <label>名称</label>
          <el-input v-model="brandForm.name" placeholder="公文辅助系统" maxlength="50" show-word-limit />
          <div class="hint">显示在顶栏、登录页与浏览器标签，留空则恢复默认</div>
        </div>
        <div class="field">
          <label>副标题</label>
          <el-input v-model="brandForm.subtitle" placeholder="公文起草 · 制度检索 · 知识库" maxlength="100" />
          <div class="hint">仅登录页显示</div>
        </div>
      </div>

      <div class="card card-pad">
        <div class="card-title">系统标识</div>

        <div class="logo-row">
          <div class="logo-preview">
            <Logo :size="56" />
          </div>
          <div class="logo-side">
            <div class="logo-tip">
              未上传时使用内置方印。建议上传正方形图片，浅色或透明底，
              尺寸不小于 64×64。
            </div>
            <div class="logo-actions">
              <el-upload
                :auto-upload="false"
                :show-file-list="false"
                accept=".png,.jpg,.jpeg,.svg,.webp"
                :on-change="onLogoChange"
              >
                <el-button>上传图片</el-button>
              </el-upload>
              <el-button v-if="brandForm.logo" @click="brandForm.logo = null">恢复内置图案</el-button>
            </div>
            <div class="hint">支持 PNG / JPG / SVG / WEBP，不超过 200KB</div>
          </div>
        </div>
      </div>

      <div class="brand-actions">
        <el-button type="primary" :loading="savingBrand" @click="saveBrand">保存并应用</el-button>
        <el-button @click="switchToBrand">撤销未保存的修改</el-button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import api from '../api'
import Logo from '../components/Logo.vue'
import { useUserStore } from '../store/user'
import { useSystemStore } from '../store/system'

const userStore = useUserStore()
const system = useSystemStore()
const isAdmin = computed(() => userStore.user?.role === 'admin')

const tab = ref('model')

const configs = ref([])
const showForm = ref(false)
const editing = ref(null)
const testing = ref(false)
const testResult = ref(null)
const providerDefaults = ref({})

const brandForm = ref({ name: '', subtitle: '', logo: null })
const savingBrand = ref(false)

const form = ref({
  name: '',
  provider: 'qwen',
  api_url: '',
  api_key: '',
  chat_model: '',
  embedding_model: '',
  embedding_url: '',
  embedding_api_key: '',
})

const PROVIDER_LABELS = {
  qwen: '阿里云百炼',
  tokenhub: '腾讯云 TokenHub',
  deepseek: 'DeepSeek',
  zhipu: '智谱 GLM',
  custom: '自定义',
}

function providerLabel(p) {
  return PROVIDER_LABELS[p] || p
}

onMounted(async () => {
  await userStore.fetchMe()
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

function switchToBrand() {
  if (tab.value !== 'brand') {
    // 每次进入都从 store 取当前生效值，丢弃上次未保存的修改
    brandForm.value = {
      name: system.name,
      subtitle: system.subtitle,
      logo: system.logo,
    }
  }
  tab.value = tab.value === 'brand' ? 'model' : 'brand'
}

function onLogoChange(file) {
  const raw = file.raw
  if (!raw) return
  if (raw.size > 200 * 1024) {
    ElMessage.error('图片不能超过 200KB，请先压缩')
    return
  }
  const reader = new FileReader()
  reader.onload = () => {
    brandForm.value.logo = reader.result
  }
  reader.onerror = () => ElMessage.error('读取图片失败')
  reader.readAsDataURL(raw)
}

async function saveBrand() {
  savingBrand.value = true
  try {
    const data = await api.put('/settings', {
      system_name: brandForm.value.name,
      system_subtitle: brandForm.value.subtitle,
      system_logo: brandForm.value.logo || '',
    })
    system.apply(data)
    ElMessage.success('已应用')
  } catch {
    // 拦截器已提示
  } finally {
    savingBrand.value = false
  }
}

function startCreate() {
  editing.value = null
  showForm.value = true
  testResult.value = null
  form.value = {
    name: '',
    provider: 'qwen',
    api_url: '',
    api_key: '',
    chat_model: '',
    embedding_model: '',
    embedding_url: '',
    embedding_api_key: '',
  }
  onProviderChange('qwen')
}

function selectConfig(c) {
  editing.value = c
  showForm.value = true
  testResult.value = null
  // 两个 Key 都不回显明文，留空表示不修改
  form.value = { ...c, api_key: '', embedding_api_key: '' }
}

function onProviderChange(provider) {
  const d = providerDefaults.value[provider]
  if (!d) return
  form.value.api_url = d.api_url || ''
  form.value.chat_model = d.chat_model || ''
  form.value.embedding_model = d.embedding_model || ''
  form.value.embedding_url = d.embedding_url || ''
}

async function handleTest() {
  testing.value = true
  testResult.value = null
  try {
    const payload = { ...form.value, config_id: editing.value?.id || null }
    if (!payload.api_key) delete payload.api_key
    if (!payload.embedding_api_key) delete payload.embedding_api_key
    testResult.value = await api.post('/llm/test', payload)
  } finally {
    testing.value = false
  }
}

async function handleSave() {
  const payload = { ...form.value }
  if (editing.value && !payload.api_key) delete payload.api_key
  if (editing.value && !payload.embedding_api_key) delete payload.embedding_api_key

  try {
    if (editing.value) {
      await api.put(`/llm/configs/${editing.value.id}`, payload)
    } else {
      await api.post('/llm/configs', payload)
    }
    ElMessage.success('保存成功')
    await loadConfigs()
    showForm.value = false
    editing.value = null
  } catch { /* 拦截器已提示 */ }
}

async function handleActivate() {
  if (!editing.value) return
  try {
    await api.put(`/llm/configs/${editing.value.id}`, { is_active: true })
    ElMessage.success('已激活')
    await loadConfigs()
  } catch { /* 拦截器已提示 */ }
}

async function handleDelete() {
  try {
    await ElMessageBox.confirm(`确认删除配置「${editing.value.name}」？`, '删除配置', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消',
    })
  } catch {
    return
  }
  try {
    await api.delete(`/llm/configs/${editing.value.id}`)
    ElMessage.success('已删除')
    showForm.value = false
    editing.value = null
    await loadConfigs()
  } catch { /* 拦截器已提示 */ }
}

function resStyle(ok) {
  return ok
    ? { color: 'var(--ok)', background: 'var(--ok-soft)' }
    : { color: 'var(--err)', background: 'var(--err-soft)' }
}
</script>

<style scoped>
.tabs {
  display: flex;
  gap: 22px;
  border-bottom: 0.5px solid var(--line);
  margin-bottom: 16px;
}

.tab {
  padding: 0 2px 9px;
  font-size: 13px;
  color: var(--ink-3);
  cursor: pointer;
  border-bottom: 1.5px solid transparent;
  margin-bottom: -0.5px;
}

.tab.active {
  color: var(--seal);
  border-bottom-color: var(--seal);
}

.layout {
  display: flex;
  gap: 16px;
  align-items: flex-start;
}

.list-col {
  width: 252px;
  flex-shrink: 0;
}

.form-col {
  flex: 1;
  min-width: 0;
}

.card-title {
  margin-bottom: 12px;
}

.cfg {
  border: 0.5px solid var(--line);
  border-radius: var(--r-sm);
  padding: 10px 12px;
  margin-bottom: 8px;
  cursor: pointer;
  background: var(--paper-3);
  transition: border-color 0.15s;
}

.cfg:hover {
  border-color: var(--gold-line);
}

.cfg.active {
  border-color: var(--seal-line);
  background: var(--seal-soft);
}

.cfg.editing {
  border-color: var(--gold);
}

.cfg-head {
  display: flex;
  align-items: center;
  margin-bottom: 4px;
}

.cfg-name {
  font-size: 13px;
  color: var(--ink);
}

.cfg-badge {
  margin-left: auto;
  font-size: 10px;
  color: var(--ok);
  background: var(--ok-soft);
  padding: 1px 6px;
  border-radius: 2px;
}

.cfg-meta {
  font-size: 11px;
  color: var(--ink-4);
  line-height: 1.7;
}

.cfg-key {
  color: var(--warn);
  margin-left: 4px;
}

.cfg-empty {
  font-size: 12px;
  color: var(--ink-4);
  padding: 10px 0;
}

.add-btn {
  width: 100%;
  margin-top: 4px;
}

.placeholder {
  padding: 44px 20px;
  text-align: center;
}

.placeholder-title {
  font-size: 13px;
  color: var(--ink-3);
}

.placeholder-sub {
  font-size: 11px;
  color: var(--ink-4);
  margin-top: 5px;
}

.field {
  margin-bottom: 12px;
}

.field label {
  display: block;
  font-size: 11px;
  color: var(--ink-3);
  margin-bottom: 5px;
}

.divider {
  height: 1px;
  background: var(--line-2);
  margin: 16px 0 14px;
}

.actions {
  display: flex;
  gap: 8px;
  margin-top: 16px;
}

.del {
  margin-left: auto;
  color: var(--ink-3) !important;
}

.result {
  margin-top: 14px;
  padding-top: 13px;
  border-top: 0.5px solid var(--line-2);
}

.res-line {
  display: flex;
  align-items: flex-start;
  gap: 9px;
  padding: 7px 10px;
  border-radius: var(--r-sm);
  margin-bottom: 5px;
}

.res-tag {
  font-size: 11px;
  white-space: nowrap;
  padding-top: 1px;
}

.res-text {
  font-size: 11px;
  line-height: 1.6;
  word-break: break-all;
}

.res-url {
  font-size: 10px;
  color: var(--ink-4);
  font-family: monospace;
  word-break: break-all;
  padding: 0 2px 8px;
}

.brand-wrap {
  max-width: 620px;
}

.brand-wrap .card {
  margin-bottom: 12px;
}

.logo-row {
  display: flex;
  gap: 18px;
  align-items: flex-start;
}

.logo-preview {
  width: 82px;
  height: 82px;
  border: 0.5px solid var(--line);
  border-radius: var(--r-sm);
  background: var(--paper-3);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.logo-side {
  flex: 1;
  min-width: 0;
}

.logo-tip {
  font-size: 11px;
  color: var(--ink-3);
  line-height: 1.7;
  margin-bottom: 10px;
}

.logo-actions {
  display: flex;
  gap: 8px;
  margin-bottom: 6px;
}

.brand-actions {
  display: flex;
  gap: 9px;
}
</style>
