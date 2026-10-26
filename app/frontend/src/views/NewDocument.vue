<template>
  <div class="page">
    <div class="page-head">
      <div>
        <div class="crumb">工作台 / 新建请示</div>
        <h1 class="page-title">新建请示</h1>
        <div class="page-sub">填写关键要素，系统据此检索制度依据并生成正文</div>
      </div>
    </div>

    <div class="layout">
      <div class="form-col">
        <div class="card card-pad block">
          <div class="card-title">基本信息</div>
          <div class="row2">
            <div class="field">
              <label>请示类型</label>
              <el-select v-model="form.doc_category" style="width: 100%">
                <el-option label="采购类" value="procurement" />
                <el-option label="人事类" value="personnel" />
                <el-option label="资金类" value="fund" />
                <el-option label="项目类" value="project" />
                <el-option label="制度类" value="regulation" />
              </el-select>
            </div>
            <div v-if="form.doc_category === 'procurement'" class="field">
              <label>采购场景</label>
              <el-select v-model="form.procurement_scenario" placeholder="选择场景" style="width: 100%">
                <el-option label="项目执行" value="project_execution" />
                <el-option label="要素组织" value="element_org" />
                <el-option label="联合采购" value="joint" />
                <el-option label="行政后勤" value="admin" />
                <el-option label="甲方指定" value="client_specified" />
              </el-select>
            </div>
          </div>
          <div class="field">
            <label>标题 <span class="req">必填</span></label>
            <el-input v-model="form.title" placeholder="关于申请采购办公设备的请示" />
          </div>
        </div>

        <div class="card card-pad block">
          <div class="card-title">关键要素</div>
          <div class="field">
            <label>事由</label>
            <el-input
              v-model="form.key_elements['事由']"
              type="textarea"
              :rows="2"
              placeholder="因业务需要，拟采购……"
            />
          </div>
          <div class="row2">
            <div class="field">
              <label>预算金额（万元）</label>
              <el-input-number
                v-model="form.budget_amount"
                :min="0"
                :precision="2"
                :controls="false"
                placeholder="15"
                style="width: 100%"
              />
            </div>
            <div class="field">
              <label>资金来源</label>
              <el-input v-model="form.key_elements['资金来源']" placeholder="项目经费" />
            </div>
          </div>
          <div class="row2">
            <div class="field">
              <label>涉及对象</label>
              <el-input v-model="form.key_elements['涉及对象']" placeholder="信息技术部" />
            </div>
            <div class="field">
              <label>依据</label>
              <el-input v-model="form.key_elements['依据']" placeholder="采购管理办法" />
            </div>
          </div>
        </div>

        <div v-if="advice" class="advice">
          <div class="advice-head">
            <div class="advice-dot"></div>
            <span class="advice-title">建议采用{{ advice.method }}</span>
          </div>
          <div class="advice-text">{{ advice.text }}</div>
        </div>

        <div class="card card-pad block">
          <div class="card-title">生成配置</div>
          <div class="field">
            <label>引用知识库</label>
            <el-select
              v-model="form.source_kb_ids"
              multiple
              collapse-tags
              collapse-tags-tooltip
              placeholder="留空则检索全部"
              style="width: 100%"
            >
              <el-option
                v-for="kb in allKbs"
                :key="kb.id"
                :label="kb.name"
                :value="kb.id"
              />
            </el-select>
            <div class="hint">留空则检索全部可访问的知识库</div>
          </div>
          <div class="field">
            <label>Word 模板</label>
            <el-select v-model="form.template_id" placeholder="系统默认公文格式" clearable style="width: 100%">
              <el-option v-for="t in templates" :key="t.id" :label="t.name" :value="t.id" />
            </el-select>
          </div>
        </div>

        <el-button
          type="primary"
          class="submit"
          :loading="submitting"
          @click="handleSubmit"
        >
          生成请示材料
        </el-button>
      </div>

      <div class="preview-col">
        <div class="preview-head">
          <span class="preview-label">实时预览</span>
          <span class="preview-note">A4 · 方正小标宋 / 仿宋</span>
        </div>

        <div class="paper">
          <div class="paper-title">{{ form.title || '关于……的请示' }}</div>
          <div class="paper-to">公司领导：</div>
          <p class="paper-p">
            {{ form.key_elements['事由'] || '（此处填写请示事由）' }}。现将有关情况请示如下。
          </p>
          <div class="paper-h">一、请示事由</div>
          <p class="paper-p">
            现有条件已不能满足当前需要，拟{{ actionWord }}，预算金额
            {{ form.budget_amount ? form.budget_amount + ' 万元' : '（待填）' }}，
            资金来源为{{ form.key_elements['资金来源'] || '（待填）' }}。
          </p>
          <div class="paper-h">二、政策依据</div>
          <p class="paper-p">
            根据《{{ form.key_elements['依据'] || '采购管理办法' }}》{{ advice ? advice.clause : '第×条' }}规定，
            本项目拟采用{{ advice ? advice.method : '（待定）' }}方式组织实施。
          </p>
          <div class="paper-h">三、请示事项</div>
          <p class="paper-p">妥否，请批示。</p>
          <div class="paper-sign">
            <div>{{ form.key_elements['涉及对象'] || '××部门' }}</div>
            <div>{{ today }}</div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import api from '../api'

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

