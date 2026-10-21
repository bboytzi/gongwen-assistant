<template>
  <div style="padding: 24px;">
    <div style="margin-bottom: 24px;">
      <h2 style="margin: 0; font-size: 18px;">新建请示</h2>
    </div>
    <el-card shadow="never" style="max-width: 800px;">
      <el-form :model="form" label-width="120px">
        <el-form-item label="请示类型">
          <el-select v-model="form.doc_category" placeholder="请选择">
            <el-option label="采购类" value="procurement" />
            <el-option label="人事类" value="personnel" />
            <el-option label="资金类" value="fund" />
            <el-option label="项目类" value="project" />
            <el-option label="制度类" value="regulation" />
          </el-select>
        </el-form-item>

        <el-form-item v-if="form.doc_category === 'procurement'" label="采购场景">
          <el-select v-model="form.procurement_scenario" placeholder="请选择采购场景">
            <el-option label="项目执行" value="project_execution" />
            <el-option label="要素组织" value="element_org" />
            <el-option label="联合采购" value="joint" />
            <el-option label="行政后勤" value="admin" />
            <el-option label="甲方指定" value="client_specified" />
          </el-select>
        </el-form-item>

        <el-form-item label="标题" required>
          <el-input v-model="form.title" placeholder="关于申请采购办公设备的请示" />
        </el-form-item>

        <el-divider>关键要素</el-divider>

        <el-form-item label="事由">
          <el-input v-model="form.key_elements['事由']" type="textarea" :rows="2" placeholder="因业务扩展需要采购办公设备..." />
        </el-form-item>
        <el-form-item label="预算金额">
          <el-input-number v-model="form.budget_amount" :min="0" :precision="2" :step="1" style="width: 200px;" />
          <span style="margin-left: 8px; color: #888;">万元</span>
        </el-form-item>
        <el-form-item v-if="form.budget_amount" label="采购方式">
          <el-alert :title="procurementHint" :type="'success'" :closable="false" style="width: 400px;" />
        </el-form-item>
        <el-form-item label="资金来源">
          <el-input v-model="form.key_elements['资金来源']" placeholder="办公经费" />
        </el-form-item>
        <el-form-item label="涉及对象">
          <el-input v-model="form.key_elements['涉及对象']" placeholder="信息部" />
        </el-form-item>
        <el-form-item label="依据">
          <el-input v-model="form.key_elements['依据']" placeholder="公司固定资产管理办法" />
        </el-form-item>

        <el-divider>生成配置</el-divider>

        <el-form-item label="引用知识库">
          <el-checkbox-group v-model="form.source_kb_ids">
            <el-checkbox v-for="kb in companyKbs" :key="kb.id" :label="kb.id">{{ kb.name }}</el-checkbox>
            <el-checkbox v-for="kb in personalKbs" :key="kb.id" :label="kb.id">{{ kb.name }}</el-checkbox>
          </el-checkbox-group>
        </el-form-item>
        <el-form-item label="Word模板">
          <el-select v-model="form.template_id" placeholder="选择模板" clearable style="width: 300px;">
            <el-option v-for="t in templates" :key="t.id" :label="t.name" :value="t.id" />
          </el-select>
        </el-form-item>

        <el-form-item>
          <el-button type="primary" :loading="submitting" @click="handleSubmit">生成请示材料</el-button>
        </el-form-item>
      </el-form>
    </el-card>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import api from '../api'
import { ElMessage } from 'element-plus'

const router = useRouter()
const submitting = ref(false)
const companyKbs = ref([])
const personalKbs = ref([])
const templates = ref([])

const form = ref({
  doc_category: 'procurement',
  procurement_scenario: '',
  title: '',
  key_elements: {},
  budget_amount: null,
  source_kb_ids: [],
  template_id: null,
})

const procurementHint = computed(() => {
  const amt = form.value.budget_amount
  if (amt == null) return ''
  if (amt < 30) return '直接委托 — 预算不足30万元，依据《采购管理办法》第十五条'
  if (amt < 50) return '询价 — 预算30-50万元，依据《采购管理办法》第十六条'
  if (amt < 200) return '公开采购 — 预算50-200万元，依据《采购管理办法》第十七条'
  return '招标 — 预算200万元以上，依据《采购管理办法》第十八条'
})

onMounted(async () => {
  const data = await api.get('/kb/bases')
  companyKbs.value = data.company
  personalKbs.value = data.personal
  // Default: check all company KBs
  form.value.source_kb_ids = companyKbs.value.map(kb => kb.id)
  templates.value = await api.get('/documents/templates')
})

async function handleSubmit() {
  if (!form.value.title) {
    ElMessage.warning('请输入标题')
    return
  }
  submitting.value = true
  try {
    const doc = await api.post('/documents', form.value)
    // Start generation
    await api.post(`/documents/${doc.id}/generate`)
    ElMessage.success('生成任务已创建')
    router.push(`/documents/${doc.id}/generate`)
  } finally {
    submitting.value = false
  }
}
</script>