const allKbs = computed(() => [...companyKbs.value, ...personalKbs.value])

const today = computed(() => {
  const d = new Date()
  return `${d.getFullYear()} 年 ${d.getMonth() + 1} 月 ${d.getDate()} 日`
})

const actionWord = computed(() => {
  return {
    procurement: '采购相关设备物资',
    personnel: '调整人员配置',
    fund: '申请专项资金',
    project: '启动相关项目',
    regulation: '制定相关制度',
  }[form.value.doc_category] || '办理相关事项'
})

// 预算自动匹配采购方式，依据《采购管理办法》
const advice = computed(() => {
  const amt = form.value.budget_amount
  if (amt == null || amt === 0) return null
  if (amt < 30) {
    return {
      method: '直接委托',
      clause: '第十五条',
      text: `预算 ${amt} 万元不足 30 万元，依据《采购管理办法》第十五条，可采用直接委托方式组织实施。`,
    }
  }
  if (amt < 50) {
    return {
      method: '询价',
      clause: '第十六条',
      text: `预算 ${amt} 万元在 30 至 50 万元之间，依据《采购管理办法》第十六条，应采用询价方式。`,
    }
  }
  if (amt < 200) {
    return {
      method: '公开采购',
      clause: '第十七条',
      text: `预算 ${amt} 万元在 50 至 200 万元之间，依据《采购管理办法》第十七条，应采用公开采购方式。`,
    }
  }
  return {
    method: '招标',
    clause: '第十八条',
    text: `预算 ${amt} 万元超过 200 万元，依据《采购管理办法》第十八条，应通过招标方式组织实施。`,
  }
})

onMounted(async () => {
  try {
    const data = await api.get('/kb/bases')
    companyKbs.value = data.company || []
    personalKbs.value = data.personal || []
  } catch { /* 知识库拉取失败不阻断填表 */ }

  try {
    templates.value = await api.get('/documents/templates')
  } catch { /* 模板为空时用默认格式 */ }
})

async function handleSubmit() {
  if (!form.value.title.trim()) {
    ElMessage.warning('请填写标题')
    return
  }

  submitting.value = true
  try {
    const doc = await api.post('/documents', form.value)
    await api.post(`/documents/${doc.id}/generate`)
    ElMessage.success('生成任务已创建')
    router.push(`/documents/${doc.id}/generate`)
  } catch {
    // 错误提示已由拦截器统一处理
  } finally {
    submitting.value = false
  }
}
</script>

<style scoped>
.layout {
  display: flex;
  gap: 18px;
  align-items: flex-start;
}

.form-col {
  width: 400px;
  flex-shrink: 0;
}

.block {
  margin-bottom: 12px;
}

.block .card-title {
  margin-bottom: 12px;
}

.field {
  margin-bottom: 11px;
}

.field:last-child {
  margin-bottom: 0;
}

.field label {
  display: block;
  font-size: 11px;
  color: var(--ink-3);
  margin-bottom: 5px;
}

.req {
  color: var(--seal);
}

.row2 {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
}

.advice {
  background: var(--gold-soft);
  border: 0.5px solid var(--gold-line);
  border-left: 2px solid var(--gold);
  border-radius: var(--r-sm);
  padding: 11px 13px;
  margin-bottom: 12px;
}

.advice-head {
  display: flex;
  align-items: center;
  gap: 7px;
  margin-bottom: 4px;
}

.advice-dot {
  width: 11px;
  height: 11px;
  border-radius: 50%;
  border: 1px solid var(--gold);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.advice-dot::after {
  content: "";
  width: 4px;
  height: 4px;
  border-radius: 50%;
  background: var(--gold);
}

.advice-title {
  font-size: 12px;
  color: #8a6a1f;
  font-weight: 500;
}

.advice-text {
  font-size: 11px;
  color: #a08b5e;
  line-height: 1.6;
}

.submit {
  width: 100%;
  height: 36px;
  font-size: 13px;
  letter-spacing: 1px;
}

.preview-col {
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
  padding: 30px 36px 34px;
  min-height: 520px;
}

.paper-title {
  font-family: var(--font-serif);
  font-size: 17px;
  color: var(--ink);
  text-align: center;
  line-height: 1.5;
  letter-spacing: 1px;
  margin-bottom: 20px;
}

.paper-to {
  font-size: 12px;
  color: var(--ink);
  margin-bottom: 8px;
}

.paper-p {
  font-size: 12px;
  color: var(--ink);
  line-height: 2;
  text-indent: 2em;
  margin: 0 0 8px;
}

.paper-h {
  font-size: 12px;
  color: var(--ink);
  line-height: 2;
  font-weight: 500;
  text-indent: 2em;
  margin-bottom: 2px;
}

.paper-sign {
  margin-top: 22px;
  text-align: right;
  font-size: 12px;
  color: var(--ink);
  line-height: 1.9;
}
</style>
